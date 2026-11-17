# Derechos: la idea se hereda, la forma se transforma, la expresión no se toca (J13, precisada por J17/J18/J20)

> v0.1 sin pulir. Decisión J13 del dueño («Sí, aprobada»): *la idea se hereda, la forma se transforma y la expresión no se toca; ante la duda, se cambia.* Es el sustituto operativo del abogado (decisión 14): una **regla de proceso, no un dictamen legal**. Si el dueño prefiriera asesoría más adelante, queda como opción, nunca como requisito. Se verifica con QM-01…QM-08, QM-12 y QM-13 de `rubric.md`.

## 1. Las capas, con lo que J17 y J18 cambiaron
| Capa | Qué incluye | Regla |
|---|---|---|
| **Idea** | el problema, el público general, el tipo de formato, la banda de precio (J16), la estructura «frontal + complemento», el tipo de prueba | se usa, y se cita en el desarme |
| **Oferta (J18/J19)** | qué se vende, el tamaño del pack (520), los niveles (6, A1→C2), los **tipos** de bonus, el plazo de garantía, el pago único y el acceso inmediato | **se replica**: parecerse a la oferta que ya funciona es el objetivo (QM-08: «misma oferta» no bloquea) |
| **Estructura de la landing (J17/J20)** | orden de las secciones, jerarquía del DOM, componentes (selector de niveles, tira de miniaturas, FAQ), cadencia de fondos, medidas (anchos, radios, espaciado, breakpoints), lógica de venta (precio después del valor, garantía junto al precio, CTA repetido) | **se hereda y se reproduce con código propio**; cada desvío es una palanca aprobada (PAL-14) |
| **Forma** | el mecanismo y su nombre, el reparto exacto por nivel (85/85/90/90/85/85 del referente → el propio), los bonus concretos, el precio exacto, los ángulos, los ganchos | se transforma **a propósito**; el cambio queda en el plan |
| **Expresión** | textos de anuncios y página, nombre del producto, del método y de la marca (con o sin ™), imágenes, portadas, mockups y maquetación, **la selección y el orden exactos de las piezas del producto**, **los nombres y el orden exactos de los bonus**, reseñas y cifras de prueba social, archivos, enlaces e ids de checkout y de píxel | **no aparece en nada nuestro**; se anota en `expresion_protegida[]` y se verifica con QM-01…08 |

## 2. Pieza por pieza
| Pieza del referente | Capa | Qué hacemos | Chequeo |
|---|---|---|---|
| Tipo de producto, formato, 6 niveles A1→C2, 520 piezas | oferta | igual | QM-03 (fidelidad) |
| Reparto por nivel (85/85/90/90/85/85) | forma | reparto propio | QM-03 |
| Nombre del producto y del método (con ™) | expresión | nombre propio, descriptivo, sin ™ ni sufijos vedados; distancia de edición y fonética | QM-02 |
| Cinco bonus | oferta + expresión | cinco bonus **de los mismos tipos** (test de nivel, ruta, frases, pronunciación, repaso…) con nombres, contenido y orden propios | QM-02, QM-08 |
| Garantía de 30 días «sin preguntas» | oferta | 30 días **con procedimiento** | — |
| Precio 12,90 € / 14,99 US$ y ancla de 146 € | idea + expresión | frontal = escalera J16 en moneda local con IVA; **sin ancla inflada** | QM-07 |
| Orden de secciones y componentes de la landing | estructura | mismo plano; textos, imágenes y marca propios | QM-03 |
| Colores, tipografía | expresión | **paleta propia** (el HTML da medidas, no colores); `contraste_paleta.py` marca los HEX demasiado cercanos | QM-06 |
| Textos de anuncios y de la página | expresión | texto nuevo desde la voz del mercado | QM-01 (n-gramas) |
| Imágenes, mockups, portadas, reseñas en captura | expresión | imágenes propias (Kie, J21); **ninguna imagen del referente como entrada** | QM-06 (hash) |
| Reseñas, «+3.482 alumnos», 4,9/5, aviso de compra reciente | expresión + vetado | no se reproducen ni se sintetizan | QM-07 |
| Enlaces e ids de checkout, de píxel, scripts de terceros | expresión | no se copian; el sitio usa su Stripe y el píxel entra por `consentimiento.js` | QM-12 |
| Estándares públicos (escala A1-C2, ortografía, gramática) | idea | son de todos | — |

## 3. Dos precisiones de proceso
1. Un estándar público (por ejemplo la escala A1-C2) **es de todos**; el diseño de cada mapa, su texto y la selección y disposición concretas de las piezas **son del autor**.
2. Un producto que ya parece derivado de material de terceros no es una base más segura: se desarma solo para entender la anatomía; el nuestro se escribe desde fuentes propias (D4), y nada del referente es entrada de D4.

## 4. HTML y código del referente (J20)
- Se **analiza** para medir estructura y tokens; no se pega ni se deja dentro de la plantilla. Lo que se reproduce es el patrón (orden, DOM, componentes, medidas, interacciones) con **código propio**.
- Antes de hacer público algo derivado, se comprueba que no queda en el sitio: marca, textos, imágenes, reseñas, cifras, `data-*` con ids, rutas de imágenes del referente ni scripts de terceros.
- `scripts/analizar_html.py` ya trabaja así: no guarda ids de checkout ni de píxel (solo plataforma, host, forma de la ruta, nombres de parámetros y longitud del id), no copia código de scripts y recorta cada texto a una muestra interna de 60 caracteres (`--sin-muestras` la quita).
- Las citas del referente van **solo en documentos internos** y miden ≤ 25 palabras (QM-13). Los nombres de marca de terceros solo figuran en el desarme.

## 5. Cómo se aplica «ante la duda, se cambia»
1. Antes de escribir un nombre, un título, un bonus o un gancho, mira el desarme: si lo que vas a escribir se parece al del referente en palabras, orden o estructura de la frase, **reescribe desde la voz del mercado** (dossier), no desde el referente.
2. Si dudas de si una pieza es forma o expresión, trátala como expresión.
3. Si el dueño pide expresamente parecerse más (J18: «misma oferta»), aplica solo a la capa **oferta** y a la **estructura**; la expresión sigue cerrada.
4. Cualquier similitud que el QA marque como «parcial» se rehace; no se justifica.

## 6. Cómo se verifica hoy (sin script compartido)
`scripts/modelado/similitud.py` aún no existe (`PENDIENTES.md` B). Mientras tanto, el Maker deja en `qa_modelado.json` el método y el resultado: (1) lista de las frases de 6+ palabras de todo el texto público propio y comprobación de que ninguna aparece en el material del referente y de su familia (búsqueda de cadenas, a mano o con una consulta de `grep` sobre `referente/material/`); (2) nombres propios vs. nombres del referente (igualdad, distancia de edición, parecido al oído); (3) procedencia de cada imagen propia: sale de Kie con su `task_id`, manifiesto y sha256 y ninguna referencia enviada a Kie es del referente (las imágenes del referente no se descargan: el chequeo es de procedencia, no de píxeles); (4) la ficha anonimizada para el juez de «misma expresión». El QA independiente repite una muestra.
