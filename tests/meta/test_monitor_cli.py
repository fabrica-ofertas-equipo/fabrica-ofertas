"""CLI de meta.monitor (A3, ola 2 B5b): dry-run y --modo fixture sobre TransporteFixture."""
from __future__ import annotations

import contextlib
import io
import json
import unittest

from engine.transporte import TransporteFixture
from meta import monitor
from tests.engine.apoyo import OFERTA, PruebaBase, crear_empresa

_CAMPAIGN_ID, _AD_OK, _AD_MALO = "1111111111", "2222222222", "3333333333"


def _ids_meta() -> dict:
    return {"campaign_id": _CAMPAIGN_ID, "adset_ids": ["4444444444"], "ad_ids": [_AD_OK, _AD_MALO]}


def _regla(metodo: str, object_id: str, cuerpo: dict) -> dict:
    return {"metodo": metodo, "url_prefijo": f"https://graph.facebook.com/v21.0/{object_id}", "cuerpo": cuerpo}


class PruebaCliMonitor(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        self.ids_meta_ruta = self.tmp / "ids_meta.json"
        self.ids_meta_ruta.write_text(json.dumps(_ids_meta()), encoding="utf-8")

    def _correr(self, argv: list[str]) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = monitor.main(argv)
        return codigo, salida.getvalue()

    def test_dry_run_no_llama_a_meta(self) -> None:
        codigo, salida = self._correr([
            "--oferta", OFERTA, "--ids-meta", str(self.ids_meta_ruta), "--ventana-h", "24",
            "--gasto-real", "1000", "--gasto-esperado", "1200", "--moneda", "EUR",
            "--estado-aprendizaje", "LEARNING", "--clics-enlace", "100", "--vistas-landing", "90", "--json",
        ])
        self.assertEqual(codigo, 0, salida)
        datos = json.loads(salida)
        self.assertEqual(datos["modo"], "dry_run")
        self.assertEqual(sorted(datos["datos"]["object_ids"]), sorted([_CAMPAIGN_ID, _AD_OK, _AD_MALO]))

    def test_modo_fixture_pausa_el_disapproved(self) -> None:
        reglas = [
            _regla("GET", _CAMPAIGN_ID, {"id": _CAMPAIGN_ID, "effective_status": "ACTIVE"}),
            _regla("GET", _AD_OK, {"id": _AD_OK, "effective_status": "ACTIVE"}),
            _regla("GET", _AD_MALO, {"id": _AD_MALO, "effective_status": "DISAPPROVED"}),
            _regla("POST", _AD_MALO, {"success": True}),
        ]
        fixture_ruta = self.tmp / "reglas.json"
        fixture_ruta.write_text(json.dumps(reglas), encoding="utf-8")
        codigo, salida = self._correr([
            "--oferta", OFERTA, "--ids-meta", str(self.ids_meta_ruta), "--ventana-h", "24",
            "--gasto-real", "1000", "--gasto-esperado", "1200", "--moneda", "EUR",
            "--estado-aprendizaje", "LEARNING", "--clics-enlace", "100", "--vistas-landing", "90",
            "--modo", "fixture", "--fixture", str(fixture_ruta), "--raiz", str(self.emp.raiz),
            "--ahora", "2026-11-10T12:00:00Z", "--json",
        ])
        self.assertEqual(codigo, 0, salida)
        datos = json.loads(salida)["datos"]
        self.assertEqual(datos["pausados"], [_AD_MALO])
        self.assertEqual(datos["rechazos_7d"], 1)
        self.assertFalse(datos["congelar"])

    def test_ventana_invalida_sale_2_por_uso_de_argparse(self) -> None:
        codigo, _ = self._correr([
            "--oferta", OFERTA, "--ids-meta", str(self.ids_meta_ruta), "--ventana-h", "3",
            "--gasto-real", "1000", "--gasto-esperado", "1200", "--moneda", "EUR",
            "--estado-aprendizaje", "LEARNING", "--clics-enlace", "100", "--vistas-landing", "90",
        ])
        self.assertEqual(codigo, 2)

    def test_modo_live_se_rechaza(self) -> None:
        codigo, _ = self._correr([
            "--oferta", OFERTA, "--ids-meta", str(self.ids_meta_ruta), "--ventana-h", "24",
            "--gasto-real", "1000", "--gasto-esperado", "1200", "--moneda", "EUR",
            "--estado-aprendizaje", "LEARNING", "--clics-enlace", "100", "--vistas-landing", "90",
            "--modo", "live",
        ])
        self.assertEqual(codigo, 4)


if __name__ == "__main__":
    unittest.main()
