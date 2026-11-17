"""Imprime el libro de costos e ingresos por test a partir de ofertas/_funnels/libro-de-tests.json.

Uso: python3 .claude/skills/escalar-oferta/scripts/libro_de_tests.py [--md salida.md]

Por test: producción (Kie + Gemini + otros), gasto en Meta, ventas brutas y netas (después de comisiones
e impuestos de Impul Pay, como las informa Impultienda), resultado contra Meta y contra el costo total,
embudo de la tienda contra las referencias del dueño (checkout 8-12 % de las visitas; compra 25-30 % de los checkouts)
y punto de equilibrio (CPA máximo = neto por venta).
"""
import json, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
REF_CHECKOUT = (8, 12)
REF_COMPRA = (25, 30)


def pct(a, b):
    return None if not b else 100.0 * a / b


def f(x, d=2):
    return "—" if x is None else f"{x:,.{d}f}"


def marca(v, rango):
    if v is None:
        return ""
    return " ✓" if v >= rango[0] else " ✗"


def main():
    L = json.loads(LIBRO.read_text())
    tc, pk, pg = L["tipos_de_cambio"], L["precio_credito_kie_usd"], L["precio_imagen_gemini_usd"]
    filas, tot = [], dict(prod=0, meta=0, bruto=0, neto=0)
    out = ["# Libro de tests", "", f"Fuente: `{LIBRO.relative_to(RAIZ)}`. Montos en USD; tipos de cambio de Impultienda.", ""]
    out += ["| Test | Mercado | Estado | Producción | Meta | Ventas | Bruto | Neto | Neto − Meta | Neto − todo | CPA real | CPA de equilibrio |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in L["tests"]:
        p = t.get("produccion") or {}
        prod = p.get("kie_creditos", 0) * pk + p.get("gemini_imagenes", 0) * pg + p.get("otros_usd", 0)
        meta = (t.get("meta") or {}).get("gasto_usd", 0) or 0
        bruto = sum(v["bruto"] * tc[v["moneda"]] for v in t.get("ventas") or [])
        neto = sum(v["neto"] * tc[v["moneda"]] for v in t.get("ventas") or [])
        # compradores = órdenes principales; upsell, bump y rebaja suman al neto pero no son ventas (02-decidir.md)
        n = sum(1 for v in t.get("ventas") or [] if v.get("tipo", "principal") not in ("upsell", "bump", "downsell"))
        cpa = meta / n if n else None
        equil = neto / n if n else None
        for k, v in (("prod", prod), ("meta", meta), ("bruto", bruto), ("neto", neto)):
            tot[k] += v
        out.append(f"| {t['nombre']} | {t['mercado']} | {t['estado']} | {f(prod)} | {f(meta)} | {n} | {f(bruto)} | {f(neto)} | {f(neto - meta)} | {f(neto - meta - prod)} | {f(cpa)} | {f(equil)} |")
        e = t.get("tienda_embudo") or {"landing": 0, "checkout": 0, "compras": 0}
        filas.append((t["nombre"], e["landing"], e["checkout"], e["compras"], pct(e["checkout"], e["landing"]), pct(e["compras"], e["checkout"]), pct(e["compras"], e["landing"]), t.get("corte", "")))
    out.append(f"| **Total** | | | {f(tot['prod'])} | {f(tot['meta'])} | | {f(tot['bruto'])} | {f(tot['neto'])} | {f(tot['neto'] - tot['meta'])} | {f(tot['neto'] - tot['meta'] - tot['prod'])} | | |")
    out += ["", "Costos fijos compartidos (no incluidos arriba): " + "; ".join(f"{c['concepto']}: {f(c['usd_mes']) if c['usd_mes'] is not None else 'a confirmar'} USD/mes" for c in L["costos_fijos_compartidos"]), ""]
    out += ["## Embudo de la tienda", "", f"Referencias del dueño: checkout {REF_CHECKOUT[0]}-{REF_CHECKOUT[1]} % de las visitas; compra {REF_COMPRA[0]}-{REF_COMPRA[1]} % de los checkouts.", "",
            "| Test | Visitas | Checkouts | Compras | % checkout | % compra / checkout | % compra / visita | Corte |", "|---|---|---|---|---|---|---|---|"]
    for nm, l, c, v, a, b, g, corte in filas:
        out.append(f"| {nm} | {l} | {c} | {v} | {f(a, 1)}{marca(a, REF_CHECKOUT)} | {f(b, 1)}{marca(b, REF_COMPRA)} | {f(g, 2)} | {corte} |")
    out += ["", "Con menos de ~30 checkouts por test, una venta más o menos mueve el % de compra 3 puntos o más: leerlo como pista, no como veredicto."]
    txt = "\n".join(out)
    if "--md" in sys.argv:
        Path(sys.argv[sys.argv.index("--md") + 1]).write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
