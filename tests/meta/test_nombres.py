"""Pruebas de meta.nombres: nombres de Meta (backbone §5.2) y URL con macros (§5.3)."""
import contextlib
import io
import json
import unittest
from datetime import date

from engine.errores import ErrorValidacion
from meta import nombres


class PruebaNombres(unittest.TestCase):
    def test_nombre_campana_valido(self) -> None:
        n = nombres.nombre_campana("OF-202611-01", "TEST", "VENTAS", "CBO", date(2026, 11, 6))
        self.assertEqual(n, "OF-202611-01_TEST_VENTAS_CBO_20261106")

    def test_nombre_campana_con_fecha_texto(self) -> None:
        n = nombres.nombre_campana("OF-202611-01", "ESCALA", "VENTAS", "ABO", "20261106")
        self.assertEqual(n, "OF-202611-01_ESCALA_VENTAS_ABO_20261106")

    def test_nombre_campana_fase_invalida_rechazada(self) -> None:
        with self.assertRaises(ErrorValidacion):
            nombres.nombre_campana("OF-202611-01", "NO_EXISTE", "VENTAS", "CBO", "20261106")

    def test_nombre_conjunto_valido(self) -> None:
        self.assertEqual(nombres.nombre_conjunto("amplia", "automaticas", "es-ES"), "amplia_automaticas_es-ES")

    def test_nombre_conjunto_invalido_rechazado(self) -> None:
        with self.assertRaises(ErrorValidacion):
            nombres.nombre_conjunto("amplia", "automaticas", "ES")  # falta el formato BCP-47 esperado

    def test_nombre_anuncio_valido(self) -> None:
        self.assertEqual(nombres.nombre_anuncio("regreso-laboral", "video", "hook-dolor", 1), "regreso-laboral_video_hook-dolor_v1")

    def test_nombre_anuncio_version_cero_rechazada(self) -> None:
        with self.assertRaises(ErrorValidacion):
            nombres.nombre_anuncio("concepto", "video", "hook", 0)

    def test_barra_vertical_prohibida_en_cualquier_nombre(self) -> None:
        with self.assertRaises(ErrorValidacion):
            nombres.validar_nombre("campana", "OF-202611-01_TEST_VENTAS_CBO_|20261106")

    def test_validar_nombre_tipo_desconocido(self) -> None:
        with self.assertRaises(ErrorValidacion):
            nombres.validar_nombre("otro", "x")  # type: ignore[arg-type]


class PruebaUrl(unittest.TestCase):
    def test_url_anuncio_trae_los_parametros_exigidos(self) -> None:
        plantilla = nombres.url_anuncio("https://ofertalanding.com/ir", "OF-202611-01")
        self.assertTrue(plantilla.startswith("https://ofertalanding.com/ir?"))
        for macro in ("{{campaign.name}}", "{{campaign.id}}", "{{adset.id}}", "{{adset.name}}", "{{ad.name}}", "{{ad.id}}"):
            self.assertIn(macro, plantilla)
        self.assertIn("utm_source=meta", plantilla)
        self.assertIn("utm_medium=paid", plantilla)
        self.assertIn("oferta_id=OF-202611-01", plantilla)

    def test_url_anuncio_exige_https(self) -> None:
        with self.assertRaises(ErrorValidacion):
            nombres.url_anuncio("http://inseguro.com", "OF-202611-01")

    def test_resolver_url_reemplaza_las_seis_macros(self) -> None:
        plantilla = nombres.url_anuncio("https://ofertalanding.com/ir", "OF-202611-01")
        resuelta = nombres.resolver_url(
            plantilla, campaign_name="OF-202611-01_TEST_VENTAS_CBO_20261106", campaign_id="1111111111",
            adset_name="amplia_automaticas_es-ES", adset_id="2222222222", ad_name="concepto_video_hook_v1", ad_id="3333333333",
        )
        self.assertNotIn("{{", resuelta)
        self.assertNotIn("}}", resuelta)
        self.assertIn("cid=1111111111", resuelta)
        self.assertIn("asid=2222222222", resuelta)
        self.assertIn("adid=3333333333", resuelta)

    def test_parametros_url_exigidos_orden_y_claves(self) -> None:
        exigidos = nombres.parametros_url_exigidos("OF-202611-01")
        self.assertEqual(
            list(exigidos),
            ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "oferta_id", "cid", "asid", "adid"],
        )


class PruebaCli(unittest.TestCase):
    """A3 (ola 2, B5b): ``python -m meta.nombres`` es puro, sin red ni ``--modo`` (sin efecto externo)."""

    def _correr(self, argv: list[str]) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = nombres.main(argv)
        return codigo, salida.getvalue()

    def test_campana_json(self) -> None:
        codigo, salida = self._correr([
            "campana", "--oferta", "OF-202611-01", "--fase", "TEST", "--objetivo", "VENTAS",
            "--estructura", "CBO", "--fecha", "2026-11-10", "--json",
        ])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertEqual(datos["datos"]["valor"], "OF-202611-01_TEST_VENTAS_CBO_20261110")
        self.assertEqual(datos["modo"], "dry_run")

    def test_json_antes_del_subcomando_tambien_funciona(self) -> None:
        codigo, salida = self._correr([
            "--json", "anuncio", "--concepto", "regreso-laboral", "--formato", "video", "--hook", "dolor", "--version", "1",
        ])
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida)["datos"]["valor"], "regreso-laboral_video_dolor_v1")

    def test_sin_json_imprime_el_valor_desnudo(self) -> None:
        codigo, salida = self._correr(["conjunto", "--audiencia", "amplia", "--ubicaciones", "automaticas", "--idioma", "es-ES"])
        self.assertEqual(codigo, 0)
        self.assertEqual(salida.strip(), "amplia_automaticas_es-ES")

    def test_nombre_invalido_sale_3(self) -> None:
        codigo, _ = self._correr(["anuncio", "--concepto", "mal|nombre", "--formato", "video", "--hook", "dolor", "--version", "1"])
        self.assertEqual(codigo, 3)

    def test_url_y_resolver(self) -> None:
        codigo, salida = self._correr(["url", "--base", "https://ofertalanding.com/ir", "--oferta", "OF-202611-01", "--json"])
        self.assertEqual(codigo, 0)
        plantilla = json.loads(salida)["datos"]["valor"]
        self.assertIn("{{campaign.id}}", plantilla)
        codigo, salida = self._correr([
            "resolver", "--plantilla", plantilla, "--campaign-name", "C", "--campaign-id", "1",
            "--adset-name", "A", "--adset-id", "2", "--ad-name", "D", "--ad-id", "3", "--json",
        ])
        self.assertEqual(codigo, 0)
        self.assertIn("adid=3", json.loads(salida)["datos"]["valor"])

    def test_subcomando_desconocido_sale_2(self) -> None:
        codigo, _ = self._correr(["no-existe"])
        self.assertEqual(codigo, 2)


if __name__ == "__main__":
    unittest.main()
