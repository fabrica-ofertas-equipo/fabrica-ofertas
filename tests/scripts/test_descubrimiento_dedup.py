"""Pruebas de `scripts.descubrimiento.dedup`: similitud_memoria determinista (D1 §3.2)."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine.errores import ErrorValidacion
from scripts.descubrimiento import dedup as D


def _candidato(**over) -> dict:
    base = {"audiencia": "madres que vuelven a trabajar", "resultado": "conseguir un empleo estable",
           "obstaculo": "falta de experiencia reciente", "formato": "plantilla"}
    base.update(over)
    return base


class PruebaSimilitudTexto(unittest.TestCase):
    def test_textos_identicos_dan_1(self) -> None:
        self.assertEqual(D.similitud_texto("ahorrar cada mes", "ahorrar cada mes"), Decimal("1.0000"))

    def test_textos_sin_overlap_dan_0(self) -> None:
        self.assertEqual(D.similitud_texto("ahorrar dinero", "dormir mejor"), Decimal("0.0000"))

    def test_textos_parcialmente_iguales_dan_fraccion(self) -> None:
        s = D.similitud_texto("ahorrar cada mes", "ahorrar cada semana")
        self.assertGreater(s, Decimal("0"))
        self.assertLess(s, Decimal("1"))

    def test_insensible_a_acentos_y_mayusculas(self) -> None:
        self.assertEqual(D.similitud_texto("Ahorro Personal", "ahorro personal"), Decimal("1.0000"))

    def test_campo_vacio_en_cualquier_lado_es_none(self) -> None:
        self.assertIsNone(D.similitud_texto("", "ahorro"))
        self.assertIsNone(D.similitud_texto(None, "ahorro"))
        self.assertIsNone(D.similitud_texto("ahorro", None))


class PruebaSimilitudPar(unittest.TestCase):
    def test_mismo_problema_categorico_fuerza_1(self) -> None:
        item = {"id": "CAND-99", "audiencia": "algo totalmente distinto", "mismo_problema_categorico": True}
        self.assertEqual(D.similitud_par(_candidato(), item), Decimal("1"))

    def test_candidato_identico_da_1(self) -> None:
        item = {"id": "CAND-01", **_candidato()}
        self.assertEqual(D.similitud_par(_candidato(), item), Decimal("1.0000"))

    def test_sin_ningun_campo_en_comun_da_0(self) -> None:
        item = {"id": "CAND-02"}
        self.assertEqual(D.similitud_par(_candidato(), item), Decimal("0"))

    def test_promedia_solo_los_campos_con_dato_en_ambos(self) -> None:
        item = {"id": "CAND-03", "audiencia": _candidato()["audiencia"]}  # solo un campo en común
        self.assertEqual(D.similitud_par(_candidato(), item), Decimal("1.0000"))


class PruebaSimilitudMemoria(unittest.TestCase):
    def test_memoria_vacia_da_cero_y_con_none(self) -> None:
        r = D.similitud_memoria(_candidato(), [])
        self.assertEqual(r, {"max": "0", "con": None})

    def test_devuelve_el_maximo_y_su_id(self) -> None:
        memoria = [
            {"id": "CAND-01", "audiencia": "totalmente distinto"},
            {"id": "CAND-02", **_candidato()},
        ]
        r = D.similitud_memoria(_candidato(), memoria)
        self.assertEqual(r["con"], "CAND-02")
        self.assertEqual(r["max"], "1.0000")

    def test_candidato_no_es_objeto_falla_cerrado(self) -> None:
        with self.assertRaises(ErrorValidacion):
            D.similitud_memoria("no es un objeto", [])  # type: ignore[arg-type]

    def test_item_de_memoria_no_objeto_falla_cerrado(self) -> None:
        with self.assertRaises(ErrorValidacion):
            D.similitud_memoria(_candidato(), ["no es un objeto"])  # type: ignore[list-item]


class PruebaCli(unittest.TestCase):
    def test_calcular_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "candidato.json").write_text(json.dumps(_candidato()), encoding="utf-8")
            (base / "memoria.json").write_text(json.dumps([{"id": "CAND-01", **_candidato()}]), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                codigo = D.main(["calcular", "--candidato", str(base / "candidato.json"),
                                "--memoria", str(base / "memoria.json"), "--json"])
            self.assertEqual(codigo, 0)
            self.assertEqual(json.loads(buf.getvalue())["con"], "CAND-01")

    def test_memoria_no_es_lista_es_error(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "candidato.json").write_text(json.dumps(_candidato()), encoding="utf-8")
            (base / "memoria.json").write_text(json.dumps({"no": "es lista"}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                codigo = D.main(["calcular", "--candidato", str(base / "candidato.json"),
                                "--memoria", str(base / "memoria.json")])
            self.assertEqual(codigo, 3)


if __name__ == "__main__":
    unittest.main()
