# Revisión diaria de un funnel en marcha

Pedido del dueño (2026-11-12): revisar cada funnel que corre con las métricas de Meta, la conversión de Impultienda y la comparación entre visitas, % de checkout y % de compra; probar todo «al máximo»; llevar el control de cuánto costó cada test (Kie, Meta y lo demás) y cuánto facturó neto; y volcar lo aprendido en la skill. Modelo de salida: `ofertas/_funnels/REVISION-2026-11-12.md`.

Se hace a la mañana siguiente del arranque (o cuando el dueño la pida) y después una vez por día mientras el test siga.

## 1. Referencias del dueño

| Tramo | Referencia | Lectura |
|---|---|---|
| Visitas → checkout | **10 %** (8-12 %) | Por debajo: la landing no convence. Por encima: la landing funciona |
| Checkout → compra | **25-30 %** | Por debajo: se pierde en el checkout (precio, confianza, medios de pago, carga) |
| CPA | ≤ **neto por venta** (equilibrio) | Neto = lo que Impul Pay deja después de comisiones e impuestos (≈ 91,9 % del bruto en México) |

Con menos de ~30 checkouts por test, una venta cambia el % de compra en 3 a 15 puntos. Decirlo siempre como pista.

## 2. Leer, en este orden y antes de probar nada

Las pruebas suman visitas a las estadísticas de la tienda. Por eso primero se lee y después se prueba.

1. **Impultienda, estadísticas «Hoy»** de cada tienda del funnel. Incluye las tiendas de niveles (básico, completo), que no tienen visitas propias pero sí checkouts. Usar `__stats` de `fragmentos-navegador.md` §7. Da visitas, checkouts y compras con sus %.
2. **Impul Pay → «Últimos movimientos»** (`/dashboard/<tienda>/impulpay`). Trae cada venta con el bruto, «comisiones e impuestos» y el neto. Es la fuente del neto: no calcularlo a mano.
3. **Ventas → carritos abandonados**:
   - Impultienda registra el abandono cuando el comprador escribe el correo.
   - La repesca (mail con link de pago y 33 % de descuento) la manda sola la tarea «repesca-carritos» cada hora; acá solo se mira «Facturación recuperada · Por link de recuperación» para saber si rinde.
   - **0 abandonados con checkouts sin compra** significa que se fueron sin tocar el formulario. El problema está en lo que ven al abrir el checkout, no en el pago.
4. **Meta, anuncio por anuncio** (`ads_get_ad_entities`, `level=ad`, `date_preset=maximum`, filtro `campaign.id`).
   - Campos: `amount_spent, impressions, cpm, link_click, ctr, landing_page_view, omni_initiated_checkout, omni_purchase, video_p25/p50/p95_watched_actions, video_avg_time_watched_actions, frequency`.
   - `landing_page_view / link_click` dice cuántos clics llegan a cargar la página.
5. **Píxel** (`ads_get_dataset_stats`, `aggregation=event` y `url`, desde las 00:00 del mercado en Unix).
   - El Purchase puede tardar **~20 min** en aparecer.
   - Si Meta no atribuye una venta que el píxel sí tiene, falta el token de la API de conversiones.

## 3. Probar sin ensuciar

```bash
python3 .claude/skills/modelar-y-lanzar-oferta/scripts/probar_funnel.py <tienda> [<tienda-básico> ...] --pais MX --salida <scratchpad>/pruebas
```

- **Bloquea el píxel** por defecto. El 12-nov, las pruebas sin bloquear sumaron 6 InitiateCheckout y eventos de quiz reales.
- Qué mide:
  - respuesta del servidor y pintado principal con 4G simulada;
  - imágenes rotas, después de recorrer toda la página: las de carga diferida dan falso positivo si no se recorre;
  - enlaces al checkout y si conservan los UTM;
  - el quiz, si lo hay, hasta el video;
  - cada checkout enlazado.
- **Precio, moneda e idioma del checkout los decide la IP.** Desde Argentina se ve en US$ y en español rioplatense («o pagá con tarjeta») aunque el mercado sea Brasil. Para ver lo que ve el comprador:
  - panel → Diseño de checkout → **«Ver como otro país»** → elegir el país;
  - bajar con la rueda sobre la vista previa, que tarda unos 5 s;
  - comprobar moneda, medios de pago (México: tarjeta, OXXO, SPEI) e idioma.
- Mirar el primer pantallazo de cada landing en móvil: qué ve el comprador antes de deslizar.

## 4. Diagnóstico tramo por tramo

Escribirlo en este orden, con número y causa medida:

1. **Anuncio → clic:** CTR y CPM. Comparar con la historia de la cuenta (tuotroproyecto AR: CPM 3-7).
2. **Clic → página cargada:** `landing_page_view / link_click`, respuesta del servidor, pintado principal.
3. **Visitas → checkout**, contra la referencia del dueño.
4. **Checkout → compra**, partido en dos: (a) inicio de pago → apretó «Pagar» y (b) **pago completado** = ventas / (ventas + abandonados + rechazados) de `impultienda_carritos_abandonados`, sin las sesiones `prueba`/`revision`. Si (b) queda muy por debajo de la madre o de otras ofertas (en FR/IT, 15-nov: 1 de 5 contra 5 de 6 en España), el problema está en el cobro del país y no en la oferta: mirar la columna «Motivo» del panel. Criterios completos en `modelar-y-lanzar-oferta/references/13-auditoria-de-adaptacion.md` §C. Además, con los carritos abandonados, la carga del checkout, lo que muestra (precio tachado sí o no, medios de pago, bump) y la muestra.
5. **Anuncios:** quién se lleva el gasto (la CBO concentra el 80 % en 2) y qué tienen en común los que venden (presentadora, ángulo, público al que le hablan). Comparar con la promesa de la landing. Nada de conclusiones sobre anuncios con menos de US$ 2.

Por funnel: bien hecho / no funciona o no se sabe / mejorable sin tocar el modelo / lo que puso el dueño y sigue publicado (no se toca) / enlace a `no-modelado/`.

Incluir **«Lo que no es dato real»**, con hechos medidos. Ejemplo: el contador del checkout mostró compradores en una tienda sin tráfico. No se cambia nada del dueño.

## 5. Libro de costos

**El libro se escribe solo con `python3 .claude/skills/escalar-oferta/scripts/libro.py`** (`set`, `append`, `merge`, `nuevo-test`, `set-raiz`): toma un candado, guarda una copia previa y escribe de forma atómica. Varias tareas lo tocan a la vez (vigilancia, renovación, lanzamientos); editarlo a mano puede pisar lo que escribió otra (escenario S38).

- `ofertas/_funnels/libro-de-tests.json`:
  - por test: producción (créditos de Kie, imágenes de Gemini, otros), Meta, embudo de la tienda y ventas con su neto;
  - costos fijos compartidos (plan de Impultienda, dominio);
  - tipos de cambio que usa Impultienda.
- Se actualiza en cada revisión.
- Tabla: `python3 .claude/skills/escalar-oferta/scripts/libro_de_tests.py --md ofertas/_funnels/libro-de-tests.md`. Da neto − Meta, neto − todo, CPA real y CPA de equilibrio.
- Al lanzar una oferta nueva, sumar su fila con los créditos de su `estado.md`.

### Para que el tablero «Negocio» del panel quede al día

El panel (`#/negocio`) lee solo este libro. En cada revisión, por test:

- `corte`: fecha y hora de la lectura, con zona (`2026-11-13T20:00-03:00`). Con más de 24 h el tablero avisa.
- `estado` (`activo`, `programado`, `pausado`) y `meta` con los totales al corte (`date_preset=maximum`), incluido `valor_compras_meta_usd` (`omni_purchase_values`): sin él, el ROAS Meta queda «sin dato».
- `tienda_embudo` y `por_tienda` (visitas, checkouts y compras de cada tienda del funnel).
- `ventas`: cada venta nueva con `orden`, `tienda`, `fecha` (día del mercado), `moneda`, `bruto`, `neto` y `nivel` si no es la principal. Las ventas de upsell, bump o rebaja llevan `"tipo": "upsell"` (`bump`, `downsell`): suben lo que deja cada venta sin contar como compradores (regla del 13-nov). **Nunca correo ni nombre del comprador.**
- `historial_diario`: un renglón por día y campaña con `ads_get_ad_entities`, `level=campaign`, `time_increment="1"`. Campos `fecha`, `campana`, `gasto_usd`, `impresiones`, `clics_enlace`, `visitas_landing_meta`, `inicios_pago_meta`, `compras_meta`, `valor_compras_meta_usd` y `leido`. Se reemplaza el día en curso y no se tocan los cerrados. El gasto del día en curso tiene que dar lo mismo que `meta.gasto_usd` al corte.
- `anuncios` (por test) — **desde el 15-nov lo carga solo `nube_sync.py` cada 5 minutos** (el worker `fabrica-vivo` lee Meta por anuncio: ayer y hoy en cada vuelta, los últimos 14 días una vez por hora; miniaturas en `ofertas/_funnels/_miniaturas/`). La ficha muestra el **top 20 de creativos** (mismo nombre sumado entre conjuntos) con todos sus KPIs. A mano solo si la nube falla (`nube.json` → `anuncios_error`): `{leido, lista[...]}` con cada anuncio de la campaña desde el inicio (`ads_get_ad_entities`, `level=ad`, `date_preset=maximum`): `id`, `nombre`, `conjunto_id`, `conjunto`, `estado`, `gasto_usd`, `impresiones`, `clics_enlace`, `ctr_pct`, `inicios_pago_meta`, `compras_meta`, `valor_compras_meta_usd` (`omni_purchase_values`), `video_p25`, `video_p100`. Incluir los anuncios de conjuntos nuevos aunque no gasten. Con esto la ficha calcula CPA, ROAS Meta, ROAS neto estimado, CTR, clic → pago, retención y el veredicto por anuncio (Ganador, Promete, Sin datos, Flojo, Mirar).
- `ficha.campanas[].anuncios`: gasto, vistas, clics, pagos iniciados y compras por anuncio, con `leido`. Cambios de conjuntos, presupuesto o estado van en la misma ficha.
- Oferta nueva: copiar la `ficha` de una existente (tiendas con `url` https y precio, campañas, píxel, fan page, referente, landing original, expediente, carpeta de trabajo). Sin ventas todavía, `equilibrio_estimado_usd` con su `equilibrio_nota`. Si es otra tanda de una oferta que ya existe, poner el mismo `oferta`.
- `programado` (opcional): `[{"cuando": "2026-11-13T00:00:00-06:00", "que": "una frase", "corto": "65 USD/día + conjunto R3"}]` (`corto`, ≤ 50 caracteres, es lo que se ve en la lista) con el próximo cambio ya programado en Meta (presupuesto, conjunto nuevo). El tablero muestra solo los que no pasaron; borrar los viejos en la revisión siguiente.
- `renovaciones` (desde el 13-nov): una entrada por cada ronda de creativos nuevos después del lanzamiento, `[{"ronda": "R3", "inicio": "2026-11-13T00:00:00-06:00", "estado": "activa", "anuncios": 10, "conjunto": "nombre del conjunto", "nota": "qué trae"}]`. Se carga al crear el conjunto (con su `inicio` a las 00:00, así sale «Renovación programada») y se pasa a `pausada` si se apaga la ronda. Sin esto, una oferta que pasó el test figura «Para renovar» aunque ya tenga ronda.
- `backend` (desde el 13-nov; lo carga la skill `backend-ofensivo`, y la revisión pone `armando` al dispararla): `{"estado": "activo", "desde": "2026-11-13", "upsells": [{"nombre": "…", "precio_usd": 21}], "tiendas": ["slug", …], "nota": "embudo y rebajas"}`. Estados: `activo`, `pausado`, `armando`, `listo` (armado por adelantado con el embudo apagado; R3b: lo prende la vigilancia en `activar_desde`, el fin del test), `no`. Sin el campo = sin backend. Al pasar el test sin backend activo, el panel lo marca «Falta backend» y lo pone en «Requiere tu atención».
- La **etapa** de cada oferta (Programada, En test, Para renovar, Renovación programada, Renovando, Para apagar, Apagada) la calcula el tablero con `estado`, `inicio`, la fase del test, el corte y `renovaciones`; no se carga a mano. «Renovando» dura 1 día desde el inicio de la ronda (`DIAS_RENOVACION_RECIENTE = 1` en `dashboard/negocio.py`, por la R9 de una ronda por día); después vuelve a «Para renovar». En el menú lateral las ofertas van agrupadas por etapa y con una «B» verde si tienen backend activo, «B!» ámbar si les falta.
- La «acción sugerida» de cada tarjeta (escalar, apagar, mirar un día más, sin pauta) la calcula el tablero: el corte a 1,5 tickets del producto completo (necesita el precio en USD de cada tienda del funnel en la ficha) y la escala por ROAS (E1-E5, firmada). No se carga a mano. Los anuncios de «Qué está vendiendo» salen de `ficha.campanas[].anuncios`.
- Al cargar el costo de un fijo (`usd_mes` del plan de Impultienda), el tablero lo reparte solo.
- Las métricas de cada funnel (facturación bruta y neta, comisiones, costos, ganancia contra Meta y neta, ROAS Meta, bruto real, neto y real, ticket medio, CPA real y de equilibrio) las calcula el tablero con las definiciones del dueño. Están escritas en «Cómo se calcula» y en el «?» de cada número. La producción no entra en el ROAS; entra en el ROAS real y en la ganancia neta.

#### Cada día, para que funcione el filtro de días del tablero

El tablero filtra por día, rango, hoy, ayer, últimos 7/14/30, este mes y mes anterior. Los días son los de la zona horaria de la cuenta publicitaria: `zona_horaria_cuenta` en el libro, hoy `America/Argentina/Buenos_Aires`.

- **Meta por campaña:** `historial_diario` con `ads_get_ad_entities`, `level=campaign`, `date_preset=maximum` y `time_increment="1"`. Un renglón por día con gasto, impresiones, clics, visitas, pagos iniciados, compras y `valor_compras_meta_usd`, más `leido`. Se reemplaza el día en curso; los días cerrados no se tocan.
- **Meta por anuncio (automático desde el 15-nov, ver arriba):** `anuncios.por_dia` con la misma lectura a `level=ad` y `time_increment="1"`. Solo hacen falta los días con gasto: `fecha`, `id`, `gasto_usd`, `impresiones`, `clics_enlace`, `inicios_pago_meta`, `compras_meta`, `valor_compras_meta_usd`, `video_p25` y `video_p100`. Además `anuncios.por_dia_leido`.
- **Ventas:** cada venta con `fecha`, y `dia_cuenta` si el día en la zona de la cuenta es otro.
- **Embudo de la tienda (14-nov):** el conector da cualquier día (`impultienda_estadisticas` con desde = hasta). La vigilancia de cada hora lo carga sola con `scripts/embudo_tiendas.py` (pedidos → leer → cargar): una fila por día en `tienda_embudo_diario` con `por_tienda`, y `tienda_embudo` con el total desde el inicio. El CR de la oferta es el de TODAS sus tiendas juntas (compras ÷ visitas a la landing); el de cada tienda por separado que muestra Impultienda no sirve en funnels de niveles.
  - `parcial: true` si es «Hoy» antes de que termine el día.
  - Lo ideal es leer «Ayer» a la mañana y guardarlo completo.
  - Si falta un día con pauta, el tablero muestra «sin dato completo» para ese período y no inventa nada.
- **Producción:** no se carga por día. Se imputa al día de inicio de la pauta.
- **Fijos:** se reparten por día de pauta solos.

Después correr `libro_de_tests.py --md …` y abrir `#/negocio` para comprobar que la acción sugerida y los números coinciden con la revisión.

Costos de referencia: 1 crédito de Kie ≈ US$ 0,005; imagen de Gemini ≈ US$ 0,134. Kling Avatar ≈ 10 créditos por segundo, y fue el 98 % del gasto de Kie de Oferta C.

## 6. Recomendaciones

- Ordenarlas por:
  1. gastar menos sin perder calidad de test;
  2. medir mejor;
  3. la fuga principal, con datos verdaderos;
  4. el modelo.
- Separar lo que hace el agente de lo que tiene que hacer el dueño:
  - el **token de la API de conversiones** por píxel;
  - la cuenta de **Microsoft Clarity**: el agente carga el Project ID en Configuración → Meta / Tracking;
  - conectar la cuenta de anuncios en **UTMIFLOW**.

**Corte del test:** firmado. 1,5 tickets del producto completo por venta → apagar (`04-vigilancia.md`). Si la revisión encuentra una oferta cruzada y todavía activa, la pausa ahí mismo.

## 6a. Chequeos del día (escenarios S10, S23, S34)

`python3 .claude/skills/escalar-oferta/scripts/chequeos_diarios.py --json`:
- **Kie:** si el saldo no alcanza para 2 rondas de renovación (5.400 créditos), aviso al dueño (la recarga es suya).
- **Comisiones y tipo de cambio:** aviso si la última venta de una tienda dejó un neto más de 1 punto distinto del habitual, o si los tipos de cambio del libro tienen más de 7 días (actualizarlos con `libro.py set-raiz tipos_de_cambio.<moneda> <valor>` y `tipos_de_cambio.fecha`).
- **Cartera:** la tabla de ofertas activas por ROAS neto de 7 días va en el resumen del día.
- **Gemini (voces, 13-nov):** el mismo comando hace una prueba REAL de la voz: una palabra con el modelo de los anuncios (`gemini-2.5-flash-preview-tts`), que cuesta una fracción de centavo. Así detecta lo mismo que haría fallar una voz:
  - saldo prepago agotado («prepayment credits are depleted»);
  - cuota;
  - facturación;
  - clave;
  - modelo retirado.
  Si falla, aviso urgente, porque sin voces no salen anuncios.
- **Saldo de Gemini:** Google no lo da por API; solo se ve en AI Studio → Billing.
  - Cuando el dueño lo diga en el chat, o lo veas con su sesión de AI Studio, anotarlo con `chequeos_diarios.py gemini-saldo --usd <saldo>`.
  - Aviso bajo `gemini.saldo_minimo_usd` (5 USD en `reglas.json`). Una voz de anuncio cuesta ≈ US$ 0,02.
  - Aviso también si pasan más de 7 días sin anotarlo.
- **Servicios y saldos (control total, 13-nov):** después del comando, anotar lo que solo se ve a mano, uno por servicio, con `chequeos_diarios.py anotar --servicio <id> --estado ok|aviso|error --detalle "<texto corto>"`:
  - `meta`: estado de la cuenta publicitaria y del medio de pago (de `ads_get_ad_accounts`: `account_status`, `disable_reason`, límite de gasto usado). Error si está deshabilitada o el pago falló; aviso si el límite pasa del 80 %.
  - `claude`: uso semanal del plan (herramienta `get_usage`). Desde el 14-nov lo anota además la vigilancia en cada vuelta completa (cada hora), igual que `meta`. Aviso desde 80 %, error desde 95 % o si el uso extra está desactivado y falta más de 1 día para la renovación: las tareas automáticas se cortan cuando se acaba.
  - `impulpay`: saldo disponible y bloqueado de Impul Pay (sin datos de clientes). Aviso si hay fondos bloqueados mayores al gasto de 3 días de pauta (conviene el adelanto del 2 %).
  - `gmail`: si el conector responde (lo sabe la tarea de soporte).
  - `impultienda` y `dominio`: si se ve la fecha de renovación del plan o del dominio, cargarla en `ofertas/_funnels/servicios.json` (`renueva`); aviso si faltan menos de 7 días.
  El panel lo muestra en «Cómo funciona» → «Servicios y saldos»; lo que esté en rojo o amarillo sube a «Lo que espera tus manos».

## 6a-bis. Dónde se pierde cada oferta (13-nov)

Por cada oferta con campaña activa y post-test: de Meta, los totales de los últimos 3 días y de los 3 anteriores (gasto, vistas de la página, ingreso con upsells —de la tienda si se leyó—, pagos iniciados y compras). Correr `python3 .claude/skills/escalar-oferta/scripts/metricas_embudo.py periodos --lectura <ruta> --registrar`.
- `lado` va en el resumen del día: «anuncios» (subió el costo por visita: lo arregla la renovación), «pagina_y_cobro» (bajó el ingreso por visita: revisar landing, checkout y upsells con `probar_funnel.py`), «ambos» o «estable».
- `SOSPECHA_CLON`: primero `probar_funnel.py` del checkout. Si el checkout falla, es `PROBAR_CHECKOUT` (`04-vigilancia.md`). Si anda, `avisos.py avisar clon-<oferta> --mensaje "…"` y anotar `libro.py set <test> renovacion_conceptos_nuevos true`: la próxima renovación de esa oferta hace 3 iteraciones + 7 conceptos nuevos en vez de 7 + 3, y después se quita el campo.

## 6b. Disputas, soporte y embudo (escenarios del 13-nov)

- **Disputas (P2, firmada):** en Impul Pay, buscar disputas o contracargos abiertos. Por cada una, el mismo día: juntar la orden, el correo de entrega y la descarga (o el acceso) y responder con esa prueba; aviso al dueño con el plazo y lo que se envió.
- **Embudo post-compra:** en la lectura de la salud, cargar `ventas_hoy` y `vistas_embudo_hoy` de cada oferta con backend activo (sale `EMBUDO_ROTO` si hubo ventas y nadie vio los upsells).
- **Soporte (P3):** lo hace la tarea de soporte cuando el dueño conecte Gmail; mientras tanto, nada.

## 6c. Aplicar las reglas de cada situación

Con los números de la revisión, recorrer la tabla de `02-decidir.md` oferta por oferta:

1. **Backend (R3, firmada):** si la oferta está en post-lanzamiento (pasó el día 1 con ventas) y el libro no tiene `backend.estado = "activo"`, `"armando"` ni `"listo"`, poner `backend: {"estado": "armando", "desde": <hoy>}` y **arrancar la skill `backend-ofensivo`** en esta misma vuelta. Si la vuelta es la de la tarea programada y no alcanza el tiempo, dejarlo en `armando` y seguir en la vuelta siguiente desde donde quedó (`09-backend/plan.md` de la oferta dice la fase).
2. **Post-test:** con la ventana de 3 días, ejecutar las firmadas (R4 corte por lo que deja cada venta; R4b —la misma cuenta sin el día 1— la aplica la vigilancia de cada hora, pero si una oferta da `APAGAR` con `corte_post_test.py` y sigue activa, apagarla aquí; E5 confirmar el ROAS con la tienda; R9 la hace la tarea «renovacion-diaria») y, de las propuestas (hoy R7), escribir en el informe qué haría cada una sin ejecutarla. La escala E1-E3 la aplica la vigilancia de cada hora.
3. **Upsells (R13, firmada):** con backend activo, leer la analítica del embudo y correr el precio que aprende (`backend-ofensivo/references/03-medir-y-ajustar.md`): `precio_upsells.py leer` y `decidir`; si dice CAMBIAR, cargar el precio nuevo en Impultienda y anotarlo con `aplicado`.

## 7. Cierre de la revisión

- `python3 .claude/skills/escalar-oferta/scripts/avisos.py latido revision-diaria ok|error --detalle "…"`.
- Resumen del día al celular (escenario S40), una vez: ganancia neta de ayer, qué se apagó, qué se lanzó, qué subió de presupuesto y qué espera las manos del dueño (`avisos.py avisar resumen-<fecha> --mensaje "…"`). Si PushNotification responde «not sent», `avisos.py no-llego <clave> --motivo "…"` para que vuelva a salir. Sumar al resumen los avisos de `avisos.py sin-entregar` (los que no llegaron en las últimas 24 h).

- Actualizar `tropiezos.md` con lo nuevo.
- Añadir al `FUNNEL.md` de cada funnel una línea «Revisión <fecha>: <resultado en una frase>» con enlace al informe.
- Decirle al dueño qué mirar en la siguiente revisión.


## Ruido de las decisiones (17-nov)

Una vez por día correr `python3 .claude/skills/escalar-oferta/scripts/medir_ruido.py` y anotar en el informe diario:
- la correlación de un día al siguiente;
- cuántas decisiones de la escala se sostuvieron en 24 h;
- la razón Meta/tienda.

Si la razón se mantiene lejos de 1 o las decisiones de la escala fallan más de la mitad, avisarle al dueño con los números: los umbrales y la fuerza de la previa se recalibran con él (`docs/ruido-y-confianza-2026-11-17.md`).

## Costos de producción al fino (17-nov)

- `chequeos_diarios.py` (modo `todo`) corre `barrido_costos.py --aplicar`: barre todos los `gasto*.jsonl` de las carpetas de trabajo (Kie, imágenes de Gemini) y el audio de las voces (Gemini TTS, por minuto), sin cobrar dos veces lo copiado de la madre a las réplicas, y lo deja en `produccion.barrido` de cada test. El tablero usa, por rubro, el mayor entre lo manual y lo barrido, y suma las voces.
- Cada script nuevo que llame a Kie o a Gemini **escribe su `gasto*.jsonl`** en la carpeta de la etapa (una línea por resultado cobrado: `ts`, `modelo`, `task_id`, `creditos` o `imagenes`). Sin esa línea el costo no existe para el tablero. Las voces no necesitan registro: se miden por el .wav.
- La renovación (R9) y el backend se ven como «renovación» en la ficha: es lo producido desde el día de salida.
- El saldo de Kie queda en `ofertas/_funnels/kie_saldos.jsonl` en cada lectura: la baja diaria del saldo tiene que parecerse a lo registrado; si se aleja, algún script no está anotando.
- La transcripción (whisper-cli) es local y no cuesta.
