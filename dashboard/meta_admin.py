"""Pantalla «Campañas en Meta» (#/meta): las campañas, conjuntos y anuncios de todas las ofertas, como el Administrador de anuncios.

Pedido del dueño (2026-11-16): «tengo problemas para mirar las campañas en Meta, ya que son muchas campañas de distintos países…
entre los testeos y todo me hace difícil ver las métricas, optimizar, ver los anuncios. Armar algo en el back office que se vea igual
que Meta para poder filtrar, ver y analizar desde ahí y tomar decisiones».

Fuente: el libro de tests (``anuncios.lista`` y ``anuncios.por_dia`` de cada test, que la nube lee de Meta por anuncio cada 5 minutos;
``ficha.campanas`` con nombre, rol, presupuesto y estado de cada campaña). Lógica pura: sin archivos ni red. Devuelve las entidades y
las filas por día del período; el navegador agrupa por campaña, conjunto o anuncio y filtra.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from dashboard import negocio as _N

METRICAS = ("gasto_usd", "impresiones", "alcance", "clics_enlace", "visitas_landing_meta", "inicios_pago_meta", "compras_meta",
            "valor_compras_meta_usd", "vistas_3s", "video_p25", "video_p50", "video_p75", "video_p100", "thruplay")
ACTIVOS = {"ACTIVE", "IN_PROCESS", "WITH_ISSUES", "PENDING_REVIEW"}
ROLES = {"principal": "CBO test", "pocket": "pocket 1-1-1", "test_variaciones": "CBO variaciones"}


def _txt(x: Any, largo: int = 200) -> str | None:
    return str(x)[:largo] if x not in (None, "") else None


def _campanas_test(t: dict[str, Any]) -> list[dict[str, Any]]:
    ficha = t.get("ficha") if isinstance(t.get("ficha"), dict) else {}
    lista = [c for c in (ficha.get("campanas") or []) if isinstance(c, dict) and c.get("id")]
    ids = [str(c["id"]) for c in lista]
    sueltas = t.get("campana") if isinstance(t.get("campana"), list) else [t.get("campana")]
    for c in sueltas:
        if isinstance(c, str) and c and c not in ids:
            lista.append({"id": c})
            ids.append(c)
    return lista


def _estado(x: Any) -> str | None:
    m = re.match(r"\s*([A-Z_]{3,})", str(x or ""))
    return m.group(1) if m else None


def vivo_por_campana(meta_vivo: Any) -> dict[str, dict[str, Any]]:
    """Estado y presupuesto de cada campaña según ``meta_vivo.json`` (la nube lo lee de Meta cada pocos minutos)."""
    d = meta_vivo if isinstance(meta_vivo, dict) else {}
    base = d if d.get("ok") else (d.get("ultima_buena") if isinstance(d.get("ultima_buena"), dict) else {})
    out = {}
    for o in (base.get("ofertas") or {}).values():
        for c in (o.get("campanas") or []) if isinstance(o, dict) else []:
            if isinstance(c, dict) and c.get("id"):
                out[str(c["id"])] = {"estado": _estado(c.get("estado")), "presupuesto": _N._num(c.get("presupuesto"))}
    return out


def armar(libro: Any, desde: _dt.date | None, hasta: _dt.date | None, ahora: _dt.datetime, vivo: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    L = libro if isinstance(libro, dict) else {}
    vivo = vivo or {}
    zona = _N.zona_de(L)
    hoy = ahora.astimezone(zona).date()
    campanas: dict[str, dict[str, Any]] = {}
    conjuntos: dict[str, dict[str, Any]] = {}
    anuncios: dict[str, dict[str, Any]] = {}
    dias: list[dict[str, Any]] = []
    primer = hoy
    for t in L.get("tests") or []:
        if not isinstance(t, dict):
            continue
        nombre_oferta = str(t.get("oferta") or t.get("nombre") or "")
        oferta_id = _N._slug(nombre_oferta)
        mercado = _txt(t.get("mercado"), 20)
        estado_oferta = str(t.get("estado") or "").lower()
        camps = _campanas_test(t)
        por_conjunto = {str(c["conjunto"]): str(c["id"]) for c in camps if c.get("conjunto")}
        principal = next((str(c["id"]) for c in camps if str(c.get("rol") or "").startswith("principal")), str(camps[0]["id"]) if camps else None)
        for c in camps:
            cid = str(c["id"])
            campanas.setdefault(cid, {
                "id": cid, "nombre": _txt(c.get("nombre")) or (f"{mercado or ''} | {t.get('nombre')}".strip(" |") + (f" · {ROLES.get(str(c.get('rol')), c.get('rol'))}" if c.get("rol") else "")),
                "oferta": nombre_oferta, "oferta_id": oferta_id, "mercado": mercado, "rol": _txt(c.get("rol"), 40),
                "presupuesto": _N._num(c.get("presupuesto_diario_usd")), "estado": _estado(c.get("estado")),
                "estado_oferta": estado_oferta, "inicio": _txt(c.get("inicio"), 40),
            })
            # la misma campaña puede venir dos veces en la ficha (p. ej. con y sin inicio): completar lo que falte (17-nov, icono «Programada»)
            ya = campanas[cid]
            ya.setdefault("motivos_libro", [])
            ya["motivos_libro"].extend(_motivos_libro(c, t))
            if not ya.get("inicio") and c.get("inicio"):
                ya["inicio"] = _txt(c.get("inicio"), 40)
            if not ya.get("rol") and c.get("rol"):
                ya["rol"] = _txt(c.get("rol"), 40)
        a = t.get("anuncios") if isinstance(t.get("anuncios"), dict) else {}
        for x in a.get("lista") or []:
            if not isinstance(x, dict) or not x.get("id"):
                continue
            aid = str(x["id"])
            sid = _txt(x.get("conjunto_id"), 40)
            cid = _txt(x.get("campana"), 40) or (por_conjunto.get(sid) if sid else None) or (str(camps[0]["id"]) if len(camps) == 1 else principal)
            if cid and cid not in campanas:
                campanas[cid] = {"id": cid, "nombre": f"{mercado or ''} | {t.get('nombre')}".strip(" |"), "oferta": nombre_oferta, "oferta_id": oferta_id,
                                 "mercado": mercado, "rol": None, "presupuesto": None, "estado": None,
                                 "estado_oferta": estado_oferta, "inicio": None, "motivos_libro": []}
            if sid:
                s = conjuntos.setdefault(sid, {"id": sid, "nombre": _txt(x.get("conjunto")) or sid, "campana": cid, "estados": []})
                s["estados"].append(str(x.get("estado") or ""))
            anuncios[aid] = {"id": aid, "nombre": _txt(x.get("nombre")) or aid, "conjunto": sid, "campana": cid, "estado": _estado(x.get("estado")),
                             "miniatura": _txt(x.get("miniatura"), 300), "video": bool(x.get("video_id")), "creado": _txt(x.get("creado"), 40)}
        for r in a.get("por_dia") or []:
            if not isinstance(r, dict) or str(r.get("id")) not in anuncios:
                continue
            f = _N.dia_de(r.get("fecha"), zona)
            if f is None:
                continue
            primer = min(primer, f)
            if (desde and f < desde) or (hasta and f > hasta):
                continue
            dias.append({"fecha": f.isoformat(), "id": str(r["id"]), **{k: _N._num(r.get(k)) or 0 for k in METRICAS}})
    for s in conjuntos.values():
        est = s.pop("estados")
        s["estado"] = "ACTIVE" if any(e in ACTIVOS for e in est) else (est[0] if est else None)
    for c in campanas.values():
        v = vivo.get(c["id"]) or {}
        if v.get("estado"):
            c["estado"] = v["estado"]
        if v.get("presupuesto"):
            c["presupuesto"] = v["presupuesto"]
        if not c["estado"]:
            hijos = [a["estado"] for a in anuncios.values() if a["campana"] == c["id"]]
            c["estado"] = "ACTIVE" if any(e in ACTIVOS for e in hijos) else ("PAUSED" if hijos else None)
    leidos = [str((t.get("anuncios") or {}).get("leido") or "") for t in L.get("tests") or [] if isinstance(t, dict) and isinstance(t.get("anuncios"), dict)]
    return {
        "campanas": sorted(campanas.values(), key=lambda c: (c["oferta"] or "", c["nombre"] or "")),
        "conjuntos": sorted(conjuntos.values(), key=lambda s: s["nombre"] or ""),
        "anuncios": sorted(anuncios.values(), key=lambda a: a["nombre"] or ""),
        "dias": dias,
        "leido": max([x for x in leidos if x], default=None),
        "periodo": {"todo": desde is None and hasta is None, "desde": desde.isoformat() if desde else None, "hasta": hasta.isoformat() if hasta else None,
                    "hoy": hoy.isoformat(), "primer_dia": primer.isoformat(), "zona": getattr(zona, "key", str(zona))},
    }


# ---------- por qué una campaña está como está (dueño, 17-nov: «cuando dice apagada, que diga la razón en tiempo real») ----------

REGLAS_TEXTO = {"R1": "corte del test", "R1b": "corte del test (segunda opción agotada)", "R4": "corte por pérdida (R4)",
                "R4b": "el día 1 no se repite (R4b)", "R15": "cierre de la oferta (R15)"}


def _regla_corta(regla: Any) -> str | None:
    r = str(regla or "").strip()
    if not r:
        return None
    m = re.match(r"(R\d+b?)\b", r)
    if m and r == m.group(1):
        return REGLAS_TEXTO.get(r, r)
    return r.split(":")[0][:60]


def _motivos_libro(c: dict[str, Any], t: dict[str, Any]) -> list[dict[str, Any]]:
    """Motivos de apagado que anotó el libro: la campaña (``apagada``, texto entre paréntesis del estado) y el test (``apagado``)."""
    out = []
    ap = c.get("apagada")
    if isinstance(ap, dict):
        out.append({"cuando": _txt(ap.get("cuando"), 40), "regla": _regla_corta(ap.get("regla")), "por": _txt(ap.get("por"), 60),
                    "detalle": _txt(ap.get("motivo"), 400), "fuente": "libro"})
    m = re.search(r"\((.+)\)", str(c.get("estado") or ""))
    if m:
        out.append({"cuando": None, "regla": _txt(m.group(1), 80), "por": None, "detalle": _txt(m.group(1), 400), "fuente": "libro"})
    ta = t.get("apagado")
    if isinstance(ta, dict):
        out.append({"cuando": _txt(ta.get("cuando"), 40), "regla": _regla_corta(ta.get("regla")) or ("corte del test" if "corte" in str(ta.get("motivo") or "").lower() else "apagado de la oferta"), "por": _txt(ta.get("por"), 60),
                    "detalle": _txt(ta.get("motivo") or ta.get("regla"), 400), "fuente": "libro", "oferta": True})
    return out


def motivos_estado(campanas: list[dict[str, Any]], cambios: list[dict[str, Any]]) -> None:
    """Pone en cada campaña ``motivo_estado`` = {corto, detalle, por, cuando}: por qué está en el estado que Meta muestra AHORA.

    Gana lo más reciente entre el libro (cortes de la vigilancia, apagados del dueño) y los cambios de estado que vieron las fotos de la nube.
    """
    for c in campanas:
        est = c.get("estado")
        apagada = est in {"PAUSED", "CAMPAIGN_PAUSED", "ADSET_PAUSED", "ARCHIVED", "DELETED"}
        evs = [x for x in cambios if x.get("campana") == c["id"]]
        ult_estado = next((x for x in reversed(evs) if x.get("tipo") == "estado"), None)
        nace = next((x for x in evs if x.get("inicio")), None)
        cand: list[dict[str, Any]] = []
        if ult_estado and ((ult_estado.get("a") in ACTIVOS) != apagada):
            sist = ult_estado.get("autor") == "sistema"
            corto = (_regla_corta(ult_estado.get("motivo")) if sist else None) or ("la apagó el sistema" if sist and apagada else "la prendió el sistema" if sist else "a mano en el Administrador")
            cand.append({"cuando": ult_estado["cuando"], "corto": corto, "por": "Sistema" if sist else "A mano",
                         "detalle": ult_estado.get("motivo") if sist else ("Se " + ("pausó" if apagada else "activó") + " fuera del sistema (Administrador de anuncios).")})
        if apagada:
            for m in c.get("motivos_libro") or []:
                f = _N.parsear_fecha(m.get("cuando")) if m.get("cuando") else None
                cand.append({"cuando": f.isoformat() if f else None, "corto": m.get("regla") or "apagada", "por": m.get("por"),
                             "detalle": m.get("detalle"), "oferta": m.get("oferta", False)})
        # el más nuevo; con la misma hora (± 15 min) gana el del libro, que trae el porqué completo
        cand.sort(key=lambda x: x["cuando"] or "")
        elegido = None
        if cand:
            elegido = cand[-1]
            t_el = _N.parsear_fecha(elegido["cuando"]) if elegido["cuando"] else None
            for x in cand:
                tx = _N.parsear_fecha(x["cuando"]) if x["cuando"] else None
                if x is not elegido and x.get("detalle") and tx and t_el and abs((tx - t_el).total_seconds()) <= 900 and len(x["detalle"] or "") > len(elegido.get("detalle") or ""):
                    elegido = {**x, "cuando": elegido["cuando"]}
        if apagada and not elegido:
            eo = str(c.get("estado_oferta") or "")
            if eo == "programado":
                elegido = {"corto": "espera activación", "detalle": "La oferta está programada: la activa el control previo antes de las 00:00 del mercado."}
            elif eo == "cerrado":
                elegido = {"corto": "oferta cerrada", "detalle": "La oferta se cerró y sus tiendas se archivaron."}
            elif nace and "PAUSED" in str(nace.get("motivo") or ""):
                elegido = {"cuando": nace["cuando"], "corto": "creada apagada", "por": "Sistema" if nace.get("autor") == "sistema" else "A mano",
                           "detalle": "Se creó en pausa y todavía no se activó."}
            else:
                elegido = {"corto": "sin motivo registrado", "detalle": "Pausada en Meta; ni el libro ni las fotos de la nube registran por qué."}
        if not apagada and not elegido and nace:
            elegido = {"cuando": nace["cuando"], "corto": None, "por": "Sistema" if nace.get("autor") == "sistema" else "A mano", "detalle": nace.get("motivo")}
        c["motivo_estado"] = elegido
        c.pop("motivos_libro", None)


# ---------- escala y línea de tiempo por oferta (dueño, 16-nov: «un timeline del presupuesto… ver qué se está haciendo, qué se dejó de hacer, por qué») ----------

ACCIONES = {"SURFEAR", "SUBIR_24H", "BAJAR"}
DEC_TEXTO = {"SURFEAR": "Surfeo", "SUBIR_24H": "Suba de 24 h", "BAJAR": "Bajada", "MANTENER": "Mantener", "SIN_DATOS": "Sin datos",
             "CONFIRMAR_TIENDA": "Confirmar con la tienda", "NO_GASTA": "No gasta su presupuesto", "TARDE": "Tarde en el mercado",
             "EN_TEST": "En test", "CONGELADA": "Congelada", "TIRON": "Tirón"}


def _f(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def filtrar_oferta(datos: dict[str, Any], oferta_id: str) -> dict[str, Any]:
    camps = [c for c in datos["campanas"] if c.get("oferta_id") == oferta_id]
    ids = {c["id"] for c in camps}
    conj = [s for s in datos["conjuntos"] if s.get("campana") in ids]
    anun = [a for a in datos["anuncios"] if a.get("campana") in ids]
    aids = {a["id"] for a in anun}
    return {**datos, "campanas": camps, "conjuntos": conj, "anuncios": anun, "dias": [r for r in datos["dias"] if r["id"] in aids]}


def escala_oferta(campanas: list[dict[str, Any]], eventos: list[Any], escala: list[Any], ahora: _dt.datetime) -> dict[str, Any]:
    """Decisiones de la escala y cambios de presupuesto/estado de las campañas de UNA oferta, listos para la línea de tiempo.

    - ``cambios``: cada suba, bajada, pausa o activación que vieron las fotos de la nube (o el historial de Meta), con autor y motivo.
    - ``decisiones``: lo que decidió la escala en cada vuelta, con los «no hacer nada» seguidos fundidos en un tramo
      (desde/hasta/veces + el porqué de la última), para ver qué se dejó de hacer y por qué.
    - ``sin_aplicar``: decisiones de subir o bajar que no tienen un cambio de presupuesto igual en las 2 h siguientes.
    - ``ultima``: la última decisión de cada campaña (para la tabla).
    """
    ids = {c["id"] for c in campanas}
    nombre = {c["id"]: c.get("nombre") for c in campanas}
    principal = next((c["id"] for c in campanas if str(c.get("rol") or "").startswith("principal")), next(iter(ids), None))
    cambios = []
    for e in eventos:
        if not isinstance(e, dict) or str(e.get("campana")) not in ids:
            continue
        cuando = _N.parsear_fecha(e.get("cuando"))
        if not cuando:
            continue
        cambios.append({"cuando": cuando.isoformat(), "campana": str(e["campana"]), "campana_nombre": nombre.get(str(e["campana"])),
                        "tipo": _txt(e.get("tipo"), 20), "inicio": bool(e.get("inicio")), "de": e.get("de"), "a": e.get("a"),
                        "autor": "sistema" if e.get("autor") == "sistema" else "a_mano", "motivo": _txt(e.get("motivo"), 400),
                        "fuente": _txt(e.get("fuente"), 80)})
    cambios.sort(key=lambda x: x["cuando"])
    crudas: list[dict[str, Any]] = []
    for ln in escala:
        if not isinstance(ln, dict):
            continue
        cuando = _N.parsear_fecha(ln.get("ahora")) or _N.parsear_fecha(ln.get("leido"))
        for d in ln.get("ofertas") or []:
            if not isinstance(d, dict) or not cuando:
                continue
            cid = str(d.get("campana") or "") or None
            if cid not in ids:
                continue
            crudas.append({"cuando": cuando.isoformat(), "campana": cid, "campana_nombre": nombre.get(cid), "decision": _txt(d.get("decision"), 30),
                           "texto": DEC_TEXTO.get(str(d.get("decision")), str(d.get("decision") or "").title()),
                           "porque": _txt(d.get("porque"), 500), "presupuesto": _f(d.get("presupuesto_usd")), "nuevo": _f(d.get("presupuesto_nuevo_usd")),
                           "roas_aov": _f(d.get("roas_aov")), "roas": _f(d.get("roas_desde_cambio") if d.get("roas_aov") is None else d.get("roas_aov")),
                           "compras": d.get("compras_desde_cambio"), "por_campana": bool(ln.get("por_campana")),
                           "regla": "por campaña con AOV" if ln.get("por_campana") else "simétrica por oferta (hasta el 16-nov)"})
    crudas.sort(key=lambda x: x["cuando"])
    # fundir los «no hacer nada» seguidos de cada campaña
    decisiones: list[dict[str, Any]] = []
    abierto: dict[str, dict[str, Any]] = {}
    for d in crudas:
        prev = abierto.get(d["campana"])
        if d["decision"] not in ACCIONES and prev and prev["decision"] == d["decision"] and prev["presupuesto"] == d["presupuesto"]:
            prev.update(hasta=d["cuando"], veces=prev["veces"] + 1, porque=d["porque"], roas=d["roas"], compras=d["compras"])
            continue
        x = {**d, "desde": d["cuando"], "hasta": d["cuando"], "veces": 1}
        decisiones.append(x)
        abierto[d["campana"]] = x
    sin_aplicar = []
    for d in decisiones:
        if d["decision"] not in ACCIONES or d["nuevo"] is None:
            continue
        t = _N.parsear_fecha(d["cuando"])
        hecho = any(c["campana"] == d["campana"] and c["tipo"] == "presupuesto" and c["a"] is not None and abs(float(c["a"]) - d["nuevo"]) < 1.01
                    and t - _dt.timedelta(minutes=10) <= _N.parsear_fecha(c["cuando"]) <= t + _dt.timedelta(hours=2) for c in cambios)
        d["aplicada"] = hecho
        if not hecho and (ahora - t) > _dt.timedelta(minutes=70):
            sin_aplicar.append({k: d[k] for k in ("cuando", "campana", "campana_nombre", "texto", "presupuesto", "nuevo", "porque")})
    ultima = {}
    for d in crudas:
        ultima[d["campana"]] = d
    return {"cambios": cambios, "decisiones": decisiones, "sin_aplicar": sin_aplicar, "ultima": ultima, "principal": principal,
            "a_mano": sum(1 for c in cambios if c["autor"] == "a_mano" and c["tipo"] == "presupuesto" and not c["inicio"]),
            "del_sistema": sum(1 for c in cambios if c["autor"] == "sistema" and c["tipo"] == "presupuesto" and not c["inicio"])}
