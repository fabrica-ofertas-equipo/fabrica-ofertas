# Ficha de oferta final y copy-brief — OF-202611-01 (es-ES, EUR)

> Ejemplo válido sobre `ofertas/_ejemplo` (oferta ficticia; no se lanza). Versión: v1 · origen_version: maker. Fuentes: `03-oferta/oferta.json`, `04-producto/producto.json`, `mercado.json`, `02-validacion/validacion.json`. Resultado del prechequeo: `preguntas` (falta Q-01, datos legales de la LLC; se usa el supuesto «datos pendientes» y no se publica).

## 1. Identidad
| Campo | Valor | Fuente |
|---|---|---|
| `oferta_id` · `familia_id` | OF-202611-01 · FAM-202611-01 | `oferta.json` |
| `locale` · moneda · países | es-ES · EUR · ES | `mercado.json` |
| Marca · dominio | Mi Regreso Laboral · miregresolaboral.example | `oferta.marca` |
| Macro-nicho · nivel | dinero · verde (P verde, C verde, E verde, N verde; reencuadre aplicado desde amarillo) | `oferta.riesgo` |
| `tema_vigilado` · conflicto pareja/familia | ninguno · no | `oferta.riesgo` |

## 2. Promesa y claims
| `claim_id` | Texto permitido | Evidencia | Se usa en |
|---|---|---|---|
| `incluye-plantilla-cv` | Incluye una plantilla editable de currículum con enfoque en competencias | `04-producto/entregables/plantilla-cv-puente-v1.md` | S06, S11 |
| `guion-explicar-pausa` | Incluye un guion para explicar tu pausa en 30 segundos | `04-producto/entregables/puente-de-la-pausa-v1-guia.md` | S01, S02, S05, S11, S13 |
| `tiempo-90-min` | Pensado para completarlo en unos 90 minutos | `04-producto/producto.json#tiempos` | S02, S12 (`{tiempo_min}`) |
| `garantia-14-dias` | Garantía de devolución de 14 días | `03-oferta/oferta.json#garantia` | S01, S10, S11, S12 (`{garantia_dias}`) |
**Claims prohibidos:** «conseguirás trabajo», «garantizamos entrevistas», cifras de sueldo o ingresos, cualquier afirmación sobre la situación personal del espectador.

## 3. Mecanismo y prueba de una frase
Puente de la Pausa: reordena el currículum por competencias, traduce lo hecho durante la pausa a frases con datos y añade un guion de 30 segundos. Prueba de una frase: «Para personas que vuelven a buscar trabajo tras una pausa larga y no saben cómo explicarla, el Puente de la Pausa es una guía con plantilla que lleva de “tengo un hueco en mi currículum” a “currículum y guion de entrevista listos” sin inventar experiencia ni pedir disculpas».

## 4. Público y dolores
Rol en tercera persona: quien vuelve a buscar trabajo tras una pausa larga (`cliente_ideal`).
| Dolor u obstáculo | Fuente | Peso | Sección |
|---|---|---|---|
| Un hueco en el currículum cuesta explicarlo sin sonar a disculpa | `validacion.json#handoff_d3.objeciones_top` | alta | S03 #1 |
| Lo hecho durante la pausa no parece «experiencia» y queda fuera del papel | `oferta.avatar.lo_dice` | media | S03 #2 |
| La pregunta sobre ese periodo llega en la entrevista sin respuesta preparada | ángulo `pregunta-de-entrevista` | media | S03 #3 |
| El formato cronológico deja la pausa a la vista y esconde las competencias | `oferta.mecanismo` | baja | S03 #4 |
Objeción nº 1 (alta): «¿Esto me va a conseguir trabajo?» → FAQ, respuesta honesta (no garantiza).

## 5. Qué incluye
| `item_id` | Nombre | Formato | Páginas / cantidad | Muestra |
|---|---|---|---|---|
| `guia-puente` | Guía del Puente de la Pausa (5 pasos) | markdown/PDF | 1 | — |
| `plantilla-cv` | Plantilla de currículum por competencias | docx/markdown | 1 | — |
| `muestra-guion` | Muestra gratuita del paso 4 | markdown | — | sí (aprobada para S04) |
**Bonus:** ninguno. **Bump:** «12 respuestas modelo para preguntas de entrevista» (`oferta.bump`, 790 en unidad menor): **AVISO P-08b: no existe en `producto.items`**; se mantiene en el ejemplo, pero en una corrida real el Maker no lo ofrecería hasta que D4 lo produzca. Tiempo prometido: 90 min.

## 6. Condiciones comerciales
Precio `{precio}` · bump `{precio_bump}` · garantía `{garantia_dias}` días · fiscal `diferido` → «precio final» · medios: tarjeta, Apple Pay, Google Pay, Link · entrega: enlace firmado por correo, vence `{vence_dias}` días, `{max_descargas}` descargas.

## 7. Pruebas reales vs faltantes
| Elemento | ¿Material real? | Decisión |
|---|---|---|
| Muestra del entregable | sí (`muestra-guia-v1.md`) | S04 incluida con 2 piezas (`muestra-principal`, `muestra-1`) |
| Reseñas con `compra_id` | no | S08 `honesta` |
| Divulgación de IA | sí | bloque «Cómo está hecho» con `{ia_divulgacion}` |
| Identidad del vendedor | pendiente (Q-01) | bloque «Quién lo vende» remite a `/legal/vendedor` |

## 8. Plano y ángulos
S01–S14 incluidas; sin omisiones. Ángulos: `hueco-como-relato` → `/` · `pregunta-de-entrevista` → `/a/pregunta-de-entrevista` · `plan-en-una-tarde` → `/a/plan-en-una-tarde`.
| Ángulo | Hook original | Hero reformulado (E ≤ E1) | `claim_id` |
|---|---|---|---|
| `hueco-como-relato` | Tu pausa no es un hueco: es un relato que puedes contar | Una pausa laboral se puede contar como un relato | `guion-explicar-pausa` |
| `pregunta-de-entrevista` | La pregunta que más temes, con tu respuesta ya escrita | La pregunta sobre la pausa, con la respuesta ya escrita | `guion-explicar-pausa` |
| `plan-en-una-tarde` | Currículum por competencias en una tarde | (sin cambio) | `tiempo-90-min`, `incluye-plantilla-cv` |

## 9. Copy-brief por sección (extracto)
S01: describir el producto y el rol en tercera persona; promesa solo con claims permitidos; CTA «Quiero la guía». S03: situaciones y obstáculos, sin estados del lector. S07: «no» incluye bolsa de trabajo, revisión individual y resultado asegurado. S08: honesta. S10: incondicional, nota sobre el derecho legal de desistimiento. S12: 8 preguntas (objeción nº 1 + 7 fijas, incluida la de tiempo).

## 10. Decisiones del Maker
| Decisión | Regla | Alternativa descartada |
|---|---|---|
| Hero en tercera persona | E ≤ E1 en la primera pantalla | conservar «Tu pausa no es un hueco…» |
| S08 honesta | sin reseñas con `compra_id` | opiniones de demostración |
| Sin «IVA incluido» | régimen diferido | «IVA incluido» por el `tax_behavior` |
| Casilla de renuncia añadida a `/comprar` | UE: renuncia en casilla separada | una sola casilla combinada |

## 11. Encargo de ranuras
| `slot_id` | `productor` | Qué muestra | Ratio · píxeles | `herramienta` |
|---|---|---|---|---|
| `hero` | D4 | portada de la guía junto a la plantilla | 1:1 · 1120×1120 | la fija D4 |
| `muestra-principal` | D4 | página de la guía con la fórmula del guion | 16:9 · 1280×720 | la fija D4 |
| `muestra-1` | D4 | primera página de la plantilla | 3:4 · 720×960 | la fija D4 |
| `compra` | D4 | composición de los dos archivos | 1:1 · 800×800 | la fija D4 |
| `og` | D6 `[SUPUESTO]` | marca + nombre del producto | 16:9 · 1200×675 | `render_estatico.py` (D6) |
| `muestra-2…6`, `bono-1…5`, `opinion-1…6` | — | `omitida` (sin material real) | — | — |
D5 solo declara; D6 cotiza lo suyo y el dueño autoriza.

## 12. Paleta y tipografías
Azul petróleo y blancos fríos con un único acento ámbar para el CTA (calma profesional, orden). Detalle y motivos en `paleta.json`. Source Serif 4 + Source Sans 3 (OFL), autoalojadas.

## 13. Supuestos y preguntas
`[SUPUESTO]` sin glosario de M1 para es-ES: tuteo informal, retraducción pendiente. `[SUPUESTO]` datos legales de la LLC pendientes (Q-01). Preguntas abiertas: ver `references/preguntas-abiertas.md`.
