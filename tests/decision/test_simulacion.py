"""Pruebas de decision.simulacion: versiones cortas (con semilla y tolerancias explicitas) de las simulaciones
Monte Carlo que validan las garantias de las reglas. Las corridas largas (2.000+) se ejecutan con
`python3 -m decision.simulacion` y sus resultados estan en docs/08-protocolo-estadistico-del-testeo.md."""

import unittest

from decision import simulacion as sim
from decision.reglas import LimitesCelda

CORRIDAS = 160
SEMILLA = 20261106


class TestSimulacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.par = sim.parametros_referencia()
        cls.lim = LimitesCelda(sim.CONFIG_REFERENCIA.tope_gasto_minor)
        cls.res = {e.nombre[0]: sim.simular_escenario(e, cls.par, cls.lim, sim.CONFIG_REFERENCIA, CORRIDAS, SEMILLA)
                   for e in sim.ESCENARIOS_REFERENCIA}

    def test_hay_al_menos_cuatro_escenarios_de_cpc_y_conversion(self):
        self.assertGreaterEqual(len(sim.ESCENARIOS_REFERENCIA), 4)
        self.assertGreaterEqual(len({e.cpc_minor for e in sim.ESCENARIOS_REFERENCIA}), 4)
        self.assertGreaterEqual(len({round(e.conv, 4) for e in sim.ESCENARIOS_REFERENCIA}), 4)

    def test_ganador_fuerte_casi_nunca_se_descarta_y_casi_siempre_se_escala(self):
        r = self.res["A"]       # CPA = 0,45 x equilibrio
        self.assertLessEqual(r.p_matar, 0.04)          # real ~0,1 %; tolerancia 4 %
        self.assertGreaterEqual(r.p_escalar, 0.88)     # real ~96 %

    def test_ganador_en_objetivo_se_descarta_menos_del_8_por_ciento(self):
        r = self.res["B"]       # CPA = objetivo; real ~2 % descartado (la regla ingenua a 10 USD lo haria ~33 %)
        self.assertLessEqual(r.p_matar, 0.08)
        self.assertGreater(r.p_escalar, 0.40)

    def test_perdedor_moderado_no_se_escala(self):
        r = self.res["E"]       # CPA = 1,5 x equilibrio
        self.assertLessEqual(r.p_escalar, 0.03)        # real ~0,2 %
        self.assertGreaterEqual(r.p_matar, 0.60)       # real ~79 %

    def test_perdedor_severo_se_mata_rapido_y_barato(self):
        r = self.res["F"]       # CPA = 4,7 x equilibrio
        self.assertGreaterEqual(r.p_matar, 0.97)
        self.assertEqual(r.p_escalar, 0.0)
        self.assertLessEqual(r.gasto_medio_minor, 9000)           # real ~52 USD, tope 225
        self.assertLess(r.gasto_medio_minor, 0.5 * self.lim.tope_gasto_celda_minor)

    def test_gasto_nunca_supera_el_tope(self):
        e = sim.ESCENARIOS_REFERENCIA[3]
        for i in range(60):
            r = sim.simular_corrida(e, self.par, self.lim, sim.CONFIG_REFERENCIA, 1000 + i)
            self.assertLessEqual(r.gasto_minor, self.lim.tope_gasto_celda_minor)

    def test_sin_tope_no_se_gasta_nada(self):
        r = sim.simular_corrida(sim.ESCENARIOS_REFERENCIA[0], self.par, LimitesCelda(None), sim.CONFIG_REFERENCIA, 5)
        self.assertEqual(r.accion.value, "BLOQUEADO")
        self.assertEqual(r.gasto_minor, 0)

    def test_reproducible_con_la_misma_semilla(self):
        e = sim.ESCENARIOS_REFERENCIA[2]
        a = sim.simular_escenario(e, self.par, self.lim, sim.CONFIG_REFERENCIA, 40, 99)
        b = sim.simular_escenario(e, self.par, self.lim, sim.CONFIG_REFERENCIA, 40, 99)
        self.assertEqual(a, b)

    def test_curva_operativa_monotona(self):
        curva = sim.curva_operativa([0.5, 1.0, 2.0], 40.0, self.par, self.lim, sim.CONFIG_REFERENCIA, 120, SEMILLA)
        matar = [c.p_matar for c in curva]
        escalar = [c.p_escalar for c in curva]
        self.assertLess(matar[0], matar[1])
        self.assertLess(matar[1], matar[2])
        self.assertGreater(escalar[0], escalar[1])
        self.assertGreaterEqual(escalar[1], escalar[2])

    def test_regla_ingenua_a_10_usd_mata_ganadores_mucho_mas(self):
        # Ganador con CPA 16,2 USD y corte a 10 USD sin venta: ~54 % (analitico) y la simulacion coincide.
        esc = sim.Escenario("g", 45.0, 45.0 / 1620.0, "CPA 16,20")
        simulado, analitico = sim.falso_descarte_regla_ingenua(esc, 1000.0, 600, SEMILLA)
        self.assertAlmostEqual(analitico, 0.54, delta=0.005)
        self.assertAlmostEqual(simulado, analitico, delta=0.08)
        # nuestra regla, mismo ganador (CPA 0,6 x un equilibrio de 27 USD), tope proporcional: casi no lo mata
        par = sim.parametros_referencia(cpa_be_minor=2700)
        cfg = sim.ConfigSim(2700, 2700 * 15, 40, 0.15, 0.20, 0.0)
        r = sim.simular_escenario(esc, par, LimitesCelda(cfg.tope_gasto_minor), cfg, 120, SEMILLA)
        self.assertLessEqual(r.p_matar, 0.08)

    def test_robustez_a_sobredispersion_de_la_conversion(self):
        cfg = sim.ConfigSim(**{**sim.CONFIG_REFERENCIA.__dict__, "sigma_conv": 0.3})
        r = sim.simular_escenario(sim.ESCENARIOS_REFERENCIA[0], self.par, self.lim, cfg, CORRIDAS, SEMILLA)
        self.assertLessEqual(r.p_matar, 0.06)          # real ~0,5 %

    def test_referencia_cli_imprime_tabla(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(sim.main(["--corridas", "20", "--semilla", "1"]), 0)
        salida = buf.getvalue()
        self.assertIn("| escenario |", salida)
        self.assertIn("Curva operativa", salida)


if __name__ == "__main__":
    unittest.main()
