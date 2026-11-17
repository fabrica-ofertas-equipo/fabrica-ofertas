#!/usr/bin/env python3
"""Regla de salud de cuentas de X1: implementación de REFERENCIA (oráculo de pruebas), no ejecutor.

La salud diaria es de CÓDIGO (spec 14 §4 paso 8; ``x1_salud``/``x1_pausa`` aún no existen en B6: ver
``references/dependencias.md`` D-04). Este archivo traduce a una función pura la regla de ``spec 14 §3.4`` y de la
nota 25 §9 para que (a) las series simuladas de ``evals/salud/series.json`` tengan un resultado esperado
reproducible y (b) quien construya el ejecutor tenga un oráculo. NO pausa nada, NO llama a Meta ni a Stripe, NO lee
credenciales: recibe un estado ya leído y devuelve una acción propuesta. Reanudar es siempre humano.

Todo umbral entra por ``params`` (claves de ``empresa/parametros.yaml`` y ``empresa/limites.yaml``); aquí no hay
números de negocio. Los valores de las series son de PRUEBA ``[SUPUESTO]``.

Uso:  python3 regla_salud.py --series ../evals/salud/series.json    (0 = todas coinciden; 1 = alguna difiere)
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

ACCIONES = ("seguir", "congelar_angulo", "congelar_hoja", "pausar_oferta", "PAUSA")
_SEV = {a: i for i, a in enumerate(ACCIONES)}
CLAVES_PARAMS = (
    "rechazos_congelar", "rechazos_ventana_dias", "disputas_alerta_pct", "disputas_casos_alerta", "disputas_casos_pausa",
    "disputas_muestra_min_pagos", "ratio_disputas_pausa", "reembolsos_alerta_pct", "reembolsos_pausa_pct", "reembolsos_n_min",
    "salud_max_antiguedad_h", "declaracion_calidad_cuenta_max_dias", "estado_meta_requerido_para_lanzar",
)


def decidir(estado: dict, params: dict) -> dict:
    """Acción propuesta para un estado de salud. Falla cerrado: un dato ausente da ``ValueError``, no ``seguir``."""
    faltan = [k for k in CLAVES_PARAMS if params.get(k) is None]
    if faltan:
        raise ValueError(f"sin parámetro no se decide (nada gasta): faltan {', '.join(faltan)}")
    accion, alcance = "seguir", None
    alertas: list[str] = []
    motivos: list[str] = []

    def subir(nueva: str, motivo: str, alc: str | None = None) -> None:
        nonlocal accion, alcance
        motivos.append(motivo)
        if _SEV[nueva] > _SEV[accion]:
            accion, alcance = nueva, alc

    # 1) cuenta y procesador: lo más grave primero
    if estado["account_status"] != "ACTIVE":
        subir("PAUSA", f"account_status={estado['account_status']}", "cuenta")
    calidad = estado.get("calidad_cuenta_meta")
    if calidad == "Restringida":
        subir("PAUSA", "calidad de cuenta Restringida", "cuenta")
    elif calidad is not None and calidad != params["estado_meta_requerido_para_lanzar"]:
        subir("congelar_hoja", f"calidad de cuenta {calidad}: congelar lanzamientos y auditar", "cuenta")  # [SUPUESTO] alcance = toda hoja nueva
        alertas.append("auditar_14_dias")
    if estado.get("stripe_aviso") in ("suspension", "cierre", "monitoreo_vamp"):
        subir("PAUSA", f"aviso de Stripe: {estado['stripe_aviso']}", "cuenta")
    elif estado.get("stripe_aviso") in ("retraso_pago", "reserva"):
        subir("pausar_oferta", f"aviso de Stripe: {estado['stripe_aviso']}", "oferta")
    elif estado.get("stripe_aviso") == "informacion":
        alertas.append("stripe_pide_informacion")

    # 2) rechazos de Meta en la ventana (un rechazo revertido en revisión no cuenta)
    vivos = [r for r in estado.get("rechazos", []) if not r.get("revertido") and r["hace_dias"] <= params["rechazos_ventana_dias"]]
    if any(r["tipo"] in ("producto", "contenido") for r in vivos):
        subir("congelar_hoja", "rechazo de producto o contenido", "hoja")
    if any(r["tipo"] == "pieza" for r in vivos):
        subir("congelar_angulo", "rechazo de pieza", "angulo")
    if len(vivos) >= params["rechazos_congelar"]:
        subir("congelar_hoja", f"{len(vivos)} rechazos en la ventana (>= rechazos_congelar)", "cuenta")
        alertas.append("bajar_D5_D9_a_N1")

    # 3) disputas + EFW (ventana móvil de disputas_ventana_dias; llegan hasta ~120 días tarde: informar también la cohorte madura)
    pagos, casos = estado["pagos_30d"], estado["disputas_30d"]
    ratio = (Decimal(casos) / Decimal(pagos)) if pagos else Decimal(0)
    if pagos >= params["disputas_muestra_min_pagos"] and ratio >= Decimal(str(params["ratio_disputas_pausa"])):  # con poca muestra mandan los conteos
        subir("pausar_oferta", "ratio de disputas >= limites.ratio_disputas_pausa", "oferta")
        alertas.append("proponer_pausa_macro_gate_H")
    if casos >= params["disputas_casos_pausa"]:
        subir("pausar_oferta", "casos de disputa >= disputas_casos_pausa", "oferta")
    elif casos >= params["disputas_casos_alerta"] or (pagos >= params["disputas_muestra_min_pagos"]
                                                      and ratio * 100 >= Decimal(str(params["disputas_alerta_pct"]))):
        alertas.append("alerta_disputas")

    # 4) reembolsos en cohortes maduras (solo con muestra suficiente)
    if estado.get("reembolsos_n", 0) >= params["reembolsos_n_min"]:
        pct = Decimal(str(estado["reembolsos_pct"]))
        if pct >= Decimal(str(params["reembolsos_pausa_pct"])):
            subir("pausar_oferta", "reembolsos >= reembolsos_pausa_pct", "oferta")
        elif pct >= Decimal(str(params["reembolsos_alerta_pct"])):
            alertas.append("alerta_reembolsos")

    # 5) frescura de los datos de salud: sin dato fresco no se lanza
    bloqueados = accion != "seguir"
    if estado["edad_salud_h"] > params["salud_max_antiguedad_h"]:
        alertas.append("salud_vieja")
        bloqueados = True
    if calidad is not None and estado.get("calidad_edad_dias", 0) > params["declaracion_calidad_cuenta_max_dias"]:
        alertas.append("declaracion_calidad_vencida")
        bloqueados = True
    return {"accion": accion, "alcance": alcance, "alertas": sorted(set(alertas)), "lanzamientos_bloqueados": bloqueados, "motivos": motivos}


def correr_series(ruta: Path) -> list[str]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    fallos = []
    for s in datos["series"]:
        r = decidir(s["estado"], datos["parametros"])
        esperado = s["esperado"]
        for clave in ("accion", "alcance", "lanzamientos_bloqueados"):
            if r[clave] != esperado[clave]:
                fallos.append(f"{s['id']}: {clave} esperado {esperado[clave]!r} != {r[clave]!r}")
        faltan = set(esperado.get("alertas", [])) - set(r["alertas"])
        if faltan:
            fallos.append(f"{s['id']}: faltan alertas {sorted(faltan)}")
    return fallos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--series", type=Path, required=True)
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    fallos = correr_series(a.series)
    print("\n".join(fallos) if fallos else "series: todas coinciden")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
