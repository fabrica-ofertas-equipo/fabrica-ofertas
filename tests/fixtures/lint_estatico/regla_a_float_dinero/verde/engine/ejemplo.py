"""Fixture verde de la regla (a): dinero en enteros, sin float ni división sobre importes."""
from decimal import ROUND_HALF_EVEN, Decimal


def calcular_mc(precio_minor: int, costo_minor: int) -> int:
    return precio_minor - costo_minor


def repartir_bp(total_minor: int, bp: int) -> int:
    return int((Decimal(total_minor) * Decimal(bp) / Decimal(10000)).to_integral_value(rounding=ROUND_HALF_EVEN))


def contar_items(items: list[str]) -> float:
    return float(len(items))
