"""Núcleo común de los robots en sombra: contexto de ejecución, resultado y escritura atómica confinada.

Garantías (probadas en ``tests/robots``): sin red, sin claves, sin ``.env``; la base se abre en ``mode=ro``; lo único que se escribe cuando
``Contexto.escribir`` es verdadero son archivos bajo ``empresa/robots/`` (y ``empresa/datos/alertas.jsonl`` por el robot de alertas).
Por defecto NO se escribe nada.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import json
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

from dashboard.api_base import Ctx
from dashboard.archivos import preparar_destino
from dashboard.seguridad import ErrorHttp
from scripts.alertas.hechos import iso_z, leer_hechos, param, parsear_z

__all__ = ["Contexto", "ErrorRobot", "RAIZ_REPO", "REL_ROBOTS", "RX_OFERTA_REAL", "Resultado", "ahora_utc", "escribir_atomico", "fecha_de", "json_estable", "sin_float"]

RAIZ_REPO = Path(__file__).resolve().parent.parent.parent
REL_ROBOTS = "empresa/robots"
RX_OFERTA_REAL = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class ErrorRobot(Exception):
    """Falla propia de un robot (instalación rota, argumento imposible). El ejecutor la registra como ``error`` y sigue con los demás."""


@dataclass
class Resultado:
    """Lo que devuelve un robot. ``estado`` ∈ ``catalogo.RESULTADOS`` (menos ``error``, que lo fija el ejecutor)."""

    estado: str
    razon: str
    resumen: list[str] = field(default_factory=list)       # líneas legibles (plantilla fija, sin texto libre de terceros)
    datos: dict[str, Any] = field(default_factory=dict)    # el producto del robot, JSON sin float
    metricas: dict[str, int] = field(default_factory=dict)  # enteros que viajan en el latido (p. ej. acierto_bp del auditor)
    salidas: list[str] = field(default_factory=list)       # rutas relativas escritas (solo con --escribir)


def ahora_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def fecha_de(t: _dt.datetime) -> str:
    return t.astimezone(_dt.timezone.utc).strftime("%Y-%m-%d")


def sin_float(valor: Any, ruta: str = "$") -> list[str]:
    """Rutas de todo ``float`` dentro de un documento (debe ser una lista vacía en lo que se persiste)."""
    if isinstance(valor, float):
        return [ruta]
    if isinstance(valor, dict):
        return [r for k, v in valor.items() for r in sin_float(v, f"{ruta}.{k}")]
    if isinstance(valor, (list, tuple)):
        return [r for i, v in enumerate(valor) for r in sin_float(v, f"{ruta}[{i}]")]
    return []


def json_estable(doc: Any) -> str:
    """JSON legible y estable (claves ordenadas), con fin de línea; rechaza NaN/Infinity."""
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def escribir_atomico(raiz: Path, rel: str, texto: str) -> bool:
    """Escribe ``rel`` bajo ``raiz`` de forma atómica (archivo temporal + ``os.replace``). ``False`` si ya tenía exactamente ese contenido.

    La ruta se valida con ``preparar_destino`` (sin enlaces simbólicos que escapen de la raíz).
    """
    destino = preparar_destino(raiz, rel)
    try:
        if destino.is_file() and destino.read_text(encoding="utf-8") == texto:
            return False
    except (OSError, UnicodeDecodeError):
        pass
    fd, tmp = tempfile.mkstemp(prefix=f".{destino.name}.", suffix=".tmp", dir=str(destino.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, destino)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return True


class Contexto:
    """Todo lo que un robot necesita: raíz del proyecto, reloj, base en solo lectura y (si ``escribir``) dónde guardar su producto."""

    def __init__(self, raiz: Path, ahora: _dt.datetime | None = None, *, escribir: bool = False, db: Path | None = None, fecha: str | None = None,
                 umbrales: Path | None = None, repo: Path = RAIZ_REPO) -> None:
        self.raiz = Path(os.path.realpath(raiz))
        self._ahora_fija = ahora
        self.escribir = bool(escribir)
        self.db = Path(db) if db is not None else self.raiz / "empresa" / "datos" / "fabrica.db"
        if fecha is not None and not _RX_FECHA.match(fecha):
            raise ErrorRobot("la fecha debe verse así: 2026-11-06")
        self.fecha_pedida = fecha
        self.umbrales_archivo = Path(umbrales) if umbrales is not None else None
        self.repo = Path(repo)
        self._ctx: Ctx | None = None
        self._hechos: dict[str, Any] | None = None
        self._parametros: Any = None
        self._parametros_leidos = False

    # ── reloj ──
    @property
    def reloj_fijo(self) -> bool:
        return self._ahora_fija is not None

    def ahora(self) -> _dt.datetime:
        """El instante de la corrida: el fijado con ``--ahora`` o el reloj real (segundos)."""
        return self._ahora_fija if self._ahora_fija is not None else ahora_utc()

    @property
    def fecha_cuenta(self) -> str:
        """Día que se evalúa: el pedido con ``--fecha`` o AYER (UTC), el último día cerrado."""
        return self.fecha_pedida or fecha_de(self.ahora() - _dt.timedelta(days=1))

    # ── lectura del proyecto ──
    def ctx(self) -> Ctx:
        if self._ctx is None:
            fijo = self._ahora_fija
            self._ctx = Ctx(self.raiz, ahora=(lambda: fijo) if fijo is not None else ahora_utc)
        return self._ctx

    def hechos(self) -> dict[str, Any]:
        """Los hechos del semáforo (una sola lectura por corrida). Nunca lanza."""
        if self._hechos is None:
            self._hechos = leer_hechos(self.ctx(), fecha_ventas=self.fecha_pedida)
        return self._hechos

    def parametros(self) -> Any:
        """``empresa/parametros.yaml`` ya cargado (o ``None``)."""
        if not self._parametros_leidos:
            lec = self.ctx().empresa().yaml("parametros.yaml")
            self._parametros = lec.dato if lec.ok else None
            self._parametros_leidos = True
        return self._parametros

    def parametro(self, grupo: str, clave: str) -> Any:
        return param(self.parametros(), grupo, clave)

    @contextlib.contextmanager
    def abrir_db(self) -> Iterator[sqlite3.Connection | None]:
        """La base en SOLO LECTURA (URI ``mode=ro`` + ``query_only``), o ``None`` si no existe. Cualquier escritura falla."""
        if not self.db.is_file():
            yield None
            return
        # URI armada a mano: Path.as_uri() importa urllib.request (y con él http y socket) y los robots no deben cargar nada de red.
        conn = sqlite3.connect(f"file:{quote(str(self.db.resolve()), safe='/')}?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA query_only = ON")
            yield conn
        finally:
            conn.close()

    # ── escritura (solo con --escribir) ──
    def guardar(self, robot: str, doc: Any, nombre: str | None = None) -> str | None:
        """Guarda el producto del robot en ``empresa/robots/salidas/<robot>/<fecha>.json`` si ``escribir``; devuelve la ruta relativa o ``None``."""
        if not self.escribir:
            return None
        rel = f"{REL_ROBOTS}/salidas/{robot}/{nombre or fecha_de(self.ahora())}.json"
        malos = sin_float(doc)
        if malos:
            raise ErrorRobot(f"el producto de {robot} lleva números decimales ({malos[:2]}); no se guarda")
        try:
            escribir_atomico(self.raiz, rel, json_estable(doc))
        except (ErrorHttp, OSError) as exc:
            raise ErrorRobot(f"no se pudo guardar {rel}: {getattr(exc, 'mensaje', None) or type(exc).__name__}") from exc
        return rel


def tabla_existe(conn: sqlite3.Connection, nombre: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (nombre,)).fetchone() is not None


def ofertas_en_base(conn: sqlite3.Connection) -> list[str]:
    """Ids de oferta reales (``OF-AAAAMM-NN``) con anuncios o gasto en la base, ordenados."""
    ids: set[str] = set()
    for tabla in ("dim_anuncio", "fact_meta_ad_dia"):
        if tabla_existe(conn, tabla):
            ids.update(str(f[0]) for f in conn.execute(f"SELECT DISTINCT oferta_id FROM {tabla}"))  # noqa: S608 - nombre de tabla fijo
    return sorted(i for i in ids if RX_OFERTA_REAL.match(i))


__all__ += ["ofertas_en_base", "tabla_existe", "parsear_z", "iso_z"]
