#!/usr/bin/env python3
"""Regla R4b «el día 1 no se repite» (firmada por el dueño el 2026-11-14, a partir de Oferta B).

La R4 mide los últimos 3 días, y si el día 1 del test fue bueno tapa los días malos que siguen. Oferta B
(MX): día 1 ROAS 1,52 con 6 ventas; días 2 y 3 ROAS 0,45 con 2 ventas cada uno. R4 daba CPA 1,31 veces lo que deja cada
venta y no cortaba; sin el día 1 daba 2,1 veces. El dueño la apagó a mano y pidió la regla: «primer día ROAS 1.7, luego
renovamos con backend y nunca más ROAS positivo… no tiene más sentido que apagarla». Eligió 2 días (14-nov: «me parece
bien con dos días»), contra la alternativa más prudente de 3.

Se APAGA cuando se cumplen las tres cosas:
  1. Ya tuvo su intento de rescate: backend activo y al menos `requiere_rondas_renovacion` ronda(s) de renovación con
     24 h de entrega desde su inicio.
  2. Los días después del test (desde las 00:00 del mercado siguientes al inicio) pierden: como mínimo `dias_minimos`
     días; un día cerrado cuenta siempre, y el día en curso solo si ya gastó el `ultimo_dia_gasto_min_pct` % del
     presupuesto diario. Juntos: gasto ≥ `veces_lo_que_deja` × lo que deja cada venta × máx(1, ventas).
  3. Ningún conjunto de renovación está prendiendo: ninguno lleva ≥ `conjunto_nuevo_compras_rescata` compras con ROAS
     de Meta ≥ `conjunto_nuevo_roas_rescata` desde su inicio. Si alguno sí, se espera y decide la R4 de siempre.

«Lo que deja cada venta» = neto total de la oferta en USD (upsells, bump y rebajas incluidos, después de comisiones) ÷
compradores (las ventas de upsell/bump/rebaja no cuentan como compradores). Es el mismo número que usa la R4.

Decisiones: APAGAR · ESPERAR_RESCATE (pierde, pero un conjunto nuevo vende) · SIGUE (no pierde tanto) ·
FALTAN_DIAS · FALTA_INTENTO (sin backend activo o sin ronda de renovación con 24 h) · SIN_DATOS.
Este script solo decide: no toca Meta. Lo corre la vigilancia de cada hora (paso 7b de 04-vigilancia.md).

Uso:
  python3 corte_post_test.py --lectura <lectura.json> [--registrar]
  python3 corte_post_test.py --desde-libro "<oferta>" [--ahora ISO] [--presupuesto USD]   (arma la lectura con el libro;
        el gasto por día sale de historial_diario, así que conviene correr antes historial_meta.py)
  python3 corte_post_test.py --probar                                                     (casos de prueba)
lectura.json:
  {"leido": "2026-11-14T18:40-03:00", "ofertas": [{
     "oferta": "Oferta B", "campana": "120…", "presupuesto_usd": 50,
     "fin_test": "2026-11-13T00:00:00-06:00",
     "lo_que_deja_usd": 12.24,
     "backend": {"estado": "activo", "desde": "2026-11-13"},
     "renovaciones": [{"conjunto_id": "120…", "inicio": "2026-11-13T00:00:00-06:00", "gasto_usd": 18.06, "compras": 0, "valor_usd": 0}],
     "dias": [{"fecha": "2026-11-13", "gasto_usd": 63.38, "ventas": 2, "neto_usd": 26.1, "cerrado": true},
              {"fecha": "2026-11-14", "gasto_usd": 40.17, "ventas": 2, "neto_usd": 16.7, "cerrado": false}]}]}
  `ventas` = compradores del día en la tienda (sin upsells); `dias` solo los posteriores al test (los anteriores se ignoran).
Salida: JSON con una decisión por oferta. Con --registrar se agrega a ofertas/_funnels/vigilancia.jsonl.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
REGISTRO = RAIZ / "ofertas" / "_funnels" / "vigilancia.jsonl"
TIPOS_EXTRA = ("upsell", "downsell", "bump", "rebaja")

def _c(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


R = valor("post_test.caida_tras_dia1", {})
DIAS_MIN = int(R.get("dias_minimos", 2))
VECES = float(R.get("veces_lo_que_deja", 1.5))
ULTIMO_DIA_PCT = float(R.get("ultimo_dia_gasto_min_pct", 70))
REQUIERE_BACKEND = bool(R.get("requiere_backend_activo", True))
RONDAS_MIN = int(R.get("requiere_rondas_renovacion", 1))
RESCATE_ROAS = float(R.get("conjunto_nuevo_roas_rescata", 1.0))
RESCATE_COMPRAS = int(R.get("conjunto_nuevo_compras_rescata", 2))
REGLA = (f"R4b «el día 1 no se repite» (dueño, 14-nov): con backend activo y ≥ {RONDAS_MIN} ronda de renovación con 24 h, "
         f"si los días después del test (≥ {DIAS_MIN}; el día en curso desde el {ULTIMO_DIA_PCT:.0f} % del presupuesto) suman "
         f"CPA ≥ {_c(VECES)} × lo que deja cada venta y ningún conjunto nuevo vende con ROAS ≥ {_c(RESCATE_ROAS)} → apagar")


def _fecha(x) -> dt.datetime | None:
    if not isinstance(x, str) or not x:
        return None
    try:
        d = dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = dt.datetime.combine(dt.date.fromisoformat(x[:10]), dt.time(0), tzinfo=dt.timezone.utc)
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _n(x) -> float:
    return float(x) if isinstance(x, (int, float)) else 0.0


def _usd(x: float) -> str:
    return f"US$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def decidir(o: dict, ahora: dt.datetime) -> dict:
    """Decisión de una oferta. Pura (probada con --probar)."""
    out = {"oferta": o.get("oferta"), "campana": o.get("campana")}
    deja = o.get("lo_que_deja_usd")
    fin_test = _fecha(o.get("fin_test"))
    if not isinstance(deja, (int, float)) or deja <= 0 or fin_test is None:
        return {**out, "decision": "SIN_DATOS", "porque": "falta lo que deja cada venta o el fin del test"}

    # 1. intento de rescate
    b = o.get("backend") or {}
    backend_ok = str(b.get("estado", "")).lower() in ("activo", "activa")
    rondas = [r for r in (o.get("renovaciones") or []) if (_fecha(r.get("inicio")) or ahora) <= ahora - dt.timedelta(hours=24)]
    if (REQUIERE_BACKEND and not backend_ok) or len(rondas) < RONDAS_MIN:
        falta = []
        if REQUIERE_BACKEND and not backend_ok:
            falta.append("backend activo")
        if len(rondas) < RONDAS_MIN:
            falta.append(f"{RONDAS_MIN} ronda de renovación con 24 h de entrega")
        return {**out, "decision": "FALTA_INTENTO", "porque": "todavía no tuvo su intento de rescate: falta " + " y ".join(falta) + ". Decide la R4."}

    # 2. días después del test
    presupuesto = _n(o.get("presupuesto_usd"))
    contados, fuera = [], []
    for d in o.get("dias") or []:
        try:
            f = dt.date.fromisoformat(str(d.get("fecha"))[:10])
        except ValueError:
            continue
        if f < fin_test.date():
            continue
        if d.get("cerrado") or (presupuesto > 0 and _n(d.get("gasto_usd")) >= presupuesto * ULTIMO_DIA_PCT / 100):
            contados.append(d)
        else:
            fuera.append(str(f))
    gasto = sum(_n(d.get("gasto_usd")) for d in contados)
    ventas = int(sum(_n(d.get("ventas")) for d in contados))
    neto = sum(_n(d.get("neto_usd")) for d in contados)
    tope = VECES * deja
    cpa = gasto / ventas if ventas else None
    datos = {"dias_contados": [str(d.get("fecha"))[:10] for d in contados], "dia_sin_contar": fuera or None,
             "gasto_usd": round(gasto, 2), "ventas": ventas, "neto_usd": round(neto, 2),
             "roas_neto": round(neto / gasto, 2) if gasto else None, "cpa_usd": round(cpa, 2) if cpa else None,
             "lo_que_deja_usd": round(deja, 2), "tope_cpa_usd": round(tope, 2),
             "veces": round(cpa / deja, 2) if cpa else None}
    if len(contados) < DIAS_MIN:
        return {**out, **datos, "decision": "FALTAN_DIAS",
                "porque": f"van {len(contados)} de {DIAS_MIN} días después del test (el día en curso cuenta desde el {ULTIMO_DIA_PCT:.0f} % del presupuesto)."}
    pierde = gasto >= tope * max(1, ventas)
    txt = (f"después del test: {_usd(gasto)} por {ventas} venta{'s' if ventas != 1 else ''}"
           + (f" (CPA {_usd(cpa)}, {_c(cpa / deja)} × lo que deja, {_usd(deja)})" if cpa else f" (sin ventas; tope {_usd(tope)})"))
    if not pierde:
        return {**out, **datos, "decision": "SIGUE", "porque": txt + f": no llega a {_c(VECES)} ×. Decide la R4."}

    # 3. ¿algún conjunto nuevo prende?
    rescate = []
    for r in o.get("renovaciones") or []:
        g, c, v = _n(r.get("gasto_usd")), int(_n(r.get("compras"))), _n(r.get("valor_usd"))
        if c >= RESCATE_COMPRAS and g > 0 and v / g >= RESCATE_ROAS:
            rescate.append({"conjunto_id": r.get("conjunto_id"), "compras": c, "roas_meta": round(v / g, 2)})
    if rescate:
        return {**out, **datos, "decision": "ESPERAR_RESCATE", "rescate": rescate,
                "porque": txt + f", pero {len(rescate)} conjunto nuevo vende con ROAS ≥ {_c(RESCATE_ROAS)}: se espera y decide la R4."}
    return {**out, **datos, "decision": "APAGAR",
            "porque": txt + f" en {len(contados)} días; backend activo, {len(rondas)} ronda(s) de renovación sin conjunto que venda. Apagar la campaña."}


# ───────────────────────── lectura armada con el libro ─────────────────────────

def _lo_que_deja(libro: dict, t: dict, ahora: dt.datetime) -> float | None:
    """Valor neto por comprador del sistema (ventana 7/14 días o historia, sin cruzar el último cambio del embudo; 17-nov)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from dashboard import negocio as N  # noqa: PLC0415
    except ImportError:
        return None
    zona = N.zona_de(libro)
    tc = {k: v for k, v in (libro.get("tipos_de_cambio") or {}).items() if N._num(v) is not None}
    nombre = t.get("oferta") or t.get("nombre")
    ts = [x for x in libro.get("tests") or [] if isinstance(x, dict) and (x.get("oferta") or x.get("nombre")) == nombre]
    v = N.neto_por_comprador_ventana(ts, tc, zona, ahora.astimezone(zona).date())
    return round(v["neto_por_venta"], 2) if v else None


def lectura_del_libro(libro: dict, nombre: str, ahora: dt.datetime, presupuesto: float | None = None) -> dict:
    t = next((x for x in libro.get("tests") or [] if nombre in (x.get("nombre"), x.get("oferta"))), None)
    if t is None:
        raise SystemExit(f"no está «{nombre}» en el libro")
    tc = {k: v for k, v in (libro.get("tipos_de_cambio") or {}).items() if isinstance(v, (int, float))}
    inicio = _fecha(t.get("inicio"))
    zona = inicio.tzinfo if inicio else dt.timezone.utc
    fin_test = dt.datetime.combine(inicio.date() + dt.timedelta(days=1), dt.time(0), tzinfo=zona) if inicio else None
    hoy = ahora.astimezone(zona).date()
    neto_total, compradores, por_dia = 0.0, 0, {}
    for v in t.get("ventas") or []:
        f = tc.get(v.get("moneda"))
        if f is None:
            continue
        n = _n(v.get("neto")) * f
        neto_total += n
        dia = str(v.get("dia_cuenta") or v.get("fecha") or "")[:10]
        x = por_dia.setdefault(dia, {"ventas": 0, "neto_usd": 0.0})
        x["neto_usd"] += n
        if str(v.get("tipo") or "") not in TIPOS_EXTRA:
            compradores += 1
            x["ventas"] += 1
    gasto_dia: dict[str, float] = {}   # suma de todas las campañas del día (pocket y variaciones incluidas, 15-nov)
    for h in t.get("historial_diario") or []:
        if isinstance(h, dict):
            f = str(h.get("fecha"))[:10]
            gasto_dia[f] = gasto_dia.get(f, 0.0) + _n(h.get("gasto_usd"))
    dias = []
    for f in sorted(set(gasto_dia) | set(por_dia)):
        dias.append({"fecha": f, "gasto_usd": gasto_dia.get(f, 0.0), "ventas": por_dia.get(f, {}).get("ventas", 0),
                     "neto_usd": round(por_dia.get(f, {}).get("neto_usd", 0.0), 2), "cerrado": f < str(hoy)})
    camp = ((t.get("ficha") or {}).get("campanas") or [{}])[0]
    renov = []
    for r in t.get("renovaciones") or []:
        renov.append({"conjunto_id": r.get("conjunto_id"), "inicio": r.get("inicio"), "gasto_usd": r.get("gasto_usd", 0),
                      "compras": r.get("compras_meta", r.get("compras", 0)), "valor_usd": r.get("valor_compras_meta_usd", r.get("valor_usd", 0))})
    return {"oferta": t.get("nombre"), "campana": t.get("campana"),
            "presupuesto_usd": presupuesto if presupuesto is not None else camp.get("presupuesto_diario_usd"),
            "fin_test": fin_test.isoformat() if fin_test else None,
            "lo_que_deja_usd": _lo_que_deja(libro, t, ahora) or (round(neto_total / compradores, 2) if compradores else None),
            "backend": t.get("backend") or {}, "renovaciones": renov, "dias": dias}


# ───────────────────────── casos de prueba ─────────────────────────

def probar() -> int:
    ahora = dt.datetime.fromisoformat("2026-11-14T18:40-03:00")
    base = {"oferta": "X", "presupuesto_usd": 50, "fin_test": "2026-11-13T00:00:00-06:00", "lo_que_deja_usd": 12.24,
            "backend": {"estado": "activo"},
            "renovaciones": [{"conjunto_id": "r3", "inicio": "2026-11-13T00:00:00-06:00", "gasto_usd": 18.06, "compras": 0, "valor_usd": 0}]}
    d2 = {"fecha": "2026-11-13", "gasto_usd": 63.38, "ventas": 2, "neto_usd": 26.1, "cerrado": True}
    casos = [
        ("Oferta B, día 3 al 80 %", {**base, "dias": [d2, {"fecha": "2026-11-14", "gasto_usd": 40.17, "ventas": 2, "neto_usd": 16.7}]}, "APAGAR"),
        ("día 3 recién empieza (no cuenta)", {**base, "dias": [d2, {"fecha": "2026-11-14", "gasto_usd": 10, "ventas": 0, "neto_usd": 0}]}, "FALTAN_DIAS"),
        ("día 2 malo, día 3 bueno", {**base, "dias": [{**d2, "gasto_usd": 50, "ventas": 1}, {"fecha": "2026-11-14", "gasto_usd": 50, "ventas": 5, "neto_usd": 60, "cerrado": True}]}, "SIGUE"),
        ("pierde, pero R3 vende", {**base, "renovaciones": [{"conjunto_id": "r3", "inicio": "2026-11-13T00:00:00-06:00", "gasto_usd": 15, "compras": 2, "valor_usd": 30}],
                                   "dias": [d2, {"fecha": "2026-11-14", "gasto_usd": 40.17, "ventas": 2, "neto_usd": 16.7}]}, "ESPERAR_RESCATE"),
        ("sin backend activo", {**base, "backend": {"estado": "armando"}, "dias": [d2, {"fecha": "2026-11-14", "gasto_usd": 40, "ventas": 2}]}, "FALTA_INTENTO"),
        ("renovación de hace menos de 24 h", {**base, "renovaciones": [{"inicio": "2026-11-14T00:00:00-06:00"}], "dias": [d2, {"fecha": "2026-11-14", "gasto_usd": 40, "ventas": 2}]}, "FALTA_INTENTO"),
        ("dos días sin ventas", {**base, "dias": [{**d2, "ventas": 0, "neto_usd": 0}, {"fecha": "2026-11-14", "gasto_usd": 40, "ventas": 0, "cerrado": True}]}, "APAGAR"),
        ("el día 1 no se cuenta", {**base, "dias": [{"fecha": "2026-11-12", "gasto_usd": 56.86, "ventas": 6, "neto_usd": 79.6, "cerrado": True}, d2]}, "FALTAN_DIAS"),
    ]
    mal = 0
    for nombre, o, esperado in casos:
        r = decidir(o, ahora)
        ok = r["decision"] == esperado
        mal += not ok
        print(f"{'ok ' if ok else 'MAL'} {nombre}: {r['decision']} (esperado {esperado}) · {r['porque']}")
    return 1 if mal else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lectura")
    ap.add_argument("--desde-libro")
    ap.add_argument("--ahora")
    ap.add_argument("--presupuesto", type=float)
    ap.add_argument("--registrar", action="store_true")
    ap.add_argument("--probar", action="store_true")
    a = ap.parse_args(argv)
    if a.probar:
        return probar()
    ahora = _fecha(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    if a.lectura:
        lec = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
        ahora = _fecha(lec.get("leido")) or ahora if not a.ahora else ahora
        ofertas = lec.get("ofertas") or []
    elif a.desde_libro:
        ofertas = [lectura_del_libro(json.loads(LIBRO.read_text(encoding="utf-8")), a.desde_libro, ahora, a.presupuesto)]
    else:
        ap.error("falta --lectura, --desde-libro o --probar")
    res = {"leido": ahora.isoformat(timespec="minutes"), "regla": REGLA, "ofertas": [decidir(o, ahora) for o in ofertas]}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.registrar:
        with REGISTRO.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**res, "tipo": "corte_post_test"}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
