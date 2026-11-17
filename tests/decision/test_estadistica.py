"""Pruebas de decision.estadistica: funciones especiales, intervalos, tamanos de muestra y errores de corte."""

import math
import unittest
from math import comb

from decision import estadistica as est


class TestFuncionesEspeciales(unittest.TestCase):
    def test_beta_formas_cerradas(self):
        self.assertAlmostEqual(est.beta_inc_reg(0.3, 1, 5), 1 - 0.7 ** 5, places=12)       # Beta(1,b)
        self.assertAlmostEqual(est.beta_inc_reg(0.3, 4, 1), 0.3 ** 4, places=12)           # Beta(a,1)
        self.assertAlmostEqual(est.beta_inc_reg(0.3, 2, 2), 3 * 0.09 - 2 * 0.027, places=12)
        self.assertEqual(est.beta_inc_reg(0.0, 2, 3), 0.0)
        self.assertEqual(est.beta_inc_reg(1.0, 2, 3), 1.0)

    def test_beta_relacion_con_binomial(self):
        n, k, p = 241, 5, 0.02
        suma = sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
        self.assertAlmostEqual(est.beta_inc_reg(1 - p, n - k, k + 1), suma, places=10)

    def test_gamma_forma_cerrada(self):
        self.assertAlmostEqual(est.gamma_inc_reg(3.0, 2.0), 1 - math.exp(-2) * (1 + 2 + 2), places=12)
        self.assertAlmostEqual(est.gamma_cdf(1.0, 1.0, 2.0), 1 - math.exp(-2.0), places=12)

    def test_ppf_inversa_de_cdf(self):
        for q in (0.025, 0.5, 0.975):
            x = est.beta_ppf(q, 6, 236)
            self.assertAlmostEqual(est.beta_inc_reg(x, 6, 236), q, places=10)
            y = est.gamma_ppf(q, 40.0, 3.0)
            self.assertAlmostEqual(est.gamma_cdf(y, 40.0, 3.0), q, places=10)

    def test_wilson_hilferty_cercano_al_exacto(self):
        for forma in (10.0, 100.0, 1000.0):
            exacto = est.gamma_ppf(0.1, forma, 2.0)
            self.assertLess(abs(est._gamma_ppf_rapida(0.1, forma, 2.0) / exacto - 1), 2e-3)


class TestPosteriores(unittest.TestCase):
    def test_prior_debil_y_actualizacion(self):
        prior = est.beta_desde_media_fuerza(0.02, 50)
        self.assertAlmostEqual(prior.a + prior.b, 50)
        post = est.actualizar_beta(prior, 3, 100)
        self.assertAlmostEqual(post.a, prior.a + 3)
        self.assertAlmostEqual(post.b, prior.b + 97)
        with self.assertRaises(ValueError):
            est.actualizar_beta(prior, 5, 3)

    def test_prob_cpa_menor_con_cpc_conocido(self):
        # Con muchos clics el CPC casi no tiene incertidumbre: P(CPA <= L) ~ P(conv >= CPC / L).
        conv = est.Beta(11, 489)
        lam = est.Gamma(100000.0, 100000.0 * 40.0)  # CPC 40 con varianza ~0
        p = est.prob_cpa_menor(conv, lam, 1500.0, nodos=3)
        self.assertAlmostEqual(p, conv.sf(40.0 / 1500.0), places=3)

    def test_prob_cpa_menor_monotona(self):
        conv, lam = est.Beta(10, 400), est.Gamma(400.0, 400.0 * 45.0)
        ps = [est.prob_cpa_menor(conv, lam, limite) for limite in (900.0, 1500.0, 2500.0, 5000.0)]
        self.assertEqual(ps, sorted(ps))
        self.assertEqual(est.prob_cpa_menor(conv, lam, 0.0), 0.0)

    def test_intervalo_cpa_contiene_la_mediana(self):
        conv, lam = est.Beta(12, 388), est.Gamma(400.0, 400.0 * 40.0)
        inf, sup = est.intervalo_cpa_minor(conv, lam, 0.90)
        self.assertLess(inf, est.cpa_mediano_minor(conv, lam))
        self.assertGreater(sup, est.cpa_mediano_minor(conv, lam))

    def test_prob_mejor_reproducible_y_suma_uno(self):
        post = [est.Beta(3, 97), est.Beta(10, 90), est.Beta(5, 95)]
        a, b = est.prob_mejor(post, semilla=7), est.prob_mejor(post, semilla=7)
        self.assertEqual(a, b)
        self.assertAlmostEqual(sum(a), 1.0)
        self.assertEqual(max(range(3), key=a.__getitem__), 1)

    def test_prob_mayor_a_mediana_de_hermanos(self):
        post = [est.Beta(30, 270), est.Beta(3, 297), est.Beta(4, 296), est.Beta(3, 297)]
        self.assertGreater(est.prob_mayor_a_mediana_hermanos(post, 0, 1), 0.99)
        self.assertLess(est.prob_mayor_a_mediana_hermanos(post, 1, 1), 0.6)

    def test_margen_por_clic_distingue_mercados(self):
        # A: conversion 5 % y contribucion 1.500 por compra; B: 2 % y 1.200. Mismo CPC.
        lam = est.Gamma(1000.0, 1000.0 * 40.0)
        p = est.prob_margen_por_clic_mayor(est.Beta(50, 950), lam, 1500.0, 0.0, est.Beta(20, 980), lam, 1200.0, 0.0, 3)
        self.assertGreater(p, 0.99)


class TestIntervalosExactos(unittest.TestCase):
    def test_clopper_pearson_nota_16(self):
        # Nota 16: 5 compras en 241 clics -> IC95 0,67 %-4,76 % (aprox.)
        inf, sup = est.intervalo_clopper_pearson(5, 241, 0.95)
        self.assertAlmostEqual(inf, 0.0067, delta=0.0005)
        self.assertAlmostEqual(sup, 0.0477, delta=0.0010)

    def test_clopper_pearson_extremos(self):
        inf, sup = est.intervalo_clopper_pearson(0, 100, 0.95)
        self.assertEqual(inf, 0.0)
        self.assertAlmostEqual(sup, 1 - 0.025 ** (1 / 100), places=8)

    def test_poisson_exacto(self):
        inf, sup = est.intervalo_poisson_exacto(0, 0.90)
        self.assertEqual(inf, 0.0)
        self.assertAlmostEqual(sup, -math.log(0.05), places=8)
        inf10, sup10 = est.intervalo_poisson_exacto(10, 0.90)
        self.assertAlmostEqual(inf10, 5.425, delta=0.01)
        self.assertAlmostEqual(sup10, 16.962, delta=0.01)

    def test_ic_cpa_poisson(self):
        # Ejemplo de F1: 10 pedidos, gasto 150 -> CPA 15, IC90 aprox. 8,8-27,6
        inf, sup = est.intervalo_cpa_poisson_minor(15000.0, 10, 0.90)
        self.assertAlmostEqual(inf / 100, 8.84, delta=0.1)
        self.assertAlmostEqual(sup / 100, 27.6, delta=0.2)
        self.assertEqual(est.intervalo_cpa_poisson_minor(15000.0, 0, 0.90)[1], math.inf)


class TestErroresDeCorte(unittest.TestCase):
    def test_corte_a_10_usd_mata_ganador_54_por_ciento(self):
        # Ganador con CPA 16,2 USD (p. ej. 0,6 x un equilibrio de 27 USD): P(0 ventas con 10 USD) ~ 54 %.
        self.assertAlmostEqual(est.prob_sin_compras_poisson(1000, 1620), 0.54, delta=0.005)

    def test_nota_12_cpa_6_5_y_10_usd(self):
        self.assertAlmostEqual(est.prob_sin_compras_poisson(1000, 650), 0.215, delta=0.002)

    def test_k_corte_equilibrio(self):
        self.assertAlmostEqual(est.prob_falso_descarte_por_corte(3, 1.0), math.exp(-3))
        self.assertAlmostEqual(est.prob_falso_descarte_por_corte(3, 0.6), math.exp(-5))

    def test_gasto_minimo_para_error(self):
        g = est.gasto_minimo_para_error(1620.0, 0.05)
        self.assertAlmostEqual(g, 1620 * math.log(20), places=6)
        self.assertAlmostEqual(est.prob_sin_compras_poisson(g, 1620.0), 0.05, places=9)

    def test_cascada(self):
        self.assertAlmostEqual(est.prob_descarte_en_cascada([0.2, 0.2, 0.2]), 1 - 0.8 ** 3)
        self.assertEqual(est.prob_descarte_en_cascada([]), 0.0)

    def test_binomial_vs_poisson_coinciden_con_conversion_baja(self):
        self.assertAlmostEqual(est.prob_sin_compras_binomial(300, 0.01), math.exp(-3), delta=0.01)


class TestTamanosDeMuestra(unittest.TestCase):
    def test_nota_16_2400_clics(self):
        n = est.n_precision_relativa(0.025, 0.25, 0.95)
        self.assertTrue(2390 <= n <= 2400, n)
        self.assertAlmostEqual(n * 0.025, 60, delta=1)
        self.assertAlmostEqual(n * 0.31, 740, delta=5)
        self.assertAlmostEqual(n * 0.51, 1220, delta=6)

    def test_contraste_y_mde_son_inversos(self):
        n = est.n_contraste_unilateral(0.025, 0.0375, 0.05, 0.80)
        self.assertAlmostEqual(est.mde_relativo(n, 0.025, 0.05, 0.80), 0.5, delta=0.01)
        self.assertGreater(est.mde_relativo(200, 0.025, 0.05, 0.8), est.mde_relativo(2400, 0.025, 0.05, 0.8))

    def test_dos_proporciones_simetrica_y_decreciente(self):
        a = est.n_dos_proporciones(0.02, 0.03, 0.05, 0.8)
        self.assertEqual(a, est.n_dos_proporciones(0.03, 0.02, 0.05, 0.8))
        self.assertLess(est.n_dos_proporciones(0.02, 0.04, 0.05, 0.8), a)
        self.assertLess(est.n_dos_proporciones(0.02, 0.03, 0.05, 0.8, unilateral=True), a)

    def test_tabla_nivel_2_de_la_nota_16(self):
        # Prior uniforme; abandonar si P(conv > c*) <= 5 %; seguir si >= 80 %.
        prior = est.Beta(1, 1)
        esperado_matar = {500: (4, 8), 1000: (12, 20), 1500: (20, 33), 2000: (29, 47)}
        esperado_seguir = {500: (13, 18), 1000: (24, 35), 1500: (35, 51), 2000: (45, 66)}
        for n, (m2, m3) in esperado_matar.items():
            self.assertEqual(est.umbral_compras_matar(n, 0.02, 0.05, prior), m2, n)
            self.assertEqual(est.umbral_compras_matar(n, 0.03, 0.05, prior), m3, n)
        for n, (s2, s3) in esperado_seguir.items():
            self.assertEqual(est.umbral_compras_seguir(n, 0.02, 0.80, prior), s2, n)
            self.assertEqual(est.umbral_compras_seguir(n, 0.03, 0.80, prior), s3, n)

    def test_clics_para_descartar_sin_compras(self):
        n = est.clics_para_descartar_sin_compras(0.02, 0.05, est.Beta(1, 1))
        self.assertEqual(est.Beta(1, 1 + n).sf(0.02) <= 0.05 < est.Beta(1, n).sf(0.02), True)
        self.assertTrue(140 <= n <= 155, n)  # ~ ln(20)/0,02


if __name__ == "__main__":
    unittest.main()
