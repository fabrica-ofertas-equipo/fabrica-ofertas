"""Autenticación interna servicio-a-servicio (docs/06 §4.7): ``X-Fabrica-Ts`` + ``X-Fabrica-Firma``.

``X-Fabrica-Firma: hmac-sha256=<hex>`` = HMAC-SHA256 de ``ts + "." + cuerpo_exacto`` (los bytes EXACTOS
que se envían, antes de cualquier reserialización), comparación en tiempo constante. La misma convención
la implementa el lado Worker en JavaScript (``infra/workers/watchdog/src/hmac.mjs``); ambos lados deben
dar el mismo resultado para el mismo ``(clave, cuerpo, ts)``.

Prefijo de CONTEXTO (revisión de seguridad del panel m-4, ``dashboard/CONTRATO.md`` §7b): en lo que firma el
dashboard (``GET /estado`` petición ``req`` y respuesta ``resp``, ``POST /ordenes`` y ``POST /ingresar`` ``req``) el
mensaje es ``contexto + "." + ts + "." + cuerpo``, para que la firma de una respuesta nunca autentique una petición.
Los Workers → API (``/ingesta/*``) y el latido/kill hacia el watchdog NO llevan contexto (``contexto=None``).
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Mapping

__all__ = ["CONTEXTOS", "cabeceras_internas", "verificar_cabeceras"]


CONTEXTOS = ("req", "resp")


def _firma_hex(clave: bytes, cuerpo: bytes, ts: str, contexto: str | None = None) -> str:
    if contexto is not None and contexto not in CONTEXTOS:
        raise ValueError(f"contexto de firma desconocido: {contexto!r} (admitidos: {', '.join(CONTEXTOS)} o ninguno)")
    prefijo = b"" if contexto is None else contexto.encode("ascii") + b"."
    mensaje = prefijo + ts.encode("utf-8") + b"." + cuerpo
    return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()


def cabeceras_internas(clave: bytes, cuerpo: bytes, ts: str, contexto: str | None = None) -> dict[str, str]:
    """``{"X-Fabrica-Ts": ts, "X-Fabrica-Firma": "hmac-sha256=<hex>"}`` (con ``contexto`` ``req``/``resp`` solo para lo
    que firma el dashboard; sin contexto, el formato de los Workers de docs/06 §4.7)."""
    return {"X-Fabrica-Ts": ts, "X-Fabrica-Firma": f"hmac-sha256={_firma_hex(clave, cuerpo, ts, contexto)}"}


def verificar_cabeceras(clave: bytes, cuerpo: bytes, ts: str, firma_cabecera: str, contexto: str | None = None) -> bool:
    """¿``firma_cabecera`` (``hmac-sha256=<hex>``) corresponde a ``(clave, cuerpo, ts[, contexto])``? Tiempo constante."""
    esperado = f"hmac-sha256={_firma_hex(clave, cuerpo, ts, contexto)}"
    return hmac.compare_digest(esperado.encode("utf-8"), (firma_cabecera or "").encode("utf-8"))
