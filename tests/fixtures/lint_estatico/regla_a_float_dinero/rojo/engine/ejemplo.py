"""Fixture rojo de la regla (a): float() y división aplicados a un importe aparente."""


def calcular_mc(precio_minor: int, costo_minor: int) -> float:
    monto_total: float = precio_minor - costo_minor
    return float(monto_total)


def promedio_por_dia(gasto_minor: int, dias: int) -> float:
    return gasto_minor / dias
