# Parámetros y umbrales que usa D4

> **Ningún número vive en esta skill**: cada umbral sale de `empresa/parametros.yaml` (grupos `producto`, `entrega`, `compliance`) o de `empresa/limites.yaml`. Todos son `[HIPÓTESIS]` con `ultima_calibracion: null` (docs/contratos.md §5). Sin dato, un script sale con código 5 y **nada gasta ni se aprueba** (fail-closed). Un cambio de valor es del dueño (`accion:cambiar_limites`/aprobación de X2), no del Maker.

## Existen hoy (leer del YAML)
| Clave | Qué gobierna | Quién la lee |
|---|---|---|
| `producto.lectura_wpm` | Palabras por minuto de lectura (necesita factor por locale [PEND.]) | `tiempo_total.py` |
| `producto.lectura_max_pct_prometido` | Máximo de lectura sobre el tiempo prometido | `tiempo_total.py` |
| `producto.cold_run_tolerancia` | Factor tolerado con base `cold_run_humano` | `tiempo_total.py`, X15 |
| `producto.cold_run_agentes` | Nº de novatos en frío | orquestador (cold run B) |
| `producto.min_fuentes_por_tema` | Fuentes distintas por tema (≥ 1 T1) | `verificar_respaldo.py` |
| `producto.t_paso_humano_min` | Minutos por tipo de micro-acción | `tiempo_total.py --autoprueba` |
| `producto.peso_max_mb_pdf`, `peso_max_mb_paquete` | Pesos máximos | `empaquetar.py` |
| `producto.paginas_vs_prometido_pct` | Desvío de páginas vs lo prometido | QA (L1-03) |
| `producto.hechos_fuente_max_dias` | Antigüedad máxima de la consulta de una fuente | `verificar_respaldo.py` |
| `producto.prompts_exito_pct` | Éxito mínimo de prompts sobre 3 entradas | QA (L1-10) |
| `producto.contraste_min` | Contraste WCAG AA mínimo | [PEND.: `contraste`] |
| `producto.volatilidad_revision_dias` | Revisión por volatilidad (alta/media/baja) | `vigencia` |
| `producto.umbral_qa` | Promedio mínimo de la rúbrica (con R1, R4, R8, R11 ≥ 4 y ningún ítem < 3) | QA |
| `entrega.enlace_vence_dias`, `enlace_max_descargas` | Enlace firmado | `producto.json#entrega` |
| `compliance.ngrama_copia_palabras`, `ngrama_alerta_temprana_palabras` | Copia que bloquea / alerta | `similitud_ngrama.py` |
| `orquestador.max_rondas_qa` | Máximo de rondas Maker↔QA | orquestador |
| `limites.creditos_max_pieza`, `creditos_max_oferta`, `costo_max_producto`, `max_budget_por_corrida_agente`, `politica_divulgacion_ia`, `lineas_rojas`, `macro_nichos_permitidos` | Topes del dueño (**hoy `null`**: solo texto) | `cotizar_creditos.py`, preflight |

## Propuestos por la spec (Anexo A) y aún no creados: [PENDIENTE: MINOR de `parametros` pedido a CT-1/dueño]
`producto.revision_meses_salud_sensible` · `revision_meses_dinero` · `revision_meses_verde` · `afirmaciones_sin_fuente_max` · `linguistica_retraduccion_pct_resto` · `linguistica_muestreo_nativo_posterior` · `biblioteca_muestra_qa_pct` · `biblioteca_muestra_fisica_min` · `respuesta_cambio_oficial_horas`. Además, de esta skill: `producto.cold_run_desvio_max_pct` (desvío tolerado del primer paso cronometrado) y `producto.cita_max_palabras` (cita atribuida). Los valores iniciales sugeridos por la spec están en `dependencias.md` §4.

## Nota sobre cifras citadas en el texto
Algunas referencias nombran de pasada un valor de la spec o del backbone vigente al 2026-11-06 (cita atribuida ≤ 25 palabras, ayuda verificada ≤ 180 días, infraestructura verde < 6 h, desvío del primer paso > 25 %). **No son política de esta skill**: la fuente es el parámetro (o archivo de X1) correspondiente y, si cambia, el texto se actualiza.
