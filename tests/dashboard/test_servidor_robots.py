"""``GET /api/robots`` (#/robots, pestaña Registro): lectura saneada y de solo lectura de ``empresa/robots.yaml``.

Raíz temporal con fixtures (nunca ``empresa/`` ni ``ofertas/`` reales).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.robots import sombra as _sombra
from tests.dashboard.test_servidor_apoyo import AHORA, PruebaBase, reloj_fijo

ROBOTS_MINI = """\
robots:
  - id: R1
    nombre: Escalera
    cadencia: cada 30 min
    nivel: N2
    estado: vivo
    ultimo_latido: "2026-11-09T11:58:00Z"
  - id: R9
    nombre: Informe del día
    cadencia: "08:30"
"""


class PruebaRobots(PruebaBase):
    def test_sin_archivo_es_vacio_con_aviso_y_no_inventa(self) -> None:
        j = self.cliente().get("/api/robots").json()
        self.assertIs(j["ok"], True)
        self.assertIs(j["vacio"], True)
        self.assertEqual(j["datos"], {})
        self.assertEqual(j["fuente"], ["empresa/robots.yaml"])
        self.assertTrue(any("Todavía no existe el registro de robots" in a for a in j["avisos"]))

    def test_con_archivo_devuelve_su_contenido(self) -> None:
        self.escribir("empresa/robots.yaml", ROBOTS_MINI)
        j = self.cliente().get("/api/robots").json()
        self.assertIs(j["vacio"], False)
        robots = j["datos"]["robots"]
        self.assertEqual([r["id"] for r in robots], ["R1", "R9"])
        self.assertEqual(robots[0]["cadencia"], "cada 30 min")

    def test_yaml_corrupto_no_rompe_y_avisa(self) -> None:
        self.escribir("empresa/robots.yaml", "robots: [sin cerrar\n  - {")
        r = self.cliente().get("/api/robots")
        self.assertEqual(r.estado, 200)
        j = r.json()
        self.assertIs(j["vacio"], True)
        self.assertTrue(j["avisos"])

    def test_se_acota_cantidad_largo_y_profundidad(self) -> None:
        largo = "x" * 5000
        muchos = "\n".join(f"  - id: R{i}" for i in range(500))
        profundo = "a:\n" + "".join("  " * (n + 1) + f"n{n}:\n" for n in range(9)) + "  " * 10 + "fin: 1\n"
        self.escribir("empresa/robots.yaml", f"robots:\n{muchos}\nnota: {largo}\n{profundo}")
        d = self.cliente().get("/api/robots").json()["datos"]
        self.assertEqual(len(d["robots"]), 200, "tope de elementos")
        self.assertEqual(len(d["nota"]), 400, "tope de largo de texto")
        n = d["a"]
        for _ in range(9):
            if n is None:
                break
            n = list(n.values())[0] if isinstance(n, dict) else None
        self.assertIsNone(n, "más allá de la profundidad máxima no viaja nada")

    def test_solo_lectura_y_metodo_no_permitido(self) -> None:
        r = self.cliente().post("/api/robots", {})
        self.assertIn(r.estado, (400, 403, 404, 405))
        self.assertFalse((self.raiz / "empresa" / "robots.yaml").exists(), "el panel nunca crea el archivo")


def _t(texto: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))


class PruebaRobotsSombra(PruebaBase):
    """``GET /api/robots/sombra``: la foto REAL de los robots en sombra (se corren de verdad en una raíz temporal), saneada y con el vencimiento recalculado."""

    _fotos: dict[str, Path] = {}

    @classmethod
    def _foto(cls, programado: bool) -> Path:
        """Corre ``python -m scripts.robots.sombra ejecutar --todos --escribir`` sobre una raíz temporal (una vez por variante) y devuelve su ``empresa/robots``."""
        clave = "programado" if programado else "manual"
        if clave not in cls._fotos:
            raiz = Path(tempfile.mkdtemp(prefix="sombra-foto-"))
            (raiz / "empresa").mkdir()
            (raiz / "ofertas").mkdir()
            from tests.dashboard.test_servidor_apoyo import RAIZ_FIXTURE
            for nombre in ("parametros.yaml", "limites.yaml"):
                shutil.copy(RAIZ_FIXTURE / "empresa" / nombre, raiz / "empresa" / nombre)
            args = ["ejecutar", "--todos", "--escribir", "--raiz", str(raiz), "--ahora", "2026-11-09T11:30:00Z"] + (["--programado"] if programado else [])
            with mock.patch.dict(os.environ, {"TZ": "UTC"}), mock.patch("sys.stdout"):
                _sombra.main(args)
            cls._fotos[clave] = raiz / "empresa" / "robots"
        return cls._fotos[clave]

    @classmethod
    def tearDownClass(cls) -> None:
        for carpeta in cls._fotos.values():
            shutil.rmtree(carpeta.parent.parent, True)
        cls._fotos.clear()

    def poner_foto(self, programado: bool = True) -> None:
        shutil.copytree(self._foto(programado), self.raiz / "empresa" / "robots")

    def sombra(self, ahora: _dt.datetime = AHORA) -> dict:
        r = self.cliente(ahora=reloj_fijo(ahora)).get("/api/robots/sombra")
        self.assertEqual(r.estado, 200)
        return r.json()

    def test_sin_foto_es_vacio_con_el_comando_para_generarla_y_no_inventa(self) -> None:
        j = self.sombra()
        self.assertIs(j["ok"], True)
        self.assertIs(j["vacio"], True)
        self.assertEqual(j["datos"]["existe"], False)
        self.assertEqual(j["fuente"], ["empresa/robots/estado.json"])
        self.assertTrue(any("scripts.robots.sombra ejecutar --todos --escribir" in a for a in j["avisos"]))
        self.assertIn("programar", j["datos"]["comandos"])
        self.assertFalse((self.raiz / "empresa" / "robots").exists(), "el panel nunca crea la carpeta de robots")

    def test_foto_real_de_robots_programados_al_dia(self) -> None:
        self.poner_foto(True)
        j = self.sombra()
        d = j["datos"]
        self.assertIs(j["vacio"], False)
        self.assertEqual((d["existe"], d["situacion"], d["de_hoy"], d["edad_min"]), (True, "corriendo", True, 30))
        self.assertEqual([r["id"] for r in d["robots"]], ["escalera", "salvavidas", "guardia", "cola", "perfil", "alarma", "vigia", "bandeja", "informe", "auditor", "alertas", "baja_j3"])
        r = d["resumen"]
        self.assertEqual(r["con_sombra"], ["perfil", "alarma", "vigia", "informe", "auditor", "alertas", "baja_j3"])
        self.assertEqual(r["sin_version"], ["escalera", "salvavidas", "guardia", "cola", "bandeja"])
        self.assertEqual((r["vencidos"], r["faltan_hoy"]), ([], []))
        self.assertEqual(sorted(r["corrieron_hoy"]), sorted(r["con_sombra"]))
        perfil = {x["id"]: x for x in d["robots"]}["perfil"]
        self.assertEqual((perfil["ejecutor_hoy"], perfil["estado_latido"], perfil["ultimo_resultado"], perfil["edad_min"]), ("sombra", "al_dia", "sin_datos", 30))
        self.assertEqual({x["id"]: x for x in d["robots"]}["escalera"]["estado_latido"], "no_aplica")
        self.assertEqual({x["id"]: x for x in d["robots"]}["alertas"]["ultimo_resultado"], "alerta")
        self.assertEqual(d["comandos"]["programar"], ".venv/bin/python -m scripts.robots.sombra programar")
        self.assertNotIn("nivel", d, "el «verde» de la foto no viaja: nada del panel lo debe leer como un planificador sano")

    def test_una_foto_vieja_no_dice_al_dia_ni_hoy(self) -> None:
        self.poner_foto(True)
        d = self.sombra(AHORA + _dt.timedelta(days=3))["datos"]
        self.assertEqual((d["situacion"], d["de_hoy"]), ("vencido", False))
        self.assertEqual(len(d["resumen"]["vencidos"]), 7)
        self.assertEqual(d["resumen"]["faltan_hoy"], [], "«faltan hoy» solo se informa si la foto es de hoy")
        self.assertEqual(d["resumen"]["corrieron_hoy"], [], "lo de hace tres días no corrió «hoy»")
        for x in d["robots"]:
            if x["esperado"]:
                self.assertEqual((x["estado_latido"], x["vencido"]), ("vencido", True), x["id"])
        self.assertIn("la foto lo daba al día", {x["id"]: x for x in d["robots"]}["vigia"]["motivo"])

    def test_el_vencimiento_se_recalcula_con_la_hora_de_ahora_dentro_del_mismo_dia(self) -> None:
        self.poner_foto(True)
        d = self.sombra(_t("2026-11-09T13:00:00Z"))["datos"]          # 90 min después de la corrida: los de cada 15 min (máx. 35) ya vencieron; el auditor (máx. 125 min) y el informe (25,5 h) no
        self.assertEqual((d["situacion"], d["de_hoy"]), ("vencido", True))
        self.assertEqual(sorted(d["resumen"]["vencidos"]), ["alertas", "vigia"])
        self.assertFalse({x["id"]: x for x in d["robots"]}["informe"]["vencido"])
        self.assertFalse({x["id"]: x for x in d["robots"]}["auditor"]["vencido"])

    def test_corridas_a_mano_no_crean_expectativa(self) -> None:
        self.poner_foto(False)
        d = self.sombra()["datos"]
        self.assertEqual(d["situacion"], "sin_programar")
        self.assertEqual((d["resumen"]["esperados"], d["resumen"]["vencidos"]), ([], []))
        self.assertEqual(len(d["resumen"]["solo_manual"]), 7)
        self.assertEqual({x["id"]: x for x in d["robots"]}["perfil"]["estado_latido"], "manual")
        d = self.sombra(AHORA + _dt.timedelta(days=5))["datos"]
        self.assertEqual((d["situacion"], d["resumen"]["vencidos"]), ("sin_programar", []), "lo que nunca se programó no vence jamás")

    def test_texto_hostil_se_sanea_y_lo_invalido_se_descarta(self) -> None:
        self.poner_foto(True)
        ruta = self.raiz / "empresa" / "robots" / "estado.json"
        d = json.loads(ruta.read_text(encoding="utf-8"))
        hostil = "<img src=x onerror=alert(1)> https://malo.example/x ‮gnp.exe\x07"
        d["robots"][4]["ultima_razon"] = hostil + "x" * 900
        d["robots"][4]["nombre"] = hostil
        d["robots"][4]["metricas"] = {"acierto_bp": 7500, "decimal": 1.5, "Mala Clave": 3, "ok_bool": True}
        d["robots"][4]["ultimo_resultado"] = "genial"
        d["robots"][4]["estado_latido"] = "inventado"
        d["robots"][5]["id"] = "../x"
        d["robots"][6]["id"] = "Escalera"
        d["robots"].extend([None, 7, "x", {"sin": "id"}] + [{"id": f"r{i}"} for i in range(60)])
        d["avisos"] = [hostil, 5, "ok"]
        d["zona_hoy"] = "../../etc/passwd"
        ruta.write_text(json.dumps(d), encoding="utf-8")
        s = self.sombra()["datos"]
        self.assertLessEqual(len(s["robots"]), 24, "tope de filas")
        ids = [x["id"] for x in s["robots"]]
        self.assertNotIn("../x", ids)
        self.assertNotIn("Escalera", ids)
        x = {x["id"]: x for x in s["robots"]}["perfil"]
        self.assertNotIn("malo.example", json.dumps(s))
        self.assertNotIn("‮", json.dumps(s, ensure_ascii=False))
        self.assertLessEqual(len(x["ultima_razon"]), 200)
        self.assertIn("<img", x["nombre"], "el texto va como dato inerte; el cliente lo pinta con textContent")
        self.assertEqual(x["metricas"], {"acierto_bp": 7500}, "solo enteros y claves en minúsculas")
        self.assertIsNone(x["ultimo_resultado"])
        self.assertEqual(x["estado_latido"], "desconocido")
        self.assertEqual(s["zona_hoy"], "UTC", "una zona rara no se usa")
        self.assertLessEqual(len(s["avisos"]), 5)

    def test_archivo_ilegible_enorme_o_con_otra_forma_se_ignora_con_aviso(self) -> None:
        carpeta = self.raiz / "empresa" / "robots"
        carpeta.mkdir(parents=True)
        for contenido in (b"{no es json", b"[]", json.dumps({"tipo": "otra_cosa", "robots": []}).encode(), json.dumps({"tipo": "estado_robots", "robots": "x"}).encode(), b"x" * (300 * 1024)):
            (carpeta / "estado.json").write_bytes(contenido)
            r = self.cliente().get("/api/robots/sombra")
            self.assertEqual(r.estado, 200)
            j = r.json()
            self.assertIs(j["vacio"], True, contenido[:20])
            self.assertEqual(j["datos"]["existe"], False)
            self.assertTrue(j["avisos"])

    def test_enlace_simbolico_que_escapa_no_se_sigue(self) -> None:
        fuera = Path(tempfile.mkdtemp(prefix="sombra-fuera-"))
        self.addCleanup(shutil.rmtree, fuera, True)
        (fuera / "estado.json").write_text(json.dumps({"tipo": "estado_robots", "robots": [{"id": "perfil"}]}), encoding="utf-8")
        os.symlink(fuera, self.raiz / "empresa" / "robots")
        j = self.cliente().get("/api/robots/sombra").json()
        self.assertIs(j["vacio"], True)

    def test_robots_yaml_sigue_igual_y_la_foto_no_lo_toca(self) -> None:
        self.poner_foto(True)
        j = self.cliente().get("/api/robots").json()
        self.assertIs(j["vacio"], True, "sin robots.yaml sigue vacío aunque haya foto de la sombra")
        self.assertEqual(j["fuente"], ["empresa/robots.yaml"])
        self.assertEqual(j["datos"], {})

    def test_solo_lectura_token_y_metodo(self) -> None:
        self.poner_foto(True)
        antes = self.hash_arbol(self.raiz)
        c = self.cliente()
        self.assertEqual(c.get("/api/robots/sombra", token=False).estado, 403)
        self.assertIn(c.post("/api/robots/sombra", {}).estado, (403, 404, 405))
        for _ in range(3):
            self.assertEqual(c.get("/api/robots/sombra").estado, 200)
        self.assertEqual(self.hash_arbol(self.raiz), antes, "leer no escribe nada")


if __name__ == "__main__":
    unittest.main()
