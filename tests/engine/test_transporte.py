"""Pruebas de ``engine.transporte``: el protocolo inyectable y ``TransporteFixture`` (sin red, sin sockets)."""
from __future__ import annotations

import json
import socket
import unittest

from engine.errores import ErrorExterno, ErrorValidacion
from engine.transporte import Respuesta, Transporte, TransporteFixture
from tests.engine.apoyo import FIXTURES, PruebaBase

URL = "https://graph.example/v0/act_100000000000001/campaigns"
CABECERAS = {"Authorization": "Bearer ficticio-123", "Content-Type": "application/json", "X-App-Secret-Proof": "abc"}


class PruebaTransporteFixture(PruebaBase):
    """Responde con datos de fixture, en orden, y registra cada llamada."""

    def test_cumple_el_protocolo_transporte(self) -> None:
        self.assertIsInstance(TransporteFixture(), Transporte)

    def test_responde_y_registra_la_llamada_con_las_credenciales_ocultas(self) -> None:
        t = TransporteFixture([{"metodo": "post", "url": URL, "estado": 200, "cuerpo": {"id": "111"}}])
        r = t.solicitar("POST", URL, cabeceras=CABECERAS, cuerpo=b'{"name":"x"}', timeout_s=10)
        self.assertEqual((r.estado, r.ok, r.json()), (200, True, {"id": "111"}))
        (llamada,) = t.llamadas
        self.assertEqual((llamada.metodo, llamada.url, llamada.timeout_s), ("POST", URL, 10))
        self.assertEqual(llamada.json(), {"name": "x"})
        self.assertEqual(llamada.cabeceras["Authorization"], "****")
        self.assertEqual(llamada.cabeceras["X-App-Secret-Proof"], "****")
        self.assertEqual(llamada.cabeceras["Content-Type"], "application/json")
        self.assertNotIn("ficticio-123", repr(t.llamadas))

    def test_falla_el_segundo_post(self) -> None:
        t = TransporteFixture([
            {"metodo": "POST", "url_prefijo": "https://graph.example/", "estado": 200, "cuerpo": {"id": "1"}},
            {"metodo": "POST", "url_prefijo": "https://graph.example/", "estado": 500, "cuerpo": {"error": "x"}},
        ])
        primero = t.solicitar("POST", URL, cabeceras={}, cuerpo=None, timeout_s=5)
        segundo = t.solicitar("POST", URL, cabeceras={}, cuerpo=None, timeout_s=5)
        self.assertEqual((primero.estado, segundo.estado), (200, 500))
        self.assertFalse(segundo.ok)
        with self.assertRaises(ErrorExterno):
            t.solicitar("POST", URL, cabeceras={}, cuerpo=None, timeout_s=5)  # no hay tercera respuesta grabada
        self.assertEqual(len(t.llamadas), 3)
        self.assertEqual(t.pendientes(), [])

    def test_reglas_ilimitadas_y_pendientes(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": URL, "veces": 0}, {"metodo": "DELETE", "url": URL, "veces": 2}])
        for _ in range(5):
            self.assertEqual(t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5).estado, 200)
        self.assertEqual(len(t.pendientes()), 1)
        t.solicitar("DELETE", URL, cabeceras={}, cuerpo=None, timeout_s=5)
        self.assertEqual(t.pendientes()[0]["_restantes"], 1)

    def test_sin_regla_aplicable_falla_en_vez_de_inventar(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": URL}])
        for metodo, url in (("POST", URL), ("GET", URL + "/otra")):
            with self.subTest(metodo=metodo, url=url), self.assertRaises(ErrorExterno):
                t.solicitar(metodo, url, cabeceras={}, cuerpo=None, timeout_s=5)

    def test_fallas_simuladas(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": URL, "error": "tiempo_agotado"}, {"metodo": "GET", "url": URL, "error": "red"}])
        for esperado in ("tiempo", "red"):
            with self.assertRaises(ErrorExterno) as cm:
                t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5)
            self.assertIn(esperado, cm.exception.mensaje)
        self.assertEqual(cm.exception.codigo_salida, 6)

    def test_reglas_mal_formadas(self) -> None:
        for regla in ({"url": URL}, {"metodo": "GET"}, {"metodo": "GET", "url": URL, "veces": -1}, {"metodo": "GET", "url": URL, "veces": True}, "texto"):
            with self.subTest(regla=regla), self.assertRaises(ErrorValidacion):
                TransporteFixture([regla])  # type: ignore[list-item]
        with self.assertRaises(ErrorValidacion):
            TransporteFixture([{"metodo": "GET", "url": URL, "error": "inventado"}]).solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5)

    def test_cuerpos_en_texto_bytes_o_json(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": URL, "veces": 0, "cuerpo": "hola ñ"}])
        self.assertEqual(t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5).texto, "hola ñ")
        t = TransporteFixture([{"metodo": "GET", "url": URL, "cuerpo": b"\x00\x01"}])
        self.assertEqual(t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5).cuerpo, b"\x00\x01")

    def test_respuesta_que_no_es_json(self) -> None:
        with self.assertRaises(ErrorExterno):
            Respuesta(200, {}, b"<html>").json()

    def test_llamadas_a_filtra_por_metodo_y_prefijo(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": URL, "veces": 0}, {"metodo": "POST", "url": URL, "veces": 0}])
        t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5)
        t.solicitar("POST", URL, cabeceras={}, cuerpo=b"{}", timeout_s=5)
        self.assertEqual(len(t.llamadas_a("post")), 1)
        self.assertEqual(len(t.llamadas_a(url_prefijo="https://graph.example/")), 2)
        self.assertEqual(len(t.llamadas_a("GET", "https://otro.example/")), 0)


class PruebaFixtureDesdeArchivo(PruebaBase):
    """Las respuestas grabadas se leen de ``tests/fixtures/engine/transporte/``."""

    def test_reglas_y_cuerpo_desde_archivo(self) -> None:
        t = TransporteFixture.desde_archivo(FIXTURES / "transporte" / "reglas_meta.json")
        lista = t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5).json()
        self.assertEqual(lista["data"][0]["effective_status"], "PAUSED")
        self.assertEqual(t.solicitar("POST", "https://graph.example/v0/111", cabeceras={}, cuerpo=b"{}", timeout_s=5).json(), {"id": "111"})
        r613 = t.solicitar("POST", "https://graph.example/v0/111", cabeceras={}, cuerpo=b"{}", timeout_s=5)
        self.assertEqual((r613.estado, r613.json()["error"]["code"]), (613, 613))

    def test_cuerpo_archivo_no_puede_salir_de_la_carpeta(self) -> None:
        (self.tmp / "reglas.json").write_text(json.dumps([{"metodo": "GET", "url": URL, "cuerpo_archivo": "../../../etc/hosts"}]), encoding="utf-8")
        t = TransporteFixture.desde_archivo(self.tmp / "reglas.json")
        with self.assertRaises(ErrorValidacion):
            t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5)

    def test_cuerpo_archivo_exige_carpeta(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": URL, "cuerpo_archivo": "x.json"}])
        with self.assertRaises(ErrorValidacion):
            t.solicitar("GET", URL, cabeceras={}, cuerpo=None, timeout_s=5)

    def test_archivo_que_no_es_una_lista(self) -> None:
        (self.tmp / "mal.json").write_text('{"reglas": 5}', encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            TransporteFixture.desde_archivo(self.tmp / "mal.json")


class PruebaSinRed(PruebaBase):
    """Ninguna prueba abre un socket: ``socket.socket`` está bloqueado en ``setUp``."""

    def test_socket_esta_bloqueado(self) -> None:
        with self.assertRaises(AssertionError):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with self.assertRaises(AssertionError):
            socket.create_connection(("127.0.0.1", 9))

    def test_usar_el_fixture_no_toca_la_red(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": URL}])
        self.assertEqual(t.solicitar("GET", URL, cabeceras=CABECERAS, cuerpo=None, timeout_s=1).estado, 200)


if __name__ == "__main__":
    unittest.main()
