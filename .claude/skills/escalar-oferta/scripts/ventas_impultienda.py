#!/usr/bin/env python3
"""Suma al libro las ventas de Impultienda que todavía no están (con candado, vía libro.py).

Pedido del dueño (2026-11-14): «el dashboard siempre que lo miro está desactualizado y no me da confianza». Las ventas entraban
al libro solo en la revisión diaria; ese día faltaban una de Oferta B y una de Oferta F. La vigilancia de cada hora
lee ahora las ventas de hoy y ayer de cada tienda con campaña andando (impultienda_listar_ventas) y corre este script.

Entrada (--lectura): lista de {"tienda": "<subdominio>", "ventas": <lo que devolvió impultienda_listar_ventas>} (vale también
el objeto completo con «detalle»). Por cada orden que no esté en el libro (por número): la agrega al test cuyo `tienda` incluye
ese subdominio, en la moneda de la tienda (USD), con neto ESTIMADO = bruto × comisión medida (reglas `impulpay.neto_estimado`,
0,919) y «confirmar en Impul Pay». Una orden post-compra entra como tipo «upsell» (suma ingresos, no cuenta como comprador).

Uso: python3 ventas_impultienda.py --lectura <json> [--seco]
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
from reglas import valor  # noqa: E402,F401

# Capa de tienda (tienda/): la plataforma donde se vende se elige en tienda/config.json; Impultienda por defecto.
_RAIZ_T = next(p for p in Path(__file__).resolve().parents if (p / "tienda" / "__init__.py").is_file())
if str(_RAIZ_T) not in sys.path:
    sys.path.insert(0, str(_RAIZ_T))
import tienda as _tienda  # noqa: E402

TIENDA = _tienda.activa()
NETO = float(TIENDA.neto_estimado())
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def _ventas(bloque) -> list[dict]:
    """Ventas en forma normal (tienda/contrato.py) desde la respuesta cruda de la plataforma activa."""
    return TIENDA.ventas(bloque)


def aplicar(libro: dict, lectura: list[dict], ahora: dt.datetime) -> list[str]:
    """Agrega las órdenes que falten (puro sobre el dict). Devuelve una línea por venta agregada."""
    out = []
    for bloque in lectura:
        slug = str(bloque.get("tienda") or "")
        t = next((x for x in libro.get("tests") or [] if isinstance(x, dict) and slug in (x.get("tienda") or [])), None)
        if not t:
            continue
        tiene = {str(v.get("orden")) for v in t.get("ventas") or [] if isinstance(v, dict)}
        niveles = {x.get("slug"): x.get("nivel") for x in (t.get("ficha") or {}).get("tiendas") or [] if isinstance(x, dict)}
        for v in _ventas(bloque):
            orden = str(v.get("orden") or "")
            if not orden or orden in tiene:
                continue
            try:
                cuando = dt.datetime.fromisoformat(str(v.get("fecha")).replace("Z", "+00:00")).astimezone(ZONA)
            except ValueError:
                cuando = ahora.astimezone(ZONA)
            bruto = round(float(v.get("total") or 0), 2)
            fila = {"orden": orden, "moneda": str(v.get("moneda") or "USD"), "bruto": bruto, "neto": round(bruto * NETO, 2),
                    "fecha": cuando.date().isoformat(), "dia_cuenta": cuando.date().isoformat(), "tienda": slug,
                    "nota": f"cargada por la vigilancia el {ahora.astimezone(ZONA).strftime('%d-%m %H:%M')} desde {TIENDA.nombre}; neto estimado ({NETO * 100:.1f} %); confirmar en la pasarela"}
            if niveles.get(slug):
                fila["nivel"] = niveles[slug]
            if v.get("post_compra"):
                fila["tipo"] = "upsell"
            t.setdefault("ventas", []).append(fila)
            tiene.add(orden)
            out.append(f"{t.get('nombre')}: orden {orden} · {bruto:.2f} {fila['moneda']} · {fila['fecha']}{' · upsell' if v.get('post_compra') else ''}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lectura", required=True)
    ap.add_argument("--seco", action="store_true")
    a = ap.parse_args(argv)
    lectura = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
    lectura = lectura if isinstance(lectura, list) else [lectura]
    ahora = dt.datetime.now(dt.timezone.utc)
    if a.seco:
        print("\n".join(aplicar(json.loads(LB.LIBRO.read_text(encoding="utf-8")), lectura, ahora)) or "sin ventas nuevas")
        return 0
    cambios: list[str] = []
    LB.modificar(lambda libro: cambios.extend(aplicar(libro, lectura, ahora)))
    print("\n".join(cambios) or "sin ventas nuevas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
