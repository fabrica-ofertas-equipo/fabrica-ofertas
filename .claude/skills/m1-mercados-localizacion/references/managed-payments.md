# Rama Managed Payments (MoR de Stripe)

> Fuente: `departamentos/16` §4.1 «Rama Managed Payments»; `docs/_investigacion/03-stripe.md` §4.2, `07e` §1.5, `07g` §0.6, `07b`. **M1 no activa nada ni decide el régimen fiscal**: reporta el delta de cada rama. La decisión es `[DUEÑO + contador]` (`docs/00-decisiones-y-tareas-del-dueno.md` §0 B4 y §4).

## 1. Qué cambia si `decision_managed_payments = si`
| Aspecto | Efecto |
|---|---|
| PAGO | solo cuentan `card`, `apple_pay`, `google_pay`, `link` y, para BE, `bancontact`. **BLIK, Satispay, MB WAY, EPS, Pay by Bank y Przelewy24 salen**; Amazon Pay tampoco (07g §0.6). En el caso polaco la cobertura cae a la de tarjetas y billeteras ⇒ R6 la excluye |
| Neto | **+3,5 %** sobre las comisiones de Payments (`[VERIFICAR]` si sobre el total con impuestos) y **sin `fee_tax` propio** (`puntaje.seleccionar`: `comision_pct += 0,035`, `stripe_tax = ninguno`) |
| FISC | sube (el MoR calcula, cobra, presenta y remite el impuesto) y **R8 no aplica** |
| Restricciones `[VERIFICAR]` antes de elegirlo | solo Checkout/Payment Links, **sin Elements ni dominio propio de checkout** (roza la decisión 9 del dueño y el backbone 5.3), descriptor «LINK.COM*»; Pix no soporta Adaptive Pricing; Stripe Tax no soporta Brasil |

## 2. Qué calcula M1 (siempre las dos ramas)
- `decision_managed_payments = no_decidido` ⇒ se calcula **Stripe estándar** (la rama «no») y se informa la otra: la rama estándar **no resta métodos ni suma 3,5 %** (MQ-20).
- `mercado.seleccion.json#rama_managed_payments{si, no}`: `pago_pct`, `delta_neto` (dinero, puede ser negativo), `fisc`, `r8_aplica`, y `rama_estandar_resta_metodos: false` mientras no esté decidido.
- Sensibilidad `managed_payments_si` de `puntaje.seleccionar`: ¿el elegido sigue en el top 3 con MP?

## 3. Cómo se presenta al dueño
Una frase por rama con número: «Con Managed Payments, X pasa de a % de cobertura y su neto cambia en b; el impuesto lo presenta Stripe. Sin él, … y la exposición fiscal de los países `[…]` queda en tu firma (`exposicion_aceptada`)». M1 **no recomienda** una rama: expone el cambio y qué decisión mueve más el resultado (casi siempre es la combinación MP × métodos locales).
