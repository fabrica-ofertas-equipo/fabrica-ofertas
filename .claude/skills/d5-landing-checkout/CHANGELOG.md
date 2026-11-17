# CHANGELOG — d5-landing-checkout

v0.2 sin pulir (alineada con J6-J21 el 2026-11-07; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).

Formato SemVer. Todo cambio de la skill lo aprueba el dueño (gate H hasta N2; esta skill publica y configura el cobro, así que también en N3/N4) y nace de un caso de `evals/` (eval primero).

## 0.2.1 — 2026-11-07 — análisis del HTML con `modelado-oferta` y costura con D10 (PENDIENTES A5)
Sigue siendo **v0.2 sin pulir**. Origen: `.claude/skills/modelado-oferta/PENDIENTES.md` sección A. `analizar_html.py` **ya existe** (skill `modelado-oferta` 0.1.x).
**Aplicado**
- **A5** `SKILL.md` paso **0b**: se quitó «si existe —hoy no existe—»; el Maker lee `ofertas/<id>/modelado/{esqueleto_html.json, mapa_ranuras.json, esqueleto_funnel.json}` (el script produce los dos primeros con `--no-red --salida`; `esqueleto_funnel.json` lo escribe `modelado-oferta` en MOD-1) y, sin ellos, el análisis manual de `referentes/analisis-html-axon.md`; en «Entradas», el referente modelado es `ofertas/<id>/modelado/`. `references/proceso-landing.md` §2a y la fila 0b y 13, y `references/dependencias.md`: quitado «hoy no existe» y registrado `[PENDIENTE: chequeo L1 por código que compare el orden y los bloques del HTML generado con esqueleto_funnel.json › plano_objetivo]` (`modelado_estructura`).
- **Costura D10 → D5:** la curación de reseñas reales que alimenta `prueba_social_real.json` la propone `d10-poscompra` (modo RESENAS); D5 solo la lee.
- `.claude/agents/d5-maker.md`: el método 0b lee los archivos de `modelado/` (el Maker no ejecuta `analizar_html.py`: no está en su lista blanca).
**Falta (bloqueado: S-B)** el chequeo `modelado_estructura` y el alta de `analizar_html.py` en `agentes/hooks/herramientas.yaml`. Ver `modelado-oferta/PENDIENTES.md` A5 y B.

## 0.2.0 — 2026-11-07 — alineación con el plano `referente`, los datos reales, la escalera de precio, las imágenes de ranuras y el método de HTML (J6-J21)
Sigue siendo **sin pulir**: la 1.0.0 exige una corrida manual del dueño con una oferta real, su retro y el DoD firmados por él. Fuentes: `docs/_historial/mentor-sistema/decisiones-del-dueno.md` (J6, J7, J11, J13, J16-J21 y la nota sobre testimonios y urgencia falsos), `landing/README.md` y `landing/PROCESO.md`, `docs/_historial/modelado-piloto/` (`estructura-funnel-referentes.md`, `referentes/analisis-html-axon.md`, `piloto-bitacora-d3.md`: F-40…F-82), la práctica real `ofertas/OF-202611-91/05-landing/` y `scripts/imagenes/`.

**Aplicado en la skill (texto)**
- **Plano `referente` por defecto (J17/J18/J20).** `SKILL.md`, `proceso-landing.md` §2 y §A, `landing-estructura.md` §2b, `copy-por-seccion.md` §3b: cuándo se usa (copy ≥ 0.2.0 o `estructura: "referente"`; `clasica` solo sin referente o copy 0.1.x), orden de bloques (barra → héroe → qué hay dentro → reseñas → niveles → para quién → bonus → comparación → precio → garantía → cómo lo recibes → FAQ → CTA final → pie), qué campo del copy 0.2.0 alimenta cada bloque y qué se omite sin dato real. Plantilla del brief con «Plano modelado» y columnas de datos reales.
- **Método de HTML del referente (J20).** Paso nuevo 0b (`proceso-landing.md` §2a): analizar el HTML del referente antes de redactar (`modelado-oferta/scripts/analizar_html.py` si existe —hoy no—; si no, el análisis manual de `analisis-html-axon.md`) y partir del plano modelado; estructura sí, expresión no (J13); tácticas inventadas del referente → su versión legítima. **Impulstienda queda PENDIENTE del dueño**: no se asumen capacidades (regla dura 12, `preguntas-abiertas.md` §6).
- **No se inventan datos (PAL-16 reformulada, F-51; nota de J19).** Tabla «Datos reales» en `SKILL.md` y `claims-rojos.md` §2b: urgencia solo con `checkout.precio_programado` real; valoración, contador y reseñas solo desde `prueba_social_real.json` / `compra_id`; demo solo en `--vista-previa`, bloqueado por `L1-DEMO` y rechazado en producción; ancla solo con comparación de mercado con fuente y fecha por cifra (S16) o precio realmente cobrado. Sin beta previa. No se construyen cuentas atrás que se reinicien, «solo hoy», precio tachado, «+N alumnos», capturas, avisos de compra ni testimonios con IA.
- **Precio por escalera (J16).** `proceso-landing.md` §5: el frontal es el peldaño 17/19/27 US$ que fijó D3; D5 solo lo traza (C02) y devuelve a D3 si no encaja; bump implementado; upsell y postpago pendientes (no se inventan).
- **Imágenes de ranuras (J21).** `proceso-landing.md` §3b y `landing-estructura.md` §5.2: D5 declara y encarga; producción con Kie.ai por `scripts/imagenes/` (D6), referencias planas propias, composición por código para mockups de varias portadas, tope de créditos y gasto previo registrado, máx. 3 intentos por ranura; **revisión ciega** por `d5-qa` en modo QA-I; base ilustrativa mientras D4 no entregue, estricta en títulos, cifras y nombres; reglas de texto en imagen y de límites (nada del referente como entrada). Esquema `assets` 1.1.1: `ilustrativa`, `reemplazar_con_real_cuando_exista_producto`, `revision_ciega`.
- **Checks C01-C17** (`checks-c01-c17.md`): sin ids nuevos; C02 suma `L1-COMPARACION`, `L1-BARRA-LANZAMIENTO` y `D5-COPY-COMPARACION-*`; C03 suma `L1-DEMO` (BLOQUEANTE), `L1-PRUEBA-SOCIAL` y `L1-RESENA`; sección «Cambios de la 0.2.0» con los juicios que ningún código cubre aún (comparación justa, fidelidad al plano, ilustrativa en producción).
- **Rúbrica** (`rubric.md`): R1-R8 con ids fijos y criterios nuevos dentro de R3 (calidad de imágenes y revisión ciega), R5 (datos reales), R6 (fidelidad al plano modelado), R7 (precio de la escalera) y R8 (voz del mercado sin revisor nativo); sección «Revisión ciega de imágenes (QA-I)».
- **Fricciones F-40…F-82 que son de la skill** (`preguntas-abiertas.md` §5, con estado hecho/regla/pendiente) y **preguntas abiertas del dueño** (§6). `dependencias.md` §5: pedidos consolidados a S-A, S-B, S-C y el dueño.
- **Agentes** `d5-maker` y `d5-qa`: rol, lecturas, escrituras, reglas duras, salida y rúbrica con lo anterior; el QA añade el modo de revisión ciega de imágenes.

**Aplicado en la skill (código, con prueba nueva)**
- `scripts/prechequeo.py`: el revisor nativo ya no bloquea (J11, F-41); **P-06c** es un aviso.
- `templates/copy.schema.json`: `contexto_riesgo.macro_nicho` admite `habilidades_hobbies` (J6/J9, F-45).
- `templates/paleta.schema.json`: `tipografia.*.archivos` puede ir vacío mientras no existan los `.woff2` (F-55).
- `templates/assets.schema.json` 1.1.1-propuesta: `ilustrativa`, `reemplazar_con_real_cuando_exista_producto`, `revision_ciega{ronda, veredicto, informe_ref}` (F-71, F-75).
- `scripts/test_scripts.py`: clase `TestV020` (5 pruebas nuevas: revisor nativo, esquemas, assets con ilustrativa, comparación de mercado con fuente y fecha, importe ajeno en un texto).

**No se tocó:** `landing/`, `templates/sitio-base/`, `tests/`, contratos, engine, empresa, ofertas ni otras skills. Los pedidos que exigen cambiar código ajeno están en `references/dependencias.md` §5 y en `docs/_historial/coordinacion-sesiones.md` («Avisos de S-C — skill D5 0.2.0»).

**Pruebas:** `tests/landing` 282 OK (sin cambios) · `scripts/test_scripts.py` de la skill 22 OK (eran 17).

**Qué falta para 1.0.0 (además de lo de la 0.1.0):** una corrida con D4 real y un referente analizado con el método de HTML (sin ranuras `ilustrativa` en producción); el chequeo por código `modelado_estructura`; el script `analizar_html.py` (skill `modelado-oferta`); el productor de `prueba_social_real.json`; `precio_programado` en el contrato; upsell y postpago; la respuesta del dueño sobre Impulstienda; las imágenes de una oferta real aprobadas por revisión ciega e integradas en `assets.json`. Evals (eval primero en la próxima pasada): un dorado `referente` (copy 0.2.0, S16 con fuente y fecha) y sembrados nuevos SD5-26…: demo en un `sitio/` de producción (`L1-DEMO`), fila de S16 sin fuente o sin fecha, valoración o contador sin `prueba_social_real.json`, barra de lanzamiento sin `precio_programado`, ranura `ilustrativa` como muestra real, imagen con título o cifra alterada, precio distinto del de D3, revisor nativo exigido, expresión del referente (nombre de bonus, cifra) en el copy. El catálogo actual (25 sembrados, 24 detecciones) no se tocó para no romper la siembra rotada.

## 0.1.1 — ajustes por la ingesta de S-A (SC-1…SC-9, SC-14)
Sigue siendo v0.1 sin pulir. Origen: `docs/_historial/ingesta-skills-cierre.md` §1 (D5) y §3.2.
- **SC-1 / SC-2:** el QA no corrige ni aplica parches (`correccion` por hallazgo, `devuelto_al_maker`, `cambios_aplicados = []`; el Maker corrige en la ronda siguiente); solo lectura (`Read, Grep, Glob`); su L1 llega en `ofertas/<id>/qa/.l1/d5-v<n>.json` y, sin él, «evidencia ausente» es MAYOR o BLOQUEANTE. Retirados la rama `qa/` y la inconsistencia I-2.
- **SC-3 / SC-7:** nivel de riesgo con `python -m scripts.nivel_riesgo` (`nivel`, `subnivel` aparte, `ejes_codigo`; sin `ejes_codigo`, 2 o más amarillos = B `[SUPUESTO]`); `prechequeo.py` usa `riesgo.subnivel`/`colores`; comandos reales `python -m compliance.lint_claims|html_checks` y `engine.orq firmar` (`--hash-objetivo`, `--clave-privada`, la clave nunca en chats ni en el repositorio).
- **SC-4:** agentes sin web ni `mcp__*`; `ads_get_datasets`, `ads_get_dataset_stats` y `ads_pixel_event_read` solo en la sesión interactiva del dueño (llegan como entrada).
- **SC-5 / SC-14:** ranuras con `productor` ∈ {D4, D6, dueño}, `herramienta` y `etiqueta_ia_visible`; retirados `html_png`, `captura_producto`, `higgsfield`, `comprador_real` y `creditos_estimados`, `cotizacion_ref`, `prompt_ref` de los ejemplos, el dorado `pl-PL`, la ficha, el brief y el proceso (el esquema `templates/assets.schema.json` los conserva solo como obsoletos, mientras los fixtures de `tests/landing` del constructor los usen: `dependencias.md` §1). El render HTML→PNG es de `render_estatico.py` de D6; D5 declara ranuras y no cotiza (sin Higgsfield ni créditos en dependencias, preguntas ni proceso). «Pedido de imágenes» pasa a «Encargo de ranuras».
- **SC-14:** el dato del alta es `ofertas/<id>/infra/alta.json` (no `alta-oferta.yaml`) en `SKILL.md`, `proceso-landing.md` y `prechequeo.py --alta-oferta` (la bandera conserva el nombre por la lista blanca de hooks; lee `infra/alta.json` por defecto; avisos P-11 y P-11b); QA-A en `qa/d5-v<n>-previo.json` `[PENDIENTE: LT-43]`; la skill apunta a `landing/PROCESO.md` y a `consentimiento.js` y al generador de `landing/`, que ya existen.
- **Coherencia con la decisión de pago:** `/comprar` estática con UN formulario `POST /api/sesion`, cookies `fab_vid` y `fab_attr`, CSP canónica con `frame-src`, `checkout.compra{renuncia{requerido, texto_version}, landing_version}` y `turnstile` `[PENDIENTE: LT-39]`, bump v1 `oferta_previa` sin evento `bump_visto`, `/desistimiento` como página propia.
- **SC-9:** v1.0.0 exige corrida manual, retro y DoD firmados. **SC-6 y SC-8:** no aplican / ya cumplidos (`landing.umbral_qa`).
- `dependencias.md` reescrito con el estado de los ítems D5 del cierre (resueltos, INEXACTOS D5-10/19/22, derivados a CT-3, CT-4, S-B y dueño). `evals/sembrados` cita `qa/.l1/d5-v<n>.json`. Pruebas: 17 en verde (3 nuevas de prechequeo y 1 de ranuras).

## 0.1.0 — 2026-11-06 (borrador)
Generada por la sesión de forja de D5 a partir de `departamentos/06-landing-checkout.md` (§4 SOP, §5-6 agentes, §10.1-10.5, anexo A1-A5), backbone v2.2, `docs/03` §2, `docs/09` §9, marco 25 y la landing de referencia de Fer (solo estructura).

**Qué trae**
- `references/proceso-landing.md`: el proceso determinado de punta a punta (pasos 0-11), plano fijo de 14 secciones, sistema visual y paleta, 20 ranuras de imagen con productor, copy, checkout y bump, tracking, legales desde plantilla, QA, preview y gates, ciclo de pulido del dueño, tabla por idioma y nicho, checklist W1 y decisiones a validar.
- `references/` complementarias: estructura, copy por sección, Stripe, tracking, legales, claims rojos, locales, mapa C01-C17, sembrados, dependencias, preguntas abiertas.
- `rubric.md` (R1-R8 con anclas, L3), `templates/` (ficha, brief y copy/paleta/assets de ejemplo válidos para `_ejemplo`, esquemas propuestos de copy/paleta/assets, bitácora y prueba de 5 s), `scripts/` (`prechequeo.py`, `lint_copy.py`, `contraste_paleta.py` y sus pruebas), `evals/` (10 dorados o bloqueos esperados, 25 sembrados SD5, un dorado completo `pl-PL` de relaciones).
- Agentes `d5-maker` y `d5-qa`.

**Verificado:** 13 pruebas de scripts en verde (dorados limpios en `es-ES` dinero y `pl-PL` relaciones; 24 siembras detectadas; prechequeo sobre `_ejemplo`); JSON de templates/evals válidos contra sus esquemas propuestos.

**Qué falta para 1.0.0**
1. Una corrida manual del dueño con una oferta real o `_ejemplo` en otro locale, retro de 30-45 min y bitácora de `Pulido` (docs/03 §2).
2. ~~El generador mejorado de `landing/`~~ ya existe (0.1.1); falta probarlo con una oferta real: hasta entonces el paso 7 y C01/C03/C10/C16 sobre un `sitio/` real son `[NO PROBADO]`.
3. Checklist W1 (`proceso-landing.md` §12): 2 ofertas de nicho y locale distintos de punta a punta, capturas de 390 px y 1440 px revisadas por el dueño y las 8 mutaciones de CT fallando en `landing.validar`.
4. Playwright, Lighthouse, axe y `fonttools` instalados; `l1-resultados.json` producido por el runner; Workers y `postcompra/` probados.
5. Pedidos a otros en `references/dependencias.md` (CT-3, CT-4, S-B, X1, M1, D0, D4, D10) y decisiones del dueño de `references/preguntas-abiertas.md`.
6. Evals de otros idiomas y nichos construidos con artefactos (DG-01 `it-IT`, DG-03 `en-CA`, DG-05 `es-AR`: hoy solo especificados) y calibración del QA con siembra rotada, ≥ 90 % de bloqueantes.
7. Calibrar los límites de longitud, el umbral de la prueba de 5 s y los píxeles de las ranuras `[HIPÓTESIS]`.
8. Revisión nativa de los textos en polaco, italiano, francés, alemán y rumano.
