"""Tipo de hallazgo compartido por los lints de cumplimiento (``lint_claims``, ``html_checks``).

Un :class:`Hallazgo` es una coincidencia de una regla contra un texto, una pieza de HTML o un
metadato. El semáforo de un conjunto de hallazgos es el peor ``nivel`` (verde < amarillo < rojo,
``contratos/comunes.schema.json#/$defs/nivel_riesgo``): ante duda, el nivel más alto manda
(falla cerrado, ``compliance/README.md``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

__all__ = ["Hallazgo", "NIVELES", "ORDEN_NIVEL", "peor_nivel"]

NIVELES = ("verde", "amarillo", "rojo")
ORDEN_NIVEL = {nivel: indice for indice, nivel in enumerate(NIVELES)}


@dataclass(frozen=True)
class Hallazgo:
    """Una coincidencia de regla.

    ``patron_clave``: identificador estable de la regla que disparó (kebab-case, incluye la
    categoría: ``salud:cura``, ``html:casilla-premarcada``...). ``nivel``: verde, amarillo o rojo.
    ``categoria``: agrupación amplia (``salud``, ``finanzas``, ``general:urgencia_falsa``, ``html``,
    ``metadatos``...). ``evidencia``: cita corta (<= 300 caracteres) que respalda el hallazgo, nunca
    el texto completo. ``locale``: ``None`` si el hallazgo no depende de idioma (p. ej. HTML).
    """

    patron_clave: str
    nivel: str
    categoria: str
    descripcion: str
    evidencia: str
    locale: str | None = None

    def __post_init__(self) -> None:
        if self.nivel not in ORDEN_NIVEL:
            raise ValueError(f"nivel de hallazgo desconocido: {self.nivel!r}")

    def asdict(self) -> dict[str, str | None]:
        """Representación JSON-serializable (claves ASCII, para ``--json`` y para los dictámenes)."""
        return {
            "patron_clave": self.patron_clave,
            "nivel": self.nivel,
            "categoria": self.categoria,
            "descripcion": self.descripcion,
            "evidencia": self.evidencia[:300],
            "locale": self.locale,
        }


def peor_nivel(hallazgos: Iterable[Hallazgo]) -> str:
    """El nivel más alto entre ``hallazgos`` (``"verde"`` si está vacío)."""
    peor = "verde"
    for h in hallazgos:
        if ORDEN_NIVEL[h.nivel] > ORDEN_NIVEL[peor]:
            peor = h.nivel
    return peor
