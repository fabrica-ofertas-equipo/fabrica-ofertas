# postcompra

Entrega del producto, correo transaccional, reembolsos (automático y manual), evidencia de disputas y
métricas de salud operativa, tras la compra (docs/06 §4.6, §4.8; docs/contratos.md).

- **Propietario:** B7 (ola 1). **Alcance de esta entrega:** `postcompra/**` y el Worker
  `infra/workers/fulfill/`. Correo: SOLO simulado (outbox local); el proveedor real (`ResendCorreo`)
  existe pero nadie lo invoca todavía con credenciales reales (fuera de alcance de la noche).
- **Estado:** construido y probado en modo prueba/fixture; `--live` deliberadamente deshabilitado en
  las CLI (ver «Decisiones» #6: no hay un `Transporte` HTTP real en el repositorio todavía).

## Módulos

| Módulo | Qué hace |
|---|---|
| `_comun.py` | Rutas de `ofertas/<id>/10-postcompra/`, validación de `oferta_id`/`checkout_session_id`, `MOTIVOS_REEMBOLSO`, hash corto determinista para IDs. |
| `almacen.py` | `AlmacenReembolsos`: reserva atómica por `session_id` + tope diario (SQLite, `BEGIN IMMEDIATE`; una conexión nueva por operación, nunca compartida entre hilos). |
| `cliente_stripe.py` | `ClienteStripe`: lee el cargo de una Checkout Session (vía `payment_intent`→`charge`), lista y crea reembolsos. Todo por `engine.transporte.Transporte` inyectado. |
| `correo.py` | `ProveedorCorreo` (protocolo), `SimuladoCorreo` (outbox local, sin email en texto plano) y `ResendCorreo` (real, vía `Transporte`); `texto_confirmacion_reembolso` (con renuncia al desistimiento). |
| `reembolsar.py` | Reembolso automático dentro de regla (algoritmo de docs/06 §4.8). CLI `python -m postcompra.reembolsar`. |
| `reembolso_manual.py` | Reembolso fuera de regla, decidido por el dueño (H). CLI `python -m postcompra.reembolso_manual`. |
| `evidencia.py` | Paquete de evidencia de disputa (resumen + manifiesto de hashes), sin datos personales. CLI `python -m postcompra.evidencia`. |
| `metricas.py` | Calcula y escribe `senal_pausa.json` (D10 → D8, R08). CLI `python -m postcompra.metricas`. |
| `publicar_producto.py` | Empaqueta el `producto.json` aprobado (D4) en un `.zip` determinista + `paquete.json` con el `producto_sha256` que usa la entrega. CLI `python -m postcompra.publicar_producto`. |

Worker `infra/workers/fulfill/` (JavaScript, módulos ES, sin dependencias): encolado por
`webhook-stripe` (pendiente de conectar, ver «Pedidos»); genera el enlace de descarga firmado
(`src/enlace.mjs`, HMAC-SHA256 con Web Crypto), "envía" el correo transaccional y hace
`POST /ingesta/entrega`. Dedupe por `session_id` (KV en producción, `Map` en pruebas).

## CLI (ejemplos que funcionan con fixtures)

Todas las CLI son **dry-run por defecto** (calculan y muestran el plan, no tocan nada); `--fixture`
simula el camino con efecto (B0, `TransporteFixture`, exige `FABRICA_ENTORNO` ∈ {prueba, desarrollo});
`--live` existe en la firma pero hoy siempre sale con código 2 (ver «Decisiones» #6).

```bash
# Reembolso automático (dry-run: solo muestra el plan, no requiere nada más que límites/parámetros)
FABRICA_ENTORNO=desarrollo python -m postcompra.reembolsar \
  --session cs_test_0001 --motivo dentro_de_garantia --oferta OF-202611-01 \
  --raiz tests/fixtures/engine/empresa_prueba --fixture-reglas tests/fixtures/postcompra/reglas_stripe_ok.json --json

# Evidencia de disputa (solo lectura de Stripe; no requiere límites)
FABRICA_ENTORNO=desarrollo python -m postcompra.evidencia \
  --session cs_test_0001 --oferta OF-202611-01 --salida /tmp/evidencia-cs_test_0001 \
  --fixture-reglas tests/fixtures/postcompra/reglas_stripe_ok.json --raiz /tmp/raiz-vacia

# Señal de pausa (conteos explícitos; ver «Pedidos» sobre leerlos de datos)
FABRICA_ENTORNO=desarrollo python -m postcompra.metricas \
  --oferta OF-202611-01 --pagos-ventana 60 --casos-disputa 2 --reembolsos 1 --reembolsos-pedidos 25 \
  --raiz tests/fixtures/engine/empresa_prueba --json

# Publicar el producto aprobado de una oferta (sin red, solo lee producto.json y escribe el paquete)
python -m postcompra.publicar_producto --oferta OF-202611-01 --raiz /tmp/mi-raiz
```

Las pruebas (`tests/postcompra/`) llaman a las funciones de cada módulo directamente (no por
subproceso) para los casos interesantes; los ejemplos de arriba muestran que la CLI también funciona.

## Códigos de salida

0 correcto · 1 interno · 2 uso (argumento, credencial ausente, `--live` sin transporte real) ·
3 validación (esquema, motivo/oferta/sesión inválidos, producto no aprobado o alterado) ·
4 bloqueado (`PAUSA`, entorno, infraestructura) · 5 límite (tope diario, tope por pedido, fuera de
garantía, disputa abierta, parámetro o límite faltante) · 6 externo (Stripe/Resend sin respuesta).

## Entradas y salidas

| Archivo | Quién lo escribe | Contrato |
|---|---|---|
| `ofertas/<id>/10-postcompra/reembolsos.jsonl` | `reembolsar.py`, `reembolso_manual.py` | `reembolso.schema.json` |
| `ofertas/<id>/10-postcompra/reembolsos.db` | `almacen.py` (interno, no es un artefacto de `contratos/`) | propio, solo idempotencia |
| `ofertas/<id>/10-postcompra/senal_pausa.json` | `metricas.py` | `senal_pausa.schema.json` 1.1.0 |
| `ofertas/<id>/10-postcompra/outbox/*.json` | `correo.SimuladoCorreo` | propio (sin email en texto plano) |
| `ofertas/<id>/10-postcompra/paquete/paquete-<v>.json`, `producto-<v>.zip` | `publicar_producto.py` | propio (no hay esquema de `contratos/` para esto; ver «Pedidos») |
| `ofertas/<id>/10-postcompra/entregas.jsonl` | **NO lo escribe este componente**: lo escribe la API `/ingesta/entrega` (motor/`datos`) a partir de lo que postea el Worker `fulfill` | `entrega.schema.json` |
| `ofertas/<id>/04-producto/producto.json` | **NO lo escribe este componente** (D4/maker); `publicar_producto.py` solo lo LEE | `producto.schema.json` |

## Variables de entorno

Python: `STRIPE_RK_REEMBOLSO` (clave restringida solo-reembolsos), `CORREO_API_KEY` (si se usa
`ResendCorreo`; no usado hoy). Worker `fulfill`: `DESCARGA_HMAC` (firma el enlace), `INGEST_HMAC_SECRET`
(autenticación con `webhook-stripe`), `CORREO_API_KEY`, `CORREO_REMITENTE`, `API_BASE_URL`,
`DESCARGA_BASE_URL`, `ENTREGA_ENLACE_VENCE_DIAS`, `ENTREGA_ENLACE_MAX_DESCARGAS` (ver «Pedidos»: estas
dos no tienen todavía una clave en `parametros.yaml`).

## Cómo probar

```bash
.venv/bin/python -m unittest discover -s tests/postcompra -t .
node --test infra/workers/fulfill/test/*.test.mjs   # desde la raíz del repositorio
```

Todas las pruebas Python bloquean `socket.socket` (`tests.engine.apoyo.PruebaBase`, reutilizada aquí),
usan reloj inyectado y una raíz temporal (`tests.engine.apoyo.crear_empresa`, para que
`engine.guard.comprobar_live` pase los 7 pasos en modo `fixture`). El Worker no abre red: todo
proveedor/transporte se inyecta como objeto en memoria (`Map` para el dedupe).

## Decisiones (conflictos de documentos o datos faltantes resueltos por lo más seguro)

1. **`entregas.jsonl` no lo escribe `postcompra`.** La interfaz de docs/06 §4.7 dice que
   `POST /ingesta/entrega` (motor) hace el upsert en `fact_entrega` → `entregas.jsonl`; el Worker
   `fulfill` solo POSTea. Escribirlo yo también habría duplicado la propiedad del artefacto
   (convenciones §1: "un artefacto = un productor"). `postcompra.evidencia` lo LEE si existe.
2. **`postcompra.reembolsos.db` es un almacén propio, no el del motor (D-21).** Solo guarda la carrera
   de idempotencia de ESTA operación (reservado/ejecutado/rechazado por `session_id`); la fuente de
   verdad legible para humanos sigue siendo `reembolsos.jsonl`.
3. **El guard recibe `monto_minor = min(monto_pendiente, reembolso_auto_max)`, nunca más.** El paso
   «topes» de `engine.guard.comprobar_live` compara un solo importe contra `reembolso_auto_max`; la
   regla de negocio real (acumulado del pedido contra `min(charge.amount, reembolso_auto_max)`) es más
   precisa y vive en `reembolsar.py`. Sin este tope, un pedido grande habría hecho que el guard
   bloqueara con su mensaje genérico en vez del `"excede_tope"` propio (con `detalle.motivo`).
4. **`reembolso_manual` respeta `PAUSA` con `engine.guard.hay_pausa`, no con `comprobar_live`
   completo.** El reembolso manual no está sujeto a `reembolso_auto_max`/`reembolsos_auto_max_por_dia`
   (son topes de lo automático) ni a `accion_gate` (la aprobación YA es el humano que lo invoca), pero
   docs/06 línea 466 es explícito en que "tampoco" corre con `PAUSA`.
5. **`metricas.py` no pasa por el guard.** No gasta, no activa, no es Meta/Stripe: es una escritura
   local de un artefacto de solo análisis. Tratarlo como "efecto externo" habría exigido credenciales
   y gates que no aplican a esta operación.
6. **Ningún CLI con efecto puede ejecutar `--live` todavía.** `engine.transporte` (B1, Decisión 11) deja
   explícito que "el cliente HTTP real lo aporta quien lo necesite"; ningún componente del repositorio
   lo aporta aún. En vez de fingir que `--live` funciona con un `TransporteFixture` (que fallaría en
   silencio con cualquier llamada real), las CLI con efecto (`reembolsar`, `reembolso_manual`) se
   niegan explícitamente (`ErrorUso`, código 2) con un mensaje que apunta al pedido. Esto es, además,
   coherente con la regla de la noche: nada de red real.
7. **Email nunca en texto plano en ningún archivo propio.** `SimuladoCorreo` solo guarda
   `sha256(email)` en el outbox; `/ingesta/entrega` nunca recibe el email (el Worker `fulfill` solo lo
   usa, en memoria, para llamar al proveedor de correo).
8. **`metricas.calcular_senal`: prioridad "disputas" sobre "reembolsos" en caso de empate de nivel.**
   El esquema solo admite un `motivo`; con los dos en rojo o los dos en amarillo se reporta "disputas"
   (es el motivo con conteo de respaldo bajo muestra insuficiente, más sensible a falsos negativos).
9. **`reembolso.regla_aplicada`** usa tres códigos propios (no normados en ningún esquema):
   `AUTO-GARANTIA` (automático dentro de regla), `AUTO-RECHAZO` (automático rechazado, queda registrado
   igual, con `estado: "rechazado"`) y `MANUAL-HUMANO`.

## Pedidos (cambios que necesito de otros componentes; no los edité)

- **Dueño / `empresa/parametros.yaml` (grupo `postcompra`):** faltan `enlace_vence_dias` y
  `enlace_max_descargas` (docs/06 §4.6 los menciona como `entrega.enlace_vence_dias`/`enlace_max_descargas`,
  pero el grupo real solo tiene `entrega_max_min`/`entrega_alerta_min`/`entrega_reintentos`). Hoy el
  Worker `fulfill` los recibe como variables de entorno (`ENTREGA_ENLACE_VENCE_DIAS`,
  `ENTREGA_ENLACE_MAX_DESCARGAS`) en vez de leerlos de `parametros.yaml`.
- **B3 / `datos`:** `postcompra.metricas` necesita `pagos_ventana`, `casos_disputa_efw`,
  `reembolsos_num`/`reembolsos_den` de verdad (hoy son argumentos explícitos de la CLI, no se leen de
  `fact_pedido`/`fact_disputa`/`fact_reembolso` porque `datos` todavía no existe en esta ola). El
  núcleo (`calcular_senal`) ya es puro y no debería cambiar cuando `datos` esté listo: solo cambia quién
  llama con qué conteos.
- **B2 / `tracking`:** `webhook-stripe` todavía no llama a `fulfill` (su propio código lo dice: "el
  Worker `fulfill` es de B7 y no es parte de este alcance"). Falta decidir el mecanismo (fetch directo
  con `X-Fabrica-Firma`, o una cola) y conectar los dos Workers.
- **B8 / `infra`:** el Worker `descarga` (mencionado en docs/06 §4.6 como quien resuelve la cuota de
  descargas con KV) no existe todavía; `enlace.verificarEnlace` está listo para que lo use cuando
  exista, pero yo no lo invoco desde `fulfill` (solo genero y firmo el enlace).
- **B1 / `engine`:** no hay un `Transporte` HTTP real inyectable en ningún lado del repositorio
  (Decisión 11 de `engine/README.md`); hasta que exista, ninguna CLI de `postcompra` puede ofrecer un
  `--live` que funcione de verdad (ver Decisión 6 arriba).
- **CT / `contratos/`:** no hay esquema para "disputa" (docs/06 §4.8 menciona `fact_disputa` pero solo
  como tabla de `datos`, nunca como artefacto de archivo); `postcompra.evidencia` arma su propio
  `resumen.json`/`manifiesto.json` sin esquema propio. Si se quiere un contrato formal, definirlo en
  `contratos/evidencia.schema.json`. Tampoco hay esquema para `paquete.json` de `publicar_producto.py`.

## Riesgos y límites conocidos

- La "espera" de `AlmacenReembolsos.esperar_resultado` es *busy-polling* acotado (reintentos +
  backoff, tope en el código, no en `parametros.yaml`: es un detalle técnico de concurrencia, no una
  regla de negocio). Con un proceso que muere entre "reservar" y "marcar ejecutado/rechazado", una
  sesión queda en `reservado` para siempre y bloquea reintentos futuros sin resolverla (no hay un
  `UPDATE ... WHERE estado='reservado' AND creado_en < hace mucho` de limpieza).
- `publicar_producto.py` no tiene esquema de `contratos/` para `paquete.json` (ver «Pedidos» a CT).
- El Worker `fulfill` no está conectado a nada todavía (ni a `webhook-stripe` que lo encola, ni al
  Worker `descarga` que validaría el enlace); su `index.mjs` es la mejor interpretación razonable de
  docs/06 §4.6/§4.7, pero no se probó de punta a punta con los otros Workers.

