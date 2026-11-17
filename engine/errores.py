"""Errores tipados de la fábrica y su código de salida (docs/convenciones-de-codigo.md, sección 8).

Toda falla esperada del sistema es una subclase de :class:`ErrorFabrica` con un atributo
``codigo_salida`` fijo. Las CLI traducen la excepción a ese código; un error que NO es
``ErrorFabrica`` sale con 1 (error interno inesperado) y su traza va a stderr sin secretos.

Códigos: 0 correcto · 1 interno · 2 uso · 3 validación · 4 bloqueado · 5 límite · 6 externo.

Este módulo no importa nada del proyecto (núcleo sin ciclos, docs/06 §4.1).
"""
from __future__ import annotations

from typing import Any, Mapping

SALIDA_OK = 0
SALIDA_INTERNO = 1
SALIDA_USO = 2
SALIDA_VALIDACION = 3
SALIDA_BLOQUEADO = 4
SALIDA_LIMITE = 5
SALIDA_EXTERNO = 6


class ErrorFabrica(Exception):
    """Base de todo error esperado. ``codigo_salida`` es el código de salida de la CLI.

    Entradas: ``mensaje`` legible (español, sin secretos ni datos personales) y ``detalle``
    opcional con datos estructurados (por ejemplo la lista de claves de límites que faltan).
    """

    codigo_salida: int = SALIDA_INTERNO

    def __init__(self, mensaje: str, *, detalle: Mapping[str, Any] | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle: dict[str, Any] = dict(detalle) if detalle else {}


class ErrorUso(ErrorFabrica):
    """Uso incorrecto: argumento inválido o variable de entorno ausente (código 2)."""

    codigo_salida = SALIDA_USO


class ErrorValidacion(ErrorFabrica):
    """Esquema, ID, moneda o dato inconsistente (código 3)."""

    codigo_salida = SALIDA_VALIDACION


class ErrorBloqueado(ErrorFabrica):
    """Bloqueado por ``empresa/PAUSA``, por entorno o por infraestructura no verde (código 4)."""

    codigo_salida = SALIDA_BLOQUEADO


class ErrorLimite(ErrorFabrica):
    """Límite excedido o dato de límites/parámetros faltante: no se gasta ni se activa (código 5)."""

    codigo_salida = SALIDA_LIMITE


class ErrorExterno(ErrorFabrica):
    """Falla de un servicio externo, red o tiempo de espera agotado (código 6)."""

    codigo_salida = SALIDA_EXTERNO


class ParametroFaltante(ErrorLimite):
    """Falta un parámetro (``grupo.clave``) o está sin valor: la operación que lo necesita no corre (código 5)."""

    def __init__(self, clave: str, motivo: str = "ausente") -> None:
        super().__init__(f"parámetro {clave}: {motivo}", detalle={"clave": clave, "motivo": motivo})
        self.clave = clave


def codigo_de_excepcion(exc: BaseException) -> int:
    """Código de salida que corresponde a una excepción: el de ``ErrorFabrica`` o 1 si es inesperada."""
    return exc.codigo_salida if isinstance(exc, ErrorFabrica) else SALIDA_INTERNO
