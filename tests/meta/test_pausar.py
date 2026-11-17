"""Pruebas de meta.pausar: idempotente, con relectura, y pausa de toda una cuenta."""
import unittest

from engine.errores import ErrorExterno
from engine.transporte import TransporteFixture
from meta import pausar
from meta.cliente import ClienteMeta


def _cliente(reglas: list[dict]) -> ClienteMeta:
    return ClienteMeta(TransporteFixture(reglas), token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)


class PruebaPausarCampana(unittest.TestCase):
    def test_pausa_una_campana_activa(self) -> None:
        cliente = _cliente([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"id": "1", "effective_status": "ACTIVE"}, "veces": 1},
            {"metodo": "POST", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"success": True}},
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"id": "1", "effective_status": "PAUSED"}, "veces": 1},
        ])
        self.assertTrue(pausar.pausar_campana(cliente, "1"))

    def test_campana_ya_pausada_es_no_op(self) -> None:
        cliente = _cliente([{"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"id": "1", "effective_status": "PAUSED"}}])
        self.assertFalse(pausar.pausar_campana(cliente, "1"))

    def test_si_sigue_activa_tras_pausar_es_error_externo(self) -> None:
        cliente = _cliente([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"id": "1", "effective_status": "ACTIVE"}, "veces": 0},
            {"metodo": "POST", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"success": True}},
        ])
        with self.assertRaises(ErrorExterno):
            pausar.pausar_campana(cliente, "1")


class PruebaPausarCuenta(unittest.TestCase):
    def test_pausa_solo_las_activas_de_la_cuenta(self) -> None:
        cliente = _cliente([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/act_1/campaigns",
             "cuerpo": {"data": [{"id": "1", "effective_status": "ACTIVE"}, {"id": "2", "effective_status": "PAUSED"}]}},
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"id": "1", "effective_status": "ACTIVE"}, "veces": 1},
            {"metodo": "POST", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"success": True}},
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/1", "cuerpo": {"id": "1", "effective_status": "PAUSED"}, "veces": 1},
        ])
        self.assertEqual(pausar.pausar_cuenta(cliente, "act_1"), ("1",))

    def test_pausar_cuentas_mapea_cada_cuenta(self) -> None:
        cliente = _cliente([
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/act_1/campaigns", "cuerpo": {"data": []}},
            {"metodo": "GET", "url_prefijo": "https://graph.facebook.com/v21.0/act_2/campaigns", "cuerpo": {"data": []}},
        ])
        self.assertEqual(pausar.pausar_cuentas(cliente, ["act_1", "act_2"]), {"act_1": (), "act_2": ()})


if __name__ == "__main__":
    unittest.main()
