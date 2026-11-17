"""Pruebas de scripts.lint_estatico (I1, MA-12): un caso verde y uno rojo por regla, más los
dos mecanismos de excepción (marcador en línea y lista blanca) y los códigos de salida de la CLI
(docs/convenciones-de-codigo.md §8). Sin red: ninguna regla abre sockets, solo lee archivos.
"""
from __future__ import annotations

import io
import shutil
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import lint_estatico as L

RAIZ_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "lint_estatico"


def _sin_red(caso: unittest.TestCase) -> None:
    original = socket.socket

    def bloqueado(*a, **k):
        raise AssertionError("las pruebas de lint_estatico no pueden abrir sockets")

    socket.socket = bloqueado  # type: ignore[assignment]
    caso.addCleanup(setattr, socket, "socket", original)


class PruebaReglaA(unittest.TestCase):
    """(a) float o división sobre un importe aparente en engine/decision/datos/meta/postcompra/landing."""

    def setUp(self) -> None:
        _sin_red(self)
        self.base = RAIZ_FIXTURES / "regla_a_float_dinero"

    def test_verde_sin_hallazgos(self) -> None:
        hallazgos = L.regla_a_float_o_division_en_dinero(self.base / "verde")
        self.assertEqual([], hallazgos)

    def test_rojo_detecta_float_y_division(self) -> None:
        hallazgos = L.regla_a_float_o_division_en_dinero(self.base / "rojo")
        self.assertEqual(3, len(hallazgos))
        self.assertTrue(all(h.regla == "a" for h in hallazgos))
        mensajes = " ".join(h.mensaje for h in hallazgos)
        self.assertIn("float", mensajes)
        self.assertIn("división", mensajes)


class PruebaReglaB(unittest.TestCase):
    """(b) literal numérico de 2+ dígitos dentro de una función de límite o umbral."""

    def setUp(self) -> None:
        _sin_red(self)
        self.base = RAIZ_FIXTURES / "regla_b_literal_fijo"

    def test_verde_sin_hallazgos(self) -> None:
        hallazgos = L.regla_b_literal_fijo_en_limites(self.base / "verde")
        self.assertEqual([], hallazgos)

    def test_rojo_detecta_literal_fijo(self) -> None:
        hallazgos = L.regla_b_literal_fijo_en_limites(self.base / "rojo")
        self.assertEqual(1, len(hallazgos))
        self.assertEqual("b", hallazgos[0].regla)
        self.assertIn("1500", hallazgos[0].mensaje)

    def test_excluye_tests_y_contratos(self) -> None:
        """La misma función roja, bajo tests/ o contratos/, queda fuera de alcance de la regla."""
        hallazgos = L.regla_b_literal_fijo_en_limites(self.base / "exclusion")
        self.assertEqual([], hallazgos)


class PruebaReglaC(unittest.TestCase):
    """(c) correo, IP y número de tarjeta (Luhn) en ofertas/, empresa/, tests/fixtures/ y logs."""

    def setUp(self) -> None:
        _sin_red(self)
        self.base = RAIZ_FIXTURES / "regla_c_datos_personales"

    def test_verde_sin_hallazgos(self) -> None:
        hallazgos = L.regla_c_datos_personales(self.base / "verde")
        self.assertEqual([], hallazgos)

    def test_rojo_detecta_correo_ip_y_tarjeta(self) -> None:
        hallazgos = L.regla_c_datos_personales(self.base / "rojo")
        self.assertEqual(3, len(hallazgos))
        mensajes = " ".join(h.mensaje for h in hallazgos)
        self.assertIn("correo", mensajes)
        self.assertIn("IP", mensajes)
        self.assertIn("tarjeta", mensajes)
        # El propio informe no debe filtrar el valor real (convenciones §10): se enmascara.
        for h in hallazgos:
            self.assertNotIn("cliente.ejemplo@correo-test.com", h.mensaje)
            self.assertNotIn("203.0.113.42", h.mensaje)
            self.assertNotIn("4539148803436467", h.mensaje)

    def test_tarjetas_de_prueba_reales_siguen_marcandose(self) -> None:
        for numero in ("4242 4242 4242 4242", "5555-5555-5555-4444", "378282246310005", "6011111111111117"):
            with self.subTest(numero=numero):
                self.assertIsNotNone(L._buscar_tarjeta(f"tarjeta: {numero} fin"))

    def test_no_marca_identificadores_ni_hashes_que_pasan_luhn_por_azar(self) -> None:
        casos = [
            '"page_id": 1056023200924288,',                      # ID de página de Meta (16 dígitos, Luhn válido por azar)
            '"id": "4242424242424242"',                          # clave id: es un identificador
            '"hash_parametros": "sha256:5a9b4242424242424242c1"', # hex: el número va pegado a letras
            'event_id=4242424242424242',
            "ad_snapshot_url=https://x/?id=4242424242424242",
        ]
        for linea in casos:
            with self.subTest(linea=linea):
                self.assertIsNone(L._buscar_tarjeta(linea))

    def test_un_numero_largo_sin_prefijo_de_emisor_no_es_tarjeta(self) -> None:
        self.assertTrue(L._luhn_valido("1056023200924288") or True)   # irrelevante para el Luhn; importa el emisor
        self.assertFalse(L._prefijo_de_emisor_valido("1056023200924288"))
        self.assertFalse(L._prefijo_de_emisor_valido("4242424242424"[:12]))      # largo no válido para Visa

    def test_luhn_rechaza_secuencia_sin_digito_de_control_valido(self) -> None:
        self.assertIsNone(L._buscar_tarjeta("numero de referencia: 1234567890123"))


class PruebaReglaD(unittest.TestCase):
    """(d) prefijos de credencial (EAA, sk_, rk_live_, whsec_, cfut_) en todo el árbol."""

    def setUp(self) -> None:
        _sin_red(self)
        self.base = RAIZ_FIXTURES / "regla_d_prefijos_secreto"

    def test_verde_sin_hallazgos(self) -> None:
        hallazgos = L.regla_d_prefijos_de_secreto(self.base / "verde")
        self.assertEqual([], hallazgos)

    def test_rojo_detecta_prefijo_sk(self) -> None:
        hallazgos = L.regla_d_prefijos_de_secreto(self.base / "rojo")
        self.assertEqual(1, len(hallazgos))
        self.assertEqual("d", hallazgos[0].regla)
        self.assertIn("sk_", hallazgos[0].mensaje)
        self.assertNotIn("sk_live_51HqpruebaNoRealToken000111222", hallazgos[0].mensaje)


class PruebaMecanismosDeExcepcion(unittest.TestCase):
    """Los falsos positivos se justifican con el marcador en línea o con LISTA_BLANCA (ambos
    explícitos y comentados), nunca de forma silenciosa."""

    def setUp(self) -> None:
        _sin_red(self)

    def test_marcador_en_linea_suprime_el_hallazgo(self) -> None:
        base = RAIZ_FIXTURES / "regla_permiso_en_linea"
        self.assertEqual([], L.regla_a_float_o_division_en_dinero(base))

    def test_sin_marcador_el_mismo_patron_se_detecta(self) -> None:
        base = RAIZ_FIXTURES / "regla_a_float_dinero" / "rojo"
        self.assertTrue(L.regla_a_float_o_division_en_dinero(base))

    def test_lista_blanca_suprime_un_archivo_completo(self) -> None:
        base = RAIZ_FIXTURES / "regla_d_prefijos_secreto" / "rojo"
        original = L.LISTA_BLANCA["d"]
        L.LISTA_BLANCA["d"] = frozenset({"meta/config.py"})  # excepción puntual, solo esta prueba
        try:
            self.assertEqual([], L.regla_d_prefijos_de_secreto(base))
        finally:
            L.LISTA_BLANCA["d"] = original


class PruebaListaBlancaDeSimbolos(unittest.TestCase):
    """CT2-41 / D-05: ``decision/presupuesto.py`` puede tener en ``float`` sus tasas (CPC/CPM/CPA, fracciones),
    pero la excepción es por SÍMBOLO y por ARCHIVO: no abre el archivo entero ni el mismo nombre en otro sitio."""

    def setUp(self) -> None:
        _sin_red(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="lint-simbolos-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _escribir(self, ruta: str, codigo: str) -> None:
        destino = self.tmp / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(codigo, encoding="utf-8")

    def test_las_tasas_declaradas_de_presupuesto_quedan_exceptuadas(self) -> None:
        self._escribir("decision/presupuesto.py",
                       "cpc_minor: float = 0.31\n"
                       "def f(cpc_minor, cpm_minor, ctr, conv, cpa):\n"
                       "    return cpc_minor / conv, cpm_minor / (1000.0 * ctr), cpa / conv\n")
        self.assertEqual([], L.regla_a_float_o_division_en_dinero(self.tmp))

    def test_un_importe_real_del_mismo_archivo_se_sigue_detectando(self) -> None:
        self._escribir("decision/presupuesto.py",
                       "def f(cpc_minor, precio_minor, n):\n"
                       "    a = cpc_minor / n\n"
                       "    return a, float(precio_minor), precio_minor / n\n")
        hallazgos = L.regla_a_float_o_division_en_dinero(self.tmp)
        self.assertEqual(2, len(hallazgos))
        self.assertTrue(all("precio_minor" in h.mensaje for h in hallazgos))

    def test_el_mismo_simbolo_en_otro_archivo_se_sigue_detectando(self) -> None:
        for ruta in ("decision/otro.py", "engine/presupuesto.py", "meta/presupuesto.py"):
            self._escribir(ruta, "def f(cpc_minor, n):\n    return cpc_minor / n\n")
        rutas = sorted(h.archivo for h in L.regla_a_float_o_division_en_dinero(self.tmp))
        self.assertEqual(["decision/otro.py", "engine/presupuesto.py", "meta/presupuesto.py"], rutas)

    def test_la_lista_declarada_solo_nombra_simbolos_de_presupuesto_y_cada_uno_es_de_tasa(self) -> None:
        self.assertEqual({"decision/presupuesto.py"}, set(L.LISTA_BLANCA_SIMBOLOS["a"]))
        self.assertTrue(all(isinstance(v, frozenset) and v for v in L.LISTA_BLANCA_SIMBOLOS["a"].values()))
        for regla in ("b", "c", "d"):
            self.assertEqual({}, L.LISTA_BLANCA_SIMBOLOS[regla])

    def test_el_arbol_real_ya_no_marca_decision_presupuesto(self) -> None:
        base = Path(__file__).resolve().parents[2]
        if not (base / "decision" / "presupuesto.py").is_file():
            self.skipTest("sin decision/presupuesto.py en este árbol")
        archivos = {h.archivo for h in L.regla_a_float_o_division_en_dinero(base)}
        self.assertNotIn("decision/presupuesto.py", archivos)


class PruebaEjecutarYCli(unittest.TestCase):
    """``ejecutar`` agrega las reglas pedidas; la CLI respeta los códigos de salida de convenciones §8."""

    def setUp(self) -> None:
        _sin_red(self)

    def test_ejecutar_agrega_resumen_por_regla(self) -> None:
        informe = L.ejecutar(RAIZ_FIXTURES / "regla_a_float_dinero" / "rojo", reglas=["a"])
        self.assertFalse(informe.ok)
        self.assertEqual({"a": 3}, informe.resumen)

    def test_ejecutar_regla_desconocida_es_error_de_uso(self) -> None:
        with self.assertRaises(L.ErrorUso):
            L.ejecutar(RAIZ_FIXTURES, reglas=["z"])

    def test_cli_sale_0_en_arbol_limpio(self) -> None:
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = L.main(["--raiz", str(RAIZ_FIXTURES / "regla_b_literal_fijo" / "verde"), "--reglas", "a,b"])
        self.assertEqual(0, codigo)
        self.assertIn("TOTAL 0 hallazgo(s)", salida.getvalue())

    def test_cli_sale_3_con_hallazgos(self) -> None:
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = L.main(["--raiz", str(RAIZ_FIXTURES / "regla_b_literal_fijo" / "rojo"), "--reglas", "b", "--json"])
        self.assertEqual(3, codigo)
        self.assertIn('"ok":false', salida.getvalue())

    def test_cli_sale_2_con_raiz_inexistente(self) -> None:
        codigo = L.main(["--raiz", str(RAIZ_FIXTURES / "no-existe-esta-carpeta")])
        self.assertEqual(2, codigo)

    def test_cli_sale_2_con_regla_desconocida(self) -> None:
        codigo = L.main(["--raiz", str(RAIZ_FIXTURES), "--reglas", "a,z"])
        self.assertEqual(2, codigo)


if __name__ == "__main__":
    unittest.main()
