"""``landing.validar``: lint de publicación (L1) de ``05-landing/sitio/``.

Implementa las mismas reglas que el oráculo de B0-11 (``tests/contratos/lint_landing_referencia.py``,
CT) con los mismos identificadores ``L1-*`` (docs/06 §6.2, B0-11): precio/moneda/garantía iguales
en ``oferta.json``, ``checkout.json`` y el HTML; enlaces y las siete legales con archivo; sin
``<script>`` externo o en línea salvo ``/js/consentimiento.js``; sin datos de salud; consentimiento
antes del píxel; sin casillas premarcadas.

CLI::

    python -m landing.validar --oferta OF-202611-01 --raiz /tmp/prueba [--produccion] --json

Reglas de los componentes del plano «referente» (todas BLOQUEANTES, como el resto de L1):

* ``L1-DEMO`` — cualquier marca de demostración (``data-demo``, ``data-vista-previa``, clases ``demo-``/``cinta-demo``/``vp-*``, la cinta «DEMO», «VISTA PREVIA»,
  «[vista previa…]»). Es la salida de ``landing.generar --vista-previa``: sirve para ver el diseño final, NUNCA para publicar. ``landing.desplegar`` la reutiliza
  para rechazar producción.
* ``L1-COMPARACION`` — la comparación con el mercado solo exenta de ``L1-PRECIO`` las cifras ``data-comparacion-cifra`` que estén DENTRO de un bloque
  ``data-comparacion-mercado`` y traigan ``data-fuente`` no vacío (fuente obligatoria por cifra); cualquier otro importe ajeno sigue bloqueado.
* ``L1-BARRA-LANZAMIENTO`` — la barra «precio de lanzamiento hasta {fecha}» exige ``checkout.precio_programado`` con la misma fecha, que no haya pasado
  (``hoy``) y un precio de después mayor que el actual y en la misma moneda.
* ``L1-PRUEBA-SOCIAL`` — un contador o valoración (``data-prueba-social``) solo con ``05-landing/prueba_social_real.json`` que lo respalde (total ≥ 1, mismo valor).
* ``L1-RESENA`` — una reseña (``blockquote.testimonio``) exige ``data-fuente`` = compra con testimonio con permiso en ``oferta.prueba``.
* ``L1-IMAGEN-ROTULO`` — cada ``<img>`` ``data-ilustrativa`` lleva su rótulo «ilustración orientativa» y cada ``data-ia`` su rótulo de IA (``[data-rotulo]`` propio con
  ``data-para`` = su ranura, o un pie de grupo ``data-para="grupo"`` en la misma sección); además, toda ranura aprobada de ``assets.json`` con ``ilustrativa`` o
  ``etiqueta_ia_visible`` debe salir con esas marcas (no se quitan a mano).
* ``L1-IMG-ATRIBUTOS`` — rendimiento: toda ``<img>`` con ``width``/``height`` y ``alt``; el héroe con ``fetchpriority="high"`` y sin ``loading="lazy"``; las demás con
  ``loading="lazy"`` y nunca ``fetchpriority="high"``.
* ``L1-PESO`` — cada imagen publicada cabe en el ``peso_max_kb`` de su ranura; el HTML de cada página ≤ ``PESO_HTML_MAX_KB``, el CSS ≤ ``PESO_CSS_MAX_KB`` y las imágenes de
  una página ≤ ``landing.peso_landing_max_kb`` (``empresa/parametros.yaml``; por defecto ``PESO_IMAGENES_MAX_KB``).
* ``L1-COMPARACION-FUENTE`` — con ``05-landing/fuentes_mercado.json`` cada cifra de comparación se contrasta con su fuente declarada (nombre + fecha + cifra, y el archivo
  capturado con su ``sha256``); con ``--produccion`` el archivo es obligatorio y la lectura no puede tener más de ``VIGENCIA_MERCADO_DIAS`` días.

Salida: 0 sin hallazgos · 3 con hallazgos (lista en ``datos.hallazgos``) · 2 uso.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlsplit

from scripts import validar_esquemas as V

from engine import comun
from engine.errores import ErrorValidacion
from landing import comun as lcomun
from landing import contenido
from landing import plantillas as P

__all__ = ["Hallazgo", "validar_sitio", "reglas", "main", "marcas_de_demo"]

# Importe = número + símbolo o código ISO 4217 REAL (no «12 PDF» ni «3 XLS»): los códigos salen de la tabla de monedas operables.
_CODIGOS_MONEDA = "|".join(sorted(V.EXPONENTE_ISO4217))
RX_IMPORTE = re.compile(rf"(\d{{1,3}}(?:[.,]\d{{1,2}})?)\s*([€$£]|zł(?!\w)|\b(?:{_CODIGOS_MONEDA})\b)")
RX_DIAS = re.compile(r"(\d+)\s*d[ií]as")
RX_BLOQUE_GARANTIA = re.compile(r"garant|devol|reembols", re.I)
RX_CONTADORES = re.compile(
    r"quedan\s+\d+|[úu]ltim[oa]s?\s+\d+|\d+\s+personas?\s+(?:viendo|compr)|cuenta\s+regresiva|"
    r"viendo\s+ahora|cupos?\b|plazas?\s+limitadas", re.I,
)
# Solo el sello EJEMPLO (mayúsculas) o el marcador [EJEMPLO]: la palabra corriente («por ejemplo») es copy legítimo.
RX_EJEMPLO = re.compile(r"\[EJEMPLO\]|\bEJEMPLO\b")
RX_PIXEL_EN_CODIGO = re.compile(r"fbq\s*\(|fbevents|connect\.facebook\.net|/js/pixel\.js", re.I)
# Arranque de pago (docs/_historial/decision-arranque-de-pago.md): solo /comprar puede llevar UN <form method="post" action="/api/sesion">.
CONTROLES = ("input", "textarea", "select", "option", "optgroup", "datalist", "button")
ATRIBUTOS_DE_DESVIO = ("formaction", "formtarget", "formmethod", "formenctype", "target")
ENCTYPE_PREDETERMINADO = "application/x-www-form-urlencoded"
ATR_FORM = {"method", "action", "enctype", "class", "id"}
ATR_OCULTO = {"type", "name", "value"}
ATR_CASILLA = {"type", "name", "id", "required", "class", "data-texto-version"}
ATR_BOTON = {"type", "class", "id"}
_SIMBOLO_MONEDA = {"€": "EUR", "$": "USD", "£": "GBP", "zł": "PLN"}
PESO_HTML_MAX_KB = 250         # una página de venta (HTML) no pasa de 250 KB
PESO_CSS_MAX_KB = 100          # ni la hoja de estilos de 100 KB
PESO_IMAGENES_MAX_KB = 2500    # imágenes locales de una página (suma), salvo `landing.peso_landing_max_kb`
ELEMENTOS_VACIOS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
# Marcas de DEMOSTRACIÓN de la vista previa (landing.generar --vista-previa). Se buscan en el HTML crudo (atributos, clases y texto); las mayúsculas de «DEMO» y
# «VISTA PREVIA» evitan falsos positivos con la palabra corriente «demo» o «vista previa» en un texto normal.
RX_DEMO_CS = re.compile(r">\s*DEMO\s*<|VISTA PREVIA")


def marcas_de_demo(html: str) -> list[str]:
    """Marcas de demostración de un HTML (lista corta y legible; vacía si no hay): atributos ``data-demo``/``data-vista-previa``, clases ``demo-``/``vp-``,
    la cinta «DEMO», «VISTA PREVIA» o «[vista previa…]». La usan ``L1-DEMO`` y ``landing.desplegar`` (rechazo en producción)."""
    marcas: list[str] = []
    if re.search(r"data-demo\b", html):
        marcas.append("atributo data-demo")
    if re.search(r"data-vista-previa\b", html):
        marcas.append("atributo data-vista-previa")
    if re.search(r"class=\"[^\"]*\b(?:demo-|cinta-demo|vp-)", html):
        marcas.append("clase demo-/cinta-demo/vp-")
    if RX_DEMO_CS.search(html):
        marcas.append("texto «DEMO» o «VISTA PREVIA»")
    if re.search(r"\[vista previa", html, re.I):
        marcas.append("marcador «[vista previa…]»")
    return marcas


@dataclass(frozen=True)
class Hallazgo:
    regla: str
    archivo: str
    detalle: str

    def __str__(self) -> str:  # pragma: no cover - solo para mensajes legibles
        return f"{self.regla} [{self.archivo}] {self.detalle}"


class _Pagina(HTMLParser):
    """Recoge de un HTML lo que miran las reglas: lang, title, meta, enlaces, scripts, comentarios y texto visible."""

    _BLOQUE = ("p", "li", "h1", "h2", "h3", "summary", "button", "label", "a")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: str | None = None
        self.title = ""
        self.meta: list[tuple[str, str]] = []
        self.enlaces: list[tuple[str, str]] = []
        self.scripts: list[tuple[str | None, str]] = []
        self.comentarios: list[str] = []
        self.bloques: list[str] = []
        self.alts: list[str] = []
        self.casillas_marcadas = 0
        self.body: dict[str, str] = {}
        self.formas: list[dict[str, str]] = []                 # atributos de cada <form>
        self.controles: list[tuple[str, dict[str, str], int | None]] = []   # (etiqueta, atributos, índice del <form> que lo contiene o None)
        self.peligrosos: list[tuple[str, str, str]] = []      # (etiqueta, atributo, valor): formaction, formtarget, formmethod, formenctype, target
        self.cifras_mercado: list[dict] = []                   # cifras data-comparacion-cifra: {fuente, texto, en_bloque}
        self.barra_lanzamiento: str | None = None              # data-barra-lanzamiento (fecha AAAA-MM-DD)
        self.prueba_social: list[dict[str, str]] = []          # elementos data-prueba-social: {tipo, valor, n}
        self.resenas: list[str] = []                           # data-fuente de cada blockquote.testimonio
        self.imgs: list[dict] = []                             # cada <img>: src, width, height, alt, loading, fetchpriority, clase, slot, ilustrativa, ia, seccion
        self.rotulos: list[dict] = []                          # cada [data-rotulo]: tipos, para, texto, seccion
        self._n_seccion = 0
        self._rot: tuple[int, dict] | None = None              # (profundidad, entrada) del rótulo abierto
        self._demo: int | None = None                          # profundidad del elemento data-demo abierto (sus reseñas no se cuentan: ya las bloquea L1-DEMO)
        self._bloque_comparacion: int | None = None            # profundidad (len(_en)) del contenedor data-comparacion-mercado
        self._cifra: tuple[int, dict] | None = None            # (profundidad, entrada) de la cifra abierta
        self._form: int | None = None
        self._en: list[str] = []
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag not in ELEMENTOS_VACIOS:                        # los vacíos (img, meta, link…) no tienen cierre: no se apilan
            self._en.append(tag)
        if tag == "section":
            self._n_seccion += 1
        if tag == "img":
            self.imgs.append({"src": a.get("src", ""), "width": a.get("width", ""), "height": a.get("height", ""), "alt": a.get("alt") if "alt" in a else None,
                              "loading": a.get("loading", ""), "fetchpriority": a.get("fetchpriority", ""), "clase": a.get("class", ""), "slot": a.get("data-slot", ""),
                              "ilustrativa": "data-ilustrativa" in a, "ia": "data-ia" in a, "seccion": self._n_seccion})
        if "data-rotulo" in a:
            entrada = {"tipos": set(a["data-rotulo"].split()), "para": a.get("data-para", ""), "texto": "", "seccion": self._n_seccion}
            self.rotulos.append(entrada)
            if self._rot is None and tag not in ELEMENTOS_VACIOS:
                self._rot = (len(self._en), entrada)
        if "data-comparacion-mercado" in a and self._bloque_comparacion is None:
            self._bloque_comparacion = len(self._en)
        if "data-comparacion-cifra" in a and self._cifra is None:
            entrada = {"fuente": a.get("data-fuente", ""), "texto": "", "en_bloque": self._bloque_comparacion is not None, "fecha": a.get("data-fecha", ""),
                       "desde": a.get("data-desde", ""), "hasta": a.get("data-hasta", "")}
            self.cifras_mercado.append(entrada)
            self._cifra = (len(self._en), entrada)
        if "data-barra-lanzamiento" in a:
            self.barra_lanzamiento = a["data-barra-lanzamiento"]
        if "data-prueba-social" in a:
            self.prueba_social.append({"tipo": a["data-prueba-social"], "valor": a.get("data-valor", ""), "n": a.get("data-n", "")})
        if "data-demo" in a and self._demo is None:
            self._demo = len(self._en)
        if tag == "blockquote" and "testimonio" in a.get("class", "").split() and self._demo is None:
            self.resenas.append(a.get("data-fuente", ""))
        for k in ATRIBUTOS_DE_DESVIO:
            if k in a:
                self.peligrosos.append((tag, k, a[k]))
        if tag == "form":
            self.formas.append(a)
            self._form = len(self.formas) - 1
        elif tag in CONTROLES:
            self.controles.append((tag, a, self._form))
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "body":
            self.body = a
        elif tag == "meta" and "content" in a:
            self.meta.append((a.get("property") or a.get("name") or "", a["content"]))
        elif tag == "a" and "href" in a:
            self.enlaces.append(("a", a["href"]))
        elif tag == "img":
            if "src" in a:
                self.enlaces.append(("img", a["src"]))
            self.alts.append(a.get("alt", ""))
        elif tag == "link" and "href" in a:
            self.enlaces.append(("link", a["href"]))
        elif tag == "script":
            self.scripts.append((a.get("src"), ""))
        elif tag == "input" and a.get("type") == "checkbox" and "checked" in a:
            self.casillas_marcadas += 1
        if tag in self._BLOQUE:
            self._buf.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._form = None
        if self._en and self._en[-1] == tag:
            self._en.pop()
            if self._cifra is not None and len(self._en) < self._cifra[0]:
                self._cifra = None
            if self._bloque_comparacion is not None and len(self._en) < self._bloque_comparacion:
                self._bloque_comparacion = None
            if self._demo is not None and len(self._en) < self._demo:
                self._demo = None
            if self._rot is not None and len(self._en) < self._rot[0]:
                self._rot = None
        if tag in self._BLOQUE and self._buf:
            texto = " ".join(self._buf.pop().split())
            if texto:
                self.bloques.append(texto)

    def handle_data(self, data: str) -> None:
        if not self._en:
            return
        if self._rot is not None:
            self._rot[1]["texto"] += data
        if self._cifra is not None:                       # el texto de una cifra de mercado va aparte: no se mezcla con el texto visible ni con L1-PRECIO
            self._cifra[1]["texto"] += data
            return
        if self._en[-1] == "title":
            self.title += data
        elif self._en[-1] == "script":
            src, codigo = self.scripts[-1]
            self.scripts[-1] = (src, codigo + data)
        elif self._en[-1] != "style" and self._buf:
            self._buf[-1] += data

    def handle_comment(self, data: str) -> None:
        self.comentarios.append(data)

    def texto_visible(self) -> str:
        return " ".join(self.bloques)


def _interno(url: str, dominio: str) -> str | None:
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


def _formularios(pag: "_Pagina", ruta_publica: str, oferta: dict, checkout: dict, rutas: dict[str, str], h: Callable[[str], None]) -> None:
    """``L1-FORMULARIO``: admite EXACTAMENTE el formulario de pago de ``/comprar`` y rechaza todo lo demás (``h`` recibe el detalle).

    En ``/comprar``: UN ``<form method="post" action="/api/sesion">`` con ``oferta_id`` y ``locale`` ocultos (iguales a ``oferta.json``), la casilla
    ``bump`` solo con ``bump_modo = oferta_previa``, la casilla ``renuncia_desistimiento`` (``required``) solo si ``checkout.compra.renuncia.requerido``
    (o, sin él, el criterio por locale) y UN ``<button type="submit">``; casillas nunca premarcadas. Prohibido en cualquier página: otro tipo de
    ``<input>``, ``<textarea>``, ``<select>``, ``formaction``, ``target``, ``enctype`` distinto del predeterminado, otra ``action`` y cualquier formulario
    o campo fuera de ``/comprar``.
    """
    for etiqueta, atributo, valor in pag.peligrosos:
        h(f"<{etiqueta} {atributo}=\"{valor[:40]}\"> no está permitido (el formulario de pago no desvía ni abre ventanas)")
    en_comprar = ruta_publica == lcomun.RUTA_COMPRAR
    if not en_comprar:
        if pag.formas:
            h("formulario fuera de /comprar")
        for etiqueta, a, _formulario in pag.controles:
            if etiqueta == "button" or (etiqueta == "input" and a.get("type", "").lower() == "checkbox"):
                continue                                  # los botones y las casillas sueltas no envían nada (las premarcadas las caza L1-CASILLA-PREMARCADA)
            h(f"<{etiqueta}{' type=' + a['type'] if 'type' in a else ''}> fuera de /comprar: no se admiten campos de formulario")
        return
    if len(pag.formas) != 1:
        h(f"/comprar debe tener exactamente un formulario y tiene {len(pag.formas)}")
        return
    f = pag.formas[0]
    for k in sorted(set(f) - ATR_FORM):
        h(f"atributo {k} no permitido en el formulario")
    if f.get("method", "").lower() != "post":
        h(f"method={f.get('method', '')!r}: el formulario es method=\"post\"")
    if f.get("action") != lcomun.RUTA_SESION:
        h(f"action={f.get('action', '')!r}: la única action permitida es {lcomun.RUTA_SESION}")
    if "enctype" in f and f["enctype"].lower() != ENCTYPE_PREDETERMINADO:
        h(f"enctype={f['enctype']!r} distinto del predeterminado")
    if lcomun.RUTA_SESION not in rutas or not str(rutas[lcomun.RUTA_SESION]).startswith("dinamica:"):
        h("rutas.json no declara /api/sesion como dinamica:crear-sesion")
    esperado = {"oferta_id": oferta["oferta_id"], "locale": oferta["locale"]}
    renuncia_req, version, _ = lcomun.renuncia(oferta, checkout)
    bump_req = lcomun.modo_bump(checkout) == "oferta_previa"
    vistos: dict[str, int] = {}
    botones_envio = 0
    for etiqueta, a, formulario in pag.controles:
        if formulario is None:
            if not (etiqueta == "button" and a.get("type") == "button"):
                h(f"<{etiqueta}> fuera del formulario")
            continue
        if etiqueta == "button":
            if set(a) - ATR_BOTON:
                h(f"atributos no permitidos en el botón: {sorted(set(a) - ATR_BOTON)}")
            if a.get("type") == "submit":
                botones_envio += 1
            else:
                h(f"<button type={a.get('type', '(sin type)')!r}> dentro del formulario: solo un botón type=\"submit\"")
            continue
        if etiqueta != "input":
            h(f"<{etiqueta}> no está permitido en el formulario de pago (sin datos personales: el comprador los da en Stripe)")
            continue
        tipo, nombre = a.get("type", "").lower(), a.get("name", "")
        vistos[nombre] = vistos.get(nombre, 0) + 1
        if tipo == "hidden":
            if nombre not in esperado:
                h(f"campo oculto no permitido: {nombre!r}")
            elif a.get("value") != esperado[nombre]:
                h(f"{nombre}={a.get('value')!r} distinto de oferta.json ({esperado[nombre]!r})")
            if set(a) - ATR_OCULTO:
                h(f"atributos no permitidos en el campo oculto {nombre}: {sorted(set(a) - ATR_OCULTO)}")
        elif tipo == "checkbox":
            if nombre not in ("bump", "renuncia_desistimiento"):
                h(f"casilla no permitida: {nombre!r}")
                continue
            if "checked" in a:
                h(f"la casilla {nombre} está premarcada")
            if set(a) - ATR_CASILLA:
                h(f"atributos no permitidos en la casilla {nombre}: {sorted(set(a) - ATR_CASILLA)}")
            if nombre == "bump":
                if not bump_req:
                    h("casilla bump presente sin bump_modo = oferta_previa")
                if "required" in a:
                    h("la casilla bump no puede ser obligatoria")
            else:
                if not renuncia_req:
                    h("casilla renuncia_desistimiento presente sin que la compra la exija")
                if "required" not in a:
                    h("la casilla renuncia_desistimiento debe ser required")
                if version is not None and a.get("data-texto-version") != version:
                    h(f"data-texto-version={a.get('data-texto-version')!r} distinto de checkout.compra.renuncia.texto_version ({version!r})")
        else:
            h(f"campo de tipo {tipo or '(sin type = text)'!r} no permitido: el formulario solo admite campos ocultos y casillas")
    for nombre in esperado:
        if vistos.get(nombre, 0) != 1:
            h(f"el campo oculto {nombre} debe aparecer exactamente una vez ({vistos.get(nombre, 0)})")
    if bump_req and vistos.get("bump", 0) != 1:
        h("falta la casilla bump (bump_modo = oferta_previa)")
    if renuncia_req and vistos.get("renuncia_desistimiento", 0) != 1:
        h("falta la casilla renuncia_desistimiento (la compra la exige: UE/UK)")
    if vistos.get("bump", 0) > 1 or vistos.get("renuncia_desistimiento", 0) > 1:
        h("casilla repetida")
    if botones_envio != 1:
        h(f"el formulario debe tener exactamente un botón type=\"submit\" y tiene {botones_envio}")


def _directivas(csp: str) -> dict[str, list[list[str]]]:
    salida: dict[str, list[list[str]]] = {}
    for trozo in csp.split(";"):
        partes = trozo.split()
        if partes:
            salida.setdefault(partes[0].lower(), []).append(partes[1:])
    return salida


def _bloques_headers(texto: str) -> dict[str, list[tuple[bool, str, str]]]:
    """``_headers`` de Cloudflare Pages -> ``{ruta: [(desvincula, cabecera, valor)]}`` (``! Cabecera`` quita la heredada)."""
    bloques: dict[str, list[tuple[bool, str, str]]] = {}
    actual: str | None = None
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        if not linea[0].isspace():
            actual = linea.strip()
            bloques.setdefault(actual, [])
        elif actual is not None:
            cuerpo = linea.strip()
            if cuerpo.startswith("!"):
                bloques[actual].append((True, cuerpo[1:].strip(), ""))
            elif ":" in cuerpo:
                nombre, valor = cuerpo.split(":", 1)
                bloques[actual].append((False, nombre.strip(), valor.strip()))
    return bloques


def _csp(sitio: Path, checkout: dict, h: Callable[[str], None]) -> None:
    """``L1-CSP``: ``sitio/_headers`` con la CSP CANÓNICA (``landing.comun.CSP_CANONICA``, decisión de S-A): cada directiva con EXACTAMENTE sus orígenes (sin
    importar el orden), sin directivas de más ni de menos, sin ``'unsafe-inline'`` y con ``form-action 'self' https://checkout.stripe.com``.

    Obligatoria cuando el sitio trae ``comprar.html`` (el formulario de pago); sin ``/comprar`` y sin ``_headers`` no se exige (sitios anteriores). Con
    ``checkout.turnstile.habilitado`` la ruta ``/comprar`` lleva su CSP aparte (la canónica + Turnstile en ``script-src`` y ``frame-src``); sin él, Turnstile no aparece.
    """
    ruta = sitio / "_headers"
    if not ruta.is_file():
        if (sitio / "comprar.html").is_file():
            h("falta _headers: el sitio con /comprar necesita su Content-Security-Policy canónica (form-action 'self' https://checkout.stripe.com)")
        return
    texto = ruta.read_text(encoding="utf-8")
    bloques = _bloques_headers(texto)
    ts = lcomun.turnstile(checkout) is not None

    def revisar(donde: str, valor: str, *, turnstile: bool) -> None:
        d = _directivas(valor)
        esperado = lcomun.csp_directivas(turnstile=turnstile)
        for nombre, tokens in esperado.items():
            if nombre not in d:
                h(f"{donde}: falta la directiva {nombre} ({' '.join(tokens)})")
            elif len(d[nombre]) != 1:
                h(f"{donde}: la directiva {nombre} está repetida")
            elif sorted(d[nombre][0]) != sorted(tokens):
                sobran = sorted(set(d[nombre][0]) - set(tokens))
                faltan = sorted(set(tokens) - set(d[nombre][0]))
                h(f"{donde}: {nombre} debe ser exactamente «{' '.join(tokens)}» (sobran {sobran}, faltan {faltan})")
        for nombre in sorted(set(d) - set(esperado)):
            h(f"{donde}: directiva no admitida {nombre}")

    general = [x for x in bloques.get("/*", []) if not x[0] and x[1].lower() == "content-security-policy"]
    if len(general) != 1:
        h("_headers: el bloque /* debe traer exactamente un Content-Security-Policy")
    else:
        revisar("/*", general[0][2], turnstile=False)
    for donde, lineas in bloques.items():
        if donde == "/*":
            continue
        if donde == lcomun.RUTA_COMPRAR and ts:
            propias = [x for x in lineas if not x[0] and x[1].lower() == "content-security-policy"]
            if not any(x[0] and x[1].lower() == "content-security-policy" for x in lineas) or len(propias) != 1:
                h("_headers: /comprar con Turnstile debe quitar (!) la CSP general y traer la suya")
            else:
                revisar(lcomun.RUTA_COMPRAR, propias[0][2], turnstile=True)
        elif any(x[1].lower() == "content-security-policy" for x in lineas):
            h(f"_headers: {donde} no puede traer su propia Content-Security-Policy")
    if not ts and lcomun.ORIGEN_TURNSTILE in texto:
        h("_headers menciona Turnstile y checkout.json no lo habilita")
    if ts and lcomun.RUTA_COMPRAR not in bloques:
        h("_headers: checkout.turnstile.habilitado exige el bloque /comprar")


def _comparacion_con_fuentes(pag: "_Pagina", rel: str, doc: dict | None, land: Path, moneda: str, produccion: bool, hoy: date,
                             h: Callable[[str, str, str], None]) -> None:
    """``L1-COMPARACION-FUENTE``: contrasta cada cifra de comparación con ``fuentes_mercado.json`` (nombre + fecha + cifra + archivo capturado) y, en producción, exige el
    archivo y una lectura de no más de ``VIGENCIA_MERCADO_DIAS`` días."""
    for c in pag.cifras_mercado:
        if not c["en_bloque"] or not c["fuente"].strip():
            continue                                                    # eso ya lo dice L1-COMPARACION
        try:
            desde = int(c["desde"])
            hasta = int(c["hasta"]) if c["hasta"] else None
        except ValueError:
            h("L1-COMPARACION-FUENTE", rel, f"cifra {c['texto'].strip()!r} sin data-desde/data-hasta legibles: no se puede contrastar con su fuente")
            continue
        if doc is None:
            if produccion:
                h("L1-COMPARACION-FUENTE", rel, f"cifra {c['texto'].strip()!r} sin 05-landing/fuentes_mercado.json: en producción toda cifra de mercado se contrasta con su fuente declarada")
        else:
            for motivo in contenido.fuente_respalda_cifra(doc, land, fuente=c["fuente"], fecha=c["fecha"], desde=desde, hasta=hasta, moneda=moneda):
                h("L1-COMPARACION-FUENTE", rel, f"cifra {c['texto'].strip()!r} ({c['fuente']}, {c['fecha']}): {motivo}")
        if produccion:
            try:
                dias = (hoy - date.fromisoformat(c["fecha"])).days
            except ValueError:
                h("L1-COMPARACION-FUENTE", rel, f"cifra {c['texto'].strip()!r} sin data-fecha válida")
                continue
            if dias > contenido.VIGENCIA_MERCADO_DIAS:
                h("L1-COMPARACION-FUENTE", rel, f"cifra {c['texto'].strip()!r} leída hace {dias} días (máximo {contenido.VIGENCIA_MERCADO_DIAS} en producción): vuelve a leer la fuente")


def _imagenes(pag: "_Pagina", rel: str, sitio: Path, slots_por_url: dict[str, dict], bytes_html: int, peso_imagenes_max: int,
              h: Callable[[str, str, str], None]) -> None:
    """``L1-IMAGEN-ROTULO``, ``L1-IMG-ATRIBUTOS`` y ``L1-PESO`` de las ``<img>`` de una página (ver el docstring del módulo)."""
    if bytes_html > PESO_HTML_MAX_KB * 1024:
        h("L1-PESO", rel, f"el HTML pesa {bytes_html // 1024} KB (máximo {PESO_HTML_MAX_KB} KB)")
    altas = [i for i in pag.imgs if i["fetchpriority"] == "high"]
    if len(altas) > 1:
        h("L1-IMG-ATRIBUTOS", rel, f"{len(altas)} imágenes con fetchpriority=\"high\": solo el héroe")
    total = 0
    vistas: set[str] = set()
    for im in pag.imgs:
        src = im["src"]
        etiqueta = src or "(sin src)"
        if not (im["width"].isdigit() and int(im["width"]) > 0 and im["height"].isdigit() and int(im["height"]) > 0):
            h("L1-IMG-ATRIBUTOS", rel, f"<img {etiqueta}> sin width y height (reserva el hueco y evita el salto de maquetación)")
        if im["slot"] and not (im["alt"] or "").strip():
            h("L1-IMG-ATRIBUTOS", rel, f"<img {etiqueta}> sin alt")
        heroe = "hero__img" in im["clase"].split()
        if heroe:
            if im["fetchpriority"] != "high" or im["loading"] == "lazy":
                h("L1-IMG-ATRIBUTOS", rel, f"el héroe ({etiqueta}) lleva fetchpriority=\"high\" y no loading=\"lazy\"")
        elif im["slot"]:
            if im["loading"] != "lazy":
                h("L1-IMG-ATRIBUTOS", rel, f"<img {etiqueta}> bajo el pliegue sin loading=\"lazy\"")
            if im["fetchpriority"] == "high":
                h("L1-IMG-ATRIBUTOS", rel, f"<img {etiqueta}> con fetchpriority=\"high\": solo el héroe")
        # rótulos de ilustrativa y de IA: propio (data-para = su ranura) o de grupo (data-para="grupo" en la misma sección)
        for marca, tipo, nombre in ((im["ilustrativa"], "ilustrativa", "ilustrativa"), (im["ia"], "ia", "de IA")):
            if not marca:
                continue
            ok = any(tipo in r["tipos"] and r["texto"].strip() and (r["para"] == im["slot"] or (r["para"] == "grupo" and r["seccion"] == im["seccion"])) for r in pag.rotulos)
            if not ok:
                h("L1-IMAGEN-ROTULO", rel, f"la imagen {nombre} {etiqueta} no lleva su rótulo visible (propio o de grupo en su sección)")
        # lo que dice assets.json debe salir tal cual en el HTML
        sl = slots_por_url.get(src)
        if sl is not None:
            if sl.get("ilustrativa") is True and not im["ilustrativa"]:
                h("L1-IMAGEN-ROTULO", rel, f"assets.json marca {sl['slot_id']} como ilustrativa y el HTML no la señala (data-ilustrativa)")
            if sl.get("etiqueta_ia_visible") is True and not im["ia"]:
                h("L1-IMAGEN-ROTULO", rel, f"assets.json marca {sl['slot_id']} con etiqueta_ia_visible y el HTML no la señala (data-ia)")
        # pesos de lo realmente publicado
        if src.startswith("/") and src not in vistas:
            vistas.add(src)
            archivo = sitio / src.lstrip("/")
            if archivo.is_file():
                tam = archivo.stat().st_size
                total += tam
                if sl is not None and tam > int(sl["peso_max_kb"]) * 1024:
                    h("L1-PESO", rel, f"{src} pesa {tam // 1024} KB y la ranura {sl['slot_id']} admite {sl['peso_max_kb']} KB")
    if total > peso_imagenes_max:
        h("L1-PESO", rel, f"las imágenes de la página suman {total // 1024} KB (máximo {peso_imagenes_max // 1024} KB)")


def validar_sitio(dir_oferta: Path | str, *, produccion: bool = False, hoy: date | None = None, carpeta: str = "sitio") -> list[Hallazgo]:
    """Hallazgos del lint de publicación sobre ``<dir_oferta>/05-landing``; vacío = pasa. Solo lee. ``hoy`` (por defecto, la fecha actual) solo decide si la
    barra de lanzamiento sigue vigente (``L1-BARRA-LANZAMIENTO``). ``carpeta``: la carpeta de ``05-landing/`` que se valida (``sitio`` por defecto; la salida de
    ``landing.generar --vista-previa`` está en ``sitio-vista-previa`` y solo debe dar ``L1-DEMO``)."""
    d = Path(dir_oferta)
    land, sitio = d / "05-landing", d / "05-landing" / carpeta
    base = f"05-landing/{carpeta}"
    oferta = comun.cargar_json(d / "03-oferta" / "oferta.json")
    checkout = comun.cargar_json(land / "checkout.json")
    tracking = comun.cargar_json(land / "tracking.json")
    rutas = lcomun.cargar_rutas(d)
    dominio = oferta["marca"]["dominio"].lower()
    lista, bump = oferta["precio"]["lista"], (oferta.get("bump") or {}).get("precio")
    importes_ok = {lista["monto"]} | ({bump["monto"]} if bump else set())
    hoy = hoy or date.today()
    out: list[Hallazgo] = []
    prog = checkout.get("precio_programado") if isinstance(checkout.get("precio_programado"), dict) else None
    ruta_ps = land / "prueba_social_real.json"
    prueba_real = comun.cargar_json(ruta_ps) if ruta_ps.is_file() else None
    permisos = {x.get("fuente") for x in oferta.get("prueba") or [] if x.get("tipo") == "testimonio_con_permiso" and x.get("consentimiento_ref")}
    ruta_fm = land / "fuentes_mercado.json"
    fuentes_mercado = comun.cargar_json(ruta_fm) if ruta_fm.is_file() else None
    ruta_as = land / "assets.json"
    slots_por_url: dict[str, dict] = {}
    if ruta_as.is_file():
        try:
            for sl in comun.cargar_json(ruta_as).get("slots", []):
                if sl.get("estado") == "aprobado" and sl.get("archivo"):
                    slots_por_url["/" + str(sl["archivo"]).lstrip("/")] = sl
        except (OSError, ValueError):
            slots_por_url = {}
    peso_imagenes_max = (lcomun.parametro_landing(d, "peso_landing_max_kb") or PESO_IMAGENES_MAX_KB) * 1024


    def h(regla: str, archivo: str, detalle: str) -> None:
        out.append(Hallazgo(regla, archivo, detalle))

    css_sitio = sitio / "css" / "estilos.css"
    if css_sitio.is_file() and css_sitio.stat().st_size > PESO_CSS_MAX_KB * 1024:
        h("L1-PESO", f"{base}/css/estilos.css", f"la hoja de estilos pesa {css_sitio.stat().st_size // 1024} KB (máximo {PESO_CSS_MAX_KB} KB)")
    for n in P.LEGALES:
        p = sitio / "legal" / f"{n}.html"
        if not p.is_file() or not p.read_text(encoding="utf-8").strip():
            h("L1-LEGALES", f"{base}/legal/{n}.html", "página legal ausente o vacía")
        if f"/legal/{n}" not in rutas:
            h("L1-RUTAS", "05-landing/rutas.json", f"falta la ruta /legal/{n}")
    for ruta, destino in rutas.items():
        if not str(destino).startswith("dinamica:") and not _archivo_de_ruta(sitio, ruta).is_file():
            h("L1-RUTAS", "05-landing/rutas.json", f"la ruta estática {ruta} no tiene archivo")
    if tracking["consent_gating"]["plataforma"] != "banner_propio_v1":
        h("L1-TRACKING-PLATAFORMA", "05-landing/tracking.json", f"plataforma {tracking['consent_gating']['plataforma']!r} != 'banner_propio_v1'")
    if checkout["precio"] != lista or checkout["moneda"] != oferta["moneda"]:
        h("L1-PRECIO", "05-landing/checkout.json", "precio o moneda distintos de oferta.json")
    if checkout["garantia_dias"] != oferta["garantia"]["dias"]:
        h("L1-GARANTIA", "05-landing/checkout.json", "garantia_dias distinto de oferta.garantia.dias")

    for ruta in sorted(sitio.rglob("*.html")):
        rel = ruta.relative_to(d).as_posix()
        html_crudo = ruta.read_text(encoding="utf-8")
        pag = _Pagina()
        pag.feed(html_crudo)
        importes_pag = importes_ok
        marcas = marcas_de_demo(html_crudo)
        if marcas:
            h("L1-DEMO", rel, "contenido de demostración o de vista previa (" + "; ".join(marcas) + "): solo sirve para ver el diseño, nunca para publicar")
        for i, c in enumerate(pag.cifras_mercado):
            if not c["en_bloque"]:
                h("L1-COMPARACION", rel, f"cifra de comparación {c['texto'].strip()!r} fuera de un bloque data-comparacion-mercado: no queda exenta de L1-PRECIO")
            if not c["fuente"].strip():
                h("L1-COMPARACION", rel, f"cifra de comparación {c['texto'].strip()!r} sin data-fuente (la fuente es obligatoria por cifra)")
        if pag.barra_lanzamiento is not None:
            fecha = pag.barra_lanzamiento
            if prog is None or prog.get("fecha") != fecha:
                h("L1-BARRA-LANZAMIENTO", rel, f"barra de lanzamiento con fecha {fecha!r} sin checkout.precio_programado de la misma fecha")
            else:
                try:
                    if date.fromisoformat(fecha) < hoy:
                        h("L1-BARRA-LANZAMIENTO", rel, f"la barra de lanzamiento vencía el {fecha} (hoy {hoy}): regenera el sitio sin ella")
                except ValueError:
                    h("L1-BARRA-LANZAMIENTO", rel, f"fecha {fecha!r} no válida")
                despues = (prog.get("precio") or {})
                if not isinstance(despues.get("monto"), int) or despues.get("moneda") != oferta["moneda"] or despues["monto"] <= lista["monto"]:
                    h("L1-BARRA-LANZAMIENTO", rel, "precio_programado.precio debe ser mayor que el precio actual y en la misma moneda")
                else:
                    importes_pag = importes_ok | {despues["monto"]}
        _comparacion_con_fuentes(pag, rel, fuentes_mercado, land, oferta["moneda"], produccion, hoy, h)
        _imagenes(pag, rel, sitio, slots_por_url, len(html_crudo.encode("utf-8")), peso_imagenes_max, h)
        for ps in pag.prueba_social:
            real = prueba_real or {}
            ok = False
            try:
                if ps["tipo"] == "ventas":
                    ok = int(ps["valor"]) >= 1 and int((real.get("ventas") or {}).get("total", 0)) == int(ps["valor"])
                elif ps["tipo"] == "descargas":
                    ok = int(ps["valor"]) >= 1 and int((real.get("descargas_muestra") or {}).get("total", 0)) == int(ps["valor"])
                elif ps["tipo"] == "valoracion":
                    v = real.get("valoracion") or {}
                    ok = int(ps["n"]) >= 1 and int(v.get("n", 0)) == int(ps["n"]) and int(v.get("media_decimas", 0)) == int(ps["valor"])
            except ValueError:
                ok = False
            if not ok:
                h("L1-PRUEBA-SOCIAL", rel, f"{ps['tipo']} {ps['valor']} sin dato real que lo respalde en 05-landing/prueba_social_real.json (solo se muestra lo medido)")
        for fuente in pag.resenas:
            if not fuente or fuente not in permisos:
                h("L1-RESENA", rel, f"reseña con data-fuente {fuente!r} sin testimonio con permiso en oferta.prueba (compra verificada)")
        if pag.lang != oferta["locale"]:
            h("L1-HTML-LANG", rel, f"lang={pag.lang!r} != {oferta['locale']!r}")
        ruta_publica = "/" if ruta.relative_to(sitio).as_posix() == "index.html" else "/" + ruta.relative_to(sitio).with_suffix("").as_posix()
        _formularios(pag, ruta_publica, oferta, checkout, rutas, lambda detalle, _rel=rel: h("L1-FORMULARIO", _rel, detalle))
        for etiqueta, url in pag.enlaces + [("og", c) for k, c in pag.meta if k in ("og:image", "og:url")]:
            if _es_externo(url, dominio):
                h("L1-ENLACE-EXTERNO", rel, f"{etiqueta} {url}")
                continue
            interno = _interno(url, dominio)
            if interno is None:
                continue
            existe = interno in rutas or any((base / interno.lstrip("/")).is_file() for base in (sitio, land))
            if not existe:
                h("L1-ENLACE-INTERNO", rel, f"{etiqueta} {url} no está en rutas.json ni existe como archivo")
        turnstile_ok = lcomun.turnstile(checkout) is not None and ruta_publica == lcomun.RUTA_COMPRAR
        turnstile_vistos = 0
        for src, codigo in pag.scripts:
            if src:
                if turnstile_ok and src == lcomun.URL_TURNSTILE:
                    turnstile_vistos += 1
                    if turnstile_vistos > 1:
                        h("L1-SCRIPT-EXTERNO", rel, "Turnstile repetido: solo se admite UN script externo exacto")
                elif _es_externo(src, dominio):
                    h("L1-SCRIPT-EXTERNO", rel, src)
                elif (_interno(src, dominio) or src) == lcomun.PIXEL:
                    h("L1-CONSENT-PIXEL", rel, "pixel.js enlazado desde el HTML: solo puede cargarlo consentimiento.js")
                elif (_interno(src, dominio) or src) != lcomun.SCRIPT_PERMITIDO:
                    h("L1-SCRIPT-NO-PERMITIDO", rel, src)
            elif RX_PIXEL_EN_CODIGO.search(codigo):
                h("L1-CONSENT-PIXEL", rel, "código de píxel en línea, sin esperar al consentimiento")
            elif codigo.strip():
                h("L1-SCRIPT-INLINE", rel, "script en línea")
        texto = pag.texto_visible()
        visibles = [texto, pag.title, *pag.alts, *(c for _, c in pag.meta)]
        if any(RX_EJEMPLO.search(x) for x in visibles):
            h("L1-EJEMPLO-VISIBLE", rel, "«ejemplo» en texto visible, título, alt o meta")
        if produccion and any(RX_EJEMPLO.search(c) for c in pag.comentarios):
            h("L1-EJEMPLO-COMENTARIO", rel, "comentario [EJEMPLO] en una página que va a producción")
        if RX_CONTADORES.search(texto):
            h("L1-CONTADORES", rel, "contador, cupo o escasez en el texto")
        if pag.casillas_marcadas:
            h("L1-CASILLA-PREMARCADA", rel, "casilla premarcada")
        for monto, simbolo in RX_IMPORTE.findall(texto):
            try:
                minor = int((Decimal(monto.replace(",", ".")) * 100).to_integral_value())
            except InvalidOperation:
                continue
            if minor not in importes_pag:
                h("L1-PRECIO", rel, f"importe {monto}{simbolo} no coincide con oferta.json {sorted(importes_ok)}")
            moneda_vista = _SIMBOLO_MONEDA.get(simbolo, simbolo)
            if moneda_vista != oferta["moneda"]:
                h("L1-MONEDA", rel, f"{simbolo} ({moneda_vista}) != {oferta['moneda']}")
        for simbolo in ("$", "£", "¥"):
            if simbolo in texto and _SIMBOLO_MONEDA.get(simbolo, simbolo) != oferta["moneda"]:
                h("L1-MONEDA", rel, f"símbolo {simbolo} de otra moneda en el texto")
        for bloque in pag.bloques:
            if RX_BLOQUE_GARANTIA.search(bloque):
                for dias in RX_DIAS.findall(bloque):
                    if int(dias) != oferta["garantia"]["dias"]:
                        h("L1-GARANTIA", rel, f"«{dias} días» en «{bloque[:60]}» != {oferta['garantia']['dias']}")
        if pag.body:
            if pag.body.get("data-precio-minor") not in (None, str(lista["monto"])):
                h("L1-PRECIO", rel, f"data-precio-minor={pag.body['data-precio-minor']} != {lista['monto']}")
            if pag.body.get("data-moneda") not in (None, oferta["moneda"]):
                h("L1-MONEDA", rel, f"data-moneda={pag.body['data-moneda']} != {oferta['moneda']}")
            if pag.body.get("data-garantia-dias") not in (None, str(oferta["garantia"]["dias"])):
                h("L1-GARANTIA", rel, "data-garantia-dias distinto de oferta.garantia.dias")
        publicos = [pag.title, *(c for k, c in pag.meta if k.startswith("og:"))]
        sens = V._terminos_sensibles(" ".join(publicos))
        if sens:
            h("L1-SALUD", rel, f"términos sensibles en <title>/og:* ({sens})")

    _csp(sitio, checkout, lambda detalle: h("L1-CSP", f"{base}/_headers", detalle))

    eventos = " ".join(e["nombre"] + " " + " ".join(e["parametros_permitidos"]) for e in tracking["eventos"])
    sens = V._terminos_sensibles(" ".join([dominio, tracking["dominio_verificado"], *rutas.keys(), eventos]))
    if sens:
        h("L1-SALUD", "05-landing/tracking.json", f"términos sensibles en dominio, rutas o eventos ({sens})")

    js = sitio / "js"
    cons = (js / "consentimiento.js").read_text(encoding="utf-8") if (js / "consentimiento.js").is_file() else ""
    for requerido in ("Aceptar", "Rechazar", "Personalizar", "version_texto", "fabrica_consent", ".checked = false"):
        if requerido not in cons:
            h("L1-CONSENTIMIENTO-JS", f"{base}/js/consentimiento.js", f"falta «{requerido}»")
    m = re.search(r"function cargarPixel\(\)\s*\{(.{0,220})", cons, re.S)
    if not m or "estado.marketing" not in m.group(1):
        h("L1-CONSENT-PIXEL", f"{base}/js/consentimiento.js", "cargarPixel() no depende de estado.marketing")
    if re.search(r"fbq\s*\(|connect\.facebook\.net", cons):
        h("L1-CONSENT-PIXEL", f"{base}/js/consentimiento.js", "consentimiento.js no puede contener el píxel")
    pix = (js / "pixel.js").read_text(encoding="utf-8") if (js / "pixel.js").is_file() else ""
    if "FabricaConsent.marketing() !== true" not in pix:
        h("L1-CONSENT-PIXEL", f"{base}/js/pixel.js", "pixel.js no comprueba el consentimiento")
    if tracking["pixel_id"] not in pix:
        h("L1-CONSENT-PIXEL", f"{base}/js/pixel.js", "pixel_id distinto de tracking.json")
    for archivo in sorted(js.glob("*.js")) if js.is_dir() else []:
        codigo = archivo.read_text(encoding="utf-8")
        if archivo.name not in ("pixel.js", "consentimiento.js") and RX_PIXEL_EN_CODIGO.search(codigo):
            h("L1-CONSENT-PIXEL", f"{base}/js/{archivo.name}", "otro JavaScript referencia el píxel")
        if produccion and "[EJEMPLO]" in codigo:
            h("L1-EJEMPLO-COMENTARIO", f"{base}/js/{archivo.name}", "comentario [EJEMPLO] en JavaScript de producción")
    return out


def reglas(hallazgos: list[Hallazgo]) -> set[str]:
    return {x.regla for x in hallazgos}


def main(argv: Sequence[str] | None = None) -> int:
    ap = lcomun.argparser_base("Lint de publicación (L1) de 05-landing/sitio/.")
    ap.add_argument("--produccion", action="store_true", help="exige además L1-EJEMPLO-COMENTARIO")
    ap.add_argument("--carpeta", default="sitio", help="carpeta de 05-landing/ a validar (por defecto sitio; la vista previa está en sitio-vista-previa)")
    ap.add_argument("--hoy", help="AAAA-MM-DD: fecha para comprobar que la barra de lanzamiento no ha vencido (por defecto, hoy)")
    args = ap.parse_args(argv)

    def cuerpo() -> int:
        env = lcomun.entorno_de_proceso()
        raiz = lcomun.raiz_de_argumentos(args, env)
        d = lcomun.dir_oferta(args.oferta, raiz=raiz)
        if args.hoy and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", args.hoy):
            raise ErrorValidacion("--hoy debe ser AAAA-MM-DD")
        hallazgos = validar_sitio(d, produccion=args.produccion, hoy=date.fromisoformat(args.hoy) if args.hoy else None, carpeta=args.carpeta)
        datos = {"oferta_id": args.oferta, "hallazgos": [h.__dict__ for h in hallazgos]}
        if args.json:
            import json as _json
            print(_json.dumps({"ok": not hallazgos, "modo": "dry_run", "codigo": 0 if not hallazgos else 3,
                               "datos": datos, "avisos": [str(h) for h in hallazgos]}, sort_keys=True, ensure_ascii=False))
        else:
            for hz in hallazgos:
                print(str(hz))
            if not hallazgos:
                print("sin hallazgos")
        if hallazgos:
            raise ErrorValidacion(f"{len(hallazgos)} hallazgo(s) de publicación", detalle={"reglas": sorted(reglas(hallazgos))})
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
