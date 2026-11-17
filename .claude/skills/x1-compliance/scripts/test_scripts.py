"""Pruebas de los scripts de la skill x1-compliance. Correr desde la raíz del repositorio:

    .venv/bin/python -m unittest discover -s .claude/skills/x1-compliance/scripts -p "test_*.py"

Sin red ni escritura fuera de directorios temporales. Las pruebas que necesitan ``engine`` o PyYAML se saltan si no
están disponibles (``python3`` del sistema); con el ``.venv`` del proyecto corren todas.
"""
from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
RAIZ = AQUI.parents[3]
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ))

import _params  # noqa: E402
import correr_evals  # noqa: E402
import nivel_ejes  # noqa: E402
import ngrama_copia  # noqa: E402
import regla_salud  # noqa: E402

try:
    import yaml  # noqa: F401

    HAY_YAML = True
except ImportError:
    HAY_YAML = False
try:
    from engine import comun  # noqa: F401

    import validar_dictamen

    HAY_ENGINE = True
except ImportError:
    HAY_ENGINE = False


class NivelEjes(unittest.TestCase):
    def test_tabla(self):
        c = nivel_ejes.calcular
        self.assertEqual(c({"P": "P0", "C": "C1", "E": "E0", "N": "N1"})["veredicto_riesgo"], "pasa")
        self.assertEqual(c({"P": "P2n", "C": "C1", "E": "E0", "N": "N1"})["nivel"], "rojo")
        self.assertEqual(c({"P": "P3", "C": "C3", "E": "E2", "N": "N2"})["veredicto_riesgo"], "bloquea")
        self.assertEqual(c({"P": "P3", "C": "C2", "E": "E1", "N": "N1s"}, hay_reencuadre=True)["veredicto_riesgo"], "reformular")
        a = c({"P": "P0", "C": "C2", "E": "E0", "N": "N1"})
        self.assertEqual((a["nivel"], a["subnivel"], a["veredicto_riesgo"]), ("amarillo", "A", "pasa_con_revision"))
        self.assertEqual(c({"P": "P0", "C": "C2", "E": "E0", "N": "N1"}, zona_gris=True)["veredicto_riesgo"], "pasa_con_gate")
        b = c({"P": "P2s", "C": "C2", "E": "E0", "N": "N1"})
        self.assertEqual((b["subnivel"], b["veredicto_riesgo"]), ("B", "pasa_con_gate"))
        self.assertIsNone(c({"P": "P0", "C": "C0", "E": "E0", "N": "N0"}, fuera_de_macro=True)["nivel"])

    def test_errores(self):
        with self.assertRaises(ValueError):
            nivel_ejes.calcular({"P": "P9", "C": "C1", "E": "E0", "N": "N1"})
        with self.assertRaises(ValueError):  # N0 solo fuera de macro
            nivel_ejes.calcular({"P": "P0", "C": "C1", "E": "E0", "N": "N0"})

    @unittest.skipUnless(HAY_YAML and correr_evals.SUITE.is_file(), "sin PyYAML o sin la suite")
    def test_suite_completa_sin_discrepancias(self):
        self.assertEqual(nivel_ejes.verificar_suite(correr_evals.SUITE), [])


class ReglaSalud(unittest.TestCase):
    def test_series(self):
        self.assertEqual(regla_salud.correr_series(SKILL / "evals" / "salud" / "series.json"), [])

    def test_sin_parametro_no_decide(self):
        datos = json.loads((SKILL / "evals" / "salud" / "series.json").read_text(encoding="utf-8"))
        params = dict(datos["parametros"])
        params["rechazos_congelar"] = None
        with self.assertRaises(ValueError):
            regla_salud.decidir(datos["series"][0]["estado"], params)


class Ngrama(unittest.TestCase):
    def test_secuencia(self):
        a = ngrama_copia.palabras("Aprende a ordenar tus gastos mensuales, paso a paso.")
        b = ngrama_copia.palabras("Y aprende a ordenar tus gastos mensuales paso a paso con calma")
        self.assertEqual(len(ngrama_copia.secuencia_comun_mas_larga(a, b)), 9)

    def test_cli(self):
        f = SKILL / "evals" / "sembrados" / "fixtures"
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(ngrama_copia.main(["--propio", str(f / "s08-copy-propio.txt"), "--referencia", str(f / "s08-competidor.txt"), "--n", "8"]), 3)
            self.assertEqual(ngrama_copia.main(["--propio", str(f / "s08-copy-propio-limpio.txt"), "--referencia", str(f / "s08-competidor.txt"), "--n", "8"]), 0)


class Parametros(unittest.TestCase):
    def test_lee_y_no_inventa(self):
        if (RAIZ / "empresa" / "parametros.yaml").is_file():
            self.assertEqual(_params.leer_parametro("compliance", "ngrama_copia_palabras"), "8")
        self.assertIsNone(_params.leer_parametro("compliance", "no_existe"))
        self.assertIsNone(_params.leer_parametro("compliance", "x", ruta=Path("/no/existe.yaml")))


@unittest.skipUnless(HAY_ENGINE, "requiere el .venv del proyecto (engine)")
class ValidarDictamen(unittest.TestCase):
    def cargar(self, nombre):
        return json.loads((SKILL / "templates" / nombre).read_text(encoding="utf-8"))

    def test_plantillas_validas(self):
        for nombre in ("dictamen-fail-d6.json", "dictamen-pass-con-notas-d5.json"):
            errores, _ = validar_dictamen.validar(self.cargar(nombre), umbral="4.0")
            self.assertEqual(errores, [], nombre)

    def test_defectos_que_debe_rechazar(self):
        base = self.cargar("dictamen-pass-con-notas-d5.json")
        casos = {}
        d = copy.deepcopy(base); d["firma_motor"] = "hmac-sha256:" + "a" * 64; casos["firma del agente"] = d
        d = copy.deepcopy(base); d["semaforo"] = "rojo"; casos["rojo con PASS"] = d
        d = copy.deepcopy(base); d["hallazgos"][0].update(severidad="BLOQUEANTE", estado="abierto"); casos["PASS con bloqueante abierto"] = d
        d = copy.deepcopy(base); d["items"] = d["items"][:-1]; casos["falta un ítem R"] = d
        d = copy.deepcopy(base); d["items"][0]["puntaje"] = 2; casos["ítem < 3 con PASS"] = d
        d = copy.deepcopy(base); d["checks_l1"] = [c for c in d["checks_l1"] if "LINT" not in c["check_id"]]; casos["sin lint"] = d
        d = copy.deepcopy(base); d["x1"] = {"dictamen_ref": "qa/x1-d5-v1.json", "veredicto": "PASS", "artefacto_sha256": "sha256:" + "0" * 64}; casos["x1 no nulo"] = d
        d = copy.deepcopy(base); d["umbral"] = "3.0"; casos["umbral ≠ parámetro"] = d
        d = copy.deepcopy(base)
        for c in d["checks_l1"]:
            if c["check_id"] == "L1-NIVEL":
                c["detalle"] = "ejes asignados: P=P2n C=C1 E=E0 N=N1 -> rojo"
        casos["semáforo verde con ejes que dan rojo"] = d
        d = copy.deepcopy(self.cargar("dictamen-fail-d6.json")); d["checks_l1"] = [c for c in d["checks_l1"] if c["check_id"] != "L1-NIVEL"]; casos["D6 sin L1-NIVEL"] = d
        d = copy.deepcopy(base); d["etapa_objetivo"] = "D2"; d["checks_l1"] = [c for c in d["checks_l1"] if c["check_id"] != "L1-NIVEL"]; casos["D2 (consultivo) sin L1-NIVEL"] = d
        for nombre, d in casos.items():
            errores, _ = validar_dictamen.validar(d, umbral="4.0")
            self.assertTrue(errores, f"debía rechazar: {nombre}")

    def test_fail_sin_correccion_en_bloqueante(self):
        d = self.cargar("dictamen-fail-d6.json")
        d["hallazgos"][0].pop("correccion")
        errores, _ = validar_dictamen.validar(d, umbral="4.0")
        self.assertTrue(any("corrección segura" in e for e in errores))


class Convenciones(unittest.TestCase):
    """Convenciones de la ingesta (SC-1, SC-4, S-A): niveles lanzables en minúscula y agentes sin web ni parches del QA."""

    def test_nivel_lanzable_en_minuscula_con_guion(self):
        # contratos/comunes#nivel_lanzable: verde | amarillo-a | amarillo-b. «amarillo-A» (mayúscula) es un defecto.
        import re
        rx = re.compile(r"amarillo-[AB]\b", re.I)
        malos = []
        for ruta in list(SKILL.rglob("*")) + [RAIZ / ".claude" / "agents" / "x1-maker.md", RAIZ / ".claude" / "agents" / "x1-qa.md"]:
            if ruta.suffix not in (".md", ".json", ".yaml", ".py") or "__pycache__" in ruta.parts or ruta == Path(__file__):
                continue
            for n in rx.findall(ruta.read_text(encoding="utf-8")):
                if n not in ("amarillo-a", "amarillo-b"):
                    malos.append(f"{ruta.name}:{n}")
        self.assertEqual(malos, [])

    @unittest.skipUnless(HAY_YAML, "sin PyYAML")
    def test_plantillas_usan_el_enum_de_nivel_lanzable(self):
        permitido = {"verde", "amarillo-a", "amarillo-b"}
        m = yaml.safe_load((SKILL / "templates" / "matriz_pais_nivel.yaml").read_text(encoding="utf-8"))
        self.assertTrue(set(m["nivel_max_sin_gate"].values()) <= permitido)
        p = yaml.safe_load((SKILL / "templates" / "paises.yaml").read_text(encoding="utf-8"))
        usados = {v for v in _valores(p, "nivel_max_sin_gate")}
        self.assertTrue(usados and usados <= permitido, usados)

    def test_qa_solo_lectura_y_maker_sin_web_ni_mcp(self):
        qa = (RAIZ / ".claude" / "agents" / "x1-qa.md").read_text(encoding="utf-8")
        mk = (RAIZ / ".claude" / "agents" / "x1-maker.md").read_text(encoding="utf-8")
        self.assertIn("tools: Read, Grep, Glob\n", qa)
        tools_mk = [l for l in mk.splitlines() if l.startswith("tools:")][0]
        self.assertNotIn("Web", tools_mk)
        self.assertNotIn("mcp__", tools_mk)
        self.assertIn("WebFetch", [l for l in mk.splitlines() if l.startswith("disallowedTools:")][0])
        rub = (SKILL / "rubric.md").read_text(encoding="utf-8")
        for texto in (qa, rub):
            self.assertNotIn("corregir defectos", texto)
            self.assertNotIn("Puedes corregir", texto)
            self.assertNotIn("corregido_por_qa", texto)
        self.assertNotIn("corregido_por_qa", (SKILL / "templates" / "dictamen-pass-con-notas-d5.json").read_text(encoding="utf-8"))


def _valores(nodo, clave):
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if k == clave:
                yield v
            else:
                yield from _valores(v, clave)
    elif isinstance(nodo, list):
        for v in nodo:
            yield from _valores(v, clave)


@unittest.skipUnless(HAY_YAML and correr_evals.SUITE.is_file(), "sin PyYAML o sin la suite")
class CorredorSuite(unittest.TestCase):
    def respuestas_perfectas(self):
        return {c["id"]: {"ejes": c["ejes"], "macro": c["macro_nicho_esperado"],
                          **({"reformulado": {"ejes": c["ejes_reformulados"]}} if c.get("ejes_reformulados") else {})}
                for c in correr_evals._suite()}

    def correr(self, respuestas, incluir_rt=True):
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "r.json"
            ruta.write_text(json.dumps(respuestas), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                codigo = correr_evals.cmd_suite(ruta, incluir_rt)
            return codigo, buf.getvalue()

    def test_respuestas_perfectas(self):
        codigo, salida = self.correr(self.respuestas_perfectas())
        self.assertEqual(codigo, 0, salida)
        self.assertIn("FALSOS VERDES PELIGROSOS: 0", salida)

    def test_detecta_un_falso_verde(self):
        r = self.respuestas_perfectas()
        r["SAL-01"]["ejes"] = {"P": "P0", "C": "C1", "E": "E0", "N": "N1"}  # una «cura» clasificada verde
        codigo, salida = self.correr(r)
        self.assertEqual(codigo, 1)
        self.assertIn("FALSO VERDE PELIGROSO SAL-01", salida)

    def test_detecta_sobre_bloqueo(self):
        r = self.respuestas_perfectas()
        r["DIN-02"]["ejes"] = {"P": "P0", "C": "C1", "E": "E2", "N": "N1"}  # reinserción laboral subida a rojo por «madres»
        _, salida = self.correr(r)
        self.assertIn("sobre-bloqueo DIN-02", salida)

    def test_cota(self):
        self.assertAlmostEqual(correr_evals.cota_superior(63, 0), 3 / 63)
        self.assertLessEqual(correr_evals.cota_superior(63, 0), 0.05)
        self.assertGreater(correr_evals.cota_superior(40, 0), 0.05)
        self.assertIsNone(correr_evals.cota_superior(100, 1))

    def test_entrada_ciega_sin_etiquetas_ni_rt(self):
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "e.json"
            with redirect_stdout(io.StringIO()):
                correr_evals.cmd_suite_entrada(ruta, incluir_rt=False)
            entrada = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(len(entrada), 200)
        self.assertFalse(any(i["id"].startswith("RT-") for i in entrada))
        self.assertEqual(set(entrada[0]), {"id", "idea", "idioma"})


class Estructura(unittest.TestCase):
    def test_evals_bien_formados(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(correr_evals.cmd_estructura(), 0)


if __name__ == "__main__":
    unittest.main()
