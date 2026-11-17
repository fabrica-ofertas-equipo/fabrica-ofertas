"""``landing.validar`` contra el oráculo de B0-11 (``tests/contratos/lint_landing_referencia.py``, CT).

La base (``ofertas/_ejemplo``, intocada) pasa limpia y cada una de las ocho mutaciones sembradas
(más las cuatro complementarias) dispara la regla ``L1-*`` que declara, sin más reglas que las
colaterales declaradas (docs/06 §6.2, B0-11; aceptación de B4). Las mutaciones solo se aplican a
copias temporales (``tests.contratos.aplicar_mutacion_landing``): el ejemplo real nunca se toca.

Comando: ``.venv/bin/python -m unittest tests.landing.test_validar``
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from landing import validar as Val
from tests.contratos import aplicar_mutacion_landing as A

RAIZ = Path(__file__).resolve().parents[2]
EJ = RAIZ / "ofertas" / "_ejemplo"


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="landing-validar-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


class TestBaseLimpia(unittest.TestCase):
    def test_ofertas_ejemplo_pasa_sin_hallazgos(self) -> None:
        self.assertEqual([], Val.validar_sitio(EJ))


class TestB0_11_OchoMutaciones(Base):
    """Las OCHO mutaciones del encargo de B0-11: ``landing.validar`` debe fallar el 100 %."""

    def test_cada_mutacion_dispara_su_regla_y_ninguna_inesperada(self) -> None:
        for m in A.mutaciones(incluir_complementarias=True):
            with self.subTest(m["id"], regla=m["regla_esperada"]):
                copia = A.copiar_ejemplo(self.tmp, m["id"])
                tocados = A.aplicar(m["id"], copia)
                self.assertTrue(tocados)
                hallazgos = Val.validar_sitio(copia)
                disparadas = Val.reglas(hallazgos)
                self.assertIn(m["regla_esperada"], disparadas, m["id"])
                self.assertLessEqual(disparadas, {m["regla_esperada"], *m["reglas_colaterales"]}, (m["id"], disparadas))

    def test_son_exactamente_ocho_mas_cuatro_complementarias(self) -> None:
        self.assertEqual(8, len(A.mutaciones()))
        self.assertEqual(4, len(A.cargar_catalogo()["complementarias"]))

    def test_el_ejemplo_real_no_se_toco(self) -> None:
        from scripts import validar_esquemas as V
        antes = V.hash_directorio(EJ)
        for m in A.mutaciones(incluir_complementarias=True):
            copia = A.copiar_ejemplo(self.tmp, "chk-" + m["id"])
            A.aplicar(m["id"], copia)
        self.assertEqual(antes, V.hash_directorio(EJ))


class TestCLI(Base):
    def test_cli_sale_3_con_hallazgos_y_0_sin_ellos(self) -> None:
        import io
        from contextlib import redirect_stdout

        copia = A.copiar_ejemplo(self.tmp / "ofertas", "cli")
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = Val.main(["--oferta", "cli", "--raiz", str(self.tmp), "--json"])
        self.assertEqual(0, codigo)
        self.assertTrue(json.loads(buf.getvalue())["ok"])

        A.aplicar("ML-04", copia)
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            codigo2 = Val.main(["--oferta", "cli", "--raiz", str(self.tmp), "--json"])
        self.assertEqual(3, codigo2)
        salida = json.loads(buf2.getvalue())
        self.assertFalse(salida["ok"])
        self.assertIn("L1-PRECIO", {h["regla"] for h in salida["datos"]["hallazgos"]})


if __name__ == "__main__":
    unittest.main()
