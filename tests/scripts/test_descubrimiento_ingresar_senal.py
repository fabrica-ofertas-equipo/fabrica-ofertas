"""Pruebas de `scripts.descubrimiento.ingresar_senal`: redacción de PII, senal_id y escritura."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from engine.errores import ErrorBloqueado, ErrorValidacion
from scripts.descubrimiento import ingresar_senal as I

RAIZ = Path(__file__).resolve().parents[2]
FUENTES = RAIZ / "tests" / "fixtures" / "descubrimiento" / "fuentes.yaml"


class PruebaRedaccion(unittest.TestCase):
    def test_correo_simple_se_redacta(self) -> None:
        self.assertIn("[correo]", I.redactar("escribime a juana.perez@gmail.com porfa"))

    def test_correo_ofuscado_arroba_punto_se_redacta(self) -> None:
        self.assertIn("[correo]", I.redactar("mi mail es juana arroba gmail punto com"))

    def test_correo_ofuscado_at_dot_ingles_se_redacta(self) -> None:
        self.assertIn("[correo]", I.redactar("write me at juana (at) gmail (dot) com"))

    def test_telefono_con_guiones_se_redacta(self) -> None:
        self.assertIn("[telefono]", I.redactar("llamame al 11-2345-6789 cuando puedas"))

    def test_telefono_con_espacios_y_codigo_pais_se_redacta(self) -> None:
        self.assertIn("[telefono]", I.redactar("mi numero es +54 9 11 2345 6789"))

    def test_numero_corto_de_precio_no_se_redacta_como_telefono(self) -> None:
        # "2026" (un año) o "100" (un precio corto) no deben confundirse con teléfono: < 7 dígitos.
        texto = I.redactar("el curso cuesta 100 pesos en 2026")
        self.assertNotIn("[telefono]", texto)

    def test_es_idempotente(self) -> None:
        texto = I.redactar("escribime a juana@gmail.com o al 11-2345-6789")
        self.assertEqual(I.redactar(texto), texto)

    def test_no_texto_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            I.redactar(None)  # type: ignore[arg-type]


class PruebaUrlYSenalId(unittest.TestCase):
    def test_url_canonica_quita_utm_y_fragmento_y_barra_final(self) -> None:
        c = I.url_canonica("https://Example.com/post/?utm_source=x&fbclid=abc&ref=y#seccion/")
        self.assertEqual(c, "https://example.com/post?ref=y")

    def test_senal_id_es_determinista_y_12_hex(self) -> None:
        a = I.calcular_senal_id(url="https://example.com/x", extracto="hola mundo", fuente_id="f", referencia=None)
        b = I.calcular_senal_id(url="https://example.com/x", extracto="hola mundo", fuente_id="f", referencia=None)
        self.assertEqual(a, b)
        self.assertRegex(a, r"^[0-9a-f]{12}$")

    def test_sin_url_usa_fuente_id_y_referencia(self) -> None:
        a = I.calcular_senal_id(url=None, extracto=None, fuente_id="dato-propio", referencia="caso-1")
        self.assertRegex(a, r"^[0-9a-f]{12}$")

    def test_sin_url_ni_referencia_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            I.calcular_senal_id(url=None, extracto=None, fuente_id="f", referencia=None)


class PruebaConstruirSenal(unittest.TestCase):
    def setUp(self) -> None:
        self.fuentes = I.cargar_fuentes(FUENTES)

    def _base(self, **over):
        d = dict(fuente_id="youtube-comentarios", fuente=self.fuentes["youtube-comentarios"], familia="dolor",
                 tipo_evidencia="E3", locale="es-MX", pais="MX", url="https://example.com/post",
                 extracto="no se en que se me va el dinero cada mes", fecha_publicacion="2026-01-01",
                 fecha_consulta="2026-11-06", modo_captura="asistida", capturado_por="humano",
                 categoria_especial=False, barrido_id=None, etiquetas=None, referencia=None)
        d.update(over)
        return d

    def test_extracto_se_redacta_antes_de_guardar(self) -> None:
        senal = I.construir_senal(**self._base(extracto="escribime a juana@gmail.com si te interesa"))
        self.assertIn("[correo]", senal["extracto"])

    def test_extracto_de_mas_de_25_palabras_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            I.construir_senal(**self._base(extracto=" ".join(["palabra"] * 30)))

    def test_categoria_especial_no_guarda_extracto_ni_url(self) -> None:
        senal = I.construir_senal(**self._base(categoria_especial=True, extracto=None, url=None,
                                                etiquetas={"nicho_id": "salud-general"}, referencia="caso-1"))
        self.assertIsNone(senal["extracto"])
        self.assertIsNone(senal["url"])
        self.assertIsNone(senal["autor_hash"])
        self.assertTrue(senal["categoria_especial"])

    def test_categoria_especial_sin_etiquetas_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            I.construir_senal(**self._base(categoria_especial=True, extracto=None, url=None))

    def test_retencion_hasta_se_calcula_desde_la_fuente(self) -> None:
        senal = I.construir_senal(**self._base())
        self.assertEqual(senal["retencion_hasta"], "2026-12-06")  # youtube-comentarios: retencion_dias=30

    def test_locale_invalido_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            I.construir_senal(**self._base(locale="es"))

    def test_familia_invalida_es_error(self) -> None:
        with self.assertRaises(ErrorValidacion):
            I.construir_senal(**self._base(familia="otra"))


class PruebaFuentesYaml(unittest.TestCase):
    def test_fuente_no_usar_se_rechaza(self) -> None:
        fuentes = I.cargar_fuentes(FUENTES)
        with self.assertRaises(ErrorValidacion):
            I._exigir_fuente_permitida(fuentes.get("foro-privado-vetado"), "foro-privado-vetado")

    def test_fuente_inexistente_se_rechaza_cerrado(self) -> None:
        with self.assertRaises(ErrorValidacion):
            I._exigir_fuente_permitida(None, "no-existe")


class PruebaCli(unittest.TestCase):
    def _argv_base(self, raiz: Path, **over) -> list[str]:
        base = {
            "--fuente-id": "youtube-comentarios", "--familia": "dolor", "--tipo-evidencia": "E3",
            "--locale": "es-MX", "--pais": "MX", "--url": "https://example.com/post",
            "--extracto": "no se en que se me va el dinero cada mes", "--fecha-consulta": "2026-11-06",
            "--modo-captura": "asistida", "--capturado-por": "humano", "--fuentes": str(FUENTES),
            "--raiz": str(raiz),
        }
        base.update(over)
        argv = ["ingresar"]
        for k, v in base.items():
            if v is not None:
                argv += [k, v]
        return argv

    def test_dry_run_no_escribe_nada(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                codigo = I.main(self._argv_base(raiz, **{"--json": None}) + ["--json"])
            self.assertEqual(codigo, 0, buf.getvalue())
            self.assertFalse((raiz / "empresa").exists())

    def test_aplicar_escribe_una_linea_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            argv = self._argv_base(raiz) + ["--aplicar", "--json"]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                codigo = I.main(argv)
            self.assertEqual(codigo, 0, buf.getvalue())
            ruta = raiz / "empresa" / "descubrimiento" / "senales" / "2026-11" / "youtube-comentarios.jsonl"
            self.assertTrue(ruta.is_file())
            lineas = ruta.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lineas), 1)
            self.assertEqual(json.loads(lineas[0])["fuente_id"], "youtube-comentarios")

    def test_fuente_no_usar_sale_con_3(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            argv = self._argv_base(raiz, **{"--fuente-id": "foro-privado-vetado"})
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                codigo = I.main(argv)
            self.assertEqual(codigo, 3)

    def test_con_pausa_sale_con_4(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            (raiz / "empresa").mkdir(parents=True)
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            argv = self._argv_base(raiz) + ["--aplicar"]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                codigo = I.main(argv)
            self.assertEqual(codigo, 4)

    def test_redactar_cli(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            codigo = I.main(["redactar", "mi mail es juana arroba gmail punto com"])
        self.assertEqual(codigo, 0)
        self.assertIn("[correo]", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
