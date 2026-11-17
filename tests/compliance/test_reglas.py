"""Pruebas de :mod:`compliance.reglas`: autosellado y forma de ``reglas_sensibles.yaml``."""
from __future__ import annotations

import yaml

from engine.errores import ErrorValidacion

from compliance.reglas import (
    RUTA_POR_DEFECTO,
    cargar_reglas,
    cargar_terminos_adicionales,
    categorias_de_locale,
    combinar_categorias,
)

from tests.compliance.apoyo import PruebaBase, escribir_regla_alterada


class PruebaCargarReglas(PruebaBase):
    def test_carga_las_reglas_del_repositorio_y_autentica_el_hash(self) -> None:
        reglas = cargar_reglas()
        # B6b (ola 2): 1.0.0 -> 1.1.0 (MINOR, aditivo: nuevos locales/categorías y los campos
        # claves_lista_negra/revision_nativa; convenciones §12, ningún campo existente cambió forma).
        self.assertEqual(reglas.reglas_version, "1.1.0")
        self.assertIn("es-ES", reglas.locales)
        self.assertIn("en-US", reglas.locales)
        self.assertIn("dominio", reglas.aplicado_a)
        self.assertIn("og", reglas.aplicado_a)

    def test_reglas_alteradas_sin_resellar_no_corren(self) -> None:
        """"reglas_claims.yaml != reglas_version firmada: el lint no corre" (docs/06 N09)."""
        alterado = escribir_regla_alterada(self.tmp / "reglas_sensibles.yaml")
        with self.assertRaises(ErrorValidacion) as ctx:
            cargar_reglas(alterado)
        self.assertIn("alteradas", str(ctx.exception))

    def test_archivo_ausente_no_corre(self) -> None:
        with self.assertRaises(ErrorValidacion):
            cargar_reglas(self.tmp / "no-existe.yaml")

    def test_nivel_desconocido_en_una_categoria_es_invalido(self) -> None:
        def mutar(datos: dict) -> None:
            datos["generales"]["urgencia_falsa"]["violeta"] = [r"\bx\b"]

        alterado = escribir_regla_alterada(self.tmp / "reglas.yaml", mutar=mutar)
        # recalcular el hash para que la prueba aísle la validación de forma, no el autosellado
        import yaml

        from engine import comun

        datos = comun.cargar_yaml(alterado)
        datos["hash_contenido"] = comun.hash_objeto(datos, excluir=("hash_contenido",))
        alterado.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            cargar_reglas(alterado)

    def test_locale_sin_reglas_es_fail_closed(self) -> None:
        reglas = cargar_reglas()
        with self.assertRaises(ErrorValidacion):
            categorias_de_locale(reglas, "pt-BR", None)

    def test_macro_nicho_dinero_selecciona_categoria_finanzas(self) -> None:
        reglas = cargar_reglas()
        categorias = categorias_de_locale(reglas, "es-ES", "dinero")
        self.assertEqual(set(categorias), {"finanzas"})

    def test_macro_nicho_ausente_mira_todas_las_categorias_del_locale(self) -> None:
        reglas = cargar_reglas()
        categorias = categorias_de_locale(reglas, "es-ES", None)
        # B6b (ola 2) agregó "relaciones" (antes solo tenía reglas generales, pedido en el README de B6).
        self.assertEqual(set(categorias), {"salud", "finanzas", "relaciones"})

    def test_ruta_por_defecto_existe_y_es_el_archivo_del_paquete(self) -> None:
        self.assertTrue(RUTA_POR_DEFECTO.is_file())

    def test_claves_lista_negra_declaradas(self) -> None:
        """Decisión 1b (``compliance/README.md``): solo estas tres (``campos_prohibidos`` = ``tracking.json › datos_sensibles``), nunca a ciegas."""
        reglas = cargar_reglas()
        self.assertEqual(set(reglas.claves_lista_negra), {"claims_prohibidos", "claims_a_evitar", "campos_prohibidos"})

    def test_revision_nativa_declara_hipotesis_sin_hablante(self) -> None:
        reglas = cargar_reglas()
        for locale in ("it-IT", "pl-PL", "ro-RO", "fr-FR", "de-DE"):
            self.assertIs(reglas.revision_nativa.get(locale), False, locale)
        # es-ES/en-US/es-AR/es-MX no están marcados como hipótesis sin revisar.
        for locale in ("es-ES", "en-US", "es-AR", "es-MX"):
            self.assertIsNot(reglas.revision_nativa.get(locale), False, locale)

    def test_relaciones_tiene_lexico_en_los_locales_pedidos(self) -> None:
        reglas = cargar_reglas()
        for locale in ("es-ES", "en-US", "es-AR", "es-MX", "it-IT", "pl-PL"):
            self.assertIn("relaciones", reglas.locales[locale], locale)
            self.assertTrue(reglas.locales[locale]["relaciones"].get("rojo"), locale)

    def test_locales_de_la_ola_2_tienen_salud_y_finanzas(self) -> None:
        reglas = cargar_reglas()
        for locale in ("es-AR", "es-MX", "it-IT", "pl-PL", "ro-RO", "fr-FR", "de-DE"):
            self.assertIn("salud", reglas.locales[locale], locale)
            self.assertIn("finanzas", reglas.locales[locale], locale)


class PruebaTerminosAdicionales(PruebaBase):
    """D-02b: ``empresa/compliance/terminos_sensibles/<locale>.yaml`` suma sin poder debilitar."""

    def _raiz_con_terminos(self, locale: str, contenido: dict) -> None:
        destino = self.tmp / "empresa" / "compliance" / "terminos_sensibles" / f"{locale}.yaml"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(yaml.safe_dump(contenido, allow_unicode=True), encoding="utf-8")

    def test_archivo_ausente_no_falla_y_no_aporta_nada(self) -> None:
        extra, avisos = cargar_terminos_adicionales("es-ES", raiz=self.tmp)
        self.assertEqual(extra, {})
        self.assertEqual(avisos, [])

    def test_archivo_con_patron_nuevo_se_suma(self) -> None:
        self._raiz_con_terminos("es-ES", {"salud": {"rojo": [r"\bpalabra-de-prueba\b"]}})
        extra, avisos = cargar_terminos_adicionales("es-ES", raiz=self.tmp)
        self.assertEqual(extra, {"salud": {"rojo": [r"\bpalabra-de-prueba\b"]}})
        self.assertEqual(avisos, [])

    def test_patron_invalido_se_ignora_y_se_informa(self) -> None:
        self._raiz_con_terminos("es-ES", {"salud": {"rojo": ["(["]}})
        extra, avisos = cargar_terminos_adicionales("es-ES", raiz=self.tmp)
        self.assertEqual(extra, {})
        self.assertTrue(avisos)

    def test_categorias_de_locale_incluye_adicionales_cuando_se_pide(self) -> None:
        self._raiz_con_terminos("es-ES", {"salud": {"rojo": [r"\bpalabra-de-prueba\b"]}})
        reglas = cargar_reglas()
        sin_extra = categorias_de_locale(reglas, "es-ES", "salud")
        con_extra = categorias_de_locale(reglas, "es-ES", "salud", incluir_adicionales=True, raiz=self.tmp)
        self.assertNotIn(r"\bpalabra-de-prueba\b", sin_extra["salud"]["rojo"])
        self.assertIn(r"\bpalabra-de-prueba\b", con_extra["salud"]["rojo"])

    def test_combinar_categorias_no_puede_debilitar_una_regla_base(self) -> None:
        base = {"salud": {"rojo": [r"\bcura\b"]}}
        extra = {"salud": {"amarillo": [r"\bcura\b"]}}  # intenta mover "cura" a un nivel más débil
        combinado, avisos = combinar_categorias(base, extra)
        self.assertNotIn(r"\bcura\b", combinado["salud"].get("amarillo", []))
        self.assertIn(r"\bcura\b", combinado["salud"]["rojo"])
        self.assertTrue(avisos)

    def test_combinar_categorias_duplicado_en_el_mismo_nivel_es_no_op(self) -> None:
        base = {"salud": {"rojo": [r"\bcura\b"]}}
        extra = {"salud": {"rojo": [r"\bcura\b", r"\bnuevo-termino\b"]}}
        combinado, avisos = combinar_categorias(base, extra)
        self.assertEqual(combinado["salud"]["rojo"].count(r"\bcura\b"), 1)
        self.assertIn(r"\bnuevo-termino\b", combinado["salud"]["rojo"])


if __name__ == "__main__":
    import unittest

    unittest.main()
