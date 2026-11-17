# Cambios en Meta sin apagar nada (dueño, 15-nov)

> «Una campaña que está gastando y está prendida no puedes apagarla y prenderla el mismo día. La puede romper.»

## Por qué

La herramienta `ads_update_entity` del conector de Meta, cuando edita una campaña, un conjunto o un anuncio **activo**, lo
**pausa sola** antes de guardar el cambio (`status_forced_to_paused: true`). Pasó el 15-nov al surfear Oferta F de 211 a
277 USD/día: la campaña quedó en pausa y hubo que prenderla con `ads_activate_entity`. Un apagado y prendido en el mismo día
puede tirar la entrega y el aprendizaje de una campaña que vende, así que **no se acepta ni por segundos**.

## La regla

| Cambio | Por dónde | Nunca |
|---|---|---|
| Subir o bajar el presupuesto de la CBO (surfeo, +30 % 24 h, −30 %) | **Administrador de anuncios**, en el navegador | `ads_update_entity` con `daily_budget` |
| Poner o quitar los límites de gasto de un conjunto (mínimo 10 % y máximo 20 %, R9b) | **Administrador de anuncios** (`03-renovar-creativos-y-escalar.md` paso 6) | `ads_update_entity` con `daily_min_spend_target` |
| Fechas, nombre, segmentación de algo que ya existe | **Administrador de anuncios** | `ads_update_entity` |
| Apagar (corte, R4b, a pedido del dueño) | `ads_update_entity` `{"status":"PAUSED"}` solo, sin otros campos | — |
| Crear conjuntos, anuncios y campañas | `ads_create_*` (no pausan nada que corra) | — |

Lo frena el código: el hook `.claude/hooks/meta_sin_pausa.py` (registrado en `.claude/settings.json`) rechaza cualquier
`ads_update_entity` que no sea solo `{"status":"PAUSED"}` (o ARCHIVED/DELETED) o descartar un borrador. Si te frena, no
busques otra herramienta que escriba en Meta: hacelo en el Administrador.

## Cambiar el presupuesto de la CBO en el Administrador

En el navegador donde esté abierta la sesión de Meta (el mismo que se usa para los límites de gasto de los conjuntos):

1. Leer antes por API la campaña con `ads_get_ad_entities` (`status`, `effective_status`, `daily_budget`): anotar el de antes.
2. Abrir `https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=<cuenta>&selected_campaign_ids=<id de la campaña>`
   (cuenta principal: `reglas.json` → `meta_vivo.cuenta`).
3. En la pestaña **Campañas**, en la fila de la campaña, hacer clic en la celda de **Presupuesto** (el lápiz), borrar el
   monto y escribir el nuevo en dólares enteros (el que dio `escalar_presupuesto.py`).
4. **Guardar** y, si aparece la barra de cambios sin publicar, **Publicar**. No tocar el interruptor de encendido.
5. Comprobar por API con `ads_get_ad_entities`: `daily_budget` = nuevo × 100, `status` = `ACTIVE` y `effective_status` = `ACTIVE`.
6. Anotar como siempre (`presupuesto_cambios`, `ficha.campanas[].presupuesto_diario_usd`, `FUNNEL.md`), con
   `"via": "administrador"`.

Si la sesión de Meta no está abierta o el Administrador no carga: **no cambiar el presupuesto** en esa vuelta (queda como
está, que no rompe nada), avisar con `avisos.py avisar presupuesto-<oferta> --mensaje "…"` y reintentar en la vuelta siguiente.

## Si igual apareció en pausa

Si al comprobar (paso 5) la campaña no está `ACTIVE` y estaba activa antes del cambio: prenderla en el momento con
`ads_activate_entity`, comprobar `ACTIVE` y avisar al dueño con urgencia (`avisos.py avisar pausa-<oferta> --urgente`),
diciendo qué se cambió, por dónde y cuántos segundos o minutos estuvo apagada. Anotarlo en `tropiezos.md`.
