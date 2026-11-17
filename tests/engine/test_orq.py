"""Pruebas de ``engine.orq``: crear, ejecutar (rondas de QA, reutilización, obsolescencia), ingresar,
firmar y el gate H. Cubren B0-05, B0-06, B0-07, B0-23 y B0-25 de docs/06 §6.2 (en un alcance reducido:
una fixture propia, no ``ofertas/_ejemplo/`` completo, que es trabajo de I1)."""
from __future__ import annotations

from pathlib import Path

import yaml

from engine import estado, orq
from engine.errores import ErrorLimite, ErrorValidacion
from tests.engine import apoyo
from tests.engine.apoyo_orq import _qa_minimo, candidatos_ejemplo, escribir_arbol, escribir_ronda, mercado_ejemplo, pre_brief

_REL_D1 = "01-descubrimiento/candidatos.json"
_REL_M1 = "mercado.json"


class PruebaOrq(apoyo.PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = apoyo.crear_empresa(self.tmp, entorno="desarrollo", modo_infra="prueba")
        self.raiz = self.emp.raiz
        self.ahora = self.emp.reloj
        self._contador_ofertas = 0
        # Sin autonomia.yaml: el nivel efectivo lo da solo estado.json (el de la fixture topa D1/M1 en
        # N2 y rompería los casos que ejercen el gate S puro con N4; el caso de gate H usa N2 aparte).
        (self.raiz / "empresa" / "autonomia.yaml").unlink(missing_ok=True)

    def _ruta_brief(self, *, nivel_autonomia: str = "N4", moneda: str | None = None) -> Path:
        self._contador_ofertas += 1
        datos = pre_brief(nivel_autonomia=nivel_autonomia, slug=f"prueba-orq-{self._contador_ofertas}")
        if moneda is not None:
            datos["mercado_objetivo"]["moneda_cobro"] = moneda
        ruta = self.tmp / f"pre-brief-{self._contador_ofertas}.yaml"
        ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return ruta

    def _crear(self, *, nivel_autonomia: str = "N4") -> str:
        resultado = orq.crear(ruta_brief=self._ruta_brief(nivel_autonomia=nivel_autonomia), raiz=self.raiz, ahora=self.ahora)
        return resultado["oferta_id"]

    def _qa(self, etapa: str, version: str, ronda: int, veredicto: str, oferta_id: str) -> dict:
        rel = {"D1": _REL_D1, "M1": _REL_M1}[etapa]
        return _qa_minimo(etapa=etapa, version=version, ronda=ronda, veredicto=veredicto, oferta_id=oferta_id, artefacto_ref=rel)

    # ------------------------------------------------------------------ crear
    def test_crear_es_idempotente_por_contenido_del_brief(self) -> None:
        ruta = self._ruta_brief()
        primero = orq.crear(ruta_brief=ruta, raiz=self.raiz, ahora=self.ahora)
        segundo = orq.crear(ruta_brief=ruta, raiz=self.raiz, ahora=self.ahora)
        self.assertTrue(primero["creado"])
        self.assertFalse(segundo["creado"])
        self.assertEqual(primero["oferta_id"], segundo["oferta_id"])
        self.assertTrue((self.raiz / "ofertas" / primero["oferta_id"] / "00-brief.yaml").is_file())
        estado.cargar(primero["oferta_id"], raiz=self.raiz)  # no lanza: el estado existe

    def test_crear_rechaza_moneda_distinta_de_moneda_limites(self) -> None:
        with self.assertRaises(ErrorLimite):
            orq.crear(ruta_brief=self._ruta_brief(moneda="USD"), raiz=self.raiz, ahora=self.ahora)

    # ------------------------------------------------------------------ ejecutar: rondas de QA (B0-05)
    def test_ejecutar_un_fail_seguido_de_pass_aprueba_en_la_ronda_2(self) -> None:
        oferta_id = self._crear()  # N4: etapa:D1 es S (auto-aprueba, sin orden firmada)
        fixture = self.tmp / "fx-d1-fail-pass"
        for indice, veredicto in ((1, "FAIL"), (2, "PASS")):
            escribir_ronda(fixture / f"ronda-{indice}", archivos={_REL_D1: candidatos_ejemplo()},
                           qa=self._qa("D1", "v1", indice, veredicto, oferta_id))
        resultado = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        self.assertEqual(resultado["resultado"], "aprobado")
        self.assertEqual(resultado["version"], "v1")
        self.assertEqual(resultado["rondas"], 2)
        campo = estado.cargar(oferta_id, raiz=self.raiz)["etapas"]["D1"]
        self.assertEqual(campo["estado"], "aprobado")
        self.assertEqual(campo["ronda_qa"], 2)

    def test_ejecutar_dos_fail_escala(self) -> None:
        oferta_id = self._crear()
        fixture = self.tmp / "fx-d1-escalado"
        for indice in (1, 2):
            escribir_ronda(fixture / f"ronda-{indice}", archivos={_REL_D1: candidatos_ejemplo()},
                           qa=self._qa("D1", "v1", indice, "FAIL", oferta_id))
        resultado = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        self.assertEqual(resultado["resultado"], "escalado")
        self.assertEqual(estado.cargar(oferta_id, raiz=self.raiz)["etapas"]["D1"]["estado"], "escalado")

    # ------------------------------------------------------------------ ejecutar: reutilización (B0-06)
    def test_ejecutar_dos_veces_con_la_misma_fixture_dice_reutilizado(self) -> None:
        oferta_id = self._crear()
        fixture = self.tmp / "fx-d1-pass"
        escribir_ronda(fixture / "ronda-1", archivos={_REL_D1: candidatos_ejemplo()}, qa=self._qa("D1", "v1", 1, "PASS", oferta_id))
        primero = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        segundo = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        self.assertEqual(primero["resultado"], "aprobado")
        self.assertEqual(segundo["resultado"], "reutilizado")
        self.assertEqual(primero["hash_salida"], segundo["hash_salida"])
        self.assertEqual(segundo["version"], "v1")

    # ------------------------------------------------------------------ obsolescencia (B0-07)
    def test_cambiar_d1_vuelve_obsoleta_m1_y_pausa_la_campana(self) -> None:
        oferta_id = self._crear()  # N4: D1 y M1 son S
        fixture_d1 = self.tmp / "fx-d1-v1"
        escribir_ronda(fixture_d1 / "ronda-1", archivos={_REL_D1: candidatos_ejemplo(variante="a")},
                       qa=self._qa("D1", "v1", 1, "PASS", oferta_id))
        orq.ejecutar(oferta_id, "D1", fixture_dir=fixture_d1, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)

        fixture_m1 = self.tmp / "fx-m1-v1"
        escribir_ronda(fixture_m1 / "ronda-1", archivos={_REL_M1: mercado_ejemplo()}, qa=self._qa("M1", "v1", 1, "PASS", oferta_id))
        orq.ejecutar(oferta_id, "M1", fixture_dir=fixture_m1, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)

        for a in ("en_construccion", "listo_para_activar", "en_test"):
            estado.transicionar_fase(oferta_id, a, actor="prueba", causa="avance", raiz=self.raiz, ahora=self.ahora)

        fixture_d1_v2 = self.tmp / "fx-d1-v2"
        escribir_ronda(fixture_d1_v2 / "ronda-1", archivos={_REL_D1: candidatos_ejemplo(variante="b")},
                       qa=self._qa("D1", "v2", 1, "PASS", oferta_id))
        resultado = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture_d1_v2, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        self.assertEqual(resultado["resultado"], "aprobado")
        self.assertEqual(resultado["version"], "v2")

        est = estado.cargar(oferta_id, raiz=self.raiz)
        self.assertEqual(est["etapas"]["M1"]["estado"], "pendiente")
        self.assertTrue(est["etapas"]["M1"]["obsoleta"])
        self.assertEqual(est["fase"], "pausada")
        self.assertTrue((self.raiz / "ofertas" / oferta_id / ".versiones" / "D1" / "v1" / _REL_D1).is_file())

    # ------------------------------------------------------------------ ingresar == ejecutar --modo fixture (B0-23)
    def test_ingresar_y_ejecutar_dan_el_mismo_hash_salida_y_gate(self) -> None:
        contenido = candidatos_ejemplo()
        oferta_ejecutar = self._crear()
        fixture = self.tmp / "fx-d1-paridad"
        escribir_ronda(fixture / "ronda-1", archivos={_REL_D1: contenido}, qa=self._qa("D1", "v1", 1, "PASS", oferta_ejecutar))
        via_ejecutar = orq.ejecutar(oferta_ejecutar, "D1", fixture_dir=fixture, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)

        oferta_ingresar = self._crear()
        self.assertNotEqual(oferta_ejecutar, oferta_ingresar)
        desde = self.tmp / "ingresar-d1"
        escribir_arbol(desde, archivos={_REL_D1: contenido})
        via_ingresar = orq.ingresar(oferta_ingresar, "D1", desde=desde, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)

        self.assertEqual(via_ejecutar["hash_salida"], via_ingresar["hash_salida"])
        self.assertEqual(via_ejecutar["resultado"], via_ingresar["resultado"])
        self.assertEqual(via_ejecutar["version"], via_ingresar["version"])
        campo_e = estado.cargar(oferta_ejecutar, raiz=self.raiz)["etapas"]["D1"]
        campo_i = estado.cargar(oferta_ingresar, raiz=self.raiz)["etapas"]["D1"]
        self.assertEqual(campo_e["hash_salida"], campo_i["hash_salida"])
        self.assertEqual(campo_e["version_aprobada"], campo_i["version_aprobada"])
        self.assertEqual(campo_e["aprobado_por"]["tipo"], "qa_pass")
        self.assertEqual(campo_i["aprobado_por"]["tipo"], "humano")

    def test_ingresar_rechaza_un_symlink_fuera_de_ruta(self) -> None:
        oferta_id = self._crear()
        desde = self.tmp / "ingresar-symlink"
        escribir_arbol(desde, archivos={_REL_D1: candidatos_ejemplo()})
        (desde / "enlace-raro.json").symlink_to(desde / "01-descubrimiento" / "candidatos.json")
        with self.assertRaises(ErrorValidacion):
            orq.ingresar(oferta_id, "D1", desde=desde, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)

    # ------------------------------------------------------------------ firmar / gate H / nonce (B0-25)
    def test_gate_h_queda_pendiente_de_firma_y_firmar_lo_resuelve(self) -> None:
        oferta_id = self._crear(nivel_autonomia="N2")  # N2: etapa:D1 es H
        fixture = self.tmp / "fx-d1-gate-h"
        escribir_ronda(fixture / "ronda-1", archivos={_REL_D1: candidatos_ejemplo()}, qa=self._qa("D1", "v1", 1, "PASS", oferta_id))
        pendiente = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        self.assertEqual(pendiente["resultado"], "pendiente_firma")
        self.assertEqual(estado.cargar(oferta_id, raiz=self.raiz)["etapas"]["D1"]["estado"], "en_QA")

        orq.firmar(oferta_id=oferta_id, etapa="D1", hash_objetivo=pendiente["hash_salida"], clave_privada=self.emp.claves.privada,
                  raiz=self.raiz, ahora=self.ahora, nonce="nonce-de-prueba-0001")
        with self.assertRaises(ErrorValidacion):
            orq.firmar(oferta_id=oferta_id, etapa="D1", hash_objetivo=pendiente["hash_salida"], clave_privada=self.emp.claves.privada,
                      raiz=self.raiz, ahora=self.ahora, nonce="nonce-de-prueba-0001")  # B0-25: nonce repetido -> rechazo

        aprobado = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        self.assertEqual(aprobado["resultado"], "aprobado")
        campo = estado.cargar(oferta_id, raiz=self.raiz)["etapas"]["D1"]
        self.assertEqual(campo["estado"], "aprobado")
        self.assertEqual(campo["aprobado_por"]["tipo"], "humano")


if __name__ == "__main__":
    import unittest
    unittest.main()
