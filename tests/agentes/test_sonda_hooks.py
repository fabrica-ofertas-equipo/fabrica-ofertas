"""Prueba de integración de ``agentes.sonda_hooks``: el 100 % del banco debe dar ``exit 2`` (criterio B0-08)."""
from __future__ import annotations

import unittest
from unittest import mock

from agentes import sonda_hooks


class PruebaBase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)


class PruebaSondaHooks(PruebaBase):
    def test_banco_completo_da_exit_2_en_todos_los_casos(self) -> None:
        resumen = sonda_hooks.correr()
        fallidos = {n: c for n, c in resumen["casos"].items() if not c["ok"]}
        self.assertEqual(fallidos, {}, f"casos que NO dieron exit 2: {fallidos}")
        self.assertTrue(resumen["ok"])

    def test_el_banco_tiene_al_menos_diez_casos(self) -> None:
        self.assertGreaterEqual(len(sonda_hooks.casos()), 10)

    def test_cada_hook_tiene_al_menos_un_caso(self) -> None:
        hooks_cubiertos = {c.hook for c in sonda_hooks.casos()}
        self.assertEqual(hooks_cubiertos, {"pretooluse_gasto.py", "pretooluse_activacion.py", "pretooluse_bash.py"})


if __name__ == "__main__":
    unittest.main()
