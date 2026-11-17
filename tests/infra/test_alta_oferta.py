"""Pruebas de ``infra.alta_oferta``: plantilla de 11 pasos, verificación de solo lectura (sin
verificador -> pendiente, nunca verde falso), spend_cap paramétrico y escritura solo con --ejecutar."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from engine.errores import ErrorBloqueado, ErrorValidacion
from infra import alta_oferta
from tests.infra.apoyo import PruebaBase, copiar_empresa_prueba

AHORA = datetime(2026, 11, 9, 8, 0, 0, tzinfo=timezone.utc)
OFERTA = "OF-202611-01"


class PruebaPlantilla(PruebaBase):
    def test_carga_los_11_pasos_con_campos_obligatorios(self) -> None:
        pasos = alta_oferta.cargar_plantilla()
        self.assertEqual(len(pasos), 11)
        ids = [p.id for p in pasos]
        self.assertEqual(len(ids), len(set(ids)))
        for p in pasos:
            self.assertTrue(p.quien)
            self.assertTrue(p.como_se_comprueba)
            self.assertTrue(p.item_preflight)

    def test_plantilla_sin_pasos_es_error_de_validacion(self) -> None:
        ruta = self.tmp / "vacia.yaml"
        ruta.write_text("pasos: []\n", encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            alta_oferta.cargar_plantilla(ruta)

    def test_id_repetido_es_error_de_validacion(self) -> None:
        ruta = self.tmp / "dup.yaml"
        ruta.write_text(
            "pasos:\n"
            "  - {paso: 1, id: x, que: a, quien: dueno, como_se_comprueba: c, item_preflight: M-01}\n"
            "  - {paso: 2, id: x, que: b, quien: dueno, como_se_comprueba: c, item_preflight: M-01}\n",
            encoding="utf-8",
        )
        with self.assertRaises(ErrorValidacion):
            alta_oferta.cargar_plantilla(ruta)


class PruebaListar(PruebaBase):
    def test_listar_no_toca_disco_y_devuelve_los_11(self) -> None:
        datos = alta_oferta.listar(OFERTA)
        self.assertEqual(len(datos), 11)
        self.assertEqual(datos[0]["paso"], 1)

    def test_oferta_id_invalido_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            alta_oferta.listar("no-es-un-id")


class PruebaVerificar(PruebaBase):
    def test_sin_verificadores_todo_queda_pendiente(self) -> None:
        resultados = alta_oferta.verificar(OFERTA)
        self.assertEqual(len(resultados), 11)
        self.assertTrue(all(r.estado == "pendiente_verificacion" for r in resultados))

    def test_verificador_inyectado_se_usa_y_otros_quedan_pendientes(self) -> None:
        def v_dominio() -> alta_oferta.ResultadoPaso:
            return alta_oferta.ResultadoPaso("dominio-compra", "ok", "DNS resuelve", {"dominio": "ejemplo.com"})

        resultados = alta_oferta.verificar(OFERTA, verificadores={"dominio-compra": v_dominio})
        por_id = {r.id: r for r in resultados}
        self.assertEqual(por_id["dominio-compra"].estado, "ok")
        self.assertEqual(por_id["meta-dataset"].estado, "pendiente_verificacion")

    def test_verificador_que_lanza_queda_pendiente_no_falta(self) -> None:
        def v_rompe() -> alta_oferta.ResultadoPaso:
            raise RuntimeError("timeout simulado")

        resultados = alta_oferta.verificar(OFERTA, verificadores={"dominio-compra": v_rompe})
        por_id = {r.id: r for r in resultados}
        self.assertEqual(por_id["dominio-compra"].estado, "pendiente_verificacion")

    def test_estado_desconocido_de_un_verificador_es_error_de_validacion(self) -> None:
        def v_raro() -> alta_oferta.ResultadoPaso:
            return alta_oferta.ResultadoPaso("dominio-compra", "verde", "x", {})

        with self.assertRaises(ErrorValidacion):
            alta_oferta.verificar(OFERTA, verificadores={"dominio-compra": v_raro})


class PruebaSpendCap(PruebaBase):
    def test_formula_toma_el_minimo_y_redondea_hacia_abajo(self) -> None:
        # factor 1.10 x 1000 = 1100 (sin redondeo); min(5000, 1100) = 1100; + 2000 = 3100
        limite = alta_oferta.calcular_limite_gasto_cuenta_meta(
            gasto_acumulado_minor=2000, capital_anuncios_restante_minor=5000,
            spend_cap_factor="1.10", suma_topes_test_en_curso_minor=1000,
        )
        self.assertEqual(limite, 3100)

    def test_capital_restante_manda_cuando_es_el_minimo(self) -> None:
        limite = alta_oferta.calcular_limite_gasto_cuenta_meta(
            gasto_acumulado_minor=0, capital_anuncios_restante_minor=500,
            spend_cap_factor="1.50", suma_topes_test_en_curso_minor=10000,
        )
        self.assertEqual(limite, 500)

    def test_redondeo_hacia_abajo_nunca_sube_el_tope(self) -> None:
        # 1.11 x 999 = 1108.89 -> floor 1108 (nunca 1109)
        limite = alta_oferta.calcular_limite_gasto_cuenta_meta(
            gasto_acumulado_minor=0, capital_anuncios_restante_minor=999999,
            spend_cap_factor="1.11", suma_topes_test_en_curso_minor=999,
        )
        self.assertEqual(limite, 1108)

    def test_factor_invalido_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            alta_oferta.calcular_limite_gasto_cuenta_meta(
                gasto_acumulado_minor=0, capital_anuncios_restante_minor=0,
                spend_cap_factor="no-es-un-numero", suma_topes_test_en_curso_minor=0,
            )

    def test_cero_y_tope_exacto(self) -> None:
        self.assertEqual(alta_oferta.calcular_limite_gasto_cuenta_meta(
            gasto_acumulado_minor=0, capital_anuncios_restante_minor=0,
            spend_cap_factor="1.10", suma_topes_test_en_curso_minor=0,
        ), 0)


class PruebaEjecutar(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        copiar_empresa_prueba(self.tmp)

    def test_ejecutar_escribe_alta_json_con_los_resultados(self) -> None:
        resultados = alta_oferta.verificar(OFERTA)
        doc = alta_oferta.ejecutar(OFERTA, raiz=self.tmp, resultados=resultados, ahora=lambda: AHORA)
        ruta = alta_oferta.ruta_alta(self.tmp, OFERTA)
        self.assertTrue(ruta.is_file())
        self.assertEqual(json.loads(ruta.read_bytes()), doc)
        self.assertFalse(doc["completo"])  # todo pendiente sin verificadores reales
        self.assertEqual(doc["oferta_id"], OFERTA)
        for paso in doc["pasos"]:
            self.assertNotIn("valor_secreto", json.dumps(paso).lower())

    def test_ejecutar_con_todo_ok_marca_completo(self) -> None:
        pasos = alta_oferta.cargar_plantilla()
        resultados = [alta_oferta.ResultadoPaso(p.id, "ok", "listo", {}) for p in pasos]
        doc = alta_oferta.ejecutar(OFERTA, raiz=self.tmp, resultados=resultados, ahora=lambda: AHORA)
        self.assertTrue(doc["completo"])


class PruebaCliDryRunPorDefecto(PruebaBase):
    def test_ejecutar_sin_flag_no_escribe_nada(self) -> None:
        copiar_empresa_prueba(self.tmp)
        codigo = alta_oferta.main(["ejecutar", "--oferta", OFERTA, "--raiz", str(self.tmp), "--json"])
        self.assertEqual(codigo, 0)
        self.assertFalse(alta_oferta.ruta_alta(self.tmp, OFERTA).is_file())

    def test_ejecutar_con_flag_en_produccion_es_bloqueado(self) -> None:
        import os
        from unittest import mock

        copiar_empresa_prueba(self.tmp)
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "produccion"}, clear=False):
            codigo = alta_oferta.main(["ejecutar", "--oferta", OFERTA, "--ejecutar", "--json"])
        self.assertEqual(codigo, ErrorBloqueado.codigo_salida)

    def test_listar_cli_json(self) -> None:
        codigo = alta_oferta.main(["listar", "--oferta", OFERTA, "--json"])
        self.assertEqual(codigo, 0)
