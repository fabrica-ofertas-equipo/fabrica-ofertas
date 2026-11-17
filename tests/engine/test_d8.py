"""Pruebas de ``engine.d8``: ``ciclo`` (lectura diaria, pausa, senal_pausa) y ``veredicto`` (B0-16, B0-19, B0-22).

Raíz temporal propia (nunca ``empresa/`` real); SQLite en memoria con las migraciones REALES de
``datos`` (``datos.db.migrar``: ``dim_anuncio``, ``fact_meta_ad_dia``, ``fact_pedido``,
``fact_reembolso`` y las vistas ``v_d8_*`` de ``datos/migraciones/0003_vistas_d8.sql``) para el almacén
de ``datos`` (``conn``), inyectado por separado de ``empresa/motor.db`` (propio del motor, para
``estado.json``): las pruebas de ``ciclo``/``veredicto`` no necesitan ``engine.estado.abrir_base`` (que
junta los dos) porque reciben ``conn`` inyectado, igual que ``orq`` lo hace en producción.
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from datos.db import Conexion as _ConexionDatos
from datos.db import migrar as _migrar_datos

from engine import comun, d8, estado
from engine.ejecutor import EjecutorMotor
from engine.errores import ErrorBloqueado
from engine.limites import Limites
from engine.parametros import Parametros

OFERTA = "OF-202611-01"


def _entrada(valor):
    return {"valor": valor, "unidad": "u", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}


def _parametros() -> Parametros:
    plano = {
        "estadistica.prior_conv_fuerza_clics": 50, "estadistica.prior_cpc_fuerza_clics": 20,
        "estadistica.alfa_descarte": "0.05", "estadistica.alfa_descarte_tope": "0.20", "estadistica.k_min_matar": "2.0",
        "estadistica.n_min_escala": 15, "estadistica.nodos_cpc": 5, "estadistica.dias_madurez_compra": 2,
        "estadistica.k_min_fallida": "3.0",
        "testeo.p_escala": "0.80", "testeo.ventana_no_decidir_h": 0, "testeo.cobertura_adid_min_pct": 90,
        "testeo.razon_meta_stripe_min": "0.8", "testeo.razon_meta_stripe_max": "1.3", "testeo.razon_ventana_dias": 7,
        "testeo.razon_n_min": 1000,  # alto a propósito: sin suficientes pedidos, la razón no bloquea en estas pruebas
        "testeo.p_fallida": "0.95",
        "veredicto.madurez_dias_extra": 7, "veredicto.compras_min": 3, "veredicto.dias_min": 3,
        "veredicto.max_dia_pct": 80, "veredicto.reembolso_max_pct": 50,
        "economia.factor_cpa_objetivo": "0.6",
        "salud_operativa.reembolsos_objetivo_pct": 7,
    }
    grupos: dict = {}
    for clave, valor in plano.items():
        grupo, nombre = clave.split(".")
        grupos.setdefault(grupo, {})[nombre] = _entrada(valor)
    return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": grupos})


def _limites(**cambios) -> Limites:
    datos = {
        "moneda_limites": "EUR", "gasto_total_test_por_oferta": 33000, "gasto_diario_por_oferta": 3000,
        "factor_techo_teorico_diario": "1.75", "politica_reembolso_dias": 14,
    }
    datos.update(cambios)
    return Limites(datos=datos, entorno="prueba")


def _db() -> sqlite3.Connection:
    """SQLite en memoria con las migraciones REALES de ``datos`` aplicadas (0001, 0002, 0003): las
    mismas tablas y vistas ``v_d8_*`` que ``engine.estado.abrir_base`` deja en producción, nunca un DDL
    propio de esta prueba (ver README del componente, «Decisiones»)."""
    conn = sqlite3.connect(":memory:")
    _migrar_datos(_ConexionDatos(conn, "sqlite", "sqlite:///:memory:"))
    return conn


def _insertar_anuncio(conn: sqlite3.Connection, ad_id: str, oferta_id: str, concepto_id: str | None = None) -> None:
    conn.execute("INSERT INTO dim_anuncio (ad_id, oferta_id, concepto_id) VALUES (?,?,?)", (ad_id, oferta_id, concepto_id))


def _insertar_gasto(conn: sqlite3.Connection, ad_id: str, fecha: str, gasto_minor: int, clics_enlace: int, *,
                    oferta_id: str = OFERTA, pull_ts: str | None = None, compras_meta: int = 0) -> None:
    """Fila real de ``fact_meta_ad_dia`` (columnas que no importan a esta prueba quedan con un valor
    cualquiera no nulo: ``v_d8_gasto_dia``/``v_d8_conv_meta`` solo exponen lo que ``engine.d8`` lee)."""
    conn.execute(
        "INSERT INTO fact_meta_ad_dia (ad_id, fecha, oferta_id, campaign_id, adset_id, tz, gasto_minor, moneda, "
        "impresiones, clics, clics_enlace, compras_meta, ingerido_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ad_id, fecha, oferta_id, "CAMP-01", "ADSET-01", "Europe/Madrid", gasto_minor, "EUR",
         clics_enlace, clics_enlace, clics_enlace, compras_meta, pull_ts or f"{fecha}T23:59:00Z"),
    )


def _insertar_pedido(conn: sqlite3.Connection, session_id: str, oferta_id: str, adid: str | None, pagado_en: str,
                     estado: str, interno: int, verificacion: int, moneda: str, bruto_minor: int,
                     impuesto_minor: int = 0, fee_minor: int = 0) -> None:
    """Fila real de ``fact_pedido`` (nombres de columna de docs/06 §4.8: ``es_interna``/``es_prueba``
    son ``interno``/``verificacion`` en ``v_d8_pedido``)."""
    conn.execute(
        "INSERT INTO fact_pedido (checkout_session_id, oferta_id, adid, monto_minor, moneda, creado_ts, dia_utc, "
        "es_prueba, es_interna, estado, impuesto_minor, fee_minor, ingerido_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (session_id, oferta_id, adid, bruto_minor, moneda, pagado_en, pagado_en[:10],
         verificacion, interno, estado, impuesto_minor, fee_minor, pagado_en),
    )


def _insertar_reembolso(conn: sqlite3.Connection, refund_id: str, oferta_id: str, session_id: str, monto_minor: int,
                        moneda: str = "EUR", creado_ts: str = "2026-11-01T00:00:00Z") -> None:
    """Fila real de ``fact_reembolso``: toda fila presente cuenta como ``ejecutado`` en ``v_d8_reembolso``
    (el esquema real no tiene un paso «reservado», docs/06 §4.8)."""
    conn.execute(
        "INSERT INTO fact_reembolso (stripe_refund_id, oferta_id, checkout_session_id, monto_minor, moneda, "
        "creado_ts, dia_utc, ingerido_en) VALUES (?,?,?,?,?,?,?,?)",
        (refund_id, oferta_id, session_id, monto_minor, moneda, creado_ts, creado_ts[:10], creado_ts),
    )


def _estado_inicial(oferta_id: str, *, fase: str = "en_test") -> dict:
    campo = {
        "estado": "aprobado", "version_aprobada": "v1", "hash_salida": "sha256:" + "ab" * 32, "entradas": {},
        "ronda_qa": 0, "intentos": 0, "gate": "A", "gate_pendiente": False, "nivel": "N2",
        "aprobado_por": None, "bloqueo": None, "idempotency_key": None, "obsoleta": False,
    }
    etapas = {e: dict(campo) for e in ("M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10")}
    return {
        "schema_version": "1.1.0", "oferta_id": oferta_id, "familia_id": "FAM-202611-01", "revision": 1,
        "nivel": "N2", "pausa": False, "fase": fase, "skills_pin": {}, "etapas": etapas,
        "candidato_elegido": None, "gasto": {"acumulado": {"monto": 0, "moneda": "EUR"}, "hoy": {"monto": 0, "moneda": "EUR"}},
        "costo_ia": {"monto": 0, "moneda": "EUR"}, "actualizado_en": "2026-11-01T00:00:00Z",
    }


def _economia() -> dict:
    return {
        "cpa_be_visto": {"monto": 1500, "moneda": "EUR"}, "cpa_obj": {"monto": 900, "moneda": "EUR"},
        "cpc_esperado": {"monto": "40.0", "moneda": "EUR"}, "conv_central": "0.025",
    }


class PruebaBaseD8(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fabrica-d8-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        comun.escribir_atomico(self.tmp / "ofertas" / OFERTA / "estado.json", comun.json_canonico(_estado_inicial(OFERTA)))
        comun.escribir_atomico(self.tmp / "ofertas" / OFERTA / "03-oferta" / "economia.json", comun.json_canonico(_economia()))
        self.conn = _db()
        self.conn.execute("INSERT INTO dim_anuncio VALUES (?,?,?)", ("1000000000001", OFERTA, "angulo-a"))
        self.par = _parametros()
        self.lim = _limites()
        self.ejecutor = EjecutorMotor(raiz=self.tmp, ahora=self._ahora)

    def tearDown(self) -> None:
        self.conn.close()

    def _ahora(self) -> datetime:
        return self._instante

    _instante = datetime(2026, 11, 20, 9, 0, 0, tzinfo=timezone.utc)


class PruebaGastoEfectivo(unittest.TestCase):
    def test_sin_horas_sin_lectura_es_el_gasto_leido(self) -> None:
        self.assertEqual(d8.gasto_efectivo(5000, diario_minor=3000, horas_sin_lectura=0.0, factor="1.75"), 5000)

    def test_con_horas_sin_lectura_suma_el_techo_teorico(self) -> None:
        # 1,75 * 3000 * (24/24) = 5250
        self.assertEqual(d8.gasto_efectivo(1000, diario_minor=3000, horas_sin_lectura=24.0, factor="1.75"), 1000 + 5250)

    def test_redondea_siempre_hacia_arriba(self) -> None:
        v = d8.gasto_efectivo(0, diario_minor=1, horas_sin_lectura=1.0, factor="1.75")
        self.assertEqual(v, 1)  # 1,75 * 1 * (1/24) = 0,0729... -> hacia arriba, 1


class PruebaCiclo(unittest.TestCase):
    def setUp(self) -> None:
        self.base = PruebaBaseD8()
        self.base.setUp()
        self.addCleanup(self.base.tearDown)

    def test_sin_evidencia_sigue_sin_decidir_y_sin_pausar(self) -> None:
        b = self.base
        registros = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="live", raiz=b.tmp)
        acciones = {r["objeto_id"]: r["accion"] for r in registros}
        self.assertEqual(acciones[OFERTA], "SEGUIR")
        self.assertEqual(acciones["1000000000001"], "SEGUIR")
        est = estado.cargar(OFERTA, raiz=b.tmp)
        self.assertEqual(est["fase"], "en_test")

    def test_matar_anuncio_con_gasto_alto_y_cero_compras(self) -> None:
        b = self.base
        _insertar_gasto(b.conn, "1000000000001", "2026-11-10", 6000, 150, pull_ts="2026-11-20T08:00:00Z")
        registros = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="live", raiz=b.tmp)
        por_objeto = {r["objeto_id"]: r for r in registros}
        self.assertEqual(por_objeto["1000000000001"]["accion"], "MATAR")
        # Sin pausador_meta inyectado, EjecutorMotor no puede pausar un ID de Meta: se registra pero no se ejecuta.
        self.assertFalse(por_objeto["1000000000001"]["ejecutada"])

    def test_dry_run_no_pausa_ni_consume_senal(self) -> None:
        b = self.base
        ruta_senal = b.tmp / "ofertas" / OFERTA / "10-postcompra" / "senal_pausa.json"
        comun.escribir_atomico(ruta_senal, comun.json_canonico(_senal_pausa()))
        registros = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="dry_run", raiz=b.tmp)
        self.assertTrue(registros)
        senal = comun.cargar_json(ruta_senal)
        self.assertIsNone(senal["consumida_por"])
        est = estado.cargar(OFERTA, raiz=b.tmp)
        self.assertEqual(est["fase"], "en_test")

    def test_senal_pausa_detiene_la_oferta_y_se_consume_una_sola_vez(self) -> None:
        b = self.base
        ruta_senal = b.tmp / "ofertas" / OFERTA / "10-postcompra" / "senal_pausa.json"
        comun.escribir_atomico(ruta_senal, comun.json_canonico(_senal_pausa()))
        registros = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="live", raiz=b.tmp)
        self.assertEqual(registros[0]["accion"], "INCONCLUSO")
        self.assertTrue(registros[0]["ejecutada"])
        est = estado.cargar(OFERTA, raiz=b.tmp)
        self.assertEqual(est["fase"], "pausada")
        senal = comun.cargar_json(ruta_senal)
        self.assertEqual(senal["consumida_por"]["etapa"], "D8")
        decision_id_1 = senal["consumida_por"]["decision_id"]
        # Segunda corrida: la oferta ya no está en_test -> no hay nada más que decidir, y la señal no se reprocesa.
        registros2 = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="live", raiz=b.tmp)
        self.assertEqual(registros2, [])
        self.assertEqual(comun.cargar_json(ruta_senal)["consumida_por"]["decision_id"], decision_id_1)

    def test_tope_de_gasto_sin_veredicto_mueve_la_fase_a_inconclusa(self) -> None:
        b = self.base
        # gasto_total_test_por_oferta=33000, 750 clics y 20 compras: zona ambigua (ni MATAR ni ESCALAR), en el tope.
        _insertar_gasto(b.conn, "1000000000001", "2026-11-10", 33000, 750, pull_ts="2026-11-20T08:00:00Z")
        for i in range(20):
            _insertar_pedido(b.conn, f"cs_{i}", OFERTA, "1000000000001", "2026-11-10T10:00:00Z", "pagado", 0, 0, "EUR", 1700, fee_minor=50)
        registros = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="live", raiz=b.tmp)
        por_objeto = {r["objeto_id"]: r for r in registros}
        self.assertEqual(por_objeto[OFERTA]["accion"], "INCONCLUSO")
        est = estado.cargar(OFERTA, raiz=b.tmp)
        self.assertEqual(est["fase"], "inconclusa")

    def test_fase_no_en_test_no_decide_nada(self) -> None:
        b = self.base
        estado.transicionar_fase(OFERTA, "pausada", actor="dueno", causa="prueba", raiz=b.tmp, ahora=b._ahora)
        registros = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="live", raiz=b.tmp)
        self.assertEqual(registros, [])


class PruebaTraspasoDeD7(unittest.TestCase):
    """Un lanzamiento marcado INESTABLE en ``07-campana/traspaso.json`` no se ESCALA (escalar gasta más); matar y el
    cierre por tope SIGUEN activos porque limitan la pérdida. Sin archivo, comportamiento de siempre."""

    def setUp(self) -> None:
        self.base = PruebaBaseD8()
        self.base.setUp()
        self.addCleanup(self.base.tearDown)

    def _datos_de_ganador(self) -> None:
        b = self.base
        _insertar_gasto(b.conn, "1000000000001", "2026-11-10", 10000, 400, pull_ts="2026-11-20T08:00:00Z")
        for i in range(25):
            _insertar_pedido(b.conn, f"cs_{i}", OFERTA, "1000000000001", "2026-11-10T10:00:00Z", "pagado", 0, 0, "EUR", 2900, fee_minor=90)

    def _traspaso(self, **cambios) -> None:
        doc = {"schema_version": "1.1.0", "oferta_id": OFERTA, "ventana_h": 72, "medido_en": "2026-11-20T08:00:00Z",
               "campana": {"campaign_id": "1000000000010", "effective_status": "ACTIVE"},
               "anuncios": [{"ad_id": "1000000000001", "effective_status": "ACTIVE", "rechazado": False}],
               "gasto": {"real": {"monto": 1, "moneda": "EUR"}, "esperado": {"monto": 1, "moneda": "EUR"}},
               "estado_aprendizaje": "LEARNING", "rechazos_7d": 0, "adid_capturado_bp": 9500, "clics_enlace": 1, "vistas_landing": 1,
               "anomalias": [], "lanzamiento_estable": True}
        doc.update(cambios)
        comun.escribir_atomico(self.base.tmp / "ofertas" / OFERTA / "07-campana" / "traspaso.json", comun.json_canonico(doc))

    def _correr(self) -> dict:
        b = self.base
        registros = d8.ciclo(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, ejecutor=b.ejecutor, modo="dry_run", raiz=b.tmp)
        return {r["objeto_id"]: r for r in registros}

    def test_sin_traspaso_un_ganador_escala(self) -> None:
        self._datos_de_ganador()
        self.assertEqual(self._correr()["1000000000001"]["accion"], "ESCALAR")  # línea base: el escenario sí escala

    def test_traspaso_estable_no_cambia_nada(self) -> None:
        self._datos_de_ganador()
        self._traspaso()
        self.assertEqual(self._correr()["1000000000001"]["accion"], "ESCALAR")

    def test_ventana_de_72h_sin_estabilidad_no_escala(self) -> None:
        self._datos_de_ganador()
        self._traspaso(lanzamiento_estable=False)
        r = self._correr()["1000000000001"]
        self.assertEqual((r["accion"], r["codigo"]), ("SEGUIR", d8.CODIGO_ENTREGA_INESTABLE))
        self.assertIn("72 h", r["explicacion"])

    def test_anomalias_no_escalan_aunque_diga_estable(self) -> None:
        self._datos_de_ganador()
        self._traspaso(anomalias=["gasto-fuera-de-ritmo"])
        self.assertEqual(self._correr()["1000000000001"]["codigo"], d8.CODIGO_ENTREGA_INESTABLE)

    def test_ventana_parcial_sin_estabilidad_todavia_no_bloquea(self) -> None:
        # ventana_h < 72 y estable=false es lo normal en T+1..48 h: ahí manda el tiempo (ventana_no_decidir_h), no el traspaso.
        self._datos_de_ganador()
        self._traspaso(ventana_h=24, lanzamiento_estable=False)
        self.assertEqual(self._correr()["1000000000001"]["accion"], "ESCALAR")

    def test_archivo_ilegible_o_de_forma_rara_falla_cerrado_sin_escalar(self) -> None:
        self._datos_de_ganador()
        ruta = self.base.tmp / "ofertas" / OFERTA / "07-campana" / "traspaso.json"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        for contenido in ("{", "[]", '{"lanzamiento_estable": "si"}', "\ufeff{}"):
            with self.subTest(contenido=contenido):
                ruta.write_text(contenido, encoding="utf-8")
                self.assertEqual(self._correr()["1000000000001"]["codigo"], d8.CODIGO_ENTREGA_INESTABLE)

    def test_un_lanzamiento_inestable_sigue_pudiendo_matar(self) -> None:
        b = self.base
        _insertar_gasto(b.conn, "1000000000001", "2026-11-10", 6000, 150, pull_ts="2026-11-20T08:00:00Z")
        self._traspaso(lanzamiento_estable=False, anomalias=["gasto-fuera-de-ritmo"])
        self.assertEqual(self._correr()["1000000000001"]["accion"], "MATAR")  # limita la pérdida: no se frena

    def test_un_lanzamiento_inestable_sigue_cerrando_por_tope(self) -> None:
        b = self.base
        _insertar_gasto(b.conn, "1000000000001", "2026-11-10", 33000, 750, pull_ts="2026-11-20T08:00:00Z")
        for i in range(20):
            _insertar_pedido(b.conn, f"cs_{i}", OFERTA, "1000000000001", "2026-11-10T10:00:00Z", "pagado", 0, 0, "EUR", 1700, fee_minor=50)
        self._traspaso(lanzamiento_estable=False)
        self.assertEqual(self._correr()[OFERTA]["accion"], "INCONCLUSO")


def _senal_pausa() -> dict:
    return {
        "schema_version": "1.1.0", "oferta_id": OFERTA, "ts": "2026-11-20T08:00:00Z", "emitida": True,
        "nivel": "rojo", "motivo": "reembolsos",
        "metricas": {"muestra_suficiente": True, "pagos_ventana": 25, "casos_disputa_efw": 0,
                     "disputas_efw_pct": "0", "reembolsos_pct": "15", "ventana_dias": 30},
        "umbrales_usados": {"disputas_alerta_pct": "0.3", "ratio_disputas_pausa": "0.006",
                             "reembolsos_alerta_pct": "8", "reembolsos_pausa_pct": "12"},
        "accion_solicitada": "pausar", "consumida_por": None,
    }


class PruebaVeredicto(unittest.TestCase):
    def setUp(self) -> None:
        self.base = PruebaBaseD8()
        self.base.setUp()
        self.addCleanup(self.base.tearDown)

    def _pedido(self, session_id: str, pagado_en: str, bruto: int, *, adid: str = "1000000000001") -> None:
        _insertar_pedido(self.base.conn, session_id, OFERTA, adid, pagado_en, "pagado", 0, 0, "EUR", bruto, fee_minor=50)

    def test_sin_compras_es_inconclusa_y_no_rompe_nada(self) -> None:
        b = self.base
        doc = d8.veredicto(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, raiz=b.tmp)
        self.assertEqual(doc["estado"], "INCONCLUSA")
        self.assertEqual(doc["recomendacion"], "extender_test")

    def test_cohorte_madura_ganadora_es_validada(self) -> None:
        b = self.base
        # 5 compras en 5 dias distintos (dias_con_compras_min=3), gasto bajo frente al margen -> P(CPA<=BE) alto.
        for i in range(5):
            self._pedido(f"cs_{i}", f"2026-10-0{i + 1}T10:00:00Z", 2700)
        for i in range(5):
            _insertar_gasto(b.conn, "1000000000001", f"2026-10-0{i + 1}", 200, 15)
        doc = d8.veredicto(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, raiz=b.tmp)
        self.assertEqual(doc["estado"], "VALIDADA")
        self.assertEqual(doc["recomendacion"], "escalar")
        self.assertIsNotNone(doc["evidencia"]["cpa_neto"])

    def test_gasto_alto_con_una_sola_compra_mala_es_fallida(self) -> None:
        b = self.base
        # 1 compra entre 7 dias de gasto alto (14000 gasto / 350 clics): CPA muy por encima del equilibrio.
        self._pedido("cs_x", "2026-10-01T10:00:00Z", 2700)
        for i in range(7):
            _insertar_gasto(b.conn, "1000000000001", f"2026-10-0{i + 1}", 2000, 50)
        doc = d8.veredicto(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, raiz=b.tmp)
        self.assertEqual(doc["estado"], "FALLIDA")
        self.assertEqual(doc["recomendacion"], "cerrar")

    def test_funciona_con_la_campana_ya_cerrada_sin_gastar_mas(self) -> None:
        # B0-22: tras cerrar, el ETL y el veredicto siguen; aquí no hay fact_meta_ad_dia nuevo (gasto = 0 desde el cierre).
        b = self.base
        estado.transicionar_fase(OFERTA, "pausada", actor="motor", causa="cierre", raiz=b.tmp, ahora=b._ahora)
        doc = d8.veredicto(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, raiz=b.tmp)
        self.assertIn(doc["estado"], ("INCONCLUSA", "PROMETEDORA", "VALIDADA", "FALLIDA"))
        self.assertEqual(doc["evidencia"]["gasto"]["monto"], 0)

    def test_falta_economia_json_bloquea(self) -> None:
        b = self.base
        (b.tmp / "ofertas" / OFERTA / "03-oferta" / "economia.json").unlink()
        with self.assertRaises(ErrorBloqueado):
            d8.veredicto(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, raiz=b.tmp)

    def test_escribe_version_siguiente_al_repetir(self) -> None:
        b = self.base
        d1 = d8.veredicto(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, raiz=b.tmp)
        d2 = d8.veredicto(OFERTA, conn=b.conn, ahora=b._ahora, par=b.par, lim=b.lim, raiz=b.tmp)
        self.assertEqual(d1["version"], "v1")
        self.assertEqual(d2["version"], "v2")


if __name__ == "__main__":
    unittest.main()
