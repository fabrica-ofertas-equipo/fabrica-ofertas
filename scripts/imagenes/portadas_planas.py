"""Portadas y mapas PLANOS (HTML/CSS -> PNG con Chrome sin pantalla) para usar como referencia de Kie.

Qué hace
--------
Lee una especificación JSON (``portadas-planas.json`` o ``mapas-ilustrativos.json`` de una oferta) y, para
cada pieza, escribe un HTML y un PNG con el sistema de diseño de la marca: fondo azul tinta, acentos
turquesa / ámbar / cielo, títulos en serif (Charter), textos en Avenir Next, marca de mapa mental propia.

Para qué sirve
--------------
Los modelos de imagen deforman el texto. La pieza plana, con la ortografía polaca exacta (Ś ł ą ę ć ń ó ź ż),
se sube a Kie como imagen de referencia (``image_input``) y el mockup 3D la conserva. También es la
referencia para las miniaturas ilustrativas de la galería «qué hay dentro» (mapas reales en palabras,
distintos de los del producto final, que D4 aún no produce).

Tipos de pieza
--------------
``pack`` (portada del pack con cifra grande), ``bonus`` (portada de bonus/bump con icono propio),
``ekran`` (pantalla horizontal para el monitor del héroe), ``og`` (texto exacto sobre una placa de Kie, con --fondo) y, en el archivo de mapas, ``mapa`` (página A4 con nodo
central, seis ramas, zdania, línea para repetir, ejercicio y siguiente paso).

Uso::

    python3 scripts/imagenes/portadas_planas.py ESPEC.json --salida DIR [--solo id1,id2] [--chrome RUTA]

Escribe ``DIR/<id>.png`` y ``DIR/html/<id>.html``. No llama a la red ni gasta nada.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import subprocess
import sys
from pathlib import Path

CHROME_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SERIF = "Charter, 'Iowan Old Style', Georgia, serif"
SANS = "'Avenir Next', 'Helvetica Neue', Helvetica, Arial, sans-serif"

COLORES_DEFECTO = {
    "fondo": "#12263F", "superficie": "#1D3A5C", "papel": "#EEF3F5", "texto": "#F1F6FA", "texto_suave": "#B9C7DB",
    "turquesa": "#6FD0C9", "turquesa_profundo": "#0B6B73", "ambar": "#F2A93B", "cielo": "#8FC7E8",
}


def esc(t: str) -> str:
    return html.escape(t, quote=True)


def esc_guion(t: str) -> str:
    """Escapa y dibuja el guion largo «–» (A1–C2) con la serif de la marca, donde se ve claramente más largo que un guion."""
    return esc(t).replace("–", f'<span style="font-family:{SERIF};font-size:1.25em;line-height:0;letter-spacing:0;padding:0 .04em">–</span>')


# ── marca ───────────────────────────────────────────────────────────────────
def marca_svg(c: dict, tam: int = 84) -> str:
    """Marca propia: nodo central y cinco ramas con nodos (mapa mental)."""
    cx = cy = 32.0
    ramas = []
    for i, ang in enumerate((-90, -18, 54, 126, 198)):
        x = cx + 22 * math.cos(math.radians(ang))
        y = cy + 22 * math.sin(math.radians(ang))
        col = c["ambar"] if i == 1 else c["turquesa"]
        ramas.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{c["texto_suave"]}" stroke-width="3" stroke-linecap="round"/>'
                     f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="{col}"/>')
    return (f'<svg width="{tam}" height="{tam}" viewBox="0 0 64 64">{"".join(ramas)}'
            f'<circle cx="{cx}" cy="{cy}" r="10" fill="{c["turquesa"]}" stroke="{c["fondo"]}" stroke-width="3"/></svg>')


def marca_decor(c: dict, ancho: int, alto: int, opacidad: float = 0.16, rel: tuple = (0.72, 0.30), escala: float = 1.0) -> str:
    """Mapa mental decorativo grande (sin texto) para el fondo."""
    cx, cy = ancho * rel[0], alto * rel[1]
    partes = []
    for i, (ang, largo, r) in enumerate(((-150, 330, 30), (-95, 280, 22), (-40, 360, 34), (10, 300, 24), (60, 340, 30), (115, 260, 20), (170, 320, 26))):
        x = cx + escala * largo * math.cos(math.radians(ang))
        y = cy + escala * largo * math.sin(math.radians(ang))
        col = c["ambar"] if i == 3 else c["turquesa"]
        partes.append(f'<line x1="{cx:.0f}" y1="{cy:.0f}" x2="{x:.0f}" y2="{y:.0f}" stroke="{c["texto_suave"]}" stroke-width="5" stroke-linecap="round"/>'
                      f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{col}"/>')
    partes.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="64" fill="{c["turquesa"]}"/>')
    return f'<svg style="position:absolute;left:0;top:0;opacity:{opacidad}" width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}">{"".join(partes)}</svg>'


def base_css(c: dict, w: int, h: int) -> str:
    return f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{c['fondo']}}}
.cover{{position:relative;width:{w}px;height:{h}px;overflow:hidden;color:{c['texto']};font-family:{SANS};
 background:radial-gradient(1100px 900px at 88% -5%, #274e7c 0%, rgba(39,78,124,0) 62%),linear-gradient(180deg,{c['fondo']} 0%,#0d1d32 100%)}}
.cover:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 2px,transparent 2px),linear-gradient(90deg,rgba(255,255,255,.035) 2px,transparent 2px);background-size:60px 60px}}
.brand{{display:flex;align-items:center;gap:22px}}
.brand b{{font-family:{SERIF};font-weight:700;letter-spacing:.06em;font-size:46px;color:{c['texto']}}}
.pill{{border-radius:999px;padding:16px 32px;font-weight:700;letter-spacing:.14em;font-size:36px;color:#12263F}}
"""


ACENTOS = {"turquesa": "turquesa", "ambar": "ambar", "cielo": "cielo"}


# ── iconos de bonus (viewBox 0 0 1020 640) ──────────────────────────────────
def icono(nombre: str, c: dict) -> str:
    T, A, S, N, P = c["turquesa"], c["ambar"], c["cielo"], c["fondo"], c["texto"]
    if nombre == "calendario":
        celdas = []
        marcadas = {0, 2, 3, 5, 8}
        for f in range(3):
            for k in range(4):
                x, y = 290 + k * 120, 235 + f * 105
                celdas.append(f'<rect x="{x}" y="{y}" width="100" height="85" rx="16" fill="#DCE7F0"/>')
                if (f * 4 + k) in marcadas:
                    celdas.append(f'<path d="M{x+24} {y+44} l20 20 l34 -42" fill="none" stroke="{c["turquesa_profundo"]}" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>')
        return (f'<rect x="250" y="70" width="520" height="500" rx="38" fill="{P}"/>'
                f'<path d="M250 108a38 38 0 0 1 38 -38h444a38 38 0 0 1 38 38v82H250z" fill="{T}"/>'
                f'<rect x="345" y="38" width="28" height="76" rx="14" fill="{N}"/><rect x="647" y="38" width="28" height="76" rx="14" fill="{N}"/>'
                + "".join(celdas) +
                f'<circle cx="760" cy="540" r="78" fill="{A}" stroke="{N}" stroke-width="10"/>'
                f'<text x="760" y="578" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="112" fill="{N}">&#8635;</text>')
    if nombre == "escalera":
        colores = [T, T, S, S, A, A]
        barras = []
        for i, (lab, alt) in enumerate(zip(("A1", "A2", "B1", "B2", "C1", "C2"), (110, 190, 270, 350, 430, 510))):
            x, y = 65 + i * 150, 590 - alt
            barras.append(f'<rect x="{x}" y="{y}" width="130" height="{alt}" rx="24" fill="{colores[i]}"/>'
                          f'<text x="{x+65}" y="{y+72}" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="58" fill="{N}">{lab}</text>')
        return (f'<line x1="40" y1="590" x2="980" y2="590" stroke="{c["texto_suave"]}" stroke-width="6" stroke-linecap="round"/>' + "".join(barras))
    if nombre == "burbujas":
        def lineas(x, y, anchos, col):
            return "".join(f'<rect x="{x}" y="{y+i*48}" width="{a}" height="20" rx="10" fill="{col}" opacity=".85"/>' for i, a in enumerate(anchos))
        return (f'<rect x="80" y="60" width="560" height="230" rx="46" fill="{P}"/><polygon points="170,285 250,285 160,360" fill="{P}"/>'
                f'<rect x="124" y="94" width="86" height="46" rx="23" fill="{T}"/><text x="167" y="128" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="30" fill="{N}">PL</text>'
                + lineas(124, 168, (440, 360, 260), "#9DB2C7") +
                f'<rect x="380" y="320" width="560" height="230" rx="46" fill="{A}"/><polygon points="840,545 760,545 850,620" fill="{A}"/>'
                f'<rect x="424" y="354" width="86" height="46" rx="23" fill="{N}"/><text x="467" y="388" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="30" fill="{P}">EN</text>'
                + lineas(424, 428, (440, 340, 240), "#12263F"))
    if nombre == "lengua":
        # dos medallones θ y ð + esquema lineal de la lengua entre los dientes (sin audio ni ondas: el producto es PDF)
        dientes_sup = "".join(f'<rect x="{334 + k * 72}" y="392" width="64" height="86" rx="16" fill="{P}"/>' for k in range(5))
        dientes_inf = "".join(f'<rect x="{334 + k * 72}" y="526" width="64" height="86" rx="16" fill="{P}" opacity=".92"/>' for k in range(5))
        return (
            f'<circle cx="260" cy="190" r="150" fill="rgba(111,208,201,.12)" stroke="{T}" stroke-width="11"/>'
            f'<text x="260" y="262" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="230" fill="{T}">θ</text>'
            f'<circle cx="760" cy="190" r="150" fill="rgba(242,169,59,.12)" stroke="{A}" stroke-width="11"/>'
            f'<text x="760" y="262" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="230" fill="{A}">ð</text>'
            f'<rect x="296" y="366" width="428" height="270" rx="70" fill="none" stroke="{S}" stroke-width="8" stroke-dasharray="2 16" stroke-linecap="round"/>'
            + dientes_sup +
            f'<rect x="332" y="478" width="356" height="48" rx="22" fill="#0e2038"/>'
            f'<rect x="402" y="480" width="216" height="44" rx="22" fill="{A}"/>'
            f'<line x1="510" y1="486" x2="510" y2="516" stroke="{N}" stroke-width="5" stroke-linecap="round"/>'
            + dientes_inf)
    if nombre == "pares":
        def tarjeta(x, col, etq, ang, txtcol):
            return (f'<g transform="rotate({ang} {x+170} 330)"><rect x="{x}" y="110" width="340" height="440" rx="38" fill="{col}"/>'
                    f'<rect x="{x+34}" y="146" width="92" height="48" rx="24" fill="{N}"/><text x="{x+80}" y="181" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="30" fill="{P}">{etq}</text>'
                    f'<rect x="{x+34}" y="248" width="250" height="52" rx="26" fill="{txtcol}"/>'
                    f'<rect x="{x+34}" y="340" width="272" height="20" rx="10" fill="{txtcol}" opacity=".55"/><rect x="{x+34}" y="384" width="210" height="20" rx="10" fill="{txtcol}" opacity=".55"/>'
                    f'<rect x="{x+34}" y="428" width="240" height="20" rx="10" fill="{txtcol}" opacity=".55"/></g>')
        return (tarjeta(80, P, "PL", -6, "#9DB2C7") + tarjeta(600, A, "EN", 6, "#12263F") +
                f'<g stroke="{T}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"><path d="M446 330 H574"/><path d="M478 292 l-40 38 l40 38"/><path d="M542 292 l40 38 l-40 38"/></g>')
    if nombre == "fiszki":
        mini = (f'<g stroke="{c["texto_suave"]}" stroke-width="7" stroke-linecap="round"><line x1="510" y1="270" x2="400" y2="200"/><line x1="510" y1="270" x2="620" y2="200"/>'
                f'<line x1="510" y1="270" x2="400" y2="340"/><line x1="510" y1="270" x2="620" y2="340"/></g>'
                f'<circle cx="400" cy="200" r="26" fill="{A}"/><circle cx="620" cy="200" r="26" fill="{S}"/><circle cx="400" cy="340" r="26" fill="{S}"/><circle cx="620" cy="340" r="26" fill="{A}"/>'
                f'<circle cx="510" cy="270" r="44" fill="{T}"/>')
        return (f'<g transform="rotate(-10 510 270)"><rect x="250" y="100" width="520" height="340" rx="40" fill="#2C527F"/></g>'
                f'<g transform="rotate(7 510 270)"><rect x="250" y="100" width="520" height="340" rx="40" fill="{S}"/></g>'
                f'<rect x="250" y="100" width="520" height="340" rx="40" fill="{P}"/>' + mini +
                f'<rect x="330" y="500" width="150" height="76" rx="38" fill="{T}"/><text x="405" y="552" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="40" letter-spacing="3" fill="{N}">PDF</text>'
                f'<rect x="540" y="500" width="150" height="76" rx="38" fill="{A}"/><text x="615" y="552" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="40" letter-spacing="3" fill="{N}">CSV</text>')
    raise ValueError(f"icono desconocido: {nombre}")


# ── portadas ────────────────────────────────────────────────────────────────
def html_bonus(p: dict, c: dict) -> str:
    w, h = p["ancho"], p["alto"]
    acc = c[ACENTOS[p["acento"]]]
    lineas = []
    for i, t in enumerate(p["titulo"]):
        col = acc if i == p.get("resaltado", -1) else c["texto"]
        lineas.append(f'<span style="color:{col}">{esc(t)}</span>')
    titulo = "<br>".join(lineas)
    pie = p["pie"]
    tres = len(p["titulo"]) > 2                      # título de tres líneas: panel más bajo y letra menor
    alto_art, top_tit, tam_tit = (540, 860, 104) if tres else (640, 960, 122)
    top_sub = top_tit + int(len(p["titulo"]) * tam_tit * 1.04) + 28
    largo = len(p["etiqueta"]) > 12
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>{esc(p['id'])}</title><style>{base_css(c, w, h)}
.top{{position:absolute;left:90px;right:90px;top:84px;display:flex;justify-content:space-between;align-items:center}}
.art{{position:absolute;left:90px;right:90px;top:250px;height:{alto_art}px;border-radius:52px;background:linear-gradient(180deg,{c['superficie']},#183253);border:3px solid rgba(111,208,201,.28);overflow:hidden}}
.titulo{{position:absolute;left:90px;right:90px;top:{top_tit}px;font-family:{SERIF};font-weight:700;font-size:{tam_tit}px;line-height:1.04;letter-spacing:-.005em}}
.sub{{position:absolute;left:90px;right:120px;top:{top_sub}px;font-size:{42 if tres else 46}px;line-height:1.3;font-weight:500;color:{c['texto_suave']}}}
.pie{{position:absolute;left:90px;right:90px;bottom:84px;border-top:4px solid {acc};padding-top:34px;display:flex;justify-content:space-between;font-weight:700;font-size:36px;letter-spacing:.1em;color:{c['texto_suave']}}}
</style></head><body><div class="cover">
<div class="top"><div class="brand">{marca_svg(c)}<b>SŁOWOMAPA</b></div><div class="pill" style="background:{acc};{'font-size:28px;letter-spacing:.08em;padding:16px 26px' if largo else ''}">{esc(p['etiqueta'])}</div></div>
<div class="art"><svg width="100%" height="100%" viewBox="0 0 1020 640" preserveAspectRatio="xMidYMid meet">{icono(p['icono'], c)}</svg></div>
<div class="titulo">{titulo}</div>
<div class="sub">{esc_guion(p['subtitulo'])}</div>
<div class="pie"><span>{esc_guion(pie[0])}</span><span>{esc_guion(pie[1])}</span></div>
</div></body></html>"""


def chips_html(chips: list[str], c: dict, tam: int, alto: int, ancho: int, gap: int) -> str:
    """Fila de seis chips de nivel (A1…C2) con color por grupo CEFR."""
    colores = [c["turquesa"], c["turquesa"], c["cielo"], c["cielo"], c["ambar"], c["ambar"]]
    return "".join(
        f'<div style="width:{ancho}px;height:{alto}px;margin-right:{gap}px;border-radius:{alto//3}px;border:5px solid {colores[i]};'
        f'color:{colores[i]};display:flex;align-items:center;justify-content:center;font-family:{SERIF};font-weight:700;'
        f'font-size:{tam}px;background:rgba(255,255,255,.04)">{esc(t)}</div>'
        for i, t in enumerate(chips))


def html_pack(p: dict, c: dict) -> str:
    w, h = p["ancho"], p["alto"]
    acc = c[ACENTOS[p["acento"]]]
    chips = chips_html(p["chips"], c, 52, 112, 150, 24)
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>pack</title><style>{base_css(c, w, h)}
.top{{position:absolute;left:90px;right:90px;top:84px;display:flex;justify-content:space-between;align-items:center}}
.cifra{{position:absolute;left:84px;top:300px;font-family:{SERIF};font-weight:700;font-size:520px;line-height:.9;color:{acc};letter-spacing:-.03em}}
.unidad{{position:absolute;left:96px;top:790px;font-family:{SERIF};font-weight:700;font-size:190px;line-height:1;color:{c['texto']}}}
.titulo{{position:absolute;left:90px;right:90px;top:1020px;font-family:{SERIF};font-weight:700;font-size:92px;line-height:1.1;color:{c['texto']}}}
.chips{{position:absolute;left:90px;top:1290px;display:flex}}
.pie{{position:absolute;left:90px;right:90px;bottom:84px;border-top:4px solid {acc};padding-top:34px;display:flex;justify-content:space-between;font-weight:700;font-size:36px;letter-spacing:.06em;color:{c['texto_suave']}}}
</style></head><body><div class="cover">{marca_decor(c, w, h, .20, (0.80, 0.13), .55)}
<div class="top"><div class="brand">{marca_svg(c)}<b>SŁOWOMAPA</b></div><div class="pill" style="background:{acc}">{esc(p['etiqueta'])}</div></div>
<div class="cifra">{esc(p['cifra'])}</div><div class="unidad">{esc(p['cifra_unidad'])}</div>
<div class="titulo">{esc(p['titulo'][0])}<br>{esc(p['titulo'][1])}</div>
<div class="chips">{chips}</div>
<div class="pie"><span>{esc(p['pie'][0])}</span><span>{esc(p['pie'][1])}</span></div>
</div></body></html>"""


def html_ekran(p: dict, c: dict) -> str:
    w, h = p["ancho"], p["alto"]
    acc = c[ACENTOS[p["acento"]]]
    chips = chips_html(p["chips"], c, 44, 96, 128, 20)
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>ekran</title><style>{base_css(c, w, h)}
.cifra{{position:absolute;left:110px;top:230px;font-family:{SERIF};font-weight:700;font-size:430px;line-height:.9;color:{acc};letter-spacing:-.03em}}
.unidad{{position:absolute;left:860px;top:395px;font-family:{SERIF};font-weight:700;font-size:170px;line-height:1;color:{c['texto']}}}
.titulo{{position:absolute;left:110px;top:640px;font-family:{SERIF};font-weight:700;font-size:92px;line-height:1.1;color:{c['texto']}}}
.chips{{position:absolute;left:110px;top:900px;display:flex}}
.pie{{position:absolute;left:110px;top:1060px;font-weight:600;font-size:38px;letter-spacing:.04em;color:{c['texto_suave']}}}
.marca{{position:absolute;left:110px;top:90px}}
</style></head><body><div class="cover">{marca_decor(c, w, h, .30)}
<div class="marca brand">{marca_svg(c, 96)}<b style="font-size:54px">SŁOWOMAPA</b></div>
<div class="cifra">{esc(p['cifra'])}</div><div class="unidad">{esc(p['cifra_unidad'])}</div>
<div class="titulo">{esc(p['titulo'][0])}<br>{esc(p['titulo'][1])}</div>
<div class="chips">{chips}</div>
<div class="pie">{esc(p['pie'][0])}</div>
</div></body></html>"""


# ── mapa A4 de la galería ilustrativa ───────────────────────────────────────
def html_mapa(m: dict, c: dict) -> str:
    w, h = 1240, 1754
    grupo = {"A": c["turquesa_profundo"], "B": "#2B5FC7", "C": "#C97F0A"}[m["grupo"]]
    claro = {"A": c["turquesa"], "B": c["cielo"], "C": c["ambar"]}[m["grupo"]]
    N = c["fondo"]
    # mapa: área 1100 x 700 (SVG), centro (550,350)
    cx, cy = 550, 320
    pos = [(0, 10), (0, 245), (0, 480), (800, 10), (800, 245), (800, 480)]   # esquinas superiores izq. de cada nodo 300x150
    trazos, nodos = [], []
    for (x, y), (en, pl, aso) in zip(pos, m["nodos"]):
        izq = x == 0
        px = x + 300 if izq else x
        py = y + 75
        qx = cx - 190 if izq else cx + 190
        trazos.append(f'<path d="M{qx} {cy} C {(qx+px)/2} {cy}, {(qx+px)/2} {py}, {px} {py}" fill="none" stroke="{claro}" stroke-width="7" stroke-linecap="round"/>')
        nodos.append(f'<g><rect x="{x}" y="{y}" width="300" height="150" rx="30" fill="#FFFFFF" stroke="{grupo}" stroke-width="6"/>'
                     f'<text x="{x+150}" y="{y+52}" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="40" fill="{N}">{esc(en)}</text>'
                     f'<text x="{x+150}" y="{y+94}" text-anchor="middle" font-family="{SANS}" font-weight="600" font-size="30" fill="{grupo}">{esc(pl)}</text>'
                     f'<text x="{x+150}" y="{y+130}" text-anchor="middle" font-family="{SANS}" font-weight="500" font-size="22" fill="#5B6B80">{esc(aso)}</text></g>')
    tam_c = 72 if len(m["centro_en"]) <= 6 else (56 if len(m["centro_en"]) <= 8 else 46)
    centro = (f'<rect x="{cx-190}" y="{cy-95}" width="380" height="190" rx="46" fill="{N}"/>'
              f'<text x="{cx}" y="{cy+10}" text-anchor="middle" font-family="{SERIF}" font-weight="700" font-size="{tam_c}" fill="#FFFFFF">{esc(m["centro_en"])}</text>'
              f'<text x="{cx}" y="{cy+58}" text-anchor="middle" font-family="{SANS}" font-weight="600" font-size="34" fill="{claro}">{esc(m["centro_pl"])}</text>')
    zdania = "".join(
        f'<div class="z"><div class="en">{esc(en)}</div><div class="pl">{esc(pl)}</div></div>' for en, pl in m["zdania"])
    ejer = "".join(f'<div class="e">{i+1}. {esc(t)}<br><span>({esc(op)})</span></div>' for i, (t, op) in enumerate(m["cwiczenie"]))
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>{esc(m['id'])}</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:#fff}}
.pg{{position:relative;width:{w}px;height:{h}px;background:#fff;color:{N};font-family:{SANS};padding:64px 78px}}
.pg:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(18,38,63,.035) 2px,transparent 2px),linear-gradient(90deg,rgba(18,38,63,.035) 2px,transparent 2px);background-size:40px 40px}}
.head{{position:relative;display:flex;justify-content:space-between;align-items:center;height:70px}}
.head .b{{display:flex;align-items:center;gap:16px;font-family:{SERIF};font-weight:700;font-size:32px;letter-spacing:.06em;color:{N}}}
.chip{{background:{claro};color:{N};font-family:{SERIF};font-weight:700;font-size:44px;padding:6px 34px;border-radius:999px}}
.tytul{{position:relative;margin-top:20px;font-family:{SERIF};font-weight:700;font-size:84px;line-height:1.05}}
.podtytul{{position:relative;font-weight:600;font-size:30px;color:#5B6B80;letter-spacing:.06em;margin-top:6px}}
.mapa{{position:relative;margin-top:26px}}
.sek{{position:relative;margin-top:30px;font-weight:700;letter-spacing:.16em;font-size:26px;color:{grupo}}}
.z{{position:relative;border-left:8px solid {claro};padding:4px 0 4px 22px;margin-top:12px}}
.z .en{{font-weight:700;font-size:31px}} .z .pl{{font-size:28px;color:#5B6B80;margin-top:2px}}
.dol{{position:relative;display:flex;gap:28px;margin-top:26px}}
.kol{{flex:1;border:3px solid #D5DEE8;border-radius:24px;padding:20px 22px;background:#fff}}
.kol h4{{font-size:24px;letter-spacing:.14em;color:{grupo};margin-bottom:10px}}
.linia{{border-bottom:3px dotted #9DB2C7;height:46px}}
.e{{font-size:26px;line-height:1.3;margin-bottom:10px;font-weight:600}} .e span{{font-weight:500;color:#5B6B80;font-size:23px}}
.krok{{background:{claro};border:none}} .krok h4{{color:{N}}} .krok p{{font-family:{SERIF};font-weight:700;font-size:38px;line-height:1.15}}
.odp{{position:relative;margin-top:14px;font-size:21px;color:#5B6B80;letter-spacing:.04em}}
</style></head><body><div class="pg">
<div class="head"><div class="b">{marca_svg({**c, 'fondo': '#FFFFFF', 'texto_suave': '#9DB2C7'}, 54)}<span>SŁOWOMAPA</span></div><div class="chip">{esc(m['nivel'])}</div></div>
<div class="tytul">{esc(m['tema'])}</div><div class="podtytul">MAPA SŁOWNICTWA · POZIOM {esc(m['nivel'])}</div>
<div class="mapa"><svg width="1084" height="646" viewBox="-8 -4 1116 650">{''.join(trazos)}{centro}{''.join(nodos)}</svg></div>
<div class="sek">ZDANIA</div>{zdania}
<div class="dol">
<div class="kol"><h4>POWTÓRZ NA GŁOS</h4><div class="linia"></div><div class="linia"></div><div class="linia"></div></div>
<div class="kol"><h4>ĆWICZENIE</h4>{ejer}</div>
<div class="kol krok"><h4>NASTĘPNY KROK</h4><p>{esc(m['siguiente'])}</p><div style="margin-top:18px;font-size:24px;font-weight:600">Jedna mapa, jedna sesja.</div></div>
</div>
<div class="odp">Odpowiedzi: {esc(m['odpowiedzi'])}</div>
</div></body></html>"""


def html_og(p: dict, c: dict) -> str:
    """Imagen para compartir: placa de Kie (``fondo``, ruta absoluta) + texto exacto superpuesto a la izquierda."""
    w, h = p["ancho"], p["alto"]
    fondo = Path(p["fondo"]).resolve()
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>og</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{c['fondo']}}}
.og{{position:relative;width:{w}px;height:{h}px;overflow:hidden;font-family:{SANS};color:{c['texto']};background:{c['fondo']} url('file://{fondo}') center/cover no-repeat}}
.vel{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(18,38,63,.94) 0%,rgba(18,38,63,.84) 28%,rgba(18,38,63,0) 44%)}}
.bloque{{position:absolute;left:60px;top:72px;width:390px}}
.brand{{display:flex;align-items:center;gap:18px}} .brand b{{font-family:{SERIF};font-weight:700;letter-spacing:.06em;font-size:34px}}
.cifra{{margin-top:38px;display:flex;align-items:baseline;gap:18px;line-height:.9}}
.cifra span:first-child{{font-family:{SERIF};font-weight:700;font-size:140px;color:{c['ambar']};letter-spacing:-.03em}}
.cifra span:last-child{{font-family:{SERIF};font-weight:700;font-size:56px}}
.titulo{{margin-top:24px;font-family:{SERIF};font-weight:700;font-size:35px;line-height:1.14}}
.pill{{display:inline-block;margin-top:28px;border:4px solid {c['turquesa']};color:{c['turquesa']};border-radius:999px;padding:6px 24px;font-family:{SERIF};font-weight:700;font-size:26px;letter-spacing:.04em}}
</style></head><body><div class="og"><div class="vel"></div><div class="bloque">
<div class="brand">{marca_svg(c, 54)}<b>SŁOWOMAPA</b></div>
<div class="cifra"><span>{esc(p['cifra'])}</span><span>{esc(p['cifra_unidad'])}</span></div>
<div class="titulo">{esc(p['titulo'][0])}<br>{esc(p['titulo'][1])}</div>
<div class="pill">{esc(p['pill'])}</div>
</div></div></body></html>"""


def html_movil(p: dict, c: dict) -> str:
    """Pantalla vertical alta (≈9:19,5) con la portada del pack, para el móvil del héroe."""
    w, h = p["ancho"], p["alto"]
    acc = c[ACENTOS[p["acento"]]]
    chips = chips_html(p["chips"], c, 46, 104, 140, 16)
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>pack-movil</title><style>{base_css(c, w, h)}
.top{{position:absolute;left:70px;right:70px;top:260px;display:flex;justify-content:space-between;align-items:center}}
.cifra{{position:absolute;left:62px;top:540px;font-family:{SERIF};font-weight:700;font-size:470px;line-height:.9;color:{acc};letter-spacing:-.03em}}
.unidad{{position:absolute;left:76px;top:1010px;font-family:{SERIF};font-weight:700;font-size:200px;line-height:1;color:{c['texto']}}}
.titulo{{position:absolute;left:70px;right:70px;top:1290px;font-family:{SERIF};font-weight:700;font-size:82px;line-height:1.12;color:{c['texto']}}}
.chips{{position:absolute;left:70px;top:1610px;display:flex}}
.pie{{position:absolute;left:70px;right:70px;top:1830px;border-top:4px solid {acc};padding-top:34px;font-weight:700;font-size:44px;line-height:1.5;letter-spacing:.04em;color:{c['texto_suave']}}}
</style></head><body><div class="cover">{marca_decor(c, w, h, .20, (0.80, 0.16), .5)}
<div class="top"><div class="brand">{marca_svg(c, 72)}<b style="font-size:42px">SŁOWOMAPA</b></div><div class="pill" style="background:{acc};font-size:30px;padding:14px 26px">{esc(p['etiqueta'])}</div></div>
<div class="cifra">{esc(p['cifra'])}</div><div class="unidad">{esc(p['cifra_unidad'])}</div>
<div class="titulo">{esc(p['titulo'][0])}<br>{esc(p['titulo'][1])}</div>
<div class="chips">{chips}</div>
<div class="pie">{esc(p['pie'][0])}<br>{esc(p['pie'][1])}</div>
</div></body></html>"""


CONSTRUCTORES = {"pack": html_pack, "movil": html_movil, "bonus": html_bonus, "ekran": html_ekran, "og": html_og}


def renderizar(html_ruta: Path, png: Path, w: int, h: int, chrome: str = CHROME_MAC) -> Path:
    """Captura el HTML local con Chrome sin pantalla (solo file://)."""
    png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [chrome, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1", f"--window-size={w},{h}",
           f"--screenshot={png}", f"file://{html_ruta.resolve()}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not png.exists() or png.stat().st_size < 1000:
        raise RuntimeError(f"Chrome no produjo {png.name}: {r.stderr[-300:]}")
    return png


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("espec", type=Path)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--solo", default="")
    ap.add_argument("--chrome", default=CHROME_MAC)
    ap.add_argument("--fondo", type=Path, default=None, help="solo tipo og: PNG de fondo (placa de Kie)")
    a = ap.parse_args(argv)
    espec = json.loads(a.espec.read_text(encoding="utf-8"))
    c = {**COLORES_DEFECTO, **(espec.get("colores") or {})}
    solo = {x for x in a.solo.split(",") if x}
    piezas = [(p, p.get("tipo")) for p in espec.get("portadas", [])] + [(m, "mapa") for m in espec.get("mapas", [])]
    for p, tipo in piezas:
        if solo and p["id"] not in solo:
            continue
        if tipo == "og":
            if not a.fondo:
                continue                                   # el og se compone solo cuando hay placa (--fondo)
            p = {**p, "fondo": str(a.fondo)}
        w, h = (1240, 1754) if tipo == "mapa" else (p["ancho"], p["alto"])
        cuerpo = html_mapa(p, c) if tipo == "mapa" else CONSTRUCTORES[tipo](p, c)
        ruta_html = a.salida / "html" / f"{p['id']}.html"
        ruta_html.parent.mkdir(parents=True, exist_ok=True)
        ruta_html.write_text(cuerpo, encoding="utf-8")
        renderizar(ruta_html, a.salida / f"{p['id']}.png", w, h, a.chrome)
        print(f"ok {p['id']} {w}x{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
