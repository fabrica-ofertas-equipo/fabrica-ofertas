"""Pruebas de :mod:`postcompra.reembolso_manual`: acción H, respeta PAUSA, no respeta el tope automático."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine.errores import ErrorBloqueado, ErrorValidacion
from engine.transporte import TransporteFixture
from postcompra.cliente_stripe import ClienteStripe
from postcompra.reembolso_manual import reembolso_manual
from tests.postcompra.apoyo import PruebaBase, crear_empresa, refrescar_infra, reglas_stripe

OFERTA = "OF-202611-01"
PAGADO_EN = datetime(2026, 10, 1, 8, 0, 0, tzinfo=timezone.utc)  # bien fuera de garantía a propósito
AHORA = datetime(2026, 11, 20, 9, 0, 0, tzinfo=timezone.utc)


class PruebaReembolsoManual(PruebaBase):
    def _emp(self):
        emp = crear_empresa(self.tmp, entorno="desarrollo", modo_infra="prueba")
        refrescar_infra(emp, AHORA)
        return emp

    def test_puede_reembolsar_fuera_de_garantia_y_por_encima_del_tope_automatico(self) -> None:
        emp = self._emp()
        # 5000 > reembolso_auto_max (3000 en la fixture de B1): el automático lo habría rechazado.
        transporte = TransporteFixture(reglas_stripe("cs_test_m1", monto_pagado=5000, moneda="EUR", pagado_en=PAGADO_EN))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        resultado = reembolso_manual(session_id="cs_test_m1", motivo="otro", monto_minor=5000, oferta_id=OFERTA,
                                     aprobado_por="dueno", raiz=self.tmp, env=emp.env, ahora=lambda: AHORA,
                                     modo="fixture", stripe=stripe)
        self.assertEqual(resultado.estado, "ejecutado")
        ruta = self.tmp / "ofertas" / OFERTA / "10-postcompra" / "reembolsos.jsonl"
        lineas = ruta.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lineas), 1)
        self.assertIn('"ejecutor":"humano"', lineas[0])

    def test_pausa_tambien_bloquea_el_manual(self) -> None:
        emp = self._emp()
        (self.tmp / "empresa" / "PAUSA").write_text("", encoding="utf-8")
        transporte = TransporteFixture(reglas_stripe("cs_test_m2", monto_pagado=5000, moneda="EUR", pagado_en=PAGADO_EN,
                                                      veces_post_refund=0))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        with self.assertRaises(ErrorBloqueado):
            reembolso_manual(session_id="cs_test_m2", motivo="otro", monto_minor=5000, oferta_id=OFERTA,
                             aprobado_por="dueno", raiz=self.tmp, env=emp.env, ahora=lambda: AHORA, modo="fixture",
                             stripe=stripe)

    def test_no_puede_exceder_lo_pendiente_en_stripe(self) -> None:
        emp = self._emp()
        transporte = TransporteFixture(reglas_stripe("cs_test_m3", monto_pagado=1000, moneda="EUR", pagado_en=PAGADO_EN,
                                                      veces_post_refund=0))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        with self.assertRaises(ErrorValidacion):
            reembolso_manual(session_id="cs_test_m3", motivo="otro", monto_minor=5000, oferta_id=OFERTA,
                             aprobado_por="dueno", raiz=self.tmp, env=emp.env, ahora=lambda: AHORA, modo="fixture",
                             stripe=stripe)

    def test_segundo_intento_para_la_misma_sesion_no_reembolsa_dos_veces(self) -> None:
        emp = self._emp()
        transporte = TransporteFixture(reglas_stripe("cs_test_m4", monto_pagado=5000, moneda="EUR", pagado_en=PAGADO_EN))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        primero = reembolso_manual(session_id="cs_test_m4", motivo="otro", monto_minor=5000, oferta_id=OFERTA,
                                   aprobado_por="dueno", raiz=self.tmp, env=emp.env, ahora=lambda: AHORA, modo="fixture",
                                   stripe=stripe)
        segundo = reembolso_manual(session_id="cs_test_m4", motivo="otro", monto_minor=5000, oferta_id=OFERTA,
                                   aprobado_por="dueno", raiz=self.tmp, env=emp.env, ahora=lambda: AHORA, modo="fixture",
                                   stripe=stripe)
        self.assertEqual(segundo.estado, "ya_reembolsado")
        self.assertEqual(segundo.refund_id, primero.refund_id)
        self.assertEqual(len(transporte.llamadas_a("POST", "https://api.stripe.com/v1/refunds")), 1)


if __name__ == "__main__":
    unittest.main()
