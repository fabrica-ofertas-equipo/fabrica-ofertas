"""Paquete `datos`: ETL de Meta y Stripe, ingesta de eventos, atribución, ledger y KPI (B3).

Solo biblioteca estándar: `datos.db` envuelve `sqlite3` (hoy) y traduce los marcadores de parámetro
(``?`` -> ``%s``) para que el mismo SQL sirva, el día que haya un controlador, a PostgreSQL.

Módulos:
  db          conexión portable, migraciones y `upsert` por clave natural.
  ingesta     controlador puro del endpoint de ingesta de eventos de tracking (PageView/ViewContent).
  etl_meta    inserta insights de Meta por anuncio y día (`fact_meta_ad_dia`).
  etl_stripe  aplica eventos de Stripe (pedidos, reembolsos, disputas) con deduplicación.
  atribucion  cobertura de `adid`, razón Meta/Stripe, evidencia de celda, cohortes de pedidos.
  ledger      líneas del ledger (`empresa/finanzas/ledger.jsonl`) y conciliación triple.
  kpi         snapshot diario de KPI (`empresa/datos/kpi_oferta_dia.json`).

Dinero en enteros de unidad menor + ISO 4217 (nunca `float`); tiempo UTC ISO-8601 con `Z`; toda carga
es un upsert por clave natural (convenciones §3, §4, §7).
"""

__all__ = ["db", "ingesta", "etl_meta", "etl_stripe", "atribucion", "ledger", "kpi"]
