# Protocolo J3: baja de lanzamiento a 1 día y su excepción de presupuesto no gastado

> v0.1 sin pulir (skill 0.1.0). Fuente: `docs/_historial/mentor-sistema/decisiones-del-dueno.md` (J1, J3, J4), `mapeo.md` §3.1, informe de brechas `02-jurado-testeo-robots.md` (B2-01, B2-02, B2-14, E-01 a E-04). Etiquetas: `[J3]` decisión del dueño · `[SUPUESTO]` valor o definición nuestra, sin firma · `[cálculo nuestro]` aritmética reproducible · `[HIPÓTESIS]` valor inicial a calibrar. La implementación de referencia es `scripts/proponer.py lanzamiento` (en sombra); la oficial será de S-B (`PEDIDOS.md` P-04).

## 1. Qué decidió el dueño (palabras suyas)

- **J1:** «el recomendado, pero tener en cuenta que una oferta se testea la oferta y los anuncios en el lanzamiento, porque un testeo es necesario oferta, landing y anuncios». El lanzamiento prueba el **paquete completo** a la vez.
- **J3:** lanzar landing + oferta + **«una campaña CBO con ~10 creativos a 50-100 USD»**; «se deja un día, si el primer día no vendió, se da de baja; **no se deja correr hasta un umbral de plata**, y así se sigue y se sigue todos los días». Elegido: **1 día sin venta → baja**.
- **Salvaguarda que se agrega a J3:** solo cuenta si la campaña **gastó su presupuesto del día** (si Meta no entregó, no es culpa de la oferta).
- **Sin tope de pérdida por oferta:** la pérdida por oferta queda acotada por la propia regla (~1 día de gasto).
- **J4:** los frenos son de empresa: techo de **300 USD/día** y **pausa automática a -3.000 USD** de pérdida acumulada.
- Nota del propio J3: el video usa 3 días para los anuncios dentro del testeo continuo y su regla de oro 3 dice «un día sin ventas no dice nada». El dueño eligió **1 día para el lanzamiento**. Esta skill separa los dos: LANZAMIENTO (1 día, esta regla) y CONTINUO (tendencia de 3 días).

## 2. El paquete que se juzga

1 campaña CBO · ~10 creativos · 50-100 USD/día (arranque 75 `[HIPÓTESIS]` del mapeo) · landing y oferta reales. Se juzga **el paquete**, no un creativo suelto: un cero de ventas puede venir de la oferta, la landing, el precio, el checkout o los anuncios, y el día 1 **no distingue** entre ellos (por eso la baja se anota con hipótesis, no con causa).

Choques con lo construido (D7 y el motor siguen en el protocolo anterior; detalle en `conflictos-con-la-spec-vieja.md` y `PEDIDOS.md`): `campana.n_anuncios_tope` = 6 (`empresa/parametros.yaml:917`), `meta/payloads.py` baja `n_anuncios` por `k_corte × cpa_max`, D7 arma `CBO_1AS` de 3-6 anuncios y `dias_test_defecto` 10 (`:932`).

## 3. Definiciones operativas (propuestas; cada una espera su firma, ver `decisiones-y-umbrales.md`)

| Término | Definición usada por el script | Estado |
|---|---|---|
| **Día** | día calendario en la zona horaria de la cuenta de Meta (`fact_meta_ad_dia.tz`); el día **evaluado** debe estar cerrado y haber pasado `lanzamiento.espera_post_dia_h` (9 h) desde su cierre | `[SUPUESTO]` E-02; hay una sola cuenta de Meta y una zona |
| **Primer día** | primer día de cuenta con gasto > 0. Si es parcial (se activó a media jornada) casi nunca llega al 90 % del presupuesto y la salvaguarda lo deja pasar sin contarlo | `[SUPUESTO]` |
| **Venta** | pedido **pagado** de la oferta en Stripe (`fact_pedido.estado` = `paid`), no de prueba (`es_prueba`) ni interno (`es_interna`), **atribuido o no** al anuncio (`adid`). Un pedido sin `adid` también cuenta como venta de la oferta: apagar una oferta que vendió es el error caro | `[SUPUESTO]` E-03 |
| **Reembolso el mismo día** | no se descuenta en el día 1 (se informa en `ventas_con_reembolso`); el neto lo mira el cierre | `[SUPUESTO]` E-03 |
| **Pago pendiente** | pedido en `unpaid`/`pending` (pago asíncrono): no es venta todavía, pero impide la baja hasta que se resuelva | `[SUPUESTO]` |
| **Presupuesto del día gastado** | gasto del día ≥ `gasto_cumplido_min_pct` % (90) del presupuesto diario de `campana.json`. «≥», no «=»: Meta puede gastar hasta 1,75 × el diario | `[SUPUESTO]` E-01 |
| **Medición sana** | PAUSA ausente, infraestructura VERDE, lectura de Meta de menos de 6 h y posterior al cierre del día, una sola moneda, eventos de landing disponibles y, con ≥ 100 clics, vistas de landing ≥ 70 % de los clics | umbrales de la spec vieja (`HIP`) |
| **Objeto de la baja** | la campaña de lanzamiento completa (propuesta `objeto_tipo: oferta`, como las celdas `oferta_mercado` del motor), no un anuncio | `[SUPUESTO]` |

## 4. Tabla de verdad (manda la primera fila que se cumple)

Es el orden de `evaluar_lanzamiento`. `A` = APAGAR, `M` = MANTENER, `N` = NO_DECIDIR, `P` = PAUSAR_Y_ESCALAR.

| # | Condición (con datos de `entrada.json`) | Propuesta | Código | Escala a |
|---|---|---|---|---|
| 0 | falta algún umbral de la regla, o `baja_requiere_presupuesto_gastado` ≠ true, o `baja_dias` < 1 | N | `UMBRAL_FALTANTE` / `UMBRAL_INCOHERENTE_J3` | dueño |
| 1 | no se sabe si hay PAUSA o cómo está la infra (sin `--raiz`, sin `estado.json`) | N | `CONTEXTO_DESCONOCIDO` | dueño |
| 2 | existe `empresa/PAUSA` | N | `PAUSA_ACTIVA` | dueño |
| 3 | infraestructura ≠ VERDE | N | `INFRA_NO_VERDE` | D5 |
| 4 | sin presupuesto diario legible | N | `SIN_PRESUPUESTO` | D7 |
| 5 | gasto de Meta y presupuesto en monedas distintas | N | `MONEDA_INCOHERENTE` | D7 |
| 6 | nunca se ingirió Meta / la última lectura tiene más de 6 h | N | `SIN_INGESTA_META` / `DATOS_OBSOLETOS` | D7 |
| 7 | todavía no hay gasto | M | `SIN_GASTO_AUN` | — |
| 8 | el día evaluado no cerró / no pasó la espera de compras tardías | M | `DIA_NO_CERRADO` / `ESPERA_COMPRAS_TARDIAS` | — |
| 9 | la lectura de Meta del día es anterior a su cierre | N | `DIA_INCOMPLETO` | D7 |
| 10 | **hay ≥ 1 venta** desde el primer gasto | M | `LANZAMIENTO_CON_VENTA` (o `VENTA_SIN_ATRIBUCION` si ninguna trae `adid`, con aviso a D5) | — / D5 |
| 11 | hay pagos asíncronos pendientes | M | `PENDIENTES_ASINCRONOS` | — |
| 12 | menos de `baja_dias` días cerrados | M | `DIAS_INSUFICIENTES` | — |
| 13 | **salvaguarda J3:** en alguno de los últimos `baja_dias` días el gasto fue < 90 % del presupuesto | M, o P si ya van `dias_max_sin_entrega` (2) días seguidos sin entrega | `ENTREGA_INCOMPLETA` / `ENTREGA_INSUFICIENTE_PERSISTENTE` | D7 (en P) |
| 14 | sin eventos de landing para verificar la conexión | N | `SIN_EVENTOS_LANDING` | D5 |
| 15 | con ≥ 100 clics, vistas de landing < 70 % de los clics | N | `ETAPA_2_CONEXION_BAJA` | D5 |
| 16 | **0 ventas, sin pendientes, presupuesto del día gastado, medición sana** | **A** | **`LANZAMIENTO_SIN_VENTA_J3`** | — |

Garantía probada (`tests/skills_d8/test_proponer.py`): **con una sola venta pagada desde el primer gasto, el script nunca propone APAGAR**, para cualquier gasto.

Qué es y qué no es cada fila 14-15: son extensiones **nuestras** a J3 (el dueño no las dijo), del mismo espíritu que su salvaguarda: «si no es culpa de la oferta, no se baja». Solo pueden convertir una baja en «no decidir y revisar»; nunca crean una baja. Si el dueño las quiere fuera, se quitan sin tocar el resto.

## 5. La excepción: presupuesto del día no gastado

- **Por qué existe:** el 0 de ventas con 20 USD gastados de 75 no dice nada de la oferta; dice que Meta no entregó (aprendizaje, puja, audiencia, límite de la cuenta, rechazos, pago). Sin esta fila, una falla de entrega se castigaría como si fuera mala la oferta.
- **Umbral:** 90 % `[SUPUESTO]` (punto de partida del informe de brechas, E-01). No se confunde con el 50 % de la etapa 0 del árbol de embudo (`departamentos/09-optimizacion.md:120`, «gasto < 50 % del presupuesto»), que diagnostica una falla de entrega; son dos usos distintos y S-A debe darles nombres distintos (`PEDIDOS.md`).
- **Qué se hace cuando no gastó:** `MANTENER` con `ENTREGA_INCOMPLETA`, diagnóstico de etapa 0 con responsable D7 (puja, audiencia, límite diario, rechazos, pago de la cuenta), **sin tocar creativos ni la oferta y sin editar la campaña viva para forzar gasto**.
- **Cuánto se espera:** `lanzamiento.dias_max_sin_entrega` = 2 `[SUPUESTO]`. Al segundo día seguido sin gastar ≥ 90 % el script devuelve `PAUSAR_Y_ESCALAR` (`ENTREGA_INSUFICIENTE_PERSISTENTE`, responsable D7): una campaña que no entrega no se deja abierta indefinidamente esperando.
- **Dónde empieza la cuenta:** en el primer día con gasto, así el día parcial de activación no cuenta como entrega cumplida ni como día perdido.

## 6. Qué se anota al apagar («se apaga y se anota por qué»)

En `por_que_se_apaga` del expediente: etapa del embudo alcanzada (clics → vistas → inicios de pago, con las cifras de `entrada.json`), hipótesis (precio, promesa, checkout, creativos) marcadas `[HIPÓTESIS]`, `nivel_evidencia: bajo`, y qué variable cambiar en el próximo lanzamiento. No se dice «la oferta es mala»: un día de datos no lo prueba (`estadistica-honesta.md`).

## 7. Después de la baja

- **Quién pausa:** el código (ejecutor del motor / `meta.pausar`) o el dueño. Hoy el gate es H.
- **Estado de la oferta:** `docs/06-bases-del-testeo.md` §5 dice que `MATAR` sobre una celda `oferta_mercado` lleva la oferta a `fase: fallida` (el código de `engine/d8.py:278-280` hoy solo llama a `ejecutor.pausar`), y salir de `fallida` exige `accion:reabrir_fallida` (H). Si se aplica tal cual, frenaría el relanzamiento diario de J3. **Pedido abierto a S-A/S-B** (`PEDIDOS.md` P-08): una causa o estado propio de «baja de lanzamiento» que no obligue a una firma por cada variante.
- **El siguiente lanzamiento** no lo decide D8: lo arma la cola de testeo / O0 con el sello de X1 y los frenos (J2, J4). D8 aporta lo aprendido al informe de cierre.
- **Control de falsos descartes** (opcional): reabrir una fracción de lo apagado para medir cuántas bajas habrían vendido; cuesta dinero (`estadistica-honesta.md` §5). Solo si el dueño lo activa.

## 8. Casos borde

| Caso | Qué hace el script |
|---|---|
| Compra tardía del día 1 llega a las 6 a. m. | por eso la espera de 9 h tras el cierre; una compra posterior a la evaluación se ve al día siguiente (la oferta ya estaría apagada: es el falso descarte que el control mide) |
| Pedido con `adid` «desconocido» o de otro anuncio | cuenta como venta de la oferta; sin atribución → `VENTA_SIN_ATRIBUCION` y aviso a D5 |
| Pedido de prueba o interno | no cuenta |
| Pago asíncrono sin resolver | `PENDIENTES_ASINCRONOS`: no se baja |
| Gasto > 100 % del presupuesto | cuenta como cumplido (Meta puede llegar a 1,75 ×); el techo lo vigila el guard |
| Webhook de Stripe caído | **el script no puede probarlo** con cero pedidos; lo cubre `infra_semaforo` (VERDE) y el vigía de pagos. Limitación documentada (`bugs-conocidos.md` L-03) |
| Banner de consentimiento (UE/UK) baja las vistas de landing | puede disparar `ETAPA_2_CONEXION_BAJA`: cae del lado seguro (no baja); lo revisa D5 |
| Cambio de horario (día de 23 o 25 h) | `zoneinfo` calcula el cierre local real |
| Moneda del cobro distinta a la del gasto | la regla solo cuenta pedidos y compara gasto contra presupuesto (ambos en la moneda de Meta): no necesita tipo de cambio |
| Reembolso el mismo día | se informa, no se descuenta |

## 9. Lo que J3 deja sin definir (preguntas al dueño)

1. ¿90 % es el umbral de «gastó su presupuesto del día»? (E-01)
2. ¿Qué es «venta» y qué es «día»? (E-02, E-03; las definiciones de arriba son nuestras)
3. ¿Cuántos días de entrega incompleta se toleran antes de pausar? (2 es nuestro)
4. ¿Qué pasa con la oferta apagada: se puede relanzar otra variante sin firma?
5. ¿Qué regla rige los días ≥ 2 de una oferta que sí vendió? J3 no lo dice; el video dice «¿vende en 3 días?» y regla de oro 3. Hasta que se firme, CONTINUO usa las decisiones del motor y no propone apagar por un día suelto (`decisiones-y-umbrales.md` U-30 a U-33).
6. Consumo de los frenos: con J4 (300 USD/día) y un CBO de 75 USD, el **máximo teórico** es 75 × 1,75 = 131,25 USD y el guard suma **máximos teóricos** (`engine/limites.py:268-290`, `docs/06-bases-del-testeo.md:181`): caben **2** lanzamientos simultáneos (3 con 50 USD, 1 con 100), no 4 como sugiere dividir 300 por 75 `[cálculo nuestro]`. Y -3.000 USD alcanzan para ~40 bajas de 75 USD (30 de 100) si ninguna oferta compensara `[cálculo nuestro]`.
