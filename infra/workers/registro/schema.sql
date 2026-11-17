-- Base D1 del worker «fabrica-registro»: qué ofertas de referencia ya tomó cada instalación de la fábrica.
-- Solo huellas (sha256 calculado en la Mac de cada instalación): el servidor nunca ve dominios, páginas ni nombres.
CREATE TABLE IF NOT EXISTS instalaciones (token_hash TEXT PRIMARY KEY, id TEXT NOT NULL UNIQUE, alta TEXT NOT NULL, activa INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS reservas (
  huella TEXT PRIMARY KEY, instalacion TEXT NOT NULL, estado TEXT NOT NULL, creada TEXT NOT NULL, actualizada TEXT NOT NULL, vence TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reservas_instalacion ON reservas (instalacion);
