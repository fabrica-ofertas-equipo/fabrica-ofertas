"""Componentes del plano «referente» de ``landing.generar``: barra superior, resaltado, héroe, tira, reseñas, niveles, para quién, bonus, comparación con el mercado,
precio, garantía, cómo lo recibes, CTA repetido, botón fijo, datos REALES (valoración, contador, barra de lanzamiento) y la VISTA PREVIA con su demostración.

Cada componente de datos reales se prueba en los dos sentidos (con dato real se muestra, sin dato o con dato cero se omite) y la demostración se prueba
como lo que es: solo en vista previa, nunca en producción (``L1-DEMO``, ``landing.desplegar``).

Comando: ``.venv/bin/python -m unittest tests.landing.test_componentes``
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import socket
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from engine import comun
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from landing import contenido, diseno, motor, textos
from landing import desplegar as D
from landing import generar as G
from landing import validar as Val
from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "landing"
HOY = date(2026, 11, 7)
SKILL = RAIZ / ".claude" / "skills" / "d5-landing-checkout"


def _sin_red(*_a, **_k):  # pragma: no cover - solo se ejecuta si algo intenta abrir un socket
    raise AssertionError("las pruebas de landing no abren sockets")


def a_referente(c: dict, *, comparacion: bool = True) -> None:
    """Convierte el copy 0.1.x de la fixture pl-PL en un copy 0.2.0 del plano referente con todos los componentes nuevos."""
    c["schema_version"] = "0.2.0"
    c["barra_superior"] = {"informativa": "Płatność jednorazowa · pliki od razu · zwrot {garantia_dias} dni", "icono": "escudo"}
    s = c["secciones"]
    s["S01"]["h1"] = "==Karty== do rozmowy bez improwizacji"
    s["S04"]["pies"].append({"imagen_ref": "muestra-1", "texto": "Druga karta z zestawu"})
    s["S06"]["modulos"][0]["etiqueta"] = "{n:karty} kart"
    s["S06"]["modulos"][0]["temas"] = ["Praca", "Dom"]
    s["S06"]["modulos"][0]["categorias"] = [{"titulo": "Pytania", "texto": "Na spokojną rozmowę.", "temas": ["Plany", "Wspomnienia"]}]
    s["S07"]["tarjetas"] = [{"titulo": "Dla par", "texto": "Mieszkacie razem i szukacie pomysłu na rozmowę.", "icono": "corazon"},
                            {"titulo": "Dla wolących gotowce", "texto": "Gotowe pytania zamiast improwizacji.", "icono": "rayo"},
                            {"titulo": "Dla spokojnego tempa", "texto": "Bez presji i bez terminu.", "icono": "reloj"},
                            {"titulo": "Dla zapracowanych", "texto": "Jedna karta to krótka rozmowa.", "icono": "calendario"}]
    s["S15"] = {"titulo": "Jak dostajesz materiał", "pasos": [{"titulo": "Płatność", "texto": "Na stronie Stripe.", "icono": "candado"},
                                                             {"titulo": "E-mail", "texto": "Link od razu.", "icono": "sobre"},
                                                             {"titulo": "Wydruk", "texto": "Zwykła drukarka.", "icono": "imprimir"}]}
    if comparacion:
        s["S16"] = {"titulo": "Cena na tle rynku", "filas": [
            {"etiqueta": "Zestawy kart w PDF", "desde": 1200, "hasta": 3300, "fuente": "tienda-a.pl", "fecha": "2026-11-06"},
            {"etiqueta": "Kurs wideo", "desde": 12900, "fuente": "kursy-b.pl", "fecha": "2026-11-07"}]}


class Base(unittest.TestCase):
    clave = ("oferta_pl_relaciones", "OF-202611-02")

    def setUp(self) -> None:
        patcher = mock.patch.object(socket, "socket", _sin_red)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="landing-comp-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        carpeta, oid = self.clave
        self.d = self.tmp / "ofertas" / oid
        shutil.copytree(FIX / carpeta, self.d)
        shutil.copytree(FIX / "empresa", self.tmp / "empresa", dirs_exist_ok=True)
        self.land, self.sitio = self.d / "05-landing", self.d / "05-landing" / "sitio"
        self.vp = self.land / "sitio-vista-previa"                                          # F-62: la vista previa NUNCA se escribe en sitio/
        self.ultima = self.sitio
        self.editar("05-landing/copy.json", a_referente)

    def editar(self, rel: str, f) -> None:
        ruta = self.d / rel
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        f(datos)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def copy(self, f) -> None:
        self.editar("05-landing/copy.json", f)

    def generar(self, **k):
        k.setdefault("hoy", HOY)
        self.ultima = self.vp if k.get("vista_previa") else self.sitio                     # `html()` lee lo último que se generó
        return G.generar_sitio_con_avisos(self.d, **k)

    def html(self, rel: str = "index.html") -> str:
        return (self.ultima / rel).read_text(encoding="utf-8")

    def hallazgos(self, **k):
        return Val.validar_sitio(self.d, hoy=k.pop("hoy", HOY), **k)

    def reglas(self, **k) -> set[str]:
        return {h.regla for h in self.hallazgos(**k)}

    def prueba_social(self, **bloques) -> None:
        doc = {"schema_version": "0.1.0", "oferta_id": "OF-202611-02", "generado_en": "2026-11-07T10:00:00Z", **bloques}
        (self.land / "prueba_social_real.json").write_text(json.dumps(doc), encoding="utf-8")


# ----------------------------------------------------------------------------------------------
class PruebaMarcatextosYMotor(unittest.TestCase):
    def test_resaltado_se_escapa_y_solo_produce_mark(self) -> None:
        self.assertEqual('Mapy <mark class="marca">słownictwa</mark> a', str(motor.md("Mapy ==słownictwa== a")))
        self.assertEqual("&lt;b&gt;x&lt;/b&gt; <mark class=\"marca\">y</mark>", str(motor.md("<b>x</b> ==y==")))
        self.assertNotIn("<mark", str(motor.md("a == b ==")))          # con espacios no es marca
        self.assertEqual("A b c", motor.texto_plano("A ==b== **c**"))

    def test_resaltado_no_admite_atributos_del_maker(self) -> None:
        salida = str(motor.md('==a" onclick="x=='))
        self.assertNotIn("<mark", salida)                                                  # el contenido con «=» no es marca: queda escapado
        self.assertNotIn('onclick="', salida)
        self.assertEqual('<mark class="marca">a&quot; onclick</mark>', str(motor.md('==a" onclick==')))


class PruebaSistemaVisual(unittest.TestCase):
    def test_iconos_de_color_cumplen_3_a_1_y_son_deterministas(self) -> None:
        for fixt in ("oferta_es_dinero", "oferta_pl_relaciones"):
            paleta = json.loads((FIX / fixt / "05-landing" / "paleta.json").read_text(encoding="utf-8"))
            d = diseno.construir_diseno(paleta)
            self.assertEqual(d.css_tokens, diseno.construir_diseno(paleta).css_tokens)
            for nombre, tono in d.tonos.items():
                self.assertEqual(6, len(tono.iconos), nombre)
                for i, (fg, bg) in enumerate(tono.iconos):
                    self.assertGreaterEqual(diseno.razon_contraste(fg, bg) + 1e-9, 3.0, (fixt, nombre, i))
            self.assertIn("--marca-fondo:", d.css_tokens)
            self.assertIn("--ic6-bg:", d.css_tokens)

    def test_resalte_es_el_par_del_boton_y_cumple_aa(self) -> None:
        paleta = json.loads((FIX / "oferta_es_dinero" / "05-landing" / "paleta.json").read_text(encoding="utf-8"))
        d = diseno.construir_diseno(paleta)
        c = paleta["colores"]
        self.assertIn(f"--marca-fondo:{c['cta_fondo']['hex'].upper()}", d.css_tokens)
        self.assertGreaterEqual(diseno.razon_contraste(c["cta_texto"]["hex"], c["cta_fondo"]["hex"]), 4.5)

    def test_rotar_tono_conserva_brillo(self) -> None:
        self.assertEqual("#00FF00", diseno.rotar_tono("#FF0000", 120))
        self.assertEqual("#FF0000", diseno.rotar_tono("#FF0000", 360))


# ----------------------------------------------------------------------------------------------
class PruebaPlano(Base):
    ANCLAS = ["inicio", "muestra", "confianza", "incluye", "para-quien", "extras", "comparacion", "oferta", "garantia", "como-recibes", "preguntas", "cierre"]

    def anclas(self, html: str) -> list[str]:
        return re.findall(r'<section class="seccion[^"]*"[^>]* id="([a-z-]+)"', html)

    def test_orden_del_referente_con_cta_y_garantia_despues_del_precio(self) -> None:
        self.generar()
        self.assertEqual(self.ANCLAS, self.anclas(self.html()))
        self.assertLess(self.html().index('id="oferta"'), self.html().index('id="garantia"'))      # garantía DESPUÉS del precio
        self.assertEqual(1, self.html().count("<h1"))

    def test_copy_01x_conserva_el_plano_clasico_y_estructura_manda(self) -> None:
        self.copy(lambda c: c.update(schema_version="0.1.0"))
        self.generar()
        self.assertIn("problema", self.anclas(self.html()))
        self.assertNotIn("como-recibes", self.anclas(self.html()))
        self.copy(lambda c: c.update(schema_version="0.2.0", estructura="clasica"))
        self.generar()
        self.assertEqual("clasica", contenido.plano_de(json.loads((self.land / "copy.json").read_text(encoding="utf-8"))))
        self.assertIn("metodo", self.anclas(self.html()))

    def test_referente_sin_s03_ni_s05_valida_y_clasico_sin_ellas_no(self) -> None:
        self.copy(lambda c: [c["secciones"].pop(x, None) for x in ("S02", "S03", "S05")])
        self.generar()                                                                     # el plano referente no las exige
        self.copy(lambda c: c.update(estructura="clasica"))
        with self.assertRaises(ErrorValidacion) as cm:
            self.generar()
        self.assertIn("copy.json no cumple su esquema", cm.exception.mensaje)

    def test_secciones_fuera_del_plano_avisan(self) -> None:
        _, avisos = self.generar()
        self.assertTrue(any("S03 no forma parte del plano referente" in a for a in avisos))

    def test_cta_repetido_tras_los_bloques_y_boton_fijo_solo_css(self) -> None:
        self.generar()
        html = self.html()
        self.assertEqual(5, html.count('class="contenedor cta-bloque"'))                  # muestra, confianza, incluye, para-quién, cómo lo recibes
        self.assertTrue(all(h == "/comprar" for h in re.findall(r'class="boton boton--cta[^"]*" href="([^"]+)"', html)))
        self.assertIn('class="barra-cta tono-oscuro"', html)                               # botón fijo inferior
        css = (self.sitio / "css" / "estilos.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"@media \(max-width:47\.99rem\)\{\s*\.barra-cta\{position:sticky;bottom:0")
        self.assertEqual(['src="/js/consentimiento.js"'], re.findall(r'<script[^>]*?(src="[^"]+")', html))

    def test_cta_de_bloque_usa_cta_ref_o_el_uso_declarado(self) -> None:
        def f(c):
            c["cta"].append({"id": "cta-niveles", "texto": "Zobacz zestaw", "usos": ["S06"]})
            c["secciones"]["S07"]["cta_ref"] = "cta-cierre"
        self.copy(f)
        self.generar()
        textos_cta = re.findall(r'cta-bloque">\s*<a[^>]*><span>([^<]+)</span>', self.html())
        self.assertIn("Zobacz zestaw", textos_cta)
        self.assertIn("Zaczynam od jednego pytania", textos_cta)

    def test_clase_del_cuerpo_y_barra_superior_informativa(self) -> None:
        self.generar()
        html = self.html()
        self.assertIn('<body class="plano-referente"', html)
        self.assertIn('class="barra-superior"', html)
        barra = re.search(r'<div class="barra-superior".*?</div>', html, re.S).group(0)
        self.assertIn("zwrot 14 dni", barra)
        self.assertNotIn("barra-superior", self.html("comprar.html"))                      # solo en las páginas de venta

    def test_h1_con_palabra_clave_resaltada(self) -> None:
        self.generar()
        self.assertIn('<h1 id="titulo-hero"><mark class="marca">Karty</mark> do rozmowy', self.html())
        self.assertNotIn("==", re.search(r"<title>(.*?)</title>", self.html()).group(1))

    def test_pasa_validar_y_es_determinista(self) -> None:
        self.generar()
        self.assertEqual([], [str(h) for h in self.hallazgos()])
        a = V.hash_directorio(self.sitio)
        shutil.rmtree(self.sitio)
        self.generar()
        self.assertEqual(a, V.hash_directorio(self.sitio))


class PruebaComponentesDeContenido(Base):
    def test_niveles_con_pestanas_css_puro(self) -> None:
        self.generar()
        h = self.html()
        self.assertEqual(2, h.count('class="pestanas__ancla"'))
        self.assertIn('href="#nivel-1"', h)
        self.assertIn('id="panel-nivel-2"', h)
        self.assertIn("Pytania", h)                                                        # categoría del panel
        self.assertEqual(1, len(re.findall(r'pestanas--n2', h)))
        self.assertNotRegex(h, r"<input|<form|onclick")

    def test_niveles_con_selector_desplegable_details(self) -> None:
        self.copy(lambda c: c["secciones"]["S06"].update(selector="desplegable"))
        self.generar()
        h = self.html()
        self.assertEqual(2, h.count('<details class="nivel" name="niveles">'))
        self.assertIn("<summary>", h)
        self.assertEqual([], [str(x) for x in self.hallazgos()])

    def test_para_quien_cuatro_tarjetas_con_icono_y_panel_no_encaja(self) -> None:
        self.generar()
        h = self.html()
        self.assertEqual(4, h.count('class="tarjeta tarjeta--perfil"'))
        self.assertIn('href="#i-corazon"', h)
        self.assertIn('class="panel no-encaja"', h)

    def test_para_quien_deriva_de_si_sin_tarjetas(self) -> None:
        self.copy(lambda c: c["secciones"]["S07"].pop("tarjetas"))
        self.generar()
        self.assertEqual(3, self.html().count('class="tarjeta tarjeta--perfil"'))

    def test_icono_desconocido_falla_cerrado(self) -> None:
        self.copy(lambda c: c["secciones"]["S07"]["tarjetas"][0].update(icono="../x"))
        with self.assertRaises(ErrorValidacion) as cm:
            self.generar()
        self.assertIn("copy.json no cumple su esquema", cm.exception.mensaje)

    def test_tira_muestra_las_miniaturas_aprobadas_y_se_omite_sin_ellas(self) -> None:
        self.generar()
        h = self.html()
        self.assertIn('class="tira__carril" tabindex="0"', h)
        self.assertEqual(2, h.count('class="miniatura'))
        def sin(a):
            for s in a["slots"]:
                if s["seccion"] == "galeria":
                    s.update(estado="omitida", archivo=None, sha256=None, origen=None)
        self.editar("05-landing/assets.json", sin)
        _, avisos = self.generar()
        self.assertNotIn('id="muestra"', self.html())                                       # sin imagen no hay bloque ni imagen inventada
        self.assertTrue(any("S04 omitida" in a for a in avisos))

    def test_bonus_con_portada_y_sin_ella(self) -> None:
        def f(c):
            c["secciones"]["S09"]["bonos"] = [{"nombre": "Karta notatek", "texto": "Miejsce na notatki.", "archivo_ref": "karty"}]
        self.copy(f)
        self.generar()
        h = self.html()
        self.assertIn('class="bono-tarjeta"', h)
        self.assertIn("Bonus #1", h)
        self.assertNotIn("vp-marcador", h)                                                  # sin portada y fuera de la vista previa: icono, no marcador
        self.assertIn('class="bono-tarjeta__icono', h)

    def test_como_lo_recibes_explicito_derivado_u_omitido(self) -> None:
        self.generar()
        self.assertIn('id="como-recibes"', self.html())
        self.copy(lambda c: c["secciones"].pop("S15"))
        self.generar()
        self.assertEqual(4, self.html().count('class="paso"'))                              # derivado del checklist de S06 (4 ítems)
        self.copy(lambda c: c["secciones"]["S06"].pop("checklist"))
        self.generar()
        self.assertNotIn('id="como-recibes"', self.html())

    def test_garantia_con_insignia_precio_y_final(self) -> None:
        self.generar()
        h = self.html()
        self.assertIn('class="escudo"', h)
        self.assertIn('class="caja-oferta"', h)
        self.assertIn("Co dostajesz", h)
        self.assertIn('class="lista-seguridad"', h)


class PruebaComparacionConElMercado(Base):
    def test_cifras_con_fuente_y_marcadas_como_comparacion(self) -> None:
        self.generar()
        h = self.html()
        self.assertIn("data-comparacion-mercado", h)
        h = h.replace("\u00a0", " ")
        self.assertIn("12–33 zł", h)
        self.assertIn("129 zł", h)
        self.assertEqual(2, h.count("data-comparacion-cifra"))
        self.assertEqual(2, len(re.findall(r'data-comparacion-cifra data-fuente="[^"]+"', h)))
        self.assertIn("Źródło: tienda-a.pl", h)
        self.assertIn("Ceny opublikowane przez osoby trzecie", h)                           # rótulo de comparación

    def test_l1_exenta_solo_las_cifras_marcadas_con_fuente(self) -> None:
        self.generar()
        self.assertEqual([], [str(x) for x in self.hallazgos()])                            # las cifras ajenas (12–33 zł, 129 zł) no son L1-PRECIO
        ruta = self.sitio / "index.html"
        original = ruta.read_text(encoding="utf-8")
        ruta.write_text(original.replace(' data-fuente="tienda-a.pl"', ' data-fuente=""'), encoding="utf-8")
        self.assertIn("L1-COMPARACION", self.reglas())                                      # sin fuente no hay exención
        ruta.write_text(original.replace("<section class=\"seccion comparacion", "<section class=\"seccion comparacion-x").replace(" data-comparacion-mercado", ""), encoding="utf-8")
        self.assertIn("L1-COMPARACION", self.reglas())                                      # fuera del bloque marcado tampoco
        ruta.write_text(original.replace("</main>", "<p>Cena 59 zł</p></main>"), encoding="utf-8")
        self.assertIn("L1-PRECIO", self.reglas())                                           # un importe ajeno suelto sigue bloqueado

    def test_importe_escrito_en_el_texto_sigue_bloqueado(self) -> None:
        self.copy(lambda c: c["secciones"]["S16"]["filas"][0].update(etiqueta="PDF 12–33 zł"))
        self.generar()
        self.assertIn("L1-PRECIO", self.reglas())

    def test_fila_sin_fuente_no_se_publica(self) -> None:
        def f(c):
            c["secciones"]["S16"]["filas"][1]["fuente"] = "   "
        self.copy(f)
        _, avisos = self.generar()                                                          # una fila sin fuente (aunque sean espacios) no se publica
        self.assertNotIn("kursy-b.pl", self.html())
        self.assertNotIn("129 zł", self.html().replace("\u00a0", " "))
        self.assertTrue(any("S16.filas[1] sin fuente" in a for a in avisos))
        self.copy(lambda c: c["secciones"]["S16"]["filas"][0].update(fuente=""))
        with self.assertRaises(ErrorValidacion):                                            # y el esquema exige una fuente de 3+ caracteres
            self.generar()

    def test_fecha_invalida_o_hasta_menor_fallan_cerrado(self) -> None:
        self.copy(lambda c: c["secciones"]["S16"]["filas"][0].update(fecha="2026-02-31"))
        with self.assertRaises(ErrorValidacion):
            self.generar()
        self.copy(lambda c: c["secciones"]["S16"]["filas"][0].update(fecha="2026-11-06", hasta=100))
        with self.assertRaises(ErrorValidacion):
            self.generar()

    def test_sin_s16_no_hay_bloque(self) -> None:
        self.copy(lambda c: c["secciones"].pop("S16"))
        self.generar()
        self.assertNotIn("data-comparacion", self.html())


class PruebaLintCopyComparacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        espec = importlib.util.spec_from_file_location("_lint_copy_comp", SKILL / "scripts" / "lint_copy.py")
        cls.L = importlib.util.module_from_spec(espec)
        espec.loader.exec_module(cls.L)
        cls.copy = json.loads((FIX / "oferta_pl_relaciones" / "05-landing" / "copy.json").read_text(encoding="utf-8"))
        cls.oferta = json.loads((FIX / "oferta_pl_relaciones" / "03-oferta" / "oferta.json").read_text(encoding="utf-8"))
        a_referente(cls.copy)

    def lint(self, mut=None):
        import copy as _c
        c = _c.deepcopy(self.copy)
        if mut:
            mut(c)
        return self.L.linter(c, self.oferta)

    def test_s16_con_fuente_y_fecha_no_dispara_importe_ni_traza(self) -> None:
        malos = [x for x in self.lint() if x["ruta"].startswith("secciones.S16")]
        self.assertEqual([], malos)

    def test_s16_sin_fuente_es_bloqueante(self) -> None:
        h = self.lint(lambda c: c["secciones"]["S16"]["filas"][0].update(fuente=""))
        self.assertTrue(any(x["regla"] == "D5-COPY-COMPARACION-SIN-FUENTE" and x["severidad"] == "BLOQUEANTE" for x in h))

    def test_importe_en_el_texto_de_s16_sigue_bloqueado(self) -> None:
        h = self.lint(lambda c: c["secciones"]["S16"]["filas"][0].update(etiqueta="PDF 12–33 zł"))
        self.assertTrue(any(x["regla"] == "D5-COPY-IMPORTE" and x["severidad"] == "BLOQUEANTE" for x in h))

    def test_importe_en_la_fuente_sigue_bloqueado(self) -> None:
        h = self.lint(lambda c: c["secciones"]["S16"]["filas"][0].update(fuente="tienda 59 zł"))
        self.assertTrue(any(x["regla"] == "D5-COPY-IMPORTE" for x in h))

    def test_el_resto_del_control_de_precios_no_se_relaja(self) -> None:
        h = self.lint(lambda c: c["secciones"]["S11"].update(linea_precio="Zamiast 99 zł tylko {precio}"))
        self.assertTrue(any(x["regla"] == "D5-COPY-IMPORTE" and x["severidad"] == "BLOQUEANTE" for x in h))

    def test_plano_referente_no_exige_s03_s05_y_fuera_de_plano_es_menor(self) -> None:
        h = self.lint()
        self.assertFalse(any(x["regla"] == "D5-COPY-SECCION" for x in h))
        self.assertTrue(any(x["regla"] == "D5-COPY-SECCION-FUERA-DE-PLANO" and x["severidad"] == "MENOR" for x in h))
        h2 = self.lint(lambda c: (c.update(estructura="clasica"), c["secciones"].pop("S03")))
        self.assertTrue(any(x["regla"] == "D5-COPY-SECCION" and "S03" in x["ruta"] for x in h2))

    def test_placeholders_de_lanzamiento_conocidos(self) -> None:
        def f(c):
            c["barra_superior"]["lanzamiento"] = {"texto": "Cena premierowa {precio} do {fecha_lanzamiento}, potem {precio_despues}", "fecha": "2026-11-30"}
        h = self.lint(f)
        self.assertFalse(any(x["regla"] == "D5-COPY-PLACEHOLDER" for x in h))


# ----------------------------------------------------------------------------------------------
class PruebaBarraDeLanzamiento(Base):
    TEXTO = "Cena premierowa {precio} do {fecha_lanzamiento}, potem {precio_despues}"

    def preparar(self, fecha="2026-11-30", despues=5900, copy_fecha=None, moneda="PLN") -> None:
        self.copy(lambda c: c["barra_superior"].update(lanzamiento={"texto": self.TEXTO, "fecha": copy_fecha or fecha}))
        self.editar("05-landing/checkout.json", lambda k: k.update(precio_programado={"fecha": fecha, "precio": {"monto": despues, "moneda": moneda}}))

    def test_con_precio_programado_de_la_misma_fecha_se_muestra(self) -> None:
        self.preparar()
        self.generar()
        h = self.html()
        self.assertIn('data-barra-lanzamiento="2026-11-30"', h)
        self.assertIn("30 listopada 2026", h)
        self.assertIn("59,00", h)
        self.assertEqual([], [str(x) for x in self.hallazgos()])                            # el precio de después está en checkout.json: no es L1-PRECIO
        self.assertNotRegex(h.lower(), r"odliczanie|countdown|cuenta regresiva|00:00")

    def test_sin_precio_programado_o_con_otra_fecha_se_omite_y_cae_a_la_informativa(self) -> None:
        self.copy(lambda c: c["barra_superior"].update(lanzamiento={"texto": self.TEXTO, "fecha": "2026-11-30"}))
        _, avisos = self.generar()
        self.assertNotIn("data-barra-lanzamiento", self.html())
        self.assertIn("zwrot 14 dni", self.html())
        self.assertTrue(any("sin precio_programado" in a.replace("checkout.json no trae precio_programado", "sin precio_programado") for a in avisos))
        self.preparar(fecha="2026-11-30", copy_fecha="2026-12-01")
        _, avisos = self.generar()
        self.assertNotIn("data-barra-lanzamiento", self.html())
        self.assertTrue(any("no coincide" in a for a in avisos))

    def test_fecha_pasada_o_precio_que_no_sube_se_omiten(self) -> None:
        self.preparar(fecha="2026-11-30")
        _, avisos = self.generar(hoy=date(2026, 12, 1))
        self.assertNotIn("data-barra-lanzamiento", self.html())
        self.assertTrue(any("ya pasó" in a for a in avisos))
        self.preparar(despues=3900)                                                         # igual al actual: no es un precio de lanzamiento
        _, avisos = self.generar()
        self.assertNotIn("data-barra-lanzamiento", self.html())
        self.assertTrue(any("debe ser mayor" in a for a in avisos))

    def test_validar_bloquea_la_barra_vencida_o_sin_respaldo(self) -> None:
        self.preparar()
        self.generar()
        self.assertEqual(set(), self.reglas())
        self.assertIn("L1-BARRA-LANZAMIENTO", self.reglas(hoy=date(2026, 12, 1)))           # vencida
        self.editar("05-landing/checkout.json", lambda k: k.pop("precio_programado"))
        self.assertIn("L1-BARRA-LANZAMIENTO", self.reglas())                                # sin precio programado que la respalde


class PruebaDatosReales(Base):
    def test_sin_archivo_o_con_total_cero_no_hay_pastilla_ni_contador_ni_demo(self) -> None:
        self.generar()
        h = self.html()
        self.assertNotIn("prueba-pastilla", h)
        self.assertNotIn("contador-real", h)
        self.prueba_social(ventas={"total": 0, "fuente": "Stripe", "al": "2026-11-07"}, descargas_muestra={"total": 0, "fuente": "Registro", "al": "2026-11-07"})
        self.generar()
        self.assertNotIn("contador-real", self.html())

    def test_con_dato_real_se_muestra_con_fuente_y_fecha_y_valida(self) -> None:
        self.prueba_social(ventas={"total": 12, "fuente": "Stripe", "al": "2026-11-07"}, valoracion={"media_decimas": 47, "n": 9, "fuente": "Reseñas", "al": "2026-11-07"})
        self.generar()
        h = self.html()
        self.assertIn("4,7", h)
        self.assertIn(">9<".replace(">9<", "9 opinii"), h)
        self.assertIn('data-prueba-social="ventas" data-valor="12"', h)
        self.assertIn("7 listopada 2026", h)
        self.assertNotIn("demo", h.lower())
        self.assertEqual([], [str(x) for x in self.hallazgos()])

    def test_las_descargas_de_la_muestra_se_muestran_si_no_hay_ventas(self) -> None:
        self.prueba_social(descargas_muestra={"total": 1234, "fuente": "Registro de descargas", "al": "2026-11-07"})
        self.generar()
        self.assertIn("Pobrania próbki", self.html())
        self.assertIn("1\u00a0234", self.html())

    def test_validar_bloquea_un_contador_sin_respaldo_o_distinto(self) -> None:
        self.prueba_social(ventas={"total": 12, "fuente": "Stripe", "al": "2026-11-07"})
        self.generar()
        ruta = self.sitio / "index.html"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace('data-valor="12"', 'data-valor="3482"').replace("12</strong>", "3 482</strong>"), encoding="utf-8")
        self.assertIn("L1-PRUEBA-SOCIAL", self.reglas())
        (self.land / "prueba_social_real.json").unlink()
        self.assertIn("L1-PRUEBA-SOCIAL", self.reglas())

    def test_archivo_invalido_o_de_otra_oferta_falla_cerrado(self) -> None:
        (self.land / "prueba_social_real.json").write_text(json.dumps({"schema_version": "0.1.0", "oferta_id": "OF-202611-99", "generado_en": "2026-11-07T10:00:00Z"}), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            self.generar()
        self.prueba_social(ventas={"total": -3, "fuente": "Stripe", "al": "2026-11-07"})
        with self.assertRaises(ErrorValidacion):
            self.generar()

    def test_resenas_reales_con_compra_verificada_y_permiso(self) -> None:
        def f(c):
            c["secciones"]["S08"].update(modo="real", resenas=[{"compra_id": "cs_test_123", "texto": "Karty są proste i spokojne.", "autor": "Anna K."}])
        self.copy(f)
        def oferta(o):
            o["prueba"].append({"tipo": "testimonio_con_permiso", "fuente": "cs_test_123", "consentimiento_ref": "consentimientos/anna.json"})
        self.editar("03-oferta/oferta.json", oferta)
        self.generar()
        h = self.html()
        self.assertIn("Zweryfikowany zakup", h)
        self.assertIn("Anna K.", h)
        self.assertIn('data-fuente="cs_test_123"', h)
        self.assertNotIn("demo", h.lower())
        self.assertEqual([], [str(x) for x in self.hallazgos()])

    def test_resena_sin_permiso_falla_cerrado(self) -> None:
        self.copy(lambda c: c["secciones"]["S08"].update(modo="real", resenas=[{"compra_id": "cs_no", "texto": "Inventada."}]))
        with self.assertRaises(ErrorValidacion):
            self.generar()

    def test_sin_resenas_reales_ni_bloques_el_bloque_se_omite(self) -> None:
        self.copy(lambda c: c["secciones"]["S08"].update(bloques=[]))
        _, avisos = self.generar()
        self.assertNotIn('id="confianza"', self.html())
        self.assertTrue(any("S08 omitida" in a for a in avisos))


# ----------------------------------------------------------------------------------------------
class PruebaVistaPrevia(Base):
    def test_vista_previa_pinta_opiniones_de_demostracion_con_cinta_y_avisos(self) -> None:
        _, avisos = self.generar(vista_previa=True)
        h = self.html()
        self.assertEqual(4, h.count('data-demo="resena"'))
        self.assertEqual(4, h.count('<span class="cinta-demo">DEMO</span>'))
        self.assertIn("Vista previa: opiniones de demostración, no son reales", h)
        self.assertIn("Anna K. (demo)", h)
        self.assertIn("resena--chat", h)                                                    # una variante estilo chat
        self.assertEqual(25, h.count('href="#i-estrella"'))                                 # 4 tarjetas demo × 5 estrellas + la pastilla de valoración demo
        self.assertIn('<div class="vp-barra" data-demo="barra"', h)
        self.assertIn("VISTA PREVIA — contiene contenido de demostración", h)
        self.assertIn('data-vista-previa="1"', h)
        self.assertTrue(any("VISTA PREVIA" in a for a in avisos))

    def test_vista_previa_pinta_la_pastilla_y_el_contador_demo_con_cinta(self) -> None:
        self.generar(vista_previa=True)
        h = self.html()
        self.assertIn('<span class="cinta-demo" data-demo="valoracion">DEMO</span>', h)
        self.assertIn('<span class="cinta-demo" data-demo="contador">DEMO</span>', h)
        self.assertNotIn("data-prueba-social", h)                                           # lo demo nunca se ofrece como dato verificable

    def test_marcadores_de_imagen_en_vista_previa(self) -> None:
        def sin(a):
            for s in a["slots"]:
                if s["seccion"] in ("galeria", "compra", "hero") and s["estado"] == "aprobado":
                    s.update(estado="vacio", archivo=None, sha256=None, origen=None)
        self.editar("05-landing/assets.json", sin)
        self.generar(vista_previa=True)
        h = self.html()
        for que in ("mockup del producto", "miniatura de un mapa"):
            self.assertIn(f"[vista previa: {que}]", h)
        self.assertNotIn('class="portada"', h)                                              # el marcador sustituye a la portada, nunca una imagen falsa
        self.assertNotIn("<img", h.split("<body")[1])                                       # y ninguna <img> sin archivo aprobado

    def test_la_generacion_normal_no_pinta_nada_de_demo_y_pasa_l1(self) -> None:
        self.generar()
        for p in self.sitio.rglob("*.html"):
            t = p.read_text(encoding="utf-8")
            self.assertEqual([], Val.marcas_de_demo(t), p.name)
            self.assertNotIn("vp-barra", t)
            self.assertNotIn("data-vista-previa", t)
        self.assertEqual([], [str(x) for x in self.hallazgos()])
        self.assertNotIn("(demo)", self.html())

    def test_validar_bloquea_una_pagina_con_demo(self) -> None:
        self.generar(vista_previa=True)
        h = self.hallazgos(carpeta="sitio-vista-previa")
        self.assertIn("L1-DEMO", {x.regla for x in h})
        self.assertEqual({"L1-DEMO"}, {x.regla for x in h})                                 # y solo esa: la vista previa es válida en todo lo demás
        # cualquiera de las marcas basta
        self.generar()
        ruta = self.sitio / "index.html"
        base = ruta.read_text(encoding="utf-8")
        for marca in ('<p data-demo="x">a</p>', '<p class="demo-x">a</p>', '<span class="cinta-demo">DEMO</span>', "<p>VISTA PREVIA</p>", "<p>[vista previa: x]</p>"):
            ruta.write_text(base.replace("</main>", marca + "</main>"), encoding="utf-8")
            self.assertIn("L1-DEMO", self.reglas(), marca)

    def test_las_palabras_normales_no_disparan_l1_demo(self) -> None:
        self.assertEqual([], Val.marcas_de_demo("<p>Esta demo de la muestra y una vista previa del PDF</p>"))

    def test_reales_sustituyen_a_demo(self) -> None:
        self.prueba_social(ventas={"total": 5, "fuente": "Stripe", "al": "2026-11-07"}, valoracion={"media_decimas": 48, "n": 5, "fuente": "Reseñas", "al": "2026-11-07"})
        def f(c):
            c["secciones"]["S08"].update(modo="real", resenas=[{"compra_id": "cs_test_9", "texto": "Prosto i spokojnie.", "autor": "Ola M."}])
        self.copy(f)
        self.editar("03-oferta/oferta.json", lambda o: o["prueba"].append({"tipo": "testimonio_con_permiso", "fuente": "cs_test_9", "consentimiento_ref": "c/ola.json"}))
        self.generar(vista_previa=True)
        h = self.html()
        self.assertIn("Ola M.", h)
        self.assertNotIn("(demo)", h)                                                       # las reseñas reales sustituyen a las de demostración
        self.assertNotIn('data-demo="valoracion"', h)
        self.assertNotIn('data-demo="contador"', h)
        self.assertNotIn('data-demo="resena"', h)
        self.assertIn('data-prueba-social="ventas"', h)

    def test_sin_resenas_reales_y_sin_vista_previa_el_bloque_de_opiniones_se_omite(self) -> None:
        self.copy(lambda c: c["secciones"]["S08"].update(bloques=[]))
        self.generar(vista_previa=True)
        self.assertIn('data-demo="resena"', self.html())                                    # con vista previa hay demo
        self.generar()
        self.assertNotIn('id="confianza"', self.html())                                     # sin ella, nada

    def test_cli_rechaza_vista_previa_en_produccion(self) -> None:
        env = {**os.environ, "FABRICA_ENTORNO": "produccion"}
        with mock.patch.dict(os.environ, env, clear=True):
            codigo = G.main(["--oferta", "OF-202611-02", "--vista-previa"])
        self.assertEqual(2, codigo)                                                         # código de uso: no genera nada
        self.assertFalse(self.sitio.exists())

    def test_cli_vista_previa_escribe_y_simular_no(self) -> None:
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "prueba"}, clear=True):
            self.assertEqual(0, G.main(["--oferta", "OF-202611-02", "--raiz", str(self.tmp), "--vista-previa", "--hoy", "2026-11-07", "--simular"]))
            self.assertFalse(self.sitio.exists() or self.vp.exists())
            self.assertEqual(0, G.main(["--oferta", "OF-202611-02", "--raiz", str(self.tmp), "--vista-previa", "--hoy", "2026-11-07"]))
        self.assertFalse(self.sitio.exists())                                               # la vista previa NO toca sitio/
        self.assertIn("(demo)", (self.vp / "index.html").read_text(encoding="utf-8"))

    def test_vista_previa_es_determinista(self) -> None:
        self.generar(vista_previa=True)
        a = V.hash_directorio(self.vp)
        shutil.rmtree(self.vp)
        self.generar(vista_previa=True)
        self.assertEqual(a, V.hash_directorio(self.vp))

    def test_la_vista_previa_nunca_pisa_sitio(self) -> None:                                # F-62
        self.generar()
        antes = V.hash_directorio(self.sitio)
        self.generar(vista_previa=True)
        self.assertEqual(antes, V.hash_directorio(self.sitio))                              # sitio/ intacto y sin una sola marca de demo
        self.assertTrue((self.vp / "index.html").is_file())
        self.assertEqual([], [str(x) for x in self.hallazgos()])                            # lo que se valida y se publica sigue verde
        self.assertEqual({"L1-DEMO"}, self.reglas(carpeta="sitio-vista-previa"))

    def test_salida_explicita_y_rechazos(self) -> None:
        self.generar(vista_previa=True, salida="para-el-dueno")
        self.assertTrue((self.land / "para-el-dueno" / "index.html").is_file())
        self.assertFalse(self.vp.exists() or self.sitio.exists())
        for mala in ("sitio", "../afuera", "a/b", "A_Mayus", ""):
            if mala == "":
                continue
            with self.assertRaises(ErrorValidacion, msg=mala):
                G.planificar_sitio(self.d, vista_previa=True, salida=mala, hoy=HOY)
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "prueba"}, clear=True):
            self.assertEqual(2, G.main(["--oferta", "OF-202611-02", "--raiz", str(self.tmp), "--vista-previa", "--salida", "sitio"]))
        self.assertEqual("sitio-vista-previa", G.carpeta_de_salida(True))
        self.assertEqual("sitio", G.carpeta_de_salida(False))


class PruebaDesplegarYDemo(Base):
    """``landing.desplegar``: producción rechaza cualquier demo (aunque alguien copie la vista previa a ``sitio/``) y solo publica ``sitio/``."""

    def setUp(self) -> None:
        super().setUp()
        self.generar(vista_previa=True)

    def copiar_demo_a_sitio(self) -> None:
        shutil.copytree(self.vp, self.sitio)                                               # el error humano que L1-DEMO y desplegar deben atajar

    def test_produccion_rechaza_demo_incluso_en_dry_run(self) -> None:
        self.copiar_demo_a_sitio()
        with self.assertRaises(ErrorBloqueado) as cm:
            D.desplegar(self.d, entorno="produccion", tag="t1", live=False, raiz=self.tmp)
        self.assertIn("demostración", cm.exception.mensaje)

    def test_produccion_live_rechaza_demo_aunque_haya_sello(self) -> None:
        self.copiar_demo_a_sitio()
        with self.assertRaises(ErrorBloqueado):
            D.desplegar(self.d, entorno="produccion", tag="t1", live=True, raiz=self.tmp, env={"FABRICA_ENTORNO": "produccion"})
        self.assertFalse((self.land / "_despliegues").exists())

    def test_produccion_solo_publica_sitio(self) -> None:
        with self.assertRaises(ErrorBloqueado) as cm:
            D.desplegar(self.d, entorno="produccion", tag="t1", live=False, raiz=self.tmp, carpeta="sitio-vista-previa")
        self.assertIn("solo publica 05-landing/sitio", cm.exception.mensaje)

    def test_preview_si_admite_la_demo(self) -> None:
        plan = D.desplegar(self.d, entorno="preview", tag="p1", live=True, raiz=self.tmp, carpeta="sitio-vista-previa")
        self.assertEqual("live", plan["modo"])

    def test_rollback_a_produccion_de_un_despliegue_con_demo_se_rechaza(self) -> None:
        D.desplegar(self.d, entorno="preview", tag="p1", live=True, raiz=self.tmp, carpeta="sitio-vista-previa")
        with self.assertRaises(ErrorBloqueado):
            D.rollback(self.d, tag="p1", entorno="produccion", live=True)

    def test_sitio_sin_demo_pasa_el_filtro_de_demo_en_produccion(self) -> None:
        self.generar()
        plan = D.desplegar(self.d, entorno="produccion", tag="t2", live=False, raiz=self.tmp)
        self.assertEqual("dry_run", plan["modo"])


class PruebaFormatos(unittest.TestCase):
    def test_fechas_y_numeros_por_idioma(self) -> None:
        self.assertEqual("30 listopada 2026", textos.formatear_fecha("2026-11-30", "pl-PL"))
        self.assertEqual("30 de noviembre de 2026", textos.formatear_fecha("2026-11-30", "es-ES"))
        self.assertEqual("November 30, 2026", textos.formatear_fecha("2026-11-30", "en-US"))
        self.assertEqual("1\u00a0234", textos.formatear_entero(1234, "pl-PL"))
        self.assertEqual("1.234", textos.formatear_entero(1234, "es-ES"))
        self.assertEqual("4,8", textos.formatear_decimal(4, 8, "pl-PL"))
        self.assertEqual("12–33 zł", textos.formatear_rango(1200, 3300, "PLN", "pl-PL").replace(" ", " "))
        self.assertEqual("$12.50", textos.formatear_rango(1250, None, "USD", "en-US"))

    def test_rotulos_nuevos_en_los_cuatro_idiomas(self) -> None:
        claves = {"verificada", "demo", "elige_nivel", "comparacion", "fuente", "recibes", "bonus", "estrellas"}
        for idioma in textos.IDIOMAS:
            self.assertTrue(claves <= set(textos.rotulos(idioma)), idioma)
            self.assertEqual(4, len(textos.demo_resenas(idioma)))
            self.assertTrue(all("(demo)" in r["nombre"] for r in textos.demo_resenas(idioma)))


class PruebaEstilosYPlantilla(unittest.TestCase):
    def test_css_sin_red_y_con_los_componentes(self) -> None:
        css = (SKILL / "templates" / "sitio-base" / "estilos.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"(?i)https?://|@import|javascript:")
        for clase in (".barra-superior", ".tira__carril", ".pestanas__panel", ".para-quien", ".bono-tarjeta", ".caja-oferta", ".garantia-caja", ".pasos", ".cta-bloque", ".vp-barra", ".cinta-demo"):
            self.assertIn(clase, css)
        self.assertIn("prefers-reduced-motion", css)

    def test_manifiesto_trae_los_dos_planos(self) -> None:
        m = contenido.manifiesto()
        self.assertEqual(["S01", "S04", "S08", "S06", "S07", "S09", "S16", "S11", "S10", "S15", "S12", "S13"], m["planos"]["referente"]["orden"])
        self.assertEqual(13, len(m["planos"]["clasica"]["orden"]))
        ids = {s["id"] for s in m["secciones"]}
        self.assertTrue({"S15", "S16"} <= ids)

    def test_schemas_de_la_skill_son_json_validos(self) -> None:
        for n in ("copy", "prueba_social_real"):
            json.loads((SKILL / "templates" / f"{n}.schema.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
