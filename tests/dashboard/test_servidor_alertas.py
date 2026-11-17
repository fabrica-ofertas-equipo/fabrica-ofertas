"""``GET /api/alertas`` y ``GET /api/informe`` (Resumen: «¿Me puedo ausentar?», Avisos: alertas e informe): solo lectura, saneadas y acotadas.

Raíz temporal con los fixtures del servidor (nunca ``empresa/`` ni ``ofertas/`` reales); sockets bloqueados.
"""
from __future__ import annotations

import json
import re
import unittest

from tests.dashboard.test_servidor_apoyo import PruebaBase

DINERO = re.compile(r"\d[\d.,]*\s?(?:USD|EUR|PLN|€|\$|zł)")
FILA_AJENA = {"schema_version": "1.0.0", "id": "F1-A02:OF-202611-01", "ts": "2026-11-09T10:00:00Z", "severidad": "naranja", "regla_id": "F1-A02", "origen": "F1",
              "oferta_id": "OF-202611-01", "macro_nicho": None, "nivel": None, "valor": "1.4", "umbral": "1.0", "accion_sugerida": "Pausar la oferta", "estado": "abierta"}


class PruebaApiAlertas(PruebaBase):
    def alertas(self) -> dict:
        r = self.cliente().get("/api/alertas")
        self.assertEqual(r.estado, 200)
        return r.json()

    def test_sobre_y_forma(self) -> None:
        j = self.alertas()
        self.assertIs(j["ok"], True)
        self.assertIs(j["vacio"], False, "siempre se calcula: nunca es «vacío»")
        d = j["datos"]
        self.assertEqual(sorted(d), ["alertas", "archivo", "reglas", "resumen", "semaforo"])
        self.assertIn("empresa/datos/alertas.jsonl", j["fuente"])
        self.assertEqual(d["semaforo"]["nivel"] in ("rojo", "amarillo", "verde"), True)
        self.assertEqual(d["reglas"]["pendientes"][0]["regla_id"], "F2-A01")
        self.assertEqual(len(d["reglas"]["pendientes"]), 15)
        self.assertEqual(d["archivo"]["existe"], False)
        self.assertEqual(d["archivo"]["al_dia"], False)
        self.assertIn("--escribir", d["archivo"]["comando_escribir"])
        r = d["resumen"]
        self.assertEqual(r["abiertas"], len(d["alertas"]) - r["cerradas"])
        self.assertEqual(r["rojas"] + r["naranjas"] + r["amarillas"] + r["info"], r["abiertas"])
        for a in d["alertas"]:
            self.assertTrue(a["titulo"] and a["accion_sugerida"] and a["enlace"], a["id"])
            self.assertLessEqual(len(a["accion_sugerida"]), 300)

    def test_exige_token_y_es_solo_lectura(self) -> None:
        c = self.cliente()
        self.assertEqual(c.get("/api/alertas", token=False).estado, 403)
        self.assertEqual(c.get("/api/informe", token=False).estado, 403)
        for ruta in ("/api/alertas", "/api/informe"):
            r = c.post(ruta, {})
            self.assertIn(r.estado, (403, 404, 405), ruta)

    def test_no_escribe_nada_ni_crea_empresa_datos(self) -> None:
        antes = self.hash_arbol(self.raiz)
        c = self.cliente()
        for ruta in ("/api/alertas", "/api/informe", "/api/alertas", "/api/informe"):
            self.assertEqual(c.get(ruta).estado, 200)
        self.assertEqual(self.hash_arbol(self.raiz), antes)
        self.assertFalse((self.raiz / "empresa" / "datos").exists(), "el panel nunca crea alertas.jsonl: eso lo hace el productor con --escribir")

    def test_el_archivo_guardado_se_integra_y_dice_si_esta_al_dia(self) -> None:
        from scripts.alertas.producir import producir
        from dashboard.api_base import Ctx
        ctx = Ctx(self.raiz, ahora=lambda: self.panel().ctx.ahora())
        producir(ctx, escribir=True)
        d = self.alertas()["datos"]
        self.assertEqual((d["archivo"]["existe"], d["archivo"]["al_dia"]), (True, True))
        self.assertIsNotNone(d["archivo"]["actualizado_en"])
        self.assertEqual({a["fuente"] for a in d["alertas"]}, {"calculada"})
        self.escribir("empresa/PAUSA", json.dumps({"ts": "2026-11-09T11:00:00Z", "motivo": "x"}))
        d = self.alertas()["datos"]
        self.assertEqual(d["archivo"]["al_dia"], False, "apareció una PAUSA que el archivo guardado todavía no tiene")
        self.assertIn("F2-AUS-PAUSA:empresa", [a["id"] for a in d["alertas"]])

    def test_lo_ajeno_pasa_saneado_y_lo_invalido_se_descarta(self) -> None:
        hostil = {**FILA_AJENA, "id": "F1-A05:x", "accion_sugerida": "Mira https://malo.example/x <script>alert(1)</script> ‮gnp", "campo_raro": "no debe pasar", "valor": 1.5,
                  "umbral": {"monto": 5, "moneda": "USDXXXX"}}
        filas = [FILA_AJENA, hostil, {**FILA_AJENA, "id": "mala", "severidad": "inventada"}, {**FILA_AJENA, "id": "sin-estado", "estado": "rara"}, {"id": 5}, [1, 2], "texto"]
        self.escribir("empresa/datos/alertas.jsonl", "".join(json.dumps(f) + "\n" for f in filas) + "esto no es json\n")
        d = self.alertas()["datos"]
        ajenas = {a["id"]: a for a in d["alertas"] if a["fuente"] == "archivo"}
        self.assertEqual(sorted(ajenas), ["F1-A02:OF-202611-01", "F1-A05:x"])
        h = ajenas["F1-A05:x"]
        self.assertNotIn("campo_raro", h)
        self.assertNotIn("http", h["accion_sugerida"])
        self.assertNotIn("‮", h["accion_sugerida"])
        self.assertIsNone(h["valor"], "un float no pasa: el dinero y los ratios son enteros o cadenas")
        self.assertEqual(h["umbral"], {"monto": 5, "moneda": "USD"})
        self.assertEqual(ajenas["F1-A02:OF-202611-01"]["severidad"], "naranja")
        self.assertEqual(d["resumen"]["naranjas"], 2)
        vig = {c["id"]: c for c in d["semaforo"]["comprobaciones"]}["vigilancia"]
        self.assertEqual((vig["nivel"], vig["enlace"]), ("rojo", "#/avisos"), "una alerta grave de otra regla abierta pone en rojo la vigilancia")
        self.assertEqual(len(d["semaforo"]["comprobaciones"]), 10)

    def test_archivo_ilegible_o_enorme_no_rompe_y_avisa(self) -> None:
        self.escribir("empresa/datos/alertas.jsonl", b"\x00" * (3 * 1024 * 1024))
        r = self.cliente().get("/api/alertas")
        self.assertEqual(r.estado, 200)
        j = r.json()
        self.assertTrue(any("no se pudo leer entero" in a for a in j["avisos"]))
        self.assertIs(j["datos"]["archivo"]["ilegible"], True)
        self.assertGreater(j["datos"]["resumen"]["abiertas"], 0, "igual se muestran las calculadas ahora")

    def test_se_acota_la_cantidad_de_alertas(self) -> None:
        filas = [{**FILA_AJENA, "id": f"F1-A04:o{i}"} for i in range(1500)]
        self.escribir("empresa/datos/alertas.jsonl", "".join(json.dumps(f) + "\n" for f in filas))
        d = self.alertas()["datos"]
        self.assertLessEqual(len(d["alertas"]), 200)

    def test_el_texto_hostil_de_pulido_llega_como_dato_inerte_y_sin_enlaces(self) -> None:
        self.escribir("empresa/panel/pulido.jsonl", json.dumps({"id": "PUL-0001", "ts": "2026-11-01T00:00:00Z", "evento": "alta", "titulo": "<img src=x onerror=alert(1)> https://malo.example", "responsable": "dueno",
                                                                   "prioridad": "P0", "vence": "2026-11-01", "estado": "abierta"}) + "\n")
        d = self.alertas()["datos"]
        a = [x for x in d["alertas"] if x["id"] == "F2-AUS-VENCE:PUL-0001"][0]
        self.assertNotIn("malo.example", json.dumps(a))
        self.assertIn("<img", a["detalle"], "texto como dato: el cliente lo muestra con textContent")
        self.assertNotIn("onerror", a["accion_sugerida"])

    def test_informe_dos_versiones_y_el_celular_sin_dinero(self) -> None:
        j = self.cliente().get("/api/informe").json()
        self.assertIs(j["ok"], True)
        d = j["datos"]
        self.assertEqual(d["tipo"], "informe_diario")
        self.assertEqual([a["id"] for a in d["avisos"]], ["pagos", "importante", "cansancio", "mercado_nuevo", "no_aprobado"])
        self.assertEqual(len(d["ceros"]), 5)
        self.assertIn("asunto", d["versiones"]["correo"])
        self.assertIsNone(DINERO.search(d["versiones"]["celular"]["texto"]))
        self.assertLess(len(json.dumps(d)), 60000, "acotado")

    def test_informe_con_ventas_lleva_el_importe_en_el_correo_y_el_porcentaje_en_el_celular(self) -> None:
        self.escribir("empresa/limites.yaml", "moneda_limites: EUR\ngasto_diario_global: 30000\ncuentas_permitidas: []\nsello: null\n")
        self.escribir("ofertas/OF-202611-77/08-operacion/diario/2026-11-08/kpi_oferta_dia.json", json.dumps(
            {"filas": [{"kpi_id": "gasto_meta", "valor": 2760, "unidad": "EUR_minor"}, {"kpi_id": "compras_stripe", "valor": 1, "unidad": "compras"}]}))
        d = self.cliente().get("/api/informe").json()["datos"]
        self.assertEqual(d["dia_medido"], "2026-11-08", "el reloj de la prueba es 2026-11-09 12:00: el día medido es ayer")
        self.assertIn("27,60 EUR", d["versiones"]["correo"]["texto"])
        self.assertIn("gasto 9 % del tope diario", d["versiones"]["celular"]["texto"])
        self.assertNotIn("27,60", d["versiones"]["celular"]["texto"])


if __name__ == "__main__":
    unittest.main()
