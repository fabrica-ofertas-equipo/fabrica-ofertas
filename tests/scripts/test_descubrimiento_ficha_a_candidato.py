"""Pruebas de `scripts.descubrimiento.ficha_a_candidato`: la puerta de entrada de interfaces §3.8.1.

Una prueba roja por cada una de las 9 reglas que el código aplica (1-9; 10-12 son del CLI/QA), más el
camino feliz completo (ficha -> candidatos.json validado contra el esquema 1.0.0 vigente).
"""
from __future__ import annotations

import copy
import hashlib
import unittest
from decimal import Decimal
from pathlib import Path

from engine.errores import ErrorValidacion
from scripts.descubrimiento import ficha_a_candidato as FAC
from scripts.modelado import puntaje_modelar as pm
from scripts.validar_esquemas import errores_de_esquema

RAIZ = Path(__file__).resolve().parents[2]
RUTA_PARAMETROS = RAIZ / "tests" / "fixtures" / "descubrimiento" / "parametros_modo_d.yaml"


def _sha(texto: str) -> str:
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _ficha() -> dict:
    return {
        "modelo_id": "ahorro-personal-us-pgabc1234567",
        "nombre": "Ahorro Personal . US",
        "fuente": {"idioma": "en", "pais": "US"},
        "macro_nicho": None,  # SIEMPRE null: lo fija este módulo (regla 2), nunca el barrido
        "traccion": {
            "anuncios_activos": 25, "edad_oferta_dias": "15", "conceptos_unicos": 3,
            "paginas_misma_landing": 2, "anunciantes_independientes_mismo_angulo": 2,
        },
        "puertas": {"marca_personal": False, "sustituto_gratis_cubre": False, "practica_vetada": False},
        "reencuadres": ["mecanismo_nombrable"],
        "pendiente": [],
        "mercados": [{
            "mercado": "MX", "idioma": "es",
            "hueco": {"original_presente": False, "anunciantes_sostenidos": 0, "puntaje_rival": None, "entrantes_30d": 1},
            "ventana": "evergreen",
            "transferibilidad": {"dolor_universal": "0.8", "viabilidad_ticket": "0.8", "riesgo_politicas": "0.8"},
            "reencuadres_mercado": [],
        }],
    }


def _juicio() -> dict:
    return {
        "prueba_una_frase": "de gastar sin control cada mes a ahorrar de forma constante",
        "problema": "quiere ahorrar pero gasta sin control cada mes",
        "tesis": "una plantilla simple para ahorrar de forma constante",
        "senal_id_e3": "abc123abc123",
        "ejes": {"P": "P1", "C": "C1", "E": "E0", "N": "N1"},
        "zona_gris": False, "hay_reencuadre": False,
        "riesgo_fuentes": ["politica-x1-dinero-v1"], "riesgo_categoria": "finanzas personales",
        "riesgo_claims_a_evitar": ["ganar dinero rapido"], "riesgo_angulo_seguro": "organizar el presupuesto mensual",
        "mecanismo": {
            "causa_raiz": {"texto": "no hay un sistema simple de ahorro", "senales": ["abc123abc123"]},
            "nombre": "metodo de ahorro simple", "como_funciona": "registra y reparte el ingreso en sobres",
            "diferencia": "mas simple que una app de banco", "prueba_logica": "menos pasos que una hoja de calculo",
            "riesgo_de_claim": "ninguno: no promete una cifra",
        },
        "entregable": {
            "formato": "plantilla", "alcance": "una plantilla de presupuesto mensual",
            "estado_a_b": {"a": "sin presupuesto", "b": "presupuesto mensual claro"},
            "tiempo_al_primer_resultado": 10,
            "producibilidad": {"nivel": "alta", "notas": "se genera con una plantilla de hoja de calculo"},
            "licencias": ["sin activos de terceros"],
        },
        "evidencia": [
            {"id": "EV-01", "tipo": "E3", "locale": "MX", "senal_id": "abc123abc123",
             "url": "https://example.com/foro-mx",
             "fecha_publicacion": "2026-01-01", "fecha_consulta": "2026-11-01",
             "cita": "no se en que se me va el dinero cada mes", "cita_literal_verificada": True,
             "hash_copia_crudo": _sha("foro-mx")},
            {"id": "EV-02", "tipo": "E2", "url": "https://example.com/anuncio",
             "fecha_publicacion": "2026-01-01", "fecha_consulta": "2026-11-01",
             "cita": "plantilla de presupuesto mensual", "cita_literal_verificada": True,
             "hash_copia_crudo": _sha("anuncio")},
        ],
        "similitud_memoria": {"max": "0.10", "con": None},
        "precio_plausible": {"min": {"monto": 700, "moneda": "USD"}, "max": {"monto": 2900, "moneda": "USD"},
                             "razon": "rango bajo ticket"},
        "ventana_estacional": None, "hipotesis_para_d2": [], "que_la_mataria": [], "palabras_clave_voz_cliente": [],
    }


def _doc_pares(ficha=None, juicio=None, **extra) -> dict:
    par = {"ficha": ficha if ficha is not None else _ficha(), "problema_id": "PRB-202611-0001",
          "nicho_id": "ahorro-personal", "microsegmento": "presupuesto-mensual",
          "juicio": juicio if juicio is not None else _juicio()}
    par.update(extra)
    return {"schema_version": "1.0.0", "pares": [par]}


class PruebaCaminoFeliz(unittest.TestCase):
    def setUp(self) -> None:
        self.parametros = pm.cargar_parametros(RUTA_PARAMETROS)
        self.sim_dup_bloqueo = FAC._leer_sim_dup_bloqueo(RUTA_PARAMETROS)

    def _mapear(self, doc_pares, **kw):
        base = dict(oferta_id="OF-202611-01", corrida_id="RUN-20261106-01", mercado_locale="es-MX",
                   mercado_paises=["MX"], nivel_max_lanzable=None, sim_dup_bloqueo=self.sim_dup_bloqueo)
        base.update(kw)
        return FAC.mapear_candidatos(doc_pares, self.parametros, **base)

    def test_un_par_completo_pasa_y_valida_contra_el_esquema_1_0_0(self) -> None:
        resultado = self._mapear(_doc_pares())
        self.assertEqual([r.estado_par for r in resultado["resultados"]], ["pasa"])
        doc = resultado["documento"]
        self.assertEqual(len(doc["candidatos"]), 1)
        errores = errores_de_esquema("candidatos", doc)
        self.assertEqual(errores, [], [str(e) for e in errores])
        cand = doc["candidatos"][0]
        self.assertEqual(cand["candidato_id"], "CAND-01")
        self.assertEqual(cand["rango"], 1)
        self.assertEqual(cand["macro_nicho"], "dinero")
        self.assertEqual(cand["riesgo"]["nivel"], "verde")
        self.assertNotIn("_riesgo_1_1_0", cand)
        self.assertNotIn("_origen", cand)
        # ningún campo aditivo 1.1.0 se filtró a evidencia[] (additionalProperties:false del 1.0.0)
        for e in cand["evidencia"]:
            self.assertNotIn("locale", e)

    def test_rango_por_score_ajustado_descendente_con_dos_pares(self) -> None:
        juicio_debil = copy.deepcopy(_juicio())
        juicio_debil["similitud_memoria"] = {"max": "0.60", "con": "CAND-99"}  # mismo baja f_dup, sigue < bloqueo
        ficha2 = copy.deepcopy(_ficha())
        ficha2["modelo_id"] = "ahorro-personal-us-pgdef7654321"
        doc = _doc_pares()
        doc["pares"].append({"ficha": ficha2, "problema_id": "PRB-202611-0002", "nicho_id": "ahorro-personal",
                             "microsegmento": "presupuesto-mensual", "juicio": juicio_debil})
        resultado = self._mapear(doc)
        self.assertEqual([r.estado_par for r in resultado["resultados"]], ["pasa", "pasa"])
        cands = resultado["documento"]["candidatos"]
        self.assertEqual([c["rango"] for c in cands], [1, 2])
        self.assertGreaterEqual(cands[0]["score_ajustado"], cands[1]["score_ajustado"])

    def test_sin_ningun_par_que_pase_no_escribe_y_exigir_alguno_falla(self) -> None:
        juicio_malo = copy.deepcopy(_juicio())
        juicio_malo["ejes"] = {"P": "P3", "C": "C1", "E": "E0", "N": "N1"}  # ROJO, sin reencuadre
        resultado = self._mapear(_doc_pares(juicio=juicio_malo))
        self.assertEqual(resultado["documento"]["candidatos"], [])
        self.assertEqual(resultado["resultados"][0].estado_par, "vetada")


class PruebaRegla1EstadoPasa(unittest.TestCase):
    def test_marca_personal_true_es_vetada_con_motivo_canonico(self) -> None:
        ficha = _ficha()
        ficha["puertas"]["marca_personal"] = True
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "dependencia_de_marca_personal"))

    def test_sustituto_gratis_cubre_true_es_vetada_con_motivo_canonico(self) -> None:
        ficha = _ficha()
        ficha["puertas"]["sustituto_gratis_cubre"] = True
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "sustituto_gratis_dominante"))

    def test_practica_vetada_sin_causa_queda_sin_motivo_canonico(self) -> None:
        ficha = _ficha()
        ficha["puertas"]["practica_vetada"] = True
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "vetada")
        self.assertIsNone(r.motivo)  # linea_roja_de_contenido_o_negocio no existe todavía (pedido a CT)

    def test_practica_vetada_por_promesa_es_claim_de_salud_o_ingresos(self) -> None:
        ficha = _ficha()
        ficha["puertas"]["practica_vetada"] = True
        juicio = _juicio()
        juicio["practica_vetada_causa"] = "promesa_salud_o_ingresos"
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "claim_de_salud_o_ingresos"))

    def test_puerta_en_null_es_incompleta(self) -> None:
        ficha = _ficha()
        ficha["puertas"]["marca_personal"] = None
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "incompleta")

    def test_pm_bajo_el_umbral_es_no_pasa(self) -> None:
        ficha = _ficha()
        ficha["traccion"] = {"anuncios_activos": 0, "edad_oferta_dias": "0", "conceptos_unicos": 0,
                             "paginas_misma_landing": 0, "anunciantes_independientes_mismo_angulo": 0}
        ficha["mercados"][0]["hueco"]["original_presente"] = True  # H = 0 también
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "no_pasa")


class PruebaRegla2Macro(unittest.TestCase):
    def test_sin_prueba_de_frase_es_no_pasa(self) -> None:
        juicio = _juicio()
        juicio["prueba_una_frase"] = "quiero mejorar mis finanzas personales"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "no_pasa")

    def test_fuera_de_macro_es_vetada_con_motivo_canonico(self) -> None:
        juicio = _juicio()
        juicio["prueba_una_frase"] = "de improvisar la cena cada noche a tener un menu variado cada semana"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "fuera_de_macro_nicho"))

    def test_sin_senal_id_e3_es_incompleta(self) -> None:
        juicio = _juicio()
        juicio["senal_id_e3"] = None
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "incompleta")
        self.assertIn("clasificacion_macro.senal_id_e3", r.pendiente)


class PruebaRegla3Nicho(unittest.TestCase):
    def test_nicho_id_mal_formado_es_incompleta(self) -> None:
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="Nicho Invalido", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "incompleta")


class PruebaRegla4Riesgo(unittest.TestCase):
    def test_riesgo_rojo_sin_reencuadre_es_vetada(self) -> None:
        juicio = _juicio()
        juicio["ejes"] = {"P": "P3", "C": "C1", "E": "E0", "N": "N1"}
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "claim_de_salud_o_ingresos"))

    def test_riesgo_rojo_por_contenido_sin_motivo_de_promesa_queda_sin_canonico(self) -> None:
        juicio = _juicio()
        juicio["ejes"] = {"P": "P1", "C": "C3", "E": "E0", "N": "N1"}
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "vetada")
        self.assertIsNone(r.motivo)

    def test_ejes_invalidos_fallan_cerrado_sin_tirar_todo_el_lote(self) -> None:
        juicio = _juicio()
        juicio["ejes"] = {"P": "P9", "C": "C1", "E": "E0", "N": "N1"}
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "no_pasa")

    def test_amarillo_sin_nivel_max_lanzable_no_pasa_fail_closed(self) -> None:
        juicio = _juicio()
        juicio["ejes"] = {"P": "P2s", "C": "C1", "E": "E0", "N": "N1"}  # amarillo-A
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80, nivel_max_lanzable=None)
        self.assertEqual(r.estado_par, "no_pasa")

    def test_amarillo_con_nivel_max_lanzable_explicito_pasa(self) -> None:
        juicio = _juicio()
        juicio["ejes"] = {"P": "P2s", "C": "C1", "E": "E0", "N": "N1"}  # amarillo-A
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="ahorro-personal", microsegmento="presupuesto-mensual", sensibilidad_pct=80,
            nivel_max_lanzable={"dinero": "amarillo-A"})
        self.assertEqual(r.estado_par, "pasa")


class PruebaRegla5MecanismoEntregable(unittest.TestCase):
    def test_nombre_de_mecanismo_fuera_de_2_a_6_palabras_no_pasa(self) -> None:
        juicio = _juicio()
        juicio["mecanismo"]["nombre"] = "metodo"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "no_pasa")

    def test_sin_e3_del_locale_destino_en_causa_raiz_es_incompleta(self) -> None:
        juicio = _juicio()
        juicio["evidencia"][0]["locale"] = "ES"  # no es el locale destino (MX)
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "incompleta")

    def test_entregable_que_describe_comunidad_es_vetada_con_motivo_canonico(self) -> None:
        """Mención AFIRMADA: veta (defecto D1d n.2b, caso base)."""
        juicio = _juicio()
        juicio["entregable"]["alcance"] = "acceso a una comunidad privada de apoyo"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "requiere_comunidad_o_en_vivo"))

    def test_entregable_que_niega_comunidad_no_veta(self) -> None:
        """Mención NEGADA ("sin comunidad"): no veta (defecto D1d n.2b)."""
        juicio = _juicio()
        juicio["entregable"]["alcance"] = "una plantilla de uso individual, sin comunidad ni grupo"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="ahorro-personal", microsegmento="presupuesto-mensual", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "pasa")

    def test_entregable_con_mencion_mixta_afirmada_y_negada_sigue_vetando(self) -> None:
        """Texto "mixto": una mención negada y otra afirmada en el mismo campo -- fail-closed, veta."""
        juicio = _juicio()
        juicio["entregable"]["alcance"] = ("sin comunidad de pago, pero incluye acceso a una comunidad "
                                          "de egresados")
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "requiere_comunidad_o_en_vivo"))

    def test_entregable_con_comunidad_ofuscada_por_guion_sigue_vetando(self) -> None:
        """Ofuscación simple (guion dentro de la palabra): sigue vetando -- resistente a evasión."""
        juicio = _juicio()
        juicio["entregable"]["alcance"] = "incluye una co-munidad privada de seguimiento"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "requiere_comunidad_o_en_vivo"))

    def test_entregable_con_servicio_humano_afirmado_es_requiere_servicio(self) -> None:
        juicio = _juicio()
        juicio["entregable"]["alcance"] = "incluye servicio humano de soporte diario"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "requiere_servicio"))

    def test_estructura_comunidad_true_veta_sin_mirar_el_texto(self) -> None:
        """Campo estructurado explícito manda sobre el texto libre ("mejor, decide por campos
        estructurados cuando existan")."""
        juicio = _juicio()
        juicio["entregable"]["alcance"] = "una plantilla sin nada raro"
        juicio["entregable_estructura"] = {"comunidad_o_en_vivo": True}
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "requiere_comunidad_o_en_vivo"))

    def test_estructura_en_false_no_evita_el_veto_por_texto(self) -> None:
        """Ausencia o `false` en el campo estructurado NO relaja el chequeo de texto (red de seguridad)."""
        juicio = _juicio()
        juicio["entregable"]["alcance"] = "incluye una comunidad de apoyo diaria"
        juicio["entregable_estructura"] = {"comunidad_o_en_vivo": False}
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual((r.estado_par, r.motivo), ("vetada", "requiere_comunidad_o_en_vivo"))

    def test_formato_fuera_del_enum_no_pasa(self) -> None:
        juicio = _juicio()
        juicio["entregable"]["formato"] = "servicio_premium"
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "no_pasa")


class PruebaRegla6Evidencia(unittest.TestCase):
    def test_sin_e2_de_la_oferta_es_incompleta(self) -> None:
        juicio = _juicio()
        juicio["evidencia"] = [juicio["evidencia"][0]]  # solo la E3, sin E2
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "incompleta")

    def test_cita_no_verificada_no_pasa(self) -> None:
        juicio = _juicio()
        juicio["evidencia"][1]["cita_literal_verificada"] = False
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "no_pasa")


class PruebaRegla7Similitud(unittest.TestCase):
    def test_similitud_sobre_el_umbral_no_pasa(self) -> None:
        juicio = _juicio()
        juicio["similitud_memoria"] = {"max": "0.85", "con": "CAND-01"}
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "no_pasa")
        self.assertIsNone(r.motivo)  # duplicado_de_la_memoria no es motivo canónico todavía

    def test_sin_similitud_memoria_es_incompleta(self) -> None:
        juicio = _juicio()
        juicio["similitud_memoria"] = {"max": None, "con": None}
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], juicio, problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "incompleta")


class PruebaRegla8Sensibilidad(unittest.TestCase):
    def test_sensibilidad_fuera_de_rango_es_incompleta(self) -> None:
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=150)
        self.assertEqual(r.estado_par, "incompleta")

    def test_sensibilidad_nunca_se_omite_incluso_con_cero(self) -> None:
        ficha = _ficha()
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="ahorro-personal", microsegmento="presupuesto-mensual", sensibilidad_pct=0)
        self.assertEqual(r.estado_par, "pasa")
        self.assertEqual(r.candidato["sensibilidad"]["top3_estable_pct"], 0)


class PruebaRegla9Pendiente(unittest.TestCase):
    def test_ficha_con_pendiente_abierto_es_incompleta(self) -> None:
        ficha = _ficha()
        ficha["pendiente"] = ["modelo_de_cobro"]
        r = FAC.evaluar_par(
            _par_pm_de(ficha), ficha, ficha["mercados"][0], _juicio(), problema_id="PRB-202611-0001",
            nicho_id="x", microsegmento="y", sensibilidad_pct=80)
        self.assertEqual(r.estado_par, "incompleta")
        self.assertIn("modelado.pendiente: modelo_de_cobro", r.pendiente)


class PruebaDeteccionNegacion(unittest.TestCase):
    """`FAC._hay_mencion_afirmada`: afirmado, negado, mixto y ofuscado (defecto D1d n.2b)."""

    def test_afirmado_simple(self) -> None:
        self.assertTrue(FAC._hay_mencion_afirmada("incluye una comunidad privada", "comunidad"))

    def test_negado_con_sin(self) -> None:
        self.assertFalse(FAC._hay_mencion_afirmada("sin comunidad ni grupo", "comunidad"))

    def test_negado_con_no_incluye(self) -> None:
        self.assertFalse(FAC._hay_mencion_afirmada("no incluye comunidad", "comunidad"))

    def test_negado_en_ingles_without(self) -> None:
        self.assertFalse(FAC._hay_mencion_afirmada("without community access", "community"))

    def test_mixto_una_negada_y_otra_afirmada_es_afirmada(self) -> None:
        texto = "sin comunidad de pago, aunque sí incluye comunidad de egresados"
        self.assertTrue(FAC._hay_mencion_afirmada(texto, "comunidad"))

    def test_ofuscado_con_guion_sigue_detectando(self) -> None:
        self.assertTrue(FAC._hay_mencion_afirmada("una co-munidad de seguimiento", "comunidad"))

    def test_ofuscado_con_espacio_extra_sigue_detectando(self) -> None:
        self.assertTrue(FAC._hay_mencion_afirmada("una co munidad de seguimiento", "comunidad"))

    def test_sin_ninguna_mencion_no_afirma(self) -> None:
        self.assertFalse(FAC._hay_mencion_afirmada("una plantilla de uso individual", "comunidad"))


class PruebaParametrosDescubrimientoReales(unittest.TestCase):
    """`FAC.parametros_descubrimiento_reales`: cada clave de SU hogar real (defecto D1d n.2c)."""

    def test_modelado_ausente_en_empresa_usa_el_respaldo(self) -> None:
        import tempfile
        import yaml

        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            empresa = raiz / "empresa"
            empresa.mkdir()
            (empresa / "parametros.yaml").write_text(yaml.safe_dump({
                "schema_version": "1.1.0", "version": 1,
                "grupos": {"descubrimiento": {"sim_dup_bloqueo": {"valor": "0.80"}}}}), encoding="utf-8")
            modelado, sim = FAC.parametros_descubrimiento_reales(raiz)
            self.assertEqual(sim, Decimal("0.80"))
            self.assertIn("modelado_umbral_pasa", modelado)  # vino del respaldo propuesta.yaml

    def test_falta_sim_dup_bloqueo_en_empresa_falla_cerrado(self) -> None:
        import tempfile
        import yaml
        from engine.errores import ErrorLimite

        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            empresa = raiz / "empresa"
            empresa.mkdir()
            (empresa / "parametros.yaml").write_text(yaml.safe_dump(
                {"schema_version": "1.1.0", "version": 1, "grupos": {"descubrimiento": {}}}), encoding="utf-8")
            with self.assertRaises(ErrorLimite):
                FAC.parametros_descubrimiento_reales(raiz)

    def test_con_el_archivo_real_del_repo_sim_dup_bloqueo_y_respaldo_modelado(self) -> None:
        """Contra el `empresa/parametros.yaml` real del repositorio (solo lectura): hoy no tiene
        `modelado_*` integrados, así que debe caer al respaldo."""
        modelado, sim = FAC.parametros_descubrimiento_reales(RAIZ)
        self.assertEqual(sim, Decimal("0.80"))
        self.assertIn("modelado_umbral_pasa", modelado)


class PruebaSidecarYCabecera1_1_0(unittest.TestCase):
    """`sello_reglas`/`modo_busqueda` (defecto D1d n.2a): a nivel documento en `parametros_usados` y
    por candidato en el sidecar."""

    def setUp(self) -> None:
        self.parametros = pm.cargar_parametros(RUTA_PARAMETROS)
        self.sim_dup_bloqueo = FAC._leer_sim_dup_bloqueo(RUTA_PARAMETROS)

    def test_modo_busqueda_invalido_falla_con_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            FAC.mapear_candidatos(
                _doc_pares(), self.parametros, oferta_id="OF-202611-01", corrida_id="RUN-20261106-01",
                mercado_locale="es-MX", mercado_paises=["MX"], nivel_max_lanzable=None,
                sim_dup_bloqueo=self.sim_dup_bloqueo, modo_busqueda="Z")

    def test_documento_lleva_sello_reglas_y_modo_busqueda_en_parametros_usados(self) -> None:
        resultado = FAC.mapear_candidatos(
            _doc_pares(), self.parametros, oferta_id="OF-202611-01", corrida_id="RUN-20261106-01",
            mercado_locale="es-MX", mercado_paises=["MX"], nivel_max_lanzable=None,
            sim_dup_bloqueo=self.sim_dup_bloqueo, modo_busqueda="D")
        usados = resultado["documento"]["parametros_usados"]
        self.assertEqual(usados["modo_busqueda"], "D")
        self.assertEqual(usados["sello_reglas"], pm.sello_reglas(self.parametros))

    def test_sidecar_tiene_un_candidato_con_sello_reglas_y_origen(self) -> None:
        resultado = FAC.mapear_candidatos(
            _doc_pares(), self.parametros, oferta_id="OF-202611-01", corrida_id="RUN-20261106-01",
            mercado_locale="es-MX", mercado_paises=["MX"], nivel_max_lanzable=None,
            sim_dup_bloqueo=self.sim_dup_bloqueo, modo_busqueda="D")
        sidecar = resultado["sidecar_1_1_0"]
        self.assertEqual(list(sidecar), ["CAND-01"])
        aditivos = sidecar["CAND-01"]
        self.assertEqual(aditivos["sello_reglas"], pm.sello_reglas(self.parametros))
        self.assertEqual(aditivos["origen"]["modo_busqueda"], "D")
        self.assertIn("ejes_codigo", aditivos["riesgo"])


class PruebaRechazosJsonl(unittest.TestCase):
    def test_solo_los_motivos_canonicos_se_anexan(self) -> None:
        from scripts.descubrimiento.ficha_a_candidato import ResultadoPar

        resultados = [ResultadoPar("vetada", motivo="fuera_de_macro_nicho", detalle="x"),
                     ResultadoPar("vetada", motivo=None, detalle="sin canónico"),
                     ResultadoPar("incompleta", pendiente=["a"])]
        pares = [{"problema_id": "PRB-202611-0001", "nicho_id": "n", "ficha": {"mercados": [{"mercado": "MX"}]}}] * 3
        lineas = FAC.rechazos_de(resultados, pares)
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0]["motivo"], "fuera_de_macro_nicho")
        self.assertEqual(lineas[0]["redencion"], "reformular")


class PruebaCli(unittest.TestCase):
    def test_mapear_aplicar_escribe_candidatos_y_rechazos(self) -> None:
        import contextlib
        import io
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            pares_ruta = base / "pares.json"
            juicio_fuera = _juicio()
            juicio_fuera["prueba_una_frase"] = "de improvisar la cena cada noche a tener un menu variado cada semana"
            doc = _doc_pares()
            doc["pares"].append({"ficha": _ficha_con_id("otra-oferta"), "problema_id": "PRB-202611-0002",
                                 "nicho_id": "ahorro-personal", "microsegmento": "presupuesto-mensual",
                                 "juicio": juicio_fuera})
            pares_ruta.write_text(json.dumps(doc), encoding="utf-8")
            salida = base / "candidatos.json"
            rechazos = base / "rechazos.jsonl"
            argv = ["mapear", str(pares_ruta), "--parametros", str(RUTA_PARAMETROS), "--oferta-id", "OF-202611-01",
                   "--corrida-id", "RUN-20261106-01", "--locale", "es-MX", "--paises", "MX", "--salida", str(salida),
                   "--rechazos", str(rechazos), "--aplicar", "--json"]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                codigo = FAC.main(argv)
            self.assertEqual(codigo, 0, buf.getvalue())
            self.assertTrue(salida.is_file())
            self.assertTrue(rechazos.is_file())
            lineas = rechazos.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lineas), 1)
            self.assertEqual(json.loads(lineas[0])["motivo"], "fuera_de_macro_nicho")
            salida_json = json.loads(buf.getvalue())
            self.assertEqual(salida_json["candidatos_pasan"], 1)
            # sidecar 1.1.0 (defecto D1d n.2a): sello_reglas/riesgo ampliado/origen por candidato
            ruta_sidecar = Path(salida_json["ruta_sidecar"])
            self.assertTrue(ruta_sidecar.is_file())
            sidecar = json.loads(ruta_sidecar.read_text(encoding="utf-8"))
            self.assertEqual(list(sidecar["candidatos"]), ["CAND-01"])
            self.assertIn("sello_reglas", sidecar["candidatos"]["CAND-01"])

    def test_sin_parametros_usa_raiz_y_resuelve_por_hogar_real(self) -> None:
        """Sin `--parametros`, el CLI usa `--raiz` y `parametros_descubrimiento_reales` (defecto D1d
        n.2c): aquí se apunta a la raíz real del repositorio (solo lectura)."""
        import contextlib
        import io
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            pares_ruta = base / "pares.json"
            pares_ruta.write_text(json.dumps(_doc_pares()), encoding="utf-8")
            salida = base / "candidatos.json"
            argv = ["mapear", str(pares_ruta), "--raiz", str(RAIZ), "--oferta-id", "OF-202611-01",
                   "--corrida-id", "RUN-20261106-01", "--locale", "es-MX", "--paises", "MX", "--salida",
                   str(salida), "--aplicar", "--json"]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                codigo = FAC.main(argv)
            self.assertEqual(codigo, 0, buf.getvalue())
            self.assertEqual(json.loads(buf.getvalue())["candidatos_pasan"], 1)

    def test_exigir_alguno_sin_candidatos_sale_con_3(self) -> None:
        import contextlib
        import io
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            pares_ruta = base / "pares.json"
            juicio_fuera = _juicio()
            juicio_fuera["prueba_una_frase"] = "de improvisar la cena cada noche a tener un menu variado cada semana"
            pares_ruta.write_text(json.dumps(_doc_pares(juicio=juicio_fuera)), encoding="utf-8")
            argv = ["mapear", str(pares_ruta), "--parametros", str(RUTA_PARAMETROS), "--oferta-id", "OF-202611-01",
                   "--corrida-id", "RUN-20261106-01", "--locale", "es-MX", "--paises", "MX", "--salida",
                   str(base / "candidatos.json"), "--exigir-alguno"]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                codigo = FAC.main(argv)
            self.assertEqual(codigo, 3)
            self.assertFalse((base / "candidatos.json").is_file())


def _ficha_con_id(modelo_id: str) -> dict:
    f = _ficha()
    f["modelo_id"] = f"{modelo_id}-us-pgabc1234567"
    return f


def _par_pm_de(ficha: dict) -> dict:
    """Puntúa `ficha` (un solo mercado) con los parámetros de prueba, como lo haría `puntaje_modelar`."""
    parametros = pm.cargar_parametros(RUTA_PARAMETROS)
    ofertas = pm.validar_fichas({"schema_version": "2.0.0", "ofertas": [ficha]}, parametros)
    oferta = ofertas[0]
    return pm.puntuar_par(oferta, oferta["mercados"][0], parametros)


if __name__ == "__main__":
    unittest.main()
