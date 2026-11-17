"""Verificación del funnel antes de activar y a los 10-15 min de activar los anuncios (dueño, 14-nov)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / f"{nombre}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


vf = _cargar("verificar_funnel")
cp = _cargar("control_previo")

T = {"nombre": "X", "estado": "activo", "inicio": "2026-11-15T00:00:00+01:00",
     "renovaciones": [{"inicio": "2026-11-16T00:00:00+01:00"}],
     "ficha": {"tiendas": [{"slug": "x-esencial", "rol": "nivel bajo"}, {"slug": "x-familia", "rol": "principal (landing)"}]}}
SANO = {"fallas": [], "checkouts": [{}]}


class Evaluar(unittest.TestCase):
    def test_imagen_rota_del_checkout_es_falla(self):
        r = vf.evaluar(T, {}, {"fallas": ["checkout x-familia: imagen del producto rota (Cartella)"]}, False)
        self.assertEqual(r["decision"], "FALLA")
        self.assertTrue(r["urgente"])

    def test_todo_bien(self):
        lec = {"anuncios": {"activos": 8}, "impresiones": 300, "clics": 12, "visitas_landing": 9}
        self.assertEqual(vf.evaluar(T, lec, SANO, False)["decision"], "OK")

    def test_sin_entrega_espera(self):
        lec = {"anuncios": {"activos": 0, "en_revision": 10}, "impresiones": 0}
        self.assertEqual(vf.evaluar(T, lec, SANO, False)["decision"], "ESPERAR")

    def test_clics_que_no_llegan(self):
        lec = {"anuncios": {"activos": 8}, "impresiones": 300, "clics": 25, "visitas_landing": 0}
        self.assertEqual(vf.evaluar(T, lec, SANO, False)["decision"], "FALLA")

    def test_anuncio_a_otra_tienda(self):
        r = vf.evaluar(T, {"urls_anuncios": ["https://otra.impultienda.ar/?v=ficha"]}, SANO, False)
        self.assertEqual(r["decision"], "FALLA")

    def test_sin_prueba_es_falla(self):
        self.assertEqual(vf.evaluar(T, {}, None, True)["decision"], "FALLA")

    def test_landing_es_la_principal(self):
        self.assertEqual(vf.tiendas_de(T), (["x-esencial", "x-familia"], "x-familia"))


class Pendientes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        vf.REGISTRO = Path(self.tmp.name) / "verificaciones.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_ventana_de_10_min_a_6_h(self):
        libro = {"tests": [T]}
        inicio = dt.datetime.fromisoformat("2026-11-15T00:00:00+01:00")
        self.assertEqual(vf.pendientes(libro, inicio + dt.timedelta(minutes=5)), [])
        self.assertEqual(len(vf.pendientes(libro, inicio + dt.timedelta(minutes=12))), 1)
        self.assertEqual(vf.pendientes(libro, inicio + dt.timedelta(hours=7)), [])
        # la renovación del día siguiente pide su propia verificación
        self.assertEqual(len(vf.pendientes(libro, inicio + dt.timedelta(days=1, minutes=15))), 1)

    def test_registrada_no_vuelve(self):
        libro = {"tests": [T]}
        inicio = dt.datetime.fromisoformat("2026-11-15T00:00:00+01:00")
        vf.registrar({"oferta": "X", "momento": inicio.isoformat(), "decision": "OK"})
        self.assertEqual(vf.pendientes(libro, inicio + dt.timedelta(minutes=20)), [])

    def test_pausada_no_se_verifica(self):
        libro = {"tests": [{**T, "estado": "pausado"}]}
        inicio = dt.datetime.fromisoformat("2026-11-15T00:00:00+01:00")
        self.assertEqual(vf.pendientes(libro, inicio + dt.timedelta(minutes=20)), [])


class ControlPrevio(unittest.TestCase):
    def _libro(self):
        return {"tests": [{"nombre": "X", "estado": "programado", "mercado": "ES",
                           "ficha": {"tiendas": [{"url": "https://x.impultienda.ar/", "precio": {"usd": 21}}], "pixel": {"id": "1"}}}]}

    def _lectura(self, **extra):
        return {"oferta": "X", "mercado": "ES", "presupuesto_usd": 63, "campana_nombre": "ES | X | CBO test",
                "conjuntos": [{"id": "1", "start_time": "2026-11-16T00:00:00+0100"}],
                "anuncios": {"total": 10, "rechazados": 0}, "errores": [], **extra}

    def test_sin_prueba_del_funnel_no_activa(self):
        ahora = dt.datetime(2026, 11, 15, 12, tzinfo=dt.timezone.utc)
        r = cp.controlar(self._lectura(), self._libro(), ahora, None)
        self.assertEqual(r["decision"], "NO_ACTIVAR")
        self.assertIn("funnel", " ".join(c["control"] for c in r["controles"] if not c["ok"]))

    def test_funnel_con_fallas_no_activa(self):
        ahora = dt.datetime(2026, 11, 15, 12, tzinfo=dt.timezone.utc)
        r = cp.controlar(self._lectura(funnel={"decision": "FALLA", "fallas": ["checkout x: imagen del producto rota"]}),
                         self._libro(), ahora, None)
        self.assertEqual(r["decision"], "NO_ACTIVAR")

    def test_funnel_ok_activa(self):
        ahora = dt.datetime(2026, 11, 15, 12, tzinfo=dt.timezone.utc)
        r = cp.controlar(self._lectura(funnel={"decision": "OK", "fallas": []}), self._libro(), ahora, None)
        self.assertEqual(r["decision"], "ACTIVAR", r)


if __name__ == "__main__":
    unittest.main()
