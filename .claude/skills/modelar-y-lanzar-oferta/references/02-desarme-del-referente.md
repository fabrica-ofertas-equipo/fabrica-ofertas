# Fase 3 · Desarme del referente

Salida: `modelado/desarme.md`. Es el plano de todo lo demás: la landing, los anuncios y el checkout se construyen contra este documento y se comparan con él al final. Modelo completo: `ejemplo-mx/modelado/desarme-referentea.md`.

Todo se lee con el navegador integrado, en una pestaña propia (`preview_start` con la URL) y pasando siempre el `tabId`. Los subagentes no usan el navegador: en México un agente de la inmersión navegó en la misma pestaña y un anuncio quedó sin leer.

## 1. Landing

1. `get_page_text` para el texto completo.
2. JavaScript de inventario: abrir todos los `<details>`, listar `video/audio/iframe` (con `duration`, `videoWidth`, `videoHeight`, `autoplay`, `muted`, `loop`), imágenes con su tamaño natural, `script[src]` (píxel, analítica), enlaces únicos (a dónde va el botón) y preguntas frecuentes.
3. Medición de bloques en móvil y en escritorio (`fragmentos-navegador.md` §1): secciones con su alto, y dentro de la cabecera el orden exacto de cada elemento.
4. Capturas en móvil cada 800 px, para tener la página a la vista al escribir.

Se escribe:
- Tipo de funnel según `taxonomia-funnels.md`: núcleo en orden, extras y lo no observado (en México: `tsl` con `video-apoyo` → checkout de Hotmart; sin quiz, sin bump ni upsell visibles).
- Tabla de secciones: número, nombre, alto, qué hace.
- Orden de los elementos de la cabecera y si es una o dos columnas.
- Video: proporción, duración, cómo arranca, dónde está el control de sonido, cómo cierra.
- Precio: cifra, ancla, descuento, contador, sellos.
- Paleta y tipografías (para tomar el clima, no para copiarlas).
- Por qué funciona, en tres o cuatro frases.
- **Qué no se copia y qué va en su lugar** (`00-reglas-del-dueno.md` §2). Este apartado se le dice al dueño en el momento, con la pregunta de la fecha de fin si quiere cuenta regresiva real.

## 1b. Si el funnel no es una página simple

El dueño prefiere modelar funnels complejos (`01-elegir-oferta-y-mercado.md` §1.2), así que esto va a ser lo habitual. La regla es la misma, hacer igual y mejorar, pero aquí «igual» son más piezas y hay que mapearlas todas antes de construir. Nada de esto se probó en México: lo que no funcione como está escrito se corrige aquí al terminar la corrida.

Recorrer el funnel entero como lo haría un comprador, sin escribir datos personales reales ni pagar, y dibujar el mapa: cada pantalla, qué la dispara y a dónde lleva.

**Primero, el tipo según la taxonomía.** El desarme empieza con una línea: tipo (`quiz+vsl`, `advertorial+tsl`…), núcleo en orden, extras y lo no observado, tal como salió de la búsqueda (radar o barrido por forma; `taxonomia-funnels.md`; `barrido_por_forma.py clasificar <URL>` da el punto de partida y la evidencia). Al recorrerlo entero se confirma o se corrige: si el funnel real tiene un componente más o en otro orden, se vuelve a encuadrar (`encuadrar --registrar`) y, si resulta un tipo nuevo, se le dice al dueño en ese momento. Cada componente del núcleo se mapea con su apartado de abajo; en un híbrido se mapean todos, y además la costura entre ellos (qué pantalla del quiz dispara el video, qué dice justo antes).

**Quiz funnel**
- Cada pregunta: texto, tipo (una opción, varias, deslizador, entrada libre), opciones, si hay imagen, y qué pantalla sigue según la respuesta. Recorrer al menos dos caminos distintos para ver si de verdad ramifica o si todas las respuestas llevan al mismo sitio.
- Pantallas intermedias: «analizando tus respuestas», barras de progreso, mensajes de ánimo, datos entre preguntas.
- Dónde pide correo o nombre, y si deja seguir sin darlo. Si lo pide, parar ahí con ese camino y anotarlo; no se rellena con datos inventados de una persona real.
- Página de resultado: qué personaliza (texto, gráfico, nombre del «plan») y con qué respuestas.
- Dónde aparece el precio por primera vez.
- Medir: número de preguntas, pantallas totales hasta la oferta.

**VSL**
- Duración total, proporción, si arranca solo, si deja adelantar.
- En qué segundo aparecen el botón y el precio (leer el script de la página: suele haber un temporizador que los muestra).
- Estructura del video por tramos con segundos (gancho, problema, historia, mecanismo, oferta, garantía, cierre), con hoja de contacto (`fragmentos-navegador.md` §2) y un cuadro cada 15-20 s si es largo.
- Qué hay debajo del video antes y después de que aparezca el botón.

**Híbridos (quiz + VSL, quiz + TSL, advertorial + VSL…)**
- Es lo que más aparece entre los quiz que venden un producto digital de pago único: las preguntas no llevan a un precio sino a un video o a una carta de ventas.
- Mapear el quiz como arriba y la segunda parte con su apartado. Anotar la pantalla de costura: en el caso visto (Mapa Relacional, `quiz+vsl`) eran dos pantallas de compromiso («¿te comprometes a seguir el paso a paso?»), un «según tus respuestas todavía hay una oportunidad», una barra «creando tu acceso…» y recién entonces el video de 2 minutos con el botón demorado hacia Hotmart.
- El resultado «personalizado» que es igual para todos se trata como en `00-reglas-del-dueno.md` §2.

**Funnel de varios pasos**
- Cada página con su URL, su función y su botón de salida (puente, advertorial, venta, checkout).
- Order bump: qué es, precio, texto, si viene marcado.
- Upsell y downsell tras el pago: solo lo visible sin comprar; lo demás se anota como «no visible».

Para cada pieza se escribe además cómo se construiría en Impultienda: el HTML propio admite JavaScript, así que un quiz o un video con botón demorado caben en la página; el plan Free admite un bono y un upsell. Lo que la tienda no permita replicar se le dice al dueño en este punto, con la alternativa más parecida, antes de producir.

Los apartados de qué no se copia siguen valiendo dentro de un funnel complejo: un resultado «personalizado» que es igual para todos, o una cuenta atrás que se reinicia, se tratan como en `00-reglas-del-dueno.md` §2.

**Leer siempre los scripts de la página, no solo lo que se ve.** Si los botones no son enlaces, el `.js` dice adónde van y qué pasa antes: en «Oferta B» el botón del nivel básico abría una oferta intermedia («llévate el completo por 4 dólares más», con un tercer checkout) y había una salida por intención a los 20 segundos; no lo vi porque anoté «los botones son JavaScript; no se siguió». El script también dice cómo funciona el contador (si guarda algo, qué pasa al llegar a cero). Las ofertas que suben el ticket (antes, durante y después del pago) se buscan con `11-ofertas-que-suben-el-ticket.md`.

## 2. Anuncios

Con 50, 60 o 100 anuncios activos no se abre ficha por ficha: se agrupan primero por título y texto (el conector los devuelve), se cuenta cuántos hay de cada grupo y se abre una muestra de cada uno, empezando por los más antiguos, hasta tener visto entero al menos un video por familia y duración. La mezcla se calcula sobre todos; el plano por plano, sobre la muestra, diciendo cuántos se vieron de cuántos. El conector entrega como máximo 50 por llamada, los más recientes primero: si hay más, decir que el recuento de familias es sobre esos 50 más los que el barrido ya tenía.

### 2.0 Cuántos anuncios se ven enteros y cuáles (regla del dueño, 2026-11-11)

**Mínimo 13-15 videos vistos de punta a punta, repartidos entre los MÁS VIEJOS, los INTERMEDIOS y los MÁS NUEVOS.** No los primeros que salgan en la lista ni los últimos por orden. Palabras del dueño: «no de los últimos en orden, sino de los más viejos, de los intermedios y de los nuevos, para modelar bien». Con el mismo texto y título en todos, agrupar por texto no alcanza: la variedad está en el video.

Por qué: en la segunda corrida vi 3 videos, todos de la misma tanda y formato, concluí «una sola familia» y los 10 anuncios nuestros salieron casi iguales (7 tomas en los diez). Al ver 16 más aparecieron tres formatos, 13 ganchos en 18 videos y una evolución clara por tanda. El dueño lo notó antes que yo.

Procedimiento que funcionó (20 minutos para 16 videos):

1. Abrir la página del anunciante en la Biblioteca con `country=ALL&media_type=video` y cargar la lista ENTERA (desplazar hasta que el recuento deje de crecer; a veces se queda quieta unos segundos y luego sigue).
2. Sacar de cada tarjeta ID, fecha de inicio, dominio de destino e idioma, y quedarse con los de la oferta. Contar cuántos hay por fecha de inicio: esas son las **tandas**.
3. Elegir la muestra repartida por tanda (más de la más vieja y de la más grande) y, dentro de cada tanda, por puesto de impresiones (de los primeros, del medio y de los últimos). Incluir alguna versión en otro idioma.
4. Hoja de contacto de cada uno sin salir de la lista (`fragmentos-navegador.md` §2, variante `__hoja3`: un cuadro grande a los 2 s para leer el gancho y 18 cuadros repartidos). Una captura por video.
5. Anotar por video: formato, gancho en pantalla, tomas de apertura, cuerpo, cierre, duración. Guardar la tabla en `modelado/anuncios-muestra.md` mientras se avanza.

Lo que hay que sacar de la muestra, con números:
- **Formatos** y su proporción (montaje con locución, persona a cámara, pantalla partida, recuadro, imagen fija…).
- **Cuántos ganchos distintos** hay por cada tantos videos.
- **Qué es propio de cada video y qué se comparte**: qué tomas se repiten y en cuántos videos, cuántas tomas de apertura son únicas.
- **Cómo evolucionó de una tanda a otra** (estilo de rótulos, ganchos nuevos, remezclas): lo más nuevo dice hacia dónde va el anunciante; lo más viejo que sigue vivo dice qué aguanta.
- Variantes de cierre y rango real de duraciones.

1. `ads_library_search` por `page_ids`, activos: lista de fichas con `ad_snapshot_url` y fecha de inicio.
2. Abrir cada ficha (`facebook.com/ads/library/?id=<ID>`) en su pestaña. Necesita que el dueño lo haya autorizado en la conversación si hay freno de captura puesto.
3. Por ficha: texto principal y título (del diálogo), y hoja de contacto del video (`fragmentos-navegador.md` §2) con un cuadro cada 3-5 s, que también da la duración exacta.
4. Leer en la hoja de contacto: qué se ve en cada plano, cuánto dura, qué dice el subtítulo, cómo cierra.

Se escribe:
- Tabla: ID, desde cuándo corre, duración, formato visual, familia, qué texto y qué título lleva.
- Los textos distintos que hay (en México eran tres: padres corto, padres largo, docentes) con su esqueleto: apertura, qué enumera, viñetas, llamada.
- **Mezcla**: cuántos anuncios de cada familia y el rango de duración de cada una. Esta línea es la que manda en la fase 9.
- Estructura plano por plano de cada video, con segundos.
- Lectura para modelar: qué tipo de creativo aguanta, cuántos públicos, cuál es el plano de cierre común.
- Qué no se copia (voz de comprador, caras de niños, la trama literal de un cuento).

Clasificar bien cada video importa: en México uno se anotó como «demostración» sin haberlo visto entero y era un cuento ilustrado de 1:37; se corrigió al hacer las hojas de contacto. No se clasifica un video que no se vio completo.

## 3. Oferta base

Qué entrega exactamente (piezas, cantidad, formato), bonus, precio, garantía, forma de entrega. Es lo que se replica; el precio del principal sale de la regla 19/27, máx(19 USD, precio del referente) (`06-tienda-impultienda.md` §3).

## 4. Checkout

Abrir el checkout del referente sin comprar ni rellenar datos. Anotar: columnas, bloques añadidos (imagen, video, gente usando el producto, sellos), campos que pide, temporizador, order bump. En México era el de Hotmart sin bloques, así que no hubo nada que replicar más allá de la configuración del dueño.

Lo que no se ve sin comprar (bump tras el pago, upsell, correos) se anota como «no visible».

## Hecho cuando

- `modelado/desarme.md` tiene las cuatro partes, con cada video visto entero.
- Está escrita la línea de mezcla y duraciones.
- El dueño sabe ya qué elementos del referente no se van a replicar y qué se pondrá en su lugar.

## Etapa del funnel en la tabla de mezcla (2026-11-13)

En la tabla de mezcla de anuncios del referente, añadir dos columnas por pieza: **etapa** (frío: abre con gancho o problema / cierre: producto + precio, oferta, urgencia) y **destino** (producto estrella, paquete, otra página). Descontar las piezas de temporada. Ver `08-creativos.md` §1.3.
