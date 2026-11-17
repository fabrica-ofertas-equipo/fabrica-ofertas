"""Ayudas compartidas por los módulos de ``postcompra``: rutas, IDs e idempotencia.

Nada de dinero ni de red aquí: solo construcción de rutas bajo ``ofertas/<id>/10-postcompra/`` y las
expresiones ancladas que validan ``session_id``/``oferta_id`` antes de tocar nada (fail-closed, igual
que el resto del núcleo). Reutiliza ``engine.comun`` para hashes, tiempo y escritura atómica; no
reimplementa nada de ahí.
"""
from __future__ import annotations

import re
from pathlib import Path

from engine.errores import ErrorValidacion

__all__ = [
    "MOTIVOS_REEMBOLSO", "dir_postcompra", "exigir_oferta_id", "exigir_session_id", "hash_corto", "id_corto",
    "ruta_entregas", "ruta_outbox", "ruta_reembolsos", "ruta_senal_pausa",
]

_RX_OFERTA_ID = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_RX_SESSION_ID = re.compile(r"^cs_[A-Za-z0-9_]+$")

# Motivos canónicos de ``contratos/reembolso.schema.json`` (un solo lugar que los enumera en Python).
MOTIVOS_REEMBOLSO = ("dentro_de_garantia", "producto_no_recibido", "duplicado", "fraude", "otro")


def exigir_oferta_id(valor: str) -> str:
    """Devuelve ``valor`` si cumple el patrón ``OF-AAAAMM-NN``; si no, ``ErrorValidacion``."""
    if not isinstance(valor, str) or not _RX_OFERTA_ID.fullmatch(valor):
        raise ErrorValidacion(f"oferta_id inválido: {valor!r} (se esperaba OF-AAAAMM-NN)")
    return valor


def exigir_session_id(valor: str) -> str:
    """Devuelve ``valor`` si cumple el patrón de Checkout Session de Stripe (``cs_...``)."""
    if not isinstance(valor, str) or not _RX_SESSION_ID.fullmatch(valor):
        raise ErrorValidacion(f"checkout_session_id inválido: {valor!r} (se esperaba cs_...)")
    return valor


def dir_postcompra(raiz: Path, oferta_id: str) -> Path:
    """``<raiz>/ofertas/<oferta_id>/10-postcompra`` (no la crea; quien escribe la crea al hacerlo)."""
    return raiz / "ofertas" / exigir_oferta_id(oferta_id) / "10-postcompra"


def ruta_entregas(raiz: Path, oferta_id: str) -> Path:
    """Ruta de ``entregas.jsonl`` de la oferta (la escribe la API de ingesta; aquí solo se lee, si acaso)."""
    return dir_postcompra(raiz, oferta_id) / "entregas.jsonl"


def ruta_reembolsos(raiz: Path, oferta_id: str) -> Path:
    """Ruta de ``reembolsos.jsonl`` de la oferta (la escribe ``postcompra.reembolsar``/``reembolso_manual``)."""
    return dir_postcompra(raiz, oferta_id) / "reembolsos.jsonl"


def ruta_senal_pausa(raiz: Path, oferta_id: str) -> Path:
    """Ruta de ``senal_pausa.json`` de la oferta (la escribe ``postcompra.metricas``)."""
    return dir_postcompra(raiz, oferta_id) / "senal_pausa.json"


def ruta_outbox(raiz: Path, oferta_id: str) -> Path:
    """Carpeta del outbox local de ``SimuladoCorreo`` para la oferta."""
    return dir_postcompra(raiz, oferta_id) / "outbox"


def hash_corto(*partes: str) -> str:
    """12 hex deterministas de ``partes`` (mismas partes => mismo resultado; usado para IDs e hilos)."""
    from engine import comun  # import tardío: evita un ciclo si algún día engine importa postcompra

    completo = comun.hash_bytes("\x1f".join(partes).encode("utf-8"))  # "sha256:<64 hex>"
    return completo[len("sha256:"):][:12]


def id_corto(prefijo: str, *partes: str) -> str:
    """``<PREFIJO>-<12 hex>``: hash corto determinista de ``partes`` (mismo ``session_id`` => mismo ID)."""
    return f"{prefijo}-{hash_corto(*partes)}"
