"""Snapshot diario de KPI (`datos.kpi`, docs/06 §4.4): `empresa/datos/kpi_oferta_dia.json`.

Cada fila trae `valor`, `n` y `estado`; sin `n` suficiente el estado es `gris` (nunca se inventa un
verde). La frescura de cada fuente se compara contra `parametros.dashboard.frescura_*_amarillo_h` /
`..._rojo_h`; sin ningún dato ingerido para la oferta, la fuente queda `rojo` con `frescura_h = null`
(honesto: no hay nada que mida «fresco», no se finge un semáforo verde). `stripe_balance` no se
implementa esta noche (sin lectura del balance real de Stripe): queda siempre `rojo` (ver README).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from engine import comun
from engine.errores import ErrorLimite, ErrorUso, ErrorValidacion, ParametroFaltante
from engine.parametros import Parametros, cargar_parametros, ruta_por_defecto
from scripts.validar_esquemas import errores_de_esquema

from datos import atribucion
from datos.db import Conexion, conectar, migrar
from datos.etl_stripe import ruta_db_por_defecto

__all__ = ["calcular_kpi", "main", "ruta_kpi"]

SCHEMA_VERSION = "1.0.0"


def ruta_kpi(raiz: Path, oferta_id: str, fecha: str) -> Path:
    """``ofertas/<id>/08-operacion/diario/<fecha>/kpi_oferta_dia.json`` (forma de `ofertas/_ejemplo`)."""
    return raiz / "ofertas" / oferta_id / "08-operacion" / "diario" / fecha / "kpi_oferta_dia.json"


def _fila(kpi_id: str, valor: Any, unidad: str, *, n: int, estado: str, ventana: str, rango: list[str] | None = None) -> dict[str, Any]:
    return {"kpi_id": kpi_id, "valor": valor, "unidad": unidad, "n": n, "estado": estado, "rango": rango, "ventana": ventana}


def _frescura_h(conn: Conexion, tabla: str, oferta_id: str, *, ahora: datetime) -> str | None:
    fila = conn.ejecutar(f"SELECT MAX(ingerido_en) FROM {tabla} WHERE oferta_id = ?", (oferta_id,)).fetchone()
    if not fila or not fila[0]:
        return None
    horas = (ahora - comun.parsear_z(fila[0])).total_seconds() / 3600
    return str(Decimal(str(max(horas, 0))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _estado_frescura(frescura_h: str | None, *, amarillo_h: Any, rojo_h: Any) -> str:
    if frescura_h is None:
        return "rojo"
    valor = Decimal(frescura_h)
    if valor <= Decimal(str(amarillo_h)):
        return "verde"
    if valor <= Decimal(str(rojo_h)):
        return "amarillo"
    return "rojo"


def _fuente_meta(conn: Conexion, oferta_id: str, *, ahora: datetime, parametros: Parametros) -> dict[str, Any]:
    frescura = _frescura_h(conn, "fact_meta_ad_dia", oferta_id, ahora=ahora)
    try:
        estado = _estado_frescura(frescura, amarillo_h=parametros.valor("dashboard.frescura_meta_amarillo_h"),
                                  rojo_h=parametros.valor("dashboard.frescura_meta_rojo_h"))
    except ParametroFaltante:
        estado = "rojo"
    return {"frescura_h": frescura, "estado": estado}


def _fuente_stripe_eventos(conn: Conexion, oferta_id: str, *, ahora: datetime, parametros: Parametros) -> dict[str, Any]:
    frescura = _frescura_h(conn, "fact_pedido", oferta_id, ahora=ahora)
    try:
        estado = _estado_frescura(frescura, amarillo_h=parametros.valor("dashboard.frescura_stripe_eventos_amarillo_h"),
                                  rojo_h=parametros.valor("dashboard.frescura_stripe_eventos_rojo_h"))
    except ParametroFaltante:
        estado = "rojo"
    return {"frescura_h": frescura, "estado": estado}


def calcular_kpi(conn: Conexion, oferta_id: str, fecha: str, *, ahora: Callable[[], datetime] = comun.ahora_utc,
                 parametros: Parametros | None = None, run_id: str, sintetico: bool = True) -> dict[str, Any]:
    """Snapshot de KPI de `oferta_id` para el día `fecha` (``ambito = "oferta"``, ventana ``24h``)."""
    ahora_dt = comun.instante(ahora)
    par = parametros if parametros is not None else cargar_parametros()
    ventana = "24h"
    gasto_minor = conn.ejecutar(
        "SELECT COALESCE(SUM(gasto_minor), 0) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha = ?", (oferta_id, fecha),
    ).fetchone()[0]
    moneda = conn.ejecutar(
        "SELECT moneda FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha = ? LIMIT 1", (oferta_id, fecha),
    ).fetchone()
    moneda_unidad = f"{moneda[0]}_minor" if moneda else "minor"
    impresiones = int(conn.ejecutar(
        "SELECT COALESCE(SUM(impresiones), 0) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha = ?", (oferta_id, fecha),
    ).fetchone()[0])
    clics_enlace = int(conn.ejecutar(
        "SELECT COALESCE(SUM(clics_enlace), 0) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha = ?", (oferta_id, fecha),
    ).fetchone()[0])
    compras_stripe = int(conn.ejecutar(
        "SELECT COUNT(*) FROM fact_pedido WHERE oferta_id = ? AND dia_utc = ? AND es_prueba = 0 AND es_interna = 0",
        (oferta_id, fecha),
    ).fetchone()[0])
    cpa = int((Decimal(gasto_minor) / Decimal(compras_stripe)).to_integral_value(rounding=ROUND_HALF_UP)) if compras_stripe else None
    ctr = str((Decimal(clics_enlace) * 100 / Decimal(impresiones)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)) if impresiones else None
    razon = atribucion.razon_meta_stripe(conn, oferta_id, fecha, fecha)
    try:
        pedidos_min_verde = int(par.valor("dashboard.pedidos_min_verde"))
    except ParametroFaltante:
        pedidos_min_verde = None

    filas = [
        _fila("gasto_meta", int(gasto_minor), moneda_unidad, n=1, estado="ok", ventana=ventana),
        _fila("impresiones", impresiones, "impresiones", n=impresiones, estado="ok", ventana=ventana),
        _fila("clics_enlace", clics_enlace, "clics", n=clics_enlace, estado="ok", ventana=ventana),
        _fila("ctr_enlace", ctr, "porcentaje", n=impresiones, estado="ok" if impresiones else "gris", ventana=ventana),
        _fila("compras_stripe", compras_stripe, "compras", n=compras_stripe,
             estado="ok" if (pedidos_min_verde is not None and compras_stripe >= pedidos_min_verde) else "gris", ventana=ventana),
        _fila("cpa", cpa, moneda_unidad, n=max(compras_stripe, 1), estado="ok" if compras_stripe else "gris", ventana=ventana),
        _fila("razon_meta_stripe", razon, "razon", n=max(compras_stripe, 1), estado="ok" if razon is not None else "gris", ventana=ventana),
    ]
    return {
        "schema_version": SCHEMA_VERSION, "generado_en": comun.iso_z(ahora_dt), "run_id": run_id,
        "version_esquema": "1.0.0", "version_glosario": "1.0.0", "ambito": "oferta", "oferta_id": oferta_id,
        "fecha": fecha,
        "fuentes": {
            "meta": _fuente_meta(conn, oferta_id, ahora=ahora_dt, parametros=par),
            "stripe_eventos": _fuente_stripe_eventos(conn, oferta_id, ahora=ahora_dt, parametros=par),
            "stripe_balance": {"frescura_h": None, "estado": "rojo"},
        },
        "filas": filas,
        "sintetico": sintetico,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datos.kpi", description="Snapshot de KPI de una oferta para un día.")
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--fecha", required=True, help="AAAA-MM-DD")
    ap.add_argument("--db")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--raiz")
    ap.add_argument("--ahora")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz:
            if comun.entorno(env) == "produccion":
                raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
            env["FABRICA_RAIZ"] = str(Path(args.raiz).resolve())
        raiz = comun.raiz(env)
        conn = conectar(args.db or f"sqlite:///{ruta_db_por_defecto(raiz)}")
        migrar(conn)
        ahora = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        ts_compacto = (args.ahora or comun.iso_z(comun.ahora_utc())).replace("-", "").replace(":", "")[:13]
        try:
            parametros = cargar_parametros(ruta_por_defecto(raiz))
        except ErrorLimite:
            parametros = Parametros({"grupos": {}})  # sin parametros.yaml: el KPI sale igual, en gris/rojo
        kpi = calcular_kpi(conn, args.oferta, args.fecha, ahora=ahora, parametros=parametros, run_id=f"RUN-{ts_compacto}")
        errores = errores_de_esquema("kpi", kpi)
        if errores:
            raise ErrorValidacion(f"kpi_oferta_dia.json inválido: {comun.resumir_errores_esquema(errores)}")
        comun.escribir_atomico(ruta_kpi(raiz, args.oferta, args.fecha), comun.json_canonico(kpi))
        if args.json:
            print(json.dumps({"ok": True, "modo": "dry_run", "codigo": 0, "datos": kpi, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(f"kpi: {args.oferta} {args.fecha} escrito en {ruta_kpi(raiz, args.oferta, args.fecha)}")
        conn.cerrar()
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
