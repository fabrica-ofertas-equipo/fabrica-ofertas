# Tipos de hook y variantes de formato (Anexo C de la spec)

El `hook_tipo` es un **vocabulario cerrado** de 8 valores en kebab-case (los valida `scripts/validar_d6.py matriz`; el esquema solo exige kebab, pero `contratos/taxonomia.yaml` **[PENDIENTE]** lo fijará). Si una idea no encaja, no se inventa un valor: se mapea al más cercano o se pide a quien mantiene la taxonomía.

## 1. Los 8 tipos

| `hook_tipo` | Qué es | Forma segura (sin cara, sin atributo del espectador) | Nunca |
|---|---|---|---|
| `dolor-situacion` | Una situación vivida, descrita sin atribuir condición a quien mira | «El domingo por la noche, la hoja de gastos sigue en blanco.» | «Si estás endeudado…», «¿Te sientes agotada?», cualquier «tú» + atributo |
| `resultado-artefacto` | El **entregable** terminado, mostrado (el resultado es el archivo, no un cambio en la vida del lector) | «Una hoja de costeo ya completada: costo por vela, precio mínimo y margen.» | Resultado del lector («ganarás», «bajarás», «tendrás») |
| `curiosidad` | Abre una pregunta que el cuerpo del anuncio responde | «Hay un orden para contar una pausa laboral en 30 segundos.» | Retener el sustantivo y no pagarlo (clickbait que contamina la conversión) |
| `mito` | Desmonta una creencia sobre la **tarea**, no sobre la persona | «Una plantilla de currículum no es lo mismo que una forma de explicar la pausa.» | Mito sobre el cuerpo, la pareja o el dinero del lector |
| `demostracion` | Se ve el producto funcionando (pantalla, hojas, manos) | Captura real de la hoja rellenándose con números «ilustrativos» | Capturas de ingresos, resultados de terceros, mockups que el producto no entrega |
| `lista-numero` | N elementos del entregable | «20 preguntas para conocerse en pareja, en tarjetas.» | Número de clientes, de ventas, de estrellas, de kilos o de euros ganados |
| `escena-pov` | Una escena concreta con manos y objetos del país | «Manos que ordenan 14 fichas sobre una mesa; la última dice “Primera pregunta”.» | Rostros, cuerpos, menores; escenas de sufrimiento |
| `pregunta-tarea` | Pregunta sobre la **tarea** | «¿Cómo armás tu menú de la semana?» (dorado; voseo solo en es-AR) | Pregunta sobre la persona o su condición: «¿Estás…?», «Jesteś zadłużony?» |

**Bloqueados por X1 aunque el corpus los use:** promesa con plazo (7 kg en 7 días), transformación visual (día 1 vs. día 21), contar billetes, facilidad de comienzo («sin experiencia»).

## 2. Qué hook por nivel de conciencia (spec §3.2)

N1 `curiosidad`, `escena-pov` · N2 `dolor-situacion`, `escena-pov`, `pregunta-tarea` · N3 `mito`, `lista-numero`, `pregunta-tarea` · N4 `demostracion`, `resultado-artefacto` · N5 no existe en el test. Frío amplio: N2–N3; N1 es apuesta; N4 con comparables.

## 3. `variante_formato` (en `matriz.json`; no está en `paquete.json`)

| Valor | Qué es | Ruta | Notas |
|---|---|---|---|
| `estatico-html` | PNG renderizado desde HTML/CSS | A | Por defecto para `imagen` y `carrusel` |
| `demo-pantalla` | Captura o grabación de la hoja o PDF real | A (captura) o B (video) | Mockup solo con entregables reales de `04-producto/` |
| `voz-en-off-broll` | Voz en off, clips propios, IA o licenciados y subtítulos | B | Nunca clips descargados |
| `pov-proceso` | Manos y producto, sin voz **[HIPÓTESIS nuestra]** | B | En «dinero con manualidades»: sin sugerir ingresos |
| `presentador-ia` | Avatar IA rotulado | B | Solo dinero verde; nunca como cliente |
| `vsl-45-90s` | Video largo con desarrollo | B | No en la v1 del test `[SUPUESTO]`: solo tras ganador y con X1 |
| `imagen-pregunta` | Estático cuyo gancho es una pregunta **sobre la tarea** (`pregunta-tarea`) | A | Formato con mejor costo por venta en la medición de la fuente `[DECL]`; `formatos-que-miden-bien.md` §1 |
| `relevo-otra-apertura` | El mismo anuncio con otra primera escena y otro hook verbal (escalera 5.8, paso 1) | A o B | Se registra `variante_de`; `formatos-que-miden-bien.md` §2 |
| `ganador-traducido` | Ganador **propio** re-renderizado en otro idioma (traducción fiel + 5 capas + X1) | A | Hipótesis en el idioma nuevo; `formatos-que-miden-bien.md` §3 |

Los tres últimos valores son una **propuesta de vocabulario** (S-A los fija en `contratos/creativos.schema.json`, `PEDIDOS.md` #3); mientras tanto viven en `matriz.json` y en `datos/ganchos.jsonl`. Formatos de J8 sin construir (reel de 3 experimentos, canción con IA, review de la app): `formatos-j8-sin-construir.md`.

## 4. El hook son tres componentes que se complementan

Un hook de video es **acción visual (0–3 s) + línea hablada + texto en pantalla**, y no se repiten: si la voz dice la frase, el texto en pantalla nombra el entregable, y la imagen muestra el artefacto. Un estático tiene dos: imagen + titular, que no se subtitulan entre sí. Se escribe cada componente en su columna del guion (`templates/guion.md`); un hook con una sola columna llena es un tercio de hook. Debe entenderse **en 3 s y sin sonido**.

## 5. Puente (on-ramp) y variación

Segundos ~3–15: continúan la premisa del hook; si el hook promete «el orden para contarlo», el puente empieza a mostrarlo, no a vender la marca. Al probar un hook nuevo sobre un cuerpo existente (escalera, paso 1) se **reescribe el puente** de cada hook; el cuerpo, la prueba y el CTA no cambian. Dos hooks de un mismo concepto difieren en mecanismo (`hook_tipo`), no solo en palabras.

## 6. Mapa desde `anthropic-skills:creativos-ads` (si existe)

| Movimiento de esa skill | En D6 |
|---|---|
| Curiosity gap | `curiosidad` |
| Relatability / POV | `escena-pov` |
| Question | `pregunta-tarea` (solo sobre la tarea) o `dolor-situacion` |
| Bold claim | `mito` o `resultado-artefacto` con `claim_id`; nunca una promesa |
| Proof-first | `demostracion` con el producto real; **no** capturas de resultados |
| First-person confession | **No usar** (testimonio fabricado) |
| Contrast / before-after | **No usar** como transformación; sí «hoja en blanco» frente a «hoja completa» del mismo entregable |
| Countdown / gamified | **No usar** (escasez salvo cierre real verificable por código) |

## 7. Ejemplos aprobables por idioma (sin cara; [SUPUESTO], ninguno probado ante Meta)

| Locale | Macro | Hook (`hook_tipo`) |
|---|---|---|
| es-ES | dinero | «Costo por vela, precio mínimo y margen en una sola hoja.» (`resultado-artefacto`) |
| it-IT | salute | *Un planner settimanale dei pasti con la lista della spesa già pronta.* (`resultado-artefacto`) |
| pl-PL | dinero | *Arkusz: koszt, cena minimalna i marża w jednej tabeli.* (`resultado-artefacto`) |
| en-US | relaciones | «Twenty conversation cards for a quiet evening together.» (`lista-numero`) |
| fr-FR | salud | *Des fiches de mobilité de 10 minutes pour les pauses.* (`lista-numero`) |
| ro-RO | dinero | *Un tabel pentru costurile unui produs handmade.* (`resultado-artefacto`) |
| de-DE | relaciones | *Arbeitsmappe als PDF: Fragen vor einem schwierigen Gespräch.* (`pregunta-tarea` implícita en el titular) |

## 8. Historial y antirrepetición

Cada gancho que se usa queda en `datos/ganchos.jsonl` con su fuente y se comprueba con `ganchos.py rechazar` antes de redactar el resto del anuncio (`biblioteca-ganchos.md`). Los 8 `hook_tipo` siguen cerrados; la biblioteca evita repetir el **texto** y la **copia** de un referente, no obliga a variar el tipo.

## 9. Ganchos que vienen de un referente modelado (skill `modelado-oferta`, MOD-7)
El tipo de hook (§1) y el ángulo se heredan; el texto no. Reglas de reescritura y chequeos: `inmersion-y-derechos.md` §3 (se descartan los ganchos de cifras de clientes o estrellas, urgencia, resultado en un plazo y preguntas sobre la persona; cada gancho nuevo nace de una cita del dossier, apunta a una palanca, pasa `ganchos.py rechazar` y el n-grama contra todos los textos del referente, y no va en primera persona atribuida). Imágenes de ambiente e ilustración: `modelado-oferta/references/imagenes-kie.md`.
