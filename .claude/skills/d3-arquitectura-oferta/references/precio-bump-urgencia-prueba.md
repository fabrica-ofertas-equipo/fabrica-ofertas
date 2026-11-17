# Precio, bump, upsell, urgencia y prueba

## 1. Precio (`precio`)
- **REGLA DEL DUEÑO (J16, 2026-11-07) — el frontal sale de la escalera, no de un barrido.** El precio frontal es el **peldaño más cercano al precio que cobra el producto original**, en USD: **17, 19 o 27**. Menos de 17 → 17; entre 17 y 19 → 19 (el empate sube; el dueño aceptó 17 o 19); 20-22 → 19; más cerca de 27 → 27 (23 empata y sube a 27); por encima de 27 → 27 (techo hasta que el dueño defina peldaños mayores). **Referencia = lo que el original realmente cobra** (precio efectivo en USD al tipo de cambio declarado), **no** el ancla tachada ni la suma de valores de los bonus; si lo visto es un precio de promoción (p. ej. «Black Friday»), se usa el más alto visto sin cuenta atrás y se declara. El peldaño y su cuenta (original → USD → peldaño) van en `oferta.md` §A con la fuente; nadie lo mueve para que la economía cierre.
- **Moneda local**: el peldaño se convierte al tipo de cambio declarado y se lleva al número local habitual más cercano (17 US$ ≈ 63 zł). Es **con IVA incluido** en la moneda de `mercado.moneda_cobro`. `moneda`, `precio.lista` y `locale` son **únicos por oferta**; la economía se calcula **por país del clúster**.
- **Límites que siguen mandando**: `limites.precio_neto_minimo` (tras IVA y comisiones; `null` = pendiente) y `economia.precio_lista_rango` (USD equivalentes; el peldaño debe caber: si no cabe, **no se mueve el precio**: se pide el cambio del rango al dueño, gate H). Ya **no** se busca «el menor escalón con `razon ≥ razon_min_factible`»: la economía se **calcula** con el precio de la escalera y, si no cierra, las palancas son el embudo (bump, upsell, postpago) o `ESCALAR`, no subir el precio.
- **Un precio en v1.** `precio_b` (un segundo precio dentro de rango) solo como alternativa **preaprobada** en `oferta.md` §E para que D7 lo testee; no va en `oferta.json`.
- **Ancla**: `anclaje = null` (v1). «Precio normal», «valor real», «antes» y descuentos solo con historial real de 30 días (S13).
- Conversión de moneda para el rango y los límites: tipos de cambio de F1 (`empresa/finanzas/tipos_cambio.jsonl`); sin ellos, uno declarado `[SUPUESTO]` con su fuente.

## 2. Bump (`bump`; 0 o 1)
- Objetivo: llevar el `aov` hacia ≥ 1,3 × el frontal (16 §2.3; los creadores dicen ≥ 1,5 `[B]`) y **diluir la comisión fija y la disputa**; **no** es un requisito de la promesa (S9) ni un servicio.
- Precio dentro del rango `landing.bump_pct_precio_min`–`landing.bump_pct_precio_max` del precio del frontal (hoy 30-60 %): **esa es la única fuente del rango** (`lint_d3` L1-12 lo comprueba contra el parámetro). Recomendación [HIPÓTESIS]: ≤ 40 % mientras no haya toma real, porque un bump caro baja la aceptación; es un criterio de diseño, no un tope.
- **Toma planificada = `economia.tasa_bump_bp`** (hoy 10 %; los creadores dicen 30-50 % `[C]`: no se usa). Subirla exige evidencia propia de D8.
- Cada bump hereda el riesgo; sin comunidad, soporte ni mentoría; descripción de una línea; producible por D4.
- **Sin bump** es válido, pero el dueño usa bump en todas sus ofertas (J16): el frontal de la escalera es bajo y el bump es lo que sube el ticket. Si el motor dice NO_FACTIBLE, las palancas son el bump y los demás escalones del embudo; **el precio frontal no**.

## 3. Upsell y postpago
**Hoy desactivado** (`upsell = null`): el upsell de un clic exige tarjeta guardada y excluye BLIK y otros métodos locales (`03-stripe.md` §1.3); `tasa_upsell_bp` = 0 en `parametros.economia` (S15). **El dueño trabaja con upsell y postpago (J16)**: se activan cuando S-A/S-B retiren S15 y el motor modele la fracción de pagos con tarjeta (`mix_metodos`; el motor ya admite `precio_upsell`/`tasa_upsell_bp`). Hasta entonces: `upsell = null` en `oferta.json`, y en `oferta.md` §E se deja **planificado** (qué ofrecería, a qué precio y con qué toma `[HIPÓTESIS]`), sin sumarlo a la economía. El postpago (oferta después de pagar) no tiene aún campo en el contrato: también va planificado en §E.

## 4. Urgencia (`urgencia`)
`null` salvo **fecha o cupo reales verificables por código**. Si no es `null`: `{tipo, verificable_por}` donde `verificable_por` nombra la fuente de verdad (una fecha de cierre configurada en D5, o un contador alimentado por el servidor **sin reinicio**). Nada de «solo hoy», «últimas unidades», cuentas regresivas que se reinician, cupos escritos a mano ni notificaciones de compra (UCPD pt. 7; S3). La landing de referencia del dueño ya los eliminó.

## 5. Prueba (`prueba[]`; tipos del contrato)
Tipos permitidos: `logica_del_producto`, `muestra`, `dato_con_fuente`, `testimonio_con_permiso`. **Una oferta nueva solo tiene los dos primeros**: la muestra de 1 página (D4 la produce; `fuente` = su ruta) y la lógica del producto (cada paso entrega un resultado verificable).
- `testimonio_con_permiso` exige `consentimiento_ref` y un cliente real: con `entrevista.casos_previos_n = 0` **no hay ninguno** (S6, S23).
- **Ninguna cifra de personas, clientes, ventas, estrellas o reseñas escrita a mano** (X1-P08: las genera un script desde Stripe y el sistema de reseñas; reseñas con `compra_id` y sin cifras de resultado). Ningún testimonio sintético, antes/después ni avatar IA como cliente.
- `dato_con_fuente`: cifra externa con `fuente` T1/T2 y fecha (D4 la guarda en `afirmaciones.jsonl`).
- Si el dueño o el encargo piden «agrega testimonios» sin casos previos: **rechaza** y déjalo en `supuestos[]` (caso C7).

## 6. Costos fijos de la oferta
`costos_fijos_oferta` = 0 salvo costos reales declarados (dominio, herramientas): suman a `perdida_max_test` (el motor lo hace).
