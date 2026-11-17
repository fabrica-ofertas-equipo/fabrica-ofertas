#!/usr/bin/env python3
"""¿Hay algo que vigilar en esta vuelta? Filtro previo de la tarea «vigilancia-ofertas» (sin red, solo el libro y los archivos del día).

Pedido del dueño (2026-11-13): «¿no sería mejor que sepa cuándo hay un test corriendo? Ahora no tenemos ninguna en test y la vigilancia
sigue gastando tokens». Cada vuelta cargaba la skill entera y leía Meta aunque no hubiera nada que cuidar. Este script mira el libro y
dice qué pasos de la vuelta tocan; si no toca ninguno, la vuelta termina en una línea.

Pasos (los de la tarea programada):
  0 verificar — un pedido «capi» de ofertas/_funnels/verificaciones.jsonl (botón «Listo, ya lo cargué» del panel) más nuevo que el
               `capi.revisado` de alguna tienda de esa oferta.
  1 corte   — un test en fase de test con campaña andando (día 1 del mercado o todavía sin ventas), o un programado que sale en ≤ 1 h.
  2 salud   — cualquier oferta con campaña andando (test o post-lanzamiento).
  3 escala  — una oferta en post-lanzamiento con campaña activa (surfeo cada 3 h, subas de 24 h y bajada simétrica: necesita la vuelta de cada hora).
  4 mínimos — una renovación (o un test) con «minimo_pendiente» cuyo inicio ya pasó.
  5 revisión diaria — desde las 09:00 de Argentina, si todavía no está ofertas/_funnels/REVISION-<fecha>.md de hoy.
  6 backend  — (R3b, dueño 14-nov) un backend armado por adelantado (`backend.estado = "listo"`) cuyo `activar_desde` (fin del
               test) ya pasó: hay que prender su embudo post-compra en cada tienda.
  7 cierre   — (R15, dueño 14-nov) una oferta apagada hace 72 h o más que hay que cerrar y cuyas tiendas hay que archivar en
               Impultienda (`cierre_oferta.py` da CERRAR).
  8 funnel   — (dueño 14-nov) una campaña o un conjunto de renovación se activó hace 10 min a 6 h y su funnel todavía no se
               verificó (`verificar_funnel.py pendientes`): anuncio → landing → checkout. Va en TODAS las vueltas, también
               en las rápidas, para que la tarea de 15 min lo tome a los 10-25 minutos de activar.

Una oferta pausada, cerrada o apagada no da trabajo (reactivarla es del dueño). Un programado que sale en más de 1 h tampoco: su
campaña no gasta hasta las 00:00 del mercado.

Vuelta rápida (dueño, 14-nov: «cuando hay ofertas corriendo bajarlo a 15 minutos pero cuando ya gastó 1 ticket o un poco menos, tampoco
para hacer vueltas al pedo»). La tarea corre cada 15 minutos. Si pasaron ≥ 52 min desde la última vuelta completa (marca en
ofertas/_funnels/vigilancia_vuelta.json), la vuelta es completa (todo lo de arriba) y deja la marca. Si no, es rápida: solo el corte
(paso 1) y solo para los tests en fase de test cuyo último gasto registrado en vigilancia.jsonl está a 0,6 ticket del corte o menos
(sin ventas: desde 0,9 ticket gastado). Los números salen de reglas.json → test.vuelta_rapida. Oferta E (14-nov) pasó el corte
entre dos vueltas de una hora: US$ 25,64 a las 10:06 y 34,58 a las 11:00, con corte de 28,50.

Uso: python3 hay_trabajo.py [--libro RUTA] [--ahora ISO] [--modo auto|completa|rapida] [--sin-marcar] [--json]
Salida: «NADA: …», «TRABAJO: pasos 1,2,3 · …» o «RÁPIDA: paso 1 · corte (…) · paso 8 · verificar funnel (…)» (código 0). Con --json, el detalle.
Con --ahora (pruebas) no deja la marca de vuelta completa.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402
import cierre_oferta  # noqa: E402
import verificar_funnel  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
ZONA_DUENO = ZoneInfo("America/Argentina/Buenos_Aires")
HORA_REVISION = 9
ANTICIPO = dt.timedelta(hours=1)   # un programado que sale dentro de 1 h ya entra en la vigilancia
RAPIDA = valor("test.vuelta_rapida", {"minutos": 15, "tickets_antes_del_corte": 0.6, "minutos_entre_completas": 52})
ENTRE_COMPLETAS = dt.timedelta(minutes=float(RAPIDA.get("minutos_entre_completas", 52)))
MARGEN_TICKETS = float(RAPIDA.get("tickets_antes_del_corte", 0.6))
DECISIONES_EN_TEST = ("SIGUE", "CERCA", "APAGAR", "SEGUNDA_OPORTUNIDAD")


def _fecha(x):
    if not isinstance(x, str) or not x:
        return None
    try:
        d = dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _campanas_andando(t: dict) -> bool:
    """Alguna campaña de la ficha sin pausar (si la ficha no las tiene, se toma el estado del test)."""
    cs = [c for c in ((t.get("ficha") or {}).get("campanas") or []) if isinstance(c, dict)]
    if not cs:
        return True
    return any(str(c.get("estado", "")).upper() not in ("PAUSED", "ARCHIVED", "DELETED") for c in cs)


def verificaciones_pendientes(libro: dict, carpeta_funnels: Path) -> list[str]:
    """Ofertas con un pedido de verificación de la API de conversiones sin revisar después del pedido (guía 04, paso 0)."""
    try:
        lineas = (carpeta_funnels / "verificaciones.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    tests = [t for t in libro.get("tests") or [] if isinstance(t, dict)]
    out = []
    for ln in lineas:
        try:
            v = json.loads(ln)
        except ValueError:
            continue
        cuando = _fecha(v.get("cuando")) if isinstance(v, dict) else None
        if not cuando or v.get("tipo") != "capi" or v.get("oferta") in out:
            continue
        t = next((x for x in tests if v.get("oferta") in (x.get("oferta"), x.get("nombre"))), None)
        tiendas = [x for x in ((t or {}).get("ficha") or {}).get("tiendas") or [] if isinstance(x, dict)]
        revisados = [_fecha((x.get("capi") or {}).get("revisado")) if isinstance(x.get("capi"), dict) else None for x in tiendas]
        if not tiendas or any(r is None or r < cuando for r in revisados):
            out.append(str(v.get("oferta")))
    return out


def _activo(t: dict) -> bool:
    estado = str(t.get("estado") or "").lower()
    return estado not in ("pausado", "pausada", "cerrado", "cerrada", "apagado", "apagada") and not t.get("apagado") and _campanas_andando(t)


def cerca_del_corte(libro: dict, carpeta_funnels: Path) -> list[dict]:
    """Tests en fase de test cuyo último gasto registrado está a MARGEN_TICKETS ticket del corte o menos (o ya en APAGAR)."""
    try:
        lineas = (carpeta_funnels / "vigilancia.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    activos = {str(t.get("nombre")) for t in libro.get("tests") or [] if isinstance(t, dict) and _activo(t)}
    ultimo: dict[str, dict] = {}
    for ln in reversed(lineas):
        try:
            vuelta = json.loads(ln)
        except ValueError:
            continue
        for r in vuelta.get("tests") or []:
            n = str(r.get("test"))
            if n in activos and n not in ultimo and r.get("decision") != "SIN_LECTURA":
                ultimo[n] = {**r, "leido": vuelta.get("leido")}
        if len(ultimo) == len(activos):
            break
    out = []
    for n, r in ultimo.items():
        if r.get("fase") != "test" or r.get("decision") not in DECISIONES_EN_TEST:
            continue
        gasto, corte, ticket = r.get("gasto_usd"), r.get("corte_usd"), r.get("ticket_corte_usd")
        if gasto is None or not corte or not ticket:
            continue
        if r.get("decision") == "APAGAR" or float(gasto) >= float(corte) - MARGEN_TICKETS * float(ticket):
            out.append({"test": n, "gasto_usd": gasto, "corte_usd": corte, "leido": r.get("leido")})
    return out


def modo_de_vuelta(carpeta_funnels: Path, ahora: dt.datetime) -> str:
    try:
        ultima = _fecha(json.loads((carpeta_funnels / "vigilancia_vuelta.json").read_text(encoding="utf-8")).get("completa"))
    except (OSError, ValueError, AttributeError):
        ultima = None
    return "completa" if ultima is None or ahora - ultima >= ENTRE_COMPLETAS else "rapida"


def funnel_pendiente(libro: dict, ahora: dt.datetime) -> list[str]:
    try:
        return sorted({str(p["oferta"]) for p in verificar_funnel.pendientes(libro, ahora)})
    except Exception:  # noqa: BLE001 - el filtro nunca se cae por esto
        return []


def evaluar_rapida(libro: dict, ahora: dt.datetime, carpeta_funnels: Path) -> dict:
    cerca = cerca_del_corte(libro, carpeta_funnels)
    funnel = funnel_pendiente(libro, ahora)
    detalle = {}
    if cerca:
        detalle["1"] = [c["test"] for c in cerca]
    if funnel:
        detalle["8"] = funnel
    pasos = [int(k) for k in detalle]
    return {"ahora": ahora.isoformat(timespec="minutes"), "modo": "rapida", "pasos": pasos,
            "detalle": detalle, "cerca": cerca, "funnel": funnel, "nada": not pasos, "proxima_salida": None}


def evaluar(libro: dict, ahora: dt.datetime, carpeta_funnels: Path) -> dict:
    pasos: dict[int, list[str]] = {0: verificaciones_pendientes(libro, carpeta_funnels), 1: [], 2: [], 3: [], 4: [], 5: [], 6: [],
                                   7: [r["test"] for r in cierre_oferta.evaluar(libro, ahora, carpeta_funnels) if r["decision"] == "CERRAR"],
                                   8: funnel_pendiente(libro, ahora)}
    esperando: list[tuple[dt.datetime, str]] = []
    for t in libro.get("tests") or []:
        if not isinstance(t, dict):
            continue
        nombre = str(t.get("nombre") or "?")
        estado = str(t.get("estado") or "").lower()
        b = t.get("backend") if isinstance(t.get("backend"), dict) else {}
        desde = _fecha(b.get("activar_desde"))
        if str(b.get("estado") or "") == "listo" and desde and desde <= ahora:
            pasos[6].append(nombre)
        if estado in ("pausado", "pausada", "cerrado", "cerrada", "apagado", "apagada") or t.get("apagado"):
            continue
        inicio = _fecha(t.get("inicio"))
        if inicio and inicio - ahora > ANTICIPO:
            esperando.append((inicio, nombre))
            continue
        if not _campanas_andando(t):
            continue
        fase = t.get("fase")
        con_ventas = bool(t.get("ventas"))
        fin_dia1 = None
        if inicio:
            fin_dia1 = dt.datetime.combine(inicio.date() + dt.timedelta(days=1), dt.time(0), tzinfo=inicio.tzinfo)
        en_test = fase == "test" or fase is None and (not con_ventas or (fin_dia1 and ahora < fin_dia1))
        if fase == "post-lanzamiento":
            en_test = False
        if en_test:
            pasos[1].append(nombre)
        else:
            pasos[3].append(nombre)
        pasos[2].append(nombre)
        # El campo vive en cada entrada de «renovaciones» (05-renovacion-diaria.md paso 6), no en la fila del test:
        # hasta el 14-nov solo se miraba la fila y el mínimo de la R4 de Oferta B nunca se puso.
        pend = [r for r in (t.get("renovaciones") or []) if isinstance(r, dict) and r.get("minimo_pendiente")
                and (_fecha(r.get("inicio")) is None or _fecha(r.get("inicio")) <= ahora)]
        if pend or (t.get("minimo_pendiente") and (inicio is None or inicio <= ahora)):
            pasos[4].append(nombre)
    hoy = ahora.astimezone(ZONA_DUENO)
    if hoy.hour >= HORA_REVISION and not (carpeta_funnels / f"REVISION-{hoy.date().isoformat()}.md").exists():
        pasos[5].append("revisión del día")
    activos = [k for k, v in pasos.items() if v]
    proxima = min(esperando) if esperando else None
    return {
        "ahora": ahora.isoformat(timespec="minutes"),
        "pasos": activos,
        "detalle": {str(k): v for k, v in pasos.items() if v},
        "proxima_salida": {"oferta": proxima[1], "inicio": proxima[0].isoformat()} if proxima else None,
        "nada": not activos,
    }


def linea(r: dict) -> str:
    if r.get("modo") == "rapida":
        if r["nada"]:
            return "NADA: vuelta rápida de 15 min · ningún test a 0,6 ticket del corte o menos y ningún funnel por verificar"
        partes = []
        if r["cerca"]:
            partes.append("paso 1 · corte (" + "; ".join(f"{c['test']}: US$ {float(c['gasto_usd']):.2f} de {float(c['corte_usd']):.2f}" for c in r["cerca"]) + ")")
        if r.get("funnel"):
            partes.append("paso 8 · verificar funnel tras activar (" + ", ".join(r["funnel"]) + ")")
        return "RÁPIDA: " + " · ".join(partes)
    prox = r["proxima_salida"]
    cola = f" · próxima salida: {prox['oferta']} el {prox['inicio'][:16].replace('T', ' ')} (hora del mercado)" if prox else ""
    if r["nada"]:
        return "NADA: ninguna oferta con campaña andando, sin verificaciones ni mínimos pendientes y sin revisión diaria por hacer" + cola
    nombres = {"0": "verificar API de conversiones", "1": "corte", "2": "salud", "3": "escala", "4": "mínimos", "5": "revisión diaria", "6": "activar backend", "7": "cerrar y archivar", "8": "verificar funnel tras activar"}
    partes = [f"{nombres[k]} ({', '.join(v)})" for k, v in r["detalle"].items()]
    return f"TRABAJO: pasos {','.join(str(p) for p in r['pasos'])} · " + " · ".join(partes) + cola


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--libro", default=str(LIBRO))
    ap.add_argument("--ahora", help="ISO con zona, para pruebas")
    ap.add_argument("--modo", choices=("auto", "completa", "rapida"), default="auto")
    ap.add_argument("--sin-marcar", action="store_true", help="no dejar la marca de vuelta completa")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    libro_ruta = Path(a.libro)
    try:
        libro = json.loads(libro_ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"TRABAJO: pasos 1,2,3 · no se pudo leer el libro ({e.__class__.__name__}); hacer la vuelta completa")
        return 0
    ahora = _fecha(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    carpeta = libro_ruta.parent
    if not a.ahora:
        # Pulso (17-nov): la vigilancia arrancó. Las vueltas sin trabajo no dejan latido; con esto la nube sabe que la Mac
        # y Claude andan y no aplica el corte de respaldo (plan_corte.py, infra/workers/vivo/src/corte.mjs).
        try:
            (carpeta / "pulso_vigilancia.json").write_text(json.dumps({"pulso": ahora.isoformat(timespec="seconds")}) + "\n", encoding="utf-8")
        except OSError:
            pass
    modo = modo_de_vuelta(carpeta, ahora) if a.modo == "auto" else a.modo
    if modo == "rapida":
        r = evaluar_rapida(libro, ahora, carpeta)
    else:
        r = evaluar(libro, ahora, carpeta)
        r["modo"] = "completa"
        if not a.ahora and not a.sin_marcar:
            try:
                (carpeta / "vigilancia_vuelta.json").write_text(json.dumps({"completa": ahora.isoformat(timespec="seconds")}) + "\n", encoding="utf-8")
            except OSError:
                pass
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else linea(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
