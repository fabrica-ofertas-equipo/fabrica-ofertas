"""B0-11: landing.validar pasa el ejemplo y falla el 100% de las 12 mutaciones (8 base + 4 complementarias)."""
from __future__ import annotations

import unittest

from scripts.b0 import landing as L


class PruebaB0_11(unittest.TestCase):
    def test_evaluar_b0_11_es_verde(self) -> None:
        r = L.evaluar_b0_11()
        self.assertEqual("verde", r.estado, r.motivo)
        self.assertIn("12/12", r.motivo)


class PruebaNegativaSembrada(unittest.TestCase):
    """Si una mutación dejara de disparar su regla (defecto real), ``evaluar_b0_11`` debe salir ROJO."""

    def test_si_landing_validar_deja_de_detectar_una_mutacion_el_criterio_sale_rojo(self) -> None:
        from unittest import mock

        from landing import validar as Val

        original = Val.validar_sitio
        with mock.patch.object(Val, "validar_sitio", side_effect=lambda ruta, **kw: [] if "ML-04" in str(ruta) else original(ruta, **kw)):
            r = L.evaluar_b0_11()
        self.assertEqual("rojo", r.estado)
        self.assertIn("ML-04", r.motivo)


if __name__ == "__main__":
    unittest.main()
