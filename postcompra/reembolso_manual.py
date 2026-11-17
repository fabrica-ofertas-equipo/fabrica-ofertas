"""``postcompra.reembolso_manual``: reembolso FUERA de la regla automática, decidido por el dueño.

Acción H (``ejecutor=humano``): el dueño ya revisó el caso (fuera de plazo, importe mayor, disputa
abierta u otro motivo que ``postcompra.reembolsar`` rechazó) y decide reembolsar de todos modos. A
diferencia del automático:

* NO comprueba ``reembolso_auto_max`` ni ``reembolsos_auto_max_por_dia`` (son topes de lo AUTOMÁTICO).
* SÍ respeta ``empresa/PAUSA`` (docs/06 §4.6: "entrega A en todos los niveles; reembolso automático no";
  el manual tampoco corre con ``PAUSA``, por eso usa ``engine.guard.hay_pausa`` directamente).
* Comparte el almacén de :mod:`postcompra.almacen` con ``reembolsar`` SOLO para que las dos vías no
  reembolsen la misma ``session_id`` dos veces (sin tope diario: :meth:`AlmacenReembolsos.reservar_sin_tope`).
* Nunca excede lo que de verdad queda pendiente en Stripe (``charge.amount - amount_refunded``): eso no
  es una regla de negocio, es aritmética (no se puede reembolsar lo que no se cobró).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from engine import comun, guard, limites, registro
from engine.errores import ErrorBloqueado, ErrorLimite, ErrorUso, ErrorValidacion
from engine.transporte import TransporteFixture
from postcompra import _comun
from postcompra.almacen import AlmacenReembolsos
from postcompra.cliente_stripe import ClienteStripe
from postcompra.correo import Correo, ProveedorCorreo, texto_confirmacion_reembolso

__all__ = ["ResultadoReembolsoManual", "main", "reembolso_manual"]

_REGLA_MANUAL = "MANUAL-HUMANO"
_SCHEMA_VERSION_REEMBOLSO = "1.0.0"
_ETAPA = "D10"
_AGENTE = "humano:soporte"
_HERRAMIENTA = "postcompra.reembolso_manual"


@dataclass(frozen=True)
class ResultadoReembolsoManual:
    """Resultado de :func:`reembolso_manual`."""

    estado: str  # "simulado" | "ejecutado" | "ya_reembolsado"
    refund_id: str | None
    monto_minor: int
    moneda: str


def _ruta_almacen(raiz: Path, oferta_id: str) -> Path:
    return _comun.dir_postcompra(raiz, oferta_id) / "reembolsos.db"


def reembolso_manual(*, session_id: str, motivo: str, monto_minor: int, oferta_id: str, aprobado_por: str,
                     raiz: Path, env: dict[str, str], ahora: Callable[[], datetime], modo: str,
                     stripe: ClienteStripe, correo: ProveedorCorreo | None = None,
                     destinatario: str | None = None) -> ResultadoReembolsoManual:
    """Ejecuta (o simula) un reembolso manual aprobado por el dueño. ``modo``: dry_run|fixture|live."""
    if modo not in ("dry_run", "fixture", "live"):
        raise ErrorUso(f"modo inválido: {modo!r}")
    oferta_id = _comun.exigir_oferta_id(oferta_id)
    session_id = _comun.exigir_session_id(session_id)
    if motivo not in _comun.MOTIVOS_REEMBOLSO:
        raise ErrorValidacion(f"motivo inválido: {motivo!r}")
    if not isinstance(aprobado_por, str) or not aprobado_por.strip():
        raise ErrorValidacion("reembolso_manual exige aprobado_por (quién lo decidió)")
    monto_minor = comun.exigir_importe(monto_minor, "monto_minor", minimo=1)

    t = comun.instante(ahora)
    dia_utc = t.date().isoformat()
    entorno_actual = comun.entorno(env)
    lim = limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env, entorno=entorno_actual)

    cargo = stripe.obtener_cargo_de_sesion(session_id)
    comun.exigir_misma_moneda(cargo.moneda, lim.moneda, "reembolso manual")
    pendiente = cargo.monto_pagado - cargo.monto_reembolsado_previo
    if monto_minor > pendiente:
        raise ErrorValidacion(f"monto_minor ({monto_minor}) supera lo pendiente en Stripe ({pendiente})")

    if modo == "dry_run":
        return ResultadoReembolsoManual(estado="simulado", refund_id=None, monto_minor=monto_minor, moneda=cargo.moneda)

    if modo == "live":
        if comun.entorno(env) != "produccion":
            raise ErrorBloqueado("--live solo con FABRICA_ENTORNO=produccion")
        if guard.hay_pausa(raiz):
            raise ErrorBloqueado("existe empresa/PAUSA: el reembolso manual tampoco corre mientras esté activa")
    else:  # fixture (B0)
        if comun.entorno(env) not in ("prueba", "desarrollo"):
            raise ErrorBloqueado("modo fixture exige FABRICA_ENTORNO prueba o desarrollo")
        if guard.hay_pausa(raiz):
            raise ErrorBloqueado("existe empresa/PAUSA: el reembolso manual tampoco corre mientras esté activa")

    with AlmacenReembolsos(_ruta_almacen(raiz, oferta_id)) as almacen:
        reserva = almacen.reservar_sin_tope(session_id, oferta_id, dia_utc, comun.iso_z(t))
        if not reserva.ganador:
            fila = reserva.fila or {}
            return ResultadoReembolsoManual(estado="ya_reembolsado", refund_id=fila.get("refund_id"),
                                            monto_minor=fila.get("monto_minor") or monto_minor, moneda=fila.get("moneda") or cargo.moneda)

        clave_idem = comun.clave_idempotencia("reembolso", session_id, {"monto_minor": monto_minor})
        existentes = stripe.listar_reembolsos(cargo.payment_intent)
        coincide = next((r for r in existentes if r.metadata.get("idempotency_key") == clave_idem), None)
        refund = coincide if coincide is not None else stripe.crear_reembolso(
            cargo.payment_intent, monto_minor, cargo.moneda, idempotency_key=clave_idem,
            metadata={"idempotency_key": clave_idem, "aprobado_por": aprobado_por},
        )
        almacen.marcar_ejecutado(session_id, refund_id=refund.id, monto_minor=monto_minor, moneda=cargo.moneda,
                                 idempotency_key=clave_idem, actualizado_en=comun.iso_z(t))

        linea = {
            "schema_version": _SCHEMA_VERSION_REEMBOLSO, "reembolso_id": _comun.id_corto("RF", session_id),
            "ts": comun.iso_z(t), "oferta_id": oferta_id, "checkout_session_id": session_id, "adid": cargo.adid,
            "stripe_refund_id": refund.id, "monto": {"monto": monto_minor, "moneda": cargo.moneda}, "motivo": motivo,
            "regla_aplicada": _REGLA_MANUAL, "dentro_garantia": False,
            "dias_desde_compra": (t.date() - cargo.pagado_en.date()).days, "estado": "ejecutado", "ejecutor": "humano",
            "gate": "H", "idempotency_key": clave_idem,
        }
        errores = comun.errores_de_esquema("reembolso", linea)
        if errores:
            raise ErrorValidacion(f"línea de reembolso manual inválida: {comun.resumir_errores_esquema(errores)}")
        comun.anexar_jsonl(_comun.ruta_reembolsos(raiz, oferta_id), linea)

        registro.registrar({
            "ejecucion_id": "reembolso-manual-" + _comun.hash_corto(session_id, t.isoformat()),
            "oferta_id": oferta_id, "etapa": _ETAPA, "agente": _AGENTE, "evento": "accion",
            "herramienta": _HERRAMIENTA, "entrada_resumen": f"reembolso manual session={session_id} por {aprobado_por}",
            "resultado": {"estado": "ok", "codigo": 0}, "costo_estimado": {"monto": 0, "moneda": "USD"},
            "modo": "live" if modo == "live" else "dry_run",
        }, ruta=registro.ruta_registro(raiz), ahora=lambda: t)

        if correo is not None:
            asunto, cuerpo = texto_confirmacion_reembolso(
                monto_texto=str(monto_minor), moneda=cargo.moneda, producto=oferta_id, con_renuncia=False,
            )
            correo.enviar(Correo(oferta_id=oferta_id, referencia=session_id, plantilla="confirmacion_reembolso_manual",
                                 asunto=asunto, cuerpo_texto=cuerpo), destinatario=destinatario or f"{session_id}@ejemplo.invalido")

        return ResultadoReembolsoManual(estado="ejecutado", refund_id=refund.id, monto_minor=monto_minor, moneda=cargo.moneda)


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python -m postcompra.reembolso_manual --session cs_... --motivo M --monto N --oferta OF-... --aprobado-por nombre [--live|--fixture]``."""
    ap = argparse.ArgumentParser(prog="python -m postcompra.reembolso_manual", description="Reembolso manual aprobado por el dueño (H).")
    ap.add_argument("--session", required=True)
    ap.add_argument("--motivo", required=True, choices=_comun.MOTIVOS_REEMBOLSO)
    ap.add_argument("--monto", required=True, type=int, help="unidad menor de la moneda del cargo")
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--aprobado-por", required=True, dest="aprobado_por")
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--live", action="store_true")
    grupo.add_argument("--fixture", action="store_true")
    ap.add_argument("--raiz")
    ap.add_argument("--ahora")
    ap.add_argument("--fixture-reglas", help="JSON/YAML de reglas de TransporteFixture (tests/fixtures/postcompra/…)")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        modo = "live" if args.live else ("fixture" if args.fixture else "dry_run")
        if modo == "live":
            # Aún no existe un Transporte HTTP real en el repositorio (engine.transporte, Decisión 11:
            # "el cliente HTTP real lo aporta quien lo necesite"). Pedido a B5/B8 pendiente; hasta
            # entonces --live no puede llamar de verdad a Stripe desde esta CLI (falla cerrado).
            raise ErrorUso("--live: no hay un Transporte HTTP real disponible todavía (pedido a B5/B8); use --fixture para B0")
        transporte = TransporteFixture.desde_archivo(args.fixture_reglas) if args.fixture_reglas else TransporteFixture()
        clave_api = env.get("STRIPE_RK_REEMBOLSO") or "ficticia-fixture"
        stripe = ClienteStripe(transporte, clave_api=clave_api)
        resultado = reembolso_manual(session_id=args.session, motivo=args.motivo, monto_minor=args.monto,
                                     oferta_id=args.oferta, aprobado_por=args.aprobado_por, raiz=raiz, env=env,
                                     ahora=reloj, modo=modo, stripe=stripe)
        datos = {"estado": resultado.estado, "refund_id": resultado.refund_id, "monto_minor": resultado.monto_minor,
                "moneda": resultado.moneda}
        if args.json:
            print(json.dumps({"ok": True, "modo": modo, "codigo": 0, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(f"REEMBOLSO MANUAL {resultado.estado.upper()}: {json.dumps(datos, ensure_ascii=False, sort_keys=True)}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
