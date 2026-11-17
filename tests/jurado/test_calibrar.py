"""Pruebas de scripts/jurado/calibrar.py con casos sintéticos: jurado perfecto, aleatorio, invertido, acumulando, regla de apagado y promoción."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.jurado import _comun as c
from scripts.jurado import agregar as ag
from scripts.jurado import calibrar as cal
from tests.jurado.apoyo import AHORA, escenario_calibracion, jurado_sellado

# Parámetros de prueba: permutaciones reducidas para que la suite sea rápida; el resto, los de producción.
P = {"permutaciones": 400}


def _calibrar(jurados, metricas, **kw):
    return cal.calibrar(jurados, metricas, P, ahora=AHORA, **kw)


def _nivel(res, nombre):
    return next(n for n in res["niveles"] if n["madurez"] == nombre)


class PruebaJuradoPerfecto(unittest.TestCase):
    def test_perfecto_con_anclas_medidas_y_rubrica_peor_es_elegible(self):
        jurados, metricas = escenario_calibracion("perfecto")
        res = _calibrar(jurados, metricas)
        clics = _nivel(res, "clics")
        self.assertEqual(clics["etiquetas"], 300)
        self.assertAlmostEqual(clics["auc"], 1.0)
        self.assertAlmostEqual(_nivel(res, "inversion")["auc"], 1.0)
        self.assertGreater(clics["ic95"][0], 0.5)
        self.assertLess(clics["p_vs_azar"], 0.05)
        self.assertLess(clics["brier"], clics["brier_prevalencia"])
        self.assertGreater(clics["brier_skill"], 0)
        rub = next(b for b in clics["baselines"] if b["nombre"] == "rubrica_unica")
        self.assertGreater(rub["diferencia"], 0.1)
        self.assertLess(rub["p_unilateral"], 0.05)
        self.assertEqual(res["estado_global"], "elegible_asesor")
        self.assertEqual(res["nivel_principal"], "pago_iniciado")  # el nivel más maduro con ≥ 150 etiquetas decide
        self.assertTrue(res["valido_para_decidir"])
        self.assertIn("«predice ventas» NO está demostrado", " ".join(res["razones"]))

    def test_perfecto_pero_la_rubrica_lo_iguala_no_es_elegible(self):
        jurados, metricas = escenario_calibracion("perfecto", rubrica="igual")
        res = _calibrar(jurados, metricas)
        self.assertEqual(res["estado_global"], "sombra")
        self.assertTrue(any("no supera a la rúbrica" in r for r in res["razones"]))

    def test_perfecto_sin_ninguna_comparacion_con_la_rubrica_no_es_elegible(self):
        jurados, metricas = escenario_calibracion("perfecto", rubrica="ninguna")
        res = _calibrar(jurados, metricas)
        self.assertEqual(res["estado_global"], "sombra")
        self.assertTrue(any("sin comparación suficiente" in r for r in res["razones"]))

    def test_perfecto_con_anclas_solo_sinteticas_no_es_elegible(self):
        jurados, metricas = escenario_calibracion("perfecto")
        sinteticas = []
        for j in jurados:
            j = copy.deepcopy(j)
            j["anclas"]["medidas"] = 0
            j["sello"] = ag.sellar(j)
            sinteticas.append(j)
        res = _calibrar(sinteticas, metricas)
        self.assertEqual(res["estado_global"], "sombra")
        self.assertTrue(any("anclas no cumplen" in r for r in res["razones"]))

    def test_perfecto_con_anclas_que_no_discriminan_no_es_elegible(self):
        jurados, metricas = escenario_calibracion("perfecto")
        malas = []
        for j in jurados:
            j = copy.deepcopy(j)
            j["anclas"].update({"discrimina": False, "share_si_ganadoras": 0.2, "share_si_perdedoras": 0.6})
            j["sello"] = ag.sellar(j)
            malas.append(j)
        self.assertEqual(_calibrar(malas, metricas)["estado_global"], "sombra")


class PruebaJuradoAleatorioEInvertido(unittest.TestCase):
    def test_aleatorio_con_150_o_mas_etiquetas_se_apaga(self):
        jurados, metricas = escenario_calibracion("aleatorio", semilla=4, tandas=80)
        res = _calibrar(jurados, metricas)
        clics = _nivel(res, "clics")
        self.assertGreaterEqual(clics["etiquetas"], 150)
        self.assertLess(abs(clics["auc"] - 0.5), 0.1)
        self.assertEqual(res["estado_global"], "apagar")
        self.assertIn("APAGAR", res["accion"])

    def test_invertido_se_apaga_con_auc_cercano_a_cero(self):
        jurados, metricas = escenario_calibracion("invertido")
        res = _calibrar(jurados, metricas)
        self.assertLess(_nivel(res, "clics")["auc"], 0.1)
        self.assertEqual(res["estado_global"], "apagar")
        self.assertTrue(any("no supera al azar" in r for r in res["razones"]))

    def test_con_menos_de_150_etiquetas_no_se_juzga_aunque_el_jurado_sea_perfecto_o_pésimo(self):
        for habilidad in ("perfecto", "invertido", "aleatorio"):
            jurados, metricas = escenario_calibracion(habilidad, tandas=10)  # 100 etiquetas
            res = _calibrar(jurados, metricas)
            self.assertEqual(_nivel(res, "clics")["etiquetas"], 100)
            self.assertEqual(res["estado_global"], "acumulando", habilidad)
            self.assertIn("ningún nivel llega a 150", " ".join(res["razones"]))
            self.assertIn("acumular", res["accion"])

    def test_sin_etiquetas_no_inventa_precision(self):
        jurados, _ = escenario_calibracion("perfecto", tandas=3)
        res = _calibrar(jurados, [])
        self.assertEqual(res["estado_global"], "acumulando")
        p = res["precision"]
        self.assertEqual((p["auc"], p["brier"], p["etiquetas"]), (None, None, 0))
        self.assertTrue(all(n["etiquetas"] == 0 and n["auc"] is None for n in res["niveles"]))


class PruebaReglaDeEstado(unittest.TestCase):
    """La regla de apagado y de promoción, sobre estadísticos escritos a mano (sin simulación)."""

    def _r(self, **kw):
        base = {"etiquetas": 200, "auc": 0.7, "ic95": [0.62, 0.78], "p_vs_azar": 0.001,
                "baselines": [{"nombre": "rubrica_unica", "n_pareado": 200, "diferencia": 0.1, "p_unilateral": 0.01}]}
        base.update(kw)
        return base

    def test_acumulando_por_debajo_de_n_min(self):
        self.assertEqual(cal.estado_nivel(self._r(etiquetas=149), c.PARAMETROS_DEFECTO)[0], "acumulando")
        self.assertNotEqual(cal.estado_nivel(self._r(etiquetas=150), c.PARAMETROS_DEFECTO)[0], "acumulando")

    def test_apaga_si_el_auc_no_supera_al_azar(self):
        for auc in (0.5, 0.49, 0.2):
            self.assertEqual(cal.estado_nivel(self._r(auc=auc, ic95=[0.4, 0.6]), c.PARAMETROS_DEFECTO)[0], "apagar", auc)

    def test_apaga_si_ni_el_extremo_optimista_llega_al_minimo_util(self):
        self.assertEqual(cal.estado_nivel(self._r(auc=0.53, ic95=[0.48, 0.58]), c.PARAMETROS_DEFECTO)[0], "apagar")

    def test_sigue_en_sombra_si_el_intervalo_aun_deja_abierta_la_utilidad(self):
        estado, razones = cal.estado_nivel(self._r(auc=0.53, ic95=[0.43, 0.63], p_vs_azar=0.3), c.PARAMETROS_DEFECTO)
        self.assertEqual(estado, "sombra")
        self.assertTrue(any("incluye el azar" in r for r in razones))

    def test_auc_alto_pero_sin_significancia_contra_el_azar_es_sombra(self):
        self.assertEqual(cal.estado_nivel(self._r(p_vs_azar=0.2), c.PARAMETROS_DEFECTO)[0], "sombra")

    def test_elegible_exige_superar_a_la_rubrica(self):
        self.assertEqual(cal.estado_nivel(self._r(), c.PARAMETROS_DEFECTO)[0], "elegible_asesor")
        peor = self._r(baselines=[{"nombre": "rubrica_unica", "n_pareado": 200, "diferencia": 0.02, "p_unilateral": 0.4}])
        self.assertEqual(cal.estado_nivel(peor, c.PARAMETROS_DEFECTO)[0], "sombra")
        negativa = self._r(baselines=[{"nombre": "rubrica_unica", "n_pareado": 200, "diferencia": -0.05, "p_unilateral": 0.99}])
        self.assertEqual(cal.estado_nivel(negativa, c.PARAMETROS_DEFECTO)[0], "sombra")
        poca = self._r(baselines=[{"nombre": "rubrica_unica", "n_pareado": 40, "diferencia": 0.3, "p_unilateral": 0.0001}])
        self.assertEqual(cal.estado_nivel(poca, c.PARAMETROS_DEFECTO)[0], "sombra")

    def test_una_sola_clase_no_se_mide(self):
        self.assertEqual(cal.estado_nivel(self._r(auc=None, ic95=None), c.PARAMETROS_DEFECTO)[0], "sombra")


class PruebaEtiquetas(unittest.TestCase):
    def test_etiqueta_relativa_estrictamente_sobre_la_mediana_de_la_tanda(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=1)
        idx = cal.indexar_metricas(metricas)
        filas, motivo = cal.etiquetar_tanda(jurados[0], idx, "clics", dict(c.PARAMETROS_DEFECTO))
        self.assertIsNone(motivo)
        self.assertEqual(len(filas), 10)
        self.assertEqual(sum(f["positivo"] for f in filas), 5)
        valores = sorted(f["valor"] for f in filas)
        mediana = (valores[4] + valores[5]) / 2
        self.assertTrue(all((f["valor"] > mediana) == bool(f["positivo"]) for f in filas))

    def test_prediccion_sellada_despues_de_leer_el_resultado_no_cuenta(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=1)
        tarde = copy.deepcopy(jurados[0])
        tarde["sellado_en"] = "2026-11-21T07:00:00Z"  # la lectura es del 2026-11-20
        tarde["sello"] = ag.sellar(tarde)
        filas, motivo = cal.etiquetar_tanda(tarde, cal.indexar_metricas(metricas), "clics", dict(c.PARAMETROS_DEFECTO))
        self.assertEqual(filas, [])
        self.assertIn("menos de", motivo)

    def test_impresiones_insuficientes_no_etiquetan(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=1)
        for m in metricas:
            m["impresiones"] = 500
        filas, motivo = cal.etiquetar_tanda(jurados[0], cal.indexar_metricas(metricas), "clics", dict(c.PARAMETROS_DEFECTO))
        self.assertEqual(filas, [])

    def test_ventas_no_se_etiqueta_sin_gasto_minimo_de_economia(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=1)
        filas, motivo = cal.etiquetar_tanda(jurados[0], cal.indexar_metricas(metricas), "ventas", dict(c.PARAMETROS_DEFECTO))
        self.assertEqual(filas, [])
        self.assertIn("gasto_min_ventas", motivo)
        p = {**c.PARAMETROS_DEFECTO, "gasto_min_ventas": 10}
        for i, m in enumerate(metricas):
            m["compras"] = 1 if i < 3 else 0
        filas, motivo = cal.etiquetar_tanda(jurados[0], cal.indexar_metricas(metricas), "ventas", p)
        self.assertEqual(sum(f["positivo"] for f in filas), 3)

    def test_la_metrica_mas_reciente_de_cada_anuncio_gana(self):
        filas = [{"ad_name": "a", "oferta_id": "o", "fecha_lectura": "2026-11-12", "compras": 0},
                 {"ad_name": "a", "oferta_id": "o", "fecha_lectura": "2026-11-15", "compras": 2}]
        self.assertEqual(cal.indexar_metricas(filas)[("o", "a")]["compras"], 2)

    def test_metricas_malformadas_se_rechazan(self):
        with self.assertRaises(c.ErrorJurado):
            cal.validar_metricas([{"ad_name": "a", "fecha_lectura": "2026-11-12", "gasto": -3}])
        with self.assertRaises(c.ErrorJurado):
            cal.validar_metricas([{"fecha_lectura": "2026-11-12"}])
        with self.assertRaises(c.ErrorJurado):
            cal.validar_metricas([{"ad_name": "a", "fecha_lectura": "x", "impresiones": True}])


class PruebaAvataresYReemplazo(unittest.TestCase):
    def test_un_avatar_antipredictivo_se_propone_para_reemplazo_y_los_demas_no(self):
        jurados, metricas = escenario_calibracion("perfecto", avatar_malo=True, ruido_avatar=0.2)
        res = _calibrar(jurados, metricas)
        propuestos = [p["avatar_id"] for p in res["propuestas_reemplazo"]]
        self.assertEqual(propuestos, ["av-pl-PL-01"])
        malo = next(a for a in res["por_avatar"] if a["avatar_id"] == "av-pl-PL-01")
        self.assertLess(malo["auc_propio"], 0.3)
        self.assertGreaterEqual(malo["mejora_mitad_a"], 0)
        self.assertGreaterEqual(malo["mejora_mitad_b"], 0)
        self.assertIn("por debajo del azar", res["propuestas_reemplazo"][0]["motivo"])

    def test_decision_de_reemplazo_por_los_dos_caminos(self):
        base = {"etiquetas": 200, "auc_propio": 0.55, "ic95_propio": [0.47, 0.63], "auc_jurado": 0.7, "auc_jurado_sin_avatar": 0.72,
                "mejora_al_quitarlo": 0.02, "mejora_mitad_a": 0.03, "mejora_mitad_b": 0.01}
        d = c.PARAMETROS_DEFECTO
        self.assertTrue(cal.decidir_reemplazo(base, d)[0])                                           # camino 1
        self.assertFalse(cal.decidir_reemplazo({**base, "mejora_mitad_b": -0.01}, d)[0])             # no se repite en las dos mitades: ruido
        self.assertFalse(cal.decidir_reemplazo({**base, "mejora_al_quitarlo": 0.005}, d)[0])         # mejora bajo el mínimo
        self.assertFalse(cal.decidir_reemplazo({**base, "etiquetas": 100}, d)[0])                    # pocas etiquetas
        self.assertFalse(cal.decidir_reemplazo({**base, "auc_propio": 0.8}, d)[0])                   # él acierta más que el jurado
        peor = {**base, "auc_propio": 0.2, "ic95_propio": [0.12, 0.28], "mejora_al_quitarlo": 0.001, "mejora_mitad_a": 0.0, "mejora_mitad_b": 0.002}
        self.assertTrue(cal.decidir_reemplazo(peor, d)[0])                                           # camino 2
        self.assertFalse(cal.decidir_reemplazo({**peor, "mejora_mitad_a": -0.01}, d)[0])             # quitarlo empeora en una mitad

    def test_jurado_sano_no_propone_reemplazos(self):
        jurados, metricas = escenario_calibracion("perfecto", ruido_avatar=0.2)
        self.assertEqual(_calibrar(jurados, metricas)["propuestas_reemplazo"], [])

    def test_con_pocas_etiquetas_no_se_propone_reemplazar_a_nadie(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=8, avatar_malo=True, ruido_avatar=0.2)
        self.assertEqual(_calibrar(jurados, metricas)["propuestas_reemplazo"], [])


class PruebaIntegridad(unittest.TestCase):
    def test_un_jurado_con_sello_roto_o_de_demostracion_no_entra(self):
        jurados, _ = escenario_calibracion("perfecto", tandas=2)
        with tempfile.TemporaryDirectory() as d:
            ok, roto, demo = Path(d) / "ok.json", Path(d) / "roto.json", Path(d) / "demo.json"
            ok.write_text(json.dumps(jurados[0]), encoding="utf-8")
            m = copy.deepcopy(jurados[1])
            m["piezas"][0]["share_si"] = 0.0  # se tocó la predicción después de sellarla
            roto.write_text(json.dumps(m), encoding="utf-8")
            dm = copy.deepcopy(jurados[1])
            dm["demostracion"] = True
            dm["sello"] = ag.sellar(dm)
            demo.write_text(json.dumps(dm), encoding="utf-8")
            validos, descartados = cal.cargar_jurados([str(ok), str(roto), str(demo)], fixture=False)
            self.assertEqual(len(validos), 1)
            motivos = " ".join(x["motivo"] for x in descartados)
            self.assertIn("sello no coincide", motivos)
            self.assertIn("DEMOSTRACIÓN", motivos)
            validos_f, desc_f = cal.cargar_jurados([str(ok), str(demo)], fixture=True)
            self.assertEqual(len(validos_f), 1)
            self.assertIn("--fixture solo admite", desc_f[0]["motivo"])

    def test_no_se_mezclan_mercados(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=2)
        otro = jurado_sellado("OF-CAL", "tx", [{"ad_name": "z", "share_si": 0.5, "puntaje_medio": 5}], "2026-11-10T07:00:00Z", locale="it-IT")
        with self.assertRaises(c.ErrorJurado):
            _calibrar(jurados + [otro], metricas)

    def test_fixture_queda_marcado_y_no_vale_para_decidir(self):
        jurados, metricas = escenario_calibracion("perfecto")
        res = _calibrar(jurados, metricas, fixture=True)
        self.assertTrue(res["fixture"])
        self.assertFalse(res["valido_para_decidir"])
        self.assertTrue(any("FIXTURE" in r for r in res["razones"]))

    def test_la_fusion_de_precision_no_rompe_el_sello_y_alimenta_la_pantalla(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=12)
        res = _calibrar(jurados, metricas)
        with tempfile.TemporaryDirectory() as d:
            ruta_j, ruta_c = Path(d) / "jurado.json", Path(d) / "calibracion.json"
            ruta_j.write_text(json.dumps(jurados[0]), encoding="utf-8")
            ruta_c.write_text(json.dumps(res), encoding="utf-8")
            cal.fusionar_precision(str(ruta_j), res, str(ruta_c))
            doc = json.loads(ruta_j.read_text(encoding="utf-8"))
            self.assertTrue(ag.sello_valido(doc))
            p = doc["precision"]
            for k in ("auc", "brier", "etiquetas", "baselines", "estado"):
                self.assertIn(k, p)
            self.assertEqual(p["etiquetas"], 120)
            self.assertEqual(doc["calibracion_ref"]["estado_global"], "acumulando")
            self.assertTrue(all({"nombre", "auc"} <= set(b) for b in p["baselines"]))

    def test_cli_calibra_y_fusiona(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=20)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            rutas = []
            for i, j in enumerate(jurados):
                r = base / f"j{i}.json"
                r.write_text(json.dumps(j), encoding="utf-8")
                rutas.append(str(r))
            (base / "m.jsonl").write_text("\n".join(json.dumps(m) for m in metricas), encoding="utf-8")
            rc = cal.main(["--jurados", *rutas, "--metricas", str(base / "m.jsonl"), "--salida", str(base / "cal.json"),
                           "--fusionar-en", rutas[0], "--parametros", self._params(base), "--ahora", AHORA])
            self.assertEqual(rc, 0)
            res = json.loads((base / "cal.json").read_text(encoding="utf-8"))
            self.assertEqual(res["estado_global"], "elegible_asesor")
            self.assertTrue(ag.sello_valido(json.loads(Path(rutas[0]).read_text(encoding="utf-8"))))

    @staticmethod
    def _params(base: Path) -> str:
        r = base / "p.json"
        r.write_text(json.dumps({"permutaciones": 300}), encoding="utf-8")
        return str(r)

    def test_parametros_desconocidos_se_rechazan(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d) / "p.json"
            r.write_text(json.dumps({"auc_minimo": 0.7}), encoding="utf-8")
            with self.assertRaises(c.ErrorJurado):
                c.cargar_parametros(str(r))

    def test_anclas_sugeridas_salen_de_resultados_reales(self):
        jurados, metricas = escenario_calibracion("perfecto", tandas=20)
        res = _calibrar(jurados, metricas)
        sug = res["anclas_sugeridas"]["candidatas"]
        self.assertTrue({"ganadora", "perdedora"} <= {s["veredicto_conocido"] for s in sug})
        self.assertIn("persona", res["anclas_sugeridas"]["nota"])


if __name__ == "__main__":
    unittest.main()
