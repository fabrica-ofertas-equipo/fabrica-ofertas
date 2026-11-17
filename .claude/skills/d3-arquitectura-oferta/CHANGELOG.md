# Changelog de d3-arquitectura-oferta (SemVer)

v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min)

## 0.1.3 — 2026-11-07 — modo `modelado` (PENDIENTES A3-A4)
Sigue siendo **v0.1 sin pulir**. Origen: `.claude/skills/modelado-oferta/PENDIENTES.md` sección A. Nota de versión: el `SKILL.md` ya decía 0.1.2 (J16, el precio frontal sale de la escalera 17/19/27 US$) sin entrada de CHANGELOG; queda constancia aquí y la numeración continúa en 0.1.3.
**Aplicado**
- **A3** `SKILL.md`: fila `modelado` en la tabla de modos; pasos **3b** (oferta base y plan de mejora: copia la oferta del referente y aplica solo las palancas aprobadas) y **9b** (antes/después con `modelado-oferta`, MOD-6); en el paso 1, ampliar el rango de niveles no es re-elegir el problema pero se declara en `supuestos[]` (F-43); en el paso 7, `NO_FACTIBLE` en modo `modelado` detiene también el modelado.
- **A4** `rubric.md`: ítem **L1-16** (modo `modelado`: `qa_modelado.json` sin BLOQUEANTE, tabla «referente → nuestra oferta» en `oferta.md` §G, tamaño, niveles y tipos de bonus iguales al desarme) y entradas del QA en modo `modelado`; `references/contratos-y-rutas.md`: fila de `modelado/{desarme_referente, plan_mejora, antes_despues}.json`; `templates/oferta.md`: sección **G. Modelado**.
- `.claude/agents/d3-maker.md` y `d3-qa.md`: entradas de `modelado/` (solo lectura) en modo `modelado`; versión alineada a 0.1.3.
- **Adaptación:** L1-16 no dice «`lint_d3` + tú»: `lint_d3.py` aún no lo comprueba, así que figura «tú (lectura)» y `no_aplica` fuera del modo `modelado`.
**Falta (bloqueado: S-A/S-B)** el chequeo por código de L1-16 (`scripts/modelado/similitud.py`), el MINOR de `oferta.schema.json` con el bloque `modelado` y `marca_propuesta[]`. Ver `modelado-oferta/PENDIENTES.md` B2 y D.

## 0.1.1 — 2026-11-06 — ajustes por la ingesta de S-A (SC-1…SC-9, SC-12)
Sigue siendo **v0.1 sin pulir**: la 1.0.0 exige una corrida manual del dueño con una oferta real, la retro de 30-45 min y el DoD firmados por el dueño (SC-9). Fuente: `docs/_historial/ingesta-skills-cierre.md` §1 (D3) y §3.2. Pruebas: 50 OK (eran 30; 3 estaban rojas por el cambio de `compliance.lint_claims`).

**Aplicado**
- **SC-1, SC-2** (QA de solo lectura): el QA no corrige ni aplica parches; cada hallazgo lleva `correccion` y `estado: devuelto_al_maker` y `cambios_aplicados = []`; el Maker aplica el parche en la ronda siguiente. Los L1 los lee de `ofertas/<id>/qa/.l1/d3-v<n>.json` (antes `qa/d3-v<n>-l1.json`, que X18 habría rechazado); sin ellos, «evidencia ausente» con la severidad de cada check y nunca PASS. (`rubric.md`, `d3-qa.md`, `d3-maker.md`, `SKILL.md`, `contratos-y-rutas.md`.)
- **SC-3, SC-12 (a)**: `scripts/_tabla_riesgo.py` borrado; `medir_frontera.py` usa `scripts.nivel_riesgo.calcular` y `test_scripts.py` prueba la paridad con los 230 casos de la suite (más `verificar_suite`). `SKILL.md` paso 8 y el Maker usan `python -m scripts.nivel_riesgo`.
- **SC-4**: **ya estaba resuelto en D3**: `d3-maker.md` no concede `WebFetch`, `WebSearch` ni `mcp__*` (y los lista en `disallowedTools`); se explicita en el cuerpo del agente. Resuelta la entrada B3 de `dependencias.md`.
- **SC-7**: comandos reales verificados (`python -m engine.factibilidad calcular|verificar`, `scripts.validar_esquemas oferta`, `scripts.nivel_riesgo`, `compliance.lint_claims --archivo … --locale …`; `engine.propuestas proponer`, no `engine.limites`). D3 no usa `orq`.
- **SC-8**: `economia.umbral_qa` en la rúbrica (antes `orquestador.umbral_pass_o0` y `umbral_item_min_o0`, que son de O0).
- **SC-9**: la frase «v0.1 sin pulir» precisa qué exige la 1.0.0 en `SKILL.md`, `rubric.md`, `como-pulirla.md` y los dos agentes.
- **SC-12 (b)** `marca_propuesta[]`: hasta 3 marcas neutras `{nombre, dominio}` en la cabecera de `oferta.md` y en §E (el campo no está en `oferta.json`); L1-13 comprueba ≤ 3, sufijos vedados, verbos de cambio, nombres de estado, «ganar» y marcas de terceros; el Maker nunca compra dominio ni crea dataset. Añadida a las tres doradas.
- **SC-12 (c)** `preguntas-abiertas.md` fila 4: un mercado a la vez (R-C01), sin par de arranque; resueltas P1-P4.
- **SC-12 (d)** Pulido: la categoría va como prefijo del título (`dashboard/pulido.py` no tiene campo de categoría); A13 resuelta.
- **SC-12 (e)** `economia_por_pais.py` lee `estadistica.meta_eventos_aprendizaje_semana` y `estadistica.meta_fraccion_min_purchase` (fracción × 10000 = bp), falla con 5 si faltan y rechaza un valor distinto en el plan; la plantilla del plan ya no lleva las constantes.
- **SC-12 (f)** `lint_d3` L1-12: el rango del bump es solo `landing.bump_pct_precio_min/max` (sin el 40 % fijo, que queda como recomendación [HIPÓTESIS]); sin `--parametros` lo dice en el detalle.
- **SC-12 (g)** severidades: S5, S17 y S21 BLOQUEANTES (20 en total), S12 MAYOR (Anexo A.1); calibración ≥ 18 de 20. `sembrados.yaml`, tests, `rubric.md`, `anexo-sembrados.md`, `evals/README.md`.
- **SC-12 (h)** `puntaje_ciego` en `simulaciones_l3`: **ya estaba**; se precisa el formato y se remite a `dependencias.md` A11 (campo propio en CT-4, LT-34).
- **SC-12 (i)** `nivel_max_lanzable` `null` = SOLO VERDE (fail-closed; no «sin gasto autorizado»): `SKILL.md`, regla 8 y paso 8, `rubric.md` L1-11, `riesgo-y-reencuadres.md`, `devoluciones-y-escalado.md`, `dependencias.md` A7.
- **Cambio de `compliance` (S-B)**: it-IT, pl-PL, ro-RO, fr-FR y de-DE ya tienen reglas (`reglas_sensibles.yaml` 1.1.0, `revision_nativa: false`). L1-03 corre y avisa «SIN revisión nativa»; sigue fallando cerrado en un locale sin reglas. Adaptado: el reconocimiento de la ficha localizada (`## Karta oferty (12 punktów)`, que antes dejaba la ficha polaca sin lintear), la garantía del dorado it-IT («ti rimborsiamo» es ROJO por `garantias_absolutas`), el gancho y la ficha del dorado pl-PL («zwrot pieniędzy»), el sembrado S3 (la regla ya no ve «copias») y las pruebas de L1-03.
- `dependencias.md` reescrito con el estado de cada ítem de D3 del cierre (CERRADO, RESUELTO, DERIVADO a CT-3, CT-4, S-B o al dueño) y sus LT/SB.

**Diferido (en `dependencias.md`, no aplicado)**: campo `marca_propuesta[]` y `riesgo.{subnivel, ejes_codigo, version_tabla}` en `oferta` (CT-3/CT-4), campo QA del puntaje ciego (LT-34), clave `economia.umbral_qa` (LT-45), `economia.escenarios_costo`, esquemas `parada`/`devolucion_d1`/`voz_cliente`/`anuncios_competencia`, `TABLA_ETAPAS["D3"]` (SB-5), etapa de L1 previa al QA (SB-6), reglas y revisión nativa de X1 (SB-14), `lint_claims` sobre `reencuadre_aplicado.descripcion` (SB-15), `version_tabla` (SB-18), `_ejemplo` (LT-33).

**No aplica a D3**: SC-5 (campos de `assets`: D4/D5/D6), SC-6 (libro de costos: D3 no gasta créditos), SC-10 y SC-11 (D2).

## 0.1.0 — 2026-11-06 (borrador)
Generada por un agente forjador desde `departamentos/04-oferta.md` (§10.1-10.5, SOP del §4, Anexo), `docs/_backbone.md` v2.2, `docs/contratos.md`, `contratos/{oferta,economia,qa,candidatos,comunes}.schema.json`, `engine/factibilidad.py` 1.2.0, la nota 25 y `ofertas/_ejemplo/`. **Ningún caso se corrió con el dueño ni con el Maker/QA reales todavía.**

**Incluye**
- `SKILL.md` (SOP de 12 pasos con «listo cuando», modos `crear`/`revisar`/`variante`/`clasificar_riesgo`/`práctica`), 15 `references/`, `rubric.md` (L1 + L2 R1-R11 con anclas y críticos + puntaje ciego 0-100 + L3), 7 `templates/`.
- `scripts/` con 30 pruebas (`.venv/bin/python -m unittest discover -s .claude/skills/d3-arquitectura-oferta/scripts -p 'test_*.py'`, OK): `economia_por_pais.py` (envoltorio de `engine.factibilidad`, sin fórmula propia), `lint_d3.py` (L1-02/03/04/05/06/07/09/10/12/13), `medir_frontera.py` (falsos negativos peligrosos), `aplicar_sembrado.py`, `_tabla_riesgo.py` (réplica de la tabla ejes → nivel, probada contra los 226 casos de la suite).
- `evals/`: 3 ofertas doradas completas (es-ES dinero, it-IT salud, pl-PL relaciones; las tres pasan `validar_esquemas oferta` y `lint_d3`), 9 casos dorados (`casos.yaml`) con números del motor, 25 defectos sembrados (18 con detección determinista comprobada por los tests) y `frontera/` (cómo medir 0 falsos negativos peligrosos).
- Agentes `.claude/agents/d3-maker.md` y `d3-qa.md` (QA de solo lectura).
- Decisión de frontmatter: **sin `disable-model-invocation`** porque D3 no mueve dinero, no publica ni activa (propone y el motor calcula).

**No cubre / falta para 1.0.0** (el DoD completo está en `references/como-pulirla.md` §4-§5)
1. Una corrida manual del dueño con una **oferta real** y retro de 30-45 min; 3 ofertas de práctica con ≤ 3 ediciones (DoD a).
2. QA calibrado: ≥ 90 % de bloqueantes sembrados y PASS a las doradas (c); coincidencia Maker-QA ≤ 10 puntos en 80 % (e); evals 2-6 sin editar la skill entre uno y otro (g).
3. **Conjunto de retención de la suite de frontera [PENDIENTE: lo sella el dueño]** (n ≥ 60 positivos, cota ≤ 5 %): hoy el «0 falsos negativos peligrosos» solo puede medirse en `desarrollo` y `rt`, sin certificar (d).
4. Reglas de X1 para it-IT, pl-PL y otros locales (L1-03 falla cerrado), `terminos_sensibles`, `ayuda_por_pais`, `matriz_pais_nivel`; `tarifas.json` y tipos de cambio de F1; claves de parámetros (`economia.escenarios_costo` y las demás de `dependencias.md` A6); `scripts/nivel_riesgo.py`; esquemas `parada`, `devolucion_d1`, `voz_cliente`; campo QA para el puntaje ciego; ajustes del runner (ver `references/dependencias.md` A y B).
5. Prueba de inyección (texto hostil en fuentes), estabilidad (3 corridas), costo medido y comparación con/sin skill en Sonnet y Haiku (`docs/03-plan-de-forja-de-skills.md` §2.4-2.6).
6. Revisión nativa del texto en italiano y polaco de las doradas.

## Registro de corridas que respaldan cada versión
| Versión | Fecha | Corrida (oferta_id, quién, modo) | Ediciones del dueño por categoría | Resultado del QA | Retro |
|---|---|---|---|---|---|
| 0.1.1 | 2026-11-06 | ninguna: ajustes por la ingesta de S-A (SC-1…SC-9, SC-12); pruebas de scripts (50 OK), dorados con `validar_esquemas oferta` y `lint_d3` sin semilla provisional | — | sin QA corrido | pendiente |
| 0.1.0 | 2026-11-06 | ninguna: borrador generado desde la spec; pruebas de scripts (30 OK) y validación de las 3 doradas con `validar_esquemas oferta` | — | sin QA corrido | pendiente |
| 0.1.3 | borrador sin pulir | 2026-11-07 | — | — | — | modo `modelado` (PENDIENTES A3-A4); sin corrida |
