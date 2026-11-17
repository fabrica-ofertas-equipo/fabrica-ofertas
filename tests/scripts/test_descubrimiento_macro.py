"""Pruebas de `scripts.descubrimiento.macro`: árbol Q0-Q6 (nota 25 §1.2) y su suite de retención."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from engine.errores import ErrorValidacion
from scripts.descubrimiento import macro as M

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "tests" / "fixtures" / "descubrimiento" / "macro_retencion.yaml"


class PruebaArbol(unittest.TestCase):
    def test_salud_primario_sin_ambiguedad(self) -> None:
        r = M.clasificar("de no dormir bien a dormir profundamente toda la noche", senal_id_e3="abc123abc123")
        self.assertEqual(r["estado"], "clasificado")
        self.assertEqual(r["macro_nicho"], "salud")
        self.assertIsNone(r["macro_secundario"])
        self.assertEqual(r["banderas"], {"S": True, "R": False, "D": False})
        self.assertEqual(r["version_arbol"], M.VERSION_ARBOL)

    def test_sin_frase_de_a_a_b_no_es_rechazo_de_macro(self) -> None:
        r = M.clasificar("quiero mejorar mis finanzas personales", senal_id_e3="abc123abc123")
        self.assertEqual(r["estado"], "sin_prueba_frase")
        self.assertIsNone(r["macro_nicho"])
        self.assertIsNone(r["motivo_macro"])

    def test_ninguna_bandera_es_fuera_de_macro(self) -> None:
        r = M.clasificar("de improvisar la cena cada noche a tener un menu variado cada semana", senal_id_e3="abc123abc123")
        self.assertEqual(r["estado"], "fuera_de_macro_nicho")
        self.assertEqual(r["motivo_macro"], "ninguna_bandera")

    def test_hobby_se_detecta_antes_de_evaluar_banderas(self) -> None:
        r = M.clasificar("de no saber tejer a crear mis propios patrones de crochet", senal_id_e3="abc123abc123")
        self.assertEqual((r["estado"], r["motivo_macro"]), ("fuera_de_macro_nicho", "hobby"))

    def test_estetica_se_detecta_como_fuera_de_macro(self) -> None:
        r = M.clasificar("de no saber maquillarme a dominar mi rutina de maquillaje", senal_id_e3="abc123abc123")
        self.assertEqual((r["estado"], r["motivo_macro"]), ("fuera_de_macro_nicho", "estetica"))

    def test_comprador_profesional_es_fuera_de_macro(self) -> None:
        r = M.clasificar("de improvisar las sesiones a tener fichas para psicologos listas para usar", senal_id_e3="abc123abc123")
        self.assertEqual((r["estado"], r["motivo_macro"]), ("fuera_de_macro_nicho", "deseo_del_comprador_es_profesional"))

    def test_sin_senal_id_e3_con_bandera_es_incompleta(self) -> None:
        r = M.clasificar("de no dormir bien a dormir profundamente toda la noche", senal_id_e3=None)
        self.assertEqual(r["estado"], "incompleta")
        self.assertIsNone(r["macro_nicho"])

    def test_sin_bandera_no_exige_senal_id_e3_para_rechazar(self) -> None:
        # El rechazo por macro ocurre ANTES de calcular el riesgo o de exigir evidencia (interfaces §1.4).
        r = M.clasificar("de improvisar la cena cada noche a tener un menu variado cada semana", senal_id_e3=None)
        self.assertEqual(r["estado"], "fuera_de_macro_nicho")

    def test_ambiguedad_la_resuelve_la_cita_e3(self) -> None:
        frase = "de pelearme con mi pareja por el dinero a ahorrar en pareja cada mes"
        # banderas: dinero (ahorrar) y relaciones (pareja) ambas verdaderas sin cita -> prioridad fija (salud>relaciones>dinero)
        sin_cita = M.clasificar(frase, senal_id_e3="abc123abc123")
        self.assertEqual(sin_cita["macro_nicho"], "relaciones")
        self.assertEqual(sin_cita["macro_secundario"], "dinero")
        con_cita = M.clasificar(frase, senal_id_e3="abc123abc123", cita_e3="ahora ahorramos juntos cada mes")
        self.assertEqual(con_cita["macro_nicho"], "dinero")
        self.assertEqual(con_cita["macro_secundario"], "relaciones")

    def test_macro_secundario_nunca_es_igual_al_primario(self) -> None:
        frase = "de pelearme con mi pareja por el dinero a ahorrar en pareja cada mes"
        r = M.clasificar(frase, senal_id_e3="abc123abc123")
        self.assertNotEqual(r["macro_nicho"], r["macro_secundario"])

    def test_frase_vacia_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            M.clasificar("", senal_id_e3="abc123abc123")

    def test_frase_no_texto_es_error_de_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            M.clasificar(None, senal_id_e3="abc123abc123")  # type: ignore[arg-type]

    def test_nunca_copia_la_etiqueta_del_barrido(self) -> None:
        """La firma de `clasificar` no admite ningún parámetro de tema/barrido: solo ve la frase."""
        import inspect
        parametros = set(inspect.signature(M.clasificar).parameters)
        self.assertEqual(parametros, {"prueba_una_frase", "senal_id_e3", "cita_e3"})


class PruebaSuiteDeRetencion(unittest.TestCase):
    def test_la_suite_tiene_al_menos_60_casos_positivos(self) -> None:
        r = M.verificar_retencion(SUITE)
        self.assertGreaterEqual(r["total_positivos"], 60)

    def test_cero_falsos_verdes(self) -> None:
        r = M.verificar_retencion(SUITE)
        self.assertEqual(r["falsos_verdes"], [], r["falsos_verdes"])

    def test_tasa_de_falsos_rojos_no_supera_5_por_ciento(self) -> None:
        r = M.verificar_retencion(SUITE)
        self.assertLessEqual(r["tasa_falsos_rojos"], 0.05, r["falsos_rojos"])

    def test_sin_forma_es_error_de_validacion(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "suite.yaml"
            ruta.write_text("casos: 5\n", encoding="utf-8")
            with self.assertRaises(ErrorValidacion):
                M.verificar_retencion(ruta)

    def test_un_falso_verde_sembrado_se_detecta(self) -> None:
        import tempfile

        import yaml

        datos = yaml.safe_load(SUITE.read_text(encoding="utf-8"))
        victima = next(c for c in datos["casos"] if c["macro_nicho_esperado"] == "fuera_de_macro_nicho" and c.get("motivo_macro_esperado") == "ninguna_bandera")
        # Se cambia la frase sembrada por una que SÍ cae en un macro: debe aparecer como falso verde.
        victima["prueba_una_frase"] = "de no dormir bien a dormir profundamente toda la noche"
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "suite.yaml"
            ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
            r = M.verificar_retencion(ruta)
        self.assertTrue(any(victima["id"] in x for x in r["falsos_verdes"]), r["falsos_verdes"])


class PruebaCli(unittest.TestCase):
    def _correr(self, *args: str) -> tuple[int, str, str]:
        salida, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(err):
            codigo = M.main(list(args))
        return codigo, salida.getvalue(), err.getvalue()

    def test_clasificar_json(self) -> None:
        codigo, out, _ = self._correr("clasificar", "--frase", "de no dormir bien a dormir profundamente toda la noche",
                                       "--senal-id-e3", "abc123abc123", "--json")
        self.assertEqual(codigo, 0)
        datos = json.loads(out)
        self.assertEqual(datos["macro_nicho"], "salud")

    def test_verificar_suite_sale_0(self) -> None:
        codigo, out, _ = self._correr("verificar", str(SUITE))
        self.assertEqual(codigo, 0, out)

    def test_sin_subcomando_es_uso_incorrecto(self) -> None:
        self.assertEqual(self._correr()[0], 2)


if __name__ == "__main__":
    unittest.main()
