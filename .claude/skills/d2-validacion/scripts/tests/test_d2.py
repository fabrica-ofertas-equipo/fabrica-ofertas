"""Pruebas de los scripts de D2 (v0.1.0). Ejecutar desde la raíz del repositorio:

  .venv/bin/python -m unittest discover -s .claude/skills/d2-validacion/scripts/tests -p "test_*.py" -v

Sin red. Los vectores de la spec (SS_a = 0,233 y 0,675) y la coincidencia de `metricas.py` con `qa_recomputar.py`
(implementación independiente) son las pruebas centrales: DoD de D2 = diferencia 0.
"""
from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SCRIPTS = AQUI.parent
SKILL = SCRIPTS.parent
RAIZ = SKILL.parents[2]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(AQUI))

import metricas as M  # noqa: E402
import params as P  # noqa: E402
import qa_recomputar as Q  # noqa: E402
import verificar_citas as VC  # noqa: E402
import veredicto as V  # noqa: E402
from fixtures_d2 import base_entrada, conc, entrada_go, hueco, op, operadores_sostenidos  # noqa: E402

PARAMS, _ = P.cargar()
PY = sys.executable


def calc(e, **over):
    p = dict(PARAMS)
    p.update(over)
    return V.calcular(e, p)


class Vectores(unittest.TestCase):
    def test_160_duplicados_un_concepto_60_dias_un_pais_sin_embudo_da_0_233(self):
        e = base_entrada()
        e["operadores"] = [op("op-01", "producto_digital", [conc("c1", "M1", "a", 60)], embudo="0")]
        o = M.calcular(e, PARAMS)["operadores"][0]
        self.assertEqual(o["SS_a"], "0.233")
        self.assertFalse(o["sostenido"])

    def test_tres_conceptos_90_dias_un_pais_landing_con_checkout_da_0_675(self):
        e = base_entrada()
        e["operadores"] = [op("op-01", "producto_digital", [conc("c1", "M1", "a", 90), conc("c2", "M1", "b", 90), conc("c3", "M1", "c", 90)], embudo="0.5")]
        o = M.calcular(e, PARAMS)["operadores"][0]
        self.assertEqual((o["SS_a"], o["I_a"], o["sostenido"]), ("0.675", 0, True))

    def test_iteracion_con_separacion_suma_I(self):
        e = base_entrada()
        e["operadores"] = [op("op-01", "producto_digital", [conc("c1", "M1", "a", 90), conc("c2", "M1", "b", 70), conc("c3", "M1", "c", 90)])]
        self.assertEqual(M.calcular(e, PARAMS)["operadores"][0]["SS_a"], "0.875")

    def test_el_volumen_bruto_pesa_cero(self):
        e = base_entrada()
        e["mercado_resumen"]["anuncios_activos"] = 160
        e["operadores"] = [op("op-01", "producto_digital", [conc("c1", "M1", "a", 60)], embudo="0")]
        self.assertEqual(M.calcular(e, PARAMS)["operadores"][0]["SS_a"], "0.233")

    def test_truncado_marca_piso(self):
        e = base_entrada()
        e["operadores"] = [op("op-01", "producto_digital", [conc("c1", "M1", "a", 60)], truncado=True)]
        self.assertTrue(M.calcular(e, PARAMS)["operadores"][0]["s_a_es_piso"])


class Mecanismo(unittest.TestCase):
    def _e(self, mecs, mu="M1", indist=False):
        e = base_entrada()
        e["operadores"] = operadores_sostenidos(mecs)
        e["mu"] = {"tipo_mecanismo": mu, "indistinguible_de_sostenido": indist, "evidencia_id": "EV-03" if indist else None}
        return e

    def test_cuatro_sostenidos_tres_en_M1_es_alta(self):
        self.assertEqual(M.calcular(self._e(["M1", "M1", "M1", "M2"]), PARAMS)["saturacion_mecanismo"]["nivel"], "alta")

    def test_tres_sostenidos_no_concluyente_es_media(self):
        self.assertEqual(M.calcular(self._e(["M1", "M1", "M1"]), PARAMS)["saturacion_mecanismo"]["nivel"], "media")

    def test_cuatro_sostenidos_sin_la_clase_es_baja(self):
        self.assertEqual(M.calcular(self._e(["M2", "M3", "M4", "M5"]), PARAMS)["saturacion_mecanismo"]["nivel"], "baja")

    def test_indistinguible_es_alta_aunque_sean_pocos(self):
        self.assertEqual(M.calcular(self._e(["M2"], indist=True), PARAMS)["saturacion_mecanismo"]["nivel"], "alta")


class Convergencia(unittest.TestCase):
    def _e(self, angulo, dif):
        e = base_entrada()
        e["operadores"] = operadores_sostenidos(["M1", "M2", "M3", "M4"])
        e["angulo_recomendado"], e["diferenciador_sustentado"] = angulo, dif
        return e

    def test_baja_si_nadie_usa_el_angulo(self):
        self.assertEqual(M.calcular(self._e("angulo-que-nadie-usa", True), PARAMS)["convergencia"]["estado"], "baja")

    def test_alta_si_solapa_mucho_sin_diferenciador_y_media_con_el(self):
        e = self._e("x", False)
        for o in e["operadores"]:
            for c in o["conceptos"]:
                c["angulo_principal"] = "x"
        self.assertEqual(M.calcular(e, PARAMS)["convergencia"]["estado"], "alta")
        e["diferenciador_sustentado"] = True
        self.assertEqual(M.calcular(e, PARAMS)["convergencia"]["estado"], "media")

    def test_media_entre_0_25_y_el_umbral(self):
        e = self._e("x", False)
        # 4 de 12 conceptos con el ángulo = 0,333: entre 0,25 y 0,5
        for o in e["operadores"]:
            o["conceptos"][0]["angulo_principal"] = "x"
        self.assertEqual(M.calcular(e, PARAMS)["convergencia"]["estado"], "media")


class Confianza(unittest.TestCase):
    def test_todo_cumplido_es_alta(self):
        c = M.calcular(entrada_go(), PARAMS)["confianza"]
        self.assertEqual((c["puntos"], c["nivel"]), (100, "alta"))

    def test_sin_segunda_pasada_no_pasa_de_baja(self):
        e = entrada_go()
        e["confianza_datos"]["segunda_pasada"] = False
        c = M.calcular(e, PARAMS)["confianza"]
        self.assertEqual((c["puntos"], c["nivel"], c["forzada_a_baja"]), (20, "baja", True))

    def test_sin_snapshots_suficientes_no_pasa_de_baja(self):
        e = entrada_go()
        e["confianza_datos"]["competidores_con_snapshot_leido"] = 2
        self.assertEqual(M.calcular(e, PARAMS)["confianza"]["nivel"], "baja")

    def test_replica_con_jaccard_bajo_es_baja(self):
        e = entrada_go()
        e["confianza_datos"]["jaccard_replica"] = "0.3"
        self.assertEqual(M.calcular(e, PARAMS)["confianza"]["nivel"], "baja")

    def test_media_con_tres_criterios(self):
        e = entrada_go()
        e["confianza_datos"].update({"landings_analizadas": 1, "consultas_distintas": 3})
        c = M.calcular(e, PARAMS)["confianza"]
        self.assertEqual((c["puntos"], c["nivel"]), (60, "media"))


class Veredicto(unittest.TestCase):
    def test_caso_completo_es_GO(self):
        r = calc(entrada_go())
        self.assertEqual((r["calculado"], r["razones_codigo"]), ("GO", []))

    def test_sin_lectura_de_snapshots_nunca_GO(self):
        for modo in ("ninguno", "pendiente_humano"):
            e = entrada_go()
            e["lectura_snapshots"] = modo
            r = calc(e)
            self.assertEqual(r["calculado"], "GO_CONDICIONAL", modo)
            self.assertEqual(r["provisional"], modo == "pendiente_humano")

    def test_cero_competidores_nunca_GO_y_con_confianza_baja_es_condicional(self):
        e = base_entrada()
        e["confianza_datos"].update({"competidores_profundos": 0, "competidores_con_snapshot_leido": 0})
        e["voz"].update({"frases_total": 5, "frases_propias": 2, "frases_del_locale": 5})
        self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL")

    def test_cero_sostenidos_pocas_frases_con_confianza_es_NO_GO(self):
        e = base_entrada()
        e["operadores"] = [op("op-01", "producto_digital", [conc("c1", "M1", "a", 20)], embudo="0")]
        e["voz"].update({"frases_total": 8, "frases_propias": 4, "frases_del_locale": 8})
        r = calc(e)
        self.assertEqual(r["calculado"], "NO_GO")
        self.assertIn("NO_GO:cero_sostenidos_pocas_frases_con_confianza", r["razones_codigo"])

    def test_mecanismo_saturado_sin_hueco_con_confianza_es_NO_GO(self):
        e = base_entrada()
        e["operadores"] = operadores_sostenidos(["M3", "M3", "M3", "M2"])
        e["mu"]["tipo_mecanismo"] = "M3"
        e["huecos"] = hueco(presente=["op-01", "op-02", "op-03", "op-04"])
        self.assertEqual(calc(e)["calculado"], "NO_GO")

    def test_mecanismo_saturado_con_hueco_no_es_GO_pero_tampoco_NO_GO(self):
        e = base_entrada()
        e["operadores"] = operadores_sostenidos(["M3", "M3", "M3", "M2"])
        e["huecos"] = hueco()
        self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL")

    def test_IS_muy_alto_sin_hueco_es_NO_GO(self):
        e = entrada_go()
        e["huecos"] = hueco(presente=["op-01", "op-02", "op-03", "op-04"])
        self.assertEqual(calc(e, is_nogo_min=10)["calculado"], "NO_GO")

    def test_IS_alto_con_hueco_no_es_GO(self):
        self.assertEqual(calc(entrada_go(), is_go_max=10)["calculado"], "GO_CONDICIONAL")

    def test_sin_hueco_sustentado_no_es_GO(self):
        e = entrada_go()
        e["huecos"] = hueco(presente=["op-01", "op-02"])  # lo cubren 2 de 4 (ausencia 0,5 < 0,7)
        self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL")

    def test_hueco_con_pocas_frases_o_fuentes_no_cuenta(self):
        for kw in ({"frases": 4}, {"fuentes": 2}):
            e = entrada_go()
            e["huecos"] = hueco(**kw)
            self.assertFalse(M.calcular(e, PARAMS)["hueco_sustentado"], kw)

    def test_rojo_sin_reencuadre_es_NO_GO_y_con_reencuadre_verificable_es_condicional(self):
        e = entrada_go()
        e["riesgo"]["final"] = {"nivel": "rojo", "subnivel": None}
        self.assertEqual(calc(e)["calculado"], "NO_GO")
        e["riesgo"]["reencuadre_verificable_x1"] = True
        self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL")

    def test_ningun_angulo_seguro_es_NO_GO(self):
        e = entrada_go()
        e["riesgo"]["angulo_seguro_existe"] = False
        self.assertEqual(calc(e)["calculado"], "NO_GO")

    def test_amarillo_A_puede_ser_GO_y_amarillo_B_no(self):
        e = entrada_go()
        e["riesgo"]["heredado"] = {"P": "verde", "C": "amarillo", "E": "verde", "N": "verde", "nivel": "amarillo", "subnivel": "A"}
        e["riesgo"]["final"] = {"nivel": "amarillo", "subnivel": "A"}
        self.assertEqual(calc(e)["calculado"], "GO")
        e["riesgo"]["heredado"]["subnivel"] = "B"
        e["riesgo"]["final"] = {"nivel": "amarillo", "subnivel": "B"}
        self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL")

    def test_veto_de_X1_impide_GO(self):
        e = entrada_go()
        e["riesgo"]["x1_dictamen"] = "FAIL"
        self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL")

    def test_sustituto_gratis_dominante_o_no_medido_impide_GO(self):
        for s in ("dominante", "no_medido"):
            e = entrada_go()
            e["sustituto_gratis"] = s
            self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL", s)

    def test_sin_evidencia_e1_e2_en_el_locale_impide_GO(self):
        e = entrada_go()
        e["evidencia_locale"]["e1_o_e2"] = 0
        self.assertEqual(calc(e)["calculado"], "GO_CONDICIONAL")

    def test_marca_personal_cuenta_0_6_y_los_servicios_no_cuentan(self):
        e = base_entrada()
        e["operadores"] = operadores_sostenidos(["M1", "M2", "M4"], tipo="marca_personal_escalera") + \
            [dict(op_, operador_id="op-09", tipo_anunciante="servicio") for op_ in operadores_sostenidos(["M5"])]
        e["huecos"] = hueco()
        m = M.calcular(e, PARAMS)
        self.assertEqual((m["n_ind_sost"], m["n_ind_sostenidos_entero"]), ("1.8", 1))
        self.assertNotEqual(calc(e)["calculado"], "GO")

    def test_hueco_de_localizacion_nunca_es_GO(self):
        e = entrada_go()
        e["operadores"] = operadores_sostenidos(["M1", "M2"])
        e["hueco_localizacion"] = {"pais_referencia": "US", "sostenidos_pais_referencia_mismo_concepto": 3}
        r = calc(e)
        self.assertEqual(r["calculado"], "GO_CONDICIONAL")
        self.assertTrue(r["hueco_de_localizacion"])

    def test_no_hay_conteo_bruto_en_la_entrada_que_mueva_el_veredicto(self):
        a, b = entrada_go(), entrada_go()
        b["mercado_resumen"]["anuncios_activos"] = 100000
        self.assertEqual(calc(a)["calculado"], calc(b)["calculado"])
        self.assertEqual(calc(a)["metricas"]["IS"], calc(b)["metricas"]["IS"])


class Entrada(unittest.TestCase):
    def test_evidencia_sin_url_o_fecha_se_rechaza(self):
        for roto in ({"id": "EV-01", "fecha": "2026-11-06"}, {"id": "EV-01", "url": "https://x.invalid/a"},
                     {"id": "EV-01", "url": "http://x.invalid/a", "fecha": "2026-11-06"},
                     {"id": "EV-01", "url": "https://x.invalid/a", "fecha": "ayer"}):
            e = entrada_go()
            e["evidencias"][0] = roto
            with self.assertRaises(P.ErrorValidacion):
                M.calcular(e, PARAMS)

    def test_concepto_con_evidencia_inexistente_se_rechaza(self):
        e = entrada_go()
        e["operadores"][0]["conceptos"][0]["evidencia_id"] = "EV-99"
        with self.assertRaises(P.ErrorValidacion):
            M.calcular(e, PARAMS)

    def test_bajar_el_riesgo_heredado_se_rechaza(self):
        e = entrada_go()
        e["riesgo"]["heredado"] = {"P": "amarillo", "C": "verde", "E": "verde", "N": "verde", "nivel": "amarillo", "subnivel": "A"}
        with self.assertRaises(P.ErrorValidacion):
            M.calcular(e, PARAMS)
        e["riesgo"]["heredado"].update({"nivel": "amarillo", "subnivel": "B"})
        e["riesgo"]["final"] = {"nivel": "amarillo", "subnivel": "A"}
        with self.assertRaises(P.ErrorValidacion):
            M.calcular(e, PARAMS)

    def test_concepto_id_con_guion_bajo_se_rechaza(self):
        e = entrada_go()
        e["operadores"][0]["conceptos"][0]["concepto_id"] = "c_11"
        with self.assertRaises(P.ErrorValidacion):
            M.calcular(e, PARAMS)

    def test_float_en_parametros_se_rechaza_y_falta_de_clave_falla_cerrado(self):
        with self.assertRaises(P.ErrorValidacion):
            P.dec(0.6)
        p = dict(PARAMS)
        del p["umbral_ss"]
        with self.assertRaises(P.ErrorLimite):
            M.calcular(entrada_go(), p)


def _validacion_desde(e, r, **over):
    m = r["metricas"]
    v = {"origen_version": "maker", "metricas_mercado": m["metricas_mercado"],
         "saturacion": {"indice": m["IS"]["indice"], "n_ind_sostenidos": m["n_ind_sostenidos_entero"],
                        "saturacion_mecanismo": m["saturacion_mecanismo"]["nivel"], "detalle": "x"},
         "convergencia": {"estado": m["convergencia"]["estado"], "detalle": "x"},
         "riesgo_politica": {"nivel": e["riesgo"]["final"]["nivel"]},
         "veredicto": {"calculado": r["calculado"], "propuesto": r["calculado"], "final": r["calculado"],
                       "confianza": {"puntos": m["confianza"]["puntos"], "detalle": "x"}, "razones": ["x"], "evidencia_faltante": []}}
    for k, val in over.items():
        v["veredicto"][k] = val
    return v


class Propuesta(unittest.TestCase):
    def setUp(self):
        self.e = entrada_go()
        self.r = calc(self.e)

    def test_coherente_pasa(self):
        self.assertEqual(V.comprobar(self.e, _validacion_desde(self.e, self.r), PARAMS), [])

    def test_el_maker_puede_degradar(self):
        self.assertEqual(V.comprobar(self.e, _validacion_desde(self.e, self.r, propuesto="GO_CONDICIONAL", final="GO_CONDICIONAL"), PARAMS), [])

    def test_el_maker_no_puede_mejorar_S11(self):
        e = entrada_go()
        e["operadores"] = operadores_sostenidos(["M1", "M2"])
        r = calc(e)
        self.assertEqual(r["calculado"], "GO_CONDICIONAL")
        v = _validacion_desde(e, r, propuesto="GO", final="GO")
        errs = V.comprobar(e, v, PARAMS)
        self.assertTrue(any("MEJORA" in x for x in errs) and any("origen_version=humano" in x for x in errs), errs)
        v["origen_version"] = "humano"  # el dueño puede mejorar el final, pero el propuesto del Maker nunca
        errs = V.comprobar(e, v, PARAMS)
        self.assertFalse(any("origen_version=humano" in x for x in errs))
        self.assertTrue(any("MEJORA" in x for x in errs))

    def test_diferencias_en_metricas_se_detectan(self):
        v = _validacion_desde(self.e, self.r)
        v["saturacion"]["indice"] += 1
        v["veredicto"]["confianza"]["puntos"] = 40
        self.assertEqual(len(V.comprobar(self.e, v, PARAMS)), 2)

    def test_riesgo_politica_no_puede_diferir_del_final(self):
        v = _validacion_desde(self.e, self.r)
        v["riesgo_politica"]["nivel"] = "amarillo"
        self.assertTrue(V.comprobar(self.e, v, PARAMS))


def _aleatoria(rng: random.Random) -> dict:
    e = base_entrada()
    tipos = ["producto_digital", "curso_mentoria", "marca_personal_escalera", "software", "servicio", "afiliado_reventa", "otro"]
    mecs = [f"M{i}" for i in range(1, 9)]
    angs = ["a1", "a2", "a3", "a4", "calendario-cuotas"]
    paises = ["IT", "ES", "PL"]
    e["paises_consultados"] = rng.sample(paises, rng.randint(1, 3))
    e["operadores"] = []
    for i in range(rng.randint(0, 9)):
        cs = [conc(f"c{i}{j}", rng.choice(mecs), rng.choice(angs), rng.randint(0, 150), activo=rng.random() > 0.15) for j in range(rng.randint(1, 5))]
        e["operadores"].append(op(f"op-{i:02d}", rng.choice(tipos), cs, paises=rng.sample(paises, rng.randint(1, 3)),
                                  embudo=rng.choice(["0", "0.5", "1"]), truncado=rng.random() > 0.8, leidos=rng.randint(0, 6),
                                  primer=rng.randint(0, 200)))
    e["mu"] = {"tipo_mecanismo": rng.choice(mecs), "indistinguible_de_sostenido": rng.random() > 0.9, "evidencia_id": "EV-03"}
    e["angulo_recomendado"] = rng.choice(angs)
    e["diferenciador_sustentado"] = rng.random() > 0.5
    ids = [o["operador_id"] for o in e["operadores"]]
    e["huecos"] = [{"hueco_id": "h-01", "descripcion": "x", "presente_en": rng.sample(ids, rng.randint(0, len(ids))),
                    "frases": rng.randint(0, 9), "fuentes": rng.randint(0, 5), "evidencia_id": "EV-02"}]
    e["sustituto_gratis"] = rng.choice(["no_dominante", "diferenciado", "dominante", "no_medido"])
    e["lectura_snapshots"] = rng.choice(["humano_muestreo", "navegador_auto", "ninguno", "pendiente_humano"])
    e["evidencia_locale"] = {"e1_o_e2": rng.randint(0, 3)}
    n = rng.randint(5, 60)
    e["voz"] = {"frases_total": n, "frases_propias": rng.randint(0, n), "frases_del_locale": rng.randint(0, n),
                "fuentes": {"f1": rng.randint(0, 20), "f2": rng.randint(0, 20), "f3": rng.randint(0, 20)}}
    prof = rng.randint(0, 8)
    e["confianza_datos"] = {"competidores_profundos": prof, "competidores_con_snapshot_leido": rng.randint(0, prof),
                            "landings_analizadas": rng.randint(0, 6), "consultas_distintas": rng.randint(0, 16),
                            "segunda_pasada": rng.random() > 0.3, "videos_total": rng.randint(0, 6), "videos_transcriptos": 0,
                            "relectura_realizada": rng.random() > 0.5, "historial_dias": rng.choice([None, 0, 3, 7, 20]),
                            "jaccard_replica": rng.choice([None, "0.2", "0.5", "0.9"])}
    e["confianza_datos"]["videos_transcriptos"] = rng.randint(0, e["confianza_datos"]["videos_total"])
    nivel = rng.choice(["verde", "amarillo", "rojo"])
    sub = rng.choice(["A", "B"]) if nivel == "amarillo" else None
    e["riesgo"]["heredado"] = {"P": "verde", "C": "verde", "E": "verde", "N": "verde", "nivel": "verde", "subnivel": None}
    e["riesgo"]["final"] = {"nivel": nivel, "subnivel": sub}
    e["riesgo"]["angulo_seguro_existe"] = rng.random() > 0.1
    e["riesgo"]["reencuadre_verificable_x1"] = rng.random() > 0.7
    e["riesgo"]["x1_dictamen"] = rng.choice(["PASS", "PASS_CON_NOTAS", "FAIL", "pendiente"])
    if rng.random() > 0.8:
        e["hueco_localizacion"] = {"pais_referencia": "US", "sostenidos_pais_referencia_mismo_concepto": rng.randint(0, 5)}
    return e


def _perturbada(rng: random.Random) -> dict:
    """Parte de un caso GO y perturba pocos campos: ejercita las fronteras del veredicto."""
    e = entrada_go()
    if rng.random() < 0.3:
        e["sustituto_gratis"] = rng.choice(["no_dominante", "dominante", "no_medido"])
    if rng.random() < 0.3:
        e["lectura_snapshots"] = rng.choice(["ninguno", "pendiente_humano", "navegador_auto"])
    if rng.random() < 0.3:
        e["huecos"] = hueco(presente=rng.sample(["op-01", "op-02", "op-03", "op-04"], rng.randint(0, 4)), frases=rng.randint(3, 7))
    if rng.random() < 0.3:
        e["mu"]["tipo_mecanismo"] = rng.choice(["M1", "M2", "M7", "M3"])
    if rng.random() < 0.3:
        e["confianza_datos"]["competidores_con_snapshot_leido"] = rng.randint(0, 5)
        e["confianza_datos"]["segunda_pasada"] = rng.random() > 0.2
    if rng.random() < 0.3:
        e["riesgo"]["final"] = rng.choice([{"nivel": "amarillo", "subnivel": "A"}, {"nivel": "amarillo", "subnivel": "B"}, {"nivel": "rojo", "subnivel": None}])
        e["riesgo"]["reencuadre_verificable_x1"] = rng.random() > 0.5
    if rng.random() < 0.3:
        e["operadores"] = e["operadores"][: rng.randint(0, 4)]
    if rng.random() < 0.2:
        e["voz"].update({"frases_total": rng.randint(5, 40), "frases_propias": rng.randint(0, 15), "frases_del_locale": 5})
    if rng.random() < 0.2:
        e["angulo_recomendado"] = "flujo-mensual"
        e["diferenciador_sustentado"] = rng.random() > 0.5
    return e


class Independencia(unittest.TestCase):
    def test_qa_recomputar_coincide_con_metricas_y_veredicto_en_600_casos(self):
        rng = random.Random(20261106)
        distintos = set()
        for i in range(600):
            e = _aleatoria(rng) if i % 3 else _perturbada(rng)
            r = V.calcular(e, PARAMS)
            val = _validacion_desde(e, r)
            self.assertEqual(Q.comparar(e, val, PARAMS, r["metricas"]), [], f"caso {i}")
            distintos.add(r["calculado"])
            # el recálculo independiente coincide SS_a a SS_a
            self.assertEqual(Q.recomputar(e, PARAMS)["calculado"], r["calculado"], f"caso {i}")
        self.assertEqual(distintos, {"GO", "GO_CONDICIONAL", "NO_GO"}, "el generador debe ejercitar los tres veredictos")

    def test_qa_recomputar_detecta_un_indice_adulterado(self):
        e = entrada_go()
        r = calc(e)
        val = _validacion_desde(e, r)
        val["saturacion"]["indice"] -= 5
        self.assertTrue(Q.comparar(e, val, PARAMS))

    def test_qa_recomputar_reproduce_los_vectores_de_la_spec(self):
        e = base_entrada()
        e["operadores"] = [op("op-01", "producto_digital", [conc("c1", "M1", "a", 60)], embudo="0")]
        self.assertEqual(Q.recomputar(e, PARAMS)["ss"]["op-01"], "0.233")
        e["operadores"] = [op("op-01", "producto_digital", [conc(f"c{i}", "M1", "a", 90) for i in range(3)])]
        self.assertEqual(Q.recomputar(e, PARAMS)["ss"]["op-01"], "0.675")


class Citas(unittest.TestCase):
    def _voz(self, **fr):
        f = {"frase_id": "f-01", "texto_literal": "non riesco a capire quanto mi resta da pagare ogni mese", "locale": "it-IT",
             "pais": "IT", "fuente_url": "https://foro.ejemplo.invalid/hilo/123", "fecha": "2026-10-20", "categoria": "dolor",
             "tema": "cuotas", "origen": "d2", "crudo_ref": "crudo/voz/hilo-123.txt"}
        f.update(fr)
        return {"frases": [f], "temas": ["cuotas"], "objeciones": [], "lexico": ["rata"]}

    def _con_crudo(self, texto, voz):
        d = tempfile.TemporaryDirectory()
        base = Path(d.name)
        (base / "crudo" / "voz").mkdir(parents=True)
        (base / "crudo" / "voz" / "hilo-123.txt").write_text(texto, encoding="utf-8")
        self.addCleanup(d.cleanup)
        return VC.verificar(voz, "it-IT", base, PARAMS)

    def test_cita_literal_en_el_crudo_se_verifica(self):
        r = self._con_crudo("Ciao a tutti.  Non riesco a capire QUANTO mi resta da pagare ogni mese!!", self._voz())
        self.assertEqual((r["verificadas"], r["fabricadas"], r["falla"]), (1, 0, []))

    def test_cita_fabricada_falla(self):
        r = self._con_crudo("otro texto que no contiene la frase", self._voz())
        self.assertEqual(r["fabricadas"], 1)
        self.assertTrue(r["falla"])

    def test_pii_falla(self):
        for txt in ("scrivimi a mario.rossi@example.com", "chiamami al +39 333 1234567", "seguimi su @mario_r", "vai su https://x.invalid"):
            r = self._con_crudo(txt, self._voz(texto_literal=txt))
            self.assertTrue(any(f["problema"].startswith("PII") for f in r["fallas"]), txt)
            self.assertTrue(r["falla"])

    def test_mas_de_25_palabras_es_falla_mayor(self):
        txt = " ".join(["parola"] * 26)
        r = self._con_crudo(txt, self._voz(texto_literal=txt))
        self.assertTrue(any(f["problema"].startswith("mas_de_") for f in r["fallas"]))

    def test_fuente_perfil_o_sin_https_falla(self):
        for url in ("https://red.ejemplo.invalid/user/mario", "https://red.ejemplo.invalid/@mario", "http://foro.ejemplo.invalid/hilo/1", None):
            r = self._con_crudo("non riesco a capire quanto mi resta da pagare ogni mese", self._voz(fuente_url=url))
            self.assertTrue(r["falla"], url)

    def test_sin_crudo_es_no_verificable_y_supera_el_5_por_ciento(self):
        v = self._voz()
        del v["frases"][0]["crudo_ref"]
        r = VC.verificar(v, "it-IT", None, PARAMS)
        self.assertEqual((r["no_verificables"], bool(r["falla"])), (1, True))

    def test_crudo_ref_fuera_de_la_carpeta_falla(self):
        r = self._con_crudo("x", self._voz(crudo_ref="../../etc/passwd"))
        self.assertTrue(any("fuera_de_la_carpeta" in f["problema"] for f in r["fallas"]))

    def test_pii_en_objeciones_o_en_otros_archivos(self):
        v = self._voz()
        v["objeciones"] = ["scrivete a pippo@example.com"]
        self.assertTrue(self._con_crudo("non riesco a capire quanto mi resta da pagare ogni mese", v)["falla"])


class Cli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([PY, *map(str, args)], capture_output=True, text=True, cwd=RAIZ)

    def test_plantillas_son_coherentes_de_punta_a_punta(self):
        t = SKILL / "templates"
        ent, val = t / "metricas_entrada.json", t / "validacion.json"
        self.assertTrue(ent.is_file() and val.is_file(), "faltan templates/metricas_entrada.json y templates/validacion.json")
        r = self._run(SCRIPTS / "metricas.py", ent)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._run(SCRIPTS / "veredicto.py", "comprobar", ent, val)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self._run(SCRIPTS / "qa_recomputar.py", ent, val)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_parametro_faltante_sale_con_5(self):
        with tempfile.TemporaryDirectory() as d:
            ent = SKILL / "templates" / "metricas_entrada.json"
            vacio = Path(d) / "p.yaml"
            vacio.write_text("grupos:\n  validacion: {}\n", encoding="utf-8")
            r = self._run(SCRIPTS / "metricas.py", ent, "--parametros", vacio)
            # `--parametros` reemplaza solo el archivo oficial: lo que falta allí lo cubre la propuesta de la skill,
            # pero las claves oficiales (umbral_ss, …) no están en la propuesta → falla cerrado.
            self.assertEqual(r.returncode, 5, r.stderr)

    def test_dorados_y_vectores(self):
        v = json.loads((SKILL / "evals" / "vectores_dorados.json").read_text(encoding="utf-8"))
        for caso in v["casos"]:
            ruta = SKILL / "evals" / "dorados" / caso["entrada"]
            e = json.loads(ruta.read_text(encoding="utf-8"))
            r = V.calcular(e, PARAMS)
            self.assertEqual(r["calculado"], caso["esperado"]["calculado"], caso["id"])
            for k, val in caso["esperado"].get("metricas", {}).items():
                m = r["metricas"]
                actual = {"IS": m["IS"]["indice"], "saturacion_mecanismo": m["saturacion_mecanismo"]["nivel"],
                          "convergencia": m["convergencia"]["estado"], "confianza_puntos": m["confianza"]["puntos"],
                          "n_ind_sost": m["n_ind_sost"], "n_sostenidos": m["metricas_mercado"]["n_sostenidos"]}[k]
                self.assertEqual(actual, val, f"{caso['id']}:{k}")
            self.assertEqual(Q.recomputar(e, PARAMS)["calculado"], caso["esperado"]["calculado"], caso["id"])


if __name__ == "__main__":
    unittest.main()
