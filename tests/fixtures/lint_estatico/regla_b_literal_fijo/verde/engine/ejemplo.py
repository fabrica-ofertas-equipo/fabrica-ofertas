"""Fixture verde de la regla (b): la función de límite no trae ningún literal fijo de 2+ dígitos."""


def exigir_limite(valor: int, limites: dict) -> None:
    tope = limites["gasto_diario_por_oferta"]
    margen = limites.get("margen_pct", 0)
    if valor > tope + margen:
        raise ValueError("fuera de límite")
