#!/usr/bin/env python3
"""Convierte subtítulos automáticos de YouTube (.vtt) en transcripciones limpias (.md).

Uso:  python3 -I convert.py <carpeta_raw_del_grupo> <carpeta_salida_del_grupo> <nombre_del_grupo>

- Lee <raw>/_meta.txt (id|fecha|duración|vistas|canal|título) y <raw>/<id>.<lang>.vtt
- Prefiere es-orig > en-orig > es > en
- Quita etiquetas inline, elimina duplicados del formato rodante de YouTube y agrupa en párrafos con [mm:ss]
- Escribe <salida>/<id>.md y <salida>/_indice.md
Las carpetas se pasan como argumentos: el intérprete no corre dentro de la carpeta de datos descargados.
"""
import html
import re
import sys
from pathlib import Path

TAG = re.compile(r"<[^>]+>")
TS = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3}) --> ")
PREF = ["es-orig", "en-orig", "es", "en"]


def parse_vtt(path: Path):
    cues = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = TS.match(line)
            if m:
                h, mi, s, ms = (int(x) for x in m.groups())
                cur = [h * 3600 + mi * 60 + s + ms / 1000.0, []]
                cues.append(cur)
                continue
            if cur is None:
                continue
            if line.strip() == "":
                cur = None
                continue
            txt = html.unescape(TAG.sub("", line)).strip()
            if txt:
                cur[1].append(txt)
    return cues


def dedupe(cues):
    out, recent = [], []
    for start, lines in cues:
        for t in lines:
            if t in recent:
                continue
            out.append((start, t))
            recent.append(t)
            if len(recent) > 6:
                recent.pop(0)
    return out


def paragraphs(lines, window=50):
    paras, buf, t0 = [], [], None
    for start, t in lines:
        if t0 is None:
            t0 = start
        buf.append(t)
        if start - t0 >= window and re.search(r"[.?!…]$", t):
            paras.append((t0, " ".join(buf)))
            buf, t0 = [], None
    if buf:
        paras.append((t0 if t0 is not None else 0, " ".join(buf)))
    return paras


def mmss(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_date(d):
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if d and d.isdigit() and len(d) == 8 else (d or "s/f")


def main():
    raw_dir, out_dir, group = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {}
    mf = raw_dir / "_meta.txt"
    if mf.exists():
        for l in mf.read_text(encoding="utf-8", errors="replace").splitlines():
            p = l.split("|", 5)
            if len(p) == 6:
                meta[p[0]] = p
    rows, missing = [], []
    for vid, p in meta.items():
        chosen = None
        for lang in PREF:
            f = raw_dir / f"{vid}.{lang}.vtt"
            if f.exists():
                chosen = (lang, f)
                break
        if not chosen:
            missing.append(vid)
            continue
        lang, f = chosen
        lines = dedupe(parse_vtt(f))
        paras = paragraphs(lines)
        words = sum(len(t.split()) for _, t in paras)
        _, fecha, dur, vistas, canal, titulo = p
        try:
            dur_s = int(float(dur))
        except Exception:
            dur_s = 0
        head = [
            f"# {titulo}",
            "",
            f"- Canal: {canal}",
            f"- URL: https://www.youtube.com/watch?v={vid}",
            f"- Fecha de publicación: {fmt_date(fecha)}",
            f"- Duración: {mmss(dur_s)}",
            f"- Vistas (a la captura): {vistas}",
            f"- Subtítulos: {lang} (automáticos de YouTube, sin revisar)",
            "",
            "> Transcripción automática: puede contener errores en nombres propios, cifras y herramientas. Uso interno de análisis; no republicar.",
            "",
        ]
        body = [f"[{mmss(t0)}] {txt}" for t0, txt in paras]
        (out_dir / f"{vid}.md").write_text("\n".join(head + body) + "\n", encoding="utf-8")
        rows.append((vid, fecha, dur_s, vistas, titulo, words, lang))
    rows.sort(key=lambda r: r[1], reverse=True)
    idx = [
        f"# Índice — {group}",
        "",
        f"Videos transcriptos: {len(rows)} · Sin subtítulos disponibles: {len(missing)}",
        "",
        "| id | fecha | duración | vistas | palabras | idioma | título |",
        "|---|---|---|---|---|---|---|",
    ]
    for vid, fecha, dur_s, vistas, titulo, words, lang in rows:
        idx.append(f"| {vid} | {fmt_date(fecha)} | {mmss(dur_s)} | {vistas} | {words} | {lang} | {titulo.replace('|', '/')} |")
    if missing:
        idx += ["", "Sin subtítulos: " + ", ".join(missing)]
    (out_dir / "_indice.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"{group}: {len(rows)} transcripciones, {len(missing)} sin subtítulos, {sum(r[5] for r in rows)} palabras")


if __name__ == "__main__":
    main()
