# CHANGELOG · x1-compliance

> **v0.1 sin pulir** (borrador generado desde la spec; v1.0 exige corrida manual del dueño, retro de 30-45 min y DoD firmados; no promover antes).

SemVer. Spec: `departamentos/14-compliance.md` (backbone v2.2.4; decisiones 7-15). Agentes: `.claude/agents/x1-maker.md`, `.claude/agents/x1-qa.md`.

## 0.1.2 · 2026-11-07 · veto de parecido con la expresión protegida (PENDIENTES A9)
Sigue **v0.1 sin pulir**. Origen: `.claude/skills/modelado-oferta/PENDIENTES.md` sección A.
**Aplicado:** `references/checklists-por-etapa.md`: filas **O-13** (D3) y **L-15** (D5) «Parecido con la expresión protegida» (solo oferta modelada; QM-01/02/06/07/12 de `modelado-oferta/rubric.md`; J13/J17/J18; la estructura de la landing se imita y no es motivo de veto) y la nota «Cuarto macro-nicho (J6/J9)» tras la tabla de D3: mientras los contratos y `macro.py` no lo admitan, el dictamen declara `[SUPUESTO]` el macro y recalcula P·C·E·N con `scripts.nivel_riesgo`.
**Falta (bloqueado: S-A/S-B)** el cuarto macro-nicho en contratos, `scripts/descubrimiento/macro.py` y el lint (F-01, F-12, F-22); `scripts/modelado/similitud.py` para QM-01/02/06/07. Ver `modelado-oferta/PENDIENTES.md` A9 y D.

## 0.1.1 · 2026-11-06 · ajustes por la ingesta de S-A (SC-1…SC-9, SC-19)

Sigue **v0.1 sin pulir**. Origen: `docs/_historial/ingesta-skills-cierre.md` §1 (X1) y §3.2; solo se aplicó lo cuya spec está CERRADA.

**Aplicado**
- **SC-1 / SC-2 / SC-19 (QA solo lectura):** `rubric.md` (regla 7 y checks L1) y `x1-qa.md` ya no «corrigen lo mecánico»: devuelven la `correccion` por hallazgo (`devuelto_al_maker`), `cambios_aplicados = []` y el Maker aplica el parche en la ronda siguiente (máx. 2). La salida de `lint_claims`, `html_checks`, `sha256` y nivel llega **del código** en `lint-x1.json` (`qa/.l1/x1-<etapa>-v<n>.json`); sin ella el hallazgo es BLOQUEANTE (L1-LINT, L1-HASH, L1-NIVEL, `html_checks` de D5) o MAYOR (el resto). `SKILL.md` §3 pasos 3, 7 y 11 en ese sentido. La plantilla `dictamen-pass-con-notas-d5.json` pasa el estado `corregido_por_qa` a `aceptado_con_nota`.
- **SC-3:** todo apunta a `python -m scripts.nivel_riesgo` (`nivel` en minúscula, `subnivel` aparte, `ejes_codigo`, `version_tabla`). Se **conserva** `scripts/nivel_ejes.py` como adaptador interno que delega (no es una segunda tabla; lo importan `validar_dictamen.py`, `correr_evals.py` y las pruebas) y nadie lo cita. Se quita la regla provisional «todo amarillo = B»; sin `ejes_codigo` se deriva de los colores (≥ 2 amarillos = B) `[SUPUESTO]`. `validar_dictamen.py` exige también `L1-NIVEL` en D2.
- **SC-4:** `x1-maker.md` sin `WebSearch`, `WebFetch` ni `mcp__*` (`disallowedTools: Agent, WebFetch, WebSearch, NotebookEdit`); esas herramientas existen solo en la sesión interactiva del dueño (Modo C y lecturas de Meta).
- **SC-7:** comandos reales (`python -m compliance.lint_claims|html_checks|sellar --etapa-objetivo|verificar|salud`, `python -m engine.propuestas proponer|sellar` en vez de `engine.limites`).
- **SC-9:** el banner «v0.1 sin pulir» dice que v1.0 exige corrida manual, retro y DoD firmados (`SKILL.md`, `como-pulirla.md`, este archivo). `.claude/skills/README.md` no es de esta skill: queda como pedido.
- **D2 como etapa consultiva:** descripción, `argument-hint`, Modo A, tabla de entradas, regla de decisión, ruta `qa/x1-d2-v<n>.json` y checklist D2 (`references/checklists-por-etapa.md`); sin sello; `x1_dictamen = pendiente` mientras no exista el dictamen.
- **Convención S-A (`contratos/comunes#nivel_lanzable`):** el nivel que puede lanzarse se escribe `verde`, `amarillo-a`, `amarillo-b` en **minúsculas con guion** (antes con la letra del subnivel en mayúscula, en SKILL, referencias, plantillas `matriz_pais_nivel`/`paises`/`limites.propuesta`, evals y agentes). `subnivel` sigue siendo `A|B`. 3 pruebas nuevas (20 en total: las 17 originales siguen en verde).
- **S-B ya construido (verificado en el repo):** reglas por locale it/pl/ro/fr/de/es-AR/es-MX y la categoría relaciones (`reglas_version` 1.1.0, `[HIPÓTESIS]`, sin revisor nativo), exclusión estrecha de `claims_prohibidos`/`claims_a_evitar` y de `tracking › campos_prohibidos`, léxico aditivo `terminos_sensibles/<locale>.yaml`, `--etapa D5` con el sitio, `html_checks` con «Quedan N» y «EJEMPLO»; `compliance/salud.py` + `scripts/x1_salud.py` con `regla_salud.py` y las 21 series como oráculo. `references/dependencias.md` reescrito con estados, LT y CT de cada pedido; `evals/README.md` y `checks-l1.md` con la cobertura actual (`correr_evals.py codigo`: 0 sin reglas de locale, 0/10 FP, 79/86 rojos vistos).
- **`dependencias.md` D-01 y `como-pulirla.md` §5 ítem 2 (INEXACTO):** NO importar. `scripts/nivel_riesgo.py`, `scripts/validar_esquemas.py` (X13) y `verificar_hwr.py` son tres implementaciones independientes **por diseño** (nota 25 §2.3). `taxonomia.yaml` y la matriz país × nivel quedan como pedidos con LT-20 / A-02 (S-21) y LT-13 / S-13.

**No aplicado (derivado; queda `[PENDIENTE]` en `dependencias.md`)**: hook de Bash con `python -m` (SB-4), `lint-x1.json` por el runner (SB-5/SB-6), emisor del sello de recolección (SB-15), checks M02-M05/K03/L1-09, `taxonomia.yaml` y MINOR de `riesgo` (CT-3), esquemas de la matriz, `decisiones_dueno.jsonl`, `salud_actual.json` y `sello_recoleccion` (CT-4), re-sellado de `_ejemplo/qa/x1-*` (LT-21, LT-50), y todo lo del dueño (líneas rojas, retención, firma de `paises.yaml`, `ratio_disputas_pausa`, revisor nativo). SC-8 no aplica a X1: la clave real es `compliance.umbral_rubrica_pass` (existe en `parametros.yaml`). SC-5 y SC-6 no tocan esta skill.

## 0.1.0 · 2026-11-06 · borrador

**Qué trae**
- `SKILL.md` (modos A-E, SOP del dictamen con «listo» por paso, decisiones con regla explícita, escalamiento, «Cómo pulirla»), `rubric.md` (R1-R8 con anclas 1/3/5 y críticos), 13 `references/`, `templates/` (2 dictámenes válidos contra `qa.schema.json`, checklist, simulación, YAML de países/matriz/reglas/términos/límites/recolección, dossier).
- **Núcleo de criterio:** riesgo por promesa, contenido, encuadre y modelo de negocio (nota 25 §1-§5), 30 líneas rojas, 15 reencuadres, la tabla ejes → nivel y la sustitución de la revisión legal por chequeo automático + plantilla + gate H del dueño.
- **Scripts deterministas probados** (17 pruebas): `nivel_ejes.py` (envoltorio de `scripts/nivel_riesgo.py`, que S-B promovió el 2026-11-06 y es la única implementación; 0 discrepancias sobre los 230 casos de la suite), `validar_dictamen.py`, `ngrama_copia.py`, `regla_salud.py`, `correr_evals.py`.
- **Evals:** 14 mínimos de §10.5; 17 legítimos que deben pasar; la **suite de 230 casos de frontera como eval central** (clasificador ciego: falsos verdes = 0, sobre-bloqueo ≤ 15 %, concordancia por eje ≥ 90 %); 33 sembrados (S01-S18 + S19-S33) con fixtures; corpus adversarial (96 frases); 21 series de salud; protocolo de retención.
- Agentes: Maker con herramientas mínimas y Bash acotado; QA solo lectura.

**Hallazgos de la corrida de evals contra el código real (`correr_evals.py codigo`, 2026-11-06)**
- El linter (`compliance/`) solo tiene reglas `es-ES` y `en-US`; it, pl, ro, fr, de, es-AR y es-MX **fallan cerrado** (no se pueden sellar).
- De 52 frases rojas es-* (voseo, tuteo, jerga) el linter ve 10; da un falso positivo sobre «comida sana»; `html_checks` no ve «Quedan N cupos» fijos ni «EJEMPLO». El QA (L2/L3) es la segunda red. Detalle y pedidos: `references/dependencias.md`.

**Qué falta para 1.0.0** (checklist completa de 18 ítems en `references/como-pulirla.md` §5)
1. **Dueño:** aprobar las 30 líneas rojas y `nivel_max_lanzable`; sellar el **conjunto de retención** (0 falsos verdes sobre ≥ 60 positivos, cota ≤ 5 %); firmar `paises.yaml` de v1; revisor nativo de it y pl; decidir impuestos con el contador; corrida manual de D3/D5/D6/D7 con retro de 30-45 min y aceptación en sombra.
2. **S-B (código):** promover `nivel_ejes.py` a `scripts/nivel_riesgo.py`; reglas por locale e integración de `empresa/compliance/terminos_sensibles/`; cobertura de voseo/jerga y de «Quedan N», «EJEMPLO»; `x1_salud`/`x1_pausa`; sello de recolección; allowlist de Bash; OCR/transcripción/visión/K03.
3. **S-A (contratos):** `contratos/taxonomia.yaml` `[PENDIENTE: no existe]`; MINOR de `riesgo` (`subnivel`, `ejes_codigo`, `banderas`…) y `riesgo_pieza`; alinear spec y esquema (`evidencia`/`correccion`, `semaforo` en minúscula); claves y parámetros pendientes de MINOR.
4. **Skill:** ampliar el corpus adversarial a ≥ 30 paráfrasis por categoría roja e idioma (incl. ro, fr, de) con revisor nativo; medir con y sin skill (Sonnet y Haiku); 3 corridas de estabilidad; prueba de inyección (10 textos hostiles).

**Supuestos principales** `[SUPUESTO]`: Maker entrega borrador y el informe del QA es el dictamen vinculante (P-08); un `locale` sin reglas es `ESCALAR`; el amarillo-b se resuelve con texto fiel a fuente T1 + gate H (sin «revisión profesional»); `es-ES` como proxy solo para medir es-AR/es-MX; formatos de `salud_actual.json` y similares sin esquema.
