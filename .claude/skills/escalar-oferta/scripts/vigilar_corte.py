"""Regla de corte del test de una oferta nueva (firmada por el dueño el 2026-11-12).

- Test = el día 1 del mercado: desde el inicio de la campaña hasta las 00:00 siguientes, en la zona del inicio.
- Durante el test se apaga cuando el CPA llega a 1,5 tickets: gasto ≥ 1,5 × ticket × máx(1, ventas).
  Sin ventas es «gastó 1,5 tickets»; con 2 ventas, 3 tickets; y así.
- El ticket es el del PRODUCTO COMPLETO (dueño, 2026-11-13): el precio en USD más alto entre las tiendas del funnel
  (principal y niveles). En una oferta de un solo producto es el del front; con niveles de 13, 19 y 27 USD es 27.
- Al cerrar el día 1: con ventas pasa a post-lanzamiento (lo decide la revisión diaria, no esta regla).
  Sin ventas sigue en test hasta que venda o llegue a 1,5 tickets, y se avisa: Meta casi no entregó.

La aplica la vigilancia de cada hora (references/04-vigilancia.md). Este script solo decide: no lee Meta ni Impultienda
y no apaga nada.

Uso:
  python3 .claude/skills/escalar-oferta/scripts/vigilar_corte.py --lectura <lectura.json> [--registrar] [--ahora <ISO>]

lectura.json (lo arma el agente con ads_get_ad_entities y ads_get_dataset_stats, recién leído):
  {
    "leido": "2026-11-13T09:05-03:00",
    "campanas": {"<id>": {"gasto_usd": 18.4, "compras_meta": 0, "estado": "ACTIVE"}},
    "pixel_compras": {"<id del píxel>": 0},          (SOLO las del navegador: con CAPI el total cuenta cada compra dos veces)
    "ventas_tienda": {"<nombre del test>": 3},    (opcional: ventas leídas en Impul Pay, si son más que las del libro)
    "embudo": {"<nombre del test>": {"ctr_pct": 1.3, "pagina_a_pago_pct": 9.5, "checkouts": 4}}   (para la segunda oportunidad)
  }
Ventas que cuenta: la mayor entre la tienda, Meta y el píxel (la más favorable a la oferta). Antes de apagar, el agente
confirma en Impul Pay; si allí hay más ventas, vuelve a correr el script con ventas_tienda.

Salida (JSON por stdout), un renglón por test activo o programado:
  APAGAR            en test y con el CPA en 1,5 tickets del completo o más → confirmar en Impul Pay y pausar
  SEGUNDA_OPORTUNIDAD  llegó al corte SIN ventas pero el anuncio y la página funcionan (CTR ≥ 1 %, ≥ 8 % de las visitas
                    al pago, ≥ 3 pagos iniciados): +0,5 ticket una sola vez (dueño, 13-nov). Anotar en el libro
                    `segunda_oportunidad` y, si el diagnóstico es «checkout», probarlo y arreglarlo antes
  CERCA             en test y con el gasto en el 80 % del corte o más
  SIGUE             en test, lejos del corte
  ENTREGA_BAJA      terminó el día 1 sin ventas y sin llegar al corte: sigue en test y se avisa al dueño
  POST_LANZAMIENTO  terminó el día 1 con ventas: esta regla ya no corre (02-decidir.md)
  SIN_PAUTA         la campaña todavía no arrancó
  SIN_PRECIO        falta el precio en USD de las tiendas en la ficha → avisar al dueño
  SIN_LECTURA       falta la lectura de Meta de alguna campaña del test
Con --registrar agrega la vuelta a ofertas/_funnels/vigilancia.jsonl.
Con --solo "A,B" (vuelta rápida de 15 min, dueño 14-nov) decide solo esos tests y marca la vuelta como "rapida".
"""
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
VECES_TICKET = valor("test.corte_tickets", 1.5)
AVISO_CERCA = valor("test.aviso_cerca", 0.8)
SEGUNDA = valor("test.segunda_oportunidad", {"extra_tickets": 0.5, "ctr_min_pct": 1.0, "pagina_a_pago_min_pct": 8.0, "checkouts_min": 3, "solo_sin_ventas": True})
CORTES_POR_ROL = {k: float(v) for k, v in valor("cortes_por_rol", {"nuevos": 1.5, "iteraciones": 1.5, "test_variaciones": 1.5, "pocket": 1.0}).items()
                  if not str(k).startswith("_") and isinstance(v, (int, float))}


def corte_tickets_de(conf: dict | None) -> float | None:
    """Corte propio de una campaña: su `corte_tickets` si lo tiene; si no, el de su rol en reglas.json → cortes_por_rol.
    None = esa campaña no se corta por su cuenta (la madre, las manuales). Lo usan la vigilancia y el respaldo en la nube."""
    conf = conf or {}
    if conf.get("corte_tickets") is not None:
        return float(conf["corte_tickets"])
    return CORTES_POR_ROL.get(str(conf.get("rol") or ""))


def ticket_corte(ficha):
    """Precio en USD del producto completo: el más alto entre las tiendas del funnel (principal y niveles)."""
    precios = [float(t["precio"]["usd"]) for t in (ficha.get("tiendas") or [])
               if isinstance(t, dict) and isinstance(t.get("precio"), dict) and isinstance(t["precio"].get("usd"), (int, float)) and t["precio"]["usd"] > 0]
    return max(precios) if precios else None


def campanas_del_test(t):
    ids = [str(c.get("id")) for c in (t.get("ficha", {}).get("campanas") or []) if c.get("id")]
    if t.get("campana") and str(t["campana"]) not in ids:
        ids.insert(0, str(t["campana"]))
    return ids


def fin_dia1(inicio):
    """00:00 siguientes al inicio, en la zona del inicio (día 1 del mercado)."""
    d = dt.datetime.fromisoformat(inicio)
    return dt.datetime.combine(d.date() + dt.timedelta(days=1), dt.time(0), tzinfo=d.tzinfo)


SOBREGASTO_META = 1.75   # Meta puede gastar hasta 175 % del presupuesto diario en un día


def presupuesto_dia(t, leidas):
    """Presupuesto diario en USD de las campañas del test: el de la lectura de Meta si vino, si no el de la ficha."""
    de_meta = [float(c["presupuesto_usd"]) for c in leidas if isinstance(c.get("presupuesto_usd"), (int, float))]
    if de_meta:
        return sum(de_meta)
    f = t.get("ficha") or {}
    camps = [c for c in (f.get("campanas") or []) if isinstance(c, dict)] + ([f["campana"]] if isinstance(f.get("campana"), dict) else [])
    for k in ("presupuesto_diario_usd", "presupuesto_usd_dia"):
        vals = [float(c[k]) for c in camps if isinstance(c.get(k), (int, float))]
        if vals:
            return max(vals)
    return None


def backend_anticipado(t, ventas, gasto, corte, presupuesto, ahora, fin):
    """R3b (dueño, 14-nov): con ventas en el test y el corte ya imposible antes del fin del día 1, el backend se arma YA
    (embudo apagado) y se activa al cierre del test, para que ninguna venta de backend caiga dentro del test."""
    if not ventas or not presupuesto or fin is None or ahora >= fin:
        return None
    b = t.get("backend") if isinstance(t.get("backend"), dict) else {}
    if str(b.get("estado") or "") in ("activo", "armando", "listo"):
        return None
    horas = (fin - ahora).total_seconds() / 3600
    tope = gasto + presupuesto * SOBREGASTO_META * min(1.0, horas / 24)
    if tope < corte:
        return {"activar_desde": fin.isoformat(), "gasto_tope_usd": round(tope, 2),
                "porque": f"Aunque Meta gaste el 175 % de US$ {presupuesto:.0f} en las {horas:.1f} h que quedan, llega a US$ {tope:.2f} < corte US$ {corte:.2f}: el test ya no se pierde."}
    return None


def cortes_por_campana(t, ids, leidas, ticket, solo_con_corte=False):
    """Réplica de oferta validada (dueño, 15-nov): cada campaña de ficha.campanas con `corte_tickets` se corta sola
    (pocket 1-1-1 a 1 ticket, CBO de variaciones a 1,5): CPA de ESA campaña (gasto ÷ compras de Meta de esa campaña)
    ≥ corte_tickets × ticket del completo → se apaga esa campaña. Sin `corte_tickets` en ninguna, devuelve None."""
    conf = {str(c.get("id")): c for c in (t.get("ficha", {}).get("campanas") or []) if isinstance(c, dict) and c.get("id")}
    if not any(corte_tickets_de(c) is not None for c in conf.values()):
        return None
    filas, apagar, cerca = [], [], []
    for i, c in zip(ids, leidas):
        propio = corte_tickets_de(conf.get(i))
        if solo_con_corte and propio is None:
            continue   # post-lanzamiento: la madre y las manuales no se cortan acá
        k = propio if propio is not None else VECES_TICKET
        g = round(float(c.get("gasto_usd") or 0), 2)
        v = int(c.get("compras_meta") or 0)
        corte = round(k * ticket * max(1, v), 2)
        activa = str(c.get("estado", "")).upper() == "ACTIVE"
        filas.append({"id": i, "rol": (conf.get(i) or {}).get("rol"), "corte_tickets": k, "gasto_usd": g, "compras_meta": v,
                      "corte_usd": corte, "activa": activa})
        if activa and g >= corte:
            apagar.append(i)
        elif activa and g >= AVISO_CERCA * corte:
            cerca.append(i)
    txt = "; ".join(f"{f['rol'] or f['id']}: US$ {f['gasto_usd']:.2f}, {f['compras_meta']} compras, corte US$ {f['corte_usd']:.2f} ({f['corte_tickets']} tickets)" for f in filas)
    activas = [f["id"] for f in filas if f["activa"]]
    if apagar and set(apagar) >= set(activas) and not solo_con_corte:
        return {"decision": "APAGAR", "campanas_detalle": filas, "apagar_campanas": apagar, "porque": "Corte por campaña: " + txt}
    if apagar:
        return {"decision": "APAGAR_CAMPANA", "campanas_detalle": filas, "apagar_campanas": apagar,
                "porque": "Corte por campaña (pausar solo las de apagar_campanas): " + txt}
    return {"decision": "CERCA" if cerca else "SIGUE", "campanas_detalle": filas, "porque": "Corte por campaña: " + txt}


def limites_por_campana(t: dict, ahora: dt.datetime) -> list[dict]:
    """Campañas de un test que se cortan solas por su cuenta, con lo que la nube necesita para decidir igual que esta
    vigilancia: [{campana, tickets, ticket_usd, inicio}]. Vale en el día 1 (réplicas) y después (R9 v2: Nuevos, Iteraciones,
    pockets). Genérico: cualquier campaña de ficha.campanas con corte propio o con rol en cortes_por_rol entra sola."""
    ficha = t.get("ficha") or {}
    ticket = ticket_corte(ficha)
    if not ticket:
        return []
    out = []
    for c in ficha.get("campanas") or []:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        k = corte_tickets_de(c)
        if k is None or str(c.get("estado") or "ACTIVE").split(" ")[0] not in ("ACTIVE", "IN_PROCESS", "WITH_ISSUES", ""):
            continue
        out.append({"campana": str(c["id"]), "rol": c.get("rol"), "tickets": k, "ticket_usd": float(ticket),
                    "inicio": c.get("inicio") or c.get("detectada") or t.get("inicio")})
    return out


def decidir(t, lectura, ahora):
    ficha = t.get("ficha") or {}
    ids = campanas_del_test(t)
    ticket = ticket_corte(ficha)
    pixel = str((ficha.get("pixel") or {}).get("id") or "")
    inicio = t.get("inicio")
    fin = fin_dia1(inicio) if inicio else None
    base = {"test": t.get("nombre"), "mercado": t.get("mercado"), "campanas": ids, "ticket_corte_usd": ticket,
            "inicio": inicio, "fin_test": fin.isoformat() if fin else None}
    if inicio and ahora < dt.datetime.fromisoformat(inicio):
        return {**base, "fase": "programada", "decision": "SIN_PAUTA", "porque": f"Arranca {inicio}."}
    faltan = [i for i in ids if i not in lectura.get("campanas", {})]
    if not ids or faltan:
        return {**base, "decision": "SIN_LECTURA", "porque": f"Falta la lectura de Meta de {', '.join(faltan) or 'la campaña'}."}
    leidas = [lectura["campanas"][i] for i in ids]
    gasto = round(sum(float(c.get("gasto_usd") or 0) for c in leidas), 2)
    principales = [v for v in (t.get("ventas") or []) if str(v.get("tipo") or "").lower() not in ("upsell", "downsell", "bump", "rebaja")]
    v_tienda = max(len(principales), int((lectura.get("ventas_tienda") or {}).get(t.get("nombre"), 0)))
    v_meta = sum(int(c.get("compras_meta") or 0) for c in leidas)
    v_pixel = int(lectura.get("pixel_compras", {}).get(pixel) or 0) if pixel else 0
    ventas = max(v_tienda, v_meta, v_pixel)
    dia1 = fin is None or ahora < fin
    fase = "test" if dia1 or ventas == 0 else "post-lanzamiento"
    activas = [i for i, c in zip(ids, leidas) if str(c.get("estado", "")).upper() == "ACTIVE"]
    base.update(fase=fase, gasto_usd=gasto, ventas=ventas, ventas_tienda=v_tienda, compras_meta=v_meta, compras_pixel=v_pixel,
                cpa_usd=round(gasto / ventas, 2) if ventas else None, campanas_activas=activas)
    if fase == "post-lanzamiento":
        # R9 v2 (dueño, 17-nov): las CBO diarias aparte (Nuevos, Iteraciones, pockets nuevos) se cortan solas aunque la oferta
        # ya pasó el test: CPA de ESA campaña ≥ corte_tickets × ticket → se pausa solo esa campaña.
        if ticket:
            pc = cortes_por_campana(t, ids, leidas, ticket, solo_con_corte=True)
            if pc is not None and pc.get("decision") == "APAGAR_CAMPANA":
                return {**base, **pc}
        return {**base, "decision": "POST_LANZAMIENTO",
                "porque": f"Terminó el día 1 con {ventas} {'venta' if ventas == 1 else 'ventas'}: la decide la revisión diaria."}
    if not ticket:
        return {**base, "decision": "SIN_PRECIO", "porque": "Falta el precio en USD de las tiendas en ficha.tiendas."}
    por_campana = cortes_por_campana(t, ids, leidas, ticket)
    if por_campana is not None:
        return {**base, **por_campana}
    extra = float(SEGUNDA.get("extra_tickets", 0.5)) if isinstance(t.get("segunda_oportunidad"), dict) else 0.0
    corte = round((VECES_TICKET + extra) * ticket * max(1, ventas), 2)
    base["corte_usd"] = corte
    cpa_txt = f"CPA US$ {gasto / ventas:.2f}" if ventas else "sin ventas"
    tickets = (gasto / max(1, ventas)) / ticket
    detalle = f"US$ {gasto:.2f} gastados, {ventas} {'venta' if ventas == 1 else 'ventas'} ({cpa_txt}, {tickets:.2f} tickets de US$ {ticket:.2f}); corte US$ {corte:.2f}."
    if gasto >= corte:
        emb = (lectura.get("embudo") or {}).get(t.get("nombre")) or {}
        sin_ventas_ok = ventas == 0 or not SEGUNDA.get("solo_sin_ventas", True)
        senales = (float(emb.get("ctr_pct") or 0) >= SEGUNDA["ctr_min_pct"] and float(emb.get("pagina_a_pago_pct") or 0) >= SEGUNDA["pagina_a_pago_min_pct"]
                   and int(emb.get("checkouts") or 0) >= SEGUNDA["checkouts_min"])
        if not extra and sin_ventas_ok and senales:
            nuevo = round((VECES_TICKET + float(SEGUNDA["extra_tickets"])) * ticket * max(1, ventas), 2)
            return {**base, "decision": "SEGUNDA_OPORTUNIDAD", "corte_nuevo_usd": nuevo,
                    "porque": f"{detalle} Pero el anuncio y la página funcionan (CTR {emb.get('ctr_pct')} %, {emb.get('pagina_a_pago_pct')} % al pago, {emb.get('checkouts')} pagos iniciados): +{SEGUNDA['extra_tickets']} ticket, corte nuevo US$ {nuevo:.2f}."}
        return {**base, "decision": "APAGAR", "porque": detalle + (" (ya tuvo su segunda oportunidad)" if extra else "")}
    if not dia1:
        return {**base, "decision": "ENTREGA_BAJA", "porque": "Terminó el día 1 sin ventas y sin llegar al corte: Meta casi no entregó. " + detalle}
    ba = backend_anticipado(t, ventas, gasto, corte, presupuesto_dia(t, leidas), ahora, fin)
    if ba:
        base["backend_anticipado"] = ba
    if gasto >= AVISO_CERCA * corte:
        return {**base, "decision": "CERCA", "porque": detalle}
    return {**base, "decision": "SIGUE", "porque": detalle}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lectura", required=True)
    ap.add_argument("--libro", default=str(LIBRO))
    ap.add_argument("--registrar", action="store_true")
    ap.add_argument("--ahora", help="fecha y hora con zona (para pruebas); por defecto, ahora")
    ap.add_argument("--solo", help="vuelta rápida (14-nov): nombres de los tests a decidir, separados por coma; el resto no se toca")
    a = ap.parse_args()
    libro = json.loads(Path(a.libro).read_text())
    lectura = json.loads(Path(a.lectura).read_text())
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    tests = [t for t in libro.get("tests", []) if t.get("estado") in ("activo", "programado")]
    if a.solo:
        solo = {x.strip() for x in a.solo.split(",") if x.strip()}
        tests = [t for t in tests if t.get("nombre") in solo]
    salida = {"leido": lectura.get("leido"), "ahora": ahora.isoformat(timespec="minutes"),
              "regla": "día 1: CPA ≥ 1,5 tickets del producto completo (sin ventas, gastar 1,5 tickets) → apagar (dueño, 2026-11-12; ticket del completo, 2026-11-13)",
              "tests": [decidir(t, lectura, ahora) for t in tests]}
    if a.solo:
        salida["vuelta"] = "rapida"
    if a.registrar:
        with REGISTRO.open("a") as f:
            f.write(json.dumps(salida, ensure_ascii=False) + "\n")
    json.dump(salida, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
