"""Pruebas de `scripts.descubrimiento.nichos`: validador de `nichos.yaml` (interfaces §3.4)."""
from __future__ import annotations

import contextlib
import copy
import io
import unittest
from pathlib import Path

from engine.comun import cargar_yaml
from engine.errores import ErrorValidacion
from scripts.descubrimiento import nichos as N

RAIZ = Path(__file__).resolve().parents[2]
SEMILLA = RAIZ / "tests" / "fixtures" / "descubrimiento" / "nichos_semilla.yaml"


def _doc_minimo() -> dict:
    return {
        "arbol": [{
            "macro_nicho": "dinero", "nichos": [{
                "nicho_id": "ahorro-personal", "microsegmentos": [{
                    "id": "presupuesto-mensual", "macro_secundario": None, "tanda": 1, "estado": "semilla",
                }],
            }],
        }],
        "semillas_fuera_de_marco": [
            {"id": "crochet-tejido", "motivo_macro": "hobby", "estado": "registrada_no_sembrada"},
        ],
    }


class PruebaValidarNichos(unittest.TestCase):
    def test_documento_minimo_valido_no_tiene_errores(self) -> None:
        self.assertEqual(N.validar_nichos(_doc_minimo()), [])

    def test_la_semilla_real_de_92_hojas_no_tiene_errores(self) -> None:
        self.assertTrue(SEMILLA.is_file(), "falta el fixture de la semilla (ver README)")
        doc = cargar_yaml(SEMILLA)
        self.assertEqual(N.validar_nichos(doc), [])
        self.assertGreaterEqual(len(N.hojas(doc)), 90)

    def test_macro_nicho_desconocido_es_error(self) -> None:
        doc = _doc_minimo()
        doc["arbol"][0]["macro_nicho"] = "hobbies"
        self.assertTrue(any("macro_nicho" in e for e in N.validar_nichos(doc)))

    def test_macro_nicho_fuera_de_los_permitidos_es_error(self) -> None:
        doc = _doc_minimo()
        errores = N.validar_nichos(doc, macro_nichos_permitidos=["salud"])
        self.assertTrue(any("macro_nichos_permitidos" in e for e in errores))

    def test_nicho_id_no_kebab_es_error(self) -> None:
        doc = _doc_minimo()
        doc["arbol"][0]["nichos"][0]["nicho_id"] = "Ahorro Personal"
        self.assertTrue(any("nicho_id" in e for e in N.validar_nichos(doc)))

    def test_hoja_id_repetida_es_error(self) -> None:
        doc = _doc_minimo()
        hoja = copy.deepcopy(doc["arbol"][0]["nichos"][0]["microsegmentos"][0])
        doc["arbol"][0]["nichos"][0]["microsegmentos"].append(hoja)
        errores = N.validar_nichos(doc)
        self.assertTrue(any("repetido" in e for e in errores))

    def test_macro_secundario_igual_al_primario_es_error(self) -> None:
        doc = _doc_minimo()
        doc["arbol"][0]["nichos"][0]["microsegmentos"][0]["macro_secundario"] = "dinero"
        errores = N.validar_nichos(doc)
        self.assertTrue(any("no puede igualar" in e for e in errores))

    def test_tanda_invalida_es_error(self) -> None:
        doc = _doc_minimo()
        doc["arbol"][0]["nichos"][0]["microsegmentos"][0]["tanda"] = 0
        self.assertTrue(any("tanda" in e for e in N.validar_nichos(doc)))

    def test_fuera_de_marco_sembrada_a_la_vez_es_error(self) -> None:
        doc = _doc_minimo()
        doc["semillas_fuera_de_marco"][0]["id"] = "presupuesto-mensual"  # colisiona con la hoja sembrada
        errores = N.validar_nichos(doc)
        self.assertTrue(any("decisión 13" in e for e in errores))

    def test_fuera_de_marco_con_estado_distinto_es_error(self) -> None:
        doc = _doc_minimo()
        doc["semillas_fuera_de_marco"][0]["estado"] = "sembrada"
        errores = N.validar_nichos(doc)
        self.assertTrue(any("registrada_no_sembrada" in e for e in errores))

    def test_sin_arbol_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            N.validar_nichos({"otra_cosa": []})


class PruebaCli(unittest.TestCase):
    def test_semilla_real_sale_0(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            codigo = N.main(["validar", str(SEMILLA)])
        self.assertEqual(codigo, 0, buf.getvalue())

    def test_ruta_inexistente_es_uso_incorrecto(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            codigo = N.main(["validar", "/no/existe.yaml"])
        self.assertEqual(codigo, 2)


if __name__ == "__main__":
    unittest.main()
