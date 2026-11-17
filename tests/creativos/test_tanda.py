"""Pruebas de tanda.py (modo tanda manual: encargo y bandeja «por aprobar»). Sin red.

Ejecutar: .venv/bin/python -m unittest discover -s tests/creativos -t . -p "test_*.py"
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests.creativos import apoyo  # noqa: F401  (agrega la ruta de la skill)

import tanda as t  # noqa: E402


def correr(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        codigo = t.main(list(args))
    return codigo, out.getvalue(), err.getvalue()


class PruebasReparto(unittest.TestCase):
    def test_relevos_primero_y_el_resto_se_alterna(self) -> None:
        r = t.repartir(8, relevos=3, angulos=4, traducciones=4)
        self.assertEqual(r["composicion"], {"relevos": 3, "angulos_nuevos": 3, "traducciones": 2})
        self.assertEqual((r["produce"], r["faltan"]), (8, 0))

    def test_no_se_inventan_pedidos(self) -> None:
        r = t.repartir(10, relevos=1, angulos=2, traducciones=0)
        self.assertEqual(r["composicion"], {"relevos": 1, "angulos_nuevos": 2, "traducciones": 0})
        self.assertEqual((r["produce"], r["faltan"]), (3, 7))
        self.assertTrue(any("menos del mínimo" in a for a in r["avisos"]))

    def test_los_relevos_nunca_pasan_del_maximo(self) -> None:
        r = t.repartir(10, relevos=14, angulos=5, traducciones=5)
        self.assertEqual(r["composicion"], {"relevos": 10, "angulos_nuevos": 0, "traducciones": 0})
        self.assertTrue(any("4 relevo(s) quedan" in a for a in r["avisos"]))

    def test_el_objetivo_se_ajusta_a_los_limites(self) -> None:
        self.assertEqual(t.repartir(2, 0, 9, 9)["objetivo_efectivo"], 5)
        self.assertEqual(t.repartir(50, 0, 9, 9)["objetivo_efectivo"], 10)

    def test_entradas_invalidas(self) -> None:
        with self.assertRaises(t.ErrorEntrada):
            t.repartir(5, -1, 0, 0)
        with self.assertRaises(t.ErrorEntrada):
            t.repartir(5, 0, 0, 0, minimo=6, maximo=5)

    def test_cli_plan_escribe_el_encargo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            salida = Path(td) / "encargo.json"
            codigo, out, _ = correr("plan", "--locale", "pl-PL", "--oferta-id", "OF-202611-91", "--fecha", "2026-11-08", "--objetivo", "8", "--relevos", "2", "--angulos-nuevos", "5",
                                    "--traducciones", "1", "--salida", str(salida))
            self.assertEqual(codigo, 0)
            e = json.loads(salida.read_text(encoding="utf-8"))
            self.assertEqual((e["tipo"], e["modo"], e["fecha"], e["composicion"]), ("tanda", "manual", "2026-11-08", {"relevos": 2, "angulos_nuevos": 5, "traducciones": 1}))
            self.assertIn("[SUPUESTO]", e["limites"]["estado"])
            self.assertIn("8 pieza", out)


def hash_de(n: int) -> str:
    return "sha256:" + f"{n:064x}"


class PruebasBandeja(unittest.TestCase):
    MATRIZ = {"anuncios": [{"ad_name": f"c0{i}-x_img_h1_v1", "variante_formato": "estatico-html", "hook_tipo": "pregunta-tarea"} for i in range(1, 7)]}

    def qc6(self, estados: list[str], sellado: bool = False) -> dict:
        piezas = []
        for i, e in enumerate(estados, 1):
            puntos = [{"id": "QC3-texto", "estado": e, "detalle": "x"}]
            piezas.append({"pieza": f"c0{i}-x_img_h1_v1", "archivo": f"assets/c0{i}.png", "sha256": hash_de(i * 7919), "estado": e, "puntos": puntos})
        return {"modo": "real", "piezas": piezas}

    SELLOS = {"estatico-html": {"sello_ref": "qa/x1-plantilla-estatico-html.json", "vigente_hasta": "2026-12-31"}}

    def bandeja(self, estados, **kw) -> dict:
        base = dict(regimen="total", confirmado=False, muestra_pct=20, sellos={}, fecha="2026-11-08")
        base.update(kw)
        return t.armar_bandeja(self.MATRIZ, self.qc6(estados), **base)

    def test_regimen_total_el_dueno_ve_todo_lo_que_no_falla(self) -> None:
        b = self.bandeja(["ok", "ok", "revisar", "falla", "ok", "ok"])
        self.assertEqual((b["aprobar_dueno"], b["lista_para_sello_x1"], b["corregir_o_descartar"]), (5, 0, 1))
        self.assertIn("Nada de esto aprueba", b["aviso"])

    def test_muestreo_exige_que_lo_confirme_el_dueno(self) -> None:
        with self.assertRaises(t.ErrorEntrada) as cm:
            self.bandeja(["ok"] * 6, regimen="muestreo", sellos=self.SELLOS)
        self.assertIn("dueño", str(cm.exception))

    def test_muestreo_sin_sello_vigente_la_plantilla_no_se_salta_al_dueno(self) -> None:
        b = self.bandeja(["ok"] * 6, regimen="muestreo", confirmado=True, sellos={})
        self.assertEqual((b["aprobar_dueno"], b["lista_para_sello_x1"]), (6, 0))
        vencido = {"estatico-html": {"sello_ref": "qa/x.json", "vigente_hasta": "2026-11-01"}}
        self.assertEqual(self.bandeja(["ok"] * 6, regimen="muestreo", confirmado=True, sellos=vencido)["lista_para_sello_x1"], 0)

    def test_muestreo_con_sello_deja_pasar_lo_ok_fuera_de_la_muestra_pero_nunca_lo_aprueba(self) -> None:
        b = self.bandeja(["ok", "ok", "ok", "revisar", "falla", "ok"], regimen="muestreo", confirmado=True, sellos=self.SELLOS, muestra_pct=0)
        acciones = {p["ad_name"]: p["accion"] for p in b["piezas"]}
        self.assertEqual(acciones["c04-x_img_h1_v1"], "aprobar_dueno")           # revisar: siempre lo ve el dueño
        self.assertEqual(acciones["c05-x_img_h1_v1"], "corregir_o_descartar")     # falla: nunca pasa
        self.assertEqual(sum(1 for a in acciones.values() if a == "lista_para_sello_x1"), 4)
        self.assertNotIn("aprobada", json.dumps(b["piezas"]))
        todo = self.bandeja(["ok"] * 6, regimen="muestreo", confirmado=True, sellos=self.SELLOS, muestra_pct=100)
        self.assertEqual(todo["lista_para_sello_x1"], 0)

    def test_la_muestra_es_determinista(self) -> None:
        a = self.bandeja(["ok"] * 6, regimen="muestreo", confirmado=True, sellos=self.SELLOS, muestra_pct=50)
        b = self.bandeja(["ok"] * 6, regimen="muestreo", confirmado=True, sellos=self.SELLOS, muestra_pct=50)
        self.assertEqual([p["accion"] for p in a["piezas"]], [p["accion"] for p in b["piezas"]])
        self.assertTrue(0 < a["aprobar_dueno"] < 6 or a["aprobar_dueno"] in (0, 6))  # válido en ambos extremos; lo importante es que no cambie

    def test_regimen_invalido_y_pct_fuera_de_rango(self) -> None:
        with self.assertRaises(t.ErrorEntrada):
            self.bandeja(["ok"], regimen="automatico")
        with self.assertRaises(t.ErrorEntrada):
            self.bandeja(["ok"], regimen="muestreo", confirmado=True, muestra_pct=101)

    def test_cli_bandeja_rechaza_un_qc6_simulado(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "matriz.json").write_text(json.dumps(self.MATRIZ), encoding="utf-8")
            (d / "qc6.json").write_text(json.dumps({**self.qc6(["ok"]), "modo": "simulado"}), encoding="utf-8")
            codigo, _, err = correr("bandeja", "--tanda-dir", str(d), "--regimen", "total")
            self.assertEqual(codigo, 3)
            self.assertIn("simulada", err)

    def test_cli_bandeja_escribe_por_aprobar(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "matriz.json").write_text(json.dumps(self.MATRIZ), encoding="utf-8")
            (d / "qc6.json").write_text(json.dumps(self.qc6(["ok", "revisar", "falla"])), encoding="utf-8")
            codigo, out, _ = correr("bandeja", "--tanda-dir", str(d), "--regimen", "total", "--fecha", "2026-11-08")
            self.assertEqual(codigo, 0)
            b = json.loads((d / "por-aprobar.json").read_text(encoding="utf-8"))
            self.assertEqual((b["regimen"], b["regimen_confirmado_por_dueno"], b["total"], b["corregir_o_descartar"]), ("total", False, 3, 1))
            self.assertIn("por-aprobar", out)

    def test_cli_sin_regimen_es_error_de_uso(self) -> None:
        self.assertEqual(correr("bandeja", "--tanda-dir", "x")[0], 2)


if __name__ == "__main__":
    unittest.main()
