# Parámetros (Anexo A) y glosario (Anexo B) de D2

> Todo umbral es **paramétrico** y `[HIPÓTESIS]`: ningún script ni la skill lo fija. Valor aprobado = `empresa/parametros.yaml` (grupo `validacion`, más `descubrimiento` y `compliance`); lo que aún no existe allí (marcado † en la spec) está **propuesto** en `references/parametros_d2.propuesta.yaml` con su rango. Integrarlo exige aprobar los valores y ampliar `contratos/parametros.schema.json` (rutas protegidas; pedido en `dependencias.md`). Sin float: decimales como cadena.

## A. Claves y estado
| Clave | Dónde vive hoy | Inicial | Rango |
|---|---|---|---|
| `max_consultas_qa` | `validacion` (existe) | 15 | 10-25 |
| `descubrimiento.anunciante_sostenido_dias_min` / `_conceptos_min` | existe (compartidas con D1 y D6) | 45 / 3 | 30-90 |
| `umbral_ss` | existe | 0,60 | 0,50-0,75 |
| `ss_peso_s,c,i,p,e`, `ss_paises_tope`, `marca_personal_peso` | propuesta † | 0,30 · 0,25 · 0,20 · 0,10 · 0,15; 2; 0,6 | ±0,10 |
| `sim_concepto` | existe | 0,8 | 0,7-0,9 |
| `sep_iteracion_dias` · `ventana_entrantes_dias` | propuesta † | 14 · 60 | 7-30 · 30-90 |
| `is_peso_n,hhi,entrantes`; `norm_N_ind` | propuesta † | 0,40 · 0,30 · 0,30; 8 | ±0,10; 5-12 |
| `n_competidores_profundos` / `snapshots_por_competidor` | existe / propuesta † (5 solo si el dueño amplía el tiempo a ≈ 25 min) | 5 / 3 | 3-8 / 3-10 |
| `min_frases_voz` / `min_frases_voz_propias` / `min_fuentes_voz` / `max_share_fuente_voz` | existe / † / existe / † | 30 / 10 / 3 / 0,5 | 20-60 / 5-20 / 3-5 / 0,4-0,6 |
| `umbral_hueco_ausencia` | existe | 0,70 | 0,5-0,85 |
| `n_ind_sost_go`; `is_go_max`; `is_nogo_min` | existe | 3; 70; 85 | 2-5; 55-75; 80-95 |
| `umbral_solapamiento`; `jaccard_replica_min`; `convergencia_baja_max` | propuesta † | 0,5; 0,5; 0,25 | 0,4-0,6; 0,4-0,6; 0,15-0,35 |
| `mecanismo_share_saturado` / `_abierto` / `_n_min_operadores` | propuesta † | 0,5 / 0,15 / 4 | 0,4-0,6 / 0,1-0,2 / 3-6 |
| `relectura_dias`; `max_palabras_cita`; `max_iteraciones_refinar`; `muestreo_no_go_pct` | existe | 7; 25; 2; 10 | 5-14; —; 1-3; 0-20 |
| constantes que la spec escribe en el texto de las fórmulas (`hueco_min_*`, `confianza_*`, `nogo_frases_min`, `hueco_localizacion_min_ref`, `min_share_frases_locale`) | propuesta | ver el YAML | ver el YAML |
| muestreo y presupuesto (`terminos_busqueda_min/max`, `competidores_deterministas_*`, `competidores_al_azar`, `urls_snapshot_max_modo_humano`, `consultas_*`) | propuesta | 6-10; 5-10; 2; 25; 20/8/8/4 | ver el YAML |
| rutina sin la herramienta (`competidores_verificables_min`, `tiempo_verificacion_dueno_max_min`, `minutos_por_enlace_verificacion`, `minutos_por_snapshot_lectura`, `tiempo_lectura_dueno_max_min`, `verificacion_enlaces_max_por_competidor`, `sonda_monocultivo_share`) | propuesta | 4; 15; 1; 1; 30; 3; 0,5 | ver el YAML |
| QA (`umbral_qa` [= `validacion.umbral_qa`, LT-45], `qa_item_min`, `qa_acuerdo_ciego_*`, `qa_clasificacion_ciega_n`, `qa_citas_*`, `qa_replica_consultas_n`) | propuesta | 3,8; 3; 0,85/0,70; 20; 0,95/0,05; 3 | ver el YAML |
| `compliance.ngrama_alerta_temprana_palabras` / `ngrama_copia_palabras` | existe | 6 / 8 | — / 6-12 |
| `limites.max_consultas_biblioteca`; `limites.costo_max_validacion` | `empresa/limites.yaml`, **del dueño, hoy `null`** | propuesta 40; 0 | 20-80; `[DUEÑO]` |
| `orquestador.max_rondas_qa`; `orquestador.timeout_etapa_min.D2` | existe | 2; 45 | — |

## B. Glosario
- **Operador**: clúster de páginas con mismo dominio, misma oferta (aun traducida), `page_id` repetido o mismo `beneficiary_payers` (UE). **Sostenido**: operador con `SS_a ≥ umbral_ss`. **Concepto**: promesa + mecanismo. **Mecanismo único (MU)**: el «cómo» nombrable (2-6 palabras) que ataca la causa raíz y se diferencia del sustituto gratis y de los mecanismos de los competidores (backbone 5.11).
- **Truncado / piso**: la muestra se cortó en 50 o el total estimado supera lo visto; todo conteo derivado es cota inferior. **Sonda**: conteo por término × país, proxy débil, no aditivo.
- **Hueco sustentado**: ausencia medida del mecanismo en los sostenidos + voz del cliente que lo pide. **Hueco de localización**: pocos sostenidos locales pero ≥ N del mismo concepto en `pais_referencia` (hipótesis para D7).
- **Banderas de la sonda**: `monocultivo`, `granja`, `operador_translocal`. **Saturación**: `IS` (mercado) y `saturacion_mecanismo` (clase M).
- **Estados**: `observado` / `inferido` / `no_disponible`. **`leido_por`**: `dueno`, `navegador_auto`, `maker_titulo` (solo título del conector).
- **`lectura_snapshots`**: `humano_muestreo` (default) · `navegador_auto` (requiere autorización del dueño y el freno levantado) · `pendiente_humano` (hoja enviada, sin devolver; GO imposible; veredicto provisional) · `ninguno` (GO imposible).
- **Veredictos**: `GO` · `GO_CONDICIONAL` (antiguo REFINAR) · `NO_GO`. **Calculado** (script) · **propuesto** (Maker, ≤ calculado) · **final** (≤ calculado salvo humano).
- **Niveles de riesgo**: verde · amarillo-a · amarillo-b · rojo (nota 25 §2.3; los calcula `scripts.nivel_riesgo`). **PM**: puntaje de modelado de D1 (no es evidencia de D2).
