"""``postcompra.evidencia``: paquete de evidencia para una disputa de Stripe, sin datos personales.

``python -m postcompra.evidencia --session cs_... --oferta OF-... --salida DIR``

Arma, en ``DIR``, lo que el dueño necesita para contestar una disputa desde ``soporte@`` (docs/06 §4.6,
«``postcompra.evidencia --session cs_… --salida DIR`` arma el paquete de disputa sin datos personales»):
el cargo (importe, moneda, fecha de pago), el historial de entrega (de ``entregas.jsonl`` si existe) y
el historial de reembolsos previos de la sesión (de ``reembolsos.jsonl``), más un manifiesto con el
hash de cada archivo del paquete. Nunca lee ni escribe el email, el nombre o la tarjeta del cliente:
solo IDs (``checkout_session_id``, ``adid``, hashes).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from engine import comun
from engine.errores import ErrorUso
from engine.transporte import TransporteFixture
from postcompra import _comun
from postcompra.cliente_stripe import ClienteStripe

__all__ = ["ResultadoEvidencia", "armar_paquete", "main"]

_NOMBRE_RESUMEN = "resumen.json"
_NOMBRE_MANIFIESTO = "manifiesto.json"


@dataclass(frozen=True)
class ResultadoEvidencia:
    """Dónde quedó el paquete y qué archivos tiene."""

    carpeta: Path
    archivos: tuple[str, ...]


def _entregas_de_la_sesion(raiz: Path, oferta_id: str, session_id: str) -> list[dict[str, Any]]:
    ruta = _comun.ruta_entregas(raiz, oferta_id)
    if not ruta.exists():
        return []
    return [linea for linea in comun.leer_jsonl(ruta) if linea.get("checkout_session_id") == session_id]


def _reembolsos_de_la_sesion(raiz: Path, oferta_id: str, session_id: str) -> list[dict[str, Any]]:
    ruta = _comun.ruta_reembolsos(raiz, oferta_id)
    if not ruta.exists():
        return []
    return [linea for linea in comun.leer_jsonl(ruta) if linea.get("checkout_session_id") == session_id]


def armar_paquete(*, session_id: str, oferta_id: str, raiz: Path, salida: Path, stripe: ClienteStripe) -> ResultadoEvidencia:
    """Construye el paquete de evidencia en ``salida`` (la crea si no existe) y lo devuelve."""
    oferta_id = _comun.exigir_oferta_id(oferta_id)
    session_id = _comun.exigir_session_id(session_id)
    cargo = stripe.obtener_cargo_de_sesion(session_id)
    entregas = _entregas_de_la_sesion(raiz, oferta_id, session_id)
    reembolsos = _reembolsos_de_la_sesion(raiz, oferta_id, session_id)

    resumen = {
        "checkout_session_id": session_id,
        "oferta_id": oferta_id,
        "payment_intent": cargo.payment_intent,
        "monto_pagado_minor": cargo.monto_pagado,
        "monto_reembolsado_previo_minor": cargo.monto_reembolsado_previo,
        "moneda": cargo.moneda,
        "pagado_en": comun.iso_z(cargo.pagado_en),
        "disputa_abierta": cargo.disputa_abierta,
        "adid": cargo.adid,
        "entregas": [
            {"estado": e.get("estado"), "ts": e.get("ts"), "producto_sha256": e.get("producto_sha256"),
             "producto_version": e.get("producto_version"), "intentos": e.get("intentos")}
            for e in entregas
        ],
        "reembolsos_previos": [
            {"estado": r.get("estado"), "ts": r.get("ts"), "monto": r.get("monto"), "motivo": r.get("motivo"),
             "regla_aplicada": r.get("regla_aplicada")}
            for r in reembolsos
        ],
    }
    if not resumen["entregas"]:
        resumen["nota"] = "sin registro local de entrega para esta sesión (ver entregas.jsonl de la oferta)"

    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    ruta_resumen = salida / _NOMBRE_RESUMEN
    comun.escribir_atomico(ruta_resumen, comun.json_canonico(resumen))

    manifiesto = {ruta_resumen.name: comun.hash_archivo(ruta_resumen)}
    for p in sorted(salida.iterdir()):
        if p.is_file() and p.name not in (_NOMBRE_RESUMEN, _NOMBRE_MANIFIESTO):
            manifiesto[p.name] = comun.hash_archivo(p)
    comun.escribir_atomico(salida / _NOMBRE_MANIFIESTO, comun.json_canonico(manifiesto))

    archivos = tuple(sorted(p.name for p in salida.iterdir() if p.is_file()))
    return ResultadoEvidencia(carpeta=salida, archivos=archivos)


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python -m postcompra.evidencia --session cs_... --oferta OF-... --salida DIR``. Solo lectura de Stripe."""
    ap = argparse.ArgumentParser(prog="python -m postcompra.evidencia", description="Paquete de evidencia de disputa (sin datos personales).")
    ap.add_argument("--session", required=True)
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--raiz")
    ap.add_argument("--fixture-reglas", help="JSON/YAML de reglas de TransporteFixture")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        transporte = TransporteFixture.desde_archivo(args.fixture_reglas) if args.fixture_reglas else TransporteFixture()
        clave_api = env.get("STRIPE_RK_REEMBOLSO") or "ficticia-fixture"
        stripe = ClienteStripe(transporte, clave_api=clave_api)
        resultado = armar_paquete(session_id=args.session, oferta_id=args.oferta, raiz=raiz, salida=Path(args.salida), stripe=stripe)
        datos = {"carpeta": str(resultado.carpeta), "archivos": list(resultado.archivos)}
        if args.json:
            print(json.dumps({"ok": True, "modo": "dry_run", "codigo": 0, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(f"PAQUETE DE EVIDENCIA en {resultado.carpeta}: {', '.join(resultado.archivos)}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
