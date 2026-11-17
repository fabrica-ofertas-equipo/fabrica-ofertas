"""Ventana de la renovación diaria por mercado (dueño, 14-nov: el horario depende del mercado, no de Argentina)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("ofertas_que_pegan", SCRIPTS / "ofertas_que_pegan.py")
oqp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oqp)

ART = dt.timezone(dt.timedelta(hours=-3))


def a(h: int, m: int = 0, dia: int = 14) -> dt.datetime:
    return dt.datetime(2026, 11, dia, h, m, tzinfo=ART)


class TestVentana(unittest.TestCase):
    def test_espana_entra_a_la_manana_de_argentina(self) -> None:
        v = oqp.ventana("ES", a(8, 35))   # 12:35 Madrid → faltan 11,4 h para la 00:00 de Madrid (20:00 ART)
        self.assertTrue(v["en_ventana"])
        self.assertEqual(v["salida"], "2026-11-15T00:00:00+01:00")

    def test_espana_tarde_pasa_a_la_00_siguiente(self) -> None:
        v = oqp.ventana("ES", a(16, 35))  # faltan 3,4 h: no alcanza
        self.assertFalse(v["en_ventana"])
        self.assertIn("próxima ronda", v["ventana"])

    def test_mexico_no_entra_antes_de_las_11_art(self) -> None:
        self.assertFalse(oqp.ventana("MX", a(10, 35))["en_ventana"])   # faltan 16,4 h
        self.assertTrue(oqp.ventana("MX", a(12, 35))["en_ventana"])    # faltan 14,4 h

    def test_australia_se_produce_la_noche_anterior(self) -> None:
        # 00:00 de Sídney = 10:00 ART: a las 10:30 ART ya pasó; la ronda se produce a la noche de Argentina.
        self.assertFalse(oqp.ventana("AU", a(10, 35))["en_ventana"])
        self.assertTrue(oqp.ventana("AU", a(18, 35))["en_ventana"])

    def test_todo_mercado_cae_en_alguna_vuelta(self) -> None:
        vueltas = [a(h, 35) for h in range(8, 23, 2)]
        for mercado in oqp.ZONA:
            with self.subTest(mercado=mercado):
                self.assertTrue(any(oqp.ventana(mercado, t)["en_ventana"] for t in vueltas + [x + dt.timedelta(days=1) for x in vueltas]))

    def test_mercado_sin_zona(self) -> None:
        v = oqp.ventana("ZZ", a(9))
        self.assertFalse(v["en_ventana"])
        self.assertIn("sin zona", v["ventana"])


if __name__ == "__main__":
    unittest.main()
