"""Empaquetado determinista de D4: ``items[].sha256``, ``producto_sha256``, ``matriz_promesas``, ``tiempos``.

Promueve a ``scripts/`` el patrón de ``.claude/skills/d4-producto/scripts/empaquetar.py`` adaptado para que
la salida cumpla ``contratos/producto.schema.json`` exactamente (``additionalProperties: false``: el esquema
NO tiene un campo ``producto_sha256`` propio -- ese hash es para la subida a R2 que hace ``postcompra.publicar_producto``,
dueño B7, docs/06 N07 -- así que este script lo calcula y lo devuelve APARTE de ``producto.json``, nunca
metido a la fuerza en el documento).

``ENTRADA.json`` es casi ``producto.json`` sin los campos que este script calcula: cada ``items[]`` lleva
``archivo`` (ruta relativa a ``--raiz``) pero NO necesita ``sha256`` ni ``peso_mb`` correctos (se recalculan
siempre desde el archivo real, nunca se confía en lo declarado); el resto de los campos (``matriz_promesas``,
``tiempos``, ``pasos``, ``vigencia``, ``entrega``, ``ia_divulgacion``, ``changelog``, identificadores) pasa
tal cual. ``tiempos.prometido_min`` DEBE declararse igual al de ``oferta.promesa.tiempo_prometido_min``
(R10, docs/contratos.md); este script no lee ``oferta.json``, así que exige ``--prometido-min`` y falla si no
coincide con lo que trae la entrada.

CLI::

    .venv/bin/python -m scripts.producto.empaquetar ENTRADA.json --raiz 04-producto/entregables \\
        --prometido-min 20 [--salida producto.json]

Salida: 0 ok (imprime ``{"producto": ..., "producto_sha256": "sha256:...", "items_sha256": {...}}``) ·
2 uso (falta un archivo declarado, ``--prometido-min`` ausente) · 3 entrada inválida o no cumple el esquema.
Nunca sobrescribe ``--salida`` si ya existe (un producto empaquetado es inmutable; una corrección es ``vN+1``).
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Mapping

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion

__all__ = ["empaquetar", "main"]

VERSION_SCRIPT = "1.0.0"
_BYTES_POR_MB = Decimal(1_000_000)
_CAMPOS_PASE = ("schema_version", "producto_id", "oferta_id", "version", "origen_version", "estado",
                "matriz_promesas", "pasos", "vigencia", "entrega", "ia_divulgacion", "changelog")


def _peso_mb(tam_bytes: int) -> str:
    return str((Decimal(tam_bytes) / _BYTES_POR_MB).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def _empaquetar_item(item: Mapping[str, Any], raiz: Path) -> dict[str, Any]:
    ruta = raiz / item["archivo"]
    if not ruta.is_file():
        raise ErrorUso(f"item {item.get('id')!r}: no existe el archivo declarado: {ruta}")
    nuevo = dict(item)
    nuevo["sha256"] = comun.hash_archivo(ruta)
    nuevo["peso_mb"] = _peso_mb(ruta.stat().st_size)
    return nuevo


def empaquetar(entrada: Mapping[str, Any], raiz: Path, *, prometido_min: int) -> dict[str, Any]:
    """``(producto.json, producto_sha256, items_sha256)`` deterministas a partir de ``ENTRADA`` y los archivos reales.

    Errores: ``ErrorUso`` (2) si falta un archivo declarado; ``ErrorValidacion`` (3) si la entrada no tiene
    la forma esperada, si ``tiempos.prometido_min`` no coincide con ``prometido_min`` (R10) o si el resultado
    no cumple ``contratos/producto.schema.json``.
    """
    if not isinstance(entrada, Mapping) or "items" not in entrada or "tiempos" not in entrada:
        raise ErrorValidacion("entrada inválida: faltan «items» o «tiempos»")
    faltan = [c for c in _CAMPOS_PASE if c not in entrada]
    if faltan:
        raise ErrorValidacion("entrada inválida: falta " + ", ".join(faltan))
    tiempos = dict(entrada["tiempos"])
    if tiempos.get("prometido_min") != prometido_min:
        raise ErrorValidacion(
            f"tiempos.prometido_min={tiempos.get('prometido_min')!r} != --prometido-min {prometido_min!r} "
            "(R10: debe ser IGUAL a oferta.promesa.tiempo_prometido_min)"
        )
    items = [_empaquetar_item(i, raiz) for i in entrada["items"]]
    doc = {clave: entrada[clave] for clave in _CAMPOS_PASE}
    doc["items"] = items
    doc["tiempos"] = tiempos
    errores = comun.errores_de_esquema("producto", doc)
    if errores:
        raise ErrorValidacion("producto.json empaquetado no cumple el esquema: " + comun.resumir_errores_esquema(errores))
    items_sha256 = {i["id"]: i["sha256"] for i in items if i.get("en_paquete", True)}
    producto_sha256 = comun.hash_objeto(items_sha256)
    return {"producto": doc, "producto_sha256": producto_sha256, "items_sha256": items_sha256}


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def _cargar_json(ruta: str) -> Any:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorUso(f"no existe {ruta}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErrorValidacion(f"{ruta} ilegible: {exc}") from exc


def _principal(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.empaquetar", description="Empaquetado determinista de D4")
    ap.add_argument("entrada")
    ap.add_argument("--raiz", required=True, help="carpeta base de los «archivo» declarados en items[]")
    ap.add_argument("--prometido-min", required=True, type=int)
    ap.add_argument("--salida")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    entrada = _cargar_json(a.entrada)
    resultado = empaquetar(entrada, Path(a.raiz), prometido_min=a.prometido_min)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if a.salida:
        ruta = Path(a.salida)
        if ruta.exists():
            raise ErrorUso(f"{a.salida} ya existe y no se sobrescribe (crea v{{n+1}})")
        comun.escribir_atomico(ruta, json.dumps(resultado["producto"], ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    sys.stdout.write(texto)
    return 0


def main(argv: list[str] | None = None) -> int:
    return comun.ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
