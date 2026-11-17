"""Pruebas de :mod:`postcompra.almacen`: reserva atómica, tope diario y concurrencia real (hilos)."""
from __future__ import annotations

import threading
import unittest

from engine.errores import ErrorLimite
from postcompra.almacen import AlmacenReembolsos
from tests.postcompra.apoyo import PruebaBase, dormir_sin_esperar


class PruebaAlmacenReembolsos(PruebaBase):
    def _almacen(self) -> AlmacenReembolsos:
        return AlmacenReembolsos(self.tmp / "reembolsos.db")

    def test_reserva_nueva_gana(self) -> None:
        with self._almacen() as almacen:
            reserva = almacen.intentar_reservar("cs_test_1", "OF-202611-01", "2026-11-12", 5, "2026-11-12T08:00:00Z")
            self.assertTrue(reserva.ganador)
            self.assertIsNone(reserva.fila)

    def test_reserva_repetida_para_el_mismo_session_id_no_gana(self) -> None:
        with self._almacen() as almacen:
            almacen.intentar_reservar("cs_test_1", "OF-202611-01", "2026-11-12", 5, "2026-11-12T08:00:00Z")
            reserva = almacen.intentar_reservar("cs_test_1", "OF-202611-01", "2026-11-12", 5, "2026-11-12T08:00:01Z")
            self.assertFalse(reserva.ganador)
            self.assertEqual(reserva.fila["estado"], "reservado")

    def test_tope_diario_exacto_pasa_y_tope_mas_uno_rechaza(self) -> None:
        with self._almacen() as almacen:
            almacen.intentar_reservar("cs_test_1", "OF-202611-01", "2026-11-12", 1, "2026-11-12T08:00:00Z")
            with self.assertRaises(ErrorLimite):
                almacen.intentar_reservar("cs_test_2", "OF-202611-01", "2026-11-12", 1, "2026-11-12T08:00:01Z")

    def test_contador_diario_con_dos_hilos_solo_uno_pasa_con_tope_uno(self) -> None:
        """Dos hilos reales reservan sesiones DISTINTAS el mismo día con tope=1: solo uno debe ganar."""
        with self._almacen() as almacen:
            resultados: dict[str, object] = {}

            def intentar(nombre: str, session_id: str) -> None:
                try:
                    resultados[nombre] = almacen.intentar_reservar(session_id, "OF-202611-01", "2026-11-12", 1,
                                                                    "2026-11-12T08:00:00Z")
                except ErrorLimite as exc:
                    resultados[nombre] = exc

            h1 = threading.Thread(target=intentar, args=("a", "cs_test_a"))
            h2 = threading.Thread(target=intentar, args=("b", "cs_test_b"))
            h1.start()
            h2.start()
            h1.join(timeout=10)
            h2.join(timeout=10)

            ganadores = [r for r in resultados.values() if not isinstance(r, Exception) and r.ganador]
            rechazados = [r for r in resultados.values() if isinstance(r, ErrorLimite)]
            self.assertEqual(len(ganadores), 1)
            self.assertEqual(len(rechazados), 1)
            self.assertEqual(almacen.contar_dia("2026-11-12"), 1)

    def test_dos_reservas_paralelas_del_mismo_session_id_solo_una_gana(self) -> None:
        """Dos hilos reales reservan el MISMO session_id: solo uno gana (dedupe por sesión, no por motivo)."""
        with self._almacen() as almacen:
            resultados: list[bool] = []
            cerrojo = threading.Lock()

            def intentar() -> None:
                reserva = almacen.intentar_reservar("cs_test_paralelo", "OF-202611-01", "2026-11-12", 5,
                                                    "2026-11-12T08:00:00Z")
                with cerrojo:
                    resultados.append(reserva.ganador)

            hilos = [threading.Thread(target=intentar) for _ in range(5)]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join(timeout=10)

            self.assertEqual(sum(1 for g in resultados if g), 1)
            self.assertEqual(almacen.contar_dia("2026-11-12"), 1)

    def test_esperar_resultado_devuelve_la_fila_terminal_del_ganador(self) -> None:
        with self._almacen() as almacen:
            almacen.intentar_reservar("cs_test_1", "OF-202611-01", "2026-11-12", 5, "2026-11-12T08:00:00Z")
            almacen.marcar_ejecutado("cs_test_1", refund_id="re_1", monto_minor=1000, moneda="EUR",
                                     idempotency_key="sha256:" + "a" * 64, actualizado_en="2026-11-12T08:00:05Z")
            fila = almacen.esperar_resultado("cs_test_1", dormir=dormir_sin_esperar)
            self.assertEqual(fila["estado"], "ejecutado")
            self.assertEqual(fila["refund_id"], "re_1")

    def test_esperar_resultado_agota_intentos_si_nadie_termina(self) -> None:
        from engine.errores import ErrorExterno

        with self._almacen() as almacen:
            almacen.intentar_reservar("cs_test_1", "OF-202611-01", "2026-11-12", 5, "2026-11-12T08:00:00Z")
            with self.assertRaises(ErrorExterno):
                almacen.esperar_resultado("cs_test_1", intentos=3, dormir=dormir_sin_esperar)


if __name__ == "__main__":
    unittest.main()
