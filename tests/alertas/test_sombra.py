"""Los robots EN SOMBRA y el semáforo «¿me puedo ausentar?»: tres estados con texto simple (nada programado · robots en sombra corriendo · latido vencido) y una regla que no se negocia:
los robots en sombra son de solo lectura y NO son el planificador real, así que nunca ponen en verde la fila del planificador ni el semáforo.

La foto de los robots sale de correr DE VERDAD ``python -m scripts.robots.sombra ejecutar --todos --escribir`` sobre una raíz temporal (nunca sobre ``empresa/`` real).
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

from scripts.alertas import hechos as H
from scripts.alertas.reglas import calcular_alertas
from scripts.alertas.semaforo import calcular_semaforo
from scripts.informe import informe_diario as I
from scripts.robots import sombra as S
from tests.alertas.ayudas import AHORA, Base, PARAMETROS

FOTO_Z = "2026-11-07T08:00:00Z"          # 30 min antes de AHORA (08:30)


def _t(texto: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))


class PruebaSombra(Base):
    _fotos: dict[bool, Path] = {}

    @classmethod
    def _foto(cls, programado: bool) -> Path:
        if programado not in cls._fotos:
            raiz = Path(tempfile.mkdtemp(prefix="sombra-alertas-"))
            (raiz / "empresa").mkdir()
            (raiz / "ofertas").mkdir()
            (raiz / "empresa" / "parametros.yaml").write_text(PARAMETROS, encoding="utf-8")
            args = ["ejecutar", "--todos", "--escribir", "--raiz", str(raiz), "--ahora", FOTO_Z] + (["--programado"] if programado else [])
            with mock.patch.dict(os.environ, {"TZ": "UTC"}), mock.patch("sys.stdout"):
                S.main(args)
            cls._fotos[programado] = raiz
        return cls._fotos[programado] / "empresa" / "robots"

    @classmethod
    def tearDownClass(cls) -> None:
        for raiz in cls._fotos.values():
            shutil.rmtree(raiz, True)
        cls._fotos.clear()

    def foto(self, programado: bool = True) -> None:
        shutil.copytree(self._foto(programado), self.raiz / "empresa" / "robots")

    def sin_planificador_real(self) -> None:
        """Todo en orden salvo que NO hay planificador real: la base sana trae uno (``latidos.json``) y acá se quita."""
        self.base_sana()
        (self.raiz / "empresa" / "infra" / "latidos.json").unlink()

    def fila(self, ahora: _dt.datetime = AHORA) -> dict:
        s = calcular_semaforo(H.leer_hechos(self.ctx(ahora)))
        return {c["id"]: c for c in s["comprobaciones"]}["planificador"]

    # ── los tres estados ──
    def test_sin_foto_no_hay_nada_programado(self) -> None:
        self.sin_planificador_real()
        f = self.fila()
        self.assertEqual(f["nivel"], "rojo")
        self.assertIn("Todavía no hay nada programado", f["estado"])
        self.assertIn("todavía no corrieron", f["estado"])
        self.assertEqual((f["responsable"], f["enlace"]), ("dueno", "#/robots"))
        self.assertIn("scripts.robots.sombra estado", f["comando"])

    def test_robots_que_solo_corrieron_a_mano_siguen_siendo_nada_programado(self) -> None:
        self.sin_planificador_real()
        self.foto(False)
        f = self.fila()
        self.assertEqual(f["nivel"], "rojo")
        self.assertIn("No hay nada programado", f["estado"])
        self.assertIn("solo corrieron a mano", f["estado"])
        self.assertIn("instalar es decisión tuya", f["que_hacer"])
        self.assertTrue(f["comando"].endswith("scripts.robots.sombra programar"), "el comando solo IMPRIME cómo se programarían")

    def test_robots_en_sombra_corriendo_son_solo_lectura_y_nunca_ponen_el_semaforo_en_verde(self) -> None:
        self.sin_planificador_real()
        self.foto(True)
        f = self.fila()
        self.assertEqual(f["nivel"], "rojo", "no son el planificador real")
        self.assertIn("Robots en sombra corriendo (solo lectura)", f["estado"])
        self.assertIn("no son el sistema real", f["estado"])
        self.assertIn("el verde llega cuando exista el planificador real", f["que_hacer"])
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual((s["nivel"], [p["id"] for p in s["pasos"]]), ("rojo", ["planificador"]), "todo lo demás en orden: lo único que falta es el planificador real")

    def test_latido_vencido_se_distingue_y_lo_dice(self) -> None:
        self.sin_planificador_real()
        self.foto(True)
        f = self.fila(_t("2026-11-07T13:00:00Z"))          # 5 h después de la corrida: vencieron los de cada 15 min (35 min) y el auditor (125 min); no los diarios
        self.assertEqual(f["nivel"], "rojo")
        self.assertIn("Latido vencido", f["estado"])
        self.assertIn("tu Mac estaba dormida", f["que_hacer"])
        self.assertIn("3 robots en sombra programados dejaron de dar señal de vida a su hora (Vigía de pagos, Auditor, Productor de alertas)", f["estado"])

    def test_el_planificador_real_manda_y_la_sombra_no_lo_cambia(self) -> None:
        self.base_sana()
        self.foto(True)
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual((s["nivel"], s["pasos"]), ("verde", []), "con un planificador real al día y todo en orden es verde")
        # y sin el real, la sombra sola no alcanza
        (self.raiz / "empresa" / "infra" / "latidos.json").unlink()
        self.assertEqual(calcular_semaforo(H.leer_hechos(self.ctx()))["nivel"], "rojo")

    def test_los_latidos_de_la_sombra_nunca_cuentan_como_planificador_real(self) -> None:
        self.foto(True)
        p = H.leer_hechos(self.ctx())["planificador"]
        self.assertEqual((p["existe"], p["trabajos"], p["n"], p["vencidos"]), (False, [], 0, 0), "la sombra va aparte")
        self.assertEqual(p["sombra"]["situacion"], "corriendo")
        self.assertEqual((p["sombra"]["n_esperados"], p["sombra"]["n_vencidos"], p["sombra"]["n_corrieron_hoy"]), (7, 0, 7))

    # ── alertas ──
    def test_alertas_cada_estado(self) -> None:
        self.sin_planificador_real()
        plan = lambda ahora=AHORA: {a.fila["id"]: a for a in calcular_alertas(H.leer_hechos(self.ctx(ahora)))}   # noqa: E731
        sin = plan()["F2-AUS-PLAN:planificador"]
        self.assertIn("ni nada programado", sin.fila["accion_sugerida"])
        self.foto(True)
        al = plan()
        self.assertIn("robots en sombra corriendo (solo lectura)", al["F2-AUS-PLAN:planificador"].fila["accion_sugerida"])
        self.assertEqual(al["F2-AUS-PLAN:planificador"].fila["severidad"], "amarilla")
        self.assertNotIn("F2-A17:sombra", al)
        venc = plan(_t("2026-11-07T13:00:00Z"))
        a = venc["F2-A17:sombra"]
        self.assertEqual((a.fila["severidad"], a.fila["valor"], a.extra["responsable"]), ("amarilla", 3, "dueno"), "un latido vencido de la sombra es amarillo, nunca la alerta roja del planificador real")
        self.assertNotIn("F2-A17:latidos", venc)
        self.assertEqual(a.extra["medida"], "3 robots en sombra sin señal a tiempo")
        from scripts.validar_esquemas import errores_de_esquema
        self.assertEqual(list(errores_de_esquema("alertas", a.fila)), [])

    def test_con_planificador_real_vencido_la_alerta_roja_sigue_siendo_del_real(self) -> None:
        self.base_sana()
        self.poner("empresa/infra/latidos.json", {"trabajos": [{"id": "x", "ultimo_latido": "2026-11-07T01:00:00Z"}]})
        self.foto(True)
        al = {a.fila["id"]: a for a in calcular_alertas(H.leer_hechos(self.ctx()))}
        self.assertEqual(al["F2-A17:latidos"].fila["severidad"], "roja")
        self.assertNotIn("F2-A17:sombra", al)

    # ── informe ──
    def test_el_informe_dice_que_la_sombra_no_mide_trabajos_reales(self) -> None:
        self.sin_planificador_real()
        c = {x["id"]: x for x in I.componer(self.ctx())["ceros"]}["trabajos_sin_latido"]
        self.assertEqual((c["estado"], c["valor"]), ("sin_medir", None))
        self.assertNotIn("sombra", c["detalle"])
        self.foto(True)
        c = {x["id"]: x for x in I.componer(self.ctx())["ceros"]}["trabajos_sin_latido"]
        self.assertEqual((c["estado"], c["valor"]), ("sin_medir", None), "los robots en sombra no son trabajos reales")
        self.assertIn("planificador real", c["detalle"])
        self.assertIn("Los robots en sombra (solo lectura, no son el sistema real): 7 programados, todos al día.", c["detalle"])
        c = {x["id"]: x for x in I.componer(self.ctx(_t("2026-11-07T13:00:00Z")))["ceros"]}["trabajos_sin_latido"]
        self.assertIn("3 con la señal de vida vencida", c["detalle"])

    # ── robustez ──
    def test_una_foto_dañada_se_ignora_como_si_no_existiera(self) -> None:
        self.sin_planificador_real()
        carpeta = self.raiz / "empresa" / "robots"
        carpeta.mkdir(parents=True)
        for contenido in ("{roto", "[]", json.dumps({"tipo": "estado_robots", "robots": "x"}), "x" * (300 * 1024)):
            (carpeta / "estado.json").write_text(contenido, encoding="utf-8")
            self.assertIsNone(H.leer_hechos(self.ctx())["planificador"]["sombra"])
            self.assertIn("Todavía no hay nada programado", self.fila()["estado"])

    def test_el_semaforo_con_sombra_no_escribe_nada(self) -> None:
        self.foto(True)
        antes = self.hash_arbol()
        calcular_semaforo(H.leer_hechos(self.ctx()))
        calcular_alertas(H.leer_hechos(self.ctx()))
        I.componer(self.ctx())
        self.assertEqual(self.hash_arbol(), antes)


if __name__ == "__main__":
    unittest.main()
