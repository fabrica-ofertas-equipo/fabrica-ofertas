> **v0.1 sin pulir (borrador generado desde la spec; v1.0.0 exige corrida manual del dueño, retro de 30-45 min y DoD firmados por el dueño).**

# CHANGELOG — o0-orquestador-portafolio

SemVer. Cada versión: qué cambia, qué falta para la siguiente.

## 0.1.2 — 2026-11-07 — modelado en la cadena y en la propuesta semanal (PENDIENTES A10)
Sigue siendo **v0.1 sin pulir**. Origen: `.claude/skills/modelado-oferta/PENDIENTES.md` sección A. **No cambia gates ni autonomía.**
**Aplicado:** `SKILL.md` §7 (cadena: modelado no es etapa del motor; dónde ocurre; costuras posteriores) y modo B paso 4 (la propuesta semanal puede citar, como conteo con su archivo, las ofertas con plan de mejora aprobado y las palancas medidas; no calcula ni compara palancas); `references/cadena-y-gates.md` §1 y `references/portafolio-y-propuesta-semanal.md` §1 (fila de entrada nueva).
**Falta (bloqueado: S-A/S-B)** `empresa/memoria/palancas.jsonl` (X2, MOD-9) y la etapa o gate de modelado en los contratos.

## 0.1.1 — 2026-11-06 — ajustes por la ingesta de S-A (SC-1…SC-9, SC-18)

Sigue **v0.1 sin pulir**. Fuente: `docs/_historial/ingesta-skills-cierre.md` §1 «O0» y §3.2. Solo se aplicó lo de spec CERRADA; lo derivado queda como `[PENDIENTE]` en `references/dependencias.md`.

- **SC-1** QA sin parches: `rubric.md` §6 y `o0-qa.md`: `correccion` por hallazgo (`devuelto_al_maker`), `cambios_aplicados = []`; el Maker aplica en la ronda siguiente.
- **SC-2** QA de solo lectura (`Read, Grep, Glob`) que recibe los checks de código en `qa/.l1/o0-v<n>.json` (o `empresa/qa/.l1/o0-<periodo>-v<n>.json`); sin ellos, «evidencia ausente» es BLOQUEANTE o MAYOR según el check (`rubric.md`, `o0-qa.md`, `dependencias.md` §D).
- **SC-3** `python -m scripts.nivel_riesgo` existe: fuera los `[PENDIENTE]` y la regla provisional «todo amarillo = B» (SKILL, rúbrica, cadena-y-gates, preguntas abiertas P10, briefs de ejemplo con el hash recalculado, evals); subnivel derivado de los colores si el snapshot no trae `ejes_codigo` (≥ 2 amarillos = B, `[SUPUESTO]`); `validar_brief.py` avisa AMARILLO-A/B (+1 prueba: 20). No se importa desde `validar_esquemas.py` ni `verificar_hwr.py`.
- **SC-4** `o0-maker` sin `WebFetch`/`WebSearch` ni `mcp__*` (ya cumplía en `tools`; regla explícita) y `o0-qa` solo `Read, Grep, Glob`.
- **SC-6** Libro de costos: `empresa/costos.jsonl`, lo escribe el motor; `orq ingresar` aún no asienta costos manuales `[PENDIENTE: SB-10, SB-8]` (ficha y `metodo-manual-y-ingresar.md`).
- **SC-7** Comandos reales de la CLI (`comandos-engine-orq.md` reescrito): `orq firmar` exige `--hash-objetivo` y `--clave-privada` (la ruta la pone el dueño: nunca en chats ni en el repo); `orq ejecutar` solo `--modo fixture --fixture DIR`; `reanudar` y `activar --live` no están en la CLI.
- **SC-8** No aplica a O0: sus claves reales son `orquestador.umbral_pass_o0` y `umbral_item_min_o0` (esquema, `parametros.yaml` y spec 00); no se usa `qa_pass_promedio_min` ni `umbral_pass_qa`.
- **SC-9** El aviso «v0.1 sin pulir» ahora dice que v1.0.0 exige corrida manual, retro y DoD firmados (SKILL, agentes, CHANGELOG). `.claude/skills/README.md` no es de esta skill: queda pedido.
- **SC-18** `dependencias.md` §A reescrito (existen `engine/orq.py` con sus 13 subcomandos, `engine/estado.py`, `engine.propuestas proponer|sellar` —no hay `engine.limites proponer|sellar`—, `scripts/nivel_riesgo.py`); `limites.boton_max_lanzamientos_dia` (en `limites`, no en `parametros`; valor del dueño; aún sin crear: LT-13); C-04 reescrita como «gate efectivo = H hasta que el dueño decida D-02» (las seis acciones no se pueden quitar ni con firma); C-06, `departamentos/02` en v1 y Anexo B resueltos o inexactos; la validación del brief no crea nada y `oferta_id` nace en `orq crear` tras el gate H (`orq validar` en seco antes: `[PENDIENTE: SB-8]`); pedidos al panel (`POST /ofertas`, `GET /bloqueos`, forma única `{motor_disponible, tipo, etapa, texto, comando}` de `proximo_paso`) en `dependencias.md` §F, sin tocar `dashboard/**`.

**Sigue `[PENDIENTE]` (de otros):** `portafolio.py` y banco de D1 (SB-18), `orq validar` y verificación de hash/firma del brief (SB-8, LT-54), `orq ejecutar` real (SB-9), costos manuales (SB-10), `activar --live` (B5), `variante_de`/`radar`/esquema `propuesta`/`boton_max_lanzamientos_dia`/`cuota_verde_topn_min_pct` (CT-3, CT-4).

## 0.1.0 — 2026-11-06 — borrador (sin pulir)

**Qué hay:** `SKILL.md` (modos A brief, B propuesta semanal, C explicar estado); `references/` (entrevista del brief ≤ 10 preguntas con defaults, cadena y gates, comandos `engine.orq` con su estado real, método manual y `ingresar`, botón y panel, cartera y propuesta, barreras y frenos, mapa de claves, dependencias, preguntas abiertas, cómo pulirla, glosario); `rubric.md` (13 checks L1 + rúbrica R14-R19 + L3); `templates/` (3 briefs borrador en `it-IT` dinero, `pl-PL` relaciones y `en-US` salud, estado de oferta nueva, QA del brief, propuesta semanal, ficha de ingreso manual); `scripts/validar_brief.py` (+19 pruebas); `evals/dorados` (7 casos: los 6 de §10.5 + salud en-US) y `evals/sembrados` (O0-S1…S18); agentes `.claude/agents/o0-maker.md` y `o0-qa.md`.

**Qué NO hay / es `[PENDIENTE]`:** todo `engine.orq`, `engine.estado`, `engine.limites proponer|sellar`, `portafolio.py`, `scripts/nivel_riesgo.py`, esquema `propuesta`, `variante_de` y `radar` en los contratos, interfaz de D1 v2 (`references/dependencias.md`). Evals no corridos con y sin skill; QA no calibrado; sin corrida manual del dueño.

**Contradicciones abiertas documentadas (no resueltas):** C-04 (`activar_campana` H siempre en `limites.yaml` frente a S en N3/N4 en `gates.json`: el botón de punta a punta nunca activaría) y C-06 (D1 a las 24 h en N3 frente a H hasta N3): `o0-lanzar-oferta/references/contradicciones-abiertas.md`. Pasos que exigen sesión interactiva: D1/D2 (Biblioteca de Anuncios) y D6 (Higgsfield).

**Hallazgo en el dorado:** `ofertas/_ejemplo/00-brief.yaml` incumple el check 2 del spec (`test_diario_max` = tope, debe ser ≤ tope ÷ `factor_techo_teorico_diario`): `dependencias.md` §B.6.

## Checklist de paso de 0.1 a 1.0.0 (cada ítem con evidencia reproducible; nada es «cumple» sin ella)

DoD de `docs/03-plan-de-forja-de-skills.md` §2.6 y de la spec `departamentos/00-orquestador-portafolio.md` §10.4, más W3/W6 de `docs/_historial/auditoria-pedidos-primera-sesion.md`.

- [ ] **Corrida manual del dueño** con una oferta real en la pestaña Code, y **retro de 30-45 min** (con el DoD firmado por el dueño) (`docs/03` §2.3: ediciones por categoría, reglas candidatas con ✔ del dueño, preferencias al perfil, checks L1 propuestos, ítems de rúbrica, 2 dorados y ≥ 10 defectos sembrados, ≤ 5 ambigüedades). Sin esto no se promueve.
- [ ] **Contrato 100 %:** salida válida contra su esquema en todas las corridas (`python -m scripts.validar_esquemas`); sin `float`, sin secretos.
- [ ] **Determinismo:** los scripts de la skill con pruebas verdes (`scripts/test_*.py`) y paridad con el motor cuando exista (`orq siguiente` = `proximo_paso.py`; `orq crear` repite `validar_brief.py`).
- [ ] **Evals:** ≥ 6 casos (`evals/dorados/`: §10.5 de la spec + otro nicho + otro idioma), **con skill > sin skill** en cada uno, en Sonnet y en Haiku (si Haiku queda por debajo, se documenta).
- [ ] **Estabilidad:** 3 corridas del mismo caso, decisión clave igual en ≥ 2 de 3.
- [ ] **QA calibrado:** 100 % de dorados en PASS y detecta **todos** los BLOQ de `evals/sembrados/` (juego rotado para que no se memorice); 0 falsos bloqueos.
- [ ] **Aceptación en sombra:** el dueño acepta ≥ 2 de 3 casos sin edición sustantiva `[HIPÓTESIS]`.
- [ ] **Forma:** `SKILL.md` < 500 líneas, `description` < 1.024 caracteres, referencias a un nivel, costo de contexto anotado (`/skill-doctor`).
- [ ] **Seguridad:** prueba de inyección (texto hostil en una cita del banco) pasa; sin secretos; sonda de guardarraíles 100 % `deny`; acciones con efecto detrás de gate.
- [ ] **Costo:** corrida dentro de `limites.max_budget_por_corrida_agente`, registrada en `costos.jsonl`.
- [ ] **Sin sobreajuste:** cero menciones del nicho del video; el caso de otro idioma (`pl-PL`) y otro macro-nicho pasan sin editar la skill entre casos.
- [ ] **Cumplimiento** (ningún candidato ROJO llega a un brief aprobable; X1 puede vetar).
- [ ] **Motor presente:** `engine.orq`, `engine.estado` y `scripts/nivel_riesgo.py` ya existen; falta `portafolio.py`, `orq validar`, `ejecutar` real y `activar --live`, y que sus criterios B0 pasen; transiciones ilegales rechazadas y replay exacto; oferta ficticia D1→M1→D7 en N1; kill switch ≤ `parametros.orquestador.pausa_global_max_min` también con un barrido en curso.
- [ ] **Decisión del dueño D-02** (C-04: gate efectivo H hasta que decida; C-06 ya está resuelta), y la lista de PEDIDOS de `o0-orquestador-portafolio/references/dependencias.md` §B (esquemas `variante_de`, `radar`, `propuesta`).
- [ ] **Alternativa por API** documentada para los pasos de sesión interactiva (D1/D2 Biblioteca, D6 Higgsfield) que el motor usará desde N3.
- [ ] **El dueño aprobó** un brief y una propuesta semanal de ejemplo (dorados reales).
- [ ] **Congelar:** aprobación del dueño, registro de versión `1.0.0` aquí y en `skills_pin` (`orq nivel --etapa O0 --a N1`); desde entonces los cambios solo entran por el script de aplicación de X2 con su aprobación. Si faltan solo ítems no innegociables: `0.9` con la deuda anotada.
