# Desglose del video — todas las variables, paso a paso

> Fuente: "Así construiría un negocio de una sola persona con Claude en 30 días" (Ramiro Cubria, ~37,1K suscriptores; publicado 28/10/2026; ~25:29; 24.645 vistas al capturar; autodoblaje al español). Transcripción en `docs/fuente/` (glosario de errores del autodoblaje en `00-metadatos-y-comentarios.md`). Los minutos (entre paréntesis) remiten a esas transcripciones, que solo marcan el **inicio de cada bloque** (0:00, 0:29, 1:14, 2:26, 4:01, 4:46, 5:48, 6:56, 7:05, 8:11, 9:09, 10:45, 11:48, 12:47, 13:42, 14:45, 16:00, 16:33, 17:40, 18:24, 19:51, 20:57, 22:05, 23:19, 24:53): un minuto dentro de un bloque es aproximado. Auditado contra la fuente el 2026-11-06 (completitud y fidelidad).
> Este documento describe **lo que el video hace y dice**. Lo que nosotros agregamos o corregimos está marcado como `[NUEVO]` y se desarrolla en las especificaciones de `departamentos/`.

**Leyenda:** `[E]` entrada humana · `[D]` decisión · `[S]` salida generada · `[M]` métrica, número o umbral citado · `[H]` hueco (el video no lo dice y hace falta para autonomía) · `→ Dx` departamento del sistema que absorbe ese paso.

---

## 0. La tesis del video en diez líneas

1. Un negocio de una sola persona no necesita una app: necesita **productos digitales** (información empaquetada que resuelve un problema concreto: guía, plantilla, PDF, ebook).
2. Servicios = vender tu tiempo (no escala sin equipo). Producto digital = se crea una vez y se vende infinitas veces, sin logística, stock ni devoluciones físicas.
3. Antes hacía falta ser experto y contratar programadores; hoy la IA investiga, estructura, redacta el producto **y monta la página de ventas y el cobro**.
4. Meta realista: "un sueldo extra o dos" (la cifra de 2:26 es **ininteligible** en el autodoblaje; la única cifra audible es "3.000 por mes en ganancia", en 24:53, como lo que calcula su entrenamiento), compatible con estudio o trabajo, sin empleados, sin mostrar la cara.
5. Plan de 30 días: **Semana 1** elegir problema y armar la oferta · **Semana 2** producto + landing · **Semanas 3-4** tráfico con anuncios y primeras ventas.
6. Dos herramientas: **Venzio** (investigación de mercado + oferta + ángulos + order bump; el autor dice también que arma el producto y redacta la publicidad, aunque en la demo el producto y los guiones los hace Claude) y **Claude** (producto, página, guiones, estáticos). **Higgsfield** para video de anuncios con IA.
7. La validación del mercado es "mirar la Biblioteca de Anuncios de Meta": si alguien corre muchos anuncios vendiendo una solución a ese problema, "está ganando mucha plata".
8. La oferta se construye con una entrevista de 10 preguntas y sale con puntaje, entregables, garantía, urgencia, competidores, análisis de anuncios, order bump, ángulos de venta y análisis del prospecto.
9. Objetivo del día 30: **no** hacerse millonario sino "tener la rueda girando": problema validado, producto terminado, tienda cobrando, tráfico entrando. Las primeras ventas son la evidencia.
10. Si funciona, escalar; si no, armar otra oferta/producto y seguir testeando. El video es también un embudo hacia su entrenamiento gratuito y su consultoría.

## 1. Mapa del flujo del video

```
SEM 1 ─ Elegir UN problema (4 fuentes) ──► Venzio: investigar mercado + Biblioteca de Anuncios
        ──► Entrevista (10 preguntas) ──► OFERTA (score, entregables, garantía, urgencia, prueba,
            competidores, análisis de anuncios, order bump, ángulos, análisis del prospecto)
SEM 2 ─ "Copiar todo" ──► Claude: PRODUCTO v1 (PDF, checklist, prompts, herramientas) ──► revisión humana
        ──► Claude/constructor: LANDING (oferta + 2 prompts de estética/estructura) ──► checkout con bump ──► publicar
SEM 3-4 ─ TRÁFICO: (a) orgánico  ó  (b) anuncios ──► guiones (Claude) ──► creativos (estáticos: Claude · video: Higgsfield)
        ──► campaña en Meta (Claude conectado al administrador de anuncios) ──► primeras ventas
DÍA 30 ─ ¿Funciona? ──► sí: escalar · no: nueva oferta/producto y repetir
```

---

## 2. Etapa por etapa

### E0 — Elección del vehículo de negocio (0:00–4:46) → O0, D3

**Qué hace:** abre con un gancho (0:00, 0:29: el modelo "de una sola persona" frente a las apps con IA), compara servicios vs productos y elige productos digitales. El autor descarta los productos físicos ("claramente con Claude no te vas a poner a vender fundas de teléfono", 2:26) y presenta el producto digital como "lo mejor de los dos mundos" (digital + e-commerce, sin stock ni logística).

| Tipo | Variable | Valor en el video |
|---|---|---|
| `[D]` | Modelo de negocio | Servicios (venden tu tiempo: con 10 clientes "sos el empleado de 10 jefes"; el autor facturó "varios millones" en servicios pero con un equipo de 30+ personas, 1:14) vs **productos digitales** (elegido: se crea una vez y se vende infinitas veces; vender más no exige más tiempo del operador, 2:26) |
| `[D]` | Tipo de producto digital | ebook, plantilla, guía, PDF (ejemplo final: guía PDF) |
| `[M]` | Meta económica | "un sueldo extra o dos por mes" (2:26; cifra ininteligible, el glosario infiere 3.000 pero no es seguro `[SUPUESTO]`); "3.000 por mes en ganancia" solo audible en 24:53, remitiendo a otro entrenamiento; **la moneda no se dice en el audio** (el glosario de la fuente asume USD `[SUPUESTO]`) |
| `[M]` | Restricciones del operador | Una persona, una computadora, 30 días, sin programar, sin saber marketing, sin mostrar la cara |
| `[M]` | Costo "antes" de una web profesional | "mínimo $1,000" hace unos 5 años (4:01; el autor dice también "hace 3 o 4 años" para la barrera de ser experto y contratar programadores) |
| `[M]` | Qué promete la IA hoy | Investiga, estructura y redacta el producto **y** monta en minutos una página "que vende y **entrega el producto solo**", "conectada con todas las pasarelas de pago" (4:01): afirmación sin demostración de la entrega automática (ver §5, huecos 14 y 22) |
| `[H]` | Mercado/país/idioma, capital inicial, costo de herramientas, horas diarias | No se mencionan en el video (la descripción promete "poco capital" y cobrar "desde cualquier país", sin cifras) |

### E1 — Semana 1 · Elegir el problema (5:48–6:56) → D1

**Qué hace:** elige un único problema que la gente "ya esté pagando por resolver".

| Tipo | Variable | Detalle |
|---|---|---|
| `[E]` | Fuente del problema | (a) lo que sabés hacer bien y a otros les cuesta; (b) lo que te preguntan siempre; (c) un problema que ya resolviste en tu vida; (d) lo que la gente pide en los comentarios de la competencia y nadie resuelve (el autor dice "cuatro lugares" pero encadena (c) y (d) dentro de la segunda explicación) |
| `[D]` | Cantidad de problemas | **Uno solo** |
| `[D]` | Criterio de elección | Resuelve un problema por el que la gente **ya paga** (demanda pagada existente) |
| `[S]` | Ejemplos | Máquinas del gimnasio y cómo usarlas · plantilla de finanzas personales ("cobro pero a fin de mes no sé a dónde se va la plata") · sacar más de 8 en la universidad · ser muy bueno en algún juego / usando IA / editando videos con IA (este último es el que usa en la demo) |
| `[M]` | Premisa | "Todo producto digital resuelve un problema por el cual la gente **ya está pagando**" y "problemas de todos los días"; es una afirmación, no se muestra evidencia |
| `[H]` | Cómo se puntúan/ordenan los candidatos, tamaño de mercado, tendencia, saturación, riesgo de políticas, vida útil del contenido | No se explican |

> El autor afirma que "el 99 % se pierde meses investigando a mano": ese es el espacio que ocupa Venzio. **`[NUEVO]`** nosotros lo convertimos en un departamento propio (D1) porque la elección del problema es la decisión de mayor palanca de todo el flujo.

### E2 — Investigación y validación automática con Venzio (7:05–9:09) → D2

**Pasos de interfaz:** login → "Mis ofertas" → "Crear oferta" → ¿desde dónde querés arrancar? → texto libre → investigación automática → opciones → continuar.

| Tipo | Variable | Valor en el video |
|---|---|---|
| `[D]` | Punto de partida | (A) "algo que ya sé hacer" vs (B) **"un problema que detecté"** (elegido) |
| `[E]` | Descripción del problema (texto libre) | "Mucha gente reniega demasiado con editores de video. Les cobran caro, les hacen perder tiempo, no les entregan a horario los videos y es demasiada frustración manejar editores. La gente no sabe cómo editar contenido con inteligencia artificial y les encantaría reemplazar a los editores con IA" |
| `[E]` | Cuentas de Instagram de referencia (opcional) | "No conozco ninguna" → vacío |
| `[D]` | Generar ángulos de venta | Sí |
| `[D]` | Generar order bumps | Sí |
| `[S]` | Acción automática | "Investigamos el mercado y los anuncios de Meta antes de armar la oferta": abre la Biblioteca de Anuncios de Meta y busca quién ya vende un producto digital para ese problema **con muchos anuncios** |
| `[M]` | Regla de validación | "Muchos anuncios" ⇒ "la gente ya está ganando mucha plata con este problema" (7:05 y 13:42) |
| `[M]` | Qué dice de la Biblioteca (8:11) | "El lugar en donde todo el mundo publicita los productos digitales" y "el mejor lugar para saber si tu producto va a funcionar o no". Es **impreciso**: la Biblioteca recoge anuncios de todo tipo (no solo infoproductos) y no informa gasto ni resultados; ver §4 |
| `[S]` | Pasos tras "continuar con mi idea" | La herramienta "analiza el mercado y los anuncios de los competidores" y recién después hace las 10 preguntas; en la pregunta 10 la pantalla muestra "investigación de Meta Ads Library" y se pulsa "confirmar respuestas" |
| `[H]` | Términos de búsqueda, país/idioma, umbral de nº de anuncios, antigüedad, qué cuenta como competidor, cómo se detecta el embudo, cuánto tarda | No se explican (más adelante dice que la oferta completa tarda "10-15 minutos") |

### E3 — Entrevista de oferta: las 10 preguntas (9:09–10:45) → D3

Cada pregunta se convierte en una variable de la oferta (la columna "Variable" es **lectura nuestra**; la herramienta no las nombra así). El flujo alterna "continuar" / "confirmar" entre preguntas. Respuestas del ejemplo entre comillas.

| # | Pregunta de la herramienta | Variable que alimenta | Respuesta en el ejemplo |
|---|---|---|---|
| 1 | ¿De dónde sale tu solución con IA? | Credibilidad / mecanismo | "Edito mis videos con IA y lo aplico en mi día a día" (el autor aclara que podría ser que ni lo apliques, "solo lo detectaste": la herramienta acepta un problema sin experiencia propia) |
| 2 | ¿Quién es específicamente la persona que sufre este problema con los editores de video? | Cliente ideal | "Dueños de negocio que venden usando contenido corto en redes" (el autor lo recorta de "corto y largo" a solo corto "para mostrar el ejemplo") |
| 3 | Si alguien compra tu producto, ¿qué resultado chico y concreto va a poder lograr con la edición con IA? | Promesa | "Editar su primer video con IA en 20 minutos" |
| 4 | ¿Cuánto tiempo le va a llevar a esa persona ver ese primer resultado? | Tiempo hasta el resultado | 20 minutos |
| 5 | ¿Qué le impide hoy a esa persona dejar de depender de un editor humano y pasarse a la IA? | Objeción / creencia limitante | "Piensa que la IA es muy complicada de usar" |
| 6 | ¿Qué cosas esa persona no está dispuesta a dejar ni pagar con tal de resolver esto? | Restricción innegociable | "No quiere perder la calidad visual de sus videos actuales" (el autor: "muy bueno ese") |
| 7 | ¿A cuántas personas ya ayudaste a editar sus videos con IA, aunque haya sido de forma informal o gratis? | Prueba / credibilidad | "Edito mis propios videos con IA" (no da número; la respuesta implica 0 personas ayudadas, inferencia nuestra) |
| 8 | ¿Qué tipo de resultado concreto viste en alguien usando IA para editar, aunque haya sido informal? | Prueba | "Mis videos editados con IA con excelente calidad" |
| 9 | ¿Qué podría sumar como extra o bonus para que la oferta sea más completa? | Bonus | "Lista de prompts o comandos listos para usar" |
| 10 | ¿Qué garantía te animás a ofrecer si alguien compra y no logra el resultado? | Reversión de riesgo | "Todavía no me animo a ofrecer garantía" |

`[NUEVO]` Las respuestas 7 y 8 muestran que la "prueba" es **del propio autor (n = 1)**, no de clientes: una oferta con credibilidad frágil que el sistema igual puntúa 85/100. Nuestro D3 debe tratar la prueba como una variable crítica con reglas de honestidad (ver X1).

### E4 — La oferta generada (10:45–13:42) → D3

> Título a vehículo: 10:45 · puntaje y entregables: 11:48 · garantía, urgencia, prueba social y "¿por qué funciona?": 12:47.

| Campo de la oferta | Contenido en el ejemplo |
|---|---|
| Título | "Guía para editar tu primer reel con IA en 20 minutos" |
| Promesa / subtítulo | "Editá y publicá tu primer reel con IA en 20 minutos, sin pasar horas mirando tutoriales larguísimos, aunque hoy sientas que editar con IA es demasiado técnico para vos" (estructura resultado + plazo + sin dolor + "aunque" + objeción: lectura nuestra, el autor no la nombra) |
| ¿Para quiénes? | Emprendedores que graban su propio contenido y pagan/pagaron a un editor humano y están cansados de esperas, precios y plazos incumplidos |
| Cliente ideal recomendado | Quien ya tiene/tuvo un editor al que paga mensualmente y se queja: "el dolor más caliente y reciente" |
| Vehículo recomendado | **Guía PDF de consumo único e inmediato**, sin goteo ni clases. Regla: el bloqueo es "sentir que es técnico", no falta de práctica; se lee en 20 min = el plazo que promete (**coherencia entre tiempo de consumo y tiempo prometido**) |
| Puntaje de la oferta `[M]` | **85/100**. Fortaleza: resultado concreto y rápido + ahorro de dejar de pagar un editor. Límite: garantía condicionada ⇒ menos "compra sin riesgo". Puntúa al menos 6 dimensiones (el autor cierra con "absolutamente todo"; la lista puede no ser exhaustiva): lo que prometés · confianza en el resultado · tiempo hasta ver avances · tranquilidad al comprar · motivos para decidirse · facilidad de aplicarlo |
| Entregables | (1) Guía PDF de 15 páginas paso a paso · (2) Checklist descargable · (3) Set de 15 prompts y plantillas (reels, shorts, testimonios) · (4) Lista curada de herramientas de IA gratuitas/baratas (bonus) · (5) Video comparativo corto (edición hecha con el método; en 17:40 el autor lo describe como un video **dentro del PDF** que compara edición tradicional con un editor vs. con IA). Nota: el bonus que pidió el dueño (Q9, prompts) quedó como entregable (3); el "bonus" explícito es la lista de herramientas (4) |
| Implementación | Elegís un video ya grabado → aplicás el prompt → ajustás lo mínimo → publicás el mismo día |
| Garantía | La herramienta **sugirió una** (el audio no la lee; el puntaje la describe como "con salida real, pero condicionada"), aunque el dueño dijo que no se animaba |
| Urgencia | "Plantillas y prompts exclusivos de este lanzamiento; después de cierta cantidad de ventas dejan de entregarse" |
| Prueba social | "Nosotros mismos editamos nuestros propios videos con IA" |
| ¿Por qué funciona? | Investigación de mercado completa (datos del mercado) |
| `[H]` | **Precio** del producto principal (no se dice en el audio; el order bump muestra un precio en pantalla que tampoco se lee), plazo de la garantía/condiciones, cantidad exacta de ventas de la "urgencia", formato de entrega |

### E5 — Análisis de competencia y de anuncios (12:47–14:45) → D2

| Tipo | Variable | Valor / detalle |
|---|---|---|
| `[S]` | Competidores principales | **4** |
| `[S]` | Campos por competidor | Ganchos de los anuncios · afirmaciones · qué entrega el producto · promesas · prueba social · garantía · mecanismo único · link a la página de compra |
| `[M]` | Anuncios analizados | **11 analizados, 10 con transcripción** (de la Biblioteca de Anuncios) |
| `[S]` | Campos por anuncio/competidor | Qué funciona · huecos de mercado · oportunidades de posicionamiento único · recomendaciones para la oferta · cómo abren los anuncios · ganchos (ej. "Seguís perdiendo horas editando tus videos") · link directo a la Biblioteca por anuncio · promesas repetidas · mecanismos · objeciones que atacan · pruebas y garantías · llamados a la acción · estructura de los videos · links a los videos |
| `[M]` | Señal de fortaleza | Un competidor con **160 anuncios**, otro con **150 "prendidos"** ⇒ "está ganando mucha plata" |
| `[H]` | Antigüedad de los anuncios, variantes, países, gasto, conversiones, rentabilidad real | No se muestran ni se pueden inferir con la Biblioteca (señal débil; ver §4) |

### E6 — Order bump, ángulos de venta y análisis del prospecto (14:45–16:00) → D3, D6

| Tipo | Variable | Valor / detalle |
|---|---|---|
| `[S]` | Order bump elegido | "**100 hooks y guiones virales para tus reels**" con pitch ("ya sabés editar tu reel pero te quedás en blanco en los primeros 3 segundos…"), precio, qué incluye, "por qué ahora" |
| `[S]` | Alternativas de bump | Otras 2 (no se leen); el autor elige una |
| `[M]` | Definición (8:11) | Order bump = adicional ofrecido en el momento de comprar (analogía del postre y la Coca-Cola en el pedido de comida) |
| `[S]` | Ángulos de venta | "Perspectivas únicas desde donde promocionamos"; estructurados por **pirámide de conciencia** |
| `[S]` | Análisis del prospecto | **Qué quiere · qué cree · qué siente · cómo lo dice** (principio: vender con sus mismas palabras) |
| `[H]` | Precio del bump, cantidad de ángulos, upsell posterior a la compra | No se dicen (el video usa "upsell" y "order bump" como sinónimos en 19:51) |

### E7 — Semana 2 · Producto con Claude (16:33–18:24) → D4

| Tipo | Variable | Detalle |
|---|---|---|
| `[E]` | Contexto | Botón "copiar todo" de la oferta (incluye la investigación) pegado en Claude |
| `[E]` | Prompt | "Redáctame un producto digital con estas instrucciones. Dame el producto final con estética profesional." |
| `[S]` | Producto v1 | Título ("Tu primer reel con IA editado en 20 minutos", distinto del título de la oferta), promesa, qué hay adentro ("Leé esto con un video tuyo a mano"), pasos, bonos, algunos prompts, herramientas que necesitás y las que no |
| `[D]` | Revisión humana | "Tenés que leerla entera y asegurarte de que esté muy buena… se puede equivocar" |
| `[S]` | Chequeo promesa ↔ entregable | Le pregunta a Claude si incluye todos los bonos: "casi todo" (PDF 15 págs, checklist, 15 prompts/plantillas, lista de herramientas). **Falta el video comparativo** |
| `[M]` | Tiempo | "5 minutos" (primera versión) |
| `[H]` | Maquetación real del PDF, verificación de hechos, prueba de uso, hosting y entrega segura, actualización cuando cambien las herramientas | No se tratan |

### E8 — Landing y checkout (18:24–20:57) → D5

| Tipo | Variable | Detalle |
|---|---|---|
| `[E]` | Insumos | (1) información del producto = la misma "copiar todo" de la oferta · (2) **dos archivos-prompt** ("dos prompts"/"dos archivos"): uno de **estética** y otro de **estructura** de la página clásica de venta de productos digitales ("andá a Instagram [del autor]; yo te los paso": no se muestran ni se publican) · (3) un video de ejemplo, que el autor aclara **no está editado con IA** ("elegí un video cualquiera para mostrarte cómo se arma la página"; en una página real debería ir uno editado con IA: la demostración del método sería falsa si se deja así, ver X1) |
| `[S]` | Respuesta del constructor | Al recibir los insumos responde "voy a tomar como producto la guía… y usar los materiales adjuntos para construir una página de venta en español" (es la **respuesta** de la herramienta, no una instrucción del autor; el prompt del autor es: pegar la oferta + los dos archivos) |
| `[S]` | Página | Hero con la promesa · video de ejemplo ("así puede quedar tu próximo reel; editalo con CapCut, con Premiere Pro") · botón de acción ("Quiero editar mi primer reel") · bloque "Tu contenido está listo. La edición sigue esperando. De tu clip grabado, un reel listo" |
| `[D]` | Edición | Todo cambio se pide por **chat**; "un par de modificaciones" y queda la página final. Armar la página es "literalmente cuestión de poner un prompt" (17:40) |
| `[S]` | Flujo de compra | Botón de la página → "ver la oferta" → "quiero mi primer video" → checkout (se muestra con la segunda página de ejemplo) |
| `[S]` | Order bump | Aparece **en el checkout** automáticamente porque se entregó la oferta completa al constructor ("para que te arme también el beneficio instantáneo después de la compra") |
| `[S]` | Publicación | Botón **"Publicar cambios"** |
| `[S]` | Medios de pago | Apple Pay · Amazon Pay · Link · tarjeta de crédito · banco · **cuotas en algunos países** · "cualquier tarjeta de crédito/débito del mundo" (19:51). Rentabilidad: el autor afirma que el order bump "hace que tengas muchísima más rentabilidad" tras la venta (sin datos) |
| `[S]` | Segundo ejemplo | Otra página para "Tu primer video ultra realista, listo para publicar en menos de 24 horas" (producto "para clonarse"), **en construcción**, hecha "como ejemplo" |
| `[H]` | Plataforma exacta (el autor dice "Claude", pero la interfaz muestra chat + "Publicar cambios"; no queda claro qué hospeda y cobra), dominio, páginas legales, **tracking (píxel/CAPI/UTMs)**, velocidad móvil, entrega post-compra, emails, **precio**, A/B | No se tratan |
| Inferencia | Apple Pay + Amazon Pay + Link + débito bancario son métodos típicos de Stripe Checkout | `[VERIFICAR]` |

### E9 — Semanas 3-4 · Tráfico: orgánico o anuncios (20:57–23:19) → D6, D7

| Tipo | Variable | Detalle |
|---|---|---|
| `[D]` | Camino de tráfico | **(1) Orgánico**: contenido propio para vender tu producto, o ayudar a un creador a montar el suyo y quedarte con **comisión** ("lo pagás con tiempo") · **(2) Anuncios**: la gente llega "hoy" a la página |
| `[E]` | Prompt de guiones | "Armame 10 guiones para anuncios en base a mi oferta e investigación del mercado" (en el mismo chat de Claude donde se hizo el producto, tras volver a Venzio a "copiar todo") |
| `[S]` | Guiones | Basados en: ángulos de venta + investigación + guiones/estructura de anuncios de la competencia |
| `[D]` | Formato del anuncio | **Estático** (se genera en Claude) o **video** (te grabás / contratás a alguien / **Higgsfield**, "la mejor herramienta para generar anuncios con IA"; añade que "muchos anuncios que hoy te aparecen, probablemente ni te diste cuenta, son hechos con IA": nada dice de divulgar el uso de IA, ver X1) |
| `[S]` | Creativos mostrados | Un ejemplo de anuncio estático y uno de video hecho con Higgsfield (se muestran, sin métricas); "ambos los usamos para llevar tráfico" (afirmación del autor) |
| `[S]` | Campaña | "Podés conectar tu administrador de anuncios de Meta con Claude para que te monte las campañas" (se dice en el cierre, bloque 23:19; **no se muestra**) |
| `[M]` | Cantidad de guiones | 10 (ejemplo) |
| `[H]` | **Presupuesto diario/total**, duración, objetivo de campaña, estructura (campañas/conjuntos/anuncios), audiencias, ubicaciones, píxel y eventos, métricas objetivo (CPA, ROAS, CTR, conversión), criterios de pausa/continuar | **Nada de esto se dice.** Un comentario lo pregunta ("¿cuánta plata por día tendríamos que poner en publicidad en Meta para que lleguen clientes buenos?"): tiene 3 respuestas cuyo contenido no se capturó |

### E10 — Día 30: test, decisión y cronograma (22:05–24:53) → D8, D9, O0

| Tipo | Variable | Detalle |
|---|---|---|
| `[M]` | Objetivo del día 30 | "La rueda girando": problema validado · producto terminado · tienda cobrando · tráfico entrando. Primeras ventas = evidencia |
| `[D]` | Regla de decisión (22:05) | **Si va bien, escalar; si no, armar otra oferta/producto y seguir testeando** (sin umbrales) |
| `[M]` | Cronograma | Días 1-7 problema + validación · días 8-14 producto + página · semanas 3-4 (días 15-30) tráfico y primeras ventas. La transcripción dice literalmente "semana 2 a 4": el glosario lo corrige a "3 y 4", coherente con "ya te podés poner a vender en dos semanas" `[SUPUESTO]`. Con el proceso aceitado: oferta en 1 día, producto en 1 día, "varios productos por día". Tras definir el objetivo: "de ahí en adelante todo es volumen y ajuste". Total: "una sola persona, una computadora y 30 días"; el autor se contradice entre "dos semanas" y "30 días" |
| `[M]` | Velocidades citadas | Investigación + oferta: 10-15 min · producto v1: 5 min |
| `[H]` | Qué es "va bien" (nº de ventas, CPA, ROAS, plazo), cómo se escala, cómo se renuevan creativos, qué se hace con ofertas "grises" | **Sin definición.** El autor lo deriva a su entrenamiento ("la cuenta real de cuántas ventas necesitás para hacer 3.000/mes") |

---

## 3. Puntos donde interviene el humano en el video (candidatos a automatizar o a gate)

| # | Intervención | Etapa | Nuestra propuesta |
|---|---|---|---|
| 1 | Elegir el problema entre infinitas fuentes | E1 | D1 (radar continuo + banco de problemas, backbone v2.1/§3.2) propone los mejores; el dueño elige en **gate H** (decisión de mayor palanca) |
| 2 | Redactar el problema en texto libre | E2 | D1 lo estructura (mercado, persona, dolor, evidencia) |
| 3 | Elegir punto de partida / cuentas de referencia / ángulos / bumps | E2 | Parámetros del brief |
| 4 | Responder 10 preguntas con la verdad del dueño | E3 | D3 con modo "dueño" y modo "inferido con supuestos marcados" |
| 5 | Confirmar respuestas | E3 | Gate de D3 |
| 6 | Elegir 1 de 3 order bumps | E6 | D3 decide con reglas + QA; dueño aprueba |
| 7 | Leer y editar el producto entero | E7 | D4 + QA con prueba en frío; dueño con checklist de 10 min |
| 8 | Pegar prompts, pedir cambios a la página, subir video | E8 | D5 automatizable (código + QA con navegador) |
| 9 | Publicar | E8 | Gate según `contratos/gates.json` (`accion:publicar_landing`) |
| 10 | Elegir orgánico vs anuncios; estático vs video | E9 | Parámetro del brief + D6 |
| 11 | Montar la campaña | E9 | D7 con preflight y activación en **gate H** |
| 12 | Decidir escalar o matar | E10 | D8/D9 con **reglas deterministas** y topes |

## 4. Registro de números y afirmaciones del video

| Afirmación | Min. | Evidencia mostrada | Nuestra postura |
|---|---|---|---|
| "8 de cada 10 negocios en EE. UU. son de una sola persona (>30 M) y la mayoría logra rentabilidad" | 0:00 | Ninguna | Los negocios sin empleados son una gran mayoría de las empresas de EE. UU. `[VERIFICAR]`, pero la mayoría factura poco: no prueba que *este* modelo funcione |
| "La mayoría de las apps hechas con IA no factura ni 100 USD" | 0:29 | Ninguna | No relevante para nuestro modelo; no verificado |
| "Más de 9,5 M USD generados con productos y servicios digitales, más de 5 años vendiendo, tiendas gestionadas por su equipo" (audio 4:46); "equipo de más de 30 personas" (1:14); "audiencia de más de 500.000" y "más de 9 millones" (**solo en la descripción**, no en el audio) | 1:14 / 4:46 / descripción | Capturas de resultados de tiendas en pantalla | No verificable; el propio autor aclara que lo suyo no implica que a vos te funcione |
| "Una web así costaba mínimo 1.000 USD hace 5 años" | 4:01 | Ninguna | Plausible; irrelevante para decidir |
| "Venzio resuelve el 80 % del trabajo" | 7:05 | Demo propia | Afirmación comercial sobre producto propio |
| "Muchos anuncios ⇒ gana mucha plata" (160 y 150) | 13:42 | Cuenta de anuncios por anunciante | **Señal débil**: la Biblioteca no muestra gasto ni conversiones; un anunciante puede correr cientos de anuncios y perder plata o estar testeando. Exigir longevidad, consistencia y varios anunciantes |
| "Puntaje 85/100" | 11:48 | Salida de la herramienta | Rúbrica no calibrada; no incluye precio ni prueba real; riesgo de autocomplacencia |
| "Producto hecho en 5 minutos" | 17:40 | Primera versión | El propio autor pide leerlo entero y corregirlo; el costo real está en la revisión y la prueba |
| "Oferta en 10-15 min; varios productos por día" | 23:19 | Ninguna | Aspiracional: el cuello de botella real es el **aprendizaje en anuncios** (días/semanas), no la producción |
| "Día 30: primeras ventas" | 23:19 | Ninguna | Sin presupuesto, nicho ni estructura declarados, no es una promesa verificable |
| "3.000 por mes en ganancia" como meta (moneda no dicha) | 2:26 (cifra ininteligible) / 24:53 | El cálculo está en otro video | Lo calcularemos nosotros en F1 (calculadora de ventas necesarias) |
| "Cualquier tarjeta de crédito/débito del mundo" | 19:51 | Lista de métodos | Depende de procesador, país y moneda `[VERIFICAR]` |
| Urgencia: "después de cierta cantidad de ventas dejan de entregarse" | 12:47 | Sugerencia de la herramienta | Solo aceptable si es **real**; si es inventada es urgencia falsa (riesgo con Meta y con consumidor). Ver X1 |
| Prueba social: "nosotros mismos editamos con IA" | 12:47 | — | Es credibilidad del operador, no prueba social de clientes. Ver D3/D10/X1 |
| "El 99 % se pierde meses investigando a mano" | 6:56 | Ninguna | Dato inventado o aspiracional; sirve para vender Venzio |
| "Armar el producto, la web y el cobro en una tarde" (descripción) frente a "dos semanas" / "30 días" (23:19) | descripción / 23:19 | Ninguna | Promesa de la descripción inconsistente con el propio plan |
| Order bump ⇒ "muchísima más rentabilidad"; "100 hooks y guiones probados" | 19:51 / 14:45 | Ninguna | Sin datos; "probados" es un claim de la herramienta que nadie validó |
| Higgsfield "la mejor herramienta para generar anuncios con IA"; anuncios con IA indistinguibles | 22:05 | Dos ejemplos sin métricas | Afirmación comercial; riesgo de transparencia sobre contenido sintético (X1) |

## 5. Huecos: lo que el video NO dice y hace falta para un sistema autónomo

**Estrategia y mercado**
1. País/idioma/moneda objetivo y poder adquisitivo; medios de pago locales. → M1, D0, D3
2. Cómo puntuar y diversificar candidatos; saturación; vida útil (los how-to de IA envejecen en semanas). → D1, D2, D4
3. Diferenciación real: si todos usan las mismas fuentes y la misma herramienta, todos llegan a la misma oferta. → D2, D3

**Economía**
4. **Precio** del producto principal, del bump y del upsell; pruebas de precio. → D3
5. **Economía unitaria**: comisiones del procesador, reembolsos, impuestos, costo de herramientas, CPA máximo tolerable, break-even de ROAS. → D3, F1
6. **Presupuesto de test** (diario/total/duración) y cómo se calcula. → D7, F1
7. Qué es una "oferta validada": nº de ventas, CPA, ROAS, ventana, estabilidad. → D8
8. LTV/backend: email, upsells, productos adyacentes (un PDF de ticket bajo rara vez cierra solo la cuenta con tráfico frío). → D9, D10

**Ejecución de campañas**
9. Estructura de campaña (objetivo, tipos, audiencias, ubicaciones, evento de optimización, atribución). → D7
10. Medición: píxel + API de Conversiones, UTMs, unión de pedidos de Stripe con anuncios. → D0, D5, F2
11. Reglas de pausa, escala y renovación de creativos; fatiga. → D8, D9
12. Volumen de creativos por test y cadencia de refresco. → D6

**Producto y experiencia**
13. Calidad real del producto: revisión, verificación de hechos, **prueba de uso en frío**. → D4
14. Hosting seguro y entrega automática; soporte; reembolsos; disputas. → D5, D10
15. Prueba social real y cómo conseguirla sin testimonios. → D3, D10
16. Garantía: política concreta y su efecto en reembolsos. → D3, D10

**Cumplimiento y riesgo**
17. Políticas de Meta para infoproductos / "ganar dinero" / contenido de IA / páginas de destino. → X1
18. Protección al consumidor (derecho de arrepentimiento, reembolsos), privacidad, testimonios, urgencia/escasez real. → X1
19. Riesgo de cuenta publicitaria y de Stripe (bloqueos, disputas); cuentas de respaldo. → D0, X1
20. Impuestos sobre bienes digitales y elegibilidad de Stripe por país/entidad. → D0, F1, X1
21. Marcas de terceros en anuncios/productos (CapCut, Premiere…), copia de competidores. → X1

**Operación del sistema**
22. Qué plataforma exacta hospeda la página y cobra; cómo se versiona y se revierte. → D5
23. Dependencia de Venzio: acceso restringido, precio no público, los comentarios dicen que muchos no pueden entrar. → D1, D2, D3 (reemplazo propio)
24. Memoria: qué se aprende de cada oferta y cómo vuelve al sistema. → X2
25. Finanzas por oferta y consolidadas; alertas; asignación de capital. → F1
26. Observabilidad: costos de IA por oferta, errores, auditoría de acciones de agentes. → O0, F2
27. Qué credenciales y permisos necesita cada paso (mínimo privilegio) y qué funciona en ejecución desatendida. → O0, D0

## 6. Lectura crítica: qué conservar y qué cambiar

**Conservar (es lo valioso del video)**
- Elegir problemas con demanda ya pagada; validar mirando qué anuncia la competencia.
- Entrevista que fuerza especificidad: resultado **chico y concreto**, plazo, objeción y restricción innegociable.
- Coherencia formato-tiempo (el PDF se lee en el plazo que promete).
- Order bump desde el inicio; ángulos por nivel de conciencia; análisis del prospecto con **sus propias palabras**.
- Un producto barato de producir y creativos derivados de la investigación.
- Objetivo realista del día 30: sistema funcionando, no facturación.

**Cambiar o agregar (`[NUEVO]`)**
- No depender de Venzio: D1-D3 replican su función con conectores propios.
- Validar con más señales que "cantidad de anuncios" y tratar el resultado como hipótesis hasta que hable el test pagado.
- Economía unitaria **antes** de construir (compuerta de factibilidad en D3).
- Producto con revisión real y prueba en frío; trazabilidad promesa ↔ entregable.
- Landing automatizable y testeable (código + navegador), con tracking desde el día uno.
- Campaña en PAUSA → preflight → activación con gate; reglas de kill/escala en **código**, no en criterio del modelo.
- Cumplimiento como departamento con **veto** (urgencia real, prueba real, claims sustanciables).
- Memoria y evolución controlada de skills.
- El ejemplo del video (edición de video con IA) es un nicho **saturado, en rápida obsolescencia y vecino al territorio de "ganar dinero con IA"**: no lo tomamos como modelo de nicho, solo de proceso.

## 7. Mapa video → departamentos del sistema

| Etapa del video | Departamento(s) | Maker | QA | Qué agregamos |
|---|---|---|---|---|
| E0 vehículo de negocio | O0 | Orquestador/Portafolio | Auditor de brief | Brief con mercado, presupuesto, riesgo y nivel de autonomía |
| E1 elegir problema | D1 (+ M1) | Analista de descubrimiento | Revisor de evidencia | Radar continuo por nichos e idiomas con banco de problemas, filtro "mecanismo único + entregable único" (§5.11) y encuadre en SALUD/RELACIONES/DINERO (decisión 13) |
| E0 + E2 (mercado/país/idioma, que el video no trata) | M1 | Maker de mercados | QA de M1 (MQ-01…MQ-17) | Selección de mercado e idioma por oferta con datos propios (pagos de Stripe, brecha y competencia); Polonia o Italia son hipótesis, no premisas |
| E2 investigación/validación | D2 | Analista de inteligencia competitiva | Auditor de validación | Señales más robustas que "nº de anuncios", veredicto GO/REFINAR/NO-GO |
| E3-E6 oferta | D3 | Arquitecto de oferta | Crítico de oferta | Economía unitaria previa, honestidad de prueba/urgencia, precio |
| E7 producto | D4 | Fábrica de producto | Auditor de producto | Trazabilidad, prueba en frío, política de actualización |
| E8 landing/checkout | D5 | Ingeniero de conversión | QA con navegador y compra de prueba | Tracking, legales, entrega, rollback |
| E9 guiones/creativos | D6 | Estratega creativo | Revisor creativo + políticas | Matriz ángulo×hook×formato, ciclo de iteración |
| E9 campaña | D7 | Media buyer | Auditor de preflight | Presupuesto desde economía unitaria, PAUSA→gate→activar |
| E10 test y decisión | D8, D9 | Analista/optimizador; escalador | Auditor de decisiones | Reglas deterministas, fatiga, refresco, escalado con topes |
| (no está) cobro y entrega | D10 | Post-compra | Auditor de experiencia | Entrega, soporte, reembolsos, prueba social ética |
| (no está) empresa | F1, F2 | CFO; BI | Conciliación; QA de datos | P&L por oferta y blended; dashboard |
| (no está) riesgo | X1 | Compliance | — (veto) | Preflight de anuncios y landing, salud de cuentas |
| (no está) aprendizaje | X2 | Memoria | — | Post-mortems → skills |
| (no está) infraestructura | D0 | Infra | Auditor de conexiones | "Todo previamente conectado", healthchecks |

> **Contexto de creadores:** este video es una sola fuente (un vendedor de curso y herramienta propia, con embudo comercial); el método se contrasta con otros creadores en `_investigacion/09`–`15` ([CREADORES], confianza A/B/C) y sus cifras son declaraciones de vendedores, hipótesis y no hechos. Donde el video calla (mercado, precio, presupuesto, umbrales), mandan `_backbone.md` y los contratos, no el video.

## 8. Señales de los comentarios (14 visibles)

- De los 13 comentarios capturados (la fuente declara 14 visibles; uno no se registró), 7 preguntan cómo **acceder a Venzio** o dicen que no pueden entrar/registrarse (uno pidió acceso por Instagram sin respuesta); 2 preguntan el **precio** (ambos del mismo usuario, @armandogomez4806); 1 pregunta si Venzio "es tu IA"; 1 elogia; 1 es el fijado del autor; 1 pregunta por el presupuesto en Meta. → Confirma que conviene no depender de ella.
- Una pregunta clave sin respuesta visible: **cuánto invertir por día en Meta** para que lleguen buenos clientes. → Es exactamente el hueco que D3/D7/F1 deben cerrar con economía unitaria.
- El comentario fijado del autor lleva a una **llamada de consultoría**: el video es un canal de captación (también: los dos prompts de la landing se entregan por Instagram del autor, E8; y el cierre remite a un entrenamiento gratuito, 24:53).
