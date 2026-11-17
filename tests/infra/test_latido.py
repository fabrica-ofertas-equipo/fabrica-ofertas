"""Pruebas de ``infra.latido``: payload firmado, regla de vencimiento (espejo de la del Worker) y CLI."""
from __future__ import annotations

import contextlib
import io
import json
from datetime import datetime, timezone

from engine import comun
from engine.errores import ErrorExterno, ErrorUso
from engine.transporte import TransporteFixture
from infra import latido
from infra.firma_servicio import verificar_cabeceras
from tests.infra.apoyo import PruebaBase

T0 = datetime(2026, 11, 9, 8, 0, 0, tzinfo=timezone.utc)
CLAVE = b"clave-latido-de-prueba"


class PruebaConstruirYFirmar(PruebaBase):
    def test_construir_es_deterministico(self) -> None:
        p1 = latido.construir_latido(estado_generado_en="2026-11-09T07:55:00Z", semaforo="VERDE", pausa=False, version="1", ahora=T0)
        p2 = latido.construir_latido(estado_generado_en="2026-11-09T07:55:00Z", semaforo="VERDE", pausa=False, version="1", ahora=T0)
        self.assertEqual(p1, p2)

    def test_semaforo_invalido_es_erroruso(self) -> None:
        with self.assertRaises(ErrorUso):
            latido.construir_latido(estado_generado_en="2026-11-09T07:55:00Z", semaforo="AZUL", pausa=False, version="1", ahora=T0)

    def test_enviar_firma_el_cuerpo_exacto(self) -> None:
        payload = latido.construir_latido(estado_generado_en="2026-11-09T07:55:00Z", semaforo="VERDE", pausa=False, version="1", ahora=T0)
        t = TransporteFixture([{"metodo": "POST", "url": "https://watchdog.ejemplo/latido", "estado": 200}])
        resp = latido.enviar(t, "https://watchdog.ejemplo", payload, CLAVE)
        self.assertTrue(resp.ok)
        llamada = t.llamadas[0]
        self.assertEqual(llamada.json(), payload)
        cuerpo_bytes = comun.json_canonico(payload)
        self.assertTrue(verificar_cabeceras(CLAVE, cuerpo_bytes, payload["ts"], llamada.cabeceras["X-Fabrica-Firma"]))
        self.assertEqual(llamada.cabeceras["X-Fabrica-Ts"], payload["ts"])


class PruebaEvaluarVencimiento(PruebaBase):
    def test_sin_latido_previo_debe_pausar(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido=None, ahora=T0, latido_max_min=30)
        self.assertTrue(r.debe_pausar)

    def test_latido_vigente_no_pausa(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido="2026-11-09T07:50:00Z", ahora=T0, latido_max_min=30)
        self.assertFalse(r.debe_pausar)

    def test_latido_vencido_pausa(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido="2026-11-09T07:00:00Z", ahora=T0, latido_max_min=30)
        self.assertTrue(r.debe_pausar)

    def test_pausa_declarada_en_el_latido_pausa_igual(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido="2026-11-09T07:59:00Z", ahora=T0, latido_max_min=30, pausa=True)
        self.assertTrue(r.debe_pausar)

    def test_semaforo_rojo_pausa(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido="2026-11-09T07:59:00Z", ahora=T0, latido_max_min=30, semaforo="ROJO")
        self.assertTrue(r.debe_pausar)

    def test_estado_generado_en_vencido_pausa(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido="2026-11-09T07:59:00Z", ahora=T0, latido_max_min=30,
                                       estado_generado_en="2026-11-09T01:00:00Z")
        self.assertTrue(r.debe_pausar)

    def test_ciclo_d8_colgado_con_latido_vivo_pausa(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido="2026-11-09T07:59:00Z", ahora=T0, latido_max_min=30,
                                       ciclo_max_min=60, ultimo_ciclo_d8="2026-11-09T06:00:00Z")
        self.assertTrue(r.debe_pausar)

    def test_borde_exacto_del_maximo_no_pausa(self) -> None:
        r = latido.evaluar_vencimiento(ultimo_latido="2026-11-09T07:30:00Z", ahora=T0, latido_max_min=30)
        self.assertFalse(r.debe_pausar)


class PruebaVerificar(PruebaBase):
    def test_estado_ok(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": "https://watchdog.ejemplo/estado", "cuerpo": {"visto_hace_min": 2}}])
        self.assertEqual(latido.verificar(t, "https://watchdog.ejemplo"), {"visto_hace_min": 2})

    def test_estado_no_ok_es_errorexterno(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": "https://watchdog.ejemplo/estado", "estado": 503}])
        with self.assertRaises(ErrorExterno):
            latido.verificar(t, "https://watchdog.ejemplo")


class PruebaCLI(PruebaBase):
    def test_evaluar_vencido_sale_4(self) -> None:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = latido.main(["evaluar", "--ultimo-latido", "2026-11-09T07:00:00Z", "--ahora", "2026-11-09T08:00:00Z",
                                  "--max-min", "30", "--json"])
        self.assertEqual(codigo, 4)
        self.assertTrue(json.loads(salida.getvalue())["datos"]["debe_pausar"])

    def test_evaluar_vigente_sale_0(self) -> None:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = latido.main(["evaluar", "--ultimo-latido", "2026-11-09T07:50:00Z", "--ahora", "2026-11-09T08:00:00Z",
                                  "--max-min", "30", "--json"])
        self.assertEqual(codigo, 0)

    def test_verificar_necesita_fixture(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            codigo = latido.main(["verificar", "--url", "https://watchdog.ejemplo"])
        self.assertEqual(codigo, 2)


if __name__ == "__main__":
    import unittest

    unittest.main()
