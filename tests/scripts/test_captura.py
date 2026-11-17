"""Pruebas de scripts/modelado/captura.py: captura automática de la Biblioteca CON FRENOS.

Sin red ni Chrome real: Chrome, el reloj, el sueño y la red se inyectan. Lo que se prueba es que los frenos
funcionan: solo fichas de la Biblioteca, tope diario, ritmo, y detención total ante un bloqueo.
"""

from __future__ import annotations

import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import quote

from scripts.modelado import captura as ca
from scripts.modelado import enlaces as en
from scripts.modelado import puntaje_modelar as pm
from tests.scripts.test_enlaces import AbridorFalso, PUBLICA, resolver_de, respuesta

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "modelado"
INICIO = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)
RELLENO = "Biblioteca de anuncios Crea y Emprende Anuncios Información Informe de la biblioteca " * 12


def dom(destinos=(), texto=RELLENO, extra_script="var x='arkose_captcha /checkpoint/block/';"):
    enlaces = "".join(f'<a href="https://l.facebook.com/l.php?u={quote(u, safe="")}&amp;h=AT0">Comprar</a>' for u in destinos)
    return (f"<html><head><title>Biblioteca de anuncios</title><script>{extra_script}</script></head>"
            f"<body><p>{texto}</p>{enlaces}</body></html>")


class Reloj:
    """Reloj falso que avanza cuando alguien duerme (sin esperas reales)."""

    def __init__(self, inicio=INICIO):
        self.ahora = inicio
        self.dormidas: list[float] = []

    def __call__(self):
        return self.ahora

    def dormir(self, segundos):
        self.dormidas.append(segundos)
        self.ahora += timedelta(seconds=segundos)


class Chrome:
    """Chrome falso: devuelve DOMs en orden y cuenta cuántas veces se lo usó."""

    def __init__(self, *doms):
        self.doms = list(doms)
        self.urls: list[str] = []

    def __call__(self, url, p):
        self.urls.append(url)
        return self.doms[min(len(self.urls), len(self.doms)) - 1]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = pm.cargar_parametros(FIXTURES / "parametros.yaml")

    def setUp(self):
        parche = mock.patch("socket.socket", side_effect=AssertionError("las pruebas no usan red"))
        parche.start()
        self.addCleanup(parche.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.estado = Path(self.tmp.name) / "captura"
        self.reloj = Reloj()

    def capturar(self, anuncio, chrome, p=None):
        return ca.capturar(anuncio, p or self.p, self.estado, ejecutar=chrome, reloj=self.reloj, dormir=self.reloj.dormir)


class PruebaFichasPermitidas(Base):
    def test_acepta_el_id_numerico_y_la_url_exacta(self):
        esperado = ("1907878687257184", "https://www.facebook.com/ads/library/?id=1907878687257184")
        self.assertEqual(ca.normalizar_anuncio("1907878687257184"), esperado)
        self.assertEqual(ca.normalizar_anuncio(esperado[1]), esperado)

    def test_rechaza_todo_lo_que_no_sea_una_ficha_de_la_biblioteca(self):
        for malo in ("https://www.facebook.com/", "https://www.facebook.com/ads/library/?id=123",
                     "https://www.facebook.com/ads/library/?id=12345678&q=x", "http://www.facebook.com/ads/library/?id=12345678",
                     "https://evil.com/ads/library/?id=12345678", "https://www.facebook.com/profile.php?id=12345678",
                     "https://www.facebook.com/ads/library/?id=12345678/../../x", "abc", "", "file:///etc/passwd"):
            with self.subTest(malo=malo):
                with self.assertRaises(pm.ErrorValidacion):
                    ca.normalizar_anuncio(malo)

    def test_no_se_ejecuta_nada_si_la_direccion_no_es_valida(self):
        chrome = Chrome(dom())
        with self.assertRaises(pm.ErrorValidacion):
            self.capturar("https://example.com/", chrome)
        self.assertEqual(chrome.urls, [])


class PruebaBusquedasPermitidas(Base):
    """Lista blanca de las páginas de BÚSQUEDA de la Biblioteca (aprobadas por el dueño el 2026-11-06)."""

    BASE = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ES&media_type=all&search_type=keyword_exact_phrase&q="

    def test_construye_la_url_de_una_frase_con_acentos_y_espacios(self):
        url = ca.construir_url_busqueda("Acceso inmediato en PDF", "ES")
        self.assertTrue(url.startswith("https://www.facebook.com/ads/library/?"))
        self.assertIn("q=Acceso%20inmediato%20en%20PDF", url)
        self.assertIn("search_type=keyword_exact_phrase", url)
        self.assertIn("ad_type=all", url)

    def test_normalizar_es_idempotente_y_ordena_los_parametros(self):
        url = ca.construir_url_busqueda("patrones crochet", "IT", exacta=False)
        self.assertEqual(ca.normalizar_busqueda(url), url)
        self.assertEqual(ca.normalizar_busqueda(url.replace("ad_type=all&", "")  + "&ad_type=all"), url)

    def test_busqueda_por_pagina(self):
        url = ca.construir_url_busqueda(pais="ALL", pagina_id=1056023200924288)
        self.assertIn("view_all_page_id=1056023200924288", url)
        self.assertIn("search_type=page", url)
        self.assertNotIn("q=", url)

    def test_rechaza_otros_sitios_rutas_y_esquemas_aunque_los_parametros_sean_validos(self):
        valida = self.BASE + "patrones"
        self.assertEqual(ca.normalizar_busqueda(valida).split("?")[0], "https://www.facebook.com/ads/library/")
        variantes = {
            "otro sitio": valida.replace("www.facebook.com", "evil.com"),
            "subdominio": valida.replace("www.facebook.com", "m.facebook.com"),
            "sitio engañoso": valida.replace("www.facebook.com", "www.facebook.com.evil.com"),
            "http": valida.replace("https://", "http://"),
            "otra ruta": valida.replace("/ads/library/", "/ads/library/api/"),
            "sin barra final": valida.replace("/ads/library/?", "/ads/library?"),
            "fragmento": valida + "#frag",
            "credenciales": valida.replace("https://", "https://u:p@"),
            "archivo local": "file:///ads/library/?" + valida.split("?")[1],
        }
        for nombre, malo in variantes.items():
            with self.subTest(nombre=nombre):
                with self.assertRaises(pm.ErrorValidacion):
                    ca.normalizar_busqueda(malo)
        for malo in ("", "https://www.facebook.com/", "no es una url"):
            with self.subTest(malo=malo):
                with self.assertRaises(pm.ErrorValidacion):
                    ca.normalizar_busqueda(malo)

    def test_rechaza_parametros_no_permitidos_y_repetidos(self):
        casos = [self.BASE + "x&access_token=abc", self.BASE + "x&id=1234567890123",
                 self.BASE + "x&sort_data%5Bmode%5D=total_impressions", self.BASE + "x&q=y",
                 self.BASE.replace("ad_type=all", "ad_type=political_and_issue_ads") + "x"]
        for malo in casos:
            with self.subTest(malo=malo):
                with self.assertRaises(pm.ErrorValidacion):
                    ca.normalizar_busqueda(malo)

    def test_solo_anuncios_comerciales_y_valores_validos(self):
        for malo in (self.BASE.replace("ad_type=all&", "") + "x", self.BASE.replace("country=ES", "country=es") + "x",
                     self.BASE.replace("country=ES", "country=ESP") + "x", self.BASE.replace("active_status=active", "active_status=raro") + "x",
                     self.BASE.replace("media_type=all", "media_type=audio") + "x"):
            with self.subTest(malo=malo):
                with self.assertRaises(pm.ErrorValidacion):
                    ca.normalizar_busqueda(malo)
        self.assertIn("country=ALL", ca.construir_url_busqueda("x" * 5, "ALL"))

    def test_exige_exactamente_una_frase_o_una_pagina(self):
        sin_nada = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ES&search_type=keyword_unordered"
        ambas = self.BASE + "x&view_all_page_id=1234567"
        for malo in (sin_nada, ambas):
            with self.subTest(malo=malo):
                with self.assertRaises(pm.ErrorValidacion):
                    ca.normalizar_busqueda(malo)

    def test_la_frase_tiene_limites(self):
        with self.assertRaises(pm.ErrorValidacion):
            ca.construir_url_busqueda("", "ES")
        with self.assertRaises(pm.ErrorValidacion):
            ca.construir_url_busqueda("a" * (ca.MAX_FRASE + 1), "ES")
        with self.assertRaises(pm.ErrorValidacion):
            ca.normalizar_busqueda(self.BASE + "hola%0Amundo")
        ca.construir_url_busqueda("a" * ca.MAX_FRASE, "ES")

    def test_la_pagina_exige_id_numerico_y_tipo_page(self):
        for malo in ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&search_type=page&view_all_page_id=abc",
                     "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&search_type=keyword_unordered&view_all_page_id=1234567"):
            with self.subTest(malo=malo):
                with self.assertRaises(pm.ErrorValidacion):
                    ca.normalizar_busqueda(malo)

    def test_una_ficha_de_anuncio_no_es_una_busqueda_ni_al_reves(self):
        with self.assertRaises(pm.ErrorValidacion):
            ca.normalizar_busqueda("https://www.facebook.com/ads/library/?id=1907878687257184")
        with self.assertRaises(pm.ErrorValidacion):
            ca.normalizar_anuncio(ca.construir_url_busqueda("patrones", "ES"))


class PruebaAnalisis(Base):
    def test_pagina_normal_es_ok_y_trae_los_destinos(self):
        r = ca.analizar_dom(dom(["https://a.com/?utm_source=fb"]), "111", self.p)
        self.assertEqual((r["estado"], r["destinos"]), ("ok", [{"url": "https://a.com/", "veces": 1}]))

    def test_las_palabras_de_bloqueo_dentro_del_codigo_no_cuentan(self):
        # Caso real: «captcha» y «checkpoint» aparecían en el JavaScript de la página, no en pantalla.
        r = ca.analizar_dom(dom(["https://a.com/"], extra_script="var c='captcha checkpoint security check';"), "1", self.p)
        self.assertEqual((r["estado"], r["motivos_bloqueo"]), ("ok", []))

    def test_una_frase_de_bloqueo_visible_marca_bloqueado(self):
        for frase in ("Confirma que eres una persona", "Demasiadas solicitudes", "Inicia sesión para continuar",
                      "Security check required", "Hemos detectado actividad inusual"):
            with self.subTest(frase=frase):
                r = ca.analizar_dom(dom(["https://a.com/"], texto=RELLENO + frase), "1", self.p)
                self.assertEqual(r["estado"], "bloqueado")

    def test_el_menu_iniciar_sesion_de_la_pagina_normal_no_es_un_muro(self):
        r = ca.analizar_dom(dom(["https://a.com/"], texto=RELLENO + " Iniciar sesión Biblioteca de anuncios"), "1", self.p)
        self.assertEqual(r["estado"], "ok")

    def test_pagina_vacia_sin_destinos_es_sin_contenido(self):
        self.assertEqual(ca.analizar_dom(dom([], texto="Cargando"), "1", self.p)["estado"], "sin_contenido")

    def test_el_texto_se_acota_pero_la_deteccion_mira_todo(self):
        largo = "palabra " * 5000 + " confirma que eres una persona"
        r = ca.analizar_dom(dom(["https://a.com/"], texto=largo), "1", dict(self.p, modelado_lectura_max_caracteres=100))
        self.assertEqual(len(r["texto"]), 100)
        self.assertEqual(r["estado"], "bloqueado")


class PruebaFrenos(Base):
    def test_cada_captura_queda_registrada(self):
        self.capturar("11111111", Chrome(dom(["https://a.com/"])))
        lineas = (self.estado / "capturas.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(x)["ad_id"] for x in lineas], ["11111111"])
        self.assertEqual(json.loads(lineas[0])["ts"], "2026-11-06T12:00:00Z")

    def test_un_bloqueo_pone_el_freno_y_no_se_captura_nada_mas(self):
        chrome = Chrome(dom(["https://a.com/"], texto=RELLENO + "Confirma que eres una persona"), dom(["https://a.com/"]))
        r = self.capturar("11111111", chrome)
        self.assertEqual(r["estado"], "bloqueado")
        self.assertTrue((self.estado / "freno.json").exists())
        with self.assertRaises(pm.ErrorBloqueado) as ctx:
            self.capturar("22222222", chrome)
        self.assertIn("borrá", str(ctx.exception))
        self.assertEqual(len(chrome.urls), 1)          # no hubo segundo intento ni reintento

    def test_solo_una_persona_levanta_el_freno(self):
        chrome = Chrome(dom(["https://a.com/"], texto=RELLENO + "Demasiadas solicitudes"), dom(["https://a.com/"]))
        self.capturar("11111111", chrome)
        (self.estado / "freno.json").unlink()           # lo hace la persona
        self.assertEqual(self.capturar("22222222", chrome)["estado"], "ok")

    def test_tope_diario(self):
        p = dict(self.p, modelado_captura_max_por_dia=2)
        chrome = Chrome(dom(["https://a.com/"]))
        self.capturar("11111111", chrome, p)
        self.capturar("22222222", chrome, p)
        with self.assertRaises(pm.ErrorLimite):
            self.capturar("33333333", chrome, p)
        self.assertEqual(len(chrome.urls), 2)

    def test_el_tope_se_reinicia_al_dia_siguiente(self):
        p = dict(self.p, modelado_captura_max_por_dia=1)
        chrome = Chrome(dom(["https://a.com/"]))
        self.capturar("11111111", chrome, p)
        self.reloj.ahora += timedelta(days=1)
        self.assertEqual(self.capturar("22222222", chrome, p)["estado"], "ok")

    def test_ritmo_humano_espera_lo_que_falta_y_no_mas(self):
        chrome = Chrome(dom(["https://a.com/"]))
        self.capturar("11111111", chrome)
        self.reloj.ahora += timedelta(seconds=8)
        self.capturar("22222222", chrome)
        self.assertEqual(self.reloj.dormidas, [self.p["modelado_captura_pausa_seg"] - 8])

    def test_si_ya_paso_la_pausa_no_duerme(self):
        chrome = Chrome(dom(["https://a.com/"]))
        self.capturar("11111111", chrome)
        self.reloj.ahora += timedelta(seconds=self.p["modelado_captura_pausa_seg"] + 1)
        self.capturar("22222222", chrome)
        self.assertEqual(self.reloj.dormidas, [])

    def test_un_error_de_chrome_no_deja_registro_ni_freno(self):
        def roto(url, p):
            raise en.ErrorExterno("Chrome terminó con código 1")
        with self.assertRaises(en.ErrorExterno):
            self.capturar("11111111", roto)
        self.assertFalse((self.estado / "capturas.jsonl").exists())
        self.assertFalse((self.estado / "freno.json").exists())


class PruebaChromeLimpio(Base):
    def lanzar(self, **kw):
        with mock.patch("scripts.modelado.captura.Path.exists", return_value=True), \
             mock.patch("scripts.modelado.captura.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="<html></html>", stderr="")
            run.side_effect = kw.get("side_effect")
            try:
                salida = ca.ejecutar_chrome("https://www.facebook.com/ads/library/?id=12345678", self.p)
            finally:
                comando = run.call_args[0][0] if run.call_args else None
        return salida, comando

    def test_usa_un_perfil_nuevo_y_no_disfraza_al_navegador(self):
        _, cmd = self.lanzar()
        planas = " ".join(cmd)
        self.assertIn("--headless=new", cmd)
        self.assertTrue(any(c.startswith("--user-data-dir=") for c in cmd))
        for prohibido in ("--user-agent", "AutomationControlled", "--disable-blink-features", "--remote-debugging",
                          "--proxy-server", "--load-extension", "stealth"):
            self.assertNotIn(prohibido, planas)

    def test_el_perfil_se_destruye_al_terminar(self):
        creados = []
        original = ca.tempfile.mkdtemp

        def rastrear(*a, **k):
            d = original(*a, **k)
            creados.append(Path(d))
            return d
        with mock.patch("scripts.modelado.captura.tempfile.mkdtemp", side_effect=rastrear):
            self.lanzar()
        self.assertEqual(len(creados), 1)
        self.assertFalse(creados[0].exists())

    def test_tiempo_agotado_o_codigo_de_error_son_falla_externa(self):
        import subprocess
        with self.assertRaises(en.ErrorExterno):
            self.lanzar(side_effect=subprocess.TimeoutExpired("chrome", 1))
        with mock.patch("scripts.modelado.captura.Path.exists", return_value=True), \
             mock.patch("scripts.modelado.captura.subprocess.run", return_value=mock.Mock(returncode=1, stdout="")):
            with self.assertRaises(en.ErrorExterno):
                ca.ejecutar_chrome("https://www.facebook.com/ads/library/?id=12345678", self.p)

    def test_sin_chrome_instalado_falla_cerrado(self):
        with mock.patch.dict("os.environ", {"FABRICA_CHROME": "/no/existe/chrome"}):
            with self.assertRaises(pm.ErrorLimite):
                ca.ejecutar_chrome("https://www.facebook.com/ads/library/?id=12345678", self.p)


class PruebaReunirMaterial(Base):
    def reunir(self, chrome, anuncios=("11111111", "22222222"), rutas=None, hosts=None, p=None):
        abridor = AbridorFalso(rutas or {})
        material = ca.reunir_material(
            "mi-oferta", anuncios, p or self.p, self.estado, ejecutar=chrome, abrir=abridor,
            resolver=resolver_de(hosts or {"a.com": [PUBLICA], "b.com": [PUBLICA]}),
            reloj=self.reloj, dormir=self.reloj.dormir)
        return material, abridor

    def test_junta_destinos_lee_las_paginas_y_marca_todo_como_dato_ajeno(self):
        chrome = Chrome(dom(["https://a.com/p", "https://a.com/p"]), dom(["https://a.com/p", "https://b.com/q"]))
        rutas = {"https://a.com/p": respuesta(cuerpo="<title>A</title><p>Oferta A</p>"),
                 "https://b.com/q": respuesta(cuerpo="<title>B</title><p>Oferta B</p>")}
        m, ab = self.reunir(chrome, rutas=rutas)
        self.assertEqual([x["url"] for x in m["paginas"]], ["https://a.com/p", "https://b.com/q"])
        self.assertEqual([x["anuncios_que_la_enlazan"] for x in m["paginas"]], [3, 1])
        self.assertIsNone(m["detenido"])
        self.assertIn("AJENO", m["aviso"])
        self.assertEqual(len(m["anuncios"]), 2)

    def test_respeta_el_maximo_de_paginas_y_la_pausa_entre_lecturas(self):
        destinos = [f"https://a.com/{i}" for i in range(6)]
        rutas = {u: respuesta() for u in destinos}
        m, _ = self.reunir(Chrome(dom(destinos)), anuncios=("11111111",), rutas=rutas)
        self.assertEqual(len(m["paginas"]), self.p["modelado_lectura_max_paginas"])
        self.assertEqual(self.reloj.dormidas.count(self.p["modelado_lectura_pausa_seg"]),
                         self.p["modelado_lectura_max_paginas"] - 1)

    def test_si_un_anuncio_sale_bloqueado_no_se_captura_ninguno_mas(self):
        chrome = Chrome(dom(["https://a.com/p"]), dom(["https://a.com/p"], texto=RELLENO + "Confirma que eres una persona"),
                        dom(["https://a.com/p"]))
        m, _ = self.reunir(chrome, anuncios=("11111111", "22222222", "33333333"), rutas={"https://a.com/p": respuesta()})
        self.assertEqual(len(chrome.urls), 2)
        self.assertIn("bloqueado", m["detenido"])
        self.assertTrue((self.estado / "freno.json").exists())

    def test_con_freno_activo_no_se_toca_nada(self):
        self.estado.mkdir(parents=True)
        (self.estado / "freno.json").write_text(json.dumps({"ts": "2026-11-05T00:00:00Z", "motivo": "x"}), encoding="utf-8")
        chrome = Chrome(dom(["https://a.com/p"]))
        m, ab = self.reunir(chrome)
        self.assertEqual((chrome.urls, ab.llamadas, m["anuncios"]), ([], [], []))
        self.assertIn("ErrorBloqueado", m["detenido"])

    def test_una_pagina_de_venta_que_apunta_a_la_red_interna_no_se_lee_y_no_rompe_el_resto(self):
        chrome = Chrome(dom(["https://a.com/p", "https://interna.com/admin"]))
        m, ab = self.reunir(chrome, anuncios=("11111111",), rutas={"https://a.com/p": respuesta()},
                            hosts={"a.com": [PUBLICA], "interna.com": ["192.168.0.10"]})
        estados = {x["url"]: x["estado"] for x in m["paginas"]}
        self.assertEqual(estados, {"https://a.com/p": "ok", "https://interna.com/admin": "no_leida"})
        self.assertTrue(all("interna.com" not in u for u in ab.urls()))

    def test_un_antibot_en_una_pagina_se_informa_y_se_sigue_con_las_demas_sin_reintentar(self):
        chrome = Chrome(dom(["https://a.com/p", "https://b.com/q"]))
        rutas = {"https://a.com/p": respuesta(403, "no"), "https://b.com/q": respuesta()}
        m, ab = self.reunir(chrome, anuncios=("11111111",), rutas=rutas)
        self.assertEqual({x["url"]: x["estado"] for x in m["paginas"]},
                         {"https://a.com/p": "bloqueado_antibot", "https://b.com/q": "ok"})
        self.assertEqual(ab.urls().count("https://a.com/p"), 1)


class PruebaCLI(Base):
    def ejecutar(self, *argv, **inyectados):
        salida, error = io.StringIO(), io.StringIO()
        with redirect_stderr(error):
            codigo = ca.main(list(argv), salida=salida, **inyectados)
        return codigo, salida.getvalue(), error.getvalue()

    def args(self, *extra):
        return (*extra, "--parametros", str(FIXTURES / "parametros.yaml"), "--estado-dir", str(self.estado))

    def test_anuncio_ok(self):
        codigo, salida, _ = self.ejecutar(*self.args("anuncio", "11111111"), ejecutar=Chrome(dom(["https://a.com/"])),
                                          reloj=self.reloj, dormir=self.reloj.dormir)
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida)["destinos"], [{"url": "https://a.com/", "veces": 1}])

    def test_direccion_invalida_sale_con_tres(self):
        codigo, _, error = self.ejecutar(*self.args("anuncio", "https://example.com/"), ejecutar=Chrome(dom()))
        self.assertEqual(codigo, 3)
        self.assertIn("ErrorValidacion", error)

    def test_con_freno_sale_con_cuatro_y_con_tope_sale_con_cinco(self):
        self.estado.mkdir(parents=True)
        (self.estado / "freno.json").write_text(json.dumps({"ts": "2026-11-06T00:00:00Z", "motivo": "x"}), encoding="utf-8")
        codigo, _, _ = self.ejecutar(*self.args("anuncio", "11111111"), ejecutar=Chrome(dom()))
        self.assertEqual(codigo, 4)
        (self.estado / "freno.json").unlink()
        otro_estado = Path(self.tmp.name) / "otro"
        parametros = Path(self.tmp.name) / "p.yaml"
        parametros.write_text((FIXTURES / "parametros.yaml").read_text(encoding="utf-8").replace(
            "modelado_captura_max_por_dia:\n      valor: 30", "modelado_captura_max_por_dia:\n      valor: 1"), encoding="utf-8")
        args = ("anuncio", "11111111", "--parametros", str(parametros), "--estado-dir", str(otro_estado))
        inyectados = dict(ejecutar=Chrome(dom(["https://a.com/"])), reloj=self.reloj, dormir=self.reloj.dormir)
        self.assertEqual(self.ejecutar(*args, **inyectados)[0], 0)
        self.assertEqual(self.ejecutar(*args, **inyectados)[0], 5)

    def test_material_escribe_el_archivo_y_no_sobrescribe(self):
        destino = Path(self.tmp.name) / "material.json"
        args = self.args("material", "mi-oferta", "11111111", "--salida", str(destino))
        inyectados = dict(ejecutar=Chrome(dom(["https://a.com/p"])), abrir=AbridorFalso({"https://a.com/p": respuesta()}),
                          resolver=resolver_de({"a.com": [PUBLICA]}), reloj=self.reloj, dormir=self.reloj.dormir)
        self.assertEqual(self.ejecutar(*args, **inyectados)[0], 0)
        contenido = destino.read_text(encoding="utf-8")
        self.assertEqual(json.loads(contenido)["paginas"][0]["estado"], "ok")
        self.assertEqual(self.ejecutar(*args, **inyectados)[0], 2)
        self.assertEqual(destino.read_text(encoding="utf-8"), contenido)


if __name__ == "__main__":
    unittest.main()
