#!/usr/bin/env python3
"""Validaciones deterministas (L1) de D6: matriz, copies, guiones, assets, textos congelados, n_anuncios_max y evals.

Solo lee archivos de la oferta y de ``empresa/``; no usa red ni secretos; no escribe nada. No reemplaza
a ``compliance.lint_claims`` (lint de claims por idioma), ni a ``scripts.creativos.{preflight_d6,cost_preflight,
ocr_check,match_landing,riesgo_pieza}`` (de S-B; ``references/dependencias.md``): comprueba lo que se puede
comprobar sin ellos. El nivel de riesgo de cada pieza se recalcula con ``scripts.nivel_riesgo.calcular`` (la ÚNICA
tabla ejes -> nivel; esta skill no tiene tabla propia). Un hallazgo BLOQUEANTE o MAYOR sale con código 3; sin topes
de créditos y con costo >0, 5.

Uso (desde la raíz del repositorio):
  .venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py nmax    --oferta-dir ofertas/OF-AAAAMM-NN
  .venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py matriz  --oferta-dir ofertas/OF-AAAAMM-NN
  .venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py textos  --oferta-dir ... [--qa-a qa/d6-v1-previo.json]
  .venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py assets  --oferta-dir ...
  .venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py ranuras --oferta-dir ...   # encargo de D5: imágenes de la landing
  .venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py todo    --oferta-dir ...
  .venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py evals
Opciones comunes: --json, --raiz RUTA (raíz del repositorio; por defecto se deduce de este archivo).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

RAIZ_POR_DEFECTO = Path(__file__).resolve().parents[4]
SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_POR_DEFECTO))  # para importar scripts.validar_esquemas (hashes, esquemas)

from scripts import nivel_riesgo as nr  # noqa: E402  (tabla única ejes -> nivel; SC-3)
from scripts import validar_esquemas as ve  # noqa: E402

HOOK_TIPOS = ("dolor-situacion", "resultado-artefacto", "curiosidad", "mito", "demostracion", "lista-numero", "escena-pov",
              "pregunta-tarea")
FORMATOS = {"imagen": "img", "video": "vid", "carrusel": "car"}
CTA = ("LEARN_MORE", "SHOP_NOW", "DOWNLOAD", "GET_OFFER", "SIGN_UP")
NIVELES_CONCIENCIA = ("N1", "N2", "N3", "N4")  # N5 no existe en el test
ORDEN_RIESGO = {"verde": 0, "amarillo": 1, "rojo": 2}
EJES_RIESGO = ("P", "C", "E", "N")
PRODUCTORES = ("D4", "D6", "dueno")  # enum ASCII de assets[].productor (LT-56); en prosa, «dueño»
RX_FONT_FACE = re.compile(r"@font-face\s*\{[^}]*\}", re.I | re.S)
RX_FONT_FAMILY = re.compile(r"font-family\s*:\s*[\"']?([^\"';}]+)", re.I)
PRESENTADORES = ("sin_rostro", "locucion_ia", "avatar_ia")
RATIO_DIMS = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "3:4": (1080, 1440), "16:9": (1920, 1080)}
RX_AD_NAME = re.compile(r"^[A-Za-z0-9-]+_[A-Za-z0-9-]+_[A-Za-z0-9-]+_v[1-9][0-9]*$")
RX_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RX_CLAIM_TAG = re.compile(r"\[claim:\s*([a-z0-9-]+)\s*\]")
RX_MOJIBAKE = re.compile("�|Ã[\u0080-¿]|Å[\u0080-¿]|Ä[\u0080-¿]|Â[\u0080-¿]|â€")
RX_PRECIO = re.compile(r"(?:(?:\$|£)\s?\d[\d.,   ]*|\d[\d.,   ]*\s?(?:€|zł|lei|RON|PLN|EUR|USD|GBP|\$|£))")
RX_ILUSTRATIVO = re.compile(r"ilustrativ|illustrat|ilustracyjn|beispielhaft|titre d.exemple|illustrative|example", re.I)
SIMBOLOS = {"EUR": "€", "PLN": "zł", "USD": "$", "GBP": "£", "RON": "lei"}
MONEDA_DE_TOKEN = {"€": "EUR", "EUR": "EUR", "zł": "PLN", "PLN": "PLN", "lei": "RON", "RON": "RON", "$": "USD", "USD": "USD", "£": "GBP", "GBP": "GBP"}
# Palabras funcionales por idioma: heurística gruesa solo para detectar un texto largo en OTRO idioma que el del locale.
STOP = {
    "es": ("el", "la", "los", "las", "que", "para", "con", "una", "por", "del", "tu", "se"),
    "it": ("il", "di", "per", "che", "con", "una", "della", "del", "le", "dei", "sono", "non"),
    "pl": ("i", "w", "na", "z", "do", "jest", "się", "nie", "dla", "to", "oraz", "jak"),
    "en": ("the", "and", "for", "with", "your", "you", "is", "of", "to", "in", "a", "this"),
    "fr": ("le", "la", "les", "des", "pour", "avec", "une", "est", "de", "du", "et", "vous"),
    "de": ("der", "die", "das", "und", "für", "mit", "ein", "eine", "ist", "zu", "den", "nicht"),
    "ro": ("și", "de", "pentru", "cu", "un", "o", "este", "la", "în", "nu", "tu", "sau"),
}
CHECKS_CONOCIDOS = {
    "D6-L1-01", "D6-L1-02", "D6-L1-03", "D6-L1-04", "D6-L1-05", "D6-L1-06", "D6-L1-07", "D6-L1-08", "D6-L1-09", "D6-L1-10",
    "D6-H01", "D6-N01", "D6-C01",
    "X1-P01", "X1-P02", "X1-P04", "X1-P05", "X1-P07", "X1-P08", "X1-E01", "X1-E03", "X1-K01", "X1-K02", "X1-M01", "X1-M02",
    "X1-M03", "X1-J06", "X1-D01",
}
PATRON_BLOQUEANTE = "BLOQUEANTE"


class Hallazgos(list):
    def add(self, check: str, severidad: str, patron: str, ref: str, detalle: str) -> None:
        self.append({"check_id": check, "severidad": severidad, "patron_clave": patron, "ref": ref, "detalle": detalle})

    def graves(self) -> list[dict]:
        return [h for h in self if h["severidad"] in (PATRON_BLOQUEANTE, "MAYOR")]


# ----------------------------------------------------------------------------------------------- utilidades

def norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def cargar(ruta: Path) -> Any:
    return ve.cargar_json(ruta) if ruta.suffix == ".json" else ve.cargar_yaml(ruta)


def param(raiz: Path, grupo: str, clave: str) -> Any:
    datos = ve.cargar_yaml(raiz / "empresa" / "parametros.yaml")
    try:
        return datos["grupos"][grupo][clave]["valor"]
    except (KeyError, TypeError) as exc:
        raise KeyError(f"parametros.yaml sin {grupo}.{clave}") from exc


def idioma_probable(texto: str) -> dict[str, int]:
    palabras = re.findall(r"[^\W\d_]+", texto.lower())
    return {lang: sum(1 for p in palabras if p in lista) for lang, lista in STOP.items()}


def formatos_precio(monto: int, moneda: str, locale: str) -> set[str]:
    """Cadenas aceptadas para un precio en el ``locale`` (references/localizacion.md §3)."""
    expo = getattr(ve, "EXPONENTE_ISO4217", {}).get(moneda, 2)
    entero, dec = divmod(monto, 10 ** expo) if expo else (monto, 0)
    dec_txt = f"{dec:0{expo}d}" if expo else ""
    simbolo = SIMBOLOS.get(moneda, moneda)
    sep = "." if locale.startswith("en-") else ","
    base = f"{entero}{sep}{dec_txt}" if expo else f"{entero}"
    delante = simbolo in ("$", "£")
    aceptados = {f"{simbolo}{base}"} if delante else {f"{base} {simbolo}", f"{base} {simbolo}"}
    if expo and dec == 0:
        aceptados |= ({f"{simbolo}{entero}"} if delante else {f"{entero} {simbolo}", f"{entero} {simbolo}"})
    return aceptados


def valor_numerico(token: str) -> float | None:
    m = re.search(r"\d[\d.,   ]*", token)
    if not m:
        return None
    s = re.sub(r"[   ]", "", m.group(0)).rstrip(".,")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        partes = s.split(",")
        s = s.replace(",", ".") if len(partes[-1]) in (1, 2) else s.replace(",", "")
    elif s.count(".") > 1 or (("." in s) and len(s.split(".")[-1]) == 3):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


# ----------------------------------------------------------------------------------------------- n_anuncios_max

def calcular_nmax(raiz: Path, oferta_dir: Path, k: int = 3) -> dict:
    eco = ve.cargar_json(oferta_dir / "03-oferta" / "economia.json")
    gasto, cpa = eco["gasto_test_plan"], eco["cpa_obj"]
    if gasto["moneda"] != cpa["moneda"]:
        raise ValueError("gasto_test_plan y cpa_obj en monedas distintas")
    if cpa["monto"] <= 0:
        raise ValueError("cpa_obj debe ser > 0")
    por_presupuesto = gasto["monto"] // (k * cpa["monto"])
    p_creativos = param(raiz, "creativos", "n_anuncios_max")
    p_tope = param(raiz, "campana", "n_anuncios_tope")
    minimo = param(raiz, "campana", "n_anuncios_min")
    n_max = min(p_creativos, p_tope, por_presupuesto)
    return {"n_anuncios_max": n_max, "n_anuncios_min": minimo, "por_presupuesto": por_presupuesto, "creativos_n_anuncios_max": p_creativos,
            "campana_n_anuncios_tope": p_tope, "k": k, "genera": n_max >= minimo}


# ----------------------------------------------------------------------------------------------- riesgo por pieza

def recalcular_riesgo_pieza(r: dict) -> tuple[dict | None, str | None]:
    """Nivel, subnivel y colores de una pieza con ``scripts.nivel_riesgo.calcular`` (la única tabla ejes -> nivel).

    Usa ``riesgo_pieza.ejes_codigo`` ({P: P1, C: C1, E: E0, N: N1}). Si la pieza no los trae, deriva del color
    declarado de cada eje (nivel = el máximo; subnivel B con >=2 amarillos) ``[SUPUESTO]`` y lo dice. Devuelve
    ``(resultado, error)``: un código fuera de escala o inconsistente es un error (falla cerrado).
    """
    codigos = r.get("ejes_codigo")
    if isinstance(codigos, dict):
        try:
            c = nr.calcular(codigos)
        except Exception as exc:  # ErrorValidacion de engine.errores: código desconocido, ausente o N0
            return None, str(getattr(exc, "mensaje", exc))
        return {"nivel": c["nivel"], "subnivel": c["subnivel"], "colores": c["colores"], "origen": "ejes_codigo"}, None
    colores = {e: r.get(e) for e in EJES_RIESGO}
    maximo = max(colores.values(), key=lambda v: ORDEN_RIESGO[v])
    amarillos = sum(1 for v in colores.values() if v == "amarillo")
    sub = (None if maximo != "amarillo" else ("B" if amarillos >= 2 else "A"))
    return {"nivel": maximo, "subnivel": sub, "colores": colores, "origen": "colores"}, None


def validar_riesgo_pieza(h: Hallazgos, ad: str, r: dict, riesgo_oferta: dict) -> None:
    """Reglas L1.4 de la spec 07 §6 (SC-15): el nivel de una pieza se compara con el RECALCULADO, no con el de la oferta.

    1. nivel declarado < recalculado = falso verde (BLOQUEANTE).
    2. recalculado > nivel de la oferta = MAYOR (se reescribe o se descarta la pieza); un ROJO no avanza (BLOQUEANTE).
       Una pieza MENOR que la oferta NO es un hallazgo (p. ej. solo producto, sin la promesa central).
    3. una pieza que repite la promesa central hereda al menos el eje P de la oferta (menor = falso verde, BLOQUEANTE).
    """
    ejes = {e: r.get(e) for e in EJES_RIESGO}
    if any(v not in ORDEN_RIESGO for v in ejes.values()) or r.get("nivel") not in ORDEN_RIESGO:
        h.add("D6-L1-04", PATRON_BLOQUEANTE, "riesgo-pieza-incompleto", ad, "riesgo_pieza exige P, C, E, N y nivel en verde|amarillo|rojo")
        return
    nivel_oferta = riesgo_oferta["nivel"]
    maximo_declarado = max(ejes.values(), key=lambda v: ORDEN_RIESGO[v])
    if r["nivel"] != maximo_declarado:
        h.add("D6-L1-04", PATRON_BLOQUEANTE, "nivel-no-es-el-maximo-de-los-ejes", ad, f"nivel {r['nivel']} != máximo de ejes {maximo_declarado}")
    rec, error = recalcular_riesgo_pieza(r)
    if rec is None:
        h.add("D6-L1-04", PATRON_BLOQUEANTE, "riesgo-pieza-ejes-codigo-invalidos", ad, f"ejes_codigo no válidos para scripts.nivel_riesgo: {error}")
        return
    if rec["origen"] == "colores":
        h.add("D6-L1-04", "MENOR", "riesgo-pieza-sin-ejes-codigo", ad, "sin ejes_codigo: nivel derivado de los colores declarados [SUPUESTO]; declarar P, C, E, N con código para recalcular con scripts.nivel_riesgo")
    # (1) nivel declarado frente al recalculado
    for e in EJES_RIESGO:
        if ORDEN_RIESGO[ejes[e]] < ORDEN_RIESGO[rec["colores"][e]]:
            h.add("D6-L1-04", PATRON_BLOQUEANTE, "riesgo-pieza-falso-verde", ad, f"eje {e} declarado {ejes[e]} < recalculado {rec['colores'][e]} (ejes_codigo)")
    if ORDEN_RIESGO[r["nivel"]] < ORDEN_RIESGO[rec["nivel"]]:
        h.add("D6-L1-04", PATRON_BLOQUEANTE, "riesgo-pieza-falso-verde", ad, f"nivel declarado {r['nivel']} < recalculado {rec['nivel']}")
    elif ORDEN_RIESGO[r["nivel"]] > ORDEN_RIESGO[rec["nivel"]] and rec["origen"] == "ejes_codigo":
        h.add("D6-L1-04", "MENOR", "riesgo-pieza-nivel-sobre-el-recalculado", ad, f"nivel declarado {r['nivel']} > recalculado {rec['nivel']}: revisar los ejes o el código")
    # (2) recalculado frente a la oferta
    nivel_efectivo = max((r["nivel"], maximo_declarado, rec["nivel"]), key=lambda v: ORDEN_RIESGO[v])
    if nivel_efectivo == "rojo":
        h.add("D6-L1-04", PATRON_BLOQUEANTE, "pieza-roja", ad, "una pieza ROJA no avanza")
    elif ORDEN_RIESGO[rec["nivel"]] > ORDEN_RIESGO[nivel_oferta]:
        h.add("D6-L1-04", "MAYOR", "pieza-mas-riesgosa-que-la-oferta", ad, f"recalculado {rec['nivel']} > oferta {nivel_oferta}: reescribir o descartar la pieza")
    # (3) promesa central: hereda al menos el eje P de la oferta
    repite = r.get("repite_promesa_central")
    if not isinstance(repite, bool):
        h.add("D6-L1-04", "MAYOR", "riesgo-pieza-sin-promesa-central-declarada", ad, "riesgo_pieza.repite_promesa_central debe ser true/false (regla 3 de L1.4 no verificable)")
    elif repite:
        p_pieza = max((ejes["P"], rec["colores"]["P"]), key=lambda v: ORDEN_RIESGO[v])
        if ORDEN_RIESGO[p_pieza] < ORDEN_RIESGO[riesgo_oferta["P"]]:
            h.add("D6-L1-04", PATRON_BLOQUEANTE, "riesgo-pieza-promesa-central-con-p-menor", ad, f"repite la promesa central y su eje P ({p_pieza}) < el de la oferta ({riesgo_oferta['P']})")


# ----------------------------------------------------------------------------------------------- matriz y copies

def _textos_anuncio(a: dict, copy: dict | None, guion: str | None) -> list[str]:
    t: list[str] = []
    if copy:
        t += [str(copy.get(k, "")) for k in ("texto_principal", "titular", "descripcion")]
        t += [str(v) for v in (copy.get("texto_en_pieza") or {}).values()]
    if guion:
        t.append(guion)
    return [x for x in t if x]


def validar_matriz(raiz: Path, oferta_dir: Path) -> Hallazgos:
    h = Hallazgos()
    d6 = oferta_dir / "06-creativos"
    oferta = ve.cargar_json(oferta_dir / "03-oferta" / "oferta.json")
    mercado = ve.cargar_json(oferta_dir / "mercado.json")
    ruta_matriz, ruta_copies = d6 / "matriz.json", d6 / "copies.json"
    if not ruta_matriz.is_file() or not ruta_copies.is_file():
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "falta-archivo", "06-creativos", "faltan matriz.json o copies.json")
        return h
    matriz, copies = ve.cargar_json(ruta_matriz), ve.cargar_json(ruta_copies)
    locale = mercado["locale"]
    lang = locale.split("-")[0]
    permitidos = {c["claim_id"]: c["texto"] for c in oferta["promesa"]["claims_permitidos"]}
    prohibidos = list(oferta["promesa"].get("claims_prohibidos", [])) + list(oferta["riesgo"].get("claims_a_evitar", []))
    nivel_oferta = oferta["riesgo"]["nivel"]
    angulos = {a["angulo_id"] for a in oferta["angulos"]}

    # --- idioma y oferta (D6-L1-06)
    if matriz.get("oferta_id") != oferta["oferta_id"]:
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "oferta-distinta", "matriz.json", "oferta_id no coincide con oferta.json")
    if matriz.get("locale") != locale:
        h.add("D6-L1-06", PATRON_BLOQUEANTE, "locale-distinto", "matriz.json", f"locale {matriz.get('locale')} != mercado.json {locale}")
    if copies.get("idioma") != locale:
        h.add("D6-L1-06", PATRON_BLOQUEANTE, "idioma-distinto", "copies.json", f"idioma {copies.get('idioma')} != {locale}")

    # --- conceptos
    conceptos = matriz.get("conceptos", [])
    ids_c = [c.get("concepto_id") for c in conceptos]
    if len(conceptos) < 3:
        h.add("D6-L1-10", PATRON_BLOQUEANTE, "menos-de-3-conceptos", "matriz.json", f"{len(conceptos)} conceptos (el esquema exige ≥3)")
    if len(set(ids_c)) != len(ids_c):
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "concepto-id-duplicado", "matriz.json", "concepto_id repetido")
    try:
        tope_conceptos = param(raiz, "creativos", "n_conceptos_test")
        if len(conceptos) > tope_conceptos:
            h.add("D6-L1-01", "MAYOR", "conceptos-sobre-tope", "matriz.json", f"{len(conceptos)} > creativos.n_conceptos_test ({tope_conceptos})")
    except KeyError as exc:
        h.add("D6-L1-01", "MENOR", "parametro-ausente", "parametros.yaml", str(exc))
    for c in conceptos:
        cid = c.get("concepto_id", "?")
        if not RX_KEBAB.match(str(cid)):
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "concepto-id-no-kebab", cid, "concepto_id debe ser kebab ASCII")
        if c.get("angulo_id") not in angulos:
            h.add("D6-L1-10", PATRON_BLOQUEANTE, "angulo-fuera-de-la-oferta", cid, f"angulo_id {c.get('angulo_id')} no está en oferta.angulos[]")
        if c.get("nivel_conciencia") not in NIVELES_CONCIENCIA:
            h.add("D6-L1-10", "MAYOR", "nivel-conciencia-invalido", cid, f"{c.get('nivel_conciencia')} (N5 no existe en el test)")
        if not str(c.get("hipotesis", "")).strip():
            h.add("D6-L1-10", "MAYOR", "concepto-sin-hipotesis", cid, "falta hipotesis")
        fuentes = [f for f in c.get("fuentes_inspiracion", []) if str(f).strip()]
        if len(fuentes) < 3:
            h.add("D6-L1-08", PATRON_BLOQUEANTE, "menos-de-3-fuentes", cid, f"{len(fuentes)} fuentes de inspiración (≥3)")
    if len({c.get("angulo_id") for c in conceptos}) < 3:
        h.add("D6-L1-10", PATRON_BLOQUEANTE, "menos-de-3-angulos", "matriz.json", "se exigen ≥3 ángulos distintos")

    # --- anuncios
    anuncios = matriz.get("anuncios", [])
    try:
        nmax = calcular_nmax(raiz, oferta_dir)
        if len(anuncios) > nmax["n_anuncios_max"]:
            h.add("D6-N01", PATRON_BLOQUEANTE, "anuncios-sobre-el-maximo", "matriz.json", f"{len(anuncios)} > n_anuncios_max {nmax['n_anuncios_max']}")
        if len(anuncios) < nmax["n_anuncios_min"] or not nmax["genera"]:
            h.add("D6-N01", PATRON_BLOQUEANTE, "anuncios-bajo-el-minimo", "matriz.json", f"{len(anuncios)} anuncios; mínimo {nmax['n_anuncios_min']}; n_anuncios_max={nmax['n_anuncios_max']}")
    except (KeyError, ValueError, OSError) as exc:
        h.add("D6-N01", "MAYOR", "n-max-no-calculable", "economia.json", str(exc))
    nombres = [a.get("ad_name") for a in anuncios]
    if len(set(nombres)) != len(nombres):
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "ad-name-duplicado", "matriz.json", "ad_name repetido")
    por_concepto: dict[str, list[dict]] = {}
    pares: dict[tuple, str] = {}
    copy_por_ad = {a.get("ad_name"): a for a in copies.get("anuncios", [])}
    for a in anuncios:
        ad = a.get("ad_name", "?")
        cid = a.get("concepto_id")
        por_concepto.setdefault(cid, []).append(a)
        if cid not in ids_c:
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "concepto-desconocido", ad, f"concepto_id {cid} no está en conceptos[]")
        formato = a.get("formato")
        if formato not in FORMATOS:
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "formato-invalido", ad, f"formato {formato!r} (imagen|video|carrusel)")
        esperado = f"{cid}_{FORMATOS.get(formato, '?')}_{a.get('hook_id')}_v{a.get('v')}"
        if not RX_AD_NAME.match(str(ad)) or ad != esperado or not str(ad).isascii():
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "ad-name-no-conforme", ad, f"debe ser {esperado} (ASCII, _ entre campos, - dentro)")
        if a.get("hook_tipo") not in HOOK_TIPOS:
            h.add("D6-L1-10", PATRON_BLOQUEANTE, "hook-tipo-fuera-del-vocabulario", ad, f"{a.get('hook_tipo')!r} no está en el vocabulario cerrado")
        if not str(a.get("variable_cambiada", "")).strip():
            h.add("D6-L1-10", "MAYOR", "sin-variable-cambiada", ad, "falta variable_cambiada")
        pres = a.get("presentador")
        if pres not in PRESENTADORES:
            h.add("D6-L1-10", PATRON_BLOQUEANTE, "presentador-invalido", ad, f"{pres!r}")
        elif pres == "avatar_ia" and not (oferta["macro_nicho"] == "dinero" and nivel_oferta == "verde"):
            h.add("X1-E03", PATRON_BLOQUEANTE, "avatar-ia-fuera-de-dinero-verde", ad, "avatar_ia solo en dinero verde")
        if not isinstance(a.get("precio_visible"), bool):
            h.add("D6-L1-10", "MAYOR", "precio-visible-no-booleano", ad, "precio_visible debe ser true/false")
        clave_par = (next((c.get("angulo_id") for c in conceptos if c.get("concepto_id") == cid), None), a.get("hook_tipo"), formato)
        if clave_par in pares:
            h.add("D6-L1-10", PATRON_BLOQUEANTE, "par-angulo-hook-formato-repetido", ad, f"igual ángulo+hook_tipo+formato que {pares[clave_par]}")
        pares[clave_par] = ad
        # claims
        cl = a.get("claim_ids") or []
        if not cl:
            h.add("D6-L1-03", PATRON_BLOQUEANTE, "anuncio-sin-claim-id", ad, "sin claim_ids")
        for x in cl:
            if x not in permitidos:
                h.add("D6-L1-03", PATRON_BLOQUEANTE, "claim-no-permitido", ad, f"claim_id {x} no está en claims_permitidos")
        if a.get("claim_id_principal") not in cl:
            h.add("D6-L1-03", "MAYOR", "claim-principal-ausente", ad, "claim_id_principal debe estar en claim_ids")
        # riesgo por pieza (spec §6 L1.4; SC-3 y SC-15)
        validar_riesgo_pieza(h, ad, a.get("riesgo_pieza") or {}, oferta["riesgo"])
        if a.get("presentador") in ("sin_rostro", "locucion_ia") or oferta["macro_nicho"] in ("salud", "relaciones"):
            if oferta["macro_nicho"] in ("salud", "relaciones") and pres == "avatar_ia":
                h.add("X1-M03", PATRON_BLOQUEANTE, "avatar-en-salud-o-relaciones", ad, "salud y relaciones: solo sin_rostro o locucion_ia")
        if ad not in copy_por_ad:
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "anuncio-sin-copy", ad, "no tiene entrada en copies.json")

    # --- hooks por concepto
    try:
        max_hooks = param(raiz, "creativos", "hooks_por_concepto")
    except KeyError:
        max_hooks = 3
    for cid, lista in por_concepto.items():
        if len(lista) > max_hooks:
            h.add("D6-L1-10", "MAYOR", "hooks-sobre-el-tope", cid, f"{len(lista)} hooks > creativos.hooks_por_concepto ({max_hooks})")
        tipos = [x.get("hook_tipo") for x in lista]
        if len(set(tipos)) != len(tipos):
            h.add("D6-L1-10", "MAYOR", "hooks-del-concepto-con-igual-tipo", cid, "dos hooks de un concepto deben diferir en hook_tipo")
    for c in conceptos:
        if c.get("concepto_id") not in por_concepto:
            h.add("D6-L1-10", "MAYOR", "concepto-sin-anuncios", c.get("concepto_id", "?"), "concepto sin anuncios")

    # --- copy, guion, texto efectivo
    esperado_precio = oferta["precio"]["lista"]
    aceptados_precio: dict[float, set[str]] = {}
    valores_ok = [esperado_precio] + ([oferta["bump"]["precio"]] if oferta.get("bump") else [])
    expo = getattr(ve, "EXPONENTE_ISO4217", {}).get(esperado_precio["moneda"], 2)
    for p in valores_ok:
        aceptados_precio[p["monto"] / (10 ** expo)] = formatos_precio(p["monto"], p["moneda"], locale)
    for a in anuncios:
        ad = a.get("ad_name", "?")
        entrada = copy_por_ad.get(ad)
        if not entrada:
            continue
        for campo, tope in (("titular", 40), ("descripcion", 30)):
            valor = str(entrada.get(campo, ""))
            if not valor.strip():
                h.add("D6-L1-01", PATRON_BLOQUEANTE, f"{campo}-vacio", ad, f"{campo} vacío")
            elif len(valor) > tope:
                h.add("D6-L1-01", "MAYOR", f"{campo}-excede-el-limite", ad, f"{len(valor)} > {tope} caracteres")
        if not str(entrada.get("texto_principal", "")).strip():
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "texto-principal-vacio", ad, "texto_principal vacío")
        if entrada.get("cta") not in CTA:
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "cta-fuera-del-enum", ad, f"{entrada.get('cta')!r}")
        if sorted(entrada.get("claim_ids", [])) != sorted(a.get("claim_ids", [])):
            h.add("D6-L1-03", "MAYOR", "claim-ids-distintos-entre-matriz-y-copies", ad, "matriz.json y copies.json declaran distintos claim_ids")
        ruta_guion = d6 / "guiones" / f"{ad}.md"
        guion = ruta_guion.read_text(encoding="utf-8") if ruta_guion.is_file() else None
        if guion is None:
            h.add("D6-L1-01", "MAYOR", "falta-guion", ad, f"no existe guiones/{ad}.md")
        else:
            etiquetas = set(RX_CLAIM_TAG.findall(guion))
            if not etiquetas:
                h.add("D6-L1-03", "MAYOR", "guion-sin-claim", ad, "el guion no marca ningún [claim: id]")
            for x in etiquetas:
                if x not in permitidos:
                    h.add("D6-L1-03", PATRON_BLOQUEANTE, "claim-no-permitido-en-guion", ad, f"[claim: {x}] no está en claims_permitidos")
                elif x not in a.get("claim_ids", []):
                    h.add("D6-L1-03", "MAYOR", "claim-del-guion-fuera-de-claim-ids", ad, f"{x} no figura en claim_ids del anuncio")
        textos = _textos_anuncio(a, entrada, guion)
        todo = "\n".join(textos)
        normal = norm(todo)
        for frase in prohibidos:
            if frase and norm(frase) in normal:
                h.add("D6-L1-03", PATRON_BLOQUEANTE, "claim-prohibido-en-el-texto", ad, f"aparece «{frase}» (claims_prohibidos/claims_a_evitar)")
        if RX_MOJIBAKE.search(todo):
            h.add("D6-L1-06", "MAYOR", "caracteres-corruptos", ad, "caracteres corruptos o mojibake en el texto")
        principal = str(entrada.get("texto_principal", ""))
        if len(re.findall(r"\w+", principal)) >= 6:
            puntajes = idioma_probable(principal + " " + str(entrada.get("titular", "")))
            esperado_n = puntajes.get(lang, 0)
            otro, mejor = max(((k, v) for k, v in puntajes.items() if k != lang), key=lambda kv: kv[1])
            if esperado_n == 0 and mejor >= 3:
                h.add("D6-L1-06", "MAYOR", "idioma-distinto-del-locale", ad, f"el texto parece «{otro}» ({mejor} palabras funcionales) y el locale es {locale}")
        # precio y moneda del texto visible (anuncio + pieza)
        visibles = [str(entrada.get(k, "")) for k in ("texto_principal", "titular", "descripcion")] + [str(v) for v in (entrada.get("texto_en_pieza") or {}).values()]
        precio_hallado = False
        for texto in visibles:
            for token in RX_PRECIO.findall(texto):
                token = token.strip()
                valor = valor_numerico(token)
                if valor is None:
                    continue
                moneda_token = next((m for s, m in MONEDA_DE_TOKEN.items() if s in token), None)
                if moneda_token and moneda_token != esperado_precio["moneda"] and not RX_ILUSTRATIVO.search(texto):
                    h.add("X1-K01", PATRON_BLOQUEANTE, "moneda-distinta-de-la-landing", ad, f"«{token}» está en {moneda_token}; la oferta cobra en {esperado_precio['moneda']}")
                    continue
                if any(abs(valor - v) < 0.005 for v in aceptados_precio):
                    precio_hallado = True
                    v_ok = next(v for v in aceptados_precio if abs(valor - v) < 0.005)
                    if token not in aceptados_precio[v_ok] and token.replace(" ", " ") not in aceptados_precio[v_ok]:
                        h.add("X1-K01", "MAYOR", "formato-de-precio-de-otro-pais", ad, f"«{token}» no usa el formato del locale {locale} ({sorted(aceptados_precio[v_ok])[0]})")
                elif not RX_ILUSTRATIVO.search(texto):
                    h.add("X1-K01", PATRON_BLOQUEANTE, "precio-distinto-de-la-landing", ad, f"«{token}» no es el precio de la oferta ni del bump")
        if a.get("precio_visible") is True and not precio_hallado:
            h.add("X1-K01", "MAYOR", "precio-visible-sin-precio", ad, "precio_visible=true pero ningún texto muestra el precio de la oferta")
        if a.get("precio_visible") is False and precio_hallado:
            h.add("X1-K01", "MAYOR", "precio-visible-no-declarado", ad, "el texto muestra el precio pero precio_visible=false")
    # --- reserva
    try:
        tope_reserva = param(raiz, "creativos", "reserva_conceptos")
        if len(matriz.get("reserva", [])) > tope_reserva:
            h.add("D6-L1-10", "MENOR", "reserva-sobre-el-tope", "matriz.json", f"{len(matriz['reserva'])} > creativos.reserva_conceptos ({tope_reserva})")
    except KeyError:
        pass
    reservas = {r.get("concepto_id") for r in matriz.get("reserva", [])}
    if reservas & set(ids_c):
        h.add("D6-L1-10", "MAYOR", "reserva-repite-concepto-del-test", "matriz.json", "un concepto de reserva repite un concepto del test")
    return h


# ----------------------------------------------------------------------------------------------- textos congelados

def hash_textos(oferta_dir: Path) -> dict[str, str]:
    d6 = oferta_dir / "06-creativos"
    mapa = {}
    for rel in ("matriz.json", "copies.json"):
        mapa[f"06-creativos/{rel}"] = ve.hash_archivo(d6 / rel)
    guiones = d6 / "guiones"
    if guiones.is_dir():
        mapa["06-creativos/guiones"] = ve.hash_directorio(guiones)
    return mapa


def verificar_textos(oferta_dir: Path, qa_a: Path | None) -> tuple[dict, Hallazgos]:
    h = Hallazgos()
    actual = hash_textos(oferta_dir)
    resultado = {"hash_textos": ve.hash_objeto(actual), "entradas": actual}
    if qa_a:
        previo = ve.cargar_json(qa_a).get("entradas", {})
        for ruta, hh in actual.items():
            if ruta not in previo:
                h.add("D6-H01", PATRON_BLOQUEANTE, "texto-fuera-del-qa-a", ruta, "el informe QA-A no cubre este archivo")
            elif not ve.comparar_hash(previo[ruta], hh):
                h.add("D6-H01", PATRON_BLOQUEANTE, "texto-cambiado-tras-qa-a", ruta, "el texto cambió después de aprobarse en QA-A")
    return resultado, h


# ----------------------------------------------------------------------------------------------- assets y costos

def _dims_png(ruta: Path) -> tuple[int, int] | None:
    import struct
    cab = ruta.read_bytes()[:24]
    if cab[:8] != b"\x89PNG\r\n\x1a\n" or cab[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", cab[16:24])


def familias_de_font_face(textos: list[str]) -> set[str]:
    """Familias declaradas con ``@font-face`` en el HTML fuente de los estáticos (las WOFF2 que D5 autoaloja)."""
    familias: set[str] = set()
    for texto in textos:
        for bloque in RX_FONT_FACE.findall(texto):
            m = RX_FONT_FAMILY.search(bloque)
            if m:
                familias.add(m.group(1).strip())
    return familias


def validar_licencias_fuentes(d6: Path, html_fuente: list[str]) -> Hallazgos:
    """Cada familia cargada con ``@font-face`` en un estático tiene su licencia en ``licencias.json`` (SC-15, L1-09)."""
    h = Hallazgos()
    familias = familias_de_font_face(html_fuente)
    if not familias:
        return h
    ruta = d6 / "licencias.json"
    entradas = []
    if ruta.is_file():
        entradas = [x for x in ve.cargar_json(ruta).get("licencias", []) if x.get("tipo") == "fuente_tipografica"]
    for familia in sorted(familias):
        entrada = next((x for x in entradas if norm(familia) in norm(f"{x.get('nombre', '')} {x.get('familia', '')}")), None)
        if entrada is None:
            h.add("D6-L1-09", PATRON_BLOQUEANTE, "fuente-sin-licencia", "licencias.json", f"la familia «{familia}» (@font-face con las WOFF2 de D5) no tiene una entrada tipo fuente_tipografica en licencias.json")
        elif not (entrada.get("licencia") or entrada.get("url_licencia") or entrada.get("evidencia_ref")):
            h.add("D6-L1-09", "MAYOR", "fuente-licencia-sin-evidencia", "licencias.json", f"«{familia}»: la entrada no trae licencia, url_licencia ni evidencia_ref")
    return h


def validar_assets(raiz: Path, oferta_dir: Path) -> tuple[Hallazgos, int]:
    h = Hallazgos()
    d6 = oferta_dir / "06-creativos"
    ruta = d6 / "paquete.json"
    if not ruta.is_file():
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "falta-paquete", "paquete.json", "no existe 06-creativos/paquete.json")
        return h, 3
    paq = ve.cargar_json(ruta)
    costos_txt = (d6 / "costos.jsonl").read_text(encoding="utf-8") if (d6 / "costos.jsonl").is_file() else ""
    html_fuente = [p.read_text(encoding="utf-8", errors="replace") for p in (d6 / "assets" / "src").glob("*.html")] if (d6 / "assets" / "src").is_dir() else []
    suma_total = 0
    hay_creditos = False
    max_pieza_visto = 0
    for a in paq.get("anuncios", []):
        ad = a["ad_name"]
        suma_anuncio = 0
        for s in a.get("assets", []):
            archivo = d6 / s["archivo"]
            suma_anuncio += s["costo_creditos"]
            max_pieza_visto = max(max_pieza_visto, s["costo_creditos"])
            if not archivo.is_file():
                h.add("D6-L1-01", PATRON_BLOQUEANTE, "asset-inexistente", ad, f"no existe {s['archivo']}")
                continue
            if not ve.comparar_hash(s["sha256"], ve.hash_archivo(archivo)):
                h.add("D6-L1-01", PATRON_BLOQUEANTE, "asset-hash-no-coincide", ad, f"sha256 de {s['archivo']}")
            if archivo.suffix.lower() == ".png":
                dims = _dims_png(archivo)
                if dims is None:
                    h.add("D6-L1-01", PATRON_BLOQUEANTE, "png-invalido", ad, s["archivo"])
                elif dims != RATIO_DIMS.get(s["ratio"]):
                    h.add("D6-L1-01", "MAYOR", "dimensiones-no-corresponden-al-ratio", ad, f"{dims} para ratio {s['ratio']} (esperado {RATIO_DIMS.get(s['ratio'])})")
            if s["ia_generado"]:
                if not s["job_id"] or not s["modelo"]:
                    h.add("D6-L1-09", PATRON_BLOQUEANTE, "asset-sin-job-id", ad, f"{s['archivo']}: ia_generado sin job_id o modelo")
                elif f"job={s['job_id']}" not in costos_txt:
                    h.add("D6-L1-09", PATRON_BLOQUEANTE, "asset-sin-registro-de-costo", ad, f"job {s['job_id']} no está en costos.jsonl")
                if not s["licencia_ref"]:
                    h.add("D6-L1-09", PATRON_BLOQUEANTE, "asset-sin-licencia", ad, s["archivo"])
                if s["c2pa_final"] == "no" and not s["etiqueta_ia_visible"]:
                    h.add("D6-L1-09", PATRON_BLOQUEANTE, "c2pa-perdido-sin-etiqueta-visible", ad, s["archivo"])
            if s["costo_creditos"] > 0:
                hay_creditos = True
                if not s["job_id"]:
                    h.add("D6-L1-09", PATRON_BLOQUEANTE, "creditos-sin-job-id", ad, s["archivo"])
            if s["herramienta"].startswith(("playwright", "chrome")) and html_fuente and not any(ad in x for x in html_fuente):
                h.add("D6-L1-01", "MAYOR", "estatico-sin-html-fuente", ad, "no hay assets/src/*.html con ese ad_name")
        if suma_anuncio != a["costo_creditos"]:
            h.add("D6-C01", "MAYOR", "costo-del-anuncio-no-suma", ad, f"assets suman {suma_anuncio} != costo_creditos {a['costo_creditos']}")
        suma_total += a["costo_creditos"]
    if suma_total != paq.get("costo_total_creditos"):
        h.add("D6-C01", "MAYOR", "costo-total-no-suma", "paquete.json", f"anuncios suman {suma_total} != costo_total_creditos {paq.get('costo_total_creditos')}")
    h += validar_licencias_fuentes(d6, html_fuente)
    me = paq.get("politicas", {}).get("meta_enhancements", {})
    if me.get("generacion_texto") is not False or me.get("mejoras_creativas") is not False:
        h.add("D6-L1-10", PATRON_BLOQUEANTE, "meta-enhancements-activos", "paquete.json", "meta_enhancements debe ser false en ambos")
    codigo = 0
    if hay_creditos:
        try:
            lim = ve.cargar_yaml(raiz / "empresa" / "limites.yaml")
        except OSError:
            lim = {}
        tope_pieza, tope_oferta = lim.get("creditos_max_pieza"), lim.get("creditos_max_oferta")
        if tope_pieza is None or tope_oferta is None:
            h.add("D6-C01", PATRON_BLOQUEANTE, "topes-de-creditos-null", "limites.yaml", "creditos_max_pieza/oferta en null: nada puede haberse generado (código 5)")
            codigo = 5
        else:
            if max_pieza_visto > tope_pieza:
                h.add("D6-C01", PATRON_BLOQUEANTE, "pieza-sobre-el-tope", "paquete.json", f"{max_pieza_visto} > creditos_max_pieza {tope_pieza}")
            if suma_total > tope_oferta:
                h.add("D6-C01", PATRON_BLOQUEANTE, "oferta-sobre-el-tope", "paquete.json", f"{suma_total} > creditos_max_oferta {tope_oferta}")
    return h, codigo


def validar_paquete_esquema(oferta_dir: Path) -> Hallazgos:
    h = Hallazgos()
    ruta = oferta_dir / "06-creativos" / "paquete.json"
    if not ruta.is_file():
        return h
    for e in ve.errores_de_esquema("creativos", ve.cargar_json(ruta)):
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "paquete-fuera-del-esquema", ve.ruta_json(e) or "paquete.json", str(e.message)[:200])
    return h


# ----------------------------------------------------------------------------------------------- ranuras de la landing (encargo de D5)

RX_OPINION = re.compile(r"avatar|opini[oó]n|opinion|rese[nñ]a|testimon|review|recensione|opinie|recenzj|avis|bewertung", re.I)


def validar_ranuras(raiz: Path, oferta_dir: Path) -> tuple[Hallazgos, int]:
    """Comprueba ``06-creativos/ranuras.json`` (imágenes de ambiente e ilustración que D6 produce para D5) contra ``05-landing/assets.json``."""
    h = Hallazgos()
    d6 = oferta_dir / "06-creativos"
    ruta = d6 / "ranuras.json"
    if not ruta.is_file():
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "falta-ranuras-json", "06-creativos/ranuras.json", "no existe")
        return h, 3
    ranuras = ve.cargar_json(ruta).get("ranuras", [])
    slots = {s["slot_id"]: s for s in ve.cargar_json(oferta_dir / "05-landing" / "assets.json").get("slots", [])}
    costos_txt = (d6 / "costos.jsonl").read_text(encoding="utf-8") if (d6 / "costos.jsonl").is_file() else ""
    total, hay_creditos, max_pieza = 0, False, 0
    for r in ranuras:
        sid = r.get("slot_id", "?")
        slot = slots.get(sid)
        if slot is None:
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "ranura-inexistente-en-d5", sid, "el slot_id no está en 05-landing/assets.json")
            continue
        if RX_OPINION.search(f"{slot.get('proposito', '')} {slot.get('alt', '')} {slot.get('seccion', '')}") and slot.get("seccion") == "prueba":
            h.add("X1-P04", PATRON_BLOQUEANTE, "ranura-de-opinion-o-avatar", sid, "D6 no produce opiniones, avatares ni testimonios (se omiten; sustituto honesto: muestra, garantía, cifras verificables)")
        for campo in ("tipo", "ratio"):
            if r.get(campo) != slot.get(campo):
                h.add("D6-L1-01", PATRON_BLOQUEANTE, f"ranura-{campo}-distinto", sid, f"{r.get(campo)!r} != D5 {slot.get(campo)!r}")
        if not str(r.get("alt", "")).strip():
            h.add("D6-L1-06", "MAYOR", "ranura-sin-alt", sid, "falta texto alternativo en el idioma de la oferta")
        archivo = d6 / r.get("archivo", "")
        if not r.get("archivo") or not archivo.is_file():
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "ranura-sin-archivo", sid, str(r.get("archivo")))
            continue
        if not ve.comparar_hash(r.get("sha256", ""), ve.hash_archivo(archivo)):
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "ranura-hash-no-coincide", sid, r["archivo"])
        if archivo.stat().st_size > slot["peso_max_kb"] * 1024:
            h.add("D6-L1-01", "MAYOR", "ranura-sobre-el-peso", sid, f"{archivo.stat().st_size} bytes > peso_max_kb {slot['peso_max_kb']}")
        if archivo.suffix.lower() == ".png":
            dims = _dims_png(archivo)
            ancho_r, alto_r = (int(x) for x in slot["ratio"].split(":"))
            if dims is None:
                h.add("D6-L1-01", PATRON_BLOQUEANTE, "png-invalido", sid, r["archivo"])
            elif abs(dims[0] / dims[1] - ancho_r / alto_r) > 0.01 * ancho_r / alto_r:
                h.add("D6-L1-01", "MAYOR", "ranura-ratio-no-corresponde", sid, f"{dims} no es {slot['ratio']}")
        if r.get("origen") not in ("ia", "propio", "stock_licenciado"):
            h.add("D6-L1-09", PATRON_BLOQUEANTE, "ranura-origen-invalido", sid, f"origen {r.get('origen')!r} (ia | propio | stock_licenciado)")
        # productor (SC-5, LT-32/LT-56): D4 | D6 | dueno; D6 solo escribe las suyas. Campo aún sin contrato: opcional.
        productor = r.get("productor")
        if productor is not None and productor not in PRODUCTORES:
            h.add("D6-L1-01", PATRON_BLOQUEANTE, "ranura-productor-invalido", sid, f"productor {productor!r}: solo {' | '.join(PRODUCTORES)} (en ASCII; no html_png, captura_producto, higgsfield ni comprador_real)")
        elif productor not in (None, "D6") or slot.get("productor") not in (None, "D6"):
            h.add("D6-L1-01", "MAYOR", "ranura-de-otro-productor", sid, f"productor {productor!r} (D5 declara {slot.get('productor')!r}): D6 solo produce las ranuras cuyo productor es D6")
        if "etiqueta_ia" in r:
            h.add("D6-L1-09", "MAYOR", "campo-etiqueta-ia-obsoleto", sid, "el campo se llama etiqueta_ia_visible")
        if r.get("ia_generado") or r.get("origen") == "ia":
            if not r.get("job_id") or not r.get("modelo"):
                h.add("D6-L1-09", PATRON_BLOQUEANTE, "asset-sin-job-id", sid, "ranura generada con IA sin job_id o modelo")
            elif f"job={r['job_id']}" not in costos_txt:
                h.add("D6-L1-09", PATRON_BLOQUEANTE, "asset-sin-registro-de-costo", sid, f"job {r['job_id']} no está en costos.jsonl")
            if not r.get("licencia_ref"):
                h.add("D6-L1-09", PATRON_BLOQUEANTE, "asset-sin-licencia", sid, r["archivo"])
            if not r.get("etiqueta_ia_visible"):
                h.add("D6-L1-09", "MAYOR", "ranura-ia-sin-etiqueta-ia", sid, "declarar etiqueta_ia_visible según limites.politica_divulgacion_ia")
        elif r.get("origen") == "stock_licenciado" and not r.get("licencia_ref"):
            h.add("D6-L1-09", PATRON_BLOQUEANTE, "asset-sin-licencia", sid, r["archivo"])
        c = int(r.get("costo_creditos", 0))
        total += c
        max_pieza = max(max_pieza, c)
        hay_creditos = hay_creditos or c > 0
    codigo = 0
    if hay_creditos:
        try:
            lim = ve.cargar_yaml(raiz / "empresa" / "limites.yaml")
        except OSError:
            lim = {}
        tope_pieza, tope_oferta = lim.get("creditos_max_pieza"), lim.get("creditos_max_oferta")
        if tope_pieza is None or tope_oferta is None:
            h.add("D6-C01", PATRON_BLOQUEANTE, "topes-de-creditos-null", "limites.yaml", "creditos_max_pieza/oferta en null (código 5)")
            codigo = 5
        else:
            if max_pieza > tope_pieza:
                h.add("D6-C01", PATRON_BLOQUEANTE, "pieza-sobre-el-tope", "ranuras.json", f"{max_pieza} > creditos_max_pieza {tope_pieza}")
            paq = d6 / "paquete.json"
            previo = ve.cargar_json(paq).get("costo_total_creditos", 0) if paq.is_file() else 0
            if total + previo > tope_oferta:
                h.add("D6-C01", PATRON_BLOQUEANTE, "oferta-sobre-el-tope", "ranuras.json", f"{total + previo} > creditos_max_oferta {tope_oferta}")
    return h, codigo


# ----------------------------------------------------------------------------------------------- evals

def validar_evals(raiz: Path) -> Hallazgos:
    h = Hallazgos()
    base = SKILL_DIR / "evals"
    dorados, sembrados = sorted((base / "dorados").glob("*.json")), sorted((base / "sembrados").glob("*.json"))
    maker = [p for p in dorados if p.name.startswith("e")]
    qa_pass = [p for p in dorados if p.name.startswith("qa-pass")]
    if len(maker) < 10:
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "faltan-casos-del-maker", "evals/dorados", f"{len(maker)} < 10 (spec §10.5)")
    for p in maker:
        c = ve.cargar_json(p)
        for k in ("caso_id", "titulo", "tipo", "entrada", "salida_esperada", "aprobacion"):
            if k not in c:
                h.add("D6-L1-01", "MAYOR", "caso-sin-campo", p.name, f"falta {k}")
    piezas = []
    for p in qa_pass:
        piezas += ve.cargar_json(p).get("piezas", [])
    if len(piezas) < 10:
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "faltan-dorados-del-qa", "evals/dorados", f"{len(piezas)} < 10 (Anexo B)")
    for x in piezas:
        for k in ("pieza_id", "locale", "macro_nicho", "nivel_oferta", "texto", "veredicto_esperado"):
            if k not in x:
                h.add("D6-L1-01", "MAYOR", "dorado-sin-campo", str(x.get("pieza_id", "?")), f"falta {k}")
        if x.get("veredicto_esperado") != "PASS":
            h.add("D6-L1-01", "MAYOR", "dorado-no-es-pass", str(x.get("pieza_id", "?")), "un dorado debe esperar PASS")
    variantes, locales, bloq = [], set(), 0
    for p in sembrados:
        for v in ve.cargar_json(p).get("variantes", []):
            variantes.append(v)
            locales.add(v.get("locale"))
            for k in ("variante_id", "locale", "macro_nicho", "nivel_oferta", "pieza", "defecto", "check_id_esperado", "severidad_esperada", "patron_clave_esperado", "veredicto_qa_esperado"):
                if k not in v:
                    h.add("D6-L1-01", "MAYOR", "sembrado-sin-campo", str(v.get("variante_id", "?")), f"falta {k}")
            if v.get("check_id_esperado") not in CHECKS_CONOCIDOS:
                h.add("D6-L1-01", "MAYOR", "check-id-desconocido", str(v.get("variante_id", "?")), str(v.get("check_id_esperado")))
            if v.get("severidad_esperada") == PATRON_BLOQUEANTE:
                bloq += 1
    try:
        minimo = param(raiz, "creativos", "calibracion_bloqueantes_sembrados_min")
    except KeyError:
        minimo = 20
    if bloq < minimo:
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "faltan-sembrados-bloqueantes", "evals/sembrados", f"{bloq} bloqueantes < creativos.calibracion_bloqueantes_sembrados_min ({minimo})")
    if len({x for x in locales if x}) < 4:
        h.add("D6-L1-01", PATRON_BLOQUEANTE, "sembrados-en-menos-de-4-idiomas", "evals/sembrados", f"{sorted(x for x in locales if x)}")
    ids = [v.get("variante_id") for v in variantes]
    if len(set(ids)) != len(ids):
        h.add("D6-L1-01", "MAYOR", "variante-id-duplicado", "evals/sembrados", "variante_id repetido")
    return h


# ----------------------------------------------------------------------------------------------- CLI

def _salida(h: Hallazgos, extra: dict, como_json: bool, codigo_forzado: int = 0) -> int:
    codigo = codigo_forzado or (3 if h.graves() else 0)
    if como_json:
        print(json.dumps({"ok": codigo == 0, "codigo": codigo, "hallazgos": list(h), **extra}, ensure_ascii=False, sort_keys=True))
    else:
        for k, v in extra.items():
            print(f"{k}: {v}")
        for x in h:
            print(f"[{x['severidad']}] {x['check_id']} {x['patron_clave']} · {x['ref']}: {x['detalle']}")
        print(f"hallazgos={len(h)} graves={len(h.graves())} -> {'OK' if codigo == 0 else f'FALLA ({codigo})'}")
    return codigo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validaciones L1 deterministas de D6 (solo lectura)")
    p.add_argument("orden", choices=("nmax", "matriz", "textos", "assets", "ranuras", "todo", "evals"))
    p.add_argument("--oferta-dir", type=Path)
    p.add_argument("--raiz", type=Path, default=RAIZ_POR_DEFECTO)
    p.add_argument("--qa-a", type=Path)
    p.add_argument("--k", type=int, default=3, help="factor de n_anuncios_max (spec §3.4: 3)")
    p.add_argument("--json", action="store_true")
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if a.orden != "evals" and not a.oferta_dir:
        print("ERROR: falta --oferta-dir", file=sys.stderr)
        return 2
    raiz = a.raiz
    try:
        if a.orden == "nmax":
            r = calcular_nmax(raiz, a.oferta_dir, a.k)
            h = Hallazgos()
            if not r["genera"]:
                h.add("D6-N01", PATRON_BLOQUEANTE, "no-generar", "economia.json",
                      f"n_anuncios_max={r['n_anuncios_max']} < campana.n_anuncios_min={r['n_anuncios_min']}: subir presupuesto, bajar cpa_obj o rediseñar")
            return _salida(h, r, a.json)
        if a.orden == "matriz":
            return _salida(validar_matriz(raiz, a.oferta_dir), {}, a.json)
        if a.orden == "textos":
            r, h = verificar_textos(a.oferta_dir, a.qa_a)
            return _salida(h, r, a.json)
        if a.orden == "assets":
            h, codigo = validar_assets(raiz, a.oferta_dir)
            return _salida(h, {}, a.json, codigo)
        if a.orden == "ranuras":
            h, codigo = validar_ranuras(raiz, a.oferta_dir)
            return _salida(h, {}, a.json, codigo)
        if a.orden == "evals":
            return _salida(validar_evals(raiz), {}, a.json)
        h = validar_matriz(raiz, a.oferta_dir)
        h += validar_paquete_esquema(a.oferta_dir)
        ha, codigo = validar_assets(raiz, a.oferta_dir)
        h += ha
        r, ht = verificar_textos(a.oferta_dir, a.qa_a)
        h += ht
        if (a.oferta_dir / "06-creativos" / "ranuras.json").is_file():
            hr, codigo_r = validar_ranuras(raiz, a.oferta_dir)
            h += hr
            codigo = codigo or codigo_r
        return _salida(h, {"hash_textos": r["hash_textos"]}, a.json, codigo)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR de entrada: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
