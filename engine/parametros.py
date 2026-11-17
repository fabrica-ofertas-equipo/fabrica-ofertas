"""Cargador de ``empresa/parametros.yaml``: umbrales ajustables, nunca fijos en el código.

``cargar_parametros()`` lee y valida el archivo contra ``contratos/parametros.schema.json`` y devuelve
un objeto de solo lectura :class:`Parametros`. ``.valor("grupo.clave")`` entrega el valor de un
parámetro; si el parámetro no existe o no tiene valor (``null`` hasta calibrar) lanza
:class:`engine.errores.ParametroFaltante` (código de salida 5): la operación que lo necesita no corre.

Este módulo no decide nada: solo entrega datos. Los umbrales de decisión (``testeo.*``,
``veredicto.*``, ``estadistica.*``) los interpretan ``decision/`` y ``engine``, siempre a través de
este cargador.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterator, Mapping

import yaml

from engine import comun
from engine.errores import ErrorLimite, ErrorUso, ErrorValidacion, ParametroFaltante
from scripts.validar_esquemas import buscar_floats

__all__ = ["Parametros", "cargar_parametros", "ruta_por_defecto"]


def ruta_por_defecto(raiz: Path | None = None) -> Path:
    """Ruta de ``empresa/parametros.yaml`` bajo la raíz (``FABRICA_RAIZ`` o la del repositorio)."""
    return (raiz or comun.raiz()) / "empresa" / "parametros.yaml"


class Parametros:
    """Parámetros cargados y validados; inmutables desde fuera (``valor`` entrega copias).

    Entrada: el mapa completo del YAML (``schema_version``, ``version``, ``grupos``).
    """

    def __init__(self, datos: Mapping[str, Any], ruta: Path | None = None) -> None:
        self._datos: dict[str, Any] = copy.deepcopy(dict(datos))
        self.ruta = ruta

    @property
    def schema_version(self) -> str:
        """Versión SemVer del esquema con que se escribió el archivo."""
        return str(self._datos.get("schema_version", ""))

    @property
    def version(self) -> int:
        """Número de versión del archivo (se incrementa en cada cambio aprobado)."""
        return int(self._datos.get("version", 0))

    def _entrada(self, clave: str) -> Mapping[str, Any]:
        """Entrada completa (``valor``, ``unidad``, ``hipotesis``…) de ``grupo.clave``."""
        if not isinstance(clave, str) or clave.count(".") != 1 or not all(clave.split(".")):
            raise ErrorUso(f"clave de parámetro inválida: {clave!r} (se espera «grupo.clave»)")
        grupo, nombre = clave.split(".")
        grupos = self._datos.get("grupos")
        entrada = grupos.get(grupo, {}).get(nombre) if isinstance(grupos, dict) and isinstance(grupos.get(grupo), dict) else None
        if not isinstance(entrada, dict) or "valor" not in entrada:
            raise ParametroFaltante(clave, "no existe en parametros.yaml")
        return entrada

    def tiene(self, clave: str) -> bool:
        """¿Existe ``grupo.clave`` con un valor distinto de ``null``? (no lanza ``ParametroFaltante``)."""
        try:
            self.valor(clave)
        except ParametroFaltante:
            return False
        return True

    def valor(self, clave: str) -> Any:
        """Valor de ``grupo.clave`` (copia profunda).

        Errores: ``ParametroFaltante`` (5) si no existe o es ``null``; ``ErrorUso`` (2) si la clave
        no tiene la forma ``grupo.clave``.
        """
        valor = self._entrada(clave)["valor"]
        if valor is None:
            raise ParametroFaltante(clave, "sin valor (null): pendiente de calibrar por el dueño")
        return copy.deepcopy(valor)

    def aplanar(self) -> dict[str, Mapping[str, Any]]:
        """Mapa plano ``"grupo.clave" -> entrada`` (valor, unidad, hipotesis, fuente, rango…), copia profunda."""
        plano: dict[str, Mapping[str, Any]] = {}
        for grupo, claves in (self._datos.get("grupos") or {}).items():
            for nombre, entrada in claves.items():
                plano[f"{grupo}.{nombre}"] = copy.deepcopy(entrada)
        return plano

    def __iter__(self) -> Iterator[str]:
        return iter(self.aplanar())

    def __repr__(self) -> str:
        return f"Parametros(version={self.version}, schema_version={self.schema_version!r}, claves={len(self.aplanar())})"


def cargar_parametros(ruta: Path | str | None = None) -> Parametros:
    """Lee, valida y devuelve ``Parametros`` desde ``ruta`` (por defecto ``<raíz>/empresa/parametros.yaml``).

    Errores: ``ErrorLimite`` (5) si el archivo no existe o es ilegible (sin parámetros no se opera);
    ``ErrorValidacion`` (3) si no cumple el esquema, repite claves de YAML, o trae números de coma
    flotante (los decimales van como cadena).
    """
    destino = Path(ruta) if ruta is not None else ruta_por_defecto()
    try:
        datos = comun.cargar_yaml(destino)
    except FileNotFoundError as exc:
        raise ErrorLimite(f"falta {destino.name}: sin parámetros no se opera") from exc
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
        raise ErrorLimite(f"{destino.name} ilegible: {exc}") from exc
    if not isinstance(datos, dict):
        raise ErrorLimite(f"{destino.name} ilegible: se esperaba un mapa")
    errores = comun.errores_de_esquema("parametros", datos)
    if errores:
        raise ErrorValidacion(f"{destino.name} no cumple parametros.schema.json: {comun.resumir_errores_esquema(errores)}")
    flotantes = buscar_floats(datos)
    if flotantes:
        raise ErrorValidacion(f"{destino.name}: números de coma flotante prohibidos en {', '.join(flotantes[:3])}")
    return Parametros(datos, destino)
