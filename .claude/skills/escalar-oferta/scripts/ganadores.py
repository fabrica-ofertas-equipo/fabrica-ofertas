#!/usr/bin/env python3
"""¿Sobre qué anuncios se itera y cuántas iteraciones lleva cada uno? (renovación diaria, paso 1).

Pedido del dueño (2026-11-14): «puede ser que tengamos muchos ganadores y tengamos que iterar entre todos… en algún momento
tendremos más winners que anuncios que vamos a sacar… hay que contemplar todas esas situaciones y hacerlo robusto, pero seguir
dándole con fuerza a iterar sobre lo que más está funcionando». Antes: un solo «ganador» = más compras en 3 días (1 compra
contra 0 alcanzaba) y las 7 iteraciones iban todas ahí; el segundo mejor nunca recibía nada.

Datos: cada anuncio de la campaña con compras, gasto, pagos iniciados e impresiones de los últimos 3 días (y, si en 3 días hay
pocas compras, desde el inicio). Se juntan los de todos los conjuntos: un mismo anuncio en dos conjuntos suma.

Clases (equilibrio = lo que deja cada venta, del libro):
  · GANADOR: ≥ COMPRAS_GANADOR compras y CPA ≤ equilibrio.
  · PROMETE: 1 compra con CPA ≤ equilibrio, o ≥ 2 compras con CPA hasta 1,2 × equilibrio.
  · Sin compras: no es candidato, salvo que no haya ninguna compra en toda la campaña (entonces, los de más pagos iniciados
    por dólar, con ≥ US$ 2 gastados).
Puntaje = compras × eficiencia, con eficiencia = equilibrio / CPA (tope 2): premia vender mucho Y barato.

Reparto de las iteraciones (7 por defecto; 3 si la ronda va con conceptos nuevos):
  1. Sin ganadores ni promesas: los 2 mejores por pagos iniciados por dólar, 4 + 3 (o todo al único que haya).
  2. Un ganador solo: 5 para él y 2 para el mejor que promete (si no hay, las 7 para él).
  3. Varios ganadores: entran como mucho MAX_RAMAS (4) por puntaje; el reparto es proporcional a puntaje^1,5 (exagera la
     diferencia: más fuerza al mejor), con piso de 1 por rama y el primero con al menos MIN_PRIMERO (3) y nunca menos que
     otro. Los que quedan afuera se informan: si ya hay más ganadores que lugares, se itera sobre los 4 de más puntaje y los
     demás siguen corriendo sin tocar (no se apagan).
  4. Ramas de la misma familia (iteraciones de un mismo anuncio padre, campo `familia`): cuentan como ramas distintas solo si
     ambas ganan; así no se concentra todo en un concepto por accidente, pero si la familia vende, se la sigue.
Siempre se dice por qué.

Uso: python3 ganadores.py --lectura <json: lista de anuncios> --equilibrio <USD> [--iteraciones 7] [--json]
Lista: [{id, nombre, conjunto?, familia?, gasto_usd, compras, inicios_pago, impresiones?, compras_inicio?, gasto_inicio?}]
(acepta también las claves del panel: compras_meta, inicios_pago_meta).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

COMPRAS_GANADOR = 2
MAX_RAMAS = 4
MIN_PRIMERO = 3
GASTO_MINIMO = 2.0
EFICIENCIA_TOPE = 2.0
POCAS_COMPRAS_3D = 3   # con menos compras en 3 días en toda la campaña, se mira desde el inicio


def _n(x) -> float:
    try:
        return float(x) if x not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def normalizar(lista: list[dict]) -> list[dict]:
    """Junta un mismo anuncio que corre en varios conjuntos y unifica nombres de campos."""
    por_id: dict[str, dict] = {}
    for a in lista or []:
        if not isinstance(a, dict):
            continue
        clave = str(a.get("id") or a.get("nombre"))
        x = por_id.setdefault(clave, {"id": a.get("id"), "nombre": a.get("nombre"), "familia": a.get("familia"), "conjuntos": [],
                                      "gasto": 0.0, "compras": 0.0, "inicios_pago": 0.0, "gasto_inicio": 0.0, "compras_inicio": 0.0})
        if a.get("conjunto"):
            x["conjuntos"].append(a.get("conjunto"))
        x["gasto"] += _n(a.get("gasto_usd", a.get("gasto")))
        x["compras"] += _n(a.get("compras", a.get("compras_meta")))
        x["inicios_pago"] += _n(a.get("inicios_pago", a.get("inicios_pago_meta")))
        x["gasto_inicio"] += _n(a.get("gasto_inicio"))
        x["compras_inicio"] += _n(a.get("compras_inicio"))
    return list(por_id.values())


def clasificar(anuncios: list[dict], equilibrio: float) -> tuple[list[dict], str]:
    """Agrega clase, CPA y puntaje a cada anuncio. Devuelve (anuncios, ventana usada)."""
    total_3d = sum(a["compras"] for a in anuncios)
    usa_inicio = total_3d < POCAS_COMPRAS_3D and any(a["compras_inicio"] > a["compras"] for a in anuncios)
    for a in anuncios:
        compras, gasto = (a["compras_inicio"], a["gasto_inicio"]) if usa_inicio and a["compras_inicio"] else (a["compras"], a["gasto"])
        a["compras_usadas"], a["gasto_usado"] = compras, gasto
        a["cpa"] = round(gasto / compras, 2) if compras else None
        ef = min(EFICIENCIA_TOPE, equilibrio / a["cpa"]) if a["cpa"] else 0.0
        a["puntaje"] = round(compras * ef, 3)
        if compras >= COMPRAS_GANADOR and a["cpa"] is not None and a["cpa"] <= equilibrio:
            a["clase"] = "ganador"
        elif (compras == 1 and a["cpa"] is not None and a["cpa"] <= equilibrio) or (compras >= COMPRAS_GANADOR and a["cpa"] is not None and a["cpa"] <= 1.2 * equilibrio):
            a["clase"] = "promete"
        else:
            a["clase"] = "sin_compras" if not compras else "caro"
        a["pagos_por_dolar"] = round(a["inicios_pago"] / a["gasto"], 3) if a["gasto"] >= GASTO_MINIMO else 0.0
    return anuncios, ("desde el inicio (en 3 días hubo menos de 3 compras)" if usa_inicio else "últimos 3 días")


def _redondeo(pesos: list[float], total: int, piso: int = 1) -> list[int]:
    """Reparte `total` en enteros proporcionales a `pesos`, con piso; restos mayores primero."""
    n = len(pesos)
    if n == 0:
        return []
    base = [piso] * n
    resto = total - piso * n
    if resto <= 0:
        return base[:total] + [0] * (n - total) if total < n else base
    s = sum(pesos) or n
    crudo = [resto * p / s for p in pesos]
    enteros = [math.floor(c) for c in crudo]
    falta = resto - sum(enteros)
    for i in sorted(range(n), key=lambda i: crudo[i] - enteros[i], reverse=True)[:falta]:
        enteros[i] += 1
    return [b + e for b, e in zip(base, enteros)]


def repartir(lista: list[dict], equilibrio: float, iteraciones: int = 7) -> dict:
    anuncios, ventana = clasificar(normalizar(lista), equilibrio)
    gan = sorted([a for a in anuncios if a["clase"] == "ganador"], key=lambda a: (-a["puntaje"], a["cpa"] or 0))
    pro = sorted([a for a in anuncios if a["clase"] == "promete"], key=lambda a: (-a["puntaje"], a["cpa"] or 0))
    ramas: list[tuple[dict, int, str]] = []
    if not gan and not pro:
        cand = sorted([a for a in anuncios if a["compras_usadas"] or a["pagos_por_dolar"]], key=lambda a: (-a["compras_usadas"], -a["pagos_por_dolar"]))[:2]
        if not cand:
            return {"escenario": "sin_datos", "ventana": ventana, "ramas": [], "afuera": [],
                    "explicacion": "Ningún anuncio tiene compras ni pagos iniciados con US$ 2 gastados: no hay de qué iterar; la ronda va con conceptos nuevos."}
        cuotas = [iteraciones] if len(cand) == 1 else [math.ceil(iteraciones / 2), iteraciones // 2]
        ramas = [(a, c, "mejor por compras o pagos iniciados por dólar, sin ganador todavía") for a, c in zip(cand, cuotas)]
        escenario, expl = "sin_ganador", "Todavía no hay ganador (2+ compras bajo el equilibrio): se reparte entre los dos que más prometen."
    elif len(gan) <= 1:
        top = gan[0] if gan else pro[0]
        segundo = (pro if gan else pro[1:])[:1]
        if segundo:
            ramas = [(top, iteraciones - 2, "ganador" if gan else "el que más promete"), (segundo[0], 2, "segundo: promete")]
        else:
            ramas = [(top, iteraciones, "ganador único" if gan else "el único que promete")]
        escenario = "un_ganador" if gan else "solo_promesas"
        expl = ("Un solo ganador: lleva la fuerza y el segundo mejor recibe 2 para no depender de una rama." if gan
                else "Nadie llega a 2 compras bajo el equilibrio: va el que más promete, con 2 para el segundo si existe.")
    else:
        elegidos = gan[:min(MAX_RAMAS, iteraciones)]
        pesos = [a["puntaje"] ** 1.5 for a in elegidos]
        cuotas = _redondeo(pesos, iteraciones)
        if cuotas[0] < MIN_PRIMERO and iteraciones >= MIN_PRIMERO + len(elegidos) - 1:   # el mejor, con fuerza
            while cuotas[0] < MIN_PRIMERO:
                j = max(range(1, len(cuotas)), key=lambda k: (cuotas[k], -k))
                if cuotas[j] <= 1:
                    break
                cuotas[j] -= 1
                cuotas[0] += 1
        for i in range(1, len(cuotas)):   # nunca otro con más que el mejor
            if cuotas[i] > cuotas[0]:
                cuotas[0], cuotas[i] = cuotas[i], cuotas[0]
        ramas = [(a, c, f"ganador #{i + 1}") for i, (a, c) in enumerate(zip(elegidos, cuotas)) if c > 0]
        escenario = "varios_ganadores" if len(gan) <= MAX_RAMAS else "mas_ganadores_que_lugares"
        expl = (f"{len(gan)} ganadores: el reparto sigue al puntaje (compras × eficiencia), con el mejor al frente."
                + (f" Hay más ganadores que lugares: se itera sobre los {len(elegidos)} de más puntaje; los demás siguen corriendo sin tocar." if len(gan) > len(elegidos) else ""))
    usados = {id(a) for a, _, _ in ramas}
    afuera = [a for a in gan + pro if id(a) not in usados]
    def fila(a, c=None, por=None):
        return {"id": a["id"], "nombre": a["nombre"], "iteraciones": c, "por": por, "clase": a["clase"], "compras": a["compras_usadas"],
                "cpa": a["cpa"], "puntaje": a["puntaje"], "familia": a.get("familia")}
    return {"escenario": escenario, "ventana": ventana, "equilibrio": equilibrio, "iteraciones": iteraciones,
            "ramas": [fila(a, c, p) for a, c, p in ramas], "afuera": [fila(a) for a in afuera], "explicacion": expl}


def _probar() -> None:
    E = 40.0
    a = lambda i, c, g, p=0: {"id": i, "nombre": i, "compras": c, "gasto_usd": g, "inicios_pago": p}
    r = repartir([a("A", 8, 120), a("B", 1, 30, 4), a("C", 0, 20, 1)], E)
    assert r["escenario"] == "un_ganador" and [x["iteraciones"] for x in r["ramas"]] == [5, 2], r
    r = repartir([a("A", 1, 20, 3), a("B", 0, 25, 6), a("C", 0, 10, 0)], E)
    assert r["escenario"] == "solo_promesas" and r["ramas"][0]["id"] == "A" and r["ramas"][0]["iteraciones"] == 7, r
    r = repartir([a("A", 0, 25, 6), a("B", 0, 25, 2), a("C", 0, 1, 1)], E)
    assert r["escenario"] == "sin_ganador" and [x["iteraciones"] for x in r["ramas"]] == [4, 3], r
    r = repartir([a("A", 10, 150), a("B", 4, 80), a("C", 3, 110)], E)
    c = [x["iteraciones"] for x in r["ramas"]]
    assert r["escenario"] == "varios_ganadores" and sum(c) == 7 and c[0] >= 3 and c[0] == max(c) and min(c) >= 1, r
    r = repartir([a(str(i), 10 - i, 100) for i in range(7)], E)
    c = [x["iteraciones"] for x in r["ramas"]]
    assert r["escenario"] == "mas_ganadores_que_lugares" and len(c) == 4 and sum(c) == 7 and c[0] >= 3 and len(r["afuera"]) == 3, r
    r = repartir([a("A", 5, 60), a("B", 5, 60)], E, iteraciones=3)
    assert sum(x["iteraciones"] for x in r["ramas"]) == 3, r
    r = repartir([a("A", 3, 200)], E)   # vende pero caro (CPA 66 > 1,2 × 40): no es ganador, igual es lo único que hay
    assert r["escenario"] == "sin_ganador" and r["ramas"][0]["clase"] == "caro" and r["ramas"][0]["iteraciones"] == 7, r
    r = repartir([{"id": "A", "nombre": "A", "conjunto": "R1", "compras": 1, "gasto_usd": 20}, {"id": "A", "nombre": "A", "conjunto": "R2", "compras": 2, "gasto_usd": 30}], E)
    assert r["ramas"][0]["compras"] == 3 and r["escenario"] == "un_ganador", r
    r = repartir([], E)
    assert r["escenario"] == "sin_datos", r
    print("ok: 9 escenarios")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lectura")
    ap.add_argument("--equilibrio", type=float)
    ap.add_argument("--iteraciones", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--probar", action="store_true")
    a = ap.parse_args(argv)
    if a.probar:
        _probar()
        return 0
    if not a.lectura or not a.equilibrio:
        ap.error("--lectura y --equilibrio son obligatorios")
    datos = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
    lista = datos.get("anuncios", datos.get("ad_entities", datos)) if isinstance(datos, dict) else datos
    r = repartir(lista, a.equilibrio, a.iteraciones)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"{r['escenario']} · {r['ventana']} · {r['explicacion']}")
        for x in r["ramas"]:
            print(f"  {x['iteraciones']} iteraci{'ón' if x['iteraciones'] == 1 else 'ones'} → {x['nombre']} ({x['por']}; {x['compras']:.0f} compras, CPA {x['cpa']}, puntaje {x['puntaje']})")
        for x in r["afuera"]:
            print(f"  sin iterar esta ronda: {x['nombre']} ({x['clase']}, {x['compras']:.0f} compras, CPA {x['cpa']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
