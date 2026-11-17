"""¿Qué campañas saca hoy cada oferta? (regla R9 v2 del dueño, 17-nov-2026).

Antes (R9, 13 al 16-nov): un conjunto nuevo por día DENTRO de la CBO madre, con límites de gasto de 10 % a 20 %. No funcionó:
en Oferta F ES la R3 adentro de la madre gastó US$ 190 con 2 compras (CPA 95) y en Oferta B Meta casi no les dio
presupuesto a los conjuntos nuevos; las variaciones de B08 en una CBO APARTE gastaron US$ 360 con 10 compras (CPA 36) y
encontraron un ganador nuevo (D4). Desde el 17-nov (dueño: «sacar todos los días una CBO 1-1-10»):

  · NUEVOS — todos los días, CBO 1-1-10 aparte con 10 conceptos distintos (referente primero, después la landing).
  · ITERACIONES — CBO 1-1-10 aparte con variaciones de los ganadores, SOLO si:
      - hay un ganador (≥ 3 compras con ROAS > 2 en las últimas 48 h; ROAS = compras de Meta × AOV de la tienda ÷ gasto);
      - la ronda de iteraciones anterior ya entregó 24 h (se pudo leer) y ninguna está produciéndose o programada;
      - la familia no está descansando: 2 rondas leídas seguidas sin rendir → 3 días de descanso (rendir = algún anuncio de la
        ronda con compras y CPA ≤ corte), salvo que el campeón esté fatigado (CPA subiendo 3 días seguidos).
    Como mucho 2 familias por ronda: 10 a una o 6 + 4.
  · POCKET — cada ganador que no está en un pocket sale a uno: CBO 1-1-N con los ganadores nuevos de la MISMA familia de
    concepto (tope 5); conceptos distintos, pockets separados. Presupuesto = máx(2 tickets, 3 × CPA medio) (Bilbao, ago-26),
    corte 1 ticket. Un ganador ahogado dentro de un 1-1-N (< 15 % del gasto con buen CPA) sale a su propio 1-1-1.
  · MANUAL — cada 5 ganadores sostenidos en pocket (≥ 3 compras y ROAS > 2 en 48 h DENTRO del pocket) que todavía no están en
    una manual: una cost cap 1-1-5 (CPA medio de esos 5 × 1,3) y una bid cap 1-1-5 (ticket × 1,3), en otra cuenta si está lista.
  · MADRE — no recibe más conjuntos. Los conjuntos de renovación viejos pierden sus límites (10 % y 20 %) a los 2 días.

Familia de concepto: la raíz del anuncio. «VB D4 | B08 en 2:23» es hija de B08; «VB2 F9 | D4 + …» es hija de D4 y nieta de B08.
Se lee del nombre del anuncio (el primer código de otro anuncio que nombra), si no del nombre de la campaña de variaciones
(«… variaciones B08»), y se puede fijar a mano en `familias` del test del libro ({"E1": "B08"}).

Uso (desde la raíz del repositorio):
  python3 .claude/skills/escalar-oferta/scripts/plan_renovacion.py [--libro …] [--ahora ISO] [--oferta "Oferta F"]
Salida: JSON por stdout. No escribe nada.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(AQUI))
from dashboard import negocio as N  # noqa: E402
from ofertas_que_pegan import ventana, _n_ronda  # noqa: E402
from ofertas_que_pegan import evaluar as evaluar_pega  # noqa: E402
from reglas import valor  # noqa: E402
from vigilar_corte import ticket_corte  # noqa: E402
from fotos_campanas import rol_por_nombre  # noqa: E402

LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
R = "renovacion."

GAN_COMPRAS = valor(R + "ganador.compras_min", 3)
GAN_ROAS = valor(R + "ganador.roas_min", 1.85)   # neto (= 2,0 bruto)
GAN_HORAS = valor(R + "ganador.ventana_horas", 48)
CBO_TICKETS = valor(R + "cbo_diaria.presupuesto_tickets", 3)
CBO_CORTE = valor(R + "cbo_diaria.corte_tickets", 1.5)
IT_LECTURA_H = valor(R + "iteraciones.lectura_horas", 24)
IT_SIN_RENDIR = valor(R + "iteraciones.rondas_sin_rendir_para_descanso", 2)
IT_DESCANSO_D = valor(R + "iteraciones.descanso_dias", 3)
IT_FATIGA_D = valor(R + "iteraciones.fatiga_dias_cpa_subiendo", 3)
IT_FAMILIAS = valor(R + "iteraciones.familias_max", 2)
IT_REPARTO2 = valor(R + "iteraciones.reparto_dos", [6, 4])
PK_TICKETS = valor(R + "pocket.presupuesto_tickets", 2)
PK_CPA = valor(R + "pocket.presupuesto_cpa_medio", 3)
PK_CORTE = valor(R + "pocket.corte_tickets", 1.0)
PK_MAX = valor(R + "pocket.max_por_pocket", 5)
PK_AHOGADO = valor(R + "pocket.ahogado_pct_gasto", 15)
MN_CADA = valor(R + "manual.cada_ganadores", 5)
MN_COST = valor(R + "manual.cost_cap_x_cpa_medio", 1.3)
MN_BID = valor(R + "manual.bid_cap_x_ticket", 1.3)
MADRE_DIAS = valor(R + "madre_limites_dias", 2)
ANUNCIOS = valor(R + "cbo_diaria.anuncios", 10)

COD = re.compile(r"\b([A-Z]{1,2}\d{1,2})\b")
TERMINADAS = ("pausada", "cancelada", "cerrada")


# ---------- anuncios, códigos y familias ----------

def codigo_propio(nombre: str) -> str | None:
    """«VB D4 | B08 en 2:23» → D4; «B08 | El testamento…» → B08; «VB2 F9 | …» → F9 (el último código del primer tramo)."""
    primero = str(nombre or "").split("|")[0]
    cods = COD.findall(primero)
    return cods[-1] if cods else None


def codigo_padre(nombre: str, propio: str | None, campana_nombre: str = "") -> str | None:
    resto = "|".join(str(nombre or "").split("|")[1:])
    for c in COD.findall(resto):
        if c != propio and not re.fullmatch(r"[IVR]\d{1,2}", c):   # I4, V1, R3 son formato o ronda, no anuncios
            return c
    if rol_por_nombre(campana_nombre or "", True) in ("test_variaciones", "iteraciones"):
        for c in COD.findall(str(campana_nombre or "")):
            if c != propio and not re.fullmatch(r"[IVR]\d{1,2}", c):
                return c
    return None


def familias(anuncios: list[dict], fijas: dict | None = None) -> dict[str, str]:
    """código → código raíz. Sigue la cadena de padres (F9 → D4 → B08); `fijas` del libro manda."""
    padre: dict[str, str | None] = {}
    for a in anuncios:
        c = a.get("codigo")
        if c and padre.get(c) is None:
            padre[c] = a.get("padre")
    for k, v in (fijas or {}).items():
        padre[k] = None if v == k else v
    raiz = {}
    for c in padre:
        x, vistos = c, {c}
        while padre.get(x) and padre[x] not in vistos:
            x = padre[x]
            vistos.add(x)
        raiz[c] = x
    return raiz


def _num(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _fecha(s):
    return N.parsear_fecha(s) if s else None


def roles_campanas(t: dict) -> dict[str, dict]:
    """id de campaña → {rol, nombre, inicio, corte_tickets, codigos}."""
    out = {}
    if t.get("campana"):
        out[str(t["campana"])] = {"rol": "principal", "nombre": "", "inicio": t.get("inicio")}
    for c in ((t.get("ficha") or {}).get("campanas") or []):
        if isinstance(c, dict) and c.get("id"):
            rol = c.get("rol") or rol_por_nombre(c.get("nombre") or "", True)
            out[str(c["id"])] = {**c, "rol": "principal" if str(c["id"]) == str(t.get("campana")) else rol}
    return out


def leer_anuncios(t: dict, roles: dict, ahora: dt.datetime) -> list[dict]:
    """Cada anuncio con su gasto y compras de toda la vida, de las últimas 48 h y por día."""
    a = t.get("anuncios") or {}
    lista = a.get("lista") or [] if isinstance(a, dict) else []
    zona = ZoneInfo("America/Argentina/Buenos_Aires")
    hoy = ahora.astimezone(zona).date()
    desde = hoy - dt.timedelta(days=max(1, math.ceil(GAN_HORAS / 24)) - 1)
    por_dia = defaultdict(dict)
    for r in (a.get("por_dia") or []) if isinstance(a, dict) else []:
        por_dia[str(r.get("id"))][str(r.get("fecha"))] = r
    out = []
    for ad in lista:
        cid = str(ad.get("campana") or "")
        rc = roles.get(cid) or {"rol": rol_por_nombre(ad.get("conjunto") or "", True)}
        conj = str(ad.get("conjunto") or "")
        rol = rc.get("rol")
        # Conjuntos de renovación adentro de la madre: rol propio para no mezclarlos con los anuncios originales
        if rol == "principal" and re.search(r"renovaci", conj, re.I):
            rol = "renovacion_madre"
        dias = por_dia.get(str(ad.get("id")), {})
        g48 = sum(_num(r.get("gasto_usd")) for f, r in dias.items() if f >= desde.isoformat())
        c48 = sum(_num(r.get("compras_meta")) for f, r in dias.items() if f >= desde.isoformat())
        propio = codigo_propio(ad.get("nombre"))
        # Las rondas repiten códigos (C01-C10 en R3 y en R5): se les suma la ronda para no confundirlos
        m = re.search(r"\b(?:Renovaci[oó]n|Nuevos|Iteraciones)\s+(R\d+)", conj + " " + str(rc.get("nombre") or ""), re.I)
        if propio and m and rol in ("renovacion_madre", "nuevos", "iteraciones"):
            propio = f"{propio}·{m.group(1).upper()}"
        out.append({
            "id": str(ad.get("id")), "nombre": ad.get("nombre"), "campana": cid, "rol": rol, "conjunto": conj,
            "estado": ad.get("estado"), "codigo": propio,
            "padre": codigo_padre(ad.get("nombre"), (propio or "").split("·")[0], rc.get("nombre") or ""),
            "gasto": _num(ad.get("gasto_usd")), "compras": _num(ad.get("compras_meta")),
            "gasto_48h": round(g48, 2), "compras_48h": c48,
            "por_dia": {f: (_num(r.get("gasto_usd")), _num(r.get("compras_meta"))) for f, r in sorted(dias.items())},
        })
    return out


def es_ganador(gasto: float, compras: float, aov: float) -> bool:
    return compras >= GAN_COMPRAS and gasto > 0 and compras * aov / gasto > GAN_ROAS


def _roas(gasto, compras, aov):
    return round(compras * aov / gasto, 2) if gasto else None


# ---------- rondas de iteraciones ----------

def rondas_iteraciones(t: dict, roles: dict, anuncios: list[dict], raiz: dict) -> list[dict]:
    """Rondas de iteraciones: las anotadas con tipo «iteraciones» en `renovaciones` y las CBO de variaciones de la ficha."""
    rondas = []
    vistos = set()
    for r in t.get("renovaciones") or []:
        if str(r.get("tipo") or "") == "iteraciones":
            rondas.append({"ronda": r.get("ronda"), "campana": str(r.get("campana") or ""), "inicio": r.get("inicio"),
                           "estado": str(r.get("estado") or ""), "sobre": r.get("sobre") or []})
            vistos.add(str(r.get("campana") or ""))
    for cid, c in roles.items():
        if c.get("rol") in ("test_variaciones", "iteraciones") and cid not in vistos:
            fams = [raiz.get(a["codigo"], a["codigo"]) for a in anuncios if a["campana"] == cid and a["codigo"]]
            sobre = sorted(set(f for f in fams if f), key=fams.count, reverse=True)[:2]
            rondas.append({"ronda": c.get("nombre"), "campana": cid, "inicio": c.get("inicio") or c.get("detectada"),
                           "estado": "activa", "sobre": sobre})
    return sorted(rondas, key=lambda r: str(r.get("inicio") or ""))


def rindio(ronda: dict, anuncios: list[dict], corte_usd: float) -> bool:
    for a in anuncios:
        if a["campana"] == ronda.get("campana") and a["compras"] >= 1 and a["gasto"] / a["compras"] <= corte_usd:
            return True
    return False


def fatigado(anuncios_fam: list[dict], ahora: dt.datetime) -> bool:
    """CPA diario subiendo IT_FATIGA_D días seguidos (días cerrados con compras) en la familia del campeón."""
    dias = defaultdict(lambda: [0.0, 0.0])
    for a in anuncios_fam:
        for f, (g, c) in a["por_dia"].items():
            dias[f][0] += g
            dias[f][1] += c
    hoy = ahora.astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).date().isoformat()
    cpas = [d[0] / d[1] for f, d in sorted(dias.items()) if f < hoy and d[1] > 0]
    ult = cpas[-IT_FATIGA_D:]
    return len(ult) == IT_FATIGA_D and all(ult[i] < ult[i + 1] for i in range(len(ult) - 1))


# ---------- plan por oferta ----------

def plan_oferta(t: dict, pega: dict, ahora: dt.datetime, libro: dict) -> dict:
    ficha = t.get("ficha") or {}
    ticket = ticket_corte(ficha) or 0.0
    aov = float(pega.get("aov") or 0) or ticket
    corte_usd = CBO_CORTE * ticket
    roles = roles_campanas(t)
    anuncios = leer_anuncios(t, roles, ahora)
    raiz = familias(anuncios, t.get("familias"))
    for a in anuncios:
        a["familia"] = raiz.get(a["codigo"], a["codigo"])
    v = ventana(t.get("mercado"), ahora)
    renov = sorted(t.get("renovaciones") or [], key=lambda r: str(r.get("inicio") or ""))
    n = max((_n_ronda(r.get("ronda")) for r in renov), default=2)
    salida = _fecha(v.get("salida"))
    out = {"oferta": t.get("oferta") or t.get("nombre"), "test": t.get("nombre"), "mercado": t.get("mercado"),
           "renueva": bool(pega.get("pega")), "motivo": pega.get("motivo"), "ticket_usd": round(ticket, 2), "aov_usd": round(aov, 2),
           "salida": v.get("salida"), "en_ventana": v.get("en_ventana"), "ventana": v.get("ventana")}
    if pega.get("salida_inmediata") or (pega.get("anticipada") and pega.get("salida")):
        out["salida"] = pega.get("salida")
        out["salida_inmediata"] = bool(pega.get("salida_inmediata"))

    # Ganadores (cualquier campaña), 48 h
    gan = [a for a in anuncios if es_ganador(a["gasto_48h"], a["compras_48h"], aov)]
    out["ganadores"] = [{"codigo": a["codigo"], "familia": a["familia"], "anuncio": a["id"], "nombre": a["nombre"], "rol_campana": a["rol"],
                         "compras_48h": a["compras_48h"], "gasto_48h": a["gasto_48h"], "roas_48h": _roas(a["gasto_48h"], a["compras_48h"], aov)}
                        for a in sorted(gan, key=lambda a: -a["compras_48h"])]

    # 1) NUEVOS: todos los días mientras la oferta renueva
    futuras = [r for r in renov if (_fecha(r.get("inicio")) or ahora) > ahora and str(r.get("estado", "")).lower() not in TERMINADAS]
    nuevos_prog = [r for r in futuras if str(r.get("tipo") or "nuevos") in ("nuevos", "madre")]
    if not pega.get("pega"):
        out["nuevos"] = {"toca": False, "porque": pega.get("motivo") or "la oferta no renueva"}
    elif nuevos_prog:
        out["nuevos"] = {"toca": False, "porque": f"ya hay ronda de Nuevos para la próxima salida ({nuevos_prog[0].get('ronda')}, {nuevos_prog[0].get('estado')})",
                         "ronda": nuevos_prog[0].get("ronda")}
    elif not (v.get("en_ventana") or pega.get("toca_hoy")):
        out["nuevos"] = {"toca": False, "porque": v.get("ventana")}
    else:
        n += 1
        out["nuevos"] = {"toca": True, "ronda": f"R{n}", "anuncios": ANUNCIOS, "estructura": "CBO 1-1-10",
                         "presupuesto_usd": round(CBO_TICKETS * ticket), "corte_tickets": CBO_CORTE,
                         "nombre_campana": f"{t.get('mercado')} | {out['oferta']} | CBO Nuevos R{n} (1-1-10) | {CBO_TICKETS} tickets",
                         "porque": "R9 v2: una CBO de Nuevos por día con 10 conceptos distintos"}

    # 2) ITERACIONES
    rondas = rondas_iteraciones(t, roles, anuncios, raiz)
    pendientes = [r for r in rondas if str(r.get("estado")).lower() in ("produciendo", "programada")
                  or (_fecha(r.get("inicio")) and ahora - _fecha(r["inicio"]) < dt.timedelta(hours=IT_LECTURA_H))]
    fam_gan = defaultdict(float)
    for a in gan:
        fam_gan[a["familia"]] += a["compras_48h"]
    # Campeón: familia con más compras en 72 h en toda la oferta
    ventas_72 = defaultdict(float)
    hoy = ahora.astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    for a in anuncios:
        ventas_72[a["familia"]] += sum(c for f, (g, c) in a["por_dia"].items() if f >= (hoy - dt.timedelta(days=2)).isoformat())
    campeon = max(ventas_72, key=ventas_72.get) if ventas_72 and max(ventas_72.values()) > 0 else None
    fat = bool(campeon and fatigado([a for a in anuncios if a["familia"] == campeon], ahora))
    estado_fam = {}
    for fam in set(list(fam_gan) + ([campeon] if fat else [])):
        de_fam = [r for r in rondas if fam in (r.get("sobre") or []) and _fecha(r.get("inicio"))
                  and ahora - _fecha(r["inicio"]) >= dt.timedelta(hours=IT_LECTURA_H)]
        seguidas = 0
        for r in reversed(de_fam):
            if rindio(r, anuncios, corte_usd):
                break
            seguidas += 1
        descansa = None
        if seguidas >= IT_SIN_RENDIR and de_fam:
            hasta = _fecha(de_fam[-1]["inicio"]) + dt.timedelta(hours=IT_LECTURA_H) + dt.timedelta(days=IT_DESCANSO_D)
            if ahora < hasta:
                descansa = hasta.isoformat(timespec="minutes")
        estado_fam[fam] = {"compras_48h": fam_gan.get(fam, 0), "rondas_leidas": len(de_fam), "sin_rendir_seguidas": seguidas,
                           "descansa_hasta": descansa, "fatigada": fat and fam == campeon}
    elegibles = [f for f, e in estado_fam.items() if not e["descansa_hasta"] or e["fatigada"]]
    elegibles.sort(key=lambda f: (not estado_fam[f]["fatigada"] and f != campeon, -estado_fam[f]["compras_48h"]))
    elegidas = elegibles[:IT_FAMILIAS]
    it = {"campeon": campeon, "campeon_fatigado": fat, "familias": estado_fam}
    if not pega.get("pega"):
        it.update(toca=False, porque=pega.get("motivo") or "la oferta no renueva")
    elif pendientes:
        p = pendientes[-1]
        it.update(toca=False, porque=f"la ronda de iteraciones {p.get('ronda')} todavía no se leyó (empezó {p.get('inicio')}, estado {p.get('estado')}): se espera {IT_LECTURA_H} h de entrega")
    elif not estado_fam:
        it.update(toca=False, porque=f"no hay ganador (≥ {GAN_COMPRAS} compras con ROAS > {GAN_ROAS} en {GAN_HORAS} h) ni campeón fatigado")
    elif not elegidas:
        it.update(toca=False, porque="los ganadores están descansando: " + "; ".join(f"{f} hasta {e['descansa_hasta']}" for f, e in estado_fam.items()))
    elif not (v.get("en_ventana") or pega.get("toca_hoy")):
        it.update(toca=False, porque=v.get("ventana"))
    else:
        n += 1
        reparto = {elegidas[0]: ANUNCIOS} if len(elegidas) == 1 else dict(zip(elegidas, IT_REPARTO2))
        it.update(toca=True, ronda=f"R{n}", sobre=elegidas, reparto=reparto, estructura="CBO 1-1-10",
                  presupuesto_usd=round(CBO_TICKETS * ticket), corte_tickets=CBO_CORTE,
                  nombre_campana=f"{t.get('mercado')} | {out['oferta']} | CBO Iteraciones R{n} {'+'.join(elegidas)} (1-1-10) | {CBO_TICKETS} tickets",
                  porque=("campeón fatigado: se refresca con aperturas y ganchos nuevos; " if fat else "") +
                  "; ".join(f"{f}: {estado_fam[f]['compras_48h']:.0f} compras de ganadores en 48 h" for f in elegidas))
    out["iteraciones"] = it

    # 3) POCKETS
    en_pocket = {a["codigo"] for a in anuncios if a["rol"] == "pocket" and a["codigo"]}
    pocket_prog = {c for r in futuras if str(r.get("tipo")) == "pocket" for c in (r.get("codigos") or [])}
    sin_pocket = [a for a in gan if a["rol"] not in ("pocket", "cost_cap", "bid_cap") and a["codigo"] not in en_pocket | pocket_prog]
    vistos, por_fam = set(), defaultdict(list)
    for a in sorted(sin_pocket, key=lambda a: -a["compras_48h"]):
        if a["codigo"] in vistos:
            continue
        vistos.add(a["codigo"])
        por_fam[a["familia"]].append(a)
    pockets = []
    # Ahogados dentro de un pocket 1-1-N
    por_pocket = defaultdict(list)
    for a in anuncios:
        if a["rol"] == "pocket":
            por_pocket[a["campana"]].append(a)
    for cid, ads in por_pocket.items():
        tot = sum(x["gasto"] for x in ads)
        ini = _fecha((roles.get(cid) or {}).get("inicio"))
        if len(ads) < 2 or not tot or (ini and ahora - ini < dt.timedelta(hours=24)):
            continue
        for x in ads:
            if x["gasto"] / tot * 100 < PK_AHOGADO and x["compras"] >= 1 and x["gasto"] / x["compras"] <= ticket:
                pockets.append({"tipo": "ahogado", "codigos": [x["codigo"]], "familia": x["familia"], "estructura": "CBO 1-1-1",
                                "porque": f"{x['codigo']} tuvo {x['gasto'] / tot * 100:.0f} % del gasto del pocket con CPA US$ {x['gasto'] / x['compras']:.2f}: sale a su propio 1-1-1"})
    for fam, ads in por_fam.items():
        for i in range(0, len(ads), PK_MAX):
            grupo = ads[i:i + PK_MAX]
            g = sum(a["gasto_48h"] for a in grupo)
            c = sum(a["compras_48h"] for a in grupo)
            cpa = g / c if c else 0
            pres = round(max(PK_TICKETS * ticket, PK_CPA * cpa))
            cods = [a["codigo"] for a in grupo]
            pockets.append({"tipo": "ganador", "codigos": cods, "anuncios": [a["id"] for a in grupo], "familia": fam,
                            "estructura": f"CBO 1-1-{len(grupo)}", "presupuesto_usd": pres, "corte_tickets": PK_CORTE,
                            "nombre_campana": f"{t.get('mercado')} | {out['oferta']} | CBO POCKET {'+'.join(cods)} (1-1-{len(grupo)})",
                            "porque": f"familia {fam}: {', '.join(f'{a['codigo']} {a['compras_48h']:.0f} compras ROAS {_roas(a['gasto_48h'], a['compras_48h'], aov)}' for a in grupo)}; presupuesto = máx({PK_TICKETS} tickets, {PK_CPA} × CPA medio US$ {cpa:.2f})"})
    out["pockets"] = {"toca": bool(pockets), "lista": pockets,
                      "salida": v.get("salida"), "nota": "no hace falta producir: se duplica el anuncio (misma publicación) y sale a la próxima 00:00 del mercado"}

    # 4) MANUALES (cost cap y bid cap)
    en_manual = {a["codigo"] for a in anuncios if a["rol"] in ("cost_cap", "bid_cap") and a["codigo"]}
    for c in ((ficha.get("campanas") or [])):
        if isinstance(c, dict) and c.get("rol") in ("cost_cap", "bid_cap"):
            en_manual |= set(c.get("codigos") or [])
    sost = {}
    for a in anuncios:
        if a["rol"] == "pocket" and es_ganador(a["gasto_48h"], a["compras_48h"], aov) and a["codigo"] not in en_manual:
            if a["codigo"] not in sost or a["compras_48h"] > sost[a["codigo"]]["compras_48h"]:
                sost[a["codigo"]] = a
    sost_l = sorted(sost.values(), key=lambda a: -a["compras_48h"])
    manuales = []
    for i in range(0, len(sost_l) - MN_CADA + 1, MN_CADA):
        grupo = sost_l[i:i + MN_CADA]
        g = sum(a["gasto_48h"] for a in grupo)
        c = sum(a["compras_48h"] for a in grupo)
        cods = [a["codigo"] for a in grupo]
        manuales.append({"codigos": cods, "estructura": f"CBO 1-1-{MN_CADA}",
                         "cost_cap_usd": round(MN_COST * g / c, 2) if c else None, "bid_cap_usd": round(MN_BID * ticket, 2),
                         "cuenta": "segunda" if valor("cuentas.segunda_cuenta_lista", False) else "misma (la segunda cuenta no está lista)",
                         "backend_activo": str((t.get("backend") or {}).get("estado") or "") == "activo"})
    out["manual"] = {"toca": bool(manuales), "lista": manuales, "sostenidos": [a["codigo"] for a in sost_l],
                     "faltan": max(0, MN_CADA - len(sost_l) % MN_CADA) if len(sost_l) % MN_CADA else 0,
                     "porque": (f"{len(sost_l)} ganadores sostenidos en pocket (≥ {GAN_COMPRAS} compras y ROAS > {GAN_ROAS} en {GAN_HORAS} h dentro del pocket); "
                                f"cada {MN_CADA} sale una cost cap y una bid cap")}

    # 5) MADRE: quitar límites a los conjuntos viejos (2 días)
    quitar = []
    for r in renov:
        tipo = str(r.get("tipo") or "madre")
        ini = _fecha(r.get("inicio"))
        if tipo != "madre" or not r.get("conjunto_id") or str(r.get("estado", "")).lower() in TERMINADAS or r.get("limites_quitados"):
            continue
        if ini and ahora - ini >= dt.timedelta(days=MADRE_DIAS):
            quitar.append({"ronda": r.get("ronda"), "conjunto": r.get("conjunto"), "conjunto_id": r.get("conjunto_id")})
    out["madre"] = {"quitar_limites_a": quitar, "nota": "la madre no recibe más conjuntos (R9 v2)"}
    return out


def plan(libro: dict, ahora: dt.datetime, solo: str | None = None) -> list[dict]:
    pegas = {p["oferta"]: p for p in evaluar_pega(libro, ahora)}
    datos = {o.get("nombre"): o for o in N.calcular(libro, ahora)["ofertas"]}
    out = []
    for t in libro.get("tests") or []:
        nombre = t.get("oferta") or t.get("nombre")
        if solo and solo not in (t.get("nombre"), t.get("oferta")):
            continue
        if str(t.get("estado")) not in ("activo",):
            continue
        p = dict(pegas.get(nombre) or pegas.get(t.get("nombre")) or {"pega": False, "motivo": "sin datos"})
        o = datos.get(nombre) or datos.get(t.get("nombre")) or {}
        p["aov"] = (o.get("valor_comprador") or {}).get("neto_por_venta")   # valor neto por comprador (17-nov), no el ticket bruto
        out.append(plan_oferta(t, p, ahora, libro))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--libro", default=str(LIBRO))
    ap.add_argument("--ahora", help="fecha y hora con zona (para pruebas)")
    ap.add_argument("--oferta", help="solo esta oferta (nombre del test o de la oferta)")
    a = ap.parse_args()
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    libro = json.loads(Path(a.libro).read_text(encoding="utf-8"))
    json.dump({"ahora": ahora.isoformat(timespec="minutes"),
               "regla": "R9 v2 (dueño, 17-nov): CBO 1-1-10 aparte — Nuevos todos los días, Iteraciones según resultados; pockets por familia; cost cap y bid cap cada 5 ganadores sostenidos; la madre no recibe más conjuntos",
               "ofertas": plan(libro, ahora, a.oferta)}, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
