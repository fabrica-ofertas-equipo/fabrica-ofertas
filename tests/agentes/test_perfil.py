"""Pruebas de ``agentes.perfil``: ``settings.efectivo.json`` y entorno del hijo (docs/09 §6.1, §3.3)."""
from __future__ import annotations

import unittest
from pathlib import Path

from agentes import perfil
from agentes.tipos import EspecCorrida, Presupuesto

RAIZ = Path(__file__).resolve().parents[2]


def _espec(rol: str = "maker") -> EspecCorrida:
    return EspecCorrida(
        rol=rol, etapa="D3", oferta_id="OF-202611-01", agente=f"d3-{rol}",
        prompt_base="encargo", entradas=(), contrato_salida="contratos/oferta.schema.json",
        artefactos_esperados=("oferta.json",) if rol == "maker" else (),
        herramientas=("Read", "Grep", "Glob", "Write", "Edit") if rol == "maker" else ("Read", "Grep", "Glob"),
        allow=("Edit(//RAIZ/ofertas/OF-202611-01/D3/.staging/RUN-1/**)",) if rol == "maker" else (),
        rutas_escribibles=("oferta.json",) if rol == "maker" else (),
        presupuesto=Presupuesto(usd_centavos_max=500, tiempo_s_max=1200, turnos_max=40),
        modelo="claude-sonnet-5", esfuerzo="medium",
    )


class PruebaSettingsEfectivo(unittest.TestCase):
    def test_maker_no_deniega_su_propio_staging(self) -> None:
        settings = perfil.construir_settings_efectivo(_espec("maker"), RAIZ)
        deny_texto = " ".join(settings["permissions"]["deny"])
        self.assertNotIn(".staging", deny_texto)
        self.assertIn("mcp__*", settings["permissions"]["deny"])

    def test_qa_deniega_todo_staging_y_runs(self) -> None:
        settings = perfil.construir_settings_efectivo(_espec("qa"), RAIZ)
        deny_texto = " ".join(settings["permissions"]["deny"])
        self.assertIn(".staging", deny_texto)
        self.assertIn("empresa/runs", deny_texto)
        self.assertNotIn("Edit(", " ".join(settings["permissions"]["allow"]))

    def test_disable_claude_ai_connectors(self) -> None:
        settings = perfil.construir_settings_efectivo(_espec("maker"), RAIZ)
        self.assertTrue(settings["disableClaudeAiConnectors"])
        self.assertTrue(settings["disableSkillShellExecution"])


class PruebaEntorno(unittest.TestCase):
    def test_entorno_minimo_sin_heredar_el_proceso(self) -> None:
        entorno = perfil.construir_entorno(
            _espec("maker"), run_id="RUN-1", raiz=RAIZ, staging_relativa="ofertas/OF-202611-01/D3/.staging/RUN-1",
            parametros_agentes={"bash_timeout_defecto_ms": 1000, "bash_timeout_max_ms": 5000},
            env_externo={"ANTHROPIC_API_KEY": "sk-ant-x", "PATH": "/no/debe/copiarse", "HOME": "/tampoco"},
        )
        self.assertNotIn("PATH", entorno)
        self.assertNotIn("HOME", entorno)
        self.assertEqual(entorno["ANTHROPIC_API_KEY"], "sk-ant-x")
        self.assertEqual(entorno["AGENT_ROL"], "maker")
        self.assertEqual(entorno["AGENT_ETAPA"], "D3")
        self.assertEqual(entorno["BASH_DEFAULT_TIMEOUT_MS"], "1000")

    def test_qa_recibe_disable_claude_mds(self) -> None:
        entorno = perfil.construir_entorno(
            _espec("qa"), run_id="RUN-1", raiz=RAIZ, staging_relativa="empresa/runs/RUN-1/staging",
            parametros_agentes={},
        )
        self.assertEqual(entorno.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS"), "1")
        self.assertEqual(entorno.get("AGENT_STAGING"), "")

    def test_exigir_sin_secretos_prohibidos_detecta_clave(self) -> None:
        with self.assertRaises(ValueError):
            perfil.exigir_sin_secretos_prohibidos({"STRIPE_SECRET_KEY": "algo"})

    def test_exigir_sin_secretos_prohibidos_detecta_valor_con_forma_de_secreto(self) -> None:
        with self.assertRaises(ValueError):
            perfil.exigir_sin_secretos_prohibidos({"ALGO": "sk" + "_live_abcdefghijklmnop"})


if __name__ == "__main__":
    unittest.main()
