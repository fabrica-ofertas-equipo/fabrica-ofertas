"""Top de creativos por oferta (dueño, 15-nov: «el top 20 de creativos que mejor están performando con todos sus KPIs»).

- nube_sync.aplicar_anuncios: la lectura por anuncio de la nube entra al libro (por día y lista), reemplaza solo los días leídos.
- negocio.creativos_de: junta el mismo anuncio entre conjuntos, ordena del mejor al peor y calcula los KPIs.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts"))

import nube_sync as NS  # noqa: E402
from dashboard import negocio as N  # noqa: E402


def _fila(fecha, i, campana="C1", gasto=10.0, compras=0, pagos=0, imp=1000, clics=20, nombre=None, conjunto="abierto"):
    return {"fecha": fecha, "id": i, "nombre": nombre or f"A{i}", "conjunto_id": "S1", "conjunto": conjunto, "campana": campana, "gasto": gasto,
            "impresiones": imp, "alcance": imp // 2, "clics": clics, "visitas": clics // 2, "pagos_iniciados": pagos, "compras": compras,
            "valor_compras": compras * 19.0, "vistas_3s": imp // 4, "video_p25": imp // 5, "video_p50": imp // 8, "video_p75": imp // 10,
            "video_p100": imp // 20, "thruplay": imp // 12}


def test_aplicar_anuncios_reemplaza_dias_leidos_y_suma_lista():
    libro = {"tests": [
        {"nombre": "Oferta", "campana": "C1", "anuncios": {"lista": [{"id": "9", "nombre": "viejo", "gasto_usd": 5}],
                                                          "por_dia": [{"fecha": "2026-11-10", "id": "1", "gasto_usd": 3.0, "impresiones": 100},
                                                                      {"fecha": "2026-11-14", "id": "1", "gasto_usd": 99.0}]}},
        {"nombre": "Otra", "campana": "C2"},
    ]}
    datos = {"anuncio_dias": ["2026-11-14", "2026-11-15"],
             "anuncio_dia": [_fila("2026-11-14", "1", compras=1, pagos=2), _fila("2026-11-15", "1", gasto=5.0), _fila("2026-11-15", "2", campana="C2")],
             "anuncios": [{"id": "1", "nombre": "A1", "estado": "ACTIVE", "campana": "C1", "conjunto": "R2", "miniatura": "https://x/t.jpg"}]}
    cambios = NS.aplicar_anuncios(libro, datos, "2026-11-15T11:00-03:00")
    a = libro["tests"][0]["anuncios"]
    dias = {(r["fecha"], r["id"]): r for r in a["por_dia"]}
    assert dias[("2026-11-14", "1")]["gasto_usd"] == 10.0          # el día leído se reemplaza
    assert ("2026-11-10", "1") in dias                              # el día no leído queda
    uno = next(x for x in a["lista"] if x["id"] == "1")
    assert uno["gasto_usd"] == 18.0 and uno["compras_meta"] == 1 and uno["estado"] == "ACTIVE" and uno["conjunto"] == "R2"
    assert uno["miniatura_url"] == "https://x/t.jpg"
    assert next(x for x in a["lista"] if x["id"] == "9")["gasto_usd"] == 5   # sin días: conserva lo que tenía
    assert libro["tests"][1]["anuncios"]["lista"][0]["id"] == "2"
    assert cambios


def test_aplicar_anuncios_sin_lectura_no_toca():
    libro = {"tests": [{"nombre": "Oferta", "campana": "C1", "anuncios": {"lista": [{"id": "1"}]}}]}
    assert NS.aplicar_anuncios(libro, {}, "x") == []
    assert libro["tests"][0]["anuncios"] == {"lista": [{"id": "1"}]}


def test_creativos_junta_conjuntos_y_ordena():
    crudos = [
        {"id": "1", "nombre": "A01 gancho", "conjunto": "R1", "estado": "PAUSED", "gasto_usd": 20, "impresiones": 2000, "clics_enlace": 40,
         "inicios_pago_meta": 4, "compras_meta": 1, "valor_compras_meta_usd": 19, "vistas_3s": 600, "video_p25": 400, "video_p100": 50},
        {"id": "2", "nombre": "A01 gancho", "conjunto": "R2", "estado": "ACTIVE", "gasto_usd": 10, "impresiones": 1000, "clics_enlace": 20,
         "inicios_pago_meta": 2, "compras_meta": 1, "valor_compras_meta_usd": 19},
        {"id": "3", "nombre": "A02", "conjunto": "R1", "gasto_usd": 15, "impresiones": 1500, "clics_enlace": 30, "inicios_pago_meta": 6, "compras_meta": 0},
        {"id": "4", "nombre": "A03", "conjunto": "R1", "gasto_usd": 6, "impresiones": 500, "clics_enlace": 5, "compras_meta": 1, "valor_compras_meta_usd": 19},
        {"id": "5", "nombre": "A04 sin salir", "conjunto": "R2", "gasto_usd": 0, "impresiones": 0},
    ]
    c = N.creativos_de(crudos, 15.0, 19.0)
    assert [x["nombre"] for x in c] == ["A01 gancho", "A03", "A02"]   # 2 compras > 1 compra > 0; el que no salió no entra
    top = c[0]
    assert top["puesto"] == 1 and top["compras_meta"] == 2 and top["gasto_usd"] == 30 and top["cpa"] == 15
    assert top["estado"] == "ACTIVE" and top["conjuntos"] == ["R1", "R2"] and top["ids"] == ["1", "2"]
    assert top["hook_pct"] == 20.0 and top["costo_pago"] == 5 and top["pago_compra_pct"] == 33.3 and top["cpm"] == 10
    assert top["veredicto"]["clave"] == "ganador"


def test_top_limita_a_20():
    crudos = [{"id": str(i), "nombre": f"A{i:02d}", "gasto_usd": 5 + i, "impresiones": 100, "clics_enlace": 2} for i in range(25)]
    r = N.anuncios_de_oferta([{"anuncios": {"lista": crudos}}], {}, 15.0, None, 19.0)
    assert len(r["top"]) == 20 and r["n_creativos"] == 25 and len(r["lista"]) == 25
