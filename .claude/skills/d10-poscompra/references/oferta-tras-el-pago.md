# Oferta tras el pago: bump, upsell y postpago

> v0.1 sin pulir. Origen: J7 («como Impulstienda pero in-house»: oferta(s) después de pagar) y J16 («después todo lleva order bumps, upsells y postpago»). `docs/_investigacion/03-stripe.md` §1.3 y §4, `brechas/03` B3-04, B3-10, B3-11. Hoy **solo existe el bump**.

## 0. Vocabulario (como lo usa esta skill)

| Nombre | Cuándo | Cómo se cobra | Estado en el repositorio |
|---|---|---|---|
| **Bump** | antes de pagar, casilla en `/comprar` (no premarcada) | 2.ª línea de la misma sesión de Checkout (`bump_modo = oferta_previa`) | **existe** (`crear-sesion`, `checkout.bump`, D5) |
| **Upsell de un clic** | justo después de pagar, en `/gracias` | cobro `off_session` sobre el método guardado en la sesión inicial (`setup_future_usage`) | **ausente** (`checkout.upsell = null`; `departamentos/06`: «upsell fuera de v1»; Stripe no trae upsell nativo para pagos únicos) |
| **Postpago** | justo después de pagar, en `/gracias` | una **2.ª sesión de Checkout** con el precio a la vista; cualquier método | **ausente** (sin campo en el contrato; D3 lo deja «planificado» en `oferta.md` §E) |

El dueño los llama juntos «upsells y postpago» (J16) y la cadena de Juan Pablo es «oferta 1 → oferta 2 → acceso → mail» (`f095`). **Cuántas ofertas y en qué orden las decide D3 con el dueño; D10 no lo fija.** `[VERIFICAR con el dueño]` si «upsell» y «postpago» son dos pasos distintos o dos nombres del mismo.

## 1. La entrega no espera a la oferta

El producto principal (y el bump pagado) se entrega **al confirmarse el pago**, con el correo E0 y el acceso visible en `/gracias`; la oferta tras el pago aparece *debajo* y es opcional. Motivos: entrega inmediata (D10 §3, `f086`: «al instante → entrega con link directo»), cada minuto de espera es una disputa «no recibí» en potencia, y el comprador no debe sentir que el acceso depende de rechazar una venta. Si compra la oferta, recibe **otro correo** (o el mismo si llega a tiempo) con esa línea (`entrega-y-correo.md` §2).

## 2. Quién hace qué

| Quién | Qué |
|---|---|
| **D3** | qué se ofrece, mecanismo y entregable (del mismo mecanismo; sin servicio humano, comunidad ni suscripción), precio, promesa, riesgo; `oferta.upsell`; la economía (`tasa_upsell_bp`, `mix_metodos`) |
| **D4** | el archivo de cada línea (`producto.items[]`, campo `linea` propuesto) |
| **D5** | `/gracias` y el bloque (HTML, CSP, formulario); los `Price` en Stripe |
| **S-B** | el cobro con método guardado y la 2.ª sesión; el `fulfill` por línea |
| **D10** | el copy del bloque y de los correos, la regla de entrega por línea, la medición por línea y por método, el informe a D3 |

D10 **no** fija precio, descuento, número de ofertas ni el límite de la ventana.

## 3. Reglas del bloque de oferta (las comprueba el QA)

1. **Precio visible, de contrato:** se expande con el placeholder de D5/D3, nunca escrito a mano. Botón explícito con el precio («Dodaj za {precio}» / «Añadir por {precio}»); **«No, gracias» visible y con el mismo peso**; no se vuelve a ofrecer lo rechazado.
2. **Sin cuenta atrás, sin «solo ahora», sin cupos, sin precio tachado** (el ancla solo con historial real de ≥ 30 días); sin avisos de «compra reciente». La urgencia solo con una fecha real y un `Price` programado (D5, `precio_programado`).
3. **Mismo mecanismo y entregable** que la oferta; ninguna promesa nueva de salud, ingresos o resultados (X1 veta).
4. **Garantía:** el texto de `oferta.garantia` cubre también la línea ofrecida salvo que D3 diga otra cosa (se cita literal junto al botón). Reembolso total por defecto.
5. **Recibo inmediato** por correo con la línea cobrada y el descriptor reconocible (`checkout.descriptor`); un cargo «sorpresa» de un clic aumenta los contracargos «no reconozco» (`03-stripe` §1.3).
6. **Consentimiento para guardar el método** (Checkout lo exige con `setup_future_usage`): su texto lo fija D5/X1 `[VERIFICAR redacción exacta, 03-stripe §5 pregunta 13]`; D10 no lo escribe.
7. **Máximo de ofertas encadenadas** `[HIPÓTESIS: 2, según la cadena del video]` y siempre una sola decisión por pantalla.
8. **Sin JavaScript nuevo:** hoy el único script es `consentimiento.js`; el botón es un formulario `POST` (hoy `L1-FORMULARIO` solo admite el de `/comprar`: PEDIDO C-01).

## 4. Restricción tarjeta frente a BLIK y Przelewy24

| Método de la sesión inicial | Upsell de un clic | Postpago (2.ª sesión) |
|---|---|---|
| Tarjeta, Apple Pay, Google Pay, Link (método reutilizable) | sí, con consentimiento y botón; si pide autenticación (SCA) → cae a una sesión nueva | sí |
| **BLIK** (PLN) | **no** (sin método guardado reutilizable; `03-stripe` §1.3, J16) `[VERIFICAR si Stripe lo cambió]` | sí, pero el comprador autoriza otra vez en su banco |
| **Przelewy24** y otros métodos locales sin tarjeta | **no** | sí |

- **Lo decide el código por el método real de la sesión** (un hecho de Stripe); el Maker redacta las dos variantes de `/gracias` y no decide cuál se muestra.
- **Hoy** el contrato solo admite `card, apple_pay, google_pay, link` (`checkout.schema.json:201`), así que todo método es reutilizable; **al habilitar BLIK/P24** (B3-04) la fracción con tarjeta baja y la economía debe reflejarlo (`mix_metodos`, que J16 pide a S-A/S-B). Hasta entonces D3 no suma el upsell a la economía (D3, `d3-arquitectura-oferta/references/precio-bump-urgencia-prueba.md`: «planificado»).
- Un reembolso de BLIK se hace por la vía que admita Stripe en ese método (`departamentos/11` Anexo C: hasta 730 días, ≤ 120 min) `[VERIFICAR]`; P24 y similares, por transferencia desde la cola humana.

## 5. Qué mide D10 por línea (informe)

Toma de cada línea por método, país y locale · ticket medio real frente al modelado por D3 (`tasa_bump_bp`, `tasa_upsell_bp`) · `r` y `d` **por línea** (la tasa de disputa del upsell se mide aparte, `03-stripe` §1.3) · tiempo hasta la entrega de la línea · tickets «no sabía que me habían cobrado». Hoy `fact_pedido` no guarda método de pago, líneas ni bump (`datos/migraciones/0001_inicial.sql:50-65`; B3-13): PEDIDO P-10.

## 6. Qué no se sabe del referente (J17)

El tramo posterior a la compra del referente (checkout, bump, upsell, gracias, correo) **no se ha visto**: «solo se ve comprando (≈ 13-15 US$) — decisión del dueño» (`estructura-funnel-referentes.md` líneas 90-98). Hasta que el dueño aporte capturas, esta skill **no imita** esa estructura ni la inventa: el bloque de oferta sigue las reglas de §3 y el orden lo fija D3.

## 7. Mientras no haya contrato

El paquete deja la línea como `«planificado»` en `paquete-poscompra.json` y un borrador `[PENDIENTE]` del bloque en `gracias.md`; el correo E0 ya admite varias líneas; `plan-entrega` ya reparte por línea. No se escribe nada que cobre.
