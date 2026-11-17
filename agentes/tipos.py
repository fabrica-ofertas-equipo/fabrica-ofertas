"""Tipos de datos compartidos del runtime de agentes (docs/09-runtime-de-agentes.md §12.1).

Firmas congeladas: ``Modo``, ``Presupuesto``, ``EspecCorrida``, ``ResultadoCorrida``. ``PlanCorrida``
es la salida pura de :func:`agentes.runner.preparar` (sin equivalente textual exacto en la doc, pero
exigida por su firma: ``preparar(espec) -> PlanCorrida``).

Nada de este módulo tiene efectos: solo estructuras de datos y su validación básica.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Mapping

__all__ = [
    "CODIGO_POR_ESTADO", "EspecCorrida", "Modo", "PlanCorrida", "Presupuesto", "ResultadoCorrida",
    "espec_desde_mapa",
]


class Modo(str, Enum):
    """Modo de ejecución de una corrida de agente."""

    DRY_RUN = "dry-run"   # por defecto: construye argv/settings/env y los imprime; NO ejecuta
    FIXTURE = "fixture"   # sin proceso ni red: reproduce una corrida grabada
    LIVE = "live"         # exige --live y todo el preflight


@dataclass(frozen=True)
class Presupuesto:
    """Techos de UNA corrida. TODOS los valores salen de ``limites.yaml``/``parametros.yaml``."""

    usd_centavos_max: int    # <= limites.max_budget_por_corrida_agente
    tiempo_s_max: int        # parametros.agentes.tiempo_s_max[etapa][rol]
    turnos_max: int          # parametros.agentes.turnos_max[etapa][rol]


@dataclass(frozen=True)
class EspecCorrida:
    """Encargo completo de una corrida (un proceso ``claude -p`` por rol, docs/09 §3.1)."""

    rol: Literal["maker", "qa"]
    etapa: str                       # id fijo del backbone §3: "D3", "X1"...
    oferta_id: str | None            # None en etapas de empresa
    agente: str                      # nombre en .claude/agents, p. ej. "d3-maker"
    prompt_base: str                 # encargo; ruta a archivo o texto
    entradas: tuple[str, ...]        # rutas de solo lectura relativas a la raíz
    contrato_salida: str             # contratos/<x>.schema.json (structured_output)
    artefactos_esperados: tuple[str, ...]   # rutas relativas bajo staging; () en QA
    herramientas: tuple[str, ...]    # lista --tools
    allow: tuple[str, ...]           # reglas allow (Edit(//...), Bash(python3 scripts/... *))
    rutas_escribibles: tuple[str, ...]      # staging del Maker; () en QA
    presupuesto: Presupuesto
    modelo: str
    esfuerzo: str
    ronda: int = 1                   # ronda Maker<->QA (la lleva el motor)

    def __post_init__(self) -> None:
        if self.rol not in ("maker", "qa"):
            raise ValueError(f"EspecCorrida.rol inválido: {self.rol!r}")
        if not self.etapa or not isinstance(self.etapa, str):
            raise ValueError("EspecCorrida.etapa es obligatoria")
        if self.rol == "qa" and self.artefactos_esperados:
            raise ValueError("el QA no escribe artefactos (artefactos_esperados debe ser () en QA)")
        if self.rol == "qa" and self.rutas_escribibles:
            raise ValueError("el QA no tiene rutas escribibles (() en QA)")
        if self.ronda < 1:
            raise ValueError("EspecCorrida.ronda debe ser >= 1")


@dataclass(frozen=True)
class PlanCorrida:
    """Salida pura de :func:`agentes.runner.preparar`: lo que se ejecutaría, sin ejecutar nada."""

    run_id: str
    argv: tuple[str, ...]
    entorno: dict[str, str]           # entorno del hijo, YA sin secretos (ver agentes.perfil)
    settings_efectivo: dict[str, Any]
    staging_relativa: str             # ruta relativa bajo la raíz, única por run_id
    presupuesto_cli_usd: str          # cadena decimal (Decimal), con holgura ya aplicada


@dataclass
class ResultadoCorrida:
    """Resultado vinculante de una corrida (ya validado; ver docs/09 §12.6)."""

    run_id: str
    rol: str
    etapa: str
    oferta_id: str | None
    estado: Literal["ok", "invalido", "bloqueado", "pausa", "timeout", "presupuesto", "turnos", "bucle", "error", "preflight"]
    veredicto: str | None            # QA: PASS|PASS_CON_NOTAS|FAIL|ESCALAR; Maker: None
    salida: dict[str, Any] | None    # structured_output ya validado
    artefactos: list[dict[str, Any]] = field(default_factory=list)   # {ruta, sha256, bytes}
    costo: dict[str, Any] = field(default_factory=dict)              # {centavos_usd, moneda, es_estimacion, confiable, por_modelo}
    turnos: int = 0
    duracion_ms: int = 0
    session_id: str | None = None
    claude_version: str | None = None
    denegaciones: list[dict[str, Any]] = field(default_factory=list)
    registro_ruta: str = ""
    errores: list[str] = field(default_factory=list)

    def a_json(self) -> dict[str, Any]:
        """Representación JSON (serializable) del resultado, para stdout de la CLI."""
        return {
            "run_id": self.run_id, "rol": self.rol, "etapa": self.etapa, "oferta_id": self.oferta_id,
            "estado": self.estado, "veredicto": self.veredicto, "salida": self.salida,
            "artefactos": self.artefactos, "costo": self.costo, "turnos": self.turnos,
            "duracion_ms": self.duracion_ms, "session_id": self.session_id, "claude_version": self.claude_version,
            "denegaciones": self.denegaciones, "registro_ruta": self.registro_ruta, "errores": self.errores,
        }


def espec_desde_mapa(d: Mapping[str, Any]) -> EspecCorrida:
    """Reconstruye una :class:`EspecCorrida` desde un mapa (JSON de ``--espec``)."""
    presupuesto = d["presupuesto"]
    return EspecCorrida(
        rol=d["rol"], etapa=d["etapa"], oferta_id=d.get("oferta_id"), agente=d["agente"],
        prompt_base=d["prompt_base"], entradas=tuple(d.get("entradas") or ()),
        contrato_salida=d["contrato_salida"], artefactos_esperados=tuple(d.get("artefactos_esperados") or ()),
        herramientas=tuple(d.get("herramientas") or ()), allow=tuple(d.get("allow") or ()),
        rutas_escribibles=tuple(d.get("rutas_escribibles") or ()),
        presupuesto=Presupuesto(usd_centavos_max=presupuesto["usd_centavos_max"],
                                tiempo_s_max=presupuesto["tiempo_s_max"], turnos_max=presupuesto["turnos_max"]),
        modelo=d["modelo"], esfuerzo=d["esfuerzo"], ronda=int(d.get("ronda", 1)),
    )


# Código de salida de CLI por estado (docs/09 §12.1; convenciones §8).
CODIGO_POR_ESTADO: dict[str, int] = {
    "ok": 0,
    "invalido": 3,
    "bloqueado": 4,
    "pausa": 4,
    "preflight": 4,
    "presupuesto": 5,
    "turnos": 5,
    "timeout": 6,
    "bucle": 6,
    "error": 6,
}
