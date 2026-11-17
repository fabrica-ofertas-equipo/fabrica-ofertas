"""Siembra del Cerebro (B1-02): J1-J21 en `empresa/memoria/decisiones_dueno.jsonl` y los pendientes sembrados en `empresa/panel/pulido.jsonl`.

SOLO LEE el repositorio real (con el gancho de escrituras puesto). Comprueba invariantes que no cambian cuando se agregan líneas nuevas; no fija cuántas hay hoy.
"""
from __future__ import annotations

import re
import unittest

from tests.cerebro._apoyo import RAIZ, comun, gp, jardinero, sin_escrituras

REAL_DEC = RAIZ / "empresa" / "memoria" / "decisiones_dueno.jsonl"
REAL_PUL = RAIZ / "empresa" / "panel" / "pulido.jsonl"
DOC = "docs/_historial/mentor-sistema/decisiones-del-dueno.md"
HOY = "2026-11-09"


def objetos(ruta) -> list[dict]:
    return comun.jsonl(ruta.read_bytes())[0]


@unittest.skipUnless(REAL_DEC.is_file(), "no está sembrada la memoria")
class PruebasDecisionesSembradas(unittest.TestCase):
    def setUp(self) -> None:
        self.dec = objetos(REAL_DEC)

    def test_j1_a_j21_estan_una_vez_cada_una_y_con_ids_correlativos(self) -> None:
        js = [int(m.group(1)) for d in self.dec if (m := re.match(r"^J(\d{1,2}) · ", d.get("titulo", "")))]
        self.assertTrue(set(range(1, 22)) <= set(js), f"faltan: {sorted(set(range(1, 22)) - set(js))}")
        self.assertEqual(len(js), len(set(js)), "ninguna J repetida")
        self.assertEqual([d["id"] for d in self.dec], [f"DEC-{k:04d}" for k in range(1, len(self.dec) + 1)], "ids correlativos y sin huecos")

    def test_cada_decision_cabe_en_las_listas_blancas_de_la_skill_de_cierre(self) -> None:
        for d in self.dec:
            cuerpo = {k: d[k] for k in ("titulo", "detalle", "alcance", "etapa", "oferta_id", "origen") if d.get(k) is not None}
            if d.get("evidencia"):
                cuerpo["evidencia"] = [{"ruta": e["ruta"]} for e in d["evidencia"]]           # el hash puede haber cambiado si el documento creció: se mira aparte
            linea = gp.validar("decision", cuerpo, raiz=RAIZ, hoy=HOY)       # lanza si no cumple (campos, largos, secretos, prueba existente)
            self.assertEqual(linea["titulo"], d["titulo"], d["id"])
            self.assertEqual((d["autor"], d["tipo"], d["vigente"], d["reemplaza"]), ("dueno", "decision", True, None), d["id"])

    def test_cada_decision_cita_las_palabras_del_dueno_y_una_prueba_con_hash(self) -> None:
        for d in self.dec:
            self.assertRegex(d["detalle"], r"\(fuente: decisiones-del-dueno\.md J\d+\)$", f"{d['id']}: cita el documento")
            self.assertRegex(d["origen"], r"decisiones-del-dueno\.md J\d+")
            self.assertTrue(d.get("evidencia"), d["id"])
            for e in d["evidencia"]:
                self.assertEqual(e["ruta"], DOC)
                self.assertRegex(e["sha256"], r"^sha256:[0-9a-f]{64}$")
                self.assertTrue((RAIZ / e["ruta"]).is_file())

    def test_casi_todas_traen_las_palabras_literales_del_dueno(self) -> None:
        """Hoy 18 de 21 llevan su cita entre « »; J6, J9 y J14 son una opción elegida de un cuestionario (el documento tampoco trae una frase suya). La prueba fija el piso, no el techo."""
        con_cita = [d["id"] for d in self.dec if "«" in d["detalle"]]
        self.assertGreaterEqual(len(con_cita), 18, con_cita)

    def test_ninguna_decision_se_repite_ni_parece_un_secreto(self) -> None:
        for i, a in enumerate(self.dec):
            self.assertIsNone(gp.buscar_secreto(a["titulo"] + " " + a["detalle"]), a["id"])
            for b in self.dec[i + 1:]:
                self.assertLess(gp.similitud(a["titulo"], b["titulo"]), gp.SIM_DUP, (a["id"], b["id"]))

    def test_el_documento_de_decisiones_no_trae_nada_sin_sembrar_o_se_dice(self) -> None:
        """Si el documento creció (J22…), el jardinero lo propone; esta prueba solo exige que lo sembrado sea un prefijo del documento."""
        crudo, _ = comun.leer(RAIZ, DOC, comun.TOPE_DOC)
        en_doc = {int(m.group(1)) for linea in crudo.decode("utf-8").splitlines() if (m := re.match(r"^\|\s*\*\*J(\d{1,2})\*\*\s*\|", linea))}
        self.assertTrue(set(range(1, 22)) <= en_doc, "el documento sigue teniendo J1-J21")
        with sin_escrituras() as eventos:
            r = jardinero.proponer(RAIZ)
        self.assertEqual(eventos, [])
        sin_sembrar = [x for x in r["items"] if x["tipo"] == "decision_sin_sembrar" and "no están guardadas" in x["motivo"]]
        faltan = {n for n in en_doc if n not in {int(m.group(1)) for d in self.dec if (m := re.match(r"^J(\d{1,2}) · ", d.get("titulo", "")))}}
        self.assertEqual(bool(sin_sembrar), bool(faltan))


@unittest.skipUnless(REAL_PUL.is_file(), "no hay lista de pendientes")
class PruebasPendientesSembrados(unittest.TestCase):
    def setUp(self) -> None:
        self.todas = objetos(REAL_PUL)
        self.altas = [o for o in self.todas if o.get("evento") == "alta"]

    def test_ids_unicos_y_correlativos_y_el_p0_de_impulstienda_esta(self) -> None:
        ids = [o["id"] for o in self.altas]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [f"PUL-{k:04d}" for k in range(1, len(ids) + 1)])
        uno = self.altas[0]
        self.assertEqual((uno["id"], uno["prioridad"], uno["responsable"]), ("PUL-0001", "P0", "dueno"))
        self.assertIn("Impulstienda", uno["titulo"])

    def test_los_sembrados_tienen_responsable_y_prioridad_y_caben_en_las_listas_blancas(self) -> None:
        sembrados = [o for o in self.altas if o["id"] != "PUL-0001"]
        self.assertGreaterEqual(len(sembrados), 18)
        for o in self.altas:
            if o.get("tipo") != "pendiente":
                continue
            cuerpo = {k: o[k] for k in ("titulo", "detalle", "etapa", "oferta_id", "severidad", "prioridad", "responsable", "categoria", "origen", "bloquea", "vence") if o.get(k) not in (None, "")}
            gp.validar("pendiente", cuerpo, raiz=RAIZ, hoy=HOY)
            self.assertTrue(o.get("responsable") and o.get("prioridad"), f"{o['id']}: sin responsable o prioridad no se siembra")
            self.assertIsNone(gp.buscar_secreto(o["titulo"] + " " + o.get("detalle", "")), o["id"])

    def test_no_hay_pendientes_abiertos_duplicados(self) -> None:
        abiertos = [e for e in comun.plegar_bitacora(self.todas) if e.get("estado") != "resuelta" and e.get("tipo") not in ("decision", "leccion")]
        for i, a in enumerate(abiertos):
            for b in abiertos[i + 1:]:
                self.assertLess(gp.similitud(a["titulo"], b["titulo"]), gp.SIM_DUP, (a["id"], b["id"]))

    def test_los_p0_estan_protegidos_del_jardinero(self) -> None:
        r = jardinero.proponer(RAIZ)
        p0 = {e["id"] for e in comun.plegar_bitacora(self.todas) if e.get("prioridad") == "P0" and e.get("estado") != "resuelta"}
        self.assertIn("PUL-0001", p0)
        self.assertEqual(p0 & {i for x in r["items"] if x["tipo"] in ("fusionar_duplicados", "revisar_dormido", "cerrar_ya_resuelta") for i in x["ids"]}, set())


if __name__ == "__main__":
    unittest.main(verbosity=1)
