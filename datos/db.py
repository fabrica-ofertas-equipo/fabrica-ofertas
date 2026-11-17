"""Capa de acceso a datos: conexión portable y migraciones (docs/06 §4.4).

`conectar(url)` acepta ``sqlite:///<ruta>`` (incluido ``sqlite:///:memory:``) y ``postgresql://...``.
El SQL de las migraciones y de este módulo se escribe UNA vez con marcadores de posición ``?``
(estilo ``sqlite3``); :func:`traducir_marcadores` los convierte a ``%s`` para PostgreSQL, así el
mismo texto sirve para los dos motores (criterio de aceptación B3: «SQLite con marcador traducido»).

Hoy solo ``sqlite`` ejecuta de verdad: no hay controlador de PostgreSQL en la biblioteca estándar y
esta sesión no puede instalar paquetes (reglas de la noche). Un componente que lo necesite declara
``psycopg2`` en ``datos/requirements-extra.txt`` (convenciones §13); hasta entonces, ``postgresql://``
se reconoce y falla cerrado con ``ErrorExterno`` en vez de fingir una conexión.
"""
from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from engine import comun
from engine.errores import ErrorExterno, ErrorUso, ErrorValidacion

__all__ = ["Conexion", "conectar", "migrar", "migraciones_aplicadas", "traducir_marcadores"]

_DIR_MIGRACIONES = Path(__file__).resolve().parent / "migraciones"
_RX_SQLITE_URL = re.compile(r"^sqlite:///(.*)$")
_RX_PG_URL = re.compile(r"^postgres(?:ql)?://")
_RX_IDENTIFICADOR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def traducir_marcadores(sql: str, dialecto: str) -> str:
    """Traduce los marcadores ``?`` (estilo sqlite) a ``%s`` (estilo psycopg2) para ``postgresql``.

    No toca signos de interrogación dentro de literales de cadena delimitados por comillas simples.
    Con ``dialecto == "sqlite"`` devuelve ``sql`` sin cambios. Errores: ``ErrorUso`` si el dialecto
    no es uno de los dos soportados.
    """
    if dialecto == "sqlite":
        return sql
    if dialecto != "postgresql":
        raise ErrorUso(f"dialecto de base de datos desconocido: {dialecto!r}")
    partes: list[str] = []
    dentro_cadena = False
    for caracter in sql:
        if caracter == "'":
            dentro_cadena = not dentro_cadena
            partes.append(caracter)
        elif caracter == "?" and not dentro_cadena:
            partes.append("%s")
        else:
            partes.append(caracter)
    return "".join(partes)


def _exigir_identificador(nombre: str, contexto: str) -> str:
    if not isinstance(nombre, str) or not _RX_IDENTIFICADOR.match(nombre):
        raise ErrorValidacion(f"{contexto}: identificador SQL inválido: {nombre!r}")
    return nombre


@dataclass
class Conexion:
    """Conexión portable: envuelve el controlador real y traduce los marcadores según el dialecto."""

    cruda: Any
    dialecto: str
    url: str

    def ejecutar(self, sql: str, parametros: Sequence[Any] = ()) -> Any:
        """Ejecuta UNA sentencia con marcadores ``?`` (traducidos si hace falta) y devuelve el cursor."""
        cursor = self.cruda.cursor()
        cursor.execute(traducir_marcadores(sql, self.dialecto), tuple(parametros))
        return cursor

    def ejecutar_muchos(self, sql: str, filas: Iterable[Sequence[Any]]) -> None:
        """``executemany`` con marcadores traducidos."""
        cursor = self.cruda.cursor()
        cursor.executemany(traducir_marcadores(sql, self.dialecto), [tuple(f) for f in filas])

    def upsert(self, tabla: str, clave: Sequence[str], valores: Mapping[str, Any]) -> None:
        """Inserta ``valores`` o actualiza la fila existente con la misma ``clave`` (clave natural).

        Usa ``INSERT ... ON CONFLICT (clave) DO UPDATE``, sintaxis portable entre SQLite (>= 3.24) y
        PostgreSQL. Reaplicar el mismo ``valores`` deja la fila idéntica (idempotente, convenciones §7).
        """
        _exigir_identificador(tabla, "upsert")
        columnas = list(valores.keys())
        if not columnas:
            raise ErrorValidacion("upsert exige al menos una columna")
        for c in (*columnas, *clave):
            _exigir_identificador(c, "upsert")
        no_clave = [c for c in columnas if c not in set(clave)]
        marcadores = ", ".join("?" for _ in columnas)
        asignacion = ", ".join(f"{c} = excluded.{c}" for c in no_clave) or f"{clave[0]} = excluded.{clave[0]}"
        sql = (f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({marcadores}) "
               f"ON CONFLICT ({', '.join(clave)}) DO UPDATE SET {asignacion}")
        self.ejecutar(sql, [valores[c] for c in columnas])

    def commit(self) -> None:
        self.cruda.commit()

    def cerrar(self) -> None:
        self.cruda.close()

    def __enter__(self) -> "Conexion":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.cerrar()


def conectar(url: str) -> Conexion:
    """Abre una conexión portable a partir de una URL ``sqlite:///...`` o ``postgresql://...``.

    Errores: ``ErrorUso`` si la URL no tiene una forma reconocida; ``ErrorExterno`` (6) si es
    ``postgresql://`` y no hay controlador instalado (sin red ni paquetes nuevos esta sesión).
    """
    if not isinstance(url, str) or not url:
        raise ErrorUso("conectar exige una URL de base de datos (sqlite:/// o postgresql://)")
    coincide = _RX_SQLITE_URL.match(url)
    if coincide:
        ruta = coincide.group(1) or ":memory:"
        if ruta != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        cruda = sqlite3.connect(ruta)
        cruda.row_factory = sqlite3.Row  # filas indexables por posición y por nombre de columna
        cruda.execute("PRAGMA foreign_keys = ON")
        return Conexion(cruda, "sqlite", url)
    if _RX_PG_URL.match(url):
        raise ErrorExterno(
            "sin controlador de PostgreSQL en este entorno: declarar psycopg2 en "
            "datos/requirements-extra.txt y correr scripts/bootstrap.sh; usar sqlite:/// en pruebas y dry-run"
        )
    raise ErrorUso(f"URL de base de datos no reconocida: {url!r} (se espera sqlite:/// o postgresql://)")


def _dividir_sentencias(sql: str) -> list[str]:
    """Divide un script en sentencias por ``;`` de fin de línea, ignorando líneas de comentario ``--``."""
    sin_comentarios = "\n".join(linea for linea in sql.splitlines() if not linea.strip().startswith("--"))
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


def migraciones_aplicadas(conn: Conexion) -> list[str]:
    """Nombres de los archivos de migración ya aplicados (``[]`` si la tabla de control no existe aún)."""
    conn.ejecutar("CREATE TABLE IF NOT EXISTS _migraciones (nombre TEXT PRIMARY KEY, aplicada_en TEXT NOT NULL)")
    conn.commit()
    return sorted(fila[0] for fila in conn.ejecutar("SELECT nombre FROM _migraciones").fetchall())


def migrar(conn: Conexion, dir_migraciones: Path | None = None, *,
           ahora: Callable[[], datetime] = comun.ahora_utc) -> list[str]:
    """Aplica, en orden y una sola vez, los ``NNNN_*.sql`` de ``dir_migraciones``. Devuelve los nuevos.

    Idempotente: reaplicar no repite nada (se registra en ``_migraciones``). El reloj es inyectable
    (convenciones §4); solo se usa para la marca de tiempo de control, nunca para decidir qué aplicar.
    """
    carpeta = dir_migraciones or _DIR_MIGRACIONES
    ya_aplicadas = set(migraciones_aplicadas(conn))
    nuevas: list[str] = []
    for ruta in sorted(carpeta.glob("*.sql")):
        if ruta.name in ya_aplicadas:
            continue
        for sentencia in _dividir_sentencias(ruta.read_text(encoding="utf-8")):
            conn.ejecutar(sentencia)
        conn.ejecutar("INSERT INTO _migraciones (nombre, aplicada_en) VALUES (?, ?)",
                      (ruta.name, comun.iso_z(comun.instante(ahora))))
        conn.commit()
        nuevas.append(ruta.name)
    return nuevas
