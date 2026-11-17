#!/usr/bin/env python3
"""metricas.py — métricas deterministas de D2 (departamentos/03-validacion.md §3.4). v0.1.0.

Entrada: `metricas_entrada.json` (plantilla en templates/). Salida: métricas por operador y de mercado
(SS_a, N_ind_sost, IS, saturación de mecanismo, convergencia, confianza, huecos sustentados) en JSON.
El veredicto NO se calcula aquí: lo hace `veredicto.py` con estas métricas. El QA las recalcula con
`qa_recomputar.py`, que NO importa este archivo (implementación independiente, Fraction en vez de Decimal).

Reglas: sin red; sin float (decimales como cadena); ningún umbral en el código (salen de params.py); el volumen bruto de
anuncios pesa 0; un conteo de una muestra truncada es un PISO (`s_a_es_piso`); evidencia sin URL https o sin fecha se
rechaza (código 3). Redondeos (half-up): SS_a a 3 decimales; IS a entero. Las comparaciones usan el valor redondeado,
que es el que se guarda y el que el QA ve.

Uso (desde la raíz del repositorio):
  .venv/bin/python .claude/skills/d2-validacion/scripts/metricas.py ENTRADA.json [--parametros P.yaml] [--salida OUT.json]
Salida 0 ok · 2 uso · 3 entrada inválida · 5 falta un parámetro.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import params as P  # noqa: E402

VERSION_SCRIPT = "0.1.0"
TIPOS_ANUNCIANTE = ("producto_digital", "curso_mentoria", "software", "servicio", "afiliado_reventa",
                    "marca_personal_escalera", "otro")
ELEGIBLES = ("producto_digital", "curso_mentoria", "marca_personal_escalera")  # los demás son sustitutos o ruido
MECANISMOS = tuple(f"M{i}" for i in range(1, 9))
EMBUDO = {"0": Decimal(0), "0.5": Decimal("0.5"), "1": Decimal(1)}
LECTURAS = ("humano_muestreo", "navegador_auto", "ninguno", "pendiente_humano")
CERO, UNO = Decimal(0), Decimal(1)
RX_FECHA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(T\d{2}:\d{2}:\d{2}Z)?$")
RX_URL = re.compile(r"^https://[^\s]+$")

REQUERIDOS = [
    "umbral_ss", "n_ind_sost_go", "is_go_max", "is_nogo_min", "umbral_hueco_ausencia", "min_frases_voz",
    "min_fuentes_voz", "relectura_dias", "anunciante_sostenido_dias_min", "anunciante_sostenido_conceptos_min",
    "ss_peso_s", "ss_peso_c", "ss_peso_i", "ss_peso_p", "ss_peso_e", "ss_paises_tope", "sep_iteracion_dias",
    "ventana_entrantes_dias", "marca_personal_peso", "is_peso_n", "is_peso_hhi", "is_peso_entrantes", "norm_N_ind",
    "mecanismo_share_saturado", "mecanismo_share_abierto", "mecanismo_n_min_operadores", "umbral_solapamiento",
    "convergencia_baja_max", "hueco_min_anuncios_leidos", "hueco_min_frases", "hueco_min_fuentes",
    "hueco_localizacion_min_ref", "min_frases_voz_propias", "max_share_fuente_voz", "min_share_frases_locale",
    "confianza_puntos_por_criterio", "confianza_pct_snapshots_min", "confianza_landings_min",
    "confianza_consultas_min", "confianza_pct_transcripcion_min", "confianza_media_min_puntos",
    "confianza_alta_min_puntos", "jaccard_replica_min", "nogo_frases_min",
]


def _d(x) -> Decimal:
    return P.dec(x)


def q3(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def q0(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _cmin(x: Decimal, tope: Decimal) -> Decimal:
    return x if x < tope else tope


# ---------------------------------------------------------------- validación de la entrada
def validar_entrada(e: dict) -> None:
    """Falla (código 3) ante cualquier dato fuera de contrato. No corrige nada."""
    err: list[str] = []

    def req(cond: bool, msg: str) -> None:
        if not cond:
            err.append(msg)

    req(isinstance(e, dict), "la entrada debe ser un objeto")
    if not isinstance(e, dict):
        raise P.ErrorValidacion("; ".join(err))
    for k in ("oferta_id", "candidato_id", "locale", "paises_consultados", "operadores", "evidencias", "mercado_resumen",
              "voz", "huecos", "sustituto_gratis", "lectura_snapshots", "confianza_datos", "riesgo", "angulo_recomendado", "mu"):
        req(k in e, f"falta «{k}»")
    if err:
        raise P.ErrorValidacion("; ".join(err))
    req(e["lectura_snapshots"] in LECTURAS, f"lectura_snapshots ∈ {LECTURAS}")
    cd = e["confianza_datos"]
    for k in ("competidores_profundos", "competidores_con_snapshot_leido", "landings_analizadas", "consultas_distintas",
              "videos_total", "videos_transcriptos"):
        req(isinstance(cd.get(k), int) and not isinstance(cd.get(k), bool) and cd[k] >= 0, f"confianza_datos.{k}: entero ≥ 0")
    for k in ("segunda_pasada", "relectura_realizada"):
        req(isinstance(cd.get(k), bool), f"confianza_datos.{k}: booleano")
    req(cd.get("historial_dias") is None or isinstance(cd.get("historial_dias"), int), "confianza_datos.historial_dias: entero o null")
    ms = e["mercado_resumen"]
    for k in ("anuncios_activos", "edad_mediana_dias"):
        req(isinstance(ms.get(k), int) and ms[k] >= 0, f"mercado_resumen.{k}: entero ≥ 0 (salida de puntaje_modelar resumir)")
    v = e["voz"]
    for k in ("frases_total", "frases_propias", "frases_del_locale"):
        req(isinstance(v.get(k), int) and v[k] >= 0, f"voz.{k}: entero ≥ 0")
    req(isinstance(v.get("fuentes"), dict), "voz.fuentes: objeto {fuente: n_frases}")
    req(e["sustituto_gratis"] in ("no_dominante", "diferenciado", "dominante", "no_medido"), "sustituto_gratis inválido")
    req(isinstance(e["paises_consultados"], list) and e["paises_consultados"], "paises_consultados: lista no vacía")
    # Evidencia: cada id referenciado debe existir con URL https y fecha (regla: evidencia sin URL o fecha se rechaza).
    ev = {}
    for i, x in enumerate(e["evidencias"]):
        ok = isinstance(x, dict) and isinstance(x.get("id"), str) and isinstance(x.get("url"), str) \
            and RX_URL.match(x["url"]) and isinstance(x.get("fecha"), str) and RX_FECHA.match(x["fecha"])
        req(bool(ok), f"evidencias[{i}]: exige id, url https y fecha (AAAA-MM-DD o ISO con Z)")
        if ok:
            ev[x["id"]] = x
    ids_usados: list[tuple[str, str]] = []
    ops = e["operadores"]
    req(isinstance(ops, list), "operadores: lista")
    vistos = set()
    for i, o in enumerate(ops if isinstance(ops, list) else []):
        pre = f"operadores[{i}]"
        req(isinstance(o, dict), f"{pre}: objeto")
        if not isinstance(o, dict):
            continue
        req(o.get("tipo_anunciante") in TIPOS_ANUNCIANTE, f"{pre}.tipo_anunciante ∈ {TIPOS_ANUNCIANTE}")
        req(isinstance(o.get("operador_id"), str) and o.get("operador_id") not in vistos, f"{pre}.operador_id único")
        vistos.add(o.get("operador_id"))
        req(str(o.get("embudo")) in EMBUDO, f"{pre}.embudo ∈ 0 | 0.5 | 1 (E_a)")
        req(isinstance(o.get("paises"), list), f"{pre}.paises: lista")
        req(isinstance(o.get("anuncios_leidos"), int) and o["anuncios_leidos"] >= 0, f"{pre}.anuncios_leidos: entero ≥ 0")
        req(isinstance(o.get("primer_anuncio_observado_dias"), int) and o["primer_anuncio_observado_dias"] >= 0,
            f"{pre}.primer_anuncio_observado_dias: entero ≥ 0")
        req(isinstance(o.get("truncado"), bool), f"{pre}.truncado: booleano")
        for j, c in enumerate(o.get("conceptos") or []):
            cp = f"{pre}.conceptos[{j}]"
            req(isinstance(c.get("concepto_id"), str) and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", c["concepto_id"] or ""),
                f"{cp}.concepto_id kebab sin «_»")
            req(isinstance(c.get("activo"), bool), f"{cp}.activo booleano")
            req(isinstance(c.get("antiguedad_dias"), int) and c["antiguedad_dias"] >= 0, f"{cp}.antiguedad_dias entero ≥ 0")
            req(c.get("tipo_mecanismo") in MECANISMOS, f"{cp}.tipo_mecanismo ∈ M1..M8")
            req(isinstance(c.get("angulo_principal"), str) and c["angulo_principal"], f"{cp}.angulo_principal")
            ids_usados.append((cp, c.get("evidencia_id")))
    for i, h in enumerate(e["huecos"]):
        for k in ("hueco_id", "presente_en", "frases", "fuentes"):
            req(k in h, f"huecos[{i}]: falta «{k}»")
        ids_usados.append((f"huecos[{i}]", h.get("evidencia_id")))
    mu = e.get("mu")
    if mu is not None:
        req(mu.get("tipo_mecanismo") in MECANISMOS, "mu.tipo_mecanismo ∈ M1..M8")
        req(isinstance(mu.get("indistinguible_de_sostenido"), bool), "mu.indistinguible_de_sostenido booleano")
        if mu.get("indistinguible_de_sostenido"):
            ids_usados.append(("mu", mu.get("evidencia_id")))
    for donde, i in ids_usados:
        req(i in ev, f"{donde}: evidencia_id {i!r} no existe en `evidencias` (con URL y fecha): se rechaza")
    r = e["riesgo"]
    for k in ("heredado", "final", "angulo_seguro_existe", "reencuadre_verificable_x1", "x1_dictamen"):
        req(k in r, f"riesgo.{k} falta")
    if not err:
        orden = {"verde": 0, "amarillo": 1, "rojo": 2}
        req(r["final"]["nivel"] in orden and r["heredado"]["nivel"] in orden, "riesgo.*.nivel ∈ verde|amarillo|rojo")
        if not err and orden[r["final"]["nivel"]] < orden[r["heredado"]["nivel"]]:
            err.append("riesgo.final BAJA el nivel heredado de D1: D2 solo puede subirlo (S16)")
        elif not err and r["final"]["nivel"] == r["heredado"]["nivel"] == "amarillo":
            if (r["heredado"].get("subnivel") == "B") and (r["final"].get("subnivel") != "B"):
                err.append("riesgo.final baja el subnivel B heredado a A: solo X1 puede hacerlo (S16)")
    if err:
        raise P.ErrorValidacion("entrada inválida: " + "; ".join(err))


# ---------------------------------------------------------------- cálculo
def _activos(op: dict) -> list[dict]:
    return [c for c in op["conceptos"] if c["activo"]]


def ss_operador(op: dict, paises: list[str], p: dict) -> dict:
    dias_min = int(p["anunciante_sostenido_dias_min"])
    tope = _d(p["anunciante_sostenido_conceptos_min"])
    sep = int(p["sep_iteracion_dias"])
    act = _activos(op)
    S = sum(1 for c in act if c["antiguedad_dias"] >= dias_min)
    C = len(act)
    por_mec: dict[str, list[int]] = {}
    for c in act:
        por_mec.setdefault(c["tipo_mecanismo"], []).append(c["antiguedad_dias"])
    I = 1 if any(len(v) >= 2 and max(v) - min(v) >= sep for v in por_mec.values()) else 0
    Pa = len(set(op["paises"]) & set(paises))
    E = EMBUDO[str(op["embudo"])]
    ss = (_d(p["ss_peso_s"]) * _cmin(_d(S) / tope, UNO)
          + _d(p["ss_peso_c"]) * _cmin(_d(C) / tope, UNO)
          + _d(p["ss_peso_i"]) * I
          + _d(p["ss_peso_p"]) * _cmin(_d(Pa) / _d(p["ss_paises_tope"]), UNO)
          + _d(p["ss_peso_e"]) * E)
    ss3 = q3(ss)
    return {"operador_id": op["operador_id"], "tipo_anunciante": op["tipo_anunciante"], "S_a": S, "C_a": C, "I_a": I,
            "P_a": Pa, "E_a": str(E), "SS_a": str(ss3), "sostenido": ss3 >= _d(p["umbral_ss"]),
            "s_a_es_piso": bool(op["truncado"])}


def calcular(e: dict, p: dict) -> dict:
    """Métricas completas. `p` = parámetros planos (params.cargar)."""
    P.exigir(p, REQUERIDOS)
    validar_entrada(e)
    ops = {o["operador_id"]: o for o in e["operadores"]}
    por_op = [ss_operador(o, e["paises_consultados"], p) for o in e["operadores"]]
    sost_ids = [x["operador_id"] for x in por_op if x["sostenido"]]
    sost_elegibles = [i for i in sost_ids if ops[i]["tipo_anunciante"] in ELEGIBLES]
    # N_ind_sost: operadores sostenidos de producto_digital o curso_mentoria; marca_personal_escalera × peso.
    n_ind = CERO
    for i in sost_elegibles:
        n_ind += _d(p["marca_personal_peso"]) if ops[i]["tipo_anunciante"] == "marca_personal_escalera" else UNO
    # Conceptos sostenidos = conceptos activos de operadores sostenidos elegibles.
    conc_sost = [(i, c) for i in sost_elegibles for c in _activos(ops[i])]
    # IS: HHI de ángulos y fracción de entrantes (sobre operadores elegibles con >= 1 concepto activo) [SUPUESTO].
    base = conc_sost or [(o["operador_id"], c) for o in e["operadores"] if o["tipo_anunciante"] in ELEGIBLES
                         for c in _activos(o)]
    hhi = CERO
    if base:
        cuenta: dict[str, int] = {}
        for _, c in base:
            cuenta[c["angulo_principal"]] = cuenta.get(c["angulo_principal"], 0) + 1
        hhi = sum((_d(n) / _d(len(base))) ** 2 for n in cuenta.values())
    elegibles = [o for o in e["operadores"] if o["tipo_anunciante"] in ELEGIBLES and _activos(o)]
    entrantes = CERO
    if elegibles:
        entrantes = _d(sum(1 for o in elegibles if o["primer_anuncio_observado_dias"] <= int(p["ventana_entrantes_dias"]))) \
            / _d(len(elegibles))
    norm = _d(p["norm_N_ind"])
    is_exacto = 100 * (_d(p["is_peso_n"]) * _cmin(n_ind / norm, UNO) + _d(p["is_peso_hhi"]) * hhi
                       + _d(p["is_peso_entrantes"]) * entrantes)
    indice = max(0, min(100, q0(is_exacto)))
    # Saturación de mecanismo.
    mu = e.get("mu") or {}
    o_n = len(sost_elegibles)
    share_mu = None
    if mu:
        con_m = sum(1 for i in sost_elegibles if any(c["tipo_mecanismo"] == mu["tipo_mecanismo"] for c in _activos(ops[i])))
        share_mu = _d(con_m) / _d(o_n) if o_n else CERO
    nmin = int(p["mecanismo_n_min_operadores"])
    if mu and (mu["indistinguible_de_sostenido"] or (o_n >= nmin and share_mu >= _d(p["mecanismo_share_saturado"]))):
        sat = "alta"
    elif mu and o_n >= nmin and share_mu <= _d(p["mecanismo_share_abierto"]):
        sat = "baja"
    else:
        sat = "media"  # incluye |O| < n_min: no concluyente
    # Convergencia.
    solap = CERO
    if conc_sost:
        solap = _d(sum(1 for _, c in conc_sost if c["angulo_principal"] == e["angulo_recomendado"])) / _d(len(conc_sost))
    umbral_sol = _d(p["umbral_solapamiento"])
    dif = bool(e.get("diferenciador_sustentado", False))
    if solap >= umbral_sol:
        conv = "media" if dif else "alta"
    elif solap >= _d(p["convergencia_baja_max"]):
        conv = "media"
    else:
        conv = "baja"
    # Huecos sustentados.
    leidos_min = int(p["hueco_min_anuncios_leidos"])
    evaluados = [i for i in sost_elegibles if ops[i]["anuncios_leidos"] >= leidos_min]
    huecos_ok, huecos_det = [], []
    for h in e["huecos"]:
        sin = [i for i in evaluados if i not in h["presente_en"]]
        ratio = _d(len(sin)) / _d(len(evaluados)) if evaluados else CERO
        ok = bool(evaluados) and ratio >= _d(p["umbral_hueco_ausencia"]) and h["frases"] >= int(p["hueco_min_frases"]) \
            and h["fuentes"] >= int(p["hueco_min_fuentes"])
        huecos_det.append({"hueco_id": h["hueco_id"], "sostenidos_evaluados": len(evaluados), "sostenidos_sin_hueco": len(sin),
                           "ausencia": str(q3(ratio)), "frases": h["frases"], "fuentes": h["fuentes"], "sustentado": ok})
        if ok:
            huecos_ok.append(h["hueco_id"])
    conf = confianza(e, p)
    voz = voz_minima(e["voz"], p)
    return {
        "version_script": VERSION_SCRIPT,
        "operadores": por_op,
        "metricas_mercado": {"n_anuncios": e["mercado_resumen"]["anuncios_activos"], "n_anunciantes": len(e["operadores"]),
                             "n_sostenidos": len(sost_ids), "edad_mediana_dias": e["mercado_resumen"]["edad_mediana_dias"]},
        "n_ind_sost": str(n_ind), "n_ind_sostenidos_entero": int(n_ind),  # entero hacia abajo (esquema: integer)
        "n_sostenidos_elegibles": o_n,
        "IS": {"indice": indice, "valor_exacto": str(is_exacto.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
               "HHI_ang": str(q3(hhi)), "entrantes": str(q3(entrantes)),
               "n_conceptos_base": len(base), "base_es_sostenidos": bool(conc_sost)},
        "saturacion_mecanismo": {"nivel": sat, "share_mu": None if share_mu is None else str(q3(share_mu)), "O": o_n},
        "convergencia": {"estado": conv, "solapamiento_angulo": str(q3(solap))},
        "huecos": huecos_det, "hueco_sustentado": bool(huecos_ok), "huecos_sustentados": huecos_ok,
        "confianza": conf, "voz": voz,
        "parametros_usados": {k: p[k] for k in REQUERIDOS},
    }


def confianza(e: dict, p: dict) -> dict:
    c = e["confianza_datos"]
    req = {k: c[k] for k in ("competidores_profundos", "competidores_con_snapshot_leido", "landings_analizadas",
                             "consultas_distintas", "segunda_pasada", "videos_total", "videos_transcriptos",
                             "relectura_realizada", "historial_dias")}
    prof = req["competidores_profundos"]
    c1 = prof > 0 and _d(req["competidores_con_snapshot_leido"]) / _d(prof) >= _d(p["confianza_pct_snapshots_min"])
    c2 = req["landings_analizadas"] >= int(p["confianza_landings_min"])
    c3 = req["consultas_distintas"] >= int(p["confianza_consultas_min"])
    c4 = req["videos_total"] == 0 or _d(req["videos_transcriptos"]) / _d(req["videos_total"]) >= _d(p["confianza_pct_transcripcion_min"])
    hist = req["historial_dias"]
    c5 = bool(req["relectura_realizada"]) or (hist is not None and hist >= int(p["relectura_dias"]))
    cumplidos = [c1, c2, c3, c4, c5]
    por = int(p["confianza_puntos_por_criterio"])
    puntos = por * sum(1 for x in cumplidos if x)
    jac = c.get("jaccard_replica")
    forzada = (not c1) or (not req["segunda_pasada"]) or (jac is not None and _d(jac) < _d(p["jaccard_replica_min"]))
    if forzada:
        puntos = min(puntos, por)  # «media o más exige (1) y 2.ª pasada»; réplica con Jaccard bajo → baja
    nivel = "alta" if puntos >= int(p["confianza_alta_min_puntos"]) else "media" if puntos >= int(p["confianza_media_min_puntos"]) else "baja"
    return {"puntos": puntos, "nivel": nivel, "criterios": {"c1_snapshots": c1, "c2_landings": c2, "c3_consultas": c3,
                                                           "c4_transcripcion": c4, "c5_relectura_o_historial": c5},
            "forzada_a_baja": forzada}


def voz_minima(v: dict, p: dict) -> dict:
    """¿Se cumplen las frases y fuentes mínimas? (insumo de GO y de NO_GO)."""
    total, propias, locale_n = v["frases_total"], v["frases_propias"], v["frases_del_locale"]
    fuentes = v["fuentes"]  # {fuente: n_frases}
    n_f = sum(fuentes.values())
    max_share = _d(max(fuentes.values(), default=0)) / _d(n_f) if n_f else CERO
    ok = (total >= int(p["min_frases_voz"]) and propias >= int(p["min_frases_voz_propias"])
          and len([1 for n in fuentes.values() if n > 0]) >= int(p["min_fuentes_voz"])
          and max_share <= _d(p["max_share_fuente_voz"]) and total > 0
          and _d(locale_n) / _d(total) >= _d(p["min_share_frases_locale"]))
    return {"frases_total": total, "frases_propias": propias, "fuentes": len([1 for n in fuentes.values() if n > 0]),
            "max_share_fuente": str(q3(max_share)), "minimas_cumplidas": bool(ok)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("entrada")
    ap.add_argument("--parametros", help="YAML con `grupos:` (por defecto empresa/parametros.yaml + propuesta de la skill)")
    ap.add_argument("--salida", help="escribe el JSON aquí (no sobrescribe)")
    a = ap.parse_args(argv)
    try:
        with open(a.entrada, encoding="utf-8") as f:
            e = json.load(f)
        valores, orig = P.cargar(Path(a.parametros) if a.parametros else None)
        out = calcular(e, valores)
        out["parametros_origen"] = {k: orig[k] for k in REQUERIDOS}
    except P.ErrorD2 as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return ex.codigo
    except (OSError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if a.salida:
        ruta = Path(a.salida)
        if ruta.exists():
            print(f"ERROR: {ruta} ya existe (no se sobrescribe)", file=sys.stderr)
            return 2
        ruta.write_text(txt + "\n", encoding="utf-8")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
