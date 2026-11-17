"""``infra.kill``: capa 1 del *kill switch* de tres capas (docs/07-puesta-en-marcha.md §9.1, D-21).

Escribe/verifica ``empresa/PAUSA`` en los TRES sitios que docs/06 §4.8 exige: el archivo espejo (este
módulo, siempre), la fila ``control(pausa)`` del almacén del motor (capa 1 real; inyectable, porque
``engine.estado``/el almacén vivo todavía no existen — ola 1, B1; ver «Pedidos») y el KV del watchdog
(``pausa:global``, capa 3 de alerta/espejo; vía :class:`engine.transporte.Transporte` hacia
``POST <watchdog>/pausa`` firmado con ``LATIDO_HMAC``, la misma clave que el latido).

**Deliberadamente NO pasa por ``engine.guard.comprobar_live``**: un *kill switch* debe poder actuar
precisamente cuando algo está roto (PAUSA ya puesta, infra en ROJO, límites incompletos); exigirle los
7 pasos de activar/gastar invertiría su propósito. Dry-run por defecto (convenciones §9): sin
``--live`` solo IMPRIME el plan. Con ``--live`` escribe el archivo (si esto falla, es un ``ErrorExterno``
real: sin él no hay capa 1) y hace el MEJOR ESFUERZO en el almacén y el watchdog, informando cada fallo
sin abortar (docs/07 «matriz de fallos»: un canal caído no debe impedir que al menos el archivo quede
puesto). Capa 2 (pausar las campañas en Meta, ``meta.pausar``) no es de esta entrega: se inyecta por
Protocolo (:class:`EjecutorPausaCampanas`); sin ella, se informa como pendiente (ver «Pedidos»).

CLI::

    python -m infra.kill activar --motivo "simulacro A-1" [--live] [--raiz RUTA] [--json]
    python -m infra.kill verificar [--raiz RUTA] [--json]

Salida: 0 las tres capas coherentes (o dry-run) · 4 archivo puesto pero almacén o watchdog no
confirmaron (o ``verificar`` encontró incoherencia) · 6 no se pudo ni escribir el archivo · 2 uso.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence, runtime_checkable

from engine import comun
from engine.errores import ErrorExterno, ErrorFabrica, ErrorUso
from engine.transporte import Transporte
from infra.firma_servicio import cabeceras_internas

__all__ = [
    "AlmacenNulo", "AlmacenPausa", "EjecutorNulo", "EjecutorPausaCampanas", "ResultadoCapa", "ResultadoKill",
    "VAR_CLAVE_WATCHDOG", "activar", "main", "ruta_pausa", "verificar",
]

VAR_CLAVE_WATCHDOG = "LATIDO_HMAC"  # misma clave que infra.latido: una sola clave comparte el Worker watchdog


@runtime_checkable
class AlmacenPausa(Protocol):
    """Capa 1 real: la fila ``control(pausa)`` del almacén del motor (``engine.estado``, aún no existe)."""

    def marcar_pausa(self, motivo: str) -> None: ...  # noqa: D102 - Protocolo
    def pausa_activa(self) -> bool: ...  # noqa: D102 - Protocolo


class AlmacenNulo:
    """Almacén de reemplazo: no hay almacén vivo que marcar (``engine.estado`` no existe todavía).

    No se puede confirmar que "el motor" sabe de la pausa (el único escritor real es el motor, D-21):
    por eso :meth:`pausa_activa` devuelve ``False`` siempre, y la capa 1 queda reportada como pendiente.
    """

    def marcar_pausa(self, motivo: str) -> None:
        return None

    def pausa_activa(self) -> bool:
        return False


@runtime_checkable
class EjecutorPausaCampanas(Protocol):
    """Capa 2: pausar toda campaña ``ACTIVE`` (``meta.pausar``, B5, aún no existe)."""

    def pausar_todas(self, motivo: str) -> Sequence[Mapping[str, Any]]: ...  # noqa: D102 - Protocolo


class EjecutorNulo:
    """Ejecutor de reemplazo: sin ``meta.pausar`` inyectado no se puede pausar ninguna campaña."""

    def pausar_todas(self, motivo: str) -> Sequence[Mapping[str, Any]]:
        return []


@dataclass(frozen=True)
class ResultadoCapa:
    """Resultado de una capa: ``ok`` (se confirmó), ``intentado`` (se llamó) y un mensaje breve."""

    nombre: str
    ok: bool
    intentado: bool
    mensaje: str
    evidencia: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResultadoKill:
    modo: str
    motivo: str
    capas: tuple[ResultadoCapa, ...]

    @property
    def ok(self) -> bool:
        """Solo ``True`` si las TRES capas quedaron confirmadas (docs: «tres sitios verificados»)."""
        return all(c.ok for c in self.capas)

    @property
    def archivo_ok(self) -> bool:
        return next(c.ok for c in self.capas if c.nombre == "archivo")


def ruta_pausa(raiz: Path) -> Path:
    return raiz / "empresa" / "PAUSA"


def _capa_archivo(raiz: Path, motivo: str, t: datetime, *, live: bool) -> ResultadoCapa:
    ruta = ruta_pausa(raiz)
    if not live:
        ya = ruta.is_file()
        return ResultadoCapa("archivo", ya, False, f"dry-run: {'ya existe' if ya else 'se escribiría'} {ruta}")
    try:
        comun.escribir_atomico(ruta, comun.json_canonico({"motivo": motivo[:300], "ts": comun.iso_z(t)}))
    except OSError as exc:
        raise ErrorExterno(f"no se pudo escribir empresa/PAUSA: {exc}") from exc
    return ResultadoCapa("archivo", True, True, f"escrito en {ruta}")


def _capa_almacen(almacen: AlmacenPausa, motivo: str, *, live: bool) -> ResultadoCapa:
    if not live:
        return ResultadoCapa("almacen", False, False, "dry-run: se marcaría control(pausa) en el almacén del motor")
    try:
        almacen.marcar_pausa(motivo)
        confirmado = almacen.pausa_activa()
    except Exception as exc:  # noqa: BLE001 - mejor esfuerzo: un almacén caído no debe tumbar las otras capas
        return ResultadoCapa("almacen", False, True, f"almacén no confirmó: {exc}")
    return ResultadoCapa("almacen", confirmado, True, "confirmado" if confirmado else "sin confirmar")


def _capa_watchdog(transporte: Transporte | None, url_watchdog: str | None, clave: bytes, motivo: str, t: datetime, *,
                   live: bool) -> ResultadoCapa:
    if not live:
        return ResultadoCapa("watchdog", False, False, "dry-run: se marcaría pausa:global en el KV del watchdog")
    if transporte is None or not url_watchdog:
        return ResultadoCapa("watchdog", False, True, "sin transporte o WATCHDOG_URL: no se pudo avisar al watchdog")
    ts = comun.iso_z(t)
    cuerpo_bytes = comun.json_canonico({"motivo": motivo[:300], "ts": ts})
    cabeceras = {**cabeceras_internas(clave, cuerpo_bytes, ts), "Content-Type": "application/json"} if clave else {}
    try:
        resp = transporte.solicitar("POST", url_watchdog.rstrip("/") + "/pausa", cabeceras=cabeceras, cuerpo=cuerpo_bytes, timeout_s=10)
    except ErrorExterno as exc:
        return ResultadoCapa("watchdog", False, True, f"watchdog inalcanzable: {exc.mensaje}")
    return ResultadoCapa("watchdog", resp.ok, True, f"watchdog respondió {resp.estado}", {"estado_http": resp.estado})


def activar(motivo: str, *, raiz: Path, env: Mapping[str, str], live: bool = False, almacen: AlmacenPausa | None = None,
           ejecutor: EjecutorPausaCampanas | None = None, transporte: Transporte | None = None,
           url_watchdog: str | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> ResultadoKill:
    """Pone ``PAUSA`` en las tres capas (mejor esfuerzo en almacén y watchdog) y pide pausar campañas.

    Sin ``--live`` (``live=False``, el defecto) no escribe ni llama a nada: solo informa el plan.
    """
    if not isinstance(motivo, str) or not motivo.strip():
        raise ErrorUso("--motivo es obligatorio y no puede estar vacío")
    t = comun.instante(ahora)
    capa_archivo = _capa_archivo(raiz, motivo, t, live=live)
    capa_almacen = _capa_almacen(almacen or AlmacenNulo(), motivo, live=live)
    clave = (env.get(VAR_CLAVE_WATCHDOG) or "").encode("utf-8")
    capa_watchdog = _capa_watchdog(transporte, url_watchdog, clave, motivo, t, live=live)
    capas = (capa_archivo, capa_almacen, capa_watchdog)
    if live:
        tiene_ejecutor = ejecutor is not None
        try:
            resultado_campanas = list((ejecutor or EjecutorNulo()).pausar_todas(motivo))
            fallo_capa2 = False
        except Exception as exc:  # noqa: BLE001 - mejor esfuerzo: capa 2 no bloquea a las demás
            resultado_campanas, fallo_capa2 = [{"error": str(exc)}], True
        mensaje = f"{len(resultado_campanas)} campaña(s) procesadas" if tiene_ejecutor else "sin meta.pausar inyectado (B5, pendiente)"
        capas = capas + (ResultadoCapa("campanas_meta", tiene_ejecutor and not fallo_capa2, tiene_ejecutor, mensaje,
                                       {"campanas": resultado_campanas}),)
    return ResultadoKill(modo="live" if live else "dry_run", motivo=motivo, capas=capas)


def verificar(*, raiz: Path, almacen: AlmacenPausa | None = None, transporte: Transporte | None = None,
             url_watchdog: str | None = None) -> dict[str, Any]:
    """Solo lectura: ¿las tres capas DICEN lo mismo sobre si hay pausa?"""
    archivo = ruta_pausa(raiz).is_file()
    try:
        almacen_pausa = (almacen or AlmacenNulo()).pausa_activa()
    except Exception:  # noqa: BLE001 - fail-closed en la lectura: un almacén que no responde no se asume "sin pausa"
        almacen_pausa = None
    watchdog_pausa: bool | None = None
    if transporte is not None and url_watchdog:
        try:
            resp = transporte.solicitar("GET", url_watchdog.rstrip("/") + "/estado", cabeceras={}, cuerpo=None, timeout_s=10)
            watchdog_pausa = bool(resp.json().get("pausa")) if resp.ok else None
        except ErrorExterno:
            watchdog_pausa = None
    valores = [v for v in (archivo, almacen_pausa, watchdog_pausa) if v is not None]
    coherente = len(set(valores)) <= 1
    return {"archivo": archivo, "almacen": almacen_pausa, "watchdog": watchdog_pausa, "coherente": coherente}


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m infra.kill", description="Kill switch de tres capas (capa 1: archivo espejo).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("activar")
    pa.add_argument("--motivo", required=True)
    pa.add_argument("--live", action="store_true")
    pa.add_argument("--raiz")
    pa.add_argument("--ahora")
    pa.add_argument("--json", action="store_true")
    pv = sub.add_parser("verificar")
    pv.add_argument("--raiz")
    pv.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or getattr(args, "ahora", None)) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        quiere_json = bool(getattr(args, "json", False))
        if args.cmd == "activar":
            reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
            resultado = activar(args.motivo, raiz=raiz, env=env, live=args.live, ahora=reloj)
            datos = {"modo": resultado.modo, "capas": [{"nombre": c.nombre, "ok": c.ok, "intentado": c.intentado, "mensaje": c.mensaje}
                                                        for c in resultado.capas]}
            if not args.live:
                codigo = 0
            else:
                codigo = 0 if resultado.ok else (6 if not resultado.archivo_ok else 4)
        else:
            datos = verificar(raiz=raiz)
            codigo = 0 if datos["coherente"] else 3
        if quiere_json:
            print(json.dumps({"ok": codigo == 0, "modo": "dry_run" if args.cmd == "verificar" or not getattr(args, "live", False) else "live",
                              "codigo": codigo, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(json.dumps(datos, ensure_ascii=False, sort_keys=True))
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
