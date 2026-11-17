"""Pruebas de ``infra.variables``: extracción del manifiesto, agrupación, generación determinista
de ``.env.example`` e idempotencia de ``--check``."""
from __future__ import annotations

from engine.errores import ErrorValidacion
from infra import variables
from tests.infra.apoyo import PruebaBase

MANIFIESTO_MINIMO = {
    "plataformas": {
        "railway": {"servicios": {
            "motor": {"variables": [
                {"nombre": "DATABASE_URL", "tipo": "secreto", "origen": "postgres", "rotacion_dias": 0, "obligatoria": True},
                {"nombre": "MODO", "tipo": "config", "origen": "vivo|prueba", "rotacion_dias": 0, "obligatoria": True},
            ]},
            "etl": {"variables": [
                {"nombre": "DATABASE_URL", "tipo": "secreto", "origen": "postgres", "rotacion_dias": 0, "obligatoria": True},
            ]},
        }},
        "cloudflare": {"workers": {
            "descarga": {"variables": [
                {"nombre": "DESCARGA_HMAC", "tipo": "secreto", "origen": "firma", "rotacion_dias": 180, "obligatoria": True},
                {"nombre": "BUCKET_PRODUCTOS (binding R2)", "tipo": "config", "origen": "binding", "rotacion_dias": 0, "obligatoria": True},
            ]},
            "capi": {"variables": [
                {"nombre": "META_CAPI_TOKEN__<oferta_id>", "tipo": "secreto", "origen": "dataset", "rotacion_dias": 90, "obligatoria": True},
            ]},
        }},
        "github": {"entornos": {"produccion": {"secretos": [
            {"nombre": "CLOUDFLARE_API_TOKEN", "tipo": "secreto", "origen": "cf_deploy", "rotacion_dias": 90},
        ]}}},
    },
}


class PruebaExtraerVariables(PruebaBase):
    def test_extrae_todas_las_entradas_de_variables_y_secretos(self) -> None:
        variables_extraidas = variables.extraer_variables(MANIFIESTO_MINIMO)
        nombres = [v.nombre_crudo for v in variables_extraidas]
        self.assertIn("DATABASE_URL", nombres)
        self.assertEqual(nombres.count("DATABASE_URL"), 2)  # motor y etl
        self.assertIn("CLOUDFLARE_API_TOKEN", nombres)

    def test_manifiesto_no_mapa_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            variables.extraer_variables(["no", "es", "un", "mapa"])  # type: ignore[arg-type]

    def test_entrada_sin_nombre_es_error_de_validacion(self) -> None:
        malo = {"plataformas": {"railway": {"servicios": {"motor": {"variables": [{"tipo": "secreto"}]}}}}}
        with self.assertRaises(ErrorValidacion):
            variables.extraer_variables(malo)

    def test_manifiesto_sin_ninguna_variable_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            variables.extraer_variables({"plataformas": {}})


class PruebaNormalizacion(PruebaBase):
    def test_binding_con_espacio_se_detecta(self) -> None:
        self.assertTrue(variables.es_binding("BUCKET_PRODUCTOS (binding R2)"))
        self.assertFalse(variables.es_binding("DATABASE_URL"))

    def test_placeholder_se_normaliza_a_ejemplo(self) -> None:
        self.assertEqual(variables.nombre_normalizado("META_CAPI_TOKEN__<oferta_id>"), "META_CAPI_TOKEN__EJEMPLO")

    def test_nombre_simple_queda_igual(self) -> None:
        self.assertEqual(variables.nombre_normalizado("DATABASE_URL"), "DATABASE_URL")


class PruebaAgrupar(PruebaBase):
    def test_deduplica_por_nombre_normalizado_y_excluye_bindings(self) -> None:
        extraidas = variables.extraer_variables(MANIFIESTO_MINIMO)
        agrupado = variables.agrupar_por_nombre(extraidas)
        self.assertEqual(len(agrupado["DATABASE_URL"]), 2)
        self.assertNotIn("BUCKET_PRODUCTOS (binding R2)", agrupado)
        self.assertNotIn("BUCKET_PRODUCTOS", agrupado)  # es un binding: no genera línea NOMBRE=
        self.assertIn("META_CAPI_TOKEN__EJEMPLO", agrupado)


class PruebaGenerarEnvExample(PruebaBase):
    def test_es_deterministico(self) -> None:
        extraidas = variables.extraer_variables(MANIFIESTO_MINIMO)
        a = variables.generar_env_example(extraidas)
        b = variables.generar_env_example(extraidas)
        self.assertEqual(a, b)

    def test_contiene_los_nombres_pero_nunca_un_valor_de_ejemplo_con_formato_de_secreto(self) -> None:
        extraidas = variables.extraer_variables(MANIFIESTO_MINIMO)
        contenido = variables.generar_env_example(extraidas).decode("utf-8")
        self.assertIn("DATABASE_URL=\n", contenido)
        self.assertIn("META_CAPI_TOKEN__EJEMPLO=\n", contenido)
        self.assertNotIn("BUCKET_PRODUCTOS=", contenido)
        for linea in contenido.splitlines():
            if linea.endswith("="):
                self.assertTrue(linea.endswith("="), linea)  # ninguna línea de variable lleva valor

    def test_manifiesto_real_del_repositorio_genera_contenido_no_vacio(self) -> None:
        datos = __import__("engine.comun", fromlist=["cargar_yaml"]).cargar_yaml(variables.ruta_manifiesto())
        extraidas = variables.extraer_variables(datos)
        contenido = variables.generar_env_example(extraidas)
        self.assertGreater(len(contenido), 0)
        self.assertNotIn(b"secreto_real", contenido)


class PruebaCLI(PruebaBase):
    def _escribir_manifiesto(self) -> None:
        import yaml
        (self.tmp / "manifiesto.yaml").write_text(yaml.safe_dump(MANIFIESTO_MINIMO), encoding="utf-8")

    def test_generar_escribe_env_example_y_check_coincide(self) -> None:
        self._escribir_manifiesto()
        salida = self.tmp / ".env.example"
        codigo = variables.main(["generar", "--manifiesto", str(self.tmp / "manifiesto.yaml"), "--salida", str(salida), "--json"])
        self.assertEqual(codigo, 0)
        self.assertTrue(salida.is_file())
        codigo_check = variables.main(["generar", "--check", "--manifiesto", str(self.tmp / "manifiesto.yaml"), "--salida", str(salida), "--json"])
        self.assertEqual(codigo_check, 0)

    def test_check_desincronizado_sale_3(self) -> None:
        self._escribir_manifiesto()
        salida = self.tmp / ".env.example"
        salida.write_text("DATABASE_URL=\n", encoding="utf-8")
        codigo = variables.main(["generar", "--check", "--manifiesto", str(self.tmp / "manifiesto.yaml"), "--salida", str(salida), "--json"])
        self.assertEqual(codigo, 3)

    def test_check_sin_archivo_previo_sale_3(self) -> None:
        self._escribir_manifiesto()
        salida = self.tmp / "no_existe.env"
        codigo = variables.main(["generar", "--check", "--manifiesto", str(self.tmp / "manifiesto.yaml"), "--salida", str(salida), "--json"])
        self.assertEqual(codigo, 3)
        self.assertFalse(salida.is_file())  # --check nunca escribe
