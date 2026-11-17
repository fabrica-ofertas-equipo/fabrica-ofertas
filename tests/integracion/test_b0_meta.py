"""B0-12 (meta.crear idempotente + preflight), B0-13 (meta.activar) y B0-21 (meta.monitor)."""
from __future__ import annotations

import unittest

from scripts.b0 import meta as M


class PruebaB0_12(unittest.TestCase):
    def test_evaluar_b0_12_es_verde(self) -> None:
        r = M.evaluar_b0_12()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaB0_13(unittest.TestCase):
    def test_evaluar_b0_13_es_verde(self) -> None:
        r = M.evaluar_b0_13()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaB0_21(unittest.TestCase):
    def test_evaluar_b0_21_queda_pendiente_pero_el_sub_escenario_es_correcto(self) -> None:
        r = M.evaluar_b0_21()
        self.assertEqual("pendiente", r.estado)
        self.assertIn("congelar=True", r.motivo)
        self.assertIn("engine.estado", r.motivo)


class PruebaNegativaSembrada(unittest.TestCase):
    def test_preflight_detecta_si_un_p_no_se_vuelve_rojo(self) -> None:
        """Siembra el fallo: una mutación de P05 que NO hace rojo el check (simula una regresión de meta.preflight)."""
        mutaciones_rotas = dict(M._MUTACIONES_POR_P)
        mutaciones_rotas["P05"] = {}  # sin mutación real: P05 debería seguir VERDE, no ROJO
        original = M._MUTACIONES_POR_P
        try:
            M._MUTACIONES_POR_P.clear()
            M._MUTACIONES_POR_P.update(mutaciones_rotas)
            ok, motivo = M._escenario_preflight()
        finally:
            M._MUTACIONES_POR_P.clear()
            M._MUTACIONES_POR_P.update(original)
        self.assertFalse(ok)
        self.assertIn("P05", motivo)

    def test_activar_negativo_que_no_rechaza_se_detecta(self) -> None:
        """``_caso_negativo`` con un sello QUE SÍ aprueba (sin firmar_orden) debe seguir rechazando
        por falta de la orden firmada; si en cambio pasara sin error, ``nombre, False, …`` lo marca."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="b0-meta-neg-") as tmp_str:
            tmp = Path(tmp_str)
            hash_ok = "sha256:" + "b0" * 32
            sello_ok = M._sello_activar(hash_config=hash_ok, object_ids={M._CAMPAIGN_ID, M._ADSET_ID, M._AD_ID})
            nombre, ok, motivo = M._caso_negativo(tmp, "control_sin_firma", firmar_orden=False, con_pausa=False,
                                                  sello=sello_ok, hash_activar=hash_ok)
            self.assertTrue(ok, f"se esperaba que SIN firma rechazara (lo hace); si esto fallara, sería la señal de ROJO: {motivo}")


if __name__ == "__main__":
    unittest.main()
