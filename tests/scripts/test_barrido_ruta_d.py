"""Pruebas de scripts/modelado/barrido/ruta_d.py: Chrome limpio sobre páginas de BÚSQUEDA de la Biblioteca, CON FRENOS.

Sin red ni Chrome real: la sesión de Chrome, el reloj y el sueño se inyectan; `socket.socket` está bloqueado. Lo que se
prueba: que los frenos de captura.py son los de verdad (no copias), que un bloqueo corta y NO se reintenta, que solo
se abre la Biblioteca, que los topes salen de parámetros y que la salida respeta el contrato del crudo.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts.modelado import captura as ca
from scripts.modelado import puntaje_modelar as pm
from scripts.modelado.barrido import comun
from scripts.modelado.barrido import ruta_d as rd
from scripts.modelado.enlaces import ErrorExterno

FIX = Path(__file__).resolve().parents[1] / "fixtures"
FIX_RD = FIX / "barrido" / "ruta_d"
INICIO = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)
PREFIJO = "https://www.facebook.com/ads/library/?"
RELLENO = "Meta Ad Library Ad Library Report Ad Library API Active ads Spain " * 4


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------

def tarjeta(n, *, pagina=None, nombre="Pagina Ejemplo", fecha="Nov 5, 2026", titulo="Titulo ejemplo", texto="Texto del anuncio"):
    """Una tarjeta de resultados mínima con el id `3000000000000000 + n`."""
    ident = 3_000_000_000_000_000 + n
    pagina = pagina if pagina is not None else 1_100_000_000_000_000 + n
    return (f'<div class="card"><div><span>Library ID:</span> <span>{ident}</span></div>'
            f'<div>Started running on {fecha}</div>'
            f'<a href="https://www.facebook.com/{pagina}/">{nombre}</a><div>{texto} {n}</div>'
            f'<div role="heading">{titulo} {n}</div></div>')


def pagina(desde=0, hasta=3, *, cabecera="~932 results", extra="", **kw):
    """DOM de una página con las tarjetas desde..hasta-1 (el código de la página nombra «captcha» y «log in to continue»)."""
    tarjetas = "".join(tarjeta(n, **kw) for n in range(desde, hasta))
    return (f"<html><head><title>Ad Library</title><script>var x='arkose_captcha /checkpoint/block/ log in to continue';</script>"
            f"</head><body><div role='main'>{RELLENO} {cabecera} {extra}<div class='lista'>{tarjetas}</div></div></body></html>")


def paso(dom, url_final=PREFIJO + "q=x", estados=()):
    return {"dom": dom, "url_final": url_final, "estados_http": list(estados)}


class Reloj:
    """Reloj falso que avanza cuando alguien duerme."""

    def __init__(self, inicio=INICIO):
        self.ahora = inicio
        self.dormidas: list[float] = []

    def __call__(self):
        return self.ahora

    def dormir(self, segundos):
        self.dormidas.append(segundos)
        self.ahora += timedelta(seconds=segundos)


class SesionFalsa:
    """Sesión de Chrome falsa: entrega los pasos en orden (o lanza la excepción que toque) y registra qué se le pidió."""

    def __init__(self, *pasos, antes=None):
        self.pasos = list(pasos)
        self.llamadas: list[tuple] = []
        self.cerrada = False
        self.antes = antes

    def _siguiente(self):
        if self.antes:
            self.antes(len(self.llamadas))
        resultado = self.pasos[min(len(self.llamadas), len(self.pasos)) - 1]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    def navegar(self, url):
        self.llamadas.append(("navegar", url))
        return self._siguiente()

    def desplazar(self):
        self.llamadas.append(("desplazar",))
        return self._siguiente()

    def cerrar(self):
        self.cerrada = True


class Fabrica:
    def __init__(self, sesion):
        self.sesion, self.veces = sesion, 0

    def __call__(self, p, pr):
        self.veces += 1
        return self.sesion


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = pm.cargar_parametros(FIX / "modelado" / "parametros.yaml")
        cls.pr = rd.cargar_parametros_ruta_d(FIX_RD / "parametros_ruta_d.yaml")

    def setUp(self):
        parche = mock.patch("socket.socket", side_effect=AssertionError("las pruebas no usan red"))
        parche.start()
        self.addCleanup(parche.stop)
        entorno = mock.patch.dict(os.environ)               # cada prueba parte sin FABRICA_ENTORNO ni FABRICA_RAIZ
        entorno.start()
        self.addCleanup(entorno.stop)
        os.environ.pop("FABRICA_ENTORNO", None)
        os.environ.pop("FABRICA_RAIZ", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.estado = Path(self.tmp.name) / "captura"
        self.raiz = Path(self.tmp.name) / "raiz"
        self.reloj = Reloj()

    def barrer(self, sesion, qid="es-prueba", *, p=None, pr=None, fabrica=None, **kw):
        fabrica = fabrica or Fabrica(sesion)
        argumentos = dict(frase="acceso inmediato en PDF", pais="ES", p=p or self.p, pr=pr or self.pr,
                          estado_dir=self.estado, raiz=self.raiz, abrir_sesion=fabrica, reloj=self.reloj,
                          dormir=self.reloj.dormir)
        argumentos.update(kw)
        return rd.barrer("2026-11-06-a", qid, **argumentos)

    def capturas(self):
        ruta = self.estado / "capturas.jsonl"
        return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()] if ruta.exists() else []

    def crudo_dir(self):
        return self.raiz / "empresa" / "barrido" / "crudo" / "2026-11-06-a"

    def poner_freno_a_mano(self):
        self.estado.mkdir(parents=True, exist_ok=True)
        (self.estado / "freno.json").write_text(json.dumps({"ts": "2026-11-05T00:00:00Z", "motivo": "x"}), encoding="utf-8")


# ---------------------------------------------------------------------------
# Parámetros propios
# ---------------------------------------------------------------------------

class PruebaParametros(Base):
    def test_la_propuesta_del_repositorio_carga_y_todo_es_entero(self):
        pr = rd.cargar_parametros_ruta_d()
        self.assertEqual(set(pr), set(rd.CLAVES_RUTA_D))
        self.assertTrue(all(isinstance(v, int) and not isinstance(v, bool) and v >= 1 for v in pr.values()))

    def _con(self, reemplazo):
        origen = (FIX_RD / "parametros_ruta_d.yaml").read_text(encoding="utf-8")
        destino = Path(self.tmp.name) / "pr.yaml"
        destino.write_text(reemplazo(origen), encoding="utf-8")
        return destino

    def test_falta_un_parametro_falla_cerrado(self):
        ruta = self._con(lambda t: t.replace("ruta_d_max_busquedas_por_dia", "otro_nombre"))
        with self.assertRaises(pm.ErrorLimite):
            rd.cargar_parametros_ruta_d(ruta)

    def test_sin_archivo_falla_cerrado(self):
        with self.assertRaises(pm.ErrorLimite):
            rd.cargar_parametros_ruta_d(Path(self.tmp.name) / "no_existe.yaml")

    def test_valor_fuera_de_rango_o_de_tipo_falla_cerrado(self):
        with self.assertRaises(pm.ErrorLimite):
            rd.cargar_parametros_ruta_d(self._con(lambda t: t.replace("valor: 5\n      unidad: desplazamientos", "valor: 99\n      unidad: desplazamientos", 1)))
        for malo in ('"5"', "2.5", "0", "true"):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorValidacion):
                rd.cargar_parametros_ruta_d(self._con(
                    lambda t: t.replace("valor: 5\n      unidad: desplazamientos", f"valor: {malo}\n      unidad: desplazamientos", 1)))

    def test_el_parametro_compartido_que_falta_tambien_falla_cerrado(self):
        p = dict(self.p)
        del p["modelado_captura_pausa_seg"]
        sesion = SesionFalsa(paso(pagina()))
        with self.assertRaises(pm.ErrorLimite):
            self.barrer(sesion, p=p)
        self.assertEqual(sesion.llamadas, [])


# ---------------------------------------------------------------------------
# Direcciones: solo la Biblioteca, por la lista blanca de captura.py
# ---------------------------------------------------------------------------

class PruebaDirecciones(Base):
    def test_la_url_es_la_de_captura_y_apunta_a_la_biblioteca(self):
        url = rd.url_busqueda("acceso inmediato en PDF", "ES")
        self.assertEqual(url, ca.construir_url_busqueda("acceso inmediato en PDF", "ES"))
        self.assertTrue(url.startswith("https://www.facebook.com/ads/library/?"))
        self.assertIn("ad_type=all", url)
        self.assertIn("active_status=active", url)
        self.assertIn("country=ES", url)
        self.assertIn("q=acceso%20inmediato%20en%20PDF", url)

    def test_por_pagina(self):
        url = rd.url_busqueda(pais="ALL", pagina_id=1100000000000001)
        self.assertIn("view_all_page_id=1100000000000001", url)

    def test_rechaza_cualquier_otra_cosa_que_no_sea_la_biblioteca(self):
        buena = rd.url_busqueda("hola", "ES")
        for malo in ("https://evil.com/ads/library/?" + buena.split("?")[1],
                     buena.replace("https://", "http://"),
                     buena.replace("www.facebook.com", "m.facebook.com"),
                     buena.replace("www.facebook.com", "www.facebook.com.evil.com"),
                     buena.replace("www.facebook.com", "user:pass@www.facebook.com"),
                     buena.replace("www.facebook.com", "www.facebook.com:8443"),
                     buena.replace("/ads/library/", "/login/"),
                     buena + "#x", buena + "&access_token=abc", buena + "&id=1234567890",
                     buena.replace("ad_type=all", "ad_type=political_and_issue_ads"),
                     "https://www.facebook.com/", "file:///etc/passwd", "", "no es una url"):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorValidacion):
                rd.exigir_url_canonica(malo)

    def test_una_url_valida_pero_no_canonica_tampoco_pasa_por_el_driver(self):
        buena = rd.url_busqueda("hola", "ES")
        desordenada = PREFIJO + "&".join(reversed(buena.split("?")[1].split("&")))
        self.assertNotEqual(desordenada, buena)
        with self.assertRaises(pm.ErrorValidacion):
            rd.exigir_url_canonica(desordenada)
        self.assertEqual(rd.exigir_url_canonica(buena), buena)

    def test_parametros_invalidos_no_abren_nada(self):
        for kw in (dict(pais="es"), dict(pais="ESP"), dict(frase=""), dict(frase="a" * (ca.MAX_FRASE + 1)),
                   dict(frase="x\ny"), dict(estado="todos")):
            sesion = SesionFalsa(paso(pagina()))
            fabrica = Fabrica(sesion)
            with self.subTest(kw=kw), self.assertRaises(pm.ErrorValidacion):
                self.barrer(sesion, fabrica=fabrica, **kw)
            self.assertEqual((fabrica.veces, sesion.llamadas), (0, []))

    def test_ids_de_corrida_y_qid_invalidos_no_abren_nada(self):
        sesion = SesionFalsa(paso(pagina()))
        for corrida, qid in (("../x", "ok"), ("2026-11-06", "ok"), ("2026-11-06-a", "../x"), ("2026-11-06-a", "Mayus"),
                             ("2026-11-06-a", "")):
            with self.subTest(corrida=corrida, qid=qid), self.assertRaises(pm.ErrorValidacion):
                rd.barrer(corrida, qid, frase="hola", pais="ES", p=self.p, pr=self.pr, estado_dir=self.estado,
                          raiz=self.raiz, abrir_sesion=Fabrica(sesion))
        self.assertEqual(sesion.llamadas, [])

    def test_a_la_sesion_solo_llega_la_url_de_la_biblioteca(self):
        sesion = SesionFalsa(paso(pagina(0, 3)), paso(pagina(0, 3)))
        self.barrer(sesion, frase="¿Qué es esto? &q=otra&id=1 #x ../../", max_desplazamientos=1)
        urls = [c[1] for c in sesion.llamadas if c[0] == "navegar"]
        self.assertEqual(len(urls), 1)
        self.assertEqual(rd.exigir_url_canonica(urls[0]), urls[0])
        self.assertTrue(urls[0].startswith(PREFIJO))

    def test_los_estados_son_los_de_captura_no_copias(self):
        self.assertIs(rd.ca, ca)
        for nombre in ("verificar_freno", "_poner_freno", "_respetar_cupo_y_ritmo", "_anotar", "_leer_capturas", "_iso",
                       "_momento", "construir_url_busqueda", "normalizar_busqueda", "FRASES_BLOQUEO", "ESTADOS_BUSQUEDA"):
            self.assertTrue(hasattr(ca, nombre), nombre)
        for propio in ("verificar_freno", "_poner_freno", "_respetar_cupo_y_ritmo", "_anotar", "FRASES_BLOQUEO"):
            self.assertFalse(hasattr(rd, propio), f"{propio} no debe estar copiado en ruta_d")
        with mock.patch.object(ca, "FRASES_BLOQUEO", ca.FRASES_BLOQUEO + ("frase nueva de captura",)):
            self.assertIn("frase nueva de captura", rd.frases_bloqueo())


# ---------------------------------------------------------------------------
# Extracción del DOM de resultados
# ---------------------------------------------------------------------------

class PruebaExtraccion(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dom = (FIX_RD / "dom_busqueda_sintetico.html").read_text(encoding="utf-8")

    def extraer(self, dom=None):
        return rd.extraer_anuncios(dom if dom is not None else self.dom, self.pr)

    def test_saca_los_cinco_anuncios_en_orden_con_sus_campos(self):
        ads, _ = self.extraer()
        self.assertEqual([a["id"] for a in ads], [f"200000000000000{i}" for i in range(1, 6)])
        self.assertEqual([a["page_id"] for a in ads], [1100000000000001, 1100000000000001, 1100000000000003, None, 1100000000000005])
        self.assertEqual([a["page_name"] for a in ads], ["Estudio Ejemplo Uno", "Estudio Ejemplo Uno", "Atril Ejemplo", "Corpo Sem Dor", "Oferta Rara"])
        self.assertEqual(ads[3]["page_vanity"], "corposemdor")

    def test_fechas_en_epoch_de_los_tres_formatos_y_sin_inventar(self):
        ads, _ = self.extraer()
        esperado = [datetime(2026, 11, d, tzinfo=timezone.utc).timestamp() for d in (5, 5, 3)]
        self.assertEqual([a["inicio_epoch"] for a in ads[:3]], [int(x) for x in esperado])
        self.assertEqual(ads[4]["inicio_epoch"], int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()))
        self.assertIsNone(ads[3]["inicio_epoch"])        # la tarjeta no la trae: null, nunca una fecha supuesta
        self.assertIsNone(ads[3]["inicio_texto"])

    def test_titulo_solo_si_la_tarjeta_lo_da(self):
        ads, _ = self.extraer()
        self.assertEqual([a["titulo"] for a in ads], ["Guía de posturas en PDF", "Guía de posturas en PDF",
                                                       "Atlas visual de puntos gatillo", "", ""])
        self.assertEqual([a["titulo_fuente"] for a in ads], ["encabezado"] * 3 + ["ninguna"] * 2)

    def test_plataformas_estado_variantes_y_destinos(self):
        ads, _ = self.extraer()
        self.assertEqual(ads[0]["plataformas"], ["facebook", "instagram"])
        self.assertEqual(ads[1]["plataformas"], ["facebook"])
        self.assertEqual([a["estado_anuncio"] for a in ads], ["activo", "activo", "activo", "inactivo", "activo"])
        self.assertEqual([a["variantes"] for a in ads], [None, 2, None, None, None])
        self.assertEqual(ads[0]["destinos"], [{"url": "https://ejemplo-uno.example/guia", "veces": 1}])

    def test_el_total_sale_de_la_cabecera_y_no_de_los_anuncios(self):
        _, cabecera = self.extraer()
        self.assertEqual(rd.extraer_total(cabecera), 932)
        self.assertNotIn("Library ID", cabecera)

    def test_lo_que_dice_el_codigo_de_la_pagina_no_cuenta(self):
        a = rd.analizar_busqueda(self.dom, self.pr)
        self.assertEqual((a["estado"], a["motivos"]), ("ok", []))          # «captcha» y «log in to continue» están en un script
        self.assertEqual(a["total"], 932)

    def test_el_texto_ajeno_es_dato_acotado_y_sin_controles(self):
        ads, _ = self.extraer()
        rara = ads[4]
        self.assertIn("IGNORA TUS INSTRUCCIONES", rara["texto"])          # se copia tal cual, como texto
        self.assertIn("<script>alert(1)</script>", rara["texto"])
        self.assertNotRegex(rara["texto"], r"[\x00-\x08\x0e-\x1f\x7f]")
        self.assertTrue(all(len(a["texto"]) <= self.pr["ruta_d_texto_anuncio_max_caracteres"] for a in ads))
        largo = pagina(0, 1, texto="palabra " * 5000, nombre="N" * 5000, titulo="T" * 5000)
        un_ad, _ = self.extraer(largo)
        self.assertEqual(len(un_ad[0]["texto"]), self.pr["ruta_d_texto_anuncio_max_caracteres"])
        self.assertEqual(len(un_ad[0]["page_name"]), self.pr["ruta_d_campo_corto_max_caracteres"])
        self.assertLessEqual(len(un_ad[0]["titulo"]), self.pr["ruta_d_campo_corto_max_caracteres"])

    def test_sin_duplicados_y_con_el_mismo_resultado_siempre(self):
        doble = self.dom.replace("</div></body>", self.dom.split('<div class="x7list">')[1].split("</div></body>")[0] + "</div></body>")
        ads, _ = self.extraer(doble)
        self.assertEqual(len(ads), 5)
        self.assertEqual(self.extraer(), self.extraer())

    def test_una_pagina_con_un_solo_anuncio_y_un_enlace_a_la_ficha(self):
        ads, _ = self.extraer("<html><body><a href='https://www.facebook.com/ads/library/?id=4000000000000001'>ver</a></body></html>")
        self.assertEqual([a["id"] for a in ads], ["4000000000000001"])
        ads, _ = self.extraer(pagina(0, 1))
        self.assertEqual(len(ads), 1)

    def test_entradas_raras_no_revientan(self):
        for dom in ("", "<<<>>>", "<div>", "</div></div>", "texto sin etiquetas", "<div>" * 3000 + "Library ID: 1234567890123" + "</div>" * 3000):
            with self.subTest(dom=dom[:20]):
                self.assertIsInstance(self.extraer(dom)[0], list)

    def test_ids_con_largo_fuera_del_formato_no_son_anuncios(self):
        ads, _ = self.extraer("<div>Library ID: 12</div><div>Library ID: 123456789012345678901234</div>")
        self.assertEqual(ads, [])

    def test_parsear_fecha(self):
        d = lambda y, m, dia: int(datetime(y, m, dia, tzinfo=timezone.utc).timestamp())  # noqa: E731
        casos = {"Nov 5, 2026": d(2026, 11, 5), "November 5, 2026": d(2026, 11, 5), "5 Nov 2026": d(2026, 11, 5),
                 "5 nov. 2026": d(2026, 11, 5), "5 de noviembre de 2026": d(2026, 11, 5), "1 de enero de 2026": d(2026, 1, 1),
                 "2026-11-05": d(2026, 11, 5), "3 dez 2026": d(2026, 12, 3), "Sept 3, 2026": d(2026, 9, 3)}
        for texto, epoch in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(rd.parsear_fecha(texto)[0], epoch)
        for malo in ("31 Feb 2026", "hola", "", "13/13/2026", "Xyz 5, 2026", "5 Nov"):
            with self.subTest(malo=malo):
                self.assertIsNone(rd.parsear_fecha(malo))

    def test_extraer_total(self):
        casos = {"~932 results": 932, "1,234 results": 1234, "1.234 resultados": 1234, "about 50 results": 50,
                 "+1.200.000 resultados": 1200000, "sin total": None, "5 ads use this creative": None, "": None}
        for texto, total in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(rd.extraer_total(texto), total)

    def test_fusionar_es_idempotente_y_completa_campos_vacios(self):
        acumulado: dict = {}
        a = {"id": "1", "titulo": "", "inicio_epoch": None, "plataformas": []}
        b = {"id": "1", "titulo": "T", "inicio_epoch": 5, "plataformas": ["facebook"]}
        self.assertEqual(rd.fusionar_anuncios(acumulado, [a]), 1)
        self.assertEqual(rd.fusionar_anuncios(acumulado, [b]), 0)
        self.assertEqual(acumulado["1"], {"id": "1", "titulo": "T", "inicio_epoch": 5, "plataformas": ["facebook"]})
        copia = json.loads(json.dumps(acumulado))
        rd.fusionar_anuncios(acumulado, [a, b])
        self.assertEqual(acumulado, copia)


class PruebaFixtureDeLaVisitaDeSondeo(Base):
    """El DOM REAL de la visita de sondeo (2026-11-06), recortado y anonimizado: lo que Meta sirve sin sesión."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dom = (FIX_RD / "dom_busqueda_sondeo_recortado.html").read_text(encoding="utf-8")

    def test_extrae_los_seis_anuncios_con_los_campos_que_da_la_web(self):
        ads, cabecera = rd.extraer_anuncios(self.dom, self.pr)
        self.assertEqual([a["id"] for a in ads], [f"200000000000000{i}" for i in range(1, 7)])
        self.assertEqual(rd.extraer_total(cabecera), 52)                              # «~52 resultados»
        self.assertTrue(all(a["page_id"] and a["page_name"].startswith("Anunciante") for a in ads))
        self.assertEqual([a["page_id"] for a in ads], [1100000000000001, 1100000000000001, 1100000000000002,
                                                       1100000000000002, 1100000000000003, 1100000000000001])
        self.assertEqual([a["estado_anuncio"] for a in ads], ["activo"] * 4 + ["inactivo", "activo"])
        self.assertTrue(all(a["plataformas"] == ["facebook", "instagram"] for a in ads))   # por la firma del ícono
        self.assertEqual([a["variantes"] for a in ads], [2, None, 2, None, None, 2])
        self.assertTrue(all(len(a["destinos"]) == 1 and a["destinos"][0]["url"].endswith(".example/") for a in ads))

    def test_fechas_en_espanol_y_el_rango_de_las_inactivas(self):
        ads, _ = rd.extraer_anuncios(self.dom, self.pr)
        d = lambda m, dia: int(datetime(2026, m, dia, tzinfo=timezone.utc).timestamp())  # noqa: E731
        self.assertEqual([a["inicio_epoch"] for a in ads], [d(10, 22), d(10, 24), d(10, 29), d(10, 31), d(8, 1), d(10, 30)])

    def test_el_titular_sale_del_bloque_dominio_titular_descripcion_del_enlace(self):
        ads, _ = rd.extraer_anuncios(self.dom, self.pr)
        self.assertEqual([a["titulo_fuente"] for a in ads], ["ninguna", "enlace", "ninguna", "enlace", "enlace", "ninguna"])
        self.assertEqual(ads[1]["titulo"], "Titular de ejemplo 002")
        self.assertNotIn("ANUNCIANTE", ads[1]["titulo"])                               # no es el dominio ni la descripción

    def test_la_pagina_es_ok_y_las_palabras_del_codigo_no_cuentan(self):
        a = rd.analizar_busqueda(self.dom, self.pr)
        self.assertEqual((a["estado"], a["motivos"], len(a["anuncios"]), a["total"]), ("ok", [], 6, 52))
        self.assertIn("captcha", self.dom)                       # el código de la página SÍ las nombra
        self.assertEqual(rd.analizar_busqueda(self.dom, self.pr, url_final=PREFIJO + "q=x")["estado"], "ok")

    def test_http_403_en_un_documento_frena_aunque_la_pagina_haya_cargado_entera(self):
        # Lo que pasó en la visita de sondeo: la página llegó completa, pero una respuesta de tipo Documento fue 403.
        # La regla es fail-closed: se frena y solo una persona decide si era falso positivo.
        a = rd.analizar_busqueda(self.dom, self.pr, estados_http=[{"tipo": "Document", "estado": 403, "destino": "www.facebook.com/x"}])
        self.assertEqual((a["estado"], a["anuncios"]), ("bloqueado", []))

    def test_el_fixture_no_trae_datos_reales(self):
        for real in ("Crea y Emprende", "Martín", "Salazar", "Catalina", "Vitraqis", "Atril", "impultienda", "fbcdn", "scontent"):
            self.assertNotIn(real.lower(), self.dom.lower())

    def test_recorrido_completo_con_el_dom_real_y_edad_de_la_oferta(self):
        sesion = SesionFalsa(paso(self.dom, url_final=PREFIJO + "q=x"), paso(self.dom, url_final=PREFIJO + "q=x"))
        r = self.barrer(sesion, max_desplazamientos=3)
        self.assertEqual((r["anuncios"], r["motivo_parada"], r["estimated_total_count"]), (5, "fin_de_lista", 52))   # el inactivo no entra
        self.assertEqual(r["tarjetas_de_otro_estado_descartadas"], 1)
        extra = json.loads((self.crudo_dir() / "es-prueba.extra.json").read_text(encoding="utf-8"))
        self.assertEqual(extra["tarjetas_de_otro_estado_descartadas"], 1)
        filas = extra["crudo_propuesto"]["ads"]
        self.assertTrue(all(f["page_id"] and f["ad_delivery_start_time"] for f in filas))      # lo que pide resumir_anuncios
        resumen = pm.resumir_anuncios(filas, INICIO)
        self.assertEqual((resumen["anuncios_activos"], resumen["paginas"]), (5, 2))
        self.assertGreater(resumen["edad_oferta_dias"], 0)


# ---------------------------------------------------------------------------
# Análisis de una instantánea: bloqueos y páginas raras
# ---------------------------------------------------------------------------

class PruebaAnalisis(Base):
    def analizar(self, dom, **kw):
        return rd.analizar_busqueda(dom, self.pr, **kw)

    def test_normal_es_ok(self):
        a = self.analizar(pagina())
        self.assertEqual((a["estado"], len(a["anuncios"]), a["total"]), ("ok", 3, 932))

    def test_cada_frase_de_bloqueo_de_captura_en_el_texto_visible_bloquea(self):
        for frase in rd.frases_bloqueo():
            with self.subTest(frase=frase):
                a = self.analizar(pagina(extra=f"<p>{frase.upper()}</p>"))
                self.assertEqual(a["estado"], "bloqueado")
                self.assertTrue(a["motivos"])
        self.assertTrue(set(ca.FRASES_BLOQUEO) <= set(rd.frases_bloqueo()))

    def test_las_mismas_frases_dentro_de_un_script_o_estilo_no_bloquean(self):
        for frase in ca.FRASES_BLOQUEO:
            dom = pagina().replace("</head>", f"<script>var m='{frase}';</script><style>/* {frase} */</style></head>")
            with self.subTest(frase=frase):
                self.assertEqual(self.analizar(dom)["estado"], "ok")

    def test_el_menu_iniciar_sesion_normal_no_es_un_muro(self):
        self.assertEqual(self.analizar(pagina(extra="Iniciar sesión Log in Crear cuenta"))["estado"], "ok")

    def test_un_bloqueo_con_anuncios_cargados_igual_bloquea_y_no_entrega_anuncios(self):
        a = self.analizar(pagina(extra="Confirma que eres una persona"))
        self.assertEqual((a["estado"], a["anuncios"]), ("bloqueado", []))

    def test_redireccion_fuera_de_la_biblioteca_es_login_obligatorio(self):
        for destino in ("https://www.facebook.com/login/?next=x", "https://www.facebook.com/checkpoint/1/",
                        "https://example.com/", "http://www.facebook.com/ads/library/?q=x"):
            with self.subTest(destino=destino):
                a = self.analizar(pagina(), url_final=destino)
                self.assertEqual(a["estado"], "bloqueado")
                self.assertIn("redirigido fuera de la Biblioteca", a["motivos"][0])
        self.assertEqual(self.analizar(pagina(), url_final=PREFIJO + "q=x&sort_data[mode]=a")["estado"], "ok")

    def test_http_401_403_429_bloquean_y_el_ruido_no(self):
        for codigo in (401, 403, 429):
            for tipo in ("Document", "XHR", "Fetch"):
                with self.subTest(codigo=codigo, tipo=tipo):
                    a = self.analizar(pagina(), estados_http=[{"tipo": tipo, "estado": codigo}])
                    self.assertEqual(a["estado"], "bloqueado")
        self.assertEqual(self.analizar(pagina(), estados_http=[{"tipo": "Document", "estado": 500}])["estado"], "bloqueado")
        self.assertEqual(self.analizar(pagina(), estados_http=[{"tipo": "XHR", "estado": 500}])["estado"], "ok")
        self.assertEqual(self.analizar(pagina(), estados_http=[{"tipo": "Image", "estado": 404}])["estado"], "ok")

    def test_el_motivo_del_http_dice_de_donde_vino_para_poder_diagnosticar(self):
        a = self.analizar(pagina(), estados_http=[{"tipo": "Document", "estado": 403, "destino": "www.facebook.com/ads/library/"}])
        self.assertEqual(a["motivos"], ["HTTP 403 (Document) en www.facebook.com/ads/library/"])

    def test_sin_anuncios_ni_mensaje_conocido_es_pagina_rara(self):
        for dom in ("", "<html><body>" + RELLENO + "</body></html>", "<html><body><div>Cargando…</div></body></html>"):
            with self.subTest(dom=dom[:30]):
                self.assertEqual(self.analizar(dom)["estado"], "rara")

    def test_el_mensaje_de_sin_resultados_es_legitimo(self):
        a = self.analizar("<html><body>" + RELLENO + "No ads match your search criteria.</body></html>")
        self.assertEqual((a["estado"], a["total"], a["anuncios"]), ("sin_resultados", 0, []))

    def test_un_dom_desmesurado_es_pagina_rara(self):
        a = rd.analizar_busqueda(pagina(), dict(self.pr, ruta_d_dom_max_caracteres=50))
        self.assertEqual(a["estado"], "rara")


# ---------------------------------------------------------------------------
# Orquestación con los frenos de captura.py
# ---------------------------------------------------------------------------

class PruebaRecorrido(Base):
    def test_recorre_fusiona_y_registra_cada_paso(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 7)), paso(pagina(0, 9)))
        r = self.barrer(sesion, max_desplazamientos=2)
        self.assertEqual([c[0] for c in sesion.llamadas], ["navegar", "desplazar", "desplazar"])
        self.assertEqual((r["estado"], r["anuncios"], r["pasos"], r["motivo_parada"]), ("ok", 9, 3, "tope_desplazamientos"))
        self.assertTrue(sesion.cerrada)
        entradas = self.capturas()
        self.assertEqual([(e["tipo"], e["paso"], e["estado"], e["anuncios"]) for e in entradas],
                         [("busqueda", 0, "ok", 4), ("busqueda", 1, "ok", 7), ("busqueda", 2, "ok", 9)])
        self.assertTrue(all(e["ad_id"] == "busqueda:es-prueba" and e["ts"].endswith("Z") for e in entradas))

    def test_el_tope_de_desplazamientos_sale_del_parametro_y_se_puede_bajar_pero_no_subir(self):
        cargas = [paso(pagina(0, 2 + 2 * i)) for i in range(40)]
        base = dict(self.pr, ruta_d_max_anuncios_por_busqueda=1000, ruta_d_max_busquedas_por_dia=20)
        for tope in (1, 3, 5):
            with self.subTest(tope=tope):
                sesion = SesionFalsa(*cargas)
                self.barrer(sesion, qid=f"q-{tope}", pr=dict(base, ruta_d_max_desplazamientos_por_busqueda=tope))
                self.assertEqual(len(sesion.llamadas), tope + 1)       # 1 carga + `tope` desplazamientos
        sesion = SesionFalsa(*cargas)
        self.barrer(sesion, qid="q-bajo", max_desplazamientos=2, pr=base)
        self.assertEqual(len(sesion.llamadas), 3)
        for pedido in (base["ruta_d_max_desplazamientos_por_busqueda"] + 1, -1, True, 1.5):
            with self.subTest(pedido=pedido), self.assertRaises(pm.ErrorUso):
                self.barrer(SesionFalsa(*cargas), qid="q-alto", max_desplazamientos=pedido, pr=base)
        sesion = SesionFalsa(*cargas)
        self.barrer(sesion, qid="q-cero", max_desplazamientos=0, pr=base)       # 0 = solo la carga inicial
        self.assertEqual([c[0] for c in sesion.llamadas], ["navegar"])

    def test_el_tope_de_anuncios_corta_y_recorta_exacto(self):
        sesion = SesionFalsa(paso(pagina(0, 5)), paso(pagina(0, 10)), paso(pagina(0, 20)), paso(pagina(0, 30)))
        pr = dict(self.pr, ruta_d_max_desplazamientos_por_busqueda=10)
        r = self.barrer(sesion, pr=pr)                        # tope de anuncios del archivo de pruebas = 12
        self.assertEqual((r["anuncios"], r["motivo_parada"]), (12, "tope_anuncios"))
        self.assertEqual(len(sesion.llamadas), 3)             # no siguió desplazando
        extra = json.loads((self.crudo_dir() / "es-prueba.extra.json").read_text(encoding="utf-8"))
        self.assertEqual([a["id"] for a in extra["ads_extra"]], [str(3_000_000_000_000_000 + n) for n in range(12)])

    def test_fin_de_lista_cuando_un_desplazamiento_no_trae_nada_nuevo(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 8)), paso(pagina(0, 8)), paso(pagina(0, 12)))
        r = self.barrer(sesion)
        self.assertEqual((r["motivo_parada"], r["anuncios"], len(sesion.llamadas)), ("fin_de_lista", 8, 3))

    def test_sin_resultados_termina_sin_desplazar(self):
        sesion = SesionFalsa(paso("<html><body>" + RELLENO + "No ads match your search criteria.</body></html>"))
        r = self.barrer(sesion)
        self.assertEqual((r["motivo_parada"], r["anuncios"], len(sesion.llamadas)), ("sin_resultados", 0, 1))
        crudo = comun.leer_crudo(self.crudo_dir() / "es-prueba.json")           # vacío es válido para el contrato
        self.assertEqual((crudo["ads"], crudo["estimated_total_count"], crudo["ruta"]), ([], 0, "D"))

    def test_la_pausa_compartida_se_respeta_entre_pasos(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 8)), paso(pagina(0, 12)))
        self.barrer(sesion, max_desplazamientos=2, pr=dict(self.pr, ruta_d_max_anuncios_por_busqueda=100))
        self.assertEqual(self.reloj.dormidas, [self.p["modelado_captura_pausa_seg"]] * 2)

    def test_idempotencia_la_misma_busqueda_no_se_abre_dos_veces(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 4)))
        self.barrer(sesion)
        antes = {f.name: f.read_bytes() for f in self.crudo_dir().iterdir()}
        capturas_antes = (self.estado / "capturas.jsonl").read_bytes()
        otra = SesionFalsa(paso(pagina(0, 9)))
        fabrica = Fabrica(otra)
        r = self.barrer(otra, fabrica=fabrica)
        self.assertEqual((r["estado"], fabrica.veces, otra.llamadas), ("ya_existe", 0, []))
        self.assertEqual({f.name: f.read_bytes() for f in self.crudo_dir().iterdir()}, antes)
        self.assertEqual((self.estado / "capturas.jsonl").read_bytes(), capturas_antes)

    def test_sin_sesion_disponible_no_se_abre_nada(self):
        with self.assertRaises(pm.ErrorUso):
            rd.barrer("2026-11-06-a", "q", frase="hola", pais="ES", p=self.p, pr=self.pr, estado_dir=self.estado, raiz=self.raiz)

    def test_la_sesion_se_cierra_incluso_si_algo_revienta(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            self.barrer(sesion)
        self.assertTrue(sesion.cerrada)


class PruebaFrenos(Base):
    def test_un_bloqueo_pone_el_freno_con_el_formato_de_captura_y_corta_sin_reintentar(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 8, extra="Confirma que eres una persona")), paso(pagina(0, 12)))
        r = self.barrer(sesion, max_desplazamientos=4)
        self.assertEqual((r["estado"], r["motivo_parada"]), ("bloqueado", "bloqueado"))
        self.assertEqual(len(sesion.llamadas), 2)                         # ni un desplazamiento más, ni reintento
        freno = json.loads((self.estado / "freno.json").read_text(encoding="utf-8"))
        self.assertEqual(set(freno), {"ts", "ad_id", "motivo"})            # el mismo formato que escribe captura
        self.assertEqual(freno["ad_id"], "busqueda:es-prueba")
        self.assertIn("confirma que eres una persona", freno["motivo"])
        with self.assertRaises(pm.ErrorBloqueado) as ctx:
            ca.verificar_freno(self.estado)                               # captura reconoce SU freno
        self.assertIn("borrá", str(ctx.exception))
        self.assertEqual(r["anuncios"], 4)                                # lo cargado antes del bloqueo se conserva
        self.assertEqual([e["estado"] for e in self.capturas()], ["ok", "bloqueado"])

    def test_bloqueo_en_la_carga_inicial_no_deja_crudo_solo_el_error(self):
        sesion = SesionFalsa(paso(pagina(0, 4, extra="Demasiadas solicitudes")))
        r = self.barrer(sesion)
        self.assertEqual((r["estado"], r["anuncios"]), ("bloqueado", 0))
        self.assertEqual(sorted(f.name for f in self.crudo_dir().iterdir()), ["es-prueba.error.json"])
        error = json.loads((self.crudo_dir() / "es-prueba.error.json").read_text(encoding="utf-8"))
        self.assertEqual(set(error), {"qid", "error", "ts"})
        self.assertTrue((self.estado / "freno.json").exists())

    def test_con_freno_presente_no_se_abre_chrome_ni_se_hace_red(self):
        self.poner_freno_a_mano()
        sesion = SesionFalsa(paso(pagina(0, 4)))
        fabrica = Fabrica(sesion)
        with mock.patch("subprocess.Popen", side_effect=AssertionError("no debe lanzar Chrome")), \
                self.assertRaises(pm.ErrorBloqueado):
            self.barrer(sesion, fabrica=fabrica)
        self.assertEqual((fabrica.veces, sesion.llamadas), (0, []))
        self.assertFalse(self.crudo_dir().exists())
        self.assertEqual(self.capturas(), [])
        # tampoco con la sesión real: SesionChrome ni se construye
        with mock.patch.object(rd, "SesionChrome", side_effect=AssertionError("no debe construirse")), \
                self.assertRaises(pm.ErrorBloqueado):
            self.barrer(sesion, fabrica=lambda p, pr: rd.SesionChrome(p, pr))        # envoltorio: la guarda M1 no interviene, el freno sí

    def test_el_freno_se_verifica_antes_de_cada_paso_y_antes_de_abrir_nada(self):
        orden: list[str] = []
        original = ca.verificar_freno

        def espia(estado):
            orden.append("freno")
            return original(estado)
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 8)), paso(pagina(0, 12)),
                             antes=lambda n: orden.append(f"paso{n}"))
        with mock.patch.object(ca, "verificar_freno", side_effect=espia):
            self.barrer(sesion, max_desplazamientos=2, pr=dict(self.pr, ruta_d_max_anuncios_por_busqueda=100))
        pasos = [i for i, x in enumerate(orden) if x.startswith("paso")]
        self.assertEqual(len(pasos), 3)
        for i in pasos:
            self.assertEqual(orden[i - 1], "freno", orden)

    def test_si_alguien_pone_el_freno_a_mitad_de_camino_no_se_desplaza_mas_y_se_conserva_lo_leido(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 8)), paso(pagina(0, 12)),
                             antes=lambda n: self.poner_freno_a_mano() if n == 2 else None)
        r = self.barrer(sesion, max_desplazamientos=4)
        self.assertEqual((r["motivo_parada"], r["anuncios"], len(sesion.llamadas)), ("freno_externo", 8, 2))

    def test_el_freno_manda_antes_que_la_idempotencia_y_que_los_topes(self):
        self.barrer(SesionFalsa(paso(pagina(0, 4))), max_desplazamientos=0)           # deja la búsqueda ya escrita
        self.poner_freno_a_mano()
        sesion = SesionFalsa(paso(pagina(0, 9)))
        with self.assertRaises(pm.ErrorBloqueado):                                    # y no «ya_existe»
            self.barrer(sesion)
        with self.assertRaises(pm.ErrorBloqueado):                                    # ni ErrorLimite por los topes propios
            self.barrer(sesion, qid="otra", pr=dict(self.pr, ruta_d_max_busquedas_por_dia=1))
        self.assertEqual(sesion.llamadas, [])

    def test_solo_una_persona_levanta_el_freno(self):
        sesion = SesionFalsa(paso(pagina(0, 4, extra="Security check required")))
        self.barrer(sesion, qid="uno")
        with self.assertRaises(pm.ErrorBloqueado):
            self.barrer(SesionFalsa(paso(pagina())), qid="dos")
        (self.estado / "freno.json").unlink()                              # lo hace la persona
        self.reloj.ahora += timedelta(seconds=self.p["modelado_captura_pausa_seg"])
        self.assertEqual(self.barrer(SesionFalsa(paso(pagina(0, 4))), qid="dos")["estado"], "ok")

    def test_pagina_rara_en_la_carga_inicial_frena(self):
        sesion = SesionFalsa(paso("<html><body>" + RELLENO + "</body></html>"))
        r = self.barrer(sesion)
        self.assertEqual((r["estado"], r["anuncios"]), ("rara", 0))
        self.assertIn("página rara", json.loads((self.estado / "freno.json").read_text(encoding="utf-8"))["motivo"])

    def test_si_la_lista_se_encoge_al_desplazar_es_pagina_rara_y_frena(self):
        sesion = SesionFalsa(paso(pagina(0, 8)), paso(pagina(0, 3)), paso(pagina(0, 20)))
        r = self.barrer(sesion, max_desplazamientos=4)
        self.assertEqual((r["estado"], r["anuncios"], len(sesion.llamadas)), ("rara", 8, 2))
        self.assertTrue((self.estado / "freno.json").exists())

    def test_redireccion_a_login_y_http_429_frenan(self):
        for i, malo in enumerate((paso(pagina(), url_final="https://www.facebook.com/login/"),
                                  paso(pagina(), estados=[{"tipo": "XHR", "estado": 429}]))):
            with self.subTest(i=i):
                (self.estado / "freno.json").unlink(missing_ok=True)
                self.reloj.ahora += timedelta(days=1)
                r = self.barrer(SesionFalsa(malo), qid=f"q-{i}")
                self.assertEqual(r["estado"], "bloqueado")
                self.assertTrue((self.estado / "freno.json").exists())

    def test_tope_diario_compartido_con_las_fichas_de_captura(self):
        self.estado.mkdir(parents=True)
        previas = "".join(json.dumps({"ad_id": f"{i}0000000", "estado": "ok", "ts": "2026-11-06T09:00:00Z"}) + "\n" for i in range(3))
        (self.estado / "capturas.jsonl").write_text(previas, encoding="utf-8")
        p = dict(self.p, modelado_captura_max_por_dia=3)
        sesion = SesionFalsa(paso(pagina(0, 4)))
        fabrica = Fabrica(sesion)
        with self.assertRaises(pm.ErrorLimite):
            self.barrer(sesion, p=p, fabrica=fabrica)
        self.assertEqual((fabrica.veces, sesion.llamadas), (0, []))
        # a mitad de búsqueda: corta, conserva lo leído y no lo trata como bloqueo
        p = dict(self.p, modelado_captura_max_por_dia=5)
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 8)), paso(pagina(0, 12)))
        r = self.barrer(sesion, p=p, max_desplazamientos=4, qid="q-medio")
        self.assertEqual((r["motivo_parada"], r["anuncios"], r["estado"]), ("tope_diario", 8, "ok"))
        self.assertFalse((self.estado / "freno.json").exists())
        self.assertEqual(len(self.capturas()), 5)

    def test_el_tope_diario_se_reinicia_al_dia_siguiente(self):
        p = dict(self.p, modelado_captura_max_por_dia=1)
        self.barrer(SesionFalsa(paso(pagina(0, 4))), p=p, qid="hoy", max_desplazamientos=1)
        self.reloj.ahora += timedelta(days=1)
        self.assertEqual(self.barrer(SesionFalsa(paso(pagina(0, 4))), p=p, qid="manana", max_desplazamientos=1)["estado"], "ok")

    def test_tope_propio_de_busquedas_por_dia(self):
        pr = dict(self.pr, ruta_d_max_busquedas_por_dia=2)
        for i in range(2):
            self.barrer(SesionFalsa(paso(pagina(0, 4))), qid=f"q-{i}", pr=pr, max_desplazamientos=1)
        sesion = SesionFalsa(paso(pagina(0, 4)))
        fabrica = Fabrica(sesion)
        with self.assertRaises(pm.ErrorLimite) as ctx:
            self.barrer(sesion, qid="q-3", pr=pr, fabrica=fabrica)
        self.assertIn("búsquedas", str(ctx.exception))
        self.assertEqual(fabrica.veces, 0)
        self.reloj.ahora += timedelta(days=1)
        self.assertEqual(self.barrer(SesionFalsa(paso(pagina(0, 4))), qid="q-4", pr=pr, max_desplazamientos=1)["estado"], "ok")

    def test_un_error_de_chrome_en_la_carga_inicial_se_anota_no_frena_y_deja_el_error(self):
        sesion = SesionFalsa(ErrorExterno("Chrome superó el tiempo máximo"))
        with self.assertRaises(ErrorExterno):
            self.barrer(sesion)
        self.assertEqual([e["estado"] for e in self.capturas()], ["error"])
        self.assertFalse((self.estado / "freno.json").exists())
        self.assertEqual([f.name for f in self.crudo_dir().iterdir()], ["es-prueba.error.json"])
        self.assertTrue(sesion.cerrada)

    def test_un_error_a_mitad_de_camino_conserva_lo_leido(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), ErrorExterno("se cayó"))
        r = self.barrer(sesion, max_desplazamientos=3)
        self.assertEqual((r["estado"], r["motivo_parada"], r["anuncios"]), ("error", "error_externo", 4))
        self.assertEqual(len(sesion.llamadas), 2)                         # no se reintentó

    def test_el_dom_se_vuelca_antes_de_analizarlo(self):
        volcados: dict[int, str] = {}
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 4, extra="Confirma que eres una persona")))
        self.barrer(sesion, max_desplazamientos=3, volcar_dom=lambda k, dom: volcados.__setitem__(k, dom))
        self.assertEqual(sorted(volcados), [0, 1])


# ---------------------------------------------------------------------------
# Salida: crudo del contrato y archivo hermano
# ---------------------------------------------------------------------------

class PruebaSalida(Base):
    def correr(self, n=4, **kw):
        sesion = SesionFalsa(paso(pagina(0, n)))
        return self.barrer(sesion, max_desplazamientos=0, **kw)

    def test_hoy_la_web_no_da_moneda_asi_que_el_crudo_oficial_no_se_escribe_pero_no_se_pierde_nada(self):
        r = self.correr()
        self.assertFalse(r["crudo_escrito"])
        self.assertEqual([f.name for f in self.crudo_dir().iterdir()], ["es-prueba.extra.json"])
        extra = json.loads((self.crudo_dir() / "es-prueba.extra.json").read_text(encoding="utf-8"))
        self.assertFalse(extra["crudo_escrito"])
        self.assertTrue(extra["motivo_sin_crudo"])
        propuesto = extra["crudo_propuesto"]
        self.assertEqual((propuesto["ruta"], propuesto["qid"], len(propuesto["ads"])), ("D", "es-prueba", 4))
        self.assertTrue(all(a["currency"] is None for a in propuesto["ads"]))
        self.assertEqual(extra["faltantes"]["currency"], 4)
        self.assertTrue(any("currency" in o for o in extra["obstaculos_del_contrato"]))
        self.assertEqual(len(extra["pedidos_al_contrato"]), 4)
        self.assertIn("AJENO", extra["aviso"])
        with self.assertRaises(pm.ErrorValidacion):
            comun.validar_crudo(propuesto)                                 # el crudo propuesto NO engaña al validador

    def test_los_obstaculos_incluyen_el_limite_de_50_cuando_se_pide_mas(self):
        sesion = SesionFalsa(paso(pagina(0, 4)))
        self.barrer(sesion, max_desplazamientos=0, pr=dict(self.pr, ruta_d_max_anuncios_por_busqueda=300), max_anuncios=60)
        extra = json.loads((self.crudo_dir() / "es-prueba.extra.json").read_text(encoding="utf-8"))
        self.assertTrue(any("limit=60" in o for o in extra["obstaculos_del_contrato"]))

    def test_si_el_contrato_acepta_los_nulos_de_la_ruta_d_el_crudo_se_escribe_tal_cual(self):
        # Simula el PEDIDO P1-P3 aceptado: el validador deja pasar null en currency/page_id/start_time cuando ruta == "D".
        def relajado(doc, *, origen=""):
            return doc
        with mock.patch.object(comun, "validar_crudo", side_effect=relajado):
            r = self.correr()
        self.assertTrue(r["crudo_escrito"])
        crudo = json.loads((self.crudo_dir() / "es-prueba.json").read_text(encoding="utf-8"))
        self.assertEqual((crudo["ruta"], crudo["estimated_total_count"], crudo["schema_version"]), ("D", 932, "1.0.0"))
        self.assertEqual(crudo["consulta"], {"search_terms": "acceso inmediato en PDF", "countries": ["ES"],
                                             "ad_active_status": "ACTIVE", "limit": 12, "page_ids": None})
        fila = crudo["ads"][0]
        self.assertEqual(set(fila), {"id", "page_id", "page_name", "ad_creative_link_title", "ad_delivery_start_time",
                                     "currency", "ad_snapshot_url"})
        self.assertIsNone(fila["currency"])
        extra = json.loads((self.crudo_dir() / "es-prueba.extra.json").read_text(encoding="utf-8"))
        self.assertIsNone(extra["crudo_propuesto"])

    def test_filas_completas_producen_un_crudo_que_el_validador_real_acepta(self):
        ads = [{"id": str(3_000_000_000_000_000 + n), "page_id": 1_100_000_000_000_000 + n, "page_name": f"P{n}",
                "titulo": f"T{n}", "inicio_epoch": 1793836800 + n, "texto": "x", "plataformas": [], "destinos": []}
               for n in range(5)]
        consulta = {"search_terms": "hola", "countries": ["ES"], "ad_active_status": "ACTIVE", "limit": 12, "page_ids": None}
        crudo = rd.construir_crudo("2026-11-06-a", "q-ok", consulta, "2026-11-06T12:00:00Z", ads, 932)
        for fila in crudo["ads"]:
            fila["currency"] = "EUR"                                       # lo que daría una fuente que sí la tenga
        r = rd.escribir_salidas(self.crudo_dir(), "2026-11-06-a", "q-ok", crudo, {"qid": "q-ok"}, ads)
        self.assertTrue(r["crudo_escrito"])
        leido = comun.leer_crudo(self.crudo_dir() / "q-ok.json")
        self.assertEqual([a["id"] for a in leido["ads"]], [a["id"] for a in ads])
        self.assertTrue(all(a["ad_snapshot_url"].endswith(f"?id={a['id']}") for a in leido["ads"]))
        self.assertEqual(pm.resumir_anuncios(leido["ads"], INICIO)["anuncios_activos"], 5)   # edad de la oferta calculable

    def test_el_total_inconsistente_no_se_afirma(self):
        ads = [{"id": str(i)} for i in range(5)]
        consulta = {"search_terms": "x", "countries": ["ES"], "ad_active_status": "ACTIVE", "limit": 12, "page_ids": None}
        self.assertIsNone(rd.construir_crudo("2026-11-06-a", "q", consulta, "2026-11-06T12:00:00Z", ads, 3)["estimated_total_count"])
        self.assertEqual(rd.construir_crudo("2026-11-06-a", "q", consulta, "2026-11-06T12:00:00Z", ads, 5)["estimated_total_count"], 5)
        self.assertIsNone(rd.construir_crudo("2026-11-06-a", "q", consulta, "2026-11-06T12:00:00Z", ads, None)["estimated_total_count"])

    def test_nunca_sobrescribe_y_no_hay_float_ni_texto_ajeno_interpretado(self):
        self.correr()
        with self.assertRaises(pm.ErrorUso):
            rd.escribir_salidas(self.crudo_dir(), "2026-11-06-a", "es-prueba", {"ads": [], "consulta": {"limit": 1, "countries": ["ES"]}}, {}, [])
        texto = (self.crudo_dir() / "es-prueba.extra.json").read_text(encoding="utf-8")
        json.loads(texto, parse_float=lambda x: self.fail(f"float en lo persistido: {x}"))

    def test_busqueda_por_pagina_fija_page_ids_y_el_pais_ALL_no_engana_al_contrato(self):
        sesion = SesionFalsa(paso(pagina(0, 4)))
        self.barrer(sesion, frase=None, pagina_id=1100000000000001, pais="ALL", max_desplazamientos=0)
        extra = json.loads((self.crudo_dir() / "es-prueba.extra.json").read_text(encoding="utf-8"))
        consulta = extra["crudo_propuesto"]["consulta"]
        self.assertEqual((consulta["search_terms"], consulta["page_ids"], consulta["countries"]), (None, ["1100000000000001"], ["ALL"]))
        self.assertTrue(any("ISO-2" in o for o in extra["obstaculos_del_contrato"]))
        self.assertIn("view_all_page_id=1100000000000001", extra["url_busqueda"])


# ---------------------------------------------------------------------------
# Chrome limpio con desplazamiento (sin Chrome real)
# ---------------------------------------------------------------------------

class ProcesoFalso:
    def __init__(self):
        self.terminado = False
        self.matado = False

    def wait(self, timeout=None):
        self.terminado = True
        return 0

    def kill(self):
        self.matado = True


class PruebaSesionChrome(Base):
    def lanzar(self):
        creados = []
        original = rd.tempfile.mkdtemp

        def rastrear(*a, **k):
            d = original(*a, **k)
            creados.append(Path(d))
            return d
        with mock.patch.object(rd.Path, "exists", return_value=True), \
                mock.patch.object(rd.tempfile, "mkdtemp", side_effect=rastrear), \
                mock.patch.object(rd.subprocess, "Popen", return_value=ProcesoFalso()) as popen:
            sesion = rd.SesionChrome(self.p, self.pr)
        return sesion, popen, creados

    def test_perfil_nuevo_sin_sesion_user_agent_honesto_y_sin_puerto_de_red(self):
        sesion, popen, creados = self.lanzar()
        cmd = popen.call_args[0][0]
        planas = " ".join(cmd)
        self.assertIn("--headless=new", cmd)
        self.assertIn("--remote-debugging-pipe", cmd)
        self.assertTrue(any(c.startswith("--user-data-dir=") for c in cmd))
        self.assertTrue(creados and creados[0].exists())
        for prohibido in ("--user-agent", "AutomationControlled", "--disable-blink-features", "--remote-debugging-port",
                          "--proxy-server", "--load-extension", "stealth", "--incognito-hide", "--enable-automation=false"):
            self.assertNotIn(prohibido, planas)
        self.assertEqual(popen.call_args[1]["pass_fds"], (3, 4))
        sesion.cerrar()
        self.assertFalse(creados[0].exists())                                # el perfil se destruye
        sesion.cerrar()                                                      # cerrar dos veces no rompe nada

    def test_sin_chrome_instalado_falla_cerrado(self):
        with mock.patch.dict("os.environ", {"FABRICA_CHROME": "/no/existe/chrome"}), self.assertRaises(pm.ErrorLimite):
            rd.SesionChrome(self.p, self.pr)

    def test_no_se_lanza_chrome_si_no_se_pide_la_visita_real(self):
        with mock.patch.object(rd, "SesionChrome", side_effect=AssertionError("no debe abrirse")), \
                mock.patch.object(rd.subprocess, "Popen", side_effect=AssertionError("no debe lanzarse")):
            salida = io.StringIO()
            codigo = rd.main(["buscar", "--corrida", "2026-11-06-a", "--qid", "q", "--frase", "hola", "--pais", "ES",
                              "--parametros", str(FIX / "modelado" / "parametros.yaml"),
                              "--parametros-ruta-d", str(FIX_RD / "parametros_ruta_d.yaml"),
                              "--estado-dir", str(self.estado), "--raiz", str(self.raiz)], salida=salida)
        self.assertEqual(codigo, 0)
        plan = json.loads(salida.getvalue())
        self.assertTrue(plan["simulacro"])
        self.assertTrue(plan["url"].startswith(PREFIJO))
        self.assertFalse(self.estado.exists())

    def test_la_sesion_solo_navega_a_direcciones_canonicas_de_la_biblioteca(self):
        sesion, _, _ = self.lanzar()
        sesion._cdp.llamar = mock.Mock()
        sesion._cdp.enviar = mock.Mock()
        for malo in ("https://evil.com/", "https://www.facebook.com/ads/library/?id=1234567890", "http://www.facebook.com/ads/library/?q=x"):
            with self.subTest(malo=malo), self.assertRaises(pm.ErrorValidacion):
                sesion.navegar(malo)
        sesion._cdp.llamar.assert_not_called()
        sesion._cdp.enviar.assert_not_called()
        sesion.cerrar()
        self.assertEqual(sesion._cdp.enviar.call_args_list, [mock.call("Browser.close")])      # lo único que se le dice al cerrar

    def test_estados_http_de_ignora_imagenes_y_exitos(self):
        eventos = [{"method": "Network.responseReceived", "params": {"type": t, "response": {"status": s, "url": f"https://www.facebook.com/x/{s}?token=secreto"}}}
                   for t, s in (("Document", 200), ("Image", 404), ("XHR", 429), ("Fetch", 500), ("Document", 403))]
        eventos.append({"method": "Page.loadEventFired"})
        eventos.append({"method": "Network.responseReceived", "params": "raro"})
        self.assertEqual(rd.estados_http_de(eventos), [
            {"tipo": "XHR", "estado": 429, "destino": "www.facebook.com/x/429"},
            {"tipo": "Fetch", "estado": 500, "destino": "www.facebook.com/x/500"},
            {"tipo": "Document", "estado": 403, "destino": "www.facebook.com/x/403"}])         # sin parámetros: ni tokens


class PruebaCdp(Base):
    def par(self):
        """(_Cdp, fd donde Chrome 'escribe', fd donde Chrome 'lee')."""
        a_r, a_w = os.pipe()
        b_r, b_w = os.pipe()
        for fd in (a_r, a_w, b_r, b_w):
            self.addCleanup(lambda f=fd: os.close(f) if self._abierto(f) else None)
        return rd._Cdp(a_w, b_r), b_w, a_r

    @staticmethod
    def _abierto(fd):
        try:
            os.fstat(fd)
            return True
        except OSError:
            return False

    @staticmethod
    def msg(obj):
        return json.dumps(obj).encode("utf-8") + b"\0"

    def test_llamar_manda_el_comando_y_junta_los_eventos_que_llegan_antes(self):
        cdp, chrome_escribe, chrome_lee = self.par()
        os.write(chrome_escribe, self.msg({"method": "Page.loadEventFired", "params": {}}) + self.msg({"id": 1, "result": {"ok": 1}}))
        self.assertEqual(cdp.llamar("Page.enable", sesion="S1", espera=2), {"ok": 1})
        enviado = json.loads(os.read(chrome_lee, 4096).rstrip(b"\0"))
        self.assertEqual(enviado, {"id": 1, "method": "Page.enable", "params": {}, "sessionId": "S1"})
        self.assertEqual([e["method"] for e in cdp.eventos], ["Page.loadEventFired"])
        self.assertTrue(cdp.esperar_evento("Page.loadEventFired", 0.1))
        self.assertFalse(cdp.esperar_evento("Network.loadingFinished", 0.05))

    def test_mensaje_partido_en_dos_lecturas(self):
        cdp, chrome_escribe, _ = self.par()
        mensaje = self.msg({"id": 1, "result": {"v": "x" * 5000}})
        os.write(chrome_escribe, mensaje[:3000])
        os.write(chrome_escribe, mensaje[3000:])
        self.assertEqual(cdp.llamar("Runtime.evaluate", espera=2)["v"], "x" * 5000)

    def test_error_de_chrome_silencio_y_cierre_son_falla_externa(self):
        cdp, chrome_escribe, _ = self.par()
        os.write(chrome_escribe, self.msg({"id": 1, "error": {"message": "no"}}))
        with self.assertRaises(ErrorExterno):
            cdp.llamar("X", espera=2)
        with self.assertRaises(ErrorExterno):                                # nadie contesta
            cdp.llamar("X", espera=0.05)
        os.write(chrome_escribe, b"basura\0")
        with self.assertRaises(ErrorExterno):
            cdp.llamar("X", espera=2)
        cdp2, escribe2, _ = self.par()
        os.close(escribe2)                                                   # Chrome cerró su lado
        with self.assertRaises(ErrorExterno):
            cdp2.llamar("X", espera=2)

    def test_bombear_recoge_eventos_sin_enviar_nada(self):
        cdp, chrome_escribe, chrome_lee = self.par()
        os.write(chrome_escribe, self.msg({"method": "Network.responseReceived", "params": {}}))
        cdp.bombear(0.05)
        self.assertEqual(len(cdp.eventos), 1)
        os.set_blocking(chrome_lee, False)
        with self.assertRaises(BlockingIOError):
            os.read(chrome_lee, 10)


# ---------------------------------------------------------------------------
# Revisión de seguridad: M1 (los frenos no los decide el invocador) y m5 (entorno mínimo de Chrome)
# ---------------------------------------------------------------------------

REAL = Path(comun.RAIZ) / "empresa" / "captura"


class PruebaGuardaDeProduccion(Base):
    """M1: con FABRICA_ENTORNO=produccion y con la visita real, el freno y el tope diario son SIEMPRE los del repositorio real."""

    def argv(self, *extra):
        return ["buscar", "--corrida", "2026-11-06-a", "--qid", "es-guarda", "--frase", "acceso inmediato en PDF", "--pais", "ES", *extra]

    def ejecutar(self, argv, **inyectados):
        salida, error = io.StringIO(), io.StringIO()
        with redirect_stderr(error):
            codigo = rd.main(argv, salida=salida, **inyectados)
        return codigo, salida.getvalue(), error.getvalue()

    def prohibidos(self):
        return (("--estado-dir", str(self.estado)), ("--raiz", str(self.raiz)),
                ("--parametros", str(FIX / "modelado" / "parametros.yaml")),
                ("--parametros-ruta-d", str(FIX_RD / "parametros_ruta_d.yaml")))

    def test_en_produccion_se_rechaza_cada_flag_que_cambia_donde_se_leen_los_frenos_y_topes(self):
        os.environ["FABRICA_ENTORNO"] = "produccion"
        for flag, valor in self.prohibidos():
            for visita in ([], ["--visita-real"]):
                with self.subTest(flag=flag, visita=visita):
                    sesion = SesionFalsa(paso(pagina(0, 4)))
                    fabrica = Fabrica(sesion)
                    with mock.patch.object(rd, "SesionChrome", side_effect=AssertionError("no debe abrirse")), \
                            mock.patch.object(rd.subprocess, "Popen", side_effect=AssertionError("no debe lanzarse")):
                        codigo, salida, error = self.ejecutar(self.argv(flag, valor, *visita), abrir_sesion=fabrica,
                                                              reloj=self.reloj, dormir=self.reloj.dormir)
                    self.assertEqual(codigo, 2)
                    self.assertIn("ErrorUso", error)
                    self.assertIn("FABRICA_ENTORNO=produccion", error)
                    self.assertEqual((fabrica.veces, sesion.llamadas, salida), (0, [], ""))
        self.assertFalse(self.estado.exists() or self.raiz.exists())          # tampoco se creó nada en la ruta alterna

    def test_fuera_de_produccion_esos_flags_siguen_valiendo_en_las_pruebas(self):
        sesion = SesionFalsa(paso(pagina(0, 4)))
        codigo, _, _ = self.ejecutar(self.argv("--estado-dir", str(self.estado), "--raiz", str(self.raiz),
                                               "--parametros", str(FIX / "modelado" / "parametros.yaml"),
                                               "--parametros-ruta-d", str(FIX_RD / "parametros_ruta_d.yaml"),
                                               "--max-desplazamientos", "0"),
                                     abrir_sesion=Fabrica(sesion), reloj=self.reloj, dormir=self.reloj.dormir)
        self.assertEqual((codigo, len(sesion.llamadas)), (0, 1))

    def test_en_produccion_un_entorno_invalido_falla_cerrado(self):
        os.environ["FABRICA_ENTORNO"] = "produccioon"
        codigo, _, error = self.ejecutar(self.argv("--estado-dir", str(self.estado)), abrir_sesion=Fabrica(SesionFalsa(paso(pagina()))))
        self.assertEqual(codigo, 2)
        self.assertIn("FABRICA_ENTORNO inválido", error)

    def test_con_la_visita_real_el_estado_siempre_es_el_del_repositorio_real(self):
        with mock.patch.object(rd, "barrer", return_value={"estado": "ok"}) as barrer, \
                mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.raiz)}):       # FABRICA_RAIZ no puede redirigirlo
            for entorno in ("desarrollo", "produccion"):
                os.environ["FABRICA_ENTORNO"] = entorno
                codigo, _, _ = self.ejecutar(self.argv("--visita-real"))
                self.assertEqual(codigo, 0)
                self.assertEqual(barrer.call_args.kwargs["estado_dir"], REAL)
                self.assertIsNone(barrer.call_args.kwargs["raiz"])
                self.assertIs(barrer.call_args.kwargs["abrir_sesion"], rd.SesionChrome)

    def test_con_la_visita_real_estado_dir_se_rechaza_en_cualquier_entorno(self):
        for entorno in ("desarrollo", "prueba", "produccion"):
            os.environ["FABRICA_ENTORNO"] = entorno
            with self.subTest(entorno=entorno), mock.patch.object(rd, "SesionChrome", side_effect=AssertionError("no debe abrirse")):
                codigo, _, error = self.ejecutar(self.argv("--visita-real", "--estado-dir", str(self.estado)))
                self.assertEqual(codigo, 2)
                self.assertIn("estado-dir", error)
        self.assertFalse(self.estado.exists())

    def test_el_driver_real_no_acepta_un_estado_alterno_ni_siquiera_llamado_como_biblioteca(self):
        fabrica = rd.SesionChrome
        with mock.patch.object(rd.subprocess, "Popen", side_effect=AssertionError("no debe lanzarse")), \
                self.assertRaises(pm.ErrorUso):
            self.barrer(None, fabrica=fabrica)                                   # estado_dir = carpeta temporal, no la real
        self.assertFalse(self.estado.exists())

    def test_en_produccion_barrer_no_acepta_estado_ni_raiz_alternos(self):
        os.environ["FABRICA_ENTORNO"] = "produccion"
        for kw in ({}, dict(estado_dir=REAL, raiz=self.raiz)):
            sesion = SesionFalsa(paso(pagina(0, 4)))
            fabrica = Fabrica(sesion)
            with self.subTest(kw=kw), self.assertRaises(pm.ErrorUso):
                self.barrer(sesion, fabrica=fabrica, **kw)
            self.assertEqual((fabrica.veces, sesion.llamadas), (0, []))

    def test_los_parametros_sin_rango_aprobado_fallan_cerrado(self):
        origen = (FIX_RD / "parametros_ruta_d.yaml").read_text(encoding="utf-8")
        for nombre, reemplazo in (("rango null", ("rango: [1, 30]", "rango: null")), ("sin rango", ("      rango: [1, 30]\n", ""))):
            destino = Path(self.tmp.name) / "sin_rango.yaml"
            destino.write_text(origen.replace(*reemplazo, 1), encoding="utf-8")
            with self.subTest(caso=nombre), self.assertRaises(pm.ErrorLimite):
                rd.cargar_parametros_ruta_d(destino)


class PruebaEntornoDeChrome(Base):
    """m5: el navegador que abre páginas de terceros no hereda tokens ni claves del proceso padre."""

    SECRETOS = {"META_AD_LIBRARY_TOKEN": "tok-meta", "STRIPE_SECRET_KEY": "sk_live_x", "ANTHROPIC_API_KEY": "sk-ant-x",
                "FABRICA_FIRMA_PUBLICA": "pub", "INGEST_HMAC_SECRET": "hmac", "AWS_SECRET_ACCESS_KEY": "aws", "FABRICA_CHROME": "/x/chrome"}

    def entorno_del_hijo(self, entorno):
        with mock.patch.dict(os.environ, entorno, clear=True), \
                mock.patch.object(rd.Path, "exists", return_value=True), \
                mock.patch.object(rd.subprocess, "Popen", return_value=ProcesoFalso()) as popen:
            sesion = rd.SesionChrome(self.p, self.pr)
        sesion.cerrar()
        return popen.call_args.kwargs.get("env")

    def test_el_hijo_solo_recibe_home_path_lang_y_tmpdir(self):
        base = {"HOME": "/Users/x", "PATH": "/usr/bin", "LANG": "es_AR.UTF-8", "TMPDIR": "/tmp/x/"}
        env = self.entorno_del_hijo({**base, **self.SECRETOS})
        self.assertEqual(env, base)
        for secreto in self.SECRETOS:
            self.assertNotIn(secreto, env)

    def test_lo_que_no_existe_no_se_inventa(self):
        self.assertEqual(self.entorno_del_hijo({"HOME": "/Users/x", "META_AD_LIBRARY_TOKEN": "t"}), {"HOME": "/Users/x"})
        self.assertEqual(self.entorno_del_hijo({"META_AD_LIBRARY_TOKEN": "t"}), {})

    def test_el_entorno_es_explicito_no_el_heredado(self):
        env = self.entorno_del_hijo({"HOME": "/h", "PATH": "/p"})
        self.assertIsInstance(env, dict)                  # env=None haría que el hijo heredara todo
        self.assertEqual(set(env), {"HOME", "PATH"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class PruebaCLI(Base):
    def ejecutar(self, *argv, **inyectados):
        salida, error = io.StringIO(), io.StringIO()
        with redirect_stderr(error):
            codigo = rd.main(list(argv), salida=salida, **inyectados)
        return codigo, salida.getvalue(), error.getvalue()

    def args(self, *extra):
        return ("buscar", "--corrida", "2026-11-06-a", "--qid", "es-cli", "--frase", "acceso inmediato en PDF", "--pais", "ES",
                "--parametros", str(FIX / "modelado" / "parametros.yaml"),
                "--parametros-ruta-d", str(FIX_RD / "parametros_ruta_d.yaml"),
                "--estado-dir", str(self.estado), "--raiz", str(self.raiz), *extra)

    def test_url_imprime_la_direccion_de_la_lista_blanca(self):
        codigo, salida, _ = self.ejecutar("url", "--frase", "acceso inmediato en PDF", "--pais", "ES")
        self.assertEqual((codigo, salida.strip()), (0, rd.url_busqueda("acceso inmediato en PDF", "ES")))
        codigo, salida, _ = self.ejecutar("url", "--pagina-id", "1100000000000001", "--pais", "ALL", "--estado", "all")
        self.assertEqual(codigo, 0)
        self.assertIn("view_all_page_id=1100000000000001", salida)

    def test_buscar_con_sesion_inyectada_escribe_los_archivos(self):
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 6)))
        codigo, salida, _ = self.ejecutar(*self.args("--max-desplazamientos", "1"), abrir_sesion=Fabrica(sesion),
                                          reloj=self.reloj, dormir=self.reloj.dormir)
        self.assertEqual(codigo, 0)
        resumen = json.loads(salida)
        self.assertEqual((resumen["anuncios"], resumen["pasos"]), (6, 2))
        self.assertTrue((self.crudo_dir() / "es-cli.extra.json").exists())

    def test_codigos_de_salida(self):
        malo = SesionFalsa(paso(pagina(0, 4, extra="Confirma que eres una persona")))
        inyectados = dict(reloj=self.reloj, dormir=self.reloj.dormir)
        self.assertEqual(self.ejecutar(*self.args(), abrir_sesion=Fabrica(malo), **inyectados)[0], 4)      # bloqueo
        self.assertEqual(self.ejecutar(*self.args(), abrir_sesion=Fabrica(malo), **inyectados)[0], 4)      # freno activo
        (self.estado / "freno.json").unlink()
        self.assertEqual(self.ejecutar("buscar", "--corrida", "2026-11-06-a", "--qid", "q", "--frase", "x", "--pais", "es",
                                       "--parametros", str(FIX / "modelado" / "parametros.yaml"),
                                       "--parametros-ruta-d", str(FIX_RD / "parametros_ruta_d.yaml"),
                                       "--estado-dir", str(self.estado), "--raiz", str(self.raiz),
                                       abrir_sesion=Fabrica(malo), **inyectados)[0], 3)                   # país inválido
        self.assertEqual(self.ejecutar(*self.args("--max-desplazamientos", "99"), abrir_sesion=Fabrica(malo), **inyectados)[0], 2)
        self.assertEqual(self.ejecutar(*self.args(), abrir_sesion=Fabrica(SesionFalsa(ErrorExterno("x"))), **inyectados)[0], 6)
        self.assertEqual(self.ejecutar(*self.args(), "--parametros-ruta-d", "/no/existe.yaml",
                                       abrir_sesion=Fabrica(malo), **inyectados)[0], 5)

    def test_guardar_dom_escribe_un_archivo_por_paso_sin_sobrescribir(self):
        base = Path(self.tmp.name) / "dom"
        sesion = SesionFalsa(paso(pagina(0, 4)), paso(pagina(0, 6)))
        self.ejecutar(*self.args("--max-desplazamientos", "1", "--guardar-dom", str(base)), abrir_sesion=Fabrica(sesion),
                      reloj=self.reloj, dormir=self.reloj.dormir)
        self.assertEqual(sorted(f.name for f in base.parent.glob("dom.paso*.html")), ["dom.paso0.html", "dom.paso1.html"])


if __name__ == "__main__":
    unittest.main()
