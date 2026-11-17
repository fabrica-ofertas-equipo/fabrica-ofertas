"""``landing.generar``: construye ``05-landing/sitio/`` de forma determinista.

Dos modos, según lo que haya en ``05-landing/``:

* **Sitio diseñado** (hay ``copy.json``, ``paleta.json`` y ``assets.json``): las secciones del plano elegido
  (``referente`` = orden del referente de venta, con barra superior, CTA repetido y botón fijo en móvil; ``clasica`` = las 14
  secciones originales) de ``templates/sitio-base/`` de la skill ``d5-landing-checkout``, CSS con variables de la paleta
  (contraste AA verificado), copy y banner en el ``locale``, imágenes de las ranuras aprobadas, ``/comprar``
  (parte estática), ``/gracias``, las siete legales y ``/desistimiento`` si la ruta existe. Todo texto del
  Maker se escapa (solo ``**negrita**``, ``*énfasis*`` y ``==resaltado==``); una entrada inválida detiene la generación (código 3).
  ``--vista-previa`` (solo preview, NUNCA producción): marcadores de imagen, opiniones y valoración de DEMOSTRACIÓN con cinta «DEMO» y barra fija; ``landing.validar``
  (``L1-DEMO``) y ``landing.desplegar --entorno produccion`` los rechazan. ``--hoy AAAA-MM-DD`` fija la fecha de la barra de lanzamiento (por defecto, la de hoy).
* **Sitio mínimo** (falta alguno de los tres): el comportamiento original de 5 secciones sin diseño, con un aviso.

No inventa producto ni legales reales: las siete páginas legales son una **plantilla genérica por idioma**
(decisión del dueño, 2026-11-06: sin abogado). Las mismas entradas dan los mismos bytes.

CLI::

    python -m landing.generar --oferta OF-202611-01 --raiz /tmp/prueba --json

Siempre escribe en disco (no hay «gasto» ni llamada externa: generar HTML local no es un efecto de
convenciones §9); lo que sí respeta dry-run/--live es ``landing.desplegar``, que publica.
Salida: 0 generado · 2 uso · 3 entrada inválida (esquema, contraste, texto hostil, imagen, plantilla).
"""
from __future__ import annotations

import re
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts import validar_esquemas as V

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion
from landing import comun as lcomun
from landing import contenido, diseno, imagenes, motor, textos
from landing import plantillas as P

__all__ = ["generar_sitio", "generar_sitio_con_avisos", "planificar_sitio", "carpeta_de_salida", "CARPETA_PRODUCCION", "CARPETA_VISTA_PREVIA", "main"]

CARPETA_PRODUCCION = "sitio"
CARPETA_VISTA_PREVIA = "sitio-vista-previa"
_RX_CARPETA = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def carpeta_de_salida(vista_previa: bool = False, salida: str | None = None) -> str:
    """Carpeta (bajo ``05-landing/``) donde se escribe el sitio: ``sitio`` en producción y ``sitio-vista-previa`` con ``--vista-previa`` (F-62: la vista previa NUNCA pisa ``sitio/``,
    que es lo que valida y publica ``landing.desplegar``). ``salida`` la fija a mano (``[a-z0-9_-]``, sin rutas); la vista previa no puede apuntar a ``sitio``."""
    carpeta = salida or (CARPETA_VISTA_PREVIA if vista_previa else CARPETA_PRODUCCION)
    if not _RX_CARPETA.match(carpeta):
        raise ErrorValidacion(f"--salida {carpeta!r} no es válida: solo minúsculas, dígitos, «-» y «_» (una carpeta bajo 05-landing/, sin rutas)")
    if vista_previa and carpeta == CARPETA_PRODUCCION:
        raise ErrorValidacion("la vista previa lleva contenido de demostración y nunca escribe en 05-landing/sitio/ (la carpeta que se valida y se publica): usa sitio-vista-previa o --salida")
    return carpeta

_EXPONENTES = {"JPY": 0, "KRW": 0, "VND": 0, "CLP": 0, "ISK": 0}


# ----------------------------------------------------------------------------------------------
# Sitio mínimo (comportamiento original; sin copy/paleta/assets)
# ----------------------------------------------------------------------------------------------
def _formatear_importe(monto_minor: int, moneda: str) -> str:
    """``19,90 €`` para EUR; para el resto, ``<monto> <MONEDA>`` con el separador decimal ``,`` (modo mínimo)."""
    exp = _EXPONENTES.get(moneda, 2)
    valor = (Decimal(monto_minor) / (Decimal(10) ** exp)).quantize(Decimal(1).scaleb(-exp), rounding=ROUND_HALF_UP)
    texto = f"{valor:,.{exp}f}".replace(",", "_").replace(".", ",").replace("_", ".") if exp else f"{int(valor)}"
    simbolo = {"EUR": "€", "USD": "$", "GBP": "£"}.get(moneda)
    return f"{texto} {simbolo}" if simbolo else f"{texto} {moneda}"


def _rutas_por_defecto(oferta: Mapping[str, Any], *, pago_estatico: bool = False) -> dict[str, str]:
    """Rutas de una oferta sin ``rutas.json``. ``pago_estatico`` = arranque de pago de S-A: ``/comprar`` estática y ``/api/sesion`` dinámica."""
    angulos = oferta.get("angulos") or []
    rutas: dict[str, str] = {}
    if angulos:
        rutas["/"] = angulos[0]["angulo_id"]
        for a in angulos[1:]:
            rutas[f"/a/{a['angulo_id']}"] = a["angulo_id"]
    else:
        rutas["/"] = "portada"
    if pago_estatico:
        rutas[lcomun.RUTA_COMPRAR] = "estatica:comprar"
        rutas[lcomun.RUTA_SESION] = "dinamica:crear-sesion"
    else:
        rutas[lcomun.RUTA_COMPRAR] = "dinamica:crear-sesion"
    rutas["/gracias"] = "estatica:gracias"
    for n in P.LEGALES:
        rutas[f"/legal/{n}"] = f"legal:{n}"
    return rutas


def _pagina(*, locale: str, titulo: str, descripcion: str, dominio: str, ruta_canonica: str,
            og_imagen: str, cuerpo: str, body_attrs: str = "") -> str:
    titulo_e, descripcion_e = escape(titulo), escape(descripcion)
    return (
        "<!doctype html>\n"
        f'<html lang="{escape(locale)}">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{titulo_e}</title>\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta name="description" content="{descripcion_e}">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:title" content="{titulo_e}">\n'
        f'<meta property="og:description" content="{descripcion_e}">\n'
        f'<meta property="og:url" content="https://{escape(dominio)}{ruta_canonica}">\n'
        f'<meta property="og:image" content="https://{escape(dominio)}{og_imagen}">\n'
        '<link rel="stylesheet" href="/css/estilos.css">\n'
        f'<script src="{lcomun.SCRIPT_PERMITIDO}" defer></script>\n'
        f"</head>\n<body{body_attrs}>\n{cuerpo}\n</body>\n</html>\n"
    )


def _faq(oferta: Mapping[str, Any]) -> str:
    items = []
    for o in (oferta.get("avatar") or {}).get("objeciones", []):
        items.append((o["texto"], "Respuesta honesta: no se garantiza un resultado concreto; el producto da un método y materiales de apoyo."))
    tiempo = (oferta.get("promesa") or {}).get("tiempo_prometido_min")
    if tiempo:
        items.append(("¿Cuánto tiempo lleva?", f"Pensado para completarlo en unos {int(tiempo)} minutos."))
    if not items:
        return ""
    piezas = "".join(f"<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>" for q, a in items)
    return f"<section><h2>Preguntas frecuentes</h2>{piezas}</section>"


def _pie_legal(marca: str) -> str:
    enlaces = " · ".join(f'<a href="/legal/{n}">{escape(P.TITULOS_LEGALES[n])}</a>' for n in P.LEGALES)
    return (
        f'<footer><nav aria-label="Legal">{enlaces}</nav>'
        '<p><button type="button" data-consent-abrir>Preferencias de cookies</button></p>'
        f"<p>Contenido informativo de {escape(marca)}. No garantiza resultados.</p></footer>"
    )


def _cuerpo_portada(oferta: Mapping[str, Any], angulo: Mapping[str, Any], precio_texto: str) -> str:
    marca = oferta["marca"]["nombre"]
    promesa = oferta["promesa"]
    garantia = oferta["garantia"]
    secciones = [
        "<header>"
        f'<p class="marca">{escape(marca)}</p>'
        f"<h1>{escape(angulo['hook'])}</h1>"
        f"<p>{escape(promesa['subtitulo'])}</p>"
        f'<img src="/imagenes/hero-placeholder.png" alt="Ilustración de {escape(marca)}" width="640" height="360">'
        f'<a class="cta" href="/comprar">Quiero esto — {escape(precio_texto)}</a>'
        "<p>Pago único. Entrega digital inmediata.</p>"
        "</header>",
        "<main>",
        f"<section><h2>{escape(angulo.get('objecion', ''))}</h2><p>El material te da un método y pasos concretos.</p></section>",
    ]
    claims = [c["texto"] for c in promesa.get("claims_permitidos", [])]
    if claims:
        items = "".join(f"<li>{escape(c)}</li>" for c in claims)
        secciones.append(f"<section><h2>Qué incluye</h2><ul>{items}</ul></section>")
    secciones.append(f"<section><h2>Garantía de {int(garantia['dias'])} días</h2><p>{escape(garantia['texto_visible'])}</p></section>")
    faq = _faq(oferta)
    if faq:
        secciones.append(faq)
    secciones.append("</main>")
    secciones.append(_pie_legal(marca))
    return "".join(secciones)


def _cuerpo_gracias(oferta: Mapping[str, Any]) -> str:
    marca = oferta["marca"]["nombre"]
    return ("<main><h1>Gracias por tu compra</h1><p>En breve recibirás el acceso por correo.</p></main>" + _pie_legal(marca))


def _atributos_de_pagina(oferta: Mapping[str, Any], checkout: Mapping[str, Any], vista_previa: bool = False) -> str:
    """Datos del ``<body>`` de las páginas de producto: los lee ``pixel.js`` (ViewContent) y los verifica el lint. En vista previa suma ``data-vista-previa`` (L1-DEMO lo bloquea)."""
    decimales = V.EXPONENTE_ISO4217.get(checkout["moneda"], 2)
    return (f' data-oferta-id="{escape(oferta["oferta_id"])}" data-precio-minor="{int(checkout["precio"]["monto"])}"'
            f' data-moneda="{escape(checkout["moneda"])}" data-decimales="{decimales}" data-garantia-dias="{int(checkout["garantia_dias"])}"'
            + (' data-vista-previa="1"' if vista_previa else ""))


def _destino_de_ruta(ruta: str) -> str:
    pagina = ruta.strip("/") or "index"
    return "sitio/index.html" if ruta == "/" else f"sitio/{pagina}.html"


def _sitio_minimo(dir_oferta: Path, oferta: Mapping[str, Any], checkout: Mapping[str, Any], tracking: Mapping[str, Any],
                  rutas: Mapping[str, str], escribir: Any, escribir_bytes: Any) -> None:
    locale, dominio, marca = oferta["locale"], oferta["marca"]["dominio"], oferta["marca"]["nombre"]
    angulos = oferta["angulos"]
    precio_texto = _formatear_importe(checkout["precio"]["monto"], checkout["moneda"])
    for ruta, destino in rutas.items():
        if str(destino).startswith(("dinamica:", "legal:", "estatica:")):
            continue
        angulo = next((a for a in angulos if a["angulo_id"] == destino), None)
        if angulo is None:
            continue
        escribir(_destino_de_ruta(ruta), _pagina(
            locale=locale, titulo=f"{marca} — {angulo['hook']}", descripcion=oferta["promesa"]["subtitulo"],
            dominio=dominio, ruta_canonica=ruta, og_imagen="/imagenes/og-placeholder.png",
            cuerpo=_cuerpo_portada(oferta, angulo, precio_texto), body_attrs=_atributos_de_pagina(oferta, checkout),
        ))
    escribir("sitio/gracias.html", _pagina(
        locale=locale, titulo=f"{marca} — Gracias", descripcion="Confirmación de compra", dominio=dominio,
        ruta_canonica="/gracias", og_imagen="/imagenes/og-placeholder.png", cuerpo=_cuerpo_gracias(oferta)))
    for n in P.LEGALES:
        escribir(f"sitio/legal/{n}.html", _pagina(
            locale=locale, titulo=f"{marca} — {P.TITULOS_LEGALES[n]}", descripcion=P.TITULOS_LEGALES[n],
            dominio=dominio, ruta_canonica=f"/legal/{n}", og_imagen="/imagenes/og-placeholder.png",
            cuerpo=f"<main><h1>{escape(P.TITULOS_LEGALES[n])}</h1>"
                   f"{P.pagina_legal(n, marca=marca, dominio=dominio, garantia_dias=oferta['garantia']['dias'])}</main>" + _pie_legal(marca)))
    escribir("sitio/css/estilos.css", P.CSS_BASE)
    escribir("sitio/_headers", P.cabeceras())
    escribir("sitio/js/consentimiento.js", P.consentimiento_js())
    escribir("sitio/js/pixel.js", P.pixel_js(tracking["pixel_id"], _eventos_de_pixel(tracking)))
    for nombre in ("hero-placeholder.png", "og-placeholder.png"):
        ruta_img = dir_oferta / "05-landing" / "imagenes" / nombre
        if not ruta_img.is_file():
            escribir_bytes(f"imagenes/{nombre}", P.PNG_PLACEHOLDER_1X1)


def _eventos_de_pixel(tracking: Mapping[str, Any]) -> list[str]:
    """Eventos de ``tracking.json`` con canal ``pixel``/``ambos`` que el navegador de una página de producto puede emitir."""
    declarados = {e["nombre"] for e in tracking["eventos"] if e.get("canal", "pixel") in ("pixel", "ambos")}
    return [n for n in ("PageView", "ViewContent") if n in declarados]


# ----------------------------------------------------------------------------------------------
# Sitio diseñado
# ----------------------------------------------------------------------------------------------
class _Plantillas:
    """Plantillas compiladas de ``templates/sitio-base/`` (se leen una vez por generación)."""

    def __init__(self) -> None:
        self.dir = contenido.DIR_PLANTILLA
        self._cache: dict[str, list[Any]] = {}

    def texto(self, nombre: str) -> str:
        ruta = self.dir / nombre
        if not ruta.is_file():
            raise ErrorValidacion(f"falta la plantilla sitio-base: {ruta}")
        return ruta.read_text(encoding="utf-8")

    def render(self, nombre: str, ctx: Mapping[str, Any]) -> motor.Seguro:
        if nombre not in self._cache:
            self._cache[nombre] = motor.compilar(self.texto(nombre), nombre)
        return motor.renderizar(self._cache[nombre], dict(ctx), nombre)


def _sitio_disenado(dir_oferta: Path, e: contenido.Entradas, escribir: Any, escribir_bytes: Any, avisos: list[str]) -> None:  # noqa: C901 - orquestación lineal
    oferta, checkout, tracking, land = e.oferta, e.checkout, e.tracking, e.dir_landing
    locale, dominio = oferta["locale"], oferta["marca"]["dominio"]
    if not textos.idioma_de(locale)[1]:
        avisos.append(f"idioma {locale.split('-')[0]!r} sin tabla en landing/textos.py: rótulos y legales en inglés (añadir la tabla antes de publicar)")

    # Diseño: paleta -> variables CSS con AA verificado (propio + el script de la skill si existe).
    def existe_fuente(archivo: str) -> bool:
        return (land / archivo).is_file() or (land / "sitio" / archivo).is_file()

    d = diseno.construir_diseno(e.paleta, existe_fuente=existe_fuente)
    de_skill = diseno.revisar_con_skill(e.paleta)
    if de_skill:
        raise ErrorValidacion("paleta.json: contraste_paleta.py reporta " + " | ".join(de_skill), detalle={"hallazgos": de_skill})
    avisos += d.avisos

    imgs, av_img = imagenes.resolver_imagenes(e.assets, land)
    avisos += av_img
    for slot_id, donde in (("compra", "S11: la tarjeta de compra va sin imagen"), ("og", "og: sin imagen para compartir (no se emite og:image)")):
        if slot_id not in imgs and any(x["slot_id"] == slot_id and x["estado"] != "omitida" for x in e.assets["slots"]):
            avisos.append(f"ranura {slot_id} sin imagen aprobada: {donde}")
    cp = contenido.expandir(e)
    avisos += contenido.comprobar_coherencia(e, cp)
    plan = contenido.manifiesto()
    plantillas = _Plantillas()
    sprite = motor.Seguro(plantillas.texto("sprite.html"))
    meta = contenido.meta_de_pagina(e, cp)
    t = textos.rotulos(locale)
    marca = oferta["marca"]["nombre"]
    og = imgs.get("og")
    og_imagen = f"https://{dominio}{og.url}" if og else None
    precargas = [{"href": "/" + a} for a in d.precargas]
    cta = {c["id"]: c["texto"] for c in cp["cta"]}
    precio = textos.formatear_importe(checkout["precio"]["monto"], checkout["moneda"], locale)
    metodos = " · ".join(textos.etiqueta_metodo(m, locale) for m in checkout.get("metodos") or [])

    vista_previa = {"barra": textos.TEXTO_VISTA_PREVIA["barra"]} if e.vista_previa else None
    plano_ref = contenido.plano_de(cp) == "referente"
    attrs_producto = _atributos_de_pagina(oferta, checkout, e.vista_previa)

    def pagina(*, ruta: str, titulo: str, descripcion: str, og_titulo: str, og_descripcion: str, cuerpos: list[motor.Seguro], pie: motor.Seguro,
               body_attrs: str = "", cta_cabecera: str | None = None, barra: Mapping[str, str] | None = None, script_turnstile: str | None = None,
               barra_superior: Mapping[str, Any] | None = None, tono_cabecera: str = "oscuro") -> str:
        if e.vista_previa and 'data-vista-previa' not in body_attrs:
            body_attrs += ' data-vista-previa="1"'
        if plano_ref:
            body_attrs = ' class="plano-referente"' + body_attrs
        return str(plantillas.render("base.html", {
            "lang": locale, "titulo": titulo, "descripcion": descripcion, "color_tema": d.color_tema, "og_titulo": og_titulo,
            "og_descripcion": og_descripcion, "og_url": f"https://{dominio}{ruta}", "og_imagen": og_imagen, "precargas": precargas,
            "body_attrs": motor.Seguro(body_attrs), "t": t, "sprite": sprite, "marca": marca, "cta_cabecera": cta_cabecera,
            "secciones": [{"html": c} for c in cuerpos], "barra": barra, "pie": pie, "script_turnstile": script_turnstile,
            "barra_superior": barra_superior, "tono_cabecera": tono_cabecera, "vista_previa": vista_previa,
        }))

    # Páginas de ángulo (una por ruta; mismo plano, solo cambian los cuatro bloques variables).
    ruta_de_angulo = {dest: r for r, dest in e.rutas.items() if not str(dest).startswith(("dinamica:", "legal:", "estatica:"))}
    angulos_validos = {a["angulo_id"] for a in oferta["angulos"]}
    ultima_cola: dict[str, str] = {}
    omitidas_vistas: set[str] = set()
    for angulo_id, ruta in ruta_de_angulo.items():
        if angulo_id not in angulos_validos:
            continue
        if angulo_id not in cp["variantes_por_angulo"]:
            avisos.append(f"copy.json no trae variantes_por_angulo[{angulo_id!r}]: la ruta {ruta} usa el copy base")
        secciones, av_sec, barra = contenido.contexto_secciones(e, cp, imgs, angulo_id, d.alternos, plan)
        for a in av_sec:
            if a not in omitidas_vistas:
                omitidas_vistas.add(a)
                avisos.append(a)
        cuerpos = []
        for x in secciones:
            cx = dict(x["ctx"])
            cx["cta_html"] = (plantillas.render("secciones/cta-bloque.html", {"cta_bloque": {"texto": cx["cta_texto"]}}) if x["spec"].get("cta") else motor.Seguro(""))
            cuerpos.append(plantillas.render("secciones/" + x["spec"]["plantilla"], cx))
        pie_ctx = contenido.contexto_pie(e, cp, barra["ultimo_tono"], d.alternos)
        pie = plantillas.render("pie.html", pie_ctx)
        ultima_cola[angulo_id] = barra["ultimo_tono"]
        escribir(_destino_de_ruta(ruta), pagina(
            ruta=ruta, titulo=meta["title"], descripcion=meta["description"], og_titulo=meta["og_title"], og_descripcion=meta["og_description"],
            cuerpos=cuerpos, pie=pie, body_attrs=attrs_producto, cta_cabecera=secciones[0]["ctx"]["cta"]["texto"],
            barra={"precio": barra["precio"], "texto": barra["texto"]}, barra_superior=barra["superior"], tono_cabecera=barra["primer_tono"]))

    pie_comun = plantillas.render("pie.html", contenido.contexto_pie(e, cp, "claro", d.alternos))

    # /gracias
    g = cp["secciones"]["gracias"]
    escribir("sitio/gracias.html", pagina(
        ruta="/gracias", titulo=f"{marca} — {motor.texto_plano(g['titulo'])}", descripcion=meta["description"], og_titulo=meta["og_title"],
        og_descripcion=meta["og_description"], pie=pie_comun,
        cuerpos=[plantillas.render("gracias.html", {"titulo": motor.md(g["titulo"]), "texto": motor.md(g["texto"]), "t": t})]))

    # /comprar: página ESTÁTICA con UN formulario hacia /api/sesion (docs/_historial/decision-arranque-de-pago.md).
    c = cp["secciones"]["comprar"]
    ruta_comprar = e.rutas.get(lcomun.RUTA_COMPRAR)
    if ruta_comprar == "estatica:comprar":
        if not str(e.rutas.get(lcomun.RUTA_SESION, "")).startswith("dinamica:"):
            avisos.append("rutas.json no declara /api/sesion como dinamica:crear-sesion: el formulario de /comprar no tiene destino (L1-RUTAS)")
        ts = lcomun.turnstile(checkout)
        bloque_ts = checkout.get("turnstile")
        if isinstance(bloque_ts, dict):
            secretas = [k for k in bloque_ts if any(m in k.lower() for m in lcomun.CLAVES_SECRETAS_TURNSTILE)]
            if secretas or set(bloque_ts) - {"habilitado", "sitekey"}:
                raise ErrorValidacion("checkout.json › turnstile solo admite {habilitado, sitekey}: la clave SECRETA de Turnstile no va en checkout.json ni en landing/ "
                                      f"(claves no admitidas: {sorted(set(bloque_ts) - {'habilitado', 'sitekey'})})")
        if ts is not None and not re.fullmatch(r"[0-9A-Za-z_-]{8,64}", str(ts.get("sitekey", ""))):
            raise ErrorValidacion("checkout.json › turnstile.habilitado exige turnstile.sitekey (clave pública del widget, 8-64 caracteres [0-9A-Za-z_-])")
        formulario = _contexto_formulario(e, cp, c, avisos)
        formulario.update(titulo=motor.md(c["titulo"]), resumen=[motor.md(x) for x in c["resumen_prepago"]], boton=c["boton"], precio=precio, metodos=metodos,
                          legales=[{"href": f"/legal/{n}", "texto": cp["secciones"]["S14"]["enlaces"][n]} for n in ("terminos", "reembolsos")], t=t,
                          turnstile={"sitekey": ts["sitekey"]} if ts else None)
        if ts:
            avisos.append("Turnstile habilitado: UN script externo exacto, solo en /comprar (su CSP aparte en _headers); no es el arranque por defecto")
        escribir("sitio/comprar.html", pagina(
            ruta=lcomun.RUTA_COMPRAR, titulo=f"{marca} — {motor.texto_plano(c['titulo'])}", descripcion=meta["description"], og_titulo=meta["og_title"],
            og_descripcion=meta["og_description"], pie=pie_comun, cuerpos=[plantillas.render("comprar.html", formulario)],
            script_turnstile=lcomun.URL_TURNSTILE if ts else None))
    else:
        avisos.append("rutas.json no declara /comprar como estatica:comprar: no se genera comprar.html (actualizar rutas.json: /comprar=estatica:comprar y "
                      "/api/sesion=dinamica:crear-sesion)")
        ts = None

    # Legales (plantilla genérica por idioma) y /desistimiento si la ruta existe.
    titulos_legales = textos.titulos_legales(locale)
    garantia = int(oferta["garantia"]["dias"])
    for n in P.LEGALES:
        cuerpo = plantillas.render("legal.html", {"titulo": titulos_legales[n], "marca": marca, "parrafos": list(
            textos.cuerpo_legal(n, locale, marca=marca, dominio=dominio, garantia_dias=garantia))})
        escribir(f"sitio/legal/{n}.html", pagina(
            ruta=f"/legal/{n}", titulo=f"{marca} — {titulos_legales[n]}", descripcion=titulos_legales[n], og_titulo=titulos_legales[n],
            og_descripcion=titulos_legales[n], cuerpos=[cuerpo], pie=pie_comun))
    if "/desistimiento" in e.rutas:
        etiqueta = cp["secciones"]["S14"]["enlaces"]["desistimiento"]
        dias = _dias_desistimiento(dir_oferta, garantia)
        cuerpo = plantillas.render("legal.html", {"titulo": etiqueta, "marca": marca, "parrafos": list(
            textos.cuerpo_desistimiento(locale, dias=dias, garantia_dias=garantia))})
        escribir("sitio/desistimiento.html", pagina(
            ruta="/desistimiento", titulo=f"{marca} — {etiqueta}", descripcion=etiqueta, og_titulo=etiqueta, og_descripcion=etiqueta,
            cuerpos=[cuerpo], pie=pie_comun))

    # CSS, JS e imágenes/fuentes.
    css = (plantillas.texto("estilos.css").replace("/*@TOKENS@*/", d.css_tokens).replace("/*@FUENTES@*/", d.css_fuentes))
    escribir("sitio/css/estilos.css", css)
    escribir("sitio/_headers", P.cabeceras(turnstile=ts is not None))
    dur_vid, dur_attr = _duraciones_de_cookies(dir_oferta, avisos)
    b = cp["secciones"]["banner"]
    banner = {"titulo": t["banner_titulo"], "cuerpo": motor.texto_plano(b["texto"]), "aceptar": b["aceptar"], "rechazar": b["rechazar"],
              "personalizar": b["personalizar"], "guardar": b["guardar"], "necesarias": t["banner_necesarias"],
              "marketing": b["etiqueta_marketing"], "mas": t["banner_mas"]}
    escribir("sitio/js/consentimiento.js", P.consentimiento_js(banner, b["version_texto"], duracion_vid_s=dur_vid, duracion_attr_s=dur_attr))
    escribir("sitio/js/pixel.js", P.pixel_js(tracking["pixel_id"], _eventos_de_pixel(tracking)))
    for im in sorted(imgs.values(), key=lambda x: x.destino):
        escribir_bytes(f"sitio/{im.destino}", im.origen.read_bytes())
    for archivo in d.fuentes:
        origen = land / archivo
        if origen.is_file():
            escribir_bytes(f"sitio/{archivo}", origen.read_bytes())


DIAS_COOKIE_VID = 90      # [HIPÓTESIS] hasta que empresa/parametros.yaml defina landing.cookie_vid_dias
DIAS_COOKIE_ATTR = 30     # [HIPÓTESIS] hasta que empresa/parametros.yaml defina landing.cookie_attr_dias


def _duraciones_de_cookies(dir_oferta: Path, avisos: list[str]) -> tuple[int, int]:
    """Segundos de vida de ``fab_vid`` y ``fab_attr``: ``parametros.landing.cookie_{vid,attr}_dias`` (tope ``TOPE_DIAS_COOKIE``) o, si faltan (CT-3 los agrega),
    el respaldo aprobado por S-A (90 y 30 días, [HIPÓTESIS]) con aviso. Un valor sobre el tope detiene la generación."""
    vid, attr = lcomun.parametro_landing(dir_oferta, "cookie_vid_dias"), lcomun.parametro_landing(dir_oferta, "cookie_attr_dias")
    for clave, valor in (("cookie_vid_dias", vid), ("cookie_attr_dias", attr)):
        if valor is not None and valor > lcomun.TOPE_DIAS_COOKIE:
            raise ErrorValidacion(f"empresa/parametros.yaml: landing.{clave} = {valor} supera el tope de {lcomun.TOPE_DIAS_COOKIE} días")
    if vid is None or attr is None:
        avisos.append(f"empresa/parametros.yaml sin landing.cookie_vid_dias / cookie_attr_dias: se usan {DIAS_COOKIE_VID} y {DIAS_COOKIE_ATTR} días "
                      "[HIPÓTESIS, respaldo aprobado por S-A] hasta que CT-3 los agregue a parametros.landing")
    return (vid or DIAS_COOKIE_VID) * 86400, (attr or DIAS_COOKIE_ATTR) * 86400


def _contexto_formulario(e: contenido.Entradas, cp: Mapping[str, Any], c: Mapping[str, Any], avisos: list[str]) -> dict[str, Any]:
    """Campos del formulario de /comprar: ``oferta_id`` y ``locale`` (ocultos), ``bump`` solo con ``bump_modo = oferta_previa`` y la casilla
    ``renuncia_desistimiento`` solo si ``checkout.compra.renuncia.requerido`` (o, sin él, el criterio provisional por locale) lo exige. Nunca premarcadas."""
    oferta, checkout = e.oferta, e.checkout
    requerida, version, desde_contrato = lcomun.renuncia(oferta, checkout)
    if not desde_contrato:
        avisos.append("checkout.json › compra.renuncia.requerido ausente: la casilla de renuncia se decide por el locale (UE/UK) [criterio provisional]")
    casillas = {x["id"]: x for x in c["casillas"]}
    renuncia_copy = casillas.get("renuncia-entrega-inmediata")
    renuncia = None
    if requerida:
        if renuncia_copy is None:
            raise ErrorValidacion("copy.json: comprar.casillas no trae «renuncia-entrega-inmediata» y la compra exige la casilla de renuncia al desistimiento"
                                  f" (locale {oferta['locale']})")
        renuncia = {"texto": motor.md(renuncia_copy["texto"]), "version": version}
    elif renuncia_copy is not None:
        avisos.append("comprar.casillas[renuncia-entrega-inmediata] no se muestra: la compra no exige la casilla de renuncia")
    if "terminos-y-desistimiento" in casillas:
        avisos.append("comprar.casillas[terminos-y-desistimiento] no es un campo del formulario (solo bump y renuncia_desistimiento): los términos se enlazan debajo del botón")
    bump = None
    if lcomun.modo_bump(checkout) == "oferta_previa":
        s9 = (cp["secciones"].get("S09") or {}).get("bump")
        if not s9:
            raise ErrorValidacion("checkout.json: bump_modo oferta_previa exige S09.bump en copy.json (texto de la casilla)")
        bump = {"texto": motor.md(s9["etiqueta_casilla"])}
    return {"oferta_id": oferta["oferta_id"], "locale": oferta["locale"], "bump": bump, "renuncia": renuncia}


def _dias_desistimiento(dir_oferta: Path, por_defecto: int) -> int:
    """Días del derecho de desistimiento de ``mercado.consumo.desistimiento_dias`` (o la garantía si no hay ``mercado.json``)."""
    ruta = dir_oferta / "mercado.json"
    if ruta.is_file():
        dias = ((comun.cargar_json(ruta).get("consumo") or {}).get("desistimiento_dias"))
        if isinstance(dias, int) and dias > 0:
            return dias
    return por_defecto


# ----------------------------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------------------------
def planificar_sitio(dir_oferta: Path, *, vista_previa: bool = False, hoy: date | None = None, salida: str | None = None
                     ) -> tuple[dict[str, bytes], dict[str, str], list[str]]:
    """Calcula TODO lo que ``landing.generar`` escribiría sin tocar el disco: ``(archivos, texto, avisos)``.

    ``archivos`` es el mapa ``ruta relativa a 05-landing/ -> bytes`` (HTML, CSS, JS, imágenes y fuentes copiadas, ``rutas.json`` si falta,
    marcadores de posición del sitio mínimo si faltan); ``texto`` es el subconjunto de texto (``ruta -> str``). Solo lee. Errores:
    ``ErrorValidacion`` si falta un campo obligatorio de ``oferta.json``/``checkout.json`` o si ``copy.json``/``paleta.json``/``assets.json``
    (cuando existen los tres) son inválidos, con contraste insuficiente, imágenes no válidas o texto hostil.

    ``vista_previa=True``: marcadores de imagen, opiniones/valoración de DEMOSTRACIÓN (cinta «DEMO») y barra fija «VISTA PREVIA»; el sitio resultante NO es publicable
    (``landing.validar`` L1-DEMO) y se escribe en ``sitio-vista-previa/``, nunca en ``sitio/``. ``salida``: carpeta de destino bajo ``05-landing/`` (ver
    :func:`carpeta_de_salida`). ``hoy``: fecha con la que se decide si la barra de lanzamiento sigue vigente (por defecto, la fecha actual).
    """
    carpeta = carpeta_de_salida(vista_previa, salida)
    oferta = lcomun.cargar_oferta(dir_oferta)
    checkout = lcomun.cargar_checkout(dir_oferta)
    tracking = lcomun.cargar_tracking(dir_oferta)
    try:
        oferta["locale"], oferta["marca"]["dominio"], oferta["marca"]["nombre"]
        if not oferta["angulos"]:
            raise KeyError("angulos")
    except KeyError as exc:
        raise ErrorValidacion(f"oferta.json incompleto para generar la landing: falta {exc.args[0]}") from exc

    rutas_existentes = lcomun.cargar_rutas(dir_oferta)
    rutas = rutas_existentes or _rutas_por_defecto(oferta)
    producto = lcomun.cargar_producto(dir_oferta)
    avisos: list[str] = []
    archivos: dict[str, bytes] = {}
    texto: dict[str, str] = {}

    def destino(rel: str) -> str:
        return carpeta + rel[len(CARPETA_PRODUCCION):] if rel.startswith(CARPETA_PRODUCCION + "/") else rel

    def escribir(rel: str, contenido_: str) -> None:
        rel = destino(rel)
        texto[rel] = contenido_
        archivos[rel] = contenido_.encode("utf-8")

    def escribir_bytes(rel: str, datos: bytes) -> None:
        archivos[destino(rel)] = datos

    entradas, av = contenido.cargar_entradas(dir_oferta, oferta=oferta, checkout=checkout, tracking=tracking, rutas=rutas, producto=producto,
                                             hoy=hoy, vista_previa=vista_previa)
    avisos += av
    if vista_previa and entradas is None:
        avisos.append("vista previa sin copy.json, paleta.json y assets.json: el sitio mínimo no lleva elementos de demostración")
    if vista_previa and entradas is not None:
        avisos.append(f"VISTA PREVIA: el sitio lleva marcadores y contenido de demostración (cinta DEMO); NO es publicable (L1-DEMO lo bloquea); se escribe en 05-landing/{carpeta}/")
    if entradas is not None and not rutas_existentes:
        rutas = entradas.rutas = _rutas_por_defecto(oferta, pago_estatico=True)    # sitio diseñado: /comprar estática y /api/sesion dinámica
    if entradas is None:
        _sitio_minimo(dir_oferta, oferta, checkout, tracking, rutas, escribir, escribir_bytes)
    else:
        _sitio_disenado(dir_oferta, entradas, escribir, escribir_bytes, avisos)
    if not rutas_existentes:
        escribir_bytes("rutas.json", comun.json_canonico(rutas))
    return archivos, texto, avisos


def generar_sitio_con_avisos(dir_oferta: Path, plantillas: Any = P, *, vista_previa: bool = False, hoy: date | None = None, salida: str | None = None
                             ) -> tuple[dict[str, str], list[str]]:
    """Genera ``05-landing/sitio/`` (``sitio-vista-previa/`` con ``vista_previa``; o ``salida``) y ``rutas.json`` si falta; devuelve ``(archivos de texto, avisos)``.

    ``archivos de texto`` es el mapa ``ruta relativa (bajo 05-landing) -> contenido`` de HTML/CSS/JS; las imágenes y fuentes
    se copian aparte (bytes). Primero se calcula todo en memoria (:func:`planificar_sitio`) y solo entonces se escribe: una entrada
    inválida no deja el sitio a medias. Errores: los de :func:`planificar_sitio`.
    """
    archivos, texto, avisos = planificar_sitio(dir_oferta, vista_previa=vista_previa, hoy=hoy, salida=salida)
    land = dir_oferta / "05-landing"
    for rel in sorted(archivos):
        comun.escribir_atomico(land / rel, archivos[rel])
    return texto, avisos


def generar_sitio(dir_oferta: Path, plantillas: Any = P, *, vista_previa: bool = False, hoy: date | None = None, salida: str | None = None) -> dict[str, str]:
    """Compatible con la versión anterior: igual que :func:`generar_sitio_con_avisos` pero devuelve solo los archivos de texto."""
    return generar_sitio_con_avisos(dir_oferta, plantillas, vista_previa=vista_previa, hoy=hoy, salida=salida)[0]


def _hoy(args: Any) -> date | None:
    return date.fromisoformat(args.hoy) if getattr(args, "hoy", None) else None


def main(argv: Sequence[str] | None = None) -> int:
    ap = lcomun.argparser_base("Genera 05-landing/sitio/ desde oferta/checkout/tracking y, si existen, copy.json, paleta.json y assets.json.")
    ap.add_argument("--simular", "--dry-run", dest="simular", action="store_true",
                    help="no escribe nada: valida las entradas y reporta los archivos que generaría (tamaño y sha256) y los avisos")
    ap.add_argument("--vista-previa", dest="vista_previa", action="store_true",
                    help="SOLO preview: marcadores de imagen, opiniones/valoración de DEMOSTRACIÓN (cinta DEMO) y barra fija; nunca con FABRICA_ENTORNO=produccion")
    ap.add_argument("--hoy", help="AAAA-MM-DD: fecha de generación para la barra de lanzamiento (por defecto, hoy)")
    ap.add_argument("--salida", help="carpeta de destino bajo 05-landing/ (por defecto sitio; con --vista-previa, sitio-vista-previa; la vista previa no puede usar sitio)")
    args = ap.parse_args(argv)

    def cuerpo() -> int:
        env = lcomun.entorno_de_proceso()
        if args.vista_previa and comun.entorno(env) == "produccion":
            raise ErrorUso("--vista-previa no existe con FABRICA_ENTORNO=produccion: la vista previa lleva contenido de demostración")
        if args.hoy and not contenido.RX_FECHA.match(args.hoy):
            raise ErrorUso("--hoy debe ser AAAA-MM-DD")
        if args.vista_previa and args.salida == CARPETA_PRODUCCION:
            raise ErrorUso("--vista-previa no puede escribir en sitio/: usa sitio-vista-previa (por defecto) o --salida")
        raiz = lcomun.raiz_de_argumentos(args, env)
        d = lcomun.dir_oferta(args.oferta, raiz=raiz)
        try:
            return _ejecutar(d, args)
        except ErrorValidacion as exc:
            if args.json:      # la consola lee JSON: el error sale también por stdout; el código y stderr los pone ejecutar_cli
                import json as _json
                print(_json.dumps({"ok": False, "modo": "simulacion" if args.simular else "dry_run", "codigo": 3,
                                   "datos": {"oferta_id": args.oferta, "errores": [exc.mensaje]}, "avisos": []}, sort_keys=True, ensure_ascii=False))
            raise

    def _ejecutar(d: Path, args: Any) -> int:
        if args.simular:
            archivos, _texto, avisos = planificar_sitio(d, vista_previa=args.vista_previa, hoy=_hoy(args), salida=args.salida)
            detalle = [{"ruta": rel, "bytes": len(archivos[rel]), "sha256": V.hash_bytes(archivos[rel])} for rel in sorted(archivos)]
            datos = {"oferta_id": args.oferta, "simulacion": True, "carpeta": carpeta_de_salida(args.vista_previa, args.salida), "archivos": [x["ruta"] for x in detalle], "detalle": detalle,
                     "total_bytes": sum(x["bytes"] for x in detalle), "landing_version": lcomun.landing_version(lcomun.cargar_checkout(d))}
            modo = "simulacion"
        else:
            salida, avisos = generar_sitio_con_avisos(d, vista_previa=args.vista_previa, hoy=_hoy(args), salida=args.salida)
            datos = {"oferta_id": args.oferta, "carpeta": carpeta_de_salida(args.vista_previa, args.salida), "archivos": sorted(salida),
                     "landing_version": lcomun.landing_version(lcomun.cargar_checkout(d))}
            modo = "dry_run"        # valor histórico de este campo: el modo por defecto SÍ escribe (HTML local, no un efecto externo)
        if args.json:
            import json as _json
            print(_json.dumps({"ok": True, "modo": modo, "codigo": 0, "datos": datos, "avisos": avisos}, sort_keys=True, ensure_ascii=False))
        elif args.simular:
            print(f"simulación (no se escribió nada): {len(datos['detalle'])} archivos, {datos['total_bytes']} bytes")
            if datos["landing_version"]:
                print(f"  landing_version (checkout.compra): {datos['landing_version']}")
            for x in datos["detalle"]:
                print(f"  {x['bytes']:>8}  {x['sha256']}  {x['ruta']}")
            for a in avisos:
                print(f"aviso: {a}", file=sys.stderr)
        else:
            print(f"generado: {len(salida)} archivos en {d / '05-landing' / carpeta_de_salida(args.vista_previa, args.salida)}")
            for a in avisos:
                print(f"aviso: {a}", file=sys.stderr)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
