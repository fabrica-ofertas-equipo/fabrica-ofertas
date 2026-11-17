"""Robot 5 · Perfil por idioma (23:40), EN SOMBRA: resume lo vendido y gastado por idioma en los últimos 7 días. La FASE (crece / estable / se cansa / cae),
la meta y el tope NO se calculan: la fuente no da los umbrales (E-09) y calcularlos «a ojo» sería inventar.

Fuentes, en este orden: la base (``fact_pedido`` y ``fact_meta_ad_dia``, solo lectura) y, si no hay base, los KPI diarios
``ofertas/<id>/08-operacion/diario/<fecha>/kpi_oferta_dia.json``. El idioma de cada oferta sale de ``ofertas/<id>/mercado.json`` (``locale``).
Dinero: enteros en unidad menor, SIEMPRE por moneda (nunca se suman monedas distintas). Sin ``float``.
"""
from __future__ import annotations

import datetime as _dt
import re
from collections import defaultdict
from typing import Any

from scripts.alertas.hechos import limpiar_texto
from scripts.robots.nucleo import RX_OFERTA_REAL, Contexto, Resultado, ofertas_en_base, tabla_existe

ID = "perfil"
DIAS = 7
_RX_MONEDA_MENOR = re.compile(r"^([A-Z]{3})_minor$")
_PAGADO = ("paid", "pagado")


def _ventana(fecha: str, dias: int = DIAS) -> list[str]:
    f = _dt.date.fromisoformat(fecha)
    return [(f - _dt.timedelta(days=dias - 1 - i)).isoformat() for i in range(dias)]


def locale_de(c: Contexto, oferta_id: str) -> str | None:
    """``locale`` de ``mercado.json`` (o del brief); ``None`` si no se sabe. Es dato de archivo: se limpia."""
    raiz = c.ctx().oferta(oferta_id)
    lec = raiz.json("mercado.json")
    if lec.ok and isinstance(lec.dato, dict) and isinstance(lec.dato.get("locale"), str):
        return limpiar_texto(lec.dato["locale"], 12) or None
    lec = raiz.yaml("00-brief.yaml")
    if lec.ok and isinstance(lec.dato, dict) and isinstance(lec.dato.get("mercado_objetivo"), dict):
        loc = lec.dato["mercado_objetivo"].get("locale")
        if isinstance(loc, str):
            return limpiar_texto(loc, 12) or None
    return None


def _desde_base(conn: Any, oferta_id: str, dias: list[str]) -> dict[str, Any] | None:
    """Ventas, ingresos y gasto de una oferta por día, desde la base. ``None`` si la base no tiene nada de esa oferta en la ventana."""
    por_dia: dict[str, dict[str, Any]] = {d: {"ventas": 0, "ingresos": defaultdict(int), "gasto": defaultdict(int)} for d in dias}
    hubo = False
    if tabla_existe(conn, "fact_pedido"):
        marcas = ",".join("?" * len(_PAGADO))
        for dia, monto, moneda in conn.execute(
                f"SELECT dia_utc, monto_minor, moneda FROM fact_pedido WHERE oferta_id = ? AND es_prueba = 0 AND es_interna = 0 "  # noqa: S608
                f"AND estado IN ({marcas}) AND dia_utc >= ? AND dia_utc <= ?", (oferta_id, *_PAGADO, dias[0], dias[-1])):
            if str(dia) not in por_dia:
                continue
            por_dia[str(dia)]["ventas"] += 1
            por_dia[str(dia)]["ingresos"][str(moneda)] += int(monto)
            hubo = True
    if tabla_existe(conn, "fact_meta_ad_dia"):
        for fecha, gasto, moneda in conn.execute(
                "SELECT fecha, gasto_minor, moneda FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha >= ? AND fecha <= ?", (oferta_id, dias[0], dias[-1])):
            if str(fecha) not in por_dia:
                continue
            por_dia[str(fecha)]["gasto"][str(moneda)] += int(gasto)
            hubo = True
    return por_dia if hubo else None


def _desde_kpi(c: Contexto, oferta_id: str, dias: list[str]) -> dict[str, Any] | None:
    por_dia: dict[str, dict[str, Any]] = {d: {"ventas": 0, "ingresos": defaultdict(int), "gasto": defaultdict(int)} for d in dias}
    hubo = False
    for d in dias:
        lec = c.ctx().oferta(oferta_id).json(f"08-operacion/diario/{d}/kpi_oferta_dia.json")
        if not lec.ok or not isinstance(lec.dato, dict):
            continue
        for fila in (lec.dato.get("filas") if isinstance(lec.dato.get("filas"), list) else [])[:80]:
            if not isinstance(fila, dict):
                continue
            v, unidad = fila.get("valor"), fila.get("unidad")
            if not isinstance(v, int) or isinstance(v, bool):
                continue
            hubo = True
            if fila.get("kpi_id") == "compras_stripe":
                por_dia[d]["ventas"] += v
            m = _RX_MONEDA_MENOR.match(unidad) if isinstance(unidad, str) else None
            if m and fila.get("kpi_id") == "gasto_meta":
                por_dia[d]["gasto"][m.group(1)] += v
            elif m and fila.get("kpi_id") in ("ingresos_brutos", "ingresos"):
                por_dia[d]["ingresos"][m.group(1)] += v
    return por_dia if hubo else None


def _sumar(por_dia: dict[str, Any], dias: list[str]) -> dict[str, Any]:
    ventas = sum(por_dia[d]["ventas"] for d in dias)
    ingresos: dict[str, int] = defaultdict(int)
    gasto: dict[str, int] = defaultdict(int)
    for d in dias:
        for m, v in por_dia[d]["ingresos"].items():
            ingresos[m] += v
        for m, v in por_dia[d]["gasto"].items():
            gasto[m] += v
    return {"ventas": ventas, "ingresos": dict(sorted(ingresos.items())), "gasto": dict(sorted(gasto.items()))}


def correr(c: Contexto) -> Resultado:
    dias = _ventana(c.fecha_cuenta)
    fuente = None
    por_oferta: dict[str, dict[str, Any]] = {}
    with c.abrir_db() as conn:
        if conn is not None:
            fuente = "base de datos (solo lectura)"
            for oid in ofertas_en_base(conn):
                datos = _desde_base(conn, oid, dias)
                if datos is not None:
                    por_oferta[oid] = datos
    if not por_oferta:
        # Sin base (o sin nada en la ventana): se prueba con los KPI diarios de las ofertas reales.
        for oid in c.hechos()["ofertas"]["ids_reales"]:
            if RX_OFERTA_REAL.match(oid):
                datos = _desde_kpi(c, oid, dias)
                if datos is not None:
                    por_oferta[oid] = datos
                    fuente = "KPI diarios de ofertas/*/08-operacion/diario"
    if not por_oferta:
        motivo = "la base no tiene nada de esos días" if fuente else "no hay base de datos (empresa/datos/fabrica.db) ni KPI diarios"
        return Resultado("sin_datos", f"sin datos: {motivo}; no hay nada vendido por idioma que resumir",
                         [f"Ventana {dias[0]} a {dias[-1]}: {motivo}.", "Sin datos no se inventa ningún perfil: ni resumen, ni fase, ni meta."],
                         datos={"ventana": {"desde": dias[0], "hasta": dias[-1]}, "idiomas": [], "fuente": fuente, "fase": None})
    por_idioma: dict[str, dict[str, Any]] = {}
    for oid, datos in sorted(por_oferta.items()):
        loc = locale_de(c, oid) or "sin_idioma"
        acum = por_idioma.setdefault(loc, {"idioma": loc, "ofertas": [], "por_dia": {d: {"ventas": 0, "ingresos": defaultdict(int), "gasto": defaultdict(int)} for d in dias}})
        acum["ofertas"].append(oid)
        for d in dias:
            acum["por_dia"][d]["ventas"] += datos[d]["ventas"]
            for m, v in datos[d]["ingresos"].items():
                acum["por_dia"][d]["ingresos"][m] += v
            for m, v in datos[d]["gasto"].items():
                acum["por_dia"][d]["gasto"][m] += v
    idiomas = []
    for loc in sorted(por_idioma):
        a = por_idioma[loc]
        idiomas.append({"idioma": loc, "ofertas": a["ofertas"], "ultimos_7_dias": _sumar(a["por_dia"], dias),
                        "ultimos_3_dias": _sumar(a["por_dia"], dias[-3:]), "7_dias_anteriores_a_los_ultimos_3": _sumar(a["por_dia"], dias[:-3]),
                        "ventas_por_dia": [a["por_dia"][d]["ventas"] for d in dias],
                        "fase": None, "fase_motivo": "umbrales de fase sin definir (E-09): no se calcula crece / estable / se cansa / cae"})
    doc = {"tipo": "perfil_por_idioma_sombra", "es_propuesta": True, "fecha": c.fecha_cuenta, "ventana": {"desde": dias[0], "hasta": dias[-1], "dias": dias},
           "fuente": fuente, "idiomas": idiomas, "meta": None, "tope": None,
           "nota": "Resumen de lo cobrado y gastado; no mezcla monedas. Fase, meta y tope quedan sin calcular hasta tener umbrales firmados (E-09, H-02)."}
    salida = c.guardar(ID, doc)
    resumen = [f"Ventana {dias[0]} a {dias[-1]} · fuente: {fuente}"]
    for i in idiomas:
        u = i["ultimos_7_dias"]
        ing = " · ".join(f"{v} {m} (unidad menor)" for m, v in u["ingresos"].items()) or "sin ingresos"
        gas = " · ".join(f"{v} {m} (unidad menor)" for m, v in u["gasto"].items()) or "sin gasto"
        resumen.append(f"  {i['idioma']}: {u['ventas']} ventas · cobrado {ing} · gastado {gas} · fase: sin calcular")
    return Resultado("parcial", f"resumen de {len(idiomas)} idioma(s) con {sum(len(i['ofertas']) for i in idiomas)} oferta(s); la fase no se calcula (faltan umbrales E-09)",
                     resumen, datos=doc, salidas=[salida] if salida else [])
