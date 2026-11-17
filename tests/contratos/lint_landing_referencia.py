"""Lint de publicación de REFERENCIA para la landing de una oferta (ola 0b-2, CT): la especificación ejecutable de B0-11.

NO es `landing.validar` (eso lo construye B4 en `landing/`): es el oráculo mínimo con el que se prueba (a) que `ofertas/_ejemplo/` pasa
limpio y (b) que cada mutación sembrada de `tests/fixtures/contratos/mutaciones_landing/` dispara la regla que declara. B4 puede reutilizar
los identificadores de regla o mapearlos a los suyos (columna «check» = departamentos/06-landing-checkout.md §6.1).

Reglas (identificador · check de D5 · qué comprueba):
  L1-LEGALES          C01  las siete páginas `sitio/legal/{vendedor,terminos,privacidad,reembolsos,cookies,aviso,entrega}.html` existen y no están vacías
  L1-RUTAS            C01  `rutas.json` trae las siete rutas legales y cada ruta estática tiene su archivo
  L1-ENLACE-INTERNO   C01  todo enlace, imagen u hoja de estilo del mismo sitio apunta a una ruta de `rutas.json` o a un archivo existente
  L1-ENLACE-EXTERNO   C01  ningún enlace, imagen u hoja de estilo apunta fuera del dominio de la marca (`rutas.json` no admite externos)
  L1-SCRIPT-EXTERNO   C01  ningún `<script src>` externo
  L1-SCRIPT-INLINE    C01  ningún `<script>` con código en línea (CSP)
  L1-SCRIPT-NO-PERMITIDO C01  el único script del HTML es `/js/consentimiento.js`
  L1-CONSENT-PIXEL    C10  `pixel.js`/`fbq`/`fbevents` no se cargan desde el HTML; solo `consentimiento.js` lo inyecta y tras el consentimiento de marketing
  L1-CONSENTIMIENTO-JS C10 el banner trae Aceptar, Rechazar y Personalizar, versión del texto, cookie propia y marketing apagado por defecto
  L1-TRACKING-PLATAFORMA C10 `tracking.json` declara `consent_gating.plataforma = "banner_propio_v1"`
  L1-PRECIO           C02  todo importe en euros del texto es el precio de lista o el del bump de `oferta.json`; `data-precio-minor` y `checkout.json` coinciden
  L1-MONEDA           C02  sin símbolos o códigos de otra moneda; `data-moneda` = moneda de la oferta
  L1-GARANTIA         C02  los «N días» de las frases de garantía/devolución son los de `oferta.garantia.dias` (y `checkout.garantia_dias`)
  L1-SALUD            M10  sin términos de salud/finanzas en `<title>`, `og:*`, rutas, dominio ni nombres/parámetros de eventos
  L1-HTML-LANG        C01  `<html lang>` = `oferta.locale` en todas las páginas
  L1-EJEMPLO-VISIBLE  C03  la palabra «ejemplo» no aparece en texto visible, `<title>`, `alt` ni meta
  L1-EJEMPLO-COMENTARIO C03 (solo `produccion=True`) ningún comentario HTML/JS con «[EJEMPLO]» llega a producción
  L1-CONTADORES       C03  sin contadores, cupos, cuentas regresivas ni «viendo ahora»
  L1-CASILLA-PREMARCADA C03 ninguna casilla `checked` en el HTML
  L1-EVENTO-NO-DECLARADO C10 `pixel.js` solo emite eventos de `tracking.json` (canal pixel o ambos); un evento con término sensible es L1-SALUD
  L1-FORMULARIO       B4   ningún `<form>`, `<textarea>`, `<select>` ni `<input>` (las casillas tienen su regla, L1-CASILLA-PREMARCADA) en el HTML estático: el checkout es de Stripe
  L1-PRUEBA-SOCIAL    B4   `<blockquote>`, `<q>` o `.testimonio` solo con `data-fuente` = `oferta.prueba[].fuente` de un testimonio con permiso
  L1-ALT              B4   todo `<img>` lleva `alt` no vacío
  L1-SCRIPT-INLINE    C01  también `javascript:` y manejadores `on*=` (los que contienen `fbq` son además L1-CONSENT-PIXEL)
  L1-ENLACE-EXTERNO   C01  también `<iframe>`, `<form action>`, `<source>`, `<video>`, `<object>`, `<embed>`, `srcset`, `<meta refresh>` y `url()`/`@import` del CSS
  L1-RUTAS            C01  también: todo HTML servido tiene su ruta en `rutas.json` (la lista cerrada)
  L1-PRECIO           C02  páginas de ángulo: `data-oferta-id/precio-minor/moneda/decimales/garantia-dias` obligatorios; el resto de páginas, sin `data-precio-minor`
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from scripts import validar_esquemas as V

LEGALES = ("vendedor", "terminos", "privacidad", "reembolsos", "cookies", "aviso", "entrega")
SCRIPT_PERMITIDO = "/js/consentimiento.js"
PIXEL = "/js/pixel.js"
RX_IMPORTE = re.compile(r"€\s*(\d{1,6}(?:[.,]\d{1,2})?)|(\d{1,6}(?:[.,]\d{1,2})?)\s*(?:€|\beuros?\b|\bEUR\b)", re.I)
RX_OTRA_MONEDA = re.compile(r"[$£¥]|\b(?:USD|GBP|JPY|MXN|ARS|COP)\b")
RX_DIAS = re.compile(r"(\d+)\s*días")
RX_BLOQUE_GARANTIA = re.compile(r"garant|devol|reembols", re.I)
RX_CONTADORES = re.compile(r"quedan\s+\d+|[úu]ltim[oa]s?\s+\d+|\d+\s+(?:personas|personas\s+est[aá]n)\s+(?:viendo|compr)|cuenta\s+regresiva|viendo\s+ahora|cupos?\b|plazas?\s+limitadas", re.I)
RX_URGENCIA_FALSA = re.compile(r"termina\s+(?:hoy|mañana|en\b)|sube\s+(?:hoy|mañana)|s[oó]lo\s+hoy|[úu]ltima\s+oportunidad|se\s+agota|hasta\s+agotar|por\s+tiempo\s+limitado|\bexpira\b", re.I)
RX_EJEMPLO = re.compile(r"\[EJEMPLO\]|\bEJEMPLO\b")             # el marcador, no la palabra corriente («por ejemplo»)
RX_EVENTO_FBQ = re.compile(r"fbq\(\s*['\"](?:track|trackCustom|trackSingle)['\"]\s*,\s*['\"](\w+)['\"]")
RX_COOKIE_ASIGNADA = re.compile(r"document\.cookie\s*=\s*")
RX_URL_CSS = re.compile(r"(?:url\(\s*|@import\s+)['\"]?((?:https?:)?//[^)'\"\s]+)", re.I)
ATRIBUTOS_URL = ("src", "href", "action", "data", "poster", "formaction", "background")
ETIQUETAS_FORMULARIO = ("form", "textarea", "select")


def _sin_comentarios(codigo: str) -> str:
    """JavaScript sin comentarios (``/* */`` y ``//``), respetando las cadenas: un comentario no puede «cumplir» una comprobación."""
    return re.sub(r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|/\*.*?\*/|//[^\n]*""", lambda m: m.group(1) or "", codigo, flags=re.S)
RX_PIXEL_EN_CODIGO = re.compile(r"fbq\s*\(|fbevents|connect\.facebook\.net|/js/pixel\.js", re.I)


@dataclass(frozen=True)
class Hallazgo:
    regla: str
    archivo: str
    detalle: str


class _Pagina(HTMLParser):
    """Recoge de un HTML lo que miran las reglas: lang, title, meta, enlaces, scripts, comentarios y texto visible."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: str | None = None
        self.title = ""
        self.meta: list[tuple[str, str]] = []
        self.enlaces: list[tuple[str, str]] = []       # (etiqueta, url)
        self.scripts: list[tuple[str | None, str]] = []  # (src, código en línea)
        self.comentarios: list[str] = []
        self.bloques: list[str] = []                   # texto visible por bloque (p, li, h*, summary…)
        self.alts: list[str] = []
        self.imgs_sin_alt = 0
        self.casillas_marcadas = 0
        self.javascript: list[str] = []                # URLs ``javascript:``
        self.manejadores: list[tuple[str, str, str]] = []  # (etiqueta, atributo on*, valor)
        self.formularios: list[str] = []               # etiquetas de formulario del HTML estático
        self.pruebas: list[dict[str, str]] = []        # blockquote / q / .testimonio (atributos)
        self.css: list[str] = []                       # <style> y style="" en línea
        self.body: dict[str, str] = {}
        self._en: list[str] = []
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        self._en.append(tag)
        for k, v in a.items():
            if k.startswith("on"):
                self.manejadores.append((tag, k, v))
            if v.strip().lower().startswith("javascript:"):
                self.javascript.append(v.strip())
            if k == "style":
                self.css.append(v)
        if tag not in ("a", "img", "link", "script"):          # estos cuatro tienen su propio tratamiento más abajo
            for k in ATRIBUTOS_URL:
                if a.get(k) and not a[k].strip().lower().startswith("javascript:"):
                    self.enlaces.append((tag, a[k]))
        for conjunto in (a.get("srcset"),):
            for trozo in (conjunto or "").split(","):
                if trozo.strip():
                    self.enlaces.append((tag + "[srcset]", trozo.split()[0]))
        if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            m = re.search(r"url\s*=\s*['\"]?([^'\"\s;]+)", a.get("content", ""), re.I)
            if m:
                self.enlaces.append(("meta-refresh", m.group(1)))
        if tag in ETIQUETAS_FORMULARIO or (tag == "input" and a.get("type") != "checkbox"):
            self.formularios.append(tag)
        if tag in ("blockquote", "q") or "testimonio" in a.get("class", "").split():
            self.pruebas.append(a)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "body":
            self.body = a
        elif tag == "meta" and ("content" in a):
            self.meta.append((a.get("property") or a.get("name") or "", a["content"]))
        elif tag == "a" and "href" in a:
            if not a["href"].strip().lower().startswith("javascript:"):
                self.enlaces.append(("a", a["href"]))
        elif tag == "img":
            if "src" in a:
                self.enlaces.append(("img", a["src"]))
            self.alts.append(a.get("alt", ""))
            if not a.get("alt", "").strip():
                self.imgs_sin_alt += 1
        elif tag == "link" and "href" in a:
            self.enlaces.append(("link", a["href"]))
        elif tag == "script":
            self.scripts.append((a.get("src"), ""))
        elif tag == "input" and a.get("type") == "checkbox" and "checked" in a:
            self.casillas_marcadas += 1
        if tag in ("p", "li", "h1", "h2", "h3", "summary", "button", "label", "a", "header", "footer"):
            self._buf.append("")

    def handle_endtag(self, tag: str) -> None:
        if self._en and self._en[-1] == tag:
            self._en.pop()
        if tag in ("p", "li", "h1", "h2", "h3", "summary", "button", "label", "a") and self._buf:
            texto = " ".join(self._buf.pop().split())
            if texto:
                self.bloques.append(texto)

    def handle_data(self, data: str) -> None:
        if not self._en:
            return
        if self._en[-1] == "title":
            self.title += data
        elif self._en[-1] == "script":
            src, codigo = self.scripts[-1]
            self.scripts[-1] = (src, codigo + data)
        elif self._en[-1] == "style":
            self.css.append(data)
        elif self._buf:
            self._buf[-1] += data

    def handle_comment(self, data: str) -> None:
        self.comentarios.append(data)

    def texto_visible(self) -> str:
        return " ".join(self.bloques)


def _interno(url: str, dominio: str) -> str | None:
    """Ruta interna (sin consulta ni ancla) de ``url`` si es del mismo sitio; ``None`` si es externa o no es navegación (mailto, tel, #)."""
    partes = urlsplit(url)
    if partes.scheme in ("mailto", "tel", "javascript", "data"):
        return None
    if partes.scheme in ("http", "https") or url.startswith("//"):
        return (partes.path or "/") if partes.netloc.lower() == dominio else None
    if not partes.path and partes.fragment:
        return None
    return partes.path or "/"


def _es_externo(url: str, dominio: str) -> bool:
    partes = urlsplit(url)
    return (partes.scheme in ("http", "https") or url.startswith("//")) and partes.netloc.lower() != dominio


def _archivo_de_ruta(sitio: Path, ruta: str) -> Path:
    ruta = ruta.rstrip("/") or "/"
    return sitio / "index.html" if ruta == "/" else sitio / (ruta.lstrip("/") + ".html")


def _ruta_de_archivo(sitio: Path, archivo: Path) -> str:
    """Ruta pública de un HTML servido (inversa de ``_archivo_de_ruta``): ``index.html`` -> ``/``, ``a/x.html`` -> ``/a/x``."""
    rel = archivo.relative_to(sitio).with_suffix("").as_posix()
    return "/" if rel == "index" else "/" + rel


def lint(dir_oferta: Path | str, *, produccion: bool = False) -> list[Hallazgo]:
    """Hallazgos del lint de publicación sobre ``<dir_oferta>/05-landing``; vacío = pasa. Solo lee."""
    d = Path(dir_oferta)
    land, sitio = d / "05-landing", d / "05-landing" / "sitio"
    oferta = V.cargar_json(d / "03-oferta" / "oferta.json")
    checkout = V.cargar_json(land / "checkout.json")
    tracking = V.cargar_json(land / "tracking.json")
    rutas = V.cargar_json(land / "rutas.json") if (land / "rutas.json").is_file() else {}
    dominio = oferta["marca"]["dominio"].lower()
    lista, bump = oferta["precio"]["lista"], (oferta.get("bump") or {}).get("precio")
    importes_ok = {lista["monto"]} | ({bump["monto"]} if bump else set())
    out: list[Hallazgo] = []

    def h(regla: str, archivo: str, detalle: str) -> None:
        out.append(Hallazgo(regla, archivo, detalle))

    # Legales y rutas.
    for n in LEGALES:
        p = sitio / "legal" / f"{n}.html"
        if not p.is_file() or not p.read_text(encoding="utf-8").strip():
            h("L1-LEGALES", f"05-landing/sitio/legal/{n}.html", "página legal ausente o vacía")
        if f"/legal/{n}" not in rutas:
            h("L1-RUTAS", "05-landing/rutas.json", f"falta la ruta /legal/{n}")
    for ruta, destino in rutas.items():
        if not str(destino).startswith("dinamica:") and not _archivo_de_ruta(sitio, ruta).is_file():
            h("L1-RUTAS", "05-landing/rutas.json", f"la ruta estática {ruta} no tiene archivo")
    for archivo in sorted(sitio.rglob("*.html")):          # rutas.json es la lista CERRADA: no se sirve nada que no figure en ella
        if _ruta_de_archivo(sitio, archivo) not in rutas:
            h("L1-RUTAS", archivo.relative_to(d).as_posix(), "página servida sin ruta en rutas.json")
    if tracking["consent_gating"]["plataforma"] != "banner_propio_v1":
        h("L1-TRACKING-PLATAFORMA", "05-landing/tracking.json", f"plataforma {tracking['consent_gating']['plataforma']!r} != 'banner_propio_v1'")
    if checkout["precio"] != lista or checkout["moneda"] != oferta["moneda"]:
        h("L1-PRECIO", "05-landing/checkout.json", "precio o moneda distintos de oferta.json")
    if checkout["garantia_dias"] != oferta["garantia"]["dias"]:
        h("L1-GARANTIA", "05-landing/checkout.json", "garantia_dias distinto de oferta.garantia.dias")

    # Páginas HTML.
    for ruta in sorted(sitio.rglob("*.html")):
        rel = ruta.relative_to(d).as_posix()
        pag = _Pagina()
        pag.feed(ruta.read_text(encoding="utf-8"))
        if pag.lang != oferta["locale"]:
            h("L1-HTML-LANG", rel, f"lang={pag.lang!r} != {oferta['locale']!r}")
        for url in pag.javascript:
            h("L1-SCRIPT-INLINE", rel, f"URL javascript: {url[:40]}")
        for etiqueta, k, v in pag.manejadores:
            h("L1-CONSENT-PIXEL" if RX_PIXEL_EN_CODIGO.search(v) else "L1-SCRIPT-INLINE", rel, f"manejador {k} en <{etiqueta}>")
        for url in (u for t in pag.css for u in RX_URL_CSS.findall(t)):
            if _es_externo(url, dominio):
                h("L1-ENLACE-EXTERNO", rel, f"css {url}")
        if pag.formularios:
            h("L1-FORMULARIO", rel, f"formulario en el HTML estático ({sorted(set(pag.formularios))}): el checkout es de Stripe")
        if pag.imgs_sin_alt:
            h("L1-ALT", rel, f"{pag.imgs_sin_alt} <img> sin alt o con alt vacío")
        for a in pag.pruebas:
            fuentes = {x["fuente"] for x in oferta.get("prueba", []) if x["tipo"] == "testimonio_con_permiso" and x.get("consentimiento_ref")}
            if a.get("data-fuente") not in fuentes:
                h("L1-PRUEBA-SOCIAL", rel, "testimonio o cita sin data-fuente que coincida con un testimonio con permiso de oferta.prueba")
        for etiqueta, url in pag.enlaces + [("og", c) for k, c in pag.meta if k == "og:image" or k == "og:url"]:
            if _es_externo(url, dominio):
                h("L1-ENLACE-EXTERNO", rel, f"{etiqueta} {url}")
                continue
            interno = _interno(url, dominio)
            if interno is None:
                continue
            existe = interno in rutas or any((base / interno.lstrip("/")).is_file() for base in (sitio, land))
            if not existe:
                h("L1-ENLACE-INTERNO", rel, f"{etiqueta} {url} no está en rutas.json ni existe como archivo")
        for src, codigo in pag.scripts:
            if src:
                if _es_externo(src, dominio):
                    h("L1-SCRIPT-EXTERNO", rel, src)
                elif (_interno(src, dominio) or src) == PIXEL:
                    h("L1-CONSENT-PIXEL", rel, "pixel.js enlazado desde el HTML: solo puede cargarlo consentimiento.js")
                elif (_interno(src, dominio) or src) != SCRIPT_PERMITIDO:
                    h("L1-SCRIPT-NO-PERMITIDO", rel, src)
            elif RX_PIXEL_EN_CODIGO.search(codigo):
                h("L1-CONSENT-PIXEL", rel, "código de píxel en línea, sin esperar al consentimiento")
            elif codigo.strip():
                h("L1-SCRIPT-INLINE", rel, "script en línea")
        texto = pag.texto_visible()
        visibles = [texto, pag.title, *pag.alts, *(c for k, c in pag.meta)]
        if any(RX_EJEMPLO.search(x) for x in visibles):
            h("L1-EJEMPLO-VISIBLE", rel, "«ejemplo» en texto visible, título, alt o meta")
        if produccion and any(RX_EJEMPLO.search(c) for c in pag.comentarios):
            h("L1-EJEMPLO-COMENTARIO", rel, "comentario [EJEMPLO] en una página que va a producción")
        if RX_CONTADORES.search(texto) or (oferta.get("urgencia") is None and RX_URGENCIA_FALSA.search(texto)):
            h("L1-CONTADORES", rel, "contador, cupo, escasez o urgencia en el texto (oferta.urgencia es null: toda urgencia es falsa)")
        if pag.casillas_marcadas:
            h("L1-CASILLA-PREMARCADA", rel, "casilla premarcada")
        for m in RX_IMPORTE.finditer(texto):
            monto = m.group(1) or m.group(2)
            minor = int(Decimal(monto.replace(",", ".")) * 100)
            if minor not in importes_ok:
                h("L1-PRECIO", rel, f"importe {monto} € no coincide con oferta.json {sorted(importes_ok)}")
        if RX_OTRA_MONEDA.search(texto):
            h("L1-MONEDA", rel, "símbolo o código de otra moneda en el texto")
        for bloque in pag.bloques:
            if RX_BLOQUE_GARANTIA.search(bloque):
                for dias in RX_DIAS.findall(bloque):
                    if int(dias) != oferta["garantia"]["dias"]:
                        h("L1-GARANTIA", rel, f"«{dias} días» en «{bloque[:60]}» != {oferta['garantia']['dias']}")
        destino = rutas.get(_ruta_de_archivo(sitio, ruta))
        es_angulo = destino is not None and ":" not in str(destino)
        esperados = {"data-oferta-id": oferta["oferta_id"], "data-precio-minor": str(lista["monto"]), "data-moneda": oferta["moneda"],
                     "data-garantia-dias": str(oferta["garantia"]["dias"]), "data-decimales": str(V.EXPONENTE_ISO4217[oferta["moneda"]])}
        if es_angulo:                       # el píxel lee estos datos del <body>: sin ellos enviaría ViewContent con valor 0
            for k, valor in esperados.items():
                if pag.body.get(k) != valor:
                    h({"data-moneda": "L1-MONEDA", "data-garantia-dias": "L1-GARANTIA"}.get(k, "L1-PRECIO"), rel, f"{k}={pag.body.get(k)!r}, se esperaba {valor!r}")
        elif "data-precio-minor" in pag.body:   # legales y /gracias no son página de producto: ni ViewContent ni precio
            h("L1-PRECIO", rel, "data-precio-minor solo va en las páginas de ángulo (el píxel enviaría ViewContent)")
        publicos = [pag.title, *(c for k, c in pag.meta if k.startswith("og:"))]
        sens = V._terminos_sensibles(" ".join(publicos))
        if sens:
            h("L1-SALUD", rel, f"términos sensibles en <title>/og:* ({sens})")

    # Tracking, rutas y dominio sin términos sensibles; eventos con nombres y parámetros neutros.
    eventos = " ".join([e["nombre"] + " " + " ".join(e["parametros_permitidos"]) for e in tracking["eventos"]])
    sens = V._terminos_sensibles(" ".join([dominio, tracking["dominio_verificado"], *rutas.keys(), eventos]))
    if sens:
        h("L1-SALUD", "05-landing/tracking.json", f"términos sensibles en dominio, rutas o eventos ({sens})")

    for css in sorted(sitio.rglob("*.css")):               # el CSS también carga terceros (@import, url()) sin consentimiento
        for url in RX_URL_CSS.findall(css.read_text(encoding="utf-8")):
            if _es_externo(url, dominio):
                h("L1-ENLACE-EXTERNO", css.relative_to(d).as_posix(), f"css {url}")

    # JavaScript: el banner y el único camino hacia el píxel.
    js = sitio / "js"
    cons = (js / "consentimiento.js").read_text(encoding="utf-8") if (js / "consentimiento.js").is_file() else ""
    for requerido in ("Aceptar", "Rechazar", "Personalizar", "version_texto", "fabrica_consent", ".checked = false"):
        if requerido not in cons:
            h("L1-CONSENTIMIENTO-JS", "05-landing/sitio/js/consentimiento.js", f"falta «{requerido}»")
    cons_codigo = _sin_comentarios(cons)             # un comentario no cumple una comprobación
    m = re.search(r"function cargarPixel\(\)\s*\{(.{0,220})", cons_codigo, re.S)
    if not m or not re.match(r"\s*if\s*\([^)]*!estado\.marketing", m.group(1)):
        h("L1-CONSENT-PIXEL", "05-landing/sitio/js/consentimiento.js", "cargarPixel() no depende de estado.marketing (primera sentencia)")
    if re.search(r"fbq\s*\(|connect\.facebook\.net", cons_codigo):
        h("L1-CONSENT-PIXEL", "05-landing/sitio/js/consentimiento.js", "consentimiento.js no puede contener el píxel")
    for escritura in RX_COOKIE_ASIGNADA.finditer(cons_codigo):    # solo la cookie propia (y borrar las de marketing); nunca _fbp/_fbc/…
        resto = cons_codigo[escritura.end(): escritura.end() + 160]
        propia = resto.startswith("CONFIG.cookie")
        borrado = resto.startswith("n + '=;") and "Max-Age=0" in resto
        if not (propia or borrado):
            h("L1-CONSENT-PIXEL", "05-landing/sitio/js/consentimiento.js", f"escribe una cookie distinta de la propia: {resto[:40]!r}")
    pix = (js / "pixel.js").read_text(encoding="utf-8") if (js / "pixel.js").is_file() else ""
    pix_codigo = _sin_comentarios(pix)
    if not re.search(r"\(function\s*\(\)\s*\{\s*'use strict';\s*if\s*\(\s*!window\.FabricaConsent\s*\|\|\s*window\.FabricaConsent\.marketing\(\)\s*!==\s*true\s*\)\s*\{\s*return;", pix_codigo):
        h("L1-CONSENT-PIXEL", "05-landing/sitio/js/pixel.js", "pixel.js no comprueba el consentimiento como primera sentencia ejecutable")
    if tracking["pixel_id"] not in pix_codigo:
        h("L1-CONSENT-PIXEL", "05-landing/sitio/js/pixel.js", "pixel_id distinto de tracking.json")
    emitidos = set(RX_EVENTO_FBQ.findall(pix_codigo))
    permitidos = {e["nombre"] for e in tracking["eventos"] if e["canal"] in ("pixel", "ambos")}
    if emitidos - permitidos:
        h("L1-EVENTO-NO-DECLARADO", "05-landing/sitio/js/pixel.js", f"eventos fuera de tracking.json: {sorted(emitidos - permitidos)}")
    if V._terminos_sensibles(" ".join(sorted(emitidos))):
        h("L1-SALUD", "05-landing/sitio/js/pixel.js", "término sensible en el nombre de un evento")
    for archivo in sorted(js.glob("*.js")) if js.is_dir() else []:
        codigo = archivo.read_text(encoding="utf-8")
        if archivo.name != "pixel.js" and archivo.name != "consentimiento.js" and RX_PIXEL_EN_CODIGO.search(codigo):
            h("L1-CONSENT-PIXEL", f"05-landing/sitio/js/{archivo.name}", "otro JavaScript referencia el píxel")
        if archivo.name != "consentimiento.js" and "document.cookie" in _sin_comentarios(codigo):
            h("L1-CONSENT-PIXEL", f"05-landing/sitio/js/{archivo.name}", "solo consentimiento.js puede tocar document.cookie")
        if produccion and "[EJEMPLO]" in codigo:
            h("L1-EJEMPLO-COMENTARIO", f"05-landing/sitio/js/{archivo.name}", "comentario [EJEMPLO] en JavaScript de producción")
    return out


def reglas(hallazgos: list[Hallazgo]) -> set[str]:
    return {x.regla for x in hallazgos}


if __name__ == "__main__":  # pragma: no cover
    import sys

    raiz = Path(sys.argv[1]) if len(sys.argv) > 1 else V.raiz_datos() / "ofertas" / "_ejemplo"
    res = lint(raiz, produccion="--produccion" in sys.argv)
    print(json.dumps([x.__dict__ for x in res], ensure_ascii=False, indent=2))
    sys.exit(1 if res else 0)
