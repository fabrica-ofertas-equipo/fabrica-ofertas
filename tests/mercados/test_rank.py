"""Pruebas del ranking reproducible de mercados (scripts/mercados/rank.py).

Sin red ni credenciales. Los números esperados salen de docs/_investigacion/08 §2.2, §2.5 y de
16-red-team §2.2 y §5.1 (citados en cada prueba).
"""
import json
import os
import tempfile
import unittest

from scripts.mercados import rank as R

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 08 §2.2: total publicado por mercado y posición
TOTAL_08 = {"CA": 79, "NZ": 77, "AU": 76, "US": 69, "IE": 67, "GB": 66, "IT": 65, "HUS": 64,
            "PL": 63, "PT": 63, "BE": 60, "GR": 60, "SE": 56, "ES": 55, "CH": 54}
ORDEN_08 = ["CA", "NZ", "AU", "US", "IE", "GB", "IT", "HUS", "PL", "PT", "BE", "GR", "SE", "ES", "CH"]


def totales(**kw):
    e = R.escenario_base(cac_modo="derivado", pago_modo="derivado", **kw)
    return {f["codigo"]: round(f["total"]) for f in R.ranking(e, PAR, MERC)}


PAR, MERC, FUERA = R.cargar_datos()


class ReproduccionDe08(unittest.TestCase):
    def test_quince_totales_y_orden(self):
        filas = R.ranking(R.escenario_base(), PAR, MERC)
        self.assertEqual([f["codigo"] for f in filas], ORDEN_08)
        for f in filas:
            self.assertAlmostEqual(f["total"], TOTAL_08[f["codigo"]], places=6, msg=f["codigo"])

    def test_base_publicada(self):
        for m in MERC:
            f = R.evaluar(m, R.escenario_base(ajuste="ninguno"), PAR)
            self.assertAlmostEqual(f["base"], m["base_08"], places=6, msg=m["codigo"])

    def test_pagos_derivado_igual_publicado(self):
        for m in MERC:
            f = R.evaluar(m, R.escenario_base(pago_modo="derivado"), PAR)
            self.assertEqual(f["puntajes"]["PAGO_derivado"], m["puntajes_08"]["PAGO"]["v"], m["codigo"])

    def test_cac_derivado_igual_publicado_y_r_cercano(self):
        for m in MERC:
            f = R.evaluar(m, R.escenario_base(cac_modo="derivado"), PAR)
            self.assertEqual(f["puntajes"]["CAC_derivado"], m["puntajes_08"]["CAC"]["v"], m["codigo"])
            dif = abs(f["econ"]["r"] - m["r_publicado_08"])
            if m["codigo"] == "CH":
                self.assertTrue(0.05 < dif < 0.10)  # inconsistencia documentada de la fila de Suiza
            else:
                self.assertLess(dif, 0.05, m["codigo"])

    def test_inconsistencia_de_suiza(self):
        """17 H1: la fila de Suiza publica r = 1,50 con CAC 2, pero la regla da 3 para r <= 1,5."""
        ch = next(m for m in MERC if m["codigo"] == "CH")
        con_iva = R.evaluar(ch, R.escenario_base(), PAR)["econ"]
        sin_iva = R.evaluar(ch, R.escenario_base(iva={"CH": 0.0}), PAR)["econ"]
        self.assertAlmostEqual(con_iva["r"], 1.58, places=2)
        self.assertAlmostEqual(sin_iva["r"], 1.45, places=2)
        self.assertAlmostEqual(sin_iva["equilibrio_pct"], 2.90, places=2)  # el 2,9 % publicado es sin IVA
        self.assertEqual(R.puntaje_cac(con_iva["r"], PAR), 2)   # coherente con el 2 publicado
        self.assertEqual(R.puntaje_cac(sin_iva["r"], PAR), 3)   # lo que daría sin IVA
        self.assertEqual(R.puntaje_cac(1.5, PAR), 3)            # la regla literal con r = 1,50
        t = totales(iva={"CH": 0.0})
        self.assertEqual(t["CH"], 58)


class Sensibilidades08(unittest.TestCase):
    """08 §2.5, reejecutadas."""

    def test_ctr(self):
        t = totales(ctr=0.012)
        self.assertEqual((t["CA"], t["NZ"], t["AU"], t["US"], t["IT"], t["PL"]), (71, 69, 68, 65, 57, 55))
        t = totales(ctr=0.010)
        self.assertEqual((t["CA"], t["AU"], t["IT"], t["PL"]), (71, 68, 53, 51))

    def test_sin_creadores(self):
        t = totales(ajuste="ninguno")
        self.assertEqual((t["CA"], t["NZ"], t["AU"], t["PL"], t["IT"]), (77, 76, 75, 63, 60))

    def test_ticket_17(self):
        t = totales(ticket={c: 17.0 for c in R.INGLES_27})
        self.assertEqual((t["CA"], t["NZ"], t["AU"], t["IE"], t["IT"], t["US"], t["PL"], t["GB"]),
                         (75, 69, 68, 67, 65, 65, 63, 62))

    def test_pesos_alternativos(self):
        w1 = {"PA": 15, "CAC": 30, "COMP": 10, "PAGO": 10, "FISC": 15, "LOC": 10, "FRAUD": 10}
        t = totales(pesos=w1)
        self.assertEqual((t["NZ"], t["CA"], t["AU"], t["IT"], t["PL"]), (75, 73, 72, 65, 61))
        w2 = {"PA": 15, "CAC": 10, "COMP": 10, "PAGO": 30, "FISC": 15, "LOC": 10, "FRAUD": 10}
        t = totales(pesos=w2)
        self.assertEqual((t["CA"], t["IT"], t["PL"]), (85, 65, 65))

    def test_pesos_iguales_italia_es_60_no_63(self):
        """08 §2.5 dice 'PL 63, IT 63'; con pesos iguales y sin creadores Italia da 60 (21/35)."""
        t = totales(ajuste="ninguno", pesos={k: 1 for k in R.CRITERIOS})
        self.assertEqual((t["CA"], t["NZ"], t["AU"], t["PL"], t["IT"]), (77, 77, 77, 63, 60))


class NetoCompleto(unittest.TestCase):
    def test_cascada_16(self):
        """16 §2.2: neto esperado PL/BLIK ~8,9; PL/tarjeta ~8,7; IT ~11,6."""
        e = R.escenario_base(neto="completo")
        self.assertAlmostEqual(R.neto_completo(13.17, .23, .044, .30, 0.0, PAR, e), 8.9, delta=0.05)
        self.assertAlmostEqual(R.neto_completo(13.17, .23, .054, .30, 1.0, PAR, e), 8.7, delta=0.05)
        self.assertAlmostEqual(R.neto_completo(17.28, .22, .054, .30, 1.0, PAR, e), 11.6, delta=0.05)

    def test_tabla_16_5_1(self):
        t = totales(neto="completo")
        for cod, esperado in {"CA": 75, "NZ": 73, "AU": 72, "IE": 67, "IT": 65, "US": 65, "HUS": 64,
                              "PT": 63, "GB": 62, "PL": 59, "BE": 56}.items():
            self.assertEqual(t[cod], esperado, cod)
        self.assertEqual(t["IT"] - t["PL"], 6)  # 16: Italia queda 6 puntos sobre Polonia

    def test_grecia_en_el_borde(self):
        """16 §5.1 estima Grecia en ~56 con el factor 0,90; el cálculo exacto da r = 1,24 (CAC 4) y 60."""
        gr = next(m for m in MERC if m["codigo"] == "GR")
        f = R.evaluar(gr, R.escenario_base(neto="completo", cac_modo="derivado"), PAR)
        self.assertLess(f["econ"]["r"], 1.25)
        self.assertGreater(f["econ"]["r"], 1.20)

    def test_el_neto_completo_nunca_sube_el_total(self):
        base = totales()
        comp = totales(neto="completo")
        for c in base:
            self.assertLessEqual(comp[c], base[c], c)


class Escenarios(unittest.TestCase):
    def test_cpm_monotono(self):
        a, b, c = (totales(cpm_mult=x) for x in (1.0, 1.2, 1.5))
        for k in a:
            self.assertGreaterEqual(a[k], b[k])
            self.assertGreaterEqual(b[k], c[k])

    def test_q4_x12_no_mueve_el_top3(self):
        self.assertEqual({k for k, v in sorted(totales(cpm_mult=1.2).items(), key=lambda x: -x[1])[:3]},
                         {"CA", "NZ", "AU"})

    def test_sin_pagos_igual_a_rank_sin_pagos(self):
        rsp = R.cargar_rank_sin_pagos()
        ref = rsp.calcular()
        mio = sorted(R.ranking(R.escenario_base(excluir=["PAGO"]), PAR, MERC), key=lambda f: f["orden_08"])
        self.assertEqual(len(ref), len(mio))
        for r, f in zip(ref, mio):
            self.assertAlmostEqual(f["total"], r["sin_pagos_con_ajuste"], delta=0.06, msg=f["codigo"])
            self.assertAlmostEqual(f["base"], r["sin_pagos"], delta=0.06, msg=f["codigo"])

    def test_datos_de_rank_sin_pagos_coinciden_con_mercados_json(self):
        rsp = R.cargar_rank_sin_pagos()
        for (nombre, v), m in zip(rsp.MERCADOS.items(), MERC):
            p = m["puntajes_08"]
            mio = tuple(p[k]["v"] for k in R.CRITERIOS) + (m["ajuste_creadores_08"],)
            self.assertEqual(tuple(v), mio, nombre)

    def test_pesos_suman_100(self):
        for kw in ({}, {"excluir": ["PAGO"]}, {"escala_peso": 10}, {"pesos": {k: 1 for k in R.CRITERIOS}}):
            w = R.pesos_efectivos(R.escenario_base(**kw), PAR)
            self.assertAlmostEqual(sum(w.values()), 100.0, places=6, msg=str(kw))

    def test_ajuste_en_regla_usa_solo_valores_permitidos(self):
        perm = set(PAR["creadores_regla_08"]["valores_permitidos"])
        for m in MERC:
            self.assertIn(m["ajuste_creadores_regla"], perm, m["codigo"])
        self.assertEqual(next(m for m in MERC if m["codigo"] == "US")["ajuste_creadores_regla"], 3)

    def test_cac_relativo_vuelve_a_discriminar(self):
        absoluto = R.ranking(R.escenario_base(neto="completo", ctr=0.013, cpm_mult=1.2, cac_modo="derivado"), PAR, MERC)
        self.assertGreaterEqual(sum(1 for f in absoluto if f["puntajes"]["CAC"] == 0), 13)  # satura en 0
        rel = R.ranking(R.escenario_base(neto="completo", ctr=0.013, cpm_mult=1.2, cac_modo="relativo"), PAR, MERC)
        self.assertGreaterEqual(len({f["puntajes"]["CAC"] for f in rel}), 4)

    def test_estabilidad_metricas(self):
        S, res, est = R.correr_todos(PAR, MERC)
        self.assertTrue(est["08_publicado"]["top3_igual_a_base"])
        self.assertEqual(est["08_publicado"]["spearman_vs_base"], 1.0)
        self.assertEqual(est["neto_completo_pct"]["dif_IT_menos_PL"], 6.0)
        for k, e in est.items():
            self.assertTrue(-1.0 <= e["spearman_vs_base"] <= 1.0, k)

    def test_rejilla_determinista_y_completa(self):
        g1, g2 = R.rejilla(PAR, MERC), R.rejilla(PAR, MERC)
        self.assertEqual(g1, g2)
        self.assertEqual(g1["n"], 216)
        self.assertEqual(len(g1["frecuencia"]), 15)


class DatosYReproducibilidad(unittest.TestCase):
    def test_campos_y_fuentes(self):
        claves = ("cpm_usd", "cpm_fuente", "tarifa_meta", "tarifa_meta_fuente", "ticket_usd", "ticket_fuente",
                  "iva", "iva_fuente", "comision_pct", "comision_fijo_usd", "comision_fuente", "comision_tarjeta_pct")
        self.assertEqual(len(MERC), 15)
        for m in MERC:
            for k in claves:
                self.assertIn(k, m["economia"], f"{m['codigo']}.{k}")
                if k.endswith("fuente"):
                    self.assertTrue(m["economia"][k].strip(), f"{m['codigo']}.{k}")
            self.assertTrue(m["pagos"]["fuente"].strip())
            self.assertTrue(m["escala"]["fuente"].strip())

    def test_fuera_del_top15(self):
        self.assertEqual(len(FUERA["totales"]), 9)  # 24 mercados puntuados - 15

    def test_exportar_coincide_con_el_archivo_versionado(self):
        versionado = os.path.join(RAIZ, "scripts", "mercados", "resultados", "escenarios.json")
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "x.json")
            R.exportar(ruta, PAR, MERC)
            with open(ruta, encoding="utf-8") as a, open(versionado, encoding="utf-8") as b:
                self.assertEqual(json.load(a), json.load(b),
                                 "regenerar: python3 -I scripts/mercados/rank.py --exportar scripts/mercados/resultados/escenarios.json")

    def test_cli_por_defecto_sin_errores(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = R.main([])
        self.assertEqual(rc, 0)
        self.assertIn("OK: 15 totales", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
