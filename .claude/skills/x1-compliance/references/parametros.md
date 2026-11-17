# Parámetros y claves que X1 lee (no se hardcodean números en esta skill)

Regla: **todo umbral, plazo o tope es paramétrico**; esta skill remite a la **clave** y el valor vigente se lee de `empresa/parametros.yaml` (`grupos.<grupo>.<clave>.valor`) o `empresa/limites.yaml`. Sin dato, **nada gasta, nada se sella por inferencia**: se escala. Los parámetros son `[HIPÓTESIS]` hasta calibrarlos con datos propios (`hipotesis: true`, `ultima_calibracion`). X1 **nunca escribe** `parametros.yaml` ni `limites.yaml`: propone en `limites.propuesta.yaml` o en `empresa/propuestas/`.

## Grupo `compliance` (existe en `empresa/parametros.yaml`)

| Clave | Para qué |
|---|---|
| `rechazos_congelar`, `rechazos_ventana_dias` | rechazos de Meta en la ventana que congelan lanzamientos |
| `apelaciones_max_por_activo` | apelaciones por activo (decide el dueño; el agente no apela) |
| `edad_max_politica_dias` | antigüedad máxima de la lectura de una política (L1-04) |
| `reverif_plataformas_dias`, `reverif_leyes_dias` | cadencia de re-verificación |
| `ngrama_copia_palabras` | coincidencia de copia que bloquea (K02); `ngrama_alerta_temprana_palabras` es solo alerta de D2 |
| `edad_max_evidencia_claim_dias` | antigüedad máxima de la evidencia de un claim (L1-13) |
| `estado_meta_requerido_para_lanzar` | estado de cuenta de Meta exigido |
| `max_anuncios_nuevos_dia` | evitar volumen inusual por API |
| `umbral_rubrica_pass` | promedio mínimo de la rúbrica de X1 (ningún ítem < 3) |
| `salud_max_antiguedad_h` | antigüedad máxima de `salud_actual.json` |
| `vigencia_dictamen_dias` | vigencia de un dictamen y de un sello |
| `declaracion_calidad_cuenta_max_dias` | vigencia de la declaración de calidad de cuenta (sin lectura por API) |
| `anticipacion_preaprobacion_h` | la preaprobación programada equivale a activar (mismo gate H) |
| `nivel_riesgo_bloquea_autonomia` | nivel de riesgo de un candidato que no avanza sin reencuadre (decisión 13); lo lee O0/D1, X1 lo respeta |

## Grupo `salud_operativa` (existe)

`reembolsos_alerta_pct`, `reembolsos_pausa_pct`, `reembolsos_n_min`, `reembolsos_objetivo_pct`, `disputas_alerta_pct`, `disputas_muestra_min_pagos`, `disputas_casos_alerta`, `disputas_casos_pausa`, `disputas_ventana_dias`. Pausa dura de disputas: **`limites.ratio_disputas_pausa`** (fracción; hoy `null` = lo fija el dueño). Conflicto abierto: la nota 25 §9 propone escalones 0,20 / 0,35 / 0,50 % y pausa del macro; `parametros.yaml` tiene otro escalón (`dependencias.md` D-09).

## Pendientes de MINOR (sin lector o sin contrato; marcados `[PENDIENTE: CT-3/CT-4, aprobación del dueño]`: LT-13, LT-20; backlog A-04, A-07, A-08, S-13)

`compliance.{riesgo_version_tabla, clasificador_*, ayuda_max_antiguedad_dias, rhs_*, x1_muestreo_verdes, disputas_pausa_oferta_pct, disputas_pausa_macro_pct, reembolsos_macro_pct}`; `limites.{…}` (las claves `hojas_pausadas`, `nivel_max_lanzable`, `cuota_gasto_amarillo_*`, `envios_amarillo_*`, `dias_limpios_para_subir_cuota`, `edad_minima_audiencia`, `reserva_dias_stripe` y `zonas_grises` **ya existen** en `limites.schema.json` 1.3.0 con valor `null` por decidir: `null` en `nivel_max_lanzable` y en las cuotas = **SOLO VERDE**; el nivel lanzable se escribe `verde`/`amarillo-a`/`amarillo-b`); el contrato `riesgo{subnivel, ejes_codigo, banderas, macro_secundario, version_tabla}` y `paquete.json#anuncios[].riesgo_pieza`. **Condiciones de calidad del clasificador (parámetros del eval, no de negocio):** concordancia por eje ≥ 0,90 y 0 falsos verdes sobre ≥ 60 positivos de retención (`evals/retencion/`).

## Claves de `limites.yaml` que X1 lee

`paises_permitidos`, `locales_permitidos`, `lineas_rojas` (hoy `[]`: sin aprobar), `subnichos_prohibidos` (vacío **por diseño**), `macro_nichos_permitidos` (fijo), `politica_divulgacion_ia` (hoy `null`), `ratio_disputas_pausa` (hoy `null`), `fuentes_permitidas`/`fuentes_prohibidas` (D1). Con las claves en `null` o listas vacías, `scripts/validar_esquemas.py::evaluar_limites` falla cerrado y X1 no puede dar luz verde de mercado.
