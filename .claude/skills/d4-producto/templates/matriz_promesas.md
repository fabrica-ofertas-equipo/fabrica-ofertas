# Matriz promesas ↔ entregables ↔ prueba — {oferta_id} · {locale} · {version}

> Fuente de verdad: `producto.json#matriz_promesas`. Este archivo es su vista legible (lo mantiene el Maker; `cobertura_matriz.py` comprueba el JSON).
> Regla: toda promesa de la landing/oferta tiene un entregable y una prueba ejecutable, y todo ítem del paquete mapea a una promesa (si no, es relleno: se tacha).

## A. Promesa → entregable → prueba (sentido «promesa → producto»)

| `promesa_id` | Texto exacto de la promesa (de `claims_permitidos`/bonus/bump) | Origen | `entregable_id` | Ubicación (archivo · sección/hoja) | Prueba ejecutable | Estado |
|---|---|---|---|---|---|---|
| {kebab} | {texto idéntico a oferta.json} | claim / bonus / bump / entregable / tiempo | {item.id} | {archivo · cap. N} | {qué se abre, ejecuta o calcula y qué resultado se espera; caso dorado CD-NN; paso de autoprueba} | cumplida / parcial / pendiente |

## B. Ítem → promesa (sentido «producto → promesa»)

| `item.id` | `en_paquete` | Promesas que prueba | ¿Página o sección sin promesa? (a tachar) |
|---|---|---|---|
| {id} | sí / no (muestra) | {promesa_id, …} | {ninguna / lista} |

## C. Tiempo (`tiempos`, base = {estimado|cold_run_humano})

| lectura_min | ejecucion_min (Σ pasos) | total_min | prometido_min (oferta) | límite aplicado | script |
|---|---|---|---|---|---|
| {n} | {n} | {n} | {n} | ≤ prometido (estimado) o ≤ tolerancia × prometido (cold run humano) | `tiempo_total.py` |

## D. Bump (ítem separable) y bonus
- Bump `{id}`: archivo propio `{archivo}`; va **pre-pago** si el método de pago no guarda tarjeta (BLIK, Bancontact, EPS, Pix) — lo decide D5; D4 solo garantiza que es separable.
- Bonus: cada uno es un archivo autocontenido; ninguno es servicio, comunidad, vivo ni suscripción.
