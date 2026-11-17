"""Pruebas de scripts/jurado/paquetes.py: determinismo con semilla, ceguera, una pieza por llamada, anclas, tope de llamadas y apagado."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import tempfile
import unittest
from pathlib import Path

from scripts.jurado import _comun as c
from scripts.jurado import paquetes as pq
from tests.jurado.apoyo import AHORA, anclas_fixture, armar_tanda, panel_fixture, piezas_fixture


def _bytes_de_arbol(raiz: Path) -> dict[str, str]:
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raiz.rglob("*")) if p.is_file()}


def _todo_el_texto(carpeta: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(carpeta.glob("paquete-*.json")))


class PruebaDeterminismo(unittest.TestCase):
    def test_misma_entrada_y_semilla_son_los_mismos_bytes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            armar_tanda(Path(a), semilla=11)
            armar_tanda(Path(b), semilla=11)
            self.assertEqual(_bytes_de_arbol(Path(a)), _bytes_de_arbol(Path(b)))

    def test_otra_semilla_cambia_el_orden_y_los_identificadores(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            _, m1, _ = armar_tanda(Path(a), semilla=11)
            _, m2, _ = armar_tanda(Path(b), semilla=12)
            self.assertNotEqual(m1["hash_orden"], m2["hash_orden"])
            self.assertNotEqual({o["pieza_id"] for o in m1["orden_llamadas"]}, {o["pieza_id"] for o in m2["orden_llamadas"]})

    def test_el_orden_de_los_archivos_de_entrada_no_altera_el_resultado(self):
        panel = panel_fixture(4)
        piezas = piezas_fixture(5)
        invertidas = copy.deepcopy(piezas)
        invertidas["piezas"].reverse()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            m1 = pq.armar(panel, piezas, anclas_fixture(), 5, Path(a), ahora=AHORA)
            m2 = pq.armar(panel, invertidas, anclas_fixture(), 5, Path(b), ahora=AHORA)
            self.assertEqual(m1["hash_orden"], m2["hash_orden"])

    def test_la_semilla_queda_registrada_y_auto_es_estable(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            _, m1, _ = armar_tanda(Path(a), semilla="auto")
            _, m2, _ = armar_tanda(Path(b), semilla="auto")
            self.assertEqual(m1["semilla_origen"], "derivada")
            self.assertEqual(m1["semilla"], m2["semilla"])
            self.assertIn("OF-TEST-01", m1["semilla"])
            self.assertEqual(m1["hash_orden"], m2["hash_orden"])
        with tempfile.TemporaryDirectory() as a:
            _, m, _ = armar_tanda(Path(a), semilla=99)
            self.assertEqual((m["semilla"], m["semilla_origen"], m["semilla_entero"]), (99, "explicita", 99))

    def test_sin_semilla_se_niega(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(c.ErrorJurado):
                pq.armar(panel_fixture(3), piezas_fixture(3), anclas_fixture(), None, Path(d))

    def test_el_orden_es_una_permutacion_completa_y_no_agrupa_por_pieza(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, _ = armar_tanda(Path(d), n_avatares=6, n_piezas=6)
            pares = [(o["avatar_id"], o["pieza_id"]) for o in m["orden_llamadas"]]
            self.assertEqual(len(pares), len(set(pares)))
            self.assertEqual(len(pares), (6 + 1) * (6 + 2))  # 6 avatares + línea base; 6 piezas + 2 anclas
            ordenado = sorted(pares)
            self.assertNotEqual(pares, ordenado)
            # sin racha larga de la misma pieza seguida (un orden agrupado delataría el barrido)
            racha = max(sum(1 for _ in g) for _, g in itertools.groupby(p[1] for p in pares))
            self.assertLess(racha, 5)


class PruebaCeguera(unittest.TestCase):
    def test_el_paquete_no_contiene_nombres_metricas_ni_formato(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, raiz = armar_tanda(Path(d))
            llave = json.loads((raiz / "privado" / "llave.json").read_text(encoding="utf-8"))
            texto = _todo_el_texto(raiz / "ciego").lower()
            for info in llave["piezas"].values():
                self.assertNotIn(info["ad_name"].lower(), texto)
                self.assertNotIn(info["id_origen"].lower(), texto)
            for info in llave["anclas"].values():
                self.assertNotIn(info["ancla_id"].lower(), texto)
            for palabra in ("ctr", "cpa", "roas", "impresiones", "ganadora", "perdedora", "ancla", "hook_tipo", "variante_formato", "pregunta-tarea",
                            "dolor-situacion", "imagen-pregunta", "_img_", "_v1", "semilla", "control_sintetico", "medida"):
                self.assertNotIn(palabra, texto, palabra)

    def test_cada_paquete_tiene_exactamente_una_pieza_y_los_mismos_campos(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, raiz = armar_tanda(Path(d))
            for o in m["orden_llamadas"]:
                paq = json.loads((raiz / o["archivo"]).read_text(encoding="utf-8"))
                self.assertIsInstance(paq["pieza"], dict)
                self.assertEqual(set(paq["pieza"]), {"pieza_id", "tipo", "texto_visible", "ruta_activo", "idioma"})
                self.assertEqual(set(paq), {"schema_version", "tipo", "paquete_id", "consigna_version", "consigna_sha256", "consigna", "avatar",
                                            "pieza", "formato_de_respuesta"})
                self.assertEqual(paq["paquete_id"], o["paquete_id"])

    def test_anclas_y_piezas_son_indistinguibles_en_el_paquete(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, raiz = armar_tanda(Path(d))
            llave = json.loads((raiz / "privado" / "llave.json").read_text(encoding="utf-8"))
            ids = list(llave["piezas"]) + list(llave["anclas"])
            self.assertTrue(all(i.startswith("P-") and len(i) == len(ids[0]) for i in ids))
            tipos = set()
            for o in m["orden_llamadas"]:
                paq = json.loads((raiz / o["archivo"]).read_text(encoding="utf-8"))
                tipos.add(tuple(sorted(paq["pieza"])))
            self.assertEqual(len(tipos), 1)

    def test_los_activos_se_copian_con_nombre_opaco(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            img = base / "origen" / "c00-secreto_img_h1_v1.png"
            img.parent.mkdir()
            img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
            piezas = piezas_fixture(3)
            piezas["piezas"][0].update({"tipo": "imagen", "ruta_activo": str(img)})
            panel = panel_fixture(3)
            m = pq.armar(panel, piezas, anclas_fixture(), 3, base / "tanda", ahora=AHORA)
            archivos = [p.name for p in (base / "tanda" / "ciego" / "activos").iterdir()]
            self.assertEqual(len(archivos), 1)
            self.assertRegex(archivos[0], r"^P-[0-9a-f]{8}\.png$")
            self.assertNotIn("secreto", _todo_el_texto(base / "tanda" / "ciego"))
            self.assertTrue(m["n_llamadas"] > 0)

    def test_verificar_detecta_una_fuga_agregada_a_mano(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, raiz = armar_tanda(Path(d))
            self.assertTrue(pq.verificar(raiz)["ok"])
            llave = json.loads((raiz / "privado" / "llave.json").read_text(encoding="utf-8"))
            nombre = next(iter(llave["piezas"].values()))["ad_name"]
            ruta = raiz / m["orden_llamadas"][0]["archivo"]
            paq = json.loads(ruta.read_text(encoding="utf-8"))
            paq["avatar"]["nota"] = f"viene de {nombre}"
            ruta.write_text(json.dumps(paq), encoding="utf-8")
            informe = pq.verificar(raiz)
            self.assertFalse(informe["ok"])
            self.assertTrue({h["check"] for h in informe["hallazgos"]} & {"C-CAMPOS", "C-FUGA-NOMBRE"})

    def test_verificar_detecta_una_palabra_de_metrica_en_la_consigna(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, raiz = armar_tanda(Path(d))
            ruta = raiz / m["orden_llamadas"][0]["archivo"]
            paq = json.loads(ruta.read_text(encoding="utf-8"))
            paq["consigna"] += " Esta pieza tuvo buen CTR."
            ruta.write_text(json.dumps(paq), encoding="utf-8")
            informe = pq.verificar(raiz)
            self.assertIn("C-FUGA-PALABRA", {h["check"] for h in informe["hallazgos"]})
            self.assertIn("C-CONSIGNA", {h["check"] for h in informe["hallazgos"]})

    def test_verificar_detecta_un_paquete_faltante(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, raiz = armar_tanda(Path(d))
            (raiz / m["orden_llamadas"][3]["archivo"]).unlink()
            self.assertIn("C-ARCHIVOS", {h["check"] for h in pq.verificar(raiz)["hallazgos"]})


class PruebaAnclas(unittest.TestCase):
    def test_cada_juez_ve_una_ancla_ganadora_y_una_perdedora(self):
        with tempfile.TemporaryDirectory() as d:
            _, m, raiz = armar_tanda(Path(d))
            llave = json.loads((raiz / "privado" / "llave.json").read_text(encoding="utf-8"))
            gan = {p for p, v in llave["anclas"].items() if v["veredicto_conocido"] == "ganadora"}
            per = {p for p, v in llave["anclas"].items() if v["veredicto_conocido"] == "perdedora"}
            for aid in m["avatares"] + [m["avatar_baseline"]]:
                vistas = {o["pieza_id"] for o in m["orden_llamadas"] if o["avatar_id"] == aid}
                self.assertTrue(vistas & gan and vistas & per, aid)
            self.assertEqual(m["anclas"], {"ganadoras": 1, "perdedoras": 1, "medidas": 2, "control_sintetico": 0})

    def test_sin_ancla_ganadora_o_perdedora_se_niega(self):
        for falta in ("ganadora", "perdedora"):
            anclas = anclas_fixture()
            anclas["anclas"] = [a for a in anclas["anclas"] if a["veredicto_conocido"] != falta]
            with tempfile.TemporaryDirectory() as d, self.assertRaises(c.ErrorJurado):
                pq.armar(panel_fixture(3), piezas_fixture(3), anclas, 1, Path(d))

    def test_un_ancla_medida_exige_fuente_y_metrica(self):
        anclas = anclas_fixture()
        anclas["anclas"][0]["evidencia"] = {"fuente": "", "metrica": ""}
        with tempfile.TemporaryDirectory() as d, self.assertRaises(c.ErrorJurado):
            pq.armar(panel_fixture(3), piezas_fixture(3), anclas, 1, Path(d))

    def test_un_control_sintetico_se_declara_como_tal(self):
        with tempfile.TemporaryDirectory() as d:
            m = pq.armar(panel_fixture(3), piezas_fixture(3), anclas_fixture("control_sintetico"), 1, Path(d), ahora=AHORA)
            self.assertEqual((m["anclas"]["medidas"], m["anclas"]["control_sintetico"]), (0, 2))

    def test_un_ancla_en_otro_idioma_se_niega_porque_se_delata(self):
        anclas = anclas_fixture()
        anclas["locale"] = "it-IT"
        with tempfile.TemporaryDirectory() as d, self.assertRaises(c.ErrorJurado):
            pq.armar(panel_fixture(3), piezas_fixture(3), anclas, 1, Path(d))


class PruebaReglas(unittest.TestCase):
    def test_sin_qa_a_ni_lint_la_pieza_se_rechaza_salvo_demo(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(c.ErrorJurado):
                pq.armar(panel_fixture(3), piezas_fixture(3, con_precondiciones=False), anclas_fixture(), 1, Path(d))
            m = pq.armar(panel_fixture(3), piezas_fixture(3, con_precondiciones=False), anclas_fixture(), 1, Path(d), demo=True, ahora=AHORA)
            self.assertTrue(m["demostracion"])

    def test_precondicion_en_fail_se_rechaza(self):
        piezas = piezas_fixture(3)
        piezas["piezas"][1]["precondiciones"]["lint"] = "FAIL"
        with tempfile.TemporaryDirectory() as d, self.assertRaises(c.ErrorJurado):
            pq.armar(panel_fixture(3), piezas, anclas_fixture(), 1, Path(d))

    def test_tope_de_llamadas_antes_de_gastar(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(c.ErrorJurado) as cm:
                pq.armar(panel_fixture(6), piezas_fixture(8), anclas_fixture(), 1, Path(d), parametros={"max_llamadas": 20})
            self.assertIn("max_llamadas", str(cm.exception))

    def test_el_video_queda_fuera_de_la_v01(self):
        piezas = piezas_fixture(3)
        piezas["piezas"][0].update({"tipo": "video", "ruta_activo": "x.mp4"})
        with tempfile.TemporaryDirectory() as d, self.assertRaises(c.ErrorJurado):
            pq.armar(panel_fixture(3), piezas, anclas_fixture(), 1, Path(d))

    def test_locale_distinto_o_pieza_repetida_o_una_sola_pieza(self):
        piezas = piezas_fixture(3)
        piezas["locale"] = "es-ES"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(c.ErrorJurado):
                pq.armar(panel_fixture(3), piezas, anclas_fixture(), 1, Path(d))
            p2 = piezas_fixture(3)
            p2["piezas"][1]["ad_name"] = p2["piezas"][0]["ad_name"]
            with self.assertRaises(c.ErrorJurado):
                pq.armar(panel_fixture(3), p2, anclas_fixture(), 1, Path(d))
            with self.assertRaises(c.ErrorJurado):
                pq.armar(panel_fixture(3), piezas_fixture(1), anclas_fixture(), 1, Path(d))

    def test_un_jurado_apagado_por_calibracion_no_arma_nada_salvo_reactivacion(self):
        cal = {"estado_global": "apagar"}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(c.ErrorJurado) as cm:
                pq.armar(panel_fixture(3), piezas_fixture(3), anclas_fixture(), 1, Path(d), calibracion=cal)
            self.assertIn("APAGADO", str(cm.exception))
            m = pq.armar(panel_fixture(3), piezas_fixture(3), anclas_fixture(), 1, Path(d), calibracion=cal, reactivado_por="dueño", ahora=AHORA)
            self.assertEqual(m["reactivado_por"], "dueño")

    def test_avatares_invalidos_se_niegan(self):
        panel = panel_fixture(3)
        panel["avatares"][0]["en_sus_palabras"] = []
        with tempfile.TemporaryDirectory() as d, self.assertRaises(c.ErrorJurado):
            pq.armar(panel, piezas_fixture(3), anclas_fixture(), 1, Path(d))

    def test_la_ficha_del_votante_no_lleva_procedencia_ni_ids_de_oferta(self):
        panel = panel_fixture(3)
        ficha = pq.ficha_avatar(panel["avatares"][0])
        self.assertNotIn("procedencia", ficha)
        self.assertNotIn("oferta_id", ficha)
        self.assertNotIn("frase_ids", json.dumps(ficha))


class PruebaCli(unittest.TestCase):
    def test_armar_y_verificar_por_cli(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "av.json").write_text(json.dumps(panel_fixture(3)), encoding="utf-8")
            (base / "pz.json").write_text(json.dumps(piezas_fixture(3)), encoding="utf-8")
            (base / "an.json").write_text(json.dumps(anclas_fixture()), encoding="utf-8")
            salida = base / "tanda"
            rc = pq.main(["armar", "--avatares", str(base / "av.json"), "--piezas", str(base / "pz.json"), "--anclas", str(base / "an.json"),
                          "--semilla", "5", "--salida", str(salida), "--ahora", AHORA])
            self.assertEqual(rc, 0)
            self.assertEqual(pq.main(["verificar", "--tanda-dir", str(salida)]), 0)
            self.assertTrue((salida / "privado" / "ceguera.json").is_file())
            man = json.loads((salida / "privado" / "manifiesto.json").read_text(encoding="utf-8"))
            self.assertEqual((man["semilla"], man["semilla_origen"]), (5, "explicita"))  # «5» desde la línea de comandos queda como número

    def test_falta_la_semilla_es_error_de_uso(self):
        with self.assertRaises(SystemExit):
            pq.main(["armar", "--avatares", "a", "--piezas", "b", "--anclas", "c", "--salida", "d"])


if __name__ == "__main__":
    unittest.main()
