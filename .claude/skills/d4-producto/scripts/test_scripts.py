#!/usr/bin/env python3
"""Pruebas de los scripts de D4 (unittest, biblioteca estándar; fixtures sintéticos en carpetas temporales; sin red).

Ejecutar:  .venv/bin/python .claude/skills/d4-producto/scripts/test_scripts.py
Cada prueba «sembrada» reproduce un defecto del Anexo B de la spec (ver evals/sembrados/catalogo.json) y exige que el script lo detecte.
Los umbrales que se pasan por bandera aquí son DATOS DE PRUEBA, no política: la política vive en empresa/parametros.yaml.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import _comun as c  # noqa: E402
import cobertura_matriz, cotizar_creditos, empaquetar, lint_contenido, lint_hoja, similitud_ngrama, tiempo_total, verificar_respaldo  # noqa: E402

RAIZ = c.raiz_proyecto(AQUI)


def correr(modulo, args: list[str]) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        cod = modulo.main(args)
    txt = out.getvalue().strip()
    return cod, (json.loads(txt) if txt else {"stderr": err.getvalue()})


def ids(res: dict, severidad: str | None = None) -> set[str]:
    return {h.get("patron_clave") or h["check_id"] for h in res.get("hallazgos", []) if severidad is None or h["severidad"] == severidad}


def escribir(p: Path, txt: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")
    return p


def oferta_base() -> dict:
    return {"locale": "it-IT", "promesa": {"tiempo_prometido_min": 60, "claims_permitidos": [
        {"claim_id": "incluye-tabella", "texto": "Include una tabella di spese", "evidencia_ref": "04-producto/producto.json#items"},
        {"claim_id": "garanzia", "texto": "Garanzia 14 giorni", "evidencia_ref": "03-oferta/oferta.json#garantia"}],
        "claims_prohibidos": []},
        "vehiculo": {"formato": "pack", "tiempo_consumo_min": 55, "palabras_max": 3000},
        "entregables": [{"id": "guida", "tipo": "guía", "cantidad": 1, "formato": "pdf"}], "bonus": [], "bump": None}


def producto_base(base: str = "estimado", ejec: int = 30, lect: int = 20) -> dict:
    return {"items": [{"id": "guida", "tipo": "guia_md", "archivo": "entregables/guida-v1-guia.md", "paginas": None, "peso_mb": "0.01",
                       "sha256": "sha256:" + "0" * 64, "formato": "markdown", "idioma": "it-IT", "en_paquete": True}],
            "matriz_promesas": [{"promesa_id": "tabella", "texto": "Include una tabella di spese", "entregable_id": "guida", "prueba": "Sezione 2 della guida", "estado": "cumplida"}],
            "tiempos": {"lectura_min": lect, "ejecucion_min": ejec, "total_min": lect + ejec, "prometido_min": 60, "base": base},
            "pasos": [{"id": "p1", "ejecutable_por_agente": False, "t_humano_min": 10}, {"id": "p2", "ejecutable_por_agente": False, "t_humano_min": ejec - 10}]}


class PruebasTiempo(unittest.TestCase):
    def preparar(self, tmp: Path, prod: dict, oferta: dict | None = None):
        escribir(tmp / "producto.json", json.dumps(prod))
        escribir(tmp / "oferta.json", json.dumps(oferta or oferta_base()))
        return ["--producto", str(tmp / "producto.json"), "--oferta", str(tmp / "oferta.json"), "--wpm", "200", "--tolerancia", "1.25", "--lectura-max-pct", "40"]

    def test_dentro_de_tolerancia(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.preparar(Path(t), producto_base())
            cod, res = correr(tiempo_total, args + ["--palabras", "4000"])  # 4000/200 = 20 min
            self.assertEqual(cod, 0, res)
            self.assertEqual(res["resumen"]["total_calc_min"], 50)

    def test_sembrado_55_contra_20_prometidos(self):
        """Defecto heredado: método de 55 min contra 20 prometidos → bloquea y manda a D3."""
        with tempfile.TemporaryDirectory() as t:
            p = producto_base(ejec=40, lect=15)
            p["tiempos"]["prometido_min"] = 20
            o = oferta_base()
            o["promesa"]["tiempo_prometido_min"] = 20
            cod, res = correr(tiempo_total, self.preparar(Path(t), p, o) + ["--palabras", "3000"])
            self.assertEqual(cod, 1)
            self.assertIn("L1-03", ids(res, "BLOQUEANTE") | {h["check_id"] for h in res["hallazgos"] if h["severidad"] == "BLOQUEANTE"})

    def test_promesa_cambiada_por_d4(self):
        with tempfile.TemporaryDirectory() as t:
            p = producto_base()
            p["tiempos"]["prometido_min"] = 90
            cod, res = correr(tiempo_total, self.preparar(Path(t), p) + ["--palabras", "100"])
            self.assertEqual(cod, 1)
            self.assertTrue(any("nunca cambia la promesa" in h["mensaje"] for h in res["hallazgos"]))

    def test_pasos_no_suman_ejecucion(self):
        with tempfile.TemporaryDirectory() as t:
            p = producto_base()
            p["pasos"][0]["t_humano_min"] = 25  # 25 + 20 != 30
            cod, res = correr(tiempo_total, self.preparar(Path(t), p) + ["--palabras", "100"])
            self.assertEqual(cod, 1)
            self.assertTrue(any("Σ pasos" in h["mensaje"] for h in res["hallazgos"]))

    def test_cold_run_admite_tolerancia(self):
        with tempfile.TemporaryDirectory() as t:
            p = producto_base(base="cold_run_humano", ejec=50, lect=20)  # total 70 ≤ 60 × 1,25 = 75
            cod, res = correr(tiempo_total, self.preparar(Path(t), p) + ["--palabras", "4000"])
            self.assertEqual(cod, 0, res)

    def test_falta_parametro_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            escribir(Path(t) / "producto.json", json.dumps(producto_base()))
            escribir(Path(t) / "oferta.json", json.dumps(oferta_base()))
            cod, _ = correr(tiempo_total, ["--producto", f"{t}/producto.json", "--oferta", f"{t}/oferta.json", "--palabras", "10", "--parametros", f"{t}/no-existe.yaml"])
            self.assertEqual(cod, 5)

    def test_desvio_primer_paso(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.preparar(Path(t), producto_base()) + ["--palabras", "100", "--medido-primer-paso-min", "20", "--estimado-primer-paso-min", "10", "--desvio-max-pct", "25"]
            cod, res = correr(tiempo_total, args)
            self.assertEqual(cod, 1)
            self.assertTrue(any("promete de más" in h["mensaje"] for h in res["hallazgos"]))


class PruebasMatriz(unittest.TestCase):
    def montar(self, tmp: Path, oferta: dict, prod: dict, archivos: dict[str, str] | None = None) -> list[str]:
        escribir(tmp / "03-oferta" / "oferta.json", json.dumps(oferta))
        escribir(tmp / "04-producto" / "producto.json", json.dumps(prod))
        for rel, txt in (archivos or {"entregables/guida-v1-guia.md": "# Guida\n"}).items():
            escribir(tmp / "04-producto" / rel, txt)
        return ["--oferta-dir", str(tmp)]

    def test_ok(self):
        with tempfile.TemporaryDirectory() as t:
            cod, res = correr(cobertura_matriz, self.montar(Path(t), oferta_base(), producto_base()))
            self.assertEqual(cod, 0, res)

    def test_sembrado_item_prometido_ausente(self):
        with tempfile.TemporaryDirectory() as t:
            o = oferta_base()
            o["bonus"] = [{"id": "video-comparativo", "descripcion": "Video comparativo"}]
            cod, res = correr(cobertura_matriz, self.montar(Path(t), o, producto_base()))
            self.assertEqual(cod, 1)
            self.assertIn("item-prometido-ausente", ids(res, "BLOQUEANTE"))

    def test_item_sin_promesa_es_relleno(self):
        with tempfile.TemporaryDirectory() as t:
            p = producto_base()
            p["items"].append(dict(p["items"][0], id="extra", archivo="entregables/extra-v1-guia.md"))
            cod, res = correr(cobertura_matriz, self.montar(Path(t), oferta_base(), p, {"entregables/guida-v1-guia.md": "x", "entregables/extra-v1-guia.md": "y"}))
            self.assertEqual(cod, 1)
            self.assertIn("item-sin-promesa", ids(res))

    def test_sembrado_servicio_humano_en_bonus(self):
        with tempfile.TemporaryDirectory() as t:
            o = oferta_base()
            o["bonus"] = [{"id": "sesion", "descripcion": "Sessione individuale 1:1 di 30 minuti"}]
            p = producto_base()
            p["items"].append(dict(p["items"][0], id="sesion", archivo="entregables/sesion-v1-guia.md"))
            p["matriz_promesas"].append({"promesa_id": "sesion", "texto": "Sessione", "entregable_id": "sesion", "prueba": "x", "estado": "cumplida"})
            cod, res = correr(cobertura_matriz, self.montar(Path(t), o, p, {"entregables/guida-v1-guia.md": "x", "entregables/sesion-v1-guia.md": "y"}))
            self.assertEqual(cod, 1)
            self.assertIn("servicio-oculto", ids(res, "BLOQUEANTE"))

    def test_idioma_distinto_y_n_unidades(self):
        with tempfile.TemporaryDirectory() as t:
            o = oferta_base()
            o["entregables"][0].update(cantidad=40, tipo="biblioteca")
            p = producto_base()
            p["items"][0]["idioma"] = "es-ES"
            tmp = Path(t)
            args = self.montar(tmp, o, p)
            escribir(tmp / "04-producto" / "entregables" / "fuente" / "guida-unidades.jsonl", "\n".join(json.dumps({"unidad_id": i}) for i in range(38)) + "\n")
            cod, res = correr(cobertura_matriz, args)
            self.assertEqual(cod, 1)
            self.assertIn("n-unidades", ids(res, "BLOQUEANTE"))
            self.assertTrue(any(h["check_id"] == "L1-01" for h in res["hallazgos"]))

    def test_filas_pendientes_solo_en_etapa_intermedia(self):
        with tempfile.TemporaryDirectory() as t:
            p = producto_base()
            p["matriz_promesas"][0]["estado"] = "pendiente"
            args = self.montar(Path(t), oferta_base(), p)
            cod, res = correr(cobertura_matriz, args)
            self.assertEqual(cod, 1)
            cod, res = correr(cobertura_matriz, args + ["--permitir-pendientes"])
            self.assertEqual(cod, 0, res)

    def test_ejemplo_dorado_se_lee_sin_error(self):
        """No exige PASS (el ejemplo es abreviado): exige que el script corra y devuelva JSON sobre la oferta de ejemplo del repositorio."""
        if not RAIZ or not (RAIZ / "ofertas" / "_ejemplo").is_dir():
            self.skipTest("sin ofertas/_ejemplo")
        cod, res = correr(cobertura_matriz, ["--oferta-dir", str(RAIZ / "ofertas" / "_ejemplo")])
        self.assertIn(cod, (0, 1))
        self.assertEqual(res["script"], "cobertura_matriz")


class PruebasSimilitud(unittest.TestCase):
    FUENTE = "La regla del cincuenta treinta veinte divide los ingresos netos mensuales en tres bloques: necesidades, deseos y ahorro, y se usa como punto de partida."

    def correr(self, producto: str, extra: list[str] | None = None, fuente: str | None = None):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        tmp = Path(t.name)
        escribir(tmp / "prod" / "a.md", producto)
        escribir(tmp / "src" / "f.txt", fuente or self.FUENTE)
        return correr(similitud_ngrama, ["--producto", str(tmp / "prod"), "--fuentes", str(tmp / "src"), "--n", "8", "--alerta", "6"] + (extra or []))

    def test_sin_copia(self):
        cod, res = self.correr("Esta guía propone tres pasos propios: anota, clasifica y decide cada semana con tus datos reales.")
        self.assertEqual(cod, 0, res)

    def test_sembrado_parrafo_copiado_8_palabras(self):
        cod, res = self.correr("Intro propia. La regla del cincuenta treinta veinte divide los ingresos netos mensuales en tres bloques. Cierre propio.")
        self.assertEqual(cod, 1)
        self.assertIn("copia-literal", ids(res, "BLOQUEANTE"))

    def test_alerta_6_o_7_no_bloquea(self):
        cod, res = self.correr("Texto previo distinto. divide los ingresos netos mensuales en tres. Texto posterior distinto aquí.")
        self.assertEqual(cod, 0, res)
        self.assertIn("copia-alerta", ids(res, "MENOR"))

    def test_cita_corta_entrecomillada_pide_atribucion(self):
        cod, res = self.correr("Según el organismo: «la regla del cincuenta treinta veinte divide los ingresos netos mensuales en tres bloques» y nada más.")
        self.assertEqual(cod, 0, res)
        self.assertIn("cita-a-verificar", ids(res, "MENOR"))

    def test_literal_permitido_se_ignora(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        tmp = Path(t.name)
        fuente = "Si necesitas ayuda ahora llama al número de emergencias del país o a la línea de apoyo indicada aquí"
        escribir(tmp / "prod" / "a.md", "Contenido propio. " + fuente + ". Más contenido propio.")
        escribir(tmp / "src" / "f.txt", fuente)
        escribir(tmp / "lit.txt", fuente + "\n")
        cod, res = correr(similitud_ngrama, ["--producto", str(tmp / "prod"), "--fuentes", str(tmp / "src"), "--n", "8", "--alerta", "6", "--permitir-literal", str(tmp / "lit.txt")])
        self.assertEqual(cod, 0, res)
        self.assertEqual(res["resumen"]["tramos_permitidos_ignorados"], 1)

    def test_diacriticos_no_burlan(self):
        cod, res = self.correr("La regla del cincuenta treinta veinte divide los ingresos netos mensuales en tres bloques", fuente=self.FUENTE.replace("ingresos", "ingrésos"))
        self.assertEqual(cod, 1)

    def test_muestreo_para_busqueda_web(self):
        largo = " ".join(f"palabra{i}distinta" for i in range(200))
        cod, res = self.correr(largo, ["--muestrear", "5"])
        self.assertEqual(len(res["resumen"]["frases_para_busqueda_web"]), 5)


class PruebasRespaldo(unittest.TestCase):
    TXT_FUENTE = "Fuente oficial. La cucchiaiata corrisponde a 15 g. Un cucchiaino equivale a 5 g di zucchero. Soglia fiscale: 1.500 euro all'anno."

    def montar(self, tmp: Path, texto_producto: str, filas: list[dict], extra_fuente: str | None = None):
        rd = tmp / "respaldo"
        escribir(rd / "fuentes" / "f1.txt", extra_fuente or self.TXT_FUENTE)
        sha = c.hash_archivo(rd / "fuentes" / "f1.txt")
        with open(rd / "afirmaciones.jsonl", "w", encoding="utf-8") as f:
            for i, fila in enumerate(filas, 1):
                base = {"afirmacion_id": f"A{i}", "tema": "dosi", "tipo": "cifra", "fuente_id": "f1", "fuente_url": "https://fuente.example.invalid/x", "nivel_fuente": "T1",
                        "fecha_fuente": "2026-10-01", "fecha_consulta": "2026-11-05", "sha256": sha, "pais_fuente": "IT", "unidad": "g", "unidad_fuente": "g"}
                base.update(fila)
                f.write(json.dumps(base, ensure_ascii=False) + "\n")
        escribir(tmp / "prod" / "guida.md", texto_producto)
        return ["--respaldo-dir", str(rd), "--producto", str(tmp / "prod"), "--locale", "it-IT", "--paises", "IT", "--hoy", "2026-11-06", "--max-dias", "14", "--min-fuentes", "1"]

    def fila_ok(self, **kw):
        d = {"texto_en_producto": "Un cucchiaino di zucchero pesa 5 g", "cita_literal": "Un cucchiaino equivale a 5 g di zucchero", "valor_normalizado": "5", "unidad_fuente": "g"}
        d.update(kw)
        return d

    def test_ok(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Un cucchiaino di zucchero pesa 5 g. Fine.", [self.fila_ok()])
            cod, res = correr(verificar_respaldo, args)
            self.assertEqual(cod, 0, res)

    def test_sembrado_dosis_x10(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Un cucchiaino di zucchero pesa 50 g.", [self.fila_ok(texto_en_producto="Un cucchiaino di zucchero pesa 50 g")])
            cod, res = correr(verificar_respaldo, args)
            self.assertEqual(cod, 1)
            self.assertIn("cifra-distinta-de-fuente", ids(res, "BLOQUEANTE"))

    def test_sembrado_cucchiaio_por_cucchiaino(self):
        with tempfile.TemporaryDirectory() as t:
            fila = self.fila_ok(texto_en_producto="Un cucchiaio di zucchero pesa 5 g", unidad="cucchiaio", unidad_fuente="cucchiaino",
                                cita_literal="Un cucchiaino equivale a 5 g di zucchero")
            args = self.montar(Path(t), "Un cucchiaio di zucchero pesa 5 g.", [fila])
            cod, res = correr(verificar_respaldo, args)
            self.assertEqual(cod, 1)
            self.assertIn("unidad-distinta", ids(res, "BLOQUEANTE"))

    def test_sembrado_separador_de_miles_ingles_en_it(self):
        with tempfile.TemporaryDirectory() as t:
            fila = self.fila_ok(texto_en_producto="La soglia è 1,500 euro all'anno", cita_literal="Soglia fiscale: 1.500 euro all'anno", valor_normalizado="1500", unidad="euro", unidad_fuente="euro", tipo="umbral", tema="fisco")
            args = self.montar(Path(t), "La soglia è 1,500 euro all'anno.", [fila])
            cod, res = correr(verificar_respaldo, args)
            self.assertEqual(cod, 1)
            self.assertIn("cifra-distinta-de-fuente", ids(res, "BLOQUEANTE"))

    def test_sembrado_cita_no_esta_en_la_fuente(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Un cucchiaino di zucchero pesa 5 g.", [self.fila_ok(cita_literal="Una frase que la fuente no contiene nunca")])
            cod, res = correr(verificar_respaldo, args)
            self.assertIn("cita-no-esta-en-fuente", ids(res, "BLOQUEANTE"))

    def test_sembrado_snapshot_alterado(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            args = self.montar(tmp, "Un cucchiaino di zucchero pesa 5 g.", [self.fila_ok()])
            (tmp / "respaldo" / "fuentes" / "f1.txt").write_text(self.TXT_FUENTE + " Añadido después.", encoding="utf-8")
            cod, res = correr(verificar_respaldo, args)
            self.assertIn("snapshot-alterado", ids(res, "BLOQUEANTE"))

    def test_sembrado_url_no_https_y_fecha_verificado_falso(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Un cucchiaino di zucchero pesa 5 g.", [self.fila_ok(fuente_url="http://x", fecha_consulta="2026-12-31")])
            cod, res = correr(verificar_respaldo, args)
            self.assertIn("url-invalida", ids(res, "BLOQUEANTE"))
            self.assertIn("fecha-falsa", ids(res, "BLOQUEANTE"))

    def test_dosis_con_fuente_t2_o_de_otro_pais(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Un cucchiaino di zucchero pesa 5 g.", [self.fila_ok(tipo="dosis", nivel_fuente="T2", pais_fuente="US")])
            cod, res = correr(verificar_respaldo, args)
            self.assertIn("nivel-insuficiente", ids(res, "BLOQUEANTE"))
            self.assertIn("fuente-de-otro-pais", ids(res, "BLOQUEANTE"))

    def test_cifra_del_texto_sin_respaldo(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Un cucchiaino di zucchero pesa 5 g. Il piano costa 2.400 euro.", [self.fila_ok()])
            cod, res = correr(verificar_respaldo, args)
            self.assertEqual(cod, 1)
            self.assertIn("cifra-sin-respaldo", ids(res, "BLOQUEANTE"))

    def test_fuente_vieja(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Un cucchiaino di zucchero pesa 5 g.", [self.fila_ok(fecha_consulta="2026-09-01", fecha_fuente="2026-08-01")])
            cod, res = correr(verificar_respaldo, args)
            self.assertIn("fuente-vieja", ids(res, "MAYOR"))

    def test_producto_sin_hechos_pasa_con_nota(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            escribir(tmp / "prod" / "a.md", "Una plantilla en blanco con tres columnas.")
            cod, res = correr(verificar_respaldo, ["--respaldo-dir", str(tmp / "respaldo"), "--producto", str(tmp / "prod"), "--locale", "es-ES", "--hoy", "2026-11-06", "--max-dias", "14", "--min-fuentes", "1"])
            self.assertEqual(cod, 0, res)
            self.assertIn("sin hechos externos", res["resumen"]["nota"])

    def test_numeros_por_locale(self):
        self.assertEqual(c.interpretar_numero("1.500", "it-IT")[0], 1500)
        self.assertIn("ambiguo_miles_decimal", c.interpretar_numero("1,500", "it-IT")[1])
        self.assertEqual(c.interpretar_numero("1,500", "en-US")[0], 1500)
        self.assertIn("separador_ajeno", c.interpretar_numero("1.5", "es-ES")[1])
        self.assertEqual(c.interpretar_numero("1 500", "pl-PL")[0], 1500)
        self.assertIn("no_numero", c.interpretar_numero("3.2.1", "es-ES")[1])


class PruebasPlantillas(unittest.TestCase):
    """Las plantillas de la skill deben pasar los propios scripts y validar contra los esquemas (no se rompen en silencio)."""

    PLANTILLAS = AQUI.parent / "templates"

    def test_respaldo_de_ejemplo_pasa_verificar_respaldo(self):
        rd = self.PLANTILLAS / "respaldo_ejemplo"
        cod, res = correr(verificar_respaldo, ["--respaldo-dir", str(rd), "--producto", str(rd / "producto_ejemplo.md"), "--locale", "es-ES", "--paises", "ES",
                                                "--hoy", "2026-11-06", "--max-dias", "14", "--min-fuentes", "3"])
        self.assertEqual(cod, 0, res)

    def test_plantillas_json_validan_contra_su_esquema(self):
        if not RAIZ:
            self.skipTest("sin raíz del proyecto")
        sys.path.insert(0, str(RAIZ))
        from scripts.validar_esquemas import errores_de_esquema  # type: ignore

        for archivo, esquema in (("producto.ejemplo.json", "producto"), ("qa-d4.ejemplo.json", "qa")):
            with self.subTest(archivo):
                self.assertEqual([e.message for e in errores_de_esquema(esquema, c.cargar_json(self.PLANTILLAS / archivo))], [])

    def test_plantillas_json_y_jsonl_son_validas(self):
        for p in sorted(self.PLANTILLAS.glob("*.json")):
            with self.subTest(p.name):
                c.cargar_json(p)
        for p in sorted(self.PLANTILLAS.rglob("*.jsonl")):
            with self.subTest(p.name):
                c.cargar_jsonl(p)

    def test_cotizacion_de_ejemplo_es_denegada_con_limites_null(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            escribir(tmp / "limites.yaml", "creditos_max_pieza: null\ncreditos_max_oferta: null\n")
            cod, res = correr(cotizar_creditos, ["--cotizacion", str(self.PLANTILLAS / "cotizacion_creditos.ejemplo.json"), "--limites", str(tmp / "limites.yaml"), "--raiz", str(tmp)])
            self.assertEqual(cod, 1)
            self.assertIn("limite-null", ids(res))


class PruebasLint(unittest.TestCase):
    def lint(self, texto: str, locale: str = "es-ES", extra: list[str] | None = None, nombre: str = "a.md"):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        p = escribir(Path(t.name) / nombre, texto)
        return correr(lint_contenido, ["--producto", str(p), "--locale", locale] + (extra or []))

    def test_limpio(self):
        cod, res = self.lint("Anota tus gastos de la semana en la tabla y suma cada columna. Revisa el total el domingo.")
        self.assertEqual(cod, 0, res)

    def test_sembrados_es(self):
        casos = {
            "placeholder": "Guía de [INSERTAR TEMA] para ti.",
            "claim-vetado": "Este método garantizado te cura la ansiedad.",
            "testimonio": "María perdió 8 kg con este plan.",
            "credencial-falsa": "Plan diseñado por nutricionistas expertos.",
            "servicio-oculto": "Incluye una sesión 1:1 de 30 minutos y acceso al grupo privado.",
            "diagnostico": "Si tienes diabetes sigue este menú.",
            "frase-chatbot": "Claro, aquí tienes la guía que me pediste.",
            "marca-pendiente": "Dato de la fuente [VERIFICAR] pendiente.",
        }
        for patron, texto in casos.items():
            with self.subTest(patron):
                cod, res = self.lint(texto)
                self.assertEqual(cod, 1, res)
                self.assertIn(patron, ids(res))

    def test_campos_de_plantilla_y_todo_en_espanol_no_son_placeholders(self):
        cod, res = self.lint("Rellena [Nombre y apellidos] y [Fecha]. Revisa todo el documento antes de enviarlo.")
        self.assertEqual(cod, 0, res)
        cod, res = self.lint("Pendiente: TODO revisar esta sección.")
        self.assertIn("placeholder", ids(res, "MAYOR"))

    def test_nombre_de_enfermedad_no_aplica_aqui_pero_secreto_si(self):
        cod, res = self.lint("Clave: sk_live_abcdefghijklmnop1234 y ruta /Users/usuario/Digital")
        self.assertIn("secreto", ids(res, "BLOQUEANTE"))
        self.assertIn("ruta-personal", ids(res))

    def test_termino_vetado_en_cita_baja_a_menor(self):
        cod, res = self.lint("La fuente oficial dice: «los productos garantizados no existen en esta categoría» y lo citamos.")
        self.assertEqual(cod, 0, res)
        self.assertIn("claim-vetado", ids(res, "MENOR"))

    def test_sembrado_separador_de_miles_en_it(self):
        cod, res = self.lint("Aggiungi 1,500 g di farina e mescola per due minuti.", "it-IT")
        self.assertEqual(cod, 1)
        self.assertIn("separador-ajeno", ids(res, "BLOQUEANTE"))

    def test_sembrado_ayuda_de_otro_pais(self):
        cod, res = self.lint("Se hai bisogno di aiuto chiama la linea 988 gratuita.", "it-IT", ["--ayuda-numeros", "1522"])
        self.assertEqual(cod, 1)
        self.assertIn("ayuda-de-otro-pais", ids(res, "BLOQUEANTE"))

    def test_ayuda_del_pais_correcto_pasa(self):
        cod, res = self.lint("Se hai bisogno di aiuto chiama il 1522, numero gratuito.", "it-IT", ["--ayuda-numeros", "1522"])
        self.assertEqual(cod, 0, res)

    def test_literal_obligatorio_ausente(self):
        cod, res = self.lint("Tarjetas de conversación para parejas.", "es-ES", ["--requiere", "seguridad=Si temes por tu seguridad, no uses este material"])
        self.assertEqual(cod, 1)
        self.assertIn("literal-ausente", ids(res, "BLOQUEANTE"))
        cod, res = self.lint("Si temes por tu seguridad, no uses este material. Tarjetas.", "es-ES", ["--requiere", "seguridad=Si temes por tu seguridad, no uses este material"])
        self.assertEqual(cod, 0, res)

    def test_idioma_sin_lexico_avisa(self):
        cod, res = self.lint("Tekst w nieznanym języku.", "sv-SE")
        self.assertIn("idioma-sin-lexico", ids(res))

    def test_it_y_pl_vetadas(self):
        cod, res = self.lint("Questo metodo garantito ti guarisce.", "it-IT")
        self.assertIn("claim-vetado", ids(res, "BLOQUEANTE"))
        cod, res = self.lint("Ta metoda gwarantowana pozwoli wyleczyć wszystko.", "pl-PL")
        self.assertIn("claim-vetado", ids(res, "BLOQUEANTE"))


def xlsx_minimo(ruta: Path, hojas: list[tuple[str, str]], formulas: list[str], oculta: bool = False, macros: bool = False, enlaces: bool = False, fila_oculta: bool = False):
    sheets = "".join(f'<sheet name="{n}" sheetId="{i}" state="{"hidden" if (oculta and i == 2) else "visible"}" r:id="rId{i}"/>' for i, (n, _) in enumerate(hojas, 1))
    wb = f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'
    filas = "".join(f'<row r="{i}"{" hidden=\"1\"" if (fila_oculta and i == 1) else ""}><c r="A{i}"><f>{f}</f></c></row>' for i, f in enumerate(formulas, 1))
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        z.writestr("xl/workbook.xml", wb)
        for i, _ in enumerate(hojas, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{filas if i == 1 else ""}</sheetData></worksheet>')
        if macros:
            z.writestr("xl/vbaProject.bin", b"x")
        if enlaces:
            z.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")


class PruebasHoja(unittest.TestCase):
    def lint(self, **kw):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        p = Path(t.name) / "p-v1-plantilla.xlsx"
        xlsx_minimo(p, kw.pop("hojas", [("Presupuesto", "")]), kw.pop("formulas", ["SUM(B1:B5)"]), **kw)
        return correr(lint_hoja, ["--hoja", str(p)])

    def test_limpia(self):
        cod, res = self.lint()
        self.assertEqual(cod, 0, res)

    def test_sembrados(self):
        casos = [("hoja-oculta", dict(hojas=[("A", ""), ("Calculos", "")], oculta=True)), ("macros", dict(macros=True)), ("enlaces-externos", dict(enlaces=True)),
                 ("formula-externa", dict(formulas=['WEBSERVICE("https://x.invalid")'])), ("hoja-puntua-estado", dict(formulas=['IF(B1&gt;30,"Obeso","Normal")'])),
                 ("filas-ocultas", dict(fila_oculta=True))]
        for patron, kw in casos:
            with self.subTest(patron):
                cod, res = self.lint(**kw)
                self.assertEqual(cod, 1, res)
                self.assertIn(patron, ids(res))

    def test_no_zip(self):
        with tempfile.TemporaryDirectory() as t:
            p = escribir(Path(t) / "x.xlsx", "no soy un zip")
            cod, res = correr(lint_hoja, ["--hoja", str(p)])
            self.assertEqual(cod, 1)


class PruebasEmpaquetar(unittest.TestCase):
    def montar(self, tmp: Path, nombre: str = "guida-v1-guia.md", sha: str | None = None):
        p = producto_base()
        p["items"][0]["archivo"] = f"entregables/{nombre}"
        if sha:
            p["items"][0]["sha256"] = sha
        escribir(tmp / "04-producto" / "producto.json", json.dumps(p))
        escribir(tmp / "04-producto" / "entregables" / nombre, "# Guida\nContenuto.\n")
        return ["--oferta-dir", str(tmp), "--max-mb-pdf", "15", "--max-mb-paquete", "100"]

    def test_hash_desactualizado_y_actualizar(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t))
            cod, res = correr(empaquetar, args)
            self.assertEqual(cod, 1)
            self.assertIn("hash-desactualizado", ids(res, "BLOQUEANTE"))
            cod, res = correr(empaquetar, args + ["--actualizar"])
            self.assertEqual(cod, 0, res)
            cod, res = correr(empaquetar, args)
            self.assertEqual(cod, 0, res)
            nuevo = json.loads((Path(t) / "04-producto" / "producto.json").read_text(encoding="utf-8"))
            self.assertEqual(nuevo["items"][0]["sha256"], c.hash_archivo(Path(t) / "04-producto" / "entregables" / "guida-v1-guia.md"))

    def test_sembrado_nombre_con_enfermedad(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "menu-diabetes-v1-guia.md")
            cod, res = correr(empaquetar, args + ["--actualizar"])
            self.assertEqual(cod, 1)
            self.assertIn("nombre-sensible", ids(res, "BLOQUEANTE"))

    def test_nombre_no_neutro(self):
        with tempfile.TemporaryDirectory() as t:
            args = self.montar(Path(t), "Guía Final.md")
            cod, res = correr(empaquetar, args + ["--actualizar"])
            self.assertIn("nombre-no-neutro", ids(res))


class PruebasCreditos(unittest.TestCase):
    def montar(self, tmp: Path, limites: str, cot: dict, pausa: bool = False, infra: dict | None = "ok"):
        (tmp / "empresa" / "infra").mkdir(parents=True)
        escribir(tmp / "empresa" / "limites.yaml", limites)
        if infra == "ok":
            infra = {"semaforo": "VERDE", "valido_hasta": "2026-11-07T00:00:00Z"}
        if infra:
            escribir(tmp / "empresa" / "infra" / "estado.json", json.dumps(infra))
        if pausa:
            escribir(tmp / "empresa" / "PAUSA", "")
        escribir(tmp / "cot.json", json.dumps(cot))
        return ["--cotizacion", str(tmp / "cot.json"), "--limites", str(tmp / "empresa" / "limites.yaml"), "--raiz", str(tmp), "--ahora", "2026-11-06T10:00:00Z"]

    COT = {"permiso_dueno": True, "gastado_antes": 10, "piezas": [{"id": "p1", "creditos": 5}, {"id": "p2", "creditos": 5}]}

    def test_autoriza_dentro_de_topes(self):
        with tempfile.TemporaryDirectory() as t:
            cod, res = correr(cotizar_creditos, self.montar(Path(t), "creditos_max_pieza: 8\ncreditos_max_oferta: 30\n", self.COT))
            self.assertEqual(cod, 0, res)
            self.assertEqual(res["resumen"]["margen_oferta"], 10)

    def test_limite_null_es_solo_texto(self):
        with tempfile.TemporaryDirectory() as t:
            cod, res = correr(cotizar_creditos, self.montar(Path(t), "creditos_max_pieza: null\ncreditos_max_oferta: null\n", self.COT))
            self.assertEqual(cod, 1)
            self.assertIn("limite-null", ids(res))

    def test_excede_pieza_y_oferta(self):
        with tempfile.TemporaryDirectory() as t:
            cot = dict(self.COT, piezas=[{"id": "p1", "creditos": 9}], gastado_antes=25)
            cod, res = correr(cotizar_creditos, self.montar(Path(t), "creditos_max_pieza: 8\ncreditos_max_oferta: 30\n", cot))
            self.assertIn("excede-pieza", ids(res))
            self.assertIn("excede-oferta", ids(res))

    def test_sin_permiso_pausa_e_infra(self):
        with tempfile.TemporaryDirectory() as t:
            cot = {k: v for k, v in self.COT.items() if k != "permiso_dueno"}
            cod, res = correr(cotizar_creditos, self.montar(Path(t), "creditos_max_pieza: 8\ncreditos_max_oferta: 30\n", cot, pausa=True, infra={"semaforo": "AMARILLO", "valido_hasta": "2026-11-07T00:00:00Z"}))
            self.assertEqual(cod, 1)
            self.assertTrue({"sin-permiso", "pausa", "infra"} <= ids(res))

    def test_unlim_exige_permiso(self):
        with tempfile.TemporaryDirectory() as t:
            cot = dict(self.COT, use_unlim=True)
            cod, res = correr(cotizar_creditos, self.montar(Path(t), "creditos_max_pieza: 8\ncreditos_max_oferta: 30\n", cot))
            self.assertIn("unlim-sin-permiso", ids(res))


if __name__ == "__main__":
    unittest.main(verbosity=1)
