"""``GET /api/flujo`` (pantalla «Cómo funciona»): el pulso en vivo de los procesos del sistema de ofertas.

Pedido del dueño (2026-11-13): ver los procesos del sistema (buscar → lanzar → test → apagar o backend → renovar y escalar →
aprender) como un flujo vivo, con cuándo se activa cada uno y qué skill lo hace. Las ofertas de cada paso salen de
``GET /api/negocio`` (etapa y backend); esta ruta suma lo que el tablero Negocio no tiene:

* ``vigilancia``: la última vuelta de la tarea de cada hora (``ofertas/_funnels/vigilancia.jsonl``) y su decisión por test;
* ``banco``: si el banco de candidatos alcanza para elegir o hay que barrer (``banco_candidatos.py estado --json``), y
  ``buscar_diario``: el último informe de la vuelta diaria de ``buscar-ofertas``;
* ``armado``: carpetas ``ofertas/_borrador-*`` que todavía no están en el libro de tests (ofertas que se están lanzando);
* ``skills``: versión y estado de las skills que mueven el flujo (frontmatter de cada ``SKILL.md``);
* ``lanzamientos``: el historial de ofertas modeladas (``ofertas/historial-modelado.json``).

Solo lectura. El único proceso que se lanza es el script del banco, con argumentos fijos, ``shell=False``, entorno mínimo y
tope de tiempo; si falla, el bloque ``banco`` llega con ``error`` y la pantalla lo dice.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import tienda
from dashboard.api_base import Ctx, Sobre

__all__ = ["flujo", "SKILLS_DEL_FLUJO", "ultima_vigilancia", "skill_info"]

REL_VIGILANCIA = "ofertas/_funnels/vigilancia.jsonl"
REL_LIBRO = "ofertas/_funnels/libro-de-tests.json"
REL_HISTORIAL = "ofertas/historial-modelado.json"
REL_DIARIO_BANCO = "empresa/barrido/banco/diario"
REL_BANCO_SCRIPT = ".claude/skills/modelar-y-lanzar-oferta/scripts/banco_candidatos.py"
SKILLS_DEL_FLUJO = ("buscar-ofertas", "modelar-y-lanzar-oferta", "backend-ofensivo", "escalar-oferta")
_RX_BORRADOR = re.compile(r"^_borrador-[a-z0-9-]{1,60}$")
_MAX_LINEAS_VIG = 400          # se leen solo las últimas líneas del registro
_TIEMPO_BANCO_S = 10


def _leer_lineas_finales(p: Path, n: int) -> list[str]:
    try:
        with p.open("rb") as f:
            f.seek(0, 2)
            tam = f.tell()
            f.seek(max(0, tam - 400_000))
            datos = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return [ln for ln in datos.splitlines() if ln.strip()][-n:]


def _fecha(v: Any) -> _dt.datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        d = _dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def ultima_vigilancia(lineas: list[str], ahora: _dt.datetime) -> dict[str, Any]:
    """Última vuelta registrada, minutos desde entonces, vueltas de las últimas 24 h y la decisión por test."""
    vueltas = []
    for ln in lineas:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and _fecha(r.get("ahora")):
            vueltas.append(r)
    if not vueltas:
        return {"existe": False}
    ult = vueltas[-1]
    cuando = _fecha(ult.get("ahora"))
    edad = max(0, int((ahora - cuando).total_seconds() // 60)) if cuando else None
    hace24 = ahora - _dt.timedelta(hours=24)
    n24 = sum(1 for r in vueltas if (_fecha(r.get("ahora")) or hace24) > hace24)
    tests = []
    for t in (ult.get("tests") or [])[:40]:
        if not isinstance(t, dict):
            continue
        tests.append({k: t.get(k) for k in ("test", "mercado", "fase", "decision", "gasto_usd", "ventas", "corte_usd", "ticket_corte_usd", "ticket_front_usd", "motivo") if k in t})
    if edad is None:
        salud = "sin_dato"
    elif edad <= 90:
        salud = "ok"
    elif edad <= 180:
        salud = "aviso"
    else:
        salud = "error"
    return {"existe": True, "ultima": ult.get("ahora"), "leido": ult.get("leido"), "edad_min": edad, "vueltas_24h": n24,
            "salud": salud, "regla": str(ult.get("regla") or "")[:200], "tests": tests}


def _banco(ctx: Ctx) -> dict[str, Any]:
    script = ctx.raiz / REL_BANCO_SCRIPT
    if not script.is_file():
        return {"error": "No está el script del banco de candidatos."}
    try:
        r = subprocess.run(  # noqa: S603 - argv fijo, shell=False, solo lectura (el subcomando «estado» no escribe)
            [sys.executable, "-I", str(script), "estado", "--json"], cwd=ctx.raiz, shell=False, capture_output=True,
            timeout=_TIEMPO_BANCO_S, env={"PATH": "/usr/bin:/bin", "LANG": "es_ES.UTF-8"}, stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"error": "El script del banco no respondió a tiempo."}
    salida = r.stdout.decode("utf-8", errors="replace").strip()
    if r.returncode != 0 or not salida.startswith("{"):
        if "vacío" in salida:
            return {"veredicto": "HAY QUE BARRER", "motivos": ["el banco está vacío"], "ofertas": 0, "usadas": 0, "listos": []}
        return {"error": "No se pudo leer el estado del banco."}
    try:
        d = json.loads(salida)
    except ValueError:
        return {"error": "El estado del banco no se entendió."}
    return {k: d.get(k) for k in ("veredicto", "motivos", "ultimo_barrido", "ofertas", "usadas", "listos", "por_verificar", "bajo_piso", "volver_a_medir")}


def skill_info(texto: str) -> dict[str, Any]:
    """Versión y estado del frontmatter de un SKILL.md (``metadata.version`` / ``metadata.estado``)."""
    cab = texto.split("\n---", 1)[0] if texto.startswith("---") else ""
    v = re.search(r'^\s*version:\s*"?([0-9][^"\n]*)"?', cab, re.M)
    e = re.search(r'^\s*estado:\s*"?([^"\n]*)"?', cab, re.M)
    return {"version": v.group(1).strip() if v else None, "estado": e.group(1).strip()[:200] if e else None}


def _skills(ctx: Ctx) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for slug in SKILLS_DEL_FLUJO:
        p = ctx.raiz / ".claude" / "skills" / slug / "SKILL.md"
        try:
            out[slug] = {"existe": True, **skill_info(p.read_text(encoding="utf-8")[:4000])}
        except OSError:
            out[slug] = {"existe": False, "version": None, "estado": None}
    return out


def _armado(ctx: Ctx, libro: Any) -> list[dict[str, Any]]:
    """Carpetas de trabajo que todavía no están en el libro: ofertas que se están armando."""
    en_libro = set()
    for t in (libro.get("tests") or []) if isinstance(libro, dict) else []:
        c = ((t or {}).get("ficha") or {}).get("carpeta_trabajo")
        if isinstance(c, str):
            en_libro.add(c.rstrip("/").rsplit("/", 1)[-1])
    out = []
    try:
        nombres = sorted(n for n in ctx.raiz_confinada.listar("ofertas", solo="dir") if _RX_BORRADOR.fullmatch(n))
    except Exception:  # noqa: BLE001 - sin carpeta de ofertas, no hay armado
        nombres = []
    for n in nombres:
        if n in en_libro:
            continue
        p = ctx.raiz / "ofertas" / n / "estado.md"
        titulo, hechas, total = n.removeprefix("_borrador-"), 0, 0
        try:
            txt = p.read_text(encoding="utf-8")[:20000]
            m = re.search(r"^#\s+(.+)$", txt, re.M)
            if m:
                titulo = m.group(1).strip()[:80]
            hechas = len(re.findall(r"^\s*[-*]\s*\[[xX]\]", txt, re.M))
            total = hechas + len(re.findall(r"^\s*[-*]\s*\[ \]", txt, re.M))
        except OSError:
            pass
        out.append({"carpeta": n, "titulo": titulo, "fases_hechas": hechas, "fases_total": total})
    return out[:30]


def _buscar_diario(ctx: Ctx) -> dict[str, Any]:
    """Último informe de la vuelta diaria de buscar-ofertas (``empresa/barrido/banco/diario/AAAA-MM-DD.md``)."""
    carpeta = ctx.raiz / REL_DIARIO_BANCO
    try:
        fechas = sorted(p.stem for p in carpeta.glob("*.md") if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", p.stem))
    except OSError:
        fechas = []
    if not fechas:
        return {"fecha": None}
    ult = fechas[-1]
    resumen = ""
    try:
        for ln in (carpeta / f"{ult}.md").read_text(encoding="utf-8")[:4000].splitlines():
            if ln.strip() and not ln.startswith("#"):
                resumen = ln.strip()[:200]
                break
    except OSError:
        pass
    return {"fecha": ult, "resumen": resumen, "dias": len(fechas)}


def _radar(ctx: Ctx) -> dict[str, Any]:
    """Resumen del radar de ofertas (``empresa/barrido/radar/``): búsquedas, cobertura, ofertas por estado y mejores joyas."""
    lec_c = ctx.raiz_confinada.json("empresa/barrido/radar/cola.json")
    lec_o = ctx.raiz_confinada.json("empresa/barrido/radar/ofertas.json")
    if not lec_c.ok or not isinstance(lec_c.dato, dict):
        return {"existe": False}
    bs = [b for b in (lec_c.dato.get("busquedas") or []) if isinstance(b, dict)]
    hoy = ctx.ahora().date()
    def _dia(b: dict) -> Any:
        try:
            return _dt.date.fromisoformat(str(b.get("ultima"))[:10])
        except ValueError:
            return None
    dias = [d for d in (_dia(b) for b in bs) if d]
    semana = sum(1 for d in dias if (hoy - d).days < 7)
    ofertas = lec_o.dato if lec_o.ok and isinstance(lec_o.dato, dict) else {}
    por_estado: dict[str, int] = {}
    for o in ofertas.values():
        if isinstance(o, dict):
            e = str(o.get("estado") or "nuevo")[:20]
            por_estado[e] = por_estado.get(e, 0) + 1
    mejores = sorted([o for o in ofertas.values() if isinstance(o, dict) and o.get("estado") in ("a_medir", "a_verificar", "verificada", "exportada")],
                     key=lambda o: -(o.get("joya") or 0))[:5]
    ultima = max((str(b.get("ultima")) for b in bs if b.get("ultima")), default=None)
    bloq = ctx.raiz_confinada.json("empresa/barrido/radar/bloqueo.json")
    bloqueo = None
    if bloq.ok and isinstance(bloq.dato, dict) and _fecha(bloq.dato.get("hasta")) and _fecha(bloq.dato.get("hasta")) > ctx.ahora():
        bloqueo = {"hasta": str(bloq.dato.get("hasta"))[:25], "motivo": str(bloq.dato.get("motivo") or "")[:160]}
    edad = int((ctx.ahora() - _fecha(ultima)).total_seconds() // 60) if _fecha(ultima) else None
    return {"existe": True, "busquedas": len(bs), "cubiertas_7_dias": semana, "cobertura_pct": round(100 * semana / len(bs), 1) if bs else 0.0,
            "paises": len({b.get("pais") for b in bs if b.get("corridas")}), "hoy": sum(1 for d in dias if d == hoy),
            "ultima": ultima, "edad_min": edad, "ofertas": len(ofertas), "por_estado": por_estado, "bloqueo": bloqueo,
            "mejores": [{"clave": str(o.get("clave"))[:80], "estado": o.get("estado"), "joya": o.get("joya"),
                         "anuncios": o.get("anuncios_total") or o.get("anuncios_vistos"), "dias": o.get("max_dias"),
                         "pagina": str((o.get("paginas") or ["?"])[0])[:80]} for o in mejores]}


RITMO_TAREAS = {"vigilancia-ofertas": 60, "radar-ofertas": 120, "renovacion-diaria": 1440, "buscar-ofertas": 1440,
                "lanzar-ofertas": 720, "revision-diaria": 1440, "soporte-clientes": 720}


def _tareas(ctx: Ctx) -> list[dict[str, Any]]:
    """Latido de cada tarea programada (``ofertas/_funnels/latidos.json``, lo escribe ``avisos.py latido``)."""
    lec = ctx.raiz_confinada.json("ofertas/_funnels/latidos.json")
    lat = lec.dato if lec.ok and isinstance(lec.dato, dict) else {}
    out = []
    for tarea, ritmo in RITMO_TAREAS.items():
        t = lat.get(tarea) if isinstance(lat.get(tarea), dict) else None
        cuando = _fecha(t.get("ultimo")) if t else None
        if not cuando:
            out.append({"tarea": tarea, "salud": "sin_dato", "ritmo_min": ritmo})
            continue
        edad = int((ctx.ahora() - cuando).total_seconds() // 60)
        fallas = int(t.get("fallas_seguidas") or 0)
        salud = "error" if fallas >= 3 or edad > 2 * ritmo else ("aviso" if t.get("resultado") != "ok" else "ok")
        out.append({"tarea": tarea, "salud": salud, "edad_min": edad, "ritmo_min": ritmo, "fallas_seguidas": fallas,
                    "detalle": str(t.get("detalle") or "")[:160]})
    return out


def _avisos(ctx: Ctx) -> list[dict[str, Any]]:
    """Últimos avisos enviados al dueño (``ofertas/_funnels/avisos.jsonl``)."""
    out = []
    for ln in reversed(_leer_lineas_finales(ctx.raiz / "ofertas/_funnels/avisos.jsonl", 60)):
        try:
            a = json.loads(ln)
        except ValueError:
            continue
        if isinstance(a, dict) and a.get("enviado"):
            out.append({"cuando": str(a.get("cuando"))[:25], "mensaje": str(a.get("mensaje") or "")[:200], "urgente": bool(a.get("urgente"))})
        if len(out) >= 8:
            break
    return out


REL_VERIFICACIONES = "ofertas/_funnels/verificaciones.jsonl"
VERIFICADO_VISIBLE_H = 24


def _verificaciones(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for ln in _leer_lineas_finales(ctx.raiz / REL_VERIFICACIONES, 200):
        try:
            v = json.loads(ln)
        except ValueError:
            continue
        if isinstance(v, dict) and _fecha(v.get("cuando")):
            out.append(v)
    return out


def pedir_verificacion(ctx: Ctx, cuerpo: Any) -> Sobre:
    """``POST /api/flujo/verificar`` {tipo: "capi", oferta}: el dueño avisa que ya cargó el token. Solo anota el pedido en
    ``ofertas/_funnels/verificaciones.jsonl``; la comprobación la hace la vigilancia (lee si el campo está lleno, nunca el valor)
    y escribe el resultado en el libro, que el panel muestra en vivo."""
    from dashboard.seguridad import ErrorHttp
    if not isinstance(cuerpo, dict) or cuerpo.get("tipo") != "capi" or not isinstance(cuerpo.get("oferta"), str):
        raise ErrorHttp(400, "pedido_invalido", "Falta qué verificar.")
    oferta = cuerpo["oferta"].strip()[:80]
    libro = ctx.raiz_confinada.json(REL_LIBRO)
    nombres = {str(t.get("nombre") or t.get("oferta")) for t in ((libro.dato or {}).get("tests") or [])} if libro.ok else set()
    if oferta not in nombres:
        raise ErrorHttp(404, "oferta_desconocida", "Esa oferta no está en el libro de tests.")
    linea = {"cuando": ctx.ahora().isoformat(timespec="seconds"), "tipo": "capi", "oferta": oferta, "estado": "pendiente"}
    destino = ctx.raiz / REL_VERIFICACIONES
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    return Sobre(linea, [REL_VERIFICACIONES])


def _manos(ctx: Ctx, libro: Any) -> list[dict[str, Any]]:
    """Lo que espera las manos del dueño, con los enlaces para hacerlo rápido: token CAPI por píxel (tiendas con
    `capi.ok` false), saldo de Kie bajo (``ofertas/_funnels/kie.json`` de chequeos_diarios) y sesiones vencidas (avisos)."""
    out: list[dict[str, Any]] = []
    verifs = _verificaciones(ctx)
    for t in (libro.get("tests") or []) if isinstance(libro, dict) else []:
        if t.get("estado") not in ("activo", "programado"):
            continue
        f = t.get("ficha") or {}
        pixel = str((f.get("pixel") or {}).get("id") or "")
        faltan = []
        for x in f.get("tiendas") or []:
            # Sin el campo `capi` cuenta como pendiente: una tienda sin comprobar no puede quedar sin aviso.
            if isinstance(x, dict) and (not isinstance(x.get("capi"), dict) or x["capi"].get("ok") is False):
                slug = str(x.get("slug") or x.get("nombre") or "")
                if re.fullmatch(r"[a-z0-9-]{1,60}", slug):
                    faltan.append({"tienda": slug, "url": tienda.activa().url_panel(slug, "configuracion")})
        nombre = str(t.get("nombre") or t.get("oferta"))[:80]
        pedidos = [v for v in verifs if v.get("tipo") == "capi" and v.get("oferta") == nombre]
        ultimo_pedido = max((_fecha(v["cuando"]) for v in pedidos), default=None)
        revisados = [_fecha((x.get("capi") or {}).get("revisado")) for x in f.get("tiendas") or [] if isinstance(x, dict) and isinstance(x.get("capi"), dict)]
        ultimo_revisado = max((r for r in revisados if r), default=None)
        if faltan and re.fullmatch(r"[0-9]{6,20}", pixel):
            estado = "verificando" if ultimo_pedido and (not ultimo_revisado or ultimo_pedido > ultimo_revisado) else "pendiente"
            out.append({"tipo": "capi", "estado": estado, "urgente": estado == "pendiente", "oferta": nombre, "pixel": pixel,
                        "pedido": ultimo_pedido.isoformat() if ultimo_pedido else None,
                        "url_meta": f"https://business.facebook.com/events_manager2/list/pixel/{pixel}/settings", "tiendas": faltan})
        elif pedidos and ultimo_revisado and (ctx.ahora() - ultimo_revisado).total_seconds() < VERIFICADO_VISIBLE_H * 3600:
            out.append({"tipo": "capi", "estado": "verificado", "urgente": False, "oferta": nombre, "pixel": pixel,
                        "verificado": ultimo_revisado.isoformat(), "tiendas": []})
    kie = ctx.raiz_confinada.json("ofertas/_funnels/kie.json")
    if kie.ok and isinstance(kie.dato, dict) and isinstance(kie.dato.get("saldo"), (int, float)) and kie.dato["saldo"] < 5400:
        out.append({"tipo": "kie", "urgente": kie.dato["saldo"] < 2700, "saldo": kie.dato["saldo"], "cuando": str(kie.dato.get("cuando"))[:25],
                    "url": "https://kie.ai"})
    mv = ctx.raiz_confinada.json("ofertas/_funnels/meta_vivo.json")
    if mv.ok and isinstance(mv.dato, dict) and mv.dato.get("error") in ("falta_token", "token_invalido", "permiso"):
        out.append({"tipo": "meta_token", "urgente": False, "error": mv.dato["error"], "app": "2000000000000467", "cuenta": "TU_CUENTA_META",
                    "nube": str(mv.dato.get("fuente") or "").startswith("nube"),
                    "url_apps": "https://business.facebook.com/latest/settings/apps",
                    "url_usuarios": "https://business.facebook.com/latest/settings/system_users"})
    return out


def _servicios(ctx: Ctx) -> list[dict[str, Any]]:
    """Servicios pagos con su último estado (``servicios.json`` + ``servicios_estado.json``)."""
    reg = ctx.raiz_confinada.json("ofertas/_funnels/servicios.json")
    est = ctx.raiz_confinada.json("ofertas/_funnels/servicios_estado.json")
    estados = est.dato if est.ok and isinstance(est.dato, dict) else {}
    out = []
    for s in ((reg.dato or {}).get("servicios") or []) if reg.ok else []:
        if not isinstance(s, dict):
            continue
        e = estados.get(s.get("id")) if isinstance(estados.get(s.get("id")), dict) else {}
        url = s.get("url") if isinstance(s.get("url"), str) and s["url"].startswith("https://") else None
        # antigüedad de la lectura contra el ritmo esperado (dueño, 14-nov: «el gasto de Claude de 88 % sigue desactualizado»)
        cada = s.get("cada_horas") if isinstance(s.get("cada_horas"), (int, float)) else None
        edad = None
        try:
            leido = _dt.datetime.fromisoformat(str(e.get("cuando")).replace("Z", "+00:00"))
            edad = round((_dt.datetime.now(_dt.timezone.utc) - (leido if leido.tzinfo else leido.replace(tzinfo=_dt.timezone.utc))).total_seconds() / 3600, 1)
        except ValueError:
            pass
        out.append({"cada_horas": cada, "edad_horas": edad, "viejo": bool(cada and edad is not None and edad > 2 * cada),
                    "id": str(s.get("id"))[:30], "nombre": str(s.get("nombre"))[:80], "para": str(s.get("para") or "")[:160], "url": url,
                    "critico": bool(s.get("critico")), "renueva": s.get("renueva"), "recarga": str(s.get("recarga") or "")[:300], "estado": e.get("estado") or "sin_dato",
                    "detalle": str(e.get("detalle") or "")[:200], "cuando": str(e.get("cuando") or "")[:25]})
    return out


def _embudo(ctx: Ctx) -> list[dict[str, Any]]:
    """«Dónde se pierde» cada oferta: lo último de ``metricas_embudo.py`` (vuelta, periodos y anuncios) en ``embudo.json``."""
    est = ctx.raiz_confinada.json("ofertas/_funnels/embudo.json")
    if not est.ok or not isinstance(est.dato, dict):
        return []
    num = lambda x: x if isinstance(x, (int, float)) and not isinstance(x, bool) else None  # noqa: E731
    out = []
    for nombre, modos in list(est.dato.items())[:30]:
        if not isinstance(modos, dict):
            continue
        v = modos.get("vuelta") if isinstance(modos.get("vuelta"), dict) else {}
        p = modos.get("periodos") if isinstance(modos.get("periodos"), dict) else {}
        a = modos.get("anuncios") if isinstance(modos.get("anuncios"), dict) else {}
        cpm = v.get("cpm") if isinstance(v.get("cpm"), dict) else {}
        out.append({
            "oferta": str(nombre)[:80],
            "carga_pct": num(v.get("carga_pct")), "costo_por_visita": num(v.get("costo_por_visita")),
            "ingreso_por_visita": num(v.get("ingreso_por_visita")), "pagina_a_pago_pct": num(v.get("pagina_a_pago_pct")),
            "pago_a_compra_pct": num(v.get("pago_a_compra_pct")), "cpm_estado": str(cpm.get("estado") or "")[:20] or None,
            "avisos": [str(x.get("mensaje"))[:240] for x in (v.get("acciones") or []) + (p.get("acciones") or []) if isinstance(x, dict)][:4],
            "lado": str(p.get("lado") or "")[:20] or None, "cambio_costo_pct": num(p.get("cambio_costo_pct")),
            "cambio_ingreso_pct": num(p.get("cambio_ingreso_pct")), "clon": str(p.get("clon") or "")[:20] or None,
            "anuncios": {str(k)[:20]: int(n) for k, n in (a.get("resumen") or {}).items() if isinstance(n, int)},
            "cuando": str(v.get("cuando") or p.get("cuando") or a.get("cuando") or "")[:25]})
    return out


def _lanzamientos(ctx: Ctx) -> list[dict[str, Any]]:
    lec = ctx.raiz_confinada.json(REL_HISTORIAL)
    if not lec.ok or not isinstance(lec.dato, list):
        return []
    out = []
    for r in lec.dato[-12:]:
        if isinstance(r, dict):
            out.append({k: str(r.get(k))[:80] for k in ("fecha", "oferta", "funnel", "pais_destino") if r.get(k) is not None})
    return out


def flujo(ctx: Ctx) -> Sobre:
    """``{vigilancia, banco, buscar_diario, armado[], skills{}, lanzamientos[]}``."""
    ahora = ctx.ahora()
    libro = ctx.raiz_confinada.json(REL_LIBRO)
    datos = {
        "vigilancia": ultima_vigilancia(_leer_lineas_finales(ctx.raiz / REL_VIGILANCIA, _MAX_LINEAS_VIG), ahora),
        "banco": _banco(ctx),
        "buscar_diario": _buscar_diario(ctx),
        "radar": _radar(ctx),
        "tareas": _tareas(ctx),
        "manos": _manos(ctx, libro.dato if libro.ok else None),
        "servicios": _servicios(ctx),
        "embudo": _embudo(ctx),
        "avisos": _avisos(ctx),
        "armado": _armado(ctx, libro.dato if libro.ok else None),
        "skills": _skills(ctx),
        "lanzamientos": _lanzamientos(ctx),
        "generado": ahora.isoformat(timespec="minutes"),
    }
    return Sobre(datos, [REL_VIGILANCIA, REL_LIBRO, REL_HISTORIAL, "empresa/barrido/banco/"], vacio=False, avisos=[])
