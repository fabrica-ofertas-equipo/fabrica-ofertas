# CHANGELOG — d2-validacion (SemVer)

> **v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min).**

## 0.1.2 — 2026-11-07 — paso 7b: inmersión del mercado (PENDIENTES A6)
Sigue siendo **v0.1 sin pulir**. Origen: `.claude/skills/modelado-oferta/PENDIENTES.md` sección A.
**Aplicado**
- **A6** `SKILL.md` §5: paso **7b** (inmersión del mercado, J12, solo en ofertas modeladas) con `modelado-oferta/references/inmersion-mercado.md` (11 secciones, `corpus_citas.jsonl` con hash, reglas I-1…I-8, mínimos de suficiencia, 5 capas del QA lingüístico) y fila `inmersion/` en §3; `references/voz-del-cliente.md` §3 amplía las categorías de la frase (`jerga`, `queja`, `deseo`, `creencia`, `celebracion`, `referencia_cultural`, `humor`, `registro`, `convencion_pagina`), que viven en `inmersion/corpus_citas.jsonl` y solo pasan a `voz_cliente.json` las `visto`.
- **Adaptación con criterio:** en vez de un ítem **R8** nuevo (que habría roto «R1-R7» en `d2-qa.md`, el mapeo a `qa.schema.json` y los sembrados), el criterio de inmersión se añadió al ancla 5 de **R4 Voz del cliente** (con la evidencia `inmersion/corpus_citas.jsonl`).
**Falta (bloqueado: S-A)** el campo `inmersion.estado` y el contrato de `inmersion/` (hoy hermano sin esquema); sin ellos, «D3 no arranca si `inmersion.estado ≠ suficiente`» se comprueba leyendo. Ver `modelado-oferta/PENDIENTES.md` D.

## 0.1.1 — 2026-11-06 — ajustes por la ingesta de S-A (SC-1…SC-11)
Fuente: `docs/_historial/ingesta-skills-cierre.md` §1 (D2) y §3.2. Sigue siendo **v0.1 sin pulir**: la v1.0.0 exige corrida manual, retro y DoD firmados por el dueño (SC-9). Solo se aplicó lo cuya spec está CERRADA; lo derivado queda en `references/dependencias.md` como `[PENDIENTE: …]` con su LT/SB/CT.

**Aplicado**
- **SC-1** (QA no corrige): `rubric.md` y `d2-qa.md` devuelven `correccion` por hallazgo (`estado: devuelto_al_maker`), `cambios_aplicados = []`; fuera la facultad de «corregir MENORES». No había `aplicar_parche`, `scripts/qa/*` ni `corregido_por_qa` en D2.
- **SC-2** (QA de solo lectura con L1 de código): el L1 llega en `qa/.l1/d2-v<n>.json`; sin él, «evidencia ausente» es BLOQUEANTE (D2-D6, D9-D10, D11, veredicto incoherente, PII) o MAYOR; no toma resultados del Maker. La réplica (Jaccard) la calcula el código.
- **SC-3 / SC-7** (riesgo): `python -m scripts.nivel_riesgo` en SKILL (paso 8 y regla de riesgo), `rubric.md` D10, `etica-y-politica.md`, `preguntas-abiertas.md`, `d2-maker.md` (Bash) y sembrado S15; fuera los `[PENDIENTE]` y la regla provisional «amarillo sin subnivel = B»; sin `ejes_codigo` se derivan de los colores (≥ 2 amarillos = B) `[SUPUESTO]`.
- **SC-6** (costos): libro `empresa/costos.jsonl` escrito por el motor; el Maker deja el borrador `02-validacion/costos.jsonl` (SKILL §3, `etica-y-politica.md`, `d2-maker.md`, `rubric.md` D1).
- **SC-8** (umbral del QA): `qa_pass_promedio_min` → `validacion.umbral_qa` en `rubric.md`, `d2-qa.md`, `parametros_d2.propuesta.yaml`, `parametros-y-glosario.md` y `preguntas-abiertas.md`.
- **SC-9**: SKILL, CHANGELOG y registro de promoción (abajo) dicen que nace v0.1 y que v1.0.0 exige corrida, retro y DoD firmados.
- **SC-11** (los 11 puntos): (1) preflight manual con `entradas.D1` y `entradas.M1` y aclaración de que el preflight real es del runner y `engine.orq`; (2) D10 con `scripts.nivel_riesgo`; (3) QA sin `crudo/` ni `evidencia/` (claims con cita ≤ 200 caracteres entre `<<DATO_NO_CONFIABLE>>…<<FIN>>`; la clasificación ciega D7 sale del paquete de claims del L1); (4) `umbral_qa`; (5) `tipo_hook` alineado a la taxonomía de D6 (mapeo sugerido, a confirmar con D6) y plantilla `ficha_competidor.json` actualizada; (6) `ngrama_copia.py` de `x1-compliance` citado como L1 D6; (7) fuera `video_analysis_create` del Maker, de `voz-del-cliente.md` y de `etica-y-politica.md`; (8) actor de los pasos 2, 4 y 11 (re-lectura = paso 12 de la spec) = el Maker en sesión Code; (9) 3 snapshots por competidor por defecto (`snapshots_por_competidor` 3; humano ≈ 15 + 15 = 30 min); (10) dependencias #1, #10, #13 resueltas y #16 parcial; (11) D2 como etapa consultiva de X1 (`qa/x1-d2-v<n>.json`, sin sello).
- Veredicto oficial = `scripts.validacion.veredicto_d2` (`calcular|comprobar`, verificado con el fixture del repo); `veredicto.py` queda como copia de paridad.

**Diferido** (en `dependencias.md`)
- **SC-10** (retirar `metricas.py` y `veredicto.py`): no aplicado; `metricas.py` no tiene reemplazo y la spec y la prueba de paridad del repo los conservan (#20).
- Arnés L1 y réplica (#12, SB-6/SB-18), sembrados (#18), `TABLA_ETAPAS["D2"]` (#11, SB-4), QA-A previo en `qa/` (#21, LT-43/SB-11), MINOR `validacion` 1.1.0 y esquemas hermanos (#4-#5, CT4-11…15), `validacion.umbral_qa` y claves † (#6, LT-40/LT-45), `taxonomia.yaml` (#3, LT-20/LT-23), `variante_de` en el brief (#22, LT-02), `lint_claims` por locale (#23, SB-14), y lo del dueño (#7, #8, #14).
- Sin cambio por ya estar resuelto: `motivo_rechazo` con `linea_roja_de_contenido_o_negocio` (ya en `comunes` 1.4.0, #17); SC-4 y SC-5 no alcanzan a D2 (D2 conserva web y `ads_library_search`; no maneja ranuras de `assets`).

## 0.1.0 — 2026-11-06 — borrador generado desde `departamentos/03-validacion.md`
Primera versión, generada por Claude Code ejecutando el §10.1 de la spec **sin** corrida manual del dueño ni retro. Estado: `0.1.0` borrador; el runner no la promueve.

**Qué trae**
- `SKILL.md` (pasos 0-12 con criterio de «listo», reglas de decisión, NUNCA, escalado, KPIs, cómo pulirla) y `rubric.md` (L1 D1-D11, L2 R1-R7 con anclas, L3, calibración).
- **Rutina «D2 sin la herramienta del video»** (`references/protocolo-biblioteca.md` §4): reparto máquina/dueño con minutos (máquina ≈ 45; dueño ≈ 25 de lectura + ≈ 15 de verificación), hoja de lectura del dueño y tabla de verificación del informe para que `anuncios_competencia.json` traiga ≥ 4 competidores con promesa, mecanismo y enlaces verificables en ≤ 15 min.
- `references/`: protocolo de la Biblioteca, límites de inferencia, taxonomías (M1-M8), voz del cliente, ética y política, fórmulas y veredicto, parámetros y glosario (+ `parametros_d2.propuesta.yaml`), dependencias `[PENDIENTE]`, preguntas abiertas, cómo pulirla.
- `scripts/` (solo biblioteca estándar y PyYAML; sin red ni secretos; 89 pruebas): `metricas.py` (SS_a, N_ind_sost, IS, saturación de mecanismo, convergencia, confianza, huecos), `veredicto.py` (veredicto calculado y comprobación de que el Maker no lo mejora), `qa_recomputar.py` (recálculo independiente con `Fraction`; coincide con diferencia 0 en 600 casos aleatorios), `normalizar_biblioteca.py` (crudo → portafolios, sonda, selección de competidores y de ≤ 25 snapshots), `verificar_citas.py`, `verificar_competidores.py`, `params.py`. Vectores de la spec: SS_a **0,233** y **0,675**.
- `templates/` (plan, ficha de competidor, voz, devolución a D1, informe, hoja de lectura del dueño, entrada de métricas, `validacion.json` válido contra `contratos/validacion.schema.json`) y `evals/` (17 casos, 11 dorados sintéticos que cubren GO/GO_CONDICIONAL/NO_GO en 7 idiomas y 3 macro-nichos, 19 sembrados con su salida esperada).
- Agentes `.claude/agents/d2-maker.md` y `.claude/agents/d2-qa.md`.

**Lo que NO cubre todavía (deuda para 1.0.0)**
- Ninguna corrida con datos reales ni retro del dueño; los dorados son sintéticos y **no están aprobados por el dueño**.
- Parámetros † sin integrar en `empresa/parametros.yaml`; `max_consultas_biblioteca` y `costo_max_validacion` en `null` (nada se consulta hasta que el dueño los fije).
- `nivel_riesgo.py`, `matriz_pais_nivel.yaml`, `taxonomia.yaml`, esquemas de los archivos hermanos, `preflight.py`, arnés L1 del QA, arnés de sembrados, allowlist de Bash del runner, chequeo de n-gramas (`references/dependencias.md`).
- Captura automática de snapshots (frenada; `[DUEÑO]`); programador de la re-lectura; el conector no existe en el runner (etapa semiasistida, tope N2).
- Minutos de la rutina y valores de IS, `umbral_ss`, `mecanismo_share_*` son `[HIPÓTESIS]` sin calibrar.
- Sin medir con vs. sin skill (Sonnet y Haiku) ni estabilidad en 3 corridas.

**Checklist para pasar a 1.0.0** (todos antes de promover; ★ innegociable): ☐★ 3 corridas manuales del dueño (≥ 2 macro-nichos, ≥ 2 idiomas, ≥ 1 sin GO) con retro de 30-45 min cada una y ≥ 2 aceptadas sin edición sustantiva · ☐★ `validacion.json` válido contra su esquema y sin ROJO avanzando ni afirmaciones de rentabilidad · ☐★ ≥ 4 competidores verificables por el dueño en ≤ 15 min en una oferta real (auditoría W8) · ☐★ `metricas.py` y `qa_recomputar.py` con diferencia 0 en dorados reales · ☐★ QA calibrado: ≥ 90 % de bloqueantes sembrados (siempre S12 y S15), dorados en PASS, 0 falsos verdes en la muestra de `casos-frontera.yaml` · ☐★ prueba de inyección y sin secretos · ☐ dorados reales aprobados por el dueño (≥ 1 GO, ≥ 1 GO_CONDICIONAL, ≥ 1 NO_GO) · ☐ ≥ 6 evals con skill > sin skill y estabilidad 2 de 3 · ☐ parámetros aprobados e integrados; `limites` fijados · ☐ dependencias críticas resueltas · ☐ ciclo y costo en tope · ☐ forma (`SKILL.md` < 500 líneas, `description` < 1.024 caracteres) · ☐ este CHANGELOG con la entrada 1.0.0, tag `skill/d2-validacion/v1.0.0` y D2 en N1 en `empresa/autonomia.yaml`.

## Registro de promoción (formato de `.claude/skills/README.md`; una fila por versión, nunca se borran)
| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-06 | — | — | — | generada desde la spec |
| 0.1.1 | borrador sin pulir | 2026-11-06 | — | — | — | ajustes por la ingesta de S-A (SC-1…SC-11); sin corrida |
| 0.1.2 | borrador sin pulir | 2026-11-07 | — | — | — | paso 7b: inmersión del mercado (PENDIENTES A6); sin corrida |
| 1.0.0 | **v1** | AAAA-MM-DD | OF-… · … · a mano | ruta al informe | `dueño` AAAA-MM-DD | pendiente: corrida manual, retro y DoD |
