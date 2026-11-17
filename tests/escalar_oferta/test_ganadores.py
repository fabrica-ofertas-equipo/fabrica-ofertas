"""Reparto de iteraciones entre ganadores en la renovación diaria (dueño, 14-nov: muchos winners, más winners que lugares,
pero siempre con fuerza sobre lo que más funciona)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ganadores", RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts" / "ganadores.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

E = 40.0


def ad(i, c, gasto, pagos=0, **kw):
    return {"id": i, "nombre": i, "compras": c, "gasto_usd": gasto, "inicios_pago": pagos, **kw}


class TestGanadores(unittest.TestCase):
    def cuotas(self, r):
        return [x["iteraciones"] for x in r["ramas"]]

    def test_escenarios_del_script(self) -> None:
        g._probar()

    def test_un_ganador_lleva_5_y_el_segundo_2(self) -> None:
        r = g.repartir([ad("A", 8, 120), ad("B", 1, 30), ad("C", 0, 20, 1)], E)
        self.assertEqual(r["escenario"], "un_ganador")
        self.assertEqual(self.cuotas(r), [5, 2])

    def test_una_compra_contra_cero_no_es_ganador(self) -> None:
        r = g.repartir([ad("A", 1, 20), ad("B", 0, 25, 6)], E)
        self.assertEqual(r["escenario"], "solo_promesas")
        self.assertEqual(r["ramas"][0]["clase"], "promete")

    def test_mas_ganadores_que_lugares_el_mejor_al_frente(self) -> None:
        r = g.repartir([ad(f"G{i}", 12 - i, 100) for i in range(9)], E)
        c = self.cuotas(r)
        self.assertEqual(r["escenario"], "mas_ganadores_que_lugares")
        self.assertEqual(len(c), g.MAX_RAMAS)
        self.assertEqual(sum(c), 7)
        self.assertGreaterEqual(c[0], g.MIN_PRIMERO)
        self.assertEqual(c[0], max(c))
        self.assertEqual(len(r["afuera"]), 5)

    def test_ganador_muy_superior_se_lleva_casi_todo(self) -> None:
        r = g.repartir([ad("A", 20, 200), ad("B", 2, 70)], E)
        self.assertGreaterEqual(self.cuotas(r)[0], 5)

    def test_ronda_con_conceptos_nuevos_solo_3_iteraciones(self) -> None:
        r = g.repartir([ad("A", 9, 100), ad("B", 6, 100), ad("C", 4, 100), ad("D", 3, 100)], E, iteraciones=3)
        self.assertEqual(sum(self.cuotas(r)), 3)
        self.assertEqual(self.cuotas(r)[0], max(self.cuotas(r)))

    def test_mismo_anuncio_en_varios_conjuntos_suma(self) -> None:
        r = g.repartir([ad("A", 1, 20, conjunto="R1"), ad("A", 2, 30, conjunto="R2")], E)
        self.assertEqual(r["ramas"][0]["compras"], 3)

    def test_pocas_compras_en_3_dias_mira_desde_el_inicio(self) -> None:
        r = g.repartir([ad("A", 1, 20, compras_inicio=9, gasto_inicio=150), ad("B", 0, 20, compras_inicio=2, gasto_inicio=90)], E)   # B: CPA 45, entre 1 y 1,2 × equilibrio → promete
        self.assertIn("inicio", r["ventana"])
        self.assertEqual(r["escenario"], "un_ganador")


if __name__ == "__main__":
    unittest.main()
