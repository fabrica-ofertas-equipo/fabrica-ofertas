"""Pruebas de ``landing.diseno``: paleta -> variables CSS con contraste AA verificado, fallo cerrado.

Comando: ``.venv/bin/python -m unittest tests.landing.test_diseno``
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from engine.errores import ErrorValidacion
from landing import diseno

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "landing"


def _paleta(nombre: str) -> dict:
    return json.loads((FIX / nombre / "05-landing" / "paleta.json").read_text(encoding="utf-8"))


class PruebaContraste(unittest.TestCase):
    def test_razon_conocida(self) -> None:
        self.assertAlmostEqual(21.0, diseno.razon_contraste("#000000", "#FFFFFF"), places=2)
        self.assertAlmostEqual(1.0, diseno.razon_contraste("#777777", "#777777"), places=2)

    def test_mezcla_entera_determinista(self) -> None:
        self.assertEqual("#808080", diseno.mezclar("#000000", "#FFFFFF", 50))
        self.assertEqual("#FFFFFF", diseno.mezclar("#123456", "#FFFFFF", 100))


class PruebaPaletas(unittest.TestCase):
    def test_las_dos_paletas_de_prueba_dan_variables_y_cumplen_aa(self) -> None:
        for nombre in ("oferta_es_dinero", "oferta_pl_relaciones"):
            with self.subTest(nombre):
                d = diseno.construir_diseno(_paleta(nombre))
                self.assertIn(".tono-claro{", d.css_tokens)
                self.assertIn(".tono-oscuro{", d.css_tokens)
                for tono in d.tonos.values():
                    for etiqueta, fg, bg, minimo in tono.pares():
                        self.assertGreaterEqual(diseno.razon_contraste(fg, bg) + 1e-9, minimo, (nombre, etiqueta))

    def test_es_determinista(self) -> None:
        a = diseno.construir_diseno(_paleta("oferta_es_dinero"))
        b = diseno.construir_diseno(_paleta("oferta_es_dinero"))
        self.assertEqual(a.css_tokens, b.css_tokens)

    def test_color_sin_declarar_se_deriva_con_aa(self) -> None:
        p = _paleta("oferta_es_dinero")
        for token in ("texto_suave_sobre_claro", "texto_suave_sobre_oscuro", "superficie_oscura", "acento_sobre_claro", "cta_hover"):
            p["colores"].pop(token)
        d = diseno.construir_diseno(p)
        self.assertGreaterEqual(diseno.razon_contraste(d.tonos["claro"].acento, d.tonos["claro"].fondo), 4.5)
        self.assertGreaterEqual(diseno.razon_contraste(d.tonos["oscuro"].suave, d.tonos["oscuro"].fondo), 4.5)

    def test_contraste_insuficiente_falla_cerrado(self) -> None:
        p = _paleta("oferta_es_dinero")
        p["colores"]["texto_sobre_claro"]["hex"] = "#B8C4C8"       # casi igual que el fondo claro
        with self.assertRaises(ErrorValidacion) as cm:
            diseno.construir_diseno(p)
        self.assertIn("contraste insuficiente", cm.exception.mensaje)

    def test_boton_ilegible_falla_cerrado(self) -> None:
        p = _paleta("oferta_pl_relaciones")
        p["colores"]["cta_texto"]["hex"] = "#2FB5A4"
        with self.assertRaises(ErrorValidacion):
            diseno.construir_diseno(p)

    def test_hex_invalido_falla_cerrado(self) -> None:
        p = _paleta("oferta_es_dinero")
        p["colores"]["acento"]["hex"] = "red; background:url(//x.invalid)"
        with self.assertRaises(ErrorValidacion):
            diseno.construir_diseno(p)

    def test_familia_tipografica_con_inyeccion_css_se_rechaza(self) -> None:
        p = copy.deepcopy(_paleta("oferta_es_dinero"))
        p["tipografia"]["titulos"]["familia"] = 'Lora"; } body{display:none'
        with self.assertRaises(ErrorValidacion):
            diseno.construir_diseno(p)

    def test_fuentes_ausentes_usan_pila_de_sistema_y_avisan(self) -> None:
        d = diseno.construir_diseno(_paleta("oferta_es_dinero"))
        self.assertEqual("", d.css_fuentes)
        self.assertTrue(any("pila de sistema" in a for a in d.avisos))
        self.assertNotIn("http", d.css_tokens)

    def test_fuentes_presentes_generan_font_face_local_sin_red(self) -> None:
        d = diseno.construir_diseno(_paleta("oferta_es_dinero"), existe_fuente=lambda a: True)
        self.assertIn("@font-face", d.css_fuentes)
        self.assertIn('url("/fonts/', d.css_fuentes)
        self.assertNotIn("//", d.css_fuentes.replace('url("/fonts/', ""))

    def test_pila_serif_para_familias_conocidas(self) -> None:
        d = diseno.construir_diseno(_paleta("oferta_es_dinero"))
        self.assertIn("Georgia", d.css_tokens)


if __name__ == "__main__":
    unittest.main()
