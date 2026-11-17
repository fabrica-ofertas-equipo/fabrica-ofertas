"""Pruebas de la rutina «D2 sin la herramienta del video»: normalizar_biblioteca.py y verificar_competidores.py.

  .venv/bin/python -m unittest discover -s .claude/skills/d2-validacion/scripts/tests -p "test_*.py" -v
Sin red. Los crudos son SINTÉTICOS (nombres y títulos inventados, ids de 15 dígitos).
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SCRIPTS = AQUI.parent
SKILL = SCRIPTS.parent
RAIZ = SKILL.parents[2]
sys.path.insert(0, str(SCRIPTS))

import normalizar_biblioteca as NB  # noqa: E402
import params as P  # noqa: E402
import verificar_competidores as VCOMP  # noqa: E402

PARAMS, _ = P.cargar()
AHORA = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)
EP = int(AHORA.timestamp())


def ad(i: int, page: int, dias: int, titulo: str, moneda="EUR") -> dict:
    aid = f"{100000000000000 + i}"
    return {"id": aid, "page_id": str(page), "page_name": f"Página {page}", "ad_creative_link_title": titulo,
            "ad_delivery_start_time": EP - dias * 86400, "currency": moneda,
            "ad_snapshot_url": f"https://www.facebook.com/ads/library/?id={aid}"}


def crudo(qid, terminos, pais, ads, total, estado="ACTIVE", page_ids=None, limite=50):
    return {"schema_version": "1.0.0", "corrida_id": "2026-11-06-a", "qid": qid,
            "consulta": {"search_terms": terminos, "countries": [pais], "ad_active_status": estado, "limit": limite, "page_ids": page_ids},
            "capturado_en": "2026-11-06T10:00:00Z", "ruta": "A", "estimated_total_count": total, "ads": ads}


def escribir(carpeta: Path, docs: list[dict]) -> Path:
    d = carpeta / "2026-11-06-a"
    d.mkdir(parents=True)
    for doc in docs:
        (d / f"{doc['qid']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return d


def escenario() -> list[dict]:
    n = 0
    a1, a2 = [], []
    # 7 páginas: la 1 y la 2 aparecen en las dos consultas; títulos con variantes « | »
    for page in range(1, 8):
        for k in range(3):
            n += 1
            a1.append(ad(n, page, 100 - page * 5 - k, f"Calendario rate {page}-{k} | variante creativa {n}"))
    for page in (1, 2, 8):
        n += 1
        a2.append(ad(n, page, 30, f"Scadenzario {page}"))
    # consulta por la página 1 (completa: 4 anuncios vistos de 4 declarados)
    a3 = [x for x in a1 if x["page_id"] == "1"] + [ad(900, 1, 12, "Otro concepto")]
    return [crudo("it-calendario-rate", "calendario rate prestiti", "IT", a1, len(a1) + 30),
            crudo("it-scadenzario-rate", "scadenzario rate", "IT", a2, len(a2)),
            crudo("it-pag-1", "", "IT", a3, 4, page_ids=["1"]),
            crudo("it-inactivos", "rate", "IT", [ad(950, 9, 400, "Viejo")], 1, estado="INACTIVE")]


class Normalizar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = escribir(Path(self.tmp.name), escenario())

    def correr(self, semilla=7, excluir=()):
        return NB.procesar(NB.cargar_crudos(self.dir), AHORA, semilla, set(excluir), PARAMS)

    def test_portafolios_y_medicion(self):
        o = self.correr()
        pg = {x["page_id"]: x for x in o["paginas"]}
        self.assertNotIn("9", pg, "una consulta INACTIVE no entra al portafolio activo")
        self.assertEqual(pg["1"]["medicion"], "pagina_completa")
        self.assertFalse(pg["1"]["truncado"])
        self.assertEqual(pg["2"]["medicion"], "muestra")
        self.assertTrue(pg["2"]["truncado"], "sin consulta por la página, S_a es piso")
        self.assertGreaterEqual(pg["1"]["n_consultas"], 2)

    def test_consulta_truncada_por_total_mayor_que_lo_visto(self):
        o = self.correr()
        c = {x["qid"]: x for x in o["consultas"]}
        self.assertTrue(c["it-calendario-rate"]["truncado"], "total estimado 51 > 21 vistos: la muestra es un piso")
        self.assertFalse(c["it-scadenzario-rate"]["truncado"])

    def test_sonda_no_se_suma_y_marca_monocultivo(self):
        o = self.correr()
        self.assertTrue(all(s["no_sumar_totales"] for s in o["sonda"]))
        self.assertNotIn("total_global", json.dumps(o))
        self.assertTrue(any("no se suman" in a for a in o["advertencias"]))

    def test_seleccion_determinista_y_semilla_registrada(self):
        a, b = self.correr(semilla=7), self.correr(semilla=7)
        self.assertEqual(a["seleccion"], b["seleccion"])
        self.assertEqual(a["seleccion"]["semilla"], 7)
        self.assertEqual(len(a["seleccion"]["profundos"]), int(PARAMS["n_competidores_profundos"]))
        self.assertEqual(a["seleccion"]["profundos"][:2], ["1", "2"], "primero las páginas con más consultas y mayor antigüedad")
        self.assertEqual(len(a["seleccion"]["al_azar"]), int(PARAMS["competidores_al_azar"]))
        self.assertFalse(set(a["seleccion"]["al_azar"]) & set(a["seleccion"]["profundos"]))

    def test_urls_son_del_crudo_y_respetan_el_tope(self):
        o = self.correr()
        ids = {a["id"] for d in escenario() for a in d["ads"]}
        urls = o["seleccion"]["urls_snapshot"]
        self.assertLessEqual(len(urls), int(PARAMS["urls_snapshot_max_modo_humano"]))
        self.assertTrue(urls)
        for u in urls:
            self.assertIn(u["ad_id"], ids)
            self.assertTrue(u["snapshot_url"].endswith("?id=" + u["ad_id"]))
        por_pag = {}
        for u in urls:
            por_pag[u["page_id"]] = por_pag.get(u["page_id"], 0) + 1
        self.assertTrue(all(v <= int(PARAMS["snapshots_por_competidor"]) for v in por_pag.values()))

    def test_excluir_quita_paginas_no_producto(self):
        o = self.correr(excluir=["1", "2"])
        self.assertNotIn("1", o["seleccion"]["profundos"])
        self.assertNotIn("2", o["seleccion"]["profundos"])
        self.assertEqual(o["seleccion"]["excluidos_por_el_maker"], ["1", "2"])

    def test_segunda_pasada_sugerida_qid_y_tope(self):
        o = self.correr()
        s = o["seleccion"]["segunda_pasada_sugerida"]
        self.assertLessEqual(len(s), int(PARAMS["consultas_segunda_pasada_max"]))
        self.assertTrue(all(x["qid"].startswith("it-") for x in s))
        self.assertTrue(any(x["mide_la_pagina"] is False and len(x["page_ids"]) >= 1 for x in s) or len(o["seleccion"]["al_azar"]) == 0)

    def test_conceptos_estimados_ignoran_variantes_despues_de_la_barra(self):
        o = self.correr()
        pg = {x["page_id"]: x for x in o["paginas"]}
        self.assertLessEqual(pg["3"]["conceptos_estimados"], 3)

    def test_nombres_se_sanean(self):
        self.assertEqual(NB.sanear("Hola\n\x00 mundo   x"), "Hola mundo x")
        self.assertEqual(len(NB.sanear("a" * 500)), 80)

    def test_crudo_con_carpeta_distinta_del_corrida_id_falla(self):
        otra = Path(self.tmp.name) / "otra"
        (otra).mkdir()
        (otra / "x.json").write_text((self.dir / "it-scadenzario-rate.json").read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaises(Exception):
            NB.cargar_crudos(otra)

    def test_cli_no_sobrescribe_y_sale_0(self):
        out = Path(self.tmp.name) / "salida.json"
        cmd = [sys.executable, str(SCRIPTS / "normalizar_biblioteca.py"), str(self.dir), "--ahora", "2026-11-06T12:00:00Z", "--semilla", "3",
               "--salida", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=RAIZ)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(subprocess.run(cmd, capture_output=True, text=True, cwd=RAIZ).returncode, 2)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["seleccion"]["semilla"], 3)


def competidor(i: int, leido="dueno", **cambios) -> dict:
    aids = [f"{100000000000000 + i * 10 + k}" for k in (1, 2)]
    c = {"operador_id": f"op-0{i}", "page_id": f"90{i}", "tipo_anunciante": "producto_digital",
         "enlaces_verificacion": aids[:2],
         "anuncios": [{"id": a, "snapshot_url": f"https://www.facebook.com/ads/library/?id={a}", "hook": "pregunta sobre cuotas",
                       "promesa": "ordenar las cuotas del mes", "mecanismo_declarado": "calendario por colores", "tipo_mecanismo": "M3",
                       "claims": [{"texto_parafraseado": "sale de deudas rápido", "nivel_riesgo": "rojo", "prohibido_copiar": True}],
                       "estado_campos": {"hook": "observado", "promesa": "observado", "mecanismo_declarado": "observado"},
                       "evidencia": {"id": f"EV-0{i}", "url": f"https://www.facebook.com/ads/library/?id={a}", "fecha": "2026-11-06", "leido_por": leido}}
                      for a in aids]}
    c.update(cambios)
    return c


def doc4() -> dict:
    return {"competidores": [competidor(i) for i in range(1, 5)]}


class Competidores(unittest.TestCase):
    def test_cuatro_verificables_en_menos_de_15_min_pasa(self):
        r = VCOMP.verificar(doc4(), PARAMS)
        self.assertEqual((r["n_verificables"], r["falla"]), (4, []))
        self.assertLessEqual(r["minutos_estimados_dueno"], int(PARAMS["tiempo_verificacion_dueno_max_min"]))

    def test_tres_competidores_no_alcanzan(self):
        d = doc4()
        d["competidores"].pop()
        self.assertTrue(VCOMP.verificar(d, PARAMS)["falla"])

    def test_solo_titulo_del_conector_no_cuenta(self):
        d = doc4()
        d["competidores"][0] = competidor(1, leido="maker_titulo")
        r = VCOMP.verificar(d, PARAMS)
        self.assertEqual(r["n_verificables"], 3)
        self.assertTrue(r["falla"])

    def test_enlace_inventado_no_esta_en_el_crudo(self):
        ids = {a["id"] for c in doc4()["competidores"] for a in c["anuncios"]}
        ids.discard("100000000000011")
        r = VCOMP.verificar(doc4(), PARAMS, ids)
        self.assertTrue(any("NO_esta_en_el_crudo" in x for x in r["competidores"][0]["problemas"]))
        self.assertTrue(r["falla"])

    def test_snapshot_que_no_coincide_con_su_id_falla(self):
        d = doc4()
        d["competidores"][1]["anuncios"][0]["snapshot_url"] = "https://www.facebook.com/ads/library/?id=1"
        self.assertTrue(VCOMP.verificar(d, PARAMS)["competidores"][1]["problemas"])

    def test_verificar_mucho_cuesta_mas_de_15_min(self):
        d = doc4()
        d["competidores"] = [competidor(i) for i in range(1, 9)]
        r = VCOMP.verificar(d, PARAMS)
        self.assertTrue(any("min" in f for f in r["falla"]))

    def test_claim_rojo_sin_prohibido_copiar_falla(self):
        d = doc4()
        d["competidores"][2]["anuncios"][0]["claims"][0]["prohibido_copiar"] = False
        self.assertFalse(VCOMP.verificar(d, PARAMS)["competidores"][2]["verificable"])

    def test_campo_observado_sin_lectura_real_falla(self):
        d = doc4()
        d["competidores"][3] = competidor(4, leido="maker_titulo")
        r = VCOMP.verificar(d, PARAMS)
        self.assertTrue(any("observado_sin_snapshot_leido" in x for x in r["competidores"][3]["problemas"]))

    def test_pii_en_el_hook_falla(self):
        d = doc4()
        d["competidores"][0]["anuncios"][0]["hook"] = "escribe a ventas@ejemplo.invalid"
        r = VCOMP.verificar(d, PARAMS)
        self.assertTrue(any(x.startswith("PII") for x in r["competidores"][0]["problemas"]))

    def test_plantilla_ficha_competidor_pasa(self):
        ruta = SKILL / "templates" / "ficha_competidor.json"
        self.assertTrue(ruta.is_file())
        r = VCOMP.verificar(json.loads(ruta.read_text(encoding="utf-8")), PARAMS)
        self.assertEqual((r["n_verificables"] >= 4, r["falla"]), (True, []), r)


# ---------------------------------------------------------------- sembrados detectables por script
import re as _re  # noqa: E402
import veredicto as V  # noqa: E402
import verificar_citas as VC  # noqa: E402
import metricas as M  # noqa: E402


def _poner(doc, ruta, valor):
    toks = _re.findall(r"[^.\[\]]+|\[\d+\]", ruta)
    cur = doc
    for t in toks[:-1]:
        cur = cur[int(t[1:-1])] if t.startswith("[") else cur[t]
    ult = toks[-1]
    if ult.startswith("["):
        cur[int(ult[1:-1])] = valor
    else:
        cur[ult] = valor


def _aplicar(sembrado: dict) -> dict:
    docs = {nombre: json.loads((SKILL / ruta).read_text(encoding="utf-8")) for nombre, ruta in sembrado["base"].items() if ruta.endswith(".json")}
    for inj in sembrado["inyeccion"]:
        _poner(docs[inj["archivo"]], inj["ruta"], inj["valor"])
    return docs


def _sembrado(prefijo: str) -> dict:
    ruta = next((SKILL / "evals" / "sembrados").glob(prefijo + "-*.json"))
    return json.loads(ruta.read_text(encoding="utf-8"))


class SembradosDetectables(unittest.TestCase):
    def test_hay_19_sembrados_con_su_salida_esperada(self):
        archivos = sorted((SKILL / "evals" / "sembrados").glob("s*.json"))
        self.assertEqual(len(archivos), 19)
        ids = {json.loads(a.read_text(encoding="utf-8"))["id"] for a in archivos}
        self.assertEqual(ids, {f"S{i:02d}" for i in range(1, 20)})
        for a in archivos:
            d = json.loads(a.read_text(encoding="utf-8"))
            self.assertIn(d["severidad"], ("BLOQUEANTE", "MAYOR"))
            self.assertTrue(d["esperado_qa"]["hallazgos_minimos"], a.name)

    def test_el_caso_base_es_coherente(self):
        docs = {n: json.loads((SKILL / "templates" / n).read_text(encoding="utf-8")) for n in ("metricas_entrada.json", "validacion.json")}
        self.assertEqual(V.comprobar(docs["metricas_entrada.json"], docs["validacion.json"], PARAMS), [])

    def test_S01_S05_S07_S11_dan_veredicto_incoherente(self):
        for pre in ("s01", "s05", "s07", "s11"):
            d = _aplicar(_sembrado(pre))
            errs = V.comprobar(d["metricas_entrada.json"], d["validacion.json"], PARAMS)
            self.assertTrue(errs, f"{pre} debe ser detectado por veredicto.py comprobar")

    def test_S16_rojo_bajado_lo_rechaza_metricas(self):
        d = _aplicar(_sembrado("s16"))
        with self.assertRaises(P.ErrorValidacion):
            M.calcular(d["metricas_entrada.json"], PARAMS)

    def test_S09_pii_lo_detecta_verificar_citas(self):
        d = _aplicar(_sembrado("s09"))
        for f in d["voz_cliente.json"]["frases"]:
            f.pop("crudo_ref")  # sin crudo: las frases quedan «no verificables», pero la PII se detecta igual
        r = VC.verificar(d["voz_cliente.json"], "it-IT", None, PARAMS)
        self.assertTrue(any(f["problema"].startswith("PII") for f in r["fallas"]))

    def test_S02_cita_inventada_la_detecta_verificar_citas(self):
        d = _aplicar(_sembrado("s02"))
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            for f in d["voz_cliente.json"]["frases"]:
                ref = base / f["crudo_ref"]
                ref.parent.mkdir(parents=True, exist_ok=True)
                ref.write_text("Ciao a tutti. non riesco a capire quanto mi resta da pagare ogni mese. ho tre prestiti con scadenze diverse e mi perdo. "
                               "esiste un calendario semplice senza dover usare un'app", encoding="utf-8")
            r = VC.verificar(d["voz_cliente.json"], "it-IT", base, PARAMS)
        self.assertEqual(r["fabricadas"], 1)
        self.assertTrue(r["falla"])

    def test_S12_S15_siempre_se_prueban_y_estan_marcados_bloqueantes(self):
        for pre in ("s12", "s15"):
            self.assertEqual(_sembrado(pre)["severidad"], "BLOQUEANTE")

    def test_S13_los_competidores_siguen_pasando_el_script_pero_el_QA_debe_detectarlo(self):
        d = _aplicar(_sembrado("s13"))
        doms = [c["dominio"] for c in d["anuncios_competencia.json"]["competidores"]]
        self.assertEqual(doms.count("uno.ejemplo.invalid"), 3)  # lo detecta el QA (clustering), no un script


if __name__ == "__main__":
    unittest.main()
