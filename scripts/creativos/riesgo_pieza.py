"""Riesgo POR PIEZA de D6 (``departamentos/07-creativos.md`` §6 L1.4, §10.3).

Usa la ÚNICA tabla ejes→nivel (``scripts.nivel_riesgo.riesgo_de_candidato``): este módulo NO infiere
los ejes P/C/E/N del tema de la pieza, los recibe YA asignados en el artefacto (``matriz.json`` o
``lint-x1.json`` hasta que ``contratos/creativos.schema.json`` tenga ``anuncios[].riesgo_pieza``, ver
README «Pedidos»). Compara el nivel de cada pieza contra el de la oferta (D3): deben ser IGUALES
(nota 25 §10.5, unificado por la skill D6: menor es un falso verde BLOQUEANTE, mayor es un hallazgo
MAYOR a corregir) y, si se declara, contra ``limites.nivel_max_lanzable[macro_nicho]``.

CLI::

    python -m scripts.creativos.riesgo_pieza --piezas PIEZAS.json --nivel-oferta amarillo
        [--subnivel-oferta A] [--nivel-max-lanzable amarillo-a] [--json]

``PIEZAS.json``: ``{"piezas": [{"id": "c01-hueco_img_h1_v1", "ejes": {"P":"P1","C":"C0","E":"E0","N":"N1"},
"zona_gris": false, "reencuadre": false}, ...]}``.

Salida (convenciones §8): 0 todas coherentes (como mucho hallazgos MAYOR) · 3 alguna pieza es ROJA,
es un falso verde BLOQUEANTE, o excede ``nivel_max_lanzable`` · 2 uso.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion

from scripts.nivel_riesgo import riesgo_de_candidato

__all__ = ["ORDEN_NIVEL", "clasificar_pieza", "evaluar_piezas", "main", "nivel_lanzable_de"]

ORDEN_NIVEL: dict[str, int] = {"verde": 0, "amarillo": 1, "rojo": 2}
_ORDEN_LANZABLE: dict[str, int] = {"verde": 0, "amarillo-a": 1, "amarillo-b": 2}


def nivel_lanzable_de(nivel: str | None, subnivel: str | None) -> str | None:
    """Traduce ``(nivel, subnivel)`` de :func:`scripts.nivel_riesgo.calcular` al enum ``nivel_lanzable``.

    ``comunes.schema.json#/$defs/nivel_lanzable`` (verde, amarillo-a, amarillo-b) no incluye rojo (nunca
    se lanza) ni ``None`` (fuera de macro-nicho): en esos casos devuelve ``None`` (no comparable).
    """
    if nivel == "verde":
        return "verde"
    if nivel == "amarillo" and subnivel in ("A", "B"):
        return f"amarillo-{subnivel.lower()}"
    return None


def clasificar_pieza(nivel_pieza: str | None, nivel_oferta: str) -> str:
    """``coherente`` (igual) · ``falso_verde_bloqueante`` (pieza por debajo del nivel de la oferta) ·
    ``mayor_revisar`` (pieza por encima: se reescribe, nota 25) · ``indeterminado`` (pieza fuera de macro)."""
    if nivel_pieza is None:
        return "indeterminado"
    if nivel_pieza not in ORDEN_NIVEL or nivel_oferta not in ORDEN_NIVEL:
        raise ErrorValidacion(f"nivel desconocido: pieza={nivel_pieza!r} oferta={nivel_oferta!r}")
    if ORDEN_NIVEL[nivel_pieza] < ORDEN_NIVEL[nivel_oferta]:
        return "falso_verde_bloqueante"
    if ORDEN_NIVEL[nivel_pieza] > ORDEN_NIVEL[nivel_oferta]:
        return "mayor_revisar"
    return "coherente"


def evaluar_piezas(piezas: Sequence[Mapping[str, Any]], *, nivel_oferta: str, nivel_max_lanzable: str | None = None) -> dict[str, Any]:
    """Riesgo de cada pieza y su clasificación frente a la oferta y (si se declara) a ``nivel_max_lanzable``."""
    if not piezas:
        raise ErrorValidacion("no hay piezas que evaluar")
    filas: list[dict[str, Any]] = []
    bloqueantes: list[str] = []
    for pieza in piezas:
        pid = pieza.get("id") if isinstance(pieza, Mapping) else None
        if not isinstance(pid, str) or not pid.strip():
            raise ErrorValidacion("cada pieza necesita «id» (texto no vacío)")
        ejes = pieza.get("ejes")
        if not isinstance(ejes, Mapping):
            raise ErrorValidacion(f"{pid}: falta «ejes» (P, C, E, N)")
        r = riesgo_de_candidato(ejes, zona_gris=bool(pieza.get("zona_gris")), hay_reencuadre=bool(pieza.get("reencuadre")))
        clasificacion = clasificar_pieza(r["nivel"], nivel_oferta)
        lanzable = nivel_lanzable_de(r["nivel"], r["subnivel"])
        excede_tope = (
            nivel_max_lanzable is not None and lanzable is not None
            and _ORDEN_LANZABLE.get(lanzable, 99) > _ORDEN_LANZABLE.get(nivel_max_lanzable, -1)
        )
        bloquea = r["nivel"] == "rojo" or clasificacion == "falso_verde_bloqueante" or excede_tope
        if bloquea:
            motivo = "rojo" if r["nivel"] == "rojo" else ("falso verde" if clasificacion == "falso_verde_bloqueante" else "excede nivel_max_lanzable")
            bloqueantes.append(f"{pid}: {motivo}")
        filas.append({
            "id": pid, "nivel": r["nivel"], "subnivel": r["subnivel"], "nivel_lanzable": lanzable,
            "veredicto_riesgo": r["veredicto_riesgo"], "clasificacion": clasificacion, "excede_nivel_max_lanzable": excede_tope,
            "bloquea": bloquea,
        })
    return {"piezas": filas, "nivel_oferta": nivel_oferta, "nivel_max_lanzable": nivel_max_lanzable, "bloqueantes": bloqueantes}


def _cargar_piezas(ruta: Path) -> list[dict[str, Any]]:
    try:
        datos = comun.cargar_json(ruta)
    except FileNotFoundError as exc:
        raise ErrorUso(f"--piezas no existe: {ruta}") from exc
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"--piezas ilegible: {exc}") from exc
    if not isinstance(datos, Mapping) or not isinstance(datos.get("piezas"), list):
        raise ErrorValidacion("el archivo debe ser {«piezas»: [...]}")
    return list(datos["piezas"])


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.creativos.riesgo_pieza", description="Riesgo por pieza (D6) con la tabla única de nivel_riesgo.")
    p.add_argument("--piezas", required=True, type=Path)
    p.add_argument("--nivel-oferta", required=True, choices=sorted(ORDEN_NIVEL), dest="nivel_oferta")
    p.add_argument("--nivel-max-lanzable", default=None, choices=sorted(_ORDEN_LANZABLE), dest="nivel_max_lanzable")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        piezas = _cargar_piezas(a.piezas)
        resultado = evaluar_piezas(piezas, nivel_oferta=a.nivel_oferta, nivel_max_lanzable=a.nivel_max_lanzable)
        codigo = 3 if resultado["bloqueantes"] else 0
        salida = {"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": resultado, "avisos": resultado["bloqueantes"]}
        if a.json:
            print(json.dumps(salida, sort_keys=True, ensure_ascii=False))
        else:
            for fila in resultado["piezas"]:
                print(f"{fila['id']}: nivel={fila['nivel']} ({fila['clasificacion']}) bloquea={fila['bloquea']}")
            if resultado["bloqueantes"]:
                print("BLOQUEANTES: " + "; ".join(resultado["bloqueantes"]))
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    raise SystemExit(main())
