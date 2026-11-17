# Taxonomía de funnels

Para qué sirve: decir de qué está hecho un funnel antes de puntuarlo o desarmarlo, con las mismas palabras cada vez, y que la lista de tipos crezca sola cuando aparece algo que no conocíamos. La pidió el dueño el 2026-11-11: «planteamos funnels de quiz, TSL, VSL y diversos otros que capaz no estoy contemplando… estoy seguro que existen quiz más VSL y otros tipos, que son como mutaciones… cuando encuentres algo distinto, ya sea encuadrarlo dentro de uno de los que tenemos o crear y decir: este funnel es quiz más TSL, o quiz más VSL, u otro tipo que no estemos contemplando».

Los datos (componentes, señales, pesos, tipos y ejemplos) viven en `scripts/taxonomia_funnels.json`. Este documento los explica; si los dos difieren, manda el JSON, que es lo que leen los scripts.

Vocabulario: **TSL** = carta de ventas en texto. **VSL** = carta de ventas en video (el dueño a veces dice «BSL»). **Bump** = complemento que se marca dentro del checkout. **Upsell** = oferta que aparece después de pagar.

## 1. La idea en cuatro líneas

1. Un funnel es una **secuencia ordenada de componentes de núcleo** (lo que el comprador atraviesa antes de pagar) más **extras** (lo que hay alrededor del pago).
2. El **tipo** se llama como su núcleo unido con «+», en el orden en que ocurre: `quiz+vsl`, `advertorial+tsl`. `vsl+quiz` sería otro tipo.
3. La **complejidad** sale de los componentes, no del nombre.
4. Lo que no se pudo ver se anota como **no observado**. No se supone.

## 2. Componentes de núcleo (definen el tipo)

| Componente | Qué es | Señales al abrir la página | No confundir con | Peso |
|---|---|---|---|---|
| `advertorial` | Página puente con forma de artículo, noticia o historia. No cobra: manda a la venta | Titular, autor y fecha; a veces la palabra «publicidad»; sin precio; el botón lleva a otra página | Una TSL con tono de historia (si cobra en la misma página, es `tsl`) | 0.60 |
| `quiz` | Preguntas paso a paso con resultado o «plan» al final | Una pregunta por pantalla, barra de progreso, «analizando tus respuestas»; rutas `/quiz`, `/test`, `/start`, `/survey`; constructores (`inlead.digital`, Typeform, Heyflow…) | Un formulario de contacto o un selector de producto | 0.80 |
| `registro` | Pide correo, nombre o teléfono antes de mostrar precio o resultado | Campo de correo obligatorio en una página que todavía no cobra | El correo que pide el checkout; un boletín en el pie | 0.30 |
| `vsl` | Un video largo es la página | Casi sin texto; reproductor (vturb/converteai, Vidalytics, Wistia, Panda…); el botón aparece pasado un rato | Un video corto dentro de una página larga (eso es el extra `video-apoyo`) | 0.80 |
| `tsl` | Página de venta en texto, por secciones, con precio y botón a la vista | Promesa, qué incluye, bonus, garantía, preguntas frecuentes; enlace de pago | Una página que no cobra (es `advertorial`) | 0.25 |
| `webinar` | La venta ocurre dentro de una clase a la que hay que apuntarse | «Reserva tu lugar», fecha y hora, sala con chat | Casi siempre vende un curso con acompañamiento: fuera del recorrido | 0.80 |
| `chat` | El botón abre WhatsApp o Messenger y ahí se cierra | Salida principal a `wa.me` o `m.me`, sin checkout | El botón flotante de soporte | 0.30 |

## 3. Extras (no cambian el nombre; solo algunos suman complejidad)

Regla del dueño (17-nov): **bump, upsell, downsell y subida previa no agregan complejidad**, porque los tienen todos; se anotan igual porque se modelan. El **escalonado de precios** (`niveles`, como Oferta F) sí suma.

| Extra | Qué es | Dónde se ve | Suma |
|---|---|---|---|
| `video-apoyo` | Video corto dentro de una TSL | Arriba de la página, con precio y botón visibles desde el inicio | 0.25 |
| `bump` | Complemento dentro del checkout | Casilla «Sí, quiero añadir…» en el checkout. Muchos checkouts lo pintan con JavaScript: si no se ve, es «no observado» | 0 |
| `upsell` | Oferta tras pagar | Casi nunca se ve sin comprar; a veces hay una ruta `/upsell` o `/oto` enlazada | 0 |
| `downsell` | Rebaja al rechazar o al intentar salir | Ventana de salida, ruta `/downsell` | 0 |
| `niveles` | Dos o más paquetes con precio distinto | Tarjetas de precio lado a lado, dos enlaces de pago distintos | 0.35 |
| `paginas-por-publico` | La misma oferta con varias landings por público o idioma | Los anuncios apuntan a rutas `/es/`, `/de/`, `/padres`… | 0.10 |
| `subida-previa` | Oferta del paquete caro con descuento, en una ventana, al elegir el barato y antes de pagar | Tocar el botón del paquete barato; o en el `.js`: un tercer enlace de pago y una función que abre una ventana en ese clic. A veces también por intención de salida | 0 |
| `ruleta` | Juego que «regala» el descuento | Ruleta o raspadita antes del precio (si siempre cae en lo mismo, es un descuento inventado: `00-reglas-del-dueno.md` §2) | 0.10 |

Un extra que no esté en la lista suma 0.10 y conviene añadirlo al JSON con sus señales.

## 4. Regla de complejidad

```
complejidad = min(1,  1 − Π(1 − peso de cada componente de núcleo)  +  Σ peso de cada extra)
```

Cada componente de núcleo aporta su peso sobre lo que falta para llegar a 1. Consecuencias:

- Un híbrido vale siempre más que cualquiera de sus partes: `quiz` 0.80, `vsl` 0.80, `quiz+vsl` 0.96; `tsl` 0.25, `quiz+tsl` 0.85; `advertorial+vsl` 0.92; `advertorial+tsl` 0.70 (complejo); `tsl` + `niveles` 0.60 (justo en el umbral: «relativamente compleja», como Oferta F); `advertorial+tsl` + `niveles` y `vsl` + `niveles` 1.0 (tope); `tsl` con bump, upsell y downsell sigue en 0.25.
- Los valores anteriores a la taxonomía no cambian: `quiz` 0.80, `vsl` 0.80, `tsl-basica` 0.25, `tsl-video` 0.50 (`tsl` + `video-apoyo`). Desde el 17-nov: advertorial pesa 0.60 (antes 0.40), niveles 0.35 (antes 0.10) y bump, upsell, downsell y subida previa 0 (antes 0.10).
- A partir de 0.60 el funnel cuenta como **complejo** (`UMBRAL_COMPLEJO` en `ordenar_candidatos.py`).

Los pesos son lectura del asistente de lo que pidió el dueño, igual que los del puntaje. Se cambian en el JSON.

## 5. Regla de encuadre

Para cada funnel observado:

1. Anotar el núcleo en orden y los extras, con la evidencia de cada uno.
2. **Si el núcleo coincide en componentes y orden con un tipo que existe, es ese tipo.** Los extras no cambian el tipo.
3. **Si no coincide, se crea un tipo nuevo** con nombre compuesto (`a+b`), se guarda el ejemplo que lo originó (página, URL, fecha) y queda en estado `nuevo-a-confirmar`. En el informe se dice así: «tipo nuevo: quiz + carta de ventas en video, visto en tal página».
4. **Nunca se fuerza** un funnel distinto dentro de un tipo existente por parecido. Si falta un componente para describirlo, se añade el componente al JSON con sus señales.
5. Si no se observó ningún componente de núcleo, queda `sin-clasificar` y se abre en el navegador.

Estados de un tipo: `base` (existía antes de la taxonomía), `previsto` (nombrado por el dueño, sin ejemplo real todavía), `nuevo-a-confirmar` (tiene su primer ejemplo real y espera que el dueño lo vea), `confirmado` (el dueño lo dio por bueno; se cambia a mano en el JSON).

Se hace con el script, que es quien escribe en el JSON:

```
B=.claude/skills/modelar-y-lanzar-oferta/scripts/barrido_por_forma.py
python3 $B encuadrar --componentes quiz,vsl --extras bump --pagina "Nombre" --url https://… --nota "qué se vio" --registrar
```

Sin `--registrar` solo responde (tipo, si es nuevo, complejidad) y no toca nada.

## 6. Tipos conocidos (al 2026-11-11)

| Tipo | Núcleo | Estado | Ejemplo real |
|---|---|---|---|
| `tsl` | Carta de ventas en texto | base | Teen Referente B (con `niveles`); ReferenteA (con `video-apoyo`) |
| `vsl` | Carta de ventas en video | base | Elias Lelles · Protocolo P4 (visto a mano: video de 36:36 con la compra oculta; `bump` leído en el checkout) |
| `quiz` | Quiz → oferta breve o checkout | base | Muses Academy (quiz que personaliza una suscripción) |
| `advertorial+tsl` | Página puente → carta en texto | base | sin ejemplo todavía (es el antiguo `varios-pasos`) |
| `quiz+vsl` | Quiz → carta en video | nuevo, a confirmar | **Mapa Relacional** (verificado a mano de punta a punta); Referente |
| `quiz+tsl` | Quiz → carta en texto | nuevo, a confirmar | André Vogt · Hundetrainer (el quiz se vio a mano; la carta de ventas solo en el HTML servido) |
| `advertorial+quiz` | Artículo → quiz | nuevo, a confirmar | Referente (clasificación automática; no pasa el piso) |
| `registro` | Página que pide el correo; lo que sigue no se ve | nuevo, a confirmar | Referente (clasificación automática; no pasa el piso) |
| `advertorial+vsl` | Artículo → carta en video | previsto | sin ejemplo todavía |

Nombres anteriores que siguen valiendo (clave `alias` del JSON): `tsl-basica` = `tsl`; `tsl-video` = `tsl` con `video-apoyo`; `varios-pasos` = `advertorial+tsl` con piso de complejidad 0.80. `ofertas/historial-modelado.json` los usa y no hay que reescribirlo.

**Variación.** Para la penalización por repetir tipo se compara el tipo canónico (el núcleo en orden). Por eso `tsl-video` y `tsl-basica` cuentan como el mismo tipo: con las dos primeras ofertas lanzadas, una tercera TSL sale multiplicada por 0.70. `quiz+vsl` solo repite a otro `quiz+vsl`; no se penaliza por compartir un componente.

## 7. Clasificador automático: qué hace y dónde se queda corto

```
python3 $B clasificar https://destino-del-anuncio/…
```

Descarga el destino (solo lectura, sin cookies, respetando `robots.txt`, una petición cada 2.5 s), busca las señales de cada componente, sigue el botón principal hasta el checkout sin enviar ningún formulario y devuelve tipo, evidencia por componente, lo no observado y una confianza.

Lo que se vio al probarlo con 26 destinos reales (2026-11-11):

| Caso | Qué hace | Qué hay que hacer |
|---|---|---|
| Página de texto servida entera (TSL, VSL con su reproductor en el HTML) | La clasifica bien; llega al checkout y ve el bump si está en el HTML | Confianza media o alta: revisar la evidencia |
| Quiz dibujado con JavaScript (casi todos: `inlead.digital`, plataformas propias) | Reconoce que es un quiz por la ruta o el constructor, pero no ve preguntas ni lo que viene después | Confianza baja: recorrerlo en el navegador. Ahí es donde aparecen los híbridos (`quiz+vsl`) |
| Página con quiz y texto de venta juntos | Detecta los dos, pero el orden dentro de la misma página no es fiable | Mirar la página y encuadrar a mano |
| `robots.txt` lo prohíbe o hay página antibot | Se detiene con ese destino y lo dice | Abrirlo a mano; no se evade |
| El primer clic del quiz dice «al continuar aceptas los términos» | — | No se sigue: se anota hasta dónde se vio |
| Suscripción | Marca «suscripción probable» si lo dice el texto leído; muchas veces solo aparece en la política o en el checkout | Buscar el enlace «política de suscripción» en el pie |

Un tipo nuevo solo se registra solo (`clasificar --registrar`) si la confianza no es baja. Lo visto a mano se registra con `encuadrar`.

## 8. Cómo crece

- Aparece un funnel con un núcleo que no existe → `encuadrar --registrar` lo crea y lo deja «a confirmar». El informe de la corrida lo lista en «tipos nuevos».
- Aparece una pieza que ningún componente describe (por ejemplo una calculadora, o un diagnóstico por chat con IA) → añadir el componente al JSON (`clase`, `peso`, `senales`), y entonces encuadrar.
- El dueño ve el tipo y lo da por bueno → cambiar su `estado` a `confirmado`. Si dice que en realidad es otro, se corrige el tipo y se deja nota en el `CHANGELOG.md`.
- Una señal da falsos positivos → se corrige en el JSON, no en el código.
