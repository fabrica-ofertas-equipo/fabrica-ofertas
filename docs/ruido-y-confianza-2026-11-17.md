# Ruido y confianza en las decisiones (17-nov)

El dueño, al ver el «ROAS neto est.» por anuncio: un anuncio puede empatar o perder un día y aun así ser rentable a lo largo del tiempo. Pidió revisar todo el sistema con esa idea. Decidió: **todo en neto**, y aprobó los cuatro puntos en este orden: 4, 1, 2 y 3.

## Punto 4 · Medir primero (`escalar-oferta/scripts/medir_ruido.py`)

Primera medición, el 17-nov, con 5 días de datos:

| Qué | Resultado | Lectura |
|---|---|---|
| Un día de un anuncio contra el siguiente (29 pares con ≥ US$ 5 cada día) | correlación **−0,12**; de 12 días con ROAS < 1, **6** dieron ≥ 1,5 al día siguiente; de 13 días ≥ 1,5, **8** dieron < 1 al siguiente | un día solo de un anuncio no predice nada |
| Dispersión de compras diarias por anuncio | media 1,5, varianza 4,6 (índice **3,1**) | más vaivén que el azar puro: también hay cambios reales (fatiga, presupuesto) |
| Ventanas de 4 h de la escala contra el día completo | 1 de 10 con veredicto contrario | poca muestra todavía; se repite cada semana |
| Decisiones de la escala contra sus 24 h siguientes | sin medir: las fotos por hora empiezan el 16-nov | se mide desde ahora |
| Compras de Meta contra compradores de la tienda | Meta **99**, tienda **117** (0,85) | Meta se queda corta ~15 % (Oferta F 16-nov: 22 contra 30) |

Se corre en la revisión diaria; con más días los números se recalibran.

## Punto 1 · Un solo valor por comprador, en neto

`dashboard/negocio.py` → `neto_por_comprador_ventana` es **el** valor por comprador del sistema:
- el neto (después de la comisión de la tienda; **sin** producción ni fijos) dividido por los compradores;
- los upsells y bumps suman al neto, pero no cuentan como compradores;
- la ventana son los últimos 7 días; con menos de 50 compradores pasa a 14; si tampoco llega, toda la historia;
- la ventana no cruza el último cambio del embudo (`backend.desde` activo o `ficha.cambios_embudo`) siempre que desde ese cambio haya ≥ 10 compradores.

Lo usan:
- el panel (ROAS neto est. y ROAS 3 d);
- la escala por campaña;
- los ganadores de `plan_renovacion.py`;
- la R16 de `congelamiento.py`;
- la R4b de `corte_post_test.py`.

Los umbrales se pasaron a neto con equivalencia exacta (neto ≈ 92 % del bruto en la cartera), así que con los mismos datos se decide lo mismo:

| Regla | Antes (bruto) | Ahora (neto) |
|---|---|---|
| Escala: surfear | 1,8 | 1,65 |
| Escala: bajar | 1,5 | 1,4 |
| Escala: ROAS alto (+10 %) | 3 | 2,75 |
| Ganador para iterar | > 2,0 | > 1,85 |
| R16 renovar | CPA ≤ 0,5 × AOV | CPA ≤ 0,54 × valor neto |

## Punto 2 · ROAS de 3 días pesando lo reciente

Hoy pesa el 50 %, ayer el 30 % y anteayer el 20 % (`negocio.PESOS_3D`).
- **En el panel:** columna «ROAS 3 d» del top 20 y de la tabla de todos los anuncios.
- **En la escala:** la previa de cada campaña es su CPA de los 3 días anteriores con esos pesos (`escalar_presupuesto.cpa_previo_de`). Si no vendió, se usa la oferta en 7 días; si tampoco, el empate.

## Punto 3 · Decidir con el rango

`negocio.roas_estimado`:
- Lo que se ve se acerca a lo previo, como si ya se hubieran visto 3 compras a ese ritmo.
- El rango es el 80 % central de lo probable (Gamma-Poisson).
- Con muchas compras propias manda lo propio; con 1 o 2, manda lo previo.

En la escala:
- **Subir:** estimado ≥ 1,65 y además **piso ≥ 1,0**. Aun en el caso pesimista razonable no pierde.
- **Bajar:** estimado < 1,4, con la misma muestra mínima de antes.
- El freno de pérdida (corte de 1,5 tickets, R1) **no cambia**: protege la caja y tiene que ser rápido.

En el panel, el «ROAS 3 d» se pinta:
- verde si hasta el piso gana;
- rojo si ni el techo empata;
- gris si todavía no se sabe.

## Queda abierto

- **Corrección por atribución.** Meta cuenta ~15 % menos compras que la tienda. No se corrigió en las reglas porque las compras que faltan no se pueden asignar a una campaña. Si la medición lo sostiene, se puede multiplicar el ROAS por campaña por la razón tienda/Meta de 7 días. Lo decide el dueño.
- **Fuerza de la previa (3 compras) y nivel del rango (80 %).** Se recalibran con `medir_ruido.py` cuando haya 2 semanas de datos.
