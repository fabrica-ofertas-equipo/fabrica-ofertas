# Stripe Checkout y bump: cómo se conecta la landing y qué debe coincidir

> v0.2.0 sin pulir (precio de la escalera J16 y precio programado añadidos el 2026-11-07; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).
> El código que mueve dinero **no vive en la skill** (`tracking/workers/crear-sesion`, `webhook-stripe`, `capi`, `eventos`; `postcompra/`; `landing.*`). El Maker aporta **configuración** (`checkout.json`) y contenido. Cambiar ese código exige gate H. Los hechos de Stripe marcados `[VERIFICAR]` no se releyeron hoy en la documentación oficial: https://docs.stripe.com/payments/checkout, https://docs.stripe.com/testing.

## 1. Flujo

`CTA` → **`/comprar`** (página **estática** con el resumen antes de pagar y UN formulario `<form method="post" action="/api/sesion">`) → `POST /api/sesion` con los campos cerrados `oferta_id`, `locale`, `bump` (solo con `oferta_previa`) y `renuncia_desistimiento` (solo UE/UK), más las cookies del mismo origen `fab_vid` (`visitor_id`), `fab_attr` (`cid`, `asid`, `adid`, `utm_*`, `fbclid`), `_fbp` y `_fbc`, que `consentimiento.js` escribe solo tras el consentimiento de marketing → Worker **`crear-sesion`** valida (mismo origen, límite de tasa del WAF; Turnstile fuera de v1), toma el precio **solo del catálogo firmado** y crea la sesión → **303** a la URL de Stripe (la CSP lleva `form-action 'self' https://checkout.stripe.com`; el modo JSON queda para pruebas) → **Stripe Checkout alojado** (`ui_mode: hosted`; `embedded` o `custom` solo tras prueba en sandbox) → `success_url` = `/gracias` (muestra la entrega solo si el servidor confirma `payment_status=paid`) → webhook firmado → `fulfill` (D10) → correo con `/descarga/<token>` → URL firmada de R2.

## 2. `checkout.json` (esquema `checkout` 1.2.0; ejemplo: `ofertas/_ejemplo/05-landing/checkout.json`)

| Campo | De dónde sale | Regla |
|---|---|---|
| `moneda`, `precio` | `oferta.moneda`, `oferta.precio.lista` | iguales a `mercado.moneda_cobro`; entero en unidad menor. **El precio frontal es el peldaño de la escalera 17/19/27 US$ que fijó D3 (J16), convertido a la moneda local con IVA incluido: D5 lo copia y no lo decide, barre ni ajusta** |
| `precio_programado{fecha, precio{monto, moneda}, price_id?}` | decisión del dueño/D3 de un cambio de precio con fecha real (Black Friday 27/11/2026, Cyber Monday 30/11, propósitos de enero) | opcional y aditivo `[PENDIENTE: el esquema 1.2.0 aún lo rechaza; `landing.generar` y `landing.validar` ya lo leen]`; precio de después **mayor** que el actual y en la **misma moneda**; el `Price` programado debe existir en Stripe (gate H; hoy nada lo crea); `copy.barra_superior.lanzamiento.fecha` = esta fecha; al cruzarla se regenera el sitio sin la barra. Sin el campo, no hay barra de lanzamiento |
| `price_ids.test` / `.live` | `infra/alta.json` (alta de oferta, paso `stripe-catalogo-prueba`) | `live` = `null` hasta el gate H; mismos `lookup_key` (`OF-…_{rol}_v{n}`) en test y live; un `Price` usado no se modifica |
| `bump{modo, price_id, copy, precio}` | `oferta.bump` | v1 `oferta_previa` (casilla en `/comprar` y segundo `line_item`); `casilla_en_checkout` (`optional_items`) `[PENDIENTE: B2; VERIFICAR en sandbox]`; la aceptación se mide como `line_item` en Stripe (F1), no como evento de Meta; nunca premarcado; `precio` entre `landing.bump_pct_precio_min` y `_max` del principal; `copy` = `copy.json#S09.bump.etiqueta_casilla` expandida |
| `upsell` y postpago | — | `null` en v1 (otra transacción, más disputas). J16 los prevé tras el frontal y el bump; no tienen campos en `oferta`/`checkout` `[PENDIENTE: S-A contratos, S-B motor; el upsell de un clic solo con tarjeta, no con BLIK/P24]`: el Maker no los inventa |
| `precios_por_moneda[]` | `mercado.monedas_precio_adicionales` | vacío salvo que M1 lo declare; selector explícito en `/comprar` |
| `impuestos` | `mercado.fiscal` | `modo: diferido` mientras el dueño no decida; la página dice «precio final» |
| `metodos[]` | `mercado.metodos_pago.activos` | hoy `card, apple_pay, google_pay, link`; Stripe calcula el menú; locales diferidos (BLIK → PLN; Satispay, Bancontact, EPS, MB WAY → EUR). Klarna y Amazon Pay no sirven fuera de EE. UU./USD; PayPal no es activable |
| `descriptor` | `perfil_stripe.yaml` (D0/X1) | 5–22 caracteres, estático y neutro (sin condición ni resultado) |
| `success_url`, `return_url` | dominio de la oferta | éxito → `/gracias` (con el id de sesión `[VERIFICAR el placeholder]`); cancelación o vuelta → `/comprar` |
| `garantia_dias` | `oferta.garantia.dias` | = `/legal/reembolsos` = texto de S10/S11 |
| `consentimientos[]` | `mercado.consumo` | `terminos-y-desistimiento` y, en UE/UK, `renuncia-entrega-inmediata`; `texto_version` versionado; el texto vive en `copy.json#comprar.casillas` (el campo del formulario es `renuncia_desistimiento`) |
| `compra{ruta, metodo, bump_modo, renuncia{requerido, texto_version}, landing_version}` y `turnstile{habilitado, sitekey}` | `mercado.consumo`, `oferta.bump`, versión de la landing | opcionales y aditivos (LT-37, LT-39) `[PENDIENTE: el esquema 1.2.0 aún los rechaza]`; `landing.generar` los lee de aquí (si falta `renuncia.requerido`, decide por el locale y avisa); `turnstile.sitekey` es la clave pública, la secreta jamás va aquí; apagado por defecto |
| `metadata_esquema[]` | backbone 5.3 | `oferta_id, cid, asid, adid, utm_*, visitor_id, consent_marketing, landing_version, event_source_url, locale` (+ `fbp`, `fbc`, `angulo_id`, `renuncia_ts`, `verificacion`); sin datos personales |
| `ui_mode`, `expires_at_min`, `sesion_en_servidor` | — | `hosted`; `landing.checkout_expira_min`; `true` |

`client_reference_id = visitor_id` y la metadata se copia a `payment_intent_data.metadata`. El Maker **nunca** escribe un importe en una sesión, ni crea `Price` fuera de modo test, ni usa claves live.

## 3. Bump: reglas
1. Lo decide D3 (`oferta.bump`); D5 lo implementa. Sin bump en la oferta, `S09.bump = null` y `checkout.bump = null`.
2. Es un **complemento natural del resultado principal** y tiene **archivo real** en `producto.items` (si no, no se ofrece y se pide a D4).
3. Misma compra (no upsell). Precio claro con moneda; descripción ≤ 120 caracteres; sin «oferta única», «valor real» ni precio tachado.
4. **Nunca premarcado**; la decisión es consciente (`premarcado: false`, y C03 lo comprueba en el HTML de `/comprar`).
5. La aceptación se mide como `line_item` en Stripe frente a `landing.bump_aceptacion_objetivo_pct`; el AOV sale de F1. No hay evento `bump_visto` (la lista de eventos de Meta es cerrada).

## 4. Matriz de coherencia (C02): una verdad, muchos lugares

| Dato | Fuente de verdad | Aparece en | Cómo se garantiza |
|---|---|---|---|
| Precio y moneda | `oferta.precio`, `mercado.moneda_cobro` | `checkout.json`, HTML (`{precio}`, `data-precio-minor`, `data-moneda`), sesión de Stripe, correo, `/legal/*` | placeholders; `landing.validar` (`L1-PRECIO`, `L1-MONEDA`); la sesión de test devuelve el mismo total |
| Impuestos | `mercado.fiscal` | `checkout.impuestos`, línea de precio | «precio final»; sin «IVA incluido» con `diferido` (SD5-24) |
| Bump | `oferta.bump` | `checkout.bump`, S09, `/comprar` | mismo precio y nombre; `Price` del bump = catálogo |
| Garantía | `oferta.garantia.dias` | `checkout.garantia_dias`, S10/S11/S12/`/comprar`, `/legal/reembolsos` | `{garantia_dias}`; `L1-GARANTIA` |
| Bonos, páginas, peso, plazos | `producto.json` | S02, S06, S11, FAQ | placeholders `{n:…}`, `{paginas:…}`, `{tiempo_min}` |
| Medios de pago | `mercado.metodos_pago` | S12, `/comprar` | el FAQ nombra solo los activos (sin BLIK mientras esté diferido) |
| Entrega | `producto.entrega` | S12, `/gracias`, correo | `{vence_dias}`, `{max_descargas}` |

Guardarraíles en código: precio neto ≥ `limites.precio_neto_minimo`; cupones ≤ `limites.cupon_descuento_max_pct`; garantía ≥ `limites.politica_reembolso_dias`; la producción se bloquea si falla un L1, falta el sello de X1 o cambió el hash.

## 5. Régimen fiscal (por qué «precio final»)
Hoy `mercado.fiscal.regimen = diferido` por decisión del dueño: la página **no** afirma «IVA incluido» ni lo contrario hasta que el contador y X1 confirmen el texto. `checkout.impuestos.tax_behavior` es un dato de Stripe y **no** autoriza a escribir «IVA incluido» (observación sobre `_ejemplo`, que lleva `tax_behavior: inclusive` con modo `diferido`: confirmar con el contador). **Stripe estándar** (v1) frente a **Managed Payments** (+3,5 %; sin BLIK, Przelewy24, Satispay, MB WAY, EPS ni Pay by Bank; pago bajo `link.com*` `[VERIFICAR]`): decisión del dueño con el contador; reversible por oferta.

## 6. Pruebas de la sesión (en preview, modo test)
Importe manipulado en el cuerpo → ignorado (C14); `adid` fuera del catálogo → `desconocido`; metadata completa (C06); firma de webhook falsa → 400, mismo evento ×2 → 1 entrega, `unpaid` → sin entrega (C07); la tarjeta de prueba se usa **en la página real de Stripe** (no se automatiza): `https://docs.stripe.com/testing` `[VERIFICAR]`.
