"""Pruebas de qc6.py (control de calidad de 6 puntos) y de qc6_reglas.py. Sin red: los archivos mínimos se generan en cada prueba.

Las pruebas con motores reales (Vision, ffmpeg, whisper, pdftoppm, Chrome) se omiten si el motor no está en la máquina.

Ejecutar: .venv/bin/python -m unittest discover -s tests/creativos -t . -p "test_*.py"
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tests.creativos.apoyo import (HAY_FFMPEG, HAY_PDFTOPPM, HAY_SAY, HAY_SWIFT, HAY_WHISPER, RAIZ, correr, copies_de_prueba, hay_navegador,
                                   renderizar_estatico)

import qc6  # noqa: E402  (la ruta de la skill la agrega apoyo)
import qc6_reglas as reglas  # noqa: E402

T_OK = "Arkusz: koszt, cena minimalna i marża w jednej tabeli dla każdego produktu"
PNG_MINIMO = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")


def motores(**kw) -> qc6.Motores:
    """Motores falsos: por defecto, un OCR que lee `ocr`, sin personas, sin audio. Todo se inyecta; nada se ejecuta."""
    ocr = kw.pop("ocr", [])
    base = dict(ocr=lambda _p, _l: ocr, personas=lambda _p: {"rostros": 0, "personas": 0, "manos": 0}, sonda=None, silencios=None, transcribir=None,
                fotogramas=lambda v, d, m: [v], paginas_pdf=lambda p, d, m: [p])
    base.update(kw)
    return qc6.Motores(**base)


def ctx(**kw) -> qc6.Contexto:
    base = dict(locale="pl-PL", ad_name="c01-koszt_img_h1_v1", macro_nicho="dinero")
    base.update(kw)
    return qc6.Contexto(**base)


class Archivo(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def png(self, nombre: str = "p.png") -> Path:
        r = self.dir / nombre
        r.write_bytes(PNG_MINIMO)
        return r


class PruebasReglas(unittest.TestCase):
    def test_las_frases_rojas_dan_rojo(self) -> None:
        sin_rojo = [s for s in reglas.PRUEBAS_ROJO if not any(h["nivel"] == "rojo" for h in reglas.buscar(reglas.plegar(s)))]
        self.assertEqual(sin_rojo, [])

    def test_las_frases_aprobables_no_dan_rojo(self) -> None:
        con_rojo = [(s, [h["categoria"] for h in reglas.buscar(reglas.plegar(s)) if h["nivel"] == "rojo"]) for s in reglas.PRUEBAS_VERDE]
        self.assertEqual([c for c in con_rojo if c[1]], [])

    def test_el_plazo_del_formato_no_es_rojo_pero_el_del_resultado_si(self) -> None:
        self.assertFalse(any(h["nivel"] == "rojo" for h in reglas.buscar(reglas.plegar("Plan de 14 días con garantía de devolución de 14 días"))))
        amarillo = reglas.buscar(reglas.plegar("Pide el reembolso en 14 días"))
        self.assertTrue(amarillo and all(h["nivel"] == "amarillo" for h in amarillo))
        self.assertTrue(any(h["categoria"] == "plazo_resultado" for h in reglas.buscar(reglas.plegar("Aprende a hablar inglés en 30 días"))))

    def test_los_falsos_negativos_conocidos_de_pl_pl(self) -> None:
        # coordinacion-sesiones: X1 no detecta płynnie, w 30 dni, sekret poliglotów, tysiące zadowolonych klientów, Zostało tylko 3
        for frase in ("Mów płynnie", "Naucz się angielskiego w 30 dni", "Sekret poliglotów", "Tysiące zadowolonych klientów", "Zostało tylko 3"):
            self.assertTrue(reglas.buscar(reglas.plegar(frase)), frase)

    def test_plegar(self) -> None:
        self.assertEqual(reglas.plegar("  ŁÓDŹ  Straße Œuvre "), "lodz strasse oeuvre")

    def test_importes(self) -> None:
        self.assertEqual(qc6.precios_en(reglas.plegar("Guía 19,90 € y 1.378,50 € o $19.90 o 49 zł o 3.000 EUR")), [19.9, 1378.5, 19.9, 49.0, 3000.0])
        self.assertEqual(qc6.precios_en(reglas.plegar("14 días, 30 mapas y 5 bonus")), [])
        self.assertEqual(qc6._importe("1 378"), 1378.0)


class PruebasIdioma(unittest.TestCase):
    def test_detecta_los_siete_idiomas(self) -> None:
        casos = {"es": "Una pausa laboral no es un hueco: es un relato que se puede contar con una guía",
                 "it": "Un planner settimanale dei pasti con la lista della spesa già pronta per la tua settimana",
                 "pl": "Arkusz: koszt, cena minimalna i marża w jednej tabeli dla każdego produktu",
                 "en": "Twenty conversation cards for a quiet evening together with your partner",
                 "fr": "Des fiches de mobilité de 10 minutes pour les pauses dans votre journée",
                 "de": "Arbeitsmappe als PDF: Fragen vor einem schwierigen Gespräch mit dem Partner",
                 "ro": "Un tabel pentru costurile unui produs handmade și pentru prețul de vânzare"}
        for esperado, texto in casos.items():
            self.assertEqual(qc6.detectar_idioma(texto)["mejor"], esperado, texto)

    def test_texto_muy_corto_es_inconcluso(self) -> None:
        self.assertIsNone(qc6.detectar_idioma("OK")["mejor"])

    def test_idioma_de_locale(self) -> None:
        self.assertEqual(qc6.idioma_de_locale("pl-PL"), "pl")


class PruebasComparacionDeTexto(unittest.TestCase):
    def test_exacto_solo_diacriticos_difuso_y_falta(self) -> None:
        ocr = "Arkusz: koszt, cena minimalna i marza w jednej tabeli. Gwarancja 14 dni • 19,90 zl"
        c = qc6.comparar_texto(["Arkusz: koszt, cena minimalna i marża w jednej tabeli.", "Gwarancja 14 dni · 19,90 zł", "Pobierz za darmo"], ocr, [ocr])
        self.assertEqual(c["exactos"], [])
        self.assertEqual(len(c["solo_diacriticos"]), 2)  # solo coinciden sin diacríticos
        self.assertEqual(c["faltan"], ["Pobierz za darmo"])

    def test_la_puntuacion_y_los_simbolos_no_cuentan(self) -> None:
        c = qc6.comparar_texto(["Gwarancja 14 dni · 19,90 zł"], "Gwarancja 14 dni • 19,90 zł", ["Gwarancja 14 dni • 19,90 zł"])
        self.assertEqual((c["exactos"], c["solo_diacriticos"], c["faltan"]), (["Gwarancja 14 dni · 19,90 zł"], [], []))

    def test_una_errata_se_marca_como_difusa(self) -> None:
        c = qc6.comparar_texto(["Koszt, cena minimalna"], "Koszt cena minimalma", ["Koszt cena minimalma"])
        self.assertEqual(c["difusos"], ["Koszt, cena minimalna"])

    def test_lineas_sin_explicar(self) -> None:
        c = qc6.comparar_texto(["Koszt, cena minimalna"], "Koszt cena minimalna SHUTTERSTOCK", ["Koszt cena minimalna", "SHUTTERSTOCK"])
        self.assertEqual(c["lineas_sin_explicar"], ["SHUTTERSTOCK"])

    def test_el_html_fuente_confirma_los_diacriticos_que_el_ocr_no_ve(self) -> None:
        esperado = ["Arkusz: koszt, cena minimalna i marża w jednej tabeli."]
        sin_html = qc6.punto_texto(ctx(esperado=esperado), ["Arkusz: koszt, cena minimalna i marza w jednej tabeli."], True)
        con_html = qc6.punto_texto(ctx(esperado=esperado, texto_fuente="ARKUSZ STUDIO Arkusz: koszt, cena minimalna i marża w jednej tabeli."), ["Arkusz: koszt, cena minimalna i marza w jednej tabeli."], True)
        self.assertEqual(sin_html["estado"], "revisar")
        self.assertEqual(con_html["estado"], "ok")
        # el HTML no salva una errata de letras: solo los diacríticos
        errata = qc6.punto_texto(ctx(esperado=esperado, texto_fuente=esperado[0]), ["Arkusz: koszt, cena minimalma i marza w jednej tabeli."], True)
        self.assertEqual(errata["estado"], "revisar")

    def test_texto_de_html_ignora_estilos_y_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "a.html"
            h.write_text("<html><head><title>x</title><style>.a{content:'no'}</style></head><body><h1>Marża &amp; cena</h1><script>var a=1</script><p>Dwa</p></body></html>", encoding="utf-8")
            self.assertEqual(qc6.texto_de_html(h), "Marża & cena Dwa")


class PruebasPuntos(Archivo):
    """Cada punto con motores falsos: ok, revisar y falla."""

    def evaluar(self, ocr, c: qc6.Contexto | None = None, **mot) -> dict:
        return qc6.evaluar_pieza(self.png(), c or ctx(), motores(ocr=ocr, **mot))

    def punto(self, p: dict, pid: str) -> dict:
        return next(x for x in p["puntos"] if x["id"] == pid)

    def test_pieza_limpia_es_ok_en_los_seis(self) -> None:
        p = self.evaluar(["Arkusz: koszt, cena minimalna i marża w jednej tabeli."], ctx(esperado=["Arkusz: koszt, cena minimalna i marża w jednej tabeli."]))
        self.assertEqual(p["estado"], "ok", json.dumps(p["puntos"], ensure_ascii=False))
        self.assertEqual([x["id"] for x in p["puntos"]], [i for i, _, _ in qc6.PUNTOS])
        self.assertFalse(self.punto(p, "QC1-audio")["aplica"])

    def test_texto_ausente_o_con_errata(self) -> None:
        esperado = ["Arkusz: koszt, cena minimalna"]
        self.assertEqual(self.punto(self.evaluar(["otra cosa"], ctx(esperado=esperado)), "QC3-texto")["estado"], "falla")
        self.assertEqual(self.punto(self.evaluar(["Arkusz koszt cena minimalma"], ctx(esperado=esperado)), "QC3-texto")["estado"], "revisar")
        self.assertEqual(self.punto(self.evaluar(["Arkusz �koszt, cena minimalna"], ctx(esperado=esperado)), "QC3-texto")["estado"], "falla")

    def test_sin_copy_esperado_no_hay_verde(self) -> None:
        self.assertEqual(self.punto(self.evaluar(["Arkusz: koszt, cena minimalna"]), "QC3-texto")["estado"], "revisar")

    def test_sin_ocr_nada_sale_verde(self) -> None:
        p = qc6.evaluar_pieza(self.png(), ctx(esperado=["Koszt"]), qc6.Motores(personas=None))
        for pid in ("QC3-texto", "QC4-caras-manos"):
            self.assertEqual(self.punto(p, pid)["estado"], "revisar", pid)
        self.assertIn(p["estado"], ("revisar", "falla"))

    def test_idioma_equivocado_y_mezcla(self) -> None:
        en = "The template is easy to use and the guide is for your team with a price and the template"
        self.assertEqual(self.punto(self.evaluar([en]), "QC2-idioma")["estado"], "falla")
        mezcla = "Arkusz: koszt, cena minimalna i marża w jednej tabeli dla Ciebie oraz jak to zrobić. The template and the guide for your team with the price"
        self.assertEqual(self.punto(self.evaluar([mezcla]), "QC2-idioma")["estado"], "revisar")
        corto = self.punto(self.evaluar(["Koszt cena"]), "QC2-idioma")
        self.assertEqual(corto["estado"], "revisar")
        self.assertIn("demasiado corto", corto["detalle"])

    def test_caras_y_manos(self) -> None:
        def con(d, **c):
            return self.punto(self.evaluar(["Koszt cena minimalna i marża w jednej tabeli"], ctx(**c), personas=lambda _p: d), "QC4-caras-manos")
        self.assertEqual(con({"rostros": 0, "personas": 0, "manos": 0})["estado"], "ok")
        self.assertEqual(con({"rostros": 0, "personas": 0, "manos": 2})["estado"], "revisar")
        self.assertEqual(con({"rostros": 1, "personas": 1, "manos": 0})["estado"], "revisar")
        self.assertEqual(con({"rostros": 1, "personas": 1, "manos": 0}, macro_nicho="salud")["estado"], "falla")
        self.assertEqual(con({"rostros": 0, "personas": 1, "manos": 0}, macro_nicho="relaciones")["estado"], "falla")

    def test_material_ajeno(self) -> None:
        def con(texto, **c):
            return self.punto(self.evaluar([texto], ctx(**c)), "QC5-material-ajeno")["estado"]
        self.assertEqual(con("Koszt, cena minimalna i marża"), "ok")
        self.assertEqual(con("Koszt i cena © Shutterstock"), "falla")
        self.assertEqual(con("Kupuj na Duolingo"), "revisar")
        self.assertEqual(con("Kupuj na Duolingo", permitidos=["Duolingo"]), "ok")
        self.assertEqual(con("Lingua Chiara 520 mappe", prohibidos=["Lingua Chiara"]), "falla")
        self.assertEqual(con("As seen on Forbes"), "falla")
        self.assertEqual(con("Más en www.ejemplo.com"), "revisar")
        self.assertEqual(con("Mappa del Francese™"), "revisar")

    def test_precios_y_promesas(self) -> None:
        def con(texto, **c):
            return self.punto(self.evaluar([texto], ctx(**c)), "QC6-precios-promesas")
        self.assertEqual(con("Arkusz z przykładem krok po kroku")["estado"], "ok")
        self.assertEqual(con("Arkusz 19,90 zł", precio_visible=False)["estado"], "falla")
        self.assertEqual(con("Arkusz 19,90 zł", precio_visible=True, precios_oferta=[19.9])["estado"], "ok")
        self.assertEqual(con("Arkusz 29,90 zł", precio_visible=True, precios_oferta=[19.9])["estado"], "falla")
        self.assertEqual(con("Arkusz 19,90 zł")["estado"], "revisar")
        self.assertEqual(con("Schudnij 10 kg w miesiąc")["estado"], "falla")
        self.assertEqual(con("Ganá 3.000 al mes", locale="es-ES")["estado"], "falla")
        self.assertEqual(con("Dostaniesz arkusz", claims_prohibidos=["Dostaniesz arkusz"])["estado"], "falla")
        self.assertEqual(con("Solo hoy: quedan 3 plazas", locale="es-ES")["estado"], "falla")

    def test_archivo_inexistente_falla_en_los_seis(self) -> None:
        p = qc6.evaluar_pieza(self.dir / "no-existe.png", ctx(), motores())
        self.assertEqual(p["estado"], "falla")
        self.assertTrue(all(x["estado"] == "falla" for x in p["puntos"]))

    def test_tipo_no_soportado(self) -> None:
        r = self.dir / "a.txt"
        r.write_text("x")
        with self.assertRaises(qc6.ErrorUso):
            qc6.evaluar_pieza(r, ctx(), motores())


class PruebasAudioConMotoresFalsos(Archivo):
    def video(self) -> Path:
        r = self.dir / "v.mp4"
        r.write_bytes(b"no es un video real: los motores son falsos")
        return r

    def audio(self, c, sonda, silencios=None, transcripcion=None) -> dict:
        m = motores(ocr=["Koszt cena minimalna i marża w jednej tabeli"], sonda=lambda _p: sonda, silencios=lambda _p: silencios, transcribir=lambda _p: transcripcion)
        p = qc6.evaluar_pieza(self.video(), c, m)
        return next(x for x in p["puntos"] if x["id"] == "QC1-audio")

    def test_audio_sano(self) -> None:
        self.assertEqual(self.audio(ctx(), {"tiene_audio": True, "duracion_video": 10.0, "duracion_audio": 10.1}, {"silencios": []})["estado"], "ok")

    def test_sin_audio(self) -> None:
        sonda = {"tiene_audio": False, "duracion_video": 10.0, "duracion_audio": None}
        self.assertEqual(self.audio(ctx(), sonda)["estado"], "revisar")
        self.assertEqual(self.audio(ctx(hablado="Una línea"), sonda)["estado"], "falla")

    def test_desfase(self) -> None:
        sonda = lambda d: {"tiene_audio": True, "duracion_video": 10.0, "duracion_audio": 10.0 + d}  # noqa: E731
        self.assertEqual(self.audio(ctx(), sonda(0.6), {"silencios": []})["estado"], "revisar")
        self.assertEqual(self.audio(ctx(), sonda(2.5), {"silencios": []})["estado"], "falla")

    def test_cortes_de_audio(self) -> None:
        sonda = {"tiene_audio": True, "duracion_video": 10.0, "duracion_audio": 10.0}
        self.assertEqual(self.audio(ctx(), sonda, {"silencios": [{"inicio": 4.0, "fin": 4.9, "duracion": 0.9}]})["estado"], "revisar")
        self.assertEqual(self.audio(ctx(), sonda, {"silencios": [{"inicio": 4.0, "fin": 7.0, "duracion": 3.0}]})["estado"], "falla")
        # una pausa al principio o al final no es un corte
        self.assertEqual(self.audio(ctx(), sonda, {"silencios": [{"inicio": 0.0, "fin": 1.2, "duracion": 1.2}, {"inicio": 9.0, "fin": None, "duracion": None}]})["estado"], "ok")
        self.assertEqual(self.audio(ctx(hablado="algo"), sonda, {"silencios": [{"inicio": 0.0, "fin": None, "duracion": None}]})["estado"], "falla")
        # un audio que se apaga 3 s antes del final se revisa
        self.assertEqual(self.audio(ctx(), sonda, {"silencios": [{"inicio": 7.0, "fin": None, "duracion": None}]})["estado"], "revisar")

    def test_audio_contra_guion(self) -> None:
        sonda = {"tiene_audio": True, "duracion_video": 5.0, "duracion_audio": 5.0}
        guion = "Una pausa laboral no es un hueco. Es un relato que se puede contar."
        self.assertEqual(self.audio(ctx(hablado=guion), sonda, {"silencios": []}, {"idioma": "es", "texto": "Una pausa laboral no es un hueco, es un relato que se puede contar."})["estado"], "ok")
        self.assertEqual(self.audio(ctx(hablado=guion), sonda, {"silencios": []}, {"idioma": "es", "texto": "Una pausa laboral no es un hueco, es un relato"})["estado"], "revisar")
        self.assertEqual(self.audio(ctx(hablado=guion), sonda, {"silencios": []}, {"idioma": "es", "texto": "Compra ahora esta oferta increíble de cursos"})["estado"], "falla")
        self.assertEqual(self.audio(ctx(hablado=guion), sonda, {"silencios": []}, None)["estado"], "revisar")

    def test_el_idioma_del_audio_manda_sobre_el_texto(self) -> None:
        sonda = {"tiene_audio": True, "duracion_video": 5.0, "duracion_audio": 5.0}
        m = motores(ocr=["Koszt cena minimalna i marża w jednej tabeli"], sonda=lambda _p: sonda, silencios=lambda _p: {"silencios": []},
                    transcribir=lambda _p: {"idioma": "es", "texto": "Una pausa laboral no es un hueco, es un relato que se puede contar."})
        p = qc6.evaluar_pieza(self.video(), ctx(), m)
        self.assertEqual(next(x for x in p["puntos"] if x["id"] == "QC2-idioma")["estado"], "falla")


class PruebasSalidaYL1(Archivo):
    def test_checks_l1_tienen_la_forma_del_esquema_qa(self) -> None:
        import jsonschema
        esquema = json.loads((RAIZ / "contratos" / "qa.schema.json").read_text(encoding="utf-8"))["properties"]["checks_l1"]
        p = qc6.evaluar_pieza(self.png(), ctx(esperado=[T_OK]), motores(ocr=[T_OK]))
        rep = qc6.reporte([p], motores=motores(), locale="pl-PL")
        jsonschema.validate(rep["checks_l1"], esquema)
        self.assertEqual({c["check_id"] for c in rep["checks_l1"]}, {"D6-L1-02", "D6-L1-06", "D6-L1-07", "D6-L1-08"})

    def test_revisar_no_cuenta_como_verde_y_falla_es_fail(self) -> None:
        ok = qc6.evaluar_pieza(self.png(), ctx(esperado=[T_OK]), motores(ocr=[T_OK]))
        revisar = qc6.evaluar_pieza(self.png("r.png"), ctx(ad_name="r", esperado=[T_OK]), motores(ocr=[T_OK.replace("minimalna", "minimalma")]))
        falla = qc6.evaluar_pieza(self.png("f.png"), ctx(ad_name="f", esperado=[T_OK]), motores(ocr=["otra cosa distinta"]))
        c = {x["check_id"]: x for x in qc6.reporte([ok], motores=motores(), locale="pl-PL")["checks_l1"]}
        self.assertTrue(all(x["resultado"] == "pass" for x in c.values()), c)
        c = {x["check_id"]: x for x in qc6.reporte([ok, revisar], motores=motores(), locale="pl-PL")["checks_l1"]}
        self.assertEqual(c["D6-L1-06"]["resultado"], "no_aplica")
        self.assertIn("REVISAR", c["D6-L1-06"]["detalle"])
        c = {x["check_id"]: x for x in qc6.reporte([ok, revisar, falla], motores=motores(), locale="pl-PL")["checks_l1"]}
        self.assertEqual(c["D6-L1-06"]["resultado"], "fail")
        self.assertEqual(qc6.resumen([ok, revisar, falla]), {"ok": 1, "revisar": 1, "falla": 1, "total": 3, "estado": "falla"})


class PruebasModoSimulado(Archivo):
    def test_simular_no_ejecuta_ningun_proceso_externo(self) -> None:
        sim = self.dir / "sim.json"
        sim.write_text(json.dumps({"ocr": ["Koszt cena minimalna i marża"], "personas": {"rostros": 0, "personas": 0, "manos": 0}}), encoding="utf-8")
        salida = self.dir / "qc6.json"
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("no debe ejecutarse nada externo")), mock.patch.object(shutil, "which", return_value=None):
            buf = io.StringIO()
            with redirect_stdout(buf):
                codigo = qc6.main(["pieza", str(self.png()), "--locale", "pl-PL", "--esperado", "Koszt cena minimalna i marża", "--simular", "--simulado", str(sim),
                                   "--json", "--salida", str(salida)])
        self.assertEqual(codigo, 0)
        rep = json.loads(buf.getvalue())
        self.assertEqual(rep["modo"], "simulado")
        self.assertEqual(rep["resumen"]["estado"], "ok")
        self.assertTrue(all(c["resultado"] == "no_aplica" and c["detalle"].startswith("SIMULADO") for c in rep["checks_l1"]))
        self.assertEqual(json.loads(salida.read_text(encoding="utf-8"))["modo"], "simulado")

    def test_simular_sin_datos_nunca_da_ok_en_lo_que_necesita_motor(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            qc6.main(["pieza", str(self.png()), "--locale", "pl-PL", "--esperado", "Koszt", "--simular", "--json"])
        p = json.loads(buf.getvalue())["piezas"][0]
        estados = {x["id"]: x["estado"] for x in p["puntos"]}
        self.assertEqual(estados["QC3-texto"], "revisar")
        self.assertEqual(estados["QC4-caras-manos"], "revisar")

    def test_simular_detecta_un_audio_en_otro_idioma(self) -> None:
        v = self.dir / "v.mp4"
        v.write_bytes(b"x")
        sim = self.dir / "sim.json"
        sim.write_text(json.dumps({"ocr": ["Koszt cena minimalna i marża w jednej tabeli"], "personas": {}, "sonda": {"tiene_audio": True, "duracion_video": 5, "duracion_audio": 5},
                                   "silencios": {"silencios": []}, "transcripcion": {"idioma": "en", "texto": "the template is for your team and the guide"}}), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = qc6.main(["pieza", str(v), "--locale", "pl-PL", "--simular", "--simulado", str(sim), "--json"])
        self.assertEqual(codigo, 3)
        self.assertEqual(json.loads(buf.getvalue())["resumen"]["falla"], 1)


class PruebasCLI(Archivo):
    def correr(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            codigo = qc6.main(list(args))
        return codigo, out.getvalue(), err.getvalue()

    def test_sin_locale_es_error_de_uso(self) -> None:
        codigo, _, err = self.correr("pieza", str(self.png()), "--simular")
        self.assertEqual(codigo, 2)
        self.assertIn("locale", err)

    def test_tipo_no_soportado_sale_2(self) -> None:
        t = self.dir / "a.txt"
        t.write_text("x")
        self.assertEqual(self.correr("pieza", str(t), "--locale", "pl-PL", "--simular")[0], 2)

    def test_estricto_convierte_revisar_en_3(self) -> None:
        self.assertEqual(self.correr("pieza", str(self.png()), "--locale", "pl-PL", "--simular")[0], 0)
        self.assertEqual(self.correr("pieza", str(self.png()), "--locale", "pl-PL", "--simular", "--estricto")[0], 3)

    def test_motores(self) -> None:
        codigo, out, _ = self.correr("motores", "--json")
        self.assertEqual(codigo, 0)
        self.assertIn("ocr_vision", json.loads(out))

    def test_archivo_faltante_falla_con_3(self) -> None:
        self.assertEqual(self.correr("pieza", str(self.dir / "no.png"), "--locale", "pl-PL", "--simular")[0], 3)

    def test_guion_y_copies(self) -> None:
        guion = self.dir / "g.md"
        guion.write_text("| Línea hablada (o titular, si es estático) | Una pausa laboral no es un hueco. [claim: x] |\n", encoding="utf-8")
        self.assertEqual(qc6.hablado_de_guion(guion.read_text(encoding="utf-8")), "Una pausa laboral no es un hueco.")
        esperado, permitidos = qc6.esperado_de_copies(copies_de_prueba("pl-PL", "Gancho", "Apoyo"), "c01-koszt_img_h1_v1")
        self.assertEqual((esperado, permitidos), (["Gancho", "Apoyo"], ["Arkusz Studio"]))
        self.assertEqual(qc6.esperado_de_copies({"x": {"texto_en_pieza": "Hola"}}, "x"), (["Hola"], []))


# ============================================================================================ con motores reales
@unittest.skipUnless(HAY_SWIFT and hay_navegador(), "sin Vision (macOS+swiftc) o sin Chrome/Brave")
class PruebasRealesImagen(Archivo):
    def lote(self, copies: dict, **extra) -> dict:
        d6 = self.dir / "oferta" / "06-creativos"
        d6.mkdir(parents=True)
        renderizar_estatico(copies, d6)
        ad = copies["anuncios"][0]["ad_name"]
        (d6 / "paquete.json").write_text(json.dumps({"anuncios": [{"ad_name": ad, "assets": [{"archivo": f"assets/{ad}.png", "ratio": "4:5"}]}]}), encoding="utf-8")
        (self.dir / "oferta" / "mercado.json").write_text(json.dumps({"locale": copies["idioma"]}), encoding="utf-8")
        (self.dir / "oferta" / "03-oferta").mkdir()
        (self.dir / "oferta" / "03-oferta" / "oferta.json").write_text(json.dumps({"macro_nicho": "dinero", "precio": {"lista": {"monto": 4900, "moneda": "PLN"}}}), encoding="utf-8")
        (d6 / "matriz.json").write_text(json.dumps({"anuncios": [{"ad_name": ad, "precio_visible": True, "presentador": "sin_rostro"}]}), encoding="utf-8")
        salida, salida_l1 = self.dir / "qc6.json", self.dir / "l1.json"
        out = io.StringIO()
        with redirect_stdout(out):
            codigo = qc6.main(["lote", "--oferta-dir", str(self.dir / "oferta"), "--json", "--salida", str(salida), "--salida-l1", str(salida_l1), *extra.get("args", [])])
        rep = json.loads(out.getvalue())
        rep["_codigo"] = codigo
        rep["_l1"] = json.loads(salida_l1.read_text(encoding="utf-8"))
        return rep

    def test_pieza_real_de_la_ruta_a_pasa_los_seis_puntos(self) -> None:
        rep = self.lote(copies_de_prueba("pl-PL", "Arkusz: koszt, cena minimalna i marża w jednej tabeli.", "Gwarancja 14 dni · 49,00 zł"))
        pieza = rep["piezas"][0]
        self.assertEqual(pieza["estado"], "ok", json.dumps(pieza["puntos"], ensure_ascii=False, indent=1))
        self.assertEqual(rep["modo"], "real")
        self.assertEqual({c["resultado"] for c in rep["_l1"]["checks"]}, {"pass"})
        self.assertEqual(rep["_codigo"], 0)

    def test_pieza_real_con_otro_idioma_falla(self) -> None:
        rep = self.lote(copies_de_prueba("pl-PL", "The template is easy to use and the guide is for your team with the price", "Money back guaranteed for your team"))
        pts = {x["id"]: x["estado"] for x in rep["piezas"][0]["puntos"]}
        self.assertEqual(pts["QC2-idioma"], "falla")
        self.assertEqual(pts["QC6-precios-promesas"], "falla")   # «guaranteed»
        self.assertEqual(rep["_codigo"], 3)

    def test_pieza_real_con_precio_distinto_al_de_la_oferta_falla(self) -> None:
        rep = self.lote(copies_de_prueba("pl-PL", "Arkusz: koszt, cena minimalna i marża w jednej tabeli.", "Tylko 79,00 zł"))
        pts = {x["id"]: x["estado"] for x in rep["piezas"][0]["puntos"]}
        self.assertEqual(pts["QC6-precios-promesas"], "falla")

    def test_el_ocr_real_funciona_como_motor_de_ocr_check(self) -> None:
        """OcrVision cumple el Protocol MotorOCR de scripts.creativos.ocr_check (el pendiente «OCR real» de S-B)."""
        from scripts.creativos import ocr_check
        png = renderizar_estatico(copies_de_prueba("pl-PL", "Arkusz: koszt, cena minimalna i łączna tabela.", "Gwarancja 14 dni"), self.dir)
        res = ocr_check.verificar([png], qc6.OcrVision("pl-PL"), {"gancho": "Arkusz: koszt, cena minimalna i łączna tabela."}, locale="pl-PL", macro_nicho="dinero")
        self.assertEqual(res["campos_sin_coincidir"], [])
        self.assertEqual(res["semaforo"], "verde")

    def test_detector_de_personas_corre_y_no_ve_a_nadie_en_un_afiche_de_texto(self) -> None:
        png = renderizar_estatico(copies_de_prueba("pl-PL", "Arkusz: koszt, cena minimalna", "Gwarancja 14 dni"), self.dir)
        self.assertEqual(qc6.personas_vision(png), {"rostros": 0, "personas": 0, "manos": 0})


@unittest.skipUnless(HAY_FFMPEG, "sin ffmpeg/ffprobe")
class PruebasRealesVideo(Archivo):
    def video(self, nombre: str, audio: str | None, dur_video: int = 4, filtro_audio: str | None = None) -> Path:
        out = self.dir / nombre
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=270x480:rate=10:duration={dur_video}"]
        if audio:
            cmd += ["-f", "lavfi", "-i", audio]
        if filtro_audio:
            cmd += ["-filter_complex", filtro_audio, "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"] + (["-c:a", "aac"] if audio else []) + [str(out)]
        correr(cmd)
        return out

    def estados(self, v: Path, **kw) -> dict[str, str]:
        m = qc6.motores_reales()
        m.ocr, m.personas, m.transcribir = None, None, None   # aquí solo importa el audio
        p = qc6.evaluar_pieza(v, ctx(**kw), m)
        return {x["id"]: x["estado"] for x in p["puntos"]}, {x["id"]: x for x in p["puntos"]}

    def test_audio_continuo_ok(self) -> None:
        e, _ = self.estados(self.video("ok.mp4", "sine=frequency=440:duration=4"))
        self.assertEqual(e["QC1-audio"], "ok")

    def test_video_sin_audio(self) -> None:
        v = self.video("mudo.mp4", None)
        self.assertEqual(self.estados(v)[0]["QC1-audio"], "revisar")
        self.assertEqual(self.estados(v, hablado="Una línea hablada")[0]["QC1-audio"], "falla")

    def test_corte_interior_de_audio(self) -> None:
        graf = "[1:a]atrim=0:2,asetpts=PTS-STARTPTS[a0];anullsrc=r=44100:cl=mono,atrim=0:3[a1];[2:a]atrim=0:2,asetpts=PTS-STARTPTS[a2];[a0][a1][a2]concat=n=3:v=0:a=1[a]"
        out = self.dir / "corte.mp4"
        correr(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=270x480:rate=10:duration=7", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-filter_complex", graf, "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)])
        e, det = self.estados(out)
        self.assertEqual(e["QC1-audio"], "falla", det["QC1-audio"]["detalle"])

    def test_audio_mas_largo_que_el_video(self) -> None:
        v = self.video("desfase.mp4", "sine=frequency=440:duration=7", dur_video=3)
        self.assertEqual(self.estados(v)[0]["QC1-audio"], "falla")

    def test_archivo_corrupto(self) -> None:
        mal = self.dir / "mal.mp4"
        mal.write_bytes(b"esto no es un mp4")
        self.assertEqual(self.estados(mal)[0]["QC1-audio"], "falla")

    def test_fotogramas_a_1_fps_con_tope(self) -> None:
        v = self.video("f.mp4", "sine=frequency=440:duration=12", dur_video=12)
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(len(qc6.fotogramas_ffmpeg(v, Path(td), 30)), 12)
            self.assertLessEqual(len(qc6.fotogramas_ffmpeg(v, Path(td) / "b", 5)), 5)


@unittest.skipUnless(HAY_FFMPEG and HAY_WHISPER and HAY_SAY and HAY_SWIFT and hay_navegador(), "sin ffmpeg, whisper-cli y modelo, say, Vision o Chrome")
class PruebasRealesConWhisper(Archivo):
    def test_audio_en_espanol_en_una_pieza_polaca_falla_y_en_es_ES_pasa(self) -> None:
        frase = "Una pausa laboral no es un hueco. Es un relato que se puede contar."
        aiff, mp4 = self.dir / "v.aiff", self.dir / "v.mp4"
        correr(["say", "-v", "Mónica", "-o", str(aiff), frase])
        png = renderizar_estatico(copies_de_prueba("es-ES", "Una pausa laboral no es un hueco: es un relato que se puede contar.", "Guía con guion de 30 segundos"), self.dir)
        correr(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "10", "-i", str(png), "-i", str(aiff), "-shortest", "-vf", "scale=540:-2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(mp4)])
        m = qc6.motores_reales()
        es = qc6.evaluar_pieza(mp4, ctx(locale="es-ES", macro_nicho="dinero", hablado=frase, esperado=["Una pausa laboral no es un hueco: es un relato que se puede contar.", "Guía con guion de 30 segundos"],
                                        permitidos=["Arkusz Studio"]), m)
        det = {x["id"]: x for x in es["puntos"]}
        self.assertEqual(det["QC1-audio"]["estado"], "ok", det["QC1-audio"]["detalle"])
        self.assertEqual(det["QC2-idioma"]["estado"], "ok", det["QC2-idioma"]["detalle"])
        self.assertGreaterEqual(det["QC1-audio"]["evidencia"]["similitud_audio_guion"], 0.85)
        pl = qc6.evaluar_pieza(mp4, ctx(locale="pl-PL", macro_nicho="dinero"), m)
        self.assertEqual(next(x for x in pl["puntos"] if x["id"] == "QC2-idioma")["estado"], "falla")


@unittest.skipUnless(HAY_PDFTOPPM and HAY_SWIFT and hay_navegador(), "sin pdftoppm, Vision o Chrome")
class PruebasRealesPdf(Archivo):
    def test_pdf_se_lee_por_paginas(self) -> None:
        html = self.dir / "a.html"
        html.write_text('<!doctype html><meta charset="utf-8"><style>body{font:700 40px Helvetica;margin:60px}</style><body><p>Arkusz: koszt, cena minimalna i łączna tabela.</p>'
                        '<p style="page-break-before:always">Gwarancja 14 dni dla łódzkich arkuszy</p></body>', encoding="utf-8")
        pdf = self.dir / "a.pdf"
        from tests.creativos.apoyo import rr
        correr([rr.buscar_navegador(), "--headless=new", "--disable-gpu", f"--print-to-pdf={pdf}", "--no-pdf-header-footer", f"file://{html}"])
        p = qc6.evaluar_pieza(pdf, ctx(esperado=["Arkusz: koszt, cena minimalna i łączna tabela.", "Gwarancja 14 dni dla łódzkich arkuszy"]), qc6.motores_reales())
        self.assertEqual(p["tipo"], "pdf")
        self.assertEqual(p["herramientas"]["cuadros_analizados"], "2")
        self.assertEqual(next(x for x in p["puntos"] if x["id"] == "QC3-texto")["estado"], "ok", json.dumps(p["puntos"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
