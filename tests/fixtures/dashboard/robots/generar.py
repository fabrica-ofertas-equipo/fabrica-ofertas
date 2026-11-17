"""Regenera los sobres de ejemplo de ``GET /api/robots/sombra`` que usan las pruebas de Node (``tests/dashboard/test_web_robots_sombra.mjs``).

Uso (desde la raíz del repositorio): ``.venv/bin/python -m tests.fixtures.dashboard.robots.generar``

Los robots en sombra se corren DE VERDAD (``python -m scripts.robots.sombra ejecutar --escribir``) sobre una raíz TEMPORAL y el sobre sale de la API real
(``dashboard/api_robots.py``) con un reloj fijo: nunca se lee ni se escribe ``empresa/`` del proyecto. Tres situaciones:
``corriendo`` (los 7 programados, 30 min después), ``vencido`` (la misma foto, tres días después: nada dio señal a tiempo) y ``manual`` (corrieron solo a mano).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from dashboard import api_robots
from dashboard.api_base import Ctx
from scripts.robots import sombra as _sombra

SALIDA = Path(__file__).resolve().parent
RAIZ_REPO = Path(__file__).resolve().parents[4]
CORRIDA = "2026-11-07T09:00:00Z"
CASOS = {
    "corriendo": (True, _dt.datetime(2026, 11, 7, 9, 30, tzinfo=_dt.timezone.utc)),
    "vencido": (True, _dt.datetime(2026, 11, 10, 9, 30, tzinfo=_dt.timezone.utc)),
    "manual": (False, _dt.datetime(2026, 11, 7, 9, 30, tzinfo=_dt.timezone.utc)),
}


def foto(raiz: Path, programado: bool, ahora: str = CORRIDA) -> None:
    """Corre los 7 robots en sombra con ``--escribir`` sobre ``raiz`` (deja ``empresa/robots/estado.json``)."""
    (raiz / "empresa").mkdir(parents=True, exist_ok=True)
    (raiz / "ofertas").mkdir(exist_ok=True)
    for nombre in ("parametros.yaml", "limites.yaml"):
        shutil.copy(RAIZ_REPO / "empresa" / nombre, raiz / "empresa" / nombre)
    args = ["ejecutar", "--todos", "--escribir", "--raiz", str(raiz), "--ahora", ahora] + (["--programado"] if programado else [])
    with mock.patch.dict(os.environ, {"TZ": "America/Argentina/Buenos_Aires"}):
        _sombra.main(args)


def main() -> None:
    for nombre, (programado, ahora) in CASOS.items():
        raiz = Path(tempfile.mkdtemp(prefix="robots-fixture-"))
        try:
            foto(raiz, programado)
            sobre = api_robots.sombra(Ctx(raiz, ahora=lambda a=ahora: a)).a_dict(ahora.strftime("%Y-%m-%dT%H:%M:%SZ"))
            (SALIDA / f"robots_sombra_{nombre}.json").write_text(json.dumps(sobre, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        finally:
            shutil.rmtree(raiz, True)


if __name__ == "__main__":
    main()
