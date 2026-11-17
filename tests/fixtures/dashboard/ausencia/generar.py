"""Regenera los sobres de ejemplo de ``GET /api/alertas`` y ``GET /api/informe`` que usan las pruebas de Node (``tests/dashboard/test_web_ausencia.mjs``).

Uso (desde la raíz del repositorio): ``.venv/bin/python -m tests.fixtures.dashboard.ausencia.generar``

Los sobres salen de la API REAL (``dashboard/api_alertas.py``) sobre una raíz TEMPORAL armada con las ayudas de ``tests/alertas`` y un reloj fijo
(2026-11-07T08:30:00Z): nunca leen ``empresa/`` ni ``ofertas/`` reales. Tres situaciones: ``hoy`` (rojo: lo que hay en el proyecto, con límites vacíos y el freno de captura puesto),
``amarillo`` (todo en orden salvo una firma esperando) y ``verde`` (todo en orden). Si cambian los textos o la forma de la API, se vuelve a correr y se revisa el diff.
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from dashboard import api_alertas
from dashboard.api_base import Ctx
from tests.alertas.ayudas import ITEMS_BUENOS, LIMITES_COMPLETOS, LIMITES_VACIOS, PARAMETROS, estado_infra

AHORA = _dt.datetime(2026, 11, 7, 8, 30, tzinfo=_dt.timezone.utc)
SALIDA = Path(__file__).resolve().parent


def _hoy(poner: Callable[[str, object], None]) -> None:
    poner("empresa/parametros.yaml", PARAMETROS)
    poner("empresa/limites.yaml", LIMITES_VACIOS)
    poner("empresa/captura/freno.json", {"ts": "2026-11-06T06:03:43Z", "motivo": "HTTP 403 (Document)"})
    poner("empresa/panel/pulido.jsonl", "".join(json.dumps(x) + "\n" for x in [
        {"id": "PUL-0003", "ts": "2026-11-07T21:20:38Z", "evento": "alta", "titulo": "Elegir el canal de avisos al celular y un segundo canal", "etapa": "D0", "responsable": "dueno", "prioridad": "P0", "estado": "abierta"},
        {"id": "PUL-0008", "ts": "2026-11-07T21:20:39Z", "evento": "alta", "titulo": "Revisar y firmar límites: 300 US$ por día y pausa a −3.000 US$", "etapa": "O0", "responsable": "dueno", "prioridad": "P1", "estado": "abierta"}]))


def _verde(poner: Callable[[str, object], None]) -> None:
    poner("empresa/parametros.yaml", PARAMETROS)
    poner("empresa/limites.yaml", LIMITES_COMPLETOS)
    poner("empresa/infra/estado.json", estado_infra(items=ITEMS_BUENOS))
    poner("empresa/avisos.yaml", "canales:\n  - {tipo: telegram, estado: probado}\n  - {tipo: correo, estado: probado}\n")
    poner("empresa/infra/latidos.json", {"trabajos": [{"id": "informe", "ultimo_latido": "2026-11-07T08:25:00Z"}]})


def _amarillo(poner: Callable[[str, object], None]) -> None:
    _verde(poner)
    poner("ofertas/OF-202611-91/estado.json", {"schema_version": "1.0.0", "oferta_id": "OF-202611-91", "fase": "en_construccion", "nivel": "N0", "pausa": False,
                                                "etapas": {"M1": {"estado": "aprobado", "gate_pendiente": False}, "D2": {"estado": "en_QA", "gate_pendiente": True, "gate": "H"}},
                                                "actualizado_en": "2026-11-06T08:30:00Z"})


def main() -> None:
    for nombre, armar in (("hoy", _hoy), ("verde", _verde), ("amarillo", _amarillo)):
        raiz = Path(tempfile.mkdtemp(prefix="ausencia-fixture-"))
        try:
            (raiz / "empresa").mkdir()
            (raiz / "ofertas").mkdir()

            def poner(rel: str, contenido: object, _raiz: Path = raiz) -> None:
                destino = _raiz / rel
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(contenido if isinstance(contenido, str) else json.dumps(contenido), encoding="utf-8")

            armar(poner)
            ctx = Ctx(raiz, ahora=lambda: AHORA)
            for ruta, lector in (("alertas", api_alertas.alertas), ("informe", api_alertas.informe)):
                sobre = lector(ctx).a_dict("2026-11-07T08:30:00Z")
                (SALIDA / f"{ruta}_{nombre}.json").write_text(json.dumps(sobre, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        finally:
            shutil.rmtree(raiz, True)


if __name__ == "__main__":
    main()
