"""Pruebas de la agenda de cada oferta (``dashboard/agenda.py``): horario de las tareas, test en curso, backend que se prende,
oferta armada sin activar, apagada y lo que le toca al dueño."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from dashboard import agenda
from dashboard.api_base import Ctx

ART = ZoneInfo("America/Argentina/Buenos_Aires")
AHORA = dt.datetime(2026, 11, 14, 17, 40, tzinfo=ART)
ZONAS_PY = 'ZONA = {\n    "ES": "Europe/Madrid", "FR": "Europe/Paris", "MX": "America/Mexico_City",\n}\n'
TAREAS = {"leido": "2026-11-14T20:00:00+00:00", "tareas": [
    {"taskId": "vigilancia-ofertas", "title": "Vigilancia", "cronExpression": "2,17,32,47 * * * *", "enabled": True},
    {"taskId": "renovacion-diaria", "title": "Renovación", "cronExpression": "35 8-22/2 * * *", "enabled": True},
    {"taskId": "lanzar-ofertas", "title": "Lanzar", "cronExpression": "0 6,13 * * *", "enabled": True},
]}


class TestCron(unittest.TestCase):
    def test_proxima_corrida_en_hora_de_argentina(self) -> None:
        self.assertEqual(agenda.proxima_corrida("2,17,32,47 * * * *", AHORA), dt.datetime(2026, 11, 14, 17, 47, tzinfo=ART))
        self.assertEqual(agenda.proxima_corrida("35 8-22/2 * * *", AHORA), dt.datetime(2026, 11, 14, 18, 35, tzinfo=ART))
        self.assertEqual(agenda.proxima_corrida("0 6,13 * * *", AHORA), dt.datetime(2026, 11, 15, 6, 0, tzinfo=ART))
        self.assertEqual(agenda.proxima_corrida("0 20 * * 0", AHORA), dt.datetime(2026, 11, 15, 20, 0, tzinfo=ART), "domingo")
        self.assertIsNone(agenda.proxima_corrida("no es cron", AHORA))


def _test(**kw) -> dict:
    base = {"nombre": "T", "oferta": "T", "mercado": "ES", "estado": "activo", "inicio": "2026-11-14T00:00:00+01:00", "campana": "1", "tienda": ["t"]}
    base.update(kw)
    return base


class TestAgenda(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        (r / "ofertas/_funnels").mkdir(parents=True)
        (r / ".claude/skills/escalar-oferta/scripts").mkdir(parents=True)
        (r / ".claude/skills/escalar-oferta/scripts/control_previo.py").write_text(ZONAS_PY, encoding="utf-8")
        (r / "ofertas/_funnels/tareas.json").write_text(json.dumps(TAREAS), encoding="utf-8")
        (r / "ofertas/_funnels/vigilancia_vuelta.json").write_text(json.dumps({"completa": "2026-11-14T20:08:00+00:00"}), encoding="utf-8")
        vig = {"ahora": "2026-11-14T20:09+00:00", "tests": [{"test": "T", "decision": "SIGUE", "gasto_usd": 178.09, "ventas": 10,
                                                              "cpa_usd": 17.81, "corte_usd": 810.0, "ticket_corte_usd": 54.0}]}
        (r / "ofertas/_funnels/vigilancia.jsonl").write_text(json.dumps(vig) + "\n", encoding="utf-8")
        self.ctx = Ctx(raiz=r, ahora=lambda: AHORA)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _agenda(self, test: dict, o: dict) -> list[dict]:
        datos = {"ofertas": [{"id": "t", "nombre": "T", **o}]}
        agenda.agregar_agendas(self.ctx, datos, {"tests": [test]}, AHORA)
        self.datos = datos
        return datos["ofertas"][0]["agenda"]

    def test_test_en_curso_con_backend_que_se_prende_al_cierre(self) -> None:
        t = _test(backend={"estado": "listo", "listo": "2026-11-14T11:45-03:00", "activar_desde": "2026-11-15T00:00:00+01:00",
                           "upsells": [{"nombre": "U1", "precio_eur": 39}], "bump_al_activar": ["b"]},
                  pendientes=[{"que": "Mirar el bump en el celular", "desde": "2026-11-15T00:00:00+01:00"}])
        ag = self._agenda(t, {"estado": "activa", "fase": "test", "inicio": "2026-11-14T00:00:00+01:00", "fin_test": "2026-11-15T00:00:00+01:00",
                              "ventas_n": 10, "corte_usd": 810.0})
        tipos = [(i["tipo"], i["titulo"]) for i in ag]
        self.assertEqual(tipos[0], ("en_curso", "Test del día 1"))
        self.assertIn("US$ 810,00", ag[0]["detalle"])
        self.assertIn(("te_toca", "Mirar el bump en el celular"), tipos)
        prox = {i["titulo"]: i for i in ag if i["tipo"] == "proximo"}
        self.assertEqual(prox["Revisa el corte"]["cuando"], "2026-11-14T21:02:00+00:00", "una completa por hora: 17:08 + 52 min → 18:02")
        backend = next(v for k, v in prox.items() if k.startswith("Se prende el backend"))
        self.assertEqual(backend["cuando"], "2026-11-14T23:00:00+00:00")
        self.assertIn("bump", backend["titulo"])
        self.assertIn(("hecho", "Backend armado y probado (embudo apagado)"), tipos)
        viene = [i["titulo"] for i in self.datos["lo_que_viene"]]
        self.assertNotIn("Revisa el corte", viene, "lo que se repite no va a «Lo que viene»")
        tareas = {t["clave"]: t for t in self.datos["agenda_sistema"]["tareas"]}
        self.assertEqual(tareas["renovacion-diaria"]["proxima"], "2026-11-14T21:35:00+00:00")

    def test_armada_sin_activar_no_promete_salida(self) -> None:
        t = _test(nombre="T", mercado="FR", estado="armado", inicio="2026-11-15T00:00:00+01:00", nota="NO ACTIVADA: falta la fan page.")
        ag = self._agenda(t, {"estado": "programada", "fase": "test", "inicio": "2026-11-15T00:00:00+01:00"})
        self.assertEqual([i["tipo"] for i in ag if i["tipo"] != "hecho"], ["condicion"], "ni «sale la campaña» ni «cierra el test»")
        self.assertIn("falta la fan page", ag[0]["detalle"])
        self.assertEqual(self.datos["lo_que_viene"][0]["titulo"], "Armada, sin activar")

    def test_apagada_no_tiene_pasos(self) -> None:
        t = _test(estado="pausado", apagado={"cuando": "2026-11-14T11:20-03:00", "porque": "corte"})
        ag = self._agenda(t, {"estado": "pausada", "fase": "test", "inicio": "2026-11-14T00:00:00+01:00"})
        self.assertFalse([i for i in ag if i["tipo"] == "proximo"])
        self.assertIn(("hecho", "Campaña apagada"), [(i["tipo"], i["titulo"]) for i in ag])

    def test_post_lanzamiento_que_no_pega_explica_por_que_no_renueva(self) -> None:
        t = _test(mercado="MX", inicio="2026-11-12T00:00:00-06:00",
                  presupuesto_cambios=[{"cuando": "2026-11-13T18:05-03:00", "de": 45.5, "a": 50, "tipo": "correccion"}])
        ag = self._agenda(t, {"estado": "activa", "fase": "post-lanzamiento", "inicio": "2026-11-12T00:00:00-06:00", "ventas_n": 10,
                              "cpa": 15.72, "equilibrio": 12.17, "backend": {"estado": "activo"}})
        titulos = [i["titulo"] for i in ag]
        self.assertIn("Evalúa la escala del presupuesto", titulos)
        self.assertIn("Revisión diaria", titulos)
        cond = next(i for i in ag if i["tipo"] == "condicion")
        self.assertIn("US$ 15,72", cond["detalle"])


if __name__ == "__main__":
    unittest.main()
