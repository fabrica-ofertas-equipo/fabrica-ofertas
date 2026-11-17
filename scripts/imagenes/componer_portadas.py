"""Pega portadas planas YA VALIDADAS sobre una escena de Kie con superficies de marcador: el texto de la imagen final es exacto.

Por qué
-------
Los modelos de imagen fallan con el texto pequeño (pies de móvil y tableta, subtítulos, «Około»). En lugar de pedirles que
escriban el texto, Kie genera solo la ESCENA (escritorio, luz, objetos) con las superficies a rellenar en un color plano de
marcador (pantallas en magenta ``#FF00FF``, portadas de broszury en verde lima ``#00FF00``) y este script:

1. **detecta** cada superficie de marcador (componentes conexas por color, sobre una copia reducida de la escena con ``ffmpeg``),
   saca sus cuatro esquinas y estima la proporción real del rectángulo en perspectiva (método de Zhang y He);
2. **asigna** a cada superficie una portada plana (``referencias/*.png``) por orden de área o de posición;
3. **compone** en Chrome sin pantalla: cada portada se deforma con una homografía CSS (``matrix3d``) hasta las esquinas de su
   superficie, se recorta con la máscara real del marcador (bordes redondeados incluidos, ligeramente dilatada para no dejar
   el halo de color) y recibe la luz de la escena (el brillo del marcador, normalizado, se multiplica sobre la portada).

No usa Pillow ni numpy: solo la biblioteca estándar, ``ffmpeg`` y Chrome. No llama a la red ni gasta créditos.

Uso::

    python3 scripts/imagenes/componer_portadas.py detectar ESCENA.png --salida DIR_DEBUG
    python3 scripts/imagenes/componer_portadas.py componer CONFIG.json

``CONFIG.json`` (``supersampling``: 2 renderiza al doble y reduce con Lanczos; ``deteccion``: 2048 detecta a la resolución de la escena)::

    {"escena": "candidatos/hero/r2-nbp-01.png", "salida": "referencias/comp/hero.png", "base": "<carpeta assets>",
     "expandir": 0.025, "dilatar": 3, "sombreado": 0.85, "recorte": [75, 95, 1690, 1690],
     "asignaciones": [{"nombre": "monitor", "color": "magenta", "orden": "area_desc", "idx": 0, "ref": "referencias/ekran.png", "recortar": true},
                      {"nombre": "dodatek 1", "color": "green", "orden": "x_asc", "idx": 0, "ref": "referencias/bono-1.png"}]}

``borde: "quad"`` recorta con el cuadrilátero (broszury: cantos rectos y limpios) en lugar de la máscara de color (pantallas redondeadas); ``expandir`` por superficie lo afina. ``recortar: true`` ajusta la portada a la proporción real de la superficie recortando márgenes (no estira); sin él se estira
(las broszury) y el informe indica la desviación de proporción. Salidas: 0 ok · 2 uso o escena sin las superficies esperadas · 6 Chrome falló.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

CHROME_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LADO_DETECCION = 1024
AREA_MINIMA = 400                       # píxeles (a la escala de detección) para ser una superficie y no ruido


# ── PNG mínimo (sin librerías) ──────────────────────────────────────────────
def _trozo(tipo: bytes, datos: bytes) -> bytes:
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)


def escribir_png(ruta: Path | None, ancho: int, alto: int, filas: list[bytes], canales: int) -> bytes:
    """PNG de 8 bits (canales 1=gris, 3=RGB, 4=RGBA). Devuelve los bytes y, si ``ruta``, también los escribe."""
    tipo = {1: 0, 3: 2, 4: 6}[canales]
    crudo = b"".join(b"\x00" + f for f in filas)
    datos = (b"\x89PNG\r\n\x1a\n" + _trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, tipo, 0, 0, 0)) +
             _trozo(b"IDAT", zlib.compress(crudo, 6)) + _trozo(b"IEND", b""))
    if ruta:
        Path(ruta).write_bytes(datos)
    return datos


def dims_png(ruta: Path) -> tuple[int, int]:
    cab = Path(ruta).read_bytes()[:24]
    if cab[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{ruta} no es PNG")
    return struct.unpack(">II", cab[16:24])


def uri_png(datos: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(datos).decode("ascii")


# ── detección ───────────────────────────────────────────────────────────────
def rgb_reducido(escena: Path, dw: int, dh: int) -> bytes:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(escena), "-vf", f"scale={dw}:{dh}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=120)
    if len(r.stdout) != dw * dh * 3:
        raise RuntimeError("ffmpeg no devolvió la escena reducida")
    return r.stdout


def codigo_color(r: int, g: int, b: int) -> int:
    """1 = magenta, 2 = verde lima, 0 = nada. Por matiz y saturación, para que las sombras sobre el marcador (verde oscuro) cuenten."""
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 40 or (mx - mn) / mx < 0.5:
        return 0
    d = mx - mn
    if mx == r:
        hue = (60 * ((g - b) / d)) % 360
    elif mx == g:
        hue = 60 * ((b - r) / d) + 120
    else:
        hue = 60 * ((r - g) / d) + 240
    if 285 <= hue <= 335 and mx >= 80:
        return 1
    if 85 <= hue <= 160 and mx >= 45:
        return 2
    return 0


COLORES = {"magenta": 1, "green": 2}


def componentes(rgb: bytes, dw: int, dh: int) -> list[dict]:
    """Componentes conexas (8 vecinos) por color de marcador. Cada una: color, píxeles (x, y), área."""
    n = dw * dh
    cod = bytearray(n)
    for i in range(n):
        j = 3 * i
        cod[i] = codigo_color(rgb[j], rgb[j + 1], rgb[j + 2])
    visto = bytearray(n)
    salida = []
    for i0 in range(n):
        if not cod[i0] or visto[i0]:
            continue
        c = cod[i0]
        pila, pix = [i0], []
        visto[i0] = 1
        while pila:
            i = pila.pop()
            pix.append(i)
            x, y = i % dw, i // dw
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= dh:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if 0 <= xx < dw:
                        k = yy * dw + xx
                        if cod[k] == c and not visto[k]:
                            visto[k] = 1
                            pila.append(k)
        if len(pix) >= AREA_MINIMA:
            salida.append({"color": "magenta" if c == 1 else "green", "pix": pix, "area": len(pix)})
    return salida


def esquinas(pix: list[int], dw: int) -> list[tuple[float, float]]:
    """TL, TR, BR, BL por extremos diagonales (válido para rectángulos con perspectiva moderada)."""
    mejor = {"tl": (1e18, None), "br": (-1e18, None), "tr": (-1e18, None), "bl": (1e18, None)}
    for i in pix:
        x, y = i % dw, i // dw
        s, d = x + y, x - y
        if s < mejor["tl"][0]:
            mejor["tl"] = (s, (x, y))
        if s > mejor["br"][0]:
            mejor["br"] = (s, (x, y))
        if d > mejor["tr"][0]:
            mejor["tr"] = (d, (x, y))
        if d < mejor["bl"][0]:
            mejor["bl"] = (d, (x, y))
    return [tuple(map(float, mejor[k][1])) for k in ("tl", "tr", "br", "bl")]


def aspecto_real(q: list[tuple[float, float]], u0: float, v0: float) -> float | None:
    """Ancho/alto reales del rectángulo visto en perspectiva (Zhang y He, 2007); ``None`` si la vista es casi frontal."""
    def v(p):
        return (p[0] - u0, p[1] - v0, 1.0)

    def cruz(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    def punto(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    m1, m2, m4, m3 = v(q[0]), v(q[1]), v(q[2]), v(q[3])           # TL, TR, BR, BL
    try:
        k2 = punto(cruz(m1, m4), m3) / punto(cruz(m2, m4), m3)
        k3 = punto(cruz(m1, m4), m2) / punto(cruz(m3, m4), m2)
    except ZeroDivisionError:
        return None
    n2 = tuple(k2 * a - b for a, b in zip(m2, m1))
    n3 = tuple(k3 * a - b for a, b in zip(m3, m1))
    if abs(n2[2] * n3[2]) < 1e-9:
        return None
    f2 = -(n2[0] * n3[0] + n2[1] * n3[1]) / (n2[2] * n3[2])
    if f2 <= 0:
        return None
    num = (n2[0] ** 2 + n2[1] ** 2) / f2 + n2[2] ** 2
    den = (n3[0] ** 2 + n3[1] ** 2) / f2 + n3[2] ** 2
    return math.sqrt(num / den) if den > 0 and num > 0 else None


def aspecto_aproximado(q) -> float:
    d = math.dist
    return (d(q[0], q[1]) + d(q[3], q[2])) / (d(q[0], q[3]) + d(q[1], q[2]))


def detectar(escena: Path, lado: int = LADO_DETECCION) -> dict:
    w, h = dims_png(escena)
    esc = min(1.0, lado / max(w, h))
    dw, dh = max(1, round(w * esc)), max(1, round(h * esc))
    rgb = rgb_reducido(escena, dw, dh)
    regiones = componentes(rgb, dw, dh)
    for r in regiones:
        q = esquinas(r["pix"], dw)
        r["quad_det"] = q
        r["quad"] = [(x / esc, y / esc) for x, y in q]
        r["cx"] = sum(i % dw for i in r["pix"]) / r["area"] / esc
        r["cy"] = sum(i // dw for i in r["pix"]) / r["area"] / esc
        r["area_px"] = r["area"] / (esc * esc)
        ar = aspecto_real(r["quad"], w / 2, h / 2)
        r["aspecto_real"] = ar if ar and 0.15 < ar < 6 else aspecto_aproximado(r["quad"])
        r["aspecto_metodo"] = "zhang_he" if ar and 0.15 < ar < 6 else "bordes"
    return {"ancho": w, "alto": h, "dw": dw, "dh": dh, "esc": esc, "rgb": rgb, "regiones": regiones}


def ordenar(regiones: list[dict], color: str, orden: str) -> list[dict]:
    r = [x for x in regiones if x["color"] == color]
    clave = {"area_desc": lambda x: -x["area"], "area_asc": lambda x: x["area"], "x_asc": lambda x: x["cx"], "x_desc": lambda x: -x["cx"],
             "y_asc": lambda x: x["cy"], "y_desc": lambda x: -x["cy"]}[orden]
    return sorted(r, key=clave)


# ── geometría ───────────────────────────────────────────────────────────────
def homografia(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> list[list[float]]:
    """H (3x3, h33 = 1) que lleva cada punto de ``src`` a su par en ``dst`` (eliminación gaussiana)."""
    a, b = [], []
    for (x, y), (X, Y) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -X * x, -X * y]); b.append(X)
        a.append([0, 0, 0, x, y, 1, -Y * x, -Y * y]); b.append(Y)
    n = 8
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        a[c], a[p], b[c], b[p] = a[p], a[c], b[p], b[c]
        for r in range(c + 1, n):
            f = a[r][c] / a[c][c]
            for k in range(c, n):
                a[r][k] -= f * a[c][k]
            b[r] -= f * b[c]
    h = [0.0] * n
    for c in range(n - 1, -1, -1):
        h[c] = (b[c] - sum(a[c][k] * h[k] for k in range(c + 1, n))) / a[c][c]
    return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]]


def css_matrix3d(H: list[list[float]]) -> str:
    (a, b, c), (d, e, f), (g, hh, _) = H
    vals = [a, d, 0, g, b, e, 0, hh, 0, 0, 1, 0, c, f, 0, 1]
    return "matrix3d(" + ",".join(f"{v:.10g}" for v in vals) + ")"


def expandir_quad(q: list[tuple[float, float]], frac: float) -> list[tuple[float, float]]:
    cx = sum(p[0] for p in q) / 4
    cy = sum(p[1] for p in q) / 4
    return [(cx + (x - cx) * (1 + frac), cy + (y - cy) * (1 + frac)) for x, y in q]


def recorte_para_aspecto(fw: int, fh: int, aspecto: float) -> tuple[float, float, float, float]:
    """Subrectángulo centrado de la portada con la proporción ``aspecto`` (recorta márgenes; no estira)."""
    af = fw / fh
    if aspecto > af:
        ch = fw / aspecto
        return 0.0, (fh - ch) / 2, float(fw), ch
    cw = fh * aspecto
    return (fw - cw) / 2, 0.0, cw, float(fh)


# ── máscara y sombreado por región ──────────────────────────────────────────
def _dilatar_filas(filas: list[int], bw: int, r: int) -> list[int]:
    """Dilatación cuadrada de radio ``r`` sobre filas de bits (un entero por fila): rápida y sin bucles por píxel."""
    tope = (1 << bw) - 1
    for _ in range(r):
        filas = [(f | (f << 1) | (f >> 1)) & tope for f in filas]
    for _ in range(r):
        n = len(filas)
        filas = [filas[max(0, i - 1)] | filas[i] | filas[min(n - 1, i + 1)] for i in range(n)]
    return filas


def _suavizar(filas: list[bytes]) -> list[bytes]:
    """Desenfoque [1,2,1] en horizontal y vertical: el borde de la máscara pasa de escalera a degradado de ~1 px."""
    h = [bytes([r[0]]) + bytes((a + 2 * b + c) >> 2 for a, b, c in zip(r, r[1:], r[2:])) + bytes([r[-1]]) if len(r) > 2 else r for r in filas]
    out = []
    for i in range(len(h)):
        a, b, c = h[max(0, i - 1)], h[i], h[min(len(h) - 1, i + 1)]
        out.append(bytes((x + 2 * y + z) >> 2 for x, y, z in zip(a, b, c)))
    return out


def mascara_y_sombra(rgb: bytes, dw: int, dh: int, pix: list[int], dilatar: int = 2) -> dict:
    """Recortes (a la escala de detección) de la máscara RGBA dilatada con borde suave y del sombreado multiplicativo de una región."""
    xs = [i % dw for i in pix]
    ys = [i // dw for i in pix]
    m = dilatar + 3
    x0, x1 = max(0, min(xs) - m), min(dw - 1, max(xs) + m)
    y0, y1 = max(0, min(ys) - m), min(dh - 1, max(ys) + m)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    filas = [0] * bh
    lum_vals = []
    lum_px = {}
    for i in pix:
        x, y = i % dw - x0, i // dw - y0
        filas[y] |= 1 << x
        j = 3 * i
        lum = 0.2126 * rgb[j] + 0.7152 * rgb[j + 1] + 0.0722 * rgb[j + 2]
        lum_vals.append(lum)
        lum_px[(x, y)] = lum
    filas = _dilatar_filas(filas, bw, dilatar)
    tabla = bytes.maketrans(b"01", b"\x00\xff")
    alfa = [format(f, f"0{bw}b")[::-1].encode().translate(tabla) for f in filas]
    alfa = _suavizar(alfa)
    lum_vals.sort()
    ref = lum_vals[int(len(lum_vals) * 0.95)] or 1.0           # el brillo del marcador (p95) = «sin sombra»
    filas_m, filas_s = [], []
    for y in range(bh):
        fm, fs = bytearray(4 * bw), bytearray(b"\xff" * (4 * bw))
        fm[3::4] = alfa[y]
        for x in range(bw):
            lum = lum_px.get((x, y))
            if lum is not None:
                v = int(255 * max(0.55, min(1.0, lum / ref)))
                fs[4 * x:4 * x + 3] = bytes((v, v, v))
        filas_m.append(bytes(fm))
        filas_s.append(bytes(fs))
    return {"x0": x0, "y0": y0, "bw": bw, "bh": bh,
            "mascara": escribir_png(None, bw, bh, filas_m, 4), "sombra": escribir_png(None, bw, bh, filas_s, 4)}


# ── composición ─────────────────────────────────────────────────────────────
def reducir_portada(ref: Path, fw: int, fh: int, factor: float, tmp: Path) -> tuple[Path, int, int]:
    """Copia de ``ref`` reducida con Lanczos (ffmpeg): Chrome deforma mucho mejor desde un tamaño cercano al destino que desde 4x más grande."""
    nw, nh = max(2, round(fw * factor)), max(2, round(fh * factor))
    destino = tmp / f"{ref.stem}_{nw}x{nh}.png"
    if not destino.exists():
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ref), "-vf", f"scale={nw}:{nh}:flags=lanczos", str(destino)], capture_output=True, timeout=120)
        if r.returncode != 0 or not destino.exists():
            raise RuntimeError(f"ffmpeg no pudo reducir {ref.name}")
    return destino, nw, nh


def html_composicion(det: dict, escena: Path, asign: list[dict], base: Path, expandir: float, sombreado: float,
                     tmp: Path | None = None, dilatar: int = 3, ss: int = 1) -> tuple[str, list[dict]]:
    w, h, esc, dw, dh = det["ancho"], det["alto"], det["esc"], det["dw"], det["dh"]
    capas, informe = [], []
    for a in asign:
        reg = a["_region"]
        ref = Path(a["ref"]) if Path(a["ref"]).is_absolute() else base / a["ref"]
        fw, fh = dims_png(ref)
        q = expandir_quad(reg["quad"], float(a.get("expandir", expandir)))
        ms = mascara_y_sombra(det["rgb"], dw, dh, reg["pix"], int(a.get("dilatar", dilatar)))
        ox, oy = ms["x0"] / esc, ms["y0"] / esc                      # origen del recorte en píxeles de la escena
        qloc = [(x - ox, y - oy) for x, y in q]
        asp = reg["aspecto_real"]
        if a.get("recortar"):
            sx, sy, cw, ch = recorte_para_aspecto(fw, fh, asp)
            desv = 0.0
        else:
            sx, sy, cw, ch = 0.0, 0.0, float(fw), float(fh)
            desv = (asp / (fw / fh) - 1) * 100
        # tamaño aproximado de la superficie en la escena, para reducir la portada con Lanczos a ~1,6x antes de deformarla
        wq = (math.dist(q[0], q[1]) + math.dist(q[3], q[2])) / 2
        hq = (math.dist(q[0], q[3]) + math.dist(q[1], q[2])) / 2
        factor = min(1.0, 1.6 * ss * max(wq / cw, hq / ch))
        ref_css, fw2, fh2 = (ref, fw, fh)
        if tmp is not None and factor < 0.9:
            ref_css, fw2, fh2 = reducir_portada(ref, fw, fh, factor, tmp)
        k = fw2 / fw
        src = [(sx * k, sy * k), ((sx + cw) * k, sy * k), ((sx + cw) * k, (sy + ch) * k), (sx * k, (sy + ch) * k)]
        H = homografia(src, qloc)
        ancho_css, alto_css = ms["bw"] / esc, ms["bh"] / esc
        if a.get("borde") == "quad":        # rectángulos (broszury): el borde lo da el cuadrilátero (recto y suave), no la máscara de color
            poligono = ",".join(f"{x:.2f}px {y:.2f}px" for x, y in qloc)
            recorte_css = f"clip-path:polygon({poligono});-webkit-clip-path:polygon({poligono})"
        else:                               # pantallas con esquinas redondeadas: máscara real del marcador
            recorte_css = (f'-webkit-mask-image:url({uri_png(ms["mascara"])});-webkit-mask-size:100% 100%;'
                           f'mask-image:url({uri_png(ms["mascara"])});mask-size:100% 100%')
        capas.append(
            f'<div style="position:absolute;left:{ox:.2f}px;top:{oy:.2f}px;width:{ancho_css:.2f}px;height:{alto_css:.2f}px;{recorte_css}">'
            f'<img src="{ref_css.resolve().as_uri()}" style="position:absolute;left:0;top:0;width:{fw2}px;height:{fh2}px;transform-origin:0 0;transform:{css_matrix3d(H)}">'
            f'<div style="position:absolute;inset:0;background:url({uri_png(ms["sombra"])}) 0 0/100% 100%;mix-blend-mode:multiply;opacity:{sombreado}"></div></div>')
        informe.append({"nombre": a.get("nombre"), "color": reg["color"], "ref": a["ref"], "centro": [round(reg["cx"]), round(reg["cy"])],
                        "area_px": round(reg["area_px"]), "aspecto_superficie": round(asp, 3), "aspecto_metodo": reg["aspecto_metodo"],
                        "aspecto_portada": round(fw / fh, 3), "recortada": bool(a.get("recortar")), "desviacion_proporcion_pct": round(desv, 1)})
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>*{{margin:0;padding:0}}html,body{{width:{w}px;height:{h}px;overflow:hidden;background:#fff}}'
            f'.esc{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:url("{escena.resolve().as_uri()}") 0 0/{w}px {h}px no-repeat}}</style></head>'
            f'<body><div class="esc">{"".join(capas)}</div></body></html>')
    return html, informe


def renderizar(html: str, destino: Path, w: int, h: int, tmp: Path, chrome: str = CHROME_MAC, dpr: int = 1) -> None:
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(html, encoding="utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([chrome, "--headless=new", "--hide-scrollbars", f"--force-device-scale-factor={dpr}", f"--window-size={w},{h}",
                        f"--screenshot={destino}", tmp.resolve().as_uri()], capture_output=True, text=True, timeout=180)
    if not destino.exists() or destino.stat().st_size < 1000:
        raise RuntimeError(f"Chrome no produjo {destino.name}: {r.stderr[-300:]}")


def componer(cfg: dict, chrome: str = CHROME_MAC) -> dict:
    """Detecta, asigna y compone. ``supersampling: 2`` renderiza al doble y reduce con Lanczos (cantos sin escalera); ``deteccion`` fija la
    resolución de detección (2048 = la de la escena: máscara exacta); ``recorte`` = [x, y, ancho, alto] del encuadre final."""
    base = Path(cfg.get("base", ".")).resolve()
    escena = Path(cfg["escena"]) if Path(cfg["escena"]).is_absolute() else base / cfg["escena"]
    salida = Path(cfg["salida"]) if Path(cfg["salida"]).is_absolute() else base / cfg["salida"]
    det = detectar(escena, int(cfg.get("deteccion", LADO_DETECCION)))
    ss = max(1, int(cfg.get("supersampling", 1)))
    dilatar = int(cfg["dilatar"]) if cfg.get("dilatar") else max(1, round(6 * det["esc"]))
    asign = []
    for a in cfg["asignaciones"]:
        cand = ordenar(det["regiones"], a["color"], a.get("orden", "area_desc"))
        if a.get("idx", 0) >= len(cand):
            raise SystemExit(f"2: la escena no tiene la superficie {a.get('nombre')} ({a['color']}, {a.get('orden')}, idx {a.get('idx', 0)}); hay {len(cand)} de ese color")
        asign.append({**a, "_region": cand[a.get("idx", 0)]})
    w, h = det["ancho"], det["alto"]
    with tempfile.TemporaryDirectory() as td:
        html, informe = html_composicion(det, escena, asign, base, float(cfg.get("expandir", 0.025)), float(cfg.get("sombreado", 0.85)), Path(td), dilatar, ss)
        crudo = Path(td) / "completa.png"
        renderizar(html, crudo, w, h, salida.with_suffix(".html"), chrome, ss)
        filtros = ([f"scale={w}:{h}:flags=lanczos"] if ss > 1 else []) + ([f"crop={int(cfg['recorte'][2])}:{int(cfg['recorte'][3])}:{int(cfg['recorte'][0])}:{int(cfg['recorte'][1])}"] if cfg.get("recorte") else [])
        salida.parent.mkdir(parents=True, exist_ok=True)
        if filtros:
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(crudo), "-vf", ",".join(filtros), str(salida)], capture_output=True, timeout=240)
            if r.returncode != 0 or not salida.exists():
                raise RuntimeError("ffmpeg no pudo reducir o recortar la composición")
        else:
            shutil.copy(crudo, salida)
    return {"escena": str(escena), "salida": str(salida), "recorte": cfg.get("recorte"), "supersampling": ss, "deteccion_px": max(det["ancho"], det["alto"]) * det["esc"],
            "superficies_detectadas": {c: sum(1 for r in det["regiones"] if r["color"] == c) for c in COLORES},
            "asignadas": informe}


def depurar(escena: Path, destino: Path, chrome: str = CHROME_MAC) -> dict:
    """Dibuja las superficies detectadas (cuadriláteros numerados) sobre la escena, para comprobarlas a ojo."""
    det = detectar(escena)
    w, h = det["ancho"], det["alto"]
    svg = []
    resumen = []
    for color in ("magenta", "green"):
        for n, r in enumerate(ordenar(det["regiones"], color, "x_asc")):
            pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in r["quad"])
            col = "#ffff00" if color == "magenta" else "#ff4400"
            svg.append(f'<polygon points="{pts}" fill="none" stroke="{col}" stroke-width="4"/>'
                       f'<text x="{r["cx"]:.0f}" y="{r["cy"]:.0f}" font-size="44" font-weight="700" fill="#fff" stroke="#000" stroke-width="2" text-anchor="middle">{color[0]}{n}</text>')
            resumen.append({"id": f"{color[0]}{n}", "color": color, "centro": [round(r["cx"]), round(r["cy"])], "area_px": round(r["area_px"]),
                            "aspecto_real": round(r["aspecto_real"], 3), "metodo": r["aspecto_metodo"], "quad": [[round(x), round(y)] for x, y in r["quad"]]})
    html = (f'<!doctype html><html><body style="margin:0"><div style="position:relative;width:{w}px;height:{h}px;background:url({escena.resolve().as_uri()}) 0 0/{w}px {h}px no-repeat">'
            f'<svg width="{w}" height="{h}" style="position:absolute;left:0;top:0">{"".join(svg)}</svg></div></body></html>')
    renderizar(html, destino, w, h, destino.with_suffix(".html"), chrome)
    return {"superficies": resumen}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pega portadas planas sobre una escena de Kie con superficies de marcador.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detectar")
    d.add_argument("escena", type=Path)
    d.add_argument("--salida", type=Path, required=True, help="PNG de depuración con los cuadriláteros")
    c = sub.add_parser("componer")
    c.add_argument("config", type=Path)
    for sp in (d, c):
        sp.add_argument("--chrome", default=CHROME_MAC)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "detectar":
            print(json.dumps(depurar(a.escena, a.salida, a.chrome), ensure_ascii=False, indent=1))
        else:
            print(json.dumps(componer(json.loads(a.config.read_text(encoding="utf-8")), a.chrome), ensure_ascii=False, indent=1))
        return 0
    except RuntimeError as e:
        print(f"CHROME/FFMPEG: {e}", file=sys.stderr)
        return 6


if __name__ == "__main__":
    sys.exit(main())
