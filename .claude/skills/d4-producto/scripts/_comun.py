"""Utilidades compartidas de los scripts de D4 (solo biblioteca estándar; sin red; sin secretos).

Convenciones de todos los scripts de esta carpeta:
- Salida: un único objeto JSON por stdout (y a ``--salida`` si se pide).
- Código de salida: 0 sin hallazgos BLOQUEANTE/MAYOR · 1 con hallazgos BLOQUEANTE/MAYOR · 2 uso · 3 entrada inválida ·
  5 falta un parámetro (fail-closed, igual que ``scripts.validar_esquemas``).
- Ningún umbral vive en el código: salen de ``empresa/parametros.yaml`` (``--parametros``) o de una bandera explícita.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

VERSION = "0.1.1"
SEVERIDADES = ("BLOQUEANTE", "MAYOR", "MENOR", "MEJORA")
EXT_TEXTO = {".md", ".txt", ".html", ".htm", ".css", ".csv", ".json", ".jsonl", ".svg"}


class ParametroFaltante(Exception):
    """Un umbral necesario no llegó por bandera ni por ``parametros.yaml`` (salida 5)."""


# --------------------------------------------------------------------------------------------------
# Raíz del proyecto, hashes y lectura
# --------------------------------------------------------------------------------------------------
def raiz_proyecto(inicio: Path | None = None) -> Path | None:
    """Sube desde ``inicio`` (o desde este archivo) hasta hallar una carpeta con ``contratos/``."""
    p = (inicio or Path(__file__)).resolve()
    for cand in [p, *p.parents]:
        if (cand / "contratos").is_dir() and (cand / "empresa").is_dir():
            return cand
    return None


def normalizar_texto(texto: str) -> str:
    """Unicode NFC y saltos de línea ``\\n`` (misma regla que ``scripts.validar_esquemas.normalizar_texto``)."""
    return unicodedata.normalize("NFC", texto.replace("\r\n", "\n").replace("\r", "\n"))


def _hash_bytes(datos: bytes) -> str:
    return "sha256:" + hashlib.sha256(datos).hexdigest()


def _json_canonico(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def hash_archivo(ruta: Path | str) -> str:
    """``sha256:<hex>`` de un archivo con la MISMA regla del validador de esquemas.

    Usa ``scripts.validar_esquemas.hash_archivo`` si el proyecto está accesible (fuente única de la regla) y, si no, una copia
    local de la regla (JSON por su forma canónica, texto normalizado NFC y ``\\n``, el resto por bytes).
    """
    ruta = Path(ruta)
    raiz = raiz_proyecto(ruta if ruta.exists() else None)
    if raiz is not None:
        try:
            if str(raiz) not in sys.path:
                sys.path.insert(0, str(raiz))
            from scripts.validar_esquemas import hash_archivo as _h  # type: ignore

            return _h(ruta)
        except Exception:  # noqa: BLE001 - sin jsonschema/yaml se cae a la copia local
            pass
    if ruta.suffix == ".json":
        return _hash_bytes(_json_canonico(json.loads(ruta.read_text(encoding="utf-8"))))
    if ruta.suffix in {".md", ".txt", ".html", ".css", ".js", ".mjs", ".jsonl", ".csv", ".svg"}:
        return _hash_bytes(normalizar_texto(ruta.read_text(encoding="utf-8")).encode("utf-8"))
    return _hash_bytes(ruta.read_bytes())


def hash_texto(texto: str) -> str:
    """Hash de un texto ya leído (misma normalización que un ``.txt``)."""
    return _hash_bytes(normalizar_texto(texto).encode("utf-8"))


def cargar_json(ruta: Path | str) -> Any:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def cargar_jsonl(ruta: Path | str) -> list[dict]:
    filas: list[dict] = []
    with open(ruta, encoding="utf-8") as f:
        for n, linea in enumerate(f, 1):
            if linea.strip():
                try:
                    filas.append(json.loads(linea))
                except json.JSONDecodeError as e:
                    raise ValueError(f"{ruta}:{n}: JSON inválido ({e.msg})") from e
    return filas


def cargar_yaml(ruta: Path | str) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ParametroFaltante("PyYAML no disponible: pasa los umbrales por bandera") from e
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parametro(parametros: Path | None, grupo: str, clave: str, cli: Any = None) -> Any:
    """Valor de ``grupos.<grupo>.<clave>.valor``; la bandera (``cli``) manda. Sin dato: ``ParametroFaltante`` (salida 5)."""
    if cli is not None:
        return cli
    if parametros is not None and Path(parametros).is_file():
        d = cargar_yaml(parametros)
        v = ((d.get("grupos", {}).get(grupo, {}) or {}).get(clave, {}) or {}).get("valor")
        if v is not None:
            return v
    raise ParametroFaltante(f"falta el parámetro {grupo}.{clave}: pasarlo por bandera o por --parametros")


def parametros_por_defecto(ruta: str | None) -> Path | None:
    if ruta:
        return Path(ruta)
    raiz = raiz_proyecto()
    return (raiz / "empresa" / "parametros.yaml") if raiz else None


# --------------------------------------------------------------------------------------------------
# Texto: lectura, limpieza, tokens
# --------------------------------------------------------------------------------------------------
class _Extractor(HTMLParser):
    """HTML a texto plano; omite ``script``/``style`` y los bloques ``data-lectura="referencia"`` si se pide."""

    def __init__(self, omitir_referencia: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.omitir_referencia = omitir_referencia
        self._pila: list[bool] = []  # por etiqueta abierta: ¿abre una zona omitida?
        self._omitidas = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"br", "img", "hr", "meta", "link", "input"}:
            return
        omitir = tag in {"script", "style"} or (self.omitir_referencia and dict(attrs).get("data-lectura") == "referencia")
        self._pila.append(omitir)
        if omitir:
            self._omitidas += 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "section", "table"}:
            self.partes.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"br", "img", "hr", "meta", "link", "input"}:
            return
        if self._pila and self._pila.pop():
            self._omitidas -= 1

    def handle_data(self, data: str) -> None:
        if self._omitidas == 0:
            self.partes.append(data)


def html_a_texto(contenido: str, omitir_referencia: bool = False) -> str:
    p = _Extractor(omitir_referencia)
    p.feed(contenido)
    return "".join(p.partes)


def _strings_de_json(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings_de_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings_de_json(v)


def leer_texto(ruta: Path | str, omitir_referencia: bool = False) -> str:
    """Texto legible de un archivo (md, txt, html, json, jsonl, csv). Otros formatos: ``ValueError``."""
    ruta = Path(ruta)
    suf = ruta.suffix.lower()
    if suf not in EXT_TEXTO:
        raise ValueError(f"formato no textual: {ruta.name} (el texto de un PDF o XLSX se verifica en su fuente HTML/MD)")
    bruto = ruta.read_text(encoding="utf-8", errors="replace")
    if suf in {".html", ".htm"}:
        return normalizar_texto(html_a_texto(bruto, omitir_referencia))
    if suf == ".json":
        return normalizar_texto("\n".join(_strings_de_json(json.loads(bruto))))
    if suf == ".jsonl":
        return normalizar_texto("\n".join(s for l in bruto.splitlines() if l.strip() for s in _strings_de_json(json.loads(l))))
    return normalizar_texto(bruto)


def expandir_rutas(rutas: Iterable[str], extensiones: set[str] | None = None) -> list[Path]:
    """Archivos de una lista de rutas (archivo o carpeta, recursivo), ordenados."""
    ext = extensiones or EXT_TEXTO
    salida: list[Path] = []
    for r in rutas:
        p = Path(r)
        if p.is_dir():
            salida.extend(sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in ext))
        elif p.is_file():
            salida.append(p)
        else:
            raise FileNotFoundError(r)
    return salida


def quitar_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


RX_TOKEN = re.compile(r"\w+(?:['’]\w+)*", re.UNICODE)


def tokens_con_posicion(texto: str, plegar_acentos: bool = True) -> list[tuple[str, int, int]]:
    """``(token, inicio, fin)`` de cada palabra (minúsculas; con ``plegar_acentos`` sin diacríticos, para comparar)."""
    salida = []
    for m in RX_TOKEN.finditer(texto):
        t = m.group(0).replace("’", "'").casefold()
        if plegar_acentos:
            t = quitar_acentos(t)
        salida.append((t, m.start(), m.end()))
    return salida


def contar_palabras(texto: str) -> int:
    return len(RX_TOKEN.findall(texto))


def normalizar_busqueda(texto: str) -> str:
    """NFC, minúsculas, comillas tipográficas unificadas y espacios colapsados (búsqueda exacta normalizada de ``cita_literal``)."""
    t = normalizar_texto(texto).casefold()
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    t = t.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", t).strip()


RX_CITAS = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"\n]*\"")


def tramos_entrecomillados(texto: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in RX_CITAS.finditer(texto)]


# --------------------------------------------------------------------------------------------------
# Números por locale (L1-13)
# --------------------------------------------------------------------------------------------------
_SEP_POR_IDIOMA = {  # (separador de miles, separador decimal)
    "es": (".", ","), "it": (".", ","), "pt": (".", ","), "de": (".", ","), "ro": (".", ","), "nl": (".", ","), "el": (".", ","),
    "pl": (" ", ","), "fr": (" ", ","), "cs": (" ", ","), "sk": (" ", ","), "ru": (" ", ","),
    "en": (",", "."), "ja": (",", "."), "zh": (",", "."),
}
RX_NUMERO = re.compile(r"(?<![\w.,])(\d+(?:[.,  ]\d+)*)(?![\w])")
UNIDADES_HECHO = (
    r"mg|µg|μg|mcg|g|kg|gr|ml|dl|cl|l|kcal|kj|cal|%|°c|ºc|°f|ºf|€|eur|euros?|euro|\$|usd|us\$|zł|zl|pln|lei|ron|£|gbp|chf|"
    r"cucchiai[oa]?|cucchiain[oi]|cucharadas?|cucharaditas?|tablespoons?|teaspoons?|tbsp|tsp|łyżk\w*|łyżeczk\w*|linguri\w*|"
    r"cuill[eè]res?|gramos?|gramm\w*|grammes?|grams?|litros?|litri|litres?|años|anni|years?|lat|ans"
)
RX_UNIDAD_ADYACENTE = re.compile(rf"^\s{{0,1}}(?:{UNIDADES_HECHO})(?![A-Za-zÀ-ÿ])", re.IGNORECASE)
RX_UNIDAD_PREVIA = re.compile(rf"(?:€|\$|£|usd|eur|pln|zł)\s?$", re.IGNORECASE)
RX_MARCADOR = re.compile(r"(?:paso|pasos|cap[ií]tulo|cap\.|p[aá]gina|p[aá]g\.|step|chapter|page|passo|capitolo|pagina|krok|rozdzia[łl]|strona|"
                         r"[ée]tape|chapitre|schritt|kapitel|seite|etapa|ficha|tarjeta|card|karta|fiche|scheda|nr\.?|n\.º|n°|#)\s*$", re.IGNORECASE)


def separadores(locale: str) -> tuple[str, str]:
    return _SEP_POR_IDIOMA.get(locale.split("-")[0].lower(), (",", "."))


def interpretar_numero(token: str, locale: str) -> tuple[Decimal | None, list[str]]:
    """Valor de ``token`` según los separadores del ``locale`` y banderas de anomalía.

    Banderas: ``separador_ajeno`` (usa el separador de otro locale), ``ambiguo_miles_decimal`` (``1,500`` en un locale de coma decimal:
    ¿1,5 o 1500?), ``inconsistente_locale`` (mezcla ``1,500.50`` en un locale de coma decimal), ``no_numero`` (fecha, versión, ``3.2.1``).
    """
    miles, dec = separadores(locale)
    banderas: list[str] = []
    t = token.replace(" ", " ")
    if re.fullmatch(r"\d+", t):
        return Decimal(t), banderas
    if " " in t and not re.search(r"[.,]", t):
        if re.fullmatch(r"\d{1,3}( \d{3})+", t):
            return Decimal(t.replace(" ", "")), banderas
        return None, ["no_numero"]
    t2 = t.replace(" ", "")
    seps = re.findall(r"[.,]", t2)
    try:
        if "." in t2 and "," in t2:
            ultimo = max(t2.rfind("."), t2.rfind(","))
            sd = t2[ultimo]
            otro = "," if sd == "." else "."
            if sd != dec:
                banderas.append("inconsistente_locale")
            ent, frac = t2[:ultimo], t2[ultimo + 1:]
            if not re.fullmatch(rf"\d{{1,3}}(?:{re.escape(otro)}\d{{3}})*", ent) or not frac.isdigit():
                return None, ["no_numero"]
            return Decimal(ent.replace(otro, "") + "." + frac), banderas
        s = seps[0]
        if len(seps) > 1:  # varios separadores iguales: solo válido como miles
            if s == miles or (miles == " " and s == "."):
                if re.fullmatch(rf"\d{{1,3}}(?:{re.escape(s)}\d{{3}})+", t2):
                    if s != miles:
                        banderas.append("separador_ajeno")
                    return Decimal(t2.replace(s, "")), banderas
            return None, ["no_numero"]
        a, b = t2.split(s)
        if s == dec:
            if len(b) == 3 and 1 <= len(a) <= 3:  # «1,500» en coma decimal: ¿1,5 o 1500 escrito a la inglesa?
                banderas.append("ambiguo_miles_decimal")
            return Decimal(a + "." + b), banderas
        # el separador es el de miles del locale (o de otro locale)
        if len(b) == 3 and 1 <= len(a) <= 3:
            if s != miles and miles != " ":
                banderas.append("separador_ajeno")
            if miles == " " and s in {".", ","}:
                banderas.append("separador_ajeno")
            return Decimal(a + b), banderas
        banderas.append("separador_ajeno")
        return Decimal(a + "." + b), banderas
    except InvalidOperation:
        return None, ["no_numero"]


def numeros_en_texto(texto: str, locale: str) -> list[dict]:
    """Cada número del texto con su valor, banderas, unidad adyacente y si es una «cifra de hecho» (a respaldar).

    ``cifra_de_hecho`` = lleva unidad de hecho (masa, volumen, energía, %, moneda, cucharas, edad), o tiene parte decimal, o es ≥ 100 y no es un año
    suelto. Se excluyen marcadores («Paso 3»), números de lista al inicio de línea, fechas y versiones.
    """
    salida: list[dict] = []
    for m in RX_NUMERO.finditer(texto):
        tok = m.group(1)
        ini, fin = m.start(1), m.end(1)
        ini_linea = texto.rfind("\n", 0, ini) + 1
        previo = texto[ini_linea:ini]
        if re.fullmatch(r"\s*[-*•]?\s*", previo) and texto[fin:fin + 1] in {".", ")"}:
            continue  # «1. » al inicio de línea: marcador de lista
        if RX_MARCADOR.search(previo):
            continue
        valor, banderas = interpretar_numero(tok, locale)
        if valor is None:
            continue
        resto = texto[fin:fin + 24]
        unidad = RX_UNIDAD_ADYACENTE.match(resto)
        con_moneda_previa = bool(RX_UNIDAD_PREVIA.search(texto[max(0, ini - 4):ini]))
        es_anio = bool(re.fullmatch(r"(19|20)\d{2}", tok)) and not unidad and not con_moneda_previa
        decimal = valor != valor.to_integral_value()
        grande = valor >= 100 and not es_anio
        salida.append({
            "token": tok, "valor": valor, "banderas": banderas, "inicio": ini,
            "linea": texto.count("\n", 0, ini) + 1,
            "unidad": unidad.group(0).strip() if unidad else ("moneda" if con_moneda_previa else None),
            "cifra_de_hecho": bool(unidad) or con_moneda_previa or decimal or grande,
        })
    return salida


# --------------------------------------------------------------------------------------------------
# Hallazgos y salida
# --------------------------------------------------------------------------------------------------
def hallazgo(check_id: str, severidad: str, mensaje: str, evidencia: str | None = None, patron_clave: str | None = None) -> dict:
    assert severidad in SEVERIDADES, severidad
    h = {"check_id": check_id, "severidad": severidad, "mensaje": mensaje}
    if evidencia:
        h["evidencia"] = evidencia
    if patron_clave:
        h["patron_clave"] = patron_clave
    return h


def codigo_de_salida(hallazgos: list[dict]) -> int:
    return 1 if any(h["severidad"] in ("BLOQUEANTE", "MAYOR") for h in hallazgos) else 0


def emitir(nombre: str, checks: list[str], hallazgos: list[dict], resumen: dict, salida: str | None = None) -> int:
    res = {
        "script": nombre, "version": VERSION, "check_ids": checks,
        "resultado": "fail" if codigo_de_salida(hallazgos) else "pass",
        "hallazgos": hallazgos, "resumen": resumen,
    }
    txt = json.dumps(res, ensure_ascii=False, indent=2, default=str)
    print(txt)
    if salida:
        Path(salida).write_text(txt + "\n", encoding="utf-8")
    return codigo_de_salida(hallazgos)


def error_uso(msg: str, codigo: int = 2) -> int:
    print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stderr)
    return codigo
