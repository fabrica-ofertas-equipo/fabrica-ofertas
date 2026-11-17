"""Pruebas de meta.payloads: presupuesto (N06/N11, Anexo A3 §3.4 con tarifa y n_anuncios) y payloads
de creación (Marketing API, todo PAUSED).

A6 (ola 2, B5b): ``calcular_presupuesto`` ahora aplica ``tarifa_meta_bp`` (nunca un literal: siempre
viene de ``economia.entradas_usadas.tarifa_meta_bp``) y calcula ``n_anuncios``/``total`` desde
``cpa_max``/``cpa_esperado``/``k_corte``/``n_dec`` en vez de recibir un ``gasto_test_plan_minor`` ya
hecho: las pruebas viejas que pasaban ese parámetro se reemplazan por las de abajo (ver README
«Decisiones»/informe de la noche).
"""
import unittest
from datetime import datetime, timezone

from engine.errores import ErrorLimite, ErrorValidacion
from engine.limites import Limites
from engine.parametros import Parametros
from meta import payloads


def _limites(**over: object) -> Limites:
    datos = {
        "moneda_limites": "EUR", "gasto_total_test_por_oferta": 100000, "perdida_max_test_por_oferta": 80000,
        "factor_techo_teorico_diario": "1.75",
    }
    datos.update(over)
    return Limites(datos=datos, entorno="prueba")


def _parametros(*, spend_cap_factor: str = "1.10", spend_cap_minimo: dict | None = None, k_corte: int = 3,
                n_dec: int = 15, n_anuncios_tope: int = 6, n_anuncios_min: int = 3) -> Parametros:
    campana: dict = {
        "spend_cap_factor": {"valor": spend_cap_factor}, "n_anuncios_tope": {"valor": n_anuncios_tope},
        "n_anuncios_min": {"valor": n_anuncios_min},
    }
    if spend_cap_minimo is not None:
        campana["spend_cap_minimo_meta"] = {"valor": spend_cap_minimo}
    testeo = {"k_corte": {"valor": k_corte}, "n_dec": {"valor": n_dec}}
    return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {"campana": campana, "testeo": testeo}})


class PruebaCalcularPresupuesto(unittest.TestCase):
    def setUp(self) -> None:
        self.inicio = datetime(2026, 11, 10, 0, 0, 0, tzinfo=timezone.utc)

    def _calcular(self, **over: object) -> dict:
        base = dict(
            moneda="EUR", dias=10, limites=_limites(), parametros=_parametros(), spend_cap_minimo_meta_minor=None,
            inicio=self.inicio, tarifa_meta_bp=0, cpa_max_minor=5000, cpa_esperado_minor=1, n_anuncios_paquete=1,
        )
        base.update(over)
        return payloads.calcular_presupuesto(**base)

    def test_total_test_es_el_minimo_del_plan_y_del_tope(self) -> None:
        # n_anuncios=1, k_corte=1 x cpa_max 5000 = corte 5000; n_dec(1) x cpa_esperado(1)=1 <= corte -> total=5000.
        p = self._calcular(parametros=_parametros(k_corte=1, n_dec=1, n_anuncios_tope=1, n_anuncios_min=1), dias=10)
        self.assertEqual(p["diario"], 500)
        self.assertEqual(p["total_test"], 5000)
        self.assertEqual(p["total_test"], p["diario"] * p["dias"])

    def test_max_teorico_diario_redondea_hacia_arriba(self) -> None:
        # n_anuncios=1, k_corte=1, cpa_max=1001 -> corte=1001; n_dec=1 x cpa_esperado=1000 -> validar=1000 <= corte.
        p = self._calcular(
            parametros=_parametros(k_corte=1, n_dec=1, n_anuncios_tope=1, n_anuncios_min=1), dias=1,
            cpa_max_minor=1001, cpa_esperado_minor=1000, n_anuncios_paquete=1,
        )
        # diario = 1001 (1 día); 1,75 x 1001 = 1751,75 -> techo 1752
        self.assertEqual(p["diario"], 1001)
        self.assertEqual(p["max_teorico_diario"], 1752)

    def test_n_anuncios_se_reduce_por_la_tarifa_hasta_entrar_en_total_visible_max(self) -> None:
        # techo_total=12000; spend_cap_factor=1.0; tarifa=5000bp (50 %) -> total_visible_max=floor(12000/1.5)=8000.
        # k_corte=3, cpa_max=1000: n=4 (4x3000=12000) no entra; n=3 (9000) no entra; n=2 (6000) sí: se reduce a 2.
        p = self._calcular(
            limites=_limites(gasto_total_test_por_oferta=12000, perdida_max_test_por_oferta=12000),
            parametros=_parametros(spend_cap_factor="1.0", k_corte=3, n_dec=1, n_anuncios_tope=5, n_anuncios_min=2),
            tarifa_meta_bp=5000, cpa_max_minor=1000, cpa_esperado_minor=500, n_anuncios_paquete=4, dias=3,
        )
        self.assertEqual(p["n_anuncios"], 2)
        self.assertEqual(p["corte"], 6000)
        self.assertFalse(p["solo_refuta"])

    def test_solo_refuta_cuando_validar_no_entra_en_total_visible_max(self) -> None:
        # total_visible_max=10000 (techo 10000, factor 1.0, tarifa 0); corte=900 (3 x 300 x 1); validar=15000>10000.
        p = self._calcular(
            limites=_limites(gasto_total_test_por_oferta=10000, perdida_max_test_por_oferta=10000),
            parametros=_parametros(spend_cap_factor="1.0", k_corte=3, n_dec=50, n_anuncios_tope=3, n_anuncios_min=1),
            tarifa_meta_bp=0, cpa_max_minor=100, cpa_esperado_minor=300, n_anuncios_paquete=3, dias=9,
        )
        self.assertTrue(p["solo_refuta"])
        self.assertEqual(p["total_test"], 900)  # = corte, no validar: un test así refuta pero no valida
        self.assertEqual(p["techo_necesario_para_validar"], 15000)

    def test_tarifa_meta_bp_entra_en_el_facturado_plan(self) -> None:
        p = self._calcular(
            limites=_limites(gasto_total_test_por_oferta=100000, perdida_max_test_por_oferta=100000),
            parametros=_parametros(spend_cap_factor="1.0", k_corte=3, n_dec=1, n_anuncios_tope=5, n_anuncios_min=1),
            tarifa_meta_bp=1000, cpa_max_minor=1000, cpa_esperado_minor=1000, n_anuncios_paquete=5, dias=5,
        )
        self.assertEqual(p["tarifa_meta_bp"], 1000)
        self.assertEqual(p["total_test"], 15000)
        self.assertEqual(p["facturado_plan"], 16500)  # techo(15000 x 1,10)

    def test_n_anuncios_min_no_alcanza_lanza_errorlimite(self) -> None:
        # total_visible_max=4000 (techo 4000, factor 1.0); n_min=2 x k_corte(3) x cpa_max(1000)=6000 > 4000.
        with self.assertRaises(ErrorLimite):
            self._calcular(
                limites=_limites(gasto_total_test_por_oferta=4000, perdida_max_test_por_oferta=4000),
                parametros=_parametros(spend_cap_factor="1.0", k_corte=3, n_dec=1, n_anuncios_tope=5, n_anuncios_min=2),
                tarifa_meta_bp=0, cpa_max_minor=1000, cpa_esperado_minor=100, n_anuncios_paquete=5, dias=4,
            )

    def test_spend_cap_bajo_el_minimo_de_meta_usa_candado_alternativo(self) -> None:
        p = self._calcular(
            parametros=_parametros(k_corte=1, n_dec=1, n_anuncios_tope=1, n_anuncios_min=1),
            spend_cap_minimo_meta_minor=10000, cpa_max_minor=5000, cpa_esperado_minor=1, n_anuncios_paquete=1, dias=10,
        )
        self.assertIsNone(p["spend_cap"])
        self.assertIsNotNone(p["candado_alternativo"])
        self.assertGreaterEqual(p["candado_alternativo"]["lifetime_budget"], p["total_test"])
        self.assertEqual(p["candado_alternativo"]["tipo"], "stop_time_lifetime_budget")
        self.assertTrue(p["candado_alternativo"]["stop_time"].endswith("Z"))

    def test_spend_cap_por_encima_del_minimo_no_usa_candado(self) -> None:
        p = self._calcular(
            parametros=_parametros(k_corte=1, n_dec=1, n_anuncios_tope=1, n_anuncios_min=1),
            spend_cap_minimo_meta_minor=1000, cpa_max_minor=5000, cpa_esperado_minor=1, n_anuncios_paquete=1, dias=10,
        )
        self.assertIsNotNone(p["spend_cap"])
        self.assertIsNone(p["candado_alternativo"])

    def test_decimales_vienen_del_exponente_iso(self) -> None:
        p = self._calcular(
            moneda="JPY", limites=_limites(moneda_limites="JPY"),
            parametros=_parametros(k_corte=1, n_dec=1, n_anuncios_tope=1, n_anuncios_min=1),
            cpa_max_minor=5000, cpa_esperado_minor=1, n_anuncios_paquete=1, dias=10,
        )
        self.assertEqual(p["decimales"], 0)

    def test_dias_invalido_rechazado(self) -> None:
        with self.assertRaises(ErrorValidacion):
            self._calcular(dias=0)

    def test_tarifa_negativa_rechazada(self) -> None:
        with self.assertRaises(ErrorValidacion):
            self._calcular(tarifa_meta_bp=-1)

    def test_falta_limite_critico_es_errorlimite(self) -> None:
        lim = Limites(datos={"moneda_limites": "EUR"}, entorno="prueba")
        with self.assertRaises(ErrorLimite):
            self._calcular(limites=lim)


class PruebaPayloadCampana(unittest.TestCase):
    def _campana(self, spend_cap: int | None = 5500) -> dict:
        return {
            "objetivo": "VENTAS", "nombres": {"campana": "OF-202611-01_TEST_VENTAS_CBO_20261110"},
            "special_ad_categories": [],
            "presupuesto": {"moneda": "EUR", "spend_cap": spend_cap, "diario": 500},
        }

    def test_payload_siempre_paused(self) -> None:
        payload = payloads.payload_campana(self._campana())
        self.assertEqual(payload["status"], "PAUSED")

    def test_payload_incluye_spend_cap_convertido(self) -> None:
        payload = payloads.payload_campana(self._campana(spend_cap=5500))
        self.assertEqual(payload["spend_cap"], 5500)  # EUR: offset 100 / exponente 2 -> sin cambio

    def test_payload_sin_spend_cap_no_incluye_la_clave(self) -> None:
        payload = payloads.payload_campana(self._campana(spend_cap=None))
        self.assertNotIn("spend_cap", payload)

    def test_objetivo_desconocido_rechazado(self) -> None:
        campana = self._campana()
        campana["objetivo"] = "OTRO"
        with self.assertRaises(ErrorValidacion):
            payloads.payload_campana(campana)


class PruebaPayloadConjuntoYAnuncio(unittest.TestCase):
    def _campana(self) -> dict:
        return {
            "nombres": {"conjunto": "amplia_automaticas_es-ES"}, "evento_optimizacion": "PURCHASE",
            "paises": ["ES"], "ubicaciones": "automaticas",
            "audiencia": {"edad_min": 18, "edad_max": 65, "genero": "todos", "intereses": []},
            "presupuesto": {"moneda": "EUR", "diario": 500, "candado_alternativo": None},
        }

    def test_conjunto_con_daily_budget_cuando_no_hay_candado(self) -> None:
        payload = payloads.payload_conjunto(self._campana(), campaign_id="999", pixel_id="PX1")
        self.assertEqual(payload["status"], "PAUSED")
        self.assertEqual(payload["daily_budget"], 500)
        self.assertEqual(payload["campaign_id"], "999")
        self.assertEqual(payload["promoted_object"]["pixel_id"], "PX1")

    def test_conjunto_con_candado_usa_lifetime_budget(self) -> None:
        campana = self._campana()
        campana["presupuesto"]["candado_alternativo"] = {"lifetime_budget": 5000, "stop_time": "2026-11-20T00:00:00Z"}
        payload = payloads.payload_conjunto(campana, campaign_id="999", pixel_id="PX1")
        self.assertEqual(payload["lifetime_budget"], 5000)
        self.assertNotIn("daily_budget", payload)
        self.assertEqual(payload["end_time"], "2026-11-20T00:00:00Z")

    def test_anuncio_referencia_creativo_y_conjunto(self) -> None:
        payload = payloads.payload_anuncio({"ad_name": "concepto_video_hook_v1"}, adset_id="777", creative_id="888")
        self.assertEqual(payload, {"name": "concepto_video_hook_v1", "adset_id": "777", "status": "PAUSED", "creative": {"creative_id": "888"}})


if __name__ == "__main__":
    unittest.main()
