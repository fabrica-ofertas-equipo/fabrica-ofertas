"""Mutaciones sembrables de B0-11 sobre la landing de ``ofertas/_ejemplo`` (ola 0b-2, CT).

Contrato: la base pasa limpia el lint de publicación; cada mutación, aplicada a una COPIA temporal, dispara la regla que declara (y solo ella
más, como mucho, las colaterales declaradas); el sellado de la oferta (hashes) también detecta la alteración; el ejemplo real nunca se toca.

Comando: ``.venv/bin/python -m unittest tests.contratos.test_mutaciones_landing``
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import validar_esquemas as V
from tests.contratos import aplicar_mutacion_landing as A
from tests.contratos import lint_landing_referencia as L

RAIZ = Path(__file__).resolve().parents[2]
EJ = RAIZ / "ofertas" / "_ejemplo"
REGLAS = {"L1-LEGALES", "L1-RUTAS", "L1-ENLACE-INTERNO", "L1-ENLACE-EXTERNO", "L1-SCRIPT-EXTERNO", "L1-SCRIPT-INLINE", "L1-SCRIPT-NO-PERMITIDO",
          "L1-CONSENT-PIXEL", "L1-CONSENTIMIENTO-JS", "L1-TRACKING-PLATAFORMA", "L1-PRECIO", "L1-MONEDA", "L1-GARANTIA", "L1-SALUD", "L1-HTML-LANG",
          "L1-EJEMPLO-VISIBLE", "L1-EJEMPLO-COMENTARIO", "L1-CONTADORES", "L1-CASILLA-PREMARCADA"}


def hash_arbol(carpeta: Path) -> str:
    return V.hash_objeto({p.relative_to(carpeta).as_posix(): p.read_bytes().hex() for p in sorted(carpeta.rglob("*")) if p.is_file()})


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mutaciones-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


class TestCatalogo(unittest.TestCase):
    def test_son_ocho_con_los_campos_que_pide_el_encargo(self) -> None:
        ms = A.mutaciones()
        self.assertEqual([f"ML-0{k}" for k in range(1, 9)], [m["id"] for m in ms])
        for m in ms:
            for campo in ("id", "nombre", "descripcion", "parches", "regla_esperada", "reglas_colaterales", "check_d5"):
                self.assertIn(campo, m, m["id"])
            self.assertIn(m["regla_esperada"], REGLAS, m["id"])
            self.assertTrue(set(m["reglas_colaterales"]) <= REGLAS, m["id"])
            self.assertTrue(m["parches"] and all(p["op"] in A.cargar_catalogo()["operaciones"] for p in m["parches"]), m["id"])
        self.assertEqual(8, len({m["regla_esperada"] + m["nombre"] for m in ms}))

    def test_cubre_los_ocho_defectos_del_encargo(self) -> None:
        nombres = {m["nombre"] for m in A.mutaciones()}
        self.assertEqual({"legal_ausente", "ejemplo_visible", "script_externo", "precio_distinto", "salud_en_title", "pixel_antes_del_consentimiento",
                          "enlace_interno_roto", "enlace_externo_fuera_de_rutas"}, nombres)

    def test_complementarias_de_docs_06(self) -> None:
        self.assertEqual({"moneda_distinta", "garantia_distinta", "salud_en_tracking", "casilla_premarcada"},
                         {m["nombre"] for m in A.cargar_catalogo()["complementarias"]})

    def test_ids_unicos_y_catalogo_sin_datos_personales(self) -> None:
        ids = [m["id"] for m in A.mutaciones(True)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("@", A.CATALOGO.read_text(encoding="utf-8"))


class TestAplicacion(Base):
    def test_la_base_pasa_limpia(self) -> None:
        self.assertEqual([], L.lint(EJ))

    def test_cada_mutacion_dispara_su_regla(self) -> None:
        for m in A.mutaciones(True):
            with self.subTest(m["id"], regla=m["regla_esperada"]):
                copia = A.copiar_ejemplo(self.tmp, m["id"])
                tocados = A.aplicar(m["id"], copia)
                self.assertTrue(tocados)
                disparadas = L.reglas(L.lint(copia))
                self.assertIn(m["regla_esperada"], disparadas)
                self.assertLessEqual(disparadas, {m["regla_esperada"], *m["reglas_colaterales"]}, "regla inesperada")

    def test_el_sellado_tambien_detecta_la_mutacion(self) -> None:
        """Hashes de landing/tracking: alterar el sitio sin re-sellar rompe la oferta (X06/X03/X02), con o sin lint."""
        aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")
        for m in A.mutaciones(True):
            with self.subTest(m["id"]):
                carpeta = A.copiar_ejemplo(self.tmp / m["id"], "OF-202611-01")     # la carpeta lleva el id de la oferta (X01)
                A.aplicar(m["id"], carpeta)
                inf = V.validar_oferta(carpeta, limites=V.limites_de_prueba(), autonomia=aut, clave_firma=V.CLAVE_DE_PRUEBA)
                self.assertTrue({h.codigo for h in inf.errores} & {"X06_HASH_LANDING", "X03_HASH_QA", "X02_HASH_ETAPA"}, m["id"])

    def test_aplicar_es_determinista(self) -> None:
        for m in A.mutaciones(True):
            a, b = A.copiar_ejemplo(self.tmp, "a-" + m["id"]), A.copiar_ejemplo(self.tmp, "b-" + m["id"])
            A.aplicar(m["id"], a); A.aplicar(m["id"], b)
            self.assertEqual(hash_arbol(a), hash_arbol(b), m["id"])

    def test_la_mutacion_cambia_la_copia_y_no_el_ejemplo(self) -> None:
        antes = hash_arbol(EJ)
        for m in A.mutaciones(True):
            copia = A.copiar_ejemplo(self.tmp, "c-" + m["id"])
            A.aplicar(m["id"], copia)
            self.assertNotEqual(antes, hash_arbol(copia), m["id"])
        self.assertEqual(antes, hash_arbol(EJ))


class TestSoloCopiasTemporales(Base):
    def test_se_niega_sobre_el_ejemplo_real(self) -> None:
        antes = hash_arbol(EJ)
        for destino in (EJ, EJ / "05-landing", RAIZ / "ofertas", EJ / "05-landing" / "sitio"):
            with self.assertRaises(A.ErrorMutacion):
                A.aplicar("ML-04", destino)
        self.assertEqual(antes, hash_arbol(EJ))

    def test_se_niega_si_la_carpeta_no_es_una_copia_marcada(self) -> None:
        sin_marca = self.tmp / "sin-marca"
        shutil.copytree(EJ, sin_marca)
        with self.assertRaises(A.ErrorMutacion):
            A.aplicar("ML-04", sin_marca)
        self.assertEqual(hash_arbol(EJ), hash_arbol(sin_marca))

    def test_se_niega_si_la_marca_se_copia_dentro_del_ejemplo(self) -> None:
        with self.assertRaises(A.ErrorMutacion):
            A.copiar_ejemplo(EJ, "copia")
        self.assertFalse((EJ / "copia").exists())

    def test_el_ejemplo_real_no_lleva_la_marca(self) -> None:
        self.assertFalse((EJ / A.MARCA).exists())

    def test_mutacion_desconocida_y_deriva_del_ejemplo(self) -> None:
        copia = A.copiar_ejemplo(self.tmp)
        with self.assertRaises(A.ErrorMutacion):
            A.aplicar("ML-99", copia)
        (copia / "05-landing" / "sitio" / "index.html").write_text("<html></html>", encoding="utf-8")
        with self.assertRaises(A.ErrorMutacion):                    # el ancla ya no existe: falla en voz alta, no a medias
            A.aplicar("ML-04", copia)

    def test_ruta_fuera_de_la_copia_se_rechaza(self) -> None:
        copia = A.copiar_ejemplo(self.tmp)
        with self.assertRaises(A.ErrorMutacion):
            A._parche(copia.resolve(), {"op": "borrar", "archivo": "../../../etc/hosts"})


if __name__ == "__main__":
    unittest.main()
