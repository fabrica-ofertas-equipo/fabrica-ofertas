"""Correcciones de la revisión de seguridad independiente (docs/_historial/panel-revision-seguridad.md): M-1, M-2 y menores de backend."""
from __future__ import annotations

import base64
import http.client
import io
import json
import logging
import os
import re
import shutil
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import yaml

from dashboard.api import ApiServicio, firmar
from dashboard.archivos import _CACHE, Raiz, TOPE_JSON, cargar_json_estricto, es_nombre_prohibido
from dashboard.seguridad import CSP_SITIO, ErrorHttp, cabeceras_json, cabeceras_panel, cabeceras_sitio, leer_cuerpo_con_plazo, parsear_longitud
from dashboard.servidor import Panel, crear_servidor, reescribir_rutas
from datos.db import conectar, migrar
from tests.dashboard.test_servidor_api_servicio import AHORA, OFERTA as OFERTA_API, PARAMS, SECRETO, TS, BaseApi, canonico
from tests.dashboard.test_servidor_apoyo import Cliente, FIXTURES, OFERTA, PruebaBase, RAIZ_REPO, reloj_fijo

SITIO = f"ofertas/{OFERTA}/05-landing/sitio"

# Las expresiones ORIGINALES (cuadráticas) para comprobar que la salida nueva es idéntica en contenido real.
_VIEJAS = (
    re.compile(r"""(\b(?:href|src|action|formaction|poster|data-src)\s*=\s*)(["'])(/(?!/)[^"']*)\2""", re.IGNORECASE),
    re.compile(r"""(\bsrcset\s*=\s*)(["'])([^"']*)\2""", re.IGNORECASE),
    re.compile(r"""url\(\s*(["']?)(/(?!/)[^)"']*)\1\s*\)""", re.IGNORECASE),
    re.compile(r"""(@import\s+)(["'])(/(?!/)[^"']*)\2""", re.IGNORECASE),
)


def reescribir_viejo(contenido: bytes, prefijo: str, mime: str) -> bytes:
    tipo = mime.split(";")[0].strip()
    if tipo not in ("text/html", "text/css"):
        return contenido
    texto = contenido.decode("utf-8", "surrogateescape")

    def nueva(ruta: str) -> str:
        return ruta if ruta == prefijo or ruta.startswith(prefijo + "/") else prefijo + ruta

    if tipo == "text/html":
        texto = _VIEJAS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}{nueva(m.group(3))}{m.group(2)}", texto)
        texto = _VIEJAS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}" + ", ".join(
            nueva(c.strip()) if c.strip().startswith("/") and not c.strip().startswith("//") else c.strip() for c in m.group(3).split(",")) + m.group(2), texto)
    texto = _VIEJAS[2].sub(lambda m: f"url({m.group(1)}{nueva(m.group(2))}{m.group(1)})", texto)
    texto = _VIEJAS[3].sub(lambda m: f"{m.group(1)}{m.group(2)}{nueva(m.group(3))}{m.group(2)}", texto)
    return texto.encode("utf-8", "surrogateescape")


class PruebaM1Redos(PruebaBase):
    def test_url_repetido_sin_cierre_no_congela(self) -> None:
        for mime in ("text/css", "text/html"):
            entrada = b"url(/" * 16000          # 80 KB: con la expresión original ≈ 8 s (cuadrático)
            t0 = time.monotonic()
            reescribir_rutas(entrada, "/sitio/OF-1", mime)
            self.assertLess(time.monotonic() - t0, 1.5, mime)

    def test_una_peticion_hostil_por_http_no_bloquea_al_resto(self) -> None:
        self.escribir(f"{SITIO}/css/hostil.css", "url(/" * 12000)    # 60 KB
        c = self.cliente()
        t0 = time.monotonic()
        r = c.get(f"/sitio/{OFERTA}/css/hostil.css")
        self.assertEqual(r.estado, 200)
        self.assertLess(time.monotonic() - t0, 2.0, "antes: 4,6 s con el proceso entero congelado")

    def test_salida_identica_en_las_landings_reales_y_de_prueba(self) -> None:
        archivos = [p for base in (RAIZ_REPO / "ofertas", self.raiz / "ofertas") for p in base.rglob("*")
                    if p.is_file() and p.suffix in (".html", ".css") and "05-landing" in p.parts]
        self.assertGreaterEqual(len(archivos), 8)
        for ruta in archivos:
            mime = "text/css" if ruta.suffix == ".css" else "text/html; charset=utf-8"
            datos = ruta.read_bytes()
            self.assertEqual(reescribir_rutas(datos, "/sitio/OF-9", mime), reescribir_viejo(datos, "/sitio/OF-9", mime), ruta.name)

    def test_archivos_de_mas_de_2_mb_se_sirven_sin_reescribir(self) -> None:
        grande = b"a{background:url(/x.png)}\n" * 90000      # > 2 MB
        self.assertGreater(len(grande), 2 * 1024 * 1024)
        self.assertEqual(reescribir_rutas(grande, "/sitio/OF-1", "text/css"), grande)
        chico = b"a{background:url(/x.png)}"
        self.assertIn(b"/sitio/OF-1/x.png", reescribir_rutas(chico, "/sitio/OF-1", "text/css"))


class PruebaM2Ingresar(unittest.TestCase):
    """``POST /ingresar`` contra el ``engine.orq`` REAL (antes: TypeError → 500 siempre)."""

    def setUp(self) -> None:
        from tests.engine import apoyo
        from tests.engine.apoyo_orq import candidatos_ejemplo, pre_brief
        p = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        p.start()
        self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="ingresar-real-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.emp = apoyo.crear_empresa(self.tmp, entorno="desarrollo", modo_infra="prueba")
        self.raiz = self.emp.raiz
        (self.raiz / "empresa" / "autonomia.yaml").unlink(missing_ok=True)
        self.candidatos = candidatos_ejemplo()
        self.pre_brief = pre_brief
        logger = logging.getLogger("dashboard.api")
        nivel = logger.level
        logger.setLevel(logging.CRITICAL)
        self.addCleanup(logger.setLevel, nivel)

    def con_parametro_ingesta(self, cuerpo_max: int | None = 1_000_000) -> None:
        ruta = self.raiz / "empresa" / "parametros.yaml"
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))

        def entrada(valor, unidad):
            return {"valor": valor, "unidad": unidad, "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}

        datos["grupos"]["ingesta"] = {"tolerancia_seg": entrada(120, "segundos"), "cuerpo_max_bytes": entrada(cuerpo_max, "bytes"),
                                      "contexto_ttl_seg": entrada(3600, "segundos")}
        ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def crear_oferta(self) -> str:
        from engine import orq
        ruta = self.tmp / "pre-brief.yaml"
        ruta.write_text(yaml.safe_dump(self.pre_brief(nivel_autonomia="N4", slug="prueba-api"), sort_keys=False, allow_unicode=True), encoding="utf-8")
        return orq.crear(ruta_brief=ruta, raiz=self.raiz, ahora=self.emp.reloj)["oferta_id"]

    def app(self) -> ApiServicio:
        return ApiServicio(self.raiz, secreto=SECRETO, parametros={"tolerancia_seg": 120, "cuerpo_max_bytes": 2048},
                           ahora=lambda: self.emp.reloj(), env=self.emp.env)

    def enviar(self, app: ApiServicio, cuerpo: bytes) -> tuple[int, dict]:
        ts = self.emp.reloj().strftime("%Y-%m-%dT%H:%M:%SZ")
        env = {"REQUEST_METHOD": "POST", "PATH_INFO": "/ingresar", "wsgi.input": io.BytesIO(cuerpo), "CONTENT_LENGTH": str(len(cuerpo)),
               "HTTP_X_FABRICA_TS": ts, "HTTP_X_FABRICA_FIRMA": firmar(SECRETO, cuerpo, ts, "req")}
        estado: list[int] = []
        salida = b"".join(app(env, lambda linea, cab, exc=None: estado.append(int(linea.split()[0]))))
        return estado[0], json.loads(salida)

    def cuerpo(self, oferta_id: str, **extra) -> bytes:
        contenido = json.dumps(self.candidatos, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return json.dumps({"oferta_id": oferta_id, "etapa": "D1", **({"archivos": [{"ruta": "01-descubrimiento/candidatos.json",
                           "contenido_b64": base64.b64encode(contenido).decode()}]} | extra)}).encode("utf-8")

    def test_cuerpo_valido_lo_ingresa_el_motor_real(self) -> None:
        self.con_parametro_ingesta()
        oferta = self.crear_oferta()
        estado, cuerpo = self.enviar(self.app(), self.cuerpo(oferta))
        self.assertEqual(estado, 200, cuerpo)
        self.assertTrue(cuerpo["ok"])
        self.assertIn("hash_salida", cuerpo["resultado"])

    def test_cuerpo_invalido_es_400_y_no_500(self) -> None:
        self.con_parametro_ingesta()
        oferta = self.crear_oferta()
        for malo in (self.cuerpo(oferta, extra_clave=1), b'{"oferta_id": "OF-202611-01"}', self.cuerpo("OF-999999-99"),
                     self.cuerpo(oferta, archivos=[{"ruta": "../x.json", "contenido_b64": "AAAA"}])):
            estado, cuerpo = self.enviar(self.app(), malo)
            self.assertIn(estado, (400, 409), cuerpo)
            self.assertIn(cuerpo["motivo"], ("ingresar_invalido", "ingresar_bloqueado"))

    def test_sin_el_parametro_del_dueno_es_500_generico_sin_nombres(self) -> None:
        oferta = self.crear_oferta()      # empresa/parametros.yaml SIN grupo ingesta
        estado, cuerpo = self.enviar(self.app(), self.cuerpo(oferta))
        self.assertEqual((estado, cuerpo), (500, {"ok": False, "motivo": "configuracion_incompleta"}))

    def test_mapeo_de_errores_del_motor_sin_typeerror(self) -> None:
        from engine import orq
        from engine.errores import ErrorBloqueado, ErrorExterno, ErrorUso, ErrorValidacion, ParametroFaltante
        app = self.app()
        for excepcion, estado, motivo in ((ErrorValidacion("x"), 400, "ingresar_invalido"), (ErrorUso("x"), 400, "ingresar_invalido"),
                                           (ErrorBloqueado("x"), 409, "ingresar_bloqueado"), (ParametroFaltante("ingesta.cuerpo_max_bytes", "falta"), 500, "configuracion_incompleta"),
                                           (ErrorExterno("x"), 502, "ingresar_externo")):
            with mock.patch.object(orq, "ingresar_desde_cuerpo", side_effect=excepcion) as m:
                e, c = self.enviar(app, b"{}")
            self.assertEqual((e, c["motivo"]), (estado, motivo), excepcion)
            self.assertEqual(len(m.call_args.args), 1, "solo el cuerpo es posicional")
            self.assertEqual(set(m.call_args.kwargs), {"raiz", "ahora", "env"})
        with mock.patch.object(orq, "ingresar_desde_cuerpo", return_value={"resultado": "ok", "hash_salida": "sha256:" + "0" * 64}):
            self.assertEqual(self.enviar(app, b"{}")[0], 200)


class PruebaM2bNombresYExtensiones(PruebaBase):
    SOSPECHOSOS = ("token.txt", "stripe_secret_key.txt", "service-account.json", "claves_api.md", "meta_access_token.json", "private_key.json",
                   "api_secret.json", "passwords.txt", "clave_privada.priv", "cert.p8", "ID_RSA", "mi-API_KEY.yaml", "credenciales.json", "llave.md")

    def leer(self, nombre: str, base: str = f"ofertas/{OFERTA}"):
        return self.cliente().get(f"/api/oferta/{OFERTA}/archivo", consulta=f"ruta={nombre}")

    def test_nombres_sospechosos_se_rechazan_aunque_la_extension_sea_inocente(self) -> None:
        for nombre in self.SOSPECHOSOS:
            self.escribir(f"ofertas/{OFERTA}/{nombre}", "contenido-sensible")
            r = self.leer(nombre)
            self.assertEqual(r.estado, 403, nombre)
            self.assertNotIn(b"contenido-sensible", r.cuerpo)
            self.assertTrue(es_nombre_prohibido(nombre), nombre)

    def test_lo_legitimo_sigue_leyendose(self) -> None:
        for nombre in ("informe.md", "privacidad.html", "puente-de-la-pausa-v1-guia.md", "secretaria.md", "kpi_oferta_dia.json", "turkey.txt"):
            self.escribir(f"ofertas/{OFERTA}/{nombre}", "ok")
            self.assertEqual(self.leer(nombre).estado, 200, nombre)
            self.assertFalse(es_nombre_prohibido(nombre), nombre)

    def test_enlace_duro_a_un_archivo_de_fuera_se_rechaza(self) -> None:
        fuera = self.raiz / "empresa" / "captura" / "freno.json"
        (self.raiz / "ofertas" / OFERTA / "notas").mkdir()
        os.link(fuera, self.raiz / "ofertas" / OFERTA / "notas" / "hard_freno.json")
        r = self.leer("notas/hard_freno.json")
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (403, "enlace_duro"))
        self.assertNotIn(b"HTTP 403", r.cuerpo)

    def test_lista_blanca_de_extensiones(self) -> None:
        for nombre in ("datos.dat", "informe.pdf", "x.bin", "LICENSE", "clave.priv", "a.exe", "dump.sqlite", "texto.log"):
            self.escribir(f"ofertas/{OFERTA}/{nombre}", "x")
            r = self.leer(nombre)
            self.assertEqual(r.estado, 403, nombre)
        for nombre in ("a.json", "a.jsonl", "a.md", "a.yaml", "a.yml", "a.html", "a.htm", "a.txt", "a.css", "a.js", "a.csv", "a.PNG", "a.jpg"):
            self.escribir(f"ofertas/{OFERTA}/{nombre}", "x")
            self.assertEqual(self.leer(nombre).estado, 200, nombre)

    def test_vale_tambien_para_el_archivo_de_skills(self) -> None:
        self.escribir(".claude/skills/f9-demo/SKILL.md", "# s")
        self.escribir(".claude/skills/f9-demo/token.txt", "sensible")
        self.escribir(".claude/skills/f9-demo/datos.bin", "x")
        c = self.cliente()
        self.assertEqual(c.get("/api/skills/f9-demo/archivo", consulta="ruta=SKILL.md").estado, 200)
        self.assertEqual(c.get("/api/skills/f9-demo/archivo", consulta="ruta=token.txt").estado, 403)
        self.assertEqual(c.get("/api/skills/f9-demo/archivo", consulta="ruta=datos.bin").estado, 403)


class PruebaM3Csp(PruebaBase):
    def test_csp_del_sitio_bloquea_data_en_scripts_y_estilos_en_linea(self) -> None:
        csp = cabeceras_sitio("text/html")
        valor = dict(csp)["Content-Security-Policy"]
        self.assertEqual(valor, CSP_SITIO)
        self.assertEqual(valor, "sandbox allow-scripts; default-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'self'")
        directivas = {d.split()[0]: d.split()[1:] for d in valor.split("; ")}
        self.assertNotIn("data:", directivas["default-src"], "un <script src=data:…> ejecutaba dentro del sandbox")
        self.assertNotIn("script-src", directivas, "los scripts caen en default-src 'self'")
        self.assertIn("data:", directivas["img-src"])
        self.assertNotIn("allow-same-origin", valor)
        self.assertNotIn("unsafe-inline", directivas["style-src"])

    def test_corp_de_la_vista_previa_permite_los_subrecursos_del_sandbox(self) -> None:
        self.assertEqual(dict(cabeceras_sitio("text/css"))["Cross-Origin-Resource-Policy"], "cross-origin")
        r = self.cliente().get(f"/sitio/{OFERTA}/css/estilos.css")
        self.assertEqual(r.cabeceras["cross-origin-resource-policy"], "cross-origin")
        self.assertEqual(sum(1 for k, _ in cabeceras_sitio("x") if k == "Cross-Origin-Resource-Policy"), 1)
        # el resto sigue «same-origin»
        self.assertEqual(dict(cabeceras_json())["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertEqual(dict(cabeceras_panel("text/html"))["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertEqual(self.cliente().get("/api/sistema").cabeceras["cross-origin-resource-policy"], "same-origin")


def contexto_de(ruta: str) -> str | None:
    return "req" if ruta in ("/estado", "/ordenes", "/ingresar") else None


class PruebaM4SeparacionDeDominio(BaseApi):
    def test_la_firma_de_una_respuesta_de_estado_no_autentica_una_peticion(self) -> None:
        app = self.app(manejadores={"ingresar": lambda p: (200, {"ok": True})})
        r = self.llamar(app, "GET", "/estado", None)
        self.assertEqual(r.estado, 200)
        ts, firma = r.cabeceras["x-fabrica-ts"], r.cabeceras["x-fabrica-firma"]
        self.assertEqual(firma, firmar(SECRETO, r.cuerpo, ts, "resp"))
        self.assertNotEqual(firma, firmar(SECRETO, r.cuerpo, ts, "req"))
        self.assertNotEqual(firma, firmar(SECRETO, r.cuerpo, ts))
        # reutilizada como firma de PETICIÓN (cuerpo = la respuesta, ts = su ts): 401
        for ruta in ("/ingresar", "/ordenes"):
            r2 = self.llamar(app, "POST", ruta, r.cuerpo, ts=ts, firma=firma)
            self.assertEqual((r2.estado, r2.motivo), (401, "firma_invalida"), ruta)
        self.assertEqual(self.llamar(app, "GET", "/estado", b"", ts=ts, firma=firma).estado, 401)

    def test_estado_ordenes_e_ingresar_exigen_el_contexto_req(self) -> None:
        app = self.app(manejadores={"ingresar": lambda p: (200, {"ok": True})}, env={"FABRICA_FIRMA_PUBLICA": "x"})
        cuerpo = canonico({"a": 1})
        for ruta, metodo, cuerpo_ in (("/estado", "GET", None), ("/ingresar", "POST", cuerpo), ("/ordenes", "POST", cuerpo)):
            sin_contexto = self.llamar(app, metodo, ruta, cuerpo_, firma=firmar(SECRETO, cuerpo_ or b"", TS))
            self.assertEqual((sin_contexto.estado, sin_contexto.motivo), (401, "firma_invalida"), ruta)
            con_resp = self.llamar(app, metodo, ruta, cuerpo_, firma=firmar(SECRETO, cuerpo_ or b"", TS, "resp"))
            self.assertEqual(con_resp.estado, 401, ruta)
        self.assertEqual(self.llamar(app, "GET", "/estado", None).estado, 200)
        self.assertEqual(self.llamar(app, "POST", "/ingresar", cuerpo).estado, 200)

    def test_ingesta_evento_y_entrega_siguen_con_ts_punto_cuerpo_sin_contexto(self) -> None:
        app = self.app(manejadores={"entrega": lambda p: (200, {"ok": True})})
        cuerpo = canonico({"event_id": "x" * 12})
        self.assertEqual(self.evento(app).estado, 200, "los Workers firman ts + «.» + cuerpo")
        for ctx in ("req", "resp"):
            r = self.llamar(app, "POST", "/ingesta/evento", canonico(__import__("tests.dashboard.test_servidor_api_servicio", fromlist=["EVENTO"]).EVENTO),
                            firma=firmar(SECRETO, canonico(__import__("tests.dashboard.test_servidor_api_servicio", fromlist=["EVENTO"]).EVENTO), TS, ctx))
            self.assertEqual((r.estado, r.motivo), (401, "firma_invalida"), ctx)
        entrega = {"checkout_session_id": "cs_test_a1", "oferta_id": OFERTA_API, "estado": "entregado", "intento": 1,
                   "producto_sha256": "sha256:" + "a" * 64, "ts": "2026-11-09T11:59:00Z"}
        self.assertEqual(self.llamar(app, "POST", "/ingesta/entrega", canonico(entrega)).estado, 200)
        self.assertEqual(self.llamar(app, "POST", "/ingesta/entrega", canonico(entrega), firma=firmar(SECRETO, canonico(entrega), TS, "req")).estado, 401)

    def test_vector_de_ejemplo_del_contrato(self) -> None:
        """El ejemplo EXACTO de dashboard/CONTRATO.md §7b: S-B puede reproducirlo en otro lenguaje."""
        cuerpo = b'{"etapa":"D1","oferta_id":"OF-202611-01"}'
        esperado_req = "hmac-sha256=" + __import__("hmac").new(b"secreto-de-ejemplo", b"req.2026-11-09T12:00:00Z." + cuerpo, "sha256").hexdigest()
        self.assertEqual(firmar(b"secreto-de-ejemplo", cuerpo, "2026-11-09T12:00:00Z", "req"), esperado_req)
        contrato = (RAIZ_REPO / "dashboard" / "CONTRATO.md").read_text(encoding="utf-8")
        self.assertIn(esperado_req, contrato, "el ejemplo del contrato debe ser el valor real")
        self.assertIn(firmar(b"secreto-de-ejemplo", cuerpo, "2026-11-09T12:00:00Z", "resp"), contrato)
        self.assertIn(firmar(b"secreto-de-ejemplo", cuerpo, "2026-11-09T12:00:00Z"), contrato)

    def evento(self, app: ApiServicio):
        from tests.dashboard.test_servidor_api_servicio import EVENTO
        return self.llamar(app, "POST", "/ingesta/evento", canonico(EVENTO))


class PruebaM5ConfiguracionGenerica(BaseApi):
    def test_el_cliente_no_autenticado_no_aprende_nombres_de_variables_ni_archivos(self) -> None:
        casos = [self.app(secreto=b""), self.app(parametros={"tolerancia_seg": 120}), self.app(secreto_stripe=b"")]
        rutas = [("POST", "/ingesta/evento", b"{}"), ("POST", "/ingresar", b"{}"), ("GET", "/estado", None), ("POST", "/ordenes", b"{}"),
                 ("POST", "/webhooks/stripe", b"{}")]
        for app in casos:
            for metodo, ruta, cuerpo in rutas:
                r = self.llamar(app, metodo, ruta, cuerpo, ts=None, firma=None, cabeceras={"Stripe-Signature": "t=1,v1=2"})
                texto = r.cuerpo.decode()
                for tabu in ("INGEST_HMAC_SECRET", "STRIPE_WEBHOOK_SECRET", "parametros.yaml", "ingesta.", "FABRICA_FIRMA_PUBLICA", "empresa/"):
                    self.assertNotIn(tabu, texto, (ruta, tabu))
                if r.estado == 500:
                    self.assertEqual(r.json(), {"ok": False, "motivo": "configuracion_incompleta"}, ruta)

    def test_el_detalle_va_al_log(self) -> None:
        logging.getLogger("dashboard.api").setLevel(logging.NOTSET)
        with self.assertLogs("dashboard.api", level="ERROR") as capturado:
            self.evento_sin_secreto()
        self.assertIn("INGEST_HMAC_SECRET", "\n".join(capturado.output))

    def evento_sin_secreto(self) -> None:
        self.llamar(self.app(secreto=b""), "POST", "/ingesta/evento", b"{}")


class PruebaM6DigitosAscii(BaseApi):
    def test_stripe_signature_con_digitos_no_ascii_es_400_no_500(self) -> None:
        app = self.app()
        for t in ("²³", "٣٤٥", "１２３", "1²", "-5", "+5", "1_000", " 12", ""):
            r = self.llamar(app, "POST", "/webhooks/stripe", b"{}", ts=None, firma=None, cabeceras={"Stripe-Signature": f"t={t},v1={'0' * 64}"})
            self.assertEqual((r.estado, r.motivo), (400, "firma_stripe_invalida"), repr(t))

    def test_last_event_id_con_digitos_no_ascii_no_rompe_el_flujo(self) -> None:
        panel = Panel(self.raiz, puerto=8765, ahora=reloj_fijo(), sondeo_sse_s=0.01)
        self.addCleanup(panel.cerrar)
        c = Cliente(panel)
        for valor in ("²", "٣", "１２", "1_0", "+1", "-1", "9" * 30, " 5"):
            estado, _, flujo = c.flujo("/api/eventos", cabeceras={"Last-Event-ID": valor})
            self.assertEqual(estado, 200, repr(valor))
            self.assertEqual(next(flujo), b"retry: 3000\n: conectado\n\n")
            flujo.close()


class PruebaM7ContentLength(BaseApi):
    MALOS = ("1_0", "+5", "-5", " 5", "5 ", "0x10", "١٠", "１０", "12345678901", "1e3", "")

    def test_parsear_longitud_unitario(self) -> None:
        self.assertEqual(parsear_longitud("0"), 0)
        self.assertEqual(parsear_longitud("0000000005"), 5)
        for malo in self.MALOS[:-1]:
            with self.assertRaises(ErrorHttp, msg=malo) as cm:
                parsear_longitud(malo)
            self.assertEqual(cm.exception.estado, 400, malo)
        with self.assertRaises(ErrorHttp) as cm:
            parsear_longitud(None)
        self.assertEqual(cm.exception.estado, 411)

    def test_api_rechaza_content_length_con_guion_bajo_o_signo(self) -> None:
        app = self.app()
        cuerpo = canonico({"a": 1})
        for malo in self.MALOS[:-1]:
            r = self.llamar(app, "POST", "/ingesta/evento", cuerpo, largo=malo)
            self.assertEqual((r.estado, r.motivo), (400, "longitud_invalida"), repr(malo))

    def test_panel_rechaza_content_length_con_guion_bajo_o_signo(self) -> None:
        panel = Panel(self.raiz, puerto=8765, ahora=reloj_fijo())
        self.addCleanup(panel.cerrar)
        c = Cliente(panel)
        for malo in self.MALOS[:-1]:
            env = c.environ("POST", "/api/pulido", cuerpo=b'{"etapa": "D1", "titulo": "t"}', tipo="application/json")
            env["CONTENT_LENGTH"] = malo
            estado: list[str] = []
            cuerpo = b"".join(panel(env, lambda linea, cab, exc=None: estado.append(linea)))
            self.assertTrue(estado[0].startswith("400"), repr(malo))
            self.assertIn(b"longitud_invalida", cuerpo)
        self.assertFalse((self.raiz / "empresa" / "panel").exists())


class PruebaM8CuerpoYHilos(BaseApi):
    class Entrada:
        def __init__(self) -> None:
            self.lecturas = 0

        def read(self, n: int = -1) -> bytes:
            self.lecturas += 1
            raise AssertionError("no debe leerse el cuerpo antes de pasar las comprobaciones baratas")

    def sin_leer(self, **kw) -> tuple[int, str | None]:
        entrada = self.Entrada()
        r = self.llamar(self.app(), "POST", "/ingesta/evento", b"", entrada=entrada, largo="50", **kw)
        self.assertEqual(entrada.lecturas, 0)
        return r.estado, r.motivo

    def test_no_se_lee_el_cuerpo_si_faltan_marcas_o_el_ts_es_malo(self) -> None:
        self.assertEqual(self.sin_leer(ts=None, firma=None), (401, "firma_ausente"))
        self.assertEqual(self.sin_leer(ts=TS, firma=None), (401, "firma_ausente"))
        self.assertEqual(self.sin_leer(ts="2026-11-09 12:00:00", firma="x"), (400, "ts_invalido"))
        self.assertEqual(self.sin_leer(ts="2026-11-09T10:00:00Z", firma="x"), (400, "ts_fuera_de_tolerancia"))

    def test_stripe_tampoco_lee_el_cuerpo_si_la_cabecera_es_mala(self) -> None:
        entrada = self.Entrada()
        r = self.llamar(self.app(), "POST", "/webhooks/stripe", b"", ts=None, firma=None, entrada=entrada, largo="50",
                        cabeceras={"Stripe-Signature": "t=1,v1=" + "0" * 64})
        self.assertEqual((r.estado, r.motivo, entrada.lecturas), (400, "ts_fuera_de_tolerancia", 0))

    def test_el_cuerpo_se_lee_con_plazo_total(self) -> None:
        reloj = iter(range(0, 1000))

        class Goteo:
            def read(self, n: int = -1) -> bytes:
                return b"x"           # un byte por lectura, siempre

        with self.assertRaises(ErrorHttp) as cm:
            leer_cuerpo_con_plazo(Goteo(), 10_000, plazo_s=5.0, reloj=lambda: float(next(reloj)))
        self.assertEqual((cm.exception.estado, cm.exception.codigo), (408, "cuerpo_demasiado_lento"))
        self.assertEqual(leer_cuerpo_con_plazo(io.BytesIO(b"abc"), 3), b"abc")
        with self.assertRaises(ErrorHttp) as cm:
            leer_cuerpo_con_plazo(io.BytesIO(b"ab"), 3)
        self.assertEqual(cm.exception.codigo, "cuerpo_incompleto")

    def test_el_goteo_no_esquiva_el_plazo_con_read_que_bloquea(self) -> None:
        """M-A: ``read(n)`` de un BufferedReader bloquea hasta reunir ``n`` bytes y el plazo no se comprobaría; se usa ``read1`` (un ``recv``)."""
        reloj = iter(range(0, 1000))
        llamadas = {"read": 0, "read1": 0}

        class Socketeado:
            def read(self, n: int = -1) -> bytes:
                llamadas["read"] += 1
                raise AssertionError("read(n) bloquearía hasta reunir n bytes: debe usarse read1")

            def read1(self, n: int = -1) -> bytes:
                llamadas["read1"] += 1
                return b"x"           # lo que llegó en UN recv: un byte

        with self.assertRaises(ErrorHttp) as cm:
            leer_cuerpo_con_plazo(Socketeado(), 10_000, plazo_s=5.0, reloj=lambda: float(next(reloj)))
        self.assertEqual((cm.exception.estado, cm.exception.codigo), (408, "cuerpo_demasiado_lento"))
        self.assertEqual(llamadas["read"], 0)
        self.assertGreater(llamadas["read1"], 0)


class PruebaM8ServidorReal(PruebaBase):
    bloquear_sockets = False

    def servidor(self, **kw):
        app = self.panel(puerto=0)
        srv = crear_servidor(app, 0, **kw)
        import threading
        hilo = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        hilo.start()
        self.addCleanup(hilo.join, 5)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return app, srv

    @staticmethod
    def pedir(puerto: int, token: str, ruta: str = "/api/sistema") -> int:
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
        try:
            c.request("GET", ruta, headers={"X-Panel-Token": token})
            return c.getresponse().status
        finally:
            c.close()

    def test_pasado_el_tope_de_hilos_la_conexion_recibe_503_al_instante(self) -> None:
        app, srv = self.servidor(max_hilos=3, plazo_cabeceras=30)
        ociosas = []
        for _ in range(3):
            s = socket.create_connection(("127.0.0.1", srv.server_port), timeout=5)
            ociosas.append(s)
        time.sleep(0.3)                     # los 3 hilos están esperando la línea de petición
        t0 = time.monotonic()
        self.assertEqual(self.pedir(srv.server_port, app.token), 503)
        self.assertLess(time.monotonic() - t0, 2)
        for s in ociosas:
            s.close()
        for _ in range(50):                 # al cerrarse, el cupo se libera
            if self.pedir(srv.server_port, app.token) == 200:
                break
            time.sleep(0.1)
        else:
            self.fail("el cupo de hilos no se liberó")

    def test_una_conexion_que_no_completa_las_cabeceras_se_corta(self) -> None:
        app, srv = self.servidor(max_hilos=4, plazo_cabeceras=0.5)
        s = socket.create_connection(("127.0.0.1", srv.server_port), timeout=5)
        self.addCleanup(s.close)
        s.sendall(b"GET /api/sistema HTTP/1.1\r\nHost: 127.0.0.1\r\n")        # nunca termina las cabeceras
        t0 = time.monotonic()
        s.settimeout(5)
        try:
            datos = s.recv(1024)
        except (ConnectionResetError, socket.timeout):
            datos = b""
        self.assertEqual(datos, b"", "el servidor cierra sin responder")
        self.assertLess(time.monotonic() - t0, 3, "antes: se quedaba hasta el timeout de 30 s por operación")
        self.assertEqual(self.pedir(srv.server_port, app.token), 200)


class PruebaM9Consentimiento(BaseApi):
    def evento(self, app, **cambios):
        from tests.dashboard.test_servidor_api_servicio import EVENTO
        return self.llamar(app, "POST", "/ingesta/evento", canonico({**EVENTO, **cambios}))

    def test_sin_consentimiento_responde_200_pero_no_queda_atribuible(self) -> None:
        app = self.app()
        r = self.evento(app, event_id="evento-sin-consentimiento-1", consentimiento=False)   # un event_id que no lleva el visitor_id dentro
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "nuevo", "atribuible": False}))
        from datos.ingesta import VISITOR_SIN_ATRIBUCION
        fila = self.conn.ejecutar("SELECT visitor_id, cid, asid, adid, oferta_id, tipo, consentimiento FROM fact_evento").fetchone()
        self.assertEqual(tuple(fila), (VISITOR_SIN_ATRIBUCION, None, None, None, OFERTA_API, "PageView", 0),
                         "se cuenta en agregados, pero sin visitor_id, cid, asid ni adid")
        volcado = json.dumps([tuple(f) for f in self.conn.ejecutar("SELECT * FROM fact_evento").fetchall()])
        self.assertNotIn("visitante0123456789", volcado)
        self.assertNotIn("120210000000103", volcado)

    def test_idempotencia_y_conflicto_con_eventos_sin_atribucion(self) -> None:
        app = self.app()
        self.evento(app, event_id="evento-sin-consentimiento-1", consentimiento=False)
        r = self.evento(app, event_id="evento-sin-consentimiento-1", consentimiento=False)
        self.assertEqual((r.estado, r.json()["resultado"], r.json()["atribuible"]), (200, "duplicado", False))
        self.assertEqual(self.evento(app, event_id="evento-sin-consentimiento-1", consentimiento=False, ts="2026-11-09T11:59:31Z").estado, 409)
        self.assertEqual(self.evento(app, event_id="evento-sin-consentimiento-1", consentimiento=True).estado, 409,
                         "el mismo event_id no puede pasar de sin atribución a atribuible")
        self.assertEqual(self.conn.ejecutar("SELECT COUNT(*) FROM fact_evento").fetchone()[0], 1)

    def test_con_consentimiento_sigue_atribuible(self) -> None:
        app = self.app()
        r = self.evento(app, event_id="otro-evento-con-consent", consentimiento=True)
        self.assertEqual(r.json(), {"ok": True, "resultado": "nuevo", "atribuible": True})
        fila = self.conn.ejecutar("SELECT visitor_id, adid FROM fact_evento WHERE event_id = 'otro-evento-con-consent'").fetchone()
        self.assertEqual((fila["visitor_id"], fila["adid"]), ("visitante0123456789", "120210000000103"))


class PruebaM10Memoria(PruebaBase):
    def test_el_cache_cuenta_el_coste_en_memoria_no_los_bytes_del_archivo(self) -> None:
        for k in range(6):
            self.escribir(f"empresa/barrido/planes/j{k}.json", json.dumps({"filas": [{}] * (150_000 + k)}))   # ~1,5 MB cada uno
        emp = self.cliente().app.ctx.empresa()
        for k in range(6):
            self.assertTrue(emp.json(f"barrido/planes/j{k}.json", cache=True).ok)
        entradas, costo = _CACHE.estadisticas()
        self.assertLessEqual(entradas, 3, "como mucho 3 JSON grandes en memoria")
        tam = (self.raiz / "empresa/barrido/planes/j5.json").stat().st_size
        self.assertGreaterEqual(costo, 20 * tam, "el coste refleja la amplificación (~25×), no los bytes del archivo")

    def test_json_de_mas_de_4_mb_se_omite_con_aviso(self) -> None:
        self.assertEqual(TOPE_JSON, 4 * 1024 * 1024)
        self.escribir("empresa/barrido/planes/enorme.json", '{"filas": [' + "{}," * 1_500_000 + "{}]}")       # ~4,5 MB
        lec = self.cliente().app.ctx.empresa().json("barrido/planes/enorme.json", cache=True)
        self.assertEqual(lec.estado, "grande")
        self.assertIn("demasiado grande", lec.aviso)

    def test_ocho_json_de_7_mb_no_se_acumulan(self) -> None:
        import resource
        for k in range(8):
            self.escribir(f"empresa/barrido/planes/h{k}.json", '{"ofertas": [' + "{}," * 3_000_000 + "{}]}")     # ~9 MB: sobre el tope
        emp = self.cliente().app.ctx.empresa()
        antes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        for k in range(8):
            self.assertEqual(emp.json(f"barrido/planes/h{k}.json", cache=True).estado, "grande")
        crecimiento = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - antes
        self.assertLess(crecimiento, 200 * 1024 * 1024)


class PruebaM11Vigia(PruebaBase):
    def test_sistema_avisa_cuando_el_vigia_supera_su_tope(self) -> None:
        app = self.panel(tope_archivos_vigia=5)
        c = Cliente(app)
        base = c.get("/api/sistema").json()
        self.assertFalse(any("vigía" in a for a in base["avisos"]))
        self.assertEqual(base["datos"]["vigia"], {"tope": 5, "archivos": 0, "truncada": False})
        app.vigia.sondear()
        j = c.get("/api/sistema").json()
        self.assertTrue(j["datos"]["vigia"]["truncada"])
        self.assertEqual((j["datos"]["vigia"]["tope"], j["datos"]["vigia"]["archivos"]), (5, 5))
        self.assertTrue(any("vigía alcanzó su límite de 5 archivos" in a for a in j["avisos"]), j["avisos"])

    def test_con_holgura_no_hay_aviso(self) -> None:
        app = self.panel()
        app.vigia.sondear()
        j = Cliente(app).get("/api/sistema").json()
        self.assertFalse(j["datos"]["vigia"]["truncada"])
        self.assertFalse(any("vigía" in a for a in j["avisos"]))


if __name__ == "__main__":
    unittest.main()
