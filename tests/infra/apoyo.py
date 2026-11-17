"""Ayudas compartidas por las pruebas de ``infra`` (B8).

No depende de fixtures de otros dueños: copia (bytes, sin reinterpretar) los ejemplos YA VÁLIDOS de
``contratos/ejemplos/`` (CT, solo lectura) a una raíz temporal propia. Así ``empresa/limites.yaml`` y
``empresa/parametros.yaml`` de las pruebas quedan siempre sincronizados con el esquema vigente sin
duplicar su contenido en ``tests/fixtures/infra/``.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONTRATOS_EJEMPLOS = RAIZ_REPO / "contratos" / "ejemplos"
FIXTURES = RAIZ_REPO / "tests" / "fixtures" / "infra"
CLAVE_PREFLIGHT_PRUEBA = b"clave-preflight-de-prueba-no-real"


class PruebaBase(unittest.TestCase):
    """Bloquea ``socket.socket`` (ninguna prueba abre un socket) y da una carpeta temporal propia."""

    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red: socket.socket está bloqueado"))
        parche.start()
        self.addCleanup(parche.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="infra-prueba-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


def copiar_empresa_prueba(destino: Path) -> None:
    """Crea ``<destino>/empresa/{limites.yaml,parametros.yaml}`` desde los ejemplos válidos de ``contratos/``.

    ``limites.yaml`` ya viene SELLADO (ficticio, EUR; ``contratos/ejemplos/limites.valido.yaml``): alcanza
    para ``evaluar_limites(..., "gastar")`` fuera de producción (sin firma Ed25519 exigida). No se
    modifica nada de ``contratos/``: solo se copian bytes a la raíz temporal de la prueba.
    """
    empresa = destino / "empresa"
    empresa.mkdir(parents=True, exist_ok=True)
    (empresa / "limites.yaml").write_bytes((CONTRATOS_EJEMPLOS / "limites.valido.yaml").read_bytes())
    (empresa / "parametros.yaml").write_bytes((CONTRATOS_EJEMPLOS / "parametros.valido.yaml").read_bytes())
