"""Pruebas de :mod:`postcompra.correo`: outbox local sin datos personales y proveedor real inyectado."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from engine.errores import ErrorExterno, ErrorValidacion
from engine.transporte import TransporteFixture
from postcompra import _comun
from postcompra.correo import Correo, ResendCorreo, SimuladoCorreo, texto_confirmacion_reembolso
from tests.postcompra.apoyo import PruebaBase

OFERTA = "OF-202611-01"


class PruebaSimuladoCorreo(PruebaBase):
    def test_enviar_escribe_un_archivo_en_el_outbox_sin_el_email_en_texto_plano(self) -> None:
        proveedor = SimuladoCorreo(self.tmp, ahora=lambda: datetime(2026, 11, 12, 9, 0, 0, tzinfo=timezone.utc))
        correo = Correo(oferta_id=OFERTA, referencia="cs_test_1", plantilla="confirmacion_reembolso",
                        asunto="Asunto", cuerpo_texto="Cuerpo")
        resultado = proveedor.enviar(correo, destinatario="cliente@ejemplo.com")
        self.assertTrue(resultado.enviado)
        self.assertEqual(resultado.proveedor, "simulado")
        outbox = _comun.ruta_outbox(self.tmp, OFERTA)
        archivos = list(outbox.glob("*.json"))
        self.assertEqual(len(archivos), 1)
        contenido = archivos[0].read_text(encoding="utf-8")
        self.assertNotIn("cliente@ejemplo.com", contenido)
        datos = json.loads(contenido)
        self.assertEqual(datos["referencia"], "cs_test_1")
        self.assertIn("destinatario_hash", datos)
        self.assertTrue(datos["destinatario_hash"].startswith("sha256:"))

    def test_enviar_exige_destinatario_con_forma_de_email(self) -> None:
        proveedor = SimuladoCorreo(self.tmp)
        correo = Correo(oferta_id=OFERTA, referencia="cs_test_1", plantilla="x", asunto="a", cuerpo_texto="b")
        with self.assertRaises(ErrorValidacion):
            proveedor.enviar(correo, destinatario="no-es-un-email")


class PruebaResendCorreo(PruebaBase):
    def test_enviar_llama_a_resend_con_el_cuerpo_esperado(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "POST", "url": "https://api.resend.com/emails", "cuerpo": {"id": "email_123"}},
        ])
        proveedor = ResendCorreo(transporte, clave_api="re_clave_de_prueba", remitente="ventas@ejemplo.com")
        correo = Correo(oferta_id=OFERTA, referencia="cs_test_1", plantilla="confirmacion_reembolso",
                        asunto="Asunto", cuerpo_texto="Cuerpo")
        resultado = proveedor.enviar(correo, destinatario="cliente@ejemplo.com")
        self.assertEqual(resultado.proveedor, "resend")
        self.assertEqual(resultado.referencia_externa, "email_123")
        llamada = transporte.llamadas_a("POST")[0]
        cuerpo = llamada.json()
        self.assertEqual(cuerpo["to"], ["cliente@ejemplo.com"])
        self.assertEqual(cuerpo["subject"], "Asunto")

    def test_enviar_sin_respuesta_grabada_es_error_externo(self) -> None:
        transporte = TransporteFixture([])
        proveedor = ResendCorreo(transporte, clave_api="re_clave_de_prueba", remitente="ventas@ejemplo.com")
        correo = Correo(oferta_id=OFERTA, referencia="cs_test_1", plantilla="x", asunto="a", cuerpo_texto="b")
        with self.assertRaises(ErrorExterno):
            proveedor.enviar(correo, destinatario="cliente@ejemplo.com")


class PruebaTextoConfirmacion(unittest.TestCase):
    def test_con_renuncia_incluye_el_texto_de_desistimiento(self) -> None:
        _asunto, cuerpo = texto_confirmacion_reembolso(monto_texto="19.90", moneda="EUR", producto="Guía",
                                                        con_renuncia=True)
        self.assertIn("derecho de desistimiento", cuerpo.lower())

    def test_sin_renuncia_no_incluye_el_texto(self) -> None:
        _asunto, cuerpo = texto_confirmacion_reembolso(monto_texto="19.90", moneda="EUR", producto="Guía",
                                                        con_renuncia=False)
        self.assertNotIn("desistimiento", cuerpo.lower())


if __name__ == "__main__":
    unittest.main()
