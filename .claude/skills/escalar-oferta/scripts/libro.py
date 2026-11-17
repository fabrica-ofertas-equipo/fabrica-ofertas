"""Escribir el libro de tests con candado (escenario S38 del 2026-11-13).

Varias tareas tocan `ofertas/_funnels/libro-de-tests.json` (vigilancia cada hora, renovación diaria, lanzamientos, revisión).
Si dos lo editan a la vez, una pisa lo de la otra. Este script es la ÚNICA forma de escribirlo desde las tareas: toma un
candado de archivo, lee la versión de disco en ese momento, aplica el cambio, guarda una copia previa y escribe de forma atómica.

Uso (desde la raíz; L=.claude/skills/escalar-oferta/scripts/libro.py). `TEST` es el `nombre` (o `oferta`) del test;
RUTA es una ruta con puntos dentro del test (`ficha.campanas.0.presupuesto_diario_usd`); VALOR es JSON.
  python3 $L get TEST [RUTA]
  python3 $L set TEST RUTA VALOR                      reemplaza (crea las claves que falten)
  python3 $L append TEST RUTA VALOR                   agrega al final de una lista (la crea si no existe)
  python3 $L merge TEST VALOR                         mezcla un objeto en el test (claves de primer nivel)
  python3 $L nuevo-test VALOR                         agrega un test entero (falla si ya existe uno con ese nombre)
  python3 $L set-raiz RUTA VALOR                      cambia algo fuera de los tests (tipos_de_cambio.MXN…)
Copia previa: ofertas/_funnels/.respaldos/libro-<fecha-hora>.json (se guardan las últimas 50).
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
CANDADO = LIBRO.with_suffix(".lock")
RESPALDOS = LIBRO.parent / ".respaldos"
MAX_RESPALDOS = 50


@contextmanager
def candado(ruta_libro: Path = LIBRO):
    lock = ruta_libro.with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _test(libro: dict, nombre: str) -> dict:
    for t in libro.get("tests") or []:
        if nombre in (t.get("nombre"), t.get("oferta")):
            return t
    raise SystemExit(f"No hay un test «{nombre}» en el libro.")


def _paso(clave: str):
    return int(clave) if clave.lstrip("-").isdigit() else clave


def _bajar(obj, partes: list[str], crear: bool):
    for p in partes:
        k = _paso(p)
        if isinstance(obj, list):
            obj = obj[k]
        else:
            if k not in obj:
                if not crear:
                    raise SystemExit(f"No existe «{p}».")
                obj[k] = {}
            obj = obj[k]
    return obj


def poner(obj: dict, ruta: str, valor, modo: str) -> None:
    partes = ruta.split(".")
    padre = _bajar(obj, partes[:-1], crear=True)
    k = _paso(partes[-1])
    if modo == "set":
        padre[k] = valor
    elif modo == "append":
        lista = padre.get(k) if isinstance(padre, dict) else padre[k]
        if lista is None:
            padre[k] = lista = []
        if not isinstance(lista, list):
            raise SystemExit(f"«{ruta}» no es una lista.")
        lista.append(valor)


def modificar(cambio, ruta_libro: Path = LIBRO) -> dict:
    """Aplica `cambio(libro)` con el candado tomado; guarda respaldo y escribe atómico. Devuelve el libro nuevo."""
    with candado(ruta_libro):
        libro = json.loads(ruta_libro.read_text(encoding="utf-8"))
        cambio(libro)
        resp = ruta_libro.parent / ".respaldos"
        resp.mkdir(exist_ok=True)
        (resp / f"libro-{dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json").write_text(ruta_libro.read_text(encoding="utf-8"), encoding="utf-8")
        for viejo in sorted(resp.glob("libro-*.json"))[:-MAX_RESPALDOS]:
            viejo.unlink(missing_ok=True)
        tmp = ruta_libro.with_suffix(".tmp")
        tmp.write_text(json.dumps(libro, ensure_ascii=False, indent=1), encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))   # comprobación: lo escrito se vuelve a leer
        os.replace(tmp, ruta_libro)
        return libro


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get"); g.add_argument("test"); g.add_argument("ruta", nargs="?")
    for c in ("set", "append"):
        x = sub.add_parser(c); x.add_argument("test"); x.add_argument("ruta"); x.add_argument("valor")
    m = sub.add_parser("merge"); m.add_argument("test"); m.add_argument("valor")
    n = sub.add_parser("nuevo-test"); n.add_argument("valor")
    r = sub.add_parser("set-raiz"); r.add_argument("ruta"); r.add_argument("valor")
    a = ap.parse_args(argv)
    if a.cmd == "get":
        t = _test(json.loads(LIBRO.read_text(encoding="utf-8")), a.test)
        print(json.dumps(_bajar(t, a.ruta.split("."), crear=False) if a.ruta else t, ensure_ascii=False, indent=1))
        return 0
    valor = json.loads(a.valor)
    if a.cmd in ("set", "append"):
        modificar(lambda L: poner(_test(L, a.test), a.ruta, valor, a.cmd))
    elif a.cmd == "merge":
        if not isinstance(valor, dict):
            raise SystemExit("merge necesita un objeto JSON.")
        modificar(lambda L: _test(L, a.test).update(valor))
    elif a.cmd == "nuevo-test":
        # El panel une el test con su carpeta (ficha.carpeta_trabajo: sale de «armando») y avisa del token CAPI
        # por tienda (ficha.tiendas[].capi.ok false). Sin esos campos la oferta queda «armando» y el aviso no sale
        # (pasó con Oferta E y Oferta F, 13-nov).
        ficha = valor.get("ficha") if isinstance(valor.get("ficha"), dict) else None
        if not ficha or not str(ficha.get("carpeta_trabajo") or "").startswith("ofertas/_borrador-"):
            raise SystemExit("nuevo-test necesita ficha.carpeta_trabajo («ofertas/_borrador-…»): el panel la usa para sacar la oferta de «armando».")
        for x in ficha.get("tiendas") or []:
            if isinstance(x, dict) and not isinstance(x.get("capi"), dict):
                x["capi"] = {"ok": False, "revisado": None, "nota": "token CAPI sin cargar (por defecto al crear el test)"}

        def agregar(L):
            if any(valor.get("nombre") in (t.get("nombre"), t.get("oferta")) for t in L.get("tests") or []):
                raise SystemExit(f"Ya hay un test «{valor.get('nombre')}».")
            L.setdefault("tests", []).append(valor)
        modificar(agregar)
    elif a.cmd == "set-raiz":
        modificar(lambda L: poner(L, a.ruta, valor, "set"))
    print(f"Libro actualizado ({a.cmd}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
