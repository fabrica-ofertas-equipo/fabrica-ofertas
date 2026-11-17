"""ETL de Stripe: aplica eventos (pedidos, reembolsos, disputas) con deduplicación (docs/06 §4.4).

Los importes de Stripe YA vienen en unidad menor (centavos): a diferencia de Meta, no hace falta
convertir. `aplicar_stripe` es la función pura que un backfill por cursor (``--live``, fuera de
alcance esta noche) o un lote grabado (``--fixture``) alimentan por igual; el dato nunca se
interpreta como instrucción (convenciones §10): si no cumple la forma esperada se descarta con un
aviso, no se ejecuta nada a partir de su contenido.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from engine import comun
from engine.errores import ErrorExterno, ErrorLimite, ErrorUso, ErrorValidacion
from engine.parametros import cargar_parametros, ruta_por_defecto

from datos.db import Conexion, conectar, migrar

__all__ = ["aplicar_evento", "aplicar_lote", "cargar_fixture", "main", "ruta_db_por_defecto"]

_RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_RX_ID_META = re.compile(r"^[0-9]{5,25}$")
_TIPOS_SOPORTADOS = ("checkout.session.completed", "charge.refunded", "charge.dispute.created")


def ruta_db_por_defecto(raiz: Path) -> Path:
    """``<raíz>/empresa/datos/fabrica.db``: base de datos de prueba/dry-run por defecto."""
    return raiz / "empresa" / "datos" / "fabrica.db"


def _normalizar_adid(valor: Any) -> str:
    """``adid`` del catálogo de Meta o ``"desconocido"`` si falta o no cumple el patrón (tracking §4.3)."""
    return valor if isinstance(valor, str) and _RX_ID_META.match(valor) else "desconocido"


def _dia_utc(ts_epoch: int) -> tuple[str, str]:
    """``(creado_ts ISO Z, dia_utc AAAA-MM-DD)`` a partir de un epoch de Stripe (segundos UTC)."""
    momento = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)
    return comun.iso_z(momento), momento.date().isoformat()


def _objeto_id(tipo: str, obj: Mapping[str, Any]) -> str:
    """Identificador del HECHO (no del evento) usado para deduplicar ``(tipo, objeto_id)``."""
    if tipo == "checkout.session.completed":
        return str(obj["id"])
    if tipo == "charge.refunded":
        reembolsos = ((obj.get("refunds") or {}).get("data")) or []
        if reembolsos:
            return str(reembolsos[-1]["id"])
        return str(obj["id"])
    if tipo == "charge.dispute.created":
        return str(obj["id"])
    raise ErrorValidacion(f"tipo de evento de Stripe no soportado: {tipo!r}")


def _es_interna(session_id: str, compras_internas_ids: Sequence[str] | None) -> bool:
    return bool(compras_internas_ids) and session_id in set(compras_internas_ids)


def _aplicar_checkout_completado(conn: Conexion, obj: Mapping[str, Any], *, evento_creado: int, ahora_iso: str,
                                 compras_internas_ids: Sequence[str] | None) -> None:
    metadata = obj.get("metadata") or {}
    oferta_id = metadata.get("oferta_id")
    if not isinstance(oferta_id, str) or not _RX_OFERTA.match(oferta_id):
        raise ErrorValidacion("checkout.session.completed sin metadata.oferta_id válida: dato hostil, se descarta")
    creado_ts, dia_utc = _dia_utc(int(obj.get("created") or evento_creado))
    session_id = str(obj["id"])
    conn.upsert("fact_pedido", ["checkout_session_id"], {
        "checkout_session_id": session_id,
        "oferta_id": oferta_id,
        "payment_intent_id": obj.get("payment_intent"),
        "adid": _normalizar_adid(metadata.get("adid")),
        "visitor_id": metadata.get("visitor_id"),
        "monto_minor": int(obj["amount_total"]),
        "moneda": str(obj["currency"]).upper(),
        "creado_ts": creado_ts,
        "dia_utc": dia_utc,
        "es_prueba": 1 if (obj.get("livemode") is False or metadata.get("verificacion") == "1") else 0,
        "es_interna": 1 if _es_interna(session_id, compras_internas_ids) else 0,
        "consent_marketing": 1 if metadata.get("consent_marketing") == "1" else 0,
        "estado": str(obj.get("payment_status") or "pagado"),
        "ingerido_en": ahora_iso,
    })


def _buscar_pedido_por_intent(conn: Conexion, payment_intent_id: str | None) -> sqlite3.Row | None:
    if not payment_intent_id:
        return None
    fila = conn.ejecutar(
        "SELECT checkout_session_id, oferta_id, adid FROM fact_pedido WHERE payment_intent_id = ?",
        (payment_intent_id,),
    ).fetchone()
    return fila


def _aplicar_reembolso(conn: Conexion, obj: Mapping[str, Any], *, evento_creado: int, ahora_iso: str) -> None:
    reembolsos = ((obj.get("refunds") or {}).get("data")) or []
    if not reembolsos:
        raise ErrorValidacion("charge.refunded sin refunds.data: nada que aplicar")
    refund = reembolsos[-1]
    pedido = _buscar_pedido_por_intent(conn, obj.get("payment_intent"))
    metadata = obj.get("metadata") or {}
    oferta_id = (pedido["oferta_id"] if pedido else metadata.get("oferta_id"))
    if not isinstance(oferta_id, str) or not _RX_OFERTA.match(oferta_id):
        raise ErrorValidacion("charge.refunded sin oferta_id resoluble (ni por payment_intent ni por metadata)")
    session_id = (pedido["checkout_session_id"] if pedido else metadata.get("checkout_session_id")) or str(obj["id"])
    adid = pedido["adid"] if pedido else _normalizar_adid(metadata.get("adid"))
    creado_ts, dia_utc = _dia_utc(int(refund.get("created") or obj.get("created") or evento_creado))
    conn.upsert("fact_reembolso", ["stripe_refund_id"], {
        "stripe_refund_id": str(refund["id"]),
        "oferta_id": oferta_id,
        "checkout_session_id": session_id,
        "adid": adid,
        "monto_minor": int(refund["amount"]),
        "moneda": str(obj["currency"]).upper(),
        "motivo": refund.get("reason"),
        "creado_ts": creado_ts,
        "dia_utc": dia_utc,
        "ingerido_en": ahora_iso,
    })


def _aplicar_disputa(conn: Conexion, obj: Mapping[str, Any], *, evento_creado: int, ahora_iso: str) -> None:
    pedido = _buscar_pedido_por_intent(conn, obj.get("payment_intent"))
    metadata = obj.get("metadata") or {}
    oferta_id = (pedido["oferta_id"] if pedido else metadata.get("oferta_id")) or "empresa"
    creado_ts, dia_utc = _dia_utc(int(obj.get("created") or evento_creado))
    conn.upsert("fact_disputa", ["dispute_id"], {
        "dispute_id": str(obj["id"]),
        "oferta_id": oferta_id,
        "checkout_session_id": pedido["checkout_session_id"] if pedido else None,
        "monto_minor": int(obj["amount"]),
        "moneda": str(obj["currency"]).upper(),
        "estado": str(obj["status"]),
        "creado_ts": creado_ts,
        "dia_utc": dia_utc,
        "ingerido_en": ahora_iso,
    })


def aplicar_evento(conn: Conexion, evento: Mapping[str, Any], *, ahora: Callable[[], datetime] = comun.ahora_utc,
                   compras_internas_ids: Sequence[str] | None = None) -> Literal["nuevo", "duplicado"]:
    """Aplica UN evento de Stripe; dedup por `event.id` Y por `(tipo, objeto_id)` (convenciones §7).

    La decisión de duplicado se toma con un `UNIQUE` de SQL (atómico dentro de la conexión), nunca en
    un almacén no transaccional. Un evento de tipo no soportado o sin los campos esperados es
    ``ErrorValidacion`` (dato hostil tratado como dato, nunca como instrucción).
    """
    if not isinstance(evento, Mapping) or "id" not in evento or "type" not in evento:
        raise ErrorValidacion("evento de Stripe mal formado: faltan id/type")
    tipo = str(evento["type"])
    if tipo not in _TIPOS_SOPORTADOS:
        raise ErrorValidacion(f"tipo de evento de Stripe no soportado: {tipo!r}")
    obj = (evento.get("data") or {}).get("object")
    if not isinstance(obj, Mapping):
        raise ErrorValidacion("evento de Stripe sin data.object")
    if "created" not in evento:
        raise ErrorValidacion("evento de Stripe sin created")
    evento_creado = int(evento["created"])
    objeto_id = _objeto_id(tipo, obj)
    event_id = str(evento["id"])
    ya_visto = conn.ejecutar(
        "SELECT 1 FROM stripe_evento WHERE event_id = ? OR (tipo = ? AND objeto_id = ?)",
        (event_id, tipo, objeto_id),
    ).fetchone()
    if ya_visto is not None:
        return "duplicado"
    # El hecho se aplica ANTES de marcar el evento como visto: si falla, no queda un dedup "fantasma"
    # que impida reintentar (los upserts de los hechos son idempotentes, así que una carrera rara que
    # duplique el trabajo es inocua; lo que no puede pasar es marcar como visto algo que no se aplicó).
    ahora_iso = comun.iso_z(comun.instante(ahora))
    if tipo == "checkout.session.completed":
        _aplicar_checkout_completado(conn, obj, evento_creado=evento_creado, ahora_iso=ahora_iso,
                                     compras_internas_ids=compras_internas_ids)
    elif tipo == "charge.refunded":
        _aplicar_reembolso(conn, obj, evento_creado=evento_creado, ahora_iso=ahora_iso)
    else:
        _aplicar_disputa(conn, obj, evento_creado=evento_creado, ahora_iso=ahora_iso)
    try:
        conn.ejecutar(
            "INSERT INTO stripe_evento (event_id, tipo, objeto_id, recibido_en) VALUES (?, ?, ?, ?)",
            (event_id, tipo, objeto_id, ahora_iso),
        )
    except sqlite3.IntegrityError:
        conn.commit()  # el hecho (idempotente) ya quedó aplicado; solo hubo una carrera al marcar el dedup
        return "duplicado"
    conn.commit()
    return "nuevo"


def aplicar_lote(conn: Conexion, eventos: Sequence[Mapping[str, Any]], *, ahora: Callable[[], datetime] = comun.ahora_utc,
                 compras_internas_ids: Sequence[str] | None = None) -> dict[str, int]:
    """Aplica una lista de eventos en orden; devuelve ``{"nuevos": N, "duplicados": N}``."""
    conteo = {"nuevos": 0, "duplicados": 0}
    for evento in eventos:
        resultado = aplicar_evento(conn, evento, ahora=ahora, compras_internas_ids=compras_internas_ids)
        conteo["nuevos" if resultado == "nuevo" else "duplicados"] += 1
    return conteo


def cargar_fixture(ruta: Path) -> dict[str, Any]:
    """Lee un lote de eventos grabado: ``{"sintetico": bool, "fuente": str, "eventos": [...]}``."""
    datos = comun.cargar_json(ruta)
    if not isinstance(datos, dict) or not isinstance(datos.get("eventos"), list):
        raise ErrorValidacion(f"{ruta.name}: se esperaba un objeto con la clave «eventos» (lista)")
    return datos


def _filtrar_desde(eventos: Sequence[Mapping[str, Any]], desde: str | None) -> list[Mapping[str, Any]]:
    if not desde:
        return list(eventos)
    limite = comun.parsear_z(desde + "T00:00:00Z") if len(desde) == len("AAAA-MM-DD") else comun.parsear_z(desde)
    return [e for e in eventos if datetime.fromtimestamp(int(e.get("created") or 0), tz=timezone.utc) >= limite]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datos.etl_stripe", description="ETL de eventos de Stripe (pedidos, reembolsos, disputas).")
    ap.add_argument("--desde", help="AAAA-MM-DD: solo eventos creados desde esa fecha (backfill parcial)")
    ap.add_argument("--fixture", help="ruta a un lote grabado de eventos (modo fixture; ver tests/fixtures/datos/)")
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
                "modo live sin conector: datos.etl_stripe no tiene un controlador de Stripe en esta "
                "sesión (sin red); usar --fixture con un lote grabado"
            )
        if not args.fixture:
            raise ErrorUso("falta --fixture (modo fixture); --live no está disponible esta noche")
        documento = cargar_fixture(Path(args.fixture))
        eventos = _filtrar_desde(documento["eventos"], args.desde)
        conn = conectar(args.db or f"sqlite:///{ruta_db_por_defecto(raiz)}")
        migrar(conn)
        ahora = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        try:
            compras_internas_ids = cargar_parametros(ruta_por_defecto(raiz)).valor("dashboard.compras_internas_ids")
        except ErrorLimite:
            compras_internas_ids = None
        conteo = aplicar_lote(conn, eventos, ahora=ahora, compras_internas_ids=compras_internas_ids)
        datos_salida = {"eventos_leidos": len(eventos), **conteo}
        if args.json:
            print(json.dumps({"ok": True, "modo": "fixture", "codigo": 0, "datos": datos_salida, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(f"etl_stripe: {conteo['nuevos']} nuevos, {conteo['duplicados']} duplicados de {len(eventos)} eventos")
        conn.cerrar()
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
