"""Pruebas de los scripts de la skill D3 (sin red, sin escritura fuera de directorios temporales).

Comando (desde la raíz del repositorio)::

    .venv/bin/python -m unittest discover -s .claude/skills/d3-arquitectura-oferta/scripts -p 'test_*.py'

Qué prueban: la paridad de ``scripts.nivel_riesgo`` (única implementación ejes -> nivel) con los 230 casos de la suite de frontera, el envoltorio de
economía contra ``ofertas/_ejemplo/03-oferta/economia.json`` y contra el motor (el evento de aprendizaje sale de ``estadistica.*``), que las tres ofertas doradas pasan el validador del repositorio y el lint, que cada defecto sembrado con ``l1_esperado`` es
detectado por el script que dice, y la medición de falsos negativos peligrosos con un oráculo (0) y un clasificador «ingenuo por tema» (> 0).
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
RAIZ = SKILL.parents[2]
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
for p in (str(AQUI), str(RAIZ)):
    if p not in sys.path:
        sys.path.insert(0, p)

import aplicar_sembrado as AS  # noqa: E402
import economia_por_pais as EP  # noqa: E402
import lint_d3 as L  # noqa: E402
import medir_frontera as MF  # noqa: E402
from engine.errores import ErrorValidacion, ParametroFaltante  # noqa: E402
from scripts import nivel_riesgo as NR  # noqa: E402
from scripts import validar_esquemas as V  # noqa: E402

PARAM = yaml.safe_load((RAIZ / "empresa" / "parametros.yaml").read_text(encoding="utf-8"))
LIMITES = yaml.safe_load((RAIZ / "empresa" / "limites.yaml").read_text(encoding="utf-8"))
DORADOS = {"01": SKILL / "evals/dorados/01-es-es-reinsercion/OF-202611-01", "02": SKILL / "evals/dorados/02-it-it-planner-pasti/OF-202611-02",
           "03": SKILL / "evals/dorados/03-pl-pl-karty-rozmow/OF-202611-03"}
HOY = L.dt.date(2026, 11, 6)


class TestParidadConNivelRiesgo(unittest.TestCase):
    """D3 no tiene tabla propia: usa ``scripts.nivel_riesgo.calcular``. Estas pruebas fijan la paridad con la suite de 230 casos."""

    @classmethod
    def setUpClass(cls):
        cls.casos = MF.cargar_suite(MF.SUITE_POR_DEFECTO)

    def test_los_230_casos_dan_nivel_subnivel_y_veredicto_esperados(self):
        self.assertEqual(230, len(self.casos))
        for c in self.casos:
            fuera = c["macro_nicho_esperado"] == "fuera_de_macro_nicho"
            r = NR.calcular(c["ejes"], fuera_de_macro=fuera, zona_gris=bool(c.get("zona_gris")), hay_reencuadre=c["veredicto_esperado"] == "reformular")
            esperado = (None if fuera else str(c["nivel_esperado"]).lower(), c.get("subnivel"), c["veredicto_esperado"])
            self.assertEqual(esperado, (r["nivel"], r["subnivel"], r["veredicto_riesgo"]), c["id"])

    def test_la_suite_completa_pasa_la_verificacion_del_propio_modulo(self):
        self.assertEqual([], NR.verificar_suite(MF.SUITE_POR_DEFECTO))

    def test_el_nivel_compuesto_de_medir_frontera_coincide_con_los_226_casos_con_nivel(self):
        n = 0
        for c in self.casos:
            if c["macro_nicho_esperado"] == "fuera_de_macro_nicho":
                continue
            self.assertEqual(MF.esperado_de(c)[0], MF.nivel_compuesto(c["ejes"]), c["id"])
            n += 1
        self.assertEqual(226, n)

    def test_ejes_invalidos_se_rechazan(self):
        malos = {"P": "P9", "C": "C1", "E": "E1", "N": "N1"}
        self.assertTrue(MF.validar_ejes(malos))
        with self.assertRaises(ErrorValidacion):
            NR.calcular(malos)
        self.assertTrue(MF.validar_ejes("no es un objeto"))

    def test_dos_amarillos_son_b_y_el_maximo_manda(self):
        self.assertEqual("AMARILLO-B", MF.nivel_compuesto({"P": "P2s", "C": "C2", "E": "E1", "N": "N1"}))
        self.assertEqual("AMARILLO-A", MF.nivel_compuesto({"P": "P2s", "C": "C1", "E": "E1", "N": "N1"}))
        self.assertEqual("ROJO", MF.nivel_compuesto({"P": "P2s", "C": "C2", "E": "E2", "N": "N1"}))
        self.assertEqual("VERDE", MF.nivel_compuesto({"P": "P0", "C": "C0", "E": "E0", "N": "N1"}))

    def test_n0_solo_existe_fuera_de_macro(self):
        n0 = {"P": "P0", "C": "C0", "E": "E0", "N": "N0"}
        with self.assertRaises(ErrorValidacion):
            MF.nivel_compuesto(n0)                                   # en macro: inconsistencia
        self.assertEqual("VERDE", MF.nivel_compuesto(n0, diagnostico=True))   # fuera de macro no detectado: N0 se lee como N1 (mismo color)

    def test_un_n0_dentro_de_macro_cuenta_como_aritmetica_inconsistente(self):
        casos = [c for c in MF.seleccionar(self.casos, "desarrollo", "d3") if c["macro_nicho_esperado"] != "fuera_de_macro_nicho"][:3]
        preds = predicciones_oraculo(casos)
        preds[0]["ejes"] = dict(preds[0]["ejes"], N="N0")
        m = MF.evaluar(casos, preds)
        self.assertEqual(1, len(m["aritmetica_inconsistente"]))


class TestEconomiaPorPais(unittest.TestCase):
    def plan_ejemplo(self):
        eco = json.loads((RAIZ / "ofertas/_ejemplo/03-oferta/economia.json").read_text(encoding="utf-8"))
        # _ejemplo se generó SIN la regla de aprendizaje (evento Purchase con 27,60 EUR/día): se reproduce fijando el evento, que es lo único
        # que justifica una clave que el Maker NO escribe en un plan real.
        base = dict(eco["entradas_usadas"], gasto_diario=2760, evento_optimizacion_inicial="Purchase")
        return eco, {"oferta_id": eco["oferta_id"], "version": "v1", "origen_version": "maker", "base": base, "paises": {"ES": {}}}

    def test_reproduce_la_economia_del_ejemplo(self):
        eco, plan = self.plan_ejemplo()
        from scripts.validar_esquemas import limites_de_prueba
        res = EP.economia_por_pais(plan, PARAM, limites_de_prueba())
        self.assertEqual(eco, res["paises"]["ES"])
        self.assertEqual("FACTIBLE", res["veredicto_cluster"])

    def test_el_peor_pais_manda_y_la_tabla_lo_marca(self):
        _, plan = self.plan_ejemplo()
        plan["paises"] = {"ES": {"tasa_iva_bp": 2100}, "IT": {"tasa_iva_bp": 2200, "tarifa_meta_bp": 300}, "FR": {"tasa_iva_bp": 2000, "tarifa_meta_bp": 300}}
        res = EP.economia_por_pais(plan, PARAM, LIMITES)
        razones = {p: float(d["razon"]) for p, d in res["paises"].items()}
        self.assertEqual(min(razones, key=razones.get), res["peor"])
        self.assertEqual("IT", res["peor"])
        self.assertIn("IT (peor)", EP.tabla_markdown(res))

    def test_monedas_mezcladas_fallan(self):
        _, plan = self.plan_ejemplo()
        plan["paises"] = {"ES": {}, "PL": {"moneda": "PLN"}}
        with self.assertRaises(Exception):
            EP.economia_por_pais(plan, PARAM, LIMITES)

    def test_cli_escribe_el_peor_y_el_motor_lo_verifica(self):
        _, plan = self.plan_ejemplo()
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "plan.json"
            ruta.write_text(json.dumps(plan), encoding="utf-8")
            salida = Path(t) / "economia.json"
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                codigo = EP.main(["--plan", str(ruta), "--parametros", str(RAIZ / "empresa/parametros.yaml"), "--salida-economia", str(salida)])
            self.assertEqual(0, codigo, err.getvalue())
            self.assertTrue(salida.is_file())
            self.assertIn("Veredicto del clúster", out.getvalue())

    def test_sin_parametros_falla_cerrado_con_5(self):
        _, plan = self.plan_ejemplo()
        del plan["base"]["gasto_diario"]
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "plan.json"
            ruta.write_text(json.dumps(plan), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(3, EP.main(["--plan", str(ruta), "--parametros", str(RAIZ / "empresa/parametros.yaml")]))


class TestEventoDeAprendizaje(unittest.TestCase):
    """El evento de optimización sale del motor con ``estadistica.meta_eventos_aprendizaje_semana`` y ``meta_fraccion_min_purchase`` (no del plan)."""

    def plan(self, nombre):
        carpeta = "02-familia-pl-it" if nombre[:3] in ("it-", "pl-") else "06-forzados"
        return json.loads((SKILL / "evals/dorados" / carpeta / f"plan-{nombre}.json").read_text(encoding="utf-8"))

    def test_los_parametros_se_traducen_a_las_entradas_del_motor(self):
        self.assertEqual({"eventos_semana_aprendizaje": 50, "fraccion_aprendizaje_min_bp": 5000}, EP.aprendizaje_de_parametros(PARAM))

    def test_un_plan_sin_las_constantes_da_lo_mismo_que_uno_que_las_trae(self):
        for nombre in ("30usd-dia", "120usd-dia"):
            con = self.plan(nombre)
            sin = copy.deepcopy(con)
            for clave in ("eventos_semana_aprendizaje", "fraccion_aprendizaje_min_bp"):
                sin["base"].pop(clave)
            a, b = EP.economia_por_pais(con, PARAM, LIMITES), EP.economia_por_pais(sin, PARAM, LIMITES)
            self.assertEqual(a["paises"], b["paises"], nombre)
            esperado = "InitiateCheckout" if nombre == "30usd-dia" else "Purchase"
            self.assertEqual(esperado, b["paises"][b["peor"]]["evento_optimizacion_inicial"], nombre)

    def test_el_plan_de_la_plantilla_no_lleva_las_constantes(self):
        plan = json.loads((SKILL / "templates/plan-economia.json").read_text(encoding="utf-8"))
        self.assertNotIn("eventos_semana_aprendizaje", plan["base"])
        self.assertNotIn("fraccion_aprendizaje_min_bp", plan["base"])

    def test_un_valor_distinto_en_el_plan_es_un_override_sin_fuente(self):
        plan = self.plan("30usd-dia")
        plan["base"]["eventos_semana_aprendizaje"] = 40
        with self.assertRaises(ErrorValidacion):
            EP.economia_por_pais(plan, PARAM, LIMITES)

    def test_sin_las_claves_de_estadistica_falla_cerrado_con_5(self):
        plan = self.plan("30usd-dia")
        sin_estadistica = copy.deepcopy(PARAM)
        del sin_estadistica["grupos"]["estadistica"]["meta_fraccion_min_purchase"]
        with self.assertRaises(ParametroFaltante):
            EP.economia_por_pais(plan, sin_estadistica, LIMITES)
        with tempfile.TemporaryDirectory() as t:
            ruta, par = Path(t) / "plan.json", Path(t) / "par.yaml"
            ruta.write_text(json.dumps(plan), encoding="utf-8")
            par.write_text(yaml.safe_dump(sin_estadistica), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(5, EP.main(["--plan", str(ruta), "--parametros", str(par)]))


class TestDorados(unittest.TestCase):
    def test_los_tres_dorados_pasan_el_validador_del_repositorio(self):
        for clave, d in DORADOS.items():
            inf = V.validar_oferta(d)
            self.assertEqual([], [str(h) for h in inf.errores], clave)

    def test_los_tres_dorados_pasan_el_lint_con_las_reglas_de_x1_y_sin_semilla_provisional(self):
        for clave, d in DORADOS.items():
            for provisional in (False, True):
                r = L.ejecutar(d, PARAM, LIMITES, provisional, HOY)
                self.assertEqual([], [c for c in r["checks"] if c["resultado"] == "fail"], (clave, provisional))

    def test_el_lint_entrega_los_hashes_que_el_qa_no_puede_calcular(self):
        r = L.ejecutar(DORADOS["01"], PARAM, LIMITES, True, HOY)
        self.assertRegex(r["artefacto_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertIn("03-oferta/economia.json", r["entradas"])
        self.assertEqual("03-oferta/oferta.json", r["artefacto_ref"])

    def test_l1_03_con_las_reglas_actuales_de_x1(self):
        """it-IT y pl-PL YA tienen reglas (reglas_sensibles.yaml 1.1.0, sin revisión nativa): pasa y lo dice; un locale sin reglas sigue fallando cerrado."""
        l103 = lambda k: next(c for c in L.ejecutar(DORADOS[k], PARAM, LIMITES, False, HOY)["checks"] if c["check_id"] == "L1-03")
        self.assertEqual("pass", l103("01")["resultado"])
        self.assertNotIn("SIN revisión nativa", l103("01")["detalle"])
        for k in ("02", "03"):
            r = l103(k)
            self.assertEqual("pass", r["resultado"], r)
            self.assertIn("SIN revisión nativa", r["detalle"])
            self.assertNotIn("sin la ficha", r["detalle"])      # la ficha de pl-PL va con el encabezado localizado «Karta oferty (12 punktów)»

    def test_l1_03_sin_reglas_del_locale_falla_cerrado_y_en_practica_queda_no_aplica(self):
        oferta = json.loads((DORADOS["01"] / "03-oferta/oferta.json").read_text(encoding="utf-8"))
        md = (DORADOS["01"] / "03-oferta/oferta.md").read_text(encoding="utf-8")
        semilla = yaml.safe_load((L.AQUI / "terminos_semilla.yaml").read_text(encoding="utf-8"))
        self.assertEqual("fail", L.l1_03(oferta, md, "nl-NL", "dinero", False, semilla)[0]["resultado"])
        self.assertEqual("no_aplica", L.l1_03(oferta, md, "nl-NL", "dinero", True, semilla)[0]["resultado"])

    def test_la_garantia_incondicional_de_los_dorados_no_usa_formulas_que_x1_marca_rojo(self):
        """garantias_absolutas marca ROJO «ti rimborsiamo», «zwrot pieniędzy», «te devolvemos el dinero»: los dorados usan formulas que pasan."""
        from compliance.lint_claims import lint_texto
        from compliance.reglas import cargar_reglas
        reglas = cargar_reglas()
        for clave, d in DORADOS.items():
            o = json.loads((d / "03-oferta/oferta.json").read_text(encoding="utf-8"))
            rojos = [h for h in lint_texto(o["garantia"]["texto_visible"], reglas, locale=o["locale"], macro_nicho=o["macro_nicho"]) if h.nivel == "rojo"]
            self.assertEqual([], rojos, clave)

    def test_la_cabecera_de_ficha_localizada_se_reconoce(self):
        for t in ("## Ficha de la oferta (12 puntos) — EN EL IDIOMA", "## Ficha della offerta (12 punti)", "## Karta oferty (12 punktów)"):
            self.assertTrue(L.RX_FICHA.search(t + "\n"), t)
        self.assertFalse(L.RX_FICHA.search("## F. Declaraciones para D4, D5 y X1\n"))

    def test_los_dorados_son_factibles_y_reproducibles_por_el_motor(self):
        from engine import factibilidad as F
        for clave, d in DORADOS.items():
            eco = json.loads((d / "03-oferta/economia.json").read_text(encoding="utf-8"))
            self.assertEqual("FACTIBLE", eco["veredicto"], clave)
            self.assertEqual([], F.verificar(eco, PARAM, LIMITES), clave)

    def test_el_ejemplo_del_repositorio_no_cumple_la_spec_de_d3(self):
        """Evidencia del PEDIDO: ofertas/_ejemplo trae 0 bonus y 3 ángulos (la spec pide 3-5 y >= 5)."""
        r = L.ejecutar(RAIZ / "ofertas/_ejemplo", PARAM, LIMITES, True, HOY)
        fallos = {c["check_id"] for c in r["checks"] if c["resultado"] == "fail"}
        self.assertTrue({"L1-07", "L1-12"} <= fallos, fallos)


class TestBumpYMarcas(unittest.TestCase):
    """L1-12 usa SOLO el rango de ``landing.bump_pct_precio_min/max`` (el 40 % de la spec es una recomendación); L1-13 vigila ``marca_propuesta[]``."""

    @classmethod
    def setUpClass(cls):
        cls.semilla = yaml.safe_load((L.AQUI / "terminos_semilla.yaml").read_text(encoding="utf-8"))
        cls.oferta = json.loads((DORADOS["01"] / "03-oferta/oferta.json").read_text(encoding="utf-8"))
        cls.md = (DORADOS["01"] / "03-oferta/oferta.md").read_text(encoding="utf-8")
        cls.eco = json.loads((DORADOS["01"] / "03-oferta/economia.json").read_text(encoding="utf-8"))

    def con_bump(self, pct):
        o = copy.deepcopy(self.oferta)
        o["bump"]["precio"]["monto"] = round(o["precio"]["lista"]["monto"] * pct / 100)
        return o

    def l112(self, o, parametros=PARAM):
        return L.l1_12(o, parametros, self.semilla, "es")[0]

    def test_un_bump_dentro_del_rango_del_parametro_pasa_aunque_supere_el_40_recomendado(self):
        rango = (PARAM["grupos"]["landing"]["bump_pct_precio_min"]["valor"], PARAM["grupos"]["landing"]["bump_pct_precio_max"]["valor"])
        self.assertEqual((30, 60), rango)
        for pct in (30, 40, 55, 60):
            self.assertEqual("pass", self.l112(self.con_bump(pct))["resultado"], pct)

    def test_un_bump_fuera_del_rango_falla_con_la_clave_del_parametro(self):
        bajo, alto = self.l112(self.con_bump(20)), self.l112(self.con_bump(65))
        self.assertEqual("fail", bajo["resultado"])
        self.assertIn("landing.bump_pct_precio_min", bajo["detalle"])
        self.assertEqual("fail", alto["resultado"])
        self.assertIn("landing.bump_pct_precio_max", alto["detalle"])

    def test_sin_parametros_el_rango_no_se_verifica_y_se_dice(self):
        r = self.l112(self.con_bump(90), parametros=None)
        self.assertEqual("pass", r["resultado"])
        self.assertIn("NO verificado", r["detalle"])

    RX_MARCAS = re.compile(r"marca_propuesta:[^\n]*\n(?:  [^\n]*\n)+")

    def md_con_marcas(self, marcas):
        cab = yaml.safe_dump({"marca_propuesta": marcas}, allow_unicode=True, sort_keys=False)
        return self.RX_MARCAS.sub(cab, self.md, count=1)

    def l113(self, marcas):
        return L.l1_13(self.oferta, self.semilla, "es", self.md_con_marcas(marcas), self.eco)[0]

    def test_hasta_tres_marcas_neutras_pasan(self):
        marcas = [{"nombre": "Mi Ruta Laboral", "dominio": "mirutalaboral.example"}, {"nombre": "Currículum en Orden", "dominio": "curriculumenorden.example"}]
        self.assertEqual("pass", self.l113(marcas)["resultado"])

    def test_mas_de_tres_marcas_fallan(self):
        marcas = [{"nombre": f"Marca Uno{i}", "dominio": f"marca{i}.example"} for i in range(4)]
        r = self.l113(marcas)
        self.assertEqual("fail", r["resultado"])
        self.assertIn("máximo 3", r["detalle"])

    def test_marcas_con_sufijo_verbo_de_cambio_o_tercero_fallan(self):
        for nombre, dominio, pista in (("Regreso Pro", "regresopro.example", "sufijo"), ("Baja Tu Deuda", "bajatudeuda.example", "nombre_verbos_de_cambio"),
                                       ("Canva Laboral", "canvalaboral.example", "terceros"), ("Ganar Dinero Hoy", "ganar.example", "nombre_ganar")):
            r = self.l113([{"nombre": nombre, "dominio": dominio}])
            self.assertEqual("fail", r["resultado"], nombre)
            self.assertIn(pista, r["detalle"], nombre)

    def test_una_marca_sin_dominio_falla(self):
        self.assertEqual("fail", self.l113([{"nombre": "Mi Ruta Laboral"}])["resultado"])

    def test_sin_marca_propuesta_pasa_pero_avisa_si_la_oferta_es_factible(self):
        r = L.l1_13(self.oferta, self.semilla, "es", self.md, self.eco)[0]
        md_sin = self.RX_MARCAS.sub("", self.md, count=1)
        self.assertNotIn("marca_propuesta", md_sin.split("\n---\n")[0])
        r2 = L.l1_13(self.oferta, self.semilla, "es", md_sin, self.eco)[0]
        self.assertEqual("pass", r2["resultado"])
        self.assertIn("sin marca_propuesta[]", r2["detalle"])
        self.assertNotIn("sin marca_propuesta[]", r["detalle"])   # los dorados ya la traen


class TestSembrados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datos = yaml.safe_load((SKILL / "evals/sembrados/sembrados.yaml").read_text(encoding="utf-8"))["sembrados"]

    def aplicar(self, s):
        t = Path(tempfile.mkdtemp(prefix="sembrado-"))
        self.addCleanup(shutil.rmtree, t, True)
        base = next(p for p in sorted((SKILL / "evals/dorados" / s["base"]).iterdir()) if p.is_dir() and p.name.startswith("OF-"))
        AS.aplicar(s, base, t)
        return t / base.name

    def test_cobertura_25_sembrados_20_bloqueantes_3_macros_y_2_idiomas(self):
        """Anexo A.1 de la spec: S5, S17 y S21 son BLOQUEANTES (sus checks lo son) y S12 es MAYOR (L1-09): 20 + 5 + 0."""
        self.assertEqual([f"S{i}" for i in range(1, 26)], [s["id"] for s in self.datos])
        sev = [s["severidad"] for s in self.datos]
        self.assertEqual((20, 5, 0), (sev.count("BLOQUEANTE"), sev.count("MAYOR"), sev.count("MENOR")))
        self.assertEqual({"BLOQUEANTE"}, {s["severidad"] for s in self.datos if s["id"] in ("S5", "S17", "S21")})
        self.assertEqual("MAYOR", next(s["severidad"] for s in self.datos if s["id"] == "S12"))
        self.assertEqual({"dinero", "salud", "relaciones"}, {s["macro"] for s in self.datos})
        self.assertGreaterEqual(len({s["idioma"] for s in self.datos}), 2)

    def test_cada_sembrado_se_aplica_y_no_toca_el_dorado(self):
        antes = {k: hashlib.sha256((d / "03-oferta/oferta.json").read_bytes()).hexdigest() for k, d in DORADOS.items()}
        for s in self.datos:
            self.aplicar(s)
        despues = {k: hashlib.sha256((d / "03-oferta/oferta.json").read_bytes()).hexdigest() for k, d in DORADOS.items()}
        self.assertEqual(antes, despues)

    def test_los_sembrados_con_l1_esperado_son_detectados_por_el_script_que_dice(self):
        sin_l1 = []
        for s in self.datos:
            if not s["l1_esperado"]:
                sin_l1.append(s["id"])
                continue
            d = self.aplicar(s)
            lint = None
            validar = None
            for esperado in s["l1_esperado"]:
                herramienta, codigo = esperado.split(":", 1)
                if herramienta == "lint_d3":
                    lint = lint or L.ejecutar(d, PARAM, LIMITES, True, HOY)
                    fallos = {c["check_id"] for c in lint["checks"] if c["resultado"] == "fail"}
                    self.assertIn(codigo, fallos, f"{s['id']}: {codigo} no falló; fallaron {sorted(fallos)}")
                else:
                    validar = validar or V.validar_oferta(d)
                    codigos = {h.codigo for h in validar.errores}
                    self.assertIn(codigo, codigos, f"{s['id']}: {codigo} no apareció; hubo {sorted(codigos)}")
        # Los que solo detecta el QA (juicio L2/L3) están declarados, no escondidos.
        self.assertEqual(["S4", "S9", "S10", "S11", "S18", "S22", "S24"], sin_l1)

    def test_un_sembrado_con_texto_inexistente_falla_con_claridad(self):
        s = {"id": "X", "muta": [{"archivo": "03-oferta/oferta.md", "op": "reemplazar_texto", "de": "NO EXISTE", "a": "x"}]}
        t = Path(tempfile.mkdtemp(prefix="sembrado-"))
        self.addCleanup(shutil.rmtree, t, True)
        with self.assertRaises(ValueError):
            AS.aplicar(s, DORADOS["01"], t)


class TestCasosNumericos(unittest.TestCase):
    """Los planes de evals/dorados/{02,06} reproducen la salida esperada con el motor (nadie la edita a mano)."""

    def test_los_planes_reproducen_el_esperado(self):
        esperado = yaml.safe_load((SKILL / "evals/dorados/_esperado-numerico.yaml").read_text(encoding="utf-8"))
        self.assertEqual(9, len(esperado))
        for clave, e in esperado.items():
            carpeta = "02-familia-pl-it" if clave[:3] in ("it-", "pl-") else "06-forzados"
            plan = json.loads((SKILL / "evals/dorados" / carpeta / f"plan-{clave}.json").read_text(encoding="utf-8"))
            res = EP.economia_por_pais(plan, PARAM, LIMITES)
            d = res["paises"][res["peor"]]
            self.assertEqual((e["razon"], e["veredicto"], e["evento"], e["dias_test"]),
                             (d["razon"], d["veredicto"], d["evento_optimizacion_inicial"], d["dias_test"]), clave)

    def test_initiatecheckout_penaliza_la_razon_en_un_cuarto(self):
        esperado = yaml.safe_load((SKILL / "evals/dorados/_esperado-numerico.yaml").read_text(encoding="utf-8"))
        ic, compra = esperado["30usd-dia"], esperado["120usd-dia"]
        self.assertEqual(("InitiateCheckout", "Purchase"), (ic["evento"], compra["evento"]))
        self.assertAlmostEqual(float(compra["razon"]) / 1.25, float(ic["razon"]), delta=0.01)

    def test_el_caso_2_es_no_factible_en_todos_los_escalones_y_el_ticket_de_7_usd_tambien(self):
        esperado = yaml.safe_load((SKILL / "evals/dorados/_esperado-numerico.yaml").read_text(encoding="utf-8"))
        for k, e in esperado.items():
            if k[:3] in ("it-", "pl-") or k == "ticket-7usd":
                self.assertEqual("NO_FACTIBLE", e["veredicto"], k)


def predicciones_oraculo(casos):
    salida = []
    for c in casos:
        fuera = c["macro_nicho_esperado"] == "fuera_de_macro_nicho"
        p = {"caso_id": c["id"], "macro_nicho": c["macro_nicho_esperado"], "ejes": c["ejes"], "veredicto": c["veredicto_esperado"]}
        if c["veredicto_esperado"] == "reformular":
            p["reencuadre"] = {"ejes_reformulados": c["ejes_reformulados"], "deseo_conservado": c["deseo_conservado"]}
        if fuera:
            p["ejes"] = {"P": "P0", "C": "C0", "E": "E0", "N": "N0"}
        salida.append(p)
    return salida


class TestMedirFrontera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = MF.cargar_suite(MF.SUITE_POR_DEFECTO)

    def test_el_oraculo_da_cero_falsos_negativos_en_los_tres_conjuntos(self):
        for conjunto in ("desarrollo", "rt"):
            for alcance in ("d3", "todo"):
                casos = MF.seleccionar(self.suite, conjunto, alcance)
                m = MF.evaluar(casos, predicciones_oraculo(casos))
                self.assertEqual([], m["falsos_negativos_peligrosos"], (conjunto, alcance))
                self.assertEqual([], m["falsos_verdes"])
                self.assertEqual([], m["aritmetica_inconsistente"])
                self.assertEqual([], m["reencuadres_invalidos"])
                v = MF.veredicto(m, conjunto, 60, 0.05)
                self.assertFalse(v["peligro"])
                self.assertFalse(v["certifica"])           # solo la retención sellada por el dueño certifica

    def test_desarrollo_excluye_los_rt_y_el_conjunto_rt_son_30(self):
        self.assertFalse(any(c["id"].startswith("RT-") for c in MF.seleccionar(self.suite, "desarrollo", "todo")))
        self.assertEqual(30, len(MF.seleccionar(self.suite, "rt", "todo")))
        self.assertEqual(200, len(MF.seleccionar(self.suite, "desarrollo", "todo")))

    def test_un_clasificador_ingenuo_por_tema_tiene_falsos_negativos_peligrosos(self):
        casos = MF.seleccionar(self.suite, "desarrollo", "d3")
        preds = predicciones_oraculo(casos)
        ingenuo = {c["id"] for c in casos if c["ingenuo_por_tema"] == "falso_negativo"}
        self.assertGreater(len(ingenuo), 10)
        for p in preds:
            if p["caso_id"] in ingenuo:
                p.update(macro_nicho="dinero", ejes={"P": "P0", "C": "C1", "E": "E1", "N": "N1"}, veredicto="pasa", reencuadre=None)
        m = MF.evaluar(casos, preds)
        self.assertGreater(len(m["falsos_negativos_peligrosos"]), 10)
        self.assertTrue(MF.veredicto(m, "desarrollo", 60, 0.05)["peligro"])

    def test_el_nivel_declarado_que_no_sale_de_los_ejes_es_inconsistencia(self):
        casos = MF.seleccionar(self.suite, "desarrollo", "d3")
        preds = predicciones_oraculo(casos)
        rojo = next(p for p, c in zip(preds, casos) if c["nivel_esperado"] == "ROJO" and c["macro_nicho_esperado"] != "fuera_de_macro_nicho")
        rojo["nivel"] = "VERDE"
        m = MF.evaluar(casos, preds)
        self.assertEqual(1, len(m["aritmetica_inconsistente"]))

    def test_un_reencuadre_que_no_cambia_ejes_es_invalido(self):
        casos = [c for c in MF.seleccionar(self.suite, "desarrollo", "todo") if c["veredicto_esperado"] == "reformular"][:3]
        preds = predicciones_oraculo(casos)
        preds[0]["reencuadre"]["ejes_reformulados"] = dict(preds[0]["ejes"])
        m = MF.evaluar(casos, preds)
        self.assertEqual(1, len(m["reencuadres_invalidos"]))

    def test_casos_sin_prediccion_son_peligro(self):
        casos = MF.seleccionar(self.suite, "desarrollo", "d3")
        m = MF.evaluar(casos, predicciones_oraculo(casos)[:-1])
        self.assertEqual(1, len(m["sin_prediccion"]))
        self.assertTrue(MF.veredicto(m, "desarrollo", 60, 0.05)["peligro"])

    def test_la_retencion_exige_archivo_y_sello_y_certifica_con_n_suficiente(self):
        with tempfile.TemporaryDirectory() as t:
            pred = Path(t) / "pred.json"
            casos_rt = MF.seleccionar(self.suite, "desarrollo", "todo")[:160]
            pred.write_text(json.dumps(predicciones_oraculo(casos_rt)), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(2, MF.main(["--predicciones", str(pred), "--conjunto", "retencion"]))
            ret = Path(t) / "ret.yaml"
            ret.write_text(yaml.safe_dump({"casos": casos_rt}, allow_unicode=True), encoding="utf-8")
            sello = "sha256:" + hashlib.sha256(ret.read_bytes()).hexdigest()
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(0, MF.main(["--predicciones", str(pred), "--conjunto", "retencion", "--retencion", str(ret), "--sello", sello, "--json"]))
            self.assertTrue(json.loads(out.getvalue())["veredicto"]["certifica"])
            with redirect_stderr(io.StringIO()):
                self.assertEqual(3, MF.main(["--predicciones", str(pred), "--conjunto", "retencion", "--retencion", str(ret), "--sello", "sha256:" + "0" * 64]))

    def test_el_lote_exportado_no_trae_respuestas(self):
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "lote.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, MF.main(["--exportar-lote", str(ruta), "--conjunto", "desarrollo", "--alcance", "d3"]))
            lote = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertGreater(len(lote), 100)
            self.assertTrue(all(set(x) == {"caso_id", "idea", "idioma"} for x in lote))
            self.assertFalse(any(x["caso_id"].startswith("RT-") for x in lote))

    def test_la_cota_de_la_regla_de_tres(self):
        casos = MF.seleccionar(self.suite, "desarrollo", "todo")
        m = MF.evaluar(casos, predicciones_oraculo(casos))
        self.assertAlmostEqual(3 / m["positivos_esperado_rojo_o_fuera"], m["cota_superior_95_si_cero_errores"], places=3)


if __name__ == "__main__":
    unittest.main()
