"""Pruebas de scripts/jurado/avatares.py: panel desde la voz del cliente, límite de N, citas íntegras, sin biografía inventada y reemplazo con registro."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.jurado import _comun as c
from scripts.jurado import avatares as av
from tests.jurado.apoyo import AHORA, panel_fixture, voz_fixture


def _generar(voz=None, n=6, semilla=7, **kw):
    return av.generar_panel(voz or voz_fixture(), "a" * 64, "voz.json", n, semilla, ahora=AHORA, **kw)


class PruebaGeneracion(unittest.TestCase):
    def test_es_determinista_con_la_misma_semilla(self):
        self.assertEqual(_generar(semilla=7), _generar(semilla=7))

    def test_otra_semilla_cambia_las_preocupaciones_secundarias(self):
        a, b = _generar(semilla=1), _generar(semilla=2)
        self.assertNotEqual([x["preocupaciones_secundarias"] for x in a["avatares"]], [x["preocupaciones_secundarias"] for x in b["avatares"]])

    def test_el_techo_de_n_es_la_evidencia_y_no_se_rellena(self):
        voz = voz_fixture(n_temas=4)  # solo 4 preocupaciones reales
        panel = _generar(voz, n=10)
        reales = [a for a in panel["avatares"] if not a["baseline"]]
        self.assertEqual(len(reales), 4)
        self.assertEqual(panel["limite_n"]["pedido"], 10)
        self.assertEqual(panel["limite_n"]["generado"], 4)
        self.assertTrue(any("solo hay evidencia para 4" in a for a in panel["advertencias"]))

    def test_cada_avatar_cita_frases_reales_sin_alterarlas(self):
        voz = voz_fixture()
        panel = _generar(voz)
        por_id = {f["frase_id"]: f["texto_literal"] for f in voz["frases"]}
        for a in panel["avatares"]:
            self.assertTrue(a["en_sus_palabras"])
            for cita in a["en_sus_palabras"]:
                self.assertEqual(cita["texto"], por_id[cita["frase_id"]])
                self.assertTrue(cita["fuente_url"].startswith("https://"))
        self.assertEqual(av.validar_panel(panel, voz), [])

    def test_validar_detecta_una_cita_alterada_o_inexistente(self):
        voz = voz_fixture()
        panel = _generar(voz)
        mala = copy.deepcopy(panel)
        mala["avatares"][0]["en_sus_palabras"][0]["texto"] = "algo que nadie dijo"
        self.assertTrue(any("alterado" in p for p in av.validar_panel(mala, voz)))
        mala2 = copy.deepcopy(panel)
        mala2["avatares"][0]["en_sus_palabras"][0]["frase_id"] = "f-inventada"
        self.assertTrue(any("no existe" in p for p in av.validar_panel(mala2, voz)))

    def test_demografia_siempre_sin_dato_y_validar_exige_cita_si_alguien_la_rellena(self):
        panel = _generar()
        for a in panel["avatares"]:
            self.assertEqual(a["demografia"], {"edad_rango": None, "genero": None, "ocupacion": None, "origen": "sin_dato", "fuente": None})
        panel["avatares"][0]["demografia"]["edad_rango"] = "25-34"
        self.assertTrue(any("edad_rango" in p for p in av.validar_panel(panel)))
        panel["avatares"][0]["demografia"]["fuente"] = "dossier §4"
        self.assertEqual(av.validar_panel(panel), [])

    def test_el_lexico_de_compra_no_funda_un_avatar(self):
        panel = _generar(n=20)
        temas = {a["preocupacion_principal"]["tema"] for a in panel["avatares"] if a["preocupacion_principal"]}
        self.assertNotIn("lexico-solo", temas)

    def test_frases_sin_fuente_o_con_otro_locale_se_descartan_con_motivo(self):
        voz = voz_fixture()
        voz["frases"][0]["fuente_url"] = ""
        voz["frases"][1]["locale"] = "it-IT"
        panel = _generar(voz)
        motivos = {d["frase_id"]: d["motivo"] for d in panel["frases_descartadas"]}
        self.assertIn("sin fuente_url", motivos[voz["frases"][0]["frase_id"]])
        self.assertIn("otro locale", motivos[voz["frases"][1]["frase_id"]])

    def test_sin_ninguna_preocupacion_con_evidencia_se_niega(self):
        voz = voz_fixture(n_temas=0)
        with self.assertRaises(c.ErrorJurado):
            _generar(voz)

    def test_frase_id_repetido_es_error(self):
        voz = voz_fixture()
        voz["frases"][1]["frase_id"] = voz["frases"][0]["frase_id"]
        with self.assertRaises(c.ErrorJurado):
            _generar(voz)

    def test_el_escéptico_se_funda_en_una_objecion(self):
        panel = _generar(n=4)
        esc = next(a for a in panel["avatares"] if a["estilo_decision"] == "esceptico")
        self.assertIn("objecion", esc["preocupacion_principal"]["categorias"])

    def test_nivel_de_evidencia_segun_fuentes(self):
        panel = _generar(voz_fixture(fuentes=1))
        self.assertTrue(all(a["nivel_evidencia"] == "debil" for a in panel["avatares"] if not a["baseline"]))
        self.assertTrue(any("sesgo" in a for a in panel["advertencias"]))

    def test_n_invalido_o_estilo_desconocido(self):
        with self.assertRaises(c.ErrorJurado):
            _generar(n=0)
        with self.assertRaises(c.ErrorJurado):
            _generar(estilos=["artista_inventado"])

    def test_la_linea_base_no_tiene_perfil_y_no_cuenta_como_avatar_real(self):
        panel = panel_fixture(4, baseline=True)
        base = [a for a in panel["avatares"] if a["baseline"]]
        self.assertEqual(len(base), 1)
        self.assertIsNone(base[0]["preocupacion_principal"])
        self.assertEqual(len(av.activos(panel)), 4)
        self.assertEqual(len(av.activos(panel, con_baseline=True)), 5)


class PruebaReemplazo(unittest.TestCase):
    def setUp(self):
        self.voz = voz_fixture(n_temas=10)
        self.panel = _generar(self.voz, n=6)

    def test_sin_propuesta_de_la_calibracion_se_niega(self):
        with self.assertRaises(c.ErrorJurado):
            av.reemplazar_avatar(self.panel, self.voz, "a" * 64, "av-pl-PL-02", "motivo", {"propuestas_reemplazo": []}, "b" * 64, ahora=AHORA)

    def test_con_propuesta_retira_repone_y_no_reutiliza_ids(self):
        cal = {"propuestas_reemplazo": [{"avatar_id": "av-pl-PL-02"}]}
        nuevo, ev = av.reemplazar_avatar(self.panel, self.voz, "a" * 64, "av-pl-PL-02", "AUC propio bajo con 150 etiquetas", cal, "b" * 64, ahora=AHORA)
        viejo = next(a for a in nuevo["avatares"] if a["avatar_id"] == "av-pl-PL-02")
        self.assertEqual(viejo["estado"], "retirado")
        self.assertEqual(viejo["reemplazado_por"], ev["avatar_nuevo"])
        self.assertNotIn(ev["avatar_nuevo"], [a["avatar_id"] for a in self.panel["avatares"]])
        self.assertEqual(len(av.activos(nuevo)), len(av.activos(self.panel)))
        self.assertEqual(av.validar_panel(nuevo, self.voz), [])
        self.assertEqual(ev["origen"], "calibracion")
        self.assertEqual(ev["calibracion_sha256"], "b" * 64)
        usados = [a["preocupacion_principal"]["tema"] for a in av.activos(nuevo)]
        self.assertEqual(len(usados), len(set(usados)), "el repuesto no repite una preocupación ya cubierta")

    def test_reemplazo_manual_exige_motivo_largo(self):
        with self.assertRaises(c.ErrorJurado):
            av.reemplazar_avatar(self.panel, self.voz, "a" * 64, "av-pl-PL-02", "corto", forzar_manual=True, ahora=AHORA)
        nuevo, ev = av.reemplazar_avatar(self.panel, self.voz, "a" * 64, "av-pl-PL-02", "El dueño considera que repite a otro avatar", forzar_manual=True, ahora=AHORA)
        self.assertEqual(ev["origen"], "manual")

    def test_no_se_reemplaza_la_linea_base_ni_un_avatar_ya_retirado(self):
        panel = panel_fixture(4, baseline=True)
        with self.assertRaises(c.ErrorJurado):
            av.reemplazar_avatar(panel, voz_fixture(), "a" * 64, "av-pl-PL-rubrica", "x" * 30, forzar_manual=True, ahora=AHORA)

    def test_sin_temas_libres_no_se_repone(self):
        voz = voz_fixture(n_temas=3)
        panel = _generar(voz, n=3)
        with self.assertRaises(c.ErrorJurado):
            av.reemplazar_avatar(panel, voz, "a" * 64, "av-pl-PL-01", "m" * 30, forzar_manual=True, ahora=AHORA)
        nuevo, ev = av.reemplazar_avatar(panel, voz, "a" * 64, "av-pl-PL-01", "m" * 30, forzar_manual=True, sin_reposicion=True, ahora=AHORA)
        self.assertIsNone(ev["avatar_nuevo"])
        self.assertEqual(len(av.activos(nuevo)), 2)


class PruebaCli(unittest.TestCase):
    def test_generar_valida_y_deja_registro(self):
        with tempfile.TemporaryDirectory() as d:
            voz = Path(d) / "voz.json"
            voz.write_text(json.dumps(voz_fixture()), encoding="utf-8")
            salida = Path(d) / "jurado" / "avatares.json"
            self.assertEqual(av.main(["generar", "--voz", str(voz), "--n", "5", "--semilla", "3", "--salida", str(salida), "--ahora", AHORA]), 0)
            self.assertEqual(av.main(["validar", str(salida), "--voz", str(voz)]), 0)
            registro = (Path(d) / "jurado" / "registro_avatares.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(registro[0])["evento"], "generado")
            doc = json.loads(salida.read_text(encoding="utf-8"))
            doc["avatares"][0]["en_sus_palabras"][0]["texto"] = "alterado"
            salida.write_text(json.dumps(doc), encoding="utf-8")
            self.assertEqual(av.main(["validar", str(salida), "--voz", str(voz)]), 3)

    def test_voz_inexistente_sale_3(self):
        self.assertEqual(av.main(["generar", "--voz", "/no/existe.json", "--semilla", "1", "--salida", "/tmp/x.json"]), 3)


if __name__ == "__main__":
    unittest.main()
