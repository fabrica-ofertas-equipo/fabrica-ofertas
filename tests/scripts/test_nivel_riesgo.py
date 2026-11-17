"""Pruebas de scripts.nivel_riesgo: tabla única de ejes P/C/E/N → nivel (nota 25 §2.3, D-01).

La suite de casos-frontera (230 casos) es el oráculo; además se siembra cada rama de la tabla y cada
fallo cerrado (código desconocido, eje ausente, N0 dentro de macro, ejes extra).
"""
from __future__ import annotations

import contextlib
import io
import itertools
import json
import unittest
from pathlib import Path

from engine.errores import ErrorValidacion
from scripts import nivel_riesgo as N

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "docs" / "_historial" / "hwr-semillas" / "casos-frontera.yaml"


def _ejes(p="P1", c="C1", e="E0", n="N1") -> dict[str, str]:
    return {"P": p, "C": c, "E": e, "N": n}


class PruebaSuite(unittest.TestCase):
    @unittest.skipUnless(SUITE.is_file(), "sin la suite de casos-frontera en este árbol")
    def test_la_suite_completa_da_cero_discrepancias(self) -> None:
        self.assertEqual([], N.verificar_suite(SUITE))

    @unittest.skipUnless(SUITE.is_file(), "sin la suite de casos-frontera en este árbol")
    def test_la_suite_tiene_los_230_casos_y_los_cuenta_toda(self) -> None:
        import yaml

        casos = yaml.safe_load(SUITE.read_text(encoding="utf-8"))["casos"]
        self.assertGreaterEqual(len(casos), 230)

    def test_una_suite_con_un_caso_cambiado_se_detecta(self) -> None:
        import tempfile

        import yaml

        if not SUITE.is_file():
            self.skipTest("sin suite")
        datos = yaml.safe_load(SUITE.read_text(encoding="utf-8"))
        victima = next(c for c in datos["casos"] if c["macro_nicho_esperado"] != "fuera_de_macro_nicho" and str(c["nivel_esperado"]).lower() == "verde")
        victima["nivel_esperado"] = "rojo"
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "suite.yaml"
            ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
            errores = N.verificar_suite(ruta)
        self.assertTrue(any(victima["id"] in e for e in errores), errores)

    def test_una_suite_sin_forma_es_error_de_validacion(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "suite.yaml"
            ruta.write_text("casos: 5\n", encoding="utf-8")
            with self.assertRaises(ErrorValidacion):
                N.verificar_suite(ruta)


class PruebaTabla(unittest.TestCase):
    def test_todo_verde_es_verde_y_pasa(self) -> None:
        r = N.calcular(_ejes())
        self.assertEqual((r["nivel"], r["subnivel"], r["veredicto_riesgo"]), ("verde", None, "pasa"))

    def test_un_amarillo_es_amarillo_a_con_revision(self) -> None:
        r = N.calcular(_ejes(p="P2s"))
        self.assertEqual((r["nivel"], r["subnivel"], r["veredicto_riesgo"]), ("amarillo", "A", "pasa_con_revision"))

    def test_dos_amarillos_son_amarillo_b_con_gate(self) -> None:
        r = N.calcular(_ejes(p="P2s", n="N1s"))
        self.assertEqual((r["nivel"], r["subnivel"], r["veredicto_riesgo"]), ("amarillo", "B", "pasa_con_gate"))

    def test_zona_gris_sube_el_amarillo_a_a_gate(self) -> None:
        r = N.calcular(_ejes(c="C2"), zona_gris=True)
        self.assertEqual((r["subnivel"], r["veredicto_riesgo"]), ("A", "pasa_con_gate"))

    def test_un_rojo_bloquea_salvo_que_haya_reencuadre(self) -> None:
        self.assertEqual(N.calcular(_ejes(p="P3"))["veredicto_riesgo"], "bloquea")
        self.assertEqual(N.calcular(_ejes(p="P3"), hay_reencuadre=True)["veredicto_riesgo"], "reformular")
        self.assertEqual(N.calcular(_ejes(p="P3"), hay_reencuadre=True)["nivel"], "rojo")

    def test_un_rojo_nunca_se_suaviza_por_tener_otros_ejes_verdes(self) -> None:
        for eje, codigo in (("P", "P2n"), ("C", "C3"), ("E", "E2"), ("N", "N2")):
            with self.subTest(eje=eje):
                ejes = _ejes()
                ejes[eje] = codigo
                self.assertEqual(N.calcular(ejes)["nivel"], "rojo")

    def test_fuera_de_macro_siempre_bloquea_sin_nivel(self) -> None:
        r = N.calcular(_ejes(n="N0"), fuera_de_macro=True)
        self.assertEqual((r["nivel"], r["subnivel"], r["veredicto_riesgo"]), (None, None, "bloquea"))

    def test_el_nivel_es_monotono_el_peor_eje_manda_en_todas_las_combinaciones(self) -> None:
        for combo in itertools.product(*(N.ESCALA[e] for e in N.EJES)):
            ejes = dict(zip(N.EJES, combo))
            if ejes["N"] == "N0":
                continue
            colores = [N.COLOR[c] for c in combo]
            esperado = max(colores, key=N.ORDEN.__getitem__)
            self.assertEqual(N.calcular(ejes)["nivel"], esperado, ejes)

    def test_la_tabla_cubre_todos_los_codigos_de_la_escala(self) -> None:
        for escala in N.ESCALA.values():
            for codigo in escala:
                self.assertIn(codigo, N.COLOR)


class PruebaFallaCerrado(unittest.TestCase):
    def test_codigo_desconocido(self) -> None:
        with self.assertRaises(ErrorValidacion):
            N.calcular(_ejes(p="P9"))

    def test_eje_ausente(self) -> None:
        ejes = _ejes()
        del ejes["E"]
        with self.assertRaises(ErrorValidacion):
            N.calcular(ejes)

    def test_eje_none_o_vacio(self) -> None:
        for malo in (None, "", 0, "p1"):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                N.calcular(_ejes(c=malo))

    def test_ejes_extra_se_rechazan(self) -> None:
        with self.assertRaises(ErrorValidacion):
            N.calcular({**_ejes(), "X": "X1"})

    def test_no_es_un_objeto(self) -> None:
        for malo in (None, [], "P1C1E0N1", 7):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                N.calcular(malo)  # type: ignore[arg-type]

    def test_n0_dentro_de_macro_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            N.calcular(_ejes(n="N0"))

    def test_el_error_de_validacion_sale_con_codigo_3(self) -> None:
        try:
            N.calcular(_ejes(p="P9"))
        except ErrorValidacion as exc:
            self.assertEqual(exc.codigo_salida, 3)


class PruebaRiesgoDeCandidato(unittest.TestCase):
    def test_devuelve_el_bloque_completo_con_version(self) -> None:
        r = N.riesgo_de_candidato(_ejes(p="P2s"), categoria="educacion", claims=["guía"], angulo="ahorro de tiempo")
        self.assertEqual(r["nivel"], "amarillo")
        self.assertEqual(r["subnivel"], "A")
        self.assertEqual(r["ejes_codigo"], _ejes(p="P2s"))
        self.assertEqual(r["version_tabla"], N.VERSION_TABLA)
        self.assertEqual((r["categoria"], r["claims"], r["angulo"]), ("educacion", ["guía"], "ahorro de tiempo"))

    def test_los_extras_no_influyen_en_el_nivel_ni_lo_pisan(self) -> None:
        r = N.riesgo_de_candidato(_ejes(p="P3"), nivel="verde", subnivel="A", version_tabla="otra")
        self.assertEqual((r["nivel"], r["subnivel"], r["version_tabla"]), ("rojo", None, N.VERSION_TABLA))

    def test_no_muta_la_entrada(self) -> None:
        ejes = _ejes()
        copia = dict(ejes)
        N.riesgo_de_candidato(ejes)
        self.assertEqual(ejes, copia)

    def test_ejes_invalidos_fallan_cerrado(self) -> None:
        with self.assertRaises(ErrorValidacion):
            N.riesgo_de_candidato(_ejes(n="N9"))


class PruebaCli(unittest.TestCase):
    def _correr(self, *args: str) -> tuple[int, str, str]:
        salida, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(err):
            codigo = N.main(list(args))
        return codigo, salida.getvalue(), err.getvalue()

    def test_json(self) -> None:
        codigo, out, _ = self._correr("--P", "P2s", "--C", "C1", "--E", "E0", "--N", "N1s", "--json")
        self.assertEqual(codigo, 0)
        datos = json.loads(out)
        self.assertEqual((datos["nivel"], datos["subnivel"]), ("amarillo", "B"))

    def test_faltan_ejes_es_uso_incorrecto(self) -> None:
        self.assertEqual(self._correr("--P", "P1")[0], 2)

    def test_codigo_fuera_de_la_escala_es_uso_incorrecto(self) -> None:
        self.assertEqual(self._correr("--P", "P9", "--C", "C1", "--E", "E0", "--N", "N1")[0], 2)

    def test_n0_en_macro_sale_con_3(self) -> None:
        codigo, _, err = self._correr("--P", "P1", "--C", "C1", "--E", "E0", "--N", "N0")
        self.assertEqual(codigo, 3, err)

    @unittest.skipUnless(SUITE.is_file(), "sin la suite")
    def test_suite_por_cli_sale_0(self) -> None:
        codigo, out, _ = self._correr("--suite", str(SUITE))
        self.assertEqual(codigo, 0)
        self.assertIn("0 discrepancias", out)

    def test_suite_inexistente_es_uso_incorrecto(self) -> None:
        self.assertEqual(self._correr("--suite", "/no/existe.yaml")[0], 2)


if __name__ == "__main__":
    unittest.main()
