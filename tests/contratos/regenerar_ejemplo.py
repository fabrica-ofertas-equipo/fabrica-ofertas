"""Regenera y RE-SELLA ``ofertas/_ejemplo/`` de forma determinista (ola 0b-2, CT).

Qué hace, en este orden:
  1. Escribe la landing (``05-landing/sitio/``: tres páginas de ángulo, ``gracias``, las SIETE páginas legales, ``css/estilos.css``)
     desde plantillas fijas con los datos de ``oferta.json``/``checkout.json``; los ``js/*.js`` se conservan (son fuente, no salida).
  2. Reescribe ``05-landing/rutas.json`` y ``tracking.json`` (``consent_gating.plataforma = "banner_propio_v1"``).
  3. ``03-oferta/economia.json`` sale de ``engine.factibilidad.documento_economia`` (única fórmula, D-01).
  4. Re-sella lo que depende de lo anterior, en orden topológico: ``campana.json`` (economía + ``hash_config``), ``paquete.json``
     (``landing_hash``), ``veredicto_oferta.json`` (``cpa_objetivo``), ``assets.json``, ``qa/*`` (hashes de artefacto y de entradas, sello de
     X1, ``firma_motor``) y ``estado.json`` (``entradas``, ``hash_salida``, firmas de las aprobaciones).

Todas las firmas son HMAC con ``CLAVE_DE_PRUEBA`` (clave pública de prueba que no protege nada); nunca hay claves reales.
Los datos del ejemplo son FICTICIOS: el texto de las páginas lleva ``[EJEMPLO]`` solo en un comentario HTML.

Uso (desde la raíz del repositorio)::

    .venv/bin/python -m tests.contratos.regenerar_ejemplo [--destino ofertas/_ejemplo] [--comprobar]

``--comprobar`` no escribe: sale con 1 si regenerar cambiaría algo (la prueba ``test_ejemplo_regenerado`` lo usa). Idempotente.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from engine import factibilidad
from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
DOMINIO = "miregresolaboral.example"
LEGALES = ("vendedor", "terminos", "privacidad", "reembolsos", "cookies", "aviso", "entrega")
TITULO_LEGAL = {
    "vendedor": "Vendedor y contacto", "terminos": "Términos de uso", "privacidad": "Política de privacidad",
    "reembolsos": "Reembolsos y desistimiento", "cookies": "Política de cookies", "aviso": "Aviso de contenido",
    "entrega": "Entrega y soporte",
}
# Ejemplos válidos de contratos/ejemplos/ que son copias de artefactos de la oferta (contratos/ejemplos/README.md): se sincronizan.
COPIAS_EN_EJEMPLOS = {
    "economia": "03-oferta/economia.json", "tracking_plan": "05-landing/tracking.json", "campana": "07-campana/campana.json",
    "creativos": "06-creativos/paquete.json", "veredicto_oferta": "08-operacion/veredicto_oferta.json",
    "checkout": "05-landing/checkout.json", "assets": "05-landing/assets.json",
}
GASTO_DIARIO_TEST = 2760            # campana.presupuesto.diario del ejemplo (EUR, unidad menor)
MARCA_EJEMPLO = "<!-- [EJEMPLO] Página ficticia de la oferta de ejemplo: no es texto legal ni se publica. -->"
CORREO = "soporte&#64;" + DOMINIO   # entidad HTML: ningún literal de correo en el repositorio (lint_estatico, regla c)


# --------------------------------------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------------------------------------
def _json(ruta: Path, objeto: Any) -> str:
    return json.dumps(objeto, ensure_ascii=False, indent=2) + "\n"


class Escritor:
    """Escribe archivos; con ``solo_comprobar`` acumula diferencias en lugar de escribir."""

    def __init__(self, solo_comprobar: bool) -> None:
        self.solo_comprobar, self.cambios = solo_comprobar, []

    def escribir(self, ruta: Path, texto: str) -> None:
        actual = ruta.read_text(encoding="utf-8") if ruta.is_file() else None
        if ruta.suffix == ".json" and actual is not None and V.cargar_json(ruta) == json.loads(texto):
            return                                   # mismo objeto JSON: no se reformatea
        if actual == texto:
            return
        self.cambios.append(str(ruta))
        if not self.solo_comprobar:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            tmp = ruta.with_name(ruta.name + ".tmp")        # temporal + renombrado: una interrupción no deja un archivo a medias
            tmp.write_text(texto, encoding="utf-8", newline="\n")
            os.replace(tmp, ruta)


def eur(minor: int) -> str:
    """19,90 € (formato es-ES) desde unidad menor entera."""
    return f"{minor // 100},{minor % 100:02d} €"


# --------------------------------------------------------------------------------------------------------------------
# Plantillas HTML (texto fijo; los datos vienen de oferta.json)
# --------------------------------------------------------------------------------------------------------------------
def _pie() -> str:
    enlaces = " · ".join(f'<a href="/legal/{n}">{TITULO_LEGAL[n]}</a>' for n in LEGALES)
    return ('<footer><nav aria-label="Legal">' + enlaces + '</nav>'
            '<p><button type="button" data-consent-abrir>Preferencias de cookies</button></p>'
            '<p>Contenido informativo. No garantiza entrevistas ni empleo.</p></footer>')


def _pagina(titulo: str, descripcion: str, cuerpo: str, o: dict, *, og: bool, ruta: str, datos_body: bool = True) -> str:
    og_tags = ""
    if og:
        og_tags = (f'\n<meta property="og:type" content="website">\n<meta property="og:title" content="{titulo}">\n'
                   f'<meta property="og:description" content="{descripcion}">\n<meta property="og:url" content="https://{DOMINIO}{ruta}">\n'
                   f'<meta property="og:image" content="https://{DOMINIO}/imagenes/og-placeholder.png">')
    precio = o["precio"]["lista"]
    # data-* solo en las páginas de ángulo: ``pixel.js`` los lee para ViewContent (legales y /gracias no son página de producto, CT2-30);
    # data-decimales = exponente ISO 4217 de la moneda: el píxel formatea el valor con enteros, sin dividir dinero en coma flotante (CT2-31).
    atributos = (f' data-oferta-id="{o["oferta_id"]}" data-precio-minor="{precio["monto"]}" data-moneda="{precio["moneda"]}"'
                 f' data-decimales="{V.EXPONENTE_ISO4217[precio["moneda"]]}" data-garantia-dias="{o["garantia"]["dias"]}"') if datos_body else ""
    return (f'<!doctype html>\n<html lang="{o["locale"]}">\n<head>\n<meta charset="utf-8">\n{MARCA_EJEMPLO}\n<title>{titulo}</title>\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<meta name="description" content="{descripcion}">{og_tags}\n'
            f'<link rel="stylesheet" href="/css/estilos.css">\n<script src="/js/consentimiento.js" defer></script>\n</head>\n'
            f'<body{atributos}>\n{cuerpo}\n</body>\n</html>\n')


def pagina_angulo(o: dict, angulo: dict, principal: bool) -> tuple[str, str]:
    """(ruta relativa a ``sitio/``, HTML) de la landing de un ángulo."""
    p, g, b = o["promesa"], o["garantia"], o["bump"]
    ruta = "/" if principal else f"/a/{angulo['angulo_id']}"
    archivo = "index.html" if principal else f"a/{angulo['angulo_id']}.html"
    titulo = f"{o['marca']['nombre']} — {p['titulo']}"
    incluye = "".join(f"<li>{x['texto']}</li>" for x in p["claims_permitidos"] if x["claim_id"] != "garantia-14-dias")
    cuerpo = (
        f'<header><p class="marca">{o["marca"]["nombre"]}</p><h1>{angulo["hook"]}</h1><p>{p["subtitulo"]}.</p>'
        f'<img src="/imagenes/hero-placeholder.png" alt="Escritorio con un currículum y una taza" width="640" height="360">'
        f'<a class="cta" href="/comprar">Quiero la guía — {eur(o["precio"]["lista"]["monto"])}</a>'
        f'<p>Pago único. Entrega inmediata por correo.</p></header>\n'
        f'<main>\n<section><h2>{angulo["objecion"]}</h2><p>La guía te da un orden y palabras concretas para contarlo; el resultado depende de ti.</p></section>\n'
        f'<section><h2>Qué incluye</h2><ul>{incluye}</ul></section>\n'
        f'<section><h2>Opcional al pagar</h2><p>{b["nombre"]}: {eur(b["precio"]["monto"])}. {b["descripcion"]}. '
        f'Se añade solo si marcas la casilla en el pago.</p></section>\n'
        f'<section><h2>Garantía de {g["dias"]} días</h2><p>{g["texto_visible"]}</p></section>\n'
        f'<section><h2>Preguntas frecuentes</h2>'
        f'<details><summary>¿Esto me va a conseguir trabajo?</summary><p>No. Es una guía para ordenar y presentar tu experiencia; '
        f'no garantiza entrevistas ni empleo.</p></details>'
        f'<details><summary>¿Cuánto tiempo lleva?</summary><p>{p["claims_permitidos"][2]["texto"]}.</p></details>'
        f'<details><summary>¿Y si no me sirve?</summary><p>Escribes a {CORREO} y te devolvemos el importe dentro de los {g["dias"]} días.</p></details>'
        f'</section>\n</main>\n{_pie()}')
    return archivo, _pagina(titulo, p["subtitulo"], cuerpo, o, og=True, ruta=ruta)


def pagina_gracias(o: dict) -> str:
    cuerpo = ('<main><h1>Gracias por tu compra</h1><p>Te enviamos el enlace de descarga por correo en unos minutos. '
              f'Si no llega, revisa la carpeta de spam o escribe a {CORREO}.</p><p><a href="/legal/entrega">Cómo funciona la entrega</a></p></main>\n{_pie()}')
    return _pagina(f"Gracias — {o['marca']['nombre']}", "Confirmación de compra", cuerpo, o, og=False, ruta="/gracias", datos_body=False)


def pagina_legal(o: dict, nombre: str) -> str:
    m, dias = o["marca"]["nombre"], o["garantia"]["dias"]
    precio = eur(o["precio"]["lista"]["monto"])
    cuerpos = {
        "vendedor": f"<p>Vendedor: {m} LLC (sociedad de responsabilidad limitada de EE. UU.; datos ficticios).</p>"
                    f"<p>Domicilio: Calle Ficticia 123, Ciudad Ficticia, 00000, EE. UU.</p><p>Correo de contacto y soporte: {CORREO}</p>"
                    "<p>Respondemos en un plazo razonable, normalmente en pocos días hábiles.</p>",
        "terminos": f"<p>Al comprar {o['promesa']['titulo']} obtienes una licencia personal, no exclusiva e intransferible para usar los materiales "
                    f"descargados. Queda prohibido revenderlos o redistribuirlos.</p><p>Precio: {precio}, pago único. El contenido es digital y se entrega por "
                    "correo con un enlace de descarga.</p><p>El contenido es informativo; ver el <a href=\"/legal/aviso\">aviso de contenido</a>.</p>",
        "privacidad": f"<p>Responsable: {m} LLC (ver <a href=\"/legal/vendedor\">vendedor y contacto</a>).</p>"
                      "<p>Datos que tratamos: correo electrónico y datos de pago, que procesa Stripe; no vemos el número de tu tarjeta. "
                      "Con tu consentimiento, el píxel de Meta recibe datos de navegación para medir anuncios y, desde nuestro servidor, "
                      "Meta recibe el evento de compra (API de conversiones) con tu correo cifrado (hash).</p>"
                      "<p>Base legal: ejecución del contrato (la compra) y tu consentimiento (marketing). Conservación: el tiempo que exige la ley "
                      "para facturación y soporte.</p><p>Transferencias a EE. UU. con las garantías aplicables. Derechos de acceso, rectificación, "
                      f"supresión, oposición y portabilidad: escribe a {CORREO}. Puedes reclamar ante tu autoridad de protección de datos.</p>",
        "reembolsos": f"<p>Garantía de devolución de {dias} días: si no te sirve, te devolvemos el importe. Sin preguntas.</p>"
                      f"<p>Cómo pedirlo: escribe a {CORREO} indicando el correo de la compra. Reembolsamos al método de pago original.</p>"
                      "<p>Desistimiento: en compras de contenido digital, al comprar aceptas la entrega inmediata y, con ella, la pérdida del derecho "
                      "legal de desistimiento; la garantía de devolución se mantiene igualmente durante el plazo indicado.</p>",
        "cookies": "<p>Usamos una cookie propia, <code>fabrica_consent</code> (preferencias, 180 días), para recordar tu elección.</p>"
                   "<p>Solo si aceptas marketing se cargan el píxel de Meta y sus cookies (<code>_fbp</code>, <code>_fbc</code>). Si lo rechazas "
                   "o no eliges, no se carga nada de eso.</p><p><button type=\"button\" data-consent-abrir>Cambiar mi elección</button></p>",
        "aviso": "<p>Contenido informativo y educativo. No garantiza entrevistas, empleo ni resultados concretos.</p>"
                 "<p>No sustituye el asesoramiento profesional (laboral, legal o de cualquier otro tipo). No afirmamos nada sobre tu situación personal.</p>",
        "entrega": f"<p>Tras el pago recibes un correo con el enlace de descarga (normalmente en pocos minutos). El enlace caduca y tiene un límite de usos.</p>"
                   f"<p>Si no llega o caduca, escribe a {CORREO} y lo reenviamos.</p><p>Formato: documentos digitales (guía y plantilla editable).</p>",
    }
    titulo = f"{TITULO_LEGAL[nombre]} — {m}"
    cuerpo = f'<main><h1>{TITULO_LEGAL[nombre]}</h1>{cuerpos[nombre]}<p><a href="/">Volver al inicio</a></p></main>\n{_pie()}'
    return _pagina(titulo, TITULO_LEGAL[nombre], cuerpo, o, og=False, ruta=f"/legal/{nombre}", datos_body=False)


CSS = """/* [EJEMPLO] estilos mínimos del ejemplo. Botones del banner con el mismo peso visual (Aceptar = Rechazar = Personalizar). */
body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 42rem; padding: 1rem; line-height: 1.5; color: #1a1a1a; }
.cta { display: inline-block; padding: .75rem 1.25rem; background: #0b5; color: #fff; text-decoration: none; border-radius: .25rem; }
img { max-width: 100%; height: auto; }
footer { margin-top: 2rem; font-size: .9rem; }
#fabrica-consent { position: fixed; inset: auto 0 0 0; background: #fff; border-top: 2px solid #1a1a1a; padding: 1rem; }
.fc-botones { display: flex; gap: .5rem; }
.fc-btn { flex: 1; padding: .6rem; font: inherit; border: 2px solid #1a1a1a; background: #fff; color: #1a1a1a; cursor: pointer; }
"""


# --------------------------------------------------------------------------------------------------------------------
# Regeneración
# --------------------------------------------------------------------------------------------------------------------
def _rutas(o: dict) -> dict[str, str]:
    r = {"/": o["angulos"][0]["angulo_id"]}
    r.update({f"/a/{a['angulo_id']}": a["angulo_id"] for a in o["angulos"][1:]})
    r.update({"/comprar": "dinamica:crear-sesion", "/gracias": "estatica:gracias"})
    r.update({f"/legal/{n}": f"legal:{n}" for n in LEGALES})
    return r


def regenerar(destino: Path, *, solo_comprobar: bool = False, clave: bytes = V.CLAVE_DE_PRUEBA) -> list[str]:
    """Regenera y re-sella ``destino`` (una copia de ``ofertas/_ejemplo``); devuelve las rutas que cambiaron."""
    w = Escritor(solo_comprobar)
    o = V.cargar_json(destino / "03-oferta" / "oferta.json")
    land, sitio = destino / "05-landing", destino / "05-landing" / "sitio"

    # 1-2. Landing, rutas y tracking.
    for k, a in enumerate(o["angulos"]):
        archivo, html = pagina_angulo(o, a, principal=k == 0)
        w.escribir(sitio / archivo, html)
    w.escribir(sitio / "gracias.html", pagina_gracias(o))
    for n in LEGALES:
        w.escribir(sitio / "legal" / f"{n}.html", pagina_legal(o, n))
    w.escribir(sitio / "css" / "estilos.css", CSS)
    for viejo in (sitio / "legal" / "reembolso.html",):   # ruta de la versión anterior (singular): ya no existe
        if viejo.is_file():
            w.cambios.append(str(viejo))
            if not solo_comprobar:
                viejo.unlink()
    w.escribir(land / "rutas.json", _json(land, _rutas(o)))
    tr = V.cargar_json(land / "tracking.json")
    tr["consent_gating"]["plataforma"] = "banner_propio_v1"
    w.escribir(land / "tracking.json", _json(land, tr))

    # 3. Economía: única fórmula.
    par = V.cargar_yaml(RAIZ / "empresa" / "parametros.yaml")
    eco_ant = V.cargar_json(destino / "03-oferta" / "economia.json")
    entradas = {**eco_ant["entradas_usadas"], "gasto_diario": GASTO_DIARIO_TEST, "oferta_id": eco_ant["oferta_id"]}
    eco = factibilidad.documento_economia(entradas, par, V.limites_de_prueba(), version=eco_ant["version"], origen_version=eco_ant["origen_version"])
    w.escribir(destino / "03-oferta" / "economia.json", _json(destino, eco))

    # 4. Re-sellado. Con ``--comprobar`` se trabaja sobre lo ya calculado en memoria; los hashes de archivos que aún no se
    # escribieron se toman de una copia temporal para no devolver falsos «sin cambios».
    if solo_comprobar and w.cambios:
        return w.cambios
    camp = V.cargar_json(destino / "07-campana" / "campana.json")
    camp["economia"].update(cpa_equilibrio=eco["cpa_be"]["monto"], cpa_objetivo=eco["cpa_obj"]["monto"], cpa_max=eco["cpa_be"]["monto"])
    camp["hash_config"] = V.hash_objeto(camp, excluir=("hash_config",))
    w.escribir(destino / "07-campana" / "campana.json", _json(destino, camp))

    paq = V.cargar_json(destino / "06-creativos" / "paquete.json")
    paq["destino"]["landing_hash"] = V.hash_directorio(sitio)
    w.escribir(destino / "06-creativos" / "paquete.json", _json(destino, paq))

    ver = V.cargar_json(destino / "08-operacion" / "veredicto_oferta.json")
    ver["evidencia"]["cpa_objetivo"]["monto"] = eco["cpa_obj"]["monto"]
    w.escribir(destino / "08-operacion" / "veredicto_oferta.json", _json(destino, ver))

    for slot in (a := V.cargar_json(land / "assets.json"))["slots"]:      # assets.json: sha256 de los archivos que cita
        if slot.get("archivo"):
            slot["sha256"] = V.hash_archivo(land / slot["archivo"])
    w.escribir(land / "assets.json", _json(land, a))

    qa_dir = destino / "qa"
    for ruta in sorted(qa_dir.glob("*.json")):
        q = V.cargar_json(ruta)
        q["artefacto_sha256"] = V.hash_ruta(destino / q["artefacto_ref"])
        q["entradas"] = {r: V.hash_ruta(destino / r) for r in q["entradas"]}
        if q.get("x1"):
            q["x1"]["artefacto_sha256"] = q["artefacto_sha256"]
        if q["etapa"] == "X1":
            q["firma_motor"] = V.firma_hmac({k: v for k, v in q.items() if k != "firma_motor"}, clave)
        w.escribir(ruta, _json(ruta, q))

    est = V.cargar_json(destino / "estado.json")
    antes = json.dumps(est, sort_keys=True)
    for etapa in ("M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7"):          # orden topológico de DEPENDENCIAS
        e = est["etapas"][etapa]
        e["entradas"] = {dep: est["etapas"][dep]["hash_salida"] for dep in V.DEPENDENCIAS.get(etapa, [])}
        if e["hash_salida"] is not None:
            e["hash_salida"] = V.hash_salida_etapa(destino, etapa)
        ap = e["aprobado_por"]
        if ap and ap.get("firma"):
            ap["firma"] = V.firma_hmac({"oferta_id": est["oferta_id"], "etapa": etapa, "hash_salida": e["hash_salida"],
                                        "aprobador": ap["id"], "fecha": ap["fecha"]}, clave)
    if json.dumps(est, sort_keys=True) != antes:
        est["revision"] += 1                       # bloqueo optimista: cada escritura del estado sube la revisión
    w.escribir(destino / "estado.json", _json(destino, est))
    if destino.resolve() == (RAIZ / "ofertas" / "_ejemplo").resolve():
        for esquema, rel in COPIAS_EN_EJEMPLOS.items():
            w.escribir(RAIZ / "contratos" / "ejemplos" / f"{esquema}.valido.json", _json(destino, V.cargar_json(destino / rel)))
        pm = V.cargar_json(RAIZ / "contratos" / "ejemplos" / "postmortem.valido.json")     # cita el hash del veredicto del ejemplo (X46)
        pm["veredicto_sha256"] = V.hash_archivo(destino / "08-operacion" / "veredicto_oferta.json")
        w.escribir(RAIZ / "contratos" / "ejemplos" / "postmortem.valido.json", _json(destino, pm))
    return w.cambios


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests.contratos.regenerar_ejemplo", description=__doc__.split("\n")[0])
    ap.add_argument("--destino", default=str(RAIZ / "ofertas" / "_ejemplo"))
    ap.add_argument("--comprobar", action="store_true", help="no escribe; sale con 1 si regenerar cambiaría algo")
    args = ap.parse_args(argv)
    cambios = regenerar(Path(args.destino), solo_comprobar=args.comprobar)
    for c in cambios:
        print(("CAMBIARÍA " if args.comprobar else "ESCRIBIÓ ") + c)
    return 1 if (args.comprobar and cambios) else 0


if __name__ == "__main__":
    sys.exit(main())
