#!/usr/bin/env python3
"""Ranking de mercados SIN el criterio de pagos (el dueño dejó los métodos de pago para después).

Reproduce el modelo de docs/_investigacion/08-mercados-ranking.md §2.1-2.2 (siete criterios con
puntajes 0-5 y pesos PA 15, CAC 20, COMP 10, PAGO 20, FISC 15, LOC 10, FRAUD 10) y recalcula
sacando PAGO y reescalando los pesos restantes a 100. Los puntajes por criterio son los de la
tabla 2.2 de la nota 08 (top 15 de 24 mercados puntuados; el resto no tiene desglose publicado).

Uso:
  python3 -I rank_sin_pagos.py            # tabla en texto
  python3 -I rank_sin_pagos.py --json     # salida JSON

Limitaciones (heredadas de 08 y de 16-red-team): casi todos los puntajes son confianza C;
las diferencias menores a ~8 puntos no son concluyentes; el neto de 08 no incluye Stripe Tax,
reembolsos ni disputas (16 §5.1); los CPM son de julio de 2026. No sustituye a M1.
"""
import json
import sys

PESOS = {"PA": 15, "CAC": 20, "COMP": 10, "PAGO": 20, "FISC": 15, "LOC": 10, "FRAUD": 10}
ORDEN = list(PESOS)

# mercado: (PA, CAC, COMP, PAGO, FISC, LOC, FRAUD, ajuste_creadores)  — fuente: 08 §2.2
MERCADOS = {
    "Canadá (inglés, sin Quebec)": (5, 2, 2, 5, 4, 5, 4, +2),
    "Nueva Zelanda": (4, 3, 3, 4, 4, 5, 4, +1),
    "Australia": (5, 2, 3, 4, 4, 5, 4, +1),
    "EE. UU. (inglés)": (5, 1, 1, 4, 4, 5, 3, +4),
    "Irlanda": (4, 2, 2, 5, 2, 5, 3, +1),
    "Reino Unido": (5, 1, 2, 4, 2, 5, 4, +3),
    "Italia": (4, 3, 2, 3, 2, 4, 3, +5),
    "Hispanos en EE. UU. (español)": (4, 0, 3, 4, 4, 5, 3, +2),
    "Polonia": (3, 3, 3, 4, 2, 3, 4, 0),
    "Portugal (PT-PT)": (3, 3, 3, 4, 2, 3, 3, +2),
    "Bélgica (NL/FR)": (4, 2, 3, 4, 2, 2, 4, 0),
    "Grecia": (2, 4, 3, 4, 2, 2, 3, 0),
    "Suecia": (5, 2, 4, 2, 2, 3, 3, -1),
    "España": (3, 3, 1, 3, 2, 4, 3, 0),
    "Suiza": (5, 2, 2, 2, 3, 2, 3, 0),
}


def calcular(excluir=("PAGO",)):
    resto = sum(p for k, p in PESOS.items() if k not in excluir)
    filas = []
    for nombre, v in MERCADOS.items():
        s = dict(zip(ORDEN, v[:7]))
        ajuste = v[7]
        base_08 = sum(PESOS[k] * s[k] / 5 for k in ORDEN)
        sin = sum(PESOS[k] * s[k] / 5 for k in ORDEN if k not in excluir) * 100 / resto
        filas.append({
            "mercado": nombre,
            "base_08": round(base_08, 1),
            "ajuste_creadores": ajuste,
            "total_08": round(base_08 + ajuste, 1),
            "sin_pagos": round(sin, 1),
            "sin_pagos_con_ajuste": round(sin + ajuste, 1),
        })
    return filas


def main():
    filas = sorted(calcular(), key=lambda f: -f["sin_pagos_con_ajuste"])
    if "--json" in sys.argv:
        print(json.dumps(filas, ensure_ascii=False, indent=2))
        return
    print(f"{'Mercado':32}{'Base 08':>8}{'Aj.':>5}{'Total 08':>9}{'Sin pagos':>10}{'+ Aj.':>8}")
    for f in filas:
        print(f"{f['mercado']:32}{f['base_08']:8.0f}{f['ajuste_creadores']:5}{f['total_08']:9.0f}"
              f"{f['sin_pagos']:10.1f}{f['sin_pagos_con_ajuste']:8.1f}")


if __name__ == "__main__":
    main()
