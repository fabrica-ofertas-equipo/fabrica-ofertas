"""Apoyo común de las pruebas del Cerebro: carga de los scripts de las skills (rutas con guion), raíces temporales y un gancho que detecta ESCRITURAS del proceso.

El gancho (``sys.addaudithook``) permite probar «solo lectura» contra el repositorio REAL aunque otros agentes escriban a la vez en él: comparar el árbol antes y después
fallaría por lo que hacen ellos, no por este código. Registra todo ``open`` para escribir y las operaciones que cambian el sistema de archivos de ESTE proceso.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

RAIZ = Path(__file__).resolve().parents[2]
SKILLS = RAIZ / ".claude" / "skills"
AHORA = dt.datetime(2026, 11, 9, 12, 0, 0, tzinfo=dt.timezone.utc)
AHORA_TXT = "2026-11-09T12:00:00Z"

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def cargar(nombre: str, ruta: Path) -> Any:
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


gp = cargar("cerebro_guardar_pendiente", SKILLS / "cerebro-cerrar" / "scripts" / "guardar_pendiente.py")
ra = cargar("cerebro_resumen_abrir", SKILLS / "cerebro-abrir" / "scripts" / "resumen_abrir.py")
from scripts.cerebro import buscar, comun, jardinero, preferencias  # noqa: E402

SCRIPT_GP = SKILLS / "cerebro-cerrar" / "scripts" / "guardar_pendiente.py"
SCRIPT_RA = SKILLS / "cerebro-abrir" / "scripts" / "resumen_abrir.py"

# ── gancho de escrituras ─────────────────────────────────────────────────────────────────────────────
_ACTIVOS: list[list[tuple]] = []
_OPERACIONES = {"os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.truncate", "os.chmod", "os.chown", "shutil.rmtree", "shutil.copyfile", "shutil.move", "os.symlink", "os.link", "os.utime"}


def _gancho(evento: str, args: tuple) -> None:
    if not _ACTIVOS:
        return
    if evento == "open":
        _ruta, modo, banderas = args
        escribe = (isinstance(banderas, int) and banderas & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC)) or (isinstance(modo, str) and any(c in modo for c in "wax+"))
        if escribe:
            for lista in _ACTIVOS:
                lista.append((evento, args))
    elif evento in _OPERACIONES:
        for lista in _ACTIVOS:
            lista.append((evento, args))


sys.addaudithook(_gancho)


@contextmanager
def sin_escrituras() -> Iterator[list[tuple]]:
    """Dentro del bloque se anotan las escrituras de este proceso; la prueba comprueba que la lista quedó vacía."""
    eventos: list[tuple] = []
    _ACTIVOS.append(eventos)
    try:
        yield eventos
    finally:
        _ACTIVOS.remove(eventos)


# ── raíces temporales ────────────────────────────────────────────────────────────────────────────────
def alta(n: int, **extra: Any) -> dict[str, Any]:
    return {"id": f"PUL-{n:04d}", "ts": "2026-11-08T10:00:00Z", "autor": "dueno", "evento": "alta", "oferta_id": None, "etapa": "O0", "titulo": f"pendiente {n}", "detalle": "",
            "severidad": "media", "tipo": "pendiente", "estado": "abierta", **extra}


def cambio(n: int, estado: str) -> dict[str, Any]:
    return {"id": f"PUL-{n:04d}", "ts": "2026-11-08T11:00:00Z", "autor": "dueno", "evento": "estado", "estado": estado}


def jsonl(*lineas: dict[str, Any]) -> str:
    return "".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lineas)


class Base(unittest.TestCase):
    """Una raíz temporal con la forma mínima de un repositorio (empresa/, dashboard/ vacío) y ayudas para poblarla."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cerebro-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.raiz = self.tmp / "repo"
        (self.raiz / "empresa" / "panel").mkdir(parents=True)
        (self.raiz / "dashboard").mkdir()
        self.pulido = self.raiz / "empresa" / "panel" / "pulido.jsonl"
        self.memoria = self.raiz / "empresa" / "memoria"

    def poner(self, rel: str, contenido: str | bytes) -> Path:
        p = self.raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(contenido if isinstance(contenido, bytes) else contenido.encode("utf-8"))
        return p

    def lineas(self, rel: str) -> list[dict[str, Any]]:
        return [json.loads(l) for l in (self.raiz / rel).read_text(encoding="utf-8").splitlines() if l.strip()]

    @staticmethod
    def arbol(carpeta: Path) -> dict[str, str]:
        salida = {}
        for d, _, fs in os.walk(carpeta):
            for f in fs:
                p = Path(d) / f
                salida[str(p.relative_to(carpeta))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return salida
