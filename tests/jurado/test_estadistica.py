"""Pruebas de scripts/jurado/estadistica.py: AUC, DeLong, azar, Brier, Wilson, kappa y bootstrap (sin red)."""
from __future__ import annotations

import math
import random
import unittest

from scripts.jurado import estadistica as est


def _auc_bruto(puntajes, etiquetas):
    pos = [p for p, e in zip(puntajes, etiquetas) if e]
    neg = [p for p, e in zip(puntajes, etiquetas) if not e]
    return sum((1 if a > b else 0.5 if a == b else 0) for a in pos for b in neg) / (len(pos) * len(neg))


class PruebaAuc(unittest.TestCase):
    def test_perfecto_azar_e_invertido(self):
        y = [0, 0, 0, 1, 1, 1]
        self.assertEqual(est.auc([1, 2, 3, 4, 5, 6], y), 1.0)
        self.assertEqual(est.auc([6, 5, 4, 3, 2, 1], y), 0.0)
        self.assertEqual(est.auc([1, 1, 1, 1, 1, 1], y), 0.5)

    def test_coincide_con_el_calculo_bruto_con_muchos_empates(self):
        rng = random.Random(1)
        for _ in range(20):
            y = [1 if rng.random() < 0.35 else 0 for _ in range(50)]
            if len(set(y)) < 2:
                continue
            s = [round(rng.random() + 0.5 * e, 1) for e in y]
            self.assertAlmostEqual(est.auc(s, y), _auc_bruto(s, y), places=9)

    def test_una_sola_clase_devuelve_none_no_un_numero(self):
        self.assertIsNone(est.auc([1, 2, 3], [1, 1, 1]))
        self.assertIsNone(est.auc_con_ic([1, 2, 3], [0, 0, 0]))
        self.assertIsNone(est.p_contra_azar([1, 2, 3], [0, 0, 0], 1))

    def test_largos_distintos_es_error(self):
        with self.assertRaises(ValueError):
            est.auc([1, 2], [1])


class PruebaDeLong(unittest.TestCase):
    def test_varianza_coincide_con_el_calculo_directo(self):
        rng = random.Random(5)
        y = [1 if rng.random() < 0.3 else 0 for _ in range(80)]
        s = [round(rng.random() + 0.4 * e, 1) for e in y]
        r = est.auc_con_ic(s, y)
        pos = [p for p, e in zip(s, y) if e]
        neg = [p for p, e in zip(s, y) if not e]
        v10 = [sum((1 if a > b else 0.5 if a == b else 0) for b in neg) / len(neg) for a in pos]
        v01 = [sum((1 if a > b else 0.5 if a == b else 0) for a in pos) / len(pos) for b in neg]

        def var(v):
            m = sum(v) / len(v)
            return sum((x - m) ** 2 for x in v) / (len(v) - 1)

        esperado = var(v10) / len(pos) + var(v01) / len(neg)
        self.assertAlmostEqual(r["se"] ** 2, esperado, places=10)
        self.assertLessEqual(r["ic95"][0], r["auc"])
        self.assertGreaterEqual(r["ic95"][1], r["auc"])

    def test_ic_none_con_menos_de_dos_casos_por_clase(self):
        self.assertIsNone(est.auc_con_ic([1, 2, 3], [1, 0, 0])["ic95"])

    def test_comparacion_pareada_detecta_al_mejor_y_no_inventa_diferencias(self):
        rng = random.Random(8)
        y = [1 if rng.random() < 0.3 else 0 for _ in range(200)]
        bueno = [e + rng.random() for e in y]
        malo = [rng.random() for _ in y]
        r = est.comparar_auc_pareado(bueno, malo, y)
        self.assertGreater(r["diferencia"], 0.3)
        self.assertLess(r["p_unilateral"], 0.001)
        igual = est.comparar_auc_pareado(bueno, list(bueno), y)
        self.assertAlmostEqual(igual["diferencia"], 0.0)
        self.assertAlmostEqual(igual["p_unilateral"], 0.5)


class PruebaAzar(unittest.TestCase):
    def test_p_contra_azar_es_reproducible_y_discrimina(self):
        rng = random.Random(3)
        y = [1 if rng.random() < 0.3 else 0 for _ in range(150)]
        bueno = [e + rng.random() for e in y]
        ruido = [rng.random() for _ in y]
        self.assertEqual(est.p_contra_azar(bueno, y, 9, 300), est.p_contra_azar(bueno, y, 9, 300))
        self.assertLess(est.p_contra_azar(bueno, y, 9, 300), 0.01)
        self.assertGreater(est.p_contra_azar(ruido, y, 9, 300), 0.05)


class PruebaMedidas(unittest.TestCase):
    def test_brier(self):
        self.assertEqual(est.brier([1, 0, 1], [1, 0, 1]), 0.0)
        self.assertEqual(est.brier([0.5] * 4, [1, 0, 1, 0]), 0.25)
        self.assertEqual(est.brier([0, 1], [1, 0]), 1.0)
        self.assertAlmostEqual(est.brier_prevalencia([1, 0, 0, 0]), 0.1875)
        self.assertIsNone(est.brier([], []))

    def test_wilson_conocido(self):
        lo, hi = est.wilson(7, 10)
        self.assertAlmostEqual(lo, 0.3968, places=3)
        self.assertAlmostEqual(hi, 0.8922, places=3)
        self.assertAlmostEqual(est.wilson(0, 10)[0], 0.0)
        self.assertAlmostEqual(est.wilson(10, 10)[1], 1.0)
        self.assertIsNone(est.wilson(0, 0))

    def test_kappa_fleiss(self):
        self.assertAlmostEqual(est.kappa_fleiss_binario([10, 0, 10, 0], 10), 1.0)
        self.assertLess(abs(est.kappa_fleiss_binario([5, 5, 5, 5], 10)), 0.2)
        self.assertIsNone(est.kappa_fleiss_binario([10, 10, 10], 10))  # todos «sí»: no definido
        self.assertIsNone(est.kappa_fleiss_binario([], 10))

    def test_bootstrap_de_puestos_es_determinista_y_ordenado(self):
        # 3 piezas claramente distintas votadas por 6 avatares
        matriz = [[(1, 9), (1, 5), (0, 1)] for _ in range(6)]
        a = est.rangos_bootstrap(matriz, 4, 200)
        b = est.rangos_bootstrap(matriz, 4, 200)
        self.assertEqual(a, b)
        self.assertEqual([x["p50"] for x in a], [1.0, 2.0, 3.0])
        self.assertEqual(a[2], {"p05": 3.0, "p50": 3.0, "p95": 3.0})
        self.assertLessEqual(a[0]["p95"], 2.0)

    def test_normal_cdf(self):
        self.assertAlmostEqual(est.normal_cdf(0), 0.5)
        self.assertTrue(math.isclose(est.normal_cdf(1.959964), 0.975, abs_tol=1e-4))


if __name__ == "__main__":
    unittest.main()
