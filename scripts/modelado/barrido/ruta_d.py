#!/usr/bin/env python3
"""Ruta D del barrido: el Chrome limpio de `captura.py` recorre una página de BÚSQUEDA de la Biblioteca (D1, Modo D).

Por qué existe: `ads_library_search` entrega como máximo 50 anuncios por consulta; la web de la Biblioteca lista
cientos al hacer scroll (spec departamentos/02-descubrimiento.md §14.7, §15.5 y §17.1.c).

Este módulo NO duplica los frenos: importa de `captura.py` y usa SU lista blanca de direcciones, SU freno
(`empresa/captura/freno.json`), SU registro y tope diario (`empresa/captura/capturas.jsonl`), SU pausa y SUS frases de
bloqueo. Lo único propio es lo nuevo:
  - el driver de Chrome que puede desplazarse (DevTools por TUBERÍA, sin puerto de red) con perfil nuevo y sin sesión;
  - topes PROPIOS por búsqueda (`parametros_ruta_d.propuesta.yaml`): desplazamientos, anuncios, búsquedas por día;
  - el extractor del DOM de resultados y el archivo crudo del contrato (CONTRATO.md §2) con `ruta: "D"`.

Frenos (los de la decisión del dueño, sin excepción)
  - Solo se abre lo que arma `captura.construir_url_busqueda` y valida `captura.normalizar_busqueda`: únicamente
    `https://www.facebook.com/ads/library/` con `ad_type=all`; el driver lo vuelve a comprobar antes de navegar.
  - Chrome con perfil NUEVO y sin sesión (se destruye al terminar); User-Agent honesto (el de «HeadlessChrome», sin
    `--user-agent`); sin proxies, sin extensiones, sin ocultar la automatización. La tubería de DevTools no abre
    ningún puerto. El driver solo navega una vez y se desplaza: no hace clic, no escribe, no inicia sesión.
  - Ritmo humano: antes de CADA paso (carga inicial o desplazamiento) se verifica el freno, se respeta el tope
    diario compartido y se espera la pausa compartida. Cada paso queda en `capturas.jsonl`.
  - Ante CUALQUIER señal de bloqueo (frases de `captura.FRASES_BLOQUEO` y otras en el texto VISIBLE, no en el código
    de la página; redirección fuera de la Biblioteca; HTTP 401/403/429; página rara) se escribe el freno con el
    formato de captura y se DETIENE. Nunca reintenta, nunca cambia de identidad, nunca esquiva nada.
  - Lo que sale de la página es DATO ajeno y no confiable: se copia como texto acotado, jamás se ejecuta.
  - El freno y el tope diario compartidos NO los decide el invocador (revisión de seguridad M1): con la visita real, o con
    `FABRICA_ENTORNO=produccion`, se leen SIEMPRE de `empresa/captura/` del repositorio real; `--estado-dir`, `--raiz`,
    `--parametros` y `--parametros-ruta-d` se rechazan en producción (código 2) y una ruta alterna vale solo en pruebas.
  - Chrome recibe un entorno mínimo explícito (HOME, PATH, LANG, TMPDIR si existen): ningún token ni clave del padre (m5).

Salida (idempotente: una búsqueda ya escrita no se vuelve a abrir)
  - `empresa/barrido/crudo/<corrida_id>/<qid>.json`: SOLO si cumple `comun.validar_crudo` (hoy la web no entrega la
    moneda, el contrato la exige y la búsqueda trae más de 50 anuncios: ver «PEDIDOS» en el informe).
  - `empresa/barrido/crudo/<corrida_id>/<qid>.extra.json`: siempre; lo que la web da y el contrato no admite, y el
    crudo propuesto con `null` cuando no se pudo escribir el oficial.

Uso (desde la raíz, con .venv); sin `--visita-real` solo muestra la dirección y el plan, sin abrir Chrome:
    .venv/bin/python -m scripts.modelado.barrido.ruta_d url --frase "acceso inmediato en PDF" --pais ES
    .venv/bin/python -m scripts.modelado.barrido.ruta_d buscar --corrida 2026-11-06-a --qid es-acceso-inmediato-pdf \\
        --frase "acceso inmediato en PDF" --pais ES --max-desplazamientos 3 --visita-real
Códigos de salida: 0 · 2 uso · 3 validación · 4 bloqueado/freno · 5 límite o parámetro faltante · 6 falla externa.
"""

from __future__ import annotations

import argparse
import bisect
import fcntl
import html
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from scripts.modelado import captura as ca
from scripts.modelado import enlaces
from scripts.modelado import puntaje_modelar as pm
from scripts.modelado.barrido import comun
from scripts.modelado.enlaces import ErrorExterno
from scripts.modelado.puntaje_modelar import ErrorBloqueado, ErrorLimite, ErrorUso, ErrorValidacion

# ---------------------------------------------------------------------------
# Vocabularios (no son umbrales): lo que la página dice, en los idiomas de los mercados de origen
# ---------------------------------------------------------------------------

FRASES_BLOQUEO_EXTRA = (
    "you're temporarily blocked", "you’re temporarily blocked", "going too fast", "rate limit", "too many attempts",
    "demasiados intentos", "confirm your identity", "confirma tu identidad", "something went wrong",
    "algo salió mal", "this page isn't available", "esta página no está disponible", "try again later",
    "inténtalo de nuevo más tarde", "intenta de nuevo más tarde",
)
MARCAS_SIN_RESULTADOS = (
    "no ads match", "we couldn't find any ads", "no se encontraron anuncios", "no hay anuncios que coincidan",
    "ningún anuncio coincide", "nenhum anúncio corresponde", "nessun annuncio corrisponde", "aucune publicité ne correspond",
)
ETIQUETAS_ID = ("identificador de la biblioteca",            # observado en la visita de sondeo (interfaz en español)
                "library id", "id de la biblioteca", "id de biblioteca", "id da biblioteca", "id della libreria",
                "id de la bibliothèque")
ETIQUETAS_INICIO = ("started running on", "en circulación desde el", "en circulación desde", "se empezó a publicar el",
                    "comenzó a publicarse el", "veiculação iniciada em", "iniciado em", "in circolazione dal",
                    "attivo dal")
MESES = {"ene": 1, "jan": 1, "gen": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "mag": 5, "mai": 5, "jun": 6,
         "giu": 6, "jul": 7, "lug": 7, "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10, "out": 10, "ott": 10,
         "nov": 11, "dic": 12, "dec": 12, "dez": 12}
PLATAFORMAS = ("facebook", "instagram", "audience network", "messenger", "whatsapp", "threads")
ESTADOS_ANUNCIO_TEXTO = {"active": "activo", "activo": "activo", "ativo": "activo", "attivo": "activo",
                         "inactive": "inactivo", "inactivo": "inactivo", "inativo": "inactivo", "inattivo": "inactivo"}
# Los íconos de plataforma de la tarjeta son <svg> sin nombre accesible: se reconocen por el comienzo de su trazo.
# Observado en la visita de sondeo del 2026-11-06; las plataformas sin firma conocida no se nombran (jamás se adivinan).
FIRMAS_ICONO_PLATAFORMA = {"M12 6.022C12 2.696 9.314 0 6 0S0 2.696": "facebook", "M6 3.227a2.773 2.773": "instagram"}
BOTONES_DE_ACCION = frozenset({"más información", "comprar", "comprar ahora", "learn more", "shop now", "ver más", "registrarte",
                               "suscribirte", "descargar", "enviar mensaje", "send message", "obtener oferta", "reservar",
                               "solicitar ahora", "contáctanos", "book now", "sign up", "download", "get offer",
                               "apply now", "contact us", "see more", "ver menú", "pedir ahora", "ir a whatsapp"})
PAGINAS_RESERVADAS = frozenset({"ads", "help", "l.php", "login", "policies", "privacy", "legal", "business", "about",
                                "pages", "settings", "terms", "cookies", "watch", "groups", "events", "marketplace",
                                "gaming", "stories", "reel", "reels", "share", "sharer", "dialog", "plugins", "tr"})
ESTADOS_HTTP_BLOQUEO = frozenset({401, 403, 429})          # códigos HTTP que el sitio usa para decir «no»
TIPOS_DE_RED_VIGILADOS = frozenset({"Document", "XHR", "Fetch"})
ESTADOS_DE_ESTADO = {"active": "ACTIVE", "inactive": "INACTIVE", "all": "ALL"}   # búsqueda web -> contrato §2
ESTADO_TARJETA_OPUESTO = {"active": "inactivo", "inactive": "activo"}   # lo que NO debe entrar según el filtro de la búsqueda
ENTORNOS = ("desarrollo", "prueba", "produccion")          # mismo vocabulario que cli.py y engine/guard.py
ENTORNO_DE_CHROME = ("HOME", "PATH", "LANG", "TMPDIR")      # lo único que hereda el navegador (si existe)
FLAGS_QUE_MUEVEN_LOS_FRENOS = (("estado_dir", "--estado-dir"), ("raiz", "--raiz"), ("parametros", "--parametros"),
                               ("parametros_ruta_d", "--parametros-ruta-d"))
SUFIJO_EXTRA = ".extra.json"
SUFIJO_ERROR = ".error.json"
PEDIDOS_AL_CONTRATO = (
    "P1: validar_crudo debe aceptar currency=null cuando ruta == 'D' (la web de la Biblioteca no muestra la moneda de "
    "la cuenta; derivarla del país destruiría la señal de exportadores de §17.2).",
    "P2: validar_crudo debe aceptar len(ads) > 50 cuando ruta == 'D' (consulta.limit hasta ruta_d_max_anuncios_por_busqueda).",
    "P3: validar_crudo debe aceptar page_id=null y ad_delivery_start_time=null cuando ruta == 'D' y la web no los dio.",
    "P4: comun.listar_crudos debe excluir también los '*.extra.json' (hoy solo excluye '*.error.json': devolvería el "
    "extra como si fuera un crudo y leer_crudo fallaría por nombre).",
)

_RE_ID_TEXTO = re.compile(r"(?:%s)\s*[:：]?\s*(\d{5,20})(?!\d)" % "|".join(re.escape(e) for e in ETIQUETAS_ID), re.I)
_RE_INICIO = re.compile(r"(?:%s)\s*(.{0,60})" % "|".join(re.escape(e) for e in ETIQUETAS_INICIO), re.I)
_RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_RE_FECHA_MES_PRIMERO = re.compile(r"([^\W\d_]{3,12})\.?\s+(\d{1,2}),?\s+(\d{4})")
_RE_FECHA_DIA_PRIMERO = re.compile(r"(\d{1,2})\s+(?:de\s+)?([^\W\d_]{3,12})\.?(?:\s+de)?,?\s+(\d{4})")
_RE_TOTAL = re.compile(r"(?<![\w.,])(?:~|≈|about\s+|approximately\s+|aprox\.?\s*)?"
                       r"(\d{1,3}(?:[.,\s  ]\d{3})+|\d+)\+?\s+(?:results?|resultados?|risultati|résultats)\b", re.I)
_RE_VARIANTES = re.compile(r"(\d[\d.,]*)\s+(?:ads|anuncios|anúncios|annunci)\s+(?:use|usan|utilizan|usam|utilizzano)\b", re.I)
_RE_ESTADO = re.compile(r"\b(active|inactive|activo|inactivo|ativo|inativo|attivo|inattivo)\b", re.I)
_RE_PLATAFORMAS = re.compile(r"(?:platforms|plataformas|piattaforme)\s*:?\s*((?:(?:%s)[\s,/·&y]*)+)" %
                             "|".join(re.escape(x) for x in PLATAFORMAS), re.I)
_RE_DOMINIO = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_RE_PAGINA_NUM = re.compile(r"^(?:https?://(?:www\.|m\.|web\.)?facebook\.com)?/(\d{5,20})/?(?:[?#].*)?$", re.I)
_RE_PAGINA_VANITY = re.compile(r"^https?://(?:www\.|m\.|web\.)?facebook\.com/([A-Za-z0-9.\-_]{5,50})/?(?:[?#].*)?$", re.I)
_RE_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1f\x7f-\x9f\u200b\u200e\u200f\u2060\ufeff]")   # controles y espacios de ancho cero
_RE_ESPACIOS = re.compile(r"\s+")
_VACIAS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
                     "track", "wbr"})
_OCULTAS = frozenset({"script", "style", "noscript", "svg", "template", "iframe", "head"})   # como enlaces.texto_visible
_ENCABEZADOS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_ATRIBUTOS_ROTULO = ("aria-label", "title", "alt", "data-platform")


# ---------------------------------------------------------------------------
# Parámetros propios (falla cerrado)
# ---------------------------------------------------------------------------

CLAVES_RUTA_D = (
    "ruta_d_max_desplazamientos_por_busqueda", "ruta_d_max_busquedas_por_dia", "ruta_d_max_anuncios_por_busqueda",
    "ruta_d_espera_desplazamiento_ms", "ruta_d_desplazamientos_sin_nuevos_max", "ruta_d_dom_max_caracteres",
    "ruta_d_texto_anuncio_max_caracteres", "ruta_d_campo_corto_max_caracteres",
)
RUTA_PARAMETROS_RUTA_D: Path = comun.RAIZ / "scripts" / "modelado" / "barrido" / "parametros_ruta_d.propuesta.yaml"
CLAVES_COMPARTIDAS = ("modelado_captura_pausa_seg", "modelado_captura_max_por_dia", "modelado_captura_espera_ms",
                      "modelado_captura_timeout_seg", "modelado_lectura_max_caracteres")


def cargar_parametros_ruta_d(ruta: Path | None = None) -> dict[str, int]:
    """Carga los topes propios de la ruta D. Errores: ErrorLimite si falta uno o sale de su rango; ErrorValidacion si no es entero."""
    import yaml  # PyYAML está en requirements.txt de la raíz

    ruta = Path(ruta) if ruta is not None else RUTA_PARAMETROS_RUTA_D
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer los parámetros de la ruta D {ruta}: {exc} "
                          "(falla cerrado: sin topes propios no se abre ninguna búsqueda)") from exc
    except yaml.YAMLError as exc:
        raise ErrorValidacion(f"{ruta}: YAML inválido ({exc})") from exc
    entradas: dict[str, Any] = {}
    for grupo in ((datos or {}).get("grupos") or {}).values():
        if isinstance(grupo, dict):
            entradas.update({k: v for k, v in grupo.items() if isinstance(v, dict) and "valor" in v})
    faltan = [c for c in CLAVES_RUTA_D if c not in entradas or entradas[c].get("valor") is None]
    if faltan:
        raise ErrorLimite(f"faltan parámetros de la ruta D en {ruta}: {', '.join(faltan)} "
                          "(falla cerrado: no se asume ningún valor)")
    salida: dict[str, int] = {}
    for clave in CLAVES_RUTA_D:
        valor = entradas[clave]["valor"]
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
            raise ErrorValidacion(f"{clave}: se esperaba un entero ≥ 1, llegó {valor!r}")
        rango = entradas[clave].get("rango")
        if not (isinstance(rango, (list, tuple)) and len(rango) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in rango)):
            raise ErrorLimite(f"{clave}: sin «rango» aprobado [mínimo, máximo] en {ruta} (falla cerrado: un tope sin rango no se acepta)")
        if not rango[0] <= valor <= rango[1]:
            raise ErrorLimite(f"{clave}: {valor} fuera del rango aprobado {list(rango)} (falla cerrado)")
        salida[clave] = valor
    return salida


def es_produccion() -> bool:
    """True si `FABRICA_ENTORNO=produccion` (vacío = desarrollo). Un valor desconocido falla cerrado (ErrorUso)."""
    entorno = (os.environ.get("FABRICA_ENTORNO") or "desarrollo").strip()
    if entorno not in ENTORNOS:
        raise ErrorUso(f"FABRICA_ENTORNO inválido: se esperaba uno de {', '.join(ENTORNOS)}")
    return entorno == "produccion"


def estado_dir_real() -> Path:
    """`empresa/captura/` del repositorio REAL (donde viven el freno y el tope diario compartidos con captura.py).

    Sale de la ubicación de este archivo, no de `FABRICA_RAIZ` ni de ningún flag: nadie puede redirigirlo.
    """
    return comun.RAIZ / "empresa" / "captura"


def exigir_estado_real(estado_dir: Path, raiz: Path | None, abrir_sesion: Callable | None) -> None:
    """M1: el freno y el tope diario compartidos NO los decide el invocador.

    Con `FABRICA_ENTORNO=produccion` solo vale el estado real y no hay raíz alterna; con el driver real de Chrome
    (la visita de verdad) vale únicamente el estado real. Una ruta alterna existe solo para las pruebas, que
    inyectan una sesión falsa. Errores: ErrorUso.
    """
    alterna = Path(estado_dir).resolve() != estado_dir_real().resolve()
    if es_produccion() and (alterna or raiz is not None):
        raise ErrorUso("--estado-dir y --raiz no existen con FABRICA_ENTORNO=produccion: el freno y el tope diario "
                       "se leen siempre de empresa/captura/ del repositorio real")
    if abrir_sesion is SesionChrome and alterna:
        raise ErrorUso("la visita real solo lee el freno y el tope diario de empresa/captura/ del repositorio real: "
                       "una ruta alterna vale solo en pruebas, con una sesión inyectada")


def entorno_minimo_de_chrome() -> dict[str, str]:
    """m5: el entorno explícito del navegador (HOME, PATH, LANG, TMPDIR si existen). Sin tokens ni claves del padre."""
    return {k: os.environ[k] for k in ENTORNO_DE_CHROME if k in os.environ}


def _exigir_compartidos(p: Mapping[str, Any]) -> None:
    faltan = [c for c in CLAVES_COMPARTIDAS if c not in p]
    if faltan:
        raise ErrorLimite(f"faltan parámetros compartidos de captura: {', '.join(faltan)} (falla cerrado)")


# ---------------------------------------------------------------------------
# Direcciones: solo las de captura.py
# ---------------------------------------------------------------------------

def url_busqueda(frase: str | None = None, pais: str = "ALL", *, exacta: bool = True, estado: str = "active",
                 pagina_id: str | int | None = None) -> str:
    """URL de búsqueda armada SIEMPRE con `captura.construir_url_busqueda` y validada con `captura.normalizar_busqueda`."""
    url = ca.construir_url_busqueda(frase, pais, exacta=exacta, estado=estado, pagina_id=pagina_id)
    return ca.normalizar_busqueda(url)


def exigir_url_canonica(url: str) -> str:
    """Devuelve `url` si ya es la forma canónica de la lista blanca; cualquier otra cosa = ErrorValidacion."""
    if ca.normalizar_busqueda(url) != url:
        raise ErrorValidacion("la sesión solo abre las direcciones canónicas de captura.normalizar_busqueda")
    return url


def _es_de_la_biblioteca(url: str) -> bool:
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return p.scheme == "https" and p.netloc == "www.facebook.com" and p.path.startswith("/ads/library")


def frases_bloqueo() -> tuple[str, ...]:
    """Las frases de `captura.FRASES_BLOQUEO` (siempre las vigentes) más las propias de las páginas de búsqueda."""
    return tuple(ca.FRASES_BLOQUEO) + FRASES_BLOQUEO_EXTRA


# ---------------------------------------------------------------------------
# Texto de la página (dato NO confiable)
# ---------------------------------------------------------------------------

def _limpio(texto: str, maximo: int | None = None) -> str:
    """Quita controles, colapsa espacios y acota. Es lo único que se hace con el texto ajeno: nunca se interpreta."""
    t = _RE_ESPACIOS.sub(" ", _RE_CONTROL.sub("", str(texto))).strip()
    return t if maximo is None else t[:maximo]


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def parsear_fecha(texto: str) -> tuple[int, str] | None:
    """(epoch en segundos a las 00:00 UTC, fecha en texto) de una fecha escrita como «Nov 5, 2026», «5 de noviembre de 2026»
    o «2026-11-05». None si no se entiende (jamás se adivina). La web da solo el DÍA: la precisión es de un día."""
    t = _limpio(texto)
    candidatos: list[tuple[int, int, int, str]] = []
    if m := _RE_FECHA_ISO.match(t):
        candidatos.append((int(m[1]), int(m[2]), int(m[3]), m[0]))
    if m := _RE_FECHA_MES_PRIMERO.match(t):
        mes = MESES.get(_sin_acentos(m[1]).lower()[:3])
        if mes:
            candidatos.append((int(m[3]), mes, int(m[2]), m[0]))
    if m := _RE_FECHA_DIA_PRIMERO.match(t):
        mes = MESES.get(_sin_acentos(m[2]).lower()[:3])
        if mes:
            candidatos.append((int(m[3]), mes, int(m[1]), m[0]))
    for anio, mes, dia, original in candidatos:
        try:
            momento = datetime(anio, mes, dia, tzinfo=timezone.utc)
        except ValueError:
            continue
        if momento.timestamp() >= 1:
            return int(momento.timestamp()), original
    return None


def extraer_total(texto: str) -> int | None:
    """Total estimado de resultados que muestra la cabecera («~932 results»); None si no aparece (jamás se inventa)."""
    m = _RE_TOTAL.search(texto)
    if not m:
        return None
    digitos = re.sub(r"\D", "", m[1])
    return int(digitos) if 0 < len(digitos) <= 9 else None


# ---------------------------------------------------------------------------
# Árbol mínimo del DOM (sin dependencias) y extracción de tarjetas
# ---------------------------------------------------------------------------

class _Arbol(HTMLParser):
    """Árbol plano del DOM: cada elemento ocupa un rango [ini, fin) de posiciones; los textos visibles también tienen posición."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.etiqueta: list[str] = []
        self.atributos: list[dict[str, str]] = []
        self.padre: list[int] = []
        self.ini: list[int] = []
        self.fin: list[int] = []
        self.t_pos: list[int] = []
        self.t_txt: list[str] = []
        self.t_padre: list[int] = []
        self.pos = 0
        self._pila: list[int] = []
        self._oculta: list[bool] = []
        self._ocultos = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        idx = len(self.etiqueta)
        atributos: dict[str, str] = {}
        for nombre, valor in attrs:
            atributos.setdefault(nombre.lower(), valor or "")
        self.etiqueta.append(tag)
        self.atributos.append(atributos)
        self.padre.append(self._pila[-1] if self._pila else -1)
        self.ini.append(self.pos)
        self.fin.append(-1)
        self.pos += 1
        if tag in _VACIAS:
            self.fin[idx] = self.pos
        else:
            self._pila.append(idx)
            self._oculta.append(tag in _OCULTAS)
            if tag in _OCULTAS:
                self._ocultos += 1

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VACIAS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for j in range(len(self._pila) - 1, -1, -1):
            if self.etiqueta[self._pila[j]] == tag:
                while len(self._pila) > j:
                    idx = self._pila.pop()
                    self.fin[idx] = self.pos
                    if self._oculta.pop():
                        self._ocultos -= 1
                return

    def handle_data(self, data: str) -> None:
        if self._ocultos or not data.strip():
            return
        self.t_pos.append(self.pos)
        self.t_txt.append(data)
        self.t_padre.append(self._pila[-1] if self._pila else -1)
        self.pos += 1

    def cerrar_todo(self) -> None:
        while self._pila:
            self.fin[self._pila.pop()] = self.pos + 1


def _construir_arbol(dom: str) -> _Arbol:
    arbol = _Arbol()
    try:
        arbol.feed(dom)
        arbol.close()
    except Exception as exc:  # noqa: BLE001  el analizador de HTML es de la biblioteca estándar; se convierte en error tipado
        raise ErrorValidacion(f"el DOM no se pudo analizar ({type(exc).__name__})") from exc
    arbol.cerrar_todo()
    return arbol


def _id_de_ficha(href: str) -> str | None:
    """Id de anuncio de un enlace a la ficha (`…/ads/library/?id=<número>`); None si no lo es."""
    try:
        p = urllib.parse.urlsplit(html.unescape(href))
    except ValueError:
        return None
    if p.netloc not in ("", "www.facebook.com", "facebook.com") or p.path != "/ads/library/":
        return None
    for nombre, valor in urllib.parse.parse_qsl(p.query):
        if nombre == "id" and re.fullmatch(r"\d{5,20}", valor):
            return valor
    return None


def _ocurrencias(a: _Arbol) -> list[tuple[int, int, str]]:
    """(posición, elemento, id) de cada vez que la página nombra un id de anuncio: «Library ID: N» o un enlace `?id=N`."""
    res: list[tuple[int, int, str]] = []
    if a.t_txt:
        inicios, acum = [], 0
        for t in a.t_txt:
            inicios.append(acum)
            acum += len(t) + 1
        total = " ".join(a.t_txt)
        for m in _RE_ID_TEXTO.finditer(total):
            k = bisect.bisect_right(inicios, m.start(1)) - 1
            res.append((a.t_pos[k], a.t_padre[k], m[1]))
    for i, atributos in enumerate(a.atributos):
        if a.etiqueta[i] == "a" and "href" in atributos:
            ident = _id_de_ficha(atributos["href"])
            if ident:
                res.append((a.ini[i], i, ident))
    res.sort()
    return res


def _tarjetas(a: _Arbol, ocurrencias: list[tuple[int, int, str]]) -> dict[str, int]:
    """id -> elemento de su tarjeta: el ancestro más alto que contiene ese id y NINGÚN otro."""
    n = len(ocurrencias)
    pos = [o[0] for o in ocurrencias]
    ids = [o[2] for o in ocurrencias]
    previo, siguiente = [-1] * n, [n] * n
    for k in range(1, n):
        previo[k] = previo[k - 1] if ids[k] == ids[k - 1] else k - 1
    for k in range(n - 2, -1, -1):
        siguiente[k] = siguiente[k + 1] if ids[k] == ids[k + 1] else k + 1
    tarjetas: dict[str, int] = {}
    for k, (_, elem, ident) in enumerate(ocurrencias):
        if ident in tarjetas:
            continue
        mejor, e = elem, a.padre[elem]
        while e != -1:
            lo, hi = bisect.bisect_left(pos, a.ini[e]), bisect.bisect_left(pos, a.fin[e])
            if lo > previo[k] and hi <= siguiente[k]:
                mejor, e = e, a.padre[e]
            else:
                break
        tarjetas[ident] = mejor
    return tarjetas


def _datos_de_tarjeta(a: _Arbol, ident: str, elem: int, pr: Mapping[str, int]) -> dict[str, Any]:
    corto, largo = pr["ruta_d_campo_corto_max_caracteres"], pr["ruta_d_texto_anuncio_max_caracteres"]
    p0, p1 = a.ini[elem], a.fin[elem]
    i0, i1 = bisect.bisect_left(a.t_pos, p0), bisect.bisect_left(a.t_pos, p1)
    texto_completo = _limpio(" ".join(a.t_txt[i0:i1]))
    j0, j1 = bisect.bisect_left(a.ini, p0), bisect.bisect_left(a.ini, p1)
    page_id, nombre, vanity, hrefs, titulo_candidatos, plataformas = None, "", None, [], [], set()
    ancla_envuelta = None

    def texto_de(j: int) -> str:
        k0, k1 = bisect.bisect_left(a.t_pos, a.ini[j]), bisect.bisect_left(a.t_pos, a.fin[j])
        return _limpio(" ".join(a.t_txt[k0:k1]))

    for j in range(j0, j1):
        atributos, etiqueta = a.atributos[j], a.etiqueta[j]
        for clave in _ATRIBUTOS_ROTULO:
            valor = atributos.get(clave, "").strip().lower()
            if valor in PLATAFORMAS:
                plataformas.add(valor)
        if etiqueta == "path":
            trazo = atributos.get("d", "")
            plataformas.update(nombre_p for firma, nombre_p in FIRMAS_ICONO_PLATAFORMA.items() if trazo.startswith(firma))
        if etiqueta in _ENCABEZADOS or atributos.get("role", "").lower() == "heading":
            titulo_candidatos.append(texto_de(j))
        if etiqueta != "a" or not atributos.get("href"):
            continue
        href = html.unescape(atributos["href"]).strip()
        hrefs.append(href)
        if ancla_envuelta is None and urllib.parse.urlsplit(href).netloc.lower() in enlaces.ENVOLTORIOS:
            ancla_envuelta = j
        if page_id is None:
            consulta = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(href).query))
            id_pagina = consulta.get("view_all_page_id") if re.fullmatch(r"\d{5,20}", consulta.get("view_all_page_id", "")) else None
            if id_pagina is None and (m := _RE_PAGINA_NUM.match(href)):
                id_pagina = m[1]
            if id_pagina is not None:
                page_id, nombre = int(id_pagina), texto_de(j) or nombre
                continue
        if vanity is None and (m := _RE_PAGINA_VANITY.match(href)) and m[1].lower() not in PAGINAS_RESERVADAS:
            vanity = m[1]
            nombre = nombre or texto_de(j)
    inicio = None
    if m := _RE_INICIO.search(texto_completo):
        inicio = parsear_fecha(m[1])
    if inicio is None and (m := _RE_ID_TEXTO.search(texto_completo)):     # inactivas: «1 ago 2026 - 4 ago 2026» tras el id
        inicio = parsear_fecha(texto_completo[m.end():m.end() + 40])
    activo = None
    if m := _RE_ESTADO.search(texto_completo):
        activo = ESTADOS_ANUNCIO_TEXTO[m[1].lower()]
    if m := _RE_PLATAFORMAS.search(texto_completo):
        plataformas.update(x for x in PLATAFORMAS if x in m[1].lower())
    variantes = None
    if m := _RE_VARIANTES.search(texto_completo):
        digitos = re.sub(r"\D", "", m[1])
        variantes = int(digitos) if 0 < len(digitos) <= 9 else None
    titulo, fuente_titulo = "", "ninguna"
    if ancla_envuelta is not None:       # el bloque del enlace del anuncio es: DOMINIO, titular, descripción (observado)
        k0, k1 = bisect.bisect_left(a.t_pos, a.ini[ancla_envuelta]), bisect.bisect_left(a.t_pos, a.fin[ancla_envuelta])
        trozos = [x for x in (_limpio(t) for t in a.t_txt[k0:k1]) if x]
        if len(trozos) >= 2 and _RE_DOMINIO.fullmatch(trozos[0]) and trozos[1].lower() not in BOTONES_DE_ACCION:
            titulo, fuente_titulo = trozos[1], "enlace"
    if not titulo:
        titulo = next((t for t in titulo_candidatos if t and t != nombre), "")
        fuente_titulo = "encabezado" if titulo else "ninguna"
    destinos = enlaces.extraer_destinos("".join(f'<a href="{html.escape(h, quote=True)}">' for h in hrefs))
    return {
        "id": ident, "page_id": page_id, "page_name": _limpio(nombre, corto), "page_vanity": vanity,
        "titulo": _limpio(titulo, corto), "titulo_fuente": fuente_titulo,
        "inicio_epoch": inicio[0] if inicio else None, "inicio_texto": inicio[1] if inicio else None,
        "estado_anuncio": activo, "plataformas": sorted(plataformas), "variantes": variantes,
        "texto": texto_completo[:largo], "destinos": destinos,
    }


def extraer_anuncios(dom: str, pr: Mapping[str, int]) -> tuple[list[dict[str, Any]], str]:
    """(anuncios en el orden de la página, texto de la cabecera anterior a la primera tarjeta).

    Una tarjeta es el bloque más grande que contiene UN solo id de anuncio («Library ID: N» o un enlace `?id=N`). Todo
    lo que se lee es dato ajeno: se limpia y se acota, nunca se interpreta. Sin duplicados (el primero gana).
    """
    a = _construir_arbol(dom)
    ocurrencias = _ocurrencias(a)
    if not ocurrencias:
        return [], _limpio(" ".join(a.t_txt))
    tarjetas = _tarjetas(a, ocurrencias)
    primera = min(a.ini[e] for e in tarjetas.values())
    cabecera = _limpio(" ".join(a.t_txt[:bisect.bisect_left(a.t_pos, primera)]))
    return [_datos_de_tarjeta(a, ident, elem, pr) for ident, elem in tarjetas.items()], cabecera


def fusionar_anuncios(acumulado: dict[str, dict[str, Any]], nuevos: Sequence[Mapping[str, Any]]) -> int:
    """Suma `nuevos` al acumulado (por id, sin duplicar; completa campos vacíos). Devuelve cuántos ids son nuevos. Idempotente."""
    agregados = 0
    for ad in nuevos:
        actual = acumulado.get(ad["id"])
        if actual is None:
            acumulado[ad["id"]] = dict(ad)
            agregados += 1
            continue
        for clave, valor in ad.items():
            if actual.get(clave) in (None, "", [], 0) and valor not in (None, "", []):
                actual[clave] = valor
    return agregados


# ---------------------------------------------------------------------------
# Análisis de una instantánea de la página (puro, sin red)
# ---------------------------------------------------------------------------

def analizar_busqueda(dom: str, pr: Mapping[str, int], *, estados_http: Sequence[Mapping[str, Any]] = (),
                      url_final: str | None = None) -> dict[str, Any]:
    """Estado de una instantánea: `ok` (hay anuncios), `sin_resultados`, `bloqueado` o `rara`.

    `bloqueado`: frase de bloqueo en el texto VISIBLE (no en scripts), redirección fuera de la Biblioteca o HTTP 401/403/429.
    `rara`: sin anuncios reconocibles ni mensaje de «sin resultados», o un DOM desmesurado. Ambos activan el freno.
    """
    motivos: list[str] = []
    if url_final is not None and not _es_de_la_biblioteca(url_final):
        partes = urllib.parse.urlsplit(url_final)
        motivos.append(f"redirigido fuera de la Biblioteca: {_limpio(partes.netloc, 80)}{_limpio(partes.path, 80)}")
    for e in estados_http:
        estado, tipo = e.get("estado"), e.get("tipo")
        destino = f" en {_limpio(str(e.get('destino') or ''), 120)}" if e.get("destino") else ""
        if estado in ESTADOS_HTTP_BLOQUEO:
            motivos.append(f"HTTP {estado} ({tipo}){destino}")
        elif tipo == "Document" and isinstance(estado, int) and estado >= 400:
            motivos.append(f"HTTP {estado} en la página{destino}")
    if len(dom) > pr["ruta_d_dom_max_caracteres"]:
        return {"estado": "rara", "anuncios": [], "total": None, "motivos": motivos + ["DOM mayor al tope permitido"]}
    _, texto, _ = enlaces.texto_visible(dom, 10 ** 9)     # igual que captura.analizar_dom: la detección mira TODO el texto visible
    bajo = texto.lower()
    motivos += [f for f in frases_bloqueo() if f in bajo]
    if motivos:
        return {"estado": "bloqueado", "anuncios": [], "total": None, "motivos": motivos}
    anuncios, cabecera = extraer_anuncios(dom, pr)
    total = extraer_total(cabecera)
    if anuncios:
        return {"estado": "ok", "anuncios": anuncios, "total": total, "motivos": []}
    if any(m in bajo for m in MARCAS_SIN_RESULTADOS):
        return {"estado": "sin_resultados", "anuncios": [], "total": 0, "motivos": []}
    return {"estado": "rara", "anuncios": [], "total": None,
            "motivos": ["página rara: sin anuncios reconocibles ni mensaje de «sin resultados»"]}


# ---------------------------------------------------------------------------
# Chrome limpio con desplazamiento: DevTools por tubería (sin puerto de red)
# ---------------------------------------------------------------------------

class _Cdp:
    """Mensajes de DevTools sobre dos tuberías (Chrome lee el fd 3 y escribe el fd 4). Terminados en NUL."""

    def __init__(self, fd_envio: int, fd_lectura: int) -> None:
        self.fd_envio, self.fd_lectura = fd_envio, fd_lectura
        self.eventos: list[dict[str, Any]] = []
        self._buf = bytearray()
        self._sig = 0

    def enviar(self, metodo: str, params: Mapping[str, Any] | None = None, sesion: str | None = None) -> int:
        self._sig += 1
        msg: dict[str, Any] = {"id": self._sig, "method": metodo, "params": dict(params or {})}
        if sesion:
            msg["sessionId"] = sesion
        datos = json.dumps(msg).encode("utf-8") + b"\0"
        while datos:
            try:
                n = os.write(self.fd_envio, datos)
            except OSError as exc:
                raise ErrorExterno(f"no se pudo hablar con Chrome: {exc}") from exc
            datos = datos[n:]
        return self._sig

    def _siguiente(self, limite: float) -> dict[str, Any] | None:
        while True:
            i = self._buf.find(b"\0")
            if i >= 0:
                bruto = bytes(self._buf[:i])
                del self._buf[:i + 1]
                if not bruto:
                    continue
                try:
                    msg = json.loads(bruto)
                except ValueError as exc:
                    raise ErrorExterno("Chrome envió un mensaje ilegible") from exc
                if not isinstance(msg, dict):
                    raise ErrorExterno("Chrome envió un mensaje inesperado")
                return msg
            resto = limite - time.monotonic()
            if resto <= 0:
                return None
            listos, _, _ = select.select([self.fd_lectura], [], [], resto)
            if not listos:
                return None
            try:
                datos = os.read(self.fd_lectura, 1 << 20)
            except OSError as exc:
                raise ErrorExterno(f"no se pudo leer de Chrome: {exc}") from exc
            if not datos:
                raise ErrorExterno("Chrome cerró la conexión")
            self._buf += datos

    def llamar(self, metodo: str, params: Mapping[str, Any] | None = None, sesion: str | None = None,
               espera: float = 30.0) -> dict[str, Any]:
        ident = self.enviar(metodo, params, sesion)
        limite = time.monotonic() + espera
        while True:
            msg = self._siguiente(limite)
            if msg is None:
                raise ErrorExterno(f"Chrome no respondió a {metodo} en {espera:g} s")
            if msg.get("id") == ident:
                if "error" in msg:
                    raise ErrorExterno(f"Chrome rechazó {metodo}: {str(msg['error'])[:200]}")
                resultado = msg.get("result")
                return resultado if isinstance(resultado, dict) else {}
            self.eventos.append(msg)

    def bombear(self, segundos: float) -> None:
        """Deja correr la página `segundos` reales recogiendo sus eventos (no envía nada)."""
        limite = time.monotonic() + segundos
        while (msg := self._siguiente(limite)) is not None:
            self.eventos.append(msg)

    def esperar_evento(self, metodo: str, espera: float) -> bool:
        limite = time.monotonic() + espera
        vistos = 0
        while True:
            for msg in self.eventos[vistos:]:
                if msg.get("method") == metodo:
                    return True
            vistos = len(self.eventos)
            msg = self._siguiente(limite)
            if msg is None:
                return False
            self.eventos.append(msg)


def _host_y_ruta(url: Any) -> str:
    """Solo host y ruta de una dirección (sin parámetros), acotados: para explicar un HTTP de error sin guardar tokens."""
    try:
        partes = urllib.parse.urlsplit(str(url))
    except ValueError:
        return ""
    return _limpio(partes.netloc + partes.path, 120)


def estados_http_de(eventos: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Respuestas de red con error (≥ 400) de documentos y llamadas XHR/Fetch; las imágenes y favicon no cuentan."""
    salida = []
    for e in eventos:
        if e.get("method") != "Network.responseReceived":
            continue
        params = e.get("params")
        respuesta = params.get("response") if isinstance(params, dict) else None
        if not isinstance(respuesta, dict):
            continue
        estado, tipo = respuesta.get("status"), params.get("type")
        if tipo in TIPOS_DE_RED_VIGILADOS and isinstance(estado, int) and estado >= 400:
            salida.append({"tipo": tipo, "estado": estado, "destino": _host_y_ruta(respuesta.get("url"))})
    return salida


class SesionChrome:
    """Una pestaña de Chrome sin pantalla con perfil NUEVO y sin sesión: navega UNA vez y se desplaza. Nada más.

    No hace clic, no escribe, no inicia sesión, no cambia el User-Agent, no usa proxies ni extensiones, no oculta la
    automatización y no abre ningún puerto (DevTools por tubería). El perfil se destruye en `cerrar()`.
    """

    def __init__(self, p: Mapping[str, Any], pr: Mapping[str, int]) -> None:
        self._p, self._pr = p, pr
        self._cerrada = False
        self._sesion_id: str | None = None
        chrome = os.environ.get("FABRICA_CHROME") or ca.CHROME_POR_DEFECTO
        if not Path(chrome).exists():
            raise ErrorLimite(f"no encuentro Chrome en {chrome}; definí FABRICA_CHROME con la ruta del ejecutable")
        self._perfil = tempfile.mkdtemp(prefix="perfil_busqueda_")
        a_r, a_w = os.pipe()
        b_r, b_w = os.pipe()

        def hijo() -> None:     # el hijo ve las tuberías como fd 3 (lee) y fd 4 (escribe), que es lo que Chrome espera
            a = fcntl.fcntl(a_r, fcntl.F_DUPFD, 10)
            b = fcntl.fcntl(b_w, fcntl.F_DUPFD, 10)
            os.dup2(a, 3)
            os.dup2(b, 4)

        comando = [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                   f"--user-data-dir={self._perfil}", "--remote-debugging-pipe", "--window-size=1280,1000",
                   "about:blank"]
        try:
            self._proc = subprocess.Popen(comando, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL, pass_fds=(3, 4), preexec_fn=hijo, close_fds=True,
                                          env=entorno_minimo_de_chrome())
        except OSError as exc:
            for fd in (a_r, a_w, b_r, b_w):
                os.close(fd)
            shutil.rmtree(self._perfil, ignore_errors=True)
            raise ErrorExterno(f"no se pudo lanzar Chrome: {exc}") from exc
        os.close(a_r)
        os.close(b_w)
        self._cdp = _Cdp(a_w, b_r)
        self.comando = comando

    # -- pasos ---------------------------------------------------------------

    def _espera_max(self) -> float:
        return float(self._p["modelado_captura_timeout_seg"])

    def _asegurar_pestana(self) -> str:
        if self._sesion_id is None:
            objetivo = self._cdp.llamar("Target.createTarget", {"url": "about:blank"}, espera=self._espera_max())
            adjunto = self._cdp.llamar("Target.attachToTarget", {"targetId": objetivo.get("targetId"), "flatten": True},
                                       espera=self._espera_max())
            sesion = adjunto.get("sessionId")
            if not isinstance(sesion, str):
                raise ErrorExterno("Chrome no abrió la pestaña")
            self._sesion_id = sesion
            self._cdp.llamar("Page.enable", sesion=sesion, espera=self._espera_max())
            self._cdp.llamar("Network.enable", sesion=sesion, espera=self._espera_max())
        return self._sesion_id

    def _instantanea(self) -> dict[str, Any]:
        sesion = self._asegurar_pestana()
        dom = self._cdp.llamar("Runtime.evaluate", {"expression": "document.documentElement.outerHTML",
                                                    "returnByValue": True}, sesion, self._espera_max())
        url = self._cdp.llamar("Runtime.evaluate", {"expression": "location.href", "returnByValue": True},
                               sesion, self._espera_max())
        valor_dom = (dom.get("result") or {}).get("value")
        valor_url = (url.get("result") or {}).get("value")
        if not isinstance(valor_dom, str) or not isinstance(valor_url, str):
            raise ErrorExterno("Chrome no entregó el DOM de la página")
        estados = estados_http_de(self._cdp.eventos)
        self._cdp.eventos.clear()
        return {"dom": valor_dom, "url_final": valor_url, "estados_http": estados}

    def navegar(self, url: str) -> dict[str, Any]:
        """Abre la búsqueda (UNA vez) y espera `modelado_captura_espera_ms` a que cargue. Solo direcciones canónicas."""
        exigir_url_canonica(url)
        sesion = self._asegurar_pestana()
        self._cdp.eventos.clear()
        r = self._cdp.llamar("Page.navigate", {"url": url}, sesion, self._espera_max())
        if r.get("errorText"):
            raise ErrorExterno(f"Chrome no pudo abrir la búsqueda: {str(r['errorText'])[:100]}")
        if not self._cdp.esperar_evento("Page.loadEventFired", self._espera_max()):
            raise ErrorExterno("la búsqueda no terminó de cargar en el tiempo máximo")
        self._cdp.bombear(self._p["modelado_captura_espera_ms"] / 1000)
        return self._instantanea()

    def desplazar(self) -> dict[str, Any]:
        """Baja hasta el final de la página (como una persona) y espera `ruta_d_espera_desplazamiento_ms`."""
        sesion = self._asegurar_pestana()
        self._cdp.eventos.clear()
        self._cdp.llamar("Runtime.evaluate", {"expression": "window.scrollTo(0, document.documentElement.scrollHeight)"},
                         sesion, self._espera_max())
        self._cdp.bombear(self._pr["ruta_d_espera_desplazamiento_ms"] / 1000)
        return self._instantanea()

    def cerrar(self) -> None:
        """Cierra Chrome y destruye el perfil (siempre, aunque falle algo antes). Seguro de llamar varias veces."""
        if self._cerrada:
            return
        self._cerrada = True
        try:
            try:
                self._cdp.enviar("Browser.close")
            except ErrorExterno:
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
        finally:
            for fd in (self._cdp.fd_envio, self._cdp.fd_lectura):
                try:
                    os.close(fd)
                except OSError:
                    pass
            shutil.rmtree(self._perfil, ignore_errors=True)


# ---------------------------------------------------------------------------
# Salida: crudo del contrato y archivo hermano
# ---------------------------------------------------------------------------

def fila_crudo(ad: Mapping[str, Any]) -> dict[str, Any]:
    """Fila de `ads` del contrato §2 con lo que dio la web; lo que no dio queda en `None` (nunca inventado)."""
    return {"id": ad["id"], "page_id": ad.get("page_id"), "page_name": ad.get("page_name") or "",
            "ad_creative_link_title": ad.get("titulo") or "", "ad_delivery_start_time": ad.get("inicio_epoch"),
            "currency": None, "ad_snapshot_url": f"https://www.facebook.com/ads/library/?id={ad['id']}"}


def construir_crudo(corrida_id: str, qid: str, consulta: Mapping[str, Any], capturado_en: str,
                    anuncios: Sequence[Mapping[str, Any]], total: int | None) -> dict[str, Any]:
    """Crudo propuesto (forma exacta del contrato §2, `ruta: "D"`). `estimated_total_count` es None si el total
    leído sería menor que lo recogido (dato inconsistente: no se afirma)."""
    filas = [fila_crudo(a) for a in anuncios]
    return {"schema_version": comun.VERSION_ESQUEMA, "corrida_id": corrida_id, "qid": qid, "consulta": dict(consulta),
            "capturado_en": capturado_en, "ruta": "D",
            "estimated_total_count": total if total is not None and total >= len(filas) else None, "ads": filas}


def faltantes(anuncios: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Cuántos anuncios no trajeron cada campo que el contrato necesita."""
    return {
        "page_id": sum(1 for a in anuncios if a.get("page_id") is None),
        "page_name": sum(1 for a in anuncios if not a.get("page_name")),
        "ad_creative_link_title": sum(1 for a in anuncios if not a.get("titulo")),
        "ad_delivery_start_time": sum(1 for a in anuncios if a.get("inicio_epoch") is None),
        "currency": len(anuncios),      # la web de la Biblioteca no la muestra
    }


def extra_de(ad: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": ad["id"], "texto": ad.get("texto", ""), "titulo_fuente": ad.get("titulo_fuente", "ninguna"),
            "plataformas": list(ad.get("plataformas", [])), "estado_anuncio": ad.get("estado_anuncio"),
            "variantes": ad.get("variantes"), "inicio_texto": ad.get("inicio_texto"), "inicio_precision": "dia",
            "page_vanity": ad.get("page_vanity"), "destinos": list(ad.get("destinos", []))}


def obstaculos_del_contrato(crudo: Mapping[str, Any]) -> list[str]:
    """Todo lo que impide hoy que este crudo sea oficial (`comun.validar_crudo` solo informa el primer fallo)."""
    ads = crudo["ads"]
    obstaculos = []
    if crudo["consulta"]["limit"] > comun.LIMITE_MAX_CONECTOR:
        obstaculos.append(f"consulta.limit={crudo['consulta']['limit']} supera {comun.LIMITE_MAX_CONECTOR} (P2)")
    if len(ads) > comun.LIMITE_MAX_CONECTOR:
        obstaculos.append(f"{len(ads)} anuncios superan {comun.LIMITE_MAX_CONECTOR} (P2)")
    for campo, pedido in (("currency", "P1"), ("page_id", "P3"), ("ad_delivery_start_time", "P3")):
        n = sum(1 for a in ads if a[campo] is None)
        if n:
            obstaculos.append(f"{n} anuncios sin {campo} (null) (%s)" % pedido)
    if crudo["consulta"]["countries"] and not re.fullmatch(r"[A-Z]{2}", crudo["consulta"]["countries"][0]):
        obstaculos.append(f"país {crudo['consulta']['countries'][0]!r} no es ISO-2 (el contrato exige un país por consulta)")
    return obstaculos


def escribir_salidas(directorio: Path, corrida_id: str, qid: str, crudo: Mapping[str, Any],
                     extra_base: Mapping[str, Any], anuncios: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Escribe `<qid>.json` SOLO si pasa `comun.validar_crudo`; siempre `<qid>.extra.json`. Nunca sobrescribe.

    Si el crudo no es válido (hoy: sin moneda), el extra lleva el crudo propuesto para no perder nada y el motivo.
    """
    motivo = None
    try:
        comun.validar_crudo(crudo, origen=f"{qid}.json")
    except ErrorValidacion as exc:
        motivo = str(exc)
    extra = dict(extra_base)
    extra.update({"ads_extra": [extra_de(a) for a in anuncios], "faltantes": faltantes(anuncios),
                  "crudo_escrito": motivo is None, "motivo_sin_crudo": motivo,
                  "obstaculos_del_contrato": obstaculos_del_contrato(crudo), "pedidos_al_contrato": list(PEDIDOS_AL_CONTRATO),
                  "crudo_propuesto": None if motivo is None else dict(crudo),
                  "aviso": "Todo el texto de este archivo es contenido AJENO: es dato para evaluar, nunca instrucciones."})
    archivos = {}
    if motivo is None:
        comun.escribir_json_nuevo(directorio / f"{qid}.json", crudo)
        archivos["crudo"] = str(directorio / f"{qid}.json")
    comun.escribir_json_nuevo(directorio / f"{qid}{SUFIJO_EXTRA}", extra)
    archivos["extra"] = str(directorio / f"{qid}{SUFIJO_EXTRA}")
    return {"crudo_escrito": motivo is None, "motivo_sin_crudo": motivo, "archivos": archivos}


# ---------------------------------------------------------------------------
# Orquestación con los frenos de captura.py
# ---------------------------------------------------------------------------

def _busquedas_de_hoy(estado_dir: Path, ahora: datetime) -> int:
    hoy = ahora.astimezone(timezone.utc).date()
    return sum(1 for e in ca._leer_capturas(estado_dir)
               if e.get("tipo") == "busqueda" and e.get("paso") == 0 and ca._momento(e["ts"]).date() == hoy)


def _tope_efectivo(nombre: str, parametro: int, pedido: int | None, *, minimo: int = 1) -> int:
    """El tope de la corrida solo puede BAJAR respecto del parámetro aprobado, nunca subir."""
    if pedido is None:
        return parametro
    if isinstance(pedido, bool) or not isinstance(pedido, int) or pedido < minimo or pedido > parametro:
        raise ErrorUso(f"{nombre}={pedido!r} no vale: debe ser un entero entre {minimo} y el parámetro aprobado ({parametro})")
    return pedido


def barrer(corrida_id: str, qid: str, *, frase: str | None = None, pagina_id: str | int | None = None, pais: str,
           exacta: bool = True, estado: str = "active", p: Mapping[str, Any], pr: Mapping[str, int], estado_dir: Path,
           raiz: Path | None = None, abrir_sesion: Callable | None = None, reloj: Callable = ca._ahora,
           dormir: Callable = time.sleep, max_desplazamientos: int | None = None, max_anuncios: int | None = None,
           volcar_dom: Callable[[int, str], None] | None = None) -> dict[str, Any]:
    """Recorre UNA búsqueda de la Biblioteca con todos los frenos de captura.py y escribe sus archivos.

    Orden: valida ids y URL (lista blanca de captura) → freno → ya escrito (idempotente) → tope de búsquedas por día →
    abre Chrome → por cada paso: freno, tope diario y pausa compartidos, paso, registro, análisis. Un bloqueo o una
    página rara escribe el freno y corta; no hay reintentos. Errores: ErrorValidacion (ids o URL), ErrorBloqueado
    (freno activo al empezar), ErrorLimite (tope diario o de búsquedas, o parámetros), ErrorExterno (falla de Chrome sin
    ningún anuncio recogido), ErrorUso (sin sesión disponible o tope pedido inválido).
    """
    exigir_estado_real(estado_dir, raiz, abrir_sesion)
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorValidacion(f"corrida_id inválido: {str(corrida_id)[:40]!r} (se espera AAAA-MM-DD-<letra>)")
    if not comun.qid_valido(qid):
        raise ErrorValidacion(f"qid inválido: {str(qid)[:40]!r} (se espera kebab-case ASCII)")
    _exigir_compartidos(p)
    url = url_busqueda(frase, pais, exacta=exacta, estado=estado, pagina_id=pagina_id)
    desplazamientos = _tope_efectivo("max_desplazamientos", pr["ruta_d_max_desplazamientos_por_busqueda"],
                                     max_desplazamientos, minimo=0)       # 0 = solo la carga inicial
    tope_anuncios = _tope_efectivo("max_anuncios", pr["ruta_d_max_anuncios_por_busqueda"], max_anuncios)
    ca.verificar_freno(estado_dir)
    directorio = comun.dir_crudo(corrida_id, raiz)
    for sufijo in (".json", SUFIJO_EXTRA):
        if (directorio / f"{qid}{sufijo}").exists():
            return {"estado": "ya_existe", "qid": qid, "corrida_id": corrida_id, "url": url, "motivo_parada": "ya_existe",
                    "pasos": 0, "anuncios": 0, "archivos": {}}
    if _busquedas_de_hoy(estado_dir, reloj()) >= pr["ruta_d_max_busquedas_por_dia"]:
        raise ErrorLimite(f"tope diario de búsquedas de la ruta D alcanzado ({pr['ruta_d_max_busquedas_por_dia']}); "
                          "se retoma mañana (UTC)")
    if abrir_sesion is None:
        raise ErrorUso("sin sesión de Chrome: la visita real exige pedirla expresamente (--visita-real)")

    marca = f"busqueda:{qid}"
    inicio = reloj()
    acumulado: dict[str, dict[str, Any]] = {}
    pasos: list[dict[str, Any]] = []
    total: int | None = None
    motivo_parada, detalle, estado_final = "tope_desplazamientos", None, "ok"
    visibles_antes, sin_nuevos, descartados = 0, 0, set()
    sesion = None
    try:
        for k in range(desplazamientos + 1):
            try:
                ca.verificar_freno(estado_dir)                    # ANTES DE CADA PASO, incluido cada desplazamiento
            except ErrorBloqueado as exc:
                if k == 0:
                    raise
                motivo_parada, detalle = "freno_externo", str(exc)
                break
            try:
                ca._respetar_cupo_y_ritmo(estado_dir, p, reloj, dormir)
            except ErrorLimite as exc:
                if k == 0:
                    raise
                motivo_parada, detalle = "tope_diario", str(exc)
                break
            if sesion is None:
                sesion = abrir_sesion(p, pr)
            try:
                paso = sesion.navegar(url) if k == 0 else sesion.desplazar()
            except ErrorExterno as exc:
                ca._anotar(estado_dir, {"ts": ca._iso(reloj()), "ad_id": marca, "estado": "error", "tipo": "busqueda", "paso": k})
                motivo_parada, detalle = "error_externo", str(exc)
                estado_final = "error"
                break
            if volcar_dom is not None:
                volcar_dom(k, paso["dom"])
            ahora = reloj()
            analisis = analizar_busqueda(paso["dom"], pr, estados_http=paso.get("estados_http", ()), url_final=paso.get("url_final"))
            visibles = len(analisis["anuncios"])
            if k > 0 and analisis["estado"] in ("ok", "sin_resultados") and visibles < visibles_antes:
                analisis = dict(analisis, estado="rara", motivos=["página rara: la lista se encogió al desplazarse"])
            ca._anotar(estado_dir, {"ts": ca._iso(ahora), "ad_id": marca, "estado": analisis["estado"], "tipo": "busqueda",
                                    "paso": k, "anuncios": visibles})
            nuevos = 0
            if analisis["estado"] in ("bloqueado", "rara"):
                detalle = "; ".join(analisis["motivos"])
                ca._poner_freno(estado_dir, ahora, marca, detalle[:300])
                motivo_parada, estado_final = analisis["estado"], analisis["estado"]
                pasos.append({"paso": k, "estado": analisis["estado"], "anuncios_visibles": 0, "nuevos": 0, "ts": ca._iso(ahora)})
                break
            if analisis["estado"] == "ok":
                ajenos = ESTADO_TARJETA_OPUESTO.get(estado)
                aceptados = [x for x in analisis["anuncios"] if x["estado_anuncio"] != ajenos]
                descartados.update(x["id"] for x in analisis["anuncios"] if x["estado_anuncio"] == ajenos)
                nuevos = fusionar_anuncios(acumulado, aceptados)
                visibles_antes = visibles
            if total is None:
                total = analisis["total"]
            pasos.append({"paso": k, "estado": analisis["estado"], "anuncios_visibles": visibles, "nuevos": nuevos, "ts": ca._iso(ahora)})
            if analisis["estado"] == "sin_resultados":
                motivo_parada = "sin_resultados"
                break
            if len(acumulado) >= tope_anuncios:
                for sobrante in list(acumulado)[tope_anuncios:]:
                    del acumulado[sobrante]
                motivo_parada = "tope_anuncios"
                break
            sin_nuevos = 0 if (k == 0 or nuevos) else sin_nuevos + 1
            if k > 0 and sin_nuevos >= pr["ruta_d_desplazamientos_sin_nuevos_max"]:
                motivo_parada = "fin_de_lista"
                break
    finally:
        if sesion is not None:
            sesion.cerrar()

    anuncios = list(acumulado.values())
    resumen: dict[str, Any] = {"estado": estado_final, "qid": qid, "corrida_id": corrida_id, "url": url,
                               "motivo_parada": motivo_parada, "detalle": detalle, "pasos": len(pasos),
                               "anuncios": len(anuncios), "estimated_total_count": total, "archivos": {},
                               "tarjetas_de_otro_estado_descartadas": len(descartados)}
    if not anuncios and motivo_parada in ("bloqueado", "rara", "error_externo", "freno_externo", "tope_diario"):
        error = directorio / f"{qid}{SUFIJO_ERROR}"
        if not error.exists():
            comun.escribir_json_nuevo(error, {"qid": qid, "error": f"{motivo_parada}: {detalle}"[:500], "ts": ca._iso(reloj())})
            resumen["archivos"]["error"] = str(error)
        if estado_final == "error":
            raise ErrorExterno(detalle or "falla de Chrome")
        return resumen
    consulta = {"search_terms": frase.strip() if pagina_id is None and frase else None, "countries": [pais],
                "ad_active_status": ESTADOS_DE_ESTADO[estado], "limit": tope_anuncios,
                "page_ids": [str(pagina_id)] if pagina_id is not None else None}
    crudo = construir_crudo(corrida_id, qid, consulta, comun.iso_z(inicio), anuncios, total)
    base = {"schema_version": comun.VERSION_ESQUEMA, "corrida_id": corrida_id, "qid": qid, "ruta": "D",
            "capturado_en": comun.iso_z(inicio), "url_busqueda": url, "estado_final": estado_final,
            "motivo_parada": motivo_parada, "detalle_parada": detalle, "pasos": pasos, "estimated_total_count": total,
            "tarjetas_de_otro_estado_descartadas": len(descartados)}
    resumen.update(escribir_salidas(directorio, corrida_id, qid, crudo, base, anuncios))
    return resumen


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scripts.modelado.barrido.ruta_d", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    for nombre in ("url", "buscar"):
        s = sub.add_parser(nombre)
        grupo = s.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--frase", default=None)
        grupo.add_argument("--pagina-id", default=None)
        s.add_argument("--pais", required=True, help="ISO-2 en mayúsculas (o ALL solo para búsquedas por página)")
        s.add_argument("--estado", default="active", choices=ca.ESTADOS_BUSQUEDA)
        s.add_argument("--aproximada", action="store_true", help="palabras en cualquier orden (por defecto, frase exacta)")
    s = sub.choices["buscar"]
    s.add_argument("--corrida", required=True)
    s.add_argument("--qid", required=True)
    s.add_argument("--max-desplazamientos", type=int, default=None, help="solo puede BAJAR el parámetro aprobado")
    s.add_argument("--max-anuncios", type=int, default=None, help="solo puede BAJAR el parámetro aprobado")
    s.add_argument("--visita-real", action="store_true", help="abre Chrome de verdad; sin esto solo muestra el plan")
    s.add_argument("--parametros", type=Path, default=None, help="parámetros modelado_* (se rechaza con FABRICA_ENTORNO=produccion; por defecto, la propuesta)")
    s.add_argument("--parametros-ruta-d", type=Path, default=None)
    s.add_argument("--estado-dir", type=Path, default=None, help="SOLO pruebas con sesión inyectada (se rechaza con --visita-real y con FABRICA_ENTORNO=produccion); "
                                                       "por defecto el empresa/captura/ real, compartido con captura.py")
    s.add_argument("--raiz", type=Path, default=None, help="raíz donde escribir empresa/barrido/ (se rechaza con FABRICA_ENTORNO=produccion)")
    s.add_argument("--guardar-dom", type=Path, default=None, help="guarda el DOM de cada paso en <base>.paso<N>.html")
    return parser


def main(argv: Sequence[str] | None = None, salida=None, **inyectados: Any) -> int:
    """Punto de entrada. `inyectados` (abrir_sesion, reloj, dormir) permite a las pruebas reemplazar Chrome y el reloj."""
    salida = salida or sys.stdout
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        url = url_busqueda(args.frase, args.pais, exacta=not args.aproximada, estado=args.estado, pagina_id=args.pagina_id)
        if args.orden == "url":
            print(url, file=salida)
            return 0
        if es_produccion():
            dados = [flag for atributo, flag in FLAGS_QUE_MUEVEN_LOS_FRENOS if getattr(args, atributo) is not None]
            if dados:
                raise ErrorUso(f"{', '.join(dados)} no existen con FABRICA_ENTORNO=produccion: el freno y el tope diario "
                               "se leen siempre de empresa/captura/ del repositorio real")
        visita_de_verdad = args.visita_real and "abrir_sesion" not in inyectados
        if visita_de_verdad and args.estado_dir is not None:
            raise ErrorUso("--estado-dir no vale con --visita-real: el freno y el tope diario se leen siempre de "
                           "empresa/captura/ del repositorio real (la ruta alterna es solo para pruebas)")
        p = pm.cargar_parametros(args.parametros or comun.RUTA_PARAMETROS_MODELADO)
        pr = cargar_parametros_ruta_d(args.parametros_ruta_d)
        estado_dir = args.estado_dir if args.estado_dir is not None else estado_dir_real()
        if not args.visita_real and "abrir_sesion" not in inyectados:
            plan = {"simulacro": True, "url": url, "nota": "no se abrió Chrome; agregue --visita-real para la visita real",
                    "max_desplazamientos": _tope_efectivo("max_desplazamientos", pr["ruta_d_max_desplazamientos_por_busqueda"],
                                                         args.max_desplazamientos, minimo=0),
                    "pausa_seg": p["modelado_captura_pausa_seg"], "tope_diario_compartido": p["modelado_captura_max_por_dia"]}
            print(json.dumps(plan, ensure_ascii=False, indent=2), file=salida)
            return 0
        inyectados.setdefault("abrir_sesion", SesionChrome)
        volcar = None
        if args.guardar_dom:
            def volcar(paso: int, dom: str) -> None:
                pm._escribir_nuevo(args.guardar_dom.with_name(f"{args.guardar_dom.name}.paso{paso}.html"), dom)
        resumen = barrer(args.corrida, args.qid, frase=args.frase, pagina_id=args.pagina_id, pais=args.pais,
                         exacta=not args.aproximada, estado=args.estado, p=p, pr=pr, estado_dir=estado_dir,
                         raiz=args.raiz, max_desplazamientos=args.max_desplazamientos, max_anuncios=args.max_anuncios,
                         volcar_dom=volcar, **inyectados)
        print(json.dumps(resumen, ensure_ascii=False, indent=2, sort_keys=True), file=salida)
        return {"bloqueado": 4, "rara": 4, "error": 6}.get(resumen.get("estado"), 0)
    except pm.ErrorFabrica as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        return exc.codigo_salida


if __name__ == "__main__":
    raise SystemExit(main())
