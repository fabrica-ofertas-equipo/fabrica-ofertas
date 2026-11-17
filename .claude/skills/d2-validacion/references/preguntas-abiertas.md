# Preguntas abiertas y supuestos de D2 v0.1.0

> Las **bloqueantes** del §10.1 de la spec se respondieron con un `[SUPUESTO]` para poder forjar sin esperar. Cada corrida real las vuelve a preguntar al dueño **antes** de gastar una consulta (una sola lista).

## A. Bloqueantes (se preguntan al inicio de cada corrida)
| # | Pregunta | `[SUPUESTO]` por defecto |
|---|---|---|
| 1 | `oferta_id` y `candidato_id` | Los de `ofertas/<id>/estado.json#candidato_elegido`; en práctica, `ofertas/_ejemplo/` |
| 2 | `locale`, países de consulta y `pais_referencia` | `mercado.json` (siempre `hipotesis`); sin `pais_referencia` salvo que M1 o el dueño lo den (un mercado maduro solo para observar; no entra a `P_a` ni a la voz del país objetivo) |
| 3 | `modo_lectura_snapshot` | `humano_muestreo`: el dueño lee los snapshots que se le indiquen (≤ `urls_snapshot_max_modo_humano`); sin esa hoja, veredicto `provisional` |
| 4 | `modo_transcripcion` y `profundidad_embudo` | `no_disponible`; solo landing (sin checkout ni compra de prueba) |
| 5 | `max_consultas_biblioteca` y `costo_max_validacion` | `null` ⇒ **no se consulta**. Propuesta: 40 consultas (20 + 8 + 8 + 4) y 0 de costo de herramientas |
| 6 | Anunciantes de referencia del dueño | ninguno |

## B. Decisiones del dueño `[DUEÑO]`
1. ¿La autorización de captura automática (D1 §14, con frenos) se extiende a las fichas de snapshot de D2? Sin ella, `humano_muestreo` y D2 queda en N2. El freno actual lo levanta solo una persona.
2. **Tiempo humano**: con `snapshots_por_competidor` = 3 (valor por defecto de la spec) la lectura (15) + verificación (≈ 15) suma ≈ 30 min, el KPI de ≤ 30. ¿Ampliar a 5 snapshots (lectura ≈ 25, total ≈ 40) en las primeras corridas, o bajar la verificación a 2 enlaces por competidor?
3. ¿`GO_CONDICIONAL` puede pasar a D3 con riesgo declarado o solo `GO` (default)? ¿Revisión humana nativa del primer lanzamiento de cada idioma (hoy: segunda lectura de otro modelo)?
4. Presupuesto de `video_analysis` (lo corre el dueño por su cuenta; el Maker no lo usa) y del sondeo pagado de NO_GO (muestreo `muestreo_no_go_pct`); ¿compra de prueba de productos de competidores (gate H, la hace el dueño)?
5. Aprobar los **dorados sintéticos** (`evals/dorados/`; hoy `aprobado_por_dueno: false`) o reemplazarlos por casos reales aprobados.
6. Aprobar o ajustar los parámetros de `references/parametros_d2.propuesta.yaml` y sumarlos a `parametros.yaml`.

## C. Ambigüedades de la spec resueltas con `[SUPUESTO]` (el dueño las confirma al pulir)
- **Denominadores**: `HHI_ang` se calcula sobre los conceptos activos de los operadores sostenidos elegibles (si no hay, sobre los de los operadores elegibles); `entrantes` sobre los operadores elegibles con concepto activo. «Concepto sostenido» (para `saturacion_mecanismo` y `solapamiento_angulo`) = concepto **activo** de un operador sostenido.
- `saturacion.n_ind_sostenidos` (entero en el esquema) = parte entera de `N_ind_sost` (que puede ser fraccionario por `marca_personal_escalera` ×0,6).
- `confianza.puntos` se **topa** al valor de un criterio cuando faltan (1) o la 2.ª pasada o la réplica del QA da Jaccard < mínimo («media o más exige…»).
- Comparaciones con el valor **redondeado** (SS_a a 3 decimales; IS a entero).
- 2.ª pasada con presupuesto de 8 consultas: una por competidor profundo (5) + 1 lote de las páginas al azar (2) + reserva; si no alcanza, primero los profundos. El lote de 2+ `page_id` **no mide** cada página (su `S_a` sigue siendo piso).
- `tipo_anunciante`: manda el vocabulario de la spec D2 (Anexo B), distinto del de `18d` §4.1 (`productor_infoproducto`, `plataforma_saas`, `marketplace`…). Equivalencias: productor_infoproducto → producto_digital/curso_mentoria; plataforma_saas → software; marketplace → afiliado_reventa/otro.
- `refinamiento` de un `GO_CONDICIONAL` no tiene campo en `validacion.json` 1.0.0: viaja en `devolucion_d1.json#refinamiento` (sub-nicho, ángulo, MU, país, formato) cuando cambia problema, MU o sub-nicho; si solo pide más evidencia, queda en `veredicto.evidencia_faltante[]`.
- El subnivel del amarillo (A/B) lo da `scripts.nivel_riesgo` (≥ 2 ejes amarillos = B); si el snapshot de D1 no trae `ejes_codigo`, se deriva de los colores `[SUPUESTO]`. El esquema `validacion` 1.0.0 no tiene `subnivel` (CT4-14): viaja en `metricas_entrada.json`.
- El umbral de PASS del QA (promedio ≥ 3,8; ningún ítem ≤ 2) usa la convención `<grupo>.umbral_qa`: `validacion.umbral_qa` "3.8" (pedido LT-45, clase S, junto con las claves † de D2 en CT4-15); aún no está en `empresa/parametros.yaml`, por eso vive en `parametros_d2.propuesta.yaml`. No se usa `qa_pass_promedio_min` ni `umbral_pass_qa` (ese es de D1).
- **Pedidos de coherencia entre documentos** (no los arregla esta skill): (a) vocabulario de `tipo_anunciante` (spec D2 vs 18d); (b) la fórmula de persistencia de `18d` §4.2 (`s_o`) quedó reemplazada por `SS_a` de la spec; (c) KPI «≤ 30 min humanos» frente a ≥ 4 competidores verificados + lectura de ≤ 25 snapshots (sección B.2); (d) la spec pide `refinamiento` en el veredicto y el esquema 1.0.0 no lo admite.

## D. Tres puntos donde el criterio del dueño debe pulir la skill (§10.1 de la spec)
1. **¿Qué «sostenido» no lo es al abrir el snapshot?** Calibra `umbral_ss`, `anunciante_sostenido_dias_min` y la regla de concepto.
2. **¿Qué «independientes» son el mismo embudo traducido?** Calibra el clustering de `operador_id` y `tipo_anunciante`.
3. **¿Sobreviven el hueco y el MU a «¿por qué nadie lo hace ya?» y el ángulo seguro conserva el deseo del cliente?** Calibra `umbral_hueco_ausencia`, las clases M1-M8 y `mecanismo_share_*`.
