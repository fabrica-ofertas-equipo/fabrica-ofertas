"""Imágenes ilustrativas y de IA rotuladas, ranuras ``bump`` y ``portada-pack``, bonus en rejilla, esquema de assets, fuentes declaradas de la comparación con el mercado,
rendimiento de las imágenes (``L1-IMG-ATRIBUTOS`` y ``L1-PESO``) y la regla de testimonios de ``lint_copy.py`` (F-63).

Comando: ``.venv/bin/python -m unittest tests.landing.test_imagenes_y_fuentes``
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from engine.errores import ErrorValidacion
from landing import contenido, imagenes, textos
from landing import generar as G
from landing import validar as Val
from scripts import validar_esquemas as V
from tests.landing import test_componentes as TC

RAIZ = Path(__file__).resolve().parents[2]
SKILL = RAIZ / ".claude" / "skills" / "d5-landing-checkout"
HOY = date(2026, 11, 7)


class Base(TC.Base):
    """Fixture pl-PL en plano referente (``a_referente``) con ayudas para declarar ranuras y marcarlas."""

    def ranura(self, slot_id: str, seccion: str, *, base: str = "compra", **extra) -> None:
        """Añade (o reemplaza) una ranura APROBADA clonando ``base`` y su archivo (alt propio, sha256 real)."""
        origen = self.land / "imagenes" / f"{base}.svg"
        destino = self.land / "imagenes" / f"{slot_id}.svg"
        shutil.copyfile(origen, destino)

        def f(a):
            modelo = next(s for s in a["slots"] if s["slot_id"] == base)
            nuevo = {**modelo, "slot_id": slot_id, "seccion": seccion, "archivo": f"imagenes/{slot_id}.svg", "sha256": V.hash_archivo(destino, servido=False), "estado": "aprobado",
                     "alt": "Ilustracja okładki zestawu kart do rozmów dla par", **extra}
            a["slots"] = [s for s in a["slots"] if s["slot_id"] != slot_id] + [nuevo]
        self.editar("05-landing/assets.json", f)

    def marcar(self, ids, **campos) -> None:
        def f(a):
            for s in a["slots"]:
                if s["slot_id"] in ids:
                    s.update(campos)
        self.editar("05-landing/assets.json", f)

    def ilustrativas(self) -> None:
        # una ilustrativa va como `imagen` (no `captura_producto`, que exige ia_generado=false), con IA y rótulo de IA
        self.marcar(("muestra-principal", "muestra-1"), tipo="imagen", origen="ia", ilustrativa=True, ia_generado=True, etiqueta_ia_visible=True,
                    reemplazar_con_real_cuando_exista_producto=True)

    def reglas_l1(self, carpeta="sitio", **k) -> set[str]:
        return {h.regla for h in Val.validar_sitio(self.d, hoy=HOY, carpeta=carpeta, **k)}


# ----------------------------------------------------------------------------------------------
class PruebaRotulosDeImagen(Base):
    def test_ilustrativa_e_ia_se_rotulan_por_imagen_y_validan(self) -> None:
        self.ilustrativas()
        self.generar()
        h = self.html()
        self.assertEqual(2, h.count('data-ilustrativa="1" data-ia="1"'))
        self.assertEqual(2, len(re.findall(r'<span class="rotulo-img rotulo-img--pie" data-rotulo="ilustrativa ia" data-para="muestra-(?:principal|1)">Ilustracja poglądowa · Obraz wygenerowany z pomocą AI</span>', h)))
        self.assertEqual(set(), self.reglas_l1())

    def test_las_ilustrativas_se_publican_en_produccion_con_su_rotulo(self) -> None:           # J21: no se omite S04
        self.ilustrativas()
        self.generar()
        self.assertIn('id="muestra"', self.html())
        self.assertIn("Ilustracja poglądowa", self.html())

    def test_solo_ia_en_la_imagen_de_compra_es_una_insignia_sobre_la_imagen(self) -> None:
        self.marcar(("compra",), ia_generado=True, etiqueta_ia_visible=True)
        self.generar()
        h = self.html()
        self.assertRegex(h, r'<img class="oferta__img"[^>]*data-slot="compra" data-ia="1"')
        self.assertIn('<span class="rotulo-img" data-rotulo="ia" data-para="compra">Obraz wygenerowany z pomocą AI</span>', h)
        self.assertNotIn("Ilustracja poglądowa", h)
        self.assertEqual(set(), self.reglas_l1())

    def test_modo_grupo_un_solo_pie_por_seccion(self) -> None:
        self.ilustrativas()
        self.copy(lambda c: c.update(rotulos_imagen={"modo": "grupo"}))
        self.generar()
        h = self.html()
        seccion = re.search(r'<section class="seccion tira.*?</section>', h, re.S).group(0)
        self.assertEqual(1, seccion.count('class="rotulo-grupo"'))
        self.assertIn('data-rotulo="ilustrativa ia" data-para="grupo"', seccion)
        self.assertIn("Ilustracja poglądowa: układ i treść gotowych materiałów mogą się różnić.", seccion)
        self.assertNotIn("rotulo-img", seccion)                                              # las miniaturas ya no llevan pie propio
        self.assertEqual(2, seccion.count('data-ilustrativa="1"'))                           # pero siguen marcadas para el validador
        self.assertEqual(set(), self.reglas_l1())

    def test_texto_configurable_y_por_idioma(self) -> None:
        self.ilustrativas()
        self.copy(lambda c: c.update(rotulos_imagen={"ilustrativa": "Wizualizacja", "ia": "Obraz AI"}))
        self.generar()
        self.assertIn("Wizualizacja · Obraz AI", self.html())
        self.assertNotIn("Ilustracja poglądowa ·", self.html())
        porcentaje = {i: textos.rotulos_de_imagen(i) for i in textos.IDIOMAS}
        self.assertEqual(4, len({v["ilustrativa"] for v in porcentaje.values()}))
        self.assertEqual("Ilustración orientativa", porcentaje["es"]["ilustrativa"])
        self.assertEqual("Illustrative image", porcentaje["en"]["ilustrativa"])
        self.assertEqual("Immagine illustrativa", porcentaje["it"]["ilustrativa"])
        self.assertEqual("Obraz wygenerowany z pomocą AI", porcentaje["pl"]["ia"])
        self.assertEqual("Ilustración orientativa", textos.rotulos_de_imagen("es-ES", {"ilustrativa": "  "})["ilustrativa"])   # texto vacío: vale el del idioma

    def test_rotulo_hostil_falla_cerrado(self) -> None:
        self.copy(lambda c: c.update(rotulos_imagen={"ia": "<b>IA</b>"}))
        with self.assertRaises(ErrorValidacion):
            self.generar()

    def test_sin_marcas_no_hay_rotulos(self) -> None:
        self.generar()
        self.assertNotIn("rotulo-img", self.html())
        self.assertNotIn("data-ilustrativa", self.html())
        self.assertEqual(set(), self.reglas_l1())

    def test_validar_exige_el_rotulo_de_cada_imagen_marcada(self) -> None:
        self.ilustrativas()
        self.generar()
        ruta = self.sitio / "index.html"
        base = ruta.read_text(encoding="utf-8")
        sin_rotulos = re.sub(r'<span class="rotulo-img[^"]*"[^>]*>.*?</span>', "", base)
        ruta.write_text(sin_rotulos, encoding="utf-8")
        self.assertIn("L1-IMAGEN-ROTULO", self.reglas_l1())                                  # sin rótulo propio ni de grupo
        ruta.write_text(re.sub(r'(<span class="rotulo-img[^"]*"[^>]*>)[^<]*', r"\1", base), encoding="utf-8")
        self.assertIn("L1-IMAGEN-ROTULO", self.reglas_l1())                                  # rótulo vacío
        ruta.write_text(base.replace(' data-ilustrativa="1"', ""), encoding="utf-8")
        self.assertIn("L1-IMAGEN-ROTULO", self.reglas_l1())                                  # assets.json dice «ilustrativa» y el HTML no la señala
        ruta.write_text(base.replace(' data-ia="1"', ""), encoding="utf-8")
        self.assertIn("L1-IMAGEN-ROTULO", self.reglas_l1())                                  # idem con la etiqueta de IA
        ruta.write_text(base, encoding="utf-8")
        self.assertEqual(set(), self.reglas_l1())

    def test_un_pie_de_grupo_de_otra_seccion_no_cubre(self) -> None:
        self.ilustrativas()
        self.copy(lambda c: c.update(rotulos_imagen={"modo": "grupo"}))
        self.generar()
        ruta = self.sitio / "index.html"
        h = ruta.read_text(encoding="utf-8")
        grupo = re.search(r'<p class="rotulo-grupo".*?</p>', h, re.S).group(0)
        ruta.write_text(h.replace(grupo, "").replace("</main>", grupo + "</main>"), encoding="utf-8")   # el pie queda fuera de la sección de las imágenes
        self.assertIn("L1-IMAGEN-ROTULO", self.reglas_l1())


class PruebaAltReal(Base):
    def probar(self, alt: str, slot: str = "compra") -> str | None:
        return imagenes.comprobar_alt(slot, alt)

    def test_motivos(self) -> None:
        self.assertIsNone(self.probar("Pakiet map słownictwa i pięć dodatków w plikach PDF"))
        self.assertIn("menos de", self.probar("Okładka"))
        self.assertIn("genérico", self.probar("Ilustracja"))
        self.assertIn("genérico", self.probar("imagen del producto"))
        self.assertIn("id de la ranura", self.probar("Ilustracja poglądowa (ilustracja): muestra-1", "muestra-1"))
        self.assertIsNone(self.probar("Okładka dodatku Powtórki bez aplikacji", "bono-1"))

    def test_una_ranura_aprobada_con_alt_de_marcador_falla_cerrado(self) -> None:
        self.marcar(("muestra-1",), alt="Mapa A1 (ilustracja): muestra-1")
        with self.assertRaises(ErrorValidacion) as cm:
            self.generar()
        self.assertIn("no es un texto alternativo real", cm.exception.mensaje)
        self.marcar(("muestra-1",), alt="mapa")
        with self.assertRaises(ErrorValidacion):
            self.generar()


class PruebaBumpYPortadaPack(Base):
    def test_el_bump_lleva_su_imagen_cuando_la_ranura_esta_aprobada(self) -> None:
        self.ranura("bump", "bonus")
        self.generar()
        h = self.html()
        self.assertIn('class="tarjeta bump bump--con-imagen"', h)
        self.assertRegex(h, r'<div class="bump__img img-rotulada">\s*<img src="/imagenes/bump.svg"[^>]*data-slot="bump"')
        self.assertEqual(set(), self.reglas_l1())

    def test_sin_ranura_bump_la_tarjeta_va_como_antes(self) -> None:
        self.generar()
        self.assertNotIn("bump--con-imagen", self.html())
        self.assertNotIn("vp-marcador--bump", self.html())

    def test_bump_declarado_sin_aprobar_solo_tiene_marcador_en_vista_previa(self) -> None:
        self.ranura("bump", "bonus", estado="vacio", archivo=None, sha256=None)
        self.generar(vista_previa=True)
        self.assertIn("[vista previa: portada del bump]", self.html())
        self.generar()
        self.assertNotIn("portada del bump", self.html())

    def test_portada_pack_es_el_heroe_si_no_hay_mockup(self) -> None:
        self.ranura("portada-pack", "producto")
        _, avisos = self.generar()
        h = self.html()
        self.assertRegex(h, r'<img class="hero__img hero__img--pack" src="/imagenes/portada-pack.svg"[^>]*data-slot="portada-pack"[^>]*fetchpriority="high"')
        self.assertNotIn('class="portada"', h)                                              # antes que la portada tipográfica
        self.assertNotIn("caja-oferta__pack", h)                                            # y sin repetirla junto al precio
        self.assertTrue(any("portada-pack" in a for a in avisos))
        self.assertEqual(set(), self.reglas_l1())

    def test_con_heroe_y_compra_la_portada_pack_es_una_miniatura_junto_a_que_recibes(self) -> None:
        self.ranura("hero", "hero")
        self.ranura("portada-pack", "producto")
        self.generar()
        h = self.html()
        self.assertNotIn("hero__img--pack", h)
        self.assertRegex(h, r'<div class="caja-oferta__pack img-rotulada">\s*<img src="/imagenes/portada-pack.svg"')
        self.assertEqual(1, h.count('fetchpriority="high"'))                                 # solo el héroe
        self.assertEqual(set(), self.reglas_l1())

    def test_sin_escena_de_compra_la_portada_pack_es_la_imagen_principal_del_precio(self) -> None:
        self.marcar(("compra",), estado="omitida", archivo=None, sha256=None, alt="")
        self.ranura("portada-pack", "producto")
        self.generar()
        self.assertRegex(self.html(), r'<img class="oferta__img" src="/imagenes/portada-pack.svg"')
        self.assertNotIn("caja-oferta__pack", self.html())


class PruebaBonusEnRejilla(unittest.TestCase):
    def test_css_2_y_3_columnas_con_portada_razonable_y_seccion_oscura(self) -> None:
        css = (SKILL / "templates" / "sitio-base" / "estilos.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.bonos-rejilla\{display:flex;flex-wrap:wrap;justify-content:center")
        self.assertIn("@media (min-width:47.5rem){.bono-tarjeta{flex:0 1 calc((100% - 1rem) / 2)}}", css)
        self.assertIn("@media (min-width:68rem){.bono-tarjeta{flex:0 1 calc((100% - 2rem) / 3)}}", css)
        m = re.search(r"\.bono-tarjeta__portada img\{width:100%;max-width:([0-9.]+)rem", css)
        self.assertLessEqual(float(m.group(1)), 20)                                          # la portada ya no ocupa una fila de 500 px
        sec = (SKILL / "templates" / "sitio-base" / "secciones" / "s09-bonus.html").read_text(encoding="utf-8")
        self.assertIn("seccion bonus tono-{{tono}}", sec)
        self.assertEqual("oscuro", contenido.manifiesto()["planos"]["referente"]["ajustes"]["S09"]["tono"])


class PruebaEsquemaDeAssets(Base):
    def validar(self, f) -> None:
        a = json.loads((self.land / "assets.json").read_text(encoding="utf-8"))
        f(a)
        contenido._validar_artefacto("assets", a)

    def test_ratio_1_91_y_productor_de_kie(self) -> None:
        def f(a):
            og = next(s for s in a["slots"] if s["slot_id"] == "og")
            og.update(ratio="1.91:1", ancho_px=1200, alto_px=630, productor="kie", herramienta="Kie (nano-banana-pro) + Chrome", ia_generado=True, etiqueta_ia_visible=True)
        self.validar(f)
        self.validar(lambda a: a["slots"][0].update(productor="ranuras_kie"))
        for malo in ({"ratio": "2:1"}, {"productor": "midjourney"}):
            with self.assertRaises(ErrorValidacion, msg=str(malo)):
                self.validar(lambda a, m=malo: a["slots"][0].update(m))
        self.assertEqual((1200, 630), imagenes._RATIOS["1.91:1"])

    def test_og_1200x630_con_ratio_1_91_genera(self) -> None:
        self.marcar(("og",), ratio="1.91:1", ancho_px=1200, alto_px=630, productor="kie", herramienta="Kie + Chrome")
        self.generar()
        self.assertIn('property="og:image"', self.html())


# ----------------------------------------------------------------------------------------------
class PruebaFuentesDeMercado(Base):
    TEXTO = "Kurs wideo z mapami myśli. Cena katalogowa: 129,00 zł."

    def declarar(self, *, monto_curso=12900, fecha_curso="2026-11-07", texto=None, hash_malo=False, moneda=None, nombre_curso="kursy-b.pl", extra=None) -> Path:
        (self.land / "fuentes").mkdir(exist_ok=True)
        archivo = self.land / "fuentes" / "kursy-b.txt"
        archivo.write_text(texto or self.TEXTO, encoding="utf-8")
        sha = "sha256:" + hashlib.sha256(archivo.read_bytes()).hexdigest()
        if hash_malo:
            sha = "sha256:" + "0" * 64
        curso = {"fuente": nombre_curso, "archivo": "fuentes/kursy-b.txt", "sha256": sha, "fecha": fecha_curso, "cifras": [{"etiqueta": "Kurs wideo", "monto": monto_curso}]}
        if moneda:
            curso["moneda"] = moneda
        doc = {"schema_version": "0.1.0", "oferta_id": "OF-202611-02", "fuentes": [
            {"fuente": "tienda-a.pl", "url": "https://tienda-a.pl/zestawy", "fecha": "2026-11-06", "cifras": [{"monto": 1200}, {"monto": 3300}]}, curso, *(extra or [])]}
        ruta = self.land / "fuentes_mercado.json"
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        return ruta

    def test_con_fuentes_declaradas_la_comparacion_se_contrasta_y_valida_tambien_en_produccion(self) -> None:
        self.declarar()
        _, avisos = self.generar()
        self.assertFalse(any("no se contrastaron" in a for a in avisos))
        self.assertIn('data-fecha="2026-11-07" data-desde="12900" data-hasta="12900"', self.html())
        self.assertIn('data-desde="1200" data-hasta="3300"', self.html())
        self.assertEqual([], [str(x) for x in Val.validar_sitio(self.d, hoy=HOY, produccion=True)])

    def test_sin_fuentes_declaradas_avisa_y_solo_producion_lo_exige(self) -> None:
        _, avisos = self.generar()
        self.assertTrue(any("no se contrastaron con una fuente declarada" in a for a in avisos))
        self.assertEqual(set(), {h.regla for h in Val.validar_sitio(self.d, hoy=HOY)})
        self.assertIn("L1-COMPARACION-FUENTE", {h.regla for h in Val.validar_sitio(self.d, hoy=HOY, produccion=True)})

    def falla(self, fragmento: str) -> None:
        with self.assertRaises(ErrorValidacion) as cm:
            self.generar()
        self.assertIn(fragmento, cm.exception.mensaje)

    def test_una_cifra_que_las_fuentes_no_respaldan_detiene_la_generacion(self) -> None:
        self.declarar()
        self.copy(lambda c: c["secciones"]["S16"]["filas"][0].update(hasta=3400))
        self.falla("hasta=3400 no figura entre las cifras")
        self.copy(lambda c: c["secciones"]["S16"]["filas"][0].update(hasta=3300, desde=1100))
        self.falla("desde=1100 no figura")

    def test_fecha_fuente_o_moneda_distintas_no_respaldan(self) -> None:
        self.declarar(fecha_curso="2026-11-01")
        self.falla("no está declarada con fecha 2026-11-07")
        self.declarar(nombre_curso="otra-tienda.pl")
        self.falla("'kursy-b.pl' no está declarada")
        self.declarar(moneda="EUR")
        self.falla("declara EUR")

    def test_el_archivo_capturado_se_verifica_por_hash_y_por_cifra(self) -> None:
        self.declarar(hash_malo=True)
        self.falla("el sha256 del archivo capturado")
        self.declarar(texto="Kurs wideo, cena: 99,00 zł")
        self.falla("no aparece en su archivo capturado")
        self.declarar(texto="Kurs: 1129,00 zł i 12,90 zł")                                  # 129 solo como parte de otro número: no cuenta
        self.falla("no aparece en su archivo capturado")

    def test_archivo_fuera_de_05_landing_o_inexistente(self) -> None:
        ruta = self.declarar()
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        doc["fuentes"][1]["archivo"] = "fuentes/no-existe.txt"
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        self.falla("no existe dentro de 05-landing/")
        doc["fuentes"][1]["archivo"] = "../../secreto.txt"
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):                                            # el esquema ni siquiera admite «..»
            self.generar()

    def test_esquema_de_fuentes_exige_url_o_archivo_con_sha(self) -> None:
        ruta = self.declarar()
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        del doc["fuentes"][0]["url"]
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            self.generar()

    def test_fuentes_de_otra_oferta_fallan(self) -> None:
        ruta = self.declarar()
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        doc["oferta_id"] = "OF-202611-99"
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            self.generar()

    def test_validar_contrasta_el_html_y_la_vigencia_de_30_dias(self) -> None:
        self.declarar()
        self.generar()
        self.assertEqual(set(), {h.regla for h in Val.validar_sitio(self.d, hoy=HOY, produccion=True)})
        self.assertIn("L1-COMPARACION-FUENTE", {h.regla for h in Val.validar_sitio(self.d, hoy=date(2026, 12, 20), produccion=True)})   # lectura de hace > 30 días
        self.assertEqual(set(), {h.regla for h in Val.validar_sitio(self.d, hoy=date(2026, 12, 20))})                                   # fuera de producción no caduca
        ruta = self.sitio / "index.html"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace('data-desde="12900" data-hasta="12900"', 'data-desde="9900" data-hasta="9900"'), encoding="utf-8")
        self.assertIn("L1-COMPARACION-FUENTE", {h.regla for h in Val.validar_sitio(self.d, hoy=HOY)})                                   # el HTML no coincide con la fuente


# ----------------------------------------------------------------------------------------------
class PruebaRendimientoDeImagenes(Base):
    def setUp(self) -> None:
        super().setUp()
        self.ranura("hero", "hero")
        self.ranura("bump", "bonus")
        self.generar()
        self.ruta = self.sitio / "index.html"
        self.base = self.ruta.read_text(encoding="utf-8")

    def reglas_con(self, html: str) -> set[str]:
        self.ruta.write_text(html, encoding="utf-8")
        return self.reglas_l1()

    def test_lo_generado_cumple_atributos_y_pesos(self) -> None:
        self.assertEqual(set(), self.reglas_l1())
        for p in self.sitio.rglob("*.html"):
            t = p.read_text(encoding="utf-8")
            self.assertLessEqual(t.count('fetchpriority="high"'), 1, p.name)                 # solo el héroe
            for img in re.findall(r"<img[^>]+>", t):
                self.assertRegex(img, r'width="\d+"')
                self.assertRegex(img, r'height="\d+"')
                if 'class="hero__img' in img:
                    self.assertIn('fetchpriority="high"', img)
                    self.assertNotIn('loading="lazy"', img)
                else:
                    self.assertIn('loading="lazy"', img)

    def test_el_heroe_va_eager_y_el_resto_lazy(self) -> None:
        self.assertIn("L1-IMG-ATRIBUTOS", self.reglas_con(re.sub(r'(<img class="hero__img[^>]*?) fetchpriority="high"', r"\1", self.base)))
        self.assertIn("L1-IMG-ATRIBUTOS", self.reglas_con(re.sub(r'(<img class="hero__img[^>]*?)( decoding)', r'\1 loading="lazy"\2', self.base)))
        self.assertIn("L1-IMG-ATRIBUTOS", self.reglas_con(self.base.replace('loading="lazy" decoding="async">', 'decoding="async">', 1)))         # una imagen bajo el pliegue sin lazy
        self.assertIn("L1-IMG-ATRIBUTOS", self.reglas_con(self.base.replace('loading="lazy" decoding="async">', 'fetchpriority="high" decoding="async">', 1)))  # alta prioridad fuera del héroe

    def test_sin_width_height_o_alt(self) -> None:
        self.assertIn("L1-IMG-ATRIBUTOS", self.reglas_con(re.sub(r'(<img class="oferta__img"[^>]*?) width="\d+"', r"\1", self.base)))
        self.assertIn("L1-IMG-ATRIBUTOS", self.reglas_con(re.sub(r'(<img class="oferta__img"[^>]*?) height="\d+"', r"\1", self.base)))
        self.assertIn("L1-IMG-ATRIBUTOS", self.reglas_con(re.sub(r'(<img class="oferta__img"[^>]*?) alt="[^"]*"', r' alt=""\1', self.base)))

    def test_pesos(self) -> None:
        self.ruta.write_text(self.base, encoding="utf-8")
        self.assertEqual(set(), self.reglas_l1())
        (self.sitio / "imagenes" / "bump.svg").write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'>" + b" " * (200 * 1024) + b"</svg>")      # la ranura admite 150 KB
        self.assertIn("L1-PESO", self.reglas_l1())
        shutil.copyfile(self.land / "imagenes" / "bump.svg", self.sitio / "imagenes" / "bump.svg")
        css = self.sitio / "css" / "estilos.css"
        css.write_text(css.read_text(encoding="utf-8") + "/*" + "x" * (Val.PESO_CSS_MAX_KB * 1024) + "*/", encoding="utf-8")
        self.assertIn("L1-PESO", self.reglas_l1())
        css.write_text(css.read_text(encoding="utf-8").split("/*xxx")[0], encoding="utf-8")
        self.assertIn("L1-PESO", self.reglas_con(self.base.replace("</main>", "<!-- " + "x" * (Val.PESO_HTML_MAX_KB * 1024) + " --></main>")))
        self.ruta.write_text(self.base, encoding="utf-8")
        with mock.patch.object(Val, "PESO_IMAGENES_MAX_KB", 1):                              # presupuesto de imágenes de la página
            self.assertIn("L1-PESO", self.reglas_l1())

    def test_el_peso_de_las_imagenes_se_lee_de_parametros(self) -> None:
        self.ruta.write_text(self.base, encoding="utf-8")
        (self.tmp / "empresa").mkdir(exist_ok=True)
        (self.tmp / "empresa" / "parametros.yaml").write_text("grupos:\n  landing:\n    peso_landing_max_kb:\n      valor: 1\n", encoding="utf-8")
        self.assertIn("L1-PESO", self.reglas_l1())


# ----------------------------------------------------------------------------------------------
class PruebaLintTestimonios(unittest.TestCase):
    """F-63: una frase honesta sobre reseñas que aún no existen no es un testimonio; una afirmación sí."""

    @classmethod
    def setUpClass(cls) -> None:
        espec = importlib.util.spec_from_file_location("_lint_copy_test", SKILL / "scripts" / "lint_copy.py")
        cls.L = importlib.util.module_from_spec(espec)
        espec.loader.exec_module(cls.L)

    def marca(self, texto: str) -> bool:
        return self.L.menciona_testimonio(self.L.plano(texto)) is not None

    def test_frases_honestas_no_se_marcan(self) -> None:
        for t in ("Opinie pojawią się, gdy będą prawdziwe.", "Brak opinii na razie.", "Aún no hay reseñas: las mostraremos cuando sean reales",
                  "No reviews yet", "Quando ci saranno recensioni reali le mostreremo", "Opinie pojawią się dopiero po pierwszych zakupach; nie publikujemy wymyślonych opinii.",
                  "Todavía no hay reseñas de compradores."):
            self.assertFalse(self.marca(t), t)

    def test_afirmaciones_siguen_marcadas(self) -> None:
        for t in ("Opinie klientów: 4,8", "Zobacz opinie zadowolonych klientów. Brak ukrytych kosztów.", "Lee las reseñas de nuestros clientes", "Read our customer reviews",
                  "Brak opinii. Zobacz opinie klientów!", "Leggi le recensioni dei nostri clienti", "Testimonios de quienes ya lo usan"):
            self.assertTrue(self.marca(t), t)

    def test_en_el_linter_completo(self) -> None:
        copy = json.loads((RAIZ / "tests" / "fixtures" / "landing" / "oferta_pl_relaciones" / "05-landing" / "copy.json").read_text(encoding="utf-8"))
        oferta = json.loads((RAIZ / "tests" / "fixtures" / "landing" / "oferta_pl_relaciones" / "03-oferta" / "oferta.json").read_text(encoding="utf-8"))
        copy["secciones"]["S08"]["bloques"][0]["texto"] = "Opinie pojawią się, gdy będą prawdziwe."
        self.assertFalse(any(x["regla"] == "D5-COPY-TESTIMONIO" for x in self.L.linter(copy, oferta)))
        copy["secciones"]["S08"]["bloques"][0]["texto"] = "Zobacz opinie klientów."
        self.assertTrue(any(x["regla"] == "D5-COPY-TESTIMONIO" for x in self.L.linter(copy, oferta)))


if __name__ == "__main__":
    unittest.main()
