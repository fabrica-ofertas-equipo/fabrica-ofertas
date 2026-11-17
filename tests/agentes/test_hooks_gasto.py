"""Pruebas de ``agentes.hooks.pretooluse_gasto`` (docs/09 §14.2): casos límite, positivos y negativos."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentes.hooks import pretooluse_gasto as hook
from agentes.sonda_hooks import construir_empresa_de_prueba


class PruebaBase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)
        self._tmp = tempfile.TemporaryDirectory(prefix="hook-gasto-")
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)

    def _env(self, **extra: str) -> dict[str, str]:
        base = {"AGENT_RAIZ": str(self.raiz), "AGENT_RUN_ID": "RUN-1", "AGENT_ROL": "maker", "AGENT_ETAPA": "D3",
                "AGENT_OFERTA_ID": "OF-202611-01", "AGENT_SPOOL": str(self.raiz / "empresa" / "registro.jsonl")}
        base.update(extra)
        return base

    def _manejar(self, datos: dict, env: dict) -> str | None:
        with mock.patch.dict(os.environ, env, clear=True):
            return hook.manejar(datos)


class PruebaLecturaSiempreLibre(PruebaBase):
    def test_read_no_opina_incluso_con_pausa(self) -> None:
        construir_empresa_de_prueba(self.raiz, pausa=True, max_budget_por_corrida_agente=None)
        motivo = self._manejar({"tool_name": "Read", "tool_input": {"file_path": "/x"}}, self._env())
        self.assertIsNone(motivo)

    def test_lectura_mcp_get_no_opina(self) -> None:
        construir_empresa_de_prueba(self.raiz, pausa=True)
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_get_ad_accounts", "tool_input": {}}, self._env())
        self.assertIsNone(motivo)


class PruebaCasosLimite(PruebaBase):
    def _staging(self) -> str:
        staging = self.raiz / "ofertas" / "OF-202611-01" / "D3" / ".staging" / "RUN-1"
        staging.mkdir(parents=True, exist_ok=True)
        return str(staging)

    def test_pausa_deniega_escritura(self) -> None:
        construir_empresa_de_prueba(self.raiz, pausa=True)
        motivo = self._manejar({"tool_name": "Write", "tool_input": {"file_path": f"{self._staging()}/x.json", "content": "{}"}},
                               self._env(AGENT_STAGING=self._staging()))
        self.assertIsNotNone(motivo)
        self.assertIn("PAUSA", motivo)

    def test_limite_ausente_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz, max_budget_por_corrida_agente=None)
        motivo = self._manejar({"tool_name": "Write", "tool_input": {"file_path": f"{self._staging()}/x.json", "content": "{}"}},
                               self._env(AGENT_STAGING=self._staging()))
        self.assertIsNotNone(motivo)
        self.assertIn("límite", motivo)

    def test_infra_vencida_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz, infra_horas_atras=100)
        motivo = self._manejar({"tool_name": "Write", "tool_input": {"file_path": f"{self._staging()}/x.json", "content": "{}"}},
                               self._env(AGENT_STAGING=self._staging()))
        self.assertIsNotNone(motivo)
        self.assertIn("infra", motivo)

    def test_tope_exacto_de_edad_pasa(self) -> None:
        """Caso límite: edad == estado_max_edad_h (6h por defecto) debe seguir pasando."""
        construir_empresa_de_prueba(self.raiz, infra_horas_atras=6.0, estado_max_edad_h=6)
        motivo = self._manejar({"tool_name": "Write", "tool_input": {"file_path": f"{self._staging()}/x.json", "content": "{}"}},
                               self._env(AGENT_STAGING=self._staging()))
        self.assertIsNone(motivo)

    def test_escribir_fuera_del_staging_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        otra = self.raiz / "ofertas" / "OF-202611-01" / "otro.json"
        motivo = self._manejar({"tool_name": "Write", "tool_input": {"file_path": str(otra), "content": "{}"}},
                               self._env(AGENT_STAGING=self._staging()))
        self.assertIsNotNone(motivo)

    def test_escribir_dentro_del_staging_pasa(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        motivo = self._manejar({"tool_name": "Write", "tool_input": {"file_path": f"{self._staging()}/oferta.json", "content": "{}"}},
                               self._env(AGENT_STAGING=self._staging()))
        self.assertIsNone(motivo)

    def test_editar_limites_yaml_deniega_aunque_este_en_staging_declarado(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        motivo = self._manejar(
            {"tool_name": "Edit", "tool_input": {"file_path": str(self.raiz / "empresa" / "limites.yaml"), "old_string": "a", "new_string": "b"}},
            self._env(AGENT_STAGING=str(self.raiz)))  # staging = raíz: aun así, ruta protegida gana
        self.assertIsNotNone(motivo)

    def test_secreto_en_tool_input_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        motivo = self._manejar(
            {"tool_name": "Write", "tool_input": {"file_path": f"{self._staging()}/x.json", "content": "sk" + "_live_abcdefghijklmnop"}},
            self._env(AGENT_STAGING=self._staging()))
        self.assertIsNotNone(motivo)
        self.assertIn("secreto", motivo)

    def test_creditos_sin_cotizacion_previa_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        motivo = self._manejar({"tool_name": "mcp__claude_ai_Higgsfield__generate_image", "tool_input": {}}, self._env())
        self.assertIsNotNone(motivo)
        self.assertIn("AGENT_COSTO_PREVIO", motivo)

    def test_creditos_con_cotizacion_dentro_del_tope_pasa(self) -> None:
        construir_empresa_de_prueba(self.raiz)  # creditos_max_pieza=50, creditos_max_oferta=500 (fixture de B1)
        motivo = self._manejar({"tool_name": "mcp__claude_ai_Higgsfield__generate_image", "tool_input": {}},
                               self._env(AGENT_COSTO_PREVIO="10"))
        self.assertIsNone(motivo)

    def test_creditos_por_encima_del_tope_por_pieza_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        motivo = self._manejar({"tool_name": "mcp__claude_ai_Higgsfield__generate_image", "tool_input": {}},
                               self._env(AGENT_COSTO_PREVIO="999"))
        self.assertIsNotNone(motivo)

    def test_json_malformado_en_stdin_es_exit_2_vuelca_la_excepcion(self) -> None:
        """El envoltorio ``_comun.ejecutar`` (no ``manejar``) es quien convierte esto en exit 2;
        acá se comprueba que ``AGENT_RAIZ`` ausente SÍ hace que ``manejar`` lance (fail-closed)."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                hook.manejar({"tool_name": "Write", "tool_input": {"file_path": "/x", "content": "x"}})


if __name__ == "__main__":
    unittest.main()
