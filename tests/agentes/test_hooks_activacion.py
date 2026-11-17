"""Pruebas de ``agentes.hooks.pretooluse_activacion`` (docs/09 §14.3): dos ramas, M07."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentes.hooks import pretooluse_activacion as hook
from agentes.sonda_hooks import HASH_CONFIG, OFERTA_ID, construir_empresa_de_prueba, escribir_sello


class PruebaBase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)
        self._tmp = tempfile.TemporaryDirectory(prefix="hook-activacion-")
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)

    def _env(self, **extra: str) -> dict[str, str]:
        base = {"AGENT_RAIZ": str(self.raiz), "AGENT_OFERTA_ID": OFERTA_ID,
                "AGENT_SPOOL": str(self.raiz / "empresa" / "registro.jsonl")}
        base.update(extra)
        return base

    def _manejar(self, datos: dict, env: dict) -> str | None:
        with mock.patch.dict(os.environ, env, clear=True):
            return hook.manejar(datos)


class PruebaActivacionPositiva(PruebaBase):
    def test_activacion_con_sello_exacto_pasa(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=("111", "222"))
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_100000000000001", "entity_type": "campaign", "entity_id": "111",
                            "object_ids": ["222"], "publish_as_active": True, "allow_partial_publish": False}},
            self._env(FABRICA_FIRMA_PUBLICA=publica))
        self.assertIsNone(motivo)

    def test_pausar_siempre_pasa_sin_sello(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_update_entity",
             "tool_input": {"entity_id": "111", "entity_type": "ad", "fields": json.dumps({"status": "PAUSED"})}},
            self._env())
        self.assertIsNone(motivo)

    def test_activar_via_update_entity_con_sello_exacto_pasa(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=("111",))
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_update_entity",
             "tool_input": {"entity_id": "111", "entity_type": "ad", "fields": json.dumps({"status": "ACTIVE"})}},
            self._env(FABRICA_FIRMA_PUBLICA=publica))
        self.assertIsNone(motivo)

    def test_bash_dry_run_sin_live_no_exige_sello(self) -> None:
        construir_empresa_de_prueba(self.raiz)  # SIN sello: si exigiera uno, esto denegaría
        motivo = self._manejar(
            {"tool_name": "Bash", "tool_input": {"command": "python3 scripts/meta_activar.py --oferta OF-202611-01 --hash-config x --object-ids 111"}},
            self._env())
        self.assertIsNone(motivo)

    def test_bash_live_con_sello_exacto_pasa(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=("111", "222"), hash_config=HASH_CONFIG)
        comando = f"python3 scripts/meta_activar.py --oferta {OFERTA_ID} --hash-config {HASH_CONFIG} --object-ids 111,222 --live"
        motivo = self._manejar({"tool_name": "Bash", "tool_input": {"command": comando}},
                               self._env(FABRICA_FIRMA_PUBLICA=publica))
        self.assertIsNone(motivo)

    def test_herramienta_fuera_de_alcance_no_opina(self) -> None:
        motivo = self._manejar({"tool_name": "Read", "tool_input": {"file_path": "/x"}}, self._env())
        self.assertIsNone(motivo)


class PruebaBashCliRealesDeActivacion(PruebaBase):
    """SB-1: la rama Bash gobierna los CLI REALES (``python -m meta.activar``, ``--modo live``, ``python -m engine.orq
    activar``, ids de ``--ids-meta``), no solo la forma ``scripts/meta_activar.py --live --object-ids``."""

    IDS = ("2000000001", "3000000001", "4000000001")  # campaña, conjunto, anuncio

    def _ids_meta(self, ids=None) -> str:
        c, a, d = ids or self.IDS
        ruta = self.raiz / "ofertas" / OFERTA_ID / "07-campana" / "ids_meta.json"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps({"campaign_id": c, "adset_ids": [a], "ad_ids": [d]}), encoding="utf-8")
        return f"ofertas/{OFERTA_ID}/07-campana/ids_meta.json"

    def _bash(self, comando: str, publica=None) -> str | None:
        extra = {"FABRICA_FIRMA_PUBLICA": publica} if publica else {}
        return self._manejar({"tool_name": "Bash", "tool_input": {"command": comando}}, self._env(**extra))

    def _base_meta(self, modo: str, ids_meta: str) -> str:
        return (f"python -m meta.activar --oferta {OFERTA_ID} --campana ofertas/{OFERTA_ID}/07-campana/campana.json --ids-meta {ids_meta} "
                f"--hash-config {HASH_CONFIG} --cuenta ofertas/{OFERTA_ID}/07-campana/cuenta.json --monto 5000 --moneda EUR {modo}")

    def test_meta_activar_modulo_modo_live_sin_sello_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        self.assertIn("sello", self._bash(self._base_meta("--modo live", self._ids_meta())))

    def test_meta_activar_modulo_modo_live_con_sello_exacto_pasa(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=self.IDS, hash_config=HASH_CONFIG)
        self.assertIsNone(self._bash(self._base_meta("--modo live", self._ids_meta()), publica))

    def test_modo_igual_a_valor_tambien_es_vivo(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        self.assertIsNotNone(self._bash(self._base_meta("--modo=live", self._ids_meta())))

    def test_sello_con_otros_ids_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=self.IDS[:2], hash_config=HASH_CONFIG)
        motivo = self._bash(self._base_meta("--modo live", self._ids_meta()), publica)
        self.assertIn("object_ids no coinciden", motivo)

    def test_dry_run_y_fixture_no_exigen_sello(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        ids_meta = self._ids_meta()
        for modo in ("", "--modo dry-run", "--modo fixture", "--modo=fixture"):
            with self.subTest(modo=modo):
                self.assertIsNone(self._bash(self._base_meta(modo, ids_meta)))

    def test_modo_sin_valor_o_desconocido_cuenta_como_vivo(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        ids_meta = self._ids_meta()
        self.assertIsNotNone(self._bash(self._base_meta("--modo", ids_meta)))
        self.assertIsNotNone(self._bash(self._base_meta("--modo produccion", ids_meta)))
        self.assertIsNotNone(self._bash(self._base_meta("--modo fixture --modo live", ids_meta)))

    def test_ids_meta_fuera_de_la_oferta_o_ilegible_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=self.IDS, hash_config=HASH_CONFIG)
        self.assertIn("fuera de", self._bash(self._base_meta("--modo live", "../../../etc/passwd"), publica))
        self.assertIn("ilegible", self._bash(self._base_meta("--modo live", f"ofertas/{OFERTA_ID}/07-campana/no-existe.json"), publica))

    def test_object_ids_y_ids_meta_que_no_coinciden_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=self.IDS, hash_config=HASH_CONFIG)
        comando = self._base_meta("--modo live", self._ids_meta()) + " --object-ids 2000000001"
        self.assertIn("no coincide", self._bash(comando, publica))

    def test_live_sin_ids_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        comando = f"python -m meta.activar --oferta {OFERTA_ID} --hash-config {HASH_CONFIG} --modo live"
        self.assertIn("sin --object-ids ni --ids-meta", self._bash(comando))

    def test_engine_orq_activar_live_con_ids_separados_por_espacios(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        base = f"python -m engine.orq activar --oferta {OFERTA_ID} --hash-config {HASH_CONFIG} --live --object-ids 111 222"
        self.assertIn("sello", self._bash(base))
        publica = escribir_sello(self.raiz, object_ids=("111", "222"), hash_config=HASH_CONFIG)
        self.assertIsNone(self._bash(base, publica))
        self.assertIn("object_ids no coinciden", self._bash(base + " 333", publica))

    def test_engine_orq_activar_sin_live_no_exige_sello_pero_otro_subcomando_no_se_confunde(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        self.assertIsNone(self._bash(f"python -m engine.orq activar --oferta {OFERTA_ID} --hash-config {HASH_CONFIG} --object-ids 111"))
        self.assertIsNone(self._bash(f"python -m engine.orq estado --oferta {OFERTA_ID} --live"))

    def test_pausar_nunca_se_gobierna_aunque_sea_vivo(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        self.assertIsNone(self._bash("python -m meta.pausar --ad-account act_100000000000001 --campana-id 2000000001 --modo live"))
        self.assertIsNone(self._bash("python3 scripts/pausar.py --campana-id 2000000001 --modo live"))

    def test_las_variantes_por_archivo_y_otros_scripts_tambien_se_gobiernan(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        ids_meta = self._ids_meta()
        for cmd in (f"python3 scripts/meta_activar.py --oferta {OFERTA_ID} --ids-meta {ids_meta} --hash-config {HASH_CONFIG} --modo live",
                    f"python3 scripts/meta_crear.py --oferta {OFERTA_ID} --ids-meta {ids_meta} --hash-config {HASH_CONFIG} --modo live",
                    f"python -m meta.subir_presupuesto --oferta {OFERTA_ID} --ids-meta {ids_meta} --hash-config {HASH_CONFIG} --modo live",
                    f"python3 scripts/subir_presupuesto.py --oferta {OFERTA_ID} --ids-meta {ids_meta} --hash-config {HASH_CONFIG} --modo live"):
            with self.subTest(cmd=cmd[:40]):
                self.assertIn("sello", self._bash(cmd))


class PruebaActivacionNegativa(PruebaBase):
    def test_sin_aprobacion_json_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz, con_aprobacion=False)
        publica = escribir_sello(self.raiz, object_ids=("111",))
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_100000000000001", "entity_type": "ad", "entity_id": "111"}},
            self._env(FABRICA_FIRMA_PUBLICA=publica))
        self.assertIsNotNone(motivo)

    def test_cuenta_fuera_de_cuentas_permitidas_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=("111",))
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_otra_cuenta", "entity_type": "ad", "entity_id": "111"}},
            self._env(FABRICA_FIRMA_PUBLICA=publica))
        self.assertIsNotNone(motivo)

    def test_sello_vencido_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=("111",), vencido=True)
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_100000000000001", "entity_type": "ad", "entity_id": "111"}},
            self._env(FABRICA_FIRMA_PUBLICA=publica))
        self.assertIsNotNone(motivo)

    def test_sin_firma_publica_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        escribir_sello(self.raiz, object_ids=("111",))
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_100000000000001", "entity_type": "ad", "entity_id": "111"}},
            self._env())  # sin FABRICA_FIRMA_PUBLICA
        self.assertIsNotNone(motivo)

    def test_allow_partial_publish_deniega(self) -> None:
        construir_empresa_de_prueba(self.raiz)
        publica = escribir_sello(self.raiz, object_ids=("111",))
        motivo = self._manejar(
            {"tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_100000000000001", "entity_type": "ad", "entity_id": "111",
                            "allow_partial_publish": True}},
            self._env(FABRICA_FIRMA_PUBLICA=publica))
        self.assertIsNotNone(motivo)


if __name__ == "__main__":
    unittest.main()
