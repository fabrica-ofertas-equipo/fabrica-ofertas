"""Pruebas de ``landing.generar``: construye un sitio determinista que ``landing.validar`` acepta.

Comando: ``.venv/bin/python -m unittest tests.landing.test_generar``
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import comun
from engine.errores import ErrorValidacion
from landing import generar as G
from landing import validar as Val

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "tests" / "fixtures" / "landing" / "oferta_minima"


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="landing-generar-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = self.tmp / "ofertas" / "OF-209901-01"
        shutil.copytree(FIXTURE, self.d)


class TestGenerarSitio(Base):
    def test_escribe_los_archivos_esperados(self) -> None:
        salida = G.generar_sitio(self.d)
        esperados = {
            "sitio/index.html", "sitio/a/angulo-secundario.html", "sitio/gracias.html",
            "sitio/css/estilos.css", "sitio/js/consentimiento.js", "sitio/js/pixel.js", "sitio/_headers",
            *(f"sitio/legal/{n}.html" for n in ("vendedor", "terminos", "privacidad", "reembolsos", "cookies", "aviso", "entrega")),
        }
        self.assertEqual(esperados, set(salida))
        for rel in esperados:
            self.assertTrue((self.d / "05-landing" / rel).is_file(), rel)
        self.assertTrue((self.d / "05-landing" / "rutas.json").is_file())
        self.assertTrue((self.d / "05-landing" / "imagenes" / "hero-placeholder.png").is_file())

    def test_rutas_json_generado_cubre_legales_y_angulos(self) -> None:
        G.generar_sitio(self.d)
        rutas = comun.cargar_json(self.d / "05-landing" / "rutas.json")
        self.assertEqual(rutas["/"], "angulo-principal")
        self.assertEqual(rutas["/a/angulo-secundario"], "angulo-secundario")
        self.assertEqual(rutas["/comprar"], "dinamica:crear-sesion")
        for n in ("vendedor", "terminos", "privacidad", "reembolsos", "cookies", "aviso", "entrega"):
            self.assertEqual(rutas[f"/legal/{n}"], f"legal:{n}")

    def test_es_determinista(self) -> None:
        a = G.generar_sitio(self.d)
        b = G.generar_sitio(self.d)
        self.assertEqual(a, b)

    def test_el_sitio_generado_pasa_landing_validar(self) -> None:
        G.generar_sitio(self.d)
        hallazgos = Val.validar_sitio(self.d)
        self.assertEqual([], hallazgos, [str(h) for h in hallazgos])

    def test_precio_moneda_garantia_consistentes_con_oferta_y_checkout(self) -> None:
        G.generar_sitio(self.d)
        html = (self.d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-precio-minor="2990"', html)
        self.assertIn('data-moneda="EUR"', html)
        self.assertIn('data-garantia-dias="14"', html)
        self.assertIn("29,90 €", html)
        self.assertIn("Garantía de 14 días", html)

    def test_sin_la_palabra_ejemplo_en_texto_visible(self) -> None:
        G.generar_sitio(self.d)
        for p in (self.d / "05-landing" / "sitio").rglob("*.html"):
            import re
            sin_comentarios = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.S)
            self.assertNotRegex(sin_comentarios, r"(?i)ejemplo", p.name)

    def test_unico_script_es_consentimiento(self) -> None:
        G.generar_sitio(self.d)
        import re
        for p in (self.d / "05-landing" / "sitio").rglob("*.html"):
            self.assertEqual(['src="/js/consentimiento.js"'], re.findall(r'<script[^>]*?(src="[^"]+")', p.read_text(encoding="utf-8")), p.name)

    def test_pixel_solo_lo_referencia_consentimiento_js(self) -> None:
        G.generar_sitio(self.d)
        import re
        sitio = self.d / "05-landing" / "sitio"
        referencias = [p.name for p in sitio.rglob("*") if p.is_file() and p.name != "pixel.js"
                      and p.suffix in (".html", ".js", ".css") and re.search(r"pixel\.js|fbevents|fbq\(", p.read_text(encoding="utf-8"))]
        self.assertEqual(["consentimiento.js"], referencias)

    def test_falla_si_falta_un_campo_obligatorio(self) -> None:
        oferta = json.loads((self.d / "03-oferta" / "oferta.json").read_text(encoding="utf-8"))
        del oferta["angulos"]
        (self.d / "03-oferta" / "oferta.json").write_text(json.dumps(oferta), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            G.generar_sitio(self.d)

    def test_no_genera_angulo_vacio_sin_ninguno(self) -> None:
        oferta = json.loads((self.d / "03-oferta" / "oferta.json").read_text(encoding="utf-8"))
        oferta["angulos"] = []
        (self.d / "03-oferta" / "oferta.json").write_text(json.dumps(oferta), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            G.generar_sitio(self.d)


class TestCLI(Base):
    def test_cli_json(self) -> None:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = G.main(["--oferta", "OF-209901-01", "--raiz", str(self.tmp), "--json"])
        self.assertEqual(0, codigo)
        salida = json.loads(buf.getvalue())
        self.assertTrue(salida["ok"])
        self.assertEqual(0, salida["codigo"])


if __name__ == "__main__":
    unittest.main()
