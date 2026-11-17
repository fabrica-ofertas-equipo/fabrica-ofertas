"""Pruebas de meta.monedas: offset de Meta por moneda (convenciones de código §3)."""
import unittest

from engine.errores import ErrorValidacion
from meta import monedas


class PruebaOffsetMeta(unittest.TestCase):
    def test_monedas_de_offset_1(self) -> None:
        for moneda in monedas.MONEDAS_META_OFFSET_1:
            self.assertEqual(monedas.offset_meta(moneda), 1, moneda)

    def test_moneda_fuera_de_la_lista_usa_offset_100(self) -> None:
        for moneda in ("USD", "EUR", "GBP", "MXN"):
            self.assertEqual(monedas.offset_meta(moneda), 100, moneda)

    def test_offset_meta_exige_texto(self) -> None:
        with self.assertRaises(ErrorValidacion):
            monedas.offset_meta(123)  # type: ignore[arg-type]


class PruebaAUnidadMeta(unittest.TestCase):
    def test_usd_offset_100_exponente_2_no_cambia(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(1234, "USD"), 1234)

    def test_eur_offset_100_exponente_2_no_cambia(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(500, "EUR"), 500)

    def test_clp_offset_1_exponente_0_no_cambia(self) -> None:
        # CLP: offset 1, exponente ISO 0: la unidad de Meta coincide con la unidad menor ISO.
        self.assertEqual(monedas.a_unidad_meta(5000, "CLP"), 5000)

    def test_jpy_offset_1_exponente_0_no_cambia(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(1000, "JPY"), 1000)

    def test_krw_offset_1_exponente_0_no_cambia(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(10000, "KRW"), 10000)

    def test_isk_offset_1_exponente_0_no_cambia(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(2000, "ISK"), 2000)

    def test_pyg_offset_1_exponente_0_no_cambia(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(50000, "PYG"), 50000)

    def test_vnd_offset_1_exponente_0_no_cambia(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(100000, "VND"), 100000)

    def test_cop_offset_1_exponente_2_escala_a_unidad_entera(self) -> None:
        # COP: offset 1, exponente ISO 2: Meta espera la unidad mayor (pesos, no centavos).
        self.assertEqual(monedas.a_unidad_meta(150000, "COP"), 1500)

    def test_crc_offset_1_exponente_2_escala_a_unidad_entera(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(250000, "CRC"), 2500)

    def test_huf_offset_1_exponente_2_escala_a_unidad_entera(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(99900, "HUF"), 999)

    def test_idr_offset_1_exponente_2_escala_a_unidad_entera(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(1000000, "IDR"), 10000)

    def test_twd_offset_1_exponente_2_escala_a_unidad_entera(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(50000, "TWD"), 500)

    def test_resultado_no_entero_falla(self) -> None:
        # COP con un resto de centavos no convierte exacto a la unidad de Meta: dato incoherente.
        with self.assertRaises(ErrorValidacion):
            monedas.a_unidad_meta(150050, "COP")

    def test_moneda_sin_exponente_iso_falla(self) -> None:
        with self.assertRaises(ErrorValidacion):
            monedas.a_unidad_meta(100, "XYZ")

    def test_monto_no_entero_falla(self) -> None:
        with self.assertRaises(ErrorValidacion):
            monedas.a_unidad_meta(True, "USD")  # type: ignore[arg-type]

    def test_cero_siempre_convierte_a_cero(self) -> None:
        self.assertEqual(monedas.a_unidad_meta(0, "USD"), 0)
        self.assertEqual(monedas.a_unidad_meta(0, "JPY"), 0)


if __name__ == "__main__":
    unittest.main()
