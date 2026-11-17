"""Ranking del barrido por forma (B5): páginas etiquetadas → temas rankeados, matriz tema × país,
señal de exportadores y puente a fichas de `puntaje_modelar`.

Contrato: scripts/modelado/barrido/CONTRATO.md §4 («Candidatos»); spec: departamentos/02-descubrimiento.md §12, §15 y
§17 (piezas 4 y 5). Principio del repo: la IA propone (etiquetas), el código dispone (cuenta, umbrales, descartes).

Qué hace
--------
- `rankear`: agrupa las páginas etiquetadas por `tema_slug` (una página = un tema), cuenta anunciantes independientes,
  aplica los umbrales de tracción de `parametros_modelado` y devuelve el documento «Candidatos».
- `matriz_tema_pais`: presencia/ausencia por tema × país. **Ausencia en la MUESTRA no es ausencia en el mercado**:
  es una hipótesis hasta medir con la pasada 3 (`page_ids` × país).
- `exportadores_por_tema`: resumen de la señal de «probable exportador» (B2) por tema. Es un indicio, no un hecho.
- `puente_a_fichas`: una ficha `schema_version "2.0.0"` por página-oferta con tracción, que pasa
  `puntaje_modelar.validar_fichas`. Lo no evaluado va `null`; jamás se inventa un valor.
- `escribir_candidatos` / `escribir_fichas_borrador`: escritura atómica sin sobrescribir.

Reglas que no se negocian
-------------------------
- Ningún umbral está fijo aquí: `modelado_anuncios_objetivo` y `modelado_dias_objetivo` llegan por `par_modelado`;
  si faltan, `ErrorLimite` (5, falla cerrado).
- **Muestra truncada = el conteo es un PISO.** Si el piso ya supera el umbral, cumple. Si no lo supera, el estado es
  `indeterminada_por_muestra` (la pasada 2/3 debe medir mejor): jamás se descarta por un conteo truncado. Vale para
  los anuncios activos y para la edad de la oferta (el 2.º anuncio más viejo de una muestra truncada también es piso).
- Páginas con exactamente los mismos títulos (normalizados) dentro de un tema son «posible mismo operador»: cuentan
  como UN solo anunciante independiente.
- `macro_nicho` es una ETIQUETA (nunca filtra). Si las páginas de un tema discrepan, el tema vale «mixto».
- Las páginas con `es_oferta_digital_pago_unico != true` o formato ∈ {comunidad_o_app, servicio, producto_fisico}
  no avanzan, pero quedan registradas con su motivo (auditoría).
- `entrantes_30d` solo sale de la memoria (B3) y solo con base válida; sin base es `null`, jamás 0 por defecto.
- Texto de la Biblioteca (títulos, nombres) = dato no confiable: se copia limpio, nunca se interpreta.
- Determinista: mismas entradas y mismo `ahora` → mismo documento, sin importar el orden de entrada.
- Sin `float` ni `Decimal` en lo persistido: enteros y cadenas decimales.

Formatos que este módulo LEE además de «Páginas» (B2) y las etiquetas (B4, CONTRATO §4)
---------------------------------------------------------------------------------------
`etiquetas_doc`: el `consolidado.json` de B4 ({corrida_id, etiquetas: [...], en_disputa: [...], sin_etiquetar: [...]})
o un lote ({corrida_id?, paginas: [...]}) o una lista directa de etiquetas {page_id, tema, tema_slug, publico, formato,
macro_nicho, es_oferta_digital_pago_unico, confianza, ...}. Las páginas en `en_disputa` / `sin_etiquetar` quedan
descartadas con ese motivo; un `tema_slug` «indeterminado» no forma tema.
`memoria_diff`: la salida de `memoria.diff` (B3): `estado`, `base_entrantes`, `base_cambios`, `temas_nuevos`,
`temas_estado`, `paginas_nuevas`, `entrantes_30d_por_pais` ({tema_slug: {PAIS: int | null}}); ver `_leer_memoria`.
Sin `estado: "ok"` todo `entrantes_30d` es `null`.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts.modelado import puntaje_modelar as pm
from scripts.modelado.barrido import comun

ErrorLimite = pm.ErrorLimite
ErrorUso = pm.ErrorUso
ErrorValidacion = pm.ErrorValidacion

SCHEMA_VERSION = "1.0.0"          # documento «Candidatos»
SCHEMA_FICHAS = "2.0.0"           # el que exige puntaje_modelar.validar_fichas (fórmula pm-2)

# ---------------------------------------------------------------------------
# Vocabularios cerrados (categorías del contrato, no umbrales)
# ---------------------------------------------------------------------------

FORMATOS = ("guia_pdf", "ebook", "plantillas", "fichas", "atlas_mapas", "kit_profesional", "curso_video",
            "patrones", "recetario", "planificador", "calculadora", "pack_recursos", "comunidad_o_app",
            "servicio", "producto_fisico", "otro")                                   # CONTRATO §4.1
FORMATOS_EXCLUIDOS = ("comunidad_o_app", "servicio", "producto_fisico")              # no avanzan a candidata
MACRO_MIXTO = "mixto"
TEMA_INDETERMINADO = "indeterminado"                                         # etiquetado.TEMA_INDETERMINADO

PASA = "pasa"
NO_PASA = "no_pasa"
INDETERMINADA = "indeterminada_por_muestra"
_ORDEN_ESTADO = {PASA: 0, INDETERMINADA: 1, NO_PASA: 2}

CUMPLE = "cumple"
NO_CUMPLE = "no_cumple"
INDET = "indeterminada"

ESTADO_AUSENCIA = "hipotesis_hasta_pasada_3"
ADVERTENCIA_AUSENCIA = (
    "Ausencia en la MUESTRA del barrido no es ausencia en el mercado: cada hueco es solo una hipótesis hasta medirlo "
    "con la pasada 3 (page_ids × país). El conector entrega como máximo 50 anuncios por consulta.")

MOTIVO_SIN_TITULOS = "sin_etiqueta: sin_titulos"      # motivo con el que B4 deja sin etiqueta a una página sin títulos
ESTADOS_MEDICION = ("completa", "parcial", "muestra")    # medicion.estado de B2 (pasada 3)
FUENTES_MEDICION = ("pagina", "muestra")
_RE_PAIS = re.compile(r"[A-Z]{2}")
_RE_DIGITOS = re.compile(r"[0-9]+")
_RE_CORRIDA_EN_NOTA = re.compile(r"corrida_id=([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z])")
_RE_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")
_RE_PELIGROSO = re.compile(r"[<>\[\]`|*_#!]|://|@")
_SIN_TITULO = "(sin título)"


# ---------------------------------------------------------------------------
# Utilidades pequeñas
# ---------------------------------------------------------------------------

def _ver(valor: Any, largo: int = 60) -> str:
    texto = repr(valor)
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def _limpio(valor: Any, maximo: int = 200) -> str:
    """Texto no confiable → una sola línea, sin caracteres de categoría Unicode «C» (controles, bidi U+202E/U+2066…,
    ancho cero, BOM, sustitutos, uso privado) y con tope de largo. Los controles y saltos se vuelven espacio; el resto
    de la categoría C se elimina."""
    texto = unicodedata.normalize("NFC", "" if valor is None else str(valor))
    texto = _RE_CONTROL.sub(" ", texto)
    texto = "".join(c for c in texto if unicodedata.category(c)[0] != "C")
    texto = " ".join(texto.split())
    return texto if len(texto) <= maximo else texto[: maximo - 1].rstrip() + "…"


def _neutralizar(texto: str) -> str:
    """Hace inerte un texto ajeno para Markdown, HTML y URLs sin volverlo irreconocible: `<>[]` ` | * _ # !`, `://` y
    `@` pasan a espacio y los espacios se colapsan (revisión de seguridad M4)."""
    return " ".join(_RE_PELIGROSO.sub(" ", texto).split())


def _norm_titulo(titulo: Any) -> str:
    """Misma normalización que `puntaje_modelar.resumir_anuncios` (NFC + casefold + espacios)."""
    return " ".join(unicodedata.normalize("NFC", str(titulo or "")).casefold().split())


def _clave_id(page_id: str) -> tuple[int, str]:
    """Orden numérico estable de ids en cadena decimal."""
    return (len(page_id), page_id)


def _es_kebab(texto: Any) -> bool:
    if not isinstance(texto, str) or not texto or texto != texto.lower():
        return False
    if texto.startswith("-") or texto.endswith("-") or "--" in texto:
        return False
    return all(c.isascii() and (c.isalnum() or c == "-") for c in texto)


def _slug(texto: str, maximo: int = 30) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:maximo].strip("-")


def _entero(valor: Any, campo: str, *, minimo: int = 0) -> int:
    if isinstance(valor, bool) or isinstance(valor, float):
        raise ErrorValidacion(f"{campo}: se esperaba un entero, llegó {type(valor).__name__} {_ver(valor)}")
    if isinstance(valor, Decimal):
        if valor != valor.to_integral_value():
            raise ErrorValidacion(f"{campo}: {valor} no es entero")
        valor = int(valor)
    if not isinstance(valor, int):
        raise ErrorValidacion(f"{campo}: se esperaba un entero, llegó {type(valor).__name__} {_ver(valor)}")
    if valor < minimo:
        raise ErrorValidacion(f"{campo}: {valor} es menor que {minimo}")
    return valor


def _decimal(valor: Any, campo: str) -> Decimal:
    if isinstance(valor, bool) or isinstance(valor, float):
        raise ErrorValidacion(f"{campo}: use entero o cadena decimal, no {type(valor).__name__}")
    try:
        if isinstance(valor, (int, Decimal)):
            d = Decimal(valor)
        elif isinstance(valor, str):
            d = Decimal(valor.strip())
        else:
            raise ErrorValidacion(f"{campo}: se esperaba un número, llegó {type(valor).__name__}")
    except InvalidOperation as exc:
        raise ErrorValidacion(f"{campo}: {_ver(valor)} no es un decimal") from exc
    if not d.is_finite():
        raise ErrorValidacion(f"{campo}: valor no finito")
    return d


def _pais(valor: Any, campo: str) -> str:
    if not (isinstance(valor, str) and _RE_PAIS.fullmatch(valor)):
        raise ErrorValidacion(f"{campo}: país ISO-2 en mayúsculas esperado, llegó {_ver(valor)}")
    return valor


def _id_pagina(valor: Any, campo: str) -> str:
    if isinstance(valor, bool):
        raise ErrorValidacion(f"{campo}: page_id inválido {_ver(valor)}")
    if isinstance(valor, int) and valor >= 0:
        return str(valor)
    if isinstance(valor, str) and _RE_DIGITOS.fullmatch(valor):
        return valor
    raise ErrorValidacion(f"{campo}: page_id debe ser una cadena de dígitos, llegó {_ver(valor)}")


def _sin_float(valor: Any, ruta: str = "doc") -> None:
    if isinstance(valor, (float, Decimal)):
        raise ErrorValidacion(f"{ruta}: no se persisten float ni Decimal (use enteros o cadenas decimales)")
    if isinstance(valor, Mapping):
        for clave, hijo in valor.items():
            _sin_float(hijo, f"{ruta}.{clave}")
    elif isinstance(valor, (list, tuple)):
        for i, hijo in enumerate(valor):
            _sin_float(hijo, f"{ruta}[{i}]")


def _moda(valores: Iterable[str]) -> str | None:
    """Valor más frecuente; en empate, el menor alfabéticamente (determinista)."""
    conteo = Counter(v for v in valores if v)
    if not conteo:
        return None
    return sorted(conteo, key=lambda v: (-conteo[v], v))[0]


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def _umbrales(par_modelado: Any) -> tuple[int, Decimal]:
    """(anuncios activos objetivo, días de edad de la oferta objetivo) de `parametros_modelado`. Falla cerrado."""
    if not isinstance(par_modelado, Mapping):
        raise ErrorUso("par_modelado debe ser un mapa clave → valor ya tipado")
    for clave in ("modelado_anuncios_objetivo", "modelado_dias_objetivo"):
        if clave not in par_modelado or par_modelado[clave] is None:
            raise ErrorLimite(f"falta el parámetro {clave} (falla cerrado: no se asume ningún umbral)")
    anuncios = _entero(par_modelado["modelado_anuncios_objetivo"], "modelado_anuncios_objetivo", minimo=1)
    dias = _decimal(par_modelado["modelado_dias_objetivo"], "modelado_dias_objetivo")
    if dias <= 0:
        raise ErrorValidacion("modelado_dias_objetivo: debe ser > 0")
    return anuncios, dias


def _config_barrido(par_barrido: Any) -> tuple[list[str], dict[str, str]]:
    """(países de origen en orden de prioridad, mapa país → idioma). Ambos parámetros son obligatorios: si falta alguno,
    ErrorLimite (5); no hay tabla de respaldo ni se adivina el idioma de un país (revisión de seguridad m9)."""
    if not isinstance(par_barrido, Mapping):
        raise ErrorUso("par_barrido debe ser un mapa clave → valor ya tipado")
    if "barrido_paises_origen" not in par_barrido or par_barrido["barrido_paises_origen"] is None:
        raise ErrorLimite("falta el parámetro barrido_paises_origen (falla cerrado)")
    origen = par_barrido["barrido_paises_origen"]
    if not isinstance(origen, (list, tuple)) or not origen:
        raise ErrorValidacion("barrido_paises_origen: se esperaba una lista no vacía de países ISO-2")
    prioridad = [_pais(p, "barrido_paises_origen") for p in origen]
    idiomas = par_barrido.get("barrido_idioma_por_pais")
    if idiomas is None:
        raise ErrorLimite("falta el parámetro barrido_idioma_por_pais (falla cerrado: no se adivina el idioma de un "
                          "país; el CLI lo toma de plan.cargar_banco()['pais_idioma'])")
    if not isinstance(idiomas, Mapping):
        raise ErrorValidacion("barrido_idioma_por_pais: se esperaba un mapa país → idioma")
    for pais, idioma in idiomas.items():
        _pais(pais, "barrido_idioma_por_pais (clave)")
        if not isinstance(idioma, str) or not idioma.strip():
            raise ErrorValidacion(f"barrido_idioma_por_pais[{pais}]: idioma de texto no vacío")
    return prioridad, {p: i.strip() for p, i in idiomas.items()}


def _validar_ahora(ahora: Any) -> datetime:
    if not isinstance(ahora, datetime) or ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ErrorUso("`ahora` debe ser un datetime con zona horaria UTC (reloj inyectado)")
    return ahora


# ---------------------------------------------------------------------------
# Lectura de «Páginas» (B2) y de las etiquetas (B4)
# ---------------------------------------------------------------------------

def _leer_exportador(bloque: Any) -> dict[str, Any]:
    """Bloque `exportador` de B2 → {senal, moneda, pais_anuncio, motivo}. La clave de B2 es «señal» (o «senal»).

    Sin bloque o con `señal` que no es booleano → `senal: None` (sin dato; no se asume que no exporta).
    """
    if not isinstance(bloque, Mapping):
        return {"senal": None, "moneda": None, "pais_anuncio": None, "motivo": None}
    senal = bloque.get("señal", bloque.get("senal"))
    return {
        "senal": senal if isinstance(senal, bool) else None,
        "moneda": _limpio(bloque["moneda"], 8) if isinstance(bloque.get("moneda"), str) else None,
        "pais_anuncio": _limpio(bloque["pais_anuncio"], 8) if isinstance(bloque.get("pais_anuncio"), str) else None,
        "motivo": _limpio(bloque["motivo"], 300) if isinstance(bloque.get("motivo"), str) else None,
    }


def _leer_medicion(p: Mapping[str, Any], ruta: str, conceptos: int) -> tuple[dict[str, Any] | None, bool]:
    """Campos de la pasada 3 de B2 → (medición normalizada | None, ¿venía incompleta?).

    Necesita `medicion.estado` (completa|parcial|muestra), `anuncios_activos_medidos` (exacto si «completa», piso si
    no) y `edad_es_piso`. Si no viene ninguno (corridas viejas) devuelve (None, False) y la tracción usa la regla de
    la muestra. Si vienen algunos pero faltan los necesarios, devuelve (None, True): se usa la regla de la muestra y
    `rankear` avisa. Un campo presente pero raro es ErrorValidacion.
    """
    bloque = p.get("medicion")
    medidos = p.get("anuncios_activos_medidos")
    edad_piso = p.get("edad_es_piso")
    medidos_piso = p.get("anuncios_activos_medidos_es_piso")
    if bloque is None and medidos is None and edad_piso is None and medidos_piso is None:
        return None, False
    estado = bloque.get("estado") if isinstance(bloque, Mapping) else None
    if estado is None or medidos is None or edad_piso is None:
        return None, True
    if estado not in ESTADOS_MEDICION:
        raise ErrorValidacion(f"{ruta}.medicion.estado: {_ver(estado)} no está en {ESTADOS_MEDICION}")
    medidos = _entero(medidos, f"{ruta}.anuncios_activos_medidos", minimo=0)
    ajustado_desde = None
    if conceptos > medidos:
        # dato incoherente de la ingesta (no puede haber menos anuncios activos que conceptos distintos vistos):
        # jamás tumba la corrida. Los conceptos vistos son una cota inferior válida; se avisa en `advertencias`.
        ajustado_desde, medidos = medidos, conceptos
    if not isinstance(edad_piso, bool):
        raise ErrorValidacion(f"{ruta}.edad_es_piso: true o false")
    if medidos_piso is not None and not isinstance(medidos_piso, bool):
        raise ErrorValidacion(f"{ruta}.anuncios_activos_medidos_es_piso: true o false")
    por_pais: dict[str, dict[str, Any]] = {}
    crudo = bloque.get("por_pais")
    if crudo is not None:
        if not isinstance(crudo, Mapping):
            raise ErrorValidacion(f"{ruta}.medicion.por_pais: se esperaba {{PAIS: {{...}}}}")
        for pais, d in crudo.items():
            campo = f"{ruta}.medicion.por_pais[{_ver(pais)}]"
            _pais(pais, campo)
            if not isinstance(d, Mapping):
                raise ErrorValidacion(f"{campo}: se esperaba un objeto")
            if d.get("fuente") not in FUENTES_MEDICION:
                raise ErrorValidacion(f"{campo}.fuente: {_ver(d.get('fuente'))} no está en {FUENTES_MEDICION}")
            if not isinstance(d.get("completa"), bool):
                raise ErrorValidacion(f"{campo}.completa: true o false")
            total = d.get("total_declarado")
            por_pais[pais] = {
                "fuente": d["fuente"], "completa": d["completa"],
                "anuncios_vistos": _entero(d.get("anuncios_vistos"), f"{campo}.anuncios_vistos"),
                "total_declarado": None if total is None else _entero(total, f"{campo}.total_declarado")}
    # el original NO corre en ese país si la pasada 3 midió el país completo y el total declarado es 0
    ausencia = sorted(c for c, d in por_pais.items()
                      if d["completa"] and d["total_declarado"] == 0 and d["anuncios_vistos"] == 0)
    return {"estado": estado, "medidos": medidos, "ajustado_desde": ajustado_desde,
            "medidos_piso": (estado != "completa" if medidos_piso is None else medidos_piso) or ajustado_desde is not None,
            "edad_piso": edad_piso, "por_pais": por_pais, "ausencia_medida": ausencia}, False


def _leer_paginas(doc: Any) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Valida el documento «Páginas» y devuelve (corrida_id, páginas normalizadas ordenadas por id, avisos de B2)."""
    if not isinstance(doc, Mapping):
        raise ErrorValidacion("paginas_doc: se esperaba el documento «Páginas» {corrida_id, paginas, ...}")
    corrida_id = doc.get("corrida_id")
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorValidacion(f"paginas_doc.corrida_id inválido {_ver(corrida_id)}: se espera AAAA-MM-DD-<letra>")
    lista = doc.get("paginas")
    if not isinstance(lista, list):
        raise ErrorValidacion("paginas_doc.paginas: se esperaba una lista")
    paginas: dict[str, dict[str, Any]] = {}
    for i, p in enumerate(lista):
        ruta = f"paginas[{i}]"
        if not isinstance(p, Mapping):
            raise ErrorValidacion(f"{ruta}: se esperaba un objeto")
        for campo in ("page_id", "paises", "anuncios_activos_en_muestra", "edad_oferta_dias", "conceptos_unicos",
                      "muestra_truncada"):
            if campo not in p:
                raise ErrorValidacion(f"{ruta}: falta «{campo}»")
        page_id = _id_pagina(p["page_id"], f"{ruta}.page_id")
        if page_id in paginas:
            raise ErrorValidacion(f"{ruta}.page_id: {page_id} repetido en el documento de páginas")
        if not isinstance(p["paises"], list) or not p["paises"]:
            raise ErrorValidacion(f"{ruta}.paises: se esperaba una lista no vacía de países ISO-2")
        paises = sorted({_pais(x, f"{ruta}.paises") for x in p["paises"]})
        anuncios = _entero(p["anuncios_activos_en_muestra"], f"{ruta}.anuncios_activos_en_muestra", minimo=1)
        edad = _decimal(p["edad_oferta_dias"], f"{ruta}.edad_oferta_dias")
        if edad < 0:
            raise ErrorValidacion(f"{ruta}.edad_oferta_dias: no puede ser negativa")
        conceptos = _entero(p["conceptos_unicos"], f"{ruta}.conceptos_unicos", minimo=1)
        if conceptos > anuncios:
            raise ErrorValidacion(f"{ruta}.conceptos_unicos: {conceptos} supera los anuncios de la muestra ({anuncios})")
        if not isinstance(p["muestra_truncada"], bool):
            raise ErrorValidacion(f"{ruta}.muestra_truncada: true o false")
        titulos = p.get("titulos", [])
        if not isinstance(titulos, list) or not all(isinstance(t, str) for t in titulos):
            raise ErrorValidacion(f"{ruta}.titulos: se esperaba una lista de textos")
        nombre = p.get("page_name")
        if nombre is not None and not isinstance(nombre, str):
            raise ErrorValidacion(f"{ruta}.page_name: texto o null")
        claves_titulo = frozenset(t for t in (_norm_titulo(x) for x in titulos) if t and t != _SIN_TITULO)
        medicion, incompleta = _leer_medicion(p, ruta, conceptos)
        paginas[page_id] = {
            "page_id": page_id,
            "page_name": _limpio(nombre, 120),
            "paises": paises,
            "anuncios": anuncios,
            "anuncios_traccion": anuncios if medicion is None else medicion["medidos"],
            "medicion": medicion,
            "medicion_incompleta": incompleta,
            "edad": edad,
            "edad_txt": format(edad, "f"),
            "conceptos": conceptos,
            "truncada": p["muestra_truncada"],
            "titulos_clave": claves_titulo,
            "exportador": _leer_exportador(p.get("exportador")),
        }
    avisos = doc.get("advertencias", [])
    avisos = [_limpio(a, 300) for a in avisos if isinstance(a, str)] if isinstance(avisos, list) else []
    return corrida_id, [paginas[k] for k in sorted(paginas, key=_clave_id)], avisos


def _etiqueta_normalizada(e: Mapping[str, Any]) -> dict[str, Any] | str:
    """Etiqueta de B4 → dict normalizado, o un texto con el motivo si no sirve (la página queda sin etiqueta válida)."""
    for campo in ("tema_slug", "formato", "macro_nicho", "es_oferta_digital_pago_unico"):
        if campo not in e:
            return f"falta «{campo}»"
    slug = e["tema_slug"]
    if not _es_kebab(slug):
        return f"tema_slug {_ver(slug)} no es kebab-case ASCII"
    if e["formato"] not in FORMATOS:
        return f"formato {_ver(e['formato'])} fuera del vocabulario"
    if e["macro_nicho"] is not None and e["macro_nicho"] not in pm.MACRO_NICHOS:
        return f"macro_nicho {_ver(e['macro_nicho'])} fuera de {pm.MACRO_NICHOS} y distinto de null"
    es_oferta = e["es_oferta_digital_pago_unico"]
    if es_oferta is not None and not isinstance(es_oferta, bool):
        return f"es_oferta_digital_pago_unico {_ver(es_oferta)}: true, false o null"
    tema = e.get("tema")
    publico = e.get("publico")
    confianza = e.get("confianza")
    return {
        "tema_slug": slug,
        "tema": _limpio(tema, 120) if isinstance(tema, str) and tema.strip() else slug,
        "publico": _limpio(publico, 120) if isinstance(publico, str) and publico.strip() else None,
        "formato": e["formato"],
        "macro_nicho": e["macro_nicho"],
        "es_oferta": es_oferta,
        "confianza": _limpio(confianza, 8) if isinstance(confianza, str) else None,
    }


def _leer_etiquetas(doc: Any, corrida_id: str) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """Etiquetas consolidadas → ({page_id: etiqueta | {"invalida": motivo} | {"conflicto": [slugs]}}, advertencias,
    {page_id: motivo} de las páginas que B4 dejó sin etiqueta: `en_disputa` y `sin_etiquetar` del consolidado)."""
    if isinstance(doc, list):
        lista = doc
    elif isinstance(doc, Mapping):
        otra = doc.get("corrida_id")
        if otra is not None and otra != corrida_id:
            raise ErrorValidacion(f"etiquetas_doc.corrida_id {_ver(otra)} no coincide con el de las páginas ({corrida_id})")
        lista = doc.get("paginas", doc.get("etiquetas"))
    else:
        raise ErrorValidacion("etiquetas_doc: se esperaba un objeto {paginas: [...]} o una lista")
    if not isinstance(lista, list):
        raise ErrorValidacion("etiquetas_doc.paginas: se esperaba una lista")
    avisos: list[str] = []
    por_pagina: dict[str, list[Any]] = {}
    sin_id = 0
    for e in lista:
        if not isinstance(e, Mapping):
            sin_id += 1
            continue
        try:
            page_id = _id_pagina(e.get("page_id"), "etiqueta.page_id")
        except ErrorValidacion:
            sin_id += 1
            continue
        por_pagina.setdefault(page_id, []).append(_etiqueta_normalizada(e))
    if sin_id:
        avisos.append(f"{sin_id} etiqueta(s) sin page_id utilizable se ignoraron")
    razones: dict[str, str] = {}
    if isinstance(doc, Mapping):
        for item in doc.get("sin_etiquetar") or []:
            if isinstance(item, Mapping) and isinstance(item.get("motivo"), str):
                try:
                    razones[_id_pagina(item.get("page_id"), "sin_etiquetar.page_id")] = \
                        "sin_etiqueta: " + _limpio(item["motivo"], 60)
                except ErrorValidacion:
                    pass
        for item in doc.get("en_disputa") or []:
            if isinstance(item, Mapping):
                try:
                    campos = item.get("discrepancias")
                    detalle = ", ".join(_limpio(c, 40) for c in campos if isinstance(c, str)) \
                        if isinstance(campos, list) else ""
                    razones[_id_pagina(item.get("page_id"), "en_disputa.page_id")] = \
                        "etiqueta_en_disputa" + (f": {detalle}" if detalle else "")
                except ErrorValidacion:
                    pass
    salida: dict[str, Any] = {}
    for page_id, entradas in por_pagina.items():
        validas = [x for x in entradas if isinstance(x, dict)]
        invalidas = [x for x in entradas if isinstance(x, str)]
        firmas = {(x["tema_slug"], x["formato"], x["macro_nicho"], x["es_oferta"]) for x in validas}
        if invalidas and not validas:
            salida[page_id] = {"invalida": sorted(invalidas)[0]}
        elif invalidas or len(firmas) > 1:
            slugs = sorted({x["tema_slug"] for x in validas})
            salida[page_id] = {"conflicto": slugs}
        else:
            salida[page_id] = min(validas, key=lambda x: (x["tema"], x["publico"] or "", x["confianza"] or ""))
    return salida, avisos, razones


def _clasificar(paginas: Sequence[Mapping[str, Any]], etiquetas: Mapping[str, Any],
                razones: Mapping[str, str] | None = None
                ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """(candidatas con tema, candidatas de tema indeterminado, descartadas con motivo, advertencias).

    Una página = a lo sumo un tema. Regla de avance (fail-open en descubrimiento, fail-closed al lanzar):
    `es_oferta_digital_pago_unico` true O null avanza (null = «no sé»: queda `por_verificar` el modelo de cobro);
    false o formato excluido no avanza y queda registrada con su motivo. Las de tema `indeterminado` no forman tema:
    se devuelven aparte y `rankear` decide por su tracción si siguen como «sin_tema»."""
    razones = razones or {}
    candidatas: list[dict[str, Any]] = []
    indeterminadas: list[dict[str, Any]] = []
    descartadas: list[dict[str, Any]] = []
    for p in paginas:
        e = etiquetas.get(p["page_id"])
        base = {"page_id": p["page_id"], "page_name": p["page_name"], "paises": list(p["paises"]),
                "anuncios_activos_en_muestra": p["anuncios"]}
        if e is None:
            if razones.get(p["page_id"]) == MOTIVO_SIN_TITULOS:
                # sin títulos no hay etiqueta posible, pero la tracción sí se mide: fail-open de descubrimiento
                indeterminadas.append({**p, "tema_slug": TEMA_INDETERMINADO, "tema": TEMA_INDETERMINADO,
                                       "publico": None, "formato": None, "macro_nicho": None, "confianza": None,
                                       "es_oferta": None, "origen_sin_tema": "sin_titulos"})
                continue
            descartadas.append({**base, "tema_slug": None, "formato": None, "macro_nicho": None,
                                "es_oferta_digital_pago_unico": None,
                                "motivos": [razones.get(p["page_id"], "sin_etiqueta")]})
            continue
        if "invalida" in e:
            descartadas.append({**base, "tema_slug": None, "formato": None, "macro_nicho": None,
                                "es_oferta_digital_pago_unico": None,
                                "motivos": [f"etiqueta_invalida: {e['invalida']}"]})
            continue
        if "conflicto" in e:
            descartadas.append({**base, "tema_slug": None, "formato": None, "macro_nicho": None,
                                "es_oferta_digital_pago_unico": None,
                                "motivos": ["etiqueta_conflictiva: " + (", ".join(e["conflicto"]) or "etiquetas incompatibles")]})
            continue
        motivos: list[str] = []
        if e["es_oferta"] is False:
            motivos.append("no_es_oferta_digital_pago_unico")
        if e["formato"] in FORMATOS_EXCLUIDOS:
            motivos.append(f"formato_excluido:{e['formato']}")
        if motivos:
            descartadas.append({**base, "tema_slug": e["tema_slug"], "formato": e["formato"],
                                "macro_nicho": e["macro_nicho"], "es_oferta_digital_pago_unico": e["es_oferta"],
                                "motivos": motivos})
        else:
            registro = {**p, **{k: e[k] for k in ("tema_slug", "tema", "publico", "formato", "macro_nicho",
                                                  "confianza")}, "es_oferta": e["es_oferta"],
                        "origen_sin_tema": "indeterminado"}
            (indeterminadas if e["tema_slug"] == TEMA_INDETERMINADO else candidatas).append(registro)
    ids = {p["page_id"] for p in paginas}
    huerfanas = sorted((k for k in etiquetas if k not in ids), key=_clave_id)
    avisos = []
    if huerfanas:
        avisos.append(f"{len(huerfanas)} etiqueta(s) de páginas que no están en el documento de páginas se ignoraron "
                      f"(primeras: {', '.join(huerfanas[:5])})")
    return candidatas, indeterminadas, descartadas, avisos


def _preparar(paginas_doc: Any, etiquetas_doc: Any) -> dict[str, Any]:
    corrida_id, paginas, avisos_b2 = _leer_paginas(paginas_doc)
    etiquetas, av_e, razones = _leer_etiquetas(etiquetas_doc, corrida_id)
    candidatas, indeterminadas, descartadas, av_c = _clasificar(paginas, etiquetas, razones)
    return {"corrida_id": corrida_id, "paginas": paginas, "candidatas": candidatas, "indeterminadas": indeterminadas,
            "descartadas": descartadas, "avisos": av_e + av_c, "avisos_b2": avisos_b2}


# ---------------------------------------------------------------------------
# Tracción
# ---------------------------------------------------------------------------

def _criterio(valor: Decimal | int, objetivo: Decimal | int, truncada: bool) -> str:
    if valor >= objetivo:
        return CUMPLE
    return INDET if truncada else NO_CUMPLE


def _evaluar_traccion(anuncios: int, edad: Decimal, truncada: bool, objetivo_a: int, objetivo_d: Decimal
                      ) -> dict[str, Any]:
    """Umbrales de §15.4: ≥ objetivo de anuncios activos Y ≥ objetivo de días de edad de la oferta (bordes incluidos).

    Muestra truncada: el conteo (y la edad, medida sobre esa muestra) son pisos. Si ya superan el umbral, cumple;
    si no, queda indeterminada. Solo un valor NO truncado por debajo del umbral descarta.
    """
    a = _criterio(anuncios, objetivo_a, truncada)
    d = _criterio(edad, objetivo_d, truncada)
    if NO_CUMPLE in (a, d):
        estado = NO_PASA
    elif INDET in (a, d):
        estado = INDETERMINADA
    else:
        estado = PASA
    return {"estado": estado, "pasa": {PASA: True, NO_PASA: False, INDETERMINADA: None}[estado],
            "detalle": {"anuncios": a, "edad": d}}


def _evaluar_pagina(c: Mapping[str, Any], objetivo_a: int, objetivo_d: Decimal) -> dict[str, Any]:
    """Tracción de UNA página (bordes incluidos). Con medición de la pasada 3 (`c["medicion"]`):

    - anuncios: `anuncios_activos_medidos` ≥ umbral → cumple (aunque sea piso: un piso que ya supera es definitivo);
      por debajo, definitivo solo si la medición es «completa»; si no, indeterminada.
    - edad: `edad_oferta_dias` ≥ umbral → cumple; por debajo, indeterminada si `edad_es_piso` (puede haber anuncios más
      viejos sin ver) y no cumple si no.
    Pasa si cumplen los dos; no pasa si alguno falla de forma definitiva; en otro caso, indeterminada_por_muestra.
    Nunca se descarta por un conteo que sea un piso insuficiente. Sin medición (corridas viejas) rige la regla de la
    muestra truncada (`_evaluar_traccion`).
    """
    m = c["medicion"]
    if m is None:
        r = _evaluar_traccion(c["anuncios"], c["edad"], c["truncada"], objetivo_a, objetivo_d)
        return {**r, "regla": "muestra"}
    if m["medidos"] >= objetivo_a:
        a = CUMPLE
    else:
        a = NO_CUMPLE if m["estado"] == "completa" else INDET
    if c["edad"] >= objetivo_d:
        d = CUMPLE
    else:
        d = INDET if m["edad_piso"] else NO_CUMPLE
    if NO_CUMPLE in (a, d):
        estado = NO_PASA
    elif INDET in (a, d):
        estado = INDETERMINADA
    else:
        estado = PASA
    return {"estado": estado, "pasa": {PASA: True, NO_PASA: False, INDETERMINADA: None}[estado],
            "detalle": {"anuncios": a, "edad": d}, "regla": "medida"}


def _estado_tema(estados: Iterable[str]) -> str:
    estados = list(estados)
    if PASA in estados:
        return PASA
    if INDETERMINADA in estados:
        return INDETERMINADA
    return NO_PASA


# ---------------------------------------------------------------------------
# Memoria (B3)
# ---------------------------------------------------------------------------

def _leer_memoria(memoria_diff: Any) -> dict[str, Any]:
    """Adaptador del `diff` de memoria (B3, `memoria.diff`). Sin base válida, nada de la memoria se usa.

    Lee la forma real de B3: `estado` («ok» / «sin_base», es la base de `entrantes_30d`), `base_entrantes.corrida_id`,
    `base_cambios.estado`, `temas_nuevos` + `temas_estado`, `paginas_nuevas` (objetos con `page_id`) y
    `entrantes_30d_por_pais` ({tema_slug: {PAIS: int | null}}). También acepta la forma simple
    {`base_valida`: bool, `previa_corrida_id`, `entrantes_30d`: {tema_slug: {PAIS: int | null}}}.
    Forma rara = ErrorValidacion. `entrantes_30d` solo vale con base válida (si no, todo `None`, jamás 0); las
    novedades (`temas_nuevos`, `paginas_nuevas`) dependen de la base de cambios, que puede existir sin base de entrantes.
    """
    vacia = {"base_valida": False, "previa": None, "temas_nuevos": None, "paginas_nuevas": None, "entrantes": None,
             "piso": None}
    if memoria_diff is None:
        return vacia
    if not isinstance(memoria_diff, Mapping):
        raise ErrorValidacion("memoria_diff: se esperaba el diff de memoria (objeto) o None")
    estado = memoria_diff.get("estado")
    if estado is not None:
        if estado not in ("ok", "sin_base"):
            raise ErrorValidacion(f"memoria_diff.estado: «ok» o «sin_base», llegó {_ver(estado)}")
        base = estado == "ok"
    else:
        base = memoria_diff.get("base_valida", memoria_diff.get("entrantes_30d_disponible", False))
        if not isinstance(base, bool):
            raise ErrorValidacion(f"memoria_diff.base_valida: true o false, llegó {_ver(base)}")
    base_entrantes = memoria_diff.get("base_entrantes")
    previa = base_entrantes.get("corrida_id") if isinstance(base_entrantes, Mapping) \
        else memoria_diff.get("previa_corrida_id")
    previa = previa if isinstance(previa, str) and comun.corrida_id_valido(previa) else None
    base_cambios = memoria_diff.get("base_cambios")
    if isinstance(base_cambios, Mapping):
        cambios_ok = base_cambios.get("estado") == "ok"
    elif "temas_estado" in memoria_diff:
        cambios_ok = memoria_diff["temas_estado"] != "sin_base"
    else:
        cambios_ok = base
    temas_nuevos = memoria_diff.get("temas_nuevos")
    if temas_nuevos is not None:
        if not isinstance(temas_nuevos, list) or not all(_es_kebab(t) for t in temas_nuevos):
            raise ErrorValidacion("memoria_diff.temas_nuevos: lista de tema_slug kebab-case")
        temas_nuevos = set(temas_nuevos) if cambios_ok and memoria_diff.get("temas_estado", "ok") == "ok" else None
    nuevas = memoria_diff.get("paginas_nuevas")
    if nuevas is not None:
        if not isinstance(nuevas, list):
            raise ErrorValidacion("memoria_diff.paginas_nuevas: se esperaba una lista")
        ids = {_id_pagina(x.get("page_id") if isinstance(x, Mapping) else x, "memoria_diff.paginas_nuevas")
               for x in nuevas}
        nuevas = ids if cambios_ok else None
    crudo = memoria_diff.get("entrantes_30d_por_pais")
    if crudo is None:
        simple = memoria_diff.get("entrantes_30d")
        if isinstance(simple, Mapping) and simple and all(isinstance(v, Mapping) for v in simple.values()):
            crudo = simple  # forma simple; el `entrantes_30d` global de B3 (enteros) no sirve para un mercado
    entrantes = None
    if crudo is not None:
        if not isinstance(crudo, Mapping):
            raise ErrorValidacion("memoria_diff.entrantes_30d_por_pais: se esperaba {tema_slug: {PAIS: entero | null}}")
        entrantes = {}
        for clave, por_pais in crudo.items():
            if not _es_kebab(clave) or not isinstance(por_pais, Mapping):
                raise ErrorValidacion(f"memoria_diff.entrantes_30d_por_pais[{_ver(clave)}]: se esperaba {{PAIS: entero}}")
            entrantes[clave] = {
                _pais(p, f"memoria_diff.entrantes_30d_por_pais[{clave}]"):
                    (None if n is None else _entero(n, f"memoria_diff.entrantes_30d_por_pais[{clave}][{p}]"))
                for p, n in por_pais.items()}
    piso = None
    crudo_piso = memoria_diff.get("entrantes_30d_piso_por_pais")  # opcional (B3, revisión m6): ¿el conteo es un piso?
    if crudo_piso is not None:
        if not isinstance(crudo_piso, Mapping):
            raise ErrorValidacion("memoria_diff.entrantes_30d_piso_por_pais: se esperaba {tema_slug: {PAIS: bool}}")
        piso = {}
        for clave, por_pais in crudo_piso.items():
            if not _es_kebab(clave) or not isinstance(por_pais, Mapping):
                raise ErrorValidacion(
                    f"memoria_diff.entrantes_30d_piso_por_pais[{_ver(clave)}]: se esperaba {{PAIS: bool}}")
            for p, v in por_pais.items():
                _pais(p, f"memoria_diff.entrantes_30d_piso_por_pais[{clave}]")
                if v is not None and not isinstance(v, bool):
                    raise ErrorValidacion(f"memoria_diff.entrantes_30d_piso_por_pais[{clave}][{p}]: true, false o null")
            piso[clave] = dict(por_pais)
    return {"base_valida": base, "previa": previa, "temas_nuevos": temas_nuevos, "paginas_nuevas": nuevas,
            "entrantes": entrantes if base else None, "piso": piso if base else None}


def _entrantes(mem: Mapping[str, Any], tema_slug: str, pais: str) -> int | None:
    """`entrantes_30d` de (tema, país) tal como lo midió B3; `None` si no hay base válida o B3 no midió ese par.
    Jamás se rellena con 0 ni se deriva de otra cosa: un par que B3 no midió es desconocido, no «nadie entró»."""
    if not mem["base_valida"] or mem["entrantes"] is None:
        return None
    return mem["entrantes"].get(tema_slug, {}).get(pais)


def _entrantes_piso(mem: Mapping[str, Any], tema_slug: str, pais: str) -> bool | None:
    """¿El `entrantes_30d` de (tema, país) es un piso? `None` si B3 no lo informó (no cambia nada)."""
    if not mem["base_valida"] or mem["piso"] is None:
        return None
    return mem["piso"].get(tema_slug, {}).get(pais)


# ---------------------------------------------------------------------------
# Matriz tema × país y exportadores
# ---------------------------------------------------------------------------

def _universo_paises(paginas: Sequence[Mapping[str, Any]], extra: Iterable[str] | None) -> list[str]:
    paises = {p for pg in paginas for p in pg["paises"]}
    for pg in paginas:  # la pasada 3 mide cada página en cada país de presencia, aunque no corra allí
        if pg.get("medicion") is not None:
            paises.update(pg["medicion"]["por_pais"])
    for p in extra or ():
        paises.add(_pais(p, "paises_barridos"))
    return sorted(paises)


def _por_tema(candidatas: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grupos: dict[str, list[Mapping[str, Any]]] = {}
    for c in candidatas:
        grupos.setdefault(c["tema_slug"], []).append(c)
    return {k: grupos[k] for k in sorted(grupos)}


def _matriz(candidatas: Sequence[Mapping[str, Any]], universo: Sequence[str]) -> dict[str, Any]:
    filas = []
    for slug, cs in _por_tema(candidatas).items():
        presencia = {}
        for pais in universo:
            n = sum(1 for c in cs if pais in c["paises"])
            presencia[pais] = {"presente": n > 0, "paginas": n}
        filas.append({
            "tema_slug": slug,
            "presencia": presencia,
            "paises_presentes": [p for p in universo if presencia[p]["presente"]],
            "huecos": [p for p in universo if not presencia[p]["presente"]],
        })
    return {"paises": list(universo), "estado_ausencia": ESTADO_AUSENCIA, "advertencia": ADVERTENCIA_AUSENCIA,
            "temas": filas}


def matriz_tema_pais(paginas_doc: Any, etiquetas_doc: Any, *, paises_barridos: Iterable[str] | None = None
                     ) -> dict[str, Any]:
    """Presencia / ausencia por tema × país (CONTRATO §4; spec §17.3 pieza 4).

    Solo cuentan las páginas candidatas (oferta digital de pago único, formato admitido). El universo de países es
    la unión de los países en que apareció CUALQUIER página de la corrida (también descartadas y sin etiqueta: prueban
    que ese país se barrió) más `paises_barridos` si se pasa. **Ausencia = hueco candidato, nunca un hecho**: es
    ausencia en la muestra (máx. 50 anuncios por consulta) y queda en `estado_ausencia` = «hipotesis_hasta_pasada_3».
    """
    prep = _preparar(paginas_doc, etiquetas_doc)
    return _matriz(prep["candidatas"], _universo_paises(prep["paginas"], paises_barridos))


def _resumen_exportadores(cs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    con_senal = [c for c in cs if c["exportador"]["senal"] is True]
    monedas = Counter(c["exportador"]["moneda"] or "?" for c in con_senal)
    paises = Counter(c["exportador"]["pais_anuncio"] or "?" for c in con_senal)
    return {
        "paginas_evaluadas": len(cs),
        "con_senal": len(con_senal),
        "sin_dato": sum(1 for c in cs if c["exportador"]["senal"] is None),
        "monedas": {k: monedas[k] for k in sorted(monedas)},
        "paises_anuncio": {k: paises[k] for k in sorted(paises)},
        "paginas": [{"page_id": c["page_id"], "page_name": c["page_name"], "moneda": c["exportador"]["moneda"],
                     "pais_anuncio": c["exportador"]["pais_anuncio"], "motivo": c["exportador"]["motivo"]}
                    for c in con_senal],
    }


def _exportadores(candidatas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    temas = [{"tema_slug": slug, **_resumen_exportadores(cs)} for slug, cs in _por_tema(candidatas).items()]
    global_ = _resumen_exportadores(list(candidatas))
    return {
        "advertencia": ("Indicio de «probable exportador» (cuenta publicitaria en la moneda de un país que anuncia en "
                        "otro idioma): sirve para seguir la oferta a los idiomas donde falta; no es un hecho ni "
                        "entra en la tracción."),
        "resumen": {k: global_[k] for k in ("paginas_evaluadas", "con_senal", "sin_dato", "monedas")},
        "temas_con_senal": sum(1 for t in temas if t["con_senal"]),
        "temas": temas,
    }


def exportadores_por_tema(paginas_doc: Any, etiquetas_doc: Any) -> dict[str, Any]:
    """Resumen de la señal de exportadores por tema (spec §17.3 pieza 5), sobre las páginas candidatas.

    Por tema: páginas evaluadas, cuántas tienen señal, cuántas sin dato, monedas y países de anuncio de las que sí
    la tienen, y el detalle de esas páginas. La señal viene de B2 (`exportador.señal`); aquí no se recalcula.
    """
    return _exportadores(_preparar(paginas_doc, etiquetas_doc)["candidatas"])


# ---------------------------------------------------------------------------
# Temas
# ---------------------------------------------------------------------------

def _grupos_operador(cs: Sequence[Mapping[str, Any]], estados: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """Agrupa por títulos idénticos (conjunto normalizado, no vacío). Cada grupo cuenta como UN anunciante.

    Devuelve por page_id {grupo (id del grupo o None), tamano, representante}. El representante de un grupo es la
    página que pasa tracción (si hay), con más anuncios y menor id: es la que cuenta como independiente.
    """
    por_clave: dict[frozenset[str], list[Mapping[str, Any]]] = {}
    sueltas: list[Mapping[str, Any]] = []
    for c in cs:
        if c["titulos_clave"]:
            por_clave.setdefault(c["titulos_clave"], []).append(c)
        else:
            sueltas.append(c)
    info: dict[str, dict[str, Any]] = {}
    for c in sueltas:
        info[c["page_id"]] = {"grupo": None, "tamano": 1, "representante": True}
    for miembros in por_clave.values():
        if len(miembros) == 1:
            info[miembros[0]["page_id"]] = {"grupo": None, "tamano": 1, "representante": True}
            continue
        grupo = min((m["page_id"] for m in miembros), key=_clave_id)
        rep = min(miembros, key=lambda m: (estados[m["page_id"]] != PASA, -m["anuncios_traccion"], _clave_id(m["page_id"])))
        for m in miembros:
            info[m["page_id"]] = {"grupo": grupo, "tamano": len(miembros), "representante": m is rep}
    return info


def _agregar_macro(cs: Sequence[Mapping[str, Any]]) -> tuple[str | None, dict[str, int]]:
    etiquetas = {c["macro_nicho"] for c in cs}
    conteo = Counter(c["macro_nicho"] or "fuera_de_marco" for c in cs)
    macro = next(iter(etiquetas)) if len(etiquetas) == 1 else MACRO_MIXTO
    ordenado = {k: conteo.get(k, 0) for k in (*pm.MACRO_NICHOS, "fuera_de_marco")}
    return macro, ordenado


def _peso_pais(medicion: Mapping[str, Any], pais: str) -> int:
    """Anuncios de la página en un país según la pasada 3: el total declarado si se midió con su propia consulta;
    si no, los vistos. Un país sin entrada pesa 0."""
    d = medicion["por_pais"].get(pais)
    if d is None:
        return 0
    return d["total_declarado"] if d["fuente"] == "pagina" and d["total_declarado"] is not None else d["anuncios_vistos"]


def _pais_fuente(paises: Sequence[str], prioridad: Sequence[str], medicion: Mapping[str, Any] | None = None) -> str:
    """País de origen de la página: aquel donde más anuncia según `medicion.por_pais` (revisión de corrección M3);
    la prioridad de `barrido_paises_origen` solo desempata y rige sola si no hay medición por país."""
    candidatos = list(paises)
    if medicion is not None and medicion["por_pais"]:
        mejor = max(_peso_pais(medicion, p) for p in candidatos)
        candidatos = [p for p in candidatos if _peso_pais(medicion, p) == mejor]
    for p in prioridad:
        if p in candidatos:
            return p
    return sorted(candidatos)[0]


def _registro_pagina(c: Mapping[str, Any], t: Mapping[str, Any], g: Mapping[str, Any], slug: str,
                     prioridad: Sequence[str]) -> dict[str, Any]:
    """Registro público de una página candidata (en un tema o «sin_tema»)."""
    return {
        "page_id": c["page_id"],
        "page_name": c["page_name"],
        "tema_slug": slug,
        "paises": list(c["paises"]),
        "pais_fuente": _pais_fuente(c["paises"], prioridad, c["medicion"]),
        "anuncios_activos_en_muestra": c["anuncios"],
        "anuncios_activos_traccion": c["anuncios_traccion"],
        "regla_traccion": t["regla"],
        "medicion_estado": None if c["medicion"] is None else c["medicion"]["estado"],
        "anuncios_activos_medidos": None if c["medicion"] is None else c["medicion"]["medidos"],
        "anuncios_activos_medidos_es_piso": None if c["medicion"] is None else c["medicion"]["medidos_piso"],
        "edad_es_piso": None if c["medicion"] is None else c["medicion"]["edad_piso"],
        "paises_ausencia_medida": [] if c["medicion"] is None else list(c["medicion"]["ausencia_medida"]),
        "edad_oferta_dias": c["edad_txt"],
        "conceptos_unicos": c["conceptos"],
        "muestra_truncada": c["truncada"],
        "estado_traccion": t["estado"],
        "pasa_traccion": t["pasa"],
        "traccion_detalle": dict(t["detalle"]),
        "formato": c["formato"],
        "macro_nicho": c["macro_nicho"],
        "confianza": c["confianza"],
        "es_oferta_digital_pago_unico": c["es_oferta"],
        "por_verificar": ["modelo_de_cobro"] if c["es_oferta"] is None else [],
        "posible_mismo_operador": g["grupo"] is not None,
        "grupo_operador": g["grupo"],
        "paginas_en_grupo": g["tamano"],
        "cuenta_como_independiente": g["representante"],
        "exportador": {"senal": c["exportador"]["senal"], "moneda": c["exportador"]["moneda"],
                       "pais_anuncio": c["exportador"]["pais_anuncio"]},
    }


def _construir_tema(slug: str, cs: Sequence[Mapping[str, Any]], *, objetivo_a: int, objetivo_d: Decimal,
                    prioridad: Sequence[str], universo: Sequence[str], mem: Mapping[str, Any]) -> dict[str, Any]:
    traccion = {c["page_id"]: _evaluar_pagina(c, objetivo_a, objetivo_d) for c in cs}
    estados = {pid: t["estado"] for pid, t in traccion.items()}
    grupos = _grupos_operador(cs, estados)
    registros = [_registro_pagina(c, traccion[c["page_id"]], grupos[c["page_id"]], slug, prioridad) for c in cs]
    registros.sort(key=lambda r: _clave_id(r["page_id"]))
    con_traccion = [c for c in cs if estados[c["page_id"]] == PASA]
    edad_traccion = max(con_traccion, key=lambda c: c["edad"])["edad_txt"] if con_traccion else None
    edad_max = max(cs, key=lambda c: c["edad"])["edad_txt"]
    macro, macro_conteo = _agregar_macro(cs)
    estado = _estado_tema(estados.values())
    presentes = sorted({p for c in cs for p in c["paises"]})
    huecos = [p for p in universo if p not in presentes]
    nuevas = mem["paginas_nuevas"]
    return {
        "tema_slug": slug,
        "tema": _moda(c["tema"] for c in cs),
        "publicos": sorted({c["publico"] for c in cs if c["publico"]}),
        "estado_traccion": estado,
        "pasa_traccion": {PASA: True, NO_PASA: False, INDETERMINADA: None}[estado],
        "anunciantes_independientes": sum(1 for r in registros if r["cuenta_como_independiente"]),
        "paginas_total": len(cs),
        "por_verificar": ["modelo_de_cobro"] if any(c["es_oferta"] is None for c in cs) else [],
        "paginas_por_verificar": sum(1 for c in cs if c["es_oferta"] is None),
        "paginas_posible_mismo_operador": sum(1 for r in registros if r["posible_mismo_operador"]),
        "paginas_con_traccion": len(con_traccion),
        "paginas_indeterminadas": sum(1 for e in estados.values() if e == INDETERMINADA),
        "anuncios_activos_en_muestra": sum(c["anuncios"] for c in cs),
        "anuncios_activos_traccion": sum(c["anuncios_traccion"] for c in cs),
        "hay_muestra_truncada": any(c["truncada"] for c in cs),
        "edad_oferta_dias": edad_traccion,
        "edad_max_muestra_dias": edad_max,
        "paises": presentes,
        "huecos": huecos,
        "macro_nicho": macro,
        "macro_nicho_conteo": macro_conteo,
        "formatos": {f: n for f, n in sorted(Counter(c["formato"] for c in cs).items())},
        "exportadores": {k: v for k, v in _resumen_exportadores(cs).items() if k != "paginas"},
        "novedad": {
            "tema_nuevo": (slug in mem["temas_nuevos"]) if mem["temas_nuevos"] is not None else None,
            "paginas_nuevas": (sum(1 for c in cs if c["page_id"] in nuevas)) if nuevas is not None else None,
        },
        "entrantes_30d": {pais: _entrantes(mem, slug, pais) for pais in huecos},
        "entrantes_30d_piso": {pais: _entrantes_piso(mem, slug, pais) for pais in huecos},
        "paginas": registros,
    }


def _construir_sin_tema(cs: Sequence[Mapping[str, Any]], *, objetivo_a: int, objetivo_d: Decimal,
                        prioridad: Sequence[str], universo: Sequence[str], mem: Mapping[str, Any]
                        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Páginas de tema `indeterminado` → ((candidatas «sin_tema» ordenadas), (descartadas por baja tracción)).

    No se agrupan por tema (no lo tienen). Avanzan si su tracción pasa O si es indeterminada por muestra truncada
    (jamás se descarta por un conteo truncado); solo una tracción definitivamente baja (`no_pasa`) las descarta.
    Cada una lleva su propio hueco (países de la muestra donde NO corre ella misma) y `por_verificar` el tema y el
    modelo de cobro. Páginas con los mismos títulos se agrupan como un solo operador, igual que dentro de un tema.
    """
    traccion = {c["page_id"]: _evaluar_pagina(c, objetivo_a, objetivo_d) for c in cs}
    avanzan = [c for c in cs if traccion[c["page_id"]]["estado"] != NO_PASA]
    descartadas = [{
        "page_id": c["page_id"], "page_name": c["page_name"], "paises": list(c["paises"]),
        "anuncios_activos_en_muestra": c["anuncios"],
        "tema_slug": TEMA_INDETERMINADO if c["origen_sin_tema"] == "indeterminado" else None, "formato": c["formato"],
        "macro_nicho": c["macro_nicho"], "es_oferta_digital_pago_unico": c["es_oferta"],
        "motivos": (["tema_indeterminado_sin_traccion_alta"] if c["origen_sin_tema"] == "indeterminado"
                    else [MOTIVO_SIN_TITULOS])}
        for c in cs if traccion[c["page_id"]]["estado"] == NO_PASA]
    estados = {c["page_id"]: traccion[c["page_id"]]["estado"] for c in avanzan}
    grupos = _grupos_operador(avanzan, estados)
    registros = []
    for c in avanzan:
        r = _registro_pagina(c, traccion[c["page_id"]], grupos[c["page_id"]], TEMA_INDETERMINADO, prioridad)
        r["por_verificar"] = ["tema"] + (["modelo_de_cobro"] if c["es_oferta"] is None else [])
        r["origen_sin_tema"] = c["origen_sin_tema"]
        r["huecos"] = [p for p in universo if p not in c["paises"]]
        # B3 indexa por page_id las páginas sin tema
        r["entrantes_30d"] = {pais: _entrantes(mem, c["page_id"], pais) for pais in r["huecos"]}
        r["entrantes_30d_piso"] = {pais: _entrantes_piso(mem, c["page_id"], pais) for pais in r["huecos"]}
        registros.append(r)
    registros.sort(key=lambda r: (_ORDEN_ESTADO[r["estado_traccion"]], -r["anuncios_activos_traccion"],
                                  -Decimal(r["edad_oferta_dias"]), _clave_id(r["page_id"])))
    return [{"rank": i, **r} for i, r in enumerate(registros, 1)], descartadas


def _clave_orden_tema(t: Mapping[str, Any]) -> tuple:
    edad = Decimal(t["edad_oferta_dias"] if t["edad_oferta_dias"] is not None else t["edad_max_muestra_dias"])
    return (_ORDEN_ESTADO[t["estado_traccion"]], -t["anunciantes_independientes"], -edad,
            -t["anuncios_activos_traccion"], t["tema_slug"])


def _idiomas(paises: Sequence[str], mapa: Mapping[str, str]) -> tuple[dict[str, str | None], list[str]]:
    """Idioma de cada país del universo según `barrido_idioma_por_pais`; el que el mapa no cubre queda `None`."""
    salida: dict[str, str | None] = {p: mapa.get(p) for p in paises}
    desconocidos = [p for p in paises if salida[p] is None]
    avisos = []
    if desconocidos:
        avisos.append("idioma desconocido para " + ", ".join(desconocidos) + ": no se arman fichas con esos países "
                      "(agregue esos países a barrido_idioma_por_pais)")
    return salida, avisos


def rankear(paginas_doc: Any, etiquetas_doc: Any, *, memoria_diff: Any = None, par_modelado: Mapping[str, Any],
            par_barrido: Mapping[str, Any], ahora: datetime,
            paises_barridos: Iterable[str] | None = None) -> dict[str, Any]:
    """Documento «Candidatos» (CONTRATO §4): temas rankeados + matriz tema × país + exportadores + descartadas.

    Entradas: «Páginas» (B2), etiquetas consolidadas (B4), `memoria_diff` opcional (B3), parámetros ya tipados
    (`comun.cargar_parametros_modelado/barrido`), reloj inyectado `ahora` (UTC con zona) y, opcional,
    `paises_barridos` (países que el plan SÍ barrió, para ampliar las columnas de la matriz: no pasar países que
    no se consultaron, porque su «ausencia» no significaría nada).
    Orden de los temas: pasa > indeterminada_por_muestra > no_pasa; luego más anunciantes independientes, mayor edad de
    la oferta, más anuncios y `tema_slug`. Las páginas de tema `indeterminado` que no fallan la tracción van aparte, en
    `sin_tema` (sin agrupar por tema); `es_oferta_digital_pago_unico = null` avanza y queda `por_verificar`. Errores: ErrorLimite (5) si faltan umbrales; ErrorValidacion (3) si un
    documento de entrada viene mal formado; ErrorUso (2) si `ahora` no tiene zona.
    """
    ahora = _validar_ahora(ahora)
    objetivo_a, objetivo_d = _umbrales(par_modelado)
    prioridad, mapa_idiomas = _config_barrido(par_barrido)
    prep = _preparar(paginas_doc, etiquetas_doc)
    mem = _leer_memoria(memoria_diff)
    universo = _universo_paises(prep["paginas"], paises_barridos)
    idiomas, av_idioma = _idiomas(universo, mapa_idiomas)

    temas = [_construir_tema(slug, cs, objetivo_a=objetivo_a, objetivo_d=objetivo_d, prioridad=prioridad,
                             universo=universo, mem=mem)
             for slug, cs in _por_tema(prep["candidatas"]).items()]
    temas.sort(key=_clave_orden_tema)
    temas = [{"rank": i, **t} for i, t in enumerate(temas, 1)]
    sin_tema, desc_sin_tema = _construir_sin_tema(prep["indeterminadas"], objetivo_a=objetivo_a,
                                                  objetivo_d=objetivo_d, prioridad=prioridad, universo=universo,
                                                  mem=mem)

    descartadas = sorted(prep["descartadas"] + desc_sin_tema, key=lambda d: _clave_id(d["page_id"]))
    por_motivo = Counter(m.split(":")[0] for d in descartadas for m in d["motivos"])
    n_trunc = sum(1 for p in prep["paginas"] if p["truncada"])
    avisos = list(prep["avisos"]) + av_idioma
    if n_trunc:
        avisos.append(f"{n_trunc} de {len(prep['paginas'])} página(s) con muestra truncada: su conteo es un PISO; si no "
                      "supera el umbral queda «indeterminada_por_muestra» (la pasada 2/3 debe medirla)")
    if sin_tema:
        avisos.append(f"{len(sin_tema)} página(s) de tema indeterminado avanzan como «sin_tema» (no se agrupan por tema; "
                      "su hueco es el del original solo): la captura de la ficha/landing debe aclarar tema y modelo de cobro")
    por_verificar = sum(1 for c in prep["candidatas"] if c["es_oferta"] is None) \
        + sum(1 for r in sin_tema if r["es_oferta_digital_pago_unico"] is None)
    if por_verificar:
        avisos.append(f"{por_verificar} página(s) avanzan con es_oferta_digital_pago_unico = null (por_verificar: "
                      "modelo_de_cobro): fail-open en descubrimiento, fail-closed al lanzar")
    avisos.append(ADVERTENCIA_AUSENCIA)
    avisos.append("paginas_misma_landing y anunciantes_independientes_mismo_angulo de las fichas son proxies: el "
                  "conector no entrega landing; se agrupa por títulos exactos idénticos (posible_mismo_operador)")
    if not mem["base_valida"]:
        avisos.append("sin base de memoria válida (instantánea previa con antigüedad suficiente): entrantes_30d = null "
                      "en todas partes, nunca 0 por defecto")

    por_macro = Counter(t["macro_nicho"] or "fuera_de_marco" for t in temas if t["estado_traccion"] == PASA)
    por_medicion = Counter("sin_medicion" if p["medicion"] is None else p["medicion"]["estado"]
                           for p in prep["paginas"])
    estados_paginas = Counter([r["estado_traccion"] for t in temas for r in t["paginas"]]
                              + [r["estado_traccion"] for r in sin_tema])
    incompletas = sum(1 for p in prep["paginas"] if p["medicion_incompleta"])
    if incompletas:
        avisos.append(f"{incompletas} página(s) con campos de medición incompletos (falta medicion.estado, "
                      "anuncios_activos_medidos o edad_es_piso): su tracción usa la regla de la muestra")
    ajustadas = [p["page_id"] for p in prep["paginas"]
                 if p["medicion"] is not None and p["medicion"]["ajustado_desde"] is not None]
    if ajustadas:
        avisos.append(f"{len(ajustadas)} página(s) con anuncios_activos_medidos menor que los conceptos únicos (dato "
                      "incoherente de la ingesta): se tomó el número de conceptos vistos como piso "
                      f"(primeras: {', '.join(ajustadas[:5])})")
    if por_medicion["parcial"] or por_medicion["muestra"]:
        avisos.append(f"medición de la pasada 3: {por_medicion['completa']} completa(s), {por_medicion['parcial']} "
                      f"parcial(es), {por_medicion['muestra']} solo muestra, {por_medicion['sin_medicion']} sin medición: "
                      "los conteos no completos son un PISO; un piso que ya supera el umbral es definitivo y uno "
                      "insuficiente queda «indeterminada_por_muestra»")
    doc = {
        "schema_version": SCHEMA_VERSION,
        "corrida_id": prep["corrida_id"],
        "generado_en": comun.iso_z(ahora),
        "umbrales_traccion": {
            "anuncios_activos": objetivo_a,
            "edad_oferta_dias": format(objetivo_d, "f"),
            "fuente": "parametros_modelado: modelado_anuncios_objetivo y modelado_dias_objetivo (bordes incluidos)",
        },
        "resumen": {
            "paginas_total": len(prep["paginas"]),
            "paginas_candidatas": len(prep["candidatas"]) + len(sin_tema),
            "paginas_en_temas": len(prep["candidatas"]),
            "paginas_sin_tema": len(sin_tema),
            "paginas_por_verificar": sum(1 for c in prep["candidatas"] if c["es_oferta"] is None)
            + sum(1 for r in sin_tema if r["es_oferta_digital_pago_unico"] is None),
            "paginas_por_medicion": {k: por_medicion[k] for k in (*ESTADOS_MEDICION, "sin_medicion")},
            "paginas_candidatas_por_estado": {k: estados_paginas[k] for k in (PASA, INDETERMINADA, NO_PASA)},
            "paginas_descartadas": len(descartadas),
            "descartadas_por_motivo": {k: por_motivo[k] for k in sorted(por_motivo)},
            "temas": len(temas),
            "temas_pasan_traccion": sum(1 for t in temas if t["estado_traccion"] == PASA),
            "temas_indeterminados_por_muestra": sum(1 for t in temas if t["estado_traccion"] == INDETERMINADA),
            "temas_no_pasan_traccion": sum(1 for t in temas if t["estado_traccion"] == NO_PASA),
            "sin_tema_pasan_traccion": sum(1 for r in sin_tema if r["estado_traccion"] == PASA),
            "sin_tema_indeterminadas_por_muestra": sum(1 for r in sin_tema if r["estado_traccion"] == INDETERMINADA),
            "temas_que_pasan_por_macro_nicho": {k: por_macro[k] for k in (*pm.MACRO_NICHOS, MACRO_MIXTO,
                                                                           "fuera_de_marco")},
        },
        "memoria": {"base_valida": mem["base_valida"], "previa_corrida_id": mem["previa"]},
        "idiomas_por_pais": idiomas,
        "temas": temas,
        "sin_tema": sin_tema,
        "matriz_tema_pais": _matriz(prep["candidatas"], universo),
        "exportadores": _exportadores(prep["candidatas"]),
        "descartadas": descartadas,
        "advertencias": avisos,
        "advertencias_ingesta": prep["avisos_b2"],
    }
    _sin_float(doc)
    return doc


# ---------------------------------------------------------------------------
# Puente a fichas de puntaje_modelar (schema_version 2.0.0)
# ---------------------------------------------------------------------------

def _validar_candidatos(doc: Any) -> None:
    if not isinstance(doc, Mapping) or doc.get("schema_version") != SCHEMA_VERSION:
        raise ErrorValidacion(f"candidatos_doc: se esperaba el documento «Candidatos» schema_version {SCHEMA_VERSION!r}")
    if not comun.corrida_id_valido(doc.get("corrida_id")):
        raise ErrorValidacion(f"candidatos_doc.corrida_id inválido {_ver(doc.get('corrida_id'))}")
    for campo in ("temas", "idiomas_por_pais"):
        if campo not in doc:
            raise ErrorValidacion(f"candidatos_doc: falta «{campo}»")
    if not isinstance(doc["temas"], list) or not isinstance(doc["idiomas_por_pais"], Mapping):
        raise ErrorValidacion("candidatos_doc: «temas» debe ser lista e «idiomas_por_pais» un mapa")


def _nombre_ficha(tema: str, pagina: Mapping[str, Any]) -> str:
    nombre = _neutralizar(_limpio(pagina["page_name"], 80)) or f"página {pagina['page_id']}"
    return f"{_neutralizar(_limpio(tema, 100)) or 'sin tema'} · {nombre} ({pagina['pais_fuente']})"


def _modelo_id(slug: str, pagina: Mapping[str, Any]) -> str:
    piezas = [slug, _slug(pagina["page_name"]), pagina["page_id"]]
    modelo_id = "-".join(p for p in piezas if p)
    if not _es_kebab(modelo_id):
        raise ErrorValidacion(f"modelo_id derivado inválido: {_ver(modelo_id)}")
    return modelo_id


def puente_a_fichas(candidatos_doc: Any, memoria_diff: Any, par_modelado: Mapping[str, Any]) -> dict[str, Any]:
    """«Candidatos» → borrador de fichas `schema_version "2.0.0"` para `puntaje_modelar` (una por página-oferta).

    Una ficha por operador (grupo de títulos idénticos) cuya página pasa la tracción, en un tema o en `sin_tema`; las
    `indeterminada_por_muestra` no generan ficha hasta que la pasada 2/3 las mida. Si la página avanzó con
    `es_oferta_digital_pago_unico = null`, la ficha lo declara en `pendiente`. Lo medido va a `traccion`; las tres puertas
    (`pm.PUERTAS`), la transferibilidad y los reencuadres van sin evaluar (`null` / `[]`), así que toda ficha sale
    «incompleta» al puntuarse: es lo correcto. `mercados` = países donde la matriz muestra ausencia del tema
    (hipótesis hasta la pasada 3), con `entrantes_30d` de la memoria o `null`. Si `memoria_diff` es None se usan los
    `entrantes_30d` que ya trae `candidatos_doc` (calculados en `rankear`). El resultado se valida con
    `puntaje_modelar.validar_fichas` antes de devolverlo. Sin ninguna ficha devuelve `ofertas: []` (que el validador
    rechaza por vacío: ver `escribir_fichas_borrador`).
    """
    _validar_candidatos(candidatos_doc)
    if not isinstance(par_modelado, Mapping) or "modelado_sostenidos_cierre" not in par_modelado:
        raise ErrorLimite("par_modelado sin «modelado_sostenidos_cierre»: no se puede validar la ficha (falla cerrado)")
    mem = _leer_memoria(memoria_diff) if memoria_diff is not None else None
    idiomas = candidatos_doc["idiomas_por_pais"]
    ofertas: list[dict[str, Any]] = []
    omitidas: list[str] = []

    def agregar(pagina: Mapping[str, Any], *, prefijo: str, tema_texto: str, huecos: Sequence[str], clave_mem: str,
                embebidos: Mapping[str, Any], embebidos_piso: Mapping[str, Any], otros_independientes: int,
                sin_tema: bool) -> None:
        idioma_fuente = idiomas.get(pagina["pais_fuente"])
        if not idioma_fuente:
            omitidas.append(f"{pagina['page_id']}: idioma_fuente_desconocido ({pagina['pais_fuente']})")
            return
        mercados = []
        con_piso: list[str] = []
        for pais in huecos:
            idioma = idiomas.get(pais)
            if not idioma:
                continue
            entrantes = _entrantes(mem, clave_mem, pais) if mem is not None else embebidos.get(pais)
            if entrantes is not None and (_entrantes_piso(mem, clave_mem, pais) if mem is not None
                                          else embebidos_piso.get(pais)):
                con_piso.append(pais)
            mercados.append({
                "mercado": pais,
                "idioma": idioma,
                "hueco": {"original_presente": False, "anunciantes_sostenidos": 0, "puntaje_rival": None,
                          "entrantes_30d": entrantes},
                "ventana": "evergreen",
                "transferibilidad": {k: None for k in pm.TRANSFERIBILIDAD},
                "_nota": ("El original NO corre aquí: la pasada 3 midió esta página en el país y declaró 0 anuncios "
                          "(sigue sin saberse si hay competidores equivalentes). 'ventana' es un relleno sin evaluar."
                          if pais in pagina.get("paises_ausencia_medida", []) else
                          "Ausencia en la MUESTRA del barrido (no en el mercado): hipótesis hasta medir con la "
                          "pasada 3. 'ventana' es un relleno sin evaluar."),
            })
        if not mercados:
            omitidas.append(f"{pagina['page_id']}: sin_mercado_destino_con_ausencia")
            return
        pendiente = [
            "puertas: " + ", ".join(pm.PUERTAS) + " sin evaluar (juicio con rúbrica sobre el anuncio real)",
            "transferibilidad: " + ", ".join(pm.TRANSFERIBILIDAD) + " sin evaluar en cada mercado",
            "reencuadres: sin diseñar",
            "ventana: 'evergreen' es un relleno, no está evaluada",
            "hueco: ausencia en la muestra del barrido; confirmar con la pasada 3 (page_ids × país) y auditar "
            "al rival si aparece",
        ]
        if pagina.get("es_oferta_digital_pago_unico") is None:
            pendiente.append("es_oferta_digital_pago_unico: sin determinar (null); verificar el modelo de cobro "
                             "(pago único) en la captura del anuncio/landing antes de lanzar")
        if sin_tema:
            origen = ("la página no tiene títulos (sin títulos no se pudo etiquetar)"
                      if pagina.get("origen_sin_tema") == "sin_titulos" else "los títulos no permiten saber el tema")
            pendiente.append(f"tema_indeterminado: {origen}; la captura de la ficha/landing debe aclararlo; el hueco "
                             "es el del original solo (no hay mapa del tema)")
        if any(m["hueco"]["entrantes_30d"] is None for m in mercados):
            pendiente.append("entrantes_30d: sin base de memoria (null; nunca 0 por defecto)")
        if con_piso:
            pendiente.append("entrantes_30d es un piso (muestra truncada) en " + ", ".join(con_piso)
                             + ": puede haber más entrantes de los contados, lo que favorece el hueco")
        if pagina.get("regla_traccion") == "medida":
            if pagina.get("anuncios_activos_medidos_es_piso"):
                pendiente.append(f"traccion.anuncios_activos es un PISO (medición {pagina['medicion_estado']}): puede "
                                 "haber más anuncios activos de los contados; completar con la pasada 3")
            if pagina.get("edad_es_piso"):
                pendiente.append("traccion.edad_oferta_dias es un PISO: pueden existir anuncios más viejos aún no vistos")
        elif pagina["muestra_truncada"]:
            pendiente.append("traccion: muestra truncada, anuncios y edad son un piso; medir con la pasada 2/3")
        proxy = ("anunciantes_independientes_mismo_angulo = otros anunciantes independientes del tema en la muestra "
                 "(proxy)" if not sin_tema else "anunciantes_independientes_mismo_angulo = 0 (sin tema no hay con quién "
                                                "comparar)")
        ofertas.append({
            "modelo_id": _modelo_id(prefijo, pagina),
            "nombre": _nombre_ficha(tema_texto, pagina),
            "fuente": {"idioma": idioma_fuente, "pais": pagina["pais_fuente"]},
            "macro_nicho": pagina["macro_nicho"],
            "traccion": {
                "anuncios_activos": pagina.get("anuncios_activos_traccion", pagina["anuncios_activos_en_muestra"]),
                "edad_oferta_dias": pagina["edad_oferta_dias"],
                "conceptos_unicos": pagina["conceptos_unicos"],
                "paginas_misma_landing": pagina["paginas_en_grupo"],
                "anunciantes_independientes_mismo_angulo": otros_independientes,
            },
            "puertas": {g: None for g in pm.PUERTAS},
            "reencuadres": [],
            "pendiente": pendiente,
            "mercados": mercados,
            "_nota": ("Borrador automático del barrido. paginas_misma_landing = páginas con títulos idénticos "
                      f"(proxy); {proxy}."),
        })

    def representantes(paginas: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return sorted((p for p in paginas if p["estado_traccion"] == PASA and p["cuenta_como_independiente"]),
                      key=lambda p: _clave_id(p["page_id"]))

    for tema in candidatos_doc["temas"]:
        for pagina in representantes(tema["paginas"]):
            agregar(pagina, prefijo=tema["tema_slug"], tema_texto=tema["tema"], huecos=tema["huecos"],
                    clave_mem=tema["tema_slug"], embebidos=tema.get("entrantes_30d", {}),
                    embebidos_piso=tema.get("entrantes_30d_piso", {}),
                    otros_independientes=max(0, tema["anunciantes_independientes"] - 1), sin_tema=False)
    for pagina in representantes(candidatos_doc.get("sin_tema", [])):
        agregar(pagina, prefijo="sin-tema", tema_texto="Sin tema", huecos=pagina["huecos"],
                clave_mem=pagina["page_id"], embebidos=pagina.get("entrantes_30d", {}),
                embebidos_piso=pagina.get("entrantes_30d_piso", {}),
                otros_independientes=0, sin_tema=True)
    nota = f"corrida_id={candidatos_doc['corrida_id']}; borrador de fichas del barrido (ranking.py): {len(ofertas)} ficha(s)."
    if omitidas:
        nota += f" Sin ficha ({len(omitidas)}): " + "; ".join(omitidas[:20]) + ("; …" if len(omitidas) > 20 else "") + "."
    doc = {"schema_version": SCHEMA_FICHAS, "_nota": nota, "ofertas": ofertas}
    if ofertas:
        pm.validar_fichas(doc, par_modelado)
    _sin_float(doc)
    return doc


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def _exigir_corrida(corrida_id: Any) -> str:
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido {_ver(corrida_id)}: se espera AAAA-MM-DD-<letra>")
    return corrida_id


def ruta_candidatos(corrida_id: str, raiz: Path | None = None) -> Path:
    """`empresa/barrido/candidatos/<corrida_id>.json`."""
    return comun.dir_barrido(raiz) / "candidatos" / f"{_exigir_corrida(corrida_id)}.json"


def ruta_fichas_borrador(corrida_id: str, raiz: Path | None = None) -> Path:
    """`empresa/barrido/candidatos/<corrida_id>/fichas_borrador.json`."""
    return comun.dir_barrido(raiz) / "candidatos" / _exigir_corrida(corrida_id) / "fichas_borrador.json"


def escribir_candidatos(doc: Mapping[str, Any], raiz: Path | None = None) -> Path:
    """Escribe el documento «Candidatos» (atómico, sin sobrescribir). Devuelve la ruta."""
    if not isinstance(doc, Mapping) or doc.get("schema_version") != SCHEMA_VERSION \
            or not isinstance(doc.get("temas"), list):
        raise ErrorValidacion("doc: se esperaba el documento «Candidatos» {schema_version, corrida_id, temas, ...}")
    ruta = ruta_candidatos(doc.get("corrida_id"), raiz)
    _sin_float(doc)
    comun.escribir_json_nuevo(ruta, doc)
    return ruta


def escribir_fichas_borrador(doc: Mapping[str, Any], raiz: Path | None = None, *,
                             corrida_id: str | None = None) -> Path | None:
    """Escribe el borrador de fichas junto a los candidatos. Devuelve la ruta, o `None` si no hay fichas.

    Sin fichas no se escribe nada: un documento con `ofertas: []` lo rechazaría `validar_fichas`. El `corrida_id` sale
    del argumento o, si falta, de la `_nota` que puso `puente_a_fichas` («corrida_id=AAAA-MM-DD-x; …»).
    """
    if not isinstance(doc, Mapping) or doc.get("schema_version") != SCHEMA_FICHAS or not isinstance(doc.get("ofertas"), list):
        raise ErrorValidacion(f"doc: se esperaba un documento de fichas schema_version {SCHEMA_FICHAS!r}")
    if corrida_id is None:
        coincide = _RE_CORRIDA_EN_NOTA.search(str(doc.get("_nota", "")))
        if coincide is None:
            raise ErrorUso("no se pudo determinar el corrida_id: pásalo con corrida_id= o usa la salida de puente_a_fichas")
        corrida_id = coincide.group(1)
    ruta = ruta_fichas_borrador(corrida_id, raiz)
    if not doc["ofertas"]:
        return None
    _sin_float(doc)
    comun.escribir_json_nuevo(ruta, doc)
    return ruta
