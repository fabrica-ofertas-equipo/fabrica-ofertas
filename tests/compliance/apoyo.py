"""Ayudas compartidas por las pruebas de ``compliance`` (B6).

``PruebaBase`` bloquea ``socket.socket`` (convenciones §11: ninguna prueba abre un socket real) y da
una carpeta temporal propia. ``escribir_regla_alterada`` fabrica una copia de
``reglas_sensibles.yaml`` con un patrón de más SIN recalcular ``hash_contenido`` (el caso adversarial
de "reglas alteradas: el lint no corre").
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import yaml

from compliance.reglas import RUTA_POR_DEFECTO

RAIZ_REPO = Path(__file__).resolve().parents[2]


class PruebaBase(unittest.TestCase):
    """Base de las pruebas de ``compliance``: socket bloqueado y carpeta temporal propia."""

    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red: socket.socket está bloqueado"))
        parche.start()
        self.addCleanup(parche.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="compliance-prueba-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


def escribir_regla_alterada(destino: Path, *, mutar: Any = None) -> Path:
    """Copia ``reglas_sensibles.yaml`` a ``destino`` con un patrón nuevo pero el ``hash_contenido`` VIEJO.

    Simula a alguien editando una regla a mano sin recalcular el autosellado (``compliance.reglas
    .resellar``): ``cargar_reglas`` debe rechazar el archivo resultante.
    """
    with RUTA_POR_DEFECTO.open("r", encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    if mutar is None:
        datos["generales"]["urgencia_falsa"]["rojo"].append(r"\bnuevo patron sin resellar\b")
    else:
        mutar(datos)
    destino.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return destino
