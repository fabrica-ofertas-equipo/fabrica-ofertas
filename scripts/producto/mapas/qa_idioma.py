"""Capas automáticas de QA de idioma de los mapas (J11: sin revisor nativo humano; el idioma se asegura con capas).

Capas (cada una devuelve hallazgos ``{codigo, severidad, campo, mensaje}``; las que no se pueden ejecutar lo dicen: NUNCA se dan por pasadas):

1. ``capa_ortografia``    corrector del sistema (macOS NSSpellChecker, ``pl`` y ``en_GB``) sobre todas las palabras de los textos.
2. ``capa_nivel``         consistencia de nivel: longitud de frase por nivel, palabras largas en A1/A2, palabras elementales en C1/C2.
3. ``capa_duplicados``    palabras repetidas dentro del nivel (módulo ``duplicados``).
4. ``capa_listas``        falsos amigos, marcas, sensibles, promesas de resultado, jerga (``datos_qa``).
5. ``retraduccion``       retraducción ciega PL→EN por un agente de contexto limpio y comparación (``preparar_retraduccion`` / ``comparar_retraduccion``).
6. (revisión ciega por un segundo agente: ``revision_ciega.py``).

Límites honestos: un corrector no detecta una palabra bien escrita pero equivocada; las listas son cortas; la retraducción y la revisión
ciega las hace un modelo de la misma familia (errores correlacionados posibles). Ninguna capa certifica un idioma.

CLI::

    .venv/bin/python -m scripts.producto.mapas.qa_idioma CARPETA_DE_MAPAS [--excepciones excepciones_ortografia.json] [--json]
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts.producto.mapas import datos_qa as D
from scripts.producto.mapas import duplicados
from scripts.producto.mapas.esquema import NIVELES, _contiene_forma, cargar_dir, hallazgo
from scripts.producto.mapas.ocr import compilar_swift

_RX_TOKEN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")


# ── utilidades de texto ──────────────────────────────────────────────────────────────────────────────────────────────────────
def campos_por_idioma(mapa: Mapping[str, Any]) -> dict[str, list[tuple[str, str]]]:
    """``{"pl": [(campo, texto)], "en": [...]}`` con TODOS los textos del mapa separados por idioma."""
    pl: list[tuple[str, str]] = []
    en: list[tuple[str, str]] = []

    def a(lista, campo, v):
        if isinstance(v, str):
            lista.append((campo, v))

    a(pl, "tema.pl", mapa.get("tema", {}).get("pl"))
    a(en, "centro.en", mapa.get("centro", {}).get("en"))
    a(pl, "centro.pl", mapa.get("centro", {}).get("pl"))
    for i, r in enumerate(mapa.get("ramas", []), 1):
        a(en, f"ramas[{i}].grupo.en", r.get("grupo", {}).get("en"))
        a(pl, f"ramas[{i}].grupo.pl", r.get("grupo", {}).get("pl"))
        for j, p in enumerate(r.get("palabras", []), 1):
            c = f"ramas[{i}].palabras[{j}]"
            a(en, c + ".en", p.get("en"))
            a(pl, c + ".pl", p.get("pl"))
            a(en, c + ".pista", p.get("pista"))
            a(pl, c + ".uwaga_pl", p.get("uwaga_pl"))
    for i, f in enumerate(mapa.get("frases", []), 1):
        a(en, f"frases[{i}].en", f.get("en"))
        a(pl, f"frases[{i}].pl", f.get("pl"))
    for i, v in enumerate(mapa.get("powiedz_na_glos", []), 1):
        a(en, f"powiedz_na_glos[{i}].en", v.get("en"))
        a(pl, f"powiedz_na_glos[{i}].pl", v.get("pl"))
    ej = mapa.get("ejercicios", {})
    for i, c in enumerate(ej.get("completar", []), 1):
        a(en, f"completar[{i}].texto", (c.get("texto") or "").replace("___", " "))
        for o in c.get("opciones", []):
            a(en, f"completar[{i}].opciones", o)
    for i, u in enumerate(ej.get("unir", []), 1):
        a(en, f"unir[{i}].en", u.get("en"))
        a(pl, f"unir[{i}].pl", u.get("pl"))
    for i, t in enumerate(ej.get("traducir", []), 1):
        a(pl, f"traducir[{i}].pl", t.get("pl"))
        a(en, f"traducir[{i}].respuesta", t.get("respuesta"))
    a(pl, "siguiente_paso.texto_pl", mapa.get("siguiente_paso", {}).get("texto_pl"))
    return {"pl": pl, "en": en}


def _tokens(texto: str) -> list[str]:
    out = []
    for t in _RX_TOKEN.findall(unicodedata.normalize("NFC", texto)):
        t = re.sub(r"['’]s$", "", t)
        out.extend(x for x in t.split("-") if x)
    return out


# ── capa 1: ortografía ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def capa_ortografia(mapas: Sequence[Mapping[str, Any]], *, excepciones: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, Any]:
    """Corrector del sistema. Devuelve ``{ejecutada, hallazgos, detalle}``; sin Swift o sin diccionario ``ejecutada`` es False."""
    exc = {k: {w.casefold(): m for w, m in v.items()} for k, v in (excepciones or {}).items()}
    try:
        binario = compilar_swift("ortografia")
    except RuntimeError as e:
        return {"ejecutada": False, "motivo": str(e), "hallazgos": [], "detalle": {}}
    hallazgos: list[dict[str, str]] = []
    detalle: dict[str, Any] = {}
    for idioma, clave in (("pl", "pl"), ("en_GB", "en")):
        donde: dict[str, list[str]] = {}
        for m in mapas:
            for campo, texto in campos_por_idioma(m)[clave]:
                for t in _tokens(texto):
                    if len(t) > 1 or t.casefold() in ("a", "i"):
                        donde.setdefault(t, []).append(f"{m['mapa_id']}:{campo}")
        palabras = sorted(donde)
        p = subprocess.run([str(binario)], input=json.dumps({"idioma": idioma, "palabras": palabras}), capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            return {"ejecutada": False, "motivo": f"ortografia falló: {p.stderr[-200:]}", "hallazgos": [], "detalle": detalle}
        r = json.loads(p.stdout)
        detalle[clave] = {"idioma": r["idioma"], "disponible": r["disponible"], "palabras_unicas": len(palabras), "mal": len(r["mal"])}
        if not r["disponible"]:
            return {"ejecutada": False, "motivo": f"el sistema no tiene diccionario de {idioma}", "hallazgos": [], "detalle": detalle}
        for x in r["mal"]:
            w = x["palabra"]
            if w.casefold() in exc.get(clave, {}):
                continue
            hallazgos.append(hallazgo("ortografia-" + clave, "MAYOR", donde[w][0], f"«{w}» no está en el diccionario {idioma} (sugerencias: {', '.join(x['sugerencias']) or '—'}); aparece en {len(donde[w])} sitio(s)"))
    return {"ejecutada": True, "hallazgos": hallazgos, "detalle": detalle}


# ── capa 2: consistencia de nivel ──────────────────────────────────────────────────────────────────────────────────────────────────────
def capa_nivel(mapa: Mapping[str, Any]) -> list[dict[str, str]]:
    hs: list[dict[str, str]] = []
    nv = mapa.get("nivel")
    if nv not in D.LONGITUD_FRASE:
        return hs
    mx, mn, md = D.LONGITUD_FRASE[nv]
    largos = []
    for i, f in enumerate(mapa.get("frases", []), 1):
        n = len(re.findall(r"[\w'’]+", f.get("en", "")))
        largos.append(n)
        if n > mx:
            hs.append(hallazgo("nivel-frase-larga", "MAYOR", f"frases[{i}].en", f"{n} palabras; para {nv} el máximo es {mx}"))
    if largos:
        media = sum(largos) / len(largos)
        if media > md:
            hs.append(hallazgo("nivel-media-alta", "MENOR", "frases", f"media de {media:.1f} palabras por frase; para {nv} lo esperable es ≤ {md}"))
        if media < mn:
            hs.append(hallazgo("nivel-media-baja", "MENOR", "frases", f"media de {media:.1f} palabras por frase; para {nv} lo esperable es ≥ {mn}"))
    for r in mapa.get("ramas", []):
        for p in r.get("palabras", []):
            en = p.get("en", "")
            if nv in D.LARGO_MAX_PALABRA and len(en) > D.LARGO_MAX_PALABRA[nv]:
                hs.append(hallazgo("nivel-palabra-larga", "MAYOR", p.get("en", "?"), f"«{en}» ({len(en)} letras) es probablemente de un nivel superior a {nv}"))
            if nv in ("C1", "C2") and en.casefold() in D.ELEMENTALES:
                hs.append(hallazgo("nivel-palabra-elemental", "MAYOR", p.get("en", "?"), f"«{en}» es una palabra elemental (A1/A2): no encaja como vocabulario de {nv}"))
    return hs


# ── capa 4: listas ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _buscar(lista: Iterable[str], texto: str) -> list[str]:
    t = texto.casefold()
    return [x for x in lista if re.search(r"(?<!\w)" + re.escape(x.casefold()) + (r"" if x.endswith(("-", " ")) else r"(?!\w)"), t)]


def capa_listas(mapa: Mapping[str, Any], *, excepciones_sensibles: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    hs: list[dict[str, str]] = []
    exc = {k.casefold() for k in (excepciones_sensibles or {})}
    campos = campos_por_idioma(mapa)
    todos = campos["en"] + campos["pl"]
    for campo, texto in todos:
        for x in _buscar(D.MARCAS, texto):
            hs.append(hallazgo("marca", "BLOQUEANTE", campo, f"nombre comercial «{x}»: no hay marcas en el producto"))
        for x in _buscar(D.MARCAS_DUDOSAS, texto):
            hs.append(hallazgo("marca-dudosa", "MAYOR", campo, f"«{x}» es un nombre de marca de uso común: sustitúyelo por la palabra genérica"))
        for x in D.MARCAS_AMBIGUAS:
            if re.search(r"(?<![.!?]\s)(?<!^)\b" + x + r"\b", texto):
                hs.append(hallazgo("marca-ambigua", "MAYOR", campo, f"«{x}» con mayúscula en medio de la frase puede ser la marca"))
        for x in _buscar(D.SENSIBLES_BLOQUEANTES, texto):
            hs.append(hallazgo("sensible-bloqueante", "BLOQUEANTE", campo, f"contenido no admitido: «{x}»"))
        for x in _buscar(D.SENSIBLES_REVISAR, texto):
            if x.casefold() not in exc:
                hs.append(hallazgo("sensible-a-revisar", "MAYOR", campo, f"«{x}»: vocabulario sensible; confirma que el uso es neutro o añade una excepción con motivo"))
        for x in _buscar(D.JERGA_PL, texto) if (campo, texto) in campos["pl"] else _buscar(D.JERGA_EN, texto):
            hs.append(hallazgo("jerga", "MAYOR", campo, f"jerga o vulgarismo «{x}»: el registro del producto es neutro"))
    for campo, texto in todos:
        for rx in D.PROMESAS_PL + D.PROMESAS_EN:
            if re.search(rx, texto, re.I):
                hs.append(hallazgo("promesa-de-resultado", "BLOQUEANTE", campo, f"promesa, plazo o urgencia prohibidos (patrón {rx!r}): «lo anunciado = lo entregado»"))
    # falsos amigos
    fa = {x["en"]: x for x in D.FALSOS_AMIGOS}
    for i, r in enumerate(mapa.get("ramas", []), 1):
        for j, p in enumerate(r.get("palabras", []), 1):
            e = fa.get(str(p.get("en", "")).casefold())
            if not e:
                continue
            c = f"ramas[{i}].palabras[{j}]"
            if str(p.get("pl", "")).casefold() in {x.casefold() for x in e["falso"]}:
                hs.append(hallazgo("falso-amigo-como-traduccion", "BLOQUEANTE", c, f"«{p['en']}» no se traduce «{p['pl']}» (falso amigo); lo correcto: {', '.join(e['correcto'])}"))
            if e["marcar"] and not p.get("uwaga_pl"):
                hs.append(hallazgo("falso-amigo-sin-nota", "MAYOR", c, f"«{p['en']}» es un falso amigo conocido: añade uwaga_pl, p. ej. «{e['nota_pl']}»"))
    for i, f in enumerate(mapa.get("frases", []), 1):
        for e in D.FALSOS_AMIGOS:
            if _contiene_forma(f.get("en", ""), e["en"]):
                for raiz in e["raiz_pl"]:
                    if re.search(r"(?<!\w)" + re.escape(raiz), f.get("pl", "").casefold()):
                        hs.append(hallazgo("falso-amigo-en-frase", "MAYOR", f"frases[{i}].pl", f"la frase inglesa usa «{e['en']}» y la polaca contiene «{raiz}…»: posible calco (correcto: {', '.join(e['correcto'])})"))
                        break
    return hs


# ── capa 5: retraducción ciega ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def elementos_retraducibles(mapa: Mapping[str, Any]) -> list[dict[str, str]]:
    """Frases, líneas para decir en voz alta y pares de ejercicio con su original inglés."""
    out = []
    for i, f in enumerate(mapa.get("frases", []), 1):
        out.append({"id": f"{mapa['mapa_id']}#frase{i}", "pl": f["pl"], "en": f["en"], "tipo": "frase"})
    for i, v in enumerate(mapa.get("powiedz_na_glos", []), 1):
        out.append({"id": f"{mapa['mapa_id']}#voz{i}", "pl": v["pl"], "en": v["en"], "tipo": "voz"})
    for i, t in enumerate(mapa.get("ejercicios", {}).get("traducir", []), 1):
        out.append({"id": f"{mapa['mapa_id']}#trad{i}", "pl": t["pl"], "en": t["respuesta"], "tipo": "traducir"})
    return out


def preparar_retraduccion(mapas: Sequence[Mapping[str, Any]], *, porcentaje: int = 100, semilla: str = "slowomapa") -> dict[str, Any]:
    """Archivo CIEGO (solo el polaco) para el retraductor y archivo secreto con los originales. ``porcentaje`` = muestra por mapa."""
    items = []
    for m in mapas:
        for e in elementos_retraducibles(m):
            h = int(hashlib.sha256((semilla + e["id"]).encode()).hexdigest(), 16) % 100
            if h < porcentaje:
                items.append(e)
    palabras = [{"id": f"{m['mapa_id']}#pal{i}", "pl": p["pl"], "en": p["en"]} for m in mapas for i, p in enumerate([p for r in m.get("ramas", []) for p in r.get("palabras", [])], 1)]
    return {
        "ciego": {"instruccion": "Traduce al inglés cada texto polaco. Devuelve SOLO JSON {\"traducciones\": {\"<id>\": \"<inglés>\"}}. Para las palabras sueltas devuelve el equivalente inglés más habitual (una o dos opciones separadas por «/»). No corrijas ni comentes el polaco; si un texto es ambiguo o incorrecto en polaco, tradúcelo literalmente y añade «[?]» al final.",
                  "frases": [{"id": e["id"], "pl": e["pl"]} for e in items], "palabras": [{"id": p["id"], "pl": p["pl"]} for p in palabras]},
        "secreto": {"frases": {e["id"]: e["en"] for e in items}, "palabras": {p["id"]: p["en"] for p in palabras}},
    }


_PARADAS = set("a an the to of in on at is are was were be been am it its this that these those and or but for with as by from i you he she we they my your his her our their do does did".split())


def _norm_en(t: str) -> list[str]:
    t = unicodedata.normalize("NFC", t).casefold().replace("’", "'")
    t = re.sub(r"n't\b", " not", t)
    return [w for w in re.findall(r"[a-z]+", t)]


def _raiz(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)]
    return w


def similitud_en(a: str, b: str) -> float:
    """0..1: mezcla de orden (SequenceMatcher) y de contenido (Jaccard de raíces sin palabras vacías). Es un DISPARADOR, no un veredicto."""
    ta, tb = _norm_en(a), _norm_en(b)
    seq = difflib.SequenceMatcher(None, ta, tb).ratio()
    ca, cb = {_raiz(w) for w in ta if w not in _PARADAS}, {_raiz(w) for w in tb if w not in _PARADAS}
    jac = len(ca & cb) / len(ca | cb) if (ca | cb) else 1.0
    return round(0.5 * seq + 0.5 * jac, 3)


def comparar_retraduccion(secreto: Mapping[str, Any], respuesta: Mapping[str, Any], *, umbral: float = 0.6) -> dict[str, Any]:
    """Compara lo que devolvió el retraductor con los originales. ``discrepancias`` = lo que hay que adjudicar (no son errores probados)."""
    trad = respuesta.get("traducciones", respuesta)
    disc, sin_resp, ok = [], [], 0
    for id_, original in secreto["frases"].items():
        t = trad.get(id_)
        if t is None:
            sin_resp.append(id_)
            continue
        s = similitud_en(original, t)
        if s >= umbral and "[?]" not in t:
            ok += 1
        else:
            disc.append({"id": id_, "original_en": original, "retraduccion": t, "similitud": s, "marca_?": "[?]" in t})
    pal_disc = []
    for id_, esperado in secreto["palabras"].items():
        t = trad.get(id_)
        if t is None:
            sin_resp.append(id_)
            continue
        opciones = {_raiz(x.strip().casefold()) for x in re.split(r"[/;,]", str(t)) if x.strip()}
        if _raiz(esperado.casefold()) not in opciones and not any(_raiz(esperado.casefold()) in o or o in _raiz(esperado.casefold()) for o in opciones if len(o) > 3):
            pal_disc.append({"id": id_, "esperado": esperado, "retraduccion": t})
    n_f = len(secreto["frases"])
    return {"frases": n_f, "frases_ok": ok, "tasa_frases_ok": round(ok / n_f, 3) if n_f else None, "discrepancias_frases": disc,
            "palabras": len(secreto["palabras"]), "discrepancias_palabras": pal_disc, "sin_respuesta": sin_resp, "umbral": umbral}


# ── orquestación ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def ejecutar_capas(mapas: Sequence[Mapping[str, Any]], *, excepciones: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Capas 1-4 sobre un lote. Devuelve ``{por_mapa: {id: hallazgos}, lote: hallazgos, ortografia: {...}}``."""
    exc = excepciones or {}
    orto = capa_ortografia(mapas, excepciones={"pl": exc.get("ortografia_pl", {}), "en": exc.get("ortografia_en", {})})
    por_mapa: dict[str, list[dict[str, str]]] = {}
    for m in mapas:
        por_mapa[m["mapa_id"]] = capa_nivel(m) + capa_listas(m, excepciones_sensibles=exc.get("sensibles", {}))
    for h in orto["hallazgos"]:
        por_mapa.setdefault(h["campo"].split(":")[0], []).append(h)
    return {"por_mapa": por_mapa, "lote": duplicados.informe(mapas), "ortografia": {k: v for k, v in orto.items() if k != "hallazgos"}}


def hay_bloqueo(res: Mapping[str, Any]) -> bool:
    todos = [h for hs in res["por_mapa"].values() for h in hs] + list(res["lote"])
    return any(h["severidad"] in ("BLOQUEANTE", "MAYOR") for h in todos) or not res["ortografia"].get("ejecutada", False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.mapas.qa_idioma")
    ap.add_argument("mapas")
    ap.add_argument("--excepciones")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    mapas = [m for _, m in cargar_dir(a.mapas)]
    exc = json.loads(Path(a.excepciones).read_text(encoding="utf-8")) if a.excepciones else {}
    res = ejecutar_capas(mapas, excepciones=exc)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for mid, hs in sorted(res["por_mapa"].items()):
            for h in hs:
                print(f"[{h['severidad']}] {mid} · {h['codigo']} · {h['campo']}: {h['mensaje']}")
        for h in res["lote"]:
            print(f"[{h['severidad']}] LOTE · {h['codigo']}: {h['mensaje']}")
        print("ortografía:", json.dumps(res["ortografia"], ensure_ascii=False))
    return 1 if hay_bloqueo(res) else 0


if __name__ == "__main__":
    sys.exit(main())
