# Preguntas abiertas, supuestos y decisiones del dueño (D6 v0.2.0)

Las **preguntas bloqueantes** (spec §10.1: «una sola lista») se hacen **al inicio de cada corrida** y se responden antes de gastar; lo no respondido queda como `[SUPUESTO]` en el brief y nunca se inventa. Etiquetas: `[DUEÑO]` decisión suya · `[SUPUESTO]` asumido aquí · `[VERIFICAR]` hecho externo sin fuente oficial · `[PENDIENTE]` construye otro (ver `dependencias.md`).

## 1. Lista única al empezar una corrida (copiar y pegar)

1. `oferta_id`, `familia_id` y, si es un pedido del loop, `pedido_id`.
2. `locale` y países de segmentación (si falta, **no se genera nada**); ¿hay glosario del idioma y dossier de voz del cliente del país? (el revisor nativo ya no se pregunta: J11)
3. `macro_nicho` y nivel de riesgo de la oferta (D3 lo trae; ¿hay un reencuadre aplicado?).
4. Topes de créditos: `creditos_max_pieza`, `creditos_max_oferta`, `max_budget_por_corrida_agente` (hoy `null`: nada se genera).
5. Presupuesto de test (`gasto_test_plan`) y `cpa_obj` (para `n_anuncios_max`).
6. `politica_divulgacion_ia` y si hay avatar IA (solo dinero verde) o solo voz y manos.
7. Marca visual de D5 (colores, fuente) y si el precio se muestra en el anuncio.
8. ¿Hay sesión Code con Higgsfield autenticado para esta corrida, o todo va por Ruta A?
9. En N0 (sin carpetas previas): pegar oferta, claims, mercado, landing y voz del cliente.
10. Si es el **modo ranuras** (encargo de D5): ¿qué `slot_id` produce D6 y cuáles el dueño o D4?
11. Si es una **tanda** (`modo-tanda.md`): ¿régimen de aprobación (A total · B muestreo con sello de X1 por plantilla)? ¿cuántos candidatos por idioma y día (5-10)? **Sin respuesta: A.**

## 2. Decisiones del dueño (de la spec §11)

| # | Decisión | Estado |
|---|---|---|
| 1 | `creditos_max_pieza`, `creditos_max_oferta`, `max_budget_por_corrida_agente`; costo real por pieza (`ads_studio_quote`/`get_cost`) | `[DUEÑO]` abierta: hoy `null` |
| 2 | `politica_divulgacion_ia` (`declarar_siempre` · `declarar_si_corresponde` · `no_declarar_donde_legal`) y si hay avatar IA | `[DUEÑO]` abierta |
| 3 | Marca visual por oferta (neutra, sin condición ni resultado) y si se muestra el precio. «Marca y dominio por oferta» es un `[SUPUESTO]` hasta que el dueño lo confirme (backbone §2.9): D6 usa `oferta.marca` y la paleta de D5 y no asume dominio propio | `[DUEÑO]` abierta; v1 asume `precio_visible: true` constante `[SUPUESTO]` |
| 4 | ~~Revisor nativo pagado por hora~~ **Resuelta por J11 (2026-11-06): se retiró.** Los ejemplos en it/pl/ro/fr/de de esta skill son `[SUPUESTO]` sin nativo. Sigue abierta la aprobación de las 30 líneas rojas (nota 25 §12.4) | J11 cerrada; líneas rojas `[DUEÑO]` abierta |
| 5 | Créditos sin humano en N3: ¿API de Higgsfield `[VERIFICAR]` o aprobación por lote? | Parcial: D6 es semiasistido mientras solo exista MCP |
| 6 | Polonia, Italia y cualquier mercado son hipótesis a decidir con datos propios. **Un mercado a la vez** (`mercados_test_paralelos_max` = 1): el primer mercado y la primera oferta los decide el dueño con la propuesta de M1; el caso e06 (it-IT y pl-PL) es un **eval**, no un lanzamiento en paralelo | D6 no asume ningún prior |
| 7 | Régimen de aprobación de la tanda (A total · B muestreo con sello de X1) y piezas por idioma y día (`modo-tanda.md` §5) | `[DUEÑO]` abierta (B1-15; mientras tanto A) |

## 3. `[SUPUESTO]` de esta v0.1.1 (a confirmar o corregir al pulir)

1. ~~`qa-a-v<n>.json` en `06-creativos/`~~ **Resuelto en 0.1.1:** el QA-A (`tramo: previo`) va en `qa/d6-v<n>-previo.json` (spec 07 §4 paso 5); hasta que CT aplique LT-43 y X18 lo admita, el runner lo deja en `qa/.previo/` (SB-11).
2. ~~`06-creativos/costos.jsonl` como libro de créditos~~ **Resuelto en 0.1.1:** es el **borrador** del Maker; el libro es `empresa/costos.jsonl` y lo escribe el motor. Se mantiene `monto` 0 hasta que F1 valore créditos y `job=<id>` dentro de `concepto`.
3. Forma de `matriz.json`, `copies.json` (con `marca` y `texto_en_pieza`), `fuentes_inspiracion.json`, `linguistico.json`, `lint-x1.json`, `preflight-d6.json`, `licencias.json` y `assets.json`: no tienen esquema en `contratos/`; las plantillas son el contrato provisional.
4. Si el snapshot de `oferta.riesgo` no trae `ejes_codigo`, se derivan de los colores (≥2 amarillos = B); el subnivel lo calcula `scripts.nivel_riesgo` (LT-04/LT-20).
5. Nueva creatividad por pedido: `hook_id` nuevo (`h3`, `h4`…) con `v1` dentro de un paquete `v(n+1)`; un anuncio nuevo es un creativo nuevo.
6. `vsl-45-90s` no entra en la v1 del test; `mini novela` y video 100 % IA de 1:30 están diferidos (prohibidos en salud y relaciones). **Actualización 2026-11-06 (dueño):** se habilita el sub-formato «sketch animado» como v0.1 experimental en `d6-sketch-animado` (gates y preguntas propias en `d6-sketch-animado/references/preguntas-abiertas.md`); la decisión general sobre «mini novela» sigue abierta.
7. `precio_visible` constante en todo el paquete; CTA por defecto `LEARN_MORE`; ambos son variables de iteración posterior.
8. Dos hooks por concepto difieren en `hook_tipo` (nunca solo en palabras).
9. Sin música en la v1 salvo pista con licencia comercial documentada.
10. Zona segura 9:16: el borde más restrictivo de la spec y de `creativos-ads` (14 % arriba, 35 % abajo, 180 px por lado).
11. Un rechazo de Meta abre un concepto nuevo con otro claim, tras decisión del dueño/X1 (spec silenciosa).
12. Sin Playwright: Ruta A con Chrome headless (`render_estatico.py`); mismo texto; con las WOFF2 de D5 incrustadas por `@font-face` los píxeles ya no dependen de la fuente del sistema (solo de la versión del navegador).
13. Las frases de ejemplo en `it`, `pl`, `ro`, `fr`, `de`, `en` de esta skill son **[SUPUESTO]** (pares de la nota 25 §5.2 y redacciones propias): ninguna fue revisada por un nativo ni probada ante Meta.

## 4. `[VERIFICAR]` (hechos externos sin fuente oficial leída)

Políticas vigentes de Meta (engaño, urgencia, testimonios), zonas seguras 9:16 oficiales, límites de caracteres y enum de CTA, términos de Higgsfield por plan (uso comercial, C2PA), costo y exactitud de `virality_predictor`, prueba de creativos por API con Advantage+ ventas (HC-12), servir piezas en Instagram sin cuenta propia, si el conector de Higgsfield emite C2PA, texto oficial del AI Act art. 50 y su aplicación a un presentador IA, clasificación de «reinserción laboral» como categoría especial de empleo, si Meta rechaza «madres» en tercera persona por «family status» (pasaría a E2 para todo el sistema).

## 5. Preguntas que esta skill aún no sabe responder (para el pulido)

¿Qué costo real tiene un video 9:16 de 20–45 s con voz? ¿Qué porcentaje de piezas edita el dueño? ¿Qué hooks de tercera persona se entienden en 3 s sin sonido en cada idioma? ¿Cuántas veces el lint pasa a la primera? ¿Qué frases de la lista de ROJO nunca aparecen y cuáles faltan? Cada respuesta pasa a regla (`como-pulirla.md`).
