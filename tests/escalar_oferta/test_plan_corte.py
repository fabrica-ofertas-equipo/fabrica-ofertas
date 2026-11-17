"""Plan del corte de respaldo en la nube (plan_corte.armar) · 17-nov."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "escalar-oferta" / "scripts"))
import plan_corte as PC  # noqa: E402

UTC = dt.timezone.utc


def _test(**x):
    t = {"nombre": "Oferta M", "estado": "activo", "inicio": "2026-11-17T00:00:00+03:00", "campana": "c1", "tienda": "zihinatlasi",
         "ficha": {"tiendas": [{"slug": "zihinatlasi", "precio": {"usd": 19.9}}]}, "ventas": [{"tipo": "principal"}, {"tipo": "upsell"}]}
    t.update(x)
    return t


def test_arma_el_test_del_dia_1():
    p = PC.armar({"tests": [_test()]}, dt.datetime(2026, 11, 17, 8, tzinfo=UTC), "2026-11-17T04:40:00+00:00")
    (t,) = p["tests"]
    assert t["ticket_usd"] == 19.9 and t["veces"] == 1.5 and t["ventas_conocidas"] == 1
    assert t["desde"] == "2026-11-16"          # 00:00 Estambul = 18:00 ART del 16 (día de la cuenta)
    assert t["fin"] == "2026-11-17T21:00:00+00:00"
    assert t["campanas"] == [{"id": "c1"}] and t["tiendas"] == ["zihinatlasi"]
    assert p["latido_vigilancia"] == "2026-11-17T04:40:00+00:00"


def test_fuera_del_dia_1_o_sin_precio_no_entra():
    assert PC.armar({"tests": [_test()]}, dt.datetime(2026, 11, 17, 22, tzinfo=UTC), None)["tests"] == []
    assert PC.armar({"tests": [_test(ficha={})]}, dt.datetime(2026, 11, 17, 8, tzinfo=UTC), None)["tests"] == []
    assert PC.armar({"tests": [_test(estado="pausado")]}, dt.datetime(2026, 11, 17, 8, tzinfo=UTC), None)["tests"] == []


def test_limites_genericos_en_cualquier_fase():
    """R9 v2 (17-nov): toda campaña con rol en cortes_por_rol (o corte_tickets propio) va a `limites`, aunque la oferta ya
    pasó el día 1; la madre y las manuales no."""
    f = {"tiendas": [{"slug": "a", "precio": {"usd": 54}}], "campanas": [
        {"id": "c1", "rol": "principal"},
        {"id": "n7", "rol": "nuevos", "inicio": "2026-11-18T00:00:00+01:00"},
        {"id": "pk", "rol": "pocket", "estado": "ACTIVE"},
        {"id": "cc", "rol": "cost_cap"},
        {"id": "x", "rol": "rol_futuro", "corte_tickets": 2.0},
        {"id": "z", "rol": "pocket", "estado": "PAUSED"}]}
    p = PC.armar({"tests": [_test(inicio="2026-11-14T00:00:00+01:00", ficha=f)]}, dt.datetime(2026, 11, 18, 12, tzinfo=UTC), None)
    assert p["tests"] == []
    lim = {l["campana"]: l for l in p["limites"]}
    assert set(lim) == {"n7", "pk", "x"}
    assert lim["n7"]["tickets"] == 1.5 and lim["n7"]["desde"] == "2026-11-17" and lim["pk"]["tickets"] == 1.0 and lim["x"]["tickets"] == 2.0


def test_dia_1_con_corte_por_campana_va_a_limites():
    f = {"tiendas": [{"slug": "a", "precio": {"usd": 54}}], "campanas": [{"id": "p", "rol": "pocket", "corte_tickets": 1.0}, {"id": "v", "rol": "test_variaciones", "corte_tickets": 1.5}]}
    p = PC.armar({"tests": [_test(ficha=f)]}, dt.datetime(2026, 11, 17, 8, tzinfo=UTC), None)
    assert p["tests"] == []
    assert {l["campana"]: l["tickets"] for l in p["limites"]} == {"p": 1.0, "v": 1.5, "c1": 1.5}
