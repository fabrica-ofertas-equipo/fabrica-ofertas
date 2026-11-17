"""Informe de las 08:30: plantilla fija, correo con importes y celular con porcentajes (cero dinero), 5 avisos, ceros explícitos, «lo que te toca a ti»."""
from __future__ import annotations

import contextlib
import io
import json
import re
import unittest

from scripts.informe import informe_diario as I
from tests.alertas.ayudas import AHORA, Base, ITEMS_BUENOS, LIMITES_COMPLETOS, LIMITES_VACIOS, PARAMETROS, estado_infra, item

DINERO = re.compile(r"\d[\d.,]*\s?(?:USD|EUR|PLN|€|\$|zł)|(?:USD|EUR|PLN)\s?\d")


def kpi(gasto: int = 2760, compras: int = 2, moneda: str = "EUR") -> dict:
    return {"filas": [{"kpi_id": "gasto_meta", "valor": gasto, "unidad": f"{moneda}_minor"}, {"kpi_id": "compras_stripe", "valor": compras, "unidad": "compras"}]}


class PruebaInforme(Base):
    def test_hoy_sin_datos_dice_todavia_no_hay_datos_y_nunca_un_cero_inventado(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        self.poner("empresa/limites.yaml", LIMITES_VACIOS)
        inf = I.componer(self.ctx())
        self.assertEqual((inf["tipo"], inf["fecha"], inf["dia_medido"], inf["hora_objetivo"]), ("informe_diario", "2026-11-07", "2026-11-06", "08:30"))
        self.assertIs(inf["ventas_gasto"]["hay_datos"], False)
        self.assertIn("Todavía no hay datos de ventas ni de gasto", inf["ventas_gasto"]["correo"][0])
        self.assertEqual(inf["ventas_gasto"]["celular"], "sin datos todavía")
        correo = inf["versiones"]["correo"]["texto"]
        self.assertNotIn("Ventas del", correo, "sin KPI no hay frase de ventas con número")
        self.assertEqual(inf["semaforo"]["nivel"], "rojo")

    def test_los_5_tipos_de_aviso_en_orden_y_cada_uno_dice_si_se_midio(self) -> None:
        inf = I.componer(self.ctx())
        self.assertEqual([a["id"] for a in inf["avisos"]], ["pagos", "importante", "cansancio", "mercado_nuevo", "no_aprobado"])
        est = {a["id"]: a["estado"] for a in inf["avisos"]}
        self.assertEqual((est["pagos"], est["cansancio"], est["mercado_nuevo"]), ("sin_medir", "sin_medir", "sin_medir"))
        self.assertIn(est["importante"], ("con_novedades", "sin_novedades"))
        self.assertEqual(est["no_aprobado"], "sin_novedades")
        for a in inf["avisos"]:
            self.assertIn(a["estado"], ("con_novedades", "sin_novedades", "sin_medir"))
            self.assertTrue(a["correo"] and a["celular"])
            if a["estado"] == "sin_medir":
                self.assertTrue(a["correo"][0].startswith("Todavía no se mide") or "no se puede decir" in a["correo"][0], a["id"])

    def test_pagos_con_chequeo_usa_los_items_de_cuenta_y_stripe(self) -> None:
        self.poner("empresa/infra/estado.json", estado_infra("AMARILLO", items=[item("M-02"), item("M-03", "AMARILLO"), item("S-01"), item("S-02", "ROJO"), item("S-07")]))
        a = {x["id"]: x for x in I.componer(self.ctx())["avisos"]}["pagos"]
        self.assertEqual(a["estado"], "con_novedades")
        self.assertEqual(len(a["correo"]), 2)
        self.poner("empresa/infra/estado.json", estado_infra("VERDE", items=ITEMS_BUENOS))
        self.assertEqual({x["id"]: x["estado"] for x in I.componer(self.ctx())["avisos"]}["pagos"], "sin_novedades")
        self.poner("empresa/infra/estado.json", estado_infra("VERDE", items=[item("M-02")]))
        self.assertEqual({x["id"]: x["estado"] for x in I.componer(self.ctx())["avisos"]}["pagos"], "sin_medir", "si el chequeo no incluye los ítems de pago no se dice que están en orden")

    def test_los_ceros_son_explicitos_y_solo_valen_cuando_se_midio(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        c = {x["id"]: x for x in I.componer(self.ctx())["ceros"]}
        self.assertEqual(list(c), ["pagos_sin_aviso", "trabajos_sin_latido", "graves_sin_aviso", "gasto_sobre_tope", "esperando_por_ti"])
        self.assertEqual((c["pagos_sin_aviso"]["estado"], c["pagos_sin_aviso"]["valor"]), ("sin_medir", None))
        self.assertEqual((c["trabajos_sin_latido"]["estado"], c["trabajos_sin_latido"]["valor"]), ("sin_medir", None))
        self.assertEqual((c["graves_sin_aviso"]["estado"], c["graves_sin_aviso"]["valor"]), ("no_cumple", 3), "hay 3 graves y ningún canal probado: ninguna salió del panel")
        self.assertEqual(c["gasto_sobre_tope"]["estado"], "sin_medir")
        self.assertEqual((c["esperando_por_ti"]["estado"], c["esperando_por_ti"]["valor"]), ("cumple", 0))

    def test_todo_en_orden_los_ceros_miden_y_cumplen(self) -> None:
        self.base_sana()
        self.oferta("OF-202611-91", fase="en_test")
        self.poner("ofertas/OF-202611-91/08-operacion/diario/2026-11-06/kpi_oferta_dia.json", kpi(gasto=20000, moneda="USD"))
        inf = I.componer(self.ctx())
        c = {x["id"]: x for x in inf["ceros"]}
        self.assertEqual((c["trabajos_sin_latido"]["estado"], c["trabajos_sin_latido"]["valor"]), ("cumple", 0))
        self.assertEqual((c["graves_sin_aviso"]["estado"], c["graves_sin_aviso"]["valor"]), ("cumple", 0))
        self.assertEqual((c["gasto_sobre_tope"]["estado"], c["gasto_sobre_tope"]["valor"]), ("cumple", 0))
        self.assertEqual(inf["semaforo"]["nivel"], "amarillo", "ya hay ofertas vendiendo y las reglas de gasto y ventas todavía no se calculan")
        self.poner("ofertas/OF-202611-91/08-operacion/diario/2026-11-06/kpi_oferta_dia.json", kpi(gasto=45000, moneda="USD"))
        self.assertEqual({x["id"]: x for x in I.componer(self.ctx())["ceros"]}["gasto_sobre_tope"]["estado"], "no_cumple")

    def test_las_alertas_ajenas_del_archivo_entran_en_lo_importante_y_en_los_ceros_saneadas(self) -> None:
        self.base_sana()
        ajena = {"schema_version": "1.0.0", "id": "F2-A08:OF-202611-91", "ts": "2026-11-07T08:00:00Z", "severidad": "roja", "regla_id": "F2-A08", "origen": "F2", "oferta_id": "OF-202611-91",
                 "macro_nicho": None, "nivel": None, "valor": "1.9", "umbral": "1.75", "accion_sugerida": "Pausar ya https://malo.example/x", "estado": "abierta"}
        cerrada = {**ajena, "id": "F2-A09:x", "regla_id": "F2-A09", "estado": "cerrada"}
        self.jsonl("empresa/datos/alertas.jsonl", [ajena, cerrada, {"id": "mala", "severidad": "inventada"}])
        inf = I.componer(self.ctx())
        imp = {a["id"]: a for a in inf["avisos"]}["importante"]
        self.assertEqual((imp["estado"], len(imp["correo"])), ("con_novedades", 1))
        self.assertIn("F2-A08 · OF-202611-91: Pausar ya [enlace]", imp["correo"][0])
        self.assertNotIn("malo.example", json.dumps(inf))
        self.assertEqual(imp["celular"], "1 alerta roja")
        self.assertEqual(inf["alertas"]["roja"], 1)
        self.assertEqual({c["id"]: c for c in inf["ceros"]}["graves_sin_aviso"]["valor"], None, "hay canal probado pero no hay registro de envíos")
        self.assertEqual(inf["semaforo"]["nivel"], "rojo", "una alerta grave de gasto abierta es rojo")
        self.assertNotIn("malo.example", inf["versiones"]["celular"]["texto"])

    def test_graves_con_canal_probado_no_se_afirma_sin_registro_de_envios(self) -> None:
        self.base_sana()
        self.poner("empresa/PAUSA", {"motivo": "x"})
        c = {x["id"]: x for x in I.componer(self.ctx())["ceros"]}["graves_sin_aviso"]
        self.assertEqual((c["estado"], c["valor"]), ("sin_medir", None))

    def test_correo_lleva_importes_y_celular_solo_porcentajes(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        self.poner("empresa/limites.yaml", LIMITES_COMPLETOS.replace("USD", "EUR"))
        self.oferta("OF-202611-91", fase="en_test")
        self.poner("ofertas/OF-202611-91/08-operacion/diario/2026-11-06/kpi_oferta_dia.json", kpi(gasto=2760, compras=2, moneda="EUR"))
        inf = I.componer(self.ctx())
        correo, celular = inf["versiones"]["correo"]["texto"], inf["versiones"]["celular"]["texto"]
        self.assertIn("Gasto en anuncios: 27,60 EUR.", correo)
        self.assertIn("2 compras", correo)
        self.assertIn("2 ventas · gasto 9 % del tope diario", celular, "27,60 de 300,00 = 9 %")
        self.assertIsNone(DINERO.search(celular), celular)
        self.assertNotIn("27,60", celular)
        self.assertNotIn("EUR", celular)

    def test_sin_tope_firmado_el_celular_no_inventa_el_porcentaje(self) -> None:
        self.oferta("OF-202611-91", fase="en_test")
        self.poner("ofertas/OF-202611-91/08-operacion/diario/2026-11-06/kpi_oferta_dia.json", kpi())
        celular = I.componer(self.ctx())["versiones"]["celular"]["texto"]
        self.assertIn("sin tope firmado", celular)
        self.assertNotIn(" %", celular.split("Ventas y gasto:")[1].split("\n")[0])

    def test_el_celular_nunca_deja_pasar_dinero(self) -> None:
        for crudo in ("Gasto 1.234,56 EUR hoy", "pagaste $ 300 y 27,60 USD y 120 zł y USD 5 y €30", "9 % del tope"):
            limpio = I._sin_dinero(crudo)
            self.assertIsNone(DINERO.search(limpio), limpio)
        self.assertEqual(I._sin_dinero("9 % del tope"), "9 % del tope")

    def test_formato_de_dinero_con_enteros_y_exponentes_de_la_moneda(self) -> None:
        f = I.formatear_dinero
        self.assertEqual(f(2760, "EUR"), "27,60 EUR")
        self.assertEqual(f(123456789, "USD"), "1.234.567,89 USD")
        self.assertEqual(f(-5, "USD"), "-0,05 USD")
        self.assertEqual(f(0, "USD"), "0,00 USD")
        self.assertEqual(f(1500, "JPY", {"JPY": 0}), "1.500 JPY")
        self.assertEqual(f(1500, "KWD", {"KWD": 3}), "1,500 KWD")
        self.assertEqual(f(10 ** 15, "USD"), "10.000.000.000.000,00 USD")

    def test_lo_que_te_toca_ordena_semaforo_firmas_y_pendientes_y_trae_comandos(self) -> None:
        self.base_sana()
        self.oferta("OF-202611-91", gate="D2")
        self.jsonl("empresa/panel/pulido.jsonl", [
            {"id": "PUL-0001", "evento": "alta", "titulo": "Uno", "responsable": "dueno", "prioridad": "P0"},
            {"id": "PUL-0002", "evento": "alta", "titulo": "Dos", "responsable": "dueno", "prioridad": "P3"}])
        tt = I.componer(self.ctx())["te_toca"]
        self.assertEqual([t["tipo"] for t in tt], ["firma", "pendiente"], "con la base sana no hay pasos del semáforo; la P3 no entra")
        self.assertIn("--etapa D2", tt[0]["comando"])
        self.assertEqual(tt[1]["id"], "PUL-0001")

    def test_plantilla_fija_hay_5_secciones_y_ningun_texto_libre_en_el_celular(self) -> None:
        self.jsonl("empresa/panel/pulido.jsonl", [{"id": "PUL-0001", "evento": "alta", "titulo": "TEXTO-LIBRE-DEL-DUENO https://x.example", "responsable": "dueno", "prioridad": "P0"}])
        v = I.componer(self.ctx())["versiones"]
        for n in ("1. VENTAS Y GASTO", "2. LOS 5 AVISOS", "3. LOS CEROS QUE IMPORTAN", "4. LO QUE TE TOCA A TI", "5. LO QUE TODAVÍA NO SE PUDO MEDIR"):
            self.assertIn(n, v["correo"]["texto"])
        self.assertIn("TEXTO-LIBRE-DEL-DUENO", v["correo"]["texto"], "el título del pendiente va en el correo, como dato")
        self.assertNotIn("http", v["correo"]["texto"])
        self.assertNotIn("TEXTO-LIBRE-DEL-DUENO", v["celular"]["texto"], "al celular no viaja ningún texto de archivos")
        self.assertLess(len(v["celular"]["texto"]), 900, "un mensaje corto")
        self.assertTrue(v["correo"]["asunto"].startswith("[ROJO] Informe del día 07/11/2026"))
        self.assertIn("No contiene texto escrito por una IA ni por terceros", v["correo"]["texto"])

    def test_los_pendientes_del_correo_se_acotan(self) -> None:
        self.jsonl("empresa/panel/pulido.jsonl", [{"id": f"PUL-{i:04d}", "evento": "alta", "titulo": f"Cosa {i}", "responsable": "dueno", "prioridad": "P1"} for i in range(1, 31)])
        texto = I.componer(self.ctx())["versiones"]["correo"]["texto"]
        self.assertIn("pendientes más en Mejoras pendientes", texto)
        self.assertLessEqual(texto.count("[P1]"), I.MAX_PENDIENTES_CORREO)

    def test_texto_hostil_no_rompe_ni_sale_con_controles(self) -> None:
        self.jsonl("empresa/panel/pulido.jsonl", [{"id": "PUL-0001", "evento": "alta", "titulo": "‮evil\x00\x1b[31m <script>alert(1)</script>", "responsable": "dueno", "prioridad": "P0"}])
        texto = I.componer(self.ctx())["versiones"]["correo"]["texto"]
        self.assertNotIn("‮", texto)
        self.assertNotIn("\x1b", texto)
        self.assertNotIn("\x00", texto)

    def test_no_escribe_nada_no_usa_red_y_es_determinista_y_json(self) -> None:
        self.base_sana()
        antes = self.hash_arbol()
        a, b = I.componer(self.ctx()), I.componer(self.ctx())
        self.assertEqual(a, b)
        self.assertEqual(self.hash_arbol(), antes)
        self.assertEqual(json.loads(json.dumps(a)), a)

    def test_la_linea_de_comandos_imprime_ambas_versiones_y_nada_mas(self) -> None:
        def correr(*args):
            s = io.StringIO()
            with contextlib.redirect_stdout(s):
                rc = I.main(list(args))
            return rc, s.getvalue()
        base = ["--raiz", str(self.raiz), "--ahora", "2026-11-07T08:30:00Z"]
        rc, out = correr(*base)
        self.assertEqual(rc, 0)
        self.assertIn("=== CORREO ===", out)
        self.assertIn("=== CELULAR ===", out)
        rc, out = correr(*base, "--version", "celular")
        self.assertNotIn("=== CORREO ===", out)
        rc, out = correr(*base, "--json")
        self.assertEqual(json.loads(out)["tipo"], "informe_diario")
        for malo in (["--ahora", "x"], ["--fecha", "ayer"]):
            s = io.StringIO()
            with contextlib.redirect_stderr(s):
                self.assertEqual(I.main(["--raiz", str(self.raiz), *malo]), 2)

    def test_la_fecha_del_informe_se_puede_elegir(self) -> None:
        self.oferta("OF-202611-91", fase="en_test")
        self.poner("ofertas/OF-202611-91/08-operacion/diario/2026-11-03/kpi_oferta_dia.json", kpi(gasto=1000, compras=1))
        inf = I.componer(self.ctx(), fecha="2026-11-03")
        self.assertEqual((inf["dia_medido"], inf["ventas_gasto"]["hay_datos"]), ("2026-11-03", True))
        self.assertIn("10,00 EUR", inf["versiones"]["correo"]["texto"])


if __name__ == "__main__":
    unittest.main()
