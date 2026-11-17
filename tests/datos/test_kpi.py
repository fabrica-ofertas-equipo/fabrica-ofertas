"""Pruebas de `datos.kpi`: snapshot diario, frescura de fuentes y conformidad con el esquema."""
from __future__ import annotations

from datetime import datetime, timezone

from engine.parametros import Parametros
from scripts.validar_esquemas import errores_de_esquema

from datos.kpi import calcular_kpi
from datos.etl_meta import aplicar_fila
from datos.etl_stripe import aplicar_evento
from tests.datos.apoyo import OFERTA, PruebaBase, reloj_fijo

PARAMETROS = Parametros({"grupos": {"dashboard": {
    "frescura_meta_amarillo_h": {"valor": 6, "unidad": "horas", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
    "frescura_meta_rojo_h": {"valor": 12, "unidad": "horas", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
    "frescura_stripe_eventos_amarillo_h": {"valor": 2, "unidad": "horas", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
    "frescura_stripe_eventos_rojo_h": {"valor": 6, "unidad": "horas", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
    "pedidos_min_verde": {"valor": 1, "unidad": "pedidos", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
}}})


def _pedido(conn, session_id: str, *, ahora, created: int = 1794394800) -> None:
    evento = {"id": f"evt_{session_id}", "type": "checkout.session.completed", "created": created,
             "data": {"object": {"id": session_id, "payment_intent": f"pi_{session_id}", "amount_total": 1990,
                                 "currency": "eur", "livemode": True, "payment_status": "paid",
                                 "metadata": {"oferta_id": OFERTA, "adid": "120210000000101", "visitor_id": "v" * 16,
                                             "consent_marketing": "1"}}}}
    aplicar_evento(conn, evento, ahora=ahora)


class PruebaCalcularKpi(PruebaBase):
    def test_sin_datos_todo_queda_gris_y_rojo(self) -> None:
        conn = self.conexion()
        ahora = reloj_fijo(datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc))
        kpi = calcular_kpi(conn, OFERTA, "2026-11-11", ahora=ahora, parametros=PARAMETROS, run_id="RUN-TEST-01")
        self.assertEqual(kpi["fuentes"]["meta"], {"frescura_h": None, "estado": "rojo"})
        self.assertEqual(kpi["fuentes"]["stripe_balance"], {"frescura_h": None, "estado": "rojo"})
        por_id = {f["kpi_id"]: f for f in kpi["filas"]}
        self.assertEqual(por_id["compras_stripe"]["estado"], "gris")
        self.assertIsNone(por_id["razon_meta_stripe"]["valor"])

    def test_con_gasto_y_una_compra_fresca_queda_verde(self) -> None:
        conn = self.conexion()
        ahora_ingesta = reloj_fijo(datetime(2026, 11, 11, 11, 30, 0, tzinfo=timezone.utc))
        aplicar_fila(conn, OFERTA, {"ad_id": "120210000000101", "adset_id": "as_1", "campaign_id": "c_1",
                                   "date_start": "2026-11-11", "spend": "27.60", "impressions": "6133",
                                   "clicks": "100", "inline_link_clicks": "98",
                                   "actions": [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "1"}]},
                    tz="Europe/Madrid", moneda="EUR", ahora=ahora_ingesta)
        _pedido(conn, "cs_1", ahora=ahora_ingesta)
        ahora_lectura = reloj_fijo(datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc))  # 30 min después
        kpi = calcular_kpi(conn, OFERTA, "2026-11-11", ahora=ahora_lectura, parametros=PARAMETROS, run_id="RUN-TEST-02")
        self.assertEqual(kpi["fuentes"]["meta"]["estado"], "verde")
        self.assertEqual(kpi["fuentes"]["stripe_eventos"]["estado"], "verde")
        por_id = {f["kpi_id"]: f for f in kpi["filas"]}
        self.assertEqual(por_id["gasto_meta"], {"kpi_id": "gasto_meta", "valor": 2760, "unidad": "EUR_minor",
                                                "n": 1, "estado": "ok", "rango": None, "ventana": "24h"})
        self.assertEqual(por_id["impresiones"]["valor"], 6133)
        self.assertEqual(por_id["clics_enlace"]["valor"], 98)
        self.assertEqual(por_id["compras_stripe"]["valor"], 1)
        self.assertEqual(por_id["compras_stripe"]["estado"], "ok")
        self.assertEqual(por_id["cpa"]["valor"], 2760)
        self.assertEqual(por_id["razon_meta_stripe"]["valor"], "1.00")

    def test_cumple_su_esquema(self) -> None:
        conn = self.conexion()
        ahora = reloj_fijo(datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc))
        kpi = calcular_kpi(conn, OFERTA, "2026-11-11", ahora=ahora, parametros=PARAMETROS, run_id="RUN-TEST-03")
        self.assertEqual(errores_de_esquema("kpi", kpi), [])

    def test_sin_parametros_de_dashboard_la_frescura_queda_rojo_sin_lanzar(self) -> None:
        from engine.parametros import Parametros as P
        conn = self.conexion()
        ahora = reloj_fijo(datetime(2026, 11, 11, 11, 30, 0, tzinfo=timezone.utc))
        aplicar_fila(conn, OFERTA, {"ad_id": "120210000000101", "adset_id": "as_1", "campaign_id": "c_1",
                                   "date_start": "2026-11-11", "spend": "1.00", "impressions": "10",
                                   "clicks": "1", "inline_link_clicks": "1"}, tz="Europe/Madrid", moneda="EUR", ahora=ahora)
        kpi = calcular_kpi(conn, OFERTA, "2026-11-11", ahora=ahora, parametros=P({"grupos": {}}), run_id="RUN-TEST-04")
        self.assertEqual(kpi["fuentes"]["meta"]["estado"], "rojo")
