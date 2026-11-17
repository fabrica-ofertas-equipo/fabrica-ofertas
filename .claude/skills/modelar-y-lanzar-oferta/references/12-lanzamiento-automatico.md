# Lanzamiento automático (reglas L3, L5 y E6 del dueño, firmadas el 2026-11-13)

Dueño: 2 ofertas nuevas por día, solas; la campaña se activa sola si pasa el control previo, «siempre 00 del mercado que estamos lanzando, por zona horaria». Anuncios rechazados (16-nov): solo se apelan una vez, nunca se reemplazan ni rehacen; la campaña sale con los que quedan, y una pocket 1-1-1 con su único anuncio rechazado no sale. Una oferta que gana una semana (ROAS neto ≥ 1,30) se replica en otro mercado.

Corre con la tarea programada **«lanzar-ofertas»** (06:00 y 13:00 de Argentina). Cada vuelta lanza **una** oferta como mucho.

## 1. ¿Toca lanzar?

```bash
python3 .claude/skills/modelar-y-lanzar-oferta/scripts/cupo_lanzamiento.py --json
```

- `ESPERAR` → terminar la vuelta con el motivo. Solo sale por tope: ya salieron 2 hoy o hay 8 en test. **Nunca se espera por el banco.**
- `LANZAR_REPLICA` → §3.
- `LANZAR_NUEVA` → §2 (alcanza con 1 listo; si `reponer_banco` es true, el radar y buscar-ofertas reponen la reserva de 3).
- `BUSCAR_Y_LANZAR` → §1b y después §2.

### 1b. Banco sin listos: buscar en la misma vuelta

Dueño (14-nov): «el sistema siempre tiene que tener preparadas ofertas. Hay miles de ofertas en todo el mercado… si no encontramos ninguna que esté a potencial, sigue buscando». Hasta el 14-nov la vuelta esperaba con menos de 3 listos y ese día no salió ninguna.

1. Verificar lo que el radar tiene en `a_verificar` (`radar.py pendientes --json`; guía 05-radar §1 de buscar-ofertas), exportar e importar al banco las producibles.
2. Si no aparece un listo: medir las de mayor joya de `a_medir` (`radar.py plan --json` da la cuota) y verificar las que pasen el piso (15 anuncios, 10 días).
3. Si sigue sin aparecer: barrido por forma con términos no usados (buscar-ofertas, `02-barrido-por-forma.md`), recorrer a mano los complejos, marcarlos y importarlos.
4. Apenas `banco_candidatos.py estado` muestra un listo → §2. El piso (15 anuncios, 10 días, producible, sin cara) no se baja.
5. **Dos por día, sí o sí** (dueño, 14-nov: «no puede pasar eso, tienen que salir dos ofertas por día sí o sí nuevas»). Si después de los pasos 1-3 de esta vuelta no apareció un funnel complejo, se lanza el mejor producible que pase el piso aunque sea una TSL (`ordenar_candidatos.py` con todos los producibles) y se avisa que no había complejo. Antes esto terminaba la vuelta sin lanzar (pasó el 14-nov a las 13 h).
6. **Lo que necesita al dueño no ocupa el lugar del día.** Si una oferta queda armada sin poder activarse (fan page, píxel), se avisa, queda `armado` en el libro y la misma vuelta sigue con la siguiente candidata: `cupo_lanzamiento.py` no cuenta las armadas sin salir. El píxel es propio de cada oferta y se carga por el panel en el navegador, no por el conector (que lo deja pendiente); solo si el panel también lo deja pendiente se copia a la tienda el píxel de una oferta apagada con `impultienda_configurar_tracking` (`pixel_id` + `pixel_de_otra_tienda: true`) y el conjunto usa ese dataset (`06-tienda-impultienda.md` §5).
7. Repechaje: la tarea corre también a las 17:00 de Argentina; si hasta ahí no salieron 2, lanza la que falta para la 00:00 siguiente de su mercado. Solo un bloqueo de la Biblioteca termina la vuelta sin lanzar (aviso).

## 2. Oferta nueva

1. **Elegir** con la skill `buscar-ofertas` (`references/01-elegir-del-banco.md`): volver a medir hoy los listos, medir en qué países corre el referente del primero (`paises_referente.py`, por mitades) y ponerlo en su `referente_paises`, `ordenar_candidatos.py` y tomar el primero que tenga países libres. Si el referente corre en todos los países donde podemos lanzar, queda fuera: `descartada` en el banco y se mide el siguiente (no frena la vuelta). Marcarlo `usada` en el banco apenas se elige, para que la otra vuelta del día no tome el mismo. Enseguida reservarlo en el registro compartido entre instalaciones (`buscar-ofertas/scripts/territorio.py reservar --landing … --page-id … --estado modelando`): `TOMADA` → marcarlo `descartada` y tomar el siguiente; `SIN_REGISTRO` con código 3 → no lanzar en esta vuelta. Al cerrar (paso 5), `--estado lanzada`.
2. **Fases 2 a 10 de esta skill, sin preguntar nada**: mercado con `elegir_mercado.py --medicion` (si sale con código 3, la oferta se descarta y se vuelve al paso 1 con la siguiente; si dice «REQUIERE STRIPE», Stripe se conecta en las tiendas de esta oferta y solo en ellas, `06-tienda-impultienda.md` §2b, y si no se puede ese día se vuelve a ordenar con `--sin-stripe`), desarme, inmersión, marca y píxel, producto, tienda, landing, expediente, creativos y campaña con inicio a las 00:00 del día siguiente del mercado.
3. Lo que necesita las manos del dueño **no frena el lanzamiento**:
   - token de la API de conversiones: la tienda sale con el píxel; aviso con la pantalla abierta;
   - precio «antes»: se calcula el del referente en la moneda local y se deja anotado en el aviso; el dueño lo guarda;
   - si la sesión de Impultienda o de Facebook está vencida: aviso urgente y la vuelta termina (no se inicia sesión por él).
4. **Fase 11, activar sola:**
   - probar el funnel entero sin dejar rastro: píxel, visitas y API de conversiones de Impultienda bloqueados (dueño, 14-nov): `python3 .claude/skills/escalar-oferta/scripts/verificar_funnel.py correr --oferta "<nombre en el libro>" --antes --salida <scratchpad>/verificar`; su `decision` y sus `fallas` van a la lectura del control como `"funnel": {"decision": …, "fallas": […]}`. Con `FALLA` se arregla lo que dice (imagen del producto del checkout, enlaces, landing) y se vuelve a probar;
   - armar la lectura y correr `python3 .claude/skills/escalar-oferta/scripts/control_previo.py --lectura <ruta>` (sin `funnel` en la lectura no activa; con `campana_nombre`, el nombre exacto de la campaña en Meta: si no es «PAÍS | Oferta | tipo» con la oferta y el mercado del libro, no activa: se renombra y se vuelve a correr);
   - justo antes de activar, mirar la hora otra vez: si el `start_time` ya pasó, conjunto nuevo con las 00:00 siguientes del mercado y anuncios copiados por `creative_id` (`09-campana-meta.md` §4), y volver a correr el control;
   - `ACTIVAR` → activar de arriba hacia abajo (`ads_activate_entity`), comprobar estados, aviso al dueño con `avisar`. A los 10-25 minutos de que la campaña empiece a entregar, la vigilancia vuelve a verificar el funnel con la lectura de Meta (paso 8 de `hay_trabajo.py`, punto 11 de `escalar-oferta/references/04-vigilancia.md`): no hace falta programarlo;
   - `NO_ACTIVAR` → no se activa: corregir lo que se pueda corregir solo (presupuesto, inicio) y volver a correr el control; los anuncios rechazados no se corrigen ni se reemplazan: se apelan una vez y la campaña sale con los que quedan (si no queda ninguno, no sale); si sigue sin pasar, aviso urgente con el motivo y dejarla en pausa.
5. **Cierre** (fase 12): fila en el libro de tests (`estado: programado`, tiendas con precio USD), línea en `ofertas/historial-modelado.json`, expediente y `estado.md`.

## 3. Réplica de una oferta que gana

La oferta madre ya tiene producto, landing, backend y anuncios que venden. Se lleva a otro mercado. **Regla del dueño (15-nov): en una réplica se rehace TODO para el mercado, también lo visual.** Traducir no alcanza. Errores de Oferta/NZ en `tropiezos.md`.

1. **Mercado:** `elegir_mercado.py` midiendo al referente como siempre; se excluyen los países donde la madre o el referente ya pautan. Si el idioma cambia, todo se adapta con la guía de voz del nuevo mercado (inmersión corta: 20 citas): leyes, instituciones, forma de hablar.
2. **Tienda:** duplicar la tienda de la madre (`/dashboard/duplicar-tienda`), market y moneda del país nuevo, precio por la regla 19/27 en esa moneda, píxel propio, y los mismos upsells adaptados. La copia trae rota la imagen del producto: subirla otra vez en cada tienda (`06-tienda-impultienda.md`). **Backend (bump y post-compra) prendido desde el día 1.**
3. **Producto:** el mismo, adaptado al país (no solo traducido).
4. **Inventario visual, ANTES de producir nada.** Listar cada imagen y cada plano que muestre un ambiente: casas, cocinas, ventanas, calles, objetos, papeles o personas. Entran los keyframes y clips de todos los videos, las fotos de la landing, los mockups de los packs, la imagen del producto del checkout, las páginas post-compra y las imágenes de la fan page. El criterio es el **ambiente**, no el texto: una foto sin texto también se rehace si se ve la casa de la madre. Presupuestar los créditos de Kie con ese inventario completo y producirlo antes de montar.
   - El prompt del país dice qué va (en IE: radiador, cortina de encaje, hervidor; en NZ: ventanal con jardín y cerca, heat pump, pared blanca lisa) **y qué NO va** (azulejos con dibujos, persianas de madera, moka, terracota). Script de referencia: `ofertas/_borrador-oferta/05-landing/assets/fotos_kie_pais.py`.
   - Nano Banana arrastra el idioma de la referencia: después de generar, **recortar y ampliar cada portada y cada página abierta**. Si queda texto del idioma de la madre, hacer una segunda pasada de edición con la página correcta como referencia 2 (`arreglar_texto_fotos.py`, en la misma carpeta). Regenerar desde cero suele repetir el error.
5. **Landing:** la de la madre adaptada, con los mismos bloques y las fotos del inventario. Al terminar no queda ninguna URL de la tienda madre: buscar su `store_id` en el HTML publicado tiene que dar 0. La subida a Recursos devuelve una URL `…supabase.co`; en la landing va `https://sb.impultienda.ar/…` (mismo camino).
6. **Creativos (esquema de oferta validada, memoria `replica-de-oferta-validada`):**
   - **CBO pocket 1-1-1** a 1,5 tickets: el ganador con el mismo largo, el mismo gancho y el guion casi igual. Corte a 1 ticket.
   - **CBO variaciones 1-1-10** a 3 tickets: el ganador en 4 duraciones y 6 variaciones. Corte a 1,5 tickets.
   - Voz nativa del país (Gemini TTS) y **planos con el ambiente del país** (punto 4).
7. **Fan page completa antes de activar:** foto de perfil, portada y 10 publicaciones (3 hechas y 7 programadas), con imágenes del país. No pasa a «pendientes»; sin la fan page completa no se activa.
8. **Control de réplica lista**, antes del control previo; cada punto se comprueba, no se supone:
   - inventario visual rehecho;
   - portadas y páginas revisadas ampliadas;
   - 0 URLs de la madre en la landing;
   - fan page completa;
   - backend prendido;
   - `verificar_funnel.py correr --antes` con `python3` del sistema (el `.venv` no tiene playwright).
   - `scripts/auditar_adaptacion.py` sin fallas: portada de cada tienda y título de la pestaña en el idioma y la marca del país, checkout visto desde el país, order bump, ninguna imagen de otra tienda. Además, los criterios B de `13-auditoria-de-adaptacion.md`.
9. **Campaña, control previo y activación:** como en §2.
10. En `historial-modelado.json`: `"replica_de": "<oferta madre>"`. Cuenta como uno de los 2 lanzamientos del día.

**Al corregir algo que el dueño marca en una réplica,** buscar el mismo error en todas las piezas del inventario (videos, landing, checkout, post-compra, fan page), no solo en la que señaló. Anotar en `tropiezos.md` lo que no se había contemplado.

## Avisos y latido

- Cada aviso pasa por `python3 .claude/skills/escalar-oferta/scripts/avisos.py avisar <clave> --mensaje "…" [--urgente]`; si imprime `ENVIAR`, se manda con la herramienta de notificaciones. Si PushNotification responde «not sent» (p. ej. «Remote Control inactive»), correr `python3 .claude/skills/escalar-oferta/scripts/avisos.py no-llego <clave> --motivo "…"`: el aviso vuelve a salir en la próxima vuelta y el panel lo muestra como no entregado.
- Al terminar la vuelta: `python3 .claude/skills/escalar-oferta/scripts/avisos.py latido lanzar-ofertas ok|error --detalle "…"`.

## Sesión vencida (S37)

Si el navegador pide iniciar sesión en Impultienda o en Facebook: no iniciarla por el dueño. `python3 .claude/skills/escalar-oferta/scripts/avisos.py avisar sesion-<sitio> --mensaje "La sesión de <sitio> está vencida: abrila en el navegador de Claude" --urgente` y, si imprime `ENVIAR`, notificación. Seguir con lo que no necesite esa sesión.

## Escribir el libro de tests

Solo con `python3 .claude/skills/escalar-oferta/scripts/libro.py` (`set`, `append`, `merge`, `nuevo-test`): toma un candado y guarda copia previa. Nunca a mano: otra tarea puede estar escribiéndolo al mismo tiempo (S38).
