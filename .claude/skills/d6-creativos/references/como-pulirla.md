# Cómo pulir la skill D6 (para el dueño)

**Estado: v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min).** Método del dueño: a mano en la pestaña Code → pulir → skill → el agente la usa. Ciclo de `docs/03-plan-de-forja-de-skills.md` §2: arranque → pulido → retro → forja → evals → congelar → corrida en sombra. Máximo **3 sesiones de 60–90 min** (spec §10.2); si el DoD no cierra, queda `0.9` con la deuda escrita.

## 1. Cómo correrla a mano

1. En la pestaña Code, abre `<carpeta del proyecto>`, pega el prefijo de contexto de `docs/03` §2.1 y el prompt de arranque de `departamentos/07-creativos.md` §10.1, con una **oferta real** (no el ejemplo del video). Pide al agente `d6-maker` que use la skill.
2. **Fase 1 (sin créditos):** brief, matriz, guiones, copies, fuentes y `linguistico.json`; corre `validar_d6.py nmax` y `matriz`; pide el QA-A (`d6-qa`, contexto limpio). **Tú apruebas el texto.**
3. **Fase 2 (solo tras tu aprobación y la del costo):** estáticos con `render_estatico.py` (Ruta A); si hay Higgsfield, cotiza, mira el total, **aprueba tú en el chat** y empieza por 1 clip por concepto. `validar_d6.py assets` y `todo`; QA-B; X1.
4. Para cada defecto que encuentres, **no lo corrijas en silencio**: dile al agente qué corregir y por qué (la bitácora sale de esas correcciones).

## 2. Qué mirar (preguntas de la spec §10.2 y las nuestras)

- ¿El hook se entiende en 3 s **y sin sonido**? ¿Muestra el entregable o una situación, y no una promesa?
- ¿Suena a nativo o a traducción? ¿El humor, el ritmo y el registro son del país? (sin revisor nativo, J11: lo juzgan las 5 capas; tu lectura cuenta como dato)
- ¿Promete algo que el producto no da, o algo sobre el cuerpo, el dinero o la pareja del lector? ¿Hay un atributo del lector, aunque sea en pregunta?
- ¿Qué haría rechazar este anuncio a Meta? ¿Qué diría el revisor de políticas simulado?
- ¿Los conceptos son realmente distintos (ángulo, hipótesis)? ¿Cada anuncio prueba una hipótesis medible?
- ¿El precio, la moneda y la promesa coinciden con la landing? ¿El texto de la pieza es el de `copies.json`?
- ¿Cuánto costó cada pieza? ¿La Ruta A basta? ¿La Ruta B valió el costo?
- ¿Los estáticos se ven bien en el móvil y respetan la zona segura? ¿Te gusta el estilo visual (marca de D5)?
- ¿Qué tuviste que editar? (cada edición es una observación)

## 3. Qué anotar en la bitácora `Pulido` del panel (una línea por observación)

Formato (de `docs/03` §2.2): `n.º | archivo y sección | antes → después | categoría | mi motivo con mis palabras`. Categorías: **`[error]`** hecho o cálculo mal · **`[regla]`** criterio que quiero siempre · **`[pref]`** gusto mío (va a un perfil del dueño, no a la skill) · **`[riesgo]`** política/legal/dinero · **`[contexto]`** solo vale para este caso. Anota además por corrida: oferta y `locale`, ruta usada, créditos reales por tipo de pieza, nº de piezas editadas sobre el total (para `origen_version`), rondas Maker↔QA, qué QA-A detectó y qué se le escapó, y las frases que X1 o tú rechazaste (pasan a `references/lista-rojo-amarillo.md` y a un caso de `evals/sembrados/`).

**Regla de pulido:** una regla nueva se escribe en la skill solo si tiene ≥2 evidencias, salvo `[riesgo]` (basta una). Cada corrección pasa a **regla** de la skill y cada defecto a **caso** del QA (`evals/`). Un cambio de skill vuelve a correr los evals.

## 4. Auditoría por excepción (spec §7: gate S)

Hasta N1 revisas **cada pieza**. En N2 revisas por excepción: notas o FAIL del QA, **amarillo** (RHS por cada ángulo nuevo), **primer lanzamiento de cada idioma × macro-nicho** (gate H de M1) y muestreo. Ascender de nivel exige: N2 → ≥10 paquetes con ≥80 % aprobados sin edición; N3 → 3 ofertas seguidas con ≥85 % sin edición, 0 rechazos atribuibles a D6, QA ≥90 % de sembrados y 0 falsos verdes.

## 5. Checklist de paso de 0.1 a 1.0.0

Marca cada casilla con evidencia (ruta o enlace). Hasta que todas estén marcadas, el frontmatter dice «v0.1 sin pulir» y el runner **no** la promueve.

- [ ] `SKILL.md` < 500 líneas, `description` < 1.024 caracteres (cuándo se usa **y** cuándo no), frontmatter YAML válido, `disable-model-invocation: true`.
- [ ] `references/` completas y sin `[PENDIENTE]` que bloqueen una corrida real (cada pendiente tiene dueño en `dependencias.md`); archivos citados existentes.
- [ ] `rubric.md` con anclas 1/3/5 y evidencia obligatoria; calibrada con los evals.
- [ ] `evals/` con ≥6 casos del maker (los 10 de la spec §10.5), **≥2 de otro nicho y de otro idioma** (hoy: e01–e10 en es-AR, es-ES, en-US, it-IT, pl-PL), dorados del QA en PASS (0 falsos bloqueos) y ≥ `creativos.calibracion_bloqueantes_sembrados_min` bloqueantes sembrados en ≥4 idiomas detectados ≥90 %; rotar el juego de sembrados para que no se memorice.
- [ ] `.claude/agents/d6-maker.md` y `d6-qa.md` con herramientas mínimas (QA solo `Read`, `Grep`, `Glob`); lista de comandos permitidos de los hooks actualizada (`dependencias.md` §4).
- [ ] **Una corrida manual real** en la pestaña Code con una oferta real, con retro de 30–45 min (`docs/03` §2.3) y las ediciones registradas en la bitácora.
- [ ] **DoD de `docs/03` §2.6 firmado por el dueño** (contrato 100 % válido; determinismo de los scripts; evals con skill > sin skill; estabilidad en 2 de 3 corridas; QA calibrado; tu aceptación en sombra de ≥2 de 3 casos sin edición sustantiva).
- [ ] **DoD de la spec §10.4:** 3 paquetes de **3 macro-nichos y 2 idiomas** pasan QA con ≤15 % de piezas editadas; QA ≥90 % de bloqueantes sembrados, 0 falsos bloqueos, **0 falsos verdes**; el lint cubre el ROJO de `05-legal.md` §10 y las listas de cada idioma; las 5 capas automáticas de idioma pasaron (sin revisor nativo, J11); **costo por pieza medido**; el dueño aprobó el estilo visual.
- [ ] Registro en `CHANGELOG.md` (versión, fecha, qué corrida lo respalda, qué falta); `skills_pin` actualizado por O0.

## 6. Qué mirar primero (orden sugerido para la primera sesión)

1. Los `[PENDIENTE]` que te bloquean: `limites.yaml` (créditos, `locales_permitidos`, `politica_divulgacion_ia`), glosario y lista de términos del idioma, las 5 capas de idioma (J11: sin revisor nativo).
2. Un estático de punta a punta con `render_estatico.py` (marca, zona segura, texto fiel).
3. Los hooks: ¿se entienden en 3 s y sin sonido, y son de **tercera persona** sin perder fuerza?
4. Qué dice `lint_claims.py` y qué se le escapa en tu idioma.
5. Cuánto del paquete tuviste que editar.

## 7. Qué mirar de lo nuevo en 0.2.0

1. `qc6.py lote` sobre tus piezas: ¿qué marcó `revisar` que no era? ¿qué se le escapó? Cada falso positivo o negativo pasa a un caso de `tests/creativos/test_qc6.py` y, si es de promesas, a `scripts/qc6_reglas.py`.
2. `ganchos.py estadisticas`: ¿hay un hook_tipo o ángulo que ya probaste dos veces?
3. La primera **tanda** (`modo-tanda.md`): ¿5-10 piezas por día te alcanzan o te sobran? ¿qué régimen de aprobación prefieres (A o B)?
4. ¿Cuántos ganchos del dossier tuviste que reencuadrar por atributo del espectador?
