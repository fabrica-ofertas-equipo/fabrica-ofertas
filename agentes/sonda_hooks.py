"""``agentes.sonda_hooks`` — banco de entradas sintéticas que TODAS deben dar ``exit 2`` (docs/09 §14.6).

Corre cada hook de ``agentes/hooks/`` como el proceso que lo invocaría de verdad (``.venv/bin/python
agentes/hooks/<hook>.py`` con la entrada por ``stdin`` y el entorno de la corrida), sobre una
«empresa» de prueba desechable (``tempfile``, nunca ``empresa/`` real). Ningún caso debe pasar: si
alguno sale con algo distinto de 2, la sonda falla (preflight de O0 y CI, §16).

CLI: ``python -m agentes.sonda_hooks`` (0 si el 100 % dio ``exit 2``; 1 si algún caso se filtró).
"""
from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from engine import comun as motor

_RAIZ_CODIGO = Path(__file__).resolve().parents[1]
_HOOKS_DIR = _RAIZ_CODIGO / "agentes" / "hooks"
_VENV_PYTHON = _RAIZ_CODIGO / ".venv" / "bin" / "python"
_LIMITES_BASE = _RAIZ_CODIGO / "tests" / "fixtures" / "engine" / "empresa_prueba" / "limites.yaml"
_PARAMETROS_BASE = _RAIZ_CODIGO / "tests" / "fixtures" / "engine" / "empresa_prueba" / "parametros.yaml"

OFERTA_ID = "OF-202611-01"
HASH_CONFIG = "sha256:" + "ab" * 32

__all__ = [
    "OFERTA_ID", "HASH_CONFIG", "Caso", "construir_empresa_de_prueba", "casos", "correr",
    "ejecutar_caso", "escribir_infra", "escribir_limites", "escribir_parametros", "escribir_sello", "main",
]


# ----------------------------------------------------------------------------------------------
# Constructor de una «empresa» de prueba desechable (reutilizado por tests/agentes/*)
# ----------------------------------------------------------------------------------------------
def _entrada_parametro(valor: Any, unidad: str = "unidad") -> dict[str, Any]:
    return {"valor": valor, "unidad": unidad, "hipotesis": True, "fuente": "sonda_hooks [HIPÓTESIS]", "ultima_calibracion": None}


def escribir_limites(tmp: Path, *, max_budget_por_corrida_agente: int | None = 500,
                     cuentas_permitidas: Sequence[str] = ("act_100000000000001",)) -> None:
    """Copia la fixture de límites de B1 (ya válida y completa) con el presupuesto de agentes ajustado."""
    datos = yaml.safe_load(_LIMITES_BASE.read_text(encoding="utf-8"))
    datos["max_budget_por_corrida_agente"] = max_budget_por_corrida_agente
    datos["cuentas_permitidas"] = list(cuentas_permitidas)
    from scripts.validar_esquemas import sello_de_limites
    datos["sello"] = {"hash": sello_de_limites(datos), "firmado_por": "dueno-de-prueba", "firmado_en": "2026-11-06T12:00:00Z"}
    destino = tmp / "empresa" / "limites.yaml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")


def escribir_parametros(tmp: Path, *, estado_max_edad_h: int = 6) -> None:
    """Copia la fixture de parámetros de B1 (válida y completa) con el grupo ``agentes`` relleno."""
    datos = yaml.safe_load(_PARAMETROS_BASE.read_text(encoding="utf-8"))
    datos["grupos"]["agentes"] = {
        "claude_version_min": _entrada_parametro("2.1.314", "semver"),
        "modelo": _entrada_parametro("claude-sonnet-5", "modelo"),
        "fallback_modelo": _entrada_parametro(None, "modelo"),
        "esfuerzo": _entrada_parametro("medium", "nivel"),
        "tiempo_s_max": _entrada_parametro({"D3": {"maker": 1200, "qa": 900}}, "segundos"),
        "turnos_max": _entrada_parametro({"D3": {"maker": 40, "qa": 20}}, "turnos"),
        "holgura_pct": _entrada_parametro(10, "porcentaje"),
        "reintentos_transitorios_max": _entrada_parametro(2, "reintentos"),
        "backoff_base_s": _entrada_parametro(60, "segundos"),
        "reintentos_validacion_max": _entrada_parametro(2, "reintentos"),
        "gracia_s": _entrada_parametro(10, "segundos"),
        "pausa_poll_s": _entrada_parametro(5, "segundos"),
        "bucle_repeticion_max": _entrada_parametro(3, "repeticiones"),
        "bucle_sin_progreso_turnos": _entrada_parametro(8, "turnos"),
        "estado_max_edad_h": _entrada_parametro(estado_max_edad_h, "horas"),
        "bash_timeout_defecto_ms": _entrada_parametro(120000, "milisegundos"),
        "bash_timeout_max_ms": _entrada_parametro(600000, "milisegundos"),
        "hook_timeout_s": _entrada_parametro(15, "segundos"),
    }
    destino = tmp / "empresa" / "parametros.yaml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")


def escribir_infra(tmp: Path, *, horas_atras: float = 0.0, verde: bool = True) -> None:
    """``empresa/infra/estado.json`` VERDE y fresco (o viejo/rojo si se pide), con una firma (no
    criptográfica: los hooks no verifican la firma de infra, solo que esté presente, H7)."""
    ahora = datetime.now(timezone.utc)
    generado = ahora - timedelta(hours=horas_atras)
    estado = {
        "modo": "vivo",
        "semaforo": "VERDE" if verde else "ROJO",
        "items": [{"id": "SONDA", "estado": "VERDE" if verde else "ROJO"}],
        "generado_en": generado.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "valido_hasta": (generado + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "firma": "hmac-sha256:" + "00" * 64,
    }
    destino = tmp / "empresa" / "infra" / "estado.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")


_CLAVE_PRIVADA: Path | None = None
_CLAVE_PUBLICA: str | None = None


def _par_de_claves_de_prueba() -> tuple[Path, str]:
    """Par Ed25519 efímero (uno por proceso, ``ssh-keygen`` local, sin red), igual técnica que
    ``tests/engine/apoyo.par_de_claves`` pero sin importar el paquete de pruebas desde producción."""
    global _CLAVE_PRIVADA, _CLAVE_PUBLICA
    if _CLAVE_PRIVADA is None:
        carpeta = Path(tempfile.mkdtemp(prefix="sonda-claves-"))
        atexit.register(shutil.rmtree, carpeta, True)
        ruta = carpeta / "sonda"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "sonda", "-f", str(ruta)],
                      check=True, capture_output=True, timeout=30)
        _CLAVE_PRIVADA = ruta
        _CLAVE_PUBLICA = Path(str(ruta) + ".pub").read_text(encoding="utf-8").strip()
    return _CLAVE_PRIVADA, _CLAVE_PUBLICA


def escribir_sello(tmp: Path, *, oferta_id: str = OFERTA_ID, object_ids: Sequence[str] = ("111", "222"),
                   hash_config: str = HASH_CONFIG, vencido: bool = False, firmar: bool = True) -> str | None:
    """Un sello en ``empresa/compliance/sellos/<hash_config>.json``. Con ``firmar=True`` (por
    defecto) la firma es una Ed25519 REAL de un par efímero: devuelve la clave PÚBLICA para que el
    caso la ponga en ``FABRICA_FIRMA_PUBLICA`` y así pruebe la rama de ``object_ids``/campos, no la
    de «sin firma». Con ``firmar=False`` la firma queda mal formada a propósito."""
    vigencia = datetime.now(timezone.utc) + (timedelta(hours=-1) if vencido else timedelta(hours=24))
    sello: dict[str, Any] = {
        "schema_version": "1.0.0", "oferta_id": oferta_id, "etapa_objetivo": "D7",
        "artefacto_sha256": hash_config, "reglas_version": "1.0.0",
        "emitido_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vigencia_hasta": vigencia.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "object_ids": list(object_ids), "dictamen_ref": "qa/x1-d7-v1.json",
        "dictamen_sha256": "sha256:" + "cd" * 32,
    }
    publica = None
    if firmar:
        privada, publica = _par_de_claves_de_prueba()
        sello["firma"] = motor.firmar_ed25519(motor.json_canonico(sello), privada, timeout_s=30)
    else:
        sello["firma"] = "ed25519:" + "A" * 96
    destino = tmp / "empresa" / "compliance" / "sellos" / f"{hash_config}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(sello, ensure_ascii=False), encoding="utf-8")
    return publica


def construir_empresa_de_prueba(tmp: Path, *, pausa: bool = False, max_budget_por_corrida_agente: int | None = 500,
                                 infra_horas_atras: float = 0.0, infra_verde: bool = True,
                                 estado_max_edad_h: int = 6, con_aprobacion: bool = True,
                                 oferta_id: str = OFERTA_ID) -> Path:
    """Raíz temporal con una «empresa» mínima y verde, lista para que los hooks corran sobre ella."""
    (tmp / "empresa").mkdir(parents=True, exist_ok=True)
    escribir_limites(tmp, max_budget_por_corrida_agente=max_budget_por_corrida_agente)
    escribir_parametros(tmp, estado_max_edad_h=estado_max_edad_h)
    escribir_infra(tmp, horas_atras=infra_horas_atras, verde=infra_verde)
    if pausa:
        (tmp / "empresa" / "PAUSA").write_text("", encoding="utf-8")
    if con_aprobacion:
        aprobacion = tmp / "ofertas" / oferta_id / "07-campana" / "aprobacion.json"
        aprobacion.parent.mkdir(parents=True, exist_ok=True)
        aprobacion.write_text(json.dumps({"aprobado": True}), encoding="utf-8")
    return tmp


# ----------------------------------------------------------------------------------------------
# Un caso de la sonda: entrada por stdin + entorno -> SIEMPRE debe dar exit 2
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Caso:
    nombre: str
    hook: str
    entrada: Mapping[str, Any]
    preparar_env: Callable[[Path], Mapping[str, str]]
    descripcion: str = ""
    estado_crudo: str | None = None  # para casos sin entrada JSON válida (prueba fail-closed)


def _env_comun(tmp: Path, *, oferta_id: str = OFERTA_ID, staging: str | None = None) -> dict[str, str]:
    env = {
        "AGENT_RAIZ": str(tmp), "AGENT_RUN_ID": "RUN-SONDA-0001", "AGENT_ROL": "maker",
        "AGENT_ETAPA": "D3", "AGENT_OFERTA_ID": oferta_id,
        "AGENT_SPOOL": str(tmp / "empresa" / "registro.jsonl"),
        "AGENT_NOMBRE": "d3-maker",
    }
    if staging is not None:
        env["AGENT_STAGING"] = str(tmp / staging)
    return env


def casos() -> list[Caso]:
    """El banco de entradas sintéticas (docs/09 §14.6), con ``>= 1`` prueba por mecanismo descrito."""

    def _activar_sin_sello(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)  # sin sello: ningún archivo en empresa/compliance/sellos/
        return _env_comun(tmp)

    def _object_ids_de_mas(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        publica = escribir_sello(tmp, object_ids=("111", "222"))  # el tool_input pide 111,222,333
        return {**_env_comun(tmp), "FABRICA_FIRMA_PUBLICA": publica or ""}

    def _update_daily_budget(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        return _env_comun(tmp)

    def _generate_con_pausa(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp, pausa=True)
        return _env_comun(tmp, staging=f"ofertas/{OFERTA_ID}/D6/.staging/RUN-SONDA-0001")

    def _estado_viejo(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp, infra_horas_atras=7417.5)
        return _env_comun(tmp, staging=f"ofertas/{OFERTA_ID}/D3/.staging/RUN-SONDA-0001")

    def _escribir_limites_yaml(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        staging = f"ofertas/{OFERTA_ID}/D3/.staging/RUN-SONDA-0001"
        return _env_comun(tmp, staging=staging)

    def _secreto_en_argumento(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        return _env_comun(tmp, staging=f"ofertas/{OFERTA_ID}/D3/.staging/RUN-SONDA-0001")

    def _limites_ausentes(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp, max_budget_por_corrida_agente=None)
        return _env_comun(tmp, staging=f"ofertas/{OFERTA_ID}/D3/.staging/RUN-SONDA-0001")

    def _sin_raiz(_tmp: Path) -> Mapping[str, str]:
        return {"AGENT_ROL": "maker"}  # a propósito: sin AGENT_RAIZ -> ValueError -> exit 2

    def _discard_draft_changes(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        publica = escribir_sello(tmp)
        return {**_env_comun(tmp), "FABRICA_FIRMA_PUBLICA": publica or ""}

    def _ads_delete(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        return _env_comun(tmp)

    def _ads_catalog(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        return _env_comun(tmp)

    def _bash_metacaracter(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        return _env_comun(tmp, staging=f"ofertas/{OFERTA_ID}/D3/.staging/RUN-SONDA-0001")

    def _bash_ruta_fuera(tmp: Path) -> Mapping[str, str]:
        construir_empresa_de_prueba(tmp)
        return _env_comun(tmp, staging=f"ofertas/{OFERTA_ID}/D3/.staging/RUN-SONDA-0001")

    return [
        Caso("activar_sin_sello", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_100000000000001", "entity_type": "campaign", "entity_id": "111",
                            "object_ids": ["222"], "publish_as_active": True, "allow_partial_publish": False}},
            _activar_sin_sello, "activar sin sello vigente"),
        Caso("object_ids_de_mas", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "tool_input": {"ad_account_id": "act_100000000000001", "entity_type": "campaign", "entity_id": "111",
                            "object_ids": ["222", "333"], "publish_as_active": True, "allow_partial_publish": False}},
            _object_ids_de_mas, "object_ids con uno de más respecto del sello"),
        Caso("update_entity_daily_budget", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__claude_ai_Meta_ADS__ads_update_entity",
             "tool_input": {"entity_id": "111", "entity_type": "ad_set", "fields": json.dumps({"daily_budget": 50000})}},
            _update_daily_budget, "ads_update_entity con un campo de presupuesto (H9)"),
        Caso("generate_con_pausa", "pretooluse_gasto.py",
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__claude_ai_Higgsfield__generate_image", "tool_input": {}},
            _generate_con_pausa, "herramienta de créditos con PAUSA activa"),
        Caso("estado_infra_viejo", "pretooluse_gasto.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Write",
             "tool_input": {"file_path": "__STAGING__/oferta.json", "content": "{}"}},
            _estado_viejo, "estado.json de hace más de estado_max_edad_h"),
        Caso("escribir_limites_yaml", "pretooluse_gasto.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Edit",
             "tool_input": {"file_path": "__RAIZ__/empresa/limites.yaml", "old_string": "a", "new_string": "b"}},
            _escribir_limites_yaml, "Edit sobre una ruta protegida (empresa/limites.yaml)"),
        Caso("secreto_en_argumento", "pretooluse_gasto.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Write",
             "tool_input": {"file_path": "__STAGING__/oferta.json", "content": "sk" + "_live_abcdefghijklmnop"}},
            _secreto_en_argumento, "tool_input con un patrón de secreto (sk_live_…)"),
        Caso("limites_ausentes", "pretooluse_gasto.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Write",
             "tool_input": {"file_path": "__STAGING__/oferta.json", "content": "{}"}},
            _limites_ausentes, "max_budget_por_corrida_agente en null"),
        Caso("json_roto", "pretooluse_gasto.py", {}, _bash_metacaracter, "entrada no es JSON válido",
            estado_crudo="no-json-en-absoluto"),
        Caso("excepcion_forzada_sin_raiz", "pretooluse_gasto.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "/x", "content": "x"}},
            _sin_raiz, "sin AGENT_RAIZ: excepción forzada"),
        Caso("bash_meta_activar_modo_live", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": f"python -m meta.activar --oferta {OFERTA_ID} --campana ofertas/{OFERTA_ID}/07-campana/campana.json "
                                       f"--ids-meta ofertas/{OFERTA_ID}/07-campana/ids_meta.json --hash-config {HASH_CONFIG} "
                                       "--cuenta ofertas/x/cuenta.json --monto 5000 --moneda EUR --modo live"}},
            _activar_sin_sello, "python -m meta.activar --modo live sin sello (SB-1)"),
        Caso("bash_meta_crear_modo_igual_live", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": f"python3 scripts/meta_crear.py --oferta {OFERTA_ID} --ids-meta ofertas/{OFERTA_ID}/07-campana/ids_meta.json "
                                       f"--hash-config {HASH_CONFIG} --modo=live"}},
            _activar_sin_sello, "meta_crear.py --modo=live sin sello (SB-1)"),
        Caso("bash_orq_activar_live", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": f"python -m engine.orq activar --oferta {OFERTA_ID} --hash-config {HASH_CONFIG} --live --object-ids 111 222"}},
            _activar_sin_sello, "python -m engine.orq activar --live sin sello (SB-1)"),
        Caso("bash_activar_ids_meta_fuera", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": f"python -m meta.activar --oferta {OFERTA_ID} --ids-meta ../../etc/ids.json "
                                       f"--hash-config {HASH_CONFIG} --modo live"}},
            _activar_sin_sello, "--ids-meta fuera de la carpeta de la oferta (SB-1)"),
        Caso("discard_draft_changes", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__claude_ai_Meta_ADS__ads_update_entity",
             "tool_input": {"entity_id": "111", "entity_type": "ad", "fields": json.dumps({"status": "PAUSED"}),
                            "discard_draft_changes": True}},
            _discard_draft_changes, "discard_draft_changes distinto de falso"),
        Caso("ads_delete", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__claude_ai_Meta_ADS__ads_delete_creative",
             "tool_input": {"id": "111"}}, _ads_delete, "ads_delete_* siempre prohibida"),
        Caso("ads_catalog", "pretooluse_activacion.py",
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__claude_ai_Meta_ADS__ads_catalog_create",
             "tool_input": {"id": "111"}}, _ads_catalog, "ads_catalog_* siempre prohibida"),
        Caso("bash_metacaracter", "pretooluse_bash.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": "python3 scripts/validar_esquemas.py oferta ofertas/_ejemplo; rm -rf /"}},
            _bash_metacaracter, "punto y coma en el comando de Bash"),
        Caso("bash_ruta_fuera", "pretooluse_bash.py",
            {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": "python3 scripts/validar_esquemas.py oferta ../../.env"}},
            _bash_ruta_fuera, "argumento de ruta fuera de ofertas/<id>/"),
    ]


def ejecutar_caso(caso: Caso) -> tuple[int, str]:
    """Corre UN caso en una raíz temporal desechable; devuelve ``(codigo_salida, stderr)``."""
    with tempfile.TemporaryDirectory(prefix="sonda-hooks-") as tmp_str:
        tmp = Path(tmp_str)
        env = dict(caso.preparar_env(tmp))
        staging_resuelto = env.pop("AGENT_STAGING", None)
        if staging_resuelto:
            Path(staging_resuelto).mkdir(parents=True, exist_ok=True)
            env["AGENT_STAGING"] = staging_resuelto
        entrada_json = caso.estado_crudo if caso.estado_crudo is not None else json.dumps(_sustituir(caso.entrada, tmp, staging_resuelto))
        proc = subprocess.run(
            [str(_VENV_PYTHON), str(_HOOKS_DIR / caso.hook)], input=entrada_json, env=env,
            capture_output=True, text=True, timeout=30, cwd=str(_RAIZ_CODIGO),
        )
        return proc.returncode, proc.stderr


def _sustituir(obj: Any, raiz: Path, staging: str | None) -> Any:
    """Reemplaza los marcadores ``__RAIZ__``/``__STAGING__`` por rutas absolutas reales."""
    if isinstance(obj, str):
        obj = obj.replace("__RAIZ__", str(raiz))
        if staging:
            obj = obj.replace("__STAGING__", staging)
        return obj
    if isinstance(obj, Mapping):
        return {k: _sustituir(v, raiz, staging) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sustituir(v, raiz, staging) for v in obj]
    return obj


def correr(bank: Sequence[Caso] | None = None) -> dict[str, Any]:
    """Corre todo el banco; devuelve ``{"ok": bool, "casos": {nombre: {"exit":n,"ok":bool,...}}}``."""
    resultados: dict[str, Any] = {}
    todo_ok = True
    for caso in bank if bank is not None else casos():
        codigo, stderr = ejecutar_caso(caso)
        ok = codigo == 2
        todo_ok = todo_ok and ok
        resultados[caso.nombre] = {"exit": codigo, "ok": ok, "descripcion": caso.descripcion, "stderr": stderr[:300]}
    return {"ok": todo_ok, "casos": resultados}


def main(argv: Sequence[str] | None = None) -> int:  # noqa: ARG001
    resumen = correr()
    print(json.dumps(resumen, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if resumen["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
