# Plantilla de salida del Maker: `copy.json` (un campo por bloque del plano)

> v0.2.0 sin pulir (alineada el 2026-11-07 con el plano `referente`, el esquema `copy` 0.2.0 y J6-J21; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).
> `copy.json`, `paleta.json` y `assets.json` son **el contrato de entrada del generador** de `landing/` (`landing.generar` los lee desde el 2026-11-06; ver §8). Esquemas propuestos: `templates/copy.schema.json` (**0.2.0**, aditivo: un copy 0.1.x sigue siendo válido), `templates/paleta.schema.json`, `templates/assets.schema.json` (1.1.1). Ejemplos válidos: `templates/*.ejemplo.json` (oferta `_ejemplo`, `es-ES`, dinero, copy 0.1.0 = plano `clasica`) y `evals/dorados/relaciones-pl-PL/` (`pl-PL`, relaciones); la corrida real con plano `referente` y copy 0.2.0 es `ofertas/OF-202611-91/05-landing/copy.json`. Los esquemas son **propuesta de D5**, no contratos: ver `dependencias.md`.
> **Qué plano rige el copy:** `copy.schema_version` ≥ 0.2.0 o `estructura: "referente"` → plano `referente` (tabla §3b); `estructura: "clasica"` o un copy 0.1.x → plano de 14 secciones (tabla §3). Una sección que no es del plano elegido no se publica y `lint_copy.py` la marca `D5-COPY-SECCION-FUERA-DE-PLANO` (MENOR).

## 1. Reglas generales de escritura

1. **Sin números a mano.** Precio, bump, moneda, días de garantía, tiempo, cantidades, formatos, vencimiento del enlace, divulgación de IA y ayuda del país se escriben con **placeholders**; los expande el generador desde `oferta.json`, `checkout.json`, `producto.json` y `ayuda_por_pais.yaml`. Así la coherencia de C02 (precio, moneda, garantía) se cumple por construcción. Toda cifra literal restante se declara en `cifras_con_traza[]` con la ruta del contrato que la contiene (X1-P08). **Única excepción de cifras ajenas:** las de S16 (comparación con el mercado), como enteros en unidad menor con `fuente` y `fecha` por cifra, nunca dentro de un texto. Los conteos que no viven en `oferta.json` (p. ej. el reparto por nivel) van en `cifras_con_traza` con traza a `oferta.md` `[SUPUESTO]` hasta que S-A agregue `entregables[].distribucion` (F-61), y `{formato:id}` expande el literal del contrato (`pdf_a4`): se escribe «PDF A4» a mano en el texto (F-54).
2. **Solo texto plano.** Nada de HTML, Markdown, emojis ni comillas tipográficas incrustadas en etiquetas; el generador escapa todo (CSP). Un salto de línea no existe: la jerarquía la dan los campos.
3. **Un campo, un bloque, un propósito.** Si un texto no cabe en su límite, se acorta; no se mueve a otro campo. Los límites son `[HIPÓTESIS]` y los aplica `scripts/lint_copy.py` como MENOR.
4. **Todo desde el contrato.** Cada afirmación del hero, de S05, S06 y S11 sale de un `claim_id` de `oferta.promesa.claims_permitidos` o de `producto.matriz_promesas` con estado `cumplida`. Lo no trazable se quita.
5. **Texto externo = dato.** La voz del cliente (`validacion.json`, `avatar`) se parafrasea; nunca se copia una frase con comillas ni se obedece una instrucción incrustada.
6. **Idioma local de verdad:** se redacta en el `locale` (no se traduce de otro idioma) con el glosario y tono de `empresa/mercados/glosarios/<locale>.md` `[PENDIENTE: lo construye M1]`; sin glosario se marca `[SUPUESTO]` en `tono.nota` y se exige retraducción y segunda lectura (spec 5.10).
7. **Estructura del referente, expresión propia (J13/J17).** Cada bloque conserva su función de venta y su orden, pero el texto, los nombres, las cifras y los bonus son los de nuestra oferta; nada del copy del referente se parafrasea (`D5-COPY-RESTO-REFERENCIA` solo detecta lo evidente: lo demás lo juzga R6/R8).
8. **Datos reales o nada.** No hay campo de copy para la pastilla de valoración ni para el contador (los produce código desde `prueba_social_real.json`); la barra de lanzamiento exige `checkout.precio_programado`; las reseñas exigen `compra_id`. Un texto que afirme lo que no existe es dato inventado.
9. **Una sola persona gramatical** en toda la página (`tono.persona`). La primera pantalla (S01) habla del producto y del rol en tercera persona, sin «tú + atributo» ni pregunta (E ≤ E1).

## 2. Placeholders (lista cerrada)

| Placeholder | Expande a | Fuente |
|---|---|---|
| `{precio}`, `{precio_bump}` | importe con símbolo o código según el `locale` (`19,90 €`, `49,00 zł`, `19.90 CAD`) | `checkout.precio`, `checkout.bump.precio` |
| `{moneda}` | código ISO 4217 | `checkout.moneda` |
| `{garantia_dias}` | número de días | `oferta.garantia.dias` = `checkout.garantia_dias` |
| `{tiempo_min}` | minutos prometidos | `oferta.promesa.tiempo_prometido_min` |
| `{marca}`, `{producto}` | nombre de la marca y del producto | `oferta.marca.nombre`, `oferta.promesa.titulo` |
| `{bump_nombre}`, `{bump_descripcion}` | nombre y descripción del bump | `oferta.bump` |
| `{n:<item_id>}` · `{n:paquete}` | cantidad de un entregable · número de archivos del paquete | `oferta.entregables[].cantidad` · `producto.items` con `en_paquete` |
| `{paginas:<item_id>}` | páginas de un archivo | `producto.items[].paginas` |
| `{formato:<item_id>}` | formato del entregable | `oferta.entregables[].formato` |
| `{vence_dias}`, `{max_descargas}` | vencimiento y límite del enlace | `producto.entrega` |
| `{ia_divulgacion}` | frase de divulgación de IA | `producto.ia_divulgacion` |
| `{ayuda_pais}` | línea de ayuda del país (violencia, duelo, crisis) | `ayuda_por_pais.yaml` `[PENDIENTE: X1]` |
| `{fecha_lanzamiento}`, `{precio_despues}` | fecha y precio de después de la barra de lanzamiento (solo en `barra_superior.lanzamiento.texto`; `{precio}` es el actual) | `checkout.precio_programado` |

## 3. Campos por bloque (plano `clasica`; el `referente` usa los mismos campos más los de §3b)

Ruta dentro de `copy.json` → límite `[HIPÓTESIS]` → fuente de verdad → reglas. Las rutas cuyo nombre acaba en `_ref` y las claves `id`, `tipo`, `modo`, `usos` son metadatos, no texto visible.

| Ruta | Límite | Fuente | Reglas |
|---|---|---|---|
| `tono.persona/registro` | — | glosario del locale | una sola persona gramatical |
| `contexto_riesgo` | — | `oferta.riesgo` | copiar `macro_nicho`, `nivel`, `tema_vigilado`; `conflicto_pareja_familia=true` en todo producto de conflicto de pareja o familia; `hero_reformulado[]` documenta cada hook reescrito |
| `meta.title/description/og_*` | 65 / 160 | marca + producto | neutros: sin salud, deuda, ruptura (C16); sin «ejemplo» |
| `cta[]` | texto ≤ 32 | — | ≥ 2 textos distintos (idealmente 3: hero, compra, cierre); verbo + objeto; sin promesa de resultado ni urgencia (§5) |
| `S01.kicker` | 40 | formato + tema neutro | tercera persona, describe el producto |
| `S01.h1` / `h1_resaltado` | 70 / 40 | `promesa`, `angulos[].hook` | sin pregunta, sin atributo del lector, sin cifra de resultado; si el hook los tiene, reformular (§6) |
| `S01.subtitulo` | 160 | `promesa.subtitulo`, `claims_permitidos` | promesa + diferencial; solo claims permitidos |
| `S01.pills` | 3–4 × 24 | `entregables`, `tiempos` | hechos del producto, no beneficios de vida |
| `S01.microcopy` | 90 | `garantia`, `precio` | garantía · pago único · entrega, con `{garantia_dias}` |
| `S01.imagen_ref` | — | `assets.json` | `slot_id` de la ranura del hero |
| `S02.cifras[]` | 3 × (valor, etiqueta ≤ 20) | `producto.items`, `tiempos` | solo placeholders o `cifras_con_traza`; sin cifras de clientes, ventas ni resultados |
| `S02.beneficios[]` | ≤ 3 × (28 / 110) | `claims_permitidos` | beneficio de uso con verbos de la herramienta (ordena, calcula, planifica, prepara) |
| `S03.titulo` | 90 | `avatar` | impersonal o tercera persona |
| `S03.dolores[]` | 3–5 × 140 + `fuente_ref` | `objeciones_top`, `avatar.lo_dice` | parafraseados en el vocabulario del cliente, sin comillas; **situaciones y obstáculos, no estados** (nada de edad, salud, estado civil o familiar, finanzas vulnerables, juicios de valor sobre el lector) |
| `S03.reencuadre` | 120 | `mecanismo.causa_raiz` | «el problema no es X, es Y»; sin culpar al lector |
| `S04.pies[]` | 90 + `imagen_ref` | `assets.json` | solo ranuras con captura real aprobada |
| `S05.nombre` | 2–6 palabras | `mecanismo.nombre` | tal cual; no es un claim de salud ni de ingresos |
| `S05.como_funciona` | 200 | `mecanismo.como_funciona` | verbatim del contrato (puede recortarse) |
| `S05.de_a_b` | 120 | `prueba_una_frase` | sin obstáculo atribuido al lector |
| `S06.modulos[]` | 1–6 × (50 / 140) + `item_ref` | `producto.items`, `entregables` | un módulo por archivo o paso real; `item_ref` existe en `producto.items` |
| `S06.checklist.items` | ≤ 6 × 80 | `producto.pasos` | qué recorre el producto |
| `S07.si` / `S07.no` | 3–4 × 90 | `cliente_ideal`, `riesgo.claims_a_evitar` | tercera persona; «no» incluye siempre: no es servicio humano ni terapia/asesoría, no garantiza resultado, 18+ |
| `S08.modo` | `honesta` \| `real` | `producto`, D10 | al lanzar `honesta`; `real` solo con `compra_id` |
| `S08.bloques[]` | 3 × 200 | muestra, `producto.ia_divulgacion`, vendedor | tres bloques: qué se puede comprobar, cómo está hecho, quién vende |
| `S08.resenas[]` | ≤ 6 × 160 | D10 | `compra_id` obligatorio; sin cifras, estrellas ni transformación |
| `S09.bonos[]` | ≤ 5 × (50 / 120) + `archivo_ref` | `oferta.bonus` | solo con archivo real; sin precio tachado ni «valor» apilado |
| `S09.bump` | texto 120 | `oferta.bump`, `checkout.bump` | complemento natural; `premarcado: false`; el precio va por `{precio_bump}`; sin «oferta única» |
| `S10.titulo/texto/nota_legal` | 70 / 220 / 160 | `garantia` | días por `{garantia_dias}`; incondicional; la nota aclara que no sustituye el derecho legal de desistimiento |
| `S11.titulo/descripcion` | 80 / 120 | `promesa` | — |
| `S11.incluye[]` | 3–6 × 70 | `producto.items` | solo lo que se entrega |
| `S11.pills` | 3 × 24 | `garantia`, `entrega` | pago único · entrega inmediata · garantía |
| `S11.linea_precio` | 70 | `precio`, `mercado.fiscal` | «Precio final: {precio}…»; con régimen diferido **nunca** «IVA incluido» ni «+ IVA» |
| `S12.preguntas[]` | 6–9 × (90 / 280) | `objeciones_top`, `mercado.consumo`, `producto.entrega` | siempre las fijas: **entrega, formato, desistimiento/reembolso, medios de pago, alcance (qué no es), idioma**; más las objeciones por peso; respuestas concretas y honestas; la objeción nº 1 puede abrir el FAQ |
| `S13.filas[]` | 2–4 × 60 | `mecanismo`, `producto` | solo diferencias verificables del producto |
| `S14.aviso` | 200 | `riesgo` | informativo, no asesoramiento (en dinero: «financiero, fiscal ni legal»; en salud: «no sustituye a un profesional de la salud»; en relaciones: «no es terapia ni asesoría legal»), 18+ |
| `S14.aviso_seguridad` | — | nota 25 §5.1 | obligatorio si `conflicto_pareja_familia`: «Si temes por tu seguridad, no uses este material» + `{ayuda_pais}` |
| `S14.ayuda` | — | `ayuda_por_pais.yaml` | obligatorio en amarillo-b y temas vigilados: «Si necesitas ayuda ahora» + `{ayuda_pais}` |
| `S14.enlaces` | — | locale | rótulos de los 7 enlaces legales + desistimiento + preferencias de cookies |
| `banner` | texto 200 | `tracking.consent_gating` | Aceptar y Rechazar del mismo peso; marketing apagado; `version_texto` versionado |
| `comprar.resumen_prepago` | ≥ 4 | `mercado.consumo`, `producto` | vendedor, formato, idioma, licencia (sin reventa), entrega inmediata, reembolso |
| `comprar.casillas[]` | — | `checkout.consentimientos` | separadas, `premarcada: false`; en UE/UK (y donde `mercado.consumo` lo exija) la casilla `renuncia-entrega-inmediata` es obligatoria (en el formulario de `/comprar` es el campo `renuncia_desistimiento`; la casilla de términos se enlaza debajo del botón, no es un campo) |
| `variantes_por_angulo` | — | `oferta.angulos` | solo S01 (campos del hero), S03 (`orden`), S11 (`cta_ref`), S12 (`primero`) |
| `omitidas[]` | motivo | plano | solo S02, S04, S08, S09, S13; con motivo real |

## 3b. Plano `referente` (copy ≥ 0.2.0): qué campo alimenta cada bloque y qué se omite sin dato real

Orden de la página y, por bloque, el campo de `copy.json`, el dato o la ranura que lo alimenta, los límites `[HIPÓTESIS]` que mide `lint_copy.py` y la regla de omisión. **Todo es opcional salvo S01, S06, S07, S10, S11, S12 y S14.** Cualquier texto admite `==palabra==` (resaltado, típico en `S01.h1`) y `{placeholders}`. Los ids de ícono (`icono`) son de una lista cerrada del sprite (`semilla, reloj, cohete, diana, libro, mapa, movil, imprimir, descarga, corazon, rayo, bombilla, grafico, usuarios, calendario, chat, ruta, niveles, persona, hoja, lupa, escudo, regalo, sobre, candado, estrella, pregunta, balanza, etiqueta, pluma, megafono, insignia, play`): el Maker no escribe SVG.

| # | Bloque (plantilla) | Campo del copy | Dato / ranura | Límites | Se omite si |
|---|---|---|---|---|---|
| 0 | **Barra superior** (pegajosa) | `barra_superior.informativa` (siempre) · `.lanzamiento{texto, fecha}` · `.icono` | `checkout.precio_programado{fecha, precio}` | texto de una línea | la de lanzamiento solo si la MISMA fecha existe en `checkout.json`, no ha pasado y el precio de después es mayor y en la misma moneda; si no, cae a la informativa. **Nunca** cuenta atrás ni «solo hoy» |
| 1 | **Héroe** con mockup grande (`s01-hero-ref`) | `S01.{kicker, h1, h1_resaltado, subtitulo, pills[3-4], cta_ref, microcopy, imagen_ref}` | ranura `hero`; pastilla de valoración y contador: `prueba_social_real.json` (sin campo en el copy) | kicker 40 · h1 70 (≤ 12 palabras) · subtítulo 160 · píldora 24 · microcopy 90 | nunca (sin imagen aprobada: portada tipográfica) |
| 2 | **Qué hay dentro** (tira oscura, `s04-tira`) + CTA | `S04.{kicker, titulo, subtitulo, pies[{texto, imagen_ref}], cta_ref}` | ranuras `muestra-*` | pie 90 | ninguna ranura de sus pies está `aprobado` (nunca se inventa una captura; una ranura `ilustrativa` no cuenta como muestra real en producción) |
| 3 | **Reseñas / confianza** (`s08-opiniones`) + CTA | `S08.{modo, kicker, titulo, subtitulo, bloques[3], resenas[{compra_id, texto, autor?}], cta_ref}` | `oferta.prueba` (testimonio con permiso), `producto.ia_divulgacion`, identidad del vendedor | bloque 200 · reseña 160 | sin reseñas reales ni bloques; una reseña sin permiso detiene la generación; en `--vista-previa` salen demos con cinta «DEMO» |
| 4 | **Niveles con selector** (`s06-pestanas` o `<details>`) + CTA | `S06.{kicker, titulo, subtitulo, selector: pestanas\|desplegable, modulos[{titulo, texto, etiqueta, temas[], categorias[{titulo, texto, temas[]}], icono, item_ref}], cta_ref}` | `producto.items`, `entregables`; el reparto por nivel va en `cifras_con_traza` (F-61) | módulo: título 50 · texto 140 · etiqueta 22 · tema 30 | nunca |
| 5 | **Para quién** (tarjetas con íconos) + CTA | `S07.{kicker, titulo, subtitulo, tarjetas[4]{titulo?, texto, icono?}, si[], no[], cta_ref}` | `cliente_ideal`, `riesgo.claims_a_evitar`, perfiles de la voz del mercado | tarjeta: título 50 · texto 150; `no` 90 | nunca (sin `tarjetas` se derivan de `si`) |
| 6 | **Bonus** (sección oscura, portada por bonus; `s09-bonus`) y bump | `S09.{titulo, subtitulo, bonos[{nombre, texto, archivo_ref}], bump}` | `oferta.bonus` con archivo en `producto.items`, ranuras `bono-N`, `checkout.bump` | nombre 50 · texto 120 | sin bono con archivo ni bump. Nombres, lista y orden **propios** (J13). **Sin precio tachado ni «GRATIS»**: chip «incluido» |
| 7 | **Comparación con el mercado** (`s16-comparacion`) | `S16.{titulo, intro?, filas[1-6]{etiqueta, desde, hasta?, fuente, fecha}}` | importes REALES de terceros en unidad menor | — | fila sin `fuente` o sin `fecha` válida (no se publica y el lint la marca BLOQUEANTE); `desde`/`hasta` enteros |
| 8 | **Precio y desglose** (`s11-precio-ref`) | `S11.{titulo, descripcion, incluye[3-6], pills[3], linea_precio, cta_ref}` | `checkout.json`, `oferta.precio` (escalera J16), ranura `compra`, medios de `mercado.metodos_pago` | título 80 · descripción 120 · incluye 70 · píldora 24 · línea 70 | nunca. Sin tachados ni suma de «valores» |
| 9 | **Garantía** con insignia, **después** del precio (`s10-garantia-ref`) | `S10.{titulo, texto, nota_legal}` | `oferta.garantia`, `{garantia_dias}` | 70 · 220 · 160 | nunca. Con **procedimiento** (cómo y a dónde escribir; el contacto real depende de Q-01) |
| 10 | **Cómo lo recibes** (3-4 pasos) + CTA | `S15.{kicker, titulo, pasos[3-4]{titulo, texto, icono?}, cta_ref}` | `producto.entrega` (vencimiento y descargas por placeholders) | título 50 · texto 120 | sin S15 se deriva del checklist de S06 (≤ 3 ítems); sin ninguno, omitida |
| 11 | **FAQ** (`<details>`) | `S12.{titulo, preguntas[6-9]{q, a}}` | `objeciones_top`, `mercado.consumo`, `producto.entrega` | q 90 · a 280 | nunca. Abre la objeción nº 1 («ya probé y no funcionó, ¿por qué esto sería distinto?»); más las fijas del locale |
| 12 | **CTA final** con lista (`s13-cierre-ref`) | `S13.{titulo, filas[2-4], cta_ref, microcopy, lista[1-8]}` | solo hechos verificables | título 90 · celda 60 | sin S13 |
| 13 | **Pie** | `S14.{descripcion, aviso, aviso_seguridad, ayuda, enlaces}` | LLC (D0), `riesgo`, `ayuda_por_pais` | 120 · 200 | nunca |
| — | CTA | `cta[{id, texto, usos[]}]` (≥ 2 textos distintos) y `cta_ref` por sección | — | 32 | — |
| — | Banner, `/comprar`, `/gracias` | `banner`, `comprar`, `gracias` | `tracking.consent_gating`, `checkout.consentimientos` | — | nunca |
| — | Omisiones | `omitidas[{seccion ∈ S02, S04, S08, S09, S13, S15, S16, motivo}]` | — | — | S04, S08, S09 y S13 exigen el registro; S15 y S16 no |

**No tienen campo de copy** (y no hay que inventarlo): la pastilla de valoración y el contador del héroe (`prueba_social_real.json`), la barra de lanzamiento sin `precio_programado`, avisos de compra reciente, cuentas atrás, precios tachados, avatares con foto, ventana de salida. **No forman parte del plano:** S02, S03 y S05 (el gancho de dolor va en el héroe y en la FAQ). Referencia completa del orden y de los componentes: `landing-estructura.md` §2b; mapa de ranuras de contenido del referente: `docs/_historial/modelado-piloto/referentes/analisis-html-axon.md` §7.

## 4. Variantes de CTA

Patrón: **verbo de acción + objeto concreto** (opcional: precio por `{precio}`). Tres usos distintos como mínimo: hero (invitación), compra (con precio) y cierre (continuidad). Ejemplos por idioma en `references/locales.md`. Evitar: promesa de resultado («quiero conseguir trabajo»), urgencia («solo hoy», «ahora»), atributo del lector, mayúsculas sostenidas y flechas decorativas; el texto debe seguir siendo cierto si el lector hace clic sin leer nada más.

## 5. Nombre del producto
Sale de D3 (`oferta.promesa.titulo`) y D5 **no lo cambia**. Debe ser descriptivo, simple y local (formato + objeto), sin sufijos de marca (Studio, Academy, Master, Pro, Lab, Creative), sin nombres de estado o resultado («Cero Deudas», «Glucosa Estable», «Sleep Reset»), sin los nombres de las 11 enfermedades de la lista de curas y sin cifra de resultado. Si el nombre incumple, D5 lo marca en `brief.md` como propuesta y devuelve el caso a D3 (D5 nunca cambia promesa, precio ni claims). La **marca** (dominio, `<title>`) nace neutra.

## 6. Reformular el hook de un ángulo para el hero (E ≤ E1)
El hook de `oferta.angulos[]` puede estar pensado para el anuncio. En la primera pantalla de la landing el rol va en tercera persona y sin atributo, y sin pregunta. Procedimiento: (1) conservar el `claim_id` y el beneficio de uso; (2) cambiar el sujeto al producto o al método («Una pausa laboral se puede contar como un relato»); (3) quitar estados del lector («que más temes», «tu vergüenza»); (4) anotar en `contexto_riesgo.hero_reformulado[]` el hook original y el motivo. Si no se puede sin cambiar la promesa, se devuelve a D3.

## 7. Cómo se valida
`python3 scripts/lint_copy.py --copy copy.json --oferta oferta.json --mercado mercado.json --assets assets.json` (0 BLOQUEANTE y 0 MAYOR) y validación contra `templates/copy.schema.json`. El lint es una red mínima: la fuente de verdad en producción es `compliance.lint_claims` (B6) y `landing.validar` (B4). Mapa a C01–C17: `checks-c01-c17.md`.

## 8. Qué lee `landing.generar` hoy (0.2.0) y lo que sigue abierto

Lectura de `landing/README.md` y `landing/PROCESO.md` (2026-11-07). El generador (S-B/S-C) **ya lee** `copy.json`, `paleta.json` y `assets.json` y emite, con las mismas entradas y los mismos bytes: el plano elegido (`referente` o `clasica`), `/comprar` con su formulario, `/gracias`, las siete legales en es, en, it y pl, `/desistimiento` si la ruta figura en `rutas.json`, `_headers` con la CSP y `js/consentimiento.js`. Cierran las diferencias que listaba la 0.1: `<title>` y `og:*` salen de `copy.meta`; H1 de `S01.h1` (+ variante por ángulo); CTA, microcopy y banner del copy y del `locale`; FAQ con respuestas reales en `<details>`; imágenes solo de ranuras `aprobado` (sha256 y peso verificados); CSS desde `paleta.json` con contraste AA verificado; `L1-EJEMPLO-VISIBLE` busca solo el sello `EJEMPLO` y `RX_IMPORTE` solo reconoce símbolos y códigos ISO reales.

| Componente nuevo del plano `referente` | Dónde se define | Estado |
|---|---|---|
| Barra superior, `==resaltado==`, héroe con mockup, tira «qué hay dentro», reseñas de texto, niveles con selector `:target`, para quién con íconos, bonus con portada, comparación con el mercado, precio, garantía con insignia, cómo lo recibes, CTA repetido, botón fijo móvil | §3b; `landing-estructura.md` §2b | construido, 282 pruebas de `tests/landing` en verde |
| Datos reales: valoración, contador, reseñas, barra de lanzamiento | `prueba_social_real.json`, `checkout.precio_programado` | construido en el generador; **faltan** el productor de `prueba_social_real.json` (S-B), el esquema (S-A) y el campo `precio_programado` en `checkout` (S-A) |
| `--vista-previa` (demos con cinta «DEMO», marcadores, barra fija) | `landing/README.md` | construido; bloqueado por `L1-DEMO` y rechazado en producción |

**Sigue abierto** (detalle en `dependencias.md`): formato y lint por `locale` y moneda en todos los idiomas, no solo es/en/it/pl (SB-17) · `{formato:id}` expande el literal del contrato, p. ej. `pdf_a4` (F-54) · `RX_CONTADORES` y símbolos de moneda cubren pocos idiomas (el `$` se asume USD; ARS, CAD, AUD… se escriben con su código) · el hueco del mockup del héroe en `--vista-previa` (F-59) y la falta de `--salida` (F-62) · `landing.generar` lee `04-producto/producto.json` fijo (F-56) · la plantilla de `/legal/vendedor` no recibe los datos de la LLC (F-42) · un aviso real de «compra reciente», el autodesplazamiento de las tiras y el botón flotante que reaccione al scroll necesitan JavaScript (hoy el único `<script>` es `consentimiento.js`).
