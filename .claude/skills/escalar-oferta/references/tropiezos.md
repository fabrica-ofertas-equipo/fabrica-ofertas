# Tropiezos después del lanzamiento

Lo que falló al revisar, decidir y escalar ofertas ya lanzadas, y su salida. Lo de antes del lanzamiento está en `modelar-y-lanzar-oferta/references/tropiezos.md`.

## Revisión de los funnels en marcha (2026-11-12, 9 h de pauta en México)

| Qué pasó | Salida |
|---|---|
| Las pruebas automáticas cargaron landings y checkouts reales con el píxel activo: 6 InitiateCheckout y eventos del quiz falsos en los píxeles de las tiendas | `scripts/probar_funnel.py` bloquea `facebook.com/tr` y `connect.facebook.net` por defecto. Leer las estadísticas de la tienda **antes** de probar, porque las visitas sí cuentan |
| «Imágenes rotas» 14 de 16 en una landing sana | Eran de carga diferida sin cargar todavía. Contar las rotas recién después de recorrer la página entera |
| El checkout salió en español y en US$ para la tienda de Brasil | Precio, moneda e idioma los decide la IP (Argentina). Lo que ve el comprador se comprueba con «Ver como otro país» en Diseño de checkout, bajando con la rueda sobre la vista previa |
| La compra de Oferta B no estaba en el píxel ni en Meta al leer | El Purchase llegó al píxel unos 20 min después. Meta siguió sin atribuirla: falta el token de la API de conversiones (lo genera el dueño en Events Manager) |
| 10 checkouts, 2 compras y 0 carritos abandonados | Impultienda registra el abandono solo cuando se escribe el correo: los que se van, se van al ver el checkout, antes de tocar nada. Para saber por qué: Microsoft Clarity (Configuración → Meta / Tracking) |
| Solo el 63-66 % de los clics llega a cargar la landing | Servidor de Impultienda 1,3-2,1 s y pintado principal 2,6-4,2 s en 4G. Lo nuestro es la primera pantalla: imagen principal liviana |
| Las dos ventas de Oferta A vinieron de anuncios a docentes; la landing le habla a padres | Comparar siempre los anuncios que venden con la promesa de la landing en la revisión |
| El contador «N personas están comprando ahora mismo» mostró 1, 2 y 6 en una tienda sin tráfico | Es configuración del checkout del dueño: no se toca, se informa como «no es dato real» |
| No había un registro de cuánto costó cada test | `ofertas/_funnels/libro-de-tests.json` + `scripts/libro_de_tests.py`; los créditos salen del `estado.md` de cada oferta |

## Lo que enseñaron las primeras ventas (2026-11-12, ~17 h de pauta en México)

| Qué pasó | Salida |
|---|---|
| La landing de Oferta B volvió dos veces sola a una versión vieja a los ~2 min de publicar: había otro Chrome (`--remote-debugging-port=9222`) con el editor abierto que volvía a guardar | Después de publicar, comprobar la huella de la página pública otra vez a los 3-5 minutos. Si vuelve a cambiar, no pelear: avisar al dueño qué proceso la está pisando |
| Museo: 15,9 % de visitas a checkout (bien) pero 9,5 % de checkout a compra (mal); Sesión: 28,6 % | Con < 30 checkouts es pista. Mirar qué difiere en el checkout (precio tachado, contador, campos) antes de tocar la landing (`01-revision-diaria.md` §4; antes `12-revision-dia-siguiente.md`, que ya no existe) |
| Las ventas de Museo vinieron de anuncios a docentes; la landing hablaba a padres | `07-landing.md` §4.1 y `08-creativos.md` §1.2 |
| Un tercio de los clics no llegó a ver la landing | Primera pantalla liviana: `07-landing.md` §4.1 |
| Ganó el anuncio más corto con gancho de oficio y producto a los 15 s | `08-creativos.md` §1.2 |
| Meta rechaza activar un conjunto con mínimo de gasto mayor que lo que queda del presupuesto del día | `03-renovar-creativos-y-escalar.md` paso 6 (antes `12-revision-dia-siguiente.md` §8.5, que ya no existe) |

## Renovación de creativos de Oferta B (2026-11-12 noche)

| Qué pasó | Salida |
|---|---|
| Meta rechazó activar el conjunto nuevo: «Minimum Spend Limit Is Higher Than Campaign Budget» con 13 USD de mínimo y 50 de presupuesto | Compara el mínimo con lo que queda del presupuesto del día, no con el total. Activar los anuncios (entran en revisión) y el conjunto a las 00:00, después de subir el presupuesto |
| La miniatura automática de Meta sale de 160 px | Subir una miniatura propia (primer cuadro, 1080×1920) con `ads_create_upload_url` + `ads_finalize_upload` y usar `image_hash` |
| Dos aperturas generadas traían el marco de un celular o la interfaz de la cámara | Mirar el primer cuadro antes de generar el clip; agregar al prompt «no phone frame, no camera-app interface» |
| Los cambios de las 00:00 dependen de que la sesión siga abierta (CronCreate vive en la sesión) | Decirle al dueño; si la sesión se cerró, hacerlo a mano a la mañana y anotar la hora real |
| Al subir el presupuesto de la CBO con `ads_update_entity`, la herramienta pausó la campaña («status_forced_to_paused»); se reactivó a los segundos (Oferta F, 15-nov) | **Prohibido desde el 15-nov** (dueño: «no puedes apagarla y prenderla el mismo día, la puede romper»). Presupuesto, mínimos y cualquier edición de algo activo van por el Administrador de anuncios (`08-cambios-en-meta-sin-pausa.md`); el hook `.claude/hooks/meta_sin_pausa.py` frena `ads_update_entity` salvo para pausar |
| A las 00:00, con 65 USD de presupuesto y 53,64 restantes, Meta siguió rechazando el conjunto con mínimo de 13 y de 10 USD por API | El mínimo de gasto por conjunto en CBO no se pudo activar por API y quedó como pendiente del dueño, que lo puso a mano (20 %) y publicó el 13-nov a la mañana. **Regla desde entonces:** el agente lo pone en el Administrador de anuncios (valores porcentuales, mínimo diario promedio 20 %, Publicar) y lo comprueba por API (`03-renovar-creativos-y-escalar.md` paso 6). Nunca dejarlo pendiente |

## Vigilancia y revisión del 13-nov (09:00)

| Qué pasó | Salida |
|---|---|
| `__stats` en un bucle sobre varias tiendas (pushState sin recargar) devolvió el embudo de una tienda con el nombre de otra y falló en la primera lectura de «Ayer» | Una tienda por vez: `navigate` a `/dashboard/<slug>/estadisticas`, esperar el selector de período y recién ahí elegir el rango. Comprobar que `location.pathname` coincide con la tienda leída |
| Después de pausar, Meta siguió sumando gasto atrasado: US$ 0,61 en Caminho y US$ 2,40 en El Museo | El gasto final se relee en la revisión siguiente y va al libro (`apagado.gasto_final_usd`, `meta`). El corte se dispara con lo que se ve; el atraso suma ~3-4 % |
| Oferta D quedó «programado» con un inicio del 13-nov que ya no valía: el conjunto se reemplazó por otro del 14-nov y la ficha no tenía `tiendas` → `SIN_PRECIO` | Al reemplazar un conjunto de una oferta programada, actualizar `inicio` y la `ficha` (tiendas con precio en USD, píxel, campañas) del libro en la misma sesión. La vigilancia, si ve un programado sin gasto, compara con el `start_time` del conjunto que entrega |
| Un conjunto de renovación con mínimo de gasto de 13 USD gastó US$ 0,15 en las primeras 6 horas | No es falla: Meta reparte el mínimo en el día. Mirarlo a media tarde antes de tocar nada |

## Renovación diaria R4 (2026-11-13)

| Qué pasó | Salida |
|---|---|
| La vuelta de las 10:30 produjo todo, subió los videos a Meta y se cortó; además dejó en el Administrador un **borrador** (conjunto R4 + 10 anuncios con errores), porque la herramienta de Meta crea en modo borrador cuando está habilitado | Al retomar (05 §0b), buscar los videos por título con `ads_get_ad_videos` antes de subir. Si el Administrador muestra «Revisar y publicar (N)» con objetos que no son tuyos o están duplicados, **no usar el «Publicar» del editor**: abrir «Revisar y publicar» en la tabla y dejar marcado solo el cambio propio |
| El 20 % puesto en el Administrador se «publicó» («Se actualizó 1 conjunto») pero el conjunto quedó con «Ningún límite agregado» y sin `daily_min_spend_target` | Con la CBO casi gastada en el día (1,41 USD de 45,5) Meta lo descarta en silencio. Comprobar siempre por API y en el editor; si no quedó, `minimo_pendiente: true` |

## Repaso del 14-nov (noche)

| Qué pasó | Salida |
|---|---|
| Oferta H y Oferta I (réplicas) salieron con el píxel de Oferta F y Mon Carnet con el de Oferta E; gastaron US$ 34 aprendiendo de compradores de otra oferta | Píxel propio por oferta, réplicas incluidas; conjuntos nuevos con el píxel nuevo y los viejos en pausa; `control_previo.py` frena |
| El mínimo del 20 % de la R4 de Oferta B nunca se puso | `hay_trabajo.py` mira `renovaciones[].minimo_pendiente` |
| Avisos urgentes (fan page, píxel de Balloon) no llegaron al celular: «Remote Control inactive» | `avisos.py no-llego` + `sin-entregar`; falta un canal que no dependa del Control remoto |
| Oferta J armada para Singapur: Meta exige anunciante verificado | `elegir_mercado.py` excluye esos 6 países sin verificación |
| La Mac durmió de 23:05 a 08:43 y se reinició a las 08:37 y a las 16:57; después del reinicio los conectores quedaron «pending» hasta `/mcp` | Ninguna tarea corre con la Mac dormida o trabada: ajuste de energía y canal en la nube (pendiente del dueño) |
| 15-nov: la vigilancia no corrió de 02:06 a 09:54 ART (todas las tareas volvieron a las 09:49); en ese hueco Oferta H y Oferta I pasaron de US$ 31-37 a 125-144 con corte en 81 | Mismo origen que la Mac dormida: sin la regla de respaldo en Meta (2 tickets sin compras, propuesta) un test de 162 USD/día se pasa del corte en pocas horas. Apagadas al despertar |
| 15-nov: `libro_de_tests.py` se caía con tests programados sin `meta`, y el panel (`negocio.py`) con `ficha.campanas[].anuncios` como número (Oferta L: `anuncios: 10`) | Los dos scripts ahora toleran el faltante; la cantidad de anuncios va en `anuncios_cantidad`, `anuncios` es siempre una lista |

- **2026-11-15 · El libro contaba los upsells como ventas.** `libro_de_tests.py` dividía por todas las filas de `ventas` (17 principales + 3 upsells = 20): CPA 19,28 y equilibrio 39,31 en Oferta F, cuando eran 22,71 y 46,24. Corregido: compradores = filas sin `tipo` upsell/bump/downsell (igual en `elegir_mercado.py`). Además, para decidir el día mirar CPA y AOV **de hoy** (tienda + Meta), no el acumulado del libro.

## 2026-11-15 · réplicas IE/NZ de Oferta F
- Impultienda empezó a pedir el celular del dueño («Agregá tu celular») antes de entrar al panel: frena duplicar tiendas, píxel e Impul Pay. Es dato del dueño: pedírselo apenas aparece. El conector MCP sigue andando mientras tanto (idioma, moneda, mercados, precios, PDF).
- Los subagentes NO deben usar el navegador integrado: uno navegó la pestaña de la sesión y cortó una copia de tienda. Decirlo en cada encargo.
- El token CAPI se pega UNA vez (tienda principal) y se copia a las demás con `impultienda_configurar_tracking` pixel_de_otra_tienda=true; Meta lo valida en el acto.
- vigilar_corte.py ahora acepta `corte_tickets` por campaña en ficha.campanas (pocket 1, variaciones 1,5) y devuelve APAGAR_CAMPANA.
- Una sesión cortada deja MP4 a medio escribir («moov atom not found»): comprobar con ffprobe antes de subir.

- 2026-11-15 · **Réplicas: los creativos nuevos van con el ambiente del país.** Oferta/NZ salió con los videos que muestran las cocinas de España (error que marcó el dueño; detalle en `modelar-y-lanzar-oferta/references/tropiezos.md`, «Réplica Oferta + NZ»). En cada renovación (R9) o iteración de una réplica, los keyframes y clips nuevos se generan con el ambiente del país (prompt de `05-landing/assets/fotos_kie_pais.py` de la oferta) y no se reusan planos de la madre con la casa a la vista. Revisar ampliadas las portadas y páginas: Nano Banana arrastra el texto del idioma de la madre.

- 2026-11-15 · **Ofertas con varias campañas (pocket, variaciones): el gasto por día tiene que sumar todas.** `historial_meta.py` solo tomaba `campana` del test y dejaba afuera las de `ficha.campanas` (Oferta F: US$ 36,83 de las B08 sin cargar en el panel); `corte_post_test.py` armaba el gasto del día con un dict y se quedaba con la última fila (leyó US$ 12,76 en vez de 384). Arreglados los dos en la vuelta de las 20:58: `historial_meta.campanas()` suma `ficha.campanas` y R4b suma todas las filas del día.

## Renovación R5 de Oferta F (2026-11-16)
- **La R4 del 15-nov quedó «produciendo» un día entero** (3 de 10 videos, sin subir) y `ofertas_que_pegan.py` pasó a la R5 como si la R4 existiera. Al empezar una ronda, mirar si la anterior sigue en `produciendo` con `inicio` vencido: marcarla `cancelada` con su nota y sumar sus créditos al libro (los 1.428 de la R4 no estaban en `produccion`).
- **Meta aceptó los límites por API** (`daily_min_spend_target` 2680 y `daily_spend_cap` 5360 en centavos) al **crear** el conjunto con `start_time` futuro, y la API los devuelve (26,8 y 53,6 USD). El rechazo de antes era al editar o con el presupuesto del día casi gastado. Pero quedan como **montos fijos**: el editor del conjunto los muestra como texto, sin opción de pasarlos a porcentaje, y no siguen solos al presupuesto si la vigilancia lo sube o lo baja. La vigilancia que cambie la CBO tiene que revisar los límites de los conjuntos con límites (deberían seguir siendo 10 % y 20 %).
- En el editor del conjunto en el panel chico, un clic fuera de lugar abrió «Usar un público guardado»; Escape cerró el editor entero sin dejar borrador («Revisar y publicar» gris). Comprobarlo siempre después de tocar algo.
- Nano Banana escribió «Savings Passbook» y «Bank Book» en inglés en fotos de España: en el prompt de planos con papeles, pedir «solo letra pequeña ilegible o palabras en español, nada en inglés». Rehechas Z5 y Z7.
- Las imágenes casi no reciben entrega en la CBO (las 7 del lanzamiento, 12 USD en 4 días); el conjunto nuevo lleva mínimo, pero dentro del conjunto Meta puede seguir eligiendo los videos.

## Vigilancia del 17-nov (11:35)

- **Corte por campaña con Meta subatribuyendo:** `vigilar_corte.py` (`cortes_por_campana`) cuenta solo `compras_meta` de cada campaña. En Oferta, Meta dio 1 compra a variaciones y la tienda tenía 2, ambas con `utm_campaign=uk-cbo-variaciones-b08`: el script pedía pausar (98,84 ≥ 81) y con 2 ventas el corte era 162. Antes de pausar una campaña por APAGAR_CAMPANA, leer `impultienda_campanas_utm` (nivel campaña, hoy) de cada tienda y, si la tienda tiene más ventas de esa campaña, volver a correr con `compras_meta` corregido. Pendiente: que el script lo tome de la lectura (`ventas_por_campana`).
- **Borradores ajenos en el Administrador:** «Revisar y publicar (2)» traía dos anuncios nuevos de otra tarea con errores. Para cambiar presupuestos sin publicarlos, usar la edición de cada campaña (`/adsmanager/manage/campaigns/edit/standalone?act=…&selected_campaign_ids=<id>`): su «Publicar» publica solo esa campaña («Se actualizó 1 campaña») y los borradores ajenos quedan.
- En esa edición, el campo de presupuesto se encuentra con `find "Ingresa un importe"`; tras escribir y Tab, el borrador tarda 2-3 s en guardarse y recién ahí se habilita «Publicar».
- **Límites fijos al bajar una CBO:** al bajar Oferta F de 187 a 162, el conjunto R5 quedó con 26,8 / 53,6 USD (16,5 % y 33 %). En el editor del conjunto los límites aparecen como texto en una sección oculta; no se encontró el campo. Queda en `pendientes` del libro.
- **Sin sesión de Impultienda en el navegador integrado** (17-nov 11:58): el cierre R15 no pudo archivar Oferta E ni Oferta D. Se dejó `cierre.intentos` y aviso urgente; no se inicia sesión por el dueño.
- **Renovación R7 por copias en el Administrador (17-nov):** el conector sigue sin permiso de anunciante en la página de Oferta F (`ads_create_ad` 1885499, `ads_create_creative` 3858749); los anuncios se arman en el Administrador. Copiar y pegar en la tabla eligió un borrador ajeno: no usarlo. Lo que funcionó: crear el primero a mano y duplicarlo 9 veces; en cada copia (1) «Eliminar contenido multimedia» y «Agregar video», (2) el texto principal se borra con clic + `alt+Backspace` ×200 y `alt+Delete` ×200 (en Lexical `cmd+a` no sirve y concatena), (3) el botón vuelve a «Ver detalles»: elegir «Más información» por ref, (4) en las copias el campo URL está oculto, así que **todas heredan el utm_content del original** (r7-c09). Próxima vez: poner en el original `utm_content={{ad.name}}` antes de duplicar. Verificar por API con `ads_get_creatives` (body, title, LEARN_MORE y `object_story_spec.video_data.video_id`).
- **nube_sync anota sola las campañas nuevas** en `ficha.campanas` a los minutos de crearlas: antes de hacer `append`, leer la lista y completar la entrada que ya está (si no, queda duplicada, como la pocket D1 el 17-nov).
