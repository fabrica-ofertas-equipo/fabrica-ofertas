# Fase 5 · Medir y ajustar

El precio correcto de cada upsell se encuentra midiendo, no suponiendo.

## Qué se lee

- Analítica del embudo: `/marketing/post-compra/analytics` de cada tienda. Por oferta: cuántos la vieron, cuántos aceptaron, cuántos aceptaron la rebaja.
- Ventas de upsells en Impul Pay («Últimos movimientos»): bruto y neto.
- Se lee en la revisión diaria de `escalar-oferta` y se carga en el libro: `backend.medicion` con `{fecha, vistas, aceptadas, aceptadas_rebaja, neto_usd}` por upsell.

## Precio que aprende solo (firmado por el dueño el 13-nov: «algo robusto automático, con criterio… que aprenda en base a datos»)

`scripts/precio_upsells.py` (P). Busca el precio que deja **más plata por comprador que ve la oferta** (precio × aceptación).

1. **Al crear cada upsell:** `python3 $P alta <oferta> <upsell> --precio <inicial> --moneda MXN --principal <precio del principal> --posicion 1|2|3`. Arma una escalera de 5 precios (×0,70 a ×1,40, terminados en 9) y arranca con lo aprendido en otras ofertas.
2. **En cada revisión diaria:** leer en la analítica del embudo los totales acumulados de vistas y aceptadas de cada upsell → `python3 $P leer <oferta> <upsell> --vistas N --aceptadas M`.
3. `python3 $P decidir` →
   - `MANTENER`: la tanda de 30 vistas sigue en curso, o el sorteo vuelve a elegir el mismo precio;
   - `CAMBIAR` → cargar `precio_nuevo` en Impultienda («Precios por mercado», escrito con teclado; guardar, recargar y comprobar) y `python3 $P aplicado <oferta> <upsell> --precio <nuevo>` (con `--consolidado` si la decisión lo dice);
   - `CONSOLIDADO`: ese precio es el mejor con ≥ 90 % de probabilidad; se deja y cada 300 vistas se prueba un escalón vecino;
   - `CAMBIAR_PRODUCTO`: nadie acepta ni al precio más bajo en 60 vistas → avisar al dueño y proponer otro producto (fase 1).
4. Con niveles, el precio de cada upsell es el de su nivel (proporcional a la entrada, `01-productos-y-precios.md` § «Precio por nivel»); un ajuste se aplica a todas las tiendas manteniendo la proporción. La rebaja que aparece al rechazar se mueve con él (mismo porcentaje).

Lo que aprende queda en `empresa/backend/aprendizaje.json` (aceptación por «precio ÷ principal» y por posición) y es el punto de partida del siguiente upsell.

## Qué cuenta para el equilibrio

El neto de los upsells sube el **neto medio por orden**. Desde que hay backend, el CPA de equilibrio de la oferta es ese neto medio (principal + bump + upsells), no solo el del producto principal. `escalar-oferta` lo usa para decidir escalar o apagar.
