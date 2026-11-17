"""Tablero «Negocio» (``#/negocio``): cálculo de la cartera (``dashboard/negocio.py``) y ``GET /api/negocio`` / ``/api/negocio/documento``.

Cubre: ganancia neta (neto − Meta − producción − fijos prorrateados), ROAS bruto y neto, CPA y punto de equilibrio (real y estimado),
agrupación de varias tiendas y varios tests en una oferta, «Requiere tu atención» (CPA sobre equilibrio, 3 × equilibrio sin ventas, freno
diario, datos viejos), que no salen datos de compradores, y que los números coinciden con ``libro_de_tests.py`` sobre el mismo libro.
Raíz temporal con fixtures (nunca ``ofertas/`` real).
"""
from __future__ import annotations

import contextlib
import copy
import datetime as _dt
import importlib.util
import io
import json
import re
import unittest
import urllib.parse
from pathlib import Path

from dashboard import negocio as N
from tests.dashboard.test_servidor_apoyo import PruebaBase, reloj_fijo

RAIZ_REPO = Path(__file__).resolve().parents[2]
SCRIPT_LIBRO = RAIZ_REPO / ".claude" / "skills" / "escalar-oferta" / "scripts" / "libro_de_tests.py"
AHORA = _dt.datetime(2026, 11, 13, 0, 0, tzinfo=_dt.timezone.utc)   # 12-nov 21:00 en Argentina

LIBRO = {
    "tipos_de_cambio": {"MXN": 0.05, "BRL": 0.2, "USD": 1.0},
    "precio_credito_kie_usd": 0.005,
    "precio_imagen_gemini_usd": 0.1,
    "costos_fijos_compartidos": [
        {"concepto": "Plan de la tienda", "usd_mes": None},
        {"concepto": "Dominio", "usd_mes": 30.0},   # 1 USD por día, repartido entre 3 ofertas
    ],
    "tests": [
        {
            "nombre": "Kit Uno", "mercado": "MX", "tipo_funnel": "tsl + niveles", "inicio": "2026-11-12T00:00:00-06:00", "estado": "activo",
            "campana": "111", "tienda": ["kit-uno", "kit-uno-basico"], "corte": "2026-11-12T20:00-03:00",
            "produccion": {"kie_creditos": 2000, "gemini_imagenes": 10, "otros_usd": 0},
            "meta": {"gasto_usd": 30.0, "impresiones": 1000, "clics_enlace": 40, "visitas_landing_meta": 30, "inicios_pago_meta": 8, "compras_meta": 5, "valor_compras_meta_usd": 45.0},
            "tienda_embudo": {"landing": 100, "checkout": 10, "compras": 3,
                              "por_tienda": {"kit-uno": {"landing": 100, "checkout": 7, "compras": 2}, "kit-uno-basico": {"landing": 0, "checkout": 3, "compras": 1}}},
            "ventas": [
                {"orden": "A1", "moneda": "MXN", "bruto": 300.0, "neto": 280.0, "fecha": "2026-11-12", "tienda": "kit-uno", "correo": "persona@ejemplo.com", "nombre": "Persona Real"},
                {"orden": "A2", "moneda": "MXN", "bruto": 300.0, "neto": 280.0, "fecha": "2026-11-12", "tienda": "kit-uno"},
                {"orden": "A3", "moneda": "MXN", "bruto": 160.0, "neto": 140.0, "fecha": "2026-11-12", "tienda": "kit-uno-basico", "nivel": "básico"},
            ],
            "historial_diario": [{"fecha": "2026-11-12", "campana": "111", "gasto_usd": 30.0, "compras_meta": 5}],
            "ficha": {"tiendas": [{"slug": "kit-uno", "nombre": "Kit Uno", "url": "https://kit-uno.impultienda.ar/", "precio": {"moneda": "MXN", "monto": 300, "usd": 15}},
                                  {"slug": "kit-uno-basico", "nombre": "Kit Uno Básico", "url": "javascript:alert(1)"}],
                      "landing_original": "http://inseguro.example/",
                      "campanas": [{"id": "111", "presupuesto_diario_usd": 50, "estado": "ACTIVE"}]},
        },
        {   # segundo test de la MISMA oferta (otra tanda): se suma
            "nombre": "Kit Uno · tanda 2", "oferta": "Kit Uno", "mercado": "MX", "inicio": "2026-11-12T00:00:00-06:00", "estado": "activo",
            "campana": "112", "tienda": ["kit-uno"], "corte": "2026-11-12T20:00-03:00",
            "produccion": {"kie_creditos": 0, "gemini_imagenes": 0},
            "meta": {"gasto_usd": 6.0, "compras_meta": 0},
            "tienda_embudo": {"landing": 0, "checkout": 0, "compras": 0},
            "ventas": [],
        },
        {
            "nombre": "Mapa Dos", "mercado": "MX", "inicio": "2026-11-11T00:00:00-06:00", "estado": "activo", "campana": "222", "tienda": ["mapa-dos"],
            "corte": "2026-11-12T20:00-03:00", "produccion": {"kie_creditos": 1000, "gemini_imagenes": 0},
            "meta": {"gasto_usd": 50.0, "compras_meta": 1}, "tienda_embudo": {"landing": 200, "checkout": 30, "compras": 1},
            "ventas": [{"orden": "B1", "moneda": "MXN", "bruto": 300.0, "neto": 280.0, "fecha": "2026-11-12"}],
            "backend": {"estado": "activo", "desde": "2026-11-12", "upsells": [{"nombre": "Extra Uno", "precio_usd": 21}, {"nombre": "Extra Dos", "precio_usd": 13}],
                        "tiendas": ["mapa-dos"], "nota": "Embudo activo."},
            "renovaciones": [{"ronda": "R2", "inicio": "2026-11-12T00:00:00-06:00", "estado": "activa", "anuncios": 10, "nota": "7 iteraciones y 3 nuevos"}],
        },
        {
            "nombre": "Camino Tres", "mercado": "BR", "inicio": "2026-11-10T00:00:00-03:00", "estado": "activo", "campana": "333", "tienda": ["camino-tres"],
            "corte": "2026-11-11T08:00-03:00", "produccion": {"kie_creditos": 0, "gemini_imagenes": 0},
            "meta": {"gasto_usd": 40.0, "compras_meta": 0}, "tienda_embudo": {"landing": 60, "checkout": 2, "compras": 0},
            "ventas": [], "ficha": {"equilibrio_estimado_usd": 12.0, "tiendas": [{"slug": "camino-tres", "rol": "principal", "precio": {"moneda": "BRL", "monto": 69, "usd": 13.0}}]},
        },
    ],
}


def _ofertas(d):
    return {o["nombre"]: o for o in d["ofertas"]}


class PruebaCalculo(unittest.TestCase):
    def setUp(self) -> None:
        self.d = N.calcular(copy.deepcopy(LIBRO), AHORA)
        self.o = _ofertas(self.d)

    def test_agrupa_tests_y_tiendas_de_una_misma_oferta(self) -> None:
        self.assertEqual([o["nombre"] for o in self.d["ofertas"]], ["Kit Uno", "Mapa Dos", "Camino Tres"])
        k = self.o["Kit Uno"]
        self.assertEqual(k["tests"], 2)
        self.assertEqual(k["gasto_meta"], 36.0, "30 + 6 de la segunda tanda")
        self.assertEqual(k["campanas"], ["111", "112"])
        self.assertEqual(k["ventas_n"], 3)
        tiendas = {t["slug"]: t for t in k["por_tienda"]}
        self.assertEqual(set(tiendas), {"kit-uno", "kit-uno-basico"})
        self.assertEqual(tiendas["kit-uno"]["ventas"], 2)
        self.assertEqual(tiendas["kit-uno-basico"]["ventas"], 1)
        self.assertEqual(tiendas["kit-uno-basico"]["neto_usd"], 7.0)
        self.assertEqual(tiendas["kit-uno"]["embudo"]["checkout"], 7)

    def test_ganancia_neta_roas_cpa_y_equilibrio(self) -> None:
        k = self.o["Kit Uno"]
        self.assertEqual(k["bruto"], 38.0)            # (300+300+160) × 0,05
        self.assertEqual(k["neto"], 35.0)             # (280+280+140) × 0,05
        self.assertEqual(k["produccion"]["total"], 11.0)   # 2000 × 0,005 + 10 × 0,1
        self.assertEqual(k["dias_pauta"], 1)
        self.assertAlmostEqual(k["fijos"], 1 / 3, places=3)   # 30 USD/mes → 1 USD/día, entre 3 ofertas
        self.assertEqual(k["neto_menos_meta"], -1.0)
        self.assertEqual(k["neto_menos_todo"], -12.0)
        self.assertEqual(k["ganancia_neta"], round(35 - 36 - 11 - 1 / 3, 2))
        self.assertEqual(k["roas_bruto"], round(38 / 36, 2))
        self.assertEqual(k["roas_neto"], round(35 / 36, 2))
        self.assertEqual(k["cpa"], 12.0)
        self.assertEqual(k["equilibrio"], round(35 / 3, 2))
        self.assertEqual(k["equilibrio_fuente"], "real")
        self.assertEqual(k["semaforo_cpa"]["zona"], "sobre", "12 > 11,67: cada venta cuesta más de lo que deja")
        self.assertEqual(k["veredicto"], "perdiendo")
        self.assertEqual(k["embudo"]["pct_checkout"], 10.0)
        self.assertEqual(k["embudo"]["tono_compra"], "ok")   # 3/10 = 30 %
        self.assertEqual(k["diferencia_atribucion"], 2, "Meta cuenta 5, reales 3")

    def test_roas_meta_bruto_neto_real_y_costos(self) -> None:
        k = self.o["Kit Uno"]
        self.assertEqual(k["roas_meta"], round(45 / 36, 2), "valor de compras de Meta ÷ gasto; la tanda 2 no trae valor y suma 0")
        self.assertEqual(k["valor_compras_meta"], 45.0)
        self.assertEqual(k["roas_bruto"], round(38 / 36, 2))
        self.assertEqual(k["roas_neto"], round(35 / 36, 2))
        self.assertEqual(k["roas_real"], round(35 / (36 + 11 + 1 / 3), 2), "neto ÷ (Meta + producción + fijos)")
        self.assertEqual(k["comisiones"], 3.0)
        self.assertEqual(k["ganancia_contra_meta"], -1.0)
        self.assertEqual(k["costos"], {"meta": 36.0, "produccion": 11.0, "fijos": round(1 / 3, 4), "total": round(36 + 11 + 1 / 3, 2)})
        self.assertEqual(k["ticket_medio"], round(38 / 3, 2))
        self.assertEqual(k["compras_meta"], 5)
        self.assertIsNone(self.o["Mapa Dos"]["roas_meta"], "sin el campo en el libro: sin dato, nunca 0")
        self.assertIsNone(self.o["Camino Tres"]["ticket_medio"])
        self.assertEqual(self.o["Camino Tres"]["roas_neto"], 0.0, "gastó y no vendió: ROAS 0")
        c = self.d["cartera"]
        self.assertEqual(c["roas_meta"], round(45 / 126, 2))
        self.assertEqual(c["costos_total"], round(c["gasto_meta"] + c["produccion"] + c["fijos"], 2))
        self.assertEqual(c["roas_real"], round(c["neto"] / (c["gasto_meta"] + c["produccion"] + c["fijos"]), 2))
        self.assertEqual(c["comisiones"], round(c["bruto"] - c["neto"], 2))

    def test_cartera_suma_sin_redondeos_intermedios(self) -> None:
        c = self.d["cartera"]
        self.assertEqual(c["gasto_meta"], 126.0)
        self.assertEqual(c["ventas"], 4)
        self.assertEqual(c["neto"], 49.0)
        self.assertEqual(c["roas_neto"], round(49 / 126, 2))
        self.assertEqual(c["cpa_medio"], 31.5)
        self.assertEqual(c["fijos_pendientes"], ["Plan de la tienda"])
        self.assertEqual(c["ganando"] + c["perdiendo"] + c["sin_pauta"], 3)
        self.assertEqual(c["presupuesto_diario"], 50.0)

    def test_equilibrio_estimado_y_corte_a_1_5_tickets(self) -> None:
        t = self.o["Camino Tres"]
        self.assertEqual(t["equilibrio"], 12.0)
        self.assertEqual(t["equilibrio_fuente"], "estimado")
        self.assertEqual(t["cpa"], None)
        self.assertEqual(t["ticket_front"], 13.0)
        self.assertEqual(t["corte_usd"], 19.5)
        self.assertEqual(t["semaforo_cpa"]["zona"], "sin_ventas_corte", "40 USD ≥ 1,5 × 13 sin ventas")
        self.assertEqual(t["accion_sugerida"]["clave"], "cortar")

    def test_requiere_tu_atencion(self) -> None:
        a = self.d["atencion"]
        titulos = [x["titulo"] for x in a]
        self.assertTrue(any("Kit Uno: cada venta cuesta más" in t for t in titulos))
        self.assertTrue(any(x["tono"] == "critico" and "Camino Tres" in x["titulo"] and "1,5 tickets" in x["titulo"] for x in a))
        self.assertTrue(any("Camino Tres: datos de hace" in t for t in titulos), "corte de hace 40 horas")
        self.assertTrue(any("Meta cuenta más compras" in t for t in titulos))
        self.assertTrue(any("Falta un costo fijo" in t for t in titulos))
        self.assertFalse(any("freno" in t.lower() for t in titulos), "36 + 50 + 40 lejos de 300")
        self.assertTrue(self.d["corte"]["viejo"])

    def test_sin_frenos_de_cuenta(self) -> None:
        """El dueño eliminó los frenos de 300 USD/día y −3.000 USD (13-nov): ni avisos ni referencias, aunque se gaste mucho."""
        libro = copy.deepcopy(LIBRO)
        libro["tests"][0]["historial_diario"][0]["gasto_usd"] = 900.0
        d = N.calcular(libro, AHORA)
        self.assertFalse(any("freno" in x["titulo"].lower() for x in d["atencion"]))
        self.assertFalse(any(k.startswith("freno") for k in d["referencias"]))

    def test_upsells_suben_lo_que_deja_cada_venta_sin_contar_como_compradores(self) -> None:
        """Dueño, 13-nov: con backend, lo que deja cada venta (AOV neto) crece; los upsells suman al neto pero no son compradores nuevos."""
        libro = copy.deepcopy(LIBRO)
        t = next(x for x in libro["tests"] if x.get("ventas"))
        base = N.calcular(copy.deepcopy(libro), AHORA)
        o0 = _ofertas(base)[t.get("oferta") or t["nombre"]]
        v0 = t["ventas"][0]
        t["ventas"].append({**v0, "orden": "U1", "tipo": "upsell"})
        o1 = _ofertas(N.calcular(libro, AHORA))[t.get("oferta") or t["nombre"]]
        self.assertEqual(o1["ventas_n"], o0["ventas_n"], "el upsell no es un comprador nuevo")
        self.assertGreater(o1["equilibrio"], o0["equilibrio"], "lo que deja cada venta sube con el backend")

    def test_corte_con_niveles_usa_el_ticket_del_completo(self) -> None:
        """Dueño, 13-nov: con niveles (13, 19 y 27 USD) el corte se calcula con el completo (27 → 40,50 sin ventas)."""
        ficha = {"tiendas": [{"rol": "principal", "precio": {"usd": 13}}, {"rol": "nivel", "precio": {"usd": 19}}, {"rol": "nivel", "precio": {"usd": 27}}]}
        self.assertEqual(N.ticket_corte(ficha), 27)
        self.assertEqual(N.ticket_corte({"tiendas": [{"rol": "principal", "precio": {"usd": 17}}]}), 17)
        self.assertIsNone(N.ticket_corte({"tiendas": [{"rol": "principal"}]}))

    def test_sin_datos_de_compradores_y_solo_https(self) -> None:
        texto = json.dumps(self.d, ensure_ascii=False)
        self.assertNotIn("persona@ejemplo.com", texto)
        self.assertNotIn("Persona Real", texto)
        v = self.o["Kit Uno"]["ventas"][0]
        self.assertEqual(set(v), {"orden", "tienda", "nivel", "fecha", "moneda", "bruto", "neto", "tipo", "bruto_usd", "neto_usd"})
        f = self.o["Kit Uno"]["ficha"]
        self.assertEqual(f["tiendas"][0]["url"], "https://kit-uno.impultienda.ar/")
        self.assertIsNone(f["tiendas"][1]["url"], "javascript: no se vuelve enlace")
        self.assertIsNone(f["landing_original"], "http sin s no se vuelve enlace")

    def test_historial_diario(self) -> None:
        dia = self.o["Kit Uno"]["diario"][0]
        self.assertEqual(dia, {"fecha": "2026-11-12", "gasto": 30.0, "ventas": 3, "bruto": 38.0, "neto": 35.0, "resultado": 5.0, "compras_meta": 5})
        self.assertEqual(self.o["Mapa Dos"]["diario"][0]["gasto"], None, "sin historial de Meta: sin dato, nunca 0")

    def test_accion_sugerida(self) -> None:
        a = N.accion_sugerida
        self.assertEqual(a(45.74, 6, 7.62, 13.22, "real", "activa")["clave"], "escalar", "≥ 3 ventas y CPA bajo el equilibrio")
        self.assertEqual(a(30.0, 2, 15.0, 20.0, "real", "activa")["clave"], "mirar", "CPA bajo el equilibrio pero menos de 3 ventas")
        self.assertIn("Faltan 1 venta", a(30.0, 2, 15.0, 20.0, "real", "activa")["porque"])
        self.assertEqual(a(58.42, 2, 29.21, 15.74, "real", "activa")["clave"], "mirar", "CPA sobre el equilibrio: la regla dice mirar un día más")
        self.assertEqual(a(60.0, 4, 15.0, 13.0, "real", "activa")["clave"], "mirar", "4 ventas pero CPA sobre el equilibrio: no se escala")
        self.assertEqual(a(25.5, 0, None, 15.6, "estimado", "activa", None, 17.0)["clave"], "cortar", "1,5 × 17 sin ventas")
        self.assertEqual(a(25.4, 0, None, 15.6, "estimado", "activa", None, 17.0)["clave"], "mirar")
        self.assertEqual(a(80.0, 1, 80.0, 15.6, "real", "activa", None, 17.0, True)["clave"], "cortar", "día 1 con una venta y CPA de 4,7 tickets")
        self.assertEqual(a(80.0, 1, 80.0, 15.6, "real", "activa", None, 17.0, False)["clave"], "mirar", "pasado el día 1 con ventas ya no corre el corte por tickets")
        self.assertEqual(a(99.0, 0, None, 12.0, "estimado", "activa")["clave"], "mirar", "sin precio del front no se corta")
        self.assertIn("Falta el precio en USD de las tiendas", a(99.0, 0, None, 12.0, "estimado", "activa")["porque"])
        sp = a(0.0, 0, None, 11.9, "estimado", "programada", "2026-11-13T00:00:00-03:00", 12.9)
        self.assertEqual(sp["clave"], "sin_pauta")
        self.assertIn("13-11 a las 00:00", sp["porque"])
        self.assertIn("US$ 19,35", sp["porque"])
        self.assertIn("firmada", sp["regla"])
        self.assertIn("sin firmar", a(45.74, 6, 7.62, 13.22, "real", "activa", None, 17.0)["regla"])
        museo = a(65.34, 2, 32.67, 15.6, "real", "activa", None, 17.0, True)
        self.assertEqual(museo["clave"], "cortar", "día 1: 2 ventas con CPA 32,67 ≥ 1,5 × 17")
        self.assertIn("Día 1", museo["porque"])
        self.assertEqual(a(65.34, 2, 32.67, 15.6, "real", "activa", None, 17.0, False)["clave"], "mirar", "pasado el día 1 con ventas: lo decide la revisión")
        self.assertEqual(a(65.34, 3, 21.78, 15.6, "real", "activa", None, 17.0, True)["clave"], "mirar", "3 ventas: CPA 21,78 < 25,50")

    def test_fase_test_y_post_lanzamiento(self) -> None:
        for o in self.d["ofertas"]:
            self.assertIn(o["fase"], ("test", "post-lanzamiento"))
        self.assertEqual(self.o["Camino Tres"]["fase"], "test", "sin ventas sigue en test aunque haya pasado el día 1")
        libro = copy.deepcopy(LIBRO)
        t = libro["tests"][0]
        t["inicio"] = AHORA.isoformat()
        o = _ofertas(N.calcular(libro, AHORA))["Kit Uno"]
        self.assertEqual(o["fase"], "test")
        self.assertIsNotNone(o["corte_usd"])
        self.assertEqual(self.o["Camino Tres"]["accion_sugerida"]["clave"], "cortar")
        self.assertEqual(self.o["Kit Uno"]["accion_sugerida"]["clave"], "mirar")
        self.assertIn("US$ 12,00", self.o["Kit Uno"]["accion_sugerida"]["porque"])

    def test_que_esta_vendiendo_y_proximo_cambio(self) -> None:
        libro = copy.deepcopy(LIBRO)
        libro["tests"][0]["ficha"]["campanas"][0]["anuncios"] = [
            {"nombre": "A", "gasto_usd": 20, "compras_meta": 1}, {"nombre": "B", "gasto_usd": 5, "compras_meta": 3},
            {"nombre": "C", "gasto_usd": 9, "compras_meta": 1}, {"nombre": "D", "gasto_usd": 30, "compras_meta": 0}, {"nombre": "E", "gasto_usd": 0, "compras_meta": 0}]
        libro["tests"][0]["programado"] = [
            {"cuando": "2026-11-14T00:00:00-06:00", "que": "Sube a 80"}, {"cuando": "2026-11-13T00:00:00-06:00", "que": "Sube a 65 y entra R3"},
            {"cuando": "2026-11-12T00:00:00-06:00", "que": "ya pasó"}, {"que": "sin fecha"}]
        k = _ofertas(N.calcular(libro, AHORA))["Kit Uno"]
        self.assertEqual([x["nombre"] for x in k["top_anuncios"]], ["B", "A", "C"], "más compras primero; a igualdad, más gasto")
        self.assertEqual([x["que"] for x in k["programado"]], ["Sube a 65 y entra R3", "Sube a 80"], "solo lo que no pasó, del más cercano al más lejano")
        self.assertEqual(k["programado"][0]["en_horas"], 6.0)
        self.assertEqual(self.o["Mapa Dos"]["top_anuncios"], [])
        self.assertEqual(self.o["Mapa Dos"]["programado"], [])
        # texto corto para la lista: día contado en la zona del cambio (AHORA = 12-nov 18:00 en México → 13-nov 00:00 es «mañana»)
        self.assertEqual(k["programado"][0]["corto"], "mañana 00:00: Sube a 65 y entra R3")
        self.assertTrue(k["programado"][1]["corto"].startswith("14/11 00:00: "))
        largo = N.texto_programado(N.parsear_fecha("2026-11-13T00:00:00-06:00"), "x" * 120, AHORA)
        self.assertLessEqual(len(largo), 72)
        self.assertTrue(largo.endswith("…"))

    def test_campana_pausada_no_recibe_mirar_y_frase_corta(self) -> None:
        libro = copy.deepcopy(LIBRO)
        libro["tests"][2]["estado"] = "pausado"
        d = N.calcular(libro, AHORA)
        m = _ofertas(d)["Mapa Dos"]
        self.assertEqual(m["accion_sugerida"]["clave"], "pausada", "pausada: ni «mirar un día más» ni «escalar»")
        self.assertEqual(m["accion_sugerida"]["texto"], "Pausada")
        self.assertIn("Antes de pausarla la regla decía", m["accion_sugerida"]["porque"])
        self.assertTrue(m["frase"].startswith("Campaña pausada con US$ 50,00 gastados"))
        for o in d["ofertas"]:
            self.assertLessEqual(len(o["frase"]), 80, o["nombre"])
            self.assertTrue(o["frase"], o["nombre"])
        self.assertEqual(self.o["Kit Uno"]["frase"], "Cada venta cuesta US$ 12,00 y deja US$ 11,67")

    def test_anuncios_roas_por_anuncio_y_veredicto(self) -> None:
        libro = copy.deepcopy(LIBRO)
        libro["tests"][0]["anuncios"] = {"leido": "2026-11-12T23:25-03:00", "lista": [
            {"id": "1", "nombre": "Gana", "conjunto": "C1", "estado": "ACTIVE", "gasto_usd": 20, "impresiones": 1000, "clics_enlace": 40, "ctr_pct": 4.0,
             "inicios_pago_meta": 10, "compras_meta": 3, "valor_compras_meta_usd": 45, "video_p25": 300, "video_p100": 100},
            {"id": "2", "nombre": "Promete", "conjunto": "C2", "estado": "ACTIVE", "gasto_usd": 5, "impresiones": 100, "clics_enlace": 5, "inicios_pago_meta": 1, "compras_meta": 1, "valor_compras_meta_usd": 15},
            {"id": "3", "nombre": "Flojo", "conjunto": "C1", "estado": "ACTIVE", "gasto_usd": 30, "impresiones": 900, "clics_enlace": 9, "inicios_pago_meta": 0, "compras_meta": 0},
            {"id": "4", "nombre": "Chico", "conjunto": "C1", "estado": "ADSET_PAUSED", "gasto_usd": 0, "impresiones": 0, "clics_enlace": 0, "compras_meta": 0},
            {"id": "5", "nombre": "Mira", "conjunto": "C1", "estado": "ACTIVE", "gasto_usd": 12, "impresiones": 400, "clics_enlace": 8, "inicios_pago_meta": 2, "compras_meta": 1, "valor_compras_meta_usd": 15},
        ]}
        libro["tests"][0]["ficha"]["tiendas"][0]["precio"]["usd"] = 15   # ticket del front: corte por anuncio a 22,50
        A = _ofertas(N.calcular(libro, AHORA))["Kit Uno"]["anuncios"]
        por = {a["nombre"]: a for a in A["lista"]}
        self.assertEqual([a["nombre"] for a in A["lista"]], ["Flojo", "Gana", "Mira", "Promete", "Chico"], "ordenados por gasto")
        neto_venta = 35 / 3
        g = por["Gana"]
        self.assertEqual(g["cpa"], round(20 / 3, 2))
        self.assertEqual(g["roas_meta"], 2.25)
        self.assertEqual(g["roas_neto_estimado"], round(3 * neto_venta / 20, 2))
        self.assertEqual(g["ctr_pct"], 4.0)
        self.assertEqual(g["clic_pago_pct"], 25.0)
        self.assertEqual(g["retencion_pct"], 10.0)
        self.assertEqual(g["retencion_25_pct"], 30.0)
        self.assertEqual(g["veredicto"]["clave"], "ganador")
        self.assertEqual(por["Promete"]["veredicto"]["clave"], "promete")
        self.assertEqual(por["Promete"]["ctr_pct"], 5.0, "sin CTR de Meta: clics ÷ impresiones")
        self.assertEqual(por["Flojo"]["veredicto"]["clave"], "flojo", "30 ≥ 1,5 × 15 sin compras")
        self.assertIsNone(por["Flojo"]["cpa"])
        self.assertEqual(por["Flojo"]["roas_meta"], 0.0)
        self.assertEqual(por["Chico"]["veredicto"]["clave"], "sin_datos")
        self.assertIsNone(por["Chico"]["roas_neto_estimado"])
        self.assertEqual(por["Mira"]["veredicto"]["clave"], "mirar", "1 compra pero ROAS neto estimado < 1")
        self.assertEqual(A["conjuntos"], ["C1", "C2"])
        self.assertEqual(A["resumen"], "1 ganador · 1 promete · 1 flojo · 1 sin datos · el que más vende: Gana (3 compras)")
        # sin lectura por anuncio: usa los anuncios de la ficha
        sin = _ofertas(N.calcular(copy.deepcopy(LIBRO), AHORA))["Mapa Dos"]["anuncios"]
        self.assertEqual(sin["lista"], [])
        self.assertIn("todavía ningún anuncio vendió", sin["resumen"])

    def test_libro_vacio_o_raro_no_rompe(self) -> None:
        for libro in (None, {}, {"tests": [None, {}, {"nombre": "X", "ventas": [{"moneda": "EUR", "bruto": 1, "neto": 1}]}]}):
            d = N.calcular(libro, AHORA)
            self.assertIn("cartera", d)
        d = N.calcular({"tests": [{"nombre": "X", "ventas": [{"orden": "1", "moneda": "EUR", "bruto": 1, "neto": 1}]}]}, AHORA)
        self.assertTrue(any("EUR" in a for a in d["avisos"]), "moneda sin tipo de cambio: se avisa, no se inventa")


class PruebaEtapaYBackend(unittest.TestCase):
    """Pedido del dueño (13-nov): ver de un vistazo la etapa de cada oferta y si tiene backend ofensivo."""

    def calc(self, cambiar=None, ahora=AHORA):
        L = copy.deepcopy(LIBRO)
        if cambiar:
            cambiar({t["nombre"]: t for t in L["tests"]})
        return _ofertas(N.calcular(L, ahora))

    def test_etapas_del_libro_de_prueba(self) -> None:
        o = self.calc()
        self.assertEqual(o["Kit Uno"]["etapa"]["clave"], "test", "día 1 del mercado")
        self.assertEqual(o["Kit Uno"]["etapa"]["corto"], "Test · día 1")
        self.assertEqual(o["Mapa Dos"]["etapa"]["clave"], "renovando", "ronda R2 de hace menos de 1 día (R9: una ronda por día)")
        self.assertEqual(o["Mapa Dos"]["etapa"]["corto"], "Renovando · R2")
        self.assertIn("la próxima ronda sale el 13/11", o["Mapa Dos"]["etapa"]["detalle"])
        o2 = self.calc(ahora=AHORA + _dt.timedelta(days=1))
        self.assertEqual(o2["Mapa Dos"]["etapa"]["clave"], "aprobada", "sin ronda nueva al día siguiente: «Para renovar»")
        self.assertEqual(o["Camino Tres"]["etapa"]["clave"], "apagar", "gastó 1,5 tickets del front sin ventas")
        self.assertEqual(o["Mapa Dos"]["renovaciones"][0]["estado"], "activa")
        self.assertNotIn("_ini", o["Mapa Dos"]["renovaciones"][0])

    def test_aprobada_renovacion_programada_programada_y_apagada(self) -> None:
        o = self.calc(lambda t: t["Mapa Dos"].pop("renovaciones"))
        self.assertEqual(o["Mapa Dos"]["etapa"]["clave"], "aprobada")
        self.assertIn("todavía no tiene renovaciones", o["Mapa Dos"]["etapa"]["detalle"])
        o = self.calc(lambda t: t["Mapa Dos"]["renovaciones"].append({"ronda": "R3", "inicio": "2026-11-14T00:00:00-06:00", "anuncios": 8}))
        self.assertEqual(o["Mapa Dos"]["etapa"]["clave"], "renovacion_programada", "una ronda futura manda sobre la que corre")
        self.assertEqual(o["Mapa Dos"]["etapa"]["corto"], "Renov. prog. · R3")
        o = self.calc(ahora=AHORA + __import__("datetime").timedelta(days=5))
        self.assertEqual(o["Mapa Dos"]["etapa"]["clave"], "aprobada", "a los 3 días la ronda ya se leyó: toca renovar")
        self.assertIn("hace 5 días", o["Mapa Dos"]["etapa"]["detalle"])

        def programar(t):
            t["Kit Uno"]["estado"] = "programado"
            t["Kit Uno"]["inicio"] = "2026-11-14T00:00:00-06:00"
            t["Kit Uno · tanda 2"]["inicio"] = "2026-11-14T00:00:00-06:00"
        o = self.calc(programar)
        self.assertEqual(o["Kit Uno"]["etapa"]["clave"], "programada")
        self.assertEqual(o["Kit Uno"]["etapa"]["corto"], "Programada · 14/11 00:00")

        def ya_arranco(t):
            t["Kit Uno"]["estado"] = "programado"
        self.assertEqual(self.calc(ya_arranco)["Kit Uno"]["etapa"]["clave"], "test", "programada con el inicio pasado: está corriendo")

        def apagar(t):
            t["Camino Tres"]["estado"] = "pausado"
            t["Camino Tres"]["apagado"] = {"cuando": "2026-11-12T23:20-03:00", "regla": "día 1: CPA ≥ 1,5 tickets del front"}
        e = self.calc(apagar)["Camino Tres"]["etapa"]
        self.assertEqual(e["clave"], "apagada")
        self.assertIn("Se apagó el 12/11 a las 23:20 por la regla de corte", e["detalle"])

    def test_backend_y_falta_backend(self) -> None:
        o = self.calc()
        b = o["Mapa Dos"]["backend"]
        self.assertTrue(b["activo"])
        self.assertEqual(b["texto"], "Backend activo · 2 upsells")
        self.assertEqual([u["precio_usd"] for u in b["upsells"]], [21, 13])
        self.assertFalse(b["falta"])
        self.assertEqual(o["Kit Uno"]["backend"]["estado"], "no")
        self.assertFalse(o["Kit Uno"]["backend"]["falta"], "en test todavía no hace falta")
        d = N.calcular(copy.deepcopy({**LIBRO, "tests": [dict(t, backend={"estado": "pausado"}) if t["nombre"] == "Mapa Dos" else t for t in LIBRO["tests"]]}), AHORA)
        m = _ofertas(d)["Mapa Dos"]["backend"]
        self.assertTrue(m["falta"], "pasó el test con el backend en pausa: falta")
        self.assertTrue(any("Mapa Dos: pasó el test y no tiene backend" in x["titulo"] for x in d["atencion"]))
        self.assertEqual(d["cartera"]["falta_backend"], 1)
        self.assertEqual(N.calcular(copy.deepcopy(LIBRO), AHORA)["cartera"]["etapas"], {"apagar": 1, "aprobada": 0, "armada": 0, "test": 1, "renovando": 1,
                                                                                         "renovacion_programada": 0, "programada": 0, "apagada": 0})

    def test_periodo_conserva_etapa_y_backend(self) -> None:
        d = N.calcular_periodo(copy.deepcopy(LIBRO), AHORA, __import__("datetime").date(2026, 11, 12), __import__("datetime").date(2026, 11, 12))
        m = _ofertas(d)["Mapa Dos"]
        self.assertEqual(m["etapa"]["clave"], "renovando")
        self.assertTrue(m["backend"]["activo"])
        self.assertEqual(d["cartera"]["con_backend"], 1)


class PruebaCoincideConLibroDeTests(unittest.TestCase):
    """Los números del tablero son los de ``libro_de_tests.py`` (la tabla que imprime el agente) sobre el mismo libro."""

    def _tabla(self, ruta: Path) -> str:
        spec = importlib.util.spec_from_file_location("libro_de_tests_prueba", SCRIPT_LIBRO)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.RAIZ, mod.LIBRO = ruta.parent, ruta
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            mod.main()
        return salida.getvalue()

    def test_misma_tabla(self) -> None:
        import tempfile
        libro = copy.deepcopy(LIBRO)
        for t in libro["tests"]:      # el script no conoce «oferta»: una fila por test
            t.pop("oferta", None)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "libro.json"
            ruta.write_text(json.dumps(libro, ensure_ascii=False))
            tabla = self._tabla(ruta)
        d = N.calcular(libro, AHORA)
        filas = {m.group(1).strip(): [c.strip() for c in m.group(2).split("|")] for m in re.finditer(r"^\| ([^|*]+?) \| (.+) \|$", tabla.split("## Embudo")[0], re.M)}
        f = lambda x: "—" if x is None else f"{x:,.2f}"   # noqa: E731 - mismo formato que el script
        for o in d["ofertas"]:
            fila = filas[o["nombre"]]
            # Mercado | Estado | Producción | Meta | Ventas | Bruto | Neto | Neto − Meta | Neto − todo | CPA real | CPA de equilibrio
            self.assertEqual(fila[2], f(o["produccion"]["total"]), o["nombre"])
            self.assertEqual(fila[3], f(o["gasto_meta"]), o["nombre"])
            self.assertEqual(fila[4], str(o["ventas_n"]), o["nombre"])
            self.assertEqual(fila[5], f(o["bruto"]), o["nombre"])
            self.assertEqual(fila[6], f(o["neto"]), o["nombre"])
            self.assertEqual(fila[7], f(o["neto_menos_meta"]), o["nombre"])
            self.assertEqual(fila[8], f(o["neto_menos_todo"]), o["nombre"])
            self.assertEqual(fila[9], f(o["cpa"]), o["nombre"])
            if o["equilibrio_fuente"] == "real":
                self.assertEqual(fila[10], f(o["equilibrio"]), o["nombre"])
        total = re.search(r"^\| \*\*Total\*\* \|.*$", tabla, re.M).group(0).split("|")
        c = d["cartera"]
        self.assertEqual(total[4].strip(), f(c["produccion"]))
        self.assertEqual(total[5].strip(), f(c["gasto_meta"]))
        self.assertEqual(total[7].strip(), f(c["bruto"]))
        self.assertEqual(total[8].strip(), f(c["neto"]))
        self.assertEqual(total[9].strip(), f(c["neto_menos_meta"]))
        self.assertEqual(total[10].strip(), f(c["neto_menos_todo"]))


class PruebaPeriodo(unittest.TestCase):
    """Filtro de días: zona de la cuenta, un día, un rango, producción dentro/fuera, fijos por día, embudo incompleto, veredicto desde el inicio."""

    def libro(self) -> dict:
        L = copy.deepcopy(LIBRO)
        L["zona_horaria_cuenta"] = "America/Argentina/Buenos_Aires"
        k = L["tests"][0]
        k["historial_diario"] = [{"fecha": "2026-11-12", "gasto_usd": 30.0, "compras_meta": 5, "valor_compras_meta_usd": 45.0},
                                 {"fecha": "2026-11-13", "gasto_usd": 10.0, "compras_meta": 1, "valor_compras_meta_usd": 15.0}]
        k["ventas"][2]["fecha"] = "2026-11-13"   # A3 (básico) cae el 13
        k["tienda_embudo_diario"] = [{"fecha": "2026-11-12", "landing": 100, "checkout": 10, "compras": 2, "parcial": True}]
        k["anuncios"] = {"lista": [{"id": "1", "nombre": "A1", "conjunto": "C", "estado": "ACTIVE"}, {"id": "2", "nombre": "A2", "conjunto": "C", "estado": "ACTIVE"}],
                         "por_dia": [{"fecha": "2026-11-12", "id": "1", "gasto_usd": 20, "compras_meta": 2}, {"fecha": "2026-11-13", "id": "1", "gasto_usd": 5, "compras_meta": 1},
                                     {"fecha": "2026-11-13", "id": "2", "gasto_usd": 5, "compras_meta": 0}]}
        L["tests"][1]["historial_diario"] = [{"fecha": "2026-11-12", "gasto_usd": 6.0}]
        return L

    AHORA_13 = _dt.datetime(2026, 11, 14, 2, 0, tzinfo=_dt.timezone.utc)   # 13-nov 23:00 en Argentina: «hoy» es el 13 aunque en UTC ya sea el 14

    def test_hoy_y_ayer_en_la_zona_de_la_cuenta(self) -> None:
        d = N.calcular_periodo(self.libro(), self.AHORA_13, None, None)
        self.assertEqual(d["periodo"]["hoy"], "2026-11-13")
        self.assertEqual(d["periodo"]["zona"], "America/Argentina/Buenos_Aires")
        self.assertTrue(d["periodo"]["todo"])
        self.assertEqual(N.dia_de("2026-11-13T01:30:00Z", N.zona_de(self.libro())).isoformat(), "2026-11-12", "01:30 UTC es el 12 a las 22:30 en Argentina")

    def test_un_dia_recalcula_meta_ventas_y_produccion_fuera(self) -> None:
        L = self.libro()
        d = N.calcular_periodo(L, self.AHORA_13, _dt.date(2026, 11, 13), _dt.date(2026, 11, 13))
        k = _ofertas(d)["Kit Uno"]
        self.assertEqual(k["gasto_meta"], 10.0, "solo el 13 (la tanda 2 no tiene historial ese día)")
        self.assertEqual(k["ventas_n"], 1)
        self.assertEqual(k["neto"], 7.0)
        self.assertEqual(k["roas_meta"], 1.5)
        self.assertEqual(k["produccion"]["total"], 0.0, "la pauta arrancó el 12: la producción no entra el 13")
        self.assertEqual(k["dias_pauta"], 1)
        self.assertAlmostEqual(k["fijos"], 1 / 3, places=3, msg="fijos de un día")
        self.assertEqual(k["ganancia_neta"], round(7 - 10 - 1 / 3, 2))
        a = {x["nombre"]: x for x in k["anuncios"]["lista"]}
        self.assertEqual((a["A1"]["gasto_usd"], a["A1"]["compras_meta"]), (5.0, 1))
        self.assertEqual(a["A2"]["gasto_usd"], 5.0)
        self.assertTrue(k["embudo"]["incompleto"], "falta la lectura de Impultienda del 13")
        self.assertIsNone(k["embudo"]["visitas"])
        total = _ofertas(N.calcular_periodo(L, self.AHORA_13, None, None))["Kit Uno"]
        self.assertEqual(k["accion_sugerida"], total["accion_sugerida"], "el veredicto se calcula siempre desde el inicio")
        self.assertEqual(k["frase"], total["frase"])
        self.assertFalse(d["periodo"]["todo"])
        self.assertEqual((d["periodo"]["desde"], d["periodo"]["hasta"], d["periodo"]["dias"]), ("2026-11-13", "2026-11-13", 1))

    def test_rango_con_produccion_dentro_y_embudo_completo(self) -> None:
        L = self.libro()
        L["tests"][0]["tienda_embudo_diario"].append({"fecha": "2026-11-13", "landing": 50, "checkout": 5, "compras": 1})
        d = N.calcular_periodo(L, self.AHORA_13, _dt.date(2026, 11, 12), _dt.date(2026, 11, 13))
        k = _ofertas(d)["Kit Uno"]
        self.assertEqual(k["gasto_meta"], 46.0, "30 + 10 del Kit + 6 de la tanda 2")
        self.assertEqual(k["ventas_n"], 3)
        self.assertEqual(k["produccion"]["total"], 11.0, "el inicio (12) cae dentro")
        self.assertEqual(k["dias_pauta"], 2)
        self.assertEqual((k["embudo"]["visitas"], k["embudo"]["checkout"], k["embudo"]["compras"]), (150, 15, 3))
        self.assertTrue(k["embudo"]["parcial"])
        self.assertEqual(k["roas_real"], round(35 / (46 + 11 + 2 / 3), 2))
        self.assertEqual(_ofertas(d)["Camino Tres"]["con_datos_periodo"], False)

    def test_periodo_sin_datos(self) -> None:
        d = N.calcular_periodo(self.libro(), self.AHORA_13, _dt.date(2026, 10, 1), _dt.date(2026, 10, 31))
        self.assertFalse(d["periodo"]["con_datos"])
        for o in d["ofertas"]:
            self.assertFalse(o["con_datos_periodo"], o["nombre"])
            self.assertEqual(o["produccion"]["total"], 0.0)
        self.assertEqual(d["cartera"]["ventas"], 0)

    def test_desde_el_inicio_no_cambia(self) -> None:
        L = self.libro()
        self.assertEqual(N.calcular_periodo(L, self.AHORA_13, None, None)["cartera"], N.calcular(L, self.AHORA_13)["cartera"])


class PruebaApiNegocio(PruebaBase):
    def test_sin_libro_es_vacio_con_aviso(self) -> None:
        j = self.cliente().get("/api/negocio").json()
        self.assertIs(j["ok"], True)
        self.assertIs(j["vacio"], True)
        self.assertEqual(j["datos"]["ofertas"], [])
        self.assertTrue(any("libro de tests" in a for a in j["avisos"]))

    def test_con_libro_devuelve_cartera_y_documentos_existentes(self) -> None:
        libro = copy.deepcopy(LIBRO)
        libro["tests"][0]["ficha"]["expediente"] = "ofertas/_funnels/Kit Uno"
        libro["tests"][0]["ficha"]["revisiones"] = ["ofertas/_funnels/REVISION-2026-11-12.md"]
        self.escribir("ofertas/_funnels/libro-de-tests.json", json.dumps(libro, ensure_ascii=False))
        self.escribir("ofertas/_funnels/Kit Uno/FUNNEL.md", "# Kit Uno\n")
        r = self.cliente(ahora=reloj_fijo(AHORA)).get("/api/negocio")
        self.assertEqual(r.estado, 200)
        j = r.json()
        self.assertIs(j["vacio"], False)
        self.assertIn("ofertas/_funnels/libro-de-tests.json", j["fuente"])
        o = _ofertas(j["datos"])["Kit Uno"]
        self.assertEqual(o["documentos"], [{"titulo": "Expediente del funnel", "ruta": "ofertas/_funnels/Kit Uno/FUNNEL.md"}], "la revisión no existe: no se lista")
        self.assertNotIn("persona@ejemplo.com", r.cuerpo.decode("utf-8"))

    def test_libro_corrupto_no_rompe(self) -> None:
        self.escribir("ofertas/_funnels/libro-de-tests.json", "{ roto")
        r = self.cliente().get("/api/negocio")
        self.assertEqual(r.estado, 200)
        self.assertIs(r.json()["vacio"], True)
        self.assertTrue(r.json()["avisos"])

    def test_periodo_por_la_direccion(self) -> None:
        self.escribir("ofertas/_funnels/libro-de-tests.json", json.dumps(LIBRO))
        c = self.cliente(ahora=reloj_fijo(AHORA))
        j = c.get("/api/negocio", consulta="desde=2026-11-12&hasta=2026-11-12").json()
        self.assertEqual((j["datos"]["periodo"]["desde"], j["datos"]["periodo"]["todo"]), ("2026-11-12", False))
        self.assertTrue(c.get("/api/negocio").json()["datos"]["periodo"]["todo"])
        for mala in ("desde=12-11-2026&hasta=2026-11-12", "desde=2026-13-40&hasta=2026-11-12", "desde=<script>"):
            self.assertEqual(c.get("/api/negocio", consulta=mala).estado, 400, mala)

    def test_documento_solo_expedientes_y_bitacora(self) -> None:
        self.escribir("ofertas/_funnels/Kit Uno/FUNNEL.md", "# Kit Uno\n")
        self.escribir("ofertas/_borrador-mx-kit/estado.md", "bitácora\n")
        self.escribir("ofertas/_borrador-mx-kit/secreto.json", "{}")
        c = self.cliente()
        q = lambda r: "ruta=" + urllib.parse.quote(r)   # noqa: E731
        r = c.get("/api/negocio/documento", consulta=q("ofertas/_funnels/Kit Uno/FUNNEL.md"))
        self.assertEqual(r.estado, 200)
        self.assertEqual(r.datos["contenido"], "# Kit Uno\n")
        self.assertEqual(c.get("/api/negocio/documento", consulta=q("ofertas/_borrador-mx-kit/estado.md")).estado, 200)
        for mala in ("ofertas/_borrador-mx-kit/secreto.json", "empresa/limites.yaml", "ofertas/_funnels/../../empresa/limites.yaml", "", "ofertas/OF-202611-77/estado.json"):
            self.assertEqual(c.get("/api/negocio/documento", consulta=q(mala)).estado, 403, mala)


if __name__ == "__main__":
    unittest.main()
