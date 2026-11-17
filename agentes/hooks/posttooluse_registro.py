#!/usr/bin/env python3
"""``posttooluse_registro.py`` — anota cada llamada de herramienta en ``$AGENT_SPOOL`` (docs/09 §14.4).

Eventos ``PostToolUse`` y ``PostToolUseFailure``. Una línea JSON por llamada, con tamaño y hash del
archivo tocado (nunca ``tool_response`` ni contenido). Un fallo al escribir es ``exit 2``: una corrida
con el registro incompleto se invalida, igual que cualquier otro hook roto.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # bootstrap: ver agentes/hooks/_comun.py

from agentes.hooks import _comun as c  # noqa: E402
from engine import comun as motor  # noqa: E402

LARGO_MAX_COMANDO = 300  # parametrizable vía AGENT_REGISTRO_COMANDO_MAX (defensivo; no es un tope de dinero)


def _entrada_de_archivo(raiz: Path, file_path: str) -> dict[str, Any]:
    try:
        ruta_rel = str(Path(file_path).resolve().relative_to(raiz))
    except ValueError:
        ruta_rel = file_path
    entrada: dict[str, Any] = {"file_path": ruta_rel}
    try:
        datos = Path(file_path).read_bytes()
    except OSError:
        return entrada
    entrada["bytes"] = len(datos)
    entrada["sha256"] = motor.hash_bytes(datos)
    return entrada


def manejar(datos: Mapping[str, Any]) -> str | None:
    import os

    env = os.environ
    evento = str(datos.get("hook_event_name") or "PostToolUse")
    if evento not in ("PostToolUse", "PostToolUseFailure"):
        return None
    raiz = c.raiz_agente(env)
    tool_name = str(datos.get("tool_name") or "")
    tool_input = datos.get("tool_input") if isinstance(datos.get("tool_input"), Mapping) else {}
    entrada: dict[str, Any] = {}
    if tool_name in ("Read", "Write", "Edit", "NotebookEdit"):
        file_path = tool_input.get("file_path")
        if isinstance(file_path, str) and file_path:
            entrada = _entrada_de_archivo(raiz, file_path)
    elif tool_name == "Bash":
        comando = str(tool_input.get("command") or "")
        largo = int((env.get("AGENT_REGISTRO_COMANDO_MAX") or "").strip() or LARGO_MAX_COMANDO)
        entrada = {"command": comando[:largo]}
    resultado = "error" if evento == "PostToolUseFailure" else "ok"
    linea = c.construir_entrada_registro(
        env, evento=evento, tool=tool_name, tool_use_id=datos.get("tool_use_id"), entrada=entrada,
        resultado=resultado, duracion_ms=datos.get("duration_ms"),
    )
    c.anotar_spool(env, linea)
    return None


if __name__ == "__main__":
    c.ejecutar(manejar)
