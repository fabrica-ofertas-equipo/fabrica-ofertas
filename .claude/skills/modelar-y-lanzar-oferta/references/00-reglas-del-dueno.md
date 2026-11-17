# Reglas del dueño, límites y reparto de manos

Todo lo de aquí salió de la corrida de México (2026-11-10/11). Cada regla lleva el motivo, porque el motivo es lo que permite aplicarla bien en un caso que no se parece al de México.

## 1. Reglas de trabajo que dio el dueño

| Regla | Sus palabras | Por qué | Cómo se aplica |
|---|---|---|---|
| Réplica: todo adaptado al mercado | «todo hay que rehacerlo al mercado cuando es así» y «todos son obligatorios en el test» (15-nov, Oferta/NZ) | Los videos y la landing salieron con cocinas de España y la fan page sin perfil ni publicaciones | Inventario visual completo (videos, landing, packs, checkout, post-compra, fan page) rehecho con el ambiente del país antes de montar; portadas revisadas ampliadas; fan page completa antes de activar; control de réplica lista (`12-lanzamiento-automatico.md` §3) |
| Modelar es hacer igual y mejorar | «siempre apégate a modelar lo que ya existe, no reinventes la estructura… si hay mix de videos cortos y largos, hacer lo mismo; si solo hay cortos, lo mismo. Modelar es hacer igual, y mejorar» | El referente ya está validado con gasto real; cada desvío de estructura es una apuesta sin datos | Medir en el referente (duraciones, mezcla de formatos, orden de bloques, cantidad de secciones, checkout) y replicar con margen de segundos. Lo propio es la expresión: textos, voz, imágenes, nombre, producto |
| Qué ofertas elegir | «siempre buscar las ofertas para modelar que tengan los funnels más complejos… mucho mejor si tiene muchos anuncios encendidos, más de 50, 60, 100»; y después: no un orden fijo de tipos, sino «una relación entre los mejores y más complejos, pero ir variando», con peso en «los anuncios encendidos y la antigüedad sobre todo» (2026-11-11) | Una TSL básica es fácil de copiar y tiene menos probabilidad de ser ganadora; pero si siempre se elige el mismo tipo no se aprende qué funciona | Piso de 15 anuncios y 10 días. Por encima, puntaje con complejidad, antigüedad y anuncios, y penalización por repetir tipo o tema (`01-elegir-oferta-y-mercado.md` §1.2, `scripts/ordenar_candidatos.py`) |
| Velocidad, sin pedir aprobaciones | «te autorizo a todo», «no me preguntes más acerca de si apruebo o no» | Las preguntas lo frenan | Avanzar fase tras fase. Avisar solo de lo que requiere sus manos (tabla 3). ~~Pedir el visto bueno una vez, antes de activar la campaña~~: obsoleto desde el 2026-11-13, la campaña se activa sola si pasa el control previo (§4) |
| No repetir mercado por defecto | «las dos ofertas… las modelaste en el mercado de México… si lo hiciste no sabes por qué y predeterminado, tiremos en otro mercado, crea algo para no tirar siempre en el mismo mercado» (2026-11-12) | Elegir por costumbre deja potencial afuera y no enseña nada | Comparar con `scripts/elegir_mercado.py` v3 (57 países, ninguno descartado por idioma: «no nos limitemos»): cobro tomado de Impul Pay (nunca a mano), castigo que crece con cada repetición, CPA observado, temporada, exploración y sensibilidad impresos; decir por qué gana y qué supuesto lo sostiene (`01-elegir-oferta-y-mercado.md` §2.1). Endurecida el 2026-11-13 tras «¿con qué criterio se eligió este mercado nuevamente?» |
| Presupuesto del test | «el testeo de la campaña el presupuesto siempre sale a testear con 3 tickets del producto principal (el completo en los casos donde tenés más básico y demás)… 19 sería 19x3, 27 sería 27x3» (2026-11-13) | El test tiene que poder pagar unas 3 ventas por día para que Meta aprenda y para juzgar el CPA contra el ticket real | `campaign_daily_budget` = 3 × precio en USD del producto principal (el nivel completo si hay niveles), en centavos. Lo comprueba `control_previo.py` (±5 %) y se dice en el aviso de activación. Antes se usaba 50 USD/día fijo (Oferta D salió así con un completo de 27 USD: por la regla le tocaban 81) |
| Mercado entero | «tiene que ser de todo el país que estamos apuntando, al mercado entero» | Test abierto: que Meta encuentre al comprador | Segmentar por país completo. Al hablar de la hora de inicio, decir «hora del centro de <país>» y no nombrar una ciudad: se confunde con la segmentación |
| Inicio a las 00:00 del día siguiente | «siempre que programamos campañas salen a las 00 del día siguiente… prográmalas y ya las dejarás activas» | El día se usa para armar; el anuncio arranca con el día completo y la revisión de Meta ya pasada | Crear el conjunto con `start_time` a las 00:00 del día siguiente en la hora del mercado y activar el mismo día. «Las siguientes 00» se cuentan desde el momento de activar, no desde que se creó el conjunto: si ya pasaron, conjunto nuevo (2026-11-13) |
| Voces con Google AI Studio | (regla permanente) | Calidad y consistencia | Toda locución con Gemini TTS; ningún otro motor |
| Idioma real del mercado | pidió «español de México real» con inmersión en foros y redes | Un texto traducido se nota y no vende | Fase de inmersión antes de escribir una sola línea de copy |
| Precio del producto principal | «ya no testearemos más productos con $17… si vale menos de 19, colocar 19; entre 19 y 27, el valor que vale; y si vale más de 27, el valor del producto original» (2026-11-12) | Que el CPA de equilibrio deje margen | `references/06-tienda-impultienda.md` §3 |
| Imagen de producto, precio original y checkout | «no configuraste foto de perfil al producto… revisa cómo lo hice… para que lo sepas para la próxima» | Quiere que la tienda salga ya como él la deja | `references/06-tienda-impultienda.md` §4 |
| Guardar en cada pantalla | «es necesario hacerlo en todas las pantallas que se modifica algo» | En Impultienda lo que no se guarda no existe | Guardar y comprobar en la tienda pública después de cada cambio |
| Modelar también el checkout | «en los casos donde sea posible modelar los checkouts, hagamoslo» | El checkout es parte del funnel validado | Leer el checkout del referente y replicar sus bloques con «Agregar bloque» |
| Video de la landing | (corrección del 2026-11-11) | Un anuncio reciclado cierra con «toca Más información», botón que en la página no existe | Montarlo aparte en 4:5, con cierre que nombra el botón real de la página; barra de sonido debajo del video |
| Condiciones de Meta al crear página y píxel | «poné en la regla que siempre lo hagas y que tenés la autorización para habilitar estas cosas siempre» (2026-11-14) | Dos ofertas quedaron armadas sin salir porque la corrida frenó en la casilla de condiciones | Marcar la casilla y crear la fan page; pulsar «Crear» en el píxel. Sin frenar ni avisar. Solo esos dos diálogos (`04-marca-y-activos-meta.md` §2 bis) |
| Nombre de toda campaña: «PAÍS \| Oferta \| tipo» | «poné eso como regla al crear las campañas, aunque ya lo haces, pero por las dudas» (16-nov) | El panel y la escala asignan solas cada campaña a su oferta por el nombre. PAÍS = el `mercado` del test (ES, IE, NZ…), Oferta = el `oferta` del libro tal cual, tipo = `CBO test …`, `CBO pocket …`, `CBO test variaciones …`, `Renovación …`, `Escala …`. Vale para lanzamientos, réplicas, pockets, variaciones y cualquier campaña nueva; el control previo no activa una campaña que no lo cumple |
| Responder en español | — | — | Ortografía completa, términos técnicos en su forma original |

## 2. Lo que no hago, aunque el referente lo haga

Estos son límites míos, no reglas del proyecto (el dueño las retiró como regla el 2026-11-11 y lo sabe). Se dicen al empezar la fase donde aparecen, no después, y siempre con la alternativa que sí construyo.

| El referente tiene | No lo construyo porque | Lo que sí hago |
|---|---|---|
| Reloj de 10 minutos que se reinicia en cada visita | Le dice al comprador que la oferta termina y no es cierto | Cuenta regresiva a una fecha real de fin del precio de lanzamiento, en el mismo lugar del referente. Necesita que el dueño dé la fecha |
| Precio «antes» que nunca se cobró | Es un descuento inventado | Mostrar `{{original_price}}` de la tienda: el dueño carga ese precio con sus manos y el checkout ya lo muestra igual |
| Testimonios o reseñas | Inventarlos es mentirle al comprador | Demostración del producto real (hojas, manos, uso). Reseñas solo cuando existan |
| Voz «yo lo compré y me llegó» | Es un testimonio de compra inventado | Voz de demostración: «te enseño lo que trae» |
| Contador «X personas están comprando» | Número inventado | No lo enciendo; le aviso al dueño que existe por si lo quiere encender él |
| Caras de niños | Menores en anuncios | Manos, espaldas, hojas; en cuentos ilustrados, niños de espaldas y rótulo «Cuento ilustrado» |

La skill `cro-polish` y `ofertas/AGENTS.md` fueron retiradas por el dueño el 2026-11-12 (están en la papelera). Si reaparecen, no se ejecutan. Tampoco ejecuto `cro-polish` ni otro paso que mande la landing a un tercero para añadir lo de la columna izquierda sin que yo lo vea. Si el dueño lo corre con sus manos, es su tienda: no se lo deshago, pero después de eso el HTML publicado ya no es el del disco, así que antes de publicar cualquier cambio se compara la huella (`fragmentos-navegador.md` §4) y se le dice qué saldría distinto.

No se copia del referente: textos, nombre, imágenes, video, ni el producto. Se hereda la idea y la estructura.

## 3. Lo que solo puede hacer el dueño

Pedirlo al EMPEZAR, en un solo mensaje, para no quedar bloqueado a la hora de publicar o lanzar.

| Qué | Cuándo hace falta | Cómo pedirlo |
|---|---|---|
| Iniciar sesión en Impultienda (entra con Google) | Antes de la fase 7 | Abrir `https://impultienda.ar/login` en el navegador integrado y pedirle que entre. La sesión se cae cada pocas horas |
| Iniciar sesión en Facebook / Business | Fases 5 y 3 | Igual, en el navegador integrado |
| Cuenta de Meta activa y con método de pago | Antes de la fase 10 | Comprobar con `ads_get_ad_accounts` (`account_status`, `has_payment_method`). Con pago pendiente Meta deja crear campaña y conjunto, pero rechaza creativos y anuncios |
| Conectar pasarela de cobro | Fase 7 | Avisar qué falta conectar |
| Generar y pegar el token de la API de conversiones de cada píxel, en cada tienda que lo usa | Fase 7; obligatorio desde el 2026-11-12, pedido del dueño | Va en el mensaje inicial. Dejarle abiertas, en el navegador integrado, la configuración del píxel con «Generar token de acceso» y la pantalla «Meta / Tracking» de cada tienda. Después comprobar sin leer el token (`06-tienda-impultienda.md` §5.1) |
| Compra de prueba con su tarjeta | Antes de activar, idealmente | Es lo único que prueba cobro, correo, descarga y evento de compra |
| Oír las voces de los videos | Antes de activar | Darle la galería |
| ~~Dar el visto bueno para activar~~ | Fase 11 | Desde el 13-nov la campaña se activa sola si pasa el control previo (regla L3). Rechazados (16-nov): solo se apelan una vez, nunca se reemplazan; sale con los que quedan, y una pocket 1-1-1 con su único anuncio rechazado no sale |

Nunca escribo contraseñas, tokens ni datos de tarjeta en ningún campo, aunque me los pase por el chat, y no se guardan en notas ni en memoria.

## 4. Frenos de dinero

- Activar gasta dinero: desde el 13-nov se activa sola si pasa `escalar-oferta/scripts/control_previo.py` (regla L3 del dueño: landing y checkout responden, píxel, precio 19/27, presupuesto de 3 tickets, inicio 00:00 en la zona del mercado, al menos 1 anuncio no rechazado; los rechazados solo se apelan, 16-nov). Si no pasa, no se activa. Justo antes de activar se mira la hora otra vez: si el `start_time` ya pasó, conjunto nuevo con las 00:00 siguientes del mercado (`09-campana-meta.md` §4).
- Frenos de empresa (300 USD por día y −3.000 USD acumulados): **eliminados por el dueño el 2026-11-13**. Cada oferta se corta por su propia regla (`escalar-oferta/references/02-decidir.md`).
- Corte del test con el ticket del **producto completo** (con niveles, el más caro): «la regla debería tomar en estos casos el del producto principal o completo, que en este es el de 27, para cortar» (2026-11-13).
- Créditos de Kie: cada script anota su gasto en un `.jsonl` y se detiene al llegar al tope (`--tope`). Decir el gasto al cerrar cada fase.
- Nunca borrar con comodines; cada ronda escribe en carpeta nueva y lo anterior queda de respaldo.
