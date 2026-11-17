"""Implementación REAL (sin dependencias) del :class:`engine.transporte.Transporte` para ``infra``.

Solo ``urllib.request`` (biblioteca estándar): nada nuevo que instalar (convenciones §13). Nadie la usa
en pruebas (bloquean ``socket.socket``) ni en esta construcción nocturna (regla de la noche: sin
peticiones de red); la aporta el componente que la necesita (docs/06 §4.1) para que ``infra.kill`` e
``infra.latido`` tengan un transporte real el día que alguien los corra con ``--live`` fuera de aquí.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from typing import Mapping

from engine.errores import ErrorExterno
from engine.transporte import Respuesta

__all__ = ["TransporteUrllib"]


class TransporteUrllib:
    """Cliente HTTP real mínimo. Nunca registra cabeceras con credenciales en una excepción."""

    def solicitar(self, metodo: str, url: str, *, cabeceras: Mapping[str, str], cuerpo: bytes | None,
                  timeout_s: int) -> Respuesta:
        peticion = urllib.request.Request(url, data=cuerpo, method=metodo.upper(), headers=dict(cabeceras))
        try:
            with urllib.request.urlopen(peticion, timeout=timeout_s) as resp:  # noqa: S310 - URL la decide el llamador
                return Respuesta(resp.status, dict(resp.headers.items()), resp.read())
        except urllib.error.HTTPError as exc:
            return Respuesta(exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise ErrorExterno(f"fallo de red hacia {metodo.upper()} <url oculta>: {type(exc).__name__}") from exc
