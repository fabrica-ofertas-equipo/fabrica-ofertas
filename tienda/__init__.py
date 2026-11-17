"""Capa de tienda de la fábrica: un contrato y un adaptador por plataforma (ver contrato.py).

    import tienda
    t = tienda.activa()            # la plataforma configurada (tienda/config.json o la variable FABRICA_TIENDA)
    t.ventas(respuesta_cruda)      # → [Venta] en forma normal
    t.url_landing("mi-tienda")

Desde la terminal:
    python3 -m tienda                    # qué plataforma está activa y cómo se hace cada operación
    python3 -m tienda como guardar_landing
    python3 -m tienda.conformidad [nombre]
"""
from __future__ import annotations

import importlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from tienda.contrato import OPERACIONES, Tienda, problemas_cobro, problemas_embudo, problemas_venta  # noqa: F401

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = Path(__file__).resolve().parent / "config.json"
POR_DEFECTO = "impultienda"


def configurada() -> str:
    env = os.environ.get("FABRICA_TIENDA", "").strip()
    if env:
        return env
    try:
        return str(json.loads(CONFIG.read_text(encoding="utf-8")).get("plataforma") or POR_DEFECTO)
    except (OSError, ValueError):
        return POR_DEFECTO


@lru_cache(maxsize=None)
def cargar(nombre: str) -> Tienda:
    if not nombre.replace("_", "").isalnum():
        raise ValueError(f"nombre de adaptador inválido: {nombre!r}")
    mod = importlib.import_module(f"tienda.adaptadores.{nombre}")
    return mod.Adaptador()


def activa() -> Tienda:
    return cargar(configurada())


def regla(clave: str, defecto: Any = None) -> Any:
    """Lee ofertas/_funnels/reglas.json (clave con puntos). Sin archivo, el defecto."""
    try:
        d: Any = json.loads((RAIZ / "ofertas" / "_funnels" / "reglas.json").read_text(encoding="utf-8"))
        for k in clave.split("."):
            d = d[k]
        return d
    except (OSError, ValueError, KeyError, TypeError):
        return defecto
