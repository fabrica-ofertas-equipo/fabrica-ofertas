#!/usr/bin/env python3
"""Fotos de cada campaña cada 5 minutos y registro de TODO cambio de presupuesto o de estado, lo haga el sistema o el dueño.

Pedido del dueño (2026-11-16): «poder ver qué se subió, qué se bajó, un timeline del presupuesto… para monitorear al sistema y ver
qué se está haciendo, qué se dejó de hacer, por qué». Además la escala por campaña (escalar_presupuesto.py, 16-nov) necesita el
gasto, las compras y el valor de cada campaña DESDE SU ÚLTIMO CAMBIO, sin pedirle a Claude el desglose por hora de Meta.

Cómo:
- ``nube_sync.py`` (cada 5 min, sin Claude) llama a ``registrar_desde_nube``: guarda una foto con el acumulado de HOY (día de la
  cuenta) de cada campaña del libro —presupuesto, estado, gasto, compras, valor, pagos iniciados— en ``fotos_campanas.jsonl`` (solo si
  algo cambió) y compara con la foto anterior: cada presupuesto o estado distinto es un evento en ``presupuesto_eventos.jsonl``.
- Quién lo hizo (``autor``): «sistema» si la escala (``escala.jsonl``) había decidido ese mismo presupuesto en las 6 h previas, o si la
  vigilancia lo anotó en ``presupuesto_cambios``/``apagado`` del libro; si no, «a_mano» (el dueño en el Administrador, u otra cosa fuera
  del sistema).
- ``desde_cambio(cid, t0)``: acumulado ahora − acumulado en t0 = días completos del historial_diario del libro + la foto del día.

Uso:
  python3 fotos_campanas.py eventos [--oferta "<nombre>"] [--dias 7]     (lista los cambios, para mirar a mano)
  python3 fotos_campanas.py desde --campana <id> --cuando <ISO>          (gasto/compras/valor desde ese momento)
  python3 fotos_campanas.py oferta --nombre "ES | Oferta F | CBO pocket B09"   (a qué oferta la asignaría; 1 si a ninguna)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[4]
FUNNELS = RAIZ / "ofertas" / "_funnels"
FOTOS = FUNNELS / "fotos_campanas.jsonl"
EVENTOS = FUNNELS / "presupuesto_eventos.jsonl"
ESTADO = FUNNELS / "fotos_estado.json"
ESCALA = FUNNELS / "escala.jsonl"
LIBRO = FUNNELS / "libro-de-tests.json"
DIAS_FOTOS = 15                    # las fotos más viejas se descartan (el historial diario queda en el libro)
CAMPOS = ("g", "n", "v", "ic")     # gasto, compras, valor de compras, pagos iniciados (acumulado de hoy en la cuenta)


def _f(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _fecha(x) -> dt.datetime | None:
    if not x:
        return None
    try:
        d = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def zona(libro: dict) -> ZoneInfo:
    return ZoneInfo(libro.get("zona_horaria_cuenta") or "America/Argentina/Buenos_Aires")


def campanas_del_libro(libro: dict) -> dict[str, dict]:
    """{id: {oferta, nombre, rol}} de todas las campañas del libro (la principal y las extra de ficha.campanas)."""
    out: dict[str, dict] = {}
    for t in libro.get("tests") or []:
        if not isinstance(t, dict):
            continue
        of = t.get("oferta") or t.get("nombre")
        c = t.get("campana")
        for cid in (c if isinstance(c, list) else [c]):
            if cid:
                out.setdefault(str(cid), {"oferta": of, "nombre": None, "rol": "principal"})
        for x in ((t.get("ficha") or {}).get("campanas") or []):
            if isinstance(x, dict) and x.get("id"):
                out[str(x["id"])] = {"oferta": of, "nombre": x.get("nombre"), "rol": x.get("rol") or "principal"}
    return out


# ---------- lectura de archivos ----------

def _jsonl(ruta: Path) -> list[dict]:
    out = []
    try:
        for ln in ruta.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def fotos() -> list[dict]:
    return _jsonl(FOTOS)


def eventos() -> list[dict]:
    return sorted(_jsonl(EVENTOS), key=lambda e: str(e.get("cuando") or ""))


# ---------- quién hizo el cambio ----------

def _decisiones_escala(desde: dt.datetime) -> list[dict]:
    out = []
    for ln in _jsonl(ESCALA):
        ahora = _fecha(ln.get("ahora"))
        if not ahora or ahora < desde:
            continue
        for d in ln.get("ofertas") or ln.get("campanas") or []:
            if isinstance(d, dict) and d.get("presupuesto_nuevo_usd") is not None:
                out.append({**d, "_cuando": ahora})
    return out


def autor_de(ev: dict, libro: dict, decisiones: list[dict] | None = None) -> tuple[str, str | None]:
    """('sistema', motivo) o ('a_mano', None) para un evento de presupuesto o de estado."""
    cuando = _fecha(ev.get("cuando"))
    if not cuando:
        return "a_mano", None
    if ev.get("tipo") == "presupuesto":
        for d in decisiones if decisiones is not None else _decisiones_escala(cuando - dt.timedelta(hours=6)):
            if str(d.get("campana")) == ev["campana"] and abs(_f(d.get("presupuesto_nuevo_usd")) - _f(ev.get("a"))) < 1.01 \
                    and cuando - dt.timedelta(hours=6) <= d["_cuando"] <= cuando + dt.timedelta(minutes=10):
                return "sistema", f"{d.get('decision')}: {d.get('porque') or ''}".strip()
    for t in libro.get("tests") or []:
        if not isinstance(t, dict):
            continue
        if ev.get("tipo") == "presupuesto":
            for c in t.get("presupuesto_cambios") or []:
                cc = _fecha(c.get("cuando"))
                if not cc or abs((cc - cuando).total_seconds()) > 3 * 3600 or abs(_f(c.get("a")) - _f(ev.get("a"))) >= 1.01:
                    continue
                if str(c.get("campana") or t.get("campana")) != ev["campana"]:
                    continue
                nota = str(c.get("nota") or "")
                if "dueño" in nota.lower() and "sin anotación" in nota.lower():
                    return "a_mano", nota[:300]
                return "sistema", (nota or c.get("tipo") or "")[:300]
        else:
            ap = t.get("apagado") if isinstance(t.get("apagado"), dict) else None
            ca = _fecha(ap.get("cuando")) if ap else None
            if ca and abs((ca - cuando).total_seconds()) <= 3 * 3600 and str(ev.get("a")) != "ACTIVE":
                regla = str(ap.get("regla") or "")
                return ("a_mano" if "dueño" in regla.lower() else "sistema"), (regla + ": " + str(ap.get("porque") or "")).strip(": ")[:300]
    return "a_mano", None


# ---------- registro desde la nube ----------

def foto_desde_nube(datos: dict, libro: dict, ahora: dt.datetime) -> dict:
    hoy = ahora.astimezone(zona(libro)).date().isoformat()
    mias = campanas_del_libro(libro)
    est = {str(c.get("id")): c for c in ((datos.get("meta_estado") or {}).get("campanas") or []) if isinstance(c, dict)}
    filas = {str(f.get("campana")): f for f in datos.get("meta_dia") or [] if f.get("fecha") == hoy}
    c = {}
    for cid in mias:
        e, f = est.get(cid), filas.get(cid)
        if not e and not f:
            continue
        c[cid] = {"p": round(_f(e.get("presupuesto_usd")), 2) if e and e.get("presupuesto_usd") is not None else None,
                  "e": (e or {}).get("estado"),
                  "g": round(_f((f or {}).get("gasto")), 2), "n": int(_f((f or {}).get("compras"))),
                  "v": round(_f((f or {}).get("valor_compras")), 2), "ic": int(_f((f or {}).get("pagos_iniciados")))}
    return {"t": ahora.astimezone(dt.timezone.utc).isoformat(timespec="seconds"), "dia": hoy, "c": c}


def registrar(foto: dict, libro: dict) -> list[dict]:
    """Guarda la foto (si cambió algo) y los eventos de presupuesto/estado. Devuelve los eventos nuevos."""
    try:
        previo = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previo = {}
    ult = previo.get("c") or {}
    nombres = campanas_del_libro(libro)
    nuevos: list[dict] = []
    decisiones = _decisiones_escala(_fecha(foto["t"]) - dt.timedelta(hours=6))
    for cid, x in foto["c"].items():
        a = ult.get(cid)
        if not a:
            if ult and x.get("p") is not None:   # campaña nueva en el libro (no la primera foto de todas): su arranque va a la línea de tiempo
                ev = {"cuando": foto["t"], "entre": previo.get("t"), "campana": cid, "oferta": nombres.get(cid, {}).get("oferta"),
                      "rol": nombres.get(cid, {}).get("rol"), "tipo": "presupuesto", "inicio": True, "de": None, "a": x["p"], "fuente": "fotos",
                      "autor": "sistema", "motivo": f"Campaña nueva en la oferta ({x.get('e') or 'sin estado'})."}
                nuevos.append(ev)
            continue
        for clave, tipo in (("p", "presupuesto"), ("e", "estado")):
            if x.get(clave) is None or a.get(clave) is None or x[clave] == a[clave]:
                continue
            if tipo == "presupuesto" and abs(_f(x[clave]) - _f(a[clave])) < 0.5:
                continue
            ev = {"cuando": foto["t"], "entre": previo.get("t"), "campana": cid, "oferta": nombres.get(cid, {}).get("oferta"),
                  "rol": nombres.get(cid, {}).get("rol"), "tipo": tipo, "de": a[clave], "a": x[clave], "fuente": "fotos"}
            ev["autor"], ev["motivo"] = autor_de(ev, libro, decisiones)
            nuevos.append(ev)
    cambio = any(foto["c"].get(k) != ult.get(k) for k in set(foto["c"]) | set(ult)) or previo.get("dia") != foto["dia"]
    if cambio:
        with FOTOS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(foto, ensure_ascii=False, separators=(",", ":")) + "\n")
    if nuevos:
        with EVENTOS.open("a", encoding="utf-8") as fh:
            for ev in nuevos:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    ESTADO.write_text(json.dumps({"t": foto["t"], "dia": foto["dia"], "c": {**ult, **foto["c"]}}, ensure_ascii=False), encoding="utf-8")
    _podar(foto["t"])
    return nuevos


def _podar(ahora_iso: str) -> None:
    """Una vez por día: descarta las fotos de más de DIAS_FOTOS días (los eventos no se podan)."""
    try:
        if FOTOS.stat().st_size < 4_000_000:
            return
    except OSError:
        return
    limite = (_fecha(ahora_iso) - dt.timedelta(days=DIAS_FOTOS)).isoformat()
    quedan = [f for f in fotos() if str(f.get("t") or "") >= limite]
    FOTOS.write_text("".join(json.dumps(f, ensure_ascii=False, separators=(",", ":")) + "\n" for f in quedan), encoding="utf-8")


def registrar_desde_nube(datos: dict, libro: dict, ahora: dt.datetime) -> list[dict]:
    return registrar(foto_desde_nube(datos, libro, ahora), libro)


# ---------- campañas que aparecen o cambian en la cuenta (dueño, 16-nov: «que el sistema detecte esa campaña y entienda dónde agregarla») ----------

SIN_OFERTA = FUNNELS / "campanas_sin_oferta.json"


def _norm(x) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(t.replace("|", " | ").split())


CORTE_REPLICA = {"pocket": 1.0, "test_variaciones": 1.5}
# R9 v2 (dueño, 17-nov): toda campaña diaria aparte se corta sola, también en ofertas que no son réplica (Nuevos e Iteraciones a 1,5
# tickets, pocket a 1). Las manuales (cost cap y bid cap) se limitan solas por la puja: sin corte.
def _cortes_por_rol() -> dict:
    try:
        from vigilar_corte import CORTES_POR_ROL  # noqa: PLC0415 (reglas.json → cortes_por_rol, un solo lugar)
        return dict(CORTES_POR_ROL)
    except Exception:  # noqa: BLE001
        return {"nuevos": 1.5, "iteraciones": 1.5, "pocket": 1.0, "test_variaciones": 1.5}


CORTE_DIARIA = _cortes_por_rol()


def rol_por_nombre(nombre: str, hay_principal: bool) -> str:
    import re
    n = _norm(nombre)
    # R9 v2 (17-nov): manuales, Nuevos e Iteraciones antes que nada («CBO Nuevos R6 (1-1-10)» contiene «1-1-10»).
    if "cost cap" in n or "costcap" in n:
        return "cost_cap"
    if "bid cap" in n or "bidcap" in n:
        return "bid_cap"
    if re.search(r"\bnuevos\b", n):
        return "nuevos"
    if "iteracion" in n:
        return "iteraciones"
    # Variaciones antes que pocket: «CBO test variaciones V1 (1-1-10)» contiene «1-1-1» y salía pocket (DE, 16-nov).
    if "variacion" in n or re.search(r"\b1-1-10\b", n):
        return "test_variaciones"
    if "pocket" in n or re.search(r"(?<![\d-])1-1-1(?![\d-])", n):
        return "pocket"
    if "renov" in n:
        return "renovacion"
    if "escala" in n or "scale" in n:
        return "escala"
    if "replica" in n:
        return "replica"
    return "otra" if hay_principal else "principal"


def oferta_de_campana(nombre: str, libro: dict) -> dict | None:
    """El test del libro al que pertenece una campaña por su nombre: «<MERCADO> | <oferta o nombre del test> | …» (como las nombra el
    sistema). El mercado tiene que coincidir: la misma oferta en otro país es otro test (réplica) y no se mezcla."""
    partes = [p.strip() for p in str(nombre or "").split("|")]
    if len(partes) < 2:
        return None
    mercado, resto = _norm(partes[0]).upper(), _norm(partes[1])
    candidatos = []
    for t in libro.get("tests") or []:
        if not isinstance(t, dict) or str(t.get("mercado") or "").upper() != mercado:
            continue
        for k in (t.get("oferta"), t.get("nombre")):
            kn = _norm(k)
            # «Oferta» es la campaña del test «Oferta»: el mercado ya separa la réplica
            if kn and (resto == kn or kn in resto or (len(resto) >= 4 and kn.startswith(resto + " "))):
                candidatos.append((len(kn), t))
    return max(candidatos, key=lambda x: x[0])[1] if candidatos else None


def asignar_campanas(libro: dict, campanas_meta: list[dict], ahora: dt.datetime) -> tuple[list[str], list[dict]]:
    """Puro sobre el dict del libro: (1) cada campaña de la cuenta que no está en el libro y cuyo nombre es de una oferta se agrega a
    ``ficha.campanas`` de ese test con su rol (por el nombre), estado y presupuesto; (2) las que ya están se ponen al día (estado,
    presupuesto, nombre). Devuelve (líneas de cambio, campañas activas sin oferta)."""
    conocidas = campanas_del_libro(libro)
    cambios, sin_oferta = [], []
    for c in campanas_meta or []:
        cid, nombre, estado = str(c.get("id") or ""), c.get("nombre"), c.get("estado")
        if not cid:
            continue
        pres = c.get("presupuesto_usd")
        if cid in conocidas:
            for t in libro.get("tests") or []:
                for x in ((t.get("ficha") or {}).get("campanas") or []) if isinstance(t, dict) else []:
                    if str(x.get("id")) == cid:
                        previo_e = str(x.get("estado") or "").split(" ")[0]   # «PAUSED (apagada por corte…)»: se compara el código, la nota queda
                        if estado and previo_e != estado:
                            cambios.append(f"{t.get('oferta')}: {x.get('nombre') or cid} {x.get('estado')} → {estado}")
                            x["estado"] = estado
                            if estado not in ("ACTIVE", "IN_PROCESS", "WITH_ISSUES") and not x.get("apagada_desde"):
                                x["apagada_desde"] = ahora.isoformat(timespec="minutes")
                            elif estado == "ACTIVE":
                                x.pop("apagada_desde", None)
                        if pres is not None and x.get("presupuesto_diario_usd") != pres:
                            x["presupuesto_diario_usd"] = pres
                        if nombre and not x.get("nombre"):
                            x["nombre"] = nombre
            continue
        t = oferta_de_campana(nombre, libro)
        if not t:
            if estado == "ACTIVE":
                sin_oferta.append({"id": cid, "nombre": nombre, "estado": estado, "presupuesto_usd": pres})
            continue
        ficha = t.setdefault("ficha", {})
        lista = ficha.setdefault("campanas", [])
        if not lista and t.get("campana") and not isinstance(t.get("campana"), list):
            lista.append({"id": str(t["campana"]), "rol": "principal"})   # la principal del test pasa a la lista para no perderla
        hay_principal = any(str(x.get("rol") or "").startswith("principal") for x in lista)
        rol = rol_por_nombre(nombre, hay_principal)
        nueva = {"id": cid, "nombre": nombre, "rol": rol, "estado": estado,
                 "presupuesto_diario_usd": pres, "detectada": ahora.isoformat(timespec="minutes"),
                 "nota": "Detectada sola en la cuenta de Meta por nube_sync (nombre «MERCADO | oferta | …»)."}
        # Réplica de una validada (dueño, 15-nov): pocket se corta a 1 ticket, variaciones a 1,5. Sin esto quedaba sin corte propio (DE, 16-nov).
        if t.get("replica_de") and rol in CORTE_REPLICA:
            nueva["corte_tickets"] = CORTE_REPLICA[rol]
        elif rol in CORTE_DIARIA:
            nueva["corte_tickets"] = CORTE_DIARIA[rol]   # R9 v2 (17-nov): las CBO diarias aparte se cortan solas
        lista.append(nueva)
        conocidas[cid] = {"oferta": t.get("oferta") or t.get("nombre")}
        cambios.append(f"{t.get('oferta') or t.get('nombre')}: campaña nueva detectada «{nombre}» ({lista[-1]['rol']})")
    return cambios, sin_oferta


# ---------- desde el último cambio ----------

def _historial(libro: dict, cid: str) -> dict[str, dict]:
    out = {}
    for t in libro.get("tests") or []:
        for f in (t.get("historial_diario") or []) if isinstance(t, dict) else []:
            if str(f.get("campana")) == cid and f.get("fecha"):
                out[str(f["fecha"])] = {"g": _f(f.get("gasto_usd")), "n": _f(f.get("compras_meta")), "v": _f(f.get("valor_compras_meta_usd")),
                                        "ic": _f(f.get("inicios_pago_meta"))}
    return out


def _foto_en(cid: str, cuando: dt.datetime, dia: str, lista: list[dict]) -> dict | None:
    """La última foto del día `dia` tomada antes de `cuando` que trae la campaña."""
    mejor = None
    for f in lista:
        if f.get("dia") != dia or cid not in (f.get("c") or {}):
            continue
        t = _fecha(f.get("t"))
        if t and t <= cuando and (mejor is None or t >= _fecha(mejor["t"])):
            mejor = f
    return mejor


def acumulado(libro: dict, cid: str, cuando: dt.datetime, lista: list[dict] | None = None) -> tuple[dict, bool]:
    """Acumulado de la campaña hasta `cuando` (días completos del historial + la foto de ese día). (valores, exacto)."""
    lista = fotos() if lista is None else lista
    z = zona(libro)
    dia = cuando.astimezone(z).date().isoformat()
    hist = _historial(libro, cid)
    tot = {k: sum(v[k] for d, v in hist.items() if d < dia) for k in CAMPOS}
    f = _foto_en(cid, cuando, dia, lista)
    if f:
        x = f["c"][cid]
        # exacto si la foto es de 20 min antes como mucho (la nube saca una cada 5 min)
        return {k: tot[k] + _f(x.get(k)) for k in CAMPOS}, (cuando - _fecha(f["t"])) <= dt.timedelta(minutes=20)
    primera = min((f for f in lista if f.get("dia") == dia and cid in (f.get("c") or {})), key=lambda f: f["t"], default=None)
    if primera and _fecha(primera["t"]) > cuando:
        # Hay fotos de ese día pero empiezan después: el cambio fue antes de la primera foto (si fue cerca de la medianoche, ~0).
        inicio_dia = dt.datetime.combine(cuando.astimezone(z).date(), dt.time(0), z)
        frac = max(0.0, min(1.0, (cuando - inicio_dia).total_seconds() / max(1.0, (_fecha(primera["t"]) - inicio_dia).total_seconds())))
        x = primera["c"][cid]
        return {k: tot[k] + frac * _f(x.get(k)) for k in CAMPOS}, frac < 0.05
    return tot, False   # sin fotos de ese día: se cuenta el día del cambio entero (aproximado)


def desde_cambio(libro: dict, cid: str, t0: dt.datetime, ahora: dt.datetime, lista: list[dict] | None = None) -> dict:
    lista = fotos() if lista is None else lista
    a1, ok1 = acumulado(libro, cid, ahora, lista)
    a0, ok0 = acumulado(libro, cid, t0, lista)
    d = {k: round(max(0.0, a1[k] - a0[k]), 2) for k in CAMPOS}
    return {"gasto_usd": d["g"], "compras": int(round(d["n"])), "valor_meta_usd": d["v"], "pagos_iniciados": int(round(d["ic"])),
            "exacto": ok0 and ok1}


def ultima_foto(cid: str, lista: list[dict] | None = None) -> dict | None:
    lista = fotos() if lista is None else lista
    for f in reversed(lista):
        if cid in (f.get("c") or {}):
            return {**f["c"][cid], "t": f["t"], "dia": f["dia"]}
    return None


def gasto_ultimas_horas(libro: dict, cid: str, ahora: dt.datetime, horas: float, lista: list[dict] | None = None) -> float | None:
    """Gasto de las últimas `horas` (para el ritmo). None si no hay fotos que lo cubran."""
    lista = fotos() if lista is None else lista
    t0 = ahora - dt.timedelta(hours=horas)
    if not any(_fecha(f.get("t")) and _fecha(f["t"]) <= t0 and cid in (f.get("c") or {}) for f in lista):
        return None
    return desde_cambio(libro, cid, t0, ahora, lista)["gasto_usd"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eventos")
    e.add_argument("--oferta")
    e.add_argument("--dias", type=float, default=7)
    o = sub.add_parser("oferta", help="a qué oferta asignaría el sistema una campaña con este nombre")
    o.add_argument("--nombre", required=True)
    d = sub.add_parser("desde")
    d.add_argument("--campana", required=True)
    d.add_argument("--cuando", required=True)
    a = ap.parse_args(argv)
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    ahora = dt.datetime.now(dt.timezone.utc)
    if a.cmd == "oferta":
        t = oferta_de_campana(a.nombre, libro)
        print(f"OK: {t.get('oferta') or t.get('nombre')} ({t.get('mercado')})" if t else "SIN OFERTA: el nombre tiene que ser «PAÍS | Oferta tal cual en el libro | tipo»")
        return 0 if t else 1
    if a.cmd == "eventos":
        lim = ahora - dt.timedelta(days=a.dias)
        for ev in eventos():
            c = _fecha(ev.get("cuando"))
            if c and c >= lim and (not a.oferta or ev.get("oferta") == a.oferta):
                print(json.dumps(ev, ensure_ascii=False))
    else:
        print(json.dumps(desde_cambio(libro, a.campana, _fecha(a.cuando), ahora), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
