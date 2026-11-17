"""B0-14: watchdog real (Worker JS), latido detenido -> pausa + alerta por los dos canales, sin ruta de activación."""
from __future__ import annotations

import unittest

from scripts.b0 import infra as I


class PruebaB0_14(unittest.TestCase):
    def test_evaluar_b0_14_es_verde(self) -> None:
        r = I.evaluar_b0_14()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaNegativaSembrada(unittest.TestCase):
    def test_interpretar_detecta_pausa_global_ausente(self) -> None:
        ok, motivo = I._interpretar({"pausa_global": None, "llamadas_fetch": [
            "https://api.correo.ejemplo/enviar", "https://api.push.ejemplo/enviar"], "activar_status": 404})
        self.assertFalse(ok)
        self.assertIn("pausa_global", motivo)

    def test_interpretar_detecta_un_solo_canal(self) -> None:
        ok, motivo = I._interpretar({"pausa_global": "true", "llamadas_fetch": ["https://api.correo.ejemplo/enviar"],
                                     "activar_status": 404})
        self.assertFalse(ok)
        self.assertIn("llamadas_fetch", motivo)

    def test_interpretar_detecta_ruta_de_activacion(self) -> None:
        ok, motivo = I._interpretar({"pausa_global": "true", "llamadas_fetch": [
            "https://api.correo.ejemplo/enviar", "https://api.push.ejemplo/enviar"], "activar_status": 200})
        self.assertFalse(ok)
        self.assertIn("activar_status", motivo)


if __name__ == "__main__":
    unittest.main()
