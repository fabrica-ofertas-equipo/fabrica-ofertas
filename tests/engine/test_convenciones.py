"""Comprobaciones estáticas del núcleo del motor contra ``docs/convenciones-de-codigo.md``.

Son pruebas sobre el código fuente de ``engine/{errores,comun,limites,parametros,guard,registro,transporte}.py``:
núcleo sin ciclos, sin red, sin ``float``, sin ``except:`` desnudo, sin reloj sin zona, sin números de decisión
fijos dentro de las funciones y con docstring en español en todo lo público.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import unittest

from tests.engine.apoyo import RAIZ_REPO, PruebaBase

MODULOS = ("errores", "comun", "limites", "parametros", "guard", "registro", "transporte")
PAQUETES_DEL_PROYECTO = {"engine", "decision", "datos", "meta", "compliance", "postcompra", "landing", "dashboard", "agentes", "infra",
                         "contratos", "scripts", "tracking"}
PROHIBIDOS_DE_RED = {"socket", "urllib", "http", "requests", "httpx", "ssl", "ftplib", "smtplib", "aiohttp"}


def _arbol(nombre: str) -> ast.Module:
    return ast.parse((RAIZ_REPO / "engine" / f"{nombre}.py").read_text(encoding="utf-8"))


def _importaciones(arbol: ast.Module) -> list[str]:
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            nombres.append(nodo.module)
    return nombres


class PruebaConvenciones(PruebaBase):
    """Reglas de código que no se dejan a la buena voluntad."""

    def test_nucleo_sin_ciclos_solo_importa_engine_y_validar_esquemas(self) -> None:
        for nombre in MODULOS:
            for modulo in _importaciones(_arbol(nombre)):
                raiz = modulo.split(".")[0]
                if raiz in PAQUETES_DEL_PROYECTO:
                    with self.subTest(modulo=nombre, importa=modulo):
                        self.assertTrue(modulo.startswith("engine") or modulo == "scripts.validar_esquemas", f"{nombre} importa {modulo}")

    def test_los_modulos_basicos_no_importan_a_los_de_arriba(self) -> None:
        capas = {"errores": set(), "comun": {"errores"}, "parametros": {"errores", "comun"}, "transporte": {"errores", "comun"},
                 "limites": {"errores", "comun"}, "registro": {"errores", "comun"}, "guard": {"errores", "comun", "limites", "parametros", "transporte"}}
        for nombre, permitidos in capas.items():
            internos = {m.split(".")[1] for m in _importaciones(_arbol(nombre)) if m.startswith("engine.")}
            internos |= {a.name for n in ast.walk(_arbol(nombre)) if isinstance(n, ast.ImportFrom) and n.module == "engine" for a in n.names}
            with self.subTest(modulo=nombre):
                self.assertLessEqual(internos, permitidos, f"{nombre} importa {internos - permitidos}")

    def test_ningun_modulo_del_nucleo_importa_red(self) -> None:
        for nombre in MODULOS:
            for modulo in _importaciones(_arbol(nombre)):
                with self.subTest(modulo=nombre, importa=modulo):
                    self.assertNotIn(modulo.split(".")[0], PROHIBIDOS_DE_RED)

    def test_sin_float_ni_division_de_importes(self) -> None:
        for nombre in MODULOS:
            for nodo in ast.walk(_arbol(nombre)):
                with self.subTest(modulo=nombre, linea=getattr(nodo, "lineno", 0)):
                    if isinstance(nodo, ast.Name):
                        self.assertNotEqual(nodo.id, "float")
                    if isinstance(nodo, ast.Constant):
                        self.assertNotIsInstance(nodo.value, float)
                    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
                        # Solo se admite la unión de rutas de pathlib (`ruta / "x"`); jamás una división numérica.
                        self.assertTrue(isinstance(nodo.right, (ast.Constant, ast.Name, ast.Call, ast.Attribute, ast.Subscript)))
                        if isinstance(nodo.right, ast.Constant):
                            self.assertIsInstance(nodo.right.value, str)

    def test_sin_except_desnudo_ni_reloj_sin_zona_ni_sleep(self) -> None:
        for nombre in MODULOS:
            for nodo in ast.walk(_arbol(nombre)):
                with self.subTest(modulo=nombre, linea=getattr(nodo, "lineno", 0)):
                    if isinstance(nodo, ast.ExceptHandler):
                        self.assertIsNotNone(nodo.type, "except: desnudo")
                    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
                        self.assertNotIn(nodo.func.attr, {"utcnow", "utcfromtimestamp", "sleep", "today"})
                        if nodo.func.attr == "now":
                            self.assertTrue(nodo.args or nodo.keywords, "datetime.now() sin zona")

    def test_sin_numeros_de_decision_fijos_dentro_de_funciones(self) -> None:
        """Ningún entero de dos o más cifras dentro de una función: los umbrales salen de limites/parametros."""
        for nombre in MODULOS:
            arbol = _arbol(nombre)
            for funcion in (n for n in ast.walk(arbol) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
                for nodo in ast.walk(funcion):
                    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, int) and not isinstance(nodo.value, bool) and abs(nodo.value) >= 10:
                        with self.subTest(modulo=nombre, funcion=funcion.name, linea=nodo.lineno):
                            self.fail(f"literal {nodo.value} dentro de {funcion.name}: súbelo a una constante con nombre o a limites/parametros")

    def test_todo_lo_publico_tiene_docstring_en_espanol(self) -> None:
        """Módulo, clases, funciones y métodos públicos (no las funciones locales de una función) llevan docstring."""
        for nombre in MODULOS:
            arbol = _arbol(nombre)
            with self.subTest(modulo=nombre):
                self.assertTrue(ast.get_docstring(arbol), "módulo sin docstring")
            candidatos = list(arbol.body)
            for clase in (n for n in arbol.body if isinstance(n, ast.ClassDef)):
                candidatos += clase.body
            for nodo in candidatos:
                if isinstance(nodo, (ast.FunctionDef, ast.ClassDef)) and not nodo.name.startswith("_"):
                    with self.subTest(modulo=nombre, nombre=nodo.name):
                        self.assertTrue(ast.get_docstring(nodo), f"{nodo.name} sin docstring")

    def test_nombres_de_archivo_ascii_y_firmas_congeladas_importables(self) -> None:
        for nombre in MODULOS:
            self.assertTrue(nombre.isascii() and re.fullmatch(r"[a-z_]+", nombre))
        from engine import comun, errores, guard, limites, parametros, registro, transporte
        firmas = {
            errores: ("ErrorFabrica", "ErrorUso", "ErrorValidacion", "ErrorBloqueado", "ErrorLimite", "ErrorExterno", "ParametroFaltante"),
            comun: ("raiz", "entorno", "ahora_utc", "iso_z", "parsear_z", "dia_de_cuenta", "escribir_atomico", "anexar_jsonl", "leer_jsonl",
                    "json_canonico", "hash_objeto", "hash_archivo", "hash_directorio", "clave_idempotencia", "firma_hmac", "comparar_hash"),
            limites: ("cargar_limites", "exigir_operacion", "exigir_agregados"),
            parametros: ("cargar_parametros", "Parametros"),
            guard: ("comprobar_live", "ContextoLive"),
            registro: ("registrar", "ingerir_spool", "costo", "verificar_cadena"),
            transporte: ("Transporte", "TransporteFixture"),
        }
        for modulo, nombres in firmas.items():
            for n in nombres:
                with self.subTest(modulo=modulo.__name__, nombre=n):
                    self.assertTrue(hasattr(modulo, n))

    def test_la_fixture_de_infra_no_dispara_la_regla_c_de_tarjetas_luhn(self) -> None:
        """``scripts.lint_estatico`` (I1) marca secuencias de 13-19 dígitos con Luhn válido como tarjeta.

        Los marcadores de relleno de ``estado.json`` (``commit``/``hash_scripts``) eran de puros ceros:
        un relleno de solo ceros de longitud >= 13 es Luhn-válido (suma 0), así que ``regla_c`` los
        marcaba como falsas tarjetas (observación de la ronda de endurecimiento). Se reconstruye el
        contenido ANTERIOR en una copia temporal para probar que de verdad disparaba la regla, y se
        comprueba que la fixture ACTUAL (``deadbeef…``, sin dígitos) ya no la dispara.
        """
        import shutil
        import tempfile
        from pathlib import Path

        from scripts import lint_estatico

        fixture = RAIZ_REPO / "tests" / "fixtures" / "engine" / "empresa_prueba"
        with tempfile.TemporaryDirectory(prefix="fabrica-lint-c-") as carpeta:
            base = Path(carpeta)
            destino = base / "tests" / "fixtures" / "empresa_prueba"
            shutil.copytree(fixture, destino)
            hallazgos_actuales = lint_estatico.regla_c_datos_personales(base)
            self.assertEqual(hallazgos_actuales, [], hallazgos_actuales)

            ruta_estado = destino / "infra" / "estado.json"
            texto = ruta_estado.read_text(encoding="utf-8")
            texto_viejo = texto.replace("deadbeef" * 5, "0" * 40).replace("deadbeef" * 8, "0" * 64)
            self.assertNotEqual(texto, texto_viejo, "la sustitución no encontró el relleno esperado")
            ruta_estado.write_text(texto_viejo, encoding="utf-8")
            # La regla (c) ahora exige prefijo de emisor: ni siquiera el relleno ANTERIOR de puros ceros (Luhn-válido)
            # se marca como tarjeta (ajuste de S-B al lint estático, 2026-11-06).
            hallazgos_viejos = lint_estatico.regla_c_datos_personales(base)
            self.assertEqual({h.linea for h in hallazgos_viejos}, set(), hallazgos_viejos)

            # Que la regla siga viva: una tarjeta de prueba real en esa misma fixture SÍ se marca.
            ruta_estado.write_text(texto_viejo.replace("0" * 40, "4242424242424242", 1), encoding="utf-8")
            con_tarjeta = lint_estatico.regla_c_datos_personales(base)
            self.assertEqual({h.linea for h in con_tarjeta}, {7}, con_tarjeta)

    def test_compileall_sin_errores(self) -> None:
        resultado = subprocess.run([sys.executable, "-m", "compileall", "-q", str(RAIZ_REPO / "engine"), str(RAIZ_REPO / "tests" / "engine")],
                                   capture_output=True, text=True, env={"PYTHONPYCACHEPREFIX": str(self.tmp / "pyc"), "PATH": "/usr/bin:/bin"})
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)


if __name__ == "__main__":
    unittest.main()
