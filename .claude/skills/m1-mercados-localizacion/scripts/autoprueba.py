#!/usr/bin/env python3
"""M1 - autoprueba.py: pruebas deterministas de la skill (las que SI se pueden medir sin LLM).

Corre: (1) reproduccion de rank.py, (2) cobertura por fase en PL/IT/CA, (3) golden D01 y D02, (4) vigencia y trazabilidad,
(5) lint_locale, (6) chequeos L1 sobre las plantillas (0 bloqueantes) y (7) cada DEFECTO SEMBRADO con `via` de script:
debe ser detectado por el check esperado. Los sembrados `via: L2` (juicio del QA) se listan como NO medibles aqui: los mide el QA en una corrida.
Uso: .venv/bin/python -I .claude/skills/m1-mercados-localizacion/scripts/autoprueba.py [--solo-sembrados] [--json]
Sale 0 si todo pasa; 3 si algo falla. Sin red, sin escribir archivos.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as C  # noqa: E402
import chequeos_l1 as L  # noqa: E402
import lint_locale as LL  # noqa: E402
import puntaje as P  # noqa: E402
import vigencia as V  # noqa: E402

SK = os.path.abspath(os.path.join(C.AQUI, ".."))
DOR = os.path.join(SK, "evals", "dorados")
SEM = os.path.join(SK, "evals", "sembrados")
HOY = "2026-11-06"
LIMITES_SIM = os.path.join(DOR, "D01-dinero-verde-it-pl", "limites.simulado.yaml")


# --------------------------------------------------------------------------- utilidades
def puntero(obj, ruta):
    partes = [p for p in ruta.split("/") if p != ""]
    for p in partes[:-1]:
        obj = obj[int(p)] if isinstance(obj, list) else obj[p]
    return obj, partes[-1]


def aplicar(obj, ops):
    obj = copy.deepcopy(obj)
    for op in ops:
        if op["op"] == "reemplazar_todo":
            obj = op["valor"]
            continue
        padre, k = puntero(obj, op["ruta"])
        k_ = int(k) if isinstance(padre, list) else k
        if op["op"] == "set":
            if isinstance(padre, list):
                padre[k_] = op["valor"]
            else:
                padre[k_] = op["valor"]
        elif op["op"] == "del":
            del padre[k_]
        elif op["op"] == "append":
            padre[k_].append(op["valor"])
        else:
            raise ValueError(op)
    return obj


def cargar_fichas_fixture():
    d = os.path.join(DOR, "fixtures")
    return {n[5:7]: C.cargar_json(os.path.join(d, n)) for n in sorted(os.listdir(d)) if re.match(r"^pais-[A-Z]{2}\.json$", n)}


def cargar_ctx(nombre):
    ruta = os.path.join(DOR, nombre, "contexto.json")
    ctx = C.cargar_json(ruta)
    base = os.path.dirname(ruta)
    ctx["fichas"] = {k: C.cargar_json(os.path.join(base, v)) for k, v in ctx["fichas"].items()}
    return ctx


def ctx_inline_a_fichas(ctx):
    return ctx


# --------------------------------------------------------------------------- pruebas
RES = []


def prueba(nombre, ok, detalle=""):
    RES.append({"prueba": nombre, "ok": bool(ok), "detalle": detalle})


def correr_pruebas(params, limites):
    # 1) rank.py
    rep = P.reproducir()
    prueba("rank.py reproduce los 15 totales de 08 y el escenario corregido (CA 71 ... IT 53, PL 51 ±1)", rep["ok"], json.dumps(rep, ensure_ascii=False))
    fichas = cargar_fichas_fixture()
    # 2) cobertura por fase
    cb = {iso: P.cobertura_por_fase(f) for iso, f in fichas.items()}
    prueba("PL: fase vigente 17,0 % y con_locales 67,0 % (valor de desbloqueo 50,0 pp)",
           cb["PL"][P.FASE_ESTANDAR]["cobertura_pct"] == "17.0" and cb["PL"][P.FASE_LOCALES]["cobertura_pct"] == "67.0" and cb["PL"]["valor_desbloqueo_pp"] == "50.0")
    prueba("IT: fase vigente 48,0 % (rango 46-50 de 07h) y hueco PayPal 30,0 pp",
           cb["IT"][P.FASE_ESTANDAR]["cobertura_pct"] == "48.0" and cb["IT"][P.FASE_ESTANDAR]["hueco_paypal_pp"] == "30.0")
    prueba("CA: 74,0 % (07g §6) y sin valor de desbloqueo", cb["CA"][P.FASE_ESTANDAR]["cobertura_pct"] == "74.0" and cb["CA"]["valor_desbloqueo_pp"] == "0.0")
    prueba("PL con Managed Payments = si: BLIK sale y la cobertura cae a 17,0 %", P.cobertura_por_fase(fichas["PL"], "si")[P.FASE_LOCALES]["cobertura_pct"] == "17.0")
    prueba("PayPal, Klarna y Amazon Pay nunca suman (MQ-13)",
           not any(x["id"] in P.NUNCA_SUMAN for iso in cb for fase in (P.FASE_ESTANDAR, P.FASE_LOCALES) for x in cb[iso][fase]["suman"]))
    # 3) D01
    ctx = cargar_ctx("D01-dinero-verde-it-pl")
    r = P.seleccionar(ctx, params)
    ex = {(e["pais"], e["regla"]) for e in r["excluidos"]}
    por = {x["pais"]: x for x in r["ranking"]}
    prueba("D01 fase vigente: PL excluido por R6 e IT elegido con bandera cobertura_media", ex == {("PL", "R6")} and r["elegido_pais"] == "IT" and "cobertura_media" in por["IT"]["banderas"])
    prueba("D01: peso de creadores 0 y el ajuste de creadores es solo informativo", r["parametros"]["peso_ajuste_creadores"] == 0 and por["IT"]["ajuste_creadores_informativo"] == 5)
    prueba("D01: PL queda con bandera bajo_minimo (bandera, no exclusion: el puntaje minimo se calibro sin neto completo)", "bajo_minimo" in por["PL"]["banderas"])
    ctx2 = copy.deepcopy(ctx)
    ctx2["fase_pagos"] = P.FASE_LOCALES
    r2 = P.seleccionar(ctx2, params)
    prueba("D01 con_locales y PLN: ambos entran (PL ya no cae por R6)", not r2["excluidos"] and {x["pais"] for x in r2["ranking"] if not x["excluido_por"]} == {"IT", "PL"})
    prueba("D01: la sensibilidad informa si el elegido sigue en el top 3 en cada escenario", all("elegido_en_top3" in s for s in r["sensibilidad"]) and len(r["sensibilidad"]) >= 10)
    # D02
    c3 = cargar_ctx("D02-commonwealth-dinero")
    r3 = P.seleccionar(c3, params)
    orden = [x["pais"] for x in r3["ranking"] if not x["excluido_por"]]
    prueba("D02 dinero verde de hogar: CA y NZ antes que AU/IE; GB excluido por R9; bloques separados por locale y moneda",
           orden[:2] == ["CA", "NZ"] and ("GB", "R9") in {(e["pais"], e["regla"]) for e in r3["excluidos"]} and len(r3["bloques"]) == len(orden))
    # D03 pais sin ficha: falla cerrado con pregunta bloqueante (no inventa)
    c3b = cargar_ctx("D01-dinero-verde-it-pl")
    c3b["limites"].update({"paises_permitidos": ["DE"], "locales_permitidos": ["de-DE"]})
    c3b["fichas"] = {}
    try:
        P.seleccionar(c3b, params)
        ok3 = False
    except C.DatoFaltante as e:
        ok3 = "pregunta bloqueante" in str(e)
    prueba("D03 de-DE sin ficha: falla cerrado con pregunta bloqueante (salida 5), sin inventar", ok3)
    # D04 salud it-IT: el angulo rojo se excluye (R2), el reencuadre verde reabre el par; el tema salud no se excluye
    base = cargar_ctx("D01-dinero-verde-it-pl")
    base["fichas"] = {"IT": base["fichas"]["IT"]}
    base["limites"].update({"paises_permitidos": ["IT"], "locales_permitidos": ["it-IT"]})
    rojo = copy.deepcopy(base)
    rojo["candidato"] = {"candidato_id": "C-ROJO", "macro_nicho": "salud", "riesgo": {"P": "rojo", "C": "verde", "E": "verde", "N": "verde", "nivel": "rojo"}, "etiquetas": []}
    verde = copy.deepcopy(base)
    verde["candidato"] = {"candidato_id": "C-REENCUADRE", "macro_nicho": "salud", "riesgo": {"P": "verde", "C": "verde", "E": "verde", "N": "verde", "nivel": "verde"}, "etiquetas": []}
    ex_r, ex_v = P.excluir(rojo, params, HOY), P.excluir(verde, params, HOY)
    prueba("D04 salud it-IT: el angulo rojo cae por R2 y el reencuadre verde reabre el par (se excluye el angulo, no el tema)",
           [e["regla"] for e in ex_r["excluidos"]] == ["R2"] and not ex_v["excluidos"])
    # D05 dinero amarillo-a en UK/AU: R3 por promesa de ingresos / no-hogar; AU hogar pasa con gate H de exposicion
    d5 = cargar_ctx("D02-commonwealth-dinero")
    d5["fichas"] = {"GB": d5["fichas"]["GB"], "AU": d5["fichas"]["AU"]}
    d5["limites"].update({"paises_permitidos": ["GB", "AU"], "locales_permitidos": ["en-GB", "en-AU"]})
    amar = {"P": "amarillo", "C": "verde", "E": "verde", "N": "verde", "nivel": "amarillo"}
    d5["candidato"] = {"candidato_id": "C-AMARILLO-A", "macro_nicho": "dinero", "riesgo": amar, "etiquetas": ["ingresos"]}
    e5 = P.excluir(d5, params, HOY)
    d5b = copy.deepcopy(d5)
    d5b["candidato"]["etiquetas"] = ["producto_hogar"]
    e5b = P.excluir(d5b, params, HOY)
    prueba("D05 dinero amarillo-a: GB con 'ingresos' cae por R3 (J05); AU solo-hogar pasa con bandera gate_h_exposicion",
           ("GB", "R3") in {(x["pais"], x["regla"]) for x in e5["excluidos"]} and not any(x["pais"] == "AU" and x["regla"] == "R3" for x in e5b["excluidos"])
           and "gate_h_exposicion" in e5b["banderas"]["AU/en-AU"])
    # D08 Managed Payments = si (relaciones, pl-PL): PL cae por R6 y R8 no aplica
    d8 = cargar_ctx("D01-dinero-verde-it-pl")
    d8["fichas"] = {"PL": d8["fichas"]["PL"]}
    d8["limites"].update({"paises_permitidos": ["PL"], "locales_permitidos": ["pl-PL"]})
    d8["candidato"] = {"candidato_id": "C-REL", "macro_nicho": "relaciones", "riesgo": {"P": "verde", "C": "verde", "E": "verde", "N": "verde", "nivel": "verde"}, "etiquetas": []}
    d8["decision_managed_payments"] = "si"
    e8 = P.excluir(d8, params, HOY)
    prueba("D08 Managed Payments=si: PL cae por R6 (≈17 %) y R8 no aplica (el MoR presenta el impuesto)",
           [x["regla"] for x in e8["excluidos"]] == ["R6"] and "requiere_firma_exposicion_fiscal" not in e8["banderas"]["PL/pl-PL"])
    # D10 en-GB dinero verde: R8 con diferido si el dueño no firmo GB; J05 con ingresos
    d10 = cargar_ctx("D02-commonwealth-dinero")
    d10["fichas"] = {"GB": d10["fichas"]["GB"]}
    d10["limites"].update({"paises_permitidos": ["GB"], "locales_permitidos": ["en-GB"]})
    d10["exposicion_fiscal_firmada_paises"] = []
    e10 = P.excluir(d10, params, HOY)
    prueba("D10 en-GB: registro HMRC desde la primera venta => R8 con diferido sin firma que cubra GB", ("GB", "R8") in {(x["pais"], x["regla"]) for x in e10["excluidos"]})
    # 4) vigencia / trazabilidad
    f_it = copy.deepcopy(fichas["IT"])
    f_it["meta"]["recargo_meta_bp"]["fecha_lectura"] = "2026-09-20"  # 47 dias > 30
    ev = V.evaluar_ficha(f_it, HOY, params)
    prueba("tarifa de 47 dias bloquea (R10); el CPM del 2026-07-27 (102 dias) NO bloquea y sale como MAYOR",
           any(b["regla"] == "R10" for b in ev["bloqueantes"]) and ev["cpm_vencido"] and not any("cpm" in str(b.get("categoria")) for b in ev["bloqueantes"]))
    f2 = copy.deepcopy(fichas["IT"])
    del f2["fiscal"]["tasa_bp"]["fuente_url"]
    prueba("hoja sin fuente_url bloquea (MQ-02)", any(b["regla"] == "MQ-02" for b in V.evaluar_ficha(f2, HOY, params)["bloqueantes"]))
    # 5) lint
    reglas = {"locale": "pl-PL", "decimal": ",", "alfabetos_permitidos": [], "prohibidos": [{"termino": "gwarantujemy"}],
              "plurales": [{"forma_1": "godzina", "forma_2_4": "godziny", "forma_5_mas": "godzin"}]}
    H = LL.lint([("/", "Cena 49.00 zł, 9,90 €. 5 godziny. Gwarantujemy.")], reglas, "PLN", [])
    checks = {h["check"] for h in H}
    prueba("lint_locale detecta prohibido, moneda ajena, decimal, plural", {"prohibidos", "moneda", "formato_moneda", "plurales"} <= checks)
    # 6) L1 sobre plantillas
    m, s = C.cargar_json(os.path.join(SK, "templates", "mercado.json")), C.cargar_json(os.path.join(SK, "templates", "mercado.seleccion.json"))
    k = L.chequear(m, s, None, limites, params, fichas, HOY, ["2026-12-10", "2026-12-20"], C.cargar_json(os.path.join(SK, "templates", "emparejamiento.json")), "borrador")
    b, mm = k.resumen()
    prueba("plantillas mercado.json + mercado.seleccion.json: 0 bloqueantes y 0 mayores en chequeos L1 (modo borrador)", b == 0 and mm == 0, json.dumps([i for i in k.items if i["resultado"] == "fail"], ensure_ascii=False))
    # 6b) MQ-03M (SC-17): CPM vencido = etiqueta [SUPUESTO] + bandera cpm_vencido; mult central 1,2; el 1,5 es sensibilidad y no excluye
    emp = C.cargar_json(os.path.join(SK, "templates", "emparejamiento.json"))

    def mq03m(mm_, ss_):
        kk = L.chequear(mm_, ss_, None, limites, params, fichas, HOY, ["2026-12-10", "2026-12-20"], emp, "borrador")
        return [i["resultado"] for i in kk.items if i["check_id"] == "MQ-03M"]
    m_sin = copy.deepcopy(m)
    m_sin["cpm_fuente"] = m_sin["cpm_fuente"].replace("[SUPUESTO]", "")
    s_sin = copy.deepcopy(s)
    s_sin["parametros_usados"]["cpm_vencido"] = False
    for rr in s_sin["ranking"]:
        rr["banderas"] = [b_ for b_ in rr.get("banderas", []) if b_ != "cpm_vencido"]
    prueba("MQ-03M: CPM vencido con [SUPUESTO] y bandera cpm_vencido pasa; sin la etiqueta o sin la bandera es MAYOR",
           mq03m(m, s) == ["pass"] and mq03m(m_sin, s) == ["fail"] and mq03m(m, s_sin) == ["fail"], f"{mq03m(m, s)} {mq03m(m_sin, s)} {mq03m(m, s_sin)}")
    esc = {e["escenario"]: e for e in r["sensibilidad"]}
    prueba("mult_cpm: central 1,2 sin clave mult_cpm_si_cpm_vencido_min; el 1,5 (estres) solo sensibilidad: IT sigue en el top 3 con cpm_x1_5 y el CPM vencido no excluye",
           "mult_cpm_si_cpm_vencido_min" not in params and params["mult_cpm"] == {"central": "1.2", "estres": "1.5"} and r["parametros"]["mult_cpm_efectivo"] == "1.2"
           and r["parametros"]["cpm_vencido"] is True and esc["cpm_x1_5"]["elegido_en_top3"] and not any(e["regla"] == "R10" for e in r["excluidos"]))
    # 6c) niveles en minusculas (contratos/comunes#nivel_lanzable; limites.nivel_max_lanzable): lo que dice el contrato y nada mas
    enum_c = C.cargar_json(os.path.join(C.RAIZ, "contratos", "comunes.schema.json"))["$defs"]["nivel_lanzable"]["enum"]
    sub_a = P.subnivel_candidato({"nivel": "amarillo", "P": "amarillo", "C": "verde", "E": "verde", "N": "verde"})
    sub_b = P.subnivel_candidato({"nivel": "amarillo", "P": "amarillo", "C": "amarillo", "E": "verde", "N": "verde"})
    sub_c = P.subnivel_candidato({"nivel": "amarillo", "subnivel": "B", "P": "amarillo", "C": "verde", "E": "verde", "N": "verde"})
    base_v = cargar_ctx("D01-dinero-verde-it-pl")
    base_v["candidato"] = dict(base_v["candidato"], riesgo={"P": "amarillo", "C": "verde", "E": "verde", "N": "verde", "nivel": "amarillo"})
    sin_tope = copy.deepcopy(base_v)
    sin_tope["limites"].pop("nivel_max_lanzable")
    cap = copy.deepcopy(base_v)
    cap["limites"]["nivel_max_lanzable"] = {"dinero": "amarillo-" + "A"}  # forma antigua en mayuscula: el contrato solo admite minusculas
    try:
        P.excluir(cap, params, HOY)
        cap_rechazado = False
    except C.DatoFaltante:
        cap_rechazado = True
    prueba("niveles en minusculas = enum de comunes#nivel_lanzable; subnivel A/B; nivel_max_lanzable ausente = SOLO VERDE; la forma antigua con mayuscula se rechaza (sale 5)",
           C.NIVELES[:3] == enum_c and (sub_a, sub_b, sub_c) == ("amarillo-a", "amarillo-b", "amarillo-b")
           and "R2" in {x["regla"] for x in P.excluir(sin_tope, params, HOY)["excluidos"]}
           and "R2" not in {x["regla"] for x in P.excluir(base_v, params, HOY)["excluidos"]} and cap_rechazado,
           f"{enum_c} {sub_a} {sub_b} {sub_c} {cap_rechazado}")
    # 7) sin prior: ninguna regla de decision nombra un pais
    mal = []
    for n in ("puntaje.py", "vigencia.py", "lint_locale.py", "_comun.py"):
        for i, linea in enumerate(open(os.path.join(C.AQUI, n), encoding="utf-8"), 1):
            for lit in re.findall(r"[\"']([A-Z]{2})[\"']", linea):
                if lit not in {"PA"} and not linea.lstrip().startswith("#") and "esperado = {" not in linea:
                    mal.append(f"{n}:{i} {lit}")
    prueba("ningun script de decision contiene un codigo de pais literal (sin prior de mercado)", not mal, "; ".join(mal))
    return k


def correr_sembrados(params, limites):
    base_m = C.cargar_json(os.path.join(SK, "templates", "mercado.json"))
    base_s = C.cargar_json(os.path.join(SK, "templates", "mercado.seleccion.json"))
    base_e = C.cargar_json(os.path.join(SK, "templates", "emparejamiento.json"))
    base_f = cargar_fichas_fixture()
    out = []
    for n in sorted(os.listdir(SEM)):
        if not n.endswith(".json"):
            continue
        d = C.cargar_json(os.path.join(SEM, n))
        det = d["deteccion"]
        if det["via"] == "L2":
            out.append({"id": d["id"], "star": d.get("bloqueante_star", False), "medible_aqui": False, "detectado": None, "nota": "lo mide el QA (L2) en una corrida"})
            continue
        m, s, e = base_m, base_s, base_e
        fichas = copy.deepcopy(base_f)
        ctx = None
        for mut in d.get("mutaciones", []):
            t = mut["archivo"]
            if t == "mercado":
                m = aplicar(m, mut["ops"])
            elif t == "seleccion":
                s = aplicar(s, mut["ops"])
            elif t == "emparejamiento":
                e = aplicar(e, mut["ops"])
            elif t.startswith("ficha:"):
                fichas[t[6:]] = aplicar(fichas[t[6:]], mut["ops"])
            elif t.startswith("contexto:"):
                ctx = aplicar(ctx or cargar_ctx(t[9:]), mut["ops"])
        ok = False
        if det["via"] == "l1":
            lim = copy.deepcopy(limites)
            k = L.chequear(m, s, None, lim, params, fichas, HOY, det.get("ventana_test"), e, det.get("modo", "borrador"))
            res = {i["check_id"]: i["resultado"] for i in k.items}
            ok = res.get(det["check"]) == "fail"
        elif det["via"] == "excluir":
            if "fichas_extra" in det:
                ctx["fichas"].update(det["fichas_extra"])
            if "fichas_mutadas" in det:
                for iso, ops in det["fichas_mutadas"].items():
                    ctx["fichas"][iso] = aplicar(ctx["fichas"][iso], ops)
            ctx["r_b"] = ctx.get("r_b")
            r = P.excluir(ctx, params, HOY)
            ok = any(x["regla"] == det["regla"] and (det.get("pais") in (None, x["pais"])) for x in r["excluidos"])
        elif det["via"] == "vigencia":
            ok = any(b.get("regla") == det["regla"] for b in V.evaluar_ficha(fichas[det["pais"]], HOY, params)["bloqueantes"])
        out.append({"id": d["id"], "star": d.get("bloqueante_star", False), "medible_aqui": True, "detectado": ok, "via": det["via"], "esperado": det.get("check") or det.get("regla")})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-sembrados", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        params, _ = C.cargar_parametros()
        limites = C.cargar_datos(LIMITES_SIM)
        if not a.solo_sembrados:
            correr_pruebas(params, limites)
        sem = correr_sembrados(params, limites)
    except C.DatoFaltante as e:
        C.imprimir_error(e)
        return C.SALIDA_FALTA_DATO
    medibles = [x for x in sem if x["medible_aqui"]]
    detectados = [x for x in medibles if x["detectado"]]
    star = [x for x in medibles if x["star"]]
    star_det = [x for x in star if x["detectado"]]
    fallos = [r for r in RES if not r["ok"]]
    resumen = {"pruebas": len(RES), "pruebas_falladas": [f["prueba"] for f in fallos],
               "sembrados_medibles_por_script": len(medibles), "sembrados_detectados": len(detectados),
               "bloqueantes_star_medibles": len(star), "bloqueantes_star_detectados": len(star_det),
               "sembrados_no_detectados": [x["id"] for x in medibles if not x["detectado"]],
               "sembrados_solo_L2": [x["id"] for x in sem if not x["medible_aqui"]]}
    if a.json:
        C.escribir_json({"resumen": resumen, "pruebas": RES, "sembrados": sem})
    else:
        for r in RES:
            print(("OK   " if r["ok"] else "FALLA"), r["prueba"], ("" if r["ok"] else "-> " + r["detalle"][:300]))
        for x in sem:
            print(("OK   " if x["detectado"] else ("L2   " if not x["medible_aqui"] else "FALLA")), "sembrado", x["id"], x.get("via", "L2"), x.get("esperado", ""))
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return C.SALIDA_OK if not fallos and len(detectados) == len(medibles) else C.SALIDA_VALIDACION


if __name__ == "__main__":
    sys.exit(main())
