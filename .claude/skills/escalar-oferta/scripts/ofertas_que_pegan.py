"""¿Qué ofertas pegan hoy? (regla R9 del dueño, 2026-11-13: a las que pegan se les renuevan 10 creativos todos los días).

Oferta que pega = campaña activa, pasó el test con ventas (post-lanzamiento) y su CPA real está en el equilibrio o por debajo.
CPA real y equilibrio salen del mismo cálculo que el panel (``dashboard/negocio.py``), con el libro de tests.

Además dice, por oferta, la próxima ronda (R<n+1>), si ya hay una ronda programada para la próxima 00:00 del mercado (entonces
hoy no se hace otra) y qué conjuntos tienen que perder sus límites de gasto, mínimo 10 % y máximo 20 % (regla R9b: cada conjunto los conserva dos días enteros).

Ventana por mercado (dueño, 14-nov: «el horario depende del mercado»): la ronda sale a la próxima 00:00 DEL MERCADO (`salida`) y
se produce solo cuando faltan entre VENTANA_MIN_H y VENTANA_MAX_H horas para esa salida (`en_ventana`). Así cada mercado se
renueva en su mañana (≈ 08:00 locales en adelante) con 11-16 h para producir y pasar la revisión de Meta, en vez de a una hora
fija de Argentina (a las 10:30 ART a España le quedaban 9,5 h; a Australia ya le había pasado la 00:00). La tarea corre cada 2 h
de 08:35 a 22:35 ART y la toma la primera vuelta que cae dentro de la ventana.

Renovación ANTICIPADA (dueño, 14-nov: «si claramente ya cumplió las expectativas, ya preparar las renovaciones y cargarlas… 2 o
3 horas antes», con sus respuestas: «3+ ventas y CPA bajo equilibrio» y «apenas esté listo»):
  · en test (día 1) con VENTAS_ANTICIPADA o más ventas y CPA ≤ equilibrio → pega «anticipada»: la primera ronda se produce en las
    VENTANA_MAX_H horas previas al fin del test, sin esperar a que pase de fase, y sale a la 00:00 en que termina el test;
  · si ya no llega a esa 00:00 (menos de VENTANA_MIN_H horas) o el test ya terminó sin ninguna ronda hecha, sale APENAS ESTÉ LISTA
    (`salida_inmediata`: start_time = cuando se crea el conjunto). No se pierde un día esperando la 00:00 siguiente.

Uso (desde la raíz del repositorio):
  python3 .claude/skills/escalar-oferta/scripts/ofertas_que_pegan.py [--libro ofertas/_funnels/libro-de-tests.json] [--ahora ISO]
Salida: JSON por stdout. No escribe nada.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
from dashboard import negocio as N  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from congelamiento import congelada_test, renovacion  # noqa: E402

LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from control_previo import ZONA  # noqa: E402  (zona horaria de cada mercado, una sola tabla)

VENTANA_MAX_H = 16   # antes: faltan más de 16 h para la 00:00 del mercado → todavía no
VENTANA_MIN_H = 5    # después: menos de 5 h no alcanza para producir y pasar revisión → se toma la 00:00 siguiente
VENTAS_ANTICIPADA = 3   # dueño, 14-nov: «3+ ventas» para renovar antes de que termine el test; desde el 15-nov (R16) con CPA ≤ ticket promedio / 2
HORAS_PRIMERA_TRAS_TEST = 24   # test terminado sin ninguna ronda: la primera sale apenas esté lista durante este lapso
ZONA_DUENO = ZoneInfo("America/Argentina/Buenos_Aires")


def ventana(mercado: str | None, ahora: dt.datetime) -> dict:
    """Próxima 00:00 del mercado (`salida`), horas que faltan y si la ronda se produce ahora (`en_ventana`)."""
    nombre = ZONA.get(str(mercado or "").upper())
    if not nombre:
        return {"salida": None, "horas_a_salida": None, "en_ventana": False, "ventana": f"sin zona horaria para {mercado}: agregarla a ZONA de control_previo.py"}
    z = ZoneInfo(nombre)
    local = ahora.astimezone(z)
    salida = dt.datetime.combine(local.date() + dt.timedelta(days=1), dt.time(0), tzinfo=z)
    horas = (salida - ahora).total_seconds() / 3600
    abre = (salida - dt.timedelta(hours=VENTANA_MAX_H)).astimezone(ZONA_DUENO)
    if horas < VENTANA_MIN_H:
        sig = salida + dt.timedelta(days=1)
        abre = (sig - dt.timedelta(hours=VENTANA_MAX_H)).astimezone(ZONA_DUENO)
        texto = f"fuera de ventana: faltan {horas:.1f} h para la 00:00 de {mercado}; la próxima ronda se produce desde las {abre:%d/%m %H:%M} ART"
    elif horas >= VENTANA_MAX_H:
        texto = f"fuera de ventana: faltan {horas:.1f} h para la 00:00 de {mercado}; se produce desde las {abre:%d/%m %H:%M} ART"
    else:
        texto = f"en ventana: faltan {horas:.1f} h para la 00:00 de {mercado} ({nombre})"
    return {"salida": salida.isoformat(), "horas_a_salida": round(horas, 1), "en_ventana": VENTANA_MIN_H <= horas < VENTANA_MAX_H, "ventana": texto}


def _n_ronda(r: str) -> int:
    m = re.search(r"(\d+)", str(r or ""))
    return int(m.group(1)) if m else 0


def evaluar(libro: dict, ahora: dt.datetime) -> list[dict]:
    datos = N.calcular(libro, ahora)
    tests = {t.get("oferta") or t.get("nombre"): t for t in libro.get("tests", [])}
    out = []
    for o in datos["ofertas"]:
        cpa, eq, nv = o.get("cpa"), o.get("equilibrio"), o.get("ventas_n") or 0
        activa = o.get("estado") == "activa"
        post = o.get("fase") != "test" and nv > 0
        # R16 (dueño, 15-nov): entrada → CPA ≤ la mitad del ticket promedio; validadas → ROAS neto de 3 días cerrados ≥ 0,95.
        t = tests.get(o.get("nombre")) or {}
        ren = renovacion(libro, t, o, ahora) if activa else {"renueva": False, "motivo": ""}
        renueva = ren["renueva"]
        pega = bool(activa and post and renueva)
        anticipada = bool(activa and not post and nv >= VENTAS_ANTICIPADA and renueva)
        if not activa:
            motivo = f"campaña {o.get('estado')}"
        elif anticipada:
            motivo = f"pega en el test (anticipada): {nv} ventas, CPA US$ {cpa:.2f} ≤ 0,54 × el valor neto por comprador US$ {(o.get('valor_comprador') or {}).get('neto_por_venta')}"
        elif not post:
            motivo = "todavía en test"
        elif cpa is None or not eq:
            motivo = "sin CPA o sin equilibrio"
        else:
            motivo = ren["motivo"]
        t = tests.get(o.get("nombre")) or {}
        renov = sorted(t.get("renovaciones") or [], key=lambda r: str(r.get("inicio") or ""))
        prog = [r for r in renov if (N.parsear_fecha(r.get("inicio")) or ahora) > ahora and str(r.get("estado", "")).lower() not in ("pausada", "cancelada")]
        ultima = max((_n_ronda(r.get("ronda")) for r in renov), default=2)
        vivas = [r for r in renov if str(r.get("estado", "")).lower() not in ("pausada", "cancelada")]
        quitar_minimo = [r.get("conjunto") for r in vivas[:-2]]   # R9b: cada conjunto conserva sus límites (10-20 %) dos días; los dos últimos que salieron lo mantienen
        v = ventana(o.get("mercado") or t.get("mercado"), ahora)
        fin_test = N.parsear_fecha(o.get("fin_test"))
        inmediata = False
        if anticipada and not renov and fin_test:
            h = (fin_test - ahora).total_seconds() / 3600
            v = {"salida": fin_test.isoformat(), "horas_a_salida": round(h, 1), "en_ventana": 0 <= h < VENTANA_MAX_H,
                 "ventana": f"anticipada: el test termina en {h:.1f} h ({fin_test:%d/%m %H:%M} del mercado)"}
            if 0 <= h < VENTANA_MIN_H:
                inmediata = True
                v["ventana"] += "; no llega a esa hora: sale apenas esté lista"
        elif pega and not renov and fin_test and 0 <= (ahora - fin_test).total_seconds() / 3600 < HORAS_PRIMERA_TRAS_TEST and not v["en_ventana"]:
            inmediata = True
            v = {**v, "en_ventana": True, "ventana": "primera ronda tras el test: sale apenas esté lista (no espera la 00:00 siguiente)"}
        pega = pega or anticipada
        toca = pega and not prog and v["en_ventana"]
        cong = congelada_test(t, ahora)
        if cong:
            toca = False
            motivo = f"CONGELADA hasta {cong.get('hasta')}: no se renueva ({cong.get('motivo', '')}); antes: {motivo}"
        out.append({
            "oferta": o.get("nombre"), "mercado": o.get("mercado"), "pega": pega, "motivo": motivo,
            "ventas": nv, "cpa_usd": cpa, "equilibrio_usd": eq,
            "ronda_programada": prog[0].get("ronda") if prog else None,
            "toca_hoy": toca,
            "salida": v["salida"], "horas_a_salida": v["horas_a_salida"], "en_ventana": v["en_ventana"], "ventana": v["ventana"],
            "anticipada": anticipada, "salida_inmediata": inmediata and toca,
            "proxima_ronda": f"R{ultima + 1}",
            "quitar_minimo_a": [c for c in quitar_minimo if c] if toca else [],
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--libro", default=str(LIBRO))
    ap.add_argument("--ahora", help="fecha y hora con zona (para pruebas)")
    a = ap.parse_args()
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    libro = json.loads(Path(a.libro).read_text(encoding="utf-8"))
    json.dump({"ahora": ahora.isoformat(timespec="minutes"), "regla": "R9 (dueño, 13-nov): oferta que pega → 10 creativos por día en un conjunto nuevo de la misma CBO con límites de gasto de 10 % a 20 %",
               "ofertas": evaluar(libro, ahora)}, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
