"""Paso 6 de D6 (``departamentos/07-creativos.md`` §4): cotiza con margen y compara contra los topes.

Dado un plan de piezas con costos YA COTIZADOS (p. ej. de ``ads_studio_quote``/``get_cost``), aplica
el margen de regeneración (PARÁMETRO, nunca literal: ``creativos.margen_regeneracion_pct`` de
``empresa/parametros.yaml``) y compara contra ``creditos_max_pieza``/``creditos_max_oferta`` de
``empresa/limites.yaml`` y contra lo ya registrado en ``empresa/costos.jsonl`` para la oferta.
Bloquea (código 5) si algún tope o el margen es ``null``/ausente, o si el plan excede algún tope.
Con ``--aplicar`` (y SOLO si no hay problemas) escribe cada pieza en ``empresa/costos.jsonl`` ANTES
de que el Maker pueda enviar nada a generar (la regla del flujo, §4 paso 6).

Esta CLI no repite las comprobaciones de PAUSA/infraestructura/entorno: asume que
``scripts.creativos.preflight_d6`` ya corrió (paso 1 del flujo); solo repite los topes de crédito
porque son los únicos que cambian pieza a pieza.

CLI::

    python -m scripts.creativos.cost_preflight --oferta OF-202611-01 --plan PLAN.json
        [--aplicar] [--ejecucion-id ID] [--raiz RUTA] [--json]

``PLAN.json``: ``{"piezas": [{"id": "c01-hueco_img_h1_v1", "creditos_cotizados": 10}, ...]}``
(un entero de créditos por pieza, YA cotizado por el proveedor; sin decimales).

Salida (convenciones §8): 0 ok (dry-run o aplicado) · 5 falta un tope/parámetro o se excede algún
tope · 3 plan ilegible · 2 uso.

Decisión (ver README, «Pedidos»): ``creativos.margen_regeneracion_pct`` NO existe hoy en
``contratos/parametros.schema.json`` (el grupo ``creativos`` es ``additionalProperties: false`` y no
lista esa clave): hasta que CT amplíe el esquema, leer este parámetro falla cerrado con 5 en
cualquier raíz real. La aritmética del margen (:func:`con_margen`) está probada de forma aislada
pasándole ``margen_pct`` explícito, para que el cálculo quede verificado aunque el parámetro no
exista todavía.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun
from engine import limites as motor_limites
from engine import parametros as motor_parametros
from engine import registro as motor_registro
from engine.errores import ErrorLimite, ErrorUso, ErrorValidacion

__all__ = ["CLAVE_MARGEN", "acumulado_previo_de_oferta", "con_margen", "evaluar_plan", "main"]

CLAVE_MARGEN = "creativos.margen_regeneracion_pct"
_RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_ETAPA = "D6"


def con_margen(creditos_cotizados: int, margen_pct: int) -> int:
    """Créditos cotizados + margen de regeneración, redondeados HACIA ARRIBA (lado conservador).

    ``margen_pct`` en unidades de porcentaje (20 = 20 %), igual que el resto de ``*_pct`` de
    ``limites``/``parametros`` (solo ``decision/entradas.py`` convierte a fracción).
    """
    if isinstance(creditos_cotizados, bool) or not isinstance(creditos_cotizados, int) or creditos_cotizados < 0:
        raise ErrorValidacion(f"creditos_cotizados debe ser un entero >= 0 (es {creditos_cotizados!r})")
    if isinstance(margen_pct, bool) or not isinstance(margen_pct, int) or margen_pct < 0:
        raise ErrorValidacion(f"margen_pct debe ser un entero >= 0 (es {margen_pct!r})")
    factor = (Decimal(100 + margen_pct) / Decimal(100))
    return int((Decimal(creditos_cotizados) * factor).to_integral_value(rounding=ROUND_CEILING))


def acumulado_previo_de_oferta(raiz: Path, oferta_id: str) -> int:
    """Suma de ``creditos`` ya registrados en ``empresa/costos.jsonl`` para ``oferta_id`` (origen créditos)."""
    lineas = comun.leer_jsonl(motor_registro.ruta_costos(raiz))
    return sum(
        int(l["creditos"]) for l in lineas
        if l.get("oferta_id") == oferta_id and l.get("origen") == "creditos" and isinstance(l.get("creditos"), int)
        and not isinstance(l.get("creditos"), bool)
    )


def evaluar_plan(piezas: Sequence[Mapping[str, Any]], *, margen_pct: int, tope_pieza: int, tope_oferta: int,
                 acumulado_previo: int) -> dict[str, Any]:
    """Aplica el margen a cada pieza y compara contra los topes; nunca lanza (los problemas quedan en el resultado)."""
    if not piezas:
        raise ErrorValidacion("el plan no tiene piezas")
    filas: list[dict[str, Any]] = []
    problemas: list[str] = []
    vistos: set[str] = set()
    acumulado = acumulado_previo
    for pieza in piezas:
        pid = pieza.get("id") if isinstance(pieza, Mapping) else None
        if not isinstance(pid, str) or not pid.strip():
            raise ErrorValidacion("cada pieza del plan necesita «id» (texto no vacío)")
        if pid in vistos:
            raise ErrorValidacion(f"id de pieza repetido en el plan: {pid}")
        vistos.add(pid)
        con_m = con_margen(pieza.get("creditos_cotizados"), margen_pct)
        acumulado += con_m
        excede_pieza = con_m > tope_pieza
        if excede_pieza:
            problemas.append(f"{pid}: {con_m} créditos (con margen) supera creditos_max_pieza ({tope_pieza})")
        filas.append({
            "id": pid, "creditos_cotizados": pieza.get("creditos_cotizados"), "margen_pct": margen_pct,
            "creditos_con_margen": con_m, "excede_tope_pieza": excede_pieza,
        })
    if acumulado > tope_oferta:
        problemas.append(f"acumulado {acumulado} créditos (con margen) supera creditos_max_oferta ({tope_oferta})")
    return {
        "piezas": filas, "acumulado_previo": acumulado_previo, "total_con_margen": acumulado - acumulado_previo,
        "acumulado_final": acumulado, "tope_pieza": tope_pieza, "tope_oferta": tope_oferta, "problemas": problemas,
    }


def _cargar_plan(ruta: Path) -> list[dict[str, Any]]:
    try:
        datos = comun.cargar_json(ruta)
    except FileNotFoundError as exc:
        raise ErrorUso(f"--plan no existe: {ruta}") from exc
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"--plan ilegible: {exc}") from exc
    if not isinstance(datos, Mapping) or not isinstance(datos.get("piezas"), list):
        raise ErrorValidacion("el plan debe ser {«piezas»: [...]}")
    return list(datos["piezas"])


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.creativos.cost_preflight", description="Paso 6 de D6: topes de créditos antes de generar.")
    p.add_argument("--oferta", required=True, dest="oferta_id")
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--aplicar", action="store_true", help="si no hay problemas, registra cada pieza en empresa/costos.jsonl")
    p.add_argument("--ejecucion-id", default="cost-preflight", dest="ejecucion_id")
    p.add_argument("--raiz", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        if not _RX_OFERTA.match(a.oferta_id):
            raise ErrorUso(f"--oferta inválido: {a.oferta_id!r} (se espera OF-AAAAMM-NN)")
        env = dict(os.environ)
        entorno_actual = comun.entorno(env)
        if a.raiz and entorno_actual == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        raiz = a.raiz.resolve() if a.raiz else comun.raiz(env)
        piezas = _cargar_plan(a.plan)

        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        motor_limites.exigir_operacion(lim, "generar_creativos")  # 5 si falta cualquier tope de la operación
        tope_pieza, tope_oferta = lim.valor("creditos_max_pieza"), lim.valor("creditos_max_oferta")

        par = motor_parametros.cargar_parametros(raiz / "empresa" / "parametros.yaml")
        margen_pct = par.valor(CLAVE_MARGEN)  # ParametroFaltante (5) si no existe o es null
        if isinstance(margen_pct, bool) or not isinstance(margen_pct, int) or margen_pct < 0:
            raise ErrorLimite(f"{CLAVE_MARGEN} inválido: se espera un entero >= 0 (unidad de porcentaje)")

        acumulado_previo = acumulado_previo_de_oferta(raiz, a.oferta_id)
        resultado = evaluar_plan(piezas, margen_pct=margen_pct, tope_pieza=tope_pieza, tope_oferta=tope_oferta,
                                 acumulado_previo=acumulado_previo)
        if resultado["problemas"]:
            raise ErrorLimite("cost_preflight bloqueado: " + "; ".join(resultado["problemas"]),
                              detalle={"problemas": resultado["problemas"]})

        aplicado = False
        if a.aplicar:
            for fila in resultado["piezas"]:
                motor_registro.costo(a.oferta_id, "creditos", 0, lim.moneda, etapa=_ETAPA, ejecucion_id=a.ejecucion_id,
                                     concepto=f"cost_preflight:{fila['id']}", creditos=fila["creditos_con_margen"])
            aplicado = True

        modo = "aplicado" if aplicado else "dry_run"
        salida = {"ok": True, "modo": modo, "codigo": 0, "datos": resultado, "avisos": []}
        if a.json:
            print(json.dumps(salida, sort_keys=True, ensure_ascii=False))
        else:
            for fila in resultado["piezas"]:
                print(f"{fila['id']}: {fila['creditos_cotizados']} + {fila['margen_pct']}% = {fila['creditos_con_margen']} créditos")
            print(f"acumulado {resultado['acumulado_previo']} + {resultado['total_con_margen']} = {resultado['acumulado_final']} "
                 f"(topes: pieza {tope_pieza}, oferta {tope_oferta}) — {modo}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    raise SystemExit(main())
