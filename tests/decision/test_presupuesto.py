"""Pruebas de decision.presupuesto: economia por pedido, plan de celda, aprendizaje de Meta y sensibilidad."""

import math
import unittest

from decision import presupuesto as pre


def precio(**kw):
    base = dict(moneda="USD", precio_bruto_minor=2700, tasa_iva=0.0, comision_pct=0.029, comision_fija_minor=30,
                stripe_tax_pct=0.0, stripe_tax_fijo_minor=0, tasa_bump=0.10, precio_bump_minor=900,
                tasa_reembolso=0.07, tasa_disputa=0.005, tarifa_disputa_minor=1500, costo_var_minor=20,
                tarifa_meta_pct=0.0, factor_objetivo=0.6)
    base.update(kw)
    return pre.ParametrosPrecio(**base)


class TestEconomia(unittest.TestCase):
    def test_vector_de_d3(self):
        e = pre.economia_por_pedido(precio())
        self.assertEqual(e.aov_bruto_minor, 2790)
        self.assertAlmostEqual(e.cpa_equilibrio_minor, 2442, delta=1)       # CPA_BE ~ 24,4
        self.assertAlmostEqual(e.cpa_objetivo_minor, round(0.6 * 2442), delta=1)
        self.assertAlmostEqual(e.roas_bruto_equilibrio, 2790 / 2442, places=3)

    def test_vector_de_f1(self):
        e = pre.economia_por_pedido(precio(precio_bruto_minor=1700, comision_pct=0.044, tasa_bump=0.30, precio_bump_minor=700))
        self.assertEqual(e.aov_bruto_minor, 1910)
        self.assertAlmostEqual(e.contribucion_minor, 1625, delta=1)         # MC 16,25
        self.assertAlmostEqual(e.cpa_objetivo_minor, 975, delta=1)

    def test_iva_y_tarifa_meta_caso_italia_nota_16(self):
        e = pre.economia_por_pedido(precio(
            precio_bruto_minor=1728, tasa_iva=0.22, comision_pct=0.054, stripe_tax_pct=0.005, tasa_bump=0.0,
            precio_bump_minor=0, tasa_reembolso=0.08, tasa_disputa=0.006, costo_var_minor=0, tarifa_meta_pct=0.03))
        self.assertAlmostEqual(e.iva_minor, 312, delta=1)
        self.assertAlmostEqual(e.cpa_equilibrio_minor / 100, 11.6, delta=0.15)       # nota 16: ~11,6
        self.assertAlmostEqual(e.cpa_equilibrio_visto_minor / 100, 11.3, delta=0.2)  # visto en Ads Manager

    def test_el_reembolso_no_devuelve_la_comision(self):
        sin = pre.economia_por_pedido(precio(tasa_reembolso=0.0, tasa_disputa=0.0))
        con = pre.economia_por_pedido(precio(tasa_reembolso=0.10, tasa_disputa=0.0))
        # perdida = r * neto (no r * (neto - comision)): 10 % de 2.790 = 279
        self.assertAlmostEqual(sin.contribucion_minor - con.contribucion_minor, 279, delta=1)

    def test_stripe_tax_fijo_pesa_mas_en_tickets_chicos(self):
        a = pre.economia_por_pedido(precio(precio_bruto_minor=700, tasa_bump=0.0, stripe_tax_fijo_minor=50))
        b = pre.economia_por_pedido(precio(precio_bruto_minor=2700, tasa_bump=0.0, stripe_tax_fijo_minor=50))
        self.assertGreater(a.stripe_tax_minor / a.aov_bruto_minor, b.stripe_tax_minor / b.aov_bruto_minor)

    def test_validaciones(self):
        with self.assertRaises(ValueError):
            precio(precio_bruto_minor=27.5)          # dinero debe ser int
        with self.assertRaises(ValueError):
            precio(tasa_reembolso=1.2)
        with self.assertRaises(ValueError):
            precio(factor_objetivo=0.0)

    def test_sin_margen_no_hay_cpa_de_equilibrio(self):
        e = pre.economia_por_pedido(precio(precio_bruto_minor=100, tasa_bump=0.0, costo_var_minor=500))
        self.assertEqual(e.cpa_equilibrio_minor, 0)
        self.assertFalse(e.margen_positivo)


class TestCostos(unittest.TestCase):
    def test_cpc_cpm_ctr_conv(self):
        cpc = pre.cpc_desde_cpm_ctr(666.0, 0.013)           # CPM 6,66 USD, CTR 1,3 % -> CPC ~0,51
        self.assertAlmostEqual(cpc / 100, 0.51, delta=0.005)
        self.assertAlmostEqual(pre.cpa_desde_cpc_conv(51.0, 0.02), 2550.0)
        self.assertEqual(pre.cpa_desde_cpc_conv(51.0, 0.0), math.inf)
        self.assertAlmostEqual(pre.conversion_equilibrio(51.0, 1148.0), 0.0444, places=3)  # ~4,4 % (nota 16, PL base)

    def test_embudo(self):
        self.assertAlmostEqual(pre.conversion_desde_embudo(0.7, 0.03, 0.20), 0.0042)
        with self.assertRaises(ValueError):
            pre.conversion_desde_embudo(1.2, 0.1, 0.1)


class TestPlanCelda(unittest.TestCase):
    def entrada(self, **kw):
        base = dict(moneda="USD", cpa_equilibrio_visto_minor=1478, cpa_objetivo_minor=887, cpc_minor=56.0,
                    conv_plausible=0.02, alfa=0.05, potencia=0.80, k_min_matar=2.0, precision_relativa=0.25,
                    prior_conv_media=0.02, prior_conv_fuerza_clics=50.0, n_dec=15, tarifa_meta_pct=0.03,
                    n_celdas=1, tope_gasto_celda_minor=None)
        base.update(kw)
        return pre.EntradaPlan(**base)

    def test_sin_tope_no_se_autoriza_gasto(self):
        plan = pre.plan_celda(self.entrada())
        self.assertFalse(plan.autorizado)
        self.assertIsNone(plan.cabe_en_tope)
        self.assertTrue(any("limites.yaml" in a for a in plan.avisos))

    def test_con_tope_suficiente_y_insuficiente(self):
        base = pre.plan_celda(self.entrada())
        ok = pre.plan_celda(self.entrada(tope_gasto_celda_minor=base.gasto_recomendado_minor + 1))
        self.assertTrue(ok.autorizado and ok.cabe_en_tope)
        corto = pre.plan_celda(self.entrada(tope_gasto_celda_minor=base.gasto_recomendado_minor - 1))
        self.assertFalse(corto.autorizado)
        self.assertFalse(corto.cabe_en_tope)

    def test_descartar_cuesta_aprox_ln_1_sobre_alfa_veces_el_equilibrio(self):
        # Con un prior casi plano y sin piso: ~ ln(20) x CPA_BE = 3,0 x 14,78 = 44 USD
        plan = pre.plan_celda(self.entrada(prior_conv_media=0.5, prior_conv_fuerza_clics=2.0, k_min_matar=0.1))
        self.assertAlmostEqual(plan.gasto_descartar_minor / 1478, math.log(20), delta=0.35)

    def test_el_piso_k_min_protege_del_prior(self):
        # Prior que ya espera conversion baja: sin piso se descartaria con muy poco gasto.
        plan = pre.plan_celda(self.entrada(k_min_matar=2.0))
        self.assertGreaterEqual(plan.gasto_descartar_minor, 2 * 1478)

    def test_confirmar_cuesta_mas_que_descartar(self):
        plan = pre.plan_celda(self.entrada())
        self.assertGreater(plan.clics_confirmar_ganador, plan.clics_descartar_sin_compras)
        self.assertEqual(plan.gasto_recomendado_minor, max(plan.gasto_descartar_minor, plan.gasto_confirmar_minor))

    def test_total_incluye_celdas_y_tarifa_meta(self):
        uno = pre.plan_celda(self.entrada(n_celdas=1))
        cuatro = pre.plan_celda(self.entrada(n_celdas=4))
        self.assertAlmostEqual(cuatro.gasto_total_minor / uno.gasto_total_minor, 4.0, places=2)
        self.assertAlmostEqual(uno.gasto_total_minor / uno.gasto_recomendado_minor, 1.03, places=2)

    def test_escenario_central_que_pierde_avisa(self):
        plan = pre.plan_celda(self.entrada(conv_plausible=0.005))   # CPA esperado 112 >> 14,78
        self.assertTrue(any("pierde dinero" in a for a in plan.avisos))

    def test_cpc_mayor_que_equilibrio_es_error(self):
        with self.assertRaises(ValueError):
            pre.plan_celda(self.entrada(cpc_minor=2000.0))
        with self.assertRaises(ValueError):
            pre.plan_celda(self.entrada(cpa_equilibrio_visto_minor=0))


class TestPrecisionYSensibilidad(unittest.TestCase):
    def test_nota_16(self):
        clics, compras, gasto = pre.presupuesto_precision(0.025, 0.25, 0.95, 31.0)
        self.assertTrue(2390 <= clics <= 2400)
        self.assertEqual(compras, 60)
        self.assertAlmostEqual(gasto / 100, 740, delta=6)
        self.assertAlmostEqual(pre.presupuesto_precision(0.025, 0.25, 0.95, 51.0)[2] / 100, 1220, delta=8)

    def test_tabla_sensibilidad_monotona(self):
        filas = pre.tabla_sensibilidad(1478, 0.6, [31.0, 51.0, 85.0], [0.01, 0.02, 0.04], 0.05, 0.8, 0.02, 50.0)
        self.assertEqual(len(filas), 9)
        por_cpc = {}
        for f in filas:
            por_cpc.setdefault(f["cpc_minor"], f)
        # a mayor CPC, mayor conversion de equilibrio y mas gasto para descartar
        # descartar cuesta ~ ln(1/alfa) x CPA_BE sin importar el CPC (se necesitan menos clics si el CPC es mayor)
        gastos = [por_cpc[c]["gasto_descartar_minor"] for c in (31.0, 51.0, 85.0)]
        self.assertTrue(all(g <= 3.2 * 1478 for g in gastos))
        # confirmar un ganador cuesta menos clics pero similar gasto relativo al equilibrio
        confirmar = [por_cpc[c]["clics_confirmar"] for c in (31.0, 51.0, 85.0)]
        self.assertEqual(confirmar, sorted(confirmar, reverse=True))
        # la razon CPA/BE baja al subir la conversion
        fila_cpc = [f for f in filas if f["cpc_minor"] == 51.0]
        razones = [f["razon_cpa_sobre_be"] for f in fila_cpc]
        self.assertEqual(razones, sorted(razones, reverse=True))

    def test_max_celdas(self):
        self.assertEqual(pre.max_celdas(10000, 3000), 3)
        with self.assertRaises(ValueError):
            pre.max_celdas(10000, 0)


class TestAprendizajeMeta(unittest.TestCase):
    def test_eventos_y_presupuesto(self):
        self.assertAlmostEqual(pre.eventos_semanales_esperados(3000, 1500), 14.0)
        self.assertAlmostEqual(pre.presupuesto_diario_para_aprendizaje(1500, 50), 50 / 7 * 1500)

    def test_evento_de_optimizacion(self):
        # necesario = 50/7*1200 = 8.571; la mitad = 4.286
        self.assertEqual(pre.evento_optimizacion_recomendado(5000, 1200, 50, 0.5), "PURCHASE")
        self.assertEqual(pre.evento_optimizacion_recomendado(1920, 1200, 50, 0.5), "INITIATE_CHECKOUT")


class TestMercados(unittest.TestCase):
    def test_costo_comparacion(self):
        total = pre.costo_comparacion_mercados(2, 1000, [51.0, 56.0], [0.0, 0.03])
        self.assertEqual(total, round(1000 * 51.0 + 1000 * 56.0 * 1.03))
        with self.assertRaises(ValueError):
            pre.costo_comparacion_mercados(2, 1000, [51.0], [0.0, 0.03])

    def test_clics_para_distinguir(self):
        self.assertGreater(pre.clics_para_distinguir_mercados(0.02, 0.025, 0.1, 0.8),
                           pre.clics_para_distinguir_mercados(0.02, 0.04, 0.1, 0.8))


if __name__ == "__main__":
    unittest.main()
