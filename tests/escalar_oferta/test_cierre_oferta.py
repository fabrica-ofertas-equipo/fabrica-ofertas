"""R15: cierre de una oferta apagada y archivo de sus tiendas en Impultienda (dueño, 14-nov: «72 h después», «cortes por regla y a mano»)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("cierre_oferta", SCRIPTS / "cierre_oferta.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)

AHORA = dt.datetime.fromisoformat("2026-11-17T12:00-03:00")
BASE = {"ficha": {"tiendas": [{"slug": "a", "store_id": "id-a"}, {"slug": "a-nivel"}]}, "tienda": ["a"]}


def decidir(*tests, carpeta=Path("/nonexistent")):
    return c.evaluar({"tests": list(tests)}, AHORA, carpeta)


class Cierre(unittest.TestCase):
    def test_casos_del_script(self):
        self.assertEqual(c._probar(), 0)

    def test_72_horas_justas(self):
        t = {**BASE, "nombre": "T", "estado": "pausado", "apagado": {"cuando": "2026-11-14T12:00-03:00"}}
        self.assertEqual(decidir(t)[0]["decision"], "CERRAR")
        t["apagado"]["cuando"] = "2026-11-14T12:01-03:00"
        self.assertEqual(decidir(t)[0]["decision"], "ESPERA")

    def test_archiva_todas_las_tiendas_con_store_id(self):
        r = decidir({**BASE, "nombre": "T", "estado": "pausado", "apagado": {"cuando": "2026-11-13T00:00-03:00"}})[0]
        self.assertEqual([(x["slug"], x["store_id"]) for x in r["archivar"]], [("a", "id-a"), ("a-nivel", None)])

    def test_no_repite_las_ya_archivadas(self):
        t = {**BASE, "nombre": "T", "estado": "pausado", "apagado": {"cuando": "2026-11-13T00:00-03:00"},
             "cierre": {"tiendas_archivadas": [{"slug": "a"}]}}
        r = decidir(t)[0]
        self.assertEqual([x["slug"] for x in r["archivar"]], ["a-nivel"])
        self.assertEqual(r["ya_archivadas"], ["a"])

    def test_apagado_sacado_de_vigilancia(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "vigilancia.jsonl").write_text(json.dumps(
                {"leido": "2026-11-14T11:02-03:00", "tests": [{"test": "T", "decision": "APAGAR", "gasto_usd": 34.58}]}) + "\n", encoding="utf-8")
            r = decidir({**BASE, "nombre": "T", "estado": "pausado"}, carpeta=Path(d))[0]
        self.assertEqual(r["decision"], "CERRAR")
        self.assertEqual(r["apagado"]["fuente"], "vigilancia.jsonl")

    def test_venta_con_hora_posterior_retiene(self):
        t = {**BASE, "nombre": "T", "estado": "pausado", "apagado": {"cuando": "2026-11-13T10:00-03:00"},
             "ventas": [{"orden": "9", "fecha": "2026-11-13", "hora": "2026-11-13T15:00-03:00"}]}
        self.assertEqual(decidir(t)[0]["decision"], "RETENER")

    def test_registrar_deja_cerrado(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "libro-de-tests.json"
            ruta.write_text(json.dumps({"tests": [{**BASE, "nombre": "T", "estado": "pausado", "programado": [{"que": "x"}],
                                                   "apagado": {"cuando": "2026-11-13T00:00-03:00"}}]}), encoding="utf-8")
            import libro
            viejo = libro.modificar.__defaults__
            libro.modificar.__defaults__ = (ruta,)
            try:
                c.registrar("T", [{"slug": "a", "store_id": "id-a", "subdominio_archivo": "a-arch-1"}], AHORA)
            finally:
                libro.modificar.__defaults__ = viejo
            t = json.loads(ruta.read_text(encoding="utf-8"))["tests"][0]
        self.assertEqual(t["estado"], "cerrado")
        self.assertIsNone(t["programado"])
        self.assertEqual(t["cierre"]["tiendas_archivadas"][0]["slug"], "a")
        self.assertEqual(c.evaluar({"tests": [t]}, AHORA, Path("/x"))[0]["decision"], "CERRADA")


if __name__ == "__main__":
    unittest.main()
