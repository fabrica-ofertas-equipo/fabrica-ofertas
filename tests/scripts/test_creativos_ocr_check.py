"""Pruebas de ``scripts.creativos.ocr_check`` (OCR a 1 fps contra copies.json y claims prohibidos)."""
from __future__ import annotations

import unittest
from pathlib import Path

from engine.errores import ErrorUso, ErrorValidacion

from scripts.creativos import ocr_check

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "creativos"
FOTOGRAMAS = FIXTURES / "fotogramas"


class _MotorFijo:
    """Motor OCR falso: devuelve el mismo texto para cualquier fotograma."""

    def __init__(self, texto: str) -> None:
        self._texto = texto

    def reconocer(self, ruta_imagen: Path) -> str:
        return self._texto


COPY_OK = {"texto_principal": "Tu pausa no es un hueco", "titular": "Guia mas plantilla"}


class PruebaCompararTexto(unittest.TestCase):
    def test_coincide_normalizando_mayusculas_y_espacios(self) -> None:
        faltantes = ocr_check.comparar_texto("  TU PAUSA no ES un   hueco  guia mas plantilla ", COPY_OK)
        self.assertEqual(faltantes, [])

    def test_campo_ausente_se_reporta(self) -> None:
        faltantes = ocr_check.comparar_texto("texto que no tiene nada que ver", COPY_OK)
        self.assertEqual(set(faltantes), {"texto_principal", "titular"})


class PruebaVerificar(unittest.TestCase):
    def setUp(self) -> None:
        self.imagenes = sorted(FOTOGRAMAS.glob("*.png"))
        self.assertEqual(len(self.imagenes), 2)

    def test_texto_coincide_y_sin_claims_prohibidos(self) -> None:
        motor = _MotorFijo("Tu pausa no es un hueco. Guia mas plantilla.")
        r = ocr_check.verificar(self.imagenes, motor, COPY_OK, locale="es-ES", macro_nicho="dinero")
        self.assertEqual(r["campos_sin_coincidir"], [])
        self.assertEqual(r["semaforo"], "verde")

    def test_claim_prohibido_da_semaforo_rojo(self) -> None:
        motor = _MotorFijo("Tu pausa no es un hueco. Guia mas plantilla. Resultados 100% garantizado.")
        r = ocr_check.verificar(self.imagenes, motor, COPY_OK, locale="es-ES", macro_nicho="dinero")
        self.assertEqual(r["semaforo"], "rojo")
        self.assertTrue(r["hallazgos"])

    def test_texto_que_no_coincide_se_reporta(self) -> None:
        motor = _MotorFijo("un texto completamente distinto")
        r = ocr_check.verificar(self.imagenes, motor, COPY_OK, locale="es-ES")
        self.assertEqual(set(r["campos_sin_coincidir"]), {"texto_principal", "titular"})

    def test_sin_imagenes_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            ocr_check.verificar([], _MotorFijo("x"), COPY_OK, locale="es-ES")


class PruebaExtraerFotogramas(unittest.TestCase):
    def test_sin_binario_configurado_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            ocr_check.extraer_fotogramas(FOTOGRAMAS / "video.mp4", FOTOGRAMAS / "salida", ffmpeg=None)

    def test_binario_inexistente_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            ocr_check.extraer_fotogramas(FOTOGRAMAS / "video.mp4", FOTOGRAMAS / "salida", ffmpeg=FIXTURES / "no-existe-ffmpeg")

    def test_binario_no_ejecutable_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            ocr_check.extraer_fotogramas(FOTOGRAMAS / "video.mp4", FOTOGRAMAS / "salida", ffmpeg=FIXTURES / "copies.json")


class PruebaCLI(unittest.TestCase):
    def test_sin_motor_inyectado_sale_dos(self) -> None:
        codigo = ocr_check.main([
            "--ad-name", "c01-hueco_img_h1_v1", "--copies", str(FIXTURES / "copies.json"),
            "--fotogramas", str(FOTOGRAMAS), "--locale", "es-ES",
        ])
        self.assertEqual(codigo, ErrorUso.codigo_salida)

    def test_con_motor_inyectado_sale_cero_si_coincide(self) -> None:
        codigo = ocr_check.main(
            ["--ad-name", "c01-hueco_img_h1_v1", "--copies", str(FIXTURES / "copies.json"),
             "--fotogramas", str(FOTOGRAMAS), "--locale", "es-ES"],
            motor=_MotorFijo("Tu pausa no es un hueco. Guia mas plantilla."),
        )
        self.assertEqual(codigo, 0)

    def test_ad_name_sin_copy_es_error_de_validacion(self) -> None:
        codigo = ocr_check.main(
            ["--ad-name", "no-existe", "--copies", str(FIXTURES / "copies.json"),
             "--fotogramas", str(FOTOGRAMAS), "--locale", "es-ES"],
            motor=_MotorFijo("x"),
        )
        self.assertEqual(codigo, ErrorValidacion.codigo_salida)


if __name__ == "__main__":
    unittest.main()
