#!/usr/bin/env python3
"""Adaptador interno de ``scripts/nivel_riesgo.py``: ejes P, C, E, N → nivel de riesgo (nota 25 §2.3).

La ÚNICA implementación de la tabla es ``scripts/nivel_riesgo.py`` (``python -m scripts.nivel_riesgo``, la forma
que citan SKILL.md y los agentes; promovida por S-B el 2026-11-06 desde el sustituto que vivía aquí; 230 casos
de la suite sin discrepancias). Este archivo NO calcula nada ni es una segunda tabla: delega en ella y conserva
solo la interfaz local de la skill (errores ``ValueError`` y códigos de salida 0/1/2 que usan
``validar_dictamen.py``, ``correr_evals.py`` y las pruebas). Nadie debe citarlo en un dictamen. El LLM NO calcula
el nivel: lo calcula el código.

Uso:
  python3 nivel_ejes.py --P P2n --C C1 --E E0 --N N1 [--zona-gris] [--reencuadre] [--json]
  python3 nivel_ejes.py --suite RUTA/casos-frontera.yaml      # prueba la aritmética contra la suite (0 = sin discrepancias)

Equivale a ``python -m scripts.nivel_riesgo`` (con salida 3 ante discrepancias, convenciones §8).
Sin red, sin escritura, sin secretos. Salida 0 = ok; 1 = discrepancias en --suite; 2 = uso.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# La raíz del repositorio (…/.claude/skills/x1-compliance/scripts/nivel_ejes.py → parents[4]) para importar el módulo canónico.
RAIZ = Path(__file__).resolve().parents[4]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from engine.errores import ErrorFabrica  # noqa: E402
from scripts import nivel_riesgo as _canonico  # noqa: E402

ESCALA = _canonico.ESCALA
COLOR = _canonico.COLOR
ORDEN = _canonico.ORDEN


def calcular(ejes: dict[str, str], *, fuera_de_macro: bool = False, zona_gris: bool = False,
             hay_reencuadre: bool = False) -> dict:
    """Devuelve ``{nivel, subnivel, colores, veredicto_riesgo}``. Falla con ValueError ante un código inválido."""
    try:
        return _canonico.calcular(ejes, fuera_de_macro=fuera_de_macro, zona_gris=zona_gris, hay_reencuadre=hay_reencuadre)
    except ErrorFabrica as exc:
        raise ValueError(getattr(exc, "mensaje", None) or str(exc)) from exc


def verificar_suite(ruta: Path) -> list[str]:
    """Compara nivel, subnivel y veredicto con los de cada caso de la suite. Devuelve las discrepancias."""
    try:
        return _canonico.verificar_suite(Path(ruta))
    except ErrorFabrica as exc:
        raise ValueError(getattr(exc, "mensaje", None) or str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for eje in "PCEN":
        p.add_argument(f"--{eje}", choices=ESCALA[eje])
    p.add_argument("--zona-gris", action="store_true", help="zona gris cerrada por el dueño (amarillo-a pasa a pasa_con_gate)")
    p.add_argument("--reencuadre", action="store_true", help="existe un reencuadre que conserva el deseo y baja a <= amarillo")
    p.add_argument("--fuera-de-macro", action="store_true")
    p.add_argument("--suite", type=Path, help="casos-frontera.yaml: verifica la aritmética de toda la suite")
    p.add_argument("--json", action="store_true")
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if a.suite:
        try:
            errores = verificar_suite(a.suite)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("\n".join(errores) if errores else "suite: 0 discrepancias")
        return 1 if errores else 0
    if not all((a.P, a.C, a.E, a.N)):
        print("faltan ejes: --P --C --E --N (o --suite)", file=sys.stderr)
        return 2
    try:
        r = calcular({"P": a.P, "C": a.C, "E": a.E, "N": a.N}, fuera_de_macro=a.fuera_de_macro,
                     zona_gris=a.zona_gris, hay_reencuadre=a.reencuadre)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False) if a.json else f"nivel={r['nivel']} subnivel={r['subnivel']} veredicto={r['veredicto_riesgo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
