#!/usr/bin/env python3
"""qa_recomputar.py — recálculo INDEPENDIENTE para el QA de D2 (check L1-D3, spec §6). v0.1.0.

No importa `metricas.py` ni `veredicto.py`: reimplementa las fórmulas de §3.4 con `fractions.Fraction` (aritmética exacta)
para que un error de transcripción de la fórmula no pase desapercibido. Solo comparte `params.py` (carga de parámetros).
Compara contra `validacion.json` (y, si se da, contra la salida de `metricas.py`) y falla con código 3 ante CUALQUIER
diferencia (la regla es «diferencia ≠ 0 → falla»; DoD de D2: diferencia 0).

Uso:
  .venv/bin/python .claude/skills/d2-validacion/scripts/qa_recomputar.py ENTRADA.json VALIDACION.json [--metricas SALIDA_METRICAS.json] [--parametros P.yaml]
Salida 0 sin diferencias · 2 uso · 3 diferencias · 5 falta un parámetro.
"""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import params as P  # noqa: E402

ELEG = {"producto_digital", "curso_mentoria", "marca_personal_escalera"}
ORDEN = {"NO_GO": 0, "GO_CONDICIONAL": 1, "GO": 2}
CLAVES = [  # copia deliberada (independencia de metricas.py): todo parámetro que usa este recálculo
    "umbral_ss", "n_ind_sost_go", "is_go_max", "is_nogo_min", "umbral_hueco_ausencia", "min_frases_voz", "min_fuentes_voz",
    "relectura_dias", "anunciante_sostenido_dias_min", "anunciante_sostenido_conceptos_min", "ss_peso_s", "ss_peso_c",
    "ss_peso_i", "ss_peso_p", "ss_peso_e", "ss_paises_tope", "sep_iteracion_dias", "ventana_entrantes_dias",
    "marca_personal_peso", "is_peso_n", "is_peso_hhi", "is_peso_entrantes", "norm_N_ind", "mecanismo_share_saturado",
    "mecanismo_share_abierto", "mecanismo_n_min_operadores", "umbral_solapamiento", "convergencia_baja_max",
    "hueco_min_anuncios_leidos", "hueco_min_frases", "hueco_min_fuentes", "hueco_localizacion_min_ref",
    "min_frases_voz_propias", "max_share_fuente_voz", "min_share_frases_locale", "confianza_puntos_por_criterio",
    "confianza_pct_snapshots_min", "confianza_landings_min", "confianza_consultas_min", "confianza_pct_transcripcion_min",
    "confianza_media_min_puntos", "confianza_alta_min_puntos", "jaccard_replica_min", "nogo_frases_min",
]


def _f(x):
    return P.frac(x)


def _r3(x: F) -> F:
    """Redondeo half-up a 3 decimales."""
    return F((x * 1000 + F(1, 2)).__floor__(), 1000)


def _fmt3(x: F) -> str:
    n = int(x * 1000)  # exacto: x ya está redondeado a 3 decimales
    return f"{n // 1000}.{n % 1000:03d}"


def _r0(x: F) -> int:
    return (x + F(1, 2)).__floor__()


def recomputar(e: dict, p: dict) -> dict:
    g = lambda k: _f(p[k])  # noqa: E731
    dias_min, tope_c, sep = int(p["anunciante_sostenido_dias_min"]), g("anunciante_sostenido_conceptos_min"), int(p["sep_iteracion_dias"])
    pesos = [g("ss_peso_s"), g("ss_peso_c"), g("ss_peso_i"), g("ss_peso_p"), g("ss_peso_e")]
    cap = lambda v, t: v if v < t else t  # noqa: E731
    filas = {}
    for o in e["operadores"]:
        act = [c for c in o["conceptos"] if c["activo"]]
        s_a = len([c for c in act if c["antiguedad_dias"] >= dias_min])
        i_a = 0
        for m in {c["tipo_mecanismo"] for c in act}:
            edades = [c["antiguedad_dias"] for c in act if c["tipo_mecanismo"] == m]
            if len(edades) > 1 and max(edades) - min(edades) >= sep:
                i_a = 1
        p_a = len(set(o["paises"]).intersection(e["paises_consultados"]))
        e_a = F(str(o["embudo"]))
        ss = (pesos[0] * cap(F(s_a) / tope_c, F(1)) + pesos[1] * cap(F(len(act)) / tope_c, F(1)) + pesos[2] * i_a
              + pesos[3] * cap(F(p_a) / g("ss_paises_tope"), F(1)) + pesos[4] * e_a)
        ss = _r3(ss)
        filas[o["operador_id"]] = {"ss": ss, "sost": ss >= g("umbral_ss"), "tipo": o["tipo_anunciante"], "o": o, "act": act}
    sost = [k for k, v in filas.items() if v["sost"] and v["tipo"] in ELEG]
    n_ind = sum((g("marca_personal_peso") if filas[k]["tipo"] == "marca_personal_escalera" else F(1)) for k in sost)
    conceptos = [c for k in sost for c in filas[k]["act"]]
    base = conceptos or [c for v in filas.values() if v["tipo"] in ELEG for c in v["act"]]
    hhi = F(0)
    for ang in {c["angulo_principal"] for c in base}:
        hhi += (F(len([c for c in base if c["angulo_principal"] == ang]), len(base))) ** 2
    eleg_act = [v for v in filas.values() if v["tipo"] in ELEG and v["act"]]
    entr = F(len([v for v in eleg_act if v["o"]["primer_anuncio_observado_dias"] <= int(p["ventana_entrantes_dias"])]), len(eleg_act)) if eleg_act else F(0)
    is_ex = 100 * (g("is_peso_n") * cap(n_ind / g("norm_N_ind"), F(1)) + g("is_peso_hhi") * hhi + g("is_peso_entrantes") * entr)
    indice = max(0, min(100, _r0(is_ex)))
    # mecanismo
    mu = e["mu"]
    con_mu = len([k for k in sost if any(c["tipo_mecanismo"] == mu["tipo_mecanismo"] for c in filas[k]["act"])])
    share = F(con_mu, len(sost)) if sost else F(0)
    n_min = int(p["mecanismo_n_min_operadores"])
    if mu["indistinguible_de_sostenido"] or (len(sost) >= n_min and share >= g("mecanismo_share_saturado")):
        sat = "alta"
    elif len(sost) >= n_min and share <= g("mecanismo_share_abierto"):
        sat = "baja"
    else:
        sat = "media"
    # convergencia
    solap = F(len([c for c in conceptos if c["angulo_principal"] == e["angulo_recomendado"]]), len(conceptos)) if conceptos else F(0)
    if solap >= g("umbral_solapamiento"):
        conv = "media" if e.get("diferenciador_sustentado") else "alta"
    else:
        conv = "media" if solap >= g("convergencia_baja_max") else "baja"
    # confianza
    cd = e["confianza_datos"]
    crit = [cd["competidores_profundos"] > 0 and F(cd["competidores_con_snapshot_leido"], cd["competidores_profundos"]) >= g("confianza_pct_snapshots_min"),
            cd["landings_analizadas"] >= int(p["confianza_landings_min"]),
            cd["consultas_distintas"] >= int(p["confianza_consultas_min"]),
            cd["videos_total"] == 0 or F(cd["videos_transcriptos"], cd["videos_total"]) >= g("confianza_pct_transcripcion_min"),
            bool(cd["relectura_realizada"]) or (cd["historial_dias"] is not None and cd["historial_dias"] >= int(p["relectura_dias"]))]
    pts = int(p["confianza_puntos_por_criterio"]) * len([x for x in crit if x])
    jac = cd.get("jaccard_replica")
    if (not crit[0]) or (not cd["segunda_pasada"]) or (jac is not None and _f(jac) < g("jaccard_replica_min")):
        pts = min(pts, int(p["confianza_puntos_por_criterio"]))
    conf = "alta" if pts >= int(p["confianza_alta_min_puntos"]) else "media" if pts >= int(p["confianza_media_min_puntos"]) else "baja"
    # huecos
    evalu = [k for k in sost if filas[k]["o"]["anuncios_leidos"] >= int(p["hueco_min_anuncios_leidos"])]
    hueco = False
    for h in e["huecos"]:
        sin = [k for k in evalu if k not in h["presente_en"]]
        if evalu and F(len(sin), len(evalu)) >= g("umbral_hueco_ausencia") and h["frases"] >= int(p["hueco_min_frases"]) and h["fuentes"] >= int(p["hueco_min_fuentes"]):
            hueco = True
    # voz
    v = e["voz"]
    pos = [n for n in v["fuentes"].values() if n > 0]
    voz_ok = (v["frases_total"] >= int(p["min_frases_voz"]) and v["frases_propias"] >= int(p["min_frases_voz_propias"])
              and len(pos) >= int(p["min_fuentes_voz"]) and v["frases_total"] > 0 and bool(pos)
              and F(max(pos), sum(pos)) <= g("max_share_fuente_voz") and F(v["frases_del_locale"], v["frases_total"]) >= g("min_share_frases_locale"))
    # veredicto
    r = e["riesgo"]["final"]
    conf_ok = conf in ("media", "alta")
    nogo = [indice >= int(p["is_nogo_min"]) and not hueco,
            sat == "alta" and not hueco and conf_ok,
            r["nivel"] == "rojo" and not e["riesgo"]["reencuadre_verificable_x1"],
            not e["riesgo"]["angulo_seguro_existe"],
            len(sost) == 0 and v["frases_total"] < int(p["nogo_frases_min"]) and conf_ok]
    go = [e["lectura_snapshots"] in ("humano_muestreo", "navegador_auto"), n_ind >= g("n_ind_sost_go"), voz_ok,
          e.get("evidencia_locale", {}).get("e1_o_e2", 0) >= 1, hueco, indice <= int(p["is_go_max"]), conv != "alta", sat != "alta",
          e["sustituto_gratis"] in ("no_dominante", "diferenciado"),
          r["nivel"] == "verde" or (r["nivel"] == "amarillo" and r.get("subnivel") == "A"),
          e["riesgo"]["x1_dictamen"] != "FAIL", conf_ok]
    ref = (e.get("hueco_localizacion") or {}).get("sostenidos_pais_referencia_mismo_concepto", 0)
    loc = n_ind < g("n_ind_sost_go") and ref >= int(p["hueco_localizacion_min_ref"])
    calc = "NO_GO" if any(nogo) else ("GO" if all(go) and not loc else "GO_CONDICIONAL")
    return {"ss": {k: _fmt3(v["ss"]) for k, v in filas.items()},
            "sostenidos": len([1 for v in filas.values() if v["sost"]]), "n_ind": n_ind, "indice": indice, "sat": sat,
            "conv": conv, "puntos": pts, "calculado": calc, "n_eleg": len(sost)}


def comparar(e: dict, val: dict, p: dict, metricas: dict | None = None) -> list[str]:
    R = recomputar(e, p)
    d: list[str] = []
    vv, sa = val["veredicto"], val["saturacion"]
    if sa["indice"] != R["indice"]:
        d.append(f"saturacion.indice: validacion={sa['indice']} recálculo={R['indice']}")
    if sa["n_ind_sostenidos"] != R["n_ind"].__floor__():
        d.append(f"saturacion.n_ind_sostenidos: validacion={sa['n_ind_sostenidos']} recálculo={R['n_ind'].__floor__()}")
    if sa["saturacion_mecanismo"] != R["sat"]:
        d.append(f"saturacion_mecanismo: validacion={sa['saturacion_mecanismo']} recálculo={R['sat']}")
    if val["convergencia"]["estado"] != R["conv"]:
        d.append(f"convergencia.estado: validacion={val['convergencia']['estado']} recálculo={R['conv']}")
    if vv["confianza"]["puntos"] != R["puntos"]:
        d.append(f"confianza.puntos: validacion={vv['confianza']['puntos']} recálculo={R['puntos']}")
    if vv["calculado"] != R["calculado"]:
        d.append(f"veredicto.calculado: validacion={vv['calculado']} recálculo={R['calculado']}")
    if val["metricas_mercado"]["n_sostenidos"] != R["sostenidos"]:
        d.append(f"metricas_mercado.n_sostenidos: validacion={val['metricas_mercado']['n_sostenidos']} recálculo={R['sostenidos']}")
    if ORDEN[vv["propuesto"]] > ORDEN[R["calculado"]]:
        d.append(f"veredicto.propuesto={vv['propuesto']} mejora el calculado {R['calculado']} (S11)")
    if ORDEN[vv["final"]] > ORDEN[R["calculado"]] and val.get("origen_version") != "humano":
        d.append(f"veredicto.final={vv['final']} mejora el calculado {R['calculado']} sin origen_version=humano (S11)")
    if metricas:
        for fila in metricas["operadores"]:
            if R["ss"].get(fila["operador_id"]) != fila["SS_a"]:
                d.append(f"SS_a[{fila['operador_id']}]: metricas.py={fila['SS_a']} recálculo={R['ss'].get(fila['operador_id'])}")
    return d


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("entrada")
    ap.add_argument("validacion")
    ap.add_argument("--metricas")
    ap.add_argument("--parametros")
    a = ap.parse_args(argv)
    try:
        e = json.load(open(a.entrada, encoding="utf-8"))
        val = json.load(open(a.validacion, encoding="utf-8"))
        met = json.load(open(a.metricas, encoding="utf-8")) if a.metricas else None
        valores, _ = P.cargar(Path(a.parametros) if a.parametros else None)
        P.exigir(valores, CLAVES)
        d = comparar(e, val, valores, met)
    except P.ErrorD2 as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return ex.codigo
    except (OSError, json.JSONDecodeError, KeyError) as ex:
        print(f"ERROR: {type(ex).__name__}: {ex}", file=sys.stderr)
        return 2
    if d:
        for x in d:
            print(f"DIFERENCIA: {x}", file=sys.stderr)
        return 3
    print("OK: diferencia 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
