# Preguntas abiertas y supuestos de la v0.1

> v0.2.0 sin pulir (alineada el 2026-11-07; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño). Lo nuevo: §5 (fricciones F-40…F-82 que son de la skill) y §6 (preguntas abiertas del dueño de la 0.2.0, con Impulstienda).
> El §10.1 de la spec pide «preguntas bloqueantes primero»: aquí están, con el `[SUPUESTO]` que se adoptó para avanzar sin esperar. Cuando el dueño responde, se actualiza esta tabla y `CHANGELOG.md`. Las preguntas de la spec §11 se repiten porque condicionan el copy y la configuración. Las del dueño ya están registradas en `docs/00-decisiones-y-tareas-del-dueno.md` (Decisión DD, §3-§4); esta tabla no las sustituye.

## 1. Bloqueantes para publicar (no para construir en preview)

| # | Pregunta | Por qué bloquea | `[SUPUESTO]` adoptado | Responde |
|---|---|---|---|---|
| Q1 | **Entidad y datos legales públicos** de la LLC: razón social, dirección (puede ser oficina virtual), ID fiscal, correo de contacto | `/legal/vendedor`, pie y S08 los exigen (L-01); sin ellos el prechequeo devuelve `preguntas` | ninguno: no se inventan | dueño (D0) |
| Q2 | **Régimen fiscal** (hoy `diferido`): Stripe Tax con registro OSS/UK, Managed Payments (+3,5 %) o seguir diferido con exposición acotada | condiciona «precio final» frente a «IVA incluido» y qué métodos locales se reabren | texto «precio final»; nunca «IVA incluido» | dueño + contador |
| Q3 | **Moneda y precio** por mercado y **garantía** (≥ `limites.politica_reembolso_dias`; ¿14 o 30?) | C02 compara contra `oferta.json` | lo que trae D3 | dueño (D3) |
| Q4 | **Países de segmentación** y `locales_permitidos` de `limites.yaml` (hoy vacíos: nada se lanza) | el prechequeo avisa y D7 no activa | preview sin restricción | dueño (W7) |
| Q5 | **Dominio**, dataset/píxel y token de la API por oferta (`ofertas/<id>/infra/alta.json`, que escribe `infra.alta_oferta`; todos sus pasos son del dueño) | sin ellos no hay `checkout.json` ni `tracking.json` reales | `_ejemplo` con dominios `.example` | dueño (D0) |
| Q6 | **Ayuda por país** vigente (≤ 180 días) para relaciones, duelo y ruptura, y para todo producto de conflicto de pareja o familia | C15; aviso de seguridad y bloque «Si necesitas ayuda ahora» | `{ayuda_pais}` queda como placeholder | X1 + dueño |
| Q7 | ¿El **píxel de conversión** es admisible en salud y dinero o va **solo por API**? (riesgo residual sin dueño legal: lo fijan las reglas de X1 y la decisión del dueño) | cambia `tracking.json` (canales) y si se genera `pixel.js` | píxel con consentimiento (`banner_propio_v1`) | dueño |
| Q8 | **Correo transaccional** (SPF/DKIM/DMARC) y buzón de soporte | C08 (recibo y correo neutros) | fuera de D5 | dueño (D0/D10) |

## 2. Decisiones de proceso a validar (copia de `proceso-landing.md` §13)
1. Números solo por placeholders con traza. 2. Plano `referente` por defecto (J17/J18/J20) y `clasica` solo sin referente; prueba honesta sin opiniones inventadas. 3. D5 declara y encarga las ranuras de imagen (J21): se producen con Kie.ai, las revisa a ciegas un agente independiente y mientras D4 no entregue son una base ilustrativa. 4. Un ángulo = una ruta, banner idéntico en todos los países. 5. «Listo» = 5 segundos con 3 personas + compra de prueba en el celular, en ≤ 3 sesiones.

## 3. Preguntas de la spec §11 que siguen abiertas
- **Métodos locales** (BLIK/PLN, Satispay/EUR…): cuándo reabrirlos; capturar las pestañas «Deshabilitado» y «Se requiere una acción» de Stripe; Adaptive Pricing frente a `currency_options`.
- **Garantía mayor de 14 días** (palanca opcional, nunca atada a un resultado) y revocar el enlace al reembolsar (propuesta: sí, lo implementa D10).
- **Bump desde el día 1** (07h) o prueba sin bump; `Purchase` neto (propuesto); upsell: no en v1.
- **Compra manual de Stripe solo si cambia la plantilla de checkout** desde N3 (`compra_real_minima` queda en H siempre).
- `[VERIFICAR]`: requisitos de destino de Meta; art. 16(m) de la Directiva 2011/83/UE y art. 11a de la 2023/2673 (desistimiento, 2026-06-19); AR Disp. 954/2025; `optional_items` con Managed Payments; charset de `client_reference_id`; Apple Pay en el navegador integrado de Instagram/Facebook; placeholder del id de sesión en `success_url`.

## 4. Supuestos principales de esta v0.1
- **[SUPUESTO]** copy, paleta y assets son el contrato de entrada del generador de `landing/` (propuesta de D5; sin esquema normativo hasta CT-4 y LT-48).
- **[SUPUESTO]** los límites de longitud, el umbral de 2 de 3 lectores en la prueba de 5 segundos y los píxeles de las ranuras son valores iniciales a calibrar con el pulido.
- **Resuelto (decisión de arranque de pago):** `/comprar` es una página estática con UN formulario `POST /api/sesion`; `/api/sesion` es la ruta dinámica del Worker. Las casillas viven en ese formulario.
- **[SUPUESTO]** la ranura `og` la produce D6 (estático HTML→PNG con `render_estatico.py`); la spec no la asigna de forma explícita.
- **[SUPUESTO]** al lanzar no hay prueba social real; S08 corre en modo `honesta` y no hay valoración ni contador (sin beta previa: las primeras reseñas reales llegan con las ventas del propio test).
- **[SUPUESTO]** el navegador integrado de Instagram/Facebook se reproduce abriendo el enlace desde Messenger o una publicación privada.
- **[SUPUESTO]** textos en polaco, italiano, francés, alemán y rumano de los ejemplos y de `locales.md` son orientativos y sin revisor nativo (J11: ya no es requisito; se compensa con inmersión del mercado, retraducción y segunda lectura de IA).
- **[SUPUESTO]** la skill lleva `disable-model-invocation: true`: D5 cubre publicación y configuración de checkout; el Maker la precarga por `skills:`; el dueño la invoca como `/d5-landing-checkout`.
- **[SUPUESTO]** para las pruebas sin Playwright, el dueño hace las capturas de 390 px y 1440 px a mano (o con Chrome sin pantalla, `landing/PROCESO.md` §4).

## 5. Fricciones del piloto (F-40…F-82) que son de la skill: cómo quedan en la 0.2.0

Fuente: `docs/_historial/modelado-piloto/piloto-bitacora-d3.md` («D5 en práctica», «ronda 2», «Imágenes con Kie» rondas 1 y 2). Aquí solo las que tocan a la skill (reglas, esquemas, scripts, textos); las de contratos, motor y generador están en `dependencias.md` §5. Estado: **hecho** (ya en la skill) · **regla** (documentada, sin código) · **pendiente** (falta código o decisión de otro).

| # | Qué pasó | Cómo queda en la skill 0.2.0 | Estado |
|---|---|---|---|
| F-40 | Sin `producto.json` (D4 no corrió) el prechequeo bloquea y no hay modo práctica oficial | `proceso-landing.md` §0 «Modo práctica»: stubs `[PRÁCTICA]`, raíz con enlaces simbólicos, `aprobada_por_dueno = null`, sin publicar | regla; `prechequeo.py --practica` y `landing.generar --producto` pendientes (S-C) |
| F-41 | `prechequeo.py` seguía bloqueando por «sin revisor nativo» aunque J11 lo retiró | P-06 ya no incluye el revisor; aviso **P-06c**; proceso, rúbrica R8, SKILL regla 9. Prueba nueva en `scripts/test_scripts.py` | **hecho** en la skill; `X32_REVISOR` en `scripts/validar_esquemas.py` pendiente (S-A/S-B) |
| F-43, F-44, F-52 | falsos positivos («według», «zwrot pieniędzy») y falsos negativos pl-PL del control de X1 | `claims-rojos.md` §2b y `checks-c01-c17.md` («falsos positivos / negativos conocidos»): el QA no da por verde el lint pl-PL y lee a mano los `claims_prohibidos` | regla; calibración de X1 pendiente (S-B) |
| F-45 | `habilidades_hobbies` no existía en esquemas | `copy.schema.json` admite el 4.º macro-nicho; filas en `proceso-landing.md` §11 y `claims-rojos.md` §3 (avisos finos: X1) | **hecho** en la skill; `comunes.schema.json` pendiente (S-A) |
| F-46 | BLIK/Przelewy24 no caben en `checkout.metodos` ni en `mercado.metodos_pago` (45-55 % del pago en PL) | `dependencias.md` §5; el preview lista solo tarjeta, Apple Pay, Google Pay y Link | pendiente (S-A, M1) |
| F-47…F-51 | el generador no tenía barra, CTA entre bloques, orden configurable, selector, comparación ni palancas legítimas | resueltas por el generador del 2026-11-07; la skill se alineó: plano `referente`, S15/S16, `precio_programado`, `prueba_social_real.json`, `--vista-previa`, L1-DEMO (SKILL, `copy-por-seccion.md` §3b, `landing-estructura.md` §2b, `checks-c01-c17.md`). PAL-16 reformulada en `claims-rojos.md` §2b. **F-48 queda a medias:** la tira «qué hay dentro» ya existe, pero el sitio sigue sin ruta de **descarga gratuita de una muestra** (`L1-FORMULARIO` prohíbe formularios y enlaces fuera de `/comprar`) | **hecho**, salvo la descarga de muestra (pendiente S-C/S-B) |
| F-53 | `checkout.compra` y `assets` 1.1.x fallan los esquemas de `contratos/` | se sigue usando el esquema de la skill (`templates/*.schema.json`) | pendiente (S-A, CT-3) |
| F-54 | `{formato:id}` expande el literal (`pdf_a4`) | `copy-por-seccion.md` §1: se escribe «PDF A4» a mano en el texto | regla; generador pendiente |
| F-55 | `paleta.schema.json` obligaba a declarar `.woff2` que no existen | `tipografia.*.archivos` puede ir vacío; prueba nueva | **hecho** |
| F-56, F-62, F-59 | `landing.generar` lee `producto.json` fijo, no tiene `--salida` y el mockup del héroe sale vacío en vista previa | `proceso-landing.md` §0 y §9 (rodeo documentado) | pendiente (S-C) |
| F-57 | un hook de ángulo contiene una frase de `claims_prohibidos` | el Maker reformula el hero y lo anota en `contexto_riesgo.hero_reformulado`; D3 corrige el hook | regla |
| F-58 | no hay petición de reseña postcompra ni fuente de datos para contador y reseñas | `dependencias.md` §5 (D10/S-B); mientras tanto S08 `honesta` | pendiente (S-B) |
| F-60, F-71 | `assets.json` quedó con los bonus y el `alt` de la v1 y `productor: D4` aunque las produce Kie | `proceso-landing.md` §3b.7: al cambiar la oferta se rehace `assets.json` antes de aprobar imágenes; `productor: D6` con `herramienta` Kie.ai; esquema con `ilustrativa`, `reemplazar_con_real_cuando_exista_producto` y `revision_ciega` | **hecho** (regla + esquema) |
| F-61 | el reparto por nivel solo vive en `oferta.md` | `cifras_con_traza` con traza a `oferta.md` `[SUPUESTO]` | regla; `entregables[].distribucion` pendiente (S-A) |
| F-63 | `D5-COPY-TESTIMONIO` marca una frase honesta que nombra las opiniones | se redacta sin la palabra (`proceso-landing.md` §4, `claims-rojos.md` §2b) | regla; afinar el lint (S-C) |
| F-64, F-65 | las cifras de S16 vienen del dossier sin releer y nada comprueba que la comparación sea justa | `proceso-landing.md` §4: relectura (dueño o `capturar_fuente`) antes de publicar, misma categoría, vigencia ≤ 30 días; juicio del QA en R5 | regla; `capturar_fuente` y regla de X1 pendientes (S-B) |
| F-66 | `precio_programado` documentado pero sin esquema ni `Price` programado | `proceso-landing.md` §5 «Precio programado» | pendiente (S-A, S-B) |
| F-67 | Chrome headless no baja de ~500 px de ancho | capturas a 390 px con un `iframe` de 390 px y recorte (`landing/PROCESO.md` §4); Playwright sigue pendiente (SB-18) | regla |
| F-68, F-69, F-79, F-82 | el estimado de créditos de `kie.py` queda corto; la clave Kie es compartida | `proceso-landing.md` §3b.4: cotizar con el mayor entre estimado y medido, controlar el tope con `creditsConsumed`, el envío a Kie cuenta como intento (las composiciones por código y los finales no gastan) | regla; ledger común (dueño, S-A) |
| F-70, F-77, F-78, F-81 | el texto pequeño generado por IA falla; la regla «nunca texto dentro de la imagen» chocaba con el encargo | `landing-estructura.md` §5 y `proceso-landing.md` §3b.3 y 3b.8: texto solo desde referencia plana propia con OCR en verde; mockups de varias portadas compuestos por código; la escena es IA (`ia_generado: true`, etiqueta visible) | **hecho** (regla) |
| F-72, F-73, F-74, F-80 | modelo según el caso; OCR con Vision de macOS; tipografía de las portadas ≠ la de la página; margen de la portada del móvil | `proceso-landing.md` §3b.3 y 3b.10 | regla; `.woff2` y portadas (S-C) |
| F-75 | las miniaturas ilustrativas no deben ir a producción como «muestra real» | `proceso-landing.md` §3b.9, `rubric.md` R3, `checks-c01-c17.md`: BLOQUEANTE si una ilustrativa aprobada se usa como muestra real en producción | regla; estado `ilustrativa_aprobada` y etiqueta visible en el generador pendientes (S-C, X1) |
| F-76 | una tarea de Kie puede quedarse en `generating` varios minutos | `ranuras_kie.py` guarda el `task_id` al instante; se retoma con `Kie.recuperar` sin pagar de nuevo | hecho (script) |

## 6. Preguntas abiertas del dueño de la 0.2.0 (ninguna bloquea construir en preview)

1. **Impulstienda (J20) — PENDIENTE.** El dueño pidió copiar el HTML del referente «en otro lugar donde diseñaremos las landings, que será Impulstienda». Antes de asumir nada: ¿admite **HTML personalizado o embebido**?, ¿**API o webhooks**?, ¿qué **pasarelas** (Stripe, BLIK, Przelewy24)?, ¿**varios idiomas y monedas**?, ¿**dominio propio**?, ¿**píxel con CAPI y UTM**? `[SUPUESTO]` hasta que responda: la landing sigue siendo propia con Stripe (J7); el esqueleto HTML sirve para ambos destinos. **Si migra**, hay que rediseñar C01 (build y enlaces), el sello del sitio por hash, el catálogo firmado, `L1-FORMULARIO`/`L1-CSP` y el arranque de pago, y J7 queda revertida parcialmente (S-A/S-B).
2. **Plano sin referente.** ¿`clasica` sigue siendo el plano cuando una oferta no tiene referente que modelar (modos pain-first de D1), o se usa igualmente el `referente` con la estructura común de `estructura-funnel-referentes.md` §3? `[SUPUESTO]` hasta que responda: `clasica`.
3. **Tramo no visible del funnel (J17).** Checkout, bump, upsell, postpago, gracias y email del referente no se ven sin comprar; lo nuestro de ese tramo son decisiones propias de D5. Para verlo sin gastar: llegar a la pantalla de pago sin pagar y mandar capturas.
4. **Upsell y postpago (J16).** Hoy D5 solo implementa el bump. ¿Cuándo entran al contrato y al flujo de `/comprar` y `/gracias`? (S-A/S-B; el upsell de un clic solo con tarjeta, no con BLIK).
5. **Tope de créditos de imágenes.** 900 por ronda (≈ 4,5 US$) `[SUPUESTO]`; ¿el dueño quiere otro tope, o una aprobación por oferta?
6. **Medida del `og`.** 1200×630 (Open Graph) frente a 1200×675 de `assets.json`: una sola medida.
7. **Etiqueta de IA en las imágenes** (`declarar_siempre`): la añade la página, no la imagen; falta el componente visible (F-81).
8. **Reseñas reales automatizadas.** La canalización (petición automática tras cada compra real) es de D10/S-B; hasta que exista, S08 va `honesta`.

