#!/usr/bin/env python3
"""M1 - vigencia.py: trazabilidad (MQ-02) y vigencia (MQ-03 / R10) de fichas de pais.

Reglas (departamentos/16 §3.4; los numeros salen de empresa/parametros.yaml#grupos.mercados o, mientras no existan, de
scripts/parametros_m1.fallback.json marcados [SUPUESTO]):
  - tarifas (comision/fijo/disputas por metodo, recargo de ubicacion de Meta): vigencia_tarifas_dias  -> BLOQUEA (R10)
  - legal (fiscal, consumo, privacidad, DSA, identidad, ayuda del pais, obligacion de idioma): vigencia_legal_dias -> BLOQUEA (R10)
  - CPM de referencia: vigencia_cpm_dias -> NO bloquea ni excluye: vencido => MAYOR (MQ-03M) con etiqueta [SUPUESTO] y bandera cpm_vencido;
    se usa mult_cpm.central (1,2) y el 1,5 (estres) es solo sensibilidad
  - TODA hoja {valor, fuente_url, fecha_lectura, confianza} necesita fuente_url (URL o [VERIFICAR]), fecha valida y confianza A/B/C (MQ-02).

Uso:  .venv/bin/python -I vigencia.py FICHA.json [FICHA.json ...] --hoy AAAA-MM-DD [--parametros empresa/parametros.yaml]
Salida: JSON por ficha; codigo 0 sin bloqueantes, 3 con bloqueantes, 2 uso, 5 falta un parametro o la fecha.
La fecha ("hoy") es SIEMPRE un argumento: el script no lee el reloj (determinista).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as C  # noqa: E402

CONFIANZAS = ("A", "B", "C")
CAMPOS_TARIFA = ("comision_bp", "fijo", "disputas", "recargo_meta_bp")
BLOQUES_LEGALES = ("fiscal", "consumo_y_datos", "consumo", "privacidad", "dsa", "identidad_vendedor", "ayuda_pais")


def hojas(nodo, ruta=""):
    """Todas las hojas con envoltorio {valor, fuente_url, fecha_lectura, confianza} (valor puede ser objeto)."""
    out = []
    if isinstance(nodo, dict):
        if "valor" in nodo and ("fuente_url" in nodo or "fecha_lectura" in nodo or "confianza" in nodo):
            out.append((ruta, nodo))
            return out
        for k, v in nodo.items():
            out += hojas(v, f"{ruta}/{k}")
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            out += hojas(v, f"{ruta}[{i}]")
    return out


def categoria(ruta):
    p = ruta.lower()
    if "cpm_bench" in p:
        return "cpm"
    if any(c in p for c in CAMPOS_TARIFA):
        return "tarifas"
    if any(f"/{b}" in p for b in BLOQUES_LEGALES) or "obligacion_legal_idioma" in p or "ayuda" in p:
        return "legal"
    return "otros"


def trazabilidad(ficha):
    """MQ-02: hojas sin fuente, sin fecha valida o sin confianza A/B/C."""
    fallos = []
    for ruta, h in hojas(ficha):
        fu, fe, co = h.get("fuente_url"), h.get("fecha_lectura"), h.get("confianza")
        if not isinstance(fu, str) or not fu.strip():
            fallos.append({"ruta": ruta, "motivo": "sin_fuente_url (URL o [VERIFICAR])"})
        try:
            C.fecha(fe)
        except (ValueError, TypeError):
            fallos.append({"ruta": ruta, "motivo": "sin_fecha_lectura_valida"})
        if co not in CONFIANZAS:
            fallos.append({"ruta": ruta, "motivo": "confianza_no_A_B_C"})
    return fallos


def evaluar_ficha(ficha, hoy, params):
    hoy = C.fecha(hoy)
    lim = {"tarifas": int(C.pedir(params, "vigencia_tarifas_dias")),
           "legal": int(C.pedir(params, "vigencia_legal_dias")),
           "cpm": int(C.pedir(params, "vigencia_cpm_dias"))}
    bloq, mayores, edades = [], [], {}
    for ruta, h in hojas(ficha):
        try:
            edad = (hoy - C.fecha(h.get("fecha_lectura"))).days
        except (ValueError, TypeError):
            continue  # ya lo reporta trazabilidad()
        if edad < 0:
            bloq.append({"ruta": ruta, "regla": "R10", "motivo": f"fecha_lectura en el futuro ({edad} dias)"})
            continue
        cat = categoria(ruta)
        edades.setdefault(cat, []).append(edad)
        if cat in ("tarifas", "legal") and edad > lim[cat]:
            bloq.append({"ruta": ruta, "regla": "R10", "categoria": cat, "edad_dias": edad, "limite_dias": lim[cat],
                         "motivo": f"dato de {cat} vencido"})
        if cat == "cpm" and edad > lim["cpm"]:
            mayores.append({"ruta": ruta, "regla": "MQ-03", "categoria": "cpm", "edad_dias": edad, "limite_dias": lim["cpm"],
                            "motivo": "CPM vencido: no bloquea ni excluye; exige etiqueta [SUPUESTO] y bandera cpm_vencido (mult_cpm central; 1,5 solo sensibilidad)"})
    tr = trazabilidad(ficha)
    return {
        "hoy": str(hoy),
        "limites_dias": lim,
        "origen_parametros": {k: params.get(k) for k in ("vigencia_tarifas_dias", "vigencia_legal_dias", "vigencia_cpm_dias")},
        "edad_max_dias_por_categoria": {k: max(v) for k, v in edades.items()},
        "bloqueantes": bloq + [dict(x, regla="MQ-02") for x in tr],
        "mayores": mayores,
        "cpm_vencido": bool(mayores),
        "hojas": len(hojas(ficha)),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichas", nargs="+")
    ap.add_argument("--hoy", required=True, help="AAAA-MM-DD (obligatorio; el script no lee el reloj)")
    ap.add_argument("--parametros", default=None)
    a = ap.parse_args(argv)
    try:
        params, _ = C.cargar_parametros(a.parametros)
        res = {}
        for ruta in a.fichas:
            res[ruta] = evaluar_ficha(C.cargar_datos(ruta), a.hoy, params)
    except C.DatoFaltante as e:
        C.imprimir_error(e)
        return C.SALIDA_FALTA_DATO
    except (OSError, ValueError) as e:
        C.imprimir_error(e)
        return C.SALIDA_USO
    C.escribir_json(res)
    return C.SALIDA_VALIDACION if any(r["bloqueantes"] for r in res.values()) else C.SALIDA_OK


if __name__ == "__main__":
    sys.exit(main())
