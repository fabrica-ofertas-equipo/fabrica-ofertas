"""Pruebas de ``scripts.creativos.cost_preflight`` (paso 6 de D6: topes de créditos antes de generar).

La integración de CLI con el margen REAL (``creativos.margen_regeneracion_pct``) no se puede probar
contra un ``parametros.yaml`` válido por esquema: la clave no existe todavía en
``contratos/parametros.schema.json`` (ver README, «Decisiones» 4). Por eso:
* la aritmética del margen y la comparación contra los topes se prueban DIRECTO (``con_margen``,
  ``evaluar_plan``), sin pasar por el cargador de parámetros;
* la integración de ``main`` con el margen se prueba con ``unittest.mock`` sustituyendo SOLO
  ``motor_parametros.cargar_parametros`` (el reloj, los IDs y, aquí, el cargador de un parámetro que
  el esquema real todavía no admite, se inyectan igual que en el resto del repositorio);
* el camino sin parchear (parámetro realmente ausente) se prueba tal cual, porque ES el
  comportamiento esperado hoy (falla cerrado con 5).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from engine import comun
from engine.errores import ErrorLimite, ErrorValidacion

from scripts.creativos import cost_preflight
from tests.scripts.test_creativos_comun import crear_empresa


class PruebaConMargen(unittest.TestCase):
    def test_cero_creditos_pasa_con_cero(self) -> None:
        self.assertEqual(cost_preflight.con_margen(0, 20), 0)

    def test_redondea_hacia_arriba(self) -> None:
        self.assertEqual(cost_preflight.con_margen(10, 20), 12)  # 10 * 1.2 = 12 exacto
        self.assertEqual(cost_preflight.con_margen(1, 20), 2)    # 1.2 -> 2 (CEILING)

    def test_margen_cero_no_cambia_nada(self) -> None:
        self.assertEqual(cost_preflight.con_margen(50, 0), 50)

    def test_creditos_negativos_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            cost_preflight.con_margen(-1, 20)

    def test_margen_negativo_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            cost_preflight.con_margen(10, -1)


class PruebaEvaluarPlan(unittest.TestCase):
    def test_dentro_de_topes_sin_problemas(self) -> None:
        r = cost_preflight.evaluar_plan([{"id": "p1", "creditos_cotizados": 10}], margen_pct=20, tope_pieza=50,
                                        tope_oferta=500, acumulado_previo=0)
        self.assertEqual(r["problemas"], [])
        self.assertEqual(r["piezas"][0]["creditos_con_margen"], 12)

    def test_tope_de_pieza_exacto_pasa(self) -> None:
        r = cost_preflight.evaluar_plan([{"id": "p1", "creditos_cotizados": 50}], margen_pct=0, tope_pieza=50,
                                        tope_oferta=500, acumulado_previo=0)
        self.assertEqual(r["problemas"], [])

    def test_tope_de_pieza_mas_uno_bloquea(self) -> None:
        r = cost_preflight.evaluar_plan([{"id": "p1", "creditos_cotizados": 51}], margen_pct=0, tope_pieza=50,
                                        tope_oferta=500, acumulado_previo=0)
        self.assertEqual(len(r["problemas"]), 1)
        self.assertIn("p1", r["problemas"][0])

    def test_tope_de_oferta_exacto_pasa(self) -> None:
        r = cost_preflight.evaluar_plan([{"id": "p1", "creditos_cotizados": 500}], margen_pct=0, tope_pieza=500,
                                        tope_oferta=500, acumulado_previo=0)
        self.assertEqual(r["problemas"], [])

    def test_acumulado_mas_uno_bloquea_por_oferta(self) -> None:
        r = cost_preflight.evaluar_plan([{"id": "p1", "creditos_cotizados": 10}], margen_pct=0, tope_pieza=50,
                                        tope_oferta=500, acumulado_previo=491)
        self.assertEqual(len(r["problemas"]), 1)
        self.assertIn("acumulado", r["problemas"][0])

    def test_plan_vacio_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            cost_preflight.evaluar_plan([], margen_pct=20, tope_pieza=50, tope_oferta=500, acumulado_previo=0)

    def test_id_repetido_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            cost_preflight.evaluar_plan(
                [{"id": "p1", "creditos_cotizados": 1}, {"id": "p1", "creditos_cotizados": 1}],
                margen_pct=0, tope_pieza=50, tope_oferta=500, acumulado_previo=0,
            )


class PruebaAcumuladoPrevio(unittest.TestCase):
    def test_suma_solo_los_creditos_de_la_oferta(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            ruta = raiz / "empresa" / "costos.jsonl"
            comun.anexar_jsonl(ruta, {
                "schema_version": "1.0.0", "ts": "2026-11-09T06:00:00Z", "oferta_id": "OF-202611-01",
                "etapa": "D6", "ejecucion_id": "r1", "origen": "creditos", "concepto": "c1",
                "monto": {"monto": 0, "moneda": "EUR"}, "creditos": 10,
            })
            comun.anexar_jsonl(ruta, {
                "schema_version": "1.0.0", "ts": "2026-11-09T06:01:00Z", "oferta_id": "OF-202611-02",
                "etapa": "D6", "ejecucion_id": "r1", "origen": "creditos", "concepto": "c2",
                "monto": {"monto": 0, "moneda": "EUR"}, "creditos": 999,
            })
            comun.anexar_jsonl(ruta, {
                "schema_version": "1.0.0", "ts": "2026-11-09T06:02:00Z", "oferta_id": "OF-202611-01",
                "etapa": "D6", "ejecucion_id": "r2", "origen": "creditos", "concepto": "c3",
                "monto": {"monto": 0, "moneda": "EUR"}, "creditos": 5,
            })
            self.assertEqual(cost_preflight.acumulado_previo_de_oferta(raiz, "OF-202611-01"), 15)

    def test_sin_costos_jsonl_es_cero(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cost_preflight.acumulado_previo_de_oferta(Path(tmp), "OF-202611-01"), 0)


_PLAN = {"piezas": [{"id": "p1", "creditos_cotizados": 10}]}


class _ParametrosConMargen:
    """Doble de ``Parametros`` que SOLO responde el margen (el resto del repo no lo necesita aquí)."""

    def __init__(self, margen: int) -> None:
        self._margen = margen

    def valor(self, clave: str):
        if clave == cost_preflight.CLAVE_MARGEN:
            return self._margen
        raise AssertionError(f"parámetro inesperado en la prueba: {clave}")


class PruebaCLI(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)
        self.emp = crear_empresa(self.tmp, entorno="prueba")
        self.plan = self.tmp / "plan.json"
        self.plan.write_text(json.dumps(_PLAN), encoding="utf-8")

    def _argv(self, **extra) -> list[str]:
        argv = ["--oferta", "OF-202611-01", "--plan", str(self.plan), "--raiz", str(self.tmp)]
        for k, v in extra.items():
            argv += [f"--{k.replace('_', '-')}"] if v is True else [f"--{k.replace('_', '-')}", str(v)]
        return argv

    def test_sin_el_parametro_del_margen_falla_cerrado_con_cinco(self) -> None:
        with mock.patch.dict("os.environ", self.emp.env, clear=False):
            codigo = cost_preflight.main(self._argv())
        self.assertEqual(codigo, ErrorLimite.codigo_salida)

    def test_con_tope_de_pieza_en_null_falla_cerrado_con_cinco(self) -> None:
        self.emp.reescribir_limites(lambda lim: lim.__setitem__("creditos_max_pieza", None))
        with mock.patch.dict("os.environ", self.emp.env, clear=False), \
             mock.patch.object(cost_preflight.motor_parametros, "cargar_parametros", return_value=_ParametrosConMargen(20)):
            codigo = cost_preflight.main(self._argv())
        self.assertEqual(codigo, ErrorLimite.codigo_salida)

    def test_con_margen_inyectado_y_dentro_de_topes_sale_cero_en_dry_run(self) -> None:
        with mock.patch.dict("os.environ", self.emp.env, clear=False), \
             mock.patch.object(cost_preflight.motor_parametros, "cargar_parametros", return_value=_ParametrosConMargen(20)):
            codigo = cost_preflight.main(self._argv())
        self.assertEqual(codigo, 0)
        self.assertFalse((self.tmp / "empresa" / "costos.jsonl").exists())

    def test_con_aplicar_escribe_costos_jsonl(self) -> None:
        with mock.patch.dict("os.environ", self.emp.env, clear=False), \
             mock.patch.object(cost_preflight.motor_parametros, "cargar_parametros", return_value=_ParametrosConMargen(20)):
            codigo = cost_preflight.main(self._argv(aplicar=True))
        self.assertEqual(codigo, 0)
        lineas = comun.leer_jsonl(self.tmp / "empresa" / "costos.jsonl")
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0]["creditos"], 12)
        self.assertEqual(lineas[0]["oferta_id"], "OF-202611-01")

    def test_plan_que_excede_no_escribe_nada_aun_con_aplicar(self) -> None:
        plan_excesivo = self.tmp / "plan_excesivo.json"
        plan_excesivo.write_text(json.dumps({"piezas": [{"id": "p1", "creditos_cotizados": 1000}]}), encoding="utf-8")
        argv = ["--oferta", "OF-202611-01", "--plan", str(plan_excesivo), "--raiz", str(self.tmp), "--aplicar"]
        with mock.patch.dict("os.environ", self.emp.env, clear=False), \
             mock.patch.object(cost_preflight.motor_parametros, "cargar_parametros", return_value=_ParametrosConMargen(20)):
            codigo = cost_preflight.main(argv)
        self.assertEqual(codigo, ErrorLimite.codigo_salida)
        self.assertFalse((self.tmp / "empresa" / "costos.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
