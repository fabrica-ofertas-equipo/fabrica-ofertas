# Pendientes de la skill `modelado-oferta` (v0.1.1)

> Único lugar de lo que falta fuera de esta carpeta. Al crearse (0.1.0) no se editó ninguna otra skill; el 2026-11-07 S-C aplicó la sección A (0.1.1). Contratos, motor, empresa y ofertas siguen sin tocar. Prioridad: **P0** = necesario para modelar la próxima oferta de punta a punta · **P1** = antes de la segunda · **P2** = con ≥ 5 ofertas. Dueño: **S-A** contratos y documentos · **S-B** motor y código · **S-C** skills, agentes y panel · **dueño**.

## A. Referencias que otras skills debían añadir — estado al 2026-11-07 (aplicadas por S-C)

S-C aplicó esta sección el 2026-11-07 (integración de skills; cada skill tocada subió su patch y lo anotó en su `CHANGELOG.md`). Las líneas originales ya no se repiten aquí: viven en los archivos destino. **Aplicada** = el texto está en la skill; **adaptada** = se aplicó con un cambio (el motivo va en la columna); **bloqueado: S-A/S-B** = lo que depende de contratos o de código ajeno y no se aplicó.

| # | Prio. | Dónde | Estado | Nota o lo que sigue bloqueado |
|---|---|---|---|---|
| A1 | P0 | `d1-descubrimiento/SKILL.md` §5 | **aplicada** (0.1.1) | viñeta «Desarme y plan de mejora» tras «Unidad = par oferta fuente × mercado destino» |
| A2 | P0 | `d1-descubrimiento/references/modo-d-rutina.md` | **aplicada** (0.1.1) | fila 14b y el cambio de «cero texto, landing o producto ajeno» en el paso 15 (que chocaba con J17) |
| A3 | P0 | `d3-arquitectura-oferta/SKILL.md` | **aplicada** (0.1.3) | modo `modelado`, pasos 3b y 9b, notas de los pasos 1 y 7 |
| A4 | P1 | `d3-arquitectura-oferta/rubric.md`, `d3-arquitectura-oferta/references/contratos-y-rutas.md`, `d3-arquitectura-oferta/templates/oferta.md` | **adaptada** (0.1.3) | L1-16 queda «tú (lectura)»: `lint_d3.py` no lo comprueba. **bloqueado: S-B** el chequeo por código (B2) |
| A5 | P0 | `d5-landing-checkout/SKILL.md` 0b y Entradas, `d5-landing-checkout/references/proceso-landing.md`, `d5-landing-checkout/references/dependencias.md`, `.claude/agents/d5-maker.md` | **aplicada** (0.2.1) | quitado «hoy no existe». El Maker de D5 **lee** `modelado/` (no ejecuta el script). **bloqueado: S-B** el chequeo L1 `modelado_estructura` contra `esqueleto_funnel.json › plano_objetivo` |
| A6 | P0 | `d2-validacion/SKILL.md` paso 7b, `d2-validacion/references/voz-del-cliente.md`, `d2-validacion/rubric.md` | **adaptada** (0.1.2) | en vez de un ítem **R8** (rompía «R1-R7» en `d2-qa.md`, el mapeo a `qa.schema.json` y los sembrados) se amplió el ancla 5 de **R4**. **bloqueado: S-A** el campo `inmersion.estado` y el contrato de `inmersion/` |
| A7 | P1 | `d4-producto/SKILL.md`, `d4-producto/references/anti-copia-y-fuentes.md` | **aplicada** (0.1.2) | matriz palanca → entregable → prueba; corpus de control = todo el material del referente |
| A8 | P1 | `d6-creativos/references/tipos-de-hook.md`, `d6-creativos/references/angulos-por-nivel.md`, `d6-creativos/SKILL.md` | **adaptada** (0.2.1) | las reglas de reescritura de ganchos ya estaban en `inmersion-y-derechos.md` §3 (0.2.0): se añadieron punteros, no un duplicado. Las reglas de imágenes J21 se enlazan desde el «Modo ranuras» |
| A9 | P1 | `x1-compliance/references/checklists-por-etapa.md` | **aplicada en parte** (0.1.2) | filas O-13 (D3) y L-15 (D5). **bloqueado: S-A/S-B** el cuarto macro-nicho (J6/J9) en contratos, `scripts/descubrimiento/macro.py`, las reglas de X1 y el lint (F-01, F-12, F-22): hoy solo hay una nota que lo declara `[SUPUESTO]` |
| A10 | P1 | `o0-lanzar-oferta`, `o0-orquestador-portafolio` | **aplicada** (0.1.2) | recorrido completo (§3b de `o0-lanzar-oferta`) y conteo de ofertas con plan aprobado. Sin cambiar gates ni autonomía. **bloqueado: S-A** una etapa o gate propio de modelado en `contratos/gates.json` y `estado.schema.json`: hoy el plan lo aprueba el dueño escribiendo `plan_mejora.json` |
| A11 | P0 | `.claude/skills/README.md` | **aplicada** | índice completo de skills con etapa, versión, estado y lo que falta |
| A12 | P0 | `.claude/agents/modelado-maker.md`, `modelado-qa.md` | **adaptada** | creados. **No** se dio `scripts/imagenes/*` al Maker: contradice `references/imagenes-kie.md` §1 (el modelado no produce, cotiza ni gasta imágenes). **bloqueado: S-B** alta de `analizar_html.py` (banderas `--no-red`, `--salida`, `--sobrescribir`, `--max-bytes`, `--timeout`, `--sin-muestras`) en `agentes/hooks/herramientas.yaml › bash_scripts` y plantillas de agente si el runner las usa; **bloqueado: S-A** contrato `qa` con etapa de modelado |

Aplicado además (sin estar en A): las costuras entre etapas (D7→D8, D8→D9 y D8→D6, D9→M1/D1, D10→D5/D6/D8) en las skills respectivas.

## B. Código que falta (S-B)
| # | Prio. | Qué | Por qué |
|---|---|---|---|
| B1 | P1 | `scripts/modelado/palancas.py`: valida R-1…R-7, calcula `valor = B×R×F×M`, aplica R-3 y la aritmética del antes/después con la salvaguarda de R-5 (una dimensión excluida que sería peor cuenta como peor) | hoy lo recomputa el QA a mano; el piloto puntuó solo (sesgo favorable, F-30) |
| B2 | P1 | `scripts/modelado/similitud.py`: n-gramas contra **todo** el material del referente y su familia, distancia de nombres (edición y fonética), fidelidad de estructura contra `esqueleto_funnel.json`, hashes de imágenes; usable por D3, D4, D5 y D6 | QM-01…QM-08 no tienen script (F-40); D4 usa su propia copia |
| B3 | P1 | `capturar_fuente` (texto crudo de páginas públicas con hash) y reglas de X1 pl-PL (plazos, «płynnie», «sekret poliglotów», preguntas sobre el lector, cifras de prueba social); términos sensibles por palabra entera | grado `visto` de las citas del dossier (F-13); el lint pl-PL es la única capa de código (F-23/F-44/F-43) |
| B4 | P1 | Capas 3-5 del QA lingüístico en código (`linguistico.json`: retraducción, segunda lectura, cobertura cruzada y lista de calcos) | J11 retiró el revisor humano (F-36) |
| B5 | P1 | `analizar_html.py` ↔ `scripts/modelado/enlaces.leer_pagina`: reutilizar la lectura que **fija la IP validada** y lee `modelado_lectura_max_bytes` (1,5 MB), `_timeout_seg` (20), `_max_redirecciones` (3), en vez de las constantes del script (2 MB, 15 s, 5) | evitar dos lectores seguros con umbrales distintos y la ventana de re-resolución de DNS |
| B6 | P1 | `validar_esquemas oferta --hasta D3` y plantilla mínima `ofertas/_plantilla/` | el modo práctica exige ~10 atajos (F-07, F-42) |
| B7 | P2 | Test de 1 día en el motor (CPA máximo a pagar como umbral), BLIK/Przelewy24, upsell y postpago, escalera J16 con redondeo local | F-26, F-28, F-38, F-39 |
| B8 | P2 | Post-mortem con `palancas_resultado[]` y `empresa/memoria/palancas.jsonl` en X2 | MOD-9 |
| B9 | P2 | Mejoras del script: idioma del texto frente a `lang` (el referente declaraba `pt-BR` en una página italiana), `scrollRestoration`, valores de `@media` en el relleno de sección, hojas externas con `--css-externo` probadas en una corrida real | límites de `references/analizar-html.md` §5 |
| B10 | P2 | Panel: tarjeta «antes y después» y vista del plan en el gate H de D3 | MOD-6 |

## C. Parámetros que el dueño debería integrar (`empresa/parametros.yaml`; hoy son propuesta `[HIPÓTESIS]`)
`modelado.palancas_min` 3 · `modelado.palancas_max` 5 · `modelado.delta_antes_despues_min` 8 (sobre 60, proporcional a las dimensiones puntuables) · `modelado.fidelidad_estructura_min` (a calibrar con 5 ofertas) · `modelado.similitud_expresion_max` (a calibrar) · `modelado.nombre_distancia_min` · `modelado.umbral_qa` 4,0 · `modelado.palancas_min_ofertas` · `inmersion.calcos_max` · `inmersion.min_*` (jerga 40 con 20 atestiguadas, quejas 15, deseos 8, creencias 5, objeciones 8, celebraciones 5, páginas 6, reglas de estilo 12, ganchos 10). Ya existen y se reutilizan: `compliance.ngrama_copia_palabras` (8) y `ngrama_alerta_temprana_palabras`, `landing.bump_pct_precio_min/max`, `orquestador.max_rondas_qa`.

## D. Contratos y decisiones (S-A y dueño)
- **Contratos nuevos (P0):** `desarme_referente`, `plan_mejora`, `antes_despues`, `esqueleto_funnel`, `qa_modelado` (o una etapa de modelado en `comunes.schema.json › etapa`, hoy sin ella) y MINOR de `oferta.schema.json` con el bloque `modelado` (`referente_ref`, `plan_mejora_ref`, `palancas[]`, `antes_despues_ref`, `expresion_no_tocada`) y `marca_propuesta[]`; categorías nuevas de `voz_cliente`. Hasta entonces son hermanos `0.1.0-borrador` y los validadores no los miran.
- **Cuarto macro-nicho (J6/J9) en contratos, `macro.py`, X1 y lint (F-01, F-12, F-22):** sin él la oferta A sale `fuera_de_macro_nicho`.
- **Inmersión (A6):** campo `inmersion.estado` (`suficiente` · `parcial` · `insuficiente`) y contrato de `ofertas/<id>/02-validacion/inmersion/` (hoy hermano sin esquema); sin ellos, «D3 no arranca sin inmersión suficiente» se comprueba leyendo.
- **Etapa o gate de modelado (A10):** `contratos/gates.json` y `estado.schema.json` no tienen `etapa:modelado`; hoy el plan lo aprueba el dueño en `plan_mejora.json`. **J2** (`activar_campana` deja de ser H) sigue pendiente en contratos: el recorrido guiado no lo asume.
- **J11 ejecutable:** `X32_REVISOR` y `revision_linguistica.metodos` (F-03).
- **Vía «oferta elegida por el dueño con par incompleto»** en D1 (F-11, F-14) y definición de «sostenido» para una oferta que se replica (F-18).
- **Regla de derechos en los departamentos** (D1, D3, D4, D5, D6, X1: J13).
- **Dueño — preguntas abiertas:** (1) ¿qué permite Impulstienda (HTML personalizado, API, pasarelas, idiomas, dominio, píxel con CAPI)? (J20; mientras tanto vale J7); (2) ¿aprueba el catálogo de 16 palancas v1 y que solo él agregue o quite? (3) ¿el desarme automático rápido con títulos para todo el ranking, o solo para los pares que llegan a candidato? (4) ¿cuándo cambiar el factor D del PM para que cuenten solo palancas propias con plan validado (recomendado tras el piloto)? (5) ¿la inmersión sigue como paso 7b de D2 o pasa a etapa con sello propio? (6) ¿abre la lectura por URL del HTML cuando haya ruta C (J15) o sigue manual?

## E. Lo que esta v0.1 no ha hecho
Ninguna corrida con el Maker y el QA reales ni con el dueño; el script se probó con 72 pruebas sin red y contra **dos** páginas reales (una WordPress/Elementor y otra Astro/Tailwind), no contra una descarga viva (el camino `urllib` real solo se probó con dobles); la inferencia de tipos de bloque no se ha calibrado con más referentes; el cotejo anti-clon (QM-01…08) y el antes/después se hacen a mano hasta B1-B2; los umbrales son hipótesis. Para 1.0.0: una corrida manual del dueño con una oferta real, retro de 30-45 min y DoD firmado por él.
