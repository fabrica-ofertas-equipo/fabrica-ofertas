-- 0002_evento_entrega.sql — fact_evento y fact_entrega (docs/06 §4.7-4.8), ADITIVA.
-- NO se toca ni se borra `fact_evento_tracking` (0001): `dashboard.api.manejar_evento` (B10) escribe ahí
-- directo con su propio SQL y sus propias pruebas (tests/dashboard/test_servidor_api_servicio.py); esta
-- migración solo agrega las tablas que exige el contrato normativo de `datos.ingesta` sin romper eso.
-- Dialecto portable: TEXT, enteros, INTEGER 0/1 para booleanos, sin FLOAT (convenciones §3, §4).

-- Eventos de tracking de primera parte (PageView, ViewContent, InitiateCheckout, Purchase) recibidos
-- por POST /ingesta/evento (docs/06 §4.7). `consentimiento` es 0/1; `valor_minor`+`moneda` van juntos
-- (o los dos NULL o los dos presentes: lo exige datos.ingesta._validar_evento, no esta tabla).
CREATE TABLE IF NOT EXISTS fact_evento (
    event_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    tipo TEXT NOT NULL,
    ts TEXT NOT NULL,
    visitor_id TEXT NOT NULL,
    cid TEXT,
    asid TEXT,
    adid TEXT,
    fuente TEXT NOT NULL,
    consentimiento INTEGER NOT NULL,
    valor_minor INTEGER,
    moneda TEXT,
    recibido_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fact_evento_oferta_ts ON fact_evento (oferta_id, ts);
CREATE INDEX IF NOT EXISTS ix_fact_evento_visitor ON fact_evento (visitor_id);

-- Última transición de entrega conocida por checkout_session_id (POST /ingesta/entrega, docs/06 §4.7
-- y §4.8). El historial completo de transiciones vive en entregas.jsonl (datos.ingesta.aplicar_entrega
-- es su único productor); esta tabla es la vista "último estado" para consultas rápidas.
CREATE TABLE IF NOT EXISTS fact_entrega (
    session_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    estado TEXT NOT NULL,
    intentos INTEGER NOT NULL,
    producto_sha256 TEXT NOT NULL,
    ts TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fact_entrega_oferta ON fact_entrega (oferta_id);
