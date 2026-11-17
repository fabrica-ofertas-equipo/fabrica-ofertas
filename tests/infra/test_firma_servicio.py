"""Pruebas de ``infra.firma_servicio``: cabeceras internas (docs/06 §4.7)."""
from __future__ import annotations

import unittest

from infra.firma_servicio import cabeceras_internas, verificar_cabeceras

CLAVE = b"clave-de-prueba"


class PruebaCabecerasInternas(unittest.TestCase):
    def test_verifica_con_la_misma_clave_cuerpo_y_ts(self) -> None:
        cab = cabeceras_internas(CLAVE, b'{"a":1}', "2026-11-09T08:00:00Z")
        self.assertTrue(verificar_cabeceras(CLAVE, b'{"a":1}', "2026-11-09T08:00:00Z", cab["X-Fabrica-Firma"]))

    def test_formato_es_hmac_sha256_igual(self) -> None:
        cab = cabeceras_internas(CLAVE, b"x", "2026-11-09T08:00:00Z")
        self.assertRegex(cab["X-Fabrica-Firma"], r"^hmac-sha256=[0-9a-f]{64}$")
        self.assertEqual(cab["X-Fabrica-Ts"], "2026-11-09T08:00:00Z")

    def test_cuerpo_distinto_no_verifica(self) -> None:
        cab = cabeceras_internas(CLAVE, b"x", "2026-11-09T08:00:00Z")
        self.assertFalse(verificar_cabeceras(CLAVE, b"y", "2026-11-09T08:00:00Z", cab["X-Fabrica-Firma"]))

    def test_ts_distinto_no_verifica(self) -> None:
        cab = cabeceras_internas(CLAVE, b"x", "2026-11-09T08:00:00Z")
        self.assertFalse(verificar_cabeceras(CLAVE, b"x", "2026-11-09T09:00:00Z", cab["X-Fabrica-Firma"]))

    def test_clave_distinta_no_verifica(self) -> None:
        cab = cabeceras_internas(CLAVE, b"x", "2026-11-09T08:00:00Z")
        self.assertFalse(verificar_cabeceras(b"otra-clave", b"x", "2026-11-09T08:00:00Z", cab["X-Fabrica-Firma"]))

    def test_firma_ausente_no_verifica(self) -> None:
        self.assertFalse(verificar_cabeceras(CLAVE, b"x", "2026-11-09T08:00:00Z", None))


if __name__ == "__main__":
    unittest.main()


class PruebaContextoDeFirma(unittest.TestCase):
    """Vectores de ``dashboard/CONTRATO.md`` §7b: la firma de una respuesta nunca autentica una petición."""

    CLAVE = b"secreto-de-ejemplo"
    TS = "2026-11-09T12:00:00Z"
    CUERPO = b'{"etapa":"D1","oferta_id":"OF-202611-01"}'

    def test_vectores_del_contrato(self) -> None:
        esperados = {
            None: "hmac-sha256=d37d04267ad3153664bc993ac36a40ea09d854920339d5f6674d70b2d0594749",
            "req": "hmac-sha256=74cc8e5c10f5c6f337b5dba9ecba66c0a0fe4ac9c5d0218b1265d5a7e74d455e",
            "resp": "hmac-sha256=a73d537ebdb37bc0380e8bbadd54be3e7bc12c45b4114661c48e243598f282de",
        }
        for contexto, firma in esperados.items():
            with self.subTest(contexto=contexto):
                self.assertEqual(cabeceras_internas(self.CLAVE, self.CUERPO, self.TS, contexto)["X-Fabrica-Firma"], firma)

    def test_una_firma_de_un_contexto_no_vale_en_otro(self) -> None:
        for emitida in (None, "req", "resp"):
            firma = cabeceras_internas(self.CLAVE, self.CUERPO, self.TS, emitida)["X-Fabrica-Firma"]
            for verificada in (None, "req", "resp"):
                with self.subTest(emitida=emitida, verificada=verificada):
                    self.assertEqual(verificar_cabeceras(self.CLAVE, self.CUERPO, self.TS, firma, verificada), emitida == verificada)

    def test_contexto_desconocido_falla_cerrado(self) -> None:
        with self.assertRaises(ValueError):
            cabeceras_internas(self.CLAVE, self.CUERPO, self.TS, "otro")
        with self.assertRaises(ValueError):
            verificar_cabeceras(self.CLAVE, self.CUERPO, self.TS, "hmac-sha256=00", "REQ")

    def test_sin_contexto_el_formato_de_los_workers_no_cambia(self) -> None:
        sin = cabeceras_internas(self.CLAVE, self.CUERPO, self.TS)
        self.assertEqual(sin, cabeceras_internas(self.CLAVE, self.CUERPO, self.TS, None))
