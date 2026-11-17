# Pagos por fase, monedas y hueco PayPal

> Fuente: `departamentos/16` §3.2 y §4.1; `docs/_investigacion/07e`-`07h`, `08` §1.6/§1.8; `docs/fuente/stripe-metodos-de-pago-habilitados.md` (captura del dueño del 2026-11-05: 14 habilitados, 24 deshabilitados y 1 «se requiere una acción» **sin leer** `[VERIFICAR]`). Código: `scripts/puntaje.py cobertura`.
> Principio: **la cobertura se calcula con lo que la fase vigente deja cobrar**, no con lo que aparece «habilitado» en el panel. El panel sobrestima: «Popular en: todas las regiones» no significa disponible para clientes de cualquier país ni para una LLC de EE. UU.

## 1. Las dos fases
| Fase | Qué cuenta | Cuándo |
|---|---|---|
| `estandar_tarjeta_billeteras` (VIGENTE; la única que admite `mercado.json` 1.1.0) | `card`, `apple_pay`, `google_pay`, `link` (elegibles, cobrables en la moneda de cobro y no excluidos por Managed Payments) | por decisión del dueño de diferir los métodos locales |
| `con_locales` (requiere decisión del dueño **y** MINOR del contrato `mercado`, pedido a S-A) | lo anterior + `blik`, `przelewy24`, `satispay`, `mb_way`, `bancontact`, `multibanco`, `eps`, `pay_by_bank` elegibles y con su moneda exigida | cuando el dueño levante el diferido |

**M1 calcula las DOS siempre** y reporta `valor_desbloqueo_pp` = cobertura(`con_locales`) − cobertura(estándar). Lo recomendado más allá de la fase vigente va a `mercado.seleccion.json#metodos_locales_recomendados[]` (`moneda_requerida`, `valor_desbloqueo_pp`, `requiere[]`), **nunca** a `mercado.json`. M1 no activa ningún método ni habla con Stripe en modo escritura.

## 2. Qué NO suma nunca (MQ-13; defectos sembrados D02 y D08)
`paypal` (una cuenta de EE. UU. no puede activarlo vía Stripe: es **hueco**, no cobertura) · `klarna` (solo clientes de EE. UU. en USD) · `amazon_pay` (solo USD; no sirve con precios en moneda local; sin Managed Payments) · `cash_app_pay`, `afterpay`, `interac`. El hueco PayPal se informa en pp por país (`hueco_paypal_pp`) y la decisión de aceptarlo (o evaluar PayPal propio) es del dueño.

## 3. Moneda ↔ método (MQ-04; sembrado D01)
| Método | Moneda exigida | Clientes | Notas |
|---|---|---|---|
| `blik` | **PLN** | solo Polonia | sin Managed Payments, sin Express Checkout Element; disputas sin apelación (aviso del cliente hasta 13 meses); en móvil el comprador vuelve a la página a mano (riesgo de medir el Purchase) `docs.stripe.com/payments/blik` (A, leída 2026-11-06) |
| `przelewy24` | PLN o EUR | Polonia | sin contracargos; exige dirección, ID fiscal, registro, reembolsos, privacidad y términos; MCC 5815-5818 «restringidos» (puede demorar) |
| `satispay`, `bancontact`, `eps`, `mb_way`, `multibanco` | EUR | IT / BE / AT / PT / PT | Bancontact es el único local compatible con Managed Payments; Multibanco: voucher, entregar solo con `async_payment_succeeded` |
| `pay_by_bank` | GBP / EUR | UK, IE, FI | sin contracargo; sin Managed Payments; elegibilidad para titular de EE. UU. `[VERIFICAR]` con compra real |
| `pix` | BRL | Brasil | otro negocio (IOF 3,5 %, disputas no impugnables): proyecto aparte |

Reglas de moneda de cobro (`mercado.moneda_cobro`): moneda **local** solo si un método clave la exige (BLIK = PLN); **EUR** en eurozona (evita +1 % de conversión); fuera de eso USD base + `monedas_precio_adicionales`. **Adaptive Pricing apagado** (D5). Un precio de referencia por moneda va a `precio_referencia[]` con `fija: "D3"`: M1 da el rango, **D3 fija el precio**.

## 4. Cómo se lee la salida
```
python -I .../puntaje.py cobertura FICHA.json --decision-mp no_decidido
→ estandar_tarjeta_billeteras{cobertura_pct, suman[], no_suman[{id, cuota_bp, motivo}], hueco_principal, hueco_paypal_pp}
  con_locales{…} · valor_desbloqueo_pp · rama_managed_payments_alternativa{…}
```
- Se toma la **mejor moneda de cobro** de `monedas_cobro_posibles` en cada fase (la moneda elegida sale en `moneda_cobro`).
- El `puntaje PAGO` usa las bandas de `scripts/mercados/datos/parametros.json#reglas_pago` sobre la cobertura de la **fase vigente**.
- R6: duro `cobertura_pago_min_duro` excluye; entre duro y `cobertura_pago_min_blando` pasa con `cobertura_media` + gate H.

## 5. Qué dicen los números (confianza C; recálcalos con la ficha, no los copies)
- Con la fase vigente, el caso **polaco** depende casi por completo de BLIK: sin él la cobertura queda en una fracción de lo que muestra el ranking de 08 (que contaba BLIK). Con `con_locales` y PLN sube mucho. Eso **no dice nada sobre el mercado polaco; dice que el cobro estándar no lo alcanza** (decisión del dueño: ¿se levantan los métodos locales?).
- El caso **italiano** casi no depende de lo local; depende de tarjetas, y PayPal (hueco grande) es inalcanzable con Stripe de una LLC de EE. UU.
- Canadá/Irlanda: las tarjetas dominan; el hueco PayPal es ~16-20 pp; Australia/Nueva Zelanda pierden por BNPL local y A2A no cubiertos.
- La cuota de BLIK va de ~30 % a > 70 % según la fuente: rango de trabajo C; **medir** el % de compras por método tras ~50 compras por país (si BLIK < el umbral de 08 §6, su relevancia queda refutada) y reemplazar la cobertura estimada por la mezcla real del panel.

## 6. Qué hace cada caso con el dueño (no lo decide M1)
`pendientes_dueno[]` de la selección lista siempre: Managed Payments sí/no; métodos locales diferidos o no; captura de las pestañas «Deshabilitado» (24) y «requiere acción» (1) de Stripe; aceptar o no el hueco PayPal. El **efecto** de cada decisión sobre el resultado se informa con números (cobertura, puntaje, neto) para que el dueño decida con el dato delante.
