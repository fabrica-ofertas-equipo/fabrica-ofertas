#!/usr/bin/env python3
"""Ranking reproducible de mercados (modelo de docs/_investigacion/08-mercados-ranking.md).

Solo biblioteca estándar. Datos versionados en scripts/mercados/datos/*.json. Salida determinista.

Qué hace
  1. Reproduce los 15 totales de 08 §2.2 desde los puntajes publicados.
  2. Recalcula el puntaje de costo de adquisición (CAC) con la regla de 08 §2.1
     (r = CPA esperado / neto) y lo contrasta con el publicado (inconsistencia de Suiza, 17 H1).
  3. Corre escenarios (neto completo, CPM de Q4, CTR, ticket, sin pagos, escala, ajuste de creadores)
     y mide la estabilidad del orden (top-3, top-5, Italia vs Polonia, correlación de rangos).

Uso (desde la raíz del repositorio):
  python3 -I scripts/mercados/rank.py                       # reproducción de 08 + verificaciones
  python3 -I scripts/mercados/rank.py --lista               # escenarios disponibles
  python3 -I scripts/mercados/rank.py --escenario corregido # un escenario
  python3 -I scripts/mercados/rank.py --todos               # resumen de todos los escenarios
  python3 -I scripts/mercados/rank.py --grid                # rejilla factorial y frecuencia en el top
  python3 -I scripts/mercados/rank.py --exportar resultados/escenarios.json

No sustituye a M1: casi todos los insumos son confianza C (08 §2.1, 16).
"""
import argparse
import copy
import importlib.util
import itertools
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, "datos")
CRITERIOS = ["PA", "CAC", "COMP", "PAGO", "FISC", "LOC", "FRAUD"]
INGLES_27 = ("CA", "NZ", "AU", "US", "GB")


# --------------------------------------------------------------------------- datos
def cargar_datos(dir_datos=DATOS):
    with open(os.path.join(dir_datos, "parametros.json"), encoding="utf-8") as f:
        par = json.load(f)
    with open(os.path.join(dir_datos, "mercados.json"), encoding="utf-8") as f:
        mer = json.load(f)
    return par, mer["mercados"], mer["fuera_top15_08"]


# --------------------------------------------------------------------------- escenarios
def escenario_base(**kw):
    """Escenario por defecto = modelo de 08 tal cual (puntajes CAC y PAGO publicados)."""
    e = {
        "descripcion": "",
        "ctr": 0.018,                 # CTR de enlace (08 §5)
        "cpm_mult": 1.0,              # multiplicador de CPM (Q4)
        "ticket": {},                 # {codigo: usd} reemplazos de ticket
        "neto": "08",                 # "08" o "completo"
        "reembolso": 0.08, "disputa": 0.006, "stripe_tax": "pct",  # "pct" | "fijo" | "ninguno"
        "cac_modo": "publicado",      # "publicado" o "derivado" (regla de r)
        "pago_modo": "publicado",     # "publicado" o "derivado" (cobertura)
        "comision": "metodo",         # "metodo" (como 08) o "tarjeta" (sin depender del método local)
        "pesos": None,                # None = pesos de 08; dict para reemplazar (se normaliza a 100)
        "excluir": [],                # criterios que se sacan (ej. ["PAGO"]); pesos restantes se reescalan a 100
        "escala_peso": 0,             # peso del criterio de escala (0 = no se usa)
        "ajuste": "08",               # "08", "regla" o "ninguno"
        "iva": {},                    # {codigo: tasa} reemplazos de IVA
    }
    e.update(kw)
    return e


def definir_escenarios():
    S = {}
    S["08_publicado"] = escenario_base(descripcion="Reproducción de 08 §2.2 con los puntajes publicados (CAC y PAGO publicados).")
    S["08_derivado"] = escenario_base(descripcion="Modelo de 08 con CAC y PAGO derivados de sus reglas y parámetros (§2.1).",
                                      cac_modo="derivado", pago_modo="derivado")
    d = dict(cac_modo="derivado", pago_modo="derivado")
    S["neto_completo_pct"] = escenario_base(descripcion="Neto completo: Stripe Tax 0,5 %, reembolsos 8 %, disputas 0,6 % x 15 USD (16 H1).",
                                            neto="completo", stripe_tax="pct", **d)
    S["neto_completo_api"] = escenario_base(descripcion="Neto completo con Stripe Tax por API (0,50 USD fijos).",
                                            neto="completo", stripe_tax="fijo", **d)
    for mult in (1.2, 1.5):
        S[f"cpm_q4_x{str(mult).replace('.', '_')}"] = escenario_base(
            descripcion=f"CPM de Q4 x{mult} (Black Friday 2026-11-27; 16 M1), resto como 08.", cpm_mult=mult, **d)
    for ctr in (0.010, 0.013):
        S[f"ctr_{str(ctr * 100).replace('.', '_')[:3]}"] = escenario_base(
            descripcion=f"CTR de enlace {str(ctr * 100).replace('.', ',')[:3]} % (08 usa 1,8 %; 16 M2 recomienda 1,3 %).", ctr=ctr, **d)
    S["ctr_1_8"] = escenario_base(descripcion="CTR 1,8 % (valor de 08) con CAC derivado: referencia para los demás CTR.", **d)
    S["ticket_ingles_17"] = escenario_base(descripcion="Ticket de 17 USD en CA/NZ/AU/US/GB (IE conserva 23); 08 §2.5.",
                                           ticket={c: 17.0 for c in INGLES_27}, **d)
    S["ticket_ingles_17_con_IE"] = escenario_base(descripcion="Ticket de 17 USD en el bloque inglés incluida Irlanda (borde: IE cae de 2 a 1).",
                                                  ticket={**{c: 17.0 for c in INGLES_27}, "IE": 17.0}, **d)
    S["sin_pagos"] = escenario_base(descripcion="Sin el criterio de pagos, pesos reescalados a 100 (equivale a rank_sin_pagos.py; CAC publicado).",
                                    excluir=["PAGO"])
    S["sin_pagos_comision_tarjeta"] = escenario_base(
        descripcion="Sin pagos y sin comisiones por método local (BLIK/MB WAY/Bancontact -> tarjeta); CAC derivado.",
        excluir=["PAGO"], comision="tarjeta", cac_modo="derivado")
    S["sin_ajuste_creadores"] = escenario_base(descripcion="Sin ajuste de creadores (08 §2.5).", ajuste="ninguno", **d)
    S["ajuste_en_regla"] = escenario_base(descripcion="Ajuste de creadores solo con valores de la regla de 08 §2.1 (US +3; NZ/AU/IE 0; SE 0).",
                                          ajuste="regla", **d)
    S["escala_10"] = escenario_base(descripcion="Criterio de escala (población) con peso 10 %, resto de pesos x0,9 (16 H2).",
                                    escala_peso=10, **d)
    S["comp_5"] = escenario_base(descripcion="Peso de COMP bajado a 5 % (16 H7), resto reescalado a 100.",
                                 pesos={"PA": 15, "CAC": 20, "COMP": 5, "PAGO": 20, "FISC": 15, "LOC": 10, "FRAUD": 10}, **d)
    S["pesos_iguales_sin_creadores"] = escenario_base(
        descripcion="Pesos iguales y sin creadores (08 §2.5).", ajuste="ninguno",
        pesos={k: 1 for k in CRITERIOS}, **d)
    S["suiza_sin_iva"] = escenario_base(descripcion="Lectura alternativa de Suiza (sin IVA, r = 1,45 -> CAC 3).",
                                        iva={"CH": 0.0}, **d)
    corr = dict(neto="completo", stripe_tax="pct", ctr=0.013, cpm_mult=1.2, ajuste="regla", **d)
    S["corregido"] = escenario_base(descripcion="CORREGIDO (central): neto completo + CTR 1,3 % + CPM x1,2 (Q4) + creadores en regla; ticket anglo 27 como 08.", **corr)
    S["corregido_ticket17"] = escenario_base(descripcion="Corregido con ticket anglo de 17 USD (estrés del bloque inglés).",
                                             ticket={c: 17.0 for c in INGLES_27}, **corr)
    S["corregido_cac_relativo"] = escenario_base(
        descripcion="Corregido con CAC relativo [NUEVO]: bandas de r reancladas por mediana(r)/mediana(r de 08), para que el CAC siga discriminando cuando todo r > 2,2.",
        **dict(corr, cac_modo="relativo"))
    S["corregido_escala"] = escenario_base(descripcion="Corregido + criterio de escala 10 %.", escala_peso=10, **corr)
    S["corregido_sin_pagos"] = escenario_base(descripcion="Corregido sin criterio de pagos y con comisión de tarjeta.",
                                              excluir=["PAGO"], comision="tarjeta", **corr)
    corr_estres = dict(corr, ctr=0.010, cpm_mult=1.5)
    S["corregido_estres"] = escenario_base(descripcion="Estrés: neto completo (Tax por API) + CTR 1,0 % + CPM x1,5 + creadores en regla.",
                                           **dict(corr_estres, stripe_tax="fijo"))
    return S


# --------------------------------------------------------------------------- fórmulas de 08
def banda(valor, bandas, clave, menor_igual=True, defecto=0):
    for b in bandas:
        if (valor <= b[clave]) if menor_igual else (valor >= b[clave]):
            return b["puntaje"]
    return defecto


def conversion(P, par):
    e = par["embudo_08"]
    c = e["conversion_base"] * (e["ticket_referencia_conversion_usd"] / P) ** e["elasticidad"]
    return min(max(c, e["conversion_min"]), e["conversion_max"])


def datos_economicos(m, esc):
    """Devuelve (P, t, pct, fijo, fee, cpm) con los reemplazos del escenario."""
    ec = m["economia"]
    P = esc["ticket"].get(m["codigo"], ec["ticket_usd"])
    t = esc["iva"].get(m["codigo"], ec["iva"])
    pct = ec["comision_tarjeta_pct"] if esc["comision"] == "tarjeta" else ec["comision_pct"]
    return P, t, pct, ec["comision_fijo_usd"], ec["tarifa_meta"], ec["cpm_usd"]


def neto_08(P, t, pct, fijo):
    """08 §5: neto = P*(1 - t/(1+t)) - (pct*P + fijo). IVA incluido en el precio."""
    return P * (1 - t / (1 + t)) - (pct * P + fijo)


def neto_completo(P, t, pct, fijo, part_tarjeta, par, esc):
    """16 §2.1: EV = (1-rho)*neto_ok - rho*(comisión+Tax) - d*15*part_tarjeta."""
    c = par["costos_directos"]
    tax = P * t / (1 + t)
    comision = pct * P + fijo
    modo = esc["stripe_tax"]
    st = P * c["stripe_tax_pct"] if modo == "pct" else (c["stripe_tax_fijo_api_usd"] if modo == "fijo" else 0.0)
    neto_ok = P - tax - comision - st
    rho = esc["reembolso"]
    return (1 - rho) * neto_ok - rho * (comision + st) - esc["disputa"] * c["disputa_costo_usd"] * part_tarjeta


def calcular_r(m, esc, par):
    P, t, pct, fijo, fee, cpm = datos_economicos(m, esc)
    cpc = cpm * esc["cpm_mult"] * (1 + fee) / (1000 * esc["ctr"])
    conv = conversion(P, par)
    cpa = cpc / conv
    if esc["neto"] == "completo":
        neto = neto_completo(P, t, pct, fijo, m["economia"]["participacion_disputa_tarjeta"], par, esc)
    else:
        neto = neto_08(P, t, pct, fijo)
    return {"P": P, "cpc": cpc, "conv": conv, "cpa": cpa, "neto": neto,
            "r": cpa / neto if neto > 0 else float("inf"),
            "equilibrio_pct": 100 * cpc / neto if neto > 0 else float("inf")}


def puntaje_cac(r, par):
    rc = par["reglas_cac"]
    return banda(r, rc["bandas"], "r_max", True, rc["puntaje_mayor"])


def puntaje_pago(cobertura, par):
    rp = par["reglas_pago"]
    return banda(cobertura, rp["bandas"], "cobertura_min", False, rp["puntaje_menor"])


def puntaje_escala(poblacion_m, par):
    re_ = par["escala"]
    return banda(poblacion_m, re_["bandas"], "poblacion_min_m", False, re_["puntaje_menor"])


def pesos_efectivos(esc, par):
    w = dict(esc["pesos"]) if esc["pesos"] else {k: par["pesos_08"][k] for k in CRITERIOS}
    for k in esc["excluir"]:
        w.pop(k, None)
    total = float(sum(w.values()))
    w = {k: 100.0 * v / total for k, v in w.items()}
    if esc["escala_peso"]:
        f = (100.0 - esc["escala_peso"]) / 100.0
        w = {k: v * f for k, v in w.items()}
        w["ESC"] = float(esc["escala_peso"])
    return w


def evaluar(m, esc, par, factor_r=1.0):
    econ = calcular_r(m, esc, par)
    p = {k: m["puntajes_08"][k]["v"] for k in CRITERIOS}
    p["CAC_publicado"] = p["CAC"]
    p["CAC_derivado"] = puntaje_cac(econ["r"] / factor_r, par)
    p["PAGO_publicado"] = p["PAGO"]
    p["PAGO_derivado"] = puntaje_pago(m["pagos"]["cobertura_central_pct"], par)
    if esc["cac_modo"] in ("derivado", "relativo"):
        p["CAC"] = p["CAC_derivado"]
    if esc["pago_modo"] == "derivado":
        p["PAGO"] = p["PAGO_derivado"]
    p["ESC"] = puntaje_escala(m["escala"]["poblacion_m"], par)
    w = pesos_efectivos(esc, par)
    base = sum(w[k] * p[k] / 5.0 for k in w)
    if esc["ajuste"] == "08":
        aj = m["ajuste_creadores_08"]
    elif esc["ajuste"] == "regla":
        aj = m["ajuste_creadores_regla"]
    else:
        aj = 0
    return {"codigo": m["codigo"], "nombre": m["nombre"], "puntajes": p, "base": base, "ajuste": aj,
            "total": base + aj, "econ": econ, "fisc": p["FISC"]}


def mediana(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def factor_relativo(esc, par, mercados):
    """cac_modo 'relativo' [NUEVO]: reancla las bandas de r dividiendo por mediana(r escenario)/mediana(r de 08).
    Sirve cuando el entorno empeora parejo y las bandas absolutas de 08 saturan en 0 (todos los r > 2,2)."""
    ref = escenario_base(comision=esc["comision"], iva=esc["iva"], ticket=esc["ticket"])
    r_esc = [calcular_r(m, esc, par)["r"] for m in mercados]
    r_ref = [calcular_r(m, ref, par)["r"] for m in mercados]
    return mediana(r_esc) / mediana(r_ref)


def ranking(esc, par, mercados):
    filas = []
    k = factor_relativo(esc, par, mercados) if esc["cac_modo"] == "relativo" else 1.0
    for i, m in enumerate(mercados):
        f = evaluar(m, esc, par, k)
        f["orden_08"] = i
        f["factor_r"] = k
        filas.append(f)
    for pr, f in enumerate(sorted(filas, key=lambda x: (x["econ"]["r"], x["orden_08"])), 1):
        f["pos_r"] = pr  # orden puramente económico (menor r = mejor)
    # desempate de 08 §2.2: menor carga fiscal (FISC mayor); luego base sin ajuste; luego el orden de 08
    filas.sort(key=lambda f: (-round(f["total"], 6), -f["fisc"], -round(f["base"], 6), f["orden_08"]))
    for pos, f in enumerate(filas, 1):
        f["pos"] = pos
    return filas


# --------------------------------------------------------------------------- estabilidad
def spearman(a, b):
    """Correlación de rangos entre dos listas de códigos en orden."""
    n = len(a)
    ra = {c: i for i, c in enumerate(a)}
    rb = {c: i for i, c in enumerate(b)}
    d2 = sum((ra[c] - rb[c]) ** 2 for c in ra)
    return 1 - 6 * d2 / (n * (n * n - 1))


def estabilidad(fila_base, fila_esc):
    cb = [f["codigo"] for f in fila_base]
    ce = [f["codigo"] for f in fila_esc]
    pos = {f["codigo"]: f["pos"] for f in fila_esc}
    return {
        "top3": ce[:3], "top5": ce[:5],
        "top3_igual_a_base": set(ce[:3]) == set(cb[:3]),
        "top5_solapamiento": len(set(ce[:5]) & set(cb[:5])),
        "spearman_vs_base": round(spearman(cb, ce), 3),
        "pos_IT": pos["IT"], "pos_PL": pos["PL"],
        "IT_sobre_PL": pos["IT"] < pos["PL"],
        "dif_IT_menos_PL": round(next(f["total"] for f in fila_esc if f["codigo"] == "IT")
                                 - next(f["total"] for f in fila_esc if f["codigo"] == "PL"), 1),
    }


def correr_todos(par, mercados):
    S = definir_escenarios()
    res = {k: ranking(e, par, mercados) for k, e in S.items()}
    base = res["08_publicado"]
    est = {k: estabilidad(base, v) for k, v in res.items()}
    return S, res, est


def rejilla(par, mercados, cac_modo="derivado"):
    """Rejilla factorial: CTR x CPM x neto x ticket anglo x pagos x creadores (3x3x2x2x2x3 = 216 combinaciones)."""
    g = par["escenarios_parametros"]
    ctrs = g["ctr_enlace"]["valores"]
    cpms = g["cpm_q4_multiplicador"]["valores"]
    cuenta = {m["codigo"]: {"top3": 0, "top5": 0, "top8": 0} for m in mercados}
    it_pl = 0
    n = 0
    posiciones = {m["codigo"]: [] for m in mercados}
    for ctr, cpm, neto, tk, pagos, aj in itertools.product(
            ctrs, cpms, ("08", "completo"), (27, 17), ("con", "sin"), ("08", "regla", "ninguno")):
        esc = escenario_base(ctr=ctr, cpm_mult=cpm, neto=neto, cac_modo=cac_modo, pago_modo="derivado",
                             ticket={} if tk == 27 else {c: 17.0 for c in INGLES_27},
                             excluir=["PAGO"] if pagos == "sin" else [],
                             comision="tarjeta" if pagos == "sin" else "metodo", ajuste=aj)
        fila = ranking(esc, par, mercados)
        n += 1
        for f in fila:
            posiciones[f["codigo"]].append(f["pos"])
            for k, lim in (("top3", 3), ("top5", 5), ("top8", 8)):
                if f["pos"] <= lim:
                    cuenta[f["codigo"]][k] += 1
        pos = {f["codigo"]: f["pos"] for f in fila}
        it_pl += pos["IT"] < pos["PL"]
    return {"n": n, "cac_modo": cac_modo, "frecuencia": cuenta, "IT_sobre_PL": it_pl,
            "posicion_mediana": {c: sorted(v)[len(v) // 2] for c, v in posiciones.items()},
            "posicion_min_max": {c: (min(v), max(v)) for c, v in posiciones.items()}}


# --------------------------------------------------------------------------- verificaciones
def cargar_rank_sin_pagos():
    ruta = os.path.join(AQUI, "rank_sin_pagos.py")
    spec = importlib.util.spec_from_file_location("rank_sin_pagos", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verificar(par, mercados):
    """Devuelve lista de hallazgos (ok/aviso/error) sobre la reproducción de 08."""
    out = []
    base = ranking(escenario_base(), par, mercados)
    # 1. totales de 08
    for f, m in zip(sorted(base, key=lambda x: x["orden_08"]), mercados):
        ok_base = round(f["base"]) == m["base_08"] and abs(f["base"] - m["base_08"]) < 1e-9
        ok_tot = round(f["total"]) == m["total_08"]
        out.append(("ok" if ok_base and ok_tot else "error",
                    f"{m['codigo']}: base {f['base']:.1f} (08: {m['base_08']}), total {f['total']:.1f} (08: {m['total_08']})"))
    # 2. CAC y PAGO derivados vs publicados
    drv = escenario_base(cac_modo="derivado", pago_modo="derivado")
    for m in mercados:
        f = evaluar(m, drv, par)
        pub = m["puntajes_08"]["CAC"]["v"]
        r = f["econ"]["r"]
        rp = m["r_publicado_08"]
        estado = "ok" if f["puntajes"]["CAC_derivado"] == pub else "aviso"
        det = f"{m['codigo']}: r calculado {r:.3f} vs r publicado {rp:.2f}; CAC derivado {f['puntajes']['CAC_derivado']} vs publicado {pub}"
        if abs(r - rp) > 0.05:
            estado = "aviso"
            det += f" [r difiere {abs(r - rp):.2f}]"
        out.append((estado, det))
        pg = f["puntajes"]["PAGO_derivado"]
        if pg != m["puntajes_08"]["PAGO"]["v"]:
            out.append(("error", f"{m['codigo']}: PAGO derivado {pg} vs publicado {m['puntajes_08']['PAGO']['v']}"))
    # 3. Suiza: la inconsistencia señalada en 17 H1
    ch = next(m for m in mercados if m["codigo"] == "CH")
    for etiqueta, iva in (("IVA 8,1 % (régimen estable, como CA/GB/IE)", 0.081), ("sin IVA (umbral global 100.000 CHF)", 0.0)):
        e = escenario_base(cac_modo="derivado", iva={"CH": iva})
        f = evaluar(ch, e, par)
        out.append(("info", f"Suiza, {etiqueta}: r = {f['econ']['r']:.3f}, equilibrio {f['econ']['equilibrio_pct']:.2f} %, CAC por regla = {f['puntajes']['CAC_derivado']} (publicado 2; r publicado 1,50; equilibrio publicado 2,9 %)"))
    # 4. contra rank_sin_pagos.py
    rsp = cargar_rank_sin_pagos()
    ref = rsp.calcular()  # misma lista y orden que 08 §2.2; el nombre de HUS difiere
    sp = sorted(ranking(escenario_base(excluir=["PAGO"]), par, mercados), key=lambda x: x["orden_08"])
    if len(ref) != len(sp):
        out.append(("error", f"rank_sin_pagos tiene {len(ref)} mercados y mercados.json {len(sp)}"))
    for r, mio in zip(ref, sp):
        ok = abs(mio["total"] - r["sin_pagos_con_ajuste"]) < 0.06
        if r["mercado"] != mio["nombre"]:
            out.append(("aviso", f"nombre distinto: rank_sin_pagos '{r['mercado']}' vs mercados.json '{mio['nombre']}'"))
        out.append(("ok" if ok else "error", f"sin pagos {mio['codigo']}: {mio['total']:.1f} vs rank_sin_pagos {r['sin_pagos_con_ajuste']}"))
    return out


# --------------------------------------------------------------------------- salida
def tabla(filas, titulo=None, ver_r=False):
    lineas = []
    if titulo:
        lineas.append(titulo)
    cab = f"{'#':>2} {'Mercado':34}{'Base':>6}{'Aj.':>5}{'Total':>7}"
    if ver_r:
        cab += f"{'r':>6}{'#r':>4}{'CAC':>4}{'CPA':>7}{'Neto':>7}"
    lineas.append(cab)
    for f in filas:
        s = f"{f['pos']:>2} {f['nombre'][:33]:34}{f['base']:6.1f}{f['ajuste']:5}{f['total']:7.1f}"
        if ver_r:
            s += f"{f['econ']['r']:6.2f}{f['pos_r']:4}{f['puntajes']['CAC']:4}{f['econ']['cpa']:7.1f}{f['econ']['neto']:7.2f}"
        lineas.append(s)
    return "\n".join(lineas)


def resumen_escenarios(S, res, est):
    lineas = [f"{'Escenario':32}{'Top 5 (códigos)':30}{'IT':>3}{'PL':>3}{'IT-PL':>7}{'Top3=base':>10}{'Spearman':>9}"]
    for k in S:
        e = est[k]
        lineas.append(f"{k:32}{' '.join(e['top5']):30}{e['pos_IT']:>3}{e['pos_PL']:>3}{e['dif_IT_menos_PL']:>7}"
                      f"{('sí' if e['top3_igual_a_base'] else 'no'):>10}{e['spearman_vs_base']:>9}")
    return "\n".join(lineas)


def exportar(ruta, par, mercados):
    S, res, est = correr_todos(par, mercados)
    grid = {"derivado": rejilla(par, mercados, "derivado"), "relativo": rejilla(par, mercados, "relativo")}
    salida = {
        "_meta": {"fecha": "2026-11-06", "generado_por": "scripts/mercados/rank.py --exportar", "nota": "Salida determinista; no editar a mano."},
        "escenarios": {k: {"descripcion": S[k]["descripcion"],
                           "orden": [{"pos": f["pos"], "codigo": f["codigo"], "total": round(f["total"], 1),
                                      "base": round(f["base"], 1), "ajuste": f["ajuste"],
                                      "r": round(f["econ"]["r"], 3), "pos_r": f["pos_r"], "cac": f["puntajes"]["CAC"],
                                      "cpa": round(f["econ"]["cpa"], 2), "neto": round(f["econ"]["neto"], 2)}
                                     for f in res[k]],
                           "estabilidad": est[k]} for k in S},
        "rejilla": grid,
    }
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--escenario")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--cac-modo", default="derivado", choices=["derivado", "relativo"], help="para --grid")
    ap.add_argument("--exportar")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    par, mercados, fuera = cargar_datos()
    S = definir_escenarios()
    if a.lista:
        for k, e in S.items():
            print(f"{k:32}{e['descripcion']}")
        return 0
    if a.exportar:
        exportar(a.exportar, par, mercados)
        print(f"escrito {a.exportar}")
        return 0
    if a.grid:
        g = rejilla(par, mercados, a.cac_modo)
        if a.json:
            print(json.dumps(g, ensure_ascii=False, indent=1))
            return 0
        print(f"Rejilla factorial ({g['cac_modo']}): {g['n']} combinaciones (CTR x CPM x neto x ticket anglo x pagos x creadores)")
        print(f"{'Cód':5}{'top3':>6}{'top5':>6}{'top8':>6}{'mediana':>9}{'min-max':>9}")
        orden = sorted(g["frecuencia"], key=lambda c: (-g["frecuencia"][c]["top5"], -g["frecuencia"][c]["top3"], c))
        for c in orden:
            fr = g["frecuencia"][c]
            mn, mx = g["posicion_min_max"][c]
            print(f"{c:5}{fr['top3']:>6}{fr['top5']:>6}{fr['top8']:>6}{g['posicion_mediana'][c]:>9}{f'{mn}-{mx}':>9}")
        print(f"Italia por encima de Polonia en {g['IT_sobre_PL']} de {g['n']} combinaciones")
        return 0
    if a.escenario:
        if a.escenario not in S:
            print("escenario desconocido; use --lista", file=sys.stderr)
            return 2
        fila = ranking(S[a.escenario], par, mercados)
        if a.json:
            print(json.dumps([{k: f[k] for k in ("pos", "codigo", "total", "base", "ajuste")} for f in fila], ensure_ascii=False, indent=1))
        else:
            print(tabla(fila, f"{a.escenario}: {S[a.escenario]['descripcion']}", ver_r=True))
        return 0
    if a.todos:
        S, res, est = correr_todos(par, mercados)
        print(resumen_escenarios(S, res, est))
        return 0
    # por defecto: reproducción de 08 y verificaciones
    base = ranking(S["08_publicado"], par, mercados)
    print(tabla(base, "Reproducción de 08 §2.2 (puntajes publicados)"))
    print("\nFuera del top 15 (solo total publicado, sin desglose): " +
          ", ".join(f"{k} {v}" for k, v in fuera["totales"].items()))
    print("\nVerificaciones")
    malos = 0
    for estado, texto in verificar(par, mercados):
        if estado == "error":
            malos += 1
        if estado != "ok":
            print(f"  [{estado}] {texto}")
    print(f"  {'OK: 15 totales y sin_pagos reproducidos' if not malos else str(malos) + ' errores'}")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
