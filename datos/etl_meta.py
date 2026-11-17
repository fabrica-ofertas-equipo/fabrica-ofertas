"""ETL de Meta: inserta insights por anuncio y día en `fact_meta_ad_dia` (docs/06 §4.4).

A diferencia de Stripe, los insights de Meta reportan el gasto como una cadena decimal en la unidad
ESTÁNDAR de la moneda de la cuenta (p. ej. ``"27.60"`` EUR), no en unidad menor: la conversión usa el
exponente ISO 4217 de la moneda (`scripts.validar_esquemas.EXPONENTE_ISO4217`), NUNCA el offset propio
de Meta (ese offset es solo para `AdAccount.spend_cap`, convenciones §3; aquí no aplica).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from engine import comun
from engine.errores import ErrorExterno, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import EXPONENTE_ISO4217, dec

from datos.db import Conexion, conectar, migrar
from datos.etl_stripe import ruta_db_por_defecto

__all__ = ["aplicar_fila", "aplicar_insights", "cargar_fixture", "main"]

_ACCION_COMPRA = "purchase"


def _monto_minor(spend: str, moneda: str) -> int:
    """Convierte el gasto reportado (unidad estándar, cadena decimal) a unidad menor."""
    if moneda not in EXPONENTE_ISO4217:
        raise ErrorValidacion(f"moneda sin exponente ISO 4217 conocido: {moneda!r} (fail-closed)")
    exponente = EXPONENTE_ISO4217[moneda]
    return int(dec(spend) * (10 ** exponente))


def _compras(acciones: Sequence[Mapping[str, Any]] | None) -> int:
    """Suma las conversiones de compra reportadas en `actions` (0 si no hay ninguna)."""
    total = 0
    for accion in acciones or ():
        tipo = str(accion.get("action_type") or "")
        if _ACCION_COMPRA in tipo:
            total += int(accion.get("value") or 0)
    return total


def aplicar_fila(conn: Conexion, oferta_id: str, fila: Mapping[str, Any], *, tz: str, moneda: str,
                 ahora: Callable[[], datetime] = comun.ahora_utc) -> None:
    """Aplica UNA fila de insight (upsert por ``(ad_id, fecha)``) a `raw_meta_insight` y `fact_meta_ad_dia`.

    También da de alta ``ad_id`` en ``dim_anuncio`` (``ad_id -> oferta_id``, docs/06 §4.8, D-21): sin
    esto ningún anuncio quedaba asociado a su oferta y ``decision.entradas._ids_de_celda`` no podía
    resolver ni la celda ``oferta_mercado``. Idempotente por ``ad_id`` (clave global de Meta) con SQL
    directo (no ``Conexion.upsert``, que pisaría ``concepto_id`` con ``NULL`` en cada corrida): el
    ``oferta_id`` se actualiza si cambiara, pero un ``concepto_id`` ya puesto por otro proceso nunca se
    borra desde aquí (este ETL no lo conoce: lo deja intacto).
    """
    faltan = [c for c in ("ad_id", "adset_id", "campaign_id", "date_start", "spend", "impressions",
                          "clicks", "inline_link_clicks") if c not in fila]
    if faltan:
        raise ErrorValidacion(f"insight de Meta incompleto: faltan {', '.join(faltan)}")
    ahora_iso = comun.iso_z(comun.instante(ahora))
    ad_id, fecha = str(fila["ad_id"]), str(fila["date_start"])
    conn.ejecutar(
        "INSERT INTO dim_anuncio (ad_id, oferta_id, concepto_id) VALUES (?, ?, NULL) "
        "ON CONFLICT (ad_id) DO UPDATE SET oferta_id = excluded.oferta_id",
        (ad_id, oferta_id),
    )
    conn.upsert("raw_meta_insight", ["ad_id", "fecha"], {
        "ad_id": ad_id, "fecha": fecha, "oferta_id": oferta_id,
        "payload_json": comun.json_canonico(dict(fila)).decode("utf-8"), "ingerido_en": ahora_iso,
    })
    conn.upsert("fact_meta_ad_dia", ["ad_id", "fecha"], {
        "ad_id": ad_id,
        "fecha": fecha,
        "oferta_id": oferta_id,
        "campaign_id": str(fila["campaign_id"]),
        "adset_id": str(fila["adset_id"]),
        "tz": tz,
        "gasto_minor": _monto_minor(str(fila["spend"]), moneda),
        "moneda": moneda,
        "impresiones": int(fila["impressions"]),
        "clics": int(fila["clicks"]),
        "clics_enlace": int(fila["inline_link_clicks"]),
        "compras_meta": _compras(fila.get("actions")),
        "ingerido_en": ahora_iso,
    })


def aplicar_insights(conn: Conexion, oferta_id: str, documento: Mapping[str, Any], *, desde: str, hasta: str,
                     ahora: Callable[[], datetime] = comun.ahora_utc) -> int:
    """Aplica las filas de ``documento["filas"]`` cuya fecha cae en ``[desde, hasta]``. Devuelve cuántas."""
    cuenta = documento.get("cuenta") or {}
    tz, moneda = cuenta.get("timezone_name"), cuenta.get("currency")
    if not tz or not moneda:
        raise ErrorValidacion("el documento de insights no trae cuenta.timezone_name / cuenta.currency")
    aplicadas = 0
    for fila in documento.get("filas", []):
        fecha = str(fila.get("date_start") or "")
        if desde <= fecha <= hasta:
            aplicar_fila(conn, oferta_id, fila, tz=str(tz), moneda=str(moneda).upper(), ahora=ahora)
            aplicadas += 1
    return aplicadas


def cargar_fixture(ruta: Path) -> dict[str, Any]:
    """Lee un documento de insights grabado: ``{"sintetico", "fuente", "cuenta", "filas": [...]}``."""
    datos = comun.cargar_json(ruta)
    if not isinstance(datos, dict) or not isinstance(datos.get("filas"), list):
        raise ErrorValidacion(f"{ruta.name}: se esperaba un objeto con la clave «filas» (lista)")
    return datos


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datos.etl_meta", description="ETL de insights de Meta (por anuncio y día).")
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--desde", required=True, help="AAAA-MM-DD")
    ap.add_argument("--hasta", required=True, help="AAAA-MM-DD")
    ap.add_argument("--fixture", help="ruta a un documento de insights grabado (modo fixture)")
    ap.add_argument("--db", help="URL de base de datos (por defecto sqlite bajo <raíz>/empresa/datos/fabrica.db)")
    ap.add_argument("--live", action="store_true")
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
        if args.live:
            raise ErrorExterno(
                "modo live sin conector: datos.etl_meta no tiene un cliente de la Graph API en esta "
                "sesión (sin red); meta.insights (B5) debe entregar el documento vía --fixture"
            )
        if not args.fixture:
            raise ErrorUso("falta --fixture (modo fixture); --live no está disponible esta noche")
        documento = cargar_fixture(Path(args.fixture))
        conn = conectar(args.db or f"sqlite:///{ruta_db_por_defecto(raiz)}")
        migrar(conn)
        ahora = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        n = aplicar_insights(conn, args.oferta, documento, desde=args.desde, hasta=args.hasta, ahora=ahora)
        conn.commit()
        if args.json:
            print(json.dumps({"ok": True, "modo": "fixture", "codigo": 0, "datos": {"filas_aplicadas": n}, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(f"etl_meta: {n} filas aplicadas")
        conn.cerrar()
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
