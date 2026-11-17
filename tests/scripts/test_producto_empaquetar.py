"""Pruebas de scripts.producto.empaquetar (empaquetado determinista de D4)."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from engine.errores import ErrorUso, ErrorValidacion
from scripts.producto import empaquetar as E

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "producto"
ENTREGABLES = FIX / "entregables"


def _json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


class PruebaEmpaquetar(unittest.TestCase):
    def setUp(self) -> None:
        self.entrada = _json(FIX / "entrada-empaquetar.json")

    def test_calcula_sha256_y_peso_reales_del_archivo(self) -> None:
        resultado = E.empaquetar(self.entrada, ENTREGABLES, prometido_min=20)
        item = resultado["producto"]["items"][0]
        self.assertTrue(item["sha256"].startswith("sha256:"))
        self.assertEqual(64 + len("sha256:"), len(item["sha256"]))
        self.assertNotEqual("0", item["peso_mb"])

    def test_es_determinista(self) -> None:
        r1 = E.empaquetar(self.entrada, ENTREGABLES, prometido_min=20)
        r2 = E.empaquetar(self.entrada, ENTREGABLES, prometido_min=20)
        self.assertEqual(r1, r2)

    def test_producto_sha256_depende_del_contenido_de_items(self) -> None:
        r1 = E.empaquetar(self.entrada, ENTREGABLES, prometido_min=20)
        otra = json.loads(json.dumps(self.entrada))
        otra["items"][0]["archivo"] = "guia-con-correo.md"
        r2 = E.empaquetar(otra, ENTREGABLES, prometido_min=20)
        self.assertNotEqual(r1["producto_sha256"], r2["producto_sha256"])

    def test_archivo_declarado_inexistente_es_error_de_uso(self) -> None:
        malo = json.loads(json.dumps(self.entrada))
        malo["items"][0]["archivo"] = "no-existe.md"
        with self.assertRaises(ErrorUso):
            E.empaquetar(malo, ENTREGABLES, prometido_min=20)

    def test_prometido_min_distinto_del_declarado_es_error_r10(self) -> None:
        with self.assertRaises(ErrorValidacion):
            E.empaquetar(self.entrada, ENTREGABLES, prometido_min=99)

    def test_resultado_cumple_el_esquema_producto(self) -> None:
        from engine import comun

        resultado = E.empaquetar(self.entrada, ENTREGABLES, prometido_min=20)
        self.assertEqual([], comun.errores_de_esquema("producto", resultado["producto"]))

    def test_entrada_sin_items_o_tiempos_es_invalida(self) -> None:
        with self.assertRaises(ErrorValidacion):
            E.empaquetar({}, ENTREGABLES, prometido_min=20)


class PruebaCli(unittest.TestCase):
    def _correr(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "scripts.producto.empaquetar", *args],
                              cwd=RAIZ, capture_output=True, text=True, timeout=30)

    def test_cli_calcula_y_sale_0(self) -> None:
        r = self._correr(str(FIX / "entrada-empaquetar.json"), "--raiz", str(ENTREGABLES), "--prometido-min", "20")
        self.assertEqual(0, r.returncode, r.stderr)
        salida = json.loads(r.stdout)
        self.assertTrue(salida["producto_sha256"].startswith("sha256:"))

    def test_cli_escribe_salida_y_no_la_sobrescribe(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            destino = Path(d) / "producto.json"
            r1 = self._correr(str(FIX / "entrada-empaquetar.json"), "--raiz", str(ENTREGABLES),
                              "--prometido-min", "20", "--salida", str(destino))
            self.assertEqual(0, r1.returncode, r1.stderr)
            self.assertTrue(destino.is_file())
            r2 = self._correr(str(FIX / "entrada-empaquetar.json"), "--raiz", str(ENTREGABLES),
                              "--prometido-min", "20", "--salida", str(destino))
            self.assertNotEqual(0, r2.returncode)

    def test_cli_con_archivo_faltante_sale_2(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            entrada = json.loads((FIX / "entrada-empaquetar.json").read_text(encoding="utf-8"))
            entrada["items"][0]["archivo"] = "no-existe.md"
            ruta = Path(d) / "entrada.json"
            ruta.write_text(json.dumps(entrada), encoding="utf-8")
            r = self._correr(str(ruta), "--raiz", str(ENTREGABLES), "--prometido-min", "20")
        self.assertEqual(2, r.returncode)


if __name__ == "__main__":
    unittest.main()
