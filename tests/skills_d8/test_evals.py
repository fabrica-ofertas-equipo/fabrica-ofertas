"""Los evals dorados de la skill d8-optimizacion, la coherencia de la plantilla con el contrato ``decision`` y la forma de la skill."""
from __future__ import annotations

import contextlib
import io
import json
import re
import unittest

from tests.skills_d8._comun import RAIZ, SKILL, cargar_modulo, no_hay_floats, umbrales_prueba

PE = cargar_modulo("probar_evals")
PR = cargar_modulo("proponer")


class PruebaEvalsDorados(unittest.TestCase):
    def test_los_tres_dorados_pasan(self) -> None:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = PE.main([])
        self.assertEqual(codigo, 0, salida.getvalue())
        for caso in ("D01", "D02", "D03"):
            self.assertIn(f"OK   {caso}", salida.getvalue())

    def test_cada_dorado_tiene_entrada_esperado_y_expectativas_de_agentes(self) -> None:
        for ruta in sorted((SKILL / "evals" / "dorados").glob("D*.json")):
            caso = json.loads(ruta.read_text(encoding="utf-8"))
            for campo in ("id", "descripcion", "modo", "entrada", "esperado", "salida_maker_esperada", "salida_qa_esperada"):
                self.assertIn(campo, caso, f"{ruta.name} sin {campo}")
            self.assertEqual(no_hay_floats(caso), [], ruta.name)

    def test_un_caso_roto_se_detecta(self) -> None:
        caso = json.loads((SKILL / "evals" / "dorados" / "D01.json").read_text(encoding="utf-8"))
        caso["esperado"]["accion_negocio"] = "MANTENER"
        self.assertTrue(PE.correr(caso, umbrales_prueba()))

    def test_d01_y_d02_solo_difieren_en_el_gasto_y_en_el_resultado(self) -> None:
        d1 = json.loads((SKILL / "evals" / "dorados" / "D01.json").read_text(encoding="utf-8"))
        d2 = json.loads((SKILL / "evals" / "dorados" / "D02.json").read_text(encoding="utf-8"))
        self.assertEqual(d1["entrada"]["dia"]["ventas_stripe_total"], d2["entrada"]["dia"]["ventas_stripe_total"])
        self.assertEqual((d1["esperado"]["accion_negocio"], d2["esperado"]["accion_negocio"]), ("APAGAR", "MANTENER"))


class PruebaPlantillaYContrato(unittest.TestCase):
    """La plantilla ``propuesta-de-decision.json`` debe poder convertirse en registros válidos del contrato ``decision``."""

    def registro(self, p: dict, oferta_id: str) -> dict:
        h = "sha256:" + "a" * 64
        return {
            "schema_version": "1.1.0", "decision_id": h, "oferta_id": oferta_id, "objeto_tipo": p["objeto_tipo"], "objeto_id": p["objeto_id"],
            "lectura_ts": "2026-11-09T09:00:00Z", "ts": "2026-11-09T09:00:00Z", "nivel": "N0", "gate": "H", "accion": p["accion_contrato"],
            "codigo": p["codigo"], "regla": p["regla"], "version_reglas": "0.1.0", "hash_parametros": h,
            "evidencia": {"gasto": {"monto": 0, "moneda": "USD"}, "clics": 0, "compras": 0, "p_cpa_menor_equilibrio": None},
            "explicacion": p["explicacion"], "ejecutada": False,
        }

    def test_cada_propuesta_de_la_plantilla_valida_contra_decision_schema(self) -> None:
        from engine import comun
        plantilla = json.loads((SKILL / "templates" / "propuesta-de-decision.json").read_text(encoding="utf-8"))
        self.assertEqual(no_hay_floats(plantilla), [])
        self.assertGreaterEqual(len(plantilla["propuestas"]), 2)
        for p in plantilla["propuestas"]:
            self.assertEqual(PR.ACCION_CONTRATO[p["accion_negocio"]], p["accion_contrato"], p["accion_negocio"])
            errores = comun.errores_de_esquema("decision", self.registro(p, plantilla["oferta_id"]))
            self.assertEqual(errores, [], f"{p['accion_negocio']}: {errores}")

    def test_lo_que_sale_de_proponer_valida_contra_decision_schema(self) -> None:
        from engine import comun
        from tests.skills_d8.test_proponer import BUENO, MALO, entrada_fatiga, serie_anuncio
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=4)
        r = PR.evaluar_fatiga(entrada_fatiga(por_dia, fin), umbrales_prueba())
        for p in r["propuestas"]:
            self.assertEqual(comun.errores_de_esquema("decision", self.registro({**p, "explicacion": p["explicacion"]}, "OF-202611-02")), [])

    def test_las_acciones_de_negocio_cubren_el_vocabulario_de_la_skill(self) -> None:
        self.assertEqual(set(PR.ACCION_CONTRATO), {"APAGAR", "MANTENER", "GRADUAR", "RELEVAR", "AVISAR_FATIGA", "PAUSAR_Y_ESCALAR", "NO_DECIDIR"})
        self.assertTrue(set(PR.ACCION_CONTRATO.values()) <= {"MATAR", "SEGUIR", "ESCALAR", "INCONCLUSO", "BLOQUEADO"})


class PruebaFormaDeLaSkill(unittest.TestCase):
    def test_archivos_pedidos_existen(self) -> None:
        esperados = [
            "SKILL.md", "CHANGELOG.md", "PEDIDOS.md", "rubric.md",
            "references/protocolo-j3.md", "references/decisiones-y-umbrales.md", "references/fatiga-relevo.md",
            "references/estadistica-honesta.md", "references/conflictos-con-la-spec-vieja.md", "references/bugs-conocidos.md",
            "templates/expediente-diario.md", "templates/propuesta-de-decision.json", "templates/informe-de-cierre.md",
            "scripts/preparar_expediente.py", "scripts/proponer.py", "scripts/validar_propuesta.py", "scripts/probar_evals.py",
            "evals/dorados/D01.json", "evals/dorados/D02.json", "evals/dorados/D03.json", "evals/_base/umbrales_prueba.json",
        ]
        faltan = [e for e in esperados if not (SKILL / e).is_file()]
        self.assertEqual(faltan, [])
        for agente in ("d8-maker.md", "d8-qa.md"):
            self.assertTrue((RAIZ / ".claude" / "agents" / agente).is_file(), agente)

    def test_frontmatter_y_limites_de_forma(self) -> None:
        texto = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
        self.assertIsNotNone(m)
        fm = m.group(1)
        self.assertIn("name: d8-optimizacion", fm)
        self.assertIn("disable-model-invocation: true", fm)
        self.assertRegex(fm, r'version: "0\.1\.[0-9]+"')  # línea 0.1 (los parches 0.1.x son de integración)
        desc = re.search(r'^description: "(.*)"$', fm, re.M)
        self.assertIsNotNone(desc)
        self.assertLess(len(desc.group(1)), 1024)
        self.assertLess(len(texto.splitlines()), 500)
        self.assertIn("v0.1 sin pulir", texto)

    def test_los_agentes_tienen_herramientas_minimas(self) -> None:
        maker = (RAIZ / ".claude" / "agents" / "d8-maker.md").read_text(encoding="utf-8")
        qa = (RAIZ / ".claude" / "agents" / "d8-qa.md").read_text(encoding="utf-8")
        tools_maker = re.search(r"^tools: (.*)$", maker, re.M).group(1)
        tools_qa = re.search(r"^tools: (.*)$", qa, re.M).group(1)
        self.assertEqual(tools_qa.strip(), "Read, Grep, Glob")
        for prohibida in ("ads_activate_entity", "ads_create", "ads_update_entity", "ads_creative", "ads_delete", "WebFetch", "WebSearch"):
            self.assertNotIn(prohibida, tools_maker)
        for herramienta in re.findall(r"mcp__[A-Za-z0-9_]+", tools_maker):
            self.assertRegex(herramienta, r"__ads_(get_|account_get_)", herramienta)  # solo lecturas de Meta
        disallowed = re.search(r"^disallowedTools: (.*)$", maker, re.M).group(1)
        for patron in ("ads_activate_entity", "ads_create_*", "ads_update_entity", "ads_delete_*"):
            self.assertIn(patron, disallowed)
        self.assertIn("Write", re.search(r"^disallowedTools: (.*)$", qa, re.M).group(1))

    def test_ningun_script_toca_la_red_ni_claves(self) -> None:
        for nombre in ("preparar_expediente.py", "proponer.py", "validar_propuesta.py", "probar_evals.py"):
            texto = (SKILL / "scripts" / nombre).read_text(encoding="utf-8")
            for prohibido in ("import requests", "urllib.request", "import socket", "http.client", ".env", "subprocess", "os.system"):
                self.assertNotIn(prohibido, texto, f"{nombre}: {prohibido}")


if __name__ == "__main__":
    unittest.main()
