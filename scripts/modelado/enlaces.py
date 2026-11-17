#!/usr/bin/env python3
"""Enlaces de destino y lectura segura de páginas de venta (D1, Modo D).

Dos cosas:
  1. Sacar la dirección REAL de un anuncio: los enlaces de Meta vienen envueltos
     (`l.facebook.com/l.php?u=…`); se desenvuelven sin visitar Meta y se les quitan los códigos de rastreo.
  2. Leer una página de venta como lo haría un visitante cualquiera, SIN que el contenido ajeno pueda hacernos daño.

Las direcciones salen de anuncios ajenos, es decir, son entradas NO confiables. Por eso `leer_pagina`:
  - solo http/https, puertos 80/443, sin credenciales en la URL;
  - resuelve el DNS y rechaza todo lo que no sea una IP pública (loopback, red privada, enlace local…);
  - se conecta a la IP ya validada (no vuelve a resolver el nombre) y revalida cada redirección;
  - respeta `robots.txt`; si no lo puede leer bien, no entra;
  - sin cookies, sin ejecutar JavaScript, con tope de tamaño, de tiempo y de redirecciones;
  - ante un muro anti-bot (403/429, «Just a moment»…) se detiene: NUNCA lo evade ni reintenta;
  - lo leído es DATO, nunca instrucción: se devuelve como texto plano para que lo juzguen los jueces.

Ningún umbral está fijado aquí: todo viene de los parámetros `modelado_lectura_*`.
"""

from __future__ import annotations

import html
import http.client
import ipaddress
import re
import socket
import ssl
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser
from typing import Any, Callable, Mapping

from scripts.modelado.puntaje_modelar import ErrorBloqueado, ErrorFabrica, ErrorValidacion

# Vocabularios (no umbrales)
ENVOLTORIOS = frozenset({"l.facebook.com", "lm.facebook.com", "l.instagram.com"})
DOMINIOS_DE_META = ("facebook.com", "fb.com", "instagram.com", "meta.com", "whatsapp.com", "messenger.com", "fb.me")
RASTREO = frozenset({"fbclid", "gclid", "msclkid", "ttclid", "igshid", "mc_cid", "mc_eid", "_ga", "_gl",
                     "ref_src", "wbraid", "gbraid"})
UA = "FabricaOfertasLector/1.0 (lectura de paginas publicas; sin cookies; respeta robots.txt)"
UA_ROBOTS = "FabricaOfertasLector"
FRASES_ANTIBOT = ("just a moment", "attention required", "verifying you are human", "verify you are human",
                  "enable javascript and cookies to continue", "checking your browser", "access denied",
                  "are you a robot", "captcha", "unusual traffic")


class ErrorExterno(ErrorFabrica):
    """Falla de red o del sitio ajeno (6)."""

    codigo_salida = 6


# ---------------------------------------------------------------------------
# Direcciones
# ---------------------------------------------------------------------------

def _es_rastreo(nombre: str) -> bool:
    n = nombre.lower()
    return n in RASTREO or n.startswith("utm_")


def limpiar_url(url: str) -> str:
    """URL canónica sin códigos de rastreo ni fragmento. Solo http/https, sin credenciales.

    Errores: ErrorValidacion si no es una URL http(s) válida.
    """
    try:
        p = urllib.parse.urlsplit(str(url).strip())
        puerto = p.port
    except ValueError as exc:
        raise ErrorValidacion(f"URL inválida: {exc}") from exc
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ErrorValidacion(f"solo se admiten URL http/https con host: {str(url)[:80]!r}")
    if p.username or p.password:
        raise ErrorValidacion("la URL no puede llevar credenciales")
    consulta = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not _es_rastreo(k)]
    netloc = p.hostname.lower() + (f":{puerto}" if puerto else "")
    return urllib.parse.urlunsplit((p.scheme, netloc, p.path or "/", urllib.parse.urlencode(consulta), ""))


def desenvolver(url: str) -> str:
    """Si es un envoltorio de Meta (`l.facebook.com/l.php?u=…`) devuelve el destino; si no, la misma URL.

    No visita nada: solo decodifica el parámetro `u`. Admite hasta 3 envoltorios anidados.
    """
    for _ in range(3):
        p = urllib.parse.urlsplit(url)
        if (p.hostname or "").lower() in ENVOLTORIOS and p.path.rstrip("/") in ("/l.php", "/l"):
            destino = urllib.parse.parse_qs(p.query).get("u")
            if not destino:
                raise ErrorValidacion("envoltorio de Meta sin parámetro de destino")
            url = destino[0]
        else:
            break
    return url


def destino_real(url: str) -> str:
    """Dirección real y limpia de un enlace de anuncio (desenvuelve y quita rastreo)."""
    return limpiar_url(desenvolver(url))


def _es_de_meta(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in DOMINIOS_DE_META)


def extraer_destinos(dom: str) -> list[dict[str, Any]]:
    """Destinos externos que enlaza el anuncio, con cuántas veces aparece cada uno (más frecuente primero).

    Solo cuentan los enlaces envueltos por Meta (los que salen del anuncio); se ignoran los de Meta mismo.
    """
    cuentas: dict[str, int] = {}
    for crudo in re.findall(r"""href=["']([^"']+)["']""", dom):
        enlace = html.unescape(crudo)
        try:
            if (urllib.parse.urlsplit(enlace).hostname or "").lower() not in ENVOLTORIOS:
                continue
            destino = destino_real(enlace)
        except (ErrorValidacion, ValueError):
            continue
        if _es_de_meta(urllib.parse.urlsplit(destino).hostname or ""):
            continue
        cuentas[destino] = cuentas.get(destino, 0) + 1
    return [{"url": u, "veces": n} for u, n in sorted(cuentas.items(), key=lambda x: (-x[1], x[0]))]


# ---------------------------------------------------------------------------
# Texto visible
# ---------------------------------------------------------------------------

class _Extractor(HTMLParser):
    """Texto visible y título; ignora scripts, estilos y similares."""

    OMITIR = frozenset({"script", "style", "noscript", "svg", "template", "iframe"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.omitir = 0
        self.en_titulo = False
        self.titulo: list[str] = []
        self.trozos: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.OMITIR:
            self.omitir += 1
        elif tag == "title":
            self.en_titulo = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self.OMITIR and self.omitir:
            self.omitir -= 1
        elif tag == "title":
            self.en_titulo = False

    def handle_data(self, data: str) -> None:
        if self.omitir:
            return
        (self.titulo if self.en_titulo else self.trozos).append(data)


def texto_visible(documento: str, max_caracteres: int) -> tuple[str, str, int]:
    """(título, texto visible acotado, caracteres totales antes de acotar)."""
    ex = _Extractor()
    ex.feed(documento)
    ex.close()
    limpiar = lambda lista: re.sub(r"\s+", " ", " ".join(lista)).strip()  # noqa: E731
    texto = limpiar(ex.trozos)
    return limpiar(ex.titulo), texto[:max_caracteres], len(texto)


# ---------------------------------------------------------------------------
# Red segura
# ---------------------------------------------------------------------------

def validar_destino(url: str, resolver: Callable = socket.getaddrinfo) -> tuple[str, int, list[str]]:
    """(host, puerto, IPs) si la URL es segura de visitar. Errores: ErrorValidacion / ErrorBloqueado."""
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ErrorValidacion("solo http/https")
    if p.username or p.password:
        raise ErrorValidacion("la URL no puede llevar credenciales")
    puerto = p.port or (443 if p.scheme == "https" else 80)
    if puerto not in (80, 443):
        raise ErrorBloqueado(f"puerto {puerto} no permitido (solo 80 y 443)")
    try:
        infos = resolver(p.hostname, puerto, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ErrorExterno(f"no se pudo resolver {p.hostname}: {exc}") from exc
    ips = sorted({i[4][0] for i in infos})
    if not ips:
        raise ErrorExterno(f"{p.hostname} no resuelve a ninguna IP")
    for ip in ips:
        direccion = ipaddress.ip_address(ip.split("%")[0])
        if direccion.version == 6 and direccion.ipv4_mapped:
            direccion = direccion.ipv4_mapped
        if not direccion.is_global or direccion.is_multicast:
            raise ErrorBloqueado(f"{p.hostname} resuelve a una IP no pública ({ip}): no se visita")
    return p.hostname.lower(), puerto, ips


class _HttpFija(http.client.HTTPConnection):
    """HTTP que se conecta a una IP ya validada (no vuelve a resolver el nombre)."""

    def __init__(self, host: str, ip: str, puerto: int, espera: float) -> None:
        super().__init__(host, puerto, timeout=espera)
        self._ip = ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _HttpsFija(http.client.HTTPSConnection):
    """HTTPS fijado a una IP validada, verificando el certificado contra el nombre original."""

    def __init__(self, host: str, ip: str, puerto: int, espera: float, contexto: ssl.SSLContext) -> None:
        super().__init__(host, puerto, timeout=espera, context=contexto)
        self._ip = ip

    def connect(self) -> None:
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def abrir_fijo(url: str, ip: str, p: Mapping[str, Any]) -> dict[str, Any]:
    """Una petición GET sin cookies ni redirecciones, conectada a `ip`. Devuelve estado, cabeceras y cuerpo acotado."""
    partes = urllib.parse.urlsplit(url)
    puerto = partes.port or (443 if partes.scheme == "https" else 80)
    espera = float(p["modelado_lectura_timeout_seg"])
    tope = p["modelado_lectura_max_bytes"]
    ruta = (partes.path or "/") + (f"?{partes.query}" if partes.query else "")
    if partes.scheme == "https":
        conexion: http.client.HTTPConnection = _HttpsFija(partes.hostname, ip, puerto, espera,
                                                           ssl.create_default_context())
    else:
        conexion = _HttpFija(partes.hostname, ip, puerto, espera)
    try:
        conexion.request("GET", ruta, headers={
            "User-Agent": UA, "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5",
            "Accept-Language": "es,en;q=0.8", "Accept-Encoding": "identity"})
        respuesta = conexion.getresponse()
        cuerpo = respuesta.read(tope + 1)
        return {"status": respuesta.status, "location": respuesta.getheader("Location"),
                "content_type": respuesta.getheader("Content-Type") or "",
                "cuerpo": cuerpo[:tope], "truncado": len(cuerpo) > tope}
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        raise ErrorExterno(f"falla de red al leer {partes.hostname}: {exc}") from exc
    finally:
        conexion.close()


def _decodificar(cuerpo: bytes, content_type: str) -> str:
    m = re.search(r"charset=([\w-]+)", content_type, re.I)
    for codificacion in ([m.group(1)] if m else []) + ["utf-8"]:
        try:
            return cuerpo.decode(codificacion, errors="replace")
        except LookupError:
            continue
    return cuerpo.decode("utf-8", errors="replace")


def _robots_permite(url: str, p: Mapping[str, Any], abrir: Callable, resolver: Callable,
                    cache: dict[str, Any]) -> bool:
    partes = urllib.parse.urlsplit(url)
    origen = f"{partes.scheme}://{partes.netloc}"
    if origen not in cache:
        robots_url = origen + "/robots.txt"
        _, _, ips = validar_destino(robots_url, resolver)
        r = abrir(robots_url, ips[0], p)
        parser = urllib.robotparser.RobotFileParser()
        if r["status"] == 200:
            parser.parse(_decodificar(r["cuerpo"], r["content_type"]).splitlines())
            cache[origen] = parser
        elif 400 <= r["status"] < 500:
            cache[origen] = True          # sin robots.txt: se puede entrar
        else:
            cache[origen] = False         # error del sitio: no se asume permiso
    regla = cache[origen]
    return regla if isinstance(regla, bool) else regla.can_fetch(UA_ROBOTS, url)


def leer_pagina(url: str, p: Mapping[str, Any], *, abrir: Callable = abrir_fijo,
                resolver: Callable = socket.getaddrinfo) -> dict[str, Any]:
    """Lee una página de venta pública y devuelve su texto visible. Nunca evade bloqueos.

    Entradas: URL (puede venir envuelta por Meta), parámetros `modelado_lectura_*`; `abrir` y `resolver`
    son inyectables (las pruebas no usan red). Salida: dict con `estado` (ok, bloqueado_robots,
    bloqueado_antibot, http_<n>, no_html, demasiadas_redirecciones), título, texto acotado y advertencias.
    Errores: ErrorValidacion (URL inválida), ErrorBloqueado (destino no público), ErrorExterno (red).
    """
    inicial = destino_real(url)
    salida: dict[str, Any] = {"url": inicial, "url_final": inicial, "estado": "error", "titulo": "",
                              "texto": "", "caracteres": 0, "advertencias": []}
    cache_robots: dict[str, Any] = {}
    actual = inicial
    for salto in range(p["modelado_lectura_max_redirecciones"] + 1):
        _, _, ips = validar_destino(actual, resolver)
        if not _robots_permite(actual, p, abrir, resolver, cache_robots):
            salida.update(url_final=actual, estado="bloqueado_robots")
            return salida
        r = abrir(actual, ips[0], p)
        if 300 <= r["status"] < 400 and r.get("location"):
            actual = limpiar_url(urllib.parse.urljoin(actual, r["location"]))
            continue
        break
    else:
        salida.update(url_final=actual, estado="demasiadas_redirecciones")
        return salida
    salida["url_final"] = actual
    contenido = _decodificar(r["cuerpo"], r["content_type"])
    titulo, texto, total = texto_visible(contenido, p["modelado_lectura_max_caracteres"])
    salida.update(titulo=titulo, texto=texto, caracteres=total)
    if r["truncado"]:
        salida["advertencias"].append("la página superó el tope de bytes: se leyó solo el comienzo")
    if total > len(texto):
        salida["advertencias"].append("el texto superó el tope de caracteres: se acotó")
    bajo = (titulo + " " + texto).lower()
    if r["status"] in (403, 429, 503) or (len(texto) < 600 and any(f in bajo for f in FRASES_ANTIBOT)):
        salida["estado"] = "bloqueado_antibot"          # se informa y se detiene: no se evade ni se reintenta
    elif r["status"] >= 400:
        salida["estado"] = f"http_{r['status']}"
    elif "html" not in r["content_type"].lower() and "text" not in r["content_type"].lower():
        salida["estado"] = "no_html"
    else:
        salida["estado"] = "ok"
    return salida
