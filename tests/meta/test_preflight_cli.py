"""CLI de meta.preflight (A3, ola 2 B5b): ``python -m meta.preflight`` sobre hechos ya leídos."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from meta import preflight
from tests.engine.apoyo import OFERTA, PruebaBase, crear_empresa
from tests.meta.test_preflight import _campana, _entradas_base

_HASH = "sha256:" + "c" * 64


class PruebaCliPreflight(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        self.campana_ruta = self.tmp / "campana.json"
        campana = dict(_campana())
        campana["oferta_id"] = OFERTA
        campana["hash_config"] = _HASH
        self.campana_ruta.write_text(json.dumps(campana), encoding="utf-8")
        self.entradas_ruta = self.tmp / "entradas.json"
        self.entradas_ruta.write_text(json.dumps(_entradas_base()), encoding="utf-8")

    def _correr(self, argv: list[str]) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = preflight.main(argv)
        return codigo, salida.getvalue()

    def test_corre_los_24_checks_y_sale_0_sea_cual_sea_el_semaforo(self) -> None:
        codigo, salida = self._correr([
            "--oferta", OFERTA, "--entradas", str(self.entradas_ruta), "--campana", str(self.campana_ruta),
            "--raiz", str(self.emp.raiz), "--ahora", "2026-11-09T07:00:00Z", "--json",
        ])
        self.assertEqual(codigo, 0, salida)
        datos = json.loads(salida)["datos"]
        self.assertEqual(set(datos["checks"]), set(preflight.CHECKS))
        self.assertEqual(datos["hash_config"], _HASH)

    def test_salida_escribe_el_archivo(self) -> None:
        destino = self.tmp / "preflight.json"
        codigo, _ = self._correr([
            "--oferta", OFERTA, "--entradas", str(self.entradas_ruta), "--campana", str(self.campana_ruta),
            "--salida", str(destino), "--raiz", str(self.emp.raiz), "--ahora", "2026-11-09T07:00:00Z",
        ])
        self.assertEqual(codigo, 0)
        self.assertTrue(destino.is_file())
        self.assertEqual(json.loads(destino.read_text(encoding="utf-8"))["oferta_id"], OFERTA)

    def test_oferta_que_no_coincide_con_la_campana_sale_2(self) -> None:
        codigo, _ = self._correr([
            "--oferta", "OF-202611-99", "--entradas", str(self.entradas_ruta), "--campana", str(self.campana_ruta),
            "--raiz", str(self.emp.raiz), "--ahora", "2026-11-09T07:00:00Z",
        ])
        self.assertEqual(codigo, 2)

    def test_sin_hash_config_en_ningun_lado_sale_2(self) -> None:
        campana_sin_hash = dict(_campana())
        campana_sin_hash["oferta_id"] = OFERTA
        ruta = self.tmp / "campana_sin_hash.json"
        ruta.write_text(json.dumps(campana_sin_hash), encoding="utf-8")
        codigo, _ = self._correr([
            "--oferta", OFERTA, "--entradas", str(self.entradas_ruta), "--campana", str(ruta),
            "--raiz", str(self.emp.raiz), "--ahora", "2026-11-09T07:00:00Z",
        ])
        self.assertEqual(codigo, 2)


if __name__ == "__main__":
    unittest.main()
