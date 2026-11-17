"""Servidor del panel local (CONTRATO §1, §4, §6, §7): aplicación WSGI de la biblioteca estándar.

* ``Panel``: la aplicación WSGI (``panel(environ, start_response)``): estáticos de ``dashboard/web/`` (MIME, sin caché),
  ``/sitio/<id>/…`` (landing en sandbox), ``/api/*`` (JSON con sobre) y ``/api/eventos`` (SSE).
* ``crear_servidor`` / ``servir``: ``wsgiref.simple_server`` con ``ThreadingMixIn``, escucha SOLO ``127.0.0.1``.

Seguridad en cada petición (ver ``dashboard/seguridad.py``): ``Host`` ∈ {``127.0.0.1:<p>``, ``localhost:<p>``}; ``/api`` exige
``X-Panel-Token``; ``POST`` exige además ``Origin`` propio y ``Content-Type: application/json``; ningún error expone trazas ni
rutas absolutas. La lectura de archivos pasa SIEMPRE por el resolvedor confinado de ``dashboard/archivos.py``.

Sobre de éxito: ``{"ok": true, "datos", "fuente", "generado_en", "vacio", "avisos"}``; de error:
``{"ok": false, "error": {"codigo", "mensaje"}}`` con 400/403/404/405/409/411/413/429/500/503/507.
"""
from __future__ import annotations

import datetime as _dt
import http
import logging
import os
import re
import socket
import socketserver
import threading
import time
import urllib.parse
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any
from wsgiref.simple_server import ServerHandler, WSGIRequestHandler, WSGIServer

from dashboard import acciones as _acciones
from dashboard import api_alertas, api_cerebro, api_descubrimiento, api_empresa, api_flujo, api_negocio, api_ofertas, api_registro, api_robots, api_sistema
from dashboard.api_base import Ctx, Sobre, ahora_utc
from dashboard.archivos import (
    Raiz, a_json_bytes, anexar_linea, cargar_json_estricto, crear_exclusivo, preparar_destino,
)
from dashboard.pulido import Pulido
from dashboard.seguridad import (
    ErrorHttp, Politica, cabeceras_json, cabeceras_panel, cabeceras_sitio, es_entero_ascii, leer_cuerpo_con_plazo,
    nuevo_token, parsear_longitud,
)
from dashboard.vigia import TOPE_ARCHIVOS, Difusor, Vigia

__all__ = ["Panel", "crear_servidor", "reescribir_rutas", "servir"]

log = logging.getLogger("dashboard")

DIR_WEB = Path(__file__).resolve().parent / "web"
ACCIONES_YAML = Path(__file__).resolve().parent / "acciones.yaml"
TOPE_CUERPO = 64 * 1024
TOPE_ESTATICO = 10 * 1024 * 1024
MAX_SSE = 16
PING_S = 15.0
MAX_HILOS = 64                  # conexiones atendidas a la vez; la que sobra recibe 503 al instante
PLAZO_CABECERAS_S = 15.0        # plazo TOTAL para recibir la línea de petición y las cabeceras
TOPE_REESCRITURA = 2 * 1024 * 1024   # más grande que esto se sirve tal cual (sin reescribir rutas)
_RX_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MIME = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".map": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".avif": "image/avif", ".ico": "image/x-icon",
    ".woff2": "font/woff2", ".woff": "font/woff", ".webmanifest": "application/manifest+json",
}
_PAGINA_PROVISIONAL = (
    "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>Panel</title></head><body>"
    "<h1>Panel</h1><p>El panel está andando, pero todavía falta su pantalla principal (<code>dashboard/web/index.html</code>).</p>"
    "<p>Avisa a quien mantiene el sistema para que la agregue.</p></body></html>"
)


def _fase(ruta: str) -> list[str]:
    return [p for p in ruta.split("/") if p]


# Todas las repeticiones están ACOTADAS: con ``[^"']*`` / ``[^)"']*`` sin tope, un archivo con miles de ``url(/`` sin cierre
# hacía cuadrático el análisis (60 KB congelaron el proceso 4,6 s; revisión de seguridad M-1).
_RX_ATRIBUTO_URL = re.compile(r"""(\b(?:href|src|action|formaction|poster|data-src)\s{0,8}=\s{0,8})(["'])(/(?!/)[^"']{0,2048})\2""", re.IGNORECASE)
_RX_SRCSET = re.compile(r"""(\bsrcset\s{0,8}=\s{0,8})(["'])([^"']{0,8192})\2""", re.IGNORECASE)
_RX_URL_CSS = re.compile(r"""url\(\s{0,32}(["']?)(/(?!/)[^()"'\s]{0,2048})\1\s{0,32}\)""", re.IGNORECASE)
_RX_IMPORT_CSS = re.compile(r"""(@import\s{1,8})(["'])(/(?!/)[^"']{0,2048})\2""", re.IGNORECASE)


def reescribir_rutas(contenido: bytes, prefijo: str, mime: str) -> bytes:
    """Reescribe en una respuesta HTML/CSS las rutas absolutas del sitio (``/css/x.css``) a ``<prefijo>/css/x.css``.

    La landing se genera para vivir en la raíz de su dominio; en el panel cuelga de ``/sitio/<id>/``. Solo se tocan las URL que
    empiezan por UNA barra (``href|src|action|poster|srcset``, ``url(/…)`` y ``@import "/…"``); ``//host``, ``http:``, ``data:``,
    ``#ancla`` y rutas relativas quedan igual, y no se reescribe lo que ya cuelga de ``prefijo``. El archivo en disco no cambia.
    Otros tipos (JS, imágenes…) y archivos de más de 2 MB pasan sin tocar.
    """
    tipo = mime.split(";")[0].strip()
    if tipo not in ("text/html", "text/css") or len(contenido) > TOPE_REESCRITURA:
        return contenido
    texto = contenido.decode("utf-8", "surrogateescape")

    def _nueva(ruta: str) -> str:
        return ruta if ruta == prefijo or ruta.startswith(prefijo + "/") else prefijo + ruta

    def _atributo(m: re.Match[str]) -> str:
        return f"{m.group(1)}{m.group(2)}{_nueva(m.group(3))}{m.group(2)}"

    def _srcset(m: re.Match[str]) -> str:
        candidatos = []
        for c in m.group(3).split(","):
            parte = c.strip()
            candidatos.append(_nueva(parte) if parte.startswith("/") and not parte.startswith("//") else parte)
        return f"{m.group(1)}{m.group(2)}{', '.join(candidatos)}{m.group(2)}"

    def _url(m: re.Match[str]) -> str:
        return f"url({m.group(1)}{_nueva(m.group(2))}{m.group(1)})"

    def _importar(m: re.Match[str]) -> str:
        return f"{m.group(1)}{m.group(2)}{_nueva(m.group(3))}{m.group(2)}"

    if tipo == "text/html":
        texto = _RX_ATRIBUTO_URL.sub(_atributo, texto)
        texto = _RX_SRCSET.sub(_srcset, texto)
    texto = _RX_URL_CSS.sub(_url, texto)
    texto = _RX_IMPORT_CSS.sub(_importar, texto)
    return texto.encode("utf-8", "surrogateescape")


class Panel:
    """Aplicación WSGI del panel. ``raiz`` es el repositorio (o una raíz temporal en pruebas)."""

    def __init__(self, raiz: str | Path, *, puerto: int = 0, token: str | None = None, web_dir: str | Path | None = None,
                 acciones_yaml: str | Path | None = None, ahora: Callable[[], _dt.datetime] | None = None,
                 entorno: str | None = None, vigia: bool = False, intervalo_vigia: float = 1.0,
                 ping_s: float = PING_S, sondeo_sse_s: float = 1.0, max_sse: int = MAX_SSE,
                 tope_archivos_vigia: int = TOPE_ARCHIVOS, publicos: tuple[str, ...] = ()) -> None:
        self.politica = Politica(puerto=puerto, token=token or nuevo_token(), publicos=tuple(publicos))
        self.ctx = Ctx(Path(raiz), ahora or ahora_utc, puerto, entorno or os.environ.get("FABRICA_ENTORNO") or "desarrollo")
        self.web = Raiz(web_dir or DIR_WEB)
        self.difusor = Difusor()
        self.vigia = Vigia(self.ctx.raiz, self.difusor, intervalo=intervalo_vigia, ahora=self.ctx.ahora,
                           tope_archivos=tope_archivos_vigia)
        self.ctx.estado_vigia = self.vigia.estado
        self._vigia_activo = vigia
        self.pulido = Pulido(self.ctx)
        self.lista_blanca = _acciones.cargar_lista_blanca(Path(acciones_yaml or ACCIONES_YAML), self.ctx.raiz)
        self.ejecutor = _acciones.Ejecutor(self.ctx.raiz, self.lista_blanca, ahora=self.ctx.ahora, auditar=self._auditar)
        self.ping_s = ping_s
        self.sondeo_sse_s = sondeo_sse_s
        self.max_sse = max_sse
        self._sse_activos = 0
        self._cerrojo = threading.Lock()
        self._cerrando = threading.Event()
        if vigia:
            self.vigia.iniciar()
        self._rutas = self._tabla_de_rutas()

    # ------------------------------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------------------------------
    @property
    def token(self) -> str:
        return self.politica.token

    def fijar_puerto(self, puerto: int) -> None:
        """Con ``--puerto 0`` el puerto real se conoce tras ``bind``: de él depende la verificación de ``Host``/``Origin``."""
        self.politica.puerto = puerto
        self.ctx.puerto = puerto

    def url(self) -> str:
        return f"http://127.0.0.1:{self.politica.puerto}/#t={self.token}"

    def cerrar(self) -> None:
        self._cerrando.set()
        self.vigia.detener()
        self.ejecutor.cerrar()

    # ------------------------------------------------------------------------------------------
    # WSGI
    # ------------------------------------------------------------------------------------------
    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        try:
            self.politica.comprobar_host(environ)
            ruta = self._path_info(environ)
            if ruta == "/api" or ruta.startswith("/api/"):
                return self._api(environ, start_response, ruta)
            if ruta.startswith("/sitio/"):
                return self._sitio(environ, start_response, ruta)
            return self._estatico(environ, start_response, ruta)
        except ErrorHttp as exc:
            return self._error(start_response, exc)
        except Exception:  # noqa: BLE001 - nada de trazas hacia el cliente
            log.exception("error interno atendiendo %s", environ.get("PATH_INFO"))
            return self._error(start_response, ErrorHttp(500, "error_interno", "El panel tuvo un problema inesperado. Prueba de nuevo; si sigue pasando, avisa a quien mantiene el sistema."))

    # -- utilidades de respuesta ---------------------------------------------------------------
    @staticmethod
    def _linea_estado(estado: int) -> str:
        return f"{estado} {http.HTTPStatus(estado).phrase}"

    def _error(self, start_response: Callable[..., Any], exc: ErrorHttp, extra_cabeceras: list[tuple[str, str]] | None = None) -> list[bytes]:
        error: dict[str, Any] = {"codigo": exc.codigo, "mensaje": exc.mensaje}
        error.update(exc.extra)
        cuerpo = a_json_bytes({"ok": False, "error": error})
        cab = cabeceras_json() + [("Content-Length", str(len(cuerpo)))] + (extra_cabeceras or [])
        start_response(self._linea_estado(exc.estado), cab)
        return [cuerpo]

    def _json(self, start_response: Callable[..., Any], sobre: Sobre, estado: int = 200) -> list[bytes]:
        cuerpo = a_json_bytes(sobre.a_dict(self.ctx.iso_ahora()))
        start_response(self._linea_estado(estado), cabeceras_json() + [("Content-Length", str(len(cuerpo)))])
        return [cuerpo]

    @staticmethod
    def _path_info(environ: dict[str, Any]) -> str:
        crudo = environ.get("PATH_INFO", "") or "/"
        try:  # PEP 3333: PATH_INFO llega como latin-1; los servidores reales entregan bytes UTF-8 decodificados así
            ruta = crudo.encode("latin-1").decode("utf-8")
        except UnicodeEncodeError:
            ruta = crudo  # ya es texto Unicode (pruebas directas)
        except UnicodeDecodeError as exc:
            raise ErrorHttp(400, "ruta_invalida", "La dirección pedida tiene caracteres que el panel no entiende.") from exc
        if "\x00" in ruta or not ruta.startswith("/"):
            raise ErrorHttp(400, "ruta_invalida", "La dirección pedida no es válida.")
        return ruta

    @staticmethod
    def _consulta(environ: dict[str, Any]) -> dict[str, list[str]]:
        qs = environ.get("QUERY_STRING", "") or ""
        if len(qs) > 4096:
            raise ErrorHttp(400, "consulta_invalida", "El pedido es demasiado largo.")
        try:
            return urllib.parse.parse_qs(qs, keep_blank_values=True, max_num_fields=32, errors="replace")
        except ValueError as exc:
            raise ErrorHttp(400, "consulta_invalida", "El pedido trae demasiados datos.") from exc

    @staticmethod
    def _cuerpo_json(environ: dict[str, Any]) -> Any:
        tipo = (environ.get("CONTENT_TYPE") or "").split(";")[0].strip().lower()
        if tipo != "application/json":
            raise ErrorHttp(400, "tipo_contenido_invalido", "Los datos se enviaron en un formato que el panel no entiende. Recarga la página y prueba de nuevo.")
        largo = parsear_longitud(environ.get("CONTENT_LENGTH"))
        if largo > TOPE_CUERPO:
            raise ErrorHttp(413, "cuerpo_demasiado_grande", f"Lo que se quiso enviar es demasiado grande (más de {TOPE_CUERPO // 1024} KB).")
        datos = leer_cuerpo_con_plazo(environ["wsgi.input"], largo)
        if not datos.strip():
            return {}
        try:
            return cargar_json_estricto(datos)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ErrorHttp(400, "cuerpo_invalido", "Los datos enviados no tienen un formato válido. Recarga la página y prueba de nuevo.") from exc

    # ------------------------------------------------------------------------------------------
    # Estáticos y /sitio
    # ------------------------------------------------------------------------------------------
    def _servir(self, base: Raiz, rel: str, environ: dict[str, Any], start_response: Callable[..., Any],
                cabeceras: Callable[[str], list[tuple[str, str]]],
                transformar: Callable[[bytes, str], bytes] | None = None) -> list[bytes]:
        metodo = environ.get("REQUEST_METHOD")
        if metodo not in ("GET", "HEAD"):
            raise ErrorHttp(405, "metodo_no_permitido", "Esa operación no está permitida en esta dirección del panel.")
        real = base.real(rel)
        if real.is_dir():
            rel = rel.rstrip("/") + "/index.html" if rel else "index.html"
            real = base.real(rel)
        mime = _MIME.get(real.suffix.lower())
        if mime is None:
            raise ErrorHttp(404, "no_encontrado", "No se encontró eso en el panel.")
        datos, truncado, _ = base.bytes(rel, TOPE_ESTATICO)
        if truncado:
            raise ErrorHttp(413, "recurso_demasiado_grande", "Ese archivo es demasiado grande para mostrarlo en el panel.")
        if transformar is not None:
            datos = transformar(datos, mime)
        cab = cabeceras(mime) + [("Content-Length", str(len(datos)))]
        start_response(self._linea_estado(200), cab)
        return [] if metodo == "HEAD" else [datos]

    def _estatico(self, environ: dict[str, Any], start_response: Callable[..., Any], ruta: str) -> list[bytes]:
        rel = ruta.lstrip("/")
        if rel == "" or rel.endswith("/"):
            rel += "index.html"
        if rel == "favicon.ico" and not self.web.existe(rel):
            start_response(self._linea_estado(204), cabeceras_json()[:1])
            return []
        if rel == "index.html" and not self.web.existe("index.html"):
            cuerpo = _PAGINA_PROVISIONAL.encode("utf-8")
            start_response("200 OK", cabeceras_panel("text/html; charset=utf-8") + [("Content-Length", str(len(cuerpo)))])
            return [] if environ.get("REQUEST_METHOD") == "HEAD" else [cuerpo]
        return self._servir(self.web, rel, environ, start_response, cabeceras_panel)

    def _sitio(self, environ: dict[str, Any], start_response: Callable[..., Any], ruta: str) -> list[bytes]:
        """``/sitio/<id>/<ruta>``: landing de ``ofertas/<id>/05-landing/sitio/`` (sin token; solo GET/HEAD; CSP en sandbox)."""
        partes = _fase(ruta)[1:]
        if not partes:
            raise ErrorHttp(404, "no_encontrado", "Falta indicar de qué oferta es la página de venta.")
        oferta_id, resto = partes[0], "/".join(partes[1:]) if len(partes) > 1 else ""
        if ruta.endswith("/") and resto:
            resto += "/"
        base = api_ofertas.carpeta_sitio(self.ctx, oferta_id)
        rel = resto or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        prefijo = f"/sitio/{oferta_id}"
        candidatos = [(base, rel)]
        if "." not in rel.rsplit("/", 1)[-1]:
            candidatos.append((base, rel + ".html"))                     # URL limpia: /legal/aviso → legal/aviso.html
        if rel.startswith("imagenes/"):
            candidatos.append((api_ofertas.carpeta_imagenes(self.ctx, oferta_id), rel[len("imagenes/"):]))   # 05-landing/imagenes/
        ultimo: ErrorHttp | None = None
        for carpeta, ruta_rel in candidatos:
            try:
                return self._servir(carpeta, ruta_rel, environ, start_response, cabeceras_sitio,
                                    lambda datos, mime: reescribir_rutas(datos, prefijo, mime))
            except ErrorHttp as exc:
                if exc.estado != 404:
                    raise
                ultimo = exc
        raise ultimo or ErrorHttp(404, "no_encontrado", "No se encontró eso en el panel.")

    # ------------------------------------------------------------------------------------------
    # /api
    # ------------------------------------------------------------------------------------------
    def _tabla_de_rutas(self) -> list[tuple[re.Pattern[str], dict[str, Callable[..., Any]]]]:
        c = self.ctx
        id_ = r"([^/]+)"
        tabla: list[tuple[str, dict[str, Callable[..., Any]]]] = [
            (r"/api/sistema", {"GET": lambda e, q, m: api_sistema.sistema(c)}),
            (r"/api/ofertas", {"GET": lambda e, q, m: api_ofertas.ofertas(c)}),
            (rf"/api/oferta/{id_}", {"GET": lambda e, q, m: api_ofertas.oferta(c, m[0])}),
            (rf"/api/oferta/{id_}/archivo", {"GET": lambda e, q, m: api_ofertas.archivo(c, m[0], (q.get("ruta") or [""])[0])}),
            (rf"/api/oferta/{id_}/referente", {"GET": lambda e, q, m: api_ofertas.referente(c, m[0])}),
            (r"/api/descubrimiento/corridas", {"GET": lambda e, q, m: api_descubrimiento.corridas(c)}),
            (rf"/api/descubrimiento/{id_}/candidatos", {"GET": lambda e, q, m: api_descubrimiento.candidatos(c, m[0])}),
            (rf"/api/descubrimiento/{id_}/fichas", {"GET": lambda e, q, m: api_descubrimiento.fichas(c, m[0])}),
            (rf"/api/descubrimiento/{id_}/etiquetas", {"GET": lambda e, q, m: api_descubrimiento.etiquetas(c, m[0])}),
            (rf"/api/descubrimiento/{id_}/plan", {"GET": lambda e, q, m: api_descubrimiento.plan(c, m[0])}),
            (rf"/api/descubrimiento/{id_}/estado", {"GET": lambda e, q, m: api_descubrimiento.estado(c, m[0])}),
            (rf"/api/descubrimiento/{id_}/paginas", {"GET": lambda e, q, m: api_descubrimiento.paginas(c, m[0], q)}),
            (rf"/api/descubrimiento/{id_}/referente/{id_}", {"GET": lambda e, q, m: api_descubrimiento.referente(c, m[0], m[1])}),
            (rf"/api/campanas/{id_}", {"GET": lambda e, q, m: api_ofertas.campanas(c, m[0])}),
            (rf"/api/operacion/{id_}", {"GET": lambda e, q, m: api_ofertas.operacion(c, m[0])}),
            (r"/api/finanzas", {"GET": lambda e, q, m: api_empresa.finanzas(c)}),
            (r"/api/negocio", {"GET": lambda e, q, m: api_negocio.negocio(c, q)}),
            (r"/api/flujo", {"GET": lambda e, q, m: api_flujo.flujo(c)}),
            (r"/api/negocio/documento", {"GET": lambda e, q, m: api_negocio.documento(c, (q.get("ruta") or [""])[0])}),
            (r"/api/meta", {"GET": lambda e, q, m: api_negocio.meta(c, q)}),
            (r"/api/agentes", {"GET": lambda e, q, m: api_registro.agentes(c, q)}),
            (rf"/api/agentes/{id_}", {"GET": lambda e, q, m: api_registro.agente_detalle(c, m[0], q)}),
            (r"/api/cumplimiento", {"GET": lambda e, q, m: api_empresa.cumplimiento(c)}),
            (r"/api/parametros", {"GET": lambda e, q, m: api_empresa.parametros(c)}),
            (r"/api/gates", {"GET": lambda e, q, m: api_empresa.gates(c)}),
            (r"/api/registro", {"GET": lambda e, q, m: api_registro.registro(c, q)}),
            (r"/api/skills", {"GET": lambda e, q, m: api_empresa.skills(c)}),
            (rf"/api/skills/{id_}/archivo", {"GET": lambda e, q, m: api_empresa.skill_archivo(c, m[0], (q.get("ruta") or [""])[0])}),
            (r"/api/cerebro", {"GET": lambda e, q, m: api_cerebro.cerebro(c)}),
            (r"/api/robots", {"GET": lambda e, q, m: api_robots.robots(c)}),
            (r"/api/robots/sombra", {"GET": lambda e, q, m: api_robots.sombra(c)}),
            (r"/api/alertas", {"GET": lambda e, q, m: api_alertas.alertas(c)}),
            (r"/api/informe", {"GET": lambda e, q, m: api_alertas.informe(c)}),
            (r"/api/pulido", {"GET": lambda e, q, m: self.pulido.listar(),
                              "POST": lambda e, q, m: self._post_pulido(e)}),
            (r"/api/acciones", {"GET": lambda e, q, m: self._get_acciones()}),
            (r"/api/accion", {"POST": lambda e, q, m: self._post_accion(e)}),
            (rf"/api/job/{id_}", {"GET": lambda e, q, m: self._get_job(m[0], q)}),
            (r"/api/pausa", {"POST": lambda e, q, m: self._post_pausa(e)}),
            (r"/api/flujo/verificar", {"POST": lambda e, q, m: api_flujo.pedir_verificacion(c, self._cuerpo_json(e))}),
        ]
        return [(re.compile(f"^{patron}$"), metodos) for patron, metodos in tabla]

    def _api(self, environ: dict[str, Any], start_response: Callable[..., Any], ruta: str) -> Iterable[bytes]:
        metodo = environ.get("REQUEST_METHOD", "")
        self.politica.comprobar_sitio_fetch(environ)
        self.politica.comprobar_origen(environ, obligatorio=(metodo == "POST"))
        consulta = self._consulta(environ)
        es_sse = ruta == "/api/eventos"
        self.politica.comprobar_token(environ, consulta=consulta, permitir_consulta=es_sse)
        if es_sse:
            if metodo != "GET":
                raise ErrorHttp(405, "metodo_no_permitido", "Esa operación no está permitida en esta dirección del panel.")
            return self._eventos(environ, start_response)
        for patron, metodos in self._rutas:
            m = patron.match(ruta)
            if m is None:
                continue
            manejador = metodos.get(metodo)
            if manejador is None:
                return self._error(start_response, ErrorHttp(405, "metodo_no_permitido", "Esa operación no está permitida en esta dirección del panel."),
                                   [("Allow", ", ".join(sorted(metodos)))])
            return self._json(start_response, manejador(environ, consulta, m.groups()))   # PATH_INFO ya viene decodificado: no se decodifica dos veces
        raise ErrorHttp(404, "ruta_no_encontrada", "El panel no tiene esa dirección.")

    # -- manejadores con efecto (acciones del dueño, §6) ---------------------------------------
    def _auditar(self, linea: dict[str, Any]) -> None:
        destino = preparar_destino(self.ctx.raiz, "empresa/panel/auditoria.jsonl")
        anexar_linea(destino, a_json_bytes({**linea, "origen": "panel"}) + b"\n")

    def _post_pulido(self, environ: dict[str, Any]) -> Sobre:
        entrada = self.pulido.escribir(self._cuerpo_json(environ))
        return Sobre(entrada, ["empresa/panel/pulido.jsonl"])

    def _get_acciones(self) -> Sobre:
        avisos = list(self.lista_blanca.avisos)
        avisos += [f"La acción «{r['id']}» fue rechazada y no se puede usar (no cumple las reglas de seguridad): {'; '.join(r['motivos'])}." for r in self.lista_blanca.rechazadas]
        datos = self.ejecutor.describir()
        return Sobre(datos, ["dashboard/acciones.yaml"], vacio=not datos["acciones"], avisos=avisos)

    def _post_accion(self, environ: dict[str, Any]) -> Sobre:
        cuerpo = self._cuerpo_json(environ)
        if not isinstance(cuerpo, dict):
            raise ErrorHttp(400, "cuerpo_invalido", "Los datos enviados no tienen la forma esperada. Recarga la página y prueba de nuevo.")
        extras = set(cuerpo) - {"id", "args"}
        if extras:
            raise ErrorHttp(400, "campo_no_permitido", f"Hay datos que no se aceptan: {', '.join(sorted(map(str, extras)))}.")
        job = self.ejecutor.iniciar(cuerpo.get("id"), cuerpo.get("args"))
        return Sobre({"job_id": job.id, "accion": job.accion, "comando": job.comando, "inicio": job.inicio}, ["dashboard/acciones.yaml"])

    def _get_job(self, job_id: str, consulta: dict[str, list[str]]) -> Sobre:
        job = self.ejecutor.job(job_id)
        if job is None:
            raise ErrorHttp(404, "job_no_encontrado", "No se encontró esa ejecución. Si reiniciaste el panel, las ejecuciones anteriores se pierden: vuelve a lanzar la acción.")
        crudo = (consulta.get("desde") or [""])[0]
        try:
            desde = int(crudo) if crudo != "" else 0
        except ValueError as exc:
            raise ErrorHttp(400, "parametro_invalido", "El valor de «desde» tiene que ser un número entero.") from exc
        return Sobre(job.leer(max(desde, 0)), [])

    def _post_pausa(self, environ: dict[str, Any]) -> Sobre:
        """Crea ``empresa/PAUSA`` si no existe. NUNCA la borra ni la sobrescribe ni toca ``empresa/captura/freno.json``."""
        cuerpo = self._cuerpo_json(environ)
        if not isinstance(cuerpo, dict):
            raise ErrorHttp(400, "cuerpo_invalido", "Los datos enviados no tienen la forma esperada. Recarga la página y prueba de nuevo.")
        motivo = cuerpo.get("motivo")
        if motivo is not None and not isinstance(motivo, str):
            raise ErrorHttp(400, "campo_invalido", "El motivo tiene que ser un texto.")
        motivo = _RX_CONTROL.sub("", motivo or "").strip()[:500] or "Pausa manual desde el panel (sin motivo)"
        ts = self.ctx.iso_ahora()
        destino = preparar_destino(self.ctx.raiz, "empresa/PAUSA")
        contenido = a_json_bytes({"ts": ts, "motivo": motivo, "origen": "panel"}) + b"\n"
        creada = crear_exclusivo(destino, contenido)
        if creada:
            try:
                self._auditar({"ts": ts, "evento": "pausa", "motivo": motivo})
            except Exception:  # noqa: BLE001 - la auditoría no puede impedir la pausa
                log.warning("no se pudo anotar la auditoría de la pausa")
        datos = {"creada": creada, "ya_existia": not creada, "pausa": api_sistema.estado_pausa(self.ctx),
                 "como_reanudar": "El panel nunca borra la pausa: revisa el motivo y, si corresponde, borra tú el archivo empresa/PAUSA desde la terminal."}
        return Sobre(datos, ["empresa/PAUSA"])

    # -- SSE -------------------------------------------------------------------------------------
    def _eventos(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        with self._cerrojo:
            if self._sse_activos >= self.max_sse:
                raise ErrorHttp(503, "demasiadas_conexiones", "Hay demasiadas pantallas del panel abiertas a la vez. Cierra alguna y recarga la página.")
        ultimo = (environ.get("HTTP_LAST_EVENT_ID") or "").strip()
        desde = int(ultimo) if es_entero_ascii(ultimo, 14) else self.difusor.ultimo_id   # isdigit() aceptaba «²» (500)
        cab = [(k, v) for k, v in cabeceras_json() if k != "Content-Type"] + [
            ("Content-Type", "text/event-stream; charset=utf-8"), ("X-Accel-Buffering", "no")]
        start_response("200 OK", cab)
        return self._flujo(desde)

    def _flujo(self, desde: int) -> Iterator[bytes]:
        with self._cerrojo:
            self._sse_activos += 1
        try:
            yield b"retry: 3000\n: conectado\n\n"
            ultimo_envio = time.monotonic()
            while not self._cerrando.is_set():
                for evento_id, evento in self.difusor.esperar(desde, self.sondeo_sse_s):
                    desde = evento_id
                    datos = a_json_bytes({k: evento.get(k) for k in ("tipo", "ruta", "ts")})
                    yield b"id: %d\nevent: cambio\ndata: %s\n\n" % (evento_id, datos)
                    ultimo_envio = time.monotonic()
                if time.monotonic() - ultimo_envio >= self.ping_s:
                    yield b"event: ping\ndata: %s\n\n" % a_json_bytes({"ts": self.ctx.iso_ahora()})
                    ultimo_envio = time.monotonic()
        finally:
            with self._cerrojo:
                self._sse_activos -= 1


# ----------------------------------------------------------------------------------------------
# Servidor HTTP (wsgiref + hilos)
# ----------------------------------------------------------------------------------------------
class _Manejador(WSGIRequestHandler):
    """Sin registro de peticiones (las URL pueden llevar parámetros), con ``timeout`` por operación y plazo TOTAL para las cabeceras."""

    timeout = 30

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _cortar(self) -> None:
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def handle(self) -> None:
        """Igual que ``WSGIRequestHandler.handle`` pero cortando al cliente que no completa la petición a tiempo (slowloris)."""
        plazo = threading.Timer(getattr(self.server, "plazo_cabeceras", PLAZO_CABECERAS_S), self._cortar)
        plazo.daemon = True
        plazo.start()
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ""
                self.request_version = ""
                self.command = ""
                self.send_error(414)
                return
            if not self.parse_request():
                return
        except (OSError, ValueError):
            return
        finally:
            plazo.cancel()
        manejador = ServerHandler(self.rfile, self.wfile, self.get_stderr(), self.get_environ(), multithread=False)
        manejador.request_handler = self
        manejador.run(self.server.get_app())


class _Servidor(socketserver.ThreadingMixIn, WSGIServer):
    """Un hilo por conexión, con TOPE: pasado ``max_hilos`` la conexión recibe 503 al instante en vez de otro hilo."""

    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 32

    def __init__(self, direccion: tuple[str, int], manejador: type, *, max_hilos: int = MAX_HILOS,
                 plazo_cabeceras: float = PLAZO_CABECERAS_S) -> None:
        self.max_hilos = max_hilos
        self.plazo_cabeceras = plazo_cabeceras
        self._cupo = threading.BoundedSemaphore(max_hilos)
        super().__init__(direccion, manejador)

    def server_bind(self) -> None:
        # Sin getfqdn (puede tardar segundos sin red): el servidor solo escucha en 127.0.0.1.
        socketserver.TCPServer.server_bind(self)
        host, puerto = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = puerto
        self.setup_environ()

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._cupo.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._cupo.release()


def crear_servidor(panel: Panel, puerto: int = 0, *, max_hilos: int = MAX_HILOS,
                   plazo_cabeceras: float = PLAZO_CABECERAS_S) -> WSGIServer:
    """Servidor ligado a ``127.0.0.1:<puerto>`` (0 = efímero); fija el puerto real en ``panel``."""
    servidor = _Servidor(("127.0.0.1", puerto), _Manejador, max_hilos=max_hilos, plazo_cabeceras=plazo_cabeceras)
    servidor.set_app(panel)
    panel.fijar_puerto(servidor.server_port)
    return servidor


def servir(panel: Panel, puerto: int = 0, *, al_iniciar: Callable[[Panel], None] | None = None) -> None:
    """Arranca el servidor (bloquea hasta Ctrl-C). Inicia el vigía y limpia trabajos al salir."""
    servidor = crear_servidor(panel, puerto)
    if not panel._vigia_activo:
        panel.vigia.iniciar()
        panel._vigia_activo = True
    if al_iniciar is not None:
        al_iniciar(panel)
    try:
        servidor.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        panel.cerrar()
        servidor.server_close()
