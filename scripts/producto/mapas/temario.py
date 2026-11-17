"""Temario de Słowomapa: 520 títulos de mapa repartidos 70/80/90/100/90/90 (A1→C2).

La fuente de verdad editable es ``temario_fuente.txt`` (una línea por mapa, bloques con ``@``). Este módulo la parsea, la
valida y genera ``ofertas/OF-202611-91/04-producto/temario.json`` (con ``mapa_id`` y ``siguiente`` calculados por código).

Formato de ``temario_fuente.txt``::

    # comentario
    @ A1 | a1-arranque | descripción corta del bloque
    Food | Jedzenie
    Family | Rodzina

El orden de las líneas es la ruta de estudio dentro de cada nivel; el último mapa de un nivel sigue con el primero del
siguiente. La asignación de nivel es criterio de diseño ``[HIPÓTESIS]``: no se contrastó con ninguna lista CEFR oficial
(no hay lista offline en el repositorio ni se usa red).

CLI::

    .venv/bin/python -m scripts.producto.mapas.temario generar [--fuente F] [--salida temario.json]
    .venv/bin/python -m scripts.producto.mapas.temario validar temario.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Mapping

from scripts.producto.mapas.esquema import NIVELES, REPARTO, TOTAL_MAPAS, hallazgo

OFERTA_ID = "OF-202611-91"
FUENTE_DEFECTO = Path(__file__).with_name("temario_fuente.txt")
SALIDA_DEFECTO = Path("ofertas") / OFERTA_ID / "04-producto" / "temario.json"
_RX_EN = re.compile(r"^[A-Z][A-Za-z,'\- ]*[A-Za-z']$")
_RX_PL = re.compile(r"^[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ,'\- ]*[A-Za-ząćęłńóśźż]$")
_RX_BLOQUE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slug(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    s = s.replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def parsear(texto: str) -> list[dict[str, Any]]:
    """Líneas del fuente -> lista de entradas ``{nivel, bloque, tema_en, tema_pl}`` y de bloques."""
    entradas: list[dict[str, Any]] = []
    bloque: dict[str, str] | None = None
    for n, linea in enumerate(texto.splitlines(), 1):
        t = linea.strip()
        if not t or t.startswith("#"):
            continue
        if t.startswith("@"):
            partes = [p.strip() for p in t[1:].split("|")]
            if len(partes) != 3 or partes[0] not in NIVELES or not _RX_BLOQUE.match(partes[1]):
                raise ValueError(f"línea {n}: bloque mal formado: {linea!r}")
            bloque = {"nivel": partes[0], "id": partes[1], "descripcion": partes[2]}
            continue
        partes = [p.strip() for p in t.split("|")]
        if len(partes) != 2 or not all(partes):
            raise ValueError(f"línea {n}: se esperaba «tema_en | tema_pl»: {linea!r}")
        if bloque is None:
            raise ValueError(f"línea {n}: mapa antes de abrir un bloque")
        entradas.append({"nivel": bloque["nivel"], "bloque": bloque["id"], "bloque_desc": bloque["descripcion"], "tema_en": partes[0], "tema_pl": partes[1]})
    return entradas


def construir(entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Asigna ``numero``, ``mapa_id`` y ``siguiente``; agrupa bloques. El orden de niveles debe ser A1..C2 sin mezclar."""
    mapas: list[dict[str, Any]] = []
    contador = {n: 0 for n in NIVELES}
    ultimo_nivel = -1
    for e in entradas:
        ni = NIVELES.index(e["nivel"])
        if ni < ultimo_nivel:
            raise ValueError(f"los niveles deben ir en orden A1..C2: {e['nivel']} aparece después de {NIVELES[ultimo_nivel]}")
        ultimo_nivel = ni
        contador[e["nivel"]] += 1
        num = contador[e["nivel"]]
        mapas.append({
            "mapa_id": f"{e['nivel'].lower()}-{num:03d}-{slug(e['tema_en'])}",
            "nivel": e["nivel"], "numero": num, "bloque": e["bloque"],
            "tema": {"en": e["tema_en"], "pl": e["tema_pl"]}, "siguiente": None,
        })
    for i, m in enumerate(mapas[:-1]):
        m["siguiente"] = mapas[i + 1]["mapa_id"]
    niveles: dict[str, Any] = {}
    for nv in NIVELES:
        ms = [m for m in mapas if m["nivel"] == nv]
        bloques: list[dict[str, Any]] = []
        for m in ms:
            if not bloques or bloques[-1]["id"] != m["bloque"]:
                desc = next(e["bloque_desc"] for e in entradas if e["bloque"] == m["bloque"])
                bloques.append({"id": m["bloque"], "descripcion": desc, "desde": m["numero"], "hasta": m["numero"], "n": 0})
            bloques[-1]["hasta"] = m["numero"]
            bloques[-1]["n"] += 1
        niveles[nv] = {"n": len(ms), "bloques": bloques}
    return {
        "schema_version": "1.0.0",
        "oferta_id": OFERTA_ID,
        "producto": "Słowomapa",
        "total": len(mapas),
        "reparto": {nv: niveles[nv]["n"] for nv in NIVELES},
        "estado": "propuesta de D4 en modo práctica [HIPÓTESIS]: el nivel de cada tema es criterio de diseño; no se contrastó con una lista CEFR oficial",
        "niveles": niveles,
        "mapas": mapas,
    }


def validar_temario(tem: Mapping[str, Any]) -> list[dict[str, str]]:
    hs: list[dict[str, str]] = []
    mapas = tem.get("mapas")
    if not isinstance(mapas, list):
        return [hallazgo("temario-estructura", "BLOQUEANTE", "mapas", "debe ser una lista")]
    if len(mapas) != TOTAL_MAPAS:
        hs.append(hallazgo("temario-total", "BLOQUEANTE", "mapas", f"{len(mapas)} mapas; deben ser {TOTAL_MAPAS}"))
    for nv in NIVELES:
        n = sum(1 for m in mapas if m.get("nivel") == nv)
        if n != REPARTO[nv]:
            hs.append(hallazgo("temario-reparto", "BLOQUEANTE", nv, f"{n} mapas; deben ser {REPARTO[nv]}"))
    ids: set[str] = set()
    en: dict[str, str] = {}
    pl: dict[str, str] = {}
    bloques: dict[str, str] = {}
    for i, m in enumerate(mapas):
        c = f"mapas[{i}]"
        mid = m.get("mapa_id", "")
        if mid in ids:
            hs.append(hallazgo("temario-id-repetido", "BLOQUEANTE", c, f"id repetido: {mid}"))
        ids.add(mid)
        t = m.get("tema", {})
        te, tp = str(t.get("en", "")), str(t.get("pl", ""))
        if not _RX_EN.match(te) or len(te.split()) > 5:
            hs.append(hallazgo("temario-titulo-en", "MAYOR", c, f"título EN inválido (ASCII, ≤ 5 palabras): {te!r}"))
        if not _RX_PL.match(tp) or len(tp.split()) > 6:
            hs.append(hallazgo("temario-titulo-pl", "MAYOR", c, f"título PL inválido (≤ 6 palabras): {tp!r}"))
        for k, d, etiqueta in ((te.casefold(), en, "EN"), (tp.casefold(), pl, "PL")):
            if k in d:
                hs.append(hallazgo("temario-titulo-repetido", "BLOQUEANTE", c, f"título {etiqueta} repetido: {k!r} (también en {d[k]})"))
            d[k] = mid
        if m.get("bloque") in bloques and bloques[m["bloque"]] != m.get("nivel"):
            hs.append(hallazgo("temario-bloque-mezcla-niveles", "BLOQUEANTE", c, f"el bloque {m['bloque']} aparece en dos niveles"))
        bloques[m.get("bloque", "")] = m.get("nivel", "")
    # ruta: cada «siguiente» es el mapa siguiente de la lista
    for i, m in enumerate(mapas):
        esperado = mapas[i + 1]["mapa_id"] if i + 1 < len(mapas) else None
        if m.get("siguiente") != esperado:
            hs.append(hallazgo("temario-ruta", "BLOQUEANTE", f"mapas[{i}]", f"«siguiente» debería ser {esperado!r}"))
    return hs


def cargar(ruta: Path | str) -> dict[str, Any]:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def _principal(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.mapas.temario")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generar")
    g.add_argument("--fuente", default=str(FUENTE_DEFECTO))
    g.add_argument("--salida", default=str(SALIDA_DEFECTO))
    g.add_argument("--sobrescribir", action="store_true")
    v = sub.add_parser("validar")
    v.add_argument("temario")
    a = ap.parse_args(argv)
    if a.cmd == "generar":
        tem = construir(parsear(Path(a.fuente).read_text(encoding="utf-8")))
        hs = validar_temario(tem)
        for h in hs:
            print(f"[{h['severidad']}] {h['codigo']} · {h['campo']}: {h['mensaje']}", file=sys.stderr)
        if any(h["severidad"] in ("BLOQUEANTE", "MAYOR") for h in hs):
            return 1
        salida = Path(a.salida)
        if salida.exists() and not a.sobrescribir:
            print(f"{salida} ya existe (usa --sobrescribir)", file=sys.stderr)
            return 2
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(tem, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"OK {salida} · {tem['total']} mapas · {tem['reparto']}")
        return 0
    hs = validar_temario(cargar(a.temario))
    for h in hs:
        print(f"[{h['severidad']}] {h['codigo']} · {h['campo']}: {h['mensaje']}")
    print("OK" if not hs else f"{len(hs)} hallazgos")
    return 1 if any(h["severidad"] in ("BLOQUEANTE", "MAYOR") for h in hs) else 0


def main(argv: list[str] | None = None) -> int:
    return _principal(argv)


if __name__ == "__main__":
    sys.exit(main())
