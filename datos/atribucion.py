"""Atribución Meta↔Stripe: cobertura de `adid`, razón Meta/Stripe, evidencia y cohortes (docs/06 §4.4).

Capa de lectura PURA (solo `SELECT`): no decide nada. `evidencia_celda` entrega los agregados crudos de
una ventana; la corrección por cobertura (`compras_corregidas`, `tracking_sano`) que alimenta las
reglas de D8 es de `decision/entradas.py` (B1, docs/06 §4.2) y debe llamar a esta función, no
reimplementar el `SELECT`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from scripts.validar_esquemas import entero_redondeado

from datos.db import Conexion

__all__ = ["EvidenciaCelda", "PedidoStripe", "cobertura_adid", "evidencia_celda", "pedidos_cohorte", "razon_meta_stripe"]


def _total_pedidos(conn: Conexion, oferta_id: str, desde: str, hasta: str, *, solo_adid_conocido: bool = False) -> int:
    condicion_adid = " AND adid != 'desconocido'" if solo_adid_conocido else ""
    fila = conn.ejecutar(
        f"SELECT COUNT(*) FROM fact_pedido WHERE oferta_id = ? AND dia_utc BETWEEN ? AND ? "
        f"AND es_prueba = 0 AND es_interna = 0{condicion_adid}",
        (oferta_id, desde, hasta),
    ).fetchone()
    return int(fila[0])


def cobertura_adid(conn: Conexion, oferta_id: str, desde: str, hasta: str) -> int:
    """Puntos básicos (0-10000) de pedidos (sin prueba/internos) con `adid` conocido en `[desde, hasta]`.

    `0` tanto si no hay pedidos como si ninguno trae `adid`; quien lea el resultado distingue los dos
    casos consultando el total por separado (criterio B0-15: cobertura >= `landing.captura_adid_min_pct`).
    """
    total = _total_pedidos(conn, oferta_id, desde, hasta)
    if total == 0:
        return 0
    conocidos = _total_pedidos(conn, oferta_id, desde, hasta, solo_adid_conocido=True)
    return entero_redondeado(conocidos * 10000, total, "half_even")


def _compras_meta(conn: Conexion, oferta_id: str, desde: str, hasta: str) -> int:
    fila = conn.ejecutar(
        "SELECT COALESCE(SUM(compras_meta), 0) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha BETWEEN ? AND ?",
        (oferta_id, desde, hasta),
    ).fetchone()
    return int(fila[0])


def razon_meta_stripe(conn: Conexion, oferta_id: str, desde: str, hasta: str) -> str | None:
    """Razón compras Meta / compras Stripe, como cadena decimal a 2 decimales; ``None`` sin compras Stripe."""
    compras_stripe = _total_pedidos(conn, oferta_id, desde, hasta)
    if compras_stripe == 0:
        return None
    compras_meta = _compras_meta(conn, oferta_id, desde, hasta)
    razon = (Decimal(compras_meta) / Decimal(compras_stripe)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return str(razon)


def _gasto_meta_minor(conn: Conexion, oferta_id: str, desde: str, hasta: str) -> tuple[int, str | None]:
    fila = conn.ejecutar(
        "SELECT COALESCE(SUM(gasto_minor), 0), MIN(moneda) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha BETWEEN ? AND ?",
        (oferta_id, desde, hasta),
    ).fetchone()
    return int(fila[0]), fila[1]


@dataclass(frozen=True)
class EvidenciaCelda:
    """Agregados crudos de una ventana (sin corrección por cobertura; esa corrección es de `decision`)."""

    oferta_id: str
    desde: str
    hasta: str
    compras_atribuidas: int
    gasto_meta_minor: int
    moneda_gasto: str | None
    compras_meta: int
    cobertura_adid_bp: int
    razon_meta_stripe: str | None


def evidencia_celda(conn: Conexion, oferta_id: str, desde: str, hasta: str) -> EvidenciaCelda:
    """Agregados crudos Meta+Stripe de `[desde, hasta]` para una oferta (una celda, docs/06 §1)."""
    compras_atribuidas = _total_pedidos(conn, oferta_id, desde, hasta)
    gasto_minor, moneda_gasto = _gasto_meta_minor(conn, oferta_id, desde, hasta)
    return EvidenciaCelda(
        oferta_id=oferta_id, desde=desde, hasta=hasta, compras_atribuidas=compras_atribuidas,
        gasto_meta_minor=gasto_minor, moneda_gasto=moneda_gasto, compras_meta=_compras_meta(conn, oferta_id, desde, hasta),
        cobertura_adid_bp=cobertura_adid(conn, oferta_id, desde, hasta),
        razon_meta_stripe=razon_meta_stripe(conn, oferta_id, desde, hasta),
    )


@dataclass(frozen=True)
class PedidoStripe:
    """Un pedido de la cohorte, con lo reembolsado hasta la fecha de corte."""

    checkout_session_id: str
    oferta_id: str
    monto_minor: int
    moneda: str
    adid: str
    creado_ts: str
    es_prueba: bool
    reembolsado_minor: int


def pedidos_cohorte(conn: Conexion, oferta_id: str, hasta: str) -> list[PedidoStripe]:
    """Pedidos de `oferta_id` creados hasta `hasta` (``AAAA-MM-DD``, inclusive), con su reembolso acumulado.

    Excluye siempre pruebas e internas (convenciones §4.4); no filtra por madurez de garantía (eso es
    de `decision`).
    """
    filas = conn.ejecutar(
        "SELECT p.checkout_session_id, p.oferta_id, p.monto_minor, p.moneda, p.adid, p.creado_ts, "
        "       COALESCE((SELECT SUM(r.monto_minor) FROM fact_reembolso r "
        "                 WHERE r.checkout_session_id = p.checkout_session_id), 0) AS reembolsado_minor "
        "FROM fact_pedido p "
        "WHERE p.oferta_id = ? AND p.dia_utc <= ? AND p.es_prueba = 0 AND p.es_interna = 0 "
        "ORDER BY p.creado_ts",
        (oferta_id, hasta),
    ).fetchall()
    return [
        PedidoStripe(
            checkout_session_id=f["checkout_session_id"], oferta_id=f["oferta_id"], monto_minor=int(f["monto_minor"]),
            moneda=f["moneda"], adid=f["adid"], creado_ts=f["creado_ts"], es_prueba=False,
            reembolsado_minor=int(f["reembolsado_minor"]),
        )
        for f in filas
    ]
