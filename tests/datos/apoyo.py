"""Ayudas compartidas por las pruebas de `datos` (B3): sin red, con una base de datos sqlite propia."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from datos.db import Conexion, conectar, migrar

RAIZ_REPO = Path(__file__).resolve().parents[2]
# "reales/" (tests/fixtures/{meta,datos}/reales/) es de I1 (captura real, B0-24); estas son de forma
# real pero sintéticas, al nivel de tests/fixtures/datos/ (ver README de esa carpeta).
FIXTURES_DATOS = RAIZ_REPO / "tests" / "fixtures" / "datos"
OFERTA = "OF-202611-01"


class PruebaBase(unittest.TestCase):
    """Bloquea ``socket.socket`` (convenciones §11) y da una carpeta temporal y una conexión sqlite por prueba."""

    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red: socket.socket está bloqueado"))
        parche.start()
        self.addCleanup(parche.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="fabrica-datos-prueba-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def conexion(self) -> Conexion:
        """Nueva conexión sqlite con las migraciones aplicadas; se cierra sola al terminar la prueba."""
        conn = conectar(f"sqlite:///{self.tmp}/fabrica.db")
        self.addCleanup(conn.cerrar)
        migrar(conn)
        return conn


def reloj_fijo(momento: datetime) -> Callable[[], datetime]:
    """Reloj inyectable que siempre devuelve ``momento`` (debe traer zona UTC)."""
    def _ahora() -> datetime:
        return momento
    return _ahora


UTC = timezone.utc
