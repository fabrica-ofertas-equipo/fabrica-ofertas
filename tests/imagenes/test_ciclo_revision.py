"""Pruebas del ciclo de revisión (scripts/imagenes/ciclo_revision.py y sus comandos en ranuras_kie.py). Sin red ni créditos: Kie nunca se llama."""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts.imagenes import ciclo_revision as cr
from scripts.imagenes import ranuras_kie as rk
from tests.imagenes.test_ranuras_kie import png_falso


def estimar_falso(modelo, entrada):
    return {"nano-banana-pro": 18, "nano-banana-2": 12, "gpt-image-2-image-to-image": 10}[modelo]


def sidecar(assets: Path, slot: str, cand: str, ronda: int = 1, tipo: str = "directo", modelo: str = "nano-banana-pro", derivada_de: str | None = None) -> None:
    d = assets / "candidatos" / slot
    png_falso(d / f"{cand}.png", 40, 60)
    reg = {"slot_id": slot, "candidato": cand, "estado": "ok", "modelo": modelo, "ronda": ronda, "tipo": tipo, "creditos_reales": 18.0, "creditos_cotizados": 18,
           "task_id": "t-secreto", "prompt": "prompt secreto con nano-banana-pro", "correccion": "corrección secreta",
           "comprobaciones": {"ocr": {"tasa_exacta": 1.0}}}
    if derivada_de:
        reg["derivada_de"] = derivada_de
    (d / f"{cand}.json").write_text(json.dumps(reg), encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.raiz = Path(self._td.name) / "OF-TEST"
        self.assets = self.raiz / "05-landing" / "assets"
        (self.raiz / "03-oferta").mkdir(parents=True)
        (self.raiz / "03-oferta" / "oferta.json").write_text(json.dumps({
            "marca": {"nombre": "Marca"}, "entregables": [{"id": "mapas", "tipo": "biblioteca", "cantidad": 520, "formato": "pdf_a4"}],
            "bonus": [{"id": "b1", "descripcion": "Guía de sonidos, bez nagrań."}], "bump": {"id": "fiszki", "nombre": "Zestaw", "descripcion": "PDF y plik CSV"},
            "mecanismo": {"nombre": "Ścieżka"}, "promesa": {"claims_prohibidos": [{"texto": "w 30 dni"}]}}), encoding="utf-8")
        png_falso(self.assets / "referencias" / "plana.png", 30, 40)
        sidecar(self.assets, "hero", "nbp-01")
        sidecar(self.assets, "hero", "gpt2-01", modelo="gpt-image-2-image-to-image")
        sidecar(self.assets, "muestra-1", "gpt2-01", modelo="gpt-image-2-image-to-image")
        sidecar(self.assets, "compra", "r2-nbp-01", ronda=2, tipo="escena_con_marcadores")
        sidecar(self.assets, "compra", "r2-comp-01", ronda=2, tipo="compuesta", derivada_de="r2-nbp-01")
        base = {"ratio": "1:1", "prompt": "p", "intentos": [], "referencias": ["referencias/plana.png", "referencias/comp/guia.png"], "resolution": "2K"}
        self.plan = {"oferta_id": "OF-TEST", "resolution": "2K", "tope_creditos": 100, "rubrica_general": {"estricto_true": "Títulos y cifras exactos."},
                     "no_debe_aparecer_global": ["rostros"], "slots": [
            {**base, "slot_id": "hero", "seccion": "hero", "funcion": "Imagen principal", "estricto": True, "textos_esperados": ["SŁOWOMAPA", "520"], "textos_estrictos": ["520"],
             "objetos_esperados": ["monitor"], "no_debe_aparecer": ["audio"], "criterios": ["texto exacto"], "dimensiones_requeridas": {"ancho": 100, "alto": 100},
             "seleccion_maker": {"candidato": "gpt2-01"}, "alt_propuesto": "alt"},
            {**base, "slot_id": "muestra-1", "asset_slot": "muestra-1", "seccion": "galeria", "funcion": "Miniatura", "estricto": False, "textos_esperados": ["Jedzenie"],
             "seleccion_maker": {"candidato": "gpt2-01"}},
            {**base, "slot_id": "compra", "seccion": "compra", "funcion": "Tarjeta", "estricto": True, "textos_esperados": ["520"], "seleccion_maker": {"candidato": "r2-comp-01"}}]}
        self.plan_ruta = self.assets / "plan.json"
        self.plan_ruta.write_text(json.dumps(self.plan), encoding="utf-8")

    def tearDown(self):
        self._td.cleanup()

    def revision(self, **kw):
        """JSON de ejemplo de un revisor: hero aprobado (alias del paquete), muestra-1 rehacer."""
        return kw

    def paquete(self, **kw):
        return cr.paquete_ciego(self.plan, self.assets, **kw)


class TestPaqueteCiego(Base):
    def test_sin_fugas_con_rubrica_hechos_y_rutas(self):
        paquete, mapa = self.paquete()
        self.assertEqual(cr.buscar_fugas(paquete), [])
        texto = json.dumps(paquete, ensure_ascii=False)
        for secreto in ("prompt secreto", "nano-banana", "gpt-image", "t-secreto", "seleccion_maker", "corrección secreta", "creditos", "ocr", "tasa_exacta"):
            self.assertNotIn(secreto, texto)
        self.assertIn("rubrica_general", paquete)
        self.assertEqual(paquete["rubrica_general"]["estricto_true"], "Títulos y cifras exactos.")
        self.assertTrue(any("audio" in x for x in paquete["hechos_del_producto"]["NO_incluye"]))
        self.assertTrue(any("grabaciones" in x for x in paquete["hechos_del_producto"]["NO_incluye"]))
        s = {x["slot_id"]: x for x in paquete["slots"]}
        self.assertEqual(s["hero"]["textos_esperados"], ["SŁOWOMAPA", "520"])
        self.assertEqual(s["hero"]["no_debe_aparecer"], ["rostros", "audio"])
        self.assertTrue(s["hero"]["rubrica"]["estricto"])
        self.assertEqual(s["hero"]["objetos_esperados"], ["monitor"])
        for sl in paquete["slots"]:
            for c in sl["candidatos"]:
                self.assertTrue(Path(c["ruta_absoluta"]).is_absolute() and Path(c["ruta_absoluta"]).is_file())
                self.assertRegex(c["alias"], r"^c\d+$")
                self.assertNotIn("nbp", c["ruta_absoluta"].split("revision-ciega")[1])        # el nombre del candidato no aparece en la ruta con alias
        self.assertEqual(sorted(mapa["hero"].values()), ["gpt2-01", "nbp-01"])                    # el mapa secreto sí lo guarda, aparte
        self.assertTrue((self.assets / "revision-ciega" / "mapa-secreto-ronda1.json").is_file())
        self.assertTrue(Path(s["hero"]["referencias_planas_absolutas"][0]).name == "plana.png")  # la plana sí; el boceto «comp/» no
        self.assertEqual(len(s["hero"]["referencias_planas_absolutas"]), 1)

    def test_excluye_escenas_y_muestra_compuestas(self):
        paquete, mapa = self.paquete()
        self.assertEqual(list(mapa["compra"].values()), ["r2-comp-01"])                       # la escena con marcadores no es un candidato
        self.assertNotIn("derivada", json.dumps(paquete))

    def test_solo_slots_y_solo_re_revisar(self):
        paquete, _ = self.paquete(solo_slots={"hero"})
        self.assertEqual([s["slot_id"] for s in paquete["slots"]], ["hero"])
        # tras aprobar hero y muestra-1, solo compra sigue pendiente
        (self.assets / "revision-ronda1.json").write_text(json.dumps({"ronda": 1, "estrictas": {"PASA": {"hero": "gpt2-01"}}, "ilustrativas": {"PASA": {"muestra-1": "gpt2-01"}}}), encoding="utf-8")
        paquete, _ = self.paquete(solo_re_revisar=True)
        self.assertEqual([s["slot_id"] for s in paquete["slots"]], ["compra"])
        self.assertEqual(paquete["ronda"], 2)                                                  # la ronda siguiente a la última revisión
        paquete, _ = self.paquete()                                                            # sin filtro: solo lo no revisado
        self.assertEqual([s["slot_id"] for s in paquete["slots"]], ["compra"])

    def test_revision_explicita_de_un_slot_ya_revisado_muestra_todo(self):
        (self.assets / "revision-ronda1.json").write_text(json.dumps({"ronda": 1, "estrictas": {"PASA": {"hero": "gpt2-01"}}}), encoding="utf-8")
        paquete, mapa = self.paquete(solo_slots={"hero"})
        self.assertEqual(sorted(mapa["hero"].values()), ["gpt2-01", "nbp-01"])

    def test_flags_de_ilustrativa_y_reemplazo(self):
        paquete, _ = self.paquete()
        s = {x["slot_id"]: x for x in paquete["slots"]}
        self.assertTrue(s["muestra-1"]["ilustrativa"] and s["muestra-1"]["reemplazar_con_real_cuando_exista_producto"])
        self.assertFalse(s["hero"]["ilustrativa"] or s["hero"]["reemplazar_con_real_cuando_exista_producto"])
        self.assertFalse(s["muestra-1"]["producto_real_disponible"])

    def test_fuga_en_un_texto_libre_se_sanea(self):
        self.plan["slots"][0]["funcion"] = "Escena de Kie con prompt y créditos"
        paquete, _ = self.paquete()
        self.assertEqual(cr.buscar_fugas(paquete), [])
        self.assertIn("[omitido]", paquete["slots"][0]["funcion_en_pagina"])


class TestHechosYFlags(Base):
    def test_resolver_ilustrativa(self):
        self.assertEqual(cr.resolver_ilustrativa({"slot_id": "muestra-3"}, self.raiz)["ilustrativa"], True)
        self.assertEqual(cr.resolver_ilustrativa({"slot_id": "hero"}, self.raiz)["reemplazar_con_real_cuando_exista_producto"], False)
        f = cr.resolver_ilustrativa({"slot_id": "x", "ilustrativa": True, "reemplazar_con_real_cuando_exista_producto": False}, self.raiz)
        self.assertEqual((f["ilustrativa"], f["reemplazar_con_real_cuando_exista_producto"]), (True, False))      # lo explícito manda
        aj = {"slots": [{"slot_id": "zz", "tipo": "captura_producto"}]}
        self.assertTrue(cr.resolver_ilustrativa({"slot_id": "zz"}, self.raiz, aj)["ilustrativa"])                  # por el tipo en assets.json
        (self.raiz / "04-producto").mkdir()
        (self.raiz / "04-producto" / "producto.json").write_text("{}", encoding="utf-8")
        f = cr.resolver_ilustrativa({"slot_id": "muestra-1"}, self.raiz)
        self.assertTrue(f["producto_real_disponible"] and f["reemplazar_ahora"])                                  # ya hay producto real: reemplazar ahora

    def test_no_incluye_sin_oferta(self):
        h = cr.hechos_del_producto(None, {"hechos_producto_extra": {"NO_incluye": ["x"]}})
        self.assertEqual(h["NO_incluye"], ["x"])


class TestPrompt(Base):
    def test_prompt_junto_al_paquete(self):
        self.paquete()
        ruta = cr.escribir_prompt_revisor(self.assets / "revision-ciega" / "ronda1" / "paquete-ciego.json")
        t = ruta.read_text(encoding="utf-8")
        self.assertEqual(ruta.parent.name, "ronda1")
        for esperado in ("Solo lectura", "paquete-ciego.json", "veredicto_slot", "correccion_para_regenerar", "diferencias_texto", "candidatos", "alias", "\"ronda\": 1"):
            self.assertIn(esperado, t)
        for modelo in ("nano-banana", "gpt-image", "nbp", "gpt2", "créditos", "task_id", "seleccion_maker"):
            self.assertNotIn(modelo, t)                                                              # el texto del revisor no nombra modelos, créditos ni elecciones


class TestAplicar(Base):
    def alias(self, slot, real):
        return next(a for a, n in json.loads((self.assets / "revision-ciega" / "mapa-secreto-ronda1.json").read_text())["alias_a_candidato"][slot].items() if n == real)

    def json_revisor(self):
        self.paquete()
        return {"ronda": 1, "revisor": "doble", "slots": [
            {"slot_id": "hero", "candidatos": [{"nombre": self.alias("hero", "gpt2-01"), "veredicto": "PASA", "diferencias_texto": []},
                                               {"nombre": self.alias("hero", "nbp-01"), "veredicto": "RECHAZADO", "diferencias_texto": ["«520» sale «502»"]}],
             "mejor": self.alias("hero", "gpt2-01"), "veredicto_slot": "PASA", "condiciones": [], "correccion_para_regenerar": ""},
            {"slot_id": "muestra-1", "candidatos": [{"nombre": self.alias("muestra-1", "gpt2-01"), "veredicto": "REHACER", "hallazgos": ["hoja estirada"]}],
             "mejor": None, "veredicto_slot": "REHACER", "condiciones": [], "correccion_para_regenerar": "Conservar las proporciones A4 vertical."},
            {"slot_id": "compra", "candidatos": [{"nombre": self.alias("compra", "r2-comp-01"), "veredicto": "REHACER"}], "mejor": None,
             "veredicto_slot": "REHACER", "correccion_para_regenerar": "Tableta de la familia del héroe."}]}

    def aplicar(self, raw, **kw):
        return cr.aplicar_revision(self.plan, self.assets, raw, plan_ruta=self.plan_ruta, estimar=estimar_falso, **kw)

    def test_aplica_guarda_y_calcula_estados_y_reintentos(self):
        res = self.aplicar(self.json_revisor(), tope=40)
        self.assertEqual(res["aprobados"], ["hero"])
        self.assertEqual(sorted(res["rehacer"]), ["compra", "muestra-1"])
        guardado = json.loads((self.assets / "revision-ronda1.json").read_text(encoding="utf-8"))
        self.assertEqual(guardado["slots"][0]["mejor_real"], "gpt2-01")                         # los alias se traducen a los candidatos reales
        self.assertIn("bruto", guardado)
        self.assertEqual(res["estados"]["hero"], "PASA_ronda1")
        self.assertEqual(res["estados"]["muestra-1"], "REHACER_ronda1")
        self.assertEqual(json.loads(self.plan_ruta.read_text())["slots"][0]["seleccion_maker"]["candidato"], "gpt2-01")
        # plan de reintentos
        pr = res["plan_de_reintentos"]
        por = {i["slot_id"]: i for i in pr["reintentos"]}
        self.assertEqual(por["muestra-1"]["modelo_propuesto"], "gpt-image-2-image-to-image")      # el modelo del candidato elegido
        self.assertEqual(por["muestra-1"]["creditos_estimados"], 10)
        self.assertEqual(por["muestra-1"]["intentos_usados_en_su_ronda"], 1)
        self.assertEqual(por["muestra-1"]["intentos_restantes_misma_ronda"], 2)
        self.assertEqual(por["compra"]["modelo_propuesto"], "nano-banana-pro")                     # el modelo de la escena base del compuesto
        self.assertIn("escena", por["compra"]["tipo_regeneracion"])
        self.assertEqual(por["compra"]["creditos_estimados"], 18)
        self.assertIn("ranuras_kie.py reintentar", por["compra"]["comando_sugerido"])
        self.assertIn("Tableta de la familia del héroe.", por["compra"]["comando_sugerido"])
        self.assertTrue((self.assets / "plan-reintentos-ronda1.json").is_file())
        # tope 40: muestra-1 (10) cabe; compra (18) cabe en 28; no hay pendientes que superen el tope
        self.assertEqual(pr["pendientes_que_superan_el_tope"], [])
        self.assertEqual(pr["creditos_estimados_total"], 28)

    def test_lo_que_supera_el_tope_se_lista(self):
        res = self.aplicar(self.json_revisor(), tope=20)
        pr = res["plan_de_reintentos"]
        self.assertEqual(pr["pendientes_que_superan_el_tope"], ["compra"])                         # 10 + 18 > 20
        self.assertEqual(pr["creditos_estimados_total"], 10)

    def test_rechaza_malformados_sin_escribir_nada(self):
        malos = [None, [], {"slots": []}, {"slots": "x"}, {"slots": [{"candidatos": []}]}, {"slots": [{"slot_id": "hero"}]},
                 {"slots": [{"slot_id": "hero", "veredicto_slot": "TAL", "candidatos": [{"nombre": "c1", "veredicto": "PASA"}]}]},
                 {"slots": [{"slot_id": "hero", "veredicto_slot": "PASA", "candidatos": [{"nombre": "c1"}], "mejor": "c1"}]}]
        for raw in malos:
            with self.assertRaises(cr.RevisionRechazada, msg=str(raw)):
                self.aplicar(raw)
        self.assertEqual(list(self.assets.glob("revision-ronda*.json")), [])
        self.assertEqual(list(self.assets.glob("plan-reintentos*.json")), [])

    def test_rechaza_slot_y_candidato_desconocidos(self):
        raw = self.json_revisor()
        raw["slots"].append({"slot_id": "no-existe", "candidatos": [{"nombre": "c1", "veredicto": "PASA"}], "mejor": "c1", "veredicto_slot": "PASA"})
        with self.assertRaises(cr.RevisionRechazada) as cm:
            self.aplicar(raw)
        self.assertTrue(any("slot desconocido" in e for e in cm.exception.errores))
        self.assertEqual(list(self.assets.glob("revision-ronda*.json")), [])
        raw = self.json_revisor()
        raw["slots"][0]["candidatos"][0]["nombre"] = "c99"
        with self.assertRaises(cr.RevisionRechazada) as cm:
            self.aplicar(raw)
        self.assertTrue(any("candidato desconocido" in e for e in cm.exception.errores))

    def test_pasa_con_diferencias_de_texto_en_slot_estricto_se_rechaza(self):
        raw = self.json_revisor()
        raw["slots"][0]["candidatos"][0]["diferencias_texto"] = ["«Około» sale «Okolo»"]        # el candidato elegido altera un texto de un slot estricto
        with self.assertRaises(cr.RevisionRechazada) as cm:
            self.aplicar(raw)
        self.assertTrue(any("ESTRICTO" in e and "diferencias_texto" in e for e in cm.exception.errores))
        self.assertEqual(list(self.assets.glob("revision-ronda*.json")), [])                      # nada aplicado
        self.assertEqual(json.loads(self.plan_ruta.read_text())["slots"][0]["seleccion_maker"]["candidato"], "gpt2-01")
        # también si las diferencias vienen a nivel de slot
        raw = self.json_revisor()
        raw["slots"][0]["diferencias_texto"] = ["x"]
        with self.assertRaises(cr.RevisionRechazada):
            self.aplicar(raw)

    def test_diferencias_en_slot_no_estricto_no_impiden_pasar(self):
        raw = self.json_revisor()
        raw["slots"][1] = {"slot_id": "muestra-1", "candidatos": [{"nombre": self.alias("muestra-1", "gpt2-01"), "veredicto": "PASA", "diferencias_texto": ["texto interior aproximado"]}],
                           "mejor": self.alias("muestra-1", "gpt2-01"), "veredicto_slot": "PASA"}
        res = self.aplicar(raw)
        self.assertIn("muestra-1", res["aprobados"])

    def test_rehacer_sin_correccion_y_pasa_apuntando_a_un_candidato_que_no_pasa(self):
        raw = self.json_revisor()
        raw["slots"][1]["correccion_para_regenerar"] = "  "
        with self.assertRaises(cr.RevisionRechazada) as cm:
            self.aplicar(raw)
        self.assertTrue(any("correccion_para_regenerar" in e for e in cm.exception.errores))
        raw = self.json_revisor()
        raw["slots"][0]["mejor"] = self.alias("hero", "nbp-01")                                     # ese candidato está RECHAZADO
        with self.assertRaises(cr.RevisionRechazada) as cm:
            self.aplicar(raw)
        self.assertTrue(any("cuyo veredicto es" in e for e in cm.exception.errores))

    def test_pasa_condicional_exige_condiciones_y_se_anota(self):
        raw = self.json_revisor()
        raw["slots"][0]["veredicto_slot"] = "PASA_CONDICIONAL"
        with self.assertRaises(cr.RevisionRechazada):
            self.aplicar(raw)
        raw["slots"][0]["condiciones"] = ["confirmar «Około» en la portada plana"]
        res = self.aplicar(raw)
        self.assertEqual(res["condicionales"], ["hero"])
        self.assertEqual(res["estados"]["hero"], "PASA_ronda1")
        self.assertEqual(cr.estado_slots(self.plan, self.assets)["hero"]["condiciones"], ["confirmar «Około» en la portada plana"])

    def test_no_pisa_una_ronda_existente(self):
        self.aplicar(self.json_revisor())
        with self.assertRaises(cr.RevisionRechazada):
            self.aplicar(self.json_revisor(), ronda=1)

    def test_candidato_nuevo_tras_rehacer_queda_pendiente(self):
        self.aplicar(self.json_revisor())
        sidecar(self.assets, "muestra-1", "r2-gpt2-01", ronda=2, modelo="gpt-image-2-image-to-image")
        self.plan["slots"][1]["seleccion_maker"] = {"candidato": "r2-gpt2-01"}
        est = cr.estado_slots(self.plan, self.assets)
        self.assertEqual(est["muestra-1"]["estado"], "rehecho_ronda2_pendiente_de_revision")
        self.assertFalse(est["muestra-1"]["aprobado"])
        paquete, mapa = cr.paquete_ciego(self.plan, self.assets, solo_re_revisar=True)
        self.assertEqual(list(mapa["muestra-1"].values()), ["r2-gpt2-01"])                         # solo el candidato nuevo: el anterior ya se revisó
        self.assertEqual(paquete["ronda"], 2)


class TestEstadosLegados(Base):
    def test_formato_manual_de_las_rondas_1_y_2(self):
        (self.assets / "revision-ronda1.json").write_text(json.dumps({"ronda": 1, "estrictas": {"PASA": {"hero": "gpt2-01"}, "REHACER": {"compra": "escena mala"}},
                                                                    "ilustrativas": {"PASA": {"muestra-1": "gpt2-01"}}}), encoding="utf-8")
        (self.assets / "revision-ronda2.json").write_text(json.dumps({"ronda": 2, "estrictas": {"PASA": {}}, "condiciones": {"hero": "confirmar el bump"}}), encoding="utf-8")
        est = cr.estado_slots(self.plan, self.assets)
        self.assertEqual(est["hero"]["estado"], "PASA_ronda1")
        self.assertEqual(est["muestra-1"]["estado"], "PASA_ronda1")
        self.assertEqual(est["compra"]["estado"], "rehecho_ronda2_pendiente_de_revision")           # el compuesto de la ronda 2 es posterior al REHACER de la ronda 1
        self.assertTrue(est["hero"]["aprobado"] and not est["compra"]["aprobado"])

    def test_sin_revisiones_todo_pendiente(self):
        est = cr.estado_slots(self.plan, self.assets)
        self.assertTrue(all(e["estado"] == "pendiente_de_revision" for e in est.values()))


class TestFinalizar(Base):
    def falso(self, origen, destino, ancho, alto, formato, peso):
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_bytes(b"x" * 1024)
        return {"calidad": 80, "peso_kb": 1.0, "peso_ok": True}

    def finalizar(self, **kw):
        return cr.finalizar(self.plan, self.assets, None, convertir_fn=self.falso, medir_fn=lambda p: (100, 100), **kw)

    def test_solo_aprobados_y_aviso_de_los_demas(self):
        (self.assets / "revision-ronda1.json").write_text(json.dumps({"ronda": 1, "estrictas": {"PASA": {"hero": "gpt2-01"}}}), encoding="utf-8")
        for s in self.plan["slots"]:
            s["dimensiones_requeridas"] = {"ancho": 100, "alto": 100, "formato_final": "webp", "peso_max_kb": 100}
        res = self.finalizar()
        self.assertEqual(res["aprobados"], ["hero"])
        self.assertEqual(sorted(n["slot_id"] for n in res["no_aprobados"]), ["compra", "muestra-1"])
        self.assertTrue(any("compra" in a for a in res["avisos"]))
        man = json.loads(Path(res["manifiesto"]).read_text(encoding="utf-8"))
        self.assertEqual([e["slot"] for e in man["ranuras"]], ["hero"])
        self.assertEqual(sorted(x["slot_id"] for x in man["no_aprobados"]), ["compra", "muestra-1"])
        self.assertTrue((self.assets / "final" / "hero.webp").is_file())
        self.assertFalse((self.assets / "final" / "compra.webp").exists())
        self.assertTrue(man["ranuras"][0]["aprobado_por_revision"])
        self.assertEqual(man["propuesta_assets_json"][0]["campos"]["estado"], "aprobado")

    def test_sin_aprobados_no_genera_nada(self):
        res = self.finalizar()
        self.assertEqual(res["aprobados"], [])
        self.assertIsNone(res["manifiesto"])
        self.assertFalse((self.assets / "final").exists())

    def test_incluir_pendientes_los_deja_asignados_y_calcula_reemplazo(self):
        (self.assets / "revision-ronda1.json").write_text(json.dumps({"ronda": 1, "estrictas": {"PASA": {"hero": "gpt2-01"}}}), encoding="utf-8")
        for s in self.plan["slots"]:
            s["dimensiones_requeridas"] = {"ancho": 100, "alto": 100, "formato_final": "webp", "peso_max_kb": 100}
        res = self.finalizar(incluir_pendientes=True)
        man = json.loads(Path(res["manifiesto"]).read_text(encoding="utf-8"))
        por = {e["slot"]: e for e in man["ranuras"]}
        self.assertEqual(len(por), 3)
        self.assertFalse(por["compra"]["aprobado_por_revision"])
        self.assertTrue(por["muestra-1"]["ilustrativa"] and por["muestra-1"]["reemplazar_con_real_cuando_exista_producto"])
        parches = {p["slot_id"]: p for p in man["propuesta_assets_json"]}
        self.assertEqual(parches["compra"]["campos"]["estado"], "asignado")
        self.assertTrue(parches["muestra-1"]["campos"]["ilustrativa"])


class TestComandos(Base):
    """El ciclo por la línea de comandos (sin Kie). El estimador sale de la tabla de créditos medidos si `requests` no está disponible."""

    def ejecutar(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            codigo = rk.main([str(x) for x in args])
        return codigo, out.getvalue(), err.getvalue()

    def test_ciclo_completo_por_comandos(self):
        c, o, e = self.ejecutar("manifiesto", self.plan_ruta, "--assets", self.assets, "--ciego", "--solo-slots", "hero,compra")
        self.assertEqual(c, 0, e)
        info = json.loads(o)
        self.assertEqual(info["slots"], ["hero", "compra"])
        c, o, e = self.ejecutar("revisar-prompt", self.plan_ruta, "--assets", self.assets)
        self.assertEqual(c, 0, e)
        self.assertTrue(Path(o.strip()).name == "instrucciones-revisor.md" and Path(o.strip()).is_file())
        mapa = json.loads((self.assets / "revision-ciega" / "mapa-secreto-ronda1.json").read_text())["alias_a_candidato"]
        a_hero = next(a for a, n in mapa["hero"].items() if n == "gpt2-01")
        a_hero_malo = next(a for a, n in mapa["hero"].items() if n == "nbp-01")
        a_compra = next(iter(mapa["compra"]))
        revision = {"ronda": 1, "slots": [
            {"slot_id": "hero", "candidatos": [{"nombre": a_hero, "veredicto": "PASA"}, {"nombre": a_hero_malo, "veredicto": "REHACER"}], "mejor": a_hero, "veredicto_slot": "PASA"},
            {"slot_id": "compra", "candidatos": [{"nombre": a_compra, "veredicto": "REHACER"}], "mejor": None, "veredicto_slot": "REHACER", "correccion_para_regenerar": "Más margen lateral."}]}
        malo = self.assets / "revision-mala.json"
        malo.write_text(json.dumps({**revision, "slots": revision["slots"][:1] + [{"slot_id": "inventado", "candidatos": [], "veredicto_slot": "PASA"}]}), encoding="utf-8")
        c, o, e = self.ejecutar("aplicar-revision", self.plan_ruta, malo, "--assets", self.assets)
        self.assertEqual(c, 3)                                                                       # rechazada
        self.assertIn("slot desconocido", e)
        self.assertFalse((self.assets / "revision-ronda1.json").exists())
        ilegible = self.assets / "revision-ilegible.json"
        ilegible.write_text("{no es json", encoding="utf-8")
        self.assertEqual(self.ejecutar("aplicar-revision", self.plan_ruta, ilegible, "--assets", self.assets)[0], 3)
        bueno = self.assets / "revision-buena.json"
        bueno.write_text(json.dumps(revision), encoding="utf-8")
        c, o, e = self.ejecutar("aplicar-revision", self.plan_ruta, bueno, "--assets", self.assets, "--tope", "300")
        self.assertEqual(c, 0, e)
        res = json.loads(o)
        self.assertEqual(res["aprobados"], ["hero"])
        self.assertEqual(res["rehacer"], ["compra"])
        self.assertEqual(res["plan_de_reintentos"]["reintentos"][0]["creditos_estimados"], 18)
        pr = json.loads((self.assets / "paquete-revision.json").read_text(encoding="utf-8"))          # el paquete de revisión se actualiza
        estados = {s["slot_id"]: (s["estado"], s["aprobado_por_revision"]) for s in pr["slots"]}
        self.assertEqual(estados["hero"], ("PASA_ronda1", True))
        self.assertEqual(estados["compra"], ("REHACER_ronda1", False))
        self.assertEqual(estados["muestra-1"], ("pendiente_de_revision", False))
        self.assertEqual({s["slot_id"]: s["ilustrativa"] for s in pr["slots"]}["muestra-1"], True)
        self.assertEqual([x["slot_id"] for x in pr["re_revisar"]], ["muestra-1"])
        # finalizar por la línea de comandos solo si hay herramientas reales; si no, comprueba al menos que avisa
        if shutil.which("ffmpeg") and shutil.which("cwebp") and shutil.which("sips"):
            for s in self.plan["slots"]:
                s["dimensiones_requeridas"] = {"ancho": 50, "alto": 50, "formato_final": "webp", "peso_max_kb": 150}
            self.plan_ruta.write_text(json.dumps(self.plan), encoding="utf-8")
            c, o, e = self.ejecutar("finalizar", self.plan_ruta, "--assets", self.assets)
            self.assertEqual(c, 0, e)
            self.assertIn("compra: REHACER_ronda1", e)
            self.assertTrue((self.assets / "final" / "hero.webp").is_file())
            self.assertFalse((self.assets / "final" / "compra.webp").exists())

    def test_prompt_sin_paquete_falla_con_mensaje(self):
        c, o, e = self.ejecutar("revisar-prompt", self.plan_ruta, "--assets", self.assets)
        self.assertEqual(c, 2)
        self.assertIn("manifiesto --ciego", e)

    def test_finalizar_sin_aprobados_sale_con_4(self):
        c, o, e = self.ejecutar("finalizar", self.plan_ruta, "--assets", self.assets)
        self.assertEqual(c, 4)
        self.assertIn("AVISO", e)


if __name__ == "__main__":
    unittest.main()
