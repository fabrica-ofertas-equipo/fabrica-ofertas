# X2 — Memoria y aprendizaje (evolución controlada de skills)
> Transversal · Eventos por entregable y por cierre de oferta; patrones, rendimiento del radar y métricas semanales; gobernanza mensual · Gate por defecto: S (todo cambio de skill: H) · Estado de la skill: por forjar · Alineada con backbone v2.2; ante conflicto manda el contrato

## 1. Misión y posición en el flujo

Convertir lo que el sistema ve (resultados, hallazgos de QA, ediciones y elecciones del dueño, rechazos de plataformas, post-mortems) en **conocimiento verificable y reutilizable**: (a) memoria consultable por **macro_nicho × nicho_id × `locale` × `familia_id`** para M1, D1, D2, D3, D6, D8 y D9; (b) **rendimiento del radar** que prioriza los barridos de D1; (c) canal **controlado** para que los patrones lleguen a las skills (evidencia, evals, aprobación del dueño, versión, reversión); (d) métricas de aprendizaje para F2.

- **Recibe de:** QA de todas las etapas, diffs Maker vs. aprobado, D8 (`veredicto_oferta.json`, `postmortem.json`), D1 (`candidatos.json`, conteos del banco), D2 (`devolucion_d1`), M1 (`mercado.json`, atlas, fichas de país), D9 (réplicas `variante_de`), D10 (agregados), F1 (economía real), X1 (rechazos, vetos, incidentes), `estado.json`, `registro.jsonl`, `costos.jsonl` y el dueño.
- **Entrega a:** M1 y D1 (fichas de mercado, `rendimiento_radar.json`, `descartes.jsonl`, priores), D2, D3, D6, D8, D9 (fichas de contexto), todos los Makers y QA (`fallas_conocidas`), dueño (PC-NNN) y F2. Ruta: `empresa/memoria/`.
- **Fuera de alcance:** gastar, publicar, usar MCP o tocar Meta/Stripe; editar `limites.yaml`, `parametros.yaml`, `contratos/**`, hooks, `.claude/**`, `casos-frontera.yaml` de X1, banco y `nichos.yaml` de D1 (solo propone); aprobarse a sí mismo.

## 2. Qué dice el video (y qué no dice)

- **[VIDEO] Hace:** pide leer y corregir la primera versión; si no anda, “armar otra”. **Omite:** memoria, post-mortem, ejecución vs. mercado, tamaño de muestra, ediciones del dueño, versionado, reversión, privacidad, diferencias por idioma. **No tomamos:** “a prueba de tarados”, “oferta en un día”, Venzio, “otra oferta” sin post-mortem. Su ejemplo (edición con IA) no es un nicho modelo.
- **[CREADORES] “Cerebro” de Tomi Trimb (Claude Code + Obsidian; arquitectura B por demo en pantalla, resultados C por cifras inconsistentes; `14` §3, `13` §5):**

| Cerebro | X2 / decisión |
|---|---|
| `index` + manual de 49–52 reglas + `log`, grafo de 282 páginas [tt/OZ_2bFG3Cd8 @ 03:14; tt/-nQaXIO7Ap0 @ 29:52] | Copiamos el `index` de una pantalla (ficha ≤`max_tokens_ficha`); Obsidian solo de lectura |
| Memoria de fracasos por producto × país; avisó “no funcionó” y se lanzó igual [tt/Lqi5fJi5gIM @ 26:55] | Ficha por nicho × `locale` × familia; un aviso vigente exige acuse en el gate H de D1/M1; informa, no veta (veta X1) |
| Escritura libre de Claude (“la memoria de Claude es una mentira” [tt/-nQaXIO7Ap0 @ 25:09]); regla anti-testimonios falsos borrada a pedido [tt/Lqi5fJi5gIM @ 30:08] | Solo `ingesta.py` escribe, con hash y cuarentena; rutas protegidas, PC con hash, M-08/M-14 |
| “92 % de lo que lanzo vende” [tt/-nQaXIO7Ap0 @ 1:07:13] vs. 3–4 productos antes del ganador | Prior “1 de cada 4” `[HIPÓTESIS]` en `priores.jsonl` (“venden” ≠ “escalan”, `20a`) |

## 3. Variables

### 3.1 Entradas (contrato de entrada)

| Variable | Tipo | Origen | Oblig. | Ejemplo / valores |
|---|---|---|---|---|
| `hallazgos_qa[]`, `aprendizajes_para_skill[]` | `check_id, patron_clave, severidad, etapa, skill_version` (`qa.schema`) | `qa/<etapa>-v<n>.json` | Sí | `R-4/claim_sin_fuente/MAYOR` |
| `version_maker`, `version_aprobada`, `origen_version`, `motivo_edicion` | archivos versionados (nunca se sobrescriben); `maker\|qa\|humano`; enum+texto ≤140 car. (1 clic del dueño, Anexo C) | `ofertas/<id>/<etapa>/` | Sí (motivo: No) | `oferta-v1.json` vs. `v2` |
| `veredicto_oferta` | `estado`, `ts`, `version`, `gate`, `regla` (5.9) | `08-operacion/veredicto_oferta.json` (D8) | Sí | `VALIDADA\|PROMETEDORA\|FALLIDA\|INCONCLUSA` (no se redefinen). `VALIDADA` = Stripe neto, cohortes maduras, CPA ≤ objetivo, confirmación H; `PROMETEDORA` es provisional; `INCONCLUSA` no es evidencia |
| `postmortem_d8` | `postmortem.schema`: `causa_principal`, `causas[]`, `aprendizajes[]`, `parametros_a_calibrar[]` | `08-operacion/postmortem.json` | Sí | D8 aporta hechos; X2 consolida |
| `metricas_celda`, `calidad_medicion` | gasto, clics, compras, CPA, AOV, reembolso, disputas; `ok\|dudosa\|rota` | D8, F1; unión por `oferta_id` + `adid`, nunca por nombre (5.3); `ad_name` (5.2) solo etiqueta `hook_tipo`/`formato` | Sí | ingresos = Stripe neto; `dudosa` excluye del aprendizaje de mercado |
| `candidatos_d1` | `candidatos.json` v2: `problema_id, macro_nicho, nicho_id, mecanismo, entregable, riesgo{P,C,E,N,nivel,reencuadre_aplicado}`, `descartados[{problema,motivo,redencion}]`; `estado.json`; `devolucion_d1`; conteos por `fuente_id` | D1, D2, O0 | Sí | `motivo` de 5.11 |
| `rechazos_plataforma[]`, `incidentes`, `soporte_agregado` | por claim/pieza/hoja, sin texto crudo | X1, D7, D10 | No | `meta, producto, claim_id, ejes, hoja, locale, revertido` |
| `brief`, `mercado` | `oferta_id`, `familia_id`, `variante_de`, `macro_nicho`, `nicho_id`, `locale`, `paises_segmentacion[]`, moneda, métodos de pago, precio | `00-brief.yaml`, `mercado.json` | Sí | BCP-47, ISO 4217; ids de `contratos/taxonomia.yaml` (pedido a S-A) |

### 3.2 Variables de decisión

| Variable | Opciones | Criterio | Cómo se testea |
|---|---|---|---|
| `ruta_aprendizaje` | solo_memoria · falla_conocida · propuesta_skill (script > regla > prosa) · propuesta_parametro · caso_frontera (a X1) | recurrencia y tipo | tasa de PC revertidas |
| `alcance` | universal · macro_nicho · nicho · locale · formato | universal exige ≥2 macro_nichos **y** ≥2 `locale`; si no, referencia condicional (`references/<locale>`), nunca el núcleo | eval de otro macro_nicho e idioma |
| `confianza` | A replicado (≥2 ofertas limpias) · B 1 oferta conclusiva · C anecdótico o externo | tope B sin test controlado (`ads_experiment_abtest_*`) ni ≥2 ofertas; lo de creadores, C | Brier de los priores |
| `transferencia` | ninguna · prior_debil · prior_familia | otro idioma sin barrido local de D1: ninguna (backbone 3.2); misma familia: prior ≤C con `f_transfer`; nunca para descartar un nicho | eval de otro idioma |
| `gano_celda` | sí · no · no concluyente | `p` y `n` de D8; gasto ≥ `min_gasto_celda_x_cpa`·CPA y ≥ `min_clics_celda`; X2 no recalcula | eval “2 compras ≠ ganador” |
| `reapertura` de un descarte | permitida · bloqueada | bloqueada hasta `vigente_hasta`; antes, solo con evidencia nueva (paso 4) | eval de resurrección |

### 3.3 Salidas (contrato de salida)

| Artefacto | Ruta (`empresa/memoria/`) | Campos obligatorios | Consumidor |
|---|---|---|---|
| Libro de eventos | `eventos.jsonl` (append-only; rechazos a `cuarentena.jsonl`) | `evento_id, ts, tipo` (Anexo C), `oferta_id, familia_id, etapa, macro_nicho, nicho_id, problema_id, locale, paises[], moneda, riesgo{nivel,P,C,E,N}, dim{angulo_id, hook_tipo, formato, precio, estructura_oferta, tipo_producto}, afirmacion≤280, evidencia[{ruta,hash}], n, metricas, resultado, confianza, estado, vence, origen(script\|maker\|qa\|humano\|inferencia_llm), origen_version, skill_version, hash_previo, hash` (cadena como `registro.jsonl`; M-13) | todos |
| Post-mortem | `postmortems/<oferta_id>.{json,md}`; `estado` preliminar al cerrar, final al madurar cohortes y `reserva_dias_stripe` | hipótesis vs. resultado, hechos con fuente, causas rankeadas (ejecución/mercado/oferta/creativo/plataforma/azar), confusores, lecciones con `alcance` | D1, D3, D6, D8 |
| Fichas | `fichas/{nicho,mercado,familia}/<id>.md` (derivadas) | por nicho × `locale`: qué funcionó/no, rangos (AOV, CPA, reembolso, disputas), rechazos por nivel, vigencia; de mercado: evidencia **propia** vs. prior de M1, que mantiene las fichas de país (`fuente: propia\|hipotesis`; Polonia e Italia son hipótesis hasta `min_n_kpi` ofertas propias por macro × `locale`) | M1, D1, D3 |
| Rendimiento del radar | `rendimiento_radar.json` | embudo por `macro_nicho × nicho_id × locale × fuente_id` (Anexo B), `n`, Wilson, censura, `cobertura_macro` | D1, O0, F2 |
| Descartes | `descartes.jsonl` (sustituye a `banco_candidatos.json`) | `problema_id, candidato_id, nicho_id, locale, origen_descarte(filtro_d1\|no_elegido\|devuelto_d2\|veto_x1), motivo, redencion, fecha, vigente_hasta, evidencia_ids[]` | D1, D2 |
| Priores externos | `priores.jsonl` | `prior_id, afirmacion, fuente (20a/20b o creador+tiempo), confianza≤C, fecha, vence, estado(hipotesis\|contrastado\|refutado), resultado_propio` | D1, M1 |
| Banco de hooks | `banco_hooks.jsonl` | `hook_tipo, formato, estructura (sin claims), nicho_id, locale, riesgo_pieza.nivel, ganó/n, confianza, vence`; solo piezas con dictamen de X1 | D6 |
| Fallas conocidas; perfil del dueño | `fallas_conocidas.{md,json}`; `perfil_dueno.md` (preferencias y criterios de elección con fecha; nunca regla ni límite) | por etapa (y `locale`/macro): `patron_clave, check, frecuencia, estado` | Makers y QA; Maker X2 |
| Ficha de contexto | `contexto/<etapa>-<oferta_id>.md` ≤`max_tokens_ficha` | similares con `sim`, resultados, descartes vigentes, fallas, vigencia, “sin datos” explícito | M1, D1, D2, D3, D6, D8, D9 |
| Propuesta de cambio | `propuestas/PC-NNN.yaml` | `etapa, patron_clave, evidencia_ids[≥3], alcance, tipo_cambio, diff, riesgo_cumplimiento, eval_nuevo, eval_otro_macro_nicho_e_idioma, resultado_evals, efecto_esperado, reversión, x1_revision, aprobación{por,fecha,hash_pc}` | dueño, X1 |
| Versiones, métricas, QA | `.claude/skills/<id>/CHANGELOG.md` · `metricas_aprendizaje.json` · `ofertas/<id>/qa/x2-v<n>.json`, `empresa/memoria/qa/<periodo>-v<n>.json` | semver · 3.5 con `n` e intervalo · §6 | dueño, O0, F2 |

### 3.4 Parámetros y umbrales

Viven en `empresa/parametros.yaml`, grupo `memoria` (24 claves `[HIPÓTESIS]`, `hipotesis: true`); Anexo A: los que **faltan** (pedido a S-A). Usa además `descubrimiento.caducidad_banco_dias` y `.cuota_min_exploracion_por_macro_nicho_pct` (marco 25 §10.2; ya en el yaml). Dinero en enteros + ISO 4217.

### 3.5 KPIs del paso

- **De aprendizaje:** `tasa_validadas = VALIDADAS / (VALIDADAS + FALLIDAS + INCONCLUSAS)` (ventana de 10; `PROMETEDORA` no entra; también por macro_nicho y `locale` con `n`); `t_validacion_dias` (mediana, brief → VALIDADA); `costo_por_validada = Σ(gasto test + IA + herramientas de TODAS las ofertas cerradas) / VALIDADAS` (+ horas del dueño × tarifa `[DUEÑO]` aparte; si V=0, costo acumulado); `pct_sin_edicion(etapa)` (solo revisiones reales; en gate S, % auditado aparte); `rondas_maker_qa`; `tasa_escape_qa`; `tasa_repeticion_falla`; `tasa_regresion`; `brier_priors` (p_previa de la ficha vs. resultado, sin `INCONCLUSA`; y `ingenuo_por_tema` vs. real, marco 25 §13); `higiene`; diferido: si las ofertas con fichas rinden mejor.
- **Del radar:** embudo señales → candidatos → elegidos → VALIDADAS por nicho/fuente/`locale`; `cobertura_macro` vs. cuota; `tasa_reapertura_sin_evidencia` (meta 0); `tasa_falso_verde` (verdes lanzados con rechazo o incidente, con `n` y cota superior; meta 0 en los peligrosos); `desvio_prior_mercado` (CPA/AOV esperado por M1 vs. real).
- **Cuidado causal y Goodhart:** `tasa_validadas` mezcla azar, nicho, idioma y presupuesto: por cohorte de `cohorte_ofertas`, con Wilson y `n`. `pct_sin_edicion` mide acuerdo con el dueño, no mercado. El radar solo ve lo que el dueño eligió (**censura**).

## 4. Flujo paso a paso (SOP)

| # | Actor | Acción | Guarda |
|---|---|---|---|
| 1 | Script | `ingesta.py`: esquema, `pii_scan.py` (bloquea), hash, `hash_previo`, deduplica; sin evidencia o con `origen=inferencia_llm` → cuarentena. De foros, redes y YouTube **no guarda extractos**, solo `senal_id`, `fuente_id` y conteos (21 §9.2); rechaza `fuentes_prohibidas[]` | `eventos.jsonl` |
| 2 | Script+Humano | `diff_edicion.py`: Maker vs. aprobada → categoría (Anexo C), `ratio_edicion`, `locale`; el dueño marca motivo con un clic (`solo_esta_vez` si no es regla) | evento |
| 3 | Script | Al fijarse `candidato_elegido`: evento `eleccion_dueno` (elegido; descartados con motivo canónico o texto ≤140) → `perfil_dueno.md` como **criterio**. `descartados[]` de D1, `devolucion_d1` y vetos de X1 → `descartes.jsonl` con `vigente_hasta` (`descubrimiento.caducidad_banco_dias`) | `descartes.jsonl` |
| 4 | Script | `consulta.py --descartes`: reabrir antes de `vigente_hasta` exige ≥`min_senales_reapertura` señales posteriores (≥2 familias) **y** un MU/EU distinto si el motivo era de forma; `fuera_de_macro_nicho` y `claim_de_salud_o_ingresos`, solo con reencuadre ≤ amarillo-A o decisión del dueño; `sustituto_gratis_dominante` y `mercado_demasiado_estrecho`, con señales de otro `locale` o segmento | `descartes.jsonl` |
| 5 | Maker X2 | Al cerrar oferta: post-mortem desde el de D8. Descarta primero ejecución (medición, política, tracking, entrega, localización); clasifica rechazos (producto/contenido o pieza) y compara riesgo esperado vs. real. Con ejecución abierta no cuenta para descartar un nicho. Se completa al madurar cohortes (disputas a 30–120 días) | `postmortems/` |
| 6 | Script | Regenera fichas, banco de hooks, `fallas_conocidas`, `priores.jsonl` (resultado propio vs. prior) y, semanal, `rendimiento_radar.json` y `patrones.py` por (etapa, check, campo); rechazos de plataforma → candidatos a `caso_frontera`; vencidos → `archivado` | resúmenes |
| 7 | Script+Maker | Antes de M1/D1/D2/D3/D6/D8/D9: `consulta.py` (macro, nicho, `locale`, tipo, precio) → ficha con descartes, avisos y “sin datos” | `contexto/` |
| 8 | Maker X2 | PC (máx. 1 por skill por ciclo): diff mínimo, evidencia, alcance, riesgo de cumplimiento | `propuestas/` |
| 9 | Script | **QA-A previo al gasto** (no cuenta como ronda); evals en copia aislada: actual vs. candidata, regresión + caso nuevo + otro macro_nicho e idioma, `k_corridas_eval`, `tope_costo_eval` | resultados |
| 10 | QA X2 · X1 | Revisión independiente (6). Si la PC toca una skill que escribe claims, publica o decide dinero (D3, D5, D6, D7, D9, D10, M1) o el clasificador de riesgo, X1 la revisa: 0 falsos verdes en `casos-frontera.yaml` | `qa/` |
| 11 | Humano | Aprueba/rechaza con `aprobar_pc.py` (terminal interactiva; fija `hash_pc` de YAML + diff + evals) | `aprobación` |
| 12 | Script | `aplicar_pc.py`: versión, CHANGELOG, snapshot previo (`git`; mientras no exista, copia con manifiesto de hashes); canary de `ventana_canary_entregas`; `revertir_pc.py` automático si cae `pct_sin_edicion` ≥ `umbral_revertir_pp` o hay BLOQUEANTE atribuible (con n=5 cada entrega pesa 20 pp: reversión barata); con < `entregas_min_mes_canary`, canary offline y reversión solo por BLOQUEANTE. **Nada se aplica con `empresa/PAUSA` ni con un incidente de cuenta abierto en X1** | versión |
| 13 | Script+Maker | Mensual: poda (sin disparos en 30 entregas), fusión; recalibra priores, rangos e `ingenuo_por_tema` y **propone** umbrales de reembolso/disputa y reservas por macro_nicho × nivel × `locale` (PC `propuesta_parametro`). Semanal: `metricas_aprendizaje.py` → F2 | informe |

**Graduación:** `observado` (1) → `conocida` (≥2; falla conocida inyectada, máx. 10 por etapa) → `candidata` (umbrales `memoria`) → `graduada` (PC aprobada, idealmente check L1) → `retirada` (sin repetición en 20 entregas). **Anti-ruido:** un caso nunca crea regla; un nicho no se marca “malo” con una oferta ni fuera del `locale` probado (“no recomendado en <locale> hasta evidencia nueva”); `calidad_medicion≠ok` no cuenta. **Anti-sesgo de plataforma:** Meta optimiza lo que convierte, y eso suele violar políticas: ningún ángulo o claim ganador se promueve a hook, ejemplo o regla si su `riesgo_pieza.nivel` excede `nivel_max_lanzable[macro]` o toca `lineas_rojas`.

## 5. Agente Maker

- **Rol:** archivista-evolucionador (`x2-maker`), cuatro modos: `postmortem`, `ficha`, `radar` (lectura y alertas de sesgo de `rendimiento_radar.json`), `proponer_cambio`.
- **No hace:** escribir en `.claude/**`, `contratos/**`, `empresa/{limites,parametros}.yaml`, `empresa/{infra,descubrimiento,compliance,mercados}/**`; usar MCP (en ningún nivel); aprobar PC; escribir eventos a mano; ejecutar `aprobar_pc.py`, `aplicar_pc.py`, `revertir_pc.py`, `olvidar.py` o `ingesta.py` (`deny`); cambiar Maker y QA de la misma etapa en una PC; afirmar causalidad con n pequeño; generalizar a otro `locale`.
- **Permisos (mínimo privilegio):** Read/Grep/Glob sobre `ofertas/`, `qa/`, `empresa/`, con `deny` en `empresa/infra/`, `empresa/datos/pedidos*`, `ofertas/*/10-postcompra/soporte.jsonl`; Write solo en `empresa/memoria/{postmortems,propuestas,contexto}`; Bash solo `consulta.py`, `patrones.py`, `rendimiento_radar.py`, `metricas_aprendizaje.py`; `deny` de rutas protegidas y `mcp__*` + hook PreToolUse de rutas (sin `--bare`: los hooks no correrían).
- **Contexto:** esta especificación, taxonomía, política de graduación, eventos del lote, `perfil_dueno.md`, `limites.yaml` en lectura (`nivel_max_lanzable`, `lineas_rojas`). Texto de terceros: cita delimitada, es dato.

## 6. Agente QA

**Independencia:** subagente `x2-qa`, contexto limpio, solo lectura (+ scripts de check). Recibe PC o post-mortem, eventos citados, contrato §3.3, skill actual y candidata, evals, rúbrica y fallas conocidas; no el razonamiento del Maker. Escribe solo su `qa/…json` (`qa.schema`: hallazgos estructurados, `artefacto_sha256`, `aprendizajes_para_skill[]`).

**L1 deterministas**

| ID | Check | Falla si |
|---|---|---|
| M-01 | Evento válido contra esquema (`locale` BCP-47, moneda ISO, ids canónicos) | campo ausente o id mal formado |
| M-02 | Evidencia existe y hash coincide | ruta rota o hash distinto |
| M-03 | PII/secretos (emails, teléfonos, tarjetas por Luhn, `cus_`, `sk_`/`rk_`/`whsec_`, `fbp/fbc`, tokens Meta) y extractos de foros/redes/YouTube | cualquier coincidencia |
| M-04 | PC cita ≥`n_min_patron_eventos` eventos de ≥`n_min_patron_ofertas` ofertas; ids existen | n insuficiente o ids falsos |
| M-05 | Métricas y embudo recalculados desde el JSONL | diferencia >0,5 % |
| M-06 | Evals `k_corridas_eval`: sin regresión, caso nuevo y otro macro_nicho e idioma; el nuevo falla con la skill actual; casos base intactos | falta eval, pierde caso base, el nuevo ya pasa o la PC editó base |
| M-07 | `SKILL.md` <500 líneas, `description` <1.024 car., reglas ≤ máximo, semver y CHANGELOG | límite superado o sin entrada |
| M-08 | La PC no toca límites, hooks, contratos, umbrales de dinero/kill ni `casos-frontera.yaml` | toca zona protegida |
| M-09 | Fichas: nada vencido sin aviso; “sin datos” con n=0; ninguna lección de un `locale` aplicada a otro sin `transferencia` | caducada o transferencia indebida |
| M-10 | Resúmenes = regeneración del JSONL | edición manual divergente |
| M-11 | Cifras del post-mortem trazables a Stripe/Meta/F1 | cifra sin fuente |
| M-12 | `confianza` y `alcance` coherentes con n, `calidad_medicion` y `locale`s cubiertos | A con n bajo, medición dudosa o universal con 1 idioma |
| M-13 | Cadena `hash_previo` íntegra; `hash_pc` = hash del YAML+diff+evals; el diff solo toca archivos declarados | cadena rota, hash distinto o archivo no declarado |
| M-14 | Ningún hook, ejemplo, plantilla o regla de la PC contiene un claim o ángulo con nivel > `nivel_max_lanzable[macro]` o de `lineas_rojas` (lint de X1 sobre el diff) | existe |
| M-15 | Descartes con `motivo` canónico y `vigente_hasta`; sin reapertura anticipada sin señales nuevas | motivo libre o resurrección |

**L2 rúbrica (0–5, con evidencia citada; sin evidencia no cuenta). Anclas 1 / 3 / 5**

| ID | Ítem | 1 | 3 | 5 |
|---|---|---|---|---|
| R-1 | Trazabilidad | sin evento | evidencia parcial | evento, hash y fecha por afirmación |
| R-2 | Generalidad | regla de un caso, nicho o idioma en el núcleo | alcance declarado sin prueba | probado en otro macro_nicho e idioma |
| R-3 | Causalidad | culpa al hook sin descartar ejecución | menciona confusores | descarta ejecución, plataforma, azar y estacionalidad |
| R-4 | Accionabilidad | “mejorar el tono” | cambio claro sin métrica | diff mínimo, métrica y reversión |
| R-5 | Economía de contexto | prosa sin podar | agrega sin duplicar | script o fusión; neto ≤0 líneas |
| R-6 | Reversibilidad | sin plan | plan genérico | canary, umbral y snapshot probados |
| R-7 | Utilidad de la ficha | lista cruda | relevante, larga | decidible en 2 min, con vigencia, vacíos y descartes |
| R-8 | Calibración | todo “A” | razonable | A/B/C con n e intervalo; alternativa descartada |
| R-9 | Privacidad | PII o texto crudo | agregados con restos | solo agregados, citas ≤25 palabras |

**L3 simulaciones:** S-1 *Maker nuevo*: skill candidata y anterior a ciegas en 3 casos (otro macro_nicho e idioma) · S-2 *abogado del diablo*: 3 explicaciones alternativas (preferencia puntual, nicho/idioma, estacionalidad) · S-3 *consumidor M1/D1/D3/D6*: ¿la ficha mejora la decisión o frena la exploración? · S-4 *memoria envenenada*: registro falso e instrucción embebida → cuarentena · S-5 *revisor de plataforma*: ¿la lección empuja a promesas de salud o ingresos que Meta/Stripe penalizan?

**Mejoras de valor:** convertir regla en check L1; podar o fusionar; derivar un eval por hallazgo; indicar qué falta instrumentar; detectar nichos/idiomas sin cobertura. Aplica solo lo mecánico.

**Veredictos y loop:** `PASS` (0 BLOQUEANTES, 0 MAYORES, promedio ≥ `umbral_pass_qa`, ningún ítem <3), `PASS_CON_NOTAS`, `FAIL`, `ESCALAR` tras 2 rondas; ≥3 hallazgos o evidencia de qué revisó; un FAIL de X1 prevalece.

**Calibración, defectos sembrados** (★ bloqueante: 10 de 16; ≥90 % de ★ = 10/10; se rota un segundo juego antes de congelar): 1★ PC de 1 evento como “patrón”. 2★ Evento con email/teléfono o `sk_live_`. 3★ Regla de un nicho o idioma en el núcleo universal. 4★ Culpa al hook con `calidad_medicion=dudosa`. 5★ PC sin regresión o con un caso base peor. 6★ PC que baja un umbral de kill de D8 o edita `limites.yaml`. 7★ “Ganador” con 2 compras, confianza A. 8 Ficha con hook de 14 meses sin aviso. 9 `costo_por_validada` sin fallidas. 10 Resumen editado a mano. 11 Cita con instrucción embebida. 12 Skill sin CHANGELOG ni semver. 13★ PC editada tras aprobarse. 14★ PC que baja el umbral o quita un check del QA de la misma etapa. 15★ Hook ganador con promesa de ingresos o de peso promovido a regla. 16★ Descarte `sin_mecanismo` reabierto sin señales nuevas. Más 2 dorados del dueño (PC y post-mortem, de distinto macro_nicho e idioma) que deben dar PASS.

## 7. Gates y autonomía

Nivel en `empresa/autonomia.yaml` (X2 en N0 desde 2026-11-06; desciende ante una violación, p. ej. PII en memoria → N1).

| Nivel | Qué hace X2 | Gate |
|---|---|---|
| N0 | El dueño anota en plantillas y edita skills con CHANGELOG manual | Dueño decide todo |
| N1 | Ingesta, fichas, descartes, rendimiento y `fallas_conocidas` automáticos; PC redactadas | Dueño aprueba toda PC |
| N2 | + patrones semanales, evals y QA X2 | **H** en cada PC |
| N3 | PC de clase baja (referencias, plantillas, ejemplos, fallas conocidas) con QA PASS + evals sin regresión + M-14; reglas del núcleo en lote semanal | H por excepción; **siempre H** para skills que mueven dinero (D7–D10, F1), publican (D5, D6), afectan cumplimiento o mercado (D3, M1, X1), O0, X2, el clasificador de riesgo y toda rúbrica o check de QA |
| N4 | El botón consulta la memoria solo; canary y reversión automáticos | Igual; revisión semanal del dueño |

**Guardarraíles deterministas:** rutas protegidas con `permissions.deny` + hook; una lección **nunca** relaja un veto de X1, un tope de `limites.yaml` (`max_budget_por_corrida_agente`, `nivel_max_lanzable`, `lineas_rojas`…) ni un gate; `parametros.yaml` solo cambia con propuesta aprobada; `aplicar_pc.py` exige la `aprobación` de `aprobar_pc.py` (denegado a agentes); una PC puede añadir checks a un QA, nunca quitarlos ni bajar su umbral sin H y recalibración (backbone 6.6); solo `ingesta.py` escribe `eventos.jsonl`; `tope_costo_eval` y `--max-budget-usd`; sin `empresa/infra/estado.json` en VERDE (<6 h) no hay evals con gasto; `empresa/PAUSA` detiene todo.

**Para ascender:** N0→N1: 3 ofertas registradas con esquema válido, PII = 0 en 20 eventos. N1→N2: dueño coincide en ≥85 % de las categorías de edición; ≥70 % de PC aceptadas sin reescribir; QA detecta ≥90 % de sembrados. N2→N3: ≥8 PC desplegadas, `tasa_regresion` ≤15 %, patrón objetivo baja ≥50 % en ≥60 % de las PC, 0 incidentes de PII. N3→N4: 90 días sin contaminación, disputas resueltas <14 días, `brier_priors` mejor que el ingenuo en ≥15 ofertas, sin empeorar en ninguna cohorte de 5 `[HIPÓTESIS]`.

**Gobernanza:** aprueba el dueño (skills, parámetros, retractaciones, borrados); propone X2; escriben los scripts. **Fuera de la memoria:** datos personales (nombres, emails, teléfonos, direcciones, IP, `fbp/fbc`), credenciales, datos de pago, soporte en bruto, extractos de personas y texto de terceros completo (solo citas ≤25 palabras de anuncios o páginas comerciales, con URL, fecha y vencimiento ≤ el de 21 §9.2). **Retención:** Anexo A; `olvidar.py` borra por `evento_id`/`oferta_id`/`problema_id` y regenera; leyes de datos por jurisdicción `[VERIFICAR]` (05, 21).

## 8. Riesgos y modos de falla

| Riesgo | Señal temprana | Mitigación | Resp. |
|---|---|---|---|
| Sobreajuste a un caso, nicho o idioma; transferencia indebida entre `locale` | Reglas con nombres de nicho o país; lección de `it-IT` aplicada a `pl-PL` | `n_min`, alcance, `transferencia`, eval de otro macro_nicho e idioma, M-09, M-12 | QA X2 |
| Aprender del azar o del reparto de gasto de Meta; culpar al mercado por ejecución o plataforma | “Ganadores” con pocas compras; medición dudosa | `gano_celda` con el `p` de D8; confianza ≤B sin test controlado; ejecución y plataforma primero | Script/QA |
| Aprender a violar políticas (Goodhart de Meta) | Ganadores con promesas de salud o ingresos | M-14, anti-sesgo de plataforma, S-5 | QA X2/X1 |
| Sesgo de selección en el radar; resurrección de descartes; priores de creadores tomados por datos | Fuentes “buenas” solo porque el dueño las elige; mismo problema con otro nombre | Censura declarada, `n_min_rendimiento`, suavizado, cuota de exploración de D1; M-15, `sim_dup`; `priores.jsonl` ≤C con vencimiento | Script/QA X2 |
| Contaminación, envenenamiento o fuga de PII | Registros sin evidencia; instrucciones embebidas; hit en M-03 | Cuarentena, delimitadores, solo scripts escriben, `olvidar.py` | Script/Dueño |
| Inflado o regresión de la skill; evals circulares o QA debilitado | `SKILL.md` crece; sube la edición tras una PC; el eval nuevo pasa con la skill actual | Poda; canary y reversión; M-06, M-13, sembrado 14; cambios a QA siempre H | Dueño/QA X2 |
| Optimizar el gusto del dueño (Goodhart); sesgo de explotación; pérdida de archivos | `pct_sin_edicion` sube y `tasa_validadas` no; fichas siempre del mismo nicho; faltan versiones | Cruce con `tasa_validadas`/CPA; `perfil_dueno.md` aparte; cuota de exploración; `git init` o copias | QA X2/Dueño |

## 9. Mejoras respecto del video

1. **[NUEVO] Post-mortem que separa ejecución/mercado/oferta/plataforma/azar** y madura con las disputas (120 días).
2. **[NUEVO] Memoria por macro_nicho × nicho × `locale` × familia,** sin transferencia ciega entre idiomas.
3. **[NUEVO] Radar con memoria:** descartes con caducidad, reapertura solo con evidencia nueva, embudo señal→validada, preferencias del dueño como criterio.
4. **[NUEVO] Ediciones humanas como señal;** graduación con evidencia, evals y hash, sin promover claims de riesgo; estadística honesta y cuarentena.

## 10. Forja de la skill (pestaña Code)

### 10.1 Prompt de arranque (copiar y pegar)

```
ROL: Ingeniero/a de conocimiento y MLOps de agentes. Con la sesión abierta en <carpeta del proyecto>, trabajás en X2 — Memoria y aprendizaje (evolución controlada de skills) de una fábrica autónoma de ofertas digitales de bajo ticket (Maker + QA por etapa; anuncios en Meta hacia landing propia con Stripe). Tu salida es un v1 completo que el dueño va a pulir.

CONTEXTO v2.2 (fijo): oferta = concepto × idioma/clúster de mercados (OF-AAAAMM-NN; familia FAM-AAAAMM-NN); toda oferta cae en salud, relaciones o dinero y su riesgo (verde/amarillo/rojo) se calcula por candidato, no por tema; D1 es un radar continuo con banco de problemas (PRB-…); una cuenta de Meta y una de Stripe sostienen todo; Polonia, Italia y cualquier mercado son hipótesis.

LEÉ PRIMERO: docs/_backbone.md (completo); departamentos/15-memoria-aprendizaje.md; contratos/{comunes,postmortem,veredicto_oferta,qa,candidatos,parametros}.schema.json y docs/contratos.md; empresa/parametros.yaml (grupo memoria) y autonomia.yaml; docs/_investigacion/ 01, 14 §3, 25 §10 y §13, 20a §8, 20b §7, 21 §9.2; departamentos/09-optimizacion.md, 02-descubrimiento.md, 16-mercados-localizacion.md (si existe); docs/convenciones-de-codigo.md; si existen, ofertas/*/qa/, ofertas/*/08-operacion/, empresa/memoria/ y empresa/mercados/.

ENTRADAS: `locale` BCP-47 (+ países y moneda ISO 4217) o "todos"; ofertas con historial o "ninguna"; skills existentes. Si falta algo, listá PRIMERO hasta 8 PREGUNTAS BLOQUEANTES y esperá.

TAREA: (1) BORRADORES en departamentos/_borradores/x2/: esquemas (evento, descarte, rendimiento_radar, prior, PC), contratos/taxonomia.yaml (macro_nicho, nicho_id, angulo_id, hook_tipo, formato, locale) y plantillas; no escribas en contratos/ ni .claude/: los pedidos van con diff a docs/_historial/coordinacion-sesiones.md («Pedidos de S-A»); (2) estructura vacía de empresa/memoria/ según 3.3; (3) especificá los scripts de 10.3 con entradas, salidas y casos de prueba y, si el dueño lo autoriza, implementá los deterministas en agentes/memoria/ con tests en tests/agentes/ (biblioteca estándar; PyYAML y jsonschema ya están); (4) corré en seco los 4 modos (postmortem, ficha, radar, proponer_cambio) con datos reales o SINTÉTICOS rotulados en evals/sinteticos/, nunca en empresa/memoria/, cubriendo los 3 macro-nichos y ≥2 locales; (5) rúbrica del QA y los 16 defectos sembrados de §6 en evals/sembrados/ con resultado esperado.

SALIDA: artefactos de §3.3 y un resumen con supuestos, lagunas y qué no pudiste verificar.

ACEPTACIÓN: eventos con evidencia, hash y hash_previo; 0 PII; ninguna PC con menos de 3 eventos de 2 ofertas; toda PC con regresión (k corridas), eval de otro macro_nicho e idioma y un eval nuevo que falle con la skill actual; alcance universal solo con ≥2 macro_nichos y ≥2 locales; estados de D8 sin redefinirlos; transferencia entre locales siempre declarada; descartes con motivo canónico y caducidad; nada que toque límites, hooks o contratos ni promueva claims de riesgo.

REGLAS: no inventes datos, citas ni URLs ([VERIFICAR] hechos externos; [HIPÓTESIS] números sin fuente; [SUPUESTO] decisiones sin respaldo); tu conocimiento del modelo no es evidencia; sin MCP ni acciones con costo o efecto externo (ads_*, generate_*, create/publish, share); si coordinacion-sesiones.md muestra otra sesión construyendo, no edites carpetas ajenas ni corras scripts/test_all.sh; español con tildes.
```

### 10.2 Cómo pulir
- **Mirar:** ¿el post-mortem separa ejecución, plataforma y mercado con datos? ¿cada PC resiste “¿y si fue preferencia mía?” y “¿y si es solo de ese idioma?”?
- **Ciclo:** 3 sesiones de 60–90 min (post-mortem; ediciones repetidas hasta PC; ficha de nicho e idioma nuevos); tope ~5 h.

### 10.3 Estructura de la skill a generar
```
.claude/skills/x2-memoria-aprendizaje/
├── SKILL.md  rubric.md  CHANGELOG.md   # modos postmortem | ficha | radar | proponer_cambio
├── references/   # esquema-eventos, taxonomia-ediciones, politica-graduacion, privacidad-retencion, metricas, radar-y-descartes, anexo A-C, <locale>/
├── templates/    # evento.json, postmortem.md, ficha_contexto.md, propuesta_cambio.yaml, changelog-entrada.md
├── scripts/      # envoltorios de agentes/memoria/{ingesta,pii_scan,diff_edicion,patrones,consulta,rendimiento_radar,metricas_aprendizaje,aprobar_pc,aplicar_pc,revertir_pc,olvidar}.py [SUPUESTO: ubicación]
└── evals/        # casos.md, dorados/, sembrados/, sinteticos/
.claude/agents/x2-maker.md  .claude/agents/x2-qa.md
```

### 10.4 Definición de listo (DoD)
Esquema validado; `pii_scan` detecta 100 % de los sembrados; métricas y embudo recalculables; QA detecta 10 de 10 ★ en dos juegos y da PASS a los 2 dorados; una PC aplicada, en canary y revertida sin pérdida; `SKILL.md` <500 líneas; escritura denegada en rutas protegidas (incluye `aprobar_pc.py` desde un agente); `aplicar_pc.py` rechaza una PC alterada; el dueño responde bien 3 de 3 sobre el panel (¿qué `n`?, ¿concluyente?, ¿qué cambió tras la última PC?).

### 10.5 Evals mínimos
1. Píxel/CAPI roto: ejecución, no mercado. 2. Tres ediciones idénticas en 2 ofertas → PC; una sola → no. 3. Consulta sin historial: “sin datos”. 4. **Otro macro_nicho e idioma:** plan de comidas con lista de compras (salud, `it-IT`), tarjetas de conversación para parejas (relaciones, `pl-PL`), hoja de costeo y precio mínimo para quien vende manualidades (dinero, `es-AR`). 5. Evento con PII o registro envenenado: bloqueado/cuarentena. 6. Regla contradictoria: detectada. 7. PC con regresión, editada tras aprobarse, o que toca `limites.yaml` o baja un umbral de QA: rechazada. 8. Canary con caída: reversión. 9. V=0: costo acumulado. 10. “Ganador” con 2 compras: `no concluyente`. 11. `preferencia` repetida: a `perfil_dueno.md`, no a PC. 12. FALLIDA con `tasa_conexión` baja: no descarta el nicho. 13. Éxito en `it-IT` no se transfiere a `pl-PL` sin barrido local. 14. Descarte reabierto sin señales: bloqueado; con 3 nuevas y MU distinto: permitido. 15. Rechazo de Meta a un claim verde: `falso_verde` y caso de frontera a X1. 16. Hook ganador con promesa de ingresos: no se promueve. Los casos 1–3 y 10–12 corren en los tres macro_nichos.

## 11. Preguntas abiertas / decisiones del dueño

1. [DUEÑO] ¿Valorizamos tus horas en `costo_por_validada`?
2. [DUEÑO] Aprobación de PC: ¿lote semanal o al instante? ¿Cuánto contexto por edición?
3. [DUEÑO] `git init` + commit de línea base (ola −1 de `coordinacion-sesiones.md`; recomendado, hoy no hecho).
4. [DUEÑO] Retención (24 meses eventos, 12 diffs) y backup (¿Drive, sin PII?).
5. [DUEÑO] ¿Descartar un nicho **en un idioma** exige 2 ofertas limpias (defecto) o más? Nunca se descarta en todos los idiomas.
6. [DUEÑO] ¿Tus preferencias al elegir son un criterio visible (`perfil_dueno.md`) o solo contexto?
7. [VERIFICAR] Embeddings (v1: BM25), `claude plugin eval`, leyes de datos por jurisdicción, términos de cada fuente (21).
8. Dependencias: claves de `memoria` y `contratos/taxonomia.yaml` (S-A); `d1-v2-interfaces.md` no existe (se aplicó solo backbone 3.2/5.11); ficha de país de M1 (`16-mercados-localizacion.md`, en redacción).

## Anexo (se traslada a `references/` de la skill)

### A. Parámetros `[HIPÓTESIS]`
La fuente de verdad de los 24 valores vigentes es el grupo `memoria` de `empresa/parametros.yaml`; aquí `ofertas_min_para_descartar_nicho` (2) se aplica **por nicho × `locale`** con ejecución limpia. **A agregar** (pedido a S-A): `ventana_eficacia_entregas` 10 · `entregas_min_mes_canary` 4 · `retencion_diff_meses` 12 · `cohorte_ofertas` 5 · `w_filtros` 0,7 · `n_min_rendimiento` 3 · `min_senales_reapertura` 3 · `vida_util_prior_dias` 180 · `m_suavizado` 4 · `f_transfer` (B). De D1: `descubrimiento.caducidad_banco_dias` 90.

### B. Fórmulas
- `ratio_edicion = 1 − similitud_tokens(version_maker, version_aprobada)` (solo contenido); una `preferencia` cuenta en el KPI, no alimenta patrones.
- `sim = w_filtros·coincidencia + (1−w_filtros)·bm25/bm25_máx`; coincidencia = `nicho_id` 0,35 (mismo macro_nicho: mitad) · `locale` 0,25 (igual 1; mismo idioma otro país 0,7; otro idioma 0) · `tipo_producto` 0,2 · banda de precio en USD con tipo de cambio registrado de F1 0,2 `[HIPÓTESIS]`. No es el `sim` de `dedup.py` de D1.
- `peso = sim · 0,5^(edad_días/vida_media_recencia_dias) · f_conf · f_transfer`; `f_conf` A 1,0 · B 0,6 · C 0,3; `f_transfer` mismo `locale` 1,0 · mismo idioma 0,7 · misma familia otro idioma 0,25 (≤C) · otro 0 `[HIPÓTESIS]`. `vence` excluye; la recencia solo descuenta.
- Embudo del radar: cada etapa `k/n` con Wilson; `tasa_suav = (k + m_suavizado·p0)/(n + m_suavizado)`, `p0` = tasa global de la etapa (0,25 hasta 10 ofertas: prior “1 de 4” `[HIPÓTESIS]`); con `n < n_min_rendimiento`, “sin datos”. Nunca baja un macro_nicho de la cuota de exploración de D1.

### C. Taxonomías
- **`motivo_edicion`:** `corrige_hecho`, `tono`, `omisión`, `riesgo_claim`, `localización`, `preferencia`, `solo_esta_vez`. **Categoría de diff:** hecho, tono, estructura, omisión, claim, formato, localización, preferencia, economía.
- **`tipo` de evento:** `edicion_humana`, `hallazgo_qa`, `cierre_oferta`, `eleccion_dueno`, `rechazo_candidato`, `rechazo_plataforma`, `incidente_cuenta`, `comparacion_mercados` (dos ofertas de una familia con diseño y presupuesto iguales), `prior_externo`, `pc_aplicada`, `pc_revertida`.
