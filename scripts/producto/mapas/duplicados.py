"""Inventario de palabras y duplicados entre mapas (regla: ninguna palabra se repite DENTRO de un nivel).

El inventario cuenta como vocabulario de un mapa su palabra central y las palabras de sus ramas. La comparación normaliza mayúsculas y
quita la «s» final (emission/emissions), de modo que una variante de número también cuenta como repetición. Entre niveles una palabra
repetida es informativa (MENOR): puede ser legítima (otro sentido) pero hay que mirarla.

CLI::

    .venv/bin/python -m scripts.producto.mapas.duplicados CARPETA_DE_MAPAS [--inventario salida.json] [--nivel B1]
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.producto.mapas.esquema import NIVELES, cargar_dir, hallazgo


def clave(palabra: str) -> str:
    p = unicodedata.normalize("NFC", palabra).strip().casefold()
    if p.endswith("ies") and len(p) > 4:
        return p[:-3] + "y"
    if len(p) > 3 and p.endswith("s") and not p.endswith(("ss", "us", "is")):
        return p[:-1]
    return p


def vocabulario(mapa: Mapping[str, Any]) -> list[tuple[str, str]]:
    """``[(palabra, rol)]`` de un mapa: el centro y las palabras de sus ramas."""
    out: list[tuple[str, str]] = []
    c = mapa.get("centro")
    if isinstance(c, dict) and isinstance(c.get("en"), str):
        out.append((c["en"], "centro"))
    for r in mapa.get("ramas", []):
        for p in r.get("palabras", []):
            if isinstance(p, dict) and isinstance(p.get("en"), str):
                out.append((p["en"], "palabra"))
    return out


def inventario(mapas: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, list[dict[str, str]]]]:
    """``{nivel: {clave: [{mapa_id, palabra, rol}]}}``."""
    inv: dict[str, dict[str, list[dict[str, str]]]] = {n: defaultdict(list) for n in NIVELES}
    for m in mapas:
        nv = m.get("nivel")
        if nv not in inv:
            continue
        for palabra, rol in vocabulario(m):
            inv[nv][clave(palabra)].append({"mapa_id": m.get("mapa_id", "?"), "palabra": palabra, "rol": rol})
    return {n: dict(d) for n, d in inv.items()}


def duplicados_en_nivel(mapas: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """BLOQUEANTE: la misma palabra (o su variante de número) en dos mapas del mismo nivel."""
    hs: list[dict[str, str]] = []
    for nv, d in inventario(mapas).items():
        for k, usos in sorted(d.items()):
            ids = sorted({u["mapa_id"] for u in usos})
            if len(ids) > 1:
                hs.append(hallazgo("duplicado-en-nivel", "BLOQUEANTE", ",".join(ids), f"nivel {nv}: «{usos[0]['palabra']}» aparece en {len(ids)} mapas ({', '.join(ids)})"))
    return hs


def duplicados_entre_niveles(mapas: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """MENOR (informativo): la misma palabra en niveles distintos."""
    mapas = list(mapas)
    vistos: dict[str, dict[str, str]] = defaultdict(dict)  # clave -> {nivel: mapa_id}
    for nv, d in inventario(mapas).items():
        for k, usos in d.items():
            vistos[k][nv] = usos[0]["mapa_id"]
    hs = []
    for k, por_nivel in sorted(vistos.items()):
        if len(por_nivel) > 1:
            hs.append(hallazgo("palabra-en-varios-niveles", "MENOR", ",".join(por_nivel.values()), f"«{k}» está en los niveles {', '.join(sorted(por_nivel))}: confirma que son sentidos distintos"))
    return hs


def frases_repetidas(mapas: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """MAYOR: la misma frase inglesa en dos mapas distintos."""
    vistas: dict[str, list[str]] = defaultdict(list)
    for m in mapas:
        for f in m.get("frases", []):
            if isinstance(f, dict) and isinstance(f.get("en"), str):
                vistas[unicodedata.normalize("NFC", f["en"]).strip().casefold()].append(m.get("mapa_id", "?"))
    return [hallazgo("frase-repetida-entre-mapas", "MAYOR", ",".join(ids), f"la frase «{k}» está en varios mapas") for k, ids in vistas.items() if len(set(ids)) > 1]


def ya_usadas(mapas: Iterable[Mapping[str, Any]], nivel: str) -> list[str]:
    """Lista ordenada de palabras ya usadas en un nivel (se pasa al escritor del siguiente lote)."""
    d = inventario(mapas).get(nivel, {})
    return sorted({u["palabra"].casefold() for usos in d.values() for u in usos})


def informe(mapas: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    mapas = list(mapas)
    return duplicados_en_nivel(mapas) + frases_repetidas(mapas) + duplicados_entre_niveles(mapas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.mapas.duplicados")
    ap.add_argument("mapas")
    ap.add_argument("--inventario")
    ap.add_argument("--nivel")
    a = ap.parse_args(argv)
    mapas = [m for _, m in cargar_dir(a.mapas)]
    hs = informe(mapas)
    for h in hs:
        print(f"[{h['severidad']}] {h['codigo']} · {h['campo']}: {h['mensaje']}")
    if a.inventario:
        inv = {n: ya_usadas(mapas, n) for n in NIVELES if not a.nivel or n == a.nivel}
        Path(a.inventario).write_text(json.dumps(inv, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(mapas)} mapas · {sum(1 for h in hs if h['severidad'] == 'BLOQUEANTE')} bloqueantes · {len(hs)} hallazgos")
    return 1 if any(h["severidad"] in ("BLOQUEANTE", "MAYOR") for h in hs) else 0


if __name__ == "__main__":
    sys.exit(main())
