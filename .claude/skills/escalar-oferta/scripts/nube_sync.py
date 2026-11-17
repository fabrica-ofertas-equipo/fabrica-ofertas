#!/usr/bin/env python3
"""Trae la capa en la nube (worker «fabrica-vivo») al libro y al panel cada 5 minutos, sin Claude y sin tokens.

Pedido del dueño (2026-11-14): «quiero algo que funcione robusto y lo más automático posible», opción 2. El worker lee Meta cada
5 minutos y recibe las ventas de Impultienda las 24 horas aunque la Mac esté apagada. Este programa, desde la Mac:
  1. pide GET https://vivo.tu-dominio.com/api/estado?desde=<ayer o el inicio más viejo de las ofertas activas> con la clave de
     lectura de ~/.config/fabrica-panel/vivo_lectura (la generó montar.sh; nunca se imprime);
  2. escribe ofertas/_funnels/meta_vivo.json con el formato que ya muestra el panel («hoy» por oferta, presupuesto, total);
  3. mezcla en el libro, con candado: el gasto de Meta por día (historial_meta.aplicar) y las ventas aprobadas que falten
     (ventas_impultienda.aplicar), marcando las reembolsadas;
  4. guarda ofertas/_funnels/nube.json con la hora de la lectura y el estado (para el panel y la vigilancia).
Lo corre el agente de inicio com.fabrica.nube-sync (StartInterval 300). Sin clave o sin red: lo dice en nube.json y no toca el libro.

Uso: python3 nube_sync.py [--url URL] [--seco]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fotos_campanas as FC  # noqa: E402
import historial_meta as HM  # noqa: E402
import libro as LB  # noqa: E402
import ventas_impultienda as VI  # noqa: E402

URL = "https://vivo.tu-dominio.com"
CLAVE = Path.home() / ".config" / "fabrica-panel" / "vivo_lectura"
FUNNELS = LB.LIBRO.parent
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def clave() -> str | None:
    try:
        t = CLAVE.read_text(encoding="utf-8").strip()
        return t or None
    except OSError:
        return None


def desde(libro: dict, hoy: dt.date) -> str:
    """Ayer, o el día de inicio más viejo de las ofertas que no están pausadas (para cargar todos sus días)."""
    d = hoy - dt.timedelta(days=1)
    for t in libro.get("tests") or []:
        if isinstance(t, dict) and str(t.get("estado", "")).lower() in ("activo", "activa", "programado", "programada"):
            try:
                i = dt.datetime.fromisoformat(str(t.get("inicio"))).astimezone(ZONA).date()
                d = min(d, i)
            except ValueError:
                pass
    return d.isoformat()


def meta_vivo(datos: dict, libro: dict, hoy: str, ahora: dt.datetime) -> dict:
    """Mismo formato que meta_vivo.py: «hoy» por oferta del libro, presupuesto de las campañas activas y total."""
    mapa = {}
    for t in libro.get("tests") or []:
        if isinstance(t, dict):
            # todas las campañas de la oferta (principal, pocket, variaciones: 16-nov; antes solo la principal y la escala no veía el resto)
            for cid in HM.campanas(t):
                mapa[str(cid)] = t.get("oferta") or t.get("nombre")
    est = datos.get("meta_estado") or {}
    campanas = {str(c.get("id")): c for c in est.get("campanas") or [] if isinstance(c, dict)}
    filas = {str(f.get("campana")): f for f in datos.get("meta_dia") or [] if f.get("fecha") == hoy}
    ofertas: dict = {}
    for cid, nombre in mapa.items():
        c = campanas.get(cid)
        f = filas.get(cid)
        if not c and not f:
            continue
        o = ofertas.setdefault(nombre, {"campanas": [], "hoy": None, "presupuesto": 0.0})
        activa = bool(c) and c.get("estado") == "ACTIVE"
        pres = float(c.get("presupuesto_usd") or 0) if activa else 0.0
        hoy_c = {"gasto": f.get("gasto") or 0, "impresiones": f.get("impresiones") or 0, "clics": f.get("clics") or 0, "vistas": f.get("visitas") or 0,
                 "checkouts": f.get("pagos_iniciados") or 0, "compras": f.get("compras") or 0, "valor": f.get("valor_compras") or 0} if f else None
        o["campanas"].append({"id": cid, "estado": c.get("estado") if c else None, "presupuesto": round(pres, 2), "hoy": hoy_c})
        o["presupuesto"] = round(o["presupuesto"] + pres, 2)
        if hoy_c:
            acc = o["hoy"] or {k: 0 for k in hoy_c}
            o["hoy"] = {k: round(acc[k] + hoy_c[k], 2) for k in acc}
    for o in ofertas.values():
        h = o["hoy"]
        if h:
            h["roas_meta"] = round(h["valor"] / h["gasto"], 2) if h["gasto"] else None
            h["cpm"] = round(1000 * h["gasto"] / h["impresiones"], 2) if h["impresiones"] else None
            h["cpa"] = round(h["gasto"] / h["compras"], 2) if h["compras"] else None
    total = {k: round(sum((o["hoy"] or {}).get(k, 0) for o in ofertas.values()), 2) for k in ("gasto", "compras", "valor", "checkouts")}
    total["roas_meta"] = round(total["valor"] / total["gasto"], 2) if total["gasto"] else None
    ok = bool(est.get("leido")) and not est.get("error")
    return {"ok": ok, "error": est.get("error"), "leido": est.get("leido") or ahora.isoformat(timespec="seconds"), "fuente": "nube (fabrica-vivo)",
            "dia": "hoy, zona horaria de la cuenta", "ofertas": ofertas, "total": total, "cuentas_sin_permiso": []}


def _hora_local(crudo, ahora: dt.datetime) -> str:
    try:
        m = dt.datetime.fromisoformat(str(crudo).replace("Z", "+00:00")) if crudo else ahora
    except ValueError:
        m = ahora
    return (m if m.tzinfo else m.replace(tzinfo=dt.timezone.utc)).astimezone(ZONA).strftime("%Y-%m-%dT%H:%M-03:00")


def aplicar(libro: dict, datos: dict, ahora: dt.datetime) -> list[str]:
    """Mezcla en el libro (puro sobre el dict): gasto por día, ventas aprobadas que falten y reembolsos."""
    try:
        crudo = str((datos.get("meta_estado") or {}).get("leido") or "").replace("Z", "+00:00")
        momento = dt.datetime.fromisoformat(crudo) if crudo else ahora
    except ValueError:
        momento = ahora
    leido = (momento if momento.tzinfo else momento.replace(tzinfo=dt.timezone.utc)).astimezone(ZONA).strftime("%Y-%m-%dT%H:%M-03:00")
    filas = [{"date_start": f.get("fecha"), "id": f.get("campana"), "amount_spent": f.get("gasto"), "impressions": f.get("impresiones"),
              "link_click": f.get("clics"), "omni_landing_page_view": f.get("visitas"), "omni_initiated_checkout": f.get("pagos_iniciados"),
              "omni_purchase": f.get("compras"), "omni_purchase_values": f.get("valor_compras")} for f in datos.get("meta_dia") or []]
    cambios = HM.aplicar(libro, [x for x in (HM.fila(r, leido) for r in filas) if x], leido, ahora.astimezone(ZONA).date()) if filas else []
    por_tienda: dict[str, list] = {}
    reembolsos = set()
    for v in datos.get("ventas") or []:
        if v.get("evento") == "order.approved":
            por_tienda.setdefault(str(v.get("tienda")), []).append({"orden": v.get("orden"), "fecha": v.get("creada") or v.get("recibido"),
                                                                     "total": v.get("total"), "moneda": v.get("moneda"), "post_compra": bool(v.get("post_compra"))})
        elif v.get("evento") in ("order.refunded", "order.chargeback"):
            reembolsos.add(str(v.get("orden")))
    cambios += VI.aplicar(libro, [{"tienda": k, "ventas": l} for k, l in por_tienda.items()], ahora)
    for t in libro.get("tests") or []:
        for v in (t.get("ventas") or []) if isinstance(t, dict) else []:
            if isinstance(v, dict) and str(v.get("orden")) in reembolsos and not v.get("reembolsada"):
                v["reembolsada"] = True
                v["neto"] = 0
                cambios.append(f"{t.get('nombre')}: orden {v.get('orden')} reembolsada")
    return cambios


# ───────────────────────── Meta por anuncio (dueño, 15-nov: «el top 20 de creativos con todos sus KPIs») ─────────────────────────

MINIATURAS = FUNNELS / "_miniaturas"
CAMPOS_DIA = {"gasto": "gasto_usd", "impresiones": "impresiones", "alcance": "alcance", "clics": "clics_enlace", "visitas": "visitas_landing_meta",
              "pagos_iniciados": "inicios_pago_meta", "compras": "compras_meta", "valor_compras": "valor_compras_meta_usd", "vistas_3s": "vistas_3s",
              "video_p25": "video_p25", "video_p50": "video_p50", "video_p75": "video_p75", "video_p100": "video_p100", "thruplay": "thruplay"}
SUMABLES = tuple(CAMPOS_DIA.values())
FIJOS = ("nombre", "conjunto_id", "conjunto", "campana", "estado", "creativo_id", "video_id", "miniatura_url", "creado")   # campana: vista tipo Administrador del panel (16-nov)


def desde_anuncios(libro: dict, hoy: dt.date) -> str:
    """El inicio más viejo de las ofertas del libro (hasta 30 días atrás): la ficha suma los anuncios desde el inicio del test."""
    d = hoy - dt.timedelta(days=1)
    for t in libro.get("tests") or []:
        try:
            d = min(d, dt.datetime.fromisoformat(str(t.get("inicio"))).astimezone(ZONA).date())
        except (ValueError, TypeError):
            pass
    return max(d, hoy - dt.timedelta(days=30)).isoformat()


def ruta_miniatura(ad_id: str) -> Path:
    return MINIATURAS / f"{ad_id}.jpg"


def aplicar_anuncios(libro: dict, datos: dict, leido: str) -> list[str]:
    """Anuncios de cada test (puro sobre el dict): ``anuncios.por_dia`` con los días que leyó la nube (reemplaza esos días, deja los demás)
    y ``anuncios.lista`` con los datos fijos de cada anuncio y la suma de sus días. Sin lectura por anuncio en la nube: no toca nada."""
    filas = [f for f in datos.get("anuncio_dia") or [] if isinstance(f, dict) and f.get("id")]
    leidos = set(datos.get("anuncio_dias") or [f.get("fecha") for f in filas])
    fijos_nube = {str(a.get("id")): a for a in datos.get("anuncios") or [] if isinstance(a, dict) and a.get("id")}
    if not leidos and not fijos_nube:
        return []
    cambios = []
    for t in libro.get("tests") or []:
        if not isinstance(t, dict):
            continue
        cids = HM.campanas(t)
        mias = [f for f in filas if str(f.get("campana")) in cids]
        fijos = {k: v for k, v in fijos_nube.items() if str(v.get("campana")) in cids}
        if not mias and not fijos:
            continue
        a = t.get("anuncios") if isinstance(t.get("anuncios"), dict) else {}
        viejos = [r for r in a.get("por_dia") or [] if isinstance(r, dict) and str(r.get("fecha"))[:10] not in leidos]
        nuevos = [{"fecha": f["fecha"], "id": str(f["id"]), **{v: f.get(k) for k, v in CAMPOS_DIA.items()}} for f in mias]
        por_dia = sorted(viejos + nuevos, key=lambda r: (str(r.get("fecha")), str(r.get("id"))))
        suma: dict[str, dict] = {}
        for r in por_dia:
            acc = suma.setdefault(str(r.get("id")), {})
            for k in SUMABLES:
                if r.get(k) is not None:
                    acc[k] = round(acc.get(k, 0) + float(r[k]), 2)
        previos = {str(x.get("id")): x for x in a.get("lista") or [] if isinstance(x, dict)}
        de_filas = {str(f["id"]): {"nombre": f.get("nombre"), "conjunto_id": f.get("conjunto_id"), "conjunto": f.get("conjunto"), "campana": f.get("campana")} for f in mias}
        lista = []
        for i in sorted(set(previos) | set(fijos) | set(suma)):
            fx = fijos.get(i) or {}
            x = {"id": i}
            for k in FIJOS:
                src = {"miniatura_url": fx.get("miniatura")}.get(k, fx.get(k))
                x[k] = src if src not in (None, "") else (de_filas.get(i, {}).get(k) or previos.get(i, {}).get(k))
            tot = suma.get(i)
            for k in SUMABLES:
                x[k] = (tot or {}).get(k, 0) if tot is not None or i not in previos else previos[i].get(k)
            x["ctr_pct"] = round(100 * x["clics_enlace"] / x["impresiones"], 2) if x.get("impresiones") else None
            if ruta_miniatura(i).exists():
                x["miniatura"] = f"ofertas/_funnels/_miniaturas/{i}.jpg"
            lista.append(x)
        antes = json.dumps(a.get("lista"), sort_keys=True)
        a.update({"lista": lista, "por_dia": por_dia, "leido": leido, "por_dia_leido": leido, "fuente": "nube fabrica-vivo (Meta level=ad, cada 5 min)"})
        t["anuncios"] = a
        if json.dumps(lista, sort_keys=True) != antes:
            cambios.append(f"{t.get('nombre')}: {len(lista)} anuncios al día")
    return cambios


def bajar_miniaturas(datos: dict, libro: dict, tope: int = 250) -> int:
    """Baja la miniatura de cada anuncio del libro que todavía no la tiene (el panel no carga imágenes de afuera)."""
    cids = set().union(*[HM.campanas(t) for t in libro.get("tests") or [] if isinstance(t, dict)] or [set()])
    MINIATURAS.mkdir(parents=True, exist_ok=True)
    n = 0
    for a in datos.get("anuncios") or []:
        url, i = a.get("miniatura"), str(a.get("id") or "")
        if n >= tope or not url or not i.isdigit() or str(a.get("campana")) not in cids or ruta_miniatura(i).exists():
            continue
        if not str(url).startswith("https://"):
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fabrica-panel"}), timeout=20) as r:  # noqa: S310 - CDN de Meta
                cuerpo = r.read(1_000_001)
            if 0 < len(cuerpo) <= 1_000_000:
                ruta_miniatura(i).write_bytes(cuerpo)
                n += 1
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default=URL)
    ap.add_argument("--seco", action="store_true")
    a = ap.parse_args(argv)
    ahora = dt.datetime.now(dt.timezone.utc)
    estado = {"leido": ahora.isoformat(timespec="seconds")}
    tok = clave()
    if not tok:
        estado.update({"ok": False, "error": "sin_configurar"})
        (FUNNELS / "nube.json").write_text(json.dumps(estado), encoding="utf-8")
        print("sin_configurar")
        return 0
    libro = json.loads(LB.LIBRO.read_text(encoding="utf-8"))
    hoy = ahora.astimezone(ZONA).date()
    req = urllib.request.Request(f"{a.url}/api/estado?desde={desde(libro, hoy)}&desde_anuncios={desde_anuncios(libro, hoy)}", headers={"Authorization": f"Bearer {tok}", "User-Agent": "fabrica-panel"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - URL fija propia
            datos = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        estado.update({"ok": False, "error": "sin_conexion", "detalle": str(e)[:200]})
        (FUNNELS / "nube.json").write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
        print(f"sin_conexion: {e}")
        return 1
    mv = meta_vivo(datos, libro, hoy.isoformat(), ahora)
    if a.seco:
        print(json.dumps(mv, ensure_ascii=False)[:600])
        copia = json.loads(json.dumps(libro))
        print("\n".join(aplicar(copia, datos, ahora) + aplicar_anuncios(copia, datos, str(datos.get("anuncios_leido") or ""))) or "sin cambios para el libro")
        return 0
    (FUNNELS / "meta_vivo.json").write_text(json.dumps(mv, ensure_ascii=False, indent=1), encoding="utf-8")
    cambios: list[str] = []
    if mv.get("ok"):
        try:   # fotos por campaña y registro de cambios de presupuesto/estado (dueño, 16-nov: timeline y escala por campaña)
            for ev in FC.registrar_desde_nube(datos, libro, ahora):
                cambios.append(f"{ev.get('oferta')}: {ev['tipo']} {ev['de']} → {ev['a']} ({ev['autor']})")
        except (OSError, ValueError, KeyError, TypeError) as e:
            cambios.append(f"fotos de campañas: error {e}")
    try:
        bajadas = bajar_miniaturas(datos, libro)
    except OSError:
        bajadas = 0
    leido_ads = _hora_local(datos.get("anuncios_leido"), ahora)
    sin_oferta: list[dict] = []

    def _todo(lib: dict) -> None:
        # primero las campañas nuevas de cada oferta (así sus días y anuncios entran en esta misma vuelta), después lo de siempre
        nuevas, sin = FC.asignar_campanas(lib, (datos.get("meta_estado") or {}).get("campanas") or [], ahora) if mv.get("ok") else ([], [])
        sin_oferta.extend(sin)
        cambios.extend(nuevas + aplicar(lib, datos, ahora) + aplicar_anuncios(lib, datos, leido_ads))
    LB.modificar(_todo)
    if mv.get("ok"):
        FC.SIN_OFERTA.write_text(json.dumps({"leido": ahora.isoformat(timespec="seconds"), "campanas": sin_oferta}, ensure_ascii=False, indent=1), encoding="utf-8")
    if bajadas:
        cambios.append(f"{bajadas} miniaturas de anuncios nuevas")
    # Corte de respaldo en la nube (dueño, 17-nov): subir el plan y avisar lo que la nube haya pausado mientras la vigilancia no corría.
    try:
        import plan_corte as PC  # noqa: PLC0415
        cambios.extend(PC.avisar(datos.get("cortes_nube") or [], LB.modificar))
        PC.subir(PC.armar(json.loads(LB.LIBRO.read_text(encoding="utf-8")), ahora, PC.latido_vigilancia()), a.url, tok)
        estado["respaldo"] = datos.get("respaldo")
    except Exception as e:  # noqa: BLE001 - el respaldo no puede tumbar la sincronización del panel
        cambios.append(f"plan de corte: error {str(e)[:120]}")
    estado.update({"ok": mv["ok"], "meta_leido": mv["leido"], "meta_error": mv.get("error"), "ultimo_aviso_venta": datos.get("ultimo_aviso"),
                   "ventas_en_nube": len(datos.get("ventas") or []), "anuncios_leido": datos.get("anuncios_leido"),
                   "anuncios_error": datos.get("anuncios_error"), "cambios": cambios[:20], "respaldo": datos.get("respaldo")})
    (FUNNELS / "nube.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(cambios) or "sin cambios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
