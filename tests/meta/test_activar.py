"""Pruebas de meta.activar (N12, B0-13): 5 negativos + 1 positivo en modo=fixture, «falla el segundo
POST» y (A5, ola 2 B5b) la re-lectura del estado vivo contra ``campana.json`` sellado: una prueba roja
sembrada por cada campo (presupuesto, evento de optimización, targeting, creativo, DSA).

Reutiliza (solo lectura) ``tests.engine.apoyo`` para construir una raíz de empresa en estado verde: los 7
pasos reales de ``engine.guard`` ya tienen su batería dedicada, una prueba por paso, en
``tests/engine/test_guard.py`` (con reloj y entorno inyectados); estas pruebas verifican la parte propia
de ``meta.activar``: el sello de X1 (TOCTOU), la comparación de estado vivo (A5) y la secuencia de
activación/pausa sobre ``ClienteMeta``.
"""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from engine.errores import ErrorBloqueado, ErrorExterno
from engine.guard import EstadoCuenta
from engine.limites import CampanaActiva
from engine.transporte import TransporteFixture
from meta import activar
from meta.cliente import ClienteMeta
from tests.engine.apoyo import HASH_CONFIG, OFERTA, PruebaBase, crear_empresa

_CAMPAIGN_ID, _ADSET_ID, _AD_ID, _CREATIVE_ID = "1111111111", "2222222222", "3333333333", "4444444444"


def _ids_meta() -> dict:
    return {"campaign_id": _CAMPAIGN_ID, "adset_ids": [_ADSET_ID], "ad_ids": [_AD_ID], "creative_ids": [_CREATIVE_ID]}


def _campana() -> dict:
    """``campana.json`` mínimo (sellado) cuyo estado vivo «correcto» coinciden con :func:`_valores_vivos`."""
    return {
        "oferta_id": OFERTA, "objetivo": "VENTAS", "evento_optimizacion": "PURCHASE",
        "special_ad_categories": [], "paises": ["ES"], "ubicaciones": "automaticas",
        "audiencia": {"edad_min": 18, "edad_max": 65, "genero": "todos", "intereses": []},
        "presupuesto": {"moneda": "EUR", "diario": 500, "spend_cap": 5500, "candado_alternativo": None},
        "nombres": {"campana": "OF-202611-01_TEST_VENTAS_CBO_20261110", "conjunto": "amplia_automaticas_es-ES"},
        "anuncios": [{"ad_name": "ad1"}],
    }


_TARGETING_ESPERADO = {
    "geo_locations": {"countries": ["ES"]}, "age_min": 18, "age_max": 65,
    "publisher_platforms": ["facebook", "instagram"],
}


def _valores_vivos() -> dict:
    """Estado vivo que coincide EXACTAMENTE con :func:`_campana` (caso positivo)."""
    return {
        "campana": {"id": _CAMPAIGN_ID, "spend_cap": 5500, "special_ad_categories": []},
        "conjunto": {
            "id": _ADSET_ID, "daily_budget": 500, "optimization_goal": "OFFSITE_CONVERSIONS",
            "targeting": copy.deepcopy(_TARGETING_ESPERADO), "promoted_object": {"custom_event_type": "PURCHASE"},
        },
        "anuncio": {"id": _AD_ID, "creative": {"id": _CREATIVE_ID}},
    }


def _sello(*, hash_config: str = HASH_CONFIG, object_ids: set | None = None) -> dict:
    return {
        "artefacto_sha256": hash_config, "emitido_en": "2026-11-09T06:00:00Z", "vigencia_hasta": "2026-11-10T06:00:00Z",
        "object_ids": sorted(object_ids if object_ids is not None else activar.ids_de(_ids_meta())),
    }


def _verificar_sello_fake(sello: dict | None):
    """«Fake de verificar_sello» (compliance aún no existe, ola 1 de B5)."""
    return lambda clave_sello, ahora: sello


def _cuenta() -> EstadoCuenta:
    nueva = CampanaActiva(oferta_id=OFERTA, campaign_id="c1", max_teorico_diario_minor=5000, spend_cap_restante_minor=0,
                          moneda="EUR", perdida_acumulada_minor=0)
    return EstadoCuenta(gasto_vitalicio_minor=0, nueva=nueva, ediciones_recientes=(), ultimo_aumento=None)


def _regla(metodo: str, object_id: str, cuerpo: dict, *, estado: int = 200, veces: int = 1) -> dict:
    return {"metodo": metodo, "url_prefijo": f"https://graph.facebook.com/v21.0/{object_id}", "estado": estado, "cuerpo": cuerpo, "veces": veces}


def _reglas_arbol_vivo() -> list[dict]:
    return [
        _regla("GET", _CAMPAIGN_ID, {"id": _CAMPAIGN_ID}),
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_CAMPAIGN_ID}/adsets", "cuerpo": {"data": [{"id": _ADSET_ID}]}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_CAMPAIGN_ID}/ads", "cuerpo": {"data": [{"id": _AD_ID}]}},
    ]


def _reglas_estado_vivo(*, overrides: dict | None = None) -> list[dict]:
    """Las 3 lecturas de :func:`meta.activar.leer_estado_vivo` (A5): una por objeto, tras el árbol vivo.

    ``overrides`` puede traer ``{"campana": {...}, "conjunto": {...}, "anuncio": {...}}`` para sembrar
    una divergencia (una prueba roja por campo).
    """
    valores = _valores_vivos()
    for clave, cambios in (overrides or {}).items():
        valores[clave].update(cambios)
    return [
        _regla("GET", _CAMPAIGN_ID, valores["campana"]),
        _regla("GET", _ADSET_ID, valores["conjunto"]),
        _regla("GET", _AD_ID, valores["anuncio"]),
    ]


def _reglas_activacion_exitosa(*, overrides_estado_vivo: dict | None = None) -> list[dict]:
    reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo(overrides=overrides_estado_vivo)
    for object_id in (_AD_ID, _ADSET_ID, _CAMPAIGN_ID):
        reglas.append(_regla("GET", object_id, {"id": object_id, "effective_status": "PAUSED"}))
        reglas.append(_regla("POST", object_id, {"success": True}))
        reglas.append(_regla("GET", object_id, {"id": object_id, "effective_status": "ACTIVE"}))
    return reglas


class BaseActivar(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")

    def _activar(self, *, transporte: TransporteFixture, sello: dict | None, hash_config: str = HASH_CONFIG,
                ids_meta: dict | None = None, campana: dict | None = None):
        cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
        return activar.activar(
            oferta_id=OFERTA, campana=campana if campana is not None else _campana(), ids_meta=ids_meta or _ids_meta(),
            hash_config=hash_config, clave_sello=hash_config, verificar_sello=_verificar_sello_fake(sello), cliente=cliente,
            monto_minor=5000, moneda="EUR", cuenta=_cuenta(), ahora=self.emp.reloj, simulacion=True,
            transporte_guard=transporte, env=self.emp.env, raiz=self.emp.raiz,
        )


class PruebaCincoNegativos(BaseActivar):
    def test_sin_sello_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(), sello=None)
        self.assertIn("sin sello", cm.exception.mensaje)

    def test_con_hash_distinto_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        sello = _sello(hash_config="sha256:" + "ff" * 32)  # no coincide con hash_config de la activación
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(), sello=sello)
        self.assertIn("sello", cm.exception.mensaje.lower())

    def test_con_object_ids_de_mas_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        # el sello solo aprobó la campaña y el conjunto: ids_meta trae además un anuncio no sellado.
        sello = _sello(object_ids={_CAMPAIGN_ID, _ADSET_ID})
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(), sello=sello)
        self.assertIn("sello", cm.exception.mensaje.lower())

    def test_sin_firma_rechaza(self) -> None:
        # no se firma ninguna orden: el paso 7 de guard (aprobación) bloquea.
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(), sello=_sello())
        self.assertIn("orden firmada", cm.exception.mensaje)

    def test_con_pausa_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        (self.emp.raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(), sello=_sello())
        self.assertIn("PAUSA", cm.exception.mensaje)


class PruebaCasoPositivo(BaseActivar):
    def test_activa_en_modo_fixture_anuncios_conjunto_campana(self) -> None:
        self.emp.firmar_orden("activar_campana")
        transporte = TransporteFixture(_reglas_activacion_exitosa())
        resultado = self._activar(transporte=transporte, sello=_sello())
        self.assertEqual(resultado.campaign_id, _CAMPAIGN_ID)
        self.assertEqual(resultado.adset_ids, (_ADSET_ID,))
        self.assertEqual(resultado.ad_ids, (_AD_ID,))
        self.assertIn("sin --creativos", " ".join(resultado.avisos))  # no se pasó payloads_creativo
        posts = transporte.llamadas_a("POST")
        self.assertEqual(len(posts), 3)
        # el orden es anuncios -> conjunto -> campaña (la campaña, al final).
        self.assertTrue(posts[0].url.startswith(f"https://graph.facebook.com/v21.0/{_AD_ID}"))
        self.assertTrue(posts[1].url.startswith(f"https://graph.facebook.com/v21.0/{_ADSET_ID}"))
        self.assertTrue(posts[2].url.startswith(f"https://graph.facebook.com/v21.0/{_CAMPAIGN_ID}"))

    def test_objeto_ya_activo_es_no_op(self) -> None:
        self.emp.firmar_orden("activar_campana")
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo()
        for object_id in (_AD_ID, _ADSET_ID, _CAMPAIGN_ID):
            reglas.append(_regla("GET", object_id, {"id": object_id, "effective_status": "ACTIVE"}, veces=0))
        transporte = TransporteFixture(reglas)
        self._activar(transporte=transporte, sello=_sello())
        self.assertEqual(len(transporte.llamadas_a("POST")), 0)


class PruebaEstadoVivo(BaseActivar):
    """A5: la configuración viva de Meta debe coincidir, campo por campo, con ``campana.json`` sellado."""

    def test_presupuesto_spend_cap_distinto_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo(overrides={"campana": {"spend_cap": 9999}})
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(reglas), sello=_sello())
        self.assertIn("presupuesto.spend_cap", cm.exception.mensaje)

    def test_evento_optimizacion_distinto_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo(
            overrides={"conjunto": {"promoted_object": {"custom_event_type": "INITIATE_CHECKOUT"}}}
        )
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(reglas), sello=_sello())
        self.assertIn("evento_optimizacion", cm.exception.mensaje)

    def test_targeting_distinto_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        targeting_alterado = dict(_TARGETING_ESPERADO, age_max=45)
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo(overrides={"conjunto": {"targeting": targeting_alterado}})
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(reglas), sello=_sello())
        self.assertIn("targeting", cm.exception.mensaje)

    def test_creativo_distinto_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo(overrides={"anuncio": {"creative": {"id": "999999"}}})
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(reglas), sello=_sello())
        self.assertIn("creativo", cm.exception.mensaje)

    def test_dsa_special_ad_categories_distinto_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo(overrides={"campana": {"special_ad_categories": ["HOUSING"]}})
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(reglas), sello=_sello())
        self.assertIn("dsa", cm.exception.mensaje.lower())

    def test_diario_distinto_rechaza(self) -> None:
        self.emp.firmar_orden("activar_campana")
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo(overrides={"conjunto": {"daily_budget": 600}})
        with self.assertRaises(ErrorBloqueado) as cm:
            self._activar(transporte=TransporteFixture(reglas), sello=_sello())
        self.assertIn("presupuesto.diario", cm.exception.mensaje)


class PruebaFallaElSegundoPost(BaseActivar):
    def test_falla_el_segundo_post_pausa_lo_ya_activado(self) -> None:
        self.emp.firmar_orden("activar_campana")
        reglas = list(_reglas_arbol_vivo()) + _reglas_estado_vivo()
        # Anuncio: se activa bien (primer POST).
        reglas.append(_regla("GET", _AD_ID, {"id": _AD_ID, "effective_status": "PAUSED"}))
        reglas.append(_regla("POST", _AD_ID, {"success": True}))
        # Rollback del anuncio tras el fallo del conjunto: segunda llamada POST sobre el mismo anuncio (pausar).
        reglas.append(_regla("POST", _AD_ID, {"success": True}))
        # Conjunto: el segundo POST falla (error ajeno a 613, sin reintento).
        reglas.append(_regla("GET", _ADSET_ID, {"id": _ADSET_ID, "effective_status": "PAUSED"}))
        reglas.append({"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_ADSET_ID}", "estado": 400,
                       "cuerpo": {"error": {"code": 100, "message": "invalid parameter"}}})
        transporte = TransporteFixture(reglas)
        with self.assertRaises(ErrorExterno):
            self._activar(transporte=transporte, sello=_sello())
        posts = transporte.llamadas_a("POST")
        # activar anuncio, fallar conjunto, pausar anuncio (rollback) = 3 POST; nunca se llega a la campaña.
        self.assertEqual(len(posts), 3)
        self.assertTrue(posts[0].url.startswith(f"https://graph.facebook.com/v21.0/{_AD_ID}"))
        self.assertTrue(posts[1].url.startswith(f"https://graph.facebook.com/v21.0/{_ADSET_ID}"))
        self.assertTrue(posts[2].url.startswith(f"https://graph.facebook.com/v21.0/{_AD_ID}"))
        import urllib.parse as up

        self.assertEqual(dict(up.parse_qsl(posts[2].cuerpo.decode())).get("status"), "PAUSED")


if __name__ == "__main__":
    unittest.main()
