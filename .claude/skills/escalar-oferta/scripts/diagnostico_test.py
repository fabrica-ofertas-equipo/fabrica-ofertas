"""Diagnóstico de un test que se apagó: en qué tramo del embudo se cayó (pedido del 13-nov; solo registra).

El dueño: hasta tener una «winner winner» (≥ 1.000 USD de ganancia por día) no se cambia la búsqueda con estos datos. Se
guardan igual, para que cuando haya ganadoras se pueda comparar qué tenían distinto. Va al campo `aprendizaje` del test.

Tramos, en orden (el primero que falla es «donde se cayó»):
  anuncio    CTR de enlace < 0,8 % o CPM > 2,5 × el de la cuenta: el anuncio no frena el dedo o Meta lo cobra caro.
  carga      menos del 60 % de los clics llega a ver la página: la página tarda o se rompe.
  landing    menos del 4 % de las visitas va al pago (referencia del dueño 8-12 %): la página no convence.
  checkout   menos del 15 % de los pagos iniciados compra (referencia 25-30 %): precio, confianza o medios de pago.
  volumen    los tramos están bien pero no alcanzó la muestra: no se sabe (posible falso negativo del test).

Uso: python3 .claude/skills/escalar-oferta/scripts/diagnostico_test.py --metricas '{"gasto": 25.5, "impresiones": 4000,
     "cpm_cuenta": 6, "clics": 40, "visitas": 30, "checkouts": 3, "compras": 0}' [--json]
"""
from __future__ import annotations

import argparse
import json
import sys

CTR_MIN, CPM_VECES = 0.008, 2.5
CARGA_MIN, LANDING_MIN, CHECKOUT_MIN = 0.60, 0.04, 0.15


def diagnosticar(m: dict) -> dict:
    imp, clics, vis, chk, comp = (float(m.get(k) or 0) for k in ("impresiones", "clics", "visitas", "checkouts", "compras"))
    gasto = float(m.get("gasto") or 0)
    ctr = clics / imp if imp else None
    cpm = 1000 * gasto / imp if imp else None
    carga = vis / clics if clics else None
    land = chk / vis if vis else None
    caja = comp / chk if chk else None
    tasas = {"ctr_pct": round(100 * ctr, 2) if ctr is not None else None, "cpm": round(cpm, 2) if cpm is not None else None,
             "clic_a_pagina_pct": round(100 * carga, 1) if carga is not None else None,
             "pagina_a_pago_pct": round(100 * land, 1) if land is not None else None,
             "pago_a_compra_pct": round(100 * caja, 1) if caja is not None else None}
    cpm_cuenta = float(m.get("cpm_cuenta") or 0)
    if ctr is not None and (ctr < CTR_MIN or (cpm_cuenta and cpm and cpm > CPM_VECES * cpm_cuenta)):
        donde, porque = "anuncio", "CTR bajo o CPM caro: los anuncios no frenan el dedo"
    elif carga is not None and carga < CARGA_MIN:
        donde, porque = "carga", "muchos clics no llegan a ver la página"
    elif land is not None and vis >= 30 and land < LANDING_MIN:
        donde, porque = "landing", "la página no lleva al pago"
    elif caja is not None and chk >= 5 and caja < CHECKOUT_MIN:
        donde, porque = "checkout", "se pierden en el pago"
    else:
        donde, porque = "volumen", "ningún tramo falla claro: faltó muestra (posible falso negativo)"
    return {"donde_se_cayo": donde, "porque": porque, **tasas}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metricas", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = diagnosticar(json.loads(a.metricas))
    print(json.dumps(r, ensure_ascii=False) if a.json else f"{r['donde_se_cayo']}: {r['porque']} · {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
