"""Pruebas de ``engine.ejecutor``: la única escritura viva sin gate (pausar)."""
from __future__ import annotations

from datetime import datetime, timezone

from engine import estado
from engine.ejecutor import EjecutorMotor, Resultado
from engine.errores import ErrorUso
from tests.engine import apoyo

BRIEF_MINIMO = {"mercado_objetivo": {"moneda_cobro": "EUR"}}


class PruebaEjecutor(apoyo.PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.raiz = self.tmp
        self.ahora = lambda: datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        self.est = estado.crear(BRIEF_MINIMO, oferta_id="OF-202611-01", familia_id="FAM-202611-01", nivel="N2",
                                raiz=self.raiz, ahora=self.ahora)
        for de, a in (("borrador", "en_construccion"), ("en_construccion", "listo_para_activar"), ("listo_para_activar", "en_test")):
            estado.transicionar_fase(self.est["oferta_id"], a, actor="prueba", causa="avance", raiz=self.raiz, ahora=self.ahora)

    def test_pausar_una_oferta_activa_mueve_la_fase(self) -> None:
        ejecutor = EjecutorMotor(raiz=self.raiz, ahora=self.ahora)
        resultado = ejecutor.pausar(self.est["oferta_id"], motivo="prueba")
        self.assertTrue(resultado.ok)
        self.assertEqual(estado.cargar(self.est["oferta_id"], raiz=self.raiz)["fase"], "pausada")

    def test_pausar_una_oferta_ya_no_activa_es_un_no_op(self) -> None:
        ejecutor = EjecutorMotor(raiz=self.raiz, ahora=self.ahora)
        ejecutor.pausar(self.est["oferta_id"], motivo="primera")
        resultado = ejecutor.pausar(self.est["oferta_id"], motivo="segunda")
        self.assertTrue(resultado.ok)
        self.assertEqual(resultado.detalle["fase"], "pausada")

    def test_pausar_un_objeto_de_meta_sin_pausador_inyectado_no_lanza(self) -> None:
        ejecutor = EjecutorMotor(raiz=self.raiz, ahora=self.ahora)
        resultado = ejecutor.pausar("123456789012345", motivo="anuncio rechazado")
        self.assertFalse(resultado.ok)
        self.assertIn("meta.pausar", resultado.detalle["pedido"])

    def test_pausar_un_objeto_de_meta_con_pausador_inyectado(self) -> None:
        llamadas = []

        def pausador(objeto_id: str, motivo: str) -> Resultado:
            llamadas.append((objeto_id, motivo))
            return Resultado(ok=True, objeto_id=objeto_id, motivo=motivo, detalle={})

        ejecutor = EjecutorMotor(raiz=self.raiz, ahora=self.ahora, pausador_meta=pausador)
        resultado = ejecutor.pausar("123456789012345", motivo="anuncio rechazado")
        self.assertTrue(resultado.ok)
        self.assertEqual(llamadas, [("123456789012345", "anuncio rechazado")])

    def test_pausar_exige_objeto_id_y_motivo(self) -> None:
        ejecutor = EjecutorMotor(raiz=self.raiz, ahora=self.ahora)
        with self.assertRaises(ErrorUso):
            ejecutor.pausar("", motivo="x")
        with self.assertRaises(ErrorUso):
            ejecutor.pausar(self.est["oferta_id"], motivo="")


if __name__ == "__main__":
    import unittest
    unittest.main()
