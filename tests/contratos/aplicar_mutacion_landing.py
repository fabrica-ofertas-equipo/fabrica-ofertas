"""Aplica las mutaciones sembrables de B0-11 (``tests/fixtures/contratos/mutaciones_landing/catalogo.json``) a una COPIA temporal de
``ofertas/_ejemplo`` (ola 0b-2, CT). Nunca opera sobre el ejemplo real.

Uso desde pruebas::

    from tests.contratos.aplicar_mutacion_landing import copiar_ejemplo, aplicar
    copia = copiar_ejemplo(carpeta_temporal)          # copia ofertas/_ejemplo y deja la marca de copia temporal
    aplicar("ML-04", copia)                           # parche determinista; devuelve los archivos tocados

Garantías: ``aplicar`` exige la marca ``.copia-temporal-mutaciones`` (solo la crea ``copiar_ejemplo``) y se niega si el destino es, o está
dentro de, ``ofertas/_ejemplo``; cada parche exige el número exacto de coincidencias (``veces``), de modo que si el ejemplo cambia, la mutación
falla en voz alta en lugar de aplicarse a medias. Sin red, sin aleatoriedad.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ / "ofertas" / "_ejemplo"
CATALOGO = RAIZ / "tests" / "fixtures" / "contratos" / "mutaciones_landing" / "catalogo.json"
MARCA = ".copia-temporal-mutaciones"


class ErrorMutacion(Exception):
    """El parche no se puede aplicar tal cual (destino prohibido, archivo ausente o número de coincidencias distinto)."""


def cargar_catalogo() -> dict[str, Any]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def mutaciones(incluir_complementarias: bool = False) -> list[dict[str, Any]]:
    """Las OCHO mutaciones del encargo (``ML-01``…``ML-08``); con ``incluir_complementarias`` también ``MC-01``…``MC-04``."""
    cat = cargar_catalogo()
    return list(cat["mutaciones"]) + (list(cat["complementarias"]) if incluir_complementarias else [])


def copiar_ejemplo(carpeta_temporal: Path | str, nombre: str = "oferta") -> Path:
    """Copia ``ofertas/_ejemplo`` a ``<carpeta_temporal>/<nombre>`` y escribe la marca de copia temporal. Devuelve la copia."""
    destino = Path(carpeta_temporal).resolve() / nombre
    if destino == EJEMPLO.resolve() or EJEMPLO.resolve() in destino.parents:
        raise ErrorMutacion("la copia no puede estar dentro de ofertas/_ejemplo")
    shutil.copytree(EJEMPLO, destino)
    (destino / MARCA).write_text("copia temporal para mutaciones de B0-11; no es una oferta\n", encoding="utf-8")
    return destino


def _comprobar_destino(destino: Path) -> Path:
    d = Path(destino).resolve()
    if d == EJEMPLO.resolve() or EJEMPLO.resolve() in d.parents or d in EJEMPLO.resolve().parents:
        raise ErrorMutacion("las mutaciones no operan sobre ofertas/_ejemplo: usa una copia temporal (copiar_ejemplo)")
    if not (d / MARCA).is_file():
        raise ErrorMutacion(f"{d} no es una copia temporal marcada (falta {MARCA}); usa copiar_ejemplo()")
    return d


def _archivo(d: Path, rel: str) -> Path:
    ruta = (d / rel).resolve()
    if d not in ruta.parents:
        raise ErrorMutacion(f"ruta fuera de la copia: {rel}")
    return ruta


def _parche(d: Path, p: dict[str, Any]) -> str:
    ruta = _archivo(d, p["archivo"])
    op = p["op"]
    if not ruta.is_file():
        raise ErrorMutacion(f"{p['archivo']}: no existe en la copia")
    if op == "borrar":
        ruta.unlink()
    elif op in ("reemplazar", "insertar_antes"):
        texto = ruta.read_text(encoding="utf-8")
        clave = p["buscar"] if op == "reemplazar" else p["ancla"]
        if texto.count(clave) != p["veces"]:
            raise ErrorMutacion(f"{p['archivo']}: se esperaban {p['veces']} coincidencia(s) de {clave!r} y hay {texto.count(clave)}")
        nuevo = p["reemplazo"] if op == "reemplazar" else p["texto"] + clave
        ruta.write_text(texto.replace(clave, nuevo), encoding="utf-8", newline="\n")
    elif op == "json_establecer":
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        nodo = datos
        for k in p["ruta"][:-1]:
            nodo = nodo[k]
        nodo[p["ruta"][-1]] = p["valor"]
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        raise ErrorMutacion(f"operación desconocida: {op}")
    return p["archivo"]


def aplicar(mutacion_id: str, destino: Path | str) -> list[str]:
    """Aplica la mutación ``mutacion_id`` (``ML-01``…, ``MC-01``…) a la copia temporal ``destino``; devuelve los archivos tocados."""
    d = _comprobar_destino(Path(destino))
    encontradas = [m for m in mutaciones(True) if m["id"] == mutacion_id]
    if not encontradas:
        raise ErrorMutacion(f"mutación desconocida: {mutacion_id}")
    return [_parche(d, p) for p in encontradas[0]["parches"]]
