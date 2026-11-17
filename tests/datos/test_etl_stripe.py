"""Pruebas de `datos.etl_stripe`: deduplicación, pedidos/reembolsos/disputas y doble ETL idéntico."""
from __future__ import annotations

from datetime import datetime, timezone

from engine.errores import ErrorValidacion

from datos.etl_stripe import aplicar_evento, aplicar_lote, cargar_fixture
from tests.datos.apoyo import FIXTURES_DATOS, OFERTA, PruebaBase, reloj_fijo

AHORA = reloj_fijo(datetime(2026, 11, 13, 9, 0, 0, tzinfo=timezone.utc))
RUTA_FIXTURE = FIXTURES_DATOS / "stripe_eventos_OF-202611-01.json"


def _evento_checkout(event_id: str, session_id: str, *, adid: str = "120210000000103", monto: int = 1990,
                     verificacion: str | None = None, livemode: bool = True) -> dict:
    metadata = {"oferta_id": OFERTA, "adid": adid, "visitor_id": "v_" + "a" * 16, "consent_marketing": "1"}
    if verificacion:
        metadata["verificacion"] = verificacion
    return {"id": event_id, "type": "checkout.session.completed", "created": 1794394800,
           "data": {"object": {"id": session_id, "payment_intent": "pi_" + session_id, "amount_total": monto,
                               "currency": "eur", "livemode": livemode, "payment_status": "paid", "metadata": metadata}}}


class PruebaAplicarEventoCheckout(PruebaBase):
    def test_nuevo_pedido_se_inserta(self) -> None:
        conn = self.conexion()
        resultado = aplicar_evento(conn, _evento_checkout("evt_1", "cs_1"), ahora=AHORA)
        self.assertEqual(resultado, "nuevo")
        fila = conn.ejecutar("SELECT oferta_id, monto_minor, moneda, adid, es_prueba FROM fact_pedido").fetchone()
        self.assertEqual(fila["oferta_id"], OFERTA)
        self.assertEqual(fila["monto_minor"], 1990)
        self.assertEqual(fila["moneda"], "EUR")
        self.assertEqual(fila["adid"], "120210000000103")
        self.assertEqual(fila["es_prueba"], 0)

    def test_mismo_event_id_es_duplicado(self) -> None:
        conn = self.conexion()
        aplicar_evento(conn, _evento_checkout("evt_1", "cs_1"), ahora=AHORA)
        self.assertEqual(aplicar_evento(conn, _evento_checkout("evt_1", "cs_1"), ahora=AHORA), "duplicado")

    def test_event_id_distinto_mismo_objeto_tambien_es_duplicado(self) -> None:
        """Stripe puede emitir dos Event distintos para el mismo hecho (convenciones §7)."""
        conn = self.conexion()
        aplicar_evento(conn, _evento_checkout("evt_1", "cs_1"), ahora=AHORA)
        resultado = aplicar_evento(conn, _evento_checkout("evt_1_otro", "cs_1"), ahora=AHORA)
        self.assertEqual(resultado, "duplicado")
        self.assertEqual(conn.ejecutar("SELECT COUNT(*) FROM fact_pedido").fetchone()[0], 1)

    def test_adid_fuera_de_patron_queda_desconocido(self) -> None:
        conn = self.conexion()
        aplicar_evento(conn, _evento_checkout("evt_1", "cs_1", adid="no-es-un-id"), ahora=AHORA)
        self.assertEqual(conn.ejecutar("SELECT adid FROM fact_pedido").fetchone()[0], "desconocido")

    def test_verificacion_marca_es_prueba(self) -> None:
        conn = self.conexion()
        aplicar_evento(conn, _evento_checkout("evt_1", "cs_1", verificacion="1"), ahora=AHORA)
        self.assertEqual(conn.ejecutar("SELECT es_prueba FROM fact_pedido").fetchone()[0], 1)

    def test_oferta_id_invalida_es_error_de_validacion(self) -> None:
        conn = self.conexion()
        evento = _evento_checkout("evt_1", "cs_1")
        evento["data"]["object"]["metadata"]["oferta_id"] = "no-es-un-id-de-oferta"
        with self.assertRaises(ErrorValidacion):
            aplicar_evento(conn, evento, ahora=AHORA)

    def test_compras_internas_se_marcan_y_se_excluyen(self) -> None:
        conn = self.conexion()
        aplicar_evento(conn, _evento_checkout("evt_1", "cs_interna"), ahora=AHORA, compras_internas_ids=["cs_interna"])
        self.assertEqual(conn.ejecutar("SELECT es_interna FROM fact_pedido").fetchone()[0], 1)


class PruebaAplicarEventoReembolsoYDisputa(PruebaBase):
    def test_reembolso_resuelve_oferta_y_adid_por_payment_intent(self) -> None:
        conn = self.conexion()
        aplicar_evento(conn, _evento_checkout("evt_1", "cs_1"), ahora=AHORA)
        evento_reembolso = {
            "id": "evt_r1", "type": "charge.refunded", "created": 1794556800,
            "data": {"object": {"id": "ch_1", "payment_intent": "pi_cs_1", "currency": "eur", "amount_refunded": 1990,
                               "refunds": {"data": [{"id": "re_1", "amount": 1990, "status": "succeeded",
                                                     "reason": "requested_by_customer", "created": 1794556800}]}}},
        }
        self.assertEqual(aplicar_evento(conn, evento_reembolso, ahora=AHORA), "nuevo")
        fila = conn.ejecutar("SELECT oferta_id, checkout_session_id, adid, monto_minor, dia_utc FROM fact_reembolso").fetchone()
        self.assertEqual(fila["oferta_id"], OFERTA)
        self.assertEqual(fila["checkout_session_id"], "cs_1")
        self.assertEqual(fila["adid"], "120210000000103")
        self.assertEqual(fila["monto_minor"], 1990)
        self.assertEqual(fila["dia_utc"], "2026-11-13")

    def test_reembolso_sin_pedido_previo_ni_metadata_falla(self) -> None:
        conn = self.conexion()
        evento_reembolso = {
            "id": "evt_r1", "type": "charge.refunded", "created": 1794556800,
            "data": {"object": {"id": "ch_x", "payment_intent": "pi_desconocido", "currency": "eur", "amount_refunded": 1990,
                               "refunds": {"data": [{"id": "re_1", "amount": 1990, "status": "succeeded",
                                                     "reason": "requested_by_customer", "created": 1794556800}]}}},
        }
        with self.assertRaises(ErrorValidacion):
            aplicar_evento(conn, evento_reembolso, ahora=AHORA)

    def test_disputa_se_inserta(self) -> None:
        conn = self.conexion()
        aplicar_evento(conn, _evento_checkout("evt_1", "cs_1"), ahora=AHORA)
        evento_disputa = {
            "id": "evt_d1", "type": "charge.dispute.created", "created": 1794556860,
            "data": {"object": {"id": "dp_1", "charge": "ch_1", "payment_intent": "pi_cs_1", "amount": 1990,
                               "currency": "eur", "status": "warning_needs_response", "created": 1794556860}},
        }
        self.assertEqual(aplicar_evento(conn, evento_disputa, ahora=AHORA), "nuevo")
        fila = conn.ejecutar("SELECT oferta_id, checkout_session_id, estado FROM fact_disputa").fetchone()
        self.assertEqual(fila["oferta_id"], OFERTA)
        self.assertEqual(fila["checkout_session_id"], "cs_1")
        self.assertEqual(fila["estado"], "warning_needs_response")

    def test_tipo_no_soportado_es_error_de_validacion(self) -> None:
        conn = self.conexion()
        with self.assertRaises(ErrorValidacion):
            aplicar_evento(conn, {"id": "evt_x", "type": "invoice.paid", "data": {"object": {}}}, ahora=AHORA)


class PruebaFixtureReal(PruebaBase):
    def test_carga_y_aplica_el_lote_real_con_duplicado_prueba_reembolso_y_disputa(self) -> None:
        conn = self.conexion()
        documento = cargar_fixture(RUTA_FIXTURE)
        self.assertTrue(documento["sintetico"])
        conteo = aplicar_lote(conn, documento["eventos"], ahora=AHORA)
        self.assertEqual(conteo, {"nuevos": 6, "duplicados": 1})
        pedidos = conn.ejecutar("SELECT COUNT(*) FROM fact_pedido WHERE es_prueba = 0").fetchone()[0]
        self.assertEqual(pedidos, 3)
        pruebas = conn.ejecutar("SELECT COUNT(*) FROM fact_pedido WHERE es_prueba = 1").fetchone()[0]
        self.assertEqual(pruebas, 1)
        self.assertEqual(conn.ejecutar("SELECT COUNT(*) FROM fact_reembolso").fetchone()[0], 1)
        self.assertEqual(conn.ejecutar("SELECT COUNT(*) FROM fact_disputa").fetchone()[0], 1)

    def test_doble_etl_deja_las_tablas_identicas(self) -> None:
        """Criterio B0-15: aplicar el mismo lote dos veces no cambia el resultado (solo cuentan duplicados)."""
        conn = self.conexion()
        documento = cargar_fixture(RUTA_FIXTURE)
        aplicar_lote(conn, documento["eventos"], ahora=AHORA)
        primero = {
            "pedidos": [dict(f) for f in conn.ejecutar("SELECT * FROM fact_pedido ORDER BY checkout_session_id").fetchall()],
            "reembolsos": [dict(f) for f in conn.ejecutar("SELECT * FROM fact_reembolso ORDER BY stripe_refund_id").fetchall()],
            "disputas": [dict(f) for f in conn.ejecutar("SELECT * FROM fact_disputa ORDER BY dispute_id").fetchall()],
        }
        conteo = aplicar_lote(conn, documento["eventos"], ahora=AHORA)
        self.assertEqual(conteo, {"nuevos": 0, "duplicados": 7})
        segundo = {
            "pedidos": [dict(f) for f in conn.ejecutar("SELECT * FROM fact_pedido ORDER BY checkout_session_id").fetchall()],
            "reembolsos": [dict(f) for f in conn.ejecutar("SELECT * FROM fact_reembolso ORDER BY stripe_refund_id").fetchall()],
            "disputas": [dict(f) for f in conn.ejecutar("SELECT * FROM fact_disputa ORDER BY dispute_id").fetchall()],
        }
        self.assertEqual(primero, segundo)
