"""Neto por comprador con ventana móvil para el ROAS neto estimado por anuncio (dashboard/negocio.py, dueño 17-nov):
7 días; con menos de 50 compradores, 14; si tampoco llega, toda la historia. Upsells suman neto, no compradores."""
from __future__ import annotations

import datetime as dt
import unittest

from dashboard import negocio

UTC = dt.timezone.utc
TC = {"USD": 1.0}


def ventas(dia: str, n: int, neto: float, tipo: str | None = None) -> list[dict]:
    return [{"fecha": dia, "moneda": "USD", "neto": neto, "tipo": tipo} for _ in range(n)]


class TestNetoVentana(unittest.TestCase):
    def test_siete_dias_con_50_compradores(self) -> None:
        vs = ventas("2026-11-01", 100, 10.0) + ventas("2026-11-16", 50, 40.0) + ventas("2026-11-16", 10, 20.0, "upsell")
        r = negocio.neto_por_comprador_ventana([{"ventas": vs}], TC, UTC, dt.date(2026, 11, 17))
        self.assertEqual((r["dias"], r["compradores"], r["desde"]), (7, 50, "2026-11-11"))
        self.assertAlmostEqual(r["neto_por_venta"], (50 * 40 + 10 * 20) / 50)

    def test_estira_a_14_y_a_la_historia(self) -> None:
        vs = ventas("2026-11-15", 30, 40.0) + ventas("2026-11-06", 30, 10.0) + ventas("2026-10-01", 5, 10.0)
        r = negocio.neto_por_comprador_ventana([{"ventas": vs}], TC, UTC, dt.date(2026, 11, 17))
        self.assertEqual((r["dias"], r["compradores"]), (14, 60))
        r = negocio.neto_por_comprador_ventana([{"ventas": vs[:40]}], TC, UTC, dt.date(2026, 11, 17))
        self.assertEqual((r["dias"], r["compradores"], r["desde"]), (None, 40, "2026-11-06"))

    def test_usa_las_ventas_sin_recortar_y_no_mira_despues_del_fin(self) -> None:
        t = {"ventas": [], "_ventas_todas": ventas("2026-11-10", 3, 30.0) + ventas("2026-11-20", 3, 90.0)}
        r = negocio.neto_por_comprador_ventana([t], TC, UTC, dt.date(2026, 11, 16))
        self.assertEqual((r["compradores"], r["neto_por_venta"]), (3, 30.0))
        self.assertIsNone(negocio.neto_por_comprador_ventana([{"ventas": ventas("2026-11-10", 2, 5.0, "upsell")}], TC, UTC, dt.date(2026, 11, 16)))


if __name__ == "__main__":
    unittest.main()
