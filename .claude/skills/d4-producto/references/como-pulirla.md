# Cómo pulirla (para el dueño)

> v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min). Método: «a mano → pulir → skill → el agente la usa» (backbone decisión 5; `docs/03-plan-de-forja-de-skills.md` §2). **2-3 sesiones de ≤ 90 min.**

## 1. Corrida a mano (qué hacer)
1. Elige una oferta real aprobada por D3 (o `ofertas/_ejemplo` como práctica) y arranca la sesión con `d4-maker` (o con el prompt §10.1 de la spec, que la skill reemplaza).
2. Deja que corra el SOP **sin ayudarlo**; anota dónde se atasca, dónde adivina y qué te sorprende.
3. Usa el producto como tu cliente: **tacha toda página que no mapee a una promesa**; **ejecuta el método con cronómetro** (la desviación > 25 % del primer paso = promete de más); **abre el PDF en el celular**; **verifica 10 afirmaciones contra su fuente** abriendo el enlace; **prueba si un chatbot con un prompt simple daría lo mismo**; en otro idioma, que lo lea un nativo **antes** de congelar el glosario.
4. Corre `d4-qa` en contexto limpio y compara con tu juicio: ¿vio lo que tú viste? ¿marcó falsos positivos?
5. Toda corrección que repitas pasa a la skill (o a un script).

## 2. Qué mirar primero
- **Matriz:** `cobertura_matriz.py` en verde; ninguna promesa sin prueba, ningún ítem sin promesa; bump separable.
- **Tiempo:** `tiempo_total.py` y tu cronometraje del primer paso; si el Maker «ajustó» los minutos para que entren, es defecto.
- **Respaldo:** 5 hechos a mano; que las cifras con unidad (cucharada/cucharadita, separadores del locale) coincidan con la fuente.
- **Anti-copia:** `similitud_ngrama.py` + 10 frases que buscas tú en la web (ningún agente navega); ¿la anatomía es de otro producto y el contenido tuyo?
- **Seguridad:** RHS si es amarillo-a; ayuda literal del país; «cuándo parar» concreto; ningún aviso que contradiga un claim.
- **Render:** PDF por la ruta A (¿se ve igual en el móvil?, ¿`lang` y `title` correctos?).
- **Costo:** D4 no gasta créditos (sin Higgsfield); ¿el producto aguanta solo con texto y capturas del render?

## 3. Qué anotar en la bitácora del panel (`Pulido`) y en `forja/d4/ediciones.md` (se crea al anotar la primera edición)
Una línea por edición tuya: `n.º | archivo y sección | antes → después | categoría | tu motivo con tus palabras`. Categorías: **[error]** hecho o cálculo mal · **[regla]** criterio que quieres siempre · **[pref]** gusto tuyo (va a tu perfil, no a la skill) · **[riesgo]** política/dinero/seguridad · **[contexto]** solo vale para este caso. Además: tiempo real vs prometido, cuántas ediciones MAYORES, cuáles escaparon al QA, falsos positivos de `lint_contenido.py` (para afinar `_patrones.py` o pedir `terminos_sensibles`), frases que el QA no entendió, y cualquier paso que el Maker no supo hacer (herramienta que falta).

## 4. Retro (30-45 min, el mismo día)
Con `ediciones.md` y el `diff` entre lo del Maker y lo final: ediciones por categoría y % del producto modificado; reglas candidatas (con evidencia y contraejemplo; descartar las de una sola evidencia salvo [riesgo]); checks L1 que un script habría atrapado; tu criterio implícito reescrito como ítems de rúbrica 0-5; 2 dorados y ≥ 10 sembrados nuevos. Solo pasan a la skill las reglas que tildes ✔.

## 5. Criterio de «lista para 1.0.0» (DoD §10.4 de la spec)
- Tres productos aprobados por ti en ≤ 1 ronda de ediciones menores: **dos de macro-nichos distintos (uno sin GUI) y una variante del mismo concepto en otro idioma** (oferta nueva con `variante_de`).
- QA: ≥ 9 de 10 bloqueantes sembrados y PASS a los dorados.
- Cold run de agentes exitoso y tiempo humano (medido en ≥ 1) en tolerancia; retraducción de la variante sin discrepancias de sentido.
- Lint sin intervención; `validar_esquemas oferta` limpio; checklist ≤ 10 min; costo bajo `costo_max_producto`.

## 6. Checklist de paso de 0.1 a 1.0.0
☐ `SKILL.md`, `references/`, `rubric.md`, `templates/` y `scripts/` revisados y pulidos con las ediciones de la corrida manual (ninguna sección «por escribir»; `SKILL.md` < 500 líneas; `description` < 1.024).
☐ `evals/` con los casos de la spec §10.5 **y ≥ 2 casos de otro nicho y otro idioma** (ya hay dorados en salud, relaciones y dinero; italiano y polaco); **con skill > sin skill** en cada uno, en Sonnet y en Haiku (se documenta si Haiku queda debajo).
☐ `d4-maker` y `d4-qa` con **herramientas mínimas** (QA solo lectura) y probados con el runner (`agentes.runner`, modo `fixture` y luego vivo).
☐ **Una corrida manual del dueño con una oferta real** y retro de 30-45 min hecha.
☐ **DoD de `docs/03-plan-de-forja-de-skills.md` §2.6 firmado** (contrato, determinismo, evals, estabilidad 3 corridas ≥ 2 iguales, QA calibrado, aceptación en sombra, forma, seguridad con inyección, costo, sin sobreajuste; **cumplimiento** no aplica a D4 salvo el eje C): los innegociables son 1, 2, 5 y 8.
☐ Pendientes de `references/dependencias.md` cerrados o aceptados por escrito (render PDF A/B/C operativo y probado con contraste/metadatos; cold run cronometrado humano medido en ≥ 1; `terminos_sensibles` y `ayuda_por_pais.yaml` de X1; glosarios de M1; `l1_d4`, `capturar_fuente` y rol `novato` del runner; `scripts.nivel_riesgo` ya existe).
☐ **`CHANGELOG.md`** registra **qué corrida respaldó la versión** (oferta, fecha, ediciones, retro) y los `[PENDIENTE]` que quedan.
☐ Tag `skill/d4-producto/v1.0.0` y la etapa D4 en N1 en `empresa/autonomia.yaml` (solo tú, con PR aprobado).
Si fallan solo ítems no innegociables: `v0.9` con la deuda escrita en `CHANGELOG.md`.

## 7. Calibración del QA (cada vez que cambie la skill del QA, el modelo o las políticas)
Dorados en PASS (≥ 2 por macro-nicho, ≥ 1 en otro idioma); ≥ 10 sembrados rotados (`evals/sembrados/rotacion.json`), ≥ 90 % detectados y 100 % de S1, S6, S10, S11; casos C de `casos-frontera.yaml` sin falsos verdes y negativa ante C3. Registra n y resultado en `CHANGELOG.md`.
