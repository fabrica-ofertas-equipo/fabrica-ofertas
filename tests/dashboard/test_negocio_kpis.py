"""KPIs por oferta del tablero Negocio (dashboard/negocio.py → kpis_oferta, 13-nov)."""
from __future__ import annotations

import datetime as dt
import unittest

from dashboard import negocio


class TestKpis(unittest.TestCase):
    def test_aov_margen_toma_y_dia(self) -> None:
        ventas = [{"tipo": "principal"}, {"tipo": "principal"}, {"tipo": "upsell"}, {"tipo": "Bump"}]
        diario = [{"fecha": "2026-11-11", "resultado": 5.0}, {"fecha": "2026-11-12", "resultado": 22.5}, {"fecha": "2026-11-13", "resultado": -3.0}]
        k = negocio.kpis_oferta(bruto=60.0, neto=54.0, gasto=40.0, ganancia=-6.0, nv=2, ventas=ventas, precio_principal=20.0, diario=diario, hoy="2026-11-13")
        self.assertEqual((k["aov"], k["aov_veces_principal"], k["aov_neto"]), (30.0, 1.5, 27.0))
        self.assertEqual((k["margen_neto_pct"], k["margen_contra_meta_pct"], k["comision_pct"]), (-10.0, 23.3, 10.0))
        self.assertEqual((k["take_rate_pct"], k["ventas_extra_n"]), (100.0, 2))
        self.assertEqual((k["ganancia_ultimo_dia"], k["ultimo_dia"]), (22.5, "2026-11-12"), "el día de hoy no está completo")

    def test_sin_ventas(self) -> None:
        k = negocio.kpis_oferta(0.0, 0.0, 10.0, -10.0, 0, [], 19.0, [], "2026-11-13")
        self.assertEqual((k["aov"], k["margen_neto_pct"], k["take_rate_pct"], k["precio_principal"]), (None, None, None, 19.0))



class TestPeriodosCuadran(unittest.TestCase):
    """Dueño, 15-nov: «la ganancia del día marca una cosa en el día y otra al día siguiente». Con «Hoy» se filtraban las ventas
    del día anterior pero no su gasto de Meta, y la ganancia del 14/11 salía como −gasto."""

    def libro(self) -> dict:
        t = {"nombre": "A", "estado": "activo", "inicio": "2026-11-14T00:00:00-03:00", "corte": "2026-11-15T10:00-03:00",
             "meta": {"gasto_usd": 50.0},
             "historial_diario": [{"fecha": "2026-11-14", "gasto_usd": 30.0}, {"fecha": "2026-11-15", "gasto_usd": 20.0}],
             "ventas": [{"fecha": "2026-11-14", "dia_cuenta": "2026-11-14", "moneda": "USD", "bruto": 50.0, "neto": 45.0},
                        {"fecha": "2026-11-15", "dia_cuenta": "2026-11-15", "moneda": "USD", "bruto": 20.0, "neto": 18.0}]}
        p = {"nombre": "B", "estado": "pausado", "inicio": "2026-11-13T00:00:00-03:00", "corte": "2026-11-13T23:00-03:00",
             "meta": {"gasto_usd": 8.0}, "historial_diario": [{"fecha": "2026-11-13", "gasto_usd": 10.0}], "ventas": []}
        return {"tipos_de_cambio": {"USD": 1}, "costos_fijos_compartidos": [{"concepto": "plan", "usd_mes": 30}], "tests": [t, p]}

    def test_ultimo_dia_igual_en_cualquier_periodo(self) -> None:
        ahora = dt.datetime(2026, 11, 15, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-3)))
        L = self.libro()
        vistas = [negocio.calcular_periodo(L, ahora, d, h)["cartera"] for d, h in
                  [(dt.date(2026, 11, 15),) * 2, (dt.date(2026, 11, 14),) * 2, (None, None)]]
        self.assertEqual({(c["ultimo_dia_completo"], c["ganancia_ultimo_dia"]) for c in vistas}, {("2026-11-14", 15.0)})

    def test_dias_suman_el_rango_y_el_inicio(self) -> None:
        ahora = dt.datetime(2026, 11, 15, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-3)))
        L = self.libro()
        dias = [negocio.calcular_periodo(L, ahora, d, d)["cartera"] for d in (dt.date(2026, 11, 13), dt.date(2026, 11, 14), dt.date(2026, 11, 15))]
        rango = negocio.calcular_periodo(L, ahora, dt.date(2026, 11, 13), dt.date(2026, 11, 15))["cartera"]
        todo = negocio.calcular_periodo(L, ahora, None, None)["cartera"]
        self.assertAlmostEqual(sum(c["ganancia_neta"] for c in dias), rango["ganancia_neta"], places=2)
        self.assertAlmostEqual(rango["ganancia_neta"], todo["ganancia_neta"], places=2)
        self.assertEqual(todo["gasto_meta"], 60.0, "el historial (10) manda sobre un total al corte más viejo (8)")


if __name__ == "__main__":
    unittest.main()
