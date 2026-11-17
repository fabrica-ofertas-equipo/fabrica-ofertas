"""CT-3, lote A (configuración): A-01 (`comunes` 1.4.0), A-03 (`monedas_iso4217.json`), A-04 (`limites` 1.3.0), A-05 (`GATE_ACTIVAR_H`),
A-06 (`CLAVES_CRITICAS["descubrir"]`), A-09 (los cuatro grupos opcionales en la plantilla de `parametros`) y A-12 (comentarios de las plantillas).
Backlog: ``docs/_historial/ct3-backlog.md`` §4.1 y «Correcciones de la crítica». Sin red; solo lectura del repositorio y copias en memoria."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
EJ_LIM = V.DIR_EJEMPLOS / "limites.valido.yaml"
CLAVES_RIESGO = ("hojas_pausadas", "nivel_max_lanzable", "cuota_gasto_amarillo_max_pct", "cuota_gasto_amarillo_b_max_pct", "envios_amarillo_a_semana",
                 "envios_amarillo_b_mes", "dias_limpios_para_subir_cuota", "edad_minima_audiencia", "reserva_dias_stripe", "zonas_grises")
GRUPOS_A09 = ("estadistica", "agentes", "ingesta", "watchdog")


def limites_resellados(d: dict) -> dict:
    d = copy.deepcopy(d)
    d["sello"] = {**d["sello"], "hash": V.sello_de_limites(d)}
    return d


def mensajes(errs) -> list[str]:
    return [f"{e.validator}@{V.ruta_json(e)}" for e in errs]


# ----------------------------------------------------------------------------------------------------------------------------
# A-01 · comunes 1.4.0
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaComunes140(unittest.TestCase):
    def setUp(self) -> None:
        _, self.esq = V.cargar_esquemas()
        self.d = self.esq["comunes"]["$defs"]

    def test_version_y_motivo_nuevo(self) -> None:
        self.assertEqual("1.4.0", self.esq["comunes"]["x-version"])
        self.assertEqual(11, len(self.d["motivo_rechazo"]["enum"]))
        self.assertIn("linea_roja_de_contenido_o_negocio", self.d["motivo_rechazo"]["enum"])
        for extra in ("duplicado_de_la_memoria", "evidencia_insuficiente", "inviable_sin_backend"):   # D-07: no se agregan
            self.assertNotIn(extra, self.d["motivo_rechazo"]["enum"])

    def test_el_motivo_nuevo_valida_en_un_descarte_de_candidatos(self) -> None:
        c = json.loads((V.DIR_EJEMPLOS / "candidatos.valido.json").read_text(encoding="utf-8"))
        self.assertTrue(c["descartados"], "el ejemplo válido debe traer al menos un descartado")
        c["descartados"][0]["motivo"] = "linea_roja_de_contenido_o_negocio"
        self.assertEqual([], V.errores_de_esquema("candidatos", c))
        c["descartados"][0]["motivo"] = "inventado"
        self.assertTrue(V.errores_de_esquema("candidatos", c))

    def test_nivel_lanzable_en_minusculas(self) -> None:
        self.assertEqual(["verde", "amarillo-a", "amarillo-b"], self.d["nivel_lanzable"]["enum"])
        self.assertNotIn("rojo", self.d["nivel_lanzable"]["enum"])

    def test_el_subnivel_de_candidatos_no_usa_nivel_lanzable(self) -> None:
        """Crítica C-08: `candidatos.riesgo.subnivel` es A | B | null (otro campo); el enum nuevo es solo de limites y campana."""
        c = json.loads((V.DIR_EJEMPLOS / "candidatos.valido.json").read_text(encoding="utf-8"))
        riesgo = self.esq["candidatos"]["$defs"]["riesgo"]
        refs = json.dumps(riesgo)
        self.assertNotIn("nivel_lanzable", refs)
        self.assertEqual([], V.errores_de_esquema("candidatos", c))


# ----------------------------------------------------------------------------------------------------------------------------
# A-03 · monedas_iso4217.json
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaMonedasIso4217(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = json.loads((V.DIR_CONTRATOS / "monedas_iso4217.json").read_text(encoding="utf-8"))

    def test_igual_a_la_fuente_unica_del_validador(self) -> None:
        self.assertEqual(V.EXPONENTE_ISO4217, self.doc["exponentes"])   # si difieren, hay que volver a volcar (el validador manda)

    def test_forma_y_metadatos(self) -> None:
        self.assertEqual({"schema_version", "descripcion", "fuente", "fecha_lectura", "exponentes"}, set(self.doc))
        self.assertEqual("1.0.0", self.doc["schema_version"])
        self.assertRegex(self.doc["fecha_lectura"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(self.doc["fuente"].startswith("Lista oficial SIX/ISO 4217"))
        for moneda, e in self.doc["exponentes"].items():
            self.assertRegex(moneda, r"^[A-Z]{3}$")
            self.assertIn(e, (0, 2), moneda)                     # ninguna moneda operable usa otro exponente hoy
            self.assertIs(type(e), int)                          # entero, nunca float ni bool
        self.assertEqual(sorted(self.doc["exponentes"]), list(self.doc["exponentes"]))   # orden estable: el diff de un re-volcado es legible

    def test_valores_conocidos_y_cero_decimales(self) -> None:
        e = self.doc["exponentes"]
        self.assertEqual((2, 2, 0, 0), (e["EUR"], e["USD"], e["JPY"], e["CLP"]))
        self.assertNotIn("XXX", e)

    def test_no_lo_toma_el_cargador_de_esquemas(self) -> None:
        _, esq = V.cargar_esquemas()
        self.assertNotIn("monedas_iso4217", esq)


# ----------------------------------------------------------------------------------------------------------------------------
# A-04 · limites 1.3.0
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaLimites130(unittest.TestCase):
    def setUp(self) -> None:
        _, self.esq = V.cargar_esquemas()
        self.ej = V.cargar_yaml(EJ_LIM)
        self.plantilla = V.cargar_yaml(RAIZ / "empresa" / "limites.yaml")

    def errores(self, d: dict) -> list:
        return V.errores_de_esquema("limites", d)

    def test_version_y_claves_nuevas(self) -> None:
        self.assertEqual("1.3.0", self.esq["limites"]["x-version"])
        for k in CLAVES_RIESGO:
            self.assertIn(k, self.esq["limites"]["properties"], k)
        self.assertNotIn("boton_max_lanzamientos_dia", self.esq["limites"]["properties"])   # S-31: ningún código lo lee

    def test_ejemplo_y_plantilla_validos_en_1_3_0(self) -> None:
        for nombre, d in (("ejemplo", self.ej), ("plantilla", self.plantilla)):
            self.assertEqual("1.3.0", d["schema_version"], nombre)
            self.assertEqual([], self.errores(d), nombre)
            self.assertEqual([], V.buscar_floats(d), nombre)

    def test_las_diez_claves_son_obligatorias_solo_desde_1_3_0(self) -> None:
        for k in CLAVES_RIESGO:
            d = copy.deepcopy(self.ej); d.pop(k)
            self.assertIn("required@", "".join(mensajes(self.errores(d))), k)
        for ver in ("1.0.0", "1.2.0"):                                # fixtures viejos (S-B y S-C) siguen válidos sin las claves
            d = copy.deepcopy(self.ej); d["schema_version"] = ver
            for k in CLAVES_RIESGO:
                d.pop(k)
            self.assertEqual([], self.errores(d), ver)
        d = copy.deepcopy(self.ej); d["schema_version"] = "1.10.0"   # el patrón no se rompe con 1.10
        d.pop("zonas_grises")
        self.assertTrue(self.errores(d))

    def test_fixtures_de_otras_sesiones_siguen_validos(self) -> None:
        for ruta in sorted((RAIZ / "tests" / "fixtures").rglob("limites.yaml")):
            d = V.cargar_yaml(ruta)
            if isinstance(d, dict) and str(d.get("schema_version", "")).startswith("1."):
                # algunos fixtures son recortes (otras claves faltan por diseño): lo que importa es que las claves NUEVAS no se exijan a una versión < 1.3.0
                nuevos = [e for e in self.errores(d) if any(f"'{k}'" in e.message for k in CLAVES_RIESGO)]
                self.assertEqual([], nuevos, str(ruta.relative_to(RAIZ)))

    def test_la_plantilla_del_dueno_queda_en_null_y_sin_sello(self) -> None:
        p = self.plantilla
        self.assertIsNone(p["sello"])
        self.assertEqual([], p["hojas_pausadas"])
        self.assertEqual({}, p["zonas_grises"])
        for k in CLAVES_RIESGO:
            if k not in ("hojas_pausadas", "zonas_grises"):
                self.assertIsNone(p[k], k)                           # regla 3: lo fija el dueño
        self.assertIsNone(p["ratio_disputas_pausa"])

    def test_nivel_max_lanzable_exige_minusculas_y_las_tres_macros(self) -> None:
        d = copy.deepcopy(self.ej)
        d["nivel_max_lanzable"] = {"salud": "amarillo-A", "relaciones": "verde", "dinero": "verde"}
        self.assertIn("enum@/nivel_max_lanzable/salud", mensajes(self.errores(d)))
        d["nivel_max_lanzable"] = {"salud": "rojo", "relaciones": "verde", "dinero": "verde"}
        self.assertTrue(self.errores(d))                              # el rojo no se lanza
        d["nivel_max_lanzable"] = {"salud": "verde", "relaciones": "verde"}
        self.assertIn("required@/nivel_max_lanzable", mensajes(self.errores(d)))
        d["nivel_max_lanzable"] = {"salud": "verde", "relaciones": "verde", "dinero": "verde", "cripto": "verde"}
        self.assertTrue(self.errores(d))
        for ok in ({"salud": "amarillo-b", "relaciones": "amarillo-a", "dinero": "verde"}, None):
            d["nivel_max_lanzable"] = ok
            self.assertEqual([], self.errores(d))

    def test_cuotas_enteros_0_a_100(self) -> None:
        for k in ("cuota_gasto_amarillo_max_pct", "cuota_gasto_amarillo_b_max_pct"):
            for malo in (101, -1, "30", 30.0, True):
                d = copy.deepcopy(self.ej); d[k] = malo
                self.assertTrue(self.errores(d) or V.buscar_floats(d), f"{k}={malo!r}")
            for bueno in (0, 30, 100, None):
                d = copy.deepcopy(self.ej); d[k] = bueno
                self.assertEqual([], self.errores(d), f"{k}={bueno!r}")

    def test_conteos_y_dias_enteros_desde_1(self) -> None:
        for k in ("envios_amarillo_a_semana", "envios_amarillo_b_mes", "dias_limpios_para_subir_cuota", "reserva_dias_stripe"):
            for malo in (0, -3, "3", 2.5, False):
                d = copy.deepcopy(self.ej); d[k] = malo
                self.assertTrue(self.errores(d) or V.buscar_floats(d), f"{k}={malo!r}")
            d = copy.deepcopy(self.ej); d[k] = None
            self.assertEqual([], self.errores(d), k)

    def test_edad_minima_audiencia(self) -> None:
        for malo in ({"defecto": 12}, {"defecto": 66}, {"defecto": "18"}, {}, {"defecto": 18, "otra": 1}):
            d = copy.deepcopy(self.ej); d["edad_minima_audiencia"] = malo
            self.assertTrue(self.errores(d), malo)
        d = copy.deepcopy(self.ej); d["edad_minima_audiencia"] = {"defecto": 25}
        self.assertEqual([], self.errores(d))

    def test_hojas_y_zonas(self) -> None:
        d = copy.deepcopy(self.ej)
        d["hojas_pausadas"] = ["hoja-uno", "hoja-uno"]
        self.assertTrue(self.errores(d))                              # únicas
        d["hojas_pausadas"] = ["Hoja Uno"]
        self.assertTrue(self.errores(d))                              # kebab
        d = copy.deepcopy(self.ej)
        d["zonas_grises"] = {"Z1": "cerrado"}
        self.assertTrue(self.errores(d))                              # ids en minúsculas
        d["zonas_grises"] = {"z1_planner_peso": 1}
        self.assertTrue(self.errores(d))                              # decisión = cadena
        d["zonas_grises"] = {"z1_planner_peso": "cerrado", "astrologia": "cerrado"}
        self.assertEqual([], self.errores(d))

    def test_null_es_solo_verde_no_un_dato_faltante(self) -> None:
        """Crítica C-07: evaluar_limites NO cambia; null en las claves de riesgo no bloquea ni 'activar'."""
        d = copy.deepcopy(self.ej)
        for k in CLAVES_RIESGO:
            d[k] = [] if k == "hojas_pausadas" else ({} if k == "zonas_grises" else None)
        d = limites_resellados(d)
        self.assertEqual([], self.errores(d))
        for op in ("gastar", "activar"):
            self.assertTrue(V.evaluar_limites(d, op, entorno="prueba"), op)
        for op, claves in V.CLAVES_CRITICAS.items():
            self.assertFalse(set(CLAVES_RIESGO) & set(claves), op)    # ninguna operación las exige

    def test_cuota_b_no_supera_cuota_amarillo(self) -> None:
        d = copy.deepcopy(self.ej)
        self.assertEqual([], V.coherencia_limites(d))
        d["cuota_gasto_amarillo_b_max_pct"] = 31                      # > 30
        self.assertTrue(any("amarillo-b es parte de amarillo" in m for m in V.coherencia_limites(d)))
        res = V.evaluar_limites(limites_resellados(d), "gastar", entorno="prueba")
        self.assertFalse(res)
        self.assertEqual(["coherencia"], res.faltantes)
        d["cuota_gasto_amarillo_max_pct"] = None                      # null = solo verde: no se compara
        self.assertEqual([], V.coherencia_limites(d))

    def test_ejemplo_sellado_y_utilizable(self) -> None:
        self.assertEqual(self.ej["sello"]["hash"], V.sello_de_limites(self.ej))
        self.assertTrue(V.evaluar_limites(self.ej, "activar", entorno="prueba"))
        self.assertEqual([], V.coherencia_limites(self.ej))

    def test_ejemplos_nuevos_del_directorio(self) -> None:
        nombres = {p.name for p in V.DIR_EJEMPLOS.glob("limites.*.yaml")}
        self.assertIn("limites.valido-solo-verde-sin-sello.yaml", nombres)
        invalidos = sorted(n for n in nombres if n.startswith("limites.invalido-"))
        self.assertGreaterEqual(len(invalidos), 6)
        for n in invalidos:
            self.assertTrue((V.DIR_EJEMPLOS / n.replace(".yaml", ".motivo.txt")).exists(), n)


# ----------------------------------------------------------------------------------------------------------------------------
# A-05 · acciones_gate_humano frente a gates.json (C-04)
# ----------------------------------------------------------------------------------------------------------------------------
def autonomia_con(**niveles: str) -> dict:
    a = copy.deepcopy(V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"))
    for etapa, nivel in niveles.items():
        a["nivel_por_etapa"][etapa]["nivel"] = nivel
    return a


class PruebaGateActivar(unittest.TestCase):
    def setUp(self) -> None:
        self.lim = V.cargar_yaml(EJ_LIM)

    def test_las_seis_minimas_no_se_pueden_quitar_ni_con_firma(self) -> None:
        for accion in sorted(V.ACCIONES_GATE_MINIMAS):
            d = copy.deepcopy(self.lim)
            d["acciones_gate_humano"] = [a for a in d["acciones_gate_humano"] if a != accion]
            d = limites_resellados(d)                                  # "con firma": sello válido sobre el contenido recortado
            self.assertTrue(V.errores_de_esquema("limites", d), accion)
            self.assertFalse(V.evaluar_limites(d, "gastar", entorno="prueba"), accion)
            self.assertTrue(V.coherencia_limites(d), accion)

    def test_agregar_acciones_si_se_puede(self) -> None:
        d = copy.deepcopy(self.lim)
        d["acciones_gate_humano"] = d["acciones_gate_humano"] + ["subir_presupuesto", "publicar_landing"]
        self.assertEqual([], V.errores_de_esquema("limites", d))

    def test_aviso_con_d7_o_m1_desde_n3(self) -> None:
        self.assertEqual([], V.coherencia_gate_activar(self.lim, autonomia_con()))                       # N2: sin aviso
        self.assertEqual([], V.coherencia_gate_activar(self.lim, autonomia_con(D7="N2", M1="N2")))
        m = V.coherencia_gate_activar(self.lim, autonomia_con(D7="N3"))
        self.assertEqual(1, len(m))
        self.assertIn("accion:activar_campana", m[0])
        self.assertIn("no se quita ni con firma", m[0])
        m = V.coherencia_gate_activar(self.lim, autonomia_con(M1="N4"))
        self.assertEqual(1, len(m))
        self.assertIn("lanzamiento_pais_idioma_nuevo", m[0])
        self.assertEqual(2, len(V.coherencia_gate_activar(self.lim, autonomia_con(D7="N4", M1="N3"))))
        self.assertEqual([], V.coherencia_gate_activar(self.lim, autonomia_con(D8="N4", D9="N4")))     # otras etapas no activan

    def test_sin_datos_no_hay_aviso_ni_excepcion(self) -> None:
        self.assertEqual([], V.coherencia_gate_activar(self.lim, None))
        self.assertEqual([], V.coherencia_gate_activar(self.lim, {}))
        self.assertEqual([], V.coherencia_gate_activar(self.lim, {"nivel_por_etapa": {"D7": {}}}))
        self.assertEqual(1, len(V.coherencia_gate_activar(None, autonomia_con(D7="N3"))))               # las mínimas rigen aunque no haya archivo

    def test_nunca_es_error_en_una_oferta(self) -> None:
        ej = RAIZ / "ofertas" / "_ejemplo"
        inf = V.validar_oferta(ej, limites=self.lim, autonomia=autonomia_con(D7="N3"), clave_firma=V.CLAVE_DE_PRUEBA)
        hall = [h for h in inf.hallazgos if h.codigo == "GATE_ACTIVAR_H"]
        self.assertEqual(1, len(hall))
        self.assertEqual("AVISO", hall[0].nivel)
        base = V.validar_oferta(ej, limites=self.lim, autonomia=autonomia_con(), clave_firma=V.CLAVE_DE_PRUEBA)
        self.assertEqual([], [h for h in base.hallazgos if h.codigo == "GATE_ACTIVAR_H"])
        self.assertNotIn("GATE_ACTIVAR_H", {e.codigo for e in inf.errores})

    def test_la_plantilla_de_autonomia_no_avisa(self) -> None:
        inf = V.validar_cartera_de_empresa()
        self.assertEqual([], [h for h in inf.hallazgos if h.codigo == "GATE_ACTIVAR_H"])               # todo en N0
        self.assertEqual([], inf.errores)


# ----------------------------------------------------------------------------------------------------------------------------
# A-06 · CLAVES_CRITICAS["descubrir"]
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaClavesCriticasDescubrir(unittest.TestCase):
    def test_incluye_max_consultas_biblioteca(self) -> None:
        self.assertIn("max_consultas_biblioteca", V.CLAVES_CRITICAS["descubrir"])
        self.assertNotIn("max_capturas_web_por_dia", V.CLAVES_CRITICAS["descubrir"])   # entra con CT-4 (S-01)

    def test_null_bloquea_descubrir_y_solo_descubrir(self) -> None:
        d = V.cargar_yaml(EJ_LIM)
        d["max_consultas_biblioteca"] = None
        d = limites_resellados(d)
        res = V.evaluar_limites(d, "descubrir", entorno="prueba")
        self.assertFalse(res)
        self.assertEqual(["max_consultas_biblioteca"], res.faltantes)
        self.assertTrue(V.evaluar_limites(d, "gastar", entorno="prueba"))

    def test_ejemplo_completo_descubre(self) -> None:
        self.assertTrue(V.evaluar_limites(V.cargar_yaml(EJ_LIM), "descubrir", entorno="prueba"))


# ----------------------------------------------------------------------------------------------------------------------------
# A-09 · parametros: plantilla con los cuatro grupos opcionales (sin subir la versión)
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaPlantillaParametros(unittest.TestCase):
    def setUp(self) -> None:
        self.par = V.cargar_yaml(RAIZ / "empresa" / "parametros.yaml")
        self.gemelo = V.cargar_yaml(V.DIR_EJEMPLOS / "parametros.valido.yaml")
        self.overlay = V.cargar_yaml(RAIZ / "empresa" / "propuestas" / "parametros-b0.yaml")

    def test_version_no_sube_y_valida(self) -> None:
        _, esq = V.cargar_esquemas()
        self.assertEqual("1.1.0", esq["parametros"]["x-version"])      # 1.2.0 sigue reservada a modelado_* (C20, crítica C-05)
        self.assertEqual("1.1.0", self.par["schema_version"])
        self.assertEqual([], V.errores_de_esquema("parametros", self.par))
        self.assertEqual([], V.coherencia_parametros(self.par))
        self.assertEqual({}, V.claves_duplicadas(self.par))
        self.assertEqual([], V.buscar_floats(self.par))
        self.assertNotIn("modelado_", json.dumps(self.par))             # regla 3: modelado_* no se integra

    def test_los_cuatro_grupos_completos(self) -> None:
        g = self.par["grupos"]
        self.assertEqual({"estadistica": 18, "agentes": 18, "ingesta": 3, "watchdog": 3}, {k: len(g[k]) for k in GRUPOS_A09})
        for k in GRUPOS_A09:
            self.assertEqual(self.overlay["grupos"][k], g[k], k)       # mismos valores del overlay aprobado para la plantilla
        _, esq = V.cargar_esquemas()
        props = esq["parametros"]["properties"]["grupos"]["properties"]
        for k in GRUPOS_A09:
            self.assertEqual(set(props[k]["required"]), set(g[k]), k)

    def test_claves_canonicas_del_evento_de_optimizacion(self) -> None:
        e = self.par["grupos"]["estadistica"]
        self.assertEqual(50, e["meta_eventos_aprendizaje_semana"]["valor"])
        self.assertIs(False, e["meta_eventos_aprendizaje_semana"]["hipotesis"])      # hecho de plataforma HC-1
        self.assertEqual("0.5", e["meta_fraccion_min_purchase"]["valor"])            # fracción decimal en cadena (no bp: traduce decision/entradas.py)
        self.assertIs(True, e["meta_fraccion_min_purchase"]["hipotesis"])
        flat = {k for grupo in self.par["grupos"].values() for k in grupo}
        self.assertNotIn("eventos_semana_aprendizaje", flat)                         # el nombre de engine.factibilidad NO es clave de parámetros
        self.assertNotIn("fraccion_aprendizaje_min_bp", flat)

    def test_agentes_todo_null_y_con_estado_max_edad_h(self) -> None:
        a = self.par["grupos"]["agentes"]
        self.assertIn("estado_max_edad_h", a)                                        # LT-25
        self.assertEqual([], [k for k, p in a.items() if p["valor"] is not None])    # el runner en vivo falla cerrado hasta calibrar
        for k, p in a.items():
            self.assertIs(True, p["hipotesis"], k)
            self.assertIsNone(p["ultima_calibracion"], k)

    def test_hipotesis_con_fuente_y_sin_calibrar(self) -> None:
        for g in GRUPOS_A09:
            for k, p in self.par["grupos"][g].items():
                self.assertTrue(p["fuente"], f"{g}.{k}")
                self.assertIsNone(p["ultima_calibracion"], f"{g}.{k}")

    def test_fail_closed_runner_en_vivo_y_decision_sin_parametros_faltantes(self) -> None:
        self.assertTrue(V.parametros_faltantes(self.par, V.OPERACION_PARAMETROS["runner_vivo"]))     # agentes null = ParametroFaltante (5)
        for op in ("decidir_d8", "ingesta", "watchdog"):
            self.assertEqual([], V.parametros_faltantes(self.par, V.OPERACION_PARAMETROS[op]), op)

    def test_un_grupo_presente_se_valida_completo(self) -> None:
        d = copy.deepcopy(self.par)
        d["grupos"]["watchdog"].pop("ciclo_max_min")
        self.assertTrue(V.errores_de_esquema("parametros", d))

    def test_ejemplo_gemelo_identico_a_la_plantilla(self) -> None:
        self.assertEqual(self.par, self.gemelo)      # solo difieren en comentarios

    def test_semantica_documentada_en_comentarios(self) -> None:
        txt = (RAIZ / "empresa" / "parametros.yaml").read_text(encoding="utf-8")
        for fragmento in ("Tope ABSOLUTO de días de una corrida de campaña", "veredicto.dias_max", "OBSOLETA", "testeo.cobertura_adid_min_pct",
                          "[DUEÑO] D-01", "decision/entradas.py"):
            self.assertIn(fragmento, txt, fragmento)

    def test_valores_existentes_sin_cambio(self) -> None:
        g = self.par["grupos"]
        self.assertEqual("0.3", g["salud_operativa"]["disputas_alerta_pct"]["valor"])    # S-22/D-01: lo decide el dueño
        self.assertEqual(30, g["campana"]["dias_test_max"]["valor"])
        self.assertEqual(70, g["dashboard"]["cobertura_atribucion_min_pct"]["valor"])    # R-06: obsoleta pero no se retira (sería MAJOR)


# ----------------------------------------------------------------------------------------------------------------------------
# A-12 · comentarios de la plantilla de limites y autonomia
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaComentariosPlantillas(unittest.TestCase):
    def test_limites_no_promete_quitar_sin_firma(self) -> None:
        txt = (RAIZ / "empresa" / "limites.yaml").read_text(encoding="utf-8")
        self.assertNotIn("se pueden agregar, no quitar sin firma", txt)       # el comentario viejo era falso (H-1)
        for fragmento in ("NO se pueden quitar, NI CON FIRMA", "GATE_ACTIVAR_H", "D-02", "0.005", "[DUEÑO] D-01", "SOLO VERDE"):
            self.assertIn(fragmento, txt, fragmento)
        self.assertNotIn("0.006 = 0,6 %", txt)

    def test_el_esquema_dice_lo_mismo(self) -> None:
        _, esq = V.cargar_esquemas()
        d = esq["limites"]["properties"]["acciones_gate_humano"]["description"]
        self.assertIn("NO se pueden quitar, ni con firma", d)
        self.assertNotIn("sin firma)", d)
        self.assertIn("0.005", esq["limites"]["properties"]["ratio_disputas_pausa"]["description"])

    def test_autonomia_sigue_en_n0_y_valida(self) -> None:
        a = V.cargar_yaml(RAIZ / "empresa" / "autonomia.yaml")
        self.assertEqual([], V.errores_de_esquema("autonomia", a))
        self.assertEqual({"N0"}, {e["nivel"] for e in a["nivel_por_etapa"].values()})

    def test_ninguna_plantilla_exige_gestor_llaves_ni_segundo_admin(self) -> None:
        """Decisión 15 (backbone v2.2.3)."""
        for n in ("limites", "parametros", "autonomia"):
            txt = (RAIZ / "empresa" / f"{n}.yaml").read_text(encoding="utf-8").lower()
            for prohibido in ("gestor de contraseñas", "llave física", "llaves físicas", "segundo administrador"):
                self.assertNotIn(prohibido, txt, f"{n}: {prohibido}")


if __name__ == "__main__":
    unittest.main()
