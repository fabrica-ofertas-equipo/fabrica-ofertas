#!/usr/bin/env python3
"""Calibración del Jurado de creativos contra lo cobrado: etiquetas por madurez, AUC, Brier, azar, rúbrica, apagado y promoción.

Qué hace el código: junta los ``jurado.json`` (predicciones selladas ANTES del resultado) con las métricas reales de cada
anuncio, construye etiquetas por madurez, mide el acierto con su intervalo y lo compara con el azar y con la rúbrica del QA.
Nunca llama a un LLM y NUNCA cambia nada solo: propone (``estado_global``, ``propuestas_reemplazo``); lo aplican personas o
los comandos ``avatares.py reemplazar`` y ``agregar.py --modo asesor`` con su registro.

Madurez de la etiqueta (H-10 de brechas/02: «inversión, vistas, gancho, clics, ventas», no solo ventas). A 3 días y ~15 USD las
ventas son ruido, así que se calibra primero con las etiquetas abundantes y solo ``ventas`` puede decir «predice ventas»:
  inversion      gasto de la pieza por encima de la mediana de su tanda (Meta le dio presupuesto: señal temprana)
  gancho         vistas de 3 s / impresiones por encima de la mediana de su tanda     (≥ ``min_impresiones``)
  clics          clics en el enlace / impresiones por encima de la mediana             (≥ ``min_impresiones``)
  pago_iniciado  pagos iniciados / clics por encima de la mediana                      (≥ ``min_clics``)
  ventas         compras netas ≥ ``min_compras_positivo`` con gasto ≥ ``gasto_min_ventas`` (sale de economia.json; sin él NO se etiqueta)
Las etiquetas son RELATIVAS a la tanda (estrictamente por encima de la mediana) para quitar el efecto del día y del presupuesto.

Estados (por nivel y global; el nivel con etiquetas más maduras y ≥ ``n_min_etiquetas`` decide):
  acumulando       menos de ``n_min_etiquetas`` etiquetas: medir el acierto sería medir ruido; no se juzga.
  apagar           con ≥ ``n_min_etiquetas``: AUC ≤ azar, o ni el extremo optimista del IC95 llega a ``auc_min``. Se apaga solo.
  sombra           supera al azar pero aún no cumple todo lo de abajo: sigue prediciendo sin decidir.
  elegible_asesor  AUC ≥ ``auc_min``, IC95 por encima del azar, p < alfa contra el azar, supera a la rúbrica (DeLong pareado,
                   p < alfa), anclas que discriminan (con alguna ancla medida) y etiquetas de clics o más maduras.
«Elegible» no promueve: la promoción la firma el dueño (``sombra-y-promocion.md``).

Uso (desde la raíz, con .venv)::

    .venv/bin/python -m scripts.jurado.calibrar --jurados T1/jurado.json T2/jurado.json --metricas metricas.jsonl --salida calibracion.json \\
        [--baseline longitud=otra.jsonl] [--fusionar-en T2/jurado.json] [--fixture]

Códigos de salida: 0 ok · 2 uso · 3 entrada inválida o regla violada.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.jurado import _comun as c
from scripts.jurado import estadistica as est
from scripts.jurado.agregar import sello_valido


# ---------------------------------------------------------------------------------------------------------------
# Entradas
# ---------------------------------------------------------------------------------------------------------------

def cargar_jurados(rutas: Sequence[str], fixture: bool) -> tuple[list[dict], list[dict]]:
    """(jurados válidos, descartados con motivo). Un jurado sin sello válido o de demostración no entra a una calibración real."""
    validos, descartados = [], []
    for r in rutas:
        j = c.leer_json(r)
        if not isinstance(j, Mapping) or j.get("tipo") != "jurado_creativos":
            descartados.append({"archivo": str(r), "motivo": "no es un jurado_creativos"})
        elif not sello_valido(j):
            descartados.append({"archivo": str(r), "motivo": "el sello no coincide con el contenido: la predicción pudo cambiarse después"})
        elif j.get("demostracion") and not fixture:
            descartados.append({"archivo": str(r), "motivo": "jurado de DEMOSTRACIÓN (votos sintéticos): no entra a una calibración real; usa --fixture para una prueba"})
        elif not j.get("demostracion") and fixture:
            descartados.append({"archivo": str(r), "motivo": "--fixture solo admite jurados de demostración o de fixture"})
        else:
            validos.append({**j, "_archivo": str(r)})
    return validos, descartados


def validar_metricas(filas: Sequence[Any]) -> list[dict]:
    salida = []
    for i, f in enumerate(filas):
        c.exigir(isinstance(f, Mapping) and isinstance(f.get("ad_name"), str) and isinstance(f.get("fecha_lectura"), str),
                 f"métricas[{i}]: falta ad_name o fecha_lectura")
        for k in ("gasto", "impresiones", "clics_enlace", "vistas_3s", "pagos_iniciados", "compras"):
            if f.get(k) is not None:
                c.exigir(c.es_numero(f[k]) and f[k] >= 0, f"métricas[{i}].{k}: debe ser un número ≥ 0 o null")
        salida.append(dict(f))
    return salida


def indexar_metricas(filas: Sequence[Mapping[str, Any]]) -> dict[tuple[str | None, str], dict]:
    """Última lectura de cada anuncio (más madura = más datos)."""
    idx: dict[tuple[str | None, str], dict] = {}
    for f in filas:
        k = (f.get("oferta_id"), f["ad_name"])
        if k not in idx or f["fecha_lectura"] >= idx[k]["fecha_lectura"]:
            idx[k] = dict(f)
    return idx


# ---------------------------------------------------------------------------------------------------------------
# Etiquetas por madurez
# ---------------------------------------------------------------------------------------------------------------

def _valor_relativo(m: Mapping[str, Any], nivel: str, p: Mapping[str, Any]) -> float | None:
    imp, cl = m.get("impresiones"), m.get("clics_enlace")
    if nivel == "inversion":
        return m.get("gasto")
    if nivel == "gancho":
        return m["vistas_3s"] / imp if imp and imp >= p["min_impresiones"] and m.get("vistas_3s") is not None else None
    if nivel == "clics":
        return cl / imp if imp and imp >= p["min_impresiones"] and cl is not None else None
    if nivel == "pago_iniciado":
        return m["pagos_iniciados"] / cl if cl and cl >= p["min_clics"] and m.get("pagos_iniciados") is not None else None
    return None


def etiquetar_tanda(jurado: Mapping[str, Any], idx: Mapping[tuple[str | None, str], Mapping[str, Any]], nivel: str, p: Mapping[str, Any]) -> tuple[list[dict], str | None]:
    """(filas {ad_name, score, share_si, valor, positivo}, motivo de exclusión). Solo cuentan los anuncios leídos DESPUÉS del sello."""
    candidatos = []
    for pz in jurado.get("piezas", []):
        m = idx.get((jurado.get("oferta_id"), pz["ad_name"])) or idx.get((None, pz["ad_name"]))
        if m is None:
            continue
        if not str(jurado.get("sellado_en", "")) < str(m["fecha_lectura"]):
            continue  # predicción sellada en o después de leer el resultado: no cuenta
        candidatos.append((pz, m))
    if nivel == "ventas":
        gmin = p.get("gasto_min_ventas")
        if gmin is None:
            return [], "falta gasto_min_ventas (sale de economia.json): sin él, «cero ventas» no significa nada"
        filas = []
        for pz, m in candidatos:
            if m.get("compras") is None or m.get("gasto") is None or m["gasto"] < gmin:
                continue
            filas.append({"ad_name": pz["ad_name"], "score": pz["score"], "share_si": pz["share_si"], "valor": m["compras"],
                          "positivo": 1 if m["compras"] >= p["min_compras_positivo"] else 0})
        return filas, (None if filas else "ninguna pieza alcanzó el gasto mínimo")
    valores = [(pz, _valor_relativo(m, nivel, p)) for pz, m in candidatos]
    valores = [(pz, v) for pz, v in valores if v is not None]
    if len(valores) < p["min_piezas_tanda_etiqueta"]:
        return [], f"menos de {p['min_piezas_tanda_etiqueta']} piezas con dato maduro en la tanda"
    med = c.mediana(v for _, v in valores)
    filas = [{"ad_name": pz["ad_name"], "score": pz["score"], "share_si": pz["share_si"], "valor": v, "positivo": 1 if v > med else 0} for pz, v in valores]
    if not any(f["positivo"] for f in filas) or all(f["positivo"] for f in filas):
        return [], "sin contraste: todas las piezas empatan en la mediana"
    return filas, None


# ---------------------------------------------------------------------------------------------------------------
# Estadísticos y estado por nivel
# ---------------------------------------------------------------------------------------------------------------

def _baselines(jurados: Sequence[Mapping[str, Any]], filas: Sequence[Mapping[str, Any]], extra: Mapping[str, Mapping[str, float]], p: Mapping[str, Any]) -> list[dict]:
    """Comparaciones del nivel: azar, «todos aprueban», rúbrica sin perfil y las que se pasen. Todas sobre las MISMAS piezas."""
    etiquetas = [f["positivo"] for f in filas]
    res = [{"nombre": "azar", "auc": p["auc_azar"], "nota": "moneda al aire por definición"},
           {"nombre": "todos_aprueban", "auc": est.auc([1.0] * len(filas), etiquetas), "nota": "puntaje constante: no ordena nada"}]
    rub: dict[str, float] = {}
    for j in jurados:
        for r in j.get("baseline_rubrica", []):
            rub[(j.get("oferta_id"), r["ad_name"])] = r["score"]
    fuentes = {"rubrica_unica": rub, **{k: {(None, a): s for a, s in v.items()} for k, v in extra.items()}}
    for nombre, mapa in fuentes.items():
        par = [(f, mapa.get((f["oferta"], f["ad_name"]), mapa.get((None, f["ad_name"])))) for f in filas]
        par = [(f, s) for f, s in par if s is not None]
        entrada = {"nombre": nombre, "n_pareado": len(par), "auc": None, "auc_jurado_mismas_piezas": None, "diferencia": None, "p_unilateral": None}
        if len(par) >= 4:
            y = [f["positivo"] for f, _ in par]
            entrada["auc"] = est.auc([s for _, s in par], y)
            cmp_ = est.comparar_auc_pareado([f["score"] for f, _ in par], [s for _, s in par], y)
            entrada["auc_jurado_mismas_piezas"] = est.auc([f["score"] for f, _ in par], y)
            if cmp_:
                entrada.update({"diferencia": cmp_["diferencia"], "p_unilateral": cmp_["p_unilateral"]})
        res.append(entrada)
    return res


def estadisticos_nivel(nivel: str, filas: list[dict], jurados: Sequence[Mapping[str, Any]], extra: Mapping[str, Mapping[str, float]],
                       p: Mapping[str, Any], semilla: int, motivos_exclusion: Sequence[str]) -> dict:
    n = len(filas)
    base = {"madurez": nivel, "etiquetas": n, "positivos": sum(f["positivo"] for f in filas), "excluidas_por": list(motivos_exclusion)}
    if n == 0:
        return {**base, "auc": None, "ic95": None, "p_vs_azar": None, "brier": None, "brier_prevalencia": None, "brier_skill": None,
                "baselines": [], "estado": "acumulando", "razones": ["sin etiquetas"]}
    y = [f["positivo"] for f in filas]
    r = est.auc_con_ic([f["score"] for f in filas], y)
    b = est.brier([f["share_si"] for f in filas], y)
    bp = est.brier_prevalencia(y)
    res = {**base, "auc": None if r is None else r["auc"], "ic95": None if r is None else r["ic95"],
           "p_vs_azar": est.p_contra_azar([f["score"] for f in filas], y, semilla, p["permutaciones"]) if r else None,
           "brier": b, "brier_prevalencia": bp, "brier_skill": (1 - b / bp) if b is not None and bp else None,
           "baselines": _baselines(jurados, filas, extra, p)}
    res["estado"], res["razones"] = estado_nivel(res, p)
    return res


def estado_nivel(r: Mapping[str, Any], p: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Estado de UN nivel a partir de sus estadísticos (las anclas se miran aparte, a nivel global)."""
    n = r["etiquetas"]
    if n < p["n_min_etiquetas"]:
        return "acumulando", [f"{n} de {p['n_min_etiquetas']} etiquetas: con menos, medir el acierto es medir ruido"]
    if r["auc"] is None:
        return "sombra", ["hay etiquetas pero una sola clase: no se puede medir el AUC"]
    ic = r["ic95"]
    if r["auc"] <= p["auc_azar"]:
        return "apagar", [f"AUC {r['auc']:.3f} ≤ {p['auc_azar']}: no supera al azar con {n} etiquetas"]
    if ic is not None and ic[1] < p["auc_min"]:
        return "apagar", [f"ni el extremo optimista del IC95 ({ic[1]:.3f}) llega al AUC mínimo útil ({p['auc_min']}) con {n} etiquetas"]
    razones = []
    if r["auc"] < p["auc_min"]:
        razones.append(f"AUC {r['auc']:.3f} < {p['auc_min']} (mínimo para ordenar)")
    if ic is None or ic[0] <= p["auc_azar"]:
        razones.append("el IC95 todavía incluye el azar")
    if r["p_vs_azar"] is None or r["p_vs_azar"] >= p["alfa"]:
        razones.append(f"p contra el azar ≥ {p['alfa']}")
    rub = next((x for x in r["baselines"] if x["nombre"] == "rubrica_unica"), None)
    if rub is None or rub["p_unilateral"] is None or rub["n_pareado"] < p["n_min_etiquetas"]:
        razones.append("sin comparación suficiente contra la rúbrica del QA (hacen falta ≥ n_min_etiquetas piezas puntuadas por ambos)")
    elif not (rub["diferencia"] > 0 and rub["p_unilateral"] < p["alfa"]):
        razones.append(f"no supera a la rúbrica (diferencia de AUC {rub['diferencia']:+.3f}, p {rub['p_unilateral']:.3f})")
    return ("sombra", razones) if razones else ("elegible_asesor", ["cumple los criterios de este nivel"])


# ---------------------------------------------------------------------------------------------------------------
# Por avatar
# ---------------------------------------------------------------------------------------------------------------

def _auc_jurado_sin(filas: Sequence[Mapping[str, Any]], votos: Mapping[str, Sequence[Mapping[str, Any]]], excluir: str | None) -> float | None:
    sc, y = [], []
    for f in filas:
        vs = [v for v in votos.get(f["ad_name"], []) if v["avatar_id"] != excluir]
        if not vs:
            continue
        sc.append(sum(1 for v in vs if v["voto"]) / len(vs) + 0.001 * statistics.fmean([v["puntaje_general"] for v in vs]) / 10)
        y.append(f["positivo"])
    return est.auc(sc, y)


def decidir_reemplazo(fila: Mapping[str, Any], p: Mapping[str, Any]) -> tuple[bool, str | None]:
    """¿Se propone retirar a este avatar? Solo propone; el reemplazo lo aplica ``avatares.py reemplazar`` con su registro.

    Camino 1 (mejora del jurado): con ≥ ``n_min_etiquetas_avatar`` etiquetas, quitarlo sube el AUC del jurado ≥ ``delta_reemplazo``
    y la mejora se repite en las DOS mitades de las etiquetas (si no, es ajuste a ruido), y él acierta menos que el jurado.
    Camino 2 (peor que el azar): su AUC propio tiene el IC95 entero por debajo del azar y quitarlo no empeora al jurado en ninguna mitad
    (cuando el jurado ya es casi perfecto, la mejora de quitarlo no llega a ``delta_reemplazo`` aunque el avatar sea inservible).
    """
    if fila["etiquetas"] < p["n_min_etiquetas_avatar"]:
        return False, None
    a, ic, d = fila["auc_propio"], fila.get("ic95_propio"), fila["mejora_al_quitarlo"]
    mitades = [fila["mejora_mitad_a"], fila["mejora_mitad_b"]]
    if any(m is None for m in mitades) or d is None or a is None:
        return False, None
    if d >= p["delta_reemplazo"] and all(m > 0 for m in mitades) and a <= (fila["auc_jurado"] or 0):
        return True, f"quitarlo sube el AUC del jurado {d:+.3f} (≥ {p['delta_reemplazo']}) y la mejora se repite en las dos mitades"
    if ic is not None and ic[1] < p["auc_azar"] and all(m >= 0 for m in mitades):
        return True, f"su AUC propio ({a:.3f}) está por debajo del azar con IC95 entero ({ic[0]:.3f}-{ic[1]:.3f}) y quitarlo no empeora al jurado"
    return False, None


def por_avatar(filas: Sequence[Mapping[str, Any]], jurados: Sequence[Mapping[str, Any]], p: Mapping[str, Any]) -> list[dict]:
    """Acierto de cada avatar, y qué pasa con el AUC del jurado si se lo quita (en las dos mitades, para no ajustar ruido)."""
    votos: dict[str, list[dict]] = {}
    for j in jurados:
        for v in j.get("votos", []):
            votos.setdefault(v["ad_name"], []).append(v)
    avatares = sorted({v["avatar_id"] for vs in votos.values() for v in vs})
    mitad = {f["ad_name"]: int(c.hash_corto("mitad", f["ad_name"], largo=2), 16) % 2 for f in filas}
    auc_total = _auc_jurado_sin(filas, votos, None)
    salida = []
    for aid in avatares:
        sc, y = [], []
        for f in filas:
            v = next((x for x in votos.get(f["ad_name"], []) if x["avatar_id"] == aid), None)
            if v:
                sc.append(v["puntaje_general"] + (0.5 if v["voto"] else 0.0))
                y.append(f["positivo"])
        propio = est.auc_con_ic(sc, y)
        sin_total = _auc_jurado_sin(filas, votos, aid)
        deltas = []
        for m in (0, 1):
            fm = [f for f in filas if mitad[f["ad_name"]] == m]
            a, b_ = _auc_jurado_sin(fm, votos, None), _auc_jurado_sin(fm, votos, aid)
            deltas.append(None if a is None or b_ is None else b_ - a)
        delta = None if sin_total is None or auc_total is None else sin_total - auc_total
        fila = {"avatar_id": aid, "etiquetas": len(sc), "auc_propio": None if propio is None else propio["auc"],
                "ic95_propio": None if propio is None else propio["ic95"], "auc_jurado": auc_total, "auc_jurado_sin_avatar": sin_total,
                "mejora_al_quitarlo": delta, "mejora_mitad_a": deltas[0], "mejora_mitad_b": deltas[1]}
        fila["propone_reemplazo"], fila["motivo_reemplazo"] = decidir_reemplazo(fila, p)
        salida.append(fila)
    return salida


# ---------------------------------------------------------------------------------------------------------------
# Calibración completa
# ---------------------------------------------------------------------------------------------------------------

def _anclas_resumen(jurados: Sequence[Mapping[str, Any]], p: Mapping[str, Any]) -> dict:
    con_ambas = [j for j in jurados if j.get("anclas", {}).get("share_si_ganadoras") is not None and j["anclas"].get("share_si_perdedoras") is not None]
    ok = [j for j in con_ambas if j["anclas"].get("discrimina")]
    medidas = sum(1 for j in jurados if j.get("anclas", {}).get("medidas", 0) > 0)
    pct = len(ok) / len(con_ambas) if con_ambas else None
    cumple = bool(pct is not None and pct >= p["anclas_min_pct"] and medidas >= 1)
    return {"tandas_con_ambas_anclas": len(con_ambas), "tandas_que_discriminan": len(ok), "pct_discrimina": pct, "tandas_con_ancla_medida": medidas,
            "minimo": p["anclas_min_pct"], "cumple": cumple}


def calibrar(jurados: Sequence[Mapping[str, Any]], metricas: Sequence[Mapping[str, Any]], parametros: Mapping[str, Any] | None = None,
             baselines_extra: Mapping[str, Mapping[str, float]] | None = None, fixture: bool = False, semilla: Any = "calibrar-v1",
             descartados: Sequence[Mapping[str, Any]] = (), ahora: str | None = None) -> dict:
    p = dict(c.PARAMETROS_DEFECTO, **(parametros or {}))
    c.exigir(bool(jurados), "no hay ningún jurado válido que calibrar")
    locales = {j.get("locale") for j in jurados}
    c.exigir(len(locales) == 1, f"mezcla de mercados {sorted(map(str, locales))}: se calibra un mercado por vez")
    locale = locales.pop()
    idx = indexar_metricas(validar_metricas(metricas))
    entero = c.semilla_a_entero(semilla)
    extra = baselines_extra or {}
    niveles, etiquetas_por_nivel = [], {}
    for nivel in c.MADUREZ:
        filas, motivos = [], []
        for j in jurados:
            fs, motivo = etiquetar_tanda(j, idx, nivel, p)
            if motivo:
                motivos.append(f"{j.get('tanda_id') or j.get('_archivo')}: {motivo}")
            for f in fs:
                filas.append({**f, "oferta": j.get("oferta_id"), "tanda_id": j.get("tanda_id")})
        etiquetas_por_nivel[nivel] = filas
        niveles.append(estadisticos_nivel(nivel, filas, jurados, extra, p, entero, motivos))
    maduros = [x for x in niveles if x["etiquetas"] >= p["n_min_etiquetas"]]
    principal = maduros[-1] if maduros else None
    anclas = _anclas_resumen(jurados, p)
    razones: list[str] = []
    if principal is None:
        estado = "acumulando"
        mejor = max(niveles, key=lambda x: x["etiquetas"])
        razones.append(f"ningún nivel llega a {p['n_min_etiquetas']} etiquetas (el más lleno: {mejor['madurez']} con {mejor['etiquetas']}): no se juzga el acierto")
    else:
        estado = principal["estado"]
        razones += principal["razones"]
        if estado == "elegible_asesor":
            if c.MADUREZ.index(principal["madurez"]) < c.MADUREZ.index("clics"):
                estado, razones = "sombra", razones + [f"el nivel «{principal['madurez']}» es demasiado temprano: «asesor» exige etiquetas de clics o más maduras"]
            elif not anclas["cumple"]:
                estado, razones = "sombra", razones + ["las anclas no cumplen: hace falta ≥ 1 tanda con ancla medida y que discriminen en ≥ "
                                                       f"{p['anclas_min_pct']:.0%} de las tandas con ambas anclas"]
        if principal["madurez"] != "ventas":
            razones.append("«predice ventas» NO está demostrado: el nivel decisivo es «" + principal["madurez"] + "»; las ventas aún no tienen etiquetas suficientes")
    if fixture:
        razones.append("FIXTURE: calculado con datos de prueba; no vale para decidir nada")
    nivel_ref = principal or max(niveles, key=lambda x: x["etiquetas"])
    por_av = por_avatar(etiquetas_por_nivel[nivel_ref["madurez"]], jurados, p) if nivel_ref["etiquetas"] else []
    ranking = sorted(niveles, key=lambda x: (c.MADUREZ.index(x["madurez"])), reverse=True)
    sugeridas = []
    base_anclas = max((etiquetas_por_nivel[x["madurez"]] for x in ranking if x["etiquetas"]), key=len, default=[])
    for veredicto, signo in (("ganadora", 1), ("perdedora", 0)):
        cand = sorted((f for f in base_anclas if f["positivo"] == signo), key=lambda f: (-f["valor"] if signo else f["valor"], f["ad_name"]))[:3]
        sugeridas += [{"ad_name": f["ad_name"], "oferta_id": f["oferta"], "veredicto_conocido": veredicto, "valor_metrica": f["valor"]} for f in cand]
    mejor_blq = nivel_ref
    precision = {
        "auc": mejor_blq["auc"], "brier": mejor_blq["brier"], "etiquetas": mejor_blq["etiquetas"], "estado": estado, "nivel": mejor_blq["madurez"],
        "ic95": mejor_blq["ic95"], "p_vs_azar": mejor_blq["p_vs_azar"], "n_min_etiquetas": p["n_min_etiquetas"],
        "baselines": [{"nombre": b["nombre"], "auc": b["auc"]} for b in mejor_blq["baselines"] if b.get("auc") is not None],
        "razones": razones, "fixture": fixture,
    }
    return {
        "schema_version": c.ESQUEMA_VERSION, "tipo": "calibracion_jurado", "fixture": fixture, "valido_para_decidir": not fixture,
        "locale": locale, "calculado_en": ahora or c.ahora_utc(), "semilla": semilla,
        "parametros": {k: p[k] for k in ("n_min_etiquetas", "auc_min", "auc_azar", "alfa", "anclas_min_pct", "delta_reemplazo", "n_min_etiquetas_avatar",
                                         "min_impresiones", "min_clics", "min_compras_positivo", "gasto_min_ventas", "permutaciones")},
        "nota_parametros": "Todos son [SUPUESTO] salvo el AUC de azar (0,5): ver scripts/jurado/_comun.py. Se calibran con datos propios.",
        "jurados": [{"archivo": j.get("_archivo"), "tanda_id": j.get("tanda_id"), "sello": j["sello"], "sellado_en": j["sellado_en"]} for j in jurados],
        "descartados": list(descartados), "niveles": niveles, "nivel_principal": principal["madurez"] if principal else None,
        "estado_global": estado, "razones": razones, "anclas": anclas, "por_avatar": por_av,
        "propuestas_reemplazo": [{"avatar_id": a["avatar_id"], "mejora_al_quitarlo": a["mejora_al_quitarlo"], "auc_propio": a["auc_propio"],
                                 "motivo": a["motivo_reemplazo"]} for a in por_av if a["propone_reemplazo"]],
        "anclas_sugeridas": {"nota": "candidatas por resultado real; las revisa una persona antes de usarlas como ancla", "candidatas": sugeridas},
        "accion": {"acumulando": "seguir en sombra y acumular etiquetas", "sombra": "seguir en sombra", "apagar": "APAGAR el jurado (deja de gastar tokens); reactivar exige decisión del dueño",
                   "elegible_asesor": "el dueño puede firmar la promoción a asesor (promocion.json)"}[estado],
        "precision": precision,
    }


def fusionar_precision(ruta_jurado: str, calibracion: Mapping[str, Any], ruta_calibracion: str, referencia: str | None = None) -> None:
    """Copia ``precision`` al jurado.json (la pantalla la lee de ahí). El sello no cambia: ``precision`` queda fuera de su alcance."""
    j = c.leer_json(ruta_jurado)
    c.exigir(sello_valido(j), f"{ruta_jurado}: sello inválido, no se toca")
    j["precision"] = calibracion["precision"]
    j["calibracion_ref"] = {"archivo": referencia or str(ruta_calibracion), "sha256": c.sha256_archivo(ruta_calibracion), "calculado_en": calibracion["calculado_en"],
                            "estado_global": calibracion["estado_global"]}
    c.escribir_json(ruta_jurado, j)


# ---------------------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.jurado.calibrar", description=__doc__.split("\n")[0])
    p.add_argument("--jurados", nargs="+", required=True)
    p.add_argument("--metricas", required=True, help="JSONL: ad_name, oferta_id, fecha_lectura, gasto, impresiones, clics_enlace, vistas_3s, pagos_iniciados, compras")
    p.add_argument("--salida", required=True)
    p.add_argument("--baseline", action="append", default=[], help="NOMBRE=archivo.jsonl con líneas {ad_name, score} (p. ej. virality)")
    p.add_argument("--parametros", default=None)
    p.add_argument("--semilla", default="calibrar-v1")
    p.add_argument("--fusionar-en", default=None, help="jurado.json donde copiar el bloque «precision» para la pantalla")
    p.add_argument("--fixture", action="store_true", help="datos de prueba: el resultado queda marcado y no vale para decidir")
    p.add_argument("--ahora", default=None)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        params = c.cargar_parametros(args.parametros)
        jurados, descartados = cargar_jurados(args.jurados, args.fixture)
        extra: dict[str, dict[str, float]] = {}
        for item in args.baseline:
            c.exigir("=" in item, f"--baseline {item!r}: usa NOMBRE=archivo.jsonl")
            nombre, ruta = item.split("=", 1)
            extra[nombre] = {f["ad_name"]: f["score"] for f in c.leer_jsonl(ruta)}
        cal = calibrar(jurados, c.leer_jsonl(args.metricas), params, extra, args.fixture, args.semilla, descartados, args.ahora)
        c.escribir_json(args.salida, cal)
        if args.fusionar_en:
            fusionar_precision(args.fusionar_en, cal, args.salida)
        print(f"estado_global: {cal['estado_global']} (nivel {cal['nivel_principal'] or '—'}) · acción: {cal['accion']}")
        for x in cal["niveles"]:
            auc_txt = "—" if x["auc"] is None else f"{x['auc']:.3f}"
            print(f"  {x['madurez']:<14} etiquetas {x['etiquetas']:>4}  AUC {auc_txt}  {x['estado']}")
        for r in cal["razones"]:
            print("  -", r)
        if cal["propuestas_reemplazo"]:
            print("  propuestas de reemplazo:", ", ".join(x["avatar_id"] for x in cal["propuestas_reemplazo"]))
        return c.SALIDA_OK
    except c.ErrorJurado as e:
        print(f"error: {e}", file=sys.stderr)
        return c.SALIDA_RECHAZO


if __name__ == "__main__":
    sys.exit(main())
