#!/usr/bin/env python3
"""probar_evals.py: corre offline los evals de D8 que el código puede verificar (dorados D01-D03).

Cada ``evals/dorados/D*.json`` trae una ``entrada`` (la que armaría ``preparar_expediente.py``), el ``modo`` y lo
``esperado`` de ``proponer.py``; se compara por inclusión (todo lo de ``esperado`` debe estar en la salida). Lo que
describe ``salida_maker_esperada`` y ``salida_qa_esperada`` es para correr ``d8-maker`` y ``d8-qa`` a mano con
``rubric.md`` (no se automatiza).

Uso (desde la raíz): ``.venv/bin/python .claude/skills/d8-optimizacion/scripts/probar_evals.py [--solo D01]``.
Sin red, sin escrituras. Salida 0 si todo pasa; 4 si algún caso falla; 3 si un archivo es inválido.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import proponer  # noqa: E402

SKILL = AQUI.parent
UMBRALES = SKILL / "evals" / "_base" / "umbrales_prueba.json"


def _contiene(obtenido, esperado, ruta="$") -> list[str]:
    """Diferencias de ``esperado`` respecto de ``obtenido`` (comparación parcial; las listas se comparan por posición)."""
    if isinstance(esperado, dict):
        if not isinstance(obtenido, dict):
            return [f"{ruta}: se esperaba un objeto"]
        return [d for k, v in esperado.items() for d in _contiene(obtenido.get(k, "<ausente>"), v, f"{ruta}.{k}")]
    if isinstance(esperado, list):
        if not isinstance(obtenido, list) or len(obtenido) != len(esperado):
            return [f"{ruta}: se esperaban {len(esperado)} elementos y hay {len(obtenido) if isinstance(obtenido, list) else '?'}"]
        return [d for i, (o, e) in enumerate(zip(obtenido, esperado)) for d in _contiene(o, e, f"{ruta}[{i}]")]
    return [] if obtenido == esperado else [f"{ruta}: esperado {esperado!r}, obtenido {obtenido!r}"]


def correr(caso: dict, umbrales: dict) -> list[str]:
    u = {**umbrales, **caso.get("umbrales_override", {})}
    if caso["modo"] == "LANZAMIENTO":
        salida = proponer.evaluar_lanzamiento(caso["entrada"], u)
    elif caso["modo"] == "FATIGA":
        salida = proponer.evaluar_fatiga(caso["entrada"], u)
    else:
        return [f"modo desconocido: {caso['modo']!r}"]
    return _contiene(salida, caso["esperado"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Corre los evals dorados de D8 que el código puede verificar.")
    ap.add_argument("--solo", default=None, help="id de un caso (p. ej. D01)")
    args = ap.parse_args(argv)
    try:
        umbrales = json.loads(UMBRALES.read_text(encoding="utf-8"))["umbrales"]
        casos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((SKILL / "evals" / "dorados").glob("D*.json"))]
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: no se pudieron leer los evals: {exc}", file=sys.stderr)
        return 3
    fallos = 0
    for caso in casos:
        if args.solo and caso.get("id") != args.solo:
            continue
        try:
            diferencias = correr(caso, umbrales)
        except proponer.ErrorProponer as exc:
            diferencias = [f"ErrorProponer: {exc}"]
        estado = "OK  " if not diferencias else "FALLA"
        print(f"{estado} {caso.get('id')}: {caso.get('descripcion', '')[:90]}")
        for d in diferencias:
            print(f"      - {d}")
        fallos += bool(diferencias)
    print(f"{'todo pasa' if not fallos else f'{fallos} caso(s) fallan'}; los casos de agente (salida_maker_esperada / salida_qa_esperada) se corren a mano con rubric.md")
    return 0 if not fallos else 4


if __name__ == "__main__":
    raise SystemExit(main())
