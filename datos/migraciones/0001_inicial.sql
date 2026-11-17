-- 0001_inicial.sql — esquema portable de datos (B3, docs/06 §4.4).
-- SQL ÚNICO: se ejecuta tal cual en SQLite y, con el marcador traducido (datos.db.traducir_marcadores),
-- en PostgreSQL. Dinero en enteros de unidad menor (centavos); tiempo UTC ISO-8601 con Z; toda tabla
-- de hechos tiene una clave natural para upsert (convenciones §3, §4, §7). Sin AUTOINCREMENT ni tipos
-- específicos de un motor.

-- Deduplicación de eventos de Stripe: por event.id (clave) y además por (tipo, objeto_id), porque
-- Stripe puede emitir dos Event distintos para el mismo hecho (convenciones §7).
CREATE TABLE IF NOT EXISTS stripe_evento (
    event_id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    objeto_id TEXT NOT NULL,
    recibido_en TEXT NOT NULL,
    UNIQUE (tipo, objeto_id)
);

-- Copia cruda de cada insight de Meta por anuncio y día (auditoría y reproceso).
CREATE TABLE IF NOT EXISTS raw_meta_insight (
    ad_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    oferta_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    ingerido_en TEXT NOT NULL,
    PRIMARY KEY (ad_id, fecha)
);

-- Insights de Meta por anuncio y día, ya normalizados a unidad menor. `tz` es la zona IANA de la
-- cuenta (engine.comun.dia_de_cuenta): toda fecha de reporte de Meta se calcula con ella.
CREATE TABLE IF NOT EXISTS fact_meta_ad_dia (
    ad_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    oferta_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    adset_id TEXT NOT NULL,
    tz TEXT NOT NULL,
    gasto_minor INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    impresiones INTEGER NOT NULL,
    clics INTEGER NOT NULL,
    clics_enlace INTEGER NOT NULL,
    compras_meta INTEGER NOT NULL DEFAULT 0,
    ingerido_en TEXT NOT NULL,
    PRIMARY KEY (ad_id, fecha)
);
CREATE INDEX IF NOT EXISTS ix_fact_meta_ad_dia_oferta_fecha ON fact_meta_ad_dia (oferta_id, fecha);

-- Pedidos de Stripe (checkout.session.completed). `es_prueba` = sesión en modo prueba o
-- `metadata.verificacion = "1"`; `es_interna` = compra propia del dueño (parametros.dashboard
-- .compras_internas_ids). Las dos se excluyen del ledger y de la evidencia (convenciones §4.4).
CREATE TABLE IF NOT EXISTS fact_pedido (
    checkout_session_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    payment_intent_id TEXT,
    adid TEXT NOT NULL,
    visitor_id TEXT,
    monto_minor INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    creado_ts TEXT NOT NULL,
    dia_utc TEXT NOT NULL,
    es_prueba INTEGER NOT NULL DEFAULT 0,
    es_interna INTEGER NOT NULL DEFAULT 0,
    consent_marketing INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL,
    ingerido_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fact_pedido_oferta_dia ON fact_pedido (oferta_id, dia_utc);

-- Reembolsos de Stripe (charge.refunded), con `dia_utc` para los cortes diarios (convenciones §4).
CREATE TABLE IF NOT EXISTS fact_reembolso (
    stripe_refund_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    checkout_session_id TEXT NOT NULL,
    adid TEXT,
    monto_minor INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    motivo TEXT,
    creado_ts TEXT NOT NULL,
    dia_utc TEXT NOT NULL,
    ingerido_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fact_reembolso_oferta_dia ON fact_reembolso (oferta_id, dia_utc);

-- Disputas de Stripe (charge.dispute.created).
CREATE TABLE IF NOT EXISTS fact_disputa (
    dispute_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    checkout_session_id TEXT,
    monto_minor INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    estado TEXT NOT NULL,
    creado_ts TEXT NOT NULL,
    dia_utc TEXT NOT NULL,
    ingerido_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fact_disputa_oferta_dia ON fact_disputa (oferta_id, dia_utc);

-- Eventos de tracking de primera parte (PageView, ViewContent) recibidos por /api/ingesta/evento.
CREATE TABLE IF NOT EXISTS fact_evento_tracking (
    event_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    visitor_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    adid TEXT,
    ts TEXT NOT NULL,
    recibido_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fact_evento_tracking_oferta ON fact_evento_tracking (oferta_id, ts);
