"""Una sola lista de pendientes de verdad (B1-06): `empresa/panel/pulido.jsonl` es la lista única y TODOS la leen igual.

Se compara lo que calcula `/cerebro-abrir` (`resumen_abrir.py`) con lo que calcula el CÓDIGO REAL del panel (`dashboard/web/lib/cerebro.js` para `#/cerebro`, `lib/tareas.js` para
«Mis tareas» `#/tareas`; vía `puente_panel.mjs` con Node) y con el lector de las alertas (`scripts/alertas/hechos._pulido`), sobre la misma bitácora: una escrita por el panel, por el
script de cierre y a mano, y la del repositorio real (copiada, solo lectura).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from tests.cerebro._apoyo import AHORA, RAIZ, Base, alta, buscar, comun, gp, jardinero, jsonl, ra, sin_escrituras

PUENTE = Path(__file__).with_name("puente_panel.mjs")
NODE = shutil.which("node")


def calcular_panel(raiz: Path) -> dict:
    """Lo que muestra el panel de la bitácora de ``raiz``, calculado con su propio JavaScript (el que lee GET /api/pulido)."""
    from dashboard.api_base import Ctx
    from dashboard.pulido import Pulido
    entradas = Pulido(Ctx(raiz), ahora=lambda: AHORA).listar().datos["entradas"]
    ahora_ms = int(AHORA.timestamp() * 1000)
    r = subprocess.run([NODE, str(PUENTE)], input=json.dumps({"entradas": entradas, "ahoraMs": ahora_ms}), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def calcular_alertas(raiz: Path) -> dict:
    from dashboard.api_base import Ctx
    from scripts.alertas import hechos
    return hechos._pulido(Ctx(raiz), AHORA)


@unittest.skipUnless(NODE, "hace falta Node para ejecutar el JavaScript del panel")
class PruebasCoherencia(Base):
    def escribir_mundo(self) -> None:
        """Una bitácora con líneas de las tres procedencias (panel, script de cierre, a mano), estados cambiados y basura."""
        from dashboard.api_base import Ctx
        from dashboard.pulido import Pulido
        panel = Pulido(Ctx(self.raiz), ahora=lambda: AHORA)
        panel.crear({"etapa": "D5", "titulo": "Impulstienda: confirmar qué permite", "tipo": "pendiente", "responsable": "dueno", "prioridad": "P0", "bloquea": ["D5"]})
        panel.crear({"etapa": "D0", "titulo": "Elegir dónde corre el sistema", "tipo": "pendiente", "responsable": "dueno", "prioridad": "P0", "vence": "2026-11-08"})
        panel.crear({"etapa": "D7", "titulo": "Cuenta de Meta limpia", "tipo": "pendiente", "responsable": "dueno", "prioridad": "P1", "vence": "2026-11-20"})
        panel.crear({"etapa": "D8", "titulo": "Firmar la regla de baja", "tipo": "pendiente", "responsable": "ia", "prioridad": "P1"})
        panel.crear({"etapa": "O0", "titulo": "Una mejora vieja", "severidad": "alta"})                                  # sin tipo: «pulido»
        panel.crear({"etapa": "D3", "titulo": "Ya hecho", "tipo": "pendiente", "responsable": "dueno", "prioridad": "P0"})
        panel.cambiar_estado({"id": "PUL-0006", "estado": "resuelta"})
        panel.cambiar_estado({"id": "PUL-0003", "estado": "en_curso"})
        gp.guardar("pendiente", {"titulo": "Elegir proveedor de correo transaccional", "responsable": "dueno", "prioridad": "P1", "etapa": "D10", "vence": "2026-11-05"}, raiz=self.raiz, escribir=True, ahora=AHORA)
        gp.guardar("regla_propuesta", {"titulo": "Nunca prometer plazos de resultado", "categoria": "regla"}, raiz=self.raiz, escribir=True, ahora=AHORA)
        self.poner("ofertas/_ejemplo/qa/d6.json", "{}")
        gp.guardar("preferencia", {"titulo": "Fondos claros en los estáticos", "criterio": "Fondo claro y un solo titular.", "etapa": "D6", "instancias": [
            {"fecha": "2026-11-03", "sobre": "estatico-02", "cita": "ese fondo oscuro no", "evidencia": ["ofertas/_ejemplo/qa/d6.json"]}, {"fecha": "2026-11-05", "sobre": "estatico-07", "cita": "otra vez oscuro: claro"}]},
                   raiz=self.raiz, escribir=True, ahora=AHORA)
        with self.pulido.open("a", encoding="utf-8") as f:
            f.write(jsonl(
                alta(40, titulo="Escrito a mano, tipo desconocido", tipo="cosa_rara", prioridad="P1", responsable="dueno"),
                alta(41, titulo="Decisión anotada en la bitácora", tipo="decision", prioridad="P2", responsable="dueno"),
                alta(42, titulo="Lección anotada en la bitácora", tipo="leccion", responsable="dueno"),
                alta(43, titulo="Estado inventado", estado="pendiente", prioridad="P1", responsable="dueno", vence="2026-11-01"),
                {"id": "PUL-0099", "ts": "2026-11-09T10:00:00Z", "autor": "dueno", "evento": "estado", "estado": "resuelta"}))      # cambio de estado sin alta
            f.write('{"id": "PUL-0044", "ts": "2026\n')                                                                                    # escritura a medias
            f.write("basura\n[1,2]\nnull\n")

    def comparar(self, raiz: Path) -> tuple[dict, dict]:
        panel = calcular_panel(raiz)
        r = ra.resumir(raiz, ahora=AHORA)
        p = r["pendientes"]
        self.assertEqual(sorted(f["id"] for f in p["p0"]), sorted(panel["p0"]), "P0: los mismos")
        self.assertEqual(p["n_p1"], len(panel["p1"]), "cuántos P1")
        self.assertTrue({f["id"] for f in p["p1"]} <= set(panel["p1"]) and len(p["p1"]) == min(len(panel["p1"]), ra.MAX_LISTA), "los P1 que lista son P1 del panel")
        self.assertEqual(p["abiertos"], panel["abiertos_tareas"], "tareas abiertas")
        self.assertEqual(p["reglas_por_aprobar"], len(panel["reglas"]), "reglas por aprobar")
        self.assertTrue({f["id"] for f in p["reglas_propuestas"]} <= set(panel["reglas"]) and len(p["reglas_propuestas"]) == min(len(panel["reglas"]), ra.MAX_LISTA))
        self.assertEqual(p["recordatorios"]["n_vencidos"], len(panel["vencidos"]), "vencidos")
        self.assertTrue({f["id"] for f in p["recordatorios"]["vencidos"]} <= set(panel["vencidos"]))
        self.assertEqual(p["del_dueno_abiertas"], panel["del_dueno"], "lo abierto que es tuyo")
        self.assertEqual(p["del_dueno_abiertas"], panel["mis_tareas_mios"], "«Mis tareas» cuenta lo mismo que /cerebro-abrir")
        self.assertEqual(p["reglas_por_aprobar"], panel["mis_tareas_reglas"], "«Mis tareas» cuenta las mismas reglas por aprobar")
        alertas = calcular_alertas(raiz)
        self.assertEqual(p["del_dueno_abiertas"], alertas["n_abiertos_dueno"], "las alertas leen la misma lista")
        return panel, r

    def test_con_lineas_del_panel_del_script_y_a_mano(self) -> None:
        self.escribir_mundo()
        panel, r = self.comparar(self.raiz)
        self.assertEqual(sorted(panel["p0"]), ["PUL-0001", "PUL-0002"])
        self.assertGreaterEqual(len(panel["vencidos"]), 3)
        self.assertEqual(r["pendientes"]["n_preferencias_propuestas"], 1)

    def test_con_la_bitacora_real_copiada(self) -> None:
        real = RAIZ / "empresa" / "panel" / "pulido.jsonl"
        if not real.is_file():
            self.skipTest("no hay bitácora real")
        self.pulido.write_bytes(real.read_bytes())
        panel, r = self.comparar(self.raiz)
        self.assertIn("PUL-0001", panel["p0"])
        self.assertIn("PUL-0001", [f["id"] for f in r["pendientes"]["p0"]])

    def test_un_p0_nuevo_aparece_en_los_cuatro_lectores(self) -> None:
        self.escribir_mundo()
        nuevo = gp.guardar("pendiente", {"titulo": "Confirmar la cuenta bancaria del cobro", "responsable": "dueno", "prioridad": "P0", "etapa": "D10"}, raiz=self.raiz, escribir=True, ahora=AHORA)["linea"]["id"]
        panel, r = self.comparar(self.raiz)
        self.assertIn(nuevo, panel["p0"])
        self.assertIn(nuevo, [f["id"] for f in r["pendientes"]["p0"]])
        self.assertIn(nuevo, [x["id"] for x in buscar.buscar(self.raiz, "cuenta bancaria", ahora=AHORA)["resultados"]])

    def test_cerrar_en_el_panel_lo_cierra_para_todos(self) -> None:
        from dashboard.api_base import Ctx
        from dashboard.pulido import Pulido
        self.escribir_mundo()
        Pulido(Ctx(self.raiz), ahora=lambda: AHORA).cambiar_estado({"id": "PUL-0001", "estado": "resuelta"})
        panel, r = self.comparar(self.raiz)
        self.assertNotIn("PUL-0001", panel["p0"])
        self.assertNotIn("PUL-0001", [f["id"] for f in r["pendientes"]["p0"]])
        self.assertNotIn("PUL-0001", [x["ids"][0] for x in jardinero.proponer(self.raiz, AHORA)["items"] if x["tipo"] == "vencido"])


class PruebasUnaSolaFuente(Base):
    def test_las_otras_listas_manuales_no_son_fuente_de_pendientes(self) -> None:
        """Ni `/cerebro-abrir`, ni el buscador de pendientes, ni el jardinero leen docs/00, coordinación, ct3 ni w1 como pendientes."""
        self.poner("empresa/panel/pulido.jsonl", jsonl(alta(1, prioridad="P1", responsable="dueno", titulo="El único pendiente real")))
        for rel in ("docs/00-decisiones-y-tareas-del-dueno.md", "docs/_historial/coordinacion-sesiones.md", "docs/_historial/ct3-backlog.md", "docs/_historial/w1-pendientes.md"):
            self.poner(rel, "- [ ] Una tarea de otra lista manual sobre pendientes y backlog\n" * 40)
        with sin_escrituras() as eventos:
            r = ra.resumir(self.raiz, ahora=AHORA)
            j = jardinero.proponer(self.raiz, AHORA)
            b = buscar.buscar(self.raiz, "", etiquetas=("tipo:pendiente",), ahora=AHORA)
        self.assertEqual(eventos, [])
        self.assertEqual((r["pendientes"]["abiertos"], r["pendientes"]["n_p1"]), (1, 1))
        self.assertEqual(j["revisado"]["pendientes_abiertos"], 1)
        self.assertEqual([x["id"] for x in b["resultados"]], ["PUL-0001"])

    def test_el_vencimiento_por_dia_es_igual_para_todos(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(alta(1, vence="2026-11-08", responsable="dueno", prioridad="P2"), alta(2, vence="2026-11-09", responsable="dueno", prioridad="P2"),
                                                         alta(3, vence="2026-11-10", responsable="dueno", prioridad="P2"), alta(4, vence="2026-11-01", responsable="dueno", prioridad="P2", estado="resuelta")))
        r = ra.resumir(self.raiz, ahora=AHORA)
        self.assertEqual([f["id"] for f in r["pendientes"]["recordatorios"]["vencidos"]], ["PUL-0001"])
        self.assertEqual([x["ids"][0] for x in jardinero.proponer(self.raiz, AHORA)["items"] if x["tipo"] == "vencido"], ["PUL-0001"])
        if NODE:
            self.assertEqual(calcular_panel(self.raiz)["vencidos"], ["PUL-0001"])
        self.assertEqual([p["id"] for p in calcular_alertas(self.raiz)["abiertos"] if p["vencido"]], ["PUL-0001"])

    def test_diferencia_conocida_un_vencimiento_con_hora(self) -> None:
        """El panel, `/cerebro-abrir` y el jardinero cuentan por DÍA (vence hoy = no vencido); las alertas (`hechos._pulido`) cuentan por instante (pasada la hora, vencido).
        Se deja escrito para que, si alguien lo unifica, esta prueba lo avise. Pedido anotado en coordinacion-sesiones.md."""
        self.poner("empresa/panel/pulido.jsonl", jsonl(alta(1, vence="2026-11-09T00:00:00Z", responsable="dueno", prioridad="P2")))
        self.assertEqual(ra.resumir(self.raiz, ahora=AHORA)["pendientes"]["recordatorios"]["n_vencidos"], 0)
        if NODE:
            self.assertEqual(calcular_panel(self.raiz)["vencidos"], [])
        self.assertTrue(calcular_alertas(self.raiz)["abiertos"][0]["vencido"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
