"""Pruebas de las métricas del embudo (escalar-oferta/scripts/metricas_embudo.py, 13-nov)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "escalar-oferta" / "scripts"))
import metricas_embudo as M  # noqa: E402

BASE = {"fase": "post", "url": "https://x.impultienda.ar/", "gasto_usd": 30, "impresiones": 4000, "clics_enlace": 100,
        "vistas_pagina": 80, "checkouts": 8, "compras": 2, "ingreso_usd": 50, "cpm_dias": [7, 7, 7, 7, 7]}


class TestVuelta(unittest.TestCase):
    def test_tasas_y_por_visita(self) -> None:
        r = M.evaluar_vuelta("X", BASE, None)
        self.assertEqual((r["carga_pct"], r["costo_por_visita"], r["ingreso_por_visita"]), (80.0, 0.38, 0.62))
        self.assertEqual((r["pagina_a_pago_pct"], r["pago_a_compra_pct"]), (10.0, 25.0))
        self.assertEqual(r["acciones"], [])

    def test_carga_baja_pagina_lenta_o_pixel(self) -> None:
        t = {**BASE, "vistas_pagina": 40, "fase": "test"}
        lenta = M.evaluar_vuelta("X", t, lambda u: {"ok": True, "ms": 5200})["acciones"][0]
        self.assertEqual((lenta["accion"], lenta["urgente"], lenta.get("test_contaminado")), ("AVISO_CARGA", True, True))
        pixel = M.evaluar_vuelta("X", t, lambda u: {"ok": True, "ms": 900})["acciones"][0]
        self.assertFalse(pixel["urgente"], "si la página carga bien, el problema es el píxel: aviso normal")
        self.assertIn("PageView", pixel["mensaje"])
        self.assertEqual(M.evaluar_vuelta("X", {**t, "clics_enlace": 40, "vistas_pagina": 10}, None)["acciones"], [], "con menos de 50 clics no avisa")

    def test_cpm_anormal_dos_dias(self) -> None:
        self.assertEqual(M.cpm_anormal([15, 16, 7, 7, 7])["estado"], "ANORMAL")
        self.assertEqual(M.cpm_anormal([15, 8, 7, 7, 7])["estado"], "OK", "un solo día alto no alcanza")
        self.assertEqual(M.cpm_anormal([15, 16, 7])["estado"], "POCA_MUESTRA")
        r = M.evaluar_vuelta("X", {**BASE, "cpm_dias": [15, 16, 7, 7, 7]}, None)
        self.assertEqual([a["accion"] for a in r["acciones"]], ["AVISO_CPM"])


class TestPeriodos(unittest.TestCase):
    def per(self, **k):
        a = {"gasto_usd": 100, "visitas": 200, "ingreso_usd": 200, "checkouts": 30, "compras": 9}
        return {"actual": {**a, **k}, "anterior": dict(a)}

    def test_lado_del_problema(self) -> None:
        self.assertEqual(M.evaluar_periodos("X", self.per())["lado"], "estable")
        self.assertEqual(M.evaluar_periodos("X", self.per(gasto_usd=130))["lado"], "anuncios")
        self.assertEqual(M.evaluar_periodos("X", self.per(ingreso_usd=150))["lado"], "pagina_y_cobro")
        self.assertEqual(M.evaluar_periodos("X", self.per(gasto_usd=130, ingreso_usd=150))["lado"], "ambos")
        self.assertEqual(M.evaluar_periodos("X", self.per(visitas=50))["lado"], "poca_muestra")

    def test_sospecha_de_clon_con_muestra(self) -> None:
        r = M.evaluar_periodos("X", self.per(compras=4))
        self.assertEqual((r["clon"], r["acciones"][0]["accion"]), ("sospecha", "SOSPECHA_CLON"))
        self.assertEqual(M.evaluar_periodos("X", self.per(compras=6))["clon"], "ok")
        self.assertEqual(M.evaluar_periodos("X", self.per(checkouts=10, compras=1))["clon"], "poca_muestra")


class TestAnuncios(unittest.TestCase):
    def test_diagnostico(self) -> None:
        d = M.diagnosticar_anuncio
        self.assertEqual(d({"impresiones": 500})["accion"], "POCA_MUESTRA")
        self.assertEqual(d({"impresiones": 2000, "clics_enlace": 40, "reproducciones": 1500, "completas": 30})["accion"], "NO_TOCAR")
        self.assertEqual(d({"impresiones": 2000, "clics_enlace": 10, "reproducciones": 1500, "completas": 90})["accion"], "REHACER_CUERPO")
        self.assertEqual(d({"impresiones": 2000, "clics_enlace": 10, "reproducciones": 1500, "completas": 200})["accion"], "REHACER_CTA")
        self.assertEqual(d({"impresiones": 2000, "clics_enlace": 10})["accion"], "REHACER_IMAGEN")
        r = M.evaluar_anuncios({"oferta": "X", "anuncios": [{"impresiones": 500}, {"impresiones": 2000, "clics_enlace": 40}]})
        self.assertEqual(r["resumen"], {"POCA_MUESTRA": 1, "NO_TOCAR": 1})


if __name__ == "__main__":
    unittest.main()
