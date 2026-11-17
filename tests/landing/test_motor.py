"""Pruebas de ``landing.motor``: escapado por defecto, mini-marcado seguro y plantillas estrictas.

Comando: ``.venv/bin/python -m unittest tests.landing.test_motor``
"""
from __future__ import annotations

import unittest

from landing import motor


class PruebaEscapado(unittest.TestCase):
    def test_md_escapa_todo_antes_de_reconocer_el_marcado(self) -> None:
        self.assertEqual("&lt;script&gt;alert(1)&lt;/script&gt;", motor.md("<script>alert(1)</script>"))
        self.assertEqual('&lt;img src=x onerror=&quot;a()&quot;&gt;', motor.md('<img src=x onerror="a()">'))

    def test_md_admite_negrita_y_enfasis(self) -> None:
        self.assertEqual("una <strong>negrita</strong> y un <em>énfasis</em>", motor.md("una **negrita** y un *énfasis*"))

    def test_md_no_admite_enlaces_ni_imagenes(self) -> None:
        self.assertEqual("[x](javascript:alert(1))", motor.md("[x](javascript:alert(1))"))
        self.assertNotIn("<a", motor.md("[x](https://externo.invalid)"))

    def test_md_deja_asteriscos_sueltos(self) -> None:
        self.assertEqual("2 * 3 * 4", motor.md("2 * 3 * 4"))

    def test_texto_plano_quita_marcas(self) -> None:
        self.assertEqual("a b c", motor.texto_plano("a **b** *c*"))

    def test_md_conserva_los_glifos_del_locale(self) -> None:
        self.assertEqual("łąęśćńóźż ¿ñ?", motor.md("łąęśćńóźż ¿ñ?"))


class PruebaPlantillas(unittest.TestCase):
    def test_variable_simple_escapa(self) -> None:
        self.assertEqual("&lt;b&gt;", motor.renderizar_texto("{{x}}", {"x": "<b>"}))

    def test_triple_llave_solo_inserta_seguro(self) -> None:
        self.assertEqual("&lt;b&gt;", motor.renderizar_texto("{{{x}}}", {"x": "<b>"}))
        self.assertEqual("<b>", motor.renderizar_texto("{{{x}}}", {"x": motor.Seguro("<b>")}))

    def test_doble_llave_reescapa_un_seguro_para_atributos(self) -> None:
        self.assertEqual("&lt;b&gt;", motor.renderizar_texto("{{x}}", {"x": motor.Seguro("<b>")}))

    def test_variable_inexistente_es_error(self) -> None:
        with self.assertRaises(motor.ErrorPlantilla):
            motor.renderizar_texto("{{falta}}", {})

    def test_si_con_variable_ausente_es_falso(self) -> None:
        self.assertEqual("n", motor.renderizar_texto("{{#si falta}}s{{sino}}n{{/si}}", {}))

    def test_cada_con_contadores(self) -> None:
        self.assertEqual("1:a 2:b ", motor.renderizar_texto("{{#cada l}}{{@n}}:{{.}} {{/cada}}", {"l": ["a", "b"]}))

    def test_cada_con_objetos_y_ambito_externo(self) -> None:
        r = motor.renderizar_texto("{{#cada l}}{{t.x}}-{{nombre}};{{/cada}}", {"t": {"x": "T"}, "l": [{"nombre": "a"}, {"nombre": "b"}]})
        self.assertEqual("T-a;T-b;", r)

    def test_bloque_sin_cerrar_es_error(self) -> None:
        with self.assertRaises(motor.ErrorPlantilla):
            motor.compilar("{{#si x}}abierto")

    def test_lineas_de_bloque_no_dejan_lineas_en_blanco(self) -> None:
        r = motor.renderizar_texto("a\n{{#si x}}\nb\n{{/si}}\nc\n", {"x": True})
        self.assertEqual("a\nb\nc\n", r)

    def test_es_determinista(self) -> None:
        ctx = {"l": ["a", "b"], "x": 1}
        a = motor.renderizar_texto("{{#cada l}}<{{.}}>{{/cada}}{{x}}", ctx)
        self.assertEqual(a, motor.renderizar_texto("{{#cada l}}<{{.}}>{{/cada}}{{x}}", ctx))


if __name__ == "__main__":
    unittest.main()
