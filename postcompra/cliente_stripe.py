"""Cliente mínimo de Stripe para ``postcompra``: solo lo que ``reembolsar``/``evidencia`` necesitan.

Usa el :class:`engine.transporte.Transporte` inyectado (nunca ``fetch``/``requests`` directo); en
pruebas y en modo ``fixture`` es un :class:`engine.transporte.TransporteFixture` con reglas grabadas
en ``tests/fixtures/postcompra/``. Las formas de los objetos siguen de cerca las de la API real de
Stripe (``Charge``, ``Refund``, ``PaymentIntent``) para que una captura real (B0-24, fixtures «de forma
real») encaje sin reescribir este módulo, pero solo se leen los campos que la regla de negocio usa.

Ningún dato personal se extrae aquí: ``email`` no se lee (si se necesitara, el llamador debe pasarlo
por ``email_hmac`` con HMAC propio, nunca el texto plano; de momento ningún caller lo pide).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from engine import comun
from engine.errores import ErrorExterno, ErrorValidacion
from engine.transporte import Transporte

__all__ = ["CargoStripe", "ClienteStripe", "ReembolsoStripe"]

_BASE_URL_POR_DEFECTO = "https://api.stripe.com/v1"
_TIMEOUT_S = 20


@dataclass(frozen=True)
class CargoStripe:
    """Lo que ``reembolsar``/``evidencia`` necesitan saber de un pago (Checkout Session + Charge)."""

    session_id: str
    payment_intent: str
    monto_pagado: int
    monto_reembolsado_previo: int
    moneda: str
    pagado_en: datetime
    disputa_abierta: bool
    adid: str | None = None


@dataclass(frozen=True)
class ReembolsoStripe:
    """Un objeto ``Refund`` de Stripe (lo que importa para la idempotencia y el registro)."""

    id: str
    monto: int
    moneda: str
    metadata: Mapping[str, str] = field(default_factory=dict)


class ClienteStripe:
    """Envoltura de solo lo necesario sobre :class:`Transporte`. No abre red por su cuenta."""

    def __init__(self, transporte: Transporte, *, clave_api: str, base_url: str = _BASE_URL_POR_DEFECTO,
                timeout_s: int = _TIMEOUT_S) -> None:
        if not clave_api or not clave_api.strip():
            raise ErrorValidacion("ClienteStripe exige una clave de API (restringida, solo reembolsos)")
        self._transporte = transporte
        self._clave_api = clave_api
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def _cabeceras(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._clave_api}"}

    def _get(self, ruta: str) -> Any:
        resp = self._transporte.solicitar("GET", f"{self._base_url}{ruta}", cabeceras=self._cabeceras(), cuerpo=None,
                                          timeout_s=self._timeout_s)
        if not resp.ok:
            raise ErrorExterno(f"Stripe GET {ruta}: estado {resp.estado}")
        return resp.json()

    def obtener_cargo_de_sesion(self, session_id: str) -> CargoStripe:
        """Resuelve la Checkout Session a su cargo: moneda, importes, fecha de pago y disputa."""
        sesion = self._get(f"/checkout/sessions/{session_id}")
        payment_intent = sesion.get("payment_intent")
        if not isinstance(payment_intent, str) or not payment_intent:
            raise ErrorValidacion(f"sesión {session_id} sin payment_intent (¿no está pagada?)")
        intento = self._get(f"/payment_intents/{payment_intent}")
        cargo = intento.get("latest_charge")
        if not isinstance(cargo, Mapping):
            raise ErrorValidacion(f"payment_intent {payment_intent} sin cargo (latest_charge)")
        creado = cargo.get("created")
        if not isinstance(creado, int) or isinstance(creado, bool):
            raise ErrorValidacion("charge.created ilegible (se esperaba un epoch entero)")
        metadata = sesion.get("metadata") if isinstance(sesion.get("metadata"), Mapping) else {}
        return CargoStripe(
            session_id=session_id,
            payment_intent=payment_intent,
            monto_pagado=comun.exigir_importe(cargo.get("amount"), "charge.amount"),
            monto_reembolsado_previo=comun.exigir_importe(cargo.get("amount_refunded"), "charge.amount_refunded"),
            moneda=comun.exigir_moneda(str(cargo.get("currency", "")).upper()),
            pagado_en=datetime.fromtimestamp(creado, tz=timezone.utc),
            disputa_abierta=cargo.get("dispute") is not None,
            adid=metadata.get("adid") if isinstance(metadata.get("adid"), str) else None,
        )

    def listar_reembolsos(self, payment_intent: str) -> list[ReembolsoStripe]:
        """Reembolsos ya existentes del ``payment_intent`` (paso previo obligatorio antes de crear uno)."""
        datos = self._get(f"/refunds?payment_intent={payment_intent}")
        crudos = datos.get("data") if isinstance(datos, Mapping) else None
        if not isinstance(crudos, list):
            raise ErrorValidacion("respuesta de /refunds ilegible (se esperaba {data: [...]})")
        return [
            ReembolsoStripe(id=str(r["id"]), monto=comun.exigir_importe(r.get("amount"), "refund.amount"),
                            moneda=comun.exigir_moneda(str(r.get("currency", "")).upper()),
                            metadata=dict(r.get("metadata") or {}))
            for r in crudos
        ]

    def crear_reembolso(self, payment_intent: str, monto_minor: int, moneda: str, *, idempotency_key: str,
                        metadata: Mapping[str, str]) -> ReembolsoStripe:
        """Crea el reembolso en Stripe con ``Idempotency-Key`` (paso c del algoritmo de docs/06 §4.8)."""
        cuerpo = {
            "payment_intent": payment_intent,
            "amount": comun.exigir_importe(monto_minor, "monto_minor"),
            "metadata": dict(metadata),
        }
        cabeceras = {**self._cabeceras(), "Idempotency-Key": idempotency_key, "content-type": "application/json"}
        resp = self._transporte.solicitar("POST", f"{self._base_url}/refunds", cabeceras=cabeceras,
                                          cuerpo=comun.json_canonico(cuerpo), timeout_s=self._timeout_s)
        if not resp.ok:
            raise ErrorExterno(f"Stripe POST /refunds: estado {resp.estado}")
        datos = resp.json()
        return ReembolsoStripe(id=str(datos["id"]), monto=comun.exigir_importe(datos.get("amount"), "refund.amount"),
                               moneda=comun.exigir_moneda(str(datos.get("currency", moneda)).upper()),
                               metadata=dict(datos.get("metadata") or metadata))
