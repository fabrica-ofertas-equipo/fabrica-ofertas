"""Seguridad del panel: Host/Origin/token, cabeceras y CSP, resolvedor confinado (rutas hostiles), estáticos y /sitio."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from dashboard.archivos import es_nombre_prohibido, resolver
from dashboard.seguridad import CSP_SITIO, ErrorHttp, Politica, iguales
from tests.dashboard.test_servidor_apoyo import OFERTA, PruebaBase


class PruebaHostOrigenToken(PruebaBase):
    def test_host_solo_loopback_con_el_puerto_del_panel(self) -> None:
        c = self.cliente()
        for host in ("evil.example.com", "127.0.0.1", "localhost", "127.0.0.1:9999", "evil.com:8765", "[::1]:8765", "", "0.0.0.0:8765",
                     "127.0.0.1:8765.evil.com", "127.0.0.1:8765,evil.com"):
            for ruta in ("/api/sistema", "/", "/app.js", f"/sitio/{OFERTA}/index.html"):
                r = c.get(ruta, host=host)
                self.assertEqual(r.estado, 403, f"{host!r} {ruta}")
                self.assertEqual(r.json()["error"]["codigo"], "host_no_permitido")
        for host in ("127.0.0.1:8765", "localhost:8765", "LOCALHOST:8765"):
            self.assertEqual(c.get("/api/sistema", host=host).estado, 200, host)

    def test_host_ausente_se_rechaza(self) -> None:
        c = self.cliente()
        env = c.environ("GET", "/api/sistema")
        del env["HTTP_HOST"]
        estado = []
        c.app(env, lambda linea, cab, exc=None: estado.append(linea))
        self.assertTrue(estado[0].startswith("403"))

    def test_token_obligatorio_y_en_tiempo_constante(self) -> None:
        c = self.cliente()
        for token in (False, "", "x", "A" * 43, "tóken-ñ-€", c.token + "x", c.token[:-1]):
            r = c.get("/api/sistema", token=token)
            self.assertEqual(r.estado, 403, repr(token))
            self.assertEqual(r.json()["error"]["codigo"], "token_invalido")
        self.assertEqual(c.get("/api/sistema").estado, 200)
        self.assertTrue(iguales("abc", "abc"))
        self.assertFalse(iguales("abc", "abd"))
        self.assertFalse(iguales(None, "abc"))
        self.assertFalse(iguales("ñ", "n"), "texto no ASCII no lanza")
        import inspect
        from dashboard import seguridad
        self.assertIn("compare_digest", inspect.getsource(seguridad.iguales))

    def test_token_en_la_consulta_solo_vale_para_eventos(self) -> None:
        c = self.cliente()
        self.assertEqual(c.get("/api/sistema", consulta=f"t={c.token}", token=False).estado, 403)
        estado, _, flujo = c.flujo("/api/eventos", consulta=f"t={c.token}", token=False)
        self.assertEqual(estado, 200)
        flujo.close()
        self.assertEqual(c.get("/api/eventos", consulta="t=mal", token=False).estado, 403)

    def test_token_es_aleatorio_de_32_bytes_y_distinto_por_panel(self) -> None:
        a, b = self.panel(), self.panel()
        self.assertNotEqual(a.token, b.token)
        self.assertGreaterEqual(len(a.token), 43)
        self.assertRegex(a.token, r"^[A-Za-z0-9_-]+$")

    def test_post_exige_origen_propio(self) -> None:
        c = self.cliente()
        r = c.post("/api/pulido", {"etapa": "D1", "titulo": "t"}, origen=False)
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (403, "origen_requerido"))
        for origen in ("http://evil.example.com", "null", "http://127.0.0.1:9999", "https://127.0.0.1:8765",
                       "http://127.0.0.1:8765.evil.com", "http://localhost"):
            r = c.post("/api/pulido", {"etapa": "D1", "titulo": "t"}, origen=origen)
            self.assertEqual((r.estado, r.json()["error"]["codigo"]), (403, "origen_no_permitido"), origen)
        ok = c.post("/api/pulido", {"etapa": "D1", "titulo": "t"}, origen="http://localhost:8765")
        self.assertEqual(ok.estado, 200)
        self.assertFalse((self.raiz / "empresa" / "PAUSA").exists())

    def test_post_sin_token_no_ejecuta_nada(self) -> None:
        c = self.cliente()
        r = c.post("/api/pausa", {"motivo": "x"}, token=False)
        self.assertEqual(r.estado, 403)
        self.assertFalse((self.raiz / "empresa" / "PAUSA").exists())
        r = c.post("/api/accion", {"id": "eco", "args": {"n": 1}}, token="mal")
        self.assertEqual(r.estado, 403)

    def test_get_con_origen_ajeno_o_sec_fetch_cross_site_se_rechaza(self) -> None:
        c = self.cliente()
        self.assertEqual(c.get("/api/sistema", origen="http://evil.example.com").estado, 403)
        self.assertEqual(c.get("/api/sistema", origen=True).estado, 200)
        self.assertEqual(c.get("/api/sistema", cabeceras={"Sec-Fetch-Site": "cross-site"}).estado, 403)
        self.assertEqual(c.get("/api/sistema", cabeceras={"Sec-Fetch-Site": "same-site"}).estado, 403)
        self.assertEqual(c.get("/api/sistema", cabeceras={"Sec-Fetch-Site": "same-origin"}).estado, 200)
        self.assertEqual(c.get("/api/sistema", cabeceras={"Sec-Fetch-Site": "none"}).estado, 200)

    def test_cambiar_el_puerto_cambia_los_hosts_validos(self) -> None:
        app = self.panel(puerto=0)
        app.fijar_puerto(4321)
        from tests.dashboard.test_servidor_apoyo import Cliente
        c = Cliente(app, puerto=4321)
        self.assertEqual(c.get("/api/sistema").estado, 200)
        self.assertEqual(Cliente(app, puerto=8765).get("/api/sistema").estado, 403)
        self.assertEqual(app.url(), f"http://127.0.0.1:4321/#t={app.token}")

    def test_politica_unitaria(self) -> None:
        p = Politica(puerto=1234, token="t" * 43)
        self.assertEqual(p.hosts(), {"127.0.0.1:1234", "localhost:1234"})
        with self.assertRaises(ErrorHttp):
            p.comprobar_host({"HTTP_HOST": "localhost:1235"})
        p.comprobar_host({"HTTP_HOST": "localhost:1234"})
        p.comprobar_origen({}, obligatorio=False)
        with self.assertRaises(ErrorHttp):
            p.comprobar_origen({}, obligatorio=True)


class PruebaCuerpos(PruebaBase):
    def test_tipo_de_contenido_obligatorio(self) -> None:
        c = self.cliente()
        r = c.llamar("POST", "/api/pausa", cuerpo=b'{"motivo": "x"}', tipo="text/plain")
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (400, "tipo_contenido_invalido"))
        r = c.llamar("POST", "/api/pausa", cuerpo=b'{"motivo": "x"}')
        self.assertEqual(r.estado, 400)
        self.assertFalse((self.raiz / "empresa" / "PAUSA").exists())
        r = c.llamar("POST", "/api/pausa", cuerpo=b'{}', tipo="application/json; charset=utf-8")
        self.assertEqual(r.estado, 200)

    def test_longitud_requerida_e_invalida(self) -> None:
        c = self.cliente()
        env = c.environ("POST", "/api/pausa", cuerpo=b"{}", tipo="application/json")
        del env["CONTENT_LENGTH"]
        estado = []
        c.app(env, lambda linea, cab, exc=None: estado.append(linea))
        self.assertTrue(estado[0].startswith("411"))
        for valor, esperado in (("abc", 400), ("-5", 400)):
            env = c.environ("POST", "/api/pausa", cuerpo=b"{}", tipo="application/json")
            env["CONTENT_LENGTH"] = valor
            estado = []
            c.app(env, lambda linea, cab, exc=None: estado.append(linea))
            self.assertTrue(estado[0].startswith(str(esperado)), valor)

    def test_cuerpo_gigante_se_rechaza_sin_leerlo(self) -> None:
        c = self.cliente()
        env = c.environ("POST", "/api/pulido", cuerpo=b"{}", tipo="application/json")
        env["CONTENT_LENGTH"] = str(10 * 1024 * 1024)

        class Prohibido:
            def read(self, n: int = -1) -> bytes:
                raise AssertionError("no debe leer un cuerpo que ya sabe demasiado grande")

        env["wsgi.input"] = Prohibido()
        estado = []
        cuerpo = b"".join(c.app(env, lambda linea, cab, exc=None: estado.append(linea)))
        self.assertTrue(estado[0].startswith("413"))
        self.assertIn(b"cuerpo_demasiado_grande", cuerpo)
        r = c.llamar("POST", "/api/pulido", cuerpo=b'{"titulo": "' + b"a" * 70000 + b'"}', tipo="application/json")
        self.assertEqual(r.estado, 413)

    def test_json_corrupto_o_no_estricto(self) -> None:
        c = self.cliente()
        for cuerpo in (b"{no json", b'{"a": NaN}', b'{"a": Infinity}', b'{"a": 1e999}', b"\xff\xfe", b"[" * 50000, b'{"titulo": "' + b"x"):
            r = c.llamar("POST", "/api/pulido", cuerpo=cuerpo, tipo="application/json")
            self.assertEqual((r.estado, r.json()["error"]["codigo"]), (400, "cuerpo_invalido"), cuerpo[:20])

    def test_cuerpo_incompleto(self) -> None:
        c = self.cliente()
        env = c.environ("POST", "/api/pulido", cuerpo=b'{"a": 1}', tipo="application/json")
        env["CONTENT_LENGTH"] = "500"
        estado = []
        cuerpo = b"".join(c.app(env, lambda linea, cab, exc=None: estado.append(linea)))
        self.assertTrue(estado[0].startswith("400"))
        self.assertIn(b"cuerpo_incompleto", cuerpo)

    def test_cuerpo_que_no_es_objeto(self) -> None:
        c = self.cliente()
        self.assertEqual(c.llamar("POST", "/api/pausa", cuerpo=b"[1,2]", tipo="application/json").estado, 400)
        self.assertEqual(c.llamar("POST", "/api/accion", cuerpo=b'"eco"', tipo="application/json").estado, 400)
        self.assertEqual(c.llamar("POST", "/api/pulido", cuerpo=b"123", tipo="application/json").estado, 400)

    def test_consulta_excesiva(self) -> None:
        c = self.cliente()
        self.assertEqual(c.get("/api/registro", consulta="a=" + "b" * 5000).estado, 400)
        self.assertEqual(c.get("/api/registro", consulta="&".join(f"k{i}=1" for i in range(40))).estado, 400)


class PruebaCabeceras(PruebaBase):
    def test_cabeceras_de_seguridad_en_json_estaticos_y_errores(self) -> None:
        c = self.cliente()
        for r in (c.get("/api/sistema"), c.get("/api/nada"), c.get("/"), c.get("/app.js"), c.get("/api/sistema", token=False)):
            self.assertEqual(r.cabeceras["x-content-type-options"], "nosniff")
            self.assertEqual(r.cabeceras["cache-control"], "no-store")
            self.assertEqual(r.cabeceras["referrer-policy"], "no-referrer")
            self.assertEqual(r.cabeceras["x-frame-options"], "DENY")
            self.assertEqual(r.cabeceras["cross-origin-resource-policy"], "same-origin")
        csp = c.get("/").cabeceras["content-security-policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("script-src 'self' 'unsafe", csp)
        self.assertNotIn("unsafe-eval", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertNotIn("http", csp, "la CSP no admite orígenes remotos")

    def test_no_hay_cabeceras_cors(self) -> None:
        r = self.cliente().get("/api/sistema")
        self.assertFalse([k for k in r.cabeceras if k.startswith("access-control")])


class PruebaEstaticos(PruebaBase):
    def test_sirve_index_y_estaticos_con_mime(self) -> None:
        c = self.cliente()
        r = c.get("/")
        self.assertEqual((r.estado, r.cabeceras["content-type"]), (200, "text/html; charset=utf-8"))
        self.assertIn(b"Panel de prueba", r.cuerpo)
        self.assertEqual(c.get("/index.html").cuerpo, r.cuerpo)
        self.assertEqual(c.get("/app.js").cabeceras["content-type"], "text/javascript; charset=utf-8")
        self.assertEqual(c.get("/styles.css").cabeceras["content-type"], "text/css; charset=utf-8")
        self.assertEqual(c.get("/pages/demo.js").estado, 200)
        self.assertEqual(c.get("/lib/util.js").estado, 200)
        h = c.llamar("HEAD", "/app.js")
        self.assertEqual((h.estado, h.cuerpo, h.cabeceras["content-length"]), (200, b"", str(len(c.get("/app.js").cuerpo))))
        self.assertEqual(c.llamar("POST", "/app.js", json_={}).estado, 405)
        self.assertEqual(c.get("/nada.js").estado, 404)
        self.assertEqual(c.get("/LEEME.md").estado, 404, "extensiones no servibles")
        self.assertEqual(c.get("/pages").estado, 404)

    def test_sin_index_muestra_pagina_provisional(self) -> None:
        (self.web / "index.html").unlink()
        r = self.cliente().get("/")
        self.assertEqual(r.estado, 200)
        self.assertIn(b"todav", r.cuerpo)
        self.assertNotIn(b"<script", r.cuerpo.lower())
        self.assertEqual(self.cliente().get("/favicon.ico").estado, 204)

    def test_estaticos_no_salen_de_web(self) -> None:
        c = self.cliente()
        (self.web / ".env").write_text("X=1\n")
        self.escribir("secreto-fuera.js", "x")
        for ruta in ("/../repo/empresa/limites.yaml", "/../../etc/passwd", "/pages/../../repo/empresa/parametros.yaml", "/.env",
                     "/%2e%2e/x.js", "//etc/passwd", "/pages/.hidden.js", "/\\..\\x.js"):
            r = c.get(ruta)
            self.assertIn(r.estado, (403, 404), ruta)
            self.assertNotIn(b"X=1", r.cuerpo)
            self.assertNotIn(b"moneda_limites", r.cuerpo)
        outside = self.tmp / "fuera.js"
        outside.write_text("secreto")
        os.symlink(outside, self.web / "enlace.js")
        r = c.get("/enlace.js")
        self.assertEqual(r.estado, 403)
        self.assertNotIn(b"secreto", r.cuerpo)

    def test_ruta_no_utf8_o_con_nul(self) -> None:
        c = self.cliente()
        env = c.environ("GET", "/")
        env["PATH_INFO"] = "/\xff\xfe"
        estado = []
        c.app(env, lambda linea, cab, exc=None: estado.append(linea))
        self.assertTrue(estado[0].startswith("400"))
        self.assertEqual(c.get("/app.js\x00.png").estado, 400)


class PruebaSitio(PruebaBase):
    def test_sitio_sirve_la_landing_con_csp_en_sandbox(self) -> None:
        c = self.cliente()
        r = c.get(f"/sitio/{OFERTA}/index.html", token=False)
        self.assertEqual(r.estado, 200, "sin token: el iframe no puede enviarlo")
        self.assertEqual(r.cabeceras["content-security-policy"], "sandbox allow-scripts; default-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'self'")
        self.assertEqual(r.cabeceras["content-security-policy"], CSP_SITIO)
        self.assertEqual(r.cabeceras["x-content-type-options"], "nosniff")
        self.assertEqual(r.cabeceras["x-frame-options"], "SAMEORIGIN")
        self.assertEqual(r.cabeceras["content-type"], "text/html; charset=utf-8")
        self.assertIn(b"<h1>Hola</h1>", r.cuerpo)
        self.assertEqual(c.get(f"/sitio/{OFERTA}/").cuerpo, r.cuerpo)
        self.assertEqual(c.get(f"/sitio/{OFERTA}").cuerpo, r.cuerpo)
        self.assertEqual(c.get(f"/sitio/{OFERTA}/css/estilos.css").cabeceras["content-type"], "text/css; charset=utf-8")
        self.assertEqual(c.get(f"/sitio/{OFERTA}/js/app.js").cabeceras["content-type"], "text/javascript; charset=utf-8")
        self.assertEqual(c.get(f"/sitio/{OFERTA}/legal/").estado, 200)
        self.assertEqual(c.llamar("HEAD", f"/sitio/{OFERTA}/index.html").cuerpo, b"")

    def test_sitio_solo_get_y_head(self) -> None:
        c = self.cliente()
        for metodo in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertEqual(c.llamar(metodo, f"/sitio/{OFERTA}/index.html", json_={}).estado, 405, metodo)

    def test_sitio_hostil(self) -> None:
        c = self.cliente()
        self.escribir(f"ofertas/{OFERTA}/05-landing/sitio/.env", "TOKEN=x")
        self.escribir(f"ofertas/{OFERTA}/05-landing/sitio/llave.pem", "x")
        self.escribir(f"ofertas/{OFERTA}/05-landing/sitio/secretos.json", "x")
        for ruta, estados in [
            (f"/sitio/{OFERTA}/../../estado.json", (403,)), (f"/sitio/{OFERTA}/../../../../empresa/limites.yaml", (403,)),
            (f"/sitio/{OFERTA}/.env", (403,)), (f"/sitio/{OFERTA}/llave.pem", (403,)), (f"/sitio/{OFERTA}/secretos.json", (403,)),
            (f"/sitio/{OFERTA}//etc/passwd", (403, 404)), ("/sitio/", (404,)), ("/sitio/../api/sistema", (400, 404)),
            ("/sitio/OF-202611-99/index.html", (404,)), ("/sitio/OF-202611-79/index.html", (404,)),
            ("/sitio/mala%20oferta/index.html", (400,)), (f"/sitio/{OFERTA}/css", (404, 200)),
        ]:
            r = c.get(ruta)
            self.assertIn(r.estado, estados, ruta)
            self.assertNotIn(b"TOKEN=x", r.cuerpo)
            self.assertNotIn(b"moneda_limites", r.cuerpo)

    def test_sitio_con_enlace_que_escapa(self) -> None:
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "dato.html").write_text("<p>secreto</p>")
        os.symlink(fuera, self.raiz / "ofertas" / OFERTA / "05-landing" / "sitio" / "salida")
        os.symlink(fuera / "dato.html", self.raiz / "ofertas" / OFERTA / "05-landing" / "sitio" / "dato.html")
        c = self.cliente()
        for ruta in (f"/sitio/{OFERTA}/salida/dato.html", f"/sitio/{OFERTA}/dato.html"):
            r = c.get(ruta)
            self.assertEqual(r.estado, 403, ruta)
            self.assertNotIn(b"secreto", r.cuerpo)


class PruebaResolvedor(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.base = self.raiz / "ofertas" / OFERTA

    def test_rechaza_rutas_hostiles(self) -> None:
        for ruta in ("..", "../x", "a/../../x", "/etc/passwd", "~/x", "C:/x", "a\\b", "a\x00b", "a\nb", ".env", "sub/.env", ".git/config",
                     "secretos.txt", "SECRETOS.JSON", "clave.pem", "x.KEY", "id_rsa", "id_ed25519.pub", "credentials.json", "datos.sqlite",
                     "a/" + "b" * 500, "x.env"):
            with self.assertRaises(ErrorHttp, msg=ruta) as cm:
                resolver(self.base, ruta)
            self.assertEqual(cm.exception.estado, 403, ruta)

    def test_acepta_rutas_normales_y_normaliza(self) -> None:
        self.assertEqual(resolver(self.base, "estado.json"), Path(os.path.realpath(self.base / "estado.json")))
        self.assertEqual(resolver(self.base, "./01-descubrimiento//informe.md"), Path(os.path.realpath(self.base / "01-descubrimiento/informe.md")))
        self.assertEqual(resolver(self.base, ""), Path(os.path.realpath(self.base)))
        with self.assertRaises(ErrorHttp) as cm:
            resolver(self.base, "no-existe.md")
        self.assertEqual(cm.exception.estado, 404)
        self.assertEqual(resolver(self.base, "no-existe.md", debe_existir=False).name, "no-existe.md")

    def test_enlaces_simbolicos(self) -> None:
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "a.txt").write_text("a")
        os.symlink(fuera, self.base / "dir_fuera")
        os.symlink(fuera / "a.txt", self.base / "archivo_fuera")
        os.symlink("/etc/passwd", self.base / "passwd")
        os.symlink(self.base / "estado.json", self.base / "interno.json")
        os.symlink(self.base / "estado.json", self.base / "oculto_interno")
        (self.base / "enlace_a_prohibido").symlink_to(self.base / "00-brief.yaml")
        for ruta in ("dir_fuera", "dir_fuera/a.txt", "archivo_fuera", "passwd"):
            with self.assertRaises(ErrorHttp, msg=ruta) as cm:
                resolver(self.base, ruta)
            self.assertEqual(cm.exception.estado, 403, ruta)
        self.assertEqual(resolver(self.base, "interno.json").name, "estado.json", "un enlace interno se resuelve a su destino real")
        # un enlace interno cuyo DESTINO es un archivo de secretos tampoco se lee
        (self.base / "secretos.txt").write_text("s")
        os.symlink(self.base / "secretos.txt", self.base / "inocente.txt")
        with self.assertRaises(ErrorHttp) as cm:
            resolver(self.base, "inocente.txt")
        self.assertEqual(cm.exception.estado, 403)

    def test_limite_externo(self) -> None:
        fuera = self.tmp / "otra_raiz"
        fuera.mkdir()
        os.symlink(fuera, self.raiz / "ofertas" / "OF-202611-90")
        with self.assertRaises(ErrorHttp) as cm:
            resolver(self.raiz / "ofertas" / "OF-202611-90", "x.md", limite=self.raiz, debe_existir=False)
        self.assertEqual(cm.exception.estado, 403)

    def test_es_nombre_prohibido(self) -> None:
        for n in (".env", ".env.local", ".DS_Store", "a.pem", "A.KEY", "secretos", "secretos-prod.yaml", "secrets.json", "id_rsa", "x.db"):
            self.assertTrue(es_nombre_prohibido(n), n)
        for n in ("estado.json", "informe.md", "env.md", "keyboard.js", "turkey.txt", "secretaria.md", "pemex.md", "monkey.json"):
            self.assertFalse(es_nombre_prohibido(n), n)


class PruebaArchivoHostil(PruebaBase):
    def ruta(self, valor: str) -> str:
        from urllib.parse import quote
        return f"ruta={quote(valor, safe='')}"

    def test_endpoint_archivo_rechaza_rutas_hostiles(self) -> None:
        c = self.cliente()
        self.escribir(f"ofertas/{OFERTA}/.env", "TOKEN=x")
        self.escribir(f"ofertas/{OFERTA}/secretos.txt", "clave")
        self.escribir(f"ofertas/{OFERTA}/llave.pem", "k")
        for valor in ("../OF-202611-78/estado.json", "../../empresa/limites.yaml", "/etc/passwd", "..", "....//x",
                     ".env", "secretos.txt", "llave.pem", "a\\..\\b", "x\x00y", "~root/.ssh/id_rsa"):
            r = c.get(f"/api/oferta/{OFERTA}/archivo", consulta=self.ruta(valor))
            self.assertEqual(r.estado, 403, valor)
            texto = r.cuerpo.decode()
            self.assertNotIn("TOKEN=x", texto)
            self.assertNotIn(str(self.raiz), texto)

    def test_no_hay_doble_decodificacion(self) -> None:
        # «%2e%2e» llegado ya decodificado una vez es un NOMBRE literal, no un «..»: no sale de la oferta ni lee nada.
        r = self.cliente().get(f"/api/oferta/{OFERTA}/archivo", consulta=self.ruta("%2e%2e/%2e%2e/x.md"))
        self.assertEqual(r.estado, 200)
        self.assertTrue(r.json()["vacio"])
        r = self.cliente().get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=%2e%2e/%2e%2e/empresa/limites.yaml")
        self.assertEqual(r.estado, 403, "una sola decodificación (la de la consulta) ya produce «..»")

    def test_enlaces_y_fifo_en_el_endpoint_archivo(self) -> None:
        c = self.cliente()
        base = self.raiz / "ofertas" / OFERTA
        os.symlink("/etc/hosts", base / "hosts.txt")
        self.assertEqual(c.get(f"/api/oferta/{OFERTA}/archivo", consulta=self.ruta("hosts.txt")).estado, 403)
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "s.txt").write_text("secreto")
        os.symlink(fuera, base / "carpeta_fuera")
        r = c.get(f"/api/oferta/{OFERTA}/archivo", consulta=self.ruta("carpeta_fuera/s.txt"))
        self.assertEqual(r.estado, 403)
        self.assertNotIn(b"secreto", r.cuerpo)
        os.mkfifo(base / "tuberia.txt")
        r = c.get(f"/api/oferta/{OFERTA}/archivo", consulta=self.ruta("tuberia.txt"))
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (400, "no_es_archivo"), "un FIFO no debe colgar el servidor")

    def test_oferta_que_es_un_enlace_hacia_fuera_no_se_lee_ni_se_lista(self) -> None:
        fuera = self.tmp / "otra"
        (fuera / "05-landing" / "sitio").mkdir(parents=True)
        (fuera / "estado.json").write_text('{"oferta_id": "OF-202611-90", "fase": "robada"}')
        (fuera / "05-landing" / "sitio" / "index.html").write_text("<p>robado</p>")
        os.symlink(fuera, self.raiz / "ofertas" / "OF-202611-90")
        c = self.cliente()
        self.assertNotIn("OF-202611-90", [f["oferta_id"] for f in c.get("/api/ofertas").datos])
        d = c.get("/api/oferta/OF-202611-90")
        self.assertNotIn(b"robada", d.cuerpo)
        self.assertEqual(c.get("/api/oferta/OF-202611-90/archivo", consulta=self.ruta("estado.json")).estado, 403)
        s = c.get("/sitio/OF-202611-90/index.html")
        self.assertNotEqual(s.estado, 200)
        self.assertNotIn(b"robado", s.cuerpo)


if __name__ == "__main__":
    unittest.main()
