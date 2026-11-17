"""Pruebas de la economía única (D-01, C14): ``engine.factibilidad`` + su envoltorio ``decision.presupuesto`` + la regla X14.

Vectores de referencia del plano (docs/08 §3.1) y qué magnitud es cada uno:
  24,42  CPA_BE (= MC) del ejemplo de D3 §3.4        16,25  MC de F1 §3.5        11,54  CPA_BE de Italia base (visto en Ads Manager: 11,20)

Comando: ``.venv/bin/python -m unittest tests.contratos.test_factibilidad``
"""
from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction
from pathlib import Path
from unittest import mock

from decision import presupuesto as pre
from engine import factibilidad as F
from engine.errores import ErrorValidacion, ParametroFaltante
from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
CLAVE = V.CLAVE_DE_PRUEBA
PARAM = V.cargar_yaml(RAIZ / "empresa" / "parametros.yaml")


def entradas(**kw):
    """Entradas del vector D3 §3.4 (USD): P 27, bump 10 % × 9, 2,9 % + 0,30, r 7 %, d 0,5 %, disputa 15, costo 0,20."""
    base = dict(moneda="USD", precio=2700, precio_bump=900, tasa_bump_bp=1000, tasa_reembolso_bp=700, tasa_disputa_bp=50,
                comision_pct_bp=290, comision_fija=30, tarifa_disputa=1500, costo_variable=20, factor_cpa_objetivo_bp=6000)
    base.update(kw)
    return base


def con_escenarios(**kw):
    esc = {"pes": {"cpm": 600, "ctr_enlace_bp": 100, "clic_compra_bp": 120},
           "central": {"cpm": 450, "ctr_enlace_bp": 160, "clic_compra_bp": 220},
           "opt": {"cpm": 400, "ctr_enlace_bp": 220, "clic_compra_bp": 300}}
    return entradas(escenarios=kw.pop("escenarios", esc), gasto_diario=kw.pop("gasto_diario", 2760), k=3, n_dec=15, razon_min_factible="1.3", **kw)


class TestVectores(unittest.TestCase):
    """Los tres vectores del plano, por la función económica y por el envoltorio de ``decision``."""

    def test_vector_24_42_cpa_be_del_ejemplo_de_d3(self):
        u = F.economia_unitaria(entradas())
        self.assertEqual(2790, u["aov"])
        self.assertEqual(2442, u["cpa_be"])                      # 24,42
        self.assertEqual(2442, u["mc"])
        self.assertEqual(1465, u["cpa_obj"])                     # 0,6 × 24,42 = 14,65
        self.assertEqual("1.14", u["roas_be"])

    def test_vector_16_25_mc_de_f1(self):
        u = F.economia_unitaria(entradas(precio=1700, precio_bump=700, tasa_bump_bp=3000, comision_pct_bp=290, recargos_bp=150))   # 4,4 % = 2,9 + 1,5
        self.assertEqual(1910, u["aov"])
        self.assertEqual(1625, u["mc"])                          # 16,25
        self.assertEqual(975, u["cpa_obj"])                      # 9,75
        self.assertEqual("1.18", u["roas_be"])

    def test_vector_11_54_cpa_be_de_italia_base(self):
        u = F.economia_unitaria(entradas(precio=1728, precio_bump=0, tasa_bump_bp=0, tasa_iva_bp=2200, comision_pct_bp=290, recargos_bp=150, conversion_bp=100,
                                         stripe_tax={"pct_bp": 50, "fijo": 0}, tasa_reembolso_bp=800, tasa_disputa_bp=60, costo_variable=0, tarifa_meta_bp=300))
        self.assertEqual(312, u["iva"])
        self.assertEqual(1154, u["cpa_be"])                      # 11,54
        self.assertEqual(1120, u["cpa_be_visto"])                # 11,20 visto en Ads Manager (Meta +3 %)

    def test_el_envoltorio_de_decision_da_los_mismos_numeros(self):
        p = pre.ParametrosPrecio(moneda="USD", precio_bruto_minor=2700, tasa_iva=0.0, comision_pct=0.029, comision_fija_minor=30, stripe_tax_pct=0.0,
                                 stripe_tax_fijo_minor=0, tasa_bump=0.10, precio_bump_minor=900, tasa_reembolso=0.07, tasa_disputa=0.005,
                                 tarifa_disputa_minor=1500, costo_var_minor=20, tarifa_meta_pct=0.0, factor_objetivo=0.6)
        e = pre.economia_por_pedido(p)
        u = F.economia_unitaria(entradas())
        self.assertEqual((u["aov"], u["mc_con_signo"], u["cpa_be"], u["cpa_be_visto"], u["cpa_obj"]),
                         (e.aov_bruto_minor, e.contribucion_minor, e.cpa_equilibrio_minor, e.cpa_equilibrio_visto_minor, e.cpa_objetivo_minor))

    def test_economia_por_pedido_llama_a_la_unica_formula(self):
        p = pre.ParametrosPrecio(moneda="USD", precio_bruto_minor=2700, tasa_iva=0.0, comision_pct=0.029, comision_fija_minor=30, stripe_tax_pct=0.0,
                                 stripe_tax_fijo_minor=0, tasa_bump=0.0, precio_bump_minor=0, tasa_reembolso=0.0, tasa_disputa=0.0,
                                 tarifa_disputa_minor=0, costo_var_minor=0, tarifa_meta_pct=0.0, factor_objetivo=0.6)
        with mock.patch.object(F, "economia_unitaria", wraps=F.economia_unitaria) as espia:
            pre.economia_por_pedido(p)
        self.assertEqual(1, espia.call_count)

    def test_envoltorio_y_nucleo_coinciden_en_una_rejilla(self):
        for precio in (700, 1490, 2700):
            for iva in (0.0, 0.21, 0.23):
                for meta in (0.0, 0.03):
                    for r in (0.0, 0.08, 0.12):
                        p = pre.ParametrosPrecio(moneda="EUR", precio_bruto_minor=precio, tasa_iva=iva, comision_pct=0.054, comision_fija_minor=30,
                                                 stripe_tax_pct=0.005, stripe_tax_fijo_minor=0, tasa_bump=0.1, precio_bump_minor=500, tasa_reembolso=r,
                                                 tasa_disputa=0.006, tarifa_disputa_minor=1500, costo_var_minor=20, tarifa_meta_pct=meta, factor_objetivo=0.6)
                        u = F.economia_unitaria(entradas(moneda="EUR", precio=precio, precio_bump=500, tasa_bump_bp=1000, tasa_iva_bp=round(iva * 10000),
                                                         comision_pct_bp=540, stripe_tax={"pct_bp": 50, "fijo": 0}, tasa_reembolso_bp=round(r * 10000),
                                                         tasa_disputa_bp=60, tarifa_meta_bp=round(meta * 10000)))
                        self.assertEqual(u["mc_con_signo"], pre.economia_por_pedido(p).contribucion_minor, (precio, iva, meta, r))


class TestFormula(unittest.TestCase):
    def test_disputa_es_d_por_neto_mas_tarifa(self):
        sin = F.economia_unitaria(entradas(tasa_disputa_bp=0))
        con = F.economia_unitaria(entradas(tasa_disputa_bp=100))
        # d·(neto + tarifa) = 1 % × (2790 + 1500) = 42,9 (la fórmula vieja daba 1 % × 1500 = 15)
        self.assertEqual(43, con["disputa_esperada"])
        self.assertEqual(sin["mc_con_signo"] - 43, con["mc_con_signo"])

    def test_iva_por_pais_baja_el_neto(self):
        a, b = F.economia_unitaria(entradas(tasa_iva_bp=0)), F.economia_unitaria(entradas(tasa_iva_bp=2200))
        self.assertEqual(round(Fraction(2790, 1) / Fraction(122, 100)), b["neto"])
        self.assertEqual(2790 - b["neto"], b["iva"])
        self.assertLess(b["mc"], a["mc"])

    def test_recargo_de_meta_solo_baja_el_cpa_visto(self):
        a, b = F.economia_unitaria(entradas()), F.economia_unitaria(entradas(tarifa_meta_bp=300))
        self.assertEqual(a["cpa_be"], b["cpa_be"])
        self.assertEqual(round(Fraction(a["cpa_be"] * 10000, 10300)), b["cpa_be_visto"])
        self.assertEqual(round(Fraction(b["cpa_be_visto"] * 6000, 10000)), b["cpa_obj"])          # cpa_obj = f × visto

    def test_la_comision_no_se_devuelve_al_reembolsar(self):
        base = F.economia_unitaria(entradas(tasa_reembolso_bp=0, tasa_disputa_bp=0))
        r10 = F.economia_unitaria(entradas(tasa_reembolso_bp=1000, tasa_disputa_bp=0))
        self.assertEqual(279, base["mc_con_signo"] - r10["mc_con_signo"])                          # r × neto = 10 % de 2790; la comisión se pierde entera
        self.assertEqual(base["comision"], r10["comision"])

    def test_mezcla_de_metodos_pondera_comision_y_tarifa_de_disputa(self):
        mezcla = [{"metodo": "tarjeta", "peso_bp": 5000, "comision_pct_bp": 290, "comision_fija": 30, "tarifa_disputa": 1500},
                  {"metodo": "local", "peso_bp": 5000, "comision_pct_bp": 190, "comision_fija": 30, "tarifa_disputa": 0}]
        u = F.economia_unitaria(entradas(mix_metodos=mezcla))
        ref = F.economia_unitaria(entradas(comision_pct_bp=240, tarifa_disputa=750))
        self.assertEqual(ref["mc_con_signo"], u["mc_con_signo"])
        self.assertEqual({"comision_pct_bp": 240, "comision_fija": 30, "tarifa_disputa": 750}, u["entradas_efectivas"])
        self.assertGreater(u["mc"], F.economia_unitaria(entradas())["mc"])

    def test_mezcla_invalida_falla(self):
        with self.assertRaises(ErrorValidacion):      # pesos que no suman 10000
            F.economia_unitaria(entradas(mix_metodos=[{"peso_bp": 4000, "comision_pct_bp": 290, "comision_fija": 30}]))
        with self.assertRaises(ErrorValidacion):      # promedio no entero: economia.json no sería reproducible
            F.economia_unitaria(entradas(mix_metodos=[{"peso_bp": 3333, "comision_pct_bp": 290, "comision_fija": 30},
                                                      {"peso_bp": 6667, "comision_pct_bp": 190, "comision_fija": 30}]))

    def test_upsell_paga_otra_tarifa_fija(self):
        sin = F.economia_unitaria(entradas())
        con = F.economia_unitaria(entradas(tasa_upsell_bp=1000, precio_upsell=1900))
        self.assertEqual(2790 + 190, con["aov"])
        self.assertGreater(con["comision"] - sin["comision"], 190 * 290 // 10000)

    def test_half_even_en_los_empates(self):
        self.assertEqual((2, 2, 4, 4), (F._redondear(Fraction(5, 2)), F._redondear(Fraction(3, 2)) + 0, F._redondear(Fraction(7, 2)), F._redondear(Fraction(9, 2))))
        # neto = aov / 2 con IVA 100 %: 3 → 1,5 → 2 · 5 → 2,5 → 2 · 7 → 3,5 → 4
        def mc(p):
            return F.economia_unitaria(entradas(precio=p, precio_bump=0, tasa_bump_bp=0, tasa_iva_bp=10000, comision_pct_bp=0, comision_fija=0,
                                                tasa_reembolso_bp=0, tasa_disputa_bp=0, costo_variable=0))["mc_con_signo"]
        self.assertEqual((2, 2, 4), (mc(3), mc(5), mc(7)))

    def test_sin_float_en_ninguna_salida(self):
        r = F.calcular(con_escenarios(), PARAM, V.limites_de_prueba())
        self.assertEqual([], V.buscar_floats(r))
        for malo in (dict(precio=19.9), dict(tasa_iva_bp=21.0), dict(comision_fija=0.3), dict(tasa_bump_bp=True)):
            with self.assertRaises(ErrorValidacion, msg=str(malo)):
                F.economia_unitaria(entradas(**malo))
        with self.assertRaises(ErrorValidacion):
            F.calcular(con_escenarios(penal_evento_senal=1.25, evento_optimizacion_inicial="InitiateCheckout"), PARAM)

    def test_margen_no_positivo_acota_a_cero_y_no_es_factible(self):
        r = F.calcular(con_escenarios(precio=100, precio_bump=0, tasa_bump_bp=0, costo_variable=500), PARAM)
        self.assertEqual(0, r["mc"]["monto"])
        self.assertLess(r["desglose"]["mc_con_signo"], 0)
        self.assertEqual("NO_FACTIBLE", r["veredicto"])
        self.assertEqual("0", r["roas_be"])

    def test_monedas_mezcladas(self):
        with self.assertRaises(ErrorValidacion):
            F.economia_unitaria(entradas(precio={"monto": 2700, "moneda": "EUR"}))


class TestCalcular(unittest.TestCase):
    def eco(self):
        return V.cargar_json(RAIZ / "ofertas" / "_ejemplo" / "03-oferta" / "economia.json")

    def test_reproduce_la_economia_del_ejemplo(self):
        eco = self.eco()
        self.assertEqual([], F.verificar(eco, PARAM, V.limites_de_prueba()))
        self.assertEqual((2069, 1830, 1098), (eco["aov"]["monto"], eco["mc"]["monto"], eco["cpa_obj"]["monto"]))      # MC 1830, no 1840 (D-01)

    def test_documento_completo_valida_contra_el_esquema_y_es_estable(self):
        eco = self.eco()
        entr = {**eco["entradas_usadas"], "gasto_diario": 2760, "oferta_id": eco["oferta_id"]}
        doc = F.documento_economia(entr, PARAM, V.limites_de_prueba())
        self.assertEqual([], V.errores_de_esquema("economia", doc))
        self.assertEqual(eco, doc)                              # el archivo del ejemplo ES la salida de calcular

    def test_campos_d02(self):
        r = F.calcular(con_escenarios(), PARAM, V.limites_de_prueba())
        self.assertEqual("0.022", r["conv_central"])
        self.assertEqual({"monto": "28.125", "moneda": "USD"}, r["cpc_esperado"])
        self.assertEqual(r["cpa_be"], r["cpa_be_visto"])
        self.assertEqual({"pes": 5000, "central": 1278, "opt": 606}, {k: v["monto"] for k, v in r["cpa_real"].items()})
        plan = r["gasto_test_plan"]["monto"]
        self.assertEqual(round(plan * (Fraction(2442 * 160 * 220, 450 * 100000) - 1)), r["resultado_esperado_central"]["monto"])

    def test_plan_del_test(self):
        r = F.calcular(con_escenarios(), PARAM)
        cpa_c = Fraction(450 * 100000, 160 * 220)
        self.assertEqual(round(max(5 * 3 * 2442, 15 * cpa_c)), r["presupuesto_test_min"]["monto"])
        self.assertEqual(max(7, -(-r["presupuesto_test_min"]["monto"] // 2760)), r["dias_test"])
        self.assertEqual(2760 * r["dias_test"], r["gasto_test_plan"]["monto"])
        self.assertEqual(r["gasto_test_plan"], r["perdida_max_test"])
        grande = F.calcular(con_escenarios(gasto_diario=999999), PARAM)
        self.assertEqual(7, grande["dias_test"])                # nunca menos de una semana
        con_fijos = F.calcular(con_escenarios(costos_fijos_oferta=1234), PARAM)
        self.assertEqual(r["gasto_test_plan"]["monto"] + 1234, con_fijos["perdida_max_test"]["monto"])

    def test_veredictos(self):
        def v(cpm):
            esc = {n: {"cpm": cpm, "ctr_enlace_bp": 160, "clic_compra_bp": 220} for n in ("pes", "central", "opt")}
            return F.calcular(con_escenarios(escenarios=esc), PARAM)
        self.assertEqual("FACTIBLE", v(450)["veredicto"])        # razón ≈ 1,9
        self.assertEqual("AJUSTADA", v(700)["veredicto"])        # 1,0 ≤ razón < 1,3
        self.assertEqual("NO_FACTIBLE", v(2000)["veredicto"])    # razón < 1,0

    def test_evento_initiatecheckout_aplica_la_penalizacion(self):
        base = F.calcular(con_escenarios(), PARAM)
        ic = F.calcular(con_escenarios(evento_optimizacion_inicial="InitiateCheckout", penal_evento_senal="1.25"), PARAM)
        self.assertEqual("InitiateCheckout", ic["evento_optimizacion_inicial"])
        self.assertEqual(round(Fraction(450 * 100000, 160 * 220) * Fraction(5, 4)), ic["cpa_real"]["central"]["monto"])
        self.assertLess(Fraction(ic["razon"]), Fraction(base["razon"]))
        regla = F.calcular(con_escenarios(eventos_semana_aprendizaje=50, fraccion_aprendizaje_min_bp=5000, penal_evento_senal="1.25"), PARAM)
        self.assertEqual("InitiateCheckout", regla["evento_optimizacion_inicial"])         # 2760 < 0,5 × (50/7) × 1278 ≈ 4565
        self.assertEqual("Purchase", F.calcular(con_escenarios(gasto_diario=10000, eventos_semana_aprendizaje=50, fraccion_aprendizaje_min_bp=5000), PARAM)["evento_optimizacion_inicial"])

    def test_umbral_ausente_falla_cerrado_con_5(self):
        sin = con_escenarios(); del sin["razon_min_factible"]
        with self.assertRaises(ParametroFaltante) as cm:
            F.calcular(sin)
        self.assertEqual(5, cm.exception.codigo_salida)
        self.assertIsNone(F.calcular(sin, estricto=False)["veredicto"])
        self.assertEqual("FACTIBLE", F.calcular(sin, PARAM)["veredicto"])     # el umbral sale de parametros.yaml (economia.razon_min_factible)

    def test_limites_en_null_no_salen_con_5_y_se_listan(self):
        plantilla = V.cargar_yaml(RAIZ / "empresa" / "limites.yaml")                 # límites reales: todo en null
        r = F.calcular(con_escenarios(), PARAM, plantilla)
        self.assertEqual(V.CLAVES_CRITICAS["gastar"], r["limites_pendientes"])
        self.assertEqual(V.CLAVES_CRITICAS["gastar"], F.calcular(con_escenarios(), PARAM, None)["limites_pendientes"])   # sin archivo: todo pendiente
        completos = V.limites_de_prueba()
        self.assertEqual([], F.calcular(con_escenarios(), PARAM, completos)["limites_pendientes"])
        parcial = copy.deepcopy(completos); parcial["gasto_diario_global"] = None
        self.assertEqual(["gasto_diario_global"], F.calcular(con_escenarios(), PARAM, parcial)["limites_pendientes"])
        self.assertEqual(V.CLAVES_CRITICAS["escalar"] and [k for k in V.CLAVES_CRITICAS["escalar"] if parcial.get(k) in (None, [], {})],
                         F.calcular(con_escenarios(), PARAM, parcial, operacion_limites="escalar")["limites_pendientes"])

    def test_documento_incompleto_falla(self):
        sin_diario = con_escenarios(); del sin_diario["gasto_diario"]
        with self.assertRaises(ErrorValidacion):
            F.documento_economia({**sin_diario, "oferta_id": "OF-202611-01"}, PARAM)

    def test_escenarios_incompletos_o_en_cero(self):
        with self.assertRaises(ErrorValidacion):
            F.calcular(con_escenarios(escenarios={"central": {"cpm": 1, "ctr_enlace_bp": 1, "clic_compra_bp": 1}}), PARAM)
        esc = {n: {"cpm": 450, "ctr_enlace_bp": 160, "clic_compra_bp": 0 if n == "pes" else 220} for n in ("pes", "central", "opt")}
        with self.assertRaises(ErrorValidacion):
            F.calcular(con_escenarios(escenarios=esc), PARAM)


class TestX14LlamaALaFormulaUnica(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fact-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "OF-202611-01"
        shutil.copytree(RAIZ / "ofertas" / "_ejemplo", self.dir)

    def validar(self):
        return V.validar_oferta(self.dir, limites=V.limites_de_prueba(), autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"), clave_firma=CLAVE)

    def test_x14_llama_a_calcular_y_el_ejemplo_pasa(self):
        with mock.patch.object(F, "calcular", wraps=F.calcular) as espia:
            inf = self.validar()
        self.assertGreaterEqual(espia.call_count, 1)
        self.assertEqual([], [str(h) for h in inf.errores])

    def test_x14_detecta_el_mc_de_la_formula_vieja(self):
        ruta = self.dir / "03-oferta" / "economia.json"
        eco = json.loads(ruta.read_text(encoding="utf-8"))
        eco["mc"]["monto"] = eco["cpa_be"]["monto"] = 1840             # d × tarifa (sin neto): el 1840 de antes de D-01
        ruta.write_text(json.dumps(eco), encoding="utf-8")
        self.assertIn("03-oferta/economia.json/mc", [h.ruta for h in self.validar().errores if h.codigo == "X14_ECONOMIA"])

    def test_no_queda_otra_formula_en_el_validador(self):
        fuente = (RAIZ / "scripts" / "validar_esquemas.py").read_text(encoding="utf-8")
        self.assertNotIn("X14_FORMULA_PENDIENTE", fuente)
        self.assertIn("fact.calcular(", fuente)
        self.assertNotIn("entero_redondeado(e[\"tarifa_disputa\"]", fuente)


class TestCLI(unittest.TestCase):
    def correr(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            codigo = F.main(list(argv))
        return codigo, out.getvalue(), err.getvalue()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fact-cli-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.eco = RAIZ / "ofertas" / "_ejemplo" / "03-oferta" / "economia.json"
        self.par = RAIZ / "empresa" / "parametros.yaml"
        self.lim = V.DIR_EJEMPLOS / "limites.valido.yaml"

    def test_calcular_escribe_el_mismo_economia_json(self):
        eco = V.cargar_json(self.eco)
        entr = self.tmp / "entradas.json"
        entr.write_text(json.dumps({**eco["entradas_usadas"], "gasto_diario": 2760, "oferta_id": eco["oferta_id"]}), encoding="utf-8")
        salida = self.tmp / "economia.json"
        codigo, _, _ = self.correr("calcular", "--entradas", str(entr), "--parametros", str(self.par), "--limites", str(self.lim), "--salida", str(salida))
        self.assertEqual(0, codigo)
        self.assertEqual(eco, json.loads(salida.read_text(encoding="utf-8")))

    def test_verificar_ok_y_diferencias(self):
        self.assertEqual(0, self.correr("verificar", "--economia", str(self.eco), "--parametros", str(self.par))[0])
        malo = V.cargar_json(self.eco); malo["mc"]["monto"] += 1
        ruta = self.tmp / "malo.json"; ruta.write_text(json.dumps(malo), encoding="utf-8")
        codigo, salida, _ = self.correr("verificar", "--economia", str(ruta))
        self.assertEqual(3, codigo)
        self.assertIn("DIFERENCIA mc", salida)

    def test_sin_umbrales_sale_con_5_y_con_uso_incorrecto_2(self):
        eco = V.cargar_json(self.eco)
        entr = self.tmp / "entradas.json"
        entr.write_text(json.dumps({**eco["entradas_usadas"], "gasto_diario": 2760, "oferta_id": eco["oferta_id"]}), encoding="utf-8")
        self.assertEqual(5, self.correr("calcular", "--entradas", str(entr))[0])        # sin parametros.yaml: k, n_dec y razon mínima faltan
        self.assertEqual(2, self.correr("calcular")[0])
        self.assertEqual(2, self.correr("calcular", "--entradas", str(self.tmp / "no-existe.json"))[0])

    def test_el_comando_exacto_esta_documentado(self):
        comando = ".venv/bin/python -m engine.factibilidad calcular --entradas"
        self.assertIn(comando, F.__doc__)
        self.assertIn(".venv/bin/python -m engine.factibilidad verificar --economia", F.__doc__)
        self.assertIn(comando, (RAIZ / "docs" / "contratos.md").read_text(encoding="utf-8"))
        for vector in ("24,42", "16,25", "11,54"):
            self.assertIn(vector, F.__doc__)


if __name__ == "__main__":
    unittest.main()
