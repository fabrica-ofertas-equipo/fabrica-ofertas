"""``ofertas/_ejemplo`` regenerada y re-sellada (ola 0b-2, CT): landing con siete páginas legales, banner de consentimiento y píxel condicionado.

Comando: ``.venv/bin/python -m unittest tests.contratos.test_ejemplo_landing``
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from engine import factibilidad
from scripts import validar_esquemas as V
from tests.contratos import lint_landing_referencia as L
from tests.contratos import regenerar_ejemplo as R

RAIZ = Path(__file__).resolve().parents[2]
EJ = RAIZ / "ofertas" / "_ejemplo"
SITIO = EJ / "05-landing" / "sitio"
LEGALES = ("vendedor", "terminos", "privacidad", "reembolsos", "cookies", "aviso", "entrega")


def j(rel: str):
    return V.cargar_json(EJ / rel)


class TestSietePaginasLegales(unittest.TestCase):
    def test_existen_las_siete_y_ya_no_la_vieja(self) -> None:
        for n in LEGALES:
            self.assertTrue((SITIO / "legal" / f"{n}.html").is_file(), n)
        self.assertEqual(sorted(f"{n}.html" for n in LEGALES), sorted(p.name for p in (SITIO / "legal").glob("*.html")))

    def test_rutas_json_trae_las_siete_rutas_y_cada_estatica_tiene_archivo(self) -> None:
        rutas = j("05-landing/rutas.json")
        for n in LEGALES:
            self.assertIn(f"/legal/{n}", rutas)
        for ruta, destino in rutas.items():
            if not destino.startswith("dinamica:"):
                self.assertTrue(L._archivo_de_ruta(SITIO, ruta).is_file(), ruta)
        angulos = {a["angulo_id"] for a in j("03-oferta/oferta.json")["angulos"]}
        self.assertTrue(angulos <= set(rutas.values()))            # cada ángulo de la oferta tiene su ruta

    def test_cada_pagina_lleva_lang_correcto_y_la_marca_solo_en_comentario(self) -> None:
        locale = j("03-oferta/oferta.json")["locale"]
        paginas = sorted(SITIO.rglob("*.html"))
        self.assertGreaterEqual(len(paginas), 11)
        for p in paginas:
            html = p.read_text(encoding="utf-8")
            self.assertIn(f'<html lang="{locale}">', html, p.name)
            self.assertIn("<!-- [EJEMPLO]", html, p.name)
            sin_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.S)
            self.assertIsNone(re.search(r"ejemplo", sin_comentarios, re.I), p.name)    # ni visible ni en atributos

    def test_enlaces_del_pie_cubren_las_siete(self) -> None:
        for p in (SITIO / "index.html", SITIO / "gracias.html", SITIO / "legal" / "cookies.html"):
            html = p.read_text(encoding="utf-8")
            for n in LEGALES:
                self.assertIn(f'href="/legal/{n}"', html, (p.name, n))


class TestConsentimiento(unittest.TestCase):
    def setUp(self) -> None:
        self.cons = (SITIO / "js" / "consentimiento.js").read_text(encoding="utf-8")
        self.pix = (SITIO / "js" / "pixel.js").read_text(encoding="utf-8")

    def test_banner_con_tres_botones_todo_apagado_cookie_propia_y_version(self) -> None:
        for texto in ("Aceptar", "Rechazar", "Personalizar", "version_texto: 'v1'", "fabrica_consent", "casilla.checked = false", "SameSite=Lax"):
            self.assertIn(texto, self.cons)
        self.assertIn("fc-aceptar", self.cons)
        self.assertEqual(3, self.cons.count("'class': 'fc-btn'") - 1)      # tres botones del banner + «Guardar elección» comparten la clase
        css = (SITIO / "css" / "estilos.css").read_text(encoding="utf-8")
        self.assertEqual(1, css.count(".fc-btn {"))                        # una sola regla: mismo peso visual para los tres

    def test_solo_consentimiento_js_lleva_al_pixel(self) -> None:
        referencias = [p.relative_to(SITIO).as_posix() for p in SITIO.rglob("*") if p.is_file() and p.name != "pixel.js"
                       and re.search(r"pixel\.js|fbevents|connect\.facebook\.net|fbq\(", p.read_text(encoding="utf-8") if p.suffix in (".html", ".js", ".css") else "")]
        self.assertEqual(["js/consentimiento.js"], referencias)
        self.assertIn("function cargarPixel()", self.cons)
        cuerpo = self.cons.split("function cargarPixel()")[1][:200]
        self.assertIn("estado.marketing", cuerpo)
        self.assertIn("window.FabricaConsent.marketing() !== true", self.pix)
        self.assertIn(j("05-landing/tracking.json")["pixel_id"], self.pix)

    def test_ningun_html_carga_otro_script_que_el_banner(self) -> None:
        for p in SITIO.rglob("*.html"):
            self.assertEqual(['src="/js/consentimiento.js"'], re.findall(r'<script[^>]*?(src="[^"]+")', p.read_text(encoding="utf-8")), p.name)

    def test_tracking_declara_banner_propio_v1(self) -> None:
        self.assertEqual("banner_propio_v1", j("05-landing/tracking.json")["consent_gating"]["plataforma"])

    def test_sintaxis_javascript(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node no disponible")
        for archivo in (SITIO / "js" / "consentimiento.js", SITIO / "js" / "pixel.js"):
            r = subprocess.run([node, "--check", str(archivo)], capture_output=True, text=True)
            self.assertEqual(0, r.returncode, r.stderr)


class TestCoherenciaDeLaOferta(unittest.TestCase):
    def test_precio_moneda_y_garantia_identicos_en_oferta_economia_checkout_y_html(self) -> None:
        o, e, c = j("03-oferta/oferta.json"), j("03-oferta/economia.json"), j("05-landing/checkout.json")
        self.assertEqual(o["precio"]["lista"], e["entradas_usadas"]["precio"])
        self.assertEqual(o["precio"]["lista"], c["precio"])
        self.assertEqual(o["moneda"], c["moneda"])
        self.assertEqual(o["garantia"]["dias"], c["garantia_dias"])
        html = (SITIO / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'data-precio-minor="{o["precio"]["lista"]["monto"]}"', html)
        self.assertIn(R.eur(o["precio"]["lista"]["monto"]), html)
        self.assertIn(f'data-garantia-dias="{o["garantia"]["dias"]}"', html)
        self.assertIn(o["garantia"]["texto_visible"], html)

    def test_dinero_y_nicho(self) -> None:
        o = j("03-oferta/oferta.json")
        self.assertEqual(("dinero", "es-ES", "EUR"), (o["macro_nicho"], o["locale"], o["moneda"]))
        sitio = " ".join(p.read_text(encoding="utf-8") for p in SITIO.rglob("*.html"))
        self.assertEqual([], V._terminos_sensibles(re.sub(r"<!--.*?-->", "", sitio, flags=re.S).split("<title>")[1].split("</title>")[0]))

    def test_sin_datos_personales_ni_correo_literal_en_la_landing(self) -> None:
        for p in SITIO.rglob("*"):
            if p.is_file():
                self.assertIsNone(re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", p.read_text(encoding="utf-8")), p.name)

    def test_sin_contadores_ni_cupos(self) -> None:
        self.assertEqual([], [x for x in L.lint(EJ) if x.regla == "L1-CONTADORES"])


class TestLintDePublicacionDeReferencia(unittest.TestCase):
    def test_el_ejemplo_pasa_limpio(self) -> None:
        self.assertEqual([], L.lint(EJ))

    def test_en_produccion_el_comentario_de_ejemplo_se_rechaza(self) -> None:
        r = L.lint(EJ, produccion=True)
        self.assertEqual({"L1-EJEMPLO-COMENTARIO"}, L.reglas(r))
        self.assertGreaterEqual(len(r), 11)


class TestReselladoYRegeneracion(unittest.TestCase):
    def test_validar_oferta_pasa_con_firmas_de_prueba(self) -> None:
        inf = V.validar_oferta(EJ, limites=V.limites_de_prueba(), autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"), clave_firma=V.CLAVE_DE_PRUEBA)
        self.assertEqual([], [str(h) for h in inf.hallazgos])

    def test_regenerar_es_idempotente_sobre_el_repositorio(self) -> None:
        self.assertEqual([], R.regenerar(EJ, solo_comprobar=True))

    def test_regenerar_desde_cero_reproduce_los_mismos_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            copia = Path(t) / "OF-202611-01"
            shutil.copytree(EJ, copia)
            shutil.rmtree(copia / "05-landing" / "sitio" / "legal")
            shutil.rmtree(copia / "05-landing" / "sitio" / "a")
            (copia / "05-landing" / "sitio" / "index.html").unlink()
            R.regenerar(copia)
            self.assertEqual(V.hash_directorio(SITIO), V.hash_directorio(copia / "05-landing" / "sitio"))
            self.assertEqual(j("estado.json"), V.cargar_json(copia / "estado.json"))
            self.assertEqual([], R.regenerar(copia, solo_comprobar=True))

    def test_hashes_dependientes_resellados(self) -> None:
        est = j("estado.json")
        for etapa, e in est["etapas"].items():
            if e["hash_salida"]:
                self.assertEqual(V.hash_salida_etapa(EJ, etapa), e["hash_salida"], etapa)
        paq = j("06-creativos/paquete.json")
        self.assertEqual(V.hash_directorio(SITIO), paq["destino"]["landing_hash"])
        for q in sorted((EJ / "qa").glob("*.json")):
            d = V.cargar_json(q)
            self.assertEqual(V.hash_ruta(EJ / d["artefacto_ref"]), d["artefacto_sha256"], q.name)
            if d["etapa"] == "X1":
                self.assertEqual(V.firma_hmac({k: v for k, v in d.items() if k != "firma_motor"}, V.CLAVE_DE_PRUEBA), d["firma_motor"], q.name)
        d5 = j("qa/d5-v1.json")
        self.assertEqual(V.hash_directorio(SITIO), d5["artefacto_sha256"])
        self.assertEqual(d5["artefacto_sha256"], j("qa/x1-d5-v1.json")["artefacto_sha256"])

    def test_economia_del_ejemplo_sale_de_factibilidad(self) -> None:
        eco = j("03-oferta/economia.json")
        self.assertEqual(eco, factibilidad.documento_economia({**eco["entradas_usadas"], "gasto_diario": 2760, "oferta_id": eco["oferta_id"]},
                                                              V.cargar_yaml(RAIZ / "empresa" / "parametros.yaml"), V.limites_de_prueba()))
        self.assertEqual(1830, eco["mc"]["monto"])
        self.assertEqual(factibilidad.VERSION, eco["script_version"])
        camp = j("07-campana/campana.json")
        self.assertEqual((eco["cpa_be"]["monto"], eco["cpa_obj"]["monto"]), (camp["economia"]["cpa_equilibrio"], camp["economia"]["cpa_objetivo"]))

    def test_ejemplos_de_contratos_sincronizados(self) -> None:
        for esquema, rel in R.COPIAS_EN_EJEMPLOS.items():
            self.assertEqual(j(rel), V.cargar_json(V.DIR_EJEMPLOS / f"{esquema}.valido.json"), esquema)

    def test_firmas_son_de_prueba(self) -> None:
        for p in EJ.rglob("*.json"):
            self.assertNotIn("BEGIN OPENSSH", p.read_text(encoding="utf-8"), p.name)
        est = (EJ / "estado.json").read_text(encoding="utf-8")
        self.assertNotIn("ed25519", est.lower())
        self.assertIn("hmac-sha256:", est)


if __name__ == "__main__":
    unittest.main()
