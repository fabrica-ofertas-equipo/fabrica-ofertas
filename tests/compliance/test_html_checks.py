"""``compliance.html_checks`` contra B0-11: casillas premarcadas, píxel sin consentimiento, enlaces
legales y temporizadores sin fecha verificable, más términos sensibles en ``title``/``og:*`` (D01).

Cubre 4 de las 8 mutaciones de B0-11 (las otras 4 — precio/moneda/garantía/datos de salud en
``tracking.json`` — son de ``landing.generar/validar``, B4; ver ``compliance/README.md``).
"""
from __future__ import annotations

from compliance.hallazgos import peor_nivel
from compliance.html_checks import LEGALES_REQUERIDAS, verificar_html
from compliance.reglas import cargar_reglas

from tests.compliance.apoyo import PruebaBase

_LEGALES_OK = "".join(f'<a data-legal="{clave}" href="{ruta}">{clave}</a>' for clave, ruta in LEGALES_REQUERIDAS.items())
_PIXEL_GATEADO = (
    '<script>if (consentimiento.aceptado) { var s = document.createElement("script"); '
    's.src = "https://connect.facebook.net/en_US/fbevents.js"; document.head.appendChild(s); }</script>'
)
_HTML_LIMPIO = f"""<html><head><title>Oferta</title>
{_PIXEL_GATEADO}
</head><body>
<input type="checkbox" name="acepto">
{_LEGALES_OK}
<div class="countdown" data-deadline="2026-11-10T00:00:00Z">10:00</div>
</body></html>"""


class PruebaCasoLimpio(PruebaBase):
    def test_el_html_limpio_no_da_hallazgos(self) -> None:
        self.assertEqual(verificar_html(_HTML_LIMPIO), [])


class PruebaB0_11_CuatroMutaciones(PruebaBase):
    """Cada mutación debe disparar ROJO; el resto del documento se queda igual (limpio)."""

    def test_casilla_premarcada(self) -> None:
        mutado = _HTML_LIMPIO.replace('<input type="checkbox" name="acepto">', '<input type="checkbox" name="acepto" checked>')
        hallazgos = verificar_html(mutado)
        self.assertIn("html:casilla-premarcada", [h.patron_clave for h in hallazgos])
        self.assertEqual(peor_nivel(hallazgos), "rojo")

    def test_legal_ausente_una_de_siete(self) -> None:
        primera_clave = next(iter(LEGALES_REQUERIDAS))
        primer_enlace = f'<a data-legal="{primera_clave}" href="{LEGALES_REQUERIDAS[primera_clave]}">{primera_clave}</a>'
        mutado = _HTML_LIMPIO.replace(primer_enlace, "")
        hallazgos = verificar_html(mutado)
        self.assertIn(f"html:legal-ausente-{primera_clave}", [h.patron_clave for h in hallazgos])

    def test_enlace_roto(self) -> None:
        primera_clave = next(iter(LEGALES_REQUERIDAS))
        primer_enlace = f'<a data-legal="{primera_clave}" href="{LEGALES_REQUERIDAS[primera_clave]}">{primera_clave}</a>'
        mutado = _HTML_LIMPIO.replace(primer_enlace, f'<a data-legal="{primera_clave}" href="#">{primera_clave}</a>')
        hallazgos = verificar_html(mutado)
        self.assertIn(f"html:enlace-roto-{primera_clave}", [h.patron_clave for h in hallazgos])

    def test_pixel_en_head_sin_condicion(self) -> None:
        html = '<html><head><script src="https://connect.facebook.net/en_US/fbevents.js"></script></head><body></body></html>'
        hallazgos = verificar_html(html)
        claves = [h.patron_clave for h in hallazgos]
        self.assertIn("html:pixel-en-head-sin-condicion", claves)
        self.assertIn("html:pixel-antes-de-consentir", claves)

    def test_pixel_despues_del_consentimiento_fuera_del_head_no_dispara(self) -> None:
        html = f"""<html><head><title>Oferta</title></head><body>
{_LEGALES_OK}
<script src="consentimiento.js"></script>
{_PIXEL_GATEADO}
</body></html>"""
        hallazgos = verificar_html(html)
        self.assertEqual([h for h in hallazgos if h.categoria == "html" and "pixel" in h.patron_clave], [])


class PruebaTemporizadorYMetadatos(PruebaBase):
    def test_temporizador_sin_fecha_limite_es_rojo(self) -> None:
        html = '<html><body><div class="countdown">09:59</div></body></html>'
        hallazgos = verificar_html(html)
        self.assertIn("html:temporizador-sin-fecha-verificable", [h.patron_clave for h in hallazgos])

    def test_temporizador_con_fecha_limite_valida_no_dispara(self) -> None:
        html = '<html><body><div class="countdown" data-deadline="2026-12-01T00:00:00Z">09:59</div></body></html>'
        hallazgos = verificar_html(html)
        self.assertEqual([h for h in hallazgos if "temporizador" in h.patron_clave], [])

    def test_termino_sensible_en_title_y_og_es_rojo(self) -> None:
        reglas = cargar_reglas()
        html = (
            '<html><head><title>Cura la ansiedad en 7 dias</title>'
            '<meta property="og:title" content="Cura la ansiedad en 7 dias"></head><body></body></html>'
        )
        hallazgos = verificar_html(html, reglas=reglas, locale="es-ES", macro_nicho="salud")
        metadatos = [h for h in hallazgos if h.categoria == "metadatos"]
        self.assertTrue(metadatos)
        self.assertEqual(peor_nivel(metadatos), "rojo")

    def test_sin_reglas_no_revisa_metadatos(self) -> None:
        html = '<html><head><title>Cura la ansiedad en 7 dias</title></head><body></body></html>'
        hallazgos = verificar_html(html)  # sin reglas/locale: no se piden metadatos
        self.assertEqual([h for h in hallazgos if h.categoria == "metadatos"], [])


class PruebaEscasezFijaYPlantillaSinReemplazar(PruebaBase):
    """B6b (ola 2): L1-PUB (a) — «Quedan N cupos» fijo y texto de plantilla olvidado."""

    def test_quedan_n_cupos_sin_marcador_verificable_es_rojo(self) -> None:
        html = _HTML_LIMPIO.replace("10:00", "10:00 — Quedan 7 cupos")
        hallazgos = verificar_html(html)
        self.assertIn("html:escasez-fija-sin-verificar", [h.patron_clave for h in hallazgos])
        self.assertEqual(peor_nivel(hallazgos), "rojo")

    def test_quedan_n_cupos_con_marcador_verificable_no_dispara(self) -> None:
        html = _HTML_LIMPIO.replace(
            '<div class="countdown" data-deadline="2026-11-10T00:00:00Z">10:00</div>',
            '<div class="countdown" data-deadline="2026-11-10T00:00:00Z" data-cupos-verificable="true">'
            "Quedan 7 cupos</div>",
        )
        hallazgos = verificar_html(html)
        self.assertEqual([h for h in hallazgos if "escasez" in h.patron_clave], [])

    def test_ultimas_n_plazas_tambien_dispara(self) -> None:
        html = "<html><body>Últimas 3 plazas disponibles</body></html>"
        hallazgos = verificar_html(html)
        self.assertIn("html:escasez-fija-sin-verificar", [h.patron_clave for h in hallazgos])

    def test_texto_legitimo_sobre_cupos_sin_numero_no_dispara(self) -> None:
        html = "<html><body>Cupos limitados según demanda; el sitio muestra el cupo disponible en vivo</body></html>"
        hallazgos = verificar_html(html)
        self.assertEqual([h for h in hallazgos if "escasez" in h.patron_clave], [])

    def test_marcador_ejemplo_entre_corchetes_es_rojo(self) -> None:
        html = '<html><body><!-- [EJEMPLO] no publicar --><h1>Oferta</h1></body></html>'
        hallazgos = verificar_html(html)
        self.assertIn("html:plantilla-sin-reemplazar", [h.patron_clave for h in hallazgos])

    def test_marcador_todo_en_mayusculas_es_rojo(self) -> None:
        html = "<html><body><p>TODO: completar esta sección</p></body></html>"
        hallazgos = verificar_html(html)
        self.assertIn("html:plantilla-sin-reemplazar", [h.patron_clave for h in hallazgos])

    def test_marcador_lorem_es_rojo(self) -> None:
        html = "<html><body><p>Lorem ipsum dolor sit amet</p></body></html>"
        hallazgos = verificar_html(html)
        self.assertIn("html:plantilla-sin-reemplazar", [h.patron_clave for h in hallazgos])

    def test_palabra_todo_en_minusculas_no_dispara(self) -> None:
        """"todo" (minúscula) es una palabra común del español: no es un marcador de plantilla."""
        html = "<html><body><p>Incluye todo lo que necesitas para empezar hoy mismo</p></body></html>"
        hallazgos = verificar_html(html)
        self.assertEqual([h for h in hallazgos if "plantilla" in h.patron_clave], [])

    def test_palabra_ejemplo_en_minusculas_no_dispara(self) -> None:
        """"ejemplo" (minúscula) es una palabra común: solo "[EJEMPLO]"/"EJEMPLO" en mayúsculas es marcador."""
        html = "<html><body><p>Te doy un ejemplo de cómo organizar tu semana</p></body></html>"
        hallazgos = verificar_html(html)
        self.assertEqual([h for h in hallazgos if "plantilla" in h.patron_clave], [])


if __name__ == "__main__":
    import unittest

    unittest.main()
