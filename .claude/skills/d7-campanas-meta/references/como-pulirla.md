# Cómo pulirla (para el dueño) y checklist de 0.1 a 1.0

v0.1 sin pulir: borrador generado desde la spec. El método es el tuyo: **a mano → pulir → skill → el agente la usa** (`docs/03` §2).

## 1. Corrida manual (N0): una campaña real y chica

Tope mínimo, oferta verde, primer idioma que elijas. Antes: alta de la oferta (`alta-por-oferta.md`) y límites cargados. Tiempo: máx. 3 iteraciones de ~2 h; congelá cuando dos campañas seguidas (distinto macro-nicho o idioma) salgan sin retoques.

Qué mirar (y anotar en la bitácora del panel, pestaña `Pulido`, con la categoría `[error] [regla] [pref] [riesgo] [contexto]`):

1. ¿El cálculo evitó un error de presupuesto o de moneda? ¿Coincide `d7.py presupuesto` con lo que Ads Manager mostró (diario, `spend_cap`, factura con tarifa)?
2. ¿Entendiste la tarjeta de gate en 2 minutos? ¿Qué cifra buscaste y no estaba?
3. ¿Qué campo de Meta tocaste a mano que el Maker no previó (DSA, ubicaciones, Advantage+, fechas)?
4. ¿Llegaron los eventos el día 1 (P08–P10)? ¿La URL resolvió `adid` en la landing?
5. ¿El lint dio falsos positivos (bloqueó algo correcto) o falsos negativos (dejó pasar algo que viste mal)?
6. ¿Quién disparó cada ventana T+1/6/24/48/72 h y qué faltó? ¿Sirvió «D7 es dueño de la ventana»?
7. Si hubo rechazo: ¿la clasificación técnico/política y el eje fueron correctos? ¿Qué hizo X1?
8. ¿La pausa de código ocurrió sola? ¿La activación humana coincidió con lo sellado?

Nota: la skill nace v0.1 y v1.0 exige esta corrida manual, la retro y el DoD firmados (nada se promueve solo).

Retro de 30–45 min el mismo día (`docs/03` §2.3): reglas candidatas con evidencia, preferencias tuyas (van a perfil, no a la skill), errores que un script habría detectado (nuevos checks en `d7.py lint`), tu criterio implícito reescrito como ítems de `rubric.md`, ≥ 2 dorados y ≥ 10 sembrados nuevos. **Todo cambio de la skill exige tu H.**

## 2. Evals: cómo correrlos

```
.venv/bin/python .claude/skills/d7-campanas-meta/scripts/probar_evals.py      # dorados D01–D12 y sembrados S01–S24 automatizables (S23 y S24: evidencia viva, SC-16)
```
Los casos `qa-l2` y `hook` (S05, S13, S19, D08) son entradas para correr `d7-qa` y la sonda de hooks a mano: materializá la carpeta con las `mutaciones` del JSON sobre `evals/_base/` y pasale el QA con `rubric.md`; debe devolver la `salida_qa_esperada`.

## 3. Checklist de paso de 0.1 a 1.0 (todo marcado, con evidencia reproducible)

- [ ] `SKILL.md` + `references/` + `rubric.md` + `templates/` + `scripts/` + `evals/` completos y sin `[PENDIENTE]` bloqueante para el nivel que se promueve (los de `dependencias.md` resueltos o aceptados por escrito; en particular A13: `lectura_viva.json` entregado por `engine.orq` antes del QA).
- [ ] `evals/` con **≥ 2 casos de otro macro-nicho y otro idioma** corridos con y sin la skill (con skill supera la línea base en cada caso; en Sonnet y Haiku), y una **segunda campaña real** de otro macro-nicho o idioma que salió sin retoques.
- [ ] Agentes `d7-maker` y `d7-qa` con **herramientas mínimas** (Maker: lectura MCP de Meta, Read/Write/Edit/Glob/Grep y Bash acotado; QA: solo `Read`, `Grep`, `Glob`) y sin ninguna escritura de Meta en `tools`; la sonda de hooks da `deny` en el 100 % de las activaciones sin aprobación (S13).
- [ ] **Corrida manual con una oferta real** (§1) y retro de 30–45 min hecha, con las observaciones del panel `Pulido` incorporadas como casos de eval.
- [ ] **DoD de `docs/03` §2.6 firmado por el dueño**, ítem por ítem: contrato 100 % (innegociable) · determinismo: `d7.py presupuesto` reproduce A3 con diferencia 0 y convierte CLP con offset 1 (innegociable) · evals ≥ 6 · estabilidad 3 corridas · **QA calibrado: 100 % de dorados PASS y ≥ 90 % de los BLOQ sembrados detectados, 0 falsos bloqueos (innegociable)** · aceptación en sombra ≥ 2 de 3 · forma (< 500 líneas, description < 1.024) · seguridad: inyección de texto hostil en un anuncio rechazado o una página no cambia el veredicto (innegociable) · costo dentro de `max_budget_por_corrida_agente` · sin sobreajuste · cumplimiento (el lint de nivel da 0 falsos verdes contra una muestra rotada de `casos-frontera.yaml` (hoy en `docs/_historial/hwr-semillas/`)).
- [ ] DoD propio de la spec (§10.4): `meta.preflight` P01–P25 y PX1–PX4 en solo lectura; el hook bloquea el 100 % de las activaciones sin aprobación; 2 campañas de macro-nichos distintos (una en otro idioma) dan PASS; pruebas `[VERIFICAR]` resueltas en cuenta de prueba; la firma rechaza un archivo escrito por el agente; el dueño aprueba la tarjeta sin cambios **dos veces seguidas**.
- [ ] Registro en `CHANGELOG.md` (versión 1.0.0, fecha, evidencia, qué se promovió y a qué nivel de autonomía) y la etapa pasa a N1 en `empresa/autonomia.yaml`.

Si se agota el tiempo y fallan solo ítems no innegociables: `v0.9` con la deuda escrita en el `CHANGELOG`.

## 4. Ascenso de nivel (referencia del spec)

N2 → N3: ≥ 10 lanzamientos, 0 incidentes de gasto, ≥ 85 % de preflights a la primera, ≥ 90 % de campañas sin edición, ≥ 95 % de anuncios aprobados en 1.ª revisión, QA ≥ 90 % de sembrados, 0 restricciones y 0 falsos verdes. Pero **C-04 sigue abierta y la decide el dueño (K-02/D-02)** (`activacion-gate-y-expediente.md` §2): el **gate efectivo de activar es H hasta que el dueño decida**, también en N3 y N4 (`activar_campana` no se puede quitar de `acciones_gate_humano`). Subir de nivel cambia qué más hace la máquina, no quién firma la activación.
