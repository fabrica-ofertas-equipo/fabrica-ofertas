# Criterio de ganador: qué dice la fuente, qué no dice y quién lo firma

> Es la pieza más débil de todo el sistema y la que más dinero mueve (brechas 02, B2-06 y E-05). **Ningún umbral de esta página está firmado por el dueño.** El código lo lee de `parametros.yaml`; hoy ese archivo no trae los de «campeón», así que el dictamen responde `BLOQUEADO / PARAMETRO_FALTANTE` (5) y la skill no propone nada. Los valores de abajo son lo que proponen las fuentes y sirven para probar el código (`evals/_base/parametros_prueba.json`, todos `[SUPUESTO]`).

## 1. Qué dice cada fuente

| Fuente | Qué dice | Certeza |
|---|---|---|
| Sistema de referencia (`know-how.md` §4.2; `brechas/02` A.2) | Producto de 27 US$. Un creativo que vende a **CPA 15-18** es rentable y **se queda en testeo** (hay muchos). El **ganador de verdad** es **≥ 10 ventas a CPA 6-7** (ROAS 3-5; «con una sola venta cualquiera tiene buen ROAS»). **3 de cada 100** creativos lanzados lo son | `[V][DECL]`: dicho de voz, sin verificar |
| Sistema de referencia (`know-how.md` §1, §12.3) | Antes tenía dos criterios contradictorios («10 ventas a CPA < 10» y «15 ventas a ROAS 2») y se pisaban; unificó en **un solo archivo de criterio** que posee el auditor. **El criterio final no se muestra** en el video | `[V]`; el valor final es desconocido |
| D8, código real (`engine/d8.py:388-462`, `decision.reglas.evaluar_oferta_validada`; `docs/08` §8) | **VALIDADA**: cohorte **madura** (último pedido + garantía + `veredicto.madurez_dias_extra`, no antes de los 28-35 días), compras netas ≥ `veredicto.compras_min` (15), compras en ≥ 3 días, ningún día > 50 %, reembolsos ≤ 8 %, P(CPA ≤ equilibrio real) ≥ `testeo.p_escala` (0,80) y CPA neto ≤ objetivo real; segundo corte confirmatorio. **PROMETEDORA**: cumple salvo CPA entre objetivo y equilibrio | código existente; sus valores son `hipotesis: true`, `ultima_calibracion: null` |
| `mapeo.md` §3.2 y §12 (S-C) | **Campeón de creativo `[HIPÓTESIS]`**: ≥ 10 compras netas y CPA ≤ **0,40 × CPA de equilibrio** (el del video: ≈ 0,25-0,30 × BE). Se recalibra con la tasa de campeones medida | propuesta, no decisión |
| `analisis/testeo-escala-robots.md` §5 pregunta 9 | Recomienda B: «10 compras, CPA ≤ 0,40 × BE **y P ≥ 0,80**, recalibrable con la tasa de campeones medida. **No sustituye a VALIDADA**» | recomendación |
| Skill `d8-optimizacion` (misma sesión de S-C, `d8-optimizacion/references/decisiones-y-umbrales.md` U-30 a U-34) | Pide **las mismas claves** que esta skill: `escalado.campeon_compras_min`, `escalado.campeon_cpa_max_x_be`, un criterio «rentable» (P ≥ `testeo.p_escala` con ≥ `testeo.n_dec` compras) y `auditor.acierto_min` (0,5 cortes / 0,6 subas). Su acción `GRADUAR` (contrato `ESCALAR`) es el disparador `CAMPEON` de D9 | alineado; un solo cambio de S-A (P-02) sirve a las dos |
| `parametros.yaml:1286+` (D9 viejo) | `escalado.promocion_min_compras` = 5 (promover un concepto del laboratorio); `testeo.n_dec` = 15 | `hipotesis: true` |

## 2. Lo que la fuente NO dice

- El criterio final unificado del sistema de referencia, y si su «retorno por dólar» es ingreso/gasto o beneficio/gasto (`know-how.md` §12.4). Su ROAS bruto declarado (≈ 1,99) no prueba margen **neto**: aquí se mide CPA neto de Stripe (compras netas de reembolso).
- Qué pasa entre el CPA «rentable» (15-18) y el «campeón» (6-7): no hay niveles intermedios publicados.
- Cuál de los criterios (D8 `VALIDADA` de 28-35 días, el campeón por compras y CPA, o el de D9 con 5 compras) **rige para graduar**, cuál **para escalar** y cuál **para VALIDADA**. Es la decisión **E-05 del dueño**.
- Cuántos días de tendencia (el video dice 3 días: regla de oro 3) frente al día 1 de J3 (que es del lanzamiento, no de la escala).

## 3. Niveles que usa la skill

| Nivel | Qué es | Quién lo calcula | Umbral | Estado del umbral |
|---|---|---|---|---|
| `SIN_SENAL` | 0 compras netas | código | — | — |
| `VENDIO` | ≥ 1 compra neta con el presupuesto del día gastado (supervivencia del día 1, J3) | D8 | — | J3 firmada |
| `RENTABLE` | CPA neto ≤ `cpa_obj` de `economia.json`: **se queda en test, no escala** | `escala_lectura.py` | `cpa_obj` | viene de D3 (`economia.json`) |
| `CAMPEON` | graduable a una ESCALA: compras netas ≥ `escalado.campeon_compras_min`, CPA neto ≤ `escalado.campeon_cpa_max_x_be` × `cpa_be` y P(CPA ≤ equilibrio) ≥ `testeo.p_escala` | `escala_lectura.py` (provisional; luego `engine/escala.py`, P-10) | **`[SUPUESTO]` 10 · 0,40 · 0,80** | sin firmar; `campeon_*` no existen en `parametros.yaml` (P-02) |
| `VALIDADA` | `veredicto_oferta.estado = VALIDADA` (backbone 5.9) | D8, **no se recalcula en D9** | los de §1 | código vigente; confirmación `H` del dueño (`accion:confirmar_validada`) |

Reglas de uso: (1) solo `CAMPEON` y `VALIDADA` habilitan graduar o subir; (2) `RENTABLE` no es un fracaso: sigue en testeo y alimenta el banco de relevos; (3) un `CAMPEON` **no es** `VALIDADA` y no se presenta como tal; escalar a un campeón sin `VALIDADA` es una «escala provisional» que `docs/08:342` permite («un paso pequeño») y `departamentos/09-optimizacion.md:113,131` niega (contradicción interna, verificada el 2026-11-07; `conflictos-con-la-spec-vieja.md`, fila 1); (4) el estado de la oferta (`fase`) no cambia por esta skill: `validada → escalando` lo mueve el motor.

## 4. Valores `[SUPUESTO]` y quién los firma

| Clave (flat `grupo.clave`) | Valor de prueba | De dónde sale | Existe en `parametros.yaml` | Quién firma |
|---|---|---|---|---|
| `escalado.campeon_compras_min` | 10 | video `[V][DECL]` y `mapeo.md` §12 | no (P-02) | **dueño** (E-05) vía S-A |
| `escalado.campeon_cpa_max_x_be` | "0.40" | `mapeo.md` §3.2 `[HIPÓTESIS]` | no (P-02) | dueño |
| `testeo.p_escala` | "0.80" | D8 | sí (`hipotesis: true`) | dueño |
| `escalado.cpa_3d_factor` | "1.15" | `departamentos/10-escalado.md` §3.4 y `09-optimizacion.md:113` («CPA 3 d ≤ 1,15 ×») | no (P-02): el texto lo trae pero no tiene clave | dueño |
| `escalado.cpa_subir_factor` | "1.0" | `parametros.yaml` | sí | dueño |
| `escalado.compras_min_ventana` | 8 (en 7 días) | `parametros.yaml` | sí | dueño |
| `escalado.suba_presupuesto_gastado_min_pct` | 90 | `brechas/02` E-01 `[HIPÓTESIS nuestra]` | no (P-02) | dueño + S-A |
| `escalado.reduccion_pct` | 30 | video `[P]` («si no rinde, baja 30 %») | no (P-02) | dueño |
| `escalado.revertir_cpa_factor` | "1.5" | `parametros.yaml` | sí | dueño |
| `testeo.k_corte` | 3 | `parametros.yaml` | sí | dueño |

## 5. Cómo se calibra (sin opinión)

Se mide, no se opina: **tasa de campeones** (el video declara 3 de 100; la nuestra sale de los datos), **acierto de la graduación** (¿el campeón sobrevivió como ESCALA a 96 h con CPAm ≤ tope?), **falsos descartes** del día 1 (grupo de control reducido, `decision.reglas.plan_grupo_control`). Cuando haya ≥ el mínimo de casos que fije S-A, el informe semanal propone al dueño recalibrar; **el dueño firma el cambio**, nunca la skill. Hasta entonces el umbral es una hipótesis y se lee así en todo expediente.
