"""Escala POR CAMPAÑA con el AOV de la tienda (criterio del dueño, 16-nov; reemplaza la escala simétrica por oferta del 14-nov).

Por qué cambió (16-nov): el dueño escaló a mano todo el día porque la escala miraba UNA campaña por oferta (la del libro) y le
atribuía el ROAS de toda la tienda: el pocket, las variaciones y las réplicas quedaban sin nadie, y la CBO original de Todo en
Orden daba «ROAS 6,2 con 0 compras» con ventas que traían las otras. Su regla, en sus palabras: «estoy surfeando lo que tiene buen
CPA y mantiene también ROAS, ROAS comparado con el AOV de la tienda, y siempre trato de escalar por arriba de 1,8 porque tiene
brecha para escalar todavía, pero a ojo». Detalle y análisis: docs/criterio-de-escala-2026-11-16.md.

17-nov (dueño: «usar neto», puntos 1-3 de docs/ruido-y-confianza-2026-11-17.md): todo en NETO y con rango.
  · Valor por comprador = el del sistema (dashboard.negocio.neto_por_comprador_ventana: neto de 7 días, 14 con < 50 compradores,
    si no la historia; no cruza el último cambio del embudo). Los umbrales se pasaron a neto con equivalencia exacta (neto ≈ 92 %
    del bruto): 1,8 → 1,65 · 1,5 → 1,4 · 3 → 2,75. Donde abajo dice «AOV» o un umbral bruto, vale el neto.
  · ROAS estimado = compras desde el cambio acercadas a lo que ya se sabe (sus 3 días anteriores 50/30/20; si no vendió, la oferta
    en 7 días; si tampoco, el empate) como si fueran 3 compras previas. Para SUBIR además el piso del rango (80 %) ≥ 1,0: aun en el
    caso pesimista razonable no pierde. Con muchas compras manda lo propio; con 2, lo previo.

Cada campaña activa se decide sola, con lo que pasó DESDE SU ÚLTIMO CAMBIO de presupuesto (lo haya hecho el sistema o el dueño):
  ROAS con AOV = compras que Meta le atribuye a ESA campaña × AOV de la tienda (bruto con bump y upsells ÷ compradores) ÷ gasto.
  (El valor de compra de Meta se queda corto y el ROAS de la tienda mezcla campañas; si la oferta tiene menos de 5 compradores
  se usa el AOV de la madre si es réplica, o el ticket del producto completo.)

  SURFEAR      ROAS con AOV ≥ 1,8, ≥ 2 compras y ≥ 3 h desde el cambio, por debajo de US$ 500/día. La dosis, que el dueño
               hacía a ojo, sale de la muestra: 2-3 compras +20 %, 4-7 +30 %, 8 o más +40 %; ROAS ≥ 3 suma +10 (tope +50 %).
  SUBIR_24H    ROAS con AOV ≥ 1,8 con US$ 500/día o más, ≥ 2 compras y ≥ 24 h desde el cambio → +30 %.
  BAJAR        ROAS con AOV < 1,5 con ≥ 3 h y (≥ 2 compras o ≥ 1,5 tickets gastados) → −30 %, nunca bajo el presupuesto inicial.
  NO_GASTA     iba a subir, pero en las últimas 6 h (de día en el mercado) gastó menos del 40 % de lo que le tocaba: con más
               presupuesto no cambia nada (lo que falta son creativos o subasta). Se avisa, no se toca.
  TARDE        iba a subir, pero quedan menos de 2 h del día del mercado: la suba solo cargaría el presupuesto de mañana sin datos.
  MANTENER     ROAS con AOV entre 1,5 y 1,8, o falta tiempo o compras.
  EN_TEST      la oferta está en su día 1 de test: no se toca (lo decide el corte del test).
  CONGELADA    la oferta está congelada por R16.
  SIN_DATOS    menos de US$ 3 gastados desde el último cambio.
Números redondos siempre. Este script solo decide: no toca Meta. Los números salen de reglas.json → escala.por_campana.

Uso:
  python3 escalar_presupuesto.py --auto [--registrar]          (arma la lectura sola: libro + fotos de la nube + cambios registrados)
  python3 escalar_presupuesto.py --lectura <json> [--registrar] (lectura a mano, misma forma que arma --auto; ver `armar_lectura`)
Con --registrar agrega la salida a ofertas/_funnels/escala.jsonl (lo lee el panel: línea de tiempo y decisiones por campaña).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402
from congelamiento import congelada  # noqa: E402
import fotos_campanas as FC  # noqa: E402
from control_previo import ZONA as ZONA_MERCADO  # noqa: E402   (zona horaria de cada mercado)

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
from dashboard import negocio as N  # noqa: E402   (valor neto por comprador y ROAS estimado con rango: los mismos que el panel)
REGISTRO = RAIZ / "ofertas" / "_funnels" / "escala.jsonl"

P = "escala.por_campana."
ROAS_SURF = valor(P + "roas_surf", 1.65)   # neto (= 1,8 bruto); 17-nov: todo en neto
PISO_SUBIR = valor(P + "piso_subir", 1.0)   # 17-nov: para subir, el piso del rango (80 %) tiene que cubrir el empate
FUERZA_PREVIA = valor(P + "fuerza_previa_compras", 3.0)
COMPRAS_MIN = valor(P + "compras_minimas", 2)
HORAS_SURF = valor(P + "horas_entre_cambios", 3)
HORAS_24 = valor("escala.horas_24", 24)
GASTO_MIN_USD = valor(P + "gasto_minimo_usd", 3.0)
PASOS = [tuple(x) for x in valor(P + "pasos", [[2, 0.2], [4, 0.3], [8, 0.4]])]
ROAS_ALTO, EXTRA_ALTO, PASO_MAX = valor(P + "roas_alto", 2.75), valor(P + "extra_roas_alto", 0.1), valor(P + "paso_max", 0.5)
SURF_HASTA_USD = valor("escala.surf_hasta_usd", 500)
SUBA_24H = valor("escala.suba_24h", 0.30)
ROAS_BAJAR = valor(P + "roas_bajar", 1.4)
BAJAR = valor("escala.bajar", 0.30)
BAJAR_GASTO_TICKETS = valor("escala.bajar_gasto_tickets", 1.5)
HORAS_FIN_DIA = valor(P + "horas_antes_fin_dia_sin_subir", 2)
RITMO_HORAS, RITMO_MIN = valor(P + "ritmo_horas", 6), valor(P + "ritmo_minimo", 0.4)
RITMO_DESDE, RITMO_HASTA = valor(P + "ritmo_desde_hora", 9), valor(P + "ritmo_hasta_hora", 21)
AOV_MIN_VENTAS = valor(P + "aov_minimo_compradores", 5)
NETO_DE_BRUTO = 0.92   # respaldo sin valor neto: el bruto de Meta pasado a neto (comisión de la tienda ≈ 8 %)
VENTANA_DIA = valor(P + "ventana_desde_medianoche_mercado", True)   # dueño, 16-nov: el día nuevo del mercado abre la cuenta de nuevo
SEGUNDA_CUENTA_USD = valor("cuentas.segunda_cuenta_desde_usd", 200)
SEGUNDA_CUENTA_LISTA = valor("cuentas.segunda_cuenta_lista", False)
REGLA = ("escala por campaña en NETO (dueño, 16-nov; neto y rango desde 17-nov): ROAS neto est. ≥ 1,65 con piso del rango ≥ 1 → surfeo cada 3 h "
         "(+20/30/40 % según compras, +10 con ROAS ≥ 2,75) hasta US$ 500/día, después +30 %/24 h; < 1,4 → −30 % (nunca bajo el inicial); "
         "el ROAS se acerca a los 3 días anteriores de la campaña; no se sube si no gasta ni al final del día del mercado")


def redondo(x: float) -> int:
    """Presupuestos siempre en números redondos (dueño, 13-nov): dólares enteros, la mitad hacia arriba."""
    return int(x + 0.5)


def paso_surf(compras: int, roas: float) -> float:
    p = 0.0
    for minimo, pct in PASOS:
        if compras >= minimo:
            p = pct
    if roas >= ROAS_ALTO:
        p += EXTRA_ALTO
    return round(min(p, PASO_MAX), 3)


def _hora_mercado(o: dict, ahora: dt.datetime) -> float | None:
    off = o.get("utc_offset_mercado_h")
    if off is None:
        return None
    t = ahora.astimezone(dt.timezone(dt.timedelta(hours=float(off))))
    return t.hour + t.minute / 60


def decidir(o: dict, ahora: dt.datetime) -> dict:
    base = {k: o.get(k) for k in ("oferta", "campana", "nombre", "rol", "presupuesto_usd")}
    if o.get("congelada"):
        c = o["congelada"]
        return {**base, "decision": "CONGELADA", "porque": f"Oferta congelada hasta {c.get('hasta')}: no se sube ni se baja ({c.get('motivo', '')})."}
    if o.get("fase") == "test":
        return {**base, "decision": "EN_TEST", "porque": "La oferta está en el día 1 de test: el presupuesto no se toca (lo decide el corte del test)."}
    pres = float(o.get("presupuesto_usd") or 0)
    desde = o.get("desde_cambio") or {}
    gasto = float(desde.get("gasto_usd") or 0)
    compras = int(desde.get("compras") or 0)
    aov = o.get("aov_usd")   # valor NETO por comprador (17-nov; el nombre del campo queda por compatibilidad)
    est = N.roas_estimado(compras, gasto, float(aov) if aov else None, o.get("cpa_previo_usd"), FUERZA_PREVIA)
    roas = est["roas"]
    if roas is None and gasto > 0:
        roas = float(desde.get("valor_meta_usd") or 0) * NETO_DE_BRUTO / gasto
    roas_meta = float(desde.get("valor_meta_usd") or 0) / gasto if gasto > 0 else None
    ult = dt.datetime.fromisoformat(o["ultimo_cambio"]) if o.get("ultimo_cambio") else None
    horas = (ahora - ult).total_seconds() / 3600 if ult else 999.0
    if o.get("ventana") == "día del mercado":
        base["ventana"] = "desde la medianoche del mercado"
    base.update(roas_crudo=est["crudo"], roas_piso=est["piso"], roas_techo=est["techo"], cpa_previo_usd=o.get("cpa_previo_usd"),
                cpa_previo_fuente=o.get("cpa_previo_fuente"))
    base.update(roas_aov=round(roas, 2) if roas is not None else None, roas_meta=round(roas_meta, 2) if roas_meta is not None else None,
                aov_usd=aov, aov_fuente=o.get("aov_fuente"), compras_desde_cambio=compras, gasto_desde_cambio=round(gasto, 2),
                cpa_desde_cambio=round(gasto / compras, 2) if compras else None, horas_desde_cambio=round(horas, 1),
                ultimo_cambio=o.get("ultimo_cambio"), exacto=desde.get("exacto"))
    if pres <= 0:
        return {**base, "decision": "SIN_DATOS", "porque": "Falta el presupuesto actual de la campaña."}
    if gasto < GASTO_MIN_USD or roas is None:
        return {**base, "decision": "SIN_DATOS", "porque": f"Solo US$ {gasto:.2f} gastados desde el último cambio: todavía no se decide."}
    rango = f", rango {est['piso']:.2f}–{est['techo']:.2f}" if est["piso"] is not None else ""
    rtxt = (f"ROAS neto est. {roas:.2f} ({compras} compra{'s' if compras != 1 else ''} × US$ {aov or '—'} ÷ US$ {gasto:.0f} = {est['crudo'] if est['crudo'] is not None else '—'}"
            f", acercado a {o.get('cpa_previo_fuente') or 'lo previo'}{rango})")
    inicial = float(o.get("presupuesto_inicial_usd") or 0)
    ticket = float(o.get("ticket_usd") or 0)

    # 1) bajada
    if roas < ROAS_BAJAR:
        muestra = horas >= HORAS_SURF and (compras >= COMPRAS_MIN or (ticket > 0 and gasto >= BAJAR_GASTO_TICKETS * ticket))
        if not muestra:
            return {**base, "decision": "MANTENER", "porque": f"{rtxt}, bajo {ROAS_BAJAR}, pero con poca muestra ({horas:.1f} h desde el cambio): se espera."}
        if inicial and pres <= inicial:
            return {**base, "decision": "MANTENER", "porque": f"{rtxt}, bajo {ROAS_BAJAR}, pero ya está en su presupuesto inicial (US$ {inicial:g}): nunca baja de ahí. Si pierde, la corta R4."}
        nuevo = max(redondo(pres * (1 - BAJAR)), redondo(inicial)) if inicial else redondo(pres * (1 - BAJAR))
        return {**base, "decision": "BAJAR", "presupuesto_nuevo_usd": nuevo, "cambio_pct": round(nuevo / pres - 1, 3),
                "porque": f"{rtxt} en {horas:.1f} h desde el último cambio, bajo {ROAS_BAJAR}: baja a US$ {nuevo}"
                          + (" (piso: presupuesto inicial)" if inicial and nuevo == redondo(inicial) else "") + "."}

    if roas < ROAS_SURF:
        return {**base, "decision": "MANTENER", "porque": f"{rtxt}: entre {ROAS_BAJAR} y {ROAS_SURF}, no se sube ni se baja."}

    # 2) subir: muestra, tiempo, hora del mercado y ritmo de gasto
    if compras < COMPRAS_MIN:
        return {**base, "decision": "MANTENER", "porque": f"{rtxt} con {compras} compra desde el cambio: hacen falta {COMPRAS_MIN} para subir."}
    if est["piso"] is not None and est["piso"] < PISO_SUBIR:
        return {**base, "decision": "MANTENER", "porque": f"{rtxt}: el piso del rango ({est['piso']:.2f}) no cubre el empate ({PISO_SUBIR:g}); con más compras se sabe si es suerte."}
    espera = HORAS_SURF if pres < SURF_HASTA_USD else HORAS_24
    if horas < espera:
        return {**base, "decision": "MANTENER", "porque": f"{rtxt}: pasaron {horas:.1f} h de las {espera} que pide la próxima suba."}
    hm = _hora_mercado(o, ahora)
    if hm is not None and hm >= 24 - HORAS_FIN_DIA:
        return {**base, "decision": "TARDE", "porque": f"{rtxt}: daría para subir, pero son las {int(hm):02d}:{int(hm % 1 * 60):02d} en el mercado; la suba solo cargaría el día de mañana. Se decide en la primera vuelta del día."}
    g6 = o.get("gasto_ultimas_horas")
    if g6 is not None and hm is not None and RITMO_DESDE <= hm <= RITMO_HASTA and pres > 0:
        ritmo = g6 / (pres * RITMO_HORAS / 24)
        base["ritmo"] = round(ritmo, 2)
        if ritmo < RITMO_MIN:
            return {**base, "decision": "NO_GASTA", "porque": f"{rtxt}, pero en las últimas {RITMO_HORAS} h gastó US$ {g6:.0f}, el {round(ritmo * 100)} % de lo que le tocaba: con más presupuesto no cambia nada. Mirar creativos o subasta."}
    if pres >= SURF_HASTA_USD:
        return {**base, "decision": "SUBIR_24H", "presupuesto_nuevo_usd": redondo(pres * (1 + SUBA_24H)), "cambio_pct": SUBA_24H,
                "porque": f"{rtxt} con US$ {pres:g}/día (desde US$ {SURF_HASTA_USD:g} se sube cada 24 h): +{round(SUBA_24H * 100)} %."}
    p = paso_surf(compras, roas)
    return {**base, "decision": "SURFEAR", "presupuesto_nuevo_usd": redondo(pres * (1 + p)), "cambio_pct": p,
            "porque": f"Surfeo: {rtxt} en {horas:.1f} h desde el último cambio: +{round(p * 100)} % ({compras} compras"
                      + (f", ROAS ≥ {ROAS_ALTO:g}" if roas >= ROAS_ALTO else "") + ")."}


# ---------- lectura automática ----------

def _offset_h(texto) -> float | None:
    d = FC._fecha(texto)
    if not d or not d.utcoffset():
        return None if not d else 0.0
    return d.utcoffset().total_seconds() / 3600


def cpa_previo_de(t: dict, cid: str, ahora: dt.datetime, valor_neto: float | None, zona) -> tuple[float | None, str]:
    """Lo que ya se sabe de la campaña antes de hoy, para acercar el ROAS de pocas horas (17-nov, puntos 2 y 3):
    sus 3 días anteriores pesando 50/30/20; si no vendió, los 7 días anteriores de toda la oferta; si tampoco, el empate."""
    hoy = ahora.astimezone(zona).date()
    por: dict[str, dict[str, list[float]]] = {}
    for h in t.get("historial_diario") or []:
        if isinstance(h, dict) and str(h.get("fecha") or "") < hoy.isoformat():
            d = por.setdefault(str(h.get("campana")), {}).setdefault(str(h.get("fecha"))[:10], [0.0, 0.0])
            d[0] += float(h.get("gasto_usd") or 0)
            d[1] += float(h.get("compras_meta") or 0)
    propios = [tuple(por.get(cid, {}).get((hoy - dt.timedelta(days=i)).isoformat(), (0.0, 0.0))) for i in (1, 2, 3)]
    c = N.cpa_ponderado(propios)
    if c:
        return c, "sus 3 días anteriores"
    g = sum(v[0] for dias in por.values() for f, v in dias.items() if f >= (hoy - dt.timedelta(days=7)).isoformat())
    n = sum(v[1] for dias in por.values() for f, v in dias.items() if f >= (hoy - dt.timedelta(days=7)).isoformat())
    if n > 0:
        return g / n, "la oferta en 7 días"
    return (valor_neto, "el empate") if valor_neto else (None, "sin previa")


def armar_lectura(libro: dict, ahora: dt.datetime, lista_fotos: list[dict] | None = None, lista_eventos: list[dict] | None = None) -> dict:
    """Una entrada por campaña ACTIVA (según la última foto) de cada oferta activa del libro."""
    lista_fotos = FC.fotos() if lista_fotos is None else lista_fotos
    lista_eventos = FC.eventos() if lista_eventos is None else lista_eventos
    calc = N.calcular(libro, ahora)
    por_nombre = {o["nombre"]: o for o in calc.get("ofertas") or []}
    tests = {str(t.get("oferta") or t.get("nombre")): t for t in libro.get("tests") or [] if isinstance(t, dict)}
    nombres = FC.campanas_del_libro(libro)
    out = []
    for cid, info in nombres.items():
        t = tests.get(str(info.get("oferta")))
        o = por_nombre.get(str(info.get("oferta")))
        if not t or not o or str(t.get("estado") or "").lower() not in ("activo", "activa"):
            continue
        uf = FC.ultima_foto(cid, lista_fotos)
        if not uf or uf.get("e") != "ACTIVE":
            continue
        evs = [e for e in lista_eventos if str(e.get("campana")) == cid and e.get("tipo") == "presupuesto"]
        ficha_c = next((c for c in ((t.get("ficha") or {}).get("campanas") or []) if str(c.get("id")) == cid), {})
        ult = FC._fecha(evs[-1]["cuando"]) if evs else (FC._fecha(ficha_c.get("inicio")) or FC._fecha(t.get("inicio")))
        # Día nuevo = ventana nueva (dueño, 16-nov: «dejarlo así y ver si empieza gastando mucho y sin convertir, ahí un tirón −30 %»).
        # El presupuesto NO se resetea a la medianoche del mercado; lo que se reinicia es la cuenta: desde las 00:00 del mercado se mira
        # solo lo de hoy, para que una mañana mala no quede tapada por las ventas de ayer.
        zona_m = ZONA_MERCADO.get(str(t.get("mercado") or "").upper())
        medianoche = None
        if VENTANA_DIA and zona_m:
            from zoneinfo import ZoneInfo  # noqa: PLC0415
            loc = ahora.astimezone(ZoneInfo(zona_m))
            medianoche = loc.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(dt.timezone.utc)
        ventana = max(ult, medianoche) if ult and medianoche else ult
        inicio_ev = next((e for e in evs if e.get("inicio")), None)
        inicial = (inicio_ev or {}).get("a") or (evs[0].get("de") if evs else None) or uf.get("p")
        vc = o.get("valor_comprador") or {}
        aov = vc.get("neto_por_venta")
        fuente = (f"neto por comprador, {('últimos ' + str(vc['dias']) + ' días') if vc.get('dias') else 'historia'} ({vc.get('compradores')} compradores)"
                  if aov else None)
        if (vc.get("compradores") or 0) < AOV_MIN_VENTAS:
            madre = por_nombre.get(str(o.get("replica_de") or "")) if o.get("replica_de") else None
            vm = (madre or {}).get("valor_comprador") or {}
            if vm.get("neto_por_venta"):
                aov, fuente = vm["neto_por_venta"], f"madre ({madre['nombre']}): la réplica tiene {vc.get('compradores') or 0} compradores"
            elif o.get("ticket_front") or N.ticket_corte(t.get("ficha") or {}):
                aov = round((N.ticket_corte(t.get("ficha") or {}) or o.get("ticket_front")) * NETO_DE_BRUTO, 2)
                fuente = f"ticket neto (solo {vc.get('compradores') or 0} compradores)"
        cpa_previo, cpa_fuente = cpa_previo_de(t, cid, ahora, aov, N.zona_de(libro))
        out.append({
            "oferta": info.get("oferta"), "campana": cid, "nombre": ficha_c.get("nombre") or info.get("nombre"), "rol": info.get("rol"),
            "presupuesto_usd": uf.get("p"), "presupuesto_inicial_usd": inicial,
            "ultimo_cambio": ventana.isoformat(timespec="minutes") if ventana else None,
            "ultimo_cambio_real": ult.isoformat(timespec="minutes") if ult else None,
            "ventana": "día del mercado" if ventana and medianoche and ventana == medianoche and ventana != ult else "desde el último cambio",
            "desde_cambio": FC.desde_cambio(libro, cid, ventana, ahora, lista_fotos) if ventana else None,
            "gasto_ultimas_horas": FC.gasto_ultimas_horas(libro, cid, ahora, RITMO_HORAS, lista_fotos),
            "aov_usd": round(float(aov), 2) if aov else None, "aov_fuente": fuente,
            "cpa_previo_usd": round(cpa_previo, 2) if cpa_previo else None, "cpa_previo_fuente": cpa_fuente,
            "ticket_usd": N.ticket_corte(t.get("ficha") or {}),
            "fase": "test" if o.get("fase") == "test" else "post",
            "utc_offset_mercado_h": _offset_h(ficha_c.get("inicio") or t.get("inicio")),
            "congelada": congelada(info.get("oferta"), ahora, libro),
        })
    return {"leido": ahora.isoformat(timespec="minutes"), "fuente": "auto (libro + fotos de la nube + presupuesto_eventos)", "ofertas": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lectura")
    g.add_argument("--auto", action="store_true")
    ap.add_argument("--registrar", action="store_true")
    ap.add_argument("--ahora")
    a = ap.parse_args()
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    if a.auto:
        sys.path.insert(0, str(RAIZ))
        libro = json.loads(FC.LIBRO.read_text(encoding="utf-8"))
        lectura = armar_lectura(libro, ahora)
    else:
        lectura = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
    decisiones = []
    for o in lectura.get("ofertas", []):
        if "congelada" not in o:
            o = {**o, "congelada": congelada(o.get("oferta"), ahora)}
        decisiones.append(decidir(o, ahora))
    salida = {"leido": lectura.get("leido"), "ahora": ahora.isoformat(timespec="minutes"), "regla": REGLA, "por_campana": True, "ofertas": decisiones}
    total = sum(float(d.get("presupuesto_usd") or 0) for d in decisiones)
    if not SEGUNDA_CUENTA_LISTA and total >= SEGUNDA_CUENTA_USD:
        salida["aviso_segunda_cuenta"] = (f"Las campañas activas suman US$ {total:g}/día: es momento de crear la segunda cuenta publicitaria "
                                          "(respaldo y escala horizontal). Al tenerla, poner cuentas.segunda_cuenta_lista en true.")
    if a.registrar:
        with REGISTRO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(salida, ensure_ascii=False) + "\n")
    json.dump(salida, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
