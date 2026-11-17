"""Pruebas de scripts.producto.render (HTML -> PDF, binario de navegador inyectable; sin red ni navegador real)."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from engine.errores import ErrorExterno, ErrorLimite, ErrorUso, ErrorValidacion
from scripts.producto import render as R

PDF_MINIMO = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
    b"2 0 obj<</Type/Page>>endobj\n%%EOF"
)


def _doble_ok(pdf_bytes: bytes = PDF_MINIMO):
    def _ejecutar(argv, *, env, timeout_s):
        # La bandera --print-to-pdf=RUTA es la última antes de la URL: imita lo que haría el navegador real.
        ruta = next(a.split("=", 1)[1] for a in argv if a.startswith("--print-to-pdf="))
        Path(ruta).write_bytes(pdf_bytes)
        return subprocess.CompletedProcess(argv, returncode=0)
    return _ejecutar


def _doble_falla(codigo: int = 1):
    def _ejecutar(argv, *, env, timeout_s):
        return subprocess.CompletedProcess(argv, returncode=codigo)
    return _ejecutar


def _doble_timeout():
    def _ejecutar(argv, *, env, timeout_s):
        raise subprocess.TimeoutExpired(argv, timeout_s)
    return _ejecutar


class PruebaRenderizar(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.html = Path(self.tmp.name) / "fuente.html"
        self.html.write_text("<html><body>hola</body></html>", encoding="utf-8")

    def test_doble_exitoso_produce_un_pdf_verificado(self) -> None:
        salida = Path(self.tmp.name) / "salida.pdf"
        resultado = R.renderizar(self.html, salida, "navegador-falso", ejecutar=_doble_ok())
        self.assertTrue(resultado["ok"])
        self.assertEqual(1, resultado["paginas"])
        self.assertTrue(salida.is_file())

    def test_doble_que_falla_es_error_externo_nunca_verde_falso(self) -> None:
        salida = Path(self.tmp.name) / "salida2.pdf"
        with self.assertRaises(ErrorExterno):
            R.renderizar(self.html, salida, "navegador-falso", ejecutar=_doble_falla())
        self.assertFalse(salida.exists())

    def test_doble_con_timeout_es_error_externo(self) -> None:
        salida = Path(self.tmp.name) / "salida3.pdf"
        with self.assertRaises(ErrorExterno):
            R.renderizar(self.html, salida, "navegador-falso", ejecutar=_doble_timeout(), timeout_s=1)

    def test_pdf_invalido_del_navegador_es_error_de_validacion(self) -> None:
        salida = Path(self.tmp.name) / "salida4.pdf"
        with self.assertRaises(ErrorValidacion):
            R.renderizar(self.html, salida, "navegador-falso", ejecutar=_doble_ok(b"no es un pdf"))
        self.assertFalse(salida.exists())

    def test_no_sobrescribe_una_salida_existente(self) -> None:
        salida = Path(self.tmp.name) / "salida5.pdf"
        salida.write_bytes(b"ya existe")
        with self.assertRaises(ErrorUso):
            R.validar_salida(str(salida))


class PruebaValidaciones(unittest.TestCase):
    def test_url_remota_se_rechaza(self) -> None:
        with self.assertRaises(ErrorUso):
            R.validar_html("https://ejemplo.invalid/pagina.html")

    def test_html_inexistente_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            R.validar_html("/no/existe/archivo.html")

    def test_sin_navegador_disponible_falla_cerrado_codigo_5(self) -> None:
        with self.assertRaises(ErrorLimite):
            R.buscar_navegador("/ruta/que/no/existe/chrome")

    def test_verificar_pdf_vacio_es_invalido(self) -> None:
        with self.assertRaises(ErrorValidacion):
            R.verificar_pdf(b"")

    def test_verificar_pdf_sin_cabecera_es_invalido(self) -> None:
        with self.assertRaises(ErrorValidacion):
            R.verificar_pdf(b"no es un pdf")

    def test_verificar_pdf_valido_cuenta_paginas(self) -> None:
        info = R.verificar_pdf(PDF_MINIMO)
        self.assertEqual(1, info["paginas"])


class PruebaCli(unittest.TestCase):
    """Solo los caminos de error (sin navegador real ni red): la CLI con doble vive en el nivel de función."""

    def setUp(self) -> None:
        import sys

        self.raiz = Path(__file__).resolve().parents[2]
        self.sys_executable = sys.executable
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.html = Path(self.tmp.name) / "fuente.html"
        self.html.write_text("<html><body>hola</body></html>", encoding="utf-8")

    def _correr(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([self.sys_executable, "-m", "scripts.producto.render", *args],
                              cwd=self.raiz, capture_output=True, text=True, timeout=30)

    def test_sin_navegador_disponible_sale_5(self) -> None:
        salida = Path(self.tmp.name) / "s.pdf"
        r = self._correr("--html", str(self.html), "--salida", str(salida), "--chrome", "/no/existe/chrome")
        self.assertEqual(5, r.returncode, r.stderr)

    def test_url_remota_sale_2(self) -> None:
        salida = Path(self.tmp.name) / "s2.pdf"
        r = self._correr("--html", "https://ejemplo.invalid/a.html", "--salida", str(salida), "--chrome", "/no/existe/chrome")
        self.assertEqual(2, r.returncode)

    def test_html_inexistente_sale_3(self) -> None:
        salida = Path(self.tmp.name) / "s3.pdf"
        r = self._correr("--html", str(Path(self.tmp.name) / "no-existe.html"), "--salida", str(salida),
                         "--chrome", "/no/existe/chrome")
        self.assertEqual(3, r.returncode)


if __name__ == "__main__":
    unittest.main()
