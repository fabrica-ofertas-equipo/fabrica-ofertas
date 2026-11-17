# Estructura, audiencia y categoría especial (decisiones del Maker)

El Maker **propone**; lo propuesto queda escrito en `campana.json` y justificado en la tarjeta. No hay «criterio libre»: cada decisión tiene regla.

## 1. Unidad de test

Una campaña por oferta (= un idioma/clúster). Los `paises_segmentacion` de `mercado.json` van juntos en **un** conjunto; dentro de una oferta no se compara país con país. Comparar mercados = comparar **ofertas de una familia** con presupuesto diario, fechas y evento iguales (docs/08 §7); eso no lo arma D7 dentro de una campaña.

## 2. Estructura

| Valor | Cuándo | `campana.estructura` |
|---|---|---|
| `CBO_1AS` (default) | 1 campaña, 1 conjunto Advantage+, `n_anuncios` de 3 a 6; junta eventos | `CBO` |
| `ABO_n` (cribado) | solo si el presupuesto ≥ `n × gasto_recomendado` de `decision.presupuesto.plan_celda`; **ordena** por clics de enlace e inicios de pago, no mata por compras; ≤ 48 h; los 1–3 mejores pasan a una campaña `CBO_1AS` **nueva** (agregar anuncios a un conjunto que aprende lo reinicia) | `ABO` |
| `AB_nativo` | fuera del test inicial | — |

v0.1: el cribado no se arma sin pedido expreso del dueño; su gasto cuenta dentro de `gasto_total_test_por_oferta`. Anuncios con gasto < `k × cpa_max` quedan «sin veredicto» (no se matan).

## 3. Audiencia (sin Instagram: identidad = fan page)

| Campo | Regla |
|---|---|
| `tipo` | `amplia` (default) o `intereses` (solo sugerencia; sin intereses sensibles). `lookalike` / `personalizada` **no** en v0.1: no hay semilla propia y las herramientas de audiencias están en `deny` (el lint da BLOQ) |
| países | exactamente `mercado.json.paises_segmentacion`, y ⊆ `limites.paises_permitidos` |
| `edad_min` | `limites.edad_minima_audiencia.defecto` (18); `edad_max` 65 |
| `genero` | `todos`. Género o 25+ solo como prueba A/B con gate H |
| `excluye_categorias_sensibles` | siempre `true`: nunca atributos de salud, finanzas personales, estado civil ni vulnerabilidades |

Preguntar al dueño (no asumir): género/edad distintos del default y el nombre visible del beneficiario DSA (`preguntas-abiertas.md`). `age_max` con Advantage+ Audience por API directa es `[VERIFICAR]` (`contratos/campana.schema.json`): usar 18–65.

## 4. `special_ad_categories`

La fija el dictamen de X1 según lo que el anuncio **ofrece**: `EMPLOYMENT` si ofrece listados de empleo; `FINANCIAL_PRODUCTS_SERVICES` si ofrece un producto financiero; la guía de carrera sin listados y la educación financiera sin producto **no** la requieren (25 §5.3). El Maker **no la decide ni la baja**: copia lo que dicta X1. Si ≠ `[]`: sin intereses, 18–65, preflight P25 obligatorio, gate H del dueño (no abogado: decisión 14). Verificación financiera de Meta (AU, IE, ES) o categoría omitida → parada dura; decide X1.

## 5. Ubicaciones, atribución, inicio

- `ubicaciones`: `automaticas` (Advantage+) por defecto; `feeds_y_reels` solo con razón escrita.
- `atribucion.ventana`: `7d_click` (informando también 1 d); Stripe es la verdad de ingresos y Meta la del gasto.
- `inicio`: **programar el inicio ya es activar**: mismo gate H; el script recalcula la hora. Si hay pre-aprobación de políticas, `compliance.anticipacion_preaprobacion_h` antes del inicio (amarillos). Mejoras automáticas de Meta apagadas (`OPT_OUT` en `text_optimizations`, `image_touchups`, `image_animation`, `inline_comment`, `enhance_cta`); `self_ai_disclosure` lo fija el dueño (`limites.politica_divulgacion_ia`), el Maker no lo infiere.

## 6. Qué NO decide el Maker

Copy y creativos (D6), riesgo y claims (D1/D3/X1), mercado (M1), topes (dueño), categoría especial (X1), `self_ai_disclosure`, mejoras de Meta (apagadas), género/edad restringidos (dueño), nombre DSA (dueño).
