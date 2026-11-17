#!/usr/bin/env python3
"""veredicto.py — veredicto CALCULADO de D2 (GO | GO_CONDICIONAL | NO_GO), departamentos/03-validacion.md §3.4. v0.1.0.

El veredicto lo calcula este script, no un LLM. El Maker lo PROPONE y solo puede DEGRADARLO (GO > GO_CONDICIONAL > NO_GO),
nunca mejorarlo; mejorarlo exige decisión del dueño (origen_version = humano). `final` no puede ser mejor que `calculado`
salvo con origen_version = humano. Un riesgo ROJO, un amarillo-b, un veto de X1 o una lectura de snapshots «ninguno» /
«pendiente_humano» nunca dan GO.

Subcomandos:
  calcular  ENTRADA.json [--parametros P.yaml]        -> JSON con calculado, condiciones y códigos de razón
  comprobar ENTRADA.json VALIDACION.json [...]        -> verifica que validacion.json respeta el veredicto calculado,
                                                         que propuesto <= calculado y que final <= calculado (salvo humano)
Salida 0 ok · 2 uso · 3 incoherente o entrada inválida · 5 falta un parámetro.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metricas as M  # noqa: E402
import params as P  # noqa: E402

RANGO = {"NO_GO": 0, "GO_CONDICIONAL": 1, "GO": 2}


def _riesgo_apto_go(r: dict) -> bool:
    f = r["final"]
    return f["nivel"] == "verde" or (f["nivel"] == "amarillo" and f.get("subnivel") == "A")


def decidir(e: dict, m: dict, p: dict) -> dict:
    """Aplica las reglas de §3.4 sobre las métricas `m` (salida de metricas.calcular)."""
    r = e["riesgo"]
    conf_ok = m["confianza"]["nivel"] in ("media", "alta")
    hueco = m["hueco_sustentado"]
    n_ind = M._d(m["n_ind_sost"])
    iss = m["IS"]["indice"]
    sat = m["saturacion_mecanismo"]["nivel"]
    conv = m["convergencia"]["estado"]
    lectura_ok = e["lectura_snapshots"] in ("humano_muestreo", "navegador_auto")
    n_sost = m["n_sostenidos_elegibles"]
    # --- GO: todas las condiciones (spec §3.4)
    cond_go = {
        "lectura_snapshots_distinta_de_ninguno": lectura_ok,
        "n_ind_sost_minimo": n_ind >= M._d(p["n_ind_sost_go"]),
        "frases_y_fuentes_minimas": m["voz"]["minimas_cumplidas"],
        "evidencia_e1_o_e2_en_locale": e.get("evidencia_locale", {}).get("e1_o_e2", 0) >= 1,
        "hueco_sustentado": hueco,
        "is_no_supera_maximo": iss <= int(p["is_go_max"]),
        "convergencia_no_alta": conv != "alta",
        "saturacion_mecanismo_no_alta": sat != "alta",
        "sustituto_gratis_no_dominante": e["sustituto_gratis"] in ("no_dominante", "diferenciado"),
        "riesgo_verde_o_amarillo_a": _riesgo_apto_go(r),
        "x1_no_veta": r["x1_dictamen"] != "FAIL",
        "confianza_media_o_mas": conf_ok,
    }
    # --- NO_GO: cualquiera de estas (spec §3.4)
    cond_nogo = {
        "is_muy_alto_sin_hueco": iss >= int(p["is_nogo_min"]) and not hueco,
        "mecanismo_saturado_sin_hueco_con_confianza": sat == "alta" and not hueco and conf_ok,
        "riesgo_rojo_sin_reencuadre_verificable": r["final"]["nivel"] == "rojo" and not r["reencuadre_verificable_x1"],
        "ningun_angulo_seguro": not r["angulo_seguro_existe"],
        "cero_sostenidos_pocas_frases_con_confianza": n_sost == 0 and m["voz"]["frases_total"] < int(p["nogo_frases_min"]) and conf_ok,
    }
    hl = e.get("hueco_localizacion") or {}
    hueco_loc = (n_ind < M._d(p["n_ind_sost_go"])
                 and hl.get("sostenidos_pais_referencia_mismo_concepto", 0) >= int(p["hueco_localizacion_min_ref"]))
    if any(cond_nogo.values()):
        calculado = "NO_GO"
    elif all(cond_go.values()) and not hueco_loc:
        calculado = "GO"
    else:
        calculado = "GO_CONDICIONAL"
    # Un riesgo ROJO con reencuadre verificable aprobado por X1 no es GO por sí mismo: queda condicionado (gate H).
    razones = [f"NO_GO:{k}" for k, v in cond_nogo.items() if v]
    if calculado != "NO_GO":
        razones += [f"falta:{k}" for k, v in cond_go.items() if not v]
        if hueco_loc:
            razones.append("hueco_de_localizacion:hipotesis_para_d7_nunca_GO")
        if r["final"]["nivel"] == "amarillo" and r["final"].get("subnivel") != "A":
            razones.append("riesgo_amarillo_B_o_sin_subnivel:gate_H_ayuda_verificada_revision")
    return {
        "calculado": calculado,
        "provisional": e["lectura_snapshots"] == "pendiente_humano",
        "hueco_de_localizacion": hueco_loc,
        "condiciones_go": cond_go, "condiciones_nogo": cond_nogo, "razones_codigo": razones,
        "confianza": {"puntos": m["confianza"]["puntos"], "nivel": m["confianza"]["nivel"]},
    }


def calcular(e: dict, p: dict) -> dict:
    m = M.calcular(e, p)
    v = decidir(e, m, p)
    v["metricas"] = m
    return v


def comprobar(e: dict, val: dict, p: dict) -> list[str]:
    """Devuelve la lista de incoherencias de validacion.json frente al cálculo (vacía = coherente)."""
    res = calcular(e, p)
    m = res["metricas"]
    err: list[str] = []
    vv = val.get("veredicto", {})
    calc = res["calculado"]
    if vv.get("calculado") != calc:
        err.append(f"veredicto.calculado={vv.get('calculado')!r} pero el script da {calc!r}")
    if vv.get("propuesto") not in RANGO or RANGO.get(vv.get("propuesto"), 99) > RANGO[calc]:
        err.append(f"veredicto.propuesto={vv.get('propuesto')!r} MEJORA el calculado {calc!r}: el Maker solo puede degradar (S11)")
    if vv.get("final") not in RANGO:
        err.append("veredicto.final inválido")
    elif RANGO[vv["final"]] > RANGO[calc] and val.get("origen_version") != "humano":
        err.append(f"veredicto.final={vv['final']!r} es mejor que el calculado {calc!r} sin origen_version=humano (S11)")
    if vv.get("confianza", {}).get("puntos") != m["confianza"]["puntos"]:
        err.append(f"confianza.puntos={vv.get('confianza', {}).get('puntos')} ≠ {m['confianza']['puntos']}")
    s = val.get("saturacion", {})
    if s.get("indice") != m["IS"]["indice"]:
        err.append(f"saturacion.indice={s.get('indice')} ≠ {m['IS']['indice']}")
    if s.get("n_ind_sostenidos") != m["n_ind_sostenidos_entero"]:
        err.append(f"saturacion.n_ind_sostenidos={s.get('n_ind_sostenidos')} ≠ {m['n_ind_sostenidos_entero']}")
    if s.get("saturacion_mecanismo") != m["saturacion_mecanismo"]["nivel"]:
        err.append(f"saturacion.saturacion_mecanismo={s.get('saturacion_mecanismo')} ≠ {m['saturacion_mecanismo']['nivel']}")
    if val.get("convergencia", {}).get("estado") != m["convergencia"]["estado"]:
        err.append(f"convergencia.estado={val.get('convergencia', {}).get('estado')} ≠ {m['convergencia']['estado']}")
    mm = val.get("metricas_mercado", {})
    for k, v in m["metricas_mercado"].items():
        if mm.get(k) != v:
            err.append(f"metricas_mercado.{k}={mm.get(k)} ≠ {v}")
    # D2-D4: ninguna métrica se apoya en conteo bruto: se comprueba que el script no use estimated_total_count (por construcción).
    if val.get("riesgo_politica", {}).get("nivel") != e["riesgo"]["final"]["nivel"]:
        err.append("riesgo_politica.nivel ≠ riesgo.final.nivel de la entrada (D2 solo sube el nivel, nunca lo baja)")
    return err


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c1 = sub.add_parser("calcular")
    c1.add_argument("entrada")
    c1.add_argument("--parametros")
    c2 = sub.add_parser("comprobar")
    c2.add_argument("entrada")
    c2.add_argument("validacion")
    c2.add_argument("--parametros")
    a = ap.parse_args(argv)
    try:
        with open(a.entrada, encoding="utf-8") as f:
            e = json.load(f)
        valores, orig = P.cargar(Path(a.parametros) if a.parametros else None)
        if a.cmd == "calcular":
            out = calcular(e, valores)
            out["parametros_origen"] = {k: orig[k] for k in M.REQUERIDOS}
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        with open(a.validacion, encoding="utf-8") as f:
            val = json.load(f)
        err = comprobar(e, val, valores)
        if err:
            for x in err:
                print(f"INCOHERENTE: {x}", file=sys.stderr)
            return 3
        print("OK: validacion.json coincide con el cálculo")
        return 0
    except P.ErrorD2 as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return ex.codigo
    except (OSError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
