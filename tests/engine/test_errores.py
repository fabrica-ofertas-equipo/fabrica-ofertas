"""Pruebas de ``engine.errores``: jerarquía tipada y códigos de salida (convenciones §8)."""
from __future__ import annotations

import unittest

from engine import errores
from engine.errores import (
    ErrorBloqueado, ErrorExterno, ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion, ParametroFaltante, codigo_de_excepcion,
)
from tests.engine.apoyo import PruebaBase


class PruebaErrores(PruebaBase):
    """Cada error lleva su código de salida; el resto sale con 1."""

    def test_codigos_de_salida_de_las_cinco_subclases(self) -> None:
        esperados = {ErrorUso: 2, ErrorValidacion: 3, ErrorBloqueado: 4, ErrorLimite: 5, ErrorExterno: 6}
        for clase, codigo in esperados.items():
            with self.subTest(clase=clase.__name__):
                self.assertTrue(issubclass(clase, ErrorFabrica))
                self.assertEqual(clase("x").codigo_salida, codigo)

    def test_base_es_error_interno_uno(self) -> None:
        self.assertEqual(ErrorFabrica("x").codigo_salida, 1)

    def test_parametro_faltante_es_un_error_de_limite_con_codigo_cinco(self) -> None:
        exc = ParametroFaltante("infra.x", "sin valor")
        self.assertIsInstance(exc, ErrorLimite)
        self.assertEqual(exc.codigo_salida, 5)
        self.assertEqual(exc.clave, "infra.x")
        self.assertIn("infra.x", str(exc))

    def test_detalle_se_copia_y_no_comparte_estado(self) -> None:
        origen = {"a": 1}
        exc = ErrorLimite("m", detalle=origen)
        origen["a"] = 2
        self.assertEqual(exc.detalle, {"a": 1})
        self.assertEqual(ErrorLimite("m").detalle, {})

    def test_codigo_de_excepcion(self) -> None:
        self.assertEqual(codigo_de_excepcion(ErrorBloqueado("x")), 4)
        self.assertEqual(codigo_de_excepcion(ValueError("x")), 1)

    def test_constantes_de_salida_cubren_cero_a_seis(self) -> None:
        self.assertEqual(
            [errores.SALIDA_OK, errores.SALIDA_INTERNO, errores.SALIDA_USO, errores.SALIDA_VALIDACION, errores.SALIDA_BLOQUEADO,
             errores.SALIDA_LIMITE, errores.SALIDA_EXTERNO],
            [0, 1, 2, 3, 4, 5, 6],
        )


if __name__ == "__main__":
    unittest.main()
