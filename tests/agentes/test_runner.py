"""Pruebas de ``agentes.runner``: los 10 casos de modo FIXTURE (docs/09 §12.8, criterio B0-08)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentes.runner import ejecutar, preparar
from agentes.tipos import Modo, espec_desde_mapa

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "tests" / "fixtures" / "agentes"

CASOS_SIMPLES = (
    "D3_maker_ok", "D3_maker_invalido_esquema", "D3_maker_artefacto_fuera_de_ruta",
    "D3_maker_sin_structured_output", "D3_maker_max_turns", "D3_maker_max_budget",
    "D3_maker_crash_costo_cero", "D3_maker_stream_bucle", "D3_qa_sello_de_goma",
)


class PruebaBase(unittest.TestCase):
    """Bloquea ``socket.socket``: ninguna prueba del runner abre red (convenciones §11)."""

    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)


def _cargar_espec(nombre: str):
    return espec_desde_mapa(json.loads((FIXTURES / nombre / "espec.json").read_text(encoding="utf-8")))


class PruebaFixture10Casos(PruebaBase):
    """Los 10 casos mínimos de §12.8: todos dan el ``estado`` esperado, sin procesos ni red."""

    def test_los_10_casos_dan_el_estado_esperado(self) -> None:
        for nombre in CASOS_SIMPLES:
            with self.subTest(caso=nombre):
                carpeta = FIXTURES / nombre
                espec = _cargar_espec(nombre)
                esperado = json.loads((carpeta / "esperado.json").read_text(encoding="utf-8"))
                resultado = ejecutar(espec, modo=Modo.FIXTURE, fixture_dir=carpeta, raiz=RAIZ)
                self.assertEqual(resultado.estado, esperado["estado"], resultado.errores)
                if "contiene_en_errores" in esperado:
                    self.assertTrue(
                        any(esperado["contiene_en_errores"] in e for e in resultado.errores),
                        f"{nombre}: {resultado.errores}",
                    )
                if "artefactos_cuenta" in esperado:
                    self.assertEqual(len(resultado.artefactos), esperado["artefactos_cuenta"])
                if "costo_confiable" in esperado:
                    self.assertEqual(resultado.costo["confiable"], esperado["costo_confiable"])
                if "costo_centavos_esperado" in esperado:
                    self.assertEqual(resultado.costo["centavos_usd"], esperado["costo_centavos_esperado"])

    def test_pausa_a_mitad_descarta_el_staging(self) -> None:
        carpeta = FIXTURES / "D3_maker_pausa_a_mitad"
        espec = _cargar_espec("D3_maker_pausa_a_mitad")
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "empresa").mkdir(parents=True)
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            resultado = ejecutar(espec, modo=Modo.FIXTURE, fixture_dir=carpeta, raiz=raiz)
        self.assertEqual(resultado.estado, "pausa")
        self.assertEqual(resultado.artefactos, [])


class PruebaPreparar(PruebaBase):
    """``preparar()`` es puro: mismo ``espec`` -> mismo ``run_id`` y argv; nunca lanza procesos."""

    def test_preparar_es_deterministico(self) -> None:
        espec = _cargar_espec("D3_maker_ok")
        plan1 = preparar(espec, raiz=RAIZ, parametros_agentes={"holgura_pct": 10})
        plan2 = preparar(espec, raiz=RAIZ, parametros_agentes={"holgura_pct": 10})
        self.assertEqual(plan1.run_id, plan2.run_id)
        self.assertEqual(plan1.argv, plan2.argv)

    def test_argv_tiene_las_banderas_de_aislamiento(self) -> None:
        espec = _cargar_espec("D3_maker_ok")
        plan = preparar(espec, raiz=RAIZ)
        argv = plan.argv
        self.assertIn("--strict-mcp-config", argv)
        self.assertIn("--disallowedTools", argv)
        self.assertIn("mcp__*", argv)
        self.assertIn("--permission-mode", argv)
        self.assertIn("dontAsk", argv)
        self.assertTrue(plan.settings_efectivo["disableClaudeAiConnectors"])

    def test_entorno_del_hijo_sin_claves_prohibidas(self) -> None:
        """Criterio B0-08: el entorno del hijo nunca trae claves de Stripe, Meta, SELLO_* ni GITHUB_TOKEN."""
        espec = _cargar_espec("D3_maker_ok")
        env_externo = {
            "ANTHROPIC_API_KEY": "sk-ant-prueba-no-real", "STRIPE_SECRET_KEY": "sk_live_no_debe_pasar",
            "META_TOKEN_OPERADOR": "no_debe_pasar", "SELLO_X1": "no_debe_pasar", "GITHUB_TOKEN": "no_debe_pasar",
        }
        plan = preparar(espec, raiz=RAIZ, env_externo=env_externo)
        self.assertNotIn("STRIPE_SECRET_KEY", plan.entorno)
        self.assertNotIn("META_TOKEN_OPERADOR", plan.entorno)
        self.assertNotIn("SELLO_X1", plan.entorno)
        self.assertNotIn("GITHUB_TOKEN", plan.entorno)
        self.assertEqual(plan.entorno.get("ANTHROPIC_API_KEY"), "sk-ant-prueba-no-real")
        for clave, valor in plan.entorno.items():
            self.assertNotRegex(clave, r"STRIPE|META_TOKEN|SELLO_|GITHUB_TOKEN", clave)


class PruebaLivePreflight(PruebaBase):
    """LIVE fuera de producción (o sin parámetros de agentes) nunca llega a lanzar un proceso."""

    def test_live_fuera_de_produccion_da_preflight(self) -> None:
        espec = _cargar_espec("D3_maker_ok")
        resultado = ejecutar(espec, modo=Modo.LIVE, raiz=RAIZ, env={"FABRICA_ENTORNO": "prueba"})
        self.assertEqual(resultado.estado, "preflight")

    def test_live_en_produccion_sin_parametros_agentes_da_preflight(self) -> None:
        espec = _cargar_espec("D3_maker_ok")
        resultado = ejecutar(espec, modo=Modo.LIVE, raiz=RAIZ, env={"FABRICA_ENTORNO": "produccion"})
        self.assertEqual(resultado.estado, "preflight")
        self.assertTrue(any("agentes" in e for e in resultado.errores))


if __name__ == "__main__":
    unittest.main()
