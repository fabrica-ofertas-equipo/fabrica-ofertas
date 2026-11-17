# CHANGELOG · backend-ofensivo

## 0.4.1 · 2026-11-16 · ofertas nuevas a la cola y conectadas, sin mover lo testeado

El dueño: «si algo ya está funcionando, está testeado, ¿por qué lo cambiaríamos?». Las ofertas nuevas van a la cola y se conectan las dos ramas de la rebaja anterior con `impultienda_conectar_oferta_postcompra`; la cola va a precio lleno (0 %) con rebaja −35,71 %; el intercambio de lugares solo con ofertas sin ventas. Aplicado en ES (U04 «Cuidar a un padre o una madre en casa», 24/14/9 €), IE y NZ (mejora a la Complete, precios por nivel, B02 y U04). Regla en `01-productos-y-precios.md` punto 3 y `reglas.json` → `backend.por_nivel.orden`.

## 0.4.0 · 2026-11-16 · precio por nivel y mejora a la Completa

El dueño: «a las personas que compraron la del medio y la más baja ofrecerles los upsells de manera equitativa a su precio» y «ofrecerle la mitad de la diferencia, diciéndole lo que hubiese pagado». Datos: Oferta F 15 de 25 compradores de la Completa tomaron upsell, contra 1 de 15 de los niveles bajos. Aplicado en las 4 tiendas bajas de Oferta F (ES) y Oferta. Regla en `01-productos-y-precios.md` § «Precio por nivel», `SKILL.md` y `reglas.json` → `backend.por_nivel`.

## 2026-11-15 · lo aprendido armando Oferta G (R3b, 2 bumps + 4 upsells)

- Producción en paralelo: un agente por PDF con un brief común (`09-backend/BRIEF-produccion.md` de la oferta) y archivos con letra propia (`modeles_<l>.py`, `render_<l>.py`…) para no pisarse; el tope de Kie es el total compartido de `gasto.jsonl`. Cinco PDF verificados en ~20 minutos.
- El embudo «siempre» toma los productos «solo post-compra» que existen AL CREARLO: el bump del checkout se crea después del embudo (con «solo post-compra» encendido, para que no se vea) y se pasa al checkout al activar (`bump_al_activar`).
- Una ficha que Impultienda generó sola y quedó sin PDF («pending») se puede reusar como upsell: se cambia el nombre, el precio y se carga el PDF.
- El HTML de las rebajas necesita `ben_rep` en `contenido.py`; vacío publica una lista vacía. En la página de gracias conviene `mostrar_resumen: false` en mercados que no hablan español (el resumen sale en español).


## 2026-11-15 · modo agresivo para ofertas congeladas (R16)

Cuando la vigilancia congela una oferta en empate, el backend va con 2 order bumps + 4 upsells post-pago (antes: 1 bump + 3 upsells). Primer caso: Oferta G. Impultienda está en plan Unlimited (upsells por tienda y por embudo ilimitados, comprobado con `impultienda_ver_plan`): la regla de cupos de 3 del plan Max ya no limita.

## 0.2.1 · 2026-11-13 · Revisión de coherencia 2026-11-13

- `SKILL.md`: la fase 5 nombra `precio_upsells.py` y la regla R13 firmada (el CHANGELOG 0.1.0 la daba como propuesta).
- `01-productos-y-precios.md`: el precio de referencia del principal (MX$ 319) marcado como de ese momento; hoy MX$ 359 por la regla 19/27, que no rige para los upsells.
- Informe: `docs/_historial/revision-coherencia-2026-11-13.md`.

## 0.2.0 · 2026-11-13 · Precio que aprende

- `scripts/precio_upsells.py`: escalera de 5 precios, tandas de 30 vistas, muestreo de Thompson hacia el precio que más deja por comprador que ve la oferta; consolida, pide cambiar el producto si nadie acepta y aprende entre ofertas (`empresa/backend/aprendizaje.json`). Regla R13 firmada.
## 0.1.0 · 2026-11-13

Pedido del dueño: dividir las skills por proceso; el backend «no tiene nada que lo dispare».

- Nace separando el apartado «Backend ofensivo» de `modelar-y-lanzar-oferta/references/11-ofertas-que-suben-el-ticket.md` → `references/02-armar-en-impultienda.md` (texto sin cambios).
- Nuevo: `references/01-productos-y-precios.md` (sacado del plan de Oferta B) y `references/03-medir-y-ajustar.md` (regla de ajuste de precio, propuesta).
- Disparador: la revisión diaria de `escalar-oferta` la arranca cuando una oferta pasa el test con ventas y no tiene backend activo.
- Regla nueva para el cupo del bump (antes la decidía el dueño): si el bump repite la subida previa, se quita; si no, la tienda lleva dos upsells.

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual | Retro | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | pulida (en uso) | 2026-11-13 | Oferta B · es-MX · a mano (12-nov) | — | — | separada de modelar-y-lanzar-oferta |

## 0.3.0 · 2026-11-14
- Regla R3b del dueño: backend anticipado. Con ventas en el test y el corte imposible antes del cierre, se arma ya con los embudos pausados y se prende al cierre del test (`vigilar_corte.py` → `backend_anticipado`; `hay_trabajo.py` paso 6). Primera vez: Oferta F (España).
- Guía 02: el backend entero con el conector de Impultienda, sin panel (embudo que nace activo, descuentos, saltos, HTML propio, agradecimiento).
- Producción de los 3 PDF en paralelo con un agente por producto, sobre la maqueta de la oferta (`04-producto/maqueta/render.py`, piezas U01-U03).
- Objetivo de ingreso por comprador ≥ 1,5 × el ticket (dueño, 14-nov), con benchmarks de 2026 y el order bump como palanca (guía 01).

- Guía 01: cómo se presenta el bump (nombre con el formato, descripción que abre con el problema, botón en primera persona, imagen con la pieza rellenada). Salió de Oferta F: «Kit para montar tu carpeta en papel» sonaba a producto físico.
