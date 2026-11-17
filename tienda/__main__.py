"""python3 -m tienda [como <operación>] — muestra la plataforma activa y cómo se hace cada operación en ella."""
from __future__ import annotations

import json
import sys

import tienda


def main(argv: list[str]) -> int:
    t = tienda.activa()
    if len(argv) >= 2 and argv[0] == "como":
        if argv[1] not in tienda.OPERACIONES:
            print(f"operación desconocida: {argv[1]}. Válidas: {', '.join(tienda.OPERACIONES)}")
            return 2
        print(json.dumps({"plataforma": t.nombre, "operacion": argv[1], **t.como(argv[1])}, ensure_ascii=False, indent=1))
        return 0
    print(f"Plataforma activa: {t.nombre}")
    for op, (tipo, desc) in tienda.OPERACIONES.items():
        c = t.como(op)
        donde = c.get("herramienta") or c.get("ruta") or c.get("pantalla") or ""
        print(f"  {op:22} {tipo:7} {c.get('via', '?'):10} {donde}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
