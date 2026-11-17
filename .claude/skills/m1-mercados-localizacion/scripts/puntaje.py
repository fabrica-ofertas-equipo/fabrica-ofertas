#!/usr/bin/env python3
"""M1 - puntaje.py: EXTIENDE scripts/mercados/rank.py (referencia de 08/08b) con lo que rank.py no cubre
(departamentos/16 §4.1): cobertura de pago POR FASE, rama Managed Payments, EXPO, R1-R10 y los 9 pesos de M1
(ajuste de creadores con peso 0). Determinista: mismos datos versionados => mismo orden; sin LLM, sin red, sin reloj.

La economia (neto, CPC, r) NO se reimplementa: se importa de rank.py. [PENDIENTE] cuando exista, la economia pasa a
engine.factibilidad (divergencia de disputas conocida: rank.py d*15*part_tarjeta vs engine d*(neto+tarifa); registrar en MQ-09).

Subcomandos (ejecutar con .venv/bin/python -I para poder leer YAML):
  reproducir                      rank.py imprime OK (15 totales de 08 §2.2) y el escenario `corregido` da CA 71 ... IT 53, PL 51 (±1)
  cobertura FICHA --decision-mp {no_decidido,si,no} [--hoy]     cobertura por fase, valor de desbloqueo, hueco PayPal, rama MP
  excluir CONTEXTO.json           R1-R10 por (pais, locale)  -> excluidos[] y banderas[]
  seleccionar CONTEXTO.json       excluir + puntaje de 9 criterios + sensibilidad + bloques por locale  (parte mecanica de mercado.seleccion.json)

Codigos de salida: 0 · 2 uso · 3 hallazgo bloqueante (p. ej. reproduccion falla) · 5 dato faltante (paises_permitidos/locales_permitidos vacios, parametro ausente).
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import os
import subprocess
import sys
from decimal import ROUND_HALF_EVEN, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as C  # noqa: E402
import vigencia as V  # noqa: E402

FASE_ESTANDAR, FASE_LOCALES = "estandar_tarjeta_billeteras", "con_locales"
ESTANDAR = {"card", "apple_pay", "google_pay", "link"}
LOCALES = {"blik", "przelewy24", "satispay", "mb_way", "bancontact", "multibanco", "eps", "pay_by_bank"}
NUNCA_SUMAN = {"paypal", "klarna", "amazon_pay", "cash_app_pay", "afterpay", "interac"}  # MQ-13 (D2, D8)
MP_OK = ESTANDAR | {"bancontact"}
CRITERIOS_M1 = ["PA", "CAC", "COMP", "PAGO", "FISC", "LOC", "FRAUD", "EXPO", "ESC"]
ORDEN_NIVEL = {n: i for i, n in enumerate(C.NIVELES)}
CLAVE_BANDERA_MACRO = {"S": "salud", "R": "relaciones", "D": "dinero"}


# --------------------------------------------------------------------------- rank.py (referencia)
def cargar_rank():
    ruta = os.path.join(C.RAIZ, "scripts", "mercados", "rank.py")
    if not os.path.exists(ruta):
        raise C.DatoFaltante(f"no existe {ruta}: M1 no puede reproducir la referencia")
    spec = importlib.util.spec_from_file_location("rank_ref", ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rank_ref"] = mod
    spec.loader.exec_module(mod)
    return mod


def q1(x):
    """float/Decimal -> cadena con 1 decimal (sin float en las salidas JSON)."""
    return str(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN))


def q2(x):
    return str(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


# --------------------------------------------------------------------------- cobertura por fase
def _monedas(m):
    e = C.valor(m, "moneda_exigida")
    if e is None:
        return None
    return [e] if isinstance(e, str) else list(e)


def _motivo_no_suma(m, fase, moneda, mp):
    mid = m["id"]
    if C.valor(m, "incluir_en_cobertura", defecto=True) is False:
        return "cuota_no_confirmada (no se suma hasta tener dato o alta confirmada; ver nota del metodo)"
    if mid in NUNCA_SUMAN:
        return "no_suma_MQ13 (PayPal, Klarna, Amazon Pay, Cash App Pay, Afterpay: no cobrables o fuera de alcance para la LLC)"
    if not C.valor(m, "elegible_cuenta_us", defecto=False):
        return "no_elegible_cuenta_us"
    permitido = ESTANDAR if fase == FASE_ESTANDAR else (ESTANDAR | LOCALES)
    if mid not in permitido:
        return "fuera_de_la_fase"
    ex = _monedas(m)
    if ex and moneda not in ex:
        return "moneda_exigida_" + "/".join(ex) + (f"_y_se_cobra_en_{moneda}" if moneda else "_sin_moneda_declarada")
    if mp == "si" and not C.valor(m, "managed_payments_ok", defecto=mid in MP_OK):
        return "incompatible_con_managed_payments"
    return None


def cobertura(ficha, fase, moneda, mp="no"):
    suman, no_suman = [], []
    for m in C.valor(ficha, "pagos", "metodos", defecto=[]):
        cuota = int(C.valor(m, "cuota_bp", defecto=0) or 0)
        motivo = _motivo_no_suma(m, fase, moneda, mp)
        (no_suman if motivo else suman).append({"id": m["id"], "cuota_bp": cuota, **({"motivo": motivo} if motivo else {})})
    total = sum(x["cuota_bp"] for x in suman)
    hueco = max(no_suman, key=lambda x: (x["cuota_bp"], x["id"]), default=None)
    paypal = sum(x["cuota_bp"] for x in no_suman if x["id"] == "paypal")
    return {"fase": fase, "moneda_cobro": moneda, "managed_payments": mp, "cobertura_bp": total, "cobertura_pct": q1(Decimal(total) / 100),
            "suman": suman, "no_suman": no_suman,
            "hueco_principal": ({"metodo": hueco["id"], "pp": q1(Decimal(hueco["cuota_bp"]) / 100)} if hueco and hueco["cuota_bp"] else None),
            "hueco_paypal_pp": q1(Decimal(paypal) / 100)}


def cobertura_por_fase(ficha, decision_mp="no_decidido"):
    """Ambas fases, en la mejor moneda de cobro posible. Con `no_decidido` la rama principal es Stripe estandar y se informa la otra rama."""
    mp_principal = "si" if decision_mp == "si" else "no"
    monedas = C.valor(ficha, "identidad", "monedas_cobro_posibles", defecto=[]) or [None]

    def mejor(fase, mp):
        best = None
        for mon in monedas:
            c = cobertura(ficha, fase, mon, mp)
            if best is None or c["cobertura_bp"] > best["cobertura_bp"]:
                best = c
        return best

    out = {FASE_ESTANDAR: mejor(FASE_ESTANDAR, mp_principal), FASE_LOCALES: mejor(FASE_LOCALES, mp_principal)}
    otra = "no" if mp_principal == "si" else "si"
    out["rama_managed_payments_alternativa"] = {"managed_payments": otra, FASE_ESTANDAR: mejor(FASE_ESTANDAR, otra), FASE_LOCALES: mejor(FASE_LOCALES, otra)}
    out["valor_desbloqueo_pp"] = q1(Decimal(out[FASE_LOCALES]["cobertura_bp"] - out[FASE_ESTANDAR]["cobertura_bp"]) / 100)
    out["decision_managed_payments"] = decision_mp
    return out


# --------------------------------------------------------------------------- niveles y EXPO
def subnivel_candidato(riesgo):
    """Nivel con subnivel en la escritura canonica del contrato (verde | amarillo-a | amarillo-b | rojo; comunes#nivel_lanzable).

    M1 NO clasifica riesgo: lee el de D1/X1. Si el candidato trae `subnivel` (A | B, que emite `python -m scripts.nivel_riesgo`;
    candidatos 1.1.0, pedido LT-04), se usa tal cual. Si no lo trae (candidatos 1.0.0), se deriva de los colores de los ejes
    P, C, E, N con la misma regla de esa tabla: un eje amarillo = A, dos o mas = B [SUPUESTO]."""
    nivel = riesgo.get("nivel")
    if nivel != "amarillo":
        return nivel
    s = riesgo.get("subnivel")
    if s in ("A", "B"):
        return "amarillo-" + s.lower()
    amarillos = sum(1 for e in "PCEN" if riesgo.get(e) == "amarillo")
    return "amarillo-a" if amarillos <= 1 else "amarillo-b"


def macros_candidato(cand):
    macros = {cand.get("macro_nicho")} - {None}
    b = cand.get("banderas") or {}
    for k, mc in CLAVE_BANDERA_MACRO.items():
        if b.get(k) or b.get(mc):
            macros.add(mc)
    if cand.get("macro_secundario"):
        macros.add(cand["macro_secundario"])
    return sorted(macros)


def exposicion_pais(iso, matriz):
    """V/A/A+/R por macro. -> (dict|None, heredada_de|None)."""
    ex = matriz.get("exposicion", {})
    if iso in ex:
        return ex[iso], None
    ne = matriz.get("no_evaluados", {}).get(iso)
    if ne and ne.get("heredan_de") in ex:
        return ex[ne["heredan_de"]], ne["heredan_de"]
    return None, None


def puntaje_expo(iso, cand, matriz):
    """Peor caso entre los macros del candidato (nota 25 §8.1: por bandera, no por macro primario). -> (puntaje|None, detalle)."""
    sub = subnivel_candidato(cand["riesgo"])
    if sub not in matriz["tabla_expo"]:
        return None, {"motivo": f"nivel {sub} no puntuable"}
    ex, heredada = exposicion_pais(iso, matriz)
    if ex is None:
        return None, {"motivo": "pais_sin_fila_de_matriz"}
    vals, det = [], {}
    for mc in macros_candidato(cand):
        e = ex.get(mc)
        p = matriz["tabla_expo"][sub].get(e) if e else None
        det[mc] = {"exposicion": e, "puntaje": p}
        if p is None:
            return None, {"motivo": f"{sub} no admitido con exposicion {e} en {mc}", "macros": det}
        vals.append(p)
    return min(vals), {"nivel": sub, "macros": det, **({"heredada_de": heredada} if heredada else {})}


# --------------------------------------------------------------------------- exclusiones R1-R10
def _par_locales(ficha):
    return C.valor(ficha, "identidad", "locales", defecto=[]) or []


def etiquetas_de(cand):
    return set(cand.get("etiquetas") or [])


def r3(iso, cand, matriz):
    macros, tags, out = set(macros_candidato(cand)), etiquetas_de(cand), []
    for r in matriz.get("restricciones", []):
        if r["pais"] != iso or (r["macro"] != "*" and r["macro"] not in macros):
            continue
        if (set(r.get("dispara_si", [])) & tags) or (r.get("dispara_si_falta") and not (set(r["dispara_si_falta"]) <= tags)):
            out.append(r)
    return out


def excluir(ctx, params, hoy=None):
    """R1-R10. Devuelve {excluidos[], banderas{(iso|locale): []}, evaluados[]}. Falla cerrado (DatoFaltante) sin limites."""
    lim = ctx.get("limites") or {}
    paises_ok, locales_ok = lim.get("paises_permitidos"), lim.get("locales_permitidos")
    if not paises_ok or not locales_ok:
        raise C.DatoFaltante("limites.paises_permitidos o limites.locales_permitidos vacios o null: fail-closed, nada se evalua (salida 5)")
    cand, fase = ctx["candidato"], ctx.get("fase_pagos", FASE_ESTANDAR)
    decision_mp = ctx.get("decision_managed_payments", "no_decidido")
    matriz = ctx.get("matriz") or C.cargar_json(os.path.join(C.AQUI, "semilla_exposicion.json"))
    excl, banderas, evaluados = [], {}, []
    sub = subnivel_candidato(cand["riesgo"])

    def add(iso, loc, regla, motivo, reabre=None):
        excl.append({"pais": iso, "locale": loc, "regla": regla, "motivo": motivo, **({"reabre_con": reabre} if reabre else {})})

    # R2: del candidato (aplica a todo par)
    nivel_max = lim.get("nivel_max_lanzable") or {}
    macros = macros_candidato(cand)
    r2 = None
    if cand.get("fuera_de_macro_nicho"):
        r2 = "fuera_de_macro_nicho"
    elif cand["riesgo"].get("nivel") == "rojo":
        r2 = "candidato rojo (sin reencuadre que lo baje)"
    else:
        for mc in macros:
            tope = nivel_max.get(mc) or "verde"  # limites 1.3.0: nivel_max_lanzable null (o un macro sin valor) = SOLO VERDE, fail-closed (contratos/limites.schema.json; lo fija el dueño)
            if tope not in ORDEN_NIVEL or sub not in ORDEN_NIVEL:
                raise C.DatoFaltante(f"nivel invalido para R2: nivel_max_lanzable[{mc}]={tope!r}, candidato={sub!r}; admitidos: {', '.join(C.NIVELES)} (minusculas, comunes#nivel_lanzable)")
            if ORDEN_NIVEL[sub] > ORDEN_NIVEL[tope]:
                r2 = f"nivel {sub} > nivel_max_lanzable[{mc}]={tope}"
    for iso, ficha in sorted(ctx["fichas"].items()):
        for loc_e in _par_locales(ficha):
            loc = loc_e["locale"]
            evaluados.append([iso, loc])
            clave = f"{iso}/{loc}"
            bandera = banderas.setdefault(clave, [])
            # R1
            if iso not in paises_ok or loc not in locales_ok:
                add(iso, loc, "R1", "pais fuera de paises_permitidos o locale fuera de locales_permitidos")
                continue
            if r2:
                add(iso, loc, "R2", r2, "reencuadre seguro que baje el nivel, o nivel_max_lanzable mayor firmado por el dueño")
                continue
            # R3 (por promesa/contenido, no por tema)
            for r in r3(iso, cand, matriz):
                add(iso, loc, "R3", f"{r['id_check']} {r['condicion']} (tipo {r['tipo']}): se excluye el PAR (promesa/contenido, pais), no el tema",
                    "reencuadre que quite la etiqueta que dispara la restriccion")
            # R4
            ayuda = matriz.get("ayuda_verificada", {}).get(iso, {})
            if ("requiere_ayuda_emocional" in etiquetas_de(cand) or sub == "amarillo-b") and ayuda.get("emocional") is not True:
                add(iso, loc, "R4", "sin linea de ayuda verificada del pais para la categoria central" + (" (amarillo-b)" if sub == "amarillo-b" else ""),
                    "X1 verifica ayuda_por_pais")
            if sub == "amarillo-b" and not ctx.get("gate_h_amarillo_b"):
                add(iso, loc, "R4", "amarillo-b sin gate H del dueño", "gate H firmado")
            # R5
            obl = C.valor(loc_e, "obligacion_legal_idioma", defecto=False)
            rev = C.valor(ficha, "localizacion_y_calidad", "revisor_nativo", "estado", defecto="ninguno")
            if obl and rev not in ("contratado", "activo"):
                add(iso, loc, "R5", f"obligacion_legal_idioma y revisor_nativo={rev}: X1 emite ROJO (X32_REVISOR)", "contratar revisor nativo")
            if loc == "en-CA" and C.valor(ficha, "identidad", "incluye_quebec", defecto=False):
                add(iso, loc, "R5", "el cluster en-CA incluye Quebec (frances obligatorio): fuera del cluster")
            # R6 / R7 (pagos de la fase vigente)
            cobs = cobertura_por_fase(ficha, decision_mp)
            cv = cobs[fase]
            pct = Decimal(cv["cobertura_bp"]) / 100
            if pct < Decimal(str(C.pedir(params, "cobertura_pago_min_duro"))):
                add(iso, loc, "R6", f"cobertura de pago de la fase {fase} = {q1(pct)} % < umbral duro (cobertura_pago_min_duro)",
                    f"fase con_locales: cobertura {cobs[FASE_LOCALES]['cobertura_pct']} % (+{cobs['valor_desbloqueo_pp']} pp)")
            elif pct < Decimal(str(C.pedir(params, "cobertura_pago_min_blando"))):
                bandera.append("cobertura_media")
            if not C.valor(ficha, "identidad", "monedas_cobro_posibles", defecto=[]):
                add(iso, loc, "R7", "moneda de cobro no declarada")
            elif fase == FASE_LOCALES and cv["suman"]:
                clave_m = max(cv["suman"], key=lambda x: x["cuota_bp"])
                if clave_m["cuota_bp"] and cv["moneda_cobro"] is None:
                    add(iso, loc, "R7", f"moneda requerida por el metodo clave {clave_m['id']} no cobrable")
            # R8
            regimen = ctx.get("regimen_fiscal", "diferido")
            if regimen == "diferido" and decision_mp != "si" and C.valor(ficha, "fiscal", "desde_primera_venta", defecto=False):
                firmada = ctx.get("exposicion_fiscal_firmada_paises")  # None = firma pendiente (la recoge el gate H); lista = ya decidida
                if firmada is None:
                    bandera.append("requiere_firma_exposicion_fiscal")  # el sellado la exige (MQ-07 / X32_FISCAL)
                elif iso not in firmada:
                    add(iso, loc, "R8", "regimen diferido en pais con IVA/registro desde la primera venta y el dueño no firmo la exposicion fiscal de este pais",
                        "firma del dueño de la exposicion fiscal del pais, o regimen stripe_tax/merchant_of_record")
            # R9
            rb = (ctx.get("r_b") or {}).get(iso)
            if rb is not None and Decimal(str(rb)) > Decimal(str(C.pedir(params, "r_max"))):
                add(iso, loc, "R9", f"r_b = r/bump = {rb} > r_max (neto completo, mult_cpm vigente)", "ticket mayor o bump probado")
            elif rb is None:
                bandera.append("r_no_calculado")
            # R10
            ev = V.evaluar_ficha(ficha, hoy or ctx["hoy"], params)
            for b in ev["bloqueantes"]:
                add(iso, loc, "R10", f"{b.get('regla')} {b.get('motivo')} en {b.get('ruta')}", "reverificar el dato con fuente oficial")
                break
            if ev["cpm_vencido"]:
                bandera.append("cpm_vencido")
            # EXPO
            e, det = puntaje_expo(iso, cand, matriz)
            if e is None:
                add(iso, loc, "R3", f"EXPO no puntuable: {det.get('motivo')}", "matriz de X1 o reencuadre")
            elif det.get("heredada_de"):
                bandera.append("expo_heredada_no_evaluado")
            if (sub in ("amarillo-a", "amarillo-b")) and e is not None and any(m["exposicion"] in ("A+", "R") for m in det["macros"].values()):
                bandera.append("gate_h_exposicion")
    return {"excluidos": excl, "banderas": banderas, "evaluados": evaluados}


# --------------------------------------------------------------------------- puntaje de 9 criterios
def _escenario(R, params, **kw):
    base = dict(neto="completo", stripe_tax="pct", ctr=float(params["ctr_enlace_central"]), cpm_mult=float(params["mult_cpm"]["central"]),
                ajuste="ninguno", cac_modo="relativo", pago_modo="derivado", comision="metodo",
                reembolso=params["reembolso_bp"] / 10000.0, disputa=params["disputa_bp"] / 10000.0)
    base.update(kw)
    return R.escenario_base(**base)


def puntajes_mercados(R, par, mercados, esc, pagos_por_codigo, expo_por_codigo, pesos, con_creadores=False):
    """Total de 9 criterios por mercado. PAGO de la fase y EXPO se inyectan; el resto sale de rank.evaluar (misma economia y bandas)."""
    k = R.factor_relativo(esc, par, mercados) if esc["cac_modo"] == "relativo" else 1.0
    tot_w = float(sum(pesos.values()))
    out = {}
    for m in mercados:
        f = R.evaluar(m, esc, par, k)
        p = {c: f["puntajes"][c] for c in ("PA", "CAC", "COMP", "PAGO", "FISC", "LOC", "FRAUD", "ESC")}
        cod = m["codigo"]
        if cod in pagos_por_codigo:
            p["PAGO"] = pagos_por_codigo[cod]["puntaje"]
        p["EXPO"] = expo_por_codigo.get(cod, 0)
        total = sum((100.0 * pesos[c] / tot_w) * p[c] / 5.0 for c in CRITERIOS_M1)
        aj = m["ajuste_creadores_regla"] if con_creadores else 0
        out[cod] = {"total": total + aj, "total_sin_creadores": total, "ajuste_creadores_informativo": m["ajuste_creadores_regla"],
                    "puntajes": p, "r": f["econ"]["r"], "cpc": f["econ"]["cpc"], "neto": f["econ"]["neto"], "fisc": p["FISC"]}
    return out, k


def seleccionar(ctx, params, hoy=None):
    permitidos = (ctx.get("limites") or {}).get("paises_permitidos") or []
    sin_ficha = sorted(set(permitidos) - set(ctx.get("fichas") or {}))
    if permitidos and len(sin_ficha) == len(permitidos):
        # paso 2 del SOP: candidatos = permitidos ∩ paises con ficha vigente; sin ninguno => pregunta bloqueante, no se inventa
        raise C.DatoFaltante("pregunta bloqueante: ningun pais de paises_permitidos tiene ficha en empresa/mercados/paises/: " + ", ".join(sin_ficha))
    R = cargar_rank()
    par, mercados, _ = R.cargar_datos(os.path.join(C.RAIZ, "scripts", "mercados", "datos") if not ctx.get("datos_dir") else ctx["datos_dir"])
    bump = float(params["bump_aov_factor"])
    decision_mp = ctx.get("decision_managed_payments", "no_decidido")
    fase = ctx.get("fase_pagos", FASE_ESTANDAR)
    matriz = ctx.get("matriz") or C.cargar_json(os.path.join(C.AQUI, "semilla_exposicion.json"))
    pesos = {k: params["pesos"][k] for k in CRITERIOS_M1}
    if sum(pesos.values()) != 100:
        raise C.DatoFaltante(f"los pesos de M1 suman {sum(pesos.values())} != 100 (MQ-09)")
    mult_central = float(params["mult_cpm"]["central"])
    cand = ctx["candidato"]
    sub = subnivel_candidato(cand["riesgo"])
    # CPM vencido (> vigencia_cpm_dias): NO bloquea; MAYOR + etiqueta [SUPUESTO] + bandera cpm_vencido (MQ-03M; spec 16 §3.4, cerrada).
    # El mult_cpm_efectivo es el central (1,2); el 1,5 (estres) es solo sensibilidad y NO excluye mercados (con 1,5 R9 sacaria a CA/NZ/AU/IE).
    cpm_vencido = any(V.evaluar_ficha(f, hoy or ctx["hoy"], params)["cpm_vencido"] for f in ctx["fichas"].values())
    mult_ef = mult_central

    def correr(escenario_kw, fase_s, mp_s, pesos_s, con_creadores=False):
        esc = _escenario(R, params, **dict({"cpm_mult": mult_ef}, **escenario_kw))
        mercs = mercados
        if mp_s == "si":  # rama MP: +3,5 % sobre comisiones y sin Stripe Tax propio (16 §4.1; [VERIFICAR] sobre total con impuestos)
            esc["stripe_tax"] = "ninguno"
            mercs = copy.deepcopy(mercados)
            for m in mercs:
                m["economia"]["comision_pct"] += 0.035
                m["economia"]["comision_tarjeta_pct"] += 0.035
        pagos, expos = {}, {}
        for m in mercs:
            ficha = ctx["fichas"].get(m["codigo"])
            if ficha:
                cob = cobertura_por_fase(ficha, "si" if mp_s == "si" else "no_decidido")
                cv = cob[fase_s]
                pagos[m["codigo"]] = {"puntaje": R.puntaje_pago(float(Decimal(cv["cobertura_bp"]) / 100), par), "cob": cob}
                e, det = puntaje_expo(m["codigo"], cand, matriz)
                expos[m["codigo"]] = e if e is not None else 0
        tabla, k = puntajes_mercados(R, par, mercs, esc, pagos, expos, pesos_s, con_creadores)
        for cod, t in tabla.items():
            t["r_b"] = t["r"] / bump
        return tabla, pagos, k

    tabla, pagos, k = correr({}, fase, "si" if decision_mp == "si" else "no", pesos)
    ctx2 = dict(ctx)
    ctx2["r_b"] = {cod: q2(t["r_b"]) for cod, t in tabla.items()}
    ex = excluir(ctx2, params, hoy)
    excl_por_iso = {}
    for e in ex["excluidos"]:
        excl_por_iso.setdefault(e["pais"], []).append(e)
    minimo, empate = Decimal(str(params["puntaje_minimo"])), Decimal(str(params["empate_puntos"]))
    ranking = []
    for m in mercados:
        cod = m["codigo"]
        if cod not in ctx["fichas"]:
            continue
        ficha = ctx["fichas"][cod]
        t = tabla[cod]
        cob = pagos[cod]["cob"]
        locs = [e["locale"] for e in _par_locales(ficha) if e["locale"].split("-")[0] == m["idioma"]] or [e["locale"] for e in _par_locales(ficha)][:1]
        ban = list(ex["banderas"].get(f"{cod}/{locs[0]}", [])) if locs else []
        if Decimal(q1(t["total"])) < minimo:
            ban.append("bajo_minimo")
        ranking.append({
            "pais": cod, "locale": locs[0] if locs else None, "moneda_cobro": cob[fase]["moneda_cobro"],
            "total": q1(t["total"]), "puntajes": {c: t["puntajes"][c] for c in CRITERIOS_M1},
            "ajuste_creadores_informativo": t["ajuste_creadores_informativo"], "peso_ajuste_creadores_en_total": params["peso_ajuste_creadores"],
            "r": q2(t["r"]), "r_b": q2(t["r_b"]),
            "cobertura": {"fase_vigente_pct": cob[fase]["cobertura_pct"], "estandar_pct": cob[FASE_ESTANDAR]["cobertura_pct"],
                          "con_locales_pct": cob[FASE_LOCALES]["cobertura_pct"], "valor_desbloqueo_pp": cob["valor_desbloqueo_pp"],
                          "hueco_paypal_pp": cob[fase]["hueco_paypal_pp"], "hueco_principal": cob[fase]["hueco_principal"]},
            "banderas": sorted(set(ban)), "excluido_por": [e["regla"] for e in excl_por_iso.get(cod, [])],
            "_orden": (-Decimal(q1(t["total"])), -t["fisc"], -Decimal(q1(t["total_sin_creadores"])), cod),
        })
    ranking.sort(key=lambda r: r["_orden"])
    elegibles = [r for r in ranking if not r["excluido_por"]]
    for i, r in enumerate(elegibles, 1):
        r["posicion"] = i
        sig = elegibles[i] if i < len(elegibles) else None
        r["empate_con_siguiente"] = bool(sig and abs(Decimal(r["total"]) - Decimal(sig["total"])) < empate)
    for r in ranking:
        r.pop("_orden")
    # ---- sensibilidad (los escenarios de rank.py + fases + MP); informa si el elegido sigue en el top 3
    elegido = elegibles[0]["pais"] if elegibles else None
    excl_estatica = {e["pais"] for e in ex["excluidos"] if e["regla"] not in ("R6", "R9")}
    esc_def = [("ctr_1_0", dict(ctr=0.010), fase, "no", pesos, False), ("ctr_1_8", dict(ctr=0.018), fase, "no", pesos, False),
               ("cpm_x1_0", dict(cpm_mult=1.0), fase, "no", pesos, False), ("cpm_x1_2", dict(cpm_mult=mult_central), fase, "no", pesos, False), ("cpm_x1_5", dict(cpm_mult=float(params["mult_cpm"]["estres"])), fase, "no", pesos, False),
               ("estres_ctr1_0_cpm1_5", dict(ctr=0.010, cpm_mult=float(params["mult_cpm"]["estres"])), fase, "no", pesos, False),
               ("pesos_iguales", {}, fase, "no", {c: 1 for c in CRITERIOS_M1}, False),
               ("con_creadores_informativo", {}, fase, "no", pesos, True),
               ("fase_con_locales", {}, FASE_LOCALES, "no", pesos, False),
               ("fase_estandar", {}, FASE_ESTANDAR, "no", pesos, False),
               ("managed_payments_si", {}, fase, "si", pesos, False)]
    sens = []
    for nombre, kw, f_s, mp_s, w_s, cc in esc_def:
        t_s, p_s, _ = correr(kw, f_s, mp_s, w_s, cc)
        filas = []
        for cod, t in t_s.items():
            if cod not in ctx["fichas"] or cod in excl_estatica:
                continue
            cvp = p_s[cod]["cob"][f_s]["cobertura_bp"] / 100
            if Decimal(str(cvp)) < Decimal(str(params["cobertura_pago_min_duro"])) or t["r_b"] > float(params["r_max"]):
                continue
            filas.append((-round(t["total"], 6), -t["fisc"], cod))
        filas.sort()
        top3 = [c for _, _, c in filas[:3]]
        sens.append({"escenario": nombre, "top3": top3, "elegido_en_top3": (elegido in top3) if elegido else None})
    # ---- bloques por (locale, moneda): 1 locale + cluster de misma moneda (el regimen lo cruza el Maker); puntaje = media simple [SUPUESTO]
    bloques = {}
    for r in elegibles:
        bloques.setdefault((r["locale"], r["moneda_cobro"]), []).append(r)
    lista_bloques = []
    for (loc, mon), rs in bloques.items():
        media = sum(Decimal(r["total"]) for r in rs) / len(rs)
        lista_bloques.append({"locale": loc, "moneda_cobro": mon, "paises": [r["pais"] for r in rs], "puntaje_medio": q1(media)})
    lista_bloques.sort(key=lambda b: (-Decimal(b["puntaje_medio"]), b["locale"] or ""))
    codigos_rank = {m["codigo"] for m in mercados}
    return {
        "paises_permitidos_sin_ficha": sin_ficha,
        "paises_con_ficha_sin_desglose_de_ranking": sorted(set(ctx["fichas"]) - codigos_rank),  # [PENDIENTE] rank.py solo cubre 15 mercados: se evaluan R1-R10 pero no se puntuan
        "fase_pagos": fase, "decision_managed_payments": decision_mp, "subnivel_candidato": sub,
        "parametros": {"pesos": pesos, "peso_ajuste_creadores": params["peso_ajuste_creadores"], "ctr_enlace": params["ctr_enlace_central"],
                       "mult_cpm_central": params["mult_cpm"]["central"], "mult_cpm_efectivo": str(mult_ef),
                       "cpm_vencido": cpm_vencido, "etiqueta_cpm": "[SUPUESTO] CPM de referencia vencido: benchmark C hasta tener CPM propio" if cpm_vencido else None, "origen": "ver scripts/parametros_m1.fallback.json (SUPUESTO) o empresa/parametros.yaml"},
        "ranking": ranking, "excluidos": ex["excluidos"], "evaluados": ex["evaluados"], "bloques": lista_bloques,
        "elegido_pais": elegido, "elegido_sigue_en_top3_en_todos": all(s["elegido_en_top3"] for s in sens) if elegido else None,
        "sensibilidad": sens,
    }


# --------------------------------------------------------------------------- reproducir
def reproducir():
    R = cargar_rank()
    ruta = os.path.join(C.RAIZ, "scripts", "mercados", "rank.py")
    p = subprocess.run([sys.executable, "-I", ruta], capture_output=True, text=True, timeout=120)
    ok_08 = "OK: 15 totales" in p.stdout
    par, mercados, _ = R.cargar_datos()
    esc = R.definir_escenarios()["corregido"]
    filas = {f["codigo"]: round(f["total"]) for f in R.ranking(esc, par, mercados)}
    esperado = {"CA": 71, "AU": 67, "NZ": 64, "US": 64, "HUS": 64, "GB": 62, "IE": 58, "IT": 53, "PL": 51}
    difs = {c: (filas.get(c), v) for c, v in esperado.items() if filas.get(c) is None or abs(filas[c] - v) > 1}
    return {"rank_py_ok_15_totales": ok_08, "corregido_esperado_vs_obtenido_fuera_de_tolerancia": difs, "ok": ok_08 and not difs}


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("reproducir")
    pc = sub.add_parser("cobertura")
    pc.add_argument("ficha")
    pc.add_argument("--decision-mp", default="no_decidido", choices=["no_decidido", "si", "no"])
    for nombre in ("excluir", "seleccionar"):
        pe = sub.add_parser(nombre)
        pe.add_argument("contexto")
        pe.add_argument("--parametros", default=None)
        pe.add_argument("--hoy", default=None)
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return C.SALIDA_USO
    try:
        if a.cmd == "reproducir":
            r = reproducir()
            C.escribir_json(r)
            return C.SALIDA_OK if r["ok"] else C.SALIDA_VALIDACION
        if a.cmd == "cobertura":
            C.escribir_json(cobertura_por_fase(C.cargar_datos(a.ficha), a.decision_mp))
            return C.SALIDA_OK
        params, _ = C.cargar_parametros(getattr(a, "parametros", None))
        ctx = C.cargar_datos(a.contexto)
        base = os.path.dirname(os.path.abspath(a.contexto))
        # fichas: dict inline o rutas relativas al contexto
        fichas = {}
        for iso, f in (ctx.get("fichas") or {}).items():
            fichas[iso] = C.cargar_datos(os.path.join(base, f)) if isinstance(f, str) else f
        ctx["fichas"] = fichas
        if a.cmd == "excluir":
            C.escribir_json(excluir(ctx, params, a.hoy))
        else:
            C.escribir_json(seleccionar(ctx, params, a.hoy))
        return C.SALIDA_OK
    except C.DatoFaltante as e:
        C.imprimir_error(e)
        return C.SALIDA_FALTA_DATO
    except (OSError, KeyError, ValueError) as e:
        C.imprimir_error(f"{type(e).__name__}: {e}")
        return C.SALIDA_USO


if __name__ == "__main__":
    sys.exit(main())
