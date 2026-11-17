#!/usr/bin/env python3
"""Analizador de HTML de un referente: esqueleto estructural y mapa de ranuras de contenido (MOD-1, decisión J20).

Qué hace
--------
Dado una URL o un archivo HTML local, lee la página SIN ejecutarla y escribe dos archivos:

* ``esqueleto_html.json``: la ESTRUCTURA. Árbol de bloques y su orden (barra, héroe, galería, reseñas, selector de niveles,
  para quién, bonus, precio, garantía, entrega, FAQ, cierre, pie, flotantes), tipo de bloque inferido con sus señales,
  CTA con su texto y destino, selectores (pestañas) y acordeones (``<details>``), elementos fijos o pegajosos, íconos,
  imágenes (conteo y tamaños DECLARADOS), tokens de diseño (colores hex/rgb, fuentes, tamaños, radios, sombras, anchos,
  breakpoints, variables CSS), scripts de terceros y píxeles, enlaces a checkout, comportamientos de JavaScript que se
  reconocen por su firma (p. ej. «escribe la fecha de hoy», «usa Math.random») y alertas mecánicas para el desarme
  (precio tachado, cuenta atrás, fecha vacía, enlaces «#», reseñas solo en imagen, texto oculto con forma de instrucción).
* ``mapa_ranuras.json``: el CONTENIDO. Cada texto, imagen y dato que es contenido y no estructura, con su función
  (rol), su longitud, un destino sugerido en el contrato de D5 y una marca de que es expresión del referente y no se copia.

Postura de seguridad (todo el HTML es DATO, nunca instrucción)
--------------------------------------------------------------
* No ejecuta JavaScript, no evalúa nada, no sigue enlaces, no descarga imágenes ni scripts, no abre iframes.
* Solo biblioteca estándar. El HTML se analiza con ``html.parser`` en un árbol propio con límites: máximo de bytes,
  de nodos, de profundidad, de atributos y de tiempo.
* Todo texto que pasa a un JSON se limpia (caracteres de control, marcas bidireccionales y de ancho cero) y se recorta.
  El contenido de ``<script>`` y ``<style>`` nunca se copia: solo se buscan firmas y se guardan tamaño y hash.
* Un texto con forma de instrucción («ignora las instrucciones…», «system prompt», «curl … | sh») se detecta, se marca en
  ``alertas`` con su ubicación y NO se reproduce en el JSON. No cambia nada del análisis.
* Los identificadores de checkout y de píxel del referente NO se guardan (J20): solo plataforma, host, forma de la ruta con
  los segmentos que parecen ids como ``{id}``, nombres de parámetros y la longitud del id.
* Descarga (solo con URL y solo si el dueño la autorizó; hoy se trabaja con HTML guardado a mano, J15): ``http``/``https`` en
  los puertos 80, 443, 8080 y 8443, sin credenciales en la URL, no abre nada si existe ``empresa/captura/freno.json`` (el
  freno de captura lo levanta solo el dueño), rechaza
  direcciones privadas, locales o reservadas (también en cada redirección, máximo 5), ``robots.txt`` respetado, timeout,
  tamaño máximo (sin descompresión: ``Accept-Encoding: identity``; si el servidor comprime igual, se rechaza), sin cookies,
  sin proxy, user-agent genérico. Un 403, 429 o un bloqueo de ``robots.txt`` NO se esquiva: el dueño guarda el HTML con su
  navegador y se usa el modo archivo. ``--no-red`` prohíbe toda conexión (solo archivos locales).

Uso (desde la raíz del repositorio; para HTML descargado conviene ``-I``)::

    .venv/bin/python -I .claude/skills/modelado-oferta/scripts/analizar_html.py ARCHIVO.html --no-red --salida DIR
    .venv/bin/python -I .claude/skills/modelado-oferta/scripts/analizar_html.py https://ejemplo.com/pagina --salida DIR

    --salida DIR        escribe esqueleto_html.json y mapa_ranuras.json (sin ella, solo imprime un resumen)
    --sobrescribir      permite reemplazar archivos existentes (por defecto no pisa nada)
    --no-red            sin conexiones: rechaza URL y --css-externo
    --max-bytes N       tamaño máximo del HTML (defecto 2 MB; tope 10 MB); superarlo es un error, no un recorte
    --timeout S         segundos por conexión (defecto 15)
    --css-externo       baja hasta 5 hojas de estilo externas (mismos límites) para completar los tokens de diseño
    --freno RUTA        archivo del freno de captura (defecto empresa/captura/freno.json); si existe, no se abre ninguna URL
    --host-propio H     dominio propio de la página (para separar scripts de terceros cuando se analiza un archivo)
    --sin-muestras      el mapa de ranuras no lleva ni el recorte de 60 caracteres de cada texto
    --permitir-red-privada  solo para pruebas locales de quien lo ejecuta; no se usa en una corrida real

Salidas: 0 ok · 2 uso o entrada inválida · 3 red no permitida o bloqueada (no se esquiva) · 4 tamaño excedido ·
5 respuesta no válida (estado, tipo o codificación).

Qué detecta bien y qué no: ver ``references/analizar-html.md`` (comparación con el análisis hecho a mano de Axon).
Límites principales: la inferencia del tipo de bloque es por reglas (clases, ids, títulos en siete idiomas y estructura):
es una propuesta con ``confianza``, no una verdad; las hojas externas solo se leen con ``--css-externo``; las reglas CSS
con combinadores solo se usan de forma aproximada (se compara el último selector compuesto); el JavaScript no se interpreta
(solo firmas); no ve lo que un script inserta en el DOM; no distingue diseño a 360 px de escritorio (no renderiza).
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

VERSION = "0.1.0"
SCHEMA = "0.1.0-borrador"
UA = "Mozilla/5.0 (compatible; analizador-html/0.1)"
UA_ROBOTS = "analizador-html"

MAX_BYTES_DEFECTO = 2_000_000
MAX_BYTES_TOPE = 10_000_000
TIMEOUT_DEFECTO = 15.0
MAX_REDIRECCIONES = 5
MAX_ROBOTS_BYTES = 200_000
MAX_CSS_EXTERNOS = 5
PUERTOS_OK = {80, 443, 8080, 8443}

FRENO_DEFECTO = Path(__file__).resolve().parents[4] / "empresa" / "captura" / "freno.json"

MAX_NODOS = 150_000
MAX_PROFUNDIDAD = 200
MAX_ATRIBUTOS = 60
MAX_TEXTO_TOTAL = 3_000_000
MAX_SCRIPT_TEXTO = 400_000
MAX_STYLE_TEXTO = 2_000_000
MAX_SEGUNDOS_PARSEO = 30.0
CHUNK = 32_768

MAX_RANURAS = 1500
MAX_RANURAS_SECCION = 160
MAX_CTAS = 120
MAX_REGLAS_CSS = 60_000
MAX_MUESTRA = 60
MAX_LINEAS_DOM = 40

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr",
        "command", "keygen"}
BLOQUE = {"address", "article", "aside", "blockquote", "details", "div", "dl", "dd", "dt", "fieldset", "figure",
          "figcaption", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav",
          "ol", "p", "pre", "section", "table", "tr", "td", "th", "ul", "summary", "button"}
CIERRAN_P = {"address", "article", "aside", "blockquote", "div", "dl", "fieldset", "figure", "footer", "form", "h1",
             "h2", "h3", "h4", "h5", "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section", "table", "ul"}
SEMANTICOS = {"section", "header", "footer", "nav", "aside", "article"}
IGNORAR_TOP = {"script", "style", "link", "meta", "noscript", "template", "head", "title", "base", "br", "hr",
               "svg", "iframe", "object", "embed"}
NO_TEXTO = {"script", "style", "template", "noscript", "svg", "head", "iframe", "object", "embed", "canvas"}
CONTENEDORES = {"div", "main", "form", "center", "span", "html", "body"}
ENVOLTORIO_TOKENS = {"wrap", "wrapper", "container", "app", "root", "page", "content", "main", "inner", "site",
                     "elementor", "entry", "layout", "body", "outer"}

_CTRL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏ -‮⁠-⁩﻿]")

PLATAFORMAS_CHECKOUT = {
    "hotmart.com": "Hotmart", "kiwify.com.br": "Kiwify", "kiwify.app": "Kiwify", "eduzz.com": "Eduzz",
    "monetizze.com.br": "Monetizze", "braip.com": "Braip", "ticto.com.br": "Ticto", "greenn.com.br": "Greenn",
    "perfectpay.com.br": "PerfectPay", "cakto.com.br": "Cakto", "buy.stripe.com": "Stripe Payment Link",
    "checkout.stripe.com": "Stripe Checkout", "paddle.com": "Paddle", "gumroad.com": "Gumroad", "gum.co": "Gumroad",
    "lemonsqueezy.com": "Lemon Squeezy", "payhip.com": "Payhip", "sellfy.com": "Sellfy", "samcart.com": "SamCart",
    "thrivecart.com": "ThriveCart", "clickbank.net": "ClickBank", "digistore24.com": "Digistore24",
    "paypal.com": "PayPal", "paypal.me": "PayPal", "mercadopago.com": "Mercado Pago", "mpago.la": "Mercado Pago",
    "przelewy24.pl": "Przelewy24", "p24.pl": "Przelewy24", "tpay.com": "Tpay", "payu.com": "PayU", "payu.pl": "PayU",
    "myshopify.com": "Shopify", "systeme.io": "systeme.io", "kajabi.com": "Kajabi", "teachable.com": "Teachable",
    "podia.com": "Podia", "thinkific.com": "Thinkific", "fastspring.com": "FastSpring", "mollie.com": "Mollie",
    "whop.com": "Whop", "ko-fi.com": "Ko-fi", "buymeacoffee.com": "Buy Me a Coffee",
}
RUTA_CHECKOUT = re.compile(r"(?:^|/)(?:checkout|cart|carrito|koszyk|carrello|panier|warenkorb|buy|order|pedido|"
                           r"comprar|zamow|zamów|acquista|pay|payment|pago|pagamento|platnosc|płatność)(?:/|$|\?)", re.I)

TERCEROS = {
    "connect.facebook.net": ("pixel_publicitario", "Meta Pixel"),
    "facebook.com": ("pixel_publicitario", "Meta"),
    "googletagmanager.com": ("gestor_de_etiquetas", "Google Tag Manager"),
    "google-analytics.com": ("analitica", "Google Analytics"),
    "analytics.google.com": ("analitica", "Google Analytics"),
    "googleadservices.com": ("pixel_publicitario", "Google Ads"),
    "googlesyndication.com": ("pixel_publicitario", "Google Ads"),
    "doubleclick.net": ("pixel_publicitario", "Google Ads"),
    "analytics.tiktok.com": ("pixel_publicitario", "TikTok Pixel"),
    "snap.licdn.com": ("pixel_publicitario", "LinkedIn Insight"),
    "static.ads-twitter.com": ("pixel_publicitario", "X Pixel"),
    "sc-static.net": ("pixel_publicitario", "Snap Pixel"),
    "s.pinimg.com": ("pixel_publicitario", "Pinterest Tag"),
    "static.hotjar.com": ("analitica_de_comportamiento", "Hotjar"),
    "script.hotjar.com": ("analitica_de_comportamiento", "Hotjar"),
    "clarity.ms": ("analitica_de_comportamiento", "Microsoft Clarity"),
    "cloudflareinsights.com": ("analitica", "Cloudflare Web Analytics"),
    "cdn.jsdelivr.net": ("biblioteca_cdn", "jsDelivr"),
    "unpkg.com": ("biblioteca_cdn", "unpkg"),
    "cdnjs.cloudflare.com": ("biblioteca_cdn", "cdnjs"),
    "code.jquery.com": ("biblioteca_cdn", "jQuery CDN"),
    "ajax.googleapis.com": ("biblioteca_cdn", "Google Hosted Libraries"),
    "fonts.googleapis.com": ("fuentes", "Google Fonts"),
    "fonts.gstatic.com": ("fuentes", "Google Fonts"),
    "js.stripe.com": ("pagos", "Stripe.js"),
    "paypal.com": ("pagos", "PayPal"),
    "paypalobjects.com": ("pagos", "PayPal"),
    "sdk.mercadopago.com": ("pagos", "Mercado Pago"),
    "cdn.shopify.com": ("plataforma", "Shopify"),
    "recaptcha.net": ("antispam", "reCAPTCHA"),
    "tawk.to": ("chat", "Tawk.to"),
    "crisp.chat": ("chat", "Crisp"),
    "intercom.io": ("chat", "Intercom"),
    "zdassets.com": ("chat", "Zendesk"),
    "hs-scripts.com": ("crm_y_marketing", "HubSpot"),
    "hsforms.net": ("crm_y_marketing", "HubSpot"),
    "chimpstatic.com": ("crm_y_marketing", "Mailchimp"),
    "klaviyo.com": ("crm_y_marketing", "Klaviyo"),
    "cdn-reach.hostinger.com": ("crm_y_marketing", "Hostinger Reach"),
    "player.vimeo.com": ("video", "Vimeo"),
    "youtube.com": ("video", "YouTube"),
    "youtube-nocookie.com": ("video", "YouTube"),
    "wistia.com": ("video", "Wistia"),
    "wistia.net": ("video", "Wistia"),
    "converteai.net": ("video", "VTurb / ConverteAI"),
    "utmify.com.br": ("rastreo_de_atribucion", "UTMify"),
    "workers.dev": ("rastreo_desconocido", "Cloudflare Workers (script de tercero)"),
}
BIBLIOTECAS_CONOCIDAS = (("jquery", "jQuery"), ("elementor", "Elementor"), ("swiper", "Swiper"), ("slick", "Slick"),
                         ("bootstrap", "Bootstrap"), ("alpine", "Alpine.js"), ("gsap", "GSAP"), ("aos", "AOS"))

FIRMAS_PIXEL = (
    ("Meta Pixel", re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"]?(\d{6,20})")),
    ("Google Analytics / Ads", re.compile(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]([A-Za-z0-9-]{4,30})")),
    ("Google Tag Manager", re.compile(r"(GTM-[A-Z0-9]{4,9})")),
    ("TikTok Pixel", re.compile(r"ttq\.load\(\s*['\"]([A-Za-z0-9]{8,30})")),
    ("LinkedIn Insight", re.compile(r"_linkedin_partner_id\s*=\s*['\"]?(\d{4,12})")),
    ("Snap Pixel", re.compile(r"snaptr\(\s*['\"]init['\"]\s*,\s*['\"]([A-Za-z0-9-]{8,50})")),
    ("Pinterest Tag", re.compile(r"pintrk\(\s*['\"]load['\"]\s*,\s*['\"](\d{6,20})")),
    ("Hotjar", re.compile(r"hjid\s*[:=]\s*(\d{4,10})")),
    ("Microsoft Clarity", re.compile(r"clarity\(\s*['\"]set['\"]|\"clarity\"")),
)
ATRIBUTOS_PIXEL = ("data-pixel", "data-pixel-id", "data-fb-pixel", "data-fbpixel", "data-gtm", "data-ga")

FIRMAS_JS = (
    ("fecha_actual_escrita_en_el_dom", re.compile(r"new\s+Date\s*\("), re.compile(r"textContent|innerHTML|innerText"),
     "escribe la fecha de hoy en la página: una «oferta de hoy» que se renueva sola (urgencia falsa)"),
    ("aleatoriedad", re.compile(r"Math\.random\s*\("), None,
     "usa números aleatorios (típico de contadores de «personas viendo» o de nombres de avisos)"),
    ("temporizador_periodico", re.compile(r"setInterval\s*\("), None,
     "repite una acción cada cierto tiempo (avisos, relojes, rotadores)"),
    ("almacenamiento_local", re.compile(r"sessionStorage|localStorage"), None,
     "guarda estado en el navegador (típico de cuentas atrás que se reinician por sesión)"),
    ("ventana_de_salida_probable",
     re.compile(r"(?:document|window|body|documentElement)\s*\.\s*addEventListener\(\s*['\"](?:mouseout|mouseleave|beforeunload)|exit[-_ ]?intent"),
     None, "posible ventana emergente al intentar salir de la página"),
    ("observador_de_visibilidad", re.compile(r"IntersectionObserver"), None, "dispara efectos al entrar en pantalla"),
    ("animacion_por_js", re.compile(r"requestAnimationFrame"), None,
     "anima por JavaScript (autodesplazamiento de tiras, contadores)"),
    ("peticiones_de_red", re.compile(r"\bfetch\s*\(|XMLHttpRequest"), None, "pide datos a un servidor tras cargar"),
    ("cookies", re.compile(r"document\.cookie"), None, "lee o escribe cookies"),
    ("redireccion_por_js", re.compile(r"location\.(?:href|replace|assign)\s*="), None, "puede redirigir por JavaScript"),
)

PATRONES_INSTRUCCION = tuple(re.compile(p, re.I) for p in (
    r"ignor\w*\s+(?:all\s+|any\s+|the\s+|todas?\s+|las\s+|tus\s+|your\s+)?(?:previous|prior|above|anteriores|previas|instruc\w+|rules?|reglas?)",
    r"olvid\w+\s+(?:todo|las|lo|tus)\s",
    r"disregard\s+(?:all|any|the|previous)",
    r"system\s*prompt|prompt\s+del\s+sistema",
    r"\byou\s+are\s+(?:now\s+)?(?:an?|the)\s",
    r"\beres\s+(?:ahora\s+)?un\s+(?:asistente|agente|modelo)",
    r"(?:^|\W)(?:assistant|asistente)\s*:",
    r"<\|im_(?:start|end)\|>|\[/?INST\]|BEGIN\s+SYSTEM",
    r"do\s+not\s+(?:follow|obey)|no\s+sigas\s+las",
    r"\b(?:curl|wget)\b[^|]{0,120}\|\s*(?:sh|bash)\b|\brm\s+-rf\b",
    r"jailbreak|developer\s+mode|modo\s+desarrollador",
    r"(?:reveal|show|print|muestra|revela)\s+(?:your\s+|tu\s+)?(?:system|instrucc|prompt|clave|key|secret)",
))

ESTILO_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
ESTILO_RGB = re.compile(r"rgba?\(\s*([0-9.]+%?)[\s,]+([0-9.]+%?)[\s,]+([0-9.]+%?)(?:[\s,/]+[0-9.]+%?)?\s*\)", re.I)
ESTILO_HSL = re.compile(r"hsla?\(\s*([0-9.]+)(?:deg)?[\s,]+([0-9.]+)%[\s,]+([0-9.]+)%", re.I)
RE_MONEDA = re.compile(
    r"(?:(?:[$€£¥₽₹]|US\$|R\$|USD|EUR|PLN|GBP|zł|zl|kr|CHF)\s?\d[\d.,\s]{0,10}\d)|"
    r"(?:\d[\d.,\s]{0,10}\d\s?(?:[$€£¥₽₹]|(?:USD|EUR|PLN|GBP|zł|zl|kr|CHF|reais|euros?|dolares|dólares)\b))|"
    r"(?:[$€£]\s?\d)|(?:\d\s?(?:[€£$]|zł))", re.I)
RE_FECHA = re.compile(r"(?:\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b)|(?:-{1,3}\s?/\s?-{1,3}\s?/\s?-{2,4})|\b(?:dd|DD)[/.\-](?:mm|MM)[/.\-](?:yyyy|YYYY|aaaa|AAAA)\b")
RE_RELOJ = re.compile(r"(?:\b\d{1,2}:\d{2}(?::\d{2})?\b)|(?:-{1,2}:-{1,2}(?::-{1,2})?)")
RE_CIFRA = re.compile(r"\d")
RE_NUMERO_MAS = re.compile(r"\+\s?\d[\d.,]*")

VERBOS_CTA = (
    "comprar", "compra", "quiero", "acceder", "accede", "empezar", "empieza", "descargar", "descarga", "obtener",
    "obten", "unirme", "apuntarme", "reservar", "pedir", "probar", "buy", "get", "start", "download", "order", "join",
    "claim", "grab", "access", "add to cart", "acquista", "voglio", "ottieni", "scarica", "inizia", "sblocca", "si,",
    "kup", "pobierz", "zamow", "chce", "dolacz", "odblokuj", "zacznij", "achetez", "commander", "je veux", "obtenir",
    "telecharger", "kaufen", "bestellen", "herunterladen", "ich will", "quero", "baixar", "garantir", "sim,", "yes,",
    "tak,")
TOKENS_CTA = {"btn", "button", "cta", "boton", "bouton", "przycisk", "pulsante", "botao"}
TOKENS_NO_CTA = {"tab", "tabs", "faq", "accordion", "toggle", "close", "cerrar", "menu", "hamburger", "nav", "swiper",
                 "slick", "prev", "next", "dot", "dots", "plus", "minus"}

CLAVES_TIPO = {
    "barra_superior": {"urgency", "announce", "announcement", "topbar", "promo", "notice", "aviso"},
    "heroe": {"hero", "masthead", "jumbotron", "above", "portada", "cabecera"},
    "tira_imagenes": {"marquee", "carousel", "slider", "gallery", "galeria", "swiper", "slick", "strip", "preview",
                      "previa", "muestra", "sneak"},
    "resenas": {"testi", "testimonial", "testimonials", "review", "reviews", "opinion", "opiniones", "opinie",
                "recensioni", "feedback", "depoimentos", "avis", "proof", "reseñas", "resenas", "testimonios"},
    "selector_niveles": {"tabs", "tablist", "levels", "niveles", "livelli", "poziomy", "niveis"},
    "contenido": {"contenido", "contenuto", "includes", "inside", "modules", "modulos", "curriculum", "programa",
                  "temario", "zawartosc"},
    "para_quien": {"who", "audience", "persona", "personas", "paraquien", "perchi", "dlakogo", "foryou"},
    "bonus": {"bonus", "bono", "bonos", "bonuses", "dodatek", "dodatki", "regalo", "gift", "extras"},
    "precio": {"offer", "offerta", "oferta", "price", "pricing", "precio", "preco", "prezzo", "cena", "checkout",
               "purchase"},
    "garantia": {"guarantee", "garantia", "garanzia", "gwarancja", "refund", "moneyback", "risk", "riesgo", "rischio"},
    "entrega": {"steps", "step", "pasos", "passi", "kroki", "delivery", "entrega", "consegna", "dostawa"},
    "faq": {"faq", "faqs", "accordion", "pytania", "domande", "preguntas", "perguntas"},
    "cta_final": {"final", "closing", "cierre", "finale", "lastcta", "close-cta", "closecta", "cta-final", "final-cta"},
    "problema": {"problem", "problema", "pain", "dolor"},
    "solucion": {"solution", "solucion", "soluzione", "mechanism", "mecanismo", "metodo", "method"},
    "comparacion": {"compare", "comparison", "comparacion", "versus", "vs", "confronto"},
    "autor": {"author", "autor", "autora", "founder", "historia", "creator"},
    "pie": {"footer", "pie", "colophon"},
}
PALABRAS_TIPO = {
    "garantia": ("garantia", "garanzia", "gwarancj", "guarantee", "garantie", "money back", "money-back", "rimbors",
                 "reembols", "zwrot", "refund", "rischio zero", "risco zero", "riesgo cero", "bez ryzyka",
                 "remboursement", "sin riesgo"),
    "faq": ("faq", "preguntas frecuentes", "perguntas frequentes", "domande frequenti", "pytania", "frequently asked",
            "questions frequentes", "haufige fragen", "dudas", "domande"),
    "resenas": ("resena", "opinion", "opinie", "recenzj", "recension", "review", "testimon", "depoimento", "avaliac",
                "bewertung", "erfahrungen", "feedback", "what people say", "dicen", "hanno detto", "mowia",
                "valoraciones", "reali"),
    "para_quien": ("para quien", "para quem", "per chi", "dla kogo", "who is it for", "who is this for", "pour qui",
                   "fur wen", "es para ti", "e per te", "dla ciebie", "this is for", "perfetto per"),
    "bonus": ("bonus", "bono", "dodatek", "dodatki", "prezent", "regalo", "gift", "extras"),
    "precio": ("precio", "preco", "prezzo", "cena", "price", "pricing", "oferta", "offerta", "prix", "preis",
               "angebot", "valore dell", "investimento", "inversion", "inwestycj"),
    "entrega": ("como recibes", "como receber", "come ricevi", "jak otrzym", "jak dostan", "how you get",
                "how it works", "como funciona", "come funziona", "jak to dziala", "pasos", "steps", "passi", "kroki",
                "entrega", "consegna", "dostawa", "receive"),
    "contenido": ("que incluye", "contenido", "contenuto", "cosa troverai", "what's inside", "whats inside",
                  "what you get", "zawartosc", "co zawiera", "co dostaniesz", "modulos", "programa", "temario",
                  "niveles", "livelli", "poziomy", "levels", "dentro", "inside", "guarda", "mira "),
    "problema": ("problema", "problem", "frustra", "dolor", "pain", "trudn", "dificult", "difficolt", "nunca fue",
                 "never was"),
    "solucion": ("solucion", "soluzione", "solution", "metodo", "method", "mecanismo", "rozwiazanie", "metoda"),
    "comparacion": ("versus", " vs ", "compar", "confronto", "porownanie"),
    "autor": ("sobre mi", "about", "autor", "fundad", "chi sono", "o mnie", "historia", "our story", "creator", "quem sou"),
}
DESTINO_D5 = {
    "barra_superior": "copy.barra_superior (informativa; la de lanzamiento solo con fecha real de checkout.precio_programado)",
    "heroe": "copy.S01 + ranura de imagen hero",
    "tira_imagenes": "copy.S04 + ranuras muestra-* (solo con imagen real aprobada o ilustrativa marcada)",
    "resenas": "copy.S08 (solo reseñas reales con compra verificada; sin ellas, el bloque se omite)",
    "selector_niveles": "copy.S06.modulos[] + copy.S06.selector",
    "contenido": "copy.S06",
    "para_quien": "copy.S07",
    "bonus": "copy.S09 + ranuras bono-N",
    "precio": "copy.S11 + checkout.json",
    "garantia": "copy.S10 + oferta.garantia",
    "entrega": "copy.S15",
    "faq": "copy.S12",
    "cta_final": "copy.S13",
    "problema": "copy.S03",
    "solucion": "copy.S05",
    "comparacion": "copy.S16 (solo cifras con fuente y fecha)",
    "autor": "sin sección en D5: solo con identidad real del vendedor",
    "pie": "copy.S14 + páginas legales",
    "flotante": "componente: solo con dato real; nunca avisos de compra inventados",
    "navegacion": "sin equivalente (la landing no lleva menú)",
    "texto_generico": "revisar a mano",
}
FUNCION_ROL = {
    "titular_principal": "Promesa principal de la página (H1): lo primero que se lee.",
    "titular_seccion": "Titular de sección: enmarca el bloque y empuja a seguir leyendo.",
    "titulo_tarjeta": "Título de una tarjeta o ítem repetido (beneficio, nivel, bonus, perfil).",
    "sobretitulo": "Etiqueta corta sobre el titular que sitúa la sección.",
    "lead": "Bajada explicativa del titular.",
    "parrafo": "Texto de apoyo.",
    "microcopy": "Línea breve de reducción de riesgo o aclaración junto a un botón o precio.",
    "etiqueta": "Insignia o etiqueta corta (número de bonus, nivel, «gratis»).",
    "item_lista": "Ítem de una lista (qué incluye, lista de seguridad, desglose).",
    "cta_texto": "Texto del botón de acción; apunta a una ancla de precio o al checkout.",
    "faq_pregunta": "Objeción formulada como pregunta.",
    "faq_respuesta": "Respuesta a una objeción.",
    "precio": "Precio mostrado: dato propio de la oferta, nunca el del referente.",
    "precio_tachado": "Precio de referencia tachado (ancla): exige historial real de 30 días; si no, no se usa (PAL-16).",
    "cifra": "Cifra de producto o de prueba social: se sustituye por un dato propio verificable.",
    "fecha": "Fecha de oferta: solo con fecha real y verificable por código.",
    "cuenta_atras": "Reloj o cuenta atrás: no se reproduce si no es un plazo real (PAL-16).",
    "valoracion": "Estrellas o valoración media: solo con valoración real.",
    "resena_texto": "Texto de reseña: solo reseñas reales con compra verificada.",
    "pie_imagen": "Pie de una imagen.",
    "celda": "Celda de una tabla comparativa.",
    "enlace_legal": "Enlace del pie (legales, contacto): en nuestro caso, páginas reales con identidad del vendedor.",
    "enlace_sin_destino": "Enlace del pie sin destino (#): hueco de confianza del referente; el nuestro lleva páginas reales.",
    "campo_formulario": "Campo de formulario.",
    "enlace": "Enlace de texto.",
    "imagen_heroe": "Mockup o imagen principal del héroe.",
    "imagen_galeria": "Miniatura de la tira «qué hay dentro»: muestra del producto.",
    "imagen_resena": "Imagen de reseña (captura): no se reproduce; sustituye una reseña de texto real.",
    "imagen_bonus": "Portada de un bonus.",
    "imagen_precio": "Imagen de la tarjeta de precio.",
    "avatar": "Foto pequeña de persona (prueba social): no se reproduce.",
    "imagen": "Imagen de contenido.",
    "video": "Video o reproductor incrustado.",
}
PREFIJOS_VARIABLES_PLATAFORMA = ("--wp-", "--wp--", "--e-", "--elementor", "--swiper", "--bs-", "--tw-", "--global-",
                                 "--wc-", "--woocommerce", "--theme-", "--ast-", "--kb-", "--et_", "--fa-", "--w-")
RE_URL_TEXTO = re.compile(r"https?://[^\s\"'<>\\)]{4,300}")


# ── errores ──────────────────────────────────────────────────────────────────
class ErrorAnalisis(Exception):
    codigo = 2


class RedNoPermitida(ErrorAnalisis):
    codigo = 3


class TamanoExcedido(ErrorAnalisis):
    codigo = 4


class RespuestaNoValida(ErrorAnalisis):
    codigo = 5


# ── utilidades de texto ──────────────────────────────────────────────────────
def limpiar(s: Any, maximo: Optional[int] = None) -> str:
    """Quita caracteres de control, marcas bidireccionales y de ancho cero; colapsa espacios; recorta."""
    if s is None:
        return ""
    s = _CTRL.sub(" ", str(s))
    s = " ".join(s.split())
    if maximo is not None and len(s) > maximo:
        s = s[: max(0, maximo - 1)].rstrip() + "…"
    return s


def normalizar(s: str) -> str:
    """Minúsculas y sin acentos, para comparar palabras clave en varios idiomas."""
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def sha16(s: str | bytes) -> str:
    b = s if isinstance(s, bytes) else s.encode("utf-8", "replace")
    return hashlib.sha256(b).hexdigest()[:16]


def con_forma_de_instruccion(texto: str) -> Optional[str]:
    """Devuelve el nombre del patrón si el texto parece una instrucción dirigida a un agente (se trata como dato)."""
    t = normalizar(texto[:4000])
    for i, p in enumerate(PATRONES_INSTRUCCION):
        if p.search(t):
            return f"patron_{i + 1:02d}"
    return None


# ── árbol propio ─────────────────────────────────────────────────────────────
class Nodo:
    __slots__ = ("tag", "attrs", "hijos", "padre", "texto", "idx", "prof")

    def __init__(self, tag: str, attrs: Optional[dict] = None, padre: "Nodo | None" = None, idx: int = 0, prof: int = 0):
        self.tag = tag
        self.attrs = attrs or {}
        self.hijos: list[Nodo] = []
        self.padre = padre
        self.texto = ""
        self.idx = idx
        self.prof = prof

    def attr(self, k: str, d: str = "") -> str:
        return self.attrs.get(k, d)

    def clases(self) -> list[str]:
        return [c[:60] for c in self.attrs.get("class", "").split()[:12]]

    def tokens(self) -> set[str]:
        """Palabras de class e id (separadas por - _ y mayúsculas), en minúsculas."""
        out: set[str] = set()
        for fuente in self.clases() + [self.attrs.get("id", "")[:60]]:
            f = fuente.lower()
            if f:
                out.add(f)
                out.update(p for p in re.split(r"[-_:]+", f) if p)
        return out

    def elementos(self) -> list["Nodo"]:
        return [h for h in self.hijos if h.tag != "#texto"]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Nodo {self.tag} #{self.idx}>"


def _valor_attr(nombre: str, valor: Optional[str]) -> str:
    v = valor if valor is not None else ""
    if v[:5].lower() == "data:":
        return f"data:…[{len(v)}]"
    limite = 4000 if nombre in ("href", "src", "data-src", "srcset", "data-srcset", "style", "content", "action") else 1000
    return v[:limite]


class _Constructor(HTMLParser):
    """Construye un árbol con límites. No ejecuta nada ni interpreta scripts."""

    def __init__(self, max_nodos: int = MAX_NODOS, max_prof: int = MAX_PROFUNDIDAD):
        super().__init__(convert_charrefs=True)
        self.raiz = Nodo("#raiz")
        self.pila: list[Nodo] = [self.raiz]
        self.n = 0
        self.max_nodos = max_nodos
        self.max_prof = max_prof
        self.truncado_nodos = False
        self.prof_truncada = 0
        self.ignorados: Counter = Counter()
        self.comentarios = 0
        self.texto_total = 0

    # -- cierres implícitos mínimos (li, p, dt/dd, tr, td, option)
    def _cierre_implicito(self, tag: str) -> None:
        pila = self.pila
        if tag == "li":
            for i in range(len(pila) - 1, 0, -1):
                t = pila[i].tag
                if t == "li":
                    del pila[i:]
                    break
                if t in ("ul", "ol", "menu", "body", "html", "table", "section", "div"):
                    break
        elif tag in ("dt", "dd"):
            for i in range(len(pila) - 1, 0, -1):
                t = pila[i].tag
                if t in ("dt", "dd"):
                    del pila[i:]
                    break
                if t in ("dl", "body", "html"):
                    break
        elif tag == "tr":
            for i in range(len(pila) - 1, 0, -1):
                t = pila[i].tag
                if t == "tr":
                    del pila[i:]
                    break
                if t in ("table", "tbody", "thead", "tfoot", "body", "html"):
                    break
        elif tag in ("td", "th"):
            for i in range(len(pila) - 1, 0, -1):
                t = pila[i].tag
                if t in ("td", "th"):
                    del pila[i:]
                    break
                if t in ("tr", "table", "body", "html"):
                    break
        elif tag == "option":
            if pila[-1].tag == "option":
                pila.pop()
        if tag in CIERRAN_P and len(pila) > 1 and pila[-1].tag == "p":
            pila.pop()

    def _abrir(self, tag: str, attrs: list, vacio: bool) -> None:
        if self.n >= self.max_nodos:
            self.truncado_nodos = True
            return
        tag = tag.lower()[:30]
        self._cierre_implicito(tag)
        d: dict[str, str] = {}
        for k, v in attrs[:MAX_ATRIBUTOS]:
            k = k.lower()[:60]
            if k not in d:
                d[k] = _valor_attr(k, v)
        padre = self.pila[-1]
        nodo = Nodo(tag, d, padre, self.n, len(self.pila))
        self.n += 1
        padre.hijos.append(nodo)
        if vacio or tag in VOID:
            return
        if len(self.pila) >= self.max_prof:
            self.prof_truncada += 1
            self.ignorados[tag] += 1
        else:
            self.pila.append(nodo)

    def handle_starttag(self, tag, attrs):  # noqa: N802
        self._abrir(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):  # noqa: N802
        self._abrir(tag, attrs, True)

    def handle_endtag(self, tag):  # noqa: N802
        tag = tag.lower()[:30]
        if tag in VOID:
            return
        if self.ignorados.get(tag):
            self.ignorados[tag] -= 1
            return
        for i in range(len(self.pila) - 1, 0, -1):
            if self.pila[i].tag == tag:
                del self.pila[i:]
                return

    def handle_data(self, data):
        cur = self.pila[-1]
        if cur.tag in ("script", "style"):
            tope = MAX_SCRIPT_TEXTO if cur.tag == "script" else MAX_STYLE_TEXTO
            if len(cur.texto) < tope:
                cur.texto += data[: tope - len(cur.texto)]
            return
        if not data or self.texto_total > MAX_TEXTO_TOTAL:
            return
        ultimo = cur.hijos[-1] if cur.hijos else None
        if ultimo is not None and ultimo.tag == "#texto":
            ultimo.texto += data
            self.texto_total += len(data)
            return
        if not data.strip():
            if ultimo is None or ultimo.tag in BLOQUE:
                return
            data = " "
        if self.n >= self.max_nodos:
            self.truncado_nodos = True
            return
        t = Nodo("#texto", None, cur, self.n, len(self.pila))
        t.texto = data
        self.n += 1
        self.texto_total += len(data)
        cur.hijos.append(t)

    def handle_comment(self, data):
        self.comentarios += 1


def parsear(html_texto: str, max_nodos: int = MAX_NODOS, max_segundos: float = MAX_SEGUNDOS_PARSEO) -> _Constructor:
    """Parsea en trozos de 32 KB con un tiempo máximo. Un fallo del parser deja el árbol parcial, no aborta."""
    c = _Constructor(max_nodos=max_nodos)
    limite = time.monotonic() + max_segundos
    error = None
    try:
        for i in range(0, len(html_texto), CHUNK):
            c.feed(html_texto[i:i + CHUNK])
            if time.monotonic() > limite:
                raise ErrorAnalisis(f"el análisis superó {max_segundos:.0f} s (HTML patológico)")
        c.close()
    except ErrorAnalisis:
        raise
    except Exception as e:  # el parser no debe tumbar el análisis
        error = type(e).__name__
    c.error_parser = error  # type: ignore[attr-defined]
    return c


def recorrer(nodo: Nodo, incluir_texto: bool = False) -> Iterator[Nodo]:
    """Preorden iterativo (sin recursión)."""
    pila = [nodo]
    while pila:
        n = pila.pop()
        if incluir_texto or n.tag != "#texto":
            yield n
        pila.extend(reversed(n.hijos))


def descendientes_hasta(nodo: Nodo, prof: int) -> Iterator[Nodo]:
    pila = [(nodo, 0)]
    while pila:
        n, p = pila.pop()
        if n.tag != "#texto":
            yield n
        if p < prof:
            pila.extend((h, p + 1) for h in reversed(n.hijos))


def buscar(nodo: Nodo, tag: str) -> Optional[Nodo]:
    for n in recorrer(nodo):
        if n.tag == tag:
            return n
    return None


def ancestros(nodo: Nodo) -> Iterator[Nodo]:
    n = nodo.padre
    while n is not None:
        yield n
        n = n.padre


def dentro_de(nodo: Nodo, tags: set[str]) -> bool:
    return any(a.tag in tags for a in ancestros(nodo))


def texto_de(nodo: Nodo, maximo: int = 400, excluir: Optional[set[int]] = None) -> str:
    """Texto visible concatenado (sin script/style/svg…); ``excluir`` = ids de nodos cuyo subárbol se salta."""
    partes: list[str] = []
    total = 0
    pila = [nodo]
    while pila and total < maximo * 4:
        n = pila.pop()
        if n.tag == "#texto":
            partes.append(n.texto)
            total += len(n.texto)
            continue
        if n.tag in NO_TEXTO or (excluir and n.idx in excluir and n is not nodo):
            continue
        pila.extend(reversed(n.hijos))
    return limpiar(" ".join(partes), maximo)


def n_palabras(s: str) -> int:
    return len(s.split())


def firma(n: Nodo) -> str:
    return n.tag + "".join("." + c for c in n.clases()[:3])


def _ident(s: str, n: int = 40) -> str:
    """Nombre de clase o id apto para un JSON de salida: solo [\\w-:.], recortado."""
    return re.sub(r"[^\w\-:.]", "?", s)[:n]


def etiqueta_corta(n: Nodo) -> str:
    """tag#id.clase.clase (hasta 2 clases). Las clases e ids vienen de la página: se filtran y, si juntas parecen una instrucción, se omiten."""
    crudo = " ".join([n.attrs.get("id", "")] + n.clases()[:6])
    if con_forma_de_instruccion(crudo):
        return n.tag + "#[omitido]"
    s = n.tag
    if n.attrs.get("id"):
        s += "#" + _ident(n.attrs["id"], 30)
    for c in n.clases()[:2]:
        s += "." + _ident(c, 30)
    return s


def blindar(o: Any, cuenta: Optional[list] = None) -> Any:
    """Red de seguridad de salida: ninguna cadena derivada de la página sale con forma de instrucción o caracteres de control."""
    cuenta = cuenta if cuenta is not None else [0]
    if isinstance(o, str):
        limpio = _CTRL.sub(" ", o)
        if len(limpio) > 12 and con_forma_de_instruccion(limpio):
            cuenta[0] += 1
            return "[omitido: forma de instrucción]"
        return limpio
    if isinstance(o, list):
        return [blindar(x, cuenta) for x in o]
    if isinstance(o, dict):
        return {blindar(k, cuenta) if isinstance(k, str) else k: blindar(v, cuenta) for k, v in o.items()}
    return o


def oculto_inline(n: Nodo) -> bool:
    """Oculto por el atributo ``hidden`` o por style en línea (no por clases: eso requiere el CSS final)."""
    estilo = n.attrs.get("style", "").replace(" ", "").lower()
    if "hidden" in n.attrs:
        return True
    return any(x in estilo for x in ("display:none", "visibility:hidden", "font-size:0;", "opacity:0;", "height:0;overflow:hidden"))


# ── CSS ──────────────────────────────────────────────────────────────────────
def _quitar_comentarios_y_datos(css: str) -> str:
    """Quita /* … */ y el cuerpo de url(data:…) sin usar expresiones regulares con retroceso."""
    out: list[str] = []
    i, n = 0, len(css)
    while i < n:
        a = css.find("/*", i)
        if a < 0:
            out.append(css[i:])
            break
        out.append(css[i:a])
        b = css.find("*/", a + 2)
        if b < 0:
            break
        i = b + 2
    css = "".join(out)
    out = []
    i = 0
    while True:
        a = css.find("url(", i)
        if a < 0:
            out.append(css[i:])
            break
        out.append(css[i:a + 4])
        j = a + 4
        while j < n and css[j] in " \t\n\r\"'":
            j += 1
        if css[j:j + 5].lower() == "data:":
            fin = css.find(")", j)
            out.append("data:…)")
            i = (fin + 1) if fin >= 0 else len(css)
        else:
            i = a + 4
    return "".join(out)


def _dividir_top(texto: str, sep: str) -> list[str]:
    partes, cur, par, cor, q = [], [], 0, 0, None
    for ch in texto:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch == "(":
            par += 1
        elif ch == ")":
            par = max(0, par - 1)
        elif ch == "[":
            cor += 1
        elif ch == "]":
            cor = max(0, cor - 1)
        elif ch == sep and par == 0 and cor == 0:
            partes.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    partes.append("".join(cur))
    return partes


def parsear_declaraciones(cuerpo: str) -> dict[str, str]:
    d: dict[str, str] = {}
    for dec in _dividir_top(cuerpo, ";")[:400]:
        if ":" not in dec:
            continue
        k, v = dec.split(":", 1)
        k = k.strip().lower()[:60]
        v = re.sub(r"\s*!important\s*$", "", v.strip(), flags=re.I)[:300]
        if k and v:
            d[k] = v
    return d


def _fin_bloque(css: str, i: int) -> int:
    """Índice posterior a la llave que cierra el bloque cuyo cuerpo empieza en ``i`` (con anidación y cadenas)."""
    n, prof, q = len(css), 1, None
    while i < n:
        ch = css[i]
        if q:
            if ch == "\\":
                i += 1
            elif ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "{":
            prof += 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                return i + 1
        i += 1
    return n


class Regla:
    __slots__ = ("cond", "selector", "decl", "origen", "partes")

    def __init__(self, cond: tuple, selector: str, decl: dict, origen: str):
        self.cond = cond
        self.selector = selector
        self.decl = decl
        self.origen = origen
        self.partes = parsear_selector(selector)


_COMP = re.compile(r"^([a-zA-Z][\w-]*|\*)?((?:[.#][\w-]+)*)$")


def parsear_selector(sel: str) -> list[tuple]:
    """Por cada selector de la lista: (tag, id, clases, simple, con_pseudo). Solo se usa el último compuesto."""
    out = []
    for p in _dividir_top(sel, ","):
        p = p.strip()
        if not p or len(p) > 300:
            continue
        simple = not re.search(r"[\s>+~]", p)
        ultimo = re.split(r"[\s>+~]+", p)[-1]
        pseudo = ":" in ultimo
        base = ultimo.split(":")[0].split("[")[0]
        m = _COMP.match(base)
        if not m:
            continue
        tag = (m.group(1) or "").lower()
        tag = "" if tag == "*" else tag
        idv, clases = "", []
        for tok in re.findall(r"[.#][\w-]+", m.group(2) or ""):
            if tok[0] == "#":
                idv = tok[1:]
            else:
                clases.append(tok[1:])
        out.append((tag, idv, tuple(clases), simple and "[" not in ultimo, pseudo))
    return out


def leer_bloques_css(css: str, origen: str, reglas: list, estado: dict, cond: tuple = (), nivel: int = 0, i: int = 0) -> int:
    n = len(css)
    while i < n:
        j, par, q = i, 0, None
        while j < n:
            c = css[j]
            if q:
                if c == "\\":
                    j += 1
                elif c == q:
                    q = None
            elif c in "\"'":
                q = c
            elif c == "(":
                par += 1
            elif c == ")":
                par = max(0, par - 1)
            elif par == 0 and c in "{};":
                break
            j += 1
        if j >= n:
            break
        c = css[j]
        if c == "}":
            return j + 1
        prelude = css[i:j].strip()
        if c == ";":
            if prelude.lower().startswith("@import"):
                estado["imports"].append(prelude[:300])
            i = j + 1
            continue
        if len(reglas) >= MAX_REGLAS_CSS:
            estado["truncado"] = True
            return n
        nombre = prelude.split("(")[0].split()[0].lower() if prelude.startswith("@") and prelude.split() else ""
        if nombre in ("@media", "@supports", "@layer", "@container", "@document") and nivel < 6:
            i = leer_bloques_css(css, origen, reglas, estado, cond + (limpiar(prelude, 120),), nivel + 1, j + 1)
            continue
        k = _fin_bloque(css, j + 1)
        cuerpo = css[j + 1:k - 1]
        if nombre == "@font-face":
            estado["font_faces"].append(parsear_declaraciones(cuerpo))
        elif nombre.endswith("keyframes"):
            estado["keyframes"] += 1
        elif nombre.startswith("@"):
            pass
        else:
            reglas.append(Regla(cond, prelude, parsear_declaraciones(cuerpo), origen))
        i = k
    return n


def color_a_hex(valor: str) -> Optional[str]:
    """Primer color del valor, normalizado a #rrggbb (sin alfa). None si no hay."""
    v = valor.strip()
    m = ESTILO_HEX.search(v)
    cand: list[tuple[int, str]] = []
    if m:
        h = m.group(0)[1:].lower()
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        cand.append((m.start(), "#" + h[:6]))
    m2 = ESTILO_RGB.search(v)
    if m2:
        try:
            comp = []
            for g in m2.groups():
                comp.append(round(float(g[:-1]) * 2.55) if g.endswith("%") else round(float(g)))
            cand.append((m2.start(), "#%02x%02x%02x" % tuple(max(0, min(255, x)) for x in comp)))
        except ValueError:
            pass
    m3 = ESTILO_HSL.search(v)
    if m3:
        try:
            import colorsys
            hh, ss, ll = float(m3.group(1)) / 360.0, float(m3.group(2)) / 100.0, float(m3.group(3)) / 100.0
            r, g, b = colorsys.hls_to_rgb(hh % 1.0, ll, ss)
            cand.append((m3.start(), "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))))
        except Exception:
            pass
    if not cand:
        return None
    cand.sort()
    return cand[0][1]


def todos_los_colores(valor: str) -> list[str]:
    out = []
    for m in ESTILO_HEX.finditer(valor):
        h = m.group(0)[1:].lower()
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        out.append("#" + h[:6])
    for m in ESTILO_RGB.finditer(valor):
        h = color_a_hex(m.group(0))
        if h:
            out.append(h)
    for m in ESTILO_HSL.finditer(valor):
        h = color_a_hex(m.group(0))
        if h:
            out.append(h)
    return out


def luminancia(hexc: str) -> float:
    r, g, b = (int(hexc[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class ContextoCSS:
    """Reglas de todas las hojas que se pudieron leer y búsquedas aproximadas sobre ellas."""

    def __init__(self, hojas: list[tuple[str, str]]):
        self.reglas: list[Regla] = []
        self.estado: dict = {"imports": [], "font_faces": [], "keyframes": 0, "truncado": False}
        self.origenes = []
        for origen, css in hojas:
            limpio = _quitar_comentarios_y_datos(css)
            antes = len(self.reglas)
            leer_bloques_css(limpio, origen, self.reglas, self.estado)
            self.origenes.append({"origen": origen, "bytes": len(css), "reglas": len(self.reglas) - antes})
        self.variables: dict[str, str] = {}
        for r in self.reglas:
            if not r.cond and any(p[0] in ("", "html", "body") and not p[2] and not p[1] and p[4] for p in r.partes) \
                    or ":root" in r.selector or r.selector.strip() in ("html", "body"):
                for k, v in r.decl.items():
                    if k.startswith("--"):
                        self.variables[k] = v
        self.por_clase: dict[str, list[int]] = {}
        self.por_tag: dict[str, list[int]] = {}
        self.por_id: dict[str, list[int]] = {}
        for i, r in enumerate(self.reglas):
            if r.cond:
                continue
            for tag, idv, clases, simple, pseudo in r.partes:
                if not simple or pseudo:
                    continue
                if idv:
                    self.por_id.setdefault(idv, []).append(i)
                elif clases:
                    self.por_clase.setdefault(clases[0], []).append(i)
                elif tag:
                    self.por_tag.setdefault(tag, []).append(i)

    def resolver(self, valor: str, prof: int = 0) -> str:
        if "var(" not in valor or prof > 3:
            return valor

        def sub(m: re.Match) -> str:
            nombre = m.group(1).strip()
            defecto = (m.group(2) or "").strip(", ")
            return self.variables.get(nombre, defecto or m.group(0))
        res = re.sub(r"var\(\s*(--[\w-]+)\s*(,[^)]*)?\)", sub, valor)
        return self.resolver(res, prof + 1) if res != valor else res

    def valor(self, n: Nodo, prop: str) -> Optional[str]:
        """Valor efectivo aproximado de ``prop`` (reglas sin condición y sin combinadores; el style inline gana)."""
        mejor: Optional[tuple] = None
        cand: set[int] = set()
        for c in n.clases():
            cand.update(self.por_clase.get(c, ()))
        cand.update(self.por_tag.get(n.tag, ()))
        if n.attrs.get("id"):
            cand.update(self.por_id.get(n.attrs["id"], ()))
        cls = set(n.clases())
        for i in cand:
            r = self.reglas[i]
            if prop not in r.decl and not (prop == "background" and "background-color" in r.decl):
                continue
            for tag, idv, clases, simple, pseudo in r.partes:
                if not simple or pseudo:
                    continue
                if tag and tag != n.tag:
                    continue
                if idv and idv != n.attrs.get("id"):
                    continue
                if clases and not set(clases) <= cls:
                    continue
                espec = (1 if idv else 0, len(clases), 1 if tag else 0, i)
                v = r.decl.get(prop) or r.decl.get("background-color")
                if mejor is None or espec > mejor[0]:
                    mejor = (espec, v)
        inline = parsear_declaraciones(n.attrs.get("style", ""))
        if prop in inline:
            return self.resolver(inline[prop])
        if prop == "background" and "background-color" in inline:
            return self.resolver(inline["background-color"])
        return self.resolver(mejor[1]) if mejor else None

    def reglas_con(self, prop: str, pred: Callable[[str], bool]) -> Iterator[Regla]:
        for r in self.reglas:
            v = r.decl.get(prop)
            if v is not None and pred(v.lower()):
                yield r


class IndiceDOM:
    def __init__(self, raiz: Nodo):
        self.por_clase: dict[str, list[Nodo]] = {}
        self.por_id: dict[str, list[Nodo]] = {}
        self.por_tag: dict[str, list[Nodo]] = {}
        for n in recorrer(raiz):
            self.por_tag.setdefault(n.tag, []).append(n)
            if n.attrs.get("id"):
                self.por_id.setdefault(n.attrs["id"], []).append(n)
            for c in n.clases():
                self.por_clase.setdefault(c, []).append(n)

    def coinciden(self, partes: list[tuple], con_pseudo: bool = False) -> Iterator[Nodo]:
        for tag, idv, clases, _simple, pseudo in partes:
            if pseudo and not con_pseudo:
                continue
            if idv:
                base = self.por_id.get(idv, [])
            elif clases:
                base = self.por_clase.get(clases[0], [])
            elif tag:
                base = self.por_tag.get(tag, [])
            else:
                continue
            for n in base[:2000]:
                if tag and n.tag != tag:
                    continue
                if clases and not set(clases) <= set(n.clases()):
                    continue
                yield n


# ── URL, destinos y hosts ────────────────────────────────────────────────────
def host_de(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url.strip()).hostname or "").lower()
    except ValueError:
        return ""


def sufijo_en(host: str, tabla: dict) -> Optional[str]:
    h = host.lower()
    for clave in tabla:
        if h == clave or h.endswith("." + clave):
            return clave
    return None


def forma_url(url: str) -> dict:
    """Plataforma, host, forma de la ruta (segmentos con pinta de id como {id}) y NOMBRES de parámetros. Sin ids ni valores."""
    try:
        u = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return {"host": "", "ruta_forma": "", "parametros": []}
    segs = []
    for s in u.path.split("/"):
        if re.fullmatch(r"[A-Za-z0-9_-]{8,}", s) and (re.search(r"\d", s) and re.search(r"[A-Za-z]", s) or re.fullmatch(r"\d{4,}", s)):
            segs.append("{id}")
        else:
            segs.append(limpiar(s, 40))
    params = sorted({limpiar(k, 30) for k, _ in urllib.parse.parse_qsl(u.query, keep_blank_values=True)[:20]})
    return {"host": (u.hostname or "").lower(), "ruta_forma": "/".join(segs)[:120], "parametros": params}


def clasificar_destino(href: str, host_propio: str) -> dict:
    h = (href or "").strip()
    if not h or h == "#":
        return {"tipo": "sin_destino"}
    if h.startswith("#"):
        return {"tipo": "ancla_interna", "ancla": limpiar(h[1:], 40)}
    bajo = h.lower()
    if bajo.startswith("javascript:"):
        return {"tipo": "javascript"}
    if bajo.startswith(("mailto:", "tel:", "sms:")):
        return {"tipo": "contacto"}
    if bajo.startswith(("http://", "https://", "//")):
        f = forma_url(h if not bajo.startswith("//") else "https:" + h)
        host = f["host"]
        plat = sufijo_en(host, PLATAFORMAS_CHECKOUT)
        if host in ("wa.me", "api.whatsapp.com") or host.endswith(".whatsapp.com"):
            return {"tipo": "contacto", "host": host}
        if plat:
            return {"tipo": "checkout_externo", "plataforma": PLATAFORMAS_CHECKOUT[plat], **f}
        propio = bool(host_propio) and (host == host_propio or host.endswith("." + host_propio) or host_propio.endswith("." + host))
        if propio and RUTA_CHECKOUT.search(f["ruta_forma"] + "/"):
            return {"tipo": "checkout_interno", **f}
        return {"tipo": "interno" if propio else "externo", **f}
    f = forma_url(h)
    if RUTA_CHECKOUT.search(f["ruta_forma"] + "/"):
        return {"tipo": "checkout_interno", "ruta_forma": f["ruta_forma"], "parametros": f["parametros"]}
    return {"tipo": "interno", "ruta_forma": f["ruta_forma"], "parametros": f["parametros"]}


def validar_url(url: str, permitir_privadas: bool = False,
                resolver: Optional[Callable[[str], list[str]]] = None) -> urllib.parse.SplitResult:
    """Rechaza esquemas no web, credenciales, puertos raros y destinos privados/locales/reservados."""
    try:
        u = urllib.parse.urlsplit(url.strip())
    except ValueError as e:
        raise RedNoPermitida(f"URL inválida: {e}") from e
    if u.scheme not in ("http", "https"):
        raise RedNoPermitida(f"esquema no permitido: {u.scheme or '(vacío)'}")
    if u.username or u.password:
        raise RedNoPermitida("la URL lleva credenciales")
    host = (u.hostname or "").lower()
    if not host:
        raise RedNoPermitida("la URL no tiene host")
    puerto = u.port or (443 if u.scheme == "https" else 80)
    if puerto not in PUERTOS_OK:
        raise RedNoPermitida(f"puerto no permitido: {puerto}")
    if not permitir_privadas:
        try:
            ips = [host] if _es_ip(host) else (resolver or _resolver_dns)(host)
        except OSError as e:
            raise RedNoPermitida(f"no se pudo resolver {host}: {e}") from e
        for ip in ips:
            a = ipaddress.ip_address(ip.split("%")[0])
            if a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified:
                raise RedNoPermitida(f"destino no público ({ip})")
    return u


def _es_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]").split("%")[0])
        return True
    except ValueError:
        return False


def _resolver_dns(host: str) -> list[str]:
    return sorted({ai[4][0] for ai in socket.getaddrinfo(host, None)})


class _RedireccionSegura(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECCIONES

    def __init__(self, permitir_privadas: bool = False):
        self.permitir_privadas = permitir_privadas

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validar_url(urllib.parse.urljoin(req.full_url, newurl), self.permitir_privadas)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _abrir_real(req: urllib.request.Request, timeout: float, permitir_privadas: bool):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RedireccionSegura(permitir_privadas))
    return opener.open(req, timeout=timeout)


def leer_limitado(fp: Any, max_bytes: int) -> bytes:
    """Lee a lo sumo ``max_bytes``; si hay más, es un error (no un recorte)."""
    datos = fp.read(max_bytes + 1)
    if len(datos) > max_bytes:
        raise TamanoExcedido(f"el documento supera {max_bytes} bytes")
    return datos


def descargar(url: str, *, max_bytes: int = MAX_BYTES_DEFECTO, timeout: float = TIMEOUT_DEFECTO,
              abrir: Optional[Callable[..., Any]] = None, permitir_privadas: bool = False,
              comprobar_robots: bool = True, tipos_ok: tuple = ("text/html", "application/xhtml+xml"),
              resolver: Optional[Callable[[str], list[str]]] = None) -> tuple[bytes, dict]:
    """Descarga una página con todos los frenos. ``abrir`` es inyectable para probar sin red."""
    u = validar_url(url, permitir_privadas, resolver)
    abrir = abrir or (lambda req, t: _abrir_real(req, t, permitir_privadas))
    if comprobar_robots:
        rp_url = f"{u.scheme}://{u.netloc}/robots.txt"
        try:
            with abrir(_pedido(rp_url), timeout) as r:
                estado = getattr(r, "status", None) or r.getcode()
                cuerpo = r.read(MAX_ROBOTS_BYTES + 1)[:MAX_ROBOTS_BYTES]
            lineas = cuerpo.decode("utf-8", "replace").splitlines() if estado == 200 else None
            if estado in (401, 403) or estado >= 500:
                raise RedNoPermitida(f"robots.txt respondió {estado}: se trata como prohibido")
        except urllib.error.HTTPError as e:
            lineas = None
            codigo_http = e.code
            e.close()
            if codigo_http in (401, 403) or codigo_http >= 500:
                raise RedNoPermitida(f"robots.txt respondió {codigo_http}: se trata como prohibido") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RedNoPermitida(f"no se pudo leer robots.txt ({type(e).__name__}); no se asume permiso") from e
        if lineas is not None:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(lineas)
            if not rp.can_fetch(UA_ROBOTS, url):
                raise RedNoPermitida("robots.txt no permite esta ruta: no se esquiva; guarda el HTML con el navegador y usa el modo archivo")
    try:
        with abrir(_pedido(url), timeout) as r:
            estado = getattr(r, "status", None) or r.getcode()
            cab = r.headers
            if estado != 200:
                raise RespuestaNoValida(f"estado HTTP {estado}")
            codif = (cab.get("Content-Encoding") or "identity").lower()
            if codif not in ("identity", ""):
                raise RespuestaNoValida(f"el servidor comprimió la respuesta ({codif}); no se descomprime")
            ctype = (cab.get("Content-Type") or "text/html").lower()
            if not any(t in ctype for t in tipos_ok):
                raise RespuestaNoValida(f"tipo de contenido no HTML: {ctype.split(';')[0]}")
            cl = cab.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > max_bytes:
                raise TamanoExcedido(f"Content-Length {cl} supera {max_bytes} bytes")
            datos = leer_limitado(r, max_bytes)
            final = getattr(r, "geturl", lambda: url)()
    except urllib.error.HTTPError as e:
        codigo_http = e.code
        e.close()
        if codigo_http in (403, 429):
            raise RedNoPermitida(f"HTTP {codigo_http}: bloqueo del sitio; no se esquiva (usa el modo archivo)") from None
        raise RespuestaNoValida(f"estado HTTP {codigo_http}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RespuestaNoValida(f"fallo de red: {type(e).__name__}") from e
    return datos, {"url_final": final, "content_type": ctype, "estado": estado}


def _pedido(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                                                "Accept-Encoding": "identity"}, method="GET")


def decodificar(datos: bytes, content_type: str = "") -> tuple[str, str]:
    """Texto y nombre de la codificación (BOM, cabecera, <meta charset> o utf-8 con reemplazo)."""
    if datos.startswith(b"\xef\xbb\xbf"):
        return datos[3:].decode("utf-8", "replace"), "utf-8"
    if datos[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return datos.decode("utf-16", "replace"), "utf-16"
    cand = []
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        cand.append(m.group(1))
    m = re.search(rb"<meta[^>]{0,200}charset=[\"']?([\w-]+)", datos[:4096], re.I)
    if m:
        cand.append(m.group(1).decode("ascii", "ignore"))
    for c in cand + ["utf-8"]:
        try:
            import codecs
            codecs.lookup(c)
            return datos.decode(c, "replace"), c.lower()
        except (LookupError, ValueError):
            continue
    return datos.decode("utf-8", "replace"), "utf-8"  # pragma: no cover


# ── análisis ─────────────────────────────────────────────────────────────────
def es_boton_cta(n: Nodo, host_propio: str) -> Optional[dict]:
    """Si el nodo es una llamada a la acción, devuelve su destino clasificado; si no, None."""
    if n.tag not in ("a", "button", "input") and n.attrs.get("role") != "button":
        return None
    if n.tag == "input" and n.attrs.get("type", "").lower() not in ("submit", "button", "image"):
        return None
    toks = n.tokens()
    if n.attrs.get("aria-expanded") is not None or n.attrs.get("aria-pressed") is not None or "data-tab" in n.attrs \
            or n.attrs.get("role") in ("tab", "menuitem", "switch") or toks & TOKENS_NO_CTA \
            or dentro_de(n, {"nav", "summary"}):
        return None
    href = n.attrs.get("href", n.attrs.get("formaction", n.attrs.get("data-href", "")))
    destino = clasificar_destino(href, host_propio) if n.tag == "a" or href else {"tipo": "formulario"}
    if n.tag == "button" and not href:
        destino = {"tipo": "boton_sin_href"}
    texto = texto_de(n, 120) or limpiar(n.attrs.get("value", "") or n.attrs.get("aria-label", ""), 120)
    es_tok = bool(toks & TOKENS_CTA) or any(t.startswith(("btn", "button", "cta")) for t in toks)
    es_checkout = destino["tipo"] in ("checkout_externo", "checkout_interno")
    nt = normalizar(texto)
    verbo = bool(nt) and len(texto) <= 50 and any(nt.startswith(v) for v in VERBOS_CTA) \
        and n.padre is not None and n.padre.tag not in ("p", "li") and not dentro_de(n, {"footer", "nav"})
    if not (es_tok or es_checkout or verbo or n.tag == "input"):
        return None
    if dentro_de(n, {"footer"}) and not (es_tok or es_checkout):
        return None
    if not texto and n.tag == "a":
        return None
    return {"texto": texto, "destino": destino, "tokens_clase": sorted(t for t in toks if t in TOKENS_CTA)[:3]}


def _firmas_hermanos(n: Nodo) -> Counter:
    return Counter(firma(h) for h in n.elementos() if h.tag not in IGNORAR_TOP)


def _tiene_contenido(n: Nodo) -> bool:
    if n.tag in IGNORAR_TOP or (n.tag == "input" and n.attrs.get("type", "").lower() == "hidden"):
        return False
    for d in descendientes_hasta(n, 6):
        if d.tag == "input" and d.attrs.get("type", "").lower() == "hidden":
            continue
        if d.tag in ("img", "picture", "video", "input", "button", "a", "h1", "h2", "h3", "h4", "ul", "ol", "table", "svg"):
            return True
    return len(texto_de(n, 80)) >= 20


def _contiene_semantico(n: Nodo, prof: int = 7) -> bool:
    return any(d is not n and d.tag in SEMANTICOS for d in descendientes_hasta(n, prof))


def _significativos(n: Nodo) -> list[Nodo]:
    return [h for h in n.elementos() if h.tag not in IGNORAR_TOP and _tiene_contenido(h)]


def hallar_bloques(cuerpo: Nodo, fijos: Optional[set[int]] = None) -> list[Nodo]:
    """Bloques de primer nivel de la página en orden de documento (secciones, barras, pie, flotantes).
    ``fijos`` = ids de nodos con posición fija o pegajosa: son bloques en sí mismos, no envoltorios."""
    bloques: list[Nodo] = []
    fijos = fijos or set()

    def es_envoltorio(h: Nodo) -> bool:
        if h.tag not in CONTENEDORES or h.idx in fijos:
            return False
        if h.tag == "main":
            return True
        hijos = _significativos(h)
        if len(hijos) == 1 and hijos[0].tag in CONTENEDORES | SEMANTICOS:
            return True
        if _contiene_semantico(h):
            return True
        toks = h.tokens()
        if len(hijos) >= 3 and (toks & ENVOLTORIO_TOKENS) and all(
                (n_palabras(texto_de(c, 60)) >= 3 or any(d.tag == "img" for d in descendientes_hasta(c, 4))) for c in hijos):
            return True
        return False

    def visitar(nodo: Nodo, prof: int) -> None:
        for h in nodo.hijos:
            if h.tag == "#texto" or h.tag in IGNORAR_TOP:
                continue
            if h.idx in fijos:
                bloques.append(h)
                continue
            if h.tag in SEMANTICOS:
                if h.tag in ("header", "article") and prof < 10 and _contiene_semantico(h, 4) and len(_significativos(h)) > 1:
                    visitar(h, prof + 1)
                else:
                    bloques.append(h)
                continue
            if prof < 12 and es_envoltorio(h):
                visitar(h, prof + 1)
                continue
            if _tiene_contenido(h):
                bloques.append(h)

    visitar(cuerpo, 0)
    return bloques


def resumir_dom(bloque: Nodo, prof_max: int = 4) -> list[str]:
    """Esquema indentado del DOM del bloque (hasta 4 niveles) con los hermanos iguales colapsados en «×N»."""
    lineas: list[str] = []

    def rec(n: Nodo, nivel: int) -> None:
        if len(lineas) >= MAX_LINEAS_DOM:
            return
        grupos: list[list[Nodo]] = []
        for h in n.elementos():
            if h.tag in IGNORAR_TOP and h.tag != "svg":
                continue
            if grupos and firma(grupos[-1][0]) == firma(h):
                grupos[-1].append(h)
            else:
                grupos.append([h])
        for g in grupos:
            if len(lineas) >= MAX_LINEAS_DOM:
                lineas.append("  " * nivel + "…")
                return
            lineas.append("  " * nivel + etiqueta_corta(g[0]) + (f" ×{len(g)}" if len(g) > 1 else ""))
            if nivel + 1 < prof_max:
                rec(g[0], nivel + 1)

    lineas.append(etiqueta_corta(bloque))
    rec(bloque, 1)
    return lineas


class Analizador:
    """Reúne todo el análisis de un documento ya parseado."""

    def __init__(self, texto_html: str, *, host_propio: str = "", css_externos: Optional[list[tuple[str, str]]] = None,
                 con_muestras: bool = True, fuente: Optional[dict] = None, ahora: Optional[str] = None):
        self.texto_html = texto_html
        self.fuente = fuente or {}
        self.ahora = ahora or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.con_muestras = con_muestras
        self.p = parsear(texto_html)
        self.raiz = self.p.raiz
        self.html = buscar(self.raiz, "html") or self.raiz
        self.head = buscar(self.raiz, "head")
        self.cuerpo = buscar(self.raiz, "body") or self.raiz
        self.alertas: list[dict] = []
        self.hojas = self._recoger_css(css_externos or [])
        self.css = ContextoCSS(self.hojas)
        self.dom = IndiceDOM(self.raiz)
        self.host_propio, self.origen_host = self._host_propio(host_propio)
        self.ctas_nodos: dict[int, dict] = {}
        for n in recorrer(self.cuerpo):
            if len(self.ctas_nodos) >= MAX_CTAS * 3:
                break
            if dentro_de(n, {"noscript", "template"}):
                continue
            c = es_boton_cta(n, self.host_propio)
            if c:
                self.ctas_nodos[n.idx] = c
        self._sospechas_vistas: set[tuple] = set()
        self._fijos = self._elementos_fijos()
        self.bloques = hallar_bloques(self.cuerpo, set(self._fijos))

    # -- fuentes de CSS
    def _recoger_css(self, externos: list[tuple[str, str]]) -> list[tuple[str, str]]:
        hojas: list[tuple[str, str]] = []
        for i, n in enumerate(s for s in recorrer(self.raiz) if s.tag == "style"):
            if n.texto.strip():
                hojas.append((f"style_{i + 1}", n.texto))
        inline = []
        for n in recorrer(self.raiz):
            st = n.attrs.get("style")
            if st:
                inline.append(f"x{{{st}}}")
                if len(inline) > 3000:
                    break
        if inline:
            hojas.append(("style_inline", "\n".join(inline)))
        hojas.extend(externos)
        return hojas

    def _host_propio(self, dado: str) -> tuple[str, str]:
        if dado:
            return dado.lower(), "argumento_o_url"
        for n in recorrer(self.raiz):
            if n.tag == "link" and n.attrs.get("rel", "").lower() == "canonical" and n.attrs.get("href"):
                h = host_de(n.attrs["href"])
                if h:
                    return h, "canonical"
            if n.tag == "meta" and n.attrs.get("property") == "og:url" and n.attrs.get("content"):
                h = host_de(n.attrs["content"])
                if h:
                    return h, "og:url"
        c: Counter = Counter()
        for n in recorrer(self.raiz):
            for k in ("src", "data-src", "href"):
                v = n.attrs.get(k, "")
                if v.startswith(("http://", "https://")) and n.tag in ("img", "link", "a", "script", "source"):
                    h = host_de(v)
                    if h and not sufijo_en(h, TERCEROS):
                        c[h] += 1
        if c:
            return c.most_common(1)[0][0], "inferido_por_frecuencia"
        return "", "desconocido"

    # -- alertas
    def alerta(self, codigo: str, nota: str, bloque: Optional[int] = None, selector: str = "", **extra) -> None:
        clave = (codigo, bloque, selector)
        if clave in self._sospechas_vistas or len(self.alertas) >= 80:
            return
        self._sospechas_vistas.add(clave)
        self.alertas.append({"codigo": codigo, "bloque": bloque, "selector": selector, "nota": nota, **extra})

    # -- elementos fijos
    def _elementos_fijos(self) -> dict[int, dict]:
        fijos: dict[int, dict] = {}

        def tipo_de(n: Nodo) -> str:
            t = n.tokens()
            if t & {"toast", "floaty", "notif", "notification", "recent", "purchase", "proof", "social"} or \
                    any("toast" in x or "floaty" in x for x in t):
                return "aviso_de_actividad"
            if t & {"fab", "float", "floating", "sticky-cta", "barra-cta", "mobile-cta", "cta-bar", "whatsapp"}:
                return "boton_flotante"
            if t & {"cookie", "cookies", "consent", "gdpr", "rodo"}:
                return "consentimiento"
            if t & {"popup", "modal", "overlay", "exit", "dialog", "lightbox", "downsell"} or \
                    n.attrs.get("role") == "dialog" or any("exit" in x or "modal" in x for x in t):
                return "ventana_emergente"
            if t & {"urgency", "announce", "announcement", "topbar", "promo", "bar", "banner", "urgbar"} or \
                    any(x.startswith(("urg", "topbar")) for x in t):
                return "barra_superior"
            if n.tag in ("header", "nav") or t & {"nav", "header", "menu", "navbar"}:
                return "navegacion"
            return "otro"

        def anotar(n: Nodo, pos: str, decl: dict, via: str) -> None:
            if dentro_de(n, {"head"}) or n.tag in IGNORAR_TOP or n.idx in fijos:
                return
            bordes = [b for b in ("top", "bottom", "left", "right") if b in decl]
            tipo = tipo_de(n)
            if tipo == "otro" and "top" in bordes and "bottom" not in bordes and n.tag not in ("header", "nav"):
                tipo = "barra_superior"
            fijos[n.idx] = {"elemento": etiqueta_corta(n), "posicion": pos, "bordes_declarados": bordes,
                            "tipo_inferido": tipo, "via": via}

        for r in self.css.reglas:
            pos = r.decl.get("position", "").strip().lower()
            if pos in ("fixed", "sticky") and not r.cond:
                for n in self.dom.coinciden(r.partes):
                    anotar(n, pos, r.decl, "css")
        for n in recorrer(self.cuerpo):
            st = parsear_declaraciones(n.attrs.get("style", "")) if n.attrs.get("style") else {}
            pos = st.get("position", "").lower()
            if pos in ("fixed", "sticky"):
                anotar(n, pos, st, "style_inline")
            elif set(n.clases()) & {"fixed", "sticky"} and n.tag not in IGNORAR_TOP:
                cl = set(n.clases())
                anotar(n, "fixed" if "fixed" in cl else "sticky", {b: 1 for b in ("top", "bottom", "left", "right") if b in cl}, "clase_utilitaria")
        return fijos

    # -- tipo de bloque
    def _tipo_bloque(self, b: Nodo, orden: int, total: int) -> tuple[str, str, list[str]]:
        sc: Counter = Counter()
        sg: dict[str, list[str]] = {}

        def sumar(tipo: str, p: float, señal: str) -> None:
            sc[tipo] += p
            sg.setdefault(tipo, []).append(señal)

        own = b.tokens()
        desc_cont: Counter = Counter()
        for d in descendientes_hasta(b, 4):
            if d is not b:
                tk = d.tokens()
                for tipo, claves in CLAVES_TIPO.items():
                    if tipo not in ("barra_superior", "pie", "cta_final", "heroe") and tk & claves:
                        desc_cont[tipo] += 1
        titulos = [normalizar(texto_de(h, 160)) for h in descendientes_hasta(b, 5) if h.tag in ("h1", "h2", "h3", "h4")]
        titulos += [normalizar(texto_de(h, 100)) for h in descendientes_hasta(b, 4) if h.tokens() & {"eyebrow", "kicker", "overline"}]
        for tipo, claves in CLAVES_TIPO.items():
            if tipo == "barra_superior" and not (own & {"bar", "barra"} or own & claves):
                continue
            hit = own & claves
            if hit:
                sumar(tipo, 3, f"clase/id propia: {sorted(hit)[0]}")
            elif desc_cont.get(tipo):
                sumar(tipo, 2 if desc_cont[tipo] >= 3 else 1, f"clase/id interna en {desc_cont[tipo]} elemento(s) de «{tipo}»")
        for tipo, palabras in PALABRAS_TIPO.items():
            for t in titulos:
                hit = next((w for w in palabras if w in t), None)
                if hit:
                    sumar(tipo, 3, f"titular contiene «{hit.strip()}»")
                    break
        elementos = list(descendientes_hasta(b, 8))
        imgs = [d for d in elementos if d.tag == "img" and not dentro_de(d, {"noscript"})]
        urls_unicas = {d.attrs.get("data-src") or d.attrs.get("src", "") for d in imgs}
        n_ctas = sum(1 for d in elementos if d.idx in self.ctas_nodos)
        pals = n_palabras(texto_de(b, 3000))
        tabs = [d for d in elementos if _es_pestana(d)]
        n_det = sum(1 for d in elementos if d.tag == "details")
        n_exp = sum(1 for d in elementos if d.attrs.get("aria-expanded") is not None and d.attrs.get("role") != "tab")
        n_bq = sum(1 for d in elementos if d.tag == "blockquote")
        precios = len(RE_MONEDA.findall(texto_de(b, 3000)))
        if len(tabs) >= 2:
            sumar("selector_niveles", 4, f"{len(tabs)} pestañas o selectores")
        if n_det >= 3 or n_exp >= 3:
            sumar("faq", 4, f"{max(n_det, n_exp)} desplegables (details/aria-expanded)")
        if precios and n_ctas:
            sumar("precio", 1, "contiene importes y un CTA")
        elif precios:
            sumar("precio", 0.5, "contiene importes")
        if len(imgs) >= 8 and pals <= 80:
            sumar("tira_imagenes", 4, f"{len(imgs)} imágenes y poco texto")
        elif len(imgs) >= 5 and pals <= 40:
            sumar("tira_imagenes", 2, f"{len(imgs)} imágenes y poco texto")
        if n_bq >= 2:
            sumar("resenas", 2, f"{n_bq} citas (blockquote)")
        retratos = sum(1 for d in imgs if _ratio(d) and _ratio(d) >= 1.4)
        if retratos >= 3:
            sumar("resenas", 1, f"{retratos} imágenes verticales (capturas)")
        if b.tag == "footer" or (own & {"footer", "colophon"}):
            sumar("pie", 6, "etiqueta footer")
        if b.tag == "nav":
            sumar("navegacion", 5, "etiqueta nav")
        if any(d.tag == "h1" for d in elementos) and orden <= 3:
            sumar("heroe", 3, "contiene el h1 en los primeros bloques")
        if orden == 1 and pals <= 40 and not any(d.tag in ("h1", "h2") for d in elementos) and \
                (b.idx in self._fijos or own & {"bar", "barra", "urgency", "announce", "topbar"}):
            sumar("barra_superior", 3, "primer bloque corto, sin titulares")
        if b.tag in ("ol",) or sum(1 for d in elementos if d.tokens() & {"step", "paso", "krok", "passo"}) >= 3:
            sumar("entrega", 3, "pasos numerados")
        checks = sum(1 for d in elementos if d.tokens() & {"check", "tick", "checklist", "checklist-item"})
        if checks >= 3 and n_ctas >= 1 and orden >= total - 3:
            sumar("cta_final", 3, f"{checks} ítems de verificación y un CTA cerca del final")
        pie_orden = next((i for i, x in enumerate(self.bloques, 1) if x.tag == "footer"), None)
        if pie_orden and orden == pie_orden - 1 and n_ctas >= 1:
            sumar("cta_final", 2, "último bloque antes del pie y lleva un CTA")
        if b.idx in self._fijos:
            f = self._fijos[b.idx]
            if f["tipo_inferido"] == "barra_superior":
                sumar("barra_superior", 4, f"{f['posicion']} {'/'.join(f['bordes_declarados']) or ''}".strip())
            else:
                sumar("flotante", 5, f"posición {f['posicion']} ({f['via']}): {f['tipo_inferido']}")
        hijos_sig = _significativos(b)
        wrap = hijos_sig[0] if len(hijos_sig) == 1 else b
        firmas = _firmas_hermanos(wrap)
        rep = max(firmas.values()) if firmas else 0
        if rep >= 3:
            for t in ("para_quien", "bonus", "contenido"):
                sc[t] += 0.5
        if not sc:
            return "texto_generico", "baja", ["sin señales claras"]
        orden_tipos = sc.most_common()
        mejor, pm = orden_tipos[0]
        segundo = orden_tipos[1][1] if len(orden_tipos) > 1 else 0
        if pm < 1:
            return "texto_generico", "baja", sg.get(mejor, [])
        conf = "alta" if pm >= 5 and pm - segundo >= 2 else "media" if pm >= 3 else "baja"
        return mejor, conf, sg.get(mejor, [])

    # -- secciones
    def secciones(self) -> list[dict]:
        out = []
        total = len(self.bloques)
        for i, b in enumerate(self.bloques, 1):
            tipo, conf, señales = self._tipo_bloque(b, i, total)
            elementos = list(descendientes_hasta(b, 9))
            heads = [d for d in elementos if d.tag in ("h1", "h2", "h3", "h4", "h5", "h6") and not dentro_de(d, {"noscript"})]
            imgs = [d for d in elementos if d.tag == "img" and not dentro_de(d, {"noscript"})]
            ctas = [d for d in elementos if d.idx in self.ctas_nodos]
            comp = self._componentes(b, elementos)
            fondo = self._fondo(b)
            sec = {
                "orden": i, "tag": b.tag, "id_html": _ident(b.attrs.get("id", ""), 40),
                "clases": [] if con_forma_de_instruccion(" ".join(b.clases())) else [_ident(c, 40) for c in b.clases()[:6]],
                "tipo_inferido": tipo, "confianza": conf, "senales": [limpiar(s, 80) for s in señales[:4]],
                "fondo": fondo, "fijo": self._fijos.get(b.idx),
                "titulares": [{"nivel": int(h.tag[1]), "palabras": n_palabras(texto_de(h, 300)), "caracteres": len(texto_de(h, 300))} for h in heads[:12]],
                "n_palabras": n_palabras(texto_de(b, 20000)), "n_imagenes": len(imgs),
                "n_imagenes_unicas": len({d.attrs.get("data-src") or d.attrs.get("src", "") for d in imgs}),
                "n_ctas": len(ctas), "componentes": comp, "dom": resumir_dom(b),
            }
            out.append(sec)
        return out

    def _fondo(self, b: Nodo) -> dict:
        v = self.css.valor(b, "background")
        hexc = color_a_hex(v) if v else None
        if hexc:
            return {"color": hexc, "tono": "oscuro" if luminancia(hexc) < 0.35 else "claro", "via": "css"}
        toks = b.tokens()
        if toks & {"dark", "oscuro", "black", "negro", "ink", "navy", "section-dark"}:
            return {"color": None, "tono": "oscuro", "via": "clase"}
        vb = self.css.valor(self.cuerpo, "background") if self.cuerpo is not self.raiz else None
        hb = color_a_hex(vb) if vb else None
        if hb:
            return {"color": hb, "tono": "oscuro" if luminancia(hb) < 0.35 else "claro", "via": "heredado_del_body"}
        return {"color": None, "tono": "desconocido", "via": "ninguna"}

    def _componentes(self, b: Nodo, elementos: list[Nodo]) -> list[dict]:
        comp: list[dict] = []

        def add(nombre: str, n: int = 1, **kw) -> None:
            comp.append({"componente": nombre, "n": n, **kw})
        ctas = sum(1 for d in elementos if d.idx in self.ctas_nodos)
        if ctas:
            add("cta", ctas)
        tabs = [d for d in elementos if _es_pestana(d)]
        if len(tabs) >= 2:
            add("selector_pestanas", len(tabs))
        det = sum(1 for d in elementos if d.tag == "details")
        exp = sum(1 for d in elementos if d.attrs.get("aria-expanded") is not None and d.attrs.get("role") != "tab" and "data-tab" not in d.attrs)
        if det:
            add("acordeon_details", det)
        if exp:
            add("acordeon_aria", exp)
        imgs = [d for d in elementos if d.tag == "img" and not dentro_de(d, {"noscript"})]
        if len(imgs) >= 5:
            srcs = [d.attrs.get("data-src") or d.attrs.get("src", "") for d in imgs]
            mitad = len(srcs) // 2
            dup = mitad >= 2 and srcs[:mitad] == srcs[mitad:2 * mitad]
            add("tira_o_galeria_de_imagenes", len(imgs), unicas=len(set(srcs)), duplicado_para_bucle=bool(dup))
        peq = [d for d in imgs if (_ancho(d) or 999) <= 64]
        if len(peq) >= 3:
            add("avatares", len(peq))
        if any(d.tokens() & {"marquee", "carousel", "slider", "swiper", "slick", "splide"} for d in elementos) or \
                any("data-speed" in d.attrs for d in elementos):
            add("carril_autodesplazable_o_carrusel")
        wrap = _significativos(b)
        wrap = _significativos(wrap[0]) if len(wrap) == 1 else wrap
        firmas = Counter()
        for h in wrap:
            for hh in (_significativos(h) if h.tag in CONTENEDORES and len(_significativos(h)) >= 3 else [h]):
                firmas[firma(hh)] += 1
        if firmas:
            f, c = firmas.most_common(1)[0]
            if c >= 3 and f not in ("li", "img", "p", "a", "span", "br", "td", "tr", "option", "h2", "h3", "h4", "strong"):
                add("rejilla_de_tarjetas", c, firma=limpiar(f, 60))
        checks = sum(1 for d in elementos if d.tokens() & {"check", "tick", "checklist-item"})
        if checks >= 3:
            add("lista_de_verificacion", checks)
        if any(d.tag == "table" for d in elementos):
            add("tabla")
        if any(d.tag == "ol" for d in elementos):
            add("lista_numerada")
        stars = texto_de(b, 3000).count("★")
        if stars >= 3 or any(d.tokens() & {"stars", "rating", "star"} for d in elementos):
            add("estrellas_o_valoracion")
        if self._precio_tachado_en(b):
            add("precio_tachado")
        if any(d.tag in ("video", "iframe") for d in elementos):
            add("video_o_iframe")
        if any(d.tag in ("form", "input", "select", "textarea") and d.attrs.get("type") != "hidden" for d in elementos):
            add("formulario")
        if any(d.tag == "blockquote" for d in elementos):
            add("citas")
        return comp

    def _precio_tachado_en(self, b: Nodo) -> bool:
        return any(self._es_tachado(d) and RE_CIFRA.search(texto_de(d, 60)) for d in recorrer(b) if d.tag != "#texto")

    def _clases_tachado(self) -> set[str]:
        if not hasattr(self, "_ct"):
            ct: set[str] = set()
            for r in self.css.reglas_con("text-decoration", lambda v: "line-through" in v):
                for tag, idv, clases, _s, ps in r.partes:
                    ct.update(clases)
            for r in self.css.reglas_con("text-decoration-line", lambda v: "line-through" in v):
                for tag, idv, clases, _s, ps in r.partes:
                    ct.update(clases)
            self._ct = ct
        return self._ct

    def _es_tachado(self, n: Nodo) -> bool:
        if n.tag in ("s", "del", "strike"):
            return True
        if "line-through" in n.attrs.get("style", "").lower():
            return True
        return bool(set(n.clases()) & self._clases_tachado())

    # -- CTA y enlaces
    def ctas(self) -> list[dict]:
        out = []
        idx_a_bloque = self._mapa_bloques()
        for n in recorrer(self.cuerpo):
            c = self.ctas_nodos.get(n.idx)
            if not c or len(out) >= MAX_CTAS:
                continue
            out.append({"bloque": idx_a_bloque.get(n.idx), "elemento": etiqueta_corta(n), "texto": limpiar(c["texto"], 100),
                        "destino": c["destino"], "tokens_clase": c["tokens_clase"]})
        return out

    def _mapa_bloques(self) -> dict[int, int]:
        if not hasattr(self, "_mb"):
            mb: dict[int, int] = {}
            for i, b in enumerate(self.bloques, 1):
                for d in recorrer(b):
                    mb[d.idx] = i
            self._mb = mb
        return self._mb

    def enlaces_checkout(self) -> list[dict]:
        vistos: dict[tuple, dict] = {}
        mb = self._mapa_bloques()

        def reg(href: str, via: str, n: Optional[Nodo]) -> None:
            d = clasificar_destino(href, self.host_propio)
            if d["tipo"] not in ("checkout_externo", "checkout_interno"):
                return
            k = (d["tipo"], d.get("plataforma", ""), d.get("host", ""), d.get("ruta_forma", ""), tuple(d.get("parametros", [])))
            e = vistos.setdefault(k, {**d, "apariciones": 0, "via": set(), "bloques": set()})
            e["apariciones"] += 1
            e["via"].add(via)
            if n is not None and mb.get(n.idx):
                e["bloques"].add(mb[n.idx])
        for n in recorrer(self.raiz):
            if n.tag == "a" and n.attrs.get("href"):
                reg(n.attrs["href"], "enlace", n)
            elif n.tag == "form" and n.attrs.get("action"):
                reg(n.attrs["action"], "formulario", n)
            for k in ("data-href", "data-url", "formaction"):
                if n.attrs.get(k):
                    reg(n.attrs[k], k, n)
            if n.tag == "script" and n.texto and "src" not in n.attrs:
                for m in list(RE_URL_TEXTO.finditer(n.texto[:MAX_SCRIPT_TEXTO]))[:200]:
                    reg(m.group(0), "script_inline", None)
        return [{**{k: v for k, v in e.items() if k not in ("via", "bloques")},
                 "via": sorted(e["via"]), "bloques": sorted(e["bloques"])} for e in vistos.values()]

    # -- selectores y acordeones
    def selectores_y_acordeones(self) -> dict:
        ids = {n.attrs.get("id") for n in recorrer(self.cuerpo) if n.attrs.get("id")}
        tabs = [n for n in recorrer(self.cuerpo) if _es_pestana(n)]
        destinos = [n.attrs.get("data-tab") or n.attrs.get("aria-controls") or n.attrs.get("href", "").lstrip("#") for n in tabs]
        paneles = [d for d in destinos if d and d in ids]
        selects = [n for n in recorrer(self.cuerpo) if n.tag == "select"]
        det = [n for n in recorrer(self.cuerpo) if n.tag == "details"]
        exp = [n for n in recorrer(self.cuerpo) if n.attrs.get("aria-expanded") is not None and n.attrs.get("role") != "tab"
               and "data-tab" not in n.attrs and not n.attrs.get("aria-pressed")]
        mb = self._mapa_bloques()
        targets = [n for n in recorrer(self.cuerpo) if n.tag == "a" and n.attrs.get("href", "").startswith("#") and len(n.attrs["href"]) > 1
                   and n.attrs["href"][1:] in ids and n.idx not in self.ctas_nodos and not dentro_de(n, {"nav", "footer"})]
        return {
            "pestanas": {"cantidad": len(tabs), "paneles_encontrados": len(paneles), "bloque": mb.get(tabs[0].idx) if tabs else None,
                         "mecanismo": "atributos data-tab/role=tab (requiere JavaScript salvo que se use :target)" if tabs else None,
                         "rotulos_longitud": [len(texto_de(t, 100)) for t in tabs[:12]]},
            "menus_select": {"cantidad": len(selects)},
            "enlaces_a_ancla_interna_que_no_son_cta": len(targets),
            "acordeones": {
                "details": {"cantidad": len(det), "abiertos_por_defecto": sum(1 for d in det if "open" in d.attrs)},
                "aria_expanded": {"cantidad": len(exp), "mecanismo": "JavaScript propio (no <details>)" if exp else None},
                "bloques": sorted({mb[n.idx] for n in det + exp if n.idx in mb}),
            },
        }

    def elementos_fijos(self) -> list[dict]:
        mb = self._mapa_bloques()
        nodos = {n.idx: n for n in recorrer(self.cuerpo)}
        out = []
        for idx, f in self._fijos.items():
            n = nodos.get(idx)
            if n is None:
                continue
            ancho = " ".join(sorted({t for t in n.tokens() if len(t) > 2})[:4])
            out.append({**f, "bloque": mb.get(idx), "oculto_por_atributo_o_style_en_linea": oculto_inline(n), "tokens": limpiar(ancho, 60)})
        return out[:40]

    def iconos(self) -> dict:
        svgs = [n for n in recorrer(self.cuerpo) if n.tag == "svg"]
        usos = sorted({limpiar(u.attrs.get("href", u.attrs.get("xlink:href", "")), 40) for u in recorrer(self.cuerpo)
                       if u.tag == "use"} - {""})[:30]
        prefijos: Counter = Counter()
        for n in recorrer(self.cuerpo):
            if n.tag in ("i", "span") and n.attrs.get("class"):
                for c in n.clases():
                    m = re.match(r"(fa[srlbd]?|fas|far|bi|icon|ico|material-icons|dashicons|lucide|ti|ri|uil|mdi)(?:[-_]|$)", c)
                    if m:
                        prefijos[m.group(1)] += 1
        texto = texto_de(self.cuerpo, 40000)
        emoji = sum(1 for ch in texto if ord(ch) >= 0x1F300 or ch in "✓✔✅❌★☆⭐➜→▶")
        img_svg = sum(1 for n in recorrer(self.cuerpo) if n.tag == "img" and (n.attrs.get("src", "") or n.attrs.get("data-src", "")).lower().split("?")[0].endswith(".svg"))
        return {"svg_inline": len(svgs), "svg_use_ids": usos, "fuentes_de_iconos": dict(prefijos.most_common(8)),
                "emoji_o_simbolos_en_texto": emoji, "img_svg": img_svg}

    def imagenes(self) -> dict:
        mb = self._mapa_bloques()
        imgs = [n for n in recorrer(self.cuerpo) if n.tag == "img"]
        en_noscript = sum(1 for n in imgs if dentro_de(n, {"noscript"}))
        reales = [n for n in imgs if not dentro_de(n, {"noscript"})]
        tam: Counter = Counter()
        sin_tamano = 0
        ext: Counter = Counter()
        hosts: Counter = Counter()
        alts: Counter = Counter()
        lazy = 0
        for n in reales:
            w, h = _ancho(n), _alto(n)
            if w and h:
                tam[f"{w}x{h}"] += 1
            else:
                sin_tamano += 1
            src = _src_real(n)
            e = os.path.splitext(urllib.parse.urlsplit(src).path)[1].lower().lstrip(".")[:5] if src else ""
            ext[e or "(sin)"] += 1
            if src.startswith(("http://", "https://")):
                hosts[host_de(src)] += 1
            if n.attrs.get("data-src") or n.attrs.get("data-lazy-src") or n.attrs.get("loading") == "lazy":
                lazy += 1
            a = limpiar(n.attrs.get("alt", ""), 80)
            if a:
                alts[a] += 1
        repetidos = {k: v for k, v in alts.items() if v >= 3}
        por_bloque = Counter(mb.get(n.idx) for n in reales)
        if repetidos:
            self.alerta("A-ALT-REPETIDO", f"{len(repetidos)} texto(s) alternativo(s) repetido(s) ≥ 3 veces (descuido de accesibilidad)")
        fondos = sum(1 for n in recorrer(self.raiz) if n.attrs.get("style") and "url(" in n.attrs["style"].lower() and "background" in n.attrs["style"].lower())
        return {"total": len(reales), "unicas": len({_src_real(n) for n in reales}), "dentro_de_noscript": en_noscript,
                "tamanos_declarados": dict(tam.most_common(15)), "sin_tamano_declarado": sin_tamano,
                "formatos": dict(ext.most_common(8)), "hosts": dict(hosts.most_common(6)), "con_carga_diferida": lazy,
                "con_alt": sum(1 for n in reales if n.attrs.get("alt")), "alt_repetidos_3_o_mas": len(repetidos),
                "por_bloque": {str(k): v for k, v in sorted(por_bloque.items(), key=lambda kv: (kv[0] is None, kv[0]))},
                "picture": sum(1 for n in recorrer(self.cuerpo) if n.tag == "picture"),
                "fondos_css_inline": fondos, "video": sum(1 for n in recorrer(self.cuerpo) if n.tag == "video"),
                "iframes": sum(1 for n in recorrer(self.cuerpo) if n.tag == "iframe")}

    # -- tokens de diseño
    def _usada(self, r: Regla) -> bool:
        """La regla se aplica a algún elemento del DOM (aprox.: se compara el último selector compuesto)."""
        sel = r.selector.strip()
        if r.origen == "style_inline":
            return True
        if ":root" in sel or sel in ("html", "body", "*") or sel.startswith(("html", "body", "*", ":root")):
            return True
        if not r.partes:
            return False
        return next(self.dom.coinciden(r.partes, con_pseudo=True), None) is not None

    def tokens_diseno(self) -> dict:
        css = self.css
        usadas = [r for r in css.reglas if self._usada(r)]
        colores: Counter = Counter()
        por_uso: dict[str, Counter] = {"texto": Counter(), "fondo": Counter(), "borde": Counter(), "sombra": Counter(), "otro": Counter()}
        fuentes: Counter = Counter()
        tamanos: Counter = Counter()
        pesos: Counter = Counter()
        radios: Counter = Counter()
        sombras: Counter = Counter()
        anchos: Counter = Counter()
        espacios: Counter = Counter()
        transiciones = animaciones = 0
        for r in usadas:
            for prop, val in r.decl.items():
                v = css.resolver(val)
                if prop.startswith("--"):
                    cs = todos_los_colores(val)
                else:
                    cs = todos_los_colores(v)
                for c in cs[:6]:
                    colores[c] += 1
                    uso = "texto" if prop == "color" else "fondo" if prop.startswith("background") else \
                        "borde" if prop.startswith("border") or prop == "outline" else "sombra" if "shadow" in prop else "otro"
                    por_uso[uso][c] += 1
                if prop == "font-family":
                    primera = limpiar(css.resolver(val).split(",")[0].strip(" '\""), 40)
                    if primera and not primera.startswith("var(") and primera.lower() not in ("inherit", "initial", "unset", "revert"):
                        fuentes[primera] += 1
                elif prop == "font-size":
                    tamanos[limpiar(v, 60)] += 1
                elif prop == "font-weight":
                    pesos[limpiar(v, 12)] += 1
                elif prop == "border-radius":
                    radios[limpiar(v, 30)] += 1
                elif prop == "box-shadow" and v != "none":
                    sombras[limpiar(v, 80)] += 1
                elif prop == "max-width" and v.endswith("px"):
                    sel = r.selector.lower()
                    if any(k in sel for k in ("wrap", "container", "inner", "content", "main", "section", "page")):
                        anchos[v] += 1
                elif prop == "padding" and "section" in r.selector.lower() and not r.cond:
                    espacios[limpiar(v, 30)] += 1
                elif prop.startswith("transition"):
                    transiciones += 1
                elif prop.startswith("animation"):
                    animaciones += 1
        # variables
        vars_ = {}
        de_plataforma = 0
        for k, v in css.variables.items():
            if k.startswith(PREFIJOS_VARIABLES_PLATAFORMA):
                de_plataforma += 1
                continue
            if len(vars_) >= 80:
                break
            tipo = "color" if todos_los_colores(v) and not v.strip().startswith("var(") and len(v) < 60 else \
                "fuente" if "font" in k else "sombra" if "shadow" in k else "medida" if re.match(r"^-?[\d.]+(?:px|rem|em|%)", v.strip()) else "otro"
            vars_[k] = {"valor": limpiar(v, 90), "tipo": tipo}
        # fuentes cargadas
        cargadas = {limpiar(f.get("font-family", "").strip(" '\""), 40) for f in css.estado["font_faces"] if f.get("font-family")}
        google = self._google_fonts()
        sistema = {"serif", "sans-serif", "monospace", "system-ui", "-apple-system", "blinkmacsystemfont", "segoe ui", "roboto",
                   "helvetica", "helvetica neue", "arial", "georgia", "times new roman", "verdana", "tahoma", "inherit", "cursive", "fantasy", "ui-sans-serif", "ui-serif"}
        sin_cargar = sorted(f for f in fuentes if f not in cargadas and f not in google and f.lower() not in sistema)
        bps: Counter = Counter()
        for r in usadas:
            for c in r.cond:
                for m in re.finditer(r"(min|max)-width\s*:\s*(\d+(?:\.\d+)?)(px|em|rem)", c):
                    bps[f"{m.group(1)}-width:{m.group(2)}{m.group(3)}"] += 1
        top = lambda c, n=12: [{"valor": k, "veces": v} for k, v in c.most_common(n)]
        uso_top = {k: [{"color": c, "veces": v} for c, v in cnt.most_common(6)] for k, cnt in por_uso.items() if cnt}
        return {
            "colores_mas_usados": [{"color": c, "veces": v} for c, v in colores.most_common(24)],
            "colores_por_uso": uso_top,
            "variables_css": vars_, "variables_de_plataforma_omitidas": de_plataforma,
            "reglas_css": {"total": len(css.reglas), "con_elemento_en_el_dom": len(usadas)},
            "fuentes_declaradas": top(fuentes, 8),
            "fuentes_cargadas": {"font_face": sorted(cargadas)[:10], "google_fonts": sorted(google)[:10]},
            "fuentes_declaradas_sin_cargar": sin_cargar,
            "tamanos_de_fuente": top(tamanos, 20), "pesos": top(pesos, 6),
            "radios": top(radios, 10), "sombras": top(sombras, 6), "anchos_de_contenedor": top(anchos, 5),
            "relleno_de_seccion": top(espacios, 5), "breakpoints": [{"condicion": k, "reglas": v} for k, v in sorted(bps.items())],
            "transiciones_declaradas": transiciones, "animaciones_declaradas": animaciones, "keyframes": css.estado["keyframes"],
            "modo_oscuro_prefers_color_scheme": any("prefers-color-scheme" in c for r in css.reglas for c in r.cond),
            "movimiento_reducido_respetado": any("prefers-reduced-motion" in c for r in css.reglas for c in r.cond),
            "hojas_leidas": css.origenes, "imports_css": [limpiar(x, 120) for x in css.estado["imports"][:5]],
            "hojas_externas_no_leidas": self._hojas_externas_pendientes(),
            "css_truncado": css.estado["truncado"],
        }

    def _google_fonts(self) -> set[str]:
        out: set[str] = set()
        textos = [n.attrs.get("href", "") for n in recorrer(self.raiz) if n.tag == "link"] + [x for x in self.css.estado["imports"]]
        for t in textos:
            if "fonts.googleapis.com" in t:
                for fam in re.findall(r"family=([^&:;)\"']+)", t):
                    out.add(limpiar(urllib.parse.unquote(fam).replace("+", " "), 40))
        return out

    def _hojas_externas_pendientes(self) -> list[dict]:
        leidas = {o["origen"] for o in self.css.origenes}
        res = []
        for n in recorrer(self.raiz):
            if n.tag == "link" and "stylesheet" in n.attrs.get("rel", "").lower() and n.attrs.get("href"):
                u = n.attrs["href"]
                if u not in leidas:
                    res.append({"host": host_de(u) or "(relativa)", "leida": False})
        return res[:20]

    # -- scripts de terceros
    def scripts_y_terceros(self) -> dict:
        propio = self.host_propio
        scripts = []
        pixeles: list[dict] = []
        comportamientos: dict[str, dict] = {}
        n_inline = 0
        for i, n in enumerate(s for s in recorrer(self.raiz) if s.tag == "script"):
            tipo = n.attrs.get("type", "").lower()
            src = n.attrs.get("src") or n.attrs.get("data-src") or ""
            es_json = "json" in tipo or tipo in ("speculationrules", "importmap")
            diferido = tipo not in ("", "text/javascript", "module", "application/javascript") and not es_json
            if src:
                host = host_de(src if not src.startswith("//") else "https:" + src)
                prov = sufijo_en(host, TERCEROS) if host else None
                tercero = bool(host) and not (propio and (host == propio or host.endswith("." + propio) or propio.endswith("." + host)))
                cat, nom = TERCEROS.get(prov, ("otro", "")) if prov else ("otro", "")
                archivo = os.path.basename(urllib.parse.urlsplit(src).path)
                lib = next((nombre for clave, nombre in BIBLIOTECAS_CONOCIDAS if clave in archivo.lower() or clave in src.lower()), "")
                if lib and not tercero:
                    cat, nom = "biblioteca_o_tema", lib
                elif tercero and cat == "otro":
                    cat = "tercero_desconocido"
                scripts.append({"origen": "externo", "host": host or "(relativo)", "archivo": limpiar(archivo, 50), "tercero": tercero,
                                "categoria": cat, "proveedor": nom, "diferido_por_plugin": diferido, "async": "async" in n.attrs,
                                "defer": "defer" in n.attrs})
                for a in ATRIBUTOS_PIXEL:
                    if n.attrs.get(a):
                        pixeles.append({"proveedor": f"desconocido (atributo {a})", "via": "atributo_del_script", "host_script": host,
                                        "id_presente": True, "id_longitud": len(n.attrs[a])})
                if cat == "pixel_publicitario":
                    pixeles.append({"proveedor": nom, "via": "script_externo", "host_script": host, "id_presente": False, "id_longitud": 0})
            elif n.texto.strip() and not es_json:
                n_inline += 1
                cuerpo = n.texto[:MAX_SCRIPT_TEXTO]
                scripts.append({"origen": "inline", "bytes": len(n.texto), "sha256_16": sha16(cuerpo), "diferido_por_plugin": diferido})
                for nombre, rx in FIRMAS_PIXEL:
                    m = rx.search(cuerpo)
                    if m:
                        ident = m.group(1) if m.groups() and m.group(1) else ""
                        pixeles.append({"proveedor": nombre, "via": "script_inline", "id_presente": bool(ident), "id_longitud": len(ident)})
                for codigo, rx1, rx2, desc in FIRMAS_JS:
                    if rx1.search(cuerpo) and (rx2 is None or rx2.search(cuerpo)):
                        e = comportamientos.setdefault(codigo, {"codigo": codigo, "descripcion": desc, "scripts_inline": 0})
                        e["scripts_inline"] += 1
        for a in ATRIBUTOS_PIXEL:
            for n in recorrer(self.raiz):
                if n.tag != "script" and n.attrs.get(a):
                    pixeles.append({"proveedor": f"desconocido (atributo {a})", "via": "atributo", "id_presente": True, "id_longitud": len(n.attrs[a])})
        for n in recorrer(self.raiz):
            if n.tag == "img" and dentro_de(n, {"noscript"}) and "facebook.com/tr" in n.attrs.get("src", ""):
                pixeles.append({"proveedor": "Meta Pixel", "via": "noscript_img", "id_presente": "id=" in n.attrs.get("src", ""), "id_longitud": 0})
        iframes = []
        for n in recorrer(self.raiz):
            if n.tag == "iframe" and (n.attrs.get("src") or n.attrs.get("data-src")):
                s = n.attrs.get("src") or n.attrs.get("data-src")
                h = host_de(s if not s.startswith("//") else "https:" + s)
                prov = sufijo_en(h, TERCEROS)
                iframes.append({"host": h or "(relativo)", "categoria": TERCEROS[prov][0] if prov else "otro",
                                "proveedor": TERCEROS[prov][1] if prov else ""})
        # deduplicar píxeles
        vistos, unicos = set(), []
        for p in pixeles:
            k = (p["proveedor"], p["via"])
            if k not in vistos:
                vistos.add(k)
                unicos.append(p)
        terceros = sorted({(s["host"], s["categoria"], s["proveedor"]) for s in scripts if s.get("tercero")})
        if unicos:
            self.alerta("A-PIXEL-DEL-REFERENTE", f"{len(unicos)} píxel(es) o rastreador(es) del referente: no se reproducen (J20); el nuestro lo inyecta consentimiento.js")
        return {
            "scripts_total": len(scripts), "scripts_inline": n_inline, "scripts_externos": sum(1 for s in scripts if s["origen"] == "externo"),
            "scripts": scripts[:80], "terceros": [{"host": h, "categoria": c, "proveedor": p} for h, c, p in terceros][:40],
            "pixeles_y_rastreadores": unicos[:20], "iframes": iframes[:20],
            "comportamientos_js_detectados": list(comportamientos.values()),
            "nota": "Solo firmas en texto: el JavaScript no se ejecutó ni se interpretó; lo que un script inserta en el DOM no se ve.",
        }

    # -- metadatos y plataforma
    def documento(self) -> dict:
        metas = {}
        for n in recorrer(self.raiz):
            if n.tag == "meta":
                k = n.attrs.get("name") or n.attrs.get("property") or ""
                if k:
                    metas[k.lower()] = n.attrs.get("content", "")
        titulos = [n for n in recorrer(self.raiz) if n.tag == "title"]
        plataformas = []
        crudo = self.texto_html[:400000].lower()
        for clave, nombre in (("wp-content", "WordPress"), ("elementor", "Elementor"), ("litespeed", "LiteSpeed Cache"),
                              ("cdn.shopify.com", "Shopify"), ("wixstatic.com", "Wix"), ("webflow", "Webflow"),
                              ("squarespace", "Squarespace"), ("framer.", "Framer"), ("systeme.io", "systeme.io"),
                              ("clickfunnels", "ClickFunnels"), ("leadpages", "Leadpages"), ("carrd.co", "Carrd"),
                              ("__next", "Next.js"), ("data-reactroot", "React")):
            if clave in crudo:
                plataformas.append({"plataforma": nombre, "evidencia": f"cadena «{clave}» en el HTML"})
        html_lang = self.html.attrs.get("lang", "") if self.html is not self.raiz else ""
        return {
            "lang": limpiar(html_lang, 12), "title_caracteres": len(texto_de(titulos[0], 300)) if titulos else 0,
            "meta_description_caracteres": len(metas.get("description", "")), "robots": limpiar(metas.get("robots", ""), 60),
            "viewport": bool(metas.get("viewport")), "og_presente": any(k.startswith("og:") for k in metas),
            "twitter_card": any(k.startswith("twitter:") for k in metas), "generator": limpiar(metas.get("generator", ""), 60),
            "canonical_host": next((host_de(n.attrs.get("href", "")) for n in recorrer(self.raiz) if n.tag == "link" and n.attrs.get("rel", "").lower() == "canonical"), ""),
            "host_propio": self.host_propio, "host_propio_origen": self.origen_host,
            "plataformas_detectadas": plataformas, "comentarios_html": self.p.comentarios,
            "nodos": self.p.n, "nodos_truncados": self.p.truncado_nodos, "profundidad_truncada": self.p.prof_truncada,
            "error_parser": getattr(self.p, "error_parser", None),
        }

    # -- alertas mecánicas (señales para el desarme; la decisión es del juez o del humano)
    def alertas_mecanicas(self, secciones: list[dict], ctas: list[dict], js: dict) -> None:
        mb = self._mapa_bloques()
        for n in recorrer(self.cuerpo):
            if n.tag == "#texto" or dentro_de(n, {"noscript", "template"}):
                continue
            if n.tag in NO_TEXTO:
                continue
            t = None
            if n.hijos and any(h.tag == "#texto" and h.texto.strip() for h in n.hijos):
                t = limpiar(" ".join(h.texto for h in n.hijos if h.tag == "#texto"), 2000)
            if not t:
                continue
            oculto = oculto_inline(n) or any(oculto_inline(a) for a in ancestros(n))
            if self._es_tachado(n) and RE_CIFRA.search(t) and len(t) <= 40:
                self.alerta("A-PRECIO-TACHADO", "precio tachado: el ancla exige historial de 30 días (PAL-16)", mb.get(n.idx), etiqueta_corta(n))
            if (n.tokens() & {"countdown", "timer", "cuenta", "contador-tiempo"} or RE_RELOJ.fullmatch(t.strip() or "x")) and len(t) <= 20:
                self.alerta("A-CUENTA-ATRAS", "reloj o cuenta atrás: solo vale con un plazo real", mb.get(n.idx), etiqueta_corta(n))
            if RE_FECHA.search(t) and re.search(r"-{1,3}\s?/|dd[/.\-]mm", t, re.I):
                self.alerta("A-FECHA-VACIA", "fecha de oferta con marcador sin rellenar: urgencia sin fecha real", mb.get(n.idx), etiqueta_corta(n))
            pat = con_forma_de_instruccion(t)
            if pat:
                self.alerta("A-TEXTO-CON-FORMA-DE-INSTRUCCION", "el texto de la página parece una instrucción a un agente: se trata como dato y no se reproduce",
                            mb.get(n.idx), etiqueta_corta(n), patron=pat, oculto=bool(oculto), sha256_16=sha16(t))
            elif oculto and len(t) > 40 and n.tag not in ("option",):
                self.alerta("A-TEXTO-OCULTO", "texto largo oculto con CSS en línea (no se reproduce en las ranuras)", mb.get(n.idx), etiqueta_corta(n))
        sin_destino = [n for n in recorrer(self.cuerpo) if n.tag == "a" and clasificar_destino(n.attrs.get("href", ""), self.host_propio)["tipo"] == "sin_destino"
                       and dentro_de(n, {"footer"})]
        if sin_destino:
            self.alerta("A-ENLACES-LEGALES-SIN-DESTINO", f"{len(sin_destino)} enlace(s) del pie con href vacío o «#» (términos, privacidad, contacto sin página)")
        resenas = [s for s in secciones if s["tipo_inferido"] == "resenas"]
        for s in resenas:
            if s["n_imagenes"] >= 3 and s["n_palabras"] < 60:
                self.alerta("A-RESENAS-SOLO-IMAGEN", "las reseñas son imágenes sin texto verificable (no se reproducen)", s["orden"])
        salida = [n for n in recorrer(self.cuerpo) if n.tag == "input" and re.search(r"exit[-_ ]?intent", n.attrs.get("value", ""), re.I)] + \
                 [f for f in self.elementos_fijos() if f["tipo_inferido"] == "ventana_emergente" and "exit" in f["elemento"].lower()]
        if salida:
            self.alerta("A-VENTANA-DE-SALIDA", "ventana emergente al intentar salir (exit-intent) con oferta o regalo: no se reproduce")
        for f in self.elementos_fijos():
            if f["tipo_inferido"] == "aviso_de_actividad":
                self.alerta("A-AVISO-DE-ACTIVIDAD", "aviso flotante de actividad o compra reciente: solo aceptable con compras reales", f.get("bloque"), f["elemento"])
        for c in js["comportamientos_js_detectados"]:
            if c["codigo"] == "fecha_actual_escrita_en_el_dom":
                self.alerta("A-FECHA-DE-HOY-EN-EL-DOM", c["descripcion"])
            if c["codigo"] == "aleatoriedad":
                self.alerta("A-ALEATORIEDAD-EN-JS", c["descripcion"])
            if c["codigo"] == "ventana_de_salida_probable":
                self.alerta("A-VENTANA-DE-SALIDA", c["descripcion"])
        cifras = [n for n in recorrer(self.cuerpo) if n.tag != "#texto" and RE_NUMERO_MAS.search(texto_de(n, 80)) and len(texto_de(n, 80)) <= 70
                  and any(w in normalizar(texto_de(n, 80)) for w in ("student", "alumn", "client", "cliente", "uczn", "accesos", "vendid", "usuari", "persone", "personas", "ludzi"))]
        if cifras:
            self.alerta("A-CIFRA-DE-PRUEBA-SOCIAL", f"{len(cifras)} cifra(s) tipo «+N alumnos/clientes»: sin fuente verificable no se reproducen")

    # -- mapa de ranuras
    def ranuras(self, secciones: list[dict]) -> dict:
        slots: list[dict] = []
        por_rol: Counter = Counter()
        por_seccion: Counter = Counter()
        truncado = False
        excl = set(self.ctas_nodos)
        n_ocultos = 0
        n_sospechosos = 0

        for bi, b in enumerate(self.bloques, 1):
            tipo = secciones[bi - 1]["tipo_inferido"]
            destino = DESTINO_D5.get(tipo, "revisar a mano")
            contador = 0
            vistos_img: dict[str, dict] = {}

            def emitir(n: Nodo, rol: str, tipo_slot: str, texto: str = "", **extra) -> Optional[dict]:
                nonlocal truncado, contador, n_sospechosos
                if len(slots) >= MAX_RANURAS or contador >= MAX_RANURAS_SECCION:
                    truncado = True
                    return None
                contador += 1
                sosp = con_forma_de_instruccion(texto) if texto else None
                if sosp:
                    n_sospechosos += 1
                s = {"id": f"B{bi:02d}-{contador:03d}", "bloque": bi, "bloque_tipo": tipo, "rol": rol, "tipo": tipo_slot,
                     "funcion": FUNCION_ROL.get(rol, "Contenido de la sección."), "selector": etiqueta_corta(n)}
                if texto:
                    s["longitud_caracteres"] = len(texto)
                    s["longitud_palabras"] = n_palabras(texto)
                    s["texto_sha256_16"] = sha16(texto)
                    if self.con_muestras and not sosp:
                        s["muestra"] = limpiar(texto, MAX_MUESTRA)
                    if sosp:
                        s["sospechoso_de_instruccion"] = True
                s.update(extra)
                s["destino_sugerido"] = destino
                s["expresion_protegida"] = True
                slots.append(s)
                por_rol[rol] += 1
                por_seccion[bi] += 1
                return s

            self._ranuras_de(b, bi, tipo, emitir, vistos_img, excl)

        # recuento de ocultos
        n_ocultos = sum(1 for n in recorrer(self.cuerpo) if n.tag != "#texto" and oculto_inline(n))
        resumen = {
            "total_ranuras": len(slots), "por_rol": dict(por_rol.most_common()),
            "por_bloque": {str(k): v for k, v in sorted(por_seccion.items())},
            "elementos_ocultos_por_css_en_linea": n_ocultos, "textos_con_forma_de_instruccion": n_sospechosos,
            "truncado_por_limite": truncado, "limites": {"max_ranuras": MAX_RANURAS, "max_por_bloque": MAX_RANURAS_SECCION},
        }
        return {"ranuras": slots, "resumen": resumen}

    def _ranuras_de(self, b: Nodo, bi: int, tipo: str, emitir: Callable, vistos_img: dict, excl: set[int]) -> None:
        # recorrido en preorden; los hojas de texto y los componentes de contenido emiten una ranura
        pila = [b]
        while pila:
            n = pila.pop()
            if n.tag == "#texto" or n.tag in NO_TEXTO:
                continue
            if oculto_inline(n) or dentro_de_noscript(n):
                continue
            if n.idx in self.ctas_nodos and n.tag != "input":
                c = self.ctas_nodos[n.idx]
                emitir(n, "cta_texto", "enlace", limpiar(c["texto"], 200), destino_tipo=c["destino"].get("tipo"))
                continue
            if n.tag == "img":
                src = _src_real(n)
                clave = src or f"idx{n.idx}"
                if clave in vistos_img:
                    vistos_img[clave]["repeticiones"] = vistos_img[clave].get("repeticiones", 1) + 1
                    continue
                w, h = _ancho(n), _alto(n)
                rol = "avatar" if ((w and w <= 64) or (n.padre is not None and n.padre.tokens() & {"avatars", "avatar", "faces", "people", "users"})) else {"heroe": "imagen_heroe", "tira_imagenes": "imagen_galeria", "resenas": "imagen_resena",
                                                      "bonus": "imagen_bonus", "precio": "imagen_precio"}.get(tipo, "imagen")
                extra: dict = {}
                if w and h:
                    extra["tamano_declarado"] = f"{w}x{h}"
                    extra["relacion_aspecto"] = round(w / h, 2) if h else None
                extra["alt_caracteres"] = len(n.attrs.get("alt", ""))
                extra["formato"] = os.path.splitext(urllib.parse.urlsplit(src).path)[1].lower().lstrip(".")[:5] if src else ""
                vistos_img[clave] = emitir(n, rol, "imagen", "", **extra) or {}
                continue
            if n.tag in ("video",) or (n.tag == "iframe" and (n.attrs.get("src") or n.attrs.get("data-src"))):
                emitir(n, "video", "video")
                continue
            if n.tag in ("input", "select", "textarea") and n.attrs.get("type", "") != "hidden":
                emitir(n, "campo_formulario", "formulario", "", tipo_campo=limpiar(n.attrs.get("type", n.tag), 20))
                continue
            if n.tag == "details":
                resumen = next((h for h in n.hijos if h.tag == "summary"), None)
                if resumen is not None:
                    t = texto_de(resumen, 400)
                    if t:
                        emitir(resumen, "faq_pregunta", "texto", t)
                    resto = texto_de(n, 1200, excluir={resumen.idx})
                    if resto:
                        emitir(n, "faq_respuesta", "texto", resto)
                    continue
            hoja = self._es_hoja_de_texto(n)
            if hoja:
                t = texto_de(n, 1500, excluir=excl)
                if t:
                    rol = self._rol_de(n, t, tipo, b)
                    extra = {}
                    if rol in ("precio", "precio_tachado"):
                        m = RE_MONEDA.search(t)
                        extra["formato_dato"] = re.sub(r"\d", "9", m.group(0))[:20] if m else None
                    emitir(n, rol, "dato" if rol in ("precio", "precio_tachado", "cifra", "fecha", "cuenta_atras", "valoracion") else "texto", t, **extra)
                continue
            # contenedor: recorrer hijos; texto suelto entre bloques
            for h in reversed(n.hijos):
                pila.append(h)

    def _es_hoja_de_texto(self, n: Nodo) -> bool:
        """Elemento con texto propio cuyos hijos elementales son solo en línea (o ninguno)."""
        if n.tag in ("html", "body", "main", "section", "header", "footer", "nav", "aside", "article", "form", "ul", "ol", "table", "tbody", "thead", "tr", "dl", "select"):
            return False
        if not any(h.tag == "#texto" and h.texto.strip() for h in n.hijos) and not any(
                h.tag in ("strong", "b", "em", "i", "mark", "span", "a", "small") and texto_de(h, 5) for h in n.hijos):
            return False
        for h in n.elementos():
            if h.tag in BLOQUE and h.tag not in ("button",):
                if h.idx in self.ctas_nodos:
                    continue
                return False
            if h.tag in ("div", "section", "img", "figure", "svg_no") and not (h.tag == "img" and False):
                if h.tag == "img":
                    continue
                return False
        return True

    def _rol_de(self, n: Nodo, t: str, tipo: str, bloque: Nodo) -> str:
        toks = n.tokens() | (n.padre.tokens() if n.padre else set())
        if n.tag == "summary":
            return "faq_pregunta"
        if toks & {"faq-q", "question", "pregunta", "pytanie", "domanda"} or (n.attrs.get("aria-expanded") is not None):
            return "faq_pregunta"
        if toks & {"faq-a", "answer", "respuesta", "odpowiedz", "risposta"}:
            return "faq_respuesta"
        if self._es_tachado(n) and RE_CIFRA.search(t):
            return "precio_tachado"
        if toks & {"countdown", "timer", "cuenta"} or (RE_RELOJ.fullmatch(t.strip()) and len(t) <= 12):
            return "cuenta_atras"
        if n.tag == "h1":
            return "titular_principal"
        if n.tag == "h2":
            return "titular_seccion"
        if n.tag in ("h3", "h4", "h5", "h6"):
            return "titulo_tarjeta"
        if n.tokens() & {"eyebrow", "kicker", "overline", "pretitle", "sobretitulo"}:
            return "sobretitulo"
        if n.tokens() & {"lead", "subtitle", "subtitulo", "subhead", "intro"}:
            return "lead"
        if n.tokens() & {"note", "microcopy", "safe", "safe-note", "disclaimer", "hint", "legal", "small"} or n.tag == "small":
            return "microcopy"
        if n.tokens() & {"badge", "tag", "chip", "pill", "label", "etiqueta", "insignia"}:
            return "etiqueta"
        if n.tokens() & {"stars", "rating", "star"} or t.count("★") >= 3:
            return "valoracion"
        if n.tokens() & {"price", "precio", "cena", "prezzo", "amount"} and RE_CIFRA.search(t):
            return "precio"
        if len(t) <= 40 and RE_MONEDA.search(t) and RE_CIFRA.search(t):
            return "precio"
        if RE_FECHA.search(t) and len(t) <= 60:
            return "fecha"
        if n.tag == "blockquote" or n.tokens() & {"testi", "review", "quote"}:
            return "resena_texto"
        if n.tag == "figcaption":
            return "pie_imagen"
        if n.tag in ("td", "th"):
            return "celda"
        if n.tag == "li" or (n.padre is not None and n.padre.tag == "li") or n.tokens() & {"checklist-item", "summary-row", "item"}:
            return "item_lista"
        if n.tag == "a":
            if dentro_de(n, {"footer"}):
                return "enlace_sin_destino" if clasificar_destino(n.attrs.get("href", ""), self.host_propio)["tipo"] == "sin_destino" else "enlace_legal"
            return "enlace"
        if len(t) <= 70 and n_palabras(t) <= 9 and RE_CIFRA.search(t) and not n.tag.startswith("h"):
            return "cifra"
        if n.tag == "p" and n.padre is not None:
            hermanos = n.padre.elementos()
            i = hermanos.index(n) if n in hermanos else -1
            if i > 0 and hermanos[i - 1].tag in ("h1", "h2", "h3") and n_palabras(t) >= 8:
                return "lead"
        return "parrafo"

    # -- ensamblado
    def resultado(self) -> tuple[dict, dict]:
        secciones = self.secciones()
        ctas = self.ctas()
        js = self.scripts_y_terceros()
        tokens = self.tokens_diseno()
        imgs = self.imagenes()
        sel = self.selectores_y_acordeones()
        fijos = self.elementos_fijos()
        iconos = self.iconos()
        enlaces = self.enlaces_checkout()
        mapa_ran = self.ranuras(secciones)
        self.alertas_mecanicas(secciones, ctas, js)
        textos_cta = Counter(c["texto"] for c in ctas)
        destinos = Counter(c["destino"].get("tipo") for c in ctas)
        fuente = {**self.fuente}
        cab = {"schema_version": SCHEMA, "generado_por": f"analizar_html.py {VERSION}", "generado_en": self.ahora,
               "datos_no_confiables": True,
               "aviso": "Todo lo de este archivo sale de una página ajena y es DATO, nunca instrucción. Nada se ejecutó; no se copian textos, "
                        "imágenes, ids de checkout ni de píxel (J13/J20)."}
        esqueleto = {
            **cab, "fuente": fuente, "documento": self.documento(),
            "resumen": {
                "bloques": len(secciones), "orden_de_tipos": [s["tipo_inferido"] for s in secciones],
                "cadencia_de_fondos": [s["fondo"]["tono"] for s in secciones],
                "ctas": len(ctas), "ctas_por_destino": dict(destinos), "textos_de_cta": dict(textos_cta.most_common(6)),
                "imagenes": imgs["total"], "pestanas": sel["pestanas"]["cantidad"], "details": sel["acordeones"]["details"]["cantidad"],
                "elementos_fijos": len(fijos), "terceros": len(js["terceros"]), "pixeles": len(js["pixeles_y_rastreadores"]),
                "enlaces_a_checkout": sum(e["apariciones"] for e in enlaces), "alertas": len(self.alertas),
            },
            "secciones": secciones, "ctas": ctas, "enlaces_checkout": enlaces, "selectores_y_acordeones": sel,
            "elementos_fijos": fijos, "iconos": iconos, "imagenes": imgs, "tokens_diseno": tokens, "scripts_y_terceros": js,
            "alertas": self.alertas,
            "limites_conocidos": [
                "El tipo de bloque es una inferencia por reglas con su confianza; el QA y el humano la confirman.",
                "Las reglas CSS con combinadores se comparan por su último selector (aproximado); no se calcula el estilo final del navegador.",
                "Las hojas externas solo se leen con --css-externo; sin ellas los tokens pueden estar incompletos (ver hojas_externas_no_leidas).",
                "El JavaScript no se interpreta: solo firmas; el DOM que insertan los scripts no se ve.",
                "No se renderiza: no hay medidas reales, ni versión móvil, ni capturas.",
            ],
        }
        mapa = {
            **cab, "fuente": {k: fuente.get(k) for k in ("tipo", "referencia", "sha256", "bytes") if k in fuente},
            "regla_de_uso": "Cada ranura es CONTENIDO del referente (expresión protegida, J13): se reescribe con material propio. Aquí solo "
                            "figura su función, su longitud y dónde cae en nuestro contrato. «muestra» es una cita corta de uso interno.",
            "ranuras": mapa_ran["ranuras"], "resumen": mapa_ran["resumen"],
            "estructura_fija_que_NO_es_contenido": [
                "orden de los bloques y jerarquía del DOM (esqueleto_html.json → secciones[].dom)",
                "clases, tokens y medidas de diseño (esqueleto_html.json → tokens_diseno)",
                "íconos y componentes (esqueleto_html.json → iconos, secciones[].componentes)",
                "rótulos de interfaz por idioma (se generan en el sitio; no vienen del referente)",
            ],
        }
        cuenta = [0]
        esqueleto, mapa = blindar(esqueleto, cuenta), blindar(mapa, cuenta)
        if cuenta[0]:
            esqueleto["alertas"].append({"codigo": "A-TEXTO-CON-FORMA-DE-INSTRUCCION", "bloque": None, "selector": "",
                                         "nota": f"{cuenta[0]} valor(es) derivados de la página (clases, ids, rutas o textos) se omitieron por parecer instrucciones; se tratan como dato"})
            esqueleto["resumen"]["alertas"] = len(esqueleto["alertas"])
        return esqueleto, mapa


def _es_pestana(n: Nodo) -> bool:
    """Elemento que actúa como pestaña: role=tab, data-tab o clase exacta tab/tab-btn (no sus hijos tab-label/tab-badge)."""
    if n.attrs.get("role") == "tab" or "data-tab" in n.attrs or n.attrs.get("data-bs-toggle") == "tab":
        return True
    return n.tag in ("button", "a", "div", "li") and bool(set(n.clases()) & {"tab", "tab-btn", "tab-button", "tab-item", "tab-link"})


def dentro_de_noscript(n: Nodo) -> bool:
    return dentro_de(n, {"noscript", "template"})


def _num(v: str) -> Optional[int]:
    m = re.match(r"^\s*(\d{1,5})", v or "")
    return int(m.group(1)) if m else None


def _ancho(n: Nodo) -> Optional[int]:
    return _num(n.attrs.get("width", ""))


def _alto(n: Nodo) -> Optional[int]:
    return _num(n.attrs.get("height", ""))


def _ratio(n: Nodo) -> Optional[float]:
    w, h = _ancho(n), _alto(n)
    return (h / w) if w and h else None


def _src_real(n: Nodo) -> str:
    for k in ("data-src", "data-lazy-src", "data-original", "src"):
        v = n.attrs.get(k, "")
        if v and not v.startswith("data:"):
            return v
    ss = n.attrs.get("data-srcset") or n.attrs.get("srcset") or ""
    return ss.split(",")[0].strip().split(" ")[0] if ss else ""


# ── fuente (archivo o URL) ───────────────────────────────────────────────────
def obtener_texto(fuente: str, *, no_red: bool, max_bytes: int, timeout: float, permitir_privadas: bool = False,
                  abrir: Optional[Callable[..., Any]] = None, comprobar_robots: bool = True,
                  freno: Optional[Path] = None) -> tuple[str, dict]:
    """Devuelve (texto, info de la fuente). Archivo local o URL; ``no_red`` rechaza la URL; un ``freno`` existente también."""
    es_url = fuente.lower().startswith(("http://", "https://"))
    if es_url:
        if no_red:
            raise RedNoPermitida("--no-red: no se abre ninguna URL; guarda el HTML con el navegador y pasa el archivo")
        if freno is not None and freno.exists():
            raise RedNoPermitida(f"el freno de captura está puesto ({freno.name}); solo el dueño lo levanta. Usa el HTML guardado a mano")
        datos, meta = descargar(fuente, max_bytes=max_bytes, timeout=timeout, abrir=abrir, permitir_privadas=permitir_privadas,
                                comprobar_robots=comprobar_robots)
        texto, cod = decodificar(datos, meta.get("content_type", ""))
        info = {"tipo": "url", "referencia": _url_sin_query(fuente), "url_final_host": host_de(meta.get("url_final", fuente)),
                "sha256": hashlib.sha256(datos).hexdigest(), "bytes": len(datos), "codificacion": cod,
                "content_type": meta.get("content_type", "").split(";")[0]}
        return texto, info
    if "://" in fuente:
        raise ErrorAnalisis(f"esquema no soportado: {fuente.split('://')[0]}")
    ruta = Path(fuente)
    try:
        st = ruta.stat()
    except OSError as e:
        raise ErrorAnalisis(f"no se puede leer el archivo: {e.strerror}") from e
    if not ruta.is_file():
        raise ErrorAnalisis("la fuente no es un archivo regular")
    if st.st_size > max_bytes:
        raise TamanoExcedido(f"el archivo pesa {st.st_size} bytes y el máximo es {max_bytes}")
    with open(ruta, "rb") as f:
        datos = leer_limitado(f, max_bytes)
    texto, cod = decodificar(datos)
    return texto, {"tipo": "archivo", "referencia": ruta.name, "sha256": hashlib.sha256(datos).hexdigest(), "bytes": len(datos),
                   "codificacion": cod}


def _url_sin_query(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((u.scheme, u.netloc.split("@")[-1], u.path, "", ""))


def analizar_texto(texto: str, *, fuente: Optional[dict] = None, host_propio: str = "", css_externos: Optional[list] = None,
                   con_muestras: bool = True, ahora: Optional[str] = None) -> tuple[dict, dict]:
    """API principal: HTML (texto) → (esqueleto, mapa de ranuras). Sin red."""
    return Analizador(texto, host_propio=host_propio, css_externos=css_externos, con_muestras=con_muestras,
                      fuente=fuente, ahora=ahora).resultado()


def bajar_css_externo(texto_html: str, base_url: str, *, max_bytes: int, timeout: float, abrir: Optional[Callable] = None,
                      permitir_privadas: bool = False, resolver: Optional[Callable[[str], list[str]]] = None) -> list[tuple[str, str]]:
    """Hasta 5 hojas ``<link rel=stylesheet>`` (mismos frenos); las que fallan se omiten sin abortar."""
    p = parsear(texto_html)
    hojas = []
    for n in recorrer(p.raiz):
        if n.tag == "link" and "stylesheet" in n.attrs.get("rel", "").lower() and n.attrs.get("href"):
            url = urllib.parse.urljoin(base_url, n.attrs["href"])
            if len(hojas) >= MAX_CSS_EXTERNOS:
                break
            try:
                datos, _ = descargar(url, max_bytes=max_bytes, timeout=timeout, abrir=abrir, permitir_privadas=permitir_privadas,
                                     comprobar_robots=False, tipos_ok=("text/css", "text/plain"), resolver=resolver)
            except ErrorAnalisis:
                continue
            hojas.append((f"externa:{host_de(url)}{urllib.parse.urlsplit(url).path[-40:]}", decodificar(datos)[0]))
    return hojas


def escribir_salidas(esqueleto: dict, mapa: dict, destino: Path, sobrescribir: bool = False) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    rutas = [destino / "esqueleto_html.json", destino / "mapa_ranuras.json"]
    if not sobrescribir:
        for r in rutas:
            if r.exists():
                raise ErrorAnalisis(f"{r.name} ya existe; usa --sobrescribir para reemplazarlo")
    for r, d in zip(rutas, (esqueleto, mapa)):
        r.write_text(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return rutas


def resumen_texto(esq: dict, mapa: dict) -> str:
    r = esq["resumen"]
    l = [f"bloques: {r['bloques']}  →  {' · '.join(r['orden_de_tipos'])}",
         f"fondos: {' · '.join(r['cadencia_de_fondos'])}",
         f"CTA: {r['ctas']}  por destino: {r['ctas_por_destino']}  textos: {r['textos_de_cta']}",
         f"imágenes: {r['imagenes']}  pestañas: {r['pestanas']}  details: {r['details']}  fijos: {r['elementos_fijos']}",
         f"terceros: {r['terceros']}  píxeles: {r['pixeles']}  enlaces a checkout: {r['enlaces_a_checkout']}",
         f"ranuras: {mapa['resumen']['total_ranuras']}  alertas: {r['alertas']} ({', '.join(sorted({a['codigo'] for a in esq['alertas']})) or 'ninguna'})"]
    return "\n".join(l)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Esqueleto HTML y mapa de ranuras de un referente (el HTML es dato; no se ejecuta).")
    ap.add_argument("fuente", help="URL http(s) o ruta de un archivo HTML local")
    ap.add_argument("--salida", help="carpeta donde escribir esqueleto_html.json y mapa_ranuras.json")
    ap.add_argument("--sobrescribir", action="store_true")
    ap.add_argument("--no-red", action="store_true", help="prohíbe toda conexión (solo archivos locales)")
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES_DEFECTO)
    ap.add_argument("--timeout", type=float, default=TIMEOUT_DEFECTO)
    ap.add_argument("--css-externo", action="store_true", help="baja hasta 5 hojas de estilo externas (necesita red)")
    ap.add_argument("--freno", default=str(FRENO_DEFECTO), help="archivo del freno de captura; si existe, no se abre ninguna URL")
    ap.add_argument("--host-propio", default="")
    ap.add_argument("--sin-muestras", action="store_true")
    ap.add_argument("--permitir-red-privada", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    try:
        if a.max_bytes <= 0 or a.max_bytes > MAX_BYTES_TOPE:
            raise ErrorAnalisis(f"--max-bytes debe estar entre 1 y {MAX_BYTES_TOPE}")
        if a.css_externo and a.no_red:
            raise RedNoPermitida("--css-externo y --no-red son incompatibles")
        texto, info = obtener_texto(a.fuente, no_red=a.no_red, max_bytes=a.max_bytes, timeout=a.timeout,
                                    permitir_privadas=a.permitir_red_privada, freno=Path(a.freno))
        externos = []
        if a.css_externo and info["tipo"] == "url":
            externos = bajar_css_externo(texto, a.fuente, max_bytes=a.max_bytes, timeout=a.timeout, permitir_privadas=a.permitir_red_privada)
        host = a.host_propio or (host_de(a.fuente) if info["tipo"] == "url" else "")
        esq, mapa = analizar_texto(texto, fuente=info, host_propio=host, css_externos=externos, con_muestras=not a.sin_muestras)
        if a.salida:
            rutas = escribir_salidas(esq, mapa, Path(a.salida), a.sobrescribir)
            print("escrito: " + ", ".join(str(r) for r in rutas))
        print(resumen_texto(esq, mapa))
        return 0
    except ErrorAnalisis as e:
        print(f"error: {e}", file=sys.stderr)
        return e.codigo


if __name__ == "__main__":
    sys.exit(main())
