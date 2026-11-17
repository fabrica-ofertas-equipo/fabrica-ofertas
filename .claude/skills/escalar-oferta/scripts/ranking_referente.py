#!/usr/bin/env python3
"""Ranking de los anuncios del referente para la renovación (R9 desde el 15-nov: 100 % creativos nuevos).

Regla del dueño (15-nov): «haremos 100 % renovaciones nuevas, basándonos primero en los mejores anuncios de la referencia para
modelarlos y mejorarlos, siempre y cuando sea posible… y si no, después, creando conceptos totalmente nuevos, enfocándonos en los
ángulos y problemas que planteamos en la landing».

Qué es «mejor» acá (lo que la Biblioteca deja ver del referente, que ya pagó por saberlo):
  - copias: cuántas veces aparece el mismo concepto (mismo texto o mismo video, en otros países o anuncios) más lo que dice `usan`
    (anuncios que usan esa pieza): el referente duplica lo que vende;
  - días activo: el anuncio más viejo del concepto que sigue activo (lo que no vende se apaga);
  - itera: tiene una variante nueva en los últimos 7 días (lo sigue empujando hoy).
Puntaje = días del más viejo × (1 + log2(copias)) × (1,25 si itera). Se agrupa por concepto (primeras 120 letras del texto o el video).

Entrada: uno o más inventarios de la Biblioteca (`modelado/referente/biblioteca-<fecha>.json`, lista de {id, desde, usan, video,
img, texto}) y los archivos con lo ya usado (cualquier texto: se toman los números de 13+ cifras; por defecto
`06-creativos/referente-usados.json` y todos los `06-creativos/revision-r*/referente.md` de la oferta).
Salida: conceptos sin usar, ordenados; con `--json`, la lista completa.

Uso: python3 ranking_referente.py --carpeta ofertas/_borrador-<slug> [--biblioteca <json> ...] [--usados <archivo> ...] [--hoy AAAA-MM-DD] [--json]
     python3 ranking_referente.py --probar
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

MESES = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "aug": 8,
         "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}
RX_ID = re.compile(r"\b\d{13,}\b")


def fecha(texto) -> dt.date | None:
    if not texto:
        return None
    s = str(texto).strip().lower()
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        pass
    m = re.match(r"(\d{1,2})\s+([a-zé]{3})[a-zé]*\.?\s+(\d{4})", s)
    if m and m.group(2)[:3] in MESES:
        return dt.date(int(m.group(3)), MESES[m.group(2)[:3]], int(m.group(1)))
    return None


def clave_concepto(a: dict) -> str:
    if a.get("video"):
        v = str(a["video"]).split("?")[0]
        return "video:" + v.rsplit("/", 1)[-1]
    t = re.sub(r"\s+", " ", str(a.get("texto") or "")).strip().lower()[:120]
    return "texto:" + t if t else "id:" + str(a.get("id"))


def ranking(anuncios: list[dict], usados: set[str], hoy: dt.date) -> list[dict]:
    grupos: dict[str, list[dict]] = {}
    for a in anuncios:
        if isinstance(a, dict) and a.get("id"):
            grupos.setdefault(clave_concepto(a), []).append(a)
    out = []
    for clave, xs in grupos.items():
        fechas = [d for d in (fecha(x.get("desde")) for x in xs) if d]
        viejo = min(fechas) if fechas else None
        nuevo = max(fechas) if fechas else None
        dias = (hoy - viejo).days if viejo else 0
        copias = max(len(xs), sum(int(x.get("usan") or 1) for x in xs))
        itera = bool(nuevo and (hoy - nuevo).days <= 7 and len(xs) > 1)
        puntaje = dias * (1 + math.log2(max(1, copias))) * (1.25 if itera else 1.0)
        ids = sorted({str(x["id"]) for x in xs})
        texto = str(xs[0].get("texto") or "").strip()
        out.append({
            "concepto": clave, "ids": ids, "formato": "video" if any(x.get("video") for x in xs) else "imagen",
            "desde": viejo.isoformat() if viejo else None, "ultima_variante": nuevo.isoformat() if nuevo else None,
            "dias_activo": dias, "copias": copias, "itera": itera, "puntaje": round(puntaje, 1),
            "usado": any(i in usados for i in ids), "gancho": texto.split("\n", 1)[0][:160],
        })
    return sorted(out, key=lambda c: (c["usado"], -c["puntaje"]))


def leer_usados(rutas: list[Path]) -> set[str]:
    ids: set[str] = set()
    for r in rutas:
        try:
            ids |= set(RX_ID.findall(r.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return ids


def probar() -> int:
    hoy = dt.date(2026, 11, 15)
    ads = [
        {"id": "1000000000001", "desde": "22 jun 2026", "usan": 1, "texto": "Mi abogado me va a reñir"},
        {"id": "1000000000002", "desde": "19 jul 2026", "usan": 1, "texto": "Screenshot this before you scroll"},
        {"id": "1000000000003", "desde": "31 jul 2026", "usan": 2, "texto": "Screenshot this before you scroll"},
        {"id": "1000000000004", "desde": "12 nov 2026", "usan": 1, "texto": "Screenshot this before you scroll"},
        {"id": "1000000000005", "desde": "30 oct 2026", "usan": 1, "video": "https://x/v/abc.mp4?x=1", "texto": "a"},
        {"id": "1000000000006", "desde": "1 nov 2026", "usan": 1, "video": "https://x/v/abc.mp4?y=2", "texto": "b"},
    ]
    r = ranking(ads, {"1000000000001"}, hoy)
    assert r[0]["gancho"].startswith("Screenshot") and r[0]["copias"] == 4 and r[0]["itera"], r[0]
    assert r[-1]["usado"] and r[-1]["ids"] == ["1000000000001"], r[-1]
    vid = next(c for c in r if c["formato"] == "video")
    assert vid["ids"] == ["1000000000005", "1000000000006"] and vid["desde"] == "2026-10-30"
    assert fecha("2026-11-01") == dt.date(2026, 11, 1) and fecha("3 ago 2026") == dt.date(2026, 8, 3)
    print("ok: 4 comprobaciones")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--carpeta")
    ap.add_argument("--biblioteca", action="append")
    ap.add_argument("--usados", action="append")
    ap.add_argument("--hoy")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--probar", action="store_true")
    a = ap.parse_args(argv)
    if a.probar:
        return probar()
    if not a.carpeta and not a.biblioteca:
        ap.error("falta --carpeta o --biblioteca")
    base = Path(a.carpeta) if a.carpeta else None
    bibs = [Path(b) for b in a.biblioteca] if a.biblioteca else sorted((base / "modelado/referente").glob("biblioteca-*.json"))
    if not bibs:
        print("No hay inventario de la Biblioteca: bajarlo antes (ads_library_search de las páginas del referente) a "
              "modelado/referente/biblioteca-<fecha>.json", file=sys.stderr)
        return 2
    anuncios: dict[str, dict] = {}
    for b in bibs:   # el inventario más nuevo pisa al viejo
        for x in json.loads(b.read_text(encoding="utf-8")):
            if isinstance(x, dict) and x.get("id"):
                anuncios[str(x["id"])] = x
    rutas = [Path(u) for u in a.usados] if a.usados else []
    if base:
        rutas += [base / "06-creativos/referente-usados.json"] + sorted((base / "06-creativos").glob("revision-r*/referente.md"))
    hoy = dt.date.fromisoformat(a.hoy) if a.hoy else dt.date.today()
    r = ranking(list(anuncios.values()), leer_usados(rutas), hoy)
    if a.json:
        print(json.dumps({"hoy": hoy.isoformat(), "inventarios": [str(b) for b in bibs], "conceptos": r,
                          "sin_usar": sum(1 for c in r if not c["usado"])}, ensure_ascii=False, indent=1))
        return 0
    libres = [c for c in r if not c["usado"]]
    print(f"{len(libres)} conceptos del referente sin usar (de {len(r)}), del mejor al peor:")
    for i, c in enumerate(libres, 1):
        print(f"{i:2}. {c['puntaje']:7} · {c['formato']:6} · {c['dias_activo']:3} días · {c['copias']} copias{' · ITERA' if c['itera'] else ''} · "
              f"{c['ids'][0]} · {c['gancho'][:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
