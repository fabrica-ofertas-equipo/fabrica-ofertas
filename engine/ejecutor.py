"""``ejecutor``: la única escritura viva sin gate (docs/06 §3 y §4.2): pausar.

``decision.reglas`` (D8) decide ``MATAR``/``INCONCLUSO`` y pide pausar un objeto; nada de esto pide
una firma humana (pausar nunca espera a un humano, docs/06 §5). :class:`Ejecutor` es el protocolo
congelado (``pausar(objeto_id, *, motivo) -> Resultado``); :class:`EjecutorMotor` es la implementación
determinista de este componente:

* ``objeto_id`` = un ``OF-AAAAMM-NN``: pausa la FASE de la oferta (``en_test``/``escalando`` ->
  ``pausada``) vía ``engine.estado.transicionar_fase``. Es síncrono, local y no pide ninguna firma.
* ``objeto_id`` = un ID de Meta (anuncio, conjunto o campaña): este componente NO tiene cliente de
  Meta (es de B5, ``meta.pausar``); se delega en ``pausador_meta`` (inyectable). Sin uno inyectado,
  devuelve ``Resultado(ok=False, ...)`` con el motivo y NO lanza: pausar nunca debe fallar con una
  excepción que detenga el resto de una corrida de D8 sobre otros objetos (ver README, «Pedidos» a B5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from engine import comun, estado
from engine.errores import ErrorUso

__all__ = ["Ejecutor", "EjecutorMotor", "Resultado"]

_RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_FASES_PAUSABLES = ("en_test", "escalando")


@dataclass(frozen=True)
class Resultado:
    """Resultado de una acción del ejecutor. Nunca contiene credenciales."""

    ok: bool
    objeto_id: str
    motivo: str
    detalle: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Ejecutor(Protocol):
    """Protocolo congelado (docs/06 §4.2): la única escritura viva sin gate."""

    def pausar(self, objeto_id: str, *, motivo: str) -> Resultado:
        """Pausa ``objeto_id`` (una oferta o un objeto de Meta) y devuelve el resultado; nunca lanza por un fallo de negocio."""
        ...


class EjecutorMotor:
    """Implementación determinista de :class:`Ejecutor` para este componente (``engine``).

    ``pausador_meta`` es un ``Callable[[str, str], Resultado]`` inyectable para los IDs que no son una
    oferta (lo aporta ``meta.pausar``, B5); sin él, pausar un objeto de Meta queda registrado como no
    resuelto (``ok=False``), con un mensaje que señala el pedido pendiente, en vez de lanzar.
    """

    def __init__(self, *, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
                pausador_meta: "Callable[[str, str], Resultado] | None" = None) -> None:
        self._raiz = raiz
        self._ahora = ahora
        self._pausador_meta = pausador_meta

    def pausar(self, objeto_id: str, *, motivo: str) -> Resultado:
        """Ver :class:`Ejecutor`. Errores: ``ErrorUso`` solo si ``objeto_id``/``motivo`` están vacíos."""
        if not isinstance(objeto_id, str) or not objeto_id:
            raise ErrorUso("pausar exige objeto_id")
        if not isinstance(motivo, str) or not motivo:
            raise ErrorUso("pausar exige motivo")
        if _RX_OFERTA.fullmatch(objeto_id):
            return self._pausar_oferta(objeto_id, motivo)
        if self._pausador_meta is not None:
            return self._pausador_meta(objeto_id, motivo)
        return Resultado(
            ok=False, objeto_id=objeto_id, motivo=f"sin pausador de Meta inyectado: {motivo}",
            detalle={"pedido": "meta.pausar (B5) debe inyectarse como pausador_meta"},
        )

    def _pausar_oferta(self, oferta_id: str, motivo: str) -> Resultado:
        est = estado.cargar(oferta_id, raiz=self._raiz)
        if est["fase"] not in _FASES_PAUSABLES:
            return Resultado(ok=True, objeto_id=oferta_id, motivo="la oferta ya no estaba activa", detalle={"fase": est["fase"]})
        nuevo = estado.transicionar_fase(oferta_id, "pausada", actor="motor", causa=motivo, raiz=self._raiz, ahora=self._ahora)
        return Resultado(ok=True, objeto_id=oferta_id, motivo=motivo, detalle={"fase": nuevo["fase"]})
