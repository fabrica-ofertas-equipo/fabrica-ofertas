"""Rol de una campaña detectada por su nombre (fotos_campanas.rol_por_nombre).

Caso real (16-nov, DE): «CBO test variaciones V1 (1-1-10)» contiene «1-1-1» y salía pocket.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "escalar-oferta" / "scripts"))
from fotos_campanas import CORTE_REPLICA, rol_por_nombre  # noqa: E402


def test_variaciones_1_1_10_no_es_pocket():
    assert rol_por_nombre("DE | Oferta | CBO test variaciones V1 (1-1-10)", True) == "test_variaciones"
    assert rol_por_nombre("X | y | CBO 1-1-10", True) == "test_variaciones"


def test_pocket():
    assert rol_por_nombre("DE | Oferta | CBO POCKET V1 (1-1-1)", True) == "pocket"
    assert rol_por_nombre("X | y | CBO 1-1-1", True) == "pocket"


def test_principal_y_otra():
    assert rol_por_nombre("ES | Oferta F | CBO test", False) == "principal"
    assert rol_por_nombre("ES | Oferta F | CBO test", True) == "otra"


def test_corte_de_replica():
    assert CORTE_REPLICA == {"pocket": 1.0, "test_variaciones": 1.5}
