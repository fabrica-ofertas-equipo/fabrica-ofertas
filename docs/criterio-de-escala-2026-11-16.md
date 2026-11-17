# Escala: lo que hiciste a mano, lo que hizo el sistema y el criterio que sale de eso

Revisión del 16-nov-2026, hecha alrededor de las 15:00 (horario de la cuenta). Fuentes: historial de cambios de Meta de la cuenta «Impultienda 1» (en «Never Give Up» no hubo cambios de presupuesto), métricas por hora de cada campaña, `ofertas/_funnels/escala.jsonl` y `REVISION-2026-11-16.md`. Los números de hoy son parciales: el día todavía no cerró.

---

## 1. Qué pasó (cronología)

### Lo que hizo el sistema (ayer, 15-nov)

| Hora | Campaña | Cambio | Por qué |
|---|---|---|---|
| 09:58 | TeO CBO test | 211 → 277 (+32 %) | Surfeo: ROAS 2,34 con 7 compras |
| 13:54 | TeO CBO test | 277 → 383 (+38 %) | Surfeo: ROAS 3,89 con 3 compras en 3,9 h |
| 17:54 | TeO CBO test | 383 → 268 (−30 %) | Bajada: ROAS de tienda 1,13 (2 ventas en 3,9 h) |
| 20:00 | — | Arrancan el **pocket B08** y las **variaciones B08** de TeO, y las réplicas IE (21:00) y NZ (hoy 08:00) | Réplica / renovación |

Desde ese momento, la CBO original de Oferta F **no volvió a tener una compra atribuida en Meta**: lleva unos US$ 145 gastados sin ventas. El ganador (B08) ahora compite contra sí mismo en el pocket.

### Lo que hiciste a mano (hoy, 16-nov, todo desde el Administrador)

| Hora | Campaña | Cambio | Qué decía el sistema en ese momento |
|---|---|---|---|
| 11:13 | TeO CBO test (original) | 268 → **187** (−30 %) | MANTENER: «ROAS 6,20 con 0 compras» |
| 11:20 | TeO variaciones B08 | 162 → **215** (+33 %) | Sin regla: el sistema no mira esta campaña |
| 11:20 | IE variaciones B08 | 162 → **230** (+42 %) | IE estaba **congelada por R16** desde las 07:53 |
| 12:10 | TeO pocket B08 | 324 → **421** (+30 %) | Sin regla: el sistema no mira esta campaña |
| 14:12 | IE variaciones B08 | 230 → **299** (+30 %) | Congelada por R16 |

---

## 2. Resultado de cada movimiento (antes / después, Meta)

| Movimiento | Antes del cambio (hoy) | Después del cambio | Lectura |
|---|---|---|---|
| **Bajar TeO original** | US$ 81, 0 compras, 5 checkouts | US$ 20, 0 compras, 2 checkouts | **Acertado.** Pero ojo: gastaba ~US$ 5/h tanto antes como después. Ya usaba menos de la mitad del presupuesto, así que la bajada casi no cambió nada. |
| **Subir TeO pocket** | US$ 166, 5 compras, ROAS 1,92 | US$ 61, 2 compras, ROAS 2,62 | **Acertado** hasta ahora. Era la única campaña con ROAS cerca de 2 y una muestra razonable. |
| **Subir TeO variaciones** | US$ 83, 3 compras, ROAS 1,79 | US$ 39, 1 compra, ROAS 0,83 | **Discutible.** La muestra de después es chica, pero subir una campaña que está para descubrir creativos le saca el rol que tiene. |
| **Subir IE variaciones ×2** (+85 % en 3 h) | US$ 172, 6 compras, ROAS 1,42 | US$ 24, 0 compras | **No lo habría hecho** (ver el punto 3). Hoy no ganó ni perdió nada porque Meta no gastó el aumento: eran las horas muertas de Irlanda. El efecto real llega mañana, cuando arranque con US$ 299 sobre un ROAS de 1,4. |

Cuenta completa de hoy (parcial, Meta): **US$ 904 gastados, US$ 1.160 en valor, ROAS 1,28.** Con lo que la tienda suma por upsells el número real es mejor (Oferta F: CPA US$ 25 contra US$ 48 que deja cada venta; IE: CPA US$ 32 contra US$ 46).

---

## 3. Mi opinión, movimiento por movimiento

1. **Bajar la CBO original de TeO: bien, y yo habría ido más lejos.** La pista que viste (0 compras desde que salió el pocket) es exactamente la correcta, y el sistema no la veía. Yo la habría bajado al inicial (US$ 162) o habría pausado los anuncios B08 que también están en el pocket. Si cuando la campaña no gasta su presupuesto le bajás el número, no cambia nada. El problema ahí es que se pisa con el pocket, no el presupuesto.
2. **Subir el pocket: bien.** Con la regla vigente no se habría subido (ROAS 1,92 cae en la franja 1,75–2, que pide esperar 24 h), y además el sistema ni miraba esa campaña. Tu lectura fue: «es el ganador probado, está rentable, la mañana fue buena → más plata acá». Es correcta.
3. **Subir las variaciones de TeO: no lo habría hecho.** Una campaña de variaciones existe para encontrar el próximo ganador con un presupuesto fijo. Cuando un anuncio gana, se lo pasa al pocket. Si se sube el presupuesto de la de variaciones, Meta le carga todo al que va primero en esa campaña y se pierde el test.
4. **Subir IE dos veces: no lo habría hecho, por tres motivos:**
   - El ROAS de Meta era 1,42 (rentable gracias a los upsells, pero justito). Dos subas que suman +85 % en 3 h es la escala que se usa con un ROAS de 3 o más.
   - Fue en la tarde y la noche de Irlanda: el gasto ya venía bajando solo (de 40 a 5 US$/h). Hoy no se podía comprar nada con ese aumento. Lo que hace es dejar cargado el presupuesto de mañana.
   - IE estaba en su día 1 de test (cierra a las 21:00 ART). Yo esperaba al cierre y decidía con el día entero.

   Lo que sí reconozco: IE tiene el mejor embudo de la cartera (CR 2,6 %, checkout 8,5 %, compra 31 %). Tu intuición de que «esta tiene con qué» tiene base. Lo que no me cierra es el momento y la dosis, no la idea.

---

## 4. El criterio que hay detrás de lo que hiciste (corregido con lo que dijo el dueño)

> Corrección del dueño (16-nov): «no pasé de una campaña que no vendió a la otra; simplemente estoy surfeando lo que tiene buen CPA y mantiene también ROAS, ROAS comparado con el AOV de la tienda, y siempre trato de escalar por arriba de 1,8 porque tiene brecha para escalar todavía, pero a ojo».

Así que no estabas pasando plata de una campaña a otra. **Cada campaña se mira sola, con esta regla:**

- **ROAS de la campaña con el AOV de la tienda** = compras que Meta le atribuye a esa campaña × AOV real de la tienda (con bump y upsells) ÷ gasto. No se usa el valor de compra que informa Meta, que se queda corto, y tampoco el ROAS de la tienda entera, que mezcla las campañas.
- **Surfear desde ~1,8**, siempre que el CPA siga bien, porque todavía hay margen para escalar. Por debajo, no se sube. Si el CPA se va, se baja (eso fue la CBO original de Oferta F).
- **La hora y la dosis se deciden a ojo.**

Con esa regla, tus movimientos de hoy se leen así:

| Campaña | ROAS de Meta antes del cambio | ¿Pasa 1,8? |
|---|---|---|
| Pocket de Oferta F | 1,92 | Sí |
| Variaciones de Oferta F | 1,79 | En el límite |
| Variaciones de IE | 1,42 en Meta. Con el AOV de la tienda, ~1,6–1,8 (6 compras × AOV de IE ÷ US$ 172; con lo que deja cada venta, US$ 45,62, da 1,59 como mínimo) | En el límite: depende del AOV bruto de IE |
| CBO original de Oferta F | 0 compras | No: se baja |

**Qué cambia en mi lectura:** tu regla es coherente y en IE no estabas lejos. Lo que mantengo sobre IE es la dosis y la hora (dos subas que suman +85 % en 3 h, en la tarde de Irlanda y en su día 1 de test), no la decisión de subir.

**Qué tiene tu regla que el sistema no tiene:**
1. Mide **cada campaña** (el sistema mira una sola por oferta).
2. Usa el **AOV real de la tienda** en vez del valor de Meta o del ROAS de toda la tienda (que es lo que causó el «ROAS 6,2 con 0 compras»).
3. Surfea **desde 1,8** (el sistema pide más de 2 para surfear, y entre 1,75 y 2 espera 24 h).

Lo que todavía depende del ojo, y hay que convertir en números, es **cuánto subir y cuándo**.

## 5. Propuesta: pasar de umbrales a criterio

La idea no es sumar más reglas, sino cambiar qué se pregunta el sistema. Hoy pregunta «¿el ROAS de esta campaña cruzó tal número?». Tendría que preguntar estas cinco cosas, en este orden:

> Nota (después de la corrección): los puntos A y B quedan como la forma de medir. La regla de suba es la del dueño: ROAS de la campaña con el AOV de la tienda ≥ ~1,8 y CPA bien. La tabla C fija la dosis.

### A. ¿Cuánta plata merece la oferta? (lo decide la tienda)
- La unidad es la oferta, con todas sus campañas y tiendas juntas.
- Margen = (lo que deja cada venta − CPA) ÷ lo que deja cada venta, con la tienda consolidada y los upsells incluidos.
- El presupuesto total de la oferta sube o baja según el margen y según qué tan segura es la muestra.

### B. ¿A qué campaña va esa plata? (lo decide Meta)
- Cada campaña tiene un rol:
  - **Pocket / ganador:** es la que escala.
  - **Variaciones:** presupuesto fijo, no se escala; cuando algo gana, se gradúa al pocket.
  - **Original:** cuando sale el pocket con su ganador, se baja al inicial o se apagan los duplicados.
- Se reparte según las compras que Meta atribuye a cada campaña desde el último cambio, nunca con el ROAS de la tienda.

### C. ¿De qué tamaño es el paso? (según cuánto confiamos en los números)
En vez de «≥ 2 compras sí, 1 no», el tamaño del paso crece con la muestra y con el margen:

| Muestra desde el cambio | Margen alto (CPA ≤ 0,5 × lo que deja) | Margen medio (0,5–0,8) | Margen justo (0,8–1,0) |
|---|---|---|---|
| 2–3 compras | +20 % | +10 % | quieto |
| 4–7 compras | +30–40 % | +20 % | quieto |
| 8 o más | +50 % | +30 % | +10 % |

La bajada sigue el mismo espejo: CPA por encima de lo que deja con muestra → −20 a −30 %. Por encima de 1,5 × lo que deja → la corta R4.

### D. ¿Sirve tocar el presupuesto ahora?
- **Ritmo de gasto:** si la campaña gastó menos del 60 % de lo que le correspondía a esa hora, no se toca el presupuesto. Lo que falta son creativos o subasta, no plata. Se avisa y se mira esa causa.
- **Hora del mercado:** se sube solo antes del mediodía del mercado, cuando queda día para gastar. De ahí en adelante no se toca y se decide al cierre del día del mercado.
- **Día 1 de test:** no se toca hasta que cierre, salvo que el margen sea alto con 4 compras o más.

### E. ¿Hay algo raro?
- Una campaña con 0 compras en Meta y 2 tickets gastados mientras otra de la misma oferta vende es **canibalización**: se baja al inicial o se apagan los anuncios duplicados.
- Si Meta y la tienda dan números muy distintos, no se decide hasta que coincidan.

---

## 6. Huecos concretos que encontré en el sistema

1. `escalar_presupuesto.py` mira **una sola campaña por oferta** (la del libro). El pocket, las variaciones e IE/NZ quedan fuera de la escala, y por eso tuviste que hacerlo a mano.
2. `tienda_desde_cambio` es de toda la oferta, pero se usa como si fuera de una sola campaña. De ahí salen el «ROAS 6,20 con 0 compras» de las 11:10 y el «ROAS 16,99» de las 14:45 en una campaña sin ventas.
3. El sistema no se da cuenta cuando tocás algo a mano. A las 13:40 ya leía 187 como presupuesto, pero no registró que el cambio fue tuyo ni por qué.

---

## 7. Cómo aprender tu criterio sin pedirte que lo escribas

- **Registro de decisiones a mano:** cada hora, el historial de Meta detecta los cambios hechos por vos que no coinciden con una decisión del sistema. Los guarda con la foto de los números de ese momento y te pide el porqué en una línea, con opciones («margen», «canibalización», «momentum», «intuición»).
- **Ver el resultado después:** a las 24 h se compara lo que pasó con lo que habría hecho el sistema.
- **Calibrar cada semana:** con 10–15 casos se ajustan los números de la tabla C y el ritmo de D. Así las reglas se mueven con tus resultados y no al revés.

---

## Resumen

Hoy acertaste en lo más importante: bajar la campaña que se canibalizaba y subir el pocket. Las dos cosas el sistema no las podía ver por diseño. En IE la idea era buena, pero llegó en mal momento y con demasiada fuerza. Lo que conviene programar no es «subí cuando el ROAS pase de X», sino estas cinco preguntas: cuánto merece la oferta, a qué campaña va la plata, de qué tamaño es el paso, si sirve tocar ahora y si hay algo raro.
