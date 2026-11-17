"""Seguridad del panel local y de la API de servicio (CONTRATO §7).

Piezas puras, sin estado global:

* ``ErrorHttp``: excepción que los manejadores lanzan y el servidor convierte en el sobre de error.
* Token de sesión de 32 bytes aleatorios (por arranque) y comparación en tiempo constante.
* ``Politica``: verificación de ``Host`` (anti DNS-rebinding), ``Origin`` (anti CSRF) y token.
* Cabeceras de seguridad y CSP (panel y ``/sitio``).

Nada de aquí imprime ni registra el token.
"""
from __future__ import annotations

import hmac
import re
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

__all__ = [
    "CABECERA_TOKEN", "CSP_PANEL", "CSP_SITIO", "ErrorHttp", "PLAZO_CUERPO_S", "Politica", "TOKEN_BYTES",
    "cabeceras_json", "cabeceras_panel", "cabeceras_sitio", "es_entero_ascii", "iguales", "leer_cuerpo_con_plazo",
    "nuevo_token", "parsear_longitud",
]

TOKEN_BYTES = 32
CABECERA_TOKEN = "X-Panel-Token"

# CSP del panel: solo recursos propios; sin scripts en línea; la landing va en un iframe del mismo origen
# (``frame-src 'self'``) y se sirve con su propia CSP en sandbox (``CSP_SITIO``). ``style-src 'unsafe-inline'``
# solo permite el atributo ``style`` (los estilos que fija ``ui.js``); los scripts siguen limitados a ``'self'``.
CSP_PANEL = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)
# Contrato §4: la landing de la oferta se sirve en sandbox sin ``allow-same-origin`` (origen opaco). Revisión de seguridad m-3:
# sin ``data:`` en ``default-src`` (un ``<script src="data:…">`` ejecutaba dentro del sandbox); las imágenes ``data:`` siguen
# permitidas; ``frame-ancestors 'self'`` solo deja enmarcarla al propio panel.
CSP_SITIO = "sandbox allow-scripts; default-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'self'"
PLAZO_CUERPO_S = 15.0

_BASE = (
    ("X-Content-Type-Options", "nosniff"),
    ("Cache-Control", "no-store"),
    ("Referrer-Policy", "no-referrer"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
)


class ErrorHttp(Exception):
    """Error con estado HTTP y código estable; el servidor lo vuelve ``{"ok": false, "error": {...}}``.

    ``mensaje`` nunca debe llevar rutas absolutas, trazas ni valores secretos.
    """

    def __init__(self, estado: int, codigo: str, mensaje: str, **extra: object) -> None:
        super().__init__(f"{codigo}: {mensaje}")
        self.estado = estado
        self.codigo = codigo
        self.mensaje = mensaje
        self.extra = dict(extra)


def nuevo_token() -> str:
    """Token aleatorio de ``TOKEN_BYTES`` bytes, seguro para URL (43 caracteres)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def iguales(a: str | bytes | None, b: str | bytes | None) -> bool:
    """Comparación en tiempo constante (acepta texto no ASCII sin lanzar). ``None`` nunca es igual."""
    if a is None or b is None:
        return False
    ba = a if isinstance(a, bytes) else a.encode("utf-8", "surrogatepass")
    bb = b if isinstance(b, bytes) else b.encode("utf-8", "surrogatepass")
    return hmac.compare_digest(ba, bb)


def cabeceras_json() -> list[tuple[str, str]]:
    """Cabeceras de una respuesta JSON de la API."""
    return [*_BASE, ("Content-Type", "application/json; charset=utf-8"), ("X-Frame-Options", "DENY")]


def cabeceras_panel(tipo_mime: str) -> list[tuple[str, str]]:
    """Cabeceras de un estático del panel (HTML/JS/CSS…) con su CSP."""
    return [*_BASE, ("Content-Type", tipo_mime), ("Content-Security-Policy", CSP_PANEL), ("X-Frame-Options", "DENY")]


def cabeceras_sitio(tipo_mime: str) -> list[tuple[str, str]]:
    """Cabeceras de ``/sitio/<id>/…``: CSP en sandbox y enmarcable solo por el propio panel.

    ``Cross-Origin-Resource-Policy: cross-origin``: dentro del sandbox (origen opaco) los CSS/JS/imágenes de la propia landing
    son peticiones «de otro origen»; con ``same-origin`` el navegador los bloqueaba (la vista previa salía sin estilos). Es
    contenido público de la landing; la lectura desde otras páginas la siguen frenando ``Host`` y CORS.
    """
    base = [(k, v) for k, v in _BASE if k != "Cross-Origin-Resource-Policy"]
    return [*base, ("Cross-Origin-Resource-Policy", "cross-origin"), ("Content-Type", tipo_mime),
            ("Content-Security-Policy", CSP_SITIO), ("X-Frame-Options", "SAMEORIGIN")]


_RX_LONGITUD = re.compile(r"[0-9]{1,10}")


def es_entero_ascii(valor: object, maximo_digitos: int = 14) -> bool:
    """¿Solo dígitos ASCII 0-9 (1 a ``maximo_digitos``)? ``str.isdigit()`` acepta ``²`` o dígitos árabes; esto no."""
    return isinstance(valor, str) and re.fullmatch(rf"[0-9]{{1,{maximo_digitos}}}", valor) is not None


def parsear_longitud(crudo: str | None) -> int:
    """``Content-Length`` estricto: 1 a 10 dígitos ASCII. Ausente → 411; con ``_``, ``+``, espacios, signo o no ASCII → 400."""
    if crudo in (None, ""):
        raise ErrorHttp(411, "longitud_requerida", "Al pedido le falta indicar cuánto pesa. Recarga la página y prueba de nuevo.")
    if not isinstance(crudo, str) or _RX_LONGITUD.fullmatch(crudo) is None:
        raise ErrorHttp(400, "longitud_invalida", "El tamaño indicado en el pedido no es válido. Recarga la página y prueba de nuevo.")
    return int(crudo)


def leer_cuerpo_con_plazo(entrada: object, largo: int, plazo_s: float = PLAZO_CUERPO_S,
                          reloj: Callable[[], float] = time.monotonic) -> bytes:
    """Lee EXACTAMENTE ``largo`` bytes con un plazo TOTAL (no por ``recv``): un cliente que gotea 1 byte cada pocos segundos no
    retiene el hilo. ``408`` si vence; ``400`` si el cuerpo llega más corto que ``Content-Length``."""
    if largo == 0:
        return b""
    limite = reloj() + plazo_s
    trozos: list[bytes] = []
    recibido = 0
    # ``read1`` vuelve tras UN ``recv`` (lo que haya llegado); ``read(n)`` bloquea hasta reunir ``n`` bytes y el plazo solo se
    # comprobaría entre lecturas: un cliente que gotea 1 byte cada pocos segundos retendría el hilo para siempre (revisión M-A).
    lee = getattr(entrada, "read1", None) or entrada.read  # type: ignore[attr-defined]
    while recibido < largo:
        if reloj() >= limite:
            raise ErrorHttp(408, "cuerpo_demasiado_lento", "Los datos tardaron demasiado en llegar. Prueba de nuevo.")
        parte = lee(min(8192, largo - recibido))
        if not parte:
            raise ErrorHttp(400, "cuerpo_incompleto", "Los datos llegaron incompletos. Prueba de nuevo.")
        trozos.append(parte)
        recibido += len(parte)
    return b"".join(trozos)


@dataclass
class Politica:
    """Reglas de acceso del panel. ``puerto`` se fija tras ``bind`` (con ``--puerto 0`` es efímero)."""

    puerto: int
    token: str = field(default_factory=nuevo_token, repr=False)
    # Dominios públicos por los que se entra al panel a través del túnel de Cloudflare (dueño, 14-nov: «el panel en un dominio»),
    # p. ej. («panel.tu-dominio.com»,). Solo HTTPS. Detrás del túnel hay Cloudflare Access (login con Google) y además la clave del panel.
    publicos: tuple[str, ...] = ()

    def hosts(self) -> frozenset[str]:
        return frozenset({f"127.0.0.1:{self.puerto}", f"localhost:{self.puerto}", *(h.lower() for h in self.publicos)})

    def origenes(self) -> frozenset[str]:
        return frozenset({f"http://127.0.0.1:{self.puerto}", f"http://localhost:{self.puerto}", *(f"https://{h.lower()}" for h in self.publicos)})

    def comprobar_host(self, environ: Mapping[str, object]) -> None:
        """403 si ``Host`` no es ``127.0.0.1:<puerto>`` o ``localhost:<puerto>`` (anti DNS-rebinding)."""
        host = environ.get("HTTP_HOST")
        if not isinstance(host, str) or host.lower() not in self.hosts():
            raise ErrorHttp(403, "host_no_permitido", "Esa dirección no es la del panel local. Abre el panel con la dirección que muestra la terminal al arrancarlo (empieza con 127.0.0.1 o localhost y lleva el puerto).")

    def comprobar_origen(self, environ: Mapping[str, object], *, obligatorio: bool) -> None:
        """403 si ``Origin`` no es propio (o falta cuando ``obligatorio``); ``Origin: null`` siempre se rechaza."""
        origen = environ.get("HTTP_ORIGIN")
        if origen is None:
            if obligatorio:
                raise ErrorHttp(403, "origen_requerido", "Esta operación solo se puede hacer desde la pantalla del propio panel.")
            return
        if not isinstance(origen, str) or origen.lower() not in self.origenes():
            raise ErrorHttp(403, "origen_no_permitido", "Esta operación solo se acepta desde la pantalla del panel local, no desde otra página.")

    def comprobar_sitio_fetch(self, environ: Mapping[str, object]) -> None:
        """Rechaza peticiones que el navegador declara de otro sitio (``Sec-Fetch-Site``)."""
        valor = environ.get("HTTP_SEC_FETCH_SITE")
        if valor is not None and valor not in ("same-origin", "none"):
            raise ErrorHttp(403, "origen_no_permitido", "El pedido vino de otra página web y no del panel; por seguridad se rechazó.")

    def comprobar_token(self, environ: Mapping[str, object], *, consulta: Mapping[str, list[str]] | None = None,
                        permitir_consulta: bool = False) -> None:
        """403 si falta o no coincide ``X-Panel-Token`` (la consulta ``t=`` solo se admite si se pide: SSE)."""
        recibido = environ.get("HTTP_X_PANEL_TOKEN")
        if recibido is None and permitir_consulta and consulta:
            valores = consulta.get("t") or []
            recibido = valores[0] if valores else None
        if not isinstance(recibido, str) or not iguales(recibido, self.token):
            raise ErrorHttp(403, "token_invalido", "Falta la clave de acceso de esta sesión o ya no sirve. Abre el panel con la dirección completa que muestra la terminal al arrancarlo.")
