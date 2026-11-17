"""Almacén SQLite de ``postcompra.reembolsar``: reserva atómica e idempotente por ``session_id``.

Implementa el paso (a) del algoritmo de ``docs/06-bases-del-testeo.md`` §4.8: una transacción
``BEGIN IMMEDIATE`` inserta la fila con ``UNIQUE(session_id)`` y cuenta cuántos reembolsos del DÍA
(UTC) ya están ``reservado`` o ``ejecutado`` antes de aceptar uno más. Cada operación abre su PROPIA
conexión SQLite (una conexión no se comparte entre hilos: el candado que serializa a los escritores es
el de ARCHIVO de SQLite, no un `Lock` de Python), así que dos llamadas concurrentes —de dos hilos o de
dos procesos— para el MISMO ``session_id`` nunca reservan las dos: la segunda espera el candado,
después encuentra la fila que dejó la primera y no inserta nada.

Este archivo es propio de ``postcompra`` (no es el almacén del motor, D-21): vive bajo
``ofertas/<id>/10-postcompra/reembolsos.db`` y solo conoce la idempotencia de esta operación.
``reembolsos.jsonl`` (el artefacto de ``docs/contratos.md``) sigue siendo la fuente de verdad legible
para humanos; esta base solo sirve para la carrera entre hilos/procesos.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from engine.errores import ErrorExterno, ErrorLimite, ErrorValidacion

__all__ = ["AlmacenReembolsos", "Reserva"]

_ESTADOS_CUENTAN = ("reservado", "ejecutado")
_ESTADOS_TERMINALES = ("ejecutado", "rechazado")
_ESPERA_INICIAL_S = 0.01
_ESPERA_MAXIMA_S = 1.0
_FACTOR_ESPERA = 2
_TIMEOUT_SQLITE_S = 30
_REINTENTOS_INIT = 20

_DDL = """
CREATE TABLE IF NOT EXISTS reembolsos (
    session_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    dia_utc TEXT NOT NULL,
    estado TEXT NOT NULL,
    monto_minor INTEGER,
    moneda TEXT,
    refund_id TEXT,
    motivo_rechazo TEXT,
    idempotency_key TEXT,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reembolsos_dia ON reembolsos(dia_utc, estado);
"""

_COLUMNAS = ("session_id", "oferta_id", "dia_utc", "estado", "monto_minor", "moneda", "refund_id", "motivo_rechazo",
            "idempotency_key", "creado_en", "actualizado_en")


@dataclass(frozen=True)
class Reserva:
    """Resultado de :meth:`AlmacenReembolsos.intentar_reservar`.

    ``ganador``: ``True`` si ESTA llamada creó la fila (debe ejecutar el reembolso). ``fila``: la fila
    existente cuando ``ganador`` es ``False`` (``None`` si ``ganador`` es ``True``, la fila recién creada
    no tiene todavía resultado).
    """

    ganador: bool
    fila: dict[str, Any] | None


class AlmacenReembolsos:
    """``reembolsos.db`` de una oferta. Crea el archivo y la tabla si faltan (en el primer uso)."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        # Dos AlmacenReembolsos(...) concurrentes (dos llamadas a reembolsar() en hilos distintos)
        # pueden chocar aquí: PRAGMA journal_mode y CREATE TABLE piden un candado especial que el
        # busy_timeout normal no cubre tan bien como BEGIN/INSERT/UPDATE. Reintenta unas pocas veces
        # con espera corta antes de darse por vencido (una sola vez por archivo, en el arranque).
        ultimo_error: sqlite3.OperationalError | None = None
        for _ in range(_REINTENTOS_INIT):
            conn = sqlite3.connect(str(self.ruta), timeout=_TIMEOUT_SQLITE_S, isolation_level=None)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(_DDL)
                return
            except sqlite3.OperationalError as exc:
                ultimo_error = exc
                time.sleep(_ESPERA_INICIAL_S)
            finally:
                conn.close()
        raise ErrorExterno(f"no se pudo inicializar {self.ruta.name}: {ultimo_error}")

    def cerrar(self) -> None:
        """No hay nada que cerrar (cada operación abre y cierra su propia conexión); existe por simetría."""
        return None

    def __enter__(self) -> "AlmacenReembolsos":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.cerrar()

    @contextmanager
    def _conectar(self) -> Iterator[sqlite3.Connection]:
        """Una conexión NUEVA, cerrada al salir. Nunca se comparte entre hilos (eso es lo que rompía
        ``BEGIN``/``COMMIT`` cuando dos hilos usaban la misma conexión: el estado de transacción de
        ``sqlite3`` es por conexión, no por hilo que la usa)."""
        conn = sqlite3.connect(str(self.ruta), timeout=_TIMEOUT_SQLITE_S, isolation_level=None)
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _a_fila(cur: sqlite3.Cursor, cruda: tuple) -> dict[str, Any]:
        return dict(zip((d[0] for d in cur.description), cruda))

    def _fila_en(self, conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
        cur = conn.execute(f"SELECT {', '.join(_COLUMNAS)} FROM reembolsos WHERE session_id = ?", (session_id,))
        cruda = cur.fetchone()
        return None if cruda is None else self._a_fila(cur, cruda)

    def _reservar(self, session_id: str, oferta_id: str, dia_utc: str, ahora_iso: str, *, tope_dia: int | None) -> Reserva:
        with self._conectar() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existente = self._fila_en(conn, session_id)
                if existente is not None:
                    conn.execute("COMMIT")
                    return Reserva(ganador=False, fila=existente)
                if tope_dia is not None:
                    conteo = conn.execute(
                        "SELECT COUNT(*) FROM reembolsos WHERE dia_utc = ? AND estado IN (?, ?)",
                        (dia_utc, *_ESTADOS_CUENTAN),
                    ).fetchone()[0]
                    if conteo >= tope_dia:
                        conn.execute("ROLLBACK")
                        raise ErrorLimite(
                            f"reembolsos_auto_max_por_dia: ya hay {conteo} reembolsos reservados o ejecutados hoy (tope {tope_dia})",
                            detalle={"clave": "reembolsos_auto_max_por_dia", "dia_utc": dia_utc, "conteo": conteo, "tope": tope_dia},
                        )
                conn.execute(
                    "INSERT INTO reembolsos(session_id, oferta_id, dia_utc, estado, creado_en, actualizado_en) "
                    "VALUES (?, ?, ?, 'reservado', ?, ?)",
                    (session_id, oferta_id, dia_utc, ahora_iso, ahora_iso),
                )
                conn.execute("COMMIT")
                return Reserva(ganador=True, fila=None)
            except BaseException:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass  # no había transacción abierta (ya se hizo COMMIT/ROLLBACK arriba)
                raise

    def intentar_reservar(self, session_id: str, oferta_id: str, dia_utc: str, tope_dia: int, ahora_iso: str) -> Reserva:
        """Reserva atómicamente ``session_id`` para hoy, o devuelve la fila existente.

        Errores: ``ErrorLimite`` si NO existe fila para ``session_id`` y el conteo del día ya alcanzó
        ``tope_dia`` (``reembolsos_auto_max_por_dia``); en ese caso no se inserta nada.
        """
        if isinstance(tope_dia, bool) or not isinstance(tope_dia, int) or tope_dia < 1:
            raise ErrorValidacion("tope_dia debe ser un entero positivo")
        return self._reservar(session_id, oferta_id, dia_utc, ahora_iso, tope_dia=tope_dia)

    def reservar_sin_tope(self, session_id: str, oferta_id: str, dia_utc: str, ahora_iso: str) -> Reserva:
        """Como :meth:`intentar_reservar` pero SIN comprobar el tope diario (lo usa ``reembolso_manual``:
        las aprobaciones humanas no están sujetas a ``reembolsos_auto_max_por_dia``, solo a que dos
        intentos para el MISMO ``session_id`` no reembolsen dos veces).
        """
        return self._reservar(session_id, oferta_id, dia_utc, ahora_iso, tope_dia=None)

    def marcar_ejecutado(self, session_id: str, *, refund_id: str, monto_minor: int, moneda: str,
                         idempotency_key: str, actualizado_en: str) -> None:
        """Pasa la fila reservada a ``ejecutado`` con el resultado de Stripe (paso d del algoritmo)."""
        with self._conectar() as conn:
            conn.execute(
                "UPDATE reembolsos SET estado = 'ejecutado', refund_id = ?, monto_minor = ?, moneda = ?, "
                "idempotency_key = ?, actualizado_en = ? WHERE session_id = ?",
                (refund_id, monto_minor, moneda, idempotency_key, actualizado_en, session_id),
            )

    def marcar_rechazado(self, session_id: str, *, motivo_rechazo: str, actualizado_en: str) -> None:
        """Pasa la fila reservada a ``rechazado`` (fuera de garantía, disputa abierta, excede el tope…)."""
        with self._conectar() as conn:
            conn.execute(
                "UPDATE reembolsos SET estado = 'rechazado', motivo_rechazo = ?, actualizado_en = ? WHERE session_id = ?",
                (motivo_rechazo, actualizado_en, session_id),
            )

    def contar_dia(self, dia_utc: str) -> int:
        """Reembolsos ``reservado``/``ejecutado`` de ``dia_utc`` (solo lectura, para diagnóstico)."""
        with self._conectar() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM reembolsos WHERE dia_utc = ? AND estado IN (?, ?)", (dia_utc, *_ESTADOS_CUENTAN),
            ).fetchone()[0])

    def esperar_resultado(self, session_id: str, *, intentos: int = 200,
                          dormir: Callable[[float], None] = time.sleep) -> dict[str, Any]:
        """Espera (reintentos acotados, espera exponencial) a que OTRO hilo/proceso termine su reserva.

        Solo se llama cuando :meth:`intentar_reservar` devolvió una fila en estado ``reservado`` (la
        ganadora de la carrera aún no terminó). ``dormir`` es inyectable: las pruebas pasan una función
        que no bloquea de verdad (p. ej. ``lambda s: None``), para no usar ``sleep`` real en el hilo de
        prueba que solo observa. Errores: ``ErrorExterno`` si se agotan los intentos sin ver un estado
        terminal (la otra parte murió sin terminar; no es un caso normal).
        """
        espera = _ESPERA_INICIAL_S
        for _ in range(intentos):
            with self._conectar() as conn:
                fila = self._fila_en(conn, session_id)
            if fila is not None and fila["estado"] in _ESTADOS_TERMINALES:
                return fila
            dormir(espera)
            espera = min(espera * _FACTOR_ESPERA, _ESPERA_MAXIMA_S)
        raise ErrorExterno(f"tiempo agotado esperando el resultado de {session_id} (otro proceso no terminó)")
