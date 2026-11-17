"""Conversión de importes a la unidad que espera la Marketing API de Meta.

Meta NO usa los decimales ISO 4217 para expresar dinero: usa su propio *offset* por moneda
(convenciones de código §3). El offset es 1 para CLP, COP, CRC, HUF, ISK, IDR, JPY, KRW, PYG,
TWD y VND, y 100 para el resto
(https://developers.facebook.com/docs/marketing-api/currencies, leída 2026-11-06). La lista de
monedas de offset 1 vive en :mod:`scripts.validar_esquemas` (``MONEDAS_META_OFFSET_1``): no se
duplica aquí.

Toda llamada de presupuesto a Meta (``spend_cap``, ``daily_budget``, ``lifetime_budget``) pasa el
importe (entero en la unidad menor ISO 4217 de la moneda) por :func:`a_unidad_meta` antes de
mandarlo. La conversión es exacta: si el resultado no es un entero, es un dato incoherente (una
moneda con un exponente ISO distinto del que Meta espera) y se rechaza en vez de redondear en
silencio (``ErrorValidacion``, fail-closed).

``AdAccount.spend_cap`` tiene una rareza propia (convenciones §3): se **lee** en unidad menor y se
**escribe** en unidad estándar; como los scripts de este paquete solo leen ese campo (nunca lo
escriben: quien sube el ``spend_cap`` de la cuenta es el dueño a mano, D-16), no hace falta una
función de escritura aquí.
"""
from __future__ import annotations

from fractions import Fraction

from engine.errores import ErrorValidacion
from scripts.validar_esquemas import EXPONENTE_ISO4217, MONEDAS_META_OFFSET_1

__all__ = ["MONEDAS_META_OFFSET_1", "OFFSET_ESTANDAR", "a_unidad_meta", "offset_meta"]

OFFSET_ESTANDAR = 100  # offset de Meta para toda moneda que no está en MONEDAS_META_OFFSET_1


def offset_meta(moneda: str) -> int:
    """Offset de Meta para ``moneda``: 1 si está en :data:`MONEDAS_META_OFFSET_1`, 100 si no.

    No valida que ``moneda`` sea un código ISO 4217 conocido; eso lo hace :func:`a_unidad_meta`
    (que además necesita el exponente ISO para la conversión).
    """
    if not isinstance(moneda, str):
        raise ErrorValidacion("offset_meta exige un código de moneda (texto)")
    return 1 if moneda in MONEDAS_META_OFFSET_1 else OFFSET_ESTANDAR


def a_unidad_meta(monto_minor: int, moneda: str) -> int:
    """Convierte ``monto_minor`` (entero, unidad menor ISO 4217 de ``moneda``) a la unidad de Meta.

    Fórmula: ``monto_minor * offset_meta(moneda) / 10**exponente_iso(moneda)``, exacta con
    :class:`fractions.Fraction` (nunca ``float``, convenciones §3). Para la mayoría de las monedas
    (offset 100 y exponente ISO 2, o offset 1 y exponente ISO 0) el resultado es ``monto_minor``
    sin cambios; para las que divergen (p. ej. CRC: offset 1, exponente ISO 2) escala de verdad.

    Errores: ``ErrorValidacion`` si ``moneda`` no tiene exponente ISO 4217 registrado, si
    ``monto_minor`` no es un entero, o si el resultado no es exacto (dato incoherente: no se
    redondea en silencio un importe que se va a gastar).
    """
    if isinstance(monto_minor, bool) or not isinstance(monto_minor, int):
        raise ErrorValidacion("a_unidad_meta exige un entero en la unidad menor de la moneda")
    if moneda not in EXPONENTE_ISO4217:
        raise ErrorValidacion(f"a_unidad_meta: moneda sin exponente ISO 4217 registrado: {moneda!r}")
    exponente = EXPONENTE_ISO4217[moneda]
    fraccion = Fraction(monto_minor) * Fraction(offset_meta(moneda)) / Fraction(10) ** exponente
    if fraccion.denominator != 1:
        raise ErrorValidacion(
            f"a_unidad_meta: {monto_minor} en {moneda} no convierte a un entero exacto en la unidad de Meta "
            f"(offset {offset_meta(moneda)}, exponente ISO {exponente}); dato incoherente"
        )
    return fraccion.numerator
