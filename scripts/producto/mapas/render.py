"""Render de la hoja A4 de un mapa (HTML + SVG de ramas generado por código) y de las hojas de apoyo.

Una hoja = un mapa. Mismo layout para todos: nodo central, ramas en dos columnas (color y NÚMERO por rama), conectores
curvos en SVG, «Zdania» con la palabra subrayada en el color de su rama, ejercicios, «Powiedz na głos» y «Następny krok».
Las respuestas de «Połącz» las calcula el código (nunca a mano). El PDF sale de Chrome sin pantalla (ruta A de D4, vía
``scripts.producto.render``); el PNG, de la misma página con ``--screenshot``.

Marca propia (navy / turquesa / ámbar, serif, nodos). No copia el diseño de ningún referente. Fuentes: la pila lista
«Source Serif 4» y «Source Sans 3» (OFL) primero y cae a Charter / Avenir Next del sistema: ver ``licencias.json`` de la oferta
(no hay WOFF2 en el repositorio: SB-17).
"""
from __future__ import annotations

import hashlib
import html
import itertools
import math
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts.producto.mapas.esquema import NIVELES, REPARTO

CSS_RUTA = Path(__file__).with_name("plantilla.css")
COLORES_RAMA = ["#0B6B73", "#C77700", "#2B5FC7", "#7A4FB0", "#C4472F", "#1F7A5B", "#B5446E", "#5B6B80", "#8A6D00", "#0E86B3"]
PAL = {"navy": "#12263F", "navy2": "#1D3A5C", "texto": "#1A2433", "suave": "#4D5B70", "turq": "#6FD0C9", "turq_p": "#0B6B73", "ambar": "#F2A93B", "cielo": "#8FC7E8", "linea": "#CBD5DE"}

# Geometría (mm) de la zona del mapa: ver plantilla.css (.rama, .pal, .centro)
W_ZONA, W_TARJ, W_CENT, H_CENT = 184.0, 57.0, 46.0, 24.0
H_ZONA_MIN, H_ZONA_MAX, GAP_MIN = 80.0, 124.0, 3.0
NOMBRE_NIVEL = {"A1": "początkujący", "A2": "podstawowy", "B1": "średni", "B2": "wyższy średni", "C1": "zaawansowany", "C2": "biegły"}


def esc(t: Any) -> str:
    return html.escape(str(t), quote=True)


def css() -> str:
    return CSS_RUTA.read_text(encoding="utf-8")


def luminancia(hex_: str) -> float:
    h = hex_.lstrip("#")
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste_wcag(fg: str, bg: str) -> float:
    a, b = sorted((luminancia(fg), luminancia(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def logo_svg() -> str:
    """Logotipo de nodos: un nodo central y cinco ramas con nodos (marca propia)."""
    cx = cy = 24.0
    nodos = [("#6FD0C9", 3.6), ("#F2A93B", 3.2), ("#8FC7E8", 3.6), ("#0B6B73", 3.0), ("#6FD0C9", 3.2)]
    partes = []
    for i, (col, r) in enumerate(nodos):
        ang = -math.pi / 2 + i * 2 * math.pi / 5 + 0.25
        x, y = cx + 16.5 * math.cos(ang), cy + 16.5 * math.sin(ang)
        partes.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.2f}" y2="{y:.2f}" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>')
        partes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="{col}"/>')
    return f'<svg viewBox="0 0 48 48" aria-hidden="true">{"".join(partes)}<circle cx="{cx}" cy="{cy}" r="6.4" fill="currentColor"/></svg>'


# ── geometría del mapa ────────────────────────────────────────────────────────────────────────────────────────────────
ANCHO_TEXTO_PX = 186.0  # ancho útil de una tarjeta (57 mm menos bordes y relleno) en px CSS


def _dos_lineas(p: Mapping[str, Any]) -> bool:
    """¿El par EN + PL no cabe en una línea? (estimación por letras; ``medir_maquetacion`` la confirma en Chrome)."""
    return 8.4 * len(p["en"]) + 7.3 * len(p["pl"]) + 7.5 > ANCHO_TEXTO_PX


def _lineas_uwaga(p: Mapping[str, Any]) -> int:
    return 0 if not p.get("uwaga_pl") else max(1, math.ceil(len(p["uwaga_pl"]) * 5.2 / ANCHO_TEXTO_PX))


def alto_tarjeta(rama: Mapping[str, Any]) -> float:
    h = 1.9 + 1.7 + 0.9 + 4.2
    for i, p in enumerate(rama["palabras"]):
        h += (0.4 if i == 0 else 1.3) + (9.6 if _dos_lineas(p) else 5.0) + 3.5 + 3.5 * _lineas_uwaga(p)
    return round(h, 2)


def disposicion(mapa: Mapping[str, Any]) -> dict[str, Any]:
    """Posiciones (mm) de tarjetas, nodo central y conectores. Devuelve también ``avisos`` si algo no cabe."""
    ramas = mapa["ramas"]
    n = len(ramas)
    alturas = [alto_tarjeta(r) for r in ramas]

    def _alto_cols(k: int) -> float:
        return max(sum(alturas[:k]) + GAP_MIN * (k - 1), sum(alturas[k:]) + GAP_MIN * (n - k - 1))

    # reparto por ALTURA (no por número de ramas): la rama k es la última de la columna izquierda; se mantiene el orden de lectura
    n_izq = min(range(max(2, n - 5), min(n - 2, 5) + 1), key=lambda k: (_alto_cols(k), abs(k - n / 2))) if n >= 4 else n
    cols = [list(range(0, n_izq)), list(range(n_izq, n))]
    necesaria = _alto_cols(n_izq)
    avisos: list[str] = []
    H = min(max(necesaria, H_ZONA_MIN), H_ZONA_MAX)
    if necesaria > H_ZONA_MAX:
        avisos.append(f"las ramas necesitan {necesaria:.1f} mm y la zona admite {H_ZONA_MAX} mm")
    pos: dict[int, dict[str, float]] = {}
    for lado, idxs in enumerate(cols):
        libre = H - sum(alturas[i] for i in idxs)
        hueco = libre / (len(idxs) - 1) if len(idxs) > 1 else 0.0
        y = 0.0 if len(idxs) > 1 else libre / 2
        for i in idxs:
            pos[i] = {"x": 0.0 if lado == 0 else W_ZONA - W_TARJ, "y": round(y, 2), "h": alturas[i], "lado": lado}
            y += alturas[i] + hueco
    xc, yc = (W_ZONA - W_CENT) / 2, (H - H_CENT) / 2
    conect = []
    for lado, idxs in enumerate(cols):
        for k, i in enumerate(idxs):
            y1 = yc + H_CENT / 2 + (k - (len(idxs) - 1) / 2) * 3.0
            x1 = xc if lado == 0 else xc + W_CENT
            x2 = W_TARJ if lado == 0 else W_ZONA - W_TARJ
            y2 = pos[i]["y"] + pos[i]["h"] / 2
            s = 1 if x2 > x1 else -1
            dx = abs(x2 - x1) * 0.55
            conect.append({"i": i, "d": f"M {x1:.2f} {y1:.2f} C {x1 + s * dx:.2f} {y1:.2f}, {x2 - s * dx:.2f} {y2:.2f}, {x2:.2f} {y2:.2f}", "x1": x1, "y1": y1})
    return {"H": round(H, 2), "pos": pos, "centro": {"x": xc, "y": yc}, "conectores": conect, "avisos": avisos, "necesaria": round(necesaria, 2)}


def _resaltar(texto: str, formas: Sequence[tuple[str, str]]) -> str:
    """Escapa ``texto`` y subraya (en el color de su rama) la primera aparición entera de cada forma."""
    spans: list[tuple[int, int, str]] = []
    for forma, color in formas:
        m = re.search(r"(?<!\w)" + re.escape(forma) + r"(?!\w)", texto, re.I)
        if m and not any(a < m.end() and m.start() < b for a, b, _ in spans):
            spans.append((m.start(), m.end(), color))
    spans.sort()
    out, pos = [], 0
    for a, b, col in spans:
        out.append(esc(texto[pos:a]))
        out.append(f'<span class="h" style="--c:{col}">{esc(texto[a:b])}</span>')
        pos = b
    out.append(esc(texto[pos:]))
    return "".join(out)


def orden_unir(mapa_id: str, n: int) -> list[int]:
    """Permutación determinista SIN puntos fijos de las traducciones del ejercicio «Połącz» (semilla = mapa_id)."""
    cands = [p for p in itertools.permutations(range(n)) if all(p[i] != i for i in range(n))]
    cands.sort(key=lambda p: hashlib.sha256((mapa_id + ":" + "".join(map(str, p))).encode()).hexdigest())
    return list(cands[0])


def respuestas(mapa: Mapping[str, Any]) -> dict[str, Any]:
    """Claves de los tres ejercicios, calculadas por código."""
    ej = mapa["ejercicios"]
    perm = orden_unir(mapa["mapa_id"], len(ej["unir"]))
    letras = "abcdefghij"
    # derecha[j] = traducción del par perm[j]; la clave de la izquierda i es la letra j con perm[j] == i
    clave = [letras[perm.index(i)] for i in range(len(ej["unir"]))]
    return {
        "completar": [c["respuesta"] for c in ej["completar"]],
        "unir": clave,
        "traducir": [t["respuesta"] for t in ej["traducir"]],
        "perm": perm,
    }


# ── una hoja ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def html_pagina(mapa: Mapping[str, Any], *, total_nivel: int | None = None, titulos: Mapping[str, str] | None = None, densidad: str = "d0") -> str:
    nivel, num = mapa["nivel"], mapa["numero"]
    total = total_nivel or REPARTO[nivel]
    dis = disposicion(mapa)
    H = dis["H"]
    colores = [COLORES_RAMA[i % len(COLORES_RAMA)] for i in range(len(mapa["ramas"]))]
    color_de: dict[str, str] = {}
    for i, r in enumerate(mapa["ramas"]):
        for p in r["palabras"]:
            color_de[p["en"].casefold()] = colores[i]
    tr = []
    for c in dis["conectores"]:
        col = colores[c["i"]]
        tr.append(f'<path d="{c["d"]}" fill="none" stroke="{col}" stroke-width="0.8" stroke-linecap="round" opacity="0.9"/><circle cx="{c["x1"]:.2f}" cy="{c["y1"]:.2f}" r="1.05" fill="{col}"/>')
    svg = f'<svg width="{W_ZONA}mm" height="{H}mm" viewBox="0 0 {W_ZONA} {H}" aria-hidden="true">{"".join(tr)}</svg>'
    cen = mapa["centro"]
    tam_c = min(19.0, 120.0 / (0.74 * max(len(cen["en"]), 1)))  # pt: el nodo mide W_CENT mm; ~0,74 em por letra en mayúsculas con espaciado
    tam_p = min(11.0, 118.0 / (0.55 * max(len(cen["pl"]), 1)))
    centro = (f'<div class="centro" style="left:{dis["centro"]["x"]:.2f}mm;top:{dis["centro"]["y"]:.2f}mm;width:{W_CENT}mm;height:{H_CENT}mm">'
              f'<div class="c-en" style="font-size:{tam_c:.1f}pt">{esc(cen["en"])}</div><div class="c-pl" style="font-size:{tam_p:.1f}pt">{esc(cen["pl"])}</div></div>')
    tarjetas = []
    for i, r in enumerate(mapa["ramas"]):
        p = dis["pos"][i]
        pals = []
        for w in r["palabras"]:
            uw = f'<div class="uwaga">{esc(w["uwaga_pl"])}</div>' if w.get("uwaga_pl") else ""
            pals.append(f'<div class="pal"><div class="l1{" dos" if _dos_lineas(w) else ""}"><span class="en">{esc(w["en"])}</span><span class="pl">{esc(w["pl"])}</span></div><div class="pista">{esc(w["pista"])}</div>{uw}</div>')
        tarjetas.append(
            f'<div class="rama" style="--c:{colores[i]};left:{p["x"]}mm;top:{p["y"]}mm;width:{W_TARJ}mm;height:{p["h"]}mm">'
            f'<span class="num">{i + 1}</span><div class="grupo">{esc(r["grupo"]["pl"])}</div>{"".join(pals)}</div>')
    zd = []
    for f in mapa["frases"]:
        en_f = [(u["forma_en"], color_de.get(u["en"].casefold(), "#0B6B73")) for u in f["usa"]]
        pl_f = [(u["forma_pl"], color_de.get(u["en"].casefold(), "#0B6B73")) for u in f["usa"]]
        zd.append(f'<div class="zd"><div class="barra"></div><div><div class="en">{_resaltar(f["en"], en_f)}</div><div class="pl">{_resaltar(f["pl"], pl_f)}</div></div></div>')
    ej, rs = mapa["ejercicios"], respuestas(mapa)
    completar = "".join(
        f'<div class="ej-l">{i}. {esc(c["texto"])} <span class="op">({esc(" / ".join(c["opciones"]))})</span></div>' for i, c in enumerate(ej["completar"], 1))
    izq = "".join(f'<div>{i}. {esc(u["en"])}</div>' for i, u in enumerate(ej["unir"], 1))
    der = "".join(f'<div>{"abcdefghij"[j]}. {esc(ej["unir"][rs["perm"][j]]["pl"])}</div>' for j in range(len(ej["unir"])))
    traducir = "".join(f'<div class="ej-l">{i}. {esc(t["pl"])}</div><div class="linea-tr"></div>' for i, t in enumerate(ej["traducir"], 1))
    voz = "".join(
        f'<div class="vz"><div class="cb"><i></i><i></i></div><div><div class="en">{esc(v["en"])}</div><div class="pl">{esc(v["pl"])}</div></div></div>' for v in mapa["powiedz_na_glos"])
    sp = mapa["siguiente_paso"]
    if sp.get("mapa_id"):
        nombre = (titulos or {}).get(sp["mapa_id"]) or sp["mapa_id"].split("-", 2)[2].replace("-", " ").capitalize()
        sig_titulo = f'Mapa {int(sp["mapa_id"].split("-")[1])} · {esc(nombre)}'
    else:
        sig_titulo = "To ostatnia mapa"
    odp = (f'<b>Odpowiedzi.</b> A: ' + " · ".join(f"{i}. {esc(a)}" for i, a in enumerate(rs["completar"], 1)) +
           ' &nbsp;|&nbsp; B: ' + " · ".join(f"{i}{esc(l)}" for i, l in enumerate(rs["unir"], 1)) +
           ' &nbsp;|&nbsp; C: ' + " · ".join(f"{i}. {esc(a)}" for i, a in enumerate(rs["traducir"], 1)))
    return (
        f'<section class="pagina {esc(densidad)}" id="{esc(mapa["mapa_id"])}" lang="pl" data-mapa="{esc(mapa["mapa_id"])}">'
        f'<div class="cab"><div class="marca">{logo_svg()}<span>SŁOWOMAPA</span></div><div class="nivel">{esc(nivel)}</div></div>'
        f'<h1>{esc(mapa["tema"]["pl"])}</h1>'
        f'<div class="sub">Mapa słownictwa · poziom {esc(nivel)} · mapa {num} z {total}</div>'
        f'<div class="zona-mapa" style="height:{H}mm">{svg}{centro}{"".join(tarjetas)}</div>'
        f'<div class="zdania"><h2>Zdania</h2>{"".join(zd)}</div>'
        f'<div class="baja"><div class="col-ej"><h2>Ćwiczenia</h2>'
        f'<div class="ej-t"><b>A</b> Uzupełnij zdanie</div>{completar}'
        f'<div class="ej-t"><b>B</b> Połącz słowo z tłumaczeniem</div><div class="unir"><div>{izq}</div><div>{der}</div></div>'
        f'<div class="ej-t"><b>C</b> Przetłumacz na angielski</div>{traducir}</div>'
        f'<div class="col-der"><div class="caja"><h2>Powiedz na głos</h2><p class="nota">Powiedz każde zdanie dwa razy.</p>{voz}</div>'
        f'<div class="caja siguiente"><h2>Następny krok</h2><div class="st">{sig_titulo}</div><div class="sx">{esc(sp["texto_pl"])}</div></div></div></div>'
        f'<div class="pie">{odp}<div class="fin"><span>Słowomapa · poziom {esc(nivel)}</span><span>{num} / {total}</span></div></div>'
        f'</section>')


# ── hojas de apoyo ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def html_portada(*, total_anunciado: int, escritos: int, borrador: bool) -> str:
    banda = f'<div class="borrador">Wersja robocza · {escritos} z {total_anunciado} map</div>' if borrador else ""
    return (
        '<section class="pagina portada" lang="pl">' + banda +
        f'<div class="marca">{logo_svg()}<span>SŁOWOMAPA</span></div>'
        '<div class="big">Słownictwo angielskie<br>w <em>mapach myśli</em></div>'
        f'<div class="cifra">{total_anunciado}<small>map</small></div>'
        '<div class="chips">' + "".join(f"<span>{n}</span>" for n in NIVELES) + "</div>"
        '<div class="pie-p">Słowa w zdaniach · PDF A4 · do druku i na telefon</div></section>')


def html_como_usar() -> str:
    return (
        '<section class="pagina" lang="pl"><div class="cab"><div class="marca">' + logo_svg() + '<span>SŁOWOMAPA</span></div></div>'
        '<div class="sec-t">Jak korzystać z map</div>'
        '<p class="p-txt"><b>Jedna mapa to jedna sesja:</b> około 10 minut. Każda mapa mieści się na jednej stronie A4, więc możesz ją wydrukować albo przeczytać na telefonie.</p>'
        '<ol class="pasos">'
        '<li><span><b>Wybierz poziom.</b> Zacznij od poziomu, który znasz, albo od testu poziomu z dodatku. Mapy w każdym pliku idą po kolei.</span></li>'
        '<li><span><b>Spójrz na mapę.</b> Przeczytaj środek i kolejne gałęzie: angielskie słowo, polskie tłumaczenie i krótką podpowiedź.</span></li>'
        '<li><span><b>Przeczytaj zdania.</b> Każde słowo z mapy stoi w zdaniu. Podkreślone słowo ma ten sam kolor co jego gałąź.</span></li>'
        '<li><span><b>Powiedz na głos.</b> Powiedz każde zdanie z ramki dwa razy i odhacz kratki.</span></li>'
        '<li><span><b>Zrób ćwiczenia.</b> Uzupełnij, połącz i przetłumacz. Odpowiedzi są na dole tej samej strony.</span></li>'
        '<li><span><b>Zobacz następny krok.</b> Ramka na dole wskazuje, od której mapy zacząć następnym razem.</span></li></ol>'
        '<p class="p-txt">Do druku w czerni i bieli: gałęzie mają numery, a tekst jest ciemny, więc nic nie ginie bez koloru.</p>'
        '<div class="sec-t" style="font-size:15pt;margin-top:6mm">O czym warto pamiętać</div>'
        '<p class="p-txt">To materiał do porządkowania i powtarzania słownictwa. Nie zastępuje rozmowy z drugą osobą, nauki gramatyki ani przygotowania do egzaminu.</p>'
        '<p class="p-txt">Tłumaczenia i zdania przygotowano z pomocą narzędzi sztucznej inteligencji i sprawdzono kontrolami automatycznymi. Jeśli znajdziesz błąd, napisz na adres kontaktowy ze strony zakupu.</p>'
        '</section>')


def _toc_html(temario: Mapping[str, Any], nivel: str, escritos: set[str], borrador: bool, enlaces: bool) -> str:
    out = []
    for m in (x for x in temario["mapas"] if x["nivel"] == nivel):
        hay = m["mapa_id"] in escritos
        titulo = f'<span class="n">{m["numero"]}</span>{esc(m["tema"]["pl"])} <span style="color:#8794a6">· {esc(m["tema"]["en"])}</span>'
        if enlaces and hay:
            titulo = f'<a href="#{esc(m["mapa_id"])}">{titulo}</a>'
        out.append(f'<div class="{"" if hay or not borrador else "falta"}">{titulo}</div>')
    return "".join(out)


def html_portada_nivel(temario: Mapping[str, Any], nivel: str, escritos: set[str], *, borrador: bool) -> str:
    n = temario["niveles"][nivel]["n"]
    hay = sum(1 for m in temario["mapas"] if m["nivel"] == nivel and m["mapa_id"] in escritos)
    estado = f' · wersja robocza: {hay} z {n} map' if borrador else ""
    return (
        f'<section class="pagina" lang="pl"><div class="cab"><div class="marca">{logo_svg()}<span>SŁOWOMAPA</span></div><div class="nivel">{nivel}</div></div>'
        f'<div class="sec-t">Poziom {nivel} · {n} map</div>'
        f'<div class="sub" style="margin-bottom:4mm">{esc(NOMBRE_NIVEL[nivel])}{estado} · kliknij tytuł, aby przejść do mapy</div>'
        f'<div class="toc" style="columns:2;font-size:8.6pt">{_toc_html(temario, nivel, escritos, borrador, True)}</div></section>')


def html_resumen_niveles(temario: Mapping[str, Any], nombre_archivo: Mapping[str, str], paginas: Mapping[str, int]) -> str:
    filas = "".join(
        f'<tr><td><b>{nv}</b></td><td>{esc(NOMBRE_NIVEL[nv])}</td><td>{temario["niveles"][nv]["n"]}</td><td>{esc(nombre_archivo.get(nv, ""))}</td><td>{paginas.get(nv, "")}</td></tr>' for nv in NIVELES)
    return (
        '<section class="pagina" lang="pl"><div class="cab"><div class="marca">' + logo_svg() + '<span>SŁOWOMAPA</span></div></div>'
        '<div class="sec-t">Sześć poziomów, jeden porządek</div>'
        '<p class="p-txt">Mapy są ułożone według poziomów A1–C2. W każdym poziomie idą po kolei, od tematów podstawowych do bardziej wymagających; ramka „Następny krok” prowadzi do kolejnej mapy.</p>'
        '<table class="tabla"><tr><th>Poziom</th><th>Opis</th><th>Liczba map</th><th>Plik</th><th>Stron</th></tr>' + filas + '</table>'
        f'<p class="p-txt" style="margin-top:4mm">Razem: <b>{temario["total"]} map</b>.</p></section>')


def html_toc(temario: Mapping[str, Any], escritos: set[str], *, borrador: bool) -> str:
    paginas = []
    for nv in NIVELES:
        paginas.append(
            f'<section class="pagina" lang="pl"><div class="cab"><div class="marca">{logo_svg()}<span>SŁOWOMAPA</span></div><div class="nivel">{nv}</div></div>'
            f'<div class="sec-t">Spis tematów · poziom {nv}</div>'
            f'<div class="toc">{_toc_html(temario, nv, escritos, borrador, False)}</div></section>')
    return "".join(paginas)


def html_plan(temario: Mapping[str, Any], escritos: set[str], *, borrador: bool, sesiones: int = 30) -> str:
    paginas = []
    for nv in NIVELES:
        ms = [m for m in temario["mapas"] if m["nivel"] == nv][:sesiones]
        filas = "".join(
            f'<div class="f"><i></i><span class="s">Sesja {i}</span><span class="t">{esc(m["tema"]["pl"])} <small>· mapa {m["numero"]}</small></span></div>' for i, m in enumerate(ms, 1))
        paginas.append(
            f'<section class="pagina" lang="pl"><div class="cab"><div class="marca">{logo_svg()}<span>SŁOWOMAPA</span></div><div class="nivel">{nv}</div></div>'
            f'<div class="sec-t">Plan 30 sesji · poziom {nv}</div>'
            f'<p class="p-txt">Jedna sesja to jedna mapa, około 10 minut. Odhaczaj kratki po kolei; plan prowadzi przez pierwsze {len(ms)} map poziomu {nv}.</p>'
            f'<div class="plan">{filas}</div></section>')
    return "".join(paginas)


def documento(titulo: str, cuerpo: str, *, lang: str = "pl") -> str:
    return (f'<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8"><title>{esc(titulo)}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><style>{css()}</style></head><body>{cuerpo}</body></html>')


def titulos_de(temario: Mapping[str, Any]) -> dict[str, str]:
    return {m["mapa_id"]: m["tema"]["pl"] for m in temario["mapas"]}


def html_nivel(mapas: Sequence[Mapping[str, Any]], nivel: str, temario: Mapping[str, Any], escritos: set[str], *, borrador: bool,
               densidades: Mapping[str, str] | None = None) -> str:
    tit = titulos_de(temario)
    cuerpo = html_portada_nivel(temario, nivel, escritos, borrador=borrador) + "".join(
        html_pagina(m, total_nivel=temario["niveles"][nivel]["n"], titulos=tit, densidad=(densidades or {}).get(m["mapa_id"], "d0")) for m in mapas)
    return documento(f"Słowomapa · poziom {nivel}", cuerpo)


def html_indice(temario: Mapping[str, Any], escritos: set[str], nombre_archivo: Mapping[str, str], paginas: Mapping[str, int], *, borrador: bool) -> str:
    total = temario["total"]
    if not borrador and len(escritos) != total:
        raise ValueError(f"lo anunciado = lo entregado: el índice anuncia {total} mapas y solo hay {len(escritos)}; usa borrador=True")
    cuerpo = (html_portada(total_anunciado=total, escritos=len(escritos), borrador=borrador) + html_como_usar() + html_resumen_niveles(temario, nombre_archivo, paginas)
              + html_toc(temario, escritos, borrador=borrador) + html_plan(temario, escritos, borrador=borrador))
    return documento("Słowomapa · 520 map od A1 do C2: spis i plan", cuerpo)


# ── maquetación: ¿cabe todo en la hoja? ───────────────────────────────────────────────────────────────────────────────────────────
_SCRIPT_MEDIDA = """<script>
window.addEventListener('load', function () {
  var out = [];
  document.querySelectorAll('.pagina[data-mapa]').forEach(function (p) {
    var cortado = 0, cajas = 0, cen = 0;
    p.querySelectorAll('.rama .l1, .rama .pista, .rama .uwaga, .rama .grupo').forEach(function (e) { if (e.scrollWidth > e.clientWidth + 1) cortado++; });
    p.querySelectorAll('.rama').forEach(function (c) { if (c.scrollHeight > c.clientHeight + 1) cortado++; });
    p.querySelectorAll('.col-ej, .col-der, .caja').forEach(function (c) { if (c.scrollHeight > c.clientHeight + 1) cajas++; });
    var c = p.querySelector('.centro');
    if (c) c.querySelectorAll('div').forEach(function (e) { if (e.scrollWidth > c.clientWidth - 10) cen++; });
    var pie = p.querySelector('.pie'), pr = p.getBoundingClientRect(), fr = pie ? pie.getBoundingClientRect() : null;
    out.push({id: p.dataset.mapa, sobra_px: p.scrollHeight - p.clientHeight, cajas: cajas, texto_cortado: cortado, centro: cen,
              pie_fuera: fr ? (fr.bottom > pr.bottom - 4) : false});
  });
  document.body.setAttribute('data-res', JSON.stringify(out));
});
</script>"""


def medir_maquetacion(mapas: Sequence[Mapping[str, Any]], *, titulos: Mapping[str, str] | None = None, densidad: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Mide en Chrome (sin pantalla, ``--dump-dom``) si cada hoja cabe: desborde de la hoja, cajas que desbordan, texto cortado en las tarjetas y nodo central."""
    cuerpo = "".join(html_pagina(m, titulos=titulos, densidad=(densidad or {}).get(m["mapa_id"], "d0")) for m in mapas)
    doc = documento("medida", cuerpo).replace("</body>", _SCRIPT_MEDIDA + "</body>")
    carpeta = Path(tempfile.mkdtemp(prefix="slowomapa-medida-"))
    try:
        ruta = carpeta / "m.html"
        ruta.write_text(doc, encoding="utf-8")
        cmd = [CHROME if Path(CHROME).is_file() else "google-chrome", "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={carpeta / 'perfil'}",
               "--host-resolver-rules=MAP * ~NOTFOUND", f"--window-size={PX_A4_ANCHO},{PX_A4_ALTO}", "--virtual-time-budget=4000", "--dump-dom", ruta.as_uri()]
        p = subprocess.run(cmd, env=_entorno_chrome(carpeta), capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL, check=False)
        m_ = re.search(r'data-res="([^"]*)"', p.stdout)
        if not m_:
            raise RuntimeError("no se pudo medir la maquetación (el script de medida no se ejecutó)")
        import json as _json
        filas = _json.loads(html.unescape(m_.group(1)))
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    res = {}
    for f in filas:
        f["desborda"] = f["sobra_px"] > 1 or f["cajas"] > 0 or f["texto_cortado"] > 0 or f["centro"] > 0 or f["pie_fuera"]
        res[f.pop("id")] = f
    return res


def elegir_densidades(mapas: Sequence[Mapping[str, Any]], *, titulos: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Para cada mapa, la primera densidad (d0 normal, d1 y d2 compactas) con la que cabe todo. ``ok`` False si ni la d2 basta."""
    pendientes = list(mapas)
    elegido: dict[str, dict[str, Any]] = {}
    for d in ("d0", "d1", "d2"):
        if not pendientes:
            break
        med = medir_maquetacion(pendientes, titulos=titulos, densidad={m["mapa_id"]: d for m in pendientes})
        sig = []
        for m in pendientes:
            r = med[m["mapa_id"]]
            if not r["desborda"] or d == "d2":
                elegido[m["mapa_id"]] = {"densidad": d, "ok": not r["desborda"], "medida": r}
            else:
                sig.append(m)
        pendientes = sig
    return elegido


# ── Chrome: PDF y PNG ──────────────────────────────────────────────────────────────────────────────────────────────────────────
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _entorno_chrome(carpeta: Path) -> dict[str, str]:
    """Entorno mínimo para Chrome. HOME es el REAL: con un HOME temporal Chrome 156 en macOS escribe el PDF/PNG y sale con código 2
    (volcado de crashpad al cerrar), y ``scripts.producto.render`` lo trata como fallo. El perfil sigue siendo temporal (``--user-data-dir``)."""
    return {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "TMPDIR": str(carpeta)}


def _ejecutor_chrome(argv: list[str], *, env: dict[str, str], timeout_s: float) -> subprocess.CompletedProcess:
    base = Path(env.get("TMPDIR", tempfile.gettempdir()))
    return subprocess.run(argv, env=_entorno_chrome(base), capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL, check=False)


def renderizar_pdf(html_texto: str, salida: Path, *, trabajo: Path | None = None, sobrescribir: bool = False, timeout_s: float = 180.0) -> dict[str, Any]:
    """HTML (texto) -> PDF con la ruta A (``scripts.producto.render``: perfil nuevo, sin red, verifica el PDF). Mide el tiempo."""
    from scripts.producto import render as r

    salida = Path(salida)
    if salida.exists():
        if not sobrescribir:
            raise FileExistsError(salida)
        salida.unlink()
    carpeta = Path(trabajo) if trabajo else Path(tempfile.mkdtemp(prefix="slowomapa-html-"))
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_html = carpeta / (salida.stem + ".html")
    ruta_html.write_text(html_texto, encoding="utf-8")
    t0 = time.perf_counter()
    info = r.renderizar(ruta_html, salida.resolve(), r.buscar_navegador(), ejecutar=_ejecutor_chrome, timeout_s=timeout_s)
    info["segundos"] = round(time.perf_counter() - t0, 2)
    info["html"] = str(ruta_html)
    if trabajo is None:
        shutil.rmtree(carpeta, ignore_errors=True)
    return info


def captura_png(html_texto: str, salida: Path, ancho: int, alto: int, *, escala: float = 1.0, espera_ms: int = 1500) -> dict[str, Any]:
    """Captura PNG de una página HTML con Chrome sin pantalla (ventana ancho×alto px CSS, ``escala`` de píxeles)."""
    salida = Path(salida)
    carpeta = Path(tempfile.mkdtemp(prefix="slowomapa-png-"))
    try:
        ruta_html = carpeta / "p.html"
        ruta_html.write_text(html_texto, encoding="utf-8")
        tmp = carpeta / "c.png"
        cmd = [CHROME if Path(CHROME).is_file() else "google-chrome", "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
               f"--user-data-dir={carpeta / 'perfil'}", "--host-resolver-rules=MAP * ~NOTFOUND", f"--force-device-scale-factor={escala}",
               f"--window-size={ancho},{alto}", f"--virtual-time-budget={espera_ms}", "--force-prefers-reduced-motion", f"--screenshot={tmp}", ruta_html.as_uri()]
        env = _entorno_chrome(carpeta)
        p = subprocess.run(cmd, env=env, capture_output=True, timeout=120, stdin=subprocess.DEVNULL, check=False)
        # Lo que manda es que el archivo exista y sea un PNG (cabecera) con contenido.
        if not tmp.is_file() or tmp.stat().st_size < 1000 or tmp.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"Chrome no produjo un PNG válido (código {p.returncode})")
        salida.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tmp, salida)
        return {"png": str(salida), "bytes": salida.stat().st_size}
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


PX_A4_ANCHO, PX_A4_ALTO = 794, 1123  # 210 x 297 mm a 96 dpi


def png_pagina(mapa: Mapping[str, Any], salida: Path, *, escala: float = 1.5625, titulos: Mapping[str, str] | None = None, densidad: str = "d0") -> dict[str, Any]:
    """PNG de la hoja completa (A4; escala 1,5625 = 150 dpi → 1240 × 1754 px)."""
    return captura_png(documento(mapa["tema"]["pl"], html_pagina(mapa, titulos=titulos, densidad=densidad)), salida, PX_A4_ANCHO, PX_A4_ALTO, escala=escala)


def _escena_css(ancho: int, alto: int) -> str:
    return (f"html,body{{margin:0;width:{ancho}px;height:{alto}px;overflow:hidden}}"
            ".escena{position:relative;width:100%;height:100%;background:radial-gradient(120% 90% at 30% 20%,#CDD8E1 0%,#B4C3CF 60%,#A3B4C2 100%);overflow:hidden}"
            ".hoja{position:absolute;transform-origin:0 0;box-shadow:0 18px 40px rgba(18,38,63,.30),0 3px 8px rgba(18,38,63,.18);background:#fff}"
            ".hoja .pagina{page-break-after:auto;break-after:auto}")


def png_miniatura(mapa: Mapping[str, Any], salida: Path, *, ancho: int = 720, alto: int = 960, titulos: Mapping[str, str] | None = None, densidad: str = "d0") -> dict[str, Any]:
    """Miniatura de la landing: la hoja REAL sobre fondo liso (proporción 3:4, igual que ``final/muestra-N.webp``)."""
    k = (alto * 0.92) / PX_A4_ALTO
    x = (ancho - PX_A4_ANCHO * k) / 2
    y = (alto - PX_A4_ALTO * k) / 2
    cuerpo = (f'<div class="escena"><div class="hoja" style="left:{x:.1f}px;top:{y:.1f}px;width:{PX_A4_ANCHO}px;height:{PX_A4_ALTO}px;transform:scale({k:.4f})">'
              f'{html_pagina(mapa, titulos=titulos, densidad=densidad)}</div></div>')
    doc = documento("miniatura", cuerpo).replace("</style>", _escena_css(ancho, alto) + "</style>")
    return captura_png(doc, salida, ancho, alto, escala=1.0)


def png_principal(mapas: Sequence[Mapping[str, Any]], salida: Path, *, ancho: int = 1280, alto: int = 720, titulos: Mapping[str, str] | None = None,
                  densidades: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Imagen principal 16:9: tres hojas reales (la del centro, delante) sobre fondo liso."""
    k = (alto * 0.82) / PX_A4_ALTO
    w = PX_A4_ANCHO * k
    y = (alto - PX_A4_ALTO * k) / 2
    centros = [ancho / 2 - w / 2 - w * 0.74, ancho / 2 - w / 2, ancho / 2 - w / 2 + w * 0.74]
    giros = [-5.0, 0.0, 5.0]
    orden = [0, 2, 1]
    piezas = []
    for i in orden:
        m = mapas[i]
        piezas.append(f'<div class="hoja" style="left:{centros[i] - (PX_A4_ANCHO - w) / 2:.1f}px;top:{y + (0 if i == 1 else 14) - (PX_A4_ALTO - PX_A4_ALTO * k) / 2:.1f}px;width:{PX_A4_ANCHO}px;height:{PX_A4_ALTO}px;'
                      f'transform:rotate({giros[i]}deg) scale({k:.4f});transform-origin:{PX_A4_ANCHO / 2}px {PX_A4_ALTO / 2}px">{html_pagina(m, titulos=titulos, densidad=(densidades or {}).get(m["mapa_id"], "d0"))}</div>')
    doc = documento("principal", f'<div class="escena">{"".join(piezas)}</div>').replace("</style>", _escena_css(ancho, alto) + "</style>")
    return captura_png(doc, salida, ancho, alto, escala=1.0)
