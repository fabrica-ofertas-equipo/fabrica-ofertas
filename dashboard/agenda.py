"""Agenda de cada oferta y del sistema: qué se está haciendo, qué viene (con hora), qué le toca al dueño y qué ya se hizo.

Pedido del dueño (14-nov): «que se agregue al dashboard en cada oferta los siguientes pasos (en tiempo real) de lo que está
programado, para yo que estoy auditando y monitorizando tener un lugar para saber qué se programó, qué se está aplicando, qué se
está por hacer, qué se hizo».

Solo lectura. Nada se inventa: cada renglón sale de un archivo que escriben las tareas o el agente.
- ``ofertas/_funnels/libro-de-tests.json``: inicio, fin del test, backend (``activar_desde``, ``bump_al_activar``), renovaciones,
  ``presupuesto_cambios``, ``programado`` y ``pendientes`` (lo que le toca al dueño: ``[{que, desde, hecho}]``), ``apagado``.
- ``ofertas/_funnels/tareas.json``: horario (cron) de cada tarea programada; lo refresca la vigilancia con
  ``scripts/tareas_snapshot.py``. La próxima corrida se calcula acá con el cron, así no envejece.
- ``ofertas/_funnels/latidos.json``: última corrida de cada tarea, con su resultado y su detalle.
- ``vigilancia.jsonl`` (corte), ``escala.jsonl`` (escala), ``avisos.jsonl`` y ``vigilancia_vuelta.json`` (última vuelta completa).
- La ventana de la renovación (5-16 h antes de la 00:00 del mercado) y las zonas de cada mercado, de los scripts de
  ``escalar-oferta`` (la tabla ``ZONA`` se lee como texto, no se ejecuta el script).

Cada renglón: ``{tipo, cuando, hasta, titulo, detalle, quien, tono, recurrente}``; ``tipo`` es ``en_curso`` · ``proximo`` ·
``te_toca`` · ``hecho`` · ``condicion`` (algo que hoy NO va a pasar y por qué).
"""
from __future__ import annotations

import ast
import datetime as _dt
import re
from typing import Any
from zoneinfo import ZoneInfo

from dashboard.negocio import parsear_fecha

__all__ = ["agregar_agendas", "proxima_corrida", "REL_TAREAS"]

ZONA_DUENO = ZoneInfo("America/Argentina/Buenos_Aires")
REL_TAREAS = "ofertas/_funnels/tareas.json"
REL_LATIDOS = "ofertas/_funnels/latidos.json"
REL_VIGILANCIA = "ofertas/_funnels/vigilancia.jsonl"
REL_ESCALA = "ofertas/_funnels/escala.jsonl"
REL_AVISOS = "ofertas/_funnels/avisos.jsonl"
REL_VUELTA = "ofertas/_funnels/vigilancia_vuelta.json"
REL_ZONAS = ".claude/skills/escalar-oferta/scripts/control_previo.py"
VENTANA_MAX_H, VENTANA_MIN_H = 16, 5          # escalar-oferta/scripts/ofertas_que_pegan.py
ENTRE_COMPLETAS = _dt.timedelta(minutes=52)  # hay_trabajo.py: una vuelta completa por hora
HORA_REVISION = 9                            # hay_trabajo.py: revisión diaria desde las 09:00 de Argentina
SURF_H, SUBA_H = 3, 24                        # escala simétrica: surfeo cada 3 h, suba cada 24 h
MAX_HECHOS = 14

# Tareas que tocan a las ofertas, en el orden en que se muestran, con qué hacen en una línea.
TAREAS_OFERTAS = {
    "vigilancia-ofertas": "Corte del test, salud, escala, revisión diaria y backend que toca prender",
    "renovacion-diaria": "10 creativos nuevos por día a las ofertas que pegan, en la mañana de cada mercado",
    "lanzar-ofertas": "Lanza 2 ofertas por día si hay candidatas y las activa si pasan el control previo",
    "radar-ofertas": "Busca ofertas que venden en 57 mercados y repone el banco",
    "buscar-ofertas": "Repone el banco hasta 3 listas y mide las que escalan",
    "soporte-clientes": "Responde los correos de clientes (entregas, dudas) y deja los reembolsos para vos",
}
_CIUDAD = {"Europe/Madrid": "Madrid", "America/Mexico_City": "Ciudad de México", "America/Sao_Paulo": "São Paulo",
           "America/New_York": "Nueva York", "Europe/Paris": "París", "Europe/London": "Londres", "Europe/Rome": "Roma",
           "Europe/Lisbon": "Lisboa", "America/Bogota": "Bogotá", "America/Santiago": "Santiago", "America/Lima": "Lima"}


# ───────────────────────── cron ─────────────────────────

def _campo(texto: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for parte in texto.split(","):
        paso = 1
        if "/" in parte:
            parte, p = parte.split("/", 1)
            paso = max(1, int(p))
        if parte in ("*", ""):
            a, b = lo, hi
        elif "-" in parte:
            a, b = (int(x) for x in parte.split("-", 1))
        else:
            a = int(parte)
            b = hi if paso > 1 else a
        out.update(range(a, b + 1, paso))
    return {x for x in out if lo <= x <= hi}


def proxima_corrida(cron: str, despues: _dt.datetime, zona: ZoneInfo = ZONA_DUENO) -> _dt.datetime | None:
    """Próxima hora (estrictamente después de ``despues``) que cumple un cron de 5 campos en la hora de la Mac (Argentina)."""
    try:
        mi, ho, dm, me, ds = cron.split()
        minutos, horas = sorted(_campo(mi, 0, 59)), sorted(_campo(ho, 0, 23))
        dias_mes, meses = _campo(dm, 1, 31), _campo(me, 1, 12)
        dias_sem = {d % 7 for d in _campo(ds, 0, 7)}
    except (ValueError, AttributeError):
        return None
    local = despues.astimezone(zona)
    for k in range(0, 9):
        dia = (local + _dt.timedelta(days=k)).date()
        if dia.month not in meses or dia.day not in dias_mes or (dia.isoweekday() % 7) not in dias_sem:
            continue
        for h in horas:
            for m in minutos:
                c = _dt.datetime.combine(dia, _dt.time(h, m), tzinfo=zona)
                if c > local:
                    return c
    return None


def _primera_corrida_desde(cron: str | None, desde: _dt.datetime) -> _dt.datetime | None:
    return proxima_corrida(cron, desde - _dt.timedelta(seconds=1)) if cron else None


# ───────────────────────── lecturas ─────────────────────────

def _json(ctx: Any, rel: str) -> Any:
    lec = ctx.raiz_confinada.json(rel)
    return lec.dato if lec.ok else None


def _jsonl(ctx: Any, rel: str, maximo: int = 200) -> list[dict[str, Any]]:
    lec = ctx.raiz_confinada.jsonl_cola(rel, maximo=maximo)
    if lec.estado != "ok":
        return []
    return [obj for _, obj, _ in lec.lineas if isinstance(obj, dict)]


_CACHE_ZONAS: dict[str, Any] = {}


def _zonas(ctx: Any) -> dict[str, str]:
    """La tabla ``ZONA`` de control_previo.py, leída como literal (sin ejecutar el script). Va directo al disco: el lector
    confinado del panel no abre carpetas ocultas como ``.claude/``, y es código del repo, no un archivo de terceros."""
    ruta = ctx.raiz / REL_ZONAS
    try:
        clave = f"{ruta}:{ruta.stat().st_mtime_ns}"
        if _CACHE_ZONAS.get("clave") == clave:
            return _CACHE_ZONAS["zonas"]
        texto = ruta.read_text(encoding="utf-8")[:200_000]
    except OSError:
        return {}
    m = re.search(r"^ZONA\s*=\s*(\{.*?\n\})", texto, re.S | re.M)
    try:
        z = ast.literal_eval(m.group(1)) if m else {}
    except (ValueError, SyntaxError):
        z = {}
    zonas = {str(k): str(v) for k, v in z.items()} if isinstance(z, dict) else {}
    _CACHE_ZONAS.update(clave=clave, zonas=zonas)
    return zonas


def _iso(d: _dt.datetime | None) -> str | None:
    return d.astimezone(_dt.timezone.utc).isoformat(timespec="seconds") if d else None


def _usd(x: Any) -> str:
    return f"US$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(x, (int, float)) else "—"


def _r(tipo: str, titulo: str, *, cuando: _dt.datetime | None = None, hasta: _dt.datetime | None = None, detalle: str = "",
       quien: str = "", tono: str = "info", recurrente: bool = False) -> dict[str, Any]:
    return {"tipo": tipo, "cuando": _iso(cuando), "hasta": _iso(hasta), "titulo": titulo, "detalle": detalle, "quien": quien,
            "tono": tono, "recurrente": recurrente}


def _salida_mercado(zona: str | None, ahora: _dt.datetime) -> tuple[_dt.datetime | None, bool, _dt.datetime | None]:
    """(00:00 de mañana en el mercado, ¿estamos en la ventana de renovación?, cuándo abre la próxima ventana)."""
    if not zona:
        return None, False, None
    z = ZoneInfo(zona)
    salida = _dt.datetime.combine(ahora.astimezone(z).date() + _dt.timedelta(days=1), _dt.time(0), tzinfo=z)
    horas = (salida - ahora).total_seconds() / 3600
    if horas < VENTANA_MIN_H:
        salida = salida + _dt.timedelta(days=1)
    abre = salida - _dt.timedelta(hours=VENTANA_MAX_H)
    return salida, VENTANA_MIN_H <= horas < VENTANA_MAX_H, abre


# ───────────────────────── agenda de una oferta ─────────────────────────

class _Sistema:
    """Lo que comparten todas las ofertas: tareas, latidos, registros y la próxima vuelta de la vigilancia."""

    def __init__(self, ctx: Any, ahora: _dt.datetime) -> None:
        self.ahora = ahora
        t = _json(ctx, REL_TAREAS)
        self.tareas = {x.get("taskId"): x for x in (t.get("tareas") if isinstance(t, dict) else []) or [] if isinstance(x, dict)}
        self.tareas_leido = t.get("leido") if isinstance(t, dict) else None
        lat = _json(ctx, REL_LATIDOS)
        self.latidos = lat if isinstance(lat, dict) else {}
        self.vigilancia = _jsonl(ctx, REL_VIGILANCIA)
        self.escala = _jsonl(ctx, REL_ESCALA)
        self.avisos = _jsonl(ctx, REL_AVISOS)
        vuelta = _json(ctx, REL_VUELTA)
        self.ultima_completa = parsear_fecha(vuelta.get("completa")) if isinstance(vuelta, dict) else None
        self.zonas = _zonas(ctx)
        hoy = ahora.astimezone(ZONA_DUENO).date().isoformat()
        self.revision_hoy = ctx.raiz_confinada.existe(f"ofertas/_funnels/REVISION-{hoy}.md")

    def cron(self, tarea: str) -> str | None:
        x = self.tareas.get(tarea) or {}
        return x.get("cronExpression") if x.get("enabled", True) and isinstance(x.get("cronExpression"), str) else None

    def proxima(self, tarea: str, desde: _dt.datetime | None = None) -> _dt.datetime | None:
        c = self.cron(tarea)
        return _primera_corrida_desde(c, desde) if c and desde else (proxima_corrida(c, self.ahora) if c else None)

    def proxima_completa(self, desde: _dt.datetime | None = None) -> _dt.datetime | None:
        """Primera corrida de la vigilancia que será vuelta completa (≥ 52 min desde la última) a partir de ``desde``."""
        base = max(desde or self.ahora, (self.ultima_completa + ENTRE_COMPLETAS) if self.ultima_completa else self.ahora)
        return self.proxima("vigilancia-ofertas", base)

    def proxima_revision(self) -> _dt.datetime | None:
        """La revisión diaria la hace la primera vuelta completa desde las 09:00 de Argentina, si todavía no está la de hoy."""
        hoy9 = _dt.datetime.combine(self.ahora.astimezone(ZONA_DUENO).date(), _dt.time(HORA_REVISION), tzinfo=ZONA_DUENO)
        if self.revision_hoy:
            return self.proxima_completa(hoy9 + _dt.timedelta(days=1))
        return self.proxima_completa(max(hoy9, self.ahora))


def _de_vigilancia(sis: _Sistema, nombre: str) -> list[tuple[_dt.datetime, dict[str, Any]]]:
    out = []
    for linea in sis.vigilancia:
        cuando = parsear_fecha(linea.get("ahora")) or parsear_fecha(linea.get("leido"))
        for t in linea.get("tests") or []:
            if isinstance(t, dict) and t.get("test") == nombre and cuando:
                out.append((cuando, t))
    return out


def _de_escala(sis: _Sistema, nombre: str) -> list[tuple[_dt.datetime, dict[str, Any]]]:
    out = []
    for linea in sis.escala:
        cuando = parsear_fecha(linea.get("ahora")) or parsear_fecha(linea.get("leido"))
        for o in linea.get("ofertas") or []:
            if isinstance(o, dict) and o.get("oferta") == nombre and cuando:
                out.append((cuando, o))
    return out


_DEC_CORTE = {"SIGUE": "sigue", "CERCA": "cerca del corte", "APAGAR": "apagar", "SEGUNDA_OPORTUNIDAD": "segunda oportunidad",
              "POST_LANZAMIENTO": "pasó el test", "ENTREGA_BAJA": "entrega baja", "SIN_LECTURA": "sin lectura de Meta"}
_DEC_ESCALA = {"SURFEAR": "surfeo", "SUBIR_24H": "suba de 24 h", "BAJAR": "bajada", "MANTENER": "mantener",
               "CONFIRMAR_TIENDA": "confirmar con la tienda", "SIN_DATOS": "sin datos", "NO_GASTA": "no gasta su presupuesto",
               "TARDE": "tarde en el mercado", "EN_TEST": "en test", "CONGELADA": "congelada"}


def agenda_oferta(o: dict[str, Any], ts: list[dict[str, Any]], sis: _Sistema) -> list[dict[str, Any]]:
    ahora = sis.ahora
    nombre = o.get("nombre") or ""
    items: list[dict[str, Any]] = []
    t0 = ts[0] if ts else {}
    estado_crudo = str(t0.get("estado") or "").lower()
    estado = o.get("estado")
    inicio = parsear_fecha(o.get("inicio") or t0.get("inicio"))
    fin_test = parsear_fecha(o.get("fin_test")) or (inicio + _dt.timedelta(days=1) if inicio else None)
    mercado = str(o.get("mercado") or t0.get("mercado") or "").split("/")[0].upper()
    zona = sis.zonas.get(mercado)
    ciudad = _CIUDAD.get(zona or "", mercado or "el mercado")
    vig = _de_vigilancia(sis, nombre)
    ult_vig = vig[-1] if vig else None
    apagada = estado in ("pausada", "cerrada")

    # ── hechos: lanzamiento, cortes, presupuesto, backend, rondas, avisos, apagado
    if inicio and inicio <= ahora and estado_crudo not in ("armado",):
        items.append(_r("hecho", "Salió la campaña del test", cuando=inicio, detalle=f"00:00 de {ciudad}", quien="Lanzamiento"))
    previa = None
    for cuando, t in vig:
        dec = t.get("decision")
        if dec != previa and dec:
            det = (f"{_usd(t.get('gasto_usd'))} gastados · {t.get('ventas', 0)} ventas"
                   + (f" · corte {_usd(t.get('corte_usd'))}" if t.get("corte_usd") else "")) if isinstance(t.get("gasto_usd"), (int, float)) \
                else str(t.get("porque") or "")[:200]
            items.append(_r("hecho", f"Vigilancia: {_DEC_CORTE.get(dec, dec.lower())}", cuando=cuando, detalle=det,
                            quien="Vigilancia", tono="error" if dec == "APAGAR" else "ok" if dec == "POST_LANZAMIENTO" else "aviso" if dec in ("CERCA", "SIN_LECTURA", "ENTREGA_BAJA") else "info"))
        previa = dec
    if vig and len(vig) > 1 and vig[-1][1].get("decision") == vig[-2][1].get("decision"):
        cuando, t = vig[-1]   # la última lectura siempre, con sus números de ahora (los cambios de decisión ya están arriba)
        dec = t.get("decision") or ""
        if isinstance(t.get("gasto_usd"), (int, float)):
            items.append(_r("hecho", f"Vigilancia: {_DEC_CORTE.get(dec, dec.lower())} (última lectura)", cuando=cuando,
                            detalle=f"{_usd(t.get('gasto_usd'))} gastados · {t.get('ventas', 0)} ventas" + (f" · corte {_usd(t.get('corte_usd'))}" if t.get("corte_usd") else ""),
                            quien="Vigilancia"))
    for t in ts:
        for c in t.get("presupuesto_cambios") or []:
            cuando = parsear_fecha(c.get("cuando")) if isinstance(c, dict) else None
            if not cuando or cuando > ahora or c.get("tipo") == "inicio":
                continue
            items.append(_r("hecho", f"Presupuesto {c.get('de')} → {c.get('a')} USD/día ({c.get('tipo')})", cuando=cuando,
                            detalle=str(c.get("nota") or (f"ROAS {c.get('roas')}" if c.get("roas") is not None else ""))[:200],
                            quien="Escala", tono="ok" if (c.get("a") or 0) > (c.get("de") or 0) else "aviso"))
        ap = t.get("apagado")
        if isinstance(ap, dict) and parsear_fecha(ap.get("cuando")):
            items.append(_r("hecho", "Campaña apagada", cuando=parsear_fecha(ap.get("cuando")),
                            detalle=str(ap.get("porque") or ap.get("motivo") or "")[:220], quien="Vigilancia", tono="error"))
    b = next((t.get("backend") for t in ts if isinstance(t.get("backend"), dict)), None) or {}
    b_est = str(b.get("estado") or "").lower()
    if parsear_fecha(b.get("listo")):
        items.append(_r("hecho", "Backend armado y probado (embudo apagado)", cuando=parsear_fecha(b.get("listo")),
                        detalle="Se prende al cierre del test para que ninguna venta de backend caiga dentro del test.", quien="Backend ofensivo", tono="ok"))
    elif b_est in ("armando", "listo", "activo") and parsear_fecha(b.get("desde")) and b_est != "activo":
        items.append(_r("hecho", "Empezó el armado del backend", cuando=parsear_fecha(b.get("desde")), quien="Backend ofensivo"))
    if b_est == "activo" and parsear_fecha(b.get("desde")):
        items.append(_r("hecho", "Backend prendido", cuando=parsear_fecha(b.get("desde")), detalle=_texto_backend(b), quien="Vigilancia", tono="ok"))
    for r in o.get("renovaciones") or []:
        ini = parsear_fecha(r.get("inicio"))
        if ini and ini <= ahora and r.get("estado") not in ("cancelada",):
            items.append(_r("hecho", f"Salió la ronda {r.get('ronda')}" + (f" ({r.get('anuncios')} anuncios)" if r.get("anuncios") else ""),
                            cuando=ini, detalle=str(r.get("nota") or "")[:200], quien="Renovación diaria", tono="ok"))
    for a in sis.avisos:
        msj = str(a.get("mensaje") or "")
        if a.get("oferta") == nombre or msj.startswith(nombre + ":") or msj.startswith(nombre + " "):
            items.append(_r("hecho", "Aviso al celular" + (" (urgente)" if a.get("urgente") else ""), cuando=parsear_fecha(a.get("cuando")),
                            detalle=msj[:240], quien="Avisos", tono="aviso" if a.get("urgente") else "info"))

    # ── lo programado a mano en el libro y lo que le toca al dueño
    for t in ts:
        for p in t.get("programado") or []:
            cuando = parsear_fecha(p.get("cuando")) if isinstance(p, dict) else None
            if cuando and isinstance(p.get("que"), str):
                items.append(_r("hecho" if cuando <= ahora else "proximo", p["que"][:160], cuando=cuando, quien=str(p.get("quien") or "Programado")))
        for p in t.get("pendientes") or []:
            if not isinstance(p, dict) or not isinstance(p.get("que"), str):
                continue
            hecho = parsear_fecha(p.get("hecho")) if isinstance(p.get("hecho"), str) else None
            desde = parsear_fecha(p.get("desde"))
            if hecho:
                items.append(_r("hecho", p["que"][:160], cuando=hecho, quien="Vos", tono="ok"))
            else:
                items.append(_r("te_toca", p["que"][:160], cuando=desde, detalle=str(p.get("porque") or "")[:240], quien="Vos",
                                tono="aviso" if not desde or desde <= ahora else "info"))

    if apagada:
        items.append(_r("condicion", "Sin pasos programados: la campaña está apagada",
                        detalle="Ninguna tarea la vuelve a prender sola: reactivarla lo decidís vos.", quien="—"))
        return _ordenar(items, ahora)

    # ── antes de salir
    if estado_crudo == "armado":
        items.append(_r("condicion", "Armada, sin activar", cuando=inicio,
                        detalle=(str(t0.get("nota") or "") or "La campaña está armada pero no programada.")[:300]
                        + " Mientras siga así, ninguna tarea la prende.", quien="Lanzamiento", tono="aviso"))
        return _ordenar(items, ahora)
    if inicio and inicio > ahora:
        items.append(_r("proximo", "Sale la campaña del test", cuando=inicio, detalle=f"00:00 de {ciudad}. Ya está programada en Meta.", quien="Meta"))
        items.append(_r("proximo", "Cierra el test del día 1", cuando=fin_test, detalle="Si vendió, pasa a post-lanzamiento; si no, se apaga al gastar 1,5 tickets.", quien="Vigilancia"))
        return _ordenar(items, ahora)

    en_test = o.get("fase") == "test" and fin_test and ahora < fin_test
    # ── test en curso
    if en_test:
        u = ult_vig[1] if ult_vig else {}
        det = (f"Última lectura {_hora(ult_vig[0])}: {_usd(u.get('gasto_usd'))} gastados, {u.get('ventas', 0)} ventas"
               f"{', CPA ' + _usd(u.get('cpa_usd')) if u.get('cpa_usd') else ''}. Se apaga sola si el gasto llega a {_usd(u.get('corte_usd') or o.get('corte_usd'))}.") if ult_vig else \
              f"Se apaga sola si el gasto llega a {_usd(o.get('corte_usd'))}."
        items.append(_r("en_curso", "Test del día 1", cuando=inicio, hasta=fin_test, detalle=det, quien="Vigilancia",
                        tono="aviso" if u.get("decision") == "CERCA" else "info"))
        gasto, corte, ticket = u.get("gasto_usd"), u.get("corte_usd"), u.get("ticket_corte_usd")
        cerca = isinstance(gasto, (int, float)) and isinstance(corte, (int, float)) and isinstance(ticket, (int, float)) and corte - gasto <= 0.6 * ticket
        prox = sis.proxima("vigilancia-ofertas") if cerca else sis.proxima_completa()
        if prox:
            items.append(_r("proximo", "Revisa el corte", cuando=prox, recurrente=True, quien="Vigilancia",
                            detalle="Cada 15 min (está cerca del corte)." if cerca else "Cada hora; pasa a cada 15 min cuando queda a 0,6 ticket del corte."))
        items.append(_r("proximo", "Cierra el test del día 1", cuando=fin_test, detalle=f"00:00 de {ciudad}. "
                        + ("Con ventas pasa a post-lanzamiento: escala, revisión diaria y renovación." if (o.get("ventas_n") or 0) else "Si no vende antes, se apaga al llegar al corte."),
                        quien="Vigilancia"))

    # ── backend
    activar = parsear_fecha(b.get("activar_desde"))
    if b_est == "listo" and activar:
        bump = len(b.get("bump_al_activar") or [])
        titulo = "Se prende el backend: " + _texto_backend(b, corto=True) + (" + bump en el checkout" if bump else "")
        if activar > ahora:
            prox = sis.proxima_completa(activar)
            items.append(_r("proximo", titulo, cuando=activar,
                            detalle=("Lo hace la vigilancia en su primera vuelta completa después de esa hora"
                                     + (f" (≈ {_hora(prox)})" if prox else "") + ": prende el embudo post-compra en cada tienda"
                                     + (" y pasa el bump al checkout" if bump else "") + ", lo comprueba y te avisa."),
                            quien="Vigilancia", tono="info"))
        else:
            tarde = (ahora - activar).total_seconds() / 3600
            items.append(_r("en_curso", "Backend por prender", cuando=activar, detalle=(f"Tocaba a las {_hora(activar)}; lo prende la próxima vuelta completa ({_hora(sis.proxima_completa())})."
                                                                                         + (" Lleva más de 2 h de atraso: revisá que la Mac esté despierta." if tarde > 2 else "")),
                            quien="Vigilancia", tono="aviso" if tarde > 2 else "info"))
    elif b_est == "armando":
        items.append(_r("en_curso", "Armando el backend", cuando=parsear_fecha(b.get("desde")), detalle=str(b.get("nota") or "")[:220], quien="Backend ofensivo"))

    # ── post-lanzamiento con campaña andando
    post = not en_test and estado == "activa" and (o.get("ventas_n") or 0) > 0
    if post:
        # escala
        esc = _de_escala(sis, nombre)
        ult = esc[-1] if esc else None
        cambios = [parsear_fecha(c.get("cuando")) for t in ts for c in (t.get("presupuesto_cambios") or []) if isinstance(c, dict)]
        ult_cambio = max((c for c in cambios if c and c <= ahora), default=inicio)
        det = ""
        if ult:
            e = ult[1]
            roas_e = e.get("roas_aov", e.get("roas_desde_cambio"))
            camp = f" ({e.get('rol')})" if e.get("rol") else ""
            det = (f"Última ({_hora(ult[0])}){camp}: {_DEC_ESCALA.get(e.get('decision'), str(e.get('decision') or '').lower())}"
                   f" · ROAS{' con AOV' if 'roas_aov' in e else ''} {roas_e} desde el último cambio · {e.get('presupuesto_usd')} USD/día. ")
        if ult_cambio:
            det += f"Cada campaña se decide sola: surfeo 3 h después de su último cambio con ROAS con AOV ≥ 1,8 y 2 compras (la línea de tiempo de la ficha muestra cada una)."
        prox = sis.proxima_completa()
        if prox:
            items.append(_r("proximo", "Evalúa la escala del presupuesto", cuando=prox, recurrente=True, detalle=det.strip(), quien="Vigilancia (cada hora)"))
        # revisión diaria
        rev = sis.proxima_revision()
        if rev:
            items.append(_r("proximo", "Revisión diaria", cuando=rev, recurrente=True, quien="Vigilancia",
                            detalle="Lee el día completo y aplica las reglas firmadas (R4 apagar si pierde, R3 backend, R13 precio de upsells, disputas); te manda el resumen."))
        # renovación de creativos
        renov = o.get("renovaciones") or []
        prog = [r for r in renov if r.get("estado") in ("programada", "produciendo")]
        for r in prog:
            ini = parsear_fecha(r.get("inicio"))
            if r.get("estado") == "produciendo":
                items.append(_r("en_curso", f"Produciendo la ronda {r.get('ronda')} (10 creativos)", hasta=ini, detalle=f"Sale a las 00:00 de {ciudad}.", quien="Renovación diaria"))
            elif ini:
                items.append(_r("proximo", f"Sale la ronda {r.get('ronda')}" + (f": {r.get('anuncios')} anuncios" if r.get("anuncios") else ""),
                                cuando=ini, detalle="Conjunto nuevo en la misma CBO con mínimo del 20 %.", quien="Meta"))
        if not prog:
            cpa, eq = o.get("cpa"), o.get("equilibrio")
            pega = isinstance(cpa, (int, float)) and isinstance(eq, (int, float)) and eq and cpa <= eq
            salida, en_ventana, abre = _salida_mercado(zona, ahora)
            if pega and salida:
                cuando = sis.proxima("renovacion-diaria") if en_ventana else sis.proxima("renovacion-diaria", abre)
                items.append(_r("proximo", "Renovación: produce la ronda nueva (10 creativos nuevos: referente y conceptos de la landing)", cuando=cuando,
                                detalle=f"Para salir a las 00:00 de {ciudad} ({_hora(salida)} en Argentina).", quien="Renovación diaria"))
            elif pega is False or (isinstance(cpa, (int, float)) and isinstance(eq, (int, float))):
                items.append(_r("condicion", "Sin renovación de creativos por ahora",
                                detalle=f"Solo se renueva la oferta que pega: CPA {_usd(cpa)} contra equilibrio {_usd(eq)}. Lo vuelve a mirar cada 2 h en la mañana de {ciudad}.",
                                quien="Renovación diaria", tono="aviso"))
        for r in renov:
            if r.get("minimo_pendiente") and parsear_fecha(r.get("inicio")):
                items.append(_r("proximo", f"Poner el mínimo del 20 % al conjunto {r.get('ronda')}", cuando=sis.proxima_completa(parsear_fecha(r.get("inicio"))), quien="Vigilancia"))
        if b_est in ("", "no") and o.get("backend", {}).get("falta"):
            items.append(_r("proximo", "Armar el backend (upsells post-compra)", cuando=rev, quien="Revisión diaria → backend ofensivo",
                            detalle="Regla R3: la oferta pasó el test con ventas y no tiene backend."))
    return _ordenar(items, ahora)


def _texto_backend(b: dict[str, Any], corto: bool = False) -> str:
    ups = [u for u in (b.get("upsells") or []) if isinstance(u, dict)]
    if corto:
        return f"{len(ups)} {'upsell' if len(ups) == 1 else 'upsells'} post-compra" if ups else "embudo post-compra"
    partes = [f"{u.get('nombre')} {u.get('precio_eur') or u.get('precio_usd')}{' €' if u.get('precio_eur') else ' USD'}" for u in ups]
    return " → ".join(partes)


def _hora(d: _dt.datetime | None) -> str:
    if not d:
        return "—"
    return d.astimezone(ZONA_DUENO).strftime("%d/%m %H:%M")


_ORDEN_TIPO = {"en_curso": 0, "te_toca": 1, "proximo": 2, "condicion": 3, "hecho": 4}


def _ordenar(items: list[dict[str, Any]], ahora: _dt.datetime) -> list[dict[str, Any]]:
    hechos = sorted((i for i in items if i["tipo"] == "hecho" and i["cuando"]), key=lambda i: i["cuando"], reverse=True)[:MAX_HECHOS]
    resto = [i for i in items if i["tipo"] != "hecho"]
    lejos = "9999"
    resto.sort(key=lambda i: (_ORDEN_TIPO[i["tipo"]], i["cuando"] or lejos))
    return resto + hechos


# ───────────────────────── todo junto ─────────────────────────

def agenda_sistema(sis: _Sistema) -> dict[str, Any]:
    """Tareas que tocan a las ofertas: próxima corrida (calculada con el cron) y la última, con su resultado."""
    tareas = []
    for clave, que in TAREAS_OFERTAS.items():
        t = sis.tareas.get(clave) or {}
        lat = sis.latidos.get(clave) or {}
        tareas.append({
            "clave": clave, "titulo": t.get("title") or clave, "que": que, "horario": t.get("schedule"),
            "activa": t.get("enabled", bool(t)) if t else None,
            "proxima": _iso(sis.proxima(clave)) if t.get("enabled", True) else None,
            "ultima": lat.get("ultimo") or t.get("lastRunAt"), "resultado": lat.get("resultado"),
            "detalle": str(lat.get("detalle") or "")[:300] or None, "fallas_seguidas": lat.get("fallas_seguidas") or 0,
        })
    return {"tareas": tareas, "tareas_leido": sis.tareas_leido, "ultima_vuelta_completa": _iso(sis.ultima_completa)}


def agregar_agendas(ctx: Any, datos: dict[str, Any], libro: dict[str, Any], ahora: _dt.datetime) -> None:
    """Agrega ``agenda`` a cada oferta de ``datos`` y ``agenda_sistema`` + ``lo_que_viene`` (próximos de todas) a ``datos``."""
    sis = _Sistema(ctx, ahora)
    por_nombre: dict[str, list[dict[str, Any]]] = {}
    for t in libro.get("tests") or []:
        if isinstance(t, dict):
            por_nombre.setdefault(str(t.get("oferta") or t.get("nombre") or ""), []).append(t)
    viene = []
    for o in datos.get("ofertas") or []:
        try:
            ag = agenda_oferta(o, por_nombre.get(o.get("nombre") or "", []), sis)
        except Exception as exc:  # noqa: BLE001 — una oferta con datos raros no rompe el tablero
            ag = [_r("condicion", "No se pudo armar la agenda de esta oferta", detalle=f"{type(exc).__name__}: {exc}"[:200], tono="error")]
        o["agenda"] = ag
        for i in ag:
            if (i["tipo"] in ("proximo", "en_curso", "te_toca") and not i.get("recurrente")) or (i["tipo"] == "condicion" and i["tono"] == "aviso" and o.get("estado") not in ("pausada", "cerrada")):
                viene.append({**i, "oferta": o.get("nombre"), "oferta_id": o.get("id")})
    viene.sort(key=lambda i: (_ORDEN_TIPO[i["tipo"]], i["cuando"] or "9999"))
    datos["agenda_sistema"] = agenda_sistema(sis)
    datos["lo_que_viene"] = viene[:12]
