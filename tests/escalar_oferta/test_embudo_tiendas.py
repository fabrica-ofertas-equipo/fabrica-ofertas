"""Embudo consolidado de las tiendas de una oferta (dueño, 14-nov: el CR de cada tienda en Impultienda no sirve; se suman)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("embudo_tiendas", SCRIPTS / "embudo_tiendas.py")
et = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(et)

HOY = dt.date(2026, 11, 14)


def libro(estado="activo"):
    return {"zona_horaria_cuenta": "America/Argentina/Buenos_Aires", "tests": [
        {"nombre": "X", "estado": estado, "inicio": "2026-11-14T00:00:00+01:00", "tienda": ["x-a", "x-b", "x-c"],
         "historial_diario": [{"fecha": "2026-11-13", "gasto_usd": 5}, {"fecha": "2026-11-14", "gasto_usd": 50}]}]}


def st(l, c, v):
    return {"visitas": {"landing": l, "checkout": c}, "ventas": {"cantidad": v}}


class TestEmbudo(unittest.TestCase):
    def test_suma_las_tres_tiendas(self) -> None:
        L = libro()
        lect = [{"tienda": "x-a", "fecha": "2026-11-14", "stats": st(360, 6, 2)}, {"tienda": "x-b", "fecha": "2026-11-14", "stats": st(0, 13, 2)},
                {"tienda": "x-c", "fecha": "2026-11-14", "stats": st(1, 13, 6)}]
        et.aplicar(L, lect, "2026-11-14T21:00-03:00", HOY)
        t = L["tests"][0]
        self.assertEqual((t["tienda_embudo"]["landing"], t["tienda_embudo"]["checkout"], t["tienda_embudo"]["compras"]), (361, 32, 10))
        self.assertEqual(t["tienda_embudo"]["por_tienda"]["x-c"]["compras"], 6)
        self.assertTrue(t["tienda_embudo_diario"][0]["parcial"])

    def test_sin_todas_las_tiendas_no_escribe(self) -> None:
        L = libro()
        out = et.aplicar(L, [{"tienda": "x-a", "fecha": "2026-11-14", "stats": st(10, 1, 0)}], "x", HOY)
        self.assertNotIn("tienda_embudo_diario", L["tests"][0])
        self.assertIn("faltan tiendas", out[0])

    def test_pedidos_activa_relee_hoy_y_completa_huecos(self) -> None:
        p = et.pedidos(libro(), HOY, {"x-a": "1", "x-b": "2", "x-c": "3"})
        self.assertEqual(sorted({x["fecha"] for x in p["lecturas"]}), ["2026-11-13", "2026-11-14"])
        self.assertEqual(len(p["lecturas"]), 6)

    def test_pedidos_pausada_solo_dias_con_gasto_y_cerrados(self) -> None:
        L = libro("pausado")
        L["tests"][0]["tienda_embudo_diario"] = [{"fecha": "2026-11-13", "por_tienda": {}, "parcial": False},
                                                {"fecha": "2026-11-14", "por_tienda": {}, "parcial": True}]
        self.assertEqual(et.pedidos(L, HOY, {})["lecturas"], [])
        self.assertEqual({x["fecha"] for x in et.pedidos(L, HOY + dt.timedelta(days=1), {})["lecturas"]}, {"2026-11-14"})


if __name__ == "__main__":
    unittest.main()
