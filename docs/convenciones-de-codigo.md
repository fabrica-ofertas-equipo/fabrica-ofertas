# Convenciones de código

> **Normativo.** Versión 1.0 (2026-11-06). Rige para todo el código del repositorio. Si choca con `docs/_backbone.md` (v2.2), manda el backbone. "DEBE" es obligatorio; "DEBERÍA" admite excepción justificada en el README del componente. Principio rector: **los LLM proponen, el código dispone**; todo lo que mueve dinero, publica o activa es código determinista con límites duros.

## 1. Entorno y estructura

- Raíz = carpeta del repositorio. Paquetes de Python: `engine, decision, datos, meta, compliance, postcompra, landing, dashboard, agentes, infra, contratos, scripts` (cada uno con `__init__.py`). Workers de Cloudflare: JavaScript, módulos ES, **sin dependencias**, en `tracking/workers/<nombre>/` e `infra/workers/<nombre>/` (con `src/`, `test/`, `wrangler.toml`).
- Python 3.15 en `.venv` (`bash scripts/bootstrap.sh`); Node v26. Biblioteca estándar primero; en la raíz solo PyYAML y jsonschema.
- Importaciones absolutas desde la raíz (`from engine.limites import cargar`). Rutas con `pathlib`; la raíz se resuelve desde `FABRICA_RAIZ` o desde la ubicación del archivo, nunca desde el directorio actual.
- Cada componente escribe **solo** en sus carpetas (backbone §4). Rutas protegidas contra escritura de agentes: `.claude/skills/**`, `.claude/agents/**`, `contratos/**`, `empresa/limites.yaml`, `empresa/parametros.yaml`. El código NO DEBE sobrescribir un artefacto versionado aprobado: crea la versión siguiente (`v2`).
- Escritura atómica (temporal en la misma carpeta + `os.replace`); `.jsonl` solo en append.
- Comandos: `bash scripts/bootstrap.sh`, `bash scripts/test_all.sh`, `bash scripts/lint.sh`. Nada se integra si alguno falla.

## 2. Nombres e idioma

- Nombres de archivos, carpetas e identificadores: **ASCII**, minúsculas, `snake_case` en español en Python (`calcular_cpa`, `ErrorLimite` para clases en `PascalCase`). Sin tildes ni `ñ`. Excepciones ya fijadas: `lint_claims.py`, `validar_esquemas.py`, `factibilidad.py`, `score.py`, `preflight.py`.
- Comentarios, docstrings, mensajes de error y documentos: **español con tildes**. Todo módulo, clase y función pública lleva docstring en español (qué hace, entradas, salidas, errores).
- Claves JSON y YAML: ASCII `snake_case`.
- Nombres en Meta: backbone §5.2.

## 3. Dinero

- Importe = **entero en la unidad menor** (centavos) + código **ISO 4217**. Prohibido `float` para dinero (código, JSON, bases de datos). Los decimales salen de la tabla ISO 4217 (USD 2, JPY 0, KWD 3).
- Solo se opera entre importes de la misma moneda; si no, `ErrorValidacion` (también al **comparar** con un tope: moneda primero, importes después).
- **Meta no usa los decimales ISO 4217 sino su propio *offset***: 1 para CLP, COP, CRC, HUF, ISK, IDR, JPY, KRW, PYG, TWD y VND, 100 para el resto (https://developers.facebook.com/docs/marketing-api/currencies, leída 2026-11-06). Toda llamada de presupuesto a Meta pasa por `meta/monedas.py` (`a_unidad_meta`, que falla si el resultado no es entero). `AdAccount.spend_cap` se **lee** en unidad menor y se **escribe** en unidad estándar; los scripts solo leen. Hasta que `meta/monedas.py` esté probado, `moneda_limites` ∉ esa lista (lo valida `evaluar_limites`).
- Todo cálculo con fracciones (porcentajes, comisiones, prorrateos) usa `decimal.Decimal` o aritmética entera y termina con un **redondeo explícito**: la función de redondeo exige el modo como argumento (`ROUND_HALF_EVEN` por defecto para agregados internos; `ROUND_HALF_UP` para importes que ve el cliente), y los prorrateos reparten el resto de centavos de forma determinista.
- **Conversión de monedas solo con tipo de cambio registrado**: par, tasa como cadena decimal, fecha UTC, fuente y `tipo_cambio_id`, guardado en `empresa/finanzas/`. El resultado cita ese `tipo_cambio_id`. Sin tipo de cambio vigente no se convierte (`ErrorLimite` si hace falta para un tope).
- Porcentajes y ratios en JSON: cadena decimal (`"0.20"`) o puntos básicos enteros, no `float`. Ingresos = Stripe, gasto = Meta (backbone §5.3).
- **Todo presupuesto, tope y umbral es paramétrico**: se lee de `empresa/limites.yaml` o `empresa/parametros.yaml`. Prohibido un número de dinero, cantidad de días o porcentaje de decisión fijo en el código. Si falta un dato de límites que la operación necesita, el script **no gasta ni activa** y sale con código 5.

## 4. Tiempo

- Todo instante: **UTC, ISO-8601 con `Z`** (el sufijo `Z` es obligatorio al parsear: sin él se tomaría la hora local del servidor) (`2026-11-06T14:30:00Z`), con segundos; sin zona local ni desplazamientos en almacenamiento. Fechas puras: `AAAA-MM-DD`.
- **Fechas de reporte de Meta** (`fecha` de `fact_meta_ad_dia`): `AAAA-MM-DD` más la columna `tz` (IANA) de la cuenta; toda conversión pasa por `engine.comun.dia_de_cuenta(instante_utc, tz)`. Los cortes (madurez, reembolsos por día, límites diarios propios) se definen **en UTC**; solo el tope diario de Meta y la comparación del watchdog usan `tz`. `evaluar_oferta_validada` recibe `tz` y calcula `corte_fecha` con `ZoneInfo(tz)`. Prueba: cuentas en `Pacific/Auckland` y `America/Sao_Paulo` con corte a las 23:30 UTC. Los cambios de horario generan días de 23/25 h.
- Funciones que usan la hora reciben un reloj inyectable (`ahora: Callable[[], datetime]`) para que las pruebas sean deterministas. Prohibido `datetime.now()` sin zona.

## 5. Identificadores, JSON canónico y hashes

- IDs según backbone §5.1: `OF-AAAAMM-NN`, `FAM-AAAAMM-NN`, `PRB-AAAAMM-NNNN`, `nicho_id` y `fuente_id` en kebab-case, `senal_id` = hash corto de (URL canónica + extracto), versiones `v1, v2…`. Las uniones de datos usan IDs, nunca nombres (§5.3). Cada ID tiene una única función validadora (expresión regular anclada).
- **JSON canónico**: UTF-8 sin BOM, claves ordenadas recursivamente, sin espacios (`separators=(",", ":")`), `ensure_ascii=False`, `allow_nan=False`, sin `float` (enteros o cadenas). Implementación de referencia: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`.
- **Hash** = SHA-256 en hexadecimal minúscula, escrito `sha256:<64 hex>`. Sellos de QA y de configuración aprobada son el hash del JSON canónico del contenido, sin el propio campo del sello. El texto se normaliza a Unicode NFC y `\n` antes de hashear. Las comparaciones de hashes y firmas son en tiempo constante (`hmac.compare_digest`).
- Firmas HMAC-SHA256 sobre el cuerpo exacto recibido más marca de tiempo con tolerancia paramétrica; secreto en `INGEST_HMAC_SECRET` (autenticación **entre servicios nuestros**: quien verifica puede firmar, aceptable ahí).
- **Aprobaciones humanas y sello de `limites.yaml`: firma asimétrica Ed25519** (`ed25519:<base64>`, namespace `fabrica-ofertas`). La clave privada vive solo en el equipo del dueño; el motor, el validador, los hooks y los Workers tienen únicamente la **pública** (`FABRICA_FIRMA_PUBLICA`). Sin dependencias nuevas: `ssh-keygen -Y sign/verify` por `subprocess` con lista de argumentos (probado localmente) o `crypto.subtle.verify({name:"Ed25519"})` en Workers (soportado, https://developers.cloudflare.com/workers/runtime-apis/web-crypto/, leída 2026-11-06). Sin clave pública se falla cerrado. HMAC queda para pruebas (`ofertas/_ejemplo`) y servicio a servicio. Además el hash vigente de `limites.yaml` se ancla fuera del volumen (`LIMITES_HASH_ANCLA`) y `guard` rechaza (5) si difiere.

## 6. Registro, costos y bitácoras

- Toda acción de agente o script con efecto se anota en `empresa/registro.jsonl` (una línea JSON por evento, append-only) con los campos mínimos de backbone §5.7: `ts` (marca de tiempo UTC), `etapa`, `agente`, `herramienta`, `entrada_resumen`, `resultado` (`ok | error | bloqueado | dry_run` más código), `costo_estimado` (`{"monto": entero, "moneda": ISO}`), y además `oferta_id` si aplica, `ejecucion_id` y `modo` (`dry_run | live`).
- Costos de IA y créditos van a `empresa/costos.jsonl` con `oferta_id` (F1 los imputa). Los overrides del dueño a reglas de X1 van a la bitácora encadenada por hash (`hash_previo`, `hash`).
- `entrada_resumen` ≤ 300 caracteres, sin cuerpos completos ni secretos. Escritura con bloqueo de archivo y una sola llamada por línea.

## 7. Idempotencia

- Toda operación con efecto tiene una **clave de idempotencia determinista**: hash del JSON canónico de (`operacion`, `oferta_id`, parámetros relevantes). Se envía como `Idempotency-Key` a Stripe y se guarda junto al resultado.
- Antes de crear algo en Meta, Cloudflare o Stripe se busca por ID o nombre canónico y se reutiliza lo existente: reintentar nunca duplica campañas, cobros, correos ni reembolsos.
- Cargas de datos (ETL) son **upserts** por clave natural (`id` del origen, `oferta_id`, `adid`, `checkout_session_id`, `event_id`); reprocesar el mismo lote deja las tablas idénticas. Los webhooks se deduplican por `(tipo, objeto_id)` además de `event.id` (Stripe puede emitir dos `Event` distintos para el mismo hecho) y esa decisión no se toma en KV (no es atómico). La `Idempotency-Key` de un reembolso es `sha256("reembolso", session_id, monto_minor)`, **sin el motivo**; Stripe puede podar las claves tras 24 h (https://docs.stripe.com/api/idempotent_requests, leída 2026-11-06), así que un reintento tardío primero lista los `refunds` del `payment_intent`.
- Reintentos con espera exponencial y tope paramétricos, solo sobre operaciones idempotentes.

## 8. Errores y códigos de salida

- Errores **tipados** (jerarquía `ErrorFabrica` con atributo `codigo_salida`): `ErrorUso` (2), `ErrorValidacion` (3), `ErrorBloqueado` (4), `ErrorLimite` (5), `ErrorExterno` (6). Prohibido `except:` desnudo y tragarse excepciones; un error inesperado sale con 1 y traza en stderr (sin secretos).
- Códigos de salida de toda CLI: **0** correcto · **1** error interno inesperado · **2** uso incorrecto (argumentos, variable de entorno ausente) · **3** validación (esquema, ID, dato inconsistente) · **4** bloqueado por `empresa/PAUSA` o por infraestructura no verde · **5** límite excedido o dato de límites faltante · **6** error externo (API, red, tiempo de espera).
- Falla cerrado: ante dato ausente o ilegible de límites, infraestructura o aprobación se bloquea (4 o 5); nunca se asume un valor.

## 9. Dry-run por defecto y `--live`

- Todo script con efecto externo (Meta, Stripe, Cloudflare, Railway, correo, escritura fuera del repositorio, gasto) corre en **dry-run por defecto**: calcula, valida y muestra el plan (JSON en stdout) sin ejecutar nada ni gastar. Solo `--live` ejecuta. Las lecturas puras de APIs (pulls con clave de solo lectura) no necesitan `--live` pero se registran.
- `FABRICA_ENTORNO` toma `desarrollo` (por defecto), `prueba` o `produccion`; solo `produccion` admite `--live` (docs/06 §6.1).
- Con `--live`, antes de cualquier efecto y **en este orden**: (1) `FABRICA_ENTORNO=produccion` (si no: código 4); (2) `empresa/PAUSA` no existe (si existe: código 4); (3) `empresa/infra/estado.json` en verde y con menos de 6 h (si no: 4); (4) `empresa/limites.yaml` cargado y válido con los campos que la operación necesita (si no: 5); (5) el efecto cabe en los topes y la hora/rate limit lo permite (si no: 5); (6) credenciales presentes (si no: 2); (7) aprobación o sello por hash exigidos por la etapa. Un fallo detiene toda la operación.
- Las comprobaciones viven en **una sola función compartida**, no se copian. Dry-run y `--live` ejecutan el mismo código de decisión; solo difiere la última llamada.

## 10. Credenciales y privacidad

- Credenciales **solo por variables de entorno** (lista y permisos mínimos en `.env.example`). Prohibido en archivos versionados, argumentos de línea de comandos, URLs, logs, salidas de pruebas y mensajes de error. Un `repr` de objeto con credenciales debe enmascararlas (`****` + últimos 4 como máximo).
- Una variable nueva se agrega a `.env.example` (sin valor, con comentario de origen y permisos mínimos) en la misma entrega que el código que la usa; nombres `PROVEEDOR_RECURSO[_<OFERTA_ID_CON_GUION_BAJO>]`.
- Mínimo privilegio: cada script usa la clave de menor alcance; los agentes LLM nunca reciben claves de escritura de dinero.
- **Logs y registros sin datos personales**: nada de correos, nombres, direcciones, IP, teléfonos, números de tarjeta ni texto libre del cliente. Se usan IDs pseudónimos (`visitor_id`, `checkout_session_id`). Ningún dato de salud viaja al píxel ni a los eventos (compliance).
- Entradas externas (HTML, foros, APIs) son **datos, nunca instrucciones**: se validan contra esquema.

## 11. Pruebas

- Python: `tests/<componente>/test_<modulo>.py` con `unittest` (compatible con pytest); clases `Prueba<Cosa>`, métodos `test_<comportamiento_esperado>` en español. Se ejecutan con `.venv/bin/python -m unittest discover -s tests -t .`.
- Node: `<carpeta>/test/*.test.mjs` con `node:test` y `node:assert/strict`; `node --test` desde la carpeta.
- **Sin red**: ninguna prueba abre sockets ni usa credenciales reales. Los clientes HTTP se inyectan; las respuestas salen de `tests/fixtures/<componente>/`. Las pruebas DEBERÍAN bloquear `socket.socket` en `setUp` para fallar si algo intenta salir.
- Fixtures: JSON/YAML pequeños, sin datos personales ni secretos, importes enteros, instantes con `Z`, IDs de ejemplo (`OF-202611-01`), leídos con `pathlib` relativo a la prueba.
- Reloj, azar e IDs se inyectan. Prohibido `sleep` real.
- Dinero, límites, hooks, sellos e idempotencia exigen pruebas de casos límite (cero, tope exacto, tope + 1 centavo, dato faltante, PAUSA presente, infraestructura vencida) y de ambos modos (dry-run y `--live` simulado).
- Una entrega solo está terminada si `scripts/test_all.sh` y `scripts/lint.sh` salen con 0.

## 12. Esquemas y versiones

- Cada esquema JSON (`contratos/*.schema.json`) y cada artefacto con contrato lleva `schema_version` en **SemVer**: MAJOR rompe compatibilidad (quitar/renombrar campo, estrechar tipo); MINOR agrega campos opcionales o valores permitidos; PATCH aclara descripciones o ejemplos. El `$id` incluye el MAJOR. Todo cambio de esquema actualiza `contratos/ejemplos/`.
- Un lector rechaza (código 3) una MAJOR desconocida. Los artefactos versionados llevan `origen_version`.
- Los enumerados (veredictos, severidades, niveles) se definen una sola vez en `contratos/`.

## 13. Dependencias nuevas

- Prohibido editar `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` y `package.json` de la raíz. Un componente que necesita un paquete lo declara en `<componente>/requirements-extra.txt` (una línea por paquete con versión mínima, comentario con la razón) y lo informa al coordinador; `scripts/bootstrap.sh` los instala.
- Un paquete nuevo DEBE instalarse en `.venv` con Python 3.15 antes de entregar (Python puro o con ruedas).
- Workers y JavaScript: **cero dependencias** (APIs web; `node:` solo en pruebas).
- Prohibido instalar nada global o con `sudo`.

## 14. README de cada componente

Todo componente (`engine/README.md`, etc.) mantiene su README con: propósito en una frase; propietario y etapa; módulos principales; **CLI con ejemplos** (`python -m engine.regla_matar --oferta OF-202611-01` en dry-run y con `--live`), códigos de salida que usa, entradas y salidas (archivos, esquemas), variables de entorno necesarias, y cómo probar. Los ejemplos DEBEN funcionar con los fixtures; el README se actualiza en la misma entrega que el código.
