"""Pruebas de ``scripts.creativos.preflight_d6`` (paso 1 de D6: tabla VERDE/ROJO/NO_DISPONIBLE).

Reutiliza (solo lectura) ``tests.engine.apoyo.crear_empresa``/``PruebaBase`` para una raíz ``empresa/``
ya verde y firmada, igual que ``tests/engine/test_guard.py``. Cada prueba de esta clase parte de un
estado VERDE y rompe UNA cosa a la vez (una prueba roja sembrada por cada comprobación del preflight).
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from scripts.creativos import preflight_d6
from tests.scripts.test_creativos_comun import PruebaBase, crear_empresa, crear_oferta_creativos

OFERTA = "OF-202611-01"


def _item(reporte: dict, item_id: str) -> dict:
    for i in reporte["items"]:
        if i["id"] == item_id:
            return i
    raise AssertionError(f"ítem no encontrado: {item_id}")


def _sello_siempre_vigente(clave_sello, ahora, *, raiz=None, env=None):
    return {"artefacto_sha256": clave_sello, "vigencia_hasta": "2099-01-01T00:00:00Z"}


def _sello_nunca_vigente(clave_sello, ahora, *, raiz=None, env=None):
    return None


class BasePreflight(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, entorno="prueba", modo_infra="prueba")
        self.dir_oferta = crear_oferta_creativos(self.emp, oferta_id=OFERTA)

    def comprobar(self, **kw):
        kw.setdefault("env", self.emp.env)
        kw.setdefault("ahora", self.emp.reloj)
        kw.setdefault("verificador_sello", _sello_siempre_vigente)
        return preflight_d6.comprobar(self.emp.raiz, OFERTA, **kw)


class PruebaCaminoFeliz(BasePreflight):
    def test_todo_verde_con_sello_inyectado_y_navegador_fuentes_landing_declarados(self) -> None:
        binario = self.tmp / "chrome-falso"
        binario.write_text("#!/bin/sh\n", encoding="utf-8")
        binario.chmod(binario.stat().st_mode | stat.S_IXUSR)
        fuente = self.tmp / "fuente.ttf"
        fuente.write_text("x", encoding="utf-8")
        reporte = self.comprobar(url_landing="https://ejemplo.invalido/", cliente_get=lambda url: 200,
                                 rutas_navegador=[binario], rutas_fuentes=[fuente])
        self.assertEqual(reporte["semaforo"], "VERDE")
        for item in reporte["items"]:
            self.assertEqual(item["estado"], "VERDE", item)

    def test_sin_url_ni_navegador_ni_fuentes_queda_rojo_por_no_disponible(self) -> None:
        # "nunca verde sin comprobar": aunque PAUSA, infra, límites, locale, entradas y sello estén
        # OK, faltar el cliente HTTP, el navegador o las fuentes basta para que el semáforo NO sea VERDE.
        reporte = self.comprobar()
        self.assertEqual(reporte["semaforo"], "ROJO")

    def test_sin_sello_inyectado_el_defecto_no_encuentra_ninguno_y_es_rojo(self) -> None:
        reporte = preflight_d6.comprobar(self.emp.raiz, OFERTA, env=self.emp.env, ahora=self.emp.reloj)
        self.assertEqual(_item(reporte, "sello_landing_vigente")["estado"], "ROJO")
        self.assertEqual(reporte["semaforo"], "ROJO")


class PruebaGuardCompartido(BasePreflight):
    """Los ítems que delega en ``engine.guard.comprobar_live`` (PAUSA, infra, límites)."""

    def test_pausa_bloquea(self) -> None:
        (self.emp.raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "sin_pausa")["estado"], "ROJO")
        self.assertEqual(_item(reporte, "infra_verde")["estado"], "NO_DISPONIBLE")
        self.assertEqual(reporte["semaforo"], "ROJO")

    def test_infra_con_modo_incorrecto_para_simulacion_bloquea(self) -> None:
        self.emp.reescribir_estado(modo="vivo")  # simulación exige modo en {prueba, simulado}
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "infra_verde")["estado"], "ROJO")
        self.assertEqual(_item(reporte, "limites_generar_creativos")["estado"], "NO_DISPONIBLE")

    def test_infra_vencida_bloquea(self) -> None:
        self.emp.reescribir_estado(valido_hasta="2026-11-09T06:05:00Z")  # ya pasó respecto del reloj (07:00)
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "infra_verde")["estado"], "ROJO")

    def test_falta_un_tope_de_la_operacion_bloquea_en_limites(self) -> None:
        self.emp.reescribir_limites(lambda lim: lim.__setitem__("creditos_max_pieza", None))
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "limites_generar_creativos")["estado"], "ROJO")
        self.assertEqual(reporte["semaforo"], "ROJO")

    def test_entorno_desconocido_bloquea_todo_el_bloque_de_guard(self) -> None:
        env = {**self.emp.env, "FABRICA_ENTORNO": "no-existe"}
        reporte = preflight_d6.comprobar(self.emp.raiz, OFERTA, env=env, ahora=self.emp.reloj, verificador_sello=_sello_siempre_vigente)
        self.assertEqual(_item(reporte, "entorno_valido")["estado"], "ROJO")


class PruebaLocale(BasePreflight):
    def test_locale_no_permitido_bloquea(self) -> None:
        crear_oferta_creativos(self.emp, oferta_id=OFERTA, locale="it-IT")
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "locale_permitido")["estado"], "ROJO")

    def test_sin_mercado_json_bloquea(self) -> None:
        (self.dir_oferta / "mercado.json").unlink()
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "locale_permitido")["estado"], "ROJO")

    def test_locale_permitido_es_verde(self) -> None:
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "locale_permitido")["estado"], "VERDE")


class PruebaEntradasYSello(BasePreflight):
    def test_sin_oferta_json_bloquea(self) -> None:
        (self.dir_oferta / "03-oferta" / "oferta.json").unlink()
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "entradas_oferta_valida")["estado"], "ROJO")

    def test_oferta_json_invalida_contra_el_esquema_bloquea(self) -> None:
        (self.dir_oferta / "03-oferta" / "oferta.json").write_text("{}", encoding="utf-8")
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "entradas_oferta_valida")["estado"], "ROJO")

    def test_sin_sitio_landing_bloquea_el_sello(self) -> None:
        import shutil

        shutil.rmtree(self.dir_oferta / "05-landing")
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "sello_landing_vigente")["estado"], "ROJO")

    def test_sello_vencido_o_ausente_bloquea(self) -> None:
        reporte = preflight_d6.comprobar(self.emp.raiz, OFERTA, env=self.emp.env, ahora=self.emp.reloj, verificador_sello=_sello_nunca_vigente)
        self.assertEqual(_item(reporte, "sello_landing_vigente")["estado"], "ROJO")


class PruebaLandingYHerramientas(BasePreflight):
    def test_sin_url_landing_es_no_disponible(self) -> None:
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "landing_responde_200")["estado"], "NO_DISPONIBLE")

    def test_con_cliente_que_devuelve_200_es_verde(self) -> None:
        reporte = self.comprobar(url_landing="https://ejemplo.invalido/", cliente_get=lambda url: 200)
        self.assertEqual(_item(reporte, "landing_responde_200")["estado"], "VERDE")

    def test_con_cliente_que_devuelve_500_es_rojo(self) -> None:
        reporte = self.comprobar(url_landing="https://ejemplo.invalido/", cliente_get=lambda url: 500)
        self.assertEqual(_item(reporte, "landing_responde_200")["estado"], "ROJO")

    def test_cliente_que_lanza_es_rojo_no_verde_falso(self) -> None:
        def _falla(url):
            raise RuntimeError("sin red")

        reporte = self.comprobar(url_landing="https://ejemplo.invalido/", cliente_get=_falla)
        self.assertEqual(_item(reporte, "landing_responde_200")["estado"], "ROJO")

    def test_sin_rutas_de_navegador_es_no_disponible(self) -> None:
        reporte = self.comprobar()
        self.assertEqual(_item(reporte, "navegador_sin_interfaz")["estado"], "NO_DISPONIBLE")
        self.assertEqual(_item(reporte, "fuentes_disponibles")["estado"], "NO_DISPONIBLE")

    def test_navegador_ejecutable_es_verde(self) -> None:
        binario = self.tmp / "chrome-falso"
        binario.write_text("#!/bin/sh\n", encoding="utf-8")
        binario.chmod(binario.stat().st_mode | stat.S_IXUSR)
        reporte = self.comprobar(rutas_navegador=[binario])
        self.assertEqual(_item(reporte, "navegador_sin_interfaz")["estado"], "VERDE")

    def test_navegador_no_ejecutable_es_rojo(self) -> None:
        archivo = self.tmp / "no-ejecutable"
        archivo.write_text("x", encoding="utf-8")
        reporte = self.comprobar(rutas_navegador=[archivo])
        self.assertEqual(_item(reporte, "navegador_sin_interfaz")["estado"], "ROJO")

    def test_fuentes_presentes_son_verde_y_faltantes_rojo(self) -> None:
        fuente = self.tmp / "fuente.ttf"
        fuente.write_text("x", encoding="utf-8")
        self.assertEqual(_item(self.comprobar(rutas_fuentes=[fuente]), "fuentes_disponibles")["estado"], "VERDE")
        self.assertEqual(_item(self.comprobar(rutas_fuentes=[self.tmp / "no-existe.ttf"]), "fuentes_disponibles")["estado"], "ROJO")


class PruebaCLI(BasePreflight):
    def test_cli_sale_cero_cuando_todo_es_verde(self) -> None:
        import contextlib
        import io
        from unittest import mock

        binario = self.tmp / "chrome-falso"
        binario.write_text("#!/bin/sh\n", encoding="utf-8")
        binario.chmod(binario.stat().st_mode | stat.S_IXUSR)
        fuente = self.tmp / "fuente.ttf"
        fuente.write_text("x", encoding="utf-8")

        # El CLI usa el verificador REAL (compliance.verificar.verificar_sello); sin fabricar un
        # sello firmado por X1 esta corrida sale bloqueada (4) y el ítem sello_landing_vigente en
        # ROJO: el comportamiento correcto sin X1 de por medio (nunca verde sin comprobar).
        argv = ["--oferta", OFERTA, "--raiz", str(self.emp.raiz), "--ahora", "2026-11-09T07:00:00Z",
                "--navegador", str(binario), "--fuente", str(fuente), "--json"]
        with mock.patch.dict(os.environ, self.emp.env, clear=False):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                codigo = preflight_d6.main(argv)
        self.assertEqual(codigo, 4)  # bloqueado: sin sello real de X1 (ver arriba)
        import json as _json

        datos = _json.loads(buf.getvalue().splitlines()[0])
        self.assertEqual(datos["codigo"], 4)
        self.assertEqual(datos["datos"]["semaforo"], "ROJO")


if __name__ == "__main__":
    import unittest

    unittest.main()
