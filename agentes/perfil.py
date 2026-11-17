"""``agentes.perfil`` — construye ``settings.efectivo.json`` y el entorno de UNA corrida (docs/09 §6.1, §3.3).

Puro: no lanza procesos ni toca disco salvo el JSON del esquema que lee para ``--json-schema``
(lectura, no efecto). El runner usa estas funciones; la CLI imprime ambas cosas sin secretos
(docs/06 §4.6: "imprime settings.efectivo.json y el entorno sin secretos").
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun as motor
from agentes.tipos import EspecCorrida, espec_desde_mapa

__all__ = [
    "CLAVES_ENTORNO_EXTERNO_PERMITIDAS", "construir_argv", "construir_entorno",
    "construir_settings_efectivo", "exigir_sin_secretos_prohibidos", "main", "ruta_staging_relativa",
]

# Única puerta de entrada de variables del proceso PADRE al entorno del hijo: todo lo demás se
# construye desde cero (docs/09 §3.3, "el runner construye el entorno desde cero, no hereda el del padre").
CLAVES_ENTORNO_EXTERNO_PERMITIDAS = ("ANTHROPIC_API_KEY", "FABRICA_FIRMA_PUBLICA")

# Nunca en el entorno del hijo (docs/09 §3.3): credenciales de dinero, sellos y tokens de automatización.
_PATRON_CLAVE_PROHIBIDA = re.compile(
    r"(STRIPE|META_TOKEN|META_APP_SECRET|META_AD_ACCOUNT|SELLO_|GITHUB_TOKEN|_WHSEC|INGEST_HMAC|"
    r"REGISTRO_HMAC|LATIDO_HMAC|PREFLIGHT_HMAC|DESCARGA_HMAC|CORREO_API_KEY|LIMITES_HASH_ANCLA)",
    re.IGNORECASE,
)


def ruta_staging_relativa(espec: EspecCorrida, run_id: str) -> str:
    """Carpeta de staging del Maker, relativa a la raíz; ``()`` conceptual (sin ruta) para el QA.

    Decisión de diseño (ver ``agentes/README.md``, «Decisiones»): se usa el CÓDIGO de etapa
    (``D3``) tal cual como nombre de carpeta bajo ``ofertas/<id>/``; mapearlo al nombre numerado
    real del backbone (``03-oferta``) es tarea de quien integre con ``engine.orq`` (B1).
    """
    if espec.oferta_id:
        return f"ofertas/{espec.oferta_id}/{espec.etapa}/.staging/{run_id}"
    return f"empresa/runs/{run_id}/staging"


def construir_settings_efectivo(espec: EspecCorrida, raiz: Path) -> dict[str, Any]:
    """``settings.efectivo.json`` de la corrida (docs/09 §6.1): ``allow`` mínimo del rol + ``deny`` adicional.

    El Maker NO recibe un ``deny`` de su propio staging; el QA sí conserva el ``deny`` completo de
    ``empresa/runs/**`` y de TODO ``.staging/**`` (no ve el razonamiento de ningún Maker, §10).
    """
    base = f"//{raiz}"
    deny = ["mcp__*"]
    allow = ["Read", "Grep", "Glob"]
    if espec.rol == "maker":
        allow += list(espec.allow)
        deny.append(f"Read({base}/empresa/runs/**)")
    else:
        deny.append(f"Read({base}/empresa/runs/**)")
        deny.append(f"Read({base}/ofertas/*/.staging/**)")
    return {
        "disableClaudeAiConnectors": True,
        "disableSkillShellExecution": True,
        "permissions": {"allow": allow, "deny": deny},
    }


def exigir_sin_secretos_prohibidos(entorno: Mapping[str, str]) -> None:
    """Red de seguridad: ``ValueError`` si, por error, el entorno construido trae una clave o un
    valor con forma de credencial prohibida. Por construcción nunca debería pasar; se comprueba
    de todos modos (nunca se confía ciegamente en la propia construcción)."""
    for clave, valor in entorno.items():
        if _PATRON_CLAVE_PROHIBIDA.search(clave):
            raise ValueError(f"el entorno del hijo no debe incluir la clave {clave!r}")
        if isinstance(valor, str) and motor.enmascarar_secretos(valor) != valor:
            raise ValueError(f"el entorno del hijo tiene un valor con forma de secreto en {clave!r}")


def construir_entorno(espec: EspecCorrida, *, run_id: str, raiz: Path, staging_relativa: str,
                      parametros_agentes: Mapping[str, Any], env_externo: Mapping[str, str] | None = None
                      ) -> dict[str, str]:
    """Entorno MÍNIMO del hijo, construido desde cero (docs/09 §3.3). Nunca hereda ``os.environ``
    completo: solo copia, de ``env_externo``, las claves de :data:`CLAVES_ENTORNO_EXTERNO_PERMITIDAS`.
    """
    externo = env_externo if env_externo is not None else {}
    entorno: dict[str, str] = {}
    for clave in CLAVES_ENTORNO_EXTERNO_PERMITIDAS:
        valor = externo.get(clave)
        if valor:
            entorno[clave] = str(valor)
    entorno.update({
        "CLAUDE_CONFIG_DIR": str(raiz / "empresa" / "runs" / run_id / ".claude-config"),
        "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
        "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
        "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "AGENT_RUN_ID": run_id,
        "AGENT_ROL": espec.rol,
        "AGENT_ETAPA": espec.etapa,
        "AGENT_OFERTA_ID": espec.oferta_id or "",
        "AGENT_RAIZ": str(raiz),
        "AGENT_STAGING": str(raiz / staging_relativa) if espec.rol == "maker" else "",
        "AGENT_CONTRATO": espec.contrato_salida,
        "AGENT_ARTEFACTOS_ESPERADOS": ",".join(espec.artefactos_esperados),
        "AGENT_SPOOL": str(raiz / "empresa" / "runs" / run_id / "herramientas.jsonl"),
        "AGENT_NOMBRE": espec.agente,
    })
    if espec.rol == "qa":
        entorno["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] = "1"
    if "bash_timeout_defecto_ms" in parametros_agentes:
        entorno["BASH_DEFAULT_TIMEOUT_MS"] = str(parametros_agentes["bash_timeout_defecto_ms"])
    if "bash_timeout_max_ms" in parametros_agentes:
        entorno["BASH_MAX_TIMEOUT_MS"] = str(parametros_agentes["bash_timeout_max_ms"])
    exigir_sin_secretos_prohibidos(entorno)
    return entorno


_RAIZ_CODIGO = Path(__file__).resolve().parents[1]  # agentes/perfil.py -> agentes -> raíz del repositorio


def _esquema_minificado(contrato_salida: str) -> str:
    """Contenido de ``contratos/<contrato_salida>`` como JSON de una línea (para ``--json-schema``).

    ``contratos/`` es CÓDIGO, no datos de una oferta: se lee SIEMPRE de la raíz del repositorio
    (``_RAIZ_CODIGO``), nunca de la raíz de datos (``FABRICA_RAIZ``) que usa el resto de la corrida
    (mismo criterio que ``scripts.validar_esquemas.DIR_CONTRATOS``; evita que una raíz temporal de
    pruebas sin ``contratos/`` rompa la construcción del argv).
    """
    datos = motor.cargar_json(_RAIZ_CODIGO / contrato_salida)
    return json.dumps(datos, separators=(",", ":"), ensure_ascii=False)


def construir_argv(espec: EspecCorrida, *, run_id: str, raiz: Path, settings_relativa: str,
                   presupuesto_cli_usd: str) -> list[str]:
    """Línea de comando canónica (docs/09 §3.1), reutilizando las banderas de aislamiento de
    ``scripts/lanzar_hijos.py`` (``--strict-mcp-config``, ``--disallowedTools mcp__*``,
    ``--settings`` con ``disableClaudeAiConnectors``, ``--permission-mode dontAsk``). El encargo va
    por STDIN (como en ``lanzar_hijos.py``), no como argumento.
    """
    return [
        "claude", "-p",
        "--agent", espec.agente,
        "--model", espec.modelo,
        "--effort", espec.esfuerzo,
        "--output-format", "stream-json", "--verbose", "--include-hook-events",
        "--json-schema", _esquema_minificado(espec.contrato_salida),
        "--max-turns", str(espec.presupuesto.turnos_max),
        "--max-budget-usd", presupuesto_cli_usd,
        "--permission-mode", "dontAsk", "--permission-prompts", "none",
        "--tools", ",".join(espec.herramientas),
        "--strict-mcp-config", "--disallowedTools", "mcp__*",
        "--settings", str(raiz / settings_relativa), "--setting-sources", "project",
        "--session-id", run_id, "--no-session-persistence",
    ]


def _entorno_enmascarado(entorno: Mapping[str, str]) -> dict[str, str]:
    """Copia del entorno con todo valor que parezca un secreto enmascarado (para imprimir sin riesgo)."""
    return {k: motor.enmascarar_secretos(v) for k, v in entorno.items()}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI de solo lectura: ``python -m agentes.perfil --espec espec.json`` imprime
    ``settings.efectivo.json`` y el entorno del hijo (secretos enmascarados). Sin efectos."""
    ap = argparse.ArgumentParser(prog="python -m agentes.perfil", description=__doc__.splitlines()[0])
    ap.add_argument("--espec", required=True, type=Path)
    ap.add_argument("--run-id", default="RUN-PERFIL-0001")
    ap.add_argument("--raiz", type=Path, default=motor.raiz())
    args = ap.parse_args(argv)
    espec = espec_desde_mapa(json.loads(args.espec.read_text(encoding="utf-8")))
    staging = ruta_staging_relativa(espec, args.run_id)
    settings = construir_settings_efectivo(espec, args.raiz)
    entorno = construir_entorno(espec, run_id=args.run_id, raiz=args.raiz, staging_relativa=staging,
                                parametros_agentes={})
    print(json.dumps({"settings_efectivo": settings, "entorno": _entorno_enmascarado(entorno)},
                     sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
