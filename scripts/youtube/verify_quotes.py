#!/usr/bin/env python3
"""Verifica que las citas textuales entre comillas de un digest aparezcan (con tolerancia
a errores de subtítulos automáticos) en la transcripción de origen.

Uso:
  python3 -I verify_quotes.py <digest.md> <transcripcion.md> [umbral=0.72]

Salida (JSON en stdout):
  {"total": N, "verificadas": M, "no_verificadas": [{"cita": "...", "ratio": 0.41}, ...]}
Criterio: se toma una ventana de la transcripción alrededor de las posiciones donde aparecen
las primeras palabras de la cita y se mide qué fracción de las palabras de la cita está presente.
Es una verificación aproximada (determinista) para detectar citas inventadas, no para validar
la interpretación.
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


def norm(s: str):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9$%€£ ]+", " ", s)
    return s.split()


def transcript_words(path: str):
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = [l for l in txt.splitlines() if re.match(r"^\[\d", l)]
    body = "\n".join(re.sub(r"^\[\d+:\d{2}(?::\d{2})?\]\s*", "", l) for l in lines)
    return norm(body)


QUOTE = re.compile(r"[\"“«]([^\"”»\n]{12,300})[\"”»]")


def best_ratio(q, tw, index):
    n = len(q)
    if n == 0:
        return 0.0
    qset = set(q)
    starts = set()
    for w in q[:4]:
        for pos in index.get(w, [])[:500]:
            starts.add(pos)
    best = 0.0
    for pos in starts:
        lo = max(0, pos - 4)
        hi = min(len(tw), pos + int(n * 1.6) + 4)
        wset = set(tw[lo:hi])
        r = len(qset & wset) / len(qset)
        if r > best:
            best = r
    return best


def main():
    digest, trans = sys.argv[1], sys.argv[2]
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.72
    tw = transcript_words(trans)
    index = defaultdict(list)
    for i, w in enumerate(tw):
        index[w].append(i)
    text = Path(digest).read_text(encoding="utf-8", errors="replace")
    quotes = [m.group(1).strip() for m in QUOTE.finditer(text)]
    quotes = [q for q in quotes if len(q.split()) >= 4]
    bad = []
    ok = 0
    for q in quotes:
        r = best_ratio(norm(q), tw, index)
        if r >= thr:
            ok += 1
        else:
            bad.append({"cita": q[:160], "ratio": round(r, 2)})
    print(json.dumps({"total": len(quotes), "verificadas": ok, "no_verificadas": bad}, ensure_ascii=False))


if __name__ == "__main__":
    main()
