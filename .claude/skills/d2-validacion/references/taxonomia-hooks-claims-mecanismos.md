# Taxonomías de D2: anunciante, hook, ángulo, claim y mecanismo (M1-M8)

> Fuentes: spec D2 Anexo B; `18d` §4.1, §5.1-§5.3. `contratos/taxonomia.yaml` (`hook_tipo`, `angulo_id`) **aún no existe** (`dependencias.md`): hasta entonces mandan las listas cerradas de abajo, marcadas `[SUPUESTO]`. Cuando exista, se reemplazan sin cambiar el resto. Los ejemplos son solo de salud, relaciones y dinero.

## 1. `tipo_anunciante` (lista cerrada; decisión del Maker con motivo y `evidencia_id`; el QA la reclasifica a ciegas)
`producto_digital` · `curso_mentoria` · `software` · `servicio` · `afiliado_reventa` · `marca_personal_escalera` · `otro`.
- Solo `producto_digital` y `curso_mentoria` cuentan 1; `marca_personal_escalera` cuenta × `marca_personal_peso` (0,6) y, si domina entre los sostenidos, sugiere el motivo `dependencia_de_marca_personal`. **Software, servicio y afiliado_reventa son sustitutos o ruido**: se listan en `sustitutos[]`, no suman a `N_ind_sost`.
- Pistas: dominio y estructura de la landing (checkout de un producto vs. alta de cuenta vs. agenda de llamada), «ebook/plantilla/guía» vs. «curso/mentoría/membresía», el nombre del anunciante es una persona y todo gira en torno a ella (marca personal).
- `operador_id`: clúster de páginas con el **mismo dominio**, la misma oferta (aun traducida), `page_id` repetido o el mismo `beneficiary_payers` (UE). Una página aislada es su propio operador; un operador en varios idiomas cuenta **una vez**. Anota siempre `motivo_clustering`.

## 2. `tipo_hook` (vocabulario cerrado de D6, Anexo C de `departamentos/07-creativos.md`; hasta que exista `contratos/taxonomia.yaml`)
`dolor-situacion` · `resultado-artefacto` · `curiosidad` · `mito` · `demostracion` · `lista-numero` · `escena-pov` · `pregunta-tarea` (sobre la **tarea**, nunca sobre la persona) · `otro`.
Lo observado que no encaja (urgencia, prueba social, pregunta sobre la persona, instrucción) **no es un tipo de hook**: se registra en `claims[]` con su nivel de riesgo y el hook va como `otro`.
Mapeo del vocabulario anterior de esta skill (sugerido; confirmar con D6): problema-solución → `dolor-situacion` · historia → `escena-pov` · pregunta → `pregunta-tarea` u `otro` + claim · comparación → `demostracion` · dato → `lista-numero`.

## 3. `angulo_principal` (≤ 10 + «otro»; kebab sin `_`; `[SUPUESTO]`)
El ángulo es la **razón emocional/práctica** que ordena el anuncio (no el tema). Lista genérica, válida para cualquier macro-nicho: `ahorro-de-tiempo` · `orden-y-claridad` · `evitar-un-error` · `paso-a-paso` · `plantilla-lista` · `atajo-con-ia` · `comparar-y-decidir` · `pertenencia` · `regalo-y-temporada` · `autoridad-del-metodo` · `otro`.
El ángulo recomendado por nosotros debe estar en esta lista (para medir `solapamiento_angulo`); su versión concreta («calendario de cuotas») va en `handoff_d3.angulos_candidatos` (kebab, sin `_`: D6 lo inserta en nombres de Meta). **No inventes ángulos nuevos para que el solapamiento salga bajo.**

## 4. Concepto (`concepto_id`)
Un concepto = una **promesa + un mecanismo** (no un `id` de anuncio ni una variante de formato). El `concepto_id` lo fija la lectura del snapshot (`c-<operador>-<n>`, kebab, sin `_`). Antes de leer: título normalizado (primer segmento antes de « | ») agrupado con `difflib` ≥ `sim_concepto`; los títulos genéricos («Más información», «Accede ahora») cuentan **como máximo 1 por fecha de creación**. 160 anuncios con la misma promesa y el mismo mecanismo = **1 concepto**.

## 5. Claims de los competidores (nivel de riesgo por claim, nota 25 §2.2)
Cada claim se guarda **parafraseado** (no el texto ajeno) con su nivel y, si es rojo, `prohibido_copiar: true`.
| Claim | Nivel | Qué hace D2 |
|---|---|---|
| Resultado atribuido al lector (peso, ánimo, dinero, deuda), con o sin cifra y plazo; «ingresos pasivos», «sin inversión», «sin experiencia»; cura/diagnóstico; control de un tercero; testimonio sintético, antes/después, escasez o precio ficticio | **rojo** (P2n/P3) | etiqueta, `prohibido_copiar`, **no es NO_GO**: es dato de mercado; el riesgo se evalúa en **nuestro** ángulo |
| Cifra reproducible del propio entregable, rotulada «ilustrativo» (P2s) | amarillo | puede inspirar un ángulo propio si X1 lo aprueba |
| Beneficio de uso con verbos de herramienta (ordena, calcula, registra, planifica, compara) | verde | ángulo seguro candidato |
Además: urgencia inventada (cuenta regresiva falsa), atributos personales dirigidos al espectador («si eres madre soltera», «¿endeudado?»), menores como público → rojo. **Que el competidor lo diga no lo hace permitido** (18d §8.6).

## 6. `tipo_mecanismo` M1-M8 (lo que el anunciante dice que *hace funcionar* su producto)
| Clase | Idea | Pregunta para clasificar | Ejemplos (genéricos) |
|---|---|---|---|
| M1 volumen / repositorio | «cantidad en un solo acceso» | ¿vende cuántos (plantillas, fichas, recetas) más que cómo? | «120 plantillas de presupuesto», «200 recetas» |
| M2 secuencia paso a paso | guía por etapas | ¿el valor es el orden de pasos hacia un resultado? | «organiza tus pagos en 4 pasos», «plan semanal de comidas por días» |
| M3 plantilla lista | rellenar y listo | ¿el comprador solo completa datos propios? | «hoja que calcula tus cuotas», «tarjetas de conversación para imprimir» |
| M4 atajo con IA / prompts | «el prompt/IA hace el trabajo» | ¿el diferenciador es la IA o los prompts? | «40 prompts para ordenar tus gastos» |
| M5 diagnóstico / verificación | «compara tu situación con el modelo» | ¿mide, chequea o puntúa algo del comprador? | «test de tus hábitos de gasto» |
| M6 novedad de producto | un objeto nuevo y específico | ¿lo central es lo novedoso del objeto? | «calendario con ventana de plazos» |
| M7 bundle con bonus / precio | paquete + precio visible | ¿el gancho es el bonus o el precio bajo? | «guía + 5 bonus a 9,90» |
| M8 anti-sistema | vencer un filtro o algoritmo | ¿promete esquivar un sistema (selección, banco, plataforma)? | «CV que supera los filtros automáticos» |
Reglas: se clasifica **un** `tipo_mecanismo` por concepto, el dominante; si dos pesan igual, el que aparece primero en la promesa y se anota `nota_clasificacion`. Se guarda la **clase y una paráfrasis** del mecanismo, nunca el texto ajeno. Se clasifica por lo que el anuncio dice que *hace funcionar* el producto, no por el formato del archivo.

### «MU indistinguible de un sostenido»
`mu.indistinguible_de_sostenido = true` solo si, **con evidencia**, un sostenido usa (a) el mismo nombre de mecanismo o (b) la misma lógica (misma causa raíz atacada con el mismo «cómo») aunque cambie el nombre. Es un juicio del Maker con `evidencia_id` que el QA reclasifica a ciegas. Dar un MU idéntico por diferencial es el sembrado **S14** (bloqueante). Consecuencia: `saturacion_mecanismo = alta` ⇒ no GO; sin hueco y con confianza ≥ media ⇒ NO_GO con devolución `sin_mecanismo`/`reformular`.

### Contraste obligatorio
Para cada sostenido del portafolio, una línea: `operador | mecanismo declarado (paráfrasis) | clase | ¿se parece al MU? sí/no + por qué`. El diferenciador del MU **no puede derivarse solo de las mismas fuentes que usó D1** (rúbrica R5).

## 7. Estados de campo
`observado` (visto en snapshot, landing o texto crudo; con `evidencia`) · `inferido` (derivado; di de qué) · `no_disponible`. Un campo `observado` sin `evidencia.leido_por ∈ {dueno, navegador_auto}` es defecto (`verificar_competidores.py` lo marca).
