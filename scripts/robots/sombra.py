"""``python -m scripts.robots.sombra``: ejecutor de robots EN SOMBRA (solo lectura y propuesta; ver ``docs/_historial/mentor-sistema/robots-sombra.md``).

Subcomandos:
  listar     catálogo de los 10 robots (+ 2 de apoyo): horario, nivel, quién lo ejecuta hoy y mañana.
  ejecutar   corre robots en sombra: ``--robot ID`` (repetible) o ``--todos``. Por defecto NO escribe nada; ``--simular`` lo dice explícito;
             ``--escribir`` guarda el latido de cada robot (``empresa/robots/latidos.jsonl``), su producto (``empresa/robots/salidas/``),
             ``empresa/datos/alertas.jsonl`` (robot de alertas) y ``empresa/robots/estado.json``.
  estado     qué robots corrieron hoy, cuáles faltan y qué latidos están vencidos (``--json`` para el semáforo; ``--escribir`` guarda estado.json).
  programar  IMPRIME las entradas de launchd/cron (no instala nada; instalar es decisión del dueño).

Nada de esto envía mensajes ni toca Meta, Stripe, claves, ``.env`` ni dinero. Salida: 0 bien · 2 uso · 3 algún robot falló o no se pudo escribir.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

from scripts.robots.catalogo import CATALOGO, VERSION, ids_en_sombra, latido_max_min
from scripts.robots.nucleo import RAIZ_REPO, Contexto, ErrorRobot, parsear_z
from scripts.robots.zonas import ZONA_MERCADO_DEFECTO

__all__ = ["main"]


def _raiz(args: argparse.Namespace) -> Path:
    raiz = Path(args.raiz or os.environ.get("FABRICA_RAIZ") or RAIZ_REPO)
    if not raiz.is_dir():
        raise ErrorRobot("--raiz no es una carpeta")
    return raiz


def _ahora(args: argparse.Namespace) -> _dt.datetime | None:
    if not getattr(args, "ahora", None):
        return None
    t = parsear_z(args.ahora)
    if t is None:
        raise ErrorRobot("--ahora debe verse así: 2026-11-07T08:30:00Z")
    return t


def _comunes(p: argparse.ArgumentParser) -> None:
    p.add_argument("--raiz", default=None, help="raíz del proyecto (defecto: FABRICA_RAIZ o la carpeta de este código)")
    p.add_argument("--ahora", default=None, help="instante fijo AAAA-MM-DDTHH:MM:SSZ (para pruebas y repetir una corrida)")
    p.add_argument("--json", action="store_true", help="salida en JSON")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m scripts.robots.sombra", description="Robots en sombra: solo lectura y propuesta, con latido por robot.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("listar", help="catálogo de robots")
    s.add_argument("--json", action="store_true")
    e = sub.add_parser("ejecutar", help="corre robots en sombra (por defecto no escribe nada)")
    _comunes(e)
    g = e.add_mutually_exclusive_group(required=True)
    g.add_argument("--robot", action="append", default=None, metavar="ID", help="un robot (se puede repetir)")
    g.add_argument("--todos", action="store_true", help="todos los robots que tienen versión en sombra")
    m = e.add_mutually_exclusive_group()
    m.add_argument("--simular", action="store_true", help="no escribe nada (es lo que hace por defecto)")
    m.add_argument("--escribir", action="store_true", help="guarda latidos, productos y estado.json")
    e.add_argument("--programado", action="store_true", help="marca el latido como de origen «programado» (lo usan las entradas de launchd/cron)")
    e.add_argument("--db", default=None, help="base SQLite en solo lectura (defecto: <raiz>/empresa/datos/fabrica.db)")
    e.add_argument("--fecha", default=None, help="día de cuenta que se evalúa, AAAA-MM-DD (defecto: ayer, UTC)")
    e.add_argument("--umbrales", default=None, help="archivo JSON de umbrales para SIMULAR (no firmados); defecto: parametros.yaml")
    t = sub.add_parser("estado", help="qué corrió hoy, qué falta, qué latidos están vencidos")
    _comunes(t)
    t.add_argument("--escribir", action="store_true", help="guarda empresa/robots/estado.json")
    t.add_argument("--zona-mercado", default=ZONA_MERCADO_DEFECTO)
    t.add_argument("--zona-dueno", default=None, help="zona del dueño (defecto: la de esta Mac)")
    r = sub.add_parser("programar", help="IMPRIME las entradas de launchd/cron (no instala nada)")
    r.add_argument("--raiz", default=None)
    r.add_argument("--formato", choices=("launchd", "cron", "ambos"), default="ambos")
    r.add_argument("--robot", action="append", default=None, metavar="ID")
    r.add_argument("--python", default=None, help="intérprete a usar (defecto: <raiz>/.venv/bin/python)")
    r.add_argument("--zona-mercado", default=ZONA_MERCADO_DEFECTO)
    r.add_argument("--zona-dueno", default=None, help="zona de esta Mac / del dueño (defecto: la de esta Mac)")
    r.add_argument("--ahora", default=None)
    return ap


def _listar(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps([{**r, "latido_max_min": latido_max_min(r)} for r in CATALOGO], ensure_ascii=False, indent=2))
        return 0
    print(f"Robots del método (10) y trabajos de apoyo (2) · marco en sombra {VERSION}\n")
    print(f"{'ID':<11}{'N°':<4}{'HORARIO':<34}{'HOY':<9}MAÑANA")
    for r in CATALOGO:
        print(f"{r['id']:<11}{str(r['numero'] or '·'):<4}{r['horario']:<34}{r['ejecutor_hoy']:<9}{r['ejecutor_manana']}")
    print("\nEn sombra hoy: " + ", ".join(ids_en_sombra()) + "\nLos demás no tienen versión en sombra: los construye S-B (runtime real) o falta decidir sus números.")
    return 0


def _ejecutar(args: argparse.Namespace) -> int:
    from scripts.robots.ejecucion import EJECUTORES, ejecutar, texto_resumen
    pedidos = ids_en_sombra() if args.todos else list(dict.fromkeys(args.robot or []))
    desconocidos = [r for r in pedidos if r not in EJECUTORES]
    if desconocidos:
        validos = ", ".join(ids_en_sombra())
        print(f"error: sin versión en sombra: {', '.join(desconocidos)}. Disponibles: {validos}", file=sys.stderr)
        return 2
    c = Contexto(_raiz(args), _ahora(args), escribir=bool(args.escribir), db=Path(args.db) if args.db else None, fecha=args.fecha,
                 umbrales=Path(args.umbrales) if args.umbrales else None)
    corrida = ejecutar(pedidos, c, origen="programado" if args.programado else "manual")
    print(json.dumps(corrida, ensure_ascii=False, indent=2, sort_keys=True) if args.json else texto_resumen(corrida))
    return 3 if (corrida["errores"] or corrida["fallas_de_latido"] or corrida["error_estado"]) else 0


def _estado(args: argparse.Namespace) -> int:
    from scripts.robots.estado import calcular_estado, escribir_estado, texto_estado
    ahora = _ahora(args) or _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    try:
        e = calcular_estado(_raiz(args), ahora, zona_mercado=args.zona_mercado, zona_dueno=args.zona_dueno)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.escribir:
        escribir_estado(_raiz(args), e)
    print(json.dumps(e, ensure_ascii=False, indent=2, sort_keys=True) if args.json else texto_estado(e))
    return 0


def _programar(args: argparse.Namespace) -> int:
    from scripts.robots.programar import generar
    pedidos = list(dict.fromkeys(args.robot or [])) or None
    if pedidos:
        malos = [r for r in pedidos if r not in ids_en_sombra()]
        if malos:
            print(f"error: sin versión en sombra: {', '.join(malos)}. Disponibles: {', '.join(ids_en_sombra())}", file=sys.stderr)
            return 2
    try:
        texto = generar(raiz=_raiz(args).resolve(), python=args.python, formato=args.formato, robots=pedidos, zona_mercado=args.zona_mercado,
                        zona_dueno=args.zona_dueno, ahora=_ahora(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(texto)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        return {"listar": _listar, "ejecutar": _ejecutar, "estado": _estado, "programar": _programar}[args.cmd](args)
    except ErrorRobot as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
