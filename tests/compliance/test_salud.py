"""Pruebas de ``compliance.salud`` (X1, D-04): paridad con el oráculo, casos límite por umbral,
construcción de ``senal_pausa.json`` y la CLI (``evaluar``/``pausa``, dry-run y ``--aplicar``).

Fixtures propias: ``tests/fixtures/compliance/salud/{parametros,limites}.yaml`` (copia de
``tests/fixtures/engine/empresa_prueba/`` -- B1, solo lectura -- con ``ratio_disputas_pausa`` fijado
en ``"0.005"`` para coincidir con el oráculo) y ``estado-*.json``. El oráculo
(``.claude/skills/x1-compliance/scripts/regla_salud.py`` y sus 21 series en
``evals/salud/series.json``) es de otra sesión y se lee, nunca se edita.
"""
from __future__ import annotations

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType

from engine.errores import ErrorLimite, ErrorValidacion
from engine.limites import cargar_limites
from engine.parametros import cargar_parametros

from compliance.salud import (
    ParametrosSalud,
    cargar_parametros_salud,
    construir_senal_pausa,
    decidir,
    escribir_senal_pausa,
    main,
    validar_estado,
)

from tests.compliance.apoyo import PruebaBase

RAIZ_REPO = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ_REPO / "tests" / "fixtures" / "compliance" / "salud"
PARAMETROS_PRUEBA = FIXTURES / "parametros.yaml"
LIMITES_PRUEBA = FIXTURES / "limites.yaml"
LIMITES_REALES_SIN_RATIO = RAIZ_REPO / "empresa" / "limites.yaml"  # ratio_disputas_pausa: null (D-04, pendiente del dueño)

RUTA_ORACULO = RAIZ_REPO / ".claude" / "skills" / "x1-compliance" / "scripts" / "regla_salud.py"
RUTA_SERIES = RAIZ_REPO / ".claude" / "skills" / "x1-compliance" / "evals" / "salud" / "series.json"


def _cargar_oraculo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("x1_regla_salud_oraculo_solo_lectura", RUTA_ORACULO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _params_prueba(**cambios) -> ParametrosSalud:
    """``ParametrosSalud`` con los valores de ``series.json`` (los del oráculo), con overrides puntuales."""
    datos = json.loads(RUTA_SERIES.read_text(encoding="utf-8"))["parametros"]
    datos = dict(datos, **cambios)
    datos.setdefault("disputas_ventana_dias", 30)
    return ParametrosSalud(**datos)


def _estado_base(**cambios) -> dict:
    base = {
        "account_status": "ACTIVE", "calidad_cuenta_meta": "Saludable", "calidad_edad_dias": 2,
        "rechazos": [], "pagos_30d": 200, "disputas_30d": 0, "reembolsos_n": 40, "reembolsos_pct": 4,
        "edad_salud_h": 3, "stripe_aviso": None,
    }
    base.update(cambios)
    return base


class PruebaParidadConOraculo(PruebaBase):
    """``decidir`` debe dar el MISMO resultado que ``regla_salud.decidir`` sobre las 21 series (D-04)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.oraculo = _cargar_oraculo()
        cls.datos = json.loads(RUTA_SERIES.read_text(encoding="utf-8"))
        cls.params = ParametrosSalud(**cls.datos["parametros"])

    def test_el_oraculo_coincide_con_sus_propias_series(self) -> None:
        # Control: si esto falla, el oráculo (de otra sesión) cambió; no se toca desde aquí.
        fallos = self.oraculo.correr_series(RUTA_SERIES)
        self.assertEqual(fallos, [], f"el oráculo ya no coincide con sus propias series: {fallos}")

    def test_las_21_series_coinciden_con_el_oraculo_y_con_lo_esperado(self) -> None:
        self.assertEqual(len(self.datos["series"]), 21)
        for serie in self.datos["series"]:
            with self.subTest(serie=serie["id"]):
                del_oraculo = self.oraculo.decidir(serie["estado"], self.datos["parametros"])
                propio = decidir(serie["estado"], self.params)
                esperado = serie["esperado"]
                for clave in ("accion", "alcance", "lanzamientos_bloqueados"):
                    self.assertEqual(propio[clave], del_oraculo[clave], f"{serie['id']}: {clave} (vs oráculo)")
                    self.assertEqual(propio[clave], esperado[clave], f"{serie['id']}: {clave} (vs esperado)")
                self.assertTrue(set(del_oraculo["alertas"]) <= set(propio["alertas"]), f"{serie['id']}: alertas (vs oráculo)")
                self.assertTrue(set(esperado.get("alertas", [])) <= set(propio["alertas"]), f"{serie['id']}: alertas (vs esperado)")


class PruebaCasosLimitePorUmbral(PruebaBase):
    """Una pareja tope-exacto / tope+1 por umbral (convenciones §11): cruzar el umbral cambia la acción."""

    def setUp(self) -> None:
        super().setUp()
        self.params = _params_prueba()

    def test_rechazos_congelar_tope_menos_uno_congela_solo_el_angulo(self) -> None:
        estado = _estado_base(rechazos=[{"hace_dias": 1, "tipo": "pieza", "revertido": False}])
        r = decidir(estado, self.params)  # 1 rechazo < rechazos_congelar (2)
        self.assertEqual(r["accion"], "congelar_angulo")
        self.assertEqual(r["alcance"], "angulo")

    def test_rechazos_congelar_tope_exacto_congela_la_cuenta(self) -> None:
        estado = _estado_base(rechazos=[
            {"hace_dias": 1, "tipo": "pieza", "revertido": False},
            {"hace_dias": 2, "tipo": "pieza", "revertido": False},
        ])
        r = decidir(estado, self.params)  # 2 rechazos == rechazos_congelar (2)
        self.assertEqual(r["accion"], "congelar_hoja")
        self.assertEqual(r["alcance"], "cuenta")
        self.assertIn("bajar_D5_D9_a_N1", r["alertas"])

    def test_rechazos_ventana_dias_justo_fuera_no_cuenta(self) -> None:
        estado = _estado_base(rechazos=[{"hace_dias": 8, "tipo": "pieza", "revertido": False}])  # ventana = 7
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "seguir")

    def test_rechazos_ventana_dias_justo_dentro_cuenta(self) -> None:
        estado = _estado_base(rechazos=[{"hace_dias": 7, "tipo": "pieza", "revertido": False}])
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "congelar_angulo")

    def test_ratio_disputas_pausa_justo_debajo_no_pausa(self) -> None:
        # pagos=201, casos=1 -> ratio=1/201=0.004975... < 0.005; casos(1) < disputas_casos_alerta(2)
        estado = _estado_base(pagos_30d=201, disputas_30d=1)
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "seguir")

    def test_ratio_disputas_pausa_tope_exacto_pausa_la_oferta(self) -> None:
        # pagos=200, casos=1 -> ratio=1/200=0.005 == ratio_disputas_pausa
        estado = _estado_base(pagos_30d=200, disputas_30d=1)
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "pausar_oferta")
        self.assertEqual(r["alcance"], "oferta")
        self.assertIn("proponer_pausa_macro_gate_H", r["alertas"])

    def test_disputas_casos_pausa_tope_menos_uno_solo_alerta(self) -> None:
        # pagos < disputas_muestra_min_pagos (50): manda el conteo, no el ratio
        estado = _estado_base(pagos_30d=40, disputas_30d=2)  # disputas_casos_pausa = 3
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "seguir")
        self.assertIn("alerta_disputas", r["alertas"])

    def test_disputas_casos_pausa_tope_exacto_pausa(self) -> None:
        estado = _estado_base(pagos_30d=40, disputas_30d=3)
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "pausar_oferta")

    def test_reembolsos_pausa_pct_justo_debajo_solo_alerta(self) -> None:
        estado = _estado_base(reembolsos_n=20, reembolsos_pct="11.99")  # alerta=8, pausa=12
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "seguir")
        self.assertIn("alerta_reembolsos", r["alertas"])

    def test_reembolsos_pausa_pct_tope_exacto_pausa(self) -> None:
        estado = _estado_base(reembolsos_n=20, reembolsos_pct=12)
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "pausar_oferta")

    def test_reembolsos_n_min_justo_debajo_no_evalua(self) -> None:
        estado = _estado_base(reembolsos_n=19, reembolsos_pct=90)  # 90 % pero sin muestra (n_min=20)
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "seguir")
        self.assertNotIn("alerta_reembolsos", r["alertas"])

    def test_salud_max_antiguedad_h_tope_exacto_no_bloquea(self) -> None:
        estado = _estado_base(edad_salud_h=24)  # salud_max_antiguedad_h = 24
        r = decidir(estado, self.params)
        self.assertFalse(r["lanzamientos_bloqueados"])

    def test_salud_max_antiguedad_h_tope_mas_uno_bloquea(self) -> None:
        estado = _estado_base(edad_salud_h=25)
        r = decidir(estado, self.params)
        self.assertTrue(r["lanzamientos_bloqueados"])
        self.assertIn("salud_vieja", r["alertas"])

    def test_declaracion_calidad_cuenta_max_dias_tope_exacto_no_bloquea(self) -> None:
        estado = _estado_base(calidad_edad_dias=7)  # declaracion_calidad_cuenta_max_dias = 7
        r = decidir(estado, self.params)
        self.assertFalse(r["lanzamientos_bloqueados"])

    def test_declaracion_calidad_cuenta_max_dias_tope_mas_uno_bloquea(self) -> None:
        estado = _estado_base(calidad_edad_dias=8)
        r = decidir(estado, self.params)
        self.assertTrue(r["lanzamientos_bloqueados"])
        self.assertIn("declaracion_calidad_vencida", r["alertas"])

    def test_estado_meta_requerido_para_lanzar_distinto_congela_la_hoja(self) -> None:
        estado = _estado_base(calidad_cuenta_meta="Necesita atención")
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "congelar_hoja")
        self.assertIn("auditar_14_dias", r["alertas"])

    def test_calidad_restringida_pausa_la_cuenta_por_encima_de_todo(self) -> None:
        estado = _estado_base(calidad_cuenta_meta="Restringida")
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "PAUSA")
        self.assertEqual(r["alcance"], "cuenta")

    def test_account_status_distinto_de_active_pausa_la_cuenta(self) -> None:
        estado = _estado_base(account_status="DISABLED")
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "PAUSA")

    def test_stripe_aviso_de_cuenta_pausa_por_encima_de_disputas(self) -> None:
        estado = _estado_base(stripe_aviso="suspension", pagos_30d=1000, disputas_30d=5)  # disputas pausaría la oferta
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "PAUSA")  # PAUSA > pausar_oferta: gana la más grave

    def test_stripe_aviso_de_oferta_pausa_la_oferta(self) -> None:
        estado = _estado_base(stripe_aviso="retraso_pago")
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "pausar_oferta")

    def test_stripe_aviso_informacion_solo_alerta(self) -> None:
        estado = _estado_base(stripe_aviso="informacion")
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "seguir")
        self.assertIn("stripe_pide_informacion", r["alertas"])

    def test_gana_la_accion_mas_grave_entre_varias(self) -> None:
        estado = _estado_base(
            rechazos=[{"hace_dias": 1, "tipo": "pieza", "revertido": False}],
            pagos_30d=1000, disputas_30d=3,
        )
        r = decidir(estado, self.params)
        self.assertEqual(r["accion"], "pausar_oferta")  # más grave que congelar_angulo


class PruebaValidarEstado(PruebaBase):
    def test_falta_un_campo_obligatorio_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            validar_estado({"account_status": "ACTIVE"})

    def test_no_es_un_objeto_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            validar_estado(["no", "es", "un", "objeto"])  # type: ignore[arg-type]

    def test_tipo_de_rechazo_desconocido_es_error_de_validacion(self) -> None:
        estado = _estado_base(rechazos=[{"hace_dias": 1, "tipo": "fantasia", "revertido": False}])
        with self.assertRaises(ErrorValidacion):
            validar_estado(estado)

    def test_stripe_aviso_desconocido_es_error_de_validacion(self) -> None:
        estado = _estado_base(stripe_aviso="inventado")
        with self.assertRaises(ErrorValidacion):
            validar_estado(estado)

    def test_entero_negativo_es_error_de_validacion(self) -> None:
        estado = _estado_base(pagos_30d=-1)
        with self.assertRaises(ErrorValidacion):
            validar_estado(estado)

    def test_estado_valido_se_normaliza_con_defectos(self) -> None:
        normalizado = validar_estado({
            "account_status": "ACTIVE", "pagos_30d": 10, "disputas_30d": 0, "reembolsos_n": 0,
            "reembolsos_pct": 0, "edad_salud_h": 1,
        })
        self.assertIsNone(normalizado["calidad_cuenta_meta"])
        self.assertIsNone(normalizado["stripe_aviso"])
        self.assertEqual(normalizado["rechazos"], [])
        self.assertEqual(normalizado["reembolsos_pct"], Decimal(0))


class PruebaCargarParametrosSalud(PruebaBase):
    def test_carga_desde_parametros_y_limites_de_prueba(self) -> None:
        par = cargar_parametros(PARAMETROS_PRUEBA)
        lim = cargar_limites(LIMITES_PRUEBA)
        params = cargar_parametros_salud(par, lim)
        self.assertEqual(params.rechazos_congelar, 2)
        self.assertEqual(str(params.ratio_disputas_pausa), "0.005")
        self.assertEqual(params.disputas_ventana_dias, 30)

    def test_ratio_disputas_pausa_nulo_en_limites_reales_es_parametro_faltante(self) -> None:
        # D-04: el dueño todavía no fijó empresa/limites.yaml -> ratio_disputas_pausa: null (fail-closed).
        par = cargar_parametros(PARAMETROS_PRUEBA)
        lim = cargar_limites(LIMITES_REALES_SIN_RATIO)
        with self.assertRaises(ErrorLimite) as cm:
            cargar_parametros_salud(par, lim)
        self.assertEqual(cm.exception.codigo_salida, 5)


class PruebaConstruirSenalPausa(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.params = _params_prueba()
        self.ahora = lambda: datetime(2026, 11, 12, 9, 0, 0, tzinfo=timezone.utc)

    def test_seguir_sin_alertas_da_verde_y_no_emitida(self) -> None:
        r = decidir(_estado_base(), self.params)
        senal = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=self.params, ahora=self.ahora)
        self.assertEqual(senal["nivel"], "verde")
        self.assertEqual(senal["accion_solicitada"], "ninguna")
        self.assertFalse(senal["emitida"])
        self.assertEqual(senal["motivo"], "ninguno")
        self.assertIsNone(senal["consumida_por"])

    def test_pausar_oferta_por_disputas_da_rojo_y_motivo_disputas(self) -> None:
        estado = _estado_base(pagos_30d=200, disputas_30d=1)
        r = decidir(estado, self.params)
        senal = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=self.params, ahora=self.ahora)
        self.assertEqual(senal["nivel"], "rojo")
        self.assertEqual(senal["motivo"], "disputas")
        self.assertEqual(senal["accion_solicitada"], "pausar")
        self.assertTrue(senal["emitida"])

    def test_pausar_oferta_por_reembolsos_da_motivo_reembolsos(self) -> None:
        estado = _estado_base(reembolsos_n=20, reembolsos_pct=12)
        r = decidir(estado, self.params)
        senal = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=self.params, ahora=self.ahora)
        self.assertEqual(senal["motivo"], "reembolsos")

    def test_rechazo_de_producto_da_motivo_otro_y_nivel_amarillo(self) -> None:
        estado = _estado_base(rechazos=[{"hace_dias": 1, "tipo": "producto", "revertido": False}])
        r = decidir(estado, self.params)
        senal = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=self.params, ahora=self.ahora)
        self.assertEqual(senal["accion_solicitada"], "pausar")
        self.assertEqual(senal["nivel"], "amarillo")
        self.assertEqual(senal["motivo"], "otro")

    def test_alerta_sin_accion_da_amarillo_y_alertar(self) -> None:
        estado = _estado_base(pagos_30d=40, disputas_30d=2)  # alerta_disputas, accion sigue "seguir"
        r = decidir(estado, self.params)
        senal = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=self.params, ahora=self.ahora)
        self.assertEqual(senal["nivel"], "amarillo")
        self.assertEqual(senal["accion_solicitada"], "alertar")
        self.assertEqual(senal["motivo"], "disputas")

    def test_sin_disputas_ventana_dias_es_error_de_validacion(self) -> None:
        params_sin_ventana = replace(self.params, disputas_ventana_dias=None)
        r = decidir(_estado_base(), self.params)
        with self.assertRaises(ErrorValidacion):
            construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=params_sin_ventana, ahora=self.ahora)

    def test_senal_sintetica_por_defecto(self) -> None:
        r = decidir(_estado_base(), self.params)
        senal = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=self.params, ahora=self.ahora)
        self.assertTrue(senal["sintetico"])
        senal_real = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=self.params, ahora=self.ahora, sintetico=False)
        self.assertFalse(senal_real["sintetico"])


class PruebaEscribirSenalPausa(PruebaBase):
    def test_escribe_json_canonico_legible(self) -> None:
        params = _params_prueba()
        r = decidir(_estado_base(), params)
        senal = construir_senal_pausa(oferta_id="OF-202611-01", resultado=r, params=params)
        destino = self.tmp / "ofertas" / "OF-202611-01" / "10-postcompra" / "senal_pausa_x1.json"
        escribir_senal_pausa(senal, destino)
        self.assertEqual(json.loads(destino.read_text(encoding="utf-8")), senal)


class PruebaCLIEvaluar(PruebaBase):
    def _correr(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = main(argv)
        return codigo, buf.getvalue()

    def test_evaluar_verde_sale_cero(self) -> None:
        codigo, salida = self._correr([
            "evaluar", "--estado", str(FIXTURES / "estado-verde.json"),
            "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA), "--json",
        ])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["datos"]["accion"], "seguir")

    def test_evaluar_cuenta_deshabilitada_informa_pausa_pero_sale_cero(self) -> None:
        # "evaluar" es una lectura: informa la acción propuesta, no bloquea su propia salida (D-04).
        codigo, salida = self._correr([
            "evaluar", "--estado", str(FIXTURES / "estado-cuenta-deshabilitada.json"),
            "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA), "--json",
        ])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertEqual(datos["datos"]["accion"], "PAUSA")

    def test_evaluar_estado_malformado_sale_tres(self) -> None:
        codigo, _ = self._correr([
            "evaluar", "--estado", str(FIXTURES / "estado-malformado.json"),
            "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA),
        ])
        self.assertEqual(codigo, 3)

    def test_evaluar_estado_inexistente_sale_dos(self) -> None:
        codigo, _ = self._correr([
            "evaluar", "--estado", str(FIXTURES / "no-existe.json"),
            "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA),
        ])
        self.assertEqual(codigo, 2)

    def test_evaluar_sin_limites_reales_sale_cinco(self) -> None:
        # Sin --limites explícito y sin --raiz, usa <raíz real>/empresa/limites.yaml: ratio_disputas_pausa
        # sigue en null (el dueño no lo fijó, D-04): falla cerrado con código 5.
        codigo, _ = self._correr([
            "evaluar", "--estado", str(FIXTURES / "estado-verde.json"), "--parametros", str(PARAMETROS_PRUEBA),
        ])
        self.assertEqual(codigo, 5)

    def test_uso_incorrecto_sale_dos(self) -> None:
        codigo, _ = self._correr(["evaluar"])  # falta --estado
        self.assertEqual(codigo, 2)


class PruebaCLIPausa(PruebaBase):
    def _correr(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = main(argv)
        return codigo, buf.getvalue()

    def test_dry_run_no_escribe_nada(self) -> None:
        destino = self.tmp / "ofertas" / "OF-202611-01" / "10-postcompra" / "senal_pausa_x1.json"
        codigo, salida = self._correr([
            "pausa", "--estado", str(FIXTURES / "estado-pausa-dura-disputas.json"), "--oferta", "OF-202611-01",
            "--salida", str(destino), "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA),
            "--raiz", str(self.tmp), "--ahora", "2026-11-12T09:00:00Z", "--json",
        ])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertEqual(datos["modo"], "dry_run")
        self.assertFalse(destino.exists())
        self.assertEqual(datos["datos"]["senal_pausa"]["accion_solicitada"], "pausar")

    def test_aplicar_escribe_y_valida_contra_el_esquema(self) -> None:
        destino = self.tmp / "ofertas" / "OF-202611-01" / "10-postcompra" / "senal_pausa_x1.json"
        codigo, salida = self._correr([
            "pausa", "--estado", str(FIXTURES / "estado-pausa-dura-disputas.json"), "--oferta", "OF-202611-01",
            "--salida", str(destino), "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA),
            "--raiz", str(self.tmp), "--ahora", "2026-11-12T09:00:00Z", "--aplicar", "--json",
        ])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertEqual(datos["modo"], "live")
        self.assertTrue(destino.is_file())
        escrito = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(escrito["oferta_id"], "OF-202611-01")
        self.assertEqual(escrito["accion_solicitada"], "pausar")
        self.assertIsNone(escrito["consumida_por"])

    def test_salida_fuera_de_la_carpeta_de_la_oferta_sale_dos(self) -> None:
        destino = self.tmp / "fuera" / "senal_pausa_x1.json"
        codigo, _ = self._correr([
            "pausa", "--estado", str(FIXTURES / "estado-verde.json"), "--oferta", "OF-202611-01",
            "--salida", str(destino), "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA),
            "--raiz", str(self.tmp), "--aplicar",
        ])
        self.assertEqual(codigo, 2)
        self.assertFalse(destino.exists())

    def test_salida_de_otra_oferta_sale_dos(self) -> None:
        destino = self.tmp / "ofertas" / "OF-202611-02" / "10-postcompra" / "senal_pausa_x1.json"
        codigo, _ = self._correr([
            "pausa", "--estado", str(FIXTURES / "estado-verde.json"), "--oferta", "OF-202611-01",
            "--salida", str(destino), "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA),
            "--raiz", str(self.tmp), "--aplicar",
        ])
        self.assertEqual(codigo, 2)

    def test_raiz_con_entorno_produccion_sale_dos(self) -> None:
        import os
        from unittest import mock

        destino = self.tmp / "ofertas" / "OF-202611-01" / "10-postcompra" / "senal_pausa_x1.json"
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "produccion"}):
            codigo, _ = self._correr([
                "pausa", "--estado", str(FIXTURES / "estado-verde.json"), "--oferta", "OF-202611-01",
                "--salida", str(destino), "--parametros", str(PARAMETROS_PRUEBA), "--limites", str(LIMITES_PRUEBA),
                "--raiz", str(self.tmp),
            ])
        self.assertEqual(codigo, 2)


class PruebaUso(PruebaBase):
    def test_sin_subcomando_sale_dos(self) -> None:
        self.assertEqual(main([]), 2)

    def test_subcomando_desconocido_sale_dos(self) -> None:
        self.assertEqual(main(["vuela"]), 2)


if __name__ == "__main__":
    unittest.main()
