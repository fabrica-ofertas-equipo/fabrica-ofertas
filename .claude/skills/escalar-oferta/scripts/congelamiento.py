"""R16 · Congelamiento de ofertas en empate (dueño, 15-nov; nació de Oferta G).

Bandas (números en `ofertas/_funnels/reglas.json` → `congelamiento`):
  · RENOVAR  — CPA ≤ 0,54 × valor neto por comprador (= 0,5 × AOV bruto; 17-nov: ventana 7/14 días, dashboard.negocio), con al menos 1 venta: renovación diaria (R9) y escala.
               Dueño: «cuando el CPA es la mitad o menos que el AOV».
  · CONGELAR — no llega a RENOVAR, tiene ≥ 3 ventas y ROAS neto (neto ÷ gasto en Meta) ≥ 0,95: un día sin renovar ni tocar el
               presupuesto, solo backend agresivo (2 order bumps + 4 upsells post-pago).
  · NORMAL   — todo lo demás: no se renueva; actúan los cortes de siempre (R1, R4).

Ciclo de un congelamiento (campo `congelada` del test en el libro):
  {"desde", "hasta", "dias": [fechas del mercado congeladas], "motivo", "quien", "medicion_inicial": {...}}
  · Mientras no tenga `resultado`, la oferta está congelada (aunque `hasta` ya haya pasado: hasta medir, no se renueva).
  · Pasado `hasta` y cerrado el último día en la zona de la cuenta, se miden los días congelados (`calcular_periodo`):
      RENOVAR → resultado «renovar» (sigue el flujo normal) · NORMAL → resultado «normal» ·
      CONGELAR con menos de `dias_max` días → un día más · CONGELAR con `dias_max` días → `espera_duenio` y aviso; sigue
      congelada hasta que el dueño ponga `resultado`.
  · Una oferta se congela sola una sola vez; después decide el dueño.
Los cortes R1/R4 siguen durante el congelamiento. R4b no aplica (pide rondas de renovación).

OFERTAS VALIDADAS (dueño, 15-nov: «separarlas»): una oferta que ya escaló (presupuesto por encima del inicial) o que tiene
una ronda de renovación con 24 h entregando NO se congela nunca. Para ella:
  · renueva mientras el ROAS neto de los últimos 3 días CERRADOS sea ≥ 0,95 (empate incluido): la fatiga se cura con creativos;
  · el presupuesto lo decide solo la escala simétrica (E1-E4) y los cortes R4/R4b;
  · si el ROAS neto de esos 3 días cae en el empate (0,95-1,20) → BACKEND_AGRESIVO: se le suma lo que falte para llegar a
    2 order bumps + 4 upsells, sin frenar nada (una vez por oferta).
Ventana: días cerrados de la cuenta (ayer y los dos anteriores); el día en curso no cuenta. En test se usa el test entero.

Uso:  python3 congelamiento.py evaluar            (solo dice qué haría)
      python3 congelamiento.py evaluar --aplicar  (lo escribe en el libro con libro.py y deja pendientes para el dueño)
Lo corre la vigilancia de cada hora (paso «R16»).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
sys.path.insert(0, str(AQUI))
from reglas import valor  # noqa: E402

VENTAS_MIN = valor("congelamiento.ventas_minimas", 3)
RENOVAR_CPA_MAX_AOV = valor("congelamiento.renovar_cpa_max_aov", 0.5)   # respaldo si falta el valor neto
RENOVAR_CPA_MAX_VALOR = valor("congelamiento.renovar_cpa_max_valor_neto", 0.54)   # = 0,5 del bruto pasado a neto (≈ 92 %)
PISO = valor("congelamiento.piso_roas_neto", 0.95)
DIAS = valor("congelamiento.dias", 1)
DIAS_MAX = valor("congelamiento.dias_max", 2)
VENTANA = valor("congelamiento.ventana_dias_cerrados", 3)
V_PISO_RENOVAR = valor("congelamiento.validada.renovar_roas_neto_min", 0.95)
V_EMPATE = valor("congelamiento.validada.empate_backend_roas_neto", [0.95, 1.2])


def _fecha(s):
    try:
        return dt.datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


# ---------- lectura (la usan escalar_presupuesto.py y ofertas_que_pegan.py) ----------

def congelada_test(t: dict | None, ahora: dt.datetime) -> dict | None:
    """El congelamiento vigente del test, o None. Vigente = empezó y todavía no tiene `resultado`."""
    c = (t or {}).get("congelada")
    if not isinstance(c, dict) or c.get("resultado"):
        return None
    desde = _fecha(c.get("desde"))
    if desde and ahora < desde:
        return None
    return c


def congelada(nombre: str | None, ahora: dt.datetime, libro: dict | None = None) -> dict | None:
    if not nombre:
        return None
    if libro is None:
        try:
            libro = json.loads(LIBRO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    for t in libro.get("tests") or []:
        if nombre in (t.get("nombre"), t.get("oferta")):
            return congelada_test(t, ahora)
    return None


def banda(m: dict) -> str:
    """renovar / congelar / normal con ventas_n, cpa, ticket_medio y roas_neto (salida de dashboard.negocio)."""
    nv = int(m.get("ventas_n") or 0)
    cpa, rn = m.get("cpa"), m.get("roas_neto")
    vc = (m.get("valor_comprador") or {}).get("neto_por_venta")   # valor por comprador del sistema (neto, 7/14 días; 17-nov)
    tope = RENOVAR_CPA_MAX_VALOR * vc if vc else (RENOVAR_CPA_MAX_AOV * m["ticket_medio"] if m.get("ticket_medio") else None)
    if nv >= 1 and cpa is not None and tope and cpa <= tope:
        return "renovar"
    if nv >= VENTAS_MIN and rn is not None and rn >= PISO:
        return "congelar"
    return "normal"


def _resumen(m: dict) -> dict:
    return {**{k: m.get(k) for k in ("ventas_n", "gasto_meta", "cpa", "ticket_medio", "roas_neto")},
            "valor_neto": (m.get("valor_comprador") or {}).get("neto_por_venta")}


def validada(t: dict, ahora: dt.datetime) -> str | None:
    """Motivo por el que la oferta está validada, o None. Ya escaló, o una ronda de renovación entregó 24 h."""
    cambios = [c for c in (t.get("presupuesto_cambios") or []) if isinstance(c, dict)]
    inicial = next((c.get("a") for c in cambios if c.get("tipo") == "inicio"), None)
    for c in cambios:
        if c.get("tipo") != "inicio" and inicial and (c.get("a") or 0) > inicial:
            return f"escaló de US$ {inicial:g} a US$ {c.get('a'):g} ({c.get('tipo')})"
    for r in t.get("renovaciones") or []:
        if str(r.get("estado", "")).lower() in ("pausada", "cancelada", "produciendo"):
            continue
        ini = _fecha(r.get("inicio"))
        if ini and ahora - ini >= dt.timedelta(hours=24):
            return f"la ronda {r.get('ronda')} entregó 24 h"
    return None


_CACHE: dict = {}


def ventana_cerrada(libro: dict, nombre: str, ahora: dt.datetime) -> dict:
    """Métricas de la oferta en los últimos VENTANA días cerrados de la cuenta (sin el día en curso)."""
    sys.path.insert(0, str(RAIZ))
    from dashboard import negocio as N
    hoy = ahora.astimezone(N.zona_de(libro)).date()
    clave = (id(libro), hoy)
    if clave not in _CACHE:
        _CACHE[clave] = {o.get("nombre"): o for o in N.calcular_periodo(libro, ahora, hoy - dt.timedelta(days=VENTANA), hoy - dt.timedelta(days=1))["ofertas"]}
    return _CACHE[clave].get(nombre) or {}


def renovacion(libro: dict, t: dict, o: dict, ahora: dt.datetime) -> dict:
    """¿Toca renovar? {renueva, motivo, regimen, metricas}. `o` = la oferta de N.calcular (desde el inicio).
    En test: banda del test entero (R16 de entrada). Después: 3 días cerrados; validadas con ROAS neto ≥ 1, las demás con R16."""
    nombre = t.get("nombre") or t.get("oferta")
    if o.get("fase") == "test":
        b = banda(o)
        return {"renueva": b == "renovar", "regimen": "entrada", "banda": b, "metricas": _resumen(o),
                "motivo": f"test: CPA {o.get('cpa')} vs valor neto por comprador {(o.get('valor_comprador') or {}).get('neto_por_venta')} → {b}"}
    m = ventana_cerrada(libro, nombre, ahora)
    if not (m.get("gasto_meta") or 0) > 0:
        m = o   # sin días cerrados con gasto (recién salió del test): lo de siempre
    v = validada(t, ahora)
    if v:
        rn = m.get("roas_neto")
        ok = rn is not None and int(m.get("ventas_n") or 0) >= 1 and rn >= V_PISO_RENOVAR
        return {"renueva": ok, "regimen": "validada", "validada": v, "metricas": _resumen(m),
                "motivo": f"validada ({v}): ROAS neto de 3 días cerrados {rn} {'≥' if ok else '<'} {V_PISO_RENOVAR}"}
    b = banda(m)
    return {"renueva": b == "renovar", "regimen": "entrada", "banda": b, "metricas": _resumen(m),
            "motivo": f"entrada: 3 días cerrados, CPA {m.get('cpa')} vs valor neto por comprador {(m.get('valor_comprador') or {}).get('neto_por_venta')} → {b}"}


# ---------- decisión ----------

def _zona_mercado(mercado: str | None):
    try:
        from control_previo import ZONA
        nombre = ZONA.get(mercado or "")
        return ZoneInfo(nombre) if nombre else None
    except Exception:  # noqa: BLE001
        return None


def evaluar(libro: dict, ahora: dt.datetime) -> list[dict]:
    sys.path.insert(0, str(RAIZ))
    from dashboard import negocio as N
    total = {o.get("nombre"): o for o in N.calcular(libro, ahora)["ofertas"]}
    zona_cuenta = N.zona_de(libro)
    hoy_cuenta = ahora.astimezone(zona_cuenta).date()
    out = []
    for t in libro.get("tests") or []:
        nombre = t.get("nombre") or t.get("oferta")
        o = total.get(nombre) or {}
        if o.get("estado") != "activa":
            continue
        c = t.get("congelada") if isinstance(t.get("congelada"), dict) else None
        z = _zona_mercado(t.get("mercado")) or zona_cuenta
        base = {"oferta": nombre, "mercado": t.get("mercado")}
        if c and not c.get("resultado"):
            hasta = _fecha(c.get("hasta"))
            if c.get("espera_duenio"):
                out.append({**base, "decision": "ESPERA_DUENIO", "porque": "dos días congelada en la banda: decide el dueño"})
                continue
            dias = [dt.date.fromisoformat(d) for d in c.get("dias") or []]
            if not hasta or ahora < hasta or not dias or hoy_cuenta <= dias[-1]:
                out.append({**base, "decision": "CONGELADA", "porque": f"congelada hasta {c.get('hasta')}; se mide al cerrar el día {dias[-1] if dias else '?'} de la cuenta"})
                continue
            p = {x.get("nombre"): x for x in N.calcular_periodo(libro, ahora, dias[0], dias[-1])["ofertas"]}.get(nombre) or {}
            if not (p.get("gasto_meta") or 0) > 0:
                out.append({**base, "decision": "CONGELADA", "porque": "falta la lectura de Meta de los días congelados: se mide en la próxima vuelta"})
                continue
            b = banda(p)
            med = {"dias": [d.isoformat() for d in dias], **_resumen(p), "banda": b}
            if b == "renovar":
                out.append({**base, "decision": "SALE_RENOVAR", "medicion": med, "cambio": {"resultado": "renovar", "medido": ahora.isoformat(timespec="minutes"), "medicion_final": med}})
            elif b == "normal":
                out.append({**base, "decision": "SALE_NORMAL", "medicion": med, "cambio": {"resultado": "normal", "medido": ahora.isoformat(timespec="minutes"), "medicion_final": med}})
            elif len(dias) < DIAS_MAX:
                nuevo_hasta = hasta + dt.timedelta(days=1)
                nuevo_dia = (nuevo_hasta - dt.timedelta(days=1)).astimezone(z).date()
                out.append({**base, "decision": "OTRO_DIA", "medicion": med,
                            "cambio": {"hasta": nuevo_hasta.isoformat(), "dias": [d.isoformat() for d in dias] + [nuevo_dia.isoformat()], "medicion_dia_1": med}})
            else:
                out.append({**base, "decision": "AVISAR_DUENIO", "medicion": med,
                            "cambio": {"espera_duenio": True, "medido": ahora.isoformat(timespec="minutes"), "medicion_final": med}})
            continue
        v = validada(t, ahora)
        if v:   # validada: nunca se congela; en empate se le suma el backend agresivo sin frenar nada
            m = ventana_cerrada(libro, nombre, ahora)
            rn = m.get("roas_neto")
            bk = t.get("backend") if isinstance(t.get("backend"), dict) else {}
            if rn is not None and V_EMPATE[0] <= rn <= V_EMPATE[1] and not bk.get("agresivo"):
                out.append({**base, "decision": "BACKEND_AGRESIVO", "medicion": {**_resumen(m), "validada": v},
                            "porque": f"validada en empate: ROAS neto de 3 días cerrados {rn} entre {V_EMPATE[0]} y {V_EMPATE[1]}: sumar 2.º bump y hasta 4 upsells, sin congelar"})
            continue
        if c:   # ya tuvo su congelamiento: desde ahí decide el dueño
            continue
        # ¿Entra en la banda? En test, con lo del test; después, con los últimos 3 días de la cuenta (la ventana de R4).
        if o.get("fase") == "test":
            m = o
        else:
            m = ventana_cerrada(libro, nombre, ahora)
            if not (m.get("gasto_meta") or 0) > 0:
                m = o
        b = banda(m)
        if b != "congelar":
            continue
        local = ahora.astimezone(z)
        prox = dt.datetime.combine(local.date() + dt.timedelta(days=1), dt.time(0), tzinfo=z)
        hasta = prox + dt.timedelta(days=DIAS)
        dias = [(prox + dt.timedelta(days=i)).date().isoformat() for i in range(DIAS)]
        out.append({**base, "decision": "CONGELAR", "medicion": {**_resumen(m), "banda": b},
                    "cambio": {"desde": ahora.isoformat(timespec="minutes"), "hasta": hasta.isoformat(), "dias": dias,
                               "motivo": f"R16: {m.get('ventas_n')} ventas, CPA US$ {m.get('cpa')} > {RENOVAR_CPA_MAX_VALOR} × el valor neto por comprador (US$ {(m.get('valor_comprador') or {}).get('neto_por_venta')}), ROAS neto {m.get('roas_neto')} ≥ {PISO}",
                               "quien": "regla R16", "medicion_inicial": {**_resumen(m), "banda": b}}})
    return out


def aplicar(decisiones: list[dict], ahora: dt.datetime) -> None:
    import libro as LB
    for d in decisiones:
        cambio = d.get("cambio") or {}
        if not cambio and d.get("decision") != "BACKEND_AGRESIVO":
            continue

        def mod(L, d=d, cambio=cambio):
            t = LB._test(L, d["oferta"])
            if d["decision"] != "BACKEND_AGRESIVO":
                c = t.get("congelada") if isinstance(t.get("congelada"), dict) else {}
                c.update(cambio)
                t["congelada"] = c
            if d["decision"] == "BACKEND_AGRESIVO":
                if not isinstance(t.get("backend"), dict):
                    t["backend"] = {}
                bk = t["backend"]
                bk["agresivo"] = {"pedido": ahora.isoformat(timespec="minutes"), "porque": d.get("porque"), "estado": "pendiente"}
                t.setdefault("pendientes", []).append({"que": "R16 validada en empate: sumar backend agresivo (2 bumps + 4 upsells) sin congelar",
                                                        "desde": ahora.isoformat(timespec="minutes"), "porque": d.get("porque")})
                return
            if d["decision"] in ("CONGELAR", "AVISAR_DUENIO"):
                que = ("R16: oferta congelada un día (sin renovar ni tocar presupuesto); armar backend agresivo: 2 bumps + 4 upsells"
                       if d["decision"] == "CONGELAR" else
                       "R16: dos días congelada en el empate; decidir: renovar, seguir congelada o dejarla a los cortes")
                t.setdefault("pendientes", []).append({"que": que, "desde": ahora.isoformat(timespec="minutes"),
                                                        "porque": json.dumps(d.get("medicion"), ensure_ascii=False)})
        LB.modificar(mod)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluar")
    e.add_argument("--aplicar", action="store_true")
    e.add_argument("--ahora")
    e.add_argument("--libro", help="otro libro (para pruebas; con --aplicar se ignora)")
    a = ap.parse_args()
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    libro = json.loads(Path(a.libro or LIBRO).read_text(encoding="utf-8"))
    dec = evaluar(libro, ahora)
    if a.aplicar and not a.libro:
        aplicar(dec, ahora)
    json.dump({"ahora": ahora.isoformat(timespec="minutes"), "regla": "R16 congelamiento", "decisiones": dec}, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
