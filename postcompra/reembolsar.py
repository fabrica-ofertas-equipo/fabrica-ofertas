"""``postcompra.reembolsar``: reembolso automático dentro de regla (docs/06 §4.8, convenciones §7).

Algoritmo (idéntico al de docs/06-bases-del-testeo.md §4.8):

(a) reserva atómica por ``session_id`` con tope diario (:mod:`postcompra.almacen`, ``BEGIN IMMEDIATE``);
(b) lee el cargo en Stripe y rechaza si hay disputa abierta, si está fuera de garantía o si el importe
    acumulado del pedido superaría ``min(charge.amount, reembolso_auto_max)``;
(c) llama a Stripe con ``Idempotency-Key = sha256("reembolso", session_id, monto_minor)`` (SIN el
    motivo) y, antes de crear, SIEMPRE lista los reembolsos existentes del ``payment_intent`` (Stripe
    puede podar la clave de idempotencia a partir de 24 h: un reintento tardío no debe duplicar);
(d) marca ``ejecutado`` con el ``refund_id`` y anota la línea en ``reembolsos.jsonl``.

Un rechazo (fuera de garantía, disputa abierta, excede el tope) **no** reintenta solo: el dueño debe
usar ``postcompra.reembolso_manual`` (acción H) o ``postcompra.evidencia`` si hay disputa.

``PAUSA`` detiene este reembolso automático (pero no la entrega, R17): lo comprueba
``engine.guard.comprobar_live`` en los modos ``live``/``fixture``; el modo ``dry_run`` nunca toca nada,
así que ni mira ``PAUSA`` (siempre sale en 0, árbol intacto, como exige B0-03).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Sequence

from engine import comun, guard, limites, registro
from engine.errores import ErrorLimite, ErrorUso, ErrorValidacion
from engine.transporte import Transporte, TransporteFixture
from postcompra import _comun
from postcompra.almacen import AlmacenReembolsos
from postcompra.cliente_stripe import ClienteStripe
from postcompra.correo import Correo, ProveedorCorreo, texto_confirmacion_reembolso
from scripts.validar_esquemas import EXPONENTE_ISO4217

__all__ = ["ResultadoReembolso", "main", "reembolsar"]

_MOTIVOS_RECHAZO_AUTOMATICO = ("disputa_abierta", "fuera_de_garantia", "excede_tope", "sin_saldo_pendiente")
_REGLA_AUTO = "AUTO-GARANTIA"
_REGLA_RECHAZO = "AUTO-RECHAZO"
_SCHEMA_VERSION_REEMBOLSO = "1.0.0"
_ETAPA = "D10"
_AGENTE = "script:postcompra-reembolsar"
_HERRAMIENTA = "postcompra.reembolsar"


@dataclass(frozen=True)
class ResultadoReembolso:
    """Resultado de :func:`reembolsar`, para la CLI y para las pruebas."""

    estado: str  # "simulado" (dry_run) | "ejecutado" | "rechazado"
    motivo_rechazo: str | None
    refund_id: str | None
    monto_minor: int | None
    moneda: str | None
    idempotency_key: str | None
    gano_la_reserva: bool
    plan: dict[str, Any]


def _ruta_almacen(raiz: Path, oferta_id: str) -> Path:
    return _comun.dir_postcompra(raiz, oferta_id) / "reembolsos.db"


def _correo_destinatario_de_prueba(session_id: str) -> str:
    """Dirección sintética determinista (solo para que ``SimuladoCorreo`` tenga algo que hashear).

    En producción el destinatario real lo provee quien llama (nunca se inventa aquí); este alias
    documenta que, de momento, ningún llamador externo pasa un email real a este módulo.
    """
    return f"{session_id}@ejemplo.invalido"


def _anexar_reembolso_jsonl(raiz: Path, *, oferta_id: str, session_id: str, adid: str | None, stripe_refund_id: str | None,
                            monto_minor: int | None, moneda: str | None, motivo: str, regla_aplicada: str,
                            dentro_garantia: bool, dias_desde_compra: int, estado: str, ejecutor: str, gate: str,
                            idempotency_key: str, ts: str) -> dict[str, Any]:
    linea = {
        "schema_version": _SCHEMA_VERSION_REEMBOLSO,
        "reembolso_id": _comun.id_corto("RF", session_id),
        "ts": ts,
        "oferta_id": oferta_id,
        "checkout_session_id": session_id,
        "adid": adid,
        "stripe_refund_id": stripe_refund_id,
        "monto": {"monto": monto_minor if monto_minor is not None else 0, "moneda": moneda or "EUR"},
        "motivo": motivo,
        "regla_aplicada": regla_aplicada,
        "dentro_garantia": dentro_garantia,
        "dias_desde_compra": dias_desde_compra,
        "estado": estado,
        "ejecutor": ejecutor,
        "gate": gate,
        "idempotency_key": idempotency_key,
    }
    errores = comun.errores_de_esquema("reembolso", linea)
    if errores:
        raise ErrorValidacion(f"línea de reembolso inválida: {comun.resumir_errores_esquema(errores)}")
    comun.anexar_jsonl(_comun.ruta_reembolsos(raiz, oferta_id), linea)
    return linea


def _registrar(raiz: Path, *, oferta_id: str, session_id: str, estado: str, codigo: int, modo: str, t: datetime) -> None:
    """Anota la acción en ``empresa/registro.jsonl`` (convenciones §6). No lo hace para reintentos idempotentes."""
    evento = {
        "ejecucion_id": "reembolsar-" + _comun.hash_corto(session_id, t.isoformat()),
        "oferta_id": oferta_id,
        "etapa": _ETAPA,
        "agente": _AGENTE,
        "evento": "accion",
        "herramienta": _HERRAMIENTA,
        "entrada_resumen": f"reembolsar session={session_id}",
        "resultado": {"estado": estado, "codigo": codigo},
        "costo_estimado": {"monto": 0, "moneda": "USD"},
        "modo": "live" if modo == "live" else "dry_run",
    }
    registro.registrar(evento, ruta=registro.ruta_registro(raiz), ahora=lambda: t)


def reembolsar(*, session_id: str, motivo: str, oferta_id: str, raiz: Path, env: dict[str, str],
               ahora: Callable[[], datetime], modo: str, stripe: ClienteStripe,
               correo: ProveedorCorreo | None = None, destinatario: str | None = None,
               transporte: Transporte | None = None, dormir: Callable[[float], None] = time.sleep) -> ResultadoReembolso:
    """Ejecuta (o simula) el algoritmo de reembolso automático para ``session_id``.

    ``modo``: ``"dry_run"`` (por defecto; no toca nada), ``"fixture"`` (B0: ``simulacion=True`` del
    guard, exige ``FABRICA_ENTORNO`` ∈ {prueba, desarrollo}) o ``"live"`` (producción real).
    """
    if modo not in ("dry_run", "fixture", "live"):
        raise ErrorUso(f"modo inválido: {modo!r} (dry_run, fixture o live)")
    oferta_id = _comun.exigir_oferta_id(oferta_id)
    session_id = _comun.exigir_session_id(session_id)
    if motivo not in _comun.MOTIVOS_REEMBOLSO:
        raise ErrorValidacion(f"motivo inválido: {motivo!r} (se esperaba uno de {_comun.MOTIVOS_REEMBOLSO})")

    t = comun.instante(ahora)
    dia_utc = t.date().isoformat()
    entorno_actual = comun.entorno(env)

    lim = limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env, entorno=entorno_actual)
    limites.exigir_operacion(lim, "reembolsar_auto")
    tope_dia = lim.valor("reembolsos_auto_max_por_dia")
    tope_pedido = lim.valor("reembolso_auto_max")
    dias_garantia = lim.valor("politica_reembolso_dias")

    cargo = stripe.obtener_cargo_de_sesion(session_id)
    comun.exigir_misma_moneda(cargo.moneda, lim.moneda, "reembolso")

    monto_pendiente = cargo.monto_pagado - cargo.monto_reembolsado_previo
    dias_desde_compra = (t.date() - cargo.pagado_en.date()).days
    dentro_garantia = dias_desde_compra <= dias_garantia

    rechazo: str | None = None
    if cargo.disputa_abierta:
        rechazo = "disputa_abierta"
    elif monto_pendiente <= 0:
        rechazo = "sin_saldo_pendiente"
    elif not dentro_garantia:
        rechazo = "fuera_de_garantia"
    elif cargo.monto_reembolsado_previo + monto_pendiente > min(cargo.monto_pagado, tope_pedido):
        rechazo = "excede_tope"

    plan = {
        "session_id": session_id, "oferta_id": oferta_id, "motivo": motivo, "dia_utc": dia_utc,
        "monto_pendiente_minor": monto_pendiente, "moneda": cargo.moneda, "dias_desde_compra": dias_desde_compra,
        "dentro_garantia": dentro_garantia, "rechazo": rechazo, "tope_dia": tope_dia, "tope_pedido": tope_pedido,
    }

    if modo == "dry_run":
        return ResultadoReembolso(estado="simulado", motivo_rechazo=rechazo, refund_id=None, monto_minor=monto_pendiente,
                                  moneda=cargo.moneda, idempotency_key=None, gano_la_reserva=False, plan=plan)

    # El guard compara monto_minor contra el tope reembolso_auto_max (paso «topes»); declaramos el peor
    # caso que de verdad podríamos gastar, NUNCA más que el tope: si el pedido superara el tope, la
    # regla de negocio de abajo (comparación contra el ACUMULADO del pedido, más precisa) ya lo rechaza
    # antes de llamar a Stripe. Sin este tope, un pago grande con reembolso dentro de regla haría que el
    # guard bloqueara con su propio mensaje genérico en vez de con el "excede_tope" de esta función.
    monto_para_guard = min(max(monto_pendiente, 0), tope_pedido)
    guard.comprobar_live(
        "reembolsar_auto", oferta_id=oferta_id, monto_minor=monto_para_guard, moneda=cargo.moneda, ahora=lambda: t,
        simulacion=(modo == "fixture"), transporte=transporte if modo == "fixture" else None, env=env, raiz=raiz,
    )

    with AlmacenReembolsos(_ruta_almacen(raiz, oferta_id)) as almacen:
        reserva = almacen.intentar_reservar(session_id, oferta_id, dia_utc, tope_dia, comun.iso_z(t))
        if not reserva.ganador:
            fila = reserva.fila
            if fila is not None and fila["estado"] == "reservado":
                fila = almacen.esperar_resultado(session_id, dormir=dormir)
            return _resultado_desde_fila(fila, monto_pendiente, cargo.moneda, plan)

        if rechazo is not None:
            almacen.marcar_rechazado(session_id, motivo_rechazo=rechazo, actualizado_en=comun.iso_z(t))
            _anexar_reembolso_jsonl(
                raiz, oferta_id=oferta_id, session_id=session_id, adid=cargo.adid, stripe_refund_id=None,
                monto_minor=monto_pendiente, moneda=cargo.moneda, motivo=motivo, regla_aplicada=_REGLA_RECHAZO,
                dentro_garantia=dentro_garantia, dias_desde_compra=dias_desde_compra, estado="rechazado",
                ejecutor="script", gate="A", idempotency_key=comun.clave_idempotencia("reembolso", session_id, {"rechazo": rechazo}),
                ts=comun.iso_z(t),
            )
            _registrar(raiz, oferta_id=oferta_id, session_id=session_id, estado="bloqueado", codigo=5, modo=modo, t=t)
            raise ErrorLimite(
                f"reembolso automático rechazado ({rechazo}): use postcompra.reembolso_manual o postcompra.evidencia",
                detalle={"motivo": rechazo},
            )

        clave_idem = comun.clave_idempotencia("reembolso", session_id, {"monto_minor": monto_pendiente})
        existentes = stripe.listar_reembolsos(cargo.payment_intent)
        coincide = next((r for r in existentes if r.metadata.get("idempotency_key") == clave_idem), None)
        refund = coincide if coincide is not None else stripe.crear_reembolso(
            cargo.payment_intent, monto_pendiente, cargo.moneda, idempotency_key=clave_idem,
            metadata={"idempotency_key": clave_idem},
        )
        almacen.marcar_ejecutado(session_id, refund_id=refund.id, monto_minor=monto_pendiente, moneda=cargo.moneda,
                                 idempotency_key=clave_idem, actualizado_en=comun.iso_z(t))
        _anexar_reembolso_jsonl(
            raiz, oferta_id=oferta_id, session_id=session_id, adid=cargo.adid, stripe_refund_id=refund.id,
            monto_minor=monto_pendiente, moneda=cargo.moneda, motivo=motivo, regla_aplicada=_REGLA_AUTO,
            dentro_garantia=dentro_garantia, dias_desde_compra=dias_desde_compra, estado="ejecutado", ejecutor="script",
            gate="A", idempotency_key=clave_idem, ts=comun.iso_z(t),
        )
        _registrar(raiz, oferta_id=oferta_id, session_id=session_id, estado="ok", codigo=0, modo=modo, t=t)
        if correo is not None:
            exponente = EXPONENTE_ISO4217.get(cargo.moneda, 2)
            monto_texto = str(Decimal(monto_pendiente).scaleb(-exponente))
            asunto, cuerpo = texto_confirmacion_reembolso(monto_texto=monto_texto, moneda=cargo.moneda,
                                                           producto=oferta_id, con_renuncia=True)
            correo.enviar(Correo(oferta_id=oferta_id, referencia=session_id, plantilla="confirmacion_reembolso",
                                 asunto=asunto, cuerpo_texto=cuerpo),
                         destinatario=destinatario or _correo_destinatario_de_prueba(session_id))
        return ResultadoReembolso(estado="ejecutado", motivo_rechazo=None, refund_id=refund.id, monto_minor=monto_pendiente,
                                  moneda=cargo.moneda, idempotency_key=clave_idem, gano_la_reserva=True, plan=plan)


def _resultado_desde_fila(fila: dict[str, Any] | None, monto_pendiente: int, moneda: str, plan: dict[str, Any]) -> ResultadoReembolso:
    if fila is None:
        raise ErrorValidacion("reembolsar: no se encontró el resultado de la reserva existente")
    estado = "ejecutado" if fila["estado"] == "ejecutado" else "rechazado"
    return ResultadoReembolso(
        estado=estado, motivo_rechazo=fila.get("motivo_rechazo"), refund_id=fila.get("refund_id"),
        monto_minor=fila.get("monto_minor") if fila.get("monto_minor") is not None else monto_pendiente,
        moneda=fila.get("moneda") or moneda, idempotency_key=fila.get("idempotency_key"), gano_la_reserva=False, plan=plan,
    )


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python -m postcompra.reembolsar --session cs_... --motivo M --oferta OF-... [--live|--fixture]``."""
    ap = argparse.ArgumentParser(prog="python -m postcompra.reembolsar", description="Reembolso automático dentro de regla.")
    ap.add_argument("--session", required=True)
    ap.add_argument("--motivo", required=True, choices=_comun.MOTIVOS_REEMBOLSO)
    ap.add_argument("--oferta", required=True)
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--live", action="store_true", help="ejecuta de verdad (exige FABRICA_ENTORNO=produccion)")
    grupo.add_argument("--fixture", action="store_true", help="simulación de B0: TransporteFixture, entorno prueba/desarrollo")
    ap.add_argument("--raiz", help="raíz alternativa (solo sin --live)")
    ap.add_argument("--ahora", help="instante UTC con Z (solo sin --live)")
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
        resultado = reembolsar(session_id=args.session, motivo=args.motivo, oferta_id=args.oferta, raiz=raiz, env=env,
                               ahora=reloj, modo=modo, stripe=stripe, transporte=transporte)
        datos = {
            "estado": resultado.estado, "motivo_rechazo": resultado.motivo_rechazo, "refund_id": resultado.refund_id,
            "monto_minor": resultado.monto_minor, "moneda": resultado.moneda, "plan": resultado.plan,
        }
        if args.json:
            print(json.dumps({"ok": True, "modo": modo, "codigo": 0, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(f"REEMBOLSO {resultado.estado.upper()}: {json.dumps(datos, ensure_ascii=False, sort_keys=True)}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
