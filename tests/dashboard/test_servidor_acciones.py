"""Consola de acciones de lista blanca: cargador, validación de argumentos y ejecutor de trabajos."""
from __future__ import annotations

import os
import re
import time
import unittest
from pathlib import Path
from unittest import mock

import yaml

from dashboard.acciones import TOPE_SALIDA, cargar_lista_blanca
from tests.dashboard.test_servidor_apoyo import FIXTURES, PruebaBase, RAIZ_REPO

SECRETOS = {"STRIPE_WEBHOOK_SECRET": "whsec_no", "META_TOKEN_OPERADOR": "EAAno", "INGEST_HMAC_SECRET": "hmac_no",
            "ANTHROPIC_API_KEY": "sk-no", "PREFLIGHT_HMAC_KEY": "pf_no", "AWS_SECRET_ACCESS_KEY": "aws_no", "HOME": "/home/no"}


class PruebaListaBlanca(unittest.TestCase):
    def cargar(self, ruta: Path, raiz: Path = Path("/nada")):
        return cargar_lista_blanca(ruta, raiz)

    def test_la_lista_de_prueba_acepta_las_validas_y_rechaza_las_peligrosas(self) -> None:
        lista = self.cargar(FIXTURES / "acciones_prueba.yaml")
        self.assertEqual(set(lista.acciones), {"eco", "con_bandera", "dormir", "lento_corto", "inundar", "falla", "entorno", "donde",
                                               "oferta_existente", "pronto"})
        rechazadas = {r["id"]: r["motivos"] for r in lista.rechazadas}
        self.assertEqual(set(rechazadas), {"mala_live", "mala_texto_libre", "mala_activar", "mala_meta", "mala_riesgo", "mala_sin_python"})
        self.assertTrue(any("--live" in m for m in rechazadas["mala_live"]))
        self.assertTrue(any("texto libre" in m for m in rechazadas["mala_texto_libre"]))
        self.assertTrue(lista.acciones["pronto"].proximamente)
        self.assertIn("landing/validar.py", lista.acciones["pronto"].motivo)

    def test_lista_real_solo_lecturas_sin_live_ni_escritura(self) -> None:
        lista = self.cargar(RAIZ_REPO / "dashboard" / "acciones.yaml", RAIZ_REPO)
        self.assertEqual(lista.rechazadas, [])
        self.assertEqual(lista.avisos, [])
        ids = set(lista.acciones)
        self.assertGreaterEqual(ids, {"barrido_estado", "barrido_plan_ver", "barrido_rankear", "barrido_fichas", "validar_esquemas",
                                      "pruebas_paquete", "landing_validar", "landing_generar"})
        for a in lista.acciones.values():
            self.assertEqual(a.riesgo, "lectura", a.id)
            texto = " ".join(a.argv)
            for prohibido in ("--live", "--escribir", "activar", "publicar", "reembolsar", "gastar", "firmar", "PAUSA", "freno"):
                self.assertNotIn(prohibido, texto, f"{a.id}: {prohibido}")
            self.assertFalse(re.search(r"(^| )meta[./ ]", texto), a.id)
            for p in a.parametros.values():
                self.assertIn(p["tipo"], ("corrida", "oferta", "entero", "eleccion", "bandera"), "sin texto libre")
        self.assertTrue(lista.acciones["landing_generar"].proximamente, "generar siempre escribe: queda como «próximamente»")
        self.assertFalse(lista.acciones["landing_generar"].argv)

    def test_la_lista_real_declara_barrido_sin_escribir(self) -> None:
        crudo = yaml.safe_load((RAIZ_REPO / "dashboard" / "acciones.yaml").read_text(encoding="utf-8"))
        for a in crudo["acciones"]:
            self.assertEqual(a["riesgo"], "lectura")

    def test_cargador_tolera_yaml_ausente_corrupto_y_con_alias(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertTrue(self.cargar(d / "no.yaml").avisos)
            (d / "mal.yaml").write_text("a: [1, 2")
            self.assertTrue(self.cargar(d / "mal.yaml").avisos)
            (d / "alias.yaml").write_text("acciones: &a [1]\notro: *a\n")
            self.assertTrue(self.cargar(d / "alias.yaml").avisos)
            (d / "forma.yaml").write_text("acciones: 5\n")
            self.assertTrue(self.cargar(d / "forma.yaml").avisos)
            (d / "dup.yaml").write_text("acciones:\n  - {id: uno, titulo: a, descripcion: b, riesgo: lectura, argv: ['{python}', '-c', 'pass']}\n"
                                        "  - {id: uno, titulo: a, descripcion: b, riesgo: lectura, argv: ['{python}', '-c', 'pass']}\n")
            lista = self.cargar(d / "dup.yaml")
            self.assertEqual(list(lista.acciones), ["uno"])
            self.assertEqual(lista.rechazadas[0]["motivos"], ["el nombre interno (id) está repetido"])

    def test_marcadores_y_parametros_se_validan(self) -> None:
        import tempfile
        casos = {
            "sin_declarar": "argv: ['{python}', '-c', 'pass', '{x}']",
            "sin_usar": "argv: ['{python}', '-c', 'pass']\n    parametros: {x: {tipo: entero, minimo: 0, maximo: 1}}",
            "entero_negativo": "argv: ['{python}', '-c', 'pass', '{x}']\n    parametros: {x: {tipo: entero, minimo: -5, maximo: 1}}",
            "eleccion_con_guion": "argv: ['{python}', '-c', 'pass', '{x}']\n    parametros: {x: {tipo: eleccion, valores: ['--live']}}",
            "bandera_peligrosa": "argv: ['{python}', '-c', 'pass', '{x}']\n    parametros: {x: {tipo: bandera, flag: '--live'}}",
            "bandera_embebida": "argv: ['{python}', '-c', 'pass', 'a{x}']\n    parametros: {x: {tipo: bandera, flag: '--ok'}}",
            "timeout_enorme": "timeout_s: 100000\n    argv: ['{python}', '-c', 'pass']",
            "sin_argv": "descripcion2: x",
            "reembolsar": "argv: ['{python}', '-m', 'postcompra.reembolsar']",
            "firmar": "argv: ['{python}', '-m', 'engine.orq', 'firmar']",
            "borrar_pausa": "argv: ['{python}', '-c', 'import os; os.remove(\"empresa/PAUSA\")']",
        }
        with tempfile.TemporaryDirectory() as d:
            for nombre, cuerpo in casos.items():
                ruta = Path(d) / f"{nombre}.yaml"
                ruta.write_text(f"acciones:\n  - id: caso\n    titulo: t\n    descripcion: d\n    riesgo: lectura\n    {cuerpo}\n")
                lista = self.cargar(ruta)
                self.assertNotIn("caso", lista.acciones, nombre)
                self.assertTrue(lista.rechazadas, nombre)


class PruebaEjecutor(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.c = self.cliente()

    def lanzar(self, accion: str, args: dict | None = None, **kw):
        cuerpo = {"id": accion}
        if args is not None:
            cuerpo["args"] = args
        return self.c.post("/api/accion", cuerpo, **kw)

    def esperar(self, job_id: str, desde: int = 0, limite: float = 20.0) -> dict:
        t = time.monotonic() + limite
        while time.monotonic() < t:
            d = self.c.get(f"/api/job/{job_id}", consulta=f"desde={desde}").datos
            if d["terminado"]:
                return d
            time.sleep(0.05)
        self.fail("el trabajo no terminó")

    # -- listado -----------------------------------------------------------------------------
    def test_listado_de_acciones(self) -> None:
        j = self.c.get("/api/acciones").json()
        d = j["datos"]
        ids = [a["id"] for a in d["acciones"]]
        self.assertIn("eco", ids)
        self.assertNotIn("mala_live", ids)
        self.assertEqual({r["id"] for r in d["rechazadas"]}, {"mala_live", "mala_texto_libre", "mala_activar", "mala_meta", "mala_riesgo", "mala_sin_python"})
        self.assertTrue(any("mala_live" in a and "rechazada" in a for a in j["avisos"]))
        eco = next(a for a in d["acciones"] if a["id"] == "eco")
        self.assertEqual((eco["riesgo"], eco["disponible"], eco["proximamente"]), ("lectura", True, False))
        self.assertEqual(eco["parametros"][0]["nombre"], "n")
        self.assertIn("<n>", eco["comando"])
        self.assertNotIn(os.path.realpath(self.raiz), eco["comando"])
        pronto = next(a for a in d["acciones"] if a["id"] == "pronto")
        self.assertEqual((pronto["proximamente"], pronto["disponible"]), (True, False))
        self.assertEqual(self.lanzar("pronto").estado, 400)

    # -- ejecución normal --------------------------------------------------------------------
    def test_ejecuta_y_entrega_la_salida_de_forma_incremental(self) -> None:
        r = self.lanzar("eco", {"n": 5})
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertEqual(set(d), {"job_id", "accion", "comando", "inicio"})
        fin = self.esperar(d["job_id"])
        self.assertEqual((fin["estado"], fin["codigo"], fin["salida"].strip()), ("ok", 0, "eco 5"))
        self.assertTrue(fin["terminado"])
        self.assertFalse(fin["truncado"])
        self.assertEqual(fin["tope_salida"], TOPE_SALIDA)
        resto = self.c.get(f"/api/job/{d['job_id']}", consulta=f"desde={fin['siguiente']}").datos
        self.assertEqual((resto["salida"], resto["desde"], resto["siguiente"]), ("", fin["siguiente"], fin["siguiente"]))
        medio = self.c.get(f"/api/job/{d['job_id']}", consulta="desde=2").datos
        self.assertEqual(medio["salida"], fin["salida"][2:])
        self.assertEqual(self.c.get(f"/api/job/{d['job_id']}", consulta="desde=99999").datos["salida"], "")

    def test_banderas_elecciones_y_valores_por_defecto(self) -> None:
        d = self.esperar(self.lanzar("con_bandera", {"corrida": "2026-11-06-a", "ruidoso": True}).datos["job_id"])
        self.assertEqual(d["salida"].strip(), "fijo-2026-11-06-a rapido --ruidoso")
        d = self.esperar(self.lanzar("con_bandera", {"corrida": "2026-11-06-a", "modo": "lento", "ruidoso": False}).datos["job_id"])
        self.assertEqual(d["salida"].strip(), "fijo-2026-11-06-a lento")

    def test_oferta_debe_existir(self) -> None:
        ok = self.esperar(self.lanzar("oferta_existente", {"oferta": "OF-202611-77"}).datos["job_id"])
        self.assertEqual(ok["salida"].strip(), "ofertas/OF-202611-77")
        for valor in ("OF-999999-99", "../empresa", "OF-202611-77/../..", "x"):
            self.assertEqual(self.lanzar("oferta_existente", {"oferta": valor}).estado, 400, valor)

    def test_codigo_de_salida_distinto_de_cero(self) -> None:
        d = self.esperar(self.lanzar("falla").datos["job_id"])
        self.assertEqual((d["estado"], d["codigo"], d["salida"].strip()), ("error", 3, "mal"))

    # -- argumentos inválidos ----------------------------------------------------------------
    def test_argumentos_invalidos_no_lanzan_ningun_proceso(self) -> None:
        marca = self.raiz / "marca-inyeccion"
        malos = [
            ("eco", {"n": "5"}), ("eco", {"n": True}), ("eco", {"n": 100}), ("eco", {"n": -1}), ("eco", {"n": 1.5}), ("eco", {}),
            ("eco", {"n": 1, "extra": 2}), ("eco", {"n": "1; touch marca"}), ("eco", {"n": ["1"]}), ("eco", {"n": None}),
            ("eco", "no-es-objeto"), ("eco", [1]),
            ("con_bandera", {"corrida": "--live"}), ("con_bandera", {"corrida": "2026-11-06-a; touch x"}), ("con_bandera", {"corrida": "$(touch x)"}),
            ("con_bandera", {"corrida": "2026-11-06-A"}), ("con_bandera", {"corrida": 20261106}), ("con_bandera", {"corrida": "2026-11-06-a\n"}),
            ("con_bandera", {"corrida": "2026-11-06-a", "modo": "--live"}), ("con_bandera", {"corrida": "2026-11-06-a", "modo": "otro"}),
            ("con_bandera", {"corrida": "2026-11-06-a", "ruidoso": "si"}), ("con_bandera", {"corrida": "2026-11-06-a", "ruidoso": 1}),
        ]
        with mock.patch("subprocess.Popen", side_effect=AssertionError("no debe lanzarse ningún proceso")):
            for accion, args in malos:
                r = self.lanzar(accion, args)
                self.assertEqual(r.estado, 400, (accion, args))
                self.assertEqual(r.json()["error"]["codigo"], "args_invalidos", (accion, args))
        self.assertFalse(marca.exists())

    def test_accion_fuera_de_la_lista(self) -> None:
        with mock.patch("subprocess.Popen", side_effect=AssertionError("no debe lanzarse ningún proceso")):
            for accion in ("rm", "mala_live", "mala_activar", "mala_texto_libre", "mala_meta", "../eco", "ECO", "", None, 5, ["eco"], {"id": "eco"}):
                r = self.c.post("/api/accion", {"id": accion})
                self.assertEqual((r.estado, r.json()["error"]["codigo"]), (404, "accion_no_permitida"), accion)
            r = self.c.post("/api/accion", {"args": {}})
            self.assertEqual(r.estado, 404)
            r = self.c.post("/api/accion", {"id": "eco", "args": {"n": 1}, "argv": ["rm", "-rf", "/"]})
            self.assertEqual((r.estado, r.json()["error"]["codigo"]), (400, "campo_no_permitido"))
            r = self.c.post("/api/accion", {"id": "eco", "args": {"n": 1}, "shell": True})
            self.assertEqual(r.estado, 400)

    # -- límites del ejecutor ----------------------------------------------------------------
    def test_timeout_mata_el_proceso(self) -> None:
        t0 = time.monotonic()
        d = self.esperar(self.lanzar("dormir").datos["job_id"])
        self.assertEqual(d["estado"], "timeout")
        self.assertLess(time.monotonic() - t0, 10, "debe morir al segundo, no a los 30 s del proceso")
        self.assertIsNotNone(d["codigo"])
        self.assertLess(d["codigo"], 0, "terminado por señal")

    def test_tope_de_salida_trunca_y_detiene(self) -> None:
        d = self.esperar(self.lanzar("inundar").datos["job_id"])
        self.assertEqual(d["estado"], "tope_salida")
        self.assertTrue(d["truncado"])
        self.assertLessEqual(len(d["salida"]), TOPE_SALIDA)
        self.assertGreater(len(d["salida"]), TOPE_SALIDA - 4096)

    def test_un_trabajo_a_la_vez_por_accion(self) -> None:
        primero = self.lanzar("lento_corto").datos["job_id"]
        r = self.lanzar("lento_corto")
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (409, "accion_en_curso"))
        self.assertEqual(r.json()["error"]["job_id"], primero)
        self.assertEqual(self.c.get("/api/acciones").datos["acciones"][[a["id"] for a in self.c.get("/api/acciones").datos["acciones"]].index("lento_corto")]["en_curso"], primero)
        otra = self.lanzar("eco", {"n": 1})
        self.assertEqual(otra.estado, 200, "otra acción sí puede correr a la vez")
        self.esperar(primero)
        self.assertEqual(self.lanzar("lento_corto").estado, 200, "terminado: puede volver a correr")

    def test_tope_de_trabajos_simultaneos(self) -> None:
        app = self.c.app
        app.ejecutor._max = 1
        self.lanzar("lento_corto")
        r = self.lanzar("eco", {"n": 1})
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (429, "demasiados_trabajos"))

    def test_cerrar_el_panel_termina_los_trabajos(self) -> None:
        job = self.lanzar("lento_corto").datos["job_id"]
        t0 = time.monotonic()
        self.c.app.cerrar()
        d = self.esperar(job)
        self.assertLess(time.monotonic() - t0, 3, "no espera los 3 s del proceso")
        self.assertNotEqual(d["estado"], "ok")
        self.assertEqual(self.lanzar("eco", {"n": 1}).estado, 503)

    def test_job_inexistente_y_desde_invalido(self) -> None:
        self.assertEqual(self.c.get("/api/job/inexistente").json()["error"]["codigo"], "job_no_encontrado")
        job = self.lanzar("eco", {"n": 1}).datos["job_id"]
        self.assertEqual(self.c.get(f"/api/job/{job}", consulta="desde=abc").estado, 400)
        self.assertEqual(self.c.get(f"/api/job/{job}", consulta="desde=-5").estado, 200)
        self.esperar(job)

    # -- cómo se lanza el proceso --------------------------------------------------------------
    def test_popen_sin_shell_en_la_raiz_con_entorno_minimo(self) -> None:
        import subprocess
        llamadas = []
        real = subprocess.Popen

        def espia(*a, **kw):
            llamadas.append((a, kw))
            return real(*a, **kw)

        with mock.patch.dict(os.environ, SECRETOS), mock.patch("subprocess.Popen", side_effect=espia):
            job = self.lanzar("entorno").datos["job_id"]
            d = self.esperar(job)
        (a, kw), = llamadas
        self.assertIsInstance(a[0], list)
        self.assertIs(kw["shell"], False)
        self.assertEqual(Path(kw["cwd"]), Path(os.path.realpath(self.raiz)))
        self.assertEqual(kw["stdin"], subprocess.DEVNULL)
        self.assertTrue(kw["start_new_session"])
        for nombre in SECRETOS:
            self.assertNotIn(nombre, kw["env"])
            self.assertNotIn(nombre, d["salida"], "el proceso hijo no ve ninguna clave")
        for valor in SECRETOS.values():
            self.assertNotIn(valor, d["salida"])
        permitidos = {"PATH", "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONDONTWRITEBYTECODE", "LC_ALL", "FABRICA_RAIZ", "FABRICA_ENTORNO"}
        self.assertLessEqual(set(kw["env"]), permitidos)
        self.assertEqual(kw["env"]["FABRICA_RAIZ"], os.path.realpath(self.raiz))

    def test_el_hijo_corre_en_la_raiz(self) -> None:
        d = self.esperar(self.lanzar("donde").datos["job_id"])
        lineas = d["salida"].split()
        # la raíz absoluta del proyecto nunca llega al navegador (CONTRATO §7.4): se muestra como «.»
        self.assertEqual(lineas, ["."] * 2)
        self.assertNotIn(os.path.realpath(self.raiz), d["salida"])

    def test_la_salida_no_filtra_rutas_absolutas_ni_partidas_entre_lecturas(self) -> None:
        from dashboard.acciones import Job
        accion = mock.Mock()
        accion.id = "x"
        raiz = "/Users/persona/Proyecto"
        job = Job("j", accion, "cmd", "ahora", ocultar=((raiz, "."), ("/Users/persona", "~")))
        # una ruta partida en dos «lecturas» y otra entera; también la carpeta personal
        for trozo in ("error en /Users/persona/Pro", "yecto/ofertas/a.json y ", "/Users/persona/otra cosa\n"):
            job.agregar(trozo)
        job.agregar("", final=True)
        salida = job.leer(0)["salida"]
        self.assertNotIn("/Users/persona", salida)
        self.assertIn("./ofertas/a.json", salida)
        self.assertIn("~/otra cosa", salida)
        # sin rutas a ocultar, la salida pasa tal cual
        j2 = Job("j2", accion, "cmd", "ahora")
        j2.agregar("hola /tmp/x\n")
        self.assertEqual(j2.leer(0)["salida"], "hola /tmp/x\n")

    def test_la_accion_queda_en_la_auditoria_de_empresa_panel(self) -> None:
        self.esperar(self.lanzar("eco", {"n": 7}).datos["job_id"])
        lineas = (self.raiz / "empresa" / "panel" / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
        import json
        registro = json.loads(lineas[-1])
        self.assertEqual((registro["evento"], registro["accion"], registro["args"], registro["origen"]), ("accion", "eco", {"n": 7}, "panel"))
        self.assertEqual(sorted(p.name for p in (self.raiz / "empresa" / "panel").iterdir()), ["auditoria.jsonl"])


if __name__ == "__main__":
    unittest.main()
