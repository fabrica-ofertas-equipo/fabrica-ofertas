"""Lectura de «hechos» para las alertas, el semáforo y el informe: SOLO archivos locales del proyecto.

Reglas (las mismas del panel, ``dashboard/CONTRATO.md`` §7):

* nada de red, nada de claves, nunca se lee ``.env`` (el resolvedor confinado ``dashboard.archivos.Raiz`` lo rechaza);
* todo texto que viene de un archivo es DATO no confiable: se recorta, se limpia de controles y de enlaces antes de usarlo;
* **fail-closed**: un archivo ausente, corrupto o ilegible es «sin dato», nunca «todo bien» ni un cero inventado;
* una lectura que falla NO tumba a las demás: ``leer_hechos`` nunca lanza (el error queda en ``avisos``).

Los umbrales salen de ``empresa/parametros.yaml`` (``watchdog.latido_max_min``, ``infra.hc_preflight_vigencia_horas``…); si la clave no está
o es ``null`` el hecho trae ``None`` y la regla queda «sin umbral fijado» (gris), nunca verde.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from dashboard import api_empresa, api_ofertas, api_sistema
from dashboard.api_base import Ctx, RX_OFERTA
from dashboard.robots_sombra import leer_sombra

__all__ = [
    "leer_hechos", "limpiar_texto", "parsear_z", "iso_z", "horas_entre", "param",
    "RX_OFERTA_REAL", "TOPE_TEXTO", "FASES_CON_VENTA",
]

RX_OFERTA_REAL = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
TOPE_TEXTO = 140
FASES_CON_VENTA = ("en_test", "escalando")        # ofertas que ya pueden estar vendiendo
_RX_URL = re.compile(r"(?i)\b(?:https?|ftp)://\S+|\bwww\.\S+")
_RX_CONTROL = re.compile(r"[\x00-\x1f\x7f‪-‮⁦-⁩]")
_RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_RX_MONEDA_MENOR = re.compile(r"^([A-Z]{3})_minor$")
RX_PUL = re.compile(r"^PUL-[0-9]{4,9}$")
_PRIORIDAD = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_MAX_PULIDO = 3000
_MAX_PENDIENTES = 60
_MAX_LATIDOS = 100
_MAX_OFERTAS_KPI = 40

# Rutas que el semáforo mira para detectar que «ya existe un planificador» (código, no datos). Ninguna existe hoy.
CODIGO_PLANIFICADOR = ("infra/planificador.py", "infra/planificador", "engine/planificador.py", "engine/planificador",
                       "scripts/planificador.py", "scripts/planificador")
# Dónde se esperan las señales de vida por trabajo (PEDIDO a S-B en coordinacion-sesiones.md): el formato lo fija quien lo produzca.
REL_LATIDOS = "empresa/infra/latidos.json"
REL_ROBOTS = "empresa/robots.yaml"
REL_CANALES = ("empresa/avisos.yaml", "empresa/avisos.json")
REL_ALERTAS = "empresa/datos/alertas.jsonl"
REL_PULIDO = "empresa/panel/pulido.jsonl"


# ----------------------------------------------------------------------------------------------
# Utilidades puras
# ----------------------------------------------------------------------------------------------
def parsear_z(valor: Any) -> _dt.datetime | None:
    """``AAAA-MM-DDTHH:MM:SSZ`` (o con fracciones/offset ISO) → datetime UTC; cualquier otra cosa → ``None`` (nunca lanza)."""
    if not isinstance(valor, str) or len(valor) > 40:
        return None
    try:
        t = _dt.datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return t.astimezone(_dt.timezone.utc)


def iso_z(t: _dt.datetime) -> str:
    return t.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def horas_entre(desde: _dt.datetime | None, hasta: _dt.datetime) -> int | None:
    """Horas ENTERAS (hacia abajo, nunca negativas) entre dos instantes; ``None`` si falta uno."""
    if desde is None:
        return None
    return max(0, int((hasta - desde).total_seconds() // 3600))


def limpiar_texto(valor: Any, maximo: int = TOPE_TEXTO) -> str:
    """Texto de un archivo → una línea sin controles ni enlaces ni marcas de dirección (U+202E…), recortada. Lo no textual → ``""``."""
    if not isinstance(valor, str):
        return ""
    t = _RX_URL.sub("[enlace]", valor)
    t = _RX_CONTROL.sub(" ", t)
    t = " ".join(t.split())
    return t if len(t) <= maximo else t[: maximo - 1].rstrip() + "…"


def param(parametros: Any, grupo: str, clave: str) -> Any:
    """``parametros.grupos.<grupo>.<clave>.valor`` o ``None`` (ausente, ``null`` o con otra forma)."""
    try:
        v = parametros["grupos"][grupo][clave]["valor"]
    except (KeyError, TypeError, IndexError):
        return None
    return v


def _entero_positivo(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def _seguro(avisos: list[str], nombre: str, fn: Any, defecto: Any) -> Any:
    """Corre una lectura; si lanza, la deja en ``avisos`` y devuelve ``defecto`` (una lectura rota no tumba a las demás)."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - robustez ante archivos hostiles; el detalle va en un aviso sin rutas ni trazas
        avisos.append(f"No se pudo leer «{nombre}» ({type(exc).__name__}).")
        return defecto


# ----------------------------------------------------------------------------------------------
# Lecturas por tema
# ----------------------------------------------------------------------------------------------
def _preflight(ctx: Ctx, ahora: _dt.datetime, vigencia_h: int | None) -> dict[str, Any]:
    infra, aviso = api_sistema.estado_infra(ctx)
    if infra is None:
        return {"existe": False, "aviso": aviso, "vigencia_h": vigencia_h}
    items = infra.get("items") or []
    por_id: dict[str, dict[str, Any]] = {}
    conteo = {"VERDE": 0, "AMARILLO": 0, "ROJO": 0, "PENDIENTE": 0, "PENDIENTE_EXTERNO": 0}
    criticos_rojos: list[str] = []
    for it in items:
        est = it.get("estado")
        if est in conteo:
            conteo[est] += 1
        if isinstance(it.get("id"), str):
            por_id[it["id"]] = {"estado": est, "mensaje": limpiar_texto(it.get("mensaje"), 200), "critico": it.get("critico")}
        if est == "ROJO" and it.get("critico") is True and isinstance(it.get("id"), str):
            criticos_rojos.append(it["id"])
    generado = parsear_z(infra.get("generado_en"))
    return {
        "existe": True, "semaforo": infra.get("semaforo"), "modo": infra.get("modo"), "generado_en": infra.get("generado_en"),
        "edad_h": horas_entre(generado, ahora), "vigencia_h": vigencia_h, "total": infra.get("items_total", len(items)),
        "conteo": conteo, "criticos_rojos": criticos_rojos[:40], "items": por_id,
    }


def _limites(ctx: Ctx) -> tuple[dict[str, Any], Any]:
    """``(hechos de límites, parametros.yaml)``. Reusa el lector del panel (una sola fuente de verdad para «null = pendiente del dueño»)."""
    sobre = api_empresa.parametros(ctx)
    d = sobre.datos if isinstance(sobre.datos, dict) else {}
    lim = d.get("limites") if isinstance(d.get("limites"), dict) else {}
    valores = lim.get("valores") if isinstance(lim.get("valores"), dict) else None
    nulos = [c for c in (lim.get("nulos") or []) if isinstance(c, str)]
    solo_verde = set(c for c in (lim.get("nulos_solo_verde") or []) if isinstance(c, str))
    bloquean = [c for c in nulos if c not in solo_verde and c != "sello"]
    sello_ok = bool(valores and valores.get("sello") not in (None, "", {}, []))
    cuentas = valores.get("cuentas_permitidas") if valores else None
    props = d.get("propuestas") if isinstance(d.get("propuestas"), list) else []
    propuesta_limites = any(isinstance(p, dict) and "limites" in str(p.get("archivo", "")).lower() for p in props)
    hechos = {
        "legible": valores is not None,
        "moneda": valores.get("moneda_limites") if valores else None,
        "bloquean": bloquean[:60],
        "n_bloquean": len(bloquean),
        "sello": sello_ok,
        "gasto_diario_global": valores.get("gasto_diario_global") if valores else None,
        "perdida_neta_acumulada_max": valores.get("perdida_neta_acumulada_max") if valores else None,
        "cuentas_permitidas": [c for c in cuentas if isinstance(c, str)][:20] if isinstance(cuentas, list) else [],
        "propuesta": propuesta_limites,
    }
    return hechos, d.get("parametros")


def _canales(ctx: Ctx) -> dict[str, Any]:
    """Canales de avisos configurados (``empresa/avisos.yaml``, formato tolerante). Sin archivo = ningún canal elegido."""
    crudo: Any = None
    existe = False
    for rel in REL_CANALES:
        nombre = rel.split("/", 1)[1]
        lec = ctx.empresa().json(nombre) if rel.endswith(".json") else ctx.empresa().yaml(nombre)
        if lec.ok:
            crudo, existe = lec.dato, True
            break
    lista: list[Any] = []
    if isinstance(crudo, dict):
        c = crudo.get("canales")
        if isinstance(c, list):
            lista = c
        else:
            lista = [x for x in (crudo.get("canal"), crudo.get("canal_respaldo"), crudo.get("canal_secundario")) if x]
    elif isinstance(crudo, list):
        lista = crudo
    canales: dict[str, bool] = {}
    for c in lista[:10]:
        tipo = c if isinstance(c, str) else (c.get("tipo") or c.get("canal") or c.get("nombre")) if isinstance(c, dict) else None
        if not isinstance(tipo, str) or not tipo.strip():
            continue
        tipo = limpiar_texto(tipo, 30).lower()
        probado = isinstance(c, dict) and (c.get("probado") is True or c.get("estado") in ("probado", "verificado") or bool(c.get("probado_en")))
        canales[tipo] = canales.get(tipo, False) or bool(probado)
    return {"archivo": existe, "tipos": sorted(canales), "n": len(canales), "n_probados": sum(1 for v in canales.values() if v)}


def _planificador(ctx: Ctx, ahora: _dt.datetime, latido_max_min: int | None) -> dict[str, Any]:
    codigo = [rel for rel in CODIGO_PLANIFICADOR if ctx.raiz_confinada.existe(rel)]
    trabajos: list[dict[str, Any]] = []
    lec = ctx.raiz_confinada.json(REL_LATIDOS)
    fuentes_latido = []
    if lec.ok:
        crudos = lec.dato.get("trabajos") if isinstance(lec.dato, dict) else lec.dato
        fuentes_latido.append(REL_LATIDOS)
        for t in (crudos if isinstance(crudos, list) else [])[:_MAX_LATIDOS]:
            if isinstance(t, dict) and isinstance(t.get("id"), str):
                trabajos.append({"id": limpiar_texto(t["id"], 40), "ultimo_latido": t.get("ultimo_latido"),
                                 "max_min": _entero_positivo(t.get("latido_max_min")) or latido_max_min})
    rob = ctx.raiz_confinada.yaml(REL_ROBOTS)
    if rob.ok:
        crudos = rob.dato.get("robots") if isinstance(rob.dato, dict) else rob.dato
        fuentes_latido.append(REL_ROBOTS)
        if isinstance(crudos, dict):
            crudos = [{"id": k, **v} for k, v in crudos.items() if isinstance(v, dict)]
        for t in (crudos if isinstance(crudos, list) else [])[:_MAX_LATIDOS]:
            if isinstance(t, dict) and isinstance(t.get("id"), str) and "ultimo_latido" in t:
                trabajos.append({"id": limpiar_texto(t["id"], 40), "ultimo_latido": t.get("ultimo_latido"),
                                 "max_min": _entero_positivo(t.get("latido_max_min")) or latido_max_min})
    vencidos = 0
    sin_latido = 0
    for t in trabajos:
        u = parsear_z(t["ultimo_latido"])
        if u is None:
            t["vencido"], t["edad_min"] = True, None
            sin_latido += 1
            vencidos += 1
            continue
        edad = max(0, int((ahora - u).total_seconds() // 60))
        t["edad_min"] = edad
        t["vencido"] = bool(t["max_min"]) and edad > t["max_min"]
        vencidos += 1 if t["vencido"] else 0
    return {"codigo": codigo, "existe": bool(codigo) or bool(trabajos), "trabajos": trabajos, "n": len(trabajos),
            "vencidos": vencidos, "sin_latido": sin_latido, "latido_max_min": latido_max_min, "fuentes": fuentes_latido, "sombra": _sombra(ctx)}


def _sombra(ctx: Ctx) -> dict[str, Any] | None:
    """Resumen de los robots EN SOMBRA (``empresa/robots/estado.json``) o ``None`` si no hay foto. **No es el planificador real**: va aparte de ``trabajos`` y de ``existe``
    para que nadie lo cuente como tal (el verde del semáforo exige el planificador de S-B). El vencimiento se recalcula con la hora de ahora."""
    datos, _ = leer_sombra(ctx)
    if datos is None:
        return None
    r = datos["resumen"]
    return {"situacion": datos["situacion"], "n_con_sombra": len(r["con_sombra"]), "n_esperados": len(r["esperados"]), "n_vencidos": len(r["vencidos"]), "ids_vencidos": r["vencidos"][:12],
            "nombres_vencidos": [f["nombre"] for f in datos["robots"] if f["id"] in r["vencidos"]][:12],
            "n_corrieron_hoy": len(r["corrieron_hoy"]), "n_solo_manual": len(r["solo_manual"]), "n_sin_arrancar": len(r["sin_arrancar"]), "de_hoy": datos["de_hoy"], "edad_min": datos["edad_min"]}


def _ofertas(ctx: Ctx) -> dict[str, Any]:
    sobre = api_ofertas.ofertas(ctx)
    filas = sobre.datos if isinstance(sobre.datos, list) else []
    reales = [f for f in filas if isinstance(f, dict) and not f.get("demo") and isinstance(f.get("oferta_id"), str)]
    gates: list[dict[str, Any]] = []
    for f in reales:
        for etapa in f.get("gates_pendientes") or []:
            gates.append({"oferta_id": f["oferta_id"], "etapa": etapa, "desde": f.get("actualizado_en"),
                          "id_estado": f.get("oferta_id_estado")})
    sin_estado = [f["oferta_id"] for f in reales if f.get("aviso") and not f.get("fase")]
    return {"n_reales": len(reales), "n_demo": sum(1 for f in filas if isinstance(f, dict) and f.get("demo")),
            "ids_reales": [f["oferta_id"] for f in reales][:_MAX_OFERTAS_KPI], "gates": gates[:_MAX_PENDIENTES],
            "con_venta_en_curso": sum(1 for f in reales if f.get("fase") in FASES_CON_VENTA),
            "por_fase": _contar(f.get("fase") for f in reales), "sin_estado": sin_estado[:20],
            "pausadas": [f["oferta_id"] for f in reales if f.get("pausa") is True][:20]}


def _contar(it: Any) -> dict[str, int]:
    c: dict[str, int] = {}
    for x in it:
        k = x if isinstance(x, str) else "sin_fase"
        c[k] = c.get(k, 0) + 1
    return c


def _pulido(ctx: Ctx, ahora: _dt.datetime) -> dict[str, Any]:
    """Pendientes abiertos del dueño de ``empresa/panel/pulido.jsonl`` (se pliega el estado igual que el panel)."""
    lec = ctx.raiz_confinada.jsonl_cola(REL_PULIDO, maximo=_MAX_PULIDO)
    if lec.estado != "ok":
        return {"existe": False, "abiertos": [], "total": 0}
    por_id: dict[str, dict[str, Any]] = {}
    for _, obj, _ in lec.lineas:
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str):
            continue
        previa = por_id.get(obj["id"])
        es_cambio = obj.get("evento") == "estado" or (obj.get("titulo") is None and obj.get("estado") is not None)
        if es_cambio:
            if previa is not None and obj.get("estado") in ("abierta", "en_curso", "resuelta"):
                previa["estado"] = obj["estado"]
            continue
        base = {"id": obj["id"], "titulo": limpiar_texto(obj.get("titulo")), "etapa": limpiar_texto(obj.get("etapa"), 12) or None,
                "responsable": obj.get("responsable") if obj.get("responsable") in ("dueno", "ia", "robot", "otro") else None,
                "prioridad": obj.get("prioridad") if obj.get("prioridad") in _PRIORIDAD else None,
                "estado": obj.get("estado") if obj.get("estado") in ("abierta", "en_curso", "resuelta") else "abierta",
                "vence": obj.get("vence") if isinstance(obj.get("vence"), str) else None, "ts": obj.get("ts")}
        nuevo = {**(previa or {}), **base}
        if previa is not None and obj.get("estado") is None:
            nuevo["estado"] = previa["estado"]
        por_id[obj["id"]] = nuevo
    abiertos = [p for p in por_id.values() if p["estado"] != "resuelta" and p["responsable"] == "dueno" and RX_PUL.match(p["id"])]
    for p in abiertos:
        p["vencido"] = _vencido(p.get("vence"), ahora)
    abiertos.sort(key=lambda p: (_PRIORIDAD.get(p["prioridad"], 9), str(p.get("ts") or ""), p["id"]))
    return {"existe": True, "abiertos": abiertos[:_MAX_PENDIENTES], "total": len(por_id), "n_abiertos_dueno": len(abiertos)}


def _vencido(vence: Any, ahora: _dt.datetime) -> bool:
    if not isinstance(vence, str):
        return False
    if _RX_FECHA.match(vence):
        try:
            fin = _dt.datetime.strptime(vence, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc) + _dt.timedelta(days=1)
        except ValueError:
            return False
        return ahora >= fin
    t = parsear_z(vence)
    return t is not None and ahora > t


def _ventas(ctx: Ctx, ids: list[str], fecha: str) -> dict[str, Any]:
    """Ventas y gasto del día ``fecha`` de las ofertas REALES, de ``ofertas/<id>/08-operacion/diario/<fecha>/kpi_oferta_dia.json``.

    Sin esos archivos NO hay cifra («todavía no hay datos»): jamás se devuelve un 0 que parezca medido. Dinero = entero en unidad menor + moneda.
    """
    filas: list[dict[str, Any]] = []
    for oferta_id in ids[:_MAX_OFERTAS_KPI]:
        if not RX_OFERTA.fullmatch(oferta_id):
            continue
        lec = ctx.oferta(oferta_id).json(f"08-operacion/diario/{fecha}/kpi_oferta_dia.json")
        if not lec.ok or not isinstance(lec.dato, dict):
            continue
        compras: int | None = None
        gasto: dict[str, Any] | None = None
        ingresos: dict[str, Any] | None = None
        for fila in (lec.dato.get("filas") if isinstance(lec.dato.get("filas"), list) else [])[:80]:
            if not isinstance(fila, dict):
                continue
            v, unidad = fila.get("valor"), fila.get("unidad")
            if fila.get("kpi_id") == "compras_stripe" and isinstance(v, int) and not isinstance(v, bool):
                compras = v
            m = _RX_MONEDA_MENOR.match(unidad) if isinstance(unidad, str) else None
            if m and isinstance(v, int) and not isinstance(v, bool):
                if fila.get("kpi_id") == "gasto_meta":
                    gasto = {"monto": v, "moneda": m.group(1)}
                elif fila.get("kpi_id") in ("ingresos_brutos", "ingresos"):
                    ingresos = {"monto": v, "moneda": m.group(1)}
        filas.append({"oferta_id": oferta_id, "compras": compras, "gasto": gasto, "ingresos": ingresos})
    if not filas:
        return {"hay_datos": False, "fecha": fecha, "ofertas": [], "compras": None, "gasto": [], "ingresos": []}
    compras_total = sum(f["compras"] for f in filas if f["compras"] is not None) if any(f["compras"] is not None for f in filas) else None
    return {"hay_datos": True, "fecha": fecha, "ofertas": filas, "compras": compras_total,
            "gasto": _sumar_monedas(f["gasto"] for f in filas), "ingresos": _sumar_monedas(f["ingresos"] for f in filas)}


def _sumar_monedas(montos: Any) -> list[dict[str, Any]]:
    acc: dict[str, int] = {}
    for m in montos:
        if isinstance(m, dict) and isinstance(m.get("monto"), int) and isinstance(m.get("moneda"), str):
            acc[m["moneda"]] = acc.get(m["moneda"], 0) + m["monto"]
    return [{"monto": v, "moneda": k} for k, v in sorted(acc.items())]


def _archivo_alertas(ctx: Ctx) -> dict[str, Any]:
    st = ctx.raiz_confinada.stat(REL_ALERTAS)
    return {"existe": st is not None}


# ----------------------------------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------------------------------
def leer_hechos(ctx: Ctx, *, fecha_ventas: str | None = None) -> dict[str, Any]:
    """Todos los hechos que necesitan las reglas, el semáforo y el informe. Nunca lanza.

    ``fecha_ventas``: día (``AAAA-MM-DD``) de las ventas/gasto del informe; por defecto, AYER (UTC), el último día cerrado.
    """
    ahora = ctx.ahora().astimezone(_dt.timezone.utc)
    avisos: list[str] = []
    fecha = fecha_ventas if isinstance(fecha_ventas, str) and _RX_FECHA.match(fecha_ventas) else (ahora - _dt.timedelta(days=1)).strftime("%Y-%m-%d")

    lim, parametros = _seguro(avisos, "límites y parámetros", lambda: _limites(ctx), ({"legible": False, "moneda": None, "bloquean": [], "n_bloquean": 0, "sello": False,
                              "gasto_diario_global": None, "perdida_neta_acumulada_max": None, "cuentas_permitidas": [], "propuesta": False}, None))
    vigencia_h = _entero_positivo(param(parametros, "infra", "hc_preflight_vigencia_horas"))
    latido_max = _entero_positivo(param(parametros, "watchdog", "latido_max_min"))
    pausa = _seguro(avisos, "PAUSA", lambda: api_sistema.estado_pausa(ctx), {"activa": False, "desde": None, "motivo": None, "ilegible": True})
    freno = _seguro(avisos, "freno de captura", lambda: api_sistema.freno_captura(ctx)[0], None)
    pre = _seguro(avisos, "chequeo de cuentas y servicios", lambda: _preflight(ctx, ahora, vigencia_h), {"existe": False, "vigencia_h": vigencia_h})
    canales = _seguro(avisos, "canales de avisos", lambda: _canales(ctx), {"archivo": False, "tipos": [], "n": 0, "n_probados": 0})
    plan = _seguro(avisos, "planificador y señales de vida", lambda: _planificador(ctx, ahora, latido_max),
                   {"codigo": [], "existe": False, "trabajos": [], "n": 0, "vencidos": 0, "sin_latido": 0, "latido_max_min": latido_max, "fuentes": [], "sombra": None})
    ofertas = _seguro(avisos, "ofertas", lambda: _ofertas(ctx), {"n_reales": 0, "n_demo": 0, "ids_reales": [], "gates": [], "con_venta_en_curso": 0,
                                                                "por_fase": {}, "sin_estado": [], "pausadas": []})
    pulido = _seguro(avisos, "pendientes", lambda: _pulido(ctx, ahora), {"existe": False, "abiertos": [], "total": 0})
    ventas = _seguro(avisos, "ventas y gasto", lambda: _ventas(ctx, ofertas["ids_reales"], fecha),
                     {"hay_datos": False, "fecha": fecha, "ofertas": [], "compras": None, "gasto": [], "ingresos": []})
    return {
        "ahora": iso_z(ahora), "fecha_ventas": fecha, "pausa": pausa, "freno_captura": freno, "preflight": pre, "limites": lim, "parametros_leidos": parametros is not None,
        "umbrales": {"preflight_vigencia_h": vigencia_h, "latido_max_min": latido_max}, "canales": canales, "planificador": plan, "ofertas": ofertas,
        "pulido": pulido, "ventas": ventas, "archivo_alertas": _seguro(avisos, "alertas guardadas", lambda: _archivo_alertas(ctx), {"existe": False}), "avisos": avisos,
    }
