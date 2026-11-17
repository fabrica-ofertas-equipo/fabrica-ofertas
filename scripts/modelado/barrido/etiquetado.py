#!/usr/bin/env python3
"""Etiquetado automático por IA del barrido por forma (D1 Modo D, `departamentos/02-descubrimiento.md` §17, pieza 2).

La IA propone, el código dispone. Un agente etiquetador lee títulos y nombres de página (contenido AJENO,
no confiable) y propone, por página, un tema, un público, un formato y una etiqueta de macro nicho. Este
módulo hace todo lo demás, con reglas fijas que ninguna IA puede aflojar:

  - `empaquetar_lotes`: parte las páginas de una corrida en lotes y escribe el material de entrada de cada uno
    en `empresa/barrido/etiquetas/<corrida_id>/entrada/<lote_id>.json`. El lote lleva SOLO `page_id`, `page_name`,
    países y títulos únicos: ninguna métrica de tracción (el agente no debe adivinar un ranking). Nunca sobrescribe.
  - `validar_etiquetas`: valida la salida del agente contra su entrada con un esquema estricto. REGLA CENTRAL: cada
    `evidencia.titulo` debe existir literalmente (solo se normalizan espacios y mayúsculas/minúsculas) entre los
    títulos de ESA página en la entrada; sin evidencia válida la etiqueta se descarta y la página queda «sin
    etiquetar», jamás con una etiqueta inventada. Un `page_id` ajeno al lote se rechaza; los duplicados se rechazan
    todos. La IA no puede aportar cifras: cualquier campo desconocido (p. ej. `anuncios_activos`) invalida la etiqueta.
  - `consolidar`: junta todos los lotes de una corrida, cuenta la cobertura y escribe `consolidado.json`. Si dos
    lotes etiquetan la misma página gana la de mayor confianza SOLO si no discrepan; si discrepan queda «en_disputa»
    (revisión humana: el código no elige).

`macro_nicho` es una ETIQUETA, no un filtro: ninguna regla de este módulo descarta una página por su macro nicho.
`senales_riesgo` es informativo: nunca descarta nada.

Todo texto de títulos y nombres de página es dato no confiable: se copia y se compara, jamás se interpreta.
Sin red, sin `float` en lo persistido, reloj inyectable (`ahora=`), raíz inyectable (`raiz=`).

Uso de apoyo para el agente (la CLI completa es de `__main__.py`):
    .venv/bin/python -m scripts.modelado.barrido.etiquetado validar <corrida_id> <lote_id>
Códigos de salida: los de `puntaje_modelar` (0 correcto, 2 uso, 3 validación, 5 falta un parámetro).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.modelado.barrido import comun
from scripts.modelado.puntaje_modelar import ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion

SCHEMA_VERSION = "1.0.0"

# Vocabularios cerrados del contrato (`CONTRATO.md` §4 y §4.1). Cambiarlos es cambiar el contrato.
FORMATOS = ("guia_pdf", "ebook", "plantillas", "fichas", "atlas_mapas", "kit_profesional", "curso_video",
            "patrones", "recetario", "planificador", "calculadora", "pack_recursos", "comunidad_o_app",
            "servicio", "producto_fisico", "otro")
FORMATOS_NO_CANDIDATOS = ("comunidad_o_app", "servicio", "producto_fisico")
MACRO_NICHOS = ("salud", "relaciones", "dinero")
SENALES_RIESGO = ("promesa_ingresos", "claim_salud_curativo", "antes_despues", "urgencia_falsa", "otro")
TEMA_INDETERMINADO = "indeterminado"

# Límites de FORMATO del texto libre (no son umbrales de decisión): evitan que un agente secuestrado escriba
# ensayos o cargas útiles en campos que deben ser etiquetas cortas. Se rechaza, nunca se recorta.
LIMITES_TEXTO = {"tema": 80, "tema_slug": 60, "publico": 80, "macro_nicho_motivo": 240, "etiquetador": 80}

CAMPOS_ETIQUETA = ("page_id", "tema", "tema_slug", "publico", "formato", "macro_nicho", "macro_nicho_motivo",
                   "es_oferta_digital_pago_unico", "confianza", "evidencia")
CAMPOS_ETIQUETA_OPCIONALES = ("senales_riesgo",)
CAMPOS_PAGINA_ENTRADA = ("page_id", "page_name", "paises", "titulos")
CAMPOS_SALIDA = ("schema_version", "corrida_id", "lote_id", "etiquetador", "paginas")
CAMPOS_ENTRADA = ("schema_version", "corrida_id", "lote_id", "generado_en", "paginas")

MOTIVOS_SIN_ETIQUETAR = ("etiqueta_rechazada", "salida_invalida", "lote_sin_salida", "sin_titulos", "no_etiquetada")

_RE_DIGITOS = re.compile(r"[0-9]+")
_RE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_RE_CONFIANZA = re.compile(r"[01](?:\.[0-9]{1,6})?")
_RE_PAIS = re.compile(r"[A-Z]{2}")
_UNO = Decimal(1)
_CUATRO_DECIMALES = Decimal("0.0001")


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

def _raiz(raiz: Path | None) -> Path:
    return Path(raiz) if raiz is not None else comun.RAIZ


def _exigir_corrida_id(corrida_id: Any) -> str:
    if not isinstance(corrida_id, str) or not comun.corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido: {corrida_id!r} (se espera AAAA-MM-DD-<letra>)")
    return corrida_id


def _exigir_lote_id(lote_id: Any) -> str:
    if not isinstance(lote_id, str) or not _RE_SLUG.fullmatch(lote_id):
        raise ErrorUso(f"lote_id inválido: {lote_id!r} (kebab-case ASCII, p. ej. lote-001)")
    return lote_id


def dir_etiquetas(corrida_id: str, raiz: Path | None = None) -> Path:
    """`empresa/barrido/etiquetas/<corrida_id>/`."""
    return _raiz(raiz) / "empresa" / "barrido" / "etiquetas" / _exigir_corrida_id(corrida_id)


def ruta_entrada(corrida_id: str, lote_id: str, raiz: Path | None = None) -> Path:
    """Material de un lote: lo escribe `empaquetar_lotes`, lo lee el agente."""
    return dir_etiquetas(corrida_id, raiz) / "entrada" / f"{_exigir_lote_id(lote_id)}.json"


def ruta_salida(corrida_id: str, lote_id: str, raiz: Path | None = None) -> Path:
    """Etiquetas de un lote: las escribe el agente etiquetador, las valida el código."""
    return dir_etiquetas(corrida_id, raiz) / "salida" / f"{_exigir_lote_id(lote_id)}.json"


def ruta_consolidado(corrida_id: str, raiz: Path | None = None) -> Path:
    return dir_etiquetas(corrida_id, raiz) / "consolidado.json"


# ---------------------------------------------------------------------------
# Utilidades de texto (todo texto ajeno es dato)
# ---------------------------------------------------------------------------

def normalizar_titulo(texto: Any) -> str:
    """Forma de comparación de una cita: NFC, espacios colapsados, minúsculas. NO quita acentos ni signos."""
    return " ".join(unicodedata.normalize("NFC", str(texto)).casefold().split())


def _limpio(texto: str, limite: int = 60) -> str:
    """Para mostrar texto ajeno en un mensaje: sin caracteres de control o de formato y recortado."""
    visible = "".join("?" if unicodedata.category(c).startswith("C") else c for c in texto)
    return visible if len(visible) <= limite else visible[:limite] + "…"


def _mostrar(valor: Any) -> str:
    if isinstance(valor, str):
        return f"«{_limpio(valor)}»"
    return f"un valor de tipo {type(valor).__name__}"


def _tiene_caracteres_de_control(texto: str) -> bool:
    return any(unicodedata.category(c).startswith("C") for c in texto)


class _Rechazo(Exception):
    """Motivo por el que se descarta UNA etiqueta (no el lote entero)."""


# ---------------------------------------------------------------------------
# Parámetros y páginas de entrada
# ---------------------------------------------------------------------------

def _parametro_entero(par_barrido: Any, clave: str) -> int:
    """Entero ≥ 1 de `parametros_barrido`. Falla cerrado: sin parámetro no se asume ningún valor."""
    if not isinstance(par_barrido, Mapping) or clave not in par_barrido:
        raise ErrorLimite(f"falta el parámetro {clave} (parametros_barrido.propuesta.yaml): no se asume ningún valor")
    valor = par_barrido[clave]
    if isinstance(valor, Decimal) and valor == valor.to_integral_value():
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ErrorLimite(f"{clave}: se esperaba un entero ≥ 1, llegó {valor!r}")
    return valor


def _id_de_pagina(valor: Any, campo: str) -> str:
    """`page_id` del material propio (Páginas de B2): cadena de dígitos; se tolera el entero del conector."""
    if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0:
        try:
            return str(valor)
        except ValueError as exc:  # entero con miles de cifras: no es un page_id
            raise ErrorValidacion(f"{campo}: page_id inutilizable") from exc
    if isinstance(valor, str) and _RE_DIGITOS.fullmatch(valor):
        return valor
    raise ErrorValidacion(f"{campo}: page_id debe ser una cadena de dígitos, llegó {valor!r}")


def _clave_id(page_id: str) -> tuple[int, str]:
    """Orden numérico de ids de dígitos sin convertirlos a `int` (un id de miles de cifras no debe romper nada)."""
    return len(page_id), page_id


def _titulos_unicos(titulos: Any, campo: str, maximo: int | None) -> list[str]:
    """Títulos sin vacíos ni repetidos (comparados como en la verificación de citas), en orden, con tope."""
    if not isinstance(titulos, list):
        raise ErrorValidacion(f"{campo}: se esperaba una lista de títulos")
    vistos: set[str] = set()
    salida: list[str] = []
    for i, titulo in enumerate(titulos):
        if not isinstance(titulo, str):
            raise ErrorValidacion(f"{campo}[{i}]: el título debe ser texto, llegó {type(titulo).__name__}")
        clave = normalizar_titulo(titulo)
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        salida.append(titulo)
        if maximo is not None and len(salida) >= maximo:
            break
    return salida


def _leer_paginas(paginas_doc: Any, max_titulos: int) -> tuple[str, list[dict[str, Any]]]:
    """Valida el documento de Páginas (contrato §4) y extrae SOLO lo que el etiquetador puede ver."""
    if not isinstance(paginas_doc, Mapping):
        raise ErrorValidacion("paginas_doc: se esperaba un objeto")
    corrida_id = paginas_doc.get("corrida_id")
    if not isinstance(corrida_id, str) or not comun.corrida_id_valido(corrida_id):
        raise ErrorValidacion(f"paginas_doc.corrida_id inválido: {corrida_id!r}")
    paginas = paginas_doc.get("paginas")
    if not isinstance(paginas, list):
        raise ErrorValidacion("paginas_doc.paginas: se esperaba una lista")
    salida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for i, pagina in enumerate(paginas):
        ruta = f"paginas_doc.paginas[{i}]"
        if not isinstance(pagina, Mapping):
            raise ErrorValidacion(f"{ruta}: se esperaba un objeto")
        for campo in ("page_id", "page_name", "paises", "titulos"):
            if campo not in pagina:
                raise ErrorValidacion(f"{ruta}: falta el campo {campo}")
        page_id = _id_de_pagina(pagina["page_id"], f"{ruta}.page_id")
        if page_id in vistos:
            raise ErrorValidacion(f"{ruta}.page_id: {page_id} repetido")
        vistos.add(page_id)
        if pagina["page_name"] is not None and not isinstance(pagina["page_name"], str):
            raise ErrorValidacion(f"{ruta}.page_name: se esperaba texto o null")
        paises = pagina["paises"]
        if not isinstance(paises, list) or any(not isinstance(p, str) or not _RE_PAIS.fullmatch(p) for p in paises):
            raise ErrorValidacion(f"{ruta}.paises: se esperaba una lista de códigos ISO-2 en mayúsculas")
        salida.append({"page_id": page_id, "page_name": pagina["page_name"],
                       "paises": sorted(set(paises)),
                       "titulos": _titulos_unicos(pagina["titulos"], f"{ruta}.titulos", max_titulos)})
    salida.sort(key=lambda p: _clave_id(p["page_id"]))
    return corrida_id, salida


# ---------------------------------------------------------------------------
# 1. Empaquetar lotes
# ---------------------------------------------------------------------------

def empaquetar_lotes(paginas_doc: Any, *, par_barrido: Mapping[str, Any], raiz: Path | None = None,
                     ahora: datetime | None = None) -> list[dict[str, Any]]:
    """Parte las páginas en lotes de `barrido_paginas_por_lote_etiquetado` y escribe sus archivos de entrada.

    Cada página lleva `page_id`, `page_name`, `paises` y hasta `barrido_titulos_por_pagina_max` títulos únicos.
    NADA más: ni anuncios, ni edades, ni conteos (el etiquetador no necesita ni debe ver cifras). Las páginas se
    ordenan por `page_id` numérico, así que el reparto depende solo del conjunto de páginas, no del orden de llegada.
    Una página sin títulos viaja con `titulos: []` (no tiene qué citar: el agente no debe etiquetarla).

    Devuelve los lotes (lo mismo que se escribió). Sin páginas devuelve `[]` y no escribe nada.
    Errores: ErrorLimite si falta un parámetro; ErrorValidacion si `paginas_doc` no cumple el contrato;
    ErrorUso si algún archivo de destino ya existe (no se sobrescribe y no se escribe ninguno).
    """
    por_lote = _parametro_entero(par_barrido, "barrido_paginas_por_lote_etiquetado")
    max_titulos = _parametro_entero(par_barrido, "barrido_titulos_por_pagina_max")
    corrida_id, paginas = _leer_paginas(paginas_doc, max_titulos)
    if not paginas:
        return []
    generado_en = comun.iso_z(ahora if ahora is not None else comun.ahora_utc())
    trozos = [paginas[i:i + por_lote] for i in range(0, len(paginas), por_lote)]
    ancho = max(3, len(str(len(trozos))))
    lotes = [{"schema_version": SCHEMA_VERSION, "corrida_id": corrida_id, "lote_id": f"lote-{n:0{ancho}d}",
              "generado_en": generado_en, "paginas": trozo} for n, trozo in enumerate(trozos, 1)]
    destinos = [ruta_entrada(corrida_id, lote["lote_id"], raiz) for lote in lotes]
    for destino in destinos:
        if destino.exists():
            raise ErrorUso(f"{destino} ya existe: no se sobrescribe. Usa otra corrida o borra los lotes a mano")
    destinos[0].parent.mkdir(parents=True, exist_ok=True)
    ruta_salida(corrida_id, lotes[0]["lote_id"], raiz).parent.mkdir(parents=True, exist_ok=True)
    for destino, lote in zip(destinos, lotes):
        comun.escribir_json_nuevo(destino, lote)
    return lotes


# ---------------------------------------------------------------------------
# 2. Validar la salida del agente
# ---------------------------------------------------------------------------

def _indexar_entrada(entrada_doc: Any) -> dict[str, Any]:
    """Valida el material de un lote (lo escribió este módulo) y lo indexa para verificar citas."""
    if not isinstance(entrada_doc, Mapping):
        raise ErrorValidacion("entrada: se esperaba un objeto")
    _exigir_claves(entrada_doc, CAMPOS_ENTRADA, (), "entrada")
    if entrada_doc["schema_version"] != SCHEMA_VERSION:
        raise ErrorValidacion(f"entrada.schema_version: {entrada_doc['schema_version']!r} no soportada")
    corrida_id, lote_id = entrada_doc["corrida_id"], entrada_doc["lote_id"]
    if not isinstance(corrida_id, str) or not comun.corrida_id_valido(corrida_id):
        raise ErrorValidacion(f"entrada.corrida_id inválido: {corrida_id!r}")
    if not isinstance(lote_id, str) or not _RE_SLUG.fullmatch(lote_id):
        raise ErrorValidacion(f"entrada.lote_id inválido: {lote_id!r}")
    if not isinstance(entrada_doc["paginas"], list):
        raise ErrorValidacion("entrada.paginas: se esperaba una lista")
    paginas: dict[str, dict[str, Any]] = {}
    for i, pagina in enumerate(entrada_doc["paginas"]):
        ruta = f"entrada.paginas[{i}]"
        if not isinstance(pagina, Mapping):
            raise ErrorValidacion(f"{ruta}: se esperaba un objeto")
        _exigir_claves(pagina, CAMPOS_PAGINA_ENTRADA, (), ruta)
        page_id = pagina["page_id"]
        if not isinstance(page_id, str) or not _RE_DIGITOS.fullmatch(page_id):
            raise ErrorValidacion(f"{ruta}.page_id: se esperaba una cadena de dígitos")
        if page_id in paginas:
            raise ErrorValidacion(f"{ruta}.page_id: {page_id} repetido en la entrada")
        if pagina["page_name"] is not None and not isinstance(pagina["page_name"], str):
            raise ErrorValidacion(f"{ruta}.page_name: se esperaba texto o null")
        titulos = _titulos_unicos(pagina["titulos"], f"{ruta}.titulos", None)
        por_clave: dict[str, str] = {}
        for titulo in titulos:
            por_clave.setdefault(normalizar_titulo(titulo), titulo)
        paginas[page_id] = {"page_name": pagina["page_name"], "titulos": titulos, "por_clave": por_clave}
    return {"corrida_id": corrida_id, "lote_id": lote_id, "paginas": paginas}


def _exigir_claves(objeto: Mapping[str, Any], requeridas: Sequence[str], opcionales: Sequence[str], ruta: str) -> None:
    faltan = sorted(set(requeridas) - set(objeto))
    sobran = sorted(set(objeto) - set(requeridas) - set(opcionales))
    if faltan:
        raise ErrorValidacion(f"{ruta}: faltan campos {faltan}")
    if sobran:
        raise ErrorValidacion(f"{ruta}: campos no reconocidos {sobran}")


def _validar_cabecera_salida(salida_doc: Any, entrada: Mapping[str, Any]) -> str:
    """Cabecera de la salida: un archivo con otra corrida/lote (o sin formato) no se usa. Devuelve `etiquetador`."""
    if not isinstance(salida_doc, Mapping):
        raise ErrorValidacion("salida: se esperaba un objeto")
    _exigir_claves(salida_doc, CAMPOS_SALIDA, (), "salida")
    if salida_doc["schema_version"] != SCHEMA_VERSION:
        raise ErrorValidacion(f"salida.schema_version: {salida_doc['schema_version']!r}; se esperaba {SCHEMA_VERSION!r}")
    if salida_doc["corrida_id"] != entrada["corrida_id"]:
        raise ErrorValidacion(f"salida.corrida_id {_mostrar(salida_doc['corrida_id'])} no es la de la entrada "
                              f"({entrada['corrida_id']})")
    if salida_doc["lote_id"] != entrada["lote_id"]:
        raise ErrorValidacion(f"salida.lote_id {_mostrar(salida_doc['lote_id'])} no es el de la entrada "
                              f"({entrada['lote_id']})")
    etiquetador = salida_doc["etiquetador"]
    try:
        etiquetador = _texto_corto(etiquetador, "etiquetador", LIMITES_TEXTO["etiquetador"])
    except _Rechazo as exc:
        raise ErrorValidacion(f"salida.{exc}") from exc
    if not isinstance(salida_doc["paginas"], list):
        raise ErrorValidacion("salida.paginas: se esperaba una lista")
    return etiquetador


# Revisión de seguridad M4: el texto libre de la IA (derivado de títulos ajenos) acaba en fichas, informes y consolas.
# Se RECHAZA (nunca se recorta ni se «limpia» en silencio) lo que sirve para HTML, Markdown, enlaces o menciones.
MARCADO_PROHIBIDO = ("<", ">", "[", "]", "`", "|", "*", "@", "://", "www.")


def _marcado_prohibido(texto: str) -> str | None:
    """Primer patrón de `MARCADO_PROHIBIDO` presente, mirando también la forma NFKC (`＠`, `［`, `ｗｗｗ．` valen igual)."""
    for variante in (texto, unicodedata.normalize("NFKC", texto)):
        bajo = variante.casefold()
        for patron in MARCADO_PROHIBIDO:
            if patron in bajo:
                return patron
    return None


def _texto_corto(valor: Any, campo: str, maximo: int, *, vacio_ok: bool = False, sin_marcado: bool = False) -> str:
    """Texto libre corto y limpio. Rechaza (con `_Rechazo`) tipo erróneo, categoría Unicode «C» (controles, bidi, ancho
    cero, privados), vacío, exceso de largo y, con `sin_marcado`, HTML/Markdown/enlaces/menciones."""
    if not isinstance(valor, str):
        raise _Rechazo(f"{campo}: se esperaba texto, llegó {type(valor).__name__}")
    if _tiene_caracteres_de_control(valor):
        raise _Rechazo(f"{campo}: tiene caracteres de control o de formato")
    if sin_marcado:
        patron = _marcado_prohibido(valor)
        if patron is not None:
            raise _Rechazo(f"{campo}: contiene marcado, enlaces o menciones no permitidos ({patron!r}); "
                           "reescríbelo como texto llano")
    limpio = re.sub(r"\s+", " ", valor).strip()
    if not limpio and not vacio_ok:
        raise _Rechazo(f"{campo}: está vacío")
    if len(limpio) > maximo:
        raise _Rechazo(f"{campo}: {len(limpio)} caracteres; el máximo es {maximo}")
    return limpio


def _normalizar_etiqueta(crudo: Mapping[str, Any], pagina: Mapping[str, Any]) -> dict[str, Any]:
    """Esquema estricto de UNA etiqueta. Lanza `_Rechazo` con el primer motivo."""
    faltan = sorted(set(CAMPOS_ETIQUETA) - set(crudo))
    sobran = sorted(set(crudo) - set(CAMPOS_ETIQUETA) - set(CAMPOS_ETIQUETA_OPCIONALES))
    if faltan:
        raise _Rechazo(f"faltan campos {faltan}")
    if sobran:
        raise _Rechazo("campos no reconocidos " + str([_limpio(str(c), 30) for c in sobran[:5]])
                       + " (la IA no aporta cifras ni campos extra)")
    tema = _texto_corto(crudo["tema"], "tema", LIMITES_TEXTO["tema"], sin_marcado=True)
    tema_slug = crudo["tema_slug"]
    if (not isinstance(tema_slug, str) or not _RE_SLUG.fullmatch(tema_slug) or tema_slug.isdigit()
            or len(tema_slug) > LIMITES_TEXTO["tema_slug"]):
        raise _Rechazo(f"tema_slug {_mostrar(tema_slug)} no es kebab-case ASCII con al menos una letra "
                       f"(minúsculas, dígitos y guiones; máx. {LIMITES_TEXTO['tema_slug']}; "
                       "un slug solo de dígitos se confundiría con un page_id)")
    publico = _texto_corto(crudo["publico"], "publico", LIMITES_TEXTO["publico"], sin_marcado=True)
    formato = crudo["formato"]
    if not isinstance(formato, str) or formato not in FORMATOS:
        raise _Rechazo(f"formato {_mostrar(formato)} fuera del enum {list(FORMATOS)}")
    macro_nicho = crudo["macro_nicho"]
    if macro_nicho is not None and (not isinstance(macro_nicho, str) or macro_nicho not in MACRO_NICHOS):
        raise _Rechazo(f"macro_nicho {_mostrar(macro_nicho)} fuera del enum {list(MACRO_NICHOS)} o null")
    motivo = crudo["macro_nicho_motivo"]
    if motivo is None:
        motivo = ""
    motivo = _texto_corto(motivo, "macro_nicho_motivo", LIMITES_TEXTO["macro_nicho_motivo"],
                          vacio_ok=macro_nicho is None, sin_marcado=True)
    es_oferta = crudo["es_oferta_digital_pago_unico"]
    if es_oferta is not None and not isinstance(es_oferta, bool):
        raise _Rechazo("es_oferta_digital_pago_unico debe ser true, false o null (booleano JSON, no texto)")
    confianza = crudo["confianza"]
    if not isinstance(confianza, str) or not _RE_CONFIANZA.fullmatch(confianza) or Decimal(confianza) > _UNO:
        raise _Rechazo(f"confianza {_mostrar(confianza)} debe ser una cadena decimal entre \"0.0\" y \"1.0\"")
    indeterminada = tema_slug == TEMA_INDETERMINADO or tema.casefold() == TEMA_INDETERMINADO
    if indeterminada:
        if tema_slug != TEMA_INDETERMINADO or tema.casefold() != TEMA_INDETERMINADO:
            raise _Rechazo("tema y tema_slug deben ser ambos \"indeterminado\"")
        if es_oferta is not None or macro_nicho is not None:
            raise _Rechazo("un tema indeterminado exige es_oferta_digital_pago_unico y macro_nicho en null")
    elif macro_nicho is not None and not motivo:
        raise _Rechazo("macro_nicho exige macro_nicho_motivo")
    evidencia = _normalizar_evidencia(crudo["evidencia"], pagina)
    senales, avisos = _normalizar_senales(crudo.get("senales_riesgo"))
    return {"page_id": crudo["page_id"], "tema": tema, "tema_slug": tema_slug, "publico": publico,
            "formato": formato, "macro_nicho": macro_nicho, "macro_nicho_motivo": motivo,
            "es_oferta_digital_pago_unico": es_oferta, "confianza": confianza, "evidencia": evidencia,
            "senales_riesgo": senales, "avisos": avisos}


def _normalizar_evidencia(evidencia: Any, pagina: Mapping[str, Any]) -> list[dict[str, str]]:
    """REGLA CENTRAL: cada título citado existe, tal cual, entre los títulos de ESTA página.

    Solo se normalizan espacios y mayúsculas/minúsculas (y la forma Unicode compuesta). Una cita parcial, con
    otro acento o de otra página no vale. Si UNA cita falla, se descarta la etiqueta entera: un agente que cita
    algo inexistente no es fiable en esa página. En lo guardado, el título es el literal de la entrada.
    """
    if not isinstance(evidencia, list) or not evidencia:
        raise _Rechazo("evidencia: se exige una lista con al menos una cita; sin evidencia no hay etiqueta")
    citados: list[str] = []
    for i, item in enumerate(evidencia):
        if not isinstance(item, Mapping) or set(item) != {"titulo"}:
            raise _Rechazo(f"evidencia[{i}]: se esperaba exactamente {{\"titulo\": texto}}")
        titulo = item["titulo"]
        if not isinstance(titulo, str):
            raise _Rechazo(f"evidencia[{i}].titulo: se esperaba texto, llegó {type(titulo).__name__}")
        clave = normalizar_titulo(titulo)
        if not clave:
            raise _Rechazo(f"evidencia[{i}].titulo: está vacío")
        literal = pagina["por_clave"].get(clave)
        if literal is None:
            raise _Rechazo(f"evidencia[{i}].titulo {_mostrar(titulo)} no aparece, tal cual, entre los títulos de "
                           "esa página en la entrada del lote (la cita debe ser el título completo y textual)")
        if literal not in citados:
            citados.append(literal)
    return [{"titulo": t} for t in citados]


def _normalizar_senales(crudo: Any) -> tuple[list[str], list[str]]:
    """`senales_riesgo` es informativo: lo desconocido se descarta con un aviso, nunca se descarta la etiqueta."""
    if crudo is None:
        return [], []
    if not isinstance(crudo, list):
        return [], ["senales_riesgo ignoradas: se esperaba una lista"]
    validas: set[str] = set()
    avisos: list[str] = []
    for valor in crudo:
        if isinstance(valor, str) and valor in SENALES_RIESGO:
            validas.add(valor)
        else:
            avisos.append(f"señal de riesgo {_mostrar(valor)} desconocida; ignorada")
    return [s for s in SENALES_RIESGO if s in validas], avisos


def _validar(salida_doc: Any, entrada: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    etiquetador = _validar_cabecera_salida(salida_doc, entrada)
    crudas = salida_doc["paginas"]
    ids: list[str | None] = []
    for etiqueta in crudas:
        valor = etiqueta.get("page_id") if isinstance(etiqueta, Mapping) else None
        ids.append(valor if isinstance(valor, str) and _RE_DIGITOS.fullmatch(valor) else None)
    veces: dict[str, int] = {}
    for page_id in ids:
        if page_id is not None:
            veces[page_id] = veces.get(page_id, 0) + 1
    aceptadas: list[dict[str, Any]] = []
    rechazadas: list[dict[str, Any]] = []
    for indice, (crudo, page_id) in enumerate(zip(crudas, ids)):
        try:
            if not isinstance(crudo, Mapping):
                raise _Rechazo("la etiqueta no es un objeto")
            if page_id is None:
                raise _Rechazo("page_id ausente o no es una cadena de dígitos")
            if page_id not in entrada["paginas"]:
                raise _Rechazo("page_id ajeno: no estaba en la entrada de este lote")
            if veces[page_id] > 1:
                raise _Rechazo(f"page_id repetido {veces[page_id]} veces en la salida: se rechazan todas sus apariciones")
            aceptadas.append(_normalizar_etiqueta(crudo, entrada["paginas"][page_id]))
        except _Rechazo as exc:
            rechazadas.append({"indice": indice, "page_id": page_id, "motivo": str(exc)})
    return aceptadas, rechazadas, etiquetador


def validar_etiquetas(salida_doc: Any, entrada_doc: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Valida la salida de un agente etiquetador contra el material de su lote.

    Devuelve `(aceptadas, rechazadas_con_motivo)`:
      - `aceptadas`: etiquetas normalizadas (con `evidencia` = literales de la entrada, `senales_riesgo` y `avisos`).
      - `rechazadas_con_motivo`: `{"indice", "page_id" (o None), "motivo"}` por cada etiqueta descartada.
    Una página sin etiqueta aceptada queda «sin etiquetar»; nunca se rellena. Orden = orden de la salida.

    Errores (el archivo entero es inutilizable): ErrorValidacion si la entrada está mal formada o la cabecera de la
    salida no corresponde (otra corrida, otro lote, formato distinto, sin `etiquetador`).
    """
    aceptadas, rechazadas, _ = _validar(salida_doc, _indexar_entrada(entrada_doc))
    return aceptadas, rechazadas


def validar_lote(corrida_id: str, lote_id: str, *, raiz: Path | None = None) -> dict[str, Any]:
    """Valida el archivo de salida de un lote contra su entrada y devuelve un informe para el agente.

    `ok` solo si no hay rechazos y todas las páginas con títulos quedaron etiquetadas. Las páginas sin títulos
    no se esperan en la salida (no tienen qué citar) y se listan aparte en `sin_titulos`.
    """
    ruta_e, ruta_s = ruta_entrada(corrida_id, lote_id, raiz), ruta_salida(corrida_id, lote_id, raiz)
    if not ruta_e.is_file():
        raise ErrorUso(f"no existe la entrada del lote: {ruta_e}")
    if not ruta_s.is_file():
        raise ErrorUso(f"no existe la salida del lote: {ruta_s} (el agente aún no la escribió)")
    entrada = _indexar_entrada(comun.leer_json(ruta_e))
    aceptadas, rechazadas, etiquetador = _validar(comun.leer_json(ruta_s), entrada)
    etiquetadas = {a["page_id"] for a in aceptadas}
    sin_etiquetar = [p for p in entrada["paginas"] if p not in etiquetadas and entrada["paginas"][p]["titulos"]]
    sin_titulos = [p for p in entrada["paginas"] if p not in etiquetadas and not entrada["paginas"][p]["titulos"]]
    return {"corrida_id": corrida_id, "lote_id": lote_id, "etiquetador": etiquetador,
            "paginas_en_entrada": len(entrada["paginas"]), "aceptadas": len(aceptadas),
            "rechazadas": rechazadas, "sin_etiquetar": sin_etiquetar, "sin_titulos": sin_titulos,
            "ok": not rechazadas and not sin_etiquetar}


# ---------------------------------------------------------------------------
# 3. Consolidar
# ---------------------------------------------------------------------------

def avanza_a_candidata(etiqueta: Mapping[str, Any]) -> bool:
    """Regla de `CONTRATO.md` §4 y §4.1 (cambio de diseño 2026-11-06: fail-open en descubrimiento, fail-closed al
    lanzar): avanza toda página cuyo `es_oferta_digital_pago_unico` sea `true` O `null` («no sé»: el etiquetador solo ve
    el título del enlace y no puede saber el modelo de cobro; la captura de la ficha/landing lo aclara) y cuyo formato no
    sea comunidad/app, servicio ni producto físico. NO avanza con `false` ni con formato excluido. Cualquier otra queda
    registrada, no descartada en silencio. Un tema `indeterminado` pasa este filtro igual; si agrupa o no lo decide el
    ranking (solo avanza con tracción, como «sin_tema»)."""
    return etiqueta["es_oferta_digital_pago_unico"] is not False and etiqueta["formato"] not in FORMATOS_NO_CANDIDATOS


def _discrepancias(candidatas: Sequence[Mapping[str, Any]]) -> list[str]:
    """Campos en los que dos lotes se contradicen. `macro_nicho` y `formato` por contrato; además, un
    `true` contra un `false` en `es_oferta_digital_pago_unico` (decide si la página avanza). Un `null` («no sé»)
    no contradice."""
    campos = []
    if len({c["macro_nicho"] for c in candidatas}) > 1:
        campos.append("macro_nicho")
    if len({c["formato"] for c in candidatas}) > 1:
        campos.append("formato")
    if len({c["es_oferta_digital_pago_unico"] for c in candidatas} - {None}) > 1:
        campos.append("es_oferta_digital_pago_unico")
    return campos


def _resolver(candidatas: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """('etiquetada', etiqueta) o ('en_disputa', registro). `candidatas` viene ordenada por `lote_id`.

    Un «indeterminado» es una ausencia de opinión, no una contradicción: si otro lote sí opinó, se ignora para
    decidir (y se anota en `lotes_sin_opinion`). Si todos son indeterminados, la página queda indeterminada.
    """
    page_id = candidatas[0]["page_id"]
    opinan = [c for c in candidatas if c["tema_slug"] != TEMA_INDETERMINADO]
    sin_opinion = [c["lote_id"] for c in candidatas if c["tema_slug"] == TEMA_INDETERMINADO] if opinan else []
    opinan = opinan or candidatas
    discrepancias = _discrepancias(opinan)
    if discrepancias:
        return "en_disputa", {"page_id": page_id, "discrepancias": discrepancias, "candidatas": candidatas}
    ganadora = opinan[0]
    for candidata in opinan[1:]:
        if Decimal(candidata["confianza"]) > Decimal(ganadora["confianza"]):
            ganadora = candidata
    resultado = dict(ganadora)
    resultado["lotes_coincidentes"] = [c["lote_id"] for c in opinan if c is not ganadora]
    resultado["lotes_sin_opinion"] = sin_opinion
    resultado["avanza_a_candidata"] = avanza_a_candidata(ganadora)
    return "etiquetada", resultado


def _leer_lotes_entrada(corrida_id: str, raiz: Path | None) -> list[tuple[str, dict[str, Any]]]:
    carpeta = dir_etiquetas(corrida_id, raiz) / "entrada"
    archivos = sorted(carpeta.glob("*.json")) if carpeta.is_dir() else []
    if not archivos:
        raise ErrorUso(f"no hay lotes de entrada en {carpeta}: ¿se empaquetó la corrida {corrida_id}?")
    lotes = []
    for archivo in archivos:
        entrada = _indexar_entrada(comun.leer_json(archivo))
        if entrada["corrida_id"] != corrida_id or entrada["lote_id"] != archivo.stem:
            raise ErrorValidacion(f"{archivo}: su corrida_id/lote_id no coincide con la ruta; el lote no es confiable")
        lotes.append((entrada["lote_id"], entrada))
    return lotes


def _tasa(parte: int, total: int) -> str | None:
    """Proporción como cadena decimal de 4 cifras; `null` si no hay páginas (jamás 0 inventado)."""
    if total == 0:
        return None
    return format((Decimal(parte) / Decimal(total)).quantize(_CUATRO_DECIMALES, rounding=ROUND_HALF_EVEN), "f")


def _escribir_reemplazando(ruta: Path, doc: Any) -> None:
    """Escritura atómica que sustituye el archivo (solo con `reemplazar=True`)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=ruta.name + ".", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            archivo.write(texto)
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise


def consolidar(corrida_id: str, *, raiz: Path | None = None, ahora: datetime | None = None,
               reemplazar: bool = False) -> dict[str, Any]:
    """Junta los lotes de una corrida y escribe `empresa/barrido/etiquetas/<corrida_id>/consolidado.json`.

    Un lote sin salida, o con una salida inutilizable (JSON roto, otra corrida/lote), NO detiene la
    consolidación: queda registrado y sus páginas cuentan como «sin etiquetar».
    Si dos lotes etiquetan la misma página: gana la de mayor confianza (empate: el `lote_id` menor) solo si no
    discrepan en `macro_nicho`, `formato` ni en un `true`/`false` de `es_oferta_digital_pago_unico`; si discrepan queda
    «en_disputa» con todas las candidatas, para revisión humana (el código no elige).
    Cobertura: cada página de las entradas está en exactamente una de `etiquetadas`, `en_disputa` o `sin_etiquetar`.

    No sobrescribe un consolidado existente salvo `reemplazar=True`.
    Errores: ErrorUso (corrida inválida, sin lotes, consolidado existente); ErrorValidacion (entrada corrupta).
    """
    _exigir_corrida_id(corrida_id)
    destino = ruta_consolidado(corrida_id, raiz)
    if destino.exists() and not reemplazar:
        raise ErrorUso(f"{destino} ya existe: no se sobrescribe (usa reemplazar=True para reconsolidar)")
    lotes_entrada = _leer_lotes_entrada(corrida_id, raiz)
    generado_en = comun.iso_z(ahora if ahora is not None else comun.ahora_utc())

    informe_lotes: list[dict[str, Any]] = []
    estado_lote: dict[str, str] = {}
    candidatas: dict[str, list[dict[str, Any]]] = {}
    rechazadas: list[dict[str, Any]] = []
    paginas: dict[str, dict[str, Any]] = {}
    for lote_id, entrada in lotes_entrada:
        for page_id, pagina in entrada["paginas"].items():
            info = paginas.setdefault(page_id, {"page_name": pagina["page_name"], "lotes": [], "con_titulos": False})
            info["lotes"].append(lote_id)
            info["con_titulos"] = info["con_titulos"] or bool(pagina["titulos"])
        registro = {"lote_id": lote_id, "estado": "sin_salida", "paginas_en_entrada": len(entrada["paginas"]),
                    "etiquetador": None, "aceptadas": 0, "rechazadas": 0, "motivo": None}
        ruta_s = ruta_salida(corrida_id, lote_id, raiz)
        if ruta_s.exists():
            try:
                aceptadas, rechazos, etiquetador = _validar(comun.leer_json(ruta_s), entrada)
            except ErrorFabrica as exc:
                registro.update(estado="salida_invalida", motivo=_limpio(str(exc), 300))
            else:
                registro.update(estado="validada", etiquetador=etiquetador, aceptadas=len(aceptadas),
                                rechazadas=len(rechazos))
                for etiqueta in aceptadas:
                    candidata = dict(etiqueta)
                    candidata.update(lote_id=lote_id, etiquetador=etiquetador)
                    candidatas.setdefault(etiqueta["page_id"], []).append(candidata)
                rechazadas += [{"lote_id": lote_id, **r} for r in rechazos]
        estado_lote[lote_id] = registro["estado"]
        informe_lotes.append(registro)

    etiquetas: list[dict[str, Any]] = []
    disputas: list[dict[str, Any]] = []
    for page_id in sorted(candidatas, key=_clave_id):
        estado, resultado = _resolver(sorted(candidatas[page_id], key=lambda c: c["lote_id"]))
        (etiquetas if estado == "etiquetada" else disputas).append(resultado)

    con_rechazo = {r["page_id"] for r in rechazadas
                   if r["page_id"] is not None and r["page_id"] in paginas
                   and any(r["lote_id"] == lote for lote in paginas[r["page_id"]]["lotes"])}
    etiquetadas_ids = {e["page_id"] for e in etiquetas}
    disputa_ids = {d["page_id"] for d in disputas}
    sin_etiquetar: list[dict[str, Any]] = []
    for page_id in sorted(paginas, key=_clave_id):
        if page_id in etiquetadas_ids or page_id in disputa_ids:
            continue
        info = paginas[page_id]
        estados = {estado_lote[lote] for lote in info["lotes"]}
        if page_id in con_rechazo:
            motivo = "etiqueta_rechazada"
        elif "salida_invalida" in estados:
            motivo = "salida_invalida"
        elif "sin_salida" in estados:
            motivo = "lote_sin_salida"
        elif not info["con_titulos"]:
            motivo = "sin_titulos"
        else:
            motivo = "no_etiquetada"
        sin_etiquetar.append({"page_id": page_id, "page_name": info["page_name"], "motivo": motivo})

    total = len(paginas)
    indeterminadas = sum(1 for e in etiquetas if e["tema_slug"] == TEMA_INDETERMINADO)
    cobertura = {
        "paginas_total": total,
        "etiquetadas": len(etiquetas),
        "indeterminadas": indeterminadas,
        "en_disputa": len(disputas),
        "sin_etiquetar": len(sin_etiquetar),
        "rechazadas": len(rechazadas),
        "avanzan_a_candidata": sum(1 for e in etiquetas if e["avanza_a_candidata"]),
        "tasa_etiquetadas": _tasa(len(etiquetas), total),
        "tasa_con_tema": _tasa(len(etiquetas) - indeterminadas, total),
        "lotes_total": len(informe_lotes),
        "lotes_validados": sum(1 for lote in informe_lotes if lote["estado"] == "validada"),
        "lotes_sin_salida": sum(1 for lote in informe_lotes if lote["estado"] == "sin_salida"),
        "lotes_salida_invalida": sum(1 for lote in informe_lotes if lote["estado"] == "salida_invalida"),
    }
    consolidado = {"schema_version": SCHEMA_VERSION, "corrida_id": corrida_id, "generado_en": generado_en,
                   "cobertura": cobertura, "lotes": informe_lotes, "etiquetas": etiquetas,
                   "en_disputa": disputas, "sin_etiquetar": sin_etiquetar, "rechazadas": rechazadas}
    if reemplazar:
        _escribir_reemplazando(destino, consolidado)
    else:
        destino.parent.mkdir(parents=True, exist_ok=True)
        comun.escribir_json_nuevo(destino, consolidado)
    return consolidado


def temas_por_pagina(consolidado: Mapping[str, Any]) -> dict[str, str]:
    """`{page_id: tema_slug}` de las páginas con un tema real, para `memoria.guardar(etiquetas=...)`.

    Excluye las indeterminadas (no hay tema que recordar) y las en disputa (nadie eligió todavía).
    """
    return {e["page_id"]: e["tema_slug"] for e in consolidado["etiquetas"] if e["tema_slug"] != TEMA_INDETERMINADO}


# ---------------------------------------------------------------------------
# CLI mínima de apoyo (la CLI del barrido es de `__main__.py`)
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None, salida=None) -> int:
    """`validar <corrida_id> <lote_id>`: imprime el informe y devuelve 0 si `ok`, 3 si hay algo que corregir."""
    salida = salida or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m scripts.modelado.barrido.etiquetado",
                                     description="Valida la salida de un agente etiquetador contra su lote.")
    sub = parser.add_subparsers(dest="orden", required=True)
    va = sub.add_parser("validar", help="valida empresa/barrido/etiquetas/<corrida_id>/salida/<lote_id>.json")
    va.add_argument("corrida_id")
    va.add_argument("lote_id")
    va.add_argument("--raiz", type=Path, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        informe = validar_lote(args.corrida_id, args.lote_id, raiz=args.raiz)
    except ErrorFabrica as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        return exc.codigo_salida
    print(json.dumps(informe, ensure_ascii=False, indent=2), file=salida)
    return 0 if informe["ok"] else ErrorValidacion.codigo_salida


if __name__ == "__main__":
    raise SystemExit(main())
