# Tracking: eventos, `event_id`, consentimiento y datos neutros

> v0.2 sin pulir (borrador generado desde la spec y revisado el 2026-11-07; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).
> Backbone 5.3 + spec D5 §4.2 + `docs/06` §4.3 + `docs/07` §7.1. El Maker escribe `tracking.json` (esquema `tracking_plan` 1.1.0; ejemplo `ofertas/_ejemplo/05-landing/tracking.json`); los Workers lo ejecutan. D5 es la **columna vertebral de medición**: si pierde un `adid` o un `event_id`, D7, D8, F1 y F2 deciden con datos falsos. Hechos de Meta no releídos hoy: `[VERIFICAR]` en https://developers.facebook.com/docs/marketing-api/conversions-api (deduplicación por `event_name` + `event_id`).

## 1. Cadena de medición

| Tramo | Qué ocurre | Quién | Falla = |
|---|---|---|---|
| Anuncio → landing | la URL del anuncio lleva `utm_*`, `oferta_id`, `cid`, `asid`, `adid` (macros de Meta; inmutables tras publicar) | D7 | C06 |
| Primer hit | se capturan los parámetros **antes de cualquier redirección**; `www` → apex conserva la consulta; `fbclid` → `fbc`; `_fbp`; `locale`; cookie de primera parte; `visitor_id` = cookie `fab_vid` (128 bits) y parámetros en `fab_attr`, que escribe `consentimiento.js` solo tras el consentimiento de marketing y lee el Worker (decisión de arranque de pago; formato en `landing/PROCESO.md` §5); sin consentimiento, `visitor_id` aleatorio sin cookie y sin atribución | Worker / landing | C06 (SD5-07) |
| `/comprar` → sesión | el formulario de `/comprar` hace POST a `/api/sesion` (campos cerrados `oferta_id`, `locale`, `bump`, `renuncia_desistimiento`); `crear-sesion` crea la Checkout Session con `client_reference_id = visitor_id` y `metadata = checkout.metadata_esquema`; acepta `adid` solo si figura en el catálogo firmado (si no, `desconocido`) | Worker | C06, C14 |
| Compra | webhook firmado → `fulfill`; `Purchase` por API de Conversiones solo con `consent_marketing="1"` | Workers | C07, C09 |
| Conciliación | `datos` compara Meta ÷ Stripe (rango 0,8–1,3) y cobertura de `adid` ≥ `landing.captura_adid_min_pct` | F1 / datos | alerta |

## 2. Eventos (lista cerrada) y `event_id`

| Evento | Canal | `event_id_regla` | Cuándo | Parámetros permitidos |
|---|---|---|---|---|
| `PageView` | pixel (+ `/api/ev` propio) | `pv_<visitor_id>_<ts>` | carga de la landing, solo tras consentimiento | `fbp`, `fbc` |
| `ViewContent` | pixel | `vc_<visitor_id>_<ts>` | S01 visible | `content_ids`, `value`, `currency` |
| `InitiateCheckout` | **ambos** | `ic_<visitor_id>_<ts>` | al invocar `crear-sesion` (el `ts` lo genera el navegador y viaja a la API para que sea idéntico) | `value`, `currency` |
| `Purchase` | **ambos** | `purchase_<checkout_session_id>` | API desde el webhook; píxel en `/gracias` solo si el servidor confirma `paid` | `value` (neto de impuestos, moneda de la sesión), `currency`, `content_type`, `content_ids=[oferta_id]`, `num_items` |

Reglas: **el mismo `event_id` en navegador y servidor** (si difieren, Meta cuenta dos: SD5-02); `Purchase` con `unpaid` no genera evento ni entrega (SD5-11, SD5-12); **nunca** `content_name` ni `content_category`; email con SHA-256 normalizado (minúsculas, sin espacios) antes de enviar y nunca en claro; IP y user-agent solo con consentimiento y TTL corto; eventos de más de 6 días no se reenvían. Lista cerrada de parámetros: `fbp, fbc, value, currency, content_ids, content_type, num_items, event_id`.

## 3. Consentimiento antes del píxel

| Pieza | Regla |
|---|---|
| `js/consentimiento.js` | **único `<script>` del HTML**; construye el banner (Aceptar, Rechazar y Personalizar con el mismo peso; marketing apagado; cookie propia `fabrica_consent` con versión y fecha del texto) |
| `js/pixel.js` | no se enlaza nunca desde el HTML; solo `consentimiento.js` lo inyecta tras aceptar marketing y él mismo vuelve a comprobar el consentimiento |
| `tracking.json#consent_gating` | `plataforma: banner_propio_v1`, `requerido_ue_uk: true`, `tolerar_trafico_sin_consentimiento: true` (Stripe sigue siendo la verdad de ingresos) |
| CSP (`sitio/_headers`) | una sola política canónica, `landing.comun.CSP_CANONICA` (LT-38b): `script-src 'self' https://connect.facebook.net`, `connect-src 'self' https://www.facebook.com https://connect.facebook.net`, `img-src 'self' data: https://www.facebook.com`, `frame-src https://www.facebook.com https://connect.facebook.net`, `form-action 'self' https://checkout.stripe.com`; la verifica `L1-CSP`. La CSP solo permite `fbevents.js`; lo carga `pixel.js` tras el consentimiento. `[VERIFICAR con el píxel real: consola y Meta Pixel Helper]` |
| Uniformidad | el **mismo banner y el mismo texto en todos los países y agentes** (sin geolocalización): K03/C17 |
| Prueba (C10) | con «Rechazar» o sin elegir no hay solicitudes a `facebook.com/tr` ni `connect.facebook.net`; con «Aceptar» sí (Playwright `[PENDIENTE: no instalado]`) |
| `/api/ev` | solo si el banner permite analítica `[SUPUESTO]` |

Si el dueño decide que el píxel no es admisible en salud o dinero (`preguntas-abiertas.md`), `tracking.json` deja `PageView`/`ViewContent` fuera, `InitiateCheckout` y `Purchase` con `canal: api` y no se genera `pixel.js`.

## 4. Sin datos de salud, deuda, ruptura ni ingresos (C16)
Lista cerrada de parámetros de evento; ninguna de estas cadenas contiene términos de `terminos_sensibles/<locale>.yaml` `[PENDIENTE: X1]` (mínimo hoy: `scripts/validar_esquemas.TERMINOS_SENSIBLES`): URL y rutas, dominio, `<title>`, `og:*`, `alt`, `event_source_url` (≤ 500 caracteres), nombres y parámetros de eventos, descriptor, ítem del recibo, asuntos y remitentes de correo, nombres de los `price_id` visibles. Sin quizzes con puntaje ni formularios de condición; ninguna lista de compradores se sube a plataformas. `tracking.json#datos_sensibles.permitidos = false`.

## 5. Entornos
Preview y modo test **nunca** envían al dataset de producción (`modo_prueba: true`, `test_event_code`); la compra real mínima va con `verificacion=1` y `datos`/F1 la excluyen. Un dataset y una verificación de dominio **por oferta**.

## 6. Qué escribe el Maker y qué no
Escribe `tracking.json` completo y válido (`pixel_id`, `dataset_id`, `dominio_verificado`, `eventos[]`, `utm_esquema.plantilla` idéntica a la de D7, `consent_gating`, `emq_objetivo` ≥ `landing.emq_min_purchase`, `modo_prueba`, `datos_sensibles`). **No** escribe ni lee tokens de la API, no envía eventos y no toca los Workers. El Maker no tiene web ni `mcp__*`: las lecturas de Meta (`ads_get_datasets`, `ads_get_dataset_stats`, `ads_pixel_event_read`) solo existen en la sesión interactiva del dueño hasta N2 (después, un script con token de lectura) y llegan como entrada. `[VERIFICAR]` `agentes/hooks/herramientas.yaml` clasifica `mcp__*__ads_pixel_*` como escritura: otra razón para que `ads_pixel_event_read` quede fuera del Maker.
