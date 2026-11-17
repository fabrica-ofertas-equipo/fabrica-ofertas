"""Ledger y conciliación triple Stripe↔ledger↔Meta (`datos.ledger`, docs/06 §4.4).

El ledger (`empresa/finanzas/ledger.jsonl`) es *append-only* (convenciones §1); el «upsert por clave
natural» de una línea ya escrita se hace agregando una línea NUEVA con el mismo `clave_natural`: un
lector toma la ÚLTIMA ocurrencia de cada clave como vigente (:func:`leer_vigente`). Reaplicar el mismo
periodo dos veces no agrega líneas si el contenido no cambió (idempotente, criterio B0-15).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion
from scripts.validar_esquemas import errores_de_esquema, hash_objeto

from datos import atribucion
from datos.db import Conexion, conectar, migrar
from datos.etl_stripe import ruta_db_por_defecto

__all__ = ["conciliar", "escribir_ledger", "generar_lineas", "leer_vigente", "main", "ruta_conciliacion", "ruta_ledger"]

SCHEMA_VERSION_LEDGER = "1.0.0"
SCHEMA_VERSION_CONCILIACION = "1.1.0"


def ruta_ledger(raiz: Path) -> Path:
    return raiz / "empresa" / "finanzas" / "ledger.jsonl"


def ruta_conciliacion(raiz: Path) -> Path:
    return raiz / "empresa" / "finanzas" / "conciliacion.json"


def _linea_pedido(oferta_id: str, pedido: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION_LEDGER, "clave_natural": f"stripe:{pedido['checkout_session_id']}",
        "tipo": "pedido", "oferta_id": oferta_id, "fecha": pedido["dia_utc"], "ts": pedido["creado_ts"],
        "sentido": "entrada", "importe": {"monto": int(pedido["monto_minor"]), "moneda": pedido["moneda"]},
        "fuente": "stripe", "es_prueba": False, "adid": pedido["adid"] or "desconocido",
    }


def _linea_gasto(oferta_id: str, fila: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION_LEDGER, "clave_natural": f"meta:{fila['ad_id']}:{fila['fecha']}",
        "tipo": "gasto", "oferta_id": oferta_id, "fecha": fila["fecha"], "ts": fila["fecha"] + "T00:00:00Z",
        "sentido": "salida", "importe": {"monto": int(fila["gasto_minor"]), "moneda": fila["moneda"]},
        "fuente": "meta", "es_prueba": False, "adid": fila["ad_id"],
    }


def _linea_reembolso(oferta_id: str, fila: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION_LEDGER, "clave_natural": f"stripe:{fila['stripe_refund_id']}",
        "tipo": "reembolso", "oferta_id": oferta_id, "fecha": fila["dia_utc"], "ts": fila["creado_ts"],
        "sentido": "salida", "importe": {"monto": int(fila["monto_minor"]), "moneda": fila["moneda"]},
        "fuente": "stripe", "es_prueba": False, "adid": fila["adid"] or "desconocido",
    }


def _linea_costo(oferta_id: str, costo: dict[str, Any]) -> dict[str, Any]:
    monto = costo["monto"]
    return {
        "schema_version": SCHEMA_VERSION_LEDGER,
        "clave_natural": f"costos:{hash_objeto(costo)[len('sha256:'):][:40]}",
        "tipo": "costo", "oferta_id": oferta_id, "fecha": costo["ts"][:10], "ts": costo["ts"],
        "sentido": "salida", "importe": {"monto": int(monto["monto"]), "moneda": monto["moneda"]},
        "fuente": "costos", "es_prueba": False,
    }


def _costos_de_oferta(raiz: Path, oferta_id: str, desde: str, hasta: str) -> list[dict[str, Any]]:
    ruta = raiz / "empresa" / "costos.jsonl"
    return [c for c in comun.leer_jsonl(ruta) if c.get("oferta_id") == oferta_id and desde <= c.get("ts", "")[:10] <= hasta]


def generar_lineas(conn: Conexion, raiz: Path, oferta_id: str, desde: str, hasta: str) -> list[dict[str, Any]]:
    """Líneas de ledger de `oferta_id` en `[desde, hasta]`: pedidos, gasto de Meta, reembolsos y costos."""
    lineas: list[dict[str, Any]] = []
    for pedido in atribucion.pedidos_cohorte(conn, oferta_id, hasta):
        if pedido.creado_ts[:10] < desde:
            continue
        lineas.append(_linea_pedido(oferta_id, {
            "checkout_session_id": pedido.checkout_session_id, "dia_utc": pedido.creado_ts[:10],
            "creado_ts": pedido.creado_ts, "monto_minor": pedido.monto_minor, "moneda": pedido.moneda,
            "adid": pedido.adid,
        }))
    for fila in conn.ejecutar(
        "SELECT ad_id, fecha, gasto_minor, moneda FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha BETWEEN ? AND ?",
        (oferta_id, desde, hasta),
    ).fetchall():
        lineas.append(_linea_gasto(oferta_id, fila))
    for fila in conn.ejecutar(
        "SELECT stripe_refund_id, dia_utc, creado_ts, monto_minor, moneda, adid FROM fact_reembolso "
        "WHERE oferta_id = ? AND dia_utc BETWEEN ? AND ?",
        (oferta_id, desde, hasta),
    ).fetchall():
        lineas.append(_linea_reembolso(oferta_id, fila))
    for costo in _costos_de_oferta(raiz, oferta_id, desde, hasta):
        lineas.append(_linea_costo(oferta_id, costo))
    for linea in lineas:
        errores = errores_de_esquema("ledger", linea)
        if errores:
            raise ErrorValidacion(f"línea de ledger inválida ({linea.get('clave_natural')}): {comun.resumir_errores_esquema(errores)}")
    return lineas


def leer_vigente(ruta: Path) -> dict[str, dict[str, Any]]:
    """Mapa ``clave_natural -> última línea`` del ledger (lo que un lector considera vigente)."""
    vigente: dict[str, dict[str, Any]] = {}
    for linea in comun.leer_jsonl(ruta):
        vigente[linea["clave_natural"]] = linea
    return vigente


def escribir_ledger(ruta: Path, lineas: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Agrega las líneas NUEVAS o CAMBIADAS; una línea idéntica a la vigente no se repite (idempotente)."""
    vigente = leer_vigente(ruta)
    nuevas = sin_cambios = 0
    for linea in lineas:
        actual = vigente.get(linea["clave_natural"])
        if actual is not None and hash_objeto(actual) == hash_objeto(linea):
            sin_cambios += 1
            continue
        comun.anexar_jsonl(ruta, linea)
        vigente[linea["clave_natural"]] = linea
        nuevas += 1
    return {"nuevas": nuevas, "sin_cambios": sin_cambios}


def _comparar(izquierda: int, derecha: int, moneda: str) -> dict[str, Any]:
    return {"izquierda": {"monto": izquierda, "moneda": moneda}, "derecha": {"monto": derecha, "moneda": moneda},
            "diferencia": {"monto": izquierda - derecha, "moneda": moneda}}


def conciliar(conn: Conexion, raiz: Path, oferta_id: str, desde: str, hasta: str, moneda: str, *,
             ahora: Callable[[], datetime] = comun.ahora_utc) -> dict[str, Any]:
    """Conciliación triple Stripe↔ledger (pedidos) y Meta↔ledger (gasto) de `[desde, hasta]`.

    `izquierda` es siempre la fuente (Stripe o Meta) leída directo de las tablas de hecho; `derecha`
    es lo que quedó vigente en el ledger para el mismo periodo. `pendientes_asincronos` queda en 0:
    los medios de pago asíncronos (OXXO, vouchers) no están modelados esta noche (ver README, Pedidos).
    """
    vigente = leer_vigente(ruta_ledger(raiz))
    lineas_oferta = [l for l in vigente.values() if l["oferta_id"] == oferta_id and desde <= l["fecha"] <= hasta]
    for linea in lineas_oferta:
        if linea["importe"]["moneda"] != moneda:
            raise ErrorValidacion(f"moneda distinta en el ledger ({linea['importe']['moneda']}) de la pedida ({moneda}); sin tipo de cambio registrado no se compara")

    pedidos_stripe = conn.ejecutar(
        "SELECT COALESCE(SUM(monto_minor), 0) FROM fact_pedido WHERE oferta_id = ? AND dia_utc BETWEEN ? AND ? "
        "AND es_prueba = 0 AND es_interna = 0 AND moneda = ?",
        (oferta_id, desde, hasta, moneda),
    ).fetchone()[0]
    pedidos_ledger = sum(l["importe"]["monto"] for l in lineas_oferta if l["tipo"] == "pedido")
    gasto_meta = conn.ejecutar(
        "SELECT COALESCE(SUM(gasto_minor), 0) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha BETWEEN ? AND ? AND moneda = ?",
        (oferta_id, desde, hasta, moneda),
    ).fetchone()[0]
    gasto_ledger = sum(l["importe"]["monto"] for l in lineas_oferta if l["tipo"] == "gasto")

    compras_stripe = conn.ejecutar(
        "SELECT COUNT(*) FROM fact_pedido WHERE oferta_id = ? AND dia_utc BETWEEN ? AND ? AND es_prueba = 0 AND es_interna = 0",
        (oferta_id, desde, hasta),
    ).fetchone()[0]
    compras_meta = conn.ejecutar(
        "SELECT COALESCE(SUM(compras_meta), 0) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha BETWEEN ? AND ?",
        (oferta_id, desde, hasta),
    ).fetchone()[0]
    pruebas = conn.ejecutar(
        "SELECT COUNT(*) FROM fact_pedido WHERE oferta_id = ? AND dia_utc BETWEEN ? AND ? AND es_prueba = 1",
        (oferta_id, desde, hasta),
    ).fetchone()[0]
    internas = conn.ejecutar(
        "SELECT COUNT(*) FROM fact_pedido WHERE oferta_id = ? AND dia_utc BETWEEN ? AND ? AND es_prueba = 0 AND es_interna = 1",
        (oferta_id, desde, hasta),
    ).fetchone()[0]

    hay_datos = (compras_stripe + compras_meta + pruebas + internas) > 0 or gasto_meta > 0
    stripe_vs_ledger = _comparar(int(pedidos_stripe), int(pedidos_ledger), moneda)
    gasto_vs_ledger = _comparar(int(gasto_meta), int(gasto_ledger), moneda)
    if not hay_datos:
        estado = "INCOMPLETO"
    elif stripe_vs_ledger["diferencia"]["monto"] != 0 or gasto_vs_ledger["diferencia"]["monto"] != 0:
        estado = "DESCUADRE"
    else:
        estado = "CONCILIADO"

    return {
        "schema_version": SCHEMA_VERSION_CONCILIACION,
        "oferta_id": oferta_id,
        "periodo": {"desde": desde, "hasta": hasta},
        "generado_en": comun.iso_z(comun.instante(ahora)),
        "moneda": moneda,
        "stripe_vs_ledger": stripe_vs_ledger,
        "gasto_meta_vs_ledger": gasto_vs_ledger,
        "compras": {"meta": int(compras_meta), "stripe": int(compras_stripe),
                   "razon_meta_stripe": atribucion.razon_meta_stripe(conn, oferta_id, desde, hasta)},
        "cobertura_adid_bp": atribucion.cobertura_adid(conn, oferta_id, desde, hasta),
        "excluidos": {"pruebas": int(pruebas), "internas": int(internas)},
        "pendientes_asincronos": 0,
        "estado": estado,
        "cifras_tachadas": estado != "CONCILIADO",
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datos.ledger", description="Líneas de ledger y conciliación de una oferta.")
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--periodo", required=True, help="AAAA-MM-DD:AAAA-MM-DD (desde:hasta)")
    ap.add_argument("--moneda", required=True)
    ap.add_argument("--db")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--raiz")
    ap.add_argument("--ahora")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        if ":" not in args.periodo:
            raise ErrorUso("--periodo exige «desde:hasta» (AAAA-MM-DD:AAAA-MM-DD)")
        desde, hasta = args.periodo.split(":", 1)
        env = dict(os.environ)
        if args.raiz:
            if comun.entorno(env) == "produccion":
                raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
            env["FABRICA_RAIZ"] = str(Path(args.raiz).resolve())
        raiz = comun.raiz(env)
        conn = conectar(args.db or f"sqlite:///{ruta_db_por_defecto(raiz)}")
        migrar(conn)
        ahora = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        lineas = generar_lineas(conn, raiz, args.oferta, desde, hasta)
        resumen = escribir_ledger(ruta_ledger(raiz), lineas)
        conciliacion = conciliar(conn, raiz, args.oferta, desde, hasta, args.moneda, ahora=ahora)
        errores = errores_de_esquema("conciliacion", conciliacion)
        if errores:
            raise ErrorValidacion(f"conciliacion.json inválida: {comun.resumir_errores_esquema(errores)}")
        comun.escribir_atomico(ruta_conciliacion(raiz), comun.json_canonico(conciliacion))
        datos_salida = {"ledger": resumen, "conciliacion": conciliacion}
        if args.json:
            print(json.dumps({"ok": True, "modo": "dry_run", "codigo": 0, "datos": datos_salida, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(f"ledger: {resumen['nuevas']} nuevas, {resumen['sin_cambios']} sin cambios; conciliación {conciliacion['estado']}")
        conn.cerrar()
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
