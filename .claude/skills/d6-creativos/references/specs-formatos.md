# Especificaciones de formato (Anexo A de la spec) y render de estáticos

Todo valor externo (zonas seguras, límites de caracteres, enum de CTA) es **[VERIFICAR]** en Ads Manager antes de congelar la skill 1.0.0. Se parametriza aquí para cambiarlo en un solo sitio.

## 1. Ratios y medidas

| Ratio | Medida de render | Uso | Ruta |
|---|---|---|---|
| 4:5 | 1080 × 1350 | Feed (principal) | A (HTML→PNG) o `generate_image` con un modelo que lo admita (p. ej. `marketing_studio_image`) |
| 9:16 | 1080 × 1920 | Reels y Stories | A o B |
| 1:1 | 1080 × 1080 | Respaldo | A o B |
| 3:4 | 1080 × 1440 | Salida de `reframe` y de `ads_studio_*` (que ofrece solo 1:1, 9:16, 16:9 y 3:4; **sin 4:5**) | B |
| 16:9 | 1920 × 1080 | Solo si D7 lo pide | B |

`reframe` es **solo de video** (usar 3:4). Un paquete con feed necesita al menos una pieza 4:5 o 1:1 por anuncio y, si el anuncio va a Reels o Stories, su versión 9:16; D7 revisa el preview por ubicación **[VERIFICAR]**. Cada asset del paquete es un archivo con **un** ratio; un anuncio con tres ratios tiene tres entradas en `assets[]`.

## 2. Zona segura 9:16 (texto y elementos portantes)

Dos fuentes dan cifras distintas, ambas **[VERIFICAR]**: el Anexo A de la spec (conservador: ≈14 % superior, ≈35 % inferior, ≈6 % por lado) y la banda de `anthropic-skills:creativos-ads` (banda de texto 720 × 1200 centrada, de y = 220 a y = 1420 en 1080 × 1920: 220 px arriba, 500 abajo y 180 por lado). La skill toma **el borde más restrictivo de cada lado**:

| Borde (1080 × 1920) | Margen libre mínimo |
|---|---|
| Superior | 14 % (≈269 px) |
| Inferior | 35 % (≈672 px) |
| Izquierdo y derecho | 180 px (≈16,7 %) |

Zona de texto resultante: x 180–900, y 269–1248. En 4:5 y 1:1 se deja un margen de ≈6 % por lado y se evita el 20 % inferior (puede tapar el CTA de Meta). El titular cortado por la zona segura es un defecto MAYOR (Anexo B).

## 3. Copy del anuncio

| Campo | Límite | Nota |
|---|---|---|
| `texto_principal` | Gancho en ≈125 caracteres visibles (Meta recorta); el máximo técnico es mayor **[VERIFICAR]** | La primera frase sola debe sostener el anuncio; el aviso necesario cabe en el cuerpo |
| `titular` | ≤ 40 (esquema `maxLength`) | En `de` y `pl` revisar truncado por palabras largas |
| `descripcion` | ≤ 30 (esquema `maxLength`) | Suele no mostrarse en todas las ubicaciones |
| `cta` | `LEARN_MORE` · `SHOP_NOW` · `DOWNLOAD` · `GET_OFFER` · `SIGN_UP` | Enum del contrato; vigencia oficial **[VERIFICAR]**. «Más información» como preferencia hispana es `[CREADORES, C]`: no se asume en otros idiomas |
| `idioma` | = `mercado.locale` | BCP-47 con región (`it-IT`) |

Moneda y números por `locale` (`references/localizacion.md` §3). Los números del anuncio (precio, minutos, cantidad de elementos) salen de `oferta.json`/`claims_permitidos`, no de la memoria.

## 4. Video

Tensión o gancho en ≤3 s; subtítulos siempre (se ve sin sonido); plano nuevo cada ≈3–5 s; 20–45 s como forma de entrada **[CREADORES, C]** (y 6–15 s para variantes cortas); primer fotograma con el gancho. Sin música en la v1 salvo pista con licencia comercial documentada en `licencias.json`. Subtítulos: grandes, contraste ≥ 4,5:1, una a tres palabras por vez, **sincronizados con el audio dentro de 0,3 s**; el texto de los subtítulos es el del guion congelado. El audio de una locución IA **es** el guion aprobado palabra por palabra.

## 5. Plantilla HTML→PNG (`templates/estatico.html`)

- Un archivo HTML por pieza y ratio, guardado en `assets/src/<ad_name>.html`; el PNG sale de `assets/<ad_name>.png` (o `<ad_name>-9x16.png` si el mismo anuncio tiene varios ratios: el `ad_name` del paquete no cambia y los nombres de archivo con sufijo quedan en `assets[].archivo`).
- `lang` = idioma del `locale`; fuentes **locales** (OFL o similar, con ñ, ł, ș/ț, ß, acentos), sin recursos remotos; ninguna fuente o imagen sin licencia registrada en `licencias.json`.
- Texto de la pieza = `copies.json` congelado (el HTML se genera desde él; no se retoca a mano). El rótulo «ilustrativo» (it *illustrativo*, pl *ilustracyjnie*, ro *ilustrativ*, fr *à titre d'exemple*, de *beispielhaft*, es *ilustrativo*, en *illustrative*) va **en el mismo cuadro** que la cifra.
- Mockups: solo con páginas reales de `04-producto/entregables/` (capturas de la muestra); nunca un entregable que el producto no incluya.
- Imagen generada: solo como fondo **sin texto ni personas**; el texto siempre lo pone el HTML (el texto dentro de imágenes generadas sale roto).
- Verificación de L1 por pieza: medida exacta del ratio, peso razonable `[PENDIENTE: umbral de peso]`, contraste texto/fondo ≥ 4,5:1, texto dentro de la zona segura (9:16), caracteres del `locale` intactos, OCR o lectura visual del PNG contra `copies.json`.

## 6. Render y herramientas

`scripts/render_estatico` (Playwright) y `scripts/ocr_check` (1 fps) **no existen**: `references/dependencias.md`. Hasta entonces el Maker puede renderizar con su propio Playwright en la sesión del dueño (ver `references/costos-y-rutas.md` §2) y el QA lee cada PNG con `Read` (lectura visual) y compara con el texto del HTML fuente. `ffmpeg` está instalado en el equipo del dueño (extracción de fotogramas a 1 por segundo: `ffmpeg -i video.mp4 -vf fps=1 frames/%03d.png`); no está en la lista de comandos permitidos de los hooks: pedido en `dependencias.md`.
