#!/usr/bin/env python3
"""probar_evals.py: corre offline los evals dorados de D9 contra ``escala_lectura.dictamen`` (código real, sin red ni escrituras).

Cada ``evals/dorados/D*.json`` trae una ``entrada`` completa y un ``esperado``; los límites y parámetros de prueba salen de
``evals/_base/`` (fixtures ``[SUPUESTO]``, no son los archivos del dueño) y el caso puede sobrescribirlos con ``limites_override`` /
``parametros_override``. Este runner NO prueba al agente ni al QA (eso es trabajo de ``d9-qa`` con ``rubric.md``): prueba que el
código que les da los números responde lo que la skill promete.

Uso (desde la raíz): ``.venv/bin/python .claude/skills/d9-escalado/scripts/probar_evals.py [--solo D01]``. Salida 0 si todo pasa, 4 si algo falla.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
BASE = SKILL / "evals" / "_base"


def _cargar_escala():
    spec = importlib.util.spec_from_file_location("d9_escala_lectura", AQUI / "escala_lectura.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # dataclasses y typing lo necesitan registrado
    spec.loader.exec_module(modulo)
    return modulo


def armar_entrada(caso: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """``(entrada, limites, parametros_planos)`` de un caso: base de prueba + sobrescrituras del caso."""
    lim = json.loads((BASE / "limites_prueba.json").read_text(encoding="utf-8"))
    par = json.loads((BASE / "parametros_prueba.json").read_text(encoding="utf-8"))
    lim.update(caso.get("limites_override", {}))
    par.update(caso.get("parametros_override", {}))
    lim.pop("_comentario", None)
    par.pop("_comentario", None)
    return copy.deepcopy(caso["entrada"]), lim, par


def comparar(caso: dict[str, Any], resultado: dict[str, Any]) -> list[str]:
    """Lista de diferencias entre ``esperado`` y el dictamen (vacía = pasa)."""
    esp = caso["esperado"]
    fallas: list[str] = []
    for clave in ("estado", "codigo", "accion"):
        if clave in esp and resultado.get(clave) != esp[clave]:
            fallas.append(f"{clave}: esperado {esp[clave]!r}, salió {resultado.get(clave)!r}")
    if "ganador_nivel" in esp and resultado.get("ganador", {}).get("nivel") != esp["ganador_nivel"]:
        fallas.append(f"ganador.nivel: esperado {esp['ganador_nivel']!r}, salió {resultado.get('ganador', {}).get('nivel')!r}")
    orden = resultado.get("orden_borrador")
    if "orden_borrador" in esp and esp["orden_borrador"] is None and orden is not None:
        fallas.append("se esperaba que NO hubiera orden_borrador")
    if "paso_nuevo_minor" in esp and (resultado.get("paso") or {}).get("nuevo_minor") != esp["paso_nuevo_minor"]:
        fallas.append(f"paso.nuevo_minor: esperado {esp['paso_nuevo_minor']}, salió {(resultado.get('paso') or {}).get('nuevo_minor')}")
    if "orden_estado" in esp and (orden or {}).get("estado") != esp["orden_estado"]:
        fallas.append(f"orden.estado: esperado {esp['orden_estado']!r}")
    if "gate" in esp and (orden or {}).get("gate", {}).get("gate") != esp["gate"]:
        fallas.append(f"orden.gate.gate: esperado {esp['gate']!r}")
    return fallas


def correr(solo: str | None = None) -> list[tuple[str, list[str], dict[str, Any]]]:
    escala = _cargar_escala()
    salida = []
    for ruta in sorted((SKILL / "evals" / "dorados").glob("D*.json")):
        caso = json.loads(ruta.read_text(encoding="utf-8"))
        if solo and caso["id"] != solo:
            continue
        entrada, lim, par = armar_entrada(caso)
        resultado, _codigo = escala.dictamen(entrada, lim, par)
        salida.append((caso["id"], comparar(caso, resultado), resultado))
    return salida


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evals dorados de D9 contra el código de apoyo.")
    ap.add_argument("--solo", help="id de un caso, p. ej. D01")
    args = ap.parse_args(argv)
    resultados = correr(args.solo)
    if not resultados:
        print("ningún caso corrido", file=sys.stderr)
        return 2
    mal = 0
    for caso_id, fallas, res in resultados:
        estado = "OK  " if not fallas else "FALLA"
        print(f"{estado} {caso_id}: {res.get('estado')} / {res.get('codigo')}")
        for f in fallas:
            print(f"      - {f}")
        mal += bool(fallas)
    return 4 if mal else 0


if __name__ == "__main__":
    sys.exit(main())
