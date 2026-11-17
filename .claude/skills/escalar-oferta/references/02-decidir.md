# Decidir qué hacer con cada oferta: una regla por situación

Pedido del dueño (2026-11-13): «quiero que este sistema sea automático, que haya una regla o automatización para cada situación y que sea robusto». Cada fila dice la situación, la regla, si está **firmada** (se aplica sola) o es **propuesta** (se calcula y se informa, pero no se ejecuta hasta que el dueño la firme), y quién la ejecuta.

**Los números de todas las reglas viven en `ofertas/_funnels/reglas.json`** y de ahí los leen todos los scripts (`scripts/reglas.py`) y el panel. Esta tabla los explica; si cambia una regla, se cambian los dos y se anota la fecha en `cambios`.

## Las cuentas que usan todas las reglas

- **Ticket del corte:** el precio en USD del **producto completo**, el más alto entre las tiendas del funnel (principal y niveles). Un solo producto: su precio. Niveles de 13, 19 y 27 USD: 27. (Dueño, 13-nov.)
- **CPA real:** gasto en Meta ÷ ventas reales de la tienda (Meta subatribuye).
- **CPA de equilibrio = lo que deja cada venta (AOV neto), y es dinámico** (dueño, 13-nov: «lo que deja puede ser dinámico post backend ofensivo y no siempre es el front»): neto total de la oferta (producto principal + bump + upsells + rebajas, después de comisiones) ÷ compradores (órdenes principales). Las ventas de upsell, bump y rebaja se cargan con `"tipo": "upsell"` (o `bump`, `downsell`): suman al neto, no cuentan como compradores. Con 7 días o más de datos se usa el de los últimos 7 días, así refleja el backend nuevo. Sin ventas, se estima con el precio y la comisión medida (≈ 8 %).
- **Ventana de 3 días:** los últimos 3 días cerrados del mercado. Las reglas post-test se miran una vez por día, en la revisión, nunca a mitad de un día.
- **Oferta que pega:** pasó el test con ventas y su CPA real (desde el inicio, o de los últimos 3 días cuando ya tiene 3 días cerrados) está en el equilibrio o por debajo. Ejemplo: Oferta B, CPA US$ 12,47 contra un equilibrio de 13,22.
- Con menos de ~30 checkouts, los porcentajes del embudo son pista, no veredicto.

## Las reglas

**Presupuestos siempre en números redondos** (dueño, 13-nov): dólares enteros, la mitad hacia arriba (84,5 → 85).

### Lanzamiento (firmadas el 13-nov)

| # | Situación | Regla | Estado |
|---|---|---|---|
| L5 | Ritmo de lanzamientos | **2 ofertas nuevas por día**, solas, mientras el banco tenga al menos 3 candidatos listos y haya **menos de 8 ofertas en test** a la vez | **Firmada** |
| L3 | Activar la campaña de un lanzamiento | **Se activa sola si pasa el control previo**: landing y checkout responden, píxel, precio de la regla 19/27, presupuesto de 3 tickets, **inicio a las 00:00 del mercado en su zona horaria**, corte configurado. Anuncios rechazados (dueño, 16-nov): **solo se apelan una vez; nunca se reemplazan, corrigen ni rehacen** (ni a mano ni solos). Si la apelación se pierde, queda rechazado y listo. Una campaña con otros anuncios **sale igual** con los que quedan; una pocket 1-1-1 con su único anuncio rechazado **no sale**. Reemplaza el «con 5 o más no se activa» | **Firmada** (13-nov; rechazados 16-nov) |

### Test y después

| # | Situación | Regla | Estado | Ejecuta |
|---|---|---|---|---|
| R1 | Test (día 1 del mercado, o mientras no venda) | Gasto ≥ 1,5 × ticket del completo × máx(1, ventas) → **apagar en el momento** | **Firmada** (12-nov; ticket del completo 13-nov) | Vigilancia de cada hora, sola |
| R1b | Test que llega al corte sin ventas, con buenas señales | **Segunda oportunidad: +0,5 ticket una sola vez** si CTR ≥ 1 %, ≥ 8 % de las visitas va al pago y hay ≥ 3 pagos iniciados (el problema es el pago o la muestra, no el anuncio ni la página). Si falla el checkout, se arregla antes | **Firmada** (13-nov) | Vigilancia, cada hora |
| R2 | Termina el día 1 sin ventas y sin llegar al corte | Sigue en test; avisar una vez que Meta casi no entregó (dueño, 13-nov: solo avisar, sin tocar nada) | **Firmada** | Vigilancia, sola |
| R3 | Pasa el test con ventas | Pasa a post-lanzamiento y se arma el **backend ofensivo** ese día | **Firmada** (el backend queda activo, 13-nov) | Revisión diaria → skill `backend-ofensivo` |
| R4 | Post-test, cada venta cuesta mucho más de lo que deja | CPA real de 3 días ≥ 1,5 × lo que deja cada venta (AOV neto dinámico, con backend) — o gasto de 3 días ≥ 1,5 × eso sin ventas → **apagar**. Se mide la oferta entera: las rondas diarias no frenan el corte | **Firmada** (13-nov) | Revisión diaria |
| R4b | Post-test, el día 1 no se repite | Con el **backend activo** y **al menos una ronda de renovación con 24 h de entrega**, se mide R4 **sin el día 1 del test**: si los días posteriores (mínimo 2; el último cuenta si ya gastó el 70 % del presupuesto diario) suman CPA ≥ 1,5 × lo que deja cada venta, y **ningún conjunto de renovación vende con ROAS de tienda ≥ 1 y ≥ 2 compras** → **apagar**. Motivo: la ventana de 3 días de R4 incluye el día 1 que pasó el test y tapa la caída (Oferta B, 14-nov: día 1 ROAS 1,52; días 2 y 3 ROAS 0,45 cada uno; R4 daba 1,31 × y no cortaba, R4b daba 2,1 ×). Números en `reglas.json` → `post_test.caida_tras_dia1`; decide `scripts/corte_post_test.py` | **Firmada** (14-nov, dueño: «me parece bien con dos días»; la alternativa de 3 días se descartó) | Vigilancia de cada hora (paso 7b), sola |
| E1 | Post-test, ROAS entre 1,75 y 2 | **+30 % cada 24 h** (ROAS de Meta desde el último cambio de presupuesto, con al menos 2 compras) | **Firmada** (13-nov; tramo 1,75-2 desde el 14-nov) | Vigilancia de cada hora |
| E2 | Post-test, ROAS mayor a 2 | **Surfeo**: cada 3 h, con al menos 2 compras desde el último cambio, +30 % en ROAS 2 subiendo lineal hasta +50 % en ROAS 6,5; por encima, +50 %. Sin techo. **Desde 500 USD/día no se surfea: +30 % cada 24 h.** Con 200 USD/día y ROAS ≥ 1,75, aviso de crear la segunda cuenta | **Firmada** (13-nov; desde ROAS 2 y no 2,5, 14-nov) | Vigilancia de cada hora |
| E3 | ROAS de la TIENDA desde el último cambio bajo 1,5 | **Bajada simétrica −30 %** en el momento (con ≥ 3 h y ≥ 2 compras o ≥ 1,5 tickets gastados), confirmada con la tienda (bruto con upsells; si Meta da menos pero la tienda vendió, no se baja). **Nunca baja del presupuesto inicial.** Sin bloqueo: si vuelve a dar ROAS > 2, se vuelve a subir. Reemplaza al tirón de 3 h, que se disparaba por azar con pocas ventas | **Firmada** (14-nov, «avancemos con las reglas que abarcan más situaciones») | Vigilancia de cada hora |
| E4 | Post-test, ROAS de tienda entre 1,5 y 1,75 | No se sube ni se baja. Si pierde, corta R4 | **Firmada** (13-nov; piso 1,5 desde el 14-nov) | — |
| E5 | Meta y la tienda no coinciden | Manda la tienda (upsells incluidos): la vigilancia la lee antes de bajar, y la revisión diaria compara la ganancia del día con la del escalón anterior y lo informa | **Firmada** (13-nov; 14-nov) | Vigilancia y revisión diaria |
| E6 | Escalar con campañas nuevas (bid cap, cost cap, ROAS mínimo, otras cuentas) | **Todavía no**: por ahora se escala y se renueva solo en la misma CBO del test. Ideas anotadas en `07-escala-simetrica.md` §4 para cuando haya volumen | Pendiente (dueño, 14-nov) | — |
| R7 | Post-test, pierde poco (CPA entre 1,0 y 1,5 × lo que deja) | ~~No subir; seguir renovando cada día mientras no llegue a R4~~ → **reemplazada por R16** (15-nov): sin renovar; solo actúan los cortes | Reemplazada | — |
| R16 | Empate con ventas | **Renovar y escalar solo con CPA ≤ la mitad del ticket promedio** (AOV bruto con bump y upsells). Si no llega a eso, tiene **≥ 3 ventas** y **ROAS neto ≥ 0,95** → **congelar un día**: sin renovación ni cambios de presupuesto, solo **backend agresivo (2 order bumps + 4 upsells post-pago)**. Al terminar se miden los días congelados: CPA ≤ ticket/2 → renovar; sigue en la banda → **un 2.º día**; después del 2.º día en la banda → aviso y **decide el dueño** (sigue congelada). Bajo 0,95 → sin renovar, actúan los cortes. Los cortes R1/R4 valen durante el congelamiento. Una oferta se congela sola una vez. **Solo rige la ENTRADA** (dueño, 15-nov: «separarlas»): una oferta **validada** (ya escaló por encima del presupuesto inicial, o una ronda de renovación entregó 24 h) **nunca se congela**; renueva mientras el **ROAS neto de los 3 días cerrados sea ≥ 0,95**, el presupuesto lo deciden E1-E4, la cortan R4/R4b, y si cae en el empate (ROAS neto 0,95-1,20) se le suma el backend agresivo sin frenar nada. Ventanas con días cerrados de la cuenta (el día en curso no cuenta). Primer caso: Oferta G (FR), 15-nov: 3 ventas, CPA 21,83, ticket 23,55, ROAS neto 0,99. Números en `reglas.json` → `congelamiento`; decide `scripts/congelamiento.py` | **Firmada** (15-nov, dueño: «cuando el CPA es la mitad o menos que el AOV», piso 0,95, «otro día congelada») | Vigilancia de cada hora (paso 3c), sola |
| R9 | Oferta que pega (desde el 15-nov, R16: en la entrada **CPA ≤ la mitad del ticket promedio**; validadas, **ROAS neto de 3 días cerrados ≥ 0,95**; antes CPA ≤ equilibrio desde el inicio) | **Renovar todos los días: 10 creativos** (**100 % nuevos** desde el 15-nov: primero los mejores anuncios del referente modelados y mejorados, después conceptos nuevos desde la landing; antes 7 iteraciones del ganador + 3 del referente), en un **conjunto nuevo dentro de la misma CBO** con **límites de gasto de mínimo 10 % y máximo 20 %**, que sale a las 00:00 del mercado | **Firmada** (13-nov) | Tarea «renovacion-diaria» → `05-renovacion-diaria.md` |
| R9b | Mínimos que se apilan | **Cada conjunto conserva el 20 % dos días enteros** y después se le quita (dueño, 13-nov: «darle solo un día 20 % capaz es poco presupuesto»). Durante el día corren con mínimo el conjunto de su primer día y el de su segundo (40 %); el 60 % queda libre para lo que ya vende | **Firmada** | Tarea «renovacion-diaria» |
| R10 | Conjunto nuevo en una CBO | Mínimo de gasto del 20 % del presupuesto, puesto en el Administrador y comprobado | **Firmada** | Quien crea el conjunto |
| R14 | Anuncios y conjuntos que solo gastan | **No se pausa nada**: la CBO reparte sola (dueño, 13-nov) | **Firmada** | — |
| R11 | Cambios de campaña | A las 00:00 del mercado; apagar y los cambios de presupuesto por ROAS (E1-E3), en el momento | **Firmada** | — |
| E6 | Una oferta gana una semana | **Réplica**: 7 días con ROAS neto (neto de la tienda ÷ gasto en Meta) ≥ 1,30 → se lanza sola en el siguiente mejor país de `elegir_mercado.py ordenar … --oferta "<oferta>"` donde el referente no pauta (lee `ficha.referente_paises` del libro, que mide cada mañana la vuelta de buscar-ofertas con `paises_referente.py`; sin esa medición no se replica; el panel lo muestra en Negocio, «Dónde corre la oferta original»), con los 10 anuncios que más vendieron (traducidos, voz local). Cuenta como uno de los 2 lanzamientos del día | **Firmada** (13-nov); por construir | Tarea de lanzamiento |
| P1 | Un cliente pide reembolso | El sistema prepara la respuesta y la devolución, avisa al dueño y **espera su sí** en cada caso | **Firmada** (13-nov) | Dueño |
| P2 | Llega una disputa o contracargo | Responder solo el mismo día con la prueba de entrega (orden, correo de entrega, descarga) y avisar al dueño | **Firmada** (13-nov); por construir | Revisión diaria |
| P3 | Mails de clientes en support@ | Leerlos dos veces por día y responder solos «no me llegó» y «no abre» con plantilla y el enlace; reembolsos y casos raros, al dueño | **Firmada** (13-nov); falta conectar Gmail | Tarea de soporte (por construir) |
| R12 | Reactivar una oferta apagada | Lo decide el dueño (si ya está cerrada, restaura sus tiendas desde «Tiendas archivadas» de Impultienda) | **Firmada** | Dueño |
| R15 | Oferta apagada: cerrarla | **72 h después del apagado**, la oferta pasa a `cerrado` y **cada tienda suya se archiva en Impultienda** (Configuración → Zona de peligro → «Eliminar tienda»: archiva, no borra; se restaura). Cierran los cortes por regla (R1, R1b agotada, R4, R4b) y los apagados a mano del dueño. **No cierran:** pausas técnicas (`pausa_tecnica`), `cierre.no_archivar`, una venta posterior al apagado (se avisa) ni una pausa sin `apagado` registrado. La campaña queda pausada en Meta; fan page y píxel no se tocan. Así en Impultienda solo quedan las ofertas vivas y se liberan cupos. Números en `reglas.json` → `cierre`; decide `scripts/cierre_oferta.py`; procedimiento en `04-vigilancia.md` «Al cerrar» | **Firmada** (14-nov, dueño: «72 h después», «cortes por regla y a mano») | Vigilancia de cada hora (paso 7), sola |
| R13 | Precio de los upsells | **Aprende solo** (`backend-ofensivo/scripts/precio_upsells.py`): escalera de 5 precios, tandas de 30 vistas, muestreo de Thompson hacia el precio que más deja por comprador; aprende entre ofertas | **Firmada** (13-nov) | Revisión diaria |

Los frenos de cuenta (300 USD por día y −3.000 USD acumulados) **los eliminó el dueño el 13-nov**: cada oferta se corta por su propia regla.

## Cómo se aplica hoy

- **Firmadas:** se ejecutan sin preguntar.
- **Propuestas:** la revisión diaria calcula la regla, dice qué haría («R7: no subiría y seguiría renovando») y no lo ejecuta. Al firmarla el dueño, se cambia el estado en esta tabla, en `dashboard/web/lib/flujo.js` (`REGLAS`) y en el `CHANGELOG.md`, y desde ahí la revisión la ejecuta sola.
- Lo que el dueño pide explícitamente (escalar una oferta, renovar) se hace aunque la regla sea propuesta.

## Lo que todavía no tiene regla

- ~~Activar la campaña de un lanzamiento~~: obsoleto, ya es la regla L3 (firmada el 13-nov).
- ~~Lanzar una oferta nueva sin que el dueño la pida~~: obsoleto, ya es la regla L5 (2 por día).
- ~~Poscompra: soporte, reembolsos y disputas~~: obsoleto, ya son P1-P3 (P2 y P3 por construir).
- Hoy no queda ninguna situación de esta tabla sin regla; las que están «por construir» tienen la regla firmada pero no el código o la tarea.

## Qué no es de esta skill

- Buscar y elegir la próxima oferta: `buscar-ofertas`.
- Lanzar una oferta nueva, rehacer el producto, la tienda o la landing, o crear la primera campaña: `modelar-y-lanzar-oferta`.
- Armar los upsells post-compra: `backend-ofensivo`.
