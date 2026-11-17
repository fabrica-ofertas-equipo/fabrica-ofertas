"""Meta en vivo, sin Claude y sin tokens (pedido del dueño del 2026-11-13: «que actualice más rápido, en tiempo real
inclusive, sin gastar nada»).

Un programa común (no un agente) que lee la API de Meta directo con un token de solo lectura y deja el resultado en
`ofertas/_funnels/meta_vivo.json`. Lo corre el agente de inicio `com.fabrica.meta-vivo` cada 10 minutos (Meta refresca sus
estadísticas cada ~15 min y las compras llegan con ~20 min de atraso: más seguido no trae nada nuevo). El panel lo muestra
en vivo y se redibuja solo cuando el archivo cambia. Dos llamadas por vuelta (campañas e insights de hoy de toda la cuenta):
muy lejos de los límites de Meta.

No decide nada ni toca campañas: solo lee. Las decisiones siguen en la vigilancia de cada hora.

Token: `META_ACCESS_TOKEN` en `.env` (token de usuario del sistema con `ads_read`; lo genera y lo pega el dueño, nunca el
agente). Sin token, el archivo dice `falta_token` y el panel muestra los pasos en «Lo que espera tus manos».

Uso: python3 .claude/skills/escalar-oferta/scripts/meta_vivo.py [--probar]   (--probar: solo dice si el token sirve)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
SALIDA = RAIZ / "ofertas" / "_funnels" / "meta_vivo.json"
CUENTA = str(valor("meta_vivo.cuenta", "TU_CUENTA_META"))
VERSION = str(valor("meta_vivo.version_api", "v23.0"))
GRAPH = f"https://graph.facebook.com/{VERSION}"

COMPRA = ("omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase")
CHECKOUT = ("omni_initiated_checkout", "initiate_checkout", "offsite_conversion.fb_pixel_initiate_checkout")
VISTA = ("omni_landing_page_view", "landing_page_view")


def token() -> str | None:
    try:
        for ln in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
            k, _, v = ln.partition("=")
            if k.strip() == "META_ACCESS_TOKEN" and v.strip():
                return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def pedir(ruta: str, params: dict, tok: str) -> dict:
    url = f"{GRAPH}/{ruta}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - URL fija de la API de Meta
        return json.loads(r.read().decode("utf-8"))


def _accion(lista, tipos) -> float:
    """Primer tipo de la lista que aparezca (en orden de preferencia), para no sumar dos veces la misma compra."""
    por_tipo = {a.get("action_type"): a.get("value") for a in (lista or []) if isinstance(a, dict)}
    for t in tipos:
        if t in por_tipo:
            try:
                return float(por_tipo[t])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def fila_insights(f: dict) -> dict:
    gasto = float(f.get("spend") or 0)
    valor_c = _accion(f.get("action_values"), COMPRA)
    return {"gasto": round(gasto, 2), "impresiones": int(f.get("impressions") or 0), "cpm": round(float(f.get("cpm") or 0), 2),
            "clics": int(f.get("inline_link_clicks") or 0), "vistas": int(_accion(f.get("actions"), VISTA)),
            "checkouts": int(_accion(f.get("actions"), CHECKOUT)), "compras": int(_accion(f.get("actions"), COMPRA)),
            "valor": round(valor_c, 2), "roas_meta": round(valor_c / gasto, 2) if gasto else None}


def cuentas_del_libro() -> list[str]:
    """Cuentas publicitarias a leer: la de las reglas más cualquier `ficha.cuenta_publicitaria` del libro. Una cuenta nueva
    entra sola cuando el lanzamiento la anota en el libro; solo hay que asignársela al usuario del sistema."""
    cuentas = [CUENTA]
    try:
        for t in json.loads(LIBRO.read_text(encoding="utf-8")).get("tests") or []:
            c = str((t.get("ficha") or {}).get("cuenta_publicitaria") or "").replace("act_", "")
            if c.isdigit() and c not in cuentas:
                cuentas.append(c)
    except (OSError, ValueError):
        pass
    return cuentas


def campanas_del_libro() -> dict[str, str]:
    """{id de campaña: nombre de la oferta} de los tests del libro (solo esas se muestran)."""
    try:
        libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for t in libro.get("tests") or []:
        nombre = t.get("nombre") or "?"
        for c in ((t.get("ficha") or {}).get("campanas") or []):
            if isinstance(c, dict) and c.get("id"):
                out[str(c["id"])] = nombre
    return out


def leer(tok: str, ahora: dt.datetime) -> dict:
    mapa = campanas_del_libro()
    camps, ins, sin_permiso = [], [], []
    for i, cuenta in enumerate(cuentas_del_libro()):
        try:
            camps += pedir(f"act_{cuenta}/campaigns", {"fields": "id,name,effective_status,daily_budget", "limit": 200}, tok).get("data") or []
            ins += pedir(f"act_{cuenta}/insights", {"level": "campaign", "date_preset": "today", "limit": 200,
                                                   "fields": "campaign_id,spend,impressions,cpm,inline_link_clicks,actions,action_values"}, tok).get("data") or []
        except urllib.error.HTTPError:
            if i == 0:
                raise   # la cuenta principal manda el error (token vencido, sin permiso…)
            sin_permiso.append(cuenta)   # una cuenta nueva que todavía no se asignó al usuario del sistema
    por_camp = {str(f.get("campaign_id")): fila_insights(f) for f in ins}
    ofertas: dict[str, dict] = {}
    for c in camps:
        cid = str(c.get("id"))
        if cid not in mapa:
            continue
        o = ofertas.setdefault(mapa[cid], {"campanas": [], "hoy": None, "presupuesto": 0.0})
        hoy = por_camp.get(cid)
        activa = c.get("effective_status") == "ACTIVE"
        pres = float(c.get("daily_budget") or 0) / 100 if activa else 0.0
        o["campanas"].append({"id": cid, "estado": c.get("effective_status"), "presupuesto": round(pres, 2), "hoy": hoy})
        o["presupuesto"] = round(o["presupuesto"] + pres, 2)
        if hoy:
            acc = o["hoy"] or {k: 0 for k in ("gasto", "impresiones", "clics", "vistas", "checkouts", "compras", "valor")}
            for k in acc:
                acc[k] = round(acc[k] + hoy[k], 2)
            o["hoy"] = acc
    for o in ofertas.values():
        h = o["hoy"]
        if h:
            h["roas_meta"] = round(h["valor"] / h["gasto"], 2) if h["gasto"] else None
            h["cpm"] = round(1000 * h["gasto"] / h["impresiones"], 2) if h["impresiones"] else None
            h["cpa"] = round(h["gasto"] / h["compras"], 2) if h["compras"] else None
    total = {k: round(sum((o["hoy"] or {}).get(k, 0) for o in ofertas.values()), 2) for k in ("gasto", "compras", "valor", "checkouts")}
    total["roas_meta"] = round(total["valor"] / total["gasto"], 2) if total["gasto"] else None
    return {"ok": True, "leido": ahora.isoformat(timespec="seconds"), "dia": "hoy, zona horaria de la cuenta", "ofertas": ofertas, "total": total,
            "cuentas_sin_permiso": sin_permiso}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probar", action="store_true")
    a = ap.parse_args(argv)
    ahora = dt.datetime.now(dt.timezone.utc)
    tok = token()
    if not tok:
        out = {"ok": False, "error": "falta_token", "leido": ahora.isoformat(timespec="seconds")}
    else:
        try:
            out = leer(tok, ahora)
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode("utf-8")).get("error") or {}
            except (ValueError, OSError):
                err = {}
            codigo = err.get("code")
            out = {"ok": False, "error": "token_invalido" if codigo in (190, 102) else "permiso" if codigo in (10, 200, 294) else "limite" if codigo in (4, 17, 32, 613, 80004) else f"http_{e.code}",
                   "detalle": str(err.get("message") or "")[:200], "leido": ahora.isoformat(timespec="seconds")}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            out = {"ok": False, "error": "sin_conexion", "detalle": str(e)[:200], "leido": ahora.isoformat(timespec="seconds")}
    if a.probar:
        print("OK: el token lee la cuenta" if out.get("ok") else f"NO: {out.get('error')} {out.get('detalle', '')}")
        return 0 if out.get("ok") else 1
    if not out.get("ok"):   # conservar la última lectura buena para que el panel no quede en blanco
        try:
            previo = json.loads(SALIDA.read_text(encoding="utf-8"))
            if previo.get("ok") or previo.get("ultima_buena"):
                out["ultima_buena"] = previo if previo.get("ok") else previo.get("ultima_buena")
        except (OSError, ValueError):
            pass
    tmp = SALIDA.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(SALIDA)
    print("ok" if out.get("ok") else out.get("error"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
