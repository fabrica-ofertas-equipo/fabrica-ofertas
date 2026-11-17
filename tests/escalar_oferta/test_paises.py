"""Mercados con bandera y nombre completo (dueño, 17-nov-2026): «IE (🇮🇪 Irlanda)»."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "escalar-oferta" / "scripts"))
from paises import con_paises, pais_largo  # noqa: E402


def test_pais_largo():
    assert pais_largo("IE") == "IE (🇮🇪 Irlanda)"
    assert pais_largo("MX/BR") == "MX (🇲🇽 México) y BR (🇧🇷 Brasil)"
    assert pais_largo("UK") == "UK (🇬🇧 Reino Unido)"


def test_con_paises_mensajes_reales():
    assert con_paises("Oferta M (TR) apagada") == "Oferta M TR (🇹🇷 Turquía) apagada"
    assert con_paises("Oferta: VB-D4 sigue") == "Oferta (🇬🇧 Reino Unido): VB-D4 sigue"
    assert con_paises("ES | Renovación R5 C01") == "ES (🇪🇸 España) | Renovación R5 C01"


def test_no_toca_lo_que_no_es_mercado():
    t = "NO se reemplaza; CR consolidado; US$ 57,08; R16, B08, VB-D4, CBO"
    assert con_paises(t) == t


def test_idempotente():
    una = con_paises("IE y NZ")
    assert con_paises(una) == una == "IE (🇮🇪 Irlanda) y NZ (🇳🇿 Nueva Zelanda)"
