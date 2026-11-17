"""Estado de los robots en sombra: qué corrió hoy, qué falta y qué latidos están vencidos. Lo puede leer el semáforo del panel.

Regla de la expectativa (para no dar falsas alarmas): un robot SOLO se espera si ya tiene al menos un latido ``origen: "programado"`` (es decir, si
alguien instaló su programación). Una corrida manual no crea expectativa: nadie quiere una alarma roja porque probó un robot a mano. Un robot
declarado ``estado: apagado`` en ``empresa/robots.yaml`` tampoco se espera.

``vencido``:
* robot periódico (``cada N min``): la edad de su último latido supera ``latido_max_min`` (= 2 × N + 5);
* robot diario: pasó más de ``GRACIA_MIN`` desde su última hora programada y no hay ningún latido desde entonces (la Mac pudo dormir: launchd recupera al despertar).

La salida trae ``trabajos`` con la forma que ya lee ``scripts.alertas.hechos._planificador`` (``{id, ultimo_latido, latido_max_min}``) más ``vencido`` y
``modo: "sombra"``: los latidos de la sombra NO son el planificador real (S-B) y quien los lea no debe darlos por tal (ver robots-sombra.md §6).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from dashboard.api_base import Ctx
from scripts.robots import latidos as L
from scripts.robots.catalogo import CATALOGO, GRACIA_MIN, horas_programadas, latido_max_min
from scripts.robots.nucleo import escribir_atomico, iso_z, json_estable, parsear_z
from scripts.robots.zonas import ZONA_MERCADO_DEFECTO, zona, zona_local

__all__ = ["calcular_estado", "escribir_estado", "texto_estado"]

SCHEMA_ESTADO = "1.0.0"
_APAGADO = {"apagado", "off", "desactivado"}


def _ocurrencias(robot: dict[str, Any], dia: _dt.date, tz: Any) -> list[_dt.datetime]:
    return [_dt.datetime(dia.year, dia.month, dia.day, int(h[:2]), int(h[3:]), tzinfo=tz) for h in horas_programadas(robot)]


def _ultima_programada(robot: dict[str, Any], ahora: _dt.datetime, tz: Any) -> _dt.datetime | None:
    hoy = ahora.astimezone(tz).date()
    cand = [o for d in (hoy - _dt.timedelta(days=1), hoy) for o in _ocurrencias(robot, d, tz) if o <= ahora]
    return max(cand) if cand else None


def _primera_de_hoy(robot: dict[str, Any], ahora: _dt.datetime, tz: Any, tz_dueno: Any) -> _dt.datetime | None:
    """Primera ocurrencia programada cuyo día, en la zona del dueño, es el de hoy."""
    hoy_dueno = ahora.astimezone(tz_dueno).date()
    base = ahora.astimezone(tz).date()
    cand = [o for d in (base - _dt.timedelta(days=1), base, base + _dt.timedelta(days=1)) for o in _ocurrencias(robot, d, tz)
            if o.astimezone(tz_dueno).date() == hoy_dueno]
    return min(cand) if cand else None


def _apagados(ctx: Ctx) -> set[str]:
    """Ids declarados ``apagado`` en ``empresa/robots.yaml`` (formato tolerante, igual que el panel). Si no existe o no se entiende, ninguno."""
    lec = ctx.empresa().yaml("robots.yaml")
    if not lec.ok:
        return set()
    crudo = lec.dato.get("robots") if isinstance(lec.dato, dict) and "robots" in lec.dato else lec.dato
    filas: list[tuple[str, Any]] = []
    if isinstance(crudo, dict):
        filas = [(str(k), v) for k, v in crudo.items() if isinstance(v, dict)]
    elif isinstance(crudo, list):
        filas = [(str(v.get("id")), v) for v in crudo if isinstance(v, dict) and v.get("id") is not None]
    return {i for i, v in filas if str(v.get("estado", v.get("modo", ""))).strip().lower() in _APAGADO}


def calcular_estado(raiz: Path, ahora: _dt.datetime, *, zona_mercado: str = ZONA_MERCADO_DEFECTO, zona_dueno: str | None = None) -> dict[str, Any]:
    ahora = ahora.astimezone(_dt.timezone.utc)
    ctx = Ctx(raiz, ahora=lambda: ahora)
    tz_m = zona(zona_mercado)
    tz_d = zona(zona_dueno) if zona_dueno else zona_local()
    latidos, avisos = L.leer(ctx)
    apagados = _apagados(ctx)
    hoy = ahora.astimezone(tz_d).date()
    robots: list[dict[str, Any]] = []
    for r in CATALOGO:
        mios = [x for x in latidos if x["robot"] == r["id"]]
        ultimo = mios[-1] if mios else None
        t_ultimo = parsear_z(ultimo["inicio"]) if ultimo else None
        hoy_n = sum(1 for x in mios if (t := parsear_z(x["inicio"])) is not None and t.astimezone(tz_d).date() == hoy)
        en_sombra = r["ejecutor_hoy"] == "sombra"
        programado = any(x.get("origen") == "programado" for x in mios)
        maximo = latido_max_min(r)
        edad = int((ahora - t_ultimo).total_seconds() // 60) if t_ultimo else None
        tz_r = tz_d if r["reloj"] == "dueno" else tz_m
        vencido, motivo = False, ""
        if not en_sombra:
            clave, motivo = "no_aplica", "todavía no tiene versión en sombra"
        elif r["id"] in apagados:
            clave, motivo = "apagado", "declarado apagado en empresa/robots.yaml"
        elif not mios:
            clave, motivo = "sin_latido", "nunca corrió"
        elif not programado:
            clave, motivo = "manual", "solo corrió a mano: no se espera su latido hasta que alguien instale su programación"
        else:
            if r["programacion"]["tipo"] == "cada":
                vencido = edad is not None and edad > maximo
                motivo = f"último latido hace {edad} min (máximo {maximo})" if vencido else f"al día: último latido hace {edad} min"
            else:
                prev = _ultima_programada(r, ahora, tz_r)
                corrio_desde = prev is not None and any((t := parsear_z(x["inicio"])) is not None and t >= prev - _dt.timedelta(minutes=10) for x in mios)
                vencido = prev is not None and (ahora - prev) > _dt.timedelta(minutes=GRACIA_MIN) and not corrio_desde
                motivo = (f"no corrió desde su hora programada ({prev.astimezone(tz_r).strftime('%H:%M')} del reloj {'del dueño' if r['reloj'] == 'dueno' else 'del mercado'})"
                          if vencido else "al día")
            clave = "vencido" if vencido else "al_dia"
        debia = False
        if en_sombra and r["id"] not in apagados:
            if r["programacion"]["tipo"] in ("diaria", "vueltas"):
                primera = _primera_de_hoy(r, ahora, tz_r, tz_d)
                debia = primera is not None and primera <= ahora
            else:       # periódico: ya tuvo tiempo de correr si desde el inicio del día (hora del dueño) pasó al menos un período
                inicio_dia = _dt.datetime(hoy.year, hoy.month, hoy.day, tzinfo=tz_d)
                debia = (ahora - inicio_dia) >= _dt.timedelta(minutes=int(r["programacion"]["cada_min"]))
        fila: dict[str, Any] = {
            "id": r["id"], "nombre": r["nombre"], "tipo": r["tipo"], "horario": r["horario"], "reloj": r["reloj"], "ejecutor_hoy": r["ejecutor_hoy"],
            "estado_latido": clave, "esperado": clave in ("al_dia", "vencido"), "vencido": vencido, "motivo": motivo,
            "ultimo_latido": ultimo["inicio"] if ultimo else None, "ultimo_resultado": ultimo["resultado"] if ultimo else None,
            "ultima_razon": (ultimo.get("razon") or "")[:200] if ultimo else None, "edad_min": edad, "latido_max_min": maximo,
            "corridas_hoy": hoy_n, "corrio_hoy": hoy_n > 0, "debia_correr_hoy": debia,
        }
        if ultimo and isinstance(ultimo.get("metricas"), dict):
            fila["metricas"] = {k: v for k, v in ultimo["metricas"].items() if isinstance(v, int) and not isinstance(v, bool)}
        robots.append(fila)
    en_sombra_ids = [x["id"] for x in robots if x["ejecutor_hoy"] == "sombra" and x["estado_latido"] != "apagado"]
    resumen = {
        "corrieron_hoy": [x["id"] for x in robots if x["corrio_hoy"]],
        "faltan_hoy": [x["id"] for x in robots if x["debia_correr_hoy"] and not x["corrio_hoy"]],
        "vencidos": [x["id"] for x in robots if x["vencido"]],
        "sin_arrancar": [x["id"] for x in robots if x["estado_latido"] == "sin_latido"],
        "solo_manual": [x["id"] for x in robots if x["estado_latido"] == "manual"],
        "no_aplica": [x["id"] for x in robots if x["estado_latido"] == "no_aplica"],
        "apagados": [x["id"] for x in robots if x["estado_latido"] == "apagado"],
        "esperados": [x["id"] for x in robots if x["esperado"]],
    }
    if resumen["vencidos"]:
        nivel, titulo = "rojo", f"{len(resumen['vencidos'])} robot(s) programados dejaron de dar señal de vida"
    elif not resumen["esperados"]:
        nivel, titulo = "gris", "Ningún robot en sombra está programado todavía (solo corren a mano)"
    elif resumen["faltan_hoy"]:
        nivel, titulo = "amarillo", f"{len(resumen['faltan_hoy'])} robot(s) todavía no corrieron hoy"
    else:
        nivel, titulo = "verde", "Los robots programados dan señal de vida a su hora"
    trabajos = [{"id": x["id"], "ultimo_latido": x["ultimo_latido"], "latido_max_min": x["latido_max_min"], "vencido": x["vencido"], "modo": "sombra"}
                for x in robots if x["esperado"]]
    aud = next((x for x in robots if x["id"] == "auditor"), None)
    auditoria = None
    if aud and aud.get("metricas"):
        m = aud["metricas"]
        auditoria = {k: m[k] for k in ("acierto_bp", "acierto_cortes_bp", "acierto_subas_bp", "cortes_juzgados", "subas_juzgadas", "decisiones") if k in m}
        auditoria["ultima_corrida"] = aud["ultimo_latido"]
    return {
        "schema_version": SCHEMA_ESTADO, "tipo": "estado_robots", "generado_en": iso_z(ahora), "hoy": hoy.isoformat(), "zona_hoy": str(tz_d),
        "zona_mercado": str(tz_m), "nivel": nivel, "titulo": titulo, "robots_en_sombra": en_sombra_ids, "resumen": resumen, "robots": robots,
        "trabajos": trabajos, "auditoria": auditoria, "latidos_leidos": len(latidos), "avisos": avisos,
        "nota": "Un robot solo se espera si tiene un latido de origen «programado» y no está apagado; una corrida a mano no crea expectativa.",
    }


def escribir_estado(raiz: Path, estado: dict[str, Any]) -> bool:
    """Guarda ``empresa/robots/estado.json`` (atómico). ``False`` si no cambió."""
    return escribir_atomico(raiz, L.REL_ESTADO, json_estable(estado))


def texto_estado(e: dict[str, Any]) -> str:
    sim = {"rojo": "ROJO", "amarillo": "AMARILLO", "verde": "VERDE", "gris": "GRIS"}
    L_ = [f"Robots en sombra — {e['generado_en']} (hoy: {e['hoy']} en {e['zona_hoy']}) · {sim.get(e['nivel'], e['nivel'])}: {e['titulo']}"]
    r = e["resumen"]
    L_.append(f"Corrieron hoy: {', '.join(r['corrieron_hoy']) or 'ninguno'}")
    L_.append(f"Faltan hoy: {', '.join(r['faltan_hoy']) or 'ninguno'}")
    L_.append(f"Latidos vencidos: {', '.join(r['vencidos']) or 'ninguno'}")
    if r["solo_manual"]:
        L_.append(f"Solo a mano (sin programar): {', '.join(r['solo_manual'])}")
    if r["sin_arrancar"]:
        L_.append(f"Nunca corrieron: {', '.join(r['sin_arrancar'])}")
    L_.append("")
    for x in e["robots"]:
        if x["estado_latido"] == "no_aplica":
            continue
        ult = f"último {x['ultimo_latido']} → {x['ultimo_resultado']}" if x["ultimo_latido"] else "sin latidos"
        L_.append(f"  {x['id']:<10} {x['estado_latido']:<10} {x['horario']:<34} {ult}")
    L_.append(f"Sin versión en sombra (los hará S-B o falta construirlos): {', '.join(r['no_aplica'])}")
    for a in e["avisos"]:
        L_.append(f"Aviso: {a}")
    return "\n".join(L_)
