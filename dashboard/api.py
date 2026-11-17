"""API de servicio (docs/06 §4.7; CONTRATO §7b): aplicación WSGI de la biblioteca estándar para Workers y ``engine.orq``.

Es OTRA aplicación que el panel local (``python -m dashboard``): comparte lectores y reglas de seguridad pero no el puerto
ni el token. Entrada propia: ``python -m dashboard.api [--host 127.0.0.1] [--puerto N]`` (en Railway: ``--host 0.0.0.0``,
puerto de ``PORT``).

Rutas::

    GET  /salud               mínimo, sin autenticación: {"ok": true}
    GET  /estado              FIRMADO: petición con contexto «req», respuesta con contexto «resp»
    POST /ingesta/evento      Workers eventos/capi (HMAC interno, sin contexto: docs/06 §4.7 tal cual)
    POST /ingesta/entrega     Worker fulfill (HMAC interno, sin contexto)
    POST /webhooks/stripe     Stripe (su propia firma Stripe-Signature)
    POST /ordenes             orq firmar (HMAC interno con contexto «req» + Ed25519 de la orden)
    POST /ingresar            orq ingresar remoto (HMAC interno con contexto «req»)

Autenticación interna: ``X-Fabrica-Ts`` (UTC ISO con ``Z``) y ``X-Fabrica-Firma: hmac-sha256=<hex>``. El mensaje firmado es
``ts + "." + cuerpo_exacto`` (``/ingesta/*``) o ``contexto + "." + ts + "." + cuerpo_exacto`` (``/estado``, ``/ordenes``, ``/ingresar``),
con ``contexto`` = ``req`` (petición) o ``resp`` (respuesta de ``/estado``): la firma de una respuesta nunca autentica una petición
(revisión de seguridad m-4; ver ``CONTRATO.md`` §7b e ``infra/firma_servicio.py``, que reproduce la misma convención). Comparación en
tiempo constante. Orden de las comprobaciones (todas fallan cerradas, y el cuerpo NO se lee hasta pasar las baratas):
``Content-Length`` estricto y tope (411/400/413) → marcas presentes (401) → ``ts`` válido y dentro de ``ingesta.tolerancia_seg`` (400)
→ lectura del cuerpo con plazo total → firma (401) → JSON y forma (400) → efecto con idempotencia (200 ``duplicado`` si idéntico; 409
si el mismo identificador trae otro contenido). Sin secreto o sin ``ingesta.*`` responde 500 ``configuracion_incompleta`` (genérico: el
detalle solo va al log) y no acepta nada.

Controladores: ``manejadores`` es un mapa inyectable ``{"evento"|"entrega"|"stripe"|"orden"|"ingresar": f(Peticion) -> (status, dict)}``.
Por defecto se montan los de ``datos`` (``datos.ingesta.manejar_ingesta_evento`` y ``manejar_ingesta_entrega``, con sus validadores;
``datos.etl_stripe.aplicar_evento``), ``engine.orq.ingresar_desde_cuerpo`` para ``/ingresar`` y el propio de órdenes Ed25519
(``empresa/ordenes/``). Si un controlador de ``datos`` no existe, responde 501 ``adaptador_no_disponible``; ``manejadores`` los sustituye.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import hmac
import http
import logging
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from dashboard.api_base import Ctx
from dashboard.api_sistema import estado_infra, estado_pausa, freno_captura
from dashboard.archivos import a_json_bytes, cargar_json_estricto, crear_exclusivo, iso_z, preparar_destino
from dashboard.seguridad import ErrorHttp, es_entero_ascii, leer_cuerpo_con_plazo, parsear_longitud

__all__ = ["ApiServicio", "Peticion", "firmar", "main"]

log = logging.getLogger("dashboard.api")

VAR_SECRETO = "INGEST_HMAC_SECRET"
VAR_STRIPE = "STRIPE_WEBHOOK_SECRET"
VAR_PUBLICA = "FABRICA_FIRMA_PUBLICA"
CABECERA_TS, CABECERA_FIRMA = "HTTP_X_FABRICA_TS", "HTTP_X_FABRICA_FIRMA"
CUERPO_MAX_STRIPE = 1024 * 1024
CUERPO_MAX_INGRESAR = 1024 * 1024
_RX_TS = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$")
_TIPOS_STRIPE = ("checkout.session.completed", "charge.refunded", "charge.dispute.created")

CTX_REQ, CTX_RESP = "req", "resp"


def firmar(secreto: bytes, cuerpo: bytes, ts: str, contexto: str | None = None) -> str:
    """Valor de ``X-Fabrica-Firma``: ``hmac-sha256=<hex>`` del mensaje ``[contexto + "."] + ts + "." + cuerpo``.

    ``contexto=None`` es la convención de ``/ingesta/*`` (idéntica a ``infra.firma_servicio`` y a los Workers). ``"req"``/``"resp"``
    separan dominios: una firma de respuesta no sirve como petición.
    """
    prefijo = f"{contexto}.".encode("ascii") if contexto else b""
    return "hmac-sha256=" + hmac.new(secreto, prefijo + ts.encode("utf-8") + b"." + cuerpo, hashlib.sha256).hexdigest()


class ErrorServicio(Exception):
    """Respuesta de error ya decidida: ``(estado, motivo, detalle)``; ``interno`` solo va al log."""

    def __init__(self, estado: int, motivo: str, detalle: str | None = None, *, interno: str | None = None) -> None:
        super().__init__(motivo)
        self.estado, self.motivo, self.detalle, self.interno = estado, motivo, detalle, interno


def error_configuracion(interno: str) -> ErrorServicio:
    """500 GENÉRICO: no nombra variables ni archivos al cliente (puede no estar autenticado); el detalle va al log."""
    return ErrorServicio(500, "configuracion_incompleta", interno=interno)


@dataclass
class Peticion:
    """Lo que reciben los controladores: cuerpo exacto, JSON ya parseado, cabeceras, reloj, raíz y conexión a ``datos``."""

    cuerpo: bytes
    json: Any
    cabeceras: Mapping[str, str]
    ahora: _dt.datetime
    raiz: Path
    parametros: Mapping[str, int]
    env: Mapping[str, str] = field(repr=False)          # copia de os.environ: lleva secretos, nunca en repr/logs
    conexion: Any = None
    secreto: bytes = field(default=b"", repr=False)       # para controladores de datos que re-verifican la firma
    parametros_datos: Any = field(default=None, repr=False)   # engine.parametros.Parametros (entrega.*, ingesta.*) si se inyectó
    extra: dict[str, Any] = field(default_factory=dict)


Manejador = Callable[[Peticion], "tuple[int, dict[str, Any]]"]


def _parsear_ts(texto: str) -> _dt.datetime:
    if not _RX_TS.fullmatch(texto):
        raise ValueError("ts")
    return _dt.datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)


# ----------------------------------------------------------------------------------------------
# Controladores: los de ``datos`` donde existen (sin duplicar su lógica), los propios para órdenes e ingreso
# ----------------------------------------------------------------------------------------------
def _descubrir(modulo: str, nombre: str) -> Callable[..., Any] | None:
    """Controlador/validador de ``datos`` si existe (``None`` si no)."""
    try:
        import importlib
        return getattr(importlib.import_module(modulo), nombre, None)
    except Exception:  # noqa: BLE001 - un módulo ausente o roto no debe tirar el servicio
        return None


def _controlador_datos(nombre: str, p: Peticion, contexto_log: str) -> tuple[int, dict[str, Any]]:
    """Llama a ``datos.ingesta.<nombre>`` con secreto, parámetros y raíz EXPLÍCITOS (no lee ``os.environ``). Sin él: 501."""
    f = _descubrir("datos.ingesta", nombre)
    if f is None:
        return 501, {"ok": False, "motivo": "adaptador_no_disponible", "detalle": f"falta datos.ingesta.{nombre}"}
    parametros = p.parametros_datos
    if parametros is None:
        try:
            from engine.parametros import Parametros, cargar_parametros, ruta_por_defecto
            if nombre == "manejar_ingesta_evento":
                # Solo necesita ``ingesta.*``: se arma con los MISMOS valores con que esta API ya autenticó (inyectados o de empresa/).
                grupo = {k: {"valor": v, "unidad": "x", "hipotesis": True, "fuente": "dashboard.api", "ultima_calibracion": None}
                         for k, v in p.parametros.items()}
                parametros = Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {"ingesta": grupo}})
            else:
                parametros = cargar_parametros(ruta_por_defecto(p.raiz))
        except Exception as exc:  # noqa: BLE001 - parámetros ausentes o inválidos: fail-closed y genérico hacia fuera
            log.error("configuración incompleta en %s: %s", contexto_log, exc)
            return 500, {"ok": False, "motivo": "configuracion_incompleta"}
    argumentos: dict[str, Any] = {"parametros": parametros, "secreto": p.secreto}
    if nombre == "manejar_ingesta_entrega":
        argumentos["raiz"] = p.raiz
    estado, cuerpo = f(p.cuerpo, dict(p.cabeceras), p.conexion, lambda: p.ahora, **argumentos)
    if estado == 500 and isinstance(cuerpo, dict) and "detalle" in cuerpo:
        log.error("configuración incompleta en %s: %s", contexto_log, cuerpo.get("detalle"))
        return 500, {"ok": False, "motivo": "configuracion_incompleta"}
    return estado, cuerpo


def manejar_evento(p: Peticion) -> tuple[int, dict[str, Any]]:
    """``POST /ingesta/evento`` (docs/06 §4.7): delega en ``datos.ingesta.manejar_ingesta_evento`` (``fact_evento``: ``cid``, ``asid``,
    ``adid``, ``fuente``, ``consentimiento`` y valor; sin consentimiento queda sin atribución y responde ``atribuible: false``).
    La autenticación ya la hizo esta API; el controlador de ``datos`` la repite con el mismo secreto (misma convención ``ts.cuerpo``).
    """
    return _controlador_datos("manejar_ingesta_evento", p, "/ingesta/evento")


def manejar_entrega(p: Peticion) -> tuple[int, dict[str, Any]]:
    """``POST /ingesta/entrega``: delega en ``datos.ingesta.manejar_ingesta_entrega`` (el cuerpo ya viene validado y autenticado)."""
    return _controlador_datos("manejar_ingesta_entrega", p, "/ingesta/entrega")


def _marcas_stripe(cabecera: str, ahora: _dt.datetime, tolerancia: int) -> tuple[str, list[str]]:
    """Comprobaciones BARATAS antes de leer el cuerpo: cabecera presente y bien formada y ``t`` dentro de la tolerancia.

    Devuelve ``(t, firmas_v1)``; lanza ``ErrorServicio`` 400. Solo dígitos ASCII (``isdigit()`` aceptaba ``²``: 500).
    """
    if not cabecera:
        raise ErrorServicio(400, "firma_stripe_ausente")
    ts_txt, firmas = None, []
    for parte in cabecera.split(","):
        clave, _, valor = parte.strip().partition("=")
        if clave == "t":
            ts_txt = valor
        elif clave == "v1":
            firmas.append(valor)
    if not es_entero_ascii(ts_txt, 12) or not firmas:
        raise ErrorServicio(400, "firma_stripe_invalida")
    if abs(ahora.timestamp() - int(ts_txt)) > tolerancia:
        raise ErrorServicio(400, "ts_fuera_de_tolerancia")
    return ts_txt, firmas


def _firma_stripe_valida(ts_txt: str, firmas: list[str], cuerpo: bytes, secreto: bytes) -> bool:
    esperado = hmac.new(secreto, ts_txt.encode("ascii") + b"." + cuerpo, hashlib.sha256).hexdigest().encode("ascii")
    return any(hmac.compare_digest(esperado, f.encode("utf-8", "ignore")) for f in firmas)


def manejar_stripe(p: Peticion) -> tuple[int, dict[str, Any]]:
    """``POST /webhooks/stripe``: la firma ya se verificó; ``datos.etl_stripe.aplicar_evento`` deduplica por ``event.id`` y objeto."""
    evento = p.json
    if not isinstance(evento, dict) or not isinstance(evento.get("id"), str) or not isinstance(evento.get("type"), str):
        return 400, {"ok": False, "motivo": "evento_stripe_invalido"}
    if evento["type"] not in _TIPOS_STRIPE:
        return 200, {"ok": True, "resultado": "ignorado"}   # un tipo que no usamos nunca debe provocar reintentos de Stripe
    aplicar = _descubrir("datos.etl_stripe", "aplicar_evento")
    if aplicar is None:
        return 501, {"ok": False, "motivo": "adaptador_no_disponible", "detalle": "falta datos.etl_stripe.aplicar_evento"}
    try:
        resultado = aplicar(p.conexion, evento, ahora=lambda: p.ahora)
    except Exception as exc:  # noqa: BLE001 - dato hostil o mal formado: 400 sin detalles internos
        if exc.__class__.__name__ == "ErrorValidacion":
            return 400, {"ok": False, "motivo": "evento_stripe_invalido"}
        raise
    return 200, {"ok": True, "resultado": resultado}


def manejar_orden(p: Peticion) -> tuple[int, dict[str, Any]]:
    """``POST /ordenes``: valida el esquema ``orden_firmada``, ``ts`` en tolerancia, Ed25519 con la pública y ``nonce`` único.

    Solo REGISTRA la orden en ``empresa/ordenes/<nonce>.json`` (el ``guard`` la consume); no activa nada.
    """
    from engine import comun
    from engine.errores import ErrorBloqueado, ErrorValidacion

    orden = p.json
    if not isinstance(orden, dict):
        return 400, {"ok": False, "motivo": "orden_invalida", "detalle": "el cuerpo no es un objeto JSON"}
    try:
        errores = comun.errores_de_esquema("orden_firmada", orden)
    except ErrorValidacion:
        return 500, {"ok": False, "motivo": "esquema_no_disponible"}
    if errores:
        return 400, {"ok": False, "motivo": "orden_invalida", "detalle": comun.resumir_errores_esquema(errores)[:300]}
    try:
        momento = _parsear_ts(orden["ts"])
    except ValueError:
        return 400, {"ok": False, "motivo": "ts_invalido"}
    if abs((p.ahora - momento).total_seconds()) > p.parametros["tolerancia_seg"]:
        return 400, {"ok": False, "motivo": "ts_fuera_de_tolerancia"}
    publica = p.env.get(VAR_PUBLICA)
    if not publica:
        log.error("configuración incompleta: falta la variable %s", VAR_PUBLICA)
        return 500, {"ok": False, "motivo": "configuracion_incompleta"}
    sin_firma = {k: v for k, v in orden.items() if k != "firma"}
    try:
        valida = comun.verificar_ed25519(comun.json_canonico(sin_firma), orden["firma"], publica)
    except ErrorBloqueado:
        return 500, {"ok": False, "motivo": "no_se_pudo_verificar_la_firma"}
    if not valida:
        return 401, {"ok": False, "motivo": "firma_de_orden_invalida"}
    try:
        destino = preparar_destino(p.raiz, f"empresa/ordenes/{orden['nonce']}.json")
    except ErrorHttp:
        return 400, {"ok": False, "motivo": "nonce_no_admitido"}
    if not crear_exclusivo(destino, comun.json_canonico(orden) + b"\n"):
        return 409, {"ok": False, "motivo": "nonce_repetido"}
    return 200, {"ok": True, "resultado": "registrada", "nonce": orden["nonce"]}


def manejar_ingresar(p: Peticion) -> tuple[int, dict[str, Any]]:
    """``POST /ingresar`` (docs/06 §4.7): delega en ``engine.orq.ingresar_desde_cuerpo(cuerpo, *, raiz, ahora, env)``.

    El cuerpo lo valida el motor: JSON con EXACTAMENTE ``oferta_id``, ``etapa`` y ``archivos[{ruta, contenido_b64}]``; su tope sale de
    ``ingesta.cuerpo_max_bytes``. Mapeo: ``ErrorValidacion``/``ErrorUso`` → 400, ``ErrorBloqueado`` → 409, ``ParametroFaltante`` →
    500 ``configuracion_incompleta`` (fail-closed hasta que el dueño apruebe ``ingesta.*``), ``ErrorExterno`` → 502.
    """
    try:
        from engine import orq
        from engine.errores import ErrorBloqueado, ErrorExterno, ErrorLimite, ErrorUso, ErrorValidacion, ParametroFaltante
    except ImportError:
        return 501, {"ok": False, "motivo": "adaptador_no_disponible", "detalle": "engine.orq no está disponible en este despliegue"}
    try:
        resultado = orq.ingresar_desde_cuerpo(p.cuerpo, raiz=p.raiz, ahora=lambda: p.ahora, env=p.env)
    except (ErrorValidacion, ErrorUso) as exc:
        return 400, {"ok": False, "motivo": "ingresar_invalido", "detalle": str(exc)[:300]}
    except ErrorBloqueado as exc:
        return 409, {"ok": False, "motivo": "ingresar_bloqueado", "detalle": str(exc)[:300]}
    except ParametroFaltante as exc:
        log.error("configuración incompleta en /ingresar: %s", exc)
        return 500, {"ok": False, "motivo": "configuracion_incompleta"}
    except ErrorLimite as exc:
        return 409, {"ok": False, "motivo": "ingresar_limite", "detalle": str(exc)[:300]}
    except ErrorExterno as exc:
        log.error("fallo externo en /ingresar: %s", exc)
        return 502, {"ok": False, "motivo": "ingresar_externo"}
    return 200, {"ok": True, "resultado": resultado}


MANEJADORES_DEFECTO: dict[str, Manejador] = {
    "evento": manejar_evento, "entrega": manejar_entrega, "stripe": manejar_stripe,
    "orden": manejar_orden, "ingresar": manejar_ingresar,
}
_MOTIVO_INVALIDO = {"evento": "evento_invalido", "entrega": "entrega_invalida"}
_VALIDADOR_DATOS = {"evento": "_validar_evento", "entrega": "_validar_entrega"}   # los de datos.ingesta: una sola definición del cuerpo
# ruta → (manejador, ¿necesita la base de datos?, contexto del HMAC). Sin contexto = docs/06 §4.7 tal cual (los Workers ya firman así).
_RUTAS: dict[str, tuple[str, bool, str | None]] = {
    "/ingesta/evento": ("evento", True, None), "/ingesta/entrega": ("entrega", True, None), "/webhooks/stripe": ("stripe", True, None),
    "/ordenes": ("orden", False, CTX_REQ), "/ingresar": ("ingresar", False, CTX_REQ),
}


# ----------------------------------------------------------------------------------------------
# Aplicación WSGI
# ----------------------------------------------------------------------------------------------
class ApiServicio:
    """Aplicación WSGI de la API de servicio. Todo lo externo (secretos, parámetros, reloj, base) es inyectable."""

    def __init__(self, raiz: str | Path | None = None, *, secreto: bytes | None = None, secreto_stripe: bytes | None = None,
                 parametros: Mapping[str, int] | None = None, ahora: Callable[[], _dt.datetime] | None = None,
                 conexion: Any = None, manejadores: Mapping[str, Manejador] | None = None,
                 env: Mapping[str, str] | None = None, parametros_datos: Any = None) -> None:
        self.env = dict(os.environ if env is None else env)
        self.raiz = Path(os.path.realpath(raiz or self.env.get("FABRICA_RAIZ") or Path(__file__).resolve().parent.parent))
        self.ctx = Ctx(self.raiz, ahora or (lambda: _dt.datetime.now(_dt.timezone.utc)))
        self._ahora = self.ctx.ahora
        self._secreto = secreto if secreto is not None else (self.env.get(VAR_SECRETO) or "").encode("utf-8")
        self._secreto_stripe = secreto_stripe if secreto_stripe is not None else (self.env.get(VAR_STRIPE) or "").encode("utf-8")
        self._parametros = dict(parametros) if parametros is not None else None
        self._inyectados = parametros is not None
        self._conexion = conexion
        self._parametros_datos = parametros_datos      # engine.parametros.Parametros inyectable (pruebas); None = cargar de empresa/
        self._migrado = False
        self.manejadores: dict[str, Manejador] = {**MANEJADORES_DEFECTO, **(dict(manejadores) if manejadores else {})}

    # -- configuración --------------------------------------------------------------------------
    def _params(self) -> dict[str, int]:
        """``tolerancia_seg`` y ``cuerpo_max_bytes`` (inyectados o de ``empresa/parametros.yaml``, grupo ``ingesta``); 500 si faltan."""
        if self._inyectados:
            if not {"tolerancia_seg", "cuerpo_max_bytes"} <= set(self._parametros or {}):
                raise error_configuracion("faltan ingesta.tolerancia_seg o ingesta.cuerpo_max_bytes (inyectados)")
            return self._parametros
        if self._parametros is None:
            lec = self.ctx.empresa().yaml("parametros.yaml")
            grupo = lec.dato.get("grupos", {}).get("ingesta") if lec.ok and isinstance(lec.dato, dict) and isinstance(lec.dato.get("grupos"), dict) else None
            valores: dict[str, int] = {}
            if isinstance(grupo, dict):
                for clave in ("tolerancia_seg", "cuerpo_max_bytes"):
                    entrada = grupo.get(clave)
                    v = entrada.get("valor") if isinstance(entrada, dict) else None
                    if isinstance(v, int) and not isinstance(v, bool) and v > 0:
                        valores[clave] = v
            if not {"tolerancia_seg", "cuerpo_max_bytes"} <= set(valores):
                raise error_configuracion("faltan ingesta.tolerancia_seg o ingesta.cuerpo_max_bytes en empresa/parametros.yaml")
            self._parametros = valores   # solo se guardan completos: si luego se agregan al archivo, se leen sin reiniciar
        return self._parametros

    @contextmanager
    def _con_conexion(self) -> Iterator[Any]:
        if self._conexion is not None and not callable(self._conexion):
            yield self._conexion          # conexión inyectada (pruebas): no se cierra aquí
            return
        from datos.db import conectar, migrar
        conn = self._conexion() if callable(self._conexion) else conectar(f"sqlite:///{self.raiz / 'empresa' / 'datos' / 'fabrica.db'}")
        try:
            if not self._migrado:
                migrar(conn)
                self._migrado = True
            yield conn
        finally:
            conn.cerrar()

    # -- WSGI ---------------------------------------------------------------------------------
    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        firmada = False
        try:
            estado, cuerpo, firmada = self._despachar(environ)
        except ErrorServicio as exc:
            if exc.interno:
                log.error("%s: %s", exc.motivo, exc.interno)     # el detalle de configuración va SOLO al log
            estado, cuerpo = exc.estado, {"ok": False, "motivo": exc.motivo, **({"detalle": exc.detalle} if exc.detalle else {})}
        except Exception:  # noqa: BLE001 - nada de trazas ni rutas hacia el cliente
            log.exception("error interno en la API de servicio")
            estado, cuerpo = 500, {"ok": False, "motivo": "error_interno"}
        datos = a_json_bytes(cuerpo)
        cabeceras = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(datos))),
                     ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")]
        if firmada:
            ts = iso_z(self._ahora())
            cabeceras += [("X-Fabrica-Ts", ts), ("X-Fabrica-Firma", firmar(self._secreto, datos, ts, CTX_RESP))]
        try:
            frase = http.HTTPStatus(estado).phrase
        except ValueError:                      # un manejador inyectado con un código no estándar no rompe la respuesta
            frase = "Error" if estado >= 400 else "OK"
        if estado == 405:
            cabeceras.append(("Allow", "GET, HEAD" if environ.get("PATH_INFO") == "/salud" else ("GET" if environ.get("PATH_INFO") == "/estado" else "POST")))
        start_response(f"{estado} {frase}", cabeceras)
        return [b""] if environ.get("REQUEST_METHOD") == "HEAD" else [datos]

    def _despachar(self, environ: dict[str, Any]) -> tuple[int, dict[str, Any], bool]:
        metodo = environ.get("REQUEST_METHOD", "")
        ruta = environ.get("PATH_INFO", "") or "/"
        if ruta == "/salud":
            if metodo not in ("GET", "HEAD"):
                raise ErrorServicio(405, "metodo_no_permitido")
            return 200, {"ok": True}, False
        if ruta == "/estado":
            if metodo != "GET":
                raise ErrorServicio(405, "metodo_no_permitido")
            return self._estado(environ)
        destino = _RUTAS.get(ruta)
        if destino is None:
            raise ErrorServicio(404, "ruta_no_encontrada")
        if metodo != "POST":
            raise ErrorServicio(405, "metodo_no_permitido")
        nombre, necesita_conexion, contexto = destino
        if nombre == "stripe":
            return self._stripe(environ)
        params = self._exigir_configuracion()
        largo = self._longitud(environ, CUERPO_MAX_INGRESAR if nombre == "ingresar" else params["cuerpo_max_bytes"])
        ts, firma = self._marcas(environ, params)          # baratas: ANTES de leer el cuerpo
        cuerpo = self._leer(environ, largo)
        self._verificar_firma(cuerpo, ts, firma, contexto)
        objeto = self._parsear_json(cuerpo)
        return self._ejecutar(nombre, necesita_conexion, environ, cuerpo, objeto, params)

    # -- pasos -----------------------------------------------------------------------------------
    def _exigir_configuracion(self) -> dict[str, int]:
        if not self._secreto:
            raise error_configuracion(f"falta la variable {VAR_SECRETO}")
        return self._params()

    @staticmethod
    def _longitud(environ: dict[str, Any], maximo: int) -> int:
        """``Content-Length`` estricto (solo dígitos ASCII) y tope, SIN leer el cuerpo: 411 / 400 / 413."""
        try:
            largo = parsear_longitud(environ.get("CONTENT_LENGTH"))
        except ErrorHttp as exc:
            raise ErrorServicio(exc.estado, exc.codigo) from exc
        if largo > maximo:
            raise ErrorServicio(413, "cuerpo_demasiado_grande", f"El cuerpo supera {maximo} bytes.")
        return largo

    @staticmethod
    def _leer(environ: dict[str, Any], largo: int) -> bytes:
        """Lee el cuerpo con plazo TOTAL (un cliente que gotea bytes no retiene el hilo): 408 / 400."""
        try:
            return leer_cuerpo_con_plazo(environ["wsgi.input"], largo)
        except ErrorHttp as exc:
            raise ErrorServicio(exc.estado, exc.codigo) from exc

    def _marcas(self, environ: dict[str, Any], params: Mapping[str, int]) -> tuple[str, str]:
        """Marcas presentes (401) y ``ts`` válido y dentro de la tolerancia (400), antes de leer el cuerpo."""
        ts, firma = environ.get(CABECERA_TS), environ.get(CABECERA_FIRMA)
        if not ts or not firma:
            raise ErrorServicio(401, "firma_ausente")
        try:
            momento = _parsear_ts(ts)
        except ValueError as exc:
            raise ErrorServicio(400, "ts_invalido") from exc
        if abs((self._ahora() - momento).total_seconds()) > params["tolerancia_seg"]:
            raise ErrorServicio(400, "ts_fuera_de_tolerancia")
        return ts, firma

    def _verificar_firma(self, cuerpo: bytes, ts: str, firma: str, contexto: str | None) -> None:
        esperada = firmar(self._secreto, cuerpo, ts, contexto).encode("ascii")
        if not hmac.compare_digest(esperada, firma.strip().encode("utf-8", "ignore")):
            raise ErrorServicio(401, "firma_invalida")

    @staticmethod
    def _parsear_json(cuerpo: bytes) -> Any:
        try:
            return cargar_json_estricto(cuerpo)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ErrorServicio(400, "cuerpo_no_json") from exc

    def _peticion(self, environ: dict[str, Any], cuerpo: bytes, objeto: Any, params: Mapping[str, int], conexion: Any) -> Peticion:
        cabeceras = {k[5:].replace("_", "-").title(): v for k, v in environ.items() if isinstance(k, str) and k.startswith("HTTP_")}
        return Peticion(cuerpo, objeto, cabeceras, self._ahora(), self.raiz, params, self.env, conexion, self._secreto, self._parametros_datos)

    def _ejecutar(self, nombre: str, necesita_conexion: bool, environ: dict[str, Any], cuerpo: bytes, objeto: Any,
                  params: Mapping[str, int]) -> tuple[int, dict[str, Any], bool]:
        validador = _descubrir("datos.ingesta", _VALIDADOR_DATOS[nombre]) if nombre in _VALIDADOR_DATOS else None
        if validador is not None:
            problemas = validador(objeto)
            if problemas:   # se valida SIEMPRE antes de entregar a un controlador (propio o inyectado)
                return 400, {"ok": False, "motivo": _MOTIVO_INVALIDO[nombre], "problemas": problemas[:10]}, False
        manejador = self.manejadores[nombre]
        if necesita_conexion:
            with self._con_conexion() as conn:
                estado, datos = manejador(self._peticion(environ, cuerpo, objeto, params, conn))
        else:
            estado, datos = manejador(self._peticion(environ, cuerpo, objeto, params, None))
        return estado, datos, False

    def _stripe(self, environ: dict[str, Any]) -> tuple[int, dict[str, Any], bool]:
        if not self._secreto_stripe:
            raise error_configuracion(f"falta la variable {VAR_STRIPE}")
        params = self._params()
        largo = self._longitud(environ, CUERPO_MAX_STRIPE)
        ts_txt, firmas = _marcas_stripe(environ.get("HTTP_STRIPE_SIGNATURE", ""), self._ahora(), params["tolerancia_seg"])
        cuerpo = self._leer(environ, largo)
        if not _firma_stripe_valida(ts_txt, firmas, cuerpo, self._secreto_stripe):
            raise ErrorServicio(400, "firma_stripe_invalida")
        objeto = self._parsear_json(cuerpo)
        return self._ejecutar("stripe", True, environ, cuerpo, objeto, params)

    def _estado(self, environ: dict[str, Any]) -> tuple[int, dict[str, Any], bool]:
        """``GET /estado`` FIRMADO: petición con contexto «req» (cuerpo vacío); la respuesta se firma con contexto «resp» (``X-Fabrica-Ts/Firma``)."""
        params = self._exigir_configuracion()
        ts, firma = self._marcas(environ, params)
        self._verificar_firma(b"", ts, firma, CTX_REQ)
        infra, _ = estado_infra(self.ctx)
        freno, _ = freno_captura(self.ctx)
        datos = {"ok": True, "ts": iso_z(self._ahora()), "pausa": estado_pausa(self.ctx), "infra": infra, "freno_captura": freno}
        return 200, datos, True


# ----------------------------------------------------------------------------------------------
# Arranque: python -m dashboard.api
# ----------------------------------------------------------------------------------------------
def _puerto_de_entorno(defecto: int = 8780) -> int:
    """``PORT`` si es un entero decimal; si no (``PORT=abc``), el valor por defecto en lugar de una traza al construir el parser."""
    crudo = (os.environ.get("PORT") or "").strip()
    return int(crudo) if crudo.isascii() and crudo.isdigit() else defecto


def main(argv: Sequence[str] | None = None) -> int:
    """Sirve la API de servicio (bloquea). ``--host 0.0.0.0`` solo detrás de la red privada de Railway/Cloudflare."""
    from wsgiref.simple_server import make_server

    from dashboard.servidor import _Manejador, _Servidor

    ap = argparse.ArgumentParser(prog="python -m dashboard.api", description="API de servicio (Workers y engine.orq).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--puerto", type=int, default=_puerto_de_entorno())
    ap.add_argument("--raiz", default=None)
    args = ap.parse_args(argv)
    if not 0 <= args.puerto <= 65535:
        print("error: --puerto fuera de rango", file=sys.stderr)
        return 2
    app = ApiServicio(args.raiz)
    try:
        servidor = make_server(args.host, args.puerto, app, server_class=_Servidor, handler_class=_Manejador)
    except OSError as exc:
        print(f"error: no se pudo abrir {args.host}:{args.puerto} ({exc.strerror or exc.__class__.__name__})", file=sys.stderr)
        return 2
    print(f"API de servicio en http://{args.host}:{servidor.server_port} · raíz {app.raiz}", flush=True)
    try:
        servidor.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
