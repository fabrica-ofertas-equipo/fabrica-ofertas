"""B0-15 (ETL x2 idéntico, cobertura, Stripe↔ledger=0) y la mitad de B0-16 (generador de 3 escenarios)."""
from __future__ import annotations

import unittest

from scripts.b0 import datos as D
from scripts.b0 import generador as G


class PruebaB0_15(unittest.TestCase):
    def test_evaluar_b0_15_es_verde(self) -> None:
        r = D.evaluar_b0_15()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaB0_16Mitad(unittest.TestCase):
    def test_evaluar_b0_16_queda_pendiente_pero_el_generador_es_correcto(self) -> None:
        r = D.evaluar_b0_16()
        self.assertEqual("pendiente", r.estado)
        self.assertIn("95,00%", r.motivo)
        self.assertIn("engine.d8", r.motivo)


class PruebaGenerador(unittest.TestCase):
    def test_los_tres_escenarios_son_deterministas(self) -> None:
        for nombre in G.ESCENARIOS:
            with self.subTest(nombre):
                e1 = G.generar_escenario(nombre)
                e2 = G.generar_escenario(nombre)
                self.assertEqual(e1, e2)

    def test_documentos_tienen_la_forma_que_etl_meta_y_etl_stripe_esperan(self) -> None:
        e = G.generar_escenario("A_perdedor_severo")
        self.assertIn("cuenta", e["meta"])
        self.assertIn("filas", e["meta"])
        self.assertTrue(e["meta"]["sintetico"])
        self.assertIn("eventos", e["stripe"])
        self.assertTrue(e["stripe"]["sintetico"])


class PruebaNegativaSembrada(unittest.TestCase):
    def test_escenario_etl_doble_detecta_cuando_no_quedan_idempotentes(self) -> None:
        """Siembra el fallo: corre el ETL con un reloj DISTINTO en cada pasada (ingerido_en cambia)
        para comprobar que la huella de tablas SÍ detecta la diferencia cuando de verdad la hay."""
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path

        from datos.db import conectar, migrar

        escenario = G.generar_escenario("A_perdedor_severo")
        with tempfile.TemporaryDirectory(prefix="b0-datos-neg-") as tmp_str:
            raiz = Path(tmp_str)
            (raiz / "empresa" / "finanzas").mkdir(parents=True, exist_ok=True)
            (raiz / "empresa" / "costos.jsonl").touch()
            conn = conectar(f"sqlite:///{raiz}/empresa/datos/fabrica.db")
            migrar(conn)
            try:
                reloj_1 = lambda: datetime(2026, 11, 24, 6, 0, 0, tzinfo=timezone.utc)
                reloj_2 = lambda: datetime(2026, 11, 24, 7, 0, 0, tzinfo=timezone.utc)  # a propósito, distinto
                D._correr_etl_una_vez(conn, raiz, escenario["meta"], escenario["stripe"], ahora=reloj_1)
                huella_1 = D._hash_tablas(conn)
                D._correr_etl_una_vez(conn, raiz, escenario["meta"], escenario["stripe"], ahora=reloj_2)
                huella_2 = D._hash_tablas(conn)
                # raw_meta_insight.payload_json no incluye ingerido_en, pero fact_meta_ad_dia sí: debería
                # diferir SOLO ahí si el reloj cambia entre corridas (confirma que la huella es sensible).
                self.assertNotEqual(huella_1["fact_meta_ad_dia__suma_hash"], huella_2["fact_meta_ad_dia__suma_hash"])
            finally:
                conn.cerrar()


if __name__ == "__main__":
    unittest.main()
