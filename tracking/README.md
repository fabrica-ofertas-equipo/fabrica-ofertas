# tracking

Captura y atribución de eventos del embudo: Workers de ingesta con firma HMAC, eventos al servidor (CAPI) y IDs de atribución.
Propietario: B2 (ola 1), según `docs/06-bases-del-testeo.md` §4.3. Datos (`datos`, B3) consume la salida vía la API interna.
Un dataset/píxel por oferta; sin datos de salud ni personales en eventos (convenciones §10).

## Módulos

- `_lib/` — librería compartida sin dependencias, consumida por los 4 Workers (no se despliega sola): `hash.mjs` (SHA-256), `hmac.mjs` (firma/verificación HMAC-SHA256 en tiempo constante + cabeceras internas `X-Fabrica-Ts`/`X-Fabrica-Firma`), `ed25519.mjs` (verificación Ed25519 cruda con `crypto.subtle`), `json_canonico.mjs`, `formatos.mjs` (patrones de `comunes.schema.json`), `almacen_memoria.mjs` (doble de `DurableObjectStorage` para pruebas) y `cerrojo.mjs` (mutex async que modela la serialización de una Durable Object).
- `crear-sesion/` — `POST <dominio_oferta>/api/sesion`: Turnstile, formato, catálogo firmado (precio solo de servidor), `adid`/`asid`/`cid` solo del catálogo (si no, `"desconocido"`), cuota diaria por visitante (Durable Object `CuotaVisitante`), metadata completa, `Idempotency-Key` determinista, Checkout Session de Stripe. Acepta tambien `application/x-www-form-urlencoded` (landing sin JavaScript, `docs/_historial/decision-arranque-de-pago.md`): campos cerrados, mismo origen, cookies `fab_vid`/`fab_attr`/`_fbp`/`_fbc`, renuncia de desistimiento UE/UK con evidencia en `metadata`, y `303` a Stripe en vez de `200` JSON (ver `crear-sesion/README.md`).
- `webhook-stripe/` — `POST hooks.<dominio_infra>/stripe`: verifica `Stripe-Signature` (tolerancia paramétrica, nunca 0), dedupe por `event.id` y por `(tipo, objeto_id)` en la Durable Object `DedupeSesion` (por `session_id`, con cerrojo para entregas concurrentes), dispara `capi.enviarPurchaseSiCorresponde` cuando corresponde.
- `capi/` — módulo interno (sin ruta pública): construye y envía `Purchase`/`InitiateCheckout` a la API de Conversiones de Meta; `em`/`ph` con SHA-256, `fbp`/`fbc` sin hash, `event_id` determinista, ventana de 6 días, solo con `consent_marketing == "1"`.
- `eventos/` — `POST <dominio>/api/ev`: valida `PageView`/`ViewContent` y reenvía firmado (HMAC) a `POST api/ingesta/evento`.

## Probar

```bash
cd tracking/workers/_lib && node --test
cd tracking/workers/capi && node --test
cd tracking/workers/webhook-stripe && node --test
cd tracking/workers/crear-sesion && node --test
cd tracking/workers/eventos && node --test
```

Sin red: todo cliente HTTP (Stripe, Turnstile, Graph, `api/ingesta/evento`) se inyecta como `transporte = { solicitar(metodo, url, {cabeceras, cuerpo}) }`; las Durable Objects se prueban mediante su lógica pura (`dedupe.mjs`, `limitador.mjs`) sobre `almacen_memoria.mjs` + `cerrojo.mjs`, nunca con una Durable Object real (no instanciable en `node --test`). Reloj siempre inyectado (`ahora: () => Date`).

## Variables de entorno

Fuente única: `infra/plantillas/variables-entorno.yaml` (B8). Resumen de lo que cada Worker necesita (secretos nunca en `wrangler.toml`):

| Worker | Config | Secretos |
|---|---|---|
| `crear-sesion` | `STRIPE_API_VERSION`, `ORIGENES_PERMITIDOS`, `MAX_SESIONES_POR_VISITANTE`*, `CUERPO_MAX_BYTES`* | `STRIPE_RK_CHECKOUT`, `CATALOGO_HMAC`, `TURNSTILE_SECRET`* |
| `webhook-stripe` | `STRIPE_TOLERANCIA_SEG` (> 0, nunca "0") | `STRIPE_WHSEC_LIVE`, `STRIPE_WHSEC_TEST` |
| `capi` | `META_API_VERSION` | `META_CAPI_TOKEN__<oferta_id>` |
| `eventos` | `INGESTA_EVENTO_URL`* | `INGEST_HMAC_SECRET`* |

`*` = no figura todavía en `infra/plantillas/variables-entorno.yaml` (ver «Pedidos»).

## Decisiones (dato faltante o conflicto de documentos; fail-closed y genérico, 2026-11-06)

1. **No existe `contratos/catalogo.schema.json`**: se asumió una forma mínima para el catálogo firmado que consume `crear-sesion` (`{ofertas: {<oferta_id>: {price_id, price_id_bump, moneda, success_url, return_url, ids_meta}}}`, documentada en `crear-sesion/src/catalogo.mjs`). Sin ese esquema, cualquier otra forma real que produzca `landing.catalogo` (B4) rompería la integración; es el mayor riesgo de este alcance.
2. **Dedupe y cuota se prueban con lógica pura + `almacen_memoria`/`cerrojo`, nunca con una Durable Object real**: `node --test` no puede instanciar el runtime de Cloudflare. `index.mjs` de cada Worker delega el `get`/`put` atómico a la Durable Object real (no probada aquí); la serialización por instancia se modela con `crearCerrojo()` dentro de la propia Durable Object (`blockConcurrencyWhile` equivalente).
3. **`_lib`'s `verificarEd25519Cruda`** verifica una firma Ed25519 **cruda** (clave pública raw + firma raw, base64 estándar), no el blob SSHSIG (`ed25519:U1NIU0lH...`) de `comunes.schema.json` que usan las aprobaciones humanas y el sello de X1 (eso lo verifica `engine.guard` en Python, con la clave pública del dueño). Ningún Worker de este alcance necesita verificar ese blob en runtime; la función queda disponible para un uso futuro.
4. **El valor (`value`/`currency`) del evento `Purchase` de CAPI no se envía** en este alcance: el exponente ISO 4217 (convenciones §3) vive en `scripts/validar_esquemas.py` (CT) y no se reimplementó en JavaScript para no duplicar la fuente única. El evento se envía igual (con `event_id`, `user_data`, `event_source_url`), sin `custom_data`. Ver «Pedidos».
5. **`eventos` no estaba en `infra/plantillas/variables-entorno.yaml`**: se usan los nombres `INGEST_HMAC_SECRET` (ya citado en `docs/06` §4.3) e `INGESTA_EVENTO_URL` (nuevo, análogo a los demás `*_URL`).
6. **Turnstile y la cuota diaria no tienen variables ya nombradas** en la plantilla de B8: se usan `TURNSTILE_SECRET`, `MAX_SESIONES_POR_VISITANTE` y `CUERPO_MAX_BYTES`, siguiendo la convención `PROVEEDOR_RECURSO`.
7. **La limitación de tasa por IP/zona (WAF) y las reglas de IP de Stripe para `webhook-stripe`** (docs/06 §4.3: "WAF con IPs de Stripe") son configuración de infraestructura (panel de Cloudflare / Terraform), no código de este Worker: `webhook-stripe` valida la firma de Stripe igual sin depender de esa capa, pero no la reemplaza.
8. **`limits.cpu_ms = 50`** en los 4 `wrangler.toml` es un valor conservador sin verificar contra el límite real del plan Paid (`[VERIFICAR]`, igual que lo deja `docs/06` §4.3).
9. **Modo formulario de `crear-sesion`** (ola 2, B2b): sin `contratos/checkout.schema.json` con `compra.renuncia_requerida`, la obligatoriedad de la renuncia de desistimiento se lee de un campo opcional `renuncia.requerido`/`texto_version` en el catalogo firmado (documentado en `catalogo.mjs`) y, si falta, de `env.LOCALES_RENUNCIA_REQUERIDA` (locales UE/UK en la configuracion del Worker, nunca un literal en el codigo). El mismo origen se valida contra `env.ORIGENES_PERMITIDOS`, nunca contra el `Host` de la peticion. Ver `crear-sesion/README.md` para el resto de las decisiones de este modo.

## Pedidos (a otros componentes)

- **CT / B4**: fijar `contratos/catalogo.schema.json` (o documentar en `docs/contratos.md` el formato exacto que produce `landing.catalogo`) para reemplazar la forma asumida en `crear-sesion/src/catalogo.mjs`.
- **B8**: agregar a `infra/plantillas/variables-entorno.yaml` el Worker `eventos` (`INGEST_HMAC_SECRET`, `INGESTA_EVENTO_URL`) y las variables que faltan en `crear-sesion` (`TURNSTILE_SECRET`, `MAX_SESIONES_POR_VISITANTE`, `CUERPO_MAX_BYTES`), idealmente derivadas de `parametros.landing.max_sesiones_por_visitante` / `parametros.ingesta.cuerpo_max_bytes`.
- **CT / B5**: exponer de alguna forma consumible desde JavaScript (tabla o endpoint) el exponente ISO 4217 por moneda, para que `capi` pueda enviar `custom_data.value`/`currency` en el evento `Purchase` sin duplicar `scripts/validar_esquemas.py`.
- **B7 (`fulfill`)**: `webhook-stripe` no escribe en ningún almacén de entrega (fuera de este alcance); solo responde `"encolado"`. Confirmar el contrato exacto de traspaso cuando `fulfill` esté construido.
- **I1**: verificar el límite real de `cpu_ms` del plan Paid contra lo declarado en los 4 `wrangler.toml` (hoy `[VERIFICAR]`).
- **B8**: agregar `ORIGENES_PERMITIDOS` (ya citada en `crear-sesion/wrangler.toml` pero sin uso hasta la ola 2) y `LOCALES_RENUNCIA_REQUERIDA` a `infra/plantillas/variables-entorno.yaml`.
- **CT/B4**: fijar `compra.renuncia_requerida` (o equivalente) en `checkout.schema.json`/el catalogo que produce `landing.catalogo`, y la forma exacta de la cookie `fab_attr` que escribe `consentimiento.js` (se asumio JSON con `encodeURIComponent`, ver `crear-sesion/README.md`).

## Probar (CLI de ejemplo)

No hay CLI de Python aquí (son Workers de JavaScript). El equivalente es `node --test` por carpeta, como arriba. No requieren variables de entorno para las pruebas (todo inyectado); en despliegue real, ver la tabla de variables.
