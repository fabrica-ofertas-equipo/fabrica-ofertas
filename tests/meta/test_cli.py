"""Pruebas de los 4 CLI de B5 (envoltorios en scripts/): dry-run, fixture end-to-end y --modo live rehusado."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from meta import activar as activar_mod
from meta import crear as crear_mod
from meta import pausar as pausar_mod
from meta import subir_presupuesto as subir_mod
from tests.engine.apoyo import HASH_CONFIG, OFERTA, PruebaBase, crear_empresa

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "meta"
_CAMPANA = FIXTURES / "campana_borrador.json"
_CREATIVOS = FIXTURES / "creativos.json"
_REGLAS_CREAR = FIXTURES / "reglas_crear.json"


class BaseCli(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="desarrollo")

    def correr(self, main, args: list[str]) -> tuple[int, dict]:
        """Corre ``main`` y decodifica stdout como JSON; si la CLI falló, el mensaje fue a stderr (sin JSON)."""
        import contextlib
        import io

        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = main(args)
        texto = salida.getvalue()
        return codigo, (json.loads(texto) if texto.strip() else {"stderr": error.getvalue()})


class PruebaMetaCrearCli(BaseCli):
    def test_dry_run_imprime_el_payload_sin_tocar_nada(self) -> None:
        codigo, datos = self.correr(crear_mod.main, [
            "--oferta", OFERTA, "--campana", str(_CAMPANA), "--creativos", str(_CREATIVOS),
            "--ad-account", "act_100000000000001", "--pixel-id", "PX1", "--json",
        ])
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["modo"], "dry_run")
        self.assertEqual(datos["datos"]["campaign"]["status"], "PAUSED")

    def test_modo_live_se_rechaza_alcance_de_la_noche(self) -> None:
        codigo, datos = self.correr(crear_mod.main, [
            "--oferta", OFERTA, "--campana", str(_CAMPANA), "--creativos", str(_CREATIVOS),
            "--ad-account", "act_100000000000001", "--pixel-id", "PX1", "--modo", "live", "--json",
        ])
        self.assertEqual(codigo, 4)

    def test_modo_fixture_crea_y_escribe_ids_meta(self) -> None:
        salida = self.tmp / "ids_meta.json"
        codigo, datos = self.correr(crear_mod.main, [
            "--oferta", OFERTA, "--campana", str(_CAMPANA), "--creativos", str(_CREATIVOS),
            "--ad-account", "act_100000000000001", "--pixel-id", "PX1", "--modo", "fixture",
            "--fixture", str(_REGLAS_CREAR), "--raiz", str(self.emp.raiz), "--salida", str(salida), "--json",
        ])
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(datos["datos"]["campaign_id"], "1001")
        self.assertTrue(salida.is_file())

    def test_oferta_que_no_coincide_con_la_campana_se_rechaza(self) -> None:
        codigo, datos = self.correr(crear_mod.main, [
            "--oferta", "OF-202611-99", "--campana", str(_CAMPANA), "--creativos", str(_CREATIVOS),
            "--ad-account", "act_1", "--pixel-id", "PX1", "--json",
        ])
        self.assertEqual(codigo, 2)


class PruebaMetaActivarCli(BaseCli):
    def _campana_minima(self) -> Path:
        """``campana.json`` mínimo: las pruebas de dry-run y de ``--modo live`` no llegan a leer sus
        demás campos (A5 solo re-lee el estado vivo en ``--modo fixture``/``live``, no en dry-run)."""
        ruta = self.tmp / "campana.json"
        ruta.write_text(json.dumps({"oferta_id": OFERTA, "hash_config": HASH_CONFIG}), encoding="utf-8")
        return ruta

    def test_dry_run_no_llama_a_guard_ni_a_meta(self) -> None:
        ids_meta = self.tmp / "ids_meta.json"
        ids_meta.write_text(json.dumps({"campaign_id": "1", "adset_ids": ["2"], "ad_ids": ["3"]}), encoding="utf-8")
        cuenta = self.tmp / "cuenta.json"
        cuenta.write_text(json.dumps({"activas": [], "gasto_vitalicio_minor": 0}), encoding="utf-8")
        codigo, datos = self.correr(activar_mod.main, [
            "--oferta", OFERTA, "--campana", str(self._campana_minima()), "--ids-meta", str(ids_meta),
            "--hash-config", HASH_CONFIG, "--cuenta", str(cuenta), "--monto", "5000", "--moneda", "EUR", "--json",
        ])
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["modo"], "dry_run")
        self.assertEqual(sorted(datos["datos"]["object_ids"]), ["1", "2", "3"])

    def test_modo_live_se_rechaza(self) -> None:
        ids_meta = self.tmp / "ids_meta.json"
        ids_meta.write_text(json.dumps({"campaign_id": "1", "adset_ids": ["2"], "ad_ids": ["3"]}), encoding="utf-8")
        cuenta = self.tmp / "cuenta.json"
        cuenta.write_text(json.dumps({"activas": [], "gasto_vitalicio_minor": 0}), encoding="utf-8")
        codigo, datos = self.correr(activar_mod.main, [
            "--oferta", OFERTA, "--campana", str(self._campana_minima()), "--ids-meta", str(ids_meta),
            "--hash-config", HASH_CONFIG, "--cuenta", str(cuenta), "--monto", "5000", "--moneda", "EUR",
            "--modo", "live", "--json",
        ])
        self.assertEqual(codigo, 4)


class PruebaMetaPausarCli(BaseCli):
    def test_dry_run(self) -> None:
        codigo, datos = self.correr(pausar_mod.main, ["--campana-id", "123", "--json"])
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["modo"], "dry_run")

    def test_modo_live_se_rechaza(self) -> None:
        codigo, datos = self.correr(pausar_mod.main, ["--campana-id", "123", "--modo", "live", "--json"])
        self.assertEqual(codigo, 4)


class PruebaSubirPresupuestoCli(BaseCli):
    def test_dry_run(self) -> None:
        cuenta = self.tmp / "cuenta.json"
        cuenta.write_text(json.dumps({"activas": [], "gasto_vitalicio_minor": 0}), encoding="utf-8")
        codigo, datos = self.correr(subir_mod.main, [
            "--oferta", OFERTA, "--object-id", "2", "--monto", "600", "--moneda", "EUR", "--cuenta", str(cuenta), "--json",
        ])
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["modo"], "dry_run")

    def test_modo_live_se_rechaza(self) -> None:
        cuenta = self.tmp / "cuenta.json"
        cuenta.write_text(json.dumps({"activas": [], "gasto_vitalicio_minor": 0}), encoding="utf-8")
        codigo, datos = self.correr(subir_mod.main, [
            "--oferta", OFERTA, "--object-id", "2", "--monto", "600", "--moneda", "EUR", "--cuenta", str(cuenta), "--modo", "live", "--json",
        ])
        self.assertEqual(codigo, 4)


if __name__ == "__main__":
    unittest.main()
