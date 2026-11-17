"""Pruebas de los validadores de D1 (v0.1.0) y arnés de los evals. Ejecutar desde la raíz del repositorio:

  .venv/bin/python -m unittest discover -s .claude/skills/d1-descubrimiento/scripts/tests -p "test_*.py" -v

Sin red y sin escribir en el repositorio (todo va a carpetas temporales). Cubre: los dorados pasan; cada sembrado detectable por código
dispara su check; la inyección en títulos, el piso del barrido, el preflight fail-closed y la corrida real 2026-11-06-a (si existe).
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parents[1]
RAIZ = SKILL.parents[2]
VALIDADOR = SKILL / "scripts" / "validar_candidatos.py"
PREFLIGHT = SKILL / "scripts" / "preflight.py"
DORADOS = SKILL / "evals" / "dorados"
SEMBRADOS = SKILL / "evals" / "sembrados"
SELLO = "sha256:7d3ce2d980bfa21a91cc915ed83068466ced5472d5307a473fd094b1c65f4e4d"
PYTHON = str(RAIZ / ".venv" / "bin" / "python") if (RAIZ / ".venv" / "bin" / "python").exists() else sys.executable


def cargar(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def correr(*args: str) -> tuple[int, dict]:
    r = subprocess.run([PYTHON, str(VALIDADOR), *args, "--json"], capture_output=True, text=True, cwd=RAIZ, check=False)
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f"salida no JSON ({r.returncode}): {r.stdout[:300]} {r.stderr[:300]}") from None


def puntero(doc, ruta: str):
    """Devuelve (contenedor, clave) de un puntero JSON simple (/a/0/b); '-' = anexar."""
    partes = [p for p in ruta.split("/") if p != ""]
    for p in partes[:-1]:
        doc = doc[int(p)] if isinstance(doc, list) else doc[p]
    return doc, partes[-1]


def aplicar(doc, op: dict):
    if op["op"] == "copy":
        origen, k = puntero(doc, op["desde"])
        valor = copy.deepcopy(origen[int(k)] if isinstance(origen, list) else origen[k])
        destino, k2 = puntero(doc, op["ruta"])
        destino.append(valor)
        return
    cont, k = puntero(doc, op["ruta"])
    if op["op"] == "replace":
        cont[int(k) if isinstance(cont, list) else k] = op["valor"]
    elif op["op"] == "append":
        cont[k].append(op["valor"])
    else:
        raise AssertionError(f"op desconocida {op['op']}")


def materializar(caso: dict, destino: Path, parche: list[dict] | None = None) -> dict:
    """Escribe la salida esperada de un dorado en `destino/01-descubrimiento/` aplicando el parche de un sembrado."""
    so = copy.deepcopy(caso["salida_esperada"])
    docs = {"candidatos": so.get("candidatos"), "riesgo_extendido": so.get("riesgo_extendido", {}), "modelado": so.get("modelado", {}),
            "barrido": caso.get("entrada", {}).get("candidatos_barrido")}
    for op in parche or []:
        en = op.get("en", "candidatos")
        if en == "informe_md":
            so["informe_md"] = so["informe_md"].replace(op["buscar"], op["valor"])
        elif en == "crudo":
            so["crudo"][op["ruta"]] = op["valor"]
        elif en in docs:
            aplicar(docs[en], op)
    d = destino / "01-descubrimiento"
    (d / "crudo").mkdir(parents=True, exist_ok=True)
    for op in parche or []:  # entradas que lee el QA además de los artefactos (registro de herramientas, estado, plan)
        if op.get("en") == "registro":
            (d / "registro.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in op["valor"]) + "\n", encoding="utf-8")
        elif op.get("en") == "estado_json":
            (destino / "estado.json").write_text(json.dumps(op["valor"], ensure_ascii=False), encoding="utf-8")
        elif op.get("en") == "plan_md":
            (d / "crudo" / "plan.md").write_text(op["valor"], encoding="utf-8")
    if docs["candidatos"] is not None:
        (d / "candidatos.json").write_text(json.dumps(docs["candidatos"], ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "informe.md").write_text(so.get("informe_md", ""), encoding="utf-8")
    for k, v in so.get("crudo", {}).items():
        (d / "crudo" / f"{k}.txt").write_text(v, encoding="utf-8")
    for k in ("riesgo_extendido", "modelado"):
        if docs[k]:
            (d / f"{k}.json").write_text(json.dumps(docs[k], ensure_ascii=False, indent=2), encoding="utf-8")
    return {"barrido": docs["barrido"]}


def args_validador(oferta: Path, extra: list[str] | None = None) -> list[str]:
    d = oferta / "01-descubrimiento"
    return ["candidatos", str(d / "candidatos.json"), "--oferta-dir", str(oferta), "--informe", str(d / "informe.md"), "--moneda-cobro", "USD", *(extra or [])]


class Dorados(unittest.TestCase):
    def test_los_dorados_con_candidatos_pasan(self):
        casos = [cargar(p) for p in sorted(DORADOS.glob("*.json"))]
        con = [c for c in casos if "candidatos" in c["salida_esperada"]]
        self.assertGreaterEqual(len(con), 5)
        for c in con:
            with self.subTest(caso=c["id"]), tempfile.TemporaryDirectory() as t:
                materializar(c, Path(t))
                extra = ["--sello-esperado", SELLO] if c["modo"] == "D" else []
                codigo, res = correr(*args_validador(Path(t), extra))
                self.assertEqual(codigo, 0, [h for h in res["hallazgos"] if h["severidad"] in ("BLOQUEANTE", "MAYOR")])

    def test_los_dorados_son_de_varios_macros_idiomas_y_modos(self):
        casos = [cargar(p) for p in sorted(DORADOS.glob("*.json")) if "candidatos" in cargar(p)["salida_esperada"]]
        locales = {c["salida_esperada"]["candidatos"]["mercado"]["locale"] for c in casos}
        macros = {x["macro_nicho"] for c in casos for x in c["salida_esperada"]["candidatos"]["candidatos"]}
        self.assertGreaterEqual(len(locales), 4)
        self.assertEqual(macros, {"dinero", "relaciones"})
        self.assertEqual({c["modo"] for c in casos}, {"A", "B", "C", "D"})

    def test_inyeccion_en_titulos_se_detecta_sin_eco(self):
        c = cargar(DORADOS / "g6-inyeccion-en-titulos-de-anuncios.json")
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "entrada.txt"
            ruta.write_text(c["entrada"]["material_pegado"], encoding="utf-8")
            r = subprocess.run([PYTHON, str(VALIDADOR), "entrada", str(ruta)], capture_output=True, text=True, cwd=RAIZ, check=False)
        self.assertEqual(r.returncode, 3)
        self.assertIn("línea 2", r.stdout)
        self.assertIn("línea 3", r.stdout)
        self.assertNotIn("línea 1", r.stdout)
        self.assertNotIn("ads_create_campaign", r.stdout)  # nunca repite la orden

    def test_regla_del_piso_en_el_dorado(self):
        c = cargar(DORADOS / "g7-nunca-descartar-por-un-conteo-piso.json")
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "barrido.json"
            ruta.write_text(json.dumps(c["entrada"]["candidatos_barrido"]), encoding="utf-8")
            codigo, res = correr("barrido", str(ruta))
        self.assertEqual(codigo, 0, res)

    def test_corrida_real_no_viola_la_regla_del_piso(self):
        real = RAIZ / "empresa" / "barrido" / "candidatos" / "2026-11-06-a.json"
        if not real.exists():
            self.skipTest("no está la corrida real")
        codigo, res = correr("barrido", str(real))
        self.assertEqual(codigo, 0, res)

    def test_g8_no_escribe_candidatos_cuando_todo_es_rojo(self):
        c = cargar(DORADOS / "g8-rojo-por-curacion-o-ingresos-garantizados.json")
        self.assertTrue(c["esperado"]["no_escribe_candidatos_json"])
        self.assertNotIn("candidatos", c["salida_esperada"])


class Sembrados(unittest.TestCase):
    def test_cada_sembrado_detectable_por_codigo_dispara_su_check(self):
        n = 0
        for p in sorted(SEMBRADOS.glob("*.json")):
            s = cargar(p)
            if s["deteccion"] not in ("script", "script_lint"):
                continue
            base = cargar(DORADOS / f"{s['base']}.json")
            with self.subTest(sembrado=s["id"]), tempfile.TemporaryDirectory() as t:
                if s["comando"] == "barrido":
                    datos = materializar(base, Path(t), s["parche"])["barrido"]
                    ruta = Path(t) / "barrido.json"
                    ruta.write_text(json.dumps(datos), encoding="utf-8")
                    codigo, res = correr("barrido", str(ruta))
                else:
                    materializar(base, Path(t), s["parche"])
                    extra = list(s["extra_args"])
                    if base["modo"] == "D" and "--sello-esperado" not in extra:
                        extra += ["--sello-esperado", SELLO]
                    codigo, res = correr(*args_validador(Path(t), extra))
                hit = [h for h in res["hallazgos"] if h["check"] == s["check_esperado"] and h["severidad"] == s["severidad_esperada"]]
                self.assertTrue(hit, f"{s['id']}: esperaba {s['check_esperado']} {s['severidad_esperada']}; hubo {[(h['check'], h['severidad']) for h in res['hallazgos']]}")
                self.assertEqual(codigo, 3)
            n += 1
        self.assertGreaterEqual(n, 20)

    def test_mas_del_90_por_ciento_de_las_estrellas_son_detectables_o_de_lectura_declarada(self):
        todos = [cargar(p) for p in sorted(SEMBRADOS.glob("*.json"))]
        estrellas = [s for s in todos if s["estrella"]]
        self.assertGreaterEqual(len(estrellas), 18)
        for s in todos:
            self.assertIn(s["deteccion"], ("script", "script_lint", "qa_lectura", "qa_registro"))
            self.assertTrue((DORADOS / f"{s['base']}.json").exists(), s["id"])

    def test_los_ids_de_sembrados_son_unicos_y_los_parches_aplican_sobre_la_base(self):
        ids = set()
        for p in sorted(SEMBRADOS.glob("*.json")):
            s = cargar(p)
            self.assertNotIn(s["id"], ids)
            ids.add(s["id"])
            base = cargar(DORADOS / f"{s['base']}.json")
            with tempfile.TemporaryDirectory() as t:
                materializar(base, Path(t), s["parche"])  # no debe lanzar


class Sellado(unittest.TestCase):
    def test_sellar_completa_hashes_y_senales_y_el_resultado_valida(self):
        caso = cargar(DORADOS / "g2-dinero-es-ar-manualidades-costeo-sin-promesa.json")
        with tempfile.TemporaryDirectory() as t:
            oferta = Path(t)
            materializar(caso, oferta)
            d = oferta / "01-descubrimiento"
            original = cargar(d / "candidatos.json")
            borrador = copy.deepcopy(original)
            for e in borrador["candidatos"][0]["evidencia"]:
                e["hash_copia_crudo"] = "sha256:" + "0" * 64
            borrador["candidatos"][0]["mecanismo"]["causa_raiz"]["senales"] = ["000000000001", "000000000002"]
            ext = cargar(d / "riesgo_extendido.json")
            ext["candidatos"]["CAND-01"]["senal_id_e3"] = "000000000001"
            (d / "riesgo_extendido.json").write_text(json.dumps(ext), encoding="utf-8")
            (d / "candidatos.json").write_text(json.dumps(borrador), encoding="utf-8")
            codigo, res = correr(*args_validador(oferta))
            self.assertEqual(codigo, 3)  # sin sellar no pasa
            self.assertTrue(any("sin sellar" in h["mensaje"] for h in res["hallazgos"]))
            r = subprocess.run([PYTHON, str(VALIDADOR), "sellar", str(d / "candidatos.json"), "--oferta-dir", str(oferta), "--escribir"],
                               capture_output=True, text=True, cwd=RAIZ, check=False)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            sellado = cargar(d / "candidatos.json")
            self.assertEqual(sellado["candidatos"][0]["evidencia"], original["candidatos"][0]["evidencia"])
            self.assertEqual(sellado["candidatos"][0]["mecanismo"]["causa_raiz"]["senales"], original["candidatos"][0]["mecanismo"]["causa_raiz"]["senales"])
            codigo, res = correr(*args_validador(oferta))
            self.assertEqual(codigo, 0, [h for h in res["hallazgos"] if h["severidad"] in ("BLOQUEANTE", "MAYOR")])

    def test_sellar_sin_escribir_no_toca_el_archivo(self):
        caso = cargar(DORADOS / "g2-dinero-es-ar-manualidades-costeo-sin-promesa.json")
        with tempfile.TemporaryDirectory() as t:
            oferta = Path(t)
            materializar(caso, oferta)
            ruta = oferta / "01-descubrimiento" / "candidatos.json"
            antes = ruta.read_bytes()
            subprocess.run([PYTHON, str(VALIDADOR), "sellar", str(ruta), "--oferta-dir", str(oferta)], capture_output=True, text=True, cwd=RAIZ, check=False)
            self.assertEqual(ruta.read_bytes(), antes)


class Plantillas(unittest.TestCase):
    def test_la_plantilla_de_candidatos_valida(self):
        T = SKILL / "templates"
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "01-descubrimiento"
            (d / "crudo").mkdir(parents=True)
            for f in (T / "crudo").glob("*.txt"):
                (d / "crudo" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            (d / "candidatos.json").write_text((T / "candidatos.json").read_text(encoding="utf-8"), encoding="utf-8")
            (d / "riesgo_extendido.json").write_text((T / "riesgo_extendido.json").read_text(encoding="utf-8"), encoding="utf-8")
            (d / "informe.md").write_text("# informe de prueba\n", encoding="utf-8")
            codigo, res = correr("candidatos", str(d / "candidatos.json"), "--oferta-dir", t, "--informe", str(d / "informe.md"), "--moneda-cobro", "USD")
        self.assertEqual(codigo, 0, [h for h in res["hallazgos"] if h["severidad"] in ("BLOQUEANTE", "MAYOR")])

    def test_los_json_de_las_plantillas_son_validos(self):
        for f in (SKILL / "templates").glob("*.json"):
            with self.subTest(f=f.name):
                json.loads(f.read_text(encoding="utf-8"))

    def test_la_ficha_de_ejemplo_pasa_puntaje_modelar_con_el_sello_aprobado(self):
        r = subprocess.run([PYTHON, "-m", "scripts.modelado.puntaje_modelar", "puntuar", str(SKILL / "templates" / "ficha_modo_d.ejemplo.json"),
                            "--parametros", str(RAIZ / "scripts" / "modelado" / "parametros_modelado.propuesta.yaml"),
                            "--sello-esperado", SELLO, "--json"], capture_output=True, text=True, cwd=RAIZ, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        par = json.loads(r.stdout)["pares"][0]
        self.assertEqual(par["estado"], "pasa")
        self.assertEqual(par["PM"], "69.32")


class MapearIntegracion(unittest.TestCase):
    """`ficha_a_candidato mapear` (S-B) sobre la plantilla de pares: el resultado coincide con el cálculo independiente del dorado g4."""

    def test_mapear_da_el_mismo_candidato_y_el_l1_exige_lo_que_mapear_deja_vacio(self):
        if not (RAIZ / "scripts" / "descubrimiento" / "ficha_a_candidato.py").exists():
            self.skipTest("ficha_a_candidato.py no existe todavía [PENDIENTE: S-B]")
        import yaml
        prop = yaml.safe_load((RAIZ / "scripts" / "modelado" / "parametros_modelado.propuesta.yaml").read_text(encoding="utf-8"))
        base = yaml.safe_load((RAIZ / "empresa" / "parametros.yaml").read_text(encoding="utf-8"))
        prop["grupos"]["descubrimiento"]["sim_dup_bloqueo"] = base["grupos"]["descubrimiento"]["sim_dup_bloqueo"]
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "p.yaml").write_text(yaml.safe_dump(prop, allow_unicode=True), encoding="utf-8")
            r = subprocess.run([PYTHON, "-m", "scripts.descubrimiento.ficha_a_candidato", "mapear", str(SKILL / "templates" / "pares.ejemplo.json"),
                                "--parametros", str(tmp / "p.yaml"), "--oferta-id", "OF-202611-05", "--corrida-id", "RUN-20261106-04",
                                "--locale", "es-MX", "--paises", "MX", "--salida", str(tmp / "candidatos.json"), "--aplicar", "--json"],
                               capture_output=True, text=True, cwd=RAIZ, check=False)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout)["conteos"]["pasa"], 1)
            c = cargar(tmp / "candidatos.json")["candidatos"][0]
            dorado = cargar(DORADOS / "g4-dinero-es-mx-modo-d-planner-por-cobro.json")["salida_esperada"]["candidatos"]["candidatos"][0]
            self.assertEqual((c["score_base"], c["score_ajustado"], c["confianza"]), (dorado["score_base"], dorado["score_ajustado"], dorado["confianza"]))
            codigo, res = correr("candidatos", str(tmp / "candidatos.json"), "--sello-esperado", SELLO)
            falta = {h["check"] for h in res["hallazgos"] if h["severidad"] == "BLOQUEANTE"}
            self.assertEqual(codigo, 3)
            # Tras D1d (S-B, 2026-11-06) el mapeo ya deja resuelto D-02; el Maker aún completa a mano D-04, D-07 y D-11.
            self.assertTrue({"D-04", "D-07", "D-11"} <= falta, falta)
            self.assertNotIn("D-02", falta, falta)


class Hojas(unittest.TestCase):
    def test_una_hoja_que_no_existe_en_la_propuesta_es_mayor_y_los_dorados_usan_hojas_reales(self):
        caso = cargar(DORADOS / "g2-dinero-es-ar-manualidades-costeo-sin-promesa.json")
        with tempfile.TemporaryDirectory() as t:
            materializar(caso, Path(t), [{"en": "candidatos", "op": "replace", "ruta": "/candidatos/0/microsegmento", "valor": "hoja-inventada"}])
            codigo, res = correr(*args_validador(Path(t)))
        self.assertEqual(codigo, 3)
        self.assertTrue(any(h["check"] == "D-12" and h["severidad"] == "MAYOR" and "nichos.yaml" in h["mensaje"] for h in res["hallazgos"]))


class Preflight(unittest.TestCase):
    def _corre(self, raiz: Path, *extra):
        r = subprocess.run([PYTHON, str(PREFLIGHT), "--raiz", str(raiz), "--json", *extra], capture_output=True, text=True, cwd=RAIZ, check=False)
        return r.returncode, json.loads(r.stdout)

    def test_con_limites_en_null_bloquea_y_no_consulta(self):
        with tempfile.TemporaryDirectory() as t:
            raiz = Path(t)
            (raiz / "empresa").mkdir()
            (raiz / "empresa" / "limites.yaml").write_text((RAIZ / "empresa" / "limites.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            (raiz / "empresa" / "parametros.yaml").write_text((RAIZ / "empresa" / "parametros.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            codigo, res = self._corre(raiz, "--locale", "es-MX")
        self.assertEqual(codigo, 5)
        self.assertFalse(res["puede_seguir"])
        self.assertTrue(any(c["id"] == "P-02" and c["estado"] == "BLOQUEA" for c in res["checks"]))

    def test_pausa_bloquea(self):
        with tempfile.TemporaryDirectory() as t:
            raiz = Path(t)
            (raiz / "empresa").mkdir()
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            codigo, res = self._corre(raiz)
        self.assertEqual(codigo, 5)
        self.assertTrue(any(c["id"] == "P-01" and c["estado"] == "BLOQUEA" for c in res["checks"]))

    def test_el_freno_se_informa_pero_no_se_toca(self):
        with tempfile.TemporaryDirectory() as t:
            raiz = Path(t)
            (raiz / "empresa" / "captura").mkdir(parents=True)
            freno = raiz / "empresa" / "captura" / "freno.json"
            freno.write_text(json.dumps({"ts": "2026-11-06T06:03:43Z", "motivo": "HTTP 403 (Document)"}), encoding="utf-8")
            _, res = self._corre(raiz)
            self.assertTrue(freno.exists())  # el preflight jamás lo borra
        self.assertTrue(any(c["id"] == "P-04" and "FRENO" in c["detalle"] for c in res["checks"]))


class Entrada(unittest.TestCase):
    def test_correo_arroba_y_extracto_largo(self):
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "e.txt"
            ruta.write_text("Escríbeme a ana.perez@ejemplo.com\nHabla con @ana_perez_22 por favor\n«" + " ".join(["palabra"] * 30) + "»\nTexto neutro de una línea\n", encoding="utf-8")
            r = subprocess.run([PYTHON, str(VALIDADOR), "entrada", str(ruta)], capture_output=True, text=True, cwd=RAIZ, check=False)
        self.assertEqual(r.returncode, 3)
        self.assertNotIn("ana.perez@", r.stdout)
        self.assertIn("línea 1", r.stdout)
        self.assertIn("línea 2", r.stdout)
        self.assertIn("línea 3", r.stdout)
        self.assertNotIn("línea 4", r.stdout)


if __name__ == "__main__":
    unittest.main()
