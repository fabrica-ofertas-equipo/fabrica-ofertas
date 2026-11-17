"""Husos horarios de los robots: las horas del método son del RELOJ DEL MERCADO (mapeo §2, E-14), salvo el informe, que es la hora del dueño.

Mercado por defecto: ``Europe/Warsaw`` (J10: la oferta A es para Polonia). Es una HIPÓTESIS: se cambia con ``--zona-mercado``.
"""
from __future__ import annotations

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = ["ZONA_MERCADO_DEFECTO", "zona", "zona_local"]

ZONA_MERCADO_DEFECTO = "Europe/Warsaw"


def zona(nombre: str) -> ZoneInfo:
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ValueError(f"zona horaria desconocida: {nombre!r} (ejemplo: Europe/Warsaw)") from exc


def zona_local() -> ZoneInfo:
    """Zona de esta Mac: ``TZ`` o el enlace ``/etc/localtime``; si no se puede saber, UTC (y quien llama debería avisarlo)."""
    nombre = os.environ.get("TZ")
    if not nombre:
        try:
            destino = os.path.realpath("/etc/localtime")
            nombre = destino.split("zoneinfo/", 1)[1] if "zoneinfo/" in destino else None
        except OSError:
            nombre = None
    try:
        return ZoneInfo(nombre) if nombre else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return ZoneInfo("UTC")
