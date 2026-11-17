"""Pruebas de :mod:`postcompra.evidencia`: paquete de disputa sin datos personales (B0-20)."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from engine import comun
from engine.transporte import TransporteFixture
from postcompra import _comun
from postcompra.cliente_stripe import ClienteStripe
from postcompra.evidencia import armar_paquete
from tests.postcompra.apoyo import PruebaBase, reglas_stripe

OFERTA = "OF-202611-01"
PAGADO_EN = datetime(2026, 11, 10, 8, 0, 0, tzinfo=timezone.utc)


class PruebaArmarPaquete(PruebaBase):
    def test_arma_resumen_y_manifiesto_sin_datos_personales(self) -> None:
        session_id = "cs_test_evidencia_1"
        transporte = TransporteFixture(reglas_stripe(session_id, monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN,
                                                      disputa=True))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        linea_entrega = {
            "schema_version": "1.0.0", "entrega_id": "ENT-" + "a" * 12, "ts": "2026-11-10T08:05:00Z",
            "oferta_id": OFERTA, "checkout_session_id": session_id, "email_hmac": None, "estado": "entregado",
            "producto_version": "v1", "producto_sha256": "sha256:" + "b" * 64,
            "enlace": {"vence_en": "2026-11-17T08:05:00Z", "max_descargas": 5, "descargas": 1}, "intentos": 1,
            "idempotency_key": "sha256:" + "c" * 64, "ejecutor": "script",
        }
        comun.anexar_jsonl(_comun.ruta_entregas(self.tmp, OFERTA), linea_entrega)

        resultado = armar_paquete(session_id=session_id, oferta_id=OFERTA, raiz=self.tmp, salida=self.tmp / "paquete",
                                  stripe=stripe)
        self.assertEqual(set(resultado.archivos), {"resumen.json", "manifiesto.json"})
        resumen = json.loads((resultado.carpeta / "resumen.json").read_text(encoding="utf-8"))
        self.assertEqual(resumen["checkout_session_id"], session_id)
        self.assertTrue(resumen["disputa_abierta"])
        self.assertEqual(len(resumen["entregas"]), 1)
        self.assertEqual(resumen["entregas"][0]["estado"], "entregado")
        texto_completo = (resultado.carpeta / "resumen.json").read_text(encoding="utf-8")
        self.assertNotIn("@", texto_completo)  # ningún email

        manifiesto = json.loads((resultado.carpeta / "manifiesto.json").read_text(encoding="utf-8"))
        self.assertIn("resumen.json", manifiesto)
        self.assertEqual(manifiesto["resumen.json"], comun.hash_archivo(resultado.carpeta / "resumen.json"))

    def test_sin_entrega_local_agrega_una_nota(self) -> None:
        session_id = "cs_test_evidencia_2"
        transporte = TransporteFixture(reglas_stripe(session_id, monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        resultado = armar_paquete(session_id=session_id, oferta_id=OFERTA, raiz=self.tmp, salida=self.tmp / "paquete2",
                                  stripe=stripe)
        resumen = json.loads((resultado.carpeta / "resumen.json").read_text(encoding="utf-8"))
        self.assertIn("nota", resumen)
        self.assertEqual(resumen["entregas"], [])


if __name__ == "__main__":
    unittest.main()
