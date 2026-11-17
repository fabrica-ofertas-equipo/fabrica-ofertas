"""Pruebas de scripts.producto.lint (lint de contenido D4: matriz de promesas, placeholders, tamaño, PII)."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from engine.errores import ErrorValidacion, ParametroFaltante
from scripts.producto import lint as L

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "producto"
ENTREGABLES = FIX / "entregables"


def _json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


PARAMETROS = {"grupos": {"producto": {"peso_max_mb_pdf": {"valor": "5"}, "peso_max_mb_paquete": {"valor": "25"}}}}


class PruebaLintear(unittest.TestCase):
    def test_contenido_limpio_da_pass(self) -> None:
        producto = _json(FIX / "producto-lint-ok.json")
        resultado = L.lintear(producto, [ENTREGABLES / "guia.md"], PARAMETROS)
        self.assertEqual("PASS", resultado["veredicto"])
        self.assertEqual([], resultado["hallazgos"])

    def test_marca_pendiente_bloquea(self) -> None:
        producto = _json(FIX / "producto-lint-ok.json")
        resultado = L.lintear(producto, [ENTREGABLES / "guia-con-placeholder.md"], PARAMETROS)
        self.assertEqual("FAIL", resultado["veredicto"])
        self.assertTrue(any(h["check_id"] == "L1-09" for h in resultado["hallazgos"]))

    def test_correo_en_el_entregable_bloquea(self) -> None:
        producto = _json(FIX / "producto-lint-ok.json")
        resultado = L.lintear(producto, [ENTREGABLES / "guia-con-correo.md"], PARAMETROS)
        self.assertEqual("FAIL", resultado["veredicto"])
        self.assertTrue(any("correo" in h["mensaje"] for h in resultado["hallazgos"]))

    def test_promesa_que_referencia_entregable_inexistente_bloquea(self) -> None:
        producto = _json(FIX / "producto-lint-promesa-rota.json")
        resultado = L.lintear(producto, [ENTREGABLES / "guia.md"], PARAMETROS)
        self.assertEqual("FAIL", resultado["veredicto"])
        self.assertTrue(any(h["check_id"] == "D4-promesa" for h in resultado["hallazgos"]))

    def test_promesa_pendiente_da_pass_con_notas_no_falla(self) -> None:
        producto = _json(FIX / "producto-lint-ok.json")
        producto["matriz_promesas"][0]["estado"] = "pendiente"
        resultado = L.lintear(producto, [ENTREGABLES / "guia.md"], PARAMETROS)
        self.assertEqual("PASS_CON_NOTAS", resultado["veredicto"])

    def test_archivo_que_supera_el_tope_oficial_bloquea(self) -> None:
        import tempfile

        producto = _json(FIX / "producto-lint-ok.json")
        parametros_estrictos = {"grupos": {"producto": {"peso_max_mb_pdf": {"valor": "0.0000001"},
                                                         "peso_max_mb_paquete": {"valor": "25"}}}}
        with tempfile.TemporaryDirectory() as d:
            pdf = Path(d) / "grande.pdf"
            pdf.write_bytes(b"%PDF-1.4\n" + b"0" * 1000)
            resultado = L.lintear(producto, [pdf], parametros_estrictos)
        self.assertEqual("FAIL", resultado["veredicto"])
        self.assertTrue(any(h["check_id"] == "D4-peso" for h in resultado["hallazgos"]))

    def test_sin_parametro_oficial_falla_cerrado(self) -> None:
        producto = _json(FIX / "producto-lint-ok.json")
        sin_param = {"grupos": {"producto": {"peso_max_mb_pdf": {"valor": None}, "peso_max_mb_paquete": {"valor": "25"}}}}
        with self.assertRaises(ParametroFaltante):
            L.lintear(producto, [ENTREGABLES / "guia.md"], sin_param)

    def test_producto_sin_items_es_invalido(self) -> None:
        with self.assertRaises(ErrorValidacion):
            L.lintear({"matriz_promesas": []}, [], PARAMETROS)


class PruebaCli(unittest.TestCase):
    def _correr(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "scripts.producto.lint", *args],
                              cwd=RAIZ, capture_output=True, text=True, timeout=30)

    def test_cli_con_contenido_limpio_sale_0(self) -> None:
        r = self._correr(str(FIX / "producto-lint-ok.json"), "--fuente", str(ENTREGABLES / "guia.md"))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("PASS", json.loads(r.stdout)["veredicto"])

    def test_cli_con_placeholder_sale_3(self) -> None:
        r = self._correr(str(FIX / "producto-lint-ok.json"), "--fuente", str(ENTREGABLES / "guia-con-placeholder.md"))
        self.assertEqual(3, r.returncode, r.stderr)

    def test_cli_sin_fuente_valida_sale_2(self) -> None:
        r = self._correr(str(FIX / "producto-lint-ok.json"), "--fuente", str(ENTREGABLES / "no-existe.md"))
        self.assertEqual(2, r.returncode)


if __name__ == "__main__":
    unittest.main()
