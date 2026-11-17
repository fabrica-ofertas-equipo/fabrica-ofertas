"""``GET /api/gates`` (#/quien-decide): lectura confinada y de solo lectura de ``contratos/gates.json``.

Raíz temporal con fixtures (nunca ``empresa/`` ni ``ofertas/`` reales); el contrato real solo se LEE para comprobar que el endpoint lo refleja.
"""
from __future__ import annotations

import json
import os
import shutil
import unittest
from unittest import mock

from tests.dashboard.test_servidor_apoyo import HOSTIL, RAIZ_REPO, PruebaBase

GATES_MINI = {
    "schema_version": "1.1.0",
    "niveles": ["N0", "N1", "N2", "N3", "N4"],
    "entradas": {
        "etapa:D7": {"descripcion": "Armado de campaña (en borrador).", "gate": {"N0": "H", "N1": "H", "N2": "H", "N3": "S", "N4": "S"}},
        "accion:activar_campana": {"descripcion": "Activar campaña (D7).", "gate": {"N0": "H", "N1": "H", "N2": "H", "N3": "S", "N4": "S"}},
        "accion:aumentar_presupuesto_d8": {"descripcion": "Solo desde N3.", "gate": {"N0": "NA", "N1": "NA", "N2": "NA", "N3": "A", "N4": "A"}},
    },
}


class PruebaGates(PruebaBase):
    def poner_gates(self, doc: object = GATES_MINI) -> None:
        self.escribir("contratos/gates.json", json.dumps(doc))

    def test_devuelve_la_tabla_con_el_sobre_estandar(self) -> None:
        self.poner_gates()
        r = self.cliente().get("/api/gates")
        self.assertEqual(r.estado, 200)
        j = r.json()
        self.assertEqual(set(j), {"ok", "datos", "fuente", "generado_en", "vacio", "avisos"})
        self.assertIs(j["vacio"], False)
        self.assertEqual(j["fuente"], ["contratos/gates.json"])
        g = j["datos"]["gates"]
        self.assertEqual(g["schema_version"], "1.1.0")
        self.assertEqual(g["niveles"], ["N0", "N1", "N2", "N3", "N4"])
        self.assertEqual(set(g["entradas"]), set(GATES_MINI["entradas"]))
        self.assertEqual(g["entradas"]["accion:aumentar_presupuesto_d8"]["gate"]["N0"], "NA")
        self.assertEqual(g["entradas"]["accion:activar_campana"]["gate"]["N4"], "S")
        self.assertEqual(g["entradas"]["etapa:D7"]["descripcion"], "Armado de campaña (en borrador).")

    def test_acciones_minimas_h_vienen_del_validador_del_proyecto(self) -> None:
        from scripts.validar_esquemas import ACCIONES_GATE_MINIMAS

        self.poner_gates()
        minimas = self.cliente().get("/api/gates").datos["acciones_minimas_h"]
        self.assertEqual(minimas, sorted(ACCIONES_GATE_MINIMAS))
        self.assertIn("activar_campana", minimas)
        with mock.patch.dict("sys.modules", {"scripts.validar_esquemas": None}):
            self.assertIsNone(self.cliente().get("/api/gates").datos["acciones_minimas_h"], "sin el validador no se afirma nada")

    def test_sin_archivo_es_vacio_con_fuente_y_aviso_sin_rutas_absolutas(self) -> None:
        r = self.cliente().get("/api/gates")
        self.assertEqual(r.estado, 200)
        j = r.json()
        self.assertIs(j["vacio"], True)
        self.assertIsNone(j["datos"]["gates"])
        self.assertEqual(j["fuente"], ["contratos/gates.json"])
        self.assertTrue(any("contratos/gates.json" in a for a in j["avisos"]))
        self.assertNotIn(str(self.raiz), r.cuerpo.decode())

    def test_json_corrupto_o_con_otra_forma_es_vacio(self) -> None:
        for contenido in ("{no es json", '{"entradas": []}', '{"entradas": {}}', "[]", '{"entradas": {"etapa:D1": {"gate": "H"}}}'):
            self.escribir("contratos/gates.json", contenido)
            j = self.cliente().get("/api/gates").json()
            self.assertIs(j["vacio"], True, contenido)
            self.assertIsNone(j["datos"]["gates"], contenido)
            self.assertNotIn(str(self.raiz), json.dumps(j))

    def test_nan_e_infinity_no_pasan_el_json_estricto(self) -> None:
        self.escribir("contratos/gates.json", '{"entradas": {"etapa:D1": {"gate": {"N0": NaN}}}}')
        j = self.cliente().get("/api/gates").json()
        self.assertIs(j["vacio"], True)

    def test_tope_de_tamano(self) -> None:
        relleno = "x" * (300 * 1024)
        self.escribir("contratos/gates.json", json.dumps({**GATES_MINI, "nota": relleno}))
        j = self.cliente().get("/api/gates").json()
        self.assertIs(j["vacio"], True)
        self.assertIsNone(j["datos"]["gates"])
        self.assertTrue(any("demasiado grande" in a for a in j["avisos"]))

    def test_solo_pasa_lo_que_tiene_la_forma_del_contrato(self) -> None:
        doc = {
            "schema_version": "1.1.0", "niveles": ["N0", "N9", "x", 7],
            "entradas": {
                "etapa:D1": {"descripcion": HOSTIL, "gate": {"N0": "H", "N1": "Z", "N7": "H", "N2": ["A"], "N3": "S"}},
                "accion:<script>": {"descripcion": "clave hostil", "gate": {"N0": "H"}},
                "../etapa:D2": {"gate": {"N0": "H"}},
                "etapa:D3": {"descripcion": "sin gate"},
                "etapa:D4": {"descripcion": "gate vacío", "gate": {"N8": "H"}},
                "etapa:D5": {"descripcion": "x" * 5000, "gate": {"N0": "A"}},
                "accion:no_dict": "H",
                "etapa:D6": {"descripcion": 12, "gate": {"N4": "NA"}},
            },
        }
        self.poner_gates(doc)
        j = self.cliente().get("/api/gates").json()
        g = j["datos"]["gates"]
        self.assertEqual(g["niveles"], ["N0"], "solo niveles N0-N4 en el orden del archivo")
        self.assertEqual(set(g["entradas"]), {"etapa:D1", "etapa:D5", "etapa:D6"})
        self.assertEqual(g["entradas"]["etapa:D1"]["gate"], {"N0": "H", "N3": "S"}, "valores y niveles fuera del contrato se descartan")
        self.assertEqual(g["entradas"]["etapa:D1"]["descripcion"], HOSTIL, "el texto hostil viaja como DATO, sin tocarlo")
        self.assertEqual(len(g["entradas"]["etapa:D5"]["descripcion"]), 600)
        self.assertIsNone(g["entradas"]["etapa:D6"]["descripcion"])
        self.assertTrue(any("Se omitieron 5 entradas" in a for a in j["avisos"]), j["avisos"])

    def test_niveles_ausentes_o_invalidos_caen_a_n0_n4(self) -> None:
        self.poner_gates({"entradas": GATES_MINI["entradas"], "niveles": "N0"})
        g = self.cliente().get("/api/gates").datos["gates"]
        self.assertEqual(g["niveles"], ["N0", "N1", "N2", "N3", "N4"])
        self.assertIsNone(g["schema_version"])

    def test_no_sigue_enlaces_fuera_de_la_raiz(self) -> None:
        fuera = self.tmp / "fuera.json"
        fuera.write_text(json.dumps(GATES_MINI), encoding="utf-8")
        (self.raiz / "contratos").mkdir()
        try:
            os.symlink(fuera, self.raiz / "contratos" / "gates.json")
        except (OSError, NotImplementedError):
            self.skipTest("el sistema de archivos no permite enlaces simbólicos")
        j = self.cliente().get("/api/gates").json()
        self.assertIs(j["vacio"], True)
        self.assertIsNone(j["datos"]["gates"])
        self.assertNotIn(str(self.tmp), json.dumps(j))

    def test_exige_token_y_solo_admite_get(self) -> None:
        self.poner_gates()
        c = self.cliente()
        sin = c.get("/api/gates", token=False)
        self.assertIn(sin.estado, (401, 403))
        self.assertNotIn(b"etapa:D7", sin.cuerpo)
        r = c.llamar("POST", "/api/gates", json_={})
        self.assertEqual(r.estado, 405)
        self.assertEqual(r.cabeceras["allow"], "GET")
        self.assertEqual(c.llamar("DELETE", "/api/gates").estado, 405)

    def test_es_de_solo_lectura(self) -> None:
        self.poner_gates()
        antes = self.hash_arbol(self.raiz)
        c = self.cliente()
        c.get("/api/gates")
        c.get("/api/gates")
        self.assertEqual(self.hash_arbol(self.raiz), antes)

    def test_refleja_el_contrato_real_entrada_por_entrada(self) -> None:
        real = RAIZ_REPO / "contratos" / "gates.json"
        if not real.is_file():
            self.skipTest("no hay contratos/gates.json en el repositorio")
        (self.raiz / "contratos").mkdir(exist_ok=True)
        shutil.copy(real, self.raiz / "contratos" / "gates.json")
        original = json.loads(real.read_text(encoding="utf-8"))
        j = self.cliente().get("/api/gates").json()
        self.assertEqual(j["avisos"], [], "el contrato real no debería perder ninguna entrada")
        g = j["datos"]["gates"]
        self.assertEqual(set(g["entradas"]), set(original["entradas"]))
        for clave, e in original["entradas"].items():
            self.assertEqual(g["entradas"][clave]["gate"], e["gate"], clave)
            self.assertEqual(g["entradas"][clave]["descripcion"], e["descripcion"], clave)
        self.assertEqual(g["niveles"], original["niveles"])


if __name__ == "__main__":
    unittest.main()
