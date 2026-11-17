"""Correo transaccional de ``postcompra``: confirmaciones de reembolso (con renuncia al desistimiento).

``ProveedorCorreo`` es el protocolo que usan ``reembolsar``/``reembolso_manual``. Dos implementaciones:

* :class:`SimuladoCorreo` — outbox local bajo ``ofertas/<id>/10-postcompra/outbox/`` (docs/06 §6.1).
  No usa red. El destinatario NUNCA se escribe en texto plano: solo su hash (pseudónimo, sin secreto;
  esto NO es el ``email_hmac`` de ``contratos/entrega.schema.json``, que firma otro componente con su
  propia clave — aquí es un archivo propio de prueba, no un artefacto de ``contratos/``).
* :class:`ResendCorreo` — proveedor real vía :class:`engine.transporte.Transporte` inyectado; nunca
  abre la red por su cuenta. El texto del correo nunca contiene datos personales más allá de lo que
  Resend necesita para entregarlo (la dirección se pasa aparte, no vive en :class:`Correo`).

``texto_confirmacion_reembolso`` incluye la renuncia al derecho de desistimiento (contenido digital
entregado con consentimiento expreso, UE: Directiva 2011/83, art. 16m) cuando el reembolso se concede
pese a eso (p. ej. fuera del plazo legal pero dentro de la política comercial propia).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol, runtime_checkable
from datetime import datetime

from engine import comun
from engine.errores import ErrorExterno, ErrorValidacion
from engine.transporte import Transporte
from postcompra import _comun

__all__ = [
    "Correo", "ProveedorCorreo", "ResendCorreo", "ResultadoEnvio", "SimuladoCorreo",
    "texto_confirmacion_reembolso",
]

_URL_RESEND = "https://api.resend.com/emails"
_TIMEOUT_S = 20


@dataclass(frozen=True)
class Correo:
    """Un correo transaccional listo para enviar. Sin datos personales: ``referencia`` es un ID, no un email."""

    oferta_id: str
    referencia: str  # checkout_session_id u otro ID pseudónimo, NUNCA el email
    plantilla: str
    asunto: str
    cuerpo_texto: str


@dataclass(frozen=True)
class ResultadoEnvio:
    """Resultado de :meth:`ProveedorCorreo.enviar`."""

    enviado: bool
    proveedor: str
    referencia_externa: str | None = None


@runtime_checkable
class ProveedorCorreo(Protocol):
    """Contrato mínimo de un proveedor de correo inyectable."""

    def enviar(self, correo: Correo, *, destinatario: str) -> ResultadoEnvio:
        """Envía ``correo`` a ``destinatario`` (dirección real, nunca persistida en texto plano)."""
        ...


class SimuladoCorreo:
    """Outbox local (docs/06 §6.1): un archivo JSON por envío, sin red ni datos personales en texto plano."""

    def __init__(self, raiz: Path, *, ahora: Callable[[], datetime] = comun.ahora_utc) -> None:
        self._raiz = Path(raiz)
        self._ahora = ahora

    def enviar(self, correo: Correo, *, destinatario: str) -> ResultadoEnvio:
        """Escribe ``correo`` en el outbox de la oferta. ``destinatario`` se guarda solo como hash."""
        if not isinstance(destinatario, str) or "@" not in destinatario:
            raise ErrorValidacion("SimuladoCorreo.enviar exige un destinatario con forma de email")
        t = comun.instante(self._ahora)
        destino_hash = comun.hash_bytes(destinatario.strip().lower().encode("utf-8"))
        nombre = _comun.id_corto("MAIL", correo.oferta_id, correo.referencia, correo.plantilla, comun.iso_z(t)) + ".json"
        datos = {
            "ts": comun.iso_z(t),
            "oferta_id": correo.oferta_id,
            "referencia": correo.referencia,
            "plantilla": correo.plantilla,
            "asunto": correo.asunto,
            "cuerpo_texto": correo.cuerpo_texto,
            "destinatario_hash": destino_hash,
        }
        destino = _comun.ruta_outbox(self._raiz, correo.oferta_id) / nombre
        comun.escribir_atomico(destino, comun.json_canonico(datos))
        return ResultadoEnvio(enviado=True, proveedor="simulado", referencia_externa=nombre)


class ResendCorreo:
    """Proveedor real (Resend) vía ``Transporte`` inyectado. No abre red directamente."""

    def __init__(self, transporte: Transporte, *, clave_api: str, remitente: str, timeout_s: int = _TIMEOUT_S) -> None:
        if not clave_api or not clave_api.strip():
            raise ErrorValidacion("ResendCorreo exige una clave de API")
        if not remitente or "@" not in remitente:
            raise ErrorValidacion("ResendCorreo exige un remitente con forma de email")
        self._transporte = transporte
        self._clave_api = clave_api
        self._remitente = remitente
        self._timeout_s = timeout_s

    def enviar(self, correo: Correo, *, destinatario: str) -> ResultadoEnvio:
        if not isinstance(destinatario, str) or "@" not in destinatario:
            raise ErrorValidacion("ResendCorreo.enviar exige un destinatario con forma de email")
        cuerpo: Mapping[str, object] = {
            "from": self._remitente,
            "to": [destinatario],
            "subject": correo.asunto,
            "text": correo.cuerpo_texto,
        }
        cabeceras = {"Authorization": f"Bearer {self._clave_api}", "content-type": "application/json"}
        resp = self._transporte.solicitar("POST", _URL_RESEND, cabeceras=cabeceras, cuerpo=comun.json_canonico(cuerpo),
                                          timeout_s=self._timeout_s)
        if not resp.ok:
            raise ErrorExterno(f"Resend POST /emails: estado {resp.estado}")
        datos = resp.json()
        return ResultadoEnvio(enviado=True, proveedor="resend", referencia_externa=str(datos.get("id")))


def texto_confirmacion_reembolso(*, monto_texto: str, moneda: str, producto: str, con_renuncia: bool) -> tuple[str, str]:
    """``(asunto, cuerpo)`` de la confirmación de reembolso. ``con_renuncia`` agrega el texto de
    renuncia al derecho de desistimiento (contenido digital ya entregado con consentimiento expreso).
    """
    asunto = "Confirmación de tu reembolso"
    lineas = [
        f"Hemos procesado tu reembolso de {monto_texto} {moneda} por «{producto}».",
        "El importe debería reflejarse en tu método de pago original en los próximos días, según tu banco o entidad emisora.",
    ]
    if con_renuncia:
        lineas.append(
            "Al comprar aceptaste la entrega inmediata del contenido digital y renunciaste expresamente a tu derecho "
            "de desistimiento sobre ese contenido una vez entregado (consentimiento expreso, art. 16.m de la Directiva "
            "2011/83/UE); este reembolso se concede como gesto comercial, no como ejercicio de ese derecho."
        )
    return asunto, "\n\n".join(lineas)
