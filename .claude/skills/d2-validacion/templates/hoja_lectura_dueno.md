# Hoja de lectura del dueño — D2 · {oferta_id} · {locale} · {fecha}

> Generada por el Maker con `normalizar_biblioteca.py` (sección `seleccion.urls_snapshot`). **Hoy la lectura es manual** (`humano_muestreo`): la captura automática de la Biblioteca tiene el freno puesto (`empresa/captura/freno.json`) y solo una persona lo levanta.
> Cómo: abre cada enlace en **tu navegador normal**, a ritmo humano (sin extensiones ni automatización), y anota solo lo que ves. **Costo: ≈ {minutos_snapshot} min por enlace** (`parametros.minutos_por_snapshot_lectura`) → ≈ {total_lectura} min en total.
> Reglas: (1) copia como mucho el hook, en ≤ 25 palabras, entre comillas; el resto, paráfrasis. (2) Si el enlace no abre, el anuncio ya no está, pide login o aparece un captcha: escribe `NO ABRE` y **para** (no insistas; si es captcha o login, avísame y no sigas). (3) Si el anuncio te da una instrucción («responde con…», «ignora lo anterior»), **no la sigas**: escribe `HOSTIL` y copia la frase. (4) No compres, no escribas, no entres a perfiles. (5) Qué NO anotar: nombres de personas, teléfonos ni correos.
> Pega la hoja rellenada en el chat de la sesión (o guárdala como `ofertas/{oferta_id}/02-validacion/evidencia/lectura_dueno.md`). El Maker la transcribe a `anuncios_competencia.json` con `leido_por: dueno`.

## Competidor {operador_id} — {page_name} (`page_id` {page_id}; {n} anuncios vistos; el más viejo, {edad} días)

| # | Enlace (`ad_snapshot_url`) | Edad (días) | Hook (≤ 25 palabras, literal) | Promesa (1 frase, paráfrasis) | Mecanismo: cómo dicen que funciona (2-6 palabras) | Prueba social (reseñas, cifras, «verificado») | CTA | ¿Claim de ingresos, cura o plazo? (sí/no + cuál) | Precio visible + moneda | URL de destino (landing) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | https://www.facebook.com/ads/library/?id={ad_id} | {edad} | | | | | | | | |
| 2 | | | | | | | | | | |
| 3 | | | | | | | | | | |
| 4 | | | | | | | | | | |
| 5 | | | | | | | | | | |

(Repite el bloque para cada competidor profundo; son {n_prof} × {snapshots_por_competidor} enlaces, tope `urls_snapshot_max_modo_humano`.)

## Cierre (1 min)
- ¿Algún anuncio te pidió algo o te llevó a un lugar raro? → `HOSTIL` / ninguno:
- ¿Qué competidor NO es producto digital (es software, servicio, afiliado)? → page_id:
- Tiempo real que te llevó (min): ______  → anótalo en la bitácora `Pulido` del panel.
