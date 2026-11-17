# Puntuación de D1: dos modelos, un contrato

> Spec §3.2 (modelo de modos A-C), §12.2 (fórmula PM del Modo D), §3.4 (parámetros), interfaces §3.7-§3.8. Todo peso y umbral es **[HIPÓTESIS]** a recalibrar con X2 y D8; vive en `empresa/parametros.yaml` (`grupos.descubrimiento`) o en las propuestas `scripts/modelado/parametros_*.propuesta.yaml`. Aquí remites a la **clave**, no a un número nuevo. `score.py` **no existe** `[PENDIENTE: S-B]` (`scripts/descubrimiento/dedup.py` sí: Jaccard **[HIPÓTESIS]** para `sim`): hasta entonces, las cuentas de los modos A-C se hacen a mano **mostrándolas en `crudo/cuentas.md`** y el L1 (`validar_candidatos.py`) las recalcula.

## 1. Modos A-C: 10 criterios 0-5 con evidencia citada
| Criterio (clave en `puntajes`) | Peso (spec) | 1 | 3 | 5 | Fuente principal |
|---|---|---|---|---|---|
| `dolor_urgencia` | 15 | molestia ocasional | dolor recurrente | bloqueo con plazo o costo | foros, comentarios, reseñas |
| `disposicion_pago_precio` | 14 | solo alternativas gratis (incluido resolverlo con un chatbot en minutos) | pagos de precio similar | compradores visibles en el rango | marketplaces, reseñas |
| `evidencia_demanda_pagada` | 12 | solo voz del cliente | anunciantes efímeros | ≥ 3 anunciantes sostenidos + ventas/reseñas en marketplace (E1) | Biblioteca + marketplaces |
| `competencia` (curva en U; unidad = anunciantes con oferta equivalente) | 8 | 0 o saturado (> 25) | 1-2 o 15-25 | 3-10 con espacio de diferenciación | Biblioteca, buscadores |
| `huecos` | 10 | «hacerlo mejor» | hueco plausible | quejas o ausencias evidenciadas, traducibles a ángulo | reseñas 2-3★, comentarios |
| `producibilidad_ia_1dia` | 12 | exige experto o datos propietarios | producible con revisión experta | verificable con fuentes públicas, ≤ 8 h-agente | juicio + referencias |
| `tiempo_primer_resultado` | 8 | semanas | días | < 1 h | diseño del producto |
| `vida_util` | 6 | < 3 meses | 6-12 meses | ≥ 24 meses o recurrente anual | historial de tendencia |
| `riesgo` (**derivado**, no juzgado) | 10 | rojo (0: veto) | amarillo-b (2) / amarillo-a (3) | verde (5) | `scripts/nivel_riesgo.py` |
| `encaje_marca_mercado` | 5 | exige rostro o autoridad personal | neutral | marca sin cara, pagable en el país, audiencia alcanzable sin atributos | brief |
Los pesos suman 100 y se copian a `pesos` **con el prefijo `ac_`** (`ac_dolor_urgencia: "15"`; decimales como cadena; `puntajes` usa el criterio sin prefijo). Los puntajes de `riesgo` (5/3/2/0) son `puntaje_riesgo_verde`, `_amarillo_a`, `_amarillo_b`, `_rojo` (propuestos, no integrados `[PENDIENTE: dueño/CT-4]`). Ninguna clave `peso_<criterio>` existe aún en `parametros.yaml` `[PENDIENTE: dueño/CT-4]`.

**Cuentas (siempre a la vista):** `score_base = Σ peso_i × s_i / 5` · `score_ajustado = score_base × f_confianza × f_dup × f_viab`, con los tres factores ≤ 1 (el L1 comprueba que `score_ajustado ≤ score_base × f_confianza`).
- `f_confianza`: alta 1,0 (≥ 3 fuentes independientes, ≥ 2 tipos, una E1) · media 0,9 (≥ 2 fuentes, ≥ 2 tipos) · baja 0,75.
- `f_dup = 1 − 0,4 × clamp((sim − 0,5)/0,3; 0; 1)` con `sim` = máxima similitud (audiencia, resultado, obstáculo, formato) con cada oferta o descartado de la memoria (`sim_penalizacion_desde`, `sim_dup_bloqueo`); un juicio categórico «mismo problema, misma audiencia» equivale a `sim` = 1 (**bloqueo**).
- `f_viab` [HIPÓTESIS]: ratio ≥ 1,5 → 1,0 · 1,0-1,5 → 0,95 · < 1,0 → 0,9 (0,85 si no hay bump o backend plausible).
- **Vetos duros** (el candidato sale del ranking): `riesgo.nivel = rojo`; (`nivel`, `subnivel`) por encima de `nivel_max_lanzable` (`null` o ausente ⇒ solo verde); `macro_nicho` fuera de salud/relaciones/dinero (`fuera_de_macro_nicho`, **antes** de calcular el riesgo); ficha MU/EU incompleta; `producibilidad` ≤ 1; evidencia bajo el mínimo (queda «especulativo»; entra solo al modo C etiquetado).
- **Viabilidad previa** [HIPÓTESIS]: `CPA_tope = precio_plausible × (1 − costos_variables_pct) − comision_fija` (pasarela, IVA y reembolsos: `docs/_investigacion/03-stripe.md`; la comisión fija pesa en tickets de pocos dólares). `CPA_estimado = CPM / (1000 × CTR_enlace × CVR_clic_compra)` en **3 escenarios** con los rangos de `04-meta-ads.md` §8.2: el CPM debe ser **el del país del público** (un CPM de EE. UU. para México es defecto S17); CTR y CVR no tienen fuente: `[HIPÓTESIS]`. `ratio = CPA_tope / CPA_estimado`: < 1,0 → «inviable sin backend»; < 1,5 → advertencia; la `bandera` del contrato es `verde` (≥ 1,5), `amarilla` (1,0-1,5), `roja` (< 1,0) `[SUPUESTO]`. Un order bump entra solo como supuesto declarado. D2/D3 lo recalculan.
- **Selección top-N (MMR)**: voraz; `MMR_i = (1−λ)·score_ajustado_i/100 − λ·max_{j∈elegidos} sim(i,j)` con `lambda_diversidad`, `max_por_nicho_topn`, ≥ `min_explore` (nicho ausente de la memoria de ofertas con evidencia 100 % externa), cuota mínima por macro (`cuota_min_exploracion_por_macro_nicho_pct`) y ≥ `cuota_verde_topn_min_pct` de verdes; sin ROJO ni amarillo-b salvo gate H.
- **Sensibilidad**: repite el ranking con cada peso ±30 % (re-normalizado a 100); el top-1 debe seguir en el top-3 en ≥ `top1_estable_min_pct` de las perturbaciones, o el informe declara **«ranking frágil»**. Con un solo candidato la sensibilidad es insuficiente y se declara.

## 2. Modo D: la fórmula PM (`pm-2`), solo `puntaje_modelar`
`PM = G × T^wT × H^wH × X^wX × D^wD × 100`, factores en [0, 1], aritmética `Decimal`. Pesos propuestos (T 0,25 · H 0,35 · X 0,20 · D 0,20; `modelado_peso_*`; H pesa más: es la señal que más coincide entre mentores y la menos inflable). Pasa si `PM ≥ modelado_umbral_pasa`. Cambiar un peso, un umbral o un vocabulario cambia el **sello de reglas** y el CLI no calcula (exit 4).
| Factor | Qué mide | Cálculo (resumen) |
|---|---|---|
| **G** puertas | vetos | `marca_personal`, `sustituto_gratis_cubre`, `practica_vetada`: cualquiera en `true` → PM 0 (`vetada`); en `null` → ficha **incompleta** (techo). El dueño quitó el 2026-11-06 «fácil de modelar» y «exige comunidad, vivo o app» |
| **T** tracción | ¿funciona en el origen? | media geométrica de volumen `min(1, A/anuncios_objetivo)`, edad de la oferta `min(1, d/dias_objetivo)`, conceptos `min(1, C/conceptos_objetivo)` y réplica (1, o `modelado_replica_baja`) |
| **H** hueco | ¿hay lugar en el destino? | idioma (1 / 0,5 rival débil / 0,25 rival fuerte / 0 original o ≥ `modelado_sostenidos_cierre` sostenidos) × (1 − entrantes_30d/tope) × ventana estacional; `entrantes_30d = null` ⇒ **incompleta**, nunca 0 |
| **X** transferibilidad | ¿viaja? | media geométrica de dolor universal, viabilidad de ticket (`f_viab`) y riesgo de políticas **por promesa**, no por tema (0-1; `null` = sin evaluar). El dueño quitó la producibilidad |
| **D** diferenciación | ¿cómo no ser un clon? | 0 reencuadres → `modelado_dif_base`; 1 → `modelado_dif_un_reencuadre`; ≥ 2 → `modelado_dif_dos_o_mas` (mecanismo nombrable, lista→sistema, cambio de unidad, subnicho × obstáculo, autoridad local, localización cultural, precio alto→bajo) |
**Armonización con A-C:** `riesgo_politicas` de la ficha (0-1) mide la promesa de la oferta **ajena**; **no es** el `riesgo` (P, C, E, N) del candidato propio, que calcula `nivel_riesgo.py`. `macro_nicho` de la ficha es una etiqueta por tema (prior), no la clasificación por deseo central. Si `riesgo_politicas ≤ 0,3` con `riesgo.P = verde`, el QA abre un hallazgo MAYOR.

**Sensibilidad en PM:** `puntuar --sensibilidad` perturba cada peso ±`modelado_sens_variacion` y exige cobertura ≥ `modelado_sens_cobertura_min`; `estado ∈ robusto·fragil·insuficiente`. Mapeo a `candidatos`: `top3_estable_pct = floor(100 × cobertura)` si `robusto|fragil`; si `insuficiente`: `0` y «ranking frágil» declarado.

**Mapeo de PM a la forma 1.0.0 del snapshot** (`references/candidatos-formato.md` §3): `puntajes{traccion, hueco, transferibilidad, diferenciacion}` con `s = round(5·factor)`, `justificacion` = el cuello de botella; `score_base = round_half_even(PM)`; `score_ajustado = round(score_base × f_confianza × f_dup)` **sin** `f_viab` (la viabilidad ya está en X); `pesos` = `pm_T`, `pm_H`, `pm_X`, `pm_D` (25/35/20/20 como cadenas); `parametros_usados.formula_version = "pm-2"` y `.sello_reglas`.

## 3. Estados de un par (Modo D)
`pasa` (PM ≥ umbral, completo) · `no_pasa` (completo, bajo el umbral) · `incompleta` (algo sin evaluar: sin PM pero con **techo**) · `vetada` (alguna puerta `true`: PM 0). Solo `pasa` puede ser candidato (y aun así debe cumplir la puerta de entrada). Un par que no pasa **no se descarta con motivo canónico** salvo que la causa lo sea (puerta `marca_personal` → `dependencia_de_marca_personal`; `sustituto_gratis_cubre` → `sustituto_gratis_dominante`; `practica_vetada` por ingresos o salud → `claim_de_salud_o_ingresos`; por clonar landing, testimonios inventados o urgencia falsa → `linea_roja_de_contenido_o_negocio`, ya en `comunes` 1.4.0).

## 4. Calibración (cuándo tocar un peso)
Solo tras ≥ 2 corridas y con el dueño; nunca el Maker. Tras ~20 ofertas lanzadas, X2 recalibra pesos y umbrales; prior de éxito: 1 de cada 4 antes del ganador (no el «92 % venden» de los mentores, que mide «venden», no «escalan»). Correlación score vs. resultado ≥ 0,3 con ≥ 10 ofertas es condición del paso N3→N4 (spec §7).
