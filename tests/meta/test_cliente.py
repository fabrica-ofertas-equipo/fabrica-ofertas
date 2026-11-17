"""Pruebas de meta.cliente.ClienteMeta: appsecret_proof, reintento ante 613, ritmo de ediciones."""
import unittest
from datetime import datetime, timedelta, timezone

from engine.errores import ErrorExterno, ErrorLimite, ErrorValidacion
from engine.transporte import TransporteFixture
from meta.cliente import ClienteMeta


def _reloj(inicio: datetime):
    estado = {"t": inicio}

    def ahora() -> datetime:
        return estado["t"]

    def avanzar(segundos: float) -> None:
        estado["t"] = estado["t"] + timedelta(seconds=segundos)

    return ahora, avanzar


class PruebaAppsecretProof(unittest.TestCase):
    def test_todas_las_llamadas_llevan_appsecret_proof_y_token(self) -> None:
        transporte = TransporteFixture([{"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/123", "cuerpo": {"id": "123", "name": "x"}}])
        cliente = ClienteMeta(transporte, token="TOKEN", app_secret="SECRETO", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        cliente.leer("123", campos=("id", "name"))
        llamada = transporte.llamadas[0]
        self.assertIn("access_token=TOKEN", llamada.url)
        self.assertIn("appsecret_proof=", llamada.url)
        import hashlib
        import hmac as _hmac
        esperado = _hmac.new(b"SECRETO", b"TOKEN", hashlib.sha256).hexdigest()
        self.assertIn(f"appsecret_proof={esperado}", llamada.url)

    def test_construir_sin_token_falla(self) -> None:
        with self.assertRaises(ErrorValidacion):
            ClienteMeta(TransporteFixture(), token="", app_secret="s", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)


class PruebaReintento613(unittest.TestCase):
    def test_reintenta_ante_613_y_al_final_responde(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com", "estado": 400, "cuerpo": {"error": {"code": 613, "message": "rate limit"}}, "veces": 2},
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com", "cuerpo": {"id": "9", "name": "ok"}},
        ])
        dormidas: list[float] = []
        cliente = ClienteMeta(
            transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4,
            dormir=dormidas.append, espera_613_base_s=1,
        )
        resultado = cliente.leer("9", campos=("id", "name"))
        self.assertEqual(resultado["id"], "9")
        self.assertEqual(dormidas, [1, 2])  # espera exponencial: base * 2**intento

    def test_613_mas_alla_del_tope_de_reintentos_falla(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com", "estado": 400, "cuerpo": {"error": {"code": 613, "message": "rate limit"}}, "veces": 0},
        ])
        cliente = ClienteMeta(
            transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4,
            dormir=lambda s: None, reintentos_613_max=2,
        )
        with self.assertRaises(ErrorExterno):
            cliente.leer("9", campos=("id",))

    def test_error_distinto_de_613_no_reintenta(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com", "estado": 400, "cuerpo": {"error": {"code": 100, "message": "invalid parameter"}}},
        ])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4, dormir=lambda s: None)
        with self.assertRaises(ErrorExterno):
            cliente.leer("9", campos=("id",))
        self.assertEqual(len(transporte.llamadas), 1)


class PruebaRitmo(unittest.TestCase):
    def test_editar_dos_veces_antes_de_30s_falla(self) -> None:
        ahora, avanzar = _reloj(datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc))
        transporte = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://graph.facebook.com", "cuerpo": {"success": True}, "veces": 0}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4, ahora=ahora)
        cliente.cambiar_estado("111", "PAUSED")
        avanzar(10)
        with self.assertRaises(ErrorLimite):
            cliente.cambiar_estado("111", "ACTIVE")

    def test_editar_tras_30s_funciona(self) -> None:
        ahora, avanzar = _reloj(datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc))
        transporte = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://graph.facebook.com", "cuerpo": {"success": True}, "veces": 0}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4, ahora=ahora)
        cliente.cambiar_estado("111", "PAUSED")
        avanzar(31)
        cliente.cambiar_estado("111", "ACTIVE")  # no debe lanzar

    def test_quinto_cambio_en_la_hora_falla_con_tope_de_4(self) -> None:
        ahora, avanzar = _reloj(datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc))
        transporte = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://graph.facebook.com", "cuerpo": {"success": True}, "veces": 0}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=0, max_cambios_presupuesto_por_hora=4, ahora=ahora)
        for _ in range(4):
            cliente.cambiar_estado("222", "PAUSED")
            avanzar(60)
        with self.assertRaises(ErrorLimite):
            cliente.cambiar_estado("222", "ACTIVE")

    def test_ritmo_es_por_objeto_no_global(self) -> None:
        ahora, avanzar = _reloj(datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc))
        transporte = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://graph.facebook.com", "cuerpo": {"success": True}, "veces": 0}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4, ahora=ahora)
        cliente.cambiar_estado("obj-a", "PAUSED")
        cliente.cambiar_estado("obj-b", "PAUSED")  # objeto distinto: no debe lanzar aunque sea el mismo instante

    def test_lecturas_no_cuentan_para_el_ritmo(self) -> None:
        ahora, _ = _reloj(datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc))
        transporte = TransporteFixture([{"metodo": "GET", "url_prefijo": "https://graph.facebook.com", "cuerpo": {"id": "1"}, "veces": 0}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4, ahora=ahora)
        cliente.leer("1", campos=("id",))
        cliente.leer("1", campos=("id",))  # dos lecturas inmediatas: no es una edición


class PruebaCrearYListar(unittest.TestCase):
    def test_crear_devuelve_id(self) -> None:
        transporte = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://graph.facebook.com/v21.0/act_1/campaigns", "cuerpo": {"id": "999"}}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        resultado = cliente.crear("act_1/campaigns", {"name": "x", "status": "PAUSED"})
        self.assertEqual(resultado["id"], "999")

    def test_crear_sin_id_en_la_respuesta_falla(self) -> None:
        transporte = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://graph.facebook.com", "cuerpo": {"success": True}}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        with self.assertRaises(ErrorExterno):
            cliente.crear("act_1/campaigns", {"name": "x"})

    def test_buscar_por_prefijo_encuentra_reutilizable(self) -> None:
        transporte = TransporteFixture([{"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/act_1/campaigns",
                                         "cuerpo": {"data": [{"id": "1", "name": "OTRA_X"}, {"id": "2", "name": "OF-202611-01_TEST_x"}]}}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        encontrado = cliente.buscar_por_prefijo("act_1/campaigns", "OF-202611-01_TEST_")
        self.assertEqual(encontrado["id"], "2")

    def test_buscar_por_prefijo_sin_coincidencia_es_none(self) -> None:
        transporte = TransporteFixture([{"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/act_1/campaigns", "cuerpo": {"data": []}}])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        self.assertIsNone(cliente.buscar_por_prefijo("act_1/campaigns", "OF-202611-01_TEST_"))


if __name__ == "__main__":
    unittest.main()
