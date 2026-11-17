"""Pruebas de meta.crear: borrador PAUSED e idempotencia por nombre (B0-12)."""
import unittest
from urllib.parse import parse_qsl

from engine.errores import ErrorValidacion
from engine.transporte import TransporteFixture
from meta import crear
from meta.cliente import ClienteMeta

_AD_ACCOUNT = "act_100"


def _campana(oferta_id: str = "OF-202611-01") -> dict:
    return {
        "oferta_id": oferta_id, "estado": "borrador", "objetivo": "VENTAS", "evento_optimizacion": "PURCHASE",
        "paises": ["ES"], "ubicaciones": "automaticas", "special_ad_categories": [],
        "nombres": {"campana": f"{oferta_id}_TEST_VENTAS_CBO_20261110", "conjunto": "amplia_automaticas_es-ES", "anuncios": ["concepto_video_hook_v1"]},
        "audiencia": {"edad_min": 18, "edad_max": 65, "genero": "todos", "intereses": []},
        "presupuesto": {"moneda": "EUR", "diario": 500, "spend_cap": 5500, "candado_alternativo": None},
        "anuncios": [{"ad_name": "concepto_video_hook_v1", "concepto_id": "concepto", "asset_sha256": "sha256:" + "a" * 64, "claim_ids": []}],
    }


def _payloads_creativo() -> dict:
    return {"concepto_video_hook_v1": {"name": "concepto_video_hook_v1_creativo", "object_story_spec": {}}}


class PruebaCrearDesdeCero(unittest.TestCase):
    def test_todo_creado_en_paused_y_devuelve_los_ids(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"id": "1001"}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"id": "2001"}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives", "cuerpo": {"id": "3001"}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads", "cuerpo": {"id": "4001"}},
        ])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        resultado = crear.crear(oferta_id="OF-202611-01", campana=_campana(), cliente=cliente, ad_account_id=_AD_ACCOUNT,
                                pixel_id="PX1", payloads_creativo=_payloads_creativo())
        self.assertEqual(resultado.campaign_id, "1001")
        self.assertEqual(resultado.adset_ids, ["2001"])
        self.assertEqual(resultado.creative_ids, ["3001"])
        self.assertEqual(resultado.ad_ids, ["4001"])
        self.assertEqual(resultado.mapa_ad_name_a_id, {"concepto_video_hook_v1": "4001"})
        posts = transporte.llamadas_a("POST")
        self.assertEqual(len(posts), 4)
        # El creativo no lleva "status" (es un activo estático); campaña, conjunto y anuncio sí.
        con_estado = [dict(parse_qsl(p.cuerpo.decode("utf-8"))) for p in posts if f"{_AD_ACCOUNT}/adcreatives" not in p.url]
        self.assertEqual(len(con_estado), 3)
        for cuerpo in con_estado:
            self.assertEqual(cuerpo.get("status"), "PAUSED")

    def test_estado_de_campana_invalido_rechazado(self) -> None:
        cliente = ClienteMeta(TransporteFixture(), token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        campana = _campana()
        campana["estado"] = "activa"
        with self.assertRaises(ErrorValidacion):
            crear.crear(oferta_id="OF-202611-01", campana=campana, cliente=cliente, ad_account_id=_AD_ACCOUNT, pixel_id="PX1",
                       payloads_creativo=_payloads_creativo())

    def test_falta_payload_de_creativo_rechazado(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"id": "1001"}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"id": "2001"}},
        ])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        with self.assertRaises(ErrorValidacion):
            crear.crear(oferta_id="OF-202611-01", campana=_campana(), cliente=cliente, ad_account_id=_AD_ACCOUNT, pixel_id="PX1", payloads_creativo={})


class PruebaCrearEsIdempotente(unittest.TestCase):
    def test_reutiliza_por_prefijo_y_nombre_sin_crear_nada_nuevo(self) -> None:
        prefijo = crear.prefijo_test("OF-202611-01")
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns",
             "cuerpo": {"data": [{"id": "1001", "name": f"{prefijo}VENTAS_CBO_20261110"}]}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets",
             "cuerpo": {"data": [{"id": "2001", "name": f"{prefijo}amplia"}]}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives",
             "cuerpo": {"data": [{"id": "3001", "name": "concepto_video_hook_v1"}]}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads",
             "cuerpo": {"data": [{"id": "4001", "name": "concepto_video_hook_v1"}]}},
        ])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        resultado = crear.crear(oferta_id="OF-202611-01", campana=_campana(), cliente=cliente, ad_account_id=_AD_ACCOUNT,
                                pixel_id="PX1", payloads_creativo=_payloads_creativo())
        self.assertEqual(resultado.campaign_id, "1001")
        self.assertEqual(resultado.adset_ids, ["2001"])
        self.assertEqual(resultado.creative_ids, ["3001"])
        self.assertEqual(resultado.ad_ids, ["4001"])
        self.assertEqual(len(transporte.llamadas_a("POST")), 0)

    def test_nombre_exacto_no_colisiona_v1_con_v10(self) -> None:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"id": "1001"}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"data": []}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"id": "2001"}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives",
             "cuerpo": {"data": [{"id": "9999", "name": "concepto_video_hook_v10"}]}},  # NO debe reutilizarse para v1
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives", "cuerpo": {"id": "3001"}},
            {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads",
             "cuerpo": {"data": [{"id": "8888", "name": "concepto_video_hook_v10"}]}},
            {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads", "cuerpo": {"id": "4001"}},
        ])
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        resultado = crear.crear(oferta_id="OF-202611-01", campana=_campana(), cliente=cliente, ad_account_id=_AD_ACCOUNT,
                                pixel_id="PX1", payloads_creativo=_payloads_creativo())
        self.assertEqual(resultado.creative_ids, ["3001"])
        self.assertEqual(resultado.ad_ids, ["4001"])


if __name__ == "__main__":
    unittest.main()
