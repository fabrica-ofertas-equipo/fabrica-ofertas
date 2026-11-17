# Hechos externos que M1 aplica (cada uno `[VERIFICAR]` en la ficha antes de sellar)

> Fuente: `departamentos/16` §4.1 «Hechos externos vigentes» y las notas citadas (leídas el 2026-11-05/06). Una política o tarifa **cambia**: antes de sellar un `mercado.json`, reverifica el hecho por fuente oficial (texto crudo; `WebFetch` solo ubica) y actualiza `fecha_lectura`. Esta tabla es un **índice de qué mirar**, no una fuente: la fuente es la URL.

| Hecho | Estado | Fuente | Dónde pega en M1 |
|---|---|---|---|
| Tarifa de ubicación de Meta (línea aparte en la factura; no figura en las métricas de Ads Manager; el IVA se calcula sobre ella; no aplica a categorías especiales de anuncios; se puede excluir el país a nivel de cuenta sin garantía de bajar la tarifa): FR, IT, ES, AT, UK, TR desde 2026-07-01 | A | `facebook.com/business/help/1238737454289085` (07a resumen 4); `medianama.com/2026/03/223-meta-advertisers-location-fees-digital-service-taxes/` | `meta.recargo_meta_bp` por país → `f_meta` en `r` y en el CPC (una vez; MQ-14, D18) |
| IVA de no establecidos: OSS no-Unión sin umbral desde la primera venta (UE); UK registro HMRC desde la primera venta; CH representante fiscal y umbral mundial; NO VOEC | B | 07b, 07h §7, 05 §6.1; `revenue.ie/en/vat/vat-ecommerce/non-union-scheme/index.aspx` | `fiscal.desde_primera_venta`, R8, FISC |
| Función/botón de desistimiento en 2 pasos obligatoria en la UE desde 2026-06-19 (Dir. (UE) 2023/2673); alcanza a comerciantes no UE que apuntan a consumidores UE; Italia art. 54-bis; transposición polaca suspendida al 2026-06-12 (CMS, B) | B/C | 05 §2; 07h §7 | `consumo.boton_arrepentimiento`, MQ-08 |
| DSA: beneficiario y pagador obligatorios en todo anuncio nuevo o editado hacia la UE | A | `facebook.com/business/help/721913190475838` (07a) | `dsa.beneficiario_pagador` (lo usa D7) |
| BLIK: titular de EE. UU. elegible, solo clientes de Polonia, PLN, sin Managed Payments, sin Express Checkout Element, sin apelación de disputas | A | `docs.stripe.com/payments/blik` (leída 2026-11-06) | MQ-04, `pagos-por-fase.md` |
| Klarna (solo EE. UU./USD) y Amazon Pay (solo USD) no sirven con una LLC de EE. UU. fuera de EE. UU.; PayPal no activable vía Stripe para titular de EE. UU. | A | 07g §1; `docs.stripe.com/payments/klarna`, `/paypal` | MQ-13, hueco PayPal |
| Managed Payments: +3,5 %; soporta tarjetas, Apple/Google Pay, Link, Bancontact (+ otros no europeos); no BLIK/Satispay/MB WAY/EPS/Pay by Bank/Przelewy24; solo Checkout/Payment Links | A (BLIK explícito; el resto por ausencia en la lista: B) | `docs.stripe.com/payments/managed-payments` (03 §4.2, 07g §0.6) | `managed-payments.md` |
| Tarifas de Stripe: tarjeta 2,9 % + 0,30 USD; internacional +1,5 %; conversión +1 %; disputa con tarjeta 15 USD; BLIK 1,9 % + 0,30; Przelewy24 2,2 % + 0,30; Satispay 1,8 % + 0,30; Stripe Tax Basic 0,5 % o 0,50 USD por API | A (leídas 2026-11-06) | `stripe.com/pricing`, `stripe.com/pricing/local-payment-methods` | `comision_bp`, neto; vigencia ≤ `vigencia_tarifas_dias` |
| Black Friday 2026-11-27: los CPM suben en Q4 (blogs: +25-50 % o más; sin cifra autoritativa para PL/IT) | C | 16 M1 | `mult_cpm.central/estres` |
| Verificación financiera de Meta (AU, IE y regiones de verificación) y aviso «pagado por» en dinero | A/B | 22b; HC 719892839342050 de Meta | EXPO dinero, regla de parada |
| Ley del Idioma Polaco (art. 7a y 8): documentación al consumidor en polaco; Loi Toubon (FR); Quebec en francés | B/C `[VERIFICAR]` | 07h §7, 07a §C.2, 07c §3.2 | R5, `obligacion_legal_idioma` |
| Digital Fairness Act: propuesta esperada ~nov-2026 (una sola fuente) | C | 07b §6 | riesgo a vigilar (disparador de reverificación) |

## Disparadores de reverificación por evento (paso 12)
Cambio de la lista de tarifas de ubicación de Meta · cambio de política de Meta/Stripe en salud, relaciones o dinero · cambio de la ley de desistimiento o DSA · un rechazo de Meta o Stripe atribuible a un país o idioma (**congela la hoja × idioma**; no se abren cuentas nuevas) · llegada de CPM o conversión propios · fin de vigencia de cualquier hoja crítica.
