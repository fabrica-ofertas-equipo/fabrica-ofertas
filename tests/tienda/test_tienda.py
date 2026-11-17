"""Capa de tienda: los adaptadores cumplen el contrato y la fábrica los usa (dueño, 17-nov: código abierto, cada uno con su tienda)."""
from __future__ import annotations

import os
import unittest

import tienda
from tienda import conformidad


class TestTienda(unittest.TestCase):
    def test_por_defecto_es_impultienda(self) -> None:
        self.assertEqual(tienda.activa().nombre if not os.environ.get("FABRICA_TIENDA") else "impultienda", "impultienda")

    def test_conformidad_de_todos_los_adaptadores(self) -> None:
        for n in ("impultienda", "propia"):
            self.assertEqual(conformidad.revisar(n), [], n)

    def test_impultienda_direcciones(self) -> None:
        t = tienda.cargar("impultienda")
        self.assertEqual(t.url_landing("x", "?v=ficha"), "https://x.impultienda.ar/?v=ficha")
        self.assertEqual(t.tienda_de_url("https://x.impultienda.ar/?utm_source=fb"), "x")
        self.assertIsNone(t.tienda_de_url("https://sb.impultienda.ar/rest/v1/visits"))
        self.assertIsNone(t.tienda_de_url("https://otra.com/x"))
        self.assertIn("preview_country=FR", t.url_checkout("x", "id1", "FR", vista_previa=True))

    def test_ventas_numero_de_orden_entero(self) -> None:
        v = tienda.cargar("impultienda").ventas({"detalle": {"ventas": [{"orden": 5, "fecha": "2026-11-17", "total": "19", "moneda": "usd"}]}})
        self.assertEqual(v[0]["orden"], "5")
        self.assertEqual(v[0]["moneda"], "USD")

    def test_plantilla_no_pasa(self) -> None:
        self.assertTrue(conformidad.revisar("plantilla"))

    def test_nombre_invalido(self) -> None:
        with self.assertRaises(ValueError):
            tienda.cargar("../x")


if __name__ == "__main__":
    unittest.main()
