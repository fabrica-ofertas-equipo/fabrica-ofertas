"""Prueba de humo: ``lint_estatico.ejecutar`` corre sobre la raíz real del repositorio sin
lanzar ninguna excepción y devuelve un ``Informe`` bien formado. No afirma que el árbol esté
limpio (hoy no lo está: ver scripts/modelado y docs/10-runbook-testeo.md) ni escribe nada fuera del
repositorio; solo guarda contra una regresión que rompa el recorrido mismo (por ejemplo, un
archivo binario o con una ruta rara que haga fallar la lectura).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import lint_estatico as L


class PruebaArbolReal(unittest.TestCase):
    def test_ejecutar_no_lanza_sobre_la_raiz_real(self) -> None:
        base = Path(__file__).resolve().parents[2]
        informe = L.ejecutar(base, reglas=None)
        self.assertEqual({"a", "b", "c", "d"}, set(informe.resumen))
        self.assertTrue(all(isinstance(n, int) and n >= 0 for n in informe.resumen.values()))
        self.assertEqual(sum(informe.resumen.values()), len(informe.hallazgos))


if __name__ == "__main__":
    unittest.main()
