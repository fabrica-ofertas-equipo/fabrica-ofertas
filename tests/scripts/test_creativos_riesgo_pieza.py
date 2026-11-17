"""Pruebas de ``scripts.creativos.riesgo_pieza`` (riesgo por pieza con la tabla única ejes→nivel)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.errores import ErrorUso, ErrorValidacion

from scripts.creativos import riesgo_pieza
from tests.scripts.test_creativos_comun import PruebaBase

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "creativos"


def _pieza(pid: str, p: str, c: str, e: str, n: str, **extra) -> dict:
    return {"id": pid, "ejes": {"P": p, "C": c, "E": e, "N": n}, **extra}


class PruebaNivelLanzableDe(unittest.TestCase):
    def test_verde(self) -> None:
        self.assertEqual(riesgo_pieza.nivel_lanzable_de("verde", None), "verde")

    def test_amarillo_con_subnivel(self) -> None:
        self.assertEqual(riesgo_pieza.nivel_lanzable_de("amarillo", "A"), "amarillo-a")
        self.assertEqual(riesgo_pieza.nivel_lanzable_de("amarillo", "B"), "amarillo-b")

    def test_rojo_o_indeterminado_no_mapea(self) -> None:
        self.assertIsNone(riesgo_pieza.nivel_lanzable_de("rojo", None))
        self.assertIsNone(riesgo_pieza.nivel_lanzable_de(None, None))


class PruebaClasificarPieza(unittest.TestCase):
    def test_coherente_cuando_es_igual(self) -> None:
        self.assertEqual(riesgo_pieza.clasificar_pieza("amarillo", "amarillo"), "coherente")

    def test_falso_verde_bloqueante_cuando_la_pieza_es_menor(self) -> None:
        self.assertEqual(riesgo_pieza.clasificar_pieza("verde", "amarillo"), "falso_verde_bloqueante")

    def test_mayor_revisar_cuando_la_pieza_es_mayor(self) -> None:
        self.assertEqual(riesgo_pieza.clasificar_pieza("rojo", "amarillo"), "mayor_revisar")

    def test_indeterminado_sin_nivel(self) -> None:
        self.assertEqual(riesgo_pieza.clasificar_pieza(None, "verde"), "indeterminado")

    def test_nivel_desconocido_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            riesgo_pieza.clasificar_pieza("azul", "verde")


class PruebaEvaluarPiezas(PruebaBase):
    def test_pieza_coherente_con_la_oferta_no_bloquea(self) -> None:
        piezas = [_pieza("c01_img_h1_v1", "P0", "C0", "E0", "N0", **{})]
        # N0 solo existe fuera de macro; se evita con N1 (todo candidato en macro es al menos N1).
        piezas = [_pieza("c01_img_h1_v1", "P0", "C0", "E0", "N1")]
        r = riesgo_pieza.evaluar_piezas(piezas, nivel_oferta="verde")
        self.assertEqual(r["piezas"][0]["nivel"], "verde")
        self.assertEqual(r["piezas"][0]["clasificacion"], "coherente")
        self.assertFalse(r["piezas"][0]["bloquea"])
        self.assertEqual(r["bloqueantes"], [])

    def test_pieza_mas_segura_que_la_oferta_es_falso_verde_bloqueante(self) -> None:
        piezas = [_pieza("c01_img_h1_v1", "P0", "C0", "E0", "N1")]  # verde
        r = riesgo_pieza.evaluar_piezas(piezas, nivel_oferta="amarillo")
        self.assertEqual(r["piezas"][0]["clasificacion"], "falso_verde_bloqueante")
        self.assertTrue(r["piezas"][0]["bloquea"])
        self.assertIn("falso verde", r["bloqueantes"][0])

    def test_pieza_roja_siempre_bloquea(self) -> None:
        piezas = [_pieza("c01_img_h1_v1", "P2n", "C0", "E0", "N1")]  # P2n -> rojo
        r = riesgo_pieza.evaluar_piezas(piezas, nivel_oferta="rojo")
        self.assertEqual(r["piezas"][0]["nivel"], "rojo")
        self.assertTrue(r["piezas"][0]["bloquea"])

    def test_excede_nivel_max_lanzable_bloquea_aunque_sea_coherente(self) -> None:
        piezas = [_pieza("c01_img_h1_v1", "P2s", "C0", "E0", "N1")]  # amarillo, 1 amarillo -> subnivel A
        r = riesgo_pieza.evaluar_piezas(piezas, nivel_oferta="amarillo", nivel_max_lanzable="verde")
        self.assertTrue(r["piezas"][0]["excede_nivel_max_lanzable"])
        self.assertTrue(r["piezas"][0]["bloquea"])

    def test_dentro_de_nivel_max_lanzable_no_bloquea_por_eso(self) -> None:
        piezas = [_pieza("c01_img_h1_v1", "P2s", "C0", "E0", "N1")]
        r = riesgo_pieza.evaluar_piezas(piezas, nivel_oferta="amarillo", nivel_max_lanzable="amarillo-b")
        self.assertFalse(r["piezas"][0]["excede_nivel_max_lanzable"])

    def test_sin_piezas_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            riesgo_pieza.evaluar_piezas([], nivel_oferta="verde")

    def test_pieza_sin_id_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            riesgo_pieza.evaluar_piezas([{"ejes": {"P": "P0", "C": "C0", "E": "E0", "N": "N1"}}], nivel_oferta="verde")

    def test_pieza_sin_ejes_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            riesgo_pieza.evaluar_piezas([{"id": "x"}], nivel_oferta="verde")


class PruebaCLI(PruebaBase):
    def test_cli_con_fixture_sale_cero_si_coherente(self) -> None:
        codigo = riesgo_pieza.main(["--piezas", str(FIXTURES / "piezas.json"), "--nivel-oferta", "verde"])
        self.assertEqual(codigo, 0)

    def test_cli_con_fixture_sale_tres_si_falso_verde(self) -> None:
        codigo = riesgo_pieza.main(["--piezas", str(FIXTURES / "piezas.json"), "--nivel-oferta", "amarillo"])
        self.assertEqual(codigo, 3)

    def test_cli_archivo_inexistente_es_uso(self) -> None:
        codigo = riesgo_pieza.main(["--piezas", str(FIXTURES / "no-existe.json"), "--nivel-oferta", "verde"])
        self.assertEqual(codigo, ErrorUso.codigo_salida)

    def test_cli_json_produce_una_linea(self) -> None:
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            riesgo_pieza.main(["--piezas", str(FIXTURES / "piezas.json"), "--nivel-oferta", "verde", "--json"])
        lineas = [l for l in buf.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(lineas), 1)
        datos = json.loads(lineas[0])
        self.assertIn("datos", datos)
        self.assertEqual(datos["codigo"], 0)


if __name__ == "__main__":
    unittest.main()
