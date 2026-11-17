#!/usr/bin/env python3
"""Verificación del funnel entero (anuncio → landing → checkout) antes de activar y a los 10-15 minutos de activar.

Pedido del dueño (2026-11-14): «deberíamos verificar esto una vez que se lanza una oferta nueva y luego de que los
anuncios se activan, a los 10 minutos o 15 minutos que se activan los anuncios, volver a verificar todo el funnel como
para comprobarlo y ver que el checkout funciona, que la landing funciona bien, que todo básicamente el sistema en sí, o
sea, desde el anuncio al funnel y al checkout». La compra no se prueba (sería un cobro real).

Motivo: ese día Oferta H y Oferta I (duplicadas de Oferta F) salieron con la imagen del producto rota en
los 6 checkouts, y salud.py no lo vio porque solo mira que las páginas respondan 200.

Qué mira:
  A. Funnel (probar_funnel.py de modelar-y-lanzar-oferta, iPhone simulado, sin dejar rastro: píxel, visitas y API de
     conversiones de Impultienda bloqueados): la landing de la oferta y sus
     vistas (?v=articulo, ?v=ficha), el quiz hasta el resultado, imágenes rotas, `{{…}}` a la vista, enlaces al checkout,
     y cada checkout: correo, botón de pagar con monto, imagen del producto. Cualquier falla → FALLA.
  B. Anuncios (lectura de Meta que arma la vigilancia, opcional): anuncios entregando, rechazados, impresiones y clics
     desde la activación, y la URL de destino de cada anuncio (tiene que ser una tienda de la oferta y responder).
  C. Llegada (lectura de Impultienda, opcional): con 10 clics o más en Meta y 0 visitas en la landing, los clics no
     están llegando (URL del anuncio, dominio o tienda caída) → FALLA.

Cuándo (pendientes): cada vez que una campaña o un conjunto de la oferta se activa: el `inicio` del test y el `inicio`
de cada entrada de `renovaciones`. Queda pendiente desde 10 min después de ese momento hasta 6 h después, mientras no
haya en ofertas/_funnels/verificaciones.jsonl un registro {"tipo": "funnel", "oferta", "momento"} de ese momento.
hay_trabajo.py lo pide como paso 8 en TODAS las vueltas (rápidas también), así la tarea de 15 min lo toma a tiempo.

Decisiones por oferta:
  OK       — todo bien: se registra y no se vuelve a probar ese momento.
  FALLA    — algo roto: se registra, aviso urgente al dueño con la lista y se arregla en la vuelta (no se pausa sola: una
             imagen rota no justifica cortar el tráfico; una landing o un checkout caídos sí los pausa salud.py).
  ESPERAR  — Meta todavía no entregó (0 impresiones) o faltan datos: no se registra, se repite en la vuelta siguiente.

Uso:
  python3 verificar_funnel.py pendientes [--ahora ISO] [--json]
  python3 verificar_funnel.py correr --oferta "<nombre>" [--lectura <json>] [--antes] [--registrar] [--salida <carpeta>]
     --antes: prueba previa a activar (control previo): solo A; el resultado va a la lectura de control_previo.py como
              "funnel": {"ok": …, "fallas": […]}.
lectura.json (opcional, la arma la vigilancia; todo opcional):
  {"momento": "<ISO del inicio que se verifica>",
   "anuncios": {"activos": 9, "en_revision": 1, "rechazados": [{"id": "…", "motivo": "…"}]},
   "impresiones": 340, "clics": 21,
   "urls_anuncios": ["https://<tienda>.impultienda.ar/?v=articulo&utm_…", …],
   "visitas_landing": 18,
   "cobro": {"<subdominio>": true}}
  `cobro` sale de impultienda_estado_pasarela de cada tienda del funnel (`puede_cobrar` y Impul Pay o Stripe operativa):
  la prueba en el navegador corre desde Argentina y ve MercadoPago en pesos, no lo que ve el comprador del mercado.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# Capa de tienda (tienda/): la plataforma donde se vende se elige en tienda/config.json; Impultienda por defecto.
_RAIZ_T = next(p for p in Path(__file__).resolve().parents if (p / "tienda" / "__init__.py").is_file())
if str(_RAIZ_T) not in sys.path:
    sys.path.insert(0, str(_RAIZ_T))
import tienda as _tienda  # noqa: E402

TIENDA = _tienda.activa()

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
REGISTRO = RAIZ / "ofertas" / "_funnels" / "verificaciones.jsonl"
PROBAR = RAIZ / ".claude" / "skills" / "modelar-y-lanzar-oferta" / "scripts"
DESDE = dt.timedelta(minutes=10)
HASTA = dt.timedelta(hours=6)
CLICS_SIN_VISITAS = 10
UA = "Mozilla/5.0 (verificar funnel; uso interno)"


def _fecha(x):
    if not isinstance(x, str) or not x:
        return None
    try:
        d = dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _activo(t: dict) -> bool:
    estado = str(t.get("estado") or "").lower()
    return estado in ("activo", "programado") and not t.get("apagado")


def momentos(t: dict) -> list[dt.datetime]:
    """Momentos en que se activaron anuncios de la oferta: inicio del test y de cada renovación."""
    out = [_fecha(t.get("inicio"))]
    out += [_fecha(r.get("inicio")) for r in t.get("renovaciones") or [] if isinstance(r, dict)]
    return sorted({m for m in out if m})


def registrados() -> list[dict]:
    try:
        lineas = REGISTRO.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lineas:
        try:
            v = json.loads(ln)
        except ValueError:
            continue
        if isinstance(v, dict) and v.get("tipo") == "funnel":
            out.append(v)
    return out


def pendientes(libro: dict, ahora: dt.datetime) -> list[dict]:
    hechos = {(str(v.get("oferta")), str(v.get("momento"))) for v in registrados() if v.get("resultado") in ("OK", "FALLA")}
    out = []
    for t in libro.get("tests") or []:
        if not isinstance(t, dict) or not _activo(t):
            continue
        for m in momentos(t):
            if DESDE <= ahora - m <= HASTA and (str(t.get("nombre")), m.isoformat()) not in hechos:
                out.append({"oferta": t.get("nombre"), "momento": m.isoformat(), "minutos": int((ahora - m).total_seconds() // 60)})
    return out


def tiendas_de(t: dict) -> tuple[list[str], str | None]:
    """(subdominios de la oferta, subdominio de la landing)."""
    ts = [x for x in ((t.get("ficha") or {}).get("tiendas") or []) if isinstance(x, dict)]
    slugs = [str(x.get("slug") or TIENDA.tienda_de_url(str(x.get("url") or "")) or "") for x in ts]
    slugs = [s for s in slugs if s] or [str(s) for s in (t.get("tienda") or [])]
    landing = next((s for s, x in zip(slugs, ts) if "landing" in str(x.get("rol") or "")), None) \
        or next((s for s, x in zip(slugs, ts) if "principal" in str(x.get("rol") or "")), None) \
        or (slugs[0] if slugs else None)
    return slugs, landing


def responde(url: str) -> int | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:  # noqa: S310
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def evaluar(t: dict, lectura: dict, funnel: dict | None, antes: bool) -> dict:
    nombre = t.get("nombre")
    slugs, landing = tiendas_de(t)
    fallas: list[str] = list((funnel or {}).get("fallas") or [])
    avisos: list[str] = []
    esperar: list[str] = []
    if funnel is None:
        fallas.append("no se pudo correr la prueba del funnel")
    elif TIENDA.bloqueos_medicion and (funnel.get("bloqueadas") or {}).get("tienda", (funnel.get("bloqueadas") or {}).get("impultienda")) == 0:
        avisos.append(f"la prueba no frenó ninguna llamada de medición de {TIENDA.nombre}: puede haber sumado visitas o eventos falsos (revisar bloqueos_medicion en tienda/adaptadores/{TIENDA.nombre}.py)")
    if not antes:
        an = lectura.get("anuncios") or {}
        if an:
            activos, revision = int(an.get("activos") or 0), int(an.get("en_revision") or 0)
            rech = an.get("rechazados") or []
            if activos == 0 and revision == 0:
                fallas.append("ningún anuncio activo ni en revisión")
            elif activos == 0:
                esperar.append(f"{revision} anuncio(s) todavía en revisión")
            if rech:
                avisos.append(f"{len(rech)} anuncio(s) rechazado(s)")
        imp, clics = lectura.get("impresiones"), lectura.get("clics")
        if imp is not None and int(imp) == 0:
            esperar.append("Meta todavía no entregó (0 impresiones)")
        for u in lectura.get("urls_anuncios") or []:
            host = TIENDA.tienda_de_url(u)
            if host not in slugs:
                fallas.append(f"un anuncio lleva a {urlparse(u).hostname}, que no es una tienda de la oferta")
                continue
            st = responde(u)
            if st is None or st >= 400:
                fallas.append(f"la URL de un anuncio no responde ({st}): {u[:90]}")
        for slug, puede in (lectura.get("cobro") or {}).items():
            if puede is False:
                fallas.append(f"la tienda {slug} no puede cobrar (pasarela)")
        vis = lectura.get("visitas_landing")
        if clics is not None and vis is not None and int(clics) >= CLICS_SIN_VISITAS and int(vis) == 0:
            fallas.append(f"{clics} clics en Meta y 0 visitas en la landing: los clics no llegan a la tienda")
    if fallas:
        decision = "FALLA"
    elif esperar:
        decision = "ESPERAR"
    else:
        decision = "OK"
    resumen = {"FALLA": f"{nombre}: el funnel tiene fallas → " + " · ".join(fallas),
               "ESPERAR": f"{nombre}: todavía no se puede verificar ({'; '.join(esperar)}); se repite en la próxima vuelta",
               "OK": f"{nombre}: funnel verificado (landing {landing}, {len((funnel or {}).get('checkouts') or [])} checkout(s))"
                     + (" · " + " · ".join(avisos) if avisos else "")}[decision]
    return {"oferta": nombre, "decision": decision, "fallas": fallas, "avisos": avisos, "esperar": esperar,
            "landing": landing, "mensaje": resumen[:300], "urgente": decision == "FALLA"}


def correr(nombre: str, lectura: dict, antes: bool, salida: str) -> dict:
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    t = next((x for x in libro.get("tests") or [] if isinstance(x, dict) and nombre in (x.get("nombre"), x.get("oferta"))), None)
    if t is None:
        return {"oferta": nombre, "decision": "FALLA", "fallas": ["no está en el libro de tests"], "urgente": True,
                "mensaje": f"{nombre}: no está en el libro de tests"}
    _, landing = tiendas_de(t)
    funnel = None
    if landing:
        sys.path.insert(0, str(PROBAR))
        try:
            import probar_funnel  # noqa: PLC0415
            funnel = probar_funnel.probar_varias([landing], str(t.get("mercado") or "US"), salida)[0]
        except Exception as e:  # noqa: BLE001
            funnel = None
            lectura = {**lectura, "_error_prueba": str(e)[:200]}
    r = evaluar(t, lectura, funnel, antes)
    r["momento"] = lectura.get("momento")
    r["funnel"] = {k: (funnel or {}).get(k) for k in ("tienda", "carga_s", "pintado_principal_ms", "enlaces_checkout", "quiz_toques")}
    r["checkouts"] = [{k: c.get(k) for k in ("url", "boton_pagar", "correo", "imagenes_producto", "carga_s", "fallas")}
                      for c in (funnel or {}).get("checkouts") or []]
    if lectura.get("_error_prueba"):
        r["error_prueba"] = lectura["_error_prueba"]
    return r


def registrar(r: dict) -> None:
    fila = {"cuando": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "tipo": "funnel",
            "oferta": r["oferta"], "momento": r.get("momento"), "resultado": r["decision"], "fallas": r.get("fallas") or [],
            "avisos": r.get("avisos") or []}
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("pendientes")
    p1.add_argument("--ahora")
    p1.add_argument("--json", action="store_true")
    p2 = sub.add_parser("correr")
    p2.add_argument("--oferta", required=True)
    p2.add_argument("--lectura")
    p2.add_argument("--antes", action="store_true")
    p2.add_argument("--registrar", action="store_true")
    p2.add_argument("--salida", default="/tmp/verificar-funnel")
    a = ap.parse_args(argv)
    if a.cmd == "pendientes":
        ahora = _fecha(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
        p = pendientes(json.loads(LIBRO.read_text(encoding="utf-8")), ahora)
        if a.json:
            print(json.dumps(p, ensure_ascii=False, indent=1))
        else:
            print("NADA" if not p else "PENDIENTES: " + " · ".join(f"{x['oferta']} (activó hace {x['minutos']} min, {x['momento']})" for x in p))
        return 0
    lectura = json.loads(Path(a.lectura).read_text(encoding="utf-8")) if a.lectura else {}
    r = correr(a.oferta, lectura, a.antes, a.salida)
    if a.registrar and not a.antes and r["decision"] in ("OK", "FALLA") and r.get("momento"):
        registrar(r)
        r["registrado"] = True
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
