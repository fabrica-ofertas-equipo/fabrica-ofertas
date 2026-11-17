"""Pruebas de ``scripts.verificar_propiedad`` (I1, ola 2): tabla de dueños, CLI y descubrimiento por mtime."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from scripts import verificar_propiedad as vp


class PruebaDuenoDe(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="b0-propiedad-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.raiz, ignore_errors=True))

    def test_archivo_dentro_de_engine_es_de_b1(self) -> None:
        self.assertEqual(vp.dueno_de("engine/orq.py", raiz=self.raiz), "B1")
        self.assertEqual(vp.dueno_de("engine/sub/mas_profundo.py", raiz=self.raiz), "B1")

    def test_archivo_dentro_de_landing_es_de_b4(self) -> None:
        self.assertEqual(vp.dueno_de("landing/generar.py", raiz=self.raiz), "B4")

    def test_fulfill_es_de_b7_aunque_este_bajo_infra(self) -> None:
        # Más específico que infra/** (B8): va antes en la tabla.
        self.assertEqual(vp.dueno_de("infra/workers/fulfill/index.mjs", raiz=self.raiz), "B7")
        self.assertEqual(vp.dueno_de("infra/preflight.py", raiz=self.raiz), "B8")

    def test_ejemplo_y_contratos_son_de_ct_antes_que_de_i1_o_b1(self) -> None:
        self.assertEqual(vp.dueno_de("ofertas/_ejemplo/00-brief.yaml", raiz=self.raiz), "CT")
        self.assertEqual(vp.dueno_de("contratos/estado.schema.json", raiz=self.raiz), "CT")

    def test_scripts_b0_y_tests_integracion_son_de_i1(self) -> None:
        self.assertEqual(vp.dueno_de("scripts/b0/motor.py", raiz=self.raiz), "I1")
        self.assertEqual(vp.dueno_de("scripts/b0_e2e.py", raiz=self.raiz), "I1")
        self.assertEqual(vp.dueno_de("tests/integracion/test_b0_criterios.py", raiz=self.raiz), "I1")

    def test_ruta_sin_patron_es_comun_dueno_none(self) -> None:
        self.assertIsNone(vp.dueno_de("README.md", raiz=self.raiz))
        self.assertIsNone(vp.dueno_de("pyproject.toml", raiz=self.raiz))
        self.assertIsNone(vp.dueno_de("docs/06-bases-del-testeo.md", raiz=self.raiz))
        self.assertIsNone(vp.dueno_de("empresa/limites.yaml", raiz=self.raiz))

    def test_docs_contratos_es_ct_pero_otros_docs_son_comunes(self) -> None:
        self.assertEqual(vp.dueno_de("docs/contratos.md", raiz=self.raiz), "CT")
        self.assertIsNone(vp.dueno_de("docs/contratos-historial.md", raiz=self.raiz))

    def test_decision_reglas_es_de_b1_aunque_cambie_solo_con_revision_de_r1(self) -> None:
        self.assertEqual(vp.dueno_de("decision/reglas.py", raiz=self.raiz), "B1")
        self.assertEqual(vp.dueno_de("decision/entradas.py", raiz=self.raiz), "B1")

    def test_es_intocable(self) -> None:
        self.assertTrue(vp.es_intocable("scripts/modelado/puntaje.py", raiz=self.raiz))
        self.assertFalse(vp.es_intocable("scripts/b0/motor.py", raiz=self.raiz))


class PruebaVerificar(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="b0-propiedad-verificar-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.raiz, ignore_errors=True))

    def test_sin_violaciones_cuando_todo_es_del_dueno(self) -> None:
        v = vp.verificar(["engine/orq.py", "tests/engine/apoyo.py"], dueno="B1", raiz=self.raiz)
        self.assertEqual(v, [])

    def test_una_violacion_cuando_una_ruta_es_de_otro_dueno(self) -> None:
        v = vp.verificar(["engine/orq.py", "landing/generar.py"], dueno="B1", raiz=self.raiz)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0].ruta, "landing/generar.py")
        self.assertEqual(v[0].dueno_esperado, "B4")

    def test_rutas_comunes_nunca_violan(self) -> None:
        v = vp.verificar(["README.md", "docs/06-bases-del-testeo.md", "empresa/limites.yaml"], dueno="B1", raiz=self.raiz)
        self.assertEqual(v, [])

    def test_varias_violaciones_de_componentes_distintos(self) -> None:
        v = vp.verificar(["landing/x.py", "meta/y.py", "engine/z.py"], dueno="B1", raiz=self.raiz)
        self.assertEqual({x.dueno_esperado for x in v}, {"B4", "B5"})


class PruebaCli(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="b0-propiedad-cli-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.raiz, ignore_errors=True))

    def test_cli_sale_0_cuando_todo_en_orden(self) -> None:
        codigo = vp.main(["--dueno", "B1", "--raiz", str(self.raiz), "engine/orq.py"])
        self.assertEqual(codigo, 0)

    def test_cli_sale_3_cuando_hay_una_violacion(self) -> None:
        codigo = vp.main(["--dueno", "B1", "--raiz", str(self.raiz), "engine/orq.py", "landing/generar.py"])
        self.assertEqual(codigo, 3)

    def test_cli_exige_dueno(self) -> None:
        with self.assertRaises(SystemExit):
            vp.main(["--raiz", str(self.raiz), "engine/orq.py"])

    def test_cli_sin_rutas_ni_ancla_sale_2(self) -> None:
        codigo = vp.main(["--dueno", "B1", "--raiz", str(self.raiz)])
        self.assertEqual(codigo, 2)

    def test_cli_ancla_y_rutas_son_excluyentes(self) -> None:
        ancla = self.raiz / "ancla.txt"
        ancla.write_text("x", encoding="utf-8")
        codigo = vp.main(["--dueno", "B1", "--raiz", str(self.raiz), "--ancla", str(ancla), "engine/orq.py"])
        self.assertEqual(codigo, 2)

    def test_cli_json_trae_violaciones_estructuradas(self) -> None:
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = vp.main(["--dueno", "B1", "--raiz", str(self.raiz), "--json", "landing/x.py"])
        self.assertEqual(codigo, 3)
        import json as _json

        doc = _json.loads(buf.getvalue())
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["codigo"], 3)
        self.assertEqual(doc["datos"]["violaciones"][0]["dueno_esperado"], "B4")


class PruebaAncla(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="b0-propiedad-ancla-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.raiz, ignore_errors=True))

    def test_descubre_solo_archivos_posteriores_al_ancla(self) -> None:
        ancla = self.raiz / "ANCLA"
        ancla.write_text("x", encoding="utf-8")
        time.sleep(0.05)
        viejo = self.raiz / "viejo.py"
        viejo.write_text("x", encoding="utf-8")
        import os

        os.utime(viejo, (ancla.stat().st_mtime - 10, ancla.stat().st_mtime - 10))
        nuevo = self.raiz / "engine" / "nuevo.py"
        nuevo.parent.mkdir(parents=True, exist_ok=True)
        nuevo.write_text("x", encoding="utf-8")

        rutas = vp.rutas_desde_ancla(ancla, raiz=self.raiz)
        self.assertIn("engine/nuevo.py", rutas)
        self.assertNotIn("viejo.py", rutas)
        self.assertNotIn("ANCLA", rutas)

    def test_ignora_carpetas_de_cache_y_git(self) -> None:
        ancla = self.raiz / "ANCLA"
        ancla.write_text("x", encoding="utf-8")
        time.sleep(0.02)
        ruidoso = self.raiz / "__pycache__" / "x.pyc"
        ruidoso.parent.mkdir(parents=True, exist_ok=True)
        ruidoso.write_text("x", encoding="utf-8")
        rutas = vp.rutas_desde_ancla(ancla, raiz=self.raiz)
        self.assertEqual(rutas, [])

    def test_ancla_inexistente_es_error_de_uso(self) -> None:
        from engine.errores import ErrorUso

        with self.assertRaises(ErrorUso):
            vp.rutas_desde_ancla(self.raiz / "no-existe.txt", raiz=self.raiz)


if __name__ == "__main__":
    unittest.main()
