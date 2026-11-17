#!/usr/bin/env python3
"""``stop_verificacion.py`` — exige que la salida valide contra el esquema (docs/09 §14.5).

Evento ``Stop`` (el matcher se ignora). **Maker**: valida cada artefacto de
``AGENT_ARTEFACTOS_ESPERADOS`` contra su contrato (``AGENT_CONTRATO``) con la misma función que
``scripts/validar_esquemas.py``. **QA**: sin acción propia (el CLI ya reintenta
``structured_output``); solo comprueba que el último mensaje mencione la clave ``veredicto``.

Es una cortesía que ahorra una ronda: el runner (``agentes.runner``) revalida siempre (§12.6), así
que este hook nunca es la única barrera. No corre si la sesión termina por turnos/presupuesto (H8).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # bootstrap: ver agentes/hooks/_comun.py

from agentes.hooks import _comun as c  # noqa: E402
from engine import comun as motor  # noqa: E402


def _nombre_schema(contrato: str) -> str:
    """``"contratos/oferta.schema.json"`` o ``"oferta"`` -> ``"oferta"`` (nombre que pide ``errores_de_esquema``)."""
    base = Path(contrato).name
    return base[: -len(".schema.json")] if base.endswith(".schema.json") else base


def _validar_maker(env: Mapping[str, str]) -> str | None:
    staging = (env.get("AGENT_STAGING") or "").strip()
    contrato = (env.get("AGENT_CONTRATO") or "").strip()
    artefactos_raw = (env.get("AGENT_ARTEFACTOS_ESPERADOS") or "").strip()
    if not staging or not contrato or not artefactos_raw:
        return None  # sin contexto suficiente para autoverificar; el runner sí revalida siempre
    nombre_schema = _nombre_schema(contrato)
    errores: list[str] = []
    for rel in artefactos_raw.split(","):
        rel = rel.strip()
        if not rel:
            continue
        ruta = Path(staging) / rel
        if not ruta.is_file():
            errores.append(f"{rel}: no existe en el staging")
            continue
        try:
            datos = motor.cargar_json(ruta)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            errores.append(f"{rel}: ilegible ({exc})")
            continue
        problemas = motor.errores_de_esquema(nombre_schema, datos)
        if problemas:
            primero = problemas[0]
            errores.append(f"{rel} inválido: {getattr(primero, 'message', str(primero))[:160]}")
    return "; ".join(errores) if errores else None


def manejar(datos: Mapping[str, Any]) -> dict[str, Any] | None:
    import os

    env = os.environ
    rol = (env.get("AGENT_ROL") or "").strip()
    if rol == "qa":
        mensaje = str(datos.get("last_assistant_message") or "")
        if "veredicto" in mensaje or datos.get("stop_hook_active"):
            return None
        return {"decision": "block", "reason": "el informe de QA debe incluir la clave «veredicto»"}

    motivo = _validar_maker(env)
    if motivo is None:
        return None
    if datos.get("stop_hook_active"):
        # Ya se avisó una vez (evita el bucle, tope de 8 del propio Stop): deja constancia en el
        # staging y deja pasar; el runner marcará estado=invalido al revalidar (§12.6).
        staging = Path(env.get("AGENT_STAGING") or ".")
        try:
            staging.mkdir(parents=True, exist_ok=True)
            (staging / "INVALIDO.json").write_text(
                json.dumps({"motivo": motivo}, ensure_ascii=False), encoding="utf-8",
            )
        except OSError:
            pass
        return None
    return {"decision": "block", "reason": f"{motivo}; corrige y vuelve a validar"}


if __name__ == "__main__":
    c.ejecutar_con_salida(manejar)
