# Fase 8 · Landing

Salida: la tienda pública con una página que tiene los mismos bloques, en el mismo orden, que la del referente, con textos, imágenes y video propios. Trabajo en `ofertas/<id>/05-landing/`.

## 1. El plano sale de medir, no de recordar

Con el fragmento 1 de `fragmentos-navegador.md`, en móvil y en escritorio, sobre la página del referente:

- Lista de secciones con su alto (cuánta página ocupa cada una).
- Dentro de la cabecera, el orden exacto de cada elemento: antetítulo, título, bajada, video, nota, caja de precio, botón, contador, sellos.
- Si es una columna o dos en escritorio, y si el texto va centrado.
- Tamaño y proporción del video, si arranca solo y en silencio, dónde está el control de sonido.
- Textos de botones, sellos y preguntas frecuentes (para saber qué función cumple cada uno, no para copiarlos).

Eso se escribe en `modelado/desarme.md` como tabla. En México el referente era: barra fija → cabecera → 6 vistas previas (la mitad de la página) → ritual en 3 pasos → 3 bonus → oferta → 5 preguntas → pie.

Error que hubo que corregir con la página ya publicada: puse precio y botón entre la bajada y el video y dejé la cabecera en dos columnas; el referente va título → bajada → video → nota → caja de precio con botón, en una sola columna centrada. El orden de los elementos dentro de cada bloque también es estructura.

## 2. Copy (`copy.md`)

Un documento con el texto de cada bloque en el orden del plano, escrito con la guía de voz de la inmersión (`ejemplo-mx/05-landing/copy.md` es el modelo). Arriba, las pocas mejoras sobre el referente, cada una con su respaldo en la inmersión (en México: edad y tamaño de hoja visibles, franja para maestras, más preguntas frecuentes con las objeciones locales, pie con contacto).

- El título nombra cosas concretas del producto y, si el mercado tiene un referente cultural propio, lo incluye (México: «De la Mona Lisa a la Catrina»).
- Medios de pago en los sellos: escribir solo los que se comprobaron en la vista previa del checkout de ese país.
- Sin testimonios; la prueba es el producto a la vista.

## 3. Plantilla y armado

`landing.plantilla.html` es solo el cuerpo (Impultienda pone el resto): un `<style>` con todo bajo `.mc`, las secciones y marcadores que se reemplazan al armar.

- Precio: `{{price}}` y `{{original_price}}` (los resuelve el servidor por mercado; también existen `{{savings}}` y `{{currency}}`). Nunca una cifra fija: el comprador de cada país ve su moneda.
- Compra: `<a href="/checkout">` o `<button data-checkout>`.
- Marcadores propios: `[[HERO]]`, `[[HERO-CLIC]]`, `[[OBRAS]]`, `[[IMG:nombre]]`, `[[CORREO]]`.

`python3 assets/armar_landing.py` rellena los marcadores con las URL de `publicar/urls.json` y escribe `publicar/landing.html`. Adaptar dentro del script: el correo de soporte y la lista de piezas de la sección de vistas previas.

Detalles que ya dieron problemas:
- El video lleva `width` y `height` como atributos para reservar el hueco; el CSS necesita `height:auto` y `aspect-ratio`, o mide 1350 px de alto.
- El control de sonido va como barra DEBAJO del video, nunca encima: tapaba los subtítulos. Tocar el video hace lo mismo que la barra.
- En móvil hay un botón fijo abajo con el precio; el pie necesita margen para que no lo tape.
- Si el referente tiene contador o precio tachado, ver `00-reglas-del-dueno.md` §2 antes de dejar el hueco.

## 4. Imágenes y video

- Hojas reales del producto renderizadas desde el PDF (`assets/render_hojas.sh`, que hay que adaptar a la ruta de la oferta).
- Fotos «en uso»: generadas con la hoja real como referencia; manos y mesa, sin caras.
- Portadas de los bonus y del kit.
- Video de cabecera: `08-creativos.md` §6.

Todo se sube a Recursos de Impultienda (`fragmentos-navegador.md` §3) y cada URL pública se anota en `publicar/urls.json`. Límites: 50 MB en total, 20 MB por video; las imágenes pasan a `.webp`.

### 4.1 Primera pantalla liviana y promesa igual a la de los anuncios (revisión del 12-nov)

- Solo el 63-66 % de los clics llegó a cargar la landing (pintado principal 2,6-4,2 s en 4G). La imagen o el póster de la cabecera va en `.webp` de menos de 150 KB, el video con `preload="metadata"` y nada pesado antes del primer botón. Medir con `scripts/probar_funnel.py` antes de dar la fase por hecha.
- El título de la cabecera tiene que hablarle a quien hablan los anuncios. En Oferta A los anuncios que vendían eran para docentes y la landing abría «para peques de 6 a 11 años» (padres). Si la tanda reparte dos públicos, la bajada nombra a los dos.

### 4.2 Opiniones reales (pedido del dueño, 12-nov)

Cuando hay compradores reales que escribieron (correo de soporte, encuesta), se agrega un bloque `#opiniones` con sus textos tal cual, nombre de pila e inicial, número de pedido guardado en `ofertas/_funnels/<Nombre>/opiniones/LEEME.md` y su permiso. Nunca antes de tenerlas, nunca editadas para vender más. Modelo: Oferta B (bloque 5b, entre contenido y uso).

## 5. Vista previa local

`publicar/landing.html` no trae `<head>`. Para revisarla antes de publicar: escribir `publicar/vista.html` (doctype + `meta viewport` + el cuerpo, con `{{price}}` y `{{original_price}}` sustituidos por cifras de ejemplo), servir `publicar/` con `assets/servir.py` (puerto 8791, entrada `landing-mx` en `.claude/launch.json`) y abrirla con `preview_start`. Medir con el fragmento 1 en móvil y escritorio y poner el resultado al lado del referente.

## 6. Publicar

1. Comparar la huella de lo publicado con el archivo local (`fragmentos-navegador.md` §4).
2. Pasar el HTML por gist, ponerlo en el `textarea`, comprobar que la huella es la del archivo, «Guardar cambios».
3. Borrar los gists.
4. Abrir la tienda pública en móvil y medir otra vez: el orden debe ser el del plano y `scrollW` igual al ancho del visor.
5. Abrir el checkout con «Ver como otro país» y comprobar moneda, precio y medios de pago del mercado.

## Hecho cuando

- Tabla lado a lado, referente y nuestra, con el mismo orden de bloques en móvil.
- La tienda pública carga el video, los precios salen en la moneda del mercado y el botón lleva al checkout.
- El píxel dispara `PageView` (se ve en `ads_get_dataset_stats` a los pocos minutos).

## Funnel quiz+vsl en una sola landing (tercera corrida, 2026-11-12)

Impultienda trae un «quiz con IA» propio, pero para modelar pantalla por pantalla se construyó el quiz dentro del HTML completo de la tienda. Plantilla probada: `ofertas/_borrador-oferta-c/05-landing/landing.plantilla.html`.

- Un único `<div>` con un «escenario» que dibuja un paso a la vez desde una lista `PASSOS`: `inicio`, `q` (una opción, avanza sola a los 260 ms), `m` (varias, botón «Próximo»), `a` (pantalla de ánimo con botón), `load` (barra que se llena en N ms), `sobre`, `grafico`, `resultado` (según respuestas) y `vsl`.
- Barra de progreso arriba, como el referente; desaparece en el video.
- La sección de oferta (mockup, qué incluye, bonus, `{{price}}`, botón a `/checkout`, garantía) está oculta y aparece cuando el video llega al segundo del tramo del precio (`REVELAR`, sale de `montar_vsl.py`) o al terminar; queda recordada en `localStorage` si vuelve.
- El video arranca mudo con un botón grande «toque para ouvir», que reinicia desde 0 con sonido. Barra de progreso real.
- `?cv_paso=N` abre directamente el paso N: sirve para capturar las pantallas del quiz para los anuncios (`Chrome --headless --window-size=500,889 --force-device-scale-factor=2.16` → 1080×1920).
- Eventos personalizados al píxel: `QuizInicio`, `QuizCompleto`, `VideoSom`, `OfertaVista`, `CliqueComprar`.
- Los UTM de la URL se copian al enlace del checkout.
