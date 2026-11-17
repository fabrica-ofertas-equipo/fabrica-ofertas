"""Pruebas de ``agentes.hooks.stop_verificacion`` (docs/09 §14.5)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentes.hooks import stop_verificacion as hook


class PruebaStopVerificacion(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)
        self._tmp = tempfile.TemporaryDirectory(prefix="hook-stop-")
        self.addCleanup(self._tmp.cleanup)
        self.staging = Path(self._tmp.name) / "staging"
        self.staging.mkdir(parents=True)

    def _env(self, **extra: str) -> dict[str, str]:
        base = {"AGENT_ROL": "maker", "AGENT_STAGING": str(self.staging), "AGENT_CONTRATO": "contratos/oferta.schema.json",
                "AGENT_ARTEFACTOS_ESPERADOS": "oferta.json"}
        base.update(extra)
        return base

    def test_maker_con_artefacto_valido_no_bloquea(self) -> None:
        oferta_valida = json.loads((Path(__file__).resolve().parents[2] / "contratos" / "ejemplos" / "oferta.valido.json").read_text())
        (self.staging / "oferta.json").write_text(json.dumps(oferta_valida), encoding="utf-8")
        with mock.patch.dict(os.environ, self._env(), clear=True):
            self.assertIsNone(hook.manejar({"hook_event_name": "Stop", "stop_hook_active": False}))

    def test_maker_sin_artefacto_bloquea_la_primera_vez(self) -> None:
        with mock.patch.dict(os.environ, self._env(), clear=True):
            salida = hook.manejar({"hook_event_name": "Stop", "stop_hook_active": False})
        self.assertIsNotNone(salida)
        self.assertEqual(salida["decision"], "block")

    def test_maker_sin_artefacto_en_el_segundo_intento_deja_pasar_y_marca_invalido(self) -> None:
        with mock.patch.dict(os.environ, self._env(), clear=True):
            salida = hook.manejar({"hook_event_name": "Stop", "stop_hook_active": True})
        self.assertIsNone(salida)  # evita el bucle de Stop
        self.assertTrue((self.staging / "INVALIDO.json").is_file())

    def test_qa_sin_veredicto_bloquea(self) -> None:
        with mock.patch.dict(os.environ, self._env(AGENT_ROL="qa"), clear=True):
            salida = hook.manejar({"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "Listo."})
        self.assertIsNotNone(salida)

    def test_qa_con_veredicto_en_el_mensaje_no_bloquea(self) -> None:
        with mock.patch.dict(os.environ, self._env(AGENT_ROL="qa"), clear=True):
            salida = hook.manejar({"hook_event_name": "Stop", "stop_hook_active": False,
                                   "last_assistant_message": "Mi veredicto es PASS."})
        self.assertIsNone(salida)


if __name__ == "__main__":
    unittest.main()
