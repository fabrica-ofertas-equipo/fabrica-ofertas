"""Pruebas de scripts/lanzar_hijos.py: los candados de los hijos de Claude.

Nunca se lanza un hijo real ni se usa red: `ejecutar_hijo` se reemplaza por un falso y `socket` está bloqueado.
Lo que importa aquí es que el comando lleve SIEMPRE los candados que impiden el acceso a los conectores con escritura.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import lanzar_hijos as lh

RAIZ = Path("/Users/prueba/Proyecto")


class Base(unittest.TestCase):
    def setUp(self):
        parche = mock.patch("socket.socket", side_effect=AssertionError("las pruebas no usan red"))
        parche.start()
        self.addCleanup(parche.stop)


class PruebaComando(Base):
    def cmd(self, **extra):
        return lh.construir_comando(RAIZ, {"id": "X", "editar": ["engine/**"], **extra})

    def test_lleva_todos_los_candados_contra_los_conectores(self):
        c = self.cmd()
        self.assertIn("--strict-mcp-config", c)
        self.assertEqual(c[c.index("--disallowedTools") + 1], "mcp__*")
        ajustes = json.loads(c[c.index("--settings") + 1])
        self.assertEqual(ajustes, {"disableClaudeAiConnectors": True})
        self.assertEqual(c[c.index("--tools") + 1], "Read,Write,Edit,Glob,Grep,Bash")

    def test_modo_dontask_y_nunca_se_salta_permisos(self):
        c = " ".join(self.cmd())
        self.assertIn("--permission-mode dontAsk", c)
        for prohibido in ("bypassPermissions", "dangerously-skip-permissions", "--bare", "--mcp-config"):
            self.assertNotIn(prohibido, c)

    def test_lee_solo_el_proyecto_y_escribe_solo_donde_se_le_dice(self):
        reglas = lh.reglas_permitidas(RAIZ, {"editar": ["engine/**", "tests/engine/**"]})
        self.assertIn("Read(//Users/prueba/Proyecto/**)", reglas)
        self.assertIn("Edit(engine/**)", reglas)
        self.assertIn("Edit(tests/engine/**)", reglas)
        self.assertEqual([r for r in reglas if r.startswith("Edit(")], ["Edit(engine/**)", "Edit(tests/engine/**)"])

    def test_sin_editar_el_hijo_es_de_solo_lectura(self):
        reglas = lh.reglas_permitidas(RAIZ, {"id": "V"})
        self.assertFalse([r for r in reglas if r.startswith(("Edit(", "Write("))])

    def test_bash_acotado_sin_curl_ni_git_ni_shell_libre(self):
        reglas = " ".join(lh.reglas_permitidas(RAIZ, {"editar": []}))
        for malo in ("curl", "git", "rm", "pip", "npm", "Bash(*)", "Bash(:*)"):
            self.assertNotIn(malo, reglas)
        self.assertIn("Bash(.venv/bin/python:*)", reglas)

    def test_topes_de_costo_y_turnos_siempre_presentes(self):
        c = self.cmd(max_usd=7, max_turnos=33)
        self.assertEqual(c[c.index("--max-budget-usd") + 1], "7")
        self.assertEqual(c[c.index("--max-turns") + 1], "33")
        c2 = lh.construir_comando(RAIZ, {"id": "Y"})
        self.assertIn("--max-budget-usd", c2)
        self.assertIn("--max-turns", c2)

    def test_el_prompt_no_va_en_los_argumentos(self):
        c = lh.construir_comando(RAIZ, {"id": "Z", "prompt_completo": "SECRETO-DEL-PROMPT"})
        self.assertNotIn("SECRETO-DEL-PROMPT", " ".join(c))


class PruebaVigilanciaDelArranque(Base):
    def test_un_hijo_con_herramientas_mcp_es_una_violacion(self):
        self.assertIn("MCP", lh.violacion_en_init({"tools": ["Read", "mcp__claude_ai_Meta_ADS__ads_activate_entity"]}))

    def test_un_hijo_con_servidores_mcp_es_una_violacion(self):
        self.assertIn("servidores", lh.violacion_en_init({"tools": ["Read"], "mcp_servers": [{"name": "x"}]}))

    def test_un_hijo_limpio_pasa(self):
        self.assertIsNone(lh.violacion_en_init({"tools": ["Bash", "Read", "Edit"], "mcp_servers": []}))
        self.assertIsNone(lh.violacion_en_init({}))


class PruebaInformes(Base):
    def test_extrae_el_json_del_informe_final(self):
        texto = 'Listo.\n{"archivos": ["a.py"], "pruebas": 3, "tests_pasan": true}\nfin'
        self.assertEqual(lh.extraer_json(texto)["pruebas"], 3)

    def test_sin_json_o_json_roto_devuelve_none(self):
        for texto in ("", "sin llaves", "{roto", "} al revés {"):
            self.assertIsNone(lh.extraer_json(texto))


class PruebaConfig(Base):
    def test_antepone_el_preambulo(self):
        t = lh.validar_config({"preambulo": "REGLAS", "trabajos": [{"id": "A", "prompt": "haz A"}]})
        self.assertTrue(t[0]["prompt_completo"].startswith("REGLAS"))
        self.assertTrue(t[0]["prompt_completo"].endswith("haz A"))

    def test_rechaza_configuraciones_invalidas(self):
        malas = [
            {}, {"trabajos": []}, {"trabajos": [{"prompt": "x"}]}, {"trabajos": [{"id": "A"}]},
            {"trabajos": [{"id": "A", "prompt": "x"}, {"id": "A", "prompt": "y"}]},
            {"trabajos": [{"id": "A", "prompt": "x", "depende_de": ["Z"]}]},
        ]
        for mala in malas:
            with self.subTest(mala=mala):
                with self.assertRaises(lh.ErrorConfig):
                    lh.validar_config(mala)

    def test_rechaza_rutas_de_escritura_peligrosas(self):
        for ruta in ("/etc/**", "../fuera/**", "a/../../b", "**", "*"):
            with self.subTest(ruta=ruta):
                with self.assertRaises(lh.ErrorConfig):
                    lh.validar_config({"trabajos": [{"id": "A", "prompt": "x", "editar": [ruta]}]})


class PruebaCorrida(Base):
    def corrida(self, trabajos, fake, concurrentes=3, tope=1000.0):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(lh, "ejecutar_hijo", fake), \
                mock.patch.object(lh.time, "sleep", lambda s: None):
            salida = Path(tmp)
            resumen = lh.correr(RAIZ, lh.validar_config({"trabajos": trabajos}), salida, concurrentes, tope)
            costos = (salida / "costos.jsonl").read_text(encoding="utf-8").splitlines() if (salida / "costos.jsonl").exists() else []
            return resumen, costos

    @staticmethod
    def hijo(estado="ok", costo=1.0):
        def fake(raiz, trabajo, salida):
            return {"id": trabajo["id"], "estado": estado, "costo_usd": costo, "turnos": 1, "informe": None, "texto": ""}
        return fake

    def test_corre_todo_y_suma_los_costos(self):
        resumen, costos = self.corrida([{"id": "A", "prompt": "x"}, {"id": "B", "prompt": "y"}], self.hijo(costo=2.5))
        self.assertEqual(resumen["gastado_usd"], 5.0)
        self.assertEqual({k: v["estado"] for k, v in resumen["resultados"].items()}, {"A": "ok", "B": "ok"})
        self.assertEqual(len(costos), 2)

    def test_respeta_las_dependencias(self):
        orden = []

        def fake(raiz, trabajo, salida):
            orden.append(trabajo["id"])
            return {"id": trabajo["id"], "estado": "ok", "costo_usd": 0.0, "turnos": 1}
        self.corrida([{"id": "C", "prompt": "x", "depende_de": ["B"]}, {"id": "B", "prompt": "x", "depende_de": ["A"]},
                      {"id": "A", "prompt": "x"}], fake)
        self.assertEqual(orden, ["A", "B", "C"])

    def test_si_falla_una_dependencia_el_dependiente_no_corre(self):
        def fake(raiz, trabajo, salida):
            ok = trabajo["id"] != "A"
            return {"id": trabajo["id"], "estado": "ok" if ok else "error", "costo_usd": 0.0, "turnos": 1}
        resumen, _ = self.corrida([{"id": "A", "prompt": "x"}, {"id": "B", "prompt": "x", "depende_de": ["A"]}], fake)
        self.assertEqual(resumen["resultados"]["A"]["estado"], "error")
        self.assertEqual(resumen["resultados"]["B"]["estado"], "OMITIDO_DEPENDENCIA")

    def test_al_alcanzar_el_tope_total_no_se_lanzan_mas_hijos(self):
        lanzados = []

        def fake(raiz, trabajo, salida):
            lanzados.append(trabajo["id"])
            return {"id": trabajo["id"], "estado": "ok", "costo_usd": 6.0, "turnos": 1}
        trabajos = [{"id": "A", "prompt": "x"}, {"id": "B", "prompt": "x", "depende_de": ["A"]},
                    {"id": "C", "prompt": "x", "depende_de": ["B"]}]
        resumen, _ = self.corrida(trabajos, fake, tope=10.0)
        self.assertEqual(lanzados, ["A", "B"])
        self.assertEqual(resumen["resultados"]["C"]["estado"], "OMITIDO_TOPE_TOTAL")
        self.assertEqual(resumen["gastado_usd"], 12.0)

    def test_no_supera_la_concurrencia_pedida(self):
        activos, maximo, cerrojo = [0], [0], threading.Lock()

        def fake(raiz, trabajo, salida):
            with cerrojo:
                activos[0] += 1
                maximo[0] = max(maximo[0], activos[0])
            threading.Event().wait(0.05)
            with cerrojo:
                activos[0] -= 1
            return {"id": trabajo["id"], "estado": "ok", "costo_usd": 0.0, "turnos": 1}
        self.corrida([{"id": f"T{i}", "prompt": "x"} for i in range(8)], fake, concurrentes=2)
        self.assertLessEqual(maximo[0], 2)
        self.assertGreaterEqual(maximo[0], 1)

    def test_una_violacion_de_mcp_cuenta_como_fallo(self):
        resumen, _ = self.corrida([{"id": "A", "prompt": "x"}], self.hijo(estado="VIOLACION_MCP"))
        self.assertEqual(resumen["resultados"]["A"]["estado"], "VIOLACION_MCP")


class PruebaReintentos(Base):
    def test_son_pasajeros_la_red_la_api_y_la_sesion_caida_a_cualquier_altura(self):
        pasajero = {"estado": "error", "turnos": 2, "texto": "API Error: Connection closed mid-response."}
        self.assertTrue(lh.es_transitorio(pasajero))
        self.assertTrue(lh.es_transitorio({**pasajero, "turnos": 60}))               # se cortó a mitad: se reanuda
        self.assertTrue(lh.es_transitorio({"estado": "error", "turnos": 23, "texto": "Not logged in · Please run /login"}))
        self.assertFalse(lh.es_transitorio({"estado": "error", "turnos": 100, "texto": "Reached max turns"}))
        self.assertFalse(lh.es_transitorio({**pasajero, "estado": "ok"}))
        self.assertFalse(lh.es_transitorio({**pasajero, "estado": "VIOLACION_MCP"}))  # una violación NUNCA se reintenta
        self.assertFalse(lh.es_transitorio({"estado": "error", "turnos": 1, "texto": "permiso denegado"}))

    def ejecutar(self, secuencia, **trabajo):
        llamadas = []

        def fake(raiz, t, salida):
            llamadas.append(1)
            return dict(secuencia[min(len(llamadas), len(secuencia)) - 1])
        with mock.patch.object(lh, "ejecutar_hijo", fake), mock.patch.object(lh.time, "sleep", lambda s: None):
            r = lh.ejecutar_con_reintentos(RAIZ, {"id": "A", **trabajo}, Path("/tmp"))
        return r, len(llamadas)

    def test_reintenta_hasta_que_sale_bien_y_suma_los_costos(self):
        mal = {"estado": "error", "turnos": 1, "costo_usd": 0.2, "texto": "API Error: overloaded"}
        bien = {"estado": "ok", "turnos": 40, "costo_usd": 3.0, "texto": ""}
        r, n = self.ejecutar([mal, mal, bien])
        self.assertEqual((r["estado"], n, r["intentos"]), ("ok", 3, 3))
        self.assertAlmostEqual(r["costo_usd"], 3.4)

    def test_respeta_el_maximo_de_reintentos(self):
        mal = {"estado": "error", "turnos": 1, "costo_usd": 0.1, "texto": "API Error: Connection closed"}
        r, n = self.ejecutar([mal], reintentos=1)
        self.assertEqual((r["estado"], n), ("error", 2))

    def test_el_reintento_avisa_que_es_una_reanudacion_sin_acumular_notas(self):
        prompts = []

        def fake(raiz, t, salida):
            prompts.append(t["prompt_completo"])
            return {"estado": "error" if len(prompts) < 3 else "ok", "turnos": 9, "costo_usd": 0.1,
                    "texto": "Not logged in · Please run /login"}
        with mock.patch.object(lh, "ejecutar_hijo", fake), mock.patch.object(lh.time, "sleep", lambda s: None):
            lh.ejecutar_con_reintentos(RAIZ, {"id": "A", "prompt_completo": "HAZ A"}, Path("/tmp"))
        self.assertEqual(prompts[0], "HAZ A")
        self.assertEqual(prompts[1].count("NOTA DE REANUDACIÓN"), 1)
        self.assertEqual(prompts[2].count("NOTA DE REANUDACIÓN"), 1)
        self.assertTrue(prompts[2].startswith("HAZ A"))

    def test_una_violacion_de_mcp_no_se_reintenta(self):
        r, n = self.ejecutar([{"estado": "VIOLACION_MCP", "turnos": 0, "costo_usd": 0.0, "texto": "MCP"}])
        self.assertEqual((r["estado"], n), ("VIOLACION_MCP", 1))


class PruebaCLI(Base):
    def ejecutar(self, *argv):
        salida, error = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(error):
            codigo = lh.main(list(argv))
        return codigo, salida.getvalue(), error.getvalue()

    def test_carpeta_de_salida_existente_sale_con_dos(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.json"
            cfg.write_text(json.dumps({"trabajos": [{"id": "A", "prompt": "x"}]}), encoding="utf-8")
            codigo, _, error = self.ejecutar(str(cfg), "--salida", tmp)
        self.assertEqual(codigo, 2)
        self.assertIn("ya existe", error)

    def test_configuracion_invalida_sale_con_tres(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.json"
            cfg.write_text(json.dumps({"trabajos": []}), encoding="utf-8")
            codigo, _, error = self.ejecutar(str(cfg), "--salida", str(Path(tmp) / "nueva"))
        self.assertEqual(codigo, 3)
        self.assertIn("configuración", error)

    def test_archivo_inexistente_sale_con_tres(self):
        codigo, _, _ = self.ejecutar("/no/existe.json", "--salida", "/tmp/no_se_crea_nunca_xyz")
        self.assertEqual(codigo, 3)


if __name__ == "__main__":
    unittest.main()
