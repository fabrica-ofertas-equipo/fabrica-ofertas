"""Pruebas del lector de Meta en vivo (escalar-oferta/scripts/meta_vivo.py, 13-nov)."""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "escalar-oferta" / "scripts"))
import meta_vivo as V  # noqa: E402


class TestMetaVivo(unittest.TestCase):
    def test_fila_sin_doble_conteo(self) -> None:
        f = {"spend": "20", "impressions": "2000", "cpm": "10", "inline_link_clicks": "40",
             "actions": [{"action_type": "omni_purchase", "value": "2"}, {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "2"},
                         {"action_type": "landing_page_view", "value": "30"}, {"action_type": "omni_initiated_checkout", "value": "5"}],
             "action_values": [{"action_type": "omni_purchase", "value": "38"}, {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "38"}]}
        h = V.fila_insights(f)
        self.assertEqual((h["compras"], h["valor"], h["vistas"], h["checkouts"], h["roas_meta"]), (2, 38.0, 30, 5, 1.9))

    def test_leer_suma_por_oferta_y_solo_las_del_libro(self) -> None:
        camps = {"data": [{"id": "1", "effective_status": "ACTIVE", "daily_budget": "5000"}, {"id": "2", "effective_status": "PAUSED", "daily_budget": "3000"},
                          {"id": "9", "effective_status": "ACTIVE", "daily_budget": "9900"}]}
        ins = {"data": [{"campaign_id": "1", "spend": "30", "impressions": "3000", "actions": [{"action_type": "omni_purchase", "value": "1"}],
                         "action_values": [{"action_type": "omni_purchase", "value": "17"}]},
                        {"campaign_id": "2", "spend": "10", "impressions": "1000"}, {"campaign_id": "9", "spend": "99"}]}
        with mock.patch.object(V, "campanas_del_libro", return_value={"1": "X", "2": "X"}), mock.patch.object(V, "cuentas_del_libro", return_value=["111"]), \
             mock.patch.object(V, "pedir", side_effect=lambda ruta, p, t: camps if ruta.endswith("campaigns") else ins):
            r = V.leer("tok", dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc))
        x = r["ofertas"]["X"]
        self.assertEqual((x["hoy"]["gasto"], x["hoy"]["compras"], x["presupuesto"], x["hoy"]["cpa"]), (40.0, 1, 50.0, 40.0))
        self.assertEqual(r["total"]["gasto"], 40.0, "la campaña 9 no es del libro")


if __name__ == "__main__":
    unittest.main()
