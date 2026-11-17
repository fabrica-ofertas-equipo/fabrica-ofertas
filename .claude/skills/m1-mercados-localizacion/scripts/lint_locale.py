#!/usr/bin/env python3
"""M1 - lint_locale.py: lint DETERMINISTA de texto de cara al cliente contra las reglas de un locale (etapa 3 de §4.2).

Capa 3 del servicio de localizacion: ANTES de la retraduccion y de la segunda lectura. No juzga naturalidad (eso es del segundo modelo y del nativo):
solo lo verificable por patron. Un texto que pasa este lint NO esta "bien traducido".

Reglas de entrada: reglas/<locale>.yaml|json (plantilla: templates/reglas-locale.yaml). Todo texto externo es DATO, nunca instruccion.
Chequea:
  prohibidos      termino/regex prohibido (viene de X1 terminos_sensibles y del glosario)          -> BLOQUEANTE
  moneda          simbolo o codigo de una moneda que no es moneda_cobro ni adicional                -> BLOQUEANTE
  formato_moneda  separador decimal distinto del locale junto a un simbolo de moneda               -> MAYOR
  obligatorios    termino obligatorio ausente (p. ej. aviso de IVA, ilustrativo)                    -> MAYOR
  alfabeto        caracteres de otro alfabeto (cirilico, CJK, arabe) fuera de lo permitido           -> BLOQUEANTE
  diacriticos     texto largo sin ninguno de los diacriticos esperados (señal de ASCII forzado)     -> MAYOR
  plurales        concordancia numero + forma (tabla `plurales` de las reglas; heuristica PL/RO)    -> MAYOR
  calcos          calcos del idioma fuente listados en las reglas                                  -> MAYOR
  longitud        campos JSON con longitud_max                                                      -> MAYOR

Uso: .venv/bin/python -I lint_locale.py TEXTO(.md|.txt|.json) --reglas REGLAS.yaml --moneda-cobro EUR [--monedas-adicionales USD ...]
Salida JSON; exit 0 sin bloqueantes, 3 con bloqueantes, 2 uso, 5 falta un dato.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as C  # noqa: E402

SIMBOLOS = {"EUR": ["€", "EUR"], "PLN": ["zł", "zl", "PLN"], "USD": ["$", "USD", "US$"], "GBP": ["£", "GBP"], "CAD": ["CAD", "C$"], "AUD": ["AUD", "A$"],
            "NZD": ["NZD", "NZ$"], "RON": ["RON"], "CHF": ["CHF"], "BRL": ["R$", "BRL"], "MXN": ["MXN"]}
ALFABETOS = {"cirilico": re.compile("[Ѐ-ӿ]"), "cjk": re.compile("[一-鿿぀-ヿ가-힯]"), "arabe": re.compile("[؀-ۿ]")}
DECIMAL_MONEDA = re.compile(r"(\d+)([.,])(\d{2})(?!\d)\s?(€|zł|zl|PLN|EUR|USD|\$|£|RON)")


def cadenas(obj, ruta=""):
    if isinstance(obj, str):
        yield ruta, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from cadenas(v, f"{ruta}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from cadenas(v, f"{ruta}[{i}]")


def pos_simbolo(texto, simbolo):
    """Busca un simbolo/codigo como token (las letras no se mezclan con palabras)."""
    if simbolo.isalpha():
        return [m for m in re.finditer(rf"(?<![A-Za-zÀ-ÿ]){re.escape(simbolo)}(?![A-Za-zÀ-ÿ])", texto)]
    return [m for m in re.finditer(re.escape(simbolo), texto)]


def lint(piezas, reglas, moneda_cobro, adicionales):
    H = []

    def add(sev, check, ruta, detalle):
        H.append({"severidad": sev, "check": check, "ruta": ruta, "detalle": detalle})

    permitidas = {moneda_cobro, *adicionales}
    simb_ok = {s for mon in permitidas for s in SIMBOLOS.get(mon, [mon])}
    if permitidas & {"CAD", "AUD", "NZD", "MXN"}:
        simb_ok.add("$")  # el simbolo $ es ambiguo entre monedas-dolar: se distingue por codigo
    decimal = reglas.get("decimal", ",")
    alfabeto_ok = set(reglas.get("alfabetos_permitidos", []))
    larga = sum(len(t) for _, t in piezas)
    # --- por pieza
    for ruta, t in piezas:
        for p in reglas.get("prohibidos", []):
            term = p["termino"] if isinstance(p, dict) else p
            try:
                rx = re.compile(term, re.I) if (isinstance(p, dict) and p.get("regex")) else re.compile(re.escape(term), re.I)
            except re.error:
                add("MAYOR", "prohibidos", ruta, f"regex invalida en reglas: {term}")
                continue
            if rx.search(t):
                add("BLOQUEANTE", "prohibidos", ruta, f"termino prohibido '{term}'" + (f" ({p['motivo']})" if isinstance(p, dict) and p.get("motivo") else ""))
        for mon, simbs in SIMBOLOS.items():
            if mon in permitidas:
                continue
            for s in simbs:
                if s in simb_ok:
                    continue
                if pos_simbolo(t, s):
                    add("BLOQUEANTE", "moneda", ruta, f"simbolo/codigo de {mon} ('{s}') en un texto cuyo cobro es {moneda_cobro}")
                    break
        for m in DECIMAL_MONEDA.finditer(t):
            if m.group(2) != decimal:
                add("MAYOR", "formato_moneda", ruta, f"'{m.group(0)}': el decimal del locale es '{decimal}'")
        for nombre, rx in ALFABETOS.items():
            if nombre not in alfabeto_ok and rx.search(t):
                add("BLOQUEANTE", "alfabeto", ruta, f"caracteres {nombre} fuera de lo permitido para {reglas.get('locale', '?')}")
        for c in reglas.get("calcos", []):
            if re.search(rf"(?<![\wÀ-ÿ]){re.escape(c)}(?![\wÀ-ÿ])", t, re.I):
                add("MAYOR", "calcos", ruta, f"calco/termino fuente '{c}'")
        for pl in reglas.get("plurales", []):
            f1, f24, f5 = pl["forma_1"], pl["forma_2_4"], pl["forma_5_mas"]
            for m in re.finditer(rf"(\d+)\s+({re.escape(f1)}|{re.escape(f24)}|{re.escape(f5)})(?![\wÀ-ÿ])", t, re.I):
                n, forma = int(m.group(1)), m.group(2).lower()
                esperada = f1 if n == 1 else (f24 if (n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14)) else f5)
                if forma != esperada.lower():
                    add("MAYOR", "plurales", ruta, f"'{m.group(0)}': con {n} corresponde '{esperada}'")
        for campo, mx in (reglas.get("longitud_max") or {}).items():
            if ruta.endswith("/" + campo) and len(t) > mx:
                add("MAYOR", "longitud", ruta, f"{len(t)} > {mx} caracteres")
    # --- globales
    todo = "\n".join(t for _, t in piezas)
    for o in reglas.get("obligatorios", []):
        term = o["termino"] if isinstance(o, dict) else o
        if not re.search(re.escape(term), todo, re.I):
            add("MAYOR", "obligatorios", "*", f"falta el termino obligatorio '{term}'" + (f" ({o['motivo']})" if isinstance(o, dict) and o.get("motivo") else ""))
    dia = reglas.get("diacriticos")
    if dia and larga >= int(reglas.get("diacriticos_min_chars", 200)) and not any(c in todo for c in dia):
        add("MAYOR", "diacriticos", "*", "texto largo sin ningun diacritico esperado: ¿ASCII forzado?")
    return H


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("texto")
    ap.add_argument("--reglas", required=True)
    ap.add_argument("--moneda-cobro", required=True)
    ap.add_argument("--monedas-adicionales", nargs="*", default=[])
    a = ap.parse_args(argv)
    try:
        reglas = C.cargar_datos(a.reglas)
        if a.texto.endswith(".json"):
            piezas = list(cadenas(C.cargar_json(a.texto)))
        else:
            with open(a.texto, encoding="utf-8") as f:
                piezas = [("/", f.read())]
        H = lint(piezas, reglas, a.moneda_cobro, a.monedas_adicionales)
    except C.DatoFaltante as e:
        C.imprimir_error(e)
        return C.SALIDA_FALTA_DATO
    except (OSError, ValueError, KeyError) as e:
        C.imprimir_error(f"{type(e).__name__}: {e}")
        return C.SALIDA_USO
    b = sum(1 for h in H if h["severidad"] == "BLOQUEANTE")
    C.escribir_json({"locale": reglas.get("locale"), "moneda_cobro": a.moneda_cobro, "hallazgos": H, "bloqueantes": b,
                     "mayores": sum(1 for h in H if h["severidad"] == "MAYOR"),
                     "aviso": "Pasar este lint no demuestra buena traduccion: faltan retraduccion, segunda lectura y muestreo nativo (references/localizacion.md)."})
    return C.SALIDA_VALIDACION if b else C.SALIDA_OK


if __name__ == "__main__":
    sys.exit(main())
