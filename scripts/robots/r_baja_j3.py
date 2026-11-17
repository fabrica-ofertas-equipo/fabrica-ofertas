"""Trabajo de apoyo · Baja del día 1 (J3), EN SOMBRA: «un día sin venta, con el presupuesto del día gastado, se da de baja» (``proponer.py lanzamiento``).

Devuelve una PROPUESTA por oferta (APAGAR, MANTENER, PAUSAR_Y_ESCALAR o NO_DECIDIR); NO pausa nada ni toca Meta. Sin los umbrales ``lanzamiento.*``
(con valor en ``parametros.yaml``) devuelve «sin decidir» y lista cuáles faltan (hoy el grupo ``lanzamiento`` no existe en ``parametros.yaml``).
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from scripts.robots import d8
from scripts.robots.nucleo import Contexto, Resultado

ID = "baja_j3"
NO_ACCIONA = "PROPUESTA: no se pausó ni se dio de baja nada."


def correr(c: Contexto) -> Resultado:
    u, fuente = d8.leer_umbrales(c)
    falta = d8.faltantes(c, u, d8.UMBRALES_LANZAMIENTO)
    with c.abrir_db() as conn:
        hay_base = conn is not None
        ofertas = d8.entradas_por_oferta(c, conn) if conn is not None else []
    if falta:
        extra = "" if hay_base else " Tampoco hay base de datos (empresa/datos/fabrica.db)."
        return Resultado("sin_decidir", f"sin decidir: faltan {len(falta)} umbral(es) de la regla J3 sin valor en parametros.yaml (lista en el resumen).{extra}"[:300],
                         ["Sin esos umbrales no se propone ninguna baja (fail-closed, regla J3).", f"Faltan: {', '.join(falta)}",
                          f"Fuente de umbrales: {fuente}.", NO_ACCIONA],
                         datos={"umbrales_faltantes": falta, "fuente_umbrales": fuente, "hay_base": hay_base,
                                "ofertas_vistas": len([o for o in ofertas if o["oferta_id"]])})
    if not hay_base or not ofertas:
        motivo = "no hay base de datos (empresa/datos/fabrica.db)" if not hay_base else "la base no tiene ninguna oferta con anuncios"
        return Resultado("sin_datos", f"sin datos: {motivo}", [f"Sin datos no hay día que juzgar: {motivo}."], datos={"fuente_umbrales": fuente, "hay_base": hay_base})
    if ofertas[0].get("base_incompleta"):
        return Resultado("sin_datos", f"sin datos: {ofertas[0]['motivo']}", [ofertas[0]["motivo"]], datos={"hay_base": True})
    proponer = d8.cargar(c, "proponer")
    cuenta: Counter[str] = Counter()
    props: list[dict[str, Any]] = []
    for o in ofertas:
        if o["entrada"] is None:
            cuenta["NO_DECIDIR"] += 1
            props.append({"oferta_id": o["oferta_id"], "accion_negocio": "NO_DECIDIR", "codigo": "ENTRADA_NO_ARMADA", "explicacion": o["motivo"]})
            continue
        try:
            r = proponer.evaluar_lanzamiento(o["entrada"], u)
        except proponer.ErrorProponer as exc:
            cuenta["NO_DECIDIR"] += 1
            props.append({"oferta_id": o["oferta_id"], "accion_negocio": "NO_DECIDIR", "codigo": "ENTRADA_INVALIDA", "explicacion": str(exc)[:200]})
            continue
        cuenta[r["accion_negocio"]] += 1
        props.append({"oferta_id": o["oferta_id"], "accion_negocio": r["accion_negocio"], "accion_contrato": r["accion_contrato"], "codigo": r["codigo"],
                      "explicacion": r["explicacion"], "escalar_a": r.get("escalar_a"), "regla": r["regla"]})
    doc = {"tipo": "baja_j3_sombra", "es_propuesta": True, "fecha": c.fecha_cuenta, "fuente_umbrales": fuente, "propuestas": props,
           "conteo": dict(sorted(cuenta.items()))}
    salida = c.guardar(ID, doc)
    bajas = cuenta.get("APAGAR", 0) + cuenta.get("PAUSAR_Y_ESCALAR", 0)
    no_dec = cuenta.get("NO_DECIDIR", 0)
    if bajas:
        estado = "alerta"
    elif no_dec == len(props):
        estado = "sin_decidir"
    elif no_dec:
        estado = "parcial"
    else:
        estado = "ok"
    resumen = [f"{len(props)} oferta(s) juzgadas con el día {c.fecha_cuenta}: " + " · ".join(f"{k} {v}" for k, v in sorted(cuenta.items()))]
    resumen += [f"  {p['oferta_id']}: {p['accion_negocio']} ({p['codigo']})" for p in props[:8]]
    resumen.append(NO_ACCIONA)
    return Resultado(estado, f"{len(props)} oferta(s): " + ", ".join(f"{k} {v}" for k, v in sorted(cuenta.items())) + f"; {NO_ACCIONA}", resumen,
                     datos=doc, salidas=[salida] if salida else [])
