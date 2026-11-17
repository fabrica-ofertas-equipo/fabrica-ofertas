"""Esquema de un mapa de vocabulario de Słowomapa y su validador propio (solo biblioteca estándar).

Un mapa = una hoja A4 = una sesión de ~10 min. El JSON de un mapa es la FUENTE DE VERDAD: el PDF y el PNG se generan de él
(``render.py``); nada se maqueta a mano. Forma (``schema_version`` 1.0.0)::

    {
      "schema_version": "1.0.0",
      "mapa_id": "a1-001-food",            # <nivel>-<nnn>-<slug del tema_en>; sale del temario
      "nivel": "A1", "numero": 1,           # numero = posición en la ruta del nivel (1..70/80/90/100/90/90)
      "tema": {"en": "Food", "pl": "Jedzenie"},
      "centro": {"en": "food", "pl": "jedzenie"},
      "ramas": [                             # 6 a 10 ramas = grupos semánticos
        {"grupo": {"en": "Meals", "pl": "posiłki"},
         "palabras": [                       # 1 o 2 palabras por rama (8 a 12 en total)
           {"en": "lunch", "pl": "obiad", "pista": "at noon", "uwaga_pl": "opcional: trampa o falso amigo"}]}],
      "frases": [                            # 4 o 5; TODAS las palabras del mapa aparecen en alguna
        {"en": "We have lunch at one.", "pl": "Jemy obiad o pierwszej.",
         "usa": [{"en": "lunch", "forma_en": "lunch", "forma_pl": "obiad"}]}],
      "powiedz_na_glos": [{"en": "I am hungry.", "pl": "Jestem głodny."}],   # 3 o 4 líneas
      "ejercicios": {
        "completar": [{"texto": "I ___ water.", "opciones": ["drink", "eat"], "respuesta": "drink"}],   # 3
        "unir": [{"en": "lunch", "pl": "obiad"}],                                                      # 4 pares (palabras del mapa)
        "traducir": [{"pl": "Jestem głodny.", "respuesta": "I am hungry."}]                            # 2 (PL -> EN)
      },
      "siguiente_paso": {"mapa_id": "a1-002-family", "texto_pl": "Rodzina: słowa o ludziach z Twojego domu."}
    }

Contrato de calidad (lo que hace BLOQUEANTE, MAYOR o MENOR cada comprobación): ``validar_mapa``. Esto valida FORMA y reglas
deterministas; **no** certifica que una traducción sea correcta (eso es de ``qa_idioma`` + la revisión ciega).

CLI::

    .venv/bin/python -m scripts.producto.mapas.esquema MAPA.json [MAPA2.json ...] [--temario temario.json] [--json]

Salida: 0 sin BLOQUEANTE ni MAYOR · 1 con hallazgos · 2 uso.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION_ESQUEMA = "1.0.0"
NIVELES = ("A1", "A2", "B1", "B2", "C1", "C2")
REPARTO = {"A1": 70, "A2": 80, "B1": 90, "B2": 100, "C1": 90, "C2": 90}
TOTAL_MAPAS = sum(REPARTO.values())

# Rangos y longitudes (calibrados con la plantilla A4: ver render.py). Cualquier cambio exige volver a mirar el PDF.
RAMAS_MIN, RAMAS_MAX = 6, 10
PALABRAS_POR_RAMA_MAX = 2
PALABRAS_MIN, PALABRAS_MAX = 8, 12
FRASES_MIN, FRASES_MAX = 4, 5
VOZ_MIN, VOZ_MAX = 3, 4
N_COMPLETAR, N_UNIR, N_TRADUCIR = 3, 4, 2
PALABRAS_VISIBLES_MAX = 450  # oferta.json#vehiculo.palabras_max
PALABRAS_FIJAS_UI = 32  # rótulos fijos de la hoja («Zdania», «Powiedz na głos»…): se suman al presupuesto
L_EN_PALABRA, L_PL_PALABRA, L_PAR_TARJETA = 22, 25, 60  # caracteres (el par se pone en 1 o 2 líneas según su ancho: ver render.py)
L_PISTA, L_UWAGA, L_GRUPO_EN, L_GRUPO_PL = 34, 70, 24, 24
L_FRASE_EN, L_FRASE_PL, L_VOZ = 100, 120, 80
L_COMPLETAR, L_NEXT = 80, 100

_PL_LETRAS = "ąćęłńóśźż"
_RX_ID = re.compile(r"^(a1|a2|b1|b2|c1|c2)-(\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*$")
_RX_EN_PALABRA = re.compile(r"^[a-z](?:[a-z'’\- ]*[a-z])?$")
_RX_PL_PALABRA = re.compile(r"^[a-ząćęłńóśźż](?:[a-ząćęłńóśźż'’\- ]*[a-ząćęłńóśźż])?$")
_RX_MARCAS = re.compile(r"\[(?:VERIFICAR|SUPUESTO|PENDIENTE|TODO|PR[ÁA]CTICA|HIP[ÓO]TESIS)[^\]]*\]|lorem ipsum|\bTODO\b|\bXXX\b|\?\?\?", re.I)
_RX_PROHIBIDOS_CHARS = re.compile(r"[<>{}\[\]\\|`]")
_RX_ETIMOLOGIA = re.compile(
    r"etymolog|etymol\.|pochodzi (?:od|z)|wywodzi si|z łaciny|z greki|z francuskiego|z niemieckiego|"
    r"derives? from|comes? from|from latin|from greek|from french|origin(?:ates)?\b|originally|literally means|dosłownie",
    re.I,
)
_RX_BLANK = re.compile(r"___")
_RX_FIN_FRASE = re.compile(r"[.?!]$")


def hallazgo(codigo: str, severidad: str, campo: str, mensaje: str) -> dict[str, str]:
    return {"codigo": codigo, "severidad": severidad, "campo": campo, "mensaje": mensaje}


def _es_txt(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _norm(t: str) -> str:
    return unicodedata.normalize("NFC", t).strip().casefold()


def _contiene_forma(texto: str, forma: str) -> bool:
    """¿``forma`` aparece en ``texto`` como palabra(s) completa(s)? (sin distinguir mayúsculas; Unicode)."""
    if not forma:
        return False
    return re.search(r"(?<!\w)" + re.escape(forma.casefold()) + r"(?!\w)", texto.casefold()) is not None


_VOCAL_SIN_SONIDO = ("uni", "use", "usu", "uti", "ura", "eu", "one", "once", "ubi")
_CONSONANTE_CON_SONIDO_VOCAL = ("hour", "honest", "honour", "honor", "heir")


def sonido_vocal(palabra: str) -> bool:
    """¿Empieza por sonido vocálico? (heurística para el artículo «a»/«an»; cubre las excepciones más comunes)."""
    w = palabra.strip().casefold()
    if w.startswith(_CONSONANTE_CON_SONIDO_VOCAL):
        return True
    if w.startswith(_VOCAL_SIN_SONIDO):
        return False
    return w[:1] in "aeiou"


def articulo_previo(texto: str) -> str | None:
    """«a» o «an» justo antes del hueco ``___`` (o None)."""
    m = re.search(r"\b(an?)\s+___", texto, re.I)
    return m.group(1).casefold() if m else None


def _tiene_diacritico_pl(t: str) -> bool:
    return any(ch in _PL_LETRAS for ch in t.casefold())


def _higiene(add, campo: str, texto: Any, *, idioma: str | None = None) -> bool:
    """Reglas de higiene de cualquier texto visible. Devuelve False si no es una cadena usable."""
    if not _es_txt(texto):
        add("texto-vacio", "BLOQUEANTE", campo, "falta el texto o está vacío")
        return False
    if texto != texto.strip():
        add("espacios-extremos", "MENOR", campo, "espacios al principio o al final")
    if "  " in texto or "\t" in texto or "\n" in texto:
        add("espacios-dobles", "MENOR", campo, "espacios dobles, tabuladores o saltos de línea dentro del texto")
    if unicodedata.normalize("NFC", texto) != texto:
        add("unicode-no-nfc", "MAYOR", campo, "el texto no está normalizado en NFC (diacríticos descompuestos)")
    if any(unicodedata.category(c) in ("Cc", "Cf", "Co", "Cs") and c not in ("\n",) for c in texto):
        add("caracter-de-control", "BLOQUEANTE", campo, "carácter de control, invisible o de uso privado")
    if any(unicodedata.category(c) == "So" for c in texto):
        add("simbolo-o-emoji", "MAYOR", campo, "símbolo o emoji: no se admiten en la hoja")
    if _RX_PROHIBIDOS_CHARS.search(texto):
        add("caracter-prohibido", "MAYOR", campo, "contiene < > { } [ ] \\ | o comilla invertida")
    if _RX_MARCAS.search(texto):
        add("marca-de-trabajo", "BLOQUEANTE", campo, "marca de trabajo o relleno en el texto final")
    if _RX_ETIMOLOGIA.search(texto):
        add("etimologia", "BLOQUEANTE", campo, "no se publican etimologías ni orígenes de palabras (no hay fuente verificada)")
    if idioma == "en" and _tiene_diacritico_pl(texto):
        add("diacritico-pl-en-texto-en", "MAYOR", campo, "letras polacas en un campo en inglés")
    return True


def _palabras_mapa(mapa: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in mapa.get("ramas", []) if isinstance(mapa.get("ramas"), list) else []:
        if isinstance(r, dict) and isinstance(r.get("palabras"), list):
            out.extend(p for p in r["palabras"] if isinstance(p, dict))
    return out


def textos_visibles(mapa: Mapping[str, Any]) -> list[str]:
    """Todas las cadenas que aparecen en la hoja (sin los rótulos fijos)."""
    t: list[str] = []

    def g(d: Any, *claves: str) -> None:
        if isinstance(d, Mapping):
            for k in claves:
                if isinstance(d.get(k), str):
                    t.append(d[k])

    g(mapa.get("tema"), "pl")
    g(mapa.get("centro"), "en", "pl")
    for r in mapa.get("ramas", []) if isinstance(mapa.get("ramas"), list) else []:
        if isinstance(r, Mapping):
            g(r.get("grupo"), "pl")  # grupo.en es interno (no se imprime)
            for p in r.get("palabras", []) if isinstance(r.get("palabras"), list) else []:
                g(p, "en", "pl", "pista", "uwaga_pl")
    for f in mapa.get("frases", []) if isinstance(mapa.get("frases"), list) else []:
        g(f, "en", "pl")
    for v in mapa.get("powiedz_na_glos", []) if isinstance(mapa.get("powiedz_na_glos"), list) else []:
        g(v, "en", "pl")
    ej = mapa.get("ejercicios") if isinstance(mapa.get("ejercicios"), Mapping) else {}
    for c in ej.get("completar", []) if isinstance(ej.get("completar"), list) else []:
        if isinstance(c, Mapping):
            g(c, "texto", "respuesta")
            t.extend(o for o in c.get("opciones", []) if isinstance(o, str))
    for u in ej.get("unir", []) if isinstance(ej.get("unir"), list) else []:
        g(u, "en", "pl")
    for tr in ej.get("traducir", []) if isinstance(ej.get("traducir"), list) else []:
        g(tr, "pl", "respuesta")
    g(mapa.get("siguiente_paso"), "texto_pl")
    return t


def contar_palabras(textos: Iterable[str]) -> int:
    return sum(len(re.findall(r"[\w'’]+", x)) for x in textos)


def palabras_visibles(mapa: Mapping[str, Any]) -> int:
    """Palabras que el comprador ve en la hoja (contenido + rótulos fijos)."""
    return contar_palabras(textos_visibles(mapa)) + PALABRAS_FIJAS_UI


def validar_mapa(mapa: Any, *, temario: Mapping[str, Any] | None = None) -> list[dict[str, str]]:
    """Valida un mapa. ``temario`` = el dict de ``temario.json`` (opcional: activa las comprobaciones de ruta)."""
    hs: list[dict[str, str]] = []

    def add(cod: str, sev: str, campo: str, msg: str) -> None:
        hs.append(hallazgo(cod, sev, campo, msg))

    if not isinstance(mapa, dict):
        return [hallazgo("no-es-objeto", "BLOQUEANTE", "$", "el mapa debe ser un objeto JSON")]
    permitidas = {"schema_version", "mapa_id", "nivel", "numero", "tema", "centro", "ramas", "frases", "powiedz_na_glos", "ejercicios", "siguiente_paso"}
    for k in sorted(set(mapa) - permitidas):
        add("clave-desconocida", "MAYOR", k, "clave que el esquema 1.0.0 no define")
    for k in sorted(permitidas - set(mapa)):
        add("clave-faltante", "BLOQUEANTE", k, "clave obligatoria ausente")
    if mapa.get("schema_version") != VERSION_ESQUEMA:
        add("schema-version", "BLOQUEANTE", "schema_version", f"debe ser {VERSION_ESQUEMA!r}")

    # --- identidad ------------------------------------------------------------------------------------------------
    nivel, numero, mid = mapa.get("nivel"), mapa.get("numero"), mapa.get("mapa_id")
    if nivel not in NIVELES:
        add("nivel", "BLOQUEANTE", "nivel", f"debe ser uno de {', '.join(NIVELES)}")
    if not (isinstance(numero, int) and not isinstance(numero, bool) and numero >= 1):
        add("numero", "BLOQUEANTE", "numero", "entero ≥ 1")
    elif nivel in REPARTO and numero > REPARTO[nivel]:
        add("numero", "BLOQUEANTE", "numero", f"el nivel {nivel} solo tiene {REPARTO[nivel]} mapas")
    m = _RX_ID.match(mid) if isinstance(mid, str) else None
    if not m:
        add("mapa-id", "BLOQUEANTE", "mapa_id", "formato <nivel>-<nnn>-<slug>, p. ej. a1-001-food")
    else:
        if nivel in NIVELES and m.group(1) != str(nivel).lower():
            add("mapa-id-nivel", "BLOQUEANTE", "mapa_id", "el prefijo del id no coincide con el nivel")
        if isinstance(numero, int) and int(m.group(2)) != numero:
            add("mapa-id-numero", "BLOQUEANTE", "mapa_id", "el número del id no coincide con «numero»")

    # --- tema y centro ----------------------------------------------------------------------------------------------
    for clave in ("tema", "centro"):
        d = mapa.get(clave)
        if not isinstance(d, dict):
            add("estructura", "BLOQUEANTE", clave, "debe ser {en, pl}")
            continue
        for k in sorted(set(d) - {"en", "pl"}):
            add("clave-desconocida", "MAYOR", f"{clave}.{k}", "clave no definida")
        _higiene(add, f"{clave}.en", d.get("en"), idioma="en")
        _higiene(add, f"{clave}.pl", d.get("pl"))
    centro = mapa.get("centro") if isinstance(mapa.get("centro"), dict) else {}
    if _es_txt(centro.get("en")) and (len(centro["en"]) > 22 or len(str(centro.get("pl", ""))) > 24):
        add("centro-largo", "MAYOR", "centro", "palabra central demasiado larga para el nodo (EN ≤ 22, PL ≤ 24)")

    # --- ramas y palabras ---------------------------------------------------------------------------------------------
    ramas = mapa.get("ramas")
    palabras: list[dict[str, Any]] = []
    vistos_en: dict[str, str] = {}
    vistos_pl: dict[str, str] = {}
    grupos_en: set[str] = set()
    if not isinstance(ramas, list):
        add("estructura", "BLOQUEANTE", "ramas", "debe ser una lista")
        ramas = []
    if not (RAMAS_MIN <= len(ramas) <= RAMAS_MAX):
        add("ramas-rango", "BLOQUEANTE", "ramas", f"{len(ramas)} ramas; deben ser de {RAMAS_MIN} a {RAMAS_MAX}")
    for i, r in enumerate(ramas, 1):
        base = f"ramas[{i}]"
        if not isinstance(r, dict):
            add("estructura", "BLOQUEANTE", base, "cada rama es un objeto")
            continue
        for k in sorted(set(r) - {"grupo", "palabras"}):
            add("clave-desconocida", "MAYOR", f"{base}.{k}", "clave no definida")
        g = r.get("grupo")
        if not isinstance(g, dict):
            add("estructura", "BLOQUEANTE", f"{base}.grupo", "debe ser {en, pl}")
        else:
            if _higiene(add, f"{base}.grupo.en", g.get("en"), idioma="en"):
                if len(g["en"]) > L_GRUPO_EN:
                    add("largo", "MAYOR", f"{base}.grupo.en", f"más de {L_GRUPO_EN} caracteres")
                if _norm(g["en"]) in grupos_en:
                    add("grupo-repetido", "MAYOR", f"{base}.grupo.en", "dos ramas con el mismo grupo")
                grupos_en.add(_norm(g["en"]))
            if _higiene(add, f"{base}.grupo.pl", g.get("pl")) and len(g["pl"]) > L_GRUPO_PL:
                add("largo", "MAYOR", f"{base}.grupo.pl", f"más de {L_GRUPO_PL} caracteres")
        ps = r.get("palabras")
        if not isinstance(ps, list) or not (1 <= len(ps) <= PALABRAS_POR_RAMA_MAX):
            add("palabras-por-rama", "BLOQUEANTE", f"{base}.palabras", f"cada rama lleva de 1 a {PALABRAS_POR_RAMA_MAX} palabras")
            continue
        for j, p in enumerate(ps, 1):
            c = f"{base}.palabras[{j}]"
            if not isinstance(p, dict):
                add("estructura", "BLOQUEANTE", c, "cada palabra es un objeto")
                continue
            for k in sorted(set(p) - {"en", "pl", "pista", "uwaga_pl"}):
                add("clave-desconocida", "MAYOR", f"{c}.{k}", "clave no definida")
            ok_en = _higiene(add, f"{c}.en", p.get("en"), idioma="en")
            ok_pl = _higiene(add, f"{c}.pl", p.get("pl"))
            if ok_en:
                if not _RX_EN_PALABRA.match(p["en"]) or len(p["en"].split()) > 3:
                    add("palabra-en-formato", "MAYOR", f"{c}.en", "minúsculas, sin signos y de 1 a 3 palabras (sin nombres propios)")
                if len(p["en"]) > L_EN_PALABRA:
                    add("largo", "MAYOR", f"{c}.en", f"más de {L_EN_PALABRA} caracteres")
                k = _norm(p["en"])
                if k in vistos_en:
                    add("palabra-repetida-en-mapa", "BLOQUEANTE", f"{c}.en", f"«{p['en']}» ya está en {vistos_en[k]}")
                vistos_en[k] = c
            if ok_pl:
                if not _RX_PL_PALABRA.match(p["pl"]):
                    add("palabra-pl-formato", "MAYOR", f"{c}.pl", "minúsculas y solo letras polacas, espacio o guion (sin signos ni números)")
                if len(p["pl"]) > L_PL_PALABRA:
                    add("largo", "MAYOR", f"{c}.pl", f"más de {L_PL_PALABRA} caracteres")
                k = _norm(p["pl"])
                if k in vistos_pl:
                    add("traduccion-repetida-en-mapa", "MAYOR", f"{c}.pl", f"«{p['pl']}» ya traduce otra palabra de este mapa ({vistos_pl[k]}): el ejercicio de unir sería ambiguo")
                vistos_pl[k] = c
            if ok_en and ok_pl and len(p["en"]) + len(p["pl"]) > L_PAR_TARJETA:
                add("par-demasiado-largo", "MAYOR", c, f"EN+PL de más de {L_PAR_TARJETA} caracteres")
            if _higiene(add, f"{c}.pista", p.get("pista"), idioma="en") and len(p["pista"]) > L_PISTA:
                add("largo", "MAYOR", f"{c}.pista", f"más de {L_PISTA} caracteres")
            if "uwaga_pl" in p and p["uwaga_pl"] is not None:
                if _higiene(add, f"{c}.uwaga_pl", p["uwaga_pl"]) and len(p["uwaga_pl"]) > L_UWAGA:
                    add("largo", "MAYOR", f"{c}.uwaga_pl", f"más de {L_UWAGA} caracteres")
            palabras.append(p)
    if not (PALABRAS_MIN <= len(palabras) <= PALABRAS_MAX):
        add("palabras-rango", "BLOQUEANTE", "ramas", f"{len(palabras)} palabras en total; deben ser de {PALABRAS_MIN} a {PALABRAS_MAX}")
    lemas = {_norm(p["en"]) for p in palabras if _es_txt(p.get("en"))}
    if _es_txt(centro.get("en")) and _norm(centro["en"]) in lemas:
        add("centro-repetido", "MAYOR", "centro.en", "la palabra central también está como palabra de una rama")
    pares_pl = {(_norm(p["en"]), _norm(p["pl"])) for p in palabras if _es_txt(p.get("en")) and _es_txt(p.get("pl"))}

    # --- frases ----------------------------------------------------------------------------------------------------------
    frases = mapa.get("frases")
    cubiertas: set[str] = set()
    if not isinstance(frases, list):
        add("estructura", "BLOQUEANTE", "frases", "debe ser una lista")
        frases = []
    if not (FRASES_MIN <= len(frases) <= FRASES_MAX):
        add("frases-rango", "BLOQUEANTE", "frases", f"{len(frases)} frases; deben ser de {FRASES_MIN} a {FRASES_MAX}")
    vistas_en: set[str] = set()
    for i, f in enumerate(frases, 1):
        c = f"frases[{i}]"
        if not isinstance(f, dict):
            add("estructura", "BLOQUEANTE", c, "cada frase es un objeto")
            continue
        for k in sorted(set(f) - {"en", "pl", "usa"}):
            add("clave-desconocida", "MAYOR", f"{c}.{k}", "clave no definida")
        ok_en = _higiene(add, f"{c}.en", f.get("en"), idioma="en")
        ok_pl = _higiene(add, f"{c}.pl", f.get("pl"))
        if ok_en:
            if not _RX_FIN_FRASE.search(f["en"]) or not (f["en"][0].isupper() or f["en"][0].isdigit()):
                add("frase-puntuacion", "MAYOR", f"{c}.en", "empieza con mayúscula y termina en . ? o !")
            if len(f["en"]) > L_FRASE_EN:
                add("largo", "MAYOR", f"{c}.en", f"más de {L_FRASE_EN} caracteres")
            if _norm(f["en"]) in vistas_en:
                add("frase-repetida", "MAYOR", f"{c}.en", "frase repetida en el mapa")
            vistas_en.add(_norm(f["en"]))
        if ok_pl:
            if not _RX_FIN_FRASE.search(f["pl"]) or not (f["pl"][0].isupper() or f["pl"][0].isdigit() or f["pl"][0] in "„\"–"):
                add("frase-puntuacion", "MAYOR", f"{c}.pl", "empieza con mayúscula y termina en . ? o !")
            if len(f["pl"]) > L_FRASE_PL:
                add("largo", "MAYOR", f"{c}.pl", f"más de {L_FRASE_PL} caracteres")
        if ok_en and ok_pl and _norm(f["en"]) == _norm(f["pl"]):
            add("traduccion-identica", "BLOQUEANTE", c, "la «traducción» es idéntica al original")
        usa = f.get("usa")
        if not isinstance(usa, list) or not usa:
            add("usa-vacio", "BLOQUEANTE", f"{c}.usa", "cada frase declara qué palabras del mapa usa")
            continue
        for k2, u in enumerate(usa, 1):
            cu = f"{c}.usa[{k2}]"
            if not isinstance(u, dict) or not all(_es_txt(u.get(x)) for x in ("en", "forma_en", "forma_pl")):
                add("usa-estructura", "BLOQUEANTE", cu, "debe ser {en, forma_en, forma_pl}")
                continue
            if _norm(u["en"]) not in lemas:
                add("usa-palabra-desconocida", "BLOQUEANTE", cu, f"«{u['en']}» no es una palabra de las ramas")
            else:
                cubiertas.add(_norm(u["en"]))
            if ok_en and not _contiene_forma(f["en"], u["forma_en"]):
                add("forma-en-no-aparece", "BLOQUEANTE", cu, f"«{u['forma_en']}» no aparece como palabra entera en la frase EN")
            if ok_pl and not _contiene_forma(f["pl"], u["forma_pl"]):
                add("forma-pl-no-aparece", "BLOQUEANTE", cu, f"«{u['forma_pl']}» no aparece como palabra entera en la frase PL: la traducción no recoge la palabra")
    for p in palabras:
        if _es_txt(p.get("en")) and _norm(p["en"]) not in cubiertas:
            add("palabra-sin-frase", "BLOQUEANTE", "frases", f"la palabra «{p['en']}» no aparece en ninguna frase (las palabras van en frases, no sueltas)")

    # --- powiedz na głos ---------------------------------------------------------------------------------------------------
    voz = mapa.get("powiedz_na_glos")
    if not isinstance(voz, list):
        add("estructura", "BLOQUEANTE", "powiedz_na_glos", "debe ser una lista")
        voz = []
    if not (VOZ_MIN <= len(voz) <= VOZ_MAX):
        add("voz-rango", "BLOQUEANTE", "powiedz_na_glos", f"{len(voz)} líneas; deben ser de {VOZ_MIN} a {VOZ_MAX}")
    for i, v in enumerate(voz, 1):
        c = f"powiedz_na_glos[{i}]"
        if not isinstance(v, dict):
            add("estructura", "BLOQUEANTE", c, "debe ser {en, pl}")
            continue
        for k in sorted(set(v) - {"en", "pl"}):
            add("clave-desconocida", "MAYOR", f"{c}.{k}", "clave no definida")
        ok_en = _higiene(add, f"{c}.en", v.get("en"), idioma="en")
        ok_pl = _higiene(add, f"{c}.pl", v.get("pl"))
        if ok_en and (len(v["en"]) > L_VOZ or not _RX_FIN_FRASE.search(v["en"])):
            add("voz-formato", "MAYOR", f"{c}.en", f"≤ {L_VOZ} caracteres y termina en . ? o !")
        if ok_pl and not _RX_FIN_FRASE.search(v["pl"]):
            add("voz-formato", "MAYOR", f"{c}.pl", "termina en . ? o !")
        if ok_en and not any(_contiene_forma(v["en"], p["en"]) for p in palabras if _es_txt(p.get("en"))) and not any(
            _contiene_forma(v["en"], u["forma_en"]) for f in frases if isinstance(f, dict) for u in (f.get("usa") or []) if isinstance(u, dict) and _es_txt(u.get("forma_en"))
        ):
            add("voz-sin-vocabulario", "MENOR", c, "la línea no usa ninguna palabra del mapa")

    # --- ejercicios -----------------------------------------------------------------------------------------------------------
    ej = mapa.get("ejercicios")
    formas_en = {_norm(u["forma_en"]) for f in frases if isinstance(f, dict) for u in (f.get("usa") or []) if isinstance(u, dict) and _es_txt(u.get("forma_en"))}
    if not isinstance(ej, dict):
        add("estructura", "BLOQUEANTE", "ejercicios", "debe ser {completar, unir, traducir}")
        ej = {}
    for k in sorted(set(ej) - {"completar", "unir", "traducir"}):
        add("clave-desconocida", "MAYOR", f"ejercicios.{k}", "clave no definida")
    comp = ej.get("completar") if isinstance(ej.get("completar"), list) else []
    if len(comp) != N_COMPLETAR:
        add("completar-cantidad", "BLOQUEANTE", "ejercicios.completar", f"{len(comp)} ítems; deben ser {N_COMPLETAR}")
    for i, c_ in enumerate(comp, 1):
        c = f"ejercicios.completar[{i}]"
        if not isinstance(c_, dict):
            add("estructura", "BLOQUEANTE", c, "debe ser {texto, opciones, respuesta}")
            continue
        for k in sorted(set(c_) - {"texto", "opciones", "respuesta"}):
            add("clave-desconocida", "MAYOR", f"{c}.{k}", "clave no definida")
        if _higiene(add, f"{c}.texto", c_.get("texto"), idioma="en"):
            if len(_RX_BLANK.findall(c_["texto"])) != 1:
                add("completar-hueco", "BLOQUEANTE", f"{c}.texto", "debe llevar exactamente un hueco «___»")
            if len(c_["texto"]) > L_COMPLETAR:
                add("largo", "MAYOR", f"{c}.texto", f"más de {L_COMPLETAR} caracteres")
        ops = c_.get("opciones")
        if not isinstance(ops, list) or not (2 <= len(ops) <= 3) or not all(_es_txt(o) for o in ops) or len({_norm(o) for o in ops}) != len(ops):
            add("completar-opciones", "BLOQUEANTE", f"{c}.opciones", "2 o 3 opciones distintas")
            ops = []
        for o in ops:
            _higiene(add, f"{c}.opciones", o, idioma="en")
        resp = c_.get("respuesta")
        if _higiene(add, f"{c}.respuesta", resp, idioma="en"):
            if ops and resp not in ops:
                add("completar-respuesta", "BLOQUEANTE", f"{c}.respuesta", "la respuesta no está entre las opciones")
            elif _norm(resp) not in lemas and _norm(resp) not in formas_en:
                add("completar-fuera-del-mapa", "MAYOR", f"{c}.respuesta", f"«{resp}» no es una palabra (ni forma usada) del mapa: el ejercicio no practica su vocabulario")
            art = articulo_previo(c_["texto"]) if isinstance(c_.get("texto"), str) else None
            if art and ops and resp in ops:
                concuerdan = [o for o in ops if (art == "an") == sonido_vocal(o.split()[0])]
                if resp not in concuerdan:
                    add("completar-articulo", "BLOQUEANTE", f"{c}.texto", f"con la respuesta «{resp}» queda «{art} {resp}», agramatical")
                elif len(concuerdan) < len(ops):
                    add("completar-articulo-delata", "MAYOR", f"{c}.texto", f"el artículo «{art}» delata la respuesta: las otras opciones no concuerdan con él")
    unir = ej.get("unir") if isinstance(ej.get("unir"), list) else []
    if len(unir) != N_UNIR:
        add("unir-cantidad", "BLOQUEANTE", "ejercicios.unir", f"{len(unir)} pares; deben ser {N_UNIR}")
    vistos_u: set[str] = set()
    for i, u in enumerate(unir, 1):
        c = f"ejercicios.unir[{i}]"
        if not isinstance(u, dict) or not _es_txt(u.get("en")) or not _es_txt(u.get("pl")):
            add("estructura", "BLOQUEANTE", c, "debe ser {en, pl}")
            continue
        for k in sorted(set(u) - {"en", "pl"}):
            add("clave-desconocida", "MAYOR", f"{c}.{k}", "clave no definida")
        if (_norm(u["en"]), _norm(u["pl"])) not in pares_pl:
            add("unir-par-inexistente", "BLOQUEANTE", c, f"«{u['en']} = {u['pl']}» no coincide con ninguna palabra y traducción del mapa")
        if _norm(u["en"]) in vistos_u:
            add("unir-repetido", "BLOQUEANTE", c, "par repetido")
        vistos_u.add(_norm(u["en"]))
    trad = ej.get("traducir") if isinstance(ej.get("traducir"), list) else []
    if len(trad) != N_TRADUCIR:
        add("traducir-cantidad", "BLOQUEANTE", "ejercicios.traducir", f"{len(trad)} ítems; deben ser {N_TRADUCIR}")
    for i, t_ in enumerate(trad, 1):
        c = f"ejercicios.traducir[{i}]"
        if not isinstance(t_, dict):
            add("estructura", "BLOQUEANTE", c, "debe ser {pl, respuesta}")
            continue
        for k in sorted(set(t_) - {"pl", "respuesta"}):
            add("clave-desconocida", "MAYOR", f"{c}.{k}", "clave no definida")
        ok_pl = _higiene(add, f"{c}.pl", t_.get("pl"))
        ok_en = _higiene(add, f"{c}.respuesta", t_.get("respuesta"), idioma="en")
        if ok_pl and not _RX_FIN_FRASE.search(t_["pl"]):
            add("frase-puntuacion", "MAYOR", f"{c}.pl", "termina en . ? o !")
        if ok_en and not _RX_FIN_FRASE.search(t_["respuesta"]):
            add("frase-puntuacion", "MAYOR", f"{c}.respuesta", "termina en . ? o !")
        if ok_pl and ok_en and _norm(t_["pl"]) == _norm(t_["respuesta"]):
            add("traduccion-identica", "BLOQUEANTE", c, "pregunta y respuesta idénticas")

    # --- siguiente paso -------------------------------------------------------------------------------------------------------
    sp = mapa.get("siguiente_paso")
    if not isinstance(sp, dict):
        add("estructura", "BLOQUEANTE", "siguiente_paso", "debe ser {mapa_id, texto_pl}")
    else:
        for k in sorted(set(sp) - {"mapa_id", "texto_pl"}):
            add("clave-desconocida", "MAYOR", f"siguiente_paso.{k}", "clave no definida")
        if _higiene(add, "siguiente_paso.texto_pl", sp.get("texto_pl")) and len(sp["texto_pl"]) > L_NEXT:
            add("largo", "MAYOR", "siguiente_paso.texto_pl", f"más de {L_NEXT} caracteres")
        sid = sp.get("mapa_id")
        if sid is not None and not (isinstance(sid, str) and _RX_ID.match(sid)):
            add("siguiente-id", "BLOQUEANTE", "siguiente_paso.mapa_id", "id de mapa válido o null (solo el último mapa de la ruta)")

    # --- presupuesto de palabras (oferta.vehiculo.palabras_max) -------------------------------------------------------------
    n = palabras_visibles(mapa)
    if n > PALABRAS_VISIBLES_MAX:
        add("palabras-visibles", "MAYOR", "$", f"{n} palabras visibles; el máximo es {PALABRAS_VISIBLES_MAX} (oferta.vehiculo.palabras_max): no cabe en una sesión de ~10 min")

    # --- contra el temario -------------------------------------------------------------------------------------------------------
    if temario is not None and isinstance(mid, str):
        por_id = {e["mapa_id"]: e for e in temario.get("mapas", [])}
        e = por_id.get(mid)
        if e is None:
            add("fuera-del-temario", "BLOQUEANTE", "mapa_id", "el id no está en el temario")
        else:
            if nivel != e["nivel"] or numero != e["numero"]:
                add("temario-posicion", "BLOQUEANTE", "nivel/numero", f"el temario lo coloca en {e['nivel']} n.º {e['numero']}")
            tm = mapa.get("tema") if isinstance(mapa.get("tema"), dict) else {}
            if tm.get("en") != e["tema"]["en"] or tm.get("pl") != e["tema"]["pl"]:
                add("temario-titulo", "BLOQUEANTE", "tema", f"el título debe ser el del temario: {e['tema']['en']} / {e['tema']['pl']}")
            if isinstance(sp, dict) and sp.get("mapa_id") != e.get("siguiente"):
                add("temario-siguiente", "BLOQUEANTE", "siguiente_paso.mapa_id", f"la ruta del temario sigue con {e.get('siguiente')!r}")
    return hs


def hay_bloqueo(hallazgos: Iterable[Mapping[str, str]]) -> bool:
    return any(h["severidad"] in ("BLOQUEANTE", "MAYOR") for h in hallazgos)


def cargar_mapa(ruta: Path | str) -> dict[str, Any]:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def cargar_dir(carpeta: Path | str) -> list[tuple[Path, dict[str, Any]]]:
    """Todos los ``*.json`` de una carpeta (recursivo), ordenados por nombre."""
    return [(p, cargar_mapa(p)) for p in sorted(Path(carpeta).rglob("*.json"))]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.mapas.esquema", description="Valida mapas de Słowomapa")
    ap.add_argument("mapas", nargs="+")
    ap.add_argument("--temario")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    tem = json.loads(Path(a.temario).read_text(encoding="utf-8")) if a.temario else None
    salida: dict[str, list[dict[str, str]]] = {}
    rutas: list[Path] = []
    for x in a.mapas:
        p = Path(x)
        rutas.extend(sorted(p.rglob("*.json")) if p.is_dir() else [p])
    for p in rutas:
        try:
            salida[str(p)] = validar_mapa(cargar_mapa(p), temario=tem)
        except (OSError, json.JSONDecodeError) as exc:
            salida[str(p)] = [hallazgo("json-ilegible", "BLOQUEANTE", "$", str(exc))]
    malo = any(hay_bloqueo(h) for h in salida.values())
    if a.json:
        print(json.dumps({"ok": not malo, "mapas": salida}, ensure_ascii=False, indent=2))
    else:
        for ruta, hs in salida.items():
            print(("FALLA " if hay_bloqueo(hs) else "ok    ") + ruta + (f"  ({len(hs)} hallazgos)" if hs else ""))
            for h in hs:
                print(f"    [{h['severidad']}] {h['codigo']} · {h['campo']}: {h['mensaje']}")
    return 1 if malo else 0


if __name__ == "__main__":
    sys.exit(main())
