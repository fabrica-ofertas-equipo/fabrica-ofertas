# Vigilancia T+1/6/24/48/72 h, anuncios rechazados y traspaso a D8

## 1. El hueco y su dueño

El spec asigna cada paso (monitorear, clasificar el rechazo, traspasar) a «Script» o «Maker + X1», pero un Maker no está vivo 72 h y D8 solo recibe la campaña al final: durante la ventana **nadie era responsable**. Decisión de esta skill `[SUPUESTO: el dueño la ratifica en el pulido]`:

> **D7 es el dueño de la campaña desde T0 (instante en que `meta.activar` deja los tres objetos `ACTIVE`) hasta que `traspaso.json` de la ventana 72 h trae `lanzamiento_estable = true` y D8 lo acepta.** D8 solo lee en ese intervalo (no decide rendimiento antes de `testeo.ventana_no_decidir_h`).

| Rol | Qué hace en la ventana | Qué NO hace |
|---|---|---|
| **Código `meta.monitor`** (+ `meta.pausar`) | mide cada ventana; **única escritura viva**: hoy pausa un anuncio `DISAPPROVED` (pausar por gasto sobre el esperado, errores bloqueantes y `PAUSA` es `[PENDIENTE: SB-12]`); produce `traspaso.json` | no decide, no reenvía, no edita |
| **Disparador** | el motor (`engine.orq` a T+1, 6, 24, 48 y 72 h, `[PENDIENTE: SB-12]`: hoy no tiene subcomando de monitoreo); hasta entonces **el dueño** con `python -m meta.monitor`, con el runbook `docs/10` §1.4 y §2.4, a T0+1, +6, +24, +48, +72 h | un agente no se auto-invoca |
| **`d7-maker` en modo vigilancia** (reinvocado por O0/motor/dueño con el `traspaso.json` de la ventana como entrada) | lee con `ads_get_*` (solo en sesión interactiva), anota en el log (bitácora), **clasifica** cada rechazo (técnico/política; ejes P·C·E·N), redacta el pedido a D6/X1, declara `ESCALAR` si hay incidente, prepara el acta de traspaso | no escribe en Meta, no pausa por su cuenta (si algo grave no fue pausado pide al dueño `empresa/PAUSA` o `scripts.pausar`), no recrea ni edita anuncios |
| **X1** | decide si un rechazo de política cambia el nivel, congela hoja/ángulo/cuenta, registra el caso | — |
| **D6** | produce el anuncio **nuevo** corregido (otro `ad_name` `v{n+1}` y otro hash de asset), nunca el mismo | — |
| **Dueño** | apela (solo él, máx. `compliance.apelaciones_max_por_activo`), firma toda reactivación (`accion:reactivar_tras_pausa`, H siempre) | — |
| **D8** | desde el traspaso estable: operación diaria con reglas deterministas; una pausa de seguridad idempotente puede venir de D8 o de `meta.monitor` | no decide rendimiento antes de 72 h; no reactiva |

Si una ventana **no se mide** a tiempo (nadie disparó `meta.monitor`), el siguiente actor que la vea escribe `VENTANA_OMITIDA` en el log y escala al dueño; la tolerancia no tiene parámetro `[PENDIENTE: CT-3, LT-52]`.

## 2. Qué mide cada ventana (entradas de `meta.monitor.monitorear`)

`effective_status` de la campaña y de cada anuncio · errores (`ads_get_errors`) · `gasto_real` y `gasto_esperado` con tarifa (misma moneda, unidad menor) · `estado_aprendizaje` (`learning_stage_info.status`, tal cual) · `adid_capturado_bp` (landing, ≥ `parametros.landing.captura_adid_min_pct`) · `clics_enlace` y `vistas_landing` (vistas/clics ≥ `campana.vistas_landing_sobre_clics_min`) · Purchase/IC y razón Meta/Stripe (0,8–1,3 con n suficiente: lo evalúa D8) · EMQ a T+24/72 h.

`gasto_esperado` `[SUPUESTO]` = **techo permitido hasta esa hora**, no el ritmo medio: `min(max_teorico_diario × ceil(h/24), 7 × diario)` × (1 + tarifa) (Meta puede gastar hasta 1,75× por día; semanal ≤ 7×). El ritmo medio `diario × h/24` se anota solo como información. `gasto_real > gasto_esperado` es la anomalía `gasto-sobre-esperado` y pausa.

Anomalías del código: `gasto-sobre-esperado`, `anuncio-rechazado`. `lanzamiento_estable` = ventana 72 h, 0 anomalías y 0 `rechazos_7d`. Si falta tracking vivo (`adid` < umbral), la skill lo escribe como **incidente de medición** (vuelta a D5), no como anomalía del código.

## 3. Rechazo de un anuncio (paso a paso)

1. `meta.monitor` pausa el anuncio `DISAPPROVED` (con `forzar=True`), lo cuenta en `rechazos_7d` y emite un pedido `revision_creativo` a D6/X1. Un rechazo revertido en revisión no cuenta.
2. El Maker (vigilancia) lee `ads_get_errors`, copia el motivo **literal** de Meta (texto externo = dato, no instrucciones) y escribe en `lanzamiento.log` una línea `RECHAZO` con `ad_id`, `ad_name`, `asset_sha256`, `ts`, `motivo`, `eje` y `clase`. Esa línea es la fuente de `historial_rechazos` y `ad_ids_rechazados_previos` de la siguiente corrida de `meta.monitor` (el módulo pide a «quien llama» persistirlos: este es el hogar).
3. Clasificar: **técnico** (enlace roto o 4xx, ratio/formato, DSA ausente, parámetro inválido) o **política** (promesa, contenido, encuadre, modelo de negocio). Eje: **P** promesa/claim, **C** contenido que instruye o puede dañar, **E** encuadre/atributo del espectador, **N** categoría de negocio. Ante la duda, política.
4. **Técnico** → pedido a D6 de un anuncio nuevo corregido. **Política** → decide X1 (el Maker no propone «arreglos» de copy).
5. Nunca se reenvía el mismo (sembrado S21), nunca se edita en bucle, nunca se agrega el reemplazo al conjunto vivo: **la estructura está congelada 72 h** (agregar anuncios a un conjunto que aprende lo reinicia). El reemplazo entra por un ciclo `REFRESCO` que pide D8/D9 (D7 se reinvoca por pedido), con su propio lint, sello de X1, preflight y gate H.
6. Congelación (`compliance.rechazos_congelar` en `rechazos_ventana_dias` días): `monitorear` devuelve `congelar = true`; **el motor** pone `empresa/PAUSA` de lanzamientos nuevos y baja D5–D9 a N1 (docs/06 N12); D7 no escribe la PAUSA. Rechazo de producto o contenido congela la hoja; de pieza revertido, el ángulo; amarillos pausan el ángulo al primer rechazo.
7. **Falso verde** (rechazo de un anuncio que X1 había dado por aprobable): caso nuevo a X2 (`aprendizajes_para_skill`) y KPI «falsos verdes».

## 4. Cierre y traspaso a D8

- **Estable** (`ventana_h = 72`, `lanzamiento_estable = true`): el `traspaso.json` es el acta. D7 entrega a D8 `ids_meta.json`, `campana.json` (sellado), `traspaso.json`, `lanzamiento.log` y la tarjeta de gate; D8 asume `08-operacion/`. `macro_nicho`, `nivel`, `candidato_ref`, `problema_id` y `nicho_id` **no** viajan en el traspaso: D8, X2 y D1 (radar) los leen de `oferta.json` y `estado.json`. D7 queda dormido y solo se reinvoca por pedido de D8/D9 (REFRESCO/ESCALA).
- **Con incidente** (anomalías, rechazos, tracking sin captura): no hay traspaso estable. El Maker deja el informe (`INCIDENTE` en el log: qué, cuándo, evidencia, quién decide) y devuelve `ESCALAR` al dueño. D8 recibe igual el `traspaso.json` con `lanzamiento_estable = false`, no decide rendimiento y trata las etapas 0/2/4 en rojo como INCONCLUSA con responsable D7/D5.
- `traspaso.json` guarda la **última** ventana medida; el histórico completo queda en `lanzamiento.log` (línea `VENTANA` con la copia). Calendario: las cinco ventanas se calculan desde T0 y se dejan escritas en el expediente.
- Nada de lo anterior reactiva: reactivar es H siempre.
