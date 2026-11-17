"""Prueba de humo del entorno: intérprete, dependencias y estructura del repositorio."""
import importlib
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PAQUETES = (
    "engine", "decision", "datos", "meta", "compliance", "postcompra",
    "landing", "dashboard", "agentes", "infra", "contratos", "scripts",
)


class PruebaHumo(unittest.TestCase):
    """Verifica que el repositorio está listo para que los componentes construyan."""

    def test_version_de_python(self):
        self.assertGreaterEqual(sys.version_info[:2], (3, 12))

    def test_dependencias_de_runtime(self):
        import jsonschema
        import yaml

        self.assertEqual(yaml.safe_load("a: 1"), {"a": 1})
        jsonschema.validate({"a": 1}, {"type": "object", "required": ["a"]})
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({}, {"type": "object", "required": ["a"]})

    def test_paquetes_importables(self):
        for nombre in PAQUETES:
            with self.subTest(paquete=nombre):
                self.assertIsNotNone(importlib.import_module(nombre))

    def test_estructura_y_readmes(self):
        carpetas = [*PAQUETES, "tracking", "tracking/workers", "infra/workers", "infra/plantillas",
                    "contratos/ejemplos", "empresa", "ofertas/_ejemplo", "tests/fixtures",
                    ".claude/agents", ".claude/skills"]
        for carpeta in carpetas:
            with self.subTest(carpeta=carpeta):
                readme = RAIZ / carpeta / "README.md"
                self.assertTrue(readme.is_file(), f"falta {readme}")
                self.assertTrue(readme.read_text(encoding="utf-8").strip(), "README vacío")

    def test_pruebas_por_componente(self):
        for nombre in PAQUETES:
            with self.subTest(componente=nombre):
                self.assertTrue((RAIZ / "tests" / nombre / "__init__.py").is_file())

    def test_env_example_sin_valores(self):
        lineas = (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
        asignaciones = [l for l in lineas if l and not l.startswith("#")]
        self.assertGreater(len(asignaciones), 20)
        for linea in asignaciones:
            with self.subTest(linea=linea):
                nombre, _, valor = linea.partition("=")
                self.assertRegex(nombre, r"^[A-Z][A-Z0-9_]+$")
                self.assertEqual(valor, "", "no debe haber valores en .env.example")


if __name__ == "__main__":
    unittest.main()
