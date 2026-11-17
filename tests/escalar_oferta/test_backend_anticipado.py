"""R3b (dueño, 14-nov): backend armado durante el test cuando el corte ya no se alcanza, activado al cierre del test."""
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


vc = _cargar("vigilar_corte")
ht = _cargar("hay_trabajo")

MADRID = dt.timezone(dt.timedelta(hours=1))


def caso_es(ventas_tienda: int, gasto: float, backend: dict | None = None) -> tuple[dict, dict]:
    t = {"nombre": "Oferta F", "mercado": "ES", "inicio": "2026-11-14T00:00:00+01:00", "estado": "activo", "campana": "1",
         "ficha": {"tiendas": [{"precio": {"usd": 21.0}}, {"precio": {"usd": 32.0}}, {"precio": {"usd": 54.0}}],
                   "campana": {"id": "1", "presupuesto_usd_dia": 162}}}
    if backend:
        t["backend"] = backend
    lectura = {"campanas": {"1": {"gasto_usd": gasto, "compras_meta": 0, "estado": "ACTIVE"}}, "ventas_tienda": {"Oferta F": ventas_tienda}}
    return t, lectura


class TestBackendAnticipado(unittest.TestCase):
    ahora = dt.datetime(2026, 11, 14, 12, 45, tzinfo=MADRID)

    def test_con_corte_imposible_se_arma_y_activa_al_cierre(self) -> None:
        r = vc.decidir(*caso_es(8, 148.76), self.ahora)
        self.assertEqual(r["decision"], "SIGUE")
        self.assertEqual(r["backend_anticipado"]["activar_desde"], "2026-11-15T00:00:00+01:00")

    def test_con_una_venta_el_corte_todavia_se_alcanza(self) -> None:
        r = vc.decidir(*caso_es(1, 40.0), self.ahora)   # corte 81, tope 40 + 162 × 1,75 × 11,25/24 ≈ 173
        self.assertNotIn("backend_anticipado", r)

    def test_sin_ventas_no(self) -> None:
        self.assertNotIn("backend_anticipado", vc.decidir(*caso_es(0, 20.0), self.ahora))

    def test_si_ya_hay_backend_no_se_repite(self) -> None:
        r = vc.decidir(*caso_es(8, 148.76, {"estado": "listo"}), self.ahora)
        self.assertNotIn("backend_anticipado", r)


class TestPasoActivar(unittest.TestCase):
    def _libro(self, estado: str) -> dict:
        t, _ = caso_es(8, 148.76, {"estado": estado, "activar_desde": "2026-11-15T00:00:00+01:00"})
        return {"tests": [t]}

    def test_listo_y_cierre_pasado_pide_activar(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = ht.evaluar(self._libro("listo"), dt.datetime(2026, 11, 15, 0, 5, tzinfo=MADRID), Path(d))
            self.assertIn(6, r["pasos"])
            self.assertIn("activar backend", ht.linea(r))

    def test_antes_del_cierre_no(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = ht.evaluar(self._libro("listo"), dt.datetime(2026, 11, 14, 23, 0, tzinfo=MADRID), Path(d))
            self.assertNotIn(6, r["pasos"])

    def test_ya_activo_no(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = ht.evaluar(self._libro("activo"), dt.datetime(2026, 11, 15, 0, 5, tzinfo=MADRID), Path(d))
            self.assertNotIn(6, r["pasos"])


class TestMinimoPendienteEnRenovacion(unittest.TestCase):
    """14-nov: el campo vive en la entrada de «renovaciones»; antes solo se miraba la fila del test y nunca se ponía."""

    def _libro(self, inicio: str) -> dict:
        t, _ = caso_es(8, 148.76)
        t["renovaciones"] = [{"ronda": "R4", "inicio": inicio, "estado": "programada", "minimo_pendiente": True}]
        return {"tests": [t]}

    def test_renovacion_ya_empezada_pide_minimo(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = ht.evaluar(self._libro("2026-11-15T00:00:00+01:00"), dt.datetime(2026, 11, 15, 0, 5, tzinfo=MADRID), Path(d))
            self.assertIn(4, r["pasos"])

    def test_renovacion_por_empezar_no(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = ht.evaluar(self._libro("2026-11-15T00:00:00+01:00"), dt.datetime(2026, 11, 14, 23, 0, tzinfo=MADRID), Path(d))
            self.assertNotIn(4, r["pasos"])


if __name__ == "__main__":
    unittest.main()
