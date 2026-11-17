"""Pedidos de P4 (landing en /sitio, desglose de consultas, tracción) y de P5 (propuestas, cumplimiento, rondas de QA, ledger)."""
from __future__ import annotations

import json
import os
import re
import unittest

from dashboard.seguridad import CSP_SITIO
from dashboard.servidor import reescribir_rutas
from scripts.validar_esquemas import hash_archivo, hash_directorio
from tests.dashboard.test_servidor_apoyo import CORRIDA, OFERTA, PruebaBase

SITIO = f"ofertas/{OFERTA}/05-landing/sitio"
PREFIJO = f"/sitio/{OFERTA}"


class PruebaSitioReescribe(PruebaBase):
    def test_html_con_rutas_absolutas_se_reescribe_a_sitio_id(self) -> None:
        r = self.cliente().get(f"{PREFIJO}/index.html")
        t = r.cuerpo.decode("utf-8")
        for esperado in (f'href="{PREFIJO}/css/estilos.css"', f"url({PREFIJO}/imagenes/hero.png)", f'@import "{PREFIJO}/css/extra.css"',
                         f'src="{PREFIJO}/imagenes/hero.png"', f'srcset="{PREFIJO}/imagenes/hero.png 1x, //cdn.example.com/hero-2x.png 2x"',
                         f'href="{PREFIJO}/legal/"', f'href="{PREFIJO}/legal/aviso"', f'src="{PREFIJO}/js/app.js"'):
            self.assertIn(esperado, t)
        for intacto in ('href="//otro.example.com/x"', 'href="https://example.com/y"', 'href="#arriba"', 'href="relativa/x.html"'):
            self.assertIn(intacto, t)
        self.assertEqual(t.count(f'{PREFIJO}/ya.html'), 1, "lo que ya cuelga de /sitio/<id>/ no se vuelve a prefijar")
        self.assertNotRegex(t, r'(href|src)="/(?!sitio/|/)')
        self.assertNotIn(f"{PREFIJO}{PREFIJO}", t)

    def test_css_con_url_e_import_absolutos(self) -> None:
        t = self.cliente().get(f"{PREFIJO}/css/estilos.css").cuerpo.decode()
        self.assertIn(f"url({PREFIJO}/imagenes/fondo.png)", t)
        self.assertIn(f'url("{PREFIJO}/imagenes/b.png")', t)
        self.assertIn("url(otra.png)", t, "las relativas no se tocan")
        self.assertIn(f'@import "{PREFIJO}/css/base.css"', t)

    def test_js_e_imagenes_pasan_sin_tocar_y_el_disco_no_cambia(self) -> None:
        antes = self.hash_arbol(self.raiz)
        c = self.cliente()
        js = c.get(f"{PREFIJO}/js/app.js")
        self.assertEqual(js.cuerpo, (self.raiz / SITIO / "js" / "app.js").read_bytes())
        self.assertEqual(js.cabeceras["content-type"], "text/javascript; charset=utf-8")
        c.get(f"{PREFIJO}/index.html")
        c.get(f"{PREFIJO}/css/estilos.css")
        self.assertEqual(self.hash_arbol(self.raiz), antes, "se reescribe al servir, nunca en disco")
        self.assertIn(b'href="/css/estilos.css"', (self.raiz / SITIO / "index.html").read_bytes())

    def test_se_mantienen_csp_sandbox_y_longitud(self) -> None:
        c = self.cliente()
        for ruta in ("index.html", "css/estilos.css", "js/app.js"):
            r = c.get(f"{PREFIJO}/{ruta}")
            self.assertEqual(r.cabeceras["content-security-policy"], CSP_SITIO)
            self.assertEqual(r.cabeceras["x-content-type-options"], "nosniff")
            self.assertEqual(r.cabeceras["content-length"], str(len(r.cuerpo)))
            h = c.llamar("HEAD", f"{PREFIJO}/{ruta}")
            self.assertEqual((h.cuerpo, h.cabeceras["content-length"]), (b"", str(len(r.cuerpo))))

    def test_reescritura_unitaria_idempotente_y_conserva_bytes_no_utf8(self) -> None:
        entrada = b'\xff\xfe<a href="/x">x</a><a href=\'/y z\'>y</a>'
        una = reescribir_rutas(entrada, "/sitio/OF-1", "text/html; charset=utf-8")
        self.assertTrue(una.startswith(b"\xff\xfe"))
        self.assertEqual(reescribir_rutas(una, "/sitio/OF-1", "text/html"), una, "idempotente")
        self.assertIn(b'href="/sitio/OF-1/x"', una)
        self.assertEqual(reescribir_rutas(b'url(/a.png)', "/sitio/OF-1", "application/json"), b'url(/a.png)')
        self.assertEqual(reescribir_rutas(b'<a href="/x">', "/sitio/OF-1", "image/svg+xml"), b'<a href="/x">')

    def test_urls_limpias_e_imagenes_de_la_oferta(self) -> None:
        c = self.cliente()
        self.assertIn(b"Aviso", c.get(f"{PREFIJO}/legal/aviso").cuerpo)
        img = c.get(f"{PREFIJO}/imagenes/hero.png")
        self.assertEqual((img.estado, img.cabeceras["content-type"]), (200, "image/png"))
        self.assertEqual(img.cuerpo, (self.raiz / "ofertas" / OFERTA / "05-landing" / "imagenes" / "hero.png").read_bytes())
        self.assertEqual(img.cabeceras["content-security-policy"], CSP_SITIO)
        self.assertEqual(c.get(f"{PREFIJO}/imagenes/no-existe.png").estado, 404)
        self.escribir(f"ofertas/{OFERTA}/05-landing/imagenes/.env", "X=1")
        for ruta in ("imagenes/.env", "imagenes/../../../estado.json", "imagenes/../sitio/index.html"):
            self.assertEqual(c.get(f"{PREFIJO}/{ruta}").estado, 403, ruta)

    def test_imagenes_que_escapan_por_enlace_no_se_sirven(self) -> None:
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "x.png").write_bytes(b"\x89PNG robado")
        os.symlink(fuera / "x.png", self.raiz / "ofertas" / OFERTA / "05-landing" / "imagenes" / "robada.png")
        r = self.cliente().get(f"{PREFIJO}/imagenes/robada.png")
        self.assertEqual(r.estado, 403)
        self.assertNotIn(b"robado", r.cuerpo)


class PruebaDescubrimientoP4(PruebaBase):
    def plan_con(self, qids: list[str]) -> None:
        self.escribir(f"empresa/barrido/planes/{CORRIDA}.pasada-2.json", json.dumps(
            {"schema_version": "1.0.0", "corrida_id": CORRIDA, "creado_en": "2026-11-06T06:20:00Z", "tope_consultas": 120,
             "consultas": [{"qid": q} for q in qids]}))

    def test_estado_desglosa_las_consultas_por_qid(self) -> None:
        self.plan_con(["es-a", "es-b", "es-c", "es-d"])
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/es-a.json", json.dumps({"estimated_total_count": 2, "ads": [{}, {}]}))
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/es-b.json", json.dumps({"estimated_total_count": 100, "ads": [{}, {}]}))
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/x y.json", "{}")
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/<script>.json", "{}")
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/es-e.extra.json", "{}")
        d = self.cliente().get(f"/api/descubrimiento/{CORRIDA}/estado").datos
        self.assertEqual(d["consultas_ok"], ["es-a", "es-b"])
        self.assertEqual(d["con_error"], ["es-c"])
        self.assertEqual(d["sin_crudo"], ["es-d"])
        self.assertEqual(d["truncadas"], ["es-b"])
        self.assertEqual(d["crudo"]["error"], 1)
        for clave in ("corrida_id", "plan", "paginas", "etiquetas", "memoria", "candidatos", "fichas", "freno", "comando_estado"):
            self.assertIn(clave, d, "aditivo: nada de lo anterior desaparece")

    def test_estado_sin_crudo_ni_plan(self) -> None:
        import shutil
        shutil.rmtree(self.raiz / "empresa" / "barrido" / "crudo" / CORRIDA)
        d = self.cliente().get(f"/api/descubrimiento/{CORRIDA}/estado").datos
        self.assertEqual((d["consultas_ok"], d["con_error"], d["truncadas"]), ([], [], []))
        self.assertEqual(d["sin_crudo"], ["es-a", "es-b", "es-c"], "todo lo planeado sin crudo")

    def test_crudo_corrupto_no_marca_truncada_ni_rompe(self) -> None:
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/es-a.json", "{no json")
        d = self.cliente().get(f"/api/descubrimiento/{CORRIDA}/estado").datos
        self.assertIn("es-a", d["consultas_ok"])
        self.assertEqual(d["truncadas"], [])

    def test_pasan_traccion_suma_temas_y_paginas_sin_tema(self) -> None:
        def fila() -> dict:
            return next(f for f in self.cliente().get("/api/descubrimiento/corridas").datos if f["corrida_id"] == CORRIDA)

        f = fila()
        self.assertEqual((f["pasan_traccion"], f["pasan_traccion_temas"], f["pasan_traccion_sin_tema"]), (2, 2, None), "sin sin_tema: solo temas")
        ruta = self.raiz / "empresa" / "barrido" / "candidatos" / f"{CORRIDA}.json"
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        doc["resumen"]["sin_tema_pasan_traccion"] = 3
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        f = fila()
        self.assertEqual((f["pasan_traccion"], f["pasan_traccion_temas"], f["pasan_traccion_sin_tema"]), (5, 2, 3))
        del doc["resumen"]["temas_pasan_traccion"]
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(fila()["pasan_traccion"], 3)
        doc["resumen"].pop("sin_tema_pasan_traccion")
        ruta.write_text(json.dumps(doc), encoding="utf-8")
        self.assertIsNone(fila()["pasan_traccion"], "sin ningún dato: null, nunca 0")


class PruebaPropuestasP5(PruebaBase):
    def test_incluye_las_propuestas_de_scripts_modelado(self) -> None:
        self.escribir("scripts/modelado/parametros_modelado.propuesta.yaml", "grupos:\n  descubrimiento:\n    modelado_anuncios_objetivo: {valor: 15}\n    modelado_dias_objetivo: {valor: 10}\n")
        self.escribir("scripts/modelado/barrido/parametros_barrido.propuesta.yaml", "grupos:\n  descubrimiento:\n    barrido_limite_por_consulta: {valor: 50}\n")
        self.escribir("scripts/modelado/barrido/frases_forma.yaml", "x: 1\n")
        self.escribir("scripts/modelado/mala.propuesta.yaml", "a: [1, 2")
        fuera = self.tmp / "fuera.propuesta.yaml"
        fuera.write_text("grupos:\n  robado:\n    k: {valor: 1}\n")
        os.symlink(fuera, self.raiz / "scripts" / "modelado" / "enlace.propuesta.yaml")
        j = self.cliente().get("/api/parametros").json()
        p = {x["archivo"]: x for x in j["datos"]["propuestas"]}
        self.assertEqual(set(p), {"empresa/propuestas/parametros-b0.yaml", "scripts/modelado/parametros_modelado.propuesta.yaml",
                                  "scripts/modelado/barrido/parametros_barrido.propuesta.yaml", "scripts/modelado/mala.propuesta.yaml"})
        self.assertEqual(p["scripts/modelado/parametros_modelado.propuesta.yaml"]["claves"],
                         ["descubrimiento.modelado_anuncios_objetivo", "descubrimiento.modelado_dias_objetivo"])
        self.assertEqual(p["scripts/modelado/barrido/parametros_barrido.propuesta.yaml"]["origen"], "scripts/modelado")
        self.assertEqual(p["empresa/propuestas/parametros-b0.yaml"]["origen"], "empresa/propuestas")
        self.assertEqual(p["scripts/modelado/mala.propuesta.yaml"]["claves"], [], "una propuesta corrupta aparece vacía, con aviso")
        self.assertTrue(any("mala.propuesta.yaml" in a for a in j["avisos"]))
        self.assertNotIn("robado", json.dumps(j["datos"]))
        self.assertIn("scripts/modelado/*.propuesta.yaml", j["fuente"])

    def test_sin_scripts_modelado_solo_las_de_empresa(self) -> None:
        d = self.cliente().get("/api/parametros").datos
        self.assertEqual([x["archivo"] for x in d["propuestas"]], ["empresa/propuestas/parametros-b0.yaml"])


class PruebaCumplimientoP5(PruebaBase):
    FIRMA = "hmac-sha256:" + "1" * 64

    def sellar(self, carpeta: str = OFERTA, *, interno: str | None = None, artefacto_ref: str = "03-oferta/oferta.json", etapa: str = "D3",
               nombre: str = "sello.json", **sello) -> tuple[dict, str]:
        base = self.raiz / "ofertas" / carpeta
        artefacto = base / artefacto_ref
        h = hash_directorio(artefacto) if artefacto.is_dir() else hash_archivo(artefacto)
        dictamen = {"etapa": "X1", "etapa_objetivo": etapa, "version": "v1", "ronda": 2, "ambito": "oferta", "veredicto": "PASS",
                    "artefacto_ref": artefacto_ref, "artefacto_sha256": h, "hallazgos": []}
        (base / "qa").mkdir(exist_ok=True)
        ruta_dictamen = base / "qa" / f"x1-{etapa.lower()}-v1.json"
        ruta_dictamen.write_text(json.dumps(dictamen), encoding="utf-8")
        contenido = {"oferta_id": interno or carpeta, "etapa_objetivo": etapa, "artefacto_sha256": h, "reglas_version": "1.0.0",
                     "emitido_en": "2026-11-09T10:00:00Z", "vigencia_hasta": "2026-11-10T10:00:00Z", "object_ids": ["120000000000001"],
                     "dictamen_ref": f"qa/x1-{etapa.lower()}-v1.json", "dictamen_sha256": hash_archivo(ruta_dictamen), "firma": self.FIRMA}
        contenido.update(sello)
        self.escribir(f"empresa/compliance/sellos/{nombre}", json.dumps(contenido))
        return contenido, h

    def sello(self, nombre: str = "sello.json") -> dict:
        return next(s for s in self.cliente().get("/api/cumplimiento").datos["sellos"] if s["archivo"] == nombre)

    def test_sello_trae_firma_object_ids_dictamen_sha_y_hash_actual(self) -> None:
        c, h = self.sellar()
        s = self.sello()
        self.assertEqual((s["firma"], s["object_ids"], s["dictamen_sha256"]), (self.FIRMA, ["120000000000001"], c["dictamen_sha256"]))
        self.assertEqual((s["hash_actual"], s["hash_coincide"], s["dictamen_hash_actual"], s["dictamen_coincide"], s["alterado"]), (h, True, c["dictamen_sha256"], True, False))
        self.assertIsNone(s["firma_valida"], "el panel no tiene la clave del HMAC: nunca afirma que la firma es válida")
        self.assertIsNone(s["verificacion"])
        self.assertEqual(s["artefacto_sha256"], h)

    def test_artefacto_o_dictamen_alterados_se_detectan(self) -> None:
        self.sellar()
        ruta = self.raiz / "ofertas" / OFERTA / "03-oferta" / "oferta.json"
        ruta.write_text(json.dumps({"precio": {"monto": 99900, "moneda": "EUR"}}), encoding="utf-8")
        s = self.sello()
        self.assertEqual((s["hash_coincide"], s["alterado"]), (False, True))
        self.assertNotEqual(s["hash_actual"], s["artefacto_sha256"])
        self.sellar(nombre="s2.json")        # re-sella con el artefacto nuevo
        d = self.raiz / "ofertas" / OFERTA / "qa" / "x1-d3-v1.json"
        d.write_text(d.read_text().replace('"PASS"', '"PASS_FALSO"'), encoding="utf-8")
        s2 = self.sello("s2.json")
        self.assertEqual((s2["dictamen_coincide"], s2["alterado"]), (False, True))

    def test_carpeta_de_directorio_y_limites_de_costo_y_seguridad(self) -> None:
        c, h = self.sellar(artefacto_ref="05-landing/sitio", etapa="D5", nombre="d5.json")
        s = self.sello("d5.json")
        self.assertEqual((s["hash_actual"], s["alterado"]), (hash_directorio(self.raiz / SITIO), False))
        os.symlink(self.tmp, self.raiz / SITIO / "enlace")
        s = self.sello("d5.json")
        self.assertIsNone(s["hash_actual"])
        self.assertIn("enlaces simbólicos", s["verificacion"])
        self.assertIsNone(s["alterado"], "sin hash recalculado no se afirma nada")
        os.unlink(self.raiz / SITIO / "enlace")
        grande = self.raiz / "ofertas" / OFERTA / "04-producto" / "muchos"
        grande.mkdir(parents=True)
        for k in range(401):
            (grande / f"a{k}.md").write_text("x")
        self.sellar(artefacto_ref="04-producto/muchos", etapa="D4", nombre="d4.json")
        s = self.sello("d4.json")
        self.assertIsNone(s["hash_actual"])
        self.assertIn("demasiado grande", s["verificacion"])

    def test_dictamen_con_artefacto_fuera_de_la_oferta_no_se_lee(self) -> None:
        c, _ = self.sellar()
        d = self.raiz / "ofertas" / OFERTA / "qa" / "x1-d3-v1.json"
        doc = json.loads(d.read_text())
        doc["artefacto_ref"] = "../../empresa/limites.yaml"
        d.write_text(json.dumps(doc))
        s = self.sello()
        self.assertIsNone(s["hash_actual"])
        self.assertIn("fuera de la oferta", s["verificacion"])
        self.sellar(nombre="hostil.json", dictamen_ref="../../../empresa/limites.yaml")
        h = self.sello("hostil.json")
        self.assertIsNone(h["hash_actual"])
        self.assertIn("no existe o no se puede leer", h["verificacion"])
        sin = self.sellar(nombre="sin.json", dictamen_ref=None)[0]
        self.assertIn("no cita ningún informe de cumplimiento", self.sello("sin.json")["verificacion"])

    def test_un_solo_identificador_la_carpeta_y_el_interno_aparte(self) -> None:
        # el demo (carpeta _ejemplo, estado.oferta_id OF-202611-01) y un sello/dictamen escritos con el id interno
        self.escribir("ofertas/_ejemplo/03-oferta/oferta.json", '{"precio": 1}')
        self.sellar("_ejemplo", interno="OF-202611-01", nombre="demo.json")
        s = self.sello("demo.json")
        self.assertEqual((s["oferta_id"], s["oferta_id_interno"], s["oferta_resuelta"]), ("_ejemplo", "OF-202611-01", True))
        d = self.cliente().get("/api/cumplimiento").datos["dictamenes"]
        demo = next(x for x in d if x["oferta_id"] == "_ejemplo")
        self.assertEqual(demo["oferta_id_interno"], "OF-202611-01")
        self.assertEqual((demo["ronda"], demo["ambito"], demo["artefacto_ref"]), (2, "oferta", "03-oferta/oferta.json"))
        self.assertEqual(demo["ruta"], "ofertas/_ejemplo/qa/x1-d3-v1.json")
        real = next(x for x in d if x["oferta_id"] == OFERTA)
        self.assertEqual(real["oferta_id"], OFERTA)
        # el mismo id interno en una carpeta real: gana la real
        (self.raiz / "ofertas" / "OF-202611-01").mkdir()
        self.assertEqual(self.sello("demo.json")["oferta_id"], "OF-202611-01")
        # un sello de una oferta que no existe conserva su id y no inventa
        self.escribir("empresa/compliance/sellos/fantasma.json", json.dumps({"oferta_id": "OF-999999-99", "etapa_objetivo": "D3",
                                                                              "artefacto_sha256": "sha256:" + "a" * 64, "dictamen_ref": "qa/x.json"}))
        f = self.sello("fantasma.json")
        self.assertEqual((f["oferta_id"], f["oferta_id_interno"], f["oferta_resuelta"], f["hash_actual"]), ("OF-999999-99", "OF-999999-99", False, None))
        self.assertIn("no existe", f["verificacion"])

    def test_los_campos_de_antes_siguen_y_el_sello_ilegible_no_cambia(self) -> None:
        d = self.cliente().get("/api/cumplimiento").datos
        s = next(x for x in d["sellos"] if x["archivo"] == "sello-d5.json")
        for k in ("archivo", "legible", "oferta_id", "etapa_objetivo", "emitido_en", "vigencia_hasta", "vigente", "dictamen_ref", "artefacto_sha256", "reglas_version"):
            self.assertIn(k, s)
        self.assertEqual(next(x for x in d["sellos"] if x["archivo"] == "roto.json"), {"archivo": "roto.json", "legible": False})


class PruebaAgentesRondasP5(PruebaBase):
    def linea(self, n: int, ejecucion: str, agente: str, etapa: str, oferta: str, hora: int) -> str:
        return json.dumps({"schema_version": "1.0.0", "ts": f"2026-11-07T{hora:02d}:00:00Z", "ejecucion_id": ejecucion, "oferta_id": oferta,
                           "etapa": etapa, "agente": agente, "evento": "accion", "herramienta": "x", "entrada_resumen": "x",
                           "resultado": {"estado": "ok", "codigo": 0}, "costo_estimado": {"monto": 1, "moneda": "EUR"}, "tokens": None,
                           "modo": "dry_run", "hash_previo": None, "hash": "sha256:" + "0" * 64}) + "\n"

    def preparar(self) -> None:
        lineas = [
            ("RUN-20261107-01", "d3-maker", "D3", OFERTA, 10), ("RUN-20261107-02", "d3-qa", "D3", OFERTA, 11),
            ("RUN-20261107-03", "d3-qa", "D3", OFERTA, 12), ("RUN-20261107-04", "d4-qa", "D4", OFERTA, 13),
            ("RUN-20261107-05", "d4-maker", "D4", OFERTA, 9), ("RUN-20261107-06", "d2-qa", "D2", "OF-202611-79", 14),
            ("RUN-20261107-07", "d2-qa", "D2", "OF-202611-79", 15), ("RUN-20261107-08", "x1", "D5", "OF-202611-79", 16),
            ("RUN-20261107-09", "qa-global", "D6", "OF-202611-79", 17),
        ]
        self.escribir("empresa/registro.jsonl", "".join(self.linea(k, *l) for k, l in enumerate(lineas)))
        estado = json.loads((self.raiz / "ofertas" / OFERTA / "estado.json").read_text())
        estado["etapas"]["D4"]["ronda_qa"] = 2
        (self.raiz / "ofertas" / OFERTA / "estado.json").write_text(json.dumps(estado))

    def filas(self) -> dict:
        return {f["ejecucion_id"]: f for f in self.cliente().get("/api/agentes").datos}

    def test_ronda_ordinal_en_las_ejecuciones_qa_y_rondas_de_la_etapa(self) -> None:
        self.preparar()
        f = self.filas()
        # D3 de OF-202611-77: el motor dice ronda_qa=1 (estado.json) aunque el registro muestre 2 ejecuciones QA
        self.assertEqual((f["RUN-20261107-02"]["ronda_qa"], f["RUN-20261107-03"]["ronda_qa"]), (1, 2), "ordinal por inicio entre las QA")
        self.assertIsNone(f["RUN-20261107-01"]["ronda_qa"], "una ejecución Maker no es una ronda de QA")
        for eid in ("RUN-20261107-01", "RUN-20261107-02", "RUN-20261107-03"):
            self.assertEqual((f[eid]["rondas_qa"], f[eid]["rondas_qa_fuente"]), (1, "estado"), eid)
        # D4: estado.json dice 2
        self.assertEqual((f["RUN-20261107-04"]["rondas_qa"], f["RUN-20261107-04"]["rondas_qa_fuente"], f["RUN-20261107-04"]["ronda_qa"]), (2, "estado", 1))
        self.assertEqual(f["RUN-20261107-05"]["rondas_qa"], 2)

    def test_sin_estado_se_derivan_del_registro_y_sin_qa_es_null(self) -> None:
        self.preparar()
        f = self.filas()
        for eid, ordinal in (("RUN-20261107-06", 1), ("RUN-20261107-07", 2)):
            self.assertEqual((f[eid]["ronda_qa"], f[eid]["rondas_qa"], f[eid]["rondas_qa_fuente"]), (ordinal, 2, "registro"), eid)
        self.assertEqual((f["RUN-20261107-08"]["ronda_qa"], f["RUN-20261107-08"]["rondas_qa"], f["RUN-20261107-08"]["rondas_qa_fuente"]), (None, None, None))
        self.assertEqual((f["RUN-20261107-09"]["ronda_qa"], f["RUN-20261107-09"]["rondas_qa"]), (1, 1), "qa-global es un agente QA")

    def test_el_detalle_tambien_las_trae_y_lo_de_antes_sigue(self) -> None:
        self.preparar()
        d = self.cliente().get("/api/agentes/RUN-20261107-03").datos
        self.assertEqual((d["ronda_qa"], d["rondas_qa"], d["rondas_qa_fuente"]), (2, 1, "estado"))
        self.assertEqual(len(d["eventos"]), 1)
        fila = self.filas()["RUN-20261107-03"]
        for k in ("ejecucion_id", "oferta_id", "etapa", "agente", "inicio", "fin", "estado", "costo", "costo_por_moneda", "modo", "eventos", "agentes"):
            self.assertIn(k, fila)
        self.assertEqual(fila["eventos"], 1)

    def test_la_demo_usa_el_estado_de_su_carpeta(self) -> None:
        self.escribir("ofertas/_ejemplo/_empresa/registro.jsonl", self.linea(0, "RUN-20261107-70", "d3-qa", "D3", "OF-202611-01", 10))
        f = self.cliente().get("/api/agentes", consulta="oferta=_ejemplo").datos[0]
        self.assertEqual((f["rondas_qa"], f["rondas_qa_fuente"], f["ronda_qa"]), (1, "estado", 1))


class PruebaFinanzasTruncadoP5(PruebaBase):
    def ledger(self, n: int, ruta: str = "empresa/finanzas/ledger.jsonl") -> None:
        self.escribir(ruta, "".join(json.dumps({"clave_natural": f"k{k}"}) + "\n" for k in range(n)))

    def test_ledger_largo_indica_truncado_y_total(self) -> None:
        self.ledger(600)
        j = self.cliente().get("/api/finanzas").json()
        self.assertEqual(len(j["datos"]["ledger"]), 500)
        self.assertEqual(j["datos"]["ledger"][-1]["clave_natural"], "k599", "se conserva la cola")
        self.assertTrue(j["truncado"])
        self.assertTrue(j["truncado_ledger"])
        self.assertFalse(j["truncado_alertas"])
        self.assertEqual(j["total"], 600)
        self.assertTrue(any("600" in a and "500" in a for a in j["avisos"]))
        self.assertEqual(set(j["datos"]), {"ledger", "pnl", "conciliacion", "alertas"}, "la forma de datos no cambia")

    def test_ledger_corto_no_es_truncado_y_exacto_en_el_tope_tampoco(self) -> None:
        self.ledger(10)
        j = self.cliente().get("/api/finanzas").json()
        self.assertEqual((j["truncado"], j["total"], len(j["datos"]["ledger"])), (False, 10, 10))
        self.ledger(500)
        j = self.cliente().get("/api/finanzas").json()
        self.assertEqual((j["truncado"], j["total"]), (False, 500))
        self.ledger(501)
        self.assertTrue(self.cliente().get("/api/finanzas").json()["truncado"])

    def test_alertas_truncadas_y_sin_archivos(self) -> None:
        self.ledger(250, "empresa/datos/alertas.jsonl")
        j = self.cliente().get("/api/finanzas").json()
        self.assertEqual((j["truncado"], j["truncado_ledger"], j["truncado_alertas"], j["total_alertas"], len(j["datos"]["alertas"])), (True, False, True, 250, 200))
        import shutil
        shutil.rmtree(self.raiz / "empresa" / "datos", ignore_errors=True)
        vacio = self.cliente().get("/api/finanzas").json()
        self.assertEqual((vacio["vacio"], vacio["truncado"], vacio["total"], vacio["total_alertas"]), (True, False, None, None))


if __name__ == "__main__":
    unittest.main()
