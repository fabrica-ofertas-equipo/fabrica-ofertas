"""Plantillas fijas de `landing.generar`: HTML, CSS y JavaScript sin dependencias.

Todo texto del Maker (promesa, ángulos, garantía, FAQ) se interpola en estas plantillas con
``html.escape``: nunca se concatena HTML crudo de un Maker (CSP, convenciones §10). El único
``<script>`` que cualquier página carga es ``/js/consentimiento.js``; ese script es el único
camino hacia ``/js/pixel.js`` y solo lo inyecta tras el consentimiento de marketing
(``banner_propio_v1``, ver docs/contratos.md C28).

Las siete páginas legales son plantilla genérica (decisión del dueño, 2026-11-06: sin abogado,
son ebooks de bajo riesgo): párrafos fijos con los datos de la marca y la garantía interpolados.
"""
from __future__ import annotations

import base64
import json
import re
from html import escape
from typing import Mapping, Sequence

LEGALES: tuple[str, ...] = ("vendedor", "terminos", "privacidad", "reembolsos", "cookies", "aviso", "entrega")

TITULOS_LEGALES: Mapping[str, str] = {
    "vendedor": "Datos del vendedor y contacto",
    "terminos": "Términos de uso",
    "privacidad": "Política de privacidad",
    "reembolsos": "Reembolsos y derecho de desistimiento",
    "cookies": "Política de cookies",
    "aviso": "Aviso de contenido",
    "entrega": "Entrega y soporte",
}

# PNG 1x1 transparente: placeholder genérico hasta que D4/D6 asignen un activo real (assets.json).
PNG_PLACEHOLDER_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

CSS_BASE = """\
:root{color-scheme:light}
body{font-family:system-ui,sans-serif;margin:0;line-height:1.5;color:#1a1a1a}
header,main,footer{max-width:720px;margin:0 auto;padding:1.5rem}
img{max-width:100%;height:auto}
.cta{display:inline-block;background:#0a7;color:#fff;padding:.75rem 1.25rem;border-radius:.4rem;text-decoration:none}
#fabrica-consent{position:fixed;inset:auto 0 0 0;z-index:999;background:#fff;border-top:2px solid #1a1a1a;padding:1rem}
.fc-botones{display:flex;gap:.5rem}
.fc-btn{flex:1;padding:.6rem;font:inherit;border:2px solid #1a1a1a;background:#fff;color:#1a1a1a;cursor:pointer}
"""


_BANNER_ES: Mapping[str, str] = {
    "titulo": "Tus preferencias de cookies",
    "cuerpo": "Usamos una cookie propia para recordar tu elección. Con tu permiso, también medimos el resultado de nuestros anuncios (Meta). Todo lo opcional está desactivado hasta que elijas.",
    "aceptar": "Aceptar", "rechazar": "Rechazar", "personalizar": "Personalizar", "guardar": "Guardar elección",
    "necesarias": "Necesarias (siempre activas): recordar esta elección.", "marketing": "Marketing: medir anuncios con el píxel de Meta.",
    "mas": "Más información",
}


def _js_texto(valor: str) -> str:
    """Literal de cadena JavaScript seguro (JSON; sin ``</`` ni separadores de línea Unicode)."""
    return json.dumps(valor, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def consentimiento_js(banner: Mapping[str, str] | None = None, version_texto: str = "v1", *, duracion_vid_s: int = 7776000, duracion_attr_s: int = 2592000) -> str:
    """Banner propio v1: Aceptar, Rechazar y Personalizar con el mismo peso; todo apagado por defecto.

    ``banner`` trae los textos del idioma (claves de ``_BANNER_ES``); sin él, español. ``pixel.js`` solo lo inyecta este archivo,
    tras el consentimiento de marketing. Estructura probada por el oráculo de CT (``tests/contratos/lint_landing_referencia.py``).

    Cookies propias del arranque de pago (docs/_historial/decision-arranque-de-pago.md §2.3), **solo con consentimiento de marketing**:
    ``fab_vid`` (``visitor_id`` = 128 bits aleatorios en hexadecimal, el mismo del píxel) y ``fab_attr`` (``k=v&k=v`` percent-encoded, ≤ 400 bytes, claves
    ``cid asid adid utm_* fbclid``; los IDs con ``^[0-9]{6,20}$``; cualquier otra clave se descarta); el Worker ``crear-sesion`` las lee del mismo origen. ``duracion_*_s`` son segundos y los fija
    quien llama (``landing.generar`` los lee de ``empresa/parametros.yaml``, grupo ``landing``).
    """
    t = {**_BANNER_ES, **(banner or {})}
    if not re.fullmatch(r"v[0-9]+", version_texto):
        raise ValueError("version_texto debe ser vN")
    texto = ",\n".join(f"    {k}: {_js_texto(t[k])}" for k in ("titulo", "cuerpo", "aceptar", "rechazar", "personalizar", "guardar", "necesarias", "marketing", "mas"))
    for nombre, valor in (("duracion_vid_s", duracion_vid_s), ("duracion_attr_s", duracion_attr_s)):
        if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
            raise ValueError(f"{nombre} debe ser un entero positivo")
    return (_CONSENTIMIENTO_PLANTILLA.replace("/*VERSION*/", version_texto).replace("/*TEXTO*/", texto)
            .replace("/*DURACION_VID*/", str(duracion_vid_s)).replace("/*DURACION_ATTR*/", str(duracion_attr_s)))


_CONSENTIMIENTO_PLANTILLA = """\
/* consentimiento.js - banner propio v1 (sin dependencias). Todo apagado por defecto.
 * Reglas: nada de marketing antes de elegir; botones Aceptar, Rechazar y Personalizar con el mismo peso (ids fc-aceptar, fc-rechazar,
 * fc-personalizar); la elección vive en una cookie propia con fecha y versión del texto; pixel.js SOLO lo carga este archivo.
 * Lo servido se hashea por bytes: no editar a mano (lo genera landing.generar con los textos de copy.json). */
(function () {
  'use strict';

  var CONFIG = {
    version_texto: '/*VERSION*/',        // sube al cambiar el texto del banner: obliga a volver a preguntar
    cookie: 'fabrica_consent',
    duracion_segundos: 15552000,         // 180 días
    pixel_src: '/js/pixel.js',           // única forma de llegar al píxel
    cookie_vid: 'fab_vid',               // visitor_id para el Worker crear-sesion (solo con consentimiento de marketing)
    cookie_attr: 'fab_attr',             // parámetros de anuncio de la URL de entrada (solo con consentimiento de marketing)
    duracion_vid_segundos: /*DURACION_VID*/,
    duracion_attr_segundos: /*DURACION_ATTR*/,
    atribucion: ['cid', 'asid', 'adid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbclid'],
    ids: ['cid', 'asid', 'adid'],        // ^[0-9]{6,20}$
    max_bytes_attr: 400                  // tope del valor de fab_attr
  };
  var TEXTO = {
/*TEXTO*/
  };

  var estado = { marketing: false, decidido: false, id: null, fecha: null };
  var pixelCargado = false;

  function leerCookie() {
    var pares = document.cookie ? document.cookie.split('; ') : [];
    for (var i = 0; i < pares.length; i++) {
      var k = pares[i].split('=');
      if (k[0] === CONFIG.cookie) {
        try { return JSON.parse(decodeURIComponent(k.slice(1).join('='))); } catch (e) { return null; }
      }
    }
    return null;
  }

  function escribirCookie(valor) {
    var seguro = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = CONFIG.cookie + '=' + encodeURIComponent(JSON.stringify(valor)) +
      '; Path=/; Max-Age=' + CONFIG.duracion_segundos + '; SameSite=Lax' + seguro;
  }

  // Meta crea _fbp/_fbc en el dominio raíz: se borran con y sin Domain=. Con el píxel ya cargado se recarga (fbq sigue vivo hasta entonces).
  function borrarCookiesDeMarketing() {
    var raiz = location.hostname.replace(/^www\\./, '');
    ['_fbp', '_fbc', CONFIG.cookie_vid, CONFIG.cookie_attr].forEach(function (n) {
      document.cookie = n + '=; Path=/; Max-Age=0; SameSite=Lax';
      document.cookie = n + '=; Path=/; Domain=.' + raiz + '; Max-Age=0; SameSite=Lax';
    });
  }

  function idAleatorio() {
    var b = new Uint8Array(16);                                  // 128 bits
    (window.crypto || window.msCrypto).getRandomValues(b);
    return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }

  // Parámetros de anuncio de la URL de entrada -> "k=v&k=v" percent-encoded, MÁXIMO max_bytes_attr bytes. Solo las claves de CONFIG.atribucion (el resto se
  // descarta), los tres IDs con ^[0-9]{6,20}$ (si no, se descartan) y sin caracteres de control. Si algo no cabe, se recorta el valor por caracteres (nunca
  // un %XX a medias) y se omite si queda vacío. El orden es el de CONFIG.atribucion: primero los IDs, al final fbclid.
  function atribucionDeUrl() {
    var q;
    try { q = new URLSearchParams(location.search); } catch (e) { return ''; }
    var cuerpo = '';
    CONFIG.atribucion.forEach(function (k) {
      var v = q.get(k);
      if (v === null) { return; }
      v = v.replace(/[\\u0000-\\u001f\\u007f]/g, '');
      if (CONFIG.ids.indexOf(k) >= 0 && !/^[0-9]{6,20}$/.test(v)) { return; }
      var prefijo = (cuerpo ? '&' : '') + k + '=';
      var libre = CONFIG.max_bytes_attr - cuerpo.length - prefijo.length;
      var caracteres = Array.from(v).slice(0, CONFIG.max_bytes_attr);
      var codificado = encodeURIComponent(caracteres.join(''));
      while (codificado.length > libre && caracteres.length > 0) {
        caracteres.pop();
        codificado = encodeURIComponent(caracteres.join(''));
      }
      if (caracteres.length > 0) { cuerpo += prefijo + codificado; }
    });
    return cuerpo;
  }

  // fab_vid y fab_attr: cookies propias del mismo origen que lee el Worker. SOLO con consentimiento de marketing; sin él no se escribe nada.
  function escribirCookiesPropias() {
    if (!estado.marketing) { return; }
    var seguro = location.protocol === 'https:' ? '; Secure' : '';
    if (estado.id) {
      document.cookie = CONFIG.cookie_vid + '=' + encodeURIComponent(estado.id) +
        '; Path=/; Max-Age=' + CONFIG.duracion_vid_segundos + '; SameSite=Lax' + seguro;
    }
    var atribucion = atribucionDeUrl();
    if (atribucion) {
      document.cookie = CONFIG.cookie_attr + '=' + atribucion +
        '; Path=/; Max-Age=' + CONFIG.duracion_attr_segundos + '; SameSite=Lax' + seguro;
    }
  }

  function cargarPixel() {
    if (pixelCargado || !estado.marketing) { return; }
    pixelCargado = true;
    var s = document.createElement('script');
    s.src = CONFIG.pixel_src;
    s.async = true;
    document.head.appendChild(s);
  }

  function aplicar(marketing) {
    var previo = estado.marketing;
    estado.marketing = !!marketing;
    estado.decidido = true;
    estado.fecha = new Date().toISOString();
    estado.id = estado.marketing ? (estado.id || idAleatorio()) : null;
    escribirCookie({ v: CONFIG.version_texto, m: estado.marketing ? 1 : 0, t: estado.fecha, id: estado.id });
    document.documentElement.setAttribute('data-consent-marketing', estado.marketing ? '1' : '0');
    if (previo && !estado.marketing) { borrarCookiesDeMarketing(); }
    escribirCookiesPropias();
    document.dispatchEvent(new CustomEvent('fabrica:consent', { detail: { marketing: estado.marketing, version: CONFIG.version_texto } }));
    cargarPixel();
    if (previo && !estado.marketing && pixelCargado) { location.reload(); }
  }

  function el(tag, attrs, hijos) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    (hijos || []).forEach(function (h) { n.appendChild(typeof h === 'string' ? document.createTextNode(h) : h); });
    return n;
  }

  function cerrar() {
    var b = document.getElementById('fabrica-consent');
    if (b && b.parentNode) { b.parentNode.removeChild(b); }
  }

  function mostrar() {
    cerrar();
    var casilla = el('input', { type: 'checkbox', id: 'fc-marketing' });
    casilla.checked = false;                                   // apagado por defecto
    var panel = el('div', { id: 'fc-panel', hidden: 'hidden' }, [
      el('p', {}, [TEXTO.necesarias]),
      el('label', {}, [casilla, ' ' + TEXTO.marketing]),
      el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-guardar' }, [TEXTO.guardar])
    ]);
    var banner = el('div', { id: 'fabrica-consent', role: 'dialog', 'aria-labelledby': 'fc-titulo' }, [
      el('h2', { id: 'fc-titulo' }, [TEXTO.titulo]),
      el('p', {}, [TEXTO.cuerpo + ' ', el('a', { href: '/legal/cookies' }, [TEXTO.mas])]),
      el('div', { 'class': 'fc-botones' }, [
        el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-aceptar' }, [TEXTO.aceptar]),
        el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-rechazar' }, [TEXTO.rechazar]),
        el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-personalizar' }, [TEXTO.personalizar])
      ]),
      panel
    ]);
    document.body.appendChild(banner);
    document.getElementById('fc-aceptar').addEventListener('click', function () { aplicar(true); cerrar(); });
    document.getElementById('fc-rechazar').addEventListener('click', function () { aplicar(false); cerrar(); });
    document.getElementById('fc-personalizar').addEventListener('click', function () { panel.removeAttribute('hidden'); });
    document.getElementById('fc-guardar').addEventListener('click', function () { aplicar(casilla.checked); cerrar(); });
  }

  function iniciar() {
    var c = leerCookie();
    if (c && c.v === CONFIG.version_texto && (c.m === 0 || c.m === 1)) {
      estado.marketing = c.m === 1; estado.decidido = true; estado.id = c.id || null; estado.fecha = c.t || null;
      if (estado.marketing && !estado.id) {
        estado.id = idAleatorio();
        escribirCookie({ v: CONFIG.version_texto, m: 1, t: estado.fecha, id: estado.id });
      }
      document.documentElement.setAttribute('data-consent-marketing', estado.marketing ? '1' : '0');
      escribirCookiesPropias();
      cargarPixel();
    } else {
      document.documentElement.setAttribute('data-consent-marketing', '0');
      borrarCookiesDeMarketing();          // sin elección vigente (texto nuevo o primera visita): ante la duda, nada de marketing
      mostrar();
    }
    Array.prototype.forEach.call(document.querySelectorAll('[data-consent-abrir]'), function (b) { b.addEventListener('click', mostrar); });
  }

  window.FabricaConsent = {
    marketing: function () { return estado.marketing === true; },
    visitorId: function () { return estado.id; },
    abrir: mostrar
  };

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', iniciar); } else { iniciar(); }
})();
"""


def pixel_js(pixel_id: str, eventos: Sequence[str] = ("PageView", "ViewContent")) -> str:
    """``pixel.js`` (inyectado SOLO por ``consentimiento.js``): vuelve a comprobar el consentimiento y emite solo ``eventos`` declarados.

    ``eventos`` son los nombres de ``tracking.json`` con canal ``pixel``/``ambos`` que esta página puede emitir (``PageView`` y
    ``ViewContent``); ``ViewContent`` solo sale en páginas de producto (las que traen ``data-oferta-id`` y ``data-precio-minor``).
    """
    pid = re.sub(r"[^0-9A-Za-z_-]", "", pixel_id)
    emite_pv = "PageView" in eventos
    emite_vc = "ViewContent" in eventos
    pv = "  window.fbq('track', 'PageView', {}, { eventID: 'pv_' + visitante + '_' + ahora });\n" if emite_pv else ""
    vc = (
        "  if (idOferta && valor !== null && moneda) {\n"
        "    window.fbq('track', 'ViewContent', {\n"
        "      content_ids: [idOferta],\n"
        "      content_type: 'product',\n"
        "      value: valor,\n"
        "      currency: moneda\n"
        "    }, { eventID: 'vc_' + visitante + '_' + ahora });\n"
        "  }\n"
    ) if emite_vc else ""
    return f"""\
/* pixel.js - píxel de Meta. NO se enlaza desde ningún HTML: lo inyecta consentimiento.js y solo después de que la persona
 * acepte marketing. Sin consentimiento este archivo no se pide. Eventos: la lista cerrada de tracking.json; nada de salud
 * ni de datos personales. ViewContent solo en páginas de producto; el valor se formatea con ENTEROS (data-decimales). */
(function () {{
  'use strict';
  if (!window.FabricaConsent || window.FabricaConsent.marketing() !== true) {{ return; }}   // defensa en profundidad

  var PIXEL_ID = '{pid}';   // = tracking.json.pixel_id
  var cuerpo = document.body;
  var ahora = Date.now();
  var visitante = window.FabricaConsent.visitorId() || 'anon';

  !function (f, b, e, v, n, t, s) {{
    if (f.fbq) {{ return; }}
    n = f.fbq = function () {{ n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); }};
    if (!f._fbq) {{ f._fbq = n; }}
    n.push = n; n.loaded = true; n.version = '2.0'; n.queue = [];
    t = b.createElement(e); t.async = true; t.src = v;
    s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
  }}(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');

  // Unidad menor entera -> decimal como cadena ("1990", 2 -> "19.90"; "1990", 0 -> "1990"); null si el dato no es un entero.
  function valorDecimal(minor, decimales) {{
    if (minor === null || !/^[0-9]+$/.test(minor) || !/^[0-9]$/.test(String(decimales))) {{ return null; }}
    var n = Number(decimales), m = minor;
    if (n === 0) {{ return m; }}
    while (m.length <= n) {{ m = '0' + m; }}
    return m.slice(0, m.length - n) + '.' + m.slice(m.length - n);
  }}

  var idOferta = cuerpo.getAttribute('data-oferta-id');
  var valor = valorDecimal(cuerpo.getAttribute('data-precio-minor'), cuerpo.getAttribute('data-decimales'));
  var moneda = cuerpo.getAttribute('data-moneda');

  window.fbq('init', PIXEL_ID);
{pv}{vc}}})();
"""


def csp(*, turnstile: bool = False) -> str:
    """Content-Security-Policy CANÓNICA del sitio (decisión de S-A, ``landing.comun.CSP_CANONICA``): ``form-action 'self' https://checkout.stripe.com``
    exacto, ``script-src 'self' https://connect.facebook.net`` (el píxel solo lo inyecta ``pixel.js`` tras el consentimiento de marketing) y nada de
    ``'unsafe-inline'``. Con ``turnstile`` (solo ``/comprar``) suma el origen de Turnstile en ``script-src`` y ``frame-src``."""
    from landing import comun as lc   # import local: plantillas no depende de comun al importarse
    return lc.csp_texto(turnstile=turnstile)


def cabeceras(*, turnstile: bool = False) -> str:
    """Archivo ``_headers`` de Cloudflare Pages. Con ``turnstile`` la ruta ``/comprar`` sustituye (``!``) la CSP general por la suya."""
    from landing import comun as lc
    comunes = "  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
    texto = f"/*\n  Content-Security-Policy: {csp()}\n{comunes}"
    if turnstile:
        texto += f"{lc.RUTA_COMPRAR}\n  ! Content-Security-Policy\n  Content-Security-Policy: {csp(turnstile=True)}\n"
    return texto


def pagina_legal(nombre: str, *, marca: str, dominio: str, garantia_dias: int) -> str:
    """Párrafo genérico de una página legal (plantilla, sin revisión de abogado: decisión del dueño)."""
    cuerpo = {
        "vendedor": f"<p>Vendedor: {escape(marca)}. Contacto: soporte en el dominio {escape(dominio)}, por el formulario de soporte del sitio.</p>",
        "terminos": f"<p>Al comprar en {escape(marca)} aceptas estos términos de uso. El contenido es informativo y se entrega según lo descrito en la página de producto.</p>",
        "privacidad": f"<p>{escape(marca)} trata los datos necesarios para procesar el pedido y la entrega. No se piden datos de salud. Puedes solicitar la baja de tus datos por el formulario de soporte.</p>",
        "reembolsos": f"<p>Dispones de {int(garantia_dias)} días desde la compra para solicitar la devolución íntegra del importe, sin preguntas. También aplica el derecho de desistimiento donde la ley lo exija.</p>",
        "cookies": f"<p>{escape(marca)} usa una cookie propia para recordar tu elección de cookies y, solo si aceptas, cookies de marketing. Puedes cambiar tu elección con el botón de preferencias del pie de página.</p>",
        "aviso": f"<p>El contenido de {escape(marca)} es informativo y no sustituye asesoría profesional. No se garantizan resultados concretos.</p>",
        "entrega": f"<p>La entrega es digital e inmediata tras la compra, por el enlace enviado a tu correo. El soporte se atiende por el formulario de soporte del sitio.</p>",
    }[nombre]
    return cuerpo
