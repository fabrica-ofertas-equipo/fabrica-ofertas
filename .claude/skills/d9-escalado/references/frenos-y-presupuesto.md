# Frenos de empresa y presupuesto (J4): dónde se verifican y qué pasa con `null`

> Fuentes: `decisiones-del-dueno.md` **J4** y J3, `mapeo.md` §4 y §12, `brechas/02` B2-04 y B2-09, `engine/README.md` (Decisiones 4, 8, 15-17), `engine/limites.py`, `engine/guard.py`, `empresa/limites.yaml`. Todo importe: entero en la unidad menor de `moneda_limites`; nunca `float`.

## 1. Los dos frenos

| Freno | Decisión | Clave | Valor en `empresa/limites.yaml` hoy |
|---|---|---|---|
| Techo global de gasto | J4: «300 US$/día» | `gasto_diario_global` | `null` (`limites.yaml:23`) |
| Pausa por pérdida acumulada | J4: «pausa automática a los 3.000 US$ perdidos acumulados» | `perdida_neta_acumulada_max` | `null` (`limites.yaml:35`) |

J4 dice que se cargan con `engine.propuestas proponer` y que **la firma del `limites.yaml` sigue siendo del dueño** (`engine.propuestas sellar`). D9 no los carga, no los sube ni los afloja: cuando el dueño los suba «con una firma cuando haya resultados» (J4), el informe semanal aporta la evidencia (cuántas propuestas válidas frenó el techo), no un número.

## 2. Dónde se verifican (y dónde NO)

| Qué | Dónde | Cuándo |
|---|---|---|
| Σ del **máximo teórico diario** (presupuesto × `factor_techo_teorico_diario` 1,75) de todas las campañas ACTIVE **más la del efecto** ≤ `gasto_diario_global`; por oferta ≤ `gasto_diario_por_oferta` | `engine.limites.exigir_agregados` (`engine/limites.py:268-355`), llamado por `engine.guard` paso 5 (`guard.py:350`) | al activar o subir (`activar`, `reactivar`, `aumentar_presupuesto`, `escalar`: `guard.py:121-127`) |
| Σ pérdida acumulada por oferta **+ Σ (`spend_cap` − gastado)** de las campañas ≤ `perdida_neta_acumulada_max` | idem, `engine/limites.py:342-343` | idem |
| gasto vitalicio + `spend_cap` restante ≤ `limite_gasto_cuenta_meta` | idem | idem |
| ritmo: ≤ 4 cambios/hora, ≥ 30 s, horas mínimas entre aumentos | `engine.limites.exigir_ritmo` (`:373`) | idem |
| % de paso, 1,75 ×, horas, techo de oferta | `decision.reglas.proponer_aumento_presupuesto` (`reglas.py:444`) | al proponer. **El guard NO lo verifica** (`guard.py:125-127`: `accion_gate=None`; `meta/subir_presupuesto.py` solo recibe un monto): P-11 |
| `empresa/PAUSA`, infra VERDE, firma y ancla de `limites.yaml` | `engine.guard` pasos 1-4 | siempre |
| **Pérdida realizada que llega a −3.000 → PAUSA** | **nadie** | `perdida_neta_acumulada_max` solo se comprueba **al activar o subir**; el watchdog recibe el gasto en `null` (`infra/workers/watchdog/src/index.mjs:116,118`) y su pausa devuelve `[]` (`:97`). Falta el vigilante continuo: P-12 (brecha B2-04) |

El dictamen de D9 llama a **la misma** `exigir_agregados_del_efecto` y a la misma `exigir_ritmo` (no las reimplementa), de modo que lo que la skill propone es lo que el guard aceptaría en ese instante; aun así el guard vuelve a comprobar al ejecutar.

## 3. Dos lecturas de «300 US$/día» (pregunta bloqueante #1 al dueño)

J4 dice «techo global 300 US$/día». El esquema y el código lo definen como techo del **máximo teórico** (`limites.schema.json`: «Techo del MÁXIMO TEÓRICO diario … factor × presupuestos diarios»), no de la suma de presupuestos. `[cálculo nuestro, con 1,75]`:

| Lectura | Presupuestos diarios que caben | Con arranque de 75 US$ |
|---|---|---|
| (A) **máximo teórico** ≤ 300 (lo que hace el código) | ≤ 171 US$ en total (300 / 1,75 = 171,4) | ×2 = 150 (máx. teórico 262,5): cabe · ×3 = 225 (393,75): **no cabe** · ×5: no cabe |
| (B) **suma de presupuestos** ≤ 300 (cómo lo dijo el dueño) | ≤ 300 US$ en total | ×2 = 150 · ×3 = 225 · ×5 = 375 (no cabe) |

Cambia el alcance real de la escalera (en (A), ×3 y ×5 casi no existen desde 75 US$/día) y el de la réplica. La skill aplica (A) porque es lo que el código exige; **la decisión es del dueño** y, si es (B), S-A cambia el esquema (`PEDIDOS.md` P-08).

## 4. Consecuencias que el dueño debe ver

- **El `spend_cap` de una ESCALA cuenta contra los −3.000 antes de perderlos.** El freno suma pérdida real + `spend_cap` restante de cada campaña: una ESCALA con un `spend_cap` grande bloquea la siguiente suba mucho antes de perder 3.000 US$. El `spend_cap` lo define D7/`meta.payloads`, no la IA (`FALTA_SPEND_CAP` si no llega).
- **Cada hija es una oferta más en la suma.** `ofertas_en_test_simultaneas_max` cuenta ofertas con campañas ACTIVE (incluidas las ESCALA) y la coherencia de `limites.yaml` exige `ofertas_simultáneas × gasto_diario_por_oferta ≤ gasto_diario_global`. `[cálculo nuestro]`: con 300 US$ de máximo teórico, 20 idiomas simultáneos serían 15 US$ de máximo teórico cada uno (≈ 8,6 US$ de presupuesto); abrir un mercado nuevo con «50 US$ por día» (`know-how.md` §4.3) pesa 87,5 en el máximo teórico: caben 3 a la vez, y `mercados.mercados_test_paralelos_max` hoy dice 1. La **amplitud de J5 la limita el techo**, no la traducción.
- **Un día malo cuesta como máximo el techo.** Con el lanzamiento de J3 (50-100 US$) y la baja al día 1, la pérdida por oferta queda acotada por la regla (~1 día de gasto); en la escala la acotan la reducción −30 %, la reversión automática a 96 h y estos dos frenos.

## 5. Fail-closed con `null`

`engine.limites` y `scripts.validar_esquemas.CLAVES_CRITICAS["escalar"]` exigen no nulas (`validar_esquemas.py:603-605`): `gasto_diario_global`, `gasto_diario_por_oferta`, `aumento_presupuesto_max_pct_por_paso`, `horas_min_entre_aumentos`, **`stop_loss_escala`**, `dias_cobertura_caja`, `perdida_neta_acumulada_max`, `limite_gasto_cuenta_meta`; el dictamen suma `moneda_limites`, `factor_techo_teorico_diario`, `max_cambios_presupuesto_por_hora_por_conjunto`, `segundos_min_entre_ediciones` y `ofertas_en_test_simultaneas_max`. Hoy **todas están en `null` salvo el factor y los hechos de plataforma** (`limites.yaml:23-53`): el dictamen contra los archivos reales responde `BLOQUEADO / LIMITES_INCOMPLETOS` (5) con la lista. Eso es correcto. La skill **no sugiere valores**: lista las claves, a quién se le piden y se detiene.

- **Choque abierto (P-08):** `stop_loss_escala` (pérdida de contribución de *una* oferta en escala) es clave crítica de `escalar`, pero J3/J4 dicen «no hay tope de pérdida por oferta». O el dueño lo firma, o S-A lo quita de `CLAVES_CRITICAS["escalar"]`. La skill no recomienda crearlo (decisión del dueño) y mientras esté `null` nada escala.
- **Caja (F1)** (`dias_cobertura_caja`, payouts, reserva de Stripe de hasta 120 días): `capital.json` no existe; el dictamen v0.1 solo exige que la clave no sea `null`. El expediente declara la caja `[SIN DATO]` y el dueño la ve (P-10).
- **Moneda**: todo en `moneda_limites`; otra moneda es error de validación (3). Monedas con offset 1 (CLP, JPY…) aún no se admiten (`engine/limites.py` `MONEDAS_META_OFFSET_1`).

## 6. Qué hace la skill ante un tope

No propone ni «un paso más chico por prudencia»; informa (a) qué tope frenó (`LIMITE_DIARIO_EMPRESA`, `TECHO_OFERTA`, `PERDIDA_ACUMULADA_EMPRESA`, `LIMITE_CUENTA_META`), (b) cuánto faltó, (c) que solo lo mueve la firma del dueño. Una propuesta que el QA encuentre por encima de un tope (aunque sea por un centavo) es BLOQUEANTE.
