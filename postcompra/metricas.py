"""``postcompra.metricas``: calcula y escribe ``senal_pausa.json`` (D10 → D8, R08, B0-19/B0-20).

Un solo conjunto de umbrales para disputas y reembolsos (``parametros.salud_operativa`` +
``limites.ratio_disputas_pausa``, reconciliación R06 de docs/contratos.md):

* **Disputas** (sobre ``disputas_ventana_dias``): con muestra suficiente (``pagos_ventana >=
  disputas_muestra_min_pagos``) el disparador es el RATIO real contra ``ratio_disputas_pausa``
  (rojo) o el porcentaje contra ``disputas_alerta_pct`` (amarillo); el ejemplo de B0-20 («dos disputas
  empujan la señal sobre ``ratio_disputas_pausa``») asume muestra suficiente. Con muestra insuficiente
  el porcentaje NO dispara por sí solo (así lo dice el esquema): se usa el CONTEO absoluto contra
  ``disputas_casos_pausa``/``disputas_casos_alerta``.
* **Reembolsos**: solo porcentaje, y solo con ``reembolsos_pedidos >= reembolsos_n_min`` (sin conteo
  de respaldo: con pocos pedidos un reembolso aislado no dice nada).

Entrada: por ahora los conteos (``--pagos-ventana``, ``--casos-disputa``, ``--reembolsos``,
``--reembolsos-pedidos``) son ARGUMENTOS explícitos, no se leen de ``datos`` todavía (B3 no está
construido en esta ola; ver «Pedidos» del README). El núcleo (:func:`calcular_senal`) es puro: dado
los conteos y los parámetros, decide el nivel; eso ya se puede probar hoy y no cambia cuando ``datos``
exista.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Callable, Sequence

from engine import comun, limites, parametros
from engine.errores import ErrorUso, ErrorValidacion
from postcompra import _comun

__all__ = ["Senal", "calcular_senal", "main", "escribir_senal_pausa"]

_SCHEMA_VERSION = "1.1.0"
_DECIMALES_PCT = Decimal("0.0001")


@dataclass(frozen=True)
class Senal:
    """El contenido de ``senal_pausa.json``, ya decidido (falta solo escribirlo)."""

    nivel: str  # verde|amarillo|rojo
    motivo: str  # ninguno|disputas|reembolsos
    emitida: bool
    accion_solicitada: str  # ninguna|alertar|pausar
    muestra_suficiente: bool
    disputas_efw_pct: str
    reembolsos_pct: str


def _pct(numerador: int, denominador: int) -> Decimal:
    if denominador <= 0:
        return Decimal(0)
    return (Decimal(numerador) * 100 / Decimal(denominador)).quantize(_DECIMALES_PCT, rounding=ROUND_HALF_EVEN)


def _nivel_peor(a: str, b: str) -> str:
    orden = {"verde": 0, "amarillo": 1, "rojo": 2}
    return a if orden[a] >= orden[b] else b


def calcular_senal(*, pagos_ventana: int, casos_disputa_efw: int, reembolsos_num: int, reembolsos_den: int,
                   lim: limites.Limites, par: parametros.Parametros) -> Senal:
    """Decide el nivel/motivo/acción a partir de los conteos y los parámetros (función pura, sin E/S)."""
    for nombre, valor in (("pagos_ventana", pagos_ventana), ("casos_disputa_efw", casos_disputa_efw),
                          ("reembolsos_num", reembolsos_num), ("reembolsos_den", reembolsos_den)):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            raise ErrorValidacion(f"{nombre} debe ser un entero >= 0")

    muestra_min_disputas = par.valor("salud_operativa.disputas_muestra_min_pagos")
    disputas_alerta_pct = Decimal(str(par.valor("salud_operativa.disputas_alerta_pct")))
    disputas_casos_alerta = par.valor("salud_operativa.disputas_casos_alerta")
    disputas_casos_pausa = par.valor("salud_operativa.disputas_casos_pausa")
    ratio_disputas_pausa = Decimal(str(lim.valor("ratio_disputas_pausa")))
    reembolsos_n_min = par.valor("salud_operativa.reembolsos_n_min")
    reembolsos_alerta_pct = Decimal(str(par.valor("salud_operativa.reembolsos_alerta_pct")))
    reembolsos_pausa_pct = Decimal(str(par.valor("salud_operativa.reembolsos_pausa_pct")))

    pct_disputas = _pct(casos_disputa_efw, pagos_ventana)
    muestra_suficiente_disputas = pagos_ventana >= muestra_min_disputas
    if muestra_suficiente_disputas:
        ratio_real = Decimal(casos_disputa_efw) / Decimal(pagos_ventana) if pagos_ventana > 0 else Decimal(0)
        if ratio_real >= ratio_disputas_pausa:
            nivel_disputas = "rojo"
        elif pct_disputas >= disputas_alerta_pct:
            nivel_disputas = "amarillo"
        else:
            nivel_disputas = "verde"
    else:
        if casos_disputa_efw >= disputas_casos_pausa:
            nivel_disputas = "rojo"
        elif casos_disputa_efw >= disputas_casos_alerta:
            nivel_disputas = "amarillo"
        else:
            nivel_disputas = "verde"

    pct_reembolsos = _pct(reembolsos_num, reembolsos_den)
    muestra_suficiente_reembolsos = reembolsos_den >= reembolsos_n_min
    if muestra_suficiente_reembolsos:
        if pct_reembolsos >= reembolsos_pausa_pct:
            nivel_reembolsos = "rojo"
        elif pct_reembolsos >= reembolsos_alerta_pct:
            nivel_reembolsos = "amarillo"
        else:
            nivel_reembolsos = "verde"
    else:
        nivel_reembolsos = "verde"  # sin conteo de respaldo para reembolsos (a diferencia de disputas)

    peor = _nivel_peor(nivel_disputas, nivel_reembolsos)
    # Con empate (las dos al mismo nivel y no verdes) se prioriza "disputas": es el motivo con el
    # conteo de respaldo de muestra insuficiente (más grave en ese escenario, B0-20).
    if peor == "verde":
        motivo, muestra_suficiente = "ninguno", muestra_suficiente_disputas
    elif nivel_disputas == peor:
        motivo, muestra_suficiente = "disputas", muestra_suficiente_disputas
    else:
        motivo, muestra_suficiente = "reembolsos", muestra_suficiente_reembolsos

    accion = {"verde": "ninguna", "amarillo": "alertar", "rojo": "pausar"}[peor]
    return Senal(nivel=peor, motivo=motivo, emitida=peor != "verde", accion_solicitada=accion,
                muestra_suficiente=muestra_suficiente, disputas_efw_pct=str(pct_disputas), reembolsos_pct=str(pct_reembolsos))


def escribir_senal_pausa(*, raiz: Path, oferta_id: str, senal: Senal, pagos_ventana: int, casos_disputa_efw: int,
                         lim: limites.Limites, par: parametros.Parametros, ahora: Callable[[], datetime]) -> dict:
    """Construye y escribe ``senal_pausa.json`` de la oferta (atómico; reemplaza el anterior)."""
    oferta_id = _comun.exigir_oferta_id(oferta_id)
    t = comun.instante(ahora)
    datos = {
        "schema_version": _SCHEMA_VERSION,
        "oferta_id": oferta_id,
        "ts": comun.iso_z(t),
        "emitida": senal.emitida,
        "nivel": senal.nivel,
        "motivo": senal.motivo,
        "metricas": {
            "muestra_suficiente": senal.muestra_suficiente,
            "pagos_ventana": pagos_ventana,
            "casos_disputa_efw": casos_disputa_efw,
            "disputas_efw_pct": senal.disputas_efw_pct,
            "reembolsos_pct": senal.reembolsos_pct,
            "ventana_dias": par.valor("salud_operativa.disputas_ventana_dias"),
        },
        "umbrales_usados": {
            "disputas_alerta_pct": str(par.valor("salud_operativa.disputas_alerta_pct")),
            "ratio_disputas_pausa": str(lim.valor("ratio_disputas_pausa")),
            "reembolsos_alerta_pct": str(par.valor("salud_operativa.reembolsos_alerta_pct")),
            "reembolsos_pausa_pct": str(par.valor("salud_operativa.reembolsos_pausa_pct")),
        },
        "accion_solicitada": senal.accion_solicitada,
        "consumida_por": None,
    }
    errores = comun.errores_de_esquema("senal_pausa", datos)
    if errores:
        raise ErrorValidacion(f"senal_pausa inválida: {comun.resumir_errores_esquema(errores)}")
    comun.escribir_atomico(_comun.ruta_senal_pausa(raiz, oferta_id), comun.json_canonico(datos))
    return datos


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python -m postcompra.metricas --oferta OF-... --pagos-ventana N --casos-disputa N --reembolsos N --reembolsos-pedidos N``."""
    ap = argparse.ArgumentParser(prog="python -m postcompra.metricas", description="Calcula y escribe senal_pausa.json.")
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--pagos-ventana", required=True, type=int, dest="pagos_ventana")
    ap.add_argument("--casos-disputa", required=True, type=int, dest="casos_disputa")
    ap.add_argument("--reembolsos", required=True, type=int)
    ap.add_argument("--reembolsos-pedidos", required=True, type=int, dest="reembolsos_pedidos")
    ap.add_argument("--raiz")
    ap.add_argument("--ahora")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        lim = limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env, entorno=comun.entorno(env))
        par = parametros.cargar_parametros(raiz / "empresa" / "parametros.yaml")
        senal = calcular_senal(pagos_ventana=args.pagos_ventana, casos_disputa_efw=args.casos_disputa,
                               reembolsos_num=args.reembolsos, reembolsos_den=args.reembolsos_pedidos, lim=lim, par=par)
        datos = escribir_senal_pausa(raiz=raiz, oferta_id=args.oferta, senal=senal, pagos_ventana=args.pagos_ventana,
                                     casos_disputa_efw=args.casos_disputa, lim=lim, par=par, ahora=reloj)
        if args.json:
            print(json.dumps({"ok": True, "modo": "dry_run", "codigo": 0, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(f"SENAL_PAUSA {datos['nivel'].upper()} ({datos['motivo']}): {json.dumps(datos, ensure_ascii=False, sort_keys=True)}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
