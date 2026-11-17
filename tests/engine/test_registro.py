"""Pruebas de ``engine.registro``: cadena de hashes, escritor único, spool, costos, ancla y datos personales."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from engine import comun, registro
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import cadena_registro_valida
from tests.engine.apoyo import PruebaBase

AHORA = datetime(2026, 11, 9, 7, 0, 0, tzinfo=timezone.utc)
CLAVE = b"clave-de-registro-de-prueba"


def _evento(**cambios) -> dict:
    base = {
        "ejecucion_id": "run-20261109-prueba", "oferta_id": "OF-202611-01", "etapa": "D7", "agente": "motor", "evento": "accion",
        "herramienta": "meta.crear", "entrada_resumen": "crear borrador PAUSED", "resultado": {"estado": "dry_run", "codigo": 0},
        "costo_estimado": {"monto": 0, "moneda": "EUR"}, "modo": "dry_run",
    }
    base.update(cambios)
    return base


def _reloj(texto="2026-11-09T07:00:00Z"):
    return lambda: comun.parsear_z(texto)


class BaseRegistro(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.ruta = self.tmp / "empresa" / "registro.jsonl"

    def registrar(self, **cambios) -> dict:
        return registro.registrar(_evento(**cambios), ruta=self.ruta, ahora=_reloj())

    def lineas(self) -> list[dict]:
        return comun.leer_jsonl(self.ruta)


class PruebaRegistrar(BaseRegistro):
    """Cada línea cumple el esquema y se encadena con la anterior."""

    def test_primera_linea_tiene_hash_previo_nulo_y_ts_del_reloj(self) -> None:
        linea = self.registrar()
        self.assertIsNone(linea["hash_previo"])
        self.assertEqual(linea["ts"], "2026-11-09T07:00:00Z")
        self.assertEqual(linea["schema_version"], "1.0.0")
        self.assertRegex(linea["hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(self.lineas(), [linea])

    def test_el_hash_es_el_del_json_canonico_sin_el_propio_hash(self) -> None:
        linea = self.registrar()
        self.assertEqual(linea["hash"], comun.hash_objeto(linea, excluir=("hash",)))

    def test_la_cadena_enlaza_cada_linea_con_la_anterior(self) -> None:
        a, b, c = self.registrar(), self.registrar(herramienta="meta.preflight"), self.registrar(herramienta="meta.activar")
        self.assertEqual((b["hash_previo"], c["hash_previo"]), (a["hash"], b["hash"]))
        self.assertEqual(registro.verificar_cadena(self.ruta), [])

    def test_ts_propio_valido_se_respeta_y_uno_invalido_se_rechaza(self) -> None:
        self.assertEqual(self.registrar(ts="2026-01-02T03:04:05Z")["ts"], "2026-01-02T03:04:05Z")
        with self.assertRaises(ErrorValidacion):
            self.registrar(ts="2026-01-02T03:04:05")

    def test_hash_y_hash_previo_los_asigna_el_registro(self) -> None:
        for campo in ("hash", "hash_previo"):
            with self.subTest(campo=campo), self.assertRaises(ErrorValidacion):
                self.registrar(**{campo: "sha256:" + "0" * 64})

    def test_campos_obligatorios_y_esquema(self) -> None:
        evento = _evento()
        for campo in ("ejecucion_id", "oferta_id", "etapa", "agente", "evento", "herramienta", "entrada_resumen", "resultado", "costo_estimado", "modo"):
            with self.subTest(falta=campo), self.assertRaises(ErrorValidacion):
                registro.registrar({k: v for k, v in evento.items() if k != campo}, ruta=self.ruta)
        invalidos = {"etapa": "D99", "evento": "inventado", "modo": "fixture", "agente": "Motor Raro", "ejecucion_id": "x",
                     "resultado": {"estado": "ok", "codigo": 9}, "costo_estimado": {"monto": -1, "moneda": "EUR"}}
        for campo, valor in invalidos.items():
            with self.subTest(campo=campo), self.assertRaises(ErrorValidacion):
                self.registrar(**{campo: valor})
        self.assertFalse(self.ruta.exists() and self.ruta.read_bytes(), "un evento inválido no deja nada escrito")

    def test_oferta_id_nulo_es_valido_y_flotantes_se_rechazan(self) -> None:
        self.assertIsNone(self.registrar(oferta_id=None)["oferta_id"])
        with self.assertRaises(ErrorValidacion):
            self.registrar(costo_estimado={"monto": 5.0, "moneda": "EUR"})
        with self.assertRaises(ErrorValidacion):
            registro.registrar("no es un mapa", ruta=self.ruta)  # type: ignore[arg-type]

    def test_no_modifica_el_evento_de_entrada(self) -> None:
        evento = _evento()
        copia = copy.deepcopy(evento)
        registro.registrar(evento, ruta=self.ruta, ahora=_reloj())
        self.assertEqual(evento, copia)

    def test_entrada_resumen_se_limpia_y_se_recorta_a_300(self) -> None:
        linea = self.registrar(entrada_resumen="cliente ana@correo.example desde 203.0.113.9 tarjeta 4111111111111111 " + "x" * 400)
        self.assertEqual(len(linea["entrada_resumen"]), registro.MAX_ENTRADA_RESUMEN)
        for dato in ("ana@correo", "203.0.113.9", "4111111111111111"):
            self.assertNotIn(dato, self.ruta.read_text(encoding="utf-8"))
        self.assertTrue(linea["entrada_resumen"].endswith("…"))
        exacto = self.registrar(entrada_resumen="y" * 300)["entrada_resumen"]
        self.assertEqual(exacto, "y" * 300)

    def test_un_secreto_cortado_por_el_recorte_no_llega_al_disco(self) -> None:
        secreto = "s" + "k_live_" + "A1b2C3d4E5f6"
        linea = self.registrar(entrada_resumen="z" * 285 + " " + secreto)
        self.assertNotIn("k_live", linea["entrada_resumen"])
        self.assertNotIn("k_live", self.ruta.read_text(encoding="utf-8"))

    def test_herramienta_tambien_se_limpia(self) -> None:
        self.registrar(herramienta="curl https://x.example?e=ana@correo.example")
        self.assertNotIn("ana@correo", self.ruta.read_text(encoding="utf-8"))

    def test_escritores_concurrentes_no_rompen_la_cadena(self) -> None:
        def escribir(n: int) -> None:
            for i in range(10):
                registro.registrar(_evento(entrada_resumen=f"hilo {n} línea {i}"), ruta=self.ruta, ahora=_reloj())

        hilos = [threading.Thread(target=escribir, args=(n,)) for n in range(6)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(len(self.lineas()), 60)
        self.assertEqual(registro.verificar_cadena(self.ruta), [])

    def test_ruta_por_defecto_sale_de_fabrica_raiz(self) -> None:
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.tmp)}):
            registro.registrar(_evento(), ahora=_reloj())
        self.assertTrue((self.tmp / "empresa" / "registro.jsonl").exists())


class PruebaCadenaRota(BaseRegistro):
    """Alterar, borrar o reordenar una línea rompe la cadena y ``registrar`` se niega a seguir."""

    def setUp(self) -> None:
        super().setUp()
        for i in range(4):
            self.registrar(entrada_resumen=f"evento {i}")
        self.crudo = self.ruta.read_text(encoding="utf-8").splitlines()

    def _escribir(self, lineas: list[str]) -> None:
        self.ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    def test_cadena_integra(self) -> None:
        self.assertEqual(registro.verificar_cadena(self.ruta), [])

    def test_contenido_alterado(self) -> None:
        obj = json.loads(self.crudo[1])
        obj["herramienta"] = "meta.activar"
        self._escribir([self.crudo[0], comun.json_canonico(obj).decode(), *self.crudo[2:]])
        errores = registro.verificar_cadena(self.ruta)
        self.assertTrue(any("hash no coincide" in e and "línea 1" in e for e in errores), errores)

    def test_linea_borrada_del_medio(self) -> None:
        self._escribir([self.crudo[0], self.crudo[2], self.crudo[3]])
        errores = registro.verificar_cadena(self.ruta)
        self.assertTrue(any("no enlaza" in e for e in errores), errores)

    def test_lineas_reordenadas(self) -> None:
        self._escribir([self.crudo[0], self.crudo[2], self.crudo[1], self.crudo[3]])
        self.assertTrue(registro.verificar_cadena(self.ruta))

    def test_primera_linea_borrada(self) -> None:
        self._escribir(self.crudo[1:])
        self.assertTrue(any("no enlaza" in e for e in registro.verificar_cadena(self.ruta)))

    def test_linea_que_no_es_json_o_no_cumple_el_esquema(self) -> None:
        self._escribir([*self.crudo, "esto no es json"])
        self.assertTrue(any("no es JSON" in e for e in registro.verificar_cadena(self.ruta)))
        obj = json.loads(self.crudo[3])
        obj["etapa"] = "D99"
        self._escribir([*self.crudo[:3], comun.json_canonico(obj).decode()])
        self.assertTrue(any("esquema" in e for e in registro.verificar_cadena(self.ruta)))

    def test_registrar_se_niega_a_escribir_sobre_una_cadena_corrupta(self) -> None:
        self.ruta.write_text("\n".join(self.crudo) + '\n{"hash":', encoding="utf-8")
        antes = self.ruta.read_bytes()
        with self.assertRaises(ErrorValidacion):
            self.registrar()
        self.assertEqual(self.ruta.read_bytes(), antes)

    def test_registrar_se_niega_si_una_linea_intermedia_esta_manipulada(self) -> None:
        # ``registrar`` antes solo miraba la ÚLTIMA línea (como verificar_cadena() SOLO lo detectaba
        # después, en una llamada aparte): con una línea INTERMEDIA manipulada y la última intacta,
        # seguía escribiendo encima sin avisar (observación 6). La línea 1 (índice 1 de 4) se altera
        # IGUAL que en test_contenido_alterado, pero aquí la última línea (3) queda perfectamente sana.
        obj = json.loads(self.crudo[1])
        obj["herramienta"] = "meta.activar"
        self._escribir([self.crudo[0], comun.json_canonico(obj).decode(), *self.crudo[2:]])
        self.assertTrue(registro.verificar_cadena(self.ruta), "la manipulación debe ser detectable por verificar_cadena")
        antes = self.ruta.read_bytes()
        with self.assertRaises(ErrorValidacion):
            self.registrar(entrada_resumen="evento nuevo tras la manipulación")
        self.assertEqual(self.ruta.read_bytes(), antes, "no debe haber escrito nada sobre una cadena ya rota")

    def test_registro_inexistente_o_vacio_es_sano(self) -> None:
        self.assertEqual(registro.verificar_cadena(self.tmp / "no-hay.jsonl"), [])
        vacio = self.tmp / "vacio.jsonl"
        vacio.write_text("", encoding="utf-8")
        self.assertEqual(registro.verificar_cadena(vacio), [])


class PruebaAnclaFirmada(BaseRegistro):
    """El ancla HMAC detecta lo que la cadena sola no ve: truncar el final o reescribir el pasado entero."""

    def setUp(self) -> None:
        super().setUp()
        for i in range(5):
            self.registrar(entrada_resumen=f"evento {i}")

    def test_ancla_valida(self) -> None:
        ancla = registro.anclar(self.ruta, clave=CLAVE, ahora=_reloj())
        self.assertEqual((ancla["n"], ancla["ts"]), (5, "2026-11-09T07:00:00Z"))
        self.assertEqual(ancla["hash_cabeza"], self.lineas()[-1]["hash"])
        self.assertRegex(ancla["firma"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertEqual(registro.verificar_cadena(self.ruta, clave_ancla=CLAVE), [])
        self.assertTrue(registro.ruta_anclas(self.ruta).name.endswith("registro.anclas.jsonl"))

    def test_clave_de_el_entorno_inyectado(self) -> None:
        registro.anclar(self.ruta, env={"REGISTRO_HMAC": "otra-clave"}, ahora=_reloj())
        self.assertEqual(registro.verificar_cadena(self.ruta, clave_ancla=b"otra-clave"), [])

    def test_sin_clave_no_se_ancla(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            registro.anclar(self.ruta, env={})
        with self.assertRaises(ErrorBloqueado):
            registro.anclar(self.ruta, env={"REGISTRO_HMAC": ""})

    def test_registro_vacio_no_se_ancla(self) -> None:
        with self.assertRaises(ErrorValidacion):
            registro.anclar(self.tmp / "otro.jsonl", clave=CLAVE)

    def test_clave_equivocada_o_ancla_alterada(self) -> None:
        registro.anclar(self.ruta, clave=CLAVE, ahora=_reloj())
        self.assertTrue(any("firma inválida" in e for e in registro.verificar_cadena(self.ruta, clave_ancla=b"otra")))
        ruta_a = registro.ruta_anclas(self.ruta)
        ancla = comun.leer_jsonl(ruta_a)[0]
        ancla["n"] = 4
        ruta_a.write_text(comun.json_canonico(ancla).decode() + "\n", encoding="utf-8")
        self.assertTrue(any("firma inválida" in e for e in registro.verificar_cadena(self.ruta, clave_ancla=CLAVE)))

    def test_registro_truncado_despues_del_ancla(self) -> None:
        registro.anclar(self.ruta, clave=CLAVE, ahora=_reloj())
        lineas = self.ruta.read_text(encoding="utf-8").splitlines()
        self.ruta.write_text("\n".join(lineas[:3]) + "\n", encoding="utf-8")
        self.assertEqual(comun.leer_jsonl(self.ruta)[-1]["hash_previo"], comun.leer_jsonl(self.ruta)[-2]["hash"], "la cadena sola sigue pareciendo sana")
        self.assertTrue(any("truncado" in e for e in registro.verificar_cadena(self.ruta, clave_ancla=CLAVE)))
        self.assertTrue(any("truncado" in e for e in registro.verificar_cadena(self.ruta)), "la coherencia con el ancla se mira aun sin clave")

    def test_historia_reescrita_con_cadena_valida(self) -> None:
        registro.anclar(self.ruta, clave=CLAVE, ahora=_reloj())
        # Un atacante cambia la línea 2 y recalcula TODOS los hashes siguientes: la cadena sigue siendo válida...
        lineas = [json.loads(x) for x in self.ruta.read_text(encoding="utf-8").splitlines()]
        lineas[1]["herramienta"] = "otra.herramienta"
        previo = lineas[0]["hash"]
        for obj in lineas[1:]:
            obj["hash_previo"] = previo
            obj["hash"] = comun.hash_objeto(obj, excluir=("hash",))
            previo = obj["hash"]
        self.ruta.write_text("".join(comun.json_canonico(x).decode() + "\n" for x in lineas), encoding="utf-8")
        self.assertEqual(cadena_registro_valida(lineas), [])
        # ...pero ya no coincide con el hash de cabeza anclado.
        self.assertTrue(any("reescrita" in e for e in registro.verificar_cadena(self.ruta, clave_ancla=CLAVE)))

    def test_registro_borrado_con_anclas(self) -> None:
        registro.anclar(self.ruta, clave=CLAVE, ahora=_reloj())
        self.ruta.unlink()
        self.assertTrue(any("borrado" in e for e in registro.verificar_cadena(self.ruta, clave_ancla=CLAVE)))

    def test_lineas_nuevas_despues_del_ancla_siguen_siendo_validas(self) -> None:
        registro.anclar(self.ruta, clave=CLAVE, ahora=_reloj())
        self.registrar()
        registro.anclar(self.ruta, clave=CLAVE, ahora=_reloj())
        self.assertEqual(registro.verificar_cadena(self.ruta, clave_ancla=CLAVE), [])
        self.assertEqual([a["n"] for a in comun.leer_jsonl(registro.ruta_anclas(self.ruta))], [5, 6])

    def test_anclas_ilegibles_se_informan(self) -> None:
        registro.ruta_anclas(self.ruta).write_text("no-json\n", encoding="utf-8")
        self.assertTrue(any("anclas ilegibles" in e for e in registro.verificar_cadena(self.ruta, clave_ancla=CLAVE)))


class PruebaCostos(PruebaBase):
    """``costo`` anota en ``costos.jsonl`` con el esquema de F1."""

    def setUp(self) -> None:
        super().setUp()
        self.ruta = self.tmp / "empresa" / "costos.jsonl"

    def _costo(self, **cambios) -> dict:
        args = dict(oferta_id="OF-202611-01", origen="ia", monto_minor=125, moneda="USD", etapa="D3", ejecucion_id="run-20261109-d3",
                    concepto="corrida del Maker de D3")
        args.update(cambios)
        return registro.costo(args.pop("oferta_id"), args.pop("origen"), args.pop("monto_minor"), args.pop("moneda"), ruta=self.ruta, ahora=_reloj(), **args)

    def test_escribe_una_linea_valida(self) -> None:
        linea = self._costo(tokens={"entrada": 1000, "salida": 200}, creditos=0)
        self.assertEqual(comun.leer_jsonl(self.ruta), [linea])
        self.assertEqual(linea["monto"], {"monto": 125, "moneda": "USD"})
        self.assertEqual(linea["ts"], "2026-11-09T07:00:00Z")

    def test_los_costos_suman_lo_registrado(self) -> None:
        for monto in (100, 250, 5):
            self._costo(monto_minor=monto)
        self._costo(oferta_id="empresa", origen="herramienta", monto_minor=10)
        lineas = comun.leer_jsonl(self.ruta)
        self.assertEqual(sum(x["monto"]["monto"] for x in lineas), 365)
        self.assertEqual(sum(x["monto"]["monto"] for x in lineas if x["oferta_id"] == "OF-202611-01"), 355)

    def test_rechaza_lo_invalido_sin_dejar_nada(self) -> None:
        invalidos = [
            {"origen": "regalo"}, {"monto_minor": -1}, {"monto_minor": 1.5}, {"monto_minor": True}, {"moneda": "usd"},
            {"oferta_id": "OF-1"}, {"etapa": "D99"}, {"etapa": None}, {"ejecucion_id": None}, {"concepto": ""}, {"tokens": {"entrada": 1}},
            {"desconocido": 1},
        ]
        for cambios in invalidos:
            with self.subTest(cambios=cambios), self.assertRaises(ErrorValidacion):
                self._costo(**cambios)
        self.assertFalse(self.ruta.exists())

    def test_el_concepto_se_limpia_de_datos_personales(self) -> None:
        self._costo(concepto="soporte a ana@correo.example")
        self.assertNotIn("ana@correo", self.ruta.read_text(encoding="utf-8"))


class PruebaSpool(BaseRegistro):
    """El motor incorpora el spool de los hooks a la cadena, sin duplicar."""

    def setUp(self) -> None:
        super().setUp()
        self.spool = self.tmp / "runs" / "R1" / "herramientas.jsonl"
        self.spool.parent.mkdir(parents=True)

    def _linea(self, **cambios) -> str:
        base = {"ts": "2026-11-09T06:59:00Z", "run_id": "R1", "oferta_id": "OF-202611-01", "etapa": "D3", "rol": "maker", "agente": "d3-maker",
                "evento": "PostToolUse", "tool": "Write", "tool_use_id": "toolu_01ABC",
                "entrada": {"file_path": "ofertas/OF-202611-01/03-oferta/.staging/R1/oferta.json", "bytes": 4120, "sha256": "ab" * 32},
                "resultado": "ok", "duracion_ms": 12, "costo_estimado_centavos": None}
        base.update(cambios)
        return json.dumps(base)

    def _agregar(self, *lineas: str, completar: bool = True) -> None:
        with open(self.spool, "a", encoding="utf-8") as f:
            f.write("\n".join(lineas) + ("\n" if completar else ""))

    def ingerir(self) -> int:
        return registro.ingerir_spool(self.spool, destino=self.ruta, ahora=_reloj())

    def test_ingiere_y_la_cadena_queda_valida(self) -> None:
        self._agregar(self._linea(), self._linea(tool="Edit", tool_use_id="toolu_02"))
        self.assertEqual(self.ingerir(), 2)
        lineas = self.lineas()
        self.assertEqual([x["herramienta"] for x in lineas], ["Write", "Edit"])
        self.assertEqual(lineas[0]["ejecucion_id"], "spool-r1")
        self.assertEqual((lineas[0]["etapa"], lineas[0]["agente"], lineas[0]["oferta_id"]), ("D3", "d3-maker", "OF-202611-01"))
        self.assertEqual((lineas[0]["evento"], lineas[0]["ts"], lineas[0]["modo"]), ("llamada_herramienta", "2026-11-09T06:59:00Z", "dry_run"))
        self.assertEqual(registro.verificar_cadena(self.ruta), [])

    def test_ingerir_dos_veces_no_duplica_y_toma_solo_lo_nuevo(self) -> None:
        self._agregar(self._linea())
        self.assertEqual(self.ingerir(), 1)
        self.assertEqual(self.ingerir(), 0)
        self._agregar(self._linea(tool="Bash"), self._linea(tool="Read"))
        self.assertEqual(self.ingerir(), 2)
        self.assertEqual(len(self.lineas()), 3)
        self.assertEqual(registro.verificar_cadena(self.ruta), [])

    def test_la_linea_a_medio_escribir_espera(self) -> None:
        self._agregar(self._linea())
        with open(self.spool, "a", encoding="utf-8") as f:
            f.write('{"ts":"2026-11-09T07:00:00Z","tool":"Wri')  # un hook todavía la está escribiendo
        self.assertEqual(self.ingerir(), 1)
        with open(self.spool, "a", encoding="utf-8") as f:
            f.write('te"}\n')
        self.assertEqual(self.ingerir(), 1)
        self.assertEqual(self.lineas()[-1]["herramienta"], "Write")

    def test_spool_inexistente_o_vacio(self) -> None:
        self.assertEqual(registro.ingerir_spool(self.tmp / "no-hay.jsonl", destino=self.ruta), 0)
        self.spool.write_text("\n\n", encoding="utf-8")
        self.assertEqual(self.ingerir(), 0)

    def test_linea_ilegible_deja_una_alerta_y_no_detiene_la_ingesta(self) -> None:
        self._agregar("esto no es json", self._linea(), "[1, 2]")
        self.assertEqual(self.ingerir(), 3)
        lineas = self.lineas()
        self.assertEqual([x["evento"] for x in lineas], ["alerta", "llamada_herramienta", "alerta"])
        self.assertEqual(lineas[0]["resultado"], {"estado": "error", "codigo": 3})
        self.assertIn("ilegible", lineas[0]["entrada_resumen"])
        self.assertEqual(registro.verificar_cadena(self.ruta), [])

    def test_deny_se_registra_como_bloqueo(self) -> None:
        self._agregar(self._linea(evento="PreToolUse", resultado="deny", tool="mcp__x__ads_activate_entity"))
        self.ingerir()
        linea = self.lineas()[0]
        self.assertEqual((linea["evento"], linea["resultado"]), ("bloqueo", {"estado": "bloqueado", "codigo": 4}))

    def test_costo_del_spool_y_moneda(self) -> None:
        self._agregar(self._linea(costo_estimado_centavos=37), self._linea(costo_estimado_centavos=-5), self._linea(costo_estimado_centavos=True))
        registro.ingerir_spool(self.spool, destino=self.ruta, ahora=_reloj(), moneda_costo="EUR")
        self.assertEqual([x["costo_estimado"] for x in self.lineas()], [{"monto": 37, "moneda": "EUR"}, {"monto": 0, "moneda": "EUR"}, {"monto": 0, "moneda": "EUR"}])

    def test_campos_desconocidos_caen_a_valores_seguros(self) -> None:
        self._agregar(self._linea(etapa="ZZ", agente="Raro Agente", oferta_id="no-es-id", run_id="", resultado="rarisimo", ts="ayer"))
        self.ingerir()
        linea = self.lineas()[0]
        self.assertEqual((linea["etapa"], linea["agente"], linea["oferta_id"]), ("O0", "hook", None))
        self.assertRegex(linea["ejecucion_id"], r"^[a-z0-9-]{6,40}$")
        self.assertEqual(linea["resultado"], {"estado": "error", "codigo": 1})
        self.assertEqual(linea["ts"], "2026-11-09T07:00:00Z")

    def test_el_run_id_se_vuelve_un_ejecucion_id_valido(self) -> None:
        self._agregar(self._linea(run_id="RUN-20261109-03"), self._linea(run_id="R_1 Raro!"))
        self.ingerir()
        ids = [x["ejecucion_id"] for x in self.lineas()]
        self.assertEqual(ids[0], "RUN-20261109-03")
        self.assertRegex(ids[1], r"^[a-z0-9-]{6,40}$")

    def test_datos_personales_del_spool_no_llegan_al_registro(self) -> None:
        self._agregar(self._linea(entrada={"comando": "mail ana@correo.example 203.0.113.9"}))
        self.ingerir()
        texto = self.ruta.read_text(encoding="utf-8")
        self.assertNotIn("ana@correo", texto)
        self.assertNotIn("203.0.113.9", texto)

    def test_spool_truncado_o_cursor_ilegible_se_rechazan(self) -> None:
        self._agregar(self._linea(), self._linea())
        self.ingerir()
        self.spool.write_text(self._linea() + "\n", encoding="utf-8")  # ahora tiene menos líneas que el cursor
        with self.assertRaises(ErrorValidacion):
            self.ingerir()
        cursor = self.spool.with_name(self.spool.name + ".cursor")
        cursor.write_text("basura", encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            self.ingerir()

    def test_spool_a_la_ruta_de_registro_por_defecto(self) -> None:
        self._agregar(self._linea())
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": str(self.tmp)}):
            registro.ingerir_spool(self.spool, ahora=_reloj())
        self.assertTrue((self.tmp / "empresa" / "registro.jsonl").exists())


class PruebaCli(BaseRegistro):
    """``python -m engine.registro verificar|anclar``."""

    def _correr(self, *args: str, env: dict | None = None) -> tuple[int, str]:
        salida = io.StringIO()
        entorno = {"FABRICA_ENTORNO": "prueba", **(env or {})}
        with mock.patch.dict(os.environ, entorno), contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = registro.main(list(args))
        return codigo, salida.getvalue()

    def test_verificar_sano_y_roto(self) -> None:
        self.registrar()
        self.registrar()
        codigo, texto = self._correr("verificar", "--raiz", str(self.tmp), "--json")
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(texto)["datos"]["problemas"], [])
        lineas = self.ruta.read_text(encoding="utf-8").splitlines()
        self.ruta.write_text(lineas[1] + "\n", encoding="utf-8")
        codigo, texto = self._correr("verificar", "--raiz", str(self.tmp), "--json")
        self.assertEqual(codigo, 3)
        self.assertTrue(json.loads(texto)["datos"]["problemas"])

    def test_anclar_exige_la_clave_y_verificar_la_usa(self) -> None:
        self.registrar()
        codigo, _ = self._correr("anclar", "--raiz", str(self.tmp), "--json")
        self.assertEqual(codigo, 4)
        codigo, texto = self._correr("anclar", "--raiz", str(self.tmp), "--json", env={"REGISTRO_HMAC": "k"})
        self.assertEqual(codigo, 0, texto)
        codigo, texto = self._correr("verificar", "--raiz", str(self.tmp), "--json")
        self.assertEqual(codigo, 0)
        self.assertTrue(json.loads(texto)["avisos"], "avisa que no pudo verificar las firmas sin clave")
        codigo, _ = self._correr("verificar", "--raiz", str(self.tmp), "--json", env={"REGISTRO_HMAC": "otra"})
        self.assertEqual(codigo, 3)

    def test_raiz_alternativa_no_existe_en_produccion(self) -> None:
        codigo, _ = self._correr("verificar", "--raiz", str(self.tmp), env={"FABRICA_ENTORNO": "produccion"})
        self.assertEqual(codigo, 2)


if __name__ == "__main__":
    unittest.main()
