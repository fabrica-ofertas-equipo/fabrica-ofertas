"""Pruebas de ``infra.preflight``: catálogo, sondas fail-closed, agregación del semáforo y CLI."""
from __future__ import annotations

import contextlib
import io
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion
from engine.transporte import TransporteFixture
from infra import preflight
from tests.infra.apoyo import CLAVE_PREFLIGHT_PRUEBA, RAIZ_REPO, PruebaBase, copiar_empresa_prueba

AHORA = datetime(2026, 11, 9, 6, 0, 0, tzinfo=timezone.utc)


class PruebaCatalogo(PruebaBase):
    def test_el_catalogo_normativo_tiene_44_items_unicos_con_r06(self) -> None:
        catalogo = preflight.cargar_catalogo()
        ids = [i.id for i in catalogo]
        self.assertEqual(len(ids), len(set(ids)), "ids repetidos en el catálogo")
        self.assertEqual(len(catalogo), 44)
        r06 = next(i for i in catalogo if i.id == "R-06")
        self.assertTrue(r06.critico)
        self.assertFalse(r06.ligero)

    def test_catalogo_vacio_es_invalido(self) -> None:
        ruta = self.tmp / "vacio.yaml"
        ruta.write_text("version: 1\nitems: []\n", encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            preflight.cargar_catalogo(ruta)

    def test_catalogo_con_id_repetido_es_invalido(self) -> None:
        ruta = self.tmp / "dup.yaml"
        ruta.write_text("items:\n  - {id: X-01, critico: true}\n  - {id: X-01, critico: false}\n", encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            preflight.cargar_catalogo(ruta)


class PruebaSondaNoEjecutable(PruebaBase):
    def test_item_critico_sin_sonda_es_rojo(self) -> None:
        item = preflight.ItemCatalogo(id="Z-01", bloque="x", critico=True, ligero=False, comprueba="")
        r = preflight._no_ejecutable(item)  # type: ignore[attr-defined]
        self.assertEqual(r.estado, "ROJO")

    def test_item_no_critico_sin_sonda_es_amarillo_nunca_verde(self) -> None:
        item = preflight.ItemCatalogo(id="Z-02", bloque="x", critico=False, ligero=False, comprueba="")
        r = preflight._no_ejecutable(item)  # type: ignore[attr-defined]
        self.assertEqual(r.estado, "AMARILLO")


class PruebaSondaK01Pausa(PruebaBase):
    def test_sin_pausa_es_verde(self) -> None:
        (self.tmp / "empresa").mkdir()
        r = preflight.sonda_k01_pausa(self.tmp)
        self.assertEqual(r.estado, "VERDE")

    def test_con_pausa_es_rojo(self) -> None:
        empresa = self.tmp / "empresa"
        empresa.mkdir()
        (empresa / "PAUSA").touch()
        r = preflight.sonda_k01_pausa(self.tmp)
        self.assertEqual(r.estado, "ROJO")


class PruebaSondaP01Limites(PruebaBase):
    def test_limites_completos_y_sellados_es_verde(self) -> None:
        copiar_empresa_prueba(self.tmp)
        r = preflight.sonda_p01_limites(self.tmp, env={})
        self.assertEqual(r.estado, "VERDE")

    def test_limites_en_null_es_rojo_fail_closed(self) -> None:
        (self.tmp / "empresa").mkdir()
        (self.tmp / "empresa" / "limites.yaml").write_bytes((RAIZ_REPO / "empresa" / "limites.yaml").read_bytes())
        r = preflight.sonda_p01_limites(self.tmp, env={})
        self.assertEqual(r.estado, "ROJO")

    def test_sin_archivo_de_limites_es_rojo(self) -> None:
        (self.tmp / "empresa").mkdir()
        r = preflight.sonda_p01_limites(self.tmp, env={})
        self.assertEqual(r.estado, "ROJO")


class PruebaSondaR06Centinela(PruebaBase):
    def test_primera_corrida_es_pendiente_externo_nunca_verde(self) -> None:
        r = preflight.sonda_centinela_r06(self.tmp, ahora=lambda: AHORA)
        self.assertEqual(r.estado, "PENDIENTE_EXTERNO")

    def test_corrida_inmediata_repetida_es_amarillo(self) -> None:
        preflight.sonda_centinela_r06(self.tmp, ahora=lambda: AHORA)
        r = preflight.sonda_centinela_r06(self.tmp, ahora=lambda: AHORA)
        self.assertEqual(r.estado, "AMARILLO")

    def test_corrida_bastante_despues_es_verde(self) -> None:
        preflight.sonda_centinela_r06(self.tmp, ahora=lambda: AHORA)
        despues = AHORA + timedelta(hours=1)
        r = preflight.sonda_centinela_r06(self.tmp, ahora=lambda: despues)
        self.assertEqual(r.estado, "VERDE")

    def test_centinela_alterado_es_rojo(self) -> None:
        preflight.sonda_centinela_r06(self.tmp, ahora=lambda: AHORA)
        ruta = self.tmp.joinpath("empresa", "infra", "centinela_persistencia.json")
        ruta.write_text("esto no es json", encoding="utf-8")
        r = preflight.sonda_centinela_r06(self.tmp, ahora=lambda: AHORA + timedelta(hours=1))
        self.assertEqual(r.estado, "ROJO")


class PruebaSondaC09Watchdog(PruebaBase):
    def test_visto_reciente_es_verde(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": "https://watchdog.ejemplo/estado", "cuerpo": {"visto_hace_min": 3}}])
        r = preflight.sonda_c09_watchdog(t, "https://watchdog.ejemplo")
        self.assertEqual(r.estado, "VERDE")

    def test_visto_hace_mas_de_10_min_es_rojo(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": "https://watchdog.ejemplo/estado", "cuerpo": {"visto_hace_min": 11}}])
        r = preflight.sonda_c09_watchdog(t, "https://watchdog.ejemplo")
        self.assertEqual(r.estado, "ROJO")

    def test_503_por_variables_obligatorias_ausentes_es_rojo(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url": "https://watchdog.ejemplo/estado", "estado": 503}])
        r = preflight.sonda_c09_watchdog(t, "https://watchdog.ejemplo")
        self.assertEqual(r.estado, "ROJO")
        self.assertIn("GASTO_DIARIO_MAX_MINOR", r.mensaje + " " + str(r.evidencia))

    def test_sin_respuesta_grabada_es_rojo_no_excepcion(self) -> None:
        t = TransporteFixture([])
        r = preflight.sonda_c09_watchdog(t, "https://watchdog.ejemplo")
        self.assertEqual(r.estado, "ROJO")


class PruebaSemaforoGlobal(PruebaBase):
    def test_critico_rojo_fuerza_rojo_global(self) -> None:
        items = [{"critico": True, "estado": "ROJO"}, {"critico": True, "estado": "VERDE"}]
        self.assertEqual(preflight.semaforo_global(items), "ROJO")

    def test_no_critico_rojo_es_solo_amarillo(self) -> None:
        items = [{"critico": False, "estado": "ROJO"}, {"critico": True, "estado": "VERDE"}]
        self.assertEqual(preflight.semaforo_global(items), "AMARILLO")

    def test_todo_verde_es_verde(self) -> None:
        items = [{"critico": True, "estado": "VERDE"}, {"critico": False, "estado": "VERDE"}]
        self.assertEqual(preflight.semaforo_global(items), "VERDE")

    def test_pendiente_externo_no_es_verde(self) -> None:
        items = [{"critico": True, "estado": "VERDE"}, {"critico": True, "estado": "PENDIENTE_EXTERNO"}]
        self.assertEqual(preflight.semaforo_global(items), "AMARILLO")


class PruebaConstruirYEscribirEstado(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        copiar_empresa_prueba(self.tmp)

    def test_estado_cumple_el_esquema_y_queda_firmado(self) -> None:
        sondas = {"K-01": lambda: preflight.ResultadoSonda("VERDE", "ok"), "P-01": lambda: preflight.sonda_p01_limites(self.tmp, env={})}
        estado = preflight.ejecutar("completo", raiz=self.tmp, env={"PREFLIGHT_HMAC_KEY": CLAVE_PREFLIGHT_PRUEBA.decode()}, sondas=sondas, ahora=lambda: AHORA)
        sin_firma = {k: v for k, v in estado.items() if k != "firma"}
        errores = comun.errores_de_esquema("infra_estado", estado)
        self.assertEqual(errores, [], msg=str(errores[:3]))
        self.assertTrue(comun.comparar_hash(estado["firma"], comun.firma_hmac(sin_firma, CLAVE_PREFLIGHT_PRUEBA)))
        self.assertTrue(preflight.ruta_estado(self.tmp).is_file())

    def test_item_critico_rojo_produce_semaforo_rojo_y_no_verde_por_omision(self) -> None:
        # Sin inyectar NINGUNA sonda: todos los críticos sin implementación propia dan ROJO (fail-closed).
        estado = preflight.ejecutar("completo", raiz=self.tmp, env={"PREFLIGHT_HMAC_KEY": CLAVE_PREFLIGHT_PRUEBA.decode()}, ahora=lambda: AHORA)
        self.assertEqual(estado["semaforo"], "ROJO")

    def test_falta_la_clave_de_firma_es_erroruso(self) -> None:
        with self.assertRaises(ErrorUso):
            preflight.ejecutar("completo", raiz=self.tmp, env={}, ahora=lambda: AHORA)

    def test_modo_ligero_conserva_los_items_no_ligeros_del_anterior(self) -> None:
        env = {"PREFLIGHT_HMAC_KEY": CLAVE_PREFLIGHT_PRUEBA.decode()}
        sondas_completo = {"K-01": lambda: preflight.ResultadoSonda("VERDE", "ok"), "P-01": lambda: preflight.sonda_p01_limites(self.tmp, env={})}
        preflight.ejecutar("completo", raiz=self.tmp, env=env, sondas=sondas_completo, ahora=lambda: AHORA)
        despues = AHORA + timedelta(hours=1)
        estado_ligero = preflight.ejecutar("ligero", raiz=self.tmp, env=env, sondas={}, ahora=lambda: despues)
        por_id = {i["id"]: i for i in estado_ligero["items"]}
        # M-04 no es ligero: debe conservar lo medido en la corrida "completo" anterior, sin extender su vigencia.
        self.assertEqual(por_id["M-04"]["medido_en"], comun.iso_z(AHORA))


class PruebaCLI(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        copiar_empresa_prueba(self.tmp)

    def _correr(self, *args: str, env: dict) -> tuple[int, str]:
        salida = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = preflight.main(list(args))
        return codigo, salida.getvalue()

    def test_todo_rojo_por_falta_de_sondas_sale_4(self) -> None:
        env = {"FABRICA_ENTORNO": "desarrollo", "FABRICA_RAIZ": str(self.tmp), "PREFLIGHT_HMAC_KEY": CLAVE_PREFLIGHT_PRUEBA.decode()}
        codigo, salida = self._correr("ejecutar", "--modo", "completo", "--ahora", "2026-11-09T06:00:00Z", "--json", env=env)
        self.assertEqual(codigo, 4)
        datos = json.loads(salida)
        self.assertEqual(datos["codigo"], 4)
        self.assertFalse(datos["ok"])

    def test_sin_clave_de_firma_sale_2(self) -> None:
        env = {"FABRICA_ENTORNO": "desarrollo", "FABRICA_RAIZ": str(self.tmp)}
        codigo, _ = self._correr("ejecutar", "--modo", "completo", "--ahora", "2026-11-09T06:00:00Z", env=env)
        self.assertEqual(codigo, 2)

    def test_modo_invalido_sale_2_por_argparse(self) -> None:
        env = {"FABRICA_ENTORNO": "desarrollo", "FABRICA_RAIZ": str(self.tmp), "PREFLIGHT_HMAC_KEY": CLAVE_PREFLIGHT_PRUEBA.decode()}
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(io.StringIO()):
            codigo = preflight.main(["ejecutar", "--modo", "no-existe"])
        self.assertEqual(codigo, 2)


if __name__ == "__main__":
    import unittest

    unittest.main()
