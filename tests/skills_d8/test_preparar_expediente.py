"""Pruebas de ``preparar_expediente.py``: lee la base SOLO en lectura y arma la entrada de D8 sin ``float``."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tests.skills_d8._comun import ADS, CAMPANA, OFERTA, RAIZ, cargar_modulo, crear_base, evento, meta, no_hay_floats, pedido

E = cargar_modulo("preparar_expediente")
AHORA = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)  # 10:00 en Varsovia: el 08/11 cerró hace 10 h (600 min con UTC+1)


def sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.db = self.dir / "fabrica.db"
        crear_base(self.db)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def escribir(self, fn) -> None:
        conn = sqlite3.connect(self.db)
        fn(conn)
        conn.commit()
        conn.close()

    def armar(self, fecha="2026-11-08", **kw) -> dict:
        conn = E.abrir_ro(self.db)
        try:
            return E.armar_entrada(conn, OFERTA, fecha, ahora=kw.pop("ahora", AHORA), **kw)
        finally:
            conn.close()


class PruebaSoloLectura(Base):
    def test_la_conexion_no_puede_escribir(self) -> None:
        conn = E.abrir_ro(self.db)
        for sql in ("INSERT INTO dim_anuncio (ad_id, oferta_id) VALUES ('x','y')", "DELETE FROM dim_anuncio", "DROP TABLE dim_anuncio",
                    "UPDATE dim_anuncio SET concepto_id = 'z'", "CREATE TABLE t (a)"):
            with self.assertRaises(sqlite3.OperationalError, msg=sql):
                conn.execute(sql)
        conn.close()

    def test_armar_la_entrada_no_cambia_ni_un_byte_de_la_base(self) -> None:
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-08", 7400))
        antes = sha(self.db)
        self.armar()
        self.assertEqual(sha(self.db), antes)

    def test_base_inexistente_es_bloqueo_4(self) -> None:
        with self.assertRaises(E.ErrorEntrada) as cm:
            E.abrir_ro(self.dir / "no_existe.db")
        self.assertEqual(cm.exception.codigo, 4)

    def test_sin_migraciones_es_bloqueo_4(self) -> None:
        vacia = self.dir / "vacia.db"
        sqlite3.connect(vacia).close()
        conn = E.abrir_ro(vacia)
        with self.assertRaises(E.ErrorEntrada) as cm:
            E.armar_entrada(conn, OFERTA, "2026-11-08", ahora=AHORA)
        self.assertEqual(cm.exception.codigo, 4)
        conn.close()


class PruebaCifrasDelDia(Base):
    def cargar_dia1(self) -> None:
        def f(c):
            meta(c, ADS[0], "2026-11-08", 3000, impr=8000, clics=70)
            meta(c, ADS[1], "2026-11-08", 2900, impr=6000, clics=50)
            meta(c, ADS[2], "2026-11-08", 1500, impr=4000, clics=40)
            for i in range(130):
                evento(c, f"pv{i}", "PageView", f"vis{i}", "2026-11-08T12:00:00Z", adid=ADS[0] if i % 2 else None)
            for i in range(4):
                evento(c, f"ic{i}", "InitiateCheckout", f"vis{i}", "2026-11-08T13:00:00Z", adid=ADS[0])
        self.escribir(f)

    def test_dia1_sin_venta(self) -> None:
        self.cargar_dia1()
        e = self.armar()
        d = e["dia"]
        self.assertEqual((d["gasto_minor"], d["impresiones"], d["clics_enlace"]), (7400, 18000, 160))
        self.assertEqual((d["vistas_landing"], d["initiate_checkout"]), (130, 4))
        self.assertEqual((d["ventas_stripe_total"], d["pedidos_pendientes"]), (0, 0))
        self.assertTrue(d["cerrado"])
        self.assertEqual(d["minutos_desde_cierre"], 600)
        self.assertTrue(d["ingesta_meta_posterior_al_cierre"])
        self.assertEqual((e["primer_dia_con_gasto"], e["dias_cerrados_desde_primer_gasto"]), ("2026-11-08", 1))
        self.assertEqual((e["tz"], e["moneda_meta"], e["campaign_ids"]), ("Europe/Warsaw", "USD", [CAMPANA]))
        self.assertEqual(e["frescura"]["edad_ingesta_meta_min"], 30)
        self.assertEqual(no_hay_floats(e), [])
        self.assertTrue(e["solo_lectura"])
        json.dumps(e)

    def test_ventas_atribucion_pruebas_internos_y_pendientes(self) -> None:
        self.cargar_dia1()
        def f(c):
            pedido(c, "s1", "2026-11-08T10:00:00Z", adid=ADS[1])                       # real y atribuida
            pedido(c, "s2", "2026-11-08T11:00:00Z", adid="desconocido")                # real sin atribución
            pedido(c, "s3", "2026-11-08T11:30:00Z", adid=ADS[0], prueba=1)             # prueba: no cuenta
            pedido(c, "s4", "2026-11-08T11:40:00Z", adid=ADS[0], interna=1)            # interna: no cuenta
            pedido(c, "s5", "2026-11-08T12:00:00Z", adid=ADS[0], estado="unpaid")      # pago asíncrono pendiente
            pedido(c, "s6", "2026-11-08T22:30:00Z", adid=ADS[0])                       # 23:30 en Varsovia: sigue siendo el día 8
            pedido(c, "s7", "2026-11-08T23:30:00Z", adid=ADS[0])                       # 00:30 del 9 en Varsovia: es del día 9
            pedido(c, "s8", "2026-11-08T14:00:00Z", adid="999")                        # adid ajeno a la oferta: sin atribución
        self.escribir(f)
        e = self.armar()
        d = e["dia"]
        self.assertEqual((d["ventas_stripe_total"], d["ventas_stripe_atribuidas"], d["ventas_stripe_sin_atribucion"]), (4, 2, 2))
        self.assertEqual(d["pedidos_pendientes"], 1)
        por_ad = {a["ad_id"]: a["por_dia"]["2026-11-08"]["ventas_stripe"] for a in e["anuncios"]}
        self.assertEqual(por_ad, {ADS[0]: 1, ADS[1]: 1, ADS[2]: 0})
        self.assertEqual(e["cobertura_adid_bp"], 7500)  # 3 de 4 pagados traen adid

    def test_la_venta_de_la_medianoche_local_va_al_dia_siguiente(self) -> None:
        self.cargar_dia1()
        self.escribir(lambda c: pedido(c, "s7", "2026-11-08T23:30:00Z"))
        self.assertEqual(self.armar("2026-11-08")["dia"]["ventas_stripe_total"], 0)
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-09", 100))
        self.assertEqual(self.armar("2026-11-09", ahora=datetime(2026, 11, 10, 9, tzinfo=timezone.utc))["dia"]["ventas_stripe_total"], 1)

    def test_reembolsos_y_disputas_con_la_columna_real(self) -> None:
        self.cargar_dia1()
        def f(c):
            pedido(c, "s1", "2026-11-08T10:00:00Z")
            c.execute("INSERT INTO fact_reembolso (stripe_refund_id, oferta_id, checkout_session_id, adid, monto_minor, moneda, motivo, creado_ts, dia_utc, ingerido_en) "
                      "VALUES ('re_1',?,?,?,?,?,?,?,?,?)", (OFERTA, "s1", ADS[0], 6300, "PLN", None, "2026-11-08T11:00:00Z", "2026-11-08", "2026-11-08T11:00:00Z"))
            c.execute("INSERT INTO fact_disputa (dispute_id, oferta_id, checkout_session_id, monto_minor, moneda, estado, creado_ts, dia_utc, ingerido_en) "
                      "VALUES ('dp_1',?,?,?,?,?,?,?,?)", (OFERTA, "s1", 6300, "PLN", "needs_response", "2026-11-08T12:00:00Z", "2026-11-08", "2026-11-08T12:00:00Z"))
            c.execute("INSERT INTO fact_disputa (dispute_id, oferta_id, checkout_session_id, monto_minor, moneda, estado, creado_ts, dia_utc, ingerido_en) "
                      "VALUES ('dp_2',?,?,?,?,?,?,?,?)", (OFERTA, "s1", 6300, "PLN", "won", "2026-11-08T12:00:00Z", "2026-11-08", "2026-11-08T12:00:00Z"))
        self.escribir(f)
        e = self.armar()
        self.assertEqual((e["dia"]["ventas_con_reembolso"], e["disputas_abiertas"]), (1, 1))

    def test_dia_que_no_cerro(self) -> None:
        self.cargar_dia1()
        e = self.armar(ahora=datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc))
        self.assertFalse(e["dia"]["cerrado"])
        self.assertEqual(e["dias_cerrados_desde_primer_gasto"], 0)

    def test_lectura_de_meta_anterior_al_cierre_se_marca(self) -> None:
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-08", 7400, ingerido="2026-11-08T15:00:00Z"))
        e = self.armar()
        self.assertFalse(e["dia"]["ingesta_meta_posterior_al_cierre"])

    def test_serie_con_ceros_explicitos_y_acumulado(self) -> None:
        def f(c):
            meta(c, ADS[0], "2026-11-06", 500)
            meta(c, ADS[0], "2026-11-08", 7400)
        self.escribir(f)
        e = self.armar(dias=5)
        self.assertEqual([s["fecha"] for s in e["serie_oferta"]], ["2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"])
        self.assertEqual([s["gasto_minor"] for s in e["serie_oferta"]], [0, 0, 500, 0, 7400])
        self.assertEqual((e["primer_dia_con_gasto"], e["acumulado"]["gasto_minor"], e["dias_cerrados_desde_primer_gasto"]), ("2026-11-06", 7900, 3))

    def test_sin_filas_de_meta_avisa_y_no_inventa(self) -> None:
        e = self.armar()
        self.assertIsNone(e["primer_dia_con_gasto"])
        self.assertIsNone(e["frescura"]["ultima_ingesta_meta_ts"])
        self.assertTrue(any("tz_asumida_utc" in a for a in e["avisos"]))

    def test_monedas_mezcladas_se_avisan(self) -> None:
        def f(c):
            meta(c, ADS[0], "2026-11-08", 100, moneda="USD")
            meta(c, ADS[1], "2026-11-08", 100, moneda="EUR")
        self.escribir(f)
        e = self.armar()
        self.assertIsNone(e["moneda_meta"])
        self.assertTrue(any(a.startswith("monedas_meta_mezcladas") for a in e["avisos"]))

    def test_dos_zonas_horarias_exigen_tz(self) -> None:
        def f(c):
            meta(c, ADS[0], "2026-11-08", 100, tz="Europe/Warsaw")
            meta(c, ADS[1], "2026-11-08", 100, tz="America/Santiago")
        self.escribir(f)
        with self.assertRaises(E.ErrorEntrada):
            self.armar()
        self.assertEqual(self.armar(tz="Europe/Warsaw")["tz"], "Europe/Warsaw")

    def test_argumentos_invalidos(self) -> None:
        conn = E.abrir_ro(self.db)
        for oferta, fecha in (("malo", "2026-11-08"), (OFERTA, "08/11/2026")):
            with self.assertRaises(E.ErrorEntrada):
                E.armar_entrada(conn, oferta, fecha, ahora=AHORA)
        with self.assertRaises(E.ErrorEntrada):
            E.armar_entrada(conn, OFERTA, "2026-11-08", ahora=AHORA, tz="Marte/Olympus")
        conn.close()


class PruebaContextoDeArchivos(Base):
    def raiz_con(self, *, pausa=False, infra="VERDE", diario=7500, pedidos=None) -> Path:
        raiz = self.dir / "repo"
        (raiz / "empresa" / "infra").mkdir(parents=True)
        (raiz / "ofertas" / OFERTA / "07-campana").mkdir(parents=True)
        (raiz / "ofertas" / OFERTA / "08-operacion").mkdir(parents=True)
        if pausa:
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
        if infra:
            (raiz / "empresa" / "infra" / "estado.json").write_text(json.dumps({"semaforo": infra}), encoding="utf-8")
        (raiz / "ofertas" / OFERTA / "07-campana" / "campana.json").write_text(
            json.dumps({"presupuesto": {"diario": diario, "moneda": "USD"}}), encoding="utf-8")
        (raiz / "ofertas" / OFERTA / "07-campana" / "traspaso.json").write_text(json.dumps({"lanzamiento_estable": True}), encoding="utf-8")
        if pedidos is not None:
            (raiz / "ofertas" / OFERTA / "08-operacion" / "pedidos_creativos.json").write_text(json.dumps({"pedidos": pedidos}), encoding="utf-8")
        return raiz

    def test_lee_pausa_infra_presupuesto_traspaso_y_pedidos(self) -> None:
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-08", 7400))
        raiz = self.raiz_con(pedidos=[{"estado": "abierto"}, {"estado": "cerrado"}])
        e = self.armar(raiz=raiz)
        self.assertEqual(e["contexto"], {"pausa_activa": False, "infra_semaforo": "VERDE", "traspaso_lanzamiento_estable": True,
                                         "pedidos_creativos_abiertos": 1})
        self.assertEqual(e["presupuesto"]["diario_minor"], 7500)

    def test_pausa_presente_y_sin_pedidos_son_cero(self) -> None:
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-08", 7400))
        e = self.armar(raiz=self.raiz_con(pausa=True))
        self.assertTrue(e["contexto"]["pausa_activa"])
        self.assertEqual(e["contexto"]["pedidos_creativos_abiertos"], 0)

    def test_sin_raiz_todo_el_contexto_es_null_y_avisa(self) -> None:
        e = self.armar()
        self.assertEqual(set(e["contexto"].values()), {None})
        self.assertIsNone(e["presupuesto"])
        self.assertTrue(any("sin --raiz" in a for a in e["avisos"]))

    def test_sin_estado_de_infra_es_null_y_moneda_distinta_se_avisa(self) -> None:
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-08", 7400))
        raiz = self.raiz_con(infra=None)
        (raiz / "ofertas" / OFERTA / "07-campana" / "campana.json").write_text(
            json.dumps({"presupuesto": {"diario": 7500, "moneda": "EUR"}}), encoding="utf-8")
        e = self.armar(raiz=raiz)
        self.assertIsNone(e["contexto"]["infra_semaforo"])
        self.assertTrue(any(a.startswith("moneda_presupuesto_distinta") for a in e["avisos"]))


class PruebaConsola(Base):
    def test_cli_escribe_el_archivo_y_los_codigos_de_salida(self) -> None:
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-08", 7400))
        salida = self.dir / "entrada.json"
        codigo = E.main(["--db", str(self.db), "--oferta", OFERTA, "--fecha", "2026-11-08", "--ahora", "2026-11-09T09:00:00Z", "--salida", str(salida)])
        self.assertEqual(codigo, 0)
        doc = json.loads(salida.read_text(encoding="utf-8"))
        self.assertEqual((doc["tipo"], doc["oferta_id"]), ("entrada_d8", OFERTA))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(E.main(["--db", str(self.dir / "no.db"), "--oferta", OFERTA, "--fecha", "2026-11-08"]), 4)
            self.assertEqual(E.main(["--db", str(self.db), "--oferta", "malo", "--fecha", "2026-11-08"]), 3)
            self.assertEqual(E.main(["--oferta", OFERTA]), 2)

    def test_la_salida_es_estable(self) -> None:
        self.escribir(lambda c: meta(c, ADS[0], "2026-11-08", 7400))
        a, b = self.dir / "a.json", self.dir / "b.json"
        for destino in (a, b):
            E.main(["--db", str(self.db), "--oferta", OFERTA, "--fecha", "2026-11-08", "--ahora", "2026-11-09T09:00:00Z", "--salida", str(destino)])
        self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
