"""Pruebas de ``scripts.creativos.match_landing`` (K01: message match contra oferta.json y la landing)."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from engine import comun
from engine.errores import ErrorValidacion

from scripts.creativos import match_landing

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "creativos"
RAIZ = FIXTURES / "raiz_match"
OFERTA_ID = "OF-202611-01"


def _oferta() -> dict:
    return comun.cargar_json(RAIZ / "ofertas" / OFERTA_ID / "03-oferta" / "oferta.json")


def _html() -> str:
    return (RAIZ / "ofertas" / OFERTA_ID / "05-landing" / "sitio" / "index.html").read_text(encoding="utf-8")


def _pieza(ruta: str) -> dict:
    return comun.cargar_json(FIXTURES / ruta)


class PruebaComparar(unittest.TestCase):
    def test_pieza_sin_diferencias(self) -> None:
        diferencias = match_landing.comparar(_pieza("pieza_ok.json"), _oferta(), _html())
        self.assertEqual(diferencias, [])

    def test_claim_id_no_permitido_es_una_diferencia(self) -> None:
        diferencias = match_landing.comparar(_pieza("pieza_claim_no_permitido.json"), _oferta(), _html())
        campos = {d.campo for d in diferencias}
        self.assertIn("claim_ids", campos)

    def test_precio_distinto_en_la_pieza_es_una_diferencia(self) -> None:
        pieza = {**_pieza("pieza_ok.json"), "precio": {"monto": 999, "moneda": "EUR"}}
        diferencias = match_landing.comparar(pieza, _oferta(), _html())
        campos = {d.campo for d in diferencias}
        self.assertIn("pieza.precio.monto", campos)

    def test_precio_distinto_entre_landing_y_oferta_es_una_diferencia(self) -> None:
        oferta = _oferta()
        oferta["precio"]["lista"]["monto"] = 1234
        diferencias = match_landing.comparar(_pieza("pieza_ok.json"), oferta, _html())
        campos = {d.campo for d in diferencias}
        self.assertIn("precio.monto", campos)

    def test_moneda_distinta_es_una_diferencia(self) -> None:
        oferta = _oferta()
        oferta["precio"]["lista"]["moneda"] = "USD"
        diferencias = match_landing.comparar(_pieza("pieza_ok.json"), oferta, _html())
        campos = {d.campo for d in diferencias}
        self.assertIn("precio.moneda", campos)

    def test_garantia_distinta_es_una_diferencia(self) -> None:
        oferta = _oferta()
        oferta["garantia"]["dias"] = 30
        diferencias = match_landing.comparar(_pieza("pieza_ok.json"), oferta, _html())
        campos = {d.campo for d in diferencias}
        self.assertIn("garantia.dias", campos)

    def test_marca_distinta_es_una_diferencia(self) -> None:
        oferta = _oferta()
        oferta["marca"]["nombre"] = "Otra marca"
        diferencias = match_landing.comparar(_pieza("pieza_ok.json"), oferta, _html())
        campos = {d.campo for d in diferencias}
        self.assertIn("marca.nombre", campos)

    def test_sin_body_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            match_landing.comparar(_pieza("pieza_ok.json"), _oferta(), "<html><p>sin body</p></html>")


class PruebaCLI(unittest.TestCase):
    def test_cli_sin_diferencias_sale_cero(self) -> None:
        codigo = match_landing.main(["--oferta", OFERTA_ID, "--pieza", str(FIXTURES / "pieza_ok.json"), "--raiz", str(RAIZ)])
        self.assertEqual(codigo, 0)

    def test_cli_con_diferencias_sale_tres_y_lista_el_campo(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            codigo = match_landing.main([
                "--oferta", OFERTA_ID, "--pieza", str(FIXTURES / "pieza_claim_no_permitido.json"), "--raiz", str(RAIZ), "--json",
            ])
        self.assertEqual(codigo, 3)
        datos = json.loads(buf.getvalue().splitlines()[0])
        campos = {d["campo"] for d in datos["datos"]["diferencias"]}
        self.assertIn("claim_ids", campos)


if __name__ == "__main__":
    unittest.main()
