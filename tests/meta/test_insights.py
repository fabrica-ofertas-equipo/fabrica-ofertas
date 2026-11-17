"""Pruebas de meta.insights: lectura para el ETL, sin efectos."""
import unittest

from engine.transporte import TransporteFixture
from meta import insights
from meta.cliente import ClienteMeta


class PruebaInsights(unittest.TestCase):
    def test_insights_anuncios_devuelve_la_lista_de_datos(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/123/insights",
             "cuerpo": {"data": [{"ad_id": "9", "spend": "12.50", "impressions": "100"}]}},
        ])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        datos = insights.insights_anuncios(cliente, "123", desde="2026-11-01", hasta="2026-11-07")
        self.assertEqual(datos, [{"ad_id": "9", "spend": "12.50", "impressions": "100"}])
        llamada = transporte.llamadas[0]
        self.assertIn("time_range=", llamada.url)
        self.assertIn("2026-11-01", llamada.url)
        self.assertIn("2026-11-07", llamada.url)

    def test_campos_por_defecto_cubren_lo_minimo_del_etl(self) -> None:
        for campo in ("ad_id", "spend", "impressions", "clicks", "date_start", "date_stop"):
            self.assertIn(campo, insights.CAMPOS_POR_DEFECTO)


if __name__ == "__main__":
    unittest.main()
