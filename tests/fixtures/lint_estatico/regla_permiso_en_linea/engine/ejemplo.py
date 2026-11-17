"""Fixture para probar el marcador de permiso en línea (mecanismo 1 de falsos positivos)."""


def tasa_en_memoria(gasto_minor: int, dias: int) -> float:
    return gasto_minor / dias  # lint-estatico: permitir=a  # D-05: tasa en memoria, no se persiste
