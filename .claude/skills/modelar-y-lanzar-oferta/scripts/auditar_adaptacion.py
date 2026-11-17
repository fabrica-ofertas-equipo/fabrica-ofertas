"""Auditoría de adaptación al mercado de una oferta (réplica u oferta nueva), sin dejar rastro.

Nació de la revisión del 15-nov-2026 (Oferta F → FR, IT, IE, NZ). Revisa lo que se puede comprobar por web
en TODAS las tiendas de la oferta, como las vería un comprador del país:

  1. Portada de cada tienda (la raíz, no solo la de la landing): idioma del texto visible y título de la pestaña.
     Las tiendas de nivel duplicadas de la madre conservan la landing de la madre en la raíz (pasó en FR, IT, IE, NZ).
  2. Vistas ?v=articulo y ?v=ficha de la tienda de la landing: idioma, imágenes de OTRA tienda (store_id ajeno,
     p. ej. la madre), llaves {{…}} a la vista.
  3. Checkout de cada tienda visto desde el país (preview_country, el mismo parámetro que usa «Ver como otro país»
     del panel): idioma, moneda del país, precio, si tiene order bump y el idioma del texto del bump y del producto.
     Desde Argentina el checkout público sale en español y en USD: eso NO es un error (lo traduce Impultienda según
     la conexión del comprador); por eso se mira con preview_country.

Lo que NO cubre (se revisa aparte, ver references/12-lanzamiento-automatico.md §3 y tropiezos.md):
  imágenes por dentro (ambiente y texto en la imagen: hojas de contacto ampliadas), videos (fotogramas),
  fan page, post-compra (impultienda_ver_postcompra), y la tasa de pago completado (impultienda_carritos_abandonados).

Bloquea píxel, visitas de Impultienda, su API de conversiones, Clarity y Whop (listas de probar_funnel.py).

Uso:
  python3 auditar_adaptacion.py --pais IT --idioma it --landing tu-tienda \
      --tiendas tu-tienda:d132360c-…,tu-tienda:35b071ef-…,tu-tienda:4dc32d04-… \
      [--moneda EUR] [--marca "Oferta I"] [--salida carpeta]
Devuelve JSON con «fallas» (bloquean el lanzamiento) y «avisos» (revisar), y sale con código 1 si hay fallas.
Correr con python3 del sistema (tiene playwright).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probar_funnel as pf  # noqa: E402

TIENDA = pf.TIENDA

PALABRAS = {
    "es": " el la los las de del que y en para con una por su tu tus es está qué cómo nuestra carpeta familia ",
    "fr": " le la les de des du que et en pour avec une un par votre vos est qui ce dans sur pas ",
    "it": " il la le di del della che e in per con una un da il tuo tua sono non è gli dei ",
    "en": " the and of to in for with your you is are this that what who on it be ",
    "pt": " o a os as de do da que e em para com uma um por seu sua você não ",
    "de": " der die das und zu den mit für ist nicht ein eine sie ihr auf ",
    "nl": " de het een van en voor met je jouw is niet op dat wat ",
}
PALABRAS = {k: set(v.split()) for k, v in PALABRAS.items()}
MONEDA_SIMBOLO = {"EUR": "€", "USD": "US$", "NZD": "NZ$", "AUD": "A$", "GBP": "£", "MXN": "MX$", "BRL": "R$", "CAD": "CA$", "PLN": "zł"}
BLOQ = pf.PIXEL + pf.IMPULTIENDA + pf.MEDICION


def idioma_de(texto: str) -> tuple[str, dict]:
    pal = re.findall(r"[a-zà-ÿ]+", texto.lower())
    cuenta = {k: sum(1 for p in pal if p in v) for k, v in PALABRAS.items()}
    tot = sum(cuenta.values()) or 1
    prop = {k: round(v / tot, 2) for k, v in cuenta.items() if v}
    return (max(cuenta, key=cuenta.get) if sum(cuenta.values()) else "?"), prop


def lineas_ajenas(texto: str, idioma: str, maximo: int = 8) -> list[str]:
    out = []
    for ln in {l.strip() for l in texto.split("\n") if len(l.strip()) > 18}:
        det, prop = idioma_de(ln)
        pal = re.findall(r"\w+", ln)
        if det not in ("?", idioma) and prop.get(det, 0) >= 0.75 and idioma not in prop and len(pal) >= 6:
            out.append(f"[{det}] {ln[:120]}")
    return sorted(out)[:maximo]


def auditar(op) -> dict:
    from playwright.sync_api import sync_playwright
    tiendas = [t.split(":") for t in op.tiendas.split(",")]
    ids = {t: sid for t, sid in tiendas}
    loc, tz = pf.PAISES.get(op.pais, (f"{op.idioma}-{op.pais}", "UTC"))
    fallas, avisos, detalle = [], [], {}
    sal = Path(op.salida)
    sal.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(**p.devices["iPhone 13"], locale=loc, timezone_id=tz)
        ctx.route("**/*", lambda r: r.abort() if any(f in r.request.url for f in BLOQ) else r.continue_())
        pg = ctx.new_page()

        def abrir(url):
            pg.goto(url, wait_until="load", timeout=90000)
            pg.wait_for_timeout(3500)
            for _ in range(10):
                pg.mouse.wheel(0, 1200)
                pg.wait_for_timeout(250)
            return pg.evaluate("document.body.innerText"), pg.content(), pg.title()

        # 1 y 2: portadas y vistas
        for t in ids:
            vistas = [""] + (["?v=articulo", "?v=ficha"] if t == op.landing else [])
            for v in vistas:
                clave = f"{t}/{v or 'raiz'}"
                try:
                    txt, html, titulo = abrir(TIENDA.url_landing(t, v))
                except Exception as e:  # noqa: BLE001
                    fallas.append(f"{clave}: no carga ({str(e)[:60]})")
                    continue
                det, prop = idioma_de(txt)
                d = {"titulo": titulo, "idioma": det, "proporciones": prop, "chars": len(txt)}
                if titulo and op.marca and op.marca.lower() not in titulo.lower():
                    avisos.append(f"{clave}: título de la pestaña «{titulo}» (no es la marca del país)")
                if len(txt) > 120 and det != op.idioma:
                    (fallas if t == op.landing or len(txt) > 3000 else avisos).append(
                        f"{clave}: el texto visible está en «{det}» y no en «{op.idioma}» ({prop}) — ¿landing de la madre?")
                aj = lineas_ajenas(txt, op.idioma)
                if aj and det == op.idioma:
                    avisos.append(f"{clave}: {len(aj)} línea(s) en otro idioma: {aj[:3]}")
                ajenas = sorted({s for s in re.findall(r"store-resources/([0-9a-f-]{36})/", html) if s != ids.get(t) and s not in ids.values()})
                if ajenas and t == op.landing:
                    fallas.append(f"{clave}: imágenes de otra tienda (store_id {', '.join(ajenas)}) — subirlas a la tienda del país")
                llaves = re.findall(r"\{\{\s*\w+\s*\}\}", txt)
                if llaves:
                    fallas.append(f"{clave}: llaves a la vista {sorted(set(llaves))}")
                d["lineas_ajenas"] = aj
                detalle[clave] = d

        # 3: checkouts vistos desde el país
        for t, sid in ids.items():
            clave = f"{t}/checkout"
            try:
                txt, html, _ = abrir(TIENDA.url_checkout(t, sid, op.pais, vista_previa=True))
            except Exception as e:  # noqa: BLE001
                fallas.append(f"{clave}: no carga ({str(e)[:60]})")
                continue
            pg.screenshot(path=str(sal / f"{t}-checkout-{op.pais}.png"), full_page=True)
            det, prop = idioma_de(txt)
            boton = re.search(r"^((?:Pagar|Payer|Paga|Pay|Bezahlen|Betalen|Zapłać|Öde)\b[^\n]{0,25}\d[^\n]{0,8})$", txt, re.M)
            simbolo = MONEDA_SIMBOLO.get((op.moneda or "").upper(), "")
            bump = bool(re.search(r"⚡|SUMA A TU COMPRA|ADD TO YOUR ORDER|AJOUTE|AGGIUNGI", txt))
            d = {"idioma": det, "proporciones": prop, "boton": boton.group(1) if boton else None, "bump": bump}
            if det != op.idioma:
                fallas.append(f"{clave}: el checkout visto desde {op.pais} sale en «{det}» ({prop})")
            if simbolo and simbolo not in txt:
                fallas.append(f"{clave}: no muestra la moneda {op.moneda} ({simbolo}) a un comprador de {op.pais} — revisar Markets")
            if not bump:
                avisos.append(f"{clave}: sin order bump (la madre lo tiene: se pierde ticket)")
            aj = lineas_ajenas(txt, op.idioma)
            if aj:
                fallas.append(f"{clave}: textos escritos a mano en otro idioma (no se traducen solos): {aj[:4]}")
            detalle[clave] = d
        ctx.close()
        nav.close()
    return {"pais": op.pais, "idioma": op.idioma, "ok": not fallas, "fallas": fallas, "avisos": avisos, "detalle": detalle}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pais", required=True)
    ap.add_argument("--idioma", required=True, choices=sorted(PALABRAS))
    ap.add_argument("--landing", required=True, help="subdominio de la tienda que tiene la landing")
    ap.add_argument("--tiendas", required=True, help="subdominio:store_id separados por coma (todas las de la oferta)")
    ap.add_argument("--moneda", default="")
    ap.add_argument("--marca", default="", help="nombre de la marca en el país (para el título de la pestaña)")
    ap.add_argument("--salida", default=".")
    op = ap.parse_args(argv)
    op.pais = op.pais.upper()
    r = auditar(op)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
