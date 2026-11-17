# Algoritmo de selección de mercado (SOP pasos 3-7)

> Fuente: `departamentos/16-mercados-localizacion.md` §4.1; modelo de `docs/_investigacion/08-mercados-ranking.md` (§2.1, §5) corregido por `16-red-team-mercados-y-modelo.md` (H1, H2, M1, M2) y reproducido por `scripts/mercados/rank.py` (08b). Todo número de abajo es una CLAVE de `empresa/parametros.yaml#grupos.mercados` (o su fallback `[SUPUESTO]` en `scripts/parametros_m1.fallback.json`): **nunca copies un número a una ficha, a un informe o al código**.
> Regla de oro: **determinista**. Mismos datos versionados ⇒ mismo orden; el LLM carga datos con fuente y redacta, nunca calcula el puntaje.

## 0. Cómo se ejecuta (todo con `.venv/bin/python -I`, desde la raíz del repo)

```
python -I .claude/skills/m1-mercados-localizacion/scripts/puntaje.py reproducir          # PRIMER paso de toda corrida
python -I .../puntaje.py cobertura FICHA.json --decision-mp {no_decidido|si|no}          # cobertura por fase de UN país
python -I .../puntaje.py excluir CONTEXTO.json --hoy AAAA-MM-DD                          # R1-R10
python -I .../puntaje.py seleccionar CONTEXTO.json --hoy AAAA-MM-DD > seleccion_mecanica.json
```
`CONTEXTO.json` (ver `evals/dorados/D01-*/contexto.json`): `limites{paises_permitidos, locales_permitidos, nivel_max_lanzable?}`, `candidato{candidato_id, macro_nicho, riesgo{P,C,E,N,nivel}, banderas{S,R,D}?, etiquetas[], fuera_de_macro_nicho}`, `fase_pagos`, `decision_managed_payments`, `regimen_fiscal`, `exposicion_fiscal_firmada_paises` (`null` = firma pendiente del gate H; lista = decidida), `primer_lanzamiento_en_locale`, `fichas{ISO: ruta|objeto}`, `matriz?` (X1; si falta se usa `scripts/semilla_exposicion.json` y se marca `[SUPUESTO]`).
Si `reproducir` no imprime `ok: true` (rank.py ya no reproduce los 15 totales de 08 §2.2 ni el escenario `corregido`), **PARA y avisa**: el modelo cambió y manda el contrato (MQ-09).

## 1. Exclusiones duras (fail-closed; por par `(país, locale)`)

| Regla | Excluye cuando | Reabre con | Dónde se implementa |
|---|---|---|---|
| R1 | país ∉ `limites.paises_permitidos` o locale ∉ `limites.locales_permitidos`. **Listas vacías o `null` ⇒ salida 5: no se evalúa nada** | decisión del dueño (fuera de la skill) | `puntaje.excluir` |
| R2 | candidato rojo, `fuera_de_macro_nicho`, o nivel > `nivel_max_lanzable[macro]` (limites 1.3.0; niveles en minúscula `verde`/`amarillo-a`/`amarillo-b`; `null` o macro ausente = SOLO VERDE, fail-closed) | reencuadre seguro que baje el nivel | ídem |
| R3 | restricción de la matriz de X1 `{pais, macro, tipo: promesa\|contenido\|modelo, condicion, id_check}` disparada por una **etiqueta del candidato** (promesa/contenido FINAL tras el reencuadre) — o EXPO no puntuable (sin fila de matriz, amarillo-b con exposición A+/R) | reencuadre que quite la etiqueta | ídem; `references/matriz-exposicion.md` |
| R4 | sin línea de ayuda verificada del país para la categoría central (etiqueta `requiere_ayuda_emocional` o amarillo-b), o amarillo-b sin gate H | X1 verifica `ayuda_por_pais` / gate H firmado | ídem |
| R5 | `obligacion_legal_idioma` sin revisor nativo (`contratado`/`activo`); cluster `en-CA` que incluye Quebec | contratar revisor; sacar Quebec | ídem |
| R6 | cobertura de pago de la **fase vigente** < `cobertura_pago_min_duro`. Entre el duro y `cobertura_pago_min_blando`: pasa con bandera `cobertura_media` (+ gate H + `valor_desbloqueo_pp`) | fase `con_locales` (decisión del dueño + MINOR del contrato) | `puntaje.cobertura_por_fase` |
| R7 | moneda de cobro no declarada, o el método clave exige una moneda no cobrable | declarar/precio en esa moneda | ídem |
| R8 | `fiscal.regimen = diferido` en país con IVA/registro desde la primera venta **y el dueño ya decidió** la exposición sin cubrir ese país (`firmada` lista que no lo incluye). Con la firma pendiente (`null`) es **bandera** `requiere_firma_exposicion_fiscal`: el sellado la exige (MQ-07). No aplica con Managed Payments = sí | firma del dueño por país, o `stripe_tax`/`merchant_of_record` | ídem |
| R9 | `r_b = r / bump_aov_factor` > `r_max` (neto completo, `mult_cpm` central) | ticket mayor o bump probado | `puntaje.seleccionar` |
| R10 | ficha con datos críticos vencidos: tarifas > `vigencia_tarifas_dias`, legal > `vigencia_legal_dias`, o sin fuente/fecha/confianza (MQ-02). **El CPM vencido NO bloquea**: bandera `cpm_vencido`, MAYOR, etiqueta `[SUPUESTO]` | reverificar con fuente oficial | `scripts/vigencia.py` |

Una exclusión es **de un par**, nunca de un tema: el motivo cita promesa/contenido/modelo y qué lo reabre. Un reencuadre seguro (nota 25 §4) que baje el nivel reabre el par.

## 2. Puntaje de 9 criterios (0-5 cada uno; total = Σ peso·puntaje / 5)

Pesos: `mercados.pesos.{PA,CAC,COMP,PAGO,FISC,LOC,FRAUD,EXPO,ESC}` (suman 100; MQ-09). **Peso del ajuste de creadores = `mercados.peso_ajuste_creadores` = 0**: se calcula y se muestra aparte (`ajuste_creadores_informativo`), jamás entra al total ni desempata (decisión del dueño 2026-11-06).

| Criterio | Regla |
|---|---|
| PA | consumo por habitante vs. media UE y ticket observado (08 §2.1; dato de `scripts/mercados/datos/mercados.json`) |
| CAC | `r = CPC / (neto · conv_esp)` **sin bump**. `CPC = CPM · mult_cpm · (1 + f_meta) / (1000 · CTR)`; `CTR = mercados.ctr_enlace_central`; `conv_esp = clamp(2 %·(17,3/P)^0,5; 1 %; 3 %)`; `neto = (1−ρ)·neto_ok − ρ·(comisión + Tax) − d·15·part_tarjeta` (16 §2.1: el reembolso devuelve bruto e IVA y la comisión se pierde; disputa con tarjeta cuesta 15 USD; BLIK no cobra tarifa de disputa). Bandas de `r` en `scripts/mercados/datos/parametros.json` (08 §2.1). **Saturación:** con neto completo casi todo `r` > 2,2 y el criterio deja de discriminar ⇒ el puntaje central usa `cac_modo = relativo` (bandas reancladas por la mediana); el nivel absoluto lo garantiza R9 |
| COMP | saturación **con** señal de demanda, no solo cantidad de anuncios (16 H7: «competencia baja» no es oportunidad por sí sola); peso bajo |
| PAGO | `cobertura` de la **fase vigente** (`references/pagos-por-fase.md`): bandas de `scripts/mercados/datos/parametros.json#reglas_pago`. Se informan SIEMPRE ambas fases, `valor_desbloqueo_pp` y el hueco PayPal |
| FISC | 4 umbral alto y Stripe presenta · 3 umbral global · 2 OSS desde la primera venta · 1 formalismo extra (Impressum, Toubon, representante). Managed Payments lo sube (`references/managed-payments.md`) |
| LOC | 5 inglés/español · 3-4 idiomas con buen soporte de IA · 1-2 difíciles, con revisor escaso u obligación legal |
| FRAUD | disputas del método dominante, COD, normas de desistimiento |
| EXPO | exposición del país × nivel del candidato, **por bandera y macro (+ secundario), tomando la PEOR**: tabla en `scripts/semilla_exposicion.json#tabla_expo` (verde V5·A4·A+3·R2; amarillo-a V4·A3·A+1·R0; amarillo-b V2·A1; A+/R excluidos) |
| ESC | alcance publicitario/población del locale (bandas `scripts/mercados/datos/parametros.json#escala`) |

El subnivel amarillo-a/B se deriva de los colores de los ejes P,C,E,N (un eje amarillo = A; dos o más = B) porque `candidatos` 1.0.0 no trae `subnivel` `[SUPUESTO]`.

## 3. Orden, bloques y K
1. Orden por total; **empate si la diferencia < `mercados.empate_puntos`** (el modelo mueve 4 puntos por 1 punto de error en un criterio de peso 20 %). Desempate: menor carga fiscal (FISC mayor), luego base sin ajuste. **Un empate NO se rompe con el ajuste de creadores ni con impresiones.**
2. `puntaje_minimo`: por debajo, bandera `bajo_minimo` + gate H (no exclusión: se calibró sin neto completo; recalibrar con ≥ 8 pares mercado-oferta con resultado).
3. **Bloque** = 1 `locale` + países de **misma moneda y régimen**; puntaje del bloque = media simple de sus países `[SUPUESTO]`. Clusters con monedas distintas se separan (en-CA/AU/NZ no se mezclan).
4. Elige **K ≤ `mercados_test_paralelos_max`** (hoy 1: un mercado a la vez, R-C01; `docs/03` ya lo dice; subir el parámetro es decisión del dueño, ver `dependencias.md` I1). Con K = 1 el presupuesto decide si la oferta funciona en ese mercado (T3), **no compara mercados**.
5. Si hay presupuesto, un **brazo de exploración** de menor puntaje para contrastar el modelo (se declara como tal en `elegido.exploracion`; cuenta dentro de K).

## 4. Sensibilidad (obligatoria; `puntaje.seleccionar` la calcula)
CTR 1,0 / central / 1,8 %; `mult_cpm` 1,0 / central / estrés; pesos iguales; con/sin ajuste de creadores (informativo); fase vigente vs. `con_locales`; Managed Payments sí/no. Se informa si el elegido **sigue en el top 3** en cada escenario y qué escenarios lo sacan. Un elegido que solo gana en el central se declara frágil.

## 5. Presupuesto de test sugerido (M1 sugiere, no asigna)
`por_mercado = clics_min_decidir_mercado × CPC_central` (el CPC ya incluye `f_meta` y `mult_cpm`: **no los apliques otra vez**, MQ-19); `total = K × por_mercado` recortado a `limites.gasto_total_test_por_oferta` / `perdida_max_test_por_oferta`; con límites `null` ⇒ `limites_pendientes[]` y nada se asigna. Si el tope es menor que lo necesario, o los clics < `clics_min_decidir_mercado`, la salida dice **«señal de proceso»** y `estado_decision` no cambia (16 H3: ~60-75 USD por país detecta fallas de proceso, no decide mercados).

## 6. Divergencias conocidas (se registran, no se arreglan aquí)
- Disputas: `rank.py`/16 §2.1 usa `d·15·part_tarjeta`; `engine/factibilidad.py` usa `d·(neto + tarifa)`. Si el neto de M1 difiere del de D3, el QA lo anota en `contradicciones[]` (MQ-17) y manda el contrato. Pedido a D3/F1: unificar y fijar `part_tarjeta` por método.
- `rank.py` solo cubre 15 mercados (sin RO, FR, DE, AT, CZ, HU, MX, BR, NL): para ellos `puntaje.py` evalúa R1-R10 pero **no puntúa** (`paises_con_ficha_sin_desglose_de_ranking`); hace falta añadir su desglose en una copia de `scripts/mercados/datos/mercados.json` con fuente `[VERIFICAR]` (modo atlas).
- Todo CPM de `scripts/mercados/datos/mercados.json` es del 2026-07-27 (Lebesgue, C, sin metodología): siempre `cpm_vencido` hasta refrescarlo.
