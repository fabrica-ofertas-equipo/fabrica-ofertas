"""Pruebas de ``agentes.hooks._comun``: el envoltorio fail-closed (docs/09 §14.1)."""
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from agentes.hooks import _comun as comun


class PruebaEjecutar(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)

    def _correr(self, manejador, entrada: str) -> tuple[int, str]:
        err = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(entrada)), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                comun.ejecutar(manejador)
        return cm.exception.code, err.getvalue()

    def test_sin_opinion_sale_0(self) -> None:
        codigo, _ = self._correr(lambda datos: None, '{"a":1}')
        self.assertEqual(codigo, 0)

    def test_motivo_sale_2_con_el_motivo_en_stderr(self) -> None:
        codigo, err = self._correr(lambda datos: "motivo de prueba", '{"a":1}')
        self.assertEqual(codigo, 2)
        self.assertIn("motivo de prueba", err)

    def test_excepcion_del_manejador_sale_2(self) -> None:
        def explota(datos):
            raise RuntimeError("boom")
        codigo, err = self._correr(explota, '{"a":1}')
        self.assertEqual(codigo, 2)
        self.assertIn("RuntimeError", err)

    def test_json_invalido_sale_2(self) -> None:
        codigo, err = self._correr(lambda datos: None, "no es json")
        self.assertEqual(codigo, 2)
        self.assertIn("fail-closed", err)

    def test_entrada_no_es_un_objeto_sale_2(self) -> None:
        codigo, _ = self._correr(lambda datos: None, "[1,2,3]")
        self.assertEqual(codigo, 2)

    def test_redacta_secretos_antes_de_escribir(self) -> None:
        _, err = self._correr(lambda datos: "fuga: sk" + "_live_abcdefghijklmnop", '{"a":1}')
        self.assertNotIn("sk_live_abcdefghijklmnop", err)
        self.assertIn("****", err)


class PruebaEjecutarConSalida(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)

    def test_sin_salida_sale_0_sin_imprimir(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO('{"a":1}')), redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                comun.ejecutar_con_salida(lambda datos: None)
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(out.getvalue(), "")

    def test_con_salida_imprime_json_y_sale_0(self) -> None:
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO('{"a":1}')), redirect_stdout(out):
            with self.assertRaises(SystemExit) as cm:
                comun.ejecutar_con_salida(lambda datos: {"decision": "block", "reason": "x"})
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(json.loads(out.getvalue()), {"decision": "block", "reason": "x"})

    def test_excepcion_sale_2_aunque_use_salida_estructurada(self) -> None:
        err = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO('{"a":1}')), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                comun.ejecutar_con_salida(lambda datos: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertEqual(cm.exception.code, 2)


class PruebaClasificarHerramienta(unittest.TestCase):
    def test_lectura_conocida(self) -> None:
        self.assertEqual(comun.clasificar_herramienta("Read"), "lectura")
        self.assertEqual(comun.clasificar_herramienta("mcp__claude_ai_Meta_ADS__ads_get_ad_accounts"), "lectura")

    def test_desconocida_es_escritura(self) -> None:
        self.assertEqual(comun.clasificar_herramienta("mcp__servidor_nuevo__algo_jamas_visto"), "escritura")
        self.assertEqual(comun.clasificar_herramienta(""), "escritura")

    def test_neutra(self) -> None:
        self.assertEqual(comun.clasificar_herramienta("WebSearch"), "neutra")


if __name__ == "__main__":
    unittest.main()
