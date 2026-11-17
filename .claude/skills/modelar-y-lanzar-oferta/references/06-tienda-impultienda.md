# Fase 7 · Tienda en Impultienda

Todo se hace en el navegador integrado con la sesión del dueño. Si el panel redirige a `/login`, abrir `https://impultienda.ar/login` y pedirle que entre (con Google); la sesión se cae cada pocas horas, así que conviene pedirlo al empezar esta fase y otra vez antes de publicar.

Regla del panel: **cada pantalla tiene su propio botón Guardar**. Después de cada cambio: guardar, recargar y leer el valor para confirmar.

Mapa de rutas del panel: `docs/_historial/impultienda/rutas-del-frontend.json`.

## 1. Crear la tienda

`/dashboard/nueva-tienda` → asistente de cinco pasos:

- **Idioma**: el del mercado, con su variante («Español (México)»). Se elige aquí y no se puede cambiar después.
- Nombre de la marca y subdominio (`<marca>.impultienda.ar`).
- Correo de contacto: **soporte@tu-dominio.com** (correo genérico del dueño desde el 2026-11-12; reenvía a su Gmail por Cloudflare Email Routing). Impultienda valida que el dominio tenga MX antes de guardarlo. En la landing va en el pie (marcador `[[EMAIL-SOPORTE]]`).
- En Contenido, omitir los textos de IA: se pega HTML propio.

Anotar la URL pública y el `store_id` (aparece en las URL de los recursos).

Plan: desde el 2026-11-11 la cuenta está en «Plan Max», con 10 tiendas (el panel muestra «1 de 10 usada»). La oferta de México se hizo en plan Free (1 tienda, 1 bono, 1 upsell, 5 % de comisión) y por eso sus bonus van dentro de un solo PDF. Los límites de bonos, upsells y comisión del plan Max no se han leído: mirarlos en el panel al crear la tienda antes de decidir cómo empaquetar los bonus. Nunca archivar una tienda existente para hacer sitio sin decírselo al dueño.

`/dashboard/nueva-tienda` ofrece también «Copiar una tienda que ya tengo» (misma landing y ebooks en otra moneda): no sirve para una oferta nueva, sí para llevar una oferta ya hecha a otro mercado.

## 2. Cobro

`/dashboard/<tienda>/configuracion` → pestaña Pagos:

1. Moneda: **Multidivisa** (cada comprador ve su moneda; se liquida en USD).
2. Procesador: **Impul Pay** (el dueño cobra por Impul Pay o por Stripe, siempre a través de Impultienda). La tienda suele nacer cobrando en pesos argentinos aunque se elija otra cosa en el asistente: «Cambiar modo» → Multidivisa, y luego «Copiar de otra tienda» para traer Impul Pay de una tienda que ya lo tenga.
3. Mirar qué medios locales ofrece para el país elegido (en México: tarjeta, Google Pay, OXXO y SPEI; en Brasil: tarjeta, Pix y Boleto). **Se comprueba con la vista previa del checkout por país** (`preview_country=XX`), bajando hasta debajo de la tarjeta y **con captura de pantalla**: los medios se dibujan dentro de un cuadro de Whop y el texto de la página (`get_page_text`, `innerText`) no los ve. Una nota vieja no se repite como hecho sin volver a mirar (`tropiezos.md`, cuarta corrida).

Si falta conectar una pasarela, es paso del dueño: avisarle cuál.

### 2b. Stripe: solo en las tiendas que lo necesitan (dueño, 14-nov)

El dueño tiene cuenta de Stripe de EE. UU. y la regla es «tener como válido Stripe y solo conectarlo en las tiendas que vamos a lanzar con método de Stripe». Stripe se conecta **por tienda** (Impul Pay es una sola cuenta para todas; Stripe, PayPal y MercadoPago van tienda por tienda).

- **Cuándo:** solo si `elegir_mercado.py` imprimió «REQUIERE STRIPE» para el país elegido (hoy: Polonia por BLIK y Przelewy24, España por Bizum, Austria por EPS, Alemania por Klarna, Corea, India por UPI, Finlandia, Honduras y Panamá; la tabla es `STRIPE_MEJORA`). Si dice «Stripe: no hace falta», la oferta sale solo con Impul Pay.
- **Dónde:** en todas las tiendas de ESA oferta (principal, niveles y subida previa), en la fase de tienda. **Nunca** en una tienda apagada, pausada o que se va a archivar, ni «para tenerlo conectado».
- **Cómo:** Configuraciones → Pagos → tarjeta de Stripe → «Configurar» → «Conectar con Stripe» (OAuth en connect.stripe.com con la sesión del dueño en el navegador integrado; contraseña y códigos son del dueño, nunca del asistente). En las otras tiendas de la misma oferta, «Copiar de otra tienda» → Stripe (misma cuenta), desde la principal recién conectada. Después `impultienda_metodos_locales_stripe` (vista previa → confirmar) en cada una, con la tienda en Multidivisa o Markets en la moneda local (BLIK solo aparece en PLN, Bizum en EUR desde España).
- **Comprobar:** `impultienda_estado_pasarela` con `pasarela: stripe` (configurada y operativa) y la vista previa del checkout del país con captura: el método local tiene que verse.
- **Si no se puede conectar ese día** (falta la sesión del dueño en Stripe, la cuenta tiene requisitos pendientes): no se lanza un mercado de Stripe sin Stripe. Se vuelve a ordenar con `elegir_mercado.py ordenar … --sin-stripe`, se toma ese ganador y se avisa al dueño qué hace falta en Stripe.
- Una tienda con Stripe e Impul Pay muestra las dos filas; en «Orden de los métodos de pago» va primero la que trae el método local del país (Stripe en Polonia o España).

### Si el referente vende en dos niveles

El checkout no admite llegar con un complemento ya agregado, así que el nivel bajo va en una segunda tienda: se termina la tienda principal (nivel completo, con la landing), se duplica con `/dashboard/duplicar-tienda` (moneda USD, subdominio `<marca>-basico`) y en la copia se configura cobro (Cambiar modo → Multidivisa; Copiar de otra tienda → Impul Pay), píxel, market y precios. El botón del nivel bajo en la landing apunta al `/checkout` de la copia; su precio va escrito a mano porque el token solo conoce el precio de la tienda donde vive la página.

Orden que ahorra subidas: cargar en la tienda principal el producto del nivel bajo con su complemento y sus PDF, duplicar, y después convertir el principal al nivel completo (título, precio, PDF) y marcar su complemento «solo post-compra».

Si el referente tiene una **subida antes de pagar** (ventana al elegir el paquete barato), va una tercera tienda con el paquete caro al precio rebajado: ver `11-ofertas-que-suben-el-ticket.md`. Al duplicar, volver a subir las imágenes (la copia las trae rotas). Incluye **la imagen del producto principal** (la que muestra el checkout): el 14-nov las 6 tiendas de Oferta H y Oferta I, duplicadas de Oferta F, salieron con esa imagen rota y nadie lo vio hasta la revisión; se sube con `impultienda_editar_producto` (imagen «subir» → PUT → «confirmar») usando el mockup de `04-producto/mockups/elegidos/`. `verificar_funnel.py --antes` lo detecta y frena la activación.

## 3. Producto y precios

`/dashboard/<tienda>/personalizacion/ebooks` → producto principal → «Precio, título y más»:

- Título y descripción en la voz del mercado.
- **Precio en USD (regla del dueño, 2026-11-12):** el producto principal cuesta **el mayor entre 19 USD y el precio del producto principal del referente**. Se acabó el ticket de 17.
  - Referente a menos de 19 → 19.
  - Entre 19 y 27 → su precio.
  - Más de 27 → su precio.
  - En moneda local va un precio redondo cercano: Brasil R$ 99, México MX$ 359.
  - El mismo precio tiene que estar en la landing (texto y respaldo por huso horario) y en el video de venta si lo dice en voz. Revisarlo antes de grabar la locución, no después.
  - Los niveles baratos (básico, oferta intermedia) y los upsells no se rigen por esta regla.
- **Precio original**: lo carga el dueño. Criterio que usó en México: ≈2.9 veces el precio, terminado en 9 (17 → 49 USD; 319 → 899 MXN). Yo no invento ese número: le recuerdo que el campo existe y uso `{{original_price}}` en la landing para mostrar lo que él cargue.
- **Imagen del producto**: siempre. Se ve en el resumen del checkout. El `input` aparece solo al pulsar «Subir imagen» (`fragmentos-navegador.md` §3).
- **Archivo**: el PDF, por el método de gists (un archivo de 17 MB son 8 trozos; esperar unos 20 s tras el `change`).

Precio por mercado: `/dashboard/<tienda>/markets` → activar modo Markets → crear el market del país con su moneda → en el editor del producto, «Precios por mercado»: la cifra local a mano, terminada en 9 (la conversión automática sugería 316 y se puso 319). También el precio original de ese mercado.

Los países sin market caen a USD con conversión automática.

## 3.1 Bonos y upsells (regla del dueño, 2026-11-11)

**Los bonus de la oferta se cargan SIEMPRE como bonos** (`/personalizacion/ebooks` → «Agregar bono (n/5)» en plan Max), no solo dentro del PDF principal. Las dos primeras ofertas salieron sin ningún bono cargado y el dueño lo marcó. Con bonos cargados el checkout muestra «+N bonos gratis» y la lista de bonos, y cada uno llega como archivo propio.

Por cada bonus:

1. Un PDF propio (si el generador saca uno solo, partirlo con PyMuPDF por las portadillas) y una portada **vertical** (la tarjeta recorta las apaisadas: si la portada es apaisada, montarla centrada sobre un lienzo 900×1200 del mismo color de fondo).
2. «Agregar bono»: nombre y descripción en la voz del mercado. No pulsar «Generar con IA».
3. En la tarjeta nueva hay `input[type=file]` de imagen y de PDF: subir los dos por el método de gists. Debe pasar de «Sin contenido» a «Listo». Recargar y volver a leer.
4. **«Valor percibido» se deja vacío.** Es el precio tachado del bono; con cualquier cifra el checkout suma los valores, tacha el total y escribe «Ahorras X». Es un campo del dueño, igual que el precio original: recordarle que existe.
5. Ver el checkout como comprador del país y leer el resumen.

Si la tienda tiene dos niveles (ver arriba), los bonos van en la tienda del nivel completo; en la del nivel bajo son el complemento de pago.

**Upsells post-compra: no se crean al lanzar.** El dueño los habilita después del test, cuando el producto principal ya convierte («backend ofensivo» para subir el ticket promedio). Excepción: lo que el funnel del referente ya traiga como parte de su estructura (complemento en el checkout, niveles). Nunca dejar un upsell que venda algo que el producto principal ya incluye.

## 4. Checkout, como lo deja el dueño

`/dashboard/<tienda>/personalizacion/diseno-checkout`. Configuración que él guardó en México y pidió respetar en las próximas tiendas:

| Ajuste | Valor |
|---|---|
| Plantilla | «Impultienda» (la clásica) |
| Bloques arriba y abajo | Ninguno, salvo los que tenga el checkout del referente |
| Resumen de compra | «Abajo de todo» |
| Anuncio de bonos | «Cantidad» |
| Sellos | «Clásico», garantía visible de 7 días |
| Colores | Por defecto |
| Barra superior «Checkout seguro» con candado | Sí |
| Wallets arriba | No |
| Datos del comprador | Solo correo |
| Order bump | Tarjeta «Clásica», con descripción |
| Barra «X personas están comprando» y temporizador del bump | Los enciende él. Yo los dejo como estén y le aviso que existen |

Leer el estado de cada interruptor antes de tocarlo (`fragmentos-navegador.md` §5).

Modelar el checkout del referente: si el suyo tiene bloques (imagen, video, gente usando el producto), replicarlos con «Agregar bloque» y contenido propio.

## 5. Píxel

`/dashboard/<tienda>/configuracion` → «Meta / Tracking» → «Meta Pixel ID» → Guardar → recargar y leer.

**Siempre un píxel propio por oferta, réplicas incluidas, cargado por el panel en el navegador** (dueño, 14-nov: «Píxel propio» y, al ver que Oferta H y Oferta I salieron con el de Oferta F: «cada oferta tiene que tener su público»). **Por qué:** el píxel aprende de quién compra; Meta usa esos datos para decidir a quién mostrarle los anuncios. Con el píxel de otra oferta (o de la madre, en una réplica a otro país) la campaña nueva arranca buscando compradores de otro producto o de otro mercado y los públicos se mezclan. Solo los niveles de una misma oferta en su mismo país (las tiendas de `ficha.tiendas` de una fila) comparten píxel. **Nunca prestar el píxel de otra oferta** (se retiró el plan B de `pixel_de_otra_tienda`): si el panel no lo guarda, la oferta queda «armado», se avisa y la vuelta sigue con otra candidata. `control_previo.py` frena la activación si el píxel aparece en otra fila del libro. No usar el conector (`impultienda_configurar_tracking`) para un píxel nuevo: desde el 13-nov lo deja «pendiente de aprobación del dueño» (pasó con Oferta G el 14-nov). El panel, con la sesión del dueño abierta en el navegador integrado, lo guarda al instante. Si una oferta ya salió con un píxel ajeno y todavía no tiene compras propias, se corrige: píxel nuevo en sus tiendas, conjunto nuevo en la misma CBO con el píxel nuevo y los mismos anuncios, y el conjunto viejo en pausa (un conjunto publicado no cambia de píxel). El token CAPI del píxel propio lo pega el dueño (§5.1): anotarlo en el libro como pendiente suyo (`libro.py set "<oferta>" pendientes '[{"que": "Pegar el token CAPI del píxel <id> en <tiendas>", "desde": "<ahora>"}]'`) para que aparezca en «Te toca» del panel. El ID es el `dataset_id` de `ads_get_datasets`, **nunca** el número `selected_asset_id` de la URL de Business (`04-marca-y-activos-meta.md` §3).

### 5.1 API de conversiones: obligatoria desde el 2026-11-12

Pedido del dueño: «vincular la API de conversiones aparte del píxel en cada funnel». Sin ella, Meta no atribuyó una venta real de Oferta B que el píxel sí recibió, y la campaña optimiza con menos señal.

- **Dónde está:** Impultienda envía los eventos desde su servidor si la tienda tiene el token del píxel.
  - El campo está en la misma pantalla: «Token de API de Conversiones (CAPI)», placeholder «Token de CAPI de ESTE pixel (opcional)».
  - Cada píxel usa su propio token. Si varias tiendas comparten píxel (niveles básico y completo), va **el mismo token en todas**.
- **Quién hace qué.** El token es una credencial: yo no la genero ni la pego.
  - **Lo preparo yo:**
    - abro en el navegador integrado el Administrador de eventos del píxel, `https://business.facebook.com/events_manager2/list/pixel/<dataset_id>/settings`, y bajo hasta «Generar token de acceso»;
    - abro también la pantalla «Meta / Tracking» de cada tienda que usa ese píxel.
  - **Lo hace el dueño:** en «API de conversiones» → «Configurar integración directa» marcar **«Configurar sin Dataset Quality API»** → «Generar token de acceso» → copiar → pegar en el campo CAPI de cada tienda de ese píxel → «Guardar cambios».
  - **Tropiezo del 12-nov:** con la opción por defecto («Configurar con Dataset Quality API», marcada como recomendada) se abre un selector de conjuntos de datos.
    - Viene con 5 píxeles de otros negocios ya marcados.
    - Los píxeles nuevos no aparecen.
    - No generar el token ahí: daría acceso a píxeles ajenos al funnel. Cerrar y usar «sin Dataset Quality API», que genera un token solo para ese píxel.
  - Se pide en el mensaje inicial de la corrida, junto con las sesiones (`00-reglas-del-dueno.md`), para que quede antes de activar.
- **Comprobar sin leer el token.**
  - En la tienda, recargar y mirar solo **si el campo tiene contenido**: `input.value.length > 0`, nunca el valor.
  - En Meta:
    - `ads_get_dataset_stats` del píxel con `event_source=SERVER_ONLY` tiene que mostrar eventos del servidor después de la primera visita o checkout real. Si los muestra, la conexión funciona;
    - `ads_get_dataset_quality` (`web`) da la calidad de coincidencia y la cobertura por clave.
  - Lo más claro es `aggregation=event_source`, que separa SERVER y BROWSER por hora.
    - Los tramos por hora tardan en aparecer: el de la hora en que se pegó el token recién se ve 40-60 min después.
    - Un tramo vacío antes de eso no es una falla.
    - Ojo: el total por evento **suma** las dos fuentes. Un Purchase que llega por navegador y por servidor cuenta 2 en `dataset_stats`; Oferta B mostró 10 Purchase para 6 ventas el 12-nov.
    - Eso no prueba duplicación: Meta deduplica al atribuir. El control es comparar `omni_purchase` de la campaña con las ventas reales de Impul Pay: con 4 atribuidas para 6 ventas, no hay doble conteo.
    - Calidad de coincidencia del Purchase con CAPI: 8,3 (`ads_get_dataset_quality`, con correo, nombre, ciudad, fbc y fbp al 100 %).
  - Una prueba propia no sirve: bloquea el píxel del navegador y el servidor puede no enviar un PageView de prueba. Esperar tráfico real o la compra de prueba del dueño.
- **Deduplicación.** Si después de conectar, las **compras atribuidas por Meta** en la campaña superan las ventas reales de Impul Pay, la plataforma no está mandando el mismo `event_id` en navegador y servidor. No usar el total de `dataset_stats` para esto: suma las dos fuentes. Avisar al dueño y al soporte de Impultienda; no desconectar por cuenta propia.

## 6. Recursos

`/dashboard/<tienda>/personalizacion/diseno/recursos`: 50 MB entre todas las tiendas, video de hasta 20 MB, las imágenes pasan a `.webp`. Cada URL pública (`sb.impultienda.ar/storage/…/<store_id>/<marca de tiempo>_<nombre>`) se anota en `05-landing/publicar/urls.json`, que es de donde arma la landing.

Lo que queda sin uso (un video viejo, por ejemplo) ocupa cuota: decirlo; borrar es decisión del dueño.

## 7. Comprobar como comprador del país

Desde otro país, `/checkout` muestra USD. Para ver lo que ve el comprador del mercado: en el editor del checkout, «Ver como otro país», o la URL `https://<tienda>.impultienda.ar/checkout?store_id=<store_id>&edit=1&tpl=default&extop=0&preview_country=XX`.

Comprobar: prefijo de teléfono del país, precio en la moneda local, precio original tachado si lo hay, y qué medios de pago aparecen. Solo esos medios se escriben en la landing.

## 8. Lo que queda para el dueño

- **Compra de prueba** con su tarjeta: es lo único que prueba cobro, correo de entrega, descarga del PDF y evento de compra en el píxel. Yo no ingreso datos de tarjeta.
- Token de la API de conversiones de cada píxel, en cada tienda que lo usa (§5.1). Ya no es opcional.
- Correos (`/personalizacion/diseno/emails`): leer el de entrega y proponerle el texto en la voz del mercado.

## Hecho cuando

- La vista previa del país muestra precio local, medios de pago locales e imagen de producto.
- El PDF está cargado en el producto.
- El píxel figura guardado tras recargar.
- El campo del token CAPI tiene contenido en cada tienda del funnel, comprobado por largo y no por valor. Si el dueño todavía no lo pegó, figura como pendiente suyo en `estado.md` y en el informe final.
- `estado.md` tiene URL, `store_id`, precios por mercado y lo que queda para el dueño.
