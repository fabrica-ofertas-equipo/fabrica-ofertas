"""Pruebas de scripts.validacion.veredicto_d2 (veredicto calculado de D2, departamentos/03-validacion.md §3.4).

Incluye una prueba de PARIDAD contra la skill ya probada (.claude/skills/d2-validacion/scripts/{veredicto,metricas}.py,
LEÍDA, nunca modificada): se ejecuta la skill sobre una de sus propias entradas sintéticas, se extraen los
agregados ya calculados (índice de saturación, sostenidos, mecanismo, convergencia, hueco, confianza) y se
arma con ellos una ENTRADA de este módulo; si los dos calculan algo distinto para el mismo caso, la prueba
lo señala (ver scripts/validacion/README.md «Decisiones» por las simplificaciones conocidas).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from engine.errores import ErrorValidacion, ParametroFaltante
from scripts.validacion import veredicto_d2 as V

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parent.parent / "fixtures" / "validacion"
SKILL_DIR = RAIZ / ".claude" / "skills" / "d2-validacion" / "scripts"


def _json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _cargar_modulo_skill(nombre: str):
    """Carga (solo lectura) un módulo de la skill d2-validacion por ruta, sin tocar sys.path del proyecto."""
    ruta = SKILL_DIR / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(f"_fixture_skill_d2_{nombre}", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


class PruebaCalcularValidacion(unittest.TestCase):
    def setUp(self) -> None:
        self.parametros = _json(FIX / "parametros-validacion.json")

    def test_entrada_go_da_go_y_cumple_el_esquema(self) -> None:
        entrada = _json(FIX / "entrada-go.json")
        doc = V.calcular_validacion(entrada, self.parametros)
        self.assertEqual("GO", doc["veredicto"]["calculado"])
        self.assertEqual("GO", doc["veredicto"]["propuesto"])
        self.assertEqual("GO", doc["veredicto"]["final"])
        self.assertEqual(["ninguna"], doc["veredicto"]["evidencia_faltante"])
        # El resto de los campos pasó tal cual de la entrada (incluida la forma que exige el esquema).
        self.assertEqual(entrada["saturacion"], doc["saturacion"])
        self.assertEqual(entrada["oferta_id"], doc["oferta_id"])

    def test_entrada_nogo_por_saturacion_sin_hueco(self) -> None:
        entrada = _json(FIX / "entrada-nogo.json")
        doc = V.calcular_validacion(entrada, self.parametros)
        self.assertEqual("NO_GO", doc["veredicto"]["calculado"])
        self.assertIn("NO_GO:is_muy_alto_sin_hueco", doc["veredicto"]["razones"])

    def test_entrada_go_condicional_por_falta_de_evidencia_local(self) -> None:
        entrada = _json(FIX / "entrada-go-condicional.json")
        doc = V.calcular_validacion(entrada, self.parametros)
        self.assertEqual("GO_CONDICIONAL", doc["veredicto"]["calculado"])
        self.assertIn("falta:evidencia_e1_o_e2_en_locale", doc["veredicto"]["razones"])
        self.assertIn("evidencia_e1_o_e2_en_locale", doc["veredicto"]["evidencia_faltante"])

    def test_cero_competidores_nunca_es_go(self) -> None:
        entrada = _json(FIX / "entrada-go.json")
        entrada["n_competidores"] = 0
        doc = V.calcular_validacion(entrada, self.parametros)
        self.assertEqual("NO_GO", doc["veredicto"]["calculado"])

    def test_riesgo_amarillo_sin_subnivel_no_es_apto_para_go(self) -> None:
        """Sin ``riesgo_subnivel`` (dato que el esquema de salida no guarda) un amarillo falla cerrado: no GO."""
        entrada = _json(FIX / "entrada-go.json")
        entrada["riesgo_politica"]["nivel"] = "amarillo"
        entrada["riesgo_subnivel"] = None
        doc = V.calcular_validacion(entrada, self.parametros)
        self.assertNotEqual("GO", doc["veredicto"]["calculado"])

    def test_riesgo_amarillo_a_es_apto_para_go(self) -> None:
        entrada = _json(FIX / "entrada-go.json")
        entrada["riesgo_politica"]["nivel"] = "amarillo"
        entrada["riesgo_subnivel"] = "A"
        doc = V.calcular_validacion(entrada, self.parametros)
        self.assertEqual("GO", doc["veredicto"]["calculado"])

    def test_riesgo_rojo_sin_reencuadre_es_nogo(self) -> None:
        entrada = _json(FIX / "entrada-go.json")
        entrada["riesgo_politica"]["nivel"] = "rojo"
        entrada["reencuadre_verificable_x1"] = False
        doc = V.calcular_validacion(entrada, self.parametros)
        self.assertEqual("NO_GO", doc["veredicto"]["calculado"])

    def test_sin_parametro_oficial_falla_cerrado_codigo_5(self) -> None:
        entrada = _json(FIX / "entrada-go.json")
        parametros_faltantes = _json(FIX / "parametros-validacion-faltante.json")
        with self.assertRaises(ParametroFaltante) as ctx:
            V.calcular_validacion(entrada, parametros_faltantes)
        self.assertEqual(5, ctx.exception.codigo_salida)

    def test_entrada_sin_forma_es_error_de_validacion_codigo_3(self) -> None:
        entrada = _json(FIX / "entrada-go.json")
        del entrada["voz"]
        with self.assertRaises(ErrorValidacion) as ctx:
            V.calcular_validacion(entrada, self.parametros)
        self.assertEqual(3, ctx.exception.codigo_salida)

    def test_entrada_que_no_es_un_objeto_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            V.calcular_validacion([], self.parametros)  # type: ignore[arg-type]


class PruebaComprobar(unittest.TestCase):
    def setUp(self) -> None:
        self.parametros = _json(FIX / "parametros-validacion.json")
        self.entrada = _json(FIX / "entrada-go-condicional.json")  # calcula GO_CONDICIONAL

    def test_validacion_coherente_no_tiene_incoherencias(self) -> None:
        doc = V.calcular_validacion(self.entrada, self.parametros)
        self.assertEqual([], V.comprobar(self.entrada, doc, self.parametros))

    def test_propuesto_no_puede_mejorar_el_calculado(self) -> None:
        doc = V.calcular_validacion(self.entrada, self.parametros)
        doc["veredicto"]["propuesto"] = "GO"  # mejora GO_CONDICIONAL -> GO: prohibido (S11)
        errores = V.comprobar(self.entrada, doc, self.parametros)
        self.assertTrue(any("MEJORA" in e for e in errores))

    def test_final_no_puede_mejorar_el_calculado_sin_origen_humano(self) -> None:
        doc = V.calcular_validacion(self.entrada, self.parametros)
        doc["veredicto"]["final"] = "GO"
        errores = V.comprobar(self.entrada, doc, self.parametros)
        self.assertTrue(any("es mejor que el calculado" in e for e in errores))

    def test_final_mejor_con_origen_humano_es_coherente(self) -> None:
        doc = V.calcular_validacion(self.entrada, self.parametros)
        doc["veredicto"]["final"] = "GO"
        doc["origen_version"] = "humano"
        self.assertEqual([], V.comprobar(self.entrada, doc, self.parametros))

    def test_calculado_tamperado_se_detecta(self) -> None:
        doc = V.calcular_validacion(self.entrada, self.parametros)
        doc["veredicto"]["calculado"] = "GO"
        doc["veredicto"]["propuesto"] = "GO"
        doc["veredicto"]["final"] = "GO"
        errores = V.comprobar(self.entrada, doc, self.parametros)
        self.assertTrue(any("pero el cálculo da" in e for e in errores))

    def test_validacion_sin_veredicto_es_incoherente(self) -> None:
        self.assertEqual(["validacion.json no tiene «veredicto»"], V.comprobar(self.entrada, {}, self.parametros))


class PruebaCli(unittest.TestCase):
    """Usa ``empresa/parametros.yaml`` REAL (el fixture recortado no cumple el esquema completo de
    ``parametros.schema.json``, que ``engine.parametros.cargar_parametros`` exige siempre; el fixture
    recortado solo sirve para las pruebas que llaman a ``calcular_validacion`` directamente)."""

    def setUp(self) -> None:
        self.entrada = FIX / "entrada-go.json"

    def _correr(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "scripts.validacion.veredicto_d2", *args],
            cwd=RAIZ, capture_output=True, text=True, timeout=30,
        )

    def test_calcular_por_cli_sale_0_y_devuelve_json_valido(self) -> None:
        r = self._correr("calcular", str(self.entrada))
        self.assertEqual(0, r.returncode, r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual("GO", doc["veredicto"]["calculado"])

    def test_comprobar_por_cli_con_validacion_coherente_sale_0(self) -> None:
        r1 = self._correr("calcular", str(self.entrada))
        validacion = Path(FIX / "_tmp_validacion_cli.json")
        validacion.write_text(r1.stdout, encoding="utf-8")
        try:
            r2 = self._correr("comprobar", str(self.entrada), str(validacion))
            self.assertEqual(0, r2.returncode, r2.stderr)
        finally:
            validacion.unlink(missing_ok=True)

    def test_sin_parametro_oficial_sale_5_por_cli(self) -> None:
        import yaml

        datos = yaml.safe_load((RAIZ / "empresa" / "parametros.yaml").read_text(encoding="utf-8"))
        datos["grupos"]["validacion"]["is_go_max"]["valor"] = None
        tmp = Path(FIX / "_tmp_parametros_sin_is_go_max.yaml")
        tmp.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
        try:
            r = self._correr("calcular", str(self.entrada), "--parametros", str(tmp))
            self.assertEqual(5, r.returncode, r.stderr)
        finally:
            tmp.unlink(missing_ok=True)

    def test_entrada_inexistente_sale_2(self) -> None:
        r = self._correr("calcular", str(FIX / "no-existe.json"))
        self.assertEqual(2, r.returncode)


@unittest.skipUnless(SKILL_DIR.is_dir(), "sin la skill d2-validacion en este árbol")
class PruebaParidadConLaSkill(unittest.TestCase):
    """Un mismo caso (entrada sintética de la skill) calculado por la skill y por scripts/validacion.

    No reimplementa los pesos de SS_a/IS (no son parámetros oficiales hoy, ver README); en cambio toma los
    AGREGADOS que la skill ya calculó (IS, n_ind_sostenidos, mecanismo, convergencia, hueco, confianza) y
    verifica que, a partir de ellos, ambos lleguen al MISMO veredicto.
    """

    def test_mismo_veredicto_que_la_skill_para_su_entrada_go(self) -> None:
        M = _cargar_modulo_skill("metricas")
        Vs = _cargar_modulo_skill("veredicto")
        valores, _ = M.P.cargar()

        entrada_skill = {
            "schema_version": "1.0.0", "oferta_id": "OF-202611-01", "candidato_id": "CAND-01", "locale": "it-IT",
            "paises_consultados": ["IT"],
            "mu": {"tipo_mecanismo": "M3", "indistinguible_de_sostenido": False, "evidencia_id": None},
            "angulo_recomendado": "calendario-cuotas", "diferenciador_sustentado": True,
            "evidencias": [{"id": f"EV-{i:02d}", "url": f"https://ejemplo.invalid/ad/{i}", "fecha": "2026-11-06"} for i in range(1, 9)],
            "mercado_resumen": {"anuncios_activos": 61, "edad_mediana_dias": 52},
            "operadores": [
                {"operador_id": f"op-0{i}", "tipo_anunciante": "producto_digital", "paises": ["IT"], "embudo": "0.5",
                 "truncado": False, "anuncios_leidos": 3, "primer_anuncio_observado_dias": 120 if i > 1 else 40,
                 "conceptos": [
                     {"concepto_id": f"c{i}1", "activo": True, "antiguedad_dias": 90, "tipo_mecanismo": mec,
                      "angulo_principal": f"angulo-{i}-1", "evidencia_id": "EV-01"},
                     {"concepto_id": f"c{i}2", "activo": True, "antiguedad_dias": 70, "tipo_mecanismo": mec,
                      "angulo_principal": f"angulo-{i}-2", "evidencia_id": "EV-01"},
                     {"concepto_id": f"c{i}3", "activo": True, "antiguedad_dias": 55, "tipo_mecanismo": mec,
                      "angulo_principal": f"angulo-{i}-3", "evidencia_id": "EV-01"},
                 ]}
                for i, mec in enumerate(["M1", "M1", "M7", "M2"], start=1)
            ],
            "huecos": [{"hueco_id": "h-01", "descripcion": "ningún sostenido unifica las cuotas en un calendario",
                        "presente_en": [], "frases": 6, "fuentes": 3, "evidencia_id": "EV-02"}],
            "sustituto_gratis": "diferenciado", "lectura_snapshots": "humano_muestreo",
            "evidencia_locale": {"e1_o_e2": 2},
            "voz": {"frases_total": 34, "frases_propias": 12, "frases_del_locale": 34,
                    "fuentes": {"foro-a.invalid": 12, "foro-b.invalid": 11, "resenas-c.invalid": 11}},
            "confianza_datos": {"competidores_profundos": 5, "competidores_con_snapshot_leido": 4, "landings_analizadas": 4,
                                "consultas_distintas": 12, "segunda_pasada": True, "videos_total": 0, "videos_transcriptos": 0,
                                "relectura_realizada": False, "historial_dias": 7, "jaccard_replica": None},
            "riesgo": {"heredado": {"nivel": "verde", "subnivel": None}, "final": {"nivel": "verde", "subnivel": None},
                       "angulo_seguro_existe": True, "reencuadre_verificable_x1": False, "x1_dictamen": "PASS"},
        }
        resultado_skill = Vs.calcular(entrada_skill, valores)
        m = resultado_skill["metricas"]

        entrada_propia = {
            "schema_version": "1.0.0", "oferta_id": "OF-202611-01", "version": "v1", "origen_version": "maker",
            "version_script": "1.0.0", "candidato_id": "CAND-01", "macro_nicho": "dinero", "consultas": [],
            "metricas_mercado": {"n_anuncios": 61, "n_anunciantes": 4, "n_sostenidos": m["metricas_mercado"]["n_sostenidos"],
                                  "edad_mediana_dias": 52},
            "saturacion": {"indice": m["IS"]["indice"], "n_ind_sostenidos": m["n_ind_sostenidos_entero"],
                           "saturacion_mecanismo": m["saturacion_mecanismo"]["nivel"], "detalle": "paridad con la skill"},
            "convergencia": {"estado": m["convergencia"]["estado"], "detalle": "paridad con la skill"},
            "huecos": ["ningún sostenido unifica las cuotas en un calendario"] if m["hueco_sustentado"] else [],
            "senales_demanda_organica": [], "restricciones_originalidad": [],
            "riesgo_politica": {"P": "verde", "C": "verde", "E": "verde", "N": "verde", "nivel": "verde",
                                 "reencuadre_aplicado": {"aplicado": False}, "fuentes": ["https://example.com/p"],
                                 "categoria": "finanzas personales", "claims_a_evitar": ["ingresos garantizados"],
                                 "angulo_seguro": "calendario de cuotas sin promesas de ingresos"},
            "no_inferible": [], "hipotesis_para_d7": [],
            "handoff_d3": {"angulos_candidatos": ["calendario-cuotas"], "objeciones_top": ["no tengo tiempo"],
                           "rango_precios_por_moneda": [{"moneda": "USD", "min": 1200, "max": 2900}],
                           "entregables_tipicos": ["guía pdf"], "prohibido_copiar": ["nombre de marca"]},
            "lectura_snapshots": entrada_skill["lectura_snapshots"],
            "voz": {"frases_total": entrada_skill["voz"]["frases_total"],
                    "fuentes_distintas": len([1 for n in entrada_skill["voz"]["fuentes"].values() if n > 0])},
            "evidencia_locale_e1_o_e2": entrada_skill["evidencia_locale"]["e1_o_e2"],
            "sustituto_gratis": entrada_skill["sustituto_gratis"],
            "angulo_seguro_existe": entrada_skill["riesgo"]["angulo_seguro_existe"],
            "reencuadre_verificable_x1": entrada_skill["riesgo"]["reencuadre_verificable_x1"],
            "x1_dictamen": entrada_skill["riesgo"]["x1_dictamen"],
            "confianza": {"puntos": m["confianza"]["puntos"], "nivel": m["confianza"]["nivel"]},
            "n_competidores": len(entrada_skill["operadores"]),
            "riesgo_subnivel": entrada_skill["riesgo"]["final"].get("subnivel"),
        }
        parametros_oficiales = {"grupos": {"validacion": {k: {"valor": valores[k]} for k in V._PARAMETROS_DECISION}}}
        doc_propio = V.calcular_validacion(entrada_propia, parametros_oficiales)
        self.assertEqual(resultado_skill["calculado"], doc_propio["veredicto"]["calculado"],
                          f"skill={resultado_skill['calculado']!r} propio={doc_propio['veredicto']['calculado']!r}; "
                          f"metricas skill={m}")


if __name__ == "__main__":
    unittest.main()
