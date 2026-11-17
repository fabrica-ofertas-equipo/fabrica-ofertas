# Economía y factibilidad: el motor decide, D3 propone

**Autoridad única: `engine/factibilidad.py` (versión 1.2.0).** La skill propone precio, bump, garantía y ángulos; **nunca calcula la economía a mano** (ni «a ojo», ni con calculadora mental, ni redondeando). Todo número de `economia.json`, de la tabla por país de `oferta.md` y de cualquier frase como «razón 1,48» sale del motor. Si el motor no corre (falta un parámetro: salida 5), la oferta se detiene en `parada.json`; no se estima.

## 1. Comando exacto (docstring del motor; desde la raíz del repositorio)
```
.venv/bin/python -m engine.factibilidad calcular --entradas ENTRADAS.json [--parametros empresa/parametros.yaml] [--limites empresa/limites.yaml] [--salida ofertas/<id>/03-oferta/economia.json]
.venv/bin/python -m engine.factibilidad verificar --economia ofertas/<id>/03-oferta/economia.json [--parametros empresa/parametros.yaml] [--limites empresa/limites.yaml]
```
Salida: 0 correcto · 2 uso · 3 entrada inválida o `verificar` con diferencias · **5 falta un parámetro** (`ParametroFaltante`). Con `limites.yaml` en `null` NO sale 5: el motor calcula y lista `limites_pendientes[]` (sin límites la oferta se calcula pero no autoriza gasto; lo cierra `engine.guard`).
Siempre pasa `--parametros empresa/parametros.yaml` (de ahí salen `economia.razon_min_factible`, `testeo.k_corte`, `testeo.n_dec`, `economia.penal_evento_senal`) y `--limites empresa/limites.yaml` (para `limites_pendientes`).

**Por país:** el motor calcula UN país por corrida (un `tasa_iva_bp`, un `tarifa_meta_bp`). Para el clúster usa el envoltorio, que llama al motor una vez por país, guarda el `economia.json` del **peor país** (menor razón) y escribe la tabla de `oferta.md`:
```
.venv/bin/python .claude/skills/d3-arquitectura-oferta/scripts/economia_por_pais.py --plan PLAN.json --parametros empresa/parametros.yaml --limites empresa/limites.yaml --salida-economia ofertas/<id>/03-oferta/economia.json --salida-tabla TABLA.md
```
`PLAN.json` = `templates/plan-economia.json` (`base` común + `paises{pais: {tasa_iva_bp, tarifa_meta_bp, …}}`; sin las constantes del evento de aprendizaje: salen de `estadistica.*`). No contiene fórmulas: llama a `engine.factibilidad.documento_economia`. Sin el envoltorio (p. ej. un runner que solo permite la CLI del motor) corre `calcular` una vez por país y guarda a mano **el archivo del peor país** (menor `razon`).
El plan es un archivo de trabajo: **no se promueve** (la carpeta `03-oferta/` solo lleva los archivos de la tabla 2 de `contratos-y-rutas.md`); escríbelo en la carpeta de trabajo que indique el encargo (`$AGENT_STAGING/.plan/` o un temporal) [PENDIENTE: ruta de las entradas en el runner, `dependencias.md`].

## 2. Qué entra al motor y de dónde sale (todo en unidad menor de la moneda de la oferta)
| Entrada | Fuente | Si falta |
|---|---|---|
| `moneda`, `precio` (con IVA incluido), `precio_bump` | oferta (propuesta de D3) | — |
| `tasa_bump_bp`, `tasa_reembolso_bp`, `tasa_disputa_bp` | `parametros.economia.*` (hoy 1000 / 700 / 50) | override solo con fuente D2/M1, declarado en `supuestos[]` («override … D2/M1») |
| `factor_cpa_objetivo_bp` | `parametros.economia.factor_cpa_objetivo` (cadena `"0.6"` → `6000`) | — |
| `escenarios.{pes,central,opt}.{ctr_enlace_bp, clic_compra_bp}` | `parametros.economia.escenarios_embudo` **sin tocar** | override solo con fuente D2/M1; si la razón solo pasa con override, L1-04 = MAYOR |
| `escenarios.*.cpm` | `mercado.cpm_esperado` (el mismo CPM en los tres escenarios: la clave `economia.escenarios_costo` aún no existe, ver `dependencias.md`) | sin CPM de M1: `[HIPÓTESIS]` con su fuente y `tarifas_origen`/`supuestos[]` lo dicen |
| `comision_pct_bp`, `recargos_bp`, `conversion_bp`, `comision_fija`, `tarifa_disputa`, `stripe_tax` | `empresa/finanzas/tarifas.json` por (país, método); sin él, `docs/_investigacion/03-stripe.md` §4.1 (tarjeta de la LLC de EE. UU.: pct + recargo internacional + conversión; fija y disputa **convertidas a la moneda de la oferta** con un tipo de cambio declarado) con `tarifas_origen = supuesto` y `tarifas_fuente` con la marca `[SUPUESTO]` | nunca 0 sin declararlo: L1-04 marca `comision_fija = 0` |
| `tasa_iva_bp` | `tarifas.json` (`iva_bp` del país); sin él, la tasa general del país de `docs/_investigacion/07*-*.md` con `[VERIFICAR]`. La tasa reducida de e-book solo con respuesta del contador | **nunca 0** salvo que `supuestos[]` diga «IVA 0 % / no aplica» (S5) |
| `tarifa_meta_bp` | `tarifas.json` (`recargo_meta_bp` del país; hoy IT/FR/ES 300, UK 200, AT 500, PL 0 según la spec `[VERIFICAR]`) | `[VERIFICAR]` |
| `costo_variable` | D4/D5 (entrega y correo por pedido); sin dato, el de la spec/ejemplo con `[SUPUESTO]` | — |
| `costos_fijos_oferta` | `0` salvo costos reales declarados | suman a `perdida_max_test` |
| `gasto_diario` | regla de §3 | — |
| `k`, `n_dec`, `razon_min_factible`, `penal_evento_senal` | `parametros` (no van en el plan: el motor los toma con `--parametros`) | salida 5 |
| `eventos_semana_aprendizaje`, `fraccion_aprendizaje_min_bp` | `estadistica.meta_eventos_aprendizaje_semana` (50) y `estadistica.meta_fraccion_min_purchase` (`"0.5"` ⇒ 5000 bp = fracción × 10000) de `--parametros`; **no** `economia.*`. `economia_por_pais.py` los traduce y los añade al plan (un valor distinto en el plan se rechaza como override sin fuente) | falta una clave ⇒ sale 5 (sin ellas el motor asumiría `Purchase` en silencio). El motor decide `Purchase` o `InitiateCheckout`; **el Maker no lo decide ni fija `evento_optimizacion_inicial`** |
| `mix_metodos` | solo si `mercado.metodos_pago.fase` ≠ `estandar_tarjeta_billeteras` **y** `tarifas.json` existe | v1 = tarjeta y billeteras; con BLIK/Satispay/Pix diferidos no se modela mezcla |

**Método local ⇒ moneda local** (BLIK → PLN; Satispay y Bancontact → EUR; Pix → BRL). Si `mercado.metodos_pago.activos` trae un método local y la oferta cobra en otra moneda, es BLOQUEANTE (S20); si `fase = estandar_tarjeta_billeteras` no puede haber métodos locales activos.

## 3. `gasto_diario` (la única entrada que elige D3 además del precio)
1. `gasto_diario` ≤ `brief.presupuesto.test_diario_max` y, si no es `null`, ≤ `⌊limites.gasto_diario_por_oferta / limites.factor_techo_teorico_diario⌋` (L1-08: 1,75 × diario ≤ el máximo diario).
2. `gasto_test_plan` (= diario × `dias_test`, lo da el motor) ≤ `brief.presupuesto.test_total_max` y ≤ `limites.gasto_total_test_por_oferta` (misma moneda; si difiere, convierte con el tipo de cambio de F1).
3. Si excede, **baja `gasto_diario`** y vuelve a correr (más días); si ni con el mínimo cabe, el test no es financiable con esos techos: eso **no es una palanca de la oferta** → `parada.json` `no_factible_escalar` con la cifra `presupuesto_test_min` frente al techo.
4. Un `gasto_diario` bajo activa `InitiateCheckout` y multiplica el CPA real por `penal_evento_senal` (hoy 1,25): subir el gasto diario puede cambiar el veredicto; pruébalo con el motor, no lo estimes.
5. `perdida_max_test` ≤ `limites.perdida_max_test_por_oferta` **tras convertir a `moneda_limites`** con el tipo de cambio de F1 (`empresa/finanzas/tipos_cambio.jsonl`). Con ese tope en `null`: no hay gasto autorizado (oferta.md §A lo dice).

## 4. Veredictos (enum del contrato) y qué hace D3 con cada uno
| Veredicto | Condición del motor | D3 |
|---|---|---|
| `FACTIBLE` | `razon ≥ economia.razon_min_factible` y `cpa_be > 0` | Sigue. `razon ≥ razon_min` solo dice que el test vale la pena; **escalar exige `razon_obj ≥ 1`** (dilo en oferta.md §A) |
| `AJUSTADA` | `1,0 ≤ razon < razon_min` | Intenta las palancas (ciclo 1); si sigue AJUSTADA entrega con **H explícito** (oferta.md §A lo pone primero) |
| `NO_FACTIBLE` | `razon < 1,0` o `cpa_be = 0` | **No pasa a D4.** Palancas (≤ 2 ciclos) y, si no alcanza, `ESCALAR` con evidencia (§6). `puntaje.total ≤ 59` |

## 5. Palancas y ciclos (≤ 2; luego `ESCALAR`)
Un **ciclo** = una revisión del diseño (pasos 4-6 del SOP) motivada por `NO_FACTIBLE` o `AJUSTADA`, seguida de una corrida del motor. Dentro de un ciclo puedes correr el motor sobre varios escalones de precio (barrido): eso es **una** revisión. Orden fijo:
1. **Precio**: barre los escalones locales ascendentes (14,90 → 19,90 → 24,90 €; 49 → 69 → 89 zł; [HIPÓTESIS, 08 §3]) hasta el tope de `economia.precio_lista_rango` (en USD equivalentes; convierte con el tipo de cambio de F1 o, sin él, uno declarado `[SUPUESTO]`) y elige **el menor con `razon ≥ razon_min` en TODOS los países**. Por encima del rango: gate H, no lo hagas tú.
2. **Bump**: precio del bump dentro del rango `landing.bump_pct_precio_min`–`landing.bump_pct_precio_max` del precio (hoy 30-60 %; única fuente del tope; ≤ 40 % es solo una recomendación [HIPÓTESIS] mientras no haya toma real); contenido más ligado a la promesa. **La toma (`tasa_bump_bp`) no se sube sin evidencia**: es de `parametros.yaml`.
3. **Mercado**: quita del clúster los países con `razon < razon_min` (la economía se rehace por país). Si el único país es inviable: escala.
4. Nada más. **No son palancas** (y L1-04 las detecta): subir CTR o conversión, bajar CPM, omitir IVA o la comisión fija, bajar `tasa_reembolso_bp`/`tasa_disputa_bp`, cambiar `factor_cpa_objetivo`, cambiar el veredicto, ni inventar métodos de pago locales. Cambiar de mecanismo o de vehículo es **devolver a D1**.

## 6. `NO_FACTIBLE` con evidencia: cuándo decir NO y cómo
D3 es el último punto barato para frenar una oferta inviable: decir NO aquí cuesta cero; en la campaña cuesta `perdida_max_test`. Tras el ciclo 2:
1. Escribe `parada.json` (`templates/parada.json`, `estado: no_factible_escalar`, `ciclos_usados: 2`) y la sección **C** de `oferta.md` con `templates/informe-inviabilidad.md`: una fila por corrida del motor (palanca, precio, bump, países, `razon` del peor país, veredicto), el CPA de equilibrio máximo alcanzable frente al CPA real central, y las opciones para el dueño.
2. Entrega igualmente `oferta.json` (mejor intento; `puntaje.total ≤ 59`; `supuestos[]` con «NO_FACTIBLE») y `economia.json` del mejor intento: el dueño decide con datos. El QA no lo trata como un fallo del Maker: `ESCALAR` (backbone 5.4).
3. Nunca «afines» escenarios para que pase (S14) ni dejes un texto que diga «rentable» sobre una economía NO_FACTIBLE (S4).

## 7. Lo que el motor no modela hoy (PEDIDOS, en `dependencias.md`)
Costos de reembolso y disputa **por escenario** (`economia.escenarios_costo`: hoy `r` y `d` son únicos y la spec pide usar la fila `pes` en amarillo), CPM por escenario (por diseño hay **un CPM por mercado**; el 1,5× es la sensibilidad de M1, no un escenario de D3), `iva` reducido de e-book, mezcla de métodos locales en v1, conversión de moneda de límites, y el plan de test con `InitiateCheckout` como estado de decisión del dueño. Mientras tanto: usa los `[SUPUESTO]` declarados y **no los compenses a mano**.
