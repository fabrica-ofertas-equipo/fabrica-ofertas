"""Pruebas de `proximo_paso.py` (solo lectura; trabaja con copias en memoria del estado de `ofertas/_ejemplo/`).

Correr (desde la raíz): .venv/bin/python .claude/skills/o0-lanzar-oferta/scripts/test_proximo_paso.py
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proximo_paso as pp  # noqa: E402

RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "contratos").is_dir() and (p / "empresa").is_dir())
ESTADO = json.loads((RAIZ / "ofertas" / "_ejemplo" / "estado.json").read_text(encoding="utf-8"))
GATES = json.loads((RAIZ / "contratos" / "gates.json").read_text(encoding="utf-8"))
H = pp.GATE_H_SIEMPRE


def aut(nivel: str) -> dict:
    return {"nivel_por_etapa": {e: {"nivel": nivel} for e in pp.CADENA + pp.POSTERIORES}}


def nuevo(nivel="N0") -> dict:
    """Oferta recién creada: todo pendiente, sin hashes."""
    e = copy.deepcopy(ESTADO)
    e["fase"], e["nivel"] = "en_construccion", nivel
    for et in e["etapas"].values():
        et.update(estado="pendiente", version_aprobada=None, hash_salida=None, entradas={}, ronda_qa=0, intentos=0, gate_pendiente=False,
                  nivel=nivel, aprobado_por=None, bloqueo=None, idempotency_key=None, obsoleta=False)
    return e


def paso(estado, nivel="N2", pausa=None, brief=None):
    return pp.proximo(estado, GATES, aut(nivel), pausa=pausa, brief=brief, acciones_h=H)


class PruebasProximoPaso(unittest.TestCase):
    def test_ejemplo_espera_la_firma_de_d7(self):
        r = paso(copy.deepcopy(ESTADO))
        self.assertEqual((r["accion"], r["etapa"], r["gate"], r["espera_firma"]), ("firmar", "D7", "H", True))
        self.assertIn("firmar --oferta OF-202611-01 --etapa D7 --como dueno", r["comando"])

    def test_oferta_nueva_en_n0_se_hace_a_mano_y_entra_con_ingresar(self):
        r = paso(nuevo("N0"), "N0")
        self.assertEqual((r["accion"], r["etapa"]), ("ingresar", "D1"))
        self.assertIn("ingresar --oferta OF-202611-01 --etapa D1", r["comando"])

    def test_oferta_nueva_en_n1_d1_exige_sesion_interactiva(self):
        r = paso(nuevo("N1"), "N1")                      # D1 usa la Biblioteca de Anuncios: solo en la sesión interactiva
        self.assertEqual((r["accion"], r["etapa"], r["requiere_sesion_interactiva"]), ("ingresar", "D1", True))
        self.assertIn("--origen sesion_code", r["comando"])

    def test_etapa_sin_conectores_se_ejecuta_primero_en_seco(self):
        e = nuevo("N1")
        for k in ("D1", "M1", "D2"):
            e["etapas"][k].update(estado="aprobado", hash_salida="sha256:" + "b" * 64, version_aprobada="v1")
        e["etapas"]["M1"]["entradas"] = {"D1": "sha256:" + "b" * 64}
        e["etapas"]["D2"]["entradas"] = {"D1": "sha256:" + "b" * 64, "M1": "sha256:" + "b" * 64}
        r = paso(e, "N1")                                # D3 no usa conectores
        self.assertEqual((r["accion"], r["etapa"]), ("ejecutar", "D3"))
        self.assertIn("--modo fixture --fixture", r["comando"])   # SC-7: la CLI solo corre `--modo fixture --fixture DIR`
        self.assertNotIn("--live", r["comando"])
        self.assertNotIn("dry-run", r["comando"])
        self.assertTrue(any("SB-9" in a for a in r["avisos"]))

    def test_d6_higgsfield_y_n3_avisa_alternativa_pendiente(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D6"].update(estado="pendiente", hash_salida=None, entradas={}, version_aprobada=None, aprobado_por=None, gate_pendiente=False)
        e["etapas"]["D7"].update(estado="pendiente", hash_salida=None, entradas={}, gate_pendiente=False)
        r = paso(e, "N2")
        self.assertEqual((r["accion"], r["etapa"], r["requiere_sesion_interactiva"]), ("ingresar", "D6", True))
        e["nivel"] = "N3"
        for et in e["etapas"].values():
            et["nivel"] = "N3"
        self.assertIn("[PENDIENTE]", paso(e, "N3")["motivo"])

    def test_pausa_detiene_todo_y_no_da_comando(self):
        r = paso(copy.deepcopy(ESTADO), pausa={})
        self.assertEqual((r["accion"], r["comando"], r["espera_firma"]), ("pausa", None, False))
        e = copy.deepcopy(ESTADO)
        e["pausa"] = True
        self.assertEqual(paso(e)["accion"], "pausa")

    def test_bloqueado_muestra_el_motivo(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D7"].update(estado="bloqueado", gate_pendiente=False, bloqueo={"motivo": "API de Meta caída", "desde": "2026-11-09T10:00:00Z"})
        r = paso(e)
        self.assertEqual(r["accion"], "resolver_bloqueo")
        self.assertIn("API de Meta caída", r["motivo"])

    def test_escalado_exige_orden_humana(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D7"]["estado"] = "escalado"
        self.assertEqual((paso(e)["accion"], paso(e)["espera_firma"]), ("orden_humana", True))

    def test_hash_de_entrada_cambiado_vuelve_obsoleta_a_la_etapa(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D3"]["hash_salida"] = "sha256:" + "a" * 64   # D4, D5 y D6 consumieron otro hash de D3
        r = paso(e)
        self.assertEqual((r["accion"], r["etapa"]), ("reejecutar", "D4"))

    def test_nivel_efectivo_es_el_menor(self):
        e = copy.deepcopy(ESTADO)
        self.assertEqual(pp.nivel_efectivo(e, "D2", aut("N0")), "N0")
        self.assertEqual(pp.nivel_efectivo(e, "D2", aut("N4")), "N2")      # el estado dice N2
        self.assertEqual(pp.nivel_efectivo(e, "D2", None), "N2")
        self.assertEqual(pp.gate_efectivo(GATES, e, "D2", aut("N0"))[0], "H")  # D2 es S en N2 pero H en N0

    def test_todo_aprobado_y_listo_pide_activar_con_h(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D7"].update(estado="aprobado", gate_pendiente=False, version_aprobada="v1")
        e["fase"] = "listo_para_activar"
        r = paso(e, "N4")
        self.assertEqual((r["accion"], r["gate"], r["espera_firma"]), ("activar", "H", True))   # activar_campana es H en todo nivel mientras limites lo diga
        self.assertIn("--live", r["comando"])

    def test_todo_aprobado_sin_preflight_espera_al_motor(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D7"].update(estado="aprobado", gate_pendiente=False, version_aprobada="v1")
        self.assertEqual(paso(e)["accion"], "esperar")

    def test_oferta_en_test_pasa_a_operacion(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D7"].update(estado="aprobado", gate_pendiente=False)
        e["fase"] = "en_test"
        self.assertEqual(paso(e)["accion"], "operacion")

    def test_borrador_sin_firma_pide_firmar_el_brief(self):
        e = nuevo("N1")
        e["fase"] = "borrador"
        r = paso(e, "N1", brief={"aprobado_por": {"firma": None}})
        self.assertEqual((r["accion"], r["etapa"], r["gate"]), ("firmar", "O0", "H"))

    def test_s_en_qa_con_pass_no_exige_firma_pero_con_gate_pendiente_si_se_muestra(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D6"].update(estado="en_QA", gate_pendiente=True)
        e["etapas"]["D7"].update(estado="pendiente", gate_pendiente=False, hash_salida=None, entradas={})
        r = paso(e)
        self.assertEqual((r["accion"], r["etapa"], r["gate"], r["espera_firma"]), ("firmar", "D6", "S", False))

    def test_la_ayuda_nunca_escribe(self):
        antes = (RAIZ / "ofertas" / "_ejemplo" / "estado.json").read_bytes()
        pp.main(["--oferta", "_ejemplo", "--autonomia", str(RAIZ / "contratos" / "ejemplos" / "autonomia.valido.yaml")])
        self.assertEqual(antes, (RAIZ / "ofertas" / "_ejemplo" / "estado.json").read_bytes())

    def test_proceso_muerto_en_d6_no_manda_repetir_la_etapa(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D6"].update(estado="en_progreso", gate_pendiente=False, aprobado_por=None)
        e["etapas"]["D7"].update(estado="pendiente", gate_pendiente=False, hash_salida=None, entradas={})
        r = paso(e)
        self.assertEqual((r["accion"], r["etapa"]), ("esperar", "D6"))
        self.assertIn("orq estado", r["comando"])
        self.assertNotIn("ejecutar", r["comando"])

    def test_estado_por_ruta_de_plantilla_pide_firmar_el_brief_sin_firma(self):
        plantilla = RAIZ / ".claude" / "skills" / "o0-orquestador-portafolio" / "templates" / "estado.oferta-nueva.json"
        self.assertEqual(pp.main(["--estado", str(plantilla), "--json"]), 0)

    def test_firmar_incluye_los_flags_que_exige_la_cli_y_nunca_una_ruta_de_clave(self):
        r = paso(copy.deepcopy(ESTADO))
        self.assertIn("--hash-objetivo " + ESTADO["etapas"]["D7"]["hash_salida"], r["comando"])
        self.assertIn("--clave-privada <RUTA_DE_TU_CLAVE_PRIVADA>", r["comando"])
        self.assertNotIn(".pem", r["comando"])
        self.assertTrue(any("--clave-privada" in a for a in r["avisos"]))

    def test_brief_sin_firma_no_inventa_un_comando_que_la_cli_rechaza(self):
        e = nuevo("N1")
        e["fase"] = "borrador"
        r = paso(e, "N1", brief={"aprobado_por": {"firma": None}})
        self.assertIsNone(r["comando"])                       # `orq firmar --etapa O0` no valida: LT-54
        self.assertIn("LT-54", r["motivo"])

    def test_activar_avisa_que_el_live_no_esta_en_la_cli(self):
        e = copy.deepcopy(ESTADO)
        e["etapas"]["D7"].update(estado="aprobado", gate_pendiente=False, version_aprobada="v1")
        e["fase"] = "listo_para_activar"
        r = paso(e, "N4")
        self.assertTrue(any("B5" in a and "--live" in a for a in r["avisos"]))
        self.assertIn("D-02", r["motivo"])

    def test_pausa_avisa_que_reanudar_no_esta_en_la_cli(self):
        r = paso(copy.deepcopy(ESTADO), pausa={})
        self.assertTrue(any("reanudar" in a for a in r["avisos"]))

    def test_sin_oferta_ni_estado_sale_2(self):
        self.assertEqual(pp.main([]), 2)

    def test_oferta_inexistente_sale_3(self):
        self.assertEqual(pp.main(["--oferta", "OF-999999-99"]), 3)


if __name__ == "__main__":
    unittest.main()
