# 07 — Puesta en marcha: inventario verificado de lo necesario para un testeo en vivo

> Estado: 2026-11-06 · Rol: operaciones y seguridad · Subordinado a `docs/_backbone.md` (v2.2), que prevalece. Plantillas normativas en `infra/plantillas/`.
> **Alcance (decisión del dueño, 2026-11-06):** las bases para armar y automatizar **un testeo**. La pérdida máxima por oferta **no se fija acá**: todo tope es **paramétrico** (`limites.yaml`, `parametros.yaml`) y, si falta el dato, nada gasta ni activa. Pagos locales y régimen fiscal están **diferidos**: el testeo inicial cobra con tarjeta y billeteras de Stripe estándar, con el diseño listo para multimoneda. Ningún mercado (Polonia incluida) es prior: lo que depende del mercado aparece como condición (p. ej. DSA si se segmenta a la UE).
> **Etiquetas:** `[VERIFICAR]` sin comprobar · `[HIPÓTESIS]` valor a calibrar · `[DUEÑO]` acción o decisión del dueño · `[NUEVO]` diseño nuestro. "Verificado hoy" = leído en la página oficial citada el 2026-11-06; "(04)", "(03)", "(05)" = verificado el 2026-11-05 en `docs/_investigacion/`. Claves de fuente (`[M1]`…) en la sección 15. **No es asesoría legal ni fiscal.**

---

## 0. Resumen ejecutivo

1. Diez bloques (Meta, Stripe, Cloudflare, Railway, GitHub, correo, consentimiento y legales, secretos, preflight, kill switch). Cada uno se comprueba **solo en lectura** con `scripts/preflight.py`, que produce `empresa/infra/estado.json` (sección 10): sin VERDE y con menos de 6 h, nadie gasta.
2. La ruta crítica es de **espera**, no técnica: verificación del negocio en Meta, decisión sobre la cuenta deshabilitada, primer pago de Stripe (7–14 días) y límite de gasto (sección 12).
3. Costo fijo estimado **20–51 USD/mes** más ~1 USD/mes por dominio (sección 11).
4. Hallazgos críticos en la sección 14. Los más importantes: el nivel *Limited* de la API de Meta solo permite 1 usuario del sistema; Meta no documenta un permiso "solo pausar"; cuentas, portfolios y datasets de Meta son irreversibles; el gate humano no puede apoyarse en aprobadores de GitHub en repos privados; un enlace firmado de R2 no limita descargas.

---

## 1. META

### 1.1 Inventario y orden

| # | Elemento | Qué es / por qué / hecho verificado | Cómo se comprueba | Quién |
|---|---|---|---|---|
| M-A | **Portfolio** a nombre de la **LLC** | Un portfolio solo gestiona cuentas de **la misma empresa** salvo agencia verificada [H6]. Uno nuevo puede crear **1** cuenta publicitaria (3 tras entregar y pagar) [H3] | Información del negocio: "límite de creación de cuentas" | Dueño |
| M-B | **Verificación del negocio** | Documentos oficiales con el nombre legal exacto y dirección o teléfono: constitución, registro, documento fiscal gubernamental, extracto bancario (la factura de servicios solo para dirección/teléfono); sin documentos autopresentados; idiomas admitidos incluyen inglés, español, italiano y polaco [H2]. Obligatoria para acceso a datos sensibles [M1] | Centro de seguridad; si faltan datos > 1 semana se reinicia [H2] | Dueño |
| M-C | **Administrador** humano (el dueño) con el 2FA que exija Meta | La apelación solo la envía un administrador [HC-24]. Riesgo residual aceptado por el dueño (decisión 15): sin gestor de contraseñas, llaves físicas ni segundo administrador; los frenos de software no cambian. Si Meta restringe su perfil personal siendo el único administrador, puede caer la cuenta de anuncios | Lista de roles | Dueño |
| M-D | **UNA cuenta publicitaria limpia** (1.2) | Moneda y zona **irreversibles**. Tarjeta (el límite de gasto **no existe con fondos prepagos** [HC-28]) | `GET /act_<id>?fields=account_status,disable_reason,currency,timezone_name,spend_cap,amount_spent,funding_source` [M3] | Dueño crea; script lee |
| M-E | **Fan page** propia, sin Instagram | Identidad del anuncio y punto único de falla (13 §R1) | `ads_get_ad_account_pages` | Dueño |
| M-F | **App de empresa** del portfolio | Para generar tokens, usuario y app deben ser del mismo portfolio [M2]. Para gestionar **solo cuentas propias** basta el acceso estándar a `ads_read` y `ads_management`, **sin revisión de app** [M1]. Modo de la app `[VERIFICAR]` | `debug_token` | Dueño |
| M-G | **Usuarios del sistema** (1.3) | Sus tokens no atribuyen acciones a una persona [M4] | `debug_token` | Dueño genera |
| M-H | **Dominio verificado por oferta** | TXT en DNS, meta-tag o archivo HTML, gratis [HC-36]. Para web ya no se priorizan eventos (AEM) "cuando tengas acceso" [HC-15] `[VERIFICAR]`; se verifica igual: `event_source_url` debe coincidir con el dominio [DV-7] | TXT en Cloudflare + estado en el portfolio | Sistema pone el TXT; dueño confirma |
| M-I | **Un dataset por oferta** (decisión 8) | Se crea en el portfolio; **máx. 100, no se borran ni se transfieren** [H5]. Nombre `DS_{oferta_id}` | `ads_get_datasets`, `ads_get_dataset_stats` | Dueño crea |
| M-J | **Token de la API de Conversiones por dataset** | Se genera en Administrador de eventos → píxel → API de Conversiones → "Generar token", o asignando el píxel a un usuario del sistema; **sin revisión de app** [M5]. Un token por dataset acota la fuga a una oferta. Si crea un usuario del sistema que cuente contra el límite: `[VERIFICAR]` | Evento con `test_event_code` (10.3) | Dueño |
| M-K | **Límite de gasto de la cuenta** (capa 3) | Al alcanzarlo se pausan todos los anuncios; ~15 min en aplicarse; solo administradores; 10 cambios/día [HC-28][DV-2]. En la API es `spend_cap` (lectura en unidad menor; escritura en unidad estándar `23.50`; `spend_cap_action=reset`; `0` = **sin tope**) [M3]; la fijación la hace el dueño en el panel y los scripts **solo leen**. Meta usa un *offset* propio por moneda: **1** para CLP, COP, CRC, HUF, ISK, IDR, JPY, KRW, PYG, TWD y VND, **100** para el resto (https://developers.facebook.com/docs/marketing-api/currencies, leída 2026-11-06): enviar el importe ISO sin convertir puede multiplicar el gasto por 100 (`meta/monedas.py`, B5; mientras no esté probado, `moneda_limites` ∉ esa lista, validado en `evaluar_limites`) | `spend_cap > amount_spent` y ≤ `limite_gasto_cuenta_meta` | **Dueño** |
| M-L | **DSA (UE)** | Si el anuncio segmenta a la UE o es "mundial" hay que informar **anunciante** y, si difiere, **pagador**; sin ello **no se publica**, tampoco por Marketing API. Los valores por defecto se fijan en la cuenta con control total y se leen como `default_dsa_beneficiary` y `default_dsa_payor` (ambos o ninguno) [H1][M3] | Preflight M-07 | Dueño una vez (nombre legal de la LLC) |

### 1.2 La cuenta deshabilitada y el píxel inactivo: diagnosticar sin contaminar

**Hechos (02):** 6 cuentas; 1 deshabilitada por "actividad inusual"; 1 sin pago; 1 sin empresa; un píxel sin disparos desde ~mayo de 2026.

**Principios `[NUEVO]`:** (i) lo irreversible se decide con datos; (ii) **no se oculta nada**: Meta podría relacionar cuentas por persona, pago o dispositivo `[VERIFICAR: no figura en lo leído]` y eludir restricciones está prohibido [TC-4]: la limpieza es de hechos (entidad verificada, página propia, cumplimiento); (iii) la cuenta vieja **no se opera** y su píxel **no se reutiliza** (queda dormido y desasignado, porque un dataset no se borra [H5]).

**Diagnóstico, solo lectura (~1–2 h del dueño):**

1. Identificar a qué **portfolio** pertenecen la cuenta y el píxel, y si ese portfolio está restringido.
2. `GET /act_<id>?fields=account_status,disable_reason,business`. Valores documentados de `disable_reason` [M3]: 1 `ADS_INTEGRITY_POLICY`, 2 `ADS_IP_REVIEW`, 3 `RISK_PAYMENT`, 4 `GRAY_ACCOUNT_SHUT_DOWN`, 5 `ADS_AFC_REVIEW`, 6 `BUSINESS_INTEGRITY_RAR`, 7 `PERMANENT_CLOSE`, 8 `UNUSED_RESELLER_ACCOUNT`, 9 `UNUSED_ACCOUNT`, 10 `UMBRELLA_AD_ACCOUNT`, 11 `BUSINESS_MANAGER_INTEGRITY_POLICY`, 12 `MISREPRESENTED_AD_ACCOUNT`, 13 `AOAB_DESHARE_LEGAL_ENTITY`, 14 `CTX_THREAD_REVIEW`, 15 `COMPROMISED_AD_ACCOUNT`.
3. En Estado de la cuenta ver si hay **solicitud de revisión**: un administrador, número limitado, decisión final [HC-24].
4. Decidir (la lectura interpreta el *nombre* del valor: confirmar con el texto del Estado de la cuenta `[VERIFICAR]`):

| Diagnóstico | Acción | ¿Cuenta limpia nueva? |
|---|---|---|
| 1, 5, 6, 12 (integridad / tergiversación) con apelación disponible | **Apelar una vez**, con texto fáctico; no operar mientras tanto | Sí, en portfolio verificado de la LLC, sin el píxel viejo; consultar a soporte si se considera relacionada `[VERIFICAR]` |
| 11, o portfolio restringido | **No usar ese portfolio**; crear uno nuevo de la LLC y verificarlo | Sí |
| 3 (riesgo de pago) | No reutilizar ese método; tarjeta virtual con tope de la LLC | Sí |
| 15 (comprometida) | Cerrar el incidente: contraseñas, 2FA, accesos | Tras cerrarlo |
| 7 (cierre permanente) | Abandonar y documentar `[VERIFICAR]` | Sí |
| 8, 9 (sin uso) o sin motivo legible | Apelar y, en paralelo, preparar el portfolio limpio | Sí |

5. **Regla:** si la apelación reinstala la cuenta antigua **y** su historial está limpio, el dueño puede preferirla (el gasto acumulado sube los límites diarios de Meta [HC-29]); la nueva queda sin uso. Se decide **una** cuenta (backbone §2.8); `cuentas_permitidas[]` contiene solo esa.
6. Se registra en `empresa/infra/meta.yaml` (sin datos personales).

### 1.3 Usuarios del sistema, permisos y tokens

**Verificado hoy** [M1][M2][M4]: niveles *Limited* (por defecto) y *Full* (≥ 500 llamadas en 15 días y < 15 % de error en las últimas 500); **Limited = 1 usuario del sistema + 1 admin; Full = 10 + 1**; `ads_read` (informes) y `ads_management` (leer y gestionar); alcances aceptados por usuarios del sistema: `ads_management`, `business_management`, `catalog_management`, `pages_read_engagement`, `pages_show_list`, `instagram_basic`, entre otros; token con vencimiento de **60 días** (`set_token_expires_in_60_days=true`, recomendado como práctica de seguridad) o **sin vencimiento**.

| Función | Alcance | Activos asignados | No lleva |
|---|---|---|---|
| **Operador** (borradores, activar con hash, presupuesto dentro de topes) | `ads_management` | cuenta publicitaria + fan page | `business_management`, `catalog_management`, `instagram_basic` |
| **Lectura** (preflight, ETL, F2) | `ads_read` | cuenta, datasets | `ads_management` |
| **Pausa** (watchdog, `pausar.py`) | `ads_management` | **solo** la cuenta | página, datasets, portfolio |
| **API de Conversiones** (Worker `capi`) | el que ofrezca "Generar token" | **solo** el dataset de la oferta | cuenta publicitaria |
| **Admin del sistema** | `business_management` | — | **fuera del alcance de agentes y scripts**; se usa a mano y se revoca tras cada alta |

Notas: (a) `pages_show_list` y `pages_read_engagement` se suman solo si la creación de anuncios falla sin ellas `[VERIFICAR]`: se empieza sin ellas; (b) `ads_management` incluye lectura [M1], por eso la lectura pura es un usuario aparte; (c) **"solo pausa"**: Meta no documenta un alcance así; se aproxima con usuario distinto, acceso solo a la cuenta, secreto guardado únicamente en el Worker `watchdog` y en `pausar.py`, y código que solo emite `GET .../campaigns?effective_status` y `POST .../<id> status=PAUSED`; (d) detalle en `infra/plantillas/permisos-tokens.yaml`.

**Escalón de privilegios `[NUEVO]`:**

| Fase | Ranura regular | Consecuencia |
|---|---|---|
| **1 — Limited** (hasta N2) | 1 operador | Lectura y pausa usan el mismo token; el watchdog guarda una **copia**. Menor aislamiento, aceptado porque el límite de cuenta (capa 3) y el tope diario acotan el gasto |
| **2 — Full** (antes de N3) | `operador`, `lectura`, `pausa` y `capi` separados | Rotación y revocación independientes. Se solicita cuando la sonda ligera acumula ~100 lecturas/día (500 llamadas en 15 días) `[VERIFICAR si las lecturas cuentan]` |

### 1.4 Límites de la API, presupuestos y borradores

**Límites (DV-2, 04):** puntaje de `ads_management` 60 (Limited) vs 9.000 (Full), lecturas = 1 y escrituras = 3; 1 edición por objeto cada 30 s; **4 cambios de presupuesto por hora por conjunto**; error 613 sin subcódigo = cuota reducida por tráfico inusual; encabezados `X-Ad-Account-Usage`, `X-Business-Use-Case`. Cuentas regulares: 50 anuncios por conjunto, 5.000 conjuntos, 5.000 campañas, 5.000 anuncios [H4] (cierra la contradicción de 04 §7.2).

**Presupuestos:** cambios pequeños no reinician el aprendizaje; no hay porcentaje oficial (HC-3); Meta puede gastar hasta **175 %** del diario (HC-26). Regla: `presupuesto_diario × 1,75 ≤ tope_diario_oferta`; incrementos y espaciado salen de `limites.yaml`, nunca del código ni del modelo. La cola respeta ≥ 30 s por objeto y ≤ 4 cambios/hora/conjunto.

**Borradores `[NUEVO]`:** el script crea campaña, conjunto y anuncio por API con `status=PAUSED`; solo `activar_campana.py` (con `hash_config` aprobado y `object_ids` exactos) activa. Si la revisión ocurre al crear o al activar es `[VERIFICAR]` (HC-25). Con el conector MCP, `ads_activate_entity` puede dejar ACTIVO (02): prueba A-9 (9.3).

| Objeto | Nombre (backbone §5.2; ASCII, sin `|`) | Ejemplo |
|---|---|---|
| Campaña | `{oferta_id}_{fase}_{objetivo}_{estructura}_{AAAAMMDD}` | `OF-202611-01_TEST_VENTAS_CBO_20261110` |
| Conjunto | `{audiencia}_{ubicaciones}_{idioma}` | `ADV-AMPLIA_AUTO_it` |
| Anuncio | `{concepto_id}_{formato}_{hook_id}_v{n}` | `C03_VID9x16_H02_v1` |
| Enlace | `utm_source=meta&utm_medium=paid&utm_campaign={{campaign.name}}&utm_content={{ad.name}}&utm_term={{adset.name}}&oferta_id=<id>&cid={{campaign.id}}&asid={{adset.id}}&adid={{ad.id}}` | macros de nombre **congeladas al publicar** (HC-16): toda unión usa IDs |

---

## 2. STRIPE

### 2.1 Modos y concentración

- **Prueba (sandbox) y vivo** tienen claves, destinos y `whsec_` **distintos** [S-wh]. Todo se construye en prueba; pasar a vivo es un paso de checklist con firma del dueño.
- **Cuenta única = riesgo existencial.** Mitigaciones `[NUEVO]`: descriptor claro, garantía y reembolso fáciles, alertas de disputas por oferta (0,3 % / 0,6 % [HIPÓTESIS], 03 §5.2), no mezclar ofertas de riesgo alto (13 §R2), y evaluar **más adelante** un procesador secundario declarado; **no** una segunda cuenta de Stripe para esquivar un cierre `[VERIFICAR términos]`. Primer pago de cuenta nueva: 7–14 días, con posibles retenciones sin umbrales públicos (03 §5.3): el capital de trabajo adelanta el gasto.
- Ya resuelto: la LLC y su cuenta verificada (decisión 7). Con el contador: IVA/OSS y sales tax (diferido).

### 2.2 Claves restringidas por función

**Verificado hoy** [S-rak]: claves `rk_live_`/`rk_test_` con **None / Read / Write** por recurso; Write implica Read; **una clave por servicio**; crearla exige verificación en dos pasos; el valor se muestra una sola vez; la clave antigua puede expirar con demora de hasta 7 días; los *request logs* muestran los 403 para ajustar permisos.

| Clave | Permisos | La usa | Dónde vive |
|---|---|---|---|
| `rk_checkout` | Checkout Sessions: Write (Prices/Products: Read solo si el 403 de sandbox lo exige) | Worker `crear-sesion` | Secreto de ese Worker |
| `rk_entrega` | Checkout Sessions, PaymentIntents, Charges: Read | Workers `fulfill` y `capi` | Secretos de esos Workers |
| `rk_lectura` | Read en Balance, Balance transactions, Charges, Refunds, Disputes, Early fraud warnings, Payouts, Checkout Sessions, Customers, PaymentIntents, Prices, Products, Events, Webhook endpoints, Reporting | ETL y preflight | Variable de `etl`/`motor` |
| `rk_reembolso` | Refunds: Write; Charges y PaymentIntents: Read | Servicio determinista de D10, con topes (`reembolso_auto_max`, `reembolsos_auto_max_por_dia`) | Variable de ese servicio; **ningún agente** |
| `rk_catalogo` | Products y Prices: Write | `stripe_catalogo.py` del dueño o CI con aprobación | Solo máquina/CI del dueño |

**Nunca `sk_`.** Nombres exactos de recursos y mínimo efectivo se afinan en sandbox con los 403 `[VERIFICAR]`. Rotación 90 días [HIPÓTESIS].

### 2.3 Webhooks: eventos exactos

**Verificado hoy** [S-wh]: destinos en Workbench o por la API `v2/core/event_destinations`, hasta **16**; formato *thin* (recomendado para integraciones nuevas) o *snapshot*; HTTPS público, TLS 1.2+; `Stripe-Signature` con `whsec_` **por destino y modo**; cuerpo crudo; tolerancia 5 min (nunca 0); reintentos hasta **3 días** (3 intentos en sandbox); reenvío 15 días (panel) / 30 (CLI); sin garantía de orden; deduplicar por `event.id`; 3xx es fallo; rotación con ventana de hasta 24 h.

**Diseño `[NUEVO]`: dos destinos independientes**, cada uno en prueba y vivo (02 §5.5):

| Destino | URL | Procesa | Eventos |
|---|---|---|---|
| `entrega` | `https://hooks.<dominio_infra>/stripe` (Worker `webhook-stripe`) | `fulfill` → `capi`; sigue vivo si Railway cae | `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `charge.refunded` |
| `finanzas` | `https://api.<dominio_infra>/webhooks/stripe` (Railway) | ledger de F1 | los cuatro anteriores más `checkout.session.expired`, `charge.dispute.created`, `charge.dispute.closed`, `radar.early_fraud_warning.created`, `payout.paid`, `payout.failed` |

Formato **snapshot** (se necesita `data.object` sin lecturas extra; la cuota de lecturas es ~500 por transacción, 03 §7.3) `[VERIFICAR]` por evento. El Worker fija `Stripe-Version` en cada llamada; la documentación actual muestra `2026-10-28.endive` [S-cs]: qué versión fijar se decide en sandbox. Acción por evento y casos de prueba en `infra/plantillas/stripe-eventos-webhook.yaml`.

**Deduplicación (verificada 2026-11-06, https://docs.stripe.com/webhooks y https://developers.cloudflare.com/kv/concepts/how-kv-works/):** Stripe dice que «en algunos casos se generan y envían dos objetos Event distintos» y que se identifican con el ID de `data.object` junto al `event.type`; recomienda además **lista de IPs permitidas + firma** (https://docs.stripe.com/ips). KV tarda hasta 60 s o más en propagarse y «no es ideal» para operaciones atómicas (recomienda Durable Objects). Por eso la clave de «ya procesado» es `(tipo, objeto_id)` —no solo `event.id`— y se decide en un **Durable Object por `session_id`** (o D1 con `INSERT … ON CONFLICT DO NOTHING` comprobando `changes`); KV queda para contadores no críticos. La respuesta 2xx va antes de `fulfill`, pero el estado `encolado` se escribe primero en el Durable Object. Regla WAF del Worker: IPs de Stripe + firma.

### 2.4 Productos, precios multimoneda e IDs

- **Un `Product` por (oferta, rol)**, rol ∈ {`front`, `bump`}; **un `Price` por variante**; monedas extra en `currency_options` del mismo `Price` (precio local redondo, riesgo cambiario nuestro) o Adaptive Pricing (0 % para el negocio, 2–4 % para el cliente, 03 §1.5). La moneda por mercado la decide el dueño con M1.
- **`lookup_key`** `OF-AAAAMM-NN_{rol}_v{n}` (caracteres admitidos `[VERIFICAR]`). Un `Price` usado **no se modifica**: nace `v{n+1}` y se transfiere el `lookup_key`. `metadata`: `oferta_id`, `rol`, `variante`.
- **El precio nunca viene del cliente:** `crear-sesion` mapea `oferta_id → price_id` desde un catálogo firmado (D0 I2).
- **Sesión** [S-cs]: `client_reference_id` hasta **200 caracteres** (cierra un `[VERIFICAR]` de 03); `expires_at` entre **30 min y 24 h**; `metadata`; `optional_items` (máx. 10); el esquema ya lista `blik`, `p24`, `ideal`, `satispay`, `mb_way`, `bizum` y un parámetro `managed_payments` para cuando se retomen los diferidos. Testeo inicial: `mode=payment`, `ui_mode=hosted_page`, métodos dinámicos del panel.
- **`metadata`** (03 §3.2): `oferta_id`, `cid`, `asid`, `adid`, `utm_*`, `fbp`, `fbc`, `visitor_id`, `landing_version`, `precio_variante`, `bump_visto`, `bump_tomado`, `event_id`. Sin datos personales.

### 2.5 Descriptor, Radar, Tax y diferidos

- **Descriptor** [S-desc]: 5–22 caracteres latinos, con una letra, sin `< > \ ' " *`, reflejando el nombre comercial; prefijo estático de 2–10 caracteres más sufijo dinámico solo en tarjetas (`payment_intent_data.statement_descriptor_suffix`). Diseño: prefijo = marca de la LLC; sufijo = código de oferta.
- **Radar:** lo básico viene con Payments `[VERIFICAR]`; el avanzado cuesta 0,05 USD por transacción (03 §4.1), 0,3–0,4 % sobre 13–17 USD: no en el primer testeo.
- **Stripe Tax:** `automatic_tax` en la sesión; 0,5 % o 0,50 USD por API; no presenta ni remite (03 §6.1). Diferido.
- **Diferidos (dueño):** régimen fiscal, Managed Payments (+3,5 %; incompatible con BLIK, Przelewy24, Satispay, MB WAY, EPS, Pay by Bank, 00 §4) y métodos locales. Queda hecho: monedas en `currency_options`, `mercado.json` con métodos por país y `impuestos.modo` por oferta.

### 2.6 Comprobación

Lectura con `rk_lectura`: cuenta habilitada sin requisitos vencidos, destinos con los eventos exactos, `Price` = `checkout.json`, descriptor, huecos de eventos 24 h. Escritura en sandbox con `stripe trigger` y firmas sintéticas. **La página de pago no se automatiza** [03 S38]: compra manual de prueba por oferta y **una compra real mínima con reembolso** antes de activar (gate H).

---

## 3. CLOUDFLARE

### 3.1 Elementos

| Elemento | Decisión | Datos verificados |
|---|---|---|
| **Zona por oferta** | Plan Free; registrador Cloudflare | A costo del registro, sin recargo; WHOIS privado y renovación automática por defecto; DNSSEC a un clic [CF-9]. Precio por TLD `[VERIFICAR]` |
| **Pages** (landing estática, un proyecto por oferta) | Compilado desde Actions | Free: 500 builds/mes, 100 proyectos, 20.000 archivos, 25 MiB por archivo, 100 dominios por proyecto; las Pages Functions cuentan en la cuota de Workers [CF-3]. Workers tiene paridad de funciones y se presenta como más amplio; no hay aviso de retiro de Pages en lo leído [CF-10]: despliegue agnóstico (02 §5.2) |
| **Workers** | Plan **Paid, 5 USD/mes** | Free: 100.000 solicitudes/día, **10 ms de CPU**, **5 crons**, 50 subrequests, 64 secretos. Paid: 10 M solicitudes/mes, **250 crons**, 10.000 subrequests, 128 secretos, 15 min de CPU por cron [CF-4][CF-5]. Firmar HMAC con 10 ms es justo y habrá más de 5 crons |
| **KV** | Latido, estado y contadores de descarga | Free: **1.000 escrituras/día**; Paid: 1 M/mes [CF-8] |
| **R2** privado | Un bucket, carpeta `/<oferta_id>/` | 10 GB, 1 M ops clase A y 10 M clase B gratis; luego 0,015 USD/GB-mes; salida **gratuita** por Workers, S3 o r2.dev [CF-6] |
| **Cron** | `triggers.crons` en Wrangler | **UTC**; cambios tardan hasta **15 min**; reintento tras fallo `[VERIFICAR]` [CF-1] |

### 3.2 Workers y rutas

| Worker | Ruta o disparador | Secretos (nombres) | Función |
|---|---|---|---|
| `crear-sesion` | `<dominio_oferta>/api/sesion*` en **cada zona** (mismo origen: cookies propias, sin CORS) | `STRIPE_RK_CHECKOUT`, `CATALOGO_HMAC` | Crea la sesión con precio de catálogo y `metadata` |
| `webhook-stripe` | `hooks.<dominio_infra>/stripe` | `STRIPE_WHSEC_LIVE/TEST` | Firma, `event_id` único, 2xx rápido, cola |
| `fulfill` | interno | `STRIPE_RK_ENTREGA`, `CORREO_API_KEY`, `DESCARGA_HMAC` | Entrega idempotente |
| `capi` | interno | `META_CAPI_TOKEN__<oferta>` | `Purchase` con `event_id = purchase_<session_id>` |
| `descarga` | `descargas.<dominio_infra>/d/*` | `DESCARGA_HMAC` + binding R2 y KV | Valida token, cuenta descargas, sirve |
| `watchdog` | cron `*/5 * * * *` + `fetch` | `META_TOKEN_PAUSA`, `LATIDO_HMAC`, `ALERTA_*` | Sección 9 |

Secretos **por Worker, sin compartir**, ≤ 5 KB cada uno [CF-5]. Lista completa en `variables-entorno.yaml`.

### 3.3 Tokens de mínimo privilegio

**Verificado hoy** [CF-7]: permisos Read/Edit por grupo, acotados a zona o cuenta, con TTL y filtro de IP opcionales, verificables en `GET /user/tokens/verify`; los nuevos llevan prefijo `cfut_` (detectable por escáneres); secreto visible una vez.

| Token | Permisos | Recurso | Lo usa |
|---|---|---|---|
| `cf_deploy` | Workers Scripts, Routes, KV y Pages: Edit `[VERIFICAR nombres]` | cuenta y zonas de ofertas | GitHub Actions (`produccion`) |
| `cf_dns` | DNS: Edit | solo zonas de ofertas | `dominio_alta.py` |
| `cf_lectura` | Workers Scripts, Zone, DNS, Pages: Read | cuenta | preflight |
| `r2_subida` / `r2_respaldo` | R2 Object Read & Write | un bucket cada uno | CI/D4; servicio de respaldo |

Sin token de propietario programático; TTL máx. 90 días.

### 3.4 Entrega de archivos

**Verificado hoy** [CF-2]: las URL firmadas de R2 permiten GET/HEAD/PUT/DELETE, vencen entre 1 s y **7 días**, se generan con SigV4 y credenciales S3 en `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, **no funcionan con dominios propios**, el *binding* de Worker **no** las genera y son **portadores reutilizables** hasta vencer.

**Decisión:** el Worker `descarga` sirve con el *binding* tras validar un token HMAC y descontar un contador KV (7 días y 5 descargas [HIPÓTESIS], 03 §2.2); el correo lleva a una página con botón (los escáneres agotarían un enlace directo). Así no hay claves S3 en el borde y el límite **sí se aplica**. Las URL firmadas quedan para subidas de CI.

### 3.5 Despliegue desde GitHub Actions

**Verificado hoy** [CF-11]: acción `cloudflare/wrangler-action@v4`; secretos `CLOUDFLARE_API_TOKEN` (edición de Workers acotada a la cuenta) y `CLOUDFLARE_ACCOUNT_ID`, en los secretos del CI. Reglas `[NUEVO]`: despliegue por `workflow_dispatch` en el entorno `produccion`, no en cada push; antes, pruebas, `gitleaks` y comprobación de `estado.json` no ROJO; **los secretos de ejecución de los Workers no pasan por Actions** (los carga el dueño, sección 8); `rollback_a` de un comando; scripts con dry-run por defecto y `--live`.

---

## 4. RAILWAY

Planes verificados hoy [RW-3]: Free (1 USD de crédito, 0,5 GB, 1 vCPU), **Hobby 5 USD/mes** (5 USD de uso incluido), Pro 20 USD. Uso: RAM 10 USD/GB-mes, CPU 20 USD/vCPU-mes, volumen 0,15 USD/GB-mes, salida 0,05 USD/GB.

| Elemento | Diseño y datos verificados |
|---|---|
| **Proyecto** `fabrica-ofertas` | Entornos `produccion` y `pruebas`; cada entorno tiene red aislada [RW-4] |
| **`motor`** | 1 réplica siempre encendida (escritor único); scheduler interno, sin depender del cron de Railway |
| **`etl`** | Servicio *cron*: Meta cada 3 h con reproceso de 7 días; backfill diario de Stripe. Cinco campos en **UTC**, intervalo mínimo **5 min**, si la ejecución previa sigue activa Railway **omite** la siguiente, y el proceso debe **terminar** y cerrar conexiones [RW-1] |
| **`api`** | Panel y destino `finanzas`; único con dominio público, con inicio de sesión 2FA |
| **Postgres** | Servicio con volumen; red privada `SERVICIO.railway.internal`, cifrada, sin exponer puertos [RW-4]; **sin proxy TCP público** |
| **Respaldo** | Copias de volumen: diaria (6 días), semanal (27), mensual (89); manual hasta el 50 % del volumen; restaurar monta un volumen nuevo y requiere redeploy; solo en el mismo proyecto y entorno [RW-2]; Postgres no se nombra en la página `[VERIFICAR]`. **Segunda copia propia:** `pg_dump` nocturno cifrado a un bucket R2 distinto, con **restauración probada cada mes** |
| **Variables** | Por servicio, con referencias entre servicios; solo las suyas (`variables-entorno.yaml`); las carga el dueño en el panel |
| **Conexiones** | `motor`/`etl` → Postgres por red privada; desde Cloudflare solo llega `api` (HTTPS con HMAC) |

Cada servicio expone `/salud`. Región y tokens de solo lectura `[VERIFICAR]`.

---

## 5. GITHUB

**Verificado hoy** [GH-1][GH-2][GH-4]: Free incluye repos privados y 2.000 min/mes de Actions, pero reglas de repositorio, secretos y ramas de entorno y revisores de PR figuran **solo para repos públicos**; Team (**4 USD por usuario/mes**) los incluye en privados. Las **reglas de protección de entornos** (aprobadores de un despliegue) figuran **solo para repos públicos** en ambos planes `[VERIFICAR en Enterprise]`. Cron de Actions: mínimo **5 min**, UTC (admite zona IANA), **solo rama por defecto**, puede retrasarse o descartarse con carga alta.

| Elemento | Decisión `[NUEVO]` |
|---|---|
| Repo | **Privado**, en una organización Team de 1 usuario `[VERIFICAR si Pro personal alcanza]` |
| `main` | PR y 1 aprobación, CI y `gitleaks` obligatorios, sin *force-push*, historial lineal, `CODEOWNERS` sobre `contratos/**`, `.claude/**`, `empresa/limites.yaml`, `scripts/preflight*`, `infra/workers/**`. **El agente nunca empuja a `main`** |
| Entornos | `pruebas` y `produccion` con secretos propios. **El gate humano real es la firma del dueño** (`orq firmar`), no un aprobador de GitHub |
| Secretos de Actions | Solo despliegue (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `RAILWAY_TOKEN`); **nunca** `rk_`, `whsec_` ni tokens de Meta |
| Escaneo | `gitleaks` en *pre-commit* y CI (`EAA`, `sk_`, `rk_`, `whsec_`, `cfut_`); el escaneo nativo en privados es de pago `[VERIFICAR]` |
| Flujos | `permissions: contents: read`, acciones fijadas por SHA, nada de `pull_request_target` con código de ramas |
| Programadas | Solo CI e integridad (hash de scripts firmados); **no** lo que mueve dinero. El preflight corre en Railway |
| Cuenta | 2FA el que exija GitHub (método a elección del dueño), tokens finos con vencimiento |

---

## 6. CORREO TRANSACCIONAL

Requisitos: recibo y entrega inmediatos, reenvío self-service, rebotes y quejas a un Worker, dominio autenticado por oferta, **solo transaccional** (el marketing es otra pista con opt-in, 05 §4.3).

| | Resend | Postmark | Amazon SES |
|---|---|---|---|
| Precio verificado hoy | Free: 3.000/mes, **100/día**, **3 dominios**. Pro 20 USD: 50.000/mes, 10 dominios [EM-1] | Gratis: 100/mes. Desde 10.000/mes: Basic 15 USD (5 dominios), Pro 16,50 (10), Platform 18 (ilimitados) [EM-2] | 0,10 USD por 1.000; IP dedicada 24,95 USD/mes; 200 USD de créditos por 6 meses [EM-3] |
| Transaccional/marketing | Por dominio o subdominio; seguimiento configurable [EM-4] | Flujos separados [EM-2] | Configuración propia |
| Esfuerzo | Mínimo (API HTTP) | Mínimo | Mayor (salida del *sandbox*, rebotes propios `[VERIFICAR]`) |
| Límite que muerde | La 4.ª oferta con dominio propio exige Pro | 100 mensajes gratis | Operación propia |

**Recomendación por defecto: Resend**, en Free hasta 3 ofertas y < 100 correos/día, luego Pro; Postmark si se quiere separación de flujos desde el inicio; SES con volumen alto. No se afirma que un proveedor entregue mejor: se mide (E-02).

**Por oferta** (subdominio `envio.<dominio_oferta>`, no la raíz [EM-4]): dominio en el proveedor con Return-Path personalizado; en Cloudflare **SPF**, **DKIM**, registros de rebote y **DMARC** `p=none` con `rua` a buzón propio durante 30 días [HIPÓTESIS], luego `quarantine` (D0 §3.4), todos **sin proxy**; `soporte@<dominio_oferta>` con buzón real (reenvío de Cloudflare `[VERIFICAR]`) y `Reply-To`; webhook de rebotes con lista de supresión; prueba a Gmail y Outlook con SPF, DKIM y DMARC en `pass` (D0 I5).

---

## 7. CONSENTIMIENTO (CMP) Y PÁGINAS LEGALES

### 7.1 CMP

Regla (05 §4.1, backbone §5.3): el píxel y la API de Conversiones **de marketing** solo se disparan con consentimiento donde sea obligatorio (UE/UK; prudencia en el resto); **Stripe sigue siendo la verdad de ingresos** y la medición tolera tráfico sin consentimiento.

| Opción | Estado | Uso |
|---|---|---|
| **Banner propio mínimo** en la landing (JS sin dependencias): Aceptar todo / Rechazar todo / Personalizar con igual peso, **todo apagado por defecto**, elección en cookie propia y registro con fecha y versión del texto; `fbq` y `capi` solo tras consentir | Diseño nuestro, sin costo; lo hace D5 y lo revisa X1 | **Por defecto** en el primer testeo |
| **Zaraz Consent Management** (Cloudflare) | Modal por finalidad, todo opt-in, cookie propia, carga cada herramienta según su finalidad; la página no menciona Meta Pixel ni costo [CF-9b] | Si se adopta Zaraz como gestor de etiquetas `[VERIFICAR]` |
| CMP de terceros | No evaluados | Solo si el dueño decide adoptarlo |

Prueba (Playwright, **no instalado todavía**; A0 lo deja declarado en `bootstrap.sh` y §8.4): sin consentimiento y con "rechazar" no hay solicitudes a `facebook.com/tr` ni `connect.facebook.net`; con "aceptar" sí (ítem L-02). Punto de riesgo residual sin dueño legal: CAPI sin consentimiento (el diseño ya la evita: solo se envía con consentimiento registrado).

**Consentimiento y CAPI (críticas M11, MA-07).** `crear-sesion` guarda en la metadata `consent_marketing` (`"1"`/`"0"`), `visitor_id`, `landing_version` y `event_source_url`; `fbp`/`fbc` solo si existen (no se fabrican sin consentimiento ni se hashean). El webhook envía `Purchase` a Meta **solo si** `consent_marketing == "1"`; con `"0"` el pedido cuenta igual en Stripe, ledger y cobertura y se registra `omitido_sin_consentimiento`. `em`/`ph` se normalizan (minúsculas/trim; teléfono solo dígitos con código de país) y se hashean con SHA-256 **antes** de enviar; nunca se guardan en claro (`email_hmac` en la base con clave propia: dos columnas, dos propósitos). El agente de usuario y la IP del cliente se guardan en KV `ctx:<session_id>` con TTL corto **solo si hubo consentimiento**, se borran tras enviar y nunca van al registro, la base ni logs. Un evento con más de 6 días de antigüedad no se reenvía (`capi_vencido`: Meta rechaza `event_time` de más de 7 días y un lote con uno viejo falla entero). `[VERIFICAR]` en la documentación de parámetros de información del cliente los campos exactos recomendados.

**URLs y nombres neutros (M10).** Los Términos de las Herramientas de Empresa de Meta (https://www.facebook.com/legal/terms/businesstools, §1.h, leídos 2026-11-06) prohíben compartir por ellas información de salud, financiera u otras categorías confidenciales y piden que los nombres y criterios de eventos y audiencias no las reflejen. Para los macro-nichos *salud* y *dinero*: dominio de marca, rutas, `<title>`, `og:*` y `event_source_url` sin términos de la condición; `Purchase` lleva solo `value`, `currency`, `content_type`, `content_ids=[oferta_id]`, `num_items`, `event_id` (`content_name` y `content_category` prohibidos; lista cerrada en `tracking_plan`). Punto de riesgo residual sin dueño legal: si estos nichos admiten píxel de conversión; si no, la medición es **solo CAPI de Purchase sin Pixel ni eventos intermedios** y la conciliación sigue en Stripe.

### 7.2 Páginas legales mínimas (por oferta e idioma)

D5/X1 las generan como plantilla del sistema; infraestructura exige que existan, den 200 y estén enlazadas desde el pie y el checkout. Riesgo residual aceptado por el dueño (decisión 14): sin revisión legal humana; lo verificable lo automatiza X1 y lo fiscal lo cubre el contador.

| Página | Ruta | Nota |
|---|---|---|
| Vendedor y contacto | `/legal/vendedor` | Razón social de la LLC, dirección, correo: **marca sin cara, empresa no anónima** (05 §4.3) |
| Términos | `/legal/terminos` | Licencia de uso personal, entrega digital |
| Privacidad | `/legal/privacidad` | Contenido mínimo de 05 §4.2 |
| Reembolsos y desistimiento | `/legal/reembolsos` | Garantía de 14 días por defecto (05 §2.1) `[DUEÑO]`; UE: función de desistimiento en dos pasos desde 2026-06-19 y casillas separadas (05 §2.2) |
| Cookies | `/legal/cookies` | Enlazada desde el banner |
| Aviso de contenido | `/legal/aviso` | Informativo, sin asesoramiento médico, financiero ni de pareja: clave en los 3 nichos |
| Entrega y soporte | `/legal/entrega` | Cómo y cuándo se entrega; reenvío |

Descripción exacta, reembolso y contacto visibles son también exigencia práctica de Stripe (03 §10) y Meta (destino coherente con el anuncio, HC-21/TC-4).

---

## 8. SECRETOS

### 8.1 Reglas

1. **2FA** el que exija cada plataforma para crear credenciales, con el método que el dueño use. Stripe y Meta exigen verificación para crear credenciales [S-rak]. Dónde guarda el dueño los valores es decisión suya: el sistema no los guarda ni los ve.
2. **Ningún valor** en chats, issues, PR, logs ni repo: el repo guarda **nombres, dueño, fecha y vencimiento** (`secretos.md`, `variables-entorno.yaml`, `permisos-tokens.yaml`). Hooks `secretos` y redactor de salida (`EAA`, `sk_`, `rk_`, `whsec_`, `cfut_`) son la segunda defensa.
3. Agentes y `runner` solo tienen la clave del modelo; cada Worker y servicio, **solo los suyos** (02 §9.4).
4. Si un secreto aparece en un chat, archivo o log: **revocar y rotar de inmediato** (runbook `token-filtrado` de D0).

### 8.2 Rotación (`infra.token_alerta_dias_antes` = 14, `infra.secretos_rotacion_dias` = 90 [HIPÓTESIS])

| Secreto | Cada | Cómo | Prueba posterior |
|---|---|---|---|
| Token de usuario del sistema de Meta | 60 días si vence [M2]; 90 si no | Regenerar e invalidar el anterior | Llamada de humo + `debug_token` |
| Token CAPI por dataset | 90 | Regenerar en Administrador de eventos | Evento con `test_event_code` |
| `rk_*` de Stripe | 90 | Crear, cargar, expirar la antigua con demora de hasta 7 días [S-rak] | Los 403 siguen siendo 403 |
| `whsec_` | 90 | "Roll secret" con ventana de hasta 24 h [S-wh] | `stripe trigger` firmado |
| Tokens de Cloudflare y claves R2 | 90 | Crear, verificar con `/user/tokens/verify` [CF-7] | Despliegue y descarga de humo |
| Railway, GitHub, correo | 90 | Regenerar | Despliegue de humo / correo de prueba |
| HMAC propios (`LATIDO`, `DESCARGA`, `CATALOGO`, `PREFLIGHT`) | 180 | Dos claves vigentes durante el cambio | Prueba de firma |

### 8.3 Cargar secretos sin pegarlos en chats ni archivos

El **dueño** mueve el valor, desde donde lo guarde (decisión suya; el sistema no lo guarda ni lo ve), al panel o terminal; no pasa por una conversación con un modelo ni por un archivo.

| Destino | Procedimiento |
|---|---|
| **Cloudflare Workers** | En un terminal **propio** (no dentro de una sesión de agente): `wrangler secret put NOMBRE` (entrada interactiva) o panel del Worker; sin `.dev.vars` versionados `[VERIFICAR flags]` |
| **Railway** | Panel → servicio → Variables, pegando desde donde el dueño lo guarde; referencias entre servicios; "selladas" si existe `[VERIFICAR]`. No pasar valores en la línea de comandos (quedan en el historial) |
| **GitHub** | `gh secret set NOMBRE --env produccion` (pide el valor) o panel; solo tokens de despliegue |
| **Stripe, Meta** | Se crean en el panel; el valor se copia **una vez** al destino y a donde el dueño decida guardarlo [S-rak][M2] |
| **Ayudante opcional** | `scripts/secretos_cargar.py` (dry-run por defecto, `--live`): lee los nombres del manifiesto, pide cada valor con `getpass`, lo entrega por entrada estándar a `wrangler`/`gh`, no lo escribe en disco ni logs y registra solo nombre y hora. Lo ejecuta el dueño en su terminal |

---

### 8.4 Herramientas externas (no instaladas hoy; `bootstrap.sh` imprime cuáles faltan y no instala nada global)

| Herramienta | Uso | Estado | Nota |
|---|---|---|---|
| `wrangler` | despliegue de Workers | no instalado | `npx wrangler@<versión fijada>` |
| `stripe` (CLI) | `stripe trigger` en sandbox, captura de fixtures reales | no instalado | solo sandbox |
| `gitleaks` | CI y pre-commit | no instalado | segunda defensa mientras tanto: `scripts/lint_estatico.py` (I1) |
| Playwright | prueba L-02 de consentimiento | no instalado | entorno aparte; `[VERIFICAR]` rueda para Python 3.15 |
| Claude Code ≥ `agentes.claude_version_min` | runner desatendido | instalada 2.1.205 | actualizar antes de la prueba S-1 |

## 9. KILL SWITCH DE TRES CAPAS Y WATCHDOG

### 9.1 Capas

| Capa | Mecanismo | Quién | Latencia | Independiente de nuestro código |
|---|---|---|---|---|
| **1. `empresa/PAUSA`** | Flag; el `motor` es la fuente y lo espeja; hooks fallan cerrado; scripts lo comprueban. **No** apaga webhook, entrega ni reembolsos. Borrarlo **no reactiva** (02 §9.2). **Se escribe en tres sitios y se verifican los tres** (`infra.kill`): fila `control(pausa)` del almacén del motor, KV del watchdog (`pausa:global`) y archivo espejo; el motor corre en Railway y el dueño en otra máquina, un archivo local no basta (D-21) | Dueño, frenos, X1, watchdog vía motor | < 1 min | No |
| **2. Pausa por API de Meta** | `scripts/pausar.py`: lista campañas `ACTIVE` de `cuentas_permitidas[]` y las pone `PAUSED`; idempotente; relee; reintenta con retroceso ante error 613; ≥ 30 s por objeto; única escritura viva permitida | Motor, X1, **watchdog** | ≤ `pausa_global_max_min` (5 [HIPÓTESIS]) | Parcial |
| **3. Límite de gasto de la cuenta** | `spend_cap` fijado por el dueño [M3][HC-28] | Dueño | ~15 min en aplicarse; luego inmediato | **Sí** |
| Externo | Tarjeta virtual con tope en el emisor (el prepago de Meta anula la capa 3) | Dueño | — | Sí |

**Valor paramétrico:** `limite_gasto_cuenta_meta = gasto_acumulado + min(capital_anuncios_restante, campana.spend_cap_factor × Σ topes_de_test_en_curso)` (D0 §3.4; el factor es parámetro, nunca el literal 1,10). **Cada alta de oferta exige recalcularlo y subir el `spend_cap`** (máx. 10 cambios/día, ~15 min, solo administradores; campo del brief; lo hace el dueño). `campana.spend_cap` ≤ `perdida_max_test_por_oferta` y ≤ `gasto_total_test_por_oferta` por construcción (`total_test_max = floor(min(ambos) / spend_cap_factor)`; regla X10 del validador). Si `capital_en_riesgo_total` o los topes de test no están cargados no hay valor, M-03 es ROJO y nada se activa.

### 9.2 Watchdog tipo *dead-man switch* (Worker `watchdog`)

Objetivo: que la caída del motor no deje campañas vivas sin vigilante.

1. **Latido.** Cada `watchdog.latido_cada_min` (5 [HIPÓTESIS]) el `motor` hace `POST https://watchdog.<dominio_infra>/latido` con `{ts, estado_generado_en, semaforo, pausa, version}` firmado HMAC-SHA256 (`LATIDO_HMAC`) con tolerancia de 120 s y rechazo de repetidos. El Worker guarda `latido:ultimo` en KV.
2. **Evaluación** (cron `*/5 * * * *` UTC):
   - Si `ahora − latido:ultimo > watchdog.latido_max_min` (30 [HIPÓTESIS]) y hay campañas `ACTIVE` → **pausar todas** y alertar.
   - Si el latido declara `semaforo=ROJO`, `pausa=true` o `estado_generado_en` de más de 6 h y hay campañas activas → pausar y alertar.
   - `GASTO_DIARIO_MAX_MINOR` y `CUENTA_TZ` son **obligatorias**: sin ellas el Worker responde 503 en `/estado` y C-09 es ROJO crítico (nunca se omite la barrera independiente del motor). Compara el gasto de «hoy» —día de la zona de la cuenta, `CUENTA_TZ`, no UTC— con ese tope × 1,75 y pausa si lo excede; también `account.amount_spent` contra `LIMITE_CUENTA_MINOR` (copia en una variable del Worker), pausando al 90 %.
   - El latido incluye `ultimo_ciclo_d8_ts`, `ultimo_etl_meta_ts` y `ultimo_etl_stripe_ts` (los escribe cada ciclo **al terminar con éxito**, no el hilo del latido); si alguno supera `watchdog.ciclo_max_min` (parámetro nuevo; sin valor = ROJO en el preflight) y hay campañas `ACTIVE`, pausa. Así un D8 colgado con el latido vivo no queda sin vigilante.
   - **Nunca activa ni edita presupuestos**: solo `GET campaigns?effective_status` y `POST /<id> status=PAUSED`, sobre IDs de `CUENTAS_PERMITIDAS`.
3. **Supervisión mutua.** Escribe `watchdog:visto` en cada ejecución; C-09 exige ≤ 10 min y el `motor` lo consulta con un `GET /estado` firmado: si el watchdog muere, el motor lo ve, y viceversa.
4. **Alertas** por dos canales independientes: correo (clave solo de enviar) y push a un servicio ajeno a Railway y Cloudflare `[VERIFICAR proveedor]`, con reintento hasta confirmar.
5. **Reanuda solo el dueño**, revalidando hashes, límites y preflight.
6. **Credenciales:** `META_TOKEN_PAUSA`, `LATIDO_HMAC`, claves de alerta. Sin acceso a Stripe, R2 ni datos de clientes.
7. **Costos:** 288 ejecuciones/día, ≤ 576 escrituras KV/día entre latido y visto (la cuota Free de 1.000 queda justa: se usa Workers Paid).

**Matriz de fallos (pruebas de B8, M13).** Meta API caída: tras 3 fallos de `pausar` → alerta crítica con instrucciones manuales y se marca `PAUSA` igual. Token revocado: M-01 ROJO y alerta (el Worker no puede pausar: queda la capa 3). Watchdog muerto: el motor lo ve (`watchdog:visto`) y ejecuta `pausar` él mismo. Un canal de alertas caído: reintento por el otro y, tras 3 fallos, pausa. Reanudar siempre exige firma, preflight y hashes.

**Qué cubre y qué no.** Cubre caída del motor, scheduler bloqueado y despliegues defectuosos. **No** cubre gasto excesivo con el motor sano (lo hacen topes duros y capa 3), token de Meta revocado (el Worker no podría pausar: lo detectan M-01 y C-09, y la capa 3 sigue vigente) ni falla simultánea de Cloudflare y Railway (capa 3 y runbook manual en Ads Manager). Peor caso: `latido_max_min` + 5 min de cron + propagación ≈ 35–40 min `[HIPÓTESIS]`; si el tope diario no tolera esa exposición se baja `latido_max_min` (≥ 10) o el tope.

### 9.3 Pruebas de aceptación

Antes de la **primera activación real** y luego mensualmente. No gastan: usan campañas de prueba **sin anuncios**, que pueden quedar `ACTIVE` sin entrega ("sin anuncios", [H4]) `[VERIFICAR]` en la cuenta.

| ID | Prueba | Aprobado si | Evidencia |
|---|---|---|---|
| A-1 | Crear `empresa/PAUSA` e intentar una escritura live sintética | Se deniega; la lectura sigue | Registro del hook |
| A-2 | Borrar `PAUSA` | Nada se reactiva; el motor exige orden humana | Estado en Meta |
| A-3 | `pausar.py` en seco con 2 campañas de prueba `ACTIVE` | Lista exactamente esas 2 | Salida |
| A-4 | `pausar.py --live` | Ambas `PAUSED` en ≤ `pausa_global_max_min`; relectura confirma | Bitácora de Meta |
| A-5 | Detener el latido (simulado) con 1 campaña de prueba `ACTIVE` | Pausada y alerta en **ambos** canales en ≤ `latido_max_min` + 10 min | Alertas + bitácora |
| A-6 | Intentar ordenar al watchdog activar o editar | No existe la ruta (404/405) | Prueba unitaria |
| A-7 | Con `spend_cap` apenas sobre `amount_spent`, intentar cambiarlo con el token del **operador** | Falla por permisos | Respuesta de la API |
| A-8 | Token de lectura intenta `POST`; `capi` intenta listar campañas; `rk_lectura` intenta escribir | Todo rechazado | Respuestas 4xx/403 |
| A-9 | Crear en `PAUSED` y en borrador por MCP; publicar con `publish_as_active=false` | Estado resultante documentado; si deja ACTIVO se agrega pausa inmediata | Prueba M8 de D0 |
| A-10 | Motor detenido 35 min con 1 campaña de prueba `ACTIVE` | Pausa + alerta; el preflight pasa a ROJO | Registro |
| A-11 | Deshabilitar el cron del Worker | El motor marca ROJO y alerta en ≤ 15 min | Registro |
| A-12 | Reanudar tras A-10 | Solo con orden firmada, preflight VERDE y hashes válidos | Registro encadenado |

---

## 10. DISEÑO DE `scripts/preflight.py`

Lo programa otro agente; esto es el contrato. Convenciones: `python -m scripts.preflight`; dinero en enteros; tiempo UTC con `Z`; pruebas sin red, con fixtures. **Catálogo normativo de ítems:** `infra/plantillas/preflight-items.yaml` (43 ítems con sonda, criterios VERDE/AMARILLO/ROJO y si es crítico o corre en modo ligero).

### 10.1 Principios

1. **Solo lectura**: ninguna llamada modifica algo. Lo que sí tiene efecto (evento de prueba, correo, compra) es el modo `e2e_prueba`, con `--live` y `test_event_code`.
2. **Fallar cerrado**: sonda no ejecutable (sin credencial, red o timeout) = ROJO si es crítica, AMARILLO si no; nunca VERDE por ausencia.
3. **Sin límites no hay VERDE**: si falta un campo requerido de `limites.yaml`, P-01 es ROJO (así se difiere la pérdida máxima sin riesgo).
4. **Modo simulado** (por defecto sin credenciales): usa fixtures y escribe `modo: "simulado"`; los hooks lo rechazan.
5. Credenciales solo por variables de entorno; la salida pasa por el redactor; la evidencia guarda hashes, IDs y números, nunca valores.
6. Las sondas críticas tienen implementación propia del QA (D0 §6).

### 10.2 Qué comprueba cada conexión (resumen; criterios completos en el YAML)

| Bloque | Ítems | Comprobaciones principales | ROJO típico |
|---|---|---|---|
| Meta | M-01…M-10 | `debug_token` y scopes; estado, moneda y zona de la cuenta; `spend_cap`; página; datasets (eventos, EMQ); dominio; DSA si hay UE; bitácora vs `registro.jsonl`; errores de entrega | `account_status≠1`, scope de más, `spend_cap=0`, falta DSA con UE |
| Stripe | S-01…S-08 | clave de lectura; cuenta habilitada; destinos con eventos exactos; huecos 24 h; `Price` vs `checkout.json`; coherencia de modo; ratio de disputas; descriptor | evento faltante, hueco de eventos, ratio ≥ pausa |
| Cloudflare | C-01…C-09 | tokens; Workers vs commit; rutas y cron; DNS (SPF/DKIM/DMARC/TXT Meta); TLS y vencimientos; R2 privado; humo HTTP; webhook rechaza firma inválida; watchdog vivo | firma inválida aceptada, R2 público, watchdog mudo |
| Railway | R-01…R-05 | servicios (motor con 1 réplica); respaldos < 26 h; base; ETL; variables por nombre | motor con ≠ 1 réplica, sin respaldo |
| GitHub | G-01…G-03 | repo privado y reglas; hashes firmados; `gitleaks` | repo público, hash distinto |
| Correo | E-01, E-02 | dominios verificados; rebotes y quejas | dominio no verificado |
| Legal | L-01, L-02 | páginas legales con hash sellado; consentimiento sin solicitudes a Meta | píxel dispara sin consentir |
| Seguridad y control | K-01…K-03, P-01 | `PAUSA` ausente; vencimientos; simulacro; `limites.yaml` completo y firmado | PAUSA presente, secreto vencido |

**Global:** ROJO si algún crítico es ROJO o falta un bloque; AMARILLO si hay AMARILLOS o ROJO no crítico; **VERDE solo si todos los críticos están en VERDE con medición vigente.**

### 10.3 Modos y consecuencias

| Modo | Cuándo | Qué corre |
|---|---|---|
| `completo` | Diario (`infra.hc_hora_diaria`, 06:00 UTC), antes de cada activación y tras cada despliegue | Todos |
| `ligero` | Cada `infra.hc_sonda_ligera_min` (15) **solo con campañas activas** | M-01, M-02, M-03, S-01, S-03, S-04, C-08, C-09, K-01, P-01; **no extiende** la vigencia de lo no remedido |
| `e2e_prueba` | Antes del primer lanzamiento y tras cambios de infraestructura | Clic con UTM → sesión de prueba → webhook firmado → correo de prueba → enlace → evento con `test_event_code`; no habilita nada por sí solo |

**Consecuencias:** ROJO crítico sin campañas activas → no se activa; con campañas activas → tras `infra.hc_reintentos_antes_de_pausa` (2) fallos consecutivos (inmediato en M-02, M-03, K-01, P-01) se crea `PAUSA`, corre `pausar.py` y se alerta.

### 10.4 Formato de `empresa/infra/estado.json`

Contrato en `contratos/infra_estado.schema.json`; ejemplo en `infra/plantillas/estado.ejemplo.json`. Campos (esquema 1.1.0, docs/06 D-07): `schema_version`, `modo` (`vivo|prueba|simulado`; ausente = no vivo), `semaforo`, `generado_en`, `valido_hasta`, `commit`, `hash_scripts`, `items[]` (`id`, `bloque`, `critico`, `estado`, `mensaje`, `evidencia`, `medido_en`, `expira_en`, `latencia_ms`), `resumen` y `firma`.

- **Antigüedad máxima 6 horas** (backbone §5.6): `valido_hasta = generado_en + min(infra.hc_preflight_vigencia_horas, 6) h`. Hooks y scripts calculan la edad con **su propio reloj** a partir de `generado_en`; no confían en `valido_hasta` ni en la fecha del archivo.
- **Firma:** HMAC-SHA256 sobre el JSON canónico (claves ordenadas, sin `firma`) con `PREFLIGHT_HMAC_KEY`, presente solo en el job del preflight y en quienes verifican (motor, hook), **nunca en los `runner`**. Quien tiene la clave podría falsificar: por eso no se comparte con agentes.
- **Estados de ítem:** `VERDE`, `AMARILLO`, `ROJO`, `PENDIENTE_EXTERNO` (a cargo del dueño; no verde para críticos).
- Escritura atómica; los agentes no pueden escribirlo (`deny` + hook). **Salida** (convenciones §8; docs/06 D-08): 0 VERDE · 4 AMARILLO o ROJO (no habilita gasto; el semáforo va en `estado.json` y en stdout) · 3 entradas o esquemas inválidos · 2 uso · 1 error interno (cuenta como ROJO).
- Registro de verificaciones manuales: `infra/plantillas/registro-verificacion-conexiones.yaml`.

---

## 11. COSTOS MENSUALES ESTIMADOS (USD)

| Concepto | Plan | USD/mes | Nota |
|---|---|---|---|
| Cloudflare Workers | Paid | **5** | 10 M solicitudes, KV, 250 crons [CF-4] |
| Pages, DNS, R2 | Free / gratuito | 0–1 | R2: 10 GB gratis [CF-6] |
| Dominios | Cloudflare Registrar | ~1 por dominio | ≈ 10–15 USD/año por TLD `[VERIFICAR]` |
| Railway | Hobby (5 con 5 de uso) | **10–20** | `motor`+`etl`+`api`+Postgres a 0,25–0,5 GB y 0,1–0,25 vCPU [RW-3] `[HIPÓTESIS]`; Pro 20 si hace falta equipo |
| GitHub | Team, 1 usuario | **4** | Privado con reglas y secretos de entorno [GH-2] |
| Correo | Resend Free → Pro | 0 → 20 | Pro desde la 4.ª oferta con dominio o 100 correos/día [EM-1] |
| Alertas push y respaldo | — | 0–1 | `[VERIFICAR]` |
| **Subtotal fijo** | | **≈ 20–51** | Coherente con 25–80 de 02 §12 |

**No incluido:** Stripe (2,9 % + 0,30 USD por tarjeta doméstica de EE. UU., 03 §4), gasto en Meta (topes en `limites.yaml`), créditos de IA y Higgsfield, plan de Claude, Radar, Stripe Tax, contador y mantenimiento de la LLC `[VERIFICAR con el contador]`.

---

## 12. QUIÉN HACE QUÉ, ORDEN, TIEMPOS, RIESGOS

### 12.1 Dueño vs sistema

| Bloque | **Dueño** (no delegable) | **Sistema** |
|---|---|---|
| Meta | Diagnóstico y decisión de la cuenta; portfolio, verificación, pago, página, app y usuarios; generar tokens; `spend_cap` y DSA; crear datasets | `meta.yaml`, validador de nombres/UTM, TXT de dominio, lecturas, borradores `PAUSED`, preflight |
| Stripe | Claves restringidas, destinos, descriptor, activar vivo, compra real mínima | Catálogo en prueba, Workers de sesión y webhook, `stripe trigger`, conciliación, preflight |
| Cloudflare | Cuenta (con el 2FA que exija), dominios, tokens, cargar secretos de Workers | Workers, rutas, cron, DNS con `cf_dns`, despliegues `--live` |
| Railway | Cuenta, plan, variables, dominio de `api` | Servicios, cron, `pg_dump`, migraciones |
| GitHub | Organización, reglas, entornos, secretos de despliegue | CI, flujos, `gitleaks` |
| Correo y legales | Cuenta, API key, buzón; gate H de publicar (sin revisión legal humana: decisión 14) | DNS, plantillas, páginas, banner, pruebas |
| Secretos | Carga de valores (desde donde el dueño los guarde) | Manifiesto de nombres, redactor, hooks, avisos |
| Kill switch | Capa 3, simulacro firmado, reanudación | Capas 1 y 2, watchdog, A-1…A-12 |

### 12.2 Orden recomendado y tiempos

Horas del dueño `[HIPÓTESIS]`; esperas externas `[VERIFICAR]`.

| # | Paso | Habilita | Depende de | Horas | Espera | Se comprueba con |
|---|---|---|---|---|---|---|
| 1 | Diagnóstico de cuenta y píxel (1.2); apelación si corresponde | Camino de Meta | — | 1–2 | ~48 h típico [HC-24] | `meta.yaml` |
| 1b | **Decidir moneda y zona horaria de la cuenta de Meta, primer mercado y primer idioma** (la moneda y la zona son irreversibles, M-D). Recomendación por defecto `[HIPÓTESIS]`: moneda de la cuenta = moneda de liquidación de Stripe (USD) y zona fija anotada en `meta.yaml`; si el primer mercado cobra en otra moneda, `economia` registra `conversion_bp` y un `tipo_cambio`. **Generar con el sistema (D5/X1) las plantillas de las siete páginas en cuanto se elige el mercado**, no en el paso 12 | Paso 8, páginas legales, `moneda_limites` | — | 0,5 | — | `meta.yaml`, `limites.yaml` |
| 2 | GitHub (organización Team) y repo con reglas | CI | — | 1 | — | G-01 |
| 3 | Cloudflare: cuenta, `cf_lectura`, primer dominio | DNS, Workers | — | 1 | DNS | C-05 |
| 4 | Portfolio y verificación del negocio de la LLC | Cuenta, dominio | 1 | 2–3 | **Días** (guías secundarias: 1–5 hábiles) [H2] | Centro de seguridad |
| 5 | Railway en `pruebas` | Preflight, ETL | 2 | 1–2 | — | R-01, R-03 |
| 6 | Stripe en **prueba**: claves, destinos, catálogo, descriptor | Checkout | — | 2 | — | S-01, S-03 |
| 7 | Correo: dominio y DNS | Entrega | 3, 6 | 1 | Verificación | E-01 |
| 8 | Meta: cuenta, pago con tope, página, app, operador | Borradores | 4 | 2 | — | M-02, M-04 |
| 9 | Dataset, dominio verificado, token CAPI | Medición | 3, 8 | 1–2 | — | M-05, M-06 |
| 10 | DSA y `spend_cap` | Candado externo | 8, `limites.yaml` | 0,5 | ~15 min | M-03, M-07 |
| 11 | Workers y secretos cargados | Embudo y vigilancia | 3, 6, 7, 9 | 2 | — | C-02, C-08, C-09 |
| 12 | Legales, banner, prueba Playwright | Landing publicable | 3, 11 | 2–4 | — | L-01, L-02 |
| 13 | `e2e_prueba` y **compra manual de prueba** | Embudo probado | 11, 12 | 1 | — | Informe |
| 14 | Kill switch A-1…A-12 | Permiso de activar | 5, 10, 11 | 2 | — | Tabla 9.3 |
| 15 | Stripe a **vivo** y **compra real mínima con reembolso** (gate H) | Cobrar | 13, 14 | 1 | Primer pago 7–14 días [03 S40] | S-02 |
| 16 | Preflight completo VERDE y firma "infra verde" | Primer testeo | todo | 0,5 | — | `estado.json` |
| 17 | Solicitar nivel *Full* y separar usuarios | N3 | 16 + 15 días | 1 | 15 días [M1] | M-08 |

**Ruta crítica:** 1 → 4 → 8 → 9 → 10 → 14 → 15 → 16. Trabajo activo del dueño ≈ 23–33 h repartidas en 2–4 semanas; primer testeo en vivo realista a las **3–4 semanas** `[HIPÓTESIS]`.

### 12.3 Riesgos y alternativas

| # | Riesgo | Señal | Mitigación | Alternativa |
|---|---|---|---|---|
| 1 | Verificación de negocio rechazada | "Se necesita más información" [H2] | Documentos oficiales con nombre exacto; traducción oficial | Otro tipo de documento admitido |
| 2 | Cuenta nueva con límite diario bajo (HC-29) | Límite < presupuesto | Test pequeño; esperar historial | — |
| 3 | Fuga de un token de Meta | Cambios en la bitácora | Alcance mínimo, vencimiento de 60 días, `spend_cap` | Revocar y regenerar |
| 4 | El operador puede cambiar `spend_cap` | Falla A-7 | Reasignar activos y roles | Tarjeta con tope en el emisor |
| 5 | Cron de Cloudflare retrasado o caído | `watchdog:visto` viejo | Supervisión mutua | Observador de solo lectura en Actions que alerta |
| 6 | Railway caído | Latido ausente | Cloudflare sigue entregando; watchdog pausa | Respaldo en R2 y `etl` en otro proveedor `[VERIFICAR]` |
| 7 | Webhook sin entregar | Huecos S-04 | Reintentos de 3 días; reenvío 15/30 días | `stripe events resend` |
| 8 | Suspensión de Stripe | Pagos retenidos, requisitos vencidos | Descriptor, garantía, ratios | Procesador secundario declarado |
| 9 | Cuarta oferta supera los 3 dominios de Resend Free | Error al agregar dominio | Pasar a Pro | Subdominio compartido de la marca paraguas |
| 10 | Rotación olvidada | K-02 amarillo | Alertas a 14 días | — |
| 11 | CAPI sin consentimiento en UE | L-02 | Banner propio y chequeo automático de X1 (L-02) | Solo eventos con consentimiento registrado |
| 12 | Decisiones irreversibles en Meta | — | Tabla 1.2 y firma del dueño | — |

---

## 13. CHECKLIST FINAL IMPRIMIBLE: LISTO PARA EL PRIMER TESTEO EN VIVO

Marcar solo con evidencia guardada en `empresa/infra/`. Un ítem sin marcar significa que **no se activa**.

**A. Personas y acceso**
- [ ] 2FA activo, con el método que el dueño use, donde la plataforma lo exija (Meta, Stripe, Cloudflare, Railway, GitHub, correo, proveedor de correo).
- [ ] Ningún secreto en chats, repo ni logs (`gitleaks` en 0).

**B. Meta**
- [ ] Diagnóstico de la cuenta deshabilitada y decisión en `meta.yaml`; píxel viejo desasignado.
- [ ] Portfolio de la LLC con negocio **verificado**.
- [ ] UNA cuenta publicitaria `ACTIVE`, moneda y zona correctas, tarjeta con tope (no prepago), ID en `cuentas_permitidas`.
- [ ] Fan page publicada y asignada.
- [ ] Dataset `DS_<oferta_id>`, dominio verificado, token CAPI y evento de prueba recibido.
- [ ] DSA por defecto fijado si se segmenta a la UE.
- [ ] `spend_cap` fijado por el dueño y ≤ `limite_gasto_cuenta_meta`; **A-7 aprobada: sin A-7 NO se activa** (es una puerta, no una prueba opcional). Si el operador puede cambiar `spend_cap`, la capa 3 pasa a ser el límite de la **tarjeta virtual** del emisor (obligatoria) y el watchdog usa un token propio de un segundo usuario del sistema si el portfolio lo permite (`GET /me/system_users` en D0); `debug_token` cada 24 h con alerta ante cambio de `scopes`.
- [ ] Tokens con alcance mínimo; A-8 aprobada; A-9 documentada.

**C. Stripe**
- [ ] Claves restringidas por función (sin `sk_`); 403 esperados confirmados.
- [ ] Destinos de prueba y vivo con los eventos exactos de 2.3; `whsec_` cargados por el dueño.
- [ ] Catálogo con `lookup_key` y precio/moneda = `checkout.json`; descriptor configurado.
- [ ] Compra manual de prueba aprobada; **compra real mínima con reembolso** hecha y firmada.

**D. Cloudflare, Railway, GitHub**
- [ ] Zona con TLS vigente y DNSSEC; Pages desplegado; rutas de Workers por zona.
- [ ] Workers con el hash esperado; R2 privado (sin firma = 403).
- [ ] Railway: `motor` con 1 réplica, `etl`, `api`, Postgres; respaldo de Railway y `pg_dump` en R2 con **restauración probada**.
- [ ] Repo privado, reglas de `main`, CI verde, despliegues manuales.

**E. Correo y legales**
- [ ] SPF, DKIM y DMARC en `pass` en Gmail y Outlook; el buzón de soporte recibe.
- [ ] Siete páginas legales publicadas y enlazadas; banner de consentimiento; prueba de Playwright aprobada.

**F. Kill switch y control**
- [ ] `PAUSA`, `pausar.py` y watchdog desplegados; **A-1…A-12 aprobadas** y firmadas.
- [ ] Las alertas llegan por dos canales independientes.
- [ ] `limites.yaml` cargado y firmado; el sistema se niega a gastar si falta cualquier campo.
- [ ] `parametros.yaml` con umbrales (`[HIPÓTESIS]` marcados).

**G. Estado final**
- [ ] `scripts/preflight.py --modo completo` en **VERDE**, firmado, con menos de 6 h.
- [ ] Gate H de "infra verde" firmado por el dueño.
- [ ] Próximos vencimientos y primer simulacro mensual anotados.

---

## 14. HALLAZGOS CRÍTICOS Y PENDIENTES

**Hallazgos críticos**

1. *Limited* permite 1 usuario del sistema + 1 admin; *Full* (10 + 1) exige ≥ 500 llamadas en 15 días con < 15 % de error [M1]. El reparto operador/lectura/pausa/CAPI no cabe en Limited: hay un escalón planificado y una Fase 1 con menor aislamiento.
2. Meta no documenta un alcance "solo pausa", y la documentación no nombra el rol que puede cambiar `spend_cap` [M3]: la prueba A-7 decide si la capa 3 es de verdad independiente.
3. Portfolio nuevo = 1 cuenta publicitaria (3 tras entregar y pagar); cuentas y datasets no se borran ni se transfieren [H3][H5]: la decisión sobre la cuenta deshabilitada es irreversible en sus consecuencias.
4. GitHub: los aprobadores de despliegue no figuran para repos privados [GH-2]; el gate humano es la firma del dueño.
5. Las URL firmadas de R2 no limitan descargas ni sirven en dominios propios [CF-2]: el diseño usa un Worker con *binding*.
6. Sin `limites.yaml` completo no hay VERDE: es lo que permite diferir la pérdida máxima por oferta sin riesgo (P-01, M-03).
7. Resend Free (3 dominios, 100/día) obliga a pagar al llegar a la 4.ª oferta con dominio propio [EM-1].
8. DSA: con segmentación a la UE y sin `default_dsa_*` **no se puede publicar** [H1].

**Pendientes `[VERIFICAR]`**

- **Meta:** roles para `spend_cap`; si "Generar token" crea un usuario que cuenta contra el límite; modo de la app; permisos de página requeridos; publicar un borrador ¿ACTIVO o PAUSADO?; campaña sin anuncios `ACTIVE` para pruebas; macros en `link_url`; si las lecturas cuentan para pasar a Full.
- **Stripe:** nombres exactos de recursos y mínimo de cada clave (403 en sandbox); caracteres de `lookup_key`; versión de API; formato *snapshot* de cada evento; términos sobre cuentas múltiples.
- **Cloudflare:** nombres de permisos de tokens, flags de `wrangler secret put`, reintento de crons, límites de reglas de tasa en Free, reenvío de correo.
- **Railway:** respaldo de Postgres, tokens de lectura, región, variables selladas. **GitHub:** Pro personal vs Team; escaneo nativo en privados.
- Proveedor de alertas push; precio por TLD; todo lo fiscal por país (contador); lo de consumo por país queda como riesgo residual aceptado (decisión 14).

---

## 15. FUENTES

**Verificadas hoy (2026-11-06):**

| Clave | URL |
|---|---|
| M1 | https://developers.facebook.com/docs/marketing-api/overview/authorization |
| M2 | https://developers.facebook.com/docs/marketing-api/system-users/install-apps-and-generate-tokens |
| M3 | https://developers.facebook.com/docs/marketing-api/reference/ad-account |
| M4 | https://developers.facebook.com/docs/marketing-api/system-users |
| M5 | https://developers.facebook.com/docs/marketing-api/conversions-api/get-started |
| H1 | https://www.facebook.com/business/help/605021638170961 |
| H2 | https://www.facebook.com/business/help/159334372093366 |
| H3 | https://www.facebook.com/business/help/915885887059947 |
| H4 | https://www.facebook.com/business/help/652738434773716 |
| H5 | https://www.facebook.com/business/help/314143995668266 |
| H6 | https://www.facebook.com/business/help/563249781254715 |
| S-rak | https://docs.stripe.com/keys/restricted-api-keys |
| S-wh | https://docs.stripe.com/webhooks |
| S-desc | https://docs.stripe.com/get-started/account/statement-descriptors |
| S-cs | https://docs.stripe.com/api/checkout/sessions/create |
| CF-1 | https://developers.cloudflare.com/workers/configuration/cron-triggers/ |
| CF-2 | https://developers.cloudflare.com/r2/api/s3/presigned-urls/ |
| CF-3 | https://developers.cloudflare.com/pages/platform/limits/ |
| CF-4 | https://developers.cloudflare.com/workers/platform/pricing/ |
| CF-5 | https://developers.cloudflare.com/workers/platform/limits/ |
| CF-6 | https://developers.cloudflare.com/r2/pricing/ |
| CF-7 | https://developers.cloudflare.com/fundamentals/api/get-started/create-token/ |
| CF-8 | https://developers.cloudflare.com/kv/platform/pricing/ |
| CF-9 | https://developers.cloudflare.com/registrar/ |
| CF-9b | https://developers.cloudflare.com/zaraz/consent-management/ |
| CF-10 | https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/ |
| CF-11 | https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/ |
| RW-1 | https://docs.railway.com/reference/cron-jobs |
| RW-2 | https://docs.railway.com/reference/backups |
| RW-3 | https://docs.railway.com/reference/pricing/plans |
| RW-4 | https://docs.railway.com/reference/private-networking |
| GH-1 | https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment |
| GH-2 | https://github.com/pricing |
| GH-4 | https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows |
| EM-1 | https://resend.com/pricing |
| EM-2 | https://postmarkapp.com/pricing |
| EM-3 | https://aws.amazon.com/ses/pricing/ |
| EM-4 | https://resend.com/docs/dashboard/domains/introduction |

**Leídas en `docs/_investigacion/` el 2026-11-05:** `04-meta-ads.md` (HC-3, HC-15, HC-16, HC-21, HC-24, HC-25, HC-26, HC-28, HC-29, HC-36, DV-2, DV-7, TC-4), `03-stripe.md`, `05-legal.md`, `02-conectores.md`, `13-playbook-operacion-stack-riesgos.md` y `departamentos/01-fundaciones-infra.md`.

**Límites del método:** las páginas se leyeron con una herramienta que resume con un modelo auxiliar; para cifras críticas (límites de tasa, precios) conviene releer la fuente antes de codificarlas. No se ejecutó ninguna acción con efecto externo.
