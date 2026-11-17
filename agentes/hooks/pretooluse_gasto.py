#!/usr/bin/env python3
"""``pretooluse_gasto.py`` — bloquea gasto/escritura si falta límite, hay ``PAUSA`` o infra no verde.

Evento ``PreToolUse``, sin matcher (corre para TODA herramienta). Clasifica ``tool_name`` con
``agentes/hooks/herramientas.yaml``: las lecturas pasan siempre; todo lo demás (incluido lo
desconocido, docs/09 §14.2) exige PAUSA ausente, límites completos e infra VERDE y fresca.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # bootstrap: ver agentes/hooks/_comun.py

from agentes.hooks import _comun as c  # noqa: E402
from engine import comun as motor  # noqa: E402
from engine import limites as motor_limites  # noqa: E402
from engine import parametros as motor_parametros  # noqa: E402
from engine.errores import ErrorFabrica  # noqa: E402
from scripts.validar_esquemas import infra_verde  # noqa: E402

PARAM_ESTADO_MAX_EDAD_H = "agentes.estado_max_edad_h"
PARAM_CREDITOS_MAX_PIEZA = "creditos_max_pieza"      # en empresa/limites.yaml, no en parametros
PARAM_CREDITOS_MAX_OFERTA = "creditos_max_oferta"


def _infra_verde_o_motivo(raiz: Path) -> str | None:
    """``None`` si la infraestructura está VERDE y fresca; si no, el motivo del bloqueo."""
    ruta = raiz / "empresa" / "infra" / "estado.json"
    try:
        estado = motor.cargar_json(ruta)
    except FileNotFoundError:
        return "infra no verde / vencida: falta empresa/infra/estado.json"
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return f"infra no verde / vencida: empresa/infra/estado.json ilegible ({exc})"
    if not isinstance(estado, dict):
        return "infra no verde / vencida: empresa/infra/estado.json no es un objeto"
    if not str(estado.get("firma") or "").strip():
        return "infra no verde / vencida: empresa/infra/estado.json sin firma"
    try:
        parametros = motor_parametros.cargar_parametros(raiz / "empresa" / "parametros.yaml")
        max_horas = parametros.valor(PARAM_ESTADO_MAX_EDAD_H)
    except ErrorFabrica as exc:
        return f"infra no verde / vencida: no se pudo leer {PARAM_ESTADO_MAX_EDAD_H} ({exc.mensaje})"
    if isinstance(max_horas, bool) or not isinstance(max_horas, int) or max_horas < 1:
        return f"infra no verde / vencida: {PARAM_ESTADO_MAX_EDAD_H} inválido"
    verde, motivo = infra_verde(estado, motor.ahora_utc, max_horas)
    return None if verde else f"infra no verde / vencida: {motivo}"


def _limite_insuficiente_o_motivo(raiz: Path, env: Mapping[str, str]) -> str | None:
    """``None`` si ``limites.yaml`` trae ``max_budget_por_corrida_agente``; si no, el motivo."""
    try:
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        lim.valor("max_budget_por_corrida_agente")
    except ErrorFabrica as exc:
        return f"falta límite para correr agentes: {exc.mensaje}"
    return None


def _limite_creditos_o_motivo(raiz: Path, env: Mapping[str, str], tool_input: Mapping[str, Any]) -> str | None:
    """``None`` si una herramienta de créditos trae cotización previa y cabe en los topes."""
    try:
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        max_pieza = lim.valor(PARAM_CREDITOS_MAX_PIEZA)
        max_oferta = lim.valor(PARAM_CREDITOS_MAX_OFERTA)
    except ErrorFabrica as exc:
        return f"falta límite de créditos: {exc.mensaje}"
    previo_raw = (env.get("AGENT_COSTO_PREVIO") or "").strip()
    if not previo_raw:
        return "herramienta de créditos sin AGENT_COSTO_PREVIO (cotización previa obligatoria)"
    try:
        previo = int(previo_raw)
    except ValueError:
        return "AGENT_COSTO_PREVIO ilegible (se espera un entero de créditos)"
    cotizado_raw = tool_input.get("cotizacion_creditos") if isinstance(tool_input, Mapping) else None
    cotizado = cotizado_raw if isinstance(cotizado_raw, int) and not isinstance(cotizado_raw, bool) else previo
    if previo < cotizado:
        return f"AGENT_COSTO_PREVIO ({previo}) es menor que la cotización ({cotizado})"
    if previo > max_pieza:
        return f"créditos de la pieza ({previo}) superan creditos_max_pieza ({max_pieza})"
    acumulado_raw = (env.get("AGENT_COSTO_ACUMULADO_OFERTA") or "0").strip()
    try:
        acumulado = int(acumulado_raw)
    except ValueError:
        return "AGENT_COSTO_ACUMULADO_OFERTA ilegible (se espera un entero de créditos)"
    if acumulado + previo > max_oferta:
        return f"créditos acumulados de la oferta ({acumulado + previo}) superan creditos_max_oferta ({max_oferta})"
    return None


def _ruta_protegida(raiz: Path, ruta: Path) -> bool:
    """¿``ruta`` cae en una carpeta que ningún agente debe editar (piso de convenciones §1)?"""
    protegidas = (
        raiz / ".claude", raiz / "contratos", raiz / "empresa" / "limites.yaml",
        raiz / "empresa" / "parametros.yaml", raiz / "empresa" / "compliance" / "sellos",
        raiz / "empresa" / "PAUSA", raiz / "agentes" / "hooks",
    )
    return any(c.ruta_dentro_de(ruta, p) for p in protegidas)


def _comprobar_escritura(datos: Mapping[str, Any], env: Mapping[str, str]) -> str | None:
    raiz = c.raiz_agente(env)
    tool_name = str(datos.get("tool_name") or "")
    tool_input = datos.get("tool_input") if isinstance(datos.get("tool_input"), Mapping) else {}

    if (raiz / "empresa" / "PAUSA").exists():
        return "PAUSA activa: solo se permiten lecturas"

    motivo_limite = _limite_insuficiente_o_motivo(raiz, env)
    if motivo_limite:
        return motivo_limite

    motivo_infra = _infra_verde_o_motivo(raiz)
    if motivo_infra:
        return motivo_infra

    if c.es_herramienta_de_creditos(tool_name):
        motivo_creditos = _limite_creditos_o_motivo(raiz, env, tool_input)
        if motivo_creditos:
            return motivo_creditos

    if tool_name in ("Write", "Edit", "NotebookEdit"):
        file_path = tool_input.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            return f"{tool_name} sin file_path"
        staging = (env.get("AGENT_STAGING") or "").strip()
        ruta = Path(file_path)
        dentro_de_staging = bool(staging) and c.ruta_dentro_de(ruta, Path(staging))
        if not dentro_de_staging or _ruta_protegida(raiz, ruta):
            return f"{tool_name} fuera de AGENT_STAGING o en ruta protegida: {file_path}"

    if c.contiene_secreto(tool_input):
        return "tool_input contiene un patrón de secreto"
    return None


def manejar(datos: Mapping[str, Any]) -> str | None:
    import os

    if datos.get("hook_event_name") not in (None, "PreToolUse"):
        return None
    tool_name = str(datos.get("tool_name") or "")
    clase = c.clasificar_herramienta(tool_name)
    if clase == "lectura" or clase == "neutra":
        return None
    motivo = _comprobar_escritura(datos, os.environ)
    if motivo:
        c.anotar_spool(os.environ, c.construir_entrada_registro(
            os.environ, evento="PreToolUse", tool=tool_name, tool_use_id=datos.get("tool_use_id"),
            entrada={}, resultado="deny",
        ))
    return motivo


if __name__ == "__main__":
    c.ejecutar(manejar)
