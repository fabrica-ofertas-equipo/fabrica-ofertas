# 03 · Plan de forja de skills: método, orden, fases y presupuesto del primer test

> Para: el dueño. Fecha: 2026-11-06. Versión 2 (adaptada al radar continuo de D1, al filtro mecanismo único + entregable único y al marco de los 3 grandes nichos). Subordinado a `docs/_backbone.md` (v2.2): si algo choca, prevalece el backbone; por debajo mandan los contratos y el código (`docs/contratos.md`, `contratos/`, `empresa/{limites,parametros}.yaml`, `engine/`).
> Etiquetas: `[DUEÑO]` decisión tuya · `[NUEVO]` aporte nuestro · `[HIPÓTESIS]` número o regla a calibrar · `[VERIFICAR]` hecho externo sin confirmar · `[SUPUESTO]` dato asumido · `[CREADORES]` afirmación de vendedores de cursos (no es evidencia).
> Insumos: backbone v2.2; sección 10 de las especificaciones; `01-claude-code-runtime`; `03-stripe`; `07e`–`07h`; `08-mercados-ranking`; `18a`–`21` (fuentes, MU/EU, legal de recolección); `25-marco-salud-relaciones-dinero` (§8-§13); `00-decisiones-y-tareas-del-dueno`; `w1-pendientes`; `departamentos/16-mercados-localizacion.md` y `docs/contratos.md` (ya existen). **No existía** (verificado el 2026-11-06 a las 09:40; a las ~10:50 la reescritura v2-radar de `departamentos/02-descubrimiento.md` y `docs/_historial/d1-v2-interfaces.md` ya figuran en el árbol y hay que contrastar este plan con ellas): el resumen del piloto del radar (`docs/_historial/d1-v2-piloto/_resumen.md`), que sigue sin existir. Por eso la sección de D1 de este plan (§2.8) se deriva del backbone §3.2/§5.11, de las notas 18-21 y 25 y de los parámetros `descubrimiento.*` ya existentes, y se marca `[SUPUESTO]`: cuando aparezca la sección 10 de la v2 de D1, manda ella. Documentos hermanos: `docs/04-datos-kpis-dashboard.md` (KPIs del Radar) y `docs/05-riesgos-guardarrailes.md` (riesgos y guardarraíles). Foco vigente del dueño: las **bases del testeo** (`docs/06-bases-del-testeo.md`); el radar queda fuera de ese plano.

---

## 0. En una página

1. **Tu método es correcto en el fondo** (hacer a mano, pulir, forjar skill, recién entonces el agente): una skill es criterio destilado y solo vos lo tenés. Pero **mezcla dos tipos de trabajo** que no se forjan igual: *criterio* (D1–D7, X1, M1: forja manual) e *ingeniería* (D0, O0, F1, F2, hooks, webhooks, ETL, reglas de kill/escala: software con tests; la skill es solo el manual de uso). Dos vías en paralelo.
2. **Ajuste principal:** no forjar 17 skills en fila. Primero un **esqueleto caminante** (Fase 1): una oferta real recorriendo todo el flujo con versiones mínimas, medición completa y gasto acotado. Las skills **v0.1** de cada agente ya no esperan a la oferta #2: por orden del dueño (2026-11-06) las forja S-C **ahora, desde las especificaciones**, con el frontmatter «v0.1 sin pulir». Vos las pulís corriendo cada paso a mano en la pestaña Code (ciclo de §2) con la oferta #1; una skill pasa a **v1.0 solo con la corrida manual real, la retro y el DoD firmados** (§2.6, con registro de la promoción), y el runner nunca promueve una v0.1 a ejecución desatendida. La forja formal de D1 → D7 con una segunda oferta distinta (Fase 2) sigue siendo la prueba de generalización, y la primera queda como caso de regresión.
3. **Oferta #1:** ya no es «manualidades». Toda oferta encuadra en **salud, relaciones o dinero** (decisión 13) y sale de un **candidato verde** (o amarillo-A con revisión) del banco de D1, con demanda y encaje de mercado; nadie te pasa una lista de problemas ni elegís el tema por afinidad. Recomendación de partida de la nota 25 §8.2, **condicionada** a su paso 0 y a lo que muestre el primer barrido: *presupuesto-por-cobro* (dinero, verde, mecanismo de cálculo) como hipótesis de oferta, a probar **en un solo mercado a la vez**: el plan no fija un mercado ni un par de arranque, y `empresa/parametros.yaml` limita los tests en paralelo (`mercados_test_paralelos_max` = 1; comparar dos mercados a la vez exigiría subirlo a 2, decisión del dueño). **El primer mercado y la primera oferta los decidís vos `[DUEÑO]`**, con la propuesta de M1 (ranking sin criterio de pagos, `scripts/mercados/rank_sin_pagos.py`, y cobertura de pago real). Italia y Polonia son **hipótesis a contrastar con datos propios**, no un prior ni un par en paralelo; con los pagos diferidos (solo tarjeta y billeteras) Polonia no pasa la regla R6 de M1 (cobertura ≈ 17 % frente a un mínimo duro de 40 %) y se evalúa solo si habilitás métodos locales. Pasos posteriores (un verde de salud, uno de relaciones) salen del banco y del mercado que decidas, no de una lista fija. «Ganar dinero con manualidades» queda como candidato válido de dinero (versión segura: «costeo y precio mínimo»); manualidades como pasatiempo puro queda fuera del marco.
4. **Tu tiempo:** las especificaciones suman ≈ 85 h de pulido (suma de los máximos de su §10.2) más ≈ 5 h de M1 `[HIPÓTESIS]`, y **D1 se forja por familias de fuentes y no de una vez** (§2.8: ≈ 12–18 h hasta N1 con el primer barrido manual, más ≈ 6–8 h por familia posterior `[HIPÓTESIS]`). Con 15 h/semana `[SUPUESTO]` esas horas son el insumo de la estimación, no una promesa de plazo: **este plan no promete meses**. El **tope práctico es N2 (el botón)** mientras D1, D2 y D6 dependan de conectores que solo existen en sesión interactiva; para N3/N4 hace falta una alternativa por API (p. ej. la API oficial de la Biblioteca de anuncios, que exige verificación de identidad del dueño `[DUEÑO]`, y la de Higgsfield si existe `[VERIFICAR]`), y además los criterios de ascenso exigen volumen (§7). El **hito siguiente es el primer test en vivo**, que depende de las decisiones del dueño (`docs/00` §0) y del Hito B0 (`docs/_historial/bases-plan-de-construccion.md`). Toda estimación temporal de este plan (duraciones de §4, horas de §5) es `[HIPÓTESIS]`.
5. **Primer test:** ≈ 170–225 USD de anuncios en el mercado que elijas (un mercado a la vez; 340–450 USD solo si más adelante se corre un segundo mercado en serie o se sube `mercados_test_paralelos_max`) más costos fijos a cotizar, **como propuesta de arranque**: la pérdida máxima por oferta **no está fijada** (la difirió el dueño) y mientras valga `null` ningún script gasta ni activa. Con ~600 clics en el mercado se puede **descartar** una oferta; no se puede **validarla** (§6).
6. **Lo que más puede frenar:** régimen fiscal (Managed Payments vs. IVA propio; decide si existen BLIK y Przelewy24), revisores nativos, el calendario (Black Friday y Navidad) y, sobre todo, **las políticas de Meta y Stripe sobre la única cuenta de cada una**: perder cualquiera es un riesgo existencial, no un costo (§0 bis).

**0 bis. Cumplimiento como diseño.** Salud, relaciones y dinero son los nichos que más vigilan Meta y Stripe, y de **una** cuenta de cada una cuelga todo. El plan lo trata así: el riesgo se evalúa **por candidato** (promesa, contenido, encuadre, categoría de negocio; tabla única de `scripts/nivel_riesgo.py`), ningún tema se excluye por sí mismo (una «cura» es rojo; una guía de reinserción laboral para madres tras el embarazo, verde), el mecanismo único nunca es un claim de salud ni de ingresos, X1 veta en cualquier etapa, y la Fase 0 incluye el plan B de pagos y cuentas (§4.1) y las reservas (§6.4).

---

## 1. Veredicto sobre el método y ajustes recomendados

### 1.1 Qué está bien `[DUEÑO]`

La skill nace de un trabajo hecho y corregido por vos, no de una especificación abstracta; coincide con la guía de Anthropic (medir qué falla *sin* skill, tres escenarios, instrucciones mínimas; `01-claude-code-runtime` §1). La pestaña Code comparte skills, hooks y settings con la CLI, así que lo forjado ahí corre después desatendido. Maker y QA independientes con gates es el patrón evaluador-optimizador de Anthropic.

### 1.2 Dónde se rompe si se aplica tal cual

| Riesgo | Por qué | Efecto |
|---|---|---|
| Waterfall de 17 skills | Cada una se pule contra su especificación, no contra el flujo | Integración tardía; `w1-pendientes` ya lista choques (campos de `limites.yaml`, 48 h vs 72 h entre aumentos, "validada") |
| Forjar sin datos de mercado | D8, D9, X2 y el afinado de D1/D3 necesitan campañas reales | Umbrales inventados |
| Todo como skill | Kill, escala, presupuesto, linters y guardarraíles deben ser código (backbone §5.6) | Un LLM decidiendo dinero |
| Sobreajuste | Un nicho, un idioma, una oferta | Skill buena para su caso y floja en el siguiente |
| Evals ≠ mercado | Pasar evals prueba que la skill sigue la rúbrica, no que la oferta venda | Falsa confianza |

### 1.3 Ajustes

| # | Ajuste | Por qué | Cómo |
|---|---|---|---|
| A1 | **Dos vías**: criterio (forja manual) e ingeniería (software con tests) | Lo determinista se programa. Las especificaciones traen vectores numéricos como tests (D2: 0,233 y 0,675; D7: 192 USD y 19,2/día; O0 §3.4) | Claude Code como programación en pareja; la skill de D0/O0/F1/F2 es un manual corto que invoca scripts |
| A2 | **Esqueleto caminante** con una oferta real antes de pulir | Expone fricciones entre etapas cuando arreglarlas cuesta horas | Fase 1: versiones mínimas, retro ligera por etapa, ninguna skill "terminada" |
| A3 | **Contratos primero** | Lo que viaja entre agentes es JSON; cambiarlo después obliga a re-forjar | `contratos.md` → `contratos/*.schema.json` + `taxonomia.yaml` + `validar_esquemas.py` en CI; v0 en Fase 0, v1 al cerrar Fase 1 |
| A4 | **Medición antes que gasto** | Sin tracking ni conciliación, 400 USD no enseñan nada | Ninguna campaña sin los 4 primeros tramos de §6.3 |
| A5 | **Skill = playbook + rúbrica + ejemplos + evals** (+ scripts) | Es la estructura de §10.3 de cada especificación; sin uno de los cuatro no se puede probar ni calibrar | Plantilla única (§2.5) |
| A6 | **Capturar tu criterio** | Es el activo que se está construyendo | Commit por tanda de correcciones etiquetado `[error]` `[regla]` `[pref]` `[riesgo]` `[contexto]` + `forja/<id>/ediciones.md`; coincide con `origen_version` (backbone §5.1) y las categorías de X2 |
| A7 | **Límites de tiempo** | Previene el perfeccionismo | Máximo 3 sesiones y el tope de §10.2. Si el DoD no cierra: `v0.9` con deuda escrita y volver con datos. Cuatro ítems innegociables (§2.6) |
| A8 | **2–3 casos de nichos e idiomas distintos por skill** | Evita sobreajuste; las especificaciones lo piden en §10.5 | Caso 1 = #1 en polaco; 2 = #1 en italiano; 3 = oferta #2; 4 = sintético sin gasto. Reemplaza los ejemplos que asumen español |
| A9 | **Eval primero** | Sin esto cada pulido rompe lo anterior | Todo cambio de skill nace como caso nuevo en `evals/` |
| A10 | **Punto de continuidad** tras la Fase 2 | No invertir en QA y escalado de un modelo que no vende | §4.3 |
| A11 | **D1 no se forja de una vez: se forja por familias de fuentes, empezando por un primer barrido manual** `[NUEVO]` | D1 es un proceso continuo (barridos + banco), no un artefacto por oferta; sus fuentes tienen colores legales y niveles distintos (nota 21 §9.4) y cada familia se pule con su propio criterio | §2.8 |
| A12 | **El riesgo por candidato se forja contra una suite, no contra sensaciones** `[NUEVO]` | El clasificador de D1 y los lints de X1 solo valen si dan 0 falsos verdes en un conjunto de retención que ellos no ven (nota 25 §11) | `casos-frontera.yaml` como eval de D1, D3, D6 y X1 (§2.5, §2.8) |
| A13 | **Filtro MU/EU antes que pulido** `[NUEVO]` | Un problema sin mecanismo único ni entregable único no llega a candidato; pulir el resto de la cadena sobre un candidato malo es el desperdicio más caro | Prueba de una frase (backbone §5.11) como puerta en D1 y rúbrica en D1-QA, D2, D3 y D4 (§2.8) |

---

## 2. El ciclo de forja por departamento

**arranque → pulido → retro → forja → evals → congelar → corrida en sombra.** Típico por skill: 2–4 semanas y 8–12 h tuyas (tope en §10.2 de cada especificación).

`[NUEVO]` Desde la orden del 2026-11-06 cada agente ya tiene una skill **v0.1 sin pulir** (la forja S-C desde la especificación, en `.claude/skills/`): el paso «forja» no parte de una carpeta vacía, sino que lleva esa v0.1 a v1.0 con lo que enseñaron tu pulido y la retro (si el prompt de §2.4 dice «construí», leelo como «actualizá la v0.1 existente»). La promoción y su registro están en §2.6.

**Preparación (15 min).** `git checkout -b forja/<id>` (p. ej. `d3`); elegí el **caso** (oferta, `locale`, moneda, pagos); abrí la especificación (§3.3, §6, §10); anotá la hora en `forja/<id>/horas.md`.

### 2.1 Arranque (Maker v1)

Pegá este prefijo **antes** del prompt de §10.1 de la especificación (los prompts v1 asumen un mercado hispanohablante):

```
CONTEXTO V2.2 (prevalece sobre cualquier supuesto del prompt que sigue). Leé primero <carpeta del proyecto>/docs/_backbone.md (v2.2: §3.1, §3.2, §5.11, decisiones 12 y 13), docs/contratos.md y docs/_investigacion/25-marco-salud-relaciones-dinero.md (§1-§2 y §10-§13). El sistema es GLOBAL: una oferta = un concepto en un idioma y un clúster de mercados (backbone §3.1). Si el prompt asume un solo mercado o español, reemplazalo por el caso de esta sesión. Toda oferta encuadra en SALUD, RELACIONES o DINERO (por el deseo central del problema); el riesgo se evalúa POR CANDIDATO (promesa, contenido, encuadre, categoría de negocio) y ningún tema se excluye por sí mismo; el mecanismo único nunca es un claim de salud ni de ingresos. El problema sale del banco de D1 (empresa/descubrimiento/), nunca de una lista del dueño, y debe pasar el filtro mecanismo único + entregable único (§5.11). Ignorá del prompt v1 cualquier mención a `exclusiones`, `tolerancia_politicas`, `riesgo_politicas` o nichos prohibidos por tema.
CASO: oferta_id=<OF-AAAAMM-NN>, familia_id=<FAM-…>, problema_id=<PRB-AAAAMM-NNNN>, macro_nicho=<salud | relaciones | dinero>, nivel de riesgo del candidato=<verde | amarillo-A | …>, locale=<pl-PL | it-IT | …>, moneda=<PLN | EUR | …>, métodos de pago=<…>, país=<…>. Entradas reales en ofertas/<oferta_id>/ (y, para D1, en empresa/descubrimiento/).
MODO: ejecutá el trabajo del departamento sobre ESTE caso y entregá el v1 del artefacto en el contrato de su §3.3. No generes todavía la skill. Marcá origen_version=maker. No uses el nicho del video salvo como eval.
PRIMERO: PREGUNTAS BLOQUEANTES (máx. 8) y esperá mi respuesta.
LÍMITES: sesión de <90> min. Ninguna herramienta con efecto externo (crear, activar, publicar, subir, generar, gastar, enviar) sin mi autorización explícita en el chat. No pidas ni escribas claves.
```

Al terminar: `git commit -m "maker-v1 <id> <oferta_id>"` y `git tag maker/<id>/<oferta_id>`.

### 2.2 Pulido (vos)

Usá el resultado como lo usaría tu cliente: la landing en tu celular, el método con cronómetro, cada cita abriendo el enlace. Las preguntas de criterio están en §10.2 de la especificación. **≤ 3 sesiones**, cada una con hora de fin.

```
MODO PULIDO. Yo corrijo este artefacto; vos aplicás y registrás. Por cada corrección: (1) aplicala exactamente; (2) si no te dije la categoría, preguntame UNA vez: [error] hecho o cálculo mal, [regla] criterio que quiero siempre, [pref] gusto mío, [riesgo] política/legal/dinero, [contexto] solo vale para este caso; (3) agregá una línea a forja/<id>/ediciones.md: n.º | archivo y sección | antes → después | categoría | mi motivo con mis palabras. No generalices, no propongas reglas, no toques nada que no te pida. Cuando diga "cerrar sesión": resumí las ediciones por categoría y listá las preguntas de criterio que respondí.
```

Commit al cerrar cada sesión (`pulido d3 s2: [regla]x4 [pref]x2`). Versión buena: `git tag final/<id>/<oferta_id>`.

### 2.3 Retro (30–45 min, el mismo día)

```
MODO RETRO para <id>. Leé: forja/<id>/ediciones.md, `git diff maker/<id>/<oferta_id> final/<id>/<oferta_id>`, los qa/*.json si existen y departamentos/<NN>-<slug>.md §3 a §6. NO leas ninguna skill existente. Producí forja/<id>/retro.md (máx. 2 páginas más anexos):
1. Ediciones por categoría y % del artefacto modificado.
2. REGLAS candidatas: enunciado verificable, evidencia (n.º de edición), contraejemplo posible, y si valen para cualquier nicho/idioma o solo para este caso. Descartá las de una sola evidencia, salvo [riesgo]. Cada una con ☐.
3. PREFERENCIAS mías: van a perfil_dueno.md, no a la skill.
4. Errores que un script habría detectado: checks L1 propuestos (nombre, entrada, condición, fallo).
5. Mi criterio implícito: las preguntas que te respondí, reescritas como ítems de rúbrica 0–5 con anclas 1/3/5.
6. Ejemplos: 2 dorados (lo aprobado) y ≥ 10 defectos sembrados con severidad.
7. Qué sigue ambiguo: máx. 5 preguntas.
Citá mis palabras textuales. No inventes motivos: toda inferencia va como [HIPÓTESIS].
```

Vos tildás ✔ las reglas; solo esas pasan a la forja.

### 2.4 Forja (skill-creator)

Antes, verificá en tu Code: `/plugin`; si falta, `/plugin install skill-creator@claude-plugins-official` (`01-claude-code-runtime` §1; `[VERIFICAR]` que coincide con la versión de GitHub leída el 2026-11-05).

```
MODO FORJA para <id>. Si skill-creator está disponible, usala (/skill-creator); si no, seguí este mismo proceso a mano.
ENTRADAS: forja/<id>/retro.md (solo reglas con ✔), departamentos/<NN>-<slug>.md §3.3 a §6 y §10.3 a §10.5, los artefactos dorados, contratos/*.schema.json.
CONSTRUÍ en la rama forja/<id> (nunca en main) .claude/skills/<slug>/ con:
- SKILL.md < 500 líneas; description < 1.024 caracteres (cuándo se usa y cuándo NO). Si mueve dinero, publica o activa: disable-model-invocation: true.
- references/ a un solo nivel; templates/; rubric.md (ítems del retro §5, evidencia obligatoria por ítem).
- scripts/ para todo lo determinista, con tests que reproduzcan los ejemplos numéricos de la especificación.
- evals/evals.json: los casos de §10.5 + ≥ 1 de otro nicho + ≥ 1 de otro idioma (pl-PL, it-IT u otro); sin aserciones al principio.
PROCESO: corré cada caso CON la skill y SIN ella (línea base); recién entonces redactá aserciones discriminantes; benchmark (aciertos, tiempo, tokens) en Sonnet y en Haiku. No optimices la description hasta que la skill funcione. Sin ejemplos del nicho del video ni de un solo idioma.
NO TOQUES .claude/settings.json, empresa/limites.yaml ni contratos/**.
CIERRE: CHANGELOG.md (0.1.0), lo que la skill NO cubre, y el DoD de §10.4 ítem por ítem (cumple / no / cómo se mide). Nada es "cumple" sin evidencia reproducible.
```

`[NUEVO]` La optimización de la `description` (20 consultas, partición 60/40, hasta 5 iteraciones) solo importa para skills que se activan por coincidencia; las que invoca el orquestador por nombre o precarga un subagente no dependen de ella.

### 2.5 Evals y calibración del QA

1. Evals de la skill del Maker, con vs. sin skill, en Sonnet y Haiku: con skill debe superar la línea base en cada caso. Si Haiku queda por debajo, se documenta.
2. **Calibrar el QA de la misma etapa** (backbone §6.6): dorados en PASS, ≥ 90 % de bloqueantes sembrados detectados, juego de sembrados *rotado* para que no se memorice.
3. **Skills que clasifican riesgo (D1, D3, D6, X1)** `[NUEVO]`: además se miden contra la suite `casos-frontera.yaml` (hoy en `docs/_historial/hwr-semillas/`; ruta definitiva pendiente): **falsos negativos peligrosos = 0**, ejes y nivel por analogía con las anclas de la nota 25 §11, y el **clasificador contra un conjunto de retención** que la skill no ve (≥ 30 % de los casos, sellado por hash, anotado por dos personas): 0 falsos verdes en ≥ 60 positivos y cota superior ≤ 5 %; se informa siempre n y la cota. La aritmética nivel = f(ejes) no la hace el LLM: la hace `scripts/nivel_riesgo.py` (pendiente de implementar; hasta entonces la tabla de la nota 25 §2.3 se aplica a mano y se anota).

Carpeta idéntica para todos: `SKILL.md`, `references/`, `rubric.md`, `templates/`, `scripts/`, `evals/` (`dorados/`, `sembrados/`), `CHANGELOG.md`; agentes `<id>-maker.md` y `<id>-qa.md` con herramientas mínimas (QA solo lectura).

### 2.6 Definición de listo (DoD) medible para congelar `v1.0.0`

| # | Criterio | Medida | Innegociable |
|---|---|---|---|
| 1 | Contrato | Salida válida contra su esquema en el 100 % de las corridas | Sí |
| 2 | Determinismo | Scripts con tests; ejemplos numéricos de la especificación con diferencia 0 | Sí |
| 3 | Evals | ≥ 6 casos (los de §10.5 + otro nicho + otro idioma); con skill > sin skill en cada uno | No |
| 4 | Estabilidad | 3 corridas del mismo caso: decisión clave igual en ≥ 2 de 3 | No |
| 5 | QA calibrado | 100 % de dorados en PASS, ≥ 90 % de bloqueantes sembrados, 0 falsos bloqueos | Sí |
| 6 | Tu aceptación | En sombra, aceptás ≥ 2 de 3 casos sin edición sustantiva `[HIPÓTESIS]` | No |
| 7 | Forma | `SKILL.md` < 500 líneas, `description` < 1.024 caracteres, referencias a un nivel; costo de contexto anotado (`/skill-doctor`) | No |
| 8 | Seguridad | Prueba de inyección (texto hostil en una fuente) pasa; sin secretos; acciones externas en `deny` o detrás de gate | Sí |
| 9 | Costo | Corrida dentro de `max_budget_por_corrida_agente`, registrada en `costos.jsonl` | No |
| 10 | Sin sobreajuste | Cero menciones del nicho del video; el caso de otro idioma pasa sin editar la skill entre casos | No |
| 11 | Cumplimiento (solo D1, D3, D6, X1) | 0 falsos verdes en retención (n y cota informados); ningún candidato ROJO sin reencuadre llega a `candidatos.json`; el mecanismo único no es un claim de salud ni de ingresos; X1 puede vetar | Sí |

Si se agota el tiempo y fallan solo ítems no innegociables: `v0.9` con la deuda en `CHANGELOG.md`. Congelar = PR aprobado por vos (CODEOWNERS), tag `skill/<slug>/v1.0.0`, etapa en N1 en `autonomia.yaml`. Después, los cambios solo entran por PR; en operación, solo el script de aplicación de X2 con tu aprobación (backbone §4).

**Registro de promoción v0.1 → v1.0 `[NUEVO]`** (orden del dueño, 2026-11-06). Las skills nacen como **v0.1** con el frontmatter «v0.1 sin pulir»: las forja S-C desde las especificaciones, antes de cualquier corrida real. Vos las pulís corriendo cada paso a mano en la pestaña Code (ciclo de §2) y una skill pasa a **v1.0 solo con la corrida manual real, la retro y el DoD firmados**. La promoción deja un registro con: versión, estado, la corrida manual que la respaldó (oferta y fecha) y el DoD firmado. El formato lo define S-C; hasta que exista, el registro va en el `CHANGELOG.md` de la skill `[SUPUESTO]`. El runner **no promueve una v0.1 a ejecución desatendida**: una skill sin ese registro solo corre asistida, en tu sesión.

### 2.7 Corrida en sombra

Con la skill congelada, un caso **nuevo**: vos a mano y el agente en paralelo, sin que veas su resultado hasta terminar.

```
MODO SOMBRA <id>. Ejecutá la skill <slug> v<x.y.z> sobre <oferta_id> en contexto limpio: primero <id>-maker y luego <id>-qa, SIN leer ofertas/<oferta_id>/humano/ (mi versión). Guardá todo en ofertas/<oferta_id>/sombra/. Comparalo con mi versión: diferencias por sección; cuáles cambiarían una decisión y cuáles son de forma; clasificá cada una [skill-falla | mi-error | pref | ambiguo]; calculá coincidencia (% de ítems de rúbrica con diferencia ≤ 1 punto); registrá tiempo, tokens y costo. Proponé hasta 3 cambios, cada uno como caso de eval nuevo. No modifiques la skill.
```

Dos sombras seguidas con coincidencia ≥ 80 % `[HIPÓTESIS]` y cero `[skill-falla]` BLOQUEANTE = etapa estable en N1 (D8 exige 7 días con ≥ 90 %, su §10.4).

### 2.8 Ciclo de forja de D1: primer barrido manual y familias de fuentes `[SUPUESTO hasta la v2 de D1]`

**Por qué D1 es distinto.** Las demás skills nacen de un artefacto que pasa por una oferta. D1 es un **proceso continuo** (barridos programados que mantienen un banco en `empresa/descubrimiento/`, backbone §3.2) y el botón solo elige de ese banco. Un `candidatos.json` de práctica no basta para forjarlo: hace falta haber barrido de verdad, con fuentes reales y su color legal. **Ya no existe la tarea «preparar una lista de problemas candidatos»**: ninguna etapa depende de ella; si tenés un tema donde sabés, entra como *semilla opcional* (una señal más, nunca evidencia).

**Orden de forja por familias (no de una vez).** Cada familia es una iteración del ciclo de §2.1–§2.7 con su propio pulido, retro y evals; el filtro MU/EU, el clasificador de riesgo y el banco se forjan en la primera y se reutilizan.

| Iteración | Familia de señales | Fuentes de arranque (colores de la nota 21 §9.4) | Por qué en este orden | Nivel legal de partida |
|---|---|---|---|---|
| **D1-a** | **Oferta persistente y pago** (¿alguien paga por vender/comprar algo parecido?) | `ads_library_search` (8 campos; V), el barrido por forma ya construido (`scripts/modelado/barrido/`), rankings públicos accesibles (p. ej. Amazon Best Sellers; la lectura humana de marketplaces es A) | Ya hay herramientas y código; no toca datos personales; sirve para calibrar MU/EU y la puerta «sustituto gratis». Mide persistencia, **no ingresos** | V + A humano |
| **D1-b** | **Dolor/deseo** (voz del cliente) | Foros y blogs independientes con `robots.txt` permisivo, reseñas de 2–3 estrellas (por `WebSearch` con `allowed_domains`), YouTube Data API con volumen bajo (A, ≤ 30 días) | Es la señal más rica por costo (18a) y la que el filtro de datos personales y el modo «solo agregado» deben proteger primero | V + A; **Reddit, X, Quora, Pinterest fuera** |
| **D1-c** | **Demanda** (¿lo buscan?) | Tendencias y autocompletado por idioma (índices relativos, nunca volumen absoluto), triangulación | Suma puntos y detecta falsos positivos; **nunca aprueba sola** (18c) | V |
| **D1-d** | **Señales propias** (comentarios de anuncios, soporte, reembolsos) | D8/D10 | Requiere campañas y clientes reales: llega con la Fase 4 | Datos propios |

**Primer barrido manual (N0): el ciclo de la iteración D1-a/b, en lugar del arranque de §2.1.** El dueño lo hace a mano en Code con el Maker de sesión; es el equivalente del «hacer el paso a mano» para un proceso continuo.

1. **Preparación (30 min).** `git checkout -b forja/d1`; elegí **1 macro-nicho** (empezá por el que menos riesgo de política tenga entre tus candidatos a oferta #1: dinero o relaciones con ángulo de herramienta) × **1 nicho** de `nichos-hwr.yaml` (18 nichos y 86 hojas, hoy en `docs/_historial/hwr-semillas/`; siembra `empresa/descubrimiento/nichos.yaml`) × **1 o 2 locales** que M1 declare activos (`locales_activos.yaml`; con el atlas sin cargar, `it-IT` y `pl-PL` según la hipótesis del plan, sin darlos por buenos). Anotá las horas en `forja/d1/horas.md`.
2. **Plan del barrido (15 min).** El Maker escribe el plan: términos por locale (de `terminos_busqueda/<locale>` si existe; si no, los del Maker marcados `[VERIFICAR]` hasta revisión nativa), fuentes y color, topes (`max_busquedas_por_barrido`, `max_costo_por_barrido`: aunque el barrido manual no los exija, usalos como tope de la sesión), qué NO se toca (fuentes rojas).
3. **Recolección (45–60 min).** Fuentes V con el Maker; fuentes A **vos, en tu navegador normal y a ritmo humano (N0), o el Maker solo con lo que pegás ya redactado (N1)**: nunca el navegador con tus cuentas de valor abiertas para automatizar. Cada señal: URL, fecha, `locale`, familia, extracto ≤ 25 palabras confirmado sobre el texto crudo (`WebFetch` solo ubica), sin nombres de usuario ni fotos.
4. **Problemas y fichas (45 min).** Del conjunto de señales salen problemas *en palabras del cliente*. Para cada uno: **prueba de una frase** («Para [audiencia] que [problema], [MU] es [EU] que lleva de [A] a [B] sin [obstáculo]»), ficha de MU (causa raíz, nombre de 2–6 palabras, diferencia frente al sustituto gratis y al chatbot, prueba lógica, riesgo de claim) y ficha de EU (formato, alcance cerrado, tiempo al primer resultado, producibilidad, licencias). Los que fallan se **rechazan con motivo canónico** (`sin_mecanismo`, `multi_mecanismo`, `requiere_servicio`, `sustituto_gratis_dominante`, `fuera_de_macro_nicho`, etc.) y con su redención.
5. **Riesgo por candidato (30 min).** Para cada sobreviviente, ejes **P, C, E, N** y nivel con la tabla de la nota 25 §2.3; si sale rojo, el Maker intenta el **reencuadre seguro** (máx. 2 intentos, catálogo de §4 de la nota 25) y conserva el deseo central. Resultado: `riesgo{P,C,E,N,nivel}`.
6. **Puntaje y banco (30 min).** Puntaje con los parámetros `descubrimiento.*` a mano mostrando las cuentas (el código `score.py`/`dedup.py` se pide después); los que pasan entran al **primer banco semilla** `empresa/descubrimiento/problemas/` (señales fuera de git).
7. **Candidatos de práctica (15 min).** Congelar un `candidatos.json` con top-N (≥ 60 % verdes si existen), validarlo contra `contratos/candidatos.schema.json` con el validador de esquemas del proyecto (`scripts/validar_esquemas.py`, que mantiene la otra sesión).
8. **Pulido (≤ 3 sesiones) y retro (§2.2–§2.3).** Mirá: ¿cada cita se reproduce abriendo el enlace? ¿el top-1 es una apuesta que harías? ¿qué MU suena a claim? ¿qué rojo se rechazó con razón y cuál por prudencia propia?

**Salida y criterio de cierre del primer barrido.** ≥ 15 señales citadas de ≥ 2 familias, ≥ 6 problemas fichados (MU+EU) con ≥ 3 rechazos con motivo, ≥ 3 candidatos con nivel de riesgo (≥ 1 verde en cada macro explorado) y un `candidatos.json` válido. Es `[HIPÓTESIS]`; sirve para sembrar el eval y el banco, no para decidir la oferta #1 todavía.

**Ciclos siguientes.** Repetí el ciclo por familia (D1-a → b → c), y por locale (un problema hallado en un idioma **no se asume válido en otro**: el traslado exige barrido local, backbone §3.2). Cada ciclo agrega evals (otro macro, otro idioma, una página con instrucciones inyectadas, una fuente roja que el Maker debe negarse a abrir, un candidato rojo con reencuadre y otro verde que un filtro por tema bloquearía) y sembrados (cita inventada, dato personal sin filtrar, MU que es claim de salud, EU que exige servicio, fuente con `Disallow`, ROJO sin reencuadre en el top-N).

**Métricas para subir de nivel D1** (valores `[HIPÓTESIS]`; los de la v1 de D1 se conservan y se completan):

| Salto | Métrica |
|---|---|
| N0 → N1 | DoD de §2.6 (incluido el ítem 11) en la familia en curso; 2 sombras con ≥ 80 % de coincidencia en el top-3; un barrido completo dentro del tope de costo |
| N1 → N2 | ≥ 80 % de candidatos aceptados sin edición en 5 corridas; QA de D1 calibrado (≥ 90 % de sembrados, dorados en PASS); **0 falsos verdes** del clasificador en la retención (n ≥ 60, cota ≤ 5 %); 100 % de citas reproducibles; 0 señales con datos personales; X1 ha sellado cada fuente (VC-01…16) |
| N2 → N3 | Tu elección ∈ top-3 en ≥ 80 % de ≥ 8 corridas; ≥ 1 oferta nacida del banco llegó a D7; checklist VC en verde y borrado verificado ≤ 7 días; aviso de investigación publicado (plantilla generada por el sistema; las 13 preguntas de la nota 21 quedan como puntos de riesgo residual sin dueño legal); APIs oficiales y claves propias listas; presupuesto del radar fijado. Elegir candidato sigue siendo **H hasta N3** (`contratos/gates.json`) |
| N3 → N4 | El botón elige desde el banco sin intervención correctiva en ≥ 5 lanzamientos; 60 días sin incidente de recolección; el rendimiento del radar (qué problemas terminaron en ofertas validadas) se revisa cada semana por X2 |
| Descenso | 3 candidatos seguidos con evidencia que D2 no reproduce, o un reclamo de plataforma por recolección: D1 baja a N1 y se revisan las fuentes (`docs/05-riesgos-guardarrailes.md` §4.2) |

---

## 3. Orden de los departamentos

### 3.1 Criterios

1. **Primero lo que protege el dinero**: D0, O0 (estado, gates, hooks, `PAUSA`), contratos, `limites.yaml`.
2. **Medir antes de gastar**: F1 mínimo (conciliación Stripe↔Meta por `oferta_id` + `adid`) y F2 mínimo (una vista) son parte del esqueleto, no del final.
3. **X1 temprano**: tiene veto, y Polonia exige polaco en toda la documentación al consumidor (Ley del Idioma Polaco, art. 7a y 8; `07h` §7). Checklist de claims y desistimiento por país en Fase 0–1; skill formal antes de forjar D5/D6.
4. **Pipeline hacia adelante** (banco de D1 → D2 → D7): la salida aprobada de cada una es entrada real de la siguiente. D1 es la excepción: no recibe nada de una oferta, produce un banco; por eso su primer barrido manual abre la Fase 1 y su forja se reparte por familias (§2.8).
5. **Lo que necesita datos de mercado va después**: D8, D9, X2 y el afinado de M1.
6. **Dos vías en paralelo**: mientras vos pulís, Claude Code construye lo determinista (`factibilidad.py`, `lint_claims.py`, receptor de webhooks, ETL) y se esperan los trámites externos (contador, Przelewy24, nativos, primer payout a 7–14 días). Tu cuello de botella es tu tiempo.

### 3.2 Secuencia

| Orden | Departamento | Vía | Fase | Nota |
|---|---|---|---|---|
| 1 | Contratos | ingeniería | 0–1 | Unificar `limites.yaml`, 72 h entre aumentos, "validada" = §5.9 |
| 2 | **D0** | ingeniería | 0–1 | Healthcheck, preflight, simulacro de kill switch (3 capas) |
| 3 | **O0** mínimo | ingeniería | 1 | Sonda de guardarraíles 100 % `deny` antes de activar |
| 4 | **F1 + F2** mínimos | ingeniería | 1 | Conciliación a 0,00; una vista por oferta |
| 5 | **X1** checklist | criterio | 1 | Skill formal en Fase 2, antes de D5 |
| 6 | **M1** a mano | criterio | 1 | Declara los locales activos que barre D1 y propone el primer mercado (lo decide el dueño `[DUEÑO]`; un mercado a la vez); para #1 valen `07h`, `08`, `rank_sin_pagos.py` y la matriz país × nivel de la nota 25 §8 (hipótesis, no prior); skill con datos en Fase 4 |
| 6b | **D1 primer barrido manual** (§2.8) | criterio | 1 (semana 1) | Banco semilla + `candidatos.json` de práctica; elige el dueño (H). Reemplaza a toda lista de problemas |
| 7 | D2 → D3 → D4 → D5 → D6 → D7, a mano | criterio | 1 | Cada paso se corre a mano en la pestaña Code partiendo de la skill **v0.1 sin pulir** de la etapa (§2.6); retro ligera tras cada una; cada etapa re-verifica MU/EU y el nivel de riesgo heredado |
| 8 | **D10** mínimo | ambas | 1 | Hay clientes pagando: no es opcional |
| 9 | **D8** a mano (revisión diaria) | criterio | 1 | Cada decisión anotada con su causa |
| 10 | **Forja D1 (por familias D1-a y D1-b) → D7** + X1 formal con su suite | criterio | 2 | Lleva las v0.1 pulidas en Fase 1 a v1.0 solo con corrida manual real, retro y DoD firmados, con registro de promoción (§2.6); oferta #2 sale del banco; #1 regresión |
| 11 | QA calibrados, O0 completo, D10 completo, X2 inicial | ambas | 3 | Dorados reales de #1 y #2 |
| 12 | D8 sombra → D9 → F1/F2 completos → M1 con datos → X2; **D1-c (demanda) y D1-d (señales propias)** | ambas | 4 | Requiere campañas vivas |
| 13 | **Radar automático de D1** (cron en Railway/GitHub Actions con APIs oficiales, banco en Postgres) | ingeniería | 5 en adelante (N3) | No entra en el plazo de este plan: exige aviso de investigación, fuentes con API aprobada y presupuesto del radar. Hasta entonces los barridos son de Code (N0-N2) |

---

## 4. Plan por fases `[HIPÓTESIS]`

Supuestos: arranque lunes 2026-11-09; 15 h/semana tuyas `[SUPUESTO]`. Con menos horas, multiplicá las duraciones; no recortes gates.

| Fase | Duración | Resultado |
|---|---|---|
| **0 Fundaciones** | 1,5–2 sem (≈ 9–23 nov) | Decisiones, cuentas, repositorio, infra mínima, líneas rojas, plan B de pagos y cuentas, sesión 1 del primer barrido de D1 |
| **1 Esqueleto caminante** (#1 elegida del banco; un solo mercado, decidido por el dueño con la propuesta de M1) | 5–6 sem | Flujo completo con una oferta real en un mercado y primer test |
| **2 Forja D1 (familias a y b) → D7** (oferta #2 desde el banco) | 7–9 sem | 7 skills + X1 congeladas; #2 en test con skills (N1) |
| **3 QA y orquestación semiautomática** | 4–6 sem | QA calibrados, O0 con gates, D10 completo |
| **4 Optimización, escalado y finanzas** | 6–9 sem | D8 sombra, D9, F1/F2, M1 con datos, X2 |
| **5 Botón** | 3–4 sem | "Lanzar nueva oferta" en N2 |

### 4.1 Fase 0: fundaciones

- **Hacer:** decisiones de §10; `git init` y repositorio privado en GitHub con la estructura del backbone §4; CI mínimo (pytest, esquemas, escaneo de secretos); Cloudflare (cuenta y DNS; los dominios se compran en el alta de cada oferta, N01b de `docs/06`); Railway (proyecto vacío); Stripe (revisar "Deshabilitado" y "Se requiere una acción"); Meta (cuenta, portfolio, fan page, verificación de dominio); correo transaccional; el 2FA que exija cada plataforma al crear credenciales (con el método que uses; las claves nunca van en chats ni en el repositorio); `skill-creator`.
- **Cumplimiento y continuidad `[NUEVO]` (decisión 13; nota 25 §8.2 paso 0 y §9):** aprobar las **30 líneas rojas** y `nivel_max_lanzable` (decisiones §10); **D0 prepara el plan B de pagos**: `perfil_stripe.yaml` (descriptor estático sin condición, categoría, MCC) y un MoR de terceros precalificado para el subconjunto verde (carril B); **plan de concentración en Meta**: verificación de negocio (con el 2FA que exija Meta), activos sin compartir con otros negocios, facturación por umbral bajo sin precargar saldo, runbook de cuenta restringida, y **decidir la cuenta deshabilitada previa (apelar o abandonar; no abrir otra para esquivar)**. Riesgo residual aceptado por el dueño (decisión 15): la higiene de seguridad personal queda fuera de este plan; los frenos de software no cambian. X1 con checklist de claims por jurisdicción y de recolección (VC-01…16); `ayuda_por_pais.yaml`; revisor nativo del idioma del primer mercado (it o pl solo si el dueño los elige) contratado en cuanto el mercado esté decidido.
- **Comprobar en tu Code:** `claude --version`; nombres reales de las herramientas MCP de Meta para `deny` y hooks; si la pestaña carga `.claude/agents` (`[VERIFICAR]`, `01-claude-code-runtime` §5).
- **Gate:** CI verde; contratos v0 que validan; `limites.yaml` firmado; D0 en VERDE y simulacro de kill switch en las 3 capas; resueltas las decisiones de §10 que bloquean Fase 1; contador contactado con fecha; **líneas rojas aprobadas, plan B de pagos y plan de concentración de Meta documentados, cuenta deshabilitada previa decidida y sesión 1 del primer barrido de D1 hecha** (condiciones previas del paso 0 de la nota 25 §8.2: si no se cumplen antes del 15 de diciembre, el paso 1 pasa a enero y el dinero se mide en febrero).

### 4.2 Fase 1: esqueleto caminante con la oferta #1

**Qué se lanza.** **Una oferta en un solo mercado** (un `oferta_id`; regla de un mercado a la vez: `mercados_test_paralelos_max` = 1 en `empresa/parametros.yaml`). **El plan no fija el mercado ni un par de arranque: el primer mercado y la primera oferta los decidís vos `[DUEÑO]`** con la propuesta de M1 (ranking sin criterio de pagos en `scripts/mercados/rank_sin_pagos.py` y cobertura de pago real); tu decisión explícita cubre el gate H de "primer lanzamiento en país o idioma nuevo". Un segundo mercado de la misma `familia_id` vendría **después, en serie**, como otro `oferta_id` (o a la vez solo si subís el parámetro a 2). Marca neutra, dominio, landing y dataset propios por oferta (`[SUPUESTO]`, §10 fila 9; el alta de la oferta se hace en N01b de `docs/06`, ver semana 2); la LLC visible como vendedor (lo exigen Przelewy24 y la ley de consumo). El **candidato** no se fija acá: sale del banco que sembró el primer barrido manual (§2.8), con nivel VERDE (o amarillo-A con revisión), MU y EU verificados, demanda y encaje de mercado.

**Hipótesis de partida (nota 25 §8.2, paso 1; condicionada a su paso 0 y a la evidencia que dé el barrido).** *Presupuesto-por-cobro* (dinero, verde, MU de cálculo: «prorrateo del ingreso hasta el próximo cobro») en el mercado que elijas (la nota parte de `it-IT` y `pl-PL`, sin darlos por buenos), con 60–75 USD en 72 h como **señal de proceso, no estadística**, y sin precio tachado. Por qué este y no otro: es verde de hogar sin P2s (no promete ahorro ni ingresos), con comparación limpia entre mercados cuando haya más de uno, en serie; el v1.0 de la nota abría con un reto de ahorro que es amarillo-A en la celda más restringida de Italia. El paso 2 de la nota (diciembre–enero) sugiere un verde de salud con deseo de salud en Italia (*plan-comidas-semanal* o *habitos-saludables-tracker*, sin tablas de conservación ni temperaturas) y uno de relaciones en Polonia (tarjetas de conversación para parejas que conviven, sin «randki»): se leen como candidatos a contrastar **en serie**, no como un par en paralelo (Polonia, además, solo si habilitás métodos locales). **Es una hipótesis, no una decisión:** si el primer barrido produce un candidato verde con más evidencia en otro nicho o idioma, manda la evidencia. El resumen del piloto del radar (`docs/_historial/d1-v2-piloto/_resumen.md`) no existe todavía; el único piloto real previo es el Modo D con crochet (`scripts/modelado/ejemplos/`), que ejercitó la herramienta y **no** es una recomendación de lanzar.

**Qué pasó con las manualidades.** Como pasatiempo puro no encuadran en salud, relaciones ni dinero y dejan de ser la oferta #1 por defecto (y con ellas los supuestos de patrón a escala, probador de costura y la sonda de 07h §6). «Ganar dinero con manualidades» es un candidato válido de **dinero** y entra al banco como cualquier otro, pero solo es verde si el nombre y la promesa no ponen ingresos del lector como resultado: su versión segura es «costeo y precio mínimo para vender manualidades» (nota 25 §12.4 n.º 14). Compite por evidencia, no por afinidad.

**Polonia e Italia.** Son **hipótesis a contrastar con datos propios**, no un par de arranque ni un prior: `07h` y `08` les ven ajuste de pagos (BLIK, Satispay; el de Polonia solo con métodos locales habilitados) y evidencia parcial, pero el dueño las fija como hipótesis y el corpus de creadores no mide salud, relaciones ni dinero personal en esos países (nota 25 §8.2) y «sobre todo Polonia» es nivel C. `08-mercados-ranking.md` y `departamentos/16-mercados-localizacion.md` ya existen: revisá el ranking el día 1 y antes de lanzar, y que M1 confirme con la matriz país × nivel (Italia en dinero: lo verificable lo cubren los checks automáticos de X1, sin consulta a abogado local; Rumanía no tiene ayuda de crisis verificada). **Con los pagos diferidos (solo tarjeta y billeteras), Polonia no pasa la regla R6 de M1** (cobertura de pago ≈ 17 % frente a un mínimo duro de 40 %; `departamentos/16`) y se evalúa solo si habilitás métodos locales; Italia ronda 46–50 % y pasa el mínimo duro con la bandera `cobertura_media` y gate H. El mercado, uno a la vez, lo decidís vos `[DUEÑO]` con la propuesta de M1; otro mercado que coloque mejor ajuste de pagos y evidencia puede reemplazar a ambos. Evitá Navidad como promesa central: si llegás tarde, el producto vence con el calendario.

| Semana | Trabajo | Tuyo `[HIPÓTESIS]` |
|---|---|---|
| 1 | **D1: sesiones 2–3 del primer barrido manual (§2.8) y elección del candidato (H, con nivel y reencuadre a la vista); M1-a empareja candidato × mercado y propone el primer mercado (lo decide el dueño `[DUEÑO]`, uno solo);** contratos v0→v1 provisional; D2 ligera (Biblioteca web: 5–10 anuncios de > 30 días; voz del cliente; **saturación del mecanismo y sustituto gratis/chatbot**); D3 con economía en la moneda del mercado elegido, y **hasta 3 candidatos de marca neutra** (campo `marca_propuesta[]` de la ficha/oferta, por agregar; sin claims de salud ni de dinero, sin imitar marcas conocidas; X1 los revisa); checklist de X1 | 15 h |
| 2 | D4: producto original en el idioma del mercado elegido, **verificación en frío del entregable único** (casos dorados de cálculo y fuentes T1 si hay afirmaciones), revisión nativa; **alta de la oferta (N01b de `docs/06`: D0 = humano + `infra.alta_oferta`, entre D4 y D5; construido por S-B el 2026-11-06)**: con el veredicto de D3 FACTIBLE o AJUSTADA y tras tu aprobación H de la marca, comprás el dominio (gasto: gate H siempre, nunca un agente) y sale `ofertas/<id>/infra/alta.json`; no se compran dominios ni se crean datasets (irreversibles, máx. 100) para candidatos sin ese veredicto; D5: landing estática, sesión de Checkout creada en servidor, con los métodos que haya (con los pagos diferidos, tarjeta y billeteras; BLIK, Satispay o Przelewy24 solo si los habilitás y, para Przelewy24, si se descarta Managed Payments), casilla de desistimiento, CMP; D5 cierra con `pixel_id`, `dataset_id` y `dominio_verificado` del alta | 15 h |
| 3 | D6: 3 conceptos × 2–3 hooks por oferta (cotizar créditos antes de generar), revisión nativa; píxel + API de Conversiones con `event_id`; D10 mínimo; D7 en borrador | 15 h |
| 4 | Preflight: compra de prueba y **compra real propia** por oferta; conciliación; sonda de guardarraíles; aprobación H, activación; días 1–3 | 12 h |
| 5 | Días 4–7: revisión diaria a mano con reglas de corte; cierre del test | 8 h |
| 6 | Post-mortem (ejecución vs. mercado), retro de cada etapa, contratos v1, decisión de continuidad | 8 h |

**Calendario.** El lanzamiento caería entre mediados de diciembre y principios de enero, tras Black Friday y en plena Navidad. Los CPM suben en el cuarto trimestre `[VERIFICAR]` (D9 usa +35 % como caso de prueba `[HIPÓTESIS]`). Mitigación: con un solo mercado el efecto estacional no se cancela contra otro mercado, así que se presupuesta +20–35 % de CPM, no se concluye de un solo tramo y, si se corre un segundo mercado en serie, se anota el sesgo de calendario.

**Gate de salida:** (1) compra real propia por oferta con 1 email de entrega, 1 `Purchase` deduplicado y conciliación Stripe↔F1 = 0,00; (2) test de 7 días completo o cortado por reglas escritas de antemano; (3) `retro.md` de D2–D8, D10 y F1; (4) contratos en v1; (5) post-mortem y horas tuyas por etapa; (6) decisión de continuidad (§4.3).

### 4.3 Fase 2: forja D1 → D7 con la oferta #2

- **Oferta #2:** otro macro-nicho (salud, relaciones o dinero) y, si el ranking lo respalda, otro idioma o clúster (los creadores citan inglés, francés y rumano `[CREADORES]`, nivel C); candidato verde (o amarillo-A con revisión) del banco, **sin ningún tema excluido por sí mismo**: solo valen las líneas rojas. La descubre la propia D1 con su skill ya pulida a mano en Fase 1 (familias D1-a y D1-b; v1.0 solo según §2.6) y, si el idioma es nuevo, con barrido local previo.
- **Orden:** D1 (familias a y b) → D7 con X1 formal (con su suite de casos de frontera) antes de D5; ciclo de §2 partiendo de las v0.1 ya pulidas en Fase 1 (§2.6: v1.0 solo con corrida manual real, retro y DoD firmados) y casos de A8 (#1 como regresión).
- **Tu tiempo:** suma de los máximos de §10.2 para D2–D7 y X1 ≈ 35–40 h, más D1 por familias (§2.8, ≈ 12–18 h hasta N1 y ≈ 6–8 h por familia posterior `[HIPÓTESIS]`) (D3 usa como "3 ofertas de práctica" las reales que haya: #1, #2 y un segundo mercado de #1 si ya corrió en serie; si faltan, casos sintéticos sin gasto).
- **Gate:** 7 skills y X1 en `v1.0.0` (o `v0.9` con deuda; D1 puede quedar en N1 con solo las familias a y b y la deuda de c y d escrita); #2 en test con Makers (N1); costo y tiempo por etapa medidos; **0 falsos verdes del clasificador en la retención**; la regresión de #1 pasa sin editar skills entre casos.
- **Punto de continuidad `[NUEVO]`:** con las pruebas de mercado que haya (al menos #1 y #2, cada una en su mercado; más si se corrieron mercados en serie), si ninguna llega a "prometedora" (§6.2), parar y revisar nicho, ángulo y modelo *antes* de las fases 3–5. La base de ingeniería se reutiliza; el escalado no tiene sentido sin una oferta que venda.

### 4.4 Fase 3: QA calibrados y orquestación semiautomática

QA de D1–D7 y X1 calibrados con dorados reales de #1 y #2. O0 completo: transiciones, gates H, propuesta semanal, reanudación sin duplicados. D10 completo: envío probado en Gmail, Outlook e iCloud, reembolsos en código. X2 solo registra. **Aceptación:** una oferta #3 (o la expansión de la familia a otro mercado) recorre, por O0, desde la elección de un candidato del banco hasta D7 con ≤ 8 h tuyas y ≥ 80 % de etapas sin edición sustantiva `[HIPÓTESIS]`; sonda 100 % `deny`; `PAUSA` ≤ 5 min.

### 4.5 Fase 4: optimización, escalado y finanzas

D8: 7 días en sombra sobre campaña real, coincidencia ≥ 90 %. D1: familias c (demanda) y d (señales propias de D8/D10), rendimiento del radar medido por X2 (qué problemas terminaron en ofertas validadas) y comparación del filtro por nivel con el filtro ingenuo por tema; primera aprobación de las reservas y los umbrales de pausa de F1/F2 con datos reales. D9: sobre una oferta validada (§5.9) o, si no hay, un replay sintético (la especificación lo permite). F1/F2: cierre mensual dorado al centavo, ETL desatendido 7 días. M1: ranking recalibrado con los pagos reales y los resultados. **Gate:** una oferta validada o el reconocimiento escrito de que aún no existe, con tu decisión (otro nicho, mercado o ángulo).

### 4.6 Fase 5: botón

Flujo completo con gates H donde el backbone los exige en N2 (oferta, publicar landing, activar campaña, subir presupuesto, primer lanzamiento en país o idioma nuevo), tope diario, revisión semanal y kill switch en 3 capas. **Aceptación:** dos lanzamientos de punta a punta sin intervención correctiva fuera de los gates; rechaza uno que viola `limites.yaml` y otro sobre una línea roja o un candidato ROJO sin reencuadre. El botón **elige desde el banco** (si no hay candidatos vigentes en el idioma pedido, dispara un barrido dirigido de D1 antes de congelar `candidatos.json`) y el dueño elige (H). El botón es N2; N3/N4 dependen de volumen (§7).

---

## 5. Checklist de los primeros 10 días (desde hoy, vie 2026-11-06)

≈ 24–30 h tuyas `[HIPÓTESIS]` (el primer barrido manual de D1 suma ≈ 6 h). ⏳ = arranca el trámite y sigue solo. **No hay tarea de «preparar una lista de problemas»**: el candidato sale del primer barrido (§2.8).

| Día | Tarea | Resultado |
|---|---|---|
| 1 (vie 6) | ⏳ Escribir al contador de la LLC con las preguntas de `07h` §16 (IVA de un PDF: general o reducido; OSS no-Unión; representante GDPR; MCC). Leer backbone v2.2, la nota 25 (§0, §8, §9, §12.4) y este plan | Consulta enviada |
| 2–3 (sáb–dom) | Capturar las pestañas "Deshabilitado" (24) y "Se requiere una acción" (1) de Stripe. Decidir: **líneas rojas** (30 de la nota 25 §3.3) y `nivel_max_lanzable`; **tolerancia de riesgo** (cuota de gasto en amarillos); A3 (reembolso); tu tiempo semanal; qué hacer con la **cuenta de Meta deshabilitada**. La pérdida máxima por oferta (C2) puede seguir diferida: `limites.yaml` queda con `null` y nada gasta. Contratar al revisor nativo del idioma del primer mercado (cuando lo decidas) | `00-decisiones` con respuestas |
| 4 (lun 9) | `git init`, repositorio privado, estructura del backbone §4, `.gitignore` con secretos y con `empresa/descubrimiento/senales/` (evidencia de terceros fuera de git) | Repo con CI en verde |
| 5 (mar 10) | Cloudflare (cuenta y DNS; **marca y dominio no se compran todavía: se compran en el alta de la oferta, N01b de `docs/06`**, después del veredicto FACTIBLE o AJUSTADA de D3 y de D4, antes de D5, con tu aprobación H de la marca). ⏳ Meta: portfolio, cuenta publicitaria limpia (no reutilizar la deshabilitada), verificación de negocio, decidir la fan page (sin decidir; recomendado: una por oferta) | Cuentas y página decidida |
| 6 (mié 11) | ⏳ Correo transaccional (cuando haya dominio); Railway; **perfil de navegador dedicado para D1 (sin login, sin cuentas de valor)** | Infra base |
| 7 (jue 12) | Revisar con Claude Code los contratos ya existentes (`docs/contratos.md`, `contratos/*.schema.json`, `empresa/{limites,parametros}.yaml`) contra las especificaciones; anotar choques en `coordinacion-sesiones.md`. **D1, sesión 1 del primer barrido manual (§2.8, pasos 1–3): plan y recolección en 1 macro × 1 nicho × 1–2 locales** | Choques anotados; primeras señales citadas |
| 8 (vie 13) | **D1, sesión 2 (pasos 4–5): fichas MU/EU, prueba de una frase y riesgo P/C/E/N por candidato.** Arranque de D0 con el prefijo de §2.1; completás `limites.yaml` con lo que ya sepas | Fichas y niveles; `limites.yaml` parcial |
| 9 (sáb 14) | **D1, sesión 3 (pasos 6–7): puntaje, banco semilla y `candidatos.json` de práctica; elegís el candidato de la oferta #1 o pedís otra ronda.** Code: `skill-creator`, `claude --version`, `/skill-doctor`, reglas `deny` sobre las herramientas MCP de Meta, `.claude/agents` | Candidato elegido; `[VERIFICAR]` resueltos |
| 10 (dom 15) | Gate de Fase 0 (§4.1) punto por punto, incluido el plan B de pagos y cuentas, y fecha de arranque de Fase 1 | Fase 0 cerrada o con plan de cierre |

Mientras tanto: no activar campañas, no pagar cursos ni Venzio, no reutilizar el píxel inactivo ni la cuenta deshabilitada (`00-decisiones` §E).

---

## 6. Presupuesto del primer test y cuánto aprender antes de gastar

### 6.1 Economía unitaria

Fuente: `07h` §3.5 y §5.3, `03-stripe`. **Referencia de orden de magnitud para un frontal de ~13–17 USD en PL/IT** (la nota 25 §8.2 también parte de 39–49 zł y 14,90 €); las dos columnas comparan las dos hipótesis de mercado y **no** son un lanzamiento en paralelo (un mercado a la vez); D3 recalcula con `engine/factibilidad` para el candidato elegido, con IVA por país, recargo de Meta, mezcla de métodos y comisión no devuelta en reembolsos. Precios iniciales `[HIPÓTESIS]`: 49 zł (≈ 13,2 USD) con BLIK; 14,90 € (≈ 17,3 USD) con tarjeta. CPC = CTR de enlace 1,8 % sobre CPM de referencia; en Italia +3 % de tarifa de ubicación de Meta.

| | Polonia | Italia |
|---|---|---|
| Neto por venta frontal tras IVA y comisión (CPA_max) | ≈ 9,8 USD | ≈ 13,0 USD |
| CPC supuesto | 0,31 | 0,36 |
| Conversión clic→compra para CPA = break-even | 3,2 % (con bump ×1,5: 2,1 %) | 2,8 % (1,9 %) |
| CPA objetivo (0,6 × CPA_max, regla de O0) | 5,9 USD | 7,8 USD |
| Conversión necesaria para CPA objetivo | 5,3 % (con bump: 3,5 %) | 4,6 % (3,1 %) |
| Gasto tras el cual 0 compras ocurriría con ≤ 5 % de probabilidad si la oferta estuviera en break-even (`3 ÷ c_be` clics) | ≈ 29 USD | ≈ 38 USD |
| Gasto para esperar 15 compras al break-even (`15 ÷ c_be` clics) | ≈ 147 USD | ≈ 194 USD |

Las dos últimas filas coinciden con `testeo.k_corte` (3 × CPA_BE; antes `m_kill`) y `testeo.n_dec` (15): `presupuesto_min_decidir` ≈ 88 USD (PL) y 117 USD (IT) más creativos. El rango de 170–225 USD por país de `07h` §11 es razonable.

### 6.2 Qué puede enseñar el test

Con 200 USD por país: ≈ 645 clics en Polonia y ≈ 556 en Italia. Probabilidad de ≥ 5 compras (criterio mínimo de `07h`), según la conversión real (cálculo propio, Poisson):

| Conversión real | Compras esperadas PL / IT | P(≥ 5 compras) PL / IT |
|---|---|---|
| 0,5 % | 3,2 / 2,8 | 22 % / 15 % |
| 1 % | 6,5 / 5,6 | 77 % / 65 % |
| 2 % | 12,9 / 11,1 | > 99 % / 99 % |
| break-even (3,2 % / 2,8 %) | 20 / 15 | > 99 % / > 99 % |

- Cero compras con ~600 clics y tracking sano implica conversión real < ≈ 0,5 % con 95 % de confianza (regla de tres). **El test sirve para descartar.**
- La "oferta validada" (backbone §5.9) exige cohortes maduras (garantía + 7 días), CPA ≤ objetivo y volumen: **el primer test no la alcanza**. Salidas posibles: *descartada*, *prometedora* (≥ 5 compras reales y CPA ≤ 1,5 × break-even con bump, criterio de `07h`) o *inconclusa* (definición en D8).
- El criterio de `07h` (CPA ≤ break-even) es más laxo que el de §5.9 (CPA ≤ 0,6 × CPA_max). Conviene fijarlo ahora para que nadie lo lea como validación `[NUEVO]`.
- Meta pide ~50 eventos semanales por conjunto para salir del aprendizaje: no se alcanza. D7 debería evaluar 1–2 conjuntos en vez de los 4 de `07h`. El test distingue diferencias grandes entre países (≈ 2×), no del 30 % `[HIPÓTESIS]`.

### 6.3 Escalera: qué saber antes de cada gasto

| Tramo | Costo | Pregunta que debe quedar respondida por escrito |
|---|---|---|
| 0 Gabinete | 0 USD | ¿El problema pasa la prueba de una frase (MU + EU) y su nivel de riesgo es verde o amarillo-A con revisión? ¿Hay anunciantes sostenidos con ese mecanismo y qué dice la voz del cliente en ese `locale`? ¿Existe un sustituto gratis dominante? (La cantidad de anuncios es contexto, no prueba.) |
| 1 Producto y cumplimiento | revisor nativo, revisión profesional o probador según el producto, dominios `[VERIFICAR]` | ¿D4 verificó en frío el entregable (cálculos con casos dorados, afirmaciones con fuente T1, un novato lo usa solo)? ¿Idioma nativo? ¿X1 sella claims, ayuda del país, desistimiento y la coherencia anuncio = landing = producto = descriptor? |
| 2 Medición | comisión de las compras propias (no se devuelve al reembolsar) | ¿Compra real propia con cada método habilitado (tarjeta y billeteras; BLIK solo si lo habilitás)? ¿1 `Purchase` deduplicado? ¿Conciliación 0,00? ¿Sin consentimiento de cookies, Stripe sigue siendo la verdad? |
| 3 Seguridad | 0 USD | ¿`limites.yaml` firmado, `PAUSA` probada, límite de gasto de la cuenta en Meta fijado, hook bloqueando activar sin aprobación? ¿Plan de concentración de Meta hecho (activos no compartidos) y carril B de pagos precalificado? ¿Umbrales de pausa por disputas, reembolsos y avisos cargados en F1/F2? |
| 4 Tramo A en vivo | ≈ 29–38 USD por país | ¿CTR de enlace ≥ 1 % tras 1.000 impresiones? ¿Hay inicio de pago? ¿Qué método elige el cliente? |
| 5 Tramo B | hasta 170–225 USD por país | ¿Se alcanzan las compras mínimas? ¿CPA neto y % por método? |

No se pasa de tramo sin responder el anterior; los tramos 0–3 enseñan más por dólar. Cortes de creativos: los de `07h` §11.

### 6.4 Costos y topes

- **Anuncios:** 4 conjuntos × 6–8 USD/día × 7 días = 168–224 USD por mercado (`07h`), +3 % en Italia. Con un mercado a la vez, el primer test cuesta esa cifra; ≈ 340–450 USD es la suma si después se corre un segundo mercado en serie (o a la vez, subiendo `mercados_test_paralelos_max` a 2).
- **Fuera de anuncios** (completalos vos; no tengo esos precios): dominio y revisor nativo por oferta e idioma, revisión profesional solo si el producto es amarillo-B, créditos de generación, Stripe Tax y comisiones de compras propias, Railway y Cloudflare, uso de Claude (`costos.jsonl`) `[VERIFICAR]`.
- **Reservas y capital inmovilizado `[HIPÓTESIS]` (no son gasto):** fondo de reembolsos `max(15 % de ingresos amarillos, 8 % verdes)` liberado a los 120 días, colchón rodante del 25 % de las ventas a 90 días y caja de congelamiento = 3 semanas de gasto en Meta + 1 mes de costos fijos (nota 25 §9). Umbrales de pausa en F1/F2 sobre 30 días móviles: disputas + alertas / pagos Visa 0,20 % alerta · 0,35 % pausa de la oferta · 0,50 % y ≥ 5 casos pausa del macro-nicho (H); casos absolutos 2 / 3 / 5; reembolsos de cohortes maduras 8 % / 12 % / 15 %. Con ~400 pagos al mes, 5 casos ya son 1,25 %; `[NUEVO]` en un test de 15–30 compras un solo caso ya pesa ~3–7 %, así que el primer caso se trata como señal y no como estadística.
- **Propuesta para `limites.yaml`** `[HIPÓTESIS]`, la fijás vos y **hoy está sin fijar** (el dueño difirió la pérdida máxima por oferta; con `null` el motor es fail-closed): test total 225 USD por oferta; presupuesto diario 32 USD por oferta (techo teórico 1,75 × = 56); global diario 64 USD (techo teórico 112); pérdida máxima all-in 450–600 USD según costos fijos. Con `mercados_test_paralelos_max` = 1 se lanza **un solo mercado primero**, el que decidas con la propuesta de M1 (Polonia solo si habilitás métodos locales: con los pagos diferidos no pasa R6); un segundo mercado, si se corre, va después en serie, aceptando el sesgo de calendario.

---

## 7. Cómo se mide que una skill o etapa sube de nivel

**Reglas.** El nivel se guarda por etapa en `empresa/autonomia.yaml`; solo lo cambia el dueño y el sistema aporta la evidencia. Todo ascenso exige: la métrica de la especificación; un **QA calibrado vigente** (si cambió la skill del QA, se recalibra); la **sonda de guardarraíles** en 100 % `deny` para lo que mueve dinero; cero incidentes abiertos de X1. Se mide sobre artefactos (ediciones tuyas por `origen_version`, recall de sembrados, PASS de dorados, coincidencia en sombra, recomputos del QA, incidentes), no sobre sensaciones. Hay descenso automático ante violaciones.

| Transición | Evidencia mínima |
|---|---|
| N0 → N1 | DoD de §2.6; 2 sombras con ≥ 80 % de coincidencia |
| N1 → N2 | QA calibrado; ≥ 5 corridas reales con ≥ 70–80 % sin edición sustantiva y 0 bloqueantes escapados (valor exacto por etapa) |
| N2 → N3 | Volumen y tiempo (tabla); 0 violaciones de tope |
| N3 → N4 | Semanas sin intervención correctiva con dinero real; simulacro superado |

Umbrales de las especificaciones (resumen):

| Etapa | N1 → N2 | N2 → N3 | En este plan |
|---|---|---|---|
| D1 (radar, por familia de fuentes; detalle en §2.8) | ≥ 80 % de candidatos aceptados sin edición en 5 corridas; 0 falsos verdes en la retención; VC-01…16 sellados | tu elección ∈ top-3 en ≥ 80 % de ≥ 8 corridas; borrado verificado; presupuesto del radar fijado | N1→N2 alcanzable en Fase 3–4 para las familias a y b; N3 (cron en Railway, APIs oficiales) fuera del plazo del plan |
| D3 | 5 ofertas con ≤ 3 ediciones | ≥ 10 ofertas, ≥ 70 % sin edición, error mediano de CPA ≤ 35 % en ≥ 5 tests | N3 solo cuando se cumpla la columna anterior; sin plazo prometido |
| D9 | v1 aprobada, QA calibrado | ≥ 15 aumentos supervisados en ≥ 2 ofertas | N2 como máximo |
| F1 | 2 cierres con 0 diferencias | ≥ 90 días | N2 en Fase 4 |
| X1 | 20 dictámenes con ≥ 90 % de concordancia; 100 % de los sembrados L1; 0 falsos verdes en retención (n ≥ 60) | 30 dictámenes, 0 falsos negativos en 60 días; sin rechazos de Meta/Stripe atribuibles a un falso verde | N2 en Fase 3–4 |

**Conclusión:** al cerrar la Fase 5 es razonable N2 en D1 (familias a y b)–D7, X1, F1 y F2, y N1–N2 en D8–D10 y X2. N4 queda fuera del plazo de este plan: depende de la cantidad de ofertas y ventas y de una alternativa por API para los conectores interactivos, no de la calidad de las skills; sin fecha prometida.

---

## 8. Pestaña Code vs. código en GitHub, Railway y Cloudflare

Principio del backbone: **el modelo propone, el código dispone** (kill, escala, presupuesto, reembolso, linters y guardarraíles son scripts).

| Tarea | Pestaña Code (tu escritorio) | GitHub | Railway | Cloudflare |
|---|---|---|---|---|
| Forjar y pulir skills (N0–N1) | Sí: sesiones interactivas, `skill-creator`, evals, retro | Rama `forja/<id>` y PR | | |
| Scripts, hooks, esquemas | Programación en pareja | Código, CI, tests | | |
| Aprobar cambios de skills y contratos | Revisás el PR | CODEOWNERS: solo vos aprobás `.claude/skills/**` y `contratos/**` | | |
| Corridas Maker/QA con MCP (Meta, Drive, Docs) hasta N2 | Sí: los conectores se autentican de forma interactiva y no sirven desatendidos | | | |
| **Barridos del radar de D1** y banco de problemas | N0–N2: barrido en Code (`WebSearch`, `ads_library_search`) y, para fuentes con muro, **perfil de navegador dedicado** sin login, a ritmo humano, con X1 aprobando cada dominio; banco = carpeta local `empresa/descubrimiento/` (señales fuera de git) | Código del radar, CI, y —solo para un barrido semanal acotado de fuentes verdes— tarea programada | N3+: servicio `radar` con cron + **banco en Postgres** (señales con TTL), scripts con APIs oficiales y claves propias; el LLM por `claude -p` con `--max-budget-usd` | |
| Webhooks de Stripe, eventos de servidor a Meta, idempotencia | | | Servicio siempre encendido + base de datos | |
| ETL de Meta y Stripe, conciliación, reglas de D8, reportes | Desarrollo y revisión | Tareas programadas de bajo riesgo | Cron + base de datos; claves de solo lectura | |
| Landing, páginas legales por oferta | Genera y pule | Código | | Hosting estático y DNS por dominio |
| Sesión de Checkout por visitante | Desarrollo | Código | Aquí o en Workers `[NUEVO]` (decide D0) | Workers |
| Corridas desatendidas (N3+) | | `claude-code-action` con clave de API (sin conectores de claude.ai) | `claude -p` o Agent SDK con clave de API y `maxBudgetUsd` | |
| Kill switch | Probás el simulacro | | Script de pausa | Límite de gasto en Meta como tercer candado |

`[VERIFICAR]` en tu pestaña: que cargue `.claude/agents`, que los hooks se disparen para los conectores de claude.ai en modo `-p`, y que `--bare` (desactiva hooks) no pase a ser el valor por defecto de `-p`.

Dos perfiles de sesión `[NUEVO]`: **forja** (vos, escribe en `.claude/skills/` de una rama) y **operativa** (agentes, con `deny` sobre `.claude/skills/**`, `.claude/agents/**`, `contratos/**` y `empresa/limites.yaml`).

---

## 9. Errores típicos a evitar

| Error | Señal temprana | Qué hacer |
|---|---|---|
| Forjar antes de los contratos | Cada skill define su propio `limites.yaml` | Contratos v0 en CI primero |
| Pulir de más | Cuarta sesión de la misma skill | `v0.9` con deuda; volver con datos |
| Sobreajustar al primer caso | Un tema («presupuesto», costura) o "zł" dentro de la skill | Otro macro-nicho y otro idioma en cada ciclo |
| Decidir plata con Meta | "Compras" tomadas del Administrador | Ingresos = Stripe; Meta, solo gasto y señal (backbone §5.3) |
| Confundir países | Si se corre más de un mercado (en serie), precios, creativos o fechas distintos | Mismo producto y embudo; solo cambian idioma, moneda y pagos |
| Concluir de más | "Polonia funciona" con 4 compras | §6.2: el test descarta o pasa a un segundo tramo |
| Elegir Managed Payments por comodidad | Se apagan BLIK y Przelewy24 sin notarlo | Decisión informada con contador (§10) |
| Revisor nativo tarde | Textos que suenan a traducción | Contratarlo en cuanto el primer mercado esté decidido (Fase 0 si ya lo está) |
| Segunda cuenta de Meta tras un rechazo | Impulso de "seguir probando" | Prohibido: escalar a X1 |
| Segunda cuenta de Stripe, o un perfil de Meta nuevo, para esquivar una terminación | «Abrir otra para seguir» | Prohibido (acuerdo de servicios de Stripe §1.2(a)(vii); activos de Meta en estrecha conexión se restringen juntos): carril B de pagos y apelación del dueño |
| Admitir o excluir un **tema** en bloque | «Salud no», «dinero sí» | Se evalúa el candidato: promesa, contenido, encuadre y categoría de negocio; solo las líneas rojas excluyen |
| Elegir el nicho por afinidad o porque «ya hay anuncios» | Un tema favorito sin banco que lo respalde | Candidato del banco con MU/EU, evidencia por `locale` y nivel verde o amarillo-A |
| Saltarse el filtro MU/EU | «Método secreto», promesa de resultado, comunidad o servicio dentro del producto | Prueba de una frase; motivo canónico de rechazo con su redención |
| Raspar una fuente roja o usar tu navegador con cuentas de valor | Captcha, 403, `Disallow`; sesión de Meta abierta | Perfil dedicado sin login, solo fuentes V/A aprobadas por X1; el bloqueo degrada la fuente |
| Creer que pausar el gasto frena las disputas | Disputas que llegan 30–120 días después | Reservas y umbrales de §6.4; el primer caso es señal |
| QA que sella todo | PASS sin hallazgos | ≥ 3 hallazgos o justificación (backbone §6.7) |
| Aprobar por fatiga | Tarjetas de gate sin leer | Tope de gates por día; sin tu firma no avanza |
| Claves en chat o repositorio | Una clave pegada | No guardarla, rotarla, escanear el repositorio |

---

## 10. Decisiones tuyas que desbloquean cada fase

"Recomendación" es una propuesta de trabajo, no asesoría legal ni fiscal. Riesgo residual aceptado por el dueño (decisión 14): sin revisión legal humana; lo verificable lo automatiza X1 y lo fiscal lo cubre el contador.

| # | Decisión | Desbloquea | Recomendación | Cuándo |
|---|---|---|---|---|
| 1 | **Régimen fiscal / MoR:** IVA propio (Stripe + Stripe Tax + OSS no-Unión) o Managed Payments (+3,5 %) | Primera venta en UE | Para este test, **IVA propio**: Managed Payments no admite BLIK, Satispay, MB WAY, EPS, Pay by Bank ni Przelewy24 y dejaría a Polonia solo con tarjeta y billeteras. Esa base se estima en **≈ 17 %** en `07h` §3.3 (tarjetas 11 % + billeteras ≈ 6 %, nivel C) y en **≈ 23 %** en `07e` §9 (Worldpay 2024: billeteras 12 % + débito/prepago 7 % + crédito 4 %, B/C): son dos estimaciones de **la misma base** (tarjeta y billeteras, sin método local) con fuentes distintas, no «sin» y «con» Managed Payments. Con los pagos diferidos esa es también la cobertura sin Managed Payments mientras no se habiliten métodos locales; con BLIK sube a ≈ 60–70 % (`07h` §3.3). En ambos casos queda bajo el mínimo duro de 40 % de M1 (R6). El OSS no-Unión no tiene umbral y Stripe puede presentarlo vía Irlanda `[VERIFICAR]` costo. Confirmar con contador | Antes de la semana 4 de Fase 1 |
| 2 | **Contador de la LLC** | #1; IVA de un PDF (¿reducido?), representante GDPR, MCC | Contratarlo ya: es el trámite más lento | Día 1 |
| 3 | **Przelewy24** | Segundo método polaco (15–25 % de pagos, C) | Habilitarlo solo si #1 descarta Managed Payments. Exige en el sitio dirección, ID fiscal, número de registro, reembolsos, privacidad y términos. PayPal no se activa vía Stripe para una LLC: aceptar el hueco en Italia durante el test `[VERIFICAR]` alternativas | Fase 1, sem. 2 |
| 4 | **Correo transaccional** (Resend, Postmark o SES `[VERIFICAR]`) y **bandeja de soporte** `[DUEÑO]` | Entrega, soporte, reembolsos; bloquea la entrega y, por tanto, la primera venta en vivo | Diseño ya escrito (`docs/07` §6: `envio.<dominio>` con SPF/DKIM/DMARC; `departamentos/11`: interfaz `ProveedorCorreo`, `soporte@<dominio>`); falta decidir proveedor y bandeja (recomendación de bandeja: reenvío de correo de Cloudflare hacia tu buzón `[VERIFICAR]`) | Fase 0 (sin fecha comprometida) |
| 5 | **Fan page(s)** `[DUEÑO]` | Identidad de los anuncios, verificación de dominio | **Sin decidir; recomendado: una por oferta** (Página neutra por marca/oferta, para aislar la restricción de una Página del resto; costo: un alta por oferta); verificar límites de páginas y datasets por portfolio `[VERIFICAR]` | Fase 0 |
| 6 | **Cuenta de Meta, plan de concentración y límites de gasto (C2)** | Cualquier campaña | Una cuenta limpia; decidir la deshabilitada (apelar o abandonar; no abrir otra para esquivar); activos no compartidos, sin precargar saldo; `limite_gasto_cuenta_meta` y `limites.yaml` firmados (§6.4). La pérdida máxima por oferta puede seguir diferida: con `null` nada gasta | Fase 0 |
| 7 | **Candidato de la oferta #1** (elegido del banco tras el primer barrido manual) y su validación de producto | Fase 1, sem. 1 | §2.8 y §4.2; nivel verde o amarillo-A con revisión; si el producto exige verificación humana (cálculo, fuentes, impresión), contratar a quien la haga | Antes del lun 16 |
| 8 | **Revisor nativo del idioma del primer mercado** (polaco o italiano solo si salen elegidos: son hipótesis, no un par de arranque) | D4, D5, D6 | Uno por idioma; revisa una vez por idioma × macro-nicho glosario, avisos y las 10 primeras piezas, y luego muestrea 1 de cada 5 (nota 25 §10.2); costo fijo del test (`07h` §8) | En cuanto el dueño decida el primer mercado; antes de su primer lanzamiento |
| 9 | **Marca y dominio por oferta** `[SUPUESTO]` hasta que lo confirmes `[DUEÑO: confirmar]` | Landing, correo, verificación de dominio | Se asume «marca y dominio por oferta» porque a la pregunta sobre marca y dominio respondiste «no aplica creo» (mensaje 2, punto 3 de la primera sesión; `docs/_historial/auditoria-pedidos-primera-sesion.md`, C-11): confirmá o corregí. Marca neutra (sin condición ni resultado en el nombre, sin claims de salud ni dinero, sin imitar marcas conocidas): D3 propone hasta 3 candidatos, X1 los revisa y la aprobás vos (gate H) **antes** de comprar el dominio (gasto: gate H siempre, nunca un agente); un dominio por oferta; la LLC visible como vendedor | N01b de `docs/06`: tras D3 FACTIBLE o AJUSTADA y D4, antes de D5 (sem. 2 de Fase 1 `[HIPÓTESIS]`) |
| 10 | **Stack de checkout** | D5 | Landing en Cloudflare + Stripe Checkout (automatizable y testeable); Shopify fuera del camino crítico | Fase 0 |
| 11 | **Política de reembolso/garantía (A3)** | D3, D5, D10 | Fijar días y condiciones; tomar de `05-legal` y verificar con los checks de X1 (plantilla generada) la renuncia al desistimiento con consentimiento separado; el contador solo para lo fiscal | Fase 0 |
| 12 | **Precios en PLN y EUR** (`currency_options`) | D3, D5 | BLIK no aparece si el precio está en EUR o USD | Fase 1, sem. 1 |
| 13 | **Fuente de "Polonia, sobre todo"** | Priorizar PL vs. IT | Ya decidiste (2026-11-06) que Polonia y cualquier mercado son hipótesis a decidir con datos propios; el corpus no la respalda (`07h` §9, nota 25 §8.2). Si tenés otra fuente, pasala como señal | Fase 1 |
| 14 | **Tiempo semanal disponible** | Todas las duraciones | Este plan asume 15 h; decime la cifra real y se reescala | Día 1 |
| 15 | **Líneas rojas, sub-áreas excluidas y tolerancia de riesgo (reemplaza a «nichos prohibidos»)** | D1, D2, D3, X1 | Aprobar las 30 líneas rojas de la nota 25 §3.3 (promesas, contenidos y modelos de negocio, no temas), `nivel_max_lanzable` = amarillo-A (B solo con decisión H y ayuda verificada) y `subnichos_prohibidos: []`. Tu decisión: **qué sub-áreas dejás fuera** (`hojas_pausadas`, zonas grises cerradas: planner de porciones, dejar de fumar o beber, ayuno, astrología, cripto de custodia, inversión conceptual) y **qué tolerancia de riesgo aceptás** (cuota de gasto en amarillos 30 % / 10 %) | Fase 0 |
| 16 | **Plan B de pagos** | D0, F1, D5 | Pre-integrar un MoR para ofertas verdes (carril B) y mantener `perfil_stripe.yaml`; no abrir segunda cuenta de Stripe; reserva de 120 días | Fase 0 (diseño), Fase 3 (prueba) |
| 17 | **Presupuesto, fuentes y alcance legal del radar** | D1, X1, D0 | `max_busquedas_por_barrido`, `max_costo_por_barrido`, `max_barridos_por_semana`, `fuentes_permitidas[]`; aviso de investigación de mercado (plantilla generada por el sistema); región de Railway y Cloudflare. El barrido manual de §2.8 no los necesita; el cron (N3) sí | Antes de N3 |
| 18 | **Régimen de revisión humana** | O0, X1 | Revisión de seguridad solo en el primer lanzamiento de cada hoja × idioma y muestreo posterior; el dueño ve excepciones (nota 25 §12.4 n.º 16) | Antes de N2 |

**Bloqueos por fase.** Fase 0: #2, #4, #5, #6, #10, #11, #14, #15, #16. Primer barrido y elección del candidato: #15 (líneas rojas) y #7. Lanzamiento de Fase 1: #1, #3, #8 (revisor nativo del idioma del mercado elegido), #9 (marca y dominio: aprobación H de la marca en N01b, tras D3 y D4, antes de D5), #12. Fase 2: #13, #18. N3: #17. Fase 3 en adelante: dónde corre lo desatendido (equipo propio o Railway con clave de API y `maxBudgetUsd`; tareas en la nube solo para lo de bajo riesgo) y el tope de IA por corrida.

> Las cifras de CPM, CTR, conversión y tarifas vienen de `07e`–`07h` y `03-stripe` (mayormente confianza B/C); los cálculos de §6 son propios `[HIPÓTESIS]`.
