# Escalera, graduación y habilitación por etapas

> Fuentes: `know-how.md` §4-§5 y §9, `mapeo.md` §3.2-§3.3 y §11, `brechas/02` (H-01 a H-05, B2-07 a B2-10, E-06 a E-11), `analisis/testeo-escala-robots.md` §5, `decision/reglas.py:444-499`, `departamentos/10-escalado.md` §3.4. **J1 manda: «su ritmo para todo, con nuestros frenos».** Lo que sigue es cómo se traduce a algo que el sistema pueda sostener hoy.

## 1. Quién hace qué

La **escalera de escala** del sistema de referencia es un **robot de código con horario** (cada 30 minutos): sube ×2, ×3 o ×5 según el retorno del día y baja 30 % si no rinde. **No existe todavía** (B2-10: ni `reducir`, ni el bucle, ni medición horaria `v_venta_hora`). D9 (esta skill, una IA) **no corre en bucle de 30 minutos**: define con código qué paso cabe hoy, redacta la propuesta y el informe, y explica. Cuando el robot exista, D9 le da la política y el robot ejecuta dentro del guard; D9 sigue solo proponiendo.

## 2. Lo que la fuente no dice (no se inventa)

Qué retorno activa ×3 y ×5, el presupuesto base, el techo diario por escala, los números del salvavidas, el paso del guardia nocturno (`know-how.md` §12.1). Lo único escrito: «ROAS ≥ 2,5 → duplicar, remedir a la hora, duplicar otra vez» (regla vieja que su propio auditor mostró que «cumplía parámetros pero no aprendía»), «baja 30 %» y el acierto medido: **3 de 4 bajas aciertan; 1 de 3 subas acierta** («por eso las subas ahora piden más pruebas»). El video remite a tres videos suyos donde casi seguro están los umbrales (H-11, pendiente del dueño).

## 3. Qué exige una suba (todo lo calcula `escala_lectura.py` con el código del motor)

1. **Ganador** `CAMPEON` o `VALIDADA` (`criterio-de-ganador.md`).
2. **Dos señales**: retorno de 7 días (`cpa_7d ≤ cpa_subir_factor × cpa_obj`) **y** tendencia de 3 días (`cpa_3d ≤ cpa_3d_factor × ese umbral`). Una sola → `SENAL_AMBIGUA`, no se sube: es la respuesta al «1 de cada 3».
3. **Compras mínimas** en la ventana (`escalado.compras_min_ventana`) y **datos maduros** (sin los últimos 2 días).
4. **Que Meta haya gastado el presupuesto anterior** (H-01): su robot viejo duplicaba cada hora sin saber si Meta ya había gastado lo anterior; de ahí nació el auditor. `presupuesto_previo_gastado_pct ≥ escalado.suba_presupuesto_gastado_min_pct`.
5. **Ritmo**: horas mínimas desde el último aumento, ≤ 4 cambios por hora y ≥ 30 s entre ediciones (`engine.limites.exigir_ritmo`).
6. **Tope**: máximo teórico (× 1,75) dentro de `gasto_diario_global` y `gasto_diario_por_oferta`, pérdida acumulada de empresa y límite de cuenta (`frenos-y-presupuesto.md`).
7. **Elegibilidad E0**: sin fatiga abierta, sin incidente de D10, sin congelación, riesgo verde, sello de X1 vigente, tracking sano…
8. **Paso** (`decision.reglas.proponer_aumento_presupuesto`): el menor entre el deseado, el múltiplo habilitado, `aumento_presupuesto_max_pct_por_paso` y el techo. **Reducir** −`escalado.reduccion_pct` si el CPA de 72 h ≥ `revertir_cpa_factor × cpa_obj` con gasto ≥ `testeo.k_corte × cpa_be` (con menos gasto es ruido). Reducir no exige E0.

Nunca se mira cada hora para decidir: la lectura horaria es alerta; se decide por día y 72-96 h (a 5 US$/día un conjunto produce ~0,1 compras en 3 horas: la señal es ruido; `analisis` §3).

## 4. Habilitación por etapas (según el acierto medido por el auditor)

El sistema de referencia mide que solo 1 de 3 subas acierta. Si la nuestra midiera algo parecido, una regla que sube cada 30 minutos sería peor que una moneda con sesgo. Por eso los saltos mayores **no se habilitan por optimismo sino por acierto medido**, y se bajan solos si el acierto cae.

| Etapa | Qué habilita | Condición de entrada (la verifica código; la firma el dueño) | Estado |
|---|---|---|---|
| **0 · hoy** | solo **proponer**: suba hasta ×2 (si el dueño fija `aumento_presupuesto_max_pct_por_paso` ≤ 100) y reducción −30 %. Ejecuta el dueño (gate H) | defecto. Sin robot y sin auditor | vigente |
| **1** | **×2** ejecutado por el robot de escalera en N3 | ≥ 15 pasos supervisados en ≥ 2 ofertas, ≥ 80 % «buenos», 0 violaciones de tope, sonda de guardarraíles 100 % `deny` (`departamentos/10-escalado.md` §7, N2→N3) | `[PENDIENTE]` robot, auditor y J2 aplicados |
| **2** | **×3** | etapa 1 sostenida; acierto de las subas de la etapa 1 ≥ `auditor.acierto_min` en ≥ N decisiones y ≥ 2 ofertas; **esquema cambiado** (hoy el % es ≤ 100 y `LimitesMeta` lo rechaza: P-01, P-11) | `[PENDIENTE]` |
| **3** | **×5** | ídem sobre la etapa 2 | `[PENDIENTE]` |
| descenso | baja una etapa | el acierto de las subas cae bajo el mínimo, una violación de tope, 2 pasos malos seguidos o `rechazos_7d ≥ compliance.rechazos_congelar` (el nivel baja a N1) | mecanismo de descenso de nivel existente en `autonomia.yaml`; sin código que lo aplique (B2-25) |

`[SUPUESTO]` de la propuesta de S-C, sin firmar: `auditor.acierto_min` 0,5 para cortes y **0,6 para subas** (`analisis` §1b y E-11) y ventana de juicio de 72 h para cortes y 96 h para subas con CPA marginal (no las 3 horas del video). Cuántas decisiones forman «N» y cuántas ofertas: los fija S-A con el dueño (P-02). El **acierto** de una suba es el `veredicto_paso` «bueno» a 96 h (CPAm ≤ `cpam_max_factor × cpa_be` y CPA de 72 h ≤ `cpa_max`; `departamentos/10-escalado.md` §3.4); el de una baja, que la oferta no se deteriore a 72 h. Los mide el **auditor** (código, en sombra primero; B2-24), no esta skill; el informe semanal solo los transcribe.

`escalado.escalera_multiplo_max` (2, 3 o 5) es el parámetro que expresa la etapa vigente; cambiarlo es una firma del dueño. Mientras no exista en `parametros.yaml`, el dictamen se detiene (5).

## 5. Graduación: del test a la ESCALA

- **Qué es graduar**: crear una campaña **ESCALA nueva** con los campeones (CBO; el sistema de referencia usa tope de costo, ver §6) y dejar **el original vivo en test** (regla de oro 2: si se lo saca, se pierde la señal). El test no se edita por dentro ni se escala ahí («la campaña de testeo no es necesario escalarla», H-09): la plata grande va solo a la escala.
- **Cuántos entran**: «los 10 mejores» (`escalado.top_en_escala`, propuesta, P-02), ordenados por P(CPA ≤ `cpa_obj`); **de una vez** en un solo conjunto, porque agregar anuncios a un conjunto que aprende reinicia el aprendizaje (HC-3). Los relevos posteriores = otra ESCALA o prueba de creativos por API (`[VERIFICAR]` con Advantage+), jamás un anuncio extra en el conjunto vivo.
- **Cuánto presupuesto**: la ESCALA nueva cuenta como **un paso sobre el agregado** de la oferta: su presupuesto inicial ≤ agregado × el paso permitido, ≤ múltiplo habilitado, ≤ techo. Lo calcula el código (`GRADUACION_PERMITIDA`).
- **Cuántas**: `escalado.max_campanas_escala` (hoy 2; el análisis recomienda 1 al inicio para calzar «1 testeo + 1 escala por mercado»).
- **Nombre y estado**: `OF-AAAAMM-NN_ESCALA_VENTAS_ADV-PLUS_AAAAMMDD` (convención de D7); nace en `PAUSED`, pasa el preflight de D7 y el sello de X1; activarla es código (J2) o el dueño (hoy).
- **Reglas de oro en la escala**: (1) no se apagan conjuntos ni anuncios por dentro: se sube o baja el presupuesto; D8 conserva G (cuenta) y la pausa por rechazo de Meta porque protegen la cuenta, no el rendimiento; la regla K (matar anuncios) en escala es decisión abierta (`conflictos-con-la-spec-vieja.md`, fila 7); (3) tendencia de 3 días; (4) ganancia antes que volumen; (5) todo robot se audita; (6) relevo **antes** del cansancio: el reemplazo se pide cuando la señal de fatiga aparece (alarma de cansancio: 3 días contra los 7 anteriores, **solo sobre la escala**, H-06), no cuando ya cayó.

## 6. Tope de costo (cost cap)

El sistema de referencia usa CBO **con tope de costo** y un robot nocturno que lo ajusta de a poco. Nuestro contrato no lo permite: `meta/payloads.py:215` fija `LOWEST_COST_WITHOUT_CAP` y `campana.schema` no tiene `estrategia_puja` ni `cost_cap` (P-05). Mientras tanto la ESCALA se propone **sin freno nativo de CPA** y la propuesta lo dice en `no_ejecutable_hasta`. Valor del tope (cuando exista el contrato): `[SUPUESTO]` 1,0-1,3 × CPA medio de 7 días de los creadores (nivel C, no el de él, que no se muestra) y **nunca por encima de `cpa_be`**; no es un número de esta skill.

## 7. Lo que no está en v0.1

**Salvavidas** (suma lo vendido del día al presupuesto: es «surfing» sobre ingreso bruto y sin respaldo; solo en N3 y sobre neto con fracción < 1, B2-19), **guardia nocturno** (depende del tope de costo, B2-20), **cola de testeo** y **perfil por idioma** (robots de D8/D7), **tope diario aprendido por prueba** (H-02) y **hora pico** como dimensión (H-03). Se listan en el informe como pendientes; no se simulan.

## 8. Calendario

Black Friday 2026-11-27 y Cyber Monday 2026-11-30 `[VERIFICAR]` (`departamentos/10-escalado.md` Anexo A): el CPM sube; **CPM +35 % con compras estables no es saturación**. Toda propuesta en esa ventana lo declara en el expediente; el CPA se compara con el mismo período o se congela el paso vertical.
