"""Aplica un defecto sembrado (``evals/sembrados/sembrados.yaml``) sobre una COPIA de una oferta dorada, para calibrar al QA de D3.

El QA debe detectar >= 90 % de los bloqueantes sembrados (backbone 6.6; departamentos/04-oferta.md §6, A.1). Cada sembrado describe una o varias
mutaciones sobre archivos de una oferta dorada (``evals/dorados/<caso>/OF-AAAAMM-NN/``); este script copia esa carpeta a ``<destino>/OF-AAAAMM-NN/`` (el validador exige que la carpeta se llame como el
``oferta_id``) y las aplica. La
original no se toca. Solo biblioteca estándar + PyYAML.

Uso (desde la raíz del repositorio)::

    .venv/bin/python .claude/skills/d3-arquitectura-oferta/scripts/aplicar_sembrado.py --sembrado S4 --destino /tmp/x   # crea /tmp/x/OF-AAAAMM-NN/ \
        [--sembrados evals/sembrados/sembrados.yaml] [--dorados evals/dorados] [--listar]

Operaciones: ``set`` (JSON pointer RFC 6901, crea o reemplaza), ``delete``, ``append`` (a una lista), ``reemplazar_texto`` (``de`` -> ``a`` en un archivo de
texto, p. ej. ``oferta.md``) y ``copiar_desde`` (sustituye el archivo por otro de ``evals/sembrados/datos/``, p. ej. una economia.json generada por el motor
con entradas distintas). Salida: 0 · 2 uso · 3 la mutación no se pudo aplicar.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent


def _tokens(pointer: str) -> list[str]:
    if pointer in ("", "/"):
        return []
    if not pointer.startswith("/"):
        raise ValueError(f"JSON pointer inválido: {pointer!r}")
    return [t.replace("~1", "/").replace("~0", "~") for t in pointer[1:].split("/")]


def _padre(doc: Any, tokens: list[str]) -> tuple[Any, str]:
    actual = doc
    for t in tokens[:-1]:
        actual = actual[int(t)] if isinstance(actual, list) else actual[t]
    return actual, tokens[-1]


def aplicar_op(doc: Any, op: Mapping[str, Any]) -> Any:
    """Aplica ``set`` | ``delete`` | ``append`` sobre un documento JSON ya cargado y lo devuelve."""
    tipo = op["op"]
    tokens = _tokens(op["ruta"])
    if not tokens:
        if tipo == "set":
            return op["valor"]
        raise ValueError("solo set admite la raíz")
    padre, clave = _padre(doc, tokens)
    if tipo == "set":
        if isinstance(padre, list):
            padre[int(clave)] = op["valor"]
        else:
            padre[clave] = op["valor"]
    elif tipo == "delete":
        if isinstance(padre, list):
            del padre[int(clave)]
        else:
            del padre[clave]
    elif tipo == "append":
        destino = padre[int(clave)] if isinstance(padre, list) else padre[clave]
        destino.append(op["valor"])
    else:
        raise ValueError(f"operación desconocida: {tipo}")
    return doc


def aplicar(sembrado: Mapping[str, Any], origen: Path, destino: Path, datos: Path | None = None) -> list[str]:
    """Copia ``origen`` a ``destino/<nombre de origen>`` y aplica las mutaciones; devuelve los archivos modificados."""
    destino = destino / origen.name          # la carpeta debe llamarse como el oferta_id
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe (usa un destino nuevo)")
    shutil.copytree(origen, destino)
    tocados: list[str] = []
    for m in sembrado["muta"]:
        ruta = destino / m["archivo"]
        if not ruta.is_file():
            raise FileNotFoundError(f"no existe {m['archivo']} en la copia")
        if m["op"] == "copiar_desde":
            shutil.copyfile((datos or SKILL / "evals" / "sembrados" / "datos") / m["desde"], ruta)
        elif m["op"] == "reemplazar_texto":
            texto = ruta.read_text(encoding="utf-8")
            if m["de"] not in texto:
                raise ValueError(f"{m['archivo']}: no contiene el texto a reemplazar: {m['de']!r}")
            ruta.write_text(texto.replace(m["de"], m["a"], 1), encoding="utf-8")
        else:
            doc = json.loads(ruta.read_text(encoding="utf-8"))
            doc = aplicar_op(doc, m)
            ruta.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tocados.append(m["archivo"])
    return tocados


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aplicar_sembrado.py", description=__doc__.splitlines()[0])
    ap.add_argument("--sembrado", help="id (S1…S25)")
    ap.add_argument("--destino")
    ap.add_argument("--sembrados", default=str(SKILL / "evals" / "sembrados" / "sembrados.yaml"))
    ap.add_argument("--dorados", default=str(SKILL / "evals" / "dorados"))
    ap.add_argument("--listar", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    datos = yaml.safe_load(Path(args.sembrados).read_text(encoding="utf-8"))
    sembrados = {s["id"]: s for s in datos["sembrados"]}
    if args.listar:
        for s in datos["sembrados"]:
            print(f"{s['id']:4} {s['severidad']:10} base={s['base']}  {s['defecto']}")
        return 0
    if not args.sembrado or not args.destino or args.sembrado not in sembrados:
        print("uso: --sembrado Sn --destino DIR (o --listar)", file=sys.stderr)
        return 2
    s = sembrados[args.sembrado]
    try:
        base = Path(args.dorados) / s["base"]
        origen = next(p for p in sorted(base.iterdir()) if p.is_dir() and p.name.startswith("OF-"))
        tocados = aplicar(s, origen, Path(args.destino))
    except (OSError, ValueError, KeyError, IndexError, StopIteration) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    print(f"{s['id']} aplicado sobre {s['base']}: {', '.join(tocados)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
