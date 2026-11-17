"""Pruebas de meta.lectura_viva (A13): genera el estado vivo de la campaña para el QA de D7, sin
que ningún Maker lo escriba (solo lectura contra ClienteMeta/TransporteFixture)."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from datetime import datetime, timezone

from engine.transporte import TransporteFixture
from meta import lectura_viva
from meta.cliente import ClienteMeta
from tests.engine.apoyo import OFERTA, PruebaBase, crear_empresa

_CAMPAIGN_ID, _ADSET_ID, _AD_ID = "1111111111", "2222222222", "3333333333"


def _ids_meta() -> dict:
    return {"campaign_id": _CAMPAIGN_ID, "adset_ids": [_ADSET_ID], "ad_ids": [_AD_ID], "creative_ids": ["4444444444"]}


def _regla(metodo: str, object_id: str, cuerpo: dict) -> dict:
    return {"metodo": metodo, "url_prefijo": f"https://graph.facebook.com/v21.0/{object_id}", "cuerpo": cuerpo}


def _reglas() -> list[dict]:
    return [
        _regla("GET", _CAMPAIGN_ID, {"id": _CAMPAIGN_ID, "spend_cap": 5500, "special_ad_categories": []}),
        _regla("GET", _ADSET_ID, {"id": _ADSET_ID, "daily_budget": 500, "optimization_goal": "OFFSITE_CONVERSIONS"}),
        _regla("GET", _AD_ID, {"id": _AD_ID, "creative": {"id": "4444444444"}}),
    ]


def _ahora() -> datetime:
    return datetime(2026, 11, 10, 8, 0, 0, tzinfo=timezone.utc)


class PruebaGenerar(unittest.TestCase):
    def test_lee_campana_conjunto_y_anuncios_sin_escribir_nada(self) -> None:
        transporte = TransporteFixture(_reglas())
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        datos = lectura_viva.generar(oferta_id=OFERTA, cliente=cliente, ids_meta=_ids_meta(), hash_config="sha256:" + "a" * 64, ahora=_ahora)
        self.assertEqual(datos["oferta_id"], OFERTA)
        self.assertEqual(datos["campana"]["spend_cap"], 5500)
        self.assertEqual(datos["conjunto"]["daily_budget"], 500)
        self.assertEqual(datos["anuncios"][0]["creative"]["id"], "4444444444")
        self.assertEqual(datos["leido_en"], "2026-11-10T08:00:00Z")
        self.assertNotIn("creativos", datos)  # incluir_creativo=False por defecto
        self.assertEqual(len(transporte.llamadas_a("POST")), 0)  # nunca escribe en Meta


class PruebaCli(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        self.ids_meta_ruta = self.tmp / "ids_meta.json"
        self.ids_meta_ruta.write_text(json.dumps(_ids_meta()), encoding="utf-8")

    def _correr(self, argv: list[str]) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = lectura_viva.main(argv)
        return codigo, salida.getvalue()

    def test_dry_run_no_llama_a_meta(self) -> None:
        codigo, salida = self._correr([
            "--oferta", OFERTA, "--ids-meta", str(self.ids_meta_ruta), "--hash-config", "sha256:" + "a" * 64, "--json",
        ])
        self.assertEqual(codigo, 0, salida)
        self.assertEqual(json.loads(salida)["modo"], "dry_run")

    def test_modo_fixture_escribe_la_salida(self) -> None:
        fixture_ruta = self.tmp / "reglas.json"
        fixture_ruta.write_text(json.dumps(_reglas()), encoding="utf-8")
        destino = self.tmp / "lectura_viva.json"
        codigo, _ = self._correr([
            "--oferta", OFERTA, "--ids-meta", str(self.ids_meta_ruta), "--hash-config", "sha256:" + "a" * 64,
            "--modo", "fixture", "--fixture", str(fixture_ruta), "--raiz", str(self.emp.raiz),
            "--ahora", "2026-11-10T08:00:00Z", "--salida", str(destino),
        ])
        self.assertEqual(codigo, 0)
        self.assertTrue(destino.is_file())
        self.assertEqual(json.loads(destino.read_text(encoding="utf-8"))["campana"]["spend_cap"], 5500)


if __name__ == "__main__":
    unittest.main()
