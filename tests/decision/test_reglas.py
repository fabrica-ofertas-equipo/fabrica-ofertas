"""Pruebas de decision.reglas: decision secuencial, control, compatibilidad con Meta y oferta validada."""

import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from decision import estadistica as est
from decision import reglas as rg
from decision.reglas import Accion
from decision.simulacion import PARAMETROS_REFERENCIA, parametros_referencia

RAIZ = Path(__file__).resolve().parents[2]
TOPE = 22500
LIM = rg.LimitesCelda(TOPE)


def ev(gasto, clics, compras, horas=200.0, tracking=True, maduros=True, moneda="USD"):
    return rg.EvidenciaCelda("c1", "oferta_mercado", moneda, gasto, clics, compras, horas, tracking, maduros)


class TestDecisionCelda(unittest.TestCase):
    def setUp(self):
        self.par = parametros_referencia()

    def dec(self, e, lim=LIM):
        return rg.evaluar_celda(e, self.par, lim)

    # --- guardarrailes: sin datos, no se gasta ---
    def test_sin_tope_bloquea(self):
        d = self.dec(ev(1000, 25, 0), rg.LimitesCelda(None))
        self.assertEqual(d.accion, Accion.BLOQUEADO)
        self.assertEqual(d.codigo, "sin_limites")
        self.assertEqual(self.dec(ev(1000, 25, 0), rg.LimitesCelda(0)).accion, Accion.BLOQUEADO)

    def test_moneda_y_datos_invalidos_bloquean(self):
        self.assertEqual(self.dec(ev(1000, 25, 0, moneda="EUR")).codigo, "moneda_distinta")
        self.assertEqual(self.dec(ev(1000, 10, 11)).codigo, "datos_invalidos")
        self.assertEqual(self.dec(ev(-1, 10, 1)).accion, Accion.BLOQUEADO)

    # --- matar ---
    def test_poco_gasto_sin_compras_no_mata(self):
        d = self.dec(ev(1000, 25, 0))   # 10 USD sin venta: el corte clasico mataria aqui
        self.assertEqual(d.accion, Accion.SEGUIR)
        self.assertEqual(d.codigo, "sin_evidencia")

    def test_mata_sin_compras_con_gasto_y_probabilidad_suficientes(self):
        d = self.dec(ev(6000, 150, 0))
        self.assertEqual(d.accion, Accion.MATAR)
        self.assertEqual(d.codigo, "sin_compras")
        self.assertLessEqual(d.p_cpa_menor_equilibrio, 0.05)

    def test_con_tracking_dudoso_no_se_mata(self):
        d = self.dec(ev(6000, 150, 0, tracking=False))
        self.assertEqual(d.accion, Accion.SEGUIR)
        self.assertEqual(d.codigo, "tracking_dudoso")

    def test_en_ventana_solo_se_mata_con_cero_compras(self):
        # 0 compras exige ademas media ventana (36 de 72 h) desde la edicion (M02): a las 10 h todavia no, a las 40 h si
        self.assertNotEqual(self.dec(ev(6000, 150, 0, horas=10)).accion, Accion.MATAR)
        self.assertEqual(self.dec(ev(6000, 150, 0, horas=40)).accion, Accion.MATAR)
        # 3 compras en 150 clics y 60 USD: CPA 20 > equilibrio pero dentro de la ventana no se actua
        d = self.dec(ev(6000, 150, 3, horas=10))
        self.assertNotEqual(d.accion, Accion.MATAR)

    def test_mata_cpa_peor_cuando_el_tope_se_alcanza(self):
        d = self.dec(ev(TOPE, 500, 12))   # CPA 18,75 > 15 con P(CPA<=BE) ~ 18 % <= 20 %
        self.assertEqual(d.accion, Accion.MATAR)
        self.assertEqual(d.codigo, "cpa_peor_que_equilibrio")
        self.assertIn("tope", d.explicacion)

    # --- escalar ---
    def test_escala_ganador_claro(self):
        d = self.dec(ev(12000, 300, 20))
        self.assertEqual(d.accion, Accion.ESCALAR)
        self.assertGreaterEqual(d.p_cpa_menor_equilibrio, 0.99)
        self.assertLessEqual(d.cpa_mediano_minor, self.par.cpa_objetivo_minor)

    def test_no_escala_en_ventana_ni_con_pocas_compras(self):
        self.assertEqual(self.dec(ev(12000, 300, 20, horas=10)).codigo, "ventana_no_decidir")
        d = self.dec(ev(3000, 70, 8))    # 8 compras < 15 aunque el CPA sea excelente
        self.assertNotEqual(d.accion, Accion.ESCALAR)

    def test_prometedora_pero_justa_no_escala(self):
        d = self.dec(ev(15000, 330, 12))
        self.assertEqual(d.accion, Accion.SEGUIR)

    # --- tope ---
    def test_tope_sin_veredicto_es_inconcluso(self):
        d = self.dec(ev(TOPE, 520, 16))     # CPA 14,06: justo bajo el equilibrio, sobre el objetivo
        self.assertEqual(d.accion, Accion.INCONCLUSO)
        self.assertEqual(d.codigo, "tope_sin_veredicto")

    def test_tope_con_tracking_roto_es_inconcluso_de_datos(self):
        d = self.dec(ev(TOPE, 520, 16, tracking=False))
        self.assertEqual(d.accion, Accion.INCONCLUSO)
        self.assertEqual(d.codigo, "tope_con_datos_dudosos")

    def test_sin_clics(self):
        self.assertEqual(self.dec(ev(500, 0, 0)).accion, Accion.SEGUIR)
        self.assertEqual(self.dec(ev(TOPE, 0, 0)).codigo, "tope_sin_clics")

    # --- propiedades generales ---
    def test_determinista_y_serializable(self):
        e = ev(12000, 300, 20)
        a, b = self.dec(e), self.dec(e)
        self.assertEqual(a, b)
        json.dumps(a.a_dict())          # debe poder ir al registro
        self.assertEqual(a.a_dict()["accion"], "ESCALAR")

    def test_explicacion_legible_con_cifras(self):
        txt = self.dec(ev(12000, 300, 20)).explicacion
        for pieza in ("20 compras", "300 clics", "120,00 USD", "equilibrio 15,00 USD", "P(CPA<=equilibrio)"):
            self.assertIn(pieza, txt)

    def test_mas_compras_a_igual_gasto_nunca_empeora_la_decision(self):
        orden = {Accion.MATAR: 0, Accion.SEGUIR: 1, Accion.INCONCLUSO: 1, Accion.ESCALAR: 2}
        previo = -1
        for k in range(0, 25):
            d = self.dec(ev(12000, 300, k))
            self.assertGreaterEqual(orden[d.accion], previo, k)
            previo = orden[d.accion]

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            rg.ParametrosDecision("USD", 1500, 2000, 40.0, 0.02, 50, 20, 0.05, 0.2, 0.8, 2.0, 15, 72, 5)
        with self.assertRaises(ValueError):
            rg.ParametrosDecision("USD", 1500, 900, 40.0, 0.02, 50, 20, 0.7, 0.2, 0.8, 2.0, 15, 72, 5)

    def test_parametros_desde_mapeo_exige_todo(self):
        economia = {"moneda": "USD", "cpa_equilibrio_visto_minor": 1500, "cpa_objetivo_minor": 900,
                    "cpc_esperado_minor": 40.0, "conv_central": 0.025}
        par = rg.parametros_desde_mapeo(PARAMETROS_REFERENCIA, economia)
        self.assertEqual(par.cpa_equilibrio_minor, 1500)
        incompleto = dict(PARAMETROS_REFERENCIA)
        del incompleto["estadistica.p_escala"]
        with self.assertRaises(rg.ParametroFaltante):
            rg.parametros_desde_mapeo(incompleto, economia)
        with self.assertRaises(rg.ParametroFaltante):
            rg.parametros_desde_mapeo(PARAMETROS_REFERENCIA, {"moneda": "USD"})
        # acepta el formato de parametros.yaml: {valor: ...}
        envuelto = {k: {"valor": v} for k, v in PARAMETROS_REFERENCIA.items()}
        self.assertEqual(rg.parametros_desde_mapeo(envuelto, economia), par)


class TestHermanos(unittest.TestCase):
    def test_ranking_exploratorio_con_pocas_compras(self):
        par = parametros_referencia()
        celdas = [rg.EvidenciaCelda(f"a{i}", "anuncio", "USD", 4000, 100, k, 200, True, True) for i, k in enumerate([1, 4, 2])]
        r = rg.ranking_hermanos(celdas, par, semilla=5)
        self.assertEqual(r[0]["celda_id"], "a1")
        self.assertTrue(all(f["etiqueta"] == "exploratorio" for f in r))
        self.assertAlmostEqual(sum(f["p_mejor"] for f in r), 1.0)
        self.assertEqual(rg.ranking_hermanos([], par, 1), [])


class TestControl(unittest.TestCase):
    def celdas(self, n):
        return [rg.CeldaApagada(f"ad{i}", 1500, "sin_compras") for i in range(n)]

    def test_determinista_e_independiente_del_orden(self):
        a = rg.plan_grupo_control(self.celdas(50), 0.15, 0.25, 3000, 9, "USD")
        b = rg.plan_grupo_control(list(reversed(self.celdas(50))), 0.15, 0.25, 3000, 9, "USD")
        self.assertEqual(set(a.celdas_control), set(b.celdas_control))

    def test_fraccion_efectiva_cercana_a_la_pedida(self):
        p = rg.plan_grupo_control(self.celdas(4000), 0.15, 0.25, 3000, 3, "USD")
        self.assertAlmostEqual(p.fraccion_efectiva, 0.15, delta=0.02)
        self.assertEqual(p.gasto_maximo_control_minor, len(p.celdas_control) * 3000)
        self.assertTrue(all(v == 375 for v in p.presupuesto_diario_control_minor.values()))
        self.assertIn("control", p.explicacion)

    def test_limites_de_fraccion(self):
        self.assertEqual(rg.plan_grupo_control(self.celdas(30), 0.0, 0.25, 3000, 1, "USD").celdas_control, ())
        self.assertEqual(len(rg.plan_grupo_control(self.celdas(30), 1.0, 0.25, 3000, 1, "USD").celdas_control), 30)
        with self.assertRaises(ValueError):
            rg.plan_grupo_control(self.celdas(3), 1.5, 0.25, 3000, 1, "USD")

    def test_estimacion_de_falsos_descartes(self):
        r = rg.estimar_falsos_descartes(40, 2, 0.90)
        self.assertAlmostEqual(r["tasa"], 0.05)
        self.assertLess(r["ic"][0], 0.05)
        self.assertGreater(r["ic"][1], 0.05)
        self.assertIsNone(rg.estimar_falsos_descartes(0, 0)["tasa"])

    def test_controles_necesarios(self):
        self.assertGreater(rg.n_controles_para_detectar(0.05, 0.10, 0.05, 0.8), rg.n_controles_para_detectar(0.05, 0.20, 0.05, 0.8))


class TestMeta(unittest.TestCase):
    lim = rg.LimitesMeta(paso_max_pct=0.20, horas_min_entre_aumentos=72, max_teorico_factor=1.75,
                         max_cambios_por_hora=4, segundos_min_entre_ediciones=30)
    ahora = "2026-11-10T12:00:00Z"

    def prop(self, **kw):
        base = dict(actual_minor=3000, deseado_minor=6000, ultimo_aumento_utc=None, ahora_utc=self.ahora,
                    cambios_ultima_hora=0, segundos_desde_ultima_edicion=3600, techo_diario_oferta_minor=20000, lim=self.lim)
        base.update(kw)
        return rg.proponer_aumento_presupuesto(**base)

    def test_recorta_al_paso_maximo(self):
        p = self.prop()
        self.assertTrue(p.permitido)
        self.assertEqual(p.nuevo_presupuesto_minor, 3600)       # +20 %
        self.assertEqual(p.max_teorico_diario_minor, round(3600 * 1.75))

    def test_espera_72_horas(self):
        p = self.prop(ultimo_aumento_utc="2026-11-08T12:00:00Z")      # hace 48 h
        self.assertFalse(p.permitido)
        self.assertEqual(p.proximo_intento_utc, "2026-11-11T12:00:00Z")
        self.assertTrue(self.prop(ultimo_aumento_utc="2026-11-07T12:00:00Z").permitido)   # hace 72 h exactas

    def test_maximo_cuatro_cambios_por_hora_y_30_segundos(self):
        self.assertFalse(self.prop(cambios_ultima_hora=4).permitido)
        self.assertTrue(self.prop(cambios_ultima_hora=3).permitido)
        p = self.prop(segundos_desde_ultima_edicion=10)
        self.assertFalse(p.permitido)
        self.assertEqual(p.proximo_intento_utc, "2026-11-10T12:00:20Z")

    def test_techo_de_la_oferta_incluye_el_1_75(self):
        p = self.prop(actual_minor=10000, deseado_minor=12000, techo_diario_oferta_minor=20000)
        self.assertTrue(p.permitido)
        self.assertEqual(p.nuevo_presupuesto_minor, 11428)             # floor(20000 / 1,75)
        self.assertLessEqual(p.max_teorico_diario_minor, 20000)
        sin_margen = self.prop(actual_minor=11428, deseado_minor=12000, techo_diario_oferta_minor=20000)
        self.assertFalse(sin_margen.permitido)

    def test_sin_techo_no_se_permite(self):
        p = self.prop(techo_diario_oferta_minor=None)
        self.assertFalse(p.permitido)
        self.assertTrue(any("limites.yaml" in m for m in p.motivos))

    def test_bajar_no_usa_este_camino(self):
        self.assertFalse(self.prop(deseado_minor=2000).permitido)

    def test_pasos_para_alcanzar(self):
        n, dias = rg.pasos_para_alcanzar(3000, 30000, 0.20, 72)
        self.assertEqual(n, 13)                       # 1,2^13 = 10,7 >= 10
        self.assertAlmostEqual(dias, 36.0)
        self.assertEqual(rg.pasos_para_alcanzar(3000, 3000, 0.2, 72), (0, 0.0))


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestOfertaValidada(unittest.TestCase):
    ahora = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc)

    def setUp(self):
        self.par = parametros_referencia()
        self.pv = rg.ParametrosValidacion(
            garantia_dias=14, margen_madurez_dias=7, n_val=15, dias_con_compras_min=3, max_dia_pct=0.5,
            reembolso_max=0.08, p_validada=0.80, p_fallida=0.95, k_min_fallida=5.0, factor_objetivo=0.6,
            costo_var_pedido_minor=20, tasa_reembolso_esperada=0.08)

    def pedidos(self, n=20, dias_atras=40, repartir=7, reembolsados=0, parcial_dia=None):
        base = self.ahora - timedelta(days=dias_atras)
        out = []
        for i in range(n):
            reemb = 1700 if i < reembolsados else 0
            out.append(rg.PedidoStripe(f"p{i}", iso(base + timedelta(days=i % repartir, hours=1)), "USD",
                                       1700, 0, 100, reembolso_bruto_minor=reemb))
        return out

    def dias(self, desde_dias_atras=40, n_dias=10, gasto_total=12000, clics_total=400):
        base = (self.ahora - timedelta(days=desde_dias_atras)).date()
        return [rg.DiaMedia((base + timedelta(days=i)).isoformat(), gasto_total // n_dias, clics_total // n_dias) for i in range(n_dias)]

    def test_validada_con_cohorte_madura(self):
        v = rg.evaluar_oferta_validada(self.pedidos(), self.dias(), iso(self.ahora), self.pv, self.par)
        self.assertEqual(v.estado, "VALIDADA", v.explicacion)
        self.assertEqual(v.madura.compras_netas, 20)
        self.assertAlmostEqual(v.madura.cpa_neto_minor, 600.0)
        self.assertAlmostEqual(v.madura.mc_neta_minor, 1580.0)           # 1.700 - 100 comision - 20 costo_var
        self.assertAlmostEqual(v.madura.roas_neto, 20 * 1580 / 12000)
        self.assertEqual(v.fecha_corte_madurez_utc, "2026-11-29T12:00:00Z")   # ahora - (14 + 7) dias

    def test_provisional_cuando_aun_no_maduran(self):
        # compras de hace 12 a 6 dias: ninguna cumple garantia + 7
        v = rg.evaluar_oferta_validada(self.pedidos(dias_atras=12), self.dias(12), iso(self.ahora), self.pv, self.par)
        self.assertEqual(v.madura.compras_netas, 0)
        self.assertEqual(v.estado, "PROVISIONAL", v.explicacion)

    def test_reembolsos_totales_no_cuentan_como_compra_neta(self):
        v = rg.evaluar_oferta_validada(self.pedidos(reembolsados=6), self.dias(), iso(self.ahora), self.pv, self.par)
        self.assertEqual(v.madura.compras_netas, 14)
        self.assertEqual(v.madura.pedidos_pagados, 20)
        self.assertNotEqual(v.estado, "VALIDADA")      # 14 < n_val y reembolsos 30 % > 8 %

    def test_concentracion_en_un_dia_impide_validar(self):
        v = rg.evaluar_oferta_validada(self.pedidos(repartir=1), self.dias(), iso(self.ahora), self.pv, self.par)
        self.assertNotEqual(v.estado, "VALIDADA")
        self.assertTrue(any("un solo dia" in f or "dias" in f for f in v.fallos))

    def test_fallida_con_gasto_alto_y_pocas_compras(self):
        v = rg.evaluar_oferta_validada(self.pedidos(n=3), self.dias(gasto_total=60000, clics_total=2000), iso(self.ahora), self.pv, self.par)
        self.assertEqual(v.estado, "FALLIDA", v.explicacion)

    def test_cpa_entre_objetivo_y_equilibrio_es_prometedora(self):
        # 20 compras con gasto 25.000 -> CPA 1.250: > objetivo real (948) y < equilibrio real (1.580)
        v = rg.evaluar_oferta_validada(self.pedidos(), self.dias(gasto_total=25000, clics_total=700), iso(self.ahora), self.pv, self.par)
        self.assertEqual(v.estado, "PROMETEDORA", v.explicacion)

    def test_pedidos_sin_adid_no_cuentan(self):
        ped = [rg.PedidoStripe(p.pedido_id, p.pagado_en, p.moneda, p.bruto_minor, 0, p.comision_minor, atribuido_a_anuncio=False)
               for p in self.pedidos()]
        v = rg.evaluar_oferta_validada(ped, self.dias(), iso(self.ahora), self.pv, self.par)
        self.assertNotEqual(v.estado, "VALIDADA")
        self.assertEqual(v.madura.pedidos_pagados, 0)

    def test_moneda_distinta_es_error(self):
        ped = [rg.PedidoStripe("x", iso(self.ahora - timedelta(days=30)), "EUR", 1700, 0, 100)]
        with self.assertRaises(ValueError):
            rg.evaluar_oferta_validada(ped, self.dias(), iso(self.ahora), self.pv, self.par)

    def test_iva_se_descuenta_del_ingreso(self):
        ped = [rg.PedidoStripe(f"p{i}", iso(self.ahora - timedelta(days=30 + i % 7)), "USD", 1700, 318, 100) for i in range(20)]
        v = rg.evaluar_oferta_validada(ped, self.dias(), iso(self.ahora), self.pv, self.par)
        self.assertAlmostEqual(v.madura.mc_neta_minor, 1700 - 318 - 100 - 20)


class TestDocumentoYParametros(unittest.TestCase):
    def test_bloque_yaml_del_protocolo_coincide_con_la_referencia(self):
        doc = RAIZ / "docs" / "08-protocolo-estadistico-del-testeo.md"
        if not doc.exists():
            self.skipTest("documento aun no escrito")
        texto = doc.read_text(encoding="utf-8")
        bloques = re.findall(r"```yaml\n(.*?)```", texto, flags=re.S)
        self.assertTrue(bloques, "el documento debe traer el bloque YAML de parametros")
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no disponible (use .venv/bin/python)")
        datos = yaml.safe_load(bloques[-1])
        params = datos["parametros"]
        for clave, valor in PARAMETROS_REFERENCIA.items():
            self.assertIn(clave, params, clave)
            self.assertEqual(params[clave]["valor"], valor, clave)
            for campo in ("unidad", "hipotesis", "fuente", "ultima_calibracion"):
                self.assertIn(campo, params[clave], f"{clave}.{campo}")


if __name__ == "__main__":
    unittest.main()


class TestValidacionDeParametros(unittest.TestCase):
    """Un parametro mal cargado falla cerrado en vez de escalar con cero compras (critica M03, M01)."""

    def _par(self, **cambios):
        par = parametros_referencia()
        import dataclasses
        return dataclasses.replace(par, **cambios)

    def test_parametros_invalidos_se_rechazan(self):
        for malo in ({"n_min_escala": 0}, {"n_min_escala": -5}, {"k_min_matar": -1}, {"k_min_matar": 0}, {"ventana_no_decidir_h": -1},
                     {"nodos_cpc": 1}, {"prior_conv_media": 0.9}, {"prior_conv_fuerza_clics": 1}, {"prior_cpc_fuerza_clics": 1}):
            with self.assertRaises(ValueError, msg=str(malo)):
                self._par(**malo)

    def test_limites_meta_exige_fraccion_y_factor_minimo(self):
        ok = dict(paso_max_pct=0.2, horas_min_entre_aumentos=72, max_teorico_factor=1.75, max_cambios_por_hora=4, segundos_min_entre_ediciones=30)
        rg.LimitesMeta(**ok)
        for malo in ({"paso_max_pct": 20}, {"paso_max_pct": 0}, {"max_teorico_factor": 1.0}, {"max_teorico_factor": 0.0},
                     {"horas_min_entre_aumentos": -1}, {"max_cambios_por_hora": 0}):
            with self.assertRaises(ValueError, msg=str(malo)):
                rg.LimitesMeta(**{**ok, **malo})

    def test_instante_sin_z_se_rechaza(self):
        with self.assertRaises(ValueError):
            rg._parse_utc("2026-11-01T00:00:00")
        self.assertEqual(rg._parse_utc("2026-11-01T00:00:00Z").hour, 0)

    def test_disputa_abierta_resta_del_veredicto(self):
        p = rg.PedidoStripe("p1", "2026-10-01T00:00:00Z", "USD", 2000, 0, 100, disputa_abierta_minor=1500)
        c, _ = rg._contribucion_pedido(p, 0, 0.0, False)
        self.assertEqual(c, 2000 - 100 - 1500)
