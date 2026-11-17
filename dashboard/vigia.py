"""Vigía de cambios y difusor de eventos para ``GET /api/eventos`` (SSE).

El vigía compara cada ``intervalo`` segundos (1 s por defecto) los ``mtime``/tamaños de lo observado:

* ``empresa/**`` (``tipo`` ``registro`` para ``registro.jsonl``/``costos.jsonl``/anclas, ``barrido`` para ``empresa/barrido/**``,
  ``empresa`` para el resto, incluido ``empresa/panel/**`` y ``empresa/PAUSA``);
* ``ofertas/**`` (``oferta``; incluye ``ofertas/*/estado.json``);
* ``.claude/skills/**`` y ``.claude/agents/**`` (``skills``).

Cada cambio produce ``{"tipo", "ruta", "ts", "accion"}`` (``accion`` ∈ creado|modificado|borrado). La primera
instantánea es la línea base: no genera eventos. El recorrido no sigue enlaces simbólicos y tiene un tope de archivos.
El :class:`Difusor` guarda los últimos eventos y deja a cada conexión SSE pedir «lo posterior al id N».
"""
from __future__ import annotations

import collections
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dashboard.api_base import ahora_utc
from dashboard.archivos import iso_z

__all__ = ["Difusor", "Vigia", "clasificar"]

TOPE_ARCHIVOS = 20000
MAX_EVENTOS_POR_SONDEO = 200
_OMITIR = frozenset({"__pycache__", "node_modules", ".git", ".DS_Store"})
_RAICES = (("empresa", 12), ("ofertas", 10), (".claude/skills", 8), (".claude/agents", 4))


def clasificar(ruta: str) -> str:
    """Tipo de evento (``empresa|oferta|registro|skills|barrido``) de una ruta relativa a la raíz."""
    if ruta.startswith(".claude/"):
        return "skills"
    if ruta.startswith("ofertas/"):
        return "oferta"
    if ruta in ("empresa/registro.jsonl", "empresa/costos.jsonl") or ruta.startswith("empresa/registro."):
        return "registro"
    if ruta.startswith("empresa/barrido/") or ruta == "empresa/barrido":
        return "barrido"
    return "empresa"


class Difusor:
    """Búfer circular de eventos con espera por condición (varias conexiones SSE lo comparten)."""

    def __init__(self, capacidad: int = 500) -> None:
        self._eventos: collections.deque[tuple[int, dict[str, Any]]] = collections.deque(maxlen=capacidad)
        self._ultimo = 0
        self._cond = threading.Condition()
        self._cerrado = False

    @property
    def ultimo_id(self) -> int:
        with self._cond:
            return self._ultimo

    def publicar(self, evento: dict[str, Any]) -> int:
        with self._cond:
            self._ultimo += 1
            self._eventos.append((self._ultimo, evento))
            self._cond.notify_all()
            return self._ultimo

    def esperar(self, desde: int, timeout: float) -> list[tuple[int, dict[str, Any]]]:
        """Eventos con id > ``desde``; espera hasta ``timeout`` s si no hay. ``[]`` al agotarse o al cerrar."""
        with self._cond:
            if not self._cerrado and self._ultimo <= desde:
                self._cond.wait(timeout)
            return [(i, e) for i, e in self._eventos if i > desde]

    def cerrar(self) -> None:
        with self._cond:
            self._cerrado = True
            self._cond.notify_all()

    @property
    def cerrado(self) -> bool:
        return self._cerrado


class Vigia:
    """Compara instantáneas de archivos y publica los cambios en un :class:`Difusor`."""

    def __init__(self, raiz: Path, difusor: Difusor, *, intervalo: float = 1.0,
                 ahora: Callable[[], Any] | None = None, tope_archivos: int = TOPE_ARCHIVOS) -> None:
        self.raiz = Path(os.path.realpath(raiz))
        self.difusor = difusor
        self.intervalo = intervalo
        self._ahora = ahora
        self._tope = tope_archivos
        self._previa: dict[str, tuple[int, int]] | None = None
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self.truncada = False
        self.archivos = 0

    # -- instantánea --------------------------------------------------------------------------
    def instantanea(self) -> dict[str, tuple[int, int]]:
        """``{ruta_relativa: (mtime_ns, tamaño)}`` de lo observado (sin seguir enlaces; con tope)."""
        salida: dict[str, tuple[int, int]] = {}
        self.truncada = False

        def _ir(carpeta: str, relativa: str, nivel: int, maximo: int) -> None:
            if nivel > maximo or len(salida) >= self._tope:
                self.truncada = self.truncada or len(salida) >= self._tope
                return
            try:
                with os.scandir(carpeta) as it:
                    entradas = list(it)
            except OSError:
                return
            for e in entradas:
                if e.name in _OMITIR or e.name.endswith(".tmp"):
                    continue
                rel = f"{relativa}/{e.name}" if relativa else e.name
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir(follow_symlinks=False):
                        _ir(e.path, rel, nivel + 1, maximo)
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        if len(salida) >= self._tope:
                            self.truncada = True
                            return
                        salida[rel] = (st.st_mtime_ns, st.st_size)
                except OSError:
                    continue

        for rel, maximo in _RAICES:
            base = self.raiz / rel
            if base.is_dir() and not base.is_symlink():
                _ir(str(base), rel, 0, maximo)
        self.archivos = len(salida)
        return salida

    def estado(self) -> dict[str, Any]:
        """Para ``/api/sistema``: ``{tope, archivos, truncada}``. ``truncada``: pasado el tope los archivos nuevos NO generan eventos."""
        return {"tope": self._tope, "archivos": self.archivos, "truncada": self.truncada}

    def sondear(self) -> list[dict[str, Any]]:
        """Una pasada: devuelve (y publica) los eventos de cambio respecto de la instantánea anterior."""
        actual = self.instantanea()
        previa, self._previa = self._previa, actual
        if previa is None:
            return []
        ts = iso_z((self._ahora or ahora_utc)())
        cambios: list[tuple[str, str]] = []
        for ruta, firma in actual.items():
            if ruta not in previa:
                cambios.append((ruta, "creado"))
            elif previa[ruta] != firma:
                cambios.append((ruta, "modificado"))
        cambios += [(ruta, "borrado") for ruta in previa if ruta not in actual]
        eventos: list[dict[str, Any]] = []
        if len(cambios) > MAX_EVENTOS_POR_SONDEO:
            tipos = sorted({clasificar(r) for r, _ in cambios})
            eventos = [{"tipo": t, "ruta": "", "ts": ts, "accion": "modificado"} for t in tipos]
        else:
            eventos = [{"tipo": clasificar(r), "ruta": r, "ts": ts, "accion": a} for r, a in sorted(cambios)]
        for ev in eventos:
            self.difusor.publicar(ev)
        return eventos

    # -- hilo ---------------------------------------------------------------------------------
    def iniciar(self) -> None:
        if self._hilo is not None:
            return
        self.sondear()  # línea base antes de aceptar clientes

        def _bucle() -> None:
            while not self._parar.wait(self.intervalo):
                try:
                    self.sondear()
                except Exception:  # noqa: BLE001 - el vigía no debe morir por un archivo que desaparece a mitad
                    time.sleep(self.intervalo)

        self._hilo = threading.Thread(target=_bucle, name="vigia", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        self.difusor.cerrar()
