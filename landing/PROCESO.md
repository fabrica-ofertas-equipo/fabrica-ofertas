# Proceso de creación de la landing (D5): de la oferta aprobada al sitio publicado

> Versión **0.1.0** (2026-11-06), sin pulir: se corrige con cada corrida real. Detalle por paso, reglas de decisión y rúbrica del QA:
> `.claude/skills/d5-landing-checkout/references/proceso-landing.md` (fuente del proceso) y `landing-estructura.md`, `copy-por-seccion.md`.
> Este archivo es la versión **operativa**: qué comando corre quién, qué entra y qué sale, y cómo se pule. Sin abogado (decisión 14): las siete
> páginas legales son plantilla genérica; el preflight solo comprueba que existan y respondan 200.
> **Para el dueño (10 minutos): §1, §4 y §6.**

## 1. El proceso en una página

La «landing ganadora» de Fer era una referencia (12 secciones y dos prompts). Aquí es un proceso con entradas y salidas exactas. Cuatro reglas:
(1) la referencia aporta **estructura**, no texto ni colores; (2) **el contrato manda**: precio, moneda, garantía, plazos y cifras salen de
`oferta.json`/`checkout.json`/`producto.json` por *placeholders* (el Maker no escribe números); (3) **los LLM proponen, el código dispone**: el
Maker escribe `copy.json`/`paleta.json`/`assets.json`, el código los valida y genera el HTML; (4) lo que no tiene material real **se omite**, no se inventa
(ni testimonios, ni cifras de clientes, ni urgencia).

| # | Paso | Quién | Comando / acción | Entra | Sale (`ofertas/<id>/05-landing/`) | Listo cuando |
|---|---|---|---|---|---|---|
| 0 | Precondiciones | código | `.venv/bin/python .claude/skills/d5-landing-checkout/scripts/prechequeo.py --oferta-dir ofertas/<id> --empresa-dir empresa` | oferta, producto, mercado, validación | `prechequeo.json` | resultado `ok` (o `preguntas` contestadas); 0 bloqueos |
| 1 | Brief y plano | Maker | redacta | los 4 JSON | `brief.md`, `rutas.json` | cada dato con traza; secciones decididas |
| 2 | Paleta e imágenes | Maker (+ código) | `python .claude/skills/d5-landing-checkout/scripts/contraste_paleta.py --paleta <paleta.json>` | brief | `paleta.json`, `assets.json`, «pedido de imágenes» | 0 hallazgos MAYOR/BLOQUEANTE |
| 3 | Copy | Maker (+ código) | `python .claude/skills/d5-landing-checkout/scripts/lint_copy.py --copy copy.json --oferta … --mercado … --assets …` | brief, plano, paleta | `copy.json` | esquema válido y lint sin BLOQUEANTE ni MAYOR |
| — | QA-A (checkpoint previo al gasto de créditos) | QA | lectura | copy, paleta, assets | informe QA-A | 0 bloqueantes |
| 4 | Imágenes aprobadas | código / dueño | las ranuras pasan a `aprobado` con `archivo` y `sha256` | `assets.json` | `imagenes/*` | cada `<img>` con ranura aprobada |
| 5 | Checkout y tracking | Maker | redacta | oferta, producto, alta de oferta | `checkout.json`, `tracking.json` | coherencia de precio/garantía (C02) |
| 6 | **Simular** | código | `.venv/bin/python -m landing.generar --oferta <id> --simular --json` | todo lo anterior | nada escrito: archivos con tamaño y `sha256`, avisos | exit 0; los avisos están entendidos |
| 7 | **Generar** | código | `.venv/bin/python -m landing.generar --oferta <id> --json` | ídem | `sitio/` (14 secciones, `/comprar` con su formulario, `/gracias`, 7 legales, `/desistimiento`, `_headers` con la CSP) | exit 0 |
| 8 | **Validar** | código | `.venv/bin/python -m landing.validar --oferta <id> [--produccion] --json` | `sitio/` | hallazgos (lint L1) | 0 hallazgos |
| 9 | Catálogo y preview | código | `python -m landing.catalogo …` y `python -m landing.desplegar --oferta <id> --entorno preview [--live]` | `sitio/`, `checkout.json` | `catalogo.json`, `_despliegues/` | URL de preview, píxel apagado |
| 10 | QA + X1 | código + QA + X1 | L1 (C01–C17), rúbrica L2, simulaciones L3; dictamen y sello por hash | preview | `qa/d5-v<n>.json`, sello | PASS y sello vigente |
| 11 | **Pulido** | dueño (+ Maker/QA) | §4 | preview en su celular | bitácora, `v<n+1>` | criterios de §4.5 |
| 12 | Compra de prueba, gate H y producción | dueño + código | `landing.desplegar --entorno produccion` (re-hash y sello) | preview aprobado | despliegue, `aprobado_por` | firma H |

Quién escribe dónde: el Maker solo en `.staging/` (el runner promueve); el código (`landing.*`) escribe `sitio/`, `catalogo.json`, `_despliegues/`; el QA
no escribe; el dueño firma los gates H. Un cambio grande tras datos reales es una **versión nueva** (`v<n+1>`), nunca una edición.

## 2. Qué genera el código: el plano de 14 secciones

Plantilla: `.claude/skills/d5-landing-checkout/templates/sitio-base/` (manifiesto `secciones.json`; una plantilla HTML por sección; `estilos.css`
sin colores sueltos). **13 secciones de cuerpo (S01–S13) más el pie (S14)**; las 12 de la referencia de Fer más «para quién sí/no» (S07), que D5 añade.
Los tonos de fondo alternan (claro/suave y oscuro/profundo) y se reparten según las secciones que realmente salgan, de modo que nunca haya dos iguales
seguidas. Obligatorias = nunca se omiten.

| ID | Ancla | Propósito | Campo de `copy.json` | Se omite si |
|---|---|---|---|---|
| S01 | `inicio` | Hero: qué es, para quién (3.ª persona), qué recibe; primer CTA a la vista | `secciones.S01` (+ variante por ángulo) | nunca |
| S02 | `resumen` | Cifras reales del producto y 3 beneficios | `secciones.S02`, `cifras_con_traza` | no hay bloque; una cifra literal sin traza se descarta |
| S03 | `problema` | Dolores en el vocabulario del cliente y reencuadre | `secciones.S03` (variante: orden) | nunca |
| S04 | `muestra` | Capturas reales del entregable | `secciones.S04`, ranuras `galeria` | ninguna ranura de sus pies está aprobada |
| S05 | `metodo` | Mecanismo único y «de A a B» | `secciones.S05` | nunca |
| S06 | `incluye` | Módulos y checklist de lo que se descarga | `secciones.S06` | nunca |
| S07 | `para-quien` | Para quién es y para quién no | `secciones.S07` | nunca |
| S08 | `confianza` | Prueba honesta (o reseñas con `compra_id` y permiso) | `secciones.S08` | no hay bloque; reseña sin permiso detiene la generación |
| S09 | `extras` | Bonos con archivo y bump (nunca premarcado) | `secciones.S09` | sin bono con archivo ni bump real |
| S10 | `garantia` | Reversión de riesgo antes del precio | `secciones.S10` | nunca |
| S11 | `oferta` | Precio, qué incluye, medios de pago y CTA | `secciones.S11` (variante: CTA) | nunca |
| S12 | `preguntas` | FAQ con `<details>` (sin JavaScript) | `secciones.S12` (variante: cuál abre) | nunca |
| S13 | `cierre` | Cierre sin/con y CTA final | `secciones.S13` | no hay bloque |
| S14 | `pie` | Identidad, avisos (alcance, seguridad, ayuda), 7 legales, preferencias de cookies | `secciones.S14` | nunca |

Además: `secciones.banner` -> `js/consentimiento.js` (textos del idioma; la estructura es idéntica en todos los países, K03), `secciones.gracias` ->
`/gracias`, `secciones.comprar` -> `/comprar` (parte estática). El título, la descripción y `og:*` salen de `copy.meta`. Una sección omitida se anota en los
avisos del generador con su motivo; el Maker la registra en `copy.json#omitidas`.

**Diseño.** Mobile-first (revisado a 390 y 1440 px), tipografía fluida, cuerpo ≥ 16 px, objetivos táctiles ≥ 44 px; ancla de compra fija en móvil (aparece al
bajar, solo CSS); animaciones solo CSS y apagadas con `prefers-reduced-motion`; **cero JavaScript propio** (el único `<script>` es `/js/consentimiento.js`);
tipografía de sistema más una ranura para fuentes autoalojadas (copiar los `.woff2` a `05-landing/fonts/` y declararlos en `paleta.tipografia`; si faltan,
el generador avisa y usa la pila de sistema); sin CDN ni fuentes remotas. Los colores salen de `paleta.json`; el generador **falla cerrado** si algún par que
el CSS usa no cumple AA (4,5:1 texto y botones, 3:1 foco y botón sobre su fondo) o si la paleta reutiliza colores de la base.

### 2b. Dos planos: `clasica` y `referente` (el del dueño: J17/J18/J20)

`secciones.json` trae los dos planos. **`referente`** (por defecto con `copy.schema_version` ≥ 0.2.0 o `estructura: "referente"`) reproduce el orden y el
DOM del referente medido en `docs/_historial/modelado-piloto/referentes/analisis-html-axon.md`: barra superior · héroe con mockup grande · tira oscura
«qué hay dentro» · reseñas · niveles con selector · para quién · bonus · comparación con el mercado · precio · garantía (después del precio) · cómo lo
recibes · FAQ · CTA final · pie, con CTA tras los bloques marcados y botón fijo en móvil solo con CSS. `clasica` es el plano de 14 secciones de arriba (copy
0.1.x). Plantillas nuevas: `s01-hero-ref`, `s04-tira`, `s06-pestanas` (o `s06-niveles` con `<details>`), `s07-tarjetas`, `s08-opiniones`, `s09-bonus`,
`s10-garantia-ref`, `s11-precio-ref`, `s13-cierre-ref`, `s15-entrega`, `s16-comparacion`, `cta-bloque`. Campos y reglas de cada componente:
`.claude/skills/d5-landing-checkout/references/landing-estructura.md` §2b.

**Datos reales y vista previa.** (1) Valoración, ventas y descargas de la muestra salen de `05-landing/prueba_social_real.json` (lo produce código, con fuente y
fecha; total 0 = no se muestra); (2) la barra de «precio de lanzamiento hasta {fecha}» exige `checkout.precio_programado{fecha, precio}` con la MISMA fecha,
vigente y con un precio de después mayor (se regenera con `--hoy`); (3) `python -m landing.generar --vista-previa` pinta marcadores y demos con cinta «DEMO» y una
barra fija, solo en preview, y la salida va a `05-landing/sitio-vista-previa/` (o `--salida`): **nunca pisa `sitio/`**. `landing.validar` los bloquea con `L1-DEMO`
(`--carpeta sitio-vista-previa`) y `landing.desplegar --entorno produccion` los rechaza y solo publica `sitio/`. Reglas de `landing.validar`: `L1-DEMO`, `L1-COMPARACION`,
`L1-COMPARACION-FUENTE`, `L1-BARRA-LANZAMIENTO`, `L1-PRUEBA-SOCIAL`, `L1-RESENA`, `L1-IMAGEN-ROTULO`, `L1-IMG-ATRIBUTOS` y `L1-PESO`.

**Imágenes (J21).** Las ilustrativas y las generadas con IA SE PUBLICAN, rotuladas («Ilustracja poglądowa», «Obraz wygenerowany z pomocą AI»…, por imagen o por grupo, texto
del idioma del locale y reconfigurable en `copy.rotulos_imagen`); no se omite S04 en producción. Ranuras con sitio: `hero`, `portada-pack` (héroe sin mockup; imagen del precio
sin escena de compra; con ambas, miniatura junto a «qué recibes»), `muestra-*`, `bono-N`, `bump` (imagen en la tarjeta del bump) y `compra`; `og` admite 1200×630 (`1.91:1`).
Rendimiento: `width`/`height` en toda `<img>`, `fetchpriority="high"` solo en el héroe y `loading="lazy"` en el resto (lo comprueba `L1-IMG-ATRIBUTOS`).

## 3. Entradas y salidas del generador

- Obligatorias: `03-oferta/oferta.json`, `05-landing/checkout.json`, `05-landing/tracking.json`. Para el sitio diseñado, además `copy.json`, `paleta.json` y
  `assets.json` válidos (esquemas en `templates/*.schema.json` de la skill). Opcionales: `04-producto/producto.json` (cifras, entrega, divulgación de IA),
  `mercado.json` (días de desistimiento), `rutas.json`, `fonts/*.woff2`, `empresa/compliance/ayuda_por_pais.yaml` (`{ayuda_pais}`, formato provisional),
  `checkout.json › compra{bump_modo, renuncia{requerido, texto_version}, landing_version}` y `turnstile{habilitado, sitekey}`, y `empresa/parametros.yaml` › `landing.cookie_{vid,attr}_dias`.
- Si falta alguno de los tres JSON de diseño, genera el **sitio mínimo** de 5 secciones y lo avisa (no rompe ofertas antiguas).
- Todo texto se **escapa**; solo `**negrita**` y `*énfasis*` se convierten. Se rechaza (código 3) el copy con HTML, `javascript:`, caracteres de control o de
  dirección de texto (p. ej. U+202E), una imagen sin `alt`, una sección obligatoria ausente, una paleta sin contraste, un placeholder desconocido o sin fuente,
  una imagen cuyo `sha256` no coincide o que pesa más de `peso_max_kb`, y un SVG con contenido activo.
- Determinista: mismas entradas, mismos bytes (`hash_directorio(sitio/)` estable). `--simular` no escribe nada y lista los archivos con tamaño y `sha256`.

## 4. Ciclo de pulido (para el dueño)

Doble objetivo: dejar lista **esta** landing y pulir **el proceso** (cada corrida real corrige este documento y la plantilla). Máximo 3 sesiones de ~2 h.

1. **Preparación.** `--simular` y revisa los avisos; genera; `landing.validar`; sirve el sitio **solo en local** y mira las capturas:
   ```bash
   cd ofertas/<id>/05-landing/sitio && python3 -m http.server 8800 --bind 127.0.0.1
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --screenshot=/tmp/m.png --window-size=390,2400 http://127.0.0.1:8800/
   ```
   (Chrome impone un ancho mínimo de ventana: para 390 px reales, mira la página dentro de un `<iframe width=390>` local o usa las herramientas de desarrollo.)
2. **5 segundos** en tu celular, desde un enlace dentro de Instagram o Facebook: a 3 personas del idioma, ¿qué es, para quién, cuánto cuesta o qué recibe?
3. **Lectura con el dedo (390 px)**, sección por sección: ¿se entiende qué compro, cuánto y qué recibo? ¿hay muros de texto? ¿algo suena a promesa de salud,
   ingresos o resultado, o a urgencia? ¿la muestra deja juzgar? ¿falta una pregunta real en el FAQ? ¿el bump es opcional y está sin marcar? ¿el CTA se ve sin
   deslizar y no hay desbordes? ¿se parece a la referencia en estructura pero no en texto ni colores? Repite a 1440 px.
4. **Bitácora** (`#/pulido`): una entrada por observación con `[S##][R#|C##][categoría]` y severidad; las correcciones repetidas pasan a la plantilla (`sitio-base`), a
   `claims-rojos.md` o a este documento.
5. **«Lista» =** C01–C17 en verde en preview; QA en PASS con R1, R2, R5, R7 ≥ 3; sello de X1; al menos 2 de 3 personas responden bien las preguntas de 5 s;
   compra de prueba completa desde tu celular (correo y descarga); cero entradas `alta` abiertas; aprobada por ti en ≤ 2 rondas sin reescribirla.

Cambiar el diseño = editar `sitio-base/` (HTML, `estilos.css`) y correr `.venv/bin/python -m unittest discover -s tests/landing -t .`; no hay que tocar Python.
Las pruebas generan dos ofertas de nicho e idioma distintos (es-ES dinero, pl-PL relaciones), exigen 0 hallazgos en `landing.validar` y en el oráculo de CT, y
siembran defectos (precio, script externo, legal ausente, sello `EJEMPLO`) para comprobar que se detectan.

## 5. Arranque de pago (decidido por S-A, 2026-11-06) y decisiones abiertas

Fuente: `docs/_historial/decision-arranque-de-pago.md` (opción A: formulario HTML sin JavaScript). Lo que hace el código:

- **`/comprar` es estática** (`rutas.json`: `/comprar` = `estatica:comprar`, `/api/sesion` = `dinamica:crear-sesion`; un `rutas.json` existente no se reescribe, solo
  se avisa) con **UN** `<form method="post" action="/api/sesion">` y nada más: ocultos `oferta_id` y `locale` (iguales a `oferta.json`); casilla `bump` solo con
  `bump_modo = oferta_previa` (`checkout.compra.bump_modo` manda sobre `checkout.bump.modo`); casilla `renuncia_desistimiento` (`required`) solo si
  `checkout.compra.renuncia.requerido` lo dice (con `data-texto-version` = `compra.renuncia.texto_version`); un `<button type="submit">`. Nunca premarcadas. Textos de
  `copy.secciones.comprar` y rótulos del idioma. La casilla de «términos» de `copy.json` no es un campo del formulario (se enlaza debajo del botón; Stripe recoge
  los términos). `visitor_id` y los parámetros de anuncio **no van en el HTML**. El formulario envía EXACTAMENTE esos cuatro campos cerrados (`oferta_id`, `locale`, `bump`, `renuncia_desistimiento`)
  por POST a `/api/sesion`; el Worker (S-B) lo acepta solo desde un origen de `ORIGENES_PERMITIDOS`.
- **Criterio provisional de la renuncia.** Mientras `checkout.compra.renuncia.requerido` falte (nombres de S-A/S-B, anidados y opcionales; los planos `renuncia_requerida`/`renuncia_texto_version` ya no se leen), `landing.generar` decide por el locale
  (región en UE-27 o Reino Unido) y lo dice con un aviso explícito (`--simular` lo muestra). Cuando el campo exista, manda él, en los dos sentidos. `compra.landing_version`, si existe, se
  refleja en el informe de `landing.generar` (`datos.landing_version`, también con `--simular`); no va en el HTML.
- **Cookies propias** (`js/consentimiento.js`, el único script) **solo tras el consentimiento de marketing**, con `Path=/`, `SameSite=Lax`, `Secure` (en https) y `Max-Age` por
  parámetro: `fab_vid` = 128 bits aleatorios en hexadecimal (`crypto.getRandomValues`; el mismo id del píxel) y `fab_attr` = `k=v&k=v` percent-encoded, **máximo 400 bytes**,
  solo las claves `cid`, `asid`, `adid` (cada ID con `^[0-9]{6,20}$`; si no, se descarta), `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` y `fbclid`
  (opcional), en ese orden; cualquier otra clave se descarta y, si algo no cabe en los 400 bytes, se recorta el valor por caracteres (nunca un `%XX` a medias) o se omite.
  Duración: `empresa/parametros.yaml › landing.cookie_vid_dias` y `cookie_attr_dias` (CT-3 los agrega; **90 y 30 días [HIPÓTESIS]**, tope 395); mientras no existan se usan
  esos valores como respaldo aprobado por S-A, con aviso. Sin consentimiento no se escribe nada y se borran `_fbp`, `_fbc`, `fab_vid` y `fab_attr`; al rechazar o revocar, también.
- **CSP canónica** (`sitio/_headers`, Cloudflare Pages; decisión final de S-A, LT-38; se define en UN solo lugar, `landing.comun.CSP_CANONICA`, y de ahí salen `_headers` y `L1-CSP`):
  `default-src 'self'; script-src 'self' https://connect.facebook.net; connect-src 'self' https://www.facebook.com https://connect.facebook.net; img-src 'self' data: https://www.facebook.com;
  frame-src https://www.facebook.com https://connect.facebook.net; style-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' https://checkout.stripe.com`.
  `data:` solo en `img-src`; no se añaden dominios regionales de Meta por adelantado. `form-action` es EXACTO (con solo `'self'` Chrome bloquea el 303 a Stripe, verificado). `pixel.js` sigue inyectando
  `fbevents.js` solo tras el consentimiento de marketing; la CSP únicamente lo permite. `landing.validar` (`L1-CSP`) exige exactamente esas directivas y orígenes (cada directiva por separado, sin importar
  el orden): sin `form-action`, con `'unsafe-inline'`, con un origen fuera de la lista, con `frame-src` ausente o ajeno, con `data:` fuera de `img-src`, o con una directiva de más o de menos, falla.
  Mutaciones de la CSP en `tests/landing/test_formulario_pago.py`: MS-01 sin `form-action` · MS-02 `'unsafe-inline'`/`'unsafe-eval'` · MS-03 origen fuera de la lista · MS-04 `frame-src` ausente o ajeno · MS-05 `data:` fuera de `img-src`.
- **Turnstile fuera de v1.** Solo si `checkout.json › turnstile.habilitado = true` (con `turnstile.sitekey`, nombre provisional) se admite UN script externo exacto
  (`https://challenges.cloudflare.com/turnstile/v0/api.js`) y su `<div class="cf-turnstile">` **solo en `/comprar`**; la cabecera específica de esa ruta (`! Content-Security-Policy` en
  `_headers`) suma `https://challenges.cloudflare.com` a `script-src` y a `frame-src`. `turnstile.sitekey` es la clave **pública** (`checkout.json › turnstile{habilitado, sitekey}`); la clave
  secreta jamás va en `checkout.json` ni en `landing/` (el generador rechaza cualquier otra clave del bloque). Apagado por defecto; lo activa el dueño si ve abuso.
- **`landing.validar`: una regla de formulario, `L1-FORMULARIO`**, que admite exactamente lo anterior y rechaza: otra `action`, `method` distinto de `post`, `enctype`
  distinto del predeterminado, `formaction`/`formtarget`/`formmethod`/`formenctype`/`target` en cualquier página, campos que no sean ocultos o casillas, `<textarea>`/`<select>`,
  ocultos con otro nombre o valor, casillas premarcadas o no permitidas, casilla de renuncia ausente cuando se exige (o presente cuando no), botones que no sean el único
  `type="submit"`, y cualquier formulario fuera de `/comprar`.
- **Mutaciones del formulario** (`tests/landing/test_formulario_pago.py`, 76 casos = 38 por oferta, todas deben fallar): **MF-01** action ajena o distinta · **MF-02** campo de
  texto/email/tel/password/number, textarea o select (y ocultos de más) · **MF-03** `method=get` · **MF-04** casilla de renuncia ausente en UE/UK (con el contrato y sin él) ·
  **MF-05** `formaction`/`target` en el form, el botón o un enlace · **MF-06** formulario fuera de `/comprar` · **MC-04p** casilla premarcada. Más las ocho de siempre
  (`test_validar.py`, sobre `ofertas/_ejemplo`).
- **Choques con el oráculo de CT hasta que S-A lo actualice** (`tests/contratos/lint_landing_referencia.py`, no se rodean): (1) **`L1-FORMULARIO`** salta en `comprar.html`
  por `form` e `input` (prohíbe todo formulario); (2) con Turnstile habilitado, **`L1-SCRIPT-EXTERNO`** salta en `comprar.html`. No chocan: `_headers`, las cookies
  de `consentimiento.js` (usan `CONFIG.cookie_*`) ni `/api/sesion` (dinámica en `rutas.json`). Las pruebas propias descuentan solo el (1) y exigen todo lo demás del oráculo.

**Decisiones y limitaciones abiertas:**

1. **Orígenes de Meta en la CSP: [VERIFICAR con el píxel real en la primera prueba: consola del navegador + Meta Pixel Helper].** No hay documentación oficial de Meta sobre la CSP del píxel; la lista
   es la decidida por S-A. En Chrome sin pantalla (solo 127.0.0.1) la portada y `/comprar` cargan con esta CSP sin violaciones (`report-uri` local, con un control que sí reporta), pero eso no prueba
   el píxel real: `fbevents.js`, sus peticiones y cualquier iframe solo se ven con el píxel en vivo. Si la consola muestra una violación, se añade el origen exacto a `CSP_CANONICA` (un solo lugar) y se vuelve a probar.
2. **`/desistimiento` y `/descarga`.** `/desistimiento` se genera solo si la ruta figura en `rutas.json` (texto genérico: dos pasos por correo, sin cuenta, con acuse);
   la función `POST /api/desistimiento` es de D10. `/descarga/<token>` es dinámica y no se genera.
3. **Fuentes.** El repositorio no trae `.woff2`; hasta que existan, la pila de sistema. La cobertura de glifos del idioma (p. ej. `ł ą ę`) se verifica con `fonttools`
   antes del gate H (pendiente de instalar).
4. **Idiomas con tabla propia:** es, en, it, pl (`landing/textos.py`). Otro idioma cae a inglés con aviso: añadir su tabla antes de publicarlo.
5. **`{ayuda_pais}`** lee `empresa/compliance/ayuda_por_pais.yaml` con un formato provisional hasta que X1 lo entregue.
6. El Worker `crear-sesion` (S-B) lee `fab_vid` y `fab_attr` con el formato de arriba; el contrato de `checkout` (CT-3) debe recoger `turnstile{habilitado, sitekey}` y `compra{…}`.
7. Las siete legales son plantilla genérica sin revisión legal (decisión 14); lo verificable lo automatiza X1 y lo fiscal lo cubre el contador.
8. El campo `modo` del JSON de la ejecución que sí escribe conserva su valor histórico `"dry_run"` (la simulación usa `"simulacion"`).

## 6. Decisiones de diseño que el dueño debe validar primero

1. **Plano fijo de 14 secciones con el orden propio** (garantía antes del precio; «para quién no» y prueba honesta en lugar de opiniones): se aparta del orden de
   la referencia y no se puede probar con A/B; se decide por criterio.
2. **Sin imagen no se inventa:** hero con portada tipográfica y sin sección de muestra hasta que haya capturas reales aprobadas. ¿Basta eso para vender en el
   primer lanzamiento o prefieres esperar a tener las capturas?
3. **Ritmo claro/oscuro, hero oscuro con el CTA ámbar/turquesa de la paleta y ancla de compra fija en móvil** (ver las capturas de 390 y 1440 px).
4. **CTA pulsante y animaciones suaves** (solo CSS, apagadas con `prefers-reduced-motion`): ¿las quieres o prefieres una página quieta?
5. **Banner de consentimiento** idéntico en todos los países (Aceptar, Rechazar y Personalizar con el mismo peso): cumple K03, pero baja la señal de Meta en todos.
