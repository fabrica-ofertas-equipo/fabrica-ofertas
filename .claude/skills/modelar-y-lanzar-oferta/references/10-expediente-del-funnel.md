# Fase 8 bis · Expediente del funnel

Pedido del dueño (2026-11-11): al terminar la landing y dejarla en la tienda, guardar en una carpeta **con el nombre tal cual figura en la tienda** todo lo necesario para reconocer el funnel: la landing original que se modeló, el HTML de la landing nueva que se pegó, y el detalle de los testimonios y recursos de urgencia y escasez que quedaron fuera de la modelación.

Salida: `ofertas/_funnels/<Nombre en tienda>/`. Modelos: `ofertas/_funnels/Oferta B/` y `ofertas/_funnels/Oferta A/`.

Se hace justo después de publicar y verificar la landing (fase 8), y se actualiza si la landing vuelve a publicarse.

## 1. Armar la carpeta

```bash
python3 .claude/skills/modelar-y-lanzar-oferta/scripts/expediente_funnel.py \
  --oferta ofertas/_borrador-<slug> --tienda "<Nombre en tienda>" \
  --original <URL del referente> --publica https://<tienda>.impultienda.ar/
```

Deja:

- `landing-original/` · `pagina.html`, los `.js` y `.css` propios del sitio y `captura-movil.png`. Es material ajeno: se guarda para análisis, no se ejecuta ni se republica.
- `landing-nueva/pegada-en-tienda.html` (con su sha1) y `publicada-<fecha>.html` (lo que sirve la tienda). El script dice si lo pegado sigue dentro de lo publicado: si no, otra herramienta publicó encima; guardar también esa versión y decirlo en la ficha.
- Esqueletos de `FUNNEL.md` y `no-modelado.md`, y una lista de pistas (qué recursos de urgencia y prueba social detectó en el HTML y en los scripts del referente).

## 2. `FUNNEL.md`: la ficha

Una tabla para reconocerlo de un vistazo (nombre en tienda, producto, comprador, mercado, referente y su landing, tipo según `taxonomia-funnels.md`, carpeta de trabajo), el recorrido del comprador paso a paso con URL y precios, los identificadores (tienda, fan page, píxel, campaña, conjunto) y qué hay en la carpeta.

## 3. `no-modelado.md`: solo lo que quedó fuera por ser falso en nuestra tienda

**Cambio del 2026-11-12 (pedido del dueño: «sé más ordenado y dejame capturas con antes y después… con un círculo o marcando qué cosa no se modeló y en dónde debería ir»):**
- Lo no modelado vive en una carpeta, `no-modelado/`, con:
  - `LEEME.md`: índice con N.º, elemento, dónde está en el original, entre qué bloques iría en la nuestra, por qué no se puso, alternativa verdadera e imagen;
  - una imagen `NN-<slug>.png` por ítem: a la izquierda, el original en móvil con el elemento marcado en rojo; a la derecha, nuestra página en el mismo tramo con un recuadro punteado donde iría;
  - `detalle.md`, con el texto largo descrito abajo.
- `no-modelado.md`, en la raíz del expediente, queda como un apunte a `no-modelado/LEEME.md`.
- Las capturas se hacen con Playwright (iPhone 390×844). Las marcas se inyectan en la página antes de capturar y el lado a lado se compone capturando un HTML local. Modelos: los tres expedientes de `ofertas/_funnels/`.

Alcance fijado por el dueño (2026-11-11): «no agregues cosas como ofertas intermedias a este documento, solo cosas relacionadas con testimonios, urgencia, escasez y cosas que por políticas no agregaste». Entra: reseñas y testimonios, contadores, «tiempo limitado», escasez, precio «antes» que nunca se cobró, valores en dinero de los bonus, cifras de clientes, porcentajes de elección, «más vendido», avisos de actividad en vivo, voz de comprador o testimonio a cámara en los anuncios, caras de menores.

**No entra** lo que es estructura del funnel o presentación (pasos intermedios, ofertas de salida, garantía, formatos, animaciones, rastreo): eso va al desarme de la carpeta de trabajo (`modelado/desarme.md`), como diferencias encontradas, y se le cuenta al dueño aparte porque sí se puede modelar.

Se escribe contra la copia guardada, no de memoria, y **leyendo los scripts** del referente (el `.js` dice cómo funciona el contador y qué pasa al llegar a cero).

Arriba de todo, **el mercado donde corre la oferta** (pedido del dueño, 2026-11-11): país entero, idioma, moneda, precios, medios de pago, campaña con su presupuesto, público, inicio programado (00:00 hora del mercado y hora de Argentina) y dónde pauta el referente. El mismo dato va resumido en la fila «Mercado» de `FUNNEL.md`.

Después, tres apartados: en la landing, en los anuncios, en el checkout. Por cada recurso, cinco datos: dónde está en la página · cómo se ve y cómo está hecho (texto fijo, script, clases, archivos; si enlaza a algo verificable) · con qué enfoque (qué intenta que haga el comprador) · por qué quedó fuera y qué se puso en su lugar · qué haría falta para tenerlo de verdad.

Para las reseñas, una tabla con cada una: nombre, fecha, tipo de avatar, y qué función o bonus del producto vende esa reseña. Decir si imitan el formato de un tercero (Google, Trustpilot) y si enlazan a una ficha real.

El documento describe; no contiene reseñas escritas para nosotros, ni código de contador, ni cifras propuestas. Lo que el dueño decida encender en su tienda es suyo.

## Hecho cuando

- La carpeta lleva el nombre exacto de la tienda y tiene las tres piezas: original, nueva y `no-modelado.md`.
- `FUNNEL.md` permite reconocer el funnel sin abrir nada más.
- Cada pista que marcó el script está descrita o descartada con motivo.
- Las diferencias de estructura que aparezcan al leer la copia (pasos, ofertas, garantía) están en el desarme y se le dijeron al dueño aparte.
