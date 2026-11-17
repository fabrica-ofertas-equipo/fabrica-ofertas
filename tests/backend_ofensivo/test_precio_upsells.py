"""Pruebas del precio de upsells que aprende (backend-ofensivo/scripts/precio_upsells.py)."""
from __future__ import annotations

import datetime as dt
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "backend-ofensivo" / "scripts"))
import precio_upsells as P  # noqa: E402

AHORA = dt.datetime(2026, 11, 14, tzinfo=dt.timezone.utc)


def nuevo(aprend=None):
    est: dict = {}
    u = P.alta(est, aprend or {}, "Sesión", "Juegos", 399, "MXN", 319, 1, None, AHORA)
    return est, u


class TestPrecioUpsells(unittest.TestCase):
    def test_escalera_con_precios_de_mercado(self) -> None:
        _, u = nuevo()
        self.assertEqual([b["precio"] for b in u["brazos"]], [279.0, 339.0, 399.0, 479.0, 559.0])
        self.assertEqual(u["actual"], 399)
        self.assertEqual(P.precio_de_mercado(21 * 1.2, "USD"), 25.0)

    def test_lectura_por_deltas_al_precio_actual(self) -> None:
        _, u = nuevo()
        P.leer(u, 20, 2)
        P.leer(u, 35, 5)
        b = next(x for x in u["brazos"] if x["precio"] == 399)
        self.assertEqual((b["vistas"], b["aceptadas"]), (35, 5))
        with self.assertRaises(SystemExit):
            P.leer(u, 30, 5)

    def test_espera_la_tanda_y_despues_se_mueve_de_a_un_escalon(self) -> None:
        _, u = nuevo()
        P.leer(u, 10, 1)
        self.assertEqual(P.decidir(u, random.Random(1))["decision"], "MANTENER")
        P.leer(u, 40, 1)   # 40 vistas, 1 aceptada: flojo
        movidas = {P.decidir(u, random.Random(s)).get("precio_nuevo") for s in range(30)}
        self.assertTrue(movidas - {None} <= {339.0, 479.0}, "sin evidencia fuerte, solo escalones vecinos")

    def test_converge_al_que_mas_deja_por_vista_no_al_que_mas_aceptan(self) -> None:
        _, u = nuevo()
        verdad = {279.0: 0.20, 339.0: 0.17, 399.0: 0.15, 479.0: 0.09, 559.0: 0.05}   # por vista: 55.8, 57.6, 59.9, 43.1, 28.0
        rng, sim = random.Random(7), random.Random(11)
        total_v = total_a = 0
        for _ in range(120):
            v = 30
            a = sum(1 for _ in range(v) if sim.random() < verdad[u["actual"]])
            total_v += v; total_a += a
            P.leer(u, total_v, total_a)
            d = P.decidir(u, rng)
            if d["decision"] == "CAMBIAR":
                P.aplicado(u, d["precio_nuevo"], AHORA, d.get("consolidado", False))
            elif d["decision"] == "CONSOLIDADO":
                P.aplicado(u, u["actual"], AHORA, True)
        post = P.posteriores(u, random.Random(3))
        mejor = max(post, key=lambda p: p["p_mejor"])
        self.assertIn(mejor["precio"], (339.0, 399.0), "gana un precio de los que más dejan por vista")
        self.assertNotEqual(mejor["precio"], 279.0, "no el que más aceptan")

    def test_cambiar_producto_si_nadie_acepta_ni_barato(self) -> None:
        _, u = nuevo()
        u["brazos"][0]["vistas"] = 60
        u["ultimo_total"]["vistas"] = 60
        self.assertEqual(P.decidir(u, random.Random(1))["decision"], "CAMBIAR_PRODUCTO")

    def test_aprende_entre_ofertas(self) -> None:
        est, u = nuevo()
        u["brazos"][2].update(vistas=200, aceptadas=40)   # 20 % a 399 (razón 1,25)
        aprend = P.actualizar_aprendizaje(est)
        a, b = P.prior_para(aprend, 399 / 319, 1)
        self.assertAlmostEqual(a / (a + b), 0.2, places=1)
        self.assertLessEqual(a + b, P.PRIOR_PESO_MAX + 0.01, "lo aprendido pesa como mucho 20 vistas")


if __name__ == "__main__":
    unittest.main()
