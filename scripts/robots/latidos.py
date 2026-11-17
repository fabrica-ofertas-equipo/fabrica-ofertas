"""Latido por robot: ``empresa/robots/latidos.jsonl`` (una línea por ejecución; solo se agrega, nunca se reescribe).

Formato de una línea (propuesta de esquema para S-A, ver ``docs/_historial/mentor-sistema/robots-sombra.md`` §4)::

    {"schema_version":"1.0.0","id":"LAT-20261107T083000Z-informe","robot":"informe","inicio":"…Z","fin":"…Z","duracion_ms":412,
     "resultado":"parcial","razon":"…","modo":"sombra","origen":"manual|programado","ejecutor":"sombra-S-C","version":"0.1.0",
     "salidas":["empresa/robots/salidas/informe/2026-11-07.json"],"metricas":{"acierto_bp":7500}}

* **Idempotente:** el ``id`` sale del robot y del segundo de inicio; repetir la misma corrida (mismo ``--ahora``) no agrega otra línea.
* **Escritura segura:** ``O_APPEND`` + ``flock`` + una sola ``write`` + ``fsync``; sin enlaces simbólicos; el archivo no se reescribe nunca.
* **Lectura tolerante:** las líneas dañadas se cuentan y se ignoran; nunca lanzan.
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import json
import os
import re
from pathlib import Path
from typing import Any

from dashboard.api_base import Ctx
from dashboard.archivos import preparar_destino
from dashboard.seguridad import ErrorHttp
from scripts.robots.catalogo import RESULTADOS, VERSION
from scripts.robots.nucleo import REL_ROBOTS, ErrorRobot, iso_z, parsear_z, sin_float

__all__ = ["REL_ESTADO", "REL_LATIDOS", "SCHEMA_LATIDO", "anexar", "construir_latido", "id_latido", "leer"]

SCHEMA_LATIDO = "1.0.0"
REL_LATIDOS = f"{REL_ROBOTS}/latidos.jsonl"
REL_ESTADO = f"{REL_ROBOTS}/estado.json"
TOPE_ARCHIVO = 64 * 1024 * 1024         # ≈ 2 años a ~250 latidos por día; al llegar, la escritura falla y el ejecutor lo dice (sin rotación: ver límites)
_COLA_BUSQUEDA = 256 * 1024             # el id repetido solo puede estar en el final (los ids avanzan con el reloj)
_RX_ID = re.compile(r"^LAT-[0-9]{8}T[0-9]{6}Z-[a-z0-9_]{1,24}$")
ORIGENES = ("manual", "programado")


def id_latido(robot: str, inicio: _dt.datetime) -> str:
    return f"LAT-{inicio.astimezone(_dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{robot}"


def construir_latido(robot: str, inicio: _dt.datetime, duracion_ms: int, resultado: str, razon: str, *, origen: str = "manual",
                     salidas: list[str] | None = None, metricas: dict[str, int] | None = None) -> dict[str, Any]:
    if resultado not in RESULTADOS:
        raise ErrorRobot(f"resultado desconocido: {resultado!r}")
    if origen not in ORIGENES:
        raise ErrorRobot(f"origen desconocido: {origen!r}")
    duracion_ms = max(0, int(duracion_ms))
    fin = inicio + _dt.timedelta(milliseconds=duracion_ms)
    linea: dict[str, Any] = {
        "schema_version": SCHEMA_LATIDO, "id": id_latido(robot, inicio), "robot": robot, "inicio": iso_z(inicio), "fin": iso_z(fin),
        "duracion_ms": duracion_ms, "resultado": resultado, "razon": " ".join(str(razon).split())[:300], "modo": "sombra", "origen": origen,
        "ejecutor": "sombra-S-C", "version": VERSION, "salidas": list(salidas or []),
    }
    if metricas:
        linea["metricas"] = {str(k): int(v) for k, v in metricas.items() if isinstance(v, int) and not isinstance(v, bool)}
    if sin_float(linea):
        raise ErrorRobot("el latido lleva números decimales")
    return linea


def anexar(raiz: Path, latido: dict[str, Any]) -> bool:
    """Agrega UNA línea al final. ``True`` si la agregó, ``False`` si ya existía una con el mismo ``id`` (idempotente)."""
    if not _RX_ID.match(str(latido.get("id", ""))):
        raise ErrorRobot("id de latido inválido")
    texto = (json.dumps(latido, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    try:
        destino = preparar_destino(raiz, REL_LATIDOS)
        fd = os.open(destino, os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), 0o644)
    except (ErrorHttp, OSError) as exc:
        raise ErrorRobot(f"no se pudo abrir {REL_LATIDOS}: {getattr(exc, 'mensaje', None) or type(exc).__name__}") from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            tamano = os.fstat(fd).st_size
            if tamano + len(texto) > TOPE_ARCHIVO:
                raise ErrorRobot(f"{REL_LATIDOS} está lleno ({TOPE_ARCHIVO // (1024 * 1024)} MB): hay que archivarlo")
            inicio = max(0, tamano - _COLA_BUSQUEDA)
            cola = os.pread(fd, tamano - inicio, inicio) if tamano else b""
            if f'"id":"{latido["id"]}"'.encode() in cola:
                return False
            if tamano and not cola.endswith(b"\n") and tamano - inicio == len(cola):
                texto = b"\n" + texto                      # el archivo quedó a medias en una escritura anterior: no pegar dos líneas
            if os.write(fd, texto) != len(texto):
                raise ErrorRobot(f"escritura incompleta en {REL_LATIDOS}")
            os.fsync(fd)
            return True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def leer(ctx: Ctx, maximo: int = 5000) -> tuple[list[dict[str, Any]], list[str]]:
    """``(latidos válidos en orden de inicio, avisos)``. Lee como mucho los últimos ``maximo`` renglones. Nunca lanza."""
    lec = ctx.raiz_confinada.jsonl_cola(REL_LATIDOS, maximo=maximo, ventana=4 * 1024 * 1024)
    if lec.estado == "ausente":
        return [], []
    avisos = list(lec.avisos)
    if lec.estado != "ok":
        return [], avisos or [f"No se pudo leer {REL_LATIDOS}."]
    validos: list[dict[str, Any]] = []
    malos = 0
    for _n, obj, _crudo in lec.lineas:
        if (isinstance(obj, dict) and isinstance(obj.get("robot"), str) and parsear_z(obj.get("inicio")) is not None
                and obj.get("resultado") in RESULTADOS):
            validos.append(obj)
        else:
            malos += 1
    if malos:
        avisos.append(f"{REL_LATIDOS}: {malos} línea(s) dañadas o con otro formato; se ignoran.")
    validos.sort(key=lambda x: (str(x["inicio"]), str(x.get("id", ""))))
    return validos, avisos
