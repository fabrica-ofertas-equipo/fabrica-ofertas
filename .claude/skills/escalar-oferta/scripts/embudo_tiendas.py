#!/usr/bin/env python3
"""Embudo de la tienda CONSOLIDADO por oferta y por día: visitas, checkouts y compras de todas sus tiendas juntas.

Pedido del dueño (2026-11-14): «en Impultienda, en ofertas de 3 tiendas, no marca por cada una correcto el CR; hay que juntarlas
las 3 y sacar 1 KPI… y el consolidado de visitas, checkouts y compras, como tiene Impultienda con las barritas».
Por qué: en un funnel de niveles la landing está en UNA tienda y los botones llevan al checkout de las otras. Impultienda calcula
el CR de cada tienda por separado (compras / visitas a SU landing), así que la tienda de la landing muestra 0,5 % y la del nivel
completo 600 %. El dato verdadero es la suma: compras de todas ÷ visitas a la landing de todas.

El conector (impultienda_estadisticas) acepta cualquier día con desde = hasta = AAAA-MM-DD (días de calendario de la tienda,
hora de Argentina, la misma zona que la cuenta de Meta del libro). Este script:
  pedidos   → qué tiendas y qué días hay que leer: hoy para las ofertas andando y todo día de pauta que falte o haya quedado
              parcial (así se cierra «ayer» con su número final y se completan los huecos). Imprime JSON con store_id.
  cargar    → recibe las lecturas [{"tienda": "<subdominio>", "fecha": "AAAA-MM-DD", "stats": <respuesta>}] y por cada oferta y día
              en que estén TODAS sus tiendas escribe una fila en tienda_embudo_diario: {fecha, landing, checkout, compras,
              por_tienda: {subdominio: {landing, checkout, compras}}, leido, parcial}. Reemplaza la del mismo día. Recalcula
              tienda_embudo (total desde el inicio, con por_tienda). Escribe con el candado de libro.py.
compras = ventas.cantidad (pagos aprobados; los upsells post-compra son órdenes hijas y no cuentan, igual que en Impultienda).

Uso: python3 embudo_tiendas.py pedidos [--hoy AAAA-MM-DD]
     python3 embudo_tiendas.py cargar --lectura <json> [--leido ISO] [--seco]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import libro as LB  # noqa: E402

IDS = LB.LIBRO.parent / "tiendas_ids.json"
# Capa de tienda (tienda/): la plataforma donde se vende se elige en tienda/config.json; Impultienda por defecto.
_RAIZ_T = next(p for p in Path(__file__).resolve().parents if (p / "tienda" / "__init__.py").is_file())
if str(_RAIZ_T) not in sys.path:
    sys.path.insert(0, str(_RAIZ_T))
import tienda as _tienda  # noqa: E402

TIENDA = _tienda.activa()
ANDANDO = {"activo", "programado", "en_test", "test"}
CLAVES = ("landing", "checkout", "compras")


def _n(x) -> int:
    try:
        return int(float(x)) if x not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def zona(libro: dict) -> ZoneInfo:
    return ZoneInfo(libro.get("zona_horaria_cuenta") or "America/Argentina/Buenos_Aires")


def tiendas(t: dict) -> list[str]:
    return [s for s in (t.get("tienda") or []) if isinstance(s, str)] if isinstance(t.get("tienda"), list) else ([t["tienda"]] if isinstance(t.get("tienda"), str) else [])


def dia_inicio(t: dict, z: ZoneInfo) -> dt.date | None:
    try:
        return dt.datetime.fromisoformat(str(t.get("inicio"))).astimezone(z).date()
    except (TypeError, ValueError):
        return None


def dias_con_pauta(t: dict, z: ZoneInfo, hoy: dt.date) -> list[dt.date]:
    """Días que el panel exige: del inicio a hoy si la oferta anda; si no, solo los días con gasto en Meta."""
    ini = dia_inicio(t, z)
    if not ini or ini > hoy:
        return []
    todos = [ini + dt.timedelta(days=i) for i in range((hoy - ini).days + 1)]
    if str(t.get("estado") or "").lower() in ANDANDO:
        return todos
    con_gasto = {str(h.get("fecha"))[:10] for h in t.get("historial_diario") or [] if isinstance(h, dict) and float(h.get("gasto_usd") or 0) > 0}
    return [d for d in todos if d.isoformat() in con_gasto]


def pedidos(libro: dict, hoy: dt.date, ids: dict[str, str]) -> dict:
    z = zona(libro)
    out, faltan_ids = [], set()
    for t in libro.get("tests") or []:
        if not isinstance(t, dict) or not tiendas(t):
            continue
        hechos = {str(r.get("fecha"))[:10]: r for r in t.get("tienda_embudo_diario") or [] if isinstance(r, dict)}
        anda = str(t.get("estado") or "").lower() in ANDANDO
        for d in dias_con_pauta(t, z, hoy):
            r = hechos.get(d.isoformat())
            # hoy se relee en cada vuelta solo si la oferta anda; un día parcial se cierra cuando ya terminó
            if (anda and d == hoy) or r is None or not isinstance(r.get("por_tienda"), dict) or (r.get("parcial") and d < hoy):
                for s in tiendas(t):
                    if s not in ids:
                        faltan_ids.add(s)
                    out.append({"oferta": t.get("nombre"), "tienda": s, "store_id": ids.get(s), "fecha": d.isoformat()})
    return {"hoy": hoy.isoformat(), "lecturas": out, "faltan_ids": sorted(faltan_ids),
            "como": f"{TIENDA.como('estadisticas').get('herramienta') or TIENDA.como('estadisticas').get('ruta')} ({TIENDA.como('estadisticas').get('notas', '')}) por tienda y fecha; guardar [{{tienda, fecha, stats}}] y correr cargar"}


def _de_stats(st: dict) -> dict:
    """Embudo en forma normal (tienda/contrato.py) desde la respuesta cruda de la plataforma activa."""
    return TIENDA.embudo(st)


def total(filas: list[dict]) -> dict:
    tot = {k: sum(_n(r.get(k)) for r in filas) for k in CLAVES}
    pt: dict[str, dict] = {}
    for r in filas:
        for s, e in (r.get("por_tienda") or {}).items():
            acc = pt.setdefault(s, {k: 0 for k in CLAVES})
            for k in CLAVES:
                acc[k] += _n(e.get(k))
    tot["por_tienda"] = pt
    return tot


def aplicar(libro: dict, lecturas: list[dict], leido: str, hoy: dt.date) -> list[str]:
    z = zona(libro)
    por: dict[tuple[str, str], dict] = {}
    for x in lecturas:
        if isinstance(x, dict) and x.get("tienda") and x.get("fecha"):
            por[(str(x["tienda"]), str(x["fecha"])[:10])] = _de_stats(x.get("stats") or {})
    out = []
    for t in libro.get("tests") or []:
        ss = tiendas(t) if isinstance(t, dict) else []
        if not ss:
            continue
        fechas = sorted({f for (s, f) in por if s in ss})
        nuevas = []
        for f in fechas:
            if not all((s, f) in por for s in ss):
                out.append(f"{t.get('nombre')} {f}: faltan tiendas {[s for s in ss if (s, f) not in por]}; no se escribe")
                continue
            pt = {s: por[(s, f)] for s in ss}
            fila = {"fecha": f, **{k: sum(e[k] for e in pt.values()) for k in CLAVES}, "por_tienda": pt, "leido": leido,
                    "parcial": f >= hoy.isoformat(), "fuente": f"{TIENDA.nombre}: estadisticas (todas las tiendas del funnel)"}
            nuevas.append(fila)
        if not nuevas:
            continue
        viejas = [r for r in t.get("tienda_embudo_diario") or [] if isinstance(r, dict) and str(r.get("fecha"))[:10] not in {n["fecha"] for n in nuevas}]
        diario = sorted(viejas + nuevas, key=lambda r: str(r.get("fecha")))
        t["tienda_embudo_diario"] = diario
        ini = dia_inicio(t, z)
        desde_inicio = [r for r in diario if not ini or str(r.get("fecha"))[:10] >= ini.isoformat()]
        tot = total(desde_inicio)
        tot["_periodo"] = f"suma de {len(desde_inicio)} días de todas las tiendas, leído {leido}" + (" (hoy en curso)" if any(r.get("parcial") for r in desde_inicio) else "")
        t["tienda_embudo"] = tot
        cr = f"{100 * tot['compras'] / tot['landing']:.2f} %" if tot["landing"] else "—"
        out.append(f"{t.get('nombre')}: {len(nuevas)} días · total {tot['landing']} visitas, {tot['checkout']} checkouts, {tot['compras']} compras · CR {cr}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pedidos")
    p.add_argument("--hoy")
    c = sub.add_parser("cargar")
    c.add_argument("--lectura", required=True)
    c.add_argument("--leido")
    c.add_argument("--hoy")
    c.add_argument("--seco", action="store_true")
    a = ap.parse_args(argv)
    libro = json.loads(LB.LIBRO.read_text(encoding="utf-8"))
    z = zona(libro)
    ahora = dt.datetime.now(z)
    hoy = dt.date.fromisoformat(a.hoy) if a.hoy else ahora.date()
    if a.cmd == "pedidos":
        ids = (json.loads(IDS.read_text(encoding="utf-8")).get("ids") or {}) if IDS.exists() else {}
        print(json.dumps(pedidos(libro, hoy, ids), ensure_ascii=False, indent=1))
        return 0
    lect = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
    leido = a.leido or ahora.isoformat(timespec="minutes")
    if a.seco:
        for linea in aplicar(libro, lect, leido, hoy):
            print(linea)
        return 0
    lineas: list[str] = []
    LB.modificar(lambda L: lineas.extend(aplicar(L, lect, leido, hoy)))
    print("\n".join(lineas) or "nada que cargar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
