-- Tienda propia de la fábrica (adaptador «propia»): una base D1 para todas las tiendas de la instalación.
CREATE TABLE IF NOT EXISTS tiendas (
  slug TEXT PRIMARY KEY,            -- dirección: https://<dominio>/<slug>/
  nombre TEXT NOT NULL,
  html TEXT NOT NULL DEFAULT '',    -- landing completa; {{price}} y {{original_price}} se reemplazan
  precio REAL NOT NULL,             -- en la moneda de la tienda
  precio_original REAL,
  moneda TEXT NOT NULL DEFAULT 'USD',
  idioma TEXT NOT NULL DEFAULT 'es',
  entregable_url TEXT,              -- PDF que recibe el comprador
  bump TEXT,                        -- JSON {"nombre","precio","entregable_url"} o NULL
  pixel TEXT,                       -- id del píxel de Meta
  correo_soporte TEXT,
  archivada INTEGER NOT NULL DEFAULT 0,
  creada TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eventos (  -- visitas a la landing e inicios de pago (para el embudo)
  tienda TEXT NOT NULL, tipo TEXT NOT NULL, fecha TEXT NOT NULL, cuando TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS eventos_dia ON eventos (tienda, fecha, tipo);
CREATE TABLE IF NOT EXISTS ventas (
  orden TEXT PRIMARY KEY, tienda TEXT NOT NULL, total REAL NOT NULL, moneda TEXT NOT NULL,
  post_compra INTEGER NOT NULL DEFAULT 0, con_bump INTEGER NOT NULL DEFAULT 0,
  estado TEXT NOT NULL DEFAULT 'aprobada', fecha TEXT NOT NULL, entregada INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ventas_tienda ON ventas (tienda, fecha);
CREATE TABLE IF NOT EXISTS carritos (  -- pagos que no terminaron (Stripe checkout.session.expired)
  sesion TEXT PRIMARY KEY, tienda TEXT NOT NULL, email TEXT, recuperar_url TEXT, fecha TEXT NOT NULL,
  avisado INTEGER NOT NULL DEFAULT 0
);
