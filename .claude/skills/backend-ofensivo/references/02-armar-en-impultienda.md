# Armar el backend en Impultienda

Movido aquí el 2026-11-13 desde `modelar-y-lanzar-oferta/references/11-ofertas-que-suben-el-ticket.md` (texto sin cambios salvo el título). Primera vez: Oferta B, 2026-11-12.

## Pasos

Se arma **después del test**, cuando el principal ya vende. Plan y razonamiento en `ofertas/_borrador-oferta-b/09-backend/plan.md`; páginas en `09-backend/landings/`.

**Productos.** Complementos que el kit no trae (un formato nuevo, temas nuevos, algo para un tercero). Nunca repetir el principal ni sus bonus. Precio contra el mercado de un producto parecido, no contra el principal: la primera oferta puede costar más que el principal ([[precio-de-upsells-post-compra]]).

**Cupos.** (Desde el 15-nov, plan Unlimited: sin límite; comprobar con `impultienda_ver_plan`.) Antes, plan Max: 3 upsells y 5 bonos por tienda, en cupos separados («Agregar upsell (n/3)»). El complemento del checkout (bump) gasta un cupo de upsell. Si la oferta usa varias tiendas (niveles, subida previa), **las tres llevan los mismos upsells**, cada una con su embudo.

**Cargar un upsell.** «Diseño de ebooks» → «Agregar upsell»: nombre, descripción, precio USD (escribirlo con teclado), interruptor «Disponible solo en post-compra». Después «Precio, título y más» → «Precios por mercado» → precio MXN con teclado (el setter de JS no se guarda en ese campo). PDF e imagen por los `input[type=file]` de la tarjeta; si queda en «Subiendo…», recargar: suele estar «Listo».

**Embudo.** `/marketing/post-compra` → «Nuevo funnel» → «Disparar siempre» (una tienda = un principal). Se prearma con los 3 upsells (15/20/25 % de descuento), 3 rebajas (40/45/50 %) y un reloj de 10 min. Hay que:
1. En cada oferta: «HTML propio» y pegar la página (contenido sin `<html>`; botones `data-pp-accept` / `data-pp-decline`; tokens `{price}`, `{compare}`, `{product-image}`, `{first-name}`…). La plantilla por defecto dice «¡ESPERA! TU PEDIDO NO ESTÁ COMPLETO» con contador: no usarla.
2. «Descuento»: solo admite porcentaje con varias monedas. Upsell sin descuento = tipo «—» **y** valor 0 (si queda el número, la tarjeta muestra «$15 Off»). Rebaja a precio exacto: porcentaje con decimales (399→249 = 37,594 %; 349→229 = 34,384 %); con 37,6 sale «MXN 248,98».
3. Conectar las ramas de cada rebaja (acepte o no) a la oferta siguiente con «Conectar a una existente…»; si no, el embudo termina ahí. Borrar la rebaja que sobra.
4. Página de agradecimiento: viene con voseo («Revisá tu bandeja»); cambiar título y mensaje y apagar el aviso. «Descargá tus productos ahora» no se puede cambiar.
5. «Compartir demo» → recorrer todas las ramas en móvil (no cobra ni suma estadísticas).
6. **Activar al terminar** («Pausado» → «Activo») en el embudo de cada tienda, recargar y comprobar. Regla del dueño (2026-11-13): el backend ofensivo siempre queda activo después de crearlo. El cambio de estado se guarda solo; el resto de las pantallas, con su «Guardar».
7. **Anotarlo en el libro de tests**: campo `backend` del test con estado, desde, upsells con precio en USD, tiendas y nota (formato en `escalar-oferta/references/01-revision-diaria.md`). El panel muestra con eso la «B» de backend de cada oferta; sin el campo la oferta figura «Sin backend».

**Editor.** El panel se ve mal en el ancho del navegador integrado (la barra lateral tapa el editor): emular 1440×900 y volver a «desktop» al terminar.

## Sesión vencida (S37)

Si el navegador pide iniciar sesión en Impultienda o en Facebook: no iniciarla por el dueño. `python3 .claude/skills/escalar-oferta/scripts/avisos.py avisar sesion-<sitio> --mensaje "La sesión de <sitio> está vencida: abrila en el navegador de Claude" --urgente` y, si imprime `ENVIAR`, notificación. Seguir con lo que no necesite esa sesión. Si PushNotification responde «not sent» (p. ej. «Remote Control inactive»), correr `python3 .claude/skills/escalar-oferta/scripts/avisos.py no-llego <clave> --motivo "…"`: el aviso vuelve a salir en la próxima vuelta y el panel lo muestra como no entregado.

## Escribir el libro de tests

Solo con `python3 .claude/skills/escalar-oferta/scripts/libro.py` (`set`, `append`, `merge`, `nuevo-test`): toma un candado y guarda copia previa. Nunca a mano: otra tarea puede estar escribiéndolo al mismo tiempo (S38).

## Con el conector de Impultienda (desde el 14-nov, Oferta F): sin panel

Todo el backend se puede armar con las herramientas `impultienda_*`, sin abrir el panel:

1. **Productos:** `impultienda_crear_producto` (tipo upsell, `solo_post_compra: true`, precio USD) en cada tienda; precio del mercado con `impultienda_precio_por_pais` (vista previa + confirmar); PDF con `impultienda_cargar_entregable` (subir → `curl -X PUT` → confirmar); imagen con `impultienda_editar_producto` (imagen subir → PUT → confirmar).
2. **Embudo:** `impultienda_crear_funnel_postcompra` modo «siempre». **Lo crea ACTIVO**: si el backend es anticipado (R3b), pausarlo en la llamada siguiente con `impultienda_alternar_funnel_postcompra` y comprobar con `impultienda_listar_ventas` que no entró ninguna venta post-compra en esos segundos.
3. **Descuentos:** `impultienda_modificar_oferta_postcompra` con `funnel_id` (si está pausado no hay «activo» por defecto): upsell `descuento_pct: 0`; rebaja al % exacto sobre el precio del mercado (27→17 € = 37,04 %).
4. **Saltos:** las rebajas vienen terminando el embudo; `impultienda_conectar_oferta_postcompra` las une a la oferta siguiente en las dos ramas. La rebaja de la última oferta no se puede borrar con el conector (solo en el panel): se le pone precio y página, o se borra a mano.
5. **Páginas:** HTML propio con `impultienda_guardar_html_postcompra` (vista previa + confirmar con los MISMOS argumentos) y `impultienda_alternar_html_postcompra` para prenderlo. Minificar y dejar en cada página solo el CSS que usa (las rebajas bajan de 14 a 8 KB). Las imágenes van a Recursos con la API de `impultienda_link_subida_recursos` y se usan con el dominio `sb.impultienda.ar` (aprobado). Son 18 publicaciones de ~25 KB para 3 tiendas: repartirlas en un agente por tienda.
6. **Agradecimiento:** `impultienda_configurar_agradecimiento` (título, mensaje con `{email}`, `mostrar_aviso_casilla: false`, que viene con voseo).
