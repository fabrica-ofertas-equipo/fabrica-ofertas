# datos (B3)

ETL de Meta y Stripe, ingesta de eventos de tracking, atribución Meta↔Stripe, ledger y KPI de una
oferta (docs/06 §4.4). Propietario: B3. Etapa: ola 1 (construcción inicial, modo prueba).

Dinero en enteros de unidad menor + ISO 4217 (nunca `float`); tiempo UTC ISO-8601 con `Z`; toda carga
es un *upsert* por clave natural (convenciones §3, §4, §7). Base de datos portable: el mismo SQL de
`datos/migraciones/*.sql` corre en SQLite (hoy) y, con el marcador traducido (`datos.db.traducir_marcadores`),
en PostgreSQL el día que haya un controlador.

## Módulos

| Módulo | Qué hace |
|---|---|
| `datos.db` | `conectar(url)`, `migrar(conn)`, `Conexion.upsert(tabla, clave, valores)` |
| `datos.etl_meta` | Insights de Meta por anuncio y día → `raw_meta_insight`, `fact_meta_ad_dia` (upsert) |
| `datos.etl_stripe` | Eventos de Stripe (pedidos, reembolsos, disputas) → `fact_pedido`, `fact_reembolso`, `fact_disputa`, con deduplicación |
| `datos.ingesta` | Controladores puros de `POST /ingesta/evento` → `fact_evento` y `POST /ingesta/entrega` → `fact_entrega` + `entregas.jsonl` |
| `datos.atribucion` | `cobertura_adid`, `razon_meta_stripe`, `evidencia_celda` (agregados crudos), `pedidos_cohorte` |
| `datos.ledger` | Líneas de `empresa/finanzas/ledger.jsonl` (upsert por `clave_natural`, append-only) y conciliación triple |
| `datos.kpi` | Snapshot `kpi_oferta_dia.json` (`ofertas/<id>/08-operacion/diario/<fecha>/`) |

## CLI (con los fixtures del repositorio)

```bash
# Migrar (crea empresa/datos/fabrica.db bajo --raiz; aquí usamos una raíz de prueba)
mkdir -p /tmp/fabrica-prueba
FABRICA_ENTORNO=prueba .venv/bin/python -m datos.etl_meta --oferta OF-202611-01 \
  --desde 2026-11-10 --hasta 2026-11-12 \
  --fixture tests/fixtures/datos/meta_insights_OF-202611-01.json \
  --raiz /tmp/fabrica-prueba --json

FABRICA_ENTORNO=prueba .venv/bin/python -m datos.etl_stripe \
  --fixture tests/fixtures/datos/stripe_eventos_OF-202611-01.json \
  --raiz /tmp/fabrica-prueba --json

FABRICA_ENTORNO=prueba .venv/bin/python -m datos.ledger --oferta OF-202611-01 \
  --periodo 2026-11-10:2026-11-12 --moneda EUR --raiz /tmp/fabrica-prueba --json

FABRICA_ENTORNO=prueba .venv/bin/python -m datos.kpi --oferta OF-202611-01 \
  --fecha 2026-11-11 --raiz /tmp/fabrica-prueba --json
```

Códigos de salida: convenciones §8 (`0` correcto, `2` uso, `3` validación, `6` externo). `--live` existe
en la firma de todos los CLI (docs/06 §4.1) pero **esta sesión no tiene conector de red**: siempre
devuelve `6` (`ErrorExterno`) con un mensaje que explica qué falta (ver «Decisiones»). `--raiz` y
`--ahora` solo existen fuera de `FABRICA_ENTORNO=produccion`.

## Variables de entorno

| Variable | Usa | Origen |
|---|---|---|
| `INGEST_HMAC_SECRET` | `datos.ingesta.manejar_ingesta_evento` (firma servicio-a-servicio) | compartida con `tracking/workers/eventos` (B2) |

Pendiente de agregar a `.env.example` por **B8** (esta sesión no escribe en `infra/**`): nombre sugerido
`INGEST_HMAC_SECRET` (sin oferta, servicio a servicio, alcance mínimo lectura/escritura de la tabla de
eventos de tracking).

## Probar

```bash
.venv/bin/python -m unittest discover -s tests/datos -t .
```

Sin red (`socket.socket` bloqueado en `tests/datos/apoyo.PruebaBase`); una base SQLite temporal por
prueba. `tests/fixtures/datos/` trae un lote de Meta (3 días × 5 anuncios) y uno de Stripe (3
pedidos, 1 de prueba, 1 duplicado, 1 reembolso, 1 disputa) con forma realista pero **sintética** (ver
el README de esa carpeta). `tests/fixtures/datos/reales/` es de **I1** (captura real, B0-24): esta
sesión no escribe ahí.

## Contrato de ingesta (`datos.ingesta`, alineado con `dashboard.api` y los Workers reales)

Autenticación (docs/06 §4.7, idéntica a `dashboard.api.firmar` y a `tracking/workers/_lib/src/hmac.mjs`):
cabeceras `X-Fabrica-Ts` (UTC ISO con `Z`) y `X-Fabrica-Firma: hmac-sha256=<hex>` = HMAC-SHA256 de
`ts + "." + cuerpo_exacto`, comparación en tiempo constante. Orden de comprobaciones: parámetros de
`ingesta.*`/secreto (500) → tamaño del cuerpo ≤ `ingesta.cuerpo_max_bytes` (413) → cabeceras de firma
presentes (401) → `ts` válido y dentro de `ingesta.tolerancia_seg` (400) → firma (401) → JSON y forma
(400) → efecto con idempotencia (200 `nuevo`/`duplicado`; 409 si el mismo identificador trae otro
contenido).

- **`POST /ingesta/evento`** — cuerpo `{event_id, oferta_id, tipo ∈ PageView·ViewContent·InitiateCheckout·Purchase,
  ts, visitor_id, cid?, asid?, adid?, fuente ∈ pixel·capi·landing, consentimiento, valor_minor?, moneda?}`
  (ningún campo extra; `valor_minor` y `moneda` van juntos). Persiste en `fact_evento` (migración
  `0002`) vía `INSERT … ON CONFLICT(event_id) DO NOTHING` equivalente (compara contenido: idéntico →
  `duplicado`, distinto → 409 `event_id_con_otro_contenido`).
- **`POST /ingesta/entrega`** — cuerpo `{checkout_session_id, oferta_id, estado ∈ encolado·enviado·entregado·fallido,
  intento, producto_sha256, ts}` (exactamente esos 6 campos, confirmado contra `fulfill` real, ver
  «Decisiones» #11). Upsert en `fact_entrega` (clave `session_id`) y apéndice idempotente en
  `.../10-postcompra/entregas.jsonl` conforme a `contratos/entrega.schema.json` (único productor de
  ese artefacto). La MISMA transición (`checkout_session_id`, `estado`, `intento`) repetida con el
  mismo contenido → `duplicado`; con otro contenido → 409 `entrega_con_otro_contenido`.

## Migraciones

| Archivo | Tablas | Nota |
|---|---|---|
| `0001_inicial.sql` | `stripe_evento`, `raw_meta_insight`, `fact_meta_ad_dia`, `fact_pedido`, `fact_reembolso`, `fact_disputa`, `fact_evento_tracking` | Base original |
| `0002_evento_entrega.sql` | `fact_evento`, `fact_entrega` | ADITIVA: no toca ni borra `fact_evento_tracking` (lo sigue usando `dashboard.api.manejar_evento`, de B10, con su propio SQL y sus propias pruebas) |

## Decisiones (sin dato mejor; se eligió lo más seguro y genérico)

1. **`--live` no está implementado esta noche**: la sesión no tiene red, credenciales ni un cliente
   real de la Graph API o de Stripe. `etl_meta`/`etl_stripe --live` fallan con `ErrorExterno` (6) en
   vez de fingir una lectura. El contrato que debe cumplir quien lo implemente: `etl_meta` recibe de
   `meta.insights` (B5) un documento con la misma forma que `--fixture` (`cuenta.timezone_name`,
   `cuenta.currency`, `filas[]`); `etl_stripe` recibe de un backfill por cursor una lista de `Event`
   igual a `--fixture` (`eventos[]`).
2. ~~**Protocolo de `datos.ingesta`** (no estaba fijado en ningún documento leído): cabeceras
   `X-Fabrica-Ts` ... y `X-Fabrica-Firma` = `hmac-sha256:<hex>` sobre `cuerpo + X-Fabrica-Ts`.~~
   **SUPERADA esta noche (B3b, ver decisión 10)**: `dashboard.api` (B10) ya fijó el protocolo real
   (`hmac-sha256=<hex>` sobre `ts + "." + cuerpo`) y los Workers reales lo confirman
   (`tracking/workers/_lib/src/hmac.mjs`); `datos.ingesta` se alineó a eso. Sin el grupo
   `parametros.ingesta` configurado, la ingesta sigue fallando cerrado (500).
3. **`kpi_oferta_dia.json` vive en `ofertas/<id>/08-operacion/diario/<fecha>/`**, no en
   `empresa/datos/` como dice literalmente la fila de `datos.kpi` en docs/06 §4.4: se siguió la forma
   real que ya trae `ofertas/_ejemplo/08-operacion/diario/2026-11-11/kpi_oferta_dia.json` (CT), más
   específica que el texto. `empresa/datos/` queda libre para el futuro `kpi_blended_dia.json`
   (ambito `blended`, no implementado esta noche: sin datos de más de una oferta que mezclar).
4. **`stripe_balance` siempre `rojo`** en `datos.kpi`: no hay lectura del balance real de Stripe esta
   noche (sin red). Se prefirió un rojo honesto a inventar un verde.
5. **Ledger append-only con upsert "última línea vigente"**: una clave natural que cambia de valor
   agrega una línea nueva; `datos.ledger.leer_vigente` toma la última por `clave_natural`. Reaplicar el
   mismo periodo sin cambios no agrega nada (idempotente, criterio B0-15).
6. **`pendientes_asincronos` siempre `0`**: los medios de pago asíncronos (OXXO, vouchers) no están
   modelados esta noche; no hay tabla ni ETL para ellos.
7. **`datos.atribucion.evidencia_celda` entrega agregados CRUDOS**, sin la corrección
   `compras_corregidas` ni `tracking_sano` de docs/06 §4.2: esa corrección es de
   `decision/entradas.py` (**B1**), que debe llamar a esta función en vez de repetir el `SELECT`.
8. **Solo SQLite ejecuta de verdad**: `postgresql://` se reconoce y el SQL se traduce, pero sin
   `psycopg2` (no instalable esta noche) la conexión real falla con `ErrorExterno`. Un componente que
   necesite Postgres en serio declara `psycopg2` en `datos/requirements-extra.txt` y corre
   `scripts/bootstrap.sh`.
9. **Fixtures de `datos` NO viven en `tests/fixtures/datos/reales/`**: esa carpeta es de **I1**
   (tabla de propiedad, docs/06 §4.1: `tests/fixtures/{meta,datos}/reales/`). Las propias quedan en
   `tests/fixtures/datos/` (ver README de esa carpeta).
10. **Se reescribió `datos.ingesta` esta noche (B3b)** para alinearlo EXACTAMENTE con docs/06 §4.7 y
    con `dashboard.api` (que ya lo monta y fija de hecho el contrato): cabecera de firma
    `hmac-sha256=<hex>` (antes `hmac-sha256:<hex>`), HMAC sobre `ts + "." + cuerpo` (antes `cuerpo + ts`),
    cuerpo con `tipo` (antes `nombre`) y el enumerado/campos completos de §4.7, códigos `401` para
    firma ausente/inválida (antes `400` los dos). Esto reemplaza las aserciones viejas de
    `tests/datos/test_ingesta.py` (dicho en el informe); `fact_evento_tracking` (tabla y función
    vieja `aplicar_evento_tracking`) NO se tocan: `dashboard.api.manejar_evento` (B10) sigue
    escribiendo ahí directo con su propio SQL, y sus pruebas (`tests/dashboard/`) no son mías.
11. **El cuerpo real de `POST /ingesta/entrega` trae MENOS datos de los que exige
    `contratos/entrega.schema.json`** (confirmado leyendo el Worker REAL,
    `infra/workers/fulfill/src/manejador.mjs`: solo manda `checkout_session_id, oferta_id, estado,
    intento, producto_sha256, ts`; ni siquiera `productoVersion`, que el propio Worker SÍ conoce, se
    incluye en el POST). Como no puedo tocar `contratos/**`, la línea de `entregas.jsonl` rellena lo
    que falta de forma genérica y documentada: `email_hmac=null` (nunca llega un email por este
    endpoint — confirmado también porque `dashboard.api` rechaza un campo `email` como no permitido),
    `enlace.{vence_en,max_descargas}` calculados con los parámetros `entrega.enlace_vence_dias`/
    `enlace_max_descargas` (nunca un número fijo) y `enlace.descargas=0` (el contador real vive en
    `infra/workers/descarga`, fuera de este módulo), `idempotency_key` derivada (convenciones §7),
    `ejecutor="script"` (vía siempre automática) y `producto_version="v1"` por falta de mejor dato.
    Ver «Pedidos».
12. **`fact_entrega` es la foto del ÚLTIMO estado** (clave `session_id`); el historial completo de
    transiciones (`encolado→enviado→entregado→fallido`, con reintentos) vive en `entregas.jsonl`
    (`datos.ingesta.aplicar_entrega` es su ÚNICO productor, convenciones «un artefacto, un
    productor»). La idempotencia de ese archivo es por `(checkout_session_id, estado, intento)`: la
    misma transición repetida con el mismo contenido no duplica línea; con otro contenido es 409.
13. **Migración `0002` es puramente ADITIVA**: agrega `fact_evento` y `fact_entrega`, sin tocar
    `fact_evento_tracking` (ver decisión 10). Nada de `datos` lee hoy `fact_evento_tracking`
    (confirmado por búsqueda); si en el futuro hace falta, una vista es más segura que borrar la tabla.
14. **`datos.ingesta.manejar_ingesta_entrega` resuelve `raiz` con `engine.comun.raiz()` por defecto**
    (no es un parámetro posicional): la llamada real desde `dashboard.api.manejar_entrega` es
    `manejar_ingesta_entrega(cuerpo, cabeceras, conexion, lambda: ahora)`, sin `raiz` (visto leyendo
    `dashboard/api.py`). `raiz` queda como argumento con nombre para inyectarlo en pruebas.
15. **Prueba de contrato contra los Workers REALES** (`tests/datos/test_contrato_workers.py`,
    `tests/fixtures/datos/arnes_worker_{eventos,fulfill}.mjs`, PEDIDO 3 del encargo): corre
    `tracking/workers/eventos` y `infra/workers/fulfill` de verdad (sin red, `fetch`/`transporte`
    interceptados) y alimenta lo que firman/envían a `manejar_ingesta_*`. Encontró una diferencia
    real (decisión 11 y «Pedidos»): `infra/workers/fulfill/src/index.mjs` manda `POST
    .../ingesta/entrega` SIN `X-Fabrica-Ts`/`X-Fabrica-Firma`; la prueba documenta ese 401 en vez de
    inventar una firma que el Worker no manda, y agrega una segunda prueba que confirma que este lado
    (B3) ya acepta el mismo cuerpo el día que B7 agregue la firma.
16. **`index.mjs` de `fulfill` usa `new Date()` real, no un reloj inyectado** (a diferencia del resto
    del sistema, convenciones §4): el arnés de la decisión 15 tuvo que usar la hora real de pared para
    que la comprobación de tolerancia de `firmaValida` no fallara. Queda anotado como pedido a B7
    (debería aceptar un `ahora` inyectable como todo lo demás) sin tocar su código.
17. **`manejar_ingesta_*` se reautentica siempre con `cargar_parametros()`/`INGEST_HMAC_SECRET` del
    entorno real**, aunque lo llame `dashboard.api` (que ya autenticó con SU `secreto`/`parametros`
    inyectables): la firma de la llamada real (`f(cuerpo, cabeceras, conexion, ahora)`, sin
    `secreto`/`parametros`) no deja otra opción. En producción ambas capas comparten el mismo
    `INGEST_HMAC_SECRET` y el mismo `empresa/parametros.yaml`, así que no hay conflicto; en las
    pruebas de `dashboard` que inyectan un secreto/parametros DISTINTOS del entorno real, delegar a
    esta función hará que la autenticación de esta capa falle con su propio motivo (500/401) en vez
    del 501 viejo — defensa en profundidad intencional, no un error de esta sesión.

## Pedidos

- **B1**: alinear `decision/entradas.py.evidencia_celda` para que llame a
  `datos.atribucion.evidencia_celda` en vez de reimplementar las consultas (evita dos fórmulas).
- **B5**: cuando `meta.insights` exista, que entregue el documento de insights con la forma de
  `tests/fixtures/datos/meta_insights_*.json` (`cuenta.timezone_name`, `cuenta.currency`, `filas[]`),
  para que `datos.etl_meta --fixture` (o una futura llamada directa) lo consuma sin cambios.
- **I1**: cuando capture fixtures reales en `tests/fixtures/{meta,datos}/reales/` (B0-24), puede
  reemplazar `tests/fixtures/datos/meta_insights_OF-202611-01.json` y
  `stripe_eventos_OF-202611-01.json` por esa captura manteniendo la misma forma; esta sesión no
  escribió en `reales/` por ser de otro dueño.
- **B8**: agregar `INGEST_HMAC_SECRET` a `.env.example` cuando se integre el Worker `eventos` de verdad.
- **Dueño/CT**: confirmar si `kpi_blended_dia.json` vive en `empresa/datos/` (como dice la fila de la
  tabla) o junto al resto de KPI por oferta; hoy no hay implementación de `ambito=blended`.
- **B7 (`infra/workers/fulfill`), URGENTE**: `postEntregaApi` en `src/index.mjs` manda `POST
  ${API_BASE_URL}/ingesta/entrega` sin `X-Fabrica-Ts`/`X-Fabrica-Firma` (docs/06 §4.7 los exige);
  hoy `datos.ingesta.manejar_ingesta_entrega` (y `dashboard.api`) lo rechazarían con 401
  `firma_ausente` (demostrado por `tests/datos/test_contrato_workers.py`). Agregar la firma con
  `construirCabecerasInternas` (igual que el Worker `eventos`) usando `env.INGEST_HMAC_SECRET`.
  Además, `manejarEntregaPagada` conoce `productoVersion` pero no la incluye en el cuerpo que manda:
  si se amplía el cuerpo (y CT amplía `_CLAVES_ENTREGA`/docs/06 §4.7 a juego), `datos.ingesta` puede
  usar el valor real en vez del `"v1"` genérico de `entregas.jsonl` (ver README «Decisiones» #11).
  También: `index.mjs` usa `new Date()` real en vez de un reloj inyectable (convenciones §4); sería
  más fácil de probar con un `ahora` inyectado como el resto del sistema.
- **B10 (`dashboard.api`)**: ahora que `fact_evento` existe con `cid`/`asid`/`fuente`/`consentimiento`/
  `valor_minor`/`moneda` (el LÍMITE CONOCIDO que `dashboard.api.manejar_evento` anota como PEDIDO a
  B3), se puede delegar `/ingesta/evento` a `datos.ingesta.manejar_ingesta_evento` igual que ya hace
  `manejar_entrega` con `manejar_ingesta_entrega` (vía `_descubrir`), en vez de escribir directo a
  `fact_evento_tracking`. Al delegar `/ingesta/entrega` por primera vez, el test propio
  `tests/dashboard/test_servidor_api_servicio.py::test_entrega_valida_se_delega_y_sin_adaptador_es_501`
  deja de reflejar la realidad (ya hay adaptador): hay que actualizarlo (no es archivo de B3).
- **CT (`contratos/entrega.schema.json`) o B7**: decidir si el esquema se relaja (campos opcionales
  cuando vienen de esta vía de ingesta) o el cuerpo de `/ingesta/entrega` se amplía (`producto_version`,
  etc.); hoy `datos.ingesta` rellena lo que falta con valores genéricos documentados (decisión 11).
