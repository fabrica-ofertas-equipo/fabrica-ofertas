"""Pruebas de ``engine.parametros``: carga validada, ``valor("grupo.clave")`` y ``ParametroFaltante`` (5)."""
from __future__ import annotations

import os
import unittest
from unittest import mock

import yaml

from engine import parametros
from engine.errores import ErrorLimite, ErrorUso, ErrorValidacion, ParametroFaltante
from tests.engine.apoyo import EMPRESA_PRUEBA, PruebaBase

FIXTURE = EMPRESA_PRUEBA / "parametros.yaml"


def _cargar_dict() -> dict:
    with open(FIXTURE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _escribir(ruta, datos) -> None:
    ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")


class PruebaCargarParametros(PruebaBase):
    """Carga, validación contra el esquema y errores por archivo ausente o ilegible."""

    def test_carga_la_fixture(self) -> None:
        par = parametros.cargar_parametros(FIXTURE)
        self.assertEqual(par.schema_version[0], "1")
        self.assertGreaterEqual(par.version, 1)
        self.assertIn("orquestador.max_rondas_qa", par.aplanar())

    def test_ruta_por_defecto_sale_de_fabrica_raiz(self) -> None:
        (self.tmp / "empresa").mkdir()
        (self.tmp / "empresa" / "parametros.yaml").write_bytes(FIXTURE.read_bytes())
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.tmp)}):
            self.assertEqual(parametros.cargar_parametros().valor("infra.hc_preflight_vigencia_horas"), 6)

    def test_archivo_inexistente_es_error_de_limite_cinco(self) -> None:
        with self.assertRaises(ErrorLimite) as cm:
            parametros.cargar_parametros(self.tmp / "no-existe.yaml")
        self.assertEqual(cm.exception.codigo_salida, 5)

    def test_yaml_ilegible_o_con_claves_repetidas_es_error_de_limite(self) -> None:
        for contenido in ("a: [1, 2", "version: 1\nversion: 2\n", "- solo\n- lista\n"):
            ruta = self.tmp / "p.yaml"
            ruta.write_text(contenido, encoding="utf-8")
            with self.subTest(contenido=contenido), self.assertRaises(ErrorLimite):
                parametros.cargar_parametros(ruta)

    def test_esquema_invalido_es_error_de_validacion_tres(self) -> None:
        datos = _cargar_dict()
        del datos["grupos"]["infra"]
        ruta = self.tmp / "p.yaml"
        _escribir(ruta, datos)
        with self.assertRaises(ErrorValidacion) as cm:
            parametros.cargar_parametros(ruta)
        self.assertEqual(cm.exception.codigo_salida, 3)

    def test_decimales_de_coma_flotante_se_rechazan(self) -> None:
        datos = _cargar_dict()
        datos["grupos"]["orquestador"]["umbral_pass_o0"]["valor"] = 4.0
        ruta = self.tmp / "p.yaml"
        _escribir(ruta, datos)
        with self.assertRaises(ErrorValidacion):
            parametros.cargar_parametros(ruta)


class PruebaValor(PruebaBase):
    """``valor`` entrega copias y falla con ``ParametroFaltante`` si falta o es ``null``."""

    def setUp(self) -> None:
        super().setUp()
        self.par = parametros.cargar_parametros(FIXTURE)

    def test_valores_de_distintos_tipos(self) -> None:
        self.assertEqual(self.par.valor("infra.hc_preflight_vigencia_horas"), 6)
        self.assertEqual(self.par.valor("orquestador.umbral_pass_o0"), "4.0")  # decimal como cadena, nunca coma flotante
        self.assertEqual(self.par.valor("orquestador.espera_reintento_min"), [1, 5])
        self.assertEqual(self.par.valor("orquestador.paralelas_max_por_nivel")["N2"], 1)

    def test_entrega_copias_que_no_alteran_el_estado(self) -> None:
        lista = self.par.valor("orquestador.espera_reintento_min")
        lista.append(99)
        self.assertEqual(self.par.valor("orquestador.espera_reintento_min"), [1, 5])
        self.par.aplanar()["infra.hc_preflight_vigencia_horas"]["valor"] = 1
        self.assertEqual(self.par.valor("infra.hc_preflight_vigencia_horas"), 6)

    def test_clave_inexistente_es_parametro_faltante_cinco(self) -> None:
        for clave in ("infra.no_existe", "grupo_inexistente.x", "estadistica.alfa_descarte"):
            with self.subTest(clave=clave), self.assertRaises(ParametroFaltante) as cm:
                self.par.valor(clave)
            self.assertEqual(cm.exception.codigo_salida, 5)
            self.assertIsInstance(cm.exception, ErrorLimite)
            self.assertEqual(cm.exception.clave, clave)

    def test_valor_nulo_es_parametro_faltante(self) -> None:
        datos = _cargar_dict()
        datos["grupos"]["infra"]["hc_hora_diaria"]["valor"] = None
        ruta = self.tmp / "p.yaml"
        _escribir(ruta, datos)
        par = parametros.cargar_parametros(ruta)
        with self.assertRaises(ParametroFaltante):
            par.valor("infra.hc_hora_diaria")
        self.assertFalse(par.tiene("infra.hc_hora_diaria"))
        self.assertTrue(par.tiene("infra.hc_preflight_vigencia_horas"))

    def test_clave_mal_formada_es_error_de_uso(self) -> None:
        for clave in ("infra", "infra.", ".x", "a.b.c", "", None):
            with self.subTest(clave=clave), self.assertRaises(ErrorUso):
                self.par.valor(clave)  # type: ignore[arg-type]

    def test_aplanar_tiene_unidad_y_valor(self) -> None:
        plano = self.par.aplanar()
        self.assertEqual(plano["infra.hc_preflight_vigencia_horas"]["unidad"], "horas")
        self.assertEqual(plano["infra.hc_preflight_vigencia_horas"]["valor"], 6)
        self.assertEqual(len(plano), len(list(self.par)))


if __name__ == "__main__":
    unittest.main()
