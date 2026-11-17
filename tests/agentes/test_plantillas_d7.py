"""A8 (ola 2, B5b): el perfil/lista blanca del Maker D7 permite SOLO lecturas de Meta
(``ads_get_*``/``ads_insights_*``) y ninguna escritura; el QA de D7 no toca Meta en absoluto.

No hay todavía un ``engine.orq`` que ensamble la ``EspecCorrida`` de D7 (B1, ola 1): estas pruebas
verifican el ÚNICO lugar donde hoy se declara ese permiso, las plantillas de
``agentes/plantillas_agentes/d7-{maker,qa}.md`` (frontmatter YAML + cuerpo), igual que lo haría
``agentes.perfil`` si las leyera. Reutiliza (solo lectura) ``agentes/hooks/herramientas.yaml`` para
no duplicar la lista de patrones de escritura de Meta.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
PLANTILLAS = RAIZ / "agentes" / "plantillas_agentes"
HERRAMIENTAS = RAIZ / "agentes" / "hooks" / "herramientas.yaml"

_PATRON_LECTURA_META = re.compile(r"^mcp__\*__ads_(get_\*|insights_\*)$")


def _frontmatter(ruta: Path) -> tuple[dict, str]:
    """``(frontmatter YAML, cuerpo)`` de una plantilla ``---\\n...\\n---\\ncuerpo``."""
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith("---\n"), f"{ruta.name}: falta el frontmatter YAML"
    _, resto = texto.split("---\n", 1)
    bloque, cuerpo = resto.split("---\n", 1)
    return yaml.safe_load(bloque), cuerpo


def _patrones_escritura_meta() -> list[str]:
    """Patrones de ``herramientas.yaml#escritura`` que son de la Marketing API de Meta.

    ``ads_studio_*`` es de Higgsfield (generación de creativos, no de Meta): se excluye a propósito.
    """
    datos = yaml.safe_load(HERRAMIENTAS.read_text(encoding="utf-8"))
    return [p for p in datos["escritura"] if p.startswith("mcp__*__ads_") and not p.startswith("mcp__*__ads_studio")]


class PruebaPlantillaD7Maker(unittest.TestCase):
    def setUp(self) -> None:
        self.ruta = PLANTILLAS / "d7-maker.md"
        self.assertTrue(self.ruta.is_file(), "falta agentes/plantillas_agentes/d7-maker.md")
        self.fm, self.cuerpo = _frontmatter(self.ruta)

    def test_tools_no_declara_ninguna_herramienta_mcp(self) -> None:
        # Las herramientas de Meta (lectura incluida) no van en `tools:` (lista gruesa de Claude
        # Code); el runner automatizado bloquea mcp__* por completo (agentes/perfil.py construir_argv).
        herramientas = [h.strip() for h in str(self.fm.get("tools", "")).split(",")]
        self.assertFalse(any(h.startswith("mcp__") for h in herramientas), herramientas)

    def test_disallowed_tools_cubre_toda_escritura_de_meta_de_herramientas_yaml(self) -> None:
        disallowed = {d.strip() for d in str(self.fm.get("disallowedTools", "")).split(",")}
        faltantes = [p for p in _patrones_escritura_meta() if p not in disallowed]
        self.assertEqual(faltantes, [], f"patrones de escritura de herramientas.yaml sin reflejar en disallowedTools: {faltantes}")

    def test_prohibido_menciona_los_4_wrappers_con_efecto_real(self) -> None:
        for script in ("meta_crear.py", "meta_activar.py", "pausar.py", "subir_presupuesto.py"):
            self.assertIn(script, self.cuerpo, f"el cuerpo debe prohibir explícitamente {script}")

    def test_prohibido_menciona_modo_live(self) -> None:
        self.assertIn("--modo live", self.cuerpo)

    def test_solo_lectura_de_meta_esta_documentada(self) -> None:
        self.assertIn("ads_get_*", self.cuerpo)
        self.assertIn("ads_insights_*", self.cuerpo)


class PruebaPlantillaD7Qa(unittest.TestCase):
    def setUp(self) -> None:
        self.ruta = PLANTILLAS / "d7-qa.md"
        self.assertTrue(self.ruta.is_file(), "falta agentes/plantillas_agentes/d7-qa.md")
        self.fm, self.cuerpo = _frontmatter(self.ruta)

    def test_disallowed_tools_bloquea_bash_write_edit_y_todo_mcp(self) -> None:
        disallowed = {d.strip() for d in str(self.fm.get("disallowedTools", "")).split(",")}
        for prohibida in ("Bash", "Write", "Edit", "mcp__*"):
            self.assertIn(prohibida, disallowed)

    def test_tools_es_solo_lectura(self) -> None:
        herramientas = {h.strip() for h in str(self.fm.get("tools", "")).split(",")}
        self.assertEqual(herramientas, {"Read", "Grep", "Glob"})


if __name__ == "__main__":
    unittest.main()
