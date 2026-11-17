# scripts/modelado
Puntaje de modelado (PM) de D1, Modo D: ordena pares «oferta fuente × mercado destino» con la fórmula de `departamentos/02-descubrimiento.md` §12.
Propietario: D1 (descubrimiento), Modo D. Solo biblioteca estándar y PyYAML. Sin red, sin credenciales, sin efectos fuera de `--salida`.

## Qué hace y qué no
- **Hace:** valida las fichas, aplica las puertas, calcula T (tracción), H (hueco), X (transferibilidad) y D (diferenciación), ordena, explica el cuello de botella y mide la sensibilidad de los pesos. También cuenta de forma determinista las filas de la Biblioteca (`resumir`) para que el Maker no cuente a mano.
- **No hace:** buscar ofertas (lo hace el Maker con `ads_library_search`), juzgar landing/marca/riesgo (eso es juicio del Maker con rúbrica) ni predecir ventas. El PM ordena candidatos; la validación es la prueba pagada de D7/D8.

## CLI (desde la raíz del repositorio)
```
.venv/bin/python -m scripts.modelado.puntaje_modelar puntuar FICHAS.json [--parametros P.yaml] [--json] [--top N] [--solo-marco] [--sensibilidad] [--salida NUEVO.json]
.venv/bin/python -m scripts.modelado.puntaje_modelar resumir FILAS.json --ahora 2026-11-06T12:00:00Z
```
Mientras los parámetros no estén integrados en `empresa/parametros.yaml`:
`--parametros scripts/modelado/parametros_modelado.propuesta.yaml`

Códigos de salida: 0 correcto · 2 uso (archivo ilegible, argumentos, `--salida` existente) · 3 validación (ficha o JSON inválido) · 5 falta un parámetro (falla cerrado; nunca se asume un valor).

## Ficha (`schema_version` "2.0.0")
Ejemplo completo con 11 ofertas del corpus (19 pares): `tests/fixtures/modelado/fichas_corpus.json`. Por oferta fuente:
`modelo_id` (kebab) · `nombre` · `fuente{idioma,pais}` · `macro_nicho` (`salud|relaciones|dinero|null`) · `traccion{anuncios_activos, edad_oferta_dias, conceptos_unicos, paginas_misma_landing, anunciantes_independientes_mismo_angulo}` · `puertas{marca_personal, sustituto_gratis_cubre, practica_vetada: booleanos; null = sin evaluar}` · `reencuadres[]` · `pendiente[]` (opcional) · `mercados[]`.
Por mercado destino: `mercado` (ISO-2) · `idioma` · `hueco{original_presente, anunciantes_sostenidos, puntaje_rival (obligatorio si hay 1-2 rivales), entrantes_30d (null = sin snapshot previo: ficha incompleta, nunca se asume 0)}` · `ventana` · `transferibilidad{dolor_universal, viabilidad_ticket, riesgo_politicas: 0-1; null = sin evaluar}` · `reencuadres_mercado[]` (opcional).
Decimales como cadena (`"0.8"`) o literal JSON; nunca `float` nativo en parámetros ni en fichas pasadas como objeto.

## Estados de un par
`pasa` / `no_pasa` (completo, contra `modelado_umbral_pasa`) · `incompleta` (hay algo sin evaluar: no tiene PM, pero sí **techo**, el máximo que podría sacar; si el techo ya es bajo, se descarta sin más juicio) · `vetada` (alguna puerta en `true`: PM 0).

## Pruebas
`.venv/bin/python -m unittest tests.scripts.test_puntaje_modelar` (fórmula, validación, CLI, sello, casos del corpus de los mentores y 27 anuncios reales) y `tests.scripts.test_juicio` (juicio por IA).
Los valores de tracción del corpus son ilustrativos salvo `crochet-patrones-es` (medido en `18d` §0.5).

## Automatizar con IA sin aflojar las reglas (`juicio.py`)
Dos jueces de IA independientes opinan con evidencia sobre puertas, transferibilidad y reencuadres; `juicio.py consolidar` las junta con reglas fijas (el veto prevalece, liberar exige a los dos, se toma el valor más bajo) y completa solo los `null`. La IA nunca completa un dato medido ni pisa lo que puso una persona. `juicio.py acuerdo` mide IA vs. persona y solo permite subir de «humano en todo» a «muestreo» con 0 falsos libres. Diseño completo: `departamentos/02-descubrimiento.md` §13.

## Captura y lectura automáticas (`captura.py`, `enlaces.py`)
Decisión del dueño (2026-11-06): automatizar el acceso a la ficha del anuncio, asumiendo el riesgo de los términos de Meta. Un Chrome sin pantalla, con perfil nuevo y sin sesión abre la ficha, saca el texto y el enlace real de destino, y `enlaces.leer_pagina` lee la página de venta con candados (solo IPs públicas, `robots.txt`, sin cookies, tope de tamaño). **Ante cualquier bloqueo se detiene, escribe un freno y no sigue hasta que una persona lo borre a mano**; nunca evade ni reintenta. Tope diario y pausa entre capturas. Detalle y riesgos: `departamentos/02-descubrimiento.md` §14. Para las páginas de búsqueda (aprobadas el 2026-11-06, §14.7) la lista blanca es `captura.normalizar_busqueda` / `construir_url_busqueda`.
```
.venv/bin/python -m scripts.modelado.captura anuncio 1907878687257184 --parametros P.yaml
.venv/bin/python -m scripts.modelado.captura material mi-oferta ID1 ID2 --parametros P.yaml --salida material.json
```

## Candado de reglas (`--sello-esperado`)
Cada ranking lleva el `sello_reglas` (SHA-256 de la fórmula, los parámetros y los vocabularios). Con `--sello-esperado <sello>`, si las reglas en uso no son las aprobadas el script no calcula nada (código 4).

## Edad de la oferta (no la mediana)
`edad_oferta_dias` = antigüedad del **2.º anuncio activo más viejo** (`resumir` la calcula). Exige dos sobrevivientes (Fer) y evita que un solo anuncio zombi la infle. No se usa la mediana: con datos reales de "Crea y Emprende" (27 anuncios) la mediana daba 0,8 días porque la página renueva creativos a diario, mientras la edad de la oferta da 14,9 y el más viejo 16,8 (la medición previa de `18d` §0.5).

## Primera corrida real
`ejemplos/piloto_crochet_2026-11-06.json` es una ficha con datos reales de la Biblioteca (tracción y hueco medidos; puertas, transferibilidad y entrantes sin evaluar). Sirve de plantilla para el Maker.

## Pendiente de integración (decisiones del dueño)
Los 35 parámetros `modelado_*` están en `parametros_modelado.propuesta.yaml` (el dueño fijó 15 anuncios y 10 días el 2026-11-06). Integrarlos exige aprobar los valores, ampliar `contratos/parametros.schema.json` y pegarlos en `empresa/parametros.yaml` (rutas protegidas para agentes).

## Reglas retiradas
El 2026-11-06 el dueño quitó las puertas `requiere_comunidad_o_vivo_o_app` y `commodity_facil_de_modelar` y el componente `producibilidad`. Fórmula `pm-2`; fichas y juicios `2.0.0`. Detalle en `departamentos/02-descubrimiento.md` §12.8.
