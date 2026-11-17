"""Robot 6 · Alarma de cansancio (08:05), EN SOMBRA: últimos 3 días contra los 7 anteriores, por anuncio (``proponer.py fatiga`` de la skill D8).

Propone un relevo o un aviso; NO pide nada a D6, no pausa, no toca Meta. Sin los umbrales ``testeo.fatiga_*`` en ``parametros.yaml`` (con valor) devuelve
«sin decidir» y lista cuáles faltan. Alcance hoy: todos los anuncios de la oferta (la fuente lo limita a la campaña de escala, H-06, que aún no existe).
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from scripts.robots import d8
from scripts.robots.nucleo import Contexto, Resultado

ID = "alarma"
NO_ACCIONA = "PROPUESTA: no se pidió ningún relevo a D6 ni se tocó ningún anuncio."


def correr(c: Contexto) -> Resultado:
    u, fuente = d8.leer_umbrales(c)
    falta = d8.faltantes(c, u, d8.UMBRALES_FATIGA)
    with c.abrir_db() as conn:
        hay_base = conn is not None
        ofertas = d8.entradas_por_oferta(c, conn) if conn is not None else []
    if falta:
        extra = "" if hay_base else " Tampoco hay base de datos (empresa/datos/fabrica.db)."
        return Resultado("sin_decidir", f"sin decidir: faltan {len(falta)} umbral(es) de la alarma sin valor en parametros.yaml (lista en el resumen).{extra}"[:300],
                         [f"Sin esos umbrales no se detecta cansancio ni se propone ningún relevo (fail-closed).", f"Faltan: {', '.join(falta)}",
                          f"Fuente de umbrales: {fuente}.", NO_ACCIONA],
                         datos={"umbrales_faltantes": falta, "fuente_umbrales": fuente, "hay_base": hay_base, "ofertas_vistas": len([o for o in ofertas if o["oferta_id"]])})
    if not hay_base or not ofertas:
        motivo = "no hay base de datos (empresa/datos/fabrica.db)" if not hay_base else "la base no tiene ninguna oferta con anuncios"
        return Resultado("sin_datos", f"sin datos: {motivo}", [f"Sin datos no hay nada que comparar (3 días contra los 7 anteriores): {motivo}."],
                         datos={"fuente_umbrales": fuente, "hay_base": hay_base})
    if ofertas[0].get("base_incompleta"):
        return Resultado("sin_datos", f"sin datos: {ofertas[0]['motivo']}", [ofertas[0]["motivo"]], datos={"hay_base": True})
    proponer = d8.cargar(c, "proponer")
    cuenta: Counter[str] = Counter()
    por_oferta: list[dict[str, Any]] = []
    propuestas: list[dict[str, Any]] = []
    no_evaluables = 0
    for o in ofertas:
        if o["entrada"] is None:
            no_evaluables += 1
            por_oferta.append({"oferta_id": o["oferta_id"], "estado": "NO_EVALUABLE", "motivo": o["motivo"]})
            continue
        try:
            r = proponer.evaluar_fatiga(o["entrada"], u)
        except proponer.ErrorProponer as exc:
            no_evaluables += 1
            por_oferta.append({"oferta_id": o["oferta_id"], "estado": "NO_EVALUABLE", "motivo": str(exc)[:200]})
            continue
        anuncios = [{"ad_id": a.get("ad_id"), "concepto_id": a.get("concepto_id"), "estado": a["estado"], "codigo": a.get("codigo")} for a in r.get("anuncios", [])]
        cuenta.update(a["estado"] for a in anuncios)
        for p in r.get("propuestas", []):
            propuestas.append({"oferta_id": o["oferta_id"], **{k: p[k] for k in ("objeto_id", "accion_negocio", "codigo", "variable_a_variar", "cantidad_max_pedido") if k in p}})
        por_oferta.append({"oferta_id": o["oferta_id"], "estado": "EVALUADA", "anuncios": anuncios})
    n_anuncios = sum(cuenta.values())
    doc = {"tipo": "alarma_cansancio_sombra", "es_propuesta": True, "fecha": c.fecha_cuenta, "fuente_umbrales": fuente, "ofertas": por_oferta,
           "propuestas": propuestas, "conteo_anuncios": dict(sorted(cuenta.items())), "alcance": "todos los anuncios de la oferta (no solo la escala, H-06)"}
    salida = c.guardar(ID, doc)
    confirmadas = cuenta.get("FATIGA_CONFIRMADA", 0)
    una = cuenta.get("FATIGA_UNA_LECTURA", 0)
    insuf = cuenta.get("DATOS_INSUFICIENTES", 0)
    no_aplica = cuenta.get("NO_APLICA", 0)
    if confirmadas or una:
        estado = "alerta"
    elif cuenta.get("SIN_FATIGA", 0) == 0 and not insuf and not no_evaluables:
        estado = "sin_datos"            # nada evaluable (ningún anuncio con historial de ventas): no se afirma «sin fatiga» sin base
    elif insuf or no_evaluables:
        estado = "parcial"
    else:
        estado = "ok"
    resumen = [f"{n_anuncios} anuncio(s) en {len(por_oferta)} oferta(s): {confirmadas} con fatiga confirmada · {una} con una lectura · "
               f"{cuenta.get('SIN_FATIGA', 0)} sin fatiga · {cuenta.get('NO_APLICA', 0)} sin historial de ventas · {insuf} sin datos suficientes."]
    resumen += [f"  {p['oferta_id']} · anuncio {p['objeto_id']}: {p['accion_negocio']} ({p['codigo']})" for p in propuestas[:8]]
    resumen.append(NO_ACCIONA)
    return Resultado(estado, f"{confirmadas} fatiga confirmada, {una} sin confirmar, {insuf} sin datos suficientes, {no_aplica} sin historial de ventas, de {n_anuncios} anuncio(s); {NO_ACCIONA}"[:300],
                     resumen, datos=doc, salidas=[salida] if salida else [])
