"""Comprobación del PDF renderizado contra el JSON de los mapas: capa de texto exacta (PDFKit) y OCR visual (Vision).

Dos pruebas distintas y complementarias (solo macOS; sin red):

1. **Capa de texto del PDF** (``PDFPage.string``): comprueba que cada palabra esperada del JSON está en el PDF TAL CUAL (diacríticos
   polacos incluidos). Si falta aquí, el PDF no contiene lo que dice el JSON: BLOQUEANTE.
2. **OCR de la página renderizada** (Vision, ``pl-PL`` y ``en-US``): comprueba que el texto SE VE (no solo está en la capa). El OCR
   se equivoca por sí solo con letras pequeñas: una palabra que está en la capa y falta en el OCR es «ruido de OCR» (informativo), no
   un fallo del PDF. La tasa de OCR y la de OCR sobre palabras con diacríticos polacos se informan aparte.

Los binarios Swift se compilan una vez en un directorio temporal (cache por hash del fuente).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.producto.mapas.esquema import textos_visibles

AQUI = Path(__file__).parent
_PL = "ąćęłńóśźż"
_RX_TOKEN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
ROTULOS_FIJOS = ["Zdania", "Ćwiczenia", "Powiedz na głos", "Następny krok", "Odpowiedzi", "Uzupełnij zdanie", "Połącz słowo z tłumaczeniem", "Przetłumacz na angielski"]


def compilar_swift(nombre: str) -> Path:
    """Compila ``<nombre>.swift`` (junto a este módulo) y devuelve el binario. ``RuntimeError`` si no hay ``swiftc``."""
    fuente = AQUI / f"{nombre}.swift"
    if shutil.which("swiftc") is None:
        raise RuntimeError("no hay swiftc: la capa que lo necesita queda NO EJECUTADA (nunca se da por pasada)")
    h = hashlib.sha256(fuente.read_bytes()).hexdigest()[:12]
    carpeta = Path(tempfile.gettempdir()) / "slowomapa-swift"
    carpeta.mkdir(exist_ok=True)
    binario = carpeta / f"{nombre}-{h}"
    if not binario.is_file():
        p = subprocess.run(["swiftc", "-O", str(fuente), "-o", str(binario)], capture_output=True, text=True, timeout=300)
        if p.returncode != 0 or not binario.is_file():
            raise RuntimeError(f"swiftc falló con {nombre}.swift: {p.stderr[-400:]}")
    return binario


def texto_pdf(pdf: Path | str, *, idiomas: str = "pl-PL,en-US", dpi: int = 300) -> list[dict[str, Any]]:
    """Capa de texto y líneas de OCR de cada página: ``[{n, capa, ocr:[...]}]``."""
    binario = compilar_swift("ocr_pdf")
    p = subprocess.run([str(binario), str(pdf), idiomas, str(dpi)], capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"ocr_pdf falló: {p.stderr[-300:]}")
    return json.loads(p.stdout)["paginas"]


def tokens(texto: str) -> list[str]:
    return [t.casefold() for t in _RX_TOKEN.findall(unicodedata.normalize("NFC", texto))]


def _sin_espacios(t: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", t).casefold())


def etiquetas(mapa: Mapping[str, Any]) -> list[str]:
    """Textos en MAYÚSCULAS con espaciado entre letras (rótulos y etiquetas de rama): la capa de texto los saca con huecos entre letras,
    así que se comprueban sin espacios."""
    return list(ROTULOS_FIJOS) + [r["grupo"]["pl"] for r in mapa.get("ramas", [])] + [f"Mapa słownictwa", f"poziom {mapa.get('nivel', '')}"]


def esperados(mapa: Mapping[str, Any]) -> list[str]:
    """Palabras que la hoja de este mapa tiene que mostrar (todo el texto del JSON salvo marcadores ``___``, etiquetas y rótulos)."""
    et = set(tokens(" ".join(etiquetas(mapa))))
    texto = " ".join(textos_visibles(mapa)).replace("___", " ")
    # las etiquetas de rama (grupo.pl) están en textos_visibles: se comprueban aparte
    return sorted(set(tokens(texto)) - et)


def _tiene_pl(t: str) -> bool:
    return any(c in _PL for c in t)


def comparar_pagina(mapa: Mapping[str, Any], pagina: Mapping[str, Any]) -> dict[str, Any]:
    esp = esperados(mapa)
    capa = set(tokens(pagina.get("capa", "")))
    ocr = set(tokens(" ".join(pagina.get("ocr", []))))
    falta_capa = [t for t in esp if t not in capa]
    falta_ocr = [t for t in esp if t not in ocr]
    sc, so = _sin_espacios(pagina.get("capa", "")), _sin_espacios(" ".join(pagina.get("ocr", [])))
    et_falta_capa = [e for e in etiquetas(mapa) if _sin_espacios(e) not in sc]
    et_falta_ocr = [e for e in etiquetas(mapa) if _sin_espacios(e) not in so]
    ruido = [t for t in falta_ocr if t in capa]
    esp_pl = [t for t in esp if _tiene_pl(t)]
    ocr_pl_ok = [t for t in esp_pl if t in ocr]
    capa_pl_ok = [t for t in esp_pl if t in capa]
    return {
        "mapa_id": mapa["mapa_id"], "pagina": pagina.get("n"),
        "tokens_esperados": len(esp), "etiquetas_faltan_en_capa": et_falta_capa, "etiquetas_faltan_en_ocr": et_falta_ocr, "faltan_en_capa": falta_capa, "faltan_en_ocr": falta_ocr, "solo_ruido_de_ocr": ruido,
        "tasa_capa": round(1 - len(falta_capa) / max(len(esp), 1), 4), "tasa_ocr": round(1 - len(falta_ocr) / max(len(esp), 1), 4),
        "diacriticos_pl": {"esperados": len(esp_pl), "en_capa": len(capa_pl_ok), "en_ocr": len(ocr_pl_ok), "faltan_en_ocr": [t for t in esp_pl if t not in ocr]},
        "ok": not falta_capa and not et_falta_capa,
    }


def verificar_pdf(pdf: Path | str, mapas: Sequence[Mapping[str, Any]], *, paginas_previas: int = 0) -> dict[str, Any]:
    """Compara cada página de ``pdf`` con su mapa. ``paginas_previas`` = hojas de portada antes del primer mapa (PDF de nivel: 1)."""
    pags = texto_pdf(pdf)
    esperadas = paginas_previas + len(mapas)
    res: dict[str, Any] = {"pdf": str(pdf), "paginas_pdf": len(pags), "paginas_esperadas": esperadas, "paginas": []}
    if len(pags) != esperadas:
        res["error"] = f"el PDF tiene {len(pags)} páginas y se esperaban {esperadas}"
    for i, m in enumerate(mapas):
        idx = paginas_previas + i
        if idx < len(pags):
            res["paginas"].append(comparar_pagina(m, pags[idx]))
    tot = sum(p["tokens_esperados"] for p in res["paginas"]) or 1
    res["resumen"] = {
        "ok_capa": all(p["ok"] for p in res["paginas"]) and "error" not in res,
        "tasa_ocr_media": round(1 - sum(len(p["faltan_en_ocr"]) for p in res["paginas"]) / tot, 4),
        "diacriticos_pl_en_ocr": round(
            sum(p["diacriticos_pl"]["en_ocr"] for p in res["paginas"]) / max(sum(p["diacriticos_pl"]["esperados"] for p in res["paginas"]), 1), 4),
        "diacriticos_pl_en_capa": round(
            sum(p["diacriticos_pl"]["en_capa"] for p in res["paginas"]) / max(sum(p["diacriticos_pl"]["esperados"] for p in res["paginas"]), 1), 4),
    }
    return res
