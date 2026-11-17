"""Robot 10 · Auditor (cada hora), EN SOMBRA: el primer auditor honesto. Juzga cada decisión de D8 con lo que pasó DESPUÉS y mide el acierto de los
CORTES (MATAR) y de las SUBAS (ESCALAR) por separado. No degrada a nadie: propone.

Lee ``ofertas/<id>/08-operacion/decisiones.jsonl`` (``contratos/decision.schema.json``), los pedidos cobrados y el gasto de Meta (base en solo lectura)
y ``03-oferta/economia.json`` (CPA de equilibrio). Sin decisiones o sin base dice «sin datos»; nunca inventa un acierto.

Definiciones (HIPÓTESIS, E-11: las debe fijar S-A con S-B; aquí van explícitas para poder discutirlas):
* **Ventana**: 72 h después de la decisión (el método original usa 3 h, que a nuestro gasto trae ~4 compras como mucho). ``robots.auditor_ventana_h`` la sobrescribe.
* **Corte acierta** si NO hubo ninguna venta pagada del objeto cortado en la ventana (si las hubo, se cortó algo que vendía). LÍMITE: un corte EJECUTADO frena el gasto
  y por eso casi no puede acertar mal; sin grupo de control no se mide el contrafactual. Por eso se informa aparte lo ejecutado y lo no ejecutado (el segundo, en sombra, sí mide).
* **Suba acierta** si en los ``ventana_h / 24`` días COMPLETOS siguientes al de la decisión hubo gasto, al menos una venta y CPA ≤ CPA de equilibrio
  (``gasto <= cpa_be × ventas``, aritmética entera). Sin gasto en la ventana la suba «no se probó» (H-01) y no cuenta.
* Con menos de ``N_MIN_LECTURA`` decisiones juzgadas por grupo, el acierto se muestra pero se avisa de que la muestra no alcanza, y no sale al panel.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from scripts.robots.nucleo import RX_OFERTA_REAL, Contexto, Resultado, parsear_z, tabla_existe

ID = "auditor"
VENTANA_H = 72                                   # [HIPÓTESIS E-11]
N_MIN_LECTURA = 10                               # [HIPÓTESIS] muestra mínima por grupo para publicar un acierto
MINIMOS_PROPUESTOS_BP = {"cortes": 5000, "subas": 6000}      # [HIPÓTESIS] lib/robots.js: «50 % en cortes y 60 % en subas»
REFERENCIA_FUENTE_BP = {"cortes": 7500, "subas": 3333}       # [DECL] «3 de 4 cortes y 1 de 3 subas aciertan»: declarado por su autor, NO es prior ni umbral
_RX_OBJETO = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_PAGADO = ("paid", "pagado")
_TIPOS = {"MATAR": "corte", "ESCALAR": "suba"}


def _en(lista: list[str]) -> tuple[str, list[str]]:
    return ",".join("?" * len(lista)), lista


def leer_decisiones(c: Contexto) -> tuple[list[dict[str, Any]], list[str]]:
    """Cortes y subas de ``ofertas/<id>/08-operacion/decisiones.jsonl`` de las ofertas reales. Líneas ilegibles o fuera del contrato se descartan."""
    avisos: list[str] = []
    salida: list[dict[str, Any]] = []
    for oid in c.hechos()["ofertas"]["ids_reales"]:
        if not RX_OFERTA_REAL.match(oid):
            continue
        lec = c.ctx().oferta(oid).jsonl_cola("08-operacion/decisiones.jsonl", maximo=5000)
        if lec.estado != "ok":
            continue
        malas = 0
        for _n, obj, _crudo in lec.lineas:
            if not isinstance(obj, dict) or obj.get("accion") not in _TIPOS:
                if obj is None:
                    malas += 1
                continue
            ts = parsear_z(obj.get("ts"))
            tipo_obj, id_obj = obj.get("objeto_tipo"), obj.get("objeto_id")
            if ts is None or tipo_obj not in ("oferta", "campana", "conjunto", "anuncio") or not isinstance(id_obj, str) or not _RX_OBJETO.match(id_obj):
                malas += 1
                continue
            salida.append({"oferta_id": oid, "decision_id": str(obj.get("decision_id", ""))[:80], "tipo": _TIPOS[obj["accion"]], "ts": ts,
                           "objeto_tipo": tipo_obj, "objeto_id": id_obj, "regla": str(obj.get("regla", ""))[:40],
                           "ejecutada": obj.get("ejecutada") is True})
        if malas:
            avisos.append(f"{oid}: {malas} línea(s) de decisiones.jsonl ilegibles o fuera del contrato; se ignoran.")
    return salida, avisos


def _ads_del_objeto(conn: Any, d: dict[str, Any]) -> list[str]:
    oferta, tipo, oid = d["oferta_id"], d["objeto_tipo"], d["objeto_id"]
    if tipo == "anuncio":
        return [oid]
    ads: set[str] = set()
    if tipo == "oferta":
        if tabla_existe(conn, "dim_anuncio"):
            ads |= {str(r[0]) for r in conn.execute("SELECT ad_id FROM dim_anuncio WHERE oferta_id = ?", (oferta,))}
        ads |= {str(r[0]) for r in conn.execute("SELECT DISTINCT ad_id FROM fact_meta_ad_dia WHERE oferta_id = ?", (oferta,))}
    else:
        col = "campaign_id" if tipo == "campana" else "adset_id"
        ads |= {str(r[0]) for r in conn.execute(f"SELECT DISTINCT ad_id FROM fact_meta_ad_dia WHERE oferta_id = ? AND {col} = ?", (oferta, oid))}  # noqa: S608
    return sorted(ads)


def _ventas(conn: Any, d: dict[str, Any], ads: list[str], donde_tiempo: str, desde: str, hasta: str) -> int:
    """Pedidos pagados (sin pruebas ni internos) del objeto en el rango. ``donde_tiempo``: ``creado_ts`` o ``dia_utc``."""
    marcas_estado, estados = _en(list(_PAGADO))
    sql = (f"SELECT COUNT(*) FROM fact_pedido WHERE oferta_id = ? AND es_prueba = 0 AND es_interna = 0 AND estado IN ({marcas_estado}) "  # noqa: S608
           f"AND {donde_tiempo} > ? AND {donde_tiempo} <= ?")
    params: list[Any] = [d["oferta_id"], *estados, desde, hasta]
    if not (d["objeto_tipo"] == "oferta"):
        marcas_ads, lista = _en(ads)
        sql += f" AND adid IN ({marcas_ads})"
        params += lista
    return int(conn.execute(sql, params).fetchone()[0])


def _cpa_be(c: Contexto, oferta_id: str) -> tuple[int, str] | None:
    lec = c.ctx().oferta(oferta_id).json("03-oferta/economia.json")
    if not lec.ok or not isinstance(lec.dato, dict):
        return None
    cpa = lec.dato.get("cpa_be_visto") or lec.dato.get("cpa_be")
    if isinstance(cpa, dict) and isinstance(cpa.get("monto"), int) and not isinstance(cpa.get("monto"), bool) and isinstance(cpa.get("moneda"), str):
        return cpa["monto"], cpa["moneda"]
    return None


def juzgar(c: Contexto, conn: Any, d: dict[str, Any], ventana_h: int) -> tuple[str, str]:
    """``(veredicto, motivo)``; veredicto ∈ acierta · falla · pendiente · no_evaluable."""
    ahora = c.ahora()
    ts: _dt.datetime = d["ts"]
    ads = _ads_del_objeto(conn, d)
    if not ads and d["objeto_tipo"] != "oferta":
        return "no_evaluable", "el objeto no tiene anuncios en la base"
    if d["tipo"] == "corte":
        fin = ts + _dt.timedelta(hours=ventana_h)
        if ahora < fin:
            return "pendiente", f"la ventana de {ventana_h} h sigue abierta"
        ventas = _ventas(conn, d, ads, "creado_ts", ts.strftime("%Y-%m-%dT%H:%M:%SZ"), fin.strftime("%Y-%m-%dT%H:%M:%SZ"))
        return ("acierta", "ninguna venta en la ventana") if ventas == 0 else ("falla", f"{ventas} venta(s) pagada(s) en la ventana después del corte")
    dias = max(1, ventana_h // 24)
    dia = ts.astimezone(_dt.timezone.utc).date()
    ini, fin_dia = dia + _dt.timedelta(days=1), dia + _dt.timedelta(days=dias)
    if ahora < _dt.datetime.combine(fin_dia + _dt.timedelta(days=1), _dt.time(0, 0), tzinfo=_dt.timezone.utc):
        return "pendiente", f"faltan días completos de la ventana (hasta el {fin_dia.isoformat()})"
    cpa = _cpa_be(c, d["oferta_id"])
    if cpa is None:
        return "no_evaluable", "sin CPA de equilibrio (03-oferta/economia.json)"
    if d["objeto_tipo"] == "oferta":
        filtro, extra = "", []
    else:
        marcas, extra = _en(ads)
        filtro = f" AND ad_id IN ({marcas})"
    filas = conn.execute(f"SELECT moneda, SUM(gasto_minor) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha >= ? AND fecha <= ?{filtro} GROUP BY moneda",  # noqa: S608
                         [d["oferta_id"], ini.isoformat(), fin_dia.isoformat(), *extra]).fetchall()
    gasto = {str(m): int(g) for m, g in filas if int(g) > 0}
    if not gasto:
        return "no_evaluable", "la campaña no gastó en la ventana: la suba no se probó (H-01)"
    if list(gasto) != [cpa[1]]:
        return "no_evaluable", "el gasto y el CPA de equilibrio están en monedas distintas"
    ventas = _ventas(conn, d, ads, "dia_utc", (ini - _dt.timedelta(days=1)).isoformat(), fin_dia.isoformat())
    g = gasto[cpa[1]]
    if ventas >= 1 and g <= cpa[0] * ventas:
        return "acierta", f"{ventas} venta(s) con gasto {g} ≤ CPA de equilibrio {cpa[0]} × ventas ({cpa[1]}, unidad menor)"
    return "falla", (f"sin ventas con gasto {g}" if ventas == 0 else f"{ventas} venta(s) pero gasto {g} > CPA de equilibrio {cpa[0]} × ventas") + f" ({cpa[1]}, unidad menor)"


def _bp(aciertos: int, juzgadas: int) -> int | None:
    return aciertos * 10000 // juzgadas if juzgadas else None


def correr(c: Contexto) -> Resultado:
    p = c.parametro("robots", "auditor_ventana_h")
    ventana_h = p if isinstance(p, int) and not isinstance(p, bool) and p > 0 else VENTANA_H
    fuente_ventana = "parametros.yaml robots.auditor_ventana_h" if ventana_h == p else "HIPÓTESIS E-11 (72 h)"
    decisiones, avisos = leer_decisiones(c)
    if not decisiones:
        return Resultado("sin_datos", "sin datos: no hay decisiones (cortes ni subas) en ofertas/*/08-operacion/decisiones.jsonl; no se mide ningún acierto",
                         ["Sin decisiones que juzgar no se inventa ningún acierto.",
                          "Referencia declarada por su autor (NO es prior ni umbral): 3 de 4 cortes y 1 de 3 subas aciertan."],
                         datos={"ventana_h": ventana_h, "decisiones": 0, "avisos": avisos})
    juicios: list[dict[str, Any]] = []
    with c.abrir_db() as conn:
        for d in decisiones:
            if conn is None:
                v, m = "no_evaluable", "no hay base de datos (empresa/datos/fabrica.db)"
            else:
                v, m = juzgar(c, conn, d, ventana_h)
            juicios.append({"decision_id": d["decision_id"], "oferta_id": d["oferta_id"], "tipo": d["tipo"], "objeto_tipo": d["objeto_tipo"],
                            "objeto_id": d["objeto_id"], "regla": d["regla"], "ejecutada": d["ejecutada"], "ts": d["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "veredicto": v, "motivo": m})
    grupos: dict[str, dict[str, Any]] = {}
    for tipo in ("corte", "suba"):
        del_tipo = [j for j in juicios if j["tipo"] == tipo]
        juzg = [j for j in del_tipo if j["veredicto"] in ("acierta", "falla")]
        ac = sum(1 for j in juzg if j["veredicto"] == "acierta")
        g = {"n": len(del_tipo), "juzgadas": len(juzg), "aciertos": ac, "acierto_bp": _bp(ac, len(juzg)),
             "pendientes": sum(1 for j in del_tipo if j["veredicto"] == "pendiente"), "no_evaluables": sum(1 for j in del_tipo if j["veredicto"] == "no_evaluable"),
             "muestra_suficiente": len(juzg) >= N_MIN_LECTURA}
        for etiqueta, flag in (("ejecutadas", True), ("no_ejecutadas", False)):
            sub = [j for j in juzg if j["ejecutada"] is flag]
            g[etiqueta] = {"juzgadas": len(sub), "aciertos": sum(1 for j in sub if j["veredicto"] == "acierta"),
                           "acierto_bp": _bp(sum(1 for j in sub if j["veredicto"] == "acierta"), len(sub))}
        grupos[tipo + "s"] = g
    por_regla: dict[str, dict[str, int]] = {}
    for j in juicios:
        if j["veredicto"] in ("acierta", "falla"):
            r = por_regla.setdefault(j["regla"] or "sin_regla", {"juzgadas": 0, "aciertos": 0})
            r["juzgadas"] += 1
            r["aciertos"] += 1 if j["veredicto"] == "acierta" else 0
    total_j = grupos["cortes"]["juzgadas"] + grupos["subas"]["juzgadas"]
    total_a = grupos["cortes"]["aciertos"] + grupos["subas"]["aciertos"]
    bajos = [k for k, mn in (("cortes", MINIMOS_PROPUESTOS_BP["cortes"]), ("subas", MINIMOS_PROPUESTOS_BP["subas"]))
             if grupos[k]["muestra_suficiente"] and grupos[k]["acierto_bp"] is not None and grupos[k]["acierto_bp"] < mn]
    doc = {"tipo": "auditoria_sombra", "es_propuesta": True, "ahora": c.ahora().strftime("%Y-%m-%dT%H:%M:%SZ"), "ventana_h": ventana_h, "fuente_ventana": fuente_ventana,
           "grupos": grupos, "por_regla": dict(sorted(por_regla.items())), "minimos_propuestos_bp": MINIMOS_PROPUESTOS_BP,
           "referencia_fuente_declarada_bp": REFERENCIA_FUENTE_BP, "n_min_lectura": N_MIN_LECTURA, "bajo_el_minimo": bajos,
           "propuesta": ("bajar de nivel a quien corresponda (NO se ejecuta)" if bajos else "ninguna"), "juicios": juicios[:200], "avisos": avisos,
           "limites": ["un corte ejecutado casi no puede fallar: sin grupo de control no se mide el contrafactual",
                       "la ventana de 72 h y la definición de acierto son hipótesis (E-11)",
                       "las cifras de la fuente (3/4 y 1/3) son declaradas y no se usan como prior"]}
    salida = c.guardar(ID, doc)
    metricas: dict[str, int] = {"decisiones": len(decisiones), "juzgadas": total_j, "cortes_juzgados": grupos["cortes"]["juzgadas"], "subas_juzgadas": grupos["subas"]["juzgadas"]}
    for k, nombre in (("cortes", "acierto_cortes_bp"), ("subas", "acierto_subas_bp")):
        if grupos[k]["muestra_suficiente"] and grupos[k]["acierto_bp"] is not None:
            metricas[nombre] = grupos[k]["acierto_bp"]
    if total_j >= N_MIN_LECTURA:
        metricas["acierto_bp"] = total_a * 10000 // total_j
    def linea(nombre: str, g: dict[str, Any]) -> str:
        pct = "sin juzgar" if g["acierto_bp"] is None else f"{(g['acierto_bp'] + 50) // 100} %"
        return (f"{nombre}: {g['aciertos']} de {g['juzgadas']} juzgadas aciertan ({pct}) · {g['pendientes']} pendientes · {g['no_evaluables']} no evaluables"
                + ("" if g["muestra_suficiente"] or not g["juzgadas"] else f" · muestra insuficiente (< {N_MIN_LECTURA})"))
    resumen = [f"Ventana de juicio: {ventana_h} h ({fuente_ventana}).", linea("Cortes", grupos["cortes"]), linea("Subas", grupos["subas"]),
               "Referencia declarada por su autor (no es prior): 3 de 4 cortes y 1 de 3 subas aciertan."]
    if bajos:
        resumen.append("Por debajo del mínimo propuesto: " + ", ".join(bajos) + " → se PROPONE bajar de nivel (no se ejecuta).")
    if total_j == 0:
        estado = "parcial"
        razon = f"{len(decisiones)} decisión(es) todavía sin juzgar (ventana abierta o sin datos para evaluar)"
    elif bajos:
        estado = "alerta"
        razon = f"acierto por debajo del mínimo propuesto en {', '.join(bajos)}; se propone bajar de nivel (no se ejecuta)"
    elif any(g["muestra_suficiente"] for g in grupos.values()):
        estado = "ok"
        razon = f"{total_a} de {total_j} decisiones juzgadas aciertan"
    else:
        estado = "parcial"
        razon = f"{total_a} de {total_j} juzgadas aciertan, pero la muestra no alcanza (< {N_MIN_LECTURA} por grupo)"
    return Resultado(estado, razon[:300], resumen, datos=doc, metricas=metricas, salidas=[salida] if salida else [])
