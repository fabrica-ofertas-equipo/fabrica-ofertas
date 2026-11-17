# Imágenes de la oferta con Kie.ai (J21): ranuras, ilustrativas, revisión ciega, tope de créditos

> v0.1 sin pulir. Decisión J21 del dueño: *todas las imágenes de la oferta (mockup del producto principal, bonus, bump, tarjeta de precio, imagen para compartir, miniaturas de «qué hay dentro») se rehacen con Kie.ai con la calidad del mockup del referente, pero cambiándolo y creando un nuevo producto que se vea distinto; algo las revisa y, si salieron mal, las vuelve a hacer. Mientras el producto no esté terminado se hace una base de cómo se vería («que se vea real, no hace falta ser tan duro»).* Fuente: bitácora del piloto («Imágenes con Kie», rondas 1 y 2), `d5-landing-checkout/references/landing-estructura.md` §5.2 y `scripts/imagenes/`.

## 1. Quién hace qué
| Quién | Hace | No hace |
|---|---|---|
| **Modelado** (esta skill) | deriva del `mapa_ranuras.json` y de `assets.json` qué imágenes hacen falta, con su función; fija las reglas de este archivo | produce, cotiza o gasta |
| **D5** | declara cada ranura en `assets.json` con `productor`, `herramienta`, `etiqueta_ia_visible` y `ilustrativa`; escribe el «Encargo de ranuras» en `brief.md`; integra solo lo aprobado | genera con IA, renderiza o cotiza |
| **D6 / sesión de imágenes que el dueño autorice** | produce con `scripts/imagenes/` bajo el tope de créditos de la ronda | cambia promesa, precio, claims; usa imágenes del referente |
| **Revisor independiente** (`d5-qa` en modo revisión de imágenes) | puntúa a ciegas con la rúbrica; devuelve PASA / REHACER por ranura | ve prompts, modelos ni la elección del generador |

## 2. Reglas permanentes
1. **Nada del referente como entrada.** Ni imagen, ni captura, ni portada, ni mockup suyo como referencia de Kie. Las referencias son portadas planas **propias**. Se imita la *calidad*, no la imagen.
2. **Otra escena, otros objetos, otros nombres, otra paleta.** El revisor comprueba que el resultado no reproduce el encuadre del referente (el piloto rehízo el héroe porque se parecía: otro orden de dispositivos y otra disposición).
3. **Lo anunciado = lo mostrado.** No se muestran funciones que el producto no tenga (el piloto rehízo una portada «de pronunciación» porque llevaba una onda de sonido y el producto es PDF sin audio).
4. **Sin rostros ni reseñas inventados**; nunca personas como clientes, antes/después ni capturas falsas. No se producen `opinion-N` (solo reseñas reales con permiso) ni `video-demo` (solo grabación real).
5. **Etiquetado:** `ia_generado: true`, `etiqueta_ia_visible: true` (la etiqueta la pone la página, no la imagen). Antes de usarlas en un anuncio de Meta: etiqueta de IA y dictamen de X1 sobre texto en imagen.
6. **Texto en la imagen:** estricto en títulos, cifras y nombres (OCR de código contra los textos esperados); flexible en el interior de lo ilustrativo (`estricto: false` en esa parte).
7. **Mientras D4 no entrega el producto, todo lo que muestre el interior es ilustrativo**: `ilustrativa: true` y `reemplazar_con_real_cuando_exista_producto: true`. Una miniatura ilustrativa **no es una muestra real**: no va a producción como «muestra real» (PAL-13); se rotula visiblemente («ilustración») y X1/QA lo validan. En vista previa sí.
8. **Máx. 3 intentos por ranura** (cuenta cada envío a Kie; las composiciones por código y los finales no gastan) y **tope de créditos de la ronda** (por defecto 900 ≈ 4,5 US$ en `ranuras_kie.py`; el dueño fija el de cada ronda). **El gasto se anota ANTES de cada envío**; si el siguiente superaría el tope, no se envía (código de salida 5).

## 3. Ranuras de una oferta de ebook (catálogo del piloto; el de D5 es el normativo)
| Ranura | Función | Medida final | Notas |
|---|---|---|---|
| `hero` | mockup principal (dispositivos + portadas) | 1:1 · 1120×1120 · webp ≤ 150 KB | composición por código (§5) |
| `portada-pack`, `bono-1…N`, `bump` | portada 3D de cada pieza | 1:1 · 640-800 px · webp ≤ 70-90 KB | una sola referencia plana → un objeto |
| `compra` | tarjeta de precio | 1:1 | composición por código |
| `og` | imagen para compartir | 1200×630 | placa de Kie + texto exacto en HTML |
| `muestra-1…6`, `muestra-principal` | miniaturas «qué hay dentro» | 3:4 y 16:9 | **ilustrativas** hasta que D4 entregue |
| `opinion-N`, `video-demo` | — | — | **no se producen** (regla 4) |

## 4. Flujo
1. **Encargo.** Por ranura: `slot_id`, función, **textos exactos**, objetos esperados, **qué NO debe aparecer**, ratio y píxeles, `estricto`, `alt` y `ilustrativa`.
2. **Portadas planas** con el texto exacto: `scripts/imagenes/portadas_planas.py ESPEC.json --salida DIR` (HTML/CSS → PNG con Chrome sin pantalla; paleta propia). Los modelos deforman el texto pequeño: se les da la pieza plana como referencia.
3. **Generación** bajo tope: `python3 scripts/imagenes/ranuras_kie.py generar PLAN --assets DIR [--solo a,b] [--tope N] [--seco]` (primero `--seco` para ver la cotización). Cada candidato deja su JSON con prompt exacto, modelo, parámetros, créditos, `task_id`, sha256, textos esperados y comprobaciones de código (dimensiones, ratio, no vacía, peso WebP, **OCR de los textos esperados**). Es idempotente: no se paga dos veces; una caída se retoma con `recuperar(task_id)`.
4. **Revisión ciega** por un agente independiente (§6). Lo que no pasa se regenera con corrección de prompt: `ranuras_kie.py reintentar PLAN --assets DIR --slot S --modelo M --correccion "…"`.
5. **Finales:** `scripts/imagenes/finales_ranuras.py PLAN --assets DIR [--revision revision-ronda1.json]` → `final/<slot>.webp|jpg` a la medida y peso de cada ranura, `final/manifiesto-final.json` (sha256, modelo, créditos de todas las rondas, intentos, `ilustrativa`, `aprobado_por_revision`, `alt_propuesto`) y una **propuesta** de cambios a `assets.json` (no lo edita).
6. **Integración** solo por D5, y solo lo aprobado.

## 5. Lecciones de modelos y de texto (medidas en el piloto)
- Con **4 o más referencias** o texto denso, `gpt-image-2` conserva iconos, etiquetas y subtítulos; con **una sola portada** y texto grande, `nano-banana-pro` es exacto. `nano-banana-2` simplificó el mapa e inventó textos en inglés.
- **El texto pequeño generado por IA falla de forma recurrente** (pies de móvil, subtítulos, diacríticos como «Około» sin barra). Lo que funciona es **no pedirle texto**: mockups con más de una portada = **composición por código**: Kie genera solo la escena con superficies de marcador de color plano (`guia_escena.py` dibuja el boceto de composición) y `componer_portadas.py` pega las portadas planas ya validadas (homografía + máscara real + luz de la escena). Una composición exacta no admite portadas solapadas.
- Las ilustraciones de «mapas por dentro» comparten plantilla: variar un poco la composición y mantener los colores dentro de la paleta de marca.
- Créditos medidos (2K): `nano-banana-pro` 18, `gpt-image-2` 10, `nano-banana-2` 12; `kie.py` estima 6 y 8 para los dos últimos (el tope usa el mayor entre estimado y medido). **La clave de Kie es compartida**: el saldo no sirve para atribuir gasto; se controla con `creditsConsumed` de cada candidato y el ledger de la ronda (`gasto-ronda.json`, `costos-borrador.jsonl`, `registro-kie.jsonl`).
- Chrome sin pantalla no baja de ~500 px de ancho; las capturas móviles se hacen con un `iframe` de 390 px.

## 6. Rúbrica del revisor ciego (por ranura)
Recibe solo la imagen, la función, los textos esperados, los objetos esperados, «qué NO debe aparecer» y `estricto`. Responde **PASA** o **REHACER** con motivo concreto.
1. **Texto estricto:** títulos, cifras y nombres idénticos a los esperados (diacríticos incluidos); sin texto inventado. Revisar a zoom el texto pequeño.
2. **Objetos y función:** están los objetos pedidos; nada que el producto no tenga (audio, app, comunidad); la imagen sirve a su sección.
3. **Distancia del referente:** otra escena, otro encuadre, otra paleta; nada de madera/lámpara/estantería u otros rasgos del referente si el encargo los excluye.
4. **Calidad:** nitidez, sin manos ni objetos deformados, sin artefactos, proporciones correctas (hoja A4 no estirada), margen suficiente.
5. **Coherencia de marca y de lote:** paleta dentro del sistema de marca; las ilustrativas no clonan la misma plantilla.
6. **Honestidad:** `ilustrativa` declarada donde corresponde; sin personas reales o inventadas como clientes.
En la ronda 1 del piloto pasaron 14 de 17 ranuras; las 3 rehechas (héroe, compra, un bonus) fallaban por una causa común (la onda de sonido) y por texto pequeño.

## 7. Qué NO prueba este flujo
Que la imagen convierta, que Meta la apruebe, ni que sea la imagen del producto real: cuando D4 entregue, las ilustrativas se reemplazan por páginas reales y se vuelve a revisar.
