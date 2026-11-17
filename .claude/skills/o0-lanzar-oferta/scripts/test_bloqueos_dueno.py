"""Pruebas de `bloqueos_dueno.py` (solo lectura; trabaja en memoria y con `ofertas/_ejemplo`).

Correr (desde la raíz): .venv/bin/python .claude/skills/o0-lanzar-oferta/scripts/test_bloqueos_dueno.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bloqueos_dueno as bd  # noqa: E402

ve = bd.ve
MERCADO = ve.cargar_json(bd.RAIZ_CODIGO / "ofertas" / "_ejemplo" / "mercado.json")


def estados(items) -> dict[str, str]:
    return {i["id"]: i["estado"] for i in items}


class PruebasBloqueos(unittest.TestCase):
    def test_limites_reales_en_null_abren_cuatro_bloqueos(self):
        lim = ve.cargar_yaml(bd.RAIZ_CODIGO / "empresa" / "limites.yaml")
        e = estados(bd.calcular(lim, None, None))
        self.assertEqual({k: e[k] for k in ("limites", "primer_mercado", "cuenta_meta", "lineas_rojas")}, dict.fromkeys(("limites", "primer_mercado", "cuenta_meta", "lineas_rojas"), "abierta"))
        self.assertEqual(e["metodos_pago"], "diferida")

    def test_sin_archivo_de_limites_falla_cerrado(self):
        self.assertEqual(estados(bd.calcular(None, None, None))["limites"], "abierta")

    def test_limites_de_prueba_resuelven_limites_mercado_y_cuenta_pero_no_lineas_rojas(self):
        e = estados(bd.calcular(ve.limites_de_prueba(), None, None, entorno="prueba"))
        self.assertEqual((e["limites"], e["primer_mercado"], e["cuenta_meta"], e["lineas_rojas"]), ("resuelta", "resuelta", "resuelta", "abierta"))

    def test_lineas_rojas_cargadas_resuelven(self):
        lim = ve.limites_de_prueba()
        lim["lineas_rojas"] = [{"id": "lp-01", "tipo": "promesa", "descripcion": "Promesas de curas o tratamientos"}]
        self.assertEqual(estados(bd.calcular(lim, None, None, entorno="prueba"))["lineas_rojas"], "resuelta")

    def test_pago_por_oferta_sin_firma_fiscal_es_abierta(self):
        m = copy.deepcopy(MERCADO)
        m["fiscal"]["exposicion_aceptada"] = None
        self.assertEqual(estados(bd.calcular(None, m, "OF-202611-01"))["metodos_pago"], "abierta")

    def test_pago_con_firma_pero_metodos_locales_diferidos_es_diferida(self):
        self.assertEqual(estados(bd.calcular(None, MERCADO, "OF-202611-01"))["metodos_pago"], "diferida")

    def test_oferta_sin_mercado_json_no_es_verificable(self):
        self.assertEqual(estados(bd.calcular(None, None, "OF-202611-01"))["metodos_pago"], "no_verificable")

    def test_cada_bloqueo_dice_que_bloquea_y_como_se_cierra(self):
        for i in bd.calcular(None, None, None):
            self.assertTrue(i["bloquea"] and i["como_se_cierra"] and i["evidencia"], i["id"])

    def test_estricto_sale_5_con_bloqueos_y_main_no_escribe(self):
        antes = (bd.RAIZ_CODIGO / "empresa" / "limites.yaml").read_bytes()
        self.assertEqual(bd.main(["--estricto", "--json"]), 5)
        self.assertEqual(bd.main(["--json"]), 0)
        self.assertEqual(antes, (bd.RAIZ_CODIGO / "empresa" / "limites.yaml").read_bytes())


if __name__ == "__main__":
    unittest.main()
