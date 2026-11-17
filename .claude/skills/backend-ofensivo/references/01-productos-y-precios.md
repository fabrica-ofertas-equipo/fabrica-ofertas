# Fase 1 · Elegir los productos y sus precios

Modelo: `ofertas/_borrador-oferta-b/09-backend/plan.md` (Oferta B, 2026-11-12, versión 2 tras la corrección del dueño).

## De dónde salen los productos

1. **Quién compró y qué dijo.** Las ventas del día 1 (nivel, ticket promedio) y la guía de voz del mercado (`02-validacion/inmersion/`): las citas que hablan de un problema que el producto principal no resuelve.
2. **Qué ya trae el principal.** Lista de lo que incluye el producto y sus bonus. Ningún upsell lo repite.
3. **Tres huecos distintos**, cada uno con su cita. Tipos que funcionaron:
   - un **formato nuevo** del mismo tema (juegos imprimibles para un kit de hojas);
   - **temas nuevos** que no entran en las áreas del principal;
   - algo **para un tercero** (hojas para los papás de un kit para el profesional).
4. **Orden:** primero el de más valor percibido y más amplio; el último, el más chico.

## Objetivo: ingreso por comprador ≥ 1,5 × el ticket (dueño, 14-nov)

«Tenemos que estimar 1,5 y de ahí sacar los precios.» El ingreso por comprador (principal + bump + ofertas post-compra cobradas) ÷ ticket promedio del principal tiene que dar **1,5** en la estimación calibrada.

**De dónde sale (investigado el 14-nov, fuentes de 2026):**
- Medido en el mismo modelo (low ticket, Meta, Impultienda): Santiago Bilbao 1,44× con 3 ofertas post-compra y rebajas (meta 1,5); Matías Bonardo ~2× con bump + upsells; su alumno 1,6×; Juan Pablo Mentor +48 % entre dos tiendas.
- Casos medidos de embudos digitales con Meta en frío: **1.ª oferta post-compra 2-7 %**; **order bump 40-80 %** a 0,5-0,7× el principal. Las tasas de 20-35 % que repiten los blogs no tienen respaldo.
- Nadie publica aceptación por oferta en español: se calibra con lo medido por Bilbao (k = 1 en `backend_modelo.py` del 14-nov) y se muestran también los escenarios medio (k 0,7) y conservador (k 0,4).

**Cómo se arma para llegar a 1,5:**
1. 1.ª oferta post-compra a **≈ 1 × el ticket promedio** (Bilbao), sin tachado; rebaja ~38-40 %.
2. 2.ª oferta a ≈ 0,7 ×; rebaja ~37 %.
3. Un **order bump propio** en el checkout (≈ 0,2-0,3 × el ticket, 10-30 % según las guías), que **no** sea ninguna de las ofertas post-pago: si lo fuera, quien no lo tilda la vuelve a ver después del pago y se pierde un upsell distinto (dueño, 14-nov). Criterio: pegado al principal, que ahorre tiempo o ayude a usarlo el mismo día (plantillas, listas, kit de inicio, la versión «para tener en la mano»), sin pisar el tema de ningún upsell. Se carga como upsell con «solo post-compra» apagado; si es backend anticipado (R3b), se crea marcado y se prende al cierre del test (`backend.bump_al_activar`).
   **Cómo se presenta el bump** (dueño, 14-nov: «¿es un producto físico? … la misma duda puede tener el comprador»). En el checkout se lee en dos segundos y la descripción se corta a pocas líneas:
   - El **nombre dice qué es y el formato**: lo que le sirve a casi todos primero y «(PDF)» al final. Nada que suene a envío («kit para montar», «pack», «set») sin decir que es un PDF.
   - La **descripción abre con el problema** que resuelve, dice «PDF para imprimir en casa» (o «para rellenar en pantalla») en la segunda frase, cuenta lo que trae con números y el tiempo que lleva usarlo. Lo que sirve solo a una parte de los compradores va como opcional («si la guardas en papel…»).
   - **Botón en primera persona** (`impultienda_configurar_checkout` → `texto_boton_bump`), p. ej. «Sí, lo añado a mi pedido».
   - **Imagen:** la pieza más útil rellenada con un ejemplo (letra a mano), no una hoja suelta que parezca papelería, con un rótulo del formato. Sin precio tachado ni reloj.
   - La portada del PDF lleva el mismo nombre que el producto.
4. Vigilar: si con el bump el paso checkout → compra cae más de 5 puntos, se saca. Ajustar con la analítica (usar «Cobradas», no «Aceptadas») con 100-200 vistas por oferta.

Primera vez: Oferta F, 14-nov: 39/24 €, 27/17 €, 14/9 € + bump propio «Tarjeta «Si me pasa algo» + kit para tu carpeta (PDF)» a 9 € (primero se llamó «Kit para montar tu carpeta en papel» y se cambió porque sonaba a producto físico) → 1,53 estimado (Bilbao), 1,39 medio.

## Precios

- **Contra el mercado** de productos parecidos en ese país (citar fuentes), no contra el principal. El principal es una oferta de entrada: no mide cuánto paga el comprador.
- **Primera oferta:** igual o más que el principal está bien. Lo que importa es precio × aceptación.
- **Rebaja si rechaza:** la misma oferta un 35-40 % más barata. La última oferta puede ir sin rebaja.
- En USD y en moneda local, terminados como los precios del mercado.

Referencia (Oferta B, principal MX$ 319 en ese momento; desde el 12-nov el principal cuesta MX$ 359 por la regla 19/27, que no rige para los upsells): Juegos MX$ 399 → rebaja 249; Temas 349 → 229; Papás 249 sin rebaja. Estimado: ticket promedio de MX$ 269 a ≈ MX$ 390 (+45 %), con aceptaciones supuestas.

## Cupos (plan Max de Impultienda)

> **Desde el 15-nov la cuenta está en plan Unlimited** (`impultienda_ver_plan`: upsells y bonos por tienda y por embudo ilimitados). Lo de abajo queda como historia: ya no limita.

- 3 upsells y 5 bonos por tienda, en cupos separados. El complemento del checkout (bump) ocupa un cupo de upsell.
- Si una tienda ya usa un cupo en el bump, se quita el bump o se ofrecen dos upsells en esa tienda. La primera vez lo decidió el dueño; desde ahora: **si el bump repite una oferta que ya está en la subida previa, se quita; si no, se deja y la tienda lleva dos upsells.**

## Qué queda escrito

`ofertas/_borrador-<slug>/09-backend/plan.md` con: de dónde parte (ventas, ticket), los 3 productos con su hueco y cita, precios y rebajas, el embudo de cada tienda dibujado, la producción y el estimado marcado como supuesto.

## Precio por nivel y mejora a la Completa (dueño, 16-nov: «tiene mucho más sentido»)

Cuando el funnel tiene niveles (Esencial / Familiar / Completa), los upsells NO cuestan lo mismo en todas las tiendas:

1. **El precio del upsell sigue al precio de entrada.** En la tienda de la Completa se cobra el precio pleno; en las de nivel bajo, el mismo upsell en proporción a lo que pagó el comprador (precio pleno × entrada del nivel ÷ entrada de la Completa, redondeado), con piso de 7 € (o el precio del bump más barato). Ejemplo IE: Completa 59 € → upsells 49/35/24/19; Family 35 € → 29/21/14/12; Essential 19 € → 16/12/9/9. Ejemplo ES: Completa 49 € → 39/27/14; Familiar 29 € → 23/16/9; Esencial 19 € → 15/11/7.
   *Por qué:* en Oferta F tomaron upsell 15 de 25 compradores de la Completa y 1 de 15 de los niveles bajos: el primer upsell costaba más que lo que había pagado el comprador barato.
2. **En las tiendas de nivel bajo, la primera oferta es «pasar a la Completa» a mitad de la diferencia, mostrando la diferencia tachada.** Producto upsell solo post-compra con un PDF que une las piezas que le faltan al nivel (Familiar: 8-12; Esencial: 4-12) y portada «Tu paso a la Completa»; precio fijo del mercado = la diferencia entera; la oferta lleva −50 % (así Impultienda muestra la diferencia tachada) y su rebaja −65 %. Texto: «Si hubieras elegido la Completa desde el principio, habrías pagado X más. Ahora, solo aquí, por la mitad: Y». La tienda de la Completa no la tiene.
3. **Orden en las tiendas de nivel bajo:** mejora → upsell 2 → upsell 1 → el resto en la cola. **Nunca se reordena una oferta que ya está testeada y vende** (dueño, 16-nov: «si algo ya está funcionando, ¿por qué lo cambiaríamos?»): el intercambio de lugares (`impultienda_reordenar_oferta_postcompra`) solo se usa cuando las ofertas que se mueven no tienen ventas (por ejemplo, una réplica en su día 1).
   - **Toda oferta nueva va a la cola** (`impultienda_agregar_oferta_postcompra` la cuelga del «acepta» de la última) **y se conecta**: las dos ramas (acepta y rechaza) de la rebaja que antes terminaba se apuntan al upsell nuevo con `impultienda_conectar_oferta_postcompra` (es el «Conectar a una existente…» del editor). Así la ven todos los compradores, aceptaran o no lo anterior, y lo testeado no se toca.
   - **Precio en la cola:** la oferta va a precio lleno del nivel (descuento 0 %) y su rebaja a −35,71 %; el agregado hereda los descuentos del lugar (30/55 % o 35/60 %) y hay que corregirlos con `impultienda_modificar_oferta_postcompra`.
   - **Comprobar** con `impultienda_ver_postcompra` que ninguna rebaja intermedia quede en «termina» antes del último upsell.
   - *Lección (16-nov):* antes de afirmar que la plataforma «no puede» algo, consultar `impultienda_faq` y la lista de herramientas: se dijo que solo se podía reordenar y existía la conexión de ramas.
4. **Los precios van por mercado** (`impultienda_precio_por_pais`): la oferta post-compra cobra el precio fijo del mercado de la compra, con el descuento de la oferta encima.
5. **Medir por nivel:** la toma de upsells se mira separada por tienda (nivel); una oferta que no vende en la Completa no se juzga con los compradores del nivel bajo, ni al revés.
