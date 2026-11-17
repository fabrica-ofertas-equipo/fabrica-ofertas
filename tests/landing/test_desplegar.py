"""Pruebas de ``landing.desplegar``: dry-run por defecto, publicación en ``preview``/``produccion`` y rollback.

Comando: ``.venv/bin/python -m unittest tests.landing.test_desplegar``
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import comun
from engine.errores import ErrorBloqueado, ErrorValidacion
from landing import desplegar as D
from landing import generar as G

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "tests" / "fixtures" / "landing" / "oferta_minima"


def _sello_valido(d: Path, raiz: Path, hash_sitio: str) -> Path:
    sello = {
        "schema_version": "1.0.0", "oferta_id": "OF-209901-01", "etapa_objetivo": "D5",
        "artefacto_sha256": hash_sitio, "reglas_version": "v1",
        "emitido_en": "2026-11-06T00:00:00Z", "vigencia_hasta": "2099-01-01T00:00:00Z",
        "object_ids": [], "dictamen_ref": "qa/x1-d5-v1.json", "dictamen_sha256": "sha256:" + "0" * 64,
    }
    sello["firma"] = comun.firma_hmac(sello, b"clave-de-prueba-sello-no-real")
    ruta = raiz / "empresa" / "compliance" / "sellos" / f"{hash_sitio.split(':')[1]}.json"
    comun.escribir_atomico(ruta, comun.json_canonico(sello))
    return ruta


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="landing-desplegar-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = self.tmp / "ofertas" / "OF-209901-01"
        shutil.copytree(FIXTURE, self.d)
        G.generar_sitio(self.d)
        self.hash_sitio = comun.hash_directorio(self.d / "05-landing" / "sitio")


class TestDryRun(Base):
    def test_dry_run_no_escribe_nada(self) -> None:
        antes = comun.hash_directorio(self.d / "05-landing" / "sitio")
        plan = D.desplegar(self.d, entorno="preview", tag="t1", live=False, raiz=self.tmp)
        self.assertEqual("dry_run", plan["modo"])
        self.assertEqual(self.hash_sitio, plan["hash_sitio"])
        self.assertFalse((self.d / "05-landing" / "_despliegues").exists())
        self.assertEqual(antes, comun.hash_directorio(self.d / "05-landing" / "sitio"))


class TestPreview(Base):
    def test_live_preview_crea_historial(self) -> None:
        plan = D.desplegar(self.d, entorno="preview", tag="t1", live=True, raiz=self.tmp)
        self.assertEqual("live", plan["modo"])
        self.assertTrue((self.d / "05-landing" / "_despliegues" / "t1").is_dir())
        historial = comun.leer_jsonl(self.d / "05-landing" / "_despliegues" / "historial.jsonl")
        self.assertEqual(1, len(historial))
        self.assertEqual("t1", historial[0]["tag"])

    def test_tag_repetido_falla(self) -> None:
        D.desplegar(self.d, entorno="preview", tag="t1", live=True, raiz=self.tmp)
        with self.assertRaises(ErrorValidacion):
            D.desplegar(self.d, entorno="preview", tag="t1", live=True, raiz=self.tmp)


class TestProduccion(Base):
    def test_sin_fabrica_entorno_produccion_bloquea(self) -> None:
        with mock.patch.dict("os.environ", {"FABRICA_ENTORNO": "desarrollo"}):
            with self.assertRaises(ErrorBloqueado):
                D.desplegar(self.d, entorno="produccion", tag="t1", live=True, raiz=self.tmp,
                           env={"FABRICA_ENTORNO": "desarrollo"})

    def test_produccion_sin_sello_bloquea(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            D.desplegar(self.d, entorno="produccion", tag="t1", live=True, raiz=self.tmp,
                       env={"FABRICA_ENTORNO": "produccion"})

    def test_produccion_con_pausa_bloquea(self) -> None:
        comun.escribir_atomico(self.tmp / "empresa" / "PAUSA", b"")
        _sello_valido(self.d, self.tmp, self.hash_sitio)
        with self.assertRaises(ErrorBloqueado):
            D.desplegar(self.d, entorno="produccion", tag="t1", live=True, raiz=self.tmp,
                       env={"FABRICA_ENTORNO": "produccion"})

    def test_produccion_con_sello_vigente_publica(self) -> None:
        _sello_valido(self.d, self.tmp, self.hash_sitio)
        plan = D.desplegar(self.d, entorno="produccion", tag="t1", live=True, raiz=self.tmp,
                           env={"FABRICA_ENTORNO": "produccion"})
        self.assertEqual("live", plan["modo"])

    def test_sello_con_otro_hash_no_sirve(self) -> None:
        _sello_valido(self.d, self.tmp, "sha256:" + "1" * 64)
        with self.assertRaises(ErrorBloqueado):
            D.desplegar(self.d, entorno="produccion", tag="t1", live=True, raiz=self.tmp,
                       env={"FABRICA_ENTORNO": "produccion"})


class TestRollback(Base):
    def test_rollback_restaura_el_sitio(self) -> None:
        D.desplegar(self.d, entorno="preview", tag="v1", live=True, raiz=self.tmp)
        (self.d / "05-landing" / "sitio" / "index.html").write_text("<html></html>", encoding="utf-8")
        self.assertNotEqual(self.hash_sitio, comun.hash_directorio(self.d / "05-landing" / "sitio"))

        plan_dry = D.rollback(self.d, tag="v1", entorno="preview", live=False)
        self.assertEqual("dry_run", plan_dry["modo"])
        self.assertNotEqual(self.hash_sitio, comun.hash_directorio(self.d / "05-landing" / "sitio"))  # dry-run no toca nada

        D.rollback(self.d, tag="v1", entorno="preview", live=True)
        self.assertEqual(self.hash_sitio, comun.hash_directorio(self.d / "05-landing" / "sitio"))

    def test_rollback_a_tag_inexistente_falla(self) -> None:
        with self.assertRaises(ErrorValidacion):
            D.rollback(self.d, tag="no-existe", entorno="preview", live=True)

    def test_rollback_detecta_historial_alterado(self) -> None:
        D.desplegar(self.d, entorno="preview", tag="v1", live=True, raiz=self.tmp)
        (self.d / "05-landing" / "_despliegues" / "v1" / "index.html").write_text("manipulado", encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            D.rollback(self.d, tag="v1", entorno="preview", live=True)


if __name__ == "__main__":
    unittest.main()
