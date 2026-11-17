-- 0003_vistas_d8.sql — vistas de solo lectura para engine.d8 y decision.entradas (docs/06 §4.8, D-21).
-- ADITIVA: no borra ni modifica columnas existentes de 0001/0002. Agrega:
--  (a) dos columnas nuevas a `fact_pedido` (impuesto_minor, fee_minor, DEFAULT 0): Stripe no desglosa
--      impuesto/comisión en el webhook de checkout.session.completed que consume hoy
--      `datos.etl_stripe` (solo balance_transaction las trae, fuera de alcance esta noche); quedan en
--      0 hasta que B3/B7 las calculen — ver README «Pedidos». `datos.etl_stripe` (no tocado) sigue
--      haciendo upsert sin nombrarlas: SQLite/Postgres les aplica el DEFAULT en el INSERT y las deja
--      intactas en el UPDATE (datos.db.Conexion.upsert solo actualiza las columnas que le pasan).
--  (b) la tabla `dim_anuncio` (catálogo ad_id -> oferta_id, clave natural `ad_id`, global en Meta):
--      la puebla `datos.etl_meta.aplicar_fila` de forma idempotente (upsert por ad_id, nunca pisa un
--      `concepto_id` ya puesto). Sin esto, `decision.entradas._ids_de_celda` (que la exige NO VACÍA
--      incluso para la celda `oferta_mercado`) no podía resolver ningún anuncio desde ningún ETL
--      real.
--  (c) 5 vistas `v_d8_*`: `engine.d8` y `decision.entradas` leen SOLO estas vistas (nunca las tablas
--      reales por su nombre, salvo `fact_disputa`: no tiene vista propia todavía porque su columna
--      `estado` guarda el `status` crudo de Stripe —needs_response, warning_needs_response,
--      under_review, won, lost...— y no hay, todavía, una decisión de qué subconjunto cuenta como
--      "abierta"; ver README «Pedidos»). Las vistas traducen nombres y valores del esquema real al
--      vocabulario que `engine.d8`/`decision.entradas` ya usaban (docs/06 §4.8): `v_d8_pedido.estado`
--      convierte el `"paid"` de Stripe a `"pagado"` (y deja cualquier otro valor igual, por si algún
--      llamador insertó `"pagado"` directo, p. ej. en pruebas).

ALTER TABLE fact_pedido ADD COLUMN impuesto_minor INTEGER NOT NULL DEFAULT 0;
ALTER TABLE fact_pedido ADD COLUMN fee_minor INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS dim_anuncio (
    ad_id TEXT PRIMARY KEY,
    oferta_id TEXT NOT NULL,
    concepto_id TEXT
);
CREATE INDEX IF NOT EXISTS ix_dim_anuncio_oferta ON dim_anuncio (oferta_id);

CREATE VIEW IF NOT EXISTS v_d8_anuncio AS
    SELECT ad_id, oferta_id, concepto_id FROM dim_anuncio;

CREATE VIEW IF NOT EXISTS v_d8_gasto_dia AS
    SELECT ad_id, fecha, gasto_minor, clics_enlace, ingerido_en AS pull_ts FROM fact_meta_ad_dia;

-- Sin ventana de atribución propia en el esquema real (Meta ya reporta `actions` consolidado,
-- docs/06 §4.4): toda conversión se presenta en la única ventana que decision.entradas/engine.d8
-- consultan hoy (`1d_click`).
CREATE VIEW IF NOT EXISTS v_d8_conv_meta AS
    SELECT ad_id, fecha, '1d_click' AS ventana, compras_meta FROM fact_meta_ad_dia;

-- `interno`/`verificacion`: nombres de docs/06 §4.8; el esquema real los llama `es_interna`/`es_prueba`
-- (misma idea, D-21). `estado`: Stripe manda "paid" en `payment_status` y `datos.etl_stripe` lo copia
-- tal cual; aquí se traduce a "pagado" para no tocar el vocabulario de engine.d8/decision.entradas.
CREATE VIEW IF NOT EXISTS v_d8_pedido AS
    SELECT
        checkout_session_id AS session_id,
        oferta_id,
        adid,
        creado_ts AS pagado_en,
        CASE WHEN estado = 'paid' THEN 'pagado' ELSE estado END AS estado,
        es_interna AS interno,
        es_prueba AS verificacion,
        moneda,
        monto_minor AS bruto_minor,
        impuesto_minor,
        fee_minor
    FROM fact_pedido;

-- Sin workflow de "reservado" en el esquema real (eso vive en el reservorio propio de
-- postcompra.reembolsar, no en datos): toda fila de fact_reembolso es, por construcción, un reembolso
-- ya aplicado por datos.etl_stripe tras charge.refunded.
CREATE VIEW IF NOT EXISTS v_d8_reembolso AS
    SELECT checkout_session_id AS session_id, monto_minor, 'ejecutado' AS estado FROM fact_reembolso;
