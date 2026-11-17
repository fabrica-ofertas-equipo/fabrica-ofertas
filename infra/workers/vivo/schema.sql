-- Base D1 del worker «fabrica-vivo». Sin datos personales del comprador.
CREATE TABLE IF NOT EXISTS ventas (
  entrega_id TEXT, evento TEXT NOT NULL, recibido TEXT, orden_id TEXT NOT NULL, orden INTEGER, estado TEXT,
  total REAL, moneda TEXT, total_comprador REAL, moneda_comprador TEXT, pais TEXT, medio TEXT,
  post_compra INTEGER DEFAULT 0, orden_padre TEXT, creada TEXT, tienda TEXT, tienda_nombre TEXT,
  utm_campaign TEXT, utm_id TEXT, utm_adset TEXT, utm_content TEXT, items TEXT, prueba INTEGER DEFAULT 0,
  PRIMARY KEY (orden_id, evento)
);
CREATE TABLE IF NOT EXISTS entregas (id TEXT PRIMARY KEY, recibido TEXT);
CREATE TABLE IF NOT EXISTS meta_dia (
  fecha TEXT NOT NULL, campana TEXT NOT NULL, nombre TEXT, gasto REAL, impresiones INTEGER, clics INTEGER,
  visitas INTEGER, pagos_iniciados INTEGER, compras INTEGER, valor_compras REAL, leido TEXT,
  PRIMARY KEY (fecha, campana)
);
CREATE TABLE IF NOT EXISTS estado (clave TEXT PRIMARY KEY, valor TEXT);
-- Meta por anuncio (15-nov): un JSON por día con la lista de anuncios de ese día (pocas escrituras por vuelta).
CREATE TABLE IF NOT EXISTS anuncio_dia (fecha TEXT PRIMARY KEY, filas TEXT NOT NULL, leido TEXT);
-- Carritos (15-nov): avisos order.abandoned y order.rejected de un endpoint aparte. Solo sirven de pista para la tarea
-- «repesca-carritos» (qué tiendas tienen carritos nuevos): sin email ni datos del comprador.
CREATE TABLE IF NOT EXISTS carritos (
  orden_id TEXT NOT NULL, evento TEXT NOT NULL, entrega_id TEXT, recibido TEXT, creada TEXT, estado TEXT,
  total REAL, moneda TEXT, tienda TEXT, verificado INTEGER DEFAULT 0, prueba INTEGER DEFAULT 0,
  PRIMARY KEY (orden_id, evento)
);
-- Corte de respaldo (17-nov): plan que sube la Mac en estado('plan_corte') y lo que la nube pausó (o habría pausado sin token).
CREATE TABLE IF NOT EXISTS cortes_nube (
  campana TEXT NOT NULL, test TEXT NOT NULL, cuando TEXT NOT NULL, gasto_usd REAL, corte_usd REAL, ventas INTEGER,
  resultado TEXT, porque TEXT,
  PRIMARY KEY (campana, test)
);
