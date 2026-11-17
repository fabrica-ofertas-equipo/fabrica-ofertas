"""Pruebas de ``decision.entradas`` (B1b): parametros_decision, evidencia_celda, tracking_sano, serializar.

La base de datos es un SQLite en memoria con el esquema MÍNIMO de docs/06 §4.8 (``dim_anuncio``,
``fact_meta_ad_dia``, ``fact_pedido``, ``fact_meta_conv``): no depende de que ``datos`` (B3) exista.
"""
from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from decision import entradas as ent
from decision.reglas import Accion, Decision, LimitesMeta
from engine.errores import ErrorLimite, ErrorValidacion, ParametroFaltante
from engine.parametros import Parametros

OFERTA = "OF-202611-01"


def _entrada(valor):
    return {"valor": valor, "unidad": "u", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}


def parametros_de_prueba(**cambios) -> Parametros:
    base = {
        "estadistica.prior_conv_fuerza_clics": 50,
        "estadistica.prior_cpc_fuerza_clics": 20,
        "estadistica.alfa_descarte": "0.05",
        "estadistica.alfa_descarte_tope": "0.20",
        "estadistica.k_min_matar": "2.0",
        "estadistica.n_min_escala": 15,
        "estadistica.nodos_cpc": 5,
        "estadistica.dias_madurez_compra": 3,
        "testeo.p_escala": "0.80",
        "testeo.ventana_no_decidir_h": 72,
        "testeo.cobertura_adid_min_pct": 90,
        "testeo.razon_meta_stripe_min": "0.8",
        "testeo.razon_meta_stripe_max": "1.3",
        "testeo.razon_ventana_dias": 7,
        "testeo.razon_n_min": 10,
    }
    base.update(cambios)
    grupos: dict = {}
    for clave, valor in base.items():
        if valor is ELIMINAR:
            continue
        grupo, nombre = clave.split(".")
        grupos.setdefault(grupo, {})[nombre] = _entrada(valor)
    return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": grupos})


ELIMINAR = object()


def economia_de_prueba(**cambios) -> dict:
    base = {
        "cpa_be_visto": {"monto": 1500, "moneda": "EUR"},
        "cpa_obj": {"monto": 900, "moneda": "EUR"},
        "cpc_esperado": {"monto": "40.0", "moneda": "EUR"},
        "conv_central": "0.025",
    }
    base.update(cambios)
    return base


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE dim_anuncio (ad_id TEXT PRIMARY KEY, oferta_id TEXT NOT NULL, concepto_id TEXT);
        CREATE TABLE fact_meta_ad_dia (ad_id TEXT NOT NULL, fecha TEXT NOT NULL, gasto_minor INTEGER NOT NULL, clics_enlace INTEGER NOT NULL);
        CREATE TABLE fact_pedido (oferta_id TEXT NOT NULL, adid TEXT, pagado_en TEXT NOT NULL, estado TEXT NOT NULL,
                                   interno INTEGER NOT NULL DEFAULT 0, verificacion INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE fact_meta_conv (ad_id TEXT NOT NULL, fecha TEXT NOT NULL, ventana TEXT NOT NULL, compras_meta INTEGER NOT NULL);
        """
    )
    return conn


AHORA = datetime(2026, 11, 20, 9, 0, 0, tzinfo=timezone.utc)


def _ahora() -> datetime:
    return AHORA


class PruebaParametrosDecision(unittest.TestCase):
    def test_construye_desde_economia_y_parametros(self) -> None:
        par = parametros_de_prueba()
        pd = ent.parametros_decision(par, economia_de_prueba())
        self.assertEqual(pd.moneda, "EUR")
        self.assertEqual(pd.cpa_equilibrio_minor, 1500)
        self.assertEqual(pd.cpa_objetivo_minor, 900)
        self.assertAlmostEqual(pd.cpc_prior_minor, 40.0)
        self.assertAlmostEqual(pd.prior_conv_media, 0.025)
        self.assertEqual(pd.n_min_escala, 15)
        self.assertAlmostEqual(pd.ventana_no_decidir_h, 72.0)

    def test_falta_alfa_descarte_tope_falla_cerrado(self) -> None:
        par = parametros_de_prueba(**{"estadistica.alfa_descarte_tope": ELIMINAR})
        with self.assertRaises(ParametroFaltante):
            ent.parametros_decision(par, economia_de_prueba())

    def test_ventana_no_decidir_h_acepta_candidato_de_testeo(self) -> None:
        # Confirma que busca primero en "testeo." (el hogar real del esquema) y no solo en "estadistica.".
        par = parametros_de_prueba(**{"testeo.ventana_no_decidir_h": 48})
        pd = ent.parametros_decision(par, economia_de_prueba())
        self.assertAlmostEqual(pd.ventana_no_decidir_h, 48.0)

    def test_economia_incompleta_es_error_de_validacion(self) -> None:
        par = parametros_de_prueba()
        with self.assertRaises(ErrorValidacion):
            ent.parametros_decision(par, {"cpa_be_visto": {"monto": 1500, "moneda": "EUR"}})


class PruebaTrackingSano(unittest.TestCase):
    def test_cobertura_insuficiente_bloquea_si_hay_muestra(self) -> None:
        par = parametros_de_prueba()
        self.assertFalse(ent.tracking_sano(8900, True, None, False, par=par))

    def test_sin_muestra_de_cobertura_no_bloquea(self) -> None:
        # Sin ningún pedido todavía (cobertura_con_muestra=False), un 0 % no es "mala cobertura": es "sin datos".
        par = parametros_de_prueba()
        self.assertTrue(ent.tracking_sano(0, False, None, False, par=par))

    def test_cobertura_suficiente_sin_muestra_de_razon_es_sano(self) -> None:
        par = parametros_de_prueba()
        self.assertTrue(ent.tracking_sano(9500, True, None, False, par=par))

    def test_razon_fuera_de_rango_bloquea(self) -> None:
        par = parametros_de_prueba()
        self.assertFalse(ent.tracking_sano(9500, True, Decimal("1.9"), True, par=par))

    def test_razon_dentro_de_rango_es_sano(self) -> None:
        par = parametros_de_prueba()
        self.assertTrue(ent.tracking_sano(9500, True, Decimal("1.0"), True, par=par))


class PruebaEvidenciaCelda(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _db()
        self.par = parametros_de_prueba()
        self.conn.executemany(
            "INSERT INTO dim_anuncio (ad_id, oferta_id, concepto_id) VALUES (?,?,?)",
            [("1000000000001", OFERTA, "angulo-a"), ("1000000000002", OFERTA, "angulo-a"), ("1000000000003", OFERTA, "angulo-b")],
        )

    def tearDown(self) -> None:
        self.conn.close()

    def _gasto(self, ad_id: str, fecha: str, gasto: int, clics: int) -> None:
        self.conn.execute("INSERT INTO fact_meta_ad_dia VALUES (?,?,?,?)", (ad_id, fecha, gasto, clics))

    def _pedido(self, adid: str | None, pagado_en: str, *, interno: int = 0, verificacion: int = 0, estado: str = "pagado") -> None:
        self.conn.execute(
            "INSERT INTO fact_pedido (oferta_id, adid, pagado_en, estado, interno, verificacion) VALUES (?,?,?,?,?,?)",
            (OFERTA, adid, pagado_en, estado, interno, verificacion),
        )

    def test_agrega_oferta_mercado_y_excluye_dias_inmaduros(self) -> None:
        # dias_madurez_compra=3: el corte es 2026-11-17. El día 19 (inmaduro) no debe contar.
        self._gasto("1000000000001", "2026-11-15", 5000, 100)
        self._gasto("1000000000002", "2026-11-16", 3000, 60)
        self._gasto("1000000000003", "2026-11-19", 9999, 999)  # inmaduro: no debe sumar
        self._pedido("1000000000001", "2026-11-15T10:00:00Z")
        self._pedido("1000000000002", "2026-11-16T10:00:00Z")
        self._pedido(None, "2026-11-16T11:00:00Z")  # sin adid: cuenta para la cobertura, no para esta celda
        ev = ent.evidencia_celda(self.conn, OFERTA, "oferta_mercado", OFERTA, _ahora(), par=self.par, moneda="EUR")
        self.assertEqual(ev.gasto_minor, 8000)
        self.assertEqual(ev.clics, 160)
        self.assertTrue(ev.datos_maduros)
        # cobertura = 2/3 compras con adid -> 6666 bp; compras_corregidas = round(2*10000/6666) = 3
        self.assertEqual(ev.compras, 3)

    def test_celda_anuncio_filtra_por_un_solo_ad_id(self) -> None:
        self._gasto("1000000000001", "2026-11-10", 1000, 20)
        self._gasto("1000000000002", "2026-11-10", 7000, 70)
        self._pedido("1000000000001", "2026-11-10T10:00:00Z")
        ev = ent.evidencia_celda(self.conn, OFERTA, "anuncio", "1000000000001", _ahora(), par=self.par, moneda="EUR")
        self.assertEqual(ev.gasto_minor, 1000)
        self.assertEqual(ev.clics, 20)

    def test_celda_angulo_agrupa_varios_anuncios(self) -> None:
        self._gasto("1000000000001", "2026-11-10", 1000, 20)
        self._gasto("1000000000002", "2026-11-10", 2000, 30)
        self._gasto("1000000000003", "2026-11-10", 5000, 50)
        ev = ent.evidencia_celda(self.conn, OFERTA, "angulo", "angulo-a", _ahora(), par=self.par, moneda="EUR")
        self.assertEqual(ev.gasto_minor, 3000)  # solo angulo-a (anuncios 1 y 2)
        self.assertEqual(ev.clics, 50)

    def test_celda_desconocida_falla_con_validacion(self) -> None:
        with self.assertRaises(ent.CeldaDesconocida):
            ent.evidencia_celda(self.conn, OFERTA, "anuncio", "no-existe", _ahora(), par=self.par, moneda="EUR")

    def test_horas_desde_edicion_usa_el_primer_dia_de_gasto_por_defecto(self) -> None:
        self._gasto("1000000000001", "2026-11-10", 100, 5)
        ev = ent.evidencia_celda(self.conn, OFERTA, "anuncio", "1000000000001", _ahora(), par=self.par, moneda="EUR")
        # AHORA = 2026-11-20T09:00Z, inicio = 2026-11-10T00:00Z -> 10 dias y 9h = 240+9 = 249h
        self.assertAlmostEqual(ev.horas_desde_edicion, 249.0, places=3)

    def test_horas_desde_edicion_inyectada_prevalece(self) -> None:
        self._gasto("1000000000001", "2026-11-10", 100, 5)
        ev = ent.evidencia_celda(self.conn, OFERTA, "anuncio", "1000000000001", _ahora(), par=self.par, moneda="EUR", horas_desde_edicion=5.0)
        self.assertEqual(ev.horas_desde_edicion, 5.0)

    def test_tracking_sano_integrado_con_razon_meta_stripe(self) -> None:
        # Ventana de razón: 7 dias excluyendo los ultimos 2 (ver testeo.razon_ventana_dias/razon_n_min).
        for dia, n in (("2026-11-10", 2), ("2026-11-11", 2), ("2026-11-12", 2), ("2026-11-13", 2), ("2026-11-14", 2)):
            for i in range(n):
                self._pedido("1000000000001", f"{dia}T1{i}:00:00Z")
        self.conn.execute("INSERT INTO fact_meta_conv VALUES (?,?,?,?)", ("1000000000001", "2026-11-12", "1d_click", 10))
        self._gasto("1000000000001", "2026-11-10", 1000, 20)
        ev = ent.evidencia_celda(self.conn, OFERTA, "anuncio", "1000000000001", _ahora(), par=self.par, moneda="EUR")
        # 10 compras stripe con adid (>= razon_n_min=10); meta=10 -> razon=1.0, cobertura=100% -> sano
        self.assertTrue(ev.tracking_sano)


class PruebaSerializar(unittest.TestCase):
    def test_sin_float_en_ningun_campo(self) -> None:
        d = Decision(
            celda_id="c1", accion=Accion.SEGUIR, codigo="zona_gris", explicacion="texto",
            p_cpa_menor_equilibrio=0.1234567, p_cpa_menor_objetivo=0.5, cpa_mediano_minor=1500,
            cpa_ic90_minor=(1200.5, 1800.25), gasto_minor=5000, tope_minor=33000, clics=100, compras=2,
            umbrales={"p_matar": 0.95, "n_min_escala": 15.0},
        )
        bruto = ent.serializar(d)
        self.assertEqual(bruto["accion"], "SEGUIR")

        def _sin_float(x):
            if isinstance(x, float):
                raise AssertionError(f"quedó un float: {x!r}")
            if isinstance(x, dict):
                for v in x.values():
                    _sin_float(v)
            elif isinstance(x, (list, tuple)):
                for v in x:
                    _sin_float(v)

        _sin_float(bruto)
        self.assertIsInstance(bruto["p_cpa_menor_equilibrio"], str)
        self.assertIsInstance(bruto["cpa_ic90_minor"][0], str)

    def test_exige_un_objeto_decision(self) -> None:
        with self.assertRaises(ErrorValidacion):
            ent.serializar({"accion": "SEGUIR"})  # type: ignore[arg-type]


class PruebaFraccionDesdePct(unittest.TestCase):
    def test_convierte_porcentaje_a_fraccion(self) -> None:
        self.assertEqual(ent.fraccion_desde_pct(20), Decimal("0.2"))
        self.assertEqual(ent.fraccion_desde_pct("20"), Decimal("0.2"))

    def test_fuera_de_rango_falla(self) -> None:
        with self.assertRaises(ErrorValidacion):
            ent.fraccion_desde_pct(150)
        with self.assertRaises(ErrorValidacion):
            ent.fraccion_desde_pct(-1)

    def test_limites_meta_desde_construye_limitesmeta(self) -> None:
        class LimFalso:
            def valor(self, clave: str):
                return {
                    "aumento_presupuesto_max_pct_por_paso": 20,
                    "horas_min_entre_aumentos": 72,
                    "factor_techo_teorico_diario": "1.75",
                    "max_cambios_presupuesto_por_hora_por_conjunto": 4,
                    "segundos_min_entre_ediciones": 30,
                }[clave]

        lm = ent.limites_meta_desde(LimFalso())
        self.assertIsInstance(lm, LimitesMeta)
        self.assertAlmostEqual(lm.paso_max_pct, 0.2)


if __name__ == "__main__":
    unittest.main()
