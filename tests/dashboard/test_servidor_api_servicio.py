"""API de servicio (``dashboard.api``): HMAC interno, tolerancias, 400/401/409/idempotencia, Stripe, órdenes y /estado firmado."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from dashboard.api import ApiServicio, firmar
from datos.db import conectar, migrar
from engine import comun
from tests.dashboard.test_servidor_apoyo import AHORA, FIXTURES, RAIZ_REPO, reloj_fijo

SECRETO = b"secreto-de-prueba-ingesta-0123456789"
WHSEC = b"whsec_secreto_de_prueba"  # lint-estatico: permitir=d  # secreto FICTICIO de prueba para firmar un webhook falso
PARAMS = {"tolerancia_seg": 120, "cuerpo_max_bytes": 2048}
TS = "2026-11-09T12:00:00Z"
OFERTA = "OF-202611-77"
EVENTO = {"event_id": "pv_visitante0123456789_2026-11-09T11:59:30Z", "oferta_id": OFERTA, "tipo": "PageView", "ts": "2026-11-09T11:59:30Z",
          "visitor_id": "visitante0123456789", "cid": "desconocido", "asid": "desconocido", "adid": "120210000000103", "fuente": "pixel",
          "consentimiento": True}


def canonico(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def contexto_de(ruta: str) -> str | None:
    """Contexto del HMAC por ruta: «req» en /estado, /ordenes e /ingresar; ninguno en /ingesta/* (docs/06 §4.7 tal cual)."""
    return "req" if ruta in ("/estado", "/ordenes", "/ingresar") else None


class Respuesta:
    def __init__(self, estado: int, cabeceras: dict[str, str], cuerpo: bytes) -> None:
        self.estado, self.cabeceras, self.cuerpo = estado, cabeceras, cuerpo

    def json(self) -> dict[str, Any]:
        return json.loads(self.cuerpo)

    @property
    def motivo(self) -> str | None:
        return self.json().get("motivo")


class BaseApi(unittest.TestCase):
    def setUp(self) -> None:
        p = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red: socket.socket está bloqueado"))
        p.start()
        self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="api-prueba-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.raiz = self.tmp / "repo"
        shutil.copytree(FIXTURES / "raiz", self.raiz)
        logger = logging.getLogger("dashboard.api")
        nivel = logger.level
        logger.setLevel(logging.CRITICAL)       # los 500 de configuración se registran a propósito; no ensucian la salida
        self.addCleanup(logger.setLevel, nivel)
        self.url_db = f"sqlite:///{self.tmp}/fabrica.db"
        self.conn = conectar(self.url_db)
        migrar(self.conn)
        self.addCleanup(self.conn.cerrar)

    def app(self, **kw: Any) -> ApiServicio:
        kw.setdefault("secreto", SECRETO)
        kw.setdefault("secreto_stripe", WHSEC)
        kw.setdefault("parametros", PARAMS)
        kw.setdefault("ahora", reloj_fijo())
        kw.setdefault("conexion", self.conn)
        kw.setdefault("env", {})
        return ApiServicio(self.raiz, **kw)

    @staticmethod
    def llamar(app: ApiServicio, metodo: str, ruta: str, cuerpo: bytes | None = b"", *, ts: str | None = TS, firma: str | None = "auto",
               secreto: bytes = SECRETO, cabeceras: dict[str, str] | None = None, largo: str | None = "auto", entrada: Any = None) -> Respuesta:
        env: dict[str, Any] = {"REQUEST_METHOD": metodo, "PATH_INFO": ruta, "wsgi.input": entrada or io.BytesIO(cuerpo or b""), "SERVER_NAME": "x",
                               "SERVER_PORT": "80", "wsgi.url_scheme": "http"}
        if largo == "auto":
            if metodo == "POST":
                env["CONTENT_LENGTH"] = str(len(cuerpo or b""))
        elif largo is not None:
            env["CONTENT_LENGTH"] = largo
        if ts is not None:
            env["HTTP_X_FABRICA_TS"] = ts
        if firma == "auto":
            if ts is not None:
                env["HTTP_X_FABRICA_FIRMA"] = firmar(secreto, cuerpo or b"", ts, contexto_de(ruta))
        elif firma is not None:
            env["HTTP_X_FABRICA_FIRMA"] = firma
        for k, v in (cabeceras or {}).items():
            env["HTTP_" + k.upper().replace("-", "_")] = v
        estado: list[Any] = []
        cuerpo_resp = b"".join(app(env, lambda linea, cab, exc=None: estado.append((int(linea.split()[0]), {k.lower(): v for k, v in cab}))))
        return Respuesta(estado[0][0], estado[0][1], cuerpo_resp)

    def evento(self, app: ApiServicio, cuerpo: dict[str, Any] | None = None, **kw: Any) -> Respuesta:
        return self.llamar(app, "POST", "/ingesta/evento", canonico(cuerpo or EVENTO), **kw)

    def filas(self) -> int:
        return self.conn.ejecutar("SELECT COUNT(*) FROM fact_evento").fetchone()[0]


class PruebaFirmaYTolerancia(BaseApi):
    def test_la_firma_sin_contexto_coincide_con_la_convencion_de_infra_y_los_workers(self) -> None:
        from infra.firma_servicio import cabeceras_internas
        cuerpo = canonico(EVENTO)
        self.assertEqual(firmar(SECRETO, cuerpo, TS), cabeceras_internas(SECRETO, cuerpo, TS)["X-Fabrica-Firma"])
        self.assertNotEqual(firmar(SECRETO, cuerpo, TS, "req"), firmar(SECRETO, cuerpo, TS), "el contexto cambia el mensaje firmado")
        esperado = "hmac-sha256=" + hmac.new(SECRETO, TS.encode() + b"." + cuerpo, hashlib.sha256).hexdigest()
        self.assertEqual(firmar(SECRETO, cuerpo, TS), esperado)

    def test_firma_valida_pasa_y_falsa_vencida_o_alterada_no(self) -> None:
        app = self.app()
        self.assertEqual(self.evento(app).estado, 200)
        cuerpo = canonico(EVENTO)
        buena = firmar(SECRETO, cuerpo, TS)
        casos = {
            "firma_falsa": buena[:-1] + ("0" if buena[-1] != "0" else "1"),
            "otra_clave": firmar(b"otra-clave", cuerpo, TS),
            "firma_de_otro_cuerpo": firmar(SECRETO, canonico({**EVENTO, "tipo": "ViewContent"}), TS),
            "firma_de_otro_ts": firmar(SECRETO, cuerpo, "2026-11-09T11:59:59Z"),
            "sin_prefijo": buena.split("=", 1)[1], "prefijo_viejo": buena.replace("hmac-sha256=", "hmac-sha256:"), "vacia": " ",
            "mayusculas": buena.upper(), "basura": "x" * 500, "no_ascii": "hmac-sha256=ñ" * 4,
        }
        for nombre, firma in casos.items():
            r = self.llamar(app, "POST", "/ingesta/evento", cuerpo, firma=firma)
            self.assertEqual((r.estado, r.motivo), (401, "firma_invalida"), nombre)
        self.assertEqual(self.filas(), 1, "ninguna petición falsa dejó rastro")

    def test_sin_cabeceras_de_firma_es_401(self) -> None:
        app = self.app()
        cuerpo = canonico(EVENTO)
        for kw in ({"ts": None, "firma": None}, {"firma": None}, {"ts": None, "firma": "hmac-sha256=" + "0" * 64}):
            r = self.llamar(app, "POST", "/ingesta/evento", cuerpo, **kw)
            self.assertEqual((r.estado, r.motivo), (401, "firma_ausente"), kw)

    def test_tolerancia_de_la_marca_de_tiempo(self) -> None:
        app = self.app()
        cuerpo = canonico(EVENTO)
        for ts, estado in [("2026-11-09T11:58:00Z", 200), ("2026-11-09T12:02:00Z", 200),     # justo en ±120 s
                           ("2026-11-09T11:57:59Z", 400), ("2026-11-09T12:02:01Z", 400), ("2026-11-08T12:00:00Z", 400), ("2027-11-09T12:00:00Z", 400)]:
            r = self.llamar(app, "POST", "/ingesta/evento", cuerpo, ts=ts)
            self.assertEqual(r.estado, estado, ts)
            if estado == 400:
                self.assertEqual(r.motivo, "ts_fuera_de_tolerancia")
        for ts in ("2026-11-09 12:00:00", "2026-11-09T12:00:00+00:00", "2026-11-09T12:00:00.123Z", "2026-11-09T12:00:00", "hoy", "2026-13-40T99:99:99Z", ""):
            r = self.llamar(app, "POST", "/ingesta/evento", cuerpo, ts=ts, firma=firmar(SECRETO, cuerpo, ts))
            self.assertEqual((r.estado, r.motivo), (400, "ts_invalido") if ts else (401, "firma_ausente"), repr(ts))

    def test_ts_vencido_con_firma_valida_es_400_no_401(self) -> None:
        r = self.evento(self.app(), ts="2026-11-09T11:00:00Z")
        self.assertEqual((r.estado, r.motivo), (400, "ts_fuera_de_tolerancia"))

    def test_la_tolerancia_sale_del_parametro(self) -> None:
        app = self.app(parametros={"tolerancia_seg": 10, "cuerpo_max_bytes": 2048})
        self.assertEqual(self.evento(app, ts="2026-11-09T11:59:50Z").estado, 200)
        self.assertEqual(self.evento(app, ts="2026-11-09T11:59:49Z").estado, 400)

    def test_la_comparacion_es_en_tiempo_constante(self) -> None:
        import inspect
        import dashboard.api as api
        fuente = inspect.getsource(api)
        self.assertIn("hmac.compare_digest", fuente)
        self.assertNotIn("== firma", fuente)

    def test_fail_closed_sin_secreto_ni_parametros(self) -> None:
        for kw in ({"secreto": b""}, {"parametros": {"tolerancia_seg": 120}}, {"parametros": {"cuerpo_max_bytes": 100}}):
            app = self.app(**kw)
            r = self.evento(app)
            self.assertEqual((r.estado, r.json()), (500, {"ok": False, "motivo": "configuracion_incompleta"}), kw)
            self.assertEqual(self.filas(), 0)
        sin = self.tmp / "sin"
        (sin / "empresa").mkdir(parents=True)
        r = self.evento(ApiServicio(sin, secreto=SECRETO, ahora=reloj_fijo(), conexion=self.conn, env={}))
        self.assertEqual((r.estado, r.motivo), (500, "configuracion_incompleta"), "sin empresa/parametros.yaml no acepta nada")

    def test_parametros_desde_empresa_parametros_yaml(self) -> None:
        r = self.evento(ApiServicio(self.raiz, secreto=SECRETO, ahora=reloj_fijo(), conexion=self.conn, env={}))
        self.assertEqual(r.estado, 200)
        r = self.evento(ApiServicio(self.raiz, secreto=SECRETO, ahora=reloj_fijo(), conexion=self.conn, env={}), ts="2026-11-09T11:57:00Z")
        self.assertEqual(r.motivo, "ts_fuera_de_tolerancia", "tolerancia 120 s del archivo")

    def test_secretos_desde_el_entorno_inyectado(self) -> None:
        app = ApiServicio(self.raiz, parametros=PARAMS, ahora=reloj_fijo(), conexion=self.conn, env={"INGEST_HMAC_SECRET": SECRETO.decode()})
        self.assertEqual(self.evento(app).estado, 200)


class PruebaCuerpoYRutas(BaseApi):
    def test_salud_minimo_y_sin_autenticacion(self) -> None:
        r = self.llamar(self.app(secreto=b""), "GET", "/salud", None, ts=None, firma=None)
        self.assertEqual((r.estado, r.json()), (200, {"ok": True}))
        self.assertEqual(r.cabeceras["content-type"], "application/json; charset=utf-8")
        self.assertEqual(r.cabeceras["x-content-type-options"], "nosniff")
        self.assertEqual(self.llamar(self.app(), "POST", "/salud", b"{}", ts=None, firma=None).estado, 405)

    def test_head_salud_no_lleva_cuerpo_y_los_405_dicen_allow(self) -> None:
        app = self.app(secreto=b"")
        h = self.llamar(app, "HEAD", "/salud", None, ts=None, firma=None)
        self.assertEqual((h.estado, h.cuerpo), (200, b""))
        self.assertEqual(h.cabeceras["content-length"], str(len(b'{"ok":true}')), "HEAD conserva el Content-Length del GET")
        self.assertEqual(self.llamar(app, "POST", "/salud", b"{}", ts=None, firma=None).cabeceras["allow"], "GET, HEAD")
        self.assertEqual(self.llamar(self.app(), "POST", "/estado", b"{}").cabeceras["allow"], "GET")
        self.assertEqual(self.llamar(self.app(), "GET", "/ordenes", None).cabeceras["allow"], "POST")

    def test_un_manejador_con_codigo_no_estandar_no_rompe_la_respuesta(self) -> None:
        app = self.app(manejadores={"evento": lambda p: (299, {"ok": True})})
        r = self.evento(app)
        self.assertEqual((r.estado, r.json()), (299, {"ok": True}))

    def test_repr_de_la_peticion_no_filtra_secretos_del_entorno(self) -> None:
        from dashboard.api import Peticion
        import dataclasses
        valores = {f.name: None for f in dataclasses.fields(Peticion)}
        valores.update(env={"INGEST_HMAC_SECRET": "MUY-SECRETO-DE-ENTORNO"}, secreto=b"OTRO-SECRETO")
        self.assertNotIn("MUY-SECRETO-DE-ENTORNO", repr(Peticion(**valores)))
        self.assertNotIn("OTRO-SECRETO", repr(Peticion(**valores)))

    def test_puerto_de_entorno_no_numerico_cae_al_defecto(self) -> None:
        from dashboard.api import _puerto_de_entorno
        for crudo, esperado in (("9000", 9000), ("abc", 8780), ("", 8780), ("-5", 8780), ("٣", 8780), (" 7001 ", 7001)):
            with mock.patch.dict("os.environ", {"PORT": crudo}):
                self.assertEqual(_puerto_de_entorno(), esperado, crudo)

    def test_rutas_y_metodos(self) -> None:
        app = self.app()
        self.assertEqual(self.llamar(app, "POST", "/otra", b"{}").estado, 404)
        self.assertEqual(self.llamar(app, "GET", "/ingesta/evento", None).estado, 405)
        self.assertEqual(self.llamar(app, "GET", "/ordenes", None).estado, 405)
        self.assertEqual(self.llamar(app, "POST", "/estado", b"{}").estado, 405)
        self.assertEqual(self.llamar(app, "DELETE", "/ingesta/evento", b"").estado, 405)

    def test_cuerpo_sobre_el_maximo_se_rechaza_sin_leerlo(self) -> None:
        app = self.app()

        class Prohibido:
            def read(self, n: int = -1) -> bytes:
                raise AssertionError("no debe leer un cuerpo demasiado grande")

        r = self.llamar(app, "POST", "/ingesta/evento", b"", largo="2049", entrada=Prohibido())
        self.assertEqual((r.estado, r.motivo), (413, "cuerpo_demasiado_grande"))
        grande = canonico({**EVENTO, "relleno": "x" * 5000})
        r = self.llamar(app, "POST", "/ingesta/evento", grande)
        self.assertEqual(r.estado, 413)
        self.assertEqual(self.filas(), 0)

    def test_longitud_ausente_invalida_o_incompleta(self) -> None:
        app = self.app()
        cuerpo = canonico(EVENTO)
        self.assertEqual(self.llamar(app, "POST", "/ingesta/evento", cuerpo, largo=None).estado, 411)
        self.assertEqual(self.llamar(app, "POST", "/ingesta/evento", cuerpo, largo="abc").estado, 400)
        self.assertEqual(self.llamar(app, "POST", "/ingesta/evento", cuerpo, largo="-1").estado, 400)
        r = self.llamar(app, "POST", "/ingesta/evento", cuerpo, largo=str(len(cuerpo) + 50))
        self.assertEqual((r.estado, r.motivo), (400, "cuerpo_incompleto"))

    def test_cuerpo_no_json_o_no_estricto_con_firma_valida(self) -> None:
        app = self.app()
        for cuerpo in (b"{no json", b'{"a": NaN}', b"\xff\xfe", b'{"a": 1e999}', b"[" * 500):
            r = self.llamar(app, "POST", "/ingesta/evento", cuerpo)
            self.assertEqual((r.estado, r.motivo), (400, "cuerpo_no_json"), cuerpo[:10])

    def test_los_errores_no_filtran_secretos_ni_rutas_ni_trazas(self) -> None:
        def malo(p: Any) -> Any:
            raise RuntimeError(f"explotó con {SECRETO.decode()} en {self.raiz}")

        app = self.app(manejadores={"evento": malo})
        with self.assertLogs("dashboard.api", level="ERROR"):
            r = self.evento(app)
        self.assertEqual((r.estado, r.motivo), (500, "error_interno"))
        texto = r.cuerpo.decode()
        self.assertNotIn(SECRETO.decode(), texto)
        self.assertNotIn(str(self.raiz), texto)
        self.assertNotIn("Traceback", texto)


class PruebaEvento(BaseApi):
    def test_nuevo_duplicado_y_conflicto(self) -> None:
        app = self.app()
        r = self.evento(app)
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "nuevo", "atribuible": True}))
        fila = self.conn.ejecutar("SELECT event_id, oferta_id, tipo, ts, visitor_id, cid, asid, adid, fuente, consentimiento FROM fact_evento").fetchone()
        self.assertEqual(tuple(fila), (EVENTO["event_id"], OFERTA, "PageView", "2026-11-09T11:59:30Z", "visitante0123456789", "desconocido",
                                       "desconocido", "120210000000103", "pixel", 1), "fact_evento guarda cid, asid, adid, fuente y consentimiento")
        r = self.evento(app)
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "duplicado", "atribuible": True}))
        r = self.evento(app, {**EVENTO, "ts": "2026-11-09T11:59:31Z"})
        self.assertEqual((r.estado, r.motivo), (409, "event_id_con_otro_contenido"))
        r = self.evento(app, {**EVENTO, "adid": "120210000000999"})
        self.assertEqual(r.estado, 409)
        self.assertEqual(self.filas(), 1)
        r = self.evento(app, {**EVENTO, "event_id": "pv_visitante0123456789_otro_000001"})
        self.assertEqual((r.estado, r.json()["resultado"]), (200, "nuevo"))
        self.assertEqual(self.filas(), 2)

    def test_tipos_y_campos_opcionales(self) -> None:
        app = self.app()
        for k, tipo in enumerate(("PageView", "ViewContent", "InitiateCheckout", "Purchase")):
            cuerpo = {**EVENTO, "event_id": f"evento-{tipo}-{k:08d}", "tipo": tipo, "fuente": "capi"}
            if tipo == "Purchase":
                cuerpo.update({"valor_minor": 1990, "moneda": "EUR"})
            self.assertEqual(self.evento(app, cuerpo).estado, 200, tipo)
        sin_atrib = {k: v for k, v in EVENTO.items() if k not in ("cid", "asid", "adid")}
        self.assertEqual(self.evento(app, {**sin_atrib, "event_id": "sin-atribucion-00001"}).estado, 200)
        fila = self.conn.ejecutar("SELECT adid, cid FROM fact_evento WHERE event_id = 'sin-atribucion-00001'").fetchone()
        self.assertEqual((fila[0], fila[1]), (None, None), "lo que no llega queda nulo (no se inventa «desconocido»)")

    def test_validacion_estricta_sin_datos_personales(self) -> None:
        app = self.app()
        malos = [
            {**EVENTO, "email": "a@b.c"}, {**EVENTO, "ip": "1.2.3.4"}, {**EVENTO, "nombre": "x"}, {**EVENTO, "tipo": "Lead"}, {**EVENTO, "tipo": "pageview"},
            {**EVENTO, "oferta_id": "_ejemplo"}, {**EVENTO, "oferta_id": "OF-1"}, {**EVENTO, "ts": "2026-11-09 11:59:30"}, {**EVENTO, "visitor_id": "corto"},
            {**EVENTO, "event_id": "x"}, {**EVENTO, "event_id": "a b c d e f g h"}, {**EVENTO, "adid": "abc"}, {**EVENTO, "cid": 123456},
            {**EVENTO, "fuente": "email"}, {**EVENTO, "consentimiento": "1"}, {**EVENTO, "consentimiento": 1}, {**EVENTO, "valor_minor": 100},
            {**EVENTO, "valor_minor": -1, "moneda": "EUR"}, {**EVENTO, "valor_minor": 1.5, "moneda": "EUR"}, {**EVENTO, "valor_minor": True, "moneda": "EUR"},
            {**EVENTO, "valor_minor": 1, "moneda": "eur"}, {k: v for k, v in EVENTO.items() if k != "consentimiento"},
        ]
        for cuerpo in malos:
            r = self.evento(app, cuerpo)
            self.assertEqual((r.estado, r.motivo), (400, "evento_invalido"), cuerpo)
        self.assertEqual(self.llamar(app, "POST", "/ingesta/evento", b"[1]").motivo, "evento_invalido")
        self.assertEqual(self.llamar(app, "POST", "/ingesta/evento", b"null").estado, 400)
        self.assertEqual(self.filas(), 0)
        problemas = self.evento(app, {**EVENTO, "email": "a@b.c"}).json()["problemas"]
        self.assertIn("campo no permitido: email", problemas)
        self.assertNotIn("a@b.c", json.dumps(problemas), "el dato personal no se devuelve")

    def test_texto_hostil_en_ids_se_rechaza_sin_ejecutarse(self) -> None:
        app = self.app()
        for hostil in ("<script>alert(1)</script>", "x'); DROP TABLE fact_evento;--", "../../etc/passwd", "a‮b"):
            r = self.evento(app, {**EVENTO, "event_id": hostil + "-0123456789"})
            self.assertEqual(r.estado, 400, hostil)
        self.assertEqual(self.filas(), 0)
        self.assertEqual(self.conn.ejecutar("SELECT COUNT(*) FROM sqlite_master WHERE name = 'fact_evento'").fetchone()[0], 1)

    def test_idempotencia_bajo_concurrencia(self) -> None:
        resultados, errores = [], []
        app = self.app(conexion=lambda: conectar(self.url_db))

        def enviar() -> None:
            try:
                resultados.append(self.evento(app).json().get("resultado"))
            except Exception as exc:  # noqa: BLE001
                errores.append(exc)

        hilos = [threading.Thread(target=enviar) for _ in range(10)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        self.assertEqual(resultados.count("nuevo"), 1, resultados)
        self.assertEqual(resultados.count("duplicado"), 9)
        self.assertEqual(self.filas(), 1)

    def test_sin_conexion_inyectada_usa_la_base_de_la_raiz_temporal(self) -> None:
        app = ApiServicio(self.raiz, secreto=SECRETO, parametros=PARAMS, ahora=reloj_fijo(), env={})
        self.assertEqual(self.evento(app).estado, 200)
        self.assertTrue((self.raiz / "empresa" / "datos" / "fabrica.db").is_file())
        self.assertEqual(self.evento(app).json()["resultado"], "duplicado")


class PruebaEntregaIngresarYAdaptadores(BaseApi):
    ENTREGA = {"checkout_session_id": "cs_test_a1b2c3", "oferta_id": OFERTA, "estado": "entregado", "intento": 1,
               "producto_sha256": "sha256:" + "a" * 64, "ts": "2026-11-09T11:59:00Z"}

    def entrega(self, app: ApiServicio, cuerpo: dict[str, Any] | None = None) -> Respuesta:
        return self.llamar(app, "POST", "/ingesta/entrega", canonico(cuerpo or self.ENTREGA))

    def test_entrega_valida_se_delega_a_un_adaptador_inyectado(self) -> None:
        vistos = []

        def adaptador(p: Any) -> tuple[int, dict]:
            vistos.append(p)
            return 200, {"ok": True, "resultado": "nuevo"}

        r = self.entrega(self.app(manejadores={"entrega": adaptador}))
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "nuevo"}))
        self.assertEqual(vistos[0].json, self.ENTREGA)
        self.assertEqual(vistos[0].cuerpo, canonico(self.ENTREGA))
        self.assertIs(vistos[0].conexion, self.conn)
        self.assertEqual(vistos[0].ahora, AHORA)

    def test_por_defecto_monta_datos_ingesta_manejar_ingesta_entrega(self) -> None:
        from engine.parametros import Parametros

        def entrada(valor: Any) -> dict:
            return {"valor": valor, "unidad": "x", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}

        par = Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {
            "ingesta": {"tolerancia_seg": entrada(120), "cuerpo_max_bytes": entrada(2048)},
            "entrega": {"enlace_vence_dias": entrada(7), "enlace_max_descargas": entrada(3)}}})
        app = self.app(parametros_datos=par)
        r = self.entrega(app)
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "nuevo"}))
        self.assertTrue((self.raiz / "ofertas" / OFERTA / "10-postcompra" / "entregas.jsonl").is_file())
        self.assertEqual(self.entrega(app).json()["resultado"], "duplicado")
        self.assertEqual(self.entrega(app, {**self.ENTREGA, "intento": 2}).json()["resultado"], "nuevo", "otra transición (intento)")
        r = self.entrega(app, {**self.ENTREGA, "producto_sha256": "sha256:" + "b" * 64})
        self.assertEqual((r.estado, r.motivo), (409, "entrega_con_otro_contenido"), "la misma transición con otro contenido")

    def test_entrega_sin_parametros_de_datos_es_500_generico(self) -> None:
        r = self.entrega(self.app())
        self.assertEqual((r.estado, r.json()), (500, {"ok": False, "motivo": "configuracion_incompleta"}))

    def test_los_adaptadores_pueden_devolver_409_y_pasa_tal_cual(self) -> None:
        r = self.entrega(self.app(manejadores={"entrega": lambda p: (409, {"ok": False, "motivo": "entrega_con_otro_contenido"})}))
        self.assertEqual((r.estado, r.motivo), (409, "entrega_con_otro_contenido"))

    def test_entrega_invalida_nunca_llega_al_adaptador(self) -> None:
        llamado = []
        app = self.app(manejadores={"entrega": lambda p: llamado.append(1) or (200, {"ok": True})})
        for malo in ({**self.ENTREGA, "estado": "pagado"}, {**self.ENTREGA, "checkout_session_id": "x"}, {**self.ENTREGA, "intento": -1},
                     {**self.ENTREGA, "producto_sha256": "abc"}, {**self.ENTREGA, "email": "a@b.c"}, {"oferta_id": OFERTA}):
            r = self.entrega(app, malo)
            self.assertEqual((r.estado, r.motivo), (400, "entrega_invalida"), malo)
        self.assertEqual(llamado, [])
        self.assertEqual(self.llamar(self.app(), "POST", "/ingesta/entrega", b"", ts=TS, firma="x" * 10).estado, 401)

    def test_ingresar_requiere_firma_con_contexto_y_admite_cuerpos_mayores(self) -> None:
        cuerpo = canonico({"cualquier": "cosa"})
        app = self.app(manejadores={"ingresar": lambda p: (200, {"ok": True})})
        self.assertEqual(self.llamar(app, "POST", "/ingresar", cuerpo, firma="hmac-sha256=" + "0" * 64).estado, 401)
        self.assertEqual(self.llamar(app, "POST", "/ingresar", cuerpo, firma=firmar(SECRETO, cuerpo, TS)).estado, 401, "sin contexto «req» no vale")
        recibido = []
        app = self.app(manejadores={"ingresar": lambda p: recibido.append(p.json) or (200, {"ok": True})})
        grande = canonico({"datos": "x" * 100_000})
        self.assertEqual(self.llamar(app, "POST", "/ingresar", grande).estado, 200, "ingresar admite cuerpos mayores que los eventos")
        self.assertEqual(recibido[0]["datos"][:3], "xxx")


class PruebaStripe(BaseApi):
    def eventos(self) -> list[dict[str, Any]]:
        return json.loads((RAIZ_REPO / "tests" / "fixtures" / "datos" / "stripe_eventos_OF-202611-01.json").read_text(encoding="utf-8"))["eventos"]

    @staticmethod
    def cabecera(cuerpo: bytes, t: int | None = None, secreto: bytes = WHSEC, extra: str = "") -> str:
        t = t if t is not None else int(AHORA.timestamp())
        firma = hmac.new(secreto, f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
        return f"t={t},v1={firma}{extra}"

    def stripe(self, app: ApiServicio, cuerpo: bytes, cabecera: str | None) -> Respuesta:
        return self.llamar(app, "POST", "/webhooks/stripe", cuerpo, ts=None, firma=None,
                           cabeceras={"Stripe-Signature": cabecera} if cabecera is not None else None)

    def test_evento_firmado_se_aplica_y_el_repetido_es_duplicado(self) -> None:
        app = self.app()
        cuerpo = canonico(self.eventos()[0])
        r = self.stripe(app, cuerpo, self.cabecera(cuerpo))
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "nuevo"}))
        self.assertEqual(self.conn.ejecutar("SELECT COUNT(*) FROM fact_pedido").fetchone()[0], 1)
        r = self.stripe(app, cuerpo, self.cabecera(cuerpo))
        self.assertEqual((r.estado, r.json()["resultado"]), (200, "duplicado"))
        self.assertEqual(self.conn.ejecutar("SELECT COUNT(*) FROM fact_pedido").fetchone()[0], 1)
        segundo = canonico(self.eventos()[1])
        self.assertEqual(self.stripe(app, segundo, self.cabecera(segundo)).json()["resultado"], "nuevo")
        reembolso = canonico(self.eventos()[5])
        self.assertEqual(self.stripe(app, reembolso, self.cabecera(reembolso)).json()["resultado"], "nuevo")
        self.assertEqual(self.stripe(app, reembolso, self.cabecera(reembolso)).json()["resultado"], "duplicado")

    def test_firma_de_stripe_falsa_ausente_o_vencida(self) -> None:
        app = self.app()
        cuerpo = canonico(self.eventos()[0])
        casos = {
            "falsa": (self.cabecera(cuerpo, secreto=b"otra"), "firma_stripe_invalida"),
            "ausente": (None, "firma_stripe_ausente"), "vacia": ("", "firma_stripe_ausente"), "sin_v1": (f"t={int(AHORA.timestamp())}", "firma_stripe_invalida"),
            "sin_t": ("v1=" + "0" * 64, "firma_stripe_invalida"), "t_no_numerico": ("t=abc,v1=" + "0" * 64, "firma_stripe_invalida"),
            "otro_cuerpo": (self.cabecera(b'{"otro": 1}'), "firma_stripe_invalida"),
            "vencida": (self.cabecera(cuerpo, t=int(AHORA.timestamp()) - 121), "ts_fuera_de_tolerancia"),
            "futura": (self.cabecera(cuerpo, t=int(AHORA.timestamp()) + 121), "ts_fuera_de_tolerancia"),
        }
        for nombre, (cab, motivo) in casos.items():
            r = self.stripe(app, cuerpo, cab)
            self.assertEqual((r.estado, r.motivo), (400, motivo), nombre)
        self.assertEqual(self.conn.ejecutar("SELECT COUNT(*) FROM fact_pedido").fetchone()[0], 0)

    def test_varias_firmas_v1_basta_una_valida_y_el_secreto_ausente_es_500(self) -> None:
        app = self.app()
        cuerpo = canonico(self.eventos()[0])
        cab = self.cabecera(cuerpo, extra=",v1=" + "f" * 64 + ",v0=" + "e" * 64)
        self.assertEqual(self.stripe(app, cuerpo, cab).estado, 200)
        r = self.stripe(self.app(secreto_stripe=b""), cuerpo, cab)
        self.assertEqual((r.estado, r.motivo), (500, "configuracion_incompleta"))

    def test_tipo_no_soportado_se_ignora_y_el_mal_formado_es_400(self) -> None:
        app = self.app()
        otro = canonico({"id": "evt_x", "type": "customer.created", "data": {"object": {}}})
        r = self.stripe(app, otro, self.cabecera(otro))
        self.assertEqual((r.estado, r.json()["resultado"]), (200, "ignorado"), "2xx: Stripe no reintenta tipos que no usamos")
        roto = canonico({"id": "evt_y", "type": "checkout.session.completed"})
        self.assertEqual(self.stripe(app, roto, self.cabecera(roto)).motivo, "evento_stripe_invalido")
        sin_tipo = canonico({"id": "evt_z"})
        self.assertEqual(self.stripe(app, sin_tipo, self.cabecera(sin_tipo)).estado, 400)
        no_json = b"{no json"
        self.assertEqual(self.stripe(app, no_json, self.cabecera(no_json)).motivo, "cuerpo_no_json")

    def test_tope_de_cuerpo_de_stripe(self) -> None:
        app = self.app()
        grande = canonico({"id": "evt_g", "type": "x", "relleno": "x" * (1024 * 1024 + 10)})
        self.assertEqual(self.stripe(app, grande, self.cabecera(grande)).estado, 413)


class PruebaOrdenes(BaseApi):
    @classmethod
    def setUpClass(cls) -> None:
        cls.claves = Path(tempfile.mkdtemp(prefix="api-claves-"))
        cls.addClassCleanup(shutil.rmtree, cls.claves, True)
        try:
            for n in ("dueno", "intruso"):
                subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "prueba", "-f", str(cls.claves / n)], check=True,
                               capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise unittest.SkipTest(f"ssh-keygen no disponible: {exc}") from exc
        cls.publica = (cls.claves / "dueno.pub").read_text().strip()

    def orden(self, clave: str = "dueno", **cambios: Any) -> dict[str, Any]:
        base = {"schema_version": "1.0.0", "accion": "aprobar_etapa", "etapa": "D3", "oferta_id": OFERTA, "hash_objetivo": "sha256:" + "a" * 64,
                "ts": "2026-11-09T11:59:00Z", "nonce": "nonce-de-prueba-0000000001"}
        base.update(cambios)
        sin_firma = {k: v for k, v in base.items() if k != "firma"}
        base["firma"] = comun.firmar_ed25519(comun.json_canonico(sin_firma), self.claves / clave)
        return base

    def enviar(self, app: ApiServicio, orden: dict[str, Any], **kw: Any) -> Respuesta:
        return self.llamar(app, "POST", "/ordenes", comun.json_canonico(orden), **kw)

    def ordenes(self) -> list[str]:
        d = self.raiz / "empresa" / "ordenes"
        return sorted(p.name for p in d.iterdir()) if d.exists() else []

    def app_o(self, **kw: Any) -> ApiServicio:
        return self.app(env={"FABRICA_FIRMA_PUBLICA": self.publica}, **kw)

    def test_orden_valida_se_registra_sin_activar_nada(self) -> None:
        app = self.app_o()
        o = self.orden()
        r = self.enviar(app, o)
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "registrada", "nonce": o["nonce"]}))
        self.assertEqual(self.ordenes(), [f"{o['nonce']}.json"])
        guardada = json.loads((self.raiz / "empresa" / "ordenes" / f"{o['nonce']}.json").read_text())
        self.assertEqual(guardada, o)
        self.assertFalse((self.raiz / "empresa" / "PAUSA").exists())

    def test_nonce_repetido_se_rechaza_y_no_se_sobrescribe(self) -> None:
        app = self.app_o()
        o = self.orden()
        self.enviar(app, o)
        antes = (self.raiz / "empresa" / "ordenes" / f"{o['nonce']}.json").read_bytes()
        r = self.enviar(app, o)
        self.assertEqual((r.estado, r.motivo), (409, "nonce_repetido"))
        otra = self.orden(hash_objetivo="sha256:" + "b" * 64)
        r = self.enviar(app, otra)
        self.assertEqual((r.estado, r.motivo), (409, "nonce_repetido"))
        self.assertEqual((self.raiz / "empresa" / "ordenes" / f"{o['nonce']}.json").read_bytes(), antes)

    def test_firma_de_otra_clave_o_alterada(self) -> None:
        app = self.app_o()
        intruso = self.orden("intruso", nonce="nonce-intruso-0000000001")
        r = self.enviar(app, intruso)
        self.assertEqual((r.estado, r.motivo), (401, "firma_de_orden_invalida"))
        alterada = self.orden()
        alterada["hash_objetivo"] = "sha256:" + "c" * 64
        r = self.enviar(app, alterada)
        self.assertEqual((r.estado, r.motivo), (401, "firma_de_orden_invalida"))
        basura = self.orden()
        basura["firma"] = "ed25519:AAAA"
        self.assertIn(self.enviar(app, basura).estado, (400, 401))
        self.assertEqual(self.ordenes(), [])

    def test_esquema_ts_y_nonce_hostil(self) -> None:
        app = self.app_o()
        for cambios in ({"nonce": "../../etc/passwd-0000000000"}, {"nonce": "CORTO"}, {"nonce": "NONCE-EN-MAYUSCULAS-000001"}, {"nonce": "a/b" * 8},
                        {"accion": "Activar"}, {"etapa": "D99"}, {"oferta_id": "OF-1"}, {"hash_objetivo": "nada"}, {"campo_extra": 1}):
            o = self.orden(**cambios)
            r = self.enviar(app, o)
            self.assertEqual((r.estado, r.motivo), (400, "orden_invalida"), cambios)
        self.assertEqual(self.ordenes(), [])
        self.assertFalse((self.raiz / "etc").exists())
        r = self.enviar(app, self.orden(ts="2026-11-09T11:00:00Z", nonce="nonce-viejo-00000000001"))
        self.assertEqual((r.estado, r.motivo), (400, "ts_fuera_de_tolerancia"))
        sin_nonce = {k: v for k, v in self.orden().items() if k != "nonce"}
        self.assertEqual(self.enviar(app, sin_nonce).motivo, "orden_invalida")
        self.assertEqual(self.llamar(app, "POST", "/ordenes", b"[1]").motivo, "orden_invalida")

    def test_exige_el_hmac_interno_ademas_de_la_firma_de_la_orden(self) -> None:
        app = self.app_o()
        o = self.orden()
        self.assertEqual(self.enviar(app, o, firma="hmac-sha256=" + "0" * 64).estado, 401)
        self.assertEqual(self.enviar(app, o, ts=None, firma=None).estado, 401)
        self.assertEqual(self.ordenes(), [])

    def test_sin_clave_publica_no_acepta_nada(self) -> None:
        r = self.enviar(self.app(env={}), self.orden())
        self.assertEqual((r.estado, r.motivo), (500, "configuracion_incompleta"))
        self.assertEqual(self.ordenes(), [])


class PruebaEstadoFirmado(BaseApi):
    def test_estado_exige_firma_de_la_peticion_y_firma_la_respuesta(self) -> None:
        app = self.app()
        r = self.llamar(app, "GET", "/estado", None)
        self.assertEqual(r.estado, 200)
        ts, firma = r.cabeceras["x-fabrica-ts"], r.cabeceras["x-fabrica-firma"]
        self.assertEqual(ts, TS)
        self.assertEqual(firma, firmar(SECRETO, r.cuerpo, ts, "resp"), "el lector verifica la respuesta con el secreto y el contexto «resp»")
        d = r.json()
        self.assertEqual((d["ok"], d["ts"], d["pausa"]["activa"]), (True, TS, False))
        self.assertEqual(d["infra"]["semaforo"], "VERDE")
        self.assertEqual(d["freno_captura"]["activo"], True)
        (self.raiz / "empresa" / "PAUSA").write_text("{}")
        self.assertTrue(self.llamar(app, "GET", "/estado", None).json()["pausa"]["activa"])

    def test_estado_rechaza_sin_firma_con_firma_falsa_o_vencida(self) -> None:
        app = self.app()
        self.assertEqual(self.llamar(app, "GET", "/estado", None, ts=None, firma=None).estado, 401)
        self.assertEqual(self.llamar(app, "GET", "/estado", None, firma="hmac-sha256=" + "0" * 64).estado, 401)
        self.assertEqual(self.llamar(app, "GET", "/estado", None, ts="2026-11-09T11:00:00Z").estado, 400)
        self.assertEqual(self.llamar(app, "GET", "/estado", None, secreto=b"otro").estado, 401)
        self.assertNotIn("x-fabrica-firma", self.llamar(app, "GET", "/estado", None, ts=None, firma=None).cabeceras)

    def test_estado_sin_secreto_es_500_y_no_expone_nada(self) -> None:
        r = self.llamar(self.app(secreto=b""), "GET", "/estado", None)
        self.assertEqual((r.estado, r.motivo), (500, "configuracion_incompleta"))
        self.assertNotIn(b"semaforo", r.cuerpo)


class PruebaContratoConLosFirmadoresReales(BaseApi):
    """Contrato con ``infra/firma_servicio.py`` (el firmador del servicio y de los Workers): la API acepta lo que ese módulo firma."""

    CUERPO = b'{"etapa":"D1","oferta_id":"OF-202611-01"}'
    TS_EJEMPLO = "2026-11-09T12:00:00Z"
    SECRETO_EJEMPLO = b"secreto-de-ejemplo"
    ENTREGA = {"checkout_session_id": "cs_test_a1b2c3", "oferta_id": OFERTA, "estado": "entregado", "intento": 1,
               "producto_sha256": "sha256:" + "a" * 64, "ts": "2026-11-09T11:59:00Z"}

    def parametros_datos(self):
        from engine.parametros import Parametros

        def entrada(valor: Any) -> dict:
            return {"valor": valor, "unidad": "x", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}

        return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {
            "ingesta": {"tolerancia_seg": entrada(120), "cuerpo_max_bytes": entrada(2048)},
            "entrega": {"enlace_vence_dias": entrada(7), "enlace_max_descargas": entrada(3)}}})

    def con_firmador(self, app: ApiServicio, ruta: str, cuerpo: bytes, *, ts: str = TS, contexto: str | None = None,
                     metodo: str = "POST", mutar: Any = None) -> Respuesta:
        from infra.firma_servicio import cabeceras_internas
        cab = cabeceras_internas(SECRETO, cuerpo, ts, contexto)
        if mutar:
            cab["X-Fabrica-Firma"] = mutar(cab["X-Fabrica-Firma"])
        return self.llamar(app, metodo, ruta, cuerpo, ts=cab["X-Fabrica-Ts"], firma=cab["X-Fabrica-Firma"])

    def test_evento_firmado_con_cabeceras_internas_sin_contexto_lo_acepta_el_controlador_real_de_datos(self) -> None:
        app = self.app()
        cuerpo = canonico(EVENTO)
        r = self.con_firmador(app, "/ingesta/evento", cuerpo)
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "nuevo", "atribuible": True}))
        self.assertEqual(self.con_firmador(app, "/ingesta/evento", cuerpo).json()["resultado"], "duplicado")
        self.assertEqual(self.filas(), 1, "lo escribió datos.ingesta.manejar_ingesta_evento en fact_evento")

    def test_entrega_firmada_con_cabeceras_internas_la_acepta_el_controlador_real_de_datos(self) -> None:
        app = self.app(parametros_datos=self.parametros_datos())
        r = self.con_firmador(app, "/ingesta/entrega", canonico(self.ENTREGA))
        self.assertEqual((r.estado, r.json()), (200, {"ok": True, "resultado": "nuevo"}), "ya no responde 501")

    def test_firma_falsa_vencida_o_con_contexto_ajeno_se_rechaza_como_siempre(self) -> None:
        app = self.app(parametros_datos=self.parametros_datos())
        for ruta, cuerpo in (("/ingesta/evento", canonico(EVENTO)), ("/ingesta/entrega", canonico(self.ENTREGA))):
            falsa = self.con_firmador(app, ruta, cuerpo, mutar=lambda f: f[:-1] + ("0" if f[-1] != "0" else "1"))
            self.assertEqual((falsa.estado, falsa.motivo), (401, "firma_invalida"), ruta)
            vencida = self.con_firmador(app, ruta, cuerpo, ts="2026-11-09T11:00:00Z")
            self.assertEqual((vencida.estado, vencida.motivo), (400, "ts_fuera_de_tolerancia"), ruta)
            for contexto in ("req", "resp"):
                self.assertEqual(self.con_firmador(app, ruta, cuerpo, contexto=contexto).estado, 401, f"{ruta} con contexto {contexto}")
            self.assertEqual(self.con_firmador(app, ruta, cuerpo, mutar=lambda f: "").estado, 401)
        self.assertEqual(self.filas(), 0)

    def test_el_prefijo_de_contexto_reproduce_el_de_infra_firma_servicio(self) -> None:
        from infra.firma_servicio import cabeceras_internas, verificar_cabeceras
        for contexto in (None, "req", "resp"):
            self.assertEqual(firmar(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, contexto),
                             cabeceras_internas(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, contexto)["X-Fabrica-Firma"], contexto)
        self.assertEqual(firmar(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO), "hmac-sha256=d37d04267ad3153664bc993ac36a40ea09d854920339d5f6674d70b2d0594749")
        self.assertEqual(firmar(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, "req"), "hmac-sha256=74cc8e5c10f5c6f337b5dba9ecba66c0a0fe4ac9c5d0218b1265d5a7e74d455e")
        self.assertEqual(firmar(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, "resp"), "hmac-sha256=a73d537ebdb37bc0380e8bbadd54be3e7bc12c45b4114661c48e243598f282de")
        f = cabeceras_internas(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, "req")["X-Fabrica-Firma"]
        self.assertTrue(verificar_cabeceras(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, f, "req"))
        self.assertFalse(verificar_cabeceras(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, f, "resp"))
        self.assertFalse(verificar_cabeceras(self.SECRETO_EJEMPLO, self.CUERPO, self.TS_EJEMPLO, f))

    def test_estado_peticion_req_y_respuesta_resp_con_el_firmador_de_infra(self) -> None:
        from infra.firma_servicio import verificar_cabeceras
        app = self.app()
        r = self.con_firmador(app, "/estado", b"", contexto="req", metodo="GET")
        self.assertEqual(r.estado, 200)
        ts, firma = r.cabeceras["x-fabrica-ts"], r.cabeceras["x-fabrica-firma"]
        self.assertTrue(verificar_cabeceras(SECRETO, r.cuerpo, ts, firma, "resp"), "quien lee /estado verifica con contexto resp")
        self.assertFalse(verificar_cabeceras(SECRETO, r.cuerpo, ts, firma, "req"))
        self.assertFalse(verificar_cabeceras(SECRETO, r.cuerpo, ts, firma))
        for malo in (None, "resp"):
            self.assertEqual(self.con_firmador(app, "/estado", b"", contexto=malo, metodo="GET").estado, 401, malo)

    def test_ordenes_e_ingresar_con_el_firmador_de_infra(self) -> None:
        app = self.app(manejadores={"orden": lambda p: (200, {"ok": True}), "ingresar": lambda p: (200, {"ok": True})})
        for ruta in ("/ordenes", "/ingresar"):
            cuerpo = canonico({"a": 1})
            self.assertEqual(self.con_firmador(app, ruta, cuerpo, contexto="req").estado, 200, ruta)
            for malo in (None, "resp"):
                r = self.con_firmador(app, ruta, cuerpo, contexto=malo)
                self.assertEqual((r.estado, r.motivo), (401, "firma_invalida"), f"{ruta} con contexto {malo}")


if __name__ == "__main__":
    unittest.main()
