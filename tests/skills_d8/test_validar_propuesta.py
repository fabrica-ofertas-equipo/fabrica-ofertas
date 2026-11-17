"""Pruebas de ``validar_propuesta.py``: forma, respaldo del código y cifras copiadas (no calculadas)."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.skills_d8._comun import SKILL, cargar_modulo, umbrales_prueba

V = cargar_modulo("validar_propuesta")
PR = cargar_modulo("proponer")


def dorado(nombre: str) -> dict:
    return json.loads((SKILL / "evals" / "dorados" / f"{nombre}.json").read_text(encoding="utf-8"))


def plantilla() -> dict:
    return json.loads((SKILL / "templates" / "propuesta-de-decision.json").read_text(encoding="utf-8"))


class Escenario(unittest.TestCase):
    def setUp(self) -> None:
        u = umbrales_prueba()
        self.entrada1 = dorado("D01")["entrada"]
        self.regla1 = PR.evaluar_lanzamiento(self.entrada1, u)
        self.entrada3 = dorado("D03")["entrada"]
        self.regla3 = PR.evaluar_fatiga(self.entrada3, u)
        self.umbrales = u
        t = plantilla()
        self.p_baja = {**t, "propuestas": [t["propuestas"][0]]}
        self.p_relevo = {**t, "modo": "FATIGA", "fecha_cuenta": "2026-11-20", "propuestas": [t["propuestas"][1]]}
        self.fuentes1 = {"entrada.json": self.entrada1, "regla_lanzamiento.json": self.regla1, "umbrales.json": u}
        self.fuentes3 = {"entrada.json": self.entrada3, "regla_fatiga.json": self.regla3, "umbrales.json": u}


class PruebaValidarPropuesta(Escenario):
    def test_la_plantilla_de_baja_valida_contra_las_cifras_reales_del_dorado(self) -> None:
        self.assertEqual(V.validar(self.p_baja, fuentes=self.fuentes1, reglas=[self.regla1]), [])

    def test_la_plantilla_de_relevo_valida_contra_la_salida_de_fatiga(self) -> None:
        self.assertEqual(V.validar(self.p_relevo, fuentes=self.fuentes3, reglas=[self.regla3]), [])

    def test_las_metricas_del_pedido_a_d6_tambien_son_cifras_citables(self) -> None:
        for m in plantilla()["pedidos_creativos"][0]["metricas"]:
            archivo, ruta = m["fuente"].split(":")
            self.assertEqual(V.como_texto(V.resolver(self.fuentes3[archivo], ruta)), m["valor"])

    def test_una_cifra_calculada_a_mano_se_detecta(self) -> None:
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["evidencia"][1]["valor"] = "7400.0"
        errores = V.validar(p, fuentes=self.fuentes1)
        self.assertTrue(any("se copia, no se calcula" in e for e in errores), errores)
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["evidencia"][0]["valor"] = "7000"
        self.assertTrue(V.validar(p, fuentes=self.fuentes1))

    def test_ruta_inexistente_en_la_fuente(self) -> None:
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["evidencia"][0]["fuente"] = "entrada.json:dia.cpa_inventado"
        self.assertTrue(any("no existe" in e for e in V.validar(p, fuentes=self.fuentes1)))

    def test_apagar_sin_respaldo_del_script_se_rechaza(self) -> None:
        d2 = dorado("D02")["entrada"]
        regla2 = PR.evaluar_lanzamiento(d2, self.umbrales)  # MANTENER / ENTREGA_INCOMPLETA
        errores = V.validar(self.p_baja, fuentes={}, reglas=[regla2])
        self.assertTrue(any("no coincide con lo que calculó proponer.py" in e for e in errores), errores)

    def test_relevar_otro_anuncio_sin_respaldo_se_rechaza(self) -> None:
        p = copy.deepcopy(self.p_relevo)
        p["propuestas"][0]["objeto_id"] = "120000000000101"
        self.assertTrue(V.validar(p, reglas=[self.regla3]))

    def test_vocabulario_y_mapeo_al_contrato(self) -> None:
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["accion_contrato"] = "SEGUIR"
        self.assertTrue(any("accion_contrato debe ser MATAR" in e for e in V.validar(p)))
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["accion_negocio"] = "ACTIVAR"
        self.assertTrue(any("desconocida" in e for e in V.validar(p)))

    def test_el_maker_no_ejecuta(self) -> None:
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["ejecutada"] = True
        self.assertTrue(any("ejecutada" in e for e in V.validar(p)))
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["ejecuta"] = "maker"
        self.assertTrue(any("nunca ejecuta" in e for e in V.validar(p)))

    def test_float_y_campos_obligatorios(self) -> None:
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["evidencia"][1]["valor"] = 7400.5
        self.assertTrue(any("float" in e for e in V.validar(p)))
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["evidencia"] = []
        p["propuestas"][0]["explicacion"] = "x" * 601
        e = V.validar(p)
        self.assertTrue(any("evidencia obligatoria" in x for x in e) and any("600" in x for x in e))
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["codigo"] = "minusculas"
        p["propuestas"][0]["gate_efectivo"] = "Z"
        self.assertEqual(sum(1 for x in V.validar(p) if "codigo" in x or "gate_efectivo" in x), 2)

    def test_objeto_de_oferta_y_de_meta(self) -> None:
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["objeto_id"] = "OF-202611-99"
        self.assertTrue(any("oferta_id" in e for e in V.validar(p)))
        p = copy.deepcopy(self.p_relevo)
        p["propuestas"][0]["objeto_id"] = "anuncio-1"
        self.assertTrue(any("id numérico" in e for e in V.validar(p)))

    def test_fuente_mal_formada_o_desconocida(self) -> None:
        p = copy.deepcopy(self.p_baja)
        p["propuestas"][0]["evidencia"][0] = {"fuente": "mi-memoria", "valor": "1"}
        p["propuestas"][0]["evidencia"][1] = {"fuente": "intuicion.json:x", "valor": "1"}
        errores = V.validar(p)
        self.assertTrue(any("debe ser" in e for e in errores) and any("desconocido" in e for e in errores), errores)

    def test_entrada_que_no_es_propuesta(self) -> None:
        self.assertTrue(V.validar([]))
        self.assertTrue(any("propuestas debe ser una lista" in e for e in V.validar({"tipo": "propuesta_d8", "propuestas": "x"})))


class PruebaConsola(Escenario):
    def test_cli_ok_y_con_errores(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            archivos = {"p.json": self.p_baja, "e.json": self.entrada1, "r.json": self.regla1, "u.json": {"umbrales": self.umbrales}}
            for nombre, doc in archivos.items():
                (d / nombre).write_text(json.dumps(doc), encoding="utf-8")
            args = ["--propuesta", str(d / "p.json"), "--entrada", str(d / "e.json"), "--regla", str(d / "r.json"), "--umbrales", str(d / "u.json")]
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                self.assertEqual(V.main(args), 0)
            self.assertTrue(json.loads(salida.getvalue())["valida"])
            mala = copy.deepcopy(self.p_baja)
            mala["propuestas"][0]["evidencia"][1]["valor"] = "1"
            (d / "p.json").write_text(json.dumps(mala), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(V.main(args), 3)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(V.main(["--propuesta", str(d / "no_existe.json")]), 3)
                self.assertEqual(V.main([]), 2)


if __name__ == "__main__":
    unittest.main()
