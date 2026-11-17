# infra/workers
Cloudflare Workers de infraestructura (JavaScript, módulos ES, sin dependencias): kill switch
(`watchdog`), descarga firmada (`descarga`). `fulfill/` es de **B7** (entrega post-compra).
Propietario: **B8** (ola 1), continuado por **B8b** (segunda sesión, 2026-11-06).
Un worker por carpeta: infra/workers/<nombre>/ con src/, test/ y wrangler.toml.
Despliegue solo vía script con --live y comprobaciones previas.
Probar: node --test infra/workers/<nombre>/test/*.test.mjs

## Workers

- `watchdog/` (B8) — *dead-man switch*: `POST /latido`, `GET /estado`, `POST /pausa`. **Sin ruta de
  activación**: cualquier otra ruta responde 404/405; el cron (`*/5 * * * *`) solo hace `GET
  campaigns` y `POST status=PAUSED`.
- `descarga/` (B8b) — `GET /d/<sessionId>?token=…`: verifica el enlace firmado por
  `infra/workers/fulfill/src/enlace.mjs` (MISMO formato, duplicado a propósito: cada Worker se
  despliega por separado), cuenta descargas en KV (`CONTADORES`) y entrega desde R2
  (`BUCKET_PRODUCTOS`). El vencimiento y la cuota viajan DENTRO del token (nunca literales aquí: los
  fijó `fulfill` a partir de variables paramétricas).

## Decisiones (B8b)

- `descarga` solo VERIFICA el token; nunca firma uno nuevo (esa responsabilidad es de `fulfill`). Se
  comprobó la compatibilidad de formato con una prueba que firma con `fulfill/src/enlace.mjs` y
  verifica con `descarga/src/enlace.mjs` (`test/enlace.test.mjs`): si algún día el formato de uno
  cambia sin el otro, esa prueba lo detecta.
- El contador de KV incrementa DESPUÉS de validar el token y encontrar el objeto en el bucket (una
  descarga que falla antes de servir el archivo no consume cuota), pero ANTES de devolver la
  respuesta — no hay forma de saber si el cliente recibió el cuerpo completo. Riesgo documentado en
  `infra/README.md` «Pedidos»: KV no es atómico ante descargas concurrentes de la misma sesión.

- `vivo/` (2026-11-14, pedido del dueño: «el dashboard no es en tiempo real… algo robusto y lo más automático posible») — capa en la
  nube del panel en `https://vivo.tu-dominio.com`, base D1 `fabrica-vivo`:
  - `POST /webhooks/impultienda`: avisos de venta firmados (HMAC «timestamp.cuerpo», 5 min de tolerancia, idempotente por `payload.id`, sin datos del comprador);
  - cron `*/5`: lee Meta (insights por campaña y día, hoy y ayer, y estado de las campañas); solo lee;
  - `GET /api/estado`: con `Authorization: Bearer <LECTURA_TOKEN>`; `GET /salud`: sin datos.
  En la Mac, `com.fabrica.nube-sync` (cada 5 min, sin Claude) corre `escalar-oferta/scripts/nube_sync.py`, que lo trae al libro y a `meta_vivo.json`.
  `com.fabrica.tunel` publica el panel (127.0.0.1:8790) por el túnel «fabrica-panel»; el DNS `panel.tu-dominio.com` se conecta
  recién después de la regla de Cloudflare Access (`montar.sh --publicar-panel`).
  Montaje idempotente: `vivo/montar.sh`. Pruebas: `node --test infra/workers/vivo/test/*.test.mjs` (incluye SQLite real).
