# landing

Generador y validador de landings (HTML estático) y del contrato landing-checkout con Stripe.

Propietario: **B4** (06-landing-checkout). Etapa: D5. Texto por locale (BCP-47); sin datos de
salud en el píxel ni en nombres de página; CSP: un único `<script>` por página
(`/js/consentimiento.js`); `pixel.js` solo lo inyecta ese script, tras el consentimiento de
marketing (`banner_propio_v1`).

## Módulos

- `landing.generar` — construye `05-landing/sitio/`. **Con `copy.json`, `paleta.json` y `assets.json`** genera el sitio
  diseñado: las 14 secciones del plano de D5 (plantilla `.claude/skills/d5-landing-checkout/templates/sitio-base/`), CSS con
  variables de la paleta (contraste AA verificado), copy y banner de consentimiento en el `locale`, imágenes de las ranuras
  aprobadas, `/comprar` (estática, con UN formulario `POST /api/sesion`), `/gracias`, las siete legales, `/desistimiento` si la ruta existe en
  `rutas.json` y `_headers` con la CSP (`form-action 'self' https://checkout.stripe.com`).
  **Sin alguno de los tres** cae al sitio mínimo de 5 secciones con un aviso. Todo texto del Maker se escapa (solo
  `**negrita**` y `*énfasis*`); entrada inválida o texto hostil = código 3. Mismas entradas, mismos bytes. Las siete páginas
  legales son **plantilla genérica por idioma** (decisión del dueño, 2026-11-06: sin abogado). Módulos de apoyo: `landing.contenido`
  (esquemas, placeholders, omisiones), `landing.diseno` (paleta -> CSS), `landing.imagenes` (ranuras), `landing.motor`
  (plantillas escapadas), `landing.textos` (rótulos y legales por idioma: es, en, it, pl). Proceso completo: `landing/PROCESO.md`.
  **Dos planos** (`landing.contenido.plano_de`): `referente` (orden y DOM del referente, J20; copy ≥ 0.2.0) y `clasica` (14 secciones, copy 0.1.x). Componentes nuevos:
  barra superior configurable, `==resaltado==`, héroe con mockup grande, tira «qué hay dentro», reseñas de texto con compra verificada, niveles con selector
  (`:target` o `<details>`, sin JS), para quién con íconos, bonus con portada, comparación con el mercado (cifras con fuente), precio, garantía con insignia,
  cómo lo recibes, CTA repetido y botón fijo móvil solo CSS; datos reales (`prueba_social_real.json`, `checkout.precio_programado`); `--vista-previa` (marcadores y
  DEMO, nunca en producción). Detalle: `.claude/skills/d5-landing-checkout/references/landing-estructura.md` §2b y `docs/_historial/modelado-piloto/referentes/analisis-html-axon.md`.
  **Imágenes (J21):** cada imagen con `ilustrativa: true` lleva su rótulo «Ilustración orientativa» y cada una con `etiqueta_ia_visible: true` su rótulo de IA, en el
  idioma del locale (`landing/textos.py`: es, en, it, pl; `copy.rotulos_imagen` los reconfigura y elige `modo: imagen|grupo`); las ilustrativas **se publican**, rotuladas
  (no se omite S04 en producción). Las ranuras `bump` (imagen en la tarjeta del bump) y `portada-pack` (héroe sin mockup; imagen del precio sin escena de compra; con ambas,
  miniatura junto a «qué recibes») tienen sitio. Bonus en rejilla de 2-3 columnas. **`--vista-previa` escribe en `05-landing/sitio-vista-previa/`** (o en `--salida NOMBRE`)
  y nunca en `sitio/` (F-62). Con `05-landing/fuentes_mercado.json` la comparación con el mercado se contrasta por código (F-64).
- `landing.validar` — lint de publicación L1 (oráculo de B0-11: precio/moneda/garantía iguales
  en `oferta`/`checkout`/HTML; enlaces y las siete legales con archivo; sin `<script>` externo o en
  línea salvo el permitido; píxel solo tras consentimiento; sin datos de salud; sin casilla
  premarcada). Reglas de los componentes nuevos: `L1-DEMO` (bloquea cualquier marca de la vista previa), `L1-COMPARACION` (cifras ajenas solo dentro del bloque
  marcado y con `data-fuente`), `L1-BARRA-LANZAMIENTO`, `L1-PRUEBA-SOCIAL`, `L1-RESENA`; el resto del control de precios (`L1-PRECIO`, `L1-MONEDA`) no se relaja.
  Reglas de imágenes y rendimiento: `L1-IMAGEN-ROTULO` (cada imagen ilustrativa o de IA con su rótulo propio o de grupo, y lo que dice `assets.json` sale en el HTML),
  `L1-IMG-ATRIBUTOS` (`width`/`height`/`alt`; `fetchpriority="high"` solo en el héroe, `loading="lazy"` en el resto), `L1-PESO` (imagen ≤ `peso_max_kb` de su ranura,
  HTML ≤ 250 KB, CSS ≤ 100 KB, imágenes de la página ≤ `landing.peso_landing_max_kb`) y `L1-COMPARACION-FUENTE` (cifras de mercado contra `fuentes_mercado.json`;
  en `--produccion` el archivo es obligatorio y la lectura no puede tener más de 30 días). `--carpeta` elige qué carpeta de `05-landing/` se valida.
- `landing.catalogo` — catálogo firmado (HMAC) `oferta_id -> price_id`, esquema
  `contratos/catalogo.schema.json` 1.0.0: `ids_meta{campaign_id|null, adset_ids[], ad_ids[]}` (de
  `07-campana/ids_meta.json`, vacío si aún no existe), `success_url`/`return_url` de `checkout.json` y,
  si `checkout.compra` los trae, `landing_version` y `renuncia{requerido, texto_version}`; la firma
  cubre el JSON canónico sin `firma`. Lo consume el Worker `crear-sesion` (B2); el validador lo
  contrasta con `checkout.json` e `ids_meta.json` (regla X48).
- `landing.desplegar` — publica o revierte `05-landing/sitio/`; dry-run por defecto; re-hash justo
  antes de "subir"; `--entorno produccion` exige sello de X1 vigente.

## CLI

```bash
# Simular la generación: NO escribe nada; valida las entradas y lista los archivos (tamaño y sha256) y los avisos
.venv/bin/python -m landing.generar --oferta OF-202611-01 --raiz /tmp/prueba --simular --json     # alias: --dry-run

# Generar el sitio (por defecto escribe: no es un efecto externo, es HTML local)
.venv/bin/python -m landing.generar --oferta OF-202611-01 --raiz /tmp/prueba --json
# Vista previa del diseño final (SOLO preview: marcadores, opiniones DEMO con cinta y barra fija; L1-DEMO la bloquea y producción la rechaza).
# Escribe en 05-landing/sitio-vista-previa/ (o en --salida NOMBRE); NUNCA en sitio/, que es lo que se valida y se publica.
.venv/bin/python -m landing.generar --oferta OF-202611-01 --raiz /tmp/prueba --vista-previa --hoy 2026-11-07
.venv/bin/python -m landing.validar --oferta OF-202611-01 --raiz /tmp/prueba --carpeta sitio-vista-previa      # solo debe dar L1-DEMO
.venv/bin/python -m landing.desplegar --oferta OF-202611-01 --entorno preview --carpeta sitio-vista-previa --raiz /tmp/prueba

# Lint de publicación (oráculo de B0-11); 0 sin hallazgos, 3 con hallazgos
.venv/bin/python -m landing.validar --oferta OF-202611-01 --raiz /tmp/prueba --json
.venv/bin/python -m landing.validar --oferta OF-202611-01 --raiz /tmp/prueba --produccion --json

# Catálogo firmado (dry-run por defecto; --live escribe 05-landing/catalogo.json)
CATALOGO_HMAC=clave-de-prueba .venv/bin/python -m landing.catalogo --oferta OF-202611-01 --raiz /tmp/prueba --json
CATALOGO_HMAC=clave-de-prueba .venv/bin/python -m landing.catalogo --oferta OF-202611-01 --raiz /tmp/prueba --live --json

# Despliegue (dry-run por defecto; preview sin gate; producción exige sello de X1 vigente)
.venv/bin/python -m landing.desplegar --oferta OF-202611-01 --entorno preview --raiz /tmp/prueba --json
.venv/bin/python -m landing.desplegar --oferta OF-202611-01 --entorno preview --live --raiz /tmp/prueba
.venv/bin/python -m landing.desplegar --oferta OF-202611-01 --entorno preview --rollback-a 2026-11-06T00-00-00Z --live --raiz /tmp/prueba
```

`--simular` (alias `--dry-run`) calcula todo en memoria y reporta, con `--json`: `modo: "simulacion"`, `datos.archivos` (rutas relativas a
`05-landing/`), `datos.detalle` (`ruta`, `bytes`, `sha256` de cada archivo, incluidas imágenes y fuentes copiadas y `rutas.json` si falta),
`datos.total_bytes` y `avisos` (secciones omitidas con su motivo, ranuras sin imagen, fuentes ausentes, idioma sin tabla). El árbol queda
idéntico (lo prueba `tests/landing/test_generar_simular.py` por hash). Con una entrada inválida sale 3 y, con `--json`, imprime
`{"ok": false, "codigo": 3, "datos": {"errores": [...]}}`. La escritura real también calcula todo antes y escribe al final: una entrada
inválida no deja el sitio a medias. (El campo `modo` de la ejecución que sí escribe conserva su valor histórico `"dry_run"`.)

Códigos de salida: `0` correcto · `2` uso (falta `--oferta`, falta la variable de la clave del
catálogo) · `3` validación (hallazgos de `landing.validar`, artefacto de entrada inválido) · `4`
bloqueado (`PAUSA`, entorno fuera de producción, sin sello de X1 vigente).

## Entradas y salidas

- Entradas: `03-oferta/oferta.json`, `05-landing/{checkout.json, tracking.json}`; para el sitio diseñado además
  `05-landing/{copy.json, paleta.json, assets.json}` (validados contra `templates/{copy,paleta,assets}.schema.json` de la skill o, si ya
  existen, `contratos/`; `assets.json` 1.0.x contra `contratos/assets.schema.json`), `04-producto/producto.json` (cifras, entrega, divulgación de IA),
  `mercado.json` (días de desistimiento), `05-landing/rutas.json`, `05-landing/fonts/*.woff2` (opcional, fuentes autoalojadas declaradas en la
  paleta), `checkout.json › compra{…}` y `turnstile{…}` (opcionales), `empresa/parametros.yaml › landing.cookie_{vid,attr}_dias` (opcional) y `empresa/compliance/ayuda_por_pais.yaml` (opcional, `{ayuda_pais}`; formato **provisional**, X1 aún no lo entrega);
  `07-campana/ids_meta.json` (opcional, para `landing.catalogo`).
- Salidas: `05-landing/sitio/**` (HTML, `css/`, `js/`, `imagenes/` y `fonts/` copiados de las ranuras aprobadas), `05-landing/rutas.json`
  (si no existe), `05-landing/imagenes/*` (placeholders del sitio mínimo), `05-landing/catalogo.json` (con `--live`),
  `05-landing/_despliegues/**` (historial de publicaciones, con `--live`).

## Variables de entorno

- `CATALOGO_HMAC` — clave HMAC para firmar `05-landing/catalogo.json` (pruebas y servicio a
  servicio, convenciones §5). **Pedido a B8**: agregarla a `.env.example` cuando corresponda (no es
  mío de tocar esa ruta).
- `FABRICA_ENTORNO`, `FABRICA_RAIZ` — como el resto del sistema (convenciones §1, §9).

## Cómo probar

```bash
.venv/bin/python -m unittest discover -s tests/landing -t .
```

Fixtures propios (no dependen de `ofertas/_ejemplo`): `tests/fixtures/landing/oferta_minima/` (sitio mínimo), `oferta_es_dinero/`
(es-ES, dinero, EUR, con imágenes aprobadas) y `oferta_pl_relaciones/` (pl-PL, relaciones, PLN, hero sin imagen); ambas generan el plano completo,
pasan `landing.validar` con 0 hallazgos y el oráculo de CT. Las pruebas de B0-11 (`tests/landing/test_validar.py`) usan
`tests.contratos.aplicar_mutacion_landing` para aplicar las 8+4 mutaciones sembradas de CT **solo
sobre copias temporales**; `ofertas/_ejemplo` nunca se toca (verificado por hash en la propia
prueba).

## Decisiones

- **Legales genéricas sin abogado.** Las siete páginas legales que genera `landing.generar` son
  una plantilla fija (marca, dominio y días de garantía interpolados); no hay texto legal
  específico por oferta. Decisión del dueño (2026-11-06): son ebooks de bajo riesgo, no se contrata
  revisión legal; el contador fiscal sigue aparte.
- **Monedas con símbolo reconocido limitadas a EUR/USD/GBP** en `landing.generar`/`landing.validar`
  (`_formatear_importe`, `_SIMBOLO_MONEDA`); el resto se muestra como código ISO 4217. Suficiente
  para B0 (el ejemplo es EUR); ampliar con la tabla de decimales ISO 4217 completa cuando haga
  falta soportar JPY/KRW/etc. en una landing real.
- **`landing.desplegar` no reimplementa `engine.guard.comprobar_live`**: no hay una operación
  `publicar_landing` en `engine.guard.OPERACIONES` (ese módulo es de B1 y gira en torno al gasto en
  Meta). En su lugar, `--entorno produccion --live` hace su propio chequeo fail-closed: sin
  `empresa/PAUSA`, `FABRICA_ENTORNO=produccion` y un sello de X1 en
  `empresa/compliance/sellos/` para `etapa_objetivo=D5` cuyo `artefacto_sha256` coincida con el
  hash **recién calculado** de `sitio/` y esté vigente. **No verifica la firma criptográfica del
  sello** (eso es `compliance.verificar`, de B6, que todavía no existe): solo comprueba presencia,
  esquema, hash y vigencia. Pedido a B6 abajo.
- **`landing.catalogo` no llama a Stripe.** Los `price_id` ya existen en `checkout.json` (los crea
  el Maker de D5 o, cuando exista, `infra.alta_oferta`); `landing.catalogo` solo los empaqueta,
  agrega `ids_meta` si `07-campana/ids_meta.json` ya existe, y firma con HMAC (convenciones §5:
  Ed25519 queda para cuando compliance u otra sesión asigne una clave de catálogo propia).
- **`landing.desplegar --rollback-a` en producción no vuelve a exigir sello**: asume que el
  despliegue restaurado del historial ya fue aprobado cuando se publicó la primera vez. Si el dueño
  quiere más rigor (p. ej. exigir una nueva orden firmada también para el rollback), es un cambio
  pequeño y aislado en `landing.desplegar.rollback`.
- **Imágenes: solo ranuras aprobadas.** El sitio diseñado publica únicamente las ranuras `aprobado` de `assets.json` (archivo dentro de
  `05-landing/`, `sha256` y `peso_max_kb` verificados; un SVG con contenido activo se rechaza) y las copia a `sitio/` (el hash de `sitio/` las
  cubre). Sin imagen aprobada el hero usa una portada tipográfica y la sección de muestra se omite; nunca se inventa una captura. El PNG 1×1
  (`PNG_PLACEHOLDER_1X1`) solo lo usa el sitio mínimo.
- **Arranque de pago (decisión de S-A, `docs/_historial/decision-arranque-de-pago.md`).** `/comprar` es estática (`rutas.json`: `estatica:comprar`;
  `/api/sesion` = `dinamica:crear-sesion`) con UN `<form method="post" action="/api/sesion">`: ocultos `oferta_id` y `locale`, casilla `bump` solo con
  `bump_modo = oferta_previa`, casilla `renuncia_desistimiento` solo si `checkout.compra.renuncia.requerido` (sin él, criterio provisional por locale UE/UK, con
  aviso), un botón; nunca premarcadas ni campos de texto. `visitor_id` y parámetros no van en el HTML: `js/consentimiento.js` escribe `fab_vid` y `fab_attr`
  (`fab_vid` = 128 bits en hex; `fab_attr` = `k=v&k=v` ≤ 400 bytes con claves cerradas; `Path=/; SameSite=Lax; Secure`; caducidad de `empresa/parametros.yaml › landing.cookie_{vid,attr}_dias`,
  respaldo 90 y 30 días, tope 395) **solo tras el consentimiento de marketing**. La CSP canónica (`sitio/_headers`; `form-action 'self' https://checkout.stripe.com` exacto) y el formulario los
  comprueba `landing.validar` (`L1-FORMULARIO`, `L1-CSP`).
  Turnstile queda apagado: solo con `checkout.json › turnstile.habilitado = true` se admite UN script externo exacto, solo en `/comprar`. Detalle y choques con el
  oráculo: `PROCESO.md` §5. `desistimiento.html` solo se genera si `/desistimiento` figura en `rutas.json`; `/descarga/<token>` es dinámica: no se genera.
- **`landing.validar`:** reglas nuevas `L1-FORMULARIO` (exactamente el formulario de `/comprar`) y `L1-CSP` (`_headers`; obligatoria si hay `comprar.html`); además
  (cambio mínimo, 2026-11-06): `L1-EJEMPLO-VISIBLE` busca solo el sello `EJEMPLO` en mayúsculas o `[EJEMPLO]` (no la
  palabra corriente «por ejemplo»); `RX_IMPORTE` solo reconoce símbolos y códigos ISO 4217 reales (ya no toma «12 PDF» por un importe) y entiende
  `zł`. Las ocho mutaciones siguen fallando al 100 %.

- **Prueba social real y precio programado: solo datos medidos.** Valoración, ventas y descargas de la muestra se muestran únicamente con
  `05-landing/prueba_social_real.json` (total ≥ 1, con `fuente` y fecha); la barra de lanzamiento, solo con `checkout.precio_programado` de la misma fecha, vigente y con
  precio de después mayor. No hay cuentas atrás que se reinicien, «solo hoy», precios tachados, «+N alumnos» sin dato, capturas de chat ni avisos de «compra
  reciente» (X1 lo veta). La **vista previa** es la excepción acotada: demo con cinta «DEMO», solo con `--vista-previa`, bloqueada por `L1-DEMO` y rechazada por
  `landing.desplegar` en producción.
- **Imágenes ilustrativas y de IA rotuladas (J21).** `landing.imagenes.Imagen` expone `ilustrativa` y `ia_visible`; las plantillas pintan una insignia sobre la imagen
  grande (héroe, compra) o un pie bajo la miniatura (galería, bonus, bump, pack), o un único pie de grupo (`copy.rotulos_imagen.modo: "grupo"`); cada `<img>` lleva
  `data-slot`, `data-ilustrativa` y `data-ia` y `landing.validar` (`L1-IMAGEN-ROTULO`) comprueba rótulo y marcas contra `assets.json`. El `alt` de una ranura aprobada
  tiene que ser real (≥ 10 caracteres, sin el id de la ranura ni un texto genérico).
- **Comparación con el mercado contra fuentes declaradas (F-64).** `05-landing/fuentes_mercado.json` (esquema `templates/fuentes_mercado.schema.json`) declara, por
  fuente, `url` y/o `archivo` capturado (con `sha256`), `fecha` y las cifras observadas; `landing.generar` detiene la generación si una fila de S16 no la respalda
  (nombre + fecha + cifra, y la cifra dentro del archivo capturado) y `landing.validar --produccion` exige el archivo y una lectura de ≤ 30 días. La captura de la fuente
  no la hace D5 (no navega): la produce `capturar_fuente` (F-13) o la lectura del dueño.
- **Comparación con el mercado (F-50).** Cifras de competidores como enteros en unidad menor con `fuente` y `fecha` por cifra (`copy.S16`); `landing.validar` exenta solo
  las marcadas y con fuente; `lint_copy.py` bloquea la fila sin fuente y sigue bloqueando cualquier importe escrito en un texto.
- **Selector de niveles sin JavaScript.** Pestañas con enlaces `#nivel-N` y `:target` (el referente usa JS; la CSP solo admite `consentimiento.js` y
  `L1-FORMULARIO` no admite `<input>` fuera de `/comprar`).

## Pedidos

- **A B6 (compliance):** cuando `compliance.verificar` exista, `landing.desplegar` debe llamarla
  en vez de leer y comprobar el sello de X1 directamente (hoy solo valida esquema, hash y vigencia,
  sin verificar la firma Ed25519/HMAC).
- **A B8 (infra):** agregar `CATALOGO_HMAC` a `.env.example` cuando se regenere (no es mío editar
  esa ruta).
- **A X1:** `empresa/compliance/ayuda_por_pais.yaml` no existe; `landing.generar` lo lee con un formato provisional (`PL: {texto: …}`) para
  `{ayuda_pais}`. Confirmar el formato.
- **A S-B (Worker `crear-sesion`):** leer `fab_vid` y `fab_attr` (`k=v&k=v`, claves `utm_source|medium|campaign|content|term`, `cid`, `asid`, `adid`) y `_fbp`/`_fbc`;
  aceptar el formulario (`oferta_id`, `locale`, `bump`, `renuncia_desistimiento`; el atributo `data-texto-version` de la casilla no se envía) y responder 303.
- **A CT-3 / S-A:** `checkout.json › compra{ruta, metodo, bump_modo, renuncia{requerido, texto_version}, landing_version}` y `turnstile{habilitado, sitekey}` (opcionales,
  aditivos); `landing.cookie_vid_dias` y `landing.cookie_attr_dias` en `parametros.yaml`; el oráculo debe admitir el formulario (`L1-FORMULARIO`) y el script de
  Turnstile solo con el flag (`L1-SCRIPT-EXTERNO`). Ver `PROCESO.md` §5.
- **A S-A (contratos), generador de landing:** `checkout.precio_programado{fecha, precio{monto, moneda}, price_id?}` (opcional, aditivo: la landing lo lee para la barra de
  lanzamiento y `landing.validar` lo cruza) y el esquema de `05-landing/prueba_social_real.json` (hoy propuesta en `templates/prueba_social_real.schema.json`). Ver
  `docs/_historial/coordinacion-sesiones.md`, «Avisos de S-C — generador de landing».
- **A S-B:** productor de `prueba_social_real.json` (ventas completadas de Stripe, descargas de la muestra del registro de entrega y valoración de reseñas verificadas, con
  fuente y fecha; total 0 si no hay) y regeneración de la landing al cruzar la fecha de la barra de lanzamiento.
- **A S-A (contratos), assets:** `contratos/assets.schema.json` (1.0.x) no admite `ratio: "1.91:1"` (og 1200×630), un `productor` para imágenes de Kie.ai (`kie` / `ranuras_kie`)
  ni los campos `ilustrativa`, `reemplazar_con_real_cuando_exista_producto` y `revision_ciega`; el generador ya los acepta en la versión 1.1.x de la skill
  (`templates/assets.schema.json`). **A S-B:** `capturar_fuente` (F-13) como productor de `05-landing/fuentes_mercado.json` + `fuentes/*.txt`, y la regla de X1 para comparaciones
  de precio (misma categoría, fuente, vigencia máxima de 30 días: F-65).
