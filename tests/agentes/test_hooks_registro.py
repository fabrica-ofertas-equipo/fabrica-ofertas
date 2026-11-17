"""Pruebas de ``agentes.hooks.posttooluse_registro`` (docs/09 §14.4)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentes.hooks import posttooluse_registro as hook


class PruebaPostToolUseRegistro(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)
        self._tmp = tempfile.TemporaryDirectory(prefix="hook-registro-")
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        self.spool = self.raiz / "empresa" / "runs" / "RUN-1" / "herramientas.jsonl"

    def _env(self) -> dict[str, str]:
        return {"AGENT_RAIZ": str(self.raiz), "AGENT_RUN_ID": "RUN-1", "AGENT_ROL": "maker", "AGENT_ETAPA": "D3",
                "AGENT_OFERTA_ID": "OF-202611-01", "AGENT_SPOOL": str(self.spool), "AGENT_NOMBRE": "d3-maker"}

    def test_escribe_una_linea_con_hash_y_bytes_sin_contenido(self) -> None:
        archivo = self.raiz / "ofertas" / "OF-202611-01" / "D3" / ".staging" / "RUN-1" / "oferta.json"
        archivo.parent.mkdir(parents=True)
        archivo.write_text('{"a": 1}', encoding="utf-8")
        datos = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_use_id": "toolu_01",
                 "tool_input": {"file_path": str(archivo), "content": '{"a": 1}'},
                 "tool_response": {"type": "create"}, "duration_ms": 12}
        with mock.patch.dict(os.environ, self._env(), clear=True):
            self.assertIsNone(hook.manejar(datos))
        lineas = self.spool.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lineas), 1)
        linea = json.loads(lineas[0])
        self.assertEqual(linea["tool"], "Write")
        self.assertEqual(linea["entrada"]["bytes"], len('{"a": 1}'))
        self.assertTrue(linea["entrada"]["sha256"].startswith("sha256:"))
        self.assertNotIn("content", json.dumps(linea))
        self.assertNotIn("tool_response", linea)

    def test_bash_trunca_el_comando_largo(self) -> None:
        datos = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_use_id": "toolu_02",
                 "tool_input": {"command": "echo " + "x" * 1000}, "duration_ms": 5}
        with mock.patch.dict(os.environ, self._env(), clear=True):
            hook.manejar(datos)
        linea = json.loads(self.spool.read_text(encoding="utf-8").strip())
        self.assertLessEqual(len(linea["entrada"]["command"]), 300)

    def test_posttooluse_failure_anota_resultado_error(self) -> None:
        datos = {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_use_id": "toolu_03",
                 "tool_input": {"command": "false"}, "error": "exit 1"}
        with mock.patch.dict(os.environ, self._env(), clear=True):
            hook.manejar(datos)
        linea = json.loads(self.spool.read_text(encoding="utf-8").strip())
        self.assertEqual(linea["resultado"], "error")

    def test_evento_desconocido_no_escribe_nada(self) -> None:
        with mock.patch.dict(os.environ, self._env(), clear=True):
            self.assertIsNone(hook.manejar({"hook_event_name": "Notification"}))
        self.assertFalse(self.spool.exists())


if __name__ == "__main__":
    unittest.main()
