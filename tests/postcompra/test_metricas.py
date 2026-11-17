"""Pruebas de :mod:`postcompra.metricas`: cálculo y escritura de ``senal_pausa.json`` (B0-19, B0-20)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine import limites, parametros
from postcompra.metricas import calcular_senal, escribir_senal_pausa
from tests.postcompra.apoyo import PruebaBase, crear_empresa

OFERTA = "OF-202611-01"
AHORA = datetime(2026, 11, 12, 9, 0, 0, tzinfo=timezone.utc)


class PruebaCalcularSenal(PruebaBase):
    def _limites_y_parametros(self):
        emp = crear_empresa(self.tmp, entorno="desarrollo")
        lim = limites.cargar_limites(self.tmp / "empresa" / "limites.yaml", env=emp.env, entorno="desarrollo")
        par = parametros.cargar_parametros(self.tmp / "empresa" / "parametros.yaml")
        return emp, lim, par

    def test_verde_sin_casos(self) -> None:
        _emp, lim, par = self._limites_y_parametros()
        senal = calcular_senal(pagos_ventana=2, casos_disputa_efw=0, reembolsos_num=1, reembolsos_den=2, lim=lim, par=par)
        self.assertEqual(senal.nivel, "verde")
        self.assertEqual(senal.motivo, "ninguno")
        self.assertFalse(senal.emitida)
        self.assertEqual(senal.accion_solicitada, "ninguna")

    def test_muestra_insuficiente_dos_disputas_alerta_amarillo(self) -> None:
        """Con pocos pagos (< disputas_muestra_min_pagos=50), 2 disputas => amarillo (disputas_casos_alerta=2)."""
        _emp, lim, par = self._limites_y_parametros()
        senal = calcular_senal(pagos_ventana=10, casos_disputa_efw=2, reembolsos_num=0, reembolsos_den=0, lim=lim, par=par)
        self.assertEqual(senal.nivel, "amarillo")
        self.assertEqual(senal.motivo, "disputas")
        self.assertFalse(senal.muestra_suficiente)
        self.assertEqual(senal.accion_solicitada, "alertar")

    def test_muestra_insuficiente_tres_disputas_pausa_rojo(self) -> None:
        """Con pocos pagos, 3 disputas => rojo (disputas_casos_pausa=3), aunque el % no dispare solo."""
        _emp, lim, par = self._limites_y_parametros()
        senal = calcular_senal(pagos_ventana=10, casos_disputa_efw=3, reembolsos_num=0, reembolsos_den=0, lim=lim, par=par)
        self.assertEqual(senal.nivel, "rojo")
        self.assertEqual(senal.motivo, "disputas")
        self.assertEqual(senal.accion_solicitada, "pausar")

    def test_muestra_suficiente_dos_disputas_sobre_ratio_disputas_pausa_es_rojo(self) -> None:
        """B0-20: con muestra suficiente, 2 disputas sobre pocos pagos ya exceden ratio_disputas_pausa (0.006)."""
        _emp, lim, par = self._limites_y_parametros()
        # disputas_muestra_min_pagos=50; con 60 pagos la muestra ya es suficiente. 2/60 = 0.0333 >> 0.006.
        senal = calcular_senal(pagos_ventana=60, casos_disputa_efw=2, reembolsos_num=0, reembolsos_den=0, lim=lim, par=par)
        self.assertTrue(senal.muestra_suficiente)
        self.assertEqual(senal.nivel, "rojo")
        self.assertEqual(senal.motivo, "disputas")

    def test_reembolsos_bajo_el_minimo_de_muestra_no_dispara(self) -> None:
        """reembolsos_n_min=20: con 5 pedidos y 5 reembolsos (100%) no hay disparo (sin conteo de respaldo)."""
        _emp, lim, par = self._limites_y_parametros()
        senal = calcular_senal(pagos_ventana=0, casos_disputa_efw=0, reembolsos_num=5, reembolsos_den=5, lim=lim, par=par)
        self.assertEqual(senal.nivel, "verde")
        self.assertEqual(senal.motivo, "ninguno")

    def test_reembolsos_sobre_el_pct_de_pausa_con_muestra_suficiente_es_rojo(self) -> None:
        """reembolsos_pausa_pct=12, reembolsos_n_min=20: 5/20 = 25% >= 12% => rojo."""
        _emp, lim, par = self._limites_y_parametros()
        senal = calcular_senal(pagos_ventana=0, casos_disputa_efw=0, reembolsos_num=5, reembolsos_den=20, lim=lim, par=par)
        self.assertEqual(senal.nivel, "rojo")
        self.assertEqual(senal.motivo, "reembolsos")
        self.assertEqual(senal.accion_solicitada, "pausar")

    def test_reembolsos_sobre_el_pct_de_alerta_pero_bajo_pausa_es_amarillo(self) -> None:
        """reembolsos_alerta_pct=8, reembolsos_pausa_pct=12: 2/20 = 10% está entre los dos => amarillo."""
        _emp, lim, par = self._limites_y_parametros()
        senal = calcular_senal(pagos_ventana=0, casos_disputa_efw=0, reembolsos_num=2, reembolsos_den=20, lim=lim, par=par)
        self.assertEqual(senal.nivel, "amarillo")
        self.assertEqual(senal.motivo, "reembolsos")


class PruebaEscribirSenalPausa(PruebaBase):
    def test_escribe_un_senal_pausa_valido_contra_el_esquema(self) -> None:
        emp = crear_empresa(self.tmp, entorno="desarrollo")
        lim = limites.cargar_limites(self.tmp / "empresa" / "limites.yaml", env=emp.env, entorno="desarrollo")
        par = parametros.cargar_parametros(self.tmp / "empresa" / "parametros.yaml")
        senal = calcular_senal(pagos_ventana=60, casos_disputa_efw=2, reembolsos_num=0, reembolsos_den=0, lim=lim, par=par)
        datos = escribir_senal_pausa(raiz=self.tmp, oferta_id=OFERTA, senal=senal, pagos_ventana=60, casos_disputa_efw=2,
                                     lim=lim, par=par, ahora=lambda: AHORA)
        self.assertEqual(datos["nivel"], "rojo")
        self.assertEqual(datos["motivo"], "disputas")
        self.assertIsNone(datos["consumida_por"])
        ruta = self.tmp / "ofertas" / OFERTA / "10-postcompra" / "senal_pausa.json"
        self.assertTrue(ruta.exists())


if __name__ == "__main__":
    unittest.main()
