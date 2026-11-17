"""Compatibilidad con la pantalla #/jurado: el jurado.json se lee con dashboard/web/lib/jurado.js (node). Se omite si no hay node."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.jurado import _comun as c

LIB = c.RAIZ / "dashboard" / "web" / "lib" / "jurado.js"
DEMO = c.RAIZ / ".claude" / "skills" / "jurado-creativos" / "evals" / "demostracion" / "tanda-2026-11-08_pl-PL" / "jurado.json"


@unittest.skipUnless(shutil.which("node") and LIB.is_file() and DEMO.is_file(), "sin node o sin la pantalla")
class PruebaLecturaPorLaPantalla(unittest.TestCase):
    def _leer(self, dato: dict) -> dict:
        codigo = (
            "import fs from 'node:fs';"
            f"import * as J from '{LIB.as_posix()}';"
            "const dato = JSON.parse(fs.readFileSync(0, 'utf8'));"
            "const m = J.modeloJurado({estado: 'ok', dato});"
            "console.log(JSON.stringify({estado: m.estado, votos: m.votos.length, piezas: m.piezas.length, orden: m.orden.length, origen: m.ordenOrigen,"
            " avatares: m.avatares.length, modo: m.modo, sello: m.sello, mercado: m.mercado, precision: J.evaluarPrecision(m.precision).estado,"
            " primero: m.orden[0] && m.orden[0].ad}));"
        )
        r = subprocess.run(["node", "--input-type=module", "-e", codigo], input=json.dumps(dato), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_la_demostracion_se_lee_completa(self):
        dato = json.loads(DEMO.read_text(encoding="utf-8"))
        m = self._leer(dato)
        self.assertEqual(m["estado"], "ok")
        self.assertEqual(m["votos"], len(dato["votos"]))
        self.assertEqual(m["piezas"], len(dato["piezas"]))
        self.assertEqual(m["orden"], len(dato["orden"]))
        self.assertEqual(m["origen"], "archivo")  # el orden lo dejó el jurado, la pantalla no lo recalcula
        self.assertEqual(m["avatares"], 10)
        self.assertEqual((m["modo"], m["mercado"]), ("sombra", "pl-PL"))
        self.assertEqual(m["sello"], dato["sello"])
        self.assertEqual(m["primero"], dato["orden"][0]["ad_name"])
        self.assertEqual(m["precision"], "acumulando")  # 0 de 150: la pantalla no inventa precisión

    def test_una_precision_fusionada_llega_a_la_pantalla(self):
        dato = json.loads(DEMO.read_text(encoding="utf-8"))
        dato["precision"] = {"auc": 0.58, "brier": 0.24, "etiquetas": 200, "estado": "sombra", "baselines": [{"nombre": "azar", "auc": 0.5}]}
        self.assertEqual(self._leer(dato)["precision"], "sombra")


if __name__ == "__main__":
    unittest.main()
