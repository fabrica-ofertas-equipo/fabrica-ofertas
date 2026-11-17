"""Pruebas de ``landing.catalogo``: catálogo firmado ``oferta_id -> price_id`` (con ``ids_meta``).

Comando: ``.venv/bin/python -m unittest tests.landing.test_catalogo``
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import comun
from engine.errores import ErrorUso
from landing import catalogo as C
from landing import comun as lcomun

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "tests" / "fixtures" / "landing" / "oferta_minima"
CLAVE = b"clave-de-prueba-catalogo-no-real"


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="landing-catalogo-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = self.tmp / "ofertas" / "OF-209901-01"
        shutil.copytree(FIXTURE, self.d)
        self.checkout = lcomun.cargar_checkout(self.d)


class TestConstruirCatalogo(Base):
    def test_price_ids_vienen_de_checkout(self) -> None:
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        self.assertEqual("price_fixture_test_principal", cat["price_ids"]["principal"])
        self.assertNotIn("bump", cat["price_ids"])

    def test_ids_meta_vacios_sin_ids_meta_json(self) -> None:
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        self.assertEqual({"campaign_id": None, "adset_ids": [], "ad_ids": []}, cat["ids_meta"])

    def test_ids_meta_presentes_cuando_existe_el_archivo(self) -> None:
        ids = {
            "schema_version": "1.0.0", "oferta_id": "OF-209901-01", "ad_account_id": "act_12345",
            "campaign_id": "1000000000001", "adset_ids": ["1000000000002"], "ad_ids": ["1000000000003"],
            "creative_ids": ["1000000000004"], "creado_en": "2026-11-06T00:00:00Z", "hash_config": "sha256:" + "0" * 64,
        }
        comun.escribir_atomico(self.d / "07-campana" / "ids_meta.json", comun.json_canonico(ids))
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        self.assertEqual({"campaign_id": "1000000000001", "adset_ids": ["1000000000002"], "ad_ids": ["1000000000003"]}, cat["ids_meta"])

    def test_la_firma_verifica_con_la_misma_clave(self) -> None:
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        sin_firma = {k: v for k, v in cat.items() if k != "firma"}
        self.assertEqual(comun.firma_hmac(sin_firma, CLAVE), cat["firma"])

    def test_es_determinista_salvo_el_reloj(self) -> None:
        a = C.construir_catalogo(self.d, self.checkout, clave=CLAVE, ahora=lambda: comun.parsear_z("2026-11-06T00:00:00Z"))
        b = C.construir_catalogo(self.d, self.checkout, clave=CLAVE, ahora=lambda: comun.parsear_z("2026-11-06T00:00:00Z"))
        self.assertEqual(a, b)


class TestContratoCatalogo(Base):
    """El catálogo valida contra contratos/catalogo.schema.json 1.0.0 y la regla X48 del validador (CT-3 B1)."""

    def _problemas(self, cat: dict) -> list:
        from scripts import validar_esquemas as V
        return V.problemas_artefacto("catalogo", cat, clave=CLAVE)

    def test_valida_contra_el_esquema_sin_ids_meta(self) -> None:
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        self.assertEqual([], self._problemas(cat))

    def test_valida_con_ids_meta_reales(self) -> None:
        ids = {
            "schema_version": "1.0.0", "oferta_id": "OF-209901-01", "ad_account_id": "act_12345",
            "campaign_id": "1000000000001", "adset_ids": ["1000000000002"], "ad_ids": ["1000000000003"],
            "creative_ids": ["1000000000004"], "creado_en": "2026-11-06T00:00:00Z", "hash_config": "sha256:" + "0" * 64,
        }
        comun.escribir_atomico(self.d / "07-campana" / "ids_meta.json", comun.json_canonico(ids))
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        self.assertEqual([], self._problemas(cat))

    def test_urls_version_y_renuncia_salen_del_checkout_cuando_existen(self) -> None:
        co = dict(self.checkout)
        co["success_url"] = "https://ejemplo.test/gracias"
        co["return_url"] = "https://ejemplo.test/volver"
        co["compra"] = {"landing_version": "v3", "renuncia": {"requerido": True, "texto_version": "v2"}}
        cat = C.construir_catalogo(self.d, co, clave=CLAVE)
        self.assertEqual("https://ejemplo.test/gracias", cat["success_url"])
        self.assertEqual("https://ejemplo.test/volver", cat["return_url"])
        self.assertEqual("v3", cat["landing_version"])
        self.assertEqual({"requerido": True, "texto_version": "v2"}, cat["renuncia"])
        self.assertEqual([], self._problemas(cat))

    def test_sin_compra_no_se_inventan_landing_version_ni_renuncia(self) -> None:
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        for campo in ("landing_version", "renuncia", "success_url", "return_url"):
            self.assertNotIn(campo, cat)

    def test_renuncia_incompleta_se_omite(self) -> None:
        co = dict(self.checkout)
        co["compra"] = {"renuncia": {"requerido": True}}          # sin texto_version
        self.assertNotIn("renuncia", C.construir_catalogo(self.d, co, clave=CLAVE))
        co["compra"] = {"renuncia": {"requerido": "si", "texto_version": "v1"}}   # requerido no booleano
        self.assertNotIn("renuncia", C.construir_catalogo(self.d, co, clave=CLAVE))

    def test_no_emite_las_llaves_viejas_de_ids_meta(self) -> None:
        cat = C.construir_catalogo(self.d, self.checkout, clave=CLAVE)
        for vieja in ("campaign", "adset", "ad"):
            self.assertNotIn(vieja, cat["ids_meta"])

    def test_la_firma_cubre_los_campos_nuevos(self) -> None:
        co = dict(self.checkout)
        co["compra"] = {"landing_version": "v3"}
        a = C.construir_catalogo(self.d, co, clave=CLAVE, ahora=lambda: comun.parsear_z("2026-11-06T00:00:00Z"))
        co["compra"] = {"landing_version": "v4"}
        b = C.construir_catalogo(self.d, co, clave=CLAVE, ahora=lambda: comun.parsear_z("2026-11-06T00:00:00Z"))
        self.assertNotEqual(a["firma"], b["firma"])


class TestCLI(Base):
    def test_falta_la_clave_sale_2(self) -> None:
        codigo = C.main(["--oferta", "OF-209901-01", "--raiz", str(self.tmp)])
        self.assertEqual(ErrorUso.codigo_salida, codigo)

    def test_dry_run_no_escribe_catalogo_json(self) -> None:
        import os
        import unittest.mock as mock
        with mock.patch.dict(os.environ, {"CATALOGO_HMAC": "clave-de-prueba"}):
            codigo = C.main(["--oferta", "OF-209901-01", "--raiz", str(self.tmp)])
        self.assertEqual(0, codigo)
        self.assertFalse((self.d / "05-landing" / "catalogo.json").exists())

    def test_live_escribe_catalogo_json(self) -> None:
        import os
        import unittest.mock as mock
        with mock.patch.dict(os.environ, {"CATALOGO_HMAC": "clave-de-prueba"}):
            codigo = C.main(["--oferta", "OF-209901-01", "--raiz", str(self.tmp), "--live", "--json"])
        self.assertEqual(0, codigo)
        cat = comun.cargar_json(self.d / "05-landing" / "catalogo.json")
        self.assertEqual("price_fixture_test_principal", cat["price_ids"]["principal"])


if __name__ == "__main__":
    unittest.main()
