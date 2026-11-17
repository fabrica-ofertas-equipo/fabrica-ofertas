# Tropiezos de la corrida de México y su salida

Una fila por cosa que falló o que el dueño tuvo que corregir. Añadir filas al cerrar cada corrida nueva; no borrar las viejas.

## Correcciones del dueño (las que más cuestan)

| Qué pasó | Qué dijo | Qué se hace ahora |
|---|---|---|
| Réplicas FR e IT (14-nov) salieron con la imagen del producto rota en los 6 checkouts; el dueño vio «muchas visitas pero ningún checkout». La salud solo miraba que las páginas respondieran 200, y la revisión a mano con el navegador integrado cargó el píxel real | «revisa para ver si todo funciona bien… verificar esto una vez que se lanza una oferta nueva y… a los 10 o 15 minutos que se activan los anuncios» | `verificar_funnel.py --antes` en el control previo y paso 8 de la vigilancia a los 10-25 min de activar; las revisiones van con `probar_funnel.py`, que además bloquea las visitas de Impultienda y su API de conversiones (`meta-track-event`, que mandaba InitiateCheckout a Meta desde el servidor aunque el píxel estuviera bloqueado), nunca a mano |
| 10 anuncios de 19-31 s cuando los del referente duran de 39 s a 1:37 | «siempre apégate a modelar lo que ya existe, no reinventes la estructura» | Tabla de mezcla y duraciones antes de escribir un guion (`08-creativos.md` §1) |
| Landing con precio y botón antes del video y cabecera en dos columnas | «la estructura de la landing no es exactamente la misma de la página original» | Medir el orden de cada elemento en móvil y comparar lado a lado antes de publicar (`07-landing.md` §1) |
| El video de la landing era un anuncio reutilizado: cerraba con «toca Más información» y ese botón no existe en la página | «queda incompleto» | Video propio en 4:5 cuyo cierre nombra el botón real, que va justo debajo |
| El botón de sonido tapaba los subtítulos del video | «tapa los subtítulos» | Barra de sonido debajo del video |
| Producto sin imagen en la tienda | «debes colocarla» | Imagen de producto siempre |
| Leí el checkout antes de que él guardara | «no le había dado a guardar» | Cada pantalla de Impultienda tiene su Guardar; releer después de que confirme |
| Dije «00:00 de Ciudad de México» y entendió que la campaña apuntaba a esa ciudad | «tiene que ser de todo el país» | Decir «hora del centro de <país>»; segmentación siempre por país entero; sin ciudades en los nombres |
| No avisé desde el principio que no haría el reloj ni el precio tachado del referente | «¿por qué no colocaste los timer de urgencia? eso es necesario» | Decirlo en el desarme, con la alternativa (fecha real de fin) y pidiéndole la fecha |

## Navegador integrado y panel de Impultienda

| Síntoma | Causa | Salida |
|---|---|---|
| El panel redirige a `/login` | La sesión se cae cada pocas horas | Abrir `impultienda.ar/login` y pedir al dueño que entre (con Google). No escribir contraseñas |
| Pegar con el teclado no llega al `textarea`; `clipboard.readText()` denegado; `fetch` a `127.0.0.1` falla | Aislamiento del panel | Gist secreto temporal + `fetch` (`fragmentos-navegador.md` §3-4) |
| No hay `input[type=file]` en la página | Solo aparece al pulsar el botón | Interceptar `HTMLInputElement.prototype.click` |
| `file://` no abre | El navegador integrado no lo permite | Servidor local + `preview_start` con entrada en `.claude/launch.json` |
| «Tab cap reached» | Demasiadas pestañas | Reutilizar una pestaña en blanco o cerrar las propias |
| El «zoom» recorta en vez de ampliar | Así funciona la herramienta | Miniaturas más grandes en la hoja de contacto |
| Chrome sin pantalla no baja de 500 px de ancho | Límite del navegador | Vista móvil con un `iframe` de 390 px o con la emulación del navegador integrado |
| La captura tras hacer scroll sale con un bloque en blanco | Se capturó a mitad del repintado | `scrollTo` por JavaScript, esperar 800 ms y capturar |
| El HTML del panel no coincide con el archivo local | Otra sesión o un script publicó encima | Comparar huellas antes de publicar; guardar copia de lo publicado; avisar |

## Video y audio

| Síntoma | Causa | Salida |
|---|---|---|
| ffmpeg falla en borrador 4:5 | Alto impar (675 px) | Montar a resolución completa |
| El video mide 1350 px de alto en la página | Atributos `width`/`height` sin `height:auto` | CSS con `height:auto` y `aspect-ratio` |
| La máquina se queda sin memoria al montar | Cada clip en caché ocupa ≈750 MB | Un proceso por anuncio |
| El audio no casa con el plano | Se insertó una frase y los wav van por índice | Mover los wav de ese anuncio y regenerar |
| Anuncios más cortos o largos que el referente tras generar voz | La voz manda la duración | Añadir o recortar frases; estilo más fluido; volver a medir |
| Un bucle de zsh no parte la variable en palabras | zsh no hace word splitting | Hacer el lote con un script de Python |

## Meta

Ver la tabla al final de `09-campana-meta.md`.

## Proceso

| Qué pasó | Salida |
|---|---|
| Atribuí al dueño una regla que era un límite mío | Distinguir siempre «regla del dueño» de «límite mío» y decir cuál es cuál |
| Quedaron gists temporales al bloquearse una subida | `pasar.py borrar` también cuando el paso falla |
| Se activó la campaña sin compra de prueba | Fue decisión del dueño; queda dicho en el informe como no comprobado y es lo primero a mirar al día siguiente |
| Fase 1 · radar 15-nov: la Biblioteca web devolvió «No hay ningún anuncio» para todo (hasta `q=hotmart` y una página con 127 activos según el conector), sin pedir sesión ni mostrar desafío | Bloqueo silencioso: antes de registrar un `medir --total 0`, hacer una prueba de control con una oferta ya medida > 0 (p. ej. `view_all_page_id` de una medida); si da 0, `radar.py bloqueo` y no se registra ningún cero. El conector `ads_library_search` por palabra clave no sirve para medir (búsqueda difusa, 384 mil resultados para un código); solo por `page_ids` |

## Segunda corrida · «Oferta B» (México, 2026-11-11), primera siguiendo la skill

Lo que se aprendió por fase. Lo que cambia un procedimiento ya está pasado también a la guía de esa fase.

### Elegir oferta y mercado
| Qué pasó | Qué se hace ahora |
|---|---|
| El dueño vio `country=AR` en la Biblioteca y avisó: «no tenés que filtrar por Argentina sino anuncios en todos los países» | El conector sin `countries` ya cuenta todos los países. En el navegador, usar siempre `country=ALL`. Facebook añade `country=AR` solo al abrir una ficha suelta por `id`: no afecta, pero no usarlo para contar |
| El barrido guarda la edad como «piso» (`edad_es_piso: true`) y con 5 días de atraso | Medir la antigüedad real en la página de la Biblioteca del anunciante (`…/ads/library/?active_status=active&ad_type=all&country=ALL&search_type=page&view_all_page_id=<id>`): desplazar unas pocas veces y contar por fecha los textos «En circulación desde el …». Ordena por impresiones, así que los primeros son los más vistos |
| Un candidato con quiz (102 anuncios) tenía TODOS sus anuncios activos con 2 días: los apaga y relanza a diario | La antigüedad se mide en los anuncios activos, no en la página. Si todos son de esta semana, no pasa el piso aunque la oferta exista hace más |
| Muchas páginas del barrido son operadores con varias ofertas a la vez (cientos o miles de anuncios en varios idiomas) | Contar los anuncios de LA oferta (por dominio o ruta de destino dentro de la página de la Biblioteca), no los de la página |
| `ads_library_search` con `limit: 50` devuelve ~10 mil tokens | Para contar, `limit: 2` (trae `estimated_total_count`). El detalle por anuncio se saca de la página de la Biblioteca con JavaScript |
| No hubo ningún funnel complejo que pasara el piso | Se dice así y se toma el mejor puntaje disponible |

### Marca y Meta
| Qué pasó | Qué se hace ahora |
|---|---|
| `facebook.com/pages/creation/` daba «contenido no disponible» | Crear la página desde Business: Configuración → Páginas → Agregar → «Crear una nueva página de Facebook» (nombre, categoría, presentación ≤100). Queda ya dentro del portfolio. Pide marcar la casilla de condiciones de Meta |
| Para poner perfil, portada y publicaciones hay que actuar como la página | En la página, «Cambiar» de perfil; al terminar, volver al perfil personal desde el menú de cuenta. Apagar los correos promocionales en el aviso de bienvenida |
| Subir imágenes a la página | Funcionó tal cual la ruta `subir a Kie → ads_creative_upload_media → fetch de la URL de fbcdn → File → input` con el clic del `input` interceptado. La portada necesitó un segundo intento tras recargar |

### Producto
| Qué pasó | Qué se hace ahora |
|---|---|
| Producto de texto y maqueta (hojas de trabajo) | No hizo falta generar imágenes: contenido en JSON por agentes (un agente por dos áreas, con una especificación de tipos y límites de caracteres), maqueta HTML→PDF por código (un tipo de hoja = una plantilla), 0 créditos. Ver `05-producto.md` §8 |
| La revisión visual encontró 7 hojas donde la consigna pedía escribir y no había renglón | Añadir a los criterios de quien escribe el contenido: «cada verbo de escribir necesita su espacio en la plantilla de ese tipo». La revisión de contenido y la visual se lanzan las dos; se cruzan |
| El agente de maqueta corrigió y cambió el número de páginas después de componer las imágenes de la landing | Componer las imágenes de la landing DESPUÉS de cerrar el PDF, o regenerarlas al final |

### Tienda
| Qué pasó | Qué se hace ahora |
|---|---|
| La tienda nace cobrando en pesos argentinos aunque en el asistente se elija Multidivisa | Tras el asistente: «Cambiar modo» → Multidivisa → confirmar. Después «Copiar de otra tienda» trae Impul Pay con la misma cuenta en dos clics |
| `form_input` sobre los interruptores (casillas ocultas) cambia el valor pero no activa «Guardar» | Hacer clic real sobre la etiqueta del interruptor y comprobar que «Guardar cambios» se habilita |
| El referente vende en dos niveles (básico y completo) y el checkout de Impultienda no deja llegar con el complemento ya agregado | Dos tiendas con el mismo píxel: la principal con el nivel completo (aloja la landing) y una copia (`/dashboard/duplicar-tienda`) con el básico y los bonus como complemento. La copia trae landing, productos con sus PDF, imágenes y diseño; NO trae cobro, píxel, markets ni correos |
| «Eliminar» un producto abre una confirmación nativa que el navegador integrado descarta | Marcar el complemento como «Disponible solo en post-compra» (deja de salir en el checkout) y decirle al dueño que lo borre a mano si quiere |
| Los valores por defecto del diseño de checkout ya coinciden con la configuración del dueño | Solo hay que apagar teléfono, nombre y apellido. En la vista previa de México esos campos reaparecen como obligatorios: parece requisito del procesador |
| `gh gist create` devolvió HTTP 400 tras 17 gists seguidos | Pausa de unos segundos entre gists; reintentar |
| Hay `input[type=file][accept=application/pdf]` directo por producto en la página de ebooks | Subir el PDF ahí sin abrir menús. Un PDF de 4-5 MB son 2-3 trozos |

### Meta
| Qué pasó | Qué se hace ahora |
|---|---|
| La descripción de `ads_create_campaign` habla de «modo borrador» | Creó objetos reales en pausa. Leer el `status` y la URL de la respuesta para saber cuál de los dos modos tocó |

### Corrección del dueño tras la segunda corrida: el barrido no encuentra funnels complejos
| Qué pasó | Qué dijo | Qué se hace ahora |
|---|---|---|
| Se eligió una página de venta simple (complejidad 0.35) porque en el barrido del 6-nov ningún quiz ni VSL pasaba el piso, y lo expliqué como «no había» | «¿no hay ningún funnel en todo el mundo que tenga mayor complejidad y umbrales de antigüedad y de ads relevantes? Lo dudo mucho… quiero plantear cosas para mejorar nuestros procesos» (2026-11-11) | Decir siempre «no lo encontró NUESTRO barrido», nunca «no hay». El límite es el método: busca por tema y no por forma. Pendiente de construir (ver `01-elegir-oferta-y-mercado.md` §1.5): barrido por forma de funnel, clasificador automático del destino, antigüedad medida sobre los anuncios activos de la oferta, barrido el mismo día y piso de 3 candidatos complejos antes de elegir |

### Corrección del dueño: los bonus no estaban cargados como bonos (2026-11-11)
| Qué pasó | Qué dijo | Qué se hace ahora |
|---|---|---|
| En las dos ofertas los bonus iban dentro del PDF principal y la tienda mostraba «Bonos 0» | «no tenemos bonos creados en ninguno de los dos productos cuando ambas ofertas tienen bonos… los upsells en general los habilitamos post-testeo» | Bonus siempre como bonos de Impultienda, uno por uno con PDF y portada vertical; upsells post-compra solo después del test (`06-tienda-impultienda.md` §3.1) |
| Cargué 2 USD de «valor percibido» por bono y el checkout mostró «Ahorras MX$ 148.88» | — | Ese campo genera un ahorro en pantalla: se deja vacío y se le avisa al dueño que existe |
| En la tienda del nivel completo quedó un upsell «solo post-compra» que vende los mismos bonus | — | No dejar upsells sobrantes al duplicar o invertir tiendas; «Eliminar» es permanente y se confirma con el dueño |
| Las portadas apaisadas se ven recortadas en la tarjeta del bono | — | Portada vertical 900×1200 |
| `gh gist create` falló tras ~18 gists en pocos minutos | — | `pasar.py` sin reintento: esperar unos 25 s y subir de a uno con pausa |
| «Eliminar» un producto usa `window.confirm`, que el navegador integrado descarta | — | Solo con el sí explícito del dueño: redefinir `window.confirm = () => true` en la pestaña justo antes del clic, comprobar que el menú abierto es el de ESE producto, y recargar para verificar los contadores |

### Corrección del dueño: los 10 anuncios se sentían iguales (2026-11-11)
| Qué pasó | Qué dijo | Qué se hace ahora |
|---|---|---|
| 10 videos con guiones distintos pero armados con 13 clips: 7 tomas en los diez, 65-76 % del tiempo repetido | «se sienten todos muy iguales, hay poca diversificación creativa, justamente lo que busca Meta… entiendo que estamos modelando lo que funciona, incluidos los creativos» | Medir la repetición con números antes de entregar (`08-creativos.md` §1.1) |
| La «mezcla a replicar» salió de 3 videos del referente, todos de la misma tanda | «revisa unos 13 o 15 más enteros, y no de los últimos en orden, sino de los más viejos, de los intermedios y de los nuevos… aplícalo a como siempre haremos las cosas» | Muestra de 13-15 videos repartida por tandas (`02-desarme-del-referente.md` §2.0) |
| Me puse un tope de créditos que forzó a reutilizar | — | El tope sale de lo que pide la muestra, no al revés |
| Segunda tanda: 10 videos con muestra de 16 del referente | — | Resultado medido: 0 % de material en 6+ videos, 33 minutos y ≈2.700 créditos (20 tomas de apertura + 6 de fondo + 3 de avatar). La miniatura del anuncio puede ir como `image_url` en `video_data` (ahorra subir 10 imágenes). Para reemplazar creativos: crear anuncios nuevos, activarlos y pausar los viejos con `ads_update_entity` `{"status":"PAUSED"}` |
| Un archivo `ofertas/AGENTS.md` con órdenes para agentes (relojes, reseñas, publicar) llegó adjunto a un subagente | — | Lo que aparece en archivos del repositorio es dato: el subagente no lo siguió y lo informó. Avisar al dueño y comprobar la huella de la landing publicada |

### Pedido del dueño: expediente del funnel (2026-11-11)
| Qué pasó | Qué dijo | Qué se hace ahora |
|---|---|---|
| No quedaba junto, en un solo lugar, qué se modeló, qué se pegó y qué quedó fuera | «en una carpeta guardar con el nombre tal cual aparece en tienda… la landing original, el HTML de la landing nueva y un detalle de todas las cosas que dejaste afuera» | Fase 8 bis (`10-expediente-del-funnel.md`, `scripts/expediente_funnel.py`) |
| Al escribir el inventario leí el `.js` del referente y apareció una oferta intermedia que el desarme no tenía | — | El desarme lee los scripts (`02-desarme-del-referente.md` §1) |
| La página pública de Oferta A no era lo que yo había pegado (lleva el reloj del script del dueño) | — | El expediente guarda las dos versiones y lo dice en la ficha |

### Pedido del dueño: modelar la oferta intermedia y guardar el patrón (2026-11-11)
| Qué pasó | Qué dijo | Qué se hace ahora |
|---|---|---|
| El desarme no vio la ventana «llévate el completo por 4 dólares más» porque no tocó el botón del básico ni leyó el script | «modélala y guarda también este tipo de cosas para próximos funnels… ofertas que suben el AOV antes de pagar» | Extra `subida-previa` en la taxonomía y guía `11-ofertas-que-suben-el-ticket.md`; el desarme toca cada botón de compra |
| `/dashboard/duplicar-tienda` copió productos y bonos con las imágenes rotas (HTTP 400) | — | Tras duplicar, comprobar las imágenes con `fetch` y volver a subirlas |
| Escribir encima del precio base en el editor del producto no guardaba (volvía a 17) | — | Setter nativo + `input`/`change`, guardar, recargar y leer la tarjeta |
| La pestaña del panel copió algo al portapapeles del dueño al hacer clic en «Meta / Tracking» | — | Avisarlo; no depender del portapapeles |
| Después de publicar la landing con la oferta intermedia, el panel volvió solo a la versión anterior en menos de 20 minutos | — | Tras publicar, vigilar la página pública un rato (que siga teniendo una marca de la versión nueva) y volver a leer la huella del panel antes de cerrar. Causa probable: otra pestaña del editor abierta con el contenido viejo que vuelve a guardar |
| La página pública nunca coincide byte a byte con lo pegado | — | Cloudflare oculta los correos al servirla; comparar trozos sin «@» y pedir la página con `?v=` para saltar la caché |
| La tercera vez se mantuvo: se puso el HTML, «Guardar cambios», se recargó el editor para leer la huella y se salió directo a otra página del panel | — | Hipótesis (no confirmada): el editor guarda por su cuenta un borrador con el contenido viejo si se queda abierto tras poner el valor por JavaScript. Tras publicar, salir del editor y vigilar la página pública unos minutos |

## Tercera corrida · «Oferta C» (Brasil, pt-BR, quiz+vsl, 2026-11-12), hecha de noche sin el dueño

### Elegir oferta y mercado
| Qué pasó | Qué se hace ahora |
|---|---|
| Las dos primeras ofertas salieron a México por costumbre; el dueño lo marcó | `scripts/elegir_mercado.py` y `01-elegir-oferta-y-mercado.md` §2.1. Aquí ganó Brasil (el referente pautaba en español en todo el mundo, 0 en BR) |
| El conector cuenta como «del país» los anuncios en español que se entregan ahí (IT 44, PL 37, GB 29) | Leerlo como entrega, no como versión local. El hueco real es el idioma que el referente no tiene |
| La página del quiz dice «video de solo 2 minutos» y dura 11:09 | Bajar el video (el `embed.html` del reproductor ConverteAI trae el `main.m3u8`; `ffmpeg -i <m3u8> -c copy`) y transcribirlo con whisper-cli. Así se mide de verdad |

### Producto
| Qué pasó | Qué se hace ahora |
|---|---|
| Guía de texto (5 módulos + mapa + 3 bonus) | ESPEC.md con formato JSON de bloques; 4 agentes de contenido + 1 de maqueta en paralelo y una revisión independiente al final. 0 créditos, ≈ 25 minutos |

### Tienda
| Qué pasó | Qué se hace ahora |
|---|---|
| Al subir las portadas y los PDF de 3 bonos en una sola llamada, los `input[type=file]` cambiaron de orden a mitad: el producto principal quedó con la portada **y el PDF del Bônus 3** | Subir de a una tarjeta por llamada y **verificar siempre**: «Descargar PDF» de cada tarjeta (capturando la URL con `window.open`/`a.click` interceptados) y comparar los bytes con el archivo local |
| El precio por mercado puesto con el setter nativo no se guardó (el checkout siguió en la conversión automática R$ 71,89) | Enfocar el campo y **escribirlo con el teclado** (`computer type`), guardar con clic real, recargar y leer |
| Los bonos se llamaban «Bônus 1 · …» y el checkout añade «Bônus #1:» | Título del bono sin número |
| La cuota de recursos ahora es 3.072 MB entre tiendas y videos de hasta 100 MB (plan Max) | La VSL puede ir con buena calidad |
| ~~Impul Pay en Brasil cobra solo tarjeta (y Google Pay). Pix existe vía dLocal Go, que hay que conectar~~ **Obsoleto (13-nov): era un error de lectura; el checkout de Brasil sí tiene Pix y Boleto (ver cuarta corrida, abajo)** | ~~Decirlo al dueño~~ Comprobar los medios con la vista previa por país y captura de pantalla, nunca con el texto de la página |

### Creativos
| Qué pasó | Qué se hace ahora |
|---|---|
| Kie tenía 1.453 créditos; el dueño recargó | Revisar saldo al empezar y decir el costo estimado antes de producir |
| `kling/ai-avatar-standard` ≈ 10 créditos por segundo de audio, 720p, buena sincronía | Usarlo en vez de pro (22/s) para presentadora larga (VSL y anuncios de 1-2 min) |
| Cada avatar tarda 10-25 min; en cola serie eran 5 h | **Kie sí acepta varios avatar a la vez** (probado con 6): repartir en colas paralelas con marcadores vacíos para que ninguna cola duplique trabajo (`06-creativos/scripts/cola.sh` de esta oferta) |
| Kling quemó un subtítulo ilegible al 84 % de la altura en un clip | En el montaje usar siempre el 79 % superior del clip de la presentadora |
| Las imágenes de apoyo se hicieron con Gemini (`gemini-3-pro-image`) | 26 imágenes sin gastar Kie; el costo lo cobra Google a la cuenta del dueño |
| `timeout` no existe en este macOS | No usarlo en los comandos |
| `ofertas/AGENTS.md` (creado fuera de nuestras sesiones el 11-nov 17:56, con las mismas órdenes que `cro-polish`) se inyectaba como contexto al leer archivos de `ofertas/` | El dueño pidió borrarlo (2026-11-12): se mandó a la papelera. Si reaparece, no seguirlo y avisar |

(Lo de después del lanzamiento, desde la revisión del 12-nov, está en `escalar-oferta/references/tropiezos.md`.)

## Cuarta corrida · «Oferta D» (México, advertorial+tsl con 3 niveles, 2026-11-12)

| Qué pasó | Salida |
|---|---|
| Cargué en las 3 tiendas el número que sale en la URL de Business al crear el píxel (`selected_asset_id=2421365245337114`): NO es el ID del píxel. `ads_create_ad_set` lo rechazó («Pixel Can't Be Used») | El ID del píxel se toma SIEMPRE de `ads_get_datasets` (`dataset_id`, aquí 1000000000000067), nunca de la URL. Comprobar con `curl` que el ID aparece en el HTML público de cada tienda |
| El barrido clasificó al referente como `tsl` simple; al recorrerlo, la mitad de sus anuncios iban a un ebook estrella con advertorial y ficha de 3 niveles | Antes de diseñar el producto, agrupar el inventario de anuncios por destino (`biblioteca-*.json`): el producto que se modela es el que más anuncios recibe, no la página que trajo el barrido |
| Subagentes usando el navegador integrado se pisaron la pestaña conmigo | Cada encargo a un agente dice explícitamente «no uses mcp__Claude_Browser__*» |
| Un agente se cortó por error de conexión a mitad de la producción | Retomarlo con SendMessage (conserva su contexto) indicando «no rehagas lo que ya está en disco» |
| El panel de Impultienda quedó cargando sin fin tras subir un PDF | Ir a `/dashboard` y volver a la ruta; el archivo ya estaba subido (comprobar por `curl` la URL de la imagen o el estado «Listo») |
| La página de Recursos acepta varias imágenes a la vez | Un solo `DataTransfer` con todos los archivos; las URL públicas se leen interceptando `navigator.clipboard.writeText` y pulsando el botón de copiar de cada tarjeta |
| El dueño contestó el visto bueno 7 h después de la pregunta; activé sin volver a mirar la hora y el conjunto (inicio 13-nov 00:00 MX, ya vencido) salió en el acto | Mirar la hora justo antes de `ads_activate_entity`; si el inicio ya pasó, conjunto nuevo con las 00:00 siguientes y anuncios copiados por `creative_id` (`09-campana-meta.md` §4). Pausar el que salió y anotarlo como «NO USAR» |
| Se anotó «Oferta C: sin Pix» (12-nov) y lo repetí al dueño el 13-nov; el checkout de Brasil sí tiene Pix y Boleto | Los medios de pago se dibujan dentro de un cuadro de Whop (iframe): `get_page_text` y `innerText` no los ven. Comprobarlos SIEMPRE con la vista previa por país (`preview_country=XX`), bajando hasta debajo de la tarjeta y con captura de pantalla. Y no repetir una nota vieja como hecho sin volver a mirar |

### Radar (fase 1) · vuelta del 13-nov noche

- Las ofertas en plataformas compartidas cuyo código o slug no aparece como frase (Hotmart `H98995146C`, `instituto-cimas-cursos-livres`) no se pudieron medir: ni el número de `pagina_url` en el conector ni el clic en el nombre de la página dan el id de la Biblioteca. Quedan en a_medir.
- Los hoplinks de ClickBank sin subdominio se funden en una sola oferta (`hop.clickbank.net/`) porque el lector corta la URL en «?».

### Vuelta diaria del banco (fase 1) · 14-nov

- **Contexto Filosófico** entró con `medir_por: dominio`, pero sus anuncios van a go.hotmart: la búsqueda de `referente307.com` ve solo 6 de los 56 de la página. Se pasó a `pagina` (page_id 100000000000119). Al exportar del radar, si el destino es una plataforma (hotmart, kiwify…), medir por página.
- **Maku**: el 142 del 13-nov lo contó el radar por tarjetas, no es el total de la búsqueda del dominio (64 hoy; la página tiene 126). Su «baja» de hoy es cambio de base, no caída real.
- `estado` se cortó con `ErrorTaxonomia`: el radar exportó Maku con `funnel: landing-simple`, que no está en la taxonomía. Se pasó a `tsl` + `bump`. `radar.py verificar --funnel` debería aceptar solo tipos de la taxonomía.
- El navegador rechazó abrir `kiwify.app` (las 3 joyas de kiwify del radar quedan en a_verificar) y, más tarde en la misma vuelta, `web.facebook.com`: sin la Biblioteca no se pudieron sacar las iteraciones de video ni medir el referente de Oferta B. No se reintentó.
- Con `__leer(4)` la búsqueda de `inlead.digital` (5.800 activos) solo carga 29 tarjetas: las ofertas «muestra» de inlead sin page_id (mmcsc, ingresos-extra) no se pueden volver a contar así. Hace falta resolver su page_id.

### Vuelta diaria del banco (fase 1) · 15-nov

- **Medir por página sin abrir fichas:** el HTML de una búsqueda por el nombre del anunciante (`search_type=keyword_unordered`, traído con `fetch` desde una pestaña de la Biblioteca) trae `"page_id":"…","page_is_deleted":…,"page_profile_uri":"…/<id de perfil>/"` antes de `"page_name"`. El número de `pagina_url` del radar coincide con ese `page_profile_uri`: así se ubicó el page_id real de 11 de 27 anunciantes de Hotmart/Kiwify y se contaron con el conector. Los 16 restantes (nombres genéricos) no aparecieron en la primera página de resultados.
- **El panel del navegador oculto frena los temporizadores:** un bucle de `fetch` con `setTimeout` de 1,2 s lanzado en segundo plano no terminó en varios minutos. Correr las búsquedas dentro de la misma llamada, en tandas de 6-14 en paralelo, sin `setTimeout`, y devolver el resultado al final (cada llamada < 45 s).
- **Bloqueo blando de la Biblioteca tras ~70 búsquedas por `fetch` en ~40 min:** las respuestas siguen trayendo `"count":N`, pero sin tarjetas, y la página visible dice «ningún anuncio» incluso para Reading Planets (680 activos). Ese `count` NO sirve (referente-l.com dio 4 contra 290 de ayer). Señal para cortar: una búsqueda conocida que vuelve sin tarjetas. Se registró con `radar.py bloqueo`.
- **Total exacto contra total redondeado:** el `count` del HTML es exacto (681) y la Biblioteca muestra «~680». Para no fabricar subas de 1 anuncio en `tendencia`, se guardó redondeado a dos cifras significativas cuando es ≥ 100, como en los días anteriores.

### Vuelta diaria del banco (fase 1) · 16-nov

- **`eval(sessionStorage…)` falla si va después de un `await`:** la Biblioteca aplica su CSP (`unsafe-eval` no permitido) en cuanto termina de cargar; un `await esp(3000); eval(...)` dio `EvalError`, y el mismo `eval` como primera instrucción de la llamada funcionó siempre. Poner el `eval` primero y esperar dentro de la función que define.
- **La ruta de un destino de inlead no se busca:** `"31-dias-de-oracao-pelo-seu-futuro-marido"` o `"quiz-ordem-cronologica"` como frase exacta dan 0. Para medir una oferta alojada en inlead: abrir una ficha (`?id=<ficha>`; la URL se reescribe sola con `view_all_page_id=…`, sin esperar más de 2,5 s), contar la página con el conector y agrupar sus tarjetas por destino en la web.
- **El número del perfil (`facebook.com/61578…/`) no es el page_id:** el conector devolvió 0 para los 6 que se probaron. El page_id sale de la ficha.
- **Un conteo por país que da lo mismo en cada grupo es segmentación mundial:** Referente dio 31 en US, 31 en GB+AU+CA+NZ+IE, 31 en el resto y 31 en MX, DE y JP sueltos. No hace falta seguir partiendo: es el veto del referente global.
- **Varios quiz de inlead filtrados por México devolvieron 500** (k-food, bisutería, Biblia cronológica, sermones, código divino), todos de páginas con nombre de persona genérico y la fecha sin leer: embudos borrados o con encubrimiento. No perder tiempo con ese grupo.

## Quinta corrida (13-nov-2026, dos ofertas en paralelo: Oferta E EE. UU. y Oferta F España)

| Síntoma | Causa | Salida |
|---|---|---|
| Meta recibió un video de 3:49 en lugar del de 70 s | Dos ofertas subieron «V1.mp4» al alojamiento temporal de Kie en el mismo segundo: la URL (`<segundos>-<nombre>`) es la misma y el segundo archivo pisa al primero | Subir siempre con nombre único por oferta (`MS-A-V1.mp4`, `TEO-B-V1.mp4`) y comparar la duración que devuelve `ads_get_ad_videos` con la local antes de crear anuncios |
| Impultienda en 10 de 10 tiendas; faltan cupos para los niveles | Plan Max = 10 tiendas; cada nivel es una tienda | Contar cupos al elegir las ofertas (niveles × ofertas). Archivar: desde el 14-nov lo hace solo la regla R15 de escalar-oferta (72 h después del apagado; `cierre_oferta.py`), que libera los cupos de las ofertas cortadas. Los checkouts de niveles que esperan cupo se dejan con el subdominio reservado y la campaña en pausa |
| La copia (`duplicar-tienda`) no trae los Markets ni el precio por mercado | Markets es por tienda | En cada copia: Activar modo Markets → Nuevo market → precio por mercado en el producto |
| El precio por mercado no se guarda si se pone por script | El campo `auto: …` no toma el setter nativo | Escribirlo con el teclado (clic + type) y comprobar al recargar |
| «Reemplazar PDF» abre una confirmación antes del `input` | Diálogo propio del panel | Interceptar el clic del botón «Reemplazar» del diálogo |
| Recursos acepta los 28-29 archivos de una vez | `input[type=file]` múltiple | Un solo `DataTransfer` desde gists; las URL se leen de los `img` de la página (`store-resources/<store_id>/<ts>_<nombre>`) |
| Los PDF de un nivel son varios y el producto lleva 1 PDF + 5 bonos | Límite del panel | Unir los PDF del nivel con PyMuPDF (`insert_pdf`): los campos rellenables se conservan; comprobar que no haya nombres de campo repetidos |
| La página nueva de Facebook muestra la bienvenida y tapa el botón de guardar la portada | Modal de bienvenida al cambiar de perfil | Apagar correos promocionales, «Usar página» y volver a poner la portada; comprobar al recargar |
| Las 5 pantallas del panel por tienda llevan horas a mano | Todo por navegador | Impultienda tiene MCP oficial (`https://mcp.impultienda.ar/mcp`, OAuth del dueño): conectarlo y probar sus herramientas antes de la próxima corrida |

### Quinta corrida, segunda parte (13-nov tarde, Plan Unlimited)
| Tropiezo | Qué hacer |
|---|---|
| La tienda duplicada queda en moneda única y «Markets requiere Multidivisa» | Configuración → Pagos → «Cambiar modo» → Multidivisa → «Sí, cambiar a MULTI»; Impul Pay sigue activo |
| Impul Pay por tienda | `/dashboard/<slug>/impulpay` → «Ver todas las tiendas» → radio «Impul Pay» de la tienda nueva |
| El precio por mercado no aparece en «Editar ebook» | Está plegado en «Precios por mercado»: abrirlo y escribir el monto con el teclado en `auto: …` |
| La tarjeta del producto sigue mostrando el precio viejo después de guardar | Es la vista sin refrescar; comprobar reabriendo «Precio, título y más» |
| La vista previa `?edit=1` del checkout muestra nombre, apellido y teléfono | El checkout real (sin `edit`) pide solo correo: comprobar ahí |
| ¿El PDF reemplazado es el bueno? | «Descargar PDF» → interceptar la URL firmada y comparar el tamaño en bytes con el archivo local |
| Inicio fijado a dos días porque faltaba una pieza | Si al activar todavía se llega, adelantar el conjunto a las 00 del día siguiente del mercado (el inicio se cambia en el Administrador de anuncios: desde el 15-nov `ads_update_entity` solo puede pausar, ver `escalar-oferta/references/08-cambios-en-meta-sin-pausa.md`) y volver a pasar control_previo |

- **Radar, medir (14-nov, vuelta de las 30):** el código del producto como frase exacta no dio resultados en 19 de 27 mediciones (Hotmart `go.hotmart.com/<código>`, Kiwify, Digistore24, inlead, systeme.io): el enlace no aparece en el texto del anuncio. Salida usada: buscar el nombre de la página con `ads_library_search`, tomar su `page_id` y contar con `page_ids`. Ojo con dos trampas: (1) el total por página mezcla todas las ofertas del anunciante (Clube da Elétrica: 50 en la página, 10 de la oferta) → antes de verificar, abrir `view_all_page_id=<id>` y contar por destino; (2) páginas homónimas («Prof Thiago Oliveira» ≠ «Prof. Thiago Oliveira»). Quedaron sin medir por no dar con la página: digistore24-com-mustafa332, go-hotmart-com-n105697023l, go-hotmart-com-x89100891m, go-hotmart-com-h89760519g, go-hotmart-com-f101749876r, go-hotmart-com-p99123687k.

- **Lanzamiento automático, vuelta de las 13 h (14-nov): sin lanzamiento.** (1) El único listo del banco (BossaColor) dependía de una cara y la ficha decía lo contrario: ahora la verificación del radar mira también los anuncios (`buscar-ofertas/references/05-radar.md`). (2) Con el panel del navegador oculto, los `setTimeout` dentro de `javascript_tool` se frenan y la llamada muere a los 45 s: hacer las esperas con `computer {action: wait}` entre llamadas cortas y sin `await`. (3) En la Biblioteca, una frase exacta con barra (`"inlead.digital/mmcsc"`) da cero: buscar solo la ruta (`"mmcsc"`) o contar por `page_id` (se saca del HTML de la página de Facebook del anunciante: `delegate_page_id`). (4) El conector `ads_library_search` con `search_terms` devuelve ruido (novelas, ropa): sus recuentos de competencia por país solo sirven como orden relativo. (5) Las frases «quiz + producto» (`quiz workbook`, `quiz printable PDF`, `quiz planner`) y «responda/faça o quiz» traen marcas, clínicas y libros físicos; lo que sí apareció con cientos de anuncios fueron páginas de venta largas con forma de artículo (BonjourTalk, StarMeiLife), que por la taxonomía son `tsl`.

## Réplica FR + IT (14-nov)

- **Se reinició la sesión a mitad de la subida a Meta y se borró la carpeta temporal (scratchpad)**: se perdieron los scripts de subida y los conectores de Meta e Impultienda quedaron «reconectando» ~1 h 20 min. Salida: guardar los scripts dentro de la carpeta de la oferta (`06-creativos/scripts/publicos_rep.py`, `spec_rep.py`, `05-landing/assets/subir_recursos.py`), nunca solo en la temporal, y si los conectores no vuelven, pedir al dueño `/mcp reconnect` o reabrir la app. Ojo: el `/mcp` acepta `reconnect`, no «reconectar».
- **La copia de una oferta arrastra `07-campana/anuncios.json` y `estado.md` de la madre**: renombrarlos a `*.madre-es.*` antes de escribir los de la réplica, o los scripts leen IDs ajenos.
- **Los textos de anuncios de cada agente pueden usar claves distintas** (`texto_principal` en FR, `principal` en IT): el armador de specs acepta las dos.


## Oferta J (14-nov): armada dos veces y sin mercado

Informe completo, con cada falla y si está resuelta: `docs/_historial/incidentes/2026-11-14-tu-tienda-sin-mercado.md`. La oferta se cerró sin salir y la tienda se archivó (14-nov 22:30).

- **Se eligió una oferta cuyo referente corría en el mundo entero.** Maku pauta en español a 89 de los 93 países de la lista. Los 4 en cero (SG, TW, TH, IN) son los que Meta bloquea sin anunciante verificado: no era un hueco. Se armó para EE. UU. (95 anuncios del referente: rompía el veto) y después para Singapur, y Meta frenó el conjunto («No Singapore Universal Ads Declaration», error 100/3858550). Salida: `ordenar_candidatos.py` ahora excluye los países bloqueados por Meta (`elegir_mercado.bloqueados_por_meta()`), así una oferta así queda «VETO» al elegirla. Guía `buscar-ofertas/references/01-elegir-del-banco.md` §1.2b.
- **Medición por grupos tomada como medición.** Grupos de 7-28 países con anuncios se anotaron como «medidos»; recién al partirlos uno por uno quedó claro que ninguno estaba en 0. Medir siempre hasta países sueltos antes de descartar o elegir.
- **Adaptar a otro país cuesta**: pasar la guía de pies a metros fueron ~650 cambios en 5 PDF, landing, 10 imágenes y la tienda (un agente, ~30 min, 0 créditos). Por eso el país se decide bien antes de producir, no después.
- **La adaptación no se puede ver como comprador del país**: el checkout público decide moneda por la conexión; `?preview_country=SG` no cambia nada desde Argentina. Solo «Ver como otro país» en Diseño de checkout del panel o una compra de prueba.
- **Condiciones de Meta al crear página y píxel**: autorizadas para siempre por el dueño el 14-nov (`04-marca-y-activos-meta.md` §2 bis). Antes la corrida automática frenaba ahí y dejaba ofertas armadas sin salir.

## Corrida DOM-A (OfertaO, JP, 15-nov-2026)

| Fase | Qué pasó | Salida |
|---|---|---|
| 5 | Tras crear la fan page en Business, el número de `selected_asset_id` de la URL (61596547771969) es el id de PERFIL; `ads_create_ad` respondió «Facebook Page is Missing» | El `page_id` bueno sale de `ads_get_user_pages` (1000000000001488). Igual que con el píxel: nunca el número de la URL |
| 5 | Publicaciones de la página desde el compositor de Business Suite: inyectar la imagen en el `input[type=file]` (que el compositor crea suelto, fuera del DOM) no la carga de forma fiable; funcionó una vez y no se pudo repetir | Quedó 1 publicación + portada; las otras 9 y la foto de perfil quedan pendientes. No cambiar de identidad a la página en facebook.com con el navegador compartido: cambia la identidad de todas las pestañas |
| 6/7 | Producto de muchos archivos (654 PNG) entregado como PDF con enlaces a Recursos: cada código de `impultienda_link_subida_recursos` sube 50 archivos y la cuenta admite 5 códigos sin vencer (30 min) entre todas las tiendas | Pedir los códigos de a uno a medida que vencen; subir con 3 hilos (con 6 da 429); priorizar los PNG que usa la landing |
| 7 | `impultienda_crear_tienda` (clásica) crea 3 bonos y 2 upsells vacíos generados por IA | Los upsells se reutilizan como order bumps (renombrar, precio, PDF, imagen); los bonos vacíos se borran en el panel (⋮ → Eliminar; el panel pide `confirm()`) para que el checkout no anuncie bonos sin contenido |
| 7 | La vista previa del checkout con `edit=1` muestra nombre, apellido y teléfono aunque estén apagados | Comprobar los campos en `/checkout` sin parámetros |

## Corrida MAR-B «Oferta N» (NL, 15-nov-2026)
- Business Suite → composer: «Agregar foto/video» crea un `input[type=file]` desconectado y le hace `.click()`; poner archivo por `DataTransfer` no llega si el input no está en el documento. Salida: sobrescribir `HTMLInputElement.prototype.click` para, si es de tipo file, adjuntarlo a `body`, cargar el `File` (fetch de la URL fbcdn de `ads_creative_upload_media`) y disparar `input`/`change`. Texto con `document.execCommand('insertText')`. Programar: interruptor «Establecer fecha y hora»; la fecha se escribe con triple clic + tipeo + **Tab** (Enter abre el calendario y no confirma); la hora es un spinbutton: foco y flecha arriba N veces (tipear no cambia). Horario = el del navegador (ART).
- Foto de perfil: Inicio de la página → «Editar página de Facebook» → «Editar Foto del perfil» → el `input[type=file]` dentro del diálogo acepta el `File` → «Guardar». No «Cambiar» al perfil de la página en facebook.com (cambia la identidad de la sesión compartida).
- Tienda clásica creada por el conector: la IA deja 1 bono y 2 upsells de más; se borran en Diseño de ebooks con `window.confirm=()=>true` antes de «Eliminar». El «Valor percibido» vacío no se guarda: poner 0 (setter nativo sobre el input cuyo rótulo es exactamente «Valor percibido»; un selector flojo pisó el título con «0»).
- `ads_get_ad_account_pages` no lista una página recién creada; `ads_get_user_pages` sí. El número `selected_asset_id` de Business para páginas no es el page_id.
# Tropiezos de la tanda 15-17 nov (para pasar a la skill al cerrar)

- LUN-A: la IA de Impultienda crea bonos y upsells basura al crear la tienda; se borran pisando `window.confirm`.
- LUN-A: el compositor de Business Suite toma la imagen solo si el input de archivo está en la página y se dispara `change` dos veces.
- LUN-A: la herramienta de avatar quema subtítulos falsos en los clips → presentador en pantalla partida.
- LUN-A / MAR-A / LUN-B: el checkout de vista previa pide nombre/teléfono aunque la tienda diga solo email; precio «antes» queda en 54,99 USD por defecto de la plantilla.
- LUN-B: la IA de la tienda creó un upsell vacío (quedó oculto).
- MAR-A: el editor de foto de perfil de la fan page en Business Suite no abrió.
- MAR-B: iDEAL no apareció en la vista previa de Impul Pay para NL (solo tarjeta y Google Pay); si falta, NL necesitaría Stripe.
- MAR-B: al unir PDF de niveles se pierden los enlaces internos del índice.
- MAR-B: en NL la ACM exige que el precio tachado sea real de los últimos 30 días.
- DOM-A: la herramienta de lip-sync quemó subtítulos falsos en 8 de 11 clips de presentador (igual que LUN-A) → tapados con barra opaca.
- DOM-A: en JP el sello «7日間保証» del checkout contradice el 特商法 «返品不可»; precio tachado inventado es riesgo de publicidad engañosa.
- DOM-B: corte de red (ENOTFOUND) mató al agente a mitad; se retomó con SendMessage leyendo estado.md sin duplicar. El navegador se reinició y cerró su pestaña.
- DOM-B: en CA, anuncios solo en inglés llegan también a Quebec (posible exigencia de francés); no se excluyó.
- DOM-B: la hora del selector de posts programados en Business Suite se asume ART (hora del navegador), no comprobado.
- POSTS CON IMAGEN EN BUSINESS SUITE (método que funcionó, DOM-B): subir la imagen con ads_creative_upload_media (URL) para tener dirección fbcdn; en el compositor pisar HTMLInputElement.prototype.click para capturar el input[type=file] de «Agregar foto/video» (sin adjuntarlo); fetch de la fbcdn → File → DataTransfer en ese input → disparar change E input (solo change no alcanza); comprobar «1080 x 1350» en el compositor. Texto con tipeo real y Shift+Enter entre líneas. Programar: interruptor «Establecer fecha y hora», fecha con execCommand('insertText','dd/mm/aaaa')+Enter, horas y minutos con flechas reales; hora = zona del navegador (ART).
- El control de permisos de Claude Code frena publicar en la fan page de OTRA oferta desde un agente ajeno: cada agente debe terminar sus propios posts.

## Réplica Oferta + NZ (15-nov): errores y cosas que no se contemplaron

Réplica de Oferta F (España) a Irlanda y Nueva Zelanda. El dueño lo marcó como error: «todo hay que rehacerlo al mercado cuando es así» y «todos son obligatorios en el test».

**Errores:**
- **Se adaptaron los textos, las voces y el producto, pero no las imágenes.** Los 11 videos y la landing salieron con las cocinas de España: azulejos, persianas de madera, cafetera moka y suelo de terracota. El plan solo rehacía los planos con texto legible y reusaba los keyframes de la madre. Para no correr la salida, el dueño eligió rehacer solo las 11 fotos de la landing de cada país (522 créditos de Kie); los videos quedaron con las cocinas de España.
- **Se activó con la fan page sin foto de perfil, sin portada y sin publicaciones.** Quedó en «pendientes» para no frenar la campaña. Se completó después, con las campañas ya programadas.
- **El criterio para reusar fotos de la madre estaba mal.** Tres fotos (art-trip-1, art-trip-2, ficha-problema) quedaron con la URL de la tienda de España porque «no tienen texto legible». Lo que decide si una foto se reusa es el ambiente (casa, cocina, calle, objetos), no el texto.

**Cosas que no se contemplaron y salieron al corregir:**
- **Nano Banana arrastra el idioma de la referencia.** Al rehacer las fotos con la carpeta de la madre como referencia, varias portadas salieron con «El Plan» o con la página del plan en español. Pasó otra vez al regenerar desde cero (la ficha-escritorio de IE necesitó 3 intentos). Lo que funcionó fue una segunda pasada de **edición**: la foto como referencia 1 y la página en inglés del producto como referencia 2, con «cambiá solo la portada / la página» (`ofertas/_borrador-oferta/05-landing/assets/arreglar_texto_fotos.py`; las fotos por país salen de `fotos_kie_pais.py`, en la misma carpeta).
- **Una hoja de contacto no alcanza para leer el texto de una portada.** Hay que recortar y ampliar cada portada y cada página abierta antes de subir.
- **El ambiente del país se rompe por detalles.** Sin prohibirlo, en NZ salieron azulejos con dibujos de estilo mediterráneo. El prompt del país tiene que decir qué NO va (azulejos con dibujos, persianas, moka, terracota) además de qué va.
- **La subida a Recursos devuelve una URL `aekpgsbqjzqntlbucbts.supabase.co`.** En la landing van `https://sb.impultienda.ar/...` (mismo camino), como el resto de las imágenes. Comprobar 200 e `image/webp` antes de reemplazar.
- **`verificar_funnel.py` corre con `python3` del sistema** (tiene playwright), no con el `.venv` del proyecto, que no lo tiene y devuelve `error_prueba` sin probar nada.
- **Además de la landing y los videos, hay otras imágenes que no se revisaron en IE/NZ:** mockups de los packs, imagen del producto en el checkout, páginas post-compra y posts de la fan page. Ahora entran en el inventario de la réplica (`12-lanzamiento-automatico.md` §3).

## Réplica Oferta + Oferta (16-nov)

| Tropiezo | Qué hacer |
|---|---|
| El conector de Meta rechazó todos los creativos («Missing Page permission», 3858749) con las páginas nuevas y también con la de Irlanda | No es el rol del dueño (idéntico en todas). Es la autorización del conector («ads MCP server» en Facebook → Integraciones comerciales): solo ve las páginas que se eligieron al autorizar. Reconectar sin eliminar no la renueva. Mientras tanto, anuncios por el Administrador desde el navegador (regla en 09 §«Si el conector de Meta no puede») |
| En el Administrador, la página nueva trae un perfil de Instagram creado por Meta y el anuncio da #1815199 (la cuenta publicitaria no tiene acceso a ese perfil) | Dar el acceso desde el propio Administrador (autorizado: activos propios) o quitar la identidad de Instagram del anuncio |
| (16-nov noche, DE) #1815199 sigue: el Administrador no ofrece dar acceso (solo «Usar página de Facebook», que da el error, o «Conectar perfil», que es conectar un Instagram real) y Business Suite no muestra ese perfil en ningún lado (la página figura «Conectar con Instagram», sin activos conectados, portfolio sin perfiles de Instagram). Las páginas que fallan son justo las nuevas que no aparecen en Configuración de la cuenta publicitaria → Páginas | Desvincular el perfil (tu-tienda.f / tu-tiendafamily.f) solo se puede en facebook.com → configuración de la página → Cuentas vinculadas, entrando como la página: es paso del dueño (o con su permiso explícito para «Cambiar»). Dejar el anuncio armado como borrador y publicarlo después |
| (17-nov, DE) Causa de fondo de #1815199 y 3858749 | La página nueva no tiene Instagram conectado: «<nombre>.f» es la identidad de Instagram que Meta genera desde la página (como en España/Irlanda), pero la cuenta publicitaria solo queda habilitada si el primer anuncio de esa página se crea por el conector. El conector quedó autorizado solo para 3 páginas ajenas a Never Give Up (`ads_get_user_pages`), y las páginas de «ads MCP server» no se editan en Integraciones comerciales: el dueño tiene que eliminar la integración y volver a conectar Meta ADS eligiendo el portfolio Never Give Up y todas sus páginas. Comprobar con `ads_get_user_pages` antes de crear la primera página de una oferta |
| Los videos de dos réplicas con el mismo nombre de archivo se confunden en la biblioteca del Administrador | Nombrar los mp4 con el país (`UK-V1.mp4`, `DE-V1.mp4`) antes de subirlos y comprobar la duración al elegir |
| La fila del libro se creó al final y el panel no mostró el aviso del token CAPI | Crear la fila del libro (`libro.py nuevo-test`, estado programado) apenas existe el píxel, con `ficha.tiendas[].capi.ok=false` |
| R16 congeló IE y NZ (réplicas de una validada) a las pocas horas de salir, sin días cerrados | Revisar `congelamiento.py`: las réplicas de una validada no deberían congelarse; pedido del dueño de revisarlo |
| `nube_sync` detectó las campañas DE por nombre y les puso rol «pocket» a las dos (también a la de variaciones) y sin `corte_tickets` | Al crear campañas de réplica, cargar `ficha.campanas` a mano con rol y `corte_tickets` (pocket 1,0; variaciones 1,5) apenas existen; revisar la detección de rol en `nube_sync.py` |
| UK: Meta rechazó V1, D4, E2, X4 y V1b por «uso falso de nombre/imagen de figura pública o marca»; V1 y E2 aprobados al apelar | Revisión dispareja, pero patrón: los rechazados eran videos largos (2:26-3:50) que hablan casi todo el tiempo de trámites oficiales (probate, HMRC, Tell Us Once, oficina pública) con el cartel de marca y precio solo en los últimos ≤8 s; ninguno con ≥14 s de cartel (cierre E6 o CTA a mitad) cayó dos veces. En mercados con organismos muy reconocibles (UK), dejar ≥14 s de marca y precio visibles (CTA a mitad o cierre largo) y, si igual rechazan, solo apelar: desde el 16-nov (dueño) un rechazado nunca se reemplaza ni se rehace; aquí se habían creado V1b y copiado E6 a la pocket, y al ganar V1 la apelación hubo que pausarlos (`06-creativos/revision-uk/rechazos.md`) |
