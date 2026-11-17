#!/usr/bin/env python3
"""Cuánto ruido tienen los números con los que decidimos (dueño, 17-nov: «medir primero», punto 4).

Antes de calibrar las reglas con ventanas y rangos de confianza, se mide con los datos del libro:

  1. PERSISTENCIA POR ANUNCIO: de un día al siguiente, ¿se repite el ROAS neto de un anuncio? Para los pares (anuncio, día, día
     siguiente) con gasto ≥ GASTO_MIN los dos días: de los días con ROAS < 1, cuántos al día siguiente dieron ≥ 1,5 (y al revés),
     y la correlación entre un día y el siguiente.
  2. COMPRAS DE MÁS O DE MENOS (dispersión): si las compras diarias de un anuncio se comportan como azar puro (Poisson) con su
     tasa media, la varianza ≈ la media. El índice varianza ÷ media dice cuánto del vaivén es azar (≈ 1) o cambio real (≫ 1).
  3. DECISIONES DE LA ESCALA: cada SURFEAR / BAJAR del sistema (presupuesto_eventos.jsonl) contra lo que hizo esa campaña en
     las 24 h siguientes (fotos_campanas.jsonl, una por hora). Una subida «se sostuvo» si las 24 h siguientes dieron ROAS neto
     ≥ 1,5; una bajada «acertó» si dieron < 1,5.
  4. META CONTRA LA TIENDA: por oferta y día, compras que atribuye Meta (historial_diario) ÷ compradores reales de la tienda.

ROAS neto = compras × neto por comprador de la oferta (ventana 7/14 días o historia, dashboard.negocio) ÷ gasto.
Solo lee. Uso: python3 medir_ruido.py [--json] [--gasto-min 5]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(AQUI))
from dashboard import negocio as N  # noqa: E402

FUNNELS = RAIZ / "ofertas" / "_funnels"
LIBRO = FUNNELS / "libro-de-tests.json"
EVENTOS = FUNNELS / "presupuesto_eventos.jsonl"
FOTOS = FUNNELS / "fotos_campanas.jsonl"


def _jsonl(ruta: Path) -> list[dict]:
    out = []
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(linea))
            except ValueError:
                pass
    return out


def _f(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 2) if sx and sy else None


def _valor(libro: dict, oferta: str, dia: dt.date, cache: dict) -> float | None:
    """Neto por comprador de la oferta con la ventana que termina ese día."""
    clave = (oferta, dia)
    if clave not in cache:
        tc = {k: v for k, v in (libro.get("tipos_de_cambio") or {}).items() if N._num(v) is not None}
        ts = [t for t in libro.get("tests") or [] if isinstance(t, dict) and (t.get("oferta") or t.get("nombre")) == oferta]
        v = N.neto_por_comprador_ventana(ts, tc, N.zona_de(libro), dia)
        cache[clave] = v["neto_por_venta"] if v else None
    return cache[clave]


def persistencia(libro: dict, gasto_min: float, cache: dict) -> dict:
    pares: list[tuple[float, float]] = []
    disp: list[tuple[float, float, int]] = []
    for t in libro.get("tests") or []:
        oferta = t.get("oferta") or t.get("nombre")
        por = defaultdict(dict)
        for r in (t.get("anuncios") or {}).get("por_dia") or []:
            por[str(r.get("id"))][r.get("fecha")] = r
        for _, dias in por.items():
            fechas = sorted(dias)
            compras = [_f(dias[f].get("compras_meta")) for f in fechas if _f(dias[f].get("gasto_usd")) >= gasto_min]
            if len(compras) >= 2:
                m = sum(compras) / len(compras)
                var = sum((c - m) ** 2 for c in compras) / (len(compras) - 1)
                disp.append((m, var, len(compras)))
            for a, b in zip(fechas, fechas[1:]):
                da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
                if (db - da).days != 1:
                    continue
                ga, gb = _f(dias[a].get("gasto_usd")), _f(dias[b].get("gasto_usd"))
                if ga < gasto_min or gb < gasto_min:
                    continue
                va, vb = _valor(libro, oferta, da, cache), _valor(libro, oferta, db, cache)
                if not va or not vb:
                    continue
                pares.append((_f(dias[a].get("compras_meta")) * va / ga, _f(dias[b].get("compras_meta")) * vb / gb))
    malos = [b for a, b in pares if a < 1]
    buenos = [b for a, b in pares if a >= 1.5]
    m_disp = sum(m for m, _, _ in disp) / len(disp) if disp else None
    v_disp = sum(v for _, v, _ in disp) / len(disp) if disp else None
    return {
        "pares": len(pares),
        "dia_malo": {"n": len(malos), "al_dia_siguiente_bueno": sum(1 for b in malos if b >= 1.5), "al_dia_siguiente_sobre_1": sum(1 for b in malos if b >= 1)},
        "dia_bueno": {"n": len(buenos), "al_dia_siguiente_malo": sum(1 for b in buenos if b < 1)},
        "correlacion_dia_siguiente": _corr([a for a, _ in pares], [b for _, b in pares]),
        "dispersion": {"anuncios": len(disp), "media_compras_dia": round(m_disp, 2) if m_disp is not None else None,
                       "varianza": round(v_disp, 2) if v_disp is not None else None,
                       "indice": round(v_disp / m_disp, 2) if m_disp else None},
    }


def _incrementos(fotos: list[dict]) -> dict[str, list[tuple[dt.datetime, float, float]]]:
    """Por campaña: [(hora, gasto, compras)] de cada hora (las fotos son acumulados del día de la cuenta)."""
    out: dict[str, list] = defaultdict(list)
    previo: dict[tuple[str, str], tuple[float, float]] = {}
    for f in sorted(fotos, key=lambda x: x.get("t") or ""):
        t = N.parsear_fecha(f.get("t"))
        if not t:
            continue
        for cid, c in (f.get("c") or {}).items():
            g0, n0 = previo.get((cid, f.get("dia")), (0.0, 0.0))
            g, n = _f(c.get("g")), _f(c.get("n"))
            out[cid].append((t, max(0.0, g - g0), max(0.0, n - n0)))
            previo[(cid, f.get("dia"))] = (g, n)
    return out


def decisiones_escala(libro: dict, cache: dict) -> dict:
    inc = _incrementos(_jsonl(FOTOS))
    zona = N.zona_de(libro)
    filas = []
    for e in _jsonl(EVENTOS):
        motivo = str(e.get("motivo") or "")
        tipo = "subir" if motivo.startswith("SURFEAR") or motivo.startswith("SUBIR") else "bajar" if motivo.startswith("BAJAR") else None
        if e.get("autor") != "sistema" or not tipo:
            continue
        t0 = N.parsear_fecha(e.get("cuando"))
        serie = inc.get(str(e.get("campana")), [])
        cubre = bool(t0 and serie and serie[0][0] <= t0 + dt.timedelta(hours=2) and serie[-1][0] >= t0 + dt.timedelta(hours=20))
        if not cubre:   # las fotos por hora empiezan el 16-nov: lo anterior no se puede medir
            filas.append({"cuando": e.get("cuando"), "oferta": e.get("oferta"), "tipo": tipo, "motivo": motivo[:90], "resultado": "sin 24 h de datos"})
            continue
        g = sum(x[1] for x in serie if t0 < x[0] <= t0 + dt.timedelta(hours=24))
        n = sum(x[2] for x in serie if t0 < x[0] <= t0 + dt.timedelta(hours=24))
        v = _valor(libro, e.get("oferta"), t0.astimezone(zona).date(), cache)
        roas = round(n * v / g, 2) if g and v else None
        ok = roas is not None and ((tipo == "subir" and roas >= 1.5) or (tipo == "bajar" and roas < 1.5))
        filas.append({"cuando": e.get("cuando"), "oferta": e.get("oferta"), "tipo": tipo, "motivo": motivo[:90],
                      "gasto_24h": round(g, 2), "compras_24h": n, "roas_neto_24h": roas, "resultado": "acertó" if ok else "no se sostuvo"})
    medidas = [f for f in filas if f["resultado"] != "sin 24 h de datos"]
    return {"decisiones": filas, "medidas": len(medidas), "acertadas": sum(1 for f in medidas if f["resultado"] == "acertó")}


def ventanas_cortas(libro: dict, cache: dict, horas: int = 4) -> dict:
    """Lo que ve la escala (ventanas de pocas horas) contra el día completo de la misma campaña: en cuántas ventanas el veredicto
    de la escala (subir ≥ 1,8 · bajar < 1,5 · mantener) es el contrario al del día entero (subir en un día que dio < 1,5 o bajar en
    uno que dio ≥ 1,8). Mide el ruido de decidir con 2-3 compras en pocas horas."""
    inc = _incrementos(_jsonl(FOTOS))
    ofertas = {cid: c.get("oferta") for cid, c in __import__("fotos_campanas").campanas_del_libro(libro).items()}
    zona = N.zona_de(libro)
    total = contrarias = 0
    ejemplos = []
    for cid, serie in inc.items():
        oferta = ofertas.get(cid)
        if not oferta:
            continue
        por_dia: dict[dt.date, list] = defaultdict(list)
        for x in serie:
            por_dia[x[0].astimezone(zona).date()].append(x)
        for dia, xs in por_dia.items():
            v = _valor(libro, oferta, dia, cache)
            gd, nd = sum(x[1] for x in xs), sum(x[2] for x in xs)
            if not v or gd < 20 or len(xs) < 20:   # día casi completo y con gasto
                continue
            roas_dia = nd * v / gd
            for i in range(0, len(xs) - horas + 1, horas):
                g, n = sum(x[1] for x in xs[i:i + horas]), sum(x[2] for x in xs[i:i + horas])
                if g < 3 or n < 2:   # la escala no decide sin 2 compras
                    continue
                r = n * v / g
                total += 1
                if (r >= 1.8 and roas_dia < 1.5) or (r < 1.5 and roas_dia >= 1.8):
                    contrarias += 1
                    if len(ejemplos) < 5:
                        ejemplos.append(f"{oferta} {dia} {xs[i][0].astimezone(zona):%H} h: {n:g} compras con US$ {g:.0f} → {r:.2f}; el día dio {roas_dia:.2f}")
    return {"horas": horas, "ventanas": total, "contrarias": contrarias, "ejemplos": ejemplos}


def meta_vs_tienda(libro: dict) -> dict:
    zona = N.zona_de(libro)
    por: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for t in libro.get("tests") or []:
        oferta = t.get("oferta") or t.get("nombre")
        for h in t.get("historial_diario") or []:
            por[(oferta, h.get("fecha"))][0] += _f(h.get("compras_meta"))
        for v in t.get("ventas") or []:
            if str(v.get("tipo") or "").lower() in N.TIPOS_VENTA_EXTRA:
                continue
            d = N.dia_de(v.get("dia_cuenta") or v.get("fecha"), zona)
            if d:
                por[(oferta, d.isoformat())][1] += 1
    filas = [{"oferta": o, "dia": d, "meta": int(m), "tienda": int(s)} for (o, d), (m, s) in sorted(por.items()) if m or s]
    tm, ts = sum(f["meta"] for f in filas), sum(f["tienda"] for f in filas)
    return {"dias": filas, "meta": tm, "tienda": ts, "razon": round(tm / ts, 2) if ts else None}


def medir(gasto_min: float = 5.0) -> dict:
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    cache: dict = {}
    return {"gasto_min": gasto_min, "persistencia": persistencia(libro, gasto_min, cache),
            "escala": decisiones_escala(libro, cache), "ventanas_cortas": ventanas_cortas(libro, cache), "meta_vs_tienda": meta_vs_tienda(libro)}


def texto(r: dict) -> str:
    p, e, m = r["persistencia"], r["escala"], r["meta_vs_tienda"]
    d = p["dispersion"]
    lineas = [
        f"1. Persistencia por anuncio ({p['pares']} pares de días seguidos con ≥ US$ {r['gasto_min']:g} cada uno):",
        f"   · días con ROAS neto < 1: {p['dia_malo']['n']}; al día siguiente ≥ 1,5: {p['dia_malo']['al_dia_siguiente_bueno']}, ≥ 1: {p['dia_malo']['al_dia_siguiente_sobre_1']}",
        f"   · días con ROAS neto ≥ 1,5: {p['dia_bueno']['n']}; al día siguiente < 1: {p['dia_bueno']['al_dia_siguiente_malo']}",
        f"   · correlación entre un día y el siguiente: {p['correlacion_dia_siguiente']}",
        f"2. Dispersión de compras diarias ({d['anuncios']} anuncios): media {d['media_compras_dia']}, varianza {d['varianza']}, índice {d['indice']} (≈ 1 = azar puro)",
        f"3. Escala: {e['acertadas']} de {e['medidas']} decisiones del sistema se sostuvieron en las 24 h siguientes",
    ]
    for f in e["decisiones"]:
        lineas.append(f"   · {f['cuando'][:16]} {f['oferta']} {f['tipo']}: {f['resultado']}"
                      + (f" (24 h: {f['compras_24h']:g} compras, US$ {f['gasto_24h']}, ROAS neto {f['roas_neto_24h']})" if "gasto_24h" in f else "")
                      + f" — {f['motivo']}")
    w = r["ventanas_cortas"]
    lineas.append(f"   · ventanas de {w['horas']} h con ≥ 2 compras: {w['ventanas']}; con veredicto contrario al del día completo: {w['contrarias']}")
    lineas += [f"     {x}" for x in w["ejemplos"]]
    lineas.append(f"4. Meta contra la tienda: Meta atribuye {m['meta']} compras, la tienda tiene {m['tienda']} compradores (razón {m['razon']})")
    return "\n".join(lineas)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gasto-min", type=float, default=5.0)
    a = ap.parse_args()
    r = medir(a.gasto_min)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else texto(r))
