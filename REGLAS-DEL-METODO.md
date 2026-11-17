# Reglas del método

Estas son las reglas con las que opera la fábrica de ofertas: cómo se buscan, modelan, lanzan, vigilan, escalan y cortan las ofertas.
Mandan sobre los valores por defecto de cualquier skill, script o agente: si algo choca con este archivo, gana este archivo.
Las cifras se pueden ajustar por instalación, pero cada cambio se documenta acá y en `ofertas/_funnels/reglas.json`, que es el archivo que leen los scripts y el panel.
Cada regla trae su porqué y quién la ejecuta; donde dice «quien opera», es la persona dueña de la instalación.

---

## 1. Búsqueda y elección de ofertas

**Se buscan ofertas que ya venden, con un radar siempre prendido en la Biblioteca de Anuncios.**
La calidad de la oferta elegida es la base de todo. El radar recorre 57 mercados en su idioma y en inglés, cada 4 horas, por señales de venta de producto digital (plataformas de cobro y frases de entrega o pago en 27 idiomas); orden de trabajo: verificar → medir → buscar. Skill `buscar-ofertas`, `scripts/radar.py` y catálogo `radar_terminos.json`; para sumar fuentes se agregan términos al catálogo, no se rehacen barridos a mano.

**Piso de tracción: 15 anuncios activos y 10 días de antigüedad.**
La antigüedad de una oferta es la del segundo anuncio activo más viejo (la mediana castiga a quien renueva creativos a diario). Una oferta con un solo anuncio activo hace 30 días o más pasa igual a medir (evergreen). El piso no se baja aunque falten candidatos.

**Se prefieren funnels complejos y con muchos anuncios, pero variando de tipo.**
Complejo = el recorrido antes de la venta: advertorial, quiz o VSL. Bump, upsell y downsell no agregan complejidad (los tienen todos); el escalonado de precios sí suma.
Un funnel básico es fácil de copiar y tiene menos chances de ser ganador; más de 50-100 anuncios activos es mejor señal. `ordenar_candidatos.py` puntúa complejidad 40 % (quiz, VSL y varios pasos valen igual), antigüedad 35 % y anuncios 25 %, con penalización por repetir tipo de funnel o tema según `ofertas/historial-modelado.json`. Nunca un orden fijo de categorías; mostrar la tabla con los números.

**Los tipos de funnel no son una lista cerrada.**
Cada funnel se describe por sus componentes y su orden; si no coincide con un tipo existente se crea uno compuesto (`quiz+vsl`, etc.), se anota con su ejemplo y se avisa. Taxonomía en `modelar-y-lanzar-oferta/scripts/taxonomia_funnels.json` y `references/taxonomia-funnels.md`.

**Decir «el barrido no encontró», nunca «no hay».**
El límite suele ser la búsqueda, no el mercado. Antes de elegir, buscar a propósito por forma de funnel (textos de quiz en varios idiomas, rutas `/quiz`, `/test`) y, si no aparecen candidatos complejos, decir cuánto se buscó.

**Nunca se espera por el banco de candidatos.**
Se lanza con 1 candidato listo; con 0, la vuelta busca hasta conseguir uno (objetivo de reserva: 3 listos). La falta de candidatos es un problema de búsqueda, no un motivo para frenar. `cupo_lanzamiento.py` devuelve `BUSCAR_Y_LANZAR`; `reglas.json → lanzamiento.banco_minimo_para_lanzar` y `banco_objetivo_listos`.

**Las iteraciones de un anunciante se leen comparando videos, no textos.**
Los copys suelen ser idénticos entre anuncios; el patrón valioso es «mismo cuerpo de video, arranque distinto». `modelar-y-lanzar-oferta/scripts/biblioteca_videos.js` (huellas de fotogramas, familias, hoja de contacto) y `banco_candidatos.py videos` / `iteraciones`. Aclarar siempre que compara imagen, no audio.

**Un bloqueo de la Biblioteca de Anuncios no se esquiva.**
Ante cualquier bloqueo se detiene y pausa (`radar.py bloqueo`, 6 h); no se cambia perfil, IP ni ritmo para pasar. Un sitio que el navegador rechaza se saltea y se avisa.

**El riesgo se evalúa por promesa, contenido y encuadre, nunca por tema.**
Una «cura» o una promesa de ingresos es mala; una guía útil sobre el mismo tema puede ser válida. No sobre-excluir ofertas legítimas: las líneas rojas son de claims, contenido y modelo de negocio.

**La landing original del referente se registra para abrirla de un clic.**
El barrido no trae la URL de destino. Se registra una vez con `python -m scripts.referentes.landing registrar <page_id> "<URL>" --escribir` y se ve en el panel.

---

## 2. Mercado

**El país se elige con `elegir_mercado.py`, nunca por costumbre ni por comodidad.**
Elegir siempre el mismo deja potencial afuera y no enseña qué mercado responde. La versión 3 puntúa 57 países con cobro medido en la pasarela (nunca puesto a mano), castigo ×0,6 por cada repetición en las últimas 4 ofertas, CPA observado, temporada, exploración del mejor país nunca probado y sensibilidad. Decir la tabla, por qué ganó el primero y si la elección es frágil; anotar `pais_destino` e `idioma` en `ofertas/historial-modelado.json`.

**Ningún país se descarta por el idioma de producción.**
Se produce en el idioma del mercado. Si el apuro empuja a un idioma cómodo, declarar ese sesgo.

**Antes de modelar, inmersión en la voz del mercado.**
Jerga, quejas, creencias y tono reales (foros, redes, reseñas) se aplican al copy de la landing, los anuncios y el producto. Guía de voz por oferta en `02-validacion/inmersion/`.

**La segmentación es siempre el país entero.**
Nunca una ciudad o región, ni nombres de ciudad en el nombre del conjunto. Al informar la hora de inicio, aclarar que es solo el huso horario del mercado.

**Revisar si el mercado depende de un método de pago local que la pasarela no cubre.**
Los métodos locales solo aparecen si el comprador ve su moneda (modo Markets). Algunos (BLIK, Przelewy24, Bizum) no están en Impul Pay y exigen Stripe con su configuración de métodos locales.

---

## 3. Modelado (landing, checkout, producto, bonos)

**Modelar es hacer igual y mejorar: la estructura del referente no se reinventa.**
El referente ya está validado con gasto real; cada desviación de estructura es una apuesta sin datos. Se replican orden de secciones, orden de bloques dentro de cada sección (medido en móvil), duración y mezcla de videos, ritmo. Lo propio es la expresión (textos, voz, imágenes, nombre) y mejoras puntuales; si hay que apartarse, decirlo y justificarlo antes.

**Se modela la misma oferta, mejorada un poco.**
Mismo tamaño de pack, niveles, tipos de bonus, garantía y pago único; mejoras pequeñas respaldadas por la voz del mercado (garantía con procedimiento, bonus ligado a la objeción principal, bump, muestra). No achicar ni rediseñar la oferta.

**Del referente se toma el esqueleto, nunca la expresión.**
Se copian estructura e interacciones del HTML; no se copian textos, marca, imágenes, reseñas, cifras ni enlaces de checkout o píxel.

**En el desarme se tocan todos los botones de compra y se leen los scripts del referente.**
Así aparecen las ofertas que suben el ticket antes de pagar: subida previa (al elegir el básico ofrece el completo), bump, upsell y downsell. Se modelan con precios que se cobran de verdad (en Impultienda, una tienda aparte para el precio rebajado) y rótulos ciertos. Guía `modelar-y-lanzar-oferta/references/11-ofertas-que-suben-el-ticket.md`.

**Precio del producto principal: el mayor entre 19 USD y el precio del principal del referente (regla 19/27).**
Un ticket más bajo deja un CPA de equilibrio sin margen. En moneda local se usa un precio redondo cercano. Los niveles más baratos y los upsells no se rigen por esta regla. La landing y el video de venta no pueden decir otro precio en voz ni en texto. Lo comprueba `escalar-oferta/scripts/control_previo.py` (`reglas.json → lanzamiento.precio_minimo_usd`).

**Cada tienda nueva sale con la configuración de checkout de la instalación y con los bloques del checkout del referente.**
La configuración base está en «Qué tiene que poner cada instalación»; además, si el referente usa bloques en su checkout (imagen, video, gente usando el producto), se replican con «Agregar bloque». Guía `modelar-y-lanzar-oferta/references/06-tienda-impultienda.md`.

**En Impultienda, cada pantalla se guarda y se comprueba.**
Cada pantalla tiene su propio botón Guardar: lo que no se guarda no existe. Guardar, recargar y comprobar en la tienda pública. Si una tarea va a tocar la tienda, iniciar sesión al empezar, no al final.

**La imagen del producto va siempre.**
Se ve en el resumen del checkout. Se sube con el conector MCP (`editar_producto`, subir/confirmar).

**El precio original (tachado) se fija a mano por mercado y la landing lo lee de la variable.**
Criterio orientativo: ≈ 2,9 × el precio, terminado en 9, fijado por mercado y no por conversión. La landing usa `{{original_price}}`, nunca una cifra fija. El sistema calcula el valor y deja la pantalla lista; quien opera decide si lo guarda.

**Cada bonus de la oferta se carga como bono, no solo dentro del PDF.**
Con bonos cargados el checkout muestra «+N bonos gratis» y cada uno llega como archivo propio. Un bono por bonus, con su PDF y portada vertical («Agregar bono»); el campo «Valor percibido» queda vacío salvo que quien opera lo cargue.

**Al lanzar no se crean upsells post-compra.**
Se habilitan después del test, con el backend ofensivo. Excepción: lo que sea estructura del referente (complemento en el checkout, niveles, subida previa).

**La landing se publica como HTML completo con variables de precio y se verifica por huella.**
Variables del servidor: `{{price}}`, `{{original_price}}`, `{{savings}}`, `{{currency}}`; botón `<a href="/checkout">` o `<button data-checkout>`. Con el conector, `guardar_html` con vista previa y token; correcciones por `reemplazos`. Antes de pisar, comparar la huella de lo publicado con el archivo local para no perder cambios hechos a mano.

**El video de cabecera de la landing no es un anuncio reutilizado.**
Se monta aparte en 4:5, con cierre que apunta al botón real de la página; barra de sonido debajo del video (no encima de los subtítulos) y botón de compra justo debajo.

**Las imágenes de la oferta se generan con Kie.ai y las revisa un agente independiente.**
Nano Banana Pro para lo que lleva texto; hasta 3 intentos por imagen. Si el producto todavía no existe, base ilustrativa que se reemplaza por la real. Nunca imágenes del referente como entrada, ni rostros o reseñas inventados.

**El sistema no fabrica prueba social ni urgencia.**
No se escriben reseñas ni cifras inventadas, ni contadores que se reinician, ni un precio «antes» que nunca se cobró. La alternativa con respaldo real es un precio de lanzamiento con fecha de fin que se cumple y su cuenta regresiva. La barra «X personas están comprando» la enciende quien opera, si quiere; el sistema avisa que existe.

**Tras publicar, se arma el expediente del funnel.**
Carpeta `ofertas/_funnels/<Nombre en tienda>/` con la landing original, el HTML pegado y el inventario de lo no modelado (testimonios, urgencia, escasez y lo que se dejó afuera por políticas), con el mercado arriba (país, moneda, precios, campaña, inicio). Las diferencias de estructura van al desarme, no a este inventario. `modelar-y-lanzar-oferta/scripts/expediente_funnel.py`, guía `references/10-expediente-del-funnel.md`.

---

## 4. Creativos y anuncios

**Antes de escribir guiones se ven enteros 13-15 videos del referente, repartidos entre viejos, intermedios y nuevos.**
Con 3 videos se saca una conclusión falsa («una sola familia»); con más aparecen formatos, ganchos y aperturas distintas. Muestra por tandas de fecha de inicio y por puesto de impresiones. Guía `modelar-y-lanzar-oferta/references/02-desarme-del-referente.md` §2.0.

**Se replica la mezcla y la duración de los anuncios del referente.**
Si hay cortos y largos, se hacen cortos y largos; margen de unos segundos. Se replican en proporción los formatos, la cantidad de ganchos, las tomas propias de apertura y las variantes de cierre.

**Reutilizar clips está permitido; que todo se vea igual, no.**
Meta premia la diversidad creativa. Antes de entregar se mide cuánto material comparten los videos (umbral orientativo: ningún video con más del 35 % de su tiempo en tomas presentes en 6 o más). Guía `08-creativos.md` §1.1.

**Cada anuncio del referente se clasifica por etapa (frío o cierre) y destino.**
El referente puede tener marca, base de clientes y retargeting que una marca nueva no tiene. En el primer test, todas las piezas abren con gancho; las de cierre («nombre + precio») se modelan en formato pero con gancho, y el precio va en el texto o la ficha. Las piezas de temporada no entran en el recuento. Guía `08-creativos.md` §1.3.

**El texto nunca tapa una cara.**
Una cara tapada en los primeros segundos le quita al anuncio lo que retiene. Con personas en la apertura, la altura del texto se decide plano por plano (arriba al 20 % o abajo al 62 %, píldora de dos líneas) y se pide la imagen inicial con fondo libre. Revisar con hoja de contacto: un cuadro cada 0,5 s hasta los 3 s y después cada 1,5 s.

**Toda locución se hace con Gemini TTS (Google AI Studio).**
Anuncios, VSL, video de la landing y réplicas. ElevenLabs queda solo para efectos de sonido.

**En la renovación, cada anuncio se juzga por sus métricas y se cambia una pieza por iteración.**
CTR ≥ 1,5 % → no tocar; retención < 10 % → rehacer el cuerpo; si falla el cierre → rehacer el llamado. Se anota la pieza cambiada. `escalar-oferta/scripts/metricas_embudo.py anuncios`; umbrales en `reglas.json → metricas` (la retención se recalibra con datos propios).

---

## 5. Lanzamiento y campaña

**Dos ofertas nuevas por día, solas, mientras haya menos de 8 en test.**
Tarea «lanzar-ofertas» (dos veces por día) con `modelar-y-lanzar-oferta/scripts/cupo_lanzamiento.py`; guía `references/12-lanzamiento-automatico.md`.

**La campaña arranca a las 00:00 del día siguiente, en la zona horaria del mercado.**
El día de trabajo se usa para armar y revisar; el anuncio arranca con el día completo de presupuesto y la revisión de Meta ya pasada. El conjunto se crea desde el principio con `start_time` (Meta no deja editarlo después). Si al activar el inicio ya pasó, se crea un conjunto nuevo con las 00:00 siguientes.

**Presupuesto del test: CBO diaria de 3 tickets del producto principal.**
Tiene que poder pagar unas 3 ventas por día para que Meta aprenda y para juzgar el CPA contra el precio real. Si hay niveles, se toma el completo. Lo comprueba `control_previo.py` (tolerancia ±5 %).

**La campaña se activa sola si pasa el control previo.**
`escalar-oferta/scripts/control_previo.py` verifica landing y checkout, píxel, precio 19/27, presupuesto de 3 tickets, inicio a las 00:00 del mercado y corte configurado. Con menos de 5 anuncios rechazados sale igual con los aprobados; con 5 o más no se activa y se avisa. Se activa de arriba hacia abajo (campaña, conjunto, cada anuncio).

**Estructura del test: una CBO, un conjunto, unos 10 anuncios, objetivo compra.**
Un píxel y una fan page por oferta, marca propia por oferta, sin Instagram; anuncios a la landing.

**La fan page sale con 10 publicaciones.**
3 al crearla y 7 programadas, una cada 8-12 h en horas del mercado durante el test; lo mismo en cada página nueva de una réplica. Guía `modelar-y-lanzar-oferta/references/04-marca-y-activos-meta.md`.

**La API de conversiones se comprueba en Meta, no en archivos de estado.**
Con `ads_get_dataset_stats` del píxel y `event_source: SERVER_ONLY`: si hay eventos por servidor, está cargada. Para contar compras se usa solo el Purchase del navegador (con CAPI, la compra cuenta doble). El token lo pega quien opera, uno por píxel; se copia a otra tienda con `configurar_tracking` y `pixel_de_otra_tienda: true`.

**El funnel se prueba sin ensuciar el píxel.**
`modelar-y-lanzar-oferta/scripts/probar_funnel.py` bloquea el píxel. La entrega real (cobro, correo, descarga, Purchase) se comprueba con una compra de punta a punta.

**Una oferta que gana una semana se replica sola (E6).**
7 días con ROAS neto (neto de la tienda ÷ gasto en Meta) ≥ 1,30 → se lanza en el siguiente mejor país de `elegir_mercado.py` donde el referente no pauta. Cuenta como uno de los 2 lanzamientos del día y tiene prioridad sobre una oferta nueva (`cupo_lanzamiento.py` → `LANZAR_REPLICA`).

**Si una oferta pega fuerte desde el día 1, se puede replicar ya, con creativos 50/50.**
Otro mercado puede responder a otro ángulo, y conviene ocupar mercados rápido. Mezcla de la réplica: 5 iteraciones del anuncio que más vendió + 5 de los que mejor rindieron en intención (CTR, hook rate, retención, pagos iniciados), no la 7+3 de la renovación. El producto se adapta al país (trámites, organismos y plazos con fuente oficial), no solo se traduce; píxel propio (nunca el de la madre: cada oferta tiene su público), fan page propia por país y upsells de la madre adaptados.

---

## 6. Vigilancia, corte y escala

**El test es el día 1 del mercado, de 00:00 a 00:00.**
Con ventas al cerrarlo pasa a post-lanzamiento. Sin ventas sigue en test hasta vender o llegar al corte; si Meta casi no entregó, solo se avisa, sin tocar nada.

**Corte en test: gasto ≥ 1,5 × ticket del producto completo × máx(1, ventas) → se apaga en el momento.**
Equivale a CPA ≥ 1,5 tickets: una oferta puede tener ventas y aun así un CPA que no se paga. El ticket es el precio USD más alto del funnel. Se pausa en la misma vuelta, sin preguntar ni esperar a las 00:00. `escalar-oferta/scripts/vigilar_corte.py`; `reglas.json → test.corte_tickets`. Reactivar una oferta apagada lo decide quien opera.

**Segunda oportunidad (R1b): +0,5 ticket una sola vez.**
Solo sin ventas y con buenas señales: CTR ≥ 1 %, ≥ 8 % de las visitas llega al pago y ≥ 3 pagos iniciados (el problema es el pago o la muestra, no el anuncio ni la página). Si falla el checkout, se arregla antes.

**La vigilancia está siempre prendida: vuelta completa cada hora y vuelta rápida cada 15 minutos solo cerca del corte.**
Cada hora sin vigilar es gasto. La vuelta rápida corre solo para tests a 0,6 ticket del corte o menos. Tarea «vigilancia-ofertas», filtro `escalar-oferta/scripts/hay_trabajo.py`, guía `references/04-vigilancia.md`. Si la tarea aparece borrada o desactivada, se recrea con el prompt de la guía.

**Corte post-test (R4): CPA real de 3 días ≥ 1,5 × lo que deja cada venta → se apaga.**
Lo que deja cada venta es el AOV neto dinámico, con backend incluido. También corta si el gasto de 3 días llega a 1,5 × eso sin ventas. Las ventas de upsell, bump y downsell suman al neto pero no cuentan como compradores. Se mide la oferta entera: las rondas de renovación no frenan el corte.

**Un funnel se juzga con las referencias del embudo.**
Checkout sobre visitas: 8-12 % (bueno ≈ 10 %). Checkout → compra: 25-30 %. CPA ≤ neto por venta que deja la pasarela. Con menos de ~30 checkouts, los porcentajes se dicen como pista. Guía `escalar-oferta/references/01-revision-diaria.md`.

**Escala simétrica en la misma CBO (E1-E5).**
ROAS de Meta > 2 → surfeo cada 3 h: +30 % en ROAS 2, lineal hasta +50 % en ROAS 6,5 (más arriba, +50 %). ROAS 1,75-2 → +30 % cada 24 h; desde 500 USD/día tampoco se surfea, solo +30 % cada 24 h. ROAS de la tienda < 1,5 → −30 % en el momento (con ≥ 3 h y ≥ 2 compras o ≥ 1,5 tickets gastados). ROAS de tienda entre 1,5 y 1,75 → nada. Siempre con ≥ 2 compras desde el último cambio, sin techo, sin bloqueo del día. `escalar-oferta/scripts/escalar_presupuesto.py`, guía `references/07-escala-simetrica.md`, `reglas.json → escala`.

**Nunca se baja del presupuesto inicial, y los presupuestos van en dólares enteros.**
Antes de bajar se confirma con la tienda (Meta atribuye tarde). No corre en el día 1 del test.

**Si Meta y la tienda no coinciden, manda la tienda.**
La tienda incluye los upsells. La revisión diaria compara la ganancia del día con la del escalón anterior y lo informa.

**Por ahora se escala solo en la misma CBO del test.**
Campañas con bid cap o cost cap, CBO «pocket», ABO escalonadas o una segunda cuenta quedan para cuando haya volumen y quien opera lo pida (`07-escala-simetrica.md` §4).

**Aviso de segunda cuenta publicitaria a 200 USD/día con ROAS ≥ 1,75.**
`reglas.json → cuentas.segunda_cuenta_desde_usd`. Es un aviso, no una acción.

**No hay freno de empresa ni de liquidez.**
Cada oferta se corta por su propia regla (R1, R4); no se proponen topes de pérdida por cuenta.

**Los anuncios que solo gastan no se pausan.**
La CBO reparte sola (R14).

**Los cambios de campaña van a las 00:00 del mercado, salvo apagar y los cambios de presupuesto por ROAS.**
Esos se hacen en el momento (R11).

**Una oferta que pega se renueva todos los días con 10 creativos (R9).**
«Pega» = pasó el test con ventas y CPA real ≤ equilibrio (`escalar-oferta/scripts/ofertas_que_pegan.py`). Cada día: 7 iteraciones del ganador de los últimos 3 días + 3 nuevos modelados de anuncios del referente no usados, en un conjunto nuevo dentro de la misma CBO, que sale a las 00:00 del mercado. Se produce cuando faltan 5-16 h para la 00:00 de ese mercado; la tarea «renovacion-diaria» corre cada 2 h y marca la ronda «produciendo» para no repetirla. Sin tope de créditos. Guía `references/05-renovacion-diaria.md`.

**Todo conjunto nuevo en una CBO lleva un mínimo de gasto del 20 %, que conserva dos días enteros.**
Sin mínimo, la CBO le da casi todo a los anuncios viejos. La API lo rechaza: se pone en el Administrador de anuncios (Límites de gasto → valores porcentuales → mínimo diario promedio 20 %, máximo vacío → Publicar) y se comprueba por API `daily_min_spend_target`. Lo hace el agente, nunca queda como pendiente de quien opera. A los dos días se quita, para que los mínimos no sumen 100 % (R9b, R10). Guía `escalar-oferta/references/03-renovar-creativos-y-escalar.md` paso 6.

**El diagnóstico del embudo dice de qué lado está el problema.**
Tasa de carga < 60 % con 50+ clics → probar la página; CPM dos días seguidos al doble del promedio → aviso; sospecha de clon con 20+ pagos iniciados → primero probar el checkout y después conceptos nuevos. `metricas_embudo.py` (`vuelta`, `periodos`); umbrales en `reglas.json → metricas`.

**Cada test tiene su costo y su neto en el libro.**
Créditos (Kie, Gemini y otros), gasto de Meta y costos puntuales contra lo facturado neto de comisiones: un test apagado pudo haber vendido. El libro se escribe solo con `escalar-oferta/scripts/libro.py` (candado y respaldo) y la tabla se regenera con `libro_de_tests.py`. Cargar cada ronda de renovación y cada backend, o el panel muestra la oferta mal.

**La búsqueda no se optimiza con datos propios hasta tener una oferta con ≥ 1.000 USD de ganancia por día.**
Antes de eso solo se registran diagnósticos.

---

## 7. Backend y ticket

**Una oferta que pasa el test con ventas recibe backend ofensivo ese día (R3).**
Tres productos complementarios elegidos desde la voz del comprador, producidos en PDF y cargados como upsells post-compra. Lo dispara la revisión diaria; skill `backend-ofensivo`.

**Backend anticipado (R3b): con ventas y corte imposible, se arma ya y se prende al cierre del test.**
Se arma en cuanto `vigilar_corte.py` marca `backend_anticipado` (hay ventas y ni gastando el 175 % del presupuesto en las horas restantes se llega al corte). Queda listo y apagado; se activa a las 00:00 del mercado siguiente al inicio. Nunca se activa un embudo post-compra mientras la oferta está en test: el test se lee limpio.

**Objetivo del backend: ingreso por comprador ≥ 1,5 × el ticket.**
Un ticket más alto sube el CPA que se puede pagar; con 1,2 × casi no mueve la aguja. Receta: 1.ª oferta ≈ 1 × ticket (rebaja ~38 %), 2.ª ≈ 0,7 ×, 3.ª la más barata, y un order bump propio de 0,2-0,3 ×. Referencias en frío: la 1.ª oferta post-compra se acepta 2-7 % y el bump 40-80 %. Datos nuevos antes que viejos: el negocio cambia rápido.

**El order bump es propio: nunca repite una oferta post-pago.**
Si el bump es una oferta post-pago, quien no lo tilda la ve repetida y se pierde un upsell. Se elige analizando comprador, productos y los bumps de la competencia. Tiene que entenderse en dos segundos: el nombre dice el formato («PDF»), abre con lo que sirve a todos, la descripción empieza por el problema y la imagen muestra la pieza rellena. Si con el bump el paso checkout → compra cae más de 5 puntos, se saca. Guía `backend-ofensivo/references/01-productos-y-precios.md`.

**El precio de los upsells se fija contra el mercado, no contra el principal.**
El principal es una oferta de entrada; tras el pago la confianza es máxima y la compra es de un clic, así que la primera oferta puede costar igual o más. La rebaja va como downsell de la propia oferta. El precio aprende solo (R13): `backend-ofensivo/scripts/precio_upsells.py`, escalera de 5 precios, tandas de 30 vistas, muestreo de Thompson hacia el precio que más deja por comprador, aprendiendo entre ofertas.

**Todas las tiendas del funnel llevan los mismos upsells.**
Cuando hay varias tiendas (niveles, subida previa), cada una tiene su embudo por su producto principal. Ojo: el complemento del checkout ocupa un cupo de upsell.

**El backend queda activo al terminarlo, sin volver a preguntar.**
Un embudo en pausa no vende. Antes: recorrido de prueba por todas las ramas y cada pantalla guardada; después: «Pausado» → «Activo» en cada tienda, recargar y comprobar. Guía `backend-ofensivo/references/02-armar-en-impultienda.md`.

---

## 8. Soporte y poscompra

**Un único correo de soporte genérico de la instalación, en todas las tiendas y landings.**
Un correo personal da poco profesionalismo. Se configura con reenvío al buzón que se lee.

**El soporte responde solo lo simple, dos veces por día.**
Tarea «soporte-clientes» con la guía `escalar-oferta/references/06-soporte.md`: «no me llegó», «no abre» y dudas se contestan con plantilla y enlace; reembolsos, quejas fuertes y casos raros quedan como borrador con etiqueta y aviso a quien opera.

**Los reembolsos los decide quien opera, caso por caso (P1).**
El sistema prepara la respuesta y la devolución, avisa y espera el sí.

**Una disputa o contracargo se responde el mismo día con la prueba de entrega (P2).**
Orden, correo de entrega y registro de descarga; después se avisa.

**Las opiniones de clientes se publican solo reales y con permiso.**
Se corrigen solo tildes y puntuación; estrellas únicamente si la persona dio una calificación. Van en el lugar donde el referente pone sus reseñas.

---

## 9. Automatización y tareas

**Las cifras viven en un solo archivo: `ofertas/_funnels/reglas.json`.**
Lo leen todos los scripts y el panel. Se cambia ahí, nunca como número suelto en un script o una guía.

**Una regla por situación, firmada o propuesta.**
Firmada = se ejecuta sola; propuesta = se calcula e informa hasta que quien opera la firme. La tabla vive en `escalar-oferta/references/02-decidir.md` y su espejo en el panel (`dashboard/web/lib/flujo.js`, `REGLAS`); al firmar una regla, cambiarla en los dos lugares.

**El sistema está dividido en cuatro skills, en este orden.**
`buscar-ofertas` → `modelar-y-lanzar-oferta` (termina en la activación) → `escalar-oferta` (test, corte, revisión, renovación, escala) → `backend-ofensivo` (lo dispara la revisión diaria). Cada skill se carga entera: no mezclar momentos.

**Toda tarea programada empieza con un filtro barato.**
Cada corrida es una sesión entera; cargar una skill para terminar en «nada nuevo» es gasto. Si no hay trabajo, termina en una línea (con latido si el panel lo espera). El filtro no puede sacar trabajo que la tarea sí hacía; ante la duda, corrida completa. Cambiar la frecuencia de una tarea lo decide quien opera.

**Tareas que sostienen el sistema.**
«radar-ofertas» y «buscar-ofertas» (búsqueda y banco), «lanzar-ofertas» (2 por día), «vigilancia-ofertas» (cada hora, con vueltas rápidas), «renovacion-diaria» (cada 2 h en horario diurno), «soporte-clientes» (2 por día) y los chequeos diarios de saldos y servicios (`escalar-oferta/scripts/chequeos_diarios.py`). Salud de campañas, píxel y cuenta en cada vuelta con `salud.py`; avisos sin repetir con `avisos.py`.

**Método de construcción: a mano → pulir → skill.**
Cada paso se corre primero a mano, se pule y recién después se convierte en skill. Al terminar cada corrida se actualizan `tropiezos.md`, la guía de la fase y el `CHANGELOG.md` de la skill; al cambiar una skill, el mapa de procesos del panel (`#/flujo`).

**Las decisiones de automatización se toman con preguntas con opciones.**
Contexto, números y la opción recomendada primero.

**El panel habla en lenguaje de negocio.**
«Requiere tu atención» arriba, el detalle técnico a un clic, sin recortar información. Corre siempre como agente de inicio, no con `nohup`.

**Los secretos los carga siempre una persona.**
El sistema nunca escribe ni guarda contraseñas o tokens (CAPI, Meta, pasarelas): deja la pantalla o el paso listo y pide que los pegue quien opera, fuera del chat y fuera del repositorio.

---

## Qué tiene que poner cada instalación

Campos que cada instalación completa con sus propios valores (en `.env`, en `reglas.json` o en la configuración de cada servicio). Ninguno viene cargado en el kit.

**Identidad y soporte**
- Correo de soporte genérico (dominio propio) y buzón al que reenvía.
- Conector de correo para la tarea de soporte y configuración «Enviar como» la dirección de soporte.
- Zona horaria de quien opera (horario de las tareas programadas).

**Panel y nube**
- Dominio o subdominio del panel y su protección de acceso (por ejemplo, Cloudflare Access con política propia).
- Clave fija del panel.
- Cuenta de Cloudflare, túnel y worker de la capa en la nube (dominio, base de datos, cron).
- Máquina que corre los agentes de inicio (panel, lectura de Meta, sincronización con la nube).

**Meta**
- Portfolio comercial, cuenta publicitaria y método de pago.
- App de Meta y usuario del sistema con permiso de lectura de anuncios: `META_ACCESS_TOKEN`.
- Token CAPI por píxel (lo pega quien opera, uno por píxel).
- `META_AD_LIBRARY_TOKEN` para la API oficial de la Biblioteca (UE/UK), si se usa.
- Cuenta publicitaria de respaldo (para el aviso de 200 USD/día).

**Impultienda y cobro**
- Cuenta de Impultienda y plan (cupos de bonos y upsells, comisión, cantidad de tiendas).
- Conector MCP de Impultienda autorizado.
- Webhook saliente hacia la capa en la nube y su secreto (`IMPULTIENDA_WEBHOOK_SECRET`).
- Zona horaria de las tiendas.
- Pasarela: Impul Pay y/o Stripe (con cuenta propia), métodos locales habilitados y modo Markets.
- Tabla de cobro y comisión neta por mercado para `elegir_mercado.py` y para el neto por venta.
- Plantilla de checkout de la instalación:
  - plantilla de checkout;
  - bloques arriba y abajo;
  - posición del resumen de compra;
  - anuncio de bonos;
  - sellos y días de garantía visibles;
  - colores (botón, precios, fondo);
  - wallets arriba (sí o no);
  - barra «Checkout seguro» (sí o no);
  - barra «X personas están comprando» (la decide quien opera);
  - datos que se piden al comprador;
  - estilo de tarjeta del order bump, temporizador del bump y descripción visible.
- Criterio del precio original (multiplicador y terminación) y si se carga.
- Precio redondo en moneda local por mercado para la regla 19/27.

**Producción**
- Clave de Kie.ai (imágenes y video).
- Clave de Google AI Studio (Gemini TTS) y voces elegidas por idioma.
- Clave de ElevenLabs (solo efectos de sonido), si se usa.
- Cuenta de GitHub con `gh` autenticado (subidas temporales).

**Cifras de negocio**
- Meta de ganancia diaria de la cartera (`reglas.json → meta`).
- Cualquier cifra de este archivo que la instalación ajuste, anotada acá y en `reglas.json`.
