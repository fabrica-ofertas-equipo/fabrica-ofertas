"""Pruebas de `datos.ledger`: líneas, escritura idempotente y conciliación triple."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine import comun
from engine.errores import ErrorValidacion

from datos import ledger
from datos.etl_meta import aplicar_fila
from datos.etl_stripe import aplicar_evento
from tests.datos.apoyo import OFERTA, PruebaBase, reloj_fijo

AHORA = reloj_fijo(datetime(2026, 11, 13, 9, 0, 0, tzinfo=timezone.utc))


def _pedido(conn, session_id: str, *, adid: str = "120210000000101", monto: int = 1990, created: int = 1794394800) -> None:
    evento = {"id": f"evt_{session_id}", "type": "checkout.session.completed", "created": created,
             "data": {"object": {"id": session_id, "payment_intent": f"pi_{session_id}", "amount_total": monto,
                                 "currency": "eur", "livemode": True, "payment_status": "paid",
                                 "metadata": {"oferta_id": OFERTA, "adid": adid, "visitor_id": "v" * 16, "consent_marketing": "1"}}}}
    aplicar_evento(conn, evento, ahora=AHORA)


def _insight(conn, ad_id: str = "120210000000101", fecha: str = "2026-11-11", spend: str = "19.90") -> None:
    aplicar_fila(conn, OFERTA, {"ad_id": ad_id, "adset_id": "as_1", "campaign_id": "c_1", "date_start": fecha,
                               "spend": spend, "impressions": "1000", "clicks": "20", "inline_link_clicks": "15"},
                tz="Europe/Madrid", moneda="EUR", ahora=AHORA)


class PruebaGenerarLineas(PruebaBase):
    def test_pedido_y_gasto_generan_lineas_validas(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1")
        _insight(conn)
        lineas = ledger.generar_lineas(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11")
        tipos = sorted(l["tipo"] for l in lineas)
        self.assertEqual(tipos, ["gasto", "pedido"])

    def test_incluye_costos_de_la_oferta(self) -> None:
        conn = self.conexion()
        ruta_costos = self.tmp / "empresa" / "costos.jsonl"
        comun.anexar_jsonl(ruta_costos, {
            "schema_version": "1.0.0", "ts": "2026-11-11T10:00:00Z", "oferta_id": OFERTA, "etapa": "D3",
            "ejecucion_id": "run-0001", "origen": "ia", "concepto": "redaccion",
            "monto": {"monto": 500, "moneda": "USD"},
        })
        lineas = ledger.generar_lineas(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11")
        costos = [l for l in lineas if l["tipo"] == "costo"]
        self.assertEqual(len(costos), 1)
        self.assertEqual(costos[0]["importe"], {"monto": 500, "moneda": "USD"})


class PruebaEscribirLedger(PruebaBase):
    def test_reescribir_las_mismas_lineas_no_agrega_nada(self) -> None:
        ruta = self.tmp / "ledger.jsonl"
        linea = {"schema_version": "1.0.0", "clave_natural": "stripe:cs_1", "tipo": "pedido", "oferta_id": OFERTA,
                 "fecha": "2026-11-11", "ts": "2026-11-11T11:00:00Z", "sentido": "entrada",
                 "importe": {"monto": 1990, "moneda": "EUR"}, "fuente": "stripe", "es_prueba": False, "adid": "120210000000101"}
        primero = ledger.escribir_ledger(ruta, [linea])
        self.assertEqual(primero, {"nuevas": 1, "sin_cambios": 0})
        segundo = ledger.escribir_ledger(ruta, [linea])
        self.assertEqual(segundo, {"nuevas": 0, "sin_cambios": 1})
        self.assertEqual(len(comun.leer_jsonl(ruta)), 1)

    def test_una_linea_con_el_mismo_clave_natural_pero_distinto_contenido_agrega_una_version_nueva(self) -> None:
        ruta = self.tmp / "ledger.jsonl"
        base = {"schema_version": "1.0.0", "clave_natural": "stripe:cs_1", "tipo": "pedido", "oferta_id": OFERTA,
               "fecha": "2026-11-11", "ts": "2026-11-11T11:00:00Z", "sentido": "entrada",
               "importe": {"monto": 1990, "moneda": "EUR"}, "fuente": "stripe", "es_prueba": False, "adid": "desconocido"}
        ledger.escribir_ledger(ruta, [base])
        corregida = {**base, "adid": "120210000000101"}
        resumen = ledger.escribir_ledger(ruta, [corregida])
        self.assertEqual(resumen, {"nuevas": 1, "sin_cambios": 0})
        lineas = comun.leer_jsonl(ruta)
        self.assertEqual(len(lineas), 2)
        self.assertEqual(ledger.leer_vigente(ruta)["stripe:cs_1"]["adid"], "120210000000101")


class PruebaConciliar(PruebaBase):
    def test_sin_datos_es_incompleto(self) -> None:
        conn = self.conexion()
        resultado = ledger.conciliar(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11", "EUR", ahora=AHORA)
        self.assertEqual(resultado["estado"], "INCOMPLETO")
        self.assertTrue(resultado["cifras_tachadas"])

    def test_ledger_al_dia_concilia_en_cero(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1")
        _insight(conn)
        lineas = ledger.generar_lineas(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11")
        ledger.escribir_ledger(ledger.ruta_ledger(self.tmp), lineas)
        resultado = ledger.conciliar(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11", "EUR", ahora=AHORA)
        self.assertEqual(resultado["estado"], "CONCILIADO")
        self.assertEqual(resultado["stripe_vs_ledger"]["diferencia"]["monto"], 0)
        self.assertEqual(resultado["gasto_meta_vs_ledger"]["diferencia"]["monto"], 0)
        self.assertFalse(resultado["cifras_tachadas"])

    def test_un_pedido_sin_volcar_al_ledger_da_descuadre(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1")
        _insight(conn)
        resultado = ledger.conciliar(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11", "EUR", ahora=AHORA)
        self.assertEqual(resultado["estado"], "DESCUADRE")
        self.assertEqual(resultado["stripe_vs_ledger"]["diferencia"]["monto"], 1990)
        self.assertTrue(resultado["cifras_tachadas"])

    def test_moneda_distinta_en_el_ledger_falla_cerrado(self) -> None:
        ruta = ledger.ruta_ledger(self.tmp)
        comun.anexar_jsonl(ruta, {"schema_version": "1.0.0", "clave_natural": "stripe:cs_1", "tipo": "pedido",
                                  "oferta_id": OFERTA, "fecha": "2026-11-11", "ts": "2026-11-11T11:00:00Z",
                                  "sentido": "entrada", "importe": {"monto": 1990, "moneda": "USD"},
                                  "fuente": "stripe", "es_prueba": False, "adid": "desconocido"})
        conn = self.conexion()
        with self.assertRaises(ErrorValidacion):
            ledger.conciliar(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11", "EUR", ahora=AHORA)

    def test_conciliacion_cumple_su_esquema(self) -> None:
        from scripts.validar_esquemas import errores_de_esquema
        conn = self.conexion()
        _pedido(conn, "cs_1")
        _insight(conn)
        resultado = ledger.conciliar(conn, self.tmp, OFERTA, "2026-11-11", "2026-11-11", "EUR", ahora=AHORA)
        self.assertEqual(errores_de_esquema("conciliacion", resultado), [])
