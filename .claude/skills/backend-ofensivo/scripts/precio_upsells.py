"""Precio de los upsells que aprende solo (pedido del dueño, 2026-11-13: «armar algo robusto automático, con criterio,
que tenga sentido y que aprenda en base a datos»).

Qué busca: el precio que deja MÁS PLATA POR COMPRADOR QUE VE LA OFERTA (precio × probabilidad de aceptar), no el que más
gente acepta. Un upsell a MX$ 399 que acepta el 12 % (47,9 por comprador) gana a uno a MX$ 199 que acepta el 20 % (39,8).

Cómo aprende:
  · Escalera de 5 precios alrededor del precio inicial que fijó la fase 1 (×0,70, ×0,85, ×1, ×1,20, ×1,40), terminados
    como los precios del mercado (…9). Impultienda muestra un precio a la vez, así que se prueba POR TANDAS: un precio queda
    hasta juntar 30 vistas nuevas y recién ahí se decide el siguiente.
  · Muestreo de Thompson con una Beta por precio (aceptadas / vistas): elige el siguiente precio sorteando qué tan bueno
    puede ser cada uno según lo visto. Prueba más lo que promete y abandona lo que no rinde, sin dejar de explorar.
  · Criterio: se mueve de a un escalón (sin saltos raros), salvo que otro precio sea el mejor con ≥ 80 % de probabilidad.
    Con ≥ 120 vistas y un precio mejor con ≥ 90 % → CONSOLIDADO (se deja; vuelve a probar un escalón cada 300 vistas).
    Si el precio más bajo tiene 0 aceptadas en 60 vistas → CAMBIAR_PRODUCTO (el problema no es el precio).
  · Aprende entre ofertas: guarda la aceptación por «precio ÷ precio del principal» y por posición en el embudo; eso es el
    punto de partida (prior, con un peso máximo de 20 vistas) de cada upsell nuevo.

Archivos: empresa/backend/precios.json (estado por oferta y upsell) y empresa/backend/aprendizaje.json (lo que aprendió).

Uso (desde la raíz; P=.claude/skills/backend-ofensivo/scripts/precio_upsells.py):
  python3 $P alta OFERTA UPSELL --precio 399 --moneda MXN --principal 319 --posicion 1 [--usd-por-unidad 0.054]
  python3 $P leer OFERTA UPSELL --vistas 140 --aceptadas 17      totales ACUMULADOS de la analítica del embudo
  python3 $P decidir [OFERTA] [--json]                           qué precio dejar o cambiar, con el porqué
  python3 $P aplicado OFERTA UPSELL --precio 349                 el precio que quedó cargado en Impultienda
  python3 $P estado [--json]
Sin red. Solo decide: el cambio de precio en Impultienda lo hace el agente (guía 02, «Precios por mercado»).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
DIR = RAIZ / "empresa" / "backend"
ESTADO = DIR / "precios.json"
APRENDIZAJE = DIR / "aprendizaje.json"

ESCALERA = (0.70, 0.85, 1.00, 1.20, 1.40)
VISTAS_TANDA = 30          # vistas nuevas antes de decidir el siguiente precio
VISTAS_CONSOLIDAR = 120    # vistas totales mínimas para dar un precio por bueno
P_SALTO = 0.80             # probabilidad de ser el mejor para saltar más de un escalón
P_CONSOLIDAR = 0.90
REVISAR_CADA = 300         # ya consolidado: cada tantas vistas se prueba un escalón vecino
VISTAS_SIN_VENTA = 60      # en el precio más bajo, con 0 aceptadas → el problema es el producto
PRIOR_PESO_MAX = 20        # vistas «virtuales» que aporta lo aprendido en otras ofertas
PRIOR_DEFECTO = (1.0, 9.0) # sin historia: ≈ 10 % de aceptación, muy poco peso
SORTEOS = 4000
TRAMOS_RAZON = ((0, 0.8, "<0,8"), (0.8, 1.2, "0,8-1,2"), (1.2, 1.6, "1,2-1,6"), (1.6, 99, ">1,6"))


def _leer(p: Path, defecto):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def _escribir(p: Path, dato) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(dato, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def precio_de_mercado(valor: float, moneda: str) -> float:
    """Redondea como un precio de tienda: MXN, BRL y demás monedas «grandes», al 9 más cercano (349, 1.299); USD/EUR, a entero."""
    if moneda.upper() in ("USD", "EUR", "GBP", "CHF", "CAD", "AUD", "NZD", "SGD"):
        return float(max(1, int(round(valor))))
    paso = 10 if valor < 2000 else 100
    return float(max(paso - 1, int(round((valor + 1) / paso)) * paso - 1))


def tramo_razon(razon: float) -> str:
    return next(t for a, b, t in TRAMOS_RAZON if a <= razon < b)


def prior_para(aprend: dict, razon: float, posicion: int) -> tuple[float, float]:
    """Beta(a, b) desde lo aprendido en otras ofertas para ese tramo de precio/principal y posición, con peso acotado."""
    k = f"{tramo_razon(razon)}|{posicion}"
    d = aprend.get("tramos", {}).get(k) or aprend.get("tramos", {}).get(f"{tramo_razon(razon)}|*")
    if not d or not d.get("vistas"):
        return PRIOR_DEFECTO
    tasa = (d["aceptadas"] + 0.5) / (d["vistas"] + 1)
    peso = min(PRIOR_PESO_MAX, d["vistas"])
    return (max(0.5, tasa * peso), max(0.5, (1 - tasa) * peso))


def alta(estado: dict, aprend: dict, oferta: str, upsell: str, precio: float, moneda: str, principal: float, posicion: int,
         usd_por_unidad: float | None, ahora: dt.datetime) -> dict:
    brazos = []
    for m in ESCALERA:
        p = precio if m == 1.0 else precio_de_mercado(precio * m, moneda)
        if any(abs(b["precio"] - p) < 1e-9 for b in brazos):
            continue
        a, b = prior_para(aprend, p / principal if principal else 1.0, posicion)
        brazos.append({"precio": p, "mult": m, "vistas": 0, "aceptadas": 0, "prior": [round(a, 3), round(b, 3)]})
    u = {"oferta": oferta, "upsell": upsell, "moneda": moneda, "principal": principal, "posicion": posicion,
         "usd_por_unidad": usd_por_unidad, "brazos": sorted(brazos, key=lambda x: x["precio"]), "actual": precio,
         "ultimo_total": {"vistas": 0, "aceptadas": 0}, "tanda_desde": 0, "estado": "probando", "cambios": [],
         "alta": ahora.isoformat(timespec="minutes")}
    estado.setdefault(oferta, {})[upsell] = u
    return u


def _brazo(u: dict, precio: float) -> dict:
    return min(u["brazos"], key=lambda b: abs(b["precio"] - precio))


def leer(u: dict, vistas_total: int, aceptadas_total: int) -> dict:
    """Atribuye al precio ACTUAL lo nuevo desde la última lectura (la analítica da totales acumulados)."""
    ult = u["ultimo_total"]
    dv, da = vistas_total - ult["vistas"], aceptadas_total - ult["aceptadas"]
    if dv < 0 or da < 0 or da > dv:
        raise SystemExit("Los totales bajaron o hay más aceptadas que vistas: revisar la lectura de la analítica.")
    b = _brazo(u, u["actual"])
    b["vistas"] += dv
    b["aceptadas"] += da
    u["ultimo_total"] = {"vistas": vistas_total, "aceptadas": aceptadas_total}
    return {"vistas_nuevas": dv, "aceptadas_nuevas": da, "precio": u["actual"]}


def posteriores(u: dict, rng: random.Random) -> list[dict]:
    """Por precio: ingreso esperado por vista (precio × p), probabilidad de ser el mejor (Monte Carlo) y la media de p."""
    bs = u["brazos"]
    gana = [0] * len(bs)
    for _ in range(SORTEOS):
        vals = [b["precio"] * rng.betavariate(b["prior"][0] + b["aceptadas"], b["prior"][1] + b["vistas"] - b["aceptadas"]) for b in bs]
        gana[vals.index(max(vals))] += 1
    out = []
    for b, g in zip(bs, gana):
        a, c = b["prior"][0] + b["aceptadas"], b["prior"][1] + b["vistas"] - b["aceptadas"]
        p = a / (a + c)
        out.append({"precio": b["precio"], "vistas": b["vistas"], "aceptadas": b["aceptadas"], "acepta_pct": round(100 * p, 1),
                    "por_vista": round(b["precio"] * p, 2), "p_mejor": round(g / SORTEOS, 3)})
    return out


def decidir(u: dict, rng: random.Random) -> dict:
    post = posteriores(u, rng)
    idx = next(i for i, b in enumerate(u["brazos"]) if abs(b["precio"] - u["actual"]) < 1e-9) if any(abs(b["precio"] - u["actual"]) < 1e-9 for b in u["brazos"]) else 2
    actual = u["brazos"][idx]
    total = sum(b["vistas"] for b in u["brazos"])
    tanda = u["ultimo_total"]["vistas"] - u["tanda_desde"]
    mejor = max(range(len(post)), key=lambda i: post[i]["p_mejor"])
    base = {"oferta": u["oferta"], "upsell": u["upsell"], "precio_actual": u["actual"], "vistas_totales": total, "tanda": tanda, "precios": post}
    minimo = u["brazos"][0]
    if minimo["vistas"] >= VISTAS_SIN_VENTA and minimo["aceptadas"] == 0 and all(b["aceptadas"] == 0 for b in u["brazos"]):
        return {**base, "decision": "CAMBIAR_PRODUCTO", "porque": f"Nadie aceptó ni al precio más bajo ({minimo['precio']:g}) en {minimo['vistas']} vistas: el problema es el producto, no el precio."}
    if tanda < VISTAS_TANDA:
        return {**base, "decision": "MANTENER", "porque": f"Tanda en curso: {tanda} de {VISTAS_TANDA} vistas al precio {u['actual']:g}."}
    if total >= VISTAS_CONSOLIDAR and post[mejor]["p_mejor"] >= P_CONSOLIDAR:
        if u["estado"] == "consolidado" and tanda >= REVISAR_CADA:
            vecino = idx + (1 if idx + 1 < len(post) and (idx == 0 or rng.random() < 0.5) else -1)
            return {**base, "decision": "CAMBIAR", "precio_nuevo": u["brazos"][vecino]["precio"], "consolidado": True,
                    "porque": f"Consolidado en {u['actual']:g}; cada {REVISAR_CADA} vistas se vuelve a probar un escalón vecino por si el mercado cambió."}
        if mejor == idx:
            return {**base, "decision": "CONSOLIDADO", "porque": f"{u['actual']:g} es el mejor con {post[mejor]['p_mejor'] * 100:.0f} % de probabilidad ({post[mejor]['por_vista']:g} por comprador que ve la oferta)."}
    # muestreo de Thompson, de a un escalón salvo evidencia fuerte
    sorteo = [b["precio"] * rng.betavariate(b["prior"][0] + b["aceptadas"], b["prior"][1] + b["vistas"] - b["aceptadas"]) for b in u["brazos"]]
    elegido = sorteo.index(max(sorteo))
    if abs(elegido - idx) > 1 and post[elegido]["p_mejor"] < P_SALTO:
        elegido = idx + (1 if elegido > idx else -1)
    if elegido == idx:
        return {**base, "decision": "MANTENER", "porque": f"El sorteo vuelve a elegir {u['actual']:g}: sigue siendo el más prometedor ({post[idx]['por_vista']:g} por vista)."}
    return {**base, "decision": "CAMBIAR", "precio_nuevo": u["brazos"][elegido]["precio"],
            "porque": f"Tras {tanda} vistas a {u['actual']:g}, probar {u['brazos'][elegido]['precio']:g} (prob. de ser el mejor {post[elegido]['p_mejor'] * 100:.0f} %, {post[elegido]['por_vista']:g} por vista esperado)."}


def aplicado(u: dict, precio: float, ahora: dt.datetime, consolidado: bool = False) -> None:
    u["cambios"].append({"cuando": ahora.isoformat(timespec="minutes"), "de": u["actual"], "a": precio})
    u["actual"] = _brazo(u, precio)["precio"]
    u["tanda_desde"] = u["ultimo_total"]["vistas"]
    if consolidado:
        u["estado"] = "consolidado"


def actualizar_aprendizaje(estado: dict) -> dict:
    """Recalcula lo aprendido sumando todas las ofertas: aceptación por tramo de precio/principal y posición."""
    tramos: dict[str, dict] = {}
    for ups in estado.values():
        for u in ups.values():
            for b in u["brazos"]:
                if not b["vistas"]:
                    continue
                r = tramo_razon(b["precio"] / u["principal"] if u.get("principal") else 1.0)
                for k in (f"{r}|{u['posicion']}", f"{r}|*"):
                    t = tramos.setdefault(k, {"vistas": 0, "aceptadas": 0})
                    t["vistas"] += b["vistas"]
                    t["aceptadas"] += b["aceptadas"]
    return {"actualizado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "tramos": tramos}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Precio de los upsells que aprende solo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("alta"); a1.add_argument("oferta"); a1.add_argument("upsell"); a1.add_argument("--precio", type=float, required=True)
    a1.add_argument("--moneda", required=True); a1.add_argument("--principal", type=float, required=True); a1.add_argument("--posicion", type=int, default=1)
    a1.add_argument("--usd-por-unidad", type=float)
    a2 = sub.add_parser("leer"); a2.add_argument("oferta"); a2.add_argument("upsell"); a2.add_argument("--vistas", type=int, required=True); a2.add_argument("--aceptadas", type=int, required=True)
    a3 = sub.add_parser("decidir"); a3.add_argument("oferta", nargs="?"); a3.add_argument("--json", action="store_true"); a3.add_argument("--semilla", type=int)
    a4 = sub.add_parser("aplicado"); a4.add_argument("oferta"); a4.add_argument("upsell"); a4.add_argument("--precio", type=float, required=True); a4.add_argument("--consolidado", action="store_true")
    a5 = sub.add_parser("estado"); a5.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    ahora = dt.datetime.now(dt.timezone.utc)
    estado, aprend = _leer(ESTADO, {}), _leer(APRENDIZAJE, {})

    def u_de(o: str, n: str) -> dict:
        try:
            return estado[o][n]
        except KeyError:
            raise SystemExit(f"No está {o} / {n}: darlo de alta primero.") from None

    if a.cmd == "alta":
        u = alta(estado, aprend, a.oferta, a.upsell, a.precio, a.moneda, a.principal, a.posicion, a.usd_por_unidad, ahora)
        _escribir(ESTADO, estado)
        escalera = ", ".join("%g" % b["precio"] for b in u["brazos"])
        print(f"{a.oferta} / {a.upsell}: escalera {escalera} {a.moneda}; empieza en {a.precio:g}.")
    elif a.cmd == "leer":
        r = leer(u_de(a.oferta, a.upsell), a.vistas, a.aceptadas)
        _escribir(ESTADO, estado)
        _escribir(APRENDIZAJE, actualizar_aprendizaje(estado))
        print(f"+{r['vistas_nuevas']} vistas, +{r['aceptadas_nuevas']} aceptadas al precio {r['precio']:g}.")
    elif a.cmd == "decidir":
        rng = random.Random(a.semilla if a.semilla is not None else int(ahora.strftime("%Y%m%d")))
        res = [decidir(u, rng) for o, ups in estado.items() if not a.oferta or o == a.oferta for u in ups.values()]
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            for r in res:
                print(f"{r['oferta']} / {r['upsell']}: {r['decision']}" + (f" → {r['precio_nuevo']:g}" if r.get("precio_nuevo") else "") + f" · {r['porque']}")
    elif a.cmd == "aplicado":
        aplicado(u_de(a.oferta, a.upsell), a.precio, ahora, a.consolidado)
        _escribir(ESTADO, estado)
        print(f"{a.oferta} / {a.upsell}: precio {a.precio:g} cargado; empieza una tanda nueva.")
    elif a.cmd == "estado":
        if a.json:
            print(json.dumps({"precios": estado, "aprendizaje": aprend}, ensure_ascii=False, indent=1))
        else:
            for o, ups in estado.items():
                for n, u in ups.items():
                    tot = sum(b["vistas"] for b in u["brazos"])
                    print(f"{o} / {n}: {u['actual']:g} {u['moneda']} · {u['estado']} · {tot} vistas · " + ", ".join(f"{b['precio']:g}:{b['aceptadas']}/{b['vistas']}" for b in u["brazos"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
