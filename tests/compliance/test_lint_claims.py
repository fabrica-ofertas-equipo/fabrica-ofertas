"""Corpus adversarial de :mod:`compliance.lint_claims` (G-13 P01/P07/P08; docs/06 N09).

Cada caso de ``CORPUS`` declara si DEBE dar ``rojo`` (claim prohibido) o quedar limpio (``verde``,
sin falsos positivos sobre copy legítimo). Cubre salud y finanzas en es-ES y en-US, más las reglas
generales (garantías absolutas, urgencia falsa, prueba social fabricada).
"""
from __future__ import annotations

import json

from engine.errores import ErrorUso, ErrorValidacion

from compliance.hallazgos import peor_nivel
from compliance.lint_claims import extraer_textos, lint_artefacto, lint_claims, lint_texto
from compliance.reglas import cargar_reglas

from tests.compliance.apoyo import PruebaBase

# (texto, locale, macro_nicho, nivel_esperado)
CORPUS: list[tuple[str, str, str | None, str]] = [
    # --- salud, es-ES: rojo ---
    ("Este suplemento te hará sanarte del dolor de espalda para siempre", "es-ES", "salud", "rojo"),
    ("Tratamiento natural que diagnostica tu ansiedad en minutos", "es-ES", "salud", "rojo"),
    ("Baja de peso 10 kilos garantizado en dos semanas", "es-ES", "salud", "rojo"),
    # --- salud, es-ES: limpio ---
    ("Guía en PDF con rutinas de estiramiento para después de entrenar", "es-ES", "salud", "verde"),
    ("Plantillas de seguimiento de hábitos de sueño, sin diagnósticos", "es-ES", "salud", "verde"),
    # --- finanzas (dinero), es-ES: rojo ---
    ("Con este método duplica tu dinero en 30 días", "es-ES", "dinero", "rojo"),
    ("Ingresos pasivos garantizados desde el primer mes", "es-ES", "dinero", "rojo"),
    ("Gana 500€ al mes sin esfuerzo trabajando desde casa", "es-ES", "dinero", "rojo"),
    # --- finanzas, es-ES: limpio ---
    ("Plantilla de Excel para organizar tus gastos mensuales", "es-ES", "dinero", "verde"),
    ("Curso de edición de video para crear contenido en redes", "es-ES", "dinero", "verde"),
    # --- salud, en-US ---
    ("This protocol will cure your anxiety in one week", "en-US", "salud", "rojo"),
    ("A simple morning journal template to track your mood", "en-US", "salud", "verde"),
    # --- finanzas, en-US ---
    ("Get rich with this one simple trick", "en-US", "dinero", "rojo"),
    ("A budgeting spreadsheet template for freelancers", "en-US", "dinero", "verde"),
    # --- generales (independientes del macro_nicho) ---
    ("Resultados garantizados o te devolvemos tu dinero, 100% garantizado", "es-ES", None, "rojo"),
    ("Oferta termina en 10 minutos, últimas unidades", "es-ES", None, "rojo"),
    ("3.482 personas ya compraron este curso", "es-ES", None, "rojo"),
    ("Una guía breve con ejemplos y plantillas descargables", "es-ES", None, "verde"),
]


class PruebaCorpusAdversarial(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.reglas = cargar_reglas()

    def test_corpus(self) -> None:
        for texto, locale, macro_nicho, esperado in CORPUS:
            with self.subTest(texto=texto, locale=locale, macro_nicho=macro_nicho):
                hallazgos = lint_texto(texto, self.reglas, locale=locale, macro_nicho=macro_nicho)
                self.assertEqual(peor_nivel(hallazgos), esperado, f"hallazgos={[h.patron_clave for h in hallazgos]}")

    def test_locale_desconocido_es_fail_closed(self) -> None:
        with self.assertRaises(ErrorValidacion):
            lint_texto("cualquier cosa", self.reglas, locale="xx-XX")

    def test_evidencia_nunca_supera_300_caracteres(self) -> None:
        texto = "cura " * 200
        hallazgos = lint_texto(texto, self.reglas, locale="es-ES", macro_nicho="salud")
        self.assertTrue(hallazgos)
        for h in hallazgos:
            self.assertLessEqual(len(h.evidencia), 300)


# Corpus de la ola 2 (B6b): locales nuevos (it-IT, pl-PL, ro-RO, fr-FR, de-DE [HIPÓTESIS, sin
# revisor nativo], es-AR, es-MX) y la categoría "relaciones". Se prueba con el --locale REAL (no el
# proxy del oráculo .claude/skills/x1-compliance/scripts/correr_evals.py, que solo mapea es/en):
# (texto, locale, macro_nicho, nivel_esperado)
CORPUS_OLA_2: list[tuple[str, str, str | None, str]] = [
    ("Guarisci dal diabete con questo metodo naturale", "it-IT", "salud", "rojo"),
    ("Pianificatore settimanale dei pasti con lista della spesa", "it-IT", "salud", "verde"),
    ("Guadagna 2.000 € al mese da casa, senza esperienza", "it-IT", "dinero", "rojo"),
    ("Riconquista il tuo ex in 7 giorni o ti rimborsiamo", "it-IT", "relaciones", "rojo"),
    ("Wylecz cukrzycę naturalnie w 30 dni", "pl-PL", "salud", "rojo"),
    ("Zarabiaj 5000 zł miesięcznie z domu, bez doświadczenia", "pl-PL", "dinero", "rojo"),
    ("Odzyskaj byłego w 7 dni albo zwrot pieniędzy", "pl-PL", "relaciones", "rojo"),
    ("Planer tygodniowy posiłków z listą zakupów", "pl-PL", "salud", "verde"),
    ("Vindecă diabetul natural fără medicamente", "ro-RO", "salud", "rojo"),
    ("Guérissez votre anxiété sans médicaments", "fr-FR", "salud", "rojo"),
    ("Heile deine Angst ohne Medikamente", "de-DE", "salud", "rojo"),
    ("Perdé 8 kilos en 30 días con este menú", "es-AR", "salud", "rojo"),
    ("Recuperá a tu ex en 7 días o te devolvemos la plata", "es-AR", "relaciones", "rojo"),
    ("Bájale 8 kilos en un mes con este plan alimenticio", "es-MX", "salud", "rojo"),
    ("Si tu ex no regresa en una semana, te regresamos tu dinero", "es-MX", "relaciones", "rojo"),
    ("Calendario de gastos de temporada: hoja para imprimir", "es-MX", "dinero", "verde"),
]


class PruebaCorpusOla2Locales(PruebaBase):
    """it-IT/pl-PL/ro-RO/fr-FR/de-DE (D-02 ampliación, [HIPÓTESIS] sin revisor nativo), es-AR/es-MX
    (voseo y slang) y la categoría "relaciones" (pedido de X1 en el README de B6)."""

    def setUp(self) -> None:
        super().setUp()
        self.reglas = cargar_reglas()

    def test_corpus_ola_2(self) -> None:
        for texto, locale, macro_nicho, esperado in CORPUS_OLA_2:
            with self.subTest(texto=texto, locale=locale):
                hallazgos = lint_texto(texto, self.reglas, locale=locale, macro_nicho=macro_nicho)
                self.assertEqual(peor_nivel(hallazgos), esperado, f"hallazgos={[h.patron_clave for h in hallazgos]}")

    def test_avisos_de_revision_nativa_en_la_cli(self) -> None:
        import json as _json

        archivo = self.tmp / "copy.txt"
        archivo.write_text("Guarisci dal diabete", encoding="utf-8")
        salida_buffer = []
        import io
        from contextlib import redirect_stdout

        from compliance.lint_claims import main as lint_main

        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = lint_main(["--archivo", str(archivo), "--locale", "it-IT", "--json"])
        self.assertEqual(codigo, 3)  # "guarisci" es rojo
        salida = _json.loads(buf.getvalue())
        self.assertTrue(any("revisión nativa" in a for a in salida["avisos"]))


class PruebaExtraerYLintearArtefactos(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.reglas = cargar_reglas()

    def test_extraer_textos_recorre_mapas_y_listas(self) -> None:
        datos = {"titulo": "Hola", "claims": [{"texto": "Cura tu ansiedad"}, {"texto": "Plantilla simple"}]}
        textos = dict(extraer_textos(datos))
        self.assertIn("Hola", textos.values())
        self.assertIn("Cura tu ansiedad", textos.values())

    def test_extraer_textos_ignora_cadenas_vacias(self) -> None:
        self.assertEqual(extraer_textos({"a": "", "b": "  "}), [])

    def test_lint_artefacto_encuentra_un_claim_dentro_de_una_lista_anidada(self) -> None:
        datos = {"oferta": {"promesa": {"claims_permitidos": [{"texto": "Resultados garantizados 100% garantizado"}]}}}
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES", macro_nicho="dinero")
        self.assertEqual(peor_nivel(hallazgos), "rojo")

    def test_lint_claims_sobre_archivo_json(self) -> None:
        archivo = self.tmp / "oferta.json"
        archivo.write_text(json.dumps({"titulo": "Cura tu ansiedad para siempre"}), encoding="utf-8")
        resultado = lint_claims(archivo, locale="es-ES", macro_nicho="salud", reglas=self.reglas)
        self.assertEqual(resultado.semaforo, "rojo")
        self.assertEqual(resultado.reglas_version, self.reglas.reglas_version)

    def test_lint_claims_sobre_archivo_de_texto_plano(self) -> None:
        archivo = self.tmp / "copy.txt"
        archivo.write_text("Una plantilla sencilla para organizar tareas", encoding="utf-8")
        resultado = lint_claims(archivo, locale="es-ES", reglas=self.reglas)
        self.assertEqual(resultado.semaforo, "verde")

    def test_lint_claims_archivo_inexistente_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            lint_claims(self.tmp / "no-existe.txt", locale="es-ES", reglas=self.reglas)


class PruebaClavesListaNegra(PruebaBase):
    """Decisión 1b (``compliance/README.md``): ``claims_prohibidos``/``claims_a_evitar`` describen a
    propósito las frases prohibidas de una oferta; no son una afirmación propia, PERO la misma
    frase fuera de esas claves exactas sigue dando ROJO (no es un blanqueo)."""

    def setUp(self) -> None:
        super().setUp()
        self.reglas = cargar_reglas()
        # Frase neutra (no coincide con ningún patrón de reglas_sensibles.yaml por sí sola): así la
        # prueba aísla el mecanismo de lista negra de una coincidencia "normal" del lint.
        self.frase = "frase de prueba sin relacion con ningun patron de cumplimiento"

    def test_la_clave_declarada_no_se_lintea_como_afirmacion(self) -> None:
        datos = {"promesa": {"claims_prohibidos": [self.frase]}}
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES")
        self.assertEqual(hallazgos, [])

    def test_la_misma_frase_en_una_clave_con_nombre_parecido_sigue_siendo_rojo(self) -> None:
        datos = {
            "promesa": {"claims_prohibidos": [self.frase]},
            "notas_internas": {"claims_prohibidos_x": [self.frase]},
        }
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES")
        self.assertEqual(peor_nivel(hallazgos), "rojo")
        self.assertIn("lista_negra:fuga", [h.patron_clave for h in hallazgos])

    def test_la_misma_frase_en_un_array_anidado_distinto_sigue_siendo_rojo(self) -> None:
        datos = {
            "riesgo": {"claims_a_evitar": [self.frase]},
            "borradores": {"ideas": [{"variantes": [self.frase, "otra idea sin relación"]}]},
        }
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES")
        self.assertEqual(peor_nivel(hallazgos), "rojo")
        self.assertIn("lista_negra:fuga", [h.patron_clave for h in hallazgos])

    def test_sin_fuga_el_resto_del_artefacto_queda_limpio(self) -> None:
        datos = {"promesa": {"claims_prohibidos": [self.frase]}, "titulo": "Una plantilla sencilla"}
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES")
        self.assertEqual(hallazgos, [])


class PruebaCamposProhibidosDeTracking(PruebaBase):
    """``tracking.json › datos_sensibles › campos_prohibidos`` es una lista negra declarada (mismo criterio que
    ``claims_prohibidos``): lo que enumera no es una afirmación, pero esas frases en otro campo siguen en ROJO."""

    def setUp(self) -> None:
        super().setUp()
        self.reglas = cargar_reglas()
        self.campo = "diagnostico medico de la persona compradora"

    def _tracking(self, **extra) -> dict:
        base = {"eventos": [{"nombre": "Purchase", "parametros": ["value", "currency"]}],
                "datos_sensibles": {"campos_prohibidos": [self.campo, "condicion de salud declarada"]}}
        base.update(extra)
        return base

    def test_la_lista_declarada_de_tracking_no_da_rojo(self) -> None:
        hallazgos = lint_artefacto(self._tracking(), self.reglas, locale="es-ES")
        self.assertEqual(hallazgos, [])

    def test_la_misma_frase_fuera_de_la_lista_si_da_rojo(self) -> None:
        datos = self._tracking(notas={"observaciones": f"enviamos el {self.campo} a Meta"})
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES")
        self.assertEqual(peor_nivel(hallazgos), "rojo")
        self.assertIn("lista_negra:fuga", [h.patron_clave for h in hallazgos])

    def test_una_clave_de_nombre_parecido_no_queda_exenta(self) -> None:
        datos = self._tracking(datos_sensibles_x={"campos_prohibidos_extra": [self.campo]})
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES")
        self.assertEqual(peor_nivel(hallazgos), "rojo")

    def test_un_claim_real_escrito_en_otro_campo_sigue_detectandose(self) -> None:
        datos = self._tracking(descripcion="Pierde 8 kg en 7 dias")
        hallazgos = lint_artefacto(datos, self.reglas, locale="es-ES")
        self.assertEqual(peor_nivel(hallazgos), "rojo")


class PruebaRutaOfertaEtapaD5IncluyeSitio(PruebaBase):
    """D-02c: ``--oferta --etapa D5`` debe lintear también el HTML de ``05-landing/sitio``."""

    def test_incluye_html_del_sitio_para_d5(self) -> None:
        from compliance.lint_claims import _ruta_oferta_etapa

        base = self.tmp / "ofertas" / "OF-202611-01"
        (base / "05-landing" / "sitio").mkdir(parents=True)
        (base / "05-landing" / "sitio" / "index.html").write_text("<html></html>", encoding="utf-8")
        (base / "05-landing").mkdir(exist_ok=True)
        rutas = _ruta_oferta_etapa("OF-202611-01", "D5", raiz=self.tmp)
        self.assertIn(base / "05-landing" / "sitio" / "index.html", rutas)

    def test_sin_carpeta_de_sitio_solo_devuelve_los_json(self) -> None:
        from compliance.lint_claims import _ruta_oferta_etapa

        rutas = _ruta_oferta_etapa("OF-202611-01", "D5", raiz=self.tmp)
        self.assertTrue(all(r.suffix == ".json" for r in rutas))


if __name__ == "__main__":
    import unittest

    unittest.main()
