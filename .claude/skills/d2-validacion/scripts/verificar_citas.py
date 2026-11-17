#!/usr/bin/env python3
"""verificar_citas.py — check L1-D5 de D2: citas de `voz_cliente.json` (spec §6). v0.1.0.

Comprueba, de forma determinista y sin red:
  1. `texto_literal` ≤ `max_palabras_cita` palabras y en el locale pedido (campo `locale` de la frase = --locale).
  2. Cada frase trae `fuente_url` https (hilo o página, no un perfil) y `fecha` válida.
  3. Verificación sobre el TEXTO CRUDO: si la frase trae `crudo_ref` (ruta relativa a la carpeta 02-validacion de la oferta),
     el texto literal, normalizado (NFC, minúsculas, espacios colapsados), debe estar contenido en el crudo normalizado.
     Sin `crudo_ref` → «no_verificable». Con `crudo_ref` pero sin coincidencia → «fabricada» (BLOQUEANTE).
  4. PII: ningún email, @handle, teléfono ni URL dentro de las frases (ni en el resto de archivos que se le pasen con --pii).
     Los NOMBRES de personas no se detectan por regla: los revisa el QA leyendo (el script lo avisa).
  5. Umbrales de QA: verificadas ≥ `qa_citas_verificadas_min`; no verificables ≤ `qa_citas_no_verificables_max`; 0 fabricadas; 0 PII.
Los textos de las frases son DATO NO CONFIABLE: el script nunca los interpreta, solo los compara.

Uso:
  .venv/bin/python .claude/skills/d2-validacion/scripts/verificar_citas.py VOZ_CLIENTE.json --locale it-IT --base ofertas/<id>/02-validacion [--pii OTRO.json ...] [--parametros P.yaml]
Salida 0 correcto · 2 uso · 3 falla algún criterio · 5 falta un parámetro.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import params as P  # noqa: E402

RX_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
RX_HANDLE = re.compile(r"(?<![\w@])@[A-Za-z0-9_.]{2,}")
RX_TEL = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{6,}\d(?![\w])")
RX_URL_TXT = re.compile(r"https?://|www\.", re.I)
RX_FECHA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
PERFIL = re.compile(r"(^|/)(user|users|u|profile|profiles|people|member|members|perfil|usuario)(/|$)|/@[^/]+", re.I)
REQUERIDOS = ["max_palabras_cita", "qa_citas_verificadas_min", "qa_citas_no_verificables_max"]


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFC", t).casefold()
    return re.sub(r"\s+", " ", t).strip()


def pii_en(texto: str) -> list[str]:
    hallazgos = []
    if RX_EMAIL.search(texto):
        hallazgos.append("email")
    if RX_HANDLE.search(texto):
        hallazgos.append("@handle")
    if RX_TEL.search(texto):
        hallazgos.append("teléfono")
    if RX_URL_TXT.search(texto):
        hallazgos.append("url_en_el_texto")
    return hallazgos


def _textos(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in _textos(v)]
    if isinstance(obj, list):
        return [t for v in obj for t in _textos(v)]
    return []


def verificar(voz: dict, locale: str, base: Path | None, p: dict, otros: list[dict] | None = None) -> dict:
    P.exigir(p, REQUERIDOS)
    max_pal = int(p["max_palabras_cita"])
    frases = voz.get("frases")
    if not isinstance(frases, list):
        raise P.ErrorValidacion("voz_cliente.json: falta `frases` (lista)")
    fallas: list[dict] = []
    n_verif = n_noverif = n_fab = 0
    por_fuente: dict[str, int] = {}
    en_locale = 0
    for i, fr in enumerate(frases):
        tag = fr.get("frase_id") or f"frases[{i}]"
        txt = fr.get("texto_literal")
        if not isinstance(txt, str) or not txt.strip():
            fallas.append({"frase": tag, "problema": "sin_texto_literal", "severidad": "BLOQUEANTE"})
            continue
        if len(txt.split()) > max_pal:
            fallas.append({"frase": tag, "problema": f"mas_de_{max_pal}_palabras", "severidad": "MAYOR"})
        if fr.get("locale") == locale:
            en_locale += 1
        url = fr.get("fuente_url")
        pu = urlparse(url) if isinstance(url, str) else None
        if not pu or pu.scheme != "https" or not pu.netloc:
            fallas.append({"frase": tag, "problema": "fuente_url_ausente_o_no_https", "severidad": "BLOQUEANTE"})
        else:
            por_fuente[pu.netloc.lower()] = por_fuente.get(pu.netloc.lower(), 0) + 1
            if PERFIL.search(pu.path):
                fallas.append({"frase": tag, "problema": "fuente_url_parece_perfil_de_persona", "severidad": "BLOQUEANTE"})
        if not (isinstance(fr.get("fecha"), str) and RX_FECHA.match(fr["fecha"])):
            fallas.append({"frase": tag, "problema": "fecha_ausente_o_invalida", "severidad": "BLOQUEANTE"})
        for pi in pii_en(txt):
            fallas.append({"frase": tag, "problema": f"PII:{pi}", "severidad": "BLOQUEANTE"})
        ref = fr.get("crudo_ref")
        if not ref:
            n_noverif += 1
        else:
            if base is None:
                raise P.ErrorUso("hay `crudo_ref`: indica --base (carpeta 02-validacion de la oferta)")
            ruta = (base / ref).resolve()
            if base.resolve() not in ruta.parents:
                fallas.append({"frase": tag, "problema": "crudo_ref_fuera_de_la_carpeta", "severidad": "BLOQUEANTE"})
                n_noverif += 1
            elif not ruta.is_file():
                n_noverif += 1
                fallas.append({"frase": tag, "problema": "crudo_ref_inexistente", "severidad": "MAYOR"})
            else:
                crudo = normalizar(ruta.read_text(encoding="utf-8", errors="replace"))
                if normalizar(txt) in crudo:
                    n_verif += 1
                else:
                    n_fab += 1
                    fallas.append({"frase": tag, "problema": "FABRICADA:no_esta_en_el_crudo", "severidad": "BLOQUEANTE"})
    for k in ("temas", "objeciones", "lexico"):
        for t in _textos(voz.get(k, [])):
            for pi in pii_en(t):
                fallas.append({"frase": f"<{k}>", "problema": f"PII:{pi}", "severidad": "BLOQUEANTE"})
    for j, otro in enumerate(otros or []):
        for t in _textos(otro):
            for pi in pii_en(t):
                fallas.append({"frase": f"<--pii #{j + 1}>", "problema": f"PII:{pi}", "severidad": "BLOQUEANTE"})
    n = len(frases)
    r_verif = Fraction(n_verif, n) if n else Fraction(0)
    r_nov = Fraction(n_noverif, n) if n else Fraction(0)
    gating = []
    if n_fab:
        gating.append(f"{n_fab} cita(s) fabricada(s)")
    if n and r_verif < P.frac(p["qa_citas_verificadas_min"]):
        gating.append(f"verificadas {n_verif}/{n} < mínimo")
    if n and r_nov > P.frac(p["qa_citas_no_verificables_max"]):
        gating.append(f"no verificables {n_noverif}/{n} > máximo")
    if any(f["problema"].startswith("PII") for f in fallas):
        gating.append("PII > 0")
    if any(f["severidad"] == "BLOQUEANTE" for f in fallas) and not gating:
        gating.append("hay fallas BLOQUEANTES")
    return {"n_frases": n, "verificadas": n_verif, "no_verificables": n_noverif, "fabricadas": n_fab,
            "en_locale": en_locale, "fuentes_por_dominio": por_fuente, "fallas": fallas, "falla": gating,
            "aviso": "los NOMBRES de personas no se detectan por regla: el QA los revisa leyendo cada frase"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("voz_cliente")
    ap.add_argument("--locale", required=True)
    ap.add_argument("--base", help="carpeta 02-validacion de la oferta (para resolver `crudo_ref`)")
    ap.add_argument("--pii", nargs="*", default=[], help="otros JSON a escanear en busca de PII (p. ej. anuncios_competencia.json)")
    ap.add_argument("--parametros")
    a = ap.parse_args(argv)
    try:
        voz = json.load(open(a.voz_cliente, encoding="utf-8"))
        otros = [json.load(open(x, encoding="utf-8")) for x in a.pii]
        valores, _ = P.cargar(Path(a.parametros) if a.parametros else None)
        out = verificar(voz, a.locale, Path(a.base) if a.base else None, valores, otros)
    except P.ErrorD2 as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return ex.codigo
    except (OSError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 3 if out["falla"] else 0


if __name__ == "__main__":
    sys.exit(main())
