"""``infra.latido``: diagnóstico del latido *dead-man switch* hacia el Worker ``watchdog`` (docs/07 §9.2).

El LATIDO real lo envía el motor cada ``watchdog.latido_cada_min`` (B1, aún no existe: ``engine.estado``
no tiene el ciclo que lo dispara). Esta entrega aporta: (1) la construcción y firma del payload
(``firma_hmac`` con ``LATIDO_HMAC``, la misma clave que ``infra.kill`` usa para avisar al watchdog);
(2) ``enviar``, para que B1 lo reutilice sin reimplementar la firma; (3) ``evaluar_vencimiento``, la
MISMA regla que debe aplicar el Worker (docs/07 §9.2.2) en una función pura y probada en Python, para
que ``infra.simulacro`` (A-5, A-10) pueda verificarla sin depender de ``node --test``; (4) ``verificar``,
un lector de solo lectura de ``GET <watchdog>/estado`` para diagnóstico manual y para
``infra.preflight.sonda_c09_watchdog``.

CLI (todo de solo lectura o con un ``Transporte`` inyectado explícitamente; sin red en estas pruebas)::

    python -m infra.latido evaluar --ultimo-latido 2026-11-09T07:50:00Z --ahora 2026-11-09T08:25:00Z --max-min 30
    python -m infra.latido verificar --url https://watchdog.ejemplo   # exige --fixture para no abrir red real

Salida: 0 latido vigente / verificación ok · 4 latido vencido (pausaría con campañas ACTIVE) · 2 uso.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun
from engine.errores import ErrorExterno, ErrorUso
from engine.transporte import Transporte, TransporteFixture
from infra.firma_servicio import cabeceras_internas

__all__ = [
    "LATIDO_TOLERANCIA_SEG", "ResultadoVencimiento", "construir_latido", "enviar", "evaluar_vencimiento", "main", "verificar",
]

LATIDO_TOLERANCIA_SEG = 120  # tolerancia de reloj del Worker (docs/07 §9.2.1); no es un umbral de decisión, es formato/protocolo


def construir_latido(*, estado_generado_en: str, semaforo: str, pausa: bool, version: str,
                     ahora: datetime) -> dict[str, Any]:
    """``{ts, estado_generado_en, semaforo, pausa, version}`` (docs/07 §9.2.1)."""
    if semaforo not in ("VERDE", "AMARILLO", "ROJO"):
        raise ErrorUso("semaforo debe ser VERDE, AMARILLO o ROJO")
    comun.parsear_z(estado_generado_en)  # valida formato; lanza ErrorValidacion si está mal
    return {"ts": comun.iso_z(ahora), "estado_generado_en": estado_generado_en, "semaforo": semaforo,
            "pausa": bool(pausa), "version": str(version)}


def enviar(transporte: Transporte, url_watchdog: str, payload: Mapping[str, Any], clave: bytes, *,
          timeout_s: int = 10):
    """``POST <url_watchdog>/latido`` firmado (``X-Fabrica-Ts``/``X-Fabrica-Firma``, docs/06 §4.7).

    Propaga ``ErrorExterno`` si el transporte falla.
    """
    cuerpo_bytes = comun.json_canonico(dict(payload))
    cabeceras = {**cabeceras_internas(clave, cuerpo_bytes, payload["ts"]), "Content-Type": "application/json"}
    return transporte.solicitar("POST", url_watchdog.rstrip("/") + "/latido", cabeceras=cabeceras, cuerpo=cuerpo_bytes,
                                timeout_s=timeout_s)


@dataclass(frozen=True)
class ResultadoVencimiento:
    debe_pausar: bool
    motivo: str


def evaluar_vencimiento(*, ultimo_latido: str | None, ahora: datetime, latido_max_min: int, semaforo: str | None = None,
                        pausa: bool = False, estado_generado_en: str | None = None, ciclo_max_min: int | None = None,
                        ultimo_ciclo_d8: str | None = None) -> ResultadoVencimiento:
    """Regla de pausa del watchdog (docs/07 §9.2.2), en Python puro para que ``infra.simulacro`` la ejercite.

    Esta es la especificación de referencia; la que de verdad corre en producción es
    ``infra/workers/watchdog/src/logica.mjs`` (JS, Worker real) y debe dar el MISMO resultado —
    ``tests/node`` lo comprueba con los mismos vectores (ver ``infra/workers/watchdog/test/``).
    """
    if ultimo_latido is None:
        return ResultadoVencimiento(True, "sin latido registrado todavía")
    t_ultimo = comun.parsear_z(ultimo_latido)
    if ahora - t_ultimo > timedelta(minutes=latido_max_min):
        return ResultadoVencimiento(True, f"sin latido hace {ahora - t_ultimo}: supera latido_max_min={latido_max_min}")
    if pausa:
        return ResultadoVencimiento(True, "el latido declara pausa=true")
    if semaforo == "ROJO":
        return ResultadoVencimiento(True, "el latido declara semaforo=ROJO")
    if estado_generado_en is not None:
        t_estado = comun.parsear_z(estado_generado_en)
        if ahora - t_estado > timedelta(hours=6):
            return ResultadoVencimiento(True, "estado_generado_en de más de 6 h")
    if ciclo_max_min is not None and ultimo_ciclo_d8 is not None:
        t_ciclo = comun.parsear_z(ultimo_ciclo_d8)
        if ahora - t_ciclo > timedelta(minutes=ciclo_max_min):
            return ResultadoVencimiento(True, f"ultimo_ciclo_d8_ts vencido (> {ciclo_max_min} min): D8 colgado con el latido vivo")
    return ResultadoVencimiento(False, "latido vigente")


def verificar(transporte: Transporte, url_watchdog: str, *, timeout_s: int = 10) -> dict[str, Any]:
    """``GET <url_watchdog>/estado``: devuelve el cuerpo interpretado o ``ErrorExterno``."""
    resp = transporte.solicitar("GET", url_watchdog.rstrip("/") + "/estado", cabeceras={}, cuerpo=None, timeout_s=timeout_s)
    if not resp.ok:
        raise ErrorExterno(f"watchdog respondió {resp.estado}")
    return resp.json()


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m infra.latido", description="Diagnóstico del latido del watchdog (sin red real).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("evaluar", help="¿el watchdog debería pausar con este latido?")
    pe.add_argument("--ultimo-latido")
    pe.add_argument("--ahora", required=True)
    pe.add_argument("--max-min", type=int, required=True)
    pe.add_argument("--semaforo", default=None)
    pe.add_argument("--pausa", action="store_true")
    pe.add_argument("--json", action="store_true")
    pv = sub.add_parser("verificar", help="GET /estado contra un fixture (nunca red real desde esta CLI)")
    pv.add_argument("--url", required=True)
    pv.add_argument("--fixture", required=True, help="ruta a un JSON/YAML de reglas de TransporteFixture")
    pv.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        if args.cmd == "evaluar":
            r = evaluar_vencimiento(ultimo_latido=args.ultimo_latido, ahora=comun.parsear_z(args.ahora), latido_max_min=args.max_min,
                                    semaforo=args.semaforo, pausa=args.pausa)
            datos = {"debe_pausar": r.debe_pausar, "motivo": r.motivo}
            codigo = 4 if r.debe_pausar else 0
        else:
            t = TransporteFixture.desde_archivo(Path(args.fixture))
            datos = verificar(t, args.url)
            codigo = 0
        if args.json:
            print(json.dumps({"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": datos, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(json.dumps(datos, ensure_ascii=False, sort_keys=True))
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
