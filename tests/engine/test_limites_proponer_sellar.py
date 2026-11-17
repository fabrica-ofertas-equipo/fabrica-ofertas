"""Pruebas de ``engine.limites proponer``/``sellar`` (B1b, ola 1): la herramienta del dueño.

``proponer`` no debe tocar ``empresa/limites.yaml`` nunca; ``sellar`` solo lo escribe con ``--live``
(y únicamente con ``FABRICA_ENTORNO=produccion``, convenciones §9).
"""
from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from engine import comun, propuestas as limites
from engine.errores import ErrorBloqueado, ErrorLimite, ErrorUso, ErrorValidacion, ParametroFaltante
from engine.parametros import Parametros, cargar_parametros
from tests.engine.apoyo import EMPRESA_PRUEBA, PruebaBase, par_de_claves

OFERTA = "OF-202611-01"


def _parametros_completos() -> Parametros:
    """``Parametros`` en memoria (sin tocar el esquema): incluye ``alfa_descarte_tope``/``n_min_escala``,
    que HOY no caben en ``parametros.schema.json`` (grupo ``estadistica`` con ``additionalProperties:
    false``, ver NOTAS_B1b «Pedidos»). Por eso esta prueba construye el objeto directamente en vez de
    pasar por ``cargar_parametros`` (que sí valida contra el esquema, y seguiría fallando hasta que CT
    agregue esas dos claves)."""
    plano = {
        "estadistica.prior_conv_fuerza_clics": 50, "estadistica.prior_cpc_fuerza_clics": 20,
        "estadistica.alfa_descarte": "0.05", "estadistica.alfa_descarte_tope": "0.20",
        "estadistica.k_min_matar": "2.0", "estadistica.n_min_escala": 15, "estadistica.nodos_cpc": 5,
        "testeo.p_escala": "0.80", "testeo.ventana_no_decidir_h": 72,
        "campana.dias_test_defecto": 10,
    }
    grupos: dict = {}
    for clave, valor in plano.items():
        grupo, nombre = clave.split(".")
        grupos.setdefault(grupo, {})[nombre] = _entrada(valor)
    return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": grupos})


def _economia() -> dict:
    return {
        "cpa_be_visto": {"monto": 1500, "moneda": "EUR"}, "cpa_obj": {"monto": 900, "moneda": "EUR"},
        "cpc_esperado": {"monto": "40.0", "moneda": "EUR"}, "conv_central": "0.025",
        "entradas_usadas": {"costos_fijos_oferta": {"monto": 1000, "moneda": "EUR"}},
    }


class PruebaProponerSellar(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        shutil.copytree(EMPRESA_PRUEBA, self.tmp / "empresa")
        self.par = _parametros_completos()
        comun.escribir_atomico(self.tmp / "ofertas" / OFERTA / "03-oferta" / "economia.json", comun.json_canonico(_economia()))

    def test_proponer_exige_parametros_cargados(self) -> None:
        with self.assertRaises(TypeError):
            limites.proponer_limites(OFERTA, raiz=self.tmp, corridas=5)

    def test_parametros_yaml_real_no_tiene_hoy_alfa_descarte_tope(self) -> None:
        # Documenta el hueco de esquema (ver NOTAS_B1b «Pedidos»): con el parametros.yaml de verdad
        # (sin el grupo "estadistica" completo), proponer falla cerrado en vez de inventar un umbral.
        par_real = cargar_parametros(self.tmp / "empresa" / "parametros.yaml")
        with self.assertRaises(ParametroFaltante):
            limites.proponer_limites(OFERTA, par_real, raiz=self.tmp, corridas=5)

    def test_proponer_sin_economia_bloquea(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            limites.proponer_limites("OF-202611-99", self.par, raiz=self.tmp, corridas=5)

    def test_proponer_escribe_propuesta_sin_tocar_limites_real(self) -> None:
        hash_antes = comun.hash_archivo(self.tmp / "empresa" / "limites.yaml")
        resultado = limites.proponer_limites(OFERTA, self.par, multiplos=(10, 15, 25), raiz=self.tmp, corridas=5, semilla=1)
        self.assertEqual(comun.hash_archivo(self.tmp / "empresa" / "limites.yaml"), hash_antes)
        ruta = Path(resultado["ruta"])
        self.assertTrue(ruta.is_file())
        propuesta = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        self.assertEqual(len(propuesta["_candidatos"]), 3)
        self.assertEqual(resultado["multiplo_recomendado"], 15)  # el intermedio de [10, 15, 25]
        self.assertEqual(propuesta["gasto_total_test_por_oferta"], 15 * 1500)
        self.assertEqual(propuesta["perdida_max_test_por_oferta"], 15 * 1500)
        self.assertEqual(propuesta["moneda_limites"], "EUR")  # preservada del limites.yaml existente
        for c in propuesta["_candidatos"]:
            self.assertEqual(len(c["tabla"]), 5)

    def test_proponer_multiplo_invalido_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorValidacion):
            limites.proponer_limites(OFERTA, self.par, multiplos=(0,), raiz=self.tmp, corridas=5)

    def _propuesta_valida(self) -> Path:
        limites.proponer_limites(OFERTA, self.par, multiplos=(10,), raiz=self.tmp, corridas=5, semilla=1)
        return limites.ruta_propuesta_por_defecto(self.tmp)

    def test_sellar_exige_como_dueno(self) -> None:
        ruta = self._propuesta_valida()
        with self.assertRaises(ErrorValidacion):
            limites.sellar_limites(ruta, como="otro", raiz=self.tmp)

    def test_sellar_dry_run_no_escribe_nada(self) -> None:
        ruta = self._propuesta_valida()
        hash_antes = comun.hash_archivo(self.tmp / "empresa" / "limites.yaml")
        resultado = limites.sellar_limites(ruta, como="dueno", modo="dry_run", raiz=self.tmp)
        self.assertEqual(resultado["modo"], "dry_run")
        self.assertEqual(comun.hash_archivo(self.tmp / "empresa" / "limites.yaml"), hash_antes)

    def test_sellar_live_fuera_de_produccion_bloquea(self) -> None:
        ruta = self._propuesta_valida()
        with self.assertRaises(ErrorBloqueado):
            limites.sellar_limites(ruta, como="dueno", modo="live", raiz=self.tmp, env={"FABRICA_ENTORNO": "prueba"})

    def test_sellar_live_sin_firma_en_produccion_falla_por_limite(self) -> None:
        ruta = self._propuesta_valida()
        with self.assertRaises(ErrorLimite):
            limites.sellar_limites(ruta, como="dueno", modo="live", raiz=self.tmp, env={"FABRICA_ENTORNO": "produccion"})

    def test_sellar_live_con_firma_escribe_limites_yaml_y_sube_la_version(self) -> None:
        ruta = self._propuesta_valida()
        claves = par_de_claves()
        version_previa = yaml.safe_load((self.tmp / "empresa" / "limites.yaml").read_text(encoding="utf-8"))["version"]
        resultado = limites.sellar_limites(
            ruta, como="dueno", modo="live", raiz=self.tmp, ruta_clave_privada=claves.privada,
            env={"FABRICA_ENTORNO": "produccion"},
        )
        self.assertTrue(resultado["firmado"])
        nuevo = yaml.safe_load((self.tmp / "empresa" / "limites.yaml").read_text(encoding="utf-8"))
        self.assertEqual(nuevo["version"], version_previa + 1)
        self.assertEqual(nuevo["gasto_total_test_por_oferta"], 10 * 1500)
        self.assertTrue(nuevo["sello"]["firma"].startswith("ed25519:"))
        self.assertNotIn("_candidatos", nuevo)  # los metadatos de proponer no contaminan limites.yaml

    def test_sellar_falta_una_clave_del_esquema_es_invalido(self) -> None:
        ruta = self._propuesta_valida()
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        del datos["politica_divulgacion_ia"]
        ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            limites.sellar_limites(ruta, como="dueno", modo="dry_run", raiz=self.tmp)


def _entrada(valor):
    return {"valor": valor, "unidad": "u", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}


if __name__ == "__main__":
    unittest.main()
