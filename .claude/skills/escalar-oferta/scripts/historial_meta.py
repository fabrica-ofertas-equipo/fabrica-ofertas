#!/usr/bin/env python3
"""Carga en el libro el gasto de Meta POR DÍA de cada campaña (historial_diario), con candado (libro.py).

Pedido del dueño (2026-11-14): «en la oferta Oferta F aparecen las ventas pero no el gasto de Meta… el dashboard siempre
está desactualizado y no me da confianza». El panel arma «Hoy», «Ayer» y los rangos con historial_diario; las ofertas nuevas no lo
tenían hasta la revisión diaria del día siguiente, así que mostraban las ventas del día con el gasto en cero.

La vigilancia de cada hora, cuando lee Meta, pide además las campañas del libro con time_increment=1 (desde ayer, o desde el
inicio si la oferta es nueva) y corre este script con lo que devolvió ads_get_ad_entities. Por cada fila (día × campaña):
reemplaza la del mismo día y campaña o la agrega. Si con eso los días cubren toda la pauta (desde el día de inicio en la zona de la
cuenta hasta hoy), también pone los totales de `meta` y `corte` al momento de la lectura.

Uso: python3 historial_meta.py --lectura <json con la lista ad_entities> [--leido ISO] [--seco]
La lista acepta el formato de ads_get_ad_entities (date_start, id, amount_spent{value}, impressions, link_click,
omni_landing_page_view, omni_initiated_checkout, omni_purchase, omni_purchase_values{value}).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import libro as LB  # noqa: E402


def _n(x) -> float:
    if isinstance(x, dict):
        x = x.get("value")
    try:
        return float(x) if x not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def fila(r: dict, leido: str) -> dict | None:
    fecha = str(r.get("date_start") or r.get("fecha") or "")[:10]
    camp = str(r.get("id") or r.get("campana") or "")
    if len(fecha) != 10 or not camp:
        return None
    return {"fecha": fecha, "campana": camp, "gasto_usd": round(_n(r.get("amount_spent", r.get("gasto_usd"))), 2),
            "impresiones": int(_n(r.get("impressions", r.get("impresiones")))), "clics_enlace": int(_n(r.get("link_click", r.get("clics_enlace")))),
            "visitas_landing_meta": int(_n(r.get("omni_landing_page_view", r.get("visitas_landing_meta")))),
            "inicios_pago_meta": int(_n(r.get("omni_initiated_checkout", r.get("inicios_pago_meta")))),
            "compras_meta": int(_n(r.get("omni_purchase", r.get("compras_meta")))),
            "valor_compras_meta_usd": round(_n(r.get("omni_purchase_values", r.get("valor_compras_meta_usd"))), 2), "leido": leido}


def campanas(t: dict) -> set[str]:
    c = t.get("campana")
    ids = {str(x) for x in (c if isinstance(c, list) else [c]) if x}
    # Campañas extra de la oferta (pocket, variaciones: 15-nov); sin esto el panel no sumaba su gasto.
    ids |= {str(x.get("id")) for x in ((t.get("ficha") or {}).get("campanas") or []) if isinstance(x, dict) and x.get("id")}
    return ids


def aplicar(libro: dict, filas: list[dict], leido: str, hoy: dt.date) -> list[str]:
    """Mezcla las filas en cada test del libro (puro sobre el dict). Devuelve qué cambió, una línea por test."""
    zona = ZoneInfo(libro.get("zona_horaria_cuenta") or "America/Argentina/Buenos_Aires")
    out = []
    for t in libro.get("tests") or []:
        if not isinstance(t, dict):
            continue
        mias = [f for f in filas if f["campana"] in campanas(t)]
        if not mias:
            continue
        hist = [h for h in t.get("historial_diario") or [] if isinstance(h, dict)]
        claves = {(f["fecha"], f["campana"]) for f in mias}
        hist = [h for h in hist if (str(h.get("fecha"))[:10], str(h.get("campana"))) not in claves] + mias
        hist.sort(key=lambda h: (str(h.get("fecha")), str(h.get("campana"))))
        t["historial_diario"] = hist
        linea = f"{t.get('nombre')}: {len(mias)} días cargados"
        try:
            inicio = dt.datetime.fromisoformat(str(t.get("inicio"))).astimezone(zona).date()
        except ValueError:
            inicio = None
        dias = {str(h.get("fecha"))[:10] for h in hist}
        if inicio and all((inicio + dt.timedelta(days=i)).isoformat() in dias for i in range((hoy - inicio).days + 1)):
            suma = lambda k: sum(_n(h.get(k)) for h in hist)  # noqa: E731
            meta = dict(t.get("meta") or {})
            meta.update({"gasto_usd": round(suma("gasto_usd"), 2), "impresiones": int(suma("impresiones")), "clics_enlace": int(suma("clics_enlace")),
                         "visitas_landing_meta": int(suma("visitas_landing_meta")), "inicios_pago_meta": int(suma("inicios_pago_meta")),
                         "compras_meta": int(suma("compras_meta")), "valor_compras_meta_usd": round(suma("valor_compras_meta_usd"), 2),
                         "_corte_meta": f"{leido} (suma por día)"})
            t["meta"] = meta
            t["corte"] = leido
            linea += f" · total al día US$ {meta['gasto_usd']:.2f}"
        out.append(linea)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lectura", required=True)
    ap.add_argument("--leido", help="ISO de la lectura (por defecto, ahora en hora de Argentina)")
    ap.add_argument("--seco", action="store_true", help="mostrar sin escribir")
    a = ap.parse_args(argv)
    datos = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
    if isinstance(datos, dict):
        datos = datos.get("ad_entities", datos.get("filas", []))
    if isinstance(datos, str):
        datos = json.loads(datos)
    ahora = dt.datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
    leido = a.leido or ahora.strftime("%Y-%m-%dT%H:%M-03:00")
    filas = [f for f in (fila(r, leido) for r in datos if isinstance(r, dict)) if f]
    if a.seco:
        libro = json.loads(LB.LIBRO.read_text(encoding="utf-8"))
        print("\n".join(aplicar(libro, filas, leido, ahora.date())) or "ninguna campaña del libro en la lectura")
        return 0
    cambios: list[str] = []
    LB.modificar(lambda libro: cambios.extend(aplicar(libro, filas, leido, ahora.date())))   # candado, respaldo y escritura atómica
    print("\n".join(cambios) or "ninguna campaña del libro en la lectura")
    return 0


if __name__ == "__main__":
    sys.exit(main())
