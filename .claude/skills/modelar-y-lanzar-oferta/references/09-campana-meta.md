# Fases 10 y 11 · Campaña en Meta: crear, programar, activar y verificar

Herramientas: el conector de Meta Ads de la sesión (`ads_*`). Antes de usar una herramienta por primera vez, cargar su esquema y leerlo; los nombres de campos de abajo son los que funcionaron el 2026-11-11 y pueden cambiar. En cada llamada van `client_conversation_id` (el mismo en toda la conversación), `client_model` y `advertiser_job: create_and_launch_new_ads`.

## 0. Comprobar la cuenta antes de producir nada

`ads_get_ad_accounts` → la cuenta debe estar `account_status: ACTIVE`, `has_payment_method: true`, `is_ads_mcp_enabled: true`. Con pago pendiente Meta deja crear campaña y conjunto, pero rechaza creativos y anuncios («Ad account status is ineligible to manage ads»); en México eso tuvo la campaña parada medio día. Si no está lista, decírselo al dueño al principio: saldarla es cosa suya.

Estructura fija del dueño: un portfolio, una cuenta publicitaria, una fan page y un píxel POR OFERTA, sin cuenta de Instagram (los anuncios salen en Instagram con la identidad de la página; no hace falta conectar nada).

## 1. Estructura del test

| Nivel | Valor |
|---|---|
| Campaña | Objetivo ventas (`OUTCOME_SALES`), subasta, presupuesto diario a nivel campaña (CBO). **Presupuesto de test = 3 tickets del producto principal** (regla del dueño, 2026-11-13): precio en USD del producto principal × 3; si hay niveles (básico, completo…), se toma **el completo**. Ej.: 19 USD → 57 USD/día (`campaign_daily_budget: 5700`, en centavos); 27 USD → 81 USD/día. Si el dueño dice otro monto para una oferta, vale el suyo |
| Conjunto | Uno solo. País entero del mercado, sin intereses ni ciudades; optimización `OFFSITE_CONVERSIONS` con `promoted_object` = píxel de la oferta (el `dataset_id` de `ads_get_datasets`, nunca el número de la URL de Business) + `PURCHASE`; destino `WEBSITE`; `start_time` a las 00:00 del día siguiente en la hora del mercado |
| Anuncios | Todos los videos dentro de ese conjunto, cada uno con el título y el texto de su familia, botón «Más información», enlace a la tienda con UTM |

Nombres (**regla del dueño, 16-nov**: el sistema asigna cada campaña a su oferta por el nombre; `escalar-oferta/references/09-escala-por-campana.md` §5): campaña `<PAÍS> | <Oferta tal cual está en el libro> | <tipo>` — PAÍS = el `mercado` del test; tipo = `CBO test N videos`, `CBO pocket <ganador> (1-1-1)`, `CBO test variaciones <ganador>`, `Renovación …`, `Escala …`. Nunca otro orden ni la oferta abreviada; el control previo lo comprueba (`campana_nombre` en la lectura) · antes: `<PAÍS> | <Marca> | CBO test N videos` · `<PAÍS> | Abierto | Compra | inicio DD-mes 00:00` (sin nombre de ciudad: el dueño lo confundió con la segmentación) · `A01 | <gancho> | P<público>`.

Enlace: `https://<tienda>.impultienda.ar/?utm_source=meta&utm_medium=paid&utm_campaign=<país>-cbo-test&utm_content=A01`.

## 2. Orden de creación (todo en pausa)

1. `ads_create_campaign`.
2. `ads_create_ad_set` **con `start_time` desde el principio**, p. ej. `2026-11-12T00:00:00-0600`. Meta no deja editar la fecha de inicio de un conjunto ni de un anuncio ya creado («Start Time Can't Be Edited»): si se crea sin fecha, la única salida es otro conjunto nuevo y recrear los anuncios dentro. En México quedó por eso un conjunto duplicado «NO USAR».
3. Videos: `ads_creative_upload_media` con `upload_source: URL`, `media_type: VIDEO` y la URL temporal de `publicos.json`; esperar `ready` con `ads_get_ad_videos`. La miniatura se sube igual como imagen o se pasa por URL.
4. Anuncios: `ads_create_ad` con `creative` = `{"object_story_spec": {"page_id": …, "video_data": {"video_id": …, "image_url" o "image_hash": …, "title": …, "message": …, "link_description": …, "call_to_action": {"type": "LEARN_MORE", "value": {"link": …}}}}}`. Para poner el mismo creativo en otro conjunto: `{"creative_id": "…"}`.
5. Anotar todo en `07-campana/anuncios.json` (formato en `ejemplo-mx/07-campana/anuncios.json`): cuenta, página, píxel, campaña, conjunto, inicio programado y, por anuncio, nombre, familia, título, texto, enlace, `video_id`, `creative_id`, `ad_id`, estado.

## 3. Revisión antes de activar

| Qué | Cómo | Debe dar |
|---|---|---|
| Campaña | `ads_get_ad_entities` nivel campaña: `status, effective_status, daily_budget, objective` | En pausa, presupuesto correcto |
| Conjunto | nivel adset: `start_time, targeting, promoted_object, optimization_goal` | Inicio = 00:00 del mercado, `countries` = el país, píxel y evento correctos |
| Anuncios | nivel ad con filtro `campaign.id`: `status, effective_status, adset_id, creative_id` | Todos en el conjunto bueno, en pausa |
| Errores | `ads_get_errors` con todos los ID | Lista vacía |
| Textos | `ads_get_creatives` con `body, title, description, call_to_action_type, instagram_user_id` | Texto y título de su familia; hay identidad de Instagram |
| Destino | `ads_get_ad_preview` de uno corto y uno largo; abrir la vista previa en el navegador y buscar el dominio de la tienda en la página | Aparece la tienda; el botón dice «Más información» |
| Píxel | `ads_get_dataset_stats` del píxel, agregado por evento | Hay `PageView` e `InitiateCheckout`. Si `Purchase` está en 0, decirlo: nadie probó la compra |
| API de conversiones | En la tienda, que el campo del token CAPI tenga contenido (largo, nunca el valor); en Meta, `ads_get_dataset_stats` con `event_source=SERVER_ONLY` tras el primer tráfico real | Si falta el token, decirlo como pendiente del dueño antes de activar (`06-tienda-impultienda.md` §5.1) |

Los nombres de campo se verifican antes con `ads_get_field_context`; un campo inventado hace fallar la consulta.

## 4. Control previo y activación

Desde el 2026-11-13 **no se pregunta al dueño** (regla L3, `escalar-oferta/references/02-decidir.md`): con la tabla del §3 se arma la lectura y se corre `python3 .claude/skills/escalar-oferta/scripts/control_previo.py --lectura <ruta>` (landing y checkout responden, píxel, precio 19/27, presupuesto de 3 tickets, inicio a las 00:00 en la zona del mercado y en el futuro, al menos 1 anuncio no rechazado (los rechazados solo se apelan una vez, nunca se reemplazan: dueño 16-nov), sin errores y, desde el 14-nov, el funnel entero probado con `verificar_funnel.py correr --oferta … --antes`, que va en la lectura como `funnel`). `NO_ACTIVAR` → no se activa: se corrige lo que se pueda (nunca reemplazando un anuncio rechazado) y se vuelve a correr; si no queda ningún anuncio no rechazado (pocket 1-1-1 con su anuncio rechazado), esa campaña no sale, queda en pausa y se avisa.

**Antes de activar, mirar la hora otra vez (`date` y `TZ=<zona del mercado> date`), sobre todo si pasaron horas desde que se creó el conjunto.** Si el `start_time` del conjunto ya pasó, el conjunto sale en el acto: crear un conjunto nuevo con las 00:00 siguientes del mercado, copiar los anuncios por `creative_id` y activar ese. En la cuarta corrida (cuando todavía se pedía el visto bueno) la pregunta se hizo a las 00:40, el dueño contestó a las 08:10 y el conjunto se activó con el inicio vencido; hubo que pausarlo y rehacerlo (gasto 0, por suerte).

~~Una sola pregunta al dueño~~ (obsoleto desde el 13-nov). Con `ACTIVAR`:

1. `ads_activate_entity` campaña → conjunto → cada anuncio, en ese orden (activar un padre no activa a los hijos). En México fueron 13 llamadas.
2. No activar conjuntos viejos ni duplicados.
3. Hacerlo con horas de margen: Meta revisa cada anuncio y los largos tardan más.

## 5. Verificación tras activar

Repetir las consultas del §3. Estado esperado: campaña y conjunto `ACTIVE`; anuncios `ACTIVE` o `IN_PROCESS` (en revisión); errores vacíos; gasto 0 hasta la hora de inicio. Anotar en `anuncios.json` la hora de activación y el estado.

Avisar al dueño (con `escalar-oferta/scripts/avisos.py avisar`): a qué hora arranca en la hora del mercado y en la suya, cuántos anuncios están aprobados y cuántos en revisión, y qué sigue sin probar (compra, voces). Desde ahí la vigila la tarea «vigilancia-ofertas» cada hora (skill `escalar-oferta`); no hace falta proponer la revisión.

## Tropiezos de esta fase

| Síntoma | Causa | Salida |
|---|---|---|
| «Ad account status is ineligible to manage ads» | Pago pendiente en la cuenta | El dueño salda; reintentar |
| «Start Time Can't Be Edited» | `start_time` no es editable tras crear | Conjunto nuevo con la fecha y anuncios por `creative_id` |
| La vista previa devuelve `body` y `link_url` vacíos | En creativos de video el texto y el enlace viven en el `object_story_spec` | Leer el creativo con `ads_get_creatives` y abrir la vista previa |
| `ads_get_ig_accounts` devuelve lista vacía | No hay cuenta de Instagram conectada | Normal en esta estructura; comprobar `instagram_user_id` en el creativo |
| Los ID de video cambian respecto a los subidos | Meta crea otro objeto al armar la publicación | Guardar los del creativo final |

### Notas de la segunda corrida (2026-11-11)

- El alojamiento temporal tarda en el primer archivo (más de 2 minutos) y luego unos 15 s por video: lanzar `publicos.py` en segundo plano y leer `videos/publicos.json` a medida que se llena.
- Crear UN anuncio primero para validar el formato del creativo y recién después los demás en paralelo.
- Los 10 videos de 9-14 MB quedaron `ready` en Meta en menos de un minuto.
- `ads_activate_entity` puede devolver un error interno pasajero en un anuncio suelto: reintentar ese anuncio y leer estados al final. Tras activar, los anuncios quedan `ACTIVE` con `effective_status` `PENDING_REVIEW` o `IN_PROCESS`: es la revisión de Meta, no un fallo.
- El `start_time` se lee de vuelta en la zona de la cuenta (`03:00 -0300` = 00:00 del centro de México): convertir antes de dar la hora al dueño.

## Si el conector de Meta no puede: se sigue por el navegador (dueño, 16-nov)

Regla del dueño: «cuando no se puede por el conector se proceda de esta manera, para que nunca te quedes parado». Si una escritura del conector de Meta Ads falla por algo que no es el contenido del anuncio —permiso de página (error 10/100, subcódigo 3858749 «Missing Page permission»), identidad de Instagram de la página (#1815199), un campo que la API no expone o el freno `meta_sin_pausa.py`—, NO se para ni se espera al dueño:

1. Se hace lo mismo en el navegador integrado con la sesión del dueño: Administrador de anuncios (`adsmanager.facebook.com/adsmanager/manage/ads?act=<cuenta>`) para anuncios, conjuntos y presupuestos; Business (`business.facebook.com/latest/settings/...`) para páginas, píxeles y activos.
2. Está autorizado dar, desde el navegador, los permisos que falten **sobre activos propios del portfolio Never Give Up** (cuenta publicitaria ↔ página de la oferta, ↔ perfil de Instagram de la página). Nada de pagos, contraseñas, verificaciones de identidad ni activos de terceros: eso se avisa.
3. Las campañas se siguen creando por la API cuando se puede (no necesitan página); solo los creativos y anuncios pasan al Administrador. Todo en pausa y con el mismo control previo antes de activar.
4. Se anota en `tropiezos.md` y en el `estado.md` de la oferta qué se hizo a mano y por qué, y se le dice al dueño en el cierre qué arreglar en el conector (casi siempre: eliminar «ads MCP server» en Facebook → Integraciones comerciales y volver a autorizar Meta Ads eligiendo todas las páginas).

Caso que lo originó: 16-nov, réplicas UK y DE. El conector solo veía las páginas personales del dueño (tuotroproyecto, el dueño, Sales With IA) y rechazaba creativos con cualquier página de Never Give Up, incluida la de Irlanda, que el 15-nov funcionaba. Los permisos del dueño en Business eran idénticos en todas las páginas; reconectar sin eliminar la integración no renovó la autorización (seguía con fecha 7-nov).
