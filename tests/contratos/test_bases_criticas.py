"""Pruebas de las correcciones de las críticas de las bases del testeo (bases-registro-de-cambios.md).

Cada prueba rompe UNA cosa y exige el código de la regla. Sin red ni credenciales (convenciones 11).
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import json
import os
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validar_esquemas as V

CLAVE = V.CLAVE_DE_PRUEBA


def _sin_red(caso: unittest.TestCase) -> None:
    original = socket.socket

    def bloqueado(*a, **k):
        raise AssertionError("las pruebas no pueden abrir sockets")

    socket.socket = bloqueado  # type: ignore[assignment]
    caso.addCleanup(setattr, socket, "socket", original)


def _sellar(d: dict) -> dict:
    d["sello"]["hash"] = V.sello_de_limites(d)
    return d


class PruebaCoherenciaDeLimites(unittest.TestCase):
    """B02: el archivo de límites no puede anular sus propios candados."""

    def setUp(self) -> None:
        _sin_red(self)
        self.lim = V.limites_de_prueba()

    def cambia(self, **kw) -> V.ResultadoLimites:
        d = copy.deepcopy(self.lim)
        d.update(kw)
        return V.evaluar_limites(_sellar(d), "activar", entorno="prueba")

    def test_base_coherente(self) -> None:
        self.assertEqual([], V.coherencia_limites(self.lim))
        self.assertTrue(V.evaluar_limites(self.lim, "activar", entorno="prueba"))

    def test_cada_incoherencia_bloquea(self) -> None:
        casos = {
            "tope por oferta mayor que el global": dict(gasto_diario_por_oferta=10**9),
            "perdida mayor que gasto total": dict(perdida_max_test_por_oferta=10**9),
            "gasto total mayor que el limite de cuenta": dict(gasto_total_test_por_oferta=10**9, perdida_max_test_por_oferta=1),
            "limite de cuenta mayor que el capital": dict(limite_gasto_cuenta_meta=10**9),
            "perdida acumulada mayor que el capital": dict(perdida_neta_acumulada_max=10**9),
            "simultaneas x diario mayor que el global": dict(ofertas_en_test_simultaneas_max=99),
            "importe como texto": dict(gasto_diario_global="abc"),
            "importe booleano": dict(gasto_diario_global=False),
            "importe negativo": dict(gasto_diario_global=-5),
            "factor que subestima a Meta": dict(factor_techo_teorico_diario="1.0"),
            "sin gates H minimos": dict(acciones_gate_humano=[]),
            "moneda con offset 1 en Meta": dict(moneda_limites="HUF"),
            "moneda en minusculas": dict(moneda_limites="eur"),
        }
        for nombre, kw in casos.items():
            res = self.cambia(**kw)
            self.assertFalse(res, nombre)

    def test_capital_en_riesgo_es_clave_critica_de_gastar(self) -> None:
        d = copy.deepcopy(self.lim)
        d["capital_en_riesgo_total"] = None
        res = V.evaluar_limites(_sellar(d), "gastar", entorno="prueba")
        self.assertFalse(res)
        self.assertIn("capital_en_riesgo_total", res.faltantes)

    def test_el_esquema_rechaza_factor_distinto_de_1_75_y_cero_en_topes(self) -> None:
        for kw in (dict(factor_techo_teorico_diario="0.0"), dict(gasto_diario_global=0), dict(acciones_gate_humano=["activar_campana"])):
            d = copy.deepcopy(self.lim)
            d.update(kw)
            self.assertTrue(V.errores_de_esquema("limites", d), kw)

    def test_produccion_exige_firma_y_ancla(self) -> None:
        d = copy.deepcopy(self.lim)
        res = V.evaluar_limites(d, "activar", entorno="produccion")
        self.assertFalse(res)
        self.assertTrue(any("firma" in f for f in res.faltantes))
        d["sello"]["firma"] = V.cargar_json(V.DIR_EJEMPLOS / "sello.valido.json")["firma"]  # forma SSHSIG real (CT1-04)
        self.assertTrue(V.evaluar_limites(d, "activar", entorno="produccion"))
        self.assertFalse(V.evaluar_limites(d, "activar", entorno="produccion", ancla_hash="sha256:" + "0" * 64))
        self.assertTrue(V.evaluar_limites(d, "activar", entorno="produccion", ancla_hash=d["sello"]["hash"]))
        self.assertEqual([], V.errores_de_esquema("limites", d))


class PruebaCargadoresEstrictos(unittest.TestCase):
    """m01 y MA-09."""

    def test_claves_duplicadas_se_rechazan(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            j, y = Path(t) / "a.json", Path(t) / "a.yaml"
            j.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            y.write_text("a: 1\na: 2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                V.cargar_json(j)
            with self.assertRaises(ValueError):
                V.cargar_yaml(y)

    def test_html_del_sitio_se_hashea_por_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            sitio = Path(t) / "05-landing" / "sitio"      # lo servido = el par 05-landing/sitio (CT2-16: no un «sitio» suelto del clon)
            sitio.mkdir(parents=True)
            a, b = sitio / "a.html", sitio / "b.html"
            a.write_bytes(b"<p>x</p>\n")
            b.write_bytes(b"<p>x</p>\r\n")
            self.assertNotEqual(V.hash_archivo(a), V.hash_archivo(b))
            copia = Path(t) / "historial" / "v1"           # una copia de despliegue fuera de 05-landing/sitio hashea igual su carpeta
            copia.mkdir(parents=True)
            (copia / "a.html").write_bytes(b"<p>x</p>\n")
            (copia / "b.html").write_bytes(b"<p>x</p>\r\n")
            self.assertEqual(V.hash_directorio(sitio), V.hash_directorio(copia))

    def test_hash_contenido_del_brief_ignora_lo_que_asigna_el_motor(self) -> None:
        brief = V.cargar_yaml(V.DIR_EJEMPLOS / "brief.valido.yaml")
        otro = copy.deepcopy(brief)
        otro.update({"oferta_id": "OF-209901-99", "familia_id": "FAM-9", "creado_en": "2099-01-01T00:00:00Z"})
        self.assertEqual(V.hash_contenido_brief(brief), V.hash_contenido_brief(otro))
        otro["nivel_autonomia"] = "N0" if brief["nivel_autonomia"] != "N0" else "N1"
        self.assertNotEqual(V.hash_contenido_brief(brief), V.hash_contenido_brief(otro))


class PruebaCoherenciaGlobal(unittest.TestCase):
    """M04, B04, B05, M15 y M18: mutaciones del ejemplo (hashes recalculados donde hace falta)."""

    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.dir = Path(self._t.name) / "_ejemplo"
        shutil.copytree(V.RAIZ / "ofertas" / "_ejemplo", self.dir)
        self.lim = V.limites_de_prueba()
        self.aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")

    def j(self, rel: str):
        return V.cargar_json(self.dir / rel)

    def w(self, rel: str, obj) -> None:
        (self.dir / rel).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def wc(self, camp: dict) -> None:
        camp["hash_config"] = V.hash_objeto(camp, excluir=("hash_config",))
        self.w("07-campana/campana.json", camp)

    def codigos(self, limites=None) -> set[str]:
        inf = V.validar_oferta(self.dir, limites=limites or self.lim, autonomia=self.aut, clave_firma=CLAVE)
        return {h.codigo for h in inf.errores}

    def assertDetecta(self, codigo: str, **kw) -> None:
        self.assertIn(codigo, self.codigos(**kw))

    def test_base_limpia(self) -> None:
        self.assertEqual(set(), self.codigos())

    # --- M04
    def test_fase_en_test_con_campana_en_borrador(self) -> None:
        e = self.j("estado.json"); e["fase"] = "en_test"; self.w("estado.json", e)
        self.assertDetecta("X30_FASE")

    def test_fase_validada_sin_veredicto(self) -> None:
        (self.dir / "08-operacion/veredicto_oferta.json").unlink()
        e = self.j("estado.json"); e["fase"] = "validada"; self.w("estado.json", e)
        self.assertDetecta("X30_FASE")

    def test_campana_activa_sin_ids_meta(self) -> None:
        c = self.j("07-campana/campana.json"); c["estado"] = "activa"; c["ids_meta"] = None; self.wc(c)
        self.assertDetecta("X30_FASE")

    def test_fase_que_cobra_con_price_live_nulo(self) -> None:
        e = self.j("estado.json"); e["fase"] = "listo_para_activar"; self.w("estado.json", e)
        self.assertDetecta("X30_FASE")

    def test_moneda_de_cobro_distinta_de_la_oferta(self) -> None:
        m = self.j("mercado.json"); m["moneda_cobro"] = "USD"; self.w("mercado.json", m)
        self.assertDetecta("X30_MONEDA")

    def test_locale_distinto_del_idioma_de_la_campana(self) -> None:
        m = self.j("mercado.json"); m["locale"] = "pl-PL"; self.w("mercado.json", m)
        self.assertDetecta("X30_MERCADO")

    def test_url_de_anuncio_en_otro_dominio(self) -> None:
        c = self.j("07-campana/campana.json")
        c["url"]["plantilla"] = c["url"]["plantilla"].replace("miregresolaboral.example", "evil.example")
        c["url"]["ejemplo_resuelto"] = c["url"]["ejemplo_resuelto"].replace("miregresolaboral.example", "evil.example")
        self.wc(c)
        self.assertDetecta("X30_DOMINIO")

    def test_campana_a_la_ue_sin_consentimiento_obligatorio(self) -> None:
        t = self.j("05-landing/tracking.json"); t["consent_gating"]["requerido_ue_uk"] = False; self.w("05-landing/tracking.json", t)
        self.assertDetecta("X30_CONSENT")

    # --- B05
    def test_spend_cap_sobre_la_perdida_maxima(self) -> None:
        lim = copy.deepcopy(self.lim)
        cap = self.j("07-campana/campana.json")["presupuesto"]["spend_cap"]
        lim["perdida_max_test_por_oferta"] = cap - 1
        lim["gasto_total_test_por_oferta"] = cap
        self.assertDetecta("X10_LIMITES", limites=_sellar(lim))

    def test_spend_cap_cero_significa_sin_tope(self) -> None:
        c = self.j("07-campana/campana.json"); c["presupuesto"]["spend_cap"] = 0; self.wc(c)
        self.assertIn("ESQUEMA", self.codigos())

    def test_dias_de_campana_sobre_la_ventana_del_veredicto(self) -> None:
        par = copy.deepcopy(V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml"))
        par["grupos"]["veredicto"]["dias_max"]["valor"] = 5
        inf = V.validar_oferta(self.dir, limites=self.lim, parametros=par, autonomia=self.aut, clave_firma=CLAVE)
        self.assertIn("X30_PRESUPUESTO", {h.codigo for h in inf.errores})

    # --- B04
    def test_reembolso_en_otra_moneda_no_se_compara_en_centimos(self) -> None:
        r = V.cargar_jsonl(self.dir / "10-postcompra/reembolsos.jsonl")
        r[0]["monto"]["moneda"] = "USD"
        (self.dir / "10-postcompra/reembolsos.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in r) + "\n", encoding="utf-8")
        inf = V.validar_oferta(self.dir, limites=self.lim, autonomia=self.aut, clave_firma=CLAVE)
        self.assertTrue(any(h.codigo == "X10_LIMITES" and "moneda del reembolso" in h.mensaje for h in inf.errores))

    # --- M15
    def test_categoria_especial_exige_audiencia_amplia_y_gate_legal(self) -> None:
        c = self.j("07-campana/campana.json"); c["special_ad_categories"] = ["FINANCIAL_PRODUCTS_SERVICES"]; self.wc(c)
        self.assertDetecta("X31_CATEGORIA_ESPECIAL")

    # --- M10
    def test_dominio_con_termino_sensible(self) -> None:
        t = self.j("05-landing/tracking.json"); t["dominio_verificado"] = "mejorsueno-insomnio.example"; self.w("05-landing/tracking.json", t)
        self.assertDetecta("X17_SENSIBLE")

    # --- M18
    def test_ejemplo_se_rechaza_en_produccion(self) -> None:
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "produccion"}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(V.SALIDA_VALIDACION, V.main(["oferta", str(self.dir)]))
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "prueba"}):
            self.assertFalse(V.ejemplo_permitido() is False)


class PruebaFasesYGates(unittest.TestCase):
    def test_fallida_se_puede_reabrir_con_gate_h_pero_retirada_es_final(self) -> None:
        self.assertTrue(V.transicion_fase_valida("fallida", "en_construccion"))
        self.assertEqual("H", V.gate_esperado("accion:reabrir_fallida", "N4"))
        for a in V.FASES_TRANSICIONES:
            self.assertNotEqual("retirada", a[0])

    def test_gates_nuevos_de_la_critica_ma_08(self) -> None:
        for k in ("confirmar_validada", "extender_test", "cerrar_oferta", "compra_real_minima", "ascender_nivel"):
            self.assertEqual("H", V.gate_esperado(f"accion:{k}", "N2"), k)
        self.assertEqual("S", V.gate_esperado("accion:cerrar_oferta", "N3"))
        self.assertEqual("H", V.gate_esperado("accion:confirmar_validada", "N4"))


if __name__ == "__main__":
    unittest.main()
