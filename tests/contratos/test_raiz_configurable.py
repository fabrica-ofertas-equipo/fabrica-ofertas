"""Raíz configurable (ola 0b-2, CT): los ESQUEMAS son código; los DATOS (empresa/, ofertas/) salen de ``FABRICA_RAIZ`` leída en cada llamada.

Antes: ``RAIZ`` y ``DIR_CONTRATOS`` se fijaban al importar desde ``FABRICA_RAIZ``; con una raíz sin ``contratos/`` ``engine.guard`` salía con 1
(``KeyError: esquema desconocido: infra_estado``) en lugar de fallar cerrado con 4/5. Ahora ``DIR_CONTRATOS`` sale siempre del propio archivo del
validador y ``raiz_datos()`` relee el entorno.

Comando: ``.venv/bin/python -m unittest tests.contratos.test_raiz_configurable``
"""
from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
OFERTA = "OF-202611-01"


def correr(args: list[str], raiz: Path, **env_extra: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FABRICA_", "PREFLIGHT_", "LIMITES_"))}
    env.update({"FABRICA_RAIZ": str(raiz), **env_extra})
    return subprocess.run([sys.executable, *args], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="raiz-sin-contratos-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.assertFalse((self.tmp / "contratos").exists())

    def raiz_con_infra(self, modo: str = "prueba", con_parametros: bool = True) -> None:
        """Raíz temporal SIN ``contratos/`` con un ``empresa/infra/estado.json`` válido, firmado con la clave de prueba y en el modo dado."""
        (self.tmp / "empresa" / "infra").mkdir(parents=True)
        if con_parametros:
            shutil.copy(RAIZ / "empresa" / "parametros.yaml", self.tmp / "empresa" / "parametros.yaml")
        est = V.cargar_json(V.DIR_EJEMPLOS / "infra_estado.valido.json")
        est.update(schema_version="1.1.0", modo=modo)
        est.pop("firma")
        est["firma"] = V.firma_hmac(est, V.CLAVE_DE_PRUEBA)
        (self.tmp / "empresa" / "infra" / "estado.json").write_text(json.dumps(est), encoding="utf-8")


class TestEsquemasSonCodigo(Base):
    def test_dir_contratos_no_depende_de_fabrica_raiz_ni_al_importar(self) -> None:
        r = correr(["-c", "from scripts import validar_esquemas as V; print(V.DIR_CONTRATOS); print(V.DIR_EJEMPLOS); print(V.raiz_datos()); "
                          "print(len(V.errores_de_esquema('infra_estado', {})) > 0)"], self.tmp)
        self.assertEqual(0, r.returncode, r.stderr[-400:])
        contratos, ejemplos, datos, hay_errores = r.stdout.split("\n")[:4]
        self.assertEqual(str(RAIZ / "contratos"), contratos)
        self.assertEqual(str(RAIZ / "contratos" / "ejemplos"), ejemplos)
        self.assertEqual(str(self.tmp), datos)                  # los datos sí siguen a FABRICA_RAIZ
        self.assertEqual("True", hay_errores)                   # esquema cargado: lista de errores, no KeyError

    def test_validador_cargables_con_raiz_sin_contratos(self) -> None:
        r = correr(["-m", "scripts.validar_esquemas", "esquemas"], self.tmp)
        self.assertEqual(0, r.returncode, r.stdout[-400:] + r.stderr[-400:])

    def test_codigo_base_no_cambia_con_la_variable_en_proceso(self) -> None:
        antes = V.DIR_CONTRATOS
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.tmp)}):
            self.assertEqual(antes, V.DIR_CONTRATOS)
            self.assertTrue(V.errores_de_esquema("infra_estado", {}))                                          # el esquema se carga
            self.assertEqual([], V.errores_de_esquema("infra_estado", V.cargar_json(V.DIR_EJEMPLOS / "infra_estado.valido.json")))


class TestDatosSeLeenEnCadaLlamada(Base):
    def test_raiz_datos_y_raiz_siguen_al_entorno_sin_reimportar(self) -> None:
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.tmp)}):
            self.assertEqual(self.tmp, V.raiz_datos())
            self.assertEqual(self.tmp, V.RAIZ)                  # nombre público histórico, ahora dinámico
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(RAIZ)}):
            self.assertEqual(RAIZ, V.raiz_datos())
        env = {k: v for k, v in os.environ.items() if k != "FABRICA_RAIZ"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(RAIZ, V.raiz_datos())              # sin variable: la raíz del código

    def test_import_historico_de_RAIZ_sigue_valiendo(self) -> None:
        from scripts.validar_esquemas import RAIZ as r             # noqa: N811
        self.assertIsInstance(r, Path)
        with self.assertRaises(AttributeError):
            V.NO_EXISTE  # noqa: B018

    def test_cartera_de_empresa_lee_de_la_raiz_actual(self) -> None:
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.tmp)}):
            inf = V.validar_cartera_de_empresa()                 # sin empresa/ en la raíz temporal: errores, no excepciones
            self.assertEqual({"EMPRESA"}, {h.codigo for h in inf.errores})
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(RAIZ)}):
            self.assertEqual([], V.validar_cartera_de_empresa().errores)

    def test_validar_oferta_busca_empresa_en_la_raiz_actual(self) -> None:
        copia = self.tmp / "ofertas" / OFERTA
        shutil.copytree(RAIZ / "ofertas" / "_ejemplo", copia)
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.tmp)}):
            inf = V.validar_oferta(copia, limites=V.limites_de_prueba(), autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"), clave_firma=V.CLAVE_DE_PRUEBA)
        # sin empresa/ en la raíz temporal no hay excepción ni hallazgo espurio; el único aviso es que sin parametros no se verifica el veredicto (CT2-09)
        self.assertEqual(["X14_VEREDICTO"], [h.codigo for h in inf.hallazgos], [str(h) for h in inf.hallazgos])
        self.assertEqual([], inf.errores)

    def test_cli_limites_y_parametros_sin_archivo_fallan_cerrado_con_5(self) -> None:
        for args in (["limites"], ["parametros", "--operacion", "runner_vivo"]):
            r = correr(["-m", "scripts.validar_esquemas", *args], self.tmp)
            self.assertEqual(5, r.returncode, (args, r.stdout[-300:], r.stderr[-300:]))
            self.assertNotIn("Traceback", r.stderr)

    def test_cli_oferta_ausente_en_la_raiz_no_revienta(self) -> None:
        r = correr(["-m", "scripts.validar_esquemas", "oferta", "ofertas/_ejemplo"], self.tmp)
        self.assertEqual(3, r.returncode)
        self.assertNotIn("Traceback", r.stderr)


class TestGuardConRaizSinContratos(Base):
    """``engine.guard`` con una raíz de datos sin ``contratos/``: falla CERRADO con 4 o 5, nunca con 1 (KeyError)."""

    ARGS = ["-m", "engine.guard", "comprobar", "--operacion", "gastar", "--oferta", OFERTA, "--monto", "100", "--moneda", "EUR", "--json"]

    def codigo_y_paso(self, r: subprocess.CompletedProcess) -> tuple[int, str | None]:
        self.assertNotIn("Traceback", r.stderr, r.stderr[-500:])
        self.assertNotIn("KeyError", r.stderr)
        return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])["datos"]["paso"]

    def test_produccion_sin_estado_de_infra_sale_con_4(self) -> None:
        r = correr(self.ARGS, self.tmp, FABRICA_ENTORNO="produccion")
        self.assertEqual((4, "infra"), self.codigo_y_paso(r))

    def test_produccion_con_estado_que_no_cumple_el_esquema_sale_con_4_y_no_con_1(self) -> None:
        (self.tmp / "empresa" / "infra").mkdir(parents=True)
        (self.tmp / "empresa" / "infra" / "estado.json").write_text('{"x": 1}', encoding="utf-8")
        r = correr(self.ARGS, self.tmp, FABRICA_ENTORNO="produccion", PREFLIGHT_HMAC_KEY="clave-de-prueba-no-real")
        self.assertEqual((4, "infra"), self.codigo_y_paso(r))      # antes: KeyError «esquema desconocido: infra_estado» ⇒ exit 1

    def test_sin_limites_sale_con_5_en_el_paso_de_limites(self) -> None:
        self.raiz_con_infra(modo="prueba")
        r = correr([*self.ARGS, "--modo", "fixture", "--ahora", "2026-11-09T07:00:00Z"], self.tmp, FABRICA_ENTORNO="prueba",
                   PREFLIGHT_HMAC_KEY=V.CLAVE_DE_PRUEBA.decode())
        self.assertEqual((5, "limites"), self.codigo_y_paso(r))

    def test_sin_parametros_el_paso_de_infra_falla_cerrado_con_4(self) -> None:
        self.raiz_con_infra(modo="prueba", con_parametros=False)
        r = correr([*self.ARGS, "--modo", "fixture", "--ahora", "2026-11-09T07:00:00Z"], self.tmp, FABRICA_ENTORNO="prueba",
                   PREFLIGHT_HMAC_KEY=V.CLAVE_DE_PRUEBA.decode())
        self.assertEqual((4, "infra"), self.codigo_y_paso(r))


class TestFirmasPublicasIntactas(unittest.TestCase):
    def test_nombres_y_parametros_que_otros_importan(self) -> None:
        esperado = {
            "hash_objeto": ["obj", "excluir"], "hash_archivo": ["ruta"], "hash_bytes": ["datos"], "json_canonico": ["obj"], "firma_hmac": ["contenido", "clave"],
            "comparar_hash": ["a", "b"], "clave_idempotencia": ["operacion", "oferta_id", "parametros"], "evaluar_limites": ["limites", "operacion"],
            "infra_verde": ["estado", "ahora", "max_horas"], "payload_firma": ["nombre", "d"], "problemas_firma": ["firma", "payload", "clave"],
            "problemas_artefacto": ["nombre", "d"], "errores_de_esquema": ["nombre", "instancia"], "validar_oferta": ["dir_oferta", "limites", "parametros"],
            "cargar_esquemas": ["dir_contratos"], "buscar_floats": ["obj", "ruta"], "sello_de_limites": ["limites"],
        }
        for nombre, params in esperado.items():
            f = getattr(V, nombre)
            reales = list(inspect.signature(f).parameters)
            self.assertEqual(params, reales[: len(params)], nombre)
        for const in ("DIR_CONTRATOS", "DIR_EJEMPLOS", "RAIZ", "CLAVES_CRITICAS", "CLAVE_DE_PRUEBA", "EXPONENTE_ISO4217", "MONEDAS_META_OFFSET_1",
                      "ACCIONES_GATE_MINIMAS", "TARIFAS_LLC_US_SUPUESTO"):
            self.assertTrue(hasattr(V, const), const)


if __name__ == "__main__":
    unittest.main()
