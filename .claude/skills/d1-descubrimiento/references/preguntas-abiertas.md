# Preguntas abiertas de D1 (bloqueantes por encargo y decisiones del dueño)

## A. Preguntas bloqueantes por corrida (máx. 8; las haces **primero** y esperas la respuesta; sin ellas no hay consulta)
1. ¿Qué modo: **A** radar abierto, **B** dado un nicho (¿cuál?), **C** dado un problema tuyo (¿cuál?) o **D** modelado de ofertas? (¿barrido nuevo o fichas del barrido `AAAA-MM-DD-<letra>` que ya existe?)
2. ¿Qué `locale` y qué países de segmentación? (una corrida de snapshot = un locale; ningún país es prior). ¿Está en `limites.locales_permitidos` (hoy vacío)?
3. ¿Moneda de cobro, rango de precio y formatos permitidos? ¿`N_top`?
4. ¿`limites.max_consultas_biblioteca`, `max_barridos_por_semana`, `max_busquedas_por_barrido`, `max_costo_por_barrido` y `fuentes_permitidas` (hoy en `null`/vacío)? ¿O autorizas por escrito un **tope de sesión** de consultas y un `infra/estado.json` aceptado a mano?
5. ¿Estado del **freno de captura** (`empresa/captura/freno.json`)? (si está puesto: el material del Modo D lo aportas tú a mano)
6. ¿Sello de reglas aprobado para `--sello-esperado` (spec §12.7: `sha256:7d3ce2d9…4e4d`) y sello de límites? ¿Quién lanza los agentes (barrido, etiquetadores, jueces)?
7. ¿Autoinventario (qué sabes hacer, qué te preguntan, qué quieres evitar)? Es hipótesis, no evidencia.
8. ¿Hay `ofertas/<oferta_id>/00-brief.yaml`? ¿Qué `oferta_id` uso (si no, propongo `OF-AAAAMM-NN` `[SUPUESTO]`)?

## B. Decisiones del dueño (con recomendación; fuente: `docs/_historial/d1-v2-resumen-para-el-dueno.md` y interfaces §9)
| # | Decisión | Recomendación |
|---|---|---|
| 1 | **Freno HTTP 403** de `empresa/captura/freno.json`: ¿falso positivo? | Dejarlo puesto hasta entender la causa; el Modo D avanza con material a mano. **No** bajar el ritmo ni cambiar de perfil (sería evadir). Solo tú lo levantas |
| 2 | ¿La captura de fichas y la lectura de páginas de venta (con frenos) siguen aprobadas? ¿Y las **páginas de búsqueda** por Chrome (§14.7)? | Mantener fichas y páginas de venta; suspender las búsquedas hasta resolver el freno y mover la ejecución a un servidor |
| 3 | **Retención** de las citas de una oferta activa más de 90 días | Excepción firmada por X1 y fuera de Git (decisión 14: riesgo residual aceptado) |
| 4 | **Salud y relaciones en modo resumen** (nada de texto íntegro de personas) | Mantener; la E3 sale de reseñas del producto, preguntas «cómo…» y datos propios; el primer candidato de esos macros puede tardar |
| 5 | **Aprobar `nichos.yaml` y `fuentes.yaml`** (propuestas en `docs/_historial/d1-v2-semillas/`) y la cuota mínima de exploración por macro (20 ó 25) | Aprobar con revisión; **25**; no se copian a `empresa/` hasta tu aprobación |
| 6 | Tres motivos de rechazo extra (`duplicado_de_la_memoria`, `evidencia_insuficiente`, `inviable_sin_backend`; `linea_roja_de_contenido_o_negocio` ya está en `comunes` 1.4.0) | Aprobar los tres: sin ellos X2 pierde la causa de la mayoría de los descartes de D1 |
| 7 | Integrar los `modelado_*` y `barrido_*` en `parametros.yaml` (15 anuncios y 10 días ya son tuyos) y el **sello de reglas** como candado | Aprobar tal cual; el sello queda como candado |
| 8 | Valores iniciales de `max_costo_por_barrido` y `max_barridos_por_semana`; `locales_permitidos`; las **30 líneas rojas** y `nivel_max_lanzable` (zonas grises, nota 25 §12.4) | Propuestas en las notas; tú los fijas en `limites.yaml` |
| 9 | Costos del radar: ¿estructura o imputados a la oferta elegida? | Costo de estructura |
| 10 | **Ruta desatendida** del Modo D (B `claude -p`, C API UE/UK, D Chrome) | No elegir aún; si hace falta escalar: C para UE/UK antes que D |
| 11 | **Fracción del muestreo** cuando el juicio pase a `muestreo` (qué parte de las fichas liberadas revisa una persona) | Hasta definirla: toda ficha con veto «para revisión» y 1 de cada 3 de las liberadas [SUPUESTO] |
| 12 | Dónde se guardan lo pegado por una persona (`empresa/descubrimiento/entrada/`) y la calibración (`empresa/barrido/calibracion/`) | Esas rutas propuestas |
| 13 | Orden del descubrimiento tras el Modo D | Primero captura asistida de reseñas 2-3★ y comentarios de anuncios propios; después `wikipedia-pageviews` como primera automatización de demanda, si la apruebas |
| 14 | Semillas fuera de marco (crochet, costura, planos…) | Registradas pero no sembradas; entran solo por su reencuadre al costeo con cita E3 |
| 15 | Autoinventario del dueño: qué sabe, qué le preguntan, qué quiere evitar | Entrevista corta en el primer encargo |

## C. Dudas que anoto durante una corrida (las lleva el dueño a la bitácora `Pulido`)
Cada vez que tengas que **decidir sin regla** (un criterio ambiguo, una fuente sin modo, un caso que la tabla de ejes no cubre, una redacción de B que el clasificador no reconoce), lo anotas `[SUPUESTO]` en `informe.md` con la razón y lo listas en «Lagunas y supuestos». No lo resuelves en silencio.

## D. Resueltas (no se vuelven a preguntar)
Titular de Stripe: LLC de EE. UU. · elección de candidato: H hasta N3 (`contratos/gates.json`) · exclusión por tema: no existe (decisión 13) · sin abogado como paso (decisión 14) · marco de nichos como etiqueta (opción A, 2026-11-06) · 15 anuncios y 10 días de edad de la oferta (2026-11-06) · automatizar el juicio con IA sin aflojar las reglas (2026-11-06).
