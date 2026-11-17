"""Boceto de composición (guía) para que Kie genere una escena con las superficies de marcador EXACTAMENTE donde se quieren.

Lee un JSON con las superficies (cuadriláteros en píxeles) y dibuja con Chrome sin pantalla un boceto plano: fondo claro,
escritorio, pantallas en magenta ``#FF00FF`` (con marco y soporte) y portadas de broszury en verde ``#00FF00`` (con lomo azul marino a la
izquierda y canto de páginas blanco a la derecha). El boceto se sube a Kie como referencia (``image_input``) y el prompt pide
convertirlo en una escena fotorrealista conservando posición, tamaño y perspectiva de cada forma, lo que evita solapes entre
broszury y fija un encuadre distinto del referente. Luego ``componer_portadas.py`` detecta las superficies reales de la escena.

Uso::

    python3 scripts/imagenes/guia_escena.py ESPEC.json --salida GUIA.png

``ESPEC.json``: ``{"ancho": 2048, "alto": 2048, "desk": [[0,880],[2048,800]], "sombras": true, "superficies": [{"id": "monitor", "tipo": "pantalla",
"quad": [[x,y],[x,y],[x,y],[x,y]]}, {"id": "b1", "tipo": "broszura", "quad": [...]}]}`` (quad: TL, TR, BR, BL). Tipos: ``pantalla``,
``telefono``, ``broszura``.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

CHROME_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _crecer(q, px):
    cx = sum(p[0] for p in q) / 4
    cy = sum(p[1] for p in q) / 4
    out = []
    for x, y in q:
        dx, dy = x - cx, y - cy
        n = (dx * dx + dy * dy) ** 0.5 or 1
        out.append((x + dx / n * px, y + dy / n * px))
    return out


def _pts(q):
    return " ".join(f"{x:.0f},{y:.0f}" for x, y in q)


def svg_guia(esp: dict) -> str:
    w, h = esp["ancho"], esp["alto"]
    d0, d1 = esp["desk"]
    p = [f'<rect width="{w}" height="{h}" fill="#D7E0E6"/>',
         f'<polygon points="{d0[0]},{d0[1]} {d1[0]},{d1[1]} {w},{h} 0,{h}" fill="#F2F5F7"/>']
    for s in esp["superficies"]:
        q = [tuple(pt) for pt in s["quad"]]
        tipo = s["tipo"]
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
        if tipo in ("pantalla", "telefono"):
            marco = 14 if tipo == "telefono" else 24
            if esp.get("sombras", True):
                p.append(f'<ellipse cx="{(x3 + x2) / 2:.0f}" cy="{max(y2, y3) + 70:.0f}" rx="{abs(x2 - x3) * 0.28:.0f}" ry="16" fill="#B9C3CA"/>')
            p.append(f'<polygon points="{(x3 + x2) / 2 - 40:.0f},{max(y2, y3):.0f} {(x3 + x2) / 2 + 40:.0f},{max(y2, y3):.0f} {(x3 + x2) / 2 + 60:.0f},{max(y2, y3) + 70:.0f} {(x3 + x2) / 2 - 60:.0f},{max(y2, y3) + 70:.0f}" fill="#AEB8BF"/>')
            p.append(f'<polygon points="{_pts(_crecer(q, marco))}" fill="#262B31"/>')
            p.append(f'<polygon points="{_pts(q)}" fill="#FF00FF"/>')
        else:                                                    # broszura: lomo azul marino a la izquierda, canto blanco a la derecha
            if esp.get("sombras", True):                 # con "sombras": false el modelo dibuja las suyas (las elipses del boceto salen como sombras flotantes)
                p.append(f'<ellipse cx="{(x3 + x2) / 2 + 10:.0f}" cy="{max(y2, y3) + 14:.0f}" rx="{abs(x2 - x3) * 0.62:.0f}" ry="16" fill="#BCC6CD"/>')
            p.append(f'<polygon points="{x1:.0f},{y1:.0f} {x1 + 16:.0f},{y1 - 5:.0f} {x2 + 16:.0f},{y2 - 5:.0f} {x2:.0f},{y2:.0f}" fill="#FFFFFF" stroke="#C9D1D7" stroke-width="2"/>')
            p.append(f'<polygon points="{x0 - 26:.0f},{y0 - 6:.0f} {x0:.0f},{y0:.0f} {x3:.0f},{y3:.0f} {x3 - 26:.0f},{y3 - 6:.0f}" fill="#12263F"/>')
            p.append(f'<polygon points="{_pts(q)}" fill="#00FF00"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{"".join(p)}</svg>'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Boceto de composición para escenas con marcadores.")
    ap.add_argument("espec", type=Path)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--chrome", default=CHROME_MAC)
    a = ap.parse_args(argv)
    esp = json.loads(a.espec.read_text(encoding="utf-8"))
    html = a.salida.with_suffix(".html")
    html.write_text(f'<!doctype html><html><body style="margin:0">{svg_guia(esp)}</body></html>', encoding="utf-8")
    subprocess.run([a.chrome, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1", f"--window-size={esp['ancho']},{esp['alto']}",
                    f"--screenshot={a.salida}", html.resolve().as_uri()], capture_output=True, timeout=120)
    if not a.salida.exists() or a.salida.stat().st_size < 1000:
        print("Chrome no produjo la guía", file=sys.stderr)
        return 6
    print(f"escrita {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
