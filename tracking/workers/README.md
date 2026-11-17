# tracking/workers
Cloudflare Workers de tracking (JavaScript, módulos ES, sin dependencias): ingesta, redirección con IDs, verificación HMAC.
Propietario: 06-landing-checkout. Un worker por carpeta: tracking/workers/<nombre>/ con src/, test/ y wrangler.toml.
Secreto de firma: INGEST_HMAC_SECRET (solo entorno).
Probar: node --test tracking/workers/<nombre>/test/*.test.mjs
