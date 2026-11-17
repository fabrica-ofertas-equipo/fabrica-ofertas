"""B0-10 (fulfill real + outbox), B0-20 (disputa rechaza reembolso + evidencia + 2 disputas) y la
mitad de B0-19 (postcompra.metricas.calcular_senal, reembolsos)."""
from __future__ import annotations

import unittest

from scripts.b0 import postcompra as P


class PruebaB0_10(unittest.TestCase):
    def test_evaluar_b0_10_es_verde(self) -> None:
        r = P.evaluar_b0_10()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaB0_20(unittest.TestCase):
    def test_evaluar_b0_20_es_verde(self) -> None:
        r = P.evaluar_b0_20()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaB0_19Mitad(unittest.TestCase):
    def test_evaluar_b0_19_queda_pendiente_pero_el_sub_escenario_es_correcto(self) -> None:
        r = P.evaluar_b0_19()
        self.assertEqual("pendiente", r.estado)
        self.assertIn("rojo/reembolsos/pausar", r.motivo)
        self.assertIn("engine.d8", r.motivo)


class PruebaNegativaSembrada(unittest.TestCase):
    def test_interpretar_fulfill_detecta_reenvio(self) -> None:
        ok, motivo = P._interpretar_fulfill({
            "primero_codigo": "entregado", "primero_enlace": {"vence_en": "2026-01-01T00:00:00Z", "max_descargas": 3},
            "segundo_codigo": "entregado",  # debería ser "duplicado": reenvío indebido
            "llamadas_correo": 2, "llamadas_api": 2,
            "enlace_valido_dentro_de_cuota": True, "enlace_null_con_cuota_agotada": True, "enlace_null_si_vencido": True,
        })
        self.assertFalse(ok)
        self.assertIn("duplicado", motivo)

    def test_dos_disputas_sin_cruzar_el_umbral_se_detecta(self) -> None:
        """Siembra el fallo: un umbral tan alto que ni dos disputas sobre 60 pagos lo cruzan."""
        from engine.limites import Limites
        from engine.parametros import Parametros
        from postcompra.metricas import calcular_senal

        lim = Limites(datos={"ratio_disputas_pausa": "0.50", "moneda_limites": "EUR"}, entorno="prueba")  # irrealmente alto
        par = Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {"salud_operativa": {
            "disputas_muestra_min_pagos": {"valor": 20}, "disputas_alerta_pct": {"valor": "1.0"},
            "disputas_casos_alerta": {"valor": 1}, "disputas_casos_pausa": {"valor": 2},
            "reembolsos_n_min": {"valor": 20}, "reembolsos_alerta_pct": {"valor": "8.0"}, "reembolsos_pausa_pct": {"valor": "12.0"},
        }}})
        senal = calcular_senal(pagos_ventana=60, casos_disputa_efw=2, reembolsos_num=0, reembolsos_den=60, lim=lim, par=par)
        self.assertNotEqual("rojo", senal.nivel)  # confirma que, con ese umbral roto, SÍ se habría detectado el problema


if __name__ == "__main__":
    unittest.main()
