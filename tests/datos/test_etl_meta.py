"""Pruebas de `datos.etl_meta`: conversión de unidad estándar a unidad menor y upsert por (ad_id, fecha)."""
from __future__ import annotations

from datetime import datetime, timezone

from engine.errores import ErrorValidacion

from datos.etl_meta import aplicar_fila, aplicar_insights, cargar_fixture
from tests.datos.apoyo import FIXTURES_DATOS, OFERTA, PruebaBase, reloj_fijo

AHORA = reloj_fijo(datetime(2026, 11, 13, 9, 0, 0, tzinfo=timezone.utc))
RUTA_FIXTURE = FIXTURES_DATOS / "meta_insights_OF-202611-01.json"


class PruebaAplicarFila(PruebaBase):
    def test_convierte_el_gasto_de_unidad_estandar_a_unidad_menor(self) -> None:
        conn = self.conexion()
        aplicar_fila(conn, OFERTA, {
            "ad_id": "120210000000101", "adset_id": "120210000000011", "campaign_id": "120210000000001",
            "date_start": "2026-11-10", "spend": "5.90", "impressions": "1300", "clicks": "32", "inline_link_clicks": "21",
        }, tz="Europe/Madrid", moneda="EUR", ahora=AHORA)
        conn.commit()
        fila = conn.ejecutar("SELECT gasto_minor, moneda, tz, compras_meta FROM fact_meta_ad_dia").fetchone()
        self.assertEqual(fila["gasto_minor"], 590)
        self.assertEqual(fila["moneda"], "EUR")
        self.assertEqual(fila["tz"], "Europe/Madrid")
        self.assertEqual(fila["compras_meta"], 0)

    def test_suma_las_acciones_de_compra(self) -> None:
        conn = self.conexion()
        aplicar_fila(conn, OFERTA, {
            "ad_id": "120210000000103", "adset_id": "120210000000011", "campaign_id": "120210000000001",
            "date_start": "2026-11-11", "spend": "5.65", "impressions": "1250", "clicks": "30", "inline_link_clicks": "20",
            "actions": [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "1"}],
        }, tz="Europe/Madrid", moneda="EUR", ahora=AHORA)
        conn.commit()
        self.assertEqual(conn.ejecutar("SELECT compras_meta FROM fact_meta_ad_dia").fetchone()[0], 1)

    def test_upsert_por_ad_id_y_fecha_no_duplica(self) -> None:
        conn = self.conexion()
        fila = {"ad_id": "120210000000101", "adset_id": "120210000000011", "campaign_id": "120210000000001",
               "date_start": "2026-11-10", "spend": "2.00", "impressions": "100", "clicks": "1", "inline_link_clicks": "1"}
        aplicar_fila(conn, OFERTA, fila, tz="Europe/Madrid", moneda="EUR", ahora=AHORA)
        aplicar_fila(conn, OFERTA, {**fila, "spend": "3.00", "impressions": "200"}, tz="Europe/Madrid", moneda="EUR", ahora=AHORA)
        conn.commit()
        filas = conn.ejecutar("SELECT gasto_minor, impresiones FROM fact_meta_ad_dia").fetchall()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["gasto_minor"], 300)

    def test_moneda_sin_exponente_conocido_falla_cerrado(self) -> None:
        conn = self.conexion()
        with self.assertRaises(ErrorValidacion):
            aplicar_fila(conn, OFERTA, {
                "ad_id": "1", "adset_id": "1", "campaign_id": "1", "date_start": "2026-11-10",
                "spend": "1.00", "impressions": "1", "clicks": "1", "inline_link_clicks": "1",
            }, tz="UTC", moneda="ZZZ", ahora=AHORA)

    def test_fila_incompleta_es_error_de_validacion(self) -> None:
        conn = self.conexion()
        with self.assertRaises(ErrorValidacion):
            aplicar_fila(conn, OFERTA, {"ad_id": "1"}, tz="UTC", moneda="EUR", ahora=AHORA)


class PruebaAplicarInsightsYFixture(PruebaBase):
    def test_carga_la_fixture_real_y_aplica_solo_el_rango_pedido(self) -> None:
        conn = self.conexion()
        documento = cargar_fixture(RUTA_FIXTURE)
        self.assertTrue(documento["sintetico"])
        n = aplicar_insights(conn, OFERTA, documento, desde="2026-11-11", hasta="2026-11-11", ahora=AHORA)
        conn.commit()
        self.assertEqual(n, 5)
        total = conn.ejecutar("SELECT COALESCE(SUM(gasto_minor),0), COALESCE(SUM(impresiones),0), COALESCE(SUM(clics_enlace),0) "
                              "FROM fact_meta_ad_dia WHERE fecha = '2026-11-11'").fetchone()
        self.assertEqual(total[0], 2760)  # coincide con ofertas/_ejemplo 2026-11-11
        self.assertEqual(total[1], 6133)
        self.assertEqual(total[2], 98)

    def test_doble_etl_deja_las_tablas_identicas(self) -> None:
        """Criterio B0-15: aplicar el mismo documento dos veces no cambia el resultado."""
        conn = self.conexion()
        documento = cargar_fixture(RUTA_FIXTURE)
        aplicar_insights(conn, OFERTA, documento, desde="2026-11-10", hasta="2026-11-12", ahora=AHORA)
        conn.commit()
        primero = [dict(f) for f in conn.ejecutar("SELECT * FROM fact_meta_ad_dia ORDER BY ad_id, fecha").fetchall()]
        aplicar_insights(conn, OFERTA, documento, desde="2026-11-10", hasta="2026-11-12", ahora=AHORA)
        conn.commit()
        segundo = [dict(f) for f in conn.ejecutar("SELECT * FROM fact_meta_ad_dia ORDER BY ad_id, fecha").fetchall()]
        self.assertEqual(primero, segundo)
        self.assertEqual(len(primero), 15)
