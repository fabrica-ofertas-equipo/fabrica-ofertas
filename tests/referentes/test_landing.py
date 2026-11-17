"""Registro de la landing original de una página anunciante (scripts/referentes/landing.py): validación estricta y escritura segura."""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts.referentes import landing as R

PID = "700000000000001"
URL = "https://referentea.example/colora?utm=x"


class PruebaUrl(unittest.TestCase):
    def test_acepta_https_normal_y_devuelve_dominio(self) -> None:
        url, dominio = R.validar_url("  https://Colora.ReferenteA.example/Ofertas?a=1#arriba ")
        self.assertEqual(url, "https://Colora.ReferenteA.example/Ofertas?a=1")   # sin fragmento, sin espacios en los bordes
        self.assertEqual(dominio, "colora.referentea.example")

    def test_dominio_internacional_se_muestra_en_punycode(self) -> None:
        _, dominio = R.validar_url("https://pаypal.example/x")        # «а» cirílica: un dominio disfrazado
        self.assertTrue(dominio.startswith("xn--"), dominio)

    def test_rechaza_lo_peligroso_o_equivocado(self) -> None:
        malas = {
            "": "falta", "javascript:alert(1)": "https", "http://a.example/x": "https", "data:text/html,x": "https", "ftp://a.example": "https",
            "//a.example/x": "https", "https://user:pass@a.example/x": "usuario", "https://a.example@evil.example/": "usuario",
            "https://a.example:8443/x": "puerto", "https://localhost/x": "dominio", "https://intranet/x": "dominio", "https://127.0.0.1/x": "IP",
            "https://[::1]/x": "dominio", "https://nas.local/x": "dominio", "https://a.example/x y": "espacios", "https://a.example/‮gnp": "invisibles",
            "https://a.example/\nx": "espacios", "https://www.facebook.com/ads/library/?id=1": "Meta", "https://m.facebook.com/x": "Meta",
            "https://l.instagram.com/x": "Meta", "https://wa.me/123": "Meta", "https://a.example/" + "x" * 600: "larga",
        }
        for url, pista in malas.items():
            with self.subTest(url=url[:40]):
                with self.assertRaises(ValueError) as ctx:
                    R.validar_url(url)
                self.assertTrue(str(ctx.exception))
        for no_texto in (None, 5, [], {"url": "x"}):
            with self.assertRaises(ValueError):
                R.validar_url(no_texto)

    def test_page_id(self) -> None:
        self.assertEqual(R.validar_page_id(PID), PID)
        self.assertEqual(R.validar_page_id(" 123456 "), "123456")
        for malo in ("", "12ab", "1234", "1" * 21, None, True, "../1234567"):
            with self.assertRaises(ValueError):
                R.validar_page_id(malo)


class PruebaRegistro(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="referentes-prueba-"))
        self.addCleanup(shutil.rmtree, self.raiz, True)

    def archivo(self) -> Path:
        return self.raiz / R.REL_REGISTRO

    def test_sin_escribir_no_toca_el_disco(self) -> None:
        reg = R.registrar(self.raiz, PID, URL, nombre="ReferenteA")
        self.assertEqual(reg["url"], URL)
        self.assertEqual(reg["origen"], "dueno")
        self.assertFalse(self.archivo().exists())
        self.assertEqual(R.cargar(self.raiz), [])

    def test_escribir_guarda_reemplaza_y_quita(self) -> None:
        R.registrar(self.raiz, PID, URL, nombre="ReferenteA", escribir=True, ahora="2026-11-08T10:00:00Z")
        R.registrar(self.raiz, "825650823960909", "https://zabala.example/", escribir=True)
        R.registrar(self.raiz, PID, "https://referentea.example/nueva", nombre="ReferenteA", nota="corregida", escribir=True)   # reemplaza, no duplica
        filas = R.cargar(self.raiz)
        self.assertEqual([f["page_id"] for f in filas], ["700000000000001", "825650823960909"])
        self.assertEqual(R.buscar(self.raiz, PID)["url"], "https://referentea.example/nueva")
        self.assertEqual(R.buscar(self.raiz, PID)["nota"], "corregida")
        self.assertIsNone(R.buscar(self.raiz, "999999"))
        self.assertTrue(R.quitar(self.raiz, PID, escribir=False))      # simulacro: sigue ahí
        self.assertEqual(len(R.cargar(self.raiz)), 2)
        self.assertTrue(R.quitar(self.raiz, PID, escribir=True))
        self.assertFalse(R.quitar(self.raiz, PID, escribir=True))
        self.assertEqual([f["page_id"] for f in R.cargar(self.raiz)], ["825650823960909"])
        self.assertEqual([p.name for p in self.archivo().parent.iterdir()], ["landings.json"], "no deja temporales")

    def test_validaciones_de_oferta_y_copia_local(self) -> None:
        with self.assertRaises(ValueError):
            R.registrar(self.raiz, PID, URL, oferta_id="cualquiera")
        for mala in ("/etc/passwd", "../fuera.html", "docs/../../x", "no/existe.html"):
            with self.assertRaises(ValueError):
                R.registrar(self.raiz, PID, URL, copia_local=mala)
        (self.raiz / "docs").mkdir()
        (self.raiz / "docs" / "p.html").write_text("<html></html>", encoding="utf-8")
        reg = R.registrar(self.raiz, PID, URL, oferta_id="OF-202611-91", copia_local="docs/p.html")
        self.assertEqual((reg["oferta_id"], reg["copia_local"]), ("OF-202611-91", "docs/p.html"))

    def test_archivo_corrupto_falla_cerrado_y_no_se_pisa(self) -> None:
        self.archivo().parent.mkdir(parents=True)
        self.archivo().write_text("{no es json", encoding="utf-8")
        with self.assertRaises(R.ErrorRegistro):
            R.registrar(self.raiz, PID, URL, escribir=True)
        self.assertEqual(self.archivo().read_text(encoding="utf-8"), "{no es json")
        self.archivo().write_text(json.dumps({"referentes": "no es lista"}), encoding="utf-8")
        with self.assertRaises(R.ErrorRegistro):
            R.cargar(self.raiz)

    def test_el_texto_libre_se_limpia(self) -> None:
        reg = R.registrar(self.raiz, PID, URL, nombre="Pitto‮lino\n", nota="a\u0007b " + "x" * 400)
        self.assertNotIn("‮", reg["page_name"])
        self.assertNotIn("\u0007", reg["nota"])
        self.assertLessEqual(len(reg["nota"]), R.MAX_NOTA)


class PruebaLineaDeComandos(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="referentes-cli-"))
        self.addCleanup(shutil.rmtree, self.raiz, True)

    def correr(self, *args: str) -> tuple[int, str, str]:
        salida, error = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(error):
            codigo = R.main(["--raiz", str(self.raiz), *args])
        return codigo, salida.getvalue(), error.getvalue()

    def test_flujo_completo(self) -> None:
        codigo, out, _ = self.correr("listar")
        self.assertEqual(codigo, 0)
        self.assertIn("Todavía no hay", out)
        codigo, out, _ = self.correr("registrar", PID, URL)
        self.assertEqual(codigo, 0)
        self.assertIn("SIMULACRO", out)
        self.assertFalse((self.raiz / R.REL_REGISTRO).exists())
        codigo, out, _ = self.correr("registrar", PID, URL, "--escribir")
        self.assertEqual(codigo, 0)
        self.assertTrue((self.raiz / R.REL_REGISTRO).exists())
        self.assertIn(URL, self.correr("listar")[1])
        self.assertEqual(self.correr("ver", PID)[0], 0)
        self.assertEqual(self.correr("ver", "999999")[0], 2)
        self.assertEqual(self.correr("quitar", PID, "--escribir")[0], 0)

    def test_errores_de_uso(self) -> None:
        codigo, _, err = self.correr("registrar", PID, "http://a.example/x", "--escribir")
        self.assertEqual(codigo, 2)
        self.assertIn("https", err)
        self.assertEqual(self.correr("registrar", "abc", URL)[0], 2)
        (self.raiz / R.REL_REGISTRO).parent.mkdir(parents=True)
        (self.raiz / R.REL_REGISTRO).write_text("[]", encoding="utf-8")
        self.assertEqual(self.correr("listar")[0], 3)


if __name__ == "__main__":
    unittest.main()
