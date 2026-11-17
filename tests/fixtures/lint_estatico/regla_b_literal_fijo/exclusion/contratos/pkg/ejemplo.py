"""Mismo patrón rojo, pero bajo contratos/: la regla (b) lo excluye por ruta."""


def exigir_umbral(valor: int) -> None:
    if valor > 1500:
        raise ValueError("fuera de umbral")
