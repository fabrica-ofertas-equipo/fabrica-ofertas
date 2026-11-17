"""``landing.generar`` en modo diseñado: dos ofertas de nicho y locale distintos (es-ES dinero, pl-PL relaciones).

Cada una debe generar el plano de 14 secciones, pasar ``landing.validar`` con 0 hallazgos y pasar el oráculo de CT
(``tests/contratos/lint_landing_referencia.py``). Casos hostiles: el generador falla cerrado (código 3).
Sin red: ``socket.socket`` se bloquea en ``setUp``.

Comando: ``.venv/bin/python -m unittest tests.landing.test_generar_disenado``
"""
from __future__ import annotations

import io
import json
import re
import shutil
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from engine.errores import ErrorValidacion
from landing import generar as G
from landing import validar as Val
from scripts import validar_esquemas as V
from tests.contratos import lint_landing_referencia as Oraculo

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "landing"
OFERTAS = {"es": ("oferta_es_dinero", "OF-202611-01", "es-ES"), "pl": ("oferta_pl_relaciones", "OF-202611-02", "pl-PL")}
LEGALES = ("vendedor", "terminos", "privacidad", "reembolsos", "cookies", "aviso", "entrega")
# Choque CONOCIDO con el oráculo vigente de CT (S-A lo corrige): su L1-FORMULARIO prohíbe todo <form>, también el único de /comprar.
CHOQUES_ORACULO = {("L1-FORMULARIO", "05-landing/sitio/comprar.html")}


def lint_oraculo(d, **k):
    """Hallazgos del oráculo SIN el choque conocido (el resto de reglas se exige igual)."""
    return [h for h in Oraculo.lint(d, **k) if (h.regla, h.archivo) not in CHOQUES_ORACULO]


ANCLAS_DEL_PLANO = ("inicio", "resumen", "problema", "muestra", "metodo", "incluye", "para-quien", "confianza", "extras", "garantia", "oferta", "preguntas", "cierre")


def _sin_red(*_a, **_k):  # pragma: no cover - solo se ejecuta si algo intenta abrir un socket
    raise AssertionError("las pruebas de landing no abren sockets")


class Base(unittest.TestCase):
    clave = "es"

    def setUp(self) -> None:
        patcher = mock.patch.object(socket, "socket", _sin_red)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="landing-disenado-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = self.preparar(self.tmp, self.clave)
        self.land = self.d / "05-landing"
        self.sitio = self.land / "sitio"

    @staticmethod
    def preparar(raiz: Path, clave: str) -> Path:
        carpeta, oid, _ = OFERTAS[clave]
        d = raiz / "ofertas" / oid
        shutil.copytree(FIX / carpeta, d)
        shutil.copytree(FIX / "empresa", raiz / "empresa", dirs_exist_ok=True)
        return d

    def leer(self, rel: str) -> str:
        return (self.sitio / rel).read_text(encoding="utf-8")

    def editar_json(self, rel: str, f) -> None:
        ruta = self.d / rel
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        f(datos)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


class PruebaDosOfertas(Base):
    """Se ejecuta una vez por oferta (``es`` y ``pl``)."""

    def para_cada_oferta(self, comprobar) -> None:
        for clave in OFERTAS:
            with self.subTest(clave):
                with tempfile.TemporaryDirectory(prefix="landing-dos-") as t:
                    d = self.preparar(Path(t), clave)
                    salida, avisos = G.generar_sitio_con_avisos(d)
                    comprobar(clave, d, salida, avisos)

    def test_genera_valida_y_pasa_el_oraculo(self) -> None:
        def c(clave, d, salida, avisos):
            hallazgos = Val.validar_sitio(d)
            self.assertEqual([], [str(h) for h in hallazgos])
            self.assertEqual([], [(h.regla, h.archivo, h.detalle) for h in lint_oraculo(d)])
            self.assertEqual([], [(h.regla, h.archivo) for h in lint_oraculo(d, produccion=True)])
        self.para_cada_oferta(c)

    def test_el_plano_trae_las_14_secciones_en_orden(self) -> None:
        def c(clave, d, salida, avisos):
            html = (d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
            ids = re.findall(r'<section class="seccion[^"]*"[^>]* id="([a-z-]+)"', html) or re.findall(r'id="([a-z-]+)" aria-labelledby', html)
            self.assertEqual(list(ANCLAS_DEL_PLANO), ids, clave)
            self.assertIn('<footer class="pie', html)         # S14
            self.assertEqual(1, html.count("<h1"))
        self.para_cada_oferta(c)

    def test_html_lang_y_textos_en_el_locale(self) -> None:
        def c(clave, d, salida, avisos):
            locale = OFERTAS[clave][2]
            for p in (d / "05-landing" / "sitio").rglob("*.html"):
                self.assertIn(f'<html lang="{locale}">', p.read_text(encoding="utf-8"), p.name)
        self.para_cada_oferta(c)

    def test_titulo_y_faq_salen_del_copy_no_del_hook(self) -> None:
        def c(clave, d, salida, avisos):
            copy = json.loads((d / "05-landing" / "copy.json").read_text(encoding="utf-8"))
            html = (d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
            oferta = json.loads((d / "03-oferta" / "oferta.json").read_text(encoding="utf-8"))
            titulo = re.search(r"<title>(.*?)</title>", html).group(1)
            esperado = copy["meta"]["title"].replace("{marca}", oferta["marca"]["nombre"]).replace("{producto}", oferta["promesa"]["titulo"])
            self.assertEqual(esperado, titulo)
            self.assertEqual(len(copy["secciones"]["S12"]["preguntas"]), html.count('<details class="faq__item"'))
            self.assertNotIn("Respuesta honesta: no se garantiza", html)
        self.para_cada_oferta(c)

    def test_precio_moneda_garantia_vienen_del_contrato(self) -> None:
        def c(clave, d, salida, avisos):
            html = (d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
            checkout = json.loads((d / "05-landing" / "checkout.json").read_text(encoding="utf-8"))
            self.assertIn(f'data-precio-minor="{checkout["precio"]["monto"]}"', html)
            self.assertIn(f'data-moneda="{checkout["moneda"]}"', html)
            self.assertIn('data-decimales="2"', html)
            self.assertIn(f'data-garantia-dias="{checkout["garantia_dias"]}"', html)
            self.assertNotIn("{", html.split("<body")[1])    # ningún placeholder sin expandir
        self.para_cada_oferta(c)

    def test_importe_con_formato_del_locale(self) -> None:
        def c(clave, d, salida, avisos):
            html = (d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
            self.assertIn("19,90 €" if clave == "es" else "39,00 zł", html)
        self.para_cada_oferta(c)

    def test_unico_script_es_consentimiento_y_no_hay_estilos_en_linea(self) -> None:
        def c(clave, d, salida, avisos):
            for p in (d / "05-landing" / "sitio").rglob("*.html"):
                t = p.read_text(encoding="utf-8")
                self.assertEqual(['src="/js/consentimiento.js"'], re.findall(r'<script[^>]*?(src="[^"]+")', t), p.name)
                self.assertNotIn("<style", t)
                self.assertNotIn(' style="', t)
                self.assertNotRegex(t, r"\son[a-z]+=", p.name)
                self.assertNotRegex(t, r"https?://(?!" + re.escape(json.loads((d / "03-oferta" / "oferta.json").read_text())["marca"]["dominio"]) + ")", p.name)
        self.para_cada_oferta(c)

    def test_imagenes_con_dimensiones_alt_y_carga(self) -> None:
        def c(clave, d, salida, avisos):
            for p in (d / "05-landing" / "sitio").rglob("*.html"):
                for img in re.findall(r"<img[^>]+>", p.read_text(encoding="utf-8")):
                    self.assertRegex(img, r'width="\d+"')
                    self.assertRegex(img, r'height="\d+"')
                    self.assertRegex(img, r'alt="[^"]+"')
                    self.assertTrue("loading=\"lazy\"" in img or "fetchpriority=\"high\"" in img, img)
        self.para_cada_oferta(c)

    def test_las_imagenes_aprobadas_se_copian_a_sitio(self) -> None:
        def c(clave, d, salida, avisos):
            assets = json.loads((d / "05-landing" / "assets.json").read_text(encoding="utf-8"))
            aprobadas = [s for s in assets["slots"] if s["estado"] == "aprobado"]
            self.assertTrue(aprobadas)
            for s in aprobadas:
                copia = d / "05-landing" / "sitio" / s["archivo"]
                self.assertTrue(copia.is_file(), s["archivo"])
                self.assertEqual((d / "05-landing" / s["archivo"]).read_bytes(), copia.read_bytes())
        self.para_cada_oferta(c)

    def test_ranura_sin_aprobar_no_genera_img_y_el_hero_usa_la_portada(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = self.preparar(Path(t), "pl")                     # el hero de pl no está aprobado
            G.generar_sitio(d)
            html = (d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="portada"', html)
            self.assertNotIn('class="hero__img"', html)

    def test_es_determinista_byte_a_byte(self) -> None:
        for clave in OFERTAS:
            with self.subTest(clave), tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
                da, db = self.preparar(Path(a), clave), self.preparar(Path(b), clave)
                G.generar_sitio(da)
                G.generar_sitio(db)
                G.generar_sitio(da)                              # reescribir no cambia nada
                archivos = sorted(p.relative_to(da / "05-landing" / "sitio") for p in (da / "05-landing" / "sitio").rglob("*") if p.is_file())
                self.assertEqual(archivos, sorted(p.relative_to(db / "05-landing" / "sitio") for p in (db / "05-landing" / "sitio").rglob("*") if p.is_file()))
                for rel in archivos:
                    self.assertEqual((da / "05-landing" / "sitio" / rel).read_bytes(), (db / "05-landing" / "sitio" / rel).read_bytes(), str(rel))
                self.assertEqual(V.hash_directorio(da / "05-landing" / "sitio"), V.hash_directorio(db / "05-landing" / "sitio"))

    def test_banner_en_el_idioma_y_misma_estructura(self) -> None:
        textos = {}
        for clave in OFERTAS:
            with tempfile.TemporaryDirectory() as t:
                d = self.preparar(Path(t), clave)
                G.generar_sitio(d)
                js = (d / "05-landing" / "sitio" / "js" / "consentimiento.js").read_text(encoding="utf-8")
                textos[clave] = js
                for ident in ("fc-aceptar", "fc-rechazar", "fc-personalizar"):
                    self.assertIn(ident, js)
                self.assertIn(".checked = false", js)
        copy_pl = json.loads((FIX / "oferta_pl_relaciones" / "05-landing" / "copy.json").read_text(encoding="utf-8"))
        self.assertIn(copy_pl["secciones"]["banner"]["aceptar"], textos["pl"])
        self.assertNotIn("Akceptuję", textos["es"])
        quitar = lambda js: re.sub(r"var TEXTO = \{.*?\n  \};", "", js, flags=re.S).replace("/* consentimiento.js", "").replace("'v1'", "")
        self.assertEqual(quitar(textos["es"]), quitar(textos["pl"]))   # K03: idéntica salvo los textos

    def test_pixel_solo_emite_eventos_declarados(self) -> None:
        def c(clave, d, salida, avisos):
            js = (d / "05-landing" / "sitio" / "js" / "pixel.js").read_text(encoding="utf-8")
            tracking = json.loads((d / "05-landing" / "tracking.json").read_text(encoding="utf-8"))
            self.assertIn(tracking["pixel_id"], js)
            self.assertEqual({"PageView", "ViewContent"}, set(re.findall(r"fbq\('track', '(\w+)'", js)))
        self.para_cada_oferta(c)

    def test_legales_en_el_idioma_y_siete_enlaces_en_el_pie(self) -> None:
        def c(clave, d, salida, avisos):
            html = (d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
            for n in LEGALES:
                self.assertIn(f'href="/legal/{n}"', html)
                self.assertTrue((d / "05-landing" / "sitio" / "legal" / f"{n}.html").is_file())
            self.assertIn('href="/desistimiento"', html)
            self.assertIn("Regulamin" if clave == "pl" else "Términos de uso", (d / "05-landing" / "sitio" / "legal" / "terminos.html").read_text(encoding="utf-8"))
        self.para_cada_oferta(c)

    def test_desistimiento_solo_si_la_ruta_existe(self) -> None:
        self.editar_json("05-landing/rutas.json", lambda r: r.pop("/desistimiento"))
        G.generar_sitio(self.d)
        self.assertFalse((self.sitio / "desistimiento.html").exists())
        self.assertNotIn("/desistimiento", self.leer("index.html"))

    def test_aviso_de_seguridad_y_ayuda_en_relaciones_conflicto(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = self.preparar(Path(t), "pl")
            G.generar_sitio(d)
            pie = (d / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")
            self.assertIn("aviso--seguridad", pie)
            self.assertIn("Jeśli obawiasz się o swoje bezpieczeństwo", pie)
            self.assertEqual(1, pie.count("służbą pomocy"))       # la ayuda no se duplica en el pie

    def test_variante_por_angulo_solo_cambia_los_cuatro_bloques(self) -> None:
        G.generar_sitio(self.d)
        base, otra = self.leer("index.html"), self.leer("a/pregunta-de-entrevista.html")
        self.assertIn("La pregunta sobre la pausa, con la respuesta ya escrita", otra)
        self.assertNotIn("La pregunta sobre la pausa, con la respuesta ya escrita", base)
        copy = json.loads((self.land / "copy.json").read_text(encoding="utf-8"))
        primero = copy["variantes_por_angulo"]["pregunta-de-entrevista"]["S12"]["primero"]
        self.assertRegex(otra, r'<details class="faq__item" id="' + primero)
        sin_h1 = lambda h: re.sub(r"<(title|h1).*?</\1>", "", h, flags=re.S)
        diferencia = [t for t in re.split(r"(?=<section)", sin_h1(base)) if t not in sin_h1(otra)]
        self.assertLessEqual(len(diferencia), 3)                  # hero, y como mucho S12 (orden) y S03


class PruebaOmisionLimpia(Base):
    def test_secciones_opcionales_sin_material_se_omiten_y_pasa_todo(self) -> None:
        def quitar(copy):
            for s in ("S02", "S04", "S08", "S09", "S13"):
                copy["secciones"].pop(s)
            copy["omitidas"] = [{"seccion": s, "motivo": "sin material real"} for s in ("S02", "S04", "S08", "S09", "S13")]
        self.editar_json("05-landing/copy.json", quitar)
        G.generar_sitio(self.d)
        html = self.leer("index.html")
        for ancla in ("resumen", "muestra", "confianza", "extras", "cierre"):
            self.assertNotIn(f'id="{ancla}"', html)
        self.assertEqual([], Val.validar_sitio(self.d))
        self.assertEqual([], [(h.regla, h.archivo) for h in lint_oraculo(self.d)])

    def test_s04_sin_captura_aprobada_se_omite_con_aviso(self) -> None:
        def sin_aprobar(a):
            for s in a["slots"]:
                if s["seccion"] == "galeria":
                    s.update(estado="omitida", archivo=None, sha256=None, origen=None)
        self.editar_json("05-landing/assets.json", sin_aprobar)
        _, avisos = G.generar_sitio_con_avisos(self.d)
        self.assertNotIn('id="muestra"', self.leer("index.html"))
        self.assertTrue(any("S04 omitida" in a for a in avisos))

    def test_cifra_literal_sin_traza_se_descarta(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c.update(cifras_con_traza=[]))
        _, avisos = G.generar_sitio_con_avisos(self.d)
        self.assertTrue(any("sin traza" in a for a in avisos))
        self.assertNotIn(">30<", self.leer("index.html"))

    def test_bonos_sin_archivo_en_el_producto_se_omiten(self) -> None:
        def f(c):
            c["secciones"]["S09"]["bonos"] = [{"nombre": "Bono sin archivo", "texto": "No existe en el producto", "archivo_ref": "no-existe"}]
            c["secciones"]["S09"]["bump"] = None
        self.editar_json("05-landing/copy.json", f)
        _, avisos = G.generar_sitio_con_avisos(self.d)
        self.assertNotIn('id="extras"', self.leer("index.html"))
        self.assertTrue(any("S09" in a for a in avisos))

    def test_si_se_omite_una_oscura_no_quedan_dos_oscuras_seguidas(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c["secciones"].pop("S04"))
        G.generar_sitio(self.d)
        tonos = re.findall(r'<section class="seccion[^"]*?tono-(\w+)', self.leer("index.html"))
        self.assertTrue(all(a != b for a, b in zip(tonos, tonos[1:])), tonos)


class PruebaFalloCerrado(Base):
    def assert_falla(self, fragmento: str) -> None:
        with self.assertRaises(ErrorValidacion) as cm:
            G.generar_sitio(self.d)
        self.assertIn(fragmento, cm.exception.mensaje)
        self.assertEqual(3, cm.exception.codigo_salida)

    def poner(self, ruta_copy: tuple, valor: str) -> None:
        def f(c):
            nodo = c
            for k in ruta_copy[:-1]:
                nodo = nodo[k]
            nodo[ruta_copy[-1]] = valor
        self.editar_json("05-landing/copy.json", f)

    def test_html_y_script_en_el_copy(self) -> None:
        self.poner(("secciones", "S01", "subtitulo"), "Hola <script>alert(1)</script>")
        self.assert_falla("marcado HTML")

    def test_etiqueta_de_imagen_con_manejador(self) -> None:
        self.poner(("secciones", "S03", "titulo"), '<img src=x onerror="a()">')
        self.assert_falla("marcado HTML")

    def test_u202e_en_el_copy(self) -> None:
        self.poner(("secciones", "S01", "h1"), "Titular ‮soñalumrof")
        self.assert_falla("U+202E")

    def test_otros_caracteres_de_control_y_ancho_cero(self) -> None:
        self.poner(("secciones", "S01", "kicker"), "Guía​ digital")
        self.assert_falla("U+200B")

    def test_enlace_javascript_en_el_copy(self) -> None:
        self.poner(("secciones", "S10", "nota_legal"), "Más en JavaScript:alert(1)")
        self.assert_falla("esquema activo")

    def test_u202e_en_el_alt_de_una_imagen(self) -> None:
        def f(a):
            for s in a["slots"]:
                if s["slot_id"] == "hero":
                    s["alt"] = "Portada ‮gnp"
        self.editar_json("05-landing/assets.json", f)
        self.assert_falla("U+202E")

    def test_imagen_aprobada_sin_alt(self) -> None:
        def f(a):
            for s in a["slots"]:
                if s["slot_id"] == "hero":
                    s["alt"] = ""
        self.editar_json("05-landing/assets.json", f)
        self.assert_falla("assets.json no cumple su esquema")

    def test_imagen_sin_clave_alt(self) -> None:
        def f(a):
            for s in a["slots"]:
                if s["slot_id"] == "hero":
                    del s["alt"]
        self.editar_json("05-landing/assets.json", f)
        self.assert_falla("assets.json no cumple su esquema")

    def test_falta_una_seccion_obligatoria(self) -> None:
        for sec in ("S01", "S03", "S05", "S06", "S07", "S10", "S11", "S12", "S14"):
            with self.subTest(sec):
                with tempfile.TemporaryDirectory() as t:
                    d = self.preparar(Path(t), "es")
                    ruta = d / "05-landing" / "copy.json"
                    copy = json.loads(ruta.read_text(encoding="utf-8"))
                    del copy["secciones"][sec]
                    ruta.write_text(json.dumps(copy, ensure_ascii=False), encoding="utf-8")
                    with self.assertRaises(ErrorValidacion) as cm:
                        G.generar_sitio(d)
                    self.assertIn("copy.json no cumple su esquema", cm.exception.mensaje)

    def test_paleta_con_contraste_insuficiente(self) -> None:
        self.editar_json("05-landing/paleta.json", lambda p: p["colores"]["texto_sobre_oscuro"].update(hex="#2A5663"))
        self.assert_falla("contraste")
        self.assertFalse(self.sitio.exists() and (self.sitio / "index.html").exists())   # no escribió nada a medias

    def test_paleta_que_reutiliza_la_base_falla(self) -> None:
        self.editar_json("05-landing/paleta.json", lambda p: p["colores"]["acento"].update(hex="#B86F4B"))
        self.assert_falla("D5-PALETA-BASE")

    def test_placeholder_desconocido(self) -> None:
        self.poner(("secciones", "S01", "microcopy"), "Garantía {dias_magicos}")
        self.assert_falla("placeholder desconocido")

    def test_placeholder_sin_fuente(self) -> None:
        ruta = self.d / "04-producto" / "producto.json"
        ruta.unlink()
        self.assert_falla("producto")

    def test_llaves_sueltas_sin_resolver(self) -> None:
        self.poner(("secciones", "S01", "microcopy"), "Texto con {{ llaves }}")
        with self.assertRaises(ErrorValidacion):
            G.generar_sitio(self.d)

    def test_locale_del_copy_distinto_del_de_la_oferta(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c.update(locale="it-IT"))
        self.assert_falla("locale")

    def test_oferta_id_distinto(self) -> None:
        self.editar_json("05-landing/paleta.json", lambda p: p.update(oferta_id="OF-209912-09"))
        self.assert_falla("oferta_id")

    def test_resena_sin_testimonio_con_permiso(self) -> None:
        def f(c):
            c["secciones"]["S08"].update(modo="real", resenas=[{"compra_id": "cs_inventada", "texto": "Me encantó"}])
        self.editar_json("05-landing/copy.json", f)
        self.assert_falla("testimonio con permiso")

    def test_resena_con_permiso_se_publica_con_su_fuente(self) -> None:
        def f(c):
            c["secciones"]["S08"].update(modo="real", resenas=[{"compra_id": "cs_real_1", "texto": "Me resultó claro."}])
        self.editar_json("05-landing/copy.json", f)
        self.editar_json("03-oferta/oferta.json", lambda o: o["prueba"].append({"tipo": "testimonio_con_permiso", "fuente": "cs_real_1", "consentimiento_ref": "consent-1"}))
        G.generar_sitio(self.d)
        self.assertIn('data-fuente="cs_real_1"', self.leer("index.html"))
        self.assertEqual([], [(h.regla) for h in lint_oraculo(self.d)])

    def test_bump_sin_oferta_bump(self) -> None:
        self.editar_json("03-oferta/oferta.json", lambda o: o.update(bump=None))
        with self.assertRaises(ErrorValidacion):
            G.generar_sitio(self.d)

    def test_garantia_distinta_entre_checkout_y_oferta(self) -> None:
        self.editar_json("05-landing/checkout.json", lambda c: c.update(garantia_dias=30))
        self.assert_falla("garantia_dias")

    def test_svg_con_contenido_activo(self) -> None:
        ruta = self.land / "imagenes" / "hero.svg"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace("</svg>", "<script>alert(1)</script></svg>"), encoding="utf-8")
        h = V.hash_archivo(ruta, servido=False)
        self.editar_json("05-landing/assets.json", lambda a: [s.update(sha256=h) for s in a["slots"] if s["slot_id"] == "hero"])
        self.assert_falla("contenido activo")

    def test_imagen_con_hash_distinto(self) -> None:
        (self.land / "imagenes" / "hero.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        self.assert_falla("sha256")

    def test_imagen_fuera_de_la_carpeta(self) -> None:
        def f(a):
            for s in a["slots"]:
                if s["slot_id"] == "hero":
                    s["archivo"] = "../03-oferta/oferta.json"
        self.editar_json("05-landing/assets.json", f)
        with self.assertRaises(ErrorValidacion):
            G.generar_sitio(self.d)

    def test_imagen_demasiado_pesada(self) -> None:
        self.editar_json("05-landing/assets.json", lambda a: [s.update(peso_max_kb=1) for s in a["slots"] if s["slot_id"] == "hero"])
        ruta = self.land / "imagenes" / "hero.svg"
        ruta.write_text(ruta.read_text(encoding="utf-8") + "<!--" + "x" * 3000 + "-->", encoding="utf-8")
        h = V.hash_archivo(ruta, servido=False)
        self.editar_json("05-landing/assets.json", lambda a: [s.update(sha256=h) for s in a["slots"] if s["slot_id"] == "hero"])
        self.assert_falla("pesa")

    def test_json_con_campos_extra_se_rechaza(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c["secciones"]["S01"].update(html_crudo="<b>x</b>"))
        self.assert_falla("copy.json no cumple su esquema")


class PruebaTextoAdversarioEscapado(Base):
    def test_ampersand_y_comillas_se_escapan(self) -> None:
        def f(c):
            c["secciones"]["S01"]["kicker"] = 'Guía & "plantilla" de <3'
        self.editar_json("05-landing/copy.json", f)
        G.generar_sitio(self.d)
        html = self.leer("index.html")
        self.assertIn("Guía &amp; &quot;plantilla&quot; de &lt;3", html)

    def test_marca_con_html_en_oferta_se_rechaza(self) -> None:
        self.editar_json("03-oferta/oferta.json", lambda o: o["marca"].update(nombre="Marca<script>"))
        with self.assertRaises(ErrorValidacion):
            G.generar_sitio(self.d)

    def test_negrita_y_enfasis_del_copy_se_convierten(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c["secciones"]["S03"].update(reencuadre="El problema no es **la pausa**. Es *no tener un orden*."))
        G.generar_sitio(self.d)
        html = self.leer("index.html")
        self.assertIn("<strong>la pausa</strong>", html)
        self.assertIn("<em>no tener un orden</em>", html)


class PruebaCompatibilidad(Base):
    def test_sin_copy_paleta_assets_cae_al_sitio_minimo_con_aviso(self) -> None:
        for n in ("copy.json", "paleta.json"):
            (self.land / n).unlink()
        def legado(r):    # el sitio mínimo no genera /desistimiento ni /comprar estática: rutas del modo anterior
            r.pop("/desistimiento"); r.pop("/api/sesion"); r["/comprar"] = "dinamica:crear-sesion"
        self.editar_json("05-landing/rutas.json", legado)
        salida, avisos = G.generar_sitio_con_avisos(self.d)
        self.assertTrue(any("faltan" in a and "copy.json" in a for a in avisos))
        self.assertIn("sitio/index.html", salida)
        self.assertNotIn("sitio/comprar.html", salida)
        self.assertEqual([], Val.validar_sitio(self.d))
        self.assertNotIn("tono-oscuro", self.leer("index.html"))

    def test_generar_sitio_devuelve_el_mapa_de_texto_como_antes(self) -> None:
        salida = G.generar_sitio(self.d)
        self.assertIsInstance(salida, dict)
        self.assertTrue({"sitio/index.html", "sitio/gracias.html", "sitio/css/estilos.css", "sitio/js/consentimiento.js", "sitio/js/pixel.js"} <= set(salida))
        self.assertTrue(all(isinstance(v, str) for v in salida.values()))

    def test_el_sitio_minimo_pasa_el_oraculo_con_los_js_nuevos(self) -> None:
        for n in ("copy.json", "paleta.json"):
            (self.land / n).unlink()
        G.generar_sitio(self.d)
        malas = [h for h in lint_oraculo(self.d) if h.regla not in ("L1-CONTADORES",)]
        # El sitio mínimo no es el entregable: solo se exige que los JS y el consentimiento cumplan el oráculo.
        self.assertEqual([], [h for h in malas if h.archivo.endswith(".js")])

    def test_cli_json_incluye_avisos(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = G.main(["--oferta", "OF-202611-01", "--raiz", str(self.tmp), "--json"])
        self.assertEqual(0, codigo)
        salida = json.loads(buf.getvalue())
        self.assertTrue(salida["ok"])
        self.assertTrue(salida["avisos"])
        self.assertIn("sitio/index.html", salida["datos"]["archivos"])

    def test_cli_sale_3_con_entrada_invalida(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c["secciones"]["S01"].update(h1="<b>x</b>"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(3, G.main(["--oferta", "OF-202611-01", "--raiz", str(self.tmp), "--json"]))

    def test_la_plantilla_no_trae_script_ni_red(self) -> None:
        plantilla = RAIZ / ".claude" / "skills" / "d5-landing-checkout" / "templates" / "sitio-base"
        for p in plantilla.rglob("*"):
            if p.is_file():
                t = p.read_text(encoding="utf-8")
                permitido = ('<script src="/js/consentimiento.js" defer></script>', '<script src="{{script_turnstile}}" async defer></script>')
                for scr in permitido:
                    t = t.replace(scr, "")
                self.assertNotRegex(t, r"(?i)<script|https?://|@import|javascript:", p.name)


class PruebaMutacionesSobreElSitioGenerado(Base):
    """El sitio generado también falla donde corresponde cuando se le siembra un defecto (validar y oráculo)."""

    def regla(self, hallazgos) -> set:
        return {h.regla for h in hallazgos}

    def test_precio_distinto_en_el_html(self) -> None:
        G.generar_sitio(self.d)
        p = self.sitio / "index.html"
        p.write_text(p.read_text(encoding="utf-8").replace("19,90 €", "17,90 €", 1), encoding="utf-8")
        self.assertIn("L1-PRECIO", self.regla(Val.validar_sitio(self.d)))
        self.assertIn("L1-PRECIO", self.regla(lint_oraculo(self.d)))

    def test_script_externo(self) -> None:
        G.generar_sitio(self.d)
        p = self.sitio / "index.html"
        p.write_text(p.read_text(encoding="utf-8").replace("</head>", '<script src="https://cdn.terceros.invalid/x.js"></script></head>', 1), encoding="utf-8")
        self.assertIn("L1-SCRIPT-EXTERNO", self.regla(Val.validar_sitio(self.d)))
        self.assertIn("L1-SCRIPT-EXTERNO", self.regla(lint_oraculo(self.d)))

    def test_legal_ausente(self) -> None:
        G.generar_sitio(self.d)
        (self.sitio / "legal" / "cookies.html").unlink()
        self.assertIn("L1-LEGALES", self.regla(Val.validar_sitio(self.d)))
        self.assertIn("L1-LEGALES", self.regla(lint_oraculo(self.d)))

    def test_el_sello_ejemplo_visible_se_detecta_pero_la_palabra_corriente_no(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c["secciones"]["S12"]["preguntas"][1].update(a="Por ejemplo, justo después del pago."))
        G.generar_sitio(self.d)
        self.assertEqual([], Val.validar_sitio(self.d))           # «por ejemplo» legítimo
        p = self.sitio / "index.html"
        p.write_text(p.read_text(encoding="utf-8").replace("<footer", "<p>EJEMPLO</p><footer", 1), encoding="utf-8")
        self.assertIn("L1-EJEMPLO-VISIBLE", self.regla(Val.validar_sitio(self.d)))

    def test_cifra_de_formato_no_se_toma_por_importe(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c["secciones"]["S12"]["preguntas"][2].update(a="La guía llega en 3 PDF y 2 XLS."))
        G.generar_sitio(self.d)
        self.assertEqual([], Val.validar_sitio(self.d))

    def test_importe_en_zloty_se_verifica(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = self.preparar(Path(t), "pl")
            G.generar_sitio(d)
            p = d / "05-landing" / "sitio" / "index.html"
            p.write_text(p.read_text(encoding="utf-8").replace("39,00 zł", "49,00 zł", 1), encoding="utf-8")
            self.assertIn("L1-PRECIO", self.regla(Val.validar_sitio(d)))


if __name__ == "__main__":
    unittest.main()


class _Balance(__import__("html.parser", fromlist=["HTMLParser"]).HTMLParser):
    VACIAS = {"meta", "link", "img", "br", "input", "hr", "source", "path", "circle", "rect", "use"}

    def __init__(self) -> None:
        super().__init__()
        self.pila: list[str] = []
        self.errores: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VACIAS:
            self.pila.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.VACIAS:
            return
        if not self.pila or self.pila[-1] != tag:
            self.errores.append(f"</{tag}> con pila {self.pila[-3:]}")
        else:
            self.pila.pop()


class PruebaHtmlBienFormado(Base):
    def test_todas_las_paginas_cierran_sus_etiquetas(self) -> None:
        for clave in OFERTAS:
            with tempfile.TemporaryDirectory() as t:
                d = self.preparar(Path(t), clave)
                G.generar_sitio(d)
                for p in (d / "05-landing" / "sitio").rglob("*.html"):
                    b = _Balance()
                    b.feed(p.read_text(encoding="utf-8"))
                    self.assertEqual([], b.errores, (clave, p.name))
                    self.assertEqual([], b.pila, (clave, p.name))


class PruebaAssetsYFuentes(Base):
    def test_assets_1_0_0_del_contrato_con_png_real(self) -> None:
        ej = RAIZ / "ofertas" / "_ejemplo" / "05-landing"
        shutil.copy(ej / "imagenes" / "hero-placeholder.png", self.land / "imagenes" / "hero-placeholder.png")
        assets = json.loads((ej / "assets.json").read_text(encoding="utf-8"))
        for ref in ("muestra-principal", "muestra-1"):
            assets["slots"].append({"slot_id": ref, "seccion": "producto", "tipo": "captura_producto", "ratio": "16:9", "proposito": "Muestra",
                                    "alt": "Muestra", "estado": "vacio", "peso_max_kb": 100, "archivo": None, "sha256": None, "origen": None,
                                    "ia_generado": False, "licencia_ref": None})
        assets["slots"] = [s for s in assets["slots"] if s["slot_id"] != "og"]
        (self.land / "assets.json").write_text(json.dumps(assets, ensure_ascii=False), encoding="utf-8")
        _, avisos = G.generar_sitio_con_avisos(self.d)
        html = self.leer("index.html")
        self.assertIn('src="/imagenes/hero-placeholder.png" width="160" height="90"', html)    # dimensiones leídas del PNG
        self.assertNotIn('id="muestra"', html)                                                  # sin capturas aprobadas
        self.assertNotIn("og:image", html)
        self.assertEqual([], Val.validar_sitio(self.d))

    def test_fuentes_autoalojadas_presentes_se_copian_y_se_precargan(self) -> None:
        (self.land / "fonts").mkdir()
        for n in ("source-serif-4-600", "source-serif-4-700", "source-sans-3-400", "source-sans-3-600"):
            (self.land / "fonts" / f"{n}.woff2").write_bytes(b"wOF2" + n.encode())
        G.generar_sitio(self.d)
        css = self.leer("css/estilos.css")
        self.assertIn('@font-face{font-family:"Source Serif 4"', css)
        self.assertIn('rel="preload" href="/fonts/source-sans-3-400.woff2"', self.leer("index.html"))
        self.assertTrue((self.sitio / "fonts" / "source-sans-3-400.woff2").is_file())
        self.assertEqual([], Val.validar_sitio(self.d))
        self.assertEqual([], [(h.regla, h.detalle) for h in lint_oraculo(self.d)])

    def test_idioma_sin_tabla_avisa_y_cae_a_ingles(self) -> None:
        self.editar_json("05-landing/copy.json", lambda c: c.update(locale="fr-FR"))
        self.editar_json("03-oferta/oferta.json", lambda o: o.update(locale="fr-FR"))
        _, avisos = G.generar_sitio_con_avisos(self.d)
        self.assertTrue(any("sin tabla" in a for a in avisos))
        self.assertIn('<html lang="fr-FR">', self.leer("index.html"))
        self.assertIn("Skip to content", self.leer("index.html"))
