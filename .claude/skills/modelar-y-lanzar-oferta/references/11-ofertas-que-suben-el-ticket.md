# Ofertas que suben el ticket promedio: dónde aparecen y cómo se modelan

Pedido del dueño (2026-11-11), tras encontrar una en «Oferta B»: «guarda este tipo de cosas para tenerlas en cuenta para próximos funnels, porque puede suceder este tipo de automatizaciones o de ofertas que suben el AOV antes de pagar».

Son parte de la **estructura** del funnel: se buscan en el desarme, se modelan con precios reales y van al desarme, no a `no-modelado.md` (ese es solo para testimonios, urgencia y escasez).

> **Dueño, 15-nov:** el test sale **igual al referente** en todo lo de antes del pago, bumps incluidos («test = solo el front» no es regla). Si el referente tiene dos bumps, se modelan los dos (con Oferta G se había modelado uno solo de los dos de ReferenteG).

## Los cuatro lugares donde aparecen

| Momento | Nombre en la taxonomía | Qué es | Cómo se encuentra | En Impultienda |
|---|---|---|---|---|
| Antes del checkout, al elegir | `subida-previa` | Ventana al tocar el paquete barato: «llévate el caro por X más», con su propio enlace de pago | Tocar el botón del paquete barato; leer el `.js` de la página (un tercer checkout y la función que abre la ventana) | Ventana en nuestra landing + una tienda aparte con el paquete caro al precio rebajado |
| Dentro del checkout | `bump` | Casilla «sí, quiero añadir…» | Abrir el checkout del referente sin pagar | Complemento del producto (tarjeta «Agregar») |
| Después de pagar | `upsell` | Página de una sola oferta tras la compra | Casi nunca se ve sin comprar | Upsell post-compra. **Regla del dueño: se activa recién después del test**, salvo que el referente lo tenga como parte de su estructura |
| Al rechazar o al salir | `downsell` | Rebaja al decir que no o al intentar irse | Ventana por intención de salida; ruta `/downsell` | Ventana por intención de salida en nuestra landing |

## Cómo buscarlas en el desarme

1. Tocar cada botón de compra de la landing del referente, no solo leerlo. Si un botón no va directo al checkout, hay un paso en medio.
2. Leer los scripts propios de la página (`fragmentos-navegador.md`, `expediente_funnel.py` los guarda). Buscar: varios enlaces de pago (`checkout`, `pay.`, `hotmart`, `snapp`…), funciones que abren ventanas (`modal`, `openModal`, `dialog`), y escuchas de salida (`mouseout`, `beforeunload`, `visibilitychange`).
3. Anotar por cada una: qué la dispara, qué ofrece, a qué precio, a qué checkout lleva y qué pasa si se rechaza.

## Cómo se modeló la primera (Oferta B, 2026-11-11)

Referente: botón «Get the Basic Toolkit» (9 USD) → ventana «ONLY ON THIS PAGE · Wait. Get Complete for just $4 more» → «$17» tachado, «$13» → botón «GET COMPLETE FOR $13» (tercer checkout) o «No thanks, continue with Basic for $9». En escritorio, a los 20 s, la misma ventana una vez si el cursor sale por arriba.

Nuestro:
- Tienda aparte `tu-tienda` (copia de la principal con `/dashboard/duplicar-tienda`): kit completo con sus 4 bonos a **13 USD / MX$ 249** (precios del 11-nov, anteriores a la regla 19/27; el principal pasó a MX$ 359 el 12-nov y los precios vigentes están en el libro de tests y en el `FUNNEL.md` de la oferta). La copia no trae cobro, píxel ni markets: Copiar de otra tienda (Impul Pay) → Cambiar modo a Multidivisa → píxel → Markets: México MXN → «Precios por mercado» 249. **La copia trae las imágenes rotas** (error 400): volver a subir la imagen del producto y las portadas de los bonos.
- En la landing (`landing.plantilla.html`): el botón del básico lleva `data-basico`; al tocarlo se abre la ventana «Antes de seguir · Llévate el kit completo por $80 más», «$319» tachado (el precio real del completo en la tienda principal) y «$249». «Quiero el completo por $249» va al checkout de la tienda aparte; «No, gracias: sigo con el básico por $169» va al checkout del básico. Misma salida por intención a los 20 s en pantallas anchas. Los enlaces llevan los parámetros `utm_*`, `fbclid`, etc. de la página.
- El rótulo del referente («ONLY ON THIS PAGE») no se copió: el precio de 249 existe en otra tienda, así que «solo en esta página» no sería cierto. Se usó «Antes de seguir».
- Al cambiar el precio base del producto en el editor, escribir encima no siempre guarda: poner el valor con el setter nativo y eventos `input`/`change`, guardar, recargar y leer la tarjeta.

## Qué vigilar después

- Cuántos de los que tocan el básico aceptan la subida (ventas de la tienda aparte contra ventas del básico).
- Que el píxel registre la compra en las tres tiendas (es el mismo píxel).

## Backend ofensivo (upsells post-compra)

Desde el 2026-11-13 es una skill propia: **`backend-ofensivo`** (`.claude/skills/backend-ofensivo/`). Se arma después del test, cuando la oferta ya vende, y lo dispara la revisión diaria de `escalar-oferta`. Aquí queda solo lo que se modela ANTES de pagar: subida previa, bump y rebaja al salir.
