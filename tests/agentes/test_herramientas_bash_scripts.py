"""Coherencia de ``bash_scripts`` en ``agentes/hooks/herramientas.yaml`` con el código real (docs/09 §14.5b).

La lista blanca de banderas solo protege si coincide con el CLI verdadero: un script inexistente, o una bandera
peligrosa que se cuela, la vuelve decorativa. Estas pruebas no ejecutan los scripts (sin red, sin escrituras).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
RUTA = RAIZ / "agentes" / "hooks" / "herramientas.yaml"
BANDERAS_PROHIBIDAS = re.compile(r"^--(live|chrome|binario|token|clave|secret|force|forzar)\b")


class PruebaBashScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scripts: dict = yaml.safe_load(RUTA.read_text(encoding="utf-8"))["bash_scripts"]

    def test_todo_script_listado_existe(self) -> None:
        faltan = [s for s in self.scripts if not (RAIZ / s).is_file()]
        self.assertEqual([], faltan, "scripts de la lista blanca que ya no existen (regenerar la lista)")

    def test_cada_entrada_trae_una_lista_de_flags_de_texto(self) -> None:
        for nombre, entrada in self.scripts.items():
            with self.subTest(script=nombre):
                self.assertIsInstance(entrada.get("flags"), list)
                self.assertTrue(all(isinstance(f, str) and f for f in entrada["flags"]))

    def test_ninguna_bandera_peligrosa_se_cuela(self) -> None:
        malas = {n: [f for f in e["flags"] if BANDERAS_PROHIBIDAS.match(f)] for n, e in self.scripts.items()}
        self.assertEqual({}, {n: m for n, m in malas.items() if m})

    def test_los_wrappers_de_meta_no_listan_banderas_que_nunca_existieron(self) -> None:
        # B5b: `--live` y `--object-ids` nunca existieron en estos CLI (el modo es `--modo {dry-run,fixture,live}`).
        for nombre in ("scripts/meta_crear.py", "scripts/meta_activar.py", "scripts/pausar.py", "scripts/subir_presupuesto.py"):
            with self.subTest(script=nombre):
                self.assertNotIn("--live", self.scripts[nombre]["flags"])
                self.assertNotIn("--object-ids", self.scripts[nombre]["flags"])
                self.assertIn("--modo", self.scripts[nombre]["flags"])

    def test_lint_claims_admite_macro_nicho_y_json(self) -> None:
        self.assertIn("--macro-nicho", self.scripts["scripts/lint_claims.py"]["flags"])
        self.assertIn("--json", self.scripts["scripts/lint_claims.py"]["flags"])


if __name__ == "__main__":
    unittest.main()
