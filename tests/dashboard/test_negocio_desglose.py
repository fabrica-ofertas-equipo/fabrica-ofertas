"""Pruebas del desglose «De dónde sale la ganancia» (dashboard/negocio.py → desglose), pedido del dueño del 15-nov."""
import unittest

from dashboard import negocio as N


def oferta(id_, gan, gasto, ventas, *, cm=None, neto=0.0, prod=0.0, cpa=None, eq=None, etapa="test", vis=0, chk=0, com=0,
           imp=0, clk=0, aov_veces=None):
    return {"id": id_, "nombre": id_.title(), "mercado": "MX", "etapa": {"clave": etapa, "texto": etapa}, "accion_sugerida": {"clave": "mirar"},
            "ganancia_neta": gan, "ganancia_contra_meta": gan if cm is None else cm, "gasto_meta": gasto, "bruto": neto, "neto": neto,
            "comisiones": 0.0, "costos": {"produccion": prod, "fijos": 0.0}, "ventas_n": ventas, "cpa": cpa, "equilibrio": eq,
            "roas_neto": (neto / gasto) if gasto else None, "kpis": {"aov": None, "aov_veces_principal": aov_veces},
            "embudo": {"visitas": vis, "checkout": chk, "compras": com, "pct_checkout": 100 * chk / vis if vis else None,
                       "pct_compra": 100 * com / chk if chk else None, "pct_compra_visita": 100 * com / vis if vis else None},
            "meta": {"impresiones": imp, "clics_enlace": clk}, "con_datos_periodo": True}


class TestDesglose(unittest.TestCase):
    def setUp(self):
        self.d = {"cartera": {"bruto": 500, "comisiones": 40, "gasto_meta": 400, "produccion": 30, "fijos": 1, "ganancia_neta": 29},
                  "ofertas": [
                      oferta("gana", 120.0, 150.0, 10, neto=270.0, cpa=15.0, eq=27.0, etapa="aprobada", vis=400, chk=40, com=10, imp=10000, clk=600, aov_veces=1.7),
                      oferta("checkout", -60.0, 120.0, 3, neto=60.0, cpa=40.0, eq=20.0, etapa="apagada", vis=300, chk=40, com=3, imp=8000, clk=300),
                      oferta("sinventas", -50.0, 50.0, 0, etapa="apagada", imp=3000, clk=100, vis=90, chk=2),
                      oferta("programada", -6.0, 0.0, 0, cm=0.0, prod=6.0, etapa="programada"),
                      oferta("produccion", -5.0, 80.0, 6, cm=10.0, neto=90.0, prod=15.0, cpa=13.3, eq=15.0, etapa="renovando"),
                  ]}
        self.g = N.desglose(self.d)

    def test_orden_y_resumen(self):
        nombres = [f["id"] for f in self.g["filas"]]
        self.assertEqual(nombres[0], "gana")
        self.assertEqual(nombres[-1], "checkout")
        r = self.g["resumen"]
        self.assertEqual((r["ganan"], r["pierden"]), (1, 4))
        self.assertEqual(r["peor"]["id"], "checkout")

    def test_palancas_del_embudo(self):
        f = {x["id"]: x for x in self.g["filas"]}
        claves = {p["clave"]: p["sentido"] for p in f["checkout"]["palancas"]}
        self.assertEqual(claves.get("compra"), "baja")        # 3 de 40 checkouts = 7,5 % (ref. 25-30)
        self.assertEqual(claves.get("cpa"), "baja")
        self.assertIn("checkout", f["checkout"]["motivo"])
        self.assertEqual({p["clave"]: p["sentido"] for p in f["gana"]["palancas"]}.get("aov"), "sube")
        self.assertTrue(f["sinventas"]["motivo"].startswith("Gastó"))
        self.assertIn("producción", f["produccion"]["motivo"])
        self.assertIn("sin pauta", f["programada"]["motivo"].lower())

    def test_grupos_patrones_y_cascada(self):
        g = {x["clave"]: x for x in self.g["grupos"]}
        self.assertEqual(g["escalando"]["ofertas"], 2)
        self.assertAlmostEqual(g["apagadas"]["ganancia_neta"], -110.0)
        self.assertTrue(all(p["clave"] not in ("cpa", "sin_ventas", "produccion") for p in self.g["patrones"]))
        self.assertEqual([c["clave"] for c in self.g["cascada"]], ["bruto", "comisiones", "meta", "produccion", "fijos", "ganancia"])
        self.assertEqual(self.g["cascada"][2]["usd"], -400)


if __name__ == "__main__":
    unittest.main()
