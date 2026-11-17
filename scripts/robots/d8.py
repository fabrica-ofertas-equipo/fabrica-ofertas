"""Puente con los scripts de la skill ``d8-optimizacion`` (reglas J3 y de fatiga en sombra) sin tocarlos.

Los scripts de la skill no son un paquete: se cargan por ruta desde el REPOSITORIO (no desde ``--raiz``, que puede ser una raíz temporal).
``preparar_expediente.py`` lee la base en ``mode=ro``; ``proponer.py`` solo calcula una PROPUESTA (``es_propuesta: true``).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from scripts.robots.nucleo import Contexto, ErrorRobot, ofertas_en_base

__all__ = ["UMBRALES_FATIGA", "UMBRALES_LANZAMIENTO", "cargar", "entradas_por_oferta", "faltantes", "leer_umbrales"]

_SCRIPTS = Path(".claude") / "skills" / "d8-optimizacion" / "scripts"


def cargar(c: Contexto, nombre: str) -> ModuleType:
    """Importa ``.claude/skills/d8-optimizacion/scripts/<nombre>.py`` por ruta (una sola vez por proceso)."""
    clave = f"robots_d8_{nombre}"
    if clave in sys.modules:
        return sys.modules[clave]
    ruta = c.repo / _SCRIPTS / f"{nombre}.py"
    if not ruta.is_file():
        raise ErrorRobot(f"falta la skill d8-optimizacion: no existe {_SCRIPTS / (nombre + '.py')}")
    spec = importlib.util.spec_from_file_location(clave, ruta)
    if spec is None or spec.loader is None:
        raise ErrorRobot(f"no se pudo cargar {_SCRIPTS / (nombre + '.py')}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[clave] = modulo
    try:
        spec.loader.exec_module(modulo)
    except BaseException:
        sys.modules.pop(clave, None)
        raise
    return modulo


def _claves(c: Contexto) -> tuple[tuple[str, ...], tuple[str, ...]]:
    p = cargar(c, "proponer")
    return tuple(p.CLAVES_LANZAMIENTO), tuple(p.CLAVES_FATIGA)


UMBRALES_LANZAMIENTO = "lanzamiento"
UMBRALES_FATIGA = "fatiga"


def leer_umbrales(c: Contexto) -> tuple[dict[str, Any], str]:
    """``(umbrales, fuente)``. Salen de ``parametros.yaml`` + ``limites.yaml`` (lo firmado/propuesto); lo que falta queda en ``None``.

    Con ``--umbrales ARCHIVO.json`` se usan ESOS valores (para simular «qué pasaría si el dueño firma esto»): la fuente lo dice, porque NO son firmados.
    """
    p = cargar(c, "proponer")
    if c.umbrales_archivo is not None:
        try:
            u = p.leer_umbrales(c.umbrales_archivo)
        except p.ErrorProponer as exc:
            raise ErrorRobot(f"no se pudo leer el archivo de umbrales: {exc}") from exc
        return dict(u), "archivo --umbrales (NO firmados: solo para simular)"
    ruta_par = c.raiz / "empresa" / "parametros.yaml"
    ruta_lim = c.raiz / "empresa" / "limites.yaml"
    if not ruta_par.is_file():
        todas = (*p.CLAVES_LANZAMIENTO, *p.CLAVES_FATIGA, *p.CLAVES_OPCIONALES, *(f"limites.{k}" for k in p.CLAVES_LIMITES_J4))
        return {k: None for k in todas}, "sin empresa/parametros.yaml"
    try:
        doc = p.umbrales_desde_yaml(ruta_par, ruta_lim if ruta_lim.is_file() else None)
    except (OSError, ValueError, p.ErrorProponer) as exc:  # YAML dañado: fail-closed, todo en None
        todas = (*p.CLAVES_LANZAMIENTO, *p.CLAVES_FATIGA, *p.CLAVES_OPCIONALES)
        return {k: None for k in todas}, f"empresa/parametros.yaml ilegible ({type(exc).__name__})"
    return dict(doc["umbrales"]), "empresa/parametros.yaml + empresa/limites.yaml"


def faltantes(c: Contexto, umbrales: dict[str, Any], regla: str) -> list[str]:
    lanz, fat = _claves(c)
    claves = lanz if regla == UMBRALES_LANZAMIENTO else fat
    return [k for k in claves if umbrales.get(k) is None]


def entradas_por_oferta(c: Contexto, conn: Any) -> list[dict[str, Any]]:
    """Arma la ``entrada_d8`` de cada oferta de la base (solo lectura): ``[{oferta_id, entrada|None, motivo|None}]``.

    ``motivo`` se llena cuando una oferta no se pudo armar (varias zonas horarias, tabla ausente…): esa oferta queda «no evaluable»,
    las demás siguen. Una base sin las migraciones de ``datos/`` (código 4) se devuelve como un único elemento con ``oferta_id`` ``None``.
    """
    pe = cargar(c, "preparar_expediente")
    salida: list[dict[str, Any]] = []
    for oid in ofertas_en_base(conn):
        try:
            entrada = pe.armar_entrada(conn, oid, c.fecha_cuenta, ahora=c.ahora(), raiz=c.raiz)
        except pe.ErrorEntrada as exc:
            if getattr(exc, "codigo", 3) == 4:
                return [{"oferta_id": None, "entrada": None, "motivo": f"la base no tiene las tablas de datos/ ({exc})"[:200], "base_incompleta": True}]
            salida.append({"oferta_id": oid, "entrada": None, "motivo": str(exc)[:200]})
            continue
        salida.append({"oferta_id": oid, "entrada": entrada, "motivo": None})
    return salida
