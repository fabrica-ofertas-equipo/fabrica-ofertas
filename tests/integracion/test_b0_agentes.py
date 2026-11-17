"""B0-08: agentes.runner (10 casos FIXTURE), agentes.sonda_hooks (100% exit 2), entorno sin claves."""
from __future__ import annotations

import unittest

from scripts.b0 import agentes as A


class PruebaB0_08(unittest.TestCase):
    def test_evaluar_b0_08_es_verde(self) -> None:
        r = A.evaluar_b0_08()
        self.assertEqual("verde", r.estado, r.motivo)

    def test_entorno_sin_claves_prohibidas(self) -> None:
        ok, motivo = A._entorno_sin_claves_prohibidas()
        self.assertTrue(ok, motivo)
        self.assertIn("ninguna llegó al hijo", motivo)


class PruebaNegativaSembrada(unittest.TestCase):
    """Siembra un fallo en la COMPARACIÓN (no en el componente real) y confirma que el criterio sale ROJO."""

    def test_comparar_resultado_detecta_estado_distinto(self) -> None:
        class FalsoResultado:
            estado = "ok"
            errores: list[str] = []
            artefactos: list[str] = []

        ok, motivo = A._comparar_resultado(FalsoResultado(), {"estado": "invalido"})
        self.assertFalse(ok)
        self.assertIn("estado=", motivo)

    def test_comparar_resultado_detecta_artefactos_de_mas(self) -> None:
        class FalsoResultado:
            estado = "ok"
            errores: list[str] = []
            artefactos = [1, 2]

        ok, motivo = A._comparar_resultado(FalsoResultado(), {"estado": "ok", "artefactos_cuenta": 1})
        self.assertFalse(ok)
        self.assertIn("artefactos_cuenta", motivo)


if __name__ == "__main__":
    unittest.main()
