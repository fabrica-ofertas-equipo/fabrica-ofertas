#!/usr/bin/env python3
"""Imprime una sección (por título) de todos los digests de videos.

Uso:
  python3 -I extract_section.py <carpeta_digest> "<regex del título de sección>" [grupo1,grupo2]

Ejemplos:
  python3 -I extract_section.py docs/fuente/youtube/_digest "mercados|paises"
  python3 -I extract_section.py docs/fuente/youtube/_digest "campa(ñ|n)as" santiago-bilbao,matias-bonardo

Omite las secciones que dicen solo "No se menciona". Sirve para que un agente sintetice un tema
sin leer los ~190 digests completos.
"""
import re
import sys
from pathlib import Path


def main():
    base = Path(sys.argv[1])
    rx = re.compile(sys.argv[2], re.I)
    groups = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    for f in sorted(base.glob("*/*.md")):
        g = f.parent.name
        if groups and g not in groups:
            continue
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        title = lines[0].lstrip("# ").strip() if lines else f.stem
        out, cap = [], False
        for l in lines[1:]:
            if l.startswith("## "):
                cap = bool(rx.search(l))
                if cap:
                    out.append(l)
                continue
            if cap:
                out.append(l)
        body = "\n".join(x for x in out if x.strip())
        if body and not re.search(r"no se menciona\.?\s*$", body, re.I):
            print(f"\n### [{g}/{f.stem}] {title}\n{body}")


if __name__ == "__main__":
    main()
