# Fórmulas, veredicto y cómo usar los scripts

> Spec: `departamentos/03-validacion.md` §3.4. Implementación v0.1.0: `scripts/metricas.py` (Decimal), `scripts/veredicto.py`, `scripts/qa_recomputar.py` (Fraction, **independiente**: no importa a los otros). Todos leen los umbrales de `empresa/parametros.yaml` (aprobado) y, si la clave no existe allí, de `references/parametros_d2.propuesta.yaml`; si falta en las dos, **salen con código 5**. Pruebas: `.venv/bin/python -m unittest discover -s .claude/skills/d2-validacion/scripts/tests -p "test_*.py"` (vectores 0,233 y 0,675; 600 casos aleatorios donde `metricas.py` y `qa_recomputar.py` coinciden con diferencia 0).

## 1. Fórmulas (redondeo half-up: SS_a a 3 decimales, IS a entero; se compara el valor guardado)
- **SS_a** por operador = `ss_peso_s·min(S_a/c,1) + ss_peso_c·min(C_a/c,1) + ss_peso_i·I_a + ss_peso_p·min(P_a/ss_paises_tope,1) + ss_peso_e·E_a`, con `c = descubrimiento.anunciante_sostenido_conceptos_min`. **El volumen bruto pesa 0.** **Sostenido** si `SS_a ≥ umbral_ss`.
  - `S_a` = conceptos activos con antigüedad ≥ `descubrimiento.anunciante_sostenido_dias_min`; `C_a` = conceptos activos; `I_a` = 1 si hay ≥ 2 conceptos activos del **mismo mecanismo** con ≥ `sep_iteracion_dias` de diferencia de antigüedad; `P_a` = países consultados donde aparece; `E_a` = 0 / 0,5 (landing + checkout) / 1 (+ bump, upsell o secuencia).
  - Vectores: 1 concepto, 60 días, 1 país, sin embudo ⇒ **0,233**; 3 conceptos de 90 días (mismo inicio), 1 país, landing con checkout ⇒ **0,675**; el mismo con una iteración de ≥ 14 días ⇒ 0,875.
- **N_ind_sost** = operadores sostenidos de tipo `producto_digital` o `curso_mentoria` (1) + `marca_personal_escalera` × `marca_personal_peso`. `saturacion.n_ind_sostenidos` (entero del esquema) = parte entera; la decisión usa el valor exacto.
- **IS** = `100·(is_peso_n·min(N_ind_sost/norm_N_ind,1) + is_peso_hhi·HHI_ang + is_peso_entrantes·entrantes)`. `HHI_ang = Σ s_k²` sobre ángulos de los conceptos activos de los operadores sostenidos (si no hay sostenidos, de los operadores elegibles: `[SUPUESTO]`); `entrantes` = fracción de operadores elegibles con concepto activo cuyo anuncio más antiguo observado tiene ≤ `ventana_entrantes_dias` (`[SUPUESTO]` sobre el denominador). Calibrar con ≥ 10 nichos conocidos antes de N1.
- **saturacion_mecanismo** (clase del MU propuesto; `O` = operadores sostenidos elegibles): **alta** si `share ≥ mecanismo_share_saturado` con `|O| ≥ mecanismo_n_min_operadores`, o si el MU es indistinguible de un sostenido; **baja** si `share ≤ mecanismo_share_abierto` con `|O| ≥ n_min`; **media** en el resto (incluye `|O| < n_min`: no concluyente).
- **convergencia** (`solapamiento_angulo` = fracción de conceptos sostenidos con el ángulo recomendado): **alta** si ≥ `umbral_solapamiento` sin diferenciador sustentado; **media** si ≥ umbral con diferenciador, o entre `convergencia_baja_max` y el umbral; **baja** si menor.
- **confianza.puntos** = `confianza_puntos_por_criterio` × criterios cumplidos: (1) snapshots leídos ≥ `confianza_pct_snapshots_min` de los competidores profundos; (2) ≥ `confianza_landings_min` landings analizadas; (3) ≥ `confianza_consultas_min` consultas distintas; (4) transcripción ≥ `confianza_pct_transcripcion_min` de los videos (o sin videos); (5) re-lectura a +`relectura_dias` o historial ≥ ese plazo. **Media o más exige (1) y 2.ª pasada**; una réplica del QA con Jaccard < `jaccard_replica_min` ⇒ baja (puntos topados al valor de un criterio). Niveles: ≥ `confianza_alta_min_puntos` alta; ≥ `confianza_media_min_puntos` media; el resto baja.
- **Hueco sustentado**: ausente en ≥ `umbral_hueco_ausencia` de los sostenidos con ≥ `hueco_min_anuncios_leidos` anuncios leídos **y** respaldado por ≥ `hueco_min_frases` frases de ≥ `hueco_min_fuentes` fuentes.

## 2. Veredicto (lo calcula el script; ningún LLM lo decide)
**NO_GO** si cualquiera: IS ≥ `is_nogo_min` y sin hueco · `saturacion_mecanismo = alta` y sin hueco y confianza ≥ media · riesgo ROJO sin reencuadre verificable · ningún ángulo seguro que conserve el deseo · 0 sostenidos y frases < `nogo_frases_min` y confianza ≥ media.
**GO** si NO hay NO_GO y **todas**: lectura de snapshots ≠ `ninguno` (y ≠ `pendiente_humano`) · `N_ind_sost ≥ n_ind_sost_go` · frases y fuentes mínimas (§ `voz-del-cliente.md`) · ≥ 1 evidencia E1/E2 en el locale · ≥ 1 hueco sustentado · IS ≤ `is_go_max` · convergencia ≠ alta · saturación de mecanismo ≠ alta · sustituto gratis `no_dominante` o `diferenciado` · riesgo verde o amarillo-a · X1 no veta · confianza ≥ media. Y **no** hay hueco de localización.
**GO_CONDICIONAL** = el resto, con `refinamiento` y `evidencia_faltante`; incluye amarillo-b y el **hueco de localización** (`N_ind_sost < n_ind_sost_go` pero ≥ `hueco_localizacion_min_ref` sostenidos del mismo concepto en `pais_referencia`: hipótesis para D7, **nunca GO**). **0 competidores nunca es GO**; con confianza baja, «0 sostenidos» es GO_CONDICIONAL.
**El Maker propone y solo puede degradar** (GO > GO_CONDICIONAL > NO_GO). `final` no puede ser mejor que `calculado` salvo con `origen_version: humano` (decisión `[DUEÑO]`). `veredicto.py comprobar` lo verifica y `qa_recomputar.py` lo repite.

## 3. Entrada (`templates/metricas_entrada.json`) — qué pone el Maker y de dónde sale
| Campo | Origen |
|---|---|
| `operadores[]` (`operador_id`, `tipo_anunciante`, `paginas`, `paises`, `embudo`, `truncado`, `anuncios_leidos`, `primer_anuncio_observado_dias`, `conceptos[]{concepto_id, activo, antiguedad_dias, tipo_mecanismo, angulo_principal, evidencia_id}`) | `normalizar_biblioteca.py` (páginas, edades, truncado) + lectura de snapshots del dueño (conceptos, mecanismos, ángulos, embudo) |
| `mu{tipo_mecanismo, indistinguible_de_sostenido, evidencia_id}` | candidato (`mecanismo`) contrastado por el Maker |
| `angulo_recomendado`, `diferenciador_sustentado` | Maker (de `riesgo.angulo_seguro` y los huecos) |
| `huecos[]{hueco_id, presente_en[], frases, fuentes, evidencia_id}` | Maker: `presente_en` = operadores sostenidos que **sí** lo cubren |
| `voz{frases_total, frases_propias, frases_del_locale, fuentes{}}` | `verificar_citas.py` y `voz_cliente.json` |
| `evidencias[]{id, url https, fecha}` | todo `evidencia_id` usado debe estar aquí; **sin URL o fecha se rechaza** |
| `mercado_resumen` | `normalizar_biblioteca.py` (vía `puntaje_modelar resumir`); informativo |
| `confianza_datos`, `lectura_snapshots`, `sustituto_gratis`, `evidencia_locale`, `hueco_localizacion` | Maker, con evidencia |
| `riesgo{heredado, final, angulo_seguro_existe, reencuadre_verificable_x1, x1_dictamen}` | D1 + cálculo manual de la tabla de la nota 25 + dictamen de X1 |

## 4. Comandos (desde la raíz del repositorio; `PY=.venv/bin/python`, `S=.claude/skills/d2-validacion/scripts`)
```
$PY $S/normalizar_biblioteca.py ofertas/<id>/02-validacion/crudo/<corrida_id> --ahora <AAAA-MM-DDTHH:MM:SSZ> --semilla <n> [--excluir <page_id,…>] --salida ofertas/<id>/02-validacion/normalizado.json
$PY $S/metricas.py ofertas/<id>/02-validacion/metricas_entrada.json --salida ofertas/<id>/02-validacion/metricas_salida.json
$PY $S/veredicto.py calcular ofertas/<id>/02-validacion/metricas_entrada.json
$PY $S/veredicto.py comprobar ofertas/<id>/02-validacion/metricas_entrada.json ofertas/<id>/02-validacion/validacion.json
$PY $S/verificar_citas.py ofertas/<id>/02-validacion/voz_cliente.json --locale <locale> --base ofertas/<id>/02-validacion --pii ofertas/<id>/02-validacion/anuncios_competencia.json
$PY $S/verificar_competidores.py ofertas/<id>/02-validacion/anuncios_competencia.json --crudo ofertas/<id>/02-validacion/crudo/<corrida_id>
$PY $S/qa_recomputar.py ofertas/<id>/02-validacion/metricas_entrada.json ofertas/<id>/02-validacion/validacion.json --metricas ofertas/<id>/02-validacion/metricas_salida.json
$PY -m scripts.validar_esquemas   # esquemas y ejemplos del repositorio (ver SKILL «Validar»)
```
Códigos: 0 ok · 2 uso · 3 incoherente/inválido · 5 falta un parámetro. `--salida` no sobrescribe. Los scripts **no usan red ni secretos**. Las rutas `.claude/skills/**` están protegidas contra escritura de agentes: los scripts se invocan, no se editan (cambiarlos es del dueño o del script de aplicación de X2).
