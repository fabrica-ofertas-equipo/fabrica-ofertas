"""``meta.subir_presupuesto``: aumenta el presupuesto de un conjunto dentro de los topes y el ritmo.

Operación ``aumentar_presupuesto`` de ``engine.guard`` (agregados + ritmo; sin gate humano propio en
N2, docs/06 gates.json ``accion:aumentar_presupuesto_d8`` es de D8/D9, no de este script suelto). El
importe que decide CUÁNTO subir no es de este módulo (eso es D8/D9, ``decision.*``); este módulo solo
ejecuta, dentro de lo que ``guard`` aprueba, la subida ya decidida.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable, Sequence
from datetime import datetime

from engine import comun, guard, limites as motor_limites
from engine.errores import ErrorUso
from engine.guard import EstadoCuenta
from engine.limites import CampanaActiva
from engine.transporte import Transporte
from meta import _cli_comun, monedas
from meta.cliente import ClienteMeta

__all__ = ["ResultadoSubirPresupuesto", "main", "subir_presupuesto"]


class ResultadoSubirPresupuesto:
    def __init__(self, *, object_id: str, campo: str, monto_unidad_meta: int, clave_idempotencia: str) -> None:
        self.object_id = object_id
        self.campo = campo
        self.monto_unidad_meta = monto_unidad_meta
        self.clave_idempotencia = clave_idempotencia


def subir_presupuesto(*, oferta_id: str, object_id: str, campo: str, nuevo_monto_minor: int, moneda: str,
                      cliente: ClienteMeta, cuenta: EstadoCuenta, ahora: Callable[[], datetime] = comun.ahora_utc,
                      simulacion: bool = False, transporte_guard: Transporte | None = None,
                      env: Any = None, raiz: Any = None) -> ResultadoSubirPresupuesto:
    """Sube el presupuesto de ``object_id`` (un conjunto) a ``nuevo_monto_minor`` (el nuevo peor caso, unidad menor)."""
    ctx = guard.comprobar_live(
        "aumentar_presupuesto", oferta_id=oferta_id, monto_minor=nuevo_monto_minor, moneda=moneda, ahora=ahora,
        simulacion=simulacion, transporte=transporte_guard, env=env, raiz=raiz, cuenta=cuenta,
    )
    monto_meta = monedas.a_unidad_meta(nuevo_monto_minor, moneda)
    cliente.cambiar_presupuesto(object_id, campo, monto_meta)
    return ResultadoSubirPresupuesto(object_id=object_id, campo=campo, monto_unidad_meta=monto_meta, clave_idempotencia=ctx.clave_idempotencia)


# ----------------------------------------------------------------------------------------------
# CLI (envoltorio en scripts/subir_presupuesto.py)
# ----------------------------------------------------------------------------------------------
def _cuenta_desde_archivo(ruta: Path) -> EstadoCuenta:
    datos = comun.cargar_json(ruta)
    nueva = datos.get("nueva")
    return EstadoCuenta(
        activas=tuple(datos.get("activas") or ()), gasto_vitalicio_minor=datos.get("gasto_vitalicio_minor"),
        nueva=CampanaActiva.desde(nueva) if nueva is not None else None,
        ediciones_recientes=tuple(datos.get("ediciones_recientes") or ()), ultimo_aumento=datos.get("ultimo_aumento"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m meta.subir_presupuesto", description="Sube el presupuesto de un conjunto, dentro de topes y ritmo.")
    ap.add_argument("--object-id", required=True, dest="object_id", help="adset_id cuyo presupuesto sube")
    ap.add_argument("--campo", choices=("daily_budget", "lifetime_budget"), default="daily_budget")
    ap.add_argument("--monto", type=int, required=True, dest="monto", help="nuevo peor caso en la unidad menor de --moneda")
    ap.add_argument("--moneda", required=True)
    ap.add_argument("--cuenta", required=True, dest="cuenta_ruta", help="JSON con activas, gasto_vitalicio_minor, nueva, ediciones_recientes, ultimo_aumento")
    _cli_comun.agregar_argumentos_comunes(ap)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else None
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        cuenta = _cuenta_desde_archivo(Path(args.cuenta_ruta))

        if args.modo == "dry-run":
            _cli_comun.imprimir(ok=True, modo="dry_run", codigo=0,
                               datos={"object_id": args.object_id, "campo": args.campo, "monto": args.monto, "moneda": args.moneda},
                               avisos=[], as_json=args.json)
            return 0

        lim = motor_limites.cargar_limites((raiz or comun.raiz(env)) / "empresa" / "limites.yaml", env=env)
        cliente, transporte = _cli_comun.construir_cliente(
            args, env, segundos_min_entre_ediciones=lim.valor("segundos_min_entre_ediciones"),
            max_cambios_presupuesto_por_hora=lim.valor("max_cambios_presupuesto_por_hora_por_conjunto"),
        )
        resultado = subir_presupuesto(
            oferta_id=args.oferta, object_id=args.object_id, campo=args.campo, nuevo_monto_minor=args.monto, moneda=args.moneda,
            cliente=cliente, cuenta=cuenta, ahora=reloj, simulacion=(args.modo == "fixture"), transporte_guard=transporte, env=env, raiz=raiz,
        )
        datos = {"object_id": resultado.object_id, "campo": resultado.campo, "monto_unidad_meta": resultado.monto_unidad_meta,
                 "clave_idempotencia": resultado.clave_idempotencia}
        _cli_comun.imprimir(ok=True, modo=args.modo, codigo=0, datos=datos, avisos=[], as_json=args.json)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
