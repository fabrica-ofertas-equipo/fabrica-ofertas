"""``meta.lectura_viva``: genera ``07-campana/lectura_viva.json`` (A13, dependencias.md de D7).

El QA de D7 no tiene ``Bash`` ni ninguna herramienta ``mcp__*`` (solo lectura de archivos,
``agentes/plantillas_agentes/d7-qa.md``): las comprobaciones deterministas contra Meta las corre el
motor ANTES de llamarlo y se las entrega como archivo. Este módulo es ese «antes»: lee el estado vivo
de la campaña (vía :func:`meta.activar.leer_estado_vivo`, sobre ``ClienteMeta``/``TransporteFixture``,
NUNCA el Maker) y lo vuelca a un objeto que el QA puede citar. Sin esto, un rechazo o una deriva
silenciosa de Meta se confundiría con «no hubo tiempo de revisarlo».

Sin esquema propio en ``contratos/`` todavía: es un pedido abierto a CT (MINOR, ver README
«Pedidos»). Se usa la forma más cercana existente, ``contratos/traspaso.schema.json`` (campaña +
anuncios + instante), adaptada; este módulo no afirma cumplirlo (no lleva ``schema_version`` hasta
que exista un esquema propio que versionar: agregarlo sin uno sería mentir sobre qué se validó).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, limites as motor_limites
from engine.errores import ErrorUso
from meta import _cli_comun
from meta.activar import leer_estado_vivo
from meta.cliente import ClienteMeta

__all__ = ["generar", "main"]


def generar(*, oferta_id: str, cliente: ClienteMeta, ids_meta: Mapping[str, Any], hash_config: str,
           ahora: Callable[[], datetime] = comun.ahora_utc, incluir_creativo: bool = False) -> dict[str, Any]:
    """Estado vivo de la campaña (campaña, conjunto, anuncios y, si se pide, creativos), para el QA.

    Puro respecto del disco: no escribe nada (quien llama decide si lo vuelca a archivo, con
    ``comun.escribir_atomico``, igual que cualquier otro artefacto). ``incluir_creativo=True`` agrega
    ``object_story_spec`` de cada creativo (mismo criterio que :func:`meta.activar.activar`).
    """
    t = comun.instante(ahora)
    vivo = leer_estado_vivo(cliente, ids_meta, incluir_creativo=incluir_creativo)
    datos: dict[str, Any] = {
        "oferta_id": oferta_id, "hash_config": hash_config, "leido_en": comun.iso_z(t),
        "campana": dict(vivo["campana"]), "conjunto": dict(vivo["conjunto"]),
        "anuncios": [dict(a) for a in vivo["anuncios"]],
    }
    if "creativos" in vivo:
        datos["creativos"] = [dict(c) for c in vivo["creativos"]]
    return datos


# ----------------------------------------------------------------------------------------------
# CLI (A13, ola 2 B5b): sin --live real (alcance de la noche, igual que el resto de meta/*; ver README).
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.lectura_viva --oferta OF-… --ids-meta ids_meta.json --hash-config … [--salida lectura_viva.json]``."""
    ap = argparse.ArgumentParser(prog="python -m meta.lectura_viva", description="Estado vivo de la campaña para el QA de D7 (A13).")
    ap.add_argument("--ids-meta", required=True, dest="ids_meta_ruta")
    ap.add_argument("--hash-config", required=True, dest="hash_config")
    ap.add_argument("--salida", help="ruta donde escribir lectura_viva.json; si se omite, solo se imprime")
    ap.add_argument("--incluir-creativo", action="store_true", dest="incluir_creativo")
    _cli_comun.agregar_argumentos_comunes(ap)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        ids_meta = comun.cargar_json(Path(args.ids_meta_ruta))

        if args.modo == "dry-run":
            plan = {"oferta_id": args.oferta, "hash_config": args.hash_config, "object_ids": sorted({
                ids_meta["campaign_id"], *ids_meta["adset_ids"], *ids_meta["ad_ids"],
            })}
            _cli_comun.imprimir(ok=True, modo="dry_run", codigo=0, datos=plan, avisos=["dry-run: no se llama a Meta"], as_json=args.json)
            return 0

        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        cliente, _ = _cli_comun.construir_cliente(
            args, env, segundos_min_entre_ediciones=lim.valor("segundos_min_entre_ediciones"),
            max_cambios_presupuesto_por_hora=lim.valor("max_cambios_presupuesto_por_hora_por_conjunto"),
        )
        datos = generar(oferta_id=args.oferta, cliente=cliente, ids_meta=ids_meta, hash_config=args.hash_config,
                        ahora=reloj, incluir_creativo=args.incluir_creativo)
        if args.salida:
            comun.escribir_atomico(Path(args.salida), comun.json_canonico(datos))
        _cli_comun.imprimir(ok=True, modo=args.modo, codigo=0, datos=datos, avisos=[], as_json=args.json)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
