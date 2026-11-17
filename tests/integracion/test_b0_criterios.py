"""Los 25 criterios de aceptación del hito B0 (docs/06 §6.2), uno por nombre: ``test_b0_01``…``test_b0_25``.

Ola 2 (I1b): `scripts.b0_e2e.ejecutar()` corre una sola vez (``setUpClass``, es una corrida real
sobre una raíz temporal: copia ``ofertas/_ejemplo``, construye fixtures con ``tests/engine/apoyo``
y llama a los módulos reales de cada componente, incluidos los de ``scripts/b0/``) y cada prueba
lee SU resultado.

Los criterios que ya quedan VERDE (núcleo de ``engine``/``scripts.validar_esquemas`` de la ola 0a,
los nueve de I1b: ``agentes``, ``tracking``, ``postcompra`` B0-10/20, ``landing``, ``meta`` B0-12/13,
``infra`` watchdog, ``datos`` B0-15, y los ocho de I1a sobre ``engine.estado``/``orq``/``d8``/``cerrar``
reales en ``scripts/b0/motor.py``: B0-05, 06, 07, 16, 19, 22, 23, 25) son pruebas normales: deben
pasar. Los que dependen de otro componente aún no cerrado (``dashboard`` para B0-17, ``meta.monitor``
sin quien aplique «congelar» para B0-21, captura real de B0-24) son ``@unittest.expectedFailure`` con
el motivo «pendiente: …»: documentan su estado sin romper ``scripts/test_all.sh``; cuando el
constructor correspondiente los implemente, ``scripts.b0_e2e`` los pondrá en verde y ``unittest``
avisará «unexpected success» para que alguien quite el decorador.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import b0_e2e


class PruebaB0Criterios(unittest.TestCase):
    """Un método por criterio B0-01…B0-25; ``_resultados`` es la ÚNICA corrida del escenario."""

    _resultados: dict[str, b0_e2e.Criterio] | None = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._resultados = b0_e2e.ejecutar()

    def _criterio(self, id_: str) -> b0_e2e.Criterio:
        assert self._resultados is not None
        return self._resultados[id_]

    def _afirmar_verde(self, id_: str) -> None:
        c = self._criterio(id_)
        self.assertEqual("verde", c.estado, f"{id_}: {c.motivo}")

    def _afirmar_pendiente(self, id_: str) -> None:
        # Si esto empieza a pasar (el criterio ya no da AssertionError), unittest lo marca como
        # «unexpected success»: es la señal de que hay que quitar el @expectedFailure de arriba.
        c = self._criterio(id_)
        self.assertEqual("verde", c.estado, c.motivo)

    # -- Demostrables hoy con el núcleo real de engine y scripts.validar_esquemas -------------------

    def test_b0_01_sin_socket_en_el_escenario(self) -> None:
        self._afirmar_verde("B0-01")

    def test_b0_02_validar_esquemas_y_factibilidad(self) -> None:
        self._afirmar_verde("B0-02")

    def test_b0_03_guard_7_pasos_negativos_y_positivo(self) -> None:
        self._afirmar_verde("B0-03")

    def test_b0_04_empresa_real_intacta(self) -> None:
        self._afirmar_verde("B0-04")

    def test_b0_18_registro_sano_y_costos(self) -> None:
        self._afirmar_verde("B0-18")

    # -- Convertidos a verde en la ola 2 (I1b): el componente real cubre toda la cláusula -----------

    def test_b0_08_runner_y_sonda_hooks(self) -> None:
        self._afirmar_verde("B0-08")

    def test_b0_09_tracking_sesion_webhook_capi(self) -> None:
        self._afirmar_verde("B0-09")

    def test_b0_10_entrega_y_outbox(self) -> None:
        self._afirmar_verde("B0-10")

    def test_b0_11_landing_validar_y_mutaciones(self) -> None:
        self._afirmar_verde("B0-11")

    def test_b0_12_meta_crear_idempotente_y_preflight(self) -> None:
        self._afirmar_verde("B0-12")

    def test_b0_13_meta_activar_negativos_y_positivo(self) -> None:
        self._afirmar_verde("B0-13")

    def test_b0_14_latido_y_watchdog(self) -> None:
        self._afirmar_verde("B0-14")

    def test_b0_15_etl_14_dias_idempotente(self) -> None:
        self._afirmar_verde("B0-15")

    def test_b0_20_disputa_abierta_bloquea_reembolso(self) -> None:
        self._afirmar_verde("B0-20")

    # -- Convertidos a verde en la ola 2 (I1a): engine.estado/orq/d8/cerrar reales (scripts/b0/motor.py) --

    def test_b0_05_gates_h_firmados_y_escalado(self) -> None:
        self._afirmar_verde("B0-05")

    def test_b0_06_etapa_repetida_reutilizada(self) -> None:
        self._afirmar_verde("B0-06")

    def test_b0_07_obsolescencia_y_pausa(self) -> None:
        self._afirmar_verde("B0-07")

    def test_b0_16_tres_escenarios_de_desenlace(self) -> None:
        self._afirmar_verde("B0-16")

    def test_b0_19_senal_pausa_por_reembolsos(self) -> None:
        self._afirmar_verde("B0-19")

    def test_b0_22_cierre_sin_gasto_y_espera_madurez(self) -> None:
        self._afirmar_verde("B0-22")

    def test_b0_23_orq_ingresar_equivale_a_ejecutar_fixture(self) -> None:
        self._afirmar_verde("B0-23")

    def test_b0_25_orden_firmada_por_api(self) -> None:
        self._afirmar_verde("B0-25")

    # -- Pendientes: el módulo real que falta esta noche (ver scripts/b0_e2e._MOTIVOS_PENDIENTES) ---

    @unittest.expectedFailure
    def test_b0_17_dashboard_escapado(self) -> None:
        self._afirmar_pendiente("B0-17")

    @unittest.expectedFailure
    def test_b0_21_anuncio_disapproved(self) -> None:
        self._afirmar_pendiente("B0-21")

    @unittest.expectedFailure
    def test_b0_24_fixtures_de_forma_real(self) -> None:
        self._afirmar_pendiente("B0-24")

    # -- Cobertura: que los 25 estén presentes y con una razón no vacía -----------------------------

    def test_b0_tabla_completa_con_motivo(self) -> None:
        assert self._resultados is not None
        self.assertEqual(set(b0_e2e.ORDEN_CRITERIOS), set(self._resultados))
        for id_, c in self._resultados.items():
            self.assertIn(c.estado, ("verde", "rojo", "pendiente"), id_)
            self.assertTrue(c.motivo.strip(), f"{id_} sin motivo")


if __name__ == "__main__":
    unittest.main()
