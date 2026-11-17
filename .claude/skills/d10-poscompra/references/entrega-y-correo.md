# Entrega, correo transaccional y página de gracias

> v0.1 sin pulir. Verificado en el repositorio el 2026-11-07 (solo lectura). `[PENDIENTE: quién]` = la spec o el flujo lo pide y aún no existe; esta skill no lo inventa ni lo simula. Los cambios que pide van a `../PEDIDOS.md` (P-nn = código de S-B, A-nn = contratos/empresa/docs de S-A, C-nn = otras skills o `landing/`).

## 1. Qué hace hoy el código (pago → correo → descarga) y qué falta

| # | Paso | Dónde | Qué hace hoy | Qué falta | Pedido |
|---|---|---|---|---|---|
| 1 | El pago se confirma | `tracking/workers/webhook-stripe/src/manejador.mjs:104-107,131` | Verifica la firma, deduplica por `event.id` y `(tipo, objeto)`, dispara el Purchase por API de conversiones y responde `«encolado»` **sin llamar a `fulfill` ni leer `customer_details.email`** | Llamar a `fulfill` con un cuerpo firmado: `session_id`, `oferta_id`, líneas pagadas, `locale` y el correo | P-01 |
| 2 | Se entrega | `infra/workers/fulfill/src/{index,manejador}.mjs` | Valida el cuerpo firmado (HMAC + tolerancia 5 min), deduplica en KV, firma un enlace con vencimiento y cuota (HMAC-SHA256), manda el correo por `fetch` a Resend y avisa a `/ingesta/entrega` sin el correo | Ver §1.1 | P-02, P-03 |
| 3 | El comprador descarga | `infra/workers/descarga/src/index.mjs:12` y `logica.mjs:37-53` | `GET /d/<sesión>?token=` verifica el token, cuenta la descarga en KV y sirve el objeto de R2 | El `GET` ya consume cuota: un escáner de correo puede agotarla. La spec pide una página con botón (el `POST` descarga) | P-04 |
| 4 | Se registra | `dashboard/api.py:169-170` → `datos.ingesta.manejar_ingesta_entrega` | Escribe `entregas.jsonl` / `fact_entrega` (`entrega.schema.json`, sin correo ni IP) | Solo se emite el estado `entregado`; nadie emite `descargado`, `activado` ni `fallido` | P-05 |
| 5 | Se reembolsa | `postcompra/reembolsar.py`, `reembolso_manual.py` | Probado con dobles; `--live` deshabilitado (no hay `Transporte` HTTP real) | Transporte real; correo de confirmación por idioma | P-09 |
| 6 | /gracias | `landing/generar.py:153-155` (mínimo) y `:319-324` + `sitio-base/gracias.html` | Título, texto y enlace de vuelta | Ver §3 | C-01 |
| 7 | Alerta de entrega | — | **Nadie consume** `postcompra.entrega_max_min`, `entrega_alerta_min` ni `entrega_reintentos` (búsqueda en código = 0) | Job que compare `pagado_en` con la entrega, reintente a 1, 5 y 30 min y avise por dos canales | P-06 |

**Nada de esto corrió jamás contra Stripe, Cloudflare ni un proveedor de correo reales.** Los ids de KV y R2 son `PENDIENTE_CREAR_EN_CLOUDFLARE`; B0-24 sigue pendiente (`brechas/03` §0).

### 1.1 Lo que `fulfill` hace mal hoy (hallazgos de esta lectura, además de las brechas B3-01, B3-14 y B3-15)
1. **Marca «entregado» antes de enviar** y lo declara aunque el correo falle. `manejador.mjs:66` llama a `marcarEntregado` antes de `enviarCorreo`, y `:72` envía a la API `estado: "entregado"` **siempre**; `index.mjs` devuelve `sin_configuracion_correo` si falta la clave o el correo y aun así queda registrado como entregado. Con el `webhook-stripe` actual (que no pasa el correo) **todas** las entregas saldrían «entregadas» sin correo, el reintento recibiría «duplicado» y la métrica `entrega_ok` mentiría. Regla que pide D10: `entregado` solo cuando el proveedor aceptó el envío; si falla, `fallido` + reintentos por `entrega_reintentos` + alerta.
2. **Asunto fijo en español** (`index.mjs:96`, «Tu descarga está lista») y cuerpo de una línea: sin vendedor identificable, sin número de pedido, sin garantía ni procedimiento, sin confirmación de la renuncia (UE/UK). Incumple L1-05.
3. **Un solo `producto_sha256` y un solo token por sesión**: sin entrega por línea (§2).
4. **`from` y proveedor**: usa `fetch` directo a Resend en vez de `ResendCorreo`; el proveedor de correo está sin decidir (B3-15).
5. **El token viaja en la URL** (`?token=`): aceptable para un enlace firmado con vencimiento y cuota, pero no debe registrarse en bitácoras ni en `soporte.jsonl`.

## 2. Entrega por línea (qué pide D10)

Una sesión puede pagar varias **líneas**: `principal`, `bump` y, cuando existan, `upsell` y `postpago`. Reglas:

1. **Un correo, un enlace por línea pagada**, con el nombre de cada archivo (`{{lista_enlaces}}`). Nunca se entrega un ítem de una línea no pagada, ni la muestra (`en_paquete = false`).
2. **La unión línea ↔ archivos** hoy es solo por id (`oferta.bump.id` = `producto.items[].id`); D4 debe respetarlo. Propuesta: `items[].linea` (`principal|bump|upsell|postpago`), PEDIDO A-03. `scripts/d10.py plan-entrega` implementa esa regla (primero `linea`, si no existe el id del bump, si no `principal`) y rechaza una línea pagada sin archivos.
3. **Hoy no se cumple:** `postcompra/publicar_producto.py:68-75` empaqueta **todos** los ítems `en_paquete` en un solo zip con un hash del mapa completo, y `fulfill` firma un solo token (`manejador.mjs:36-60`). O el bump se entrega a todos o a nadie `[NO VERIFICADO cuál ocurre]`. PEDIDO P-03 + A-02 (`entrega.schema.json:53,104`: una fila por línea con campo `linea`).
4. **Reembolso:** total (bump incluido) por defecto; un reembolso parcial de una línea es decisión del dueño (cola manual).
5. **La entrega del producto principal nunca espera a la oferta tras el pago** (`oferta-tras-el-pago.md` §1).

## 3. Página de gracias (`/gracias`)

La genera D5 (`landing.generar`); D10 define qué debe decir y lo entrega en `gracias.md`. Hoy el sitio diseñado muestra título y texto de `copy.secciones.gracias` y un enlace de vuelta; el sitio mínimo dice «En breve recibirás el acceso por correo». Contenido requerido:

1. **Confirma el pago** y que el acceso llega por correo **a la dirección que indicó** (sin mostrarla) en menos de `postcompra.entrega_max_min` minutos.
2. **Si no llega:** revisar spam y promociones, esperar `entrega_alerta_min`, escribir a soporte con el número de pedido. Texto fijo por idioma.
3. **Primer paso** (de `producto.pasos`), una sola acción.
4. **Garantía y cómo pedirla:** copia literal de `oferta.garantia.texto_visible`, con enlace a `/legal/reembolsos`.
5. **Identidad del vendedor** y enlaces legales (los pone el pie de D5).
6. **Oferta tras el pago**, si existe, *debajo* de lo anterior y sin cuenta atrás ni escasez (`oferta-tras-el-pago.md`).
7. **Sin datos personales en la URL ni en la página**, sin scripts nuevos: la CSP solo admite `/js/consentimiento.js`, y `L1-FORMULARIO` solo admite el formulario de `/comprar`; una oferta con botón (formulario `POST`) exige ampliar esas reglas (PEDIDO C-01, con S-A/S-B).
8. **Enlace directo al acceso («al instante → entrega con link directo», `f086`)**: requiere que `success_url` lleve `{CHECKOUT_SESSION_ID}` y una ruta dinámica que resuelva el token; hoy `checkout.json › success_url` es `…/gracias` a secas. Opción, no requisito de v0.1 `[DUEÑO]`.

## 4. Plantillas de correo (`templates/correo-*.txt`)

| Plantilla | Tipo | Cuándo | Idiomas |
|---|---|---|---|
| `correo-entrega` (E0) | `entrega` | al confirmarse el pago | pl, es, en |
| `correo-resena` (E1) | `resena` | día 3 | pl, es, en |
| `correo-resena-recordatorio` (E2) | `resena` | día 7, solo si no respondió | pl, es, en |
| `correo-reembolso` (E3) | `reembolso` | tras ejecutarse el reembolso | pl, es, en |

Formato: líneas `# tipo:`, `# locale:`, `# estado:`; `Asunto: …`; línea en blanco; cuerpo con `{{campo}}`. Los campos son **la lista cerrada `CAMPOS` de `scripts/d10.py`**; el generador valida cada valor (URLs `https` con host permitido, enteros estrictos, texto sin controles ni marcas de dirección, un salto de línea en el asunto se convierte en espacio), escapa en HTML y expande **en una pasada** (un valor con `{{…}}` no se vuelve a expandir).

| Campo | De dónde sale | Nota |
|---|---|---|
| `marca`, `producto` | `oferta.marca.nombre`, `oferta` | el asunto **no** lleva `producto` |
| `pedido_ref` | lo asigna el código (propuesta: `ENT-` + 12 hex derivados del `session_id`, el mismo formato de `entrega.entrega_id`) | el comprador lo cita en soporte; el código lo resuelve a `checkout_session_id`; hoy el correo no lleva número de pedido |
| `lista_enlaces` / `enlace_descarga` | código (un enlace por línea) | jamás un enlace a otro dominio |
| `vence_dias`, `max_descargas` | `parametros.entrega.*` (7 y 5) o `producto.entrega` | hoy `fulfill` los lee de variables de entorno (PEDIDO P-02) |
| `garantia_dias`, `garantia_texto` | `oferta.garantia.dias` y `texto_visible` | **copia literal**; no se parafrasea |
| `bloque_renuncia` | texto sellado de `checkout.compra.renuncia.texto_version` (legales de D5), vacío si no se exige | D10 no redacta texto legal; en UE/UK es la confirmación en soporte duradero (L1-05) |
| `vendedor`, `soporte_email`, `politica_url` | D0 / dueño; `/legal/reembolsos` | obligatorios en todo correo |
| `primer_paso` | `producto.pasos[0]` | una sola acción |
| `baja_url`, `resena_url_1…5` | código (token de un solo pedido) | solo en la petición de reseña |
| `monto_texto`, `tiempo_reembolso` | código (monto real del reembolso, plazo habitual del método) | el Maker no inventa ni calcula importes |
| `aviso_ia` | `limites.politica_divulgacion_ia` | solo en respuestas de soporte |

Reglas de contenido (L1-05, L1-06, X1): transaccional sin promoción ni urgencia; sin emoji ni exclamaciones repetidas; asunto neutro (marca y pedido); sin claims de resultado; firma con la marca. `d10.py lint-plantilla` las comprueba. Las plantillas son **punto de partida**: la versión de una oferta pasa por QA, retraducción y segunda lectura (J11) y la sella X1 por hash; una vez sellada, un cambio es una versión nueva (D-23).

**Datos personales:** el correo del comprador lo tienen Stripe y el proveedor de correo; en el repositorio solo existe como `email_hmac` (`entregas.jsonl`) o como hash en el `outbox/`. El Maker nunca lo ve ni lo pide; el generador lo rechaza como campo (`email_comprador` no está en `CAMPOS`).

## 5. Estados de la entrega y quién los emite

`pagado → encolado → enviado → entregado → descargado → activado → resultado` | `fallido` (`entrega.schema.json`). `activado` = descarga + un clic confirmado, no una apertura (se descartan clics de escáner: agente de usuario o IP de seguridad, o menos de 5 s). `resultado` = respuesta afirmativa a la pregunta de utilidad **sin cifras de cambio** (en salud, relaciones y dinero se pregunta por la utilidad del material, no por cambios corporales, emocionales o de ingresos). Hoy solo se emite `entregado`.

## 6. `PAUSA` y entrega

`PAUSA` detiene al Maker, el marketing, las reseñas y los reembolsos **automáticos**; **no** detiene la entrega ni los correos transaccionales (detenerlos genera disputas, R17); los reembolsos pasan a la cola humana, que los honra en `postcompra.reembolso_ejecucion_h`.
