#!/usr/bin/env python3
"""Puntaje de modelado (PM) de D1, Modo D: ordena pares «oferta fuente × mercado destino».

Los LLM proponen (llenan la ficha con evidencia y juicio), el código dispone (calcula, veta y ordena).
Ningún umbral está fijado aquí: todo sale de un YAML con el formato de `empresa/parametros.yaml`
(grupo `grupos.descubrimiento`, claves `modelado_*`). Sin `float`: aritmética con `decimal.Decimal`.

Fórmula (docs: departamentos/02-descubrimiento.md §12):

    PM = G × T^wT × H^wH × X^wX × D^wD × 100        (todos los factores en [0, 1])

  G  puertas: 0 si alguna está en `true` (marca personal, sustituto gratis,
     práctica vetada). Una puerta en `null` deja la ficha «incompleta» (no se asume nada).
  T  tracción en el origen: media geométrica de volumen, edad, conceptos únicos y réplica.
  H  hueco en el destino: hueco de idioma × (1 − entrantes recientes) × ventana estacional.
  X  transferibilidad: media geométrica de dolor universal, viabilidad de ticket
     y riesgo de políticas.
  D  diferenciación: según cuántos reencuadres válidos (mecanismo, lista→sistema, etc.) se sustentan.

Uso (desde la raíz del repositorio, con el intérprete de `.venv`):

    .venv/bin/python -m scripts.modelado.puntaje_modelar puntuar fichas.json --parametros P.yaml
    .venv/bin/python -m scripts.modelado.puntaje_modelar resumir filas.json --ahora 2026-11-06T12:00:00Z

Códigos de salida: 0 correcto · 2 uso incorrecto · 3 validación · 5 parámetro faltante (falla cerrado).
Limitaciones: ver scripts/modelado/README.md. El PM ordena candidatos; NO predice ventas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Vocabularios cerrados (categorías, no umbrales)
# ---------------------------------------------------------------------------

PUERTAS = (
    "marca_personal",
    "sustituto_gratis_cubre",
    "practica_vetada",
)
TRANSFERIBILIDAD = ("dolor_universal", "viabilidad_ticket", "riesgo_politicas")
REENCUADRES = (
    "mecanismo_nombrable",
    "lista_a_sistema",
    "cambio_de_unidad",
    "subnicho_x_obstaculo",
    "autoridad_local",
    "localizacion_cultural",
    "precio_alto_a_bajo",
)
VENTANAS = ("evergreen", "abierta", "cierra_pronto", "vencida")
MACRO_NICHOS = ("salud", "relaciones", "dinero")  # contratos/comunes.schema.json#/$defs/macro_nicho
FACTORES = ("T", "H", "X", "D")

# Claves que el script exige en `grupos.descubrimiento` del YAML de parámetros.
CLAVES_PARAMETROS = (
    "modelado_anuncios_objetivo",
    "modelado_dias_objetivo",
    "modelado_conceptos_objetivo",
    "modelado_replica_baja",
    "modelado_entrantes_tope_30d",
    "modelado_sostenidos_cierre",
    "modelado_rival_debil_bajo",
    "modelado_hueco_rival_debil",
    "modelado_hueco_rival_fuerte",
    "modelado_ventana_cierra_pronto",
    "modelado_dif_base",
    "modelado_dif_un_reencuadre",
    "modelado_dif_dos_o_mas",
    "modelado_peso_traccion",
    "modelado_peso_hueco",
    "modelado_peso_transferibilidad",
    "modelado_peso_diferenciacion",
    "modelado_umbral_pasa",
    "modelado_sens_variacion",
    "modelado_sens_cobertura_min",
    "modelado_sens_top",
    "modelado_juicio_tolerancia",
    "modelado_evidencia_min_caracteres",
    "modelado_calibracion_min_casos",
    "modelado_acuerdo_min",
    "modelado_captura_pausa_seg",
    "modelado_captura_max_por_dia",
    "modelado_captura_espera_ms",
    "modelado_captura_timeout_seg",
    "modelado_lectura_max_bytes",
    "modelado_lectura_timeout_seg",
    "modelado_lectura_max_caracteres",
    "modelado_lectura_max_redirecciones",
    "modelado_lectura_max_paginas",
    "modelado_lectura_pausa_seg",
)

UNO = Decimal(1)
CERO = Decimal(0)
CIEN = Decimal(100)

# Cambia solo si cambia la fórmula (no los parámetros): forma parte del sello de reglas.
FORMULA_VERSION = "pm-2"


# ---------------------------------------------------------------------------
# Errores tipados (códigos de salida de docs/convenciones-de-codigo.md §8)
# ---------------------------------------------------------------------------

class ErrorFabrica(Exception):
    """Base de los errores esperados; `codigo_salida` es el código de salida de la CLI."""

    codigo_salida = 1


class ErrorUso(ErrorFabrica):
    """Argumentos, rutas o archivos de entrada inutilizables (2)."""

    codigo_salida = 2


class ErrorValidacion(ErrorFabrica):
    """Dato inconsistente o fuera de contrato (3)."""

    codigo_salida = 3


class ErrorBloqueado(ErrorFabrica):
    """Las reglas en uso no son las aprobadas (sello distinto): no se calcula nada (4)."""

    codigo_salida = 4


class ErrorLimite(ErrorFabrica):
    """Falta un parámetro o límite necesario: no se asume ningún valor (5)."""

    codigo_salida = 5


# ---------------------------------------------------------------------------
# Lectura y validación de tipos básicos (sin float)
# ---------------------------------------------------------------------------

def raiz_repositorio() -> Path:
    """Raíz del repositorio: `FABRICA_RAIZ` si existe; si no, dos niveles sobre este archivo."""
    entorno = os.environ.get("FABRICA_RAIZ")
    return Path(entorno) if entorno else Path(__file__).resolve().parents[2]


def _rechazar_constante(nombre: str) -> Any:
    raise ErrorValidacion(f"JSON con constante no permitida: {nombre}")


def leer_json(ruta: Path) -> Any:
    """Lee un JSON con decimales exactos (`Decimal`) y sin NaN/Infinity.

    Errores: ErrorUso si no se puede leer; ErrorValidacion si no es JSON válido.
    """
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErrorUso(f"no se pudo leer {ruta}: {exc}") from exc
    try:
        return json.loads(texto, parse_float=Decimal, parse_constant=_rechazar_constante)
    except json.JSONDecodeError as exc:
        raise ErrorValidacion(f"{ruta}: JSON inválido ({exc})") from exc


def _decimal(valor: Any, campo: str) -> Decimal:
    """Convierte int, cadena decimal o Decimal a Decimal finito. Rechaza bool y float."""
    if isinstance(valor, bool) or isinstance(valor, float):
        raise ErrorValidacion(f"{campo}: use entero o cadena decimal, no {type(valor).__name__}")
    if isinstance(valor, (int, Decimal)):
        d = Decimal(valor)
    elif isinstance(valor, str):
        try:
            d = Decimal(valor.strip())
        except InvalidOperation as exc:
            raise ErrorValidacion(f"{campo}: «{valor}» no es un decimal") from exc
    else:
        raise ErrorValidacion(f"{campo}: se esperaba un número, llegó {type(valor).__name__}")
    if not d.is_finite():
        raise ErrorValidacion(f"{campo}: valor no finito")
    return d


def _ratio(valor: Any, campo: str, *, nulo_ok: bool = False) -> Decimal | None:
    """Decimal en [0, 1]. Si `nulo_ok` y llega None, devuelve None (dato aún sin evaluar)."""
    if valor is None:
        if nulo_ok:
            return None
        raise ErrorValidacion(f"{campo}: falta el valor")
    d = _decimal(valor, campo)
    if d < CERO or d > UNO:
        raise ErrorValidacion(f"{campo}: {d} fuera de [0, 1]")
    return d


def _entero(valor: Any, campo: str, *, minimo: int = 0, maximo: int | None = None) -> int:
    """Entero estricto (rechaza bool, float y decimales con parte fraccionaria)."""
    if isinstance(valor, bool) or isinstance(valor, float):
        raise ErrorValidacion(f"{campo}: se esperaba un entero")
    if isinstance(valor, Decimal):
        if valor != valor.to_integral_value():
            raise ErrorValidacion(f"{campo}: {valor} no es entero")
        valor = int(valor)
    if not isinstance(valor, int):
        raise ErrorValidacion(f"{campo}: se esperaba un entero, llegó {type(valor).__name__}")
    if valor < minimo or (maximo is not None and valor > maximo):
        rango = f"≥ {minimo}" if maximo is None else f"[{minimo}, {maximo}]"
        raise ErrorValidacion(f"{campo}: {valor} fuera de {rango}")
    return valor


def _mapa(valor: Any, campo: str, claves: Iterable[str], opcionales: Iterable[str] = ()) -> Mapping[str, Any]:
    """Verifica que `valor` sea un objeto con exactamente las claves esperadas."""
    if not isinstance(valor, dict):
        raise ErrorValidacion(f"{campo}: se esperaba un objeto")
    esperadas = set(claves)
    permitidas = esperadas | set(opcionales)
    faltan = sorted(esperadas - set(valor))
    sobran = sorted(set(valor) - permitidas)
    if faltan:
        raise ErrorValidacion(f"{campo}: faltan campos {faltan}")
    if sobran:
        raise ErrorValidacion(f"{campo}: campos no reconocidos {sobran}")
    return valor


def _texto(d: Decimal | None, lugares: int) -> str | None:
    """Decimal → cadena con `lugares` decimales (ROUND_HALF_EVEN); None se conserva."""
    if d is None:
        return None
    return format(d.quantize(Decimal(1).scaleb(-lugares), rounding=ROUND_HALF_EVEN), "f")


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def cargar_parametros(ruta: Path | None = None) -> dict[str, Any]:
    """Carga los parámetros `modelado_*` de `grupos.descubrimiento` y los valida.

    Entradas: ruta a un YAML con el formato de `empresa/parametros.yaml` (por defecto, ese archivo).
    Salida: dict clave → int o Decimal. Errores: ErrorLimite si falta algún parámetro (falla
    cerrado); ErrorValidacion si un valor está fuera de rango o los pesos no suman 1.
    """
    import yaml  # PyYAML está en requirements.txt de la raíz

    ruta = ruta or raiz_repositorio() / "empresa" / "parametros.yaml"
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer el archivo de parámetros {ruta}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ErrorValidacion(f"{ruta}: YAML inválido ({exc})") from exc
    grupo = ((datos or {}).get("grupos") or {}).get("descubrimiento") or {}
    crudos: dict[str, Any] = {}
    faltan: list[str] = []
    for clave in CLAVES_PARAMETROS:
        entrada = grupo.get(clave)
        if not isinstance(entrada, dict) or "valor" not in entrada:
            faltan.append(clave)
        else:
            crudos[clave] = entrada["valor"]
    if faltan:
        raise ErrorLimite(
            f"faltan parámetros de Modo D en {ruta}: {', '.join(faltan)}. "
            "Propuesta lista para aprobar: scripts/modelado/parametros_modelado.propuesta.yaml"
        )
    return normalizar_parametros(crudos)


def normalizar_parametros(crudos: Mapping[str, Any]) -> dict[str, Any]:
    """Convierte y valida los parámetros crudos (enteros y decimales exactos)."""
    p: dict[str, Any] = {}
    for clave in ("modelado_anuncios_objetivo", "modelado_conceptos_objetivo",
                  "modelado_entrantes_tope_30d", "modelado_sostenidos_cierre", "modelado_sens_top",
                  "modelado_evidencia_min_caracteres", "modelado_calibracion_min_casos",
                  "modelado_captura_pausa_seg", "modelado_captura_max_por_dia", "modelado_captura_espera_ms",
                  "modelado_captura_timeout_seg", "modelado_lectura_max_bytes", "modelado_lectura_timeout_seg",
                  "modelado_lectura_max_caracteres", "modelado_lectura_max_redirecciones",
                  "modelado_lectura_max_paginas", "modelado_lectura_pausa_seg"):
        p[clave] = _entero(crudos[clave], clave, minimo=1)
    p["modelado_rival_debil_bajo"] = _entero(crudos["modelado_rival_debil_bajo"], "modelado_rival_debil_bajo",
                                              minimo=0, maximo=100)
    p["modelado_umbral_pasa"] = _entero(crudos["modelado_umbral_pasa"], "modelado_umbral_pasa", minimo=0, maximo=100)
    dias = _decimal(crudos["modelado_dias_objetivo"], "modelado_dias_objetivo")
    if dias <= CERO:
        raise ErrorValidacion("modelado_dias_objetivo: debe ser > 0")
    p["modelado_dias_objetivo"] = dias
    for clave in ("modelado_replica_baja", "modelado_hueco_rival_debil", "modelado_hueco_rival_fuerte",
                  "modelado_ventana_cierra_pronto", "modelado_dif_base", "modelado_dif_un_reencuadre",
                  "modelado_dif_dos_o_mas", "modelado_sens_variacion", "modelado_sens_cobertura_min",
                  "modelado_juicio_tolerancia", "modelado_acuerdo_min"):
        p[clave] = _ratio(crudos[clave], clave)
    pesos = ("modelado_peso_traccion", "modelado_peso_hueco",
             "modelado_peso_transferibilidad", "modelado_peso_diferenciacion")
    for clave in pesos:
        p[clave] = _ratio(crudos[clave], clave)
    if sum(p[c] for c in pesos) != UNO:
        raise ErrorValidacion("los cuatro pesos de modelado_peso_* deben sumar exactamente 1")
    return p


def _pesos(p: Mapping[str, Any]) -> dict[str, Decimal]:
    return {
        "T": p["modelado_peso_traccion"],
        "H": p["modelado_peso_hueco"],
        "X": p["modelado_peso_transferibilidad"],
        "D": p["modelado_peso_diferenciacion"],
    }


def _canonico(valor: Any) -> str:
    """Número → texto canónico (25, 25.0 y "25" dan lo mismo)."""
    return format(Decimal(valor).normalize(), "f")


def sello_reglas(p: Mapping[str, Any]) -> str:
    """Sello SHA-256 de las reglas en uso: versión de la fórmula + parámetros + vocabularios.

    Sirve para probar que el ranking se calculó con las reglas aprobadas: si alguien (o una IA) cambia
    un umbral, un peso o un vocabulario, el sello cambia. Convención del repo: JSON canónico, NFC, `sha256:<hex>`.
    """
    contenido = {
        "formula": FORMULA_VERSION,
        "parametros": {k: _canonico(v) for k, v in sorted(p.items())},
        "vocabularios": {"puertas": list(PUERTAS), "transferibilidad": list(TRANSFERIBILIDAD),
                         "reencuadres": list(REENCUADRES), "ventanas": list(VENTANAS)},
    }
    texto = json.dumps(contenido, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(unicodedata.normalize("NFC", texto).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validación de las fichas
# ---------------------------------------------------------------------------

def validar_fichas(doc: Any, p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Valida el documento de fichas y devuelve la lista de ofertas con tipos normalizados.

    Formato: {"schema_version": "2.0.0", "ofertas": [ ... ]} (ver scripts/modelado/README.md).
    Cualquier campo faltante, fuera de rango o desconocido es ErrorValidacion con la ruta del campo.
    """
    raiz = _mapa(doc, "fichas", ("schema_version", "ofertas"), ("_nota",))
    if raiz["schema_version"] != "2.0.0":
        raise ErrorValidacion(f"fichas.schema_version: {raiz['schema_version']!r} no soportada (MAJOR 1)")
    if not isinstance(raiz["ofertas"], list) or not raiz["ofertas"]:
        raise ErrorValidacion("fichas.ofertas: debe ser una lista no vacía")
    vistos: set[str] = set()
    salida = []
    for i, oferta in enumerate(raiz["ofertas"]):
        salida.append(_validar_oferta(oferta, f"ofertas[{i}]", p, vistos))
    return salida


def _validar_oferta(o: Any, ruta: str, p: Mapping[str, Any], vistos: set[str]) -> dict[str, Any]:
    o = _mapa(o, ruta, ("modelo_id", "nombre", "fuente", "macro_nicho", "traccion", "puertas",
                        "reencuadres", "mercados"), ("pendiente", "_nota"))
    modelo_id = o["modelo_id"]
    if not isinstance(modelo_id, str) or not _es_kebab(modelo_id):
        raise ErrorValidacion(f"{ruta}.modelo_id: debe ser kebab-case ASCII")
    if modelo_id in vistos:
        raise ErrorValidacion(f"{ruta}.modelo_id: «{modelo_id}» repetido")
    vistos.add(modelo_id)
    if not isinstance(o["nombre"], str) or not o["nombre"].strip():
        raise ErrorValidacion(f"{ruta}.nombre: texto no vacío")
    fuente = _mapa(o["fuente"], f"{ruta}.fuente", ("idioma", "pais"))
    if not isinstance(fuente["idioma"], str) or not fuente["idioma"]:
        raise ErrorValidacion(f"{ruta}.fuente.idioma: texto no vacío")
    _pais(fuente["pais"], f"{ruta}.fuente.pais")
    macro = o["macro_nicho"]
    if macro is not None and macro not in MACRO_NICHOS:
        raise ErrorValidacion(f"{ruta}.macro_nicho: {macro!r} no está en {MACRO_NICHOS} ni es null")
    t = _mapa(o["traccion"], f"{ruta}.traccion",
              ("anuncios_activos", "edad_oferta_dias", "conceptos_unicos",
               "paginas_misma_landing", "anunciantes_independientes_mismo_angulo"))
    traccion = {
        "anuncios_activos": _entero(t["anuncios_activos"], f"{ruta}.traccion.anuncios_activos"),
        "edad_oferta_dias": _decimal(t["edad_oferta_dias"], f"{ruta}.traccion.edad_oferta_dias"),
        "conceptos_unicos": _entero(t["conceptos_unicos"], f"{ruta}.traccion.conceptos_unicos"),
        "paginas_misma_landing": _entero(t["paginas_misma_landing"], f"{ruta}.traccion.paginas_misma_landing"),
        "anunciantes_independientes_mismo_angulo": _entero(
            t["anunciantes_independientes_mismo_angulo"],
            f"{ruta}.traccion.anunciantes_independientes_mismo_angulo"),
    }
    if traccion["edad_oferta_dias"] < CERO:
        raise ErrorValidacion(f"{ruta}.traccion.edad_oferta_dias: no puede ser negativa")
    a, c = traccion["anuncios_activos"], traccion["conceptos_unicos"]
    if a == 0 and (c != 0 or traccion["paginas_misma_landing"] != 0):
        raise ErrorValidacion(f"{ruta}.traccion: sin anuncios activos, conceptos y páginas deben ser 0")
    if a > 0 and not (1 <= c <= a):
        raise ErrorValidacion(f"{ruta}.traccion.conceptos_unicos: debe estar entre 1 y anuncios_activos ({a})")
    if a > 0 and traccion["paginas_misma_landing"] < 1:
        raise ErrorValidacion(f"{ruta}.traccion.paginas_misma_landing: con anuncios activos debe ser ≥ 1")
    puertas = _mapa(o["puertas"], f"{ruta}.puertas", PUERTAS)
    for nombre, valor in puertas.items():
        if valor is not None and not isinstance(valor, bool):
            raise ErrorValidacion(f"{ruta}.puertas.{nombre}: true, false o null (sin evaluar)")
    reencuadres = _reencuadres(o["reencuadres"], f"{ruta}.reencuadres")
    pendiente = o.get("pendiente", [])
    if not isinstance(pendiente, list) or not all(isinstance(x, str) for x in pendiente):
        raise ErrorValidacion(f"{ruta}.pendiente: lista de textos")
    if not isinstance(o["mercados"], list) or not o["mercados"]:
        raise ErrorValidacion(f"{ruta}.mercados: lista no vacía")
    paises: set[str] = set()
    mercados = []
    for j, m in enumerate(o["mercados"]):
        mercado = _validar_mercado(m, f"{ruta}.mercados[{j}]", p)
        if mercado["mercado"] in paises:
            raise ErrorValidacion(f"{ruta}.mercados[{j}].mercado: «{mercado['mercado']}» repetido")
        paises.add(mercado["mercado"])
        mercados.append(mercado)
    return {
        "modelo_id": modelo_id, "nombre": o["nombre"], "fuente": dict(fuente), "macro_nicho": macro,
        "traccion": traccion, "puertas": dict(puertas), "reencuadres": reencuadres,
        "pendiente": list(pendiente), "mercados": mercados,
    }


def _validar_mercado(m: Any, ruta: str, p: Mapping[str, Any]) -> dict[str, Any]:
    m = _mapa(m, ruta, ("mercado", "idioma", "hueco", "ventana", "transferibilidad"),
              ("reencuadres_mercado", "_nota"))
    _pais(m["mercado"], f"{ruta}.mercado")
    if not isinstance(m["idioma"], str) or not m["idioma"]:
        raise ErrorValidacion(f"{ruta}.idioma: texto no vacío")
    h = _mapa(m["hueco"], f"{ruta}.hueco",
              ("original_presente", "anunciantes_sostenidos", "puntaje_rival", "entrantes_30d"))
    if not isinstance(h["original_presente"], bool):
        raise ErrorValidacion(f"{ruta}.hueco.original_presente: true o false")
    sostenidos = _entero(h["anunciantes_sostenidos"], f"{ruta}.hueco.anunciantes_sostenidos")
    puntaje = h["puntaje_rival"]
    if puntaje is not None:
        puntaje = _entero(puntaje, f"{ruta}.hueco.puntaje_rival", minimo=0, maximo=100)
    # null = sin snapshot previo con el que comparar: la ficha queda incompleta (no se asume 0)
    entrantes = (None if h["entrantes_30d"] is None
                 else _entero(h["entrantes_30d"], f"{ruta}.hueco.entrantes_30d"))
    necesita_rival = (not h["original_presente"]) and 0 < sostenidos < p["modelado_sostenidos_cierre"]
    if necesita_rival and puntaje is None:
        raise ErrorValidacion(
            f"{ruta}.hueco.puntaje_rival: con {sostenidos} anunciante(s) sostenido(s) hace falta "
            "el puntaje del auditor (0-100) para saber si el rival es débil")
    if m["ventana"] not in VENTANAS:
        raise ErrorValidacion(f"{ruta}.ventana: {m['ventana']!r} no está en {VENTANAS}")
    x = _mapa(m["transferibilidad"], f"{ruta}.transferibilidad", TRANSFERIBILIDAD)
    transferibilidad = {k: _ratio(x[k], f"{ruta}.transferibilidad.{k}", nulo_ok=True) for k in TRANSFERIBILIDAD}
    extra = _reencuadres(m.get("reencuadres_mercado", []), f"{ruta}.reencuadres_mercado")
    return {
        "mercado": m["mercado"], "idioma": m["idioma"], "ventana": m["ventana"],
        "hueco": {"original_presente": h["original_presente"], "anunciantes_sostenidos": sostenidos,
                  "puntaje_rival": puntaje, "entrantes_30d": entrantes},
        "transferibilidad": transferibilidad, "reencuadres_mercado": extra,
    }


def _es_kebab(texto: str) -> bool:
    if not texto or texto != texto.lower() or texto.startswith("-") or texto.endswith("-") or "--" in texto:
        return False
    return all(c.isascii() and (c.isalnum() or c == "-") for c in texto)


def _pais(valor: Any, campo: str) -> None:
    if not (isinstance(valor, str) and len(valor) == 2 and valor.isascii() and valor.isalpha() and valor.isupper()):
        raise ErrorValidacion(f"{campo}: país ISO-2 en mayúsculas (p. ej. «RO»)")


def _reencuadres(valor: Any, campo: str) -> list[str]:
    if not isinstance(valor, list):
        raise ErrorValidacion(f"{campo}: se esperaba una lista")
    for r in valor:
        if r not in REENCUADRES:
            raise ErrorValidacion(f"{campo}: reencuadre {r!r} desconocido; válidos: {REENCUADRES}")
    return list(valor)


# ---------------------------------------------------------------------------
# Factores
# ---------------------------------------------------------------------------

def _pot(base: Decimal, exponente: Decimal) -> Decimal:
    """base^exponente en Decimal (0^positivo = 0)."""
    if base == CERO:
        return CERO
    return base ** exponente


def _media_geometrica(valores: Sequence[Decimal]) -> Decimal:
    producto = UNO
    for v in valores:
        producto *= v
    return _pot(producto, UNO / Decimal(len(valores)))


def calcular_traccion(t: Mapping[str, Any], p: Mapping[str, Any]) -> tuple[Decimal, dict[str, Decimal]]:
    """T en [0, 1] y sus subfactores (volumen, edad, conceptos, réplica)."""
    volumen = min(UNO, Decimal(t["anuncios_activos"]) / p["modelado_anuncios_objetivo"])
    edad = min(UNO, t["edad_oferta_dias"] / p["modelado_dias_objetivo"])
    conceptos = min(UNO, Decimal(t["conceptos_unicos"]) / p["modelado_conceptos_objetivo"])
    hay_replica = t["paginas_misma_landing"] >= 2 or t["anunciantes_independientes_mismo_angulo"] >= 2
    replica = UNO if hay_replica else p["modelado_replica_baja"]
    sub = {"t_volumen": volumen, "t_edad": edad, "t_conceptos": conceptos, "t_replica": replica}
    return _media_geometrica(list(sub.values())), sub


def calcular_hueco(h: Mapping[str, Any], ventana: str,
                   p: Mapping[str, Any]) -> tuple[Decimal | None, dict[str, Decimal | None], Decimal]:
    """H en [0, 1], sus subfactores (idioma, entrantes, ventana) y el techo de H.

    Si `entrantes_30d` es None (aún no hay snapshot previo), H es None y el techo de H usa
    entrantes = 1: lo máximo que podría valer una vez medido. Nunca se asume cero entrantes.
    """
    sostenidos = h["anunciantes_sostenidos"]
    if h["original_presente"] or sostenidos >= p["modelado_sostenidos_cierre"]:
        idioma = CERO
    elif sostenidos == 0:
        idioma = UNO
    elif h["puntaje_rival"] < p["modelado_rival_debil_bajo"]:
        idioma = p["modelado_hueco_rival_debil"]
    else:
        idioma = p["modelado_hueco_rival_fuerte"]
    if h["entrantes_30d"] is None:
        entrantes = None
    else:
        entrantes = UNO - min(UNO, Decimal(h["entrantes_30d"]) / p["modelado_entrantes_tope_30d"])
    if ventana == "vencida":
        v = CERO
    elif ventana == "cierra_pronto":
        v = p["modelado_ventana_cierra_pronto"]
    else:
        v = UNO
    sub = {"h_idioma": idioma, "h_entrantes": entrantes, "h_ventana": v}
    techo = idioma * (UNO if entrantes is None else entrantes) * v
    return (None if entrantes is None else techo), sub, techo


def calcular_transferibilidad(x: Mapping[str, Decimal | None]) -> Decimal | None:
    """X en [0, 1], o None si algún componente aún no fue evaluado."""
    if any(x[k] is None for k in TRANSFERIBILIDAD):
        return None
    return _media_geometrica([x[k] for k in TRANSFERIBILIDAD])  # type: ignore[misc]


def calcular_diferenciacion(reencuadres: Iterable[str], p: Mapping[str, Any]) -> Decimal:
    """D en [0, 1] según la cantidad de reencuadres distintos (la traducción pelada vale `dif_base`)."""
    n = len(set(reencuadres))
    if n == 0:
        return p["modelado_dif_base"]
    if n == 1:
        return p["modelado_dif_un_reencuadre"]
    return p["modelado_dif_dos_o_mas"]


# ---------------------------------------------------------------------------
# Puntaje por par y ranking
# ---------------------------------------------------------------------------

def _combinar(factores: Mapping[str, Decimal | None], pesos: Mapping[str, Decimal],
              desconocido_como: Decimal = UNO) -> Decimal:
    """CIEN × Π factor^peso; un factor None se sustituye por `desconocido_como` (techo = 1)."""
    total = CIEN
    for k in FACTORES:
        valor = factores[k] if factores[k] is not None else desconocido_como
        total *= _pot(valor, pesos[k])
    return total


def puntuar_par(oferta: Mapping[str, Any], mercado: Mapping[str, Any], p: Mapping[str, Any]) -> dict[str, Any]:
    """Puntúa un par oferta × mercado ya validado. Devuelve un dict con Decimal (ver `formatear`)."""
    t, sub_t = calcular_traccion(oferta["traccion"], p)
    h, sub_h, h_techo = calcular_hueco(mercado["hueco"], mercado["ventana"], p)
    x = calcular_transferibilidad(mercado["transferibilidad"])
    d = calcular_diferenciacion(list(oferta["reencuadres"]) + list(mercado["reencuadres_mercado"]), p)
    factores = {"T": t, "H": h, "X": x, "D": d}
    pesos = _pesos(p)
    vetos = [g for g in PUERTAS if oferta["puertas"][g] is True]
    pendientes = [g for g in PUERTAS if oferta["puertas"][g] is None]
    pendientes += [f"transferibilidad.{k}" for k in TRANSFERIBILIDAD if mercado["transferibilidad"][k] is None]
    if h is None:
        pendientes.append("hueco.entrantes_30d")
    techo = _combinar({**factores, "H": h_techo}, pesos)
    if vetos:
        estado, pm, techo = "vetada", CERO, CERO  # con veto el máximo posible es 0
    elif pendientes:
        estado, pm = "incompleta", None
    else:
        pm = techo
        estado = "pasa" if pm >= p["modelado_umbral_pasa"] else "no_pasa"
    conocidos = {k: v for k, v in factores.items() if v is not None}
    cuello = min(conocidos, key=lambda k: (conocidos[k], FACTORES.index(k))) if conocidos else None
    return {
        "modelo_id": oferta["modelo_id"], "nombre": oferta["nombre"], "mercado": mercado["mercado"],
        "macro_nicho": oferta["macro_nicho"], "en_marco": oferta["macro_nicho"] is not None,
        "estado": estado, "PM": pm, "techo": techo, "factores": factores,
        "subfactores": {**sub_t, **sub_h}, "cuello": cuello, "vetos": vetos,
        "pendientes": pendientes, "notas": list(oferta["pendiente"]),
    }


def puntuar(doc: Any, p: Mapping[str, Any], *, solo_marco: bool = False) -> list[dict[str, Any]]:
    """Valida las fichas y devuelve todos los pares puntuados, ordenados.

    Orden: primero los completos (por PM descendente), luego los incompletos (por techo descendente)
    y al final los vetados. `solo_marco` descarta las ofertas fuera de salud/relaciones/dinero.
    """
    ofertas = validar_fichas(doc, p)
    pares = [puntuar_par(o, m, p) for o in ofertas for m in o["mercados"]]
    if solo_marco:
        pares = [x for x in pares if x["en_marco"]]
    grupo = {"pasa": 0, "no_pasa": 0, "incompleta": 1, "vetada": 2}
    pares.sort(key=lambda x: (grupo[x["estado"]],
                              -(x["PM"] if x["PM"] is not None else x["techo"]),
                              x["modelo_id"], x["mercado"]))
    return pares


# ---------------------------------------------------------------------------
# Sensibilidad de los pesos (D1 §3.2: ±30 %, el top-1 debe seguir en el top-3 en ≥ 80 %)
# ---------------------------------------------------------------------------

def sensibilidad(pares: Sequence[Mapping[str, Any]], p: Mapping[str, Any]) -> dict[str, Any]:
    """Repite el ranking con cada peso ±`modelado_sens_variacion` (renormalizado a 1).

    Solo participan los pares completos y no vetados. Devuelve cobertura, estado y el top-1 base.
    Estado «insuficiente» si hay menos pares que `modelado_sens_top` + 1.
    """
    completos = [x for x in pares if x["estado"] in ("pasa", "no_pasa")]
    top_n = p["modelado_sens_top"]
    if len(completos) < top_n + 1:
        return {"estado": "insuficiente", "pares": len(completos), "perturbaciones": 0,
                "cobertura": None, "top1": None}
    base = _pesos(p)
    clave = lambda x: (x["modelo_id"], x["mercado"])  # noqa: E731
    top1 = max(completos, key=lambda x: (x["PM"], clave(x)[::-1]))
    aciertos = 0
    perturbaciones = 0
    for k in FACTORES:
        for signo in (1, -1):
            w = dict(base)
            w[k] = base[k] * (UNO + signo * p["modelado_sens_variacion"])
            suma = sum(w.values())
            w = {kk: vv / suma for kk, vv in w.items()}
            orden = sorted(completos, key=lambda x: (-_combinar(x["factores"], w), clave(x)))
            perturbaciones += 1
            if clave(top1) in [clave(x) for x in orden[:top_n]]:
                aciertos += 1
    cobertura = Decimal(aciertos) / Decimal(perturbaciones)
    estado = "robusto" if cobertura >= p["modelado_sens_cobertura_min"] else "fragil"
    return {"estado": estado, "pares": len(completos), "perturbaciones": perturbaciones,
            "cobertura": cobertura, "top1": f"{top1['modelo_id']}@{top1['mercado']}"}


# ---------------------------------------------------------------------------
# Resumen de filas de la Biblioteca (conector ads_library_search) → bloque `traccion`
# ---------------------------------------------------------------------------

def _normalizar_titulo(titulo: Any) -> str:
    texto = unicodedata.normalize("NFC", str(titulo or "")).casefold()
    return " ".join(texto.split())


def _mediana(valores: Sequence[Decimal]) -> Decimal:
    orden = sorted(valores)
    n = len(orden)
    medio = n // 2
    return orden[medio] if n % 2 else (orden[medio - 1] + orden[medio]) / 2


def resumir_anuncios(filas: Any, ahora: datetime) -> dict[str, Any]:
    """Cuenta de forma determinista lo que el Maker no debe contar a mano.

    Entrada: filas tal como las devuelve `ads_library_search` (id, page_id, ad_creative_link_title,
    ad_delivery_start_time en epoch). `ahora` debe tener zona UTC (reloj inyectado).
    Salida: anuncios distintos; **edad de la oferta** = antigüedad del 2.º anuncio activo más viejo
    (exige ≥ 2 sobrevivientes, como pide Fer, y evita que un solo anuncio zombi la infle; no se usa la
    mediana porque castiga a quien renueva creativos a diario, que es señal de escala); edad del más viejo
    y mediana (solo informativas); conceptos únicos (por título normalizado); páginas y páginas que
    comparten concepto (proxy de «misma landing», que el conector NO entrega).
    """
    if ahora.tzinfo is None:
        raise ErrorUso("`ahora` debe incluir zona horaria UTC")
    if not isinstance(filas, list) or not filas:
        raise ErrorValidacion("filas: lista no vacía de anuncios de la Biblioteca")
    ahora_epoch = Decimal(int(ahora.timestamp()))
    por_id: dict[str, Mapping[str, Any]] = {}
    for i, fila in enumerate(filas):
        if not isinstance(fila, dict):
            raise ErrorValidacion(f"filas[{i}]: se esperaba un objeto")
        for campo in ("id", "page_id", "ad_delivery_start_time"):
            if campo not in fila:
                raise ErrorValidacion(f"filas[{i}]: falta «{campo}»")
        por_id.setdefault(str(fila["id"]), fila)
    dias: list[Decimal] = []
    titulos_por_pagina: dict[str, set[str]] = {}
    futuros = 0
    sin_titulo = 0
    for fila in por_id.values():
        inicio = _decimal(fila["ad_delivery_start_time"], "ad_delivery_start_time")
        dif = (ahora_epoch - inicio) / Decimal(86400)
        if dif < CERO:
            futuros += 1
            dif = CERO
        dias.append(dif)
        titulo = _normalizar_titulo(fila.get("ad_creative_link_title"))
        if not titulo:
            sin_titulo += 1
            titulo = "(sin título)"
        titulos_por_pagina.setdefault(str(fila["page_id"]), set()).add(titulo)
    todos = set().union(*titulos_por_pagina.values())
    compartidos = {t for t in todos if sum(t in ts for ts in titulos_por_pagina.values()) >= 2
                   and t != "(sin título)"}
    paginas_compartiendo = [pg for pg, ts in titulos_por_pagina.items() if ts & compartidos]
    advertencias = []
    if len(filas) > len(por_id):
        advertencias.append(f"{len(filas) - len(por_id)} fila(s) con id repetido descartadas")
    if futuros:
        advertencias.append(f"{futuros} anuncio(s) con inicio posterior a `ahora`: edad fijada en 0")
    if sin_titulo:
        advertencias.append(f"{sin_titulo} anuncio(s) sin título cuentan como un solo concepto «(sin título)»")
    advertencias.append("el conector no entrega landing ni texto: «páginas que comparten concepto» es un proxy")
    por_edad = sorted(dias, reverse=True)
    if len(por_edad) < 2:
        advertencias.append("con un solo anuncio activo no hay sobrevivientes: edad_oferta_dias = 0")
    return {
        "anuncios_activos": len(por_id),
        "edad_oferta_dias": por_edad[1] if len(por_edad) >= 2 else CERO,
        "edad_max_dias": por_edad[0],
        "mediana_dias_activos": _mediana(dias),
        "conceptos_unicos": len(todos),
        "paginas": len(titulos_por_pagina),
        "paginas_con_concepto_compartido": len(paginas_compartiendo),
        "advertencias": advertencias,
    }


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def formatear(par: Mapping[str, Any]) -> dict[str, Any]:
    """Par puntuado → dict serializable (decimales como cadenas)."""
    return {
        "modelo_id": par["modelo_id"], "mercado": par["mercado"], "macro_nicho": par["macro_nicho"],
        "en_marco": par["en_marco"], "estado": par["estado"],
        "PM": _texto(par["PM"], 2), "techo": _texto(par["techo"], 2),
        "factores": {k: _texto(v, 3) for k, v in par["factores"].items()},
        "subfactores": {k: _texto(v, 3) for k, v in par["subfactores"].items()},
        "cuello": par["cuello"], "vetos": list(par["vetos"]), "pendientes": list(par["pendientes"]),
        "notas": list(par["notas"]),
    }


def formatear_sensibilidad(s: Mapping[str, Any]) -> dict[str, Any]:
    return {**s, "cobertura": _texto(s["cobertura"], 3)}


def resumir_pendientes(pendientes: Sequence[str]) -> str:
    """Agrupa los campos sin evaluar: «puertas×4, transferibilidad×4, hueco.entrantes_30d»."""
    grupos: dict[str, list[str]] = {}
    for campo in pendientes:
        grupos.setdefault(campo.split(".")[0] if "." in campo else "puertas", []).append(campo)
    return ", ".join(v[0] if len(v) == 1 else f"{k}×{len(v)}" for k, v in grupos.items())


def tabla_texto(pares: Sequence[Mapping[str, Any]], top: int | None) -> str:
    """Tabla legible para terminal."""
    lineas = [f"{'#':>2}  {'oferta fuente':<28} {'dest':<4} {'estado':<10} {'PM':>6} {'techo':>6}  "
              f"{'T':>5} {'H':>5} {'X':>5} {'D':>5}  cuello  notas"]
    visibles = list(pares if top is None else pares[:top])
    for i, par in enumerate(visibles, 1):
        f = {k: (_texto(v, 2) if v is not None else "  ?") for k, v in par["factores"].items()}
        notas = []
        if par["vetos"]:
            notas.append("veto: " + ", ".join(par["vetos"]))
        if par["pendientes"]:
            notas.append("sin evaluar: " + resumir_pendientes(par["pendientes"]))
        if par["notas"]:
            notas.append(f"{len(par['notas'])} nota(s) del Maker en el JSON")
        if not par["en_marco"]:
            notas.append("fuera del marco")
        lineas.append(
            f"{i:>2}  {par['modelo_id']:<28} {par['mercado']:<4} {par['estado']:<10} "
            f"{(_texto(par['PM'], 1) or '—'):>6} {_texto(par['techo'], 1):>6}  "
            f"{f['T']:>5} {f['H']:>5} {f['X']:>5} {f['D']:>5}  {par['cuello'] or '-':<6}  {'; '.join(notas)}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _escribir_nuevo(ruta: Path, texto: str) -> None:
    """Escritura atómica; nunca sobrescribe un archivo existente."""
    if ruta.exists():
        raise ErrorUso(f"{ruta} ya existe: use otro nombre (no se sobrescriben artefactos)")
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(texto, encoding="utf-8")
    os.replace(temporal, ruta)


def _analizar_ahora(texto: str) -> datetime:
    try:
        ahora = datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ErrorUso("--ahora debe ser un instante UTC ISO-8601 con Z, p. ej. 2026-11-06T12:00:00Z") from exc
    return ahora.replace(tzinfo=timezone.utc)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scripts.modelado.puntaje_modelar", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    pu = sub.add_parser("puntuar", help="puntúa y ordena pares oferta × mercado")
    pu.add_argument("fichas", type=Path)
    pu.add_argument("--parametros", type=Path, default=None, help="YAML de parámetros (por defecto empresa/parametros.yaml)")
    pu.add_argument("--json", action="store_true", help="salida JSON en vez de tabla")
    pu.add_argument("--top", type=int, default=None)
    pu.add_argument("--solo-marco", action="store_true", help="solo salud/relaciones/dinero")
    pu.add_argument("--sensibilidad", action="store_true")
    pu.add_argument("--salida", type=Path, default=None, help="escribe el JSON aquí (no sobrescribe)")
    pu.add_argument("--sello-esperado", default=None,
                    help="sello de reglas aprobado; si no coincide con las reglas en uso, no se calcula (código 4)")
    re_ = sub.add_parser("resumir", help="resume filas de ads_library_search en el bloque `traccion`")
    re_.add_argument("filas", type=Path)
    re_.add_argument("--ahora", required=True, help="instante UTC ISO-8601 con Z (reloj inyectado)")
    return parser


def main(argv: Sequence[str] | None = None, salida=None) -> int:
    """Punto de entrada. Devuelve el código de salida; los errores esperados no lanzan traza."""
    salida = salida or sys.stdout
    try:
        args = construir_parser().parse_args(argv)
    except SystemExit as exc:  # argparse sale con 2 ante uso incorrecto
        return int(exc.code or 0)
    try:
        if args.orden == "resumir":
            resumen = resumir_anuncios(leer_json(args.filas), _analizar_ahora(args.ahora))
            resumen = {**resumen, **{k: _texto(resumen[k], 1) for k in
                                     ("edad_oferta_dias", "edad_max_dias", "mediana_dias_activos")}}
            print(json.dumps(resumen, ensure_ascii=False, indent=2), file=salida)
            return 0
        p = cargar_parametros(args.parametros)
        sello = sello_reglas(p)
        if args.sello_esperado and args.sello_esperado != sello:
            raise ErrorBloqueado(f"las reglas en uso ({sello[:19]}…) no son las aprobadas "
                                 f"({args.sello_esperado[:19]}…): no se calcula nada")
        pares = puntuar(leer_json(args.fichas), p, solo_marco=args.solo_marco)
        sens = sensibilidad(pares, p) if args.sensibilidad else None
        if args.json or args.salida:
            cuerpo = {"schema_version": "1.0.0", "sello_reglas": sello, "pares": [formatear(x) for x in pares]}
            if sens is not None:
                cuerpo["sensibilidad"] = formatear_sensibilidad(sens)
            texto = json.dumps(cuerpo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if args.salida:
                _escribir_nuevo(args.salida, texto)
            if args.json:
                print(texto, end="", file=salida)
        if not args.json:
            print(tabla_texto(pares, args.top), file=salida)
            print(f"\nReglas: {sello[:19]}… (fórmula {FORMULA_VERSION})", file=salida)
            if sens is not None:
                print(f"\nSensibilidad: {sens['estado']} (top-1 {sens['top1']}, cobertura "
                      f"{_texto(sens['cobertura'], 3)} en {sens['perturbaciones']} perturbaciones)", file=salida)
        return 0
    except ErrorFabrica as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        return exc.codigo_salida


if __name__ == "__main__":
    raise SystemExit(main())
