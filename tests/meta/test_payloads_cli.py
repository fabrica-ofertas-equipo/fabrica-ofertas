"""CLI de meta.payloads (A3, ola 2 B5b): ``python -m meta.payloads presupuesto`` sin red ni --modo."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from meta import payloads
from tests.engine.apoyo import PruebaBase, crear_empresa


def _economia(*, tarifa_meta_bp: int = 0) -> dict:
    return {
        "cpa_be": {"monto": 1830, "moneda": "EUR"},
        "cpa_real": {"pes": {"monto": 5000, "moneda": "EUR"}, "central": {"monto": 1278, "moneda": "EUR"}, "opt": {"monto": 606, "moneda": "EUR"}},
        "dias_test": 10,
        "entradas_usadas": {"moneda": "EUR", "tarifa_meta_bp": tarifa_meta_bp},
    }


class PruebaCliPresupuesto(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        self.economia_ruta = self.tmp / "economia.json"

    def _correr(self, argv: list[str]) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = payloads.main(argv)
        return codigo, salida.getvalue()

    def test_presupuesto_desde_economia_json(self) -> None:
        self.economia_ruta.write_text(json.dumps(_economia()), encoding="utf-8")
        codigo, salida = self._correr([
            "presupuesto", "--economia", str(self.economia_ruta), "--n-anuncios-paquete", "5",
            "--raiz", str(self.emp.raiz), "--ahora", "2026-11-10T00:00:00Z", "--json",
        ])
        self.assertEqual(codigo, 0, salida)
        datos = json.loads(salida)["datos"]
        self.assertEqual(datos["n_anuncios"], 5)
        self.assertEqual(datos["diario"], 2745)
        self.assertEqual(datos["total_test"], 27450)
        self.assertFalse(datos["solo_refuta"])

    def test_tarifa_se_lee_de_economia_nunca_un_literal(self) -> None:
        self.economia_ruta.write_text(json.dumps(_economia(tarifa_meta_bp=1000)), encoding="utf-8")
        codigo, salida = self._correr([
            "presupuesto", "--economia", str(self.economia_ruta), "--n-anuncios-paquete", "5",
            "--raiz", str(self.emp.raiz), "--ahora", "2026-11-10T00:00:00Z", "--json",
        ])
        self.assertEqual(codigo, 0, salida)
        datos = json.loads(salida)["datos"]
        self.assertEqual(datos["tarifa_meta_bp"], 1000)

    def test_escenario_elige_el_cpa_esperado(self) -> None:
        self.economia_ruta.write_text(json.dumps(_economia()), encoding="utf-8")
        codigo, salida = self._correr([
            "presupuesto", "--economia", str(self.economia_ruta), "--n-anuncios-paquete", "5", "--escenario", "opt",
            "--raiz", str(self.emp.raiz), "--ahora", "2026-11-10T00:00:00Z", "--json",
        ])
        self.assertEqual(codigo, 0, salida)
        self.assertEqual(json.loads(salida)["datos"]["validar"], 15 * 606)

    def test_limites_faltantes_sale_5(self) -> None:
        self.economia_ruta.write_text(json.dumps(_economia()), encoding="utf-8")
        raiz_sin_limites = self.tmp / "sin-limites"
        raiz_sin_limites.mkdir()
        codigo, _ = self._correr([
            "presupuesto", "--economia", str(self.economia_ruta), "--n-anuncios-paquete", "5",
            "--raiz", str(raiz_sin_limites),
        ])
        self.assertEqual(codigo, 5)


if __name__ == "__main__":
    unittest.main()
