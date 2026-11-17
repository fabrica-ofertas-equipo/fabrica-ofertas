"""Pruebas de `datos.atribucion`: cobertura de `adid`, razón Meta/Stripe, evidencia y cohortes."""
from __future__ import annotations

from datos import atribucion
from datos.etl_meta import aplicar_fila
from datos.etl_stripe import aplicar_evento
from tests.datos.apoyo import OFERTA, PruebaBase, reloj_fijo
from datetime import datetime, timezone

AHORA = reloj_fijo(datetime(2026, 11, 13, 9, 0, 0, tzinfo=timezone.utc))


def _pedido(conn, session_id: str, *, adid: str, monto: int = 1990, created: int = 1794394800, prueba: bool = False) -> None:
    metadata = {"oferta_id": OFERTA, "visitor_id": "v" * 16, "consent_marketing": "1"}
    if adid is not None:
        metadata["adid"] = adid
    if prueba:
        metadata["verificacion"] = "1"
    evento = {"id": f"evt_{session_id}", "type": "checkout.session.completed", "created": created,
             "data": {"object": {"id": session_id, "payment_intent": f"pi_{session_id}", "amount_total": monto,
                                 "currency": "eur", "livemode": not prueba, "payment_status": "paid", "metadata": metadata}}}
    aplicar_evento(conn, evento, ahora=AHORA)


def _insight(conn, ad_id: str, fecha: str, *, compras: int = 0) -> None:
    fila = {"ad_id": ad_id, "adset_id": "as_1", "campaign_id": "c_1", "date_start": fecha,
           "spend": "10.00", "impressions": "1000", "clicks": "20", "inline_link_clicks": "15"}
    if compras:
        fila["actions"] = [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": str(compras)}]
    aplicar_fila(conn, OFERTA, fila, tz="Europe/Madrid", moneda="EUR", ahora=AHORA)


class PruebaCoberturaAdid(PruebaBase):
    def test_sin_pedidos_la_cobertura_es_cero(self) -> None:
        conn = self.conexion()
        self.assertEqual(atribucion.cobertura_adid(conn, OFERTA, "2026-11-01", "2026-11-30"), 0)

    def test_todos_con_adid_conocido_es_10000_bp(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101")
        _pedido(conn, "cs_2", adid="120210000000102")
        self.assertEqual(atribucion.cobertura_adid(conn, OFERTA, "2026-11-11", "2026-11-11"), 10000)

    def test_mitad_desconocido_es_5000_bp(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101")
        _pedido(conn, "cs_2", adid="no-valido")
        self.assertEqual(atribucion.cobertura_adid(conn, OFERTA, "2026-11-11", "2026-11-11"), 5000)

    def test_pruebas_e_internas_no_cuentan(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101")
        _pedido(conn, "cs_prueba", adid=None, prueba=True)
        self.assertEqual(atribucion.cobertura_adid(conn, OFERTA, "2026-11-11", "2026-11-11"), 10000)


class PruebaRazonMetaStripe(PruebaBase):
    def test_sin_compras_de_stripe_es_none(self) -> None:
        conn = self.conexion()
        self.assertIsNone(atribucion.razon_meta_stripe(conn, OFERTA, "2026-11-11", "2026-11-11"))

    def test_razon_exacta_uno_a_uno(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101")
        _insight(conn, "120210000000101", "2026-11-11", compras=1)
        self.assertEqual(atribucion.razon_meta_stripe(conn, OFERTA, "2026-11-11", "2026-11-11"), "1.00")

    def test_meta_reporta_el_doble_que_stripe(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101")
        _insight(conn, "120210000000101", "2026-11-11", compras=2)
        self.assertEqual(atribucion.razon_meta_stripe(conn, OFERTA, "2026-11-11", "2026-11-11"), "2.00")


class PruebaEvidenciaCeldaYCohorte(PruebaBase):
    def test_evidencia_celda_agrega_meta_y_stripe(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101", monto=1990)
        _insight(conn, "120210000000101", "2026-11-11", compras=1)
        evidencia = atribucion.evidencia_celda(conn, OFERTA, "2026-11-11", "2026-11-11")
        self.assertEqual(evidencia.compras_atribuidas, 1)
        self.assertEqual(evidencia.gasto_meta_minor, 1000)
        self.assertEqual(evidencia.moneda_gasto, "EUR")
        self.assertEqual(evidencia.compras_meta, 1)
        self.assertEqual(evidencia.cobertura_adid_bp, 10000)
        self.assertEqual(evidencia.razon_meta_stripe, "1.00")

    def test_pedidos_cohorte_incluye_lo_reembolsado(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101", monto=1990)
        evento_reembolso = {
            "id": "evt_r1", "type": "charge.refunded", "created": 1794556800,
            "data": {"object": {"id": "ch_1", "payment_intent": "pi_cs_1", "currency": "eur", "amount_refunded": 1990,
                               "refunds": {"data": [{"id": "re_1", "amount": 500, "status": "succeeded",
                                                     "reason": "requested_by_customer", "created": 1794556800}]}}},
        }
        aplicar_evento(conn, evento_reembolso, ahora=AHORA)
        cohorte = atribucion.pedidos_cohorte(conn, OFERTA, "2026-11-30")
        self.assertEqual(len(cohorte), 1)
        self.assertEqual(cohorte[0].monto_minor, 1990)
        self.assertEqual(cohorte[0].reembolsado_minor, 500)

    def test_pedidos_cohorte_excluye_fecha_posterior_al_corte(self) -> None:
        conn = self.conexion()
        _pedido(conn, "cs_1", adid="120210000000101", created=1794556800)  # 2026-11-13
        self.assertEqual(atribucion.pedidos_cohorte(conn, OFERTA, "2026-11-11"), [])
