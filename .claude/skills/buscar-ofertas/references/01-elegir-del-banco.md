# Elegir la oferta del banco

Movido aquí el 2026-11-13 desde `modelar-y-lanzar-oferta/references/01-elegir-oferta-y-mercado.md` (división de skills pedida por el dueño). Los scripts siguen en `.claude/skills/modelar-y-lanzar-oferta/scripts/` (caja de herramientas compartida): las rutas de abajo son relativas a esa carpeta.

## Elegir la oferta

### 1.1 De dónde salen los candidatos

Desde el 2026-11-13 el banco lo llena sobre todo el **radar** (`05-radar.md`, tarea «radar-ofertas» cada 4 horas: `radar.py exportar` + `banco_candidatos.py importar`). Los barridos quedan como complemento. Fuentes anteriores al radar, todavía útiles:

- `empresa/barrido/candidatos/<corrida>.json`: páginas anunciantes agrupadas por tema. Por página: `page_id`, `page_name`, `tema_slug`, `pais_fuente`, `anuncios_activos_medidos`, `edad_oferta_dias`, `conceptos_unicos`, `estado_traccion`, `exportador` (`moneda` de la cuenta distinta a la del país = operador que exporta ofertas), `por_verificar`.
- El panel («Radar de ofertas») muestra lo mismo y, si alguien la registró, la landing original (`python -m scripts.referentes.landing`; el barrido no guarda la URL de destino).
- Puntaje de modelado (par oferta × mercado): `scripts/modelado/puntaje_modelar.py` y su README.

**Cuándo se barre y cuándo no (regla del 2026-11-12).** Buscar y elegir son dos cosas separadas. Los barridos llenan el banco de candidatos (`empresa/barrido/banco/`); al pedir una oferta nueva no se barre: se corre `python3 .claude/skills/modelar-y-lanzar-oferta/scripts/banco_candidatos.py estado`. Si responde «ALCANZA», se vuelven a medir ese día los candidatos listos y se elige. Si responde «HAY QUE BARRER» (menos de 3 candidatos complejos, verificados y producibles, o último barrido de hace más de 7 días), primero se verifica lo que el radar tiene en `a_verificar` (`radar.py pendientes`) y se exporta; si aun así no alcanza, un barrido de reposición por forma de funnel (§1.5) con términos que no se hayan usado, se importa y se vuelve a preguntar. Detalle en §1.6.

El barrido por tema de `scripts/modelado/barrido/` (el del 6 de noviembre) es de otra sesión y tiene frenos propios (`empresa/captura/freno.json`): no se relanza desde esta skill.

### 1.2 Qué se mira

**Piso.** Umbral de tracción del dueño: al menos 15 anuncios activos y 10 días de antigüedad de la oferta (la antigüedad es la del segundo anuncio activo más viejo). Por debajo de eso no se modela.

**Por encima del piso: un puntaje con tres señales, y variar.** Regla del dueño (2026-11-11, en dos mensajes): apuntar a funnels complejos y con muchos anuncios encendidos («más de 50, 60, 100 inclusive»), pero sin un orden fijo de tipos, porque «siempre habrá un quiz para encontrar, entonces siempre haremos quiz»; quiere «una relación entre los mejores y más complejos, pero ir variando», con «algo de peso también en los anuncios encendidos y la antigüedad sobre todo», para «ir probando distintas cosas».

Se calcula con `scripts/ordenar_candidatos.py`, que deja los números a la vista y decide igual cada vez:

| Señal | Peso | Cómo se mide |
|---|---|---|
| Complejidad del funnel | 40 % | Sale de los componentes del funnel según `taxonomia-funnels.md` §4, no de un valor fijo por nombre. Quiz y VSL solos valen lo mismo (0.80); un híbrido vale más que sus partes (`quiz+vsl` 0.96, `quiz+tsl` 0.85); TSL con video de apoyo 0.50, TSL básica 0.25. Advertorial + TSL 0.70 (cuenta como complejo). Regla del dueño (17-nov): bump, upsell y downsell **no suman** (los tienen todos); el escalonado de precios (niveles) suma 0.35, así TSL + niveles queda justo en complejo (0.60), debajo de advertorial + TSL (0.70) y de quiz o VSL (0.80); páginas por público 0.10; tope 1.0 |
| Antigüedad | 35 % | De 0 en 10 días a 1 en 90 días o más, en escala logarítmica |
| Anuncios encendidos | 25 % | De 0 en 15 anuncios a 1 en 100 o más, en escala logarítmica |

Variación, contra `ofertas/historial-modelado.json` (una línea por oferta lanzada):
- Mismo tipo de funnel que la última oferta lanzada: el puntaje se multiplica por 0.85. «Mismo tipo» es el mismo núcleo en el mismo orden (`tsl-video` y `tsl-basica` son los dos `tsl`; `quiz+vsl` solo repite a otro `quiz+vsl`).
- Mismo tipo que las dos últimas: por 0.70.
- Mismo tema que alguna de las tres últimas: por 0.90.

Así una oferta excelente del mismo tipo todavía puede ganar, pero a igualdad se prueba algo distinto. Si los dos primeros quedan a menos de 0.05, es empate técnico y se presentan los dos al dueño.

Los pesos y factores son mi lectura de su regla, no cifras que él haya dado; están en un solo bloque al principio del script. Si al ver un orden dice «esto no es lo que quiero», se ajustan ahí y se anota en el `CHANGELOG.md`.

Cómo reconocer cada tipo al abrir la landing: con `taxonomia-funnels.md`, que lista los componentes (quiz, carta en texto, carta en video, página puente, registro previo y los extras del checkout), las señales que delatan a cada uno y los tipos conocidos. El campo `funnel` de cada candidato es un tipo de esa taxonomía: un componente (`quiz`, `tsl`, `vsl`) o varios en orden unidos con «+» (`quiz+vsl`). Si lo que se ve no coincide con ningún tipo, no se fuerza: se crea el tipo con `barrido_por_forma.py encuadrar --registrar` y se le dice al dueño como «tipo nuevo, a confirmar». Los nombres `tsl-video`, `tsl-basica` y `varios-pasos` siguen funcionando.

**Cómo se aplica, dado que el barrido no guarda el tipo de funnel** (solo página, país, anuncios, antigüedad y título):

1. Del archivo de candidatos, quedarse con los que pasan el piso. Tomar unos 15: los de más anuncios y los más antiguos, para que la antigüedad no quede fuera por ordenar solo por cantidad.
2. Encontrar la landing de cada uno (registro de `scripts.referentes.landing`, o siguiendo el botón de una ficha) y abrirla en el navegador.
3. Clasificar el funnel con `barrido_por_forma.py clasificar <URL>` y, si la confianza no es alta (casi siempre en un quiz), recorrerlo en el navegador. Anotar núcleo, extras, número de pasos, preguntas del quiz, duración del video y lo no observado.
4. Escribir `modelado/candidatos.json` (formato en la cabecera del script) con `anuncios` y `dias` medidos ese día (§1.3) y correr `python3 .claude/skills/modelar-y-lanzar-oferta/scripts/ordenar_candidatos.py ofertas/_borrador-<slug>/modelado/candidatos.json`.
5. Presentar la tabla que imprime y recomendar la primera que se pueda producir. Si la primera es una TSL, decirlo así: no había un funnel complejo con tracción suficiente.
6. Al lanzar la oferta, añadir su línea a `ofertas/historial-modelado.json` (fecha, oferta, carpeta, referente, `funnel`, `tema`, `pais_destino`). Sin esa línea la variación no funciona en la siguiente.

**Aviso.** La corrida de México fue una TSL corta con video de apoyo. Un quiz, una VSL larga o un funnel con upsell no se han construido todavía con esta skill: el desarme tiene que mapear cada paso (`02-desarme-del-referente.md` §1b) y la fase de landing va a necesitar piezas nuevas. Decir ese riesgo al proponer la oferta, sin que sea motivo para evitarla.

**Condiciones para que se pueda hacer con este recorrido:**
- Producto digital de pago único que se entrega como archivo (PDF, plantillas, patrones). Suscripciones, comunidades, apps y cursos con acompañamiento quedan fuera.
- Se puede producir de verdad con las herramientas disponibles, y con contenido propio o de dominio público.
- No depende de una marca personal ni de una cara.
- La promesa no es de salud ni de ingresos garantizados (el riesgo se evalúa por promesa y encuadre, no por tema).
- Pocos conceptos de anuncio repetidos muchos días suele ser mejor señal que muchos conceptos nuevos.

### 1.2b Veto: el referente no puede correr en todos lados (2026-11-14)

Oferta D se eligió con Referente D pautando en los 57 países de la lista de entonces y en los 62 de afuera que se miraron (incluido México, 127-170 anuncios) y salió a México igual. Una oferta cuyo referente corre en todos los países donde podemos lanzar **no tiene mercado libre: no se modela**, por buena que sea.

Antes de tomar el primero de la tabla:
1. Medir en qué países corre su referente: `P=.claude/skills/buscar-ofertas/scripts/paises_referente.py`; `python3 $P universo` (sin oferta: los 93 de `elegir_mercado.py`) y, por mitades (`python3 $P mitades <lista>`), `ads_library_search` con `page_ids: [<page_id>]`, `ad_active_status: "ACTIVE"`, `limit: 1`, `countries: [...]`. Un grupo con 0 deja todos sus países en 0; uno con más se parte hasta países sueltos.
2. Guardar la medición en el candidato como `"referente_paises": {"paises": {"US": 147, ...}, "sin_anuncios": [...]}` y volver a correr `ordenar_candidatos.py`. Si el referente corre en todos, queda fuera («VETO») y se marca `descartada` en el banco; se mide el siguiente.
3. Pasar la misma medición a la fase 2 (`elegir_mercado.py ordenar … --medicion <archivo>`), que veta país por país.

Un referente que corre en muchos países pero deja algunos libres sirve: el mercado sale de esos libres. Con menos de 3 libres, la tabla lo avisa.

**Libre tiene que ser pautable (2026-11-14, Oferta J).** Los países donde Meta exige anunciante verificado (SG, TW, TH, MY, AU, IN; `reglas.json → meta`) no cuentan como libres mientras el portfolio no esté verificado: `ordenar_candidatos.py` ya los saca de la lista de lanzables. Ojo con la trampa: un referente que corre en casi todo el mundo y da 0 justo en esos países **no** dejó un hueco, también él está bloqueado ahí. Oferta J se eligió con «libres» SG, TW, TH, IN, se armó entera dos veces (EE. UU. y Singapur) y quedó sin mercado: el referente corría en los otros 89.

**Un grupo con anuncios no prueba nada de cada país.** Medir por mitades hasta países sueltos; un «Europa chica: 86» no dice si Finlandia está en 0. El 14-nov se dio por «medido» un grupo y hubo que volver a medir 60 países uno por uno.

### 1.3 Volver a medir el día que se empieza

Siempre con todos los países: el conector sin `countries`, y en el navegador `country=ALL` (nunca el país desde donde se trabaja). Para contar basta `limit: 2`. La antigüedad real y el reparto por oferta se sacan de la página de la Biblioteca del anunciante (ver `tropiezos.md`, segunda corrida).

`ads_library_search` con `page_ids: [<page_id>]`, `ad_active_status: "ACTIVE"`, `limit: 50`. Anotar `estimated_total_count` y la fecha de inicio de cada anuncio.

En México el barrido había medido 38 activos el 6-nov y cuatro días después quedaban 6, todos del 22-23 de octubre: los más viejos son los que sobrevivieron al recorte, y son los que se modelan. El dueño lo pidió así: «modelando los mejores que tiene corriendo y los más antiguos».

Si quedan muy pocos o ninguno, decírselo antes de seguir: puede que la oferta se haya apagado.

Encontrar la landing: si no está registrada, abrir una ficha (`ad_snapshot_url`) y seguir el botón; registrarla con `scripts.referentes.landing` para que quede en el panel.

