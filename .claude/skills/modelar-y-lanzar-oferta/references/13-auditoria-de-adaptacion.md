# 13 · Auditoría de adaptación al mercado (toda oferta, antes de activar y al revisar una que no vende)

Nació el 15-nov-2026. El dueño lo pidió así: «revisar con este criterio y criterios similares o adyacentes, no solo con esta oferta, sino con todas las que modelemos en un futuro». El disparador fue Oferta F replicada a FR, IT, IE y NZ.

Se corre en dos momentos:
- **Antes del control previo** de cada oferta nueva o réplica (fase 11).
- **Al diagnosticar una oferta que no convirtió**, antes de culpar al producto o al mercado.

Cada punto se **comprueba**, no se supone. Si un punto no se puede comprobar, se dice.

## A. Lo que mira el script (`scripts/auditar_adaptacion.py`)

Corre con `python3` del sistema y sin dejar rastro: bloquea el píxel, las visitas de Impultienda, su API de conversiones, Clarity y Whop. Revisa todas las tiendas de la oferta, no solo la de la landing.

| # | Criterio | Por qué |
|---|---|---|
| A1 | La **portada** (raíz) de cada tienda está en el idioma del país. | Las tiendas de nivel que se duplican de la madre conservan su landing en la raíz: en FR, IT, IE y NZ la tienda Complete mostraba la landing de España. Arreglo: la landing del país, o un `location.replace` a la landing principal (IE y NZ, 15-nov). |
| A2 | El **título de la pestaña** lleva la marca del país. | FR e IT mostraban «Oferta F» en todas sus tiendas: se ve en la pestaña y en la vista previa al compartir el enlace. Se cambia con `impultienda_cambiar_titulo_pagina`. |
| A3 | Las vistas `?v=articulo` y `?v=ficha` están en el idioma del país, sin líneas sueltas en otro idioma y sin llaves `{{…}}` a la vista. | — |
| A4 | Ninguna imagen viene de **otra tienda** (otro `store_id`, como el de la madre). | IE y NZ salieron con 3 fotos de la tienda de España. |
| A5 | El **checkout visto desde el país** está en su idioma y en su moneda. Se mira con `preview_country=XX`, el mismo parámetro que usa «Ver como otro país» del panel. | Desde Argentina el checkout público sale en español y en USD. **Eso no es un error**: Impultienda traduce los textos del sistema según la conexión del comprador. Lo que no traduce es lo escrito a mano (bump, botón de pagar propio, bloques, textos del downsell): esas líneas las marca el script. |
| A6 | El checkout tiene **order bump** si la madre lo tiene. | FR e IT salieron sin bump (España lo vende en el 20-25 % de las compras): se pierde ticket. |

## B. Lo que se revisa a mano o con herramientas

| # | Criterio | Cómo |
|---|---|---|
| B1 | **Ambiente de imágenes y clips**: casas, cocinas, objetos y documentos del país. | Inventario visual de la guía 12 §3, punto 4. |
| B2 | **Texto dentro de las imágenes** (portadas, páginas, pantallas) en el idioma del país. | Recortar y ampliar cada portada. Nano Banana arrastra el idioma de la referencia. |
| B3 | **Videos**: subtítulos y píldoras en el idioma del país, sin datos de la madre (instituciones, plazos, moneda) y sin texto sobre caras. | Hoja de fotogramas cada ~3 s de cada video. Si son muchos, un agente que lea las hojas sin usar el navegador. |
| B3b | **Papeles y objetos de fondo** en los planos reusados de la madre: recibos, facturas, listas escritas a mano, etiquetas de carpetas, calendarios, libros, carteles y vistas por la ventana. Es lo que más se escapa, porque no es el texto principal del plano. | En FR e IT, 6 de 14 videos mostraban un recibo «RECIBO» de España. T03 y T05 tenían una lista a mano con «Banco / Luge / Agua» («Agua» es español; «Luge» es un error de la IA por «Luce»). Además, en 8 de los 14 había una etiqueta «TARJETA DE…» en la tapa de la carpeta, y en 4 italianos se veía una calle de Madrid por la ventana. Ampliar los planos con papeles y regenerar o tapar lo que no sea del país. |
| B3c | **Variedad real**: cuántos anuncios distintos hay de verdad (gancho y cuerpo), no cuántos archivos. | En FR e IT, 5 de los 7 videos de cada país compartían el cuerpo plano a plano y 4 abrían con el mismo plano. En la práctica eran unos 3 anuncios por país, y Meta los trata como casi duplicados. Medir la diversidad como pide el muestreo por tandas del referente (`08-creativos.md`). |
| B4 | **Post-compra**: título y descripción de cada oferta en el idioma del país. | `impultienda_ver_postcompra` en cada tienda: los textos marcados PERSONALIZADO no se traducen solos. |
| B5 | **Downsell pre-compra**: si se activa en una tienda que no está en español, inglés, portugués, árabe ni serbio, sus textos quedan en español. | Revisar en Marketing → «Downsell pre-compra» → «Modal de salida». |
| B6 | **Fan page completa** (perfil, portada, 3 publicaciones y 7 programadas) antes de activar. | `marca/publicado.json` |
| B7 | **Píxel propio** por país, nunca el de la madre. | FR e IT usaron el de España; la regla se corrigió el 14-nov. |
| B8 | **Plazos, leyes e instituciones** del producto y de la landing son los del país (en IT el plan es 48 · 30 · 12, no 48 · 30 · 6). | `04-producto/marco.json` contra la landing y los videos. |

## C. Diagnóstico cuando no convierte: comparar contra la madre, paso por paso

Mismo cálculo para la madre y para la réplica, con datos de Meta y de la tienda (todas las tiendas juntas, sin las sesiones de prueba):

1. **CTR y CPM** (Meta). Si son bajos, el problema está en el anuncio.
2. **Landing → inicio de pago** (inicios de pago del píxel / visitas a la landing). Si es bajo, el problema está en la landing o en el precio.
3. **Inicio de pago → apretó «Pagar»**: ventas más carritos (`impultienda_carritos_abandonados`, detalle por tienda), sobre las sesiones de checkout con `utm_source=meta`.
4. **Apretó «Pagar» → compró** (pago completado). Ventas / (ventas + abandonados + rechazados). Si es bajo, el problema está en el cobro (tarjetas del país, 3D Secure, método de pago que falta), no en la oferta. El motivo de cada rechazo está en la columna «Motivo» de Carritos abandonados del panel.

Las sesiones con `utm_source` igual a `prueba` o `revision`, o sin UTM, son nuestras: no se cuentan.

**Caso FR / IT (14 y 15-nov):**

| | España (madre) | Francia | Italia |
|---|---|---|---|
| CTR de salida | 6,8 % | 5,3 % | 5,8 % |
| Landing → inicio de pago | 7,1 % | 4,7 % | **2,1 %** |
| Apretó «Pagar» → compró | 15 de 18 (tienda Completa) | **1 de 5** | **1 de 3 o 4** |

- Los anuncios funcionaron (CTR parecido al de España), aunque con errores visibles en los papeles de fondo (B3b) y poca variedad real (B3c).
- En Italia la landing convirtió a un tercio que en España: con la tasa de España habría tenido unos 17 inicios de pago y tuvo 5. La causa no está en el idioma ni en las fotos (comprobado); queda abierta la calidad del texto en italiano.
- En los dos países, de cada 4 o 5 personas que apretaron «Pagar» con la tarjeta, solo 1 terminó la compra; en España terminaron 5 de cada 6. Los motivos de rechazo no se informaron.
- Lo que se aprende: medir el **pago completado** de cada país desde el día 1. Un mercado nuevo puede tener el cobro roto aunque todo lo demás esté bien.
