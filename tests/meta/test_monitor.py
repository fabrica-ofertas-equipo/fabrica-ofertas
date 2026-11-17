"""Pruebas de meta.monitor (B0-21): pausa por DISAPPROVED, sin recreación idéntica, congelación a los 2 en 7 días."""
import unittest
from datetime import datetime, timezone

from engine.transporte import TransporteFixture
from meta import monitor
from meta.cliente import ClienteMeta

_CAMPAIGN_ID, _AD_OK, _AD_MALO = "1111111111", "2222222222", "3333333333"


def _ids_meta() -> dict:
    return {"campaign_id": _CAMPAIGN_ID, "adset_ids": ["4444444444"], "ad_ids": [_AD_OK, _AD_MALO]}


def _cliente(reglas: list[dict]) -> tuple[ClienteMeta, TransporteFixture]:
    transporte = TransporteFixture(reglas)
    return ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4), transporte


def _regla(metodo: str, object_id: str, cuerpo: dict) -> dict:
    return {"metodo": metodo, "url_prefijo": f"https://graph.facebook.com/v21.0/{object_id}", "cuerpo": cuerpo}


def _reglas_lectura(estado_malo: str = "DISAPPROVED") -> list[dict]:
    return [
        _regla("GET", _CAMPAIGN_ID, {"id": _CAMPAIGN_ID, "effective_status": "ACTIVE"}),
        _regla("GET", _AD_OK, {"id": _AD_OK, "effective_status": "ACTIVE"}),
        _regla("GET", _AD_MALO, {"id": _AD_MALO, "effective_status": estado_malo}),
    ]


def _ahora() -> datetime:
    return datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)


class PruebaDisapproved(unittest.TestCase):
    def test_anuncio_disapproved_se_pausa_y_abre_pedido_a_d6(self) -> None:
        reglas = _reglas_lectura() + [_regla("POST", _AD_MALO, {"success": True})]
        cliente, transporte = _cliente(reglas)
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=24, ahora=_ahora,
            gasto_real_minor=1000, gasto_esperado_minor=1200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=100, vistas_landing=90, rechazos_congelar=2,
        )
        self.assertEqual(resultado.pausados, (_AD_MALO,))
        self.assertEqual(resultado.nuevos_rechazos, (_AD_MALO,))
        self.assertEqual(len(resultado.pedidos_d6), 1)
        self.assertEqual(resultado.pedidos_d6[0]["ad_id"], _AD_MALO)
        self.assertEqual(resultado.pedidos_d6[0]["destino"], "D6/X1")
        self.assertEqual(resultado.rechazos_7d, 1)
        self.assertFalse(resultado.congelar)
        posts = transporte.llamadas_a("POST")
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0].url.startswith(f"https://graph.facebook.com/v21.0/{_AD_MALO}"))

    def test_anuncio_sano_no_se_toca(self) -> None:
        cliente, transporte = _cliente(_reglas_lectura(estado_malo="ACTIVE"))
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=1, ahora=_ahora,
            gasto_real_minor=100, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
        )
        self.assertEqual(resultado.pausados, ())
        self.assertEqual(len(transporte.llamadas_a("POST")), 0)

    def test_mismo_anuncio_rechazado_no_se_vuelve_a_pausar_ni_a_contar(self) -> None:
        # ya estaba en ad_ids_rechazados_previos (de una corrida anterior): no se reenvía el mismo hash.
        cliente, transporte = _cliente(_reglas_lectura())
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=24, ahora=_ahora,
            gasto_real_minor=100, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
            ad_ids_rechazados_previos=(_AD_MALO,),
            historial_rechazos=[{"ad_id": _AD_MALO, "en": "2026-11-09T12:00:00Z"}],
        )
        self.assertEqual(resultado.pausados, ())
        self.assertEqual(resultado.nuevos_rechazos, ())
        self.assertEqual(len(resultado.pedidos_d6), 0)
        self.assertEqual(resultado.rechazos_7d, 1)  # sigue contando dentro de la ventana de 7 días
        self.assertEqual(len(transporte.llamadas_a("POST")), 0)

    def test_dos_rechazos_en_siete_dias_congelan(self) -> None:
        cliente, transporte = _cliente(_reglas_lectura() + [_regla("POST", _AD_MALO, {"success": True})])
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=24, ahora=_ahora,
            gasto_real_minor=100, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
            historial_rechazos=[{"ad_id": "9999999999", "en": "2026-11-06T12:00:00Z"}],  # otro anuncio, dentro de 7 días
        )
        self.assertEqual(resultado.rechazos_7d, 2)
        self.assertTrue(resultado.congelar)

    def test_rechazo_fuera_de_la_ventana_de_siete_dias_no_cuenta(self) -> None:
        cliente, transporte = _cliente(_reglas_lectura() + [_regla("POST", _AD_MALO, {"success": True})])
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=24, ahora=_ahora,
            gasto_real_minor=100, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
            historial_rechazos=[{"ad_id": "9999999999", "en": "2026-10-20T12:00:00Z"}],  # hace más de 7 días
        )
        self.assertEqual(resultado.rechazos_7d, 1)
        self.assertFalse(resultado.congelar)


class PruebaTraspaso(unittest.TestCase):
    def test_lanzamiento_estable_solo_a_las_72h_sin_anomalias_ni_rechazos(self) -> None:
        cliente, _ = _cliente(_reglas_lectura(estado_malo="ACTIVE"))
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=72, ahora=_ahora,
            gasto_real_minor=100, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
        )
        self.assertTrue(resultado.traspaso["lanzamiento_estable"])
        self.assertEqual(resultado.traspaso["anomalias"], [])

    def test_lanzamiento_no_estable_antes_de_72h_aunque_todo_bien(self) -> None:
        cliente, _ = _cliente(_reglas_lectura(estado_malo="ACTIVE"))
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=24, ahora=_ahora,
            gasto_real_minor=100, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
        )
        self.assertFalse(resultado.traspaso["lanzamiento_estable"])

    def test_gasto_sobre_esperado_es_anomalia(self) -> None:
        cliente, _ = _cliente(_reglas_lectura(estado_malo="ACTIVE"))
        resultado = monitor.monitorear(
            oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=72, ahora=_ahora,
            gasto_real_minor=500, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
            adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
        )
        self.assertIn("gasto-sobre-esperado", resultado.traspaso["anomalias"])
        self.assertFalse(resultado.traspaso["lanzamiento_estable"])

    def test_ventana_invalida_rechazada(self) -> None:
        cliente, _ = _cliente(_reglas_lectura(estado_malo="ACTIVE"))
        with self.assertRaises(ValueError):
            monitor.monitorear(
                oferta_id="OF-202611-01", cliente=cliente, ids_meta=_ids_meta(), ventana_h=2, ahora=_ahora,
                gasto_real_minor=100, gasto_esperado_minor=200, moneda="EUR", estado_aprendizaje="LEARNING",
                adid_capturado_bp=9500, clics_enlace=10, vistas_landing=9, rechazos_congelar=2,
            )


if __name__ == "__main__":
    unittest.main()
