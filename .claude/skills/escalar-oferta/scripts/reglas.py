"""Lee las reglas del dueño de `ofertas/_funnels/reglas.json` (un solo lugar para todos los números de las reglas).

Uso desde un script:  from reglas import valor;  VECES = valor("test.corte_tickets", 1.5)
Si el archivo falta o la clave no existe, devuelve el valor por defecto (el mismo que estaba firmado) y lo anota en stderr,
para que una regla nunca quede sin número. Sin efectos: solo lee.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
ARCHIVO = RAIZ / "ofertas" / "_funnels" / "reglas.json"


@lru_cache(maxsize=1)
def todas() -> dict:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def valor(clave: str, defecto):
    d = todas()
    for parte in clave.split("."):
        if not isinstance(d, dict) or parte not in d:
            print(f"reglas: falta «{clave}» en {ARCHIVO.name}; uso {defecto!r}", file=sys.stderr)
            return defecto
        d = d[parte]
    return d
