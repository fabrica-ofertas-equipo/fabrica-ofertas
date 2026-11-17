"""Prueba del script de la prueba S-1 (docs/06 §8 ola 3): solo su construcción en DRY_RUN; la
corrida real (``--live``) es tarea del dueño/I1 en la ola 3, nunca de esta sesión."""
from __future__ import annotations

import unittest
from unittest import mock

from agentes import prueba_s1
from agentes.runner import ejecutar
from agentes.tipos import Modo


class PruebaS1DryRun(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)

    def test_espec_humo_es_valida_y_barata(self) -> None:
        espec = prueba_s1.espec_humo()
        self.assertEqual(espec.rol, "maker")
        self.assertLessEqual(espec.presupuesto.usd_centavos_max, 100)

    def test_dry_run_no_lanza_ningun_proceso(self) -> None:
        espec = prueba_s1.espec_humo()
        with mock.patch("subprocess.Popen", side_effect=AssertionError("DRY_RUN no debe lanzar procesos")):
            resultado = ejecutar(espec, modo=Modo.DRY_RUN)
        self.assertEqual(resultado.estado, "ok")

    def test_cli_dry_run_devuelve_0(self) -> None:
        self.assertEqual(prueba_s1.main([]), 0)


if __name__ == "__main__":
    unittest.main()
