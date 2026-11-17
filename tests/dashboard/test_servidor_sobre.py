"""Sobre de la API, errores y lectores tolerantes (``vacio`` vs dato) del panel, sobre la raíz de fixtures."""
from __future__ import annotations

import json
import os
import unittest

from tests.dashboard.test_servidor_apoyo import CORRIDA, HOSTIL, OFERTA, Cliente, PruebaBase


from dashboard.api_empresa import CLAVES_NULO_SOLO_VERDE


class PruebaSobre(PruebaBase):
    def test_sobre_de_exito_tiene_las_seis_claves(self) -> None:
        r = self.cliente().get("/api/sistema")
        self.assertEqual(r.estado, 200)
        j = r.json()
        self.assertEqual(set(j), {"ok", "datos", "fuente", "generado_en", "vacio", "avisos"})
        self.assertIs(j["ok"], True)
        self.assertEqual(j["generado_en"], "2026-11-09T12:00:00Z")
        self.assertIsInstance(j["fuente"], list)
        self.assertIsInstance(j["avisos"], list)
        self.assertEqual(r.cabeceras["content-type"], "application/json; charset=utf-8")
        self.assertEqual(r.cabeceras["cache-control"], "no-store")
        self.assertEqual(r.cabeceras["x-content-type-options"], "nosniff")

    def test_sobre_de_error(self) -> None:
        c = self.cliente()
        for ruta, estado, codigo in [
            ("/api/no-existe", 404, "ruta_no_encontrada"),
            ("/api/oferta/OF-999999-99", 404, "oferta_no_encontrada"),
            ("/api/oferta/OF-2026-1", 400, "oferta_invalida"),
            ("/api/descubrimiento/xx/candidatos", 400, "corrida_invalida"),
            ("/api/agentes/RUN%20MALO", 400, "ejecucion_invalida"),
        ]:
            r = c.get(ruta)
            self.assertEqual(r.estado, estado, ruta)
            j = r.json()
            self.assertEqual(set(j), {"ok", "error"}, ruta)
            self.assertIs(j["ok"], False)
            self.assertEqual(j["error"]["codigo"], codigo, ruta)
            self.assertIsInstance(j["error"]["mensaje"], str)
            texto = r.cuerpo.decode()
            self.assertNotIn(str(self.raiz), texto, "el error no debe llevar rutas absolutas")
            self.assertNotIn("Traceback", texto)

    def test_metodo_no_permitido_lleva_allow(self) -> None:
        r = self.cliente().llamar("POST", "/api/sistema", json_={})
        self.assertEqual(r.estado, 405)
        self.assertEqual(r.cabeceras["allow"], "GET")
        r = self.cliente().llamar("DELETE", "/api/pulido")
        self.assertEqual(r.estado, 405)

    def test_error_interno_no_expone_traza_ni_rutas(self) -> None:
        from unittest import mock
        app = self.panel()
        with mock.patch("dashboard.api_sistema.sistema", side_effect=RuntimeError(f"fallo en {self.raiz}/secreto")), \
                self.assertLogs("dashboard", level="ERROR"):
            app._rutas = app._tabla_de_rutas()
            r = Cliente(app).get("/api/sistema")
        self.assertEqual(r.estado, 500)
        self.assertEqual(r.json()["error"]["codigo"], "error_interno")
        self.assertNotIn(str(self.raiz), r.cuerpo.decode())
        self.assertNotIn("secreto", r.cuerpo.decode())


class PruebaSistema(PruebaBase):
    def test_sistema_con_freno_infra_y_sin_pausa(self) -> None:
        d = self.cliente().get("/api/sistema").datos
        self.assertEqual(d["entorno"], "prueba")
        self.assertEqual(d["pausa"], {"activa": False, "desde": None, "motivo": None})
        self.assertEqual(d["freno_captura"], {"activo": True, "ts": "2026-11-06T06:03:43Z", "motivo": "HTTP 403 (Document)"})
        self.assertEqual(d["infra"]["semaforo"], "VERDE")
        self.assertEqual(d["panel"], {"version": "1.0.0", "puerto": 8765})
        self.assertTrue(d["modo_demo"])
        self.assertEqual(d["ofertas_reales"], 3)
        self.assertIn("hora", d)

    def test_sistema_infra_items_saneados(self) -> None:
        self.escribir("empresa/infra/estado.json", json.dumps({
            "semaforo": "AMARILLO", "generado_en": "2026-11-09T06:00:00Z", "valido_hasta": "2026-11-09T12:00:00Z",
            "items": [
                {"id": "META-01", "bloque": "meta", "estado": "VERDE", "medido_en": "2026-11-09T06:00:00Z", "expira_en": "2026-11-10T06:00:00Z",
                 "critico": True, "mensaje": "ok", "latencia_ms": 120, "evidencia_ruta": "empresa/infra/healthcheck/x.json", "extra": "no sale"},
                {"id": "STRIPE-01", "bloque": "stripe", "estado": "ROJO", "latencia_ms": True, "critico": "si", "mensaje": "x" * 5000},
                {"sin_id": 1}, "texto suelto", None,
            ]}))
        infra = self.cliente().get("/api/sistema").datos["infra"]
        self.assertEqual(infra["semaforo"], "AMARILLO")
        self.assertEqual(infra["items_total"], 5)
        self.assertEqual([i["id"] for i in infra["items"]], ["META-01", "STRIPE-01"])
        a, b = infra["items"]
        self.assertEqual((a["bloque"], a["estado"], a["critico"], a["latencia_ms"]), ("meta", "VERDE", True, 120))
        self.assertNotIn("extra", a)
        self.assertIsNone(b["latencia_ms"], "un booleano no es una latencia")
        self.assertIsNone(b["critico"], "critico solo si es booleano")
        self.assertLessEqual(len(b["mensaje"]), 300)

    def test_sistema_infra_sin_items_da_lista_vacia(self) -> None:
        self.escribir("empresa/infra/estado.json", json.dumps({"semaforo": "VERDE"}))
        infra = self.cliente().get("/api/sistema").datos["infra"]
        self.assertEqual((infra["items"], infra["items_total"]), ([], 0))

    def test_sistema_sin_nada_no_inventa(self) -> None:
        import shutil
        shutil.rmtree(self.raiz / "empresa")
        shutil.rmtree(self.raiz / "ofertas")
        r = self.cliente().get("/api/sistema")
        d = r.datos
        self.assertIsNone(d["freno_captura"])
        self.assertIsNone(d["infra"])
        self.assertFalse(d["modo_demo"])
        self.assertFalse(d["pausa"]["activa"])
        self.assertTrue(r.json()["avisos"])

    def test_pausa_con_json_y_con_texto_plano_y_freno_ilegible(self) -> None:
        self.escribir("empresa/PAUSA", json.dumps({"ts": "2026-11-09T11:00:00Z", "motivo": "kill", "origen": "panel"}))
        self.assertEqual(self.cliente().get("/api/sistema").datos["pausa"],
                         {"activa": True, "desde": "2026-11-09T11:00:00Z", "motivo": "kill"})
        self.escribir("empresa/PAUSA", "pausado a mano\n")
        p = self.cliente().get("/api/sistema").datos["pausa"]
        self.assertTrue(p["activa"])
        self.assertEqual(p["motivo"], "pausado a mano")
        self.escribir("empresa/captura/freno.json", "{no es json")
        r = self.cliente().get("/api/sistema")
        self.assertTrue(r.datos["freno_captura"]["activo"], "un freno ilegible sigue contando como puesto")
        self.assertTrue(any("freno" in a for a in r.json()["avisos"]))


class PruebaOfertas(PruebaBase):
    def test_lista_con_demo_corrupta_y_sin_estado(self) -> None:
        r = self.cliente().get("/api/ofertas")
        self.assertFalse(r.json()["vacio"])
        filas = {f["oferta_id"]: f for f in r.datos}
        self.assertEqual(list(filas), ["OF-202611-77", "OF-202611-78", "OF-202611-79", "_ejemplo"], "reales primero, demo al final")
        f = filas["OF-202611-77"]
        self.assertFalse(f["demo"])
        self.assertTrue(filas["_ejemplo"]["demo"])
        self.assertEqual(f["fase"], "en_construccion")
        self.assertEqual(f["nivel"], "N2")
        self.assertEqual(f["etapas"]["D7"], "en_QA")
        self.assertEqual(f["gates_pendientes"], ["D7"])
        self.assertEqual(f["gasto"]["acumulado"], {"monto": 1250, "moneda": "EUR"})
        self.assertEqual(f["costo_ia"], {"monto": 412, "moneda": "EUR"})
        self.assertIsNone(f["aviso"])
        corrupta = filas["OF-202611-78"]
        self.assertIsNone(corrupta["fase"], "estado corrupto = sin dato, no cero")
        self.assertEqual(corrupta["etapas"], {})
        self.assertIn("dañado o mal escrito", corrupta["aviso"])
        self.assertIn("todavía no tiene su registro de avance", filas["OF-202611-79"]["aviso"])
        for k in ("gasto", "costo_ia", "fase"):
            self.assertIn(k, corrupta)
        self.assertEqual(corrupta["gasto"], {"hoy": None, "acumulado": None})

    def test_sin_ofertas_es_vacio_con_pista(self) -> None:
        import shutil
        shutil.rmtree(self.raiz / "ofertas")
        j = self.cliente().get("/api/ofertas").json()
        self.assertTrue(j["vacio"])
        self.assertEqual(j["datos"], [])
        self.assertTrue(j["avisos"])

    def test_detalle_de_oferta(self) -> None:
        r = self.cliente().get(f"/api/oferta/{OFERTA}")
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertEqual(set(d), {"estado", "etapas", "proximo_paso", "brief", "mercado", "motor_disponible"})
        self.assertEqual([e["id"] for e in d["etapas"]], ["M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10"])
        e = {x["id"]: x for x in d["etapas"]}
        self.assertEqual(e["D7"]["estado"], "en_QA")
        self.assertTrue(e["D7"]["gate_pendiente"])
        self.assertEqual(e["D1"]["version"], "v1")
        self.assertEqual(e["D1"]["hash"], "sha256:" + "a" * 64)
        self.assertEqual(e["D1"]["nombre"], "Descubrimiento")
        rutas = {a["ruta"] for a in e["D1"]["artefactos"]}
        self.assertIn("01-descubrimiento/informe.md", rutas)
        art = next(a for a in e["D1"]["artefactos"] if a["ruta"].endswith("informe.md"))
        self.assertEqual(art["tipo"], "md")
        self.assertGreater(art["bytes"], 0)
        self.assertRegex(art["mtime"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual([a["ruta"] for a in e["M1"]["artefactos"]], ["mercado.json"])
        qa = {x["archivo"]: x for x in e["D1"]["qa"]}
        self.assertEqual(qa["qa/d1-v1.json"]["veredicto"], "PASS_CON_NOTAS")
        self.assertIn("2 hallazgo(s)", qa["qa/d1-v1.json"]["resumen"])
        self.assertEqual([x["archivo"] for x in e["D5"]["qa"]], ["qa/x1-d5-v1.json"])
        ilegible = e["D2"]["qa"][0]
        self.assertIsNone(ilegible["veredicto"], "qa corrupto: sin veredicto, no inventado")
        self.assertEqual(ilegible["resumen"], "archivo ilegible")
        self.assertEqual(d["brief"]["nicho"], "relaciones")
        self.assertEqual(d["mercado"]["moneda"], "EUR")
        self.assertEqual(e["D8"]["artefactos"][0]["ruta"], "08-operacion/decisiones.jsonl")

    def test_proximo_paso_da_el_comando_exacto_para_firmar(self) -> None:
        pp = self.cliente().get(f"/api/oferta/{OFERTA}").datos["proximo_paso"]
        self.assertEqual(pp["tipo"], "firmar_gate")
        self.assertEqual(pp["etapa"], "D7")
        self.assertEqual(pp["comando"], f"python -m engine.orq firmar --oferta {OFERTA} --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno")
        self.assertIn("motor_disponible", pp)

    def test_oferta_sin_estado_y_con_estado_corrupto(self) -> None:
        sin = self.cliente().get("/api/oferta/OF-202611-79").json()
        self.assertTrue(sin["vacio"])
        self.assertIsNone(sin["datos"]["estado"])
        self.assertEqual(sin["datos"]["proximo_paso"]["tipo"], "sin_estado")
        self.assertTrue(sin["avisos"])
        roto = self.cliente().get("/api/oferta/OF-202611-78").json()
        self.assertTrue(roto["vacio"])
        self.assertTrue(any("dañado o mal escrito" in a for a in roto["avisos"]))

    def test_archivo_texto_hostil_pasa_intacto_como_dato(self) -> None:
        r = self.cliente().get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=01-descubrimiento/informe.md")
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertEqual(d["tipo"], "md")
        self.assertIn(HOSTIL, d["contenido"], "HTML y U+202E llegan íntegros (el frontend los escapa)")
        self.assertFalse(d["truncado"])
        self.assertEqual(d["ruta"], "01-descubrimiento/informe.md")
        self.assertTrue(r.cuerpo.isascii(), "el JSON es ASCII: U+202E viaja como \\u202e")
        self.assertIn(b"\\u202e", r.cuerpo)

    def test_archivo_tipos_truncado_imagen_vacio(self) -> None:
        c = self.cliente()
        j = c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=03-oferta/oferta.json").datos
        self.assertEqual(j["tipo"], "json")
        self.assertEqual(json.loads(j["contenido"])["precio"]["monto"], 1900)
        self.assertEqual(c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=../OF-202611-78/estado.json").estado, 403)
        y = c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=00-brief.yaml").datos
        self.assertEqual(y["tipo"], "yaml")
        h = c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=05-landing/sitio/index.html").datos
        self.assertEqual(h["tipo"], "html")
        img = c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=05-landing/imagenes/hero.png").datos
        self.assertEqual(img["tipo"], "imagen")
        self.assertTrue(img["contenido"].startswith("data:image/png;base64,"))
        self.escribir(f"ofertas/{OFERTA}/grande.txt", "a" * (400 * 1024 + 500))
        g = c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=grande.txt")
        self.assertEqual(len(g.datos["contenido"]), 400 * 1024)
        self.assertTrue(g.datos["truncado"])
        self.assertEqual(g.datos["bytes"], 400 * 1024 + 500)
        self.escribir(f"ofertas/{OFERTA}/enorme.png", b"\x89PNG" + b"0" * (1024 * 1024 + 10))
        e = c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=enorme.png")
        self.assertIsNone(e.datos["contenido"])
        self.assertTrue(e.datos["truncado"])
        self.escribir(f"ofertas/{OFERTA}/binario.txt", bytes(range(256)) * 8)
        self.assertEqual(c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=binario.txt").json()["error"]["codigo"], "archivo_binario")
        ausente = c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=no/existe.md").json()
        self.assertTrue(ausente["vacio"])
        self.assertEqual(ausente["fuente"], [f"ofertas/{OFERTA}/no/existe.md"])
        self.assertEqual(c.get(f"/api/oferta/{OFERTA}/archivo", consulta="ruta=01-descubrimiento").json()["error"]["codigo"], "no_es_archivo")
        self.assertEqual(c.get(f"/api/oferta/{OFERTA}/archivo").json()["error"]["codigo"], "ruta_requerida")

    def test_campanas_y_operacion(self) -> None:
        c = self.cliente()
        camp = c.get(f"/api/campanas/{OFERTA}")
        d = camp.datos
        self.assertEqual(set(d), {"campana", "preflight", "ids_meta", "aprobacion", "estado"})
        self.assertEqual(d["campana"]["estado"], "borrador")
        self.assertIsNone(d["preflight"], "preflight ausente = null, no objeto vacío")
        self.assertEqual(d["estado"]["etapa"], "en_QA")
        self.assertTrue(d["estado"]["gate_pendiente"])
        self.assertFalse(camp.json()["vacio"])
        sin = c.get("/api/campanas/OF-202611-79").json()
        self.assertTrue(sin["vacio"])
        op = c.get(f"/api/operacion/{OFERTA}")
        d = op.datos
        self.assertEqual([k["fecha"] for k in d["kpi_dia"]], ["2026-11-10", "2026-11-11"])
        self.assertEqual([x["accion"] for x in d["decisiones"]], ["SEGUIR", "MATAR"])
        self.assertEqual(d["ordenes"][0]["orden_id"], "ORD-OF-202611-77-0001")
        self.assertEqual(d["veredicto"]["estado"], "INCONCLUSA")
        self.assertFalse(op.json()["vacio"])
        vacia = c.get("/api/operacion/OF-202611-79").json()
        self.assertTrue(vacia["vacio"])
        self.assertEqual(vacia["datos"]["kpi_dia"], [])
        self.assertIsNone(vacia["datos"]["veredicto"])

    def test_operacion_tolera_jsonl_corrupto_y_kpi_corrupto(self) -> None:
        self.escribir(f"ofertas/{OFERTA}/08-operacion/decisiones.jsonl", '{"accion": "SEGUIR"}\n{roto\n{"accion": "MATAR"}\n')
        self.escribir(f"ofertas/{OFERTA}/08-operacion/diario/2026-11-12/kpi_oferta_dia.json", "NaN")
        j = self.cliente().get(f"/api/operacion/{OFERTA}").json()
        self.assertEqual([x["accion"] for x in j["datos"]["decisiones"]], ["SEGUIR", "MATAR"])
        self.assertEqual(len(j["datos"]["kpi_dia"]), 2, "el kpi corrupto se omite, no se cuenta como cero")
        self.assertTrue(any("no se pudieron leer" in a for a in j["avisos"]))
        self.assertTrue(any("kpi_oferta_dia.json" in a for a in j["avisos"]))


class PruebaDescubrimiento(PruebaBase):
    def test_corridas_con_conteos_y_null_cuando_falta(self) -> None:
        r = self.cliente().get("/api/descubrimiento/corridas")
        filas = {f["corrida_id"]: f for f in r.datos}
        self.assertEqual(list(filas), ["2026-11-07-a", CORRIDA], "más recientes primero")
        z = filas[CORRIDA]
        self.assertEqual((z["consultas_ok"], z["consultas_tope"], z["paginas"], z["etiquetadas"], z["candidatas"], z["pasan_traccion"], z["fichas"]),
                         (2, 120, 12, 10, 9, 2, 3))
        self.assertEqual(z["consultas_plan"], 3, "el plan de la pasada 2 es el vigente (acumulado)")
        self.assertEqual(z["actualizado_en"], "2026-11-06T06:25:41Z")
        a = filas["2026-11-07-a"]
        for k in ("consultas_ok", "paginas", "etiquetadas", "candidatas", "pasan_traccion", "fichas"):
            self.assertIsNone(a[k], f"{k}: sin archivo = null, nunca 0")
        self.assertEqual(a["consultas_tope"], 120)

    def test_sin_barrido_es_vacio(self) -> None:
        import shutil
        shutil.rmtree(self.raiz / "empresa" / "barrido")
        j = self.cliente().get("/api/descubrimiento/corridas").json()
        self.assertTrue(j["vacio"])
        self.assertEqual(j["datos"], [])
        self.assertIn("barrido", j["avisos"][0])

    def test_documentos_de_la_corrida(self) -> None:
        c = self.cliente()
        cand = c.get(f"/api/descubrimiento/{CORRIDA}/candidatos")
        self.assertEqual(set(cand.datos) >= {"temas", "sin_tema", "resumen", "matriz_tema_pais", "exportadores"}, True)
        self.assertEqual(cand.datos["temas"][0]["tema"], HOSTIL, "texto de anunciantes: dato intacto")
        self.assertEqual(c.get(f"/api/descubrimiento/{CORRIDA}/fichas").datos["ofertas"][1]["modelo_id"], "m2")
        self.assertEqual(c.get(f"/api/descubrimiento/{CORRIDA}/etiquetas").datos["cobertura"]["etiquetadas"], 10)
        plan = c.get(f"/api/descubrimiento/{CORRIDA}/plan").datos
        self.assertEqual(plan["plan_archivo"], f"{CORRIDA}.pasada-2.json")
        self.assertEqual(plan["pasadas"], [1, 2])
        self.assertEqual(len(plan["consultas"]), 3)

    def test_documento_ausente_es_vacio_con_la_fuente_esperada(self) -> None:
        j = self.cliente().get("/api/descubrimiento/2026-11-07-a/fichas").json()
        self.assertTrue(j["vacio"])
        self.assertIsNone(j["datos"])
        self.assertEqual(j["fuente"], ["empresa/barrido/candidatos/2026-11-07-a/fichas_borrador.json"])
        self.assertEqual(self.cliente().get("/api/descubrimiento/2031-01-01-a/candidatos").json()["vacio"], True)

    def test_estado_de_la_corrida(self) -> None:
        d = self.cliente().get(f"/api/descubrimiento/{CORRIDA}/estado").datos
        self.assertEqual(d["crudo"], {"existe": True, "ok": 2, "error": 1})
        self.assertEqual(d["plan"]["consultas"], 3)
        self.assertEqual(d["paginas"]["total"], 12)
        self.assertEqual(d["fichas"]["total"], 3)
        self.assertTrue(d["memoria"]["existe"])
        self.assertTrue(d["freno"]["activo"])
        self.assertIn("scripts.modelado.barrido estado", d["comando_estado"])
        vacio = self.cliente().get("/api/descubrimiento/2031-01-01-a/estado").json()
        self.assertTrue(vacio["vacio"])

    def test_paginas_filtradas_y_paginadas(self) -> None:
        c = self.cliente()
        d = c.get(f"/api/descubrimiento/{CORRIDA}/paginas").datos
        self.assertEqual((d["total"], d["total_sin_filtrar"], d["pagina"], d["por_pagina"], d["total_paginas"]), (12, 12, 1, 50, 1))
        d = c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="por_pagina=5&pagina=3").datos
        self.assertEqual(len(d["paginas"]), 2)
        self.assertEqual(d["total_paginas"], 3)
        guia = c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="q=guía").datos
        self.assertEqual(guia["total"], 6)
        self.assertTrue(all("Guía" in p["page_name"] for p in guia["paginas"]))
        mx = c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="pais=mx").datos
        self.assertTrue(all("MX" in p["paises"] for p in mx["paginas"]))
        comp = c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="estado=completa").datos
        self.assertTrue(all(p["medicion"]["estado"] == "completa" for p in comp["paginas"]))
        titulo = c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="q=onerror").datos
        self.assertEqual(titulo["total"], 1, "la búsqueda mira también los títulos")
        self.assertEqual(c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="por_pagina=abc").estado, 400)
        tope = c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="por_pagina=99999").datos
        self.assertEqual(tope["por_pagina"], 200)
        fuera = c.get(f"/api/descubrimiento/{CORRIDA}/paginas", consulta="pagina=99").datos
        self.assertEqual((fuera["paginas"], fuera["total"]), ([], 12))

    def test_json_corrupto_de_la_corrida_no_rompe(self) -> None:
        self.escribir(f"empresa/barrido/paginas/{CORRIDA}.json", '{"paginas": [1, 2,')
        j = self.cliente().get(f"/api/descubrimiento/{CORRIDA}/paginas").json()
        self.assertTrue(j["vacio"])
        self.assertTrue(any("dañado o mal escrito" in a for a in j["avisos"]))
        fila = next(f for f in self.cliente().get("/api/descubrimiento/corridas").datos if f["corrida_id"] == CORRIDA)
        self.assertIsNone(fila["paginas"])


class PruebaEmpresa(PruebaBase):
    def test_finanzas_vacio_y_con_datos(self) -> None:
        j = self.cliente().get("/api/finanzas").json()
        self.assertTrue(j["vacio"])
        self.assertEqual(j["datos"], {"ledger": [], "pnl": None, "conciliacion": None, "alertas": []})
        self.assertIn("empresa/finanzas/ledger.jsonl", j["fuente"])
        self.escribir("empresa/finanzas/ledger.jsonl", '{"clave_natural": "a"}\n{"clave_natural": "b"}\n')
        self.escribir("empresa/finanzas/pnl.json", '{"moneda_base": "USD"}')
        j = self.cliente().get("/api/finanzas").json()
        self.assertFalse(j["vacio"])
        self.assertEqual(len(j["datos"]["ledger"]), 2)
        self.assertEqual(j["datos"]["pnl"], {"moneda_base": "USD"})
        self.assertIsNone(j["datos"]["conciliacion"])

    def test_cumplimiento(self) -> None:
        j = self.cliente().get("/api/cumplimiento")
        d = j.datos
        self.assertEqual([x["archivo"] for x in d["dictamenes"]], ["qa/x1-d5-v1.json"])
        self.assertEqual(d["dictamenes"][0]["semaforo"], "VERDE")
        self.assertEqual(d["dictamenes"][0]["etapa_objetivo"], "D5")
        sellos = {s["archivo"]: s for s in d["sellos"]}
        self.assertTrue(sellos["sello-d5.json"]["legible"])
        self.assertFalse(sellos["sello-d5.json"]["vigente"], "vigencia_hasta anterior a 'ahora'")
        self.assertFalse(sellos["roto.json"]["legible"])

    def test_parametros_y_limites_con_nulos(self) -> None:
        j = self.cliente().get("/api/parametros")
        d = j.datos
        self.assertIn("moneda_limites", d["limites"]["nulos"])
        self.assertIn("maximos.gasto_diario", d["limites"]["nulos"])
        self.assertIn("acciones_gate_humano", d["limites"]["listas_vacias"])
        self.assertEqual(d["limites"]["nulos_solo_verde"], [c for c in d["limites"]["nulos"] if c.split(".")[0] in CLAVES_NULO_SOLO_VERDE])
        self.assertEqual(d["limites"]["valores"]["maximos"]["ofertas_simultaneas"], 2)
        self.assertEqual(d["parametros"]["grupos"]["ingesta"]["tolerancia_seg"]["valor"], 120)
        self.assertEqual(d["parametros"]["sin_valor"], ["testeo.cpa_max"])
        self.assertEqual(d["autonomia"]["nivel_por_etapa"]["D1"]["nivel"], "N0")
        self.assertEqual(d["propuestas"], [{"archivo": "empresa/propuestas/parametros-b0.yaml", "origen": "empresa/propuestas",
                                            "claves": ["watchdog.latido_cada_min", "watchdog.ciclo_max_min"]}])
        # las fechas YAML sin comillas se serializan como texto ISO
        self.assertEqual(d["autonomia"]["nivel_por_etapa"]["D1"]["desde"], "2026-11-06")

    def test_yaml_con_alias_se_rechaza_sin_romper(self) -> None:
        self.escribir("empresa/limites.yaml", "a: &x [1, 2]\nb: *x\n")
        j = self.cliente().get("/api/parametros").json()
        self.assertIsNone(j["datos"]["limites"]["valores"])
        self.assertTrue(any("dañado o mal escrito" in a for a in j["avisos"]))

    def test_yaml_gigante_y_json_gigante_o_con_nan_se_omiten(self) -> None:
        self.escribir("empresa/limites.yaml", "x: " + "a" * (2 * 1024 * 1024))
        j = self.cliente().get("/api/parametros").json()
        self.assertIsNone(j["datos"]["limites"]["valores"])
        self.assertTrue(any("demasiado grande" in a for a in j["avisos"]))
        self.escribir("empresa/finanzas/pnl.json", "[" + "1," * (5 * 1024 * 1024) + "1]")
        j = self.cliente().get("/api/finanzas").json()
        self.assertIsNone(j["datos"]["pnl"])
        self.assertTrue(any("demasiado grande" in a for a in j["avisos"]))
        for texto in ('{"a": NaN}', '{"a": Infinity}', '{"a": 1e999}', "[" * 100000):
            self.escribir("empresa/finanzas/pnl.json", texto)
            j = self.cliente().get("/api/finanzas").json()
            self.assertIsNone(j["datos"]["pnl"], texto[:20])
            self.assertTrue(any("dañado o mal escrito" in a for a in j["avisos"]), texto[:20])

    def test_skills_vacio_y_con_skill(self) -> None:
        j = self.cliente().get("/api/skills").json()
        self.assertTrue(j["vacio"])
        self.assertEqual(j["datos"], [])
        self.escribir(".claude/skills/f9-demo/SKILL.md",
                      "---\nname: f9-demo\ndescription: Skill de prueba\nversion: 0.2.0\n---\n# Demo\n\n"
                      "## Definición de listo (DoD)\n- [x] Criterio uno\n- [ ] Criterio dos\n- Criterio tres\n\n## Otra\n- [x] no cuenta\n")
        self.escribir(".claude/skills/f9-demo/rubric.md", "r\n")
        self.escribir(".claude/skills/f9-demo/templates/a.md", "t\n")
        self.escribir(".claude/skills/f9-demo/CHANGELOG.md", "## 0.2.0\n- algo\n")
        self.escribir(".claude/skills/v1-skill/SKILL.md", "---\nname: v1-skill\nversion: 1.0.0\n---\n# v1\n")
        self.escribir(".claude/agents/f9-maker.md", "x")
        self.escribir(".claude/agents/f9-qa.md", "x")
        self.escribir(".claude/agents/README.md", "x")
        self.escribir(".claude/skills/MALO_SLUG/SKILL.md", "x")
        d = {s["slug"]: s for s in self.cliente().get("/api/skills").datos}
        self.assertEqual(set(d), {"f9-demo", "v1-skill"}, "los slugs inválidos se ignoran")
        s = d["f9-demo"]
        self.assertEqual((s["version"], s["estado"], s["descripcion"]), ("0.2.0", "borrador", "Skill de prueba"))
        self.assertEqual(s["archivos"]["rubric.md"], True)
        self.assertEqual(s["archivos"]["templates"], 1)
        self.assertEqual(s["archivos"]["evals"], 0)
        self.assertEqual(s["agentes"], ["f9-maker", "f9-qa"])
        self.assertEqual(s["dod"], [{"criterio": "Criterio uno", "ok": True}, {"criterio": "Criterio dos", "ok": False},
                                    {"criterio": "Criterio tres", "ok": None}])
        self.assertEqual(s["lineas_skill_md"], 14)
        self.assertEqual(d["v1-skill"]["estado"], "v1")
        self.assertEqual(d["v1-skill"]["agentes"], [])


class PruebaRegistro(PruebaBase):
    def test_registro_vacio_sin_demo(self) -> None:
        import shutil
        shutil.rmtree(self.raiz / "ofertas" / "_ejemplo")
        j = self.cliente().get("/api/registro").json()
        self.assertTrue(j["vacio"])
        self.assertEqual(j["datos"]["lineas"], [])
        self.assertIsNone(j["datos"]["cadena_ok"])
        self.assertEqual(j["fuente"], ["empresa/registro.jsonl"])
        self.assertFalse(j["demo"])
        self.assertEqual(self.cliente().get("/api/agentes").json()["vacio"], True)

    def test_registro_con_cadena_valida(self) -> None:
        self.poner_registro()
        j = self.cliente().get("/api/registro").json()
        d = j["datos"]
        self.assertFalse(j["vacio"])
        self.assertTrue(d["cadena_ok"])
        self.assertEqual(d["total"], 6)
        self.assertEqual([x["n"] for x in d["lineas"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual(d["siguiente"], 7)
        self.assertEqual(d["lineas"][0]["entrada_resumen"], HOSTIL, "texto con HTML y U+202E intacto")
        self.assertFalse(j["demo"])

    def test_registro_desde_limite_y_filtros(self) -> None:
        self.poner_registro()
        c = self.cliente()
        d = c.get("/api/registro", consulta="limite=2").datos
        self.assertEqual([x["n"] for x in d["lineas"]], [5, 6], "sin desde: la cola")
        d = c.get("/api/registro", consulta="desde=2&limite=2").datos
        self.assertEqual([x["n"] for x in d["lineas"]], [2, 3])
        self.assertEqual(d["siguiente"], 4)
        d = c.get("/api/registro", consulta="desde=5").datos
        self.assertEqual([x["n"] for x in d["lineas"]], [5, 6])
        self.assertEqual(d["siguiente"], 7)
        d = c.get("/api/registro", consulta="desde=99").datos
        self.assertEqual((d["lineas"], d["siguiente"]), ([], 7))
        d = c.get("/api/registro", consulta="etapa=D2").datos
        self.assertEqual([x["n"] for x in d["lineas"]], [2, 5])
        self.assertEqual([x["n"] for x in c.get("/api/registro", consulta="agente=motor").datos["lineas"]], [2, 5])
        self.assertEqual(c.get("/api/registro", consulta="oferta=OF-202611-99").datos["lineas"], [])
        self.assertEqual(c.get("/api/registro", consulta="desde=abc").estado, 400)

    def test_cadena_rota_se_detecta(self) -> None:
        self.poner_registro("registro_roto.jsonl")
        j = self.cliente().get("/api/registro").json()
        self.assertIs(j["datos"]["cadena_ok"], False)
        self.assertTrue(any("Historial alterado" in a for a in j["avisos"]))

    def test_linea_corrupta_se_marca_y_no_rompe(self) -> None:
        self.poner_registro()
        with open(self.raiz / "empresa" / "registro.jsonl", "a", encoding="utf-8") as f:
            f.write("{esto no es json\n")
        j = self.cliente().get("/api/registro").json()
        ultima = j["datos"]["lineas"][-1]
        self.assertTrue(ultima["_ilegible"])
        self.assertEqual(ultima["n"], 7)
        self.assertIs(j["datos"]["cadena_ok"], False)
        self.assertTrue(any("no se pudieron leer" in a for a in j["avisos"]))

    def test_demo_cuando_no_hay_registro_real(self) -> None:
        self.poner_registro()
        (self.raiz / "ofertas" / "_ejemplo" / "_empresa").mkdir()
        os.replace(self.raiz / "empresa" / "registro.jsonl", self.raiz / "ofertas" / "_ejemplo" / "_empresa" / "registro.jsonl")
        os.replace(self.raiz / "empresa" / "costos.jsonl", self.raiz / "ofertas" / "_ejemplo" / "_empresa" / "costos.jsonl")
        j = self.cliente().get("/api/registro").json()
        self.assertTrue(j["demo"])
        self.assertEqual(j["fuente"], ["ofertas/_ejemplo/_empresa/registro.jsonl"])
        self.assertTrue(any("DEMOSTRACIÓN" in a for a in j["avisos"]))
        self.assertEqual(j["datos"]["total"], 6)

    def test_agentes_agrupados_con_costos(self) -> None:
        self.poner_registro()
        c = self.cliente()
        filas = c.get("/api/agentes").datos
        self.assertEqual([f["ejecucion_id"] for f in filas], ["RUN-20261106-02", "RUN-20261106-01"], "más recientes primero")
        f1 = next(f for f in filas if f["ejecucion_id"] == "RUN-20261106-01")
        self.assertEqual((f1["oferta_id"], f1["etapa"], f1["agente"], f1["modo"], f1["eventos"]), (OFERTA, "D1", "d1-maker", "dry_run", 3))
        self.assertEqual(f1["costo"], {"monto": 500, "moneda": "EUR"})
        self.assertEqual(f1["costo_fuente"], "costos.jsonl")
        self.assertEqual(f1["inicio"], "2026-11-06T10:00:00Z")
        self.assertEqual(f1["fin"], "2026-11-06T12:00:00Z")
        f2 = next(f for f in filas if f["ejecucion_id"] == "RUN-20261106-02")
        self.assertEqual(f2["estado"], "error", "una línea con error vuelve la ejecución error")
        self.assertEqual(f2["costo"], {"monto": 90, "moneda": "EUR"})
        self.assertEqual([f["ejecucion_id"] for f in c.get("/api/agentes", consulta="agente=motor").datos], ["RUN-20261106-02", "RUN-20261106-01"])
        self.assertEqual(c.get("/api/agentes", consulta="etapa=D9").datos, [])

    def test_detalle_de_ejecucion(self) -> None:
        self.poner_registro()
        c = self.cliente()
        d = c.get("/api/agentes/RUN-20261106-01").datos
        self.assertEqual(len(d["eventos"]), 3)
        self.assertEqual(d["n_eventos"], 3)
        self.assertEqual(d["eventos"][0]["n"], 1)
        self.assertEqual(c.get("/api/agentes/RUN-20261106-99").estado, 404)
        self.assertEqual(c.get("/api/agentes/RUN-20261106-99").json()["error"]["codigo"], "ejecucion_no_encontrada")


if __name__ == "__main__":
    unittest.main()
