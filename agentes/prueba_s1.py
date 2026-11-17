"""Prueba S-1 (docs/06 §8 ola 3, docs/10-runbook-testeo.md §"S-1/E-1"): corrida REAL mínima del
runner con una skill de humo de tres líneas y presupuesto de centavos.

Qué demuestra (antes de dejar que un agente trabaje desatendido con dinero real, y de nuevo tras
cada actualización de Claude Code): el evento ``system/init`` lista los hooks cargados, ``tools``
no incluye ningún ``mcp__*``, la skill se invoca y el staging valida. Es la ÚNICA pieza de este
componente que de verdad lanza un proceso ``claude -p``: por eso exige ``--live``, ``produccion`` y
``ANTHROPIC_API_KEY`` real (los 7/pasos del preflight de ``agentes.runner``, §12.3).

Esta sesión de construcción NO la ejecuta (sin red, sin credenciales, sin ``--live``, reglas de la
noche): solo deja el script listo para que el dueño (o I1) la corra en la ola 3.

CLI: ``python -m agentes.prueba_s1 [--live]``. Sin ``--live``, imprime el plan (dry-run) y no toca nada.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from agentes.runner import ejecutar
from agentes.tipos import EspecCorrida, Modo, Presupuesto

__all__ = ["espec_humo", "main"]


def espec_humo(*, agente: str = "s1-humo", presupuesto_centavos: int = 50) -> EspecCorrida:
    """``EspecCorrida`` de la prueba S-1: una skill de humo mínima, sin dinero real ni artefactos."""
    return EspecCorrida(
        rol="maker", etapa="S1", oferta_id=None, agente=agente,
        prompt_base='/s1-humo Responde SOLO con el JSON {"hola":"mundo"} y nada más de texto.',
        entradas=(), contrato_salida="contratos/comunes.schema.json",
        artefactos_esperados=(), herramientas=("Read",), allow=(), rutas_escribibles=(),
        presupuesto=Presupuesto(usd_centavos_max=presupuesto_centavos, tiempo_s_max=120, turnos_max=5),
        modelo="claude-haiku-4-5", esfuerzo="low",
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m agentes.prueba_s1",
        description="Prueba S-1: corrida real mínima del runner (ola 3; exige --live, produccion y ANTHROPIC_API_KEY real).",
    )
    ap.add_argument("--live", action="store_true", help="sin esto, solo imprime el plan (dry-run); nunca lanza un proceso")
    ap.add_argument("--raiz", type=Path, default=None)
    args = ap.parse_args(argv)

    espec = espec_humo()
    modo = Modo.LIVE if args.live else Modo.DRY_RUN
    resultado = ejecutar(espec, modo=modo, raiz=args.raiz, env=os.environ)
    print(json.dumps(resultado.a_json(), ensure_ascii=False, indent=2, sort_keys=True))
    if modo is Modo.DRY_RUN:
        return 0
    return 0 if resultado.estado == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
