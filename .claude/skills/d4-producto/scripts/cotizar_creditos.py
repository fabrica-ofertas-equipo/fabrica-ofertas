#!/usr/bin/env python3
"""Cotización previa de créditos de imagen/video: AUTORIZA o DENIEGA el gasto antes de llamar a Higgsfield (u otro generador). No gasta nada.

El Maker (o quien genere) obtiene la cotización de cada pieza SIN generar (``generate_image`` con ``get_cost: true`` en la sesión interactiva; el lote
``generate_image_batch`` NO admite cotizar: se cotiza pieza por pieza) y la anota en un JSON; este script compara con los topes del dueño:

  - ``limites.creditos_max_pieza``  : ninguna pieza lo supera.
  - ``limites.creditos_max_oferta`` : gastado_antes + Σ cotizado ≤ tope.
  - ``limites.costo_max_producto``  : si existe y la cotización trae ``costo_tokens_estimado`` (misma unidad), el total no lo supera.
  - ``null`` en cualquiera de las dos primeras (o archivo ausente) = NO se gasta («solo texto»): fail-closed.
  - Existe ``empresa/PAUSA`` o ``empresa/infra/estado.json`` no está en VERDE y vigente = NO se gasta.
  - Falta ``permiso_dueno: true`` en la cotización = NO se gasta (el permiso es del dueño, en el chat; nunca se infiere).
  - ``use_unlim`` / ``use_free_gens`` solo con ``permiso_unlim_dueno: true`` explícito.

Cotización (JSON): {"permiso_dueno": true, "gastado_antes": 0, "piezas": [{"id": "...", "creditos": 12, "modelo": "...", "prompt_ref": "..."}],
                    "costo_tokens_estimado": null, "use_unlim": false, "permiso_unlim_dueno": false}

Uso: python3 cotizar_creditos.py --cotizacion cot.json [--limites empresa/limites.yaml] [--raiz .] [--ahora 2026-11-06T10:00:00Z] [--salida X]
Salida 0 = AUTORIZADO · 1 = DENEGADO (con motivos) · 3 entrada inválida.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402


def instante(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cotizacion", required=True)
    ap.add_argument("--limites")
    ap.add_argument("--raiz", help="raíz del proyecto (por defecto, la detectada)")
    ap.add_argument("--ahora", help="AAAA-MM-DDTHH:MM:SSZ (determinismo; por defecto, ahora)")
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    raiz = Path(a.raiz) if a.raiz else c.raiz_proyecto()
    try:
        cot = c.cargar_json(a.cotizacion)
        lim_ruta = Path(a.limites) if a.limites else (raiz / "empresa" / "limites.yaml" if raiz else None)
        lim = c.cargar_yaml(lim_ruta) if lim_ruta and lim_ruta.is_file() else None
    except (OSError, ValueError, c.ParametroFaltante) as e:
        return c.error_uso(f"entrada inválida: {e}", 3)
    ahora = instante(a.ahora) if a.ahora else datetime.now(timezone.utc)
    h: list[dict] = []

    def denegar(msg: str, patron: str) -> None:
        h.append(c.hallazgo("L1-GASTO", "BLOQUEANTE", msg, a.cotizacion, patron))

    if lim is None:
        denegar("no se pudo leer limites.yaml: sin dato, nada gasta (solo texto)", "sin-limites")
        lim = {}
    tope_pieza, tope_oferta, tope_producto = lim.get("creditos_max_pieza"), lim.get("creditos_max_oferta"), lim.get("costo_max_producto")
    if tope_pieza is None:
        denegar("limites.creditos_max_pieza es null: el producto se hace solo con texto", "limite-null")
    if tope_oferta is None:
        denegar("limites.creditos_max_oferta es null: el producto se hace solo con texto", "limite-null")
    if raiz:
        if (raiz / "empresa" / "PAUSA").exists():
            denegar("existe empresa/PAUSA: ningún agente gasta", "pausa")
        infra = raiz / "empresa" / "infra" / "estado.json"
        if not infra.is_file():
            denegar("falta empresa/infra/estado.json: sin infraestructura en VERDE y vigente nada gasta", "infra")
        else:
            try:
                e = c.cargar_json(infra)
                vh = instante(e.get("valido_hasta", ""))
                if e.get("semaforo") != "VERDE" or vh is None or vh < ahora:
                    denegar(f"infraestructura {e.get('semaforo')} o vencida ({e.get('valido_hasta')}): nada gasta", "infra")
            except (OSError, ValueError):
                denegar("empresa/infra/estado.json ilegible", "infra")
    if cot.get("permiso_dueno") is not True:
        denegar("falta permiso_dueno: true (el permiso de gastar créditos es del dueño, explícito y por esta cotización)", "sin-permiso")
    if (cot.get("use_unlim") or cot.get("use_free_gens")) and cot.get("permiso_unlim_dueno") is not True:
        denegar("use_unlim/use_free_gens solo con permiso explícito del dueño (por defecto se paga con créditos cotizados)", "unlim-sin-permiso")
    piezas = cot.get("piezas") or []
    if not piezas:
        denegar("la cotización no trae piezas", "vacia")
    total = 0
    for p in piezas:
        cr = p.get("creditos")
        if not isinstance(cr, int) or isinstance(cr, bool) or cr < 0:
            denegar(f"pieza {p.get('id')}: créditos inválidos (entero ≥ 0 cotizado SIN generar)", "creditos-invalidos")
            continue
        total += cr
        if tope_pieza is not None and cr > tope_pieza:
            denegar(f"pieza {p.get('id')}: {cr} créditos > creditos_max_pieza {tope_pieza}", "excede-pieza")
    antes = cot.get("gastado_antes", 0)
    if not isinstance(antes, int) or antes < 0:
        denegar("gastado_antes inválido", "creditos-invalidos")
        antes = 0
    if tope_oferta is not None and antes + total > tope_oferta:
        denegar(f"gastado {antes} + cotizado {total} = {antes + total} > creditos_max_oferta {tope_oferta}", "excede-oferta")
    if tope_producto is not None and cot.get("costo_tokens_estimado") is not None:
        if total + int(cot["costo_tokens_estimado"]) > tope_producto:
            denegar("créditos + tokens estimados superan limites.costo_max_producto", "excede-producto")
    return c.emitir("cotizar_creditos", ["L1-GASTO"], h, {
        "autorizado": not h, "total_cotizado": total, "gastado_antes": antes, "creditos_max_pieza": tope_pieza,
        "creditos_max_oferta": tope_oferta, "margen_oferta": None if tope_oferta is None else tope_oferta - antes - total, "piezas": len(piezas),
    }, a.salida)


if __name__ == "__main__":
    sys.exit(main())
