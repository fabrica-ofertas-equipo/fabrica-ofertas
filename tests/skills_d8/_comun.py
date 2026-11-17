"""Utilidades compartidas de las pruebas de la skill d8-optimizacion (sin red, sin claves, sin tocar la base real).

Crean una base SQLite temporal aplicando las migraciones reales de ``datos/migraciones/*.sql`` y la pueblan con
filas de ejemplo (sintéticas). Los scripts de la skill no son un paquete: se importan por ruta.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SKILL = RAIZ / ".claude" / "skills" / "d8-optimizacion"
SCRIPTS = SKILL / "scripts"
MIGRACIONES = RAIZ / "datos" / "migraciones"

OFERTA = "OF-202611-02"
ADS = ["120000000000100", "120000000000101", "120000000000102"]
CAMPANA = "120000000000001"
CONJUNTO = "120000000000002"


def cargar_modulo(nombre: str):
    """Importa ``.claude/skills/d8-optimizacion/scripts/<nombre>.py`` por ruta."""
    ruta = SCRIPTS / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(f"d8_skill_{nombre}", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def crear_base(ruta: Path) -> None:
    """Crea una base con el esquema real (0001-0003) y 3 anuncios de la oferta de ejemplo."""
    conn = sqlite3.connect(ruta)
    for sql in sorted(MIGRACIONES.glob("*.sql")):
        conn.executescript(sql.read_text(encoding="utf-8"))
    for i, ad in enumerate(ADS):
        conn.execute("INSERT INTO dim_anuncio (ad_id, oferta_id, concepto_id) VALUES (?,?,?)", (ad, OFERTA, f"c0{i + 1}-mapas"))
    conn.commit()
    conn.close()


def meta(conn: sqlite3.Connection, ad: str, fecha: str, gasto: int, *, impr: int = 1000, clics: int = 20, compras_meta: int = 0,
         ingerido: str = "2026-11-09T08:30:00Z", moneda: str = "USD", tz: str = "Europe/Warsaw") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO fact_meta_ad_dia (ad_id, fecha, oferta_id, campaign_id, adset_id, tz, gasto_minor, moneda, impresiones, "
        "clics, clics_enlace, compras_meta, ingerido_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ad, fecha, OFERTA, CAMPANA, CONJUNTO, tz, gasto, moneda, impr, clics, clics, compras_meta, ingerido))


def pedido(conn: sqlite3.Connection, sid: str, creado_ts: str, *, adid: str = ADS[0], estado: str = "paid", prueba: int = 0,
           interna: int = 0, monto: int = 6300, moneda: str = "PLN") -> None:
    conn.execute(
        "INSERT INTO fact_pedido (checkout_session_id, oferta_id, payment_intent_id, adid, visitor_id, monto_minor, moneda, creado_ts, dia_utc, "
        "es_prueba, es_interna, consent_marketing, estado, ingerido_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, OFERTA, f"pi_{sid}", adid, f"v_{sid}", monto, moneda, creado_ts, creado_ts[:10], prueba, interna, 0, estado, creado_ts))


def evento(conn: sqlite3.Connection, eid: str, tipo: str, visitante: str, ts: str, *, adid: str | None = ADS[0]) -> None:
    conn.execute(
        "INSERT INTO fact_evento (event_id, oferta_id, tipo, ts, visitor_id, cid, asid, adid, fuente, consentimiento, valor_minor, moneda, recibido_en) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid, OFERTA, tipo, ts, visitante, CAMPANA, CONJUNTO, adid, "navegador", 1, None, None, ts))


def umbrales_prueba() -> dict:
    """Los umbrales de prueba de ``evals/_base/umbrales_prueba.json`` (valores de ejemplo, NO son los firmados)."""
    doc = json.loads((SKILL / "evals" / "_base" / "umbrales_prueba.json").read_text(encoding="utf-8"))
    return dict(doc["umbrales"])


def no_hay_floats(valor, ruta: str = "$") -> list[str]:
    """Rutas de todo ``float`` dentro de un documento JSON ya cargado (debe ser una lista vacía)."""
    if isinstance(valor, float):
        return [ruta]
    if isinstance(valor, dict):
        return [r for k, v in valor.items() for r in no_hay_floats(v, f"{ruta}.{k}")]
    if isinstance(valor, list):
        return [r for i, v in enumerate(valor) for r in no_hay_floats(v, f"{ruta}[{i}]")]
    return []
