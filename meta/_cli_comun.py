"""Ayudas compartidas por los CLI de ``meta.{crear,activar,pausar,subir_presupuesto}``.

Los cuatro CLI siguen la forma común de docs/06 §4.1: ``--oferta``, ``--live``/``--modo``, ``--json``,
``--raiz``, ``--ahora``. **Alcance de esta entrega** (ola 1, B5): ``ClienteMeta`` solo corre sobre
``TransporteFixture``; ningún script aquí abre una conexión real. ``--modo live`` existe en la forma
del CLI (consistencia de interfaz) pero se niega con ``ErrorBloqueado`` hasta que un ``Transporte``
real se conecte (pedido en el README, «Pedidos»); ``--modo fixture`` corre el mismo código con las
reglas de un archivo (``TransporteFixture.desde_archivo``).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from engine.errores import ErrorBloqueado, ErrorUso
from engine.transporte import TransporteFixture
from meta.cliente import ClienteMeta

__all__ = ["agregar_argumentos_comunes", "construir_cliente", "imprimir"]


def agregar_argumentos_comunes(ap: argparse.ArgumentParser, *, con_oferta: bool = True) -> None:
    """Agrega las banderas comunes de docs/06 §4.1 (adaptadas: ``--modo`` en vez de ``--live`` suelto)."""
    if con_oferta:
        ap.add_argument("--oferta", required=True, help="OF-AAAAMM-NN")
    ap.add_argument("--modo", choices=("dry-run", "fixture", "live"), default="dry-run",
                    help="dry-run: solo imprime el plan; fixture: corre sobre --fixture (TransporteFixture); live: aún no conectado")
    ap.add_argument("--fixture", help="reglas de TransporteFixture (JSON/YAML) para --modo fixture")
    ap.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
    ap.add_argument("--ahora", help="instante UTC con Z (solo con FABRICA_ENTORNO distinto de produccion)")
    ap.add_argument("--json", action="store_true", help="una línea JSON en stdout")


def construir_cliente(args: argparse.Namespace, env: dict[str, str], *, segundos_min_entre_ediciones: int,
                      max_cambios_presupuesto_por_hora: int) -> tuple[ClienteMeta, TransporteFixture]:
    """Un ``ClienteMeta`` sobre un ``TransporteFixture`` cargado de ``--fixture`` (solo para ``--modo fixture``).

    Errores: ``ErrorBloqueado`` si ``--modo live`` (sin Transporte real conectado, alcance de esta
    entrega); ``ErrorUso`` si ``--modo fixture`` sin ``--fixture``.
    """
    if args.modo == "live":
        raise ErrorBloqueado(
            "meta.*: esta entrega no conecta un Transporte real a Meta (alcance de la noche, ver README «Pedidos»); use --modo fixture"
        )
    if not args.fixture:
        raise ErrorUso("--modo fixture exige --fixture RUTA con las reglas de TransporteFixture")
    transporte = TransporteFixture.desde_archivo(Path(args.fixture))
    token = (env.get("META_TOKEN_OPERADOR") or "").strip() or "fixture-token"
    secreto = (env.get("META_APP_SECRET") or "").strip() or "fixture-secreto"
    cliente = ClienteMeta(
        transporte, token=token, app_secret=secreto, segundos_min_entre_ediciones=segundos_min_entre_ediciones,
        max_cambios_presupuesto_por_hora=max_cambios_presupuesto_por_hora,
    )
    return cliente, transporte


def imprimir(*, ok: bool, modo: str, codigo: int, datos: Any, avisos: list[str], as_json: bool) -> None:
    """Salida uniforme: una línea JSON con ``--json``, o el objeto de datos legible sin ella."""
    if as_json:
        print(json.dumps({"ok": ok, "modo": modo, "codigo": codigo, "datos": datos, "avisos": avisos}, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(datos, indent=2, ensure_ascii=False, sort_keys=True))
        for aviso in avisos:
            print(aviso)
