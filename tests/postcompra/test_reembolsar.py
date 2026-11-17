"""Pruebas de :mod:`postcompra.reembolsar`: algoritmo de docs/06 §4.8 (casos límite obligatorios)."""
from __future__ import annotations

import threading
import unittest
from datetime import datetime, timedelta, timezone

from engine.errores import ErrorBloqueado, ErrorLimite
from engine.transporte import TransporteFixture
from postcompra.cliente_stripe import ClienteStripe
from postcompra.correo import SimuladoCorreo
from postcompra.reembolsar import reembolsar
from tests.postcompra.apoyo import PruebaBase, crear_empresa, dormir_sin_esperar, refrescar_infra, reglas_stripe

OFERTA = "OF-202611-01"
PAGADO_EN = datetime(2026, 11, 10, 8, 0, 0, tzinfo=timezone.utc)
AHORA = datetime(2026, 11, 11, 9, 0, 0, tzinfo=timezone.utc)  # 1 día después: dentro de garantía (14 días)


class PruebaReembolsarDryRun(PruebaBase):
    def test_dry_run_no_escribe_nada_y_devuelve_el_plan(self) -> None:
        emp = crear_empresa(self.tmp, entorno="desarrollo")
        transporte = TransporteFixture(reglas_stripe("cs_test_0001", monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        antes = sorted((self.tmp / "empresa").rglob("*"))
        resultado = reembolsar(session_id="cs_test_0001", motivo="dentro_de_garantia", oferta_id=OFERTA,
                               raiz=self.tmp, env=emp.env, ahora=lambda: AHORA, modo="dry_run", stripe=stripe)
        despues = sorted((self.tmp / "empresa").rglob("*"))
        self.assertEqual(antes, despues)
        self.assertEqual(resultado.estado, "simulado")
        self.assertIsNone(resultado.motivo_rechazo)
        self.assertEqual(resultado.monto_minor, 1990)

    def test_dry_run_detecta_el_rechazo_sin_tocar_nada(self) -> None:
        emp = crear_empresa(self.tmp, entorno="desarrollo")
        transporte = TransporteFixture(reglas_stripe("cs_test_0002", monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN,
                                                      disputa=True))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        resultado = reembolsar(session_id="cs_test_0002", motivo="dentro_de_garantia", oferta_id=OFERTA,
                               raiz=self.tmp, env=emp.env, ahora=lambda: AHORA, modo="dry_run", stripe=stripe)
        self.assertEqual(resultado.estado, "simulado")
        self.assertEqual(resultado.motivo_rechazo, "disputa_abierta")


class PruebaReembolsarFixture(PruebaBase):
    def _emp(self, ahora: datetime = AHORA):
        emp = crear_empresa(self.tmp, entorno="desarrollo", modo_infra="prueba")
        refrescar_infra(emp, ahora)
        return emp

    def test_fixture_ejecuta_y_escribe_reembolsos_jsonl_y_outbox(self) -> None:
        emp = self._emp()
        transporte = TransporteFixture(reglas_stripe("cs_test_0003", monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        correo = SimuladoCorreo(self.tmp, ahora=lambda: AHORA)
        resultado = reembolsar(session_id="cs_test_0003", motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                               env=emp.env, ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte,
                               correo=correo, destinatario="cliente@ejemplo.com")
        self.assertEqual(resultado.estado, "ejecutado")
        self.assertEqual(resultado.refund_id, "re_test_0001")
        ruta = self.tmp / "ofertas" / OFERTA / "10-postcompra" / "reembolsos.jsonl"
        self.assertTrue(ruta.exists())
        self.assertEqual(len(ruta.read_text(encoding="utf-8").strip().splitlines()), 1)
        outbox = list((self.tmp / "ofertas" / OFERTA / "10-postcompra" / "outbox").glob("*.json"))
        self.assertEqual(len(outbox), 1)

    def test_pausa_bloquea_el_reembolso_automatico(self) -> None:
        emp = self._emp()
        (self.tmp / "empresa" / "PAUSA").write_text("", encoding="utf-8")
        transporte = TransporteFixture(reglas_stripe("cs_test_0004", monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        with self.assertRaises(ErrorBloqueado):
            reembolsar(session_id="cs_test_0004", motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                      env=emp.env, ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte)
        ruta = self.tmp / "ofertas" / OFERTA / "10-postcompra" / "reembolsos.jsonl"
        self.assertFalse(ruta.exists())

    def test_disputa_abierta_rechaza_y_no_llama_a_crear_reembolso(self) -> None:
        emp = self._emp()
        transporte = TransporteFixture(reglas_stripe("cs_test_0005", monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN,
                                                      disputa=True, veces_post_refund=0))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        with self.assertRaises(ErrorLimite) as ctx:
            reembolsar(session_id="cs_test_0005", motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                      env=emp.env, ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte)
        self.assertEqual(ctx.exception.detalle.get("motivo"), "disputa_abierta")
        self.assertEqual(len(transporte.llamadas_a("POST", "https://api.stripe.com/v1/refunds")), 0)

    def test_fuera_de_garantia_rechaza(self) -> None:
        ahora_lejos = PAGADO_EN + timedelta(days=30)  # política de prueba: 14 días
        emp = self._emp(ahora_lejos)
        transporte = TransporteFixture(reglas_stripe("cs_test_0006", monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN,
                                                      veces_post_refund=0))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        with self.assertRaises(ErrorLimite) as ctx:
            reembolsar(session_id="cs_test_0006", motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                      env=emp.env, ahora=lambda: ahora_lejos, modo="fixture", stripe=stripe, transporte=transporte)
        self.assertEqual(ctx.exception.detalle.get("motivo"), "fuera_de_garantia")

    def test_excede_el_tope_automatico_rechaza(self) -> None:
        emp = self._emp()
        # reembolso_auto_max de la fixture de B1 es 3000 (EUR); pedimos un pago de 5000.
        transporte = TransporteFixture(reglas_stripe("cs_test_0007", monto_pagado=5000, moneda="EUR", pagado_en=PAGADO_EN,
                                                      veces_post_refund=0))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        with self.assertRaises(ErrorLimite) as ctx:
            reembolsar(session_id="cs_test_0007", motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                      env=emp.env, ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte)
        self.assertEqual(ctx.exception.detalle.get("motivo"), "excede_tope")

    def test_tope_diario_mas_uno_rechaza(self) -> None:
        emp = self._emp()
        # reembolsos_auto_max_por_dia de la fixture de B1 es 5: agotamos el tope con 5 sesiones distintas.
        for n in range(5):
            sid = f"cs_test_dia_{n:04d}"
            transporte = TransporteFixture(reglas_stripe(sid, monto_pagado=1000, moneda="EUR", pagado_en=PAGADO_EN,
                                                          refund_id=f"re_dia_{n:04d}"))
            stripe = ClienteStripe(transporte, clave_api="rk_prueba")
            resultado = reembolsar(session_id=sid, motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                                   env=emp.env, ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte)
            self.assertEqual(resultado.estado, "ejecutado")
        transporte = TransporteFixture(reglas_stripe("cs_test_dia_tope_mas_uno", monto_pagado=1000, moneda="EUR",
                                                      pagado_en=PAGADO_EN, veces_post_refund=0))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        with self.assertRaises(ErrorLimite) as ctx:
            reembolsar(session_id="cs_test_dia_tope_mas_uno", motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                      env=emp.env, ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte)
        self.assertEqual(ctx.exception.detalle.get("clave"), "reembolsos_auto_max_por_dia")

    def test_reintento_tras_25_horas_no_crea_un_segundo_reembolso(self) -> None:
        emp = self._emp()
        session_id = "cs_test_0008"
        transporte = TransporteFixture(reglas_stripe(session_id, monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN))
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        primero = reembolsar(session_id=session_id, motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                             env=emp.env, ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte)
        self.assertEqual(primero.estado, "ejecutado")
        mas_tarde = AHORA + timedelta(hours=25)
        refrescar_infra(emp, mas_tarde)  # la infraestructura "vivo" también caduca a las 6 h
        segundo = reembolsar(session_id=session_id, motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=self.tmp,
                             env=emp.env, ahora=lambda: mas_tarde, modo="fixture", stripe=stripe, transporte=transporte)
        self.assertEqual(segundo.estado, "ejecutado")
        self.assertEqual(segundo.refund_id, primero.refund_id)
        # La regla de POST de /refunds tiene veces=1: si hubiera un segundo POST, el fixture lo rechazaría.
        self.assertEqual(len(transporte.llamadas_a("POST", "https://api.stripe.com/v1/refunds")), 1)
        ruta = self.tmp / "ofertas" / OFERTA / "10-postcompra" / "reembolsos.jsonl"
        self.assertEqual(len(ruta.read_text(encoding="utf-8").strip().splitlines()), 1)

    def test_dos_reembolsos_paralelos_con_motivo_distinto_producen_uno_solo(self) -> None:
        emp = self._emp()
        session_id = "cs_test_paralelo"
        transporte = TransporteFixture(reglas_stripe(session_id, monto_pagado=1990, moneda="EUR", pagado_en=PAGADO_EN))
        resultados: list[object] = []
        cerrojo = threading.Lock()

        def intentar(motivo: str) -> None:
            stripe = ClienteStripe(transporte, clave_api="rk_prueba")
            try:
                r = reembolsar(session_id=session_id, motivo=motivo, oferta_id=OFERTA, raiz=self.tmp, env=emp.env,
                               ahora=lambda: AHORA, modo="fixture", stripe=stripe, transporte=transporte,
                               dormir=dormir_sin_esperar)
            except Exception as exc:  # noqa: BLE001 - se guarda para inspeccionar en el hilo principal
                r = exc
            with cerrojo:
                resultados.append(r)

        h1 = threading.Thread(target=intentar, args=("dentro_de_garantia",))
        h2 = threading.Thread(target=intentar, args=("producto_no_recibido",))
        h1.start()
        h2.start()
        h1.join(timeout=10)
        h2.join(timeout=10)

        self.assertEqual(len(resultados), 2)
        for r in resultados:
            self.assertNotIsInstance(r, Exception)
            self.assertEqual(r.estado, "ejecutado")
            self.assertEqual(r.refund_id, "re_test_0001")
        self.assertEqual(len(transporte.llamadas_a("POST", "https://api.stripe.com/v1/refunds")), 1)
        ruta = self.tmp / "ofertas" / OFERTA / "10-postcompra" / "reembolsos.jsonl"
        self.assertEqual(len(ruta.read_text(encoding="utf-8").strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
