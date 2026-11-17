# Fase 5 · Marca, fan page y píxel

Estructura fija del dueño: un portfolio comercial, una cuenta publicitaria, y por cada oferta una marca, una fan page y un píxel propios. Sin cuenta de Instagram. Todo esto se hace en el navegador integrado con la sesión de Facebook que abre el dueño; el conector de Meta no crea páginas ni píxeles.

## 1. Nombre de la marca

Corto, en el idioma del mercado, que diga de qué va el producto y no se parezca al del referente. En México: «Oferta A».

No se comprobó entonces si el nombre estaba registrado o si ya había una página con ese nombre. Hacerlo ahora: buscar el nombre en Facebook y en un buscador del país, y decir el resultado.

## 2. Fan page

1. `ads_get_ad_account_pages` y `ads_get_user_pages` para ver qué páginas hay.
2. Si el navegador no tiene sesión de Facebook, abrir `https://www.facebook.com/` y pedir al dueño que entre.
   Ruta que funciona (probada el 2026-11-11): Business → `business.facebook.com/latest/settings/pages?business_id=<id>` → Agregar → «Crear una nueva página de Facebook». Queda dentro del portfolio. La ruta vieja `facebook.com/pages/creation/` puede responder «contenido no disponible».
3. Crear: nombre, categoría (escribir el comienzo y elegir del desplegable; en México «Tienda de artículos educativos»), presentación de unos 100 caracteres. En el asistente posterior: foto y portada; omitir WhatsApp e invitar amigos; desmarcar los correos promocionales.
4. Perfil y portada: maquetarlos en HTML con las tipografías y colores de la marca (`marca/perfil.html` 800 px, `marca/portada.html` 1640×624) y sacar la imagen con Chrome sin pantalla.
5. **Diez publicaciones, no tres** (dueño, 14-nov: «la fanpage es el único activo al que la gente puede entrar desde el anuncio: que vea actividad»). Cada una con una pieza real del producto (1080×1080) y un texto de 150-250 caracteres en el idioma del mercado. Son muestras del producto, consejos y fragmentos de la guía, no reseñas ni historias de clientes.
   - **3 de entrada**, antes de crear los anuncios, para que la página no esté vacía.
   - **7 programadas y espaciadas** (Meta Business Suite → Crear publicación → Programar): una cada 8-12 h desde el día del lanzamiento, en horas de actividad del mercado (8-22 h locales), para que durante el test la página se vea viva. Nunca las 10 de golpe.
   - Anotar en `estado.md` las 10 con su fecha y hora de salida; si una falla, rehacerla en la siguiente vuelta.
   - En las réplicas a otro país, cada página nueva lleva sus 10 publicaciones en su idioma.
6. Sumar la página al portfolio: `business.facebook.com/latest/settings/pages?business_id=<id>` → Agregar → página existente → pegar la URL. ~~Aceptar condiciones de Meta es un paso que confirma el dueño.~~ Ver «Condiciones de Meta» abajo.
7. Anotar el `page_id` (sale en `ads_get_user_pages`; en `ads_get_ad_account_pages` puede tardar en aparecer).

### Subir imágenes a Facebook desde el navegador integrado

La página de Facebook no deja leer archivos locales ni hosts externos corrientes. Lo que funcionó, después de tres intentos fallidos:

1. Subir el archivo a un alojamiento temporal (el de Kie: `rk._cliente_real(None)[0].subir(ruta)` en `scripts/imagenes/ranuras_kie.py`).
2. `ads_creative_upload_media` con `upload_source: "URL"`, `media_type: "IMAGE"` → la respuesta trae una URL de `fbcdn.net`.
3. En la pestaña de Facebook: `fetch` de esa URL (ese host sí está permitido) → `File` → `DataTransfer` → `input[type=file]` + evento `change`.

Para perfil y portada también sirve dibujar la imagen con `canvas` dentro de la propia página y entregarla al `input` con `canvas.toBlob`.

Efecto lateral: las imágenes quedan en la biblioteca de la cuenta publicitaria.

No funcionan: pegar con el teclado, `navigator.clipboard.read()`, `fetch` directo al alojamiento temporal.

## 2 bis. Condiciones de Meta: autorización permanente del dueño (2026-11-14)

Dueño: «poné en la regla que siempre lo hagas y que tenés la autorización para habilitar estas cosas siempre». Al crear la fan page y el píxel de una oferta en el portfolio Never Give Up:

- en «Crear página de Facebook» → paso «Confirmar»: marcar «Acepto las Condiciones comerciales de Meta y las Políticas de páginas, grupos y eventos…» y pulsar «Crear página»;
- en «Crear un nuevo conjunto de datos»: pulsar «Crear» aunque diga «Al continuar, aceptas las Condiciones de las herramientas empresariales de Meta».

No se frena ni se avisa por esto. El 14-nov dos ofertas (Oferta G y Oferta J) quedaron armadas sin salir porque la corrida automática paró en esa casilla. Alcance: solo esos dos diálogos. Otras condiciones, permisos de aplicaciones, medios de pago o verificaciones siguen siendo del dueño.

## 3. Píxel

1. `ads_get_datasets` para ver los que hay. No reutilizar el de otra oferta ni uno inactivo.
2. Crear en `business.facebook.com/latest/settings/events_dataset_and_pixel?business_id=<id>` → Agregar → nombre «<Marca> Pixel» → asignarlo a la cuenta publicitaria.
3. Confirmar con `ads_get_datasets` y anotar el `dataset_id`. **Ese es el ID del píxel**: el número de `selected_asset_id` que aparece en la URL de Business al crearlo es otro y Meta lo rechaza («Pixel Can't Be Used»). En la cuarta corrida se cargó ese número en tres tiendas y hubo que corregirlas.
4. Se carga en la tienda en la fase 7, **con la API de conversiones** (`06-tienda-impultienda.md` §5.1).
   - El dueño genera el token en el Administrador de eventos y lo pega en la tienda; yo dejo abiertas las dos pantallas y compruebo después.
   - Sin token, Meta solo ve los eventos del navegador. El 12-nov eso hizo que una venta real no se atribuyera a ningún anuncio.

## 4. Cuenta publicitaria

`ads_get_ad_accounts`: debe figurar `ACTIVE` y con método de pago. Si no, avisar ya. Hay otra cuenta en el portfolio sin método de pago y una deshabilitada: no usarlas.

## Hecho cuando

- Página con perfil, portada y 3 publicaciones hechas + 7 programadas y espaciadas, dentro del portfolio; `page_id` anotado.
- Píxel creado y asignado a la cuenta; `dataset_id` anotado.
- Estado de la cuenta publicitaria comprobado y dicho.
