# Fatiga y relevo: alarma de cansancio, relevo antes de que caiga y banco de suplentes

> v0.1 sin pulir (skill 0.1.0). Fuentes: JPS (`know-how.md` §5 y §9, brechas A.3 y A.4: robot «Alarma de cansancio» 08:05 y regla de oro 6), spec vieja (`departamentos/09-optimizacion.md:112`, regla FT) y parámetros de `empresa/parametros.yaml`. Implementación de referencia en sombra: `scripts/proponer.py fatiga` (las reglas FT del motor no existen: B2-12). Todo umbral sale de `decisiones-y-umbrales.md` §D.

## 1. Qué dice JPS (y cuánto se sabe)

- **Alarma de cansancio** `[P]`: corre a las **08:05**, compara los **últimos 3 días contra los 7 anteriores** y **«pide relevo a la fábrica»**; por voz `[V 40:00]`: «me avisa para que lo pueda reemplazar» (no queda claro si el relevo es automático). **El umbral de «cansado» no se dice** `[?]`.
- **Alcance** `[V 40:00]`: los creativos de la campaña de **escala**.
- **Regla de oro 6** `[P 43:58]`: «relevo antes del cansancio»; el reemplazo se produce **antes** de que el ganador caiga; por eso se testea todos los días, para tener un creativo en el **banco de suplentes** `[V 45:00]`.
- **Regla de oro 2** `[P]`: «el ganador sigue en testeo»; si se lo saca, «se pierde la señal».
- **Tipos de relevo** `[DECL]`: «relevo con otra apertura» (mismo anuncio, otro gancho) rinde 1,39 por dólar según su tablero; esa cifra **no** se usa como prior (no dice si es ingreso o beneficio, `mapeo.md` §6).

## 2. Alarma de cansancio: 3 d contra 7 d (lo que hace el script)

Dos formas de mirar «7 días» conviven en las fuentes y **no son lo mismo**:

| | JPS `[P]` | Spec vieja (`09-optimizacion.md:45` y `:112`) |
|---|---|---|
| Con qué se compara | últimos **3 días** contra los **7 días anteriores** (ventana móvil) | CTR y CPA de **3 días** contra el CTR/CPA **inicial** del anuncio; frecuencia a **7 días** |
| Umbral de «cansado» | no lo da `[?]` | caída de CTR ≥ 30 %, CPA ≥ 1,5 ×, frecuencia ≥ 2,5, ≥ 2 de 3 señales en 2 lecturas seguidas (`HIP`) |

**Lo que adopta la skill:** la ventana móvil de JPS (3 recientes contra 7 previos, sin depender de un «valor inicial» que se vuelve viejo) con los **umbrales de la spec vieja** (`HIP`, a calibrar). Es decisión nuestra y está marcada `[SUPUESTO]` hasta que el dueño la firme (`decisiones-y-umbrales.md` U-40 a U-48).

Algoritmo (por anuncio, enteros y fracciones exactas, sin `float`):

1. **Lectura k** = ventana que termina `k` días antes de la fecha evaluada: **recientes** = 3 días, **previos** = los 7 anteriores. Hacen falta `3 + 7 + (lecturas − 1)` días de serie (con 2 lecturas, 11); `preparar_expediente.py` entrega 14 por defecto.
2. **Señal CTR de enlace** (clics de enlace / impresiones): evaluable si ambas ventanas tienen ≥ 3.000 impresiones y hubo clics previos. Fatiga si `CTR_reciente ≤ (1 − 30 %) × CTR_previo` (el 30 % exacto cuenta).
3. **Señal costo por venta** (gasto / ventas de Stripe del `adid`): evaluable si los 7 días previos tienen ≥ 3 ventas y, o bien los recientes también tienen ≥ 3, o bien el gasto reciente ≥ 3 × el CPA previo (así un colapso a cero ventas **sí** se detecta: sin ventas con gasto suficiente es fatiga). Fatiga si `CPA_reciente ≥ 1,5 × CPA_previo`. Sin ventas suficientes, **costo por inicio de pago** como sustituto.
4. **Señal frecuencia 7 d** (opcional): solo la lectura más reciente y solo si la entrada trae `frecuencia_7d` (hoy la base no la guarda; el Maker **no la escribe a mano**).
5. **Lectura con alerta** = al menos 2 señales verdaderas entre las evaluables, y deben ser evaluables al menos 2. **Confirmada** = alerta en las 2 lecturas seguidas.
6. **Aplicabilidad:** solo para anuncios con ≥ 3 ventas en la ventana previa (había un «ganador» que relevar). Los demás: `NO_APLICA`, y los juzgan las reglas de baja y del motor.

Resultado por anuncio: `FATIGA_CONFIRMADA` · `FATIGA_UNA_LECTURA` · `SIN_FATIGA` · `NO_APLICA` · `DATOS_INSUFICIENTES`. Con solo CTR y costo por venta evaluables (hoy), **ambas** deben caer: es más conservador que «2 de 3» con frecuencia; dejará pasar fatigas puras de frecuencia hasta que exista el dato.

## 3. Qué se propone

| Estado | Propuesta | Qué incluye |
|---|---|---|
| `FATIGA_CONFIRMADA` y hay cupo de pedido | **RELEVAR** (`FATIGA_RELEVO_PEDIDO`) | pedido a D6 (abajo) |
| `FATIGA_CONFIRMADA` sin cupo (pedidos abiertos ≥ `max_pedidos_abiertos`, o desconocidos) | AVISAR_FATIGA (`FATIGA_SIN_CUPO_DE_PEDIDO`) | aviso al dueño |
| `FATIGA_UNA_LECTURA` | AVISAR_FATIGA (`FATIGA_SIN_CONFIRMAR`) | pre-aviso; se vuelve a leer mañana |
| `SIN_FATIGA`, `NO_APLICA`, `DATOS_INSUFICIENTES` | nada (la nota va al expediente) | — |

### El pedido de relevo a D6 (forma de `departamentos/09-optimizacion.md` §3.3)

`pedido_id` · `motivo: fatiga` · `ad_origen` · `metricas[]` (cifras copiadas con su `fuente`) · **`variable_a_variar`: una sola** (por defecto el **gancho**, que es el «relevo con otra apertura» de JPS) · `cantidad` ≤ `cantidad_max_pedido` (5) · `plazo_h` · `mecanismo_lanzamiento` (`tanda_diaria_cbo`) · `angulo_id` tomado de `oferta.angulos[]` **permitido al nivel de riesgo** · `aprendizaje{hook_id, hipotesis_id, resultado}` · `no_repetir[]` (el gancho que cayó y **todo claim** del ganador). Nunca se transmite el texto del ganador ni claims de salud, ingresos o resultado; solo estructura y variable. Sin testimonios, cifras de alumnos ni urgencias inventadas (J8). El pedido pasa por D6, X1 y el sello como cualquier pieza.

## 4. Relevo antes de que caiga (regla de oro 6)

- El **pre-aviso** (`FATIGA_UNA_LECTURA`) es la forma de «avisar antes». El pedido (`RELEVAR`) sale con la segunda lectura. No se espera a que el CPA supere el equilibrio.
- **El anuncio vivo no se toca** y **no se pausa por fatiga** mientras venda: reglas de oro 1 y 2 de JPS. Choca con la spec vieja (`09-optimizacion.md:112`: «el viejo se pausa solo cuando el reemplazo entrega y su CPA 7 d ≥ 2·`cpa_obj`»). Hasta que S-A decida (`PEDIDOS.md` P-09), esta skill **no propone pausar** el anuncio fatigado; sus bajas siguen las reglas K del motor.
- **El relevo entra como anuncio nuevo** en la tanda siguiente, nunca dentro del conjunto que aprende (editar un conjunto con aprendizaje lo reinicia: `docs/08` §4.6, HC-3), y nunca como una edición del anuncio original (los creativos son inmutables).
- Antes de culpar al creativo, se descartan las etapas **0** (entrega), **2** (conexión) y **4** (pago) del árbol de embudo con las cifras del día (`09-optimizacion.md:116-126`): un CPA que sube porque el checkout falló no se arregla con un gancho nuevo.

## 5. Banco de suplentes

- **Qué es en JPS:** creativos ya probados (o listos) en espera, para reemplazar sin quedarse sin nada. **Qué hay hoy:** solo `creativos.reserva_conceptos` = 2 (`parametros.yaml:861`: conceptos con guion y copy, **sin assets**); no existe `banco_creativos` ni etiqueta «ganador» (B2-07).
- **Qué hace D8:** informa si hay suplentes disponibles (lo que D6 declare en su paquete) y lo pone en el pedido; **no** construye ni mantiene el banco. Un suplente sin sello vigente de X1 no cuenta como disponible.
- **Pedido:** S-B `scripts/banco_creativos.py` (registro sin Meta) y S-A el contrato; mientras tanto el expediente dice «banco: no medible».

## 6. Lo que falta (y a quién se pide)

| Falta | Dueño | Referencia |
|---|---|---|
| frecuencia a 7 días en la base (`reach` y `frequency` no son aditivos: se piden a Meta con el rango) | S-B (ETL) | U-44, B2-12 |
| la alarma oficial en `engine/d8.py` (FT) y el consumo de `testeo.fatiga_*` | S-B | B2-12, B2-18 |
| `fatiga_ventana_*`, `fatiga_lecturas_seguidas`, `fatiga_compras_min` en `parametros.yaml` | S-A | U-40, U-45, U-46 |
| umbral de «cansado» real (JPS no lo da; sus 3 videos remitidos probablemente sí) | dueño (B2-33) | `[NO VERIFICADO]` |
| decisión sobre pausar o no el fatigado | S-A | P-09 |
| que el relevo sea automático (JPS no aclara) | dueño | J2 |

## 7. Ejemplo (eval D03)

Un anuncio ganador (20 clics por mil y 2 ventas por día) cae a 10 clics por mil y 1 venta por día. Lectura del 2026-11-20: CTR 1,00 % contra 1,85 % (-46 %) y costo por venta 1.000 contra 538 (×1,86); lectura del 19: -50 % y ×2,00. Dos lecturas seguidas ⇒ `FATIGA_CONFIRMADA` ⇒ `RELEVAR` con pedido de 1 variable (gancho), máximo 5 piezas, sin pausar el original (`evals/dorados/D03.json`).
