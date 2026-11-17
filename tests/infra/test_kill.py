"""Pruebas de ``infra.kill``: capa 1 (archivo), mejor esfuerzo en capa 2/3, dry-run por defecto y CLI."""
from __future__ import annotations

import contextlib
import io
import json
import os
from datetime import datetime, timezone
from unittest import mock

from engine import comun
from engine.errores import ErrorExterno, ErrorUso
from engine.transporte import TransporteFixture
from infra import kill
from tests.infra.apoyo import PruebaBase

AHORA = datetime(2026, 11, 9, 8, 0, 0, tzinfo=timezone.utc)


class AlmacenFalso:
    def __init__(self, *, falla: bool = False) -> None:
        self.marcada = False
        self._falla = falla

    def marcar_pausa(self, motivo: str) -> None:
        if self._falla:
            raise ErrorExterno("almacén caído (simulado)")
        self.marcada = True

    def pausa_activa(self) -> bool:
        return self.marcada


class EjecutorFalso:
    def __init__(self, *, campanas: list[dict] | None = None) -> None:
        self.llamado_con: str | None = None
        self._campanas = campanas if campanas is not None else [{"campaign_id": "c1", "estado": "PAUSED"}]

    def pausar_todas(self, motivo: str):
        self.llamado_con = motivo
        return self._campanas


class PruebaDryRun(PruebaBase):
    def test_sin_live_no_escribe_nada(self) -> None:
        antes = (self.tmp / "empresa").mkdir() or comun.hash_directorio(self.tmp)
        resultado = kill.activar("prueba", raiz=self.tmp, env={}, live=False, ahora=lambda: AHORA)
        self.assertEqual(resultado.modo, "dry_run")
        self.assertFalse(kill.ruta_pausa(self.tmp).is_file())
        self.assertEqual(comun.hash_directorio(self.tmp), antes)

    def test_motivo_vacio_es_erroruso(self) -> None:
        with self.assertRaises(ErrorUso):
            kill.activar("   ", raiz=self.tmp, env={}, live=False)


class PruebaLive(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "empresa").mkdir()

    def test_live_escribe_el_archivo_siempre(self) -> None:
        resultado = kill.activar("A-1", raiz=self.tmp, env={}, live=True, ahora=lambda: AHORA)
        self.assertTrue(kill.ruta_pausa(self.tmp).is_file())
        capa = next(c for c in resultado.capas if c.nombre == "archivo")
        self.assertTrue(capa.ok)

    def test_almacen_y_watchdog_caidos_no_impiden_el_archivo(self) -> None:
        almacen = AlmacenFalso(falla=True)
        t = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://watchdog.ejemplo", "error": "red"}])
        resultado = kill.activar("A-10", raiz=self.tmp, env={"LATIDO_HMAC": "clave"}, live=True, almacen=almacen,
                                 transporte=t, url_watchdog="https://watchdog.ejemplo", ahora=lambda: AHORA)
        self.assertTrue(kill.ruta_pausa(self.tmp).is_file())
        self.assertFalse(resultado.ok)  # no las tres capas confirmadas
        self.assertTrue(resultado.archivo_ok)
        self.assertEqual({c.nombre: c.ok for c in resultado.capas}["almacen"], False)
        self.assertEqual({c.nombre: c.ok for c in resultado.capas}["watchdog"], False)

    def test_las_tres_capas_mas_meta_confirman_si_todo_responde(self) -> None:
        almacen = AlmacenFalso()
        ejecutor = EjecutorFalso()
        t = TransporteFixture([{"metodo": "POST", "url_prefijo": "https://watchdog.ejemplo", "estado": 200, "cuerpo": {"ok": True}}])
        resultado = kill.activar("A-5", raiz=self.tmp, env={"LATIDO_HMAC": "clave"}, live=True, almacen=almacen, ejecutor=ejecutor,
                                 transporte=t, url_watchdog="https://watchdog.ejemplo", ahora=lambda: AHORA)
        self.assertTrue(resultado.ok)
        self.assertEqual(ejecutor.llamado_con, "A-5")

    def test_sin_ejecutor_la_capa_meta_queda_pendiente(self) -> None:
        resultado = kill.activar("A-1", raiz=self.tmp, env={}, live=True, ahora=lambda: AHORA)
        capa = next(c for c in resultado.capas if c.nombre == "campanas_meta")
        self.assertFalse(capa.intentado)
        self.assertFalse(resultado.ok)


class PruebaVerificar(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "empresa").mkdir()

    def test_sin_nada_es_coherente_sin_pausa(self) -> None:
        datos = kill.verificar(raiz=self.tmp)
        self.assertTrue(datos["coherente"])
        self.assertFalse(datos["archivo"])

    def test_archivo_presente_sin_almacen_es_incoherente(self) -> None:
        kill.activar("A-1", raiz=self.tmp, env={}, live=True, ahora=lambda: AHORA)
        almacen = AlmacenFalso()  # nunca se marcó: pausa_activa() == False
        datos = kill.verificar(raiz=self.tmp, almacen=almacen)
        self.assertFalse(datos["coherente"])


class PruebaCLI(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "empresa").mkdir()

    def _correr(self, *args: str, env: dict) -> tuple[int, str]:
        salida = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = kill.main(list(args))
        return codigo, salida.getvalue()

    def test_dry_run_por_defecto_sale_0_y_no_escribe(self) -> None:
        env = {"FABRICA_ENTORNO": "desarrollo", "FABRICA_RAIZ": str(self.tmp)}
        codigo, _ = self._correr("activar", "--motivo", "prueba", "--json", env=env)
        self.assertEqual(codigo, 0)
        self.assertFalse(kill.ruta_pausa(self.tmp).is_file())

    def test_live_sin_meta_pausar_sale_4_pero_escribe_archivo(self) -> None:
        env = {"FABRICA_ENTORNO": "desarrollo", "FABRICA_RAIZ": str(self.tmp)}
        codigo, salida = self._correr("activar", "--motivo", "A-1", "--live", "--ahora", "2026-11-09T08:00:00Z", "--json", env=env)
        self.assertEqual(codigo, 4)
        self.assertTrue(kill.ruta_pausa(self.tmp).is_file())
        self.assertEqual(json.loads(salida)["codigo"], 4)

    def test_verificar_coherente_sale_0(self) -> None:
        env = {"FABRICA_ENTORNO": "desarrollo", "FABRICA_RAIZ": str(self.tmp)}
        codigo, _ = self._correr("verificar", "--json", env=env)
        self.assertEqual(codigo, 0)


if __name__ == "__main__":
    import unittest

    unittest.main()
