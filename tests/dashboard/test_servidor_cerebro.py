"""``GET /api/cerebro`` (Cerebro v0): solo lectura, estados vacíos honestos, conteos sin texto y datos hostiles como datos."""
from __future__ import annotations

import json
import os

from dashboard import api_cerebro
from tests.dashboard.test_servidor_apoyo import HOSTIL, OFERTA, PruebaBase

DOC_DECISIONES = """# Decisiones y tareas del dueño

## 0. Prioridades

- [ ] abierta uno
- [ ] abierta dos
  - [x] hecha uno

## 1. Decisiones ya tomadas

| Tema | Decisión | Efecto |
|---|---|---|
| Mercado | todo el mundo | M1 |
| Meta | una cuenta | D7 |
| Pagos | luego | — |

## 2. Otra tabla que no cuenta

| a | b |
|---|---|
| 1 | 2 |
"""
DOC_ADOPCION = """# Decisiones — adopción

## Decisión madre
texto

## Decisiones tomadas

| # | Tema | Decisión |
|---|---|---|
| **J1** | Encaje | x |
| **J2** | Autonomía | y |

## Qué NO cambió
- cosa
"""


class PruebaCerebro(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.c = self.cliente()

    def leer(self) -> dict:
        r = self.c.get("/api/cerebro")
        self.assertEqual(r.estado, 200, r.cuerpo)
        return r.json()

    # -- vacío honesto --------------------------------------------------------------------------
    def test_sin_memoria_ni_documentos_dice_que_falta_y_no_crea_nada(self) -> None:
        antes = self.hash_arbol(self.raiz)
        j = self.leer()
        d = j["datos"]
        self.assertEqual(self.hash_arbol(self.raiz), antes, "leer no escribe nada")
        self.assertFalse((self.raiz / "empresa" / "memoria").exists())
        self.assertFalse(d["memoria"]["carpeta"]["existe"])
        self.assertEqual([f["existe"] for f in d["memoria"]["archivos"]], [False, False, False])
        self.assertEqual([f["clave"] for f in d["memoria"]["archivos"]], ["decisiones_dueno", "lecciones", "eventos"])
        self.assertTrue(all(not f["existe"] and f["decisiones"] is None and f["sha256"] is None for f in d["decisiones"]["fuentes"]))
        self.assertEqual(d["lecciones"]["memoria"], {"ruta": "empresa/memoria/lecciones.jsonl", "existe": False, "total": 0, "ultimas": []})
        self.assertEqual(d["decisiones"]["memoria"], {"ruta": "empresa/memoria/decisiones_dueno.jsonl", "existe": False, "total": 0, "vigentes": 0, "ultimas": []})
        self.assertEqual((d["jardin"]["propuestas"], d["jardin"]["existe"]), (0, False))
        self.assertTrue(any("empresa/memoria" in a for a in j["avisos"]))
        self.assertIn("empresa/memoria/lecciones.jsonl", j["fuente"])

    def test_metodos_que_escriben_no_existen(self) -> None:
        for metodo in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertEqual(self.c.llamar(metodo, "/api/cerebro", json_={}).estado, 405, metodo)
        self.assertEqual(self.c.get("/api/cerebro", token=False).estado, 403, "exige token como todo /api")

    # -- documentos de decisiones: solo enlaza y cuenta -----------------------------------------
    def test_decisiones_se_cuentan_sin_devolver_texto(self) -> None:
        self.escribir("docs/00-decisiones-y-tareas-del-dueno.md", DOC_DECISIONES)
        self.escribir("docs/_historial/mentor-sistema/decisiones-del-dueno.md", DOC_ADOPCION)
        fuentes = {f["clave"]: f for f in self.leer()["datos"]["decisiones"]["fuentes"]}
        a, b = fuentes["decisiones_y_tareas"], fuentes["decisiones_adopcion"]
        self.assertEqual((a["existe"], a["decisiones"], a["tareas_abiertas"], a["tareas_hechas"]), (True, 3, 2, 1))
        self.assertEqual((b["decisiones"], b["tareas_abiertas"], b["tareas_hechas"]), (2, 0, 0))
        self.assertEqual(a["ruta"], "docs/00-decisiones-y-tareas-del-dueno.md")
        self.assertEqual(len(a["sha256"]), 64)
        self.assertEqual(a["bytes"], len(DOC_DECISIONES.encode()))
        crudo = self.c.get("/api/cerebro").cuerpo.decode()
        self.assertNotIn("todo el mundo", crudo, "el texto de las decisiones no viaja")

    def test_contar_decisiones_casos_borde(self) -> None:
        self.assertEqual(api_cerebro.contar_decisiones(""), {"decisiones": 0, "tareas_abiertas": 0, "tareas_hechas": 0})
        self.assertEqual(api_cerebro.contar_decisiones("## Decisiones tomadas\n| a |\n|---|\n")["decisiones"], 0, "solo cabecera")
        self.assertEqual(api_cerebro.contar_decisiones("## Decisiones ya tomadas\n| a |\n|---|\n| 1 |\n| 2 |\n\n## Otro\n| a |\n|-|\n| 9 |\n")["decisiones"], 2)
        self.assertEqual(api_cerebro.contar_decisiones("- [X] mayúscula\n* [ ] asterisco\n- [] mal\n")["tareas_hechas"], 1)

    def test_documento_enorme_no_se_cuenta_y_avisa(self) -> None:
        self.escribir("docs/00-decisiones-y-tareas-del-dueno.md", "x" * (410 * 1024))
        j = self.leer()
        f = j["datos"]["decisiones"]["fuentes"][0]
        self.assertEqual((f["existe"], f["decisiones"], f["sha256"]), (True, None, None))
        self.assertTrue(any("supera" in a for a in j["avisos"]))

    # -- memoria --------------------------------------------------------------------------------
    def test_archivos_de_memoria_cuentan_lineas_y_ultima_fecha(self) -> None:
        self.escribir("empresa/memoria/decisiones_dueno.jsonl",
                      '{"id":"DEC-0001","ts":"2026-11-06T10:00:00Z","titulo":"a"}\n{"id":"DEC-0002","ts":"2026-11-07T11:00:00Z","titulo":"b"}\n')
        d = self.leer()["datos"]
        f = d["memoria"]["archivos"][0]
        self.assertEqual((f["existe"], f["lineas"], f["ultima_ts"]), (True, 2, "2026-11-07T11:00:00Z"))
        self.assertEqual(len(f["sha256"]), 64)
        self.assertTrue(d["memoria"]["carpeta"]["existe"])
        self.assertFalse(d["memoria"]["archivos"][1]["existe"])

    def test_decisiones_guardadas_distinguen_vigentes_de_reemplazadas(self) -> None:
        lineas = [{"id": "DEC-0001", "ts": "2026-11-06T10:00:00Z", "titulo": "Primera", "detalle": "x", "alcance": "sistema"},
                  {"id": "DEC-0002", "ts": "2026-11-07T10:00:00Z", "titulo": "Segunda", "reemplaza": "DEC-0001", "oferta_id": OFERTA},
                  {"id": "DEC-0003", "ts": "2026-11-08T10:00:00Z", "titulo": "Tercera", "vigente": False},
                  {"id": "DEC-0004", "ts": "2026-11-09T10:00:00Z", "titulo": HOSTIL * 20}]
        self.escribir("empresa/memoria/decisiones_dueno.jsonl", "".join(json.dumps(x) + "\n" for x in lineas))
        m = self.leer()["datos"]["decisiones"]["memoria"]
        self.assertEqual((m["existe"], m["total"], m["vigentes"]), (True, 4, 2))
        self.assertEqual({u["id"]: u["vigente"] for u in m["ultimas"]}, {"DEC-0001": False, "DEC-0002": True, "DEC-0003": False, "DEC-0004": True})
        self.assertLessEqual(len(m["ultimas"][-1]["titulo"]), 140)

    def test_linea_a_medias_en_memoria_no_rompe(self) -> None:
        self.escribir("empresa/memoria/lecciones.jsonl",
                      '{"id":"LEC-0001","ts":"2026-11-06T10:00:00Z","titulo":"t","leccion":"l","confianza":"B","etapa":"D3","evidencia":[{"ruta":"ofertas/x/qa/d3-v1.json","sha256":"ab"}]}\n{"id":"LEC-0002","ts":"2026')
        j = self.leer()
        m = j["datos"]["lecciones"]["memoria"]
        self.assertEqual([x["id"] for x in m["ultimas"]], ["LEC-0001"])
        self.assertEqual(m["ultimas"][0]["evidencia"][0]["ruta"], "ofertas/x/qa/d3-v1.json")
        self.assertTrue(any("no se pudieron leer" in a for a in j["avisos"]))

    def test_texto_hostil_en_lecciones_viaja_como_dato_recortado(self) -> None:
        linea = {"id": "LEC-0001", "ts": "2026-11-06T10:00:00Z", "titulo": HOSTIL * 10, "leccion": HOSTIL * 50, "etapa": "D3", "confianza": "B",
                 "evidencia": [{"ruta": HOSTIL, "sha256": "x"}, "no es objeto", {"sin_ruta": 1}]}
        self.escribir("empresa/memoria/lecciones.jsonl", json.dumps(linea) + "\n")
        u = self.leer()["datos"]["lecciones"]["memoria"]["ultimas"][0]
        self.assertLessEqual(len(u["titulo"]), 140)
        self.assertLessEqual(len(u["leccion"]), 300)
        self.assertEqual(len(u["evidencia"]), 1)
        self.assertTrue(u["leccion"].startswith("<script>"), "se entrega tal cual: el cliente lo escapa")

    # -- reglas ---------------------------------------------------------------------------------
    def test_reglas_resumen_de_solo_lectura(self) -> None:
        r = self.leer()["datos"]["reglas"]
        self.assertTrue(r["parametros"]["existe"])
        self.assertEqual(len(r["parametros"]["sha256"]), 64)
        self.assertGreaterEqual(r["parametros"]["grupos"], 1)
        self.assertGreaterEqual(r["parametros"]["claves"], r["parametros"]["hipotesis"])
        self.assertFalse(r["limites"]["sellado"], "el fixture no está sellado")
        self.assertEqual(r["sellos_compliance"]["archivos"], 2)
        self.assertIn("por_nivel", r["autonomia"])

    def test_reglas_ausentes_o_corruptas_no_rompen(self) -> None:
        (self.raiz / "empresa" / "parametros.yaml").write_text("grupos: [esto: no: es: yaml\n  - {", encoding="utf-8")
        os.unlink(self.raiz / "empresa" / "limites.yaml")
        j = self.leer()
        r = j["datos"]["reglas"]
        self.assertEqual((r["parametros"]["claves"], r["limites"]["existe"], r["limites"]["sellado"]), (0, False, False))
        self.assertTrue(any("parametros.yaml" in a for a in j["avisos"]))

    # -- lecciones de QA y post-mortems ---------------------------------------------------------
    def test_hallazgos_de_qa_por_oferta_y_marca_demo(self) -> None:
        qa = {"etapa": "D3", "version": "v1", "veredicto": "PASS", "aprendizajes_para_skill": ["Medir antes de afirmar", 5, "  "],
              "hallazgos": [{"check_id": "D3-H1", "patron_clave": "formato", "severidad": "MENOR", "descripcion": "Mayúsculas", "estado": "corregido_por_qa"},
                            "basura", {"check_id": "D3-H2", "descripcion": HOSTIL * 40}]}
        self.escribir(f"ofertas/{OFERTA}/qa/d3-v1.json", json.dumps(qa))
        self.escribir("ofertas/_ejemplo/qa/d3-v1.json", json.dumps(qa))
        self.escribir(f"ofertas/{OFERTA}/qa/roto.json", "{no es json")
        j = self.leer()
        q = j["datos"]["lecciones"]["qa"]
        reales = [h for h in q["hallazgos"] if h["oferta_id"] == OFERTA and h["archivo"] == "qa/d3-v1.json"]
        self.assertEqual([h["check_id"] for h in reales], ["D3-H1", "D3-H2"])
        self.assertTrue(all(h["demo"] is False for h in reales))
        self.assertTrue(all(h["demo"] is True for h in q["hallazgos"] if h["oferta_id"] == "_ejemplo"))
        self.assertLessEqual(max(len(h["descripcion"] or "") for h in q["hallazgos"]), 300)
        self.assertEqual([a["texto"] for a in q["aprendizajes"] if a["oferta_id"] == OFERTA], ["Medir antes de afirmar"])
        self.assertGreaterEqual(q["archivos"], 2)
        self.assertTrue(any("roto.json" in a for a in j["avisos"]), "un QA ilegible avisa y no tumba el resto")

    def test_tope_de_hallazgos_marca_truncado(self) -> None:
        qa = {"etapa": "D3", "hallazgos": [{"check_id": f"H{i}", "descripcion": "x"} for i in range(400)]}
        self.escribir(f"ofertas/{OFERTA}/qa/d3-v1.json", json.dumps(qa))
        q = self.leer()["datos"]["lecciones"]["qa"]
        self.assertEqual(len(q["hallazgos"]), 300)
        self.assertTrue(q["truncado"])

    def test_postmortem_se_resume_sin_inventar(self) -> None:
        pm = {"oferta_id": OFERTA, "generado_en": "2026-11-20T10:00:00Z", "origen_version": "maker", "veredicto": "FALLIDA", "causa_principal": "creativo-debil",
              "aprendizajes": ["Probar el gancho antes", 7, ""], "causas": [{"codigo": "x"}]}
        self.escribir(f"ofertas/{OFERTA}/08-operacion/postmortem.json", json.dumps(pm))
        p = [x for x in self.leer()["datos"]["lecciones"]["postmortems"] if x["oferta_id"] == OFERTA]
        self.assertEqual(len(p), 1)
        self.assertEqual((p[0]["veredicto"], p[0]["causa_principal"], p[0]["aprendizajes"]), ("FALLIDA", "creativo-debil", ["Probar el gancho antes"]))
        self.assertEqual(p[0]["ruta"], f"ofertas/{OFERTA}/08-operacion/postmortem.json")
        self.assertEqual(len(p[0]["sha256"]), 64)

    def test_sin_ofertas_con_qa_ni_postmortem_la_lista_es_vacia_no_inventada(self) -> None:
        for o in (self.raiz / "ofertas").iterdir():
            qa = o / "qa"
            if qa.is_dir():
                for f in qa.iterdir():
                    f.unlink()
        q = self.leer()["datos"]["lecciones"]
        self.assertEqual((q["qa"]["hallazgos"], q["qa"]["aprendizajes"], q["postmortems"]), ([], [], []))

    # -- jardín ---------------------------------------------------------------------------------
    def test_jardin_cuenta_propuestas_si_las_hubiera(self) -> None:
        self.escribir("empresa/memoria/jardin/2026-W45.json", "{}")
        self.escribir("empresa/memoria/jardin/2026-W46.json", "{}")
        j = self.leer()["datos"]["jardin"]
        self.assertEqual((j["existe"], j["propuestas"], j["ultima"]), (True, 2, "2026-W46.json"))

    # -- confinamiento --------------------------------------------------------------------------
    def test_un_enlace_simbolico_que_escapa_no_se_lee(self) -> None:
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "decisiones_dueno.jsonl").write_text('{"id":"X","ts":"2026-01-01T00:00:00Z"}\n', encoding="utf-8")
        os.symlink(fuera, self.raiz / "empresa" / "memoria")
        d = self.leer()["datos"]
        self.assertFalse(d["memoria"]["archivos"][0]["existe"], "una carpeta enlazada hacia fuera de la raíz no se sigue")
