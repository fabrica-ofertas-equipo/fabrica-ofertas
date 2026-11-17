"""Salud del funnel y de la cuenta en cada vuelta de la vigilancia (escenarios del 2026-11-13: S09, S14, S15, S26, S32, S33, S36).

Prueba por sí mismo (HTTP) la landing y los checkouts de cada oferta con campaña activa, y con la lectura de Meta que arma
la vigilancia revisa la cuenta, los pagos iniciados sin compra, los anuncios rechazados y el embudo post-compra.
Devuelve ACCIONES; el agente las ejecuta (pausar, reactivar, probar, avisar con avisos.py + PushNotification).

Reglas:
  PAUSAR_POR_CAIDA       landing o checkout caídos (error HTTP o sin respuesta) 2 vueltas seguidas con la campaña activa →
                         pausar en el momento: se paga tráfico a una página rota. Aviso urgente.
  REACTIVAR_TRAS_CAIDA   una campaña que pausó ESTA regla vuelve a prenderse cuando todo responde otra vez (solo esas;
                         las apagadas por corte no se reactivan). Aviso.
  AVISO_PIXEL            la landing responde pero no tiene el píxel de la ficha. Aviso urgente.
  PROBAR_CHECKOUT        10 o más pagos iniciados hoy y ninguna compra → probar el checkout (probar_funnel.py) y avisar.
  REVISAR_RECHAZOS       anuncios rechazados: apelar una vez cada uno; nunca se corrigen, reemplazan ni rehacen (dueño, 16-nov).
  EMBUDO_ROTO            hay ventas hoy, el backend está activo y el embudo post-compra no tuvo vistas → probar el demo y avisar.
  AVISO_CUENTA           la cuenta publicitaria no está activa (restringida, deuda, tarjeta rechazada). Urgente.
  AVISO_LIMITE           la cuenta gastó el 80 % o más de su límite de gasto.
  AVISO_CONECTOR         3 vueltas seguidas sin poder leer Meta. Urgente.
  AVISO_ACTIVO           una fan page o un píxel de una oferta quedó restringido o desactivado (S12). Urgente.
  AVISO_SESION           la sesión de Impultienda o de Facebook en el navegador está vencida: las tareas no pueden publicar,
                         cambiar precios ni poner el mínimo del 20 % hasta que el dueño la abra (S37). Urgente.

Uso: python3 .claude/skills/escalar-oferta/scripts/salud.py --lectura <lectura.json> [--sin-http] [--registrar]
lectura.json (lo arma la vigilancia; todo opcional salvo meta_ok):
  {"meta_ok": true,
   "cuenta": {"account_status": 1, "spend_cap_usd": 0, "amount_spent_usd": 120},
   "activos": [{"tipo": "pagina" | "pixel", "nombre": "…", "oferta": "…", "ok": true, "motivo": "…"}],
   "sesiones": {"impultienda": true, "facebook": true},
   "tests": {"<nombre>": {"campanas_activas": ["…"], "inicios_pago_hoy": 3, "compras_hoy": 1,
                          "rechazados": [{"id": "…", "motivo": "…"}], "ventas_hoy": 2, "vistas_embudo_hoy": 0}}}
Estado entre vueltas: ofertas/_funnels/salud.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
ESTADO = RAIZ / "ofertas" / "_funnels" / "salud.json"
REGISTRO = RAIZ / "ofertas" / "_funnels" / "salud.jsonl"
CAIDAS_PARA_PAUSAR = valor("salud.caidas_para_pausar", 2)
CHECKOUTS_SIN_COMPRA = valor("salud.checkouts_sin_compra", 10)
VUELTAS_SIN_META = valor("salud.vueltas_sin_meta", 3)
LIMITE_AVISO = valor("salud.limite_cuenta_aviso", 0.8)
TIEMPO_S = 20
UA = "Mozilla/5.0 (salud del funnel; uso interno)"


def probar_url(url: str) -> dict:
    """GET con tiempo acotado: {ok, estado, ms, html (los primeros 400 KB, para buscar el píxel)}."""
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=TIEMPO_S) as r:  # noqa: S310 - URLs https de la ficha del libro
            html = r.read(400_000).decode("utf-8", errors="replace")
            return {"ok": 200 <= r.status < 400, "estado": r.status, "ms": int((time.monotonic() - t0) * 1000), "html": html}
    except urllib.error.HTTPError as e:
        return {"ok": False, "estado": e.code, "ms": int((time.monotonic() - t0) * 1000), "html": ""}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"ok": False, "estado": None, "error": str(getattr(e, "reason", e))[:120], "ms": int((time.monotonic() - t0) * 1000), "html": ""}


def urls_de(t: dict) -> dict:
    """Landing y checkouts de un test, de su ficha (solo https)."""
    f = t.get("ficha") or {}
    out = {}
    for i, tienda in enumerate(f.get("tiendas") or []):
        u = tienda.get("url") if isinstance(tienda, dict) else None
        if isinstance(u, str) and u.startswith("https://"):
            out["tienda" if i == 0 else f"tienda_{i + 1}"] = u
            if i == 0:
                out["checkout"] = u.rstrip("/") + "/checkout"
    if isinstance(f.get("landing"), str) and f["landing"].startswith("https://"):
        out["landing"] = f["landing"]
    return out


def evaluar(lectura: dict, libro: dict, estado: dict, probar: Callable[[str], dict] | None) -> tuple[list[dict], dict]:
    acciones: list[dict] = []
    nuevo = {"ofertas": dict(estado.get("ofertas") or {}), "sin_meta": estado.get("sin_meta", 0)}

    # conector de Meta
    if not lectura.get("meta_ok"):
        nuevo["sin_meta"] += 1
        if nuevo["sin_meta"] >= VUELTAS_SIN_META:
            acciones.append({"accion": "AVISO_CONECTOR", "urgente": True, "clave": "conector-meta",
                             "mensaje": f"No se puede leer Meta hace {nuevo['sin_meta']} vueltas: la vigilancia no ve gasto ni ventas. Reconectar el conector."})
    else:
        nuevo["sin_meta"] = 0

    # cuenta publicitaria
    c = lectura.get("cuenta") or {}
    if c.get("account_status") not in (None, 1, "1", "ACTIVE"):
        acciones.append({"accion": "AVISO_CUENTA", "urgente": True, "clave": "cuenta-estado",
                         "mensaje": f"La cuenta publicitaria no está activa (estado {c.get('account_status')}, motivo {c.get('disable_reason', 'sin dato')}): los anuncios no corren."})
    cap, gastado = float(c.get("spend_cap_usd") or 0), float(c.get("amount_spent_usd") or 0)
    if cap > 0 and gastado >= LIMITE_AVISO * cap:
        acciones.append({"accion": "AVISO_LIMITE", "urgente": gastado >= cap, "clave": "cuenta-limite",
                         "mensaje": f"La cuenta gastó US$ {gastado:.0f} de un límite de US$ {cap:.0f} ({100 * gastado / cap:.0f} %). Al llegar, Meta corta todo."})

    for act in lectura.get("activos") or []:
        if isinstance(act, dict) and act.get("ok") is False:
            acciones.append({"accion": "AVISO_ACTIVO", "oferta": act.get("oferta"), "urgente": True, "clave": f"activo-{act.get('tipo')}-{act.get('nombre')}",
                             "mensaje": f"{act.get('oferta') or ''}: {'la fan page' if act.get('tipo') == 'pagina' else 'el píxel'} «{act.get('nombre')}» quedó restringido ({act.get('motivo') or 'sin motivo'}). Revisar en el Business Manager."})
    for sitio, ok in (lectura.get("sesiones") or {}).items():
        if ok is False:
            acciones.append({"accion": "AVISO_SESION", "urgente": True, "clave": f"sesion-{sitio}",
                             "mensaje": f"La sesión de {sitio.capitalize()} en el navegador de Claude está vencida: abrila para que las tareas puedan seguir."})

    for t in libro.get("tests") or []:
        nombre = t.get("nombre") or t.get("oferta")
        lt = (lectura.get("tests") or {}).get(nombre) or {}
        activas = lt.get("campanas_activas") or []
        st = dict(nuevo["ofertas"].get(nombre) or {"caidas": 0, "pausada_por_caida": []})
        if t.get("estado") not in ("activo", "programado") and not st.get("pausada_por_caida"):
            continue
        # landing y checkouts
        if probar:
            urls = urls_de(t)
            pruebas = {k: probar(u) for k, u in urls.items()}
            caidas = [k for k, r in pruebas.items() if not r["ok"]]
            st["ultima_prueba"] = {k: {"ok": r["ok"], "estado": r.get("estado"), "ms": r.get("ms")} for k, r in pruebas.items()}
            if caidas:
                st["caidas"] = st.get("caidas", 0) + 1
                if st["caidas"] >= CAIDAS_PARA_PAUSAR and activas:
                    acciones.append({"accion": "PAUSAR_POR_CAIDA", "oferta": nombre, "campanas": activas, "urgente": True, "clave": f"caida-{nombre}",
                                     "mensaje": f"{nombre}: {', '.join(caidas)} no responde hace {st['caidas']} vueltas; se pausa la campaña para no pagar tráfico a una página rota."})
            else:
                if st.get("pausada_por_caida"):
                    acciones.append({"accion": "REACTIVAR_TRAS_CAIDA", "oferta": nombre, "campanas": st["pausada_por_caida"], "urgente": False,
                                     "clave": f"vuelve-{nombre}", "mensaje": f"{nombre}: la página volvió a responder; se reactiva la campaña que se había pausado por la caída."})
                st["caidas"] = 0
                pixel = str(((t.get("ficha") or {}).get("pixel") or {}).get("id") or "")
                html = (pruebas.get("landing") or pruebas.get("tienda") or {}).get("html", "")
                if pixel and html and pixel not in html:
                    acciones.append({"accion": "AVISO_PIXEL", "oferta": nombre, "urgente": True, "clave": f"pixel-{nombre}",
                                     "mensaje": f"{nombre}: la página responde pero no tiene el píxel {pixel}: Meta no ve las compras."})
        # pagos iniciados sin compra
        if int(lt.get("inicios_pago_hoy") or 0) >= CHECKOUTS_SIN_COMPRA and int(lt.get("compras_hoy") or 0) == 0:
            acciones.append({"accion": "PROBAR_CHECKOUT", "oferta": nombre, "urgente": True, "clave": f"checkout-{nombre}",
                             "mensaje": f"{nombre}: {lt['inicios_pago_hoy']} pagos iniciados hoy y ninguna compra; probando el checkout."})
        # anuncios rechazados
        if lt.get("rechazados"):
            acciones.append({"accion": "REVISAR_RECHAZOS", "oferta": nombre, "anuncios": lt["rechazados"], "urgente": False,
                             "clave": f"rechazos-{nombre}", "mensaje": f"{nombre}: {len(lt['rechazados'])} anuncios rechazados; se apelan una vez, no se reemplazan."})
        # embudo post-compra
        b = t.get("backend") or {}
        if int(lt.get("ventas_hoy") or 0) > 0 and b.get("estado") == "activo" and lt.get("vistas_embudo_hoy") == 0:
            acciones.append({"accion": "EMBUDO_ROTO", "oferta": nombre, "urgente": True, "clave": f"embudo-{nombre}",
                             "mensaje": f"{nombre}: {lt['ventas_hoy']} ventas hoy y nadie vio los upsells: el embudo post-compra puede estar roto."})
        nuevo["ofertas"][nombre] = st
    return acciones, nuevo


def aplicar_resultado(estado: dict, accion: str, oferta: str, campanas: list[str]) -> None:
    """Lo llama el agente después de ejecutar: `--hecho PAUSAR_POR_CAIDA --oferta X --campanas a,b`."""
    st = estado.setdefault("ofertas", {}).setdefault(oferta, {"caidas": 0, "pausada_por_caida": []})
    if accion == "PAUSAR_POR_CAIDA":
        st["pausada_por_caida"] = sorted(set(st.get("pausada_por_caida") or []) | set(campanas))
    elif accion == "REACTIVAR_TRAS_CAIDA":
        st["pausada_por_caida"] = []


def _guardar(p: Path, dato) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(dato, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lectura")
    ap.add_argument("--sin-http", action="store_true")
    ap.add_argument("--registrar", action="store_true")
    ap.add_argument("--hecho", choices=["PAUSAR_POR_CAIDA", "REACTIVAR_TRAS_CAIDA"])
    ap.add_argument("--oferta")
    ap.add_argument("--campanas", default="")
    a = ap.parse_args(argv)
    try:
        estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        estado = {}
    if a.hecho:
        aplicar_resultado(estado, a.hecho, a.oferta, [c for c in a.campanas.split(",") if c])
        _guardar(ESTADO, estado)
        print(f"{a.oferta}: {a.hecho} anotado.")
        return 0
    lectura = json.loads(Path(a.lectura).read_text(encoding="utf-8")) if a.lectura else {"meta_ok": True}
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    acciones, nuevo = evaluar(lectura, libro, estado, None if a.sin_http else probar_url)
    nuevo["leido"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    _guardar(ESTADO, nuevo)
    salida = {"leido": nuevo["leido"], "acciones": acciones,
              "pruebas": {k: v.get("ultima_prueba") for k, v in nuevo["ofertas"].items() if v.get("ultima_prueba")}}
    if a.registrar:
        with REGISTRO.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"leido": nuevo["leido"], "acciones": [x["accion"] + ":" + str(x.get("oferta")) for x in acciones]}, ensure_ascii=False) + "\n")
    print(json.dumps(salida, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
