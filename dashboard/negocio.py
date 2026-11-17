"""Tablero «Negocio»: cuentas de la cartera de ofertas a partir del libro de tests (lógica pura, sin archivos ni red).

Fuente: ``ofertas/_funnels/libro-de-tests.json`` (lo actualiza el agente en cada revisión: skill escalar-oferta, guía
``references/01-revision-diaria.md``). Una **oferta** agrupa uno o más tests (clave ``oferta``; si falta, el ``nombre``) y cada test
puede tener varias tiendas de Impultienda (niveles, oferta intermedia) y campañas. Todo en USD con los tipos de cambio del libro.

Fórmulas (las mismas que ``libro_de_tests.py``, más los costos fijos):

- producción = créditos Kie × precio del crédito + imágenes Gemini × precio + otros;
- bruto / neto = suma de cada venta convertida a USD (el neto es el que informa Impul Pay, después de comisiones e impuestos);
- neto − Meta = lo que queda contra los anuncios; **ganancia neta** = neto − Meta − producción − fijos prorrateados;
- fijos prorrateados = cada costo fijo mensual / 30, y el de cada día se reparte entre las ofertas que pautaron ese día (día empezado = 1; 17-nov);
- ROAS Meta = valor de compras que atribuye Meta / gasto en Meta (lo que ve el administrador de anuncios);
  ROAS bruto real = bruto / gasto en Meta; ROAS neto = neto / gasto en Meta (equilibrio contra anuncios = 1,00);
  ROAS real = neto / (gasto en Meta + producción + fijos repartidos) (equilibrio del funnel completo = 1,00);
  la producción NO entra en los ROAS de anuncios: entra en el ROAS real y en la ganancia neta;
- ticket medio = bruto / ventas; CPA = gasto en Meta / ventas reales;
- CPA de equilibrio = neto / ventas (lo máximo que se puede pagar por venta sin perder contra Meta). Sin ventas se usa
  ``ficha.equilibrio_estimado_usd`` o, si falta, el precio de la tienda principal × (neto / bruto) del resto de la cartera
  (marcado «estimado»).

Nada de aquí escribe archivos. Los datos personales de compradores no se leen ni se devuelven (solo orden, tienda,
nivel, fecha y montos).
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any

__all__ = [
    "REF_CHECKOUT", "REF_COMPRA", "HORAS_DATOS_VIEJOS", "ticket_corte",
    "calcular", "calcular_test", "agrupar_ofertas", "zona_cpa", "parsear_fecha", "costos_produccion",
]

REF_CHECKOUT = (8.0, 12.0)       # % de visitas que llegan al checkout (buena: 10 %)
REF_CHECKOUT_BUENA = 10.0
REF_COMPRA = (25.0, 30.0)        # % de checkouts que compran
POCOS_CHECKOUTS = 30             # por debajo, el % de compra es una pista, no un veredicto
HORAS_DATOS_VIEJOS = 24
def _regla(clave: str, defecto: Any) -> Any:
    """Número de una regla del dueño desde ``ofertas/_funnels/reglas.json`` (el mismo archivo que leen los scripts de las skills)."""
    import json as _json
    from pathlib import Path as _P
    try:
        d: Any = _json.loads((_P(__file__).resolve().parents[1] / "ofertas" / "_funnels" / "reglas.json").read_text(encoding="utf-8"))
        for parte in clave.split("."):
            d = d[parte]
        return d
    except (OSError, ValueError, KeyError, TypeError):
        return defecto


VECES_TICKET_PARA_CORTAR = _regla("test.corte_tickets", 1.5)   # dueño, 12-nov; el ticket es el del producto completo (13-nov)
# Los frenos de cuenta (300 USD/día y −3.000 USD) los eliminó el dueño el 13-nov: cada oferta se corta por su propia regla.
MARGEN_CPA = 0.9                 # CPA entre 90 % y 100 % del equilibrio: «justo»
_CAMPOS_VENTA = ("orden", "tienda", "nivel", "fecha", "moneda", "bruto", "neto", "tipo")   # lista blanca: nunca correo ni nombre
# Ventas que suben el ticket de un comprador que ya contó (dueño, 13-nov: «lo que deja (AOV) puede ser dinámico post backend ofensivo»):
# suman al neto pero no son compradores nuevos, así que no cuentan en ventas_n ni en el CPA.
TIPOS_VENTA_EXTRA = ("upsell", "downsell", "bump", "rebaja")


# ───────────────────────── ayudas ─────────────────────────

def _num(x: Any) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)) and math.isfinite(x):
        return float(x)
    return None


def _div(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else a / b


def _pct(a: Any, b: Any) -> float | None:
    a, b = _num(a), _num(b)
    return None if a is None or not b else 100.0 * a / b


def _r(x: float | None, d: int = 2) -> float | None:
    return None if x is None else round(x, d)


def parsear_fecha(texto: Any) -> _dt.datetime | None:
    """ISO con zona («2026-11-12T20:00-03:00», «…Z»); sin zona se toma UTC. ``None`` si no se entiende."""
    if not isinstance(texto, str) or not texto:
        return None
    t = texto.strip().replace("Z", "+00:00")
    try:
        d = _dt.datetime.fromisoformat(t)
    except ValueError:
        try:
            d = _dt.datetime.fromisoformat(t[:10])
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def _texto(x: Any, largo: int = 400) -> str | None:
    return x[:largo] if isinstance(x, str) else None


def costos_produccion(prod: Any, precio_kie: float, precio_gemini: float) -> dict[str, Any]:
    """Producción de un test. Desde el 17-nov cruza la carga manual con ``produccion.barrido`` (barrido_costos.py, lo que
    dicen los gasto*.jsonl y el audio de las voces): por rubro manda el MAYOR de los dos (lo manual trae rondas cuyos
    registros se limpiaron; el barrido trae renovaciones y voces que nadie sumó). Las voces de Gemini (TTS) solo las mide
    el barrido."""
    p = prod if isinstance(prod, dict) else {}
    b = p.get("barrido") if isinstance(p.get("barrido"), dict) else {}
    kie_man, kie_bar = _num(p.get("kie_creditos")) or 0.0, _num(b.get("kie_creditos")) or 0.0
    gem_man, gem_bar = _num(p.get("gemini_imagenes")) or 0.0, _num(b.get("gemini_imagenes")) or 0.0
    kie, gem = max(kie_man, kie_bar), max(gem_man, gem_bar)
    otros = _num(p.get("otros_usd")) or 0.0
    voces_usd = _num(b.get("tts_usd")) or 0.0
    kie_usd, gem_usd = kie * precio_kie, gem * precio_gemini
    return {"kie_creditos": kie, "kie_usd": kie_usd, "gemini_imagenes": gem, "gemini_usd": gem_usd, "otros_usd": otros,
            "voces_usd": voces_usd, "voces_min": _num(b.get("tts_minutos")) or 0.0,
            "renovacion_kie": _num(b.get("kie_despues_de_lanzar")) or 0.0,
            "kie_manual": kie_man, "kie_barrido": kie_bar, "barrido_fecha": _texto(b.get("fecha"), 20),
            "total": kie_usd + gem_usd + otros + voces_usd, "nota": _texto(p.get("nota"))}


def zona_cpa(cpa: float | None, equilibrio: float | None, gasto: float, ventas: int, ticket_front: float | None = None) -> dict[str, Any]:
    """Semáforo del costo por venta contra el equilibrio: ok (por debajo del 90 %), justo, sobre, sin_ventas, sin_ventas_corte
    (gastó 1,5 tickets sin ventas: se apaga), sin_pauta, sin_dato."""
    if gasto <= 0:
        return {"zona": "sin_pauta", "tono": "neutro", "texto": "Todavía sin gasto en anuncios"}
    if ventas == 0:
        if ticket_front and gasto >= VECES_TICKET_PARA_CORTAR * ticket_front:
            return {"zona": "sin_ventas_corte", "tono": "error", "texto": f"Sin ventas tras gastar {_coma(gasto / ticket_front)} tickets"}
        return {"zona": "sin_ventas", "tono": "aviso" if ticket_front and gasto >= ticket_front else "neutro", "texto": "Todavía sin ventas"}
    if cpa is None or not equilibrio:
        return {"zona": "sin_dato", "tono": "neutro", "texto": "Sin punto de equilibrio"}
    if cpa > equilibrio:
        return {"zona": "sobre", "tono": "error", "texto": "Cada venta cuesta más de lo que deja"}
    if cpa > MARGEN_CPA * equilibrio:
        return {"zona": "justo", "tono": "aviso", "texto": "Justo en el equilibrio"}
    return {"zona": "ok", "tono": "ok", "texto": "Cada venta deja ganancia"}


def _tono_rango(v: float | None, rango: tuple[float, float]) -> str | None:
    if v is None:
        return None
    return "ok" if v >= rango[0] else "aviso"


def _dias_pauta(inicio: _dt.datetime | None, corte: _dt.datetime | None) -> int:
    if not inicio or not corte or corte <= inicio:
        return 0
    return max(1, math.ceil((corte - inicio).total_seconds() / 86400))


# ───────────────────────── un test ─────────────────────────

def calcular_test(t: dict[str, Any], tc: dict[str, float], precio_kie: float, precio_gemini: float) -> dict[str, Any]:
    """Cuentas de un test del libro (sin fijos: se prorratean a nivel cartera). Las monedas sin tipo de cambio se avisan, no se inventan."""
    avisos: list[str] = []
    prod = costos_produccion(t.get("produccion"), precio_kie, precio_gemini)
    meta = t.get("meta") if isinstance(t.get("meta"), dict) else {}
    gasto = _num(meta.get("gasto_usd")) or 0.0
    # El gasto de Meta solo crece: si el historial por día (leído después) suma más que el total al corte, vale el historial.
    # Sin esto, «Desde el inicio» y un rango que cubre todos los días daban gastos distintos (Caminho: 21,18 vs 23,03).
    hist_gasto = sum(_num(h.get("gasto_usd")) or 0.0 for h in t.get("historial_diario") or [] if isinstance(h, dict))
    if hist_gasto > gasto:
        gasto = hist_gasto
    ventas: list[dict[str, Any]] = []
    bruto = neto = 0.0
    for v in t.get("ventas") or []:
        if not isinstance(v, dict):
            continue
        mon = v.get("moneda")
        f = _num(tc.get(mon)) if isinstance(mon, str) else None
        b, n = _num(v.get("bruto")), _num(v.get("neto"))
        if f is None:
            avisos.append(f"Venta {v.get('orden')}: falta el tipo de cambio de {mon}; no se suma.")
            continue
        fila = {k: v.get(k) for k in _CAMPOS_VENTA}
        fila["bruto_usd"] = (b or 0.0) * f
        fila["neto_usd"] = (n or 0.0) * f
        bruto += fila["bruto_usd"]
        neto += fila["neto_usd"]
        ventas.append(fila)
    emb = t.get("tienda_embudo") if isinstance(t.get("tienda_embudo"), dict) else {}
    return {"prod": prod, "gasto": gasto, "meta": meta, "bruto": bruto, "neto": neto, "ventas": ventas, "embudo": emb, "avisos": avisos}


# ───────────────────────── agrupación por oferta ─────────────────────────

def agrupar_ofertas(tests: list[Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """``[(nombre de la oferta, [tests])]`` en el orden del libro: los tests con la misma ``oferta`` (o el mismo ``nombre``) van juntos."""
    orden: list[str] = []
    grupos: dict[str, list[dict[str, Any]]] = {}
    for t in tests or []:
        if not isinstance(t, dict):
            continue
        clave = t.get("oferta") if isinstance(t.get("oferta"), str) and t.get("oferta") else t.get("nombre")
        if not isinstance(clave, str) or not clave:
            continue
        if clave not in grupos:
            orden.append(clave)
            grupos[clave] = []
        grupos[clave].append(t)
    return [(k, grupos[k]) for k in orden]


def _slug(nombre: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", nombre).encode("ascii", "ignore").decode("ascii").lower()
    out = "".join(c if c.isalnum() else "-" for c in s)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:60] or "oferta"


_ESTADOS = {"activo": "activa", "activa": "activa", "programado": "programada", "programada": "programada",
            "pausado": "pausada", "pausada": "pausada", "cerrado": "cerrada", "cerrada": "cerrada",
            "armado": "armada", "armada": "armada"}   # armada: tienda, landing y campaña listas, pero la campaña NO salió (falta algo del dueño)


def _estado(tests: list[dict[str, Any]]) -> str:
    vistos = [_ESTADOS.get(str(t.get("estado", "")).lower(), str(t.get("estado") or "sin dato")) for t in tests]
    for e in ("activa", "programada", "pausada", "cerrada"):
        if e in vistos:
            return e
    return vistos[0] if vistos else "sin dato"


def _sanear_ficha(f: Any) -> dict[str, Any]:
    """Copia acotada de la ficha (texto recortado, listas con tope). Las URL se devuelven tal cual: el cliente las valida (https)."""
    def s(v: Any, nivel: int = 0) -> Any:
        if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            return v[:600]
        if nivel > 5:
            return None
        if isinstance(v, list):
            return [s(x, nivel + 1) for x in v[:200]]
        if isinstance(v, dict):
            return {str(k)[:80]: s(x, nivel + 1) for k, x in list(v.items())[:80]}
        return None
    if not isinstance(f, dict):
        return {}
    out = s(f)

    def https(u: Any) -> str | None:   # solo https y sin espacios ni comillas: el panel las abre en otra pestaña con un clic explícito
        return u if isinstance(u, str) and u.startswith("https://") and not any(c in u for c in " \"'<>\\") else None
    out["landing_original"] = https(out.get("landing_original"))
    for t in out.get("tiendas") or []:
        if isinstance(t, dict):
            t["url"] = https(t.get("url"))
    return out


# ───────────────────────── decisión: acción sugerida, anuncios que venden, cambios programados ─────────────────────────

VENTAS_PARA_ESCALAR = 3
REGLA_ESTADO = "propuesta, todavía sin firmar por el dueño"
REGLA_CORTE = "firmada por el dueño el 12-nov: en el día 1 (o mientras no venda) se apaga sola con el CPA en 1,5 tickets del producto completo (ticket del completo: dueño, 13-nov)"


def accion_sugerida(gasto: float, ventas: int, cpa: float | None, equilibrio: float | None, fuente_eq: str | None,
                    estado: str, inicio: Any = None, ticket_front: float | None = None, en_test: bool = True) -> dict[str, Any]:
    """Regla por test. Corte (firmado por el dueño el 12-nov): en test (día 1 del mercado, o mientras no venda), con el CPA en
    1,5 tickets del producto completo o más (gasto ≥ 1,5 × ticket × máx(1, ventas)), se apaga; sin ventas es «gastó 1,5 tickets».
    Escalar (propuesta, sin firmar): ≥ 3 ventas y CPA bajo el equilibrio. Sin pauta si no arrancó; mirar un día más en lo demás."""
    eq_txt = f"{_usd(equilibrio)}{' (estimado)' if fuente_eq == 'estimado' else ''}" if equilibrio else "sin equilibrio"
    corte_usd = VECES_TICKET_PARA_CORTAR * ticket_front if ticket_front else None
    sin_ticket = " Falta el precio en USD de las tiendas en la ficha: sin él no se puede aplicar el corte."
    if gasto <= 0 and ventas == 0:
        ini = parsear_fecha(inicio)
        cuando = f"Arranca el {ini.strftime('%d-%m')} a las {ini.strftime('%H:%M')} (hora del mercado). " if ini and estado == "programada" else ""
        corte = f" Se apaga a {_usd(corte_usd)} gastados sin ventas (1,5 × {_usd(ticket_front)})." if corte_usd else sin_ticket
        return {"clave": "sin_pauta", "texto": "Sin pauta", "tono": "neutro", "porque": f"{cuando}Equilibrio {eq_txt} por venta.{corte}", "regla": REGLA_CORTE}
    if ventas == 0:
        if corte_usd and gasto >= corte_usd:
            return {"clave": "cortar", "texto": "Apagar", "tono": "error", "regla": REGLA_CORTE,
                    "porque": f"Gastó {_usd(gasto)} sin ventas: {_coma(gasto / ticket_front)} tickets de {_usd(ticket_front)} (el corte es 1,5)."}
        falta = f" Se apaga a {_usd(corte_usd)} (1,5 × {_usd(ticket_front)})." if corte_usd else sin_ticket
        return {"clave": "mirar", "texto": "Sigue en test", "tono": "aviso", "regla": REGLA_CORTE,
                "porque": f"Todavía sin ventas con {_usd(gasto)} gastados.{falta}"}
    if en_test and corte_usd and cpa is not None and cpa >= corte_usd:
        return {"clave": "cortar", "texto": "Apagar", "tono": "error", "regla": REGLA_CORTE,
                "porque": f"Día 1: costo por venta {_usd(cpa)} con {ventas} {'venta' if ventas == 1 else 'ventas'}, {_coma(cpa / ticket_front)} tickets de {_usd(ticket_front)} (el corte es 1,5)."}
    base = f"Costo por venta {_usd(cpa)} contra un equilibrio de {eq_txt}, {ventas} {'venta' if ventas == 1 else 'ventas'}, {_usd(gasto)} gastados."
    if ventas >= VENTAS_PARA_ESCALAR and cpa is not None and equilibrio and cpa < equilibrio:
        return {"clave": "escalar", "texto": "Escalar", "tono": "ok", "porque": base, "regla": REGLA_ESTADO}
    if cpa is not None and equilibrio and cpa < equilibrio:
        motivo = f" Faltan {VENTAS_PARA_ESCALAR - ventas} {'venta' if VENTAS_PARA_ESCALAR - ventas == 1 else 'ventas'} para escalar."
    elif cpa is not None and equilibrio:
        motivo = " Cada venta cuesta más de lo que deja."
    else:
        motivo = ""
    return {"clave": "mirar", "texto": "Mirar un día más", "tono": "aviso", "porque": base + motivo, "regla": REGLA_ESTADO}


def _fin_dia1(inicio: _dt.datetime | None) -> _dt.datetime | None:
    """Fin del test: las 00:00 siguientes al inicio, en la zona del inicio (día 1 del mercado)."""
    if inicio is None:
        return None
    return _dt.datetime.combine(inicio.date() + _dt.timedelta(days=1), _dt.time(0), tzinfo=inicio.tzinfo)


def texto_programado(cuando: _dt.datetime, que: str, ahora: _dt.datetime) -> str:
    """«mañana 00:00: 65 USD/día + conjunto R3» (día contado en la zona del cambio, la del mercado); como mucho ~70 caracteres."""
    hoy = ahora.astimezone(cuando.tzinfo).date()
    dias = (cuando.date() - hoy).days
    dia = "hoy" if dias == 0 else "mañana" if dias == 1 else cuando.strftime("%d/%m")
    que = " ".join(que.split())
    if len(que) > 52:
        que = que[:51].rstrip(" ,.;") + "…"
    return f"{dia} {cuando.strftime('%H:%M')}: {que}"


def frase_corta(o: dict[str, Any]) -> str:
    """El porqué del veredicto en una línea (≤ 80 caracteres) para la lista de ofertas; el detalle completo queda en ``porque``."""
    a = o.get("accion_sugerida") or {}
    clave = a.get("clave")
    gasto, nv, cpa, eq, corte = o.get("gasto_meta") or 0, o.get("ventas_n") or 0, o.get("cpa"), o.get("equilibrio"), o.get("corte_usd")
    if clave == "pausada":
        txt = f"Campaña pausada con {_usd(gasto)} gastados y {nv} {'venta' if nv == 1 else 'ventas'}"
    elif clave == "sin_pauta":
        ini = parsear_fecha(o.get("inicio_texto"))
        txt = (f"Arranca el {ini.strftime('%d/%m')} a las {ini.strftime('%H:%M')}" if ini and o.get("estado") == "programada" else "Todavía sin gasto en anuncios")
        if o.get("ticket_front"):
            txt += f"; se apaga a {_usd(VECES_TICKET_PARA_CORTAR * o['ticket_front'])} sin ventas"
    elif nv == 0:
        txt = f"Sin ventas con {_usd(gasto)} gastados" + (f"; se apaga a {_usd(corte)}" if corte and clave != "cortar" else "")
    elif cpa is not None and eq:
        txt = f"Cada venta cuesta {_usd(cpa)} y deja {_usd(eq)}"
        if clave == "mirar" and cpa < eq and nv < VENTAS_PARA_ESCALAR:
            txt += f"; faltan {VENTAS_PARA_ESCALAR - nv} para escalar"
    else:
        txt = f"{nv} {'venta' if nv == 1 else 'ventas'} con {_usd(gasto)} gastados"
    return txt if len(txt) <= 80 else txt[:79].rstrip() + "…"


def veredicto_de_fila(o: dict[str, Any]) -> None:
    """Una campaña pausada o cerrada no recibe «mirar un día más» ni «escalar»: su veredicto es «Pausada». Agrega ``frase`` (≤ 80)."""
    if o.get("estado") in ("pausada", "cerrada"):
        previa = o.get("accion_sugerida") or {}
        o["accion_sugerida"] = {"clave": "pausada", "texto": "Pausada" if o["estado"] == "pausada" else "Cerrada", "tono": "pausada",
                                "porque": f"La campaña está {o['estado']}. Antes de pausarla la regla decía: {previa.get('texto', 'sin dato')}. {previa.get('porque', '')}".strip(),
                                "regla": previa.get("regla", REGLA_ESTADO)}
    o["frase"] = frase_corta(o)


def precio_front(ficha: dict[str, Any]) -> float | None:
    """Precio en USD del front: la tienda con rol «principal» o, si ninguna lo dice, la primera con precio."""
    tiendas = [x for x in (ficha.get("tiendas") if isinstance(ficha.get("tiendas"), list) else []) if isinstance(x, dict) and isinstance(x.get("precio"), dict)]
    principal = next((x for x in tiendas if str(x.get("rol", "")).startswith("principal")), tiendas[0] if tiendas else None)
    return _num(principal["precio"].get("usd")) if principal else None


def kpis_oferta(bruto: float, neto: float, gasto: float, ganancia: float, nv: int, ventas: list[dict[str, Any]],
                precio_principal: float | None, diario: list[dict[str, Any]], hoy: str) -> dict[str, Any]:
    """KPIs de la oferta (dueño, 13-nov: «a los KPIs de cada oferta falta el AOV, el margen neto…»).

    - aov: facturación bruta ÷ compradores (principal + upsells, bumps y downsells de esos compradores).
    - aov_veces_principal: aov ÷ precio del producto principal; referencia ≥ 1,5 × con backend (Bilbao).
    - aov_neto: lo que deja cada comprador después de comisiones (= CPA de equilibrio contra Meta).
    - margen_neto_pct: ganancia neta ÷ facturación bruta (con producción y fijos).
    - margen_contra_meta_pct: (neto − Meta) ÷ bruto: el margen de la operación, sin la producción que se pagó una vez.
    - comision_pct: (bruto − neto) ÷ bruto (Impul Pay, impuestos, cambio).
    - take_rate_pct: ventas extra (upsell, downsell, bump) ÷ compradores.
    - ganancia_ultimo_dia: neto − Meta del último día completo con gasto leído (lo que suma hoy para la meta diaria).
    """
    extras = sum(1 for v in ventas if str(v.get("tipo") or "").lower() in TIPOS_VENTA_EXTRA)
    dias = [d for d in diario if d.get("resultado") is not None and d.get("fecha") and d["fecha"] < hoy]
    ult = max(dias, key=lambda d: d["fecha"]) if dias else None
    aov = bruto / nv if nv else None
    return {"aov": _r(aov), "aov_neto": _r(neto / nv) if nv else None,
            "aov_veces_principal": _r(aov / precio_principal) if aov and precio_principal else None,
            "precio_principal": _r(precio_principal),
            "margen_neto_pct": _r(100 * ganancia / bruto, 1) if bruto else None,
            "margen_contra_meta_pct": _r(100 * (neto - gasto) / bruto, 1) if bruto else None,
            "comision_pct": _r(100 * (bruto - neto) / bruto, 1) if bruto else None,
            "take_rate_pct": _r(100 * extras / nv, 1) if nv else None, "ventas_extra_n": extras,
            "ganancia_ultimo_dia": ult["resultado"] if ult else None, "ultimo_dia": ult["fecha"] if ult else None}


def ticket_corte(ficha: dict[str, Any]) -> float | None:
    """Ticket con el que se corta el test (dueño, 13-nov): el del producto completo, o sea el precio en USD más alto de las
    tiendas del funnel (principal y niveles). En una oferta de un solo producto es el del front; con niveles de 13, 19 y 27 USD es 27."""
    tiendas = [x for x in (ficha.get("tiendas") if isinstance(ficha.get("tiendas"), list) else []) if isinstance(x, dict) and isinstance(x.get("precio"), dict)]
    precios = [p for p in (_num(x["precio"].get("usd")) for x in tiendas) if p and p > 0]
    return max(precios) if precios else None


ANUNCIO_GASTO_MINIMO = 2.0   # con menos de US$ 2, un anuncio todavía no dice nada


def veredicto_anuncio(gasto: float, compras: int, roas_neto_est: float | None, ticket_front: float | None) -> dict[str, str]:
    """Veredicto por anuncio (dueño, 12-nov): Ganador (ROAS neto estimado ≥ 1 y ≥ 2 compras) · Promete (1 compra y ROAS ≥ 1) ·
    Sin datos (gastó menos de US$ 2) · Flojo (1,5 × el ticket del completo gastado sin compras: la regla firmada, por anuncio) · Mirar."""
    if compras >= 2 and roas_neto_est is not None and roas_neto_est >= 1:
        return {"clave": "ganador", "texto": "Ganador", "tono": "ok"}
    if compras == 1 and roas_neto_est is not None and roas_neto_est >= 1:
        return {"clave": "promete", "texto": "Promete", "tono": "info"}
    if gasto < ANUNCIO_GASTO_MINIMO:
        return {"clave": "sin_datos", "texto": "Sin datos", "tono": "neutro"}
    if compras == 0 and ticket_front and gasto >= VECES_TICKET_PARA_CORTAR * ticket_front:
        return {"clave": "flojo", "texto": "Flojo", "tono": "error"}
    return {"clave": "mirar", "texto": "Mirar", "tono": "aviso"}


# ───────────────────────── ROAS estimado con rango (dueño, 17-nov: «decidir con la confianza, no solo con el promedio») ─────────────────────────
# Las compras de pocas horas o de un día son azar en buena parte (medir_ruido.py: un día de un anuncio casi no predice el siguiente).
# El ROAS se estima «acercando» lo que se ve a lo que se sabe de antes (los 3 días anteriores de esa campaña o anuncio, 50/30/20, o el
# promedio de la oferta): como si ya se hubieran visto FUERZA_PREVIA compras a ese ritmo. Con muchas compras propias manda lo propio;
# con 1 o 2, manda lo previo. El rango (piso, techo) es el 80 % central de lo probable (Gamma-Poisson, aproximación Wilson-Hilferty).

FUERZA_PREVIA = 3.0
PESOS_3D = (0.5, 0.3, 0.2)   # hoy (o el día más reciente), ayer, anteayer
Z80 = 1.2816


def _cuantil_gamma(forma: float, tasa: float, z: float) -> float:
    nu = 2 * forma
    c = 1 - 2 / (9 * nu) + z * math.sqrt(2 / (9 * nu))
    return max(0.0, nu * c ** 3 / (2 * tasa))


def roas_estimado(compras: float, gasto: float, valor: float | None, cpa_previo: float | None,
                  fuerza: float = FUERZA_PREVIA) -> dict[str, float | None]:
    """``{roas, piso, techo, crudo}`` de ROAS neto: compras × valor por comprador ÷ gasto, acercado al CPA previo."""
    if not valor or gasto <= 0:
        return {"roas": None, "piso": None, "techo": None, "crudo": None}
    crudo = compras * valor / gasto
    if not cpa_previo or cpa_previo <= 0:   # sin nada previo: el ROAS es el que se ve; el rango, el honesto de esas compras
        forma, tasa = compras + 0.5, gasto
        return {"roas": _r(crudo), "piso": _r(_cuantil_gamma(forma, tasa, -Z80) * valor),
                "techo": _r(_cuantil_gamma(forma, tasa, Z80) * valor), "crudo": _r(crudo)}
    forma, tasa = compras + fuerza, gasto + fuerza * cpa_previo
    return {"roas": _r(forma / tasa * valor), "piso": _r(_cuantil_gamma(forma, tasa, -Z80) * valor),
            "techo": _r(_cuantil_gamma(forma, tasa, Z80) * valor), "crudo": _r(crudo)}


def cpa_ponderado(dias: list[tuple[float, float]], pesos: tuple[float, ...] = PESOS_3D) -> float | None:
    """CPA de los últimos días [(gasto, compras)] del más reciente al más viejo, pesando 50/30/20. None sin compras."""
    g = sum(w * d[0] for w, d in zip(pesos, dias))
    c = sum(w * d[1] for w, d in zip(pesos, dias))
    return g / c if c > 0 else None


# ───────────────────────── neto por comprador para el ROAS estimado por anuncio (dueño, 17-nov) ─────────────────────────
# El neto medio de UN día salta con los upsells de ese día; para comparar anuncios entre días se usa una ventana móvil que termina
# en el último día del período: 7 días; con menos de 50 compradores, 14; si tampoco llega, toda la historia hasta ese día.

NPV_MIN_COMPRADORES = 50
NPV_VENTANAS = (7, 14)
NPV_MIN_TRAS_CAMBIO = 10   # con menos compradores desde el último cambio del embudo, el cambio todavía no cuenta


def cambios_de_embudo(ts: list[dict[str, Any]], zona: _dt.tzinfo) -> list[_dt.date]:
    """Días en que cambió lo que deja cada comprador: backend activado (``backend.desde``) y ``ficha.cambios_embudo``
    (lista de fechas o de ``{"fecha", "que"}``: precio nuevo, bump, upsell…). La ventana del valor por comprador no los cruza."""
    out: set[_dt.date] = set()
    for t in ts:
        b = t.get("backend") if isinstance(t.get("backend"), dict) else {}
        if str(b.get("estado") or "").lower() in ("activo", "activa") and (d := dia_de(b.get("desde"), zona)):
            out.add(d)
        f = t.get("ficha") if isinstance(t.get("ficha"), dict) else {}
        for c in f.get("cambios_embudo") or []:
            d = dia_de(c.get("fecha") if isinstance(c, dict) else c, zona)
            if d:
                out.add(d)
    return sorted(out)


def neto_por_comprador_ventana(ts: list[dict[str, Any]], tc: dict[str, float], zona: _dt.tzinfo, fin: _dt.date) -> dict[str, Any] | None:
    """``{neto_por_venta, dias (7, 14 o None = historia), compradores, desde, hasta, cambio}`` con las ventas de la oferta (todas, no
    las del período: ``_ventas_todas`` si el libro está recortado). La ventana no cruza el último cambio del embudo (``cambio``) si
    desde entonces hay al menos NPV_MIN_TRAS_CAMBIO compradores. None si no hay ningún comprador hasta ``fin``.
    Es EL valor por comprador del sistema (dueño, 17-nov): lo usan el panel, la escala, los ganadores, la R16 y la R4b."""
    filas: list[tuple[_dt.date, float, bool]] = []
    for t in ts:
        vs = t.get("_ventas_todas") if isinstance(t.get("_ventas_todas"), list) else t.get("ventas")
        for v in vs or []:
            if not isinstance(v, dict):
                continue
            d = dia_de(v.get("dia_cuenta") or v.get("fecha"), zona)
            mon = v.get("moneda")
            f = _num(tc.get(mon)) if isinstance(mon, str) else None
            if d is None or f is None or d > fin:
                continue
            filas.append((d, (_num(v.get("neto")) or 0.0) * f, str(v.get("tipo") or "").lower() not in TIPOS_VENTA_EXTRA))
    if not any(p for _, _, p in filas):
        return None

    def medir(desde: _dt.date | None) -> tuple[float, int, _dt.date | None]:
        sel = [x for x in filas if desde is None or x[0] >= desde]
        return sum(n for _, n, _ in sel), sum(1 for _, _, p in sel if p), min((x[0] for x in sel), default=None)

    piso, cambio = None, None
    for c in reversed([c for c in cambios_de_embudo(ts, zona) if c <= fin]):
        if medir(c)[1] >= NPV_MIN_TRAS_CAMBIO:
            piso = cambio = c
            break
    for dias in NPV_VENTANAS:
        desde = fin - _dt.timedelta(days=dias - 1)
        if piso and desde < piso:
            break
        neto, nc, _ = medir(desde)
        if nc >= NPV_MIN_COMPRADORES:
            return {"neto_por_venta": neto / nc, "dias": dias, "compradores": nc,
                    "desde": desde.isoformat(), "hasta": fin.isoformat(), "cambio": None}
    neto, nc, primero = medir(piso)
    return {"neto_por_venta": neto / nc, "dias": None, "compradores": nc,
            "desde": (piso or primero).isoformat() if (piso or primero) else None, "hasta": fin.isoformat(),
            "cambio": cambio.isoformat() if cambio else None}


def anuncios_de_oferta(tests: list[dict[str, Any]], ficha: dict[str, Any], neto_por_venta: float | None, fuente_eq: str | None,
                       ticket_front: float | None, ventana: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tabla de anuncios de la oferta, ordenada por gasto, con CPA, ROAS Meta, ROAS neto ESTIMADO (compras × neto medio por venta ÷ gasto:
    Meta atribuye las compras a cada anuncio, el neto real es por oferta), CTR, clic → pago y retención del video, más el veredicto
    por anuncio y una línea de lectura. Fuente: ``anuncios.lista`` del test (lectura de Meta por anuncio); si falta, ``ficha.campanas[].anuncios``."""
    if ventana:   # neto por comprador de la ventana móvil (7/14 días o historia), no el del período
        neto_por_venta, fuente_eq = ventana["neto_por_venta"], "real"
    crudos: list[dict[str, Any]] = []
    leido = None
    for t in tests:
        a = t.get("anuncios")
        if isinstance(a, dict) and isinstance(a.get("lista"), list):
            leido = leido or _texto(a.get("leido"), 40)
            crudos += [x for x in a["lista"] if isinstance(x, dict)]
    if not crudos:
        for c in ficha.get("campanas") or []:
            if isinstance(c, dict):
                leido = leido or _texto(c.get("leido"), 40)
                crudos += [dict(x, conjunto=None) for x in (c.get("anuncios") if isinstance(c.get("anuncios"), list) else []) if isinstance(x, dict)]
    filas = [_kpis_anuncio({**{k: x.get(k) for k in ("id", "nombre", "conjunto", "estado", "miniatura", "creativo_id")}, **_sumas_anuncio([x])},
                           x.get("ctr_pct"), neto_por_venta, ticket_front) for x in crudos]
    filas.sort(key=lambda a: (-(a["gasto_usd"] or 0), a["nombre"] or ""))
    conjuntos = sorted({a["conjunto"] for a in filas if a["conjunto"]})
    vendedor = max((a for a in filas if a["compras_meta"]), key=lambda a: (a["compras_meta"], a["gasto_usd"] or 0), default=None)
    cuenta = {k: sum(1 for a in filas if a["veredicto"]["clave"] == k) for k in ("ganador", "promete", "sin_datos", "flojo", "mirar")}
    partes = [f"{cuenta['ganador']} {'ganador' if cuenta['ganador'] == 1 else 'ganadores'}"]
    if cuenta["promete"]:
        partes.append(f"{cuenta['promete']} {'promete' if cuenta['promete'] == 1 else 'prometen'}")
    if cuenta["flojo"]:
        partes.append(f"{cuenta['flojo']} {'flojo' if cuenta['flojo'] == 1 else 'flojos'}")
    partes.append(f"{cuenta['sin_datos']} sin datos")
    partes.append(f"el que más vende: {vendedor['nombre']} ({vendedor['compras_meta']} {'compra' if vendedor['compras_meta'] == 1 else 'compras'})" if vendedor else "todavía ningún anuncio vendió")
    creativos = creativos_de(crudos, neto_por_venta, ticket_front)
    fin = _dt.date.fromisoformat(ventana["hasta"]) if ventana and ventana.get("hasta") else None
    agregar_roas_3d(tests, filas + creativos, neto_por_venta, fin)
    return {"lista": filas, "leido": leido, "conjuntos": conjuntos, "cuenta": cuenta, "resumen": " · ".join(partes),
            "neto_por_venta": _r(neto_por_venta), "neto_estimado": fuente_eq == "estimado",
            "neto_ventana": ({k: ventana.get(k) for k in ("dias", "compradores", "desde", "hasta", "cambio")} if ventana else None),
            "top": creativos[:TOP_CREATIVOS], "n_creativos": len(creativos)}


# ───────────────────────── top de creativos (dueño, 15-nov: «el top 20 de creativos que mejor están performando con todos sus KPIs») ─────────────────────────

TOP_CREATIVOS = 20
_SUMABLES_AD = ("gasto_usd", "impresiones", "alcance", "clics_enlace", "visitas_landing_meta", "inicios_pago_meta", "compras_meta", "vistas_3s",
                "video_p25", "video_p50", "video_p75", "video_p100", "thruplay")


def _sumas_anuncio(xs: list[dict[str, Any]]) -> dict[str, Any]:
    """Suma de los datos crudos de uno o varios anuncios; el valor de compras queda en None si ninguno lo trae."""
    out: dict[str, Any] = {k: sum(_num(x.get(k)) or 0.0 for x in xs) for k in _SUMABLES_AD}
    vals = [_num(x.get("valor_compras_meta_usd")) for x in xs]
    out["valor_compras_meta_usd"] = sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None
    out["con_video"] = any(_num(x.get(k)) for x in xs for k in ("video_p25", "vistas_3s", "video_p100"))
    return out


def _kpis_anuncio(x: dict[str, Any], ctr_dado: Any, neto_por_venta: float | None, ticket_front: float | None) -> dict[str, Any]:
    """KPIs de un anuncio o de un creativo (suma de sus anuncios): costo, embudo, video y veredicto."""
    g, imp, cl = x["gasto_usd"], x["impresiones"], x["clics_enlace"]
    ic, comp, vis = x["inicios_pago_meta"], int(x["compras_meta"]), x["visitas_landing_meta"]
    val = x["valor_compras_meta_usd"]
    roas_meta = (val if val is not None else (0.0 if comp == 0 else None))
    roas_est = (comp * neto_por_venta / g) if g > 0 and neto_por_venta else None
    ctr = _num(ctr_dado)
    video = x.get("con_video")
    por_imp = lambda k: _r(100 * x[k] / imp, 1) if imp and video else None  # noqa: E731
    return {
        **{k: x.get(k) for k in ("id", "nombre", "conjunto", "estado", "miniatura", "creativo_id", "ids", "conjuntos")},
        "gasto_usd": _r(g), "compras_meta": comp, "cpa": _r(g / comp) if comp else None,
        "roas_meta": _r(roas_meta / g) if g > 0 and roas_meta is not None else None,
        "roas_neto_estimado": _r(roas_est),
        "ctr_pct": _r(ctr if ctr is not None else (100 * cl / imp if imp else None)),
        "cpc": _r(g / cl) if cl else None, "cpm": _r(1000 * g / imp) if imp else None,
        "clic_pago_pct": _r(100 * ic / cl, 1) if cl else None,
        "pago_compra_pct": _r(100 * comp / ic, 1) if ic else None,
        "costo_pago": _r(g / ic) if ic else None,
        "visitas_landing_meta": int(vis), "costo_visita": _r(g / vis) if vis else None,
        "hook_pct": por_imp("vistas_3s") if x.get("vistas_3s") else None,
        "retencion_pct": por_imp("video_p100"), "retencion_25_pct": por_imp("video_p25"),
        "retencion_50_pct": por_imp("video_p50") if x.get("video_p50") else None,
        "impresiones": int(imp), "clics_enlace": int(cl), "inicios_pago_meta": int(ic),
        "veredicto": veredicto_anuncio(g, comp, roas_est, ticket_front),
    }


def _clave_creativo(x: dict[str, Any]) -> str:
    """Un mismo creativo corre en varios conjuntos (renovaciones): se junta por nombre del anuncio; sin nombre, por id."""
    n = (x.get("nombre") or "").strip().lower()
    return f"n:{n}" if n else f"i:{x.get('id')}"


def _orden_creativo(c: dict[str, Any]) -> tuple:
    """Mejor primero: más compras; a igualdad, menor CPA; sin compras, primero los que ya gastaron US$ 2 (los «Sin datos» al final),
    después más pagos iniciados, mejor CTR y más gasto."""
    return (-c["compras_meta"], c["cpa"] if c["cpa"] is not None else float("inf"), (c["gasto_usd"] or 0) < ANUNCIO_GASTO_MINIMO, -(c["inicios_pago_meta"] or 0),
            -(c["ctr_pct"] or 0), -(c["gasto_usd"] or 0))


def agregar_roas_3d(tests: list[dict[str, Any]], filas: list[dict[str, Any]], valor: float | None, fin: _dt.date | None) -> None:
    """Agrega a cada anuncio o creativo ``roas_3d`` = {roas, piso, techo, crudo, compras, gasto}: sus 3 últimos días hasta ``fin``
    pesando 50/30/20 (hoy, ayer, anteayer), acercado al CPA de la oferta en 7 días (dueño, 17-nov, puntos 2 y 3).
    Un día malo no lo hunde y uno bueno no lo corona; el rango dice cuánto se sabe de verdad."""
    if not valor or not fin:
        return
    por: dict[str, dict[str, tuple[float, float]]] = {}
    for t in tests:
        a = t.get("anuncios") if isinstance(t.get("anuncios"), dict) else {}
        for r in a.get("por_dia") or []:
            if isinstance(r, dict) and r.get("fecha"):
                d = por.setdefault(str(r.get("id")), {})
                g0, c0 = d.get(str(r["fecha"])[:10], (0.0, 0.0))
                d[str(r["fecha"])[:10]] = (g0 + (_num(r.get("gasto_usd")) or 0.0), c0 + (_num(r.get("compras_meta")) or 0.0))
    desde7 = (fin - _dt.timedelta(days=6)).isoformat()
    g7 = sum(v[0] for d in por.values() for f, v in d.items() if desde7 <= f <= fin.isoformat())
    c7 = sum(v[1] for d in por.values() for f, v in d.items() if desde7 <= f <= fin.isoformat())
    cpa_oferta = g7 / c7 if c7 else valor   # sin compras en la semana, se acerca al empate
    dias = [(fin - _dt.timedelta(days=i)).isoformat() for i in range(3)]
    for a in filas:
        ids = [str(i) for i in (a.get("ids") or [a.get("id")]) if i]
        serie = [(sum(por.get(i, {}).get(f, (0.0, 0.0))[0] for i in ids), sum(por.get(i, {}).get(f, (0.0, 0.0))[1] for i in ids)) for f in dias]
        g = sum(w * x[0] for w, x in zip(PESOS_3D, serie))
        c = sum(w * x[1] for w, x in zip(PESOS_3D, serie))
        if g <= 0:
            a["roas_3d"] = None
            continue
        a["roas_3d"] = {**roas_estimado(c, g, valor, cpa_oferta), "compras": _r(sum(x[1] for x in serie), 0), "gasto": _r(sum(x[0] for x in serie))}


def creativos_de(crudos: list[dict[str, Any]], neto_por_venta: float | None, ticket_front: float | None) -> list[dict[str, Any]]:
    """Creativos de la oferta (anuncios juntados por nombre entre conjuntos), con sus KPIs, del mejor al peor; solo los que tuvieron impresiones."""
    grupos: dict[str, list[dict[str, Any]]] = {}
    for x in crudos:
        grupos.setdefault(_clave_creativo(x), []).append(x)
    out = []
    for xs in grupos.values():
        s = _sumas_anuncio(xs)
        if not s["impresiones"] and not s["gasto_usd"]:
            continue
        estados = [x.get("estado") for x in xs if x.get("estado")]
        principal = max(xs, key=lambda x: _num(x.get("gasto_usd")) or 0)
        base = {"id": principal.get("id"), "nombre": principal.get("nombre"), "ids": [x.get("id") for x in xs if x.get("id")],
                "conjuntos": sorted({x.get("conjunto") for x in xs if x.get("conjunto")}),
                "estado": "ACTIVE" if "ACTIVE" in estados else (estados[0] if estados else None),
                "miniatura": next((x.get("miniatura") for x in sorted(xs, key=lambda x: -(_num(x.get("gasto_usd")) or 0)) if x.get("miniatura")), None),
                "creativo_id": principal.get("creativo_id"), "conjunto": None}
        out.append(_kpis_anuncio({**base, **s}, None, neto_por_venta, ticket_front))
    out.sort(key=_orden_creativo)
    for i, c in enumerate(out, 1):
        c["puesto"] = i
    return out


def top_anuncios(ficha: dict[str, Any], n: int = 3) -> list[dict[str, Any]]:
    """Los ``n`` anuncios con más compras (y después más gasto) de todas las campañas de la ficha; solo los que gastaron algo."""
    lista = []
    for c in ficha.get("campanas") or []:
        if not isinstance(c, dict):
            continue
        anuncios = c.get("anuncios")
        for a in anuncios if isinstance(anuncios, list) else []:
            if isinstance(a, dict) and (_num(a.get("gasto_usd")) or 0) > 0:
                lista.append({"nombre": _texto(a.get("nombre"), 200), "id": _texto(a.get("id"), 40), "gasto_usd": _num(a.get("gasto_usd")) or 0.0,
                              "compras_meta": int(_num(a.get("compras_meta")) or 0), "clics_enlace": int(_num(a.get("clics_enlace")) or 0),
                              "inicios_pago_meta": int(_num(a.get("inicios_pago_meta")) or 0), "leido": _texto(c.get("leido"), 40)})
    lista.sort(key=lambda a: (-a["compras_meta"], -a["gasto_usd"]))
    return lista[:n]


def programados(tests: list[dict[str, Any]], ahora: _dt.datetime) -> list[dict[str, Any]]:
    """Cambios programados (campo opcional ``programado: [{cuando, que}]`` del test) que todavía no pasaron, del más cercano al más lejano."""
    out = []
    for t in tests:
        for p in t.get("programado") or []:
            if not isinstance(p, dict) or not isinstance(p.get("que"), str):
                continue
            cuando = parsear_fecha(p.get("cuando"))
            if cuando is None or cuando < ahora:
                continue
            out.append((cuando, {"cuando": p.get("cuando"), "que": p["que"][:400], "en_horas": round((cuando - ahora).total_seconds() / 3600, 1),
                                 "corto": texto_programado(cuando, p.get("corto") if isinstance(p.get("corto"), str) else p["que"], ahora)}))
    return [x for _, x in sorted(out, key=lambda z: z[0])]


# ───────────────────────── etapa y backend ofensivo (pedido del dueño, 13-nov) ─────────────────────────
#
# «Cuando estemos testeando 15, 20 ofertas juntas será muy difícil ver si ya le pusimos backend a una… en qué estado está: si sigue en
# testeo, si ya están programadas las renovaciones, si está aprobada para renovaciones, si está para pausarla y apagarla».
# La ETAPA es dónde está la oferta en su vida (no lo que conviene hacer: eso es el veredicto). Sale del libro: estado, fase del test,
# la acción de corte y el campo opcional ``renovaciones`` [{ronda, inicio, estado, anuncios, conjunto, nota}] de cada test.
# El BACKEND (upsells post-compra) sale del campo opcional ``backend`` {estado: activo|pausado|armando|no, desde, upsells[{nombre,
# precio_usd}], tiendas[], nota}; si falta, la oferta no tiene backend.

DIAS_RENOVACION_RECIENTE = 1   # R9 (dueño, 13-nov): a las ofertas que pegan se les hace una ronda por día; sin ronda de hoy ni de mañana, «Para renovar»

ETAPAS: dict[str, dict[str, Any]] = {   # orden = urgencia (lo que pide una mano primero)
    "apagar": {"texto": "Para apagar", "corto": "Apagar", "tono": "error", "orden": 0},
    "aprobada": {"texto": "Aprobada para renovar", "corto": "Renovar", "tono": "ok", "orden": 1},
    "armada": {"texto": "Armada, sin salir", "corto": "Armada", "tono": "aviso", "orden": 1.5},
    "test": {"texto": "En test", "corto": "Test", "tono": "aviso", "orden": 2},
    "renovando": {"texto": "Renovando", "corto": "Renovando", "tono": "info", "orden": 3},
    "renovacion_programada": {"texto": "Renovación programada", "corto": "Renov. prog.", "tono": "info", "orden": 4},
    "programada": {"texto": "Programada", "corto": "Programada", "tono": "info", "orden": 5},
    "apagada": {"texto": "Apagada", "corto": "Apagada", "tono": "pausada", "orden": 6},
}

_ESTADOS_BACKEND = {"activo": "activo", "activa": "activo", "pausado": "pausado", "pausada": "pausado", "armando": "armando", "listo": "listo",
                    "en armado": "armando", "no": "no", "sin": "no", "sin backend": "no"}


def _hora_mercado(d: _dt.datetime) -> str:
    """«13/11 00:00» en la zona en que vino la fecha (la del mercado)."""
    return d.strftime("%d/%m %H:%M")


def renovaciones_de(tests: list[dict[str, Any]], ahora: _dt.datetime) -> list[dict[str, Any]]:
    """Rondas de creativos nuevos de la oferta, de la más vieja a la más nueva. Con inicio futuro y sin pausar: «programada»;
    con inicio pasado y estado programada o vacío: «activa» (el conjunto se activa el mismo día con el inicio a las 00:00)."""
    out = []
    for t in tests:
        for r in t.get("renovaciones") or []:
            if not isinstance(r, dict):
                continue
            ini = parsear_fecha(r.get("inicio"))
            est = str(r.get("estado") or "").strip().lower()
            if est not in ("pausada", "cancelada"):
                if ini and ini > ahora:
                    est = "programada"
                elif est in ("", "programada", "activo") and ini:
                    est = "activa"
            out.append({"ronda": _texto(r.get("ronda"), 20) or "?", "inicio": r.get("inicio") if ini else None, "estado": est or "sin dato",
                        "anuncios": int(_num(r.get("anuncios")) or 0) or None, "conjunto": _texto(r.get("conjunto"), 200),
                        "nota": _texto(r.get("nota")), "_ini": ini})
    out.sort(key=lambda r: r["_ini"].timestamp() if r["_ini"] else 0)
    return out


def backend_de(tests: list[dict[str, Any]]) -> dict[str, Any]:
    """Backend ofensivo de la oferta (upsells post-compra): estado, upsells y tiendas. Sin el campo: «no»."""
    b = next((t.get("backend") for t in tests if isinstance(t.get("backend"), dict)), None) or {}
    est = _ESTADOS_BACKEND.get(str(b.get("estado") or "no").strip().lower(), "no")
    ups = [{"nombre": _texto(u.get("nombre"), 120), "precio_usd": _num(u.get("precio_usd"))}
           for u in (b.get("upsells") or []) if isinstance(u, dict)][:12]
    tiendas = [x for x in (b.get("tiendas") or []) if isinstance(x, str)][:12]
    # order bump del checkout (dueño, 14-nov: «le activamos un order bump en el checkout y no aparece»): `backend.bump` {nombre, precio_usd, estado?}
    # o una lista; sin estado propio sigue el del backend (en R3b se prende junto con el embudo)
    crudos = b.get("bump") if isinstance(b.get("bump"), list) else [b.get("bump")] if isinstance(b.get("bump"), dict) else []
    bumps = [{"nombre": _texto(x.get("nombre"), 160), "precio_usd": _num(x.get("precio_usd")),
              "estado": _ESTADOS_BACKEND.get(str(x.get("estado") or est).strip().lower(), est)} for x in crudos if isinstance(x, dict)][:6]
    n = len(ups)
    cuantos = f"{n} {'upsell' if n == 1 else 'upsells'}" if n else ""
    if bumps:
        cuantos = f"{cuantos} + order bump" if cuantos else "order bump"
    texto = {"activo": "Backend activo", "pausado": "Backend en pausa", "armando": "Backend en armado", "listo": "Backend listo", "no": "Sin backend"}[est]
    # «listo» (R3b, backend anticipado): armado y con el embudo apagado hasta que cierre el test; se prende solo en activar_desde
    activar = b.get("activar_desde") if est == "listo" and parsear_fecha(b.get("activar_desde")) else None
    if activar:
        texto += f" · se prende el {parsear_fecha(activar).strftime('%d/%m %H:%M')}"
    return {"estado": est, "activo": est == "activo", "activar_desde": activar, "texto": texto + (f" · {cuantos}" if cuantos and est != "no" else ""),
            "upsells": ups, "bumps": bumps, "tiendas": tiendas, "desde": b.get("desde") if parsear_fecha(b.get("desde")) else None, "nota": _texto(b.get("nota"))}


def etapa_de(o: dict[str, Any], tests: list[dict[str, Any]], renov: list[dict[str, Any]], ahora: _dt.datetime) -> dict[str, Any]:
    """Etapa de la oferta con una línea de detalle. Se llama después de ``veredicto_de_fila`` (usa estado, fase y acción de corte)."""
    def e(clave: str, detalle: str, extra: str | None = None) -> dict[str, Any]:
        base = ETAPAS[clave]
        corto = f"{base['corto']} · {extra}" if extra else base["corto"]
        return {"clave": clave, "texto": base["texto"], "corto": corto, "tono": base["tono"], "orden": base["orden"], "detalle": detalle}

    estado = o.get("estado")
    if estado in ("pausada", "cerrada"):
        ap = next((t.get("apagado") for t in tests if isinstance(t.get("apagado"), dict)), None)
        if ap:
            cuando = parsear_fecha(ap.get("cuando"))
            det = f"Se apagó{' el ' + cuando.strftime('%d/%m a las %H:%M') if cuando else ''} por la regla de corte ({ap.get('regla') or 'sin dato'})."
        else:
            det = f"La campaña está {estado}."
        return e("apagada", det)
    if estado == "armada":   # 14-nov: una oferta armada con la campaña en pausa salía «En test» (Oferta J)
        pend = [str(p.get("que")) for t in tests for p in (t.get("pendientes") or []) if isinstance(p, dict) and p.get("que") and not p.get("hecho")]
        det = "La campaña está creada en pausa y no gasta: no salió." + (f" Falta: {pend[0]}" + (f" (y {len(pend) - 1} más)" if len(pend) > 1 else "") if pend else "")
        return e("armada", det, "falta el dueño" if pend else None)
    if (o.get("accion_sugerida") or {}).get("clave") == "cortar":
        return e("apagar", f"{(o.get('accion_sugerida') or {}).get('porque', '')} La vigilancia de cada hora la apaga sola.".strip())
    ini = parsear_fecha(o.get("inicio_texto"))
    if (ini and ini > ahora) or (estado == "programada" and not ini):   # programada con el inicio ya pasado: está corriendo (test)
        return e("programada", f"La campaña sale el {_hora_mercado(ini)} (hora del mercado)." if ini else "La campaña todavía no arrancó.",
                 ini.strftime("%d/%m %H:%M") if ini else None)
    if o.get("fase") == "test":
        fin = parsear_fecha(o.get("fin_test"))
        if fin and ahora < fin:
            det = f"Día 1 del mercado: el test cierra el {_hora_mercado(fin)}. Con ventas y el costo por venta bajo 1,5 tickets, pasa a renovar."
        else:
            det = "Todavía sin ventas: sigue en test hasta vender o llegar al corte de 1,5 tickets."
        return e("test", det, "día 1" if fin and ahora < fin else "sin ventas")
    prog = [r for r in renov if r["estado"] == "programada"]
    if prog:
        r = prog[0]
        return e("renovacion_programada", f"Ronda {r['ronda']}{' con ' + str(r['anuncios']) + ' anuncios' if r['anuncios'] else ''} sale el "
                 f"{_hora_mercado(r['_ini'])} (hora del mercado).", r["ronda"])
    activas = [r for r in renov if r["estado"] == "activa" and r["_ini"]]
    ultima = activas[-1] if activas else None
    if ultima and (ahora - ultima["_ini"]) <= _dt.timedelta(days=DIAS_RENOVACION_RECIENTE):
        lee = ultima["_ini"] + _dt.timedelta(days=DIAS_RENOVACION_RECIENTE)
        return e("renovando", f"Ronda {ultima['ronda']}{' con ' + str(ultima['anuncios']) + ' anuncios' if ultima['anuncios'] else ''} corre desde el "
                 f"{_hora_mercado(ultima['_ini'])}; la próxima ronda sale el {lee.strftime('%d/%m')} a las 00:00.", ultima["ronda"])
    if ultima:
        dias = (ahora - ultima["_ini"]).days
        det = f"Pasó el test. La última ronda ({ultima['ronda']}) salió hace {dias} días: toca renovar creativos."
    else:
        det = "Pasó el test y todavía no tiene renovaciones: toca la primera ronda de creativos."
    return e("aprobada", det)


# ───────────────────────── cartera ─────────────────────────

def calcular(libro: Any, ahora: _dt.datetime) -> dict[str, Any]:
    """Modelo completo del tablero: ``{corte, referencias, cartera, atencion, ofertas, avisos}``."""
    L = libro if isinstance(libro, dict) else {}
    tc = {k: v for k, v in (L.get("tipos_de_cambio") or {}).items() if _num(v) is not None}
    pk = _num(L.get("precio_credito_kie_usd")) or 0.0
    pg = _num(L.get("precio_imagen_gemini_usd")) or 0.0
    avisos: list[str] = []
    zona = zona_de(L)
    fin_ventana = dia_de(L.get("_hasta"), zona) or ahora.astimezone(zona).date()   # último día del período (o hoy)
    cortes_activos: list[_dt.datetime] = []   # «datos viejos» solo mira lo que sigue gastando: una oferta pausada no cambia

    grupos = agrupar_ofertas(L.get("tests") or [])
    n_ofertas = max(1, sum(1 for _, ts in grupos if _estado(ts) != "cerrada"))
    fijos_mes = [c for c in (L.get("costos_fijos_compartidos") or []) if isinstance(c, dict)]
    fijo_diario = sum(_num(c.get("usd_mes")) or 0.0 for c in fijos_mes) / 30.0
    fijos_pendientes = [_texto(c.get("concepto"), 120) for c in fijos_mes if _num(c.get("usd_mes")) is None]

    # fijos por día de calendario (17-nov): el costo fijo de cada día se reparte entre las ofertas que pautaron ESE día.
    # Antes era «días de la oferta ÷ ofertas abiertas hoy», que dejaba sin cargar los días ya pagados (con 600 USD/mes de
    # fijos, la cartera mostraba 40 USD en vez de los ~20 USD diarios de verdad).
    dias_grupo: dict[str, set[str]] = {}
    for nombre, ts in grupos:
        dd: set[str] = set()
        for t in ts:
            lista = t.get("_dias_lista")
            dd.update(lista if isinstance(lista, list) else (d.isoformat() for d in dias_de_pauta(t, zona, ahora)))
        dias_grupo[nombre] = dd
    con_pauta: dict[str, int] = {}
    for dd in dias_grupo.values():
        for d in dd:
            con_pauta[d] = con_pauta.get(d, 0) + 1

    # razón neto/bruto de toda la cartera (para estimar el equilibrio de una oferta sin ventas)
    tot_b = tot_n = 0.0
    calculos: dict[str, list[dict[str, Any]]] = {}
    for nombre, ts in grupos:
        calculos[nombre] = [calcular_test(t, tc, pk, pg) for t in ts]
        for c in calculos[nombre]:
            tot_b += c["bruto"]
            tot_n += c["neto"]
    razon_neta = tot_n / tot_b if tot_b else None

    ofertas: list[dict[str, Any]] = []
    crudos: list[dict[str, float]] = []   # sin redondear: los totales de la cartera se suman de aquí (igual que libro_de_tests.py)
    cortes: list[_dt.datetime] = []
    for nombre, ts in grupos:
        cs = calculos[nombre]
        for c in cs:
            avisos.extend(c["avisos"])
        gasto = sum(c["gasto"] for c in cs)
        bruto = sum(c["bruto"] for c in cs)
        neto = sum(c["neto"] for c in cs)
        ventas = [v for c in cs for v in c["ventas"]]
        nv = sum(1 for v in ventas if str(v.get("tipo") or "").lower() not in TIPOS_VENTA_EXTRA)   # compradores (órdenes principales)
        prod_tot = sum(c["prod"]["total"] for c in cs)
        prod = {k: sum((c["prod"][k] or 0.0) for c in cs) for k in ("kie_creditos", "kie_usd", "gemini_imagenes", "gemini_usd", "otros_usd", "voces_usd", "voces_min", "renovacion_kie", "kie_manual", "kie_barrido", "total")}
        prod["notas"] = [c["prod"]["nota"] for c in cs if c["prod"]["nota"]]

        inicio = min((d for d in (parsear_fecha(t.get("inicio")) for t in ts) if d), default=None)
        corte_dt = max((d for d in (parsear_fecha(t.get("corte")) for t in ts) if d), default=None)
        if corte_dt:
            cortes.append(corte_dt)
            cortes_activos.extend(d for d in (parsear_fecha(t.get("corte")) for t in ts if _ESTADOS.get(str(t.get("estado", "")).lower()) == "activa") if d)
        dias_periodo = [t["_dias_periodo"] for t in ts if isinstance(t.get("_dias_periodo"), int)]
        dias = max(dias_periodo) if dias_periodo else max((len(dias_de_pauta(t, zona, ahora)) for t in ts), default=0)
        fijos = sum(fijo_diario / con_pauta[d] for d in dias_grupo.get(nombre, ()))

        ficha = _sanear_ficha(next((t.get("ficha") for t in ts if isinstance(t.get("ficha"), dict)), {}))
        equilibrio, fuente_eq = (neto / nv, "real") if nv else (None, None)
        if equilibrio is None:
            est = _num(ficha.get("equilibrio_estimado_usd"))
            if est:
                equilibrio, fuente_eq = est, "estimado"
            else:
                tiendas = ficha.get("tiendas") if isinstance(ficha.get("tiendas"), list) else []
                precio = next((_num((x.get("precio") or {}).get("usd")) for x in tiendas if isinstance(x, dict) and isinstance(x.get("precio"), dict)), None)
                if precio and razon_neta:
                    equilibrio, fuente_eq = precio * razon_neta, "estimado"
        cpa = gasto / nv if nv else None
        valor_c = neto_por_comprador_ventana(ts, tc, zona, fin_ventana)
        if valor_c:
            valor_c = {**valor_c, "neto_por_venta": _r(valor_c["neto_por_venta"])}
        ganancia = neto - gasto - prod_tot - fijos
        ticket_front = ticket_corte(ficha)   # el nombre del campo queda por compatibilidad: es el ticket del corte (producto completo)
        # segunda oportunidad del test (dueño, 13-nov): el corte pasa de 1,5 a 2 tickets; se refleja escalando el ticket del corte
        segunda = any(isinstance(t.get("segunda_oportunidad"), dict) for t in ts)
        if segunda and ticket_front:
            extra = float((_regla("test.segunda_oportunidad", {}) or {}).get("extra_tickets", 0.5))
            ticket_front = ticket_front * (VECES_TICKET_PARA_CORTAR + extra) / VECES_TICKET_PARA_CORTAR
        fin_test = _fin_dia1(inicio)
        en_test = nv == 0 or fin_test is None or ahora < fin_test

        # embudo (suma de tests) contra las referencias
        vis = sum(_num(c["embudo"].get("landing")) or 0 for c in cs)
        chk = sum(_num(c["embudo"].get("checkout")) or 0 for c in cs)
        com = sum(_num(c["embudo"].get("compras")) or 0 for c in cs)
        incompleto = any(c["embudo"].get("incompleto") for c in cs)
        if incompleto:
            vis = chk = com = None
        p_chk, p_com, p_vis = (None, None, None) if incompleto else (_pct(chk, vis), _pct(com, chk), _pct(com, vis))
        por_tienda_emb = {}
        for c in cs:
            pt = c["embudo"].get("por_tienda")
            if isinstance(pt, dict):
                for slug, e in pt.items():
                    if isinstance(e, dict):
                        acc = por_tienda_emb.setdefault(str(slug), {"landing": 0, "checkout": 0, "compras": 0})
                        for k in acc:
                            acc[k] += _num(e.get(k)) or 0
        periodos = [_texto(c["embudo"].get("_periodo") or c["embudo"].get("_nota")) for c in cs]

        # Meta: totales al corte
        mt = {k: sum(_num(c["meta"].get(k)) or 0 for c in cs) for k in ("gasto_usd", "impresiones", "clics_enlace", "visitas_landing_meta", "inicios_pago_meta", "compras_meta")}
        # valor de compras que atribuye Meta (para el ROAS que muestra el administrador de anuncios); sin el campo en ningún test → sin dato
        valores_meta = [_num(c["meta"].get("valor_compras_meta_usd")) for c in cs]
        valor_meta = sum(v for v in valores_meta if v is not None) if any(v is not None for v in valores_meta) else None
        costo_total = gasto + prod_tot + fijos

        # ventas por tienda (agrupación de tiendas)
        nombres_tienda = {x.get("slug"): x.get("nombre") for x in (ficha.get("tiendas") or []) if isinstance(x, dict)}
        slugs = [s for t in ts for s in (t.get("tienda") or []) if isinstance(s, str)]
        por_tienda: dict[str, dict[str, Any]] = {s: {"slug": s, "nombre": nombres_tienda.get(s) or s, "ventas": 0, "bruto_usd": 0.0, "neto_usd": 0.0} for s in slugs}
        for v in ventas:
            s = v.get("tienda") if isinstance(v.get("tienda"), str) else (slugs[0] if slugs else "sin tienda")
            fila = por_tienda.setdefault(s, {"slug": s, "nombre": nombres_tienda.get(s) or s, "ventas": 0, "bruto_usd": 0.0, "neto_usd": 0.0})
            fila["ventas"] += 1
            fila["bruto_usd"] += v["bruto_usd"]
            fila["neto_usd"] += v["neto_usd"]
            if por_tienda_emb.get(s):
                fila["embudo"] = por_tienda_emb[s]
        for s, e in por_tienda_emb.items():
            por_tienda.setdefault(s, {"slug": s, "nombre": nombres_tienda.get(s) or s, "ventas": 0, "bruto_usd": 0.0, "neto_usd": 0.0})["embudo"] = e

        # historial por día: gasto de Meta (historial_diario) + ventas por fecha
        dias_map: dict[str, dict[str, Any]] = {}
        leido_hist: list[str] = []
        for t in ts:
            for h in t.get("historial_diario") or []:
                if not isinstance(h, dict) or not isinstance(h.get("fecha"), str):
                    continue
                d = dias_map.setdefault(h["fecha"][:10], {"fecha": h["fecha"][:10], "gasto": 0.0, "ventas": 0, "bruto": 0.0, "neto": 0.0, "compras_meta": 0, "con_meta": False})
                d["gasto"] += _num(h.get("gasto_usd")) or 0.0
                d["compras_meta"] += int(_num(h.get("compras_meta")) or 0)
                d["con_meta"] = True
                if isinstance(h.get("leido"), str):
                    leido_hist.append(h["leido"])
        for v in ventas:
            dv = dia_de(v.get("dia_cuenta") or v.get("fecha"), zona)   # mismo día de la cuenta que usa el filtro de período
            if dv is None:
                continue
            f = dv.isoformat()
            d = dias_map.setdefault(f, {"fecha": f, "gasto": 0.0, "ventas": 0, "bruto": 0.0, "neto": 0.0, "compras_meta": 0, "con_meta": False})
            d["ventas"] += 1
            d["bruto"] += v["bruto_usd"]
            d["neto"] += v["neto_usd"]
        diario = []
        for k in sorted(dias_map):
            d = dias_map[k]
            diario.append({"fecha": k, "gasto": _r(d["gasto"]) if d["con_meta"] else None, "ventas": d["ventas"], "bruto": _r(d["bruto"]), "neto": _r(d["neto"]),
                           "resultado": _r(d["neto"] - d["gasto"]) if d["con_meta"] else None, "compras_meta": d["compras_meta"] if d["con_meta"] else None})
        gasto_hist = sum(d["gasto"] or 0 for d in diario)
        ventas_sin_fecha = sum(1 for v in ventas if not isinstance(v.get("fecha"), str))

        veredicto = "sin_pauta" if gasto <= 0 and nv == 0 else ("ganando" if ganancia > 0 else "perdiendo")
        estado = _estado(ts)
        campanas = [c for t in ts for c in ([t.get("campana")] if isinstance(t.get("campana"), str) else (t.get("campana") or [])) if isinstance(c, str)]

        crudos.append({"gasto": gasto, "bruto": bruto, "neto": neto, "prod": prod_tot, "fijos": fijos, "valor_meta": valor_meta})
        ofertas.append({
            "id": _slug(nombre), "nombre": nombre, "estado": estado,
            "mercado": "/".join(sorted({str(t.get("mercado")) for t in ts if t.get("mercado")})) or None,
            "tipo_funnel": next((t.get("tipo_funnel") for t in ts if t.get("tipo_funnel")), None),
            "inicio": inicio.isoformat() if inicio else None,
            "inicio_texto": next((t.get("inicio") for t in ts if t.get("inicio")), None),
            "corte": next((t.get("corte") for t in ts if parsear_fecha(t.get("corte")) == corte_dt), None) if corte_dt else None,
            "corte_horas": _r((ahora - corte_dt).total_seconds() / 3600, 1) if corte_dt else None,
            "tests": len(ts), "tiendas": slugs, "campanas": campanas,
            "gasto_meta": _r(gasto), "produccion": {k: (_r(v) if isinstance(v, float) else v) for k, v in prod.items()},
            "fijos": _r(fijos, 4), "dias_pauta": dias,
            "fijos_detalle": _fijos_detalle(fijos, fijos_mes),
            "apagado_cuando": _cuando_apagada(ts),
            "ventas_n": nv, "bruto": _r(bruto), "neto": _r(neto),
            "neto_menos_meta": _r(neto - gasto), "neto_menos_todo": _r(neto - gasto - prod_tot), "ganancia_neta": _r(ganancia),
            "roas_bruto": _r(_div(bruto, gasto)), "roas_neto": _r(_div(neto, gasto)),
            "roas_meta": _r(_div(valor_meta, gasto)), "valor_compras_meta": _r(valor_meta),
            "roas_real": _r(_div(neto, costo_total)),
            "comisiones": _r(bruto - neto), "ganancia_contra_meta": _r(neto - gasto),
            "costos": {"meta": _r(gasto), "produccion": _r(prod_tot), "fijos": _r(fijos, 4), "total": _r(costo_total)},
            "ticket_medio": _r(bruto / nv) if nv else None,
            "kpis": kpis_oferta(bruto, neto, gasto, ganancia, nv, ventas, precio_front(ficha), diario, ahora.astimezone(zona).date().isoformat()),
            "cpa": _r(cpa), "equilibrio": _r(equilibrio), "equilibrio_fuente": fuente_eq,
            "equilibrio_nota": ficha.get("equilibrio_nota") if fuente_eq == "estimado" else None,
            "fase": "test" if en_test else "post-lanzamiento", "fin_test": fin_test.isoformat() if fin_test else None,
            "ticket_front": _r(ticket_front),
            "corte_usd": _r(VECES_TICKET_PARA_CORTAR * ticket_front * max(1, nv)) if ticket_front and en_test else None,
            "semaforo_cpa": zona_cpa(cpa, equilibrio, gasto, nv, ticket_front),
            "veredicto": veredicto,
            "embudo": {"visitas": vis, "checkout": chk, "compras": com, "pct_checkout": _r(p_chk, 1), "pct_compra": _r(p_com, 1), "pct_compra_visita": _r(p_vis, 2),
                       "tono_checkout": _tono_rango(p_chk, REF_CHECKOUT), "tono_compra": _tono_rango(p_com, REF_COMPRA),
                       "pocos_datos": (chk or 0) < POCOS_CHECKOUTS, "periodo": [p for p in periodos if p], "incompleto": incompleto,
                       "parcial": any(c["embudo"].get("parcial") for c in cs)},
            "meta": mt, "compras_meta": int(mt["compras_meta"]), "diferencia_atribucion": int(mt["compras_meta"]) - nv,
            "ventas": [{k: (_r(v) if isinstance(v, float) else v) for k, v in x.items()} for x in ventas],
            "por_tienda": [{k: (_r(v) if isinstance(v, float) else v) for k, v in x.items()} for x in por_tienda.values()],
            "diario": diario, "historial_leido": max(leido_hist) if leido_hist else None,
            "historial_vs_corte": _r(gasto_hist - gasto) if diario and any(d["gasto"] is not None for d in diario) else None,
            "ventas_sin_fecha": ventas_sin_fecha,
            "ficha": ficha,
            "accion_sugerida": accion_sugerida(gasto, nv, cpa, equilibrio, fuente_eq, estado, next((t.get("inicio") for t in ts if t.get("inicio")), None), ticket_front, en_test),
            "segunda_oportunidad": segunda,
            "top_anuncios": top_anuncios(ficha),
            "valor_comprador": valor_c,
            "anuncios": anuncios_de_oferta(ts, ficha, equilibrio, fuente_eq, ticket_front, valor_c),
            "programado": programados(ts, ahora),
            "con_datos_periodo": any(t.get("_con_datos", True) for t in ts),
            "meta_sin_dia": _r(sum(t.get("_meta_sin_dia") or 0 for t in ts)) or None,
            "backend": backend_de(ts),
            "replica_de": next((r for t in ts for r in (t.get("replica_de"), (t.get("ficha") or {}).get("replica_de")) if isinstance(r, str) and r.strip()), None),
            "_tests": ts,
        })

    for o in ofertas:
        veredicto_de_fila(o)
        ts = o.pop("_tests")
        renov = renovaciones_de(ts, ahora)
        o["etapa"] = etapa_de(o, ts, renov, ahora)
        o["renovaciones"] = [{k: v for k, v in r.items() if k != "_ini"} for r in renov]
        # pasó el test y no tiene backend activo: los upsells post-compra se arman después del test
        o["backend"]["falta"] = o["etapa"]["clave"] in ("aprobada", "renovando", "renovacion_programada") and o["backend"]["estado"] not in ("activo", "listo")

    # cartera
    def suma(k: str) -> float:
        return sum(c[k] for c in crudos)
    gasto_t, bruto_t, neto_t, prod_t, fijos_t = suma("gasto"), suma("bruto"), suma("neto"), suma("prod"), suma("fijos")
    ventas_t = sum(o["ventas_n"] for o in ofertas)
    # gasto del último día con historial (todas las ofertas) y presupuesto diario comprometido
    por_dia: dict[str, float] = {}
    for o in ofertas:
        for d in o["diario"]:
            if d["gasto"] is not None:
                por_dia[d["fecha"]] = por_dia.get(d["fecha"], 0.0) + d["gasto"]
    ultimo_dia = max(por_dia) if por_dia else None
    presupuesto = 0.0
    for o in ofertas:
        if o["estado"] in ("activa", "programada"):
            for c in (o["ficha"].get("campanas") or []):
                if isinstance(c, dict) and str(c.get("estado", "")).upper() != "PAUSED":
                    presupuesto += _num(c.get("presupuesto_diario_usd")) or 0.0
    ganancia_t = neto_t - gasto_t - prod_t - fijos_t
    udc = max((o["kpis"]["ultimo_dia"] for o in ofertas if o["kpis"]["ultimo_dia"]), default=None)   # último día completo con gasto leído
    valores_t = [c["valor_meta"] for c in crudos if c["valor_meta"] is not None]
    valor_t = sum(valores_t) if valores_t else None
    cartera = {
        "gasto_meta": _r(gasto_t), "produccion": _r(prod_t), "fijos": _r(fijos_t, 4), "bruto": _r(bruto_t), "neto": _r(neto_t),
        "neto_menos_meta": _r(neto_t - gasto_t), "neto_menos_todo": _r(neto_t - gasto_t - prod_t), "ganancia_neta": _r(ganancia_t),
        "roas_bruto": _r(_div(bruto_t, gasto_t)), "roas_neto": _r(_div(neto_t, gasto_t)),
        "roas_meta": _r(_div(valor_t, gasto_t)), "roas_real": _r(_div(neto_t, gasto_t + prod_t + fijos_t)),
        "costos_total": _r(gasto_t + prod_t + fijos_t), "comisiones": _r(bruto_t - neto_t), "cpa_medio": _r(_div(gasto_t, ventas_t) if ventas_t else None),
        "equilibrio_medio": _r(neto_t / ventas_t) if ventas_t else None,
        "ventas": ventas_t, "compras_meta": sum(o["compras_meta"] for o in ofertas),
        "ofertas": len(ofertas),
        "ganando": sum(1 for o in ofertas if o["veredicto"] == "ganando"),
        "perdiendo": sum(1 for o in ofertas if o["veredicto"] == "perdiendo"),
        "sin_pauta": sum(1 for o in ofertas if o["veredicto"] == "sin_pauta"),
        "ganando_contra_meta": sum(1 for o in ofertas if o["gasto_meta"] and o["neto_menos_meta"] > 0),
        "gasto_ultimo_dia": _r(por_dia[ultimo_dia]) if ultimo_dia else None, "ultimo_dia": ultimo_dia,
        "gasto_ultimo_dia_leido": max((o["historial_leido"] for o in ofertas if o["historial_leido"]), default=None),
        "presupuesto_diario": _r(presupuesto),
        "etapas": {k: sum(1 for o in ofertas if o["etapa"]["clave"] == k) for k in ETAPAS},
        "con_backend": sum(1 for o in ofertas if o["backend"]["activo"]),
        "falta_backend": sum(1 for o in ofertas if o["backend"]["falta"]),
        "fijos_pendientes": [x for x in fijos_pendientes if x],
        "aov": _r(bruto_t / ventas_t) if ventas_t else None,
        "margen_neto_pct": _r(100 * ganancia_t / bruto_t, 1) if bruto_t else None,
        "margen_contra_meta_pct": _r(100 * (neto_t - gasto_t) / bruto_t, 1) if bruto_t else None,
        "ganancia_ultimo_dia": _r(sum(d["resultado"] for o in ofertas for d in o["diario"] if d["fecha"] == udc and d["resultado"] is not None)) if udc else None,
        "ultimo_dia_completo": udc,
        "meta_ganancia_dia": _num(_regla("meta.ganancia_neta_dia_usd", 10000)),
        "fijos_mes": [{"concepto": _texto(c.get("concepto"), 120), "usd_mes": _num(c.get("usd_mes")), "nota": _texto(c.get("nota"))} for c in fijos_mes],
    }
    ultimo = max(cortes) if cortes else None
    mas_viejo = min(cortes_activos) if cortes_activos else (min(cortes) if cortes else None)
    corte = {
        "ultimo": ultimo.isoformat() if ultimo else None, "mas_viejo": mas_viejo.isoformat() if mas_viejo else None,
        "horas": _r((ahora - mas_viejo).total_seconds() / 3600, 1) if mas_viejo else None,
        "viejo": bool(mas_viejo and (ahora - mas_viejo).total_seconds() > HORAS_DATOS_VIEJOS * 3600),
    }
    referencias = {"checkout": list(REF_CHECKOUT), "checkout_buena": REF_CHECKOUT_BUENA, "compra": list(REF_COMPRA), "pocos_checkouts": POCOS_CHECKOUTS,
                   "horas_datos_viejos": HORAS_DATOS_VIEJOS}
    return {"corte": corte, "referencias": referencias, "cartera": cartera, "ofertas": ofertas,
            "atencion": atencion(ofertas, cartera, referencias, ahora), "tipos_de_cambio": tc, "avisos": avisos}


# ───────────────────────── «De dónde sale la ganancia» (dueño, 15-nov) ─────────────────────────
# Pedido: «arriba, un detalle de esa ganancia oferta por oferta: cuáles ganaron, cuáles perdieron y todas las métricas para tener
# noción de qué está haciendo que perdamos o ganemos, qué tira para abajo y qué para arriba».
# Todo sale de los mismos números de cada oferta (respeta el período elegido). Las referencias del dueño (checkout 8-12 %, compra
# 25-30 %, CR 2-3,6 %, AOV 1,5 × el principal, CPA ≤ equilibrio) son fijas; CTR, CPM y costo por visita se comparan con la mediana
# de la propia cartera (no hay referencia del dueño para eso).

GRUPOS_ETAPA = {   # cómo se agrupan las etapas para leer la cartera
    "escalando": {"texto": "Escalando", "ayuda": "Pasaron el test: aprobadas, renovando o con renovación programada.", "etapas": ("aprobada", "renovando", "renovacion_programada")},
    "test": {"texto": "En test o por salir", "ayuda": "Día 1 en curso, programadas o armadas: lo que se está probando.", "etapas": ("test", "programada", "armada")},
    "apagadas": {"texto": "Apagadas", "ayuda": "No pasaron el test o se apagaron: es el costo de explorar.", "etapas": ("apagar", "apagada")},
}
REF_CR_TIENDA = (2.0, 3.6)
REF_AOV_VECES = 1.5
REF_LLEGADA = 0.6          # visitas a la landing ÷ clics en el enlace: por debajo se pierden clics antes de que cargue la página
MIN_VISITAS_TASA = 60      # con menos visitas, el % del embudo es ruido
MIN_IMPRESIONES = 1500


def _mediana(xs: list[float]) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def _f(x: float | None, d: int = 1, suf: str = "") -> str:
    return "—" if x is None else (f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf)


def _fila_desglose(o: dict[str, Any]) -> dict[str, Any]:
    m, e, k = o.get("meta") or {}, o.get("embudo") or {}, o.get("kpis") or {}
    gasto = _num(o.get("gasto_meta")) or 0.0
    imp, clk = _num(m.get("impresiones")) or 0.0, _num(m.get("clics_enlace")) or 0.0
    vis = _num(e.get("visitas")) if not e.get("incompleto") else None
    etapa = o.get("etapa") or {}
    grupo = next((g for g, v in GRUPOS_ETAPA.items() if etapa.get("clave") in v["etapas"]), "test")
    return {
        "id": o["id"], "nombre": o["nombre"], "mercado": o.get("mercado"), "etapa": {"clave": etapa.get("clave"), "texto": etapa.get("texto"), "tono": etapa.get("tono")},
        "grupo": grupo, "pastilla": (o.get("accion_sugerida") or {}).get("clave"),
        "ganancia_neta": o.get("ganancia_neta"), "contra_meta": o.get("ganancia_contra_meta"), "gasto": o.get("gasto_meta"),
        "bruto": o.get("bruto"), "neto": o.get("neto"), "comisiones": o.get("comisiones"),
        "produccion": (o.get("costos") or {}).get("produccion"), "fijos": (o.get("costos") or {}).get("fijos"),
        "ventas": o.get("ventas_n") or 0, "cpa": o.get("cpa"), "equilibrio": o.get("equilibrio"), "equilibrio_fuente": o.get("equilibrio_fuente"),
        "roas_neto": o.get("roas_neto"), "aov": k.get("aov"), "aov_veces": k.get("aov_veces_principal"), "precio_principal": k.get("precio_principal"),
        "visitas": vis, "checkouts": e.get("checkout") if vis is not None else None,
        "cr": e.get("pct_compra_visita") if vis else None, "pct_checkout": e.get("pct_checkout") if vis else None, "pct_compra": e.get("pct_compra") if vis else None,
        "impresiones": int(imp), "clics": int(clk),
        "ctr": _r(100 * clk / imp, 2) if imp else None, "cpm": _r(1000 * gasto / imp) if imp else None, "cpc": _r(gasto / clk) if clk else None,
        "costo_visita": _r(gasto / vis) if vis else None, "llegada": _r(vis / clk, 2) if vis is not None and clk else None,
        "embudo_parcial": bool(e.get("parcial")),
    }


def _palancas(f: dict[str, Any], med: dict[str, float | None]) -> list[dict[str, Any]]:
    """Qué empuja la oferta para arriba (sube) y para abajo (baja), del anuncio a la venta. Cada palanca: texto corto, detalle, tono y
    un puntaje de cuánto se aparta de su referencia (para ordenar y elegir el cuello de botella)."""
    out: list[dict[str, Any]] = []

    def add(clave: str, paso: str, sube: bool, corto: str, detalle: str, desvio: float) -> None:
        out.append({"clave": clave, "paso": paso, "sentido": "sube" if sube else "baja", "tono": "ok" if sube else "error",
                    "corto": corto, "detalle": detalle, "desvio": round(abs(desvio), 3)})

    gasto = f["gasto"] or 0
    if f["ventas"] and f["cpa"] is not None and f["equilibrio"]:
        r = f["cpa"] / f["equilibrio"]
        if r <= 0.9 or r >= 1.1:
            add("cpa", "venta", r < 1, f"CPA {_usd(f['cpa'])} vs {_usd(f['equilibrio'])}",
                f"Cada venta cuesta {_usd(f['cpa'])} en Meta y deja {_usd(f['equilibrio'])} neto ({'gana' if r < 1 else 'pierde'} {_usd(abs(f['equilibrio'] - f['cpa']))} por venta).", 1 - r)
    elif not f["ventas"] and gasto >= 5:
        add("sin_ventas", "venta", False, f"{_usd(gasto)} sin ventas", f"Gastó {_usd(gasto)} en Meta y todavía no vendió.", 1)
    if f["impresiones"] >= MIN_IMPRESIONES and f["ctr"] is not None and med.get("ctr"):
        r = f["ctr"] / med["ctr"]
        if r <= 0.75 or r >= 1.25:
            add("ctr", "anuncio", r > 1, f"CTR {_f(f['ctr'], 2, ' %')}", f"De cada 100 que ven el anuncio, {_f(f['ctr'], 2)} hacen clic; la cartera, {_f(med['ctr'], 2)}. {'Los anuncios enganchan más que el promedio.' if r > 1 else 'Los anuncios enganchan poco: el problema empieza en el creativo.'}", r - 1)
    if f["impresiones"] >= MIN_IMPRESIONES and f["cpm"] is not None and med.get("cpm"):
        r = f["cpm"] / med["cpm"]
        if r <= 0.7 or r >= 1.4:
            add("cpm", "trafico", r < 1, f"CPM {_usd(f['cpm'])}", f"Mil impresiones cuestan {_usd(f['cpm'])}; la mediana de la cartera, {_usd(med['cpm'])}. {'El mercado es barato.' if r < 1 else 'El mercado o la subasta son caros.'}", 1 - r)
    # con el día de hoy en curso la tienda puede ir atrasada respecto de Meta: la llegada solo se juzga con días cerrados
    if f["llegada"] is not None and f["clics"] >= 50 and f["llegada"] < REF_LLEGADA and not f["embudo_parcial"]:
        add("llegada", "landing", False, f"Solo llega el {_f(100 * f['llegada'], 0, ' %')} de los clics",
            f"{f['clics']} clics en el enlace y {int(f['visitas'] or 0)} visitas a la landing: se pierden clics antes de que cargue la página (velocidad, enlace o rebote instantáneo).", REF_LLEGADA - f["llegada"])
    if f["visitas"] and f["visitas"] >= MIN_VISITAS_TASA and f["pct_checkout"] is not None:
        bajo, alto = REF_CHECKOUT
        if f["pct_checkout"] < bajo or f["pct_checkout"] > alto:
            sube = f["pct_checkout"] > alto
            add("checkout", "landing", sube, f"Checkout {_f(f['pct_checkout'], 1, ' %')}", f"El {_f(f['pct_checkout'], 1)} % de las visitas llega al pago (ref. 8-12 %). {'La landing convence.' if sube else 'La landing o la oferta no convencen: pocos pasan al pago.'}", (f["pct_checkout"] - (alto if sube else bajo)) / bajo)
    if (f["checkouts"] or 0) >= 10 and f["pct_compra"] is not None:
        bajo, alto = REF_COMPRA
        if f["pct_compra"] < bajo or f["pct_compra"] > alto:
            sube = f["pct_compra"] > alto
            add("compra", "checkout", sube, f"Compra {_f(f['pct_compra'], 0, ' %')}", f"El {_f(f['pct_compra'], 0)} % de los que llegan al pago compra (ref. 25-30 %). {'El checkout cierra bien.' if sube else 'Se caen en el checkout: precio, medios de pago o confianza.'}", (f["pct_compra"] - (alto if sube else bajo)) / bajo)
    if f["visitas"] and f["visitas"] >= MIN_VISITAS_TASA and f["cr"] is not None:
        bajo, alto = REF_CR_TIENDA
        if f["cr"] < bajo or f["cr"] > alto:
            sube = f["cr"] > alto
            add("cr", "landing", sube, f"CR {_f(f['cr'], 2, ' %')}", f"Compra el {_f(f['cr'], 2)} % de las visitas (ref. 2-3,6 %).", (f["cr"] - (alto if sube else bajo)) / bajo)
    if f["ventas"] >= 3 and f["aov_veces"] is not None:
        if f["aov_veces"] >= REF_AOV_VECES or f["aov_veces"] < 1.15:
            sube = f["aov_veces"] >= REF_AOV_VECES
            add("aov", "backend", sube, f"AOV {_f(f['aov_veces'], 2, ' ×')}", f"Cada comprador deja {_usd(f['aov'])}, {_f(f['aov_veces'], 2)} veces el principal (ref. 1,5 ×). {'Bump y upsells suben el ticket.' if sube else 'Casi nadie suma bump o upsell: el ticket no sube.'}", f["aov_veces"] / REF_AOV_VECES - 1)
    if f["costo_visita"] is not None and med.get("costo_visita") and f["visitas"] and f["visitas"] >= MIN_VISITAS_TASA:
        r = f["costo_visita"] / med["costo_visita"]
        if r <= 0.7 or r >= 1.4:
            add("costo_visita", "trafico", r < 1, f"Visita a {_usd(f['costo_visita'])}", f"Cada visita a la landing cuesta {_usd(f['costo_visita'])}; la mediana de la cartera, {_usd(med['costo_visita'])}.", 1 - r)
    prod = f["produccion"] or 0
    if prod > 0 and (f["contra_meta"] or 0) >= 0 and (f["ganancia_neta"] or 0) < 0:
        add("produccion", "costos", False, f"Producción {_usd(prod)}", f"Contra Meta gana {_usd(f['contra_meta'])}, pero todavía no recupera la producción ({_usd(prod)}).", 0.5)
    elif prod > 0 and not gasto:
        add("produccion", "costos", False, f"Producción {_usd(prod)}", f"Ya se pagó la producción ({_usd(prod)}) y todavía no hay pauta.", 0.2)
    return sorted(out, key=lambda p: -p["desvio"])


def _motivo(f: dict[str, Any], palancas: list[dict[str, Any]]) -> str:
    g, cm, gasto = f["ganancia_neta"] or 0, f["contra_meta"] or 0, f["gasto"] or 0
    baja = [p for p in palancas if p["sentido"] == "baja" and p["clave"] not in ("cpa", "sin_ventas", "produccion")]
    sube = [p for p in palancas if p["sentido"] == "sube" and p["clave"] != "cpa"]
    nombres = {"anuncio": "los anuncios", "trafico": "el costo del tráfico", "landing": "la landing", "checkout": "el checkout", "backend": "el ticket", "costos": "los costos"}
    if not gasto and not f["ventas"]:
        return "Todavía sin pauta: solo pesa la producción." if (f["produccion"] or 0) > 0 else "Sin movimiento en el período."
    if g > 0:
        base = f"Gana: cada venta cuesta {_usd(f['cpa'])} y deja {_usd(f['equilibrio'])}." if f["cpa"] is not None else "Gana."
        return base + (f" Empuja {nombres.get(sube[0]['paso'], sube[0]['paso'])} ({sube[0]['corto']})." if sube else "")
    if cm >= 0 and g < 0:
        return f"Contra Meta gana {_usd(cm)}; lo que falta es recuperar la producción."
    if not f["ventas"]:
        return f"Gastó {_usd(gasto)} sin vender." + (f" Se corta en {nombres.get(baja[0]['paso'], baja[0]['paso'])} ({baja[0]['corto']})." if baja else " Con tan poco tráfico todavía no se ve dónde se corta.")
    base = f"Pierde: cada venta cuesta {_usd(f['cpa'])} y deja {_usd(f['equilibrio'])}."
    return base + (f" El cuello está en {nombres.get(baja[0]['paso'], baja[0]['paso'])} ({baja[0]['corto']})." if baja else " Ningún paso del embudo se sale de su referencia: falta volumen para ver el cuello.")


def _cuando_apagada(ts: list[dict[str, Any]]) -> str | None:
    """Cuándo se apagó la oferta (17-nov, para ordenar el menú): la hora del apagado más reciente de sus tests; si nunca hubo
    apagado registrado (cierre a pedido), la del cierre; si tampoco, el cambio de estado. Nunca el corte: ese es la última lectura."""
    fechas = []
    for t in ts:
        for campo in ("apagado", "cierre"):
            v = t.get(campo)
            if isinstance(v, dict) and parsear_fecha(v.get("cuando")):
                fechas.append((0 if campo == "apagado" else 1, v["cuando"]))
        if parsear_fecha(t.get("estado_desde")):
            fechas.append((2, t["estado_desde"]))
    if not fechas:
        return None
    mejor = min(p for p, _ in fechas)
    return max((c for p, c in fechas if p == mejor), key=lambda c: parsear_fecha(c))


def _fijos_detalle(fijos: float, fijos_mes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lo que tocó de fijos, abierto por concepto en proporción a su monto mensual (17-nov)."""
    total_mes = sum(_num(c.get("usd_mes")) or 0.0 for c in fijos_mes)
    if not total_mes:
        return []
    return [{"concepto": _texto(c.get("concepto"), 120), "usd_mes": _num(c.get("usd_mes")), "usd": _r(fijos * (_num(c.get("usd_mes")) or 0.0) / total_mes, 2)}
            for c in fijos_mes if _num(c.get("usd_mes"))]


def _sumar_produccion(ofertas: list[dict[str, Any]]) -> dict[str, float]:
    claves = ("kie_usd", "kie_creditos", "renovacion_kie", "gemini_usd", "gemini_imagenes", "voces_usd", "voces_min", "otros_usd")
    t = {k: 0.0 for k in claves}
    for o in ofertas:
        p = o.get("produccion") if isinstance(o.get("produccion"), dict) else {}
        for k in claves:
            t[k] += _num(p.get(k)) or 0.0
        if p.get("kie_creditos"):
            t.setdefault("renovacion_usd", 0.0)
            t["renovacion_usd"] += (_num(p.get("renovacion_kie")) or 0.0) * (_num(p.get("kie_usd")) or 0.0) / (_num(p.get("kie_creditos")) or 1)
    return t


def _det_produccion(p: dict[str, float]) -> str:
    def n(x: float) -> str:
        return f"{x:,.0f}".replace(",", ".")
    partes = []
    if p.get("kie_usd"):
        ren = f", {_usd(p.get('renovacion_usd'))} de renovación y backend" if p.get("renovacion_usd") else ""
        partes.append(f"Kie {_usd(p['kie_usd'])} ({n(p['kie_creditos'])} créditos{ren})")
    if p.get("gemini_usd"):
        partes.append(f"imágenes de Gemini {_usd(p['gemini_usd'])} ({n(p['gemini_imagenes'])})")
    if p.get("voces_usd") or p.get("voces_min"):
        partes.append(f"voces de Gemini {_usd(p.get('voces_usd'))} ({_coma(p.get('voces_min') or 0)} min)")
    if p.get("otros_usd"):
        partes.append(f"otros {_usd(p['otros_usd'])}")
    return " · ".join(partes)


def _det_fijos(det: list[dict[str, Any]], fijos_mes: list[dict[str, Any]]) -> str:
    total_mes = sum((c.get("usd_mes") or 0) for c in fijos_mes)
    partes = [f"{(x['concepto'] or '').split(' (')[0]} {_usd(x['usd'])}" for x in det]
    return " · ".join(partes) + (f" — de {_usd(total_mes)} por mes ({_usd(total_mes / 30)} por día), repartidos entre las ofertas con pauta cada día" if total_mes else "")


def desglose(d: dict[str, Any]) -> dict[str, Any]:
    """Desglose de la ganancia de la cartera por oferta: filas ordenadas de la que más suma a la que más resta, con métricas del
    anuncio a la venta, palancas (qué sube y qué baja) y un motivo en una frase; resumen por grupo de etapa; cascada de la cartera."""
    c = d.get("cartera") or {}
    filas = [_fila_desglose(o) for o in d.get("ofertas") or [] if o.get("con_datos_periodo", True)]
    activas = [f for f in filas if (f["gasto"] or 0) > 0 or f["ventas"] or (f["produccion"] or 0) > 0]
    med = {k: _mediana([f[k] for f in activas if f["impresiones"] >= MIN_IMPRESIONES and f[k] is not None]) for k in ("ctr", "cpm")}
    med["costo_visita"] = _mediana([f["costo_visita"] for f in activas if f["visitas"] and f["visitas"] >= MIN_VISITAS_TASA and f["costo_visita"] is not None])
    for f in activas:
        f["palancas"] = _palancas(f, med)
        f["motivo"] = _motivo(f, f["palancas"])
    activas.sort(key=lambda f: -(f["ganancia_neta"] or 0))
    pos = sum(f["ganancia_neta"] for f in activas if (f["ganancia_neta"] or 0) > 0)
    neg = sum(f["ganancia_neta"] for f in activas if (f["ganancia_neta"] or 0) < 0)
    for f in activas:
        g = f["ganancia_neta"] or 0
        f["peso_pct"] = _r(100 * g / pos, 1) if g > 0 and pos else (_r(100 * g / abs(neg), 1) if g < 0 and neg else 0.0)
    grupos = []
    for clave, v in GRUPOS_ETAPA.items():
        fs = [f for f in activas if f["grupo"] == clave]
        grupos.append({"clave": clave, "texto": v["texto"], "ayuda": v["ayuda"], "ofertas": len(fs),
                       "ganancia_neta": _r(sum(f["ganancia_neta"] or 0 for f in fs)), "contra_meta": _r(sum(f["contra_meta"] or 0 for f in fs)),
                       "gasto": _r(sum(f["gasto"] or 0 for f in fs)), "produccion": _r(sum(f["produccion"] or 0 for f in fs)), "ventas": sum(f["ventas"] for f in fs)})
    ganan = [f for f in activas if (f["ganancia_neta"] or 0) > 0]
    pierden = [f for f in activas if (f["ganancia_neta"] or 0) < 0]
    # qué palanca se repite en las que pierden (patrón de la cartera)
    cuenta: dict[str, dict[str, Any]] = {}
    for f in pierden:
        for p in f["palancas"]:
            if p["sentido"] == "baja" and p["clave"] not in ("cpa", "sin_ventas", "produccion"):
                x = cuenta.setdefault(p["clave"], {"clave": p["clave"], "paso": p["paso"], "ofertas": [], "usd": 0.0})
                x["ofertas"].append(f["nombre"])
                x["usd"] += f["ganancia_neta"] or 0
    patrones = sorted(cuenta.values(), key=lambda x: (-len(x["ofertas"]), x["usd"]))
    cascada = [
        {"clave": "bruto", "texto": "Facturación bruta", "usd": c.get("bruto"), "tipo": "entra"},
        {"clave": "comisiones", "texto": "Comisiones e impuestos", "usd": -(c.get("comisiones") or 0), "tipo": "sale"},
        {"clave": "meta", "texto": "Anuncios en Meta", "usd": -(c.get("gasto_meta") or 0), "tipo": "sale"},
        {"clave": "produccion", "texto": "Producción (productos y creativos)", "usd": -(c.get("produccion") or 0), "tipo": "sale",
         "detalle": _det_produccion(_sumar_produccion(d.get("ofertas") or [])),
         "fuente": "Barrido diario de los registros de gasto de cada carpeta de trabajo (Kie e imágenes de Gemini) y del audio de las voces; si lo anotado a mano es mayor, manda lo anotado. La transcripción (whisper) es local y no cuesta."},
        {"clave": "fijos", "texto": "Costos fijos repartidos", "usd": -(c.get("fijos") or 0), "tipo": "sale",
         "detalle": _det_fijos(_fijos_detalle(c.get("fijos") or 0, c.get("fijos_mes") or []), c.get("fijos_mes") or []),
         "fuente": "Planes y servicios mensuales del libro (costos_fijos_compartidos). Cada día se divide el total mensual por 30 y se reparte entre las ofertas que tuvieron pauta ese día."},
        {"clave": "ganancia", "texto": "Ganancia neta", "usd": c.get("ganancia_neta"), "tipo": "total"},
    ]
    return {
        "filas": activas, "sin_movimiento": len(filas) - len(activas), "medianas": {k: _r(v, 2) for k, v in med.items()},
        "resumen": {"ganan": len(ganan), "ganan_usd": _r(pos), "pierden": len(pierden), "pierden_usd": _r(neg),
                    "mejor": {"id": ganan[0]["id"], "nombre": ganan[0]["nombre"], "usd": ganan[0]["ganancia_neta"]} if ganan else None,
                    "peor": {"id": pierden[-1]["id"], "nombre": pierden[-1]["nombre"], "usd": pierden[-1]["ganancia_neta"]} if pierden else None},
        "grupos": grupos, "patrones": [{**p, "usd": _r(p["usd"]), "n": len(p["ofertas"])} for p in patrones[:4]], "cascada": cascada,
        "referencias": {"checkout": list(REF_CHECKOUT), "compra": list(REF_COMPRA), "cr": list(REF_CR_TIENDA), "aov_veces": REF_AOV_VECES, "llegada": REF_LLEGADA},
    }


# ───────────────────────── «Requiere tu atención» ─────────────────────────

def _usd(x: float | None) -> str:
    if x is None:
        return "—"
    return ("−" if x < 0 else "") + "US$ " + f"{abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _coma(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def atencion(ofertas: list[dict[str, Any]], cartera: dict[str, Any], ref: dict[str, Any], ahora: _dt.datetime) -> list[dict[str, Any]]:
    """Avisos priorizados (crítico → grave → aviso → info), cada uno con la oferta a la que lleva (``oferta``: id o ``None``)."""
    items: list[dict[str, Any]] = []
    for o in ofertas:
        sem = o["semaforo_cpa"]["zona"]
        eq = o["equilibrio"]
        if sem == "sobre":
            items.append({"tono": "grave", "oferta": o["id"], "titulo": f"{o['nombre']}: cada venta cuesta más de lo que deja",
                          "detalle": f"Costo por venta {_usd(o['cpa'])} contra un equilibrio de {_usd(eq)} ({o['ventas_n']} ventas). "
                                     + ("Con pocas ventas es una pista, no un veredicto." if o["ventas_n"] < 10 else "Revisar anuncios y página.")})
        elif sem == "sin_ventas_corte":
            items.append({"tono": "critico", "oferta": o["id"], "titulo": f"{o['nombre']}: gastó 1,5 tickets sin ventas",
                          "detalle": f"Gastó {_usd(o['gasto_meta'])} sin ninguna venta; el corte es {_usd(o['corte_usd'])} (1,5 × {_usd(o['ticket_front'])}). "
                                     + ("La vigilancia la apaga sola." if o["estado"] == "activa" else "")})
        elif sem == "sin_ventas" and o["corte_usd"] and o["gasto_meta"] >= o["ticket_front"]:
            items.append({"tono": "aviso", "oferta": o["id"], "titulo": f"{o['nombre']}: todavía sin ventas",
                          "detalle": f"Lleva {_usd(o['gasto_meta'])}; a los {_usd(o['corte_usd'])} sin ventas se apaga sola."})
        if o["ventas_n"] and o["accion_sugerida"]["clave"] == "cortar":
            items.append({"tono": "critico", "oferta": o["id"], "titulo": f"{o['nombre']}: el costo por venta del día 1 pasó 1,5 tickets",
                          "detalle": o["accion_sugerida"]["porque"] + (" La vigilancia la apaga sola." if o["estado"] == "activa" else "")})
        if o["estado"] == "activa" and o["ventas_n"] == 0 and not o["corte_usd"]:
            items.append({"tono": "grave", "oferta": o["id"], "titulo": f"{o['nombre']}: falta el precio de las tiendas",
                          "detalle": "Sin el precio en USD de las tiendas en la ficha, la regla de 1,5 tickets no se puede aplicar."})
        if o["corte_horas"] is not None and o["corte_horas"] > HORAS_DATOS_VIEJOS and o["estado"] == "activa":
            items.append({"tono": "aviso", "oferta": o["id"], "titulo": f"{o['nombre']}: datos de hace {o['corte_horas']:.0f} horas",
                          "detalle": "Los números tienen más de un día. Pídele al agente la revisión del funnel para ponerlos al día."})
        if o["diferencia_atribucion"] > 0:
            items.append({"tono": "aviso", "oferta": o["id"], "titulo": f"{o['nombre']}: Meta cuenta más compras que las reales",
                          "detalle": f"Meta atribuye {o['compras_meta']} compras y la tienda registró {o['ventas_n']}. Puede haber eventos duplicados en el medidor."})
        e = o["embudo"]
        if o["estado"] == "activa" and e["tono_compra"] == "aviso" and e["checkout"] >= 10:
            items.append({"tono": "info", "oferta": o["id"], "titulo": f"{o['nombre']}: se pierden compras en la pantalla de pago",
                          "detalle": f"Compra {_coma(e['pct_compra'])} % de los checkouts (referencia 25-30 %)." + (" Con menos de 30 checkouts es una pista." if e["pocos_datos"] else "")})
        if o["estado"] == "activa" and e["tono_checkout"] == "aviso" and e["visitas"] >= 50:
            items.append({"tono": "info", "oferta": o["id"], "titulo": f"{o['nombre']}: la página convence poco",
                          "detalle": f"Llega al pago el {_coma(e['pct_checkout'])} % de las visitas (referencia 8-12 %)."})
        b = o.get("backend") or {}
        if b.get("falta"):
            items.append({"tono": "aviso", "oferta": o["id"], "titulo": f"{o['nombre']}: pasó el test y no tiene backend",
                          "detalle": ("El backend está en pausa: no vende. " if b.get("estado") == "pausado" else "")
                                     + "Los upsells post-compra se arman después del test (guía 11 de modelar-y-lanzar-oferta) y quedan activos al crearlos."})
        if o["estado"] == "programada":
            ini = parsear_fecha(o["inicio_texto"])
            if ini and ini <= ahora:
                items.append({"tono": "aviso", "oferta": o["id"], "titulo": f"{o['nombre']}: ya debería estar en marcha",
                              "detalle": "El libro la tiene como programada y la hora de inicio pasó. Actualiza el estado en la próxima revisión."})
            elif ini:
                items.append({"tono": "info", "oferta": o["id"], "titulo": f"{o['nombre']}: arranca el {ini.strftime('%d-%m')} a las {ini.strftime('%H:%M')} (hora del mercado)",
                              "detalle": f"Equilibrio {'estimado ' if o['equilibrio_fuente'] == 'estimado' else ''}{_usd(eq)} por venta: el costo por venta tiene que quedar por debajo."})
    if cartera.get("fijos_pendientes"):
        items.append({"tono": "info", "oferta": None, "titulo": "Falta un costo fijo en la cuenta",
                      "detalle": "Sin el monto de: " + ", ".join(cartera["fijos_pendientes"]) + ". La ganancia neta no lo incluye hasta que lo cargues."})
    return items


# ───────────────────────── período (filtro de días) ─────────────────────────
#
# Pedido del dueño (2026-11-12): filtrar por un día, un rango, hoy, ayer, últimos 7/14/30, este mes, mes anterior o desde el inicio.
# Los días se cuentan en la zona horaria de la cuenta publicitaria (``zona_horaria_cuenta`` del libro; Meta corta los días así).
# Con un período: Meta (campaña y anuncio) y ventas se suman por día; la producción entra solo si el día de inicio de la pauta cae
# dentro; los fijos se reparten por día de pauta del período; el embudo de la tienda solo se muestra si hay lectura de TODOS los días
# con pauta del período (si falta uno: «sin dato completo»). El veredicto (Escalar, Mirar, Apagar…) se calcula SIEMPRE desde el inicio.

ZONA_POR_DEFECTO = "America/Argentina/Buenos_Aires"


def zona_de(libro: Any) -> _dt.tzinfo:
    from zoneinfo import ZoneInfo
    nombre = libro.get("zona_horaria_cuenta") if isinstance(libro, dict) and isinstance(libro.get("zona_horaria_cuenta"), str) else ZONA_POR_DEFECTO
    try:
        return ZoneInfo(nombre)
    except Exception:  # noqa: BLE001 - zona desconocida: la de la cuenta por defecto
        return ZoneInfo(ZONA_POR_DEFECTO)


def dia_de(texto: Any, zona: _dt.tzinfo) -> _dt.date | None:
    """Día (en la zona de la cuenta) de una fecha ISO; «AAAA-MM-DD» sola se toma tal cual."""
    if isinstance(texto, str) and len(texto) == 10:
        try:
            return _dt.date.fromisoformat(texto)
        except ValueError:
            return None
    d = parsear_fecha(texto)
    return d.astimezone(zona).date() if d else None


def _sumar(filas: list[dict[str, Any]], clave: str) -> float | None:
    vals = [_num(f.get(clave)) for f in filas]
    return sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None


def dias_de_pauta(t: dict[str, Any], zona: _dt.tzinfo, ahora: _dt.datetime,
                  desde: _dt.date | None = None, hasta: _dt.date | None = None) -> list[_dt.date]:
    """Días de la cuenta con pauta de un test: desde el día de inicio (si ya llegó) hasta hoy o, si está pausado o cerrado,
    hasta el día de su último corte. Lo usan los fijos de «Desde el inicio» y de cualquier período, así un rango que
    cubre todos los días da lo mismo que «Desde el inicio» y la suma de los días da el rango (dueño, 15-nov)."""
    ini_dt = parsear_fecha(t.get("inicio"))
    if not ini_dt or ini_dt > ahora:
        return []
    inicio = dia_de(t.get("inicio"), zona)
    hoy = ahora.astimezone(zona).date()
    fin = min(hasta or hoy, hoy)
    if _ESTADOS.get(str(t.get("estado", "")).lower()) != "activa" and (dc := dia_de(t.get("corte"), zona)):
        fin = min(fin, dc)
    d = max(desde or inicio, inicio)
    dias = []
    while d <= fin:
        dias.append(d)
        d += _dt.timedelta(days=1)
    return dias


def libro_del_periodo(libro: dict[str, Any], desde: _dt.date, hasta: _dt.date, ahora: _dt.datetime) -> dict[str, Any]:
    """Copia del libro con cada test reducido a los días [desde, hasta] (ver el encabezado de esta sección)."""
    import copy
    zona = zona_de(libro)
    hoy = ahora.astimezone(zona).date()
    L = copy.deepcopy(libro)
    L["_hasta"] = hasta.isoformat()
    for t in L.get("tests") or []:
        if not isinstance(t, dict):
            continue
        inicio = dia_de(t.get("inicio"), zona)
        hist = [h for h in t.get("historial_diario") or [] if isinstance(h, dict) and (d := dia_de(h.get("fecha"), zona)) and desde <= d <= hasta]
        meta = {k: (_sumar(hist, k) or 0) for k in ("gasto_usd", "impresiones", "clics_enlace", "visitas_landing_meta", "inicios_pago_meta", "compras_meta")}
        valor = _sumar(hist, "valor_compras_meta_usd")
        if valor is not None:
            meta["valor_compras_meta_usd"] = valor
        # Gasto de Meta SIN desglose por día (dueño, 14-nov: «aparecen las ventas pero no el gasto de Meta»). Si el total de Meta del test
        # supera lo que suman sus días, ese gasto no se puede ubicar en el período: si toda la pauta del test cae dentro, vale el total;
        # si no, el período queda marcado «Meta sin desglose por día» y el panel muestra «—», nunca un 0 inventado.
        meta_total = t.get("meta") if isinstance(t.get("meta"), dict) else {}
        sin_dia = (_num(meta_total.get("gasto_usd")) or 0) - sum(_num(h.get("gasto_usd")) or 0 for h in t.get("historial_diario") or [] if isinstance(h, dict))
        if sin_dia > 0.5:
            ultimo = dia_de(t.get("corte"), zona) or hoy
            if inicio and desde <= inicio and ultimo <= hasta:
                meta = {k: _num(meta_total.get(k)) or 0 for k in ("gasto_usd", "impresiones", "clics_enlace", "visitas_landing_meta", "inicios_pago_meta", "compras_meta")}
                if _num(meta_total.get("valor_compras_meta_usd")) is not None:
                    meta["valor_compras_meta_usd"] = _num(meta_total.get("valor_compras_meta_usd"))
            elif inicio and inicio <= hasta and ultimo >= desde:
                t["_meta_sin_dia"] = round(sin_dia, 2)
        t["meta"] = meta
        t["historial_diario"] = hist   # sin esto, los días fuera del período quedaban con gasto y sin ventas (−377 el 14/11 visto desde «Hoy»)
        t["_ventas_todas"] = t.get("ventas") or []   # para el neto por comprador de la ventana móvil (no se recorta)
        t["ventas"] = [v for v in t.get("ventas") or [] if isinstance(v, dict) and (d := dia_de(v.get("dia_cuenta") or v.get("fecha"), zona)) and desde <= d <= hasta]
        if not (inicio and desde <= inicio <= hasta):
            prod = t.get("produccion") if isinstance(t.get("produccion"), dict) else {}
            t["produccion"] = {"kie_creditos": 0, "gemini_imagenes": 0, "otros_usd": 0,
                               "nota": f"La producción ({prod.get('nota') or 'Kie y Gemini'}) se imputa al día de inicio de la pauta, fuera de este período."}
        # días de pauta dentro del período (para fijos y para exigir el embudo de cada día)
        dias_pauta = dias_de_pauta(t, zona, ahora, desde, hasta)
        t["_dias_periodo"] = len(dias_pauta)
        t["_dias_lista"] = [d.isoformat() for d in dias_pauta]
        regs = {dia_de(r.get("fecha"), zona): r for r in t.get("tienda_embudo_diario") or [] if isinstance(r, dict)}
        e0 = t.get("tienda_embudo") if isinstance(t.get("tienda_embudo"), dict) else {}
        sin_embudo_propio = not regs and not any(_num(e0.get(k)) for k in ("landing", "checkout", "compras"))
        if sin_embudo_propio:   # test sin tienda propia ni visitas (p. ej. otra tanda de la misma oferta): no aporta ni falta
            t["tienda_embudo"] = {"landing": 0, "checkout": 0, "compras": 0}
        elif dias_pauta and all(d in regs for d in dias_pauta):
            sel = [regs[d] for d in dias_pauta]
            t["tienda_embudo"] = {k: _sumar(sel, k) or 0 for k in ("landing", "checkout", "compras")}
            # detalle por tienda del funnel (dueño, 14-nov: el CR de cada tienda en Impultienda no sirve; se suman todas)
            pt: dict[str, dict[str, float]] = {}
            for r in sel:
                for s, e in (r.get("por_tienda") or {}).items():
                    if isinstance(e, dict):
                        acc = pt.setdefault(str(s), {"landing": 0, "checkout": 0, "compras": 0})
                        for k in acc:
                            acc[k] += _num(e.get(k)) or 0
            if pt:
                t["tienda_embudo"]["por_tienda"] = pt
            t["tienda_embudo"]["parcial"] = any(r.get("parcial") for r in sel)
            t["tienda_embudo"]["_periodo"] = "; ".join(r.get("nota") or f"leído {r.get('leido', '')}" for r in sel if r.get("parcial") or r.get("nota"))
        elif dias_pauta:
            t["tienda_embudo"] = {"incompleto": True, "_periodo": "Sin dato completo para este período: falta la lectura de Impultienda de algún día."}
        else:
            t["tienda_embudo"] = {"landing": 0, "checkout": 0, "compras": 0, "_periodo": "Sin pauta en este período."}
        # anuncios: se suman los días del período; los datos fijos (nombre, conjunto, estado) salen de la lista
        a = t.get("anuncios")
        if isinstance(a, dict) and isinstance(a.get("lista"), list):
            if isinstance(a.get("por_dia"), list):
                suma: dict[str, dict[str, float]] = {}
                for r in a["por_dia"]:
                    if isinstance(r, dict) and (d := dia_de(r.get("fecha"), zona)) and desde <= d <= hasta:
                        acc = suma.setdefault(str(r.get("id")), {})
                        for k in (*_SUMABLES_AD, "valor_compras_meta_usd"):
                            v = _num(r.get(k))
                            if v is not None:
                                acc[k] = acc.get(k, 0) + v
                nueva = []
                for x in a["lista"]:
                    acc = suma.get(str(x.get("id")), {})
                    y = {k: x.get(k) for k in ("id", "nombre", "conjunto_id", "conjunto", "estado", "miniatura", "creativo_id")}
                    y.update({k: acc.get(k, 0) for k in _SUMABLES_AD})
                    y["valor_compras_meta_usd"] = acc.get("valor_compras_meta_usd")
                    nueva.append(y)
                a["lista"] = nueva
                a["leido"] = a.get("por_dia_leido") or a.get("leido")
            else:
                a["lista"] = []
                a["_sin_por_dia"] = True
        t["_con_datos"] = bool(hist or t["ventas"] or t.get("_meta_sin_dia") or (t["meta"].get("gasto_usd") or 0) > 0)
    return L


def calcular_periodo(libro: Any, ahora: _dt.datetime, desde: _dt.date | None, hasta: _dt.date | None) -> dict[str, Any]:
    """Modelo del tablero para un período. Sin período (o desde-hasta que cubren todo): ``calcular`` tal cual («Desde el inicio»).
    El veredicto, la frase y lo programado de cada oferta salen SIEMPRE del cálculo desde el inicio."""
    L = libro if isinstance(libro, dict) else {}
    zona = zona_de(L)
    hoy = ahora.astimezone(zona).date()
    inicios = [d for d in (dia_de(t.get("inicio"), zona) for t in L.get("tests") or [] if isinstance(t, dict)) if d]
    primer_dia = min(inicios) if inicios else hoy
    total = calcular(L, ahora)
    base = {"zona": getattr(zona, "key", str(zona)), "hoy": hoy.isoformat(), "primer_dia": primer_dia.isoformat()}
    if desde is None and hasta is None:
        total["periodo"] = {**base, "todo": True, "desde": None, "hasta": None, "con_datos": True}
        total["desglose"] = desglose(total)
        return total
    desde = desde or primer_dia
    hasta = hasta or hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    d = calcular(libro_del_periodo(L, desde, hasta, ahora), ahora)
    fijos = {o["id"]: o for o in total["ofertas"]}
    for o in d["ofertas"]:
        t = fijos.get(o["id"])
        if t:
            for k in ("accion_sugerida", "frase", "programado", "fase", "fin_test", "corte_usd", "semaforo_cpa", "veredicto", "etapa", "backend", "renovaciones"):
                if k in t:
                    o[k] = t[k]
    d["atencion"] = total["atencion"]
    d["corte"] = total["corte"]
    # la «ganancia del último día» es siempre la del último día completo, elijas el período que elijas (dueño, 15-nov)
    for k in ("ganancia_ultimo_dia", "ultimo_dia_completo", "meta_ganancia_dia"):
        d["cartera"][k] = total["cartera"][k]
    for o in d["ofertas"]:
        t = fijos.get(o["id"])
        if t:
            for k in ("ganancia_ultimo_dia", "ultimo_dia"):
                o["kpis"][k] = t["kpis"][k]
    for k in ("etapas", "con_backend", "falta_backend"):   # la etapa no depende del período
        d["cartera"][k] = total["cartera"][k]
    con_datos = any(o.get("con_datos_periodo") for o in d["ofertas"])
    d["periodo"] = {**base, "todo": False, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": (hasta - desde).days + 1, "con_datos": con_datos}
    d["desglose"] = desglose(d)
    return d
