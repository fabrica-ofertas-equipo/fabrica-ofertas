# Presupuesto, tarifa y límites (de dónde sale cada número)

Regla madre: **ningún importe, plazo ni umbral está escrito en esta skill**. Todo sale de `economia.json` (D3), `empresa/limites.yaml` (solo el dueño) y `empresa/parametros.yaml`. Sin dato, no se calcula y no se arma (fail-closed, salida 5). Importes: enteros en la unidad menor de la moneda (nunca `float`).

## 1. Qué clave alimenta qué

| Magnitud | Fuente (clave) | Notas |
|---|---|---|
| `cpa_max` (= `cpa_equilibrio`) | `economia.cpa_be` | ya incluye bump, reembolsos y disputas; en `campana.economia.cpa_equilibrio/cpa_max` |
| `cpa_objetivo` | `economia.cpa_obj` | |
| `cpa_esperado` | `economia.cpa_real.central` | solo para validar y para el umbral de PURCHASE |
| `k_corte`, `n_dec` | `parametros.testeo.k_corte`, `testeo.n_dec` | |
| `n_anuncios_tope`, `n_anuncios_min` | `parametros.campana.*` | |
| días | `economia.dias_test`; si falta, `campana.dias_test_defecto`; rango `campana.dias_test_min/max` | |
| `spend_cap_factor` | `parametros.campana.spend_cap_factor` | |
| mínimo de `spend_cap` de Meta | `parametros.campana.spend_cap_minimo_meta` (opcional, `[VERIFICAR]` monto local) convertido con un tipo de cambio registrado | `campana.presupuesto.spend_cap_minimo_meta` |
| techo del test | `min(limites.gasto_total_test_por_oferta, limites.perdida_max_test_por_oferta)`; si falta uno → salida 5 | `perdida_max_test_por_oferta` está diferida por el dueño: con `null` nada gasta |
| tope diario | `limites.gasto_diario_por_oferta` | se compara con el **máximo teórico** |
| factor 1,75 | `limites.factor_techo_teorico_diario` | hecho de plataforma `[VERIFICAR]` |
| tarifa de ubicación | `economia.entradas_usadas.tarifa_meta_bp` (D3 la toma de `tarifas.json#recargo_meta_bp`) | `[PENDIENTE]` copia en `campana.economia` (`dependencias.md`) |
| mínimo diario de la cuenta | lectura `ads_get_ad_accounts` → `cuenta_meta.min_daily_budget` | |
| umbral de PURCHASE | `parametros.estadistica.meta_eventos_aprendizaje_semana` y `meta_fraccion_min_purchase` | hoy solo en la propuesta `empresa/propuestas/parametros-b0.yaml`: sin ellos PURCHASE no se confirma |
| moneda | `limites.moneda_limites` debe ser la de la campaña; si no, falta tipo de cambio registrado y no se arma | |

## 2. Fórmulas (las aplica `scripts/d7.py presupuesto`; no a mano)

1. `n_anuncios = min(anuncios del paquete, n_anuncios_tope, floor(techo_total / (k × cpa_max)))`; si queda `< n_anuncios_min` → no se arma (menos anuncios, **no** menos gasto por anuncio). El script además baja `n` mientras `n × k × cpa_max` no quepa en `total_visible_max`.
2. Corte = `n × k × cpa_max`. Validar = `n_dec × cpa_esperado`.
3. `total_visible_max = floor(techo_total / (spend_cap_factor × (1 + tarifa)))` (el `spend_cap` facturado con tarifa no puede pasar del techo; `meta.payloads.calcular_presupuesto` no incluye la tarifa).
4. Si `validar ≤ total_visible_max`: `total = max(corte, validar)`. Si no: `total = corte` y se declara **`SOLO_REFUTA`** con `techo_necesario_para_validar` (subir el tope es del dueño).
5. `dias` → `diario = total // dias`; `total_test = diario × dias`; `max_teorico_diario = ceil(diario × factor_techo)`; `spend_cap = half_up(total_test × spend_cap_factor)`; si queda bajo el mínimo de Meta → `spend_cap = null` + `candado_alternativo {stop_time = inicio + dias, lifetime_budget}` (nunca los dos). Todo esto lo hace `meta.payloads.calcular_presupuesto`.
6. Aborta (salida 5) si `max_teorico_diario > gasto_diario_por_oferta` (el mensaje sugiere cuántos días lo harían caber: decisión del dueño), si `diario < mínimo diario de la cuenta` o si `ceil(tope × (1 + tarifa)) > techo_total`.
7. `facturado_plan = ceil(total_test × (1 + tarifa))`: la tarifa va en la factura y **no** se ve en Ads Manager; el CPA que verá Ads Manager es `cpa_be / (1 + tarifa)`.
8. `monto_api = a_unidad_meta(monto, moneda)` (`meta.monedas`): offset 1 para CLP, COP, CRC, HUF, ISK, IDR, JPY, KRW, PYG, TWD, VND; 100 para el resto. Nunca el decimal ISO. Comprobar siempre que `campana.presupuesto.decimales` = exponente ISO 4217.

## 3. Evento de optimización

`evento_optimizacion` = `economia.evento_optimizacion_inicial` (`Purchase`→`PURCHASE`, `InitiateCheckout`→`INITIATE_CHECKOUT`); no se cambia en caliente. El script calcula el recomendado: `PURCHASE` si `diario ≥ fraccion × (eventos_semana / 7) × cpa_esperado`; si no, `INITIATE_CHECKOUT` y se informa cuánto falta por día.
- economía pide PURCHASE y el recomendado es IC → estado `EVENTO_INCOHERENTE` (sembrado S7): **no se arma**; se pide a D3 reemitir `economia.json` o decide H en la tarjeta. El Maker nunca cambia el evento por su cuenta.
- economía pide IC y alcanzaría PURCHASE → se mantiene IC y se anota.
- Se juzga siempre por compras de Stripe, no por las de Meta. Eventos esperados por semana = `7 × diario / cpa_esperado`: el aprendizaje limitado se asume y se declara.

## 4. Poder del test (lo que la tarjeta debe decir)

Descartar cuesta ≈ `k × cpa_max` por anuncio; confirmar un ganador ≈ `n_dec × cpa_esperado`. Un test chico **refuta, no valida**, y se escribe en la tarjeta. D7 no ejecuta la regla de decisión: la congela en `reglas_parada` (`k_corte`, `hash_parametros`) y la ejecuta D8.

## 5. Ejemplo numérico (A3 del spec; en `evals/dorados/D10.json`)

USD, `cpa_be` 16, `cpa_esperado` 12, n = 4, k = 3, 10 días, sin tarifa: corte 192, validar 180, total 192, diario 19,2, máximo teórico 33,6; umbral PURCHASE ≈ 43/día > 19,2 ⇒ `INITIATE_CHECKOUT` y lo dice. Con tarifa 3 %: facturado 197,76 y CPA visto 15,5. Contraejemplo (`D11`): CPA esperado > `cpa_be` ⇒ `NO_FACTIBLE`: no se arma, se escala al dueño sin gastar (04 §8.3).
