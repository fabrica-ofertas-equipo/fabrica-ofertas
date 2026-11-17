"""Pruebas de scripts/modelado/puntaje_modelar.py (D1, Modo D).

Sin red: se bloquea `socket.socket` en cada prueba. Los parámetros salen de
tests/fixtures/modelado/parametros.yaml y los casos del corpus de tests/fixtures/modelado/fichas_corpus.json.
Los valores esperados de las fórmulas se calculan aquí de forma independiente (con float, solo en pruebas).
"""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

from scripts.modelado import puntaje_modelar as pm

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "modelado"
PARAMETROS = FIXTURES / "parametros.yaml"
CORPUS = FIXTURES / "fichas_corpus.json"

PUERTAS_LIMPIAS = {g: False for g in pm.PUERTAS}


def oferta_base(**cambios):
    """Oferta válida con T = H = X = D = 1 (PM = 100) para modificar caso por caso."""
    oferta = {
        "modelo_id": "base",
        "nombre": "Oferta base",
        "fuente": {"idioma": "en", "pais": "US"},
        "macro_nicho": "salud",
        "traccion": {"anuncios_activos": 25, "edad_oferta_dias": 14, "conceptos_unicos": 3,
                     "paginas_misma_landing": 2, "anunciantes_independientes_mismo_angulo": 0},
        "puertas": dict(PUERTAS_LIMPIAS),
        "reencuadres": ["mecanismo_nombrable", "lista_a_sistema"],
        "mercados": [{
            "mercado": "RO", "idioma": "ro",
            "hueco": {"original_presente": False, "anunciantes_sostenidos": 0, "puntaje_rival": None,
                      "entrantes_30d": 0},
            "ventana": "evergreen",
            "transferibilidad": {k: "1" for k in pm.TRANSFERIBILIDAD},
        }],
    }
    oferta.update(copy.deepcopy(cambios))
    return oferta


def documento(*ofertas):
    return {"schema_version": "2.0.0", "ofertas": list(ofertas)}


class Base(unittest.TestCase):
    """Bloquea la red y carga los parámetros de prueba una vez."""

    @classmethod
    def setUpClass(cls):
        cls.p = pm.cargar_parametros(PARAMETROS)
        cls.corpus = pm.leer_json(CORPUS)

    def setUp(self):
        parche = mock.patch("socket.socket", side_effect=AssertionError("las pruebas no usan red"))
        parche.start()
        self.addCleanup(parche.stop)

    def par(self, oferta, indice=0):
        """Puntúa el par `indice` de una oferta (pasando por la validación completa)."""
        return pm.puntuar(documento(oferta), self.p)[indice]

    def pares_corpus(self):
        return {(x["modelo_id"], x["mercado"]): x for x in pm.puntuar(copy.deepcopy(self.corpus), self.p)}


class PruebaParametros(Base):
    def test_carga_todos_los_parametros_del_fixture(self):
        self.assertEqual(set(self.p), set(pm.CLAVES_PARAMETROS))

    def test_falla_cerrado_si_falta_un_parametro(self):
        texto = PARAMETROS.read_text(encoding="utf-8").replace(
            "modelado_umbral_pasa:", "modelado_otra_cosa:")
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "p.yaml"
            ruta.write_text(texto, encoding="utf-8")
            with self.assertRaises(pm.ErrorLimite) as ctx:
                pm.cargar_parametros(ruta)
        self.assertIn("modelado_umbral_pasa", str(ctx.exception))
        self.assertEqual(ctx.exception.codigo_salida, 5)

    def test_falla_cerrado_si_no_existe_el_archivo(self):
        with self.assertRaises(pm.ErrorLimite):
            pm.cargar_parametros(Path("/no/existe/parametros.yaml"))

    def test_sin_ruta_lee_empresa_parametros_bajo_la_raiz(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FABRICA_RAIZ": tmp}):
            with self.assertRaises(pm.ErrorLimite):
                pm.cargar_parametros()

    def test_pesos_que_no_suman_uno_son_error(self):
        crudos = {k: self.p[k] for k in pm.CLAVES_PARAMETROS}
        crudos["modelado_peso_hueco"] = "0.40"
        with self.assertRaises(pm.ErrorValidacion):
            pm.normalizar_parametros(crudos)

    def test_rechaza_float_en_parametros(self):
        crudos = {k: self.p[k] for k in pm.CLAVES_PARAMETROS}
        crudos["modelado_replica_baja"] = 0.5
        with self.assertRaises(pm.ErrorValidacion):
            pm.normalizar_parametros(crudos)

    def test_rechaza_valores_fuera_de_rango(self):
        crudos = {k: self.p[k] for k in pm.CLAVES_PARAMETROS}
        crudos["modelado_umbral_pasa"] = 101
        with self.assertRaises(pm.ErrorValidacion):
            pm.normalizar_parametros(crudos)


class PruebaTraccion(Base):
    def t(self, **cambios):
        traccion = dict(oferta_base()["traccion"], **cambios)
        return pm.calcular_traccion(traccion, self.p)[0]

    def test_el_objetivo_exacto_da_uno(self):
        self.assertEqual(self.t(), Decimal(1))

    def test_sin_replica_aplica_el_valor_bajo(self):
        esperado = 0.5 ** 0.25
        self.assertAlmostEqual(float(self.t(paginas_misma_landing=1)), esperado, places=9)

    def test_dos_anunciantes_independientes_cuentan_como_replica(self):
        self.assertEqual(self.t(paginas_misma_landing=1, anunciantes_independientes_mismo_angulo=2), Decimal(1))

    def test_sin_anuncios_la_traccion_es_cero(self):
        self.assertEqual(self.t(anuncios_activos=0, conceptos_unicos=0, paginas_misma_landing=0), Decimal(0))

    def test_crece_con_el_volumen_y_se_satura(self):
        valores = [self.t(anuncios_activos=a) for a in (5, 10, 20, 25, 100)]
        self.assertEqual(valores, sorted(valores))
        self.assertEqual(valores[-1], valores[-2])

    def test_crece_con_la_edad(self):
        self.assertLess(self.t(edad_oferta_dias=3), self.t(edad_oferta_dias=10))


class PruebaHueco(Base):
    def h(self, ventana="evergreen", **hueco):
        base = {"original_presente": False, "anunciantes_sostenidos": 0, "puntaje_rival": None, "entrantes_30d": 0}
        base.update(hueco)
        return pm.calcular_hueco(base, ventana, self.p)[0]

    def test_sin_competencia_ni_entrantes_es_uno(self):
        self.assertEqual(self.h(), Decimal(1))

    def test_el_original_presente_cierra_el_hueco(self):
        self.assertEqual(self.h(original_presente=True), Decimal(0))

    def test_tres_sostenidos_cierran_el_hueco_y_dos_no(self):
        self.assertEqual(self.h(anunciantes_sostenidos=3, puntaje_rival=10), Decimal(0))
        self.assertGreater(self.h(anunciantes_sostenidos=2, puntaje_rival=10), Decimal(0))

    def test_rival_debil_justo_bajo_el_corte_y_fuerte_en_el_corte(self):
        self.assertEqual(self.h(anunciantes_sostenidos=1, puntaje_rival=49), Decimal("0.5"))
        self.assertEqual(self.h(anunciantes_sostenidos=1, puntaje_rival=50), Decimal("0.25"))

    def test_entrantes_en_el_tope_dan_cero_y_a_la_mitad_dan_proporcional(self):
        self.assertEqual(self.h(entrantes_30d=5), Decimal(0))
        self.assertEqual(self.h(entrantes_30d=2), Decimal("0.6"))

    def test_ventanas_estacionales(self):
        self.assertEqual(self.h("vencida"), Decimal(0))
        self.assertEqual(self.h("cierra_pronto"), Decimal("0.5"))
        self.assertEqual(self.h("abierta"), Decimal(1))
        self.assertEqual(self.h("evergreen"), Decimal(1))

    def test_entrantes_sin_medir_dejan_la_ficha_incompleta_y_nunca_cuentan_como_cero(self):
        oferta = oferta_base()
        oferta["mercados"][0]["hueco"]["entrantes_30d"] = None
        par = self.par(oferta)
        self.assertEqual(par["estado"], "incompleta")
        self.assertIsNone(par["PM"])
        self.assertIsNone(par["factores"]["H"])
        self.assertIn("hueco.entrantes_30d", par["pendientes"])
        self.assertEqual(par["techo"], Decimal(100))  # lo máximo que podría valer una vez medido

    def test_el_techo_respeta_lo_ya_medido_aunque_falten_los_entrantes(self):
        oferta = oferta_base()
        oferta["mercados"][0]["hueco"].update(entrantes_30d=None, original_presente=True)
        par = self.par(oferta)
        self.assertEqual(par["estado"], "incompleta")
        self.assertEqual(par["techo"], Decimal(0))  # el hueco ya está cerrado, falte o no el dato

    def test_calcular_hueco_devuelve_none_y_techo_sin_entrantes(self):
        hueco = {"original_presente": False, "anunciantes_sostenidos": 0, "puntaje_rival": None,
                 "entrantes_30d": None}
        h, sub, techo = pm.calcular_hueco(hueco, "cierra_pronto", self.p)
        self.assertIsNone(h)
        self.assertIsNone(sub["h_entrantes"])
        self.assertEqual(techo, Decimal("0.5"))

    def test_rival_sostenido_sin_puntaje_del_auditor_es_error_de_validacion(self):
        oferta = oferta_base()
        oferta["mercados"][0]["hueco"].update(anunciantes_sostenidos=1, puntaje_rival=None)
        with self.assertRaises(pm.ErrorValidacion) as ctx:
            pm.puntuar(documento(oferta), self.p)
        self.assertIn("puntaje_rival", str(ctx.exception))


class PruebaDiferenciacionYTransferibilidad(Base):
    def test_d_segun_cantidad_de_reencuadres(self):
        self.assertEqual(pm.calcular_diferenciacion([], self.p), Decimal("0.4"))
        self.assertEqual(pm.calcular_diferenciacion(["lista_a_sistema"], self.p), Decimal("0.7"))
        self.assertEqual(pm.calcular_diferenciacion(["lista_a_sistema", "cambio_de_unidad"], self.p), Decimal("1.0"))

    def test_un_reencuadre_repetido_cuenta_una_vez(self):
        self.assertEqual(pm.calcular_diferenciacion(["lista_a_sistema"] * 3, self.p), Decimal("0.7"))

    def test_los_reencuadres_del_mercado_se_suman_a_los_de_la_oferta(self):
        oferta = oferta_base(reencuadres=["mecanismo_nombrable"])
        oferta["mercados"][0]["reencuadres_mercado"] = ["autoridad_local"]
        self.assertEqual(self.par(oferta)["factores"]["D"], Decimal("1.0"))

    def test_reencuadre_desconocido_es_error(self):
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta_base(reencuadres=["inventado"])), self.p)

    def test_x_es_media_geometrica_de_tres_componentes(self):
        x = {"dolor_universal": Decimal("0.8"), "viabilidad_ticket": Decimal("0.8"), "riesgo_politicas": Decimal("0.7")}
        self.assertAlmostEqual(float(pm.calcular_transferibilidad(x)), (0.8 * 0.8 * 0.7) ** (1 / 3), places=9)

    def test_la_producibilidad_ya_no_es_una_regla(self):
        # El dueño la quitó el 2026-11-06: una ficha con ese campo se rechaza como campo desconocido.
        self.assertNotIn("producibilidad", pm.TRANSFERIBILIDAD)
        oferta = oferta_base()
        oferta["mercados"][0]["transferibilidad"]["producibilidad"] = "0.2"
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta), self.p)

    def test_un_componente_en_cero_anula_x_y_uno_nulo_lo_deja_sin_evaluar(self):
        x = {k: Decimal("0.8") for k in pm.TRANSFERIBILIDAD}
        self.assertEqual(pm.calcular_transferibilidad({**x, "viabilidad_ticket": Decimal(0)}), Decimal(0))
        self.assertIsNone(pm.calcular_transferibilidad({**x, "viabilidad_ticket": None}))


class PruebaFormula(Base):
    def test_todo_en_uno_da_cien(self):
        par = self.par(oferta_base())
        self.assertEqual(par["PM"], Decimal(100))
        self.assertEqual(par["estado"], "pasa")

    def test_coincide_con_el_calculo_independiente(self):
        par = self.pares_corpus()[("desayunos-365-diabeticos", "AR")]
        x = (0.9 * 0.8 * 0.5) ** (1 / 3)
        h = 0.25 * (1 - 2 / 5) * 1
        esperado = 100 * (1.0 ** 0.25) * (h ** 0.35) * (x ** 0.20) * (1.0 ** 0.20)
        self.assertAlmostEqual(float(par["PM"]), esperado, places=6)

    def test_el_umbral_decide_pasa_o_no_pasa(self):
        alto = dict(self.p, modelado_umbral_pasa=100)
        par = pm.puntuar(documento(oferta_base(reencuadres=["lista_a_sistema"])), alto)[0]  # D = 0.7
        self.assertEqual(par["estado"], "no_pasa")
        bajo = dict(self.p, modelado_umbral_pasa=90)
        par = pm.puntuar(documento(oferta_base(reencuadres=["lista_a_sistema"])), bajo)[0]
        self.assertEqual(par["estado"], "pasa")

    def test_orden_completas_luego_incompletas_luego_vetadas(self):
        pares = pm.puntuar(copy.deepcopy(self.corpus), self.p)
        grupos = [{"pasa": 0, "no_pasa": 0, "incompleta": 1, "vetada": 2}[x["estado"]] for x in pares]
        self.assertEqual(grupos, sorted(grupos))
        completos = [x["PM"] for x in pares if x["estado"] in ("pasa", "no_pasa")]
        self.assertEqual(completos, sorted(completos, reverse=True))

    def test_todo_pm_esta_entre_cero_y_cien(self):
        for x in pm.puntuar(copy.deepcopy(self.corpus), self.p):
            if x["PM"] is not None:
                self.assertTrue(Decimal(0) <= x["PM"] <= Decimal(100), x["modelo_id"])

    def test_solo_marco_descarta_lo_que_no_es_salud_relaciones_dinero(self):
        pares = pm.puntuar(copy.deepcopy(self.corpus), self.p, solo_marco=True)
        self.assertTrue(pares)
        self.assertTrue(all(x["macro_nicho"] in pm.MACRO_NICHOS for x in pares))

    def test_el_cuello_es_el_factor_mas_bajo(self):
        par = self.pares_corpus()[("trusa-3r", "ES")]
        self.assertEqual(par["cuello"], "H")


class PruebaPuertas(Base):
    def test_cada_puerta_en_true_veta_y_deja_pm_en_cero(self):
        for puerta in pm.PUERTAS:
            with self.subTest(puerta=puerta):
                oferta = oferta_base()
                oferta["puertas"][puerta] = True
                par = self.par(oferta)
                self.assertEqual(par["estado"], "vetada")
                self.assertEqual(par["PM"], Decimal(0))
                self.assertEqual(par["techo"], Decimal(0))
                self.assertEqual(par["vetos"], [puerta])

    def test_una_puerta_sin_evaluar_deja_la_ficha_incompleta_con_techo(self):
        oferta = oferta_base()
        oferta["puertas"]["marca_personal"] = None
        par = self.par(oferta)
        self.assertEqual(par["estado"], "incompleta")
        self.assertIsNone(par["PM"])
        self.assertEqual(par["techo"], Decimal(100))
        self.assertIn("marca_personal", par["pendientes"])

    def test_el_veto_gana_a_lo_pendiente(self):
        oferta = oferta_base()
        oferta["puertas"].update(marca_personal=True, sustituto_gratis_cubre=None)
        self.assertEqual(self.par(oferta)["estado"], "vetada")

    def test_una_puerta_con_texto_en_vez_de_booleano_es_error(self):
        oferta = oferta_base()
        oferta["puertas"]["marca_personal"] = "no"
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta), self.p)


class PruebaCorpus(Base):
    """Los casos de los mentores deben comportarse como ellos dicen que se comportan."""

    def test_trusa_en_rumania_y_polonia_pasa_y_encabeza_el_ranking(self):
        pares = pm.puntuar(copy.deepcopy(self.corpus), self.p)
        self.assertEqual({(pares[0]["modelo_id"], pares[0]["mercado"])}, {("trusa-3r", "RO")})
        corp = self.pares_corpus()
        self.assertEqual(corp[("trusa-3r", "RO")]["estado"], "pasa")
        self.assertEqual(corp[("trusa-3r", "PL")]["estado"], "pasa")

    def test_trusa_en_italia_francia_y_alemania_muere_por_hueco(self):
        corp = self.pares_corpus()
        for mercado in ("IT", "FR", "DE"):
            with self.subTest(mercado=mercado):
                par = corp[("trusa-3r", mercado)]
                self.assertEqual(par["factores"]["H"], Decimal(0))
                self.assertEqual(par["PM"], Decimal(0))
                self.assertEqual(par["estado"], "no_pasa")

    def test_el_recetario_generico_muere_por_saturacion(self):
        par = self.pares_corpus()[("recetario-generico", "AR")]
        self.assertEqual(par["PM"], Decimal(0))
        self.assertEqual(par["cuello"], "H")

    def test_desayunos_en_argentina_no_pasa_pese_a_un_buen_reencuadre(self):
        par = self.pares_corpus()[("desayunos-365-diabeticos", "AR")]
        self.assertEqual(par["factores"]["D"], Decimal("1.0"))
        self.assertEqual(par["estado"], "no_pasa")
        self.assertEqual(par["cuello"], "H")

    def test_goma_eva_y_marca_personal_quedan_vetadas(self):
        corp = self.pares_corpus()
        self.assertEqual(corp[("megapack-goma-eva", "ES")]["vetos"], ["practica_vetada"])
        self.assertEqual(corp[("curso-ejercicio-influencer", "IT")]["vetos"], ["marca_personal"])

    def test_una_oferta_con_comunidad_ya_no_se_veta_porque_el_dueno_quito_esa_regla(self):
        # Decisión del dueño (2026-11-06): «exige comunidad o app» ya no es una regla.
        par = self.pares_corpus()[("curso-con-comunidad-whatsapp", "ES")]
        self.assertEqual(par["vetos"], [])
        self.assertIn(par["estado"], ("pasa", "no_pasa"))
        self.assertNotIn("requiere_comunidad_o_vivo_o_app", pm.PUERTAS)
        self.assertNotIn("commodity_facil_de_modelar", pm.PUERTAS)

    def test_las_unicas_puertas_son_marca_personal_sustituto_gratis_y_practica_vetada(self):
        self.assertEqual(pm.PUERTAS, ("marca_personal", "sustituto_gratis_cubre", "practica_vetada"))

    def test_el_kit_de_bricolaje_muere_porque_todos_lo_van_a_lanzar(self):
        par = self.pares_corpus()[("kit-bricolaje-madera", "FR")]
        self.assertEqual(par["subfactores"]["h_entrantes"], Decimal(0))
        self.assertEqual(par["PM"], Decimal(0))

    def test_crochet_ya_localizado_al_italiano_no_pasa_pero_polonia_si(self):
        corp = self.pares_corpus()
        self.assertEqual(corp[("crochet-patrones-es", "IT")]["factores"]["H"], Decimal(0))
        self.assertEqual(corp[("crochet-patrones-es", "PL")]["estado"], "pasa")
        self.assertGreater(corp[("crochet-patrones-es", "PL")]["PM"], corp[("crochet-patrones-es", "PT")]["PM"])

    def test_oferta_con_juicio_pendiente_queda_incompleta_y_con_techo_alto(self):
        par = self.pares_corpus()[("oferta-pendiente-de-landing", "PL")]
        self.assertEqual(par["estado"], "incompleta")
        self.assertIsNone(par["factores"]["X"])
        self.assertGreater(par["techo"], Decimal(90))
        self.assertIn("transferibilidad.riesgo_politicas", par["pendientes"])

    def test_la_ventana_vencida_mata_la_oferta_de_navidad(self):
        doc = copy.deepcopy(self.corpus)
        navidad = next(o for o in doc["ofertas"] if o["modelo_id"] == "juegos-navidad")
        navidad["mercados"][0]["ventana"] = "vencida"
        par = next(x for x in pm.puntuar(doc, self.p) if x["modelo_id"] == "juegos-navidad")
        self.assertEqual(par["PM"], Decimal(0))

    def test_la_mayoria_de_las_ofertas_viables_cae_fuera_del_marco(self):
        pasan = [x for x in pm.puntuar(copy.deepcopy(self.corpus), self.p) if x["estado"] == "pasa"]
        fuera = [x for x in pasan if not x["en_marco"]]
        self.assertGreater(len(fuera), len(pasan) / 2)


class PruebaValidacionDeFichas(Base):
    def test_campo_faltante_indica_la_ruta(self):
        oferta = oferta_base()
        del oferta["traccion"]["conceptos_unicos"]
        with self.assertRaises(pm.ErrorValidacion) as ctx:
            pm.puntuar(documento(oferta), self.p)
        self.assertIn("ofertas[0].traccion", str(ctx.exception))
        self.assertIn("conceptos_unicos", str(ctx.exception))

    def test_campo_desconocido_es_error(self):
        oferta = oferta_base()
        oferta["traccion"]["ventas"] = 10
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta), self.p)

    def test_float_nativo_no_es_aceptado(self):
        oferta = oferta_base()
        oferta["mercados"][0]["transferibilidad"]["dolor_universal"] = 0.8
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta), self.p)

    def test_ratio_fuera_de_cero_a_uno_es_error(self):
        oferta = oferta_base()
        oferta["mercados"][0]["transferibilidad"]["dolor_universal"] = "1.2"
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta), self.p)

    def test_conceptos_mayores_que_anuncios_es_inconsistente(self):
        oferta = oferta_base()
        oferta["traccion"].update(anuncios_activos=2, conceptos_unicos=5)
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta), self.p)

    def test_ids_repetidos_y_mercados_repetidos_son_error(self):
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta_base(), oferta_base()), self.p)
        oferta = oferta_base()
        oferta["mercados"].append(copy.deepcopy(oferta["mercados"][0]))
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta), self.p)

    def test_macro_nicho_fuera_del_contrato_es_error_pero_null_es_valido(self):
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(documento(oferta_base(macro_nicho="otro")), self.p)
        self.assertFalse(self.par(oferta_base(macro_nicho=None))["en_marco"])

    def test_major_desconocida_se_rechaza(self):
        doc = documento(oferta_base())
        doc["schema_version"] = "3.0.0"
        with self.assertRaises(pm.ErrorValidacion):
            pm.puntuar(doc, self.p)


class PruebaSensibilidad(Base):
    def test_el_corpus_es_robusto(self):
        s = pm.sensibilidad(pm.puntuar(copy.deepcopy(self.corpus), self.p), self.p)
        self.assertEqual(s["estado"], "robusto")
        self.assertEqual(s["perturbaciones"], 8)
        self.assertEqual(s["cobertura"], Decimal(1))
        self.assertEqual(s["top1"], "trusa-3r@RO")

    def test_con_pocos_pares_es_insuficiente(self):
        pares = pm.puntuar(documento(oferta_base()), self.p)
        self.assertEqual(pm.sensibilidad(pares, self.p)["estado"], "insuficiente")

    def test_es_determinista(self):
        pares = pm.puntuar(copy.deepcopy(self.corpus), self.p)
        self.assertEqual(pm.sensibilidad(pares, self.p), pm.sensibilidad(pares, self.p))

    def test_un_ranking_cercano_se_declara_fragil(self):
        # Cuatro pares casi empatados con perfiles opuestos: bajar un peso mueve al líder fuera del top-1,
        # y con top = 1 la cobertura no puede llegar al 80 %.
        def par(identificador, t, h):
            f = {"T": Decimal(t), "H": Decimal(h), "X": Decimal("0.8"), "D": Decimal("0.8")}
            return {"modelo_id": identificador, "mercado": "RO", "estado": "pasa", "factores": f,
                    "PM": pm._combinar(f, pm._pesos(self.p))}
        pares = [par("a", "1.0", "0.6"), par("b", "0.6", "1.0"), par("c", "0.8", "0.8")]
        pares.sort(key=lambda x: -x["PM"])
        parametros = dict(self.p, modelado_sens_top=1)
        s = pm.sensibilidad(pares, parametros)
        self.assertEqual(s["estado"], "fragil")
        self.assertLess(s["cobertura"], Decimal("0.8"))


class PruebaResumirAnuncios(Base):
    AHORA = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)

    def fila(self, ident, pagina, titulo, dias):
        inicio = int(self.AHORA.timestamp()) - int(dias * 86400)
        return {"id": ident, "page_id": pagina, "ad_creative_link_title": titulo, "ad_delivery_start_time": inicio}

    def test_cuenta_edad_de_la_oferta_y_conceptos_con_titulos_normalizados(self):
        filas = [self.fila("1", 10, "Florería Tejida", 20), self.fila("2", 10, "  florería   TEJIDA ", 10),
                 self.fila("3", 10, "Navidad Tejida", 30), self.fila("4", 11, "Florería Tejida", 4)]
        r = pm.resumir_anuncios(filas, self.AHORA)
        self.assertEqual(r["anuncios_activos"], 4)
        self.assertEqual(r["conceptos_unicos"], 2)
        self.assertEqual(r["edad_max_dias"], Decimal(30))
        self.assertEqual(r["edad_oferta_dias"], Decimal(20))  # el 2.º más viejo: exige dos sobrevivientes
        self.assertEqual(r["mediana_dias_activos"], Decimal(15))  # solo informativa: mediana de 4, 10, 20, 30
        self.assertEqual(r["paginas"], 2)
        self.assertEqual(r["paginas_con_concepto_compartido"], 2)

    def test_ids_repetidos_se_descartan_con_advertencia(self):
        filas = [self.fila("1", 10, "A", 5), self.fila("1", 10, "A", 5)]
        r = pm.resumir_anuncios(filas, self.AHORA)
        self.assertEqual(r["anuncios_activos"], 1)
        self.assertTrue(any("repetido" in a for a in r["advertencias"]))

    def test_sin_titulo_cuenta_como_un_solo_concepto_y_no_cuenta_como_compartido(self):
        filas = [self.fila("1", 10, "", 5), self.fila("2", 11, None, 6)]
        r = pm.resumir_anuncios(filas, self.AHORA)
        self.assertEqual(r["conceptos_unicos"], 1)
        self.assertEqual(r["paginas_con_concepto_compartido"], 0)

    def test_inicio_en_el_futuro_se_fija_en_cero_con_advertencia(self):
        r = pm.resumir_anuncios([self.fila("1", 10, "A", -2)], self.AHORA)
        self.assertEqual(r["edad_max_dias"], Decimal(0))
        self.assertTrue(any("posterior" in a for a in r["advertencias"]))

    def test_un_solo_anuncio_no_tiene_sobrevivientes(self):
        r = pm.resumir_anuncios([self.fila("1", 10, "A", 40)], self.AHORA)
        self.assertEqual(r["edad_max_dias"], Decimal(40))
        self.assertEqual(r["edad_oferta_dias"], Decimal(0))
        self.assertTrue(any("sobrevivientes" in a for a in r["advertencias"]))

    def test_un_anuncio_zombi_no_infla_la_edad_de_la_oferta(self):
        filas = [self.fila("1", 10, "A", 200)] + [self.fila(str(i), 10, "A", 1) for i in range(2, 8)]
        self.assertEqual(pm.resumir_anuncios(filas, self.AHORA)["edad_oferta_dias"], Decimal(1))

    def test_ahora_sin_zona_y_filas_invalidas_son_error(self):
        with self.assertRaises(pm.ErrorUso):
            pm.resumir_anuncios([self.fila("1", 10, "A", 1)], datetime(2026, 11, 6))
        with self.assertRaises(pm.ErrorValidacion):
            pm.resumir_anuncios([], self.AHORA)
        with self.assertRaises(pm.ErrorValidacion):
            pm.resumir_anuncios([{"id": "1", "page_id": 1}], self.AHORA)

    def test_el_resumen_alimenta_el_bloque_traccion_de_una_ficha(self):
        filas = [self.fila(str(i), 10 + i % 2, f"concepto {i % 3}", 20) for i in range(30)]
        r = pm.resumir_anuncios(filas, self.AHORA)
        oferta = oferta_base(traccion={
            "anuncios_activos": r["anuncios_activos"], "edad_oferta_dias": r["edad_oferta_dias"],
            "conceptos_unicos": r["conceptos_unicos"], "paginas_misma_landing": r["paginas_con_concepto_compartido"],
            "anunciantes_independientes_mismo_angulo": 0})
        self.assertEqual(self.par(oferta)["factores"]["T"], Decimal(1))


class PruebaDatosReales(Base):
    """27 anuncios reales de «Crea y Emprende» (ES) leídos con ads_library_search el 2026-11-06T04:53Z.

    Datos públicos de la Biblioteca de Anuncios, sin datos personales. Regresión de un error de diseño
    hallado con estos datos: la mediana de días (0,8) castigaba a una página que renueva creativos a diario.
    """

    AHORA = datetime(2026, 11, 6, 4, 53, 45, tzinfo=timezone.utc)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.filas = pm.leer_json(FIXTURES / "filas_crea_y_emprende_es.json")
        cls.resumen = pm.resumir_anuncios(cls.filas, cls.AHORA)

    def test_reproduce_la_medicion_previa_de_la_investigacion(self):
        # 18d §0.5 midió 27 anuncios, 2 conceptos y el más viejo con 16,8 días.
        self.assertEqual(self.resumen["anuncios_activos"], 27)
        self.assertEqual(self.resumen["conceptos_unicos"], 2)
        self.assertEqual(self.resumen["edad_max_dias"].quantize(Decimal("0.1")), Decimal("16.8"))

    def test_edad_de_la_oferta_es_la_del_segundo_mas_viejo(self):
        inicios = sorted(int(f["ad_delivery_start_time"]) for f in self.filas)
        esperado = (int(self.AHORA.timestamp()) - inicios[1]) / 86400  # cálculo independiente (float en prueba)
        self.assertAlmostEqual(float(self.resumen["edad_oferta_dias"]), esperado, places=6)
        self.assertEqual(self.resumen["edad_oferta_dias"].quantize(Decimal("0.1")), Decimal("14.9"))

    def test_la_mediana_castigaba_a_quien_renueva_creativos(self):
        self.assertLess(self.resumen["mediana_dias_activos"], Decimal(1))
        base = oferta_base()["traccion"]
        real = dict(base, anuncios_activos=27, conceptos_unicos=2, paginas_misma_landing=1,
                    anunciantes_independientes_mismo_angulo=4)
        con_edad = pm.calcular_traccion(dict(real, edad_oferta_dias=self.resumen["edad_oferta_dias"]), self.p)
        con_mediana = pm.calcular_traccion(dict(real, edad_oferta_dias=self.resumen["mediana_dias_activos"]), self.p)
        self.assertAlmostEqual(float(con_edad[0]), (2 / 3) ** 0.25, places=9)  # solo los conceptos limitan
        self.assertEqual(con_edad[1]["t_edad"], Decimal(1))
        self.assertLess(con_mediana[0], Decimal("0.5"))

    def test_los_titulos_reales_son_dos_conceptos_de_una_sola_pagina(self):
        self.assertEqual(self.resumen["paginas"], 1)
        self.assertEqual(self.resumen["paginas_con_concepto_compartido"], 0)


class PruebaEjemploPiloto(Base):
    """El ejemplo real de scripts/modelado/ejemplos/ debe seguir siendo válido y dar lo que documenta."""

    RUTA = Path(__file__).resolve().parents[2] / "scripts" / "modelado" / "ejemplos" / "piloto_crochet_2026-11-06.json"

    def test_los_tres_mercados_quedan_incompletos_y_se_ordenan_por_techo(self):
        pares = pm.puntuar(pm.leer_json(self.RUTA), self.p)
        self.assertEqual([x["mercado"] for x in pares], ["PL", "PT", "IT"])
        self.assertTrue(all(x["estado"] == "incompleta" and x["PM"] is None for x in pares))

    def test_el_techo_refleja_lo_medido(self):
        pares = {x["mercado"]: x for x in pm.puntuar(pm.leer_json(self.RUTA), self.p)}
        # T = (1 · 1 · 2/3 · 1)^(1/4); H, X sin medir valen 1 en el techo; D = 0,4 (sin reencuadres)
        esperado = 100 * ((2 / 3) ** 0.25) ** 0.25 * 0.4 ** 0.20
        self.assertAlmostEqual(float(pares["PL"]["techo"]), esperado, places=6)
        self.assertEqual(pares["IT"]["techo"], Decimal(0))  # el original ya corre en italiano

    def test_lo_no_evaluado_se_separa_de_las_notas_del_maker(self):
        par = pm.puntuar(pm.leer_json(self.RUTA), self.p)[0]
        self.assertIn("hueco.entrantes_30d", par["pendientes"])
        self.assertEqual(len(par["notas"]), 4)
        self.assertNotIn(par["notas"][0], par["pendientes"])

    def test_resumir_pendientes_agrupa_por_tipo(self):
        texto = pm.resumir_pendientes(["marca_personal", "sustituto_gratis_cubre", "transferibilidad.dolor_universal",
                                       "hueco.entrantes_30d"])
        self.assertEqual(texto, "puertas×2, transferibilidad.dolor_universal, hueco.entrantes_30d")


class PruebaSelloDeReglas(Base):
    """El sello prueba con qué reglas se calculó un ranking: si alguien cambia un número, cambia."""

    def test_formato_y_determinismo(self):
        sello = pm.sello_reglas(self.p)
        self.assertRegex(sello, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(sello, pm.sello_reglas(dict(self.p)))

    def test_cualquier_parametro_que_cambie_cambia_el_sello(self):
        base = pm.sello_reglas(self.p)
        for clave, valor in self.p.items():
            with self.subTest(clave=clave):
                cambiado = dict(self.p)
                cambiado[clave] = valor + 1 if isinstance(valor, int) else valor + Decimal("0.01")
                self.assertNotEqual(pm.sello_reglas(cambiado), base)

    def test_cambiar_la_version_de_la_formula_cambia_el_sello(self):
        base = pm.sello_reglas(self.p)
        with mock.patch.object(pm, "FORMULA_VERSION", "pm-3"):
            self.assertNotEqual(pm.sello_reglas(self.p), base)

    def test_cambiar_un_vocabulario_cambia_el_sello(self):
        base = pm.sello_reglas(self.p)
        with mock.patch.object(pm, "PUERTAS", pm.PUERTAS[:-1]):
            self.assertNotEqual(pm.sello_reglas(self.p), base)

    def test_la_forma_de_escribir_el_numero_no_importa(self):
        otro = dict(self.p, modelado_anuncios_objetivo=Decimal("25.0"), modelado_peso_hueco=Decimal("0.350"))
        self.assertEqual(pm.sello_reglas(otro), pm.sello_reglas(self.p))

    def test_el_sello_aprobado_bloquea_y_no_calcula_si_las_reglas_cambiaron(self):
        sello = pm.sello_reglas(self.p)
        args = ("puntuar", str(CORPUS), "--parametros", str(PARAMETROS), "--json")
        ok = io.StringIO()
        self.assertEqual(pm.main([*args, "--sello-esperado", sello], salida=ok), 0)
        self.assertEqual(json.loads(ok.getvalue())["sello_reglas"], sello)
        bloqueado, error = io.StringIO(), io.StringIO()
        with redirect_stderr(error):
            codigo = pm.main([*args, "--sello-esperado", "sha256:" + "0" * 64], salida=bloqueado)
        self.assertEqual(codigo, 4)
        self.assertEqual(bloqueado.getvalue(), "")  # no se calculó ni se mostró nada
        self.assertIn("ErrorBloqueado", error.getvalue())

    def test_la_tabla_muestra_con_que_reglas_se_calculo(self):
        salida = io.StringIO()
        pm.main(["puntuar", str(CORPUS), "--parametros", str(PARAMETROS)], salida=salida)
        self.assertIn("Reglas: sha256:", salida.getvalue())


class PruebaCLI(Base):
    def ejecutar(self, *argv):
        salida, error = io.StringIO(), io.StringIO()
        with redirect_stderr(error):
            codigo = pm.main(list(argv), salida=salida)
        return codigo, salida.getvalue(), error.getvalue()

    def puntuar_args(self, fichas=CORPUS, *extra):
        return ("puntuar", str(fichas), "--parametros", str(PARAMETROS), *extra)

    def test_puntuar_imprime_tabla_y_sale_con_cero(self):
        codigo, salida, _ = self.ejecutar(*self.puntuar_args(CORPUS, "--sensibilidad"))
        self.assertEqual(codigo, 0)
        self.assertIn("trusa-3r", salida)
        self.assertIn("Sensibilidad: robusto", salida)

    def test_json_es_valido_y_los_decimales_son_cadenas(self):
        codigo, salida, _ = self.ejecutar(*self.puntuar_args(CORPUS, "--json", "--solo-marco"))
        self.assertEqual(codigo, 0)
        cuerpo = json.loads(salida)
        self.assertEqual(cuerpo["schema_version"], "1.0.0")
        self.assertTrue(all(isinstance(x["factores"]["T"], str) for x in cuerpo["pares"]))
        self.assertTrue(all(x["en_marco"] for x in cuerpo["pares"]))

    def test_archivo_inexistente_sale_con_dos(self):
        codigo, _, error = self.ejecutar(*self.puntuar_args(Path("/no/existe.json")))
        self.assertEqual(codigo, 2)
        self.assertIn("ErrorUso", error)

    def test_uso_incorrecto_sale_con_dos(self):
        codigo, _, _ = self.ejecutar("puntuar")
        self.assertEqual(codigo, 2)

    def test_ficha_invalida_sale_con_tres(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "f.json"
            ruta.write_text(json.dumps({"schema_version": "1.0.0", "ofertas": [{"modelo_id": "x"}]}), encoding="utf-8")
            codigo, _, error = self.ejecutar(*self.puntuar_args(ruta))
        self.assertEqual(codigo, 3)
        self.assertIn("ErrorValidacion", error)

    def test_nan_en_el_json_sale_con_tres(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "f.json"
            ruta.write_text('{"schema_version": "1.0.0", "ofertas": NaN}', encoding="utf-8")
            codigo, _, _ = self.ejecutar(*self.puntuar_args(ruta))
        self.assertEqual(codigo, 3)

    def test_decimales_literales_en_el_json_se_aceptan_sin_float(self):
        doc = documento(oferta_base())
        texto = json.dumps(doc).replace('"transferibilidad": {"dolor_universal": "1"',
                                        '"transferibilidad": {"dolor_universal": 1.0')
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "f.json"
            ruta.write_text(texto, encoding="utf-8")
            codigo, salida, _ = self.ejecutar(*self.puntuar_args(ruta, "--json"))
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida)["pares"][0]["PM"], "100.00")

    def test_parametros_faltantes_salen_con_cinco(self):
        with tempfile.TemporaryDirectory() as tmp:
            vacio = Path(tmp) / "p.yaml"
            vacio.write_text("grupos: {descubrimiento: {}}\n", encoding="utf-8")
            codigo, _, error = self.ejecutar("puntuar", str(CORPUS), "--parametros", str(vacio))
        self.assertEqual(codigo, 5)
        self.assertIn("parametros_modelado.propuesta.yaml", error)

    def test_salida_nunca_sobrescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "ranking.json"
            primero, _, _ = self.ejecutar(*self.puntuar_args(CORPUS, "--salida", str(destino)))
            contenido = destino.read_text(encoding="utf-8")
            segundo, _, error = self.ejecutar(*self.puntuar_args(CORPUS, "--salida", str(destino)))
            self.assertEqual(destino.read_text(encoding="utf-8"), contenido)
        self.assertEqual((primero, segundo), (0, 2))
        self.assertIn("ya existe", error)

    def test_resumir_por_cli(self):
        ahora = int(datetime(2026, 11, 6, 12, tzinfo=timezone.utc).timestamp())
        filas = [{"id": "1", "page_id": 1, "ad_creative_link_title": "A", "ad_delivery_start_time": ahora - 86400 * 10}]
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "filas.json"
            ruta.write_text(json.dumps(filas), encoding="utf-8")
            codigo, salida, _ = self.ejecutar("resumir", str(ruta), "--ahora", "2026-11-06T12:00:00Z")
            malo, _, _ = self.ejecutar("resumir", str(ruta), "--ahora", "ayer")
        self.assertEqual(codigo, 0)
        resumen = json.loads(salida)
        self.assertEqual(resumen["mediana_dias_activos"], "10.0")
        self.assertEqual(resumen["edad_max_dias"], "10.0")
        self.assertEqual(resumen["edad_oferta_dias"], "0.0")  # un solo anuncio: sin sobrevivientes
        self.assertEqual(malo, 2)


if __name__ == "__main__":
    unittest.main()
