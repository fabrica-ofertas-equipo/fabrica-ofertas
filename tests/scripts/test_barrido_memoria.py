"""Pruebas de scripts/modelado/barrido/memoria.py (B3): instantáneas inmutables, diff y entrantes_30d.

Sin red ni reloj real: `ahora` siempre se inyecta y cada prueba escribe en una raíz temporal (nunca en `empresa/`).
Fixtures en tests/fixtures/barrido/memoria/: dos barridos sintéticos con el formato «Páginas» de B2 (contrato §4),
sus etiquetas y un YAML de parámetros propio con la estructura de parametros_barrido.propuesta.yaml.

Escenario del par de fixtures (base 2026-10-07-a, actual 2026-11-06-a; entre ambos pasan exactamente 30 días):
  1001 crece (5→9) · 1002 decrece (8→3) · 1003 igual · 1004 desaparece · 1005 cambia de ES a MX ·
  1006 truncada · 2001 entrante real · 2002 «reaparecida» (anuncio de 70 días: ya existía) ·
  2003 entrante en ES y MX con un tema nuevo.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import tempfile
import unicodedata
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

import yaml

from scripts.modelado import puntaje_modelar as pm
from scripts.modelado.barrido import comun
from scripts.modelado.barrido import memoria as mem

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "barrido" / "memoria"
PARAMETROS_MODELADO = RAIZ / "tests" / "fixtures" / "modelado" / "parametros.yaml"
UTC = timezone.utc
T0 = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)          # «ahora» del barrido actual
CORRIDA_BASE = "2026-10-07-a"                               # 30 días exactos antes de T0
CORRIDA_ACTUAL = "2026-11-06-a"


def dias(n, segundos=0):
    return timedelta(days=n, seconds=segundos)


def leer(nombre):
    return json.loads((FIX / nombre).read_text(encoding="utf-8"))


def cargar_par():
    datos = yaml.safe_load((FIX / "parametros_memoria.yaml").read_text(encoding="utf-8"))
    return {k: v["valor"] for k, v in datos["grupos"]["descubrimiento"].items()}


def con_corrida(doc, corrida_id):
    nuevo = copy.deepcopy(doc)
    nuevo["corrida_id"] = corrida_id
    return nuevo


def pagina(pid, nombre="Página", paises=("ES",), anuncios=3, edad="12.5", edad_max="20", truncada=False, qids=("q1",)):
    return {"page_id": pid, "page_name": nombre, "paises": list(paises), "monedas": ["USD"],
            "anuncios_activos_en_muestra": anuncios, "edad_oferta_dias": edad, "edad_max_dias": edad_max,
            "conceptos_unicos": 1, "titulos": ["t"], "qids": list(qids), "muestra_truncada": truncada,
            "exportador": {"señal": False, "moneda": "USD", "pais_anuncio": paises[0], "motivo": "x"}}


def doc_paginas(corrida_id, *paginas, **extra):
    doc = {"schema_version": "1.0.0", "corrida_id": corrida_id, "generado_en": "2026-11-06T11:58:00Z",
           "paginas": list(paginas), "advertencias": []}
    doc.update(extra)
    return doc


def recorrer(valor):
    """Todos los valores hoja de una estructura JSON."""
    if isinstance(valor, dict):
        for v in valor.values():
            yield from recorrer(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from recorrer(v)
    else:
        yield valor


def sin_float(prueba, valor):
    for hoja in recorrer(valor):
        prueba.assertNotIsInstance(hoja, (float, Decimal))


class Base(unittest.TestCase):
    def setUp(self):
        parche = mock.patch("socket.socket", side_effect=AssertionError("las pruebas no usan red"))
        parche.start()
        self.addCleanup(parche.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        self.par = cargar_par()
        self.base_doc = leer("paginas_base.json")
        self.actual_doc = leer("paginas_actual.json")
        self.et_base = leer("etiquetas_base.json")
        self.et_actual = leer("etiquetas_actual.json")

    @property
    def carpeta(self):
        return self.raiz / "empresa" / "barrido" / "memoria"

    def guardar(self, doc, corrida_id, ahora, **kw):
        return mem.guardar_instantanea(con_corrida(doc, corrida_id), corrida_id, raiz=self.raiz, ahora=ahora, **kw)

    def guardar_base(self, antes=30, **kw):
        """Guarda el barrido base `antes` días antes de T0 (con etiquetas y cobertura ES+MX)."""
        kw.setdefault("etiquetas", self.et_base)
        kw.setdefault("paises_consultados", ["ES", "MX"])
        return self.guardar(self.base_doc, CORRIDA_BASE, T0 - dias(antes), **kw)

    def actual(self, **kw):
        kw.setdefault("etiquetas", self.et_actual)
        kw.setdefault("paises_consultados", ["ES", "MX"])
        return mem.construir_instantanea(self.actual_doc, CORRIDA_ACTUAL, ahora=T0, **kw)

    def previas(self):
        return mem.cargar_previas(self.raiz)

    def escenario(self, antes=30):
        self.guardar_base(antes)
        return self.actual(), self.previas()

    def entrantes(self, clave, actual, previas, **kw):
        return mem.entrantes_30d(clave, actual, previas, ahora=T0, par=self.par, **kw)

    def detalle(self, clave, actual, previas, **kw):
        return mem.entrantes_detalle(clave, actual, previas, ahora=T0, par=self.par, **kw)

    def diff(self, actual, previas, **kw):
        return mem.diff(actual, previas, par=self.par, ahora=T0, **kw)

    def escribir_json(self, ruta, doc):
        ruta.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def alterar_archivo(self, corrida_id, cambio):
        ruta = self.carpeta / f"{corrida_id}.json"
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        cambio(doc)
        self.escribir_json(ruta, doc)


# ---------------------------------------------------------------------------
# Guardado
# ---------------------------------------------------------------------------

class TestGuardar(Base):
    def test_guarda_archivo_inmutable_e_indice(self):
        ruta = self.guardar_base()
        self.assertEqual(ruta, self.carpeta / f"{CORRIDA_BASE}.json")
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], "1.0.0")
        self.assertEqual(doc["corrida_id"], CORRIDA_BASE)
        self.assertEqual(doc["ts"], "2026-10-07T12:00:00Z")
        self.assertEqual(doc["n_paginas"], 6)
        self.assertEqual(doc["n_consultas"], 1)   # unión de qids de las páginas del fixture
        self.assertEqual(doc["n_consultas_origen"], "qids")
        self.assertEqual(doc["paises_consultados"], ["ES", "MX"])
        self.assertEqual([p["page_id"] for p in doc["paginas"]], ["1001", "1002", "1003", "1004", "1005", "1006"])
        self.assertEqual(doc["paginas"][0]["tema_slug"], "yoga-pilates")
        self.assertEqual(doc["paginas"][0]["anuncios_activos_en_muestra"], 5)
        lineas = (self.carpeta / "indice.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lineas), 1)
        entrada = json.loads(lineas[0])
        self.assertEqual(set(entrada), {"corrida_id", "ts", "n_paginas", "n_consultas", "hash"})
        self.assertEqual(entrada["corrida_id"], CORRIDA_BASE)
        self.assertEqual(entrada["n_paginas"], 6)
        self.assertEqual(entrada["hash"], doc["hash"])

    def test_el_hash_es_sha256_del_contenido_canonico(self):
        ruta = self.guardar_base()
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        sin = {k: v for k, v in doc.items() if k != "hash"}
        canonico = json.dumps(sin, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        esperado = "sha256:" + hashlib.sha256(unicodedata.normalize("NFC", canonico).encode("utf-8")).hexdigest()
        self.assertEqual(doc["hash"], esperado)

    def test_doble_guardado_de_la_misma_corrida_es_ErrorUso_y_no_toca_nada(self):
        ruta = self.guardar_base()
        antes = ruta.read_bytes()
        indice_antes = (self.carpeta / "indice.jsonl").read_bytes()
        otro = copy.deepcopy(self.base_doc)
        otro["paginas"][0]["anuncios_activos_en_muestra"] = 99
        with self.assertRaises(mem.ErrorUso):
            mem.guardar_instantanea(otro, CORRIDA_BASE, raiz=self.raiz, ahora=T0)
        self.assertEqual(ruta.read_bytes(), antes)
        self.assertEqual((self.carpeta / "indice.jsonl").read_bytes(), indice_antes)

    def test_archivo_existente_sin_indice_tampoco_se_sobrescribe(self):
        self.carpeta.mkdir(parents=True)
        (self.carpeta / f"{CORRIDA_BASE}.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(mem.ErrorUso):
            self.guardar_base()
        self.assertEqual((self.carpeta / f"{CORRIDA_BASE}.json").read_text(encoding="utf-8"), "{}")
        self.assertFalse((self.carpeta / "indice.jsonl").exists())

    def test_indice_que_ya_registra_la_corrida_es_ErrorUso(self):
        ruta = self.guardar_base()
        ruta.unlink()
        with self.assertRaises(mem.ErrorUso):
            self.guardar_base()

    def test_corrida_id_invalido_es_ErrorUso(self):
        for malo in ("../x", "2026-11-06", "2026-13-01-a", "2026-11-06-A", "", None, 5):
            with self.subTest(corrida=malo), self.assertRaises(mem.ErrorUso):
                mem.guardar_instantanea(self.base_doc, malo, raiz=self.raiz, ahora=T0)
        self.assertFalse(self.carpeta.exists())

    def test_el_documento_de_otra_corrida_es_ErrorValidacion(self):
        with self.assertRaises(mem.ErrorValidacion):
            mem.guardar_instantanea(self.base_doc, "2026-10-08-a", raiz=self.raiz, ahora=T0)
        self.assertFalse(self.carpeta.exists())

    def test_reloj_inyectado_define_ts(self):
        ruta = self.guardar(self.base_doc, CORRIDA_BASE, datetime(2020, 1, 2, 3, 4, 5, 999999, tzinfo=UTC))
        self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["ts"], "2020-01-02T03:04:05Z")

    def test_ahora_con_otra_zona_se_guarda_en_utc(self):
        zona = timezone(timedelta(hours=-5))
        ruta = self.guardar(self.base_doc, CORRIDA_BASE, datetime(2026, 10, 7, 7, 0, 0, tzinfo=zona))
        self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["ts"], "2026-10-07T12:00:00Z")

    def test_ahora_sin_zona_es_ErrorUso(self):
        with self.assertRaises(mem.ErrorUso):
            mem.guardar_instantanea(self.base_doc, CORRIDA_BASE, raiz=self.raiz, ahora=datetime(2026, 10, 7, 12, 0, 0))
        with self.assertRaises(mem.ErrorUso):
            mem.guardar_instantanea(self.base_doc, CORRIDA_BASE, raiz=self.raiz, ahora="2026-10-07T12:00:00Z")

    def test_el_orden_de_entrada_no_cambia_el_resultado(self):
        revuelto = copy.deepcopy(self.base_doc)
        random.Random(7).shuffle(revuelto["paginas"])
        a = mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0)
        b = mem.construir_instantanea(revuelto, CORRIDA_BASE, ahora=T0)
        self.assertEqual(a, b)
        self.assertEqual(a["hash"], b["hash"])

    def test_determinismo_bytes_identicos_en_dos_raices(self):
        otra = tempfile.TemporaryDirectory()
        self.addCleanup(otra.cleanup)
        r1 = self.guardar_base()
        r2 = mem.guardar_instantanea(self.base_doc, CORRIDA_BASE, raiz=Path(otra.name), ahora=T0 - dias(30),
                                     etiquetas=self.et_base, paises_consultados=["ES", "MX"])
        self.assertEqual(r1.read_bytes(), r2.read_bytes())
        self.assertEqual((self.carpeta / "indice.jsonl").read_bytes(),
                         (Path(otra.name) / "empresa" / "barrido" / "memoria" / "indice.jsonl").read_bytes())

    def test_no_se_persiste_ningun_float(self):
        ruta = self.guardar_base()

        def rechazar(texto):
            raise AssertionError(f"float en lo persistido: {texto}")

        doc = json.loads(ruta.read_text(encoding="utf-8"), parse_float=rechazar)
        sin_float(self, doc)
        for hoja in recorrer(doc["paginas"]):
            self.assertNotIsInstance(hoja, float)
        self.assertIsInstance(doc["paginas"][0]["edad_oferta_dias"], str)
        indice = json.loads((self.carpeta / "indice.jsonl").read_text(encoding="utf-8").splitlines()[0],
                            parse_float=rechazar)
        sin_float(self, indice)

    def test_decimales_se_guardan_canonicos(self):
        doc = doc_paginas(CORRIDA_BASE, pagina("1", edad="14.90", edad_max=Decimal("20.0"), anuncios=2))
        snap = mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0)
        self.assertEqual(snap["paginas"][0]["edad_oferta_dias"], "14.9")
        self.assertEqual(snap["paginas"][0]["edad_max_dias"], "20")

    def test_float_en_la_entrada_es_ErrorValidacion(self):
        for campo, valor in (("anuncios_activos_en_muestra", 5.0), ("edad_oferta_dias", 1.5), ("edad_max_dias", 2.5)):
            doc = doc_paginas(CORRIDA_BASE, pagina("1"))
            doc["paginas"][0][campo] = valor
            with self.subTest(campo=campo), self.assertRaises(mem.ErrorValidacion):
                mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0)

    def test_paginas_fuera_de_contrato_son_ErrorValidacion(self):
        def sin(campo):
            return lambda p: p.pop(campo)

        def poner(campo, valor):
            return lambda p: p.__setitem__(campo, valor)

        casos = {
            "falta page_name": sin("page_name"), "falta paises": sin("paises"),
            "falta edad_max": sin("edad_max_dias"), "falta truncada": sin("muestra_truncada"),
            "page_id con letras": poner("page_id", "12a"), "page_id vacío": poner("page_id", ""),
            "page_id None": poner("page_id", None), "pais en minúscula": poner("paises", ["es"]),
            "paises vacío": poner("paises", []), "paises repetidos": poner("paises", ["ES", "ES"]),
            "anuncios negativo": poner("anuncios_activos_en_muestra", -1),
            "anuncios bool": poner("anuncios_activos_en_muestra", True),
            "anuncios texto": poner("anuncios_activos_en_muestra", "3"),
            "truncada no bool": poner("muestra_truncada", "si"), "edad negativa": poner("edad_oferta_dias", "-1"),
            "edad basura": poner("edad_oferta_dias", "abc"), "edad NaN": poner("edad_max_dias", "NaN"),
            "nombre numérico": poner("page_name", 5),
        }
        for nombre, cambio in casos.items():
            doc = doc_paginas(CORRIDA_BASE, pagina("1"))
            cambio(doc["paginas"][0])
            with self.subTest(caso=nombre), self.assertRaises(mem.ErrorValidacion):
                mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0)

    def test_page_id_repetido_y_documento_roto_son_ErrorValidacion(self):
        with self.assertRaises(mem.ErrorValidacion):
            mem.construir_instantanea(doc_paginas(CORRIDA_BASE, pagina("1"), pagina("1")), CORRIDA_BASE, ahora=T0)
        for roto in (None, [], {"corrida_id": CORRIDA_BASE}, {"corrida_id": CORRIDA_BASE, "paginas": "x"},
                     doc_paginas(CORRIDA_BASE, "no-es-objeto")):
            with self.subTest(roto=roto), self.assertRaises(mem.ErrorValidacion):
                mem.construir_instantanea(roto, CORRIDA_BASE, ahora=T0)

    def test_page_id_entero_se_guarda_como_cadena(self):
        doc = doc_paginas(CORRIDA_BASE, pagina(1431294770063492))
        snap = mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0)
        self.assertEqual(snap["paginas"][0]["page_id"], "1431294770063492")

    def test_barrido_vacio_es_valido(self):
        snap = mem.construir_instantanea(doc_paginas(CORRIDA_BASE), CORRIDA_BASE, ahora=T0)
        self.assertEqual(snap["n_paginas"], 0)
        self.assertEqual(snap["n_consultas"], 0)

    def test_n_consultas_declarada_derivada_o_error(self):
        sin_qids = doc_paginas(CORRIDA_BASE, pagina("1"))
        del sin_qids["paginas"][0]["qids"]
        with self.assertRaises(mem.ErrorValidacion):   # no hay de dónde sacarla: no se inventa
            mem.construir_instantanea(sin_qids, CORRIDA_BASE, ahora=T0)
        snap = mem.construir_instantanea(sin_qids, CORRIDA_BASE, ahora=T0, n_consultas=40)
        self.assertEqual((snap["n_consultas"], snap["n_consultas_origen"]), (40, "declarado"))
        en_doc = copy.deepcopy(sin_qids)
        en_doc["n_consultas"] = 12
        self.assertEqual(mem.construir_instantanea(en_doc, CORRIDA_BASE, ahora=T0)["n_consultas"], 12)
        with self.assertRaises(mem.ErrorValidacion):   # el argumento contradice al documento
            mem.construir_instantanea(en_doc, CORRIDA_BASE, ahora=T0, n_consultas=13)
        derivada = doc_paginas(CORRIDA_BASE, pagina("1", qids=("a", "b")), pagina("2", qids=("b", "c")))
        snap = mem.construir_instantanea(derivada, CORRIDA_BASE, ahora=T0)
        self.assertEqual((snap["n_consultas"], snap["n_consultas_origen"]), (3, "qids"))
        with self.assertRaises(mem.ErrorValidacion):   # menos consultas que las que citan las páginas
            mem.construir_instantanea(derivada, CORRIDA_BASE, ahora=T0, n_consultas=2)
        for malo in (-1, True, 2.5, "3"):
            with self.subTest(n=malo), self.assertRaises(mem.ErrorValidacion):
                mem.construir_instantanea(derivada, CORRIDA_BASE, ahora=T0, n_consultas=malo)

    def test_paises_consultados(self):
        doc = doc_paginas(CORRIDA_BASE, pagina("1", paises=("MX", "ES")))
        snap = mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0, paises_consultados=["MX", "ES", "BR"])
        self.assertEqual(snap["paises_consultados"], ["BR", "ES", "MX"])
        self.assertEqual(snap["paginas"][0]["paises"], ["ES", "MX"])
        self.assertIsNone(mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0)["paises_consultados"])
        for malo in (["ES"], [], ["es", "mx"], ["ES", "ES", "MX"]):   # ["ES"] deja fuera a MX
            with self.subTest(paises=malo), self.assertRaises(mem.ErrorValidacion):
                mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0, paises_consultados=malo)

    def test_etiquetas(self):
        snap = mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0,
                                         etiquetas={**self.et_base, "999999": "tema-ajeno"})
        temas = {p["page_id"]: p["tema_slug"] for p in snap["paginas"]}
        self.assertEqual(temas, self.et_base)             # la clave ajena se ignora
        sin = mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0)
        self.assertTrue(all(p["tema_slug"] is None for p in sin["paginas"]))
        propia = doc_paginas(CORRIDA_BASE, pagina("1"), pagina("2"))
        propia["paginas"][0]["tema_slug"] = "ceramica-fria"
        snap = mem.construir_instantanea(propia, CORRIDA_BASE, ahora=T0, etiquetas={"2": "yoga-pilates"})
        self.assertEqual([p["tema_slug"] for p in snap["paginas"]], ["ceramica-fria", "yoga-pilates"])
        for malo in ("Yoga", "yoga pilates", "yoga_pilates", "-yoga", "2026", "", None, 5, "yóga"):
            with self.subTest(slug=malo), self.assertRaises(mem.ErrorValidacion):
                mem.construir_instantanea(doc_paginas(CORRIDA_BASE, pagina("1")), CORRIDA_BASE, ahora=T0,
                                          etiquetas={"1": malo})
        with self.assertRaises(mem.ErrorUso):
            mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0, etiquetas=["x"])

    def test_nombre_de_pagina_es_dato_no_confiable_y_se_sanea(self):
        sucio = "Ana\u0000 \n\t  Martin \ud83d <script>alert(1)</script>"
        doc = doc_paginas(CORRIDA_BASE, pagina("1", nombre=sucio), pagina("2", nombre=None))
        ruta = mem.guardar_instantanea(doc, CORRIDA_BASE, raiz=self.raiz, ahora=T0)
        paginas = json.loads(ruta.read_text(encoding="utf-8"))["paginas"]
        self.assertEqual(paginas[0]["page_name"], "Ana Martin ? <script>alert(1)</script>")  # texto, jamás se interpreta
        self.assertIsNone(paginas[1]["page_name"])
        mem.cargar_instantanea(CORRIDA_BASE, self.raiz)   # y sigue verificándose

    def test_caracteres_de_formato_unicode_se_tratan_como_controles(self):
        # M4 (revisión de seguridad): bidi (Cf) y joiners no pueden disfrazar el orden de lectura del nombre
        casos = {
            "Atril\u202egpj.exe": "Atril gpj.exe",                    # U+202E RIGHT-TO-LEFT OVERRIDE
            "A\u2066B\u2069C": "A B C",                              # U+2066 LRI y U+2069 PDI
            "a\u200db\u200cc\u200bd": "a b c d",                    # joiners y ancho cero
            "\ufeffNombre\u00adlargo": "Nombre largo",               # BOM y guion blando
            "x\ue000y": "x y",                                       # uso privado (Co)
            "ctl\u0000\u0085z": "ctl z",                            # los Cc siguen igual
            "\u202e\u2066": "",                                     # solo formato: queda vacío, no se inventa nada
        }
        for sucio, esperado in casos.items():
            doc = doc_paginas(CORRIDA_BASE, pagina("1", nombre=sucio))
            with self.subTest(sucio=sucio):
                snap = mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0)
                self.assertEqual(snap["paginas"][0]["page_name"], esperado)
                for c in snap["paginas"][0]["page_name"]:
                    self.assertNotEqual(unicodedata.category(c)[0], "C")

    def test_snapshot_ya_guardado_con_formato_en_el_nombre_sigue_verificando(self):
        # una instantánea escrita antes de la limpieza (nombre con U+202E) conserva su hash: la limpieza solo
        # actúa sobre la copia de trabajo, nunca sobre lo que se hashea
        doc = doc_paginas(CORRIDA_BASE, pagina("1", nombre="limpio"))
        snap = mem.construir_instantanea(doc, CORRIDA_BASE, ahora=T0)
        snap["paginas"][0]["page_name"] = "Atril\u202egpj.exe \u2066x"
        snap["hash"] = mem._hash_contenido({k: v for k, v in snap.items() if k != "hash"})
        self.carpeta.mkdir(parents=True)
        self.escribir_json(self.carpeta / f"{CORRIDA_BASE}.json", snap)
        comun.anexar_jsonl(self.carpeta / "indice.jsonl", {
            "corrida_id": CORRIDA_BASE, "ts": snap["ts"], "n_paginas": 1, "n_consultas": snap["n_consultas"],
            "hash": snap["hash"]})
        self.assertEqual(mem.verificar_integridad(self.raiz), [])
        cargada = mem.cargar_instantanea(CORRIDA_BASE, self.raiz)
        self.assertEqual(cargada["hash"], snap["hash"])
        self.assertEqual(cargada["paginas"][0]["page_name"], "Atril\u202egpj.exe \u2066x")   # lo guardado no se toca
        foto = mem._foto_de_instantanea(cargada, "x")
        self.assertEqual(foto["paginas"]["1"]["page_name"], "Atril gpj.exe x")                  # lo que se usa, limpio

    def test_solo_escribe_dentro_de_su_carpeta(self):
        self.guardar_base()
        escritos = sorted(p.relative_to(self.raiz).as_posix() for p in self.raiz.rglob("*") if p.is_file())
        self.assertEqual(escritos, [f"empresa/barrido/memoria/{CORRIDA_BASE}.json", "empresa/barrido/memoria/indice.jsonl"])

    def test_indice_danado_detiene_el_guardado(self):
        self.guardar_base()
        with (self.carpeta / "indice.jsonl").open("a", encoding="utf-8") as f:
            f.write("esto no es json\n")
        with self.assertRaises(mem.ErrorValidacion):
            self.guardar(self.base_doc, "2026-10-08-a", T0)
        self.assertFalse((self.carpeta / "2026-10-08-a.json").exists())


# ---------------------------------------------------------------------------
# Listado, carga e integridad
# ---------------------------------------------------------------------------

class TestListarYVerificar(Base):
    def test_sin_memoria_todo_vacio(self):
        self.assertEqual(mem.listar_instantaneas(self.raiz), [])
        self.assertEqual(mem.verificar_integridad(self.raiz), [])
        self.assertEqual(mem.cargar_previas(self.raiz), [])

    def test_listar_ordena_por_ts_y_luego_corrida(self):
        self.guardar(self.base_doc, "2026-10-20-a", T0 - dias(10))
        self.guardar(self.base_doc, "2026-09-01-a", T0 - dias(60))
        self.guardar(self.base_doc, "2026-10-05-b", T0 - dias(30))
        self.guardar(self.base_doc, "2026-10-05-a", T0 - dias(30))
        lista = mem.listar_instantaneas(self.raiz)
        self.assertEqual([e["corrida_id"] for e in lista], ["2026-09-01-a", "2026-10-05-a", "2026-10-05-b", "2026-10-20-a"])
        self.assertEqual(set(lista[0]), {"corrida_id", "ts", "n_paginas", "n_consultas", "hash"})

    def test_integra_si_nada_fue_tocado(self):
        self.guardar_base()
        self.guardar(self.base_doc, "2026-10-20-a", T0 - dias(10))
        self.assertEqual(mem.verificar_integridad(self.raiz), [])

    def test_hash_alterado_se_detecta(self):
        self.guardar_base()
        self.alterar_archivo(CORRIDA_BASE, lambda d: d["paginas"][0].__setitem__("anuncios_activos_en_muestra", 6))
        problemas = mem.verificar_integridad(self.raiz)
        self.assertEqual([(p["tipo"], p["corrida_id"]) for p in problemas], [("hash_distinto", CORRIDA_BASE)])

    def test_hash_del_indice_distinto_al_del_archivo(self):
        self.guardar_base()
        indice = self.carpeta / "indice.jsonl"
        entrada = json.loads(indice.read_text(encoding="utf-8"))
        entrada["hash"] = "sha256:" + "0" * 64
        indice.write_text(json.dumps(entrada) + "\n", encoding="utf-8")
        self.assertEqual([p["tipo"] for p in mem.verificar_integridad(self.raiz)], ["hash_distinto"])

    def test_indice_inconsistente_con_el_archivo(self):
        self.guardar_base()
        indice = self.carpeta / "indice.jsonl"
        entrada = json.loads(indice.read_text(encoding="utf-8"))
        entrada["n_paginas"] = 99
        indice.write_text(json.dumps(entrada) + "\n", encoding="utf-8")
        self.assertEqual([p["tipo"] for p in mem.verificar_integridad(self.raiz)], ["indice_inconsistente"])

    def test_indice_sin_archivo(self):
        ruta = self.guardar_base()
        ruta.unlink()
        problemas = mem.verificar_integridad(self.raiz)
        self.assertEqual([(p["tipo"], p["corrida_id"]) for p in problemas], [("indice_sin_archivo", CORRIDA_BASE)])

    def test_archivo_sin_indice(self):
        self.guardar_base()
        copia = self.carpeta / "2026-10-08-a.json"
        copia.write_bytes((self.carpeta / f"{CORRIDA_BASE}.json").read_bytes())
        problemas = mem.verificar_integridad(self.raiz)
        self.assertEqual([(p["tipo"], p["corrida_id"]) for p in problemas], [("archivo_sin_indice", "2026-10-08-a")])

    def test_archivo_ilegible_o_con_estructura_rota(self):
        self.guardar_base()
        (self.carpeta / f"{CORRIDA_BASE}.json").write_text("{no es json", encoding="utf-8")
        self.assertEqual([p["tipo"] for p in mem.verificar_integridad(self.raiz)], ["archivo_invalido"])
        (self.carpeta / f"{CORRIDA_BASE}.json").write_text('{"corrida_id": "x"}', encoding="utf-8")
        self.assertEqual([p["tipo"] for p in mem.verificar_integridad(self.raiz)], ["archivo_invalido"])

    def test_archivo_con_float_es_invalido(self):
        self.guardar_base()
        self.alterar_archivo(CORRIDA_BASE, lambda d: d["paginas"][0].__setitem__("anuncios_activos_en_muestra", 5.0))
        self.assertEqual([p["tipo"] for p in mem.verificar_integridad(self.raiz)], ["archivo_invalido"])

    def test_indice_danado(self):
        self.guardar_base()
        indice = self.carpeta / "indice.jsonl"
        indice.write_text(indice.read_text(encoding="utf-8") + "{roto\n", encoding="utf-8")
        with self.assertRaises(mem.ErrorValidacion):
            mem.listar_instantaneas(self.raiz)
        self.assertEqual([p["tipo"] for p in mem.verificar_integridad(self.raiz)], ["indice_invalido"])

    def test_indice_con_corrida_repetida_o_campos_raros(self):
        self.guardar_base()
        indice = self.carpeta / "indice.jsonl"
        linea = indice.read_text(encoding="utf-8")
        indice.write_text(linea + linea, encoding="utf-8")
        with self.assertRaises(mem.ErrorValidacion):
            mem.listar_instantaneas(self.raiz)
        entrada = json.loads(linea)
        for cambio in ({"n_paginas": 1.5}, {"n_paginas": True}, {"ts": "ayer"}, {"corrida_id": "../x"},
                       {"hash": "sha256:abc"}, {"extra": 1}):
            malo = {**entrada, **cambio}
            indice.write_text(json.dumps(malo) + "\n", encoding="utf-8")
            with self.subTest(cambio=cambio), self.assertRaises(mem.ErrorValidacion):
                mem.listar_instantaneas(self.raiz)

    def test_verificar_no_modifica_nada(self):
        self.guardar_base()
        self.alterar_archivo(CORRIDA_BASE, lambda d: d.__setitem__("n_consultas", 7))
        antes = {p: p.read_bytes() for p in self.carpeta.iterdir()}
        mem.verificar_integridad(self.raiz)
        self.assertEqual(antes, {p: p.read_bytes() for p in self.carpeta.iterdir()})

    def test_orden_de_problemas_es_determinista(self):
        for cid in ("2026-10-02-a", "2026-10-01-a"):
            self.guardar(self.base_doc, cid, T0 - dias(30))
            self.alterar_archivo(cid, lambda d: d.__setitem__("n_consultas", 9))
        problemas = mem.verificar_integridad(self.raiz)
        self.assertEqual([p["corrida_id"] for p in problemas], ["2026-10-01-a", "2026-10-02-a"])
        self.assertEqual(problemas, mem.verificar_integridad(self.raiz))


class TestCargar(Base):
    def test_cargar_devuelve_lo_guardado(self):
        self.guardar_base()
        esperada = mem.construir_instantanea(con_corrida(self.base_doc, CORRIDA_BASE), CORRIDA_BASE,
                                             ahora=T0 - dias(30), etiquetas=self.et_base,
                                             paises_consultados=["ES", "MX"])
        self.assertEqual(mem.cargar_instantanea(CORRIDA_BASE, self.raiz), esperada)

    def test_no_existe_es_ErrorUso(self):
        with self.assertRaises(mem.ErrorUso):
            mem.cargar_instantanea("2026-10-07-a", self.raiz)

    def test_corrupta_es_ErrorValidacion_y_no_se_devuelve(self):
        self.guardar_base()
        self.alterar_archivo(CORRIDA_BASE, lambda d: d["paginas"][1].__setitem__("anuncios_activos_en_muestra", 80))
        with self.assertRaises(mem.ErrorValidacion) as ctx:
            mem.cargar_instantanea(CORRIDA_BASE, self.raiz)
        self.assertIn("hash", str(ctx.exception))

    def test_archivo_y_hash_reescritos_a_la_vez_los_atrapa_el_indice(self):
        self.guardar_base()

        def cambio(doc):
            doc["paginas"][0]["anuncios_activos_en_muestra"] = 77
            doc["hash"] = mem._hash_contenido({k: v for k, v in doc.items() if k != "hash"})

        self.alterar_archivo(CORRIDA_BASE, cambio)
        with self.assertRaises(mem.ErrorValidacion):
            mem.cargar_instantanea(CORRIDA_BASE, self.raiz)

    def test_archivo_sin_indice_no_se_usa(self):
        self.guardar_base()
        (self.carpeta / "indice.jsonl").write_text("", encoding="utf-8")
        with self.assertRaises(mem.ErrorValidacion):
            mem.cargar_instantanea(CORRIDA_BASE, self.raiz)

    def test_cargar_previas_ordena_y_excluye(self):
        self.guardar(self.base_doc, "2026-10-20-a", T0 - dias(10))
        self.guardar(self.base_doc, "2026-09-01-a", T0 - dias(60))
        self.assertEqual([d["corrida_id"] for d in mem.cargar_previas(self.raiz)], ["2026-09-01-a", "2026-10-20-a"])
        self.assertEqual([d["corrida_id"] for d in mem.cargar_previas(self.raiz, excluir="2026-10-20-a")],
                         ["2026-09-01-a"])

    def test_una_corrupta_detiene_cargar_previas(self):
        self.guardar(self.base_doc, "2026-10-20-a", T0 - dias(10))
        self.guardar_base()
        self.alterar_archivo("2026-10-20-a", lambda d: d.__setitem__("n_consultas", 5))
        with self.assertRaises(mem.ErrorValidacion):
            mem.cargar_previas(self.raiz)


# ---------------------------------------------------------------------------
# entrantes_30d
# ---------------------------------------------------------------------------

class TestEntrantesBase(Base):
    """Cuándo hay base y cuándo `None` (jamás 0)."""

    def test_primera_corrida_todo_none_y_sin_base(self):
        actual = self.actual()
        for clave in ("yoga-pilates", "atlas-visual-salud", "2001", "1001"):
            for pais in (None, "ES", "MX"):
                with self.subTest(clave=clave, pais=pais):
                    self.assertIsNone(self.entrantes(clave, actual, [], pais=pais))
        d = self.detalle("yoga-pilates", actual, [])
        self.assertEqual((d["estado"], d["motivo"], d["valor"]), ("sin_base", "primera_corrida", None))
        self.assertIsNone(d["base"]["corrida_id"])

    def test_previa_demasiado_reciente_es_none(self):
        for antes in (1, 7, 12, 24):
            self.guardar(self.base_doc, f"{(T0 - dias(antes)).strftime('%Y-%m-%d')}-a", T0 - dias(antes))
        actual = self.actual()
        d = self.detalle("yoga-pilates", actual, self.previas())
        self.assertIsNone(d["valor"])
        self.assertEqual((d["estado"], d["motivo"]), ("sin_base", "base_demasiado_reciente"))
        self.assertEqual(d["base"]["n_muy_recientes"], 4)

    def test_borde_exacto_de_memoria_ventana_min_dias_cumple(self):
        self.guardar_base(antes=25)
        actual = self.actual()
        valor = self.entrantes("yoga-pilates", actual, self.previas())
        self.assertIsNotNone(valor)
        self.assertEqual(self.detalle("yoga-pilates", actual, self.previas())["base"]["antiguedad_dias"], "25.0000")

    def test_un_segundo_antes_del_borde_no_cumple(self):
        self.guardar(self.base_doc, CORRIDA_BASE, T0 - dias(25) + timedelta(seconds=1))
        self.assertIsNone(self.entrantes("yoga-pilates", self.actual(), self.previas()))

    def test_un_segundo_despues_del_borde_cumple(self):
        self.guardar(self.base_doc, CORRIDA_BASE, T0 - dias(25, 1))
        self.assertIsNotNone(self.entrantes("yoga-pilates", self.actual(), self.previas()))

    def test_el_minimo_sale_del_parametro_no_del_codigo(self):
        self.guardar_base(antes=10)
        actual = self.actual()
        self.assertIsNone(self.entrantes("yoga-pilates", actual, self.previas()))
        self.par["memoria_ventana_min_dias"] = 10
        self.assertIsNotNone(self.entrantes("yoga-pilates", actual, self.previas()))
        self.par["memoria_ventana_min_dias"] = "10.5"      # decimal exacto en cadena
        self.assertIsNone(self.entrantes("yoga-pilates", actual, self.previas()))

    def test_borde_del_maximo_opcional(self):
        self.guardar_base(antes=60)
        actual = self.actual()
        self.assertIsNotNone(self.entrantes("yoga-pilates", actual, self.previas()))      # == máximo: cumple
        self.par["memoria_ventana_max_dias"] = 59
        d = self.detalle("yoga-pilates", actual, self.previas())
        self.assertIsNone(d["valor"])
        self.assertEqual(d["motivo"], "base_vencida")

    def test_sin_maximo_la_base_vieja_se_usa_pero_se_advierte(self):
        del self.par["memoria_ventana_max_dias"]
        self.guardar_base(antes=200)
        actual = self.actual()
        d = self.detalle("yoga-pilates", actual, self.previas())
        self.assertIsNotNone(d["valor"])
        self.assertTrue(d["base"]["ventana_excedida"])
        self.assertTrue(any("ventana más larga" in a for a in d["advertencias"]))
        self.assertTrue(any("memoria_ventana_max_dias" in a for a in self.diff(actual, self.previas())["advertencias"]))

    def test_varias_previas_usa_la_mas_cercana_a_30_dias_que_cumpla(self):
        edades = {"2026-10-27-a": 10, "2026-10-16-a": 21, "2026-10-09-a": 28, "2026-09-22-a": 45, "2026-08-08-a": 90}
        for cid, antes in edades.items():
            self.guardar(self.base_doc, cid, T0 - dias(antes))
        d = self.detalle("yoga-pilates", self.actual(), self.previas())
        self.assertEqual(d["base"]["corrida_id"], "2026-10-09-a")     # 28 d: la más cercana a 30 entre las que cumplen
        self.assertEqual(d["base"]["antiguedad_dias"], "28.0000")
        self.assertEqual((d["base"]["n_previas"], d["base"]["n_muy_recientes"], d["base"]["n_vencidas"]), (5, 2, 1))

    def test_la_mas_cercana_puede_ser_la_mas_vieja_de_las_validas(self):
        for cid, antes in {"2026-10-12-a": 26, "2026-09-22-a": 33}.items():
            self.guardar(self.base_doc, cid, T0 - dias(antes))
        d = self.detalle("yoga-pilates", self.actual(), self.previas())
        self.assertEqual(d["base"]["corrida_id"], "2026-09-22-a")      # |33-30| = 3 < |26-30| = 4

    def test_empate_a_igual_distancia_gana_la_mas_antigua(self):
        for cid, antes in {"2026-10-12-a": 25, "2026-10-02-a": 35}.items():
            self.guardar(self.base_doc, cid, T0 - dias(antes))
        previas = self.previas()
        d = self.detalle("yoga-pilates", self.actual(), previas)
        self.assertEqual(d["base"]["corrida_id"], "2026-10-02-a")
        self.assertEqual(self.detalle("yoga-pilates", self.actual(), list(reversed(previas)))["base"]["corrida_id"],
                         "2026-10-02-a")

    def test_todas_vencidas_o_mezcla_sin_ninguna_en_ventana(self):
        self.guardar(self.base_doc, "2026-08-08-a", T0 - dias(90))
        d = self.detalle("yoga-pilates", self.actual(), self.previas())
        self.assertEqual((d["valor"], d["motivo"]), (None, "base_vencida"))
        self.guardar(self.base_doc, "2026-10-27-a", T0 - dias(10))
        d = self.detalle("yoga-pilates", self.actual(), self.previas())
        self.assertEqual((d["valor"], d["motivo"]), (None, "sin_previa_en_ventana"))

    def test_cero_es_cero_cuando_hay_base(self):
        actual, previas = self.escenario()
        valor = self.entrantes("atlas-visual-salud", actual, previas)
        self.assertEqual(valor, 0)
        self.assertIsNotNone(valor)
        self.assertIsNot(valor, None)

    def test_el_reloj_inyectado_decide_la_elegibilidad(self):
        self.guardar_base()
        actual, previas = self.actual(), self.previas()
        ya = mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0, par=self.par)
        pronto = mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0 - dias(20), par=self.par)
        tarde = mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0 + dias(100), par=self.par)
        self.assertIsNotNone(ya)
        self.assertIsNone(pronto)        # a los 10 días de la base: demasiado reciente
        self.assertIsNone(tarde)         # a los 130 días: base vencida (máximo 60)
        with self.assertRaises(mem.ErrorUso):
            mem.entrantes_30d("yoga-pilates", actual, previas, ahora=datetime(2026, 11, 6), par=self.par)

    def test_zona_horaria_de_ahora_no_cambia_el_resultado(self):
        actual, previas = self.escenario()
        zona = timezone(timedelta(hours=9))
        local = T0.astimezone(zona)
        self.assertEqual(mem.entrantes_30d("yoga-pilates", actual, previas, ahora=local, par=self.par),
                         self.entrantes("yoga-pilates", actual, previas))

    def test_instantanea_posterior_a_ahora_es_ErrorValidacion(self):
        self.guardar(self.base_doc, CORRIDA_BASE, T0 + dias(1))
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("yoga-pilates", self.actual(), self.previas())

    def test_la_propia_corrida_no_es_su_previa(self):
        self.guardar_base()
        self.guardar(self.actual_doc, CORRIDA_ACTUAL, T0 - dias(31), etiquetas=self.et_actual)
        actual = mem.cargar_instantanea(CORRIDA_ACTUAL, self.raiz)
        previas = mem.cargar_previas(self.raiz)        # incluye a la propia corrida
        d = self.detalle("yoga-pilates", actual, previas)
        self.assertEqual(d["base"]["corrida_id"], CORRIDA_BASE)
        self.assertEqual(d["base"]["n_previas"], 1)

    def test_previa_repetida_es_ErrorValidacion(self):
        actual, previas = self.escenario()
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("yoga-pilates", actual, previas + previas)


class TestEntrantesDefinicion(Base):
    """Qué es «entrante» (bloque Definiciones del módulo)."""

    def setUp(self):
        super().setUp()
        self.actual_snap, self.previas_ok = self.escenario()

    def e(self, clave, **kw):
        return self.entrantes(clave, self.actual_snap, self.previas_ok, **kw)

    def test_tema_alcance_global(self):
        # yoga-pilates: 1001, 1003 y 1005 ya estaban (1005 solo cambió de país); 2001 es nueva con anuncio de 10 días
        self.assertEqual(self.e("yoga-pilates"), 1)
        self.assertEqual(self.e("atlas-visual-salud"), 0)      # 2002 es «reaparecida»: su anuncio (70 d) es anterior a la base
        self.assertEqual(self.e("recetas-sin-azucar"), 1)

    def test_pagina_reaparecida_no_cuenta_y_se_informa(self):
        d = self.detalle("atlas-visual-salud", self.actual_snap, self.previas_ok)
        self.assertEqual((d["valor"], d["reaparecidas"], d["paginas"]), (0, 1, []))
        d = self.detalle("yoga-pilates", self.actual_snap, self.previas_ok)
        self.assertEqual((d["valor"], d["reaparecidas"], d["paginas"]), (1, 0, ["2001"]))

    def test_oferta_pagina_es_uno_o_cero(self):
        self.assertEqual(self.e("2001"), 1)        # nueva real
        self.assertEqual(self.e("2003"), 1)
        self.assertEqual(self.e("2002"), 0)        # reaparecida
        self.assertEqual(self.e("1001"), 0)        # ya estaba
        self.assertEqual(self.e(2001), 1)          # page_id entero también

    def test_borde_de_la_edad_del_anuncio_mas_viejo(self):
        # la base tiene exactamente 30 días: un anuncio de 30 días empezó en el instante de la base -> cuenta; 30.0001 no
        for edad, esperado in (("30", 1), ("29.9999", 1), ("30.0001", 0)):
            actual_doc = doc_paginas(CORRIDA_ACTUAL, pagina("7777", edad_max=edad, edad="1"))
            actual = mem.construir_instantanea(actual_doc, CORRIDA_ACTUAL, ahora=T0)
            with self.subTest(edad_max=edad):
                self.assertEqual(self.entrantes("7777", actual, self.previas_ok), esperado)

    def test_pagina_con_cero_anuncios_no_es_presencia(self):
        actual_doc = doc_paginas(CORRIDA_ACTUAL, pagina("7777", anuncios=0, edad_max="1"), pagina("8888", edad_max="1"))
        actual = mem.construir_instantanea(actual_doc, CORRIDA_ACTUAL, ahora=T0)
        with self.assertRaises(mem.ErrorUso):
            self.entrantes("7777", actual, self.previas_ok)
        self.assertEqual(self.entrantes("8888", actual, self.previas_ok), 1)

    def test_por_pais_cuenta_nuevas_y_expansiones(self):
        self.assertEqual(self.e("yoga-pilates", pais="ES"), 1)     # 2001 nueva en ES
        self.assertEqual(self.e("yoga-pilates", pais="MX"), 1)     # 1005 se expandió a MX (estaba en ES)
        self.assertEqual(self.e("atlas-visual-salud", pais="ES"), 0)
        self.assertEqual(self.e("atlas-visual-salud", pais="MX"), 0)   # nadie del tema en MX: 0 legítimo con base y cobertura
        self.assertEqual(self.e("recetas-sin-azucar", pais="ES"), 1)
        self.assertEqual(self.e("recetas-sin-azucar", pais="MX"), 1)

    def test_pagina_que_cambia_de_pais(self):
        # 1005 estaba en ES (base) y ahora solo en MX
        self.assertEqual(self.e("1005"), 0)              # no es una página nueva
        self.assertEqual(self.e("1005", pais="MX"), 1)   # sí es un entrante al mercado MX (expansión)
        self.assertEqual(self.e("1005", pais="ES"), 0)   # y en ES ya no está: no entra, se fue
        d = self.diff(self.actual_snap, self.previas_ok)
        self.assertEqual(d["paginas_que_cambian_de_pais"], [{
            "page_id": "1005", "page_name": "Viajera", "paises_antes": ["ES"], "paises_ahora": ["MX"],
            "paises_nuevos": ["MX"], "paises_perdidos": ["ES"]}])
        self.assertNotIn("1005", [p["page_id"] for p in d["paginas_nuevas"]])

    def test_pagina_que_sigue_igual_en_su_pais_no_es_entrante(self):
        self.assertEqual(self.e("1001", pais="ES"), 0)
        self.assertEqual(self.e("1003", pais="ES"), 0)

    def test_pagina_fuera_del_pais_pedido_da_cero(self):
        self.assertEqual(self.e("2001", pais="MX"), 0)   # 2001 solo está en ES

    def test_claves_desconocidas_son_ErrorUso_no_cero(self):
        for clave in ("9999", "tema-que-no-existe", "1004", "Mayusculas", "con espacio", "", None, True, 1.5, ["1001"]):
            with self.subTest(clave=clave), self.assertRaises(mem.ErrorUso):
                self.e(clave)

    def test_pais_invalido_es_ErrorUso(self):
        for pais in ("es", "ESP", "E", 5, ""):
            with self.subTest(pais=pais), self.assertRaises(mem.ErrorUso):
                self.e("yoga-pilates", pais=pais)

    def test_piso_y_base_truncada(self):
        d = self.detalle("atlas-visual-salud", self.actual_snap, self.previas_ok, pais="ES")
        self.assertTrue(d["piso"])               # 1006 está truncada ahora: el conteo es piso
        self.assertTrue(d["base_truncada"])      # y lo estaba en la base: pudo contar falsos entrantes
        d = self.detalle("yoga-pilates", self.actual_snap, self.previas_ok, pais="ES")
        self.assertEqual((d["piso"], d["base_truncada"]), (False, True))   # la base ES tiene la 1006 truncada
        d = self.detalle("yoga-pilates", self.actual_snap, self.previas_ok, pais="MX")
        self.assertEqual((d["piso"], d["base_truncada"]), (False, False))

    def test_mercado_no_consultado_es_none_no_cero(self):
        # barrido actual que solo consultó ES (las páginas de MX se quitan para que la cobertura sea coherente)
        doc = copy.deepcopy(self.actual_doc)
        doc["paginas"] = [p for p in doc["paginas"] if p["paises"] == ["ES"]]
        solo_es = mem.construir_instantanea(doc, CORRIDA_ACTUAL, ahora=T0, etiquetas=self.et_actual,
                                            paises_consultados=["ES"])
        d = self.detalle("yoga-pilates", solo_es, self.previas_ok, pais="MX")
        self.assertIsNone(d["valor"])
        self.assertEqual(d["motivo"], "pais_no_consultado_ahora")
        self.assertEqual(self.entrantes("yoga-pilates", solo_es, self.previas_ok, pais="ES"), 1)

    def test_base_que_no_miro_el_mercado_es_none(self):
        otra = tempfile.TemporaryDirectory()
        self.addCleanup(otra.cleanup)
        doc = copy.deepcopy(self.base_doc)
        doc["paginas"] = [p for p in doc["paginas"] if p["paises"] == ["ES"]]
        mem.guardar_instantanea(doc, CORRIDA_BASE, raiz=Path(otra.name), ahora=T0 - dias(30),
                                etiquetas=self.et_base, paises_consultados=["ES"])
        previas = mem.cargar_previas(Path(otra.name))
        d = self.detalle("yoga-pilates", self.actual_snap, previas, pais="MX")
        self.assertEqual((d["valor"], d["motivo"]), (None, "pais_no_consultado_en_base"))
        self.assertEqual(self.entrantes("yoga-pilates", self.actual_snap, previas, pais="ES"), 1)

    def test_cobertura_desconocida_calcula_pero_advierte(self):
        otra = tempfile.TemporaryDirectory()
        self.addCleanup(otra.cleanup)
        mem.guardar_instantanea(self.base_doc, CORRIDA_BASE, raiz=Path(otra.name), ahora=T0 - dias(30),
                                etiquetas=self.et_base)           # sin paises_consultados
        previas = mem.cargar_previas(Path(otra.name))
        d = self.detalle("yoga-pilates", self.actual_snap, previas, pais="MX")
        self.assertEqual(d["valor"], 1)
        self.assertTrue(any("cobertura de países desconocida en la base" in a for a in d["advertencias"]))


class TestEntrantesEntradas(Base):
    def test_parametro_obligatorio_faltante_es_ErrorLimite(self):
        actual, previas = self.escenario()
        for par in ({}, {"memoria_ventana_min_dias": None}, {"otra_clave": 1}):
            with self.subTest(par=par), self.assertRaises(mem.ErrorLimite):
                mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0, par=par)
            with self.subTest(par=par, funcion="diff"), self.assertRaises(mem.ErrorLimite):
                mem.diff(actual, previas, par=par, ahora=T0)

    def test_parametros_raros_son_ErrorValidacion(self):
        actual, previas = self.escenario()
        malos = [{"memoria_ventana_min_dias": 25.0}, {"memoria_ventana_min_dias": "abc"},
                 {"memoria_ventana_min_dias": 0}, {"memoria_ventana_min_dias": -3},
                 {"memoria_ventana_min_dias": True}, {"memoria_ventana_min_dias": "NaN"},
                 {"memoria_ventana_min_dias": 25, "memoria_ventana_max_dias": 24},
                 {"memoria_ventana_min_dias": 25, "memoria_ventana_max_dias": 90.5}]
        for par in malos:
            with self.subTest(par=par), self.assertRaises(mem.ErrorValidacion):
                mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0, par=par)

    def test_par_que_no_es_mapa_es_ErrorUso(self):
        actual, previas = self.escenario()
        for par in (None, 25, [25]):
            with self.subTest(par=par), self.assertRaises(mem.ErrorUso):
                mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0, par=par)

    def test_acepta_decimal_y_cadena_en_los_parametros(self):
        actual, previas = self.escenario()
        for valor in (25, Decimal("25"), "25", "25.0"):
            par = {"memoria_ventana_min_dias": valor}
            with self.subTest(valor=valor):
                self.assertEqual(mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0, par=par), 1)

    def test_con_los_parametros_reales_de_B1(self):
        par = comun.cargar_parametros_barrido()      # parametros_barrido.propuesta.yaml: solo lee, no escribe
        actual, previas = self.escenario()
        valor = mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0, par=par)
        self.assertEqual(valor, 1)

    def test_previa_corrupta_es_ErrorValidacion_y_no_se_usa(self):
        actual, previas = self.escenario()
        corrupta = copy.deepcopy(previas[0])
        corrupta["paginas"][0]["anuncios_activos_en_muestra"] += 1
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("yoga-pilates", actual, [corrupta])
        with self.assertRaises(mem.ErrorValidacion):
            self.diff(actual, [corrupta])

    def test_la_corrupta_no_se_usa_aunque_sea_la_mejor_base(self):
        self.guardar_base(antes=30)                              # la mejor base (exactamente 30 d)
        self.guardar(self.base_doc, "2026-09-22-a", T0 - dias(45))
        previas = self.previas()
        corrupta = next(p for p in previas if p["corrida_id"] == CORRIDA_BASE)
        corrupta = copy.deepcopy(corrupta)
        corrupta["paginas"].pop()                                # y además n_paginas deja de cuadrar
        resto = [p for p in previas if p["corrida_id"] != CORRIDA_BASE]
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("yoga-pilates", self.actual(), resto + [corrupta])
        corrupta2 = copy.deepcopy(next(p for p in previas if p["corrida_id"] == CORRIDA_BASE))
        corrupta2["ts"] = "2026-10-01T00:00:00Z"                 # cambiar el ts también rompe el hash
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("yoga-pilates", self.actual(), resto + [corrupta2])

    def test_hash_recalculado_a_mano_pero_distinto_al_indice_no_pasa_por_disco(self):
        actual, previas = self.escenario()
        falsa = copy.deepcopy(previas[0])
        falsa["paginas"][0]["anuncios_activos_en_muestra"] += 1
        falsa["hash"] = mem._hash_contenido({k: v for k, v in falsa.items() if k != "hash"})
        self.assertEqual(mem.entrantes_30d("yoga-pilates", actual, [falsa], ahora=T0, par=self.par), 1)  # en memoria pasa
        # pero cargar desde disco la rechaza si el archivo se reescribió así
        self.alterar_archivo(CORRIDA_BASE, lambda d: d.update(falsa))
        with self.assertRaises(mem.ErrorValidacion):
            mem.cargar_previas(self.raiz)

    def test_previa_que_no_es_instantanea_es_ErrorValidacion(self):
        actual, _ = self.escenario()
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("yoga-pilates", actual, [self.base_doc])     # documento «Páginas», sin hash
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("yoga-pilates", actual, [None])
        with self.assertRaises(mem.ErrorUso):
            self.entrantes("yoga-pilates", actual, "no-es-lista")
        with self.assertRaises(mem.ErrorUso):
            self.entrantes("yoga-pilates", actual, None)

    def test_actual_acepta_documento_paginas_sin_hash(self):
        self.guardar_base()
        previas = self.previas()
        self.assertEqual(self.entrantes("2001", self.actual_doc, previas), 1)
        self.assertEqual(self.entrantes("2002", self.actual_doc, previas), 0)
        with self.assertRaises(mem.ErrorUso):                           # sin etiquetas no hay temas
            self.entrantes("yoga-pilates", self.actual_doc, previas)

    def test_actual_invalido(self):
        self.guardar_base()
        previas = self.previas()
        with self.assertRaises(mem.ErrorUso):
            self.entrantes("1001", None, previas)
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("1001", {"corrida_id": "mala", "paginas": []}, previas)
        corrupta = self.actual()
        corrupta["paginas"][0]["anuncios_activos_en_muestra"] = 1234
        with self.assertRaises(mem.ErrorValidacion):
            self.entrantes("1001", corrupta, previas)

    def test_determinismo_y_orden_de_previas(self):
        for cid, antes in {"2026-10-27-a": 10, "2026-10-09-a": 28, "2026-09-22-a": 45}.items():
            self.guardar(self.base_doc, cid, T0 - dias(antes), etiquetas=self.et_base)
        actual, previas = self.actual(), self.previas()
        base = self.detalle("yoga-pilates", actual, previas)
        for i in range(5):
            barajadas = list(previas)
            random.Random(i).shuffle(barajadas)
            self.assertEqual(self.detalle("yoga-pilates", actual, barajadas), base)
        self.assertEqual(json.dumps(self.detalle("yoga-pilates", actual, previas), sort_keys=True),
                         json.dumps(base, sort_keys=True))

    def test_no_muta_las_entradas(self):
        actual, previas = self.escenario()
        copia_a, copia_p, copia_par = copy.deepcopy(actual), copy.deepcopy(previas), copy.deepcopy(self.par)
        self.entrantes("yoga-pilates", actual, previas, pais="MX")
        self.diff(actual, previas)
        self.assertEqual((actual, previas, self.par), (copia_a, copia_p, copia_par))


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

class TestDiff(Base):
    def test_primera_corrida_todo_none_y_sin_base(self):
        d = self.diff(self.actual(), [])
        self.assertEqual(d["estado"], "sin_base")
        self.assertEqual(d["base_entrantes"]["estado"], "sin_base")
        self.assertEqual(d["base_entrantes"]["motivo"], "primera_corrida")
        self.assertEqual(d["base_cambios"], {"estado": "sin_base", "motivo": "primera_corrida",
                                             "corrida_id": None, "antiguedad_dias": None})
        for clave in ("paginas_nuevas", "paginas_que_crecen", "paginas_que_decrecen", "paginas_desaparecidas",
                      "paginas_que_cambian_de_pais", "temas_nuevos"):
            self.assertEqual(d[clave], [], clave)
        self.assertEqual(d["temas_estado"], "sin_base")
        self.assertEqual(set(d["entrantes_30d"]), {"yoga-pilates", "atlas-visual-salud", "recetas-sin-azucar"})
        self.assertTrue(all(v is None for v in d["entrantes_30d"].values()))
        self.assertTrue(all(v is None for por in d["entrantes_30d_por_pais"].values() for v in por.values()))
        self.assertTrue(any("sin base" in a for a in d["advertencias"]))
        self.assertNotIn(0, [v for v in recorrer(d["entrantes_30d"])])

    def test_diff_completo_del_fixture(self):
        actual, previas = self.escenario()
        d = self.diff(actual, previas)
        self.assertEqual(d["estado"], "ok")
        self.assertEqual(d["corrida_id"], CORRIDA_ACTUAL)
        self.assertEqual(d["ahora"], "2026-11-06T12:00:00Z")
        self.assertEqual(d["base_entrantes"]["corrida_id"], CORRIDA_BASE)
        self.assertEqual(d["base_entrantes"]["antiguedad_dias"], "30.0000")
        self.assertFalse(d["base_entrantes"]["ventana_excedida"])
        self.assertEqual(d["base_cambios"]["corrida_id"], CORRIDA_BASE)
        self.assertEqual([(p["page_id"], p["entrante"]) for p in d["paginas_nuevas"]],
                         [("2001", True), ("2002", False), ("2003", True)])
        self.assertEqual(d["paginas_nuevas"][0], {
            "page_id": "2001", "page_name": "Nueva Real", "paises": ["ES"], "anuncios_activos_en_muestra": 6,
            "tema_slug": "yoga-pilates", "entrante": True})
        self.assertEqual(d["paginas_que_crecen"], [{"page_id": "1001", "page_name": "Anna Martin", "antes": 5,
                                                    "despues": 9, "delta": 4, "piso": False}])
        self.assertEqual(d["paginas_que_decrecen"], [{"page_id": "1002", "page_name": "Atril Estudio", "antes": 8,
                                                      "despues": 3, "delta": -5, "piso": False}])
        self.assertEqual(d["paginas_desaparecidas"], [{"page_id": "1004", "page_name": "Solo en la base",
                                                       "paises": ["ES"], "anuncios_activos_en_muestra": 2}])
        self.assertEqual([p["page_id"] for p in d["paginas_que_cambian_de_pais"]], ["1005"])
        self.assertEqual(d["temas_nuevos"], ["recetas-sin-azucar"])
        self.assertEqual(d["temas_estado"], "ok")
        self.assertEqual(d["entrantes_30d"], {"atlas-visual-salud": 0, "recetas-sin-azucar": 1, "yoga-pilates": 1})
        self.assertEqual(d["entrantes_30d_por_pais"], {
            "atlas-visual-salud": {"ES": 0, "MX": 0},
            "recetas-sin-azucar": {"ES": 1, "MX": 1},
            "yoga-pilates": {"ES": 1, "MX": 1}})
        self.assertTrue(any("desaparecida" in a for a in d["advertencias"]))
        self.assertTrue(any("truncada" in a for a in d["advertencias"]))

    def test_diff_coincide_con_entrantes_30d(self):
        actual, previas = self.escenario()
        d = self.diff(actual, previas)
        for clave, valor in d["entrantes_30d"].items():
            self.assertEqual(self.entrantes(clave, actual, previas), valor)
            for pais, v in d["entrantes_30d_por_pais"][clave].items():
                self.assertEqual(self.entrantes(clave, actual, previas, pais=pais), v)

    def test_base_de_cambios_es_la_mas_reciente_aunque_no_sirva_para_entrantes(self):
        self.guardar_base(antes=30)
        self.guardar(self.base_doc, "2026-11-03-a", T0 - dias(3))
        actual, previas = self.actual(), self.previas()
        d = self.diff(actual, previas)
        self.assertEqual(d["base_cambios"]["corrida_id"], "2026-11-03-a")
        self.assertEqual(d["base_entrantes"]["corrida_id"], CORRIDA_BASE)
        self.assertEqual(d["estado"], "ok")

    def test_con_solo_una_previa_reciente_hay_cambios_pero_entrantes_none(self):
        self.guardar_base(antes=3)
        actual, previas = self.actual(), self.previas()
        d = self.diff(actual, previas)
        self.assertEqual(d["estado"], "sin_base")
        self.assertEqual(d["base_entrantes"]["motivo"], "base_demasiado_reciente")
        self.assertEqual(d["base_cambios"]["estado"], "ok")
        self.assertEqual([p["page_id"] for p in d["paginas_nuevas"]], ["2001", "2002", "2003"])
        self.assertTrue(all(p["entrante"] is None for p in d["paginas_nuevas"]))   # ni sí ni no: sin base
        self.assertEqual(d["temas_nuevos"], ["recetas-sin-azucar"])
        self.assertTrue(all(v is None for v in d["entrantes_30d"].values()))

    def test_sin_etiquetas_las_claves_son_page_id(self):
        self.guardar_base(etiquetas={})
        d = self.diff(self.actual_doc, self.previas())
        self.assertEqual(d["temas_estado"], "sin_etiquetas")
        self.assertEqual(d["temas_nuevos"], [])
        self.assertEqual(list(d["entrantes_30d"]), ["1001", "1002", "1003", "1005", "1006", "2001", "2002", "2003"])
        self.assertEqual({k: v for k, v in d["entrantes_30d"].items() if v}, {"2001": 1, "2003": 1})

    def test_base_sin_etiquetas_no_declara_temas_nuevos(self):
        self.guardar_base(etiquetas={})
        d = self.diff(self.actual(), self.previas())
        self.assertEqual(d["temas_estado"], "base_sin_etiquetas")
        self.assertEqual(d["temas_nuevos"], [])       # no se afirma «nuevo» lo que no se puede comparar
        self.assertEqual(d["entrantes_30d"]["yoga-pilates"], 1)   # entrantes no depende de las etiquetas de la base

    def test_paginas_sin_tema_conviven_con_temas(self):
        et = {k: v for k, v in self.et_actual.items() if k != "2001"}
        self.guardar_base()
        d = self.diff(self.actual(etiquetas=et), self.previas())
        self.assertIn("2001", d["entrantes_30d"])
        self.assertEqual(d["entrantes_30d"]["2001"], 1)
        self.assertEqual(d["entrantes_30d"]["yoga-pilates"], 0)

    def test_crece_y_decrece_marcan_piso_si_hubo_truncamiento(self):
        self.guardar_base()
        doc = copy.deepcopy(self.actual_doc)
        for p in doc["paginas"]:
            if p["page_id"] == "1006":
                p["anuncios_activos_en_muestra"] = 49          # base: 50 truncada
            if p["page_id"] == "1001":
                p["muestra_truncada"] = True
        actual = mem.construir_instantanea(doc, CORRIDA_ACTUAL, ahora=T0, etiquetas=self.et_actual)
        d = self.diff(actual, self.previas())
        self.assertEqual([(i["page_id"], i["piso"]) for i in d["paginas_que_decrecen"]], [("1002", False), ("1006", True)])
        self.assertEqual([(i["page_id"], i["piso"]) for i in d["paginas_que_crecen"]], [("1001", True)])

    def test_orden_de_crecen_y_decrecen_por_magnitud_y_luego_page_id(self):
        base = doc_paginas(CORRIDA_BASE, pagina("10", anuncios=5), pagina("20", anuncios=5), pagina("30", anuncios=5),
                           pagina("40", anuncios=9), pagina("50", anuncios=9))
        nuevo = doc_paginas(CORRIDA_ACTUAL, pagina("10", anuncios=8), pagina("20", anuncios=12), pagina("30", anuncios=8),
                            pagina("40", anuncios=2), pagina("50", anuncios=4))
        mem.guardar_instantanea(base, CORRIDA_BASE, raiz=self.raiz, ahora=T0 - dias(30))
        actual = mem.construir_instantanea(nuevo, CORRIDA_ACTUAL, ahora=T0)
        d = self.diff(actual, self.previas())
        self.assertEqual([i["page_id"] for i in d["paginas_que_crecen"]], ["20", "10", "30"])
        self.assertEqual([i["page_id"] for i in d["paginas_que_decrecen"]], ["40", "50"])

    def test_sin_cambios_listas_vacias_y_entrantes_cero(self):
        self.guardar_base()
        igual = con_corrida(self.base_doc, CORRIDA_ACTUAL)
        actual = mem.construir_instantanea(igual, CORRIDA_ACTUAL, ahora=T0, etiquetas=self.et_base,
                                           paises_consultados=["ES", "MX"])
        d = self.diff(actual, self.previas())
        for clave in ("paginas_nuevas", "paginas_que_crecen", "paginas_que_decrecen", "paginas_desaparecidas",
                      "paginas_que_cambian_de_pais", "temas_nuevos"):
            self.assertEqual(d[clave], [], clave)
        self.assertTrue(all(v == 0 for v in d["entrantes_30d"].values()))

    def test_paises_del_mapa_por_pais_salen_de_la_cobertura_o_de_las_paginas(self):
        self.guardar_base()
        con = self.diff(self.actual(), self.previas())
        sin = self.diff(self.actual(paises_consultados=None), self.previas())
        self.assertEqual(set(next(iter(con["entrantes_30d_por_pais"].values()))), {"ES", "MX"})
        self.assertEqual(set(next(iter(sin["entrantes_30d_por_pais"].values()))), {"ES", "MX"})
        self.assertTrue(any("paises_consultados" in a for a in sin["advertencias"]))

    def test_salida_sin_float_y_serializable(self):
        actual, previas = self.escenario()
        d = self.diff(actual, previas)
        sin_float(self, d)
        texto = json.dumps(d, sort_keys=True, ensure_ascii=False)
        self.assertEqual(json.loads(texto), d)
        d0 = self.diff(self.actual(), [])
        sin_float(self, d0)
        json.dumps(d0, allow_nan=False)

    def test_determinismo_y_orden_de_previas(self):
        for cid, antes in {"2026-10-27-a": 10, "2026-10-09-a": 28, "2026-09-22-a": 45}.items():
            self.guardar(self.base_doc, cid, T0 - dias(antes), etiquetas=self.et_base)
        actual, previas = self.actual(), self.previas()
        primero = self.diff(actual, previas)
        for i in range(5):
            barajadas = list(previas)
            random.Random(i).shuffle(barajadas)
            self.assertEqual(self.diff(actual, barajadas), primero)
        self.assertEqual(json.dumps(self.diff(actual, previas), sort_keys=True), json.dumps(primero, sort_keys=True))

    def test_actual_instantanea_o_documento_dan_los_mismos_cambios(self):
        self.guardar_base(etiquetas={})
        previas = self.previas()
        sin_tema = mem.construir_instantanea(self.actual_doc, CORRIDA_ACTUAL, ahora=T0,
                                             paises_consultados=["ES", "MX"])
        a = self.diff(sin_tema, previas)
        b = self.diff(self.actual_doc, previas)
        for clave in ("paginas_nuevas", "paginas_que_crecen", "paginas_que_decrecen", "paginas_desaparecidas",
                      "paginas_que_cambian_de_pais", "entrantes_30d", "estado"):
            self.assertEqual(a[clave], b[clave], clave)

    def test_diff_no_usa_instantanea_corrupta(self):
        self.guardar_base()
        self.alterar_archivo(CORRIDA_BASE, lambda d: d["paginas"][0].__setitem__("anuncios_activos_en_muestra", 1))
        with self.assertRaises(mem.ErrorValidacion):
            self.diff(self.actual(), mem.cargar_previas(self.raiz))

    def test_pagina_con_cero_anuncios_cuenta_como_ausente(self):
        base = doc_paginas(CORRIDA_BASE, pagina("10", anuncios=0), pagina("20", anuncios=4))
        nuevo = doc_paginas(CORRIDA_ACTUAL, pagina("10", anuncios=3, edad_max="2"), pagina("20", anuncios=0))
        mem.guardar_instantanea(base, CORRIDA_BASE, raiz=self.raiz, ahora=T0 - dias(30))
        d = self.diff(mem.construir_instantanea(nuevo, CORRIDA_ACTUAL, ahora=T0), self.previas())
        self.assertEqual([p["page_id"] for p in d["paginas_nuevas"]], ["10"])        # 10 no estaba activa en la base
        self.assertEqual([p["page_id"] for p in d["paginas_desaparecidas"]], ["20"])  # 20 dejó de estar activa
        self.assertEqual(d["entrantes_30d"], {"10": 1})

    def test_barrido_actual_vacio(self):
        self.guardar_base()
        vacio = mem.construir_instantanea(doc_paginas(CORRIDA_ACTUAL), CORRIDA_ACTUAL, ahora=T0)
        d = self.diff(vacio, self.previas())
        self.assertEqual(d["entrantes_30d"], {})
        self.assertEqual(len(d["paginas_desaparecidas"]), 6)
        self.assertEqual(d["paginas_nuevas"], [])


# ---------------------------------------------------------------------------
# Piso de los entrantes por país (revisión de corrección m6)
# ---------------------------------------------------------------------------

class TestPisoPorPais(Base):
    """Un 0 sobre muestras truncadas es un piso y favorece el hueco: diff debe marcarlo, no solo exportar enteros."""

    def test_exporta_el_piso_con_las_mismas_claves_que_los_enteros(self):
        actual, previas = self.escenario()
        d = self.diff(actual, previas)
        self.assertEqual(d["entrantes_30d_piso_por_pais"], {
            "atlas-visual-salud": {"ES": True, "MX": False},
            "recetas-sin-azucar": {"ES": True, "MX": False},
            "yoga-pilates": {"ES": True, "MX": False}})          # la muestra de ES (1006) está truncada en la base
        self.assertEqual({k: sorted(v) for k, v in d["entrantes_30d_piso_por_pais"].items()},
                         {k: sorted(v) for k, v in d["entrantes_30d_por_pais"].items()})

    def test_es_un_cero_marcado_como_piso(self):
        actual, previas = self.escenario()
        d = self.diff(actual, previas)
        self.assertEqual(d["entrantes_30d_por_pais"]["atlas-visual-salud"]["ES"], 0)      # el cero…
        self.assertIs(d["entrantes_30d_piso_por_pais"]["atlas-visual-salud"]["ES"], True)  # …no prueba que nadie entró
        self.assertIs(d["entrantes_30d_piso_por_pais"]["atlas-visual-salud"]["MX"], False)

    def test_coincide_con_el_desglose_de_entrantes_detalle(self):
        actual, previas = self.escenario()
        d = self.diff(actual, previas)
        for clave, por_pais in d["entrantes_30d_piso_por_pais"].items():
            for pais, marca in por_pais.items():
                det = self.detalle(clave, actual, previas, pais=pais)
                self.assertEqual(marca, bool(det["piso"] or det["base_truncada"]), (clave, pais))

    def test_muestras_completas_no_se_marcan(self):
        base = copy.deepcopy(self.base_doc)
        nuevo = copy.deepcopy(self.actual_doc)
        for doc in (base, nuevo):
            for p in doc["paginas"]:
                p["muestra_truncada"] = False
        self.base_doc = base
        self.guardar_base()
        actual = mem.construir_instantanea(nuevo, CORRIDA_ACTUAL, ahora=T0, etiquetas=self.et_actual,
                                           paises_consultados=["ES", "MX"])
        d = self.diff(actual, self.previas())
        self.assertTrue(all(m is False for por in d["entrantes_30d_piso_por_pais"].values() for m in por.values()))
        self.assertEqual(d["entrantes_30d_por_pais"]["atlas-visual-salud"]["ES"], 0)

    def test_basta_con_que_el_actual_este_truncado(self):
        base = copy.deepcopy(self.base_doc)
        for p in base["paginas"]:
            p["muestra_truncada"] = False
        self.base_doc = base
        self.guardar_base()
        nuevo = copy.deepcopy(self.actual_doc)
        for p in nuevo["paginas"]:
            p["muestra_truncada"] = p["page_id"] == "1001"
        actual = mem.construir_instantanea(nuevo, CORRIDA_ACTUAL, ahora=T0, etiquetas=self.et_actual,
                                           paises_consultados=["ES", "MX"])
        d = self.diff(actual, self.previas())
        self.assertEqual(d["entrantes_30d_piso_por_pais"]["yoga-pilates"], {"ES": True, "MX": False})
        self.assertEqual(d["entrantes_30d_piso_por_pais"]["atlas-visual-salud"], {"ES": False, "MX": False})

    def test_sin_base_todo_none(self):
        d = self.diff(self.actual(), [])
        self.assertEqual(set(d["entrantes_30d_piso_por_pais"]), set(d["entrantes_30d_por_pais"]))
        self.assertTrue(all(m is None for por in d["entrantes_30d_piso_por_pais"].values() for m in por.values()))

    def test_none_donde_el_valor_es_none(self):
        doc = copy.deepcopy(self.base_doc)
        doc["paginas"] = [p for p in doc["paginas"] if p["paises"] == ["ES"]]
        self.guardar(doc, CORRIDA_BASE, T0 - dias(30), etiquetas=self.et_base, paises_consultados=["ES"])
        d = self.diff(self.actual(), self.previas())
        self.assertIsNone(d["entrantes_30d_por_pais"]["yoga-pilates"]["MX"])       # la base no miró MX
        self.assertIsNone(d["entrantes_30d_piso_por_pais"]["yoga-pilates"]["MX"])
        self.assertIsInstance(d["entrantes_30d_piso_por_pais"]["yoga-pilates"]["ES"], bool)

    def test_cambio_aditivo_y_serializable(self):
        actual, previas = self.escenario()
        d = self.diff(actual, previas)
        for clave in ("entrantes_30d", "entrantes_30d_por_pais", "estado", "base_entrantes", "base_cambios"):
            self.assertIn(clave, d)
        hojas = list(recorrer(d["entrantes_30d_piso_por_pais"]))
        self.assertTrue(all(h is None or isinstance(h, bool) for h in hojas))
        json.dumps(d, allow_nan=False)


# ---------------------------------------------------------------------------
# Antigüedad medida desde la captura (revisión de corrección, «Deducido»)
# ---------------------------------------------------------------------------

class TestCapturadoEn(Base):
    def captura(self, antes, **kw):
        return comun.iso_z(T0 - dias(antes, kw.pop("segundos", 0)))

    def test_se_guarda_se_verifica_y_no_toca_el_indice(self):
        ruta = self.guardar_base(antes=20, capturado_en=self.captura(30))
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(doc["capturado_en"], "2026-10-07T12:00:00Z")
        self.assertEqual(doc["ts"], "2026-10-17T12:00:00Z")
        self.assertEqual(mem.verificar_integridad(self.raiz), [])
        entrada = json.loads((self.carpeta / "indice.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(set(entrada), {"corrida_id", "ts", "n_paginas", "n_consultas", "hash"})

    def test_la_antiguedad_se_mide_desde_la_captura_no_desde_el_guardado(self):
        # capturada hace 30 días, guardada hace 20: por ts sería demasiado reciente (< 25) y se descartaría
        self.guardar_base(antes=20, capturado_en=self.captura(30))
        actual, previas = self.actual(), self.previas()
        d = self.detalle("yoga-pilates", actual, previas)
        self.assertEqual(d["valor"], 1)
        self.assertEqual(d["base"]["antiguedad_dias"], "30.0000")
        self.assertEqual(d["base"]["antiguedad_desde"], "capturado_en")

    def test_sin_capturado_en_se_mide_por_ts_y_se_dice(self):
        ruta = self.guardar_base(antes=20)
        self.assertNotIn("capturado_en", json.loads(ruta.read_text(encoding="utf-8")))
        d = self.detalle("yoga-pilates", self.actual(), self.previas())
        self.assertEqual((d["valor"], d["motivo"]), (None, "base_demasiado_reciente"))
        self.guardar(self.base_doc, "2026-09-22-a", T0 - dias(45))
        d = self.detalle("yoga-pilates", self.actual(), self.previas())
        self.assertEqual(d["base"]["antiguedad_desde"], "ts")

    def test_documento_de_paginas_con_capturado_en_equivale_al_argumento(self):
        en_doc = copy.deepcopy(self.base_doc)
        en_doc["capturado_en"] = self.captura(30)
        a = mem.construir_instantanea(en_doc, CORRIDA_BASE, ahora=T0 - dias(20))
        b = mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0 - dias(20), capturado_en=self.captura(30))
        c = mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0 - dias(20), capturado_en=T0 - dias(30))
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(a["capturado_en"], "2026-10-07T12:00:00Z")

    def test_argumento_y_documento_que_se_contradicen_son_ErrorValidacion(self):
        en_doc = copy.deepcopy(self.base_doc)
        en_doc["capturado_en"] = self.captura(30)
        with self.assertRaises(mem.ErrorValidacion):
            mem.construir_instantanea(en_doc, CORRIDA_BASE, ahora=T0 - dias(20), capturado_en=self.captura(29))
        self.assertEqual(mem.construir_instantanea(en_doc, CORRIDA_BASE, ahora=T0 - dias(20),
                                                   capturado_en=self.captura(30))["capturado_en"], "2026-10-07T12:00:00Z")

    def test_capturado_en_invalido_o_posterior_al_guardado_es_error(self):
        for malo in ("ayer", "2026-10-07", "2026-10-07T12:00:00", "2026-10-07 12:00:00Z", 5):
            with self.subTest(malo=malo), self.assertRaises(mem.ErrorValidacion):
                mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0, capturado_en=malo)
        with self.assertRaises(mem.ErrorValidacion):      # capturar después de guardar no existe
            mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0, capturado_en=comun.iso_z(T0 + dias(0, 1)))
        with self.assertRaises(mem.ErrorUso):             # datetime sin zona
            mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0, capturado_en=datetime(2026, 10, 7))
        mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0, capturado_en=comun.iso_z(T0))   # == ts: válido

    def test_borde_de_memoria_ventana_min_dias_se_mide_desde_la_captura(self):
        self.guardar_base(antes=2, capturado_en=self.captura(25))
        self.assertIsNotNone(self.entrantes("yoga-pilates", self.actual(), self.previas()))
        otra = tempfile.TemporaryDirectory()
        self.addCleanup(otra.cleanup)
        mem.guardar_instantanea(self.base_doc, CORRIDA_BASE, raiz=Path(otra.name), ahora=T0 - dias(2),
                                capturado_en=self.captura(25, segundos=-1))      # 1 s menos de 25 días
        self.assertIsNone(self.entrantes("yoga-pilates", self.actual(), mem.cargar_previas(Path(otra.name))))

    def test_snapshot_con_capturado_en_posterior_a_ts_se_rechaza_al_leer(self):
        snap = mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0 - dias(30))
        snap["capturado_en"] = comun.iso_z(T0)
        snap["hash"] = mem._hash_contenido({k: v for k, v in snap.items() if k != "hash"})
        with self.assertRaises(mem.ErrorValidacion):
            mem._foto_de_instantanea(snap, "x")

    def test_el_campo_esta_cubierto_por_el_hash(self):
        self.guardar_base(antes=20, capturado_en=self.captura(30))
        self.alterar_archivo(CORRIDA_BASE, lambda d: d.__setitem__("capturado_en", self.captura(26)))
        self.assertEqual([p["tipo"] for p in mem.verificar_integridad(self.raiz)], ["hash_distinto"])
        with self.assertRaises(mem.ErrorValidacion):
            mem.cargar_previas(self.raiz)

    def test_la_base_mas_cercana_a_30_dias_se_elige_por_captura(self):
        # P1: guardada hace 28 d pero capturada hace 45 (por ts parecería la mejor); P2: capturada y guardada hace 35
        self.guardar(self.base_doc, "2026-09-22-a", T0 - dias(28), capturado_en=self.captura(45))
        self.guardar(self.base_doc, "2026-10-02-a", T0 - dias(35))
        d = self.detalle("yoga-pilates", self.actual(), self.previas())
        self.assertEqual(d["base"]["corrida_id"], "2026-10-02-a")      # |35-30| = 5 < |45-30| = 15
        self.assertEqual(d["base"]["antiguedad_dias"], "35.0000")

    def test_la_regla_de_edad_usa_la_antiguedad_desde_la_captura(self):
        # una página nueva con un anuncio de 40 días: empezó después de una base capturada hace 45 días
        pag = doc_paginas(CORRIDA_ACTUAL, pagina("7777", edad_max="40", edad="3"))
        actual = mem.construir_instantanea(pag, CORRIDA_ACTUAL, ahora=T0)
        self.guardar_base(antes=28, capturado_en=self.captura(45))
        self.assertEqual(self.entrantes("7777", actual, self.previas()), 1)
        otra = tempfile.TemporaryDirectory()
        self.addCleanup(otra.cleanup)
        mem.guardar_instantanea(self.base_doc, CORRIDA_BASE, raiz=Path(otra.name), ahora=T0 - dias(28))   # sin captura
        # medida por ts (28 d) el anuncio de 40 días sería anterior a la base: reaparecida, no cuenta
        self.assertEqual(self.entrantes("7777", actual, mem.cargar_previas(Path(otra.name))), 0)

    def test_base_de_cambios_ordena_y_fecha_por_captura(self):
        self.guardar(self.base_doc, "2026-10-01-a", T0 - dias(3), capturado_en=self.captura(40))   # guardada tarde
        self.guardar(self.base_doc, "2026-10-27-a", T0 - dias(6), capturado_en=self.captura(10))
        d = self.diff(self.actual(), self.previas())
        self.assertEqual(d["base_cambios"]["corrida_id"], "2026-10-27-a")      # la captura más reciente (por ts sería la otra)
        self.assertEqual((d["base_cambios"]["antiguedad_dias"], d["base_cambios"]["antiguedad_desde"]),
                         ("10.0000", "capturado_en"))                           # y por ts serían 6 días

    def test_instantaneas_anteriores_al_campo_siguen_siendo_validas_con_el_mismo_hash(self):
        snap = mem.construir_instantanea(self.base_doc, CORRIDA_BASE, ahora=T0 - dias(30), etiquetas=self.et_base,
                                         paises_consultados=["ES", "MX"])
        self.assertNotIn("capturado_en", snap)             # sin captura declarada, el formato no cambia
        # hash fijo de la instantánea del fixture: si cambia, cambió el formato y las ya guardadas dejarían de verificar
        self.assertEqual(snap["hash"], "sha256:57945f9f299d0b6354114ccdc36f9d54daf0c406a9289ae0507ce41a6ea1692f")
        foto = mem._foto_de_instantanea(snap, "x")
        self.assertEqual((foto["instante"], foto["instante_origen"]), (foto["ts"], "ts"))
        self.carpeta.mkdir(parents=True)
        self.escribir_json(self.carpeta / f"{CORRIDA_BASE}.json", snap)
        comun.anexar_jsonl(self.carpeta / "indice.jsonl", {
            "corrida_id": CORRIDA_BASE, "ts": snap["ts"], "n_paginas": snap["n_paginas"],
            "n_consultas": snap["n_consultas"], "hash": snap["hash"]})
        self.assertEqual(mem.verificar_integridad(self.raiz), [])


# ---------------------------------------------------------------------------
# Integración con el puntaje de modelado
# ---------------------------------------------------------------------------

class TestConPuntajeModelar(Base):
    """La lección de calcular_hueco: sin snapshot previo `entrantes_30d` es None y H queda incompleto; nunca 0."""

    def setUp(self):
        super().setUp()
        self.p = pm.cargar_parametros(PARAMETROS_MODELADO)

    def hueco(self, entrantes):
        h = {"original_presente": False, "anunciantes_sostenidos": 0, "puntaje_rival": None, "entrantes_30d": entrantes}
        return pm.calcular_hueco(h, "evergreen", self.p)

    def test_primera_corrida_deja_H_incompleta_con_techo(self):
        valor = mem.entrantes_30d("yoga-pilates", self.actual(), [], ahora=T0, par=self.par, pais="MX")
        self.assertIsNone(valor)
        h, sub, techo = self.hueco(valor)
        self.assertIsNone(h)
        self.assertIsNone(sub["h_entrantes"])
        self.assertEqual(techo, Decimal(1))

    def test_con_base_H_se_calcula_con_el_entero_medido(self):
        actual, previas = self.escenario()
        valor = mem.entrantes_30d("yoga-pilates", actual, previas, ahora=T0, par=self.par, pais="MX")
        self.assertEqual(valor, 1)
        h, sub, _ = self.hueco(valor)
        esperado = Decimal(1) - Decimal(1) / self.p["modelado_entrantes_tope_30d"]
        self.assertEqual(sub["h_entrantes"], esperado)
        self.assertEqual(h, esperado)

    def test_el_valor_cabe_en_la_ficha(self):
        actual, previas = self.escenario()
        for clave, por_pais in self.diff(actual, previas)["entrantes_30d_por_pais"].items():
            for pais, valor in por_pais.items():
                with self.subTest(tema=clave, pais=pais):
                    self.assertIsInstance(valor, int)
                    self.assertNotIsInstance(valor, bool)
                    self.hueco(valor)       # puntaje_modelar acepta el entero sin quejarse


if __name__ == "__main__":
    unittest.main()
