"""Fixture rojo de la regla (b): literal fijo de 2+ dígitos dentro de una función de límite."""


def exigir_umbral(valor: int) -> None:
    if valor > 1500:
        raise ValueError("fuera de umbral")
