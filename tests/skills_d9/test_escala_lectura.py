"""Pruebas del apoyo de solo lectura de la skill D9 (``escala_lectura.py`` y ``probar_evals.py``).

Sin red, sin claves, sin tocar ``empresa/``: los límites y parámetros son los fixtures de ``evals/_base/`` (``[SUPUESTO]``) y las
únicas rutas que se leen del repositorio son los esquemas y ``contratos/gates.json``. Correr:

    .venv/bin/python -m unittest discover -s tests/skills_d9 -t . -p "test_*.py"
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import os
import re
import socket
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SKILL = RAIZ / ".claude" / "skills" / "d9-escalado"
SCRIPTS = SKILL / "scripts"


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(f"d9_{nombre}", SCRIPTS / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


escala = _cargar("escala_lectura")
evals = _cargar("probar_evals")


def _caso(nombre: str) -> dict:
    return json.loads((SKILL / "evals" / "dorados" / nombre).read_text(encoding="utf-8"))


def _preparar(nombre: str = "D01-ganador-claro.json", *, entrada=None, limites=None, parametros=None):
    caso = _caso(nombre)
    e, lim, par = evals.armar_entrada(caso)
    for k, v in (entrada or {}).items():
        e[k] = v
    lim.update(limites or {})
    par.update(parametros or {})
    return e, lim, par


def _metricas(e: dict, **cambios) -> dict:
    e["metricas"] = {**e["metricas"], **cambios}
    return e["metricas"]


class PruebaBase(unittest.TestCase):
    def setUp(self) -> None:
        def _sin_red(*_a, **_k):
            raise AssertionError("el apoyo de D9 no debe abrir sockets")
        self._socket = socket.socket
        socket.socket = _sin_red  # type: ignore[misc,assignment]
        self.addCleanup(setattr, socket, "socket", self._socket)


class PruebaEvalsDorados(PruebaBase):
    def test_los_tres_evals_dorados_pasan(self) -> None:
        resultados = evals.correr()
        self.assertEqual({r[0] for r in resultados}, {"D01", "D02", "D03"})
        for caso_id, fallas, _res in resultados:
            self.assertEqual(fallas, [], f"{caso_id}: {fallas}")

    def test_d01_ganador_claro_propone_graduar_con_el_porcentaje_permitido(self) -> None:
        e, lim, par = _preparar()
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual(codigo, 0)
        self.assertEqual((res["estado"], res["codigo"], res["accion"]), ("PROPONER", "GRADUACION_PERMITIDA", "graduar"))
        # el dueño "quiere" 22.500 y el código recorta al paso: 75 US$ (100 % del agregado de 75 US$)
        self.assertEqual(res["paso"]["nuevo_minor"], 7500)
        orden = res["orden_borrador"]
        self.assertEqual((orden["estado"], orden["emisor"], orden["aprobado_por"]), ("propuesta", "D9", None))
        self.assertEqual(orden["gate"]["gate"], "H")  # D9 en N0: gate efectivo H
        self.assertEqual(comun_errores(orden), [])

    def test_d02_una_sola_senal_no_sube(self) -> None:
        e, lim, par = _preparar("D02-senal-ambigua.json")
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual(codigo, 0)
        self.assertEqual((res["estado"], res["codigo"]), ("NO_PROPONER", "SENAL_AMBIGUA"))
        self.assertNotIn("orden_borrador", res)
        self.assertTrue(res["senales"]["retorno_7d"] and not res["senales"]["tendencia_3d"])

    def test_d03_limite_diario_de_la_empresa_no_propone_ni_un_paso_chico(self) -> None:
        e, lim, par = _preparar("D03-limite-diario-empresa.json")
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual((res["estado"], res["codigo"]), ("NO_PROPONER", "LIMITE_DIARIO_EMPRESA"))
        self.assertEqual(res["techo"]["max_presupuesto_permitido_minor"], e["presupuesto_actual_minor"])
        self.assertNotIn("orden_borrador", res)


def comun_errores(orden: dict) -> list:
    from engine import comun
    return comun.errores_de_esquema("orden_presupuesto", orden)


class PruebaFailClosed(PruebaBase):
    def test_limite_en_null_bloquea_con_5_y_lista_lo_que_falta(self) -> None:
        e, lim, par = _preparar(limites={"gasto_diario_global": None, "stop_loss_escala": None})
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["estado"], res["codigo"]), (5, "BLOQUEADO", "LIMITES_INCOMPLETOS"))
        self.assertIn("gasto_diario_global", res["faltantes"])
        self.assertIn("stop_loss_escala", res["faltantes"])

    def test_parametro_ausente_bloquea_con_5_y_no_inventa_un_valor(self) -> None:
        e, lim, par = _preparar()
        del par["escalado.campeon_compras_min"]
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "PARAMETRO_FALTANTE"))
        self.assertEqual(res["faltantes"], ["escalado.campeon_compras_min"])

    def test_parametro_null_tambien_bloquea(self) -> None:
        e, lim, par = _preparar(parametros={"escalado.reduccion_pct": None})
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "PARAMETRO_FALTANTE"))

    def test_pausa_manda_sobre_todo(self) -> None:
        e, lim, par = _preparar(entrada={"pausa": True})
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (4, "PAUSA_ACTIVA"))

    def test_el_archivo_empresa_pausa_manda_desde_la_cli(self) -> None:
        e, lim, par = _preparar()
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "empresa").mkdir()
            (t / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            (t / "e.json").write_text(json.dumps({**e, "limites": lim, "parametros": par}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as salida:
                codigo = escala.main(["dictamen", "--entrada", str(t / "e.json"), "--raiz", str(t)])
            self.assertEqual(codigo, 4)
            self.assertEqual(json.loads(salida.getvalue())["codigo"], "PAUSA_ACTIVA")

    def test_float_en_la_entrada_es_error_de_validacion(self) -> None:
        e, lim, par = _preparar()
        e["metricas"]["cpa_neto_minor"] = 6.0
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "e.json"
            ruta.write_text(json.dumps({**e, "limites": lim, "parametros": par}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(escala.main(["dictamen", "--entrada", str(ruta), "--raiz", tmp]), 3)

    def test_moneda_distinta_a_la_de_los_limites_es_3(self) -> None:
        e, lim, par = _preparar(entrada={"moneda": "EUR"})
        with self.assertRaises(escala.ErrorValidacion):
            escala.dictamen(e, lim, par)

    def test_archivos_reales_del_dueno_hoy_bloquean(self) -> None:
        """Con ``empresa/limites.yaml`` tal como está (todo null) el resultado correcto es BLOQUEADO; se prueba sobre una copia en null."""
        e, _lim, par = _preparar()
        lim_null = {k: None for k in ("gasto_diario_global", "gasto_diario_por_oferta", "aumento_presupuesto_max_pct_por_paso", "horas_min_entre_aumentos",
                                      "stop_loss_escala", "dias_cobertura_caja", "perdida_neta_acumulada_max", "limite_gasto_cuenta_meta", "moneda_limites")}
        res, codigo = escala.dictamen(e, lim_null, par)
        self.assertEqual((codigo, res["codigo"]), (5, "LIMITES_INCOMPLETOS"))


class PruebaSenalesYCriterios(PruebaBase):
    def _dictamen(self, **cambios):
        e, lim, par = _preparar()
        _metricas(e, **cambios)
        return escala.dictamen(e, lim, par)[0]

    def test_solo_rentable_se_queda_en_test(self) -> None:
        res = self._dictamen(compras_netas=6, cpa_neto_minor=900)
        self.assertEqual((res["estado"], res["codigo"], res["ganador"]["nivel"]), ("NO_PROPONER", "SIN_GANADOR", "RENTABLE"))

    def test_sin_compras_es_sin_senal(self) -> None:
        res = self._dictamen(compras_netas=0, cpa_neto_minor=None, p_cpa_menor_equilibrio=None)
        self.assertEqual((res["codigo"], res["ganador"]["nivel"]), ("SIN_GANADOR", "SIN_SENAL"))

    def test_p_baja_impide_campeon(self) -> None:
        res = self._dictamen(p_cpa_menor_equilibrio="0.79")
        self.assertEqual(res["ganador"]["nivel"], "RENTABLE")

    def test_validada_de_d8_cuenta_como_ganador(self) -> None:
        res = self._dictamen(compras_netas=6, cpa_neto_minor=900, veredicto_d8="VALIDADA")
        self.assertEqual((res["estado"], res["ganador"]["nivel"]), ("PROPONER", "VALIDADA"))

    def test_presupuesto_previo_no_gastado_no_sube(self) -> None:
        res = self._dictamen(presupuesto_previo_gastado_pct=60)
        self.assertEqual(res["codigo"], "PRESUPUESTO_PREVIO_NO_GASTADO")

    def test_datos_inmaduros_no_suben(self) -> None:
        res = self._dictamen(datos_maduros=False)
        self.assertEqual(res["codigo"], "DATOS_INMADUROS")

    def test_pocas_compras_en_la_ventana_no_suben(self) -> None:
        res = self._dictamen(compras_7d=7)
        self.assertEqual(res["codigo"], "COMPRAS_INSUFICIENTES")

    def test_ninguna_senal_no_sube(self) -> None:
        res = self._dictamen(cpa_7d_minor=1800, cpa_3d_minor=1900)
        self.assertEqual(res["codigo"], "SIN_SENAL_DE_SUBA")

    def test_umbral_exacto_pasa_y_uno_mas_no(self) -> None:
        # umbral de 7 días = 1,0 x 1300; de 3 días = 1,15 x 1300 = 1495
        self.assertEqual(self._dictamen(cpa_7d_minor=1300, cpa_3d_minor=1495)["estado"], "PROPONER")
        self.assertEqual(self._dictamen(cpa_7d_minor=1300, cpa_3d_minor=1496)["codigo"], "SENAL_AMBIGUA")
        self.assertEqual(self._dictamen(cpa_7d_minor=1301, cpa_3d_minor=1495)["codigo"], "SENAL_AMBIGUA")


class PruebaPasoYTechos(PruebaBase):
    def _escala(self, **entrada):
        e, lim, par = _preparar("D03-limite-diario-empresa.json")
        e["cuenta"]["activas"] = [{"oferta_id": "OF-202611-02", "campaign_id": "120000000000009", "max_teorico_diario_minor": 13125,
                                   "spend_cap_restante_minor": 52500, "moneda": "USD", "perdida_acumulada_minor": 0}]
        e.update({"presupuesto_actual_minor": 7500, "presupuesto_deseado_minor": 15000, "presupuesto_agregado_oferta_minor": 7500, "spend_cap_restante_minor": 52500})
        e.update(entrada)
        return e, lim, par

    def test_subida_x2_dentro_de_todos_los_topes(self) -> None:
        e, lim, par = self._escala()
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual((res["estado"], res["accion"], res["paso"]["nuevo_minor"]), ("PROPONER", "aumentar", 15000))
        self.assertEqual(res["orden_borrador"]["delta_pct"], "100.00")
        self.assertEqual(res["orden_borrador"]["horas_desde_ultimo_aumento"], 48)  # último aumento: 2026-11-10T09:00Z; ahora: 2026-11-12T09:00Z

    def test_porcentaje_del_dueno_recorta_la_suba(self) -> None:
        e, lim, par = self._escala()
        lim["aumento_presupuesto_max_pct_por_paso"] = 20
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual(res["paso"]["nuevo_minor"], 9000)  # +20 %
        self.assertTrue(any("%" in m or "paso" in m for m in res["motivos"]))

    def test_multiplo_habilitado_recorta_antes_que_nada(self) -> None:
        e, lim, par = self._escala(presupuesto_deseado_minor=37500)  # x5 deseado
        res, _ = escala.dictamen(e, lim, par)
        self.assertLessEqual(res["paso"]["nuevo_minor"], 15000)  # escalera_multiplo_max = 2 y paso <= 100 %

    def test_horas_minimas_entre_aumentos(self) -> None:
        e, lim, par = self._escala()
        e["cuenta"]["ultimo_aumento"] = "2026-11-12T07:00:00Z"
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual((res["estado"], res["codigo"]), ("NO_PROPONER", "ESPERAR_PASO_PREVIO"))

    def test_tope_exacto_pasa_y_tope_menos_uno_no_cabe(self) -> None:
        # el techo deja holgura exacta para 15.000 (máximo teórico 26.250); con un centavo menos ya no cabe
        e, lim, par = self._escala()
        lim["gasto_diario_global"] = lim["gasto_diario_por_oferta"] = 26250  # la coherencia exige por_oferta <= global
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual(res["paso"]["nuevo_minor"], 15000)
        lim["gasto_diario_global"] = lim["gasto_diario_por_oferta"] = 26249
        res, _ = escala.dictamen(e, lim, par)
        self.assertLess(res["paso"]["nuevo_minor"], 15000)

    def test_perdida_acumulada_de_empresa_frena(self) -> None:
        e, lim, par = self._escala()
        # misma campaña (se repone): su spend_cap restante solo ya supera los 3.000 US$ de pérdida máxima de la empresa (J4)
        e["cuenta"]["activas"][0]["spend_cap_restante_minor"] = 310000
        e["spend_cap_restante_minor"] = 310000
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual((res["estado"], res["codigo"]), ("NO_PROPONER", "PERDIDA_ACUMULADA_EMPRESA"))

    def test_falta_el_gasto_vitalicio_bloquea(self) -> None:
        e, lim, par = self._escala()
        e["cuenta"]["gasto_vitalicio_minor"] = None
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "DATO_DE_CUENTA_FALTANTE"))

    def test_falta_spend_cap_bloquea(self) -> None:
        e, lim, par = self._escala()
        e["spend_cap_restante_minor"] = None
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "FALTA_SPEND_CAP"))

    def test_deterioro_propone_reducir_30_por_ciento(self) -> None:
        e, lim, par = self._escala()
        _metricas(e, cpa_72h_minor=2000, gasto_72h_minor=5000)
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual((res["estado"], res["accion"], res["codigo"]), ("PROPONER", "reducir", "REDUCCION_PROPUESTA"))
        self.assertEqual(res["paso"]["nuevo_minor"], 5250)  # 7500 x 70 %
        self.assertEqual(res["orden_borrador"]["accion"], "reducir")
        self.assertEqual(comun_errores(res["orden_borrador"]), [])

    def test_deterioro_con_poco_gasto_es_ruido_y_no_reduce(self) -> None:
        e, lim, par = self._escala()
        _metricas(e, cpa_72h_minor=2000, gasto_72h_minor=1000)
        res, _ = escala.dictamen(e, lim, par)
        self.assertNotEqual(res.get("accion"), "reducir")

    def test_maximo_de_campanas_de_escala(self) -> None:
        e, lim, par = _preparar()
        e["campanas_escala_existentes"] = 2
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual(res["codigo"], "MAX_CAMPANAS_ESCALA")

    def test_la_graduacion_deja_el_test_vivo(self) -> None:
        """El ganador sigue en testeo: la campaña de test cuenta en los agregados y no se edita (regla de oro 2)."""
        e, lim, par = _preparar()
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual(res["techo"]["suma_otras_max_teorico_minor"], 13125)
        self.assertIsNone(res["orden_borrador"]["objeto"]["id_meta"])
        self.assertNotEqual(res["orden_borrador"]["objeto"]["nombre"], e["objeto"]["nombre"])


class PruebaElegibilidad(PruebaBase):
    def test_una_bandera_en_false_no_propone(self) -> None:
        for bandera in ("sello_x1_vigente", "cuenta_saludable", "tracking_sano", "sin_incidente_d10", "sin_congelacion", "sin_alerta_fatiga",
                        "reembolsos_disputas_ok", "hoja_no_pausada", "macro_nicho_permitido", "limite_diario_meta_ok"):
            e, lim, par = _preparar()
            e["elegibilidad"][bandera] = False
            res, codigo = escala.dictamen(e, lim, par)
            self.assertEqual((codigo, res["codigo"]), (0, "ELEGIBILIDAD_NO_CUMPLIDA"), bandera)
            self.assertIn(bandera, res["no_cumple_e0"])

    def test_riesgo_amarillo_no_sube_solo(self) -> None:
        e, lim, par = _preparar()
        e["elegibilidad"]["riesgo_nivel"] = "amarillo-a"
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual(res["codigo"], "ELEGIBILIDAD_NO_CUMPLIDA")

    def test_bandera_ausente_bloquea_con_5_lo_desconocido_no_se_asume(self) -> None:
        e, lim, par = _preparar()
        del e["elegibilidad"]["sello_x1_vigente"]
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"], res["faltantes"]), (5, "ELEGIBILIDAD_SIN_DATO", ["sello_x1_vigente"]))

    def test_reducir_no_exige_elegibilidad(self) -> None:
        e, lim, par = _preparar("D03-limite-diario-empresa.json")
        e["elegibilidad"]["sello_x1_vigente"] = False
        _metricas(e, cpa_72h_minor=2000, gasto_72h_minor=5000)
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual((res["estado"], res["accion"]), ("PROPONER", "reducir"))


class PruebaNivelYSello(PruebaBase):
    def test_con_d9_en_n3_el_gate_es_a_y_ejecuta_el_script(self) -> None:
        e, lim, par = _preparar(entrada={"nivel_autonomia_d9": "N3"})
        res, _ = escala.dictamen(e, lim, par)
        self.assertEqual((res["gate_efectivo"]["gate"], res["orden_borrador"]["gate"]["gate"], res["orden_borrador"]["ejecutor"]), ("A", "A", "script"))

    def test_nivel_de_autonomia_invalido_es_error_de_validacion(self) -> None:
        e, lim, par = _preparar(entrada={"nivel_autonomia_d9": "N9"})
        with self.assertRaises(escala.ErrorValidacion):
            escala.dictamen(e, lim, par)

    def test_exigir_sello_bloquea_unos_limites_sin_sello_valido(self) -> None:
        e, lim, par = _preparar(entrada={"exigir_sello": True})
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "LIMITES_SIN_SELLO_VALIDO"))

    def test_limites_incoherentes_bloquean(self) -> None:
        e, lim, par = _preparar(limites={"gasto_diario_por_oferta": 99999})  # por oferta > global
        res, codigo = escala.dictamen(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "LIMITES_INCOHERENTES"))

    def test_rol_invalido_es_error_de_validacion(self) -> None:
        e, lim, par = _preparar()
        e["objeto"]["rol"] = "refresco"
        with self.assertRaises(escala.ErrorValidacion):
            escala.dictamen(e, lim, par)


class PruebaReplica(PruebaBase):
    def _entrada(self):
        lim = {"locales_permitidos": ["pl-PL", "de-DE"], "paises_permitidos": ["PL", "DE"]}
        par = {"mercados.hija_requiere_madre_validada": True, "mercados.aperturas_max_por_ventana": 1, "mercados.ventana_dias": 14,
               "mercados.ganadores_transferidos_max": 10}
        e = {"ahora": "2026-11-30T00:00:00Z",
             "madre": {"oferta_id": "OF-202611-02", "familia_id": "FAM-202611-01", "locale": "pl-PL", "estado_veredicto": "VALIDADA"},
             "hija": {"oferta_id": "OF-202612-01", "familia_id": "FAM-202611-01", "locale": "de-DE", "paises": ["DE"], "variante_de": "OF-202611-02"},
             "aperturas_recientes": [], "ganadores_a_transferir": ["c01", "c02"], "tablero": {"origen": "codigo", "estado": "completo"}}
        return e, lim, par

    def test_replica_permitida_con_todo_en_regla(self) -> None:
        e, lim, par = self._entrada()
        res, codigo = escala.puerta_replica(e, lim, par)
        self.assertEqual((codigo, res["estado"], res["codigo"]), (0, "PROPONER", "REPLICA_PERMITIDA"))

    def test_la_madre_se_valida_antes_que_las_hijas(self) -> None:
        e, lim, par = self._entrada()
        e["madre"]["estado_veredicto"] = "PROMETEDORA"
        res, _ = escala.puerta_replica(e, lim, par)
        self.assertEqual(res["estado"], "NO_PROPONER")
        self.assertTrue(any("MADRE_NO_VALIDADA" in m for m in res["motivos"]))

    def test_tablero_marcado_a_mano_no_vale(self) -> None:
        e, lim, par = self._entrada()
        e["tablero"]["origen"] = "manual"
        res, _ = escala.puerta_replica(e, lim, par)
        self.assertTrue(any("TABLERO_NO_CALCULADO" in m for m in res["motivos"]))

    def test_cadencia_de_aperturas(self) -> None:
        e, lim, par = self._entrada()
        e["aperturas_recientes"] = ["2026-11-20T00:00:00Z"]
        res, _ = escala.puerta_replica(e, lim, par)
        self.assertTrue(any("CADENCIA" in m for m in res["motivos"]))
        e["aperturas_recientes"] = ["2026-11-10T00:00:00Z"]  # hace 20 días: fuera de la ventana de 14
        self.assertEqual(escala.puerta_replica(e, lim, par)[0]["estado"], "PROPONER")

    def test_locale_fuera_de_los_permitidos_y_familia_distinta(self) -> None:
        e, lim, par = self._entrada()
        e["hija"]["locale"] = "fr-FR"
        e["hija"]["familia_id"] = "FAM-202611-09"
        res, _ = escala.puerta_replica(e, lim, par)
        texto = " ".join(res["motivos"])
        self.assertIn("LOCALE_NO_PERMITIDO", texto)
        self.assertIn("FAMILIA_DISTINTA", texto)

    def test_listas_vacias_bloquean_con_5(self) -> None:
        e, lim, par = self._entrada()
        lim["locales_permitidos"] = []
        res, codigo = escala.puerta_replica(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "LIMITES_INCOMPLETOS"))

    def test_parametros_de_mercados_ausentes_bloquean_con_5(self) -> None:
        e, lim, par = self._entrada()
        del par["mercados.ventana_dias"]
        res, codigo = escala.puerta_replica(e, lim, par)
        self.assertEqual((codigo, res["codigo"]), (5, "PARAMETRO_FALTANTE"))


class PruebaValidarPropuesta(PruebaBase):
    PLANTILLA = SKILL / "templates" / "propuesta-de-suba.json"

    def _doc(self) -> dict:
        return json.loads(self.PLANTILLA.read_text(encoding="utf-8"))

    def test_la_plantilla_de_propuesta_valida(self) -> None:
        res, codigo = escala.validar_propuesta(self._doc())
        self.assertEqual((codigo, res["defectos"]), (0, []))

    def test_una_orden_aprobada_o_firmada_no_es_del_maker(self) -> None:
        for cambio in ({"estado": "aprobada"}, {"estado": "ejecutada"}, {"aprobado_por": {"tipo": "humano", "id": "x", "fecha": "2026-11-12T09:00:00Z"}}):
            d = self._doc()
            d["orden_presupuesto"].update(cambio)
            res, codigo = escala.validar_propuesta(d)
            self.assertEqual(codigo, 4, cambio)
            self.assertTrue(res["defectos"])

    def test_cifra_de_la_orden_distinta_a_la_del_dictamen(self) -> None:
        d = self._doc()
        d["orden_presupuesto"]["despues"]["monto"] += 1
        res, codigo = escala.validar_propuesta(d)
        self.assertEqual(codigo, 4)
        self.assertTrue(any("despues" in x for x in res["defectos"]))

    def test_sin_dictamen_proponer_no_hay_propuesta(self) -> None:
        d = self._doc()
        d["dictamen_codigo"]["estado"] = "NO_PROPONER"
        res, codigo = escala.validar_propuesta(d)
        self.assertEqual(codigo, 4)

    def test_la_salida_real_del_dictamen_valida(self) -> None:
        e, lim, par = _preparar()
        res, _ = escala.dictamen(e, lim, par)
        doc = {"estado": "propuesta", "dictamen_codigo": {"estado": res["estado"], "paso": res["paso"]}, "orden_presupuesto": res["orden_borrador"]}
        self.assertEqual(escala.validar_propuesta(doc)[1], 0)

    def test_la_cli_validar_devuelve_4_con_defectos(self) -> None:
        d = self._doc()
        d["emisor"] = "D8"
        d["orden_presupuesto"]["emisor"] = "D8"
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "p.json"
            ruta.write_text(json.dumps(d), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(escala.main(["validar", "--archivo", str(ruta)]), 4)


class PruebaPlantillas(PruebaBase):
    def test_las_plantillas_existen_y_no_tienen_secretos(self) -> None:
        for nombre in ("expediente-de-escala.md", "propuesta-de-suba.json", "kanban-idioma.md", "informe-semanal.md"):
            texto = (SKILL / "templates" / nombre).read_text(encoding="utf-8")
            self.assertGreater(len(texto), 500, nombre)
            self.assertIsNone(re.search(r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{12,}|Bearer\s+[A-Za-z0-9._-]{20,})", texto), nombre)

    def test_el_tablero_tiene_las_25_tarjetas_del_panel(self) -> None:
        texto = (SKILL / "templates" / "kanban-idioma.md").read_text(encoding="utf-8")
        ids = re.findall(r"^\| (?:TIENDA|DOMINIO|META|COBRO|CREATIVOS|LISTO) \| ([A-Z][0-9]) \|", texto, flags=re.M)
        panel = (RAIZ / "dashboard" / "web" / "lib" / "paises.js").read_text(encoding="utf-8")
        esperados = re.findall(r"\{ id: '([A-Z][0-9])', col: '", panel)
        self.assertEqual(len(ids), 25)
        self.assertEqual(sorted(ids), sorted(esperados))

    def test_los_pedidos_citados_existen_en_pedidos_md(self) -> None:
        pedidos = (SKILL / "PEDIDOS.md").read_text(encoding="utf-8")
        definidos = set(re.findall(r"^### (P-\d\d) ", pedidos, flags=re.M))
        citados: set[str] = set()
        for ruta in list(SKILL.rglob("*.md")) + list(SKILL.rglob("*.py")) + list(SKILL.rglob("*.json")):
            if ruta.name == "PEDIDOS.md":
                continue
            citados |= set(re.findall(r"\b(P-\d\d)\b", ruta.read_text(encoding="utf-8")))
        self.assertEqual(sorted(citados - definidos), [], "pedido citado sin definir en PEDIDOS.md")
        self.assertEqual(len(definidos), 18)


class PruebaSoloLecturaYAlineacion(PruebaBase):
    def test_el_script_no_escribe_ni_usa_red(self) -> None:
        for nombre in ("escala_lectura.py",):
            fuente = (SCRIPTS / nombre).read_text(encoding="utf-8")
            for prohibido in (r"\.write_text\(", r"\.write_bytes\(", r"open\([^)]*[\"'][wax]", r"shutil\.", r"os\.remove", r"unlink\(", r"requests", r"urllib", r"http\.client", r"socket", r"subprocess"):
                self.assertIsNone(re.search(prohibido, fuente), f"{nombre} contiene {prohibido!r}")

    def test_la_cli_no_crea_archivos(self) -> None:
        e, lim, par = _preparar()
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "e.json").write_text(json.dumps({**e, "limites": lim, "parametros": par}), encoding="utf-8")
            antes = sorted(p.name for p in t.rglob("*"))
            with contextlib.redirect_stdout(io.StringIO()) as salida:
                self.assertEqual(escala.main(["dictamen", "--entrada", str(t / "e.json"), "--raiz", str(t)]), 0)
            self.assertEqual(sorted(p.name for p in t.rglob("*")), antes)
            self.assertEqual(json.loads(salida.getvalue())["estado"], "PROPONER")

    def test_el_script_no_trae_cifras_de_decision(self) -> None:
        """Ningún umbral de decisión vive en el código: 300, 3000, 30 %, x2/x3/x5 y similares llegan por parámetro o límite."""
        fuente = (SCRIPTS / "escala_lectura.py").read_text(encoding="utf-8")
        sin_comentarios = "\n".join(l.split("#")[0] for l in fuente.splitlines())
        sin_docstrings = re.sub(r'"""[\s\S]*?"""', "", sin_comentarios)
        for numero in ("3000", "30000", "300", "0.30", "0.4", "0.40", "1.15", "0.8", "0.80", "1.75"):
            self.assertIsNone(re.search(rf"(?<![\w.]){re.escape(numero)}(?![\w.])", sin_docstrings), f"cifra {numero} en el código")

    def test_las_claves_de_parametros_que_ya_existen_siguen_en_parametros_yaml(self) -> None:
        """Si S-A renombra una clave existente, esta prueba avisa; las claves nuevas (pedido P-02) no se exigen."""
        import yaml
        doc = yaml.safe_load((RAIZ / "empresa" / "parametros.yaml").read_text(encoding="utf-8"))
        planos = escala._aplanar_parametros(doc)
        for clave in ("escalado.compras_min_ventana", "escalado.cpa_subir_factor", "escalado.revertir_cpa_factor", "escalado.max_campanas_escala",
                      "testeo.p_escala", "testeo.k_corte"):
            self.assertIn(clave, planos, clave)
        self.assertIn("accion:subir_presupuesto_d9", json.loads((RAIZ / "contratos" / "gates.json").read_text(encoding="utf-8"))["entradas"])

    def test_los_fixtures_llevan_la_etiqueta_de_supuesto(self) -> None:
        for nombre in ("limites_prueba.json", "parametros_prueba.json"):
            texto = (SKILL / "evals" / "_base" / nombre).read_text(encoding="utf-8")
            self.assertIn("SUPUESTO", texto)

    def test_gate_efectivo_sale_de_gates_json(self) -> None:
        gates = json.loads((RAIZ / "contratos" / "gates.json").read_text(encoding="utf-8"))["entradas"]["accion:subir_presupuesto_d9"]["gate"]
        for nivel, esperado in gates.items():
            self.assertEqual(escala._gate_de(nivel), esperado)


if __name__ == "__main__":
    unittest.main()
