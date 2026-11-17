"""R9 v2 (dueño, 17-nov): CBO aparte — Nuevos todos los días, Iteraciones según resultados, pockets por familia, manuales cada 5."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "escalar-oferta" / "scripts"))
from fotos_campanas import rol_por_nombre  # noqa: E402
from plan_renovacion import codigo_padre, codigo_propio, familias, plan_oferta  # noqa: E402

AHORA = dt.datetime(2026, 11, 17, 15, 0, tzinfo=dt.timezone.utc)   # 12:00 ART, en ventana de ES
PEGA = {"pega": True, "motivo": "validada", "aov": 50.0}


def _ad(i, nombre, campana, conjunto, dias):
    return {"id": i, "nombre": nombre, "campana": campana, "conjunto": conjunto,
            "gasto_usd": sum(d[1] for d in dias), "compras_meta": sum(d[2] for d in dias)}, \
           [{"id": i, "fecha": f, "gasto_usd": g, "compras_meta": c} for f, g, c in dias]


def _test(ads, campanas, renov=None):
    lista, por_dia = [], []
    for a, d in ads:
        lista.append(a)
        por_dia += d
    return {"nombre": "T", "oferta": "T", "mercado": "ES", "estado": "activo", "campana": "M",
            "ficha": {"tiendas": [{"precio": {"usd": 50}}], "campanas": campanas},
            "anuncios": {"lista": lista, "por_dia": por_dia}, "renovaciones": renov or []}


def test_codigos_y_familias():
    assert codigo_propio("VB D4 | B08 en 2:23 | duración") == "D4"
    assert codigo_padre("VB D4 | B08 en 2:23 | duración", "D4") == "B08"
    assert codigo_padre("B08 | El testamento no dice qué hacer | V1", "B08") is None   # V1 es formato
    assert codigo_padre("VB E1 | gancho mito/realidad", "E1", "ES | X | CBO test variaciones B08") == "B08"
    ads = [{"codigo": "B08", "padre": None}, {"codigo": "D4", "padre": "B08"}, {"codigo": "F9", "padre": "D4"}]
    assert familias(ads) == {"B08": "B08", "D4": "B08", "F9": "B08"}
    assert familias(ads, {"F9": "F9"})["F9"] == "F9"


def test_roles_nuevos_iteraciones_manuales():
    assert rol_por_nombre("ES | T | CBO Nuevos R7 (1-1-10) | 3 tickets", True) == "nuevos"
    assert rol_por_nombre("ES | T | CBO Iteraciones R8 B08 (1-1-10) | 3 tickets", True) == "iteraciones"
    assert rol_por_nombre("ES | T | CBO COST CAP 1-1-5", True) == "cost_cap"
    assert rol_por_nombre("ES | T | CBO BID CAP 1-1-5", True) == "bid_cap"
    assert rol_por_nombre("ES | T | CBO POCKET D1 (1-1-1)", True) == "pocket"


def test_nuevos_todos_los_dias_y_pocket_para_ganador():
    ads = [_ad("1", "B08 | x | V1", "M", "ES | Abierto", [("2026-11-16", 40, 4), ("2026-11-17", 20, 1)]),   # ROAS 4,2 → ganador
           _ad("2", "B09 | y | V2", "M", "ES | Abierto", [("2026-11-16", 100, 2)])]                        # 2 compras → no
    p = plan_oferta(_test(ads, []), PEGA, AHORA, {})
    assert p["nuevos"]["toca"] and p["nuevos"]["presupuesto_usd"] == 150
    assert [g["codigo"] for g in p["ganadores"]] == ["B08"]
    pk = p["pockets"]["lista"]
    assert len(pk) == 1 and pk[0]["codigos"] == ["B08"] and pk[0]["presupuesto_usd"] == 100   # máx(2 × 50, 3 × 12)
    assert p["iteraciones"]["toca"] and p["iteraciones"]["sobre"] == ["B08"] and p["iteraciones"]["reparto"] == {"B08": 10}


def test_roas_debe_superar_1_85_neto():
    ads = [_ad("1", "B08 | x", "M", "ES | Abierto", [("2026-11-16", 81.09, 3)])]   # 3 × 50 / 81,09 = 1,85 justo → no
    assert plan_oferta(_test(ads, []), PEGA, AHORA, {})["ganadores"] == []


def test_iteraciones_esperan_lectura_de_la_ronda_anterior():
    camp = [{"id": "V", "rol": "test_variaciones", "nombre": "ES | T | CBO test variaciones B08", "inicio": "2026-11-17T00:00:00+01:00"}]
    ads = [_ad("1", "B08 | x", "M", "ES | Abierto", [("2026-11-16", 40, 4)]),
           _ad("2", "VB D1 | B08 corto", "V", "ES | Abierto", [("2026-11-17", 10, 0)])]
    it = plan_oferta(_test(ads, camp), PEGA, AHORA, {})["iteraciones"]
    assert not it["toca"] and "todavía no se leyó" in it["porque"]


def test_familia_descansa_tras_dos_rondas_sin_rendir():
    camp = [{"id": "V1", "rol": "test_variaciones", "nombre": "ES | T | CBO test variaciones B08", "inicio": "2026-11-13T00:00:00+01:00"},
            {"id": "V2", "rol": "test_variaciones", "nombre": "ES | T | CBO test variaciones 2 B08", "inicio": "2026-11-15T00:00:00+01:00"}]
    ads = [_ad("1", "B08 | x", "M", "ES | Abierto", [("2026-11-16", 20, 2), ("2026-11-17", 20, 2)]),
           _ad("2", "VB D1 | B08 corto", "V1", "ES | Abierto", [("2026-11-13", 90, 0)]),
           _ad("3", "VC E1 | B08 gancho", "V2", "ES | Abierto", [("2026-11-15", 90, 0)])]
    it = plan_oferta(_test(ads, camp), PEGA, AHORA, {})["iteraciones"]
    assert not it["toca"] and it["familias"]["B08"]["sin_rendir_seguidas"] == 2 and it["familias"]["B08"]["descansa_hasta"]


def test_manual_cada_cinco_sostenidos_en_pocket():
    camp = [{"id": f"P{i}", "rol": "pocket", "nombre": f"ES | T | CBO POCKET X{i} (1-1-1)"} for i in range(5)]
    ads = [_ad(str(i), f"X{i} | algo", f"P{i}", "ES | Abierto", [("2026-11-16", 30, 2), ("2026-11-17", 30, 2)]) for i in range(5)]
    m = plan_oferta(_test(ads, camp), PEGA, AHORA, {})["manual"]
    assert m["toca"] and len(m["lista"]) == 1
    assert m["lista"][0]["cost_cap_usd"] == round(1.3 * 300 / 20, 2) and m["lista"][0]["bid_cap_usd"] == 65.0
    camp4, ads4 = camp[:4], ads[:4]
    m4 = plan_oferta(_test(ads4, camp4), PEGA, AHORA, {})["manual"]
    assert not m4["toca"] and m4["faltan"] == 1


def test_madre_pierde_limites_a_los_dos_dias():
    renov = [{"ronda": "R3", "tipo": "madre", "inicio": "2026-11-15T00:40:05+01:00", "estado": "programada", "conjunto_id": "c3"},
             {"ronda": "R5", "inicio": "2026-11-17T00:00:00+01:00", "estado": "programada", "conjunto_id": "c5"}]
    q = plan_oferta(_test([], [], renov), PEGA, AHORA, {})["madre"]["quitar_limites_a"]
    assert [x["ronda"] for x in q] == ["R3"]
