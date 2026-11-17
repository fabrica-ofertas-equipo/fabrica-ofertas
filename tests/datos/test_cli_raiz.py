"""Pruebas de aislamiento de `--raiz`: ningún CLI de `datos` debe leer el `empresa/` real del repositorio.

Regresión de un error real de esta sesión: `datos.kpi` y `datos.etl_stripe` llamaban a
`cargar_parametros()` SIN argumento dentro de funciones que ya habían resuelto `raiz` con un `--raiz`
explícito; como `cargar_parametros()` por defecto usa `comun.raiz()` SIN el `env` local, acababa leyendo
`empresa/parametros.yaml` del repositorio real en vez de la raíz de prueba (B0-04 lo exige al revés:
con `--raiz`, el `empresa/` real ni se lee para esto ni se toca).
"""
from __future__ import annotations

import json
from io import StringIO
from unittest import mock

from datos import etl_meta, etl_stripe, kpi
from tests.datos.apoyo import FIXTURES_DATOS, OFERTA, PruebaBase

RUTA_INSIGHTS = FIXTURES_DATOS / "meta_insights_OF-202611-01.json"
RUTA_EVENTOS = FIXTURES_DATOS / "stripe_eventos_OF-202611-01.json"


def _salida_json(capturado: str) -> dict:
    return json.loads(capturado.strip().splitlines()[-1])


class PruebaAislamientoDeRaiz(PruebaBase):
    def test_kpi_sin_parametros_yaml_en_la_raiz_no_lee_el_del_repositorio(self) -> None:
        """Si leyera el `empresa/parametros.yaml` real, `meta` saldría «verde»; aislado, sale «rojo»."""
        codigo = etl_meta.main(["--oferta", OFERTA, "--desde", "2026-11-10", "--hasta", "2026-11-12",
                               "--fixture", str(RUTA_INSIGHTS), "--raiz", str(self.tmp)])
        self.assertEqual(codigo, 0)
        with mock.patch("sys.stdout", new_callable=StringIO) as salida:
            codigo = kpi.main(["--oferta", OFERTA, "--fecha", "2026-11-11", "--raiz", str(self.tmp), "--json"])
        self.assertEqual(codigo, 0)
        resultado = _salida_json(salida.getvalue())
        self.assertEqual(resultado["datos"]["fuentes"]["meta"]["estado"], "rojo")

    def test_etl_stripe_sin_parametros_yaml_no_falla_y_no_excluye_nada_como_interna(self) -> None:
        with mock.patch("sys.stdout", new_callable=StringIO) as salida:
            codigo = etl_stripe.main(["--fixture", str(RUTA_EVENTOS), "--raiz", str(self.tmp), "--json"])
        self.assertEqual(codigo, 0)
        resultado = _salida_json(salida.getvalue())
        self.assertEqual(resultado["datos"]["nuevos"], 6)
