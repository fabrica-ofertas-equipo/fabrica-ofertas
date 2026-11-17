"""Pruebas de `scripts.descubrimiento.banco`: alta, estados/transiciones, índice y caducidad del
banco de problemas (interfaces d1-v2 §2, §2.3, §2.4, §8.2 n.2; defecto D1d n.3).

Casos límite obligatorios (convenciones §11): banco vacío (cero), caducidad en el tope exacto y
tope + 1 día, parámetro de caducidad faltante, `PAUSA` presente, dry-run vs. `--aplicar`.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine.errores import ErrorBloqueado, ErrorLimite, ErrorUso, ErrorValidacion
from scripts.descubrimiento import banco as B

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_ENGINE_PARAMETROS = RAIZ / "tests" / "fixtures" / "engine" / "empresa_prueba" / "parametros.yaml"


def _ahora_fija(momento: datetime):
    return lambda: momento


class _RaizTemporal:
    """Carpeta temporal vacía (sin `empresa/`); los tests la pueblan según lo que necesiten."""

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        return Path(self._tmp.name)

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()


class _RaizConParametros(_RaizTemporal):
    """Igual, pero copia (solo lectura, reusa fixture de engine) `parametros.yaml` con
    `descubrimiento.caducidad_banco_dias = 90`."""

    def __enter__(self) -> Path:
        base = super().__enter__()
        empresa = base / "empresa"
        empresa.mkdir()
        shutil.copy(FIXTURE_ENGINE_PARAMETROS, empresa / "parametros.yaml")
        return base


class PruebaGenerarProblemaId(unittest.TestCase):
    def test_primero_del_mes_es_0001(self) -> None:
        with _RaizTemporal() as raiz:
            pid = B.generar_problema_id(raiz, ahora=_ahora_fija(datetime(2026, 11, 6, tzinfo=timezone.utc)))
        self.assertEqual(pid, "PRB-202611-0001")

    def test_correlativo_ignora_otros_meses(self) -> None:
        with _RaizTemporal() as raiz:
            carpeta = raiz / "empresa" / "descubrimiento" / "problemas"
            carpeta.mkdir(parents=True)
            (carpeta / "PRB-202611-0001.json").write_text("{}", encoding="utf-8")
            (carpeta / "PRB-202611-0003.json").write_text("{}", encoding="utf-8")
            (carpeta / "PRB-202610-0099.json").write_text("{}", encoding="utf-8")
            pid = B.generar_problema_id(raiz, ahora=_ahora_fija(datetime(2026, 11, 6, tzinfo=timezone.utc)))
        self.assertEqual(pid, "PRB-202611-0004")


class PruebaNuevoYCrearProblema(unittest.TestCase):
    def test_via_invalida_falla(self) -> None:
        with self.assertRaises(ErrorValidacion):
            B.nuevo_problema("PRB-202611-0001", via="otra", locale_origen="es-MX")

    def test_doc_semilla_tiene_los_campos_minimos(self) -> None:
        doc = B.nuevo_problema("PRB-202611-0001", via="oferta_primero", locale_origen="es-MX",
                               ahora=_ahora_fija(datetime(2026, 11, 6, tzinfo=timezone.utc)))
        self.assertEqual(doc["estado"], "semilla")
        self.assertEqual(doc["pares_modelado"], [])
        self.assertEqual(doc["intentos_reencuadre"], 0)
        self.assertIsNone(doc["rechazo"])
        self.assertEqual(doc["creado_en"], "2026-11-06T00:00:00Z")

    def test_crear_problema_dry_run_no_escribe_nada(self) -> None:
        with _RaizTemporal() as raiz:
            doc = B.crear_problema(raiz, via="oferta_primero", locale_origen="es-MX",
                                   ahora=_ahora_fija(datetime(2026, 11, 6, tzinfo=timezone.utc)))
            self.assertFalse((raiz / "empresa" / "descubrimiento" / "problemas").exists())
        self.assertEqual(doc["problema_id"], "PRB-202611-0001")

    def test_crear_problema_aplicar_escribe_atomico(self) -> None:
        with _RaizTemporal() as raiz:
            doc = B.crear_problema(raiz, via="oferta_primero", locale_origen="es-MX", aplicar=True)
            ruta = B.ruta_problema(raiz, doc["problema_id"])
            self.assertTrue(ruta.is_file())
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["problema_id"], doc["problema_id"])

    def test_crear_problema_con_pausa_bloquea_con_4(self) -> None:
        with _RaizTemporal() as raiz:
            (raiz / "empresa").mkdir()
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            with self.assertRaises(ErrorBloqueado) as cm:
                B.crear_problema(raiz, via="oferta_primero", locale_origen="es-MX", aplicar=True)
            self.assertEqual(cm.exception.codigo_salida, 4)
            self.assertFalse((raiz / "empresa" / "descubrimiento" / "problemas").exists())


class PruebaTransiciones(unittest.TestCase):
    def _doc(self, estado: str = "semilla") -> dict:
        doc = B.nuevo_problema("PRB-202611-0001", via="oferta_primero", locale_origen="es-MX")
        doc["estado"] = estado
        return doc

    def test_transicion_permitida_cambia_estado_y_actualizado_en(self) -> None:
        doc = self._doc("semilla")
        nuevo = B.transicionar(doc, "normalizado", ahora=_ahora_fija(datetime(2026, 11, 7, tzinfo=timezone.utc)))
        self.assertEqual(nuevo["estado"], "normalizado")
        self.assertEqual(nuevo["actualizado_en"], "2026-11-07T00:00:00Z")
        self.assertIsNot(nuevo, doc)  # no muta el original

    def test_transicion_no_permitida_falla(self) -> None:
        doc = self._doc("semilla")
        with self.assertRaises(ErrorValidacion) as cm:
            B.transicionar(doc, "vigente")
        self.assertEqual(cm.exception.codigo_salida, 3)

    def test_estado_destino_desconocido_falla(self) -> None:
        doc = self._doc("semilla")
        with self.assertRaises(ErrorValidacion):
            B.transicionar(doc, "no_existe")

    def test_a_rechazado_guarda_el_motivo(self) -> None:
        doc = self._doc("con_ficha")
        nuevo = B.transicionar(doc, "rechazado", motivo={"motivo": "fuera_de_macro_nicho", "detalle": "x"})
        self.assertEqual(nuevo["rechazo"]["motivo"], "fuera_de_macro_nicho")

    def test_a_en_reencuadre_incrementa_intentos(self) -> None:
        doc = self._doc("con_ficha")
        doc["intentos_reencuadre"] = 1
        nuevo = B.transicionar(doc, "en_reencuadre")
        self.assertEqual(nuevo["intentos_reencuadre"], 2)

    def test_elegido_a_devuelto_d2_permitido_pero_no_al_reves(self) -> None:
        doc = self._doc("elegido")
        nuevo = B.transicionar(doc, "devuelto_d2")
        self.assertEqual(nuevo["estado"], "devuelto_d2")
        with self.assertRaises(ErrorValidacion):
            B.transicionar(nuevo, "elegido")

    def test_vencido_puede_refrescar_a_vigente_o_archivarse(self) -> None:
        doc = self._doc("vencido")
        self.assertEqual(B.transicionar(doc, "vigente")["estado"], "vigente")
        self.assertEqual(B.transicionar(doc, "archivado")["estado"], "archivado")

    def test_archivado_es_terminal(self) -> None:
        doc = self._doc("archivado")
        with self.assertRaises(ErrorValidacion):
            B.transicionar(doc, "vigente")


class PruebaCargarGuardar(unittest.TestCase):
    def test_cargar_problema_inexistente_falla_con_2(self) -> None:
        with _RaizTemporal() as raiz:
            with self.assertRaises(ErrorUso) as cm:
                B.cargar_problema(raiz, "PRB-202611-0001")
            self.assertEqual(cm.exception.codigo_salida, 2)

    def test_round_trip_guardar_y_cargar(self) -> None:
        with _RaizTemporal() as raiz:
            doc = B.crear_problema(raiz, via="oferta_primero", locale_origen="es-MX", aplicar=True)
            releido = B.cargar_problema(raiz, doc["problema_id"])
            self.assertEqual(releido["problema_id"], doc["problema_id"])

    def test_guardar_problema_sin_aplicar_no_escribe(self) -> None:
        with _RaizTemporal() as raiz:
            doc = B.nuevo_problema("PRB-202611-0001", via="oferta_primero", locale_origen="es-MX")
            ruta = B.guardar_problema(raiz, doc, aplicar=False)
            self.assertFalse(ruta.is_file())


class PruebaIndice(unittest.TestCase):
    def test_banco_vacio_tiene_cero_problemas(self) -> None:
        with _RaizTemporal() as raiz:
            indice = B.reconstruir_indice(raiz)
        self.assertEqual(indice["problemas"], [])
        self.assertTrue(indice["banco_hash"].startswith("sha256:"))

    def test_indice_con_problemas_y_escritura(self) -> None:
        with _RaizTemporal() as raiz:
            B.crear_problema(raiz, via="oferta_primero", locale_origen="es-MX", aplicar=True)
            B.crear_problema(raiz, via="oferta_primero", locale_origen="es-MX", aplicar=True)
            indice = B.reconstruir_indice(raiz, aplicar=True)
            self.assertEqual(len(indice["problemas"]), 2)
            ruta = B.ruta_indice(raiz)
            self.assertTrue(ruta.is_file())
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["banco_hash"], indice["banco_hash"])

    def test_indice_con_pausa_bloquea_la_escritura(self) -> None:
        with _RaizTemporal() as raiz:
            (raiz / "empresa").mkdir()
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            with self.assertRaises(ErrorBloqueado):
                B.reconstruir_indice(raiz, aplicar=True)


class PruebaParesModelado(unittest.TestCase):
    def test_agrega_y_dedup_por_par_id(self) -> None:
        doc = B.nuevo_problema("PRB-202611-0001", via="oferta_primero", locale_origen="es-MX")
        doc = B.agregar_pares_modelado(doc, [{"par_id": "modelo-1@MX", "estado_par": "incompleta",
                                              "pendiente": ["evidencia"]}])
        doc = B.agregar_pares_modelado(doc, [{"par_id": "modelo-1@MX", "estado_par": "no_pasa"},
                                             {"par_id": "modelo-2@MX", "estado_par": "vetada"}])
        pares = {p["par_id"]: p["estado_par"] for p in doc["pares_modelado"]}
        self.assertEqual(pares, {"modelo-1@MX": "no_pasa", "modelo-2@MX": "vetada"})

    def test_par_sin_par_id_falla(self) -> None:
        doc = B.nuevo_problema("PRB-202611-0001", via="oferta_primero", locale_origen="es-MX")
        with self.assertRaises(ErrorValidacion):
            B.agregar_pares_modelado(doc, [{"estado_par": "no_pasa"}])


class PruebaCaducidad(unittest.TestCase):
    def test_sin_problemas_vigentes_no_hay_transiciones(self) -> None:
        with _RaizConParametros() as raiz:
            self.assertEqual(B.evaluar_caducidad(raiz), [])

    def test_falta_caducidad_banco_dias_falla_con_5(self) -> None:
        import yaml

        with _RaizConParametros() as raiz:
            ruta = raiz / "empresa" / "parametros.yaml"
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
            datos["grupos"]["descubrimiento"]["caducidad_banco_dias"]["valor"] = None  # pendiente de calibrar
            ruta.write_text(yaml.safe_dump(datos), encoding="utf-8")
            with self.assertRaises(ErrorLimite) as cm:
                B.evaluar_caducidad(raiz)
            self.assertEqual(cm.exception.codigo_salida, 5)

    def test_en_el_tope_exacto_no_vence_todavia(self) -> None:
        creado = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ahora = creado + timedelta(days=90)  # caducidad_banco_dias = 90 en el fixture
        with _RaizConParametros() as raiz:
            doc = B.nuevo_problema("PRB-202601-0001", via="oferta_primero", locale_origen="es-MX",
                                   ahora=_ahora_fija(creado))
            doc["estado"] = "vigente"
            B.guardar_problema(raiz, doc, aplicar=True)
            transiciones = B.evaluar_caducidad(raiz, ahora=_ahora_fija(ahora))
        self.assertEqual(transiciones, [])

    def test_tope_mas_un_dia_vence(self) -> None:
        creado = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ahora = creado + timedelta(days=91)
        with _RaizConParametros() as raiz:
            doc = B.nuevo_problema("PRB-202601-0001", via="oferta_primero", locale_origen="es-MX",
                                   ahora=_ahora_fija(creado))
            doc["estado"] = "vigente"
            B.guardar_problema(raiz, doc, aplicar=True)
            transiciones = B.evaluar_caducidad(raiz, ahora=_ahora_fija(ahora))
        self.assertEqual(transiciones, [{"problema_id": "PRB-202601-0001", "de": "vigente", "a": "vencido"}])

    def test_tope_mas_un_dia_con_aplicar_escribe_vencido(self) -> None:
        creado = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ahora = creado + timedelta(days=91)
        with _RaizConParametros() as raiz:
            doc = B.nuevo_problema("PRB-202601-0001", via="oferta_primero", locale_origen="es-MX",
                                   ahora=_ahora_fija(creado))
            doc["estado"] = "vigente"
            B.guardar_problema(raiz, doc, aplicar=True)
            B.evaluar_caducidad(raiz, ahora=_ahora_fija(ahora), aplicar=True)
            releido = B.cargar_problema(raiz, "PRB-202601-0001")
        self.assertEqual(releido["estado"], "vencido")

    def test_caducidad_con_pausa_bloquea_la_escritura(self) -> None:
        creado = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ahora = creado + timedelta(days=91)
        with _RaizConParametros() as raiz:
            doc = B.nuevo_problema("PRB-202601-0001", via="oferta_primero", locale_origen="es-MX",
                                   ahora=_ahora_fija(creado))
            doc["estado"] = "vigente"
            B.guardar_problema(raiz, doc, aplicar=True)
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            with self.assertRaises(ErrorBloqueado):
                B.evaluar_caducidad(raiz, ahora=_ahora_fija(ahora), aplicar=True)


class PruebaCli(unittest.TestCase):
    def _correr(self, argv: list[str]) -> tuple[int, str]:
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            codigo = B.main(argv)
        return codigo, buf.getvalue()

    def test_crear_y_transicionar_e_indice_de_punta_a_punta(self) -> None:
        with _RaizTemporal() as raiz:
            codigo, salida = self._correr(
                ["--raiz", str(raiz), "crear", "--via", "oferta_primero", "--locale-origen", "es-MX",
                 "--aplicar", "--json"])
            self.assertEqual(codigo, 0, salida)
            problema_id = json.loads(salida)["problema_id"]

            codigo, salida = self._correr(
                ["--raiz", str(raiz), "transicionar", problema_id, "--a", "normalizado", "--aplicar", "--json"])
            self.assertEqual(codigo, 0, salida)
            self.assertEqual(json.loads(salida)["a"], "normalizado")

            codigo, salida = self._correr(["--raiz", str(raiz), "indice", "--aplicar", "--json"])
            self.assertEqual(codigo, 0, salida)
            self.assertEqual(json.loads(salida)["problemas_n"], 1)

    def test_transicion_invalida_sale_con_3(self) -> None:
        with _RaizTemporal() as raiz:
            _, salida = self._correr(
                ["--raiz", str(raiz), "crear", "--via", "oferta_primero", "--locale-origen", "es-MX",
                 "--aplicar", "--json"])
            problema_id = json.loads(salida)["problema_id"]
            codigo, _ = self._correr(["--raiz", str(raiz), "transicionar", problema_id, "--a", "vigente"])
            self.assertEqual(codigo, 3)

    def test_caducar_cli_sin_parametros_sale_con_5(self) -> None:
        with _RaizTemporal() as raiz:
            (raiz / "empresa").mkdir()
            codigo, _ = self._correr(["--raiz", str(raiz), "caducar"])
            self.assertEqual(codigo, 5)


if __name__ == "__main__":
    unittest.main()
