"""Métricas del embudo que no mirábamos (pedido del dueño del 2026-11-13, tras comparar con Santiago Bilbao).

Ninguna toca presupuesto ni campañas: detectan, avisan y le dicen a la renovación qué pieza cambiar. Los números salen de
`ofertas/_funnels/reglas.json` → `metricas`.

Tres modos, cada uno en la tarea que ya corre:

  vuelta     (vigilancia de cada hora) por oferta con campaña activa:
             AVISO_CARGA   ≥ 50 clics y menos del 60 % llega a ver la página. Antes de avisar se prueba la landing: si
                           está caída o tarda más de 3 s, el problema es la página (urgente); si carga bien, es el píxel
                           (PageView) y el aviso es normal. En fase de test el corte sigue igual, pero el test queda
                           marcado como contaminado (`aprendizaje.test_contaminado`) y la oferta puede volver a lanzarse.
             AVISO_CPM     el CPM de hoy y el de ayer duplican el promedio de los 7 días anteriores (con ≥ 1.000
                           impresiones hoy y ≥ 3 días previos). Con una sola cuenta, solo se avisa; cuando exista la
                           segunda (`cuentas.segunda_cuenta_lista`), propone duplicar la campaña ahí.
             Además calcula costo e ingreso por visita y las tasas página→pago y pago→compra para el panel.

  periodos   (revisión diaria) compara los últimos 3 días con los 3 anteriores:
             lado          de qué lado está el problema cuando el ROAS se mueve: «anuncios» si el costo por visita subió
                           ≥ 20 %, «pagina_y_cobro» si el ingreso por visita bajó ≥ 20 %, «ambos», o «estable».
                           (Ingreso por visita ÷ costo por visita es el ROAS: no es una regla nueva, dice dónde arreglar.)
             SOSPECHA_CLON con ≥ 20 pagos iniciados en cada período, compras ÷ pagos iniciados cayó a la mitad o menos.
                           Primero se prueba el checkout (`probar_funnel.py`): un medio de pago caído da lo mismo. Si el
                           checkout anda, aviso y la próxima renovación trae conceptos nuevos en vez de iteraciones.
             (Se llama con los 3 días; la comparación de 7 contra 7 se arma igual pasando esos totales.)

  anuncios   (renovación diaria) diagnóstico de cada anuncio con ≥ 1.000 impresiones:
             NO_TOCAR        CTR de enlace ≥ 1,5 %: no se modifica; se itera alrededor.
             REHACER_CUERPO  retención < 10 % (reproducciones completas ÷ reproducciones): se pierde a la gente en el medio.
             REHACER_CTA     retención ≥ 10 % y CTR < 1,5 %: lo miran pero no hacen clic.
             REHACER_IMAGEN  anuncio sin video con CTR < 1,5 %.
             POCA_MUESTRA    menos de 1.000 impresiones.
             Desde el 15-nov la renovación de la CBO madre ya no itera sobre el ganador (10 creativos 100 % nuevos); el
             diagnóstico se sigue registrando y orienta las iteraciones donde todavía se hacen (réplica, pocket).

Uso:
  python3 .claude/skills/escalar-oferta/scripts/metricas_embudo.py vuelta   --lectura <json> [--sin-http] [--registrar]
  python3 .claude/skills/escalar-oferta/scripts/metricas_embudo.py periodos --lectura <json> [--registrar]
  python3 .claude/skills/escalar-oferta/scripts/metricas_embudo.py anuncios --lectura <json> [--registrar]

lectura vuelta:   {"tests": {"<oferta>": {"fase": "test"|"post", "url": "https://…", "gasto_usd": 30, "impresiones": 4000,
                   "clics_enlace": 80, "vistas_pagina": 60, "checkouts": 6, "compras": 2, "ingreso_usd": 50,
                   "cpm_dias": [cpm_hoy, cpm_ayer, cpm_anteayer, …]}}}            (hasta 9 días, hoy primero)
lectura periodos: {"tests": {"<oferta>": {"actual": {gasto_usd, visitas, ingreso_usd, checkouts, compras},
                                          "anterior": {…lo mismo…}}}}
lectura anuncios: {"oferta": "<oferta>", "anuncios": [{"id": "…", "nombre": "…", "impresiones": 3000, "reproducciones": 2000,
                   "completas": 150, "clics_enlace": 30, "compras": 1, "gasto_usd": 12}]}
Estado para el panel: ofertas/_funnels/embudo.json (último resultado de cada modo por oferta).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
ESTADO = RAIZ / "ofertas" / "_funnels" / "embudo.json"

CARGA_MIN = valor("metricas.carga_min_pct", 60) / 100
CARGA_CLICS_MIN = valor("metricas.carga_clics_min", 50)
PAGINA_LENTA_MS = valor("metricas.pagina_lenta_ms", 3000)
CPM_VECES = valor("metricas.cpm_veces", 2.0)
CPM_DIAS = valor("metricas.cpm_dias_seguidos", 2)
CPM_IMP_MIN = valor("metricas.cpm_impresiones_min", 1000)
CPM_PREVIOS_MIN = valor("metricas.cpm_dias_previos_min", 3)
LADO_CAMBIO = valor("metricas.lado_cambio_pct", 20) / 100
LADO_VISITAS_MIN = valor("metricas.lado_visitas_min", 100)
CLON_CAIDA = valor("metricas.clon_caida", 0.5)
CLON_CHECKOUTS_MIN = valor("metricas.clon_checkouts_min", 20)
ANUNCIO_IMP_MIN = valor("metricas.anuncio_impresiones_min", 1000)
RETENCION_MIN = valor("metricas.retencion_min_pct", 10) / 100
CTR_NO_TOCAR = valor("metricas.ctr_no_tocar_pct", 1.5) / 100
SEGUNDA_CUENTA = valor("cuentas.segunda_cuenta_lista", False)


def _f(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _div(a: float, b: float) -> float | None:
    return a / b if b else None


def _r(x: float | None, n: int = 2) -> float | None:
    return round(x, n) if x is not None else None


# ---------------------------------------------------------------- vuelta (cada hora)

def cpm_anormal(cpm_dias: list) -> dict:
    dias = [_f(x) for x in (cpm_dias or [])]
    previos = [x for x in dias[CPM_DIAS:CPM_DIAS + 7] if x > 0]
    if len(dias) < CPM_DIAS or len(previos) < CPM_PREVIOS_MIN:
        return {"estado": "POCA_MUESTRA"}
    prom = sum(previos) / len(previos)
    altos = all(x >= CPM_VECES * prom for x in dias[:CPM_DIAS])
    return {"estado": "ANORMAL" if altos else "OK", "cpm_hoy": _r(dias[0]), "promedio_7d": _r(prom)}


def evaluar_vuelta(nombre: str, t: dict, probar: Callable[[str], dict] | None) -> dict:
    gasto, imp, clics, vis = _f(t.get("gasto_usd")), _f(t.get("impresiones")), _f(t.get("clics_enlace")), _f(t.get("vistas_pagina"))
    chk, comp, ing = _f(t.get("checkouts")), _f(t.get("compras")), _f(t.get("ingreso_usd"))
    carga = _div(vis, clics)
    out = {"oferta": nombre, "fase": t.get("fase"), "carga_pct": _r(100 * carga, 1) if carga is not None else None,
           "costo_por_visita": _r(_div(gasto, vis)), "ingreso_por_visita": _r(_div(ing, vis)),
           "pagina_a_pago_pct": _r(100 * _div(chk, vis), 1) if vis else None,
           "pago_a_compra_pct": _r(100 * _div(comp, chk), 1) if chk else None, "acciones": []}
    if carga is not None and clics >= CARGA_CLICS_MIN and carga < CARGA_MIN:
        prueba = probar(t["url"]) if probar and t.get("url") else None
        out["pagina_ms"] = prueba.get("ms") if prueba else None
        pagina_mal = prueba is not None and (not prueba.get("ok") or _f(prueba.get("ms")) > PAGINA_LENTA_MS)
        if prueba is None:
            causa, urgente = "no se pudo probar la página desde aquí: revisar a mano la landing y el píxel", True
        elif pagina_mal:
            causa, urgente = (f"la página {'no responde' if not prueba.get('ok') else 'tarda ' + str(round(_f(prueba.get('ms')) / 1000, 1)) + ' s'}: "
                              "se paga cada clic que no la ve"), True
        else:
            causa, urgente = f"la página carga bien ({round(_f(prueba.get('ms')) / 1000, 1)} s): revisar el PageView del píxel", False
        a = {"accion": "AVISO_CARGA", "urgente": urgente,
             "mensaje": f"{nombre}: solo {round(100 * carga)} % de los clics llega a ver la página ({int(vis)} de {int(clics)}); {causa}."}
        if t.get("fase") == "test":
            a["test_contaminado"] = True
            a["mensaje"] += " El corte del test sigue igual; el test queda marcado como contaminado."
        out["acciones"].append(a)
    if imp >= CPM_IMP_MIN:
        c = cpm_anormal(t.get("cpm_dias") or [])
        out["cpm"] = c
        if c["estado"] == "ANORMAL":
            donde = ("duplicar la campaña en la segunda cuenta y comparar" if SEGUNDA_CUENTA
                     else "con una sola cuenta no hay dónde probarla: queda como dato para la segunda cuenta")
            out["acciones"].append({"accion": "AVISO_CPM", "urgente": False,
                                    "mensaje": f"{nombre}: CPM {c['cpm_hoy']} contra {c['promedio_7d']} de promedio ({CPM_DIAS} días seguidos al doble o más); {donde}."})
    return out


# ---------------------------------------------------------------- periodos (revisión diaria)

def evaluar_periodos(nombre: str, t: dict) -> dict:
    a, b = t.get("actual") or {}, t.get("anterior") or {}
    va, vb = _f(a.get("visitas")), _f(b.get("visitas"))
    cpv_a, cpv_b = _div(_f(a.get("gasto_usd")), va), _div(_f(b.get("gasto_usd")), vb)
    rpv_a, rpv_b = _div(_f(a.get("ingreso_usd")), va), _div(_f(b.get("ingreso_usd")), vb)
    out = {"oferta": nombre, "costo_por_visita": _r(cpv_a), "costo_por_visita_antes": _r(cpv_b),
           "ingreso_por_visita": _r(rpv_a), "ingreso_por_visita_antes": _r(rpv_b), "acciones": []}
    if min(va, vb) < LADO_VISITAS_MIN or not cpv_b or rpv_b is None:
        out["lado"] = "poca_muestra"
    else:
        sube_costo = cpv_a is not None and cpv_a >= (1 + LADO_CAMBIO) * cpv_b
        baja_ingreso = rpv_b > 0 and rpv_a is not None and rpv_a <= (1 - LADO_CAMBIO) * rpv_b
        out["lado"] = "ambos" if sube_costo and baja_ingreso else "anuncios" if sube_costo else "pagina_y_cobro" if baja_ingreso else "estable"
        out["cambio_costo_pct"] = _r(100 * (cpv_a / cpv_b - 1), 0) if cpv_a is not None else None
        out["cambio_ingreso_pct"] = _r(100 * (rpv_a / rpv_b - 1), 0) if rpv_b and rpv_a is not None else None
    ca, cb = _f(a.get("checkouts")), _f(b.get("checkouts"))
    if min(ca, cb) < CLON_CHECKOUTS_MIN:
        out["clon"] = "poca_muestra"
    else:
        ta, tb = _f(a.get("compras")) / ca, _f(b.get("compras")) / cb
        out["pago_a_compra_pct"], out["pago_a_compra_antes_pct"] = _r(100 * ta, 1), _r(100 * tb, 1)
        if tb > 0 and ta <= CLON_CAIDA * tb:
            out["clon"] = "sospecha"
            out["acciones"].append({"accion": "SOSPECHA_CLON", "urgente": False, "primero": "probar el checkout (probar_funnel.py)",
                                    "mensaje": f"{nombre}: del pago a la compra cayó de {round(100 * tb)} % a {round(100 * ta)} %. "
                                               "Si el checkout anda, puede ser un clon: la próxima renovación trae conceptos nuevos."})
        else:
            out["clon"] = "ok"
    return out


# ---------------------------------------------------------------- anuncios (renovación diaria)

def diagnosticar_anuncio(a: dict) -> dict:
    imp, rep, comp_v, clics = _f(a.get("impresiones")), _f(a.get("reproducciones")), _f(a.get("completas")), _f(a.get("clics_enlace"))
    ctr, ret = _div(clics, imp), _div(comp_v, rep)
    d = {"id": a.get("id"), "nombre": a.get("nombre"), "impresiones": int(imp), "ctr_pct": _r(100 * ctr) if ctr is not None else None,
         "retencion_pct": _r(100 * ret, 1) if ret is not None else None, "compras": int(_f(a.get("compras")))}
    if imp < ANUNCIO_IMP_MIN:
        d["accion"], d["porque"] = "POCA_MUESTRA", f"{int(imp)} impresiones: hacen falta {ANUNCIO_IMP_MIN}"
    elif ctr is not None and ctr >= CTR_NO_TOCAR:
        d["accion"], d["porque"] = "NO_TOCAR", f"CTR {100 * ctr:.2f} %: funciona; se itera alrededor sin modificarlo"
    elif ret is None:
        d["accion"], d["porque"] = "REHACER_IMAGEN", f"sin video y CTR {100 * (ctr or 0):.2f} %: otra imagen o gancho visual"
    elif ret < RETENCION_MIN:
        d["accion"], d["porque"] = "REHACER_CUERPO", f"solo {100 * ret:.1f} % lo ve entero: se pierde a la gente en el medio"
    else:
        d["accion"], d["porque"] = "REHACER_CTA", f"{100 * ret:.1f} % lo ve entero pero el CTR es {100 * (ctr or 0):.2f} %: cambiar el llamado"
    return d


def evaluar_anuncios(lectura: dict) -> dict:
    ds = [diagnosticar_anuncio(a) for a in lectura.get("anuncios") or []]
    cuenta: dict[str, int] = {}
    for d in ds:
        cuenta[d["accion"]] = cuenta.get(d["accion"], 0) + 1
    return {"oferta": lectura.get("oferta"), "anuncios": ds, "resumen": cuenta,
            "piezas": ["formato", "guion", "gancho", "cuerpo", "cta", "avatar", "edicion"],
            "regla": "cada iteración cambia UNA pieza y la anota en anuncios.json → pieza_cambiada"}


# ---------------------------------------------------------------- estado y CLI

def guardar(modo: str, resultados: list[dict], ahora: str) -> None:
    try:
        est = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        est = {}
    for r in resultados:
        nombre = r.get("oferta")
        if nombre:
            est.setdefault(nombre, {})[modo] = {**{k: v for k, v in r.items() if k != "oferta"}, "cuando": ahora}
    ESTADO.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["vuelta", "periodos", "anuncios"])
    ap.add_argument("--lectura", required=True)
    ap.add_argument("--sin-http", action="store_true")
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args(argv)
    lectura = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
    ahora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    if a.modo == "vuelta":
        probar = None
        if not a.sin_http:
            from salud import probar_url
            probar = probar_url
        res = [evaluar_vuelta(n, t, probar) for n, t in (lectura.get("tests") or {}).items()]
    elif a.modo == "periodos":
        res = [evaluar_periodos(n, t) for n, t in (lectura.get("tests") or {}).items()]
    else:
        res = [evaluar_anuncios(lectura)]
    if a.registrar:
        guardar(a.modo, res, ahora)
    json.dump({"modo": a.modo, "ahora": ahora, "resultados": res,
               "acciones": [x for r in res for x in r.get("acciones", [])]}, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
