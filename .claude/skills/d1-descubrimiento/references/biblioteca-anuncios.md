# La Biblioteca de Anuncios en D1: qué da, qué no, y cómo se consulta

> Fuentes: spec §5, §12.3-§12.4, §15, §17; `scripts/modelado/barrido/README.md` §7; `docs/_investigacion/04-meta-ads.md` §0.3 y §9.1, `02-conectores.md` (c). Etiquetas: [HIPÓTESIS] lo no medido; `[VERIFICAR]` lo no leído en fuente oficial.

## 1. Qué entrega el conector `ads_library_search` (y qué no)
| Da | No da |
|---|---|
| anuncios de una consulta (máx. **50** por llamada, los **más recientes primero**, sin cursor), `ad_snapshot_url`, título (`ad_creative_link_title`), `ad_delivery_start_time` (fecha deseada de inicio, no impresión real), `page_id`/`page_name`, `currency` (la de la **cuenta del anunciante**, no la del mercado), `estimated_total_count` **por país** | gasto, impresiones, conversiones, ventas, texto principal, landing, país por anuncio, fecha de fin, precio |
Consecuencias: **la Biblioteca mide oferta, no rentabilidad** (`senal_rentabilidad = "no medible"` siempre). «Muchos anuncios = gana dinero» es falso. «Misma landing» es un **proxy** (páginas que comparten concepto). `currency` solo sugiere un exportador (cuenta en otra moneda que anuncia en otro idioma): es pista para M1, no evidencia de demanda. La lectura del texto y de la landing exige mirar el anuncio: es humana (o del CLI con freno, por orden del dueño).

## 2. Parámetros de cada consulta
| Parámetro | Valor | Nota |
|---|---|---|
| `search_terms` | 1 palabra o frase corta (2-3 palabras en modos A-C), **en el idioma del país** | las búsquedas no se traducen solas: «patrones crochet» no encuentra nada en polaco; la coincidencia usa también texto invisible, así que se descartan títulos irrelevantes |
| `countries` | **un país por consulta** (ISO-2) | el conteo es por país |
| `ad_active_status` | `ACTIVE` | solo lo que corre hoy |
| `limit` | 50 | máximo del conector |
| 2.ª pasada | `page_ids` (hasta `barrido_page_ids_por_consulta_max`) + `countries` | mide la edad real y la presencia por país; **ordena por recencia, así que los longevos quedan enterrados** |
| `advertiser_job` | `plan_future_campaigns` | etiqueta de intención (no es un permiso) |
| `advertiser_request` (modos A-C) | plantilla fija **sin datos personales** (se envía a Meta) | la Biblioteca exige una cuenta publicitaria activa |
| `client_conversation_id` | cadena aleatoria de 20 caracteres alfanuméricos, estable en la sesión | nunca un id de página, cuenta o campaña |
Tope por corrida: `modelado_max_consultas_por_corrida` (propuesta 120; cuenta las tres pasadas) ∩ `limites.max_consultas_biblioteca` (hoy `null`: **sin tope no se consulta**). Modos A-C: `consultas_biblioteca_por_corrida_pipeline` (propuesta 20, solo los ≤ 8 mejores pre-puntaje) y ≤ 3 palabras, ≤ 3 consultas por candidato. **Sin extracción masiva** (términos del conector: «no bulk extraction»).

## 3. Conceptos, anunciantes, sostenido: contar sin engañarse
- **Concepto creativo único** = promesa + mecanismo, no `id` de anuncio (160 `id` pueden ser 1 concepto). Agrupa por concepto y guarda en `demanda_pagada.n_conceptos_unicos` (≤ `n_anuncios`).
- **Operador**, no página: un mismo operador con varias páginas (mismo dominio/oferta, aun traducida) cuenta una vez; `paginas_misma_landing` y `anunciantes_independientes_mismo_angulo` lo reflejan.
- **Anunciante sostenido (modos A-C y D2)** = ≥ `anunciante_sostenido_conceptos_min` conceptos únicos activos **con** ≥ `anunciante_sostenido_dias_min` días desde `ad_delivery_start_time`. **Tracción del Modo D** (otra cosa; no se mapean): ≥ `modelado_anuncios_objetivo` anuncios activos **y** ≥ `modelado_dias_objetivo` días de **edad de la oferta** = antigüedad del **2.º** anuncio activo más viejo (exige dos sobrevivientes; la mediana engaña: con datos reales dio 0,8 días y la edad de la oferta 14,9). Las claves de tracción de D no alimentan `n_sostenidos`.
- `resumir`: `puntaje_modelar resumir FILAS.json --ahora AAAA-MM-DDTHH:MM:SSZ` cuenta anuncios, edad de la oferta, conceptos únicos y páginas que comparten concepto de forma determinista: **no cuentes a mano**.

## 4. Pisos, muestras y ausencias
| Situación | Estado | Qué hacer |
|---|---|---|
| Página vista solo por frases, muestra truncada (50 de 932) | `medicion = muestra`: el conteo es un **piso** | si el piso ya supera el umbral → definitivo; si no → `indeterminada_por_muestra`: **pasada 3**, nunca descartar |
| Consulta por `page_id` y país con todos los anuncios vistos | `completa` (total declarado ≤ vistos y no está al tope de la consulta) | conteo exacto; solo aquí `no_pasa` es legítimo |
| 50 de 744 | `parcial` | piso; `edad_es_piso` |
| `estimated_total_count = 0` en el destino con consulta unipágina | **ausencia medida** | el original no corre allí: hueco candidato (comprobado el 2026-11-06: una página con 19 anuncios en EE. UU. tenía 0 en MX, ES y BR) |
| ausencia solo en la muestra de una frase | hipótesis | `original_presente: false` es optimista hasta medir; el CLI lo marca en `pendiente` |
`estimated_total_count` es una **estimación**; 50 de 50 es «parcial». Nunca sumes totales entre países (un mismo anuncio en 2 países contaría doble): `anuncios_activos_medidos` toma el máximo por país y es una cota inferior.

## 5. Quién consulta y con qué límites
- **Hoy:** solo **sesiones interactivas** con el conector (un proceso desatendido con clave de API no carga conectores `[VERIFICAR]`; `ads_library_search` no corre en el cron de Railway). La ruta A del barrido (agentes de Claude Code que escriben el crudo ellos mismos) es la única que orquesta el CLI. **D1 queda en nivel de recolección N2** hasta que el dueño elija una ruta desatendida y X1 la selle.
- Las rutas B (`claude -p`), C (API `ads_archive`, solo UE/UK, token del dueño) y D (Chrome sobre la búsqueda, con freno) están **investigadas y no integradas**; el Maker no las usa. La web de la Biblioteca y las páginas de venta (excepciones aprobadas por el dueño con frenos, spec §14) las corre el **CLI por orden expresa**, nunca el Maker; **hoy detenidas por el freno** (HTTP 403: la sonda cargó 27 anuncios y recibió 403; el freno se activó solo y solo el dueño lo levanta).
- Ante captcha, «confirma que eres una persona», login obligatorio, 403/429 o límite de ritmo: **se detiene y se escala**. Nunca se evade (DMCA §1201; hallazgo 3 de la nota 21).
- Plan B si el conector no está disponible: enlaces `ad_snapshot_url` para revisión humana; `evidencia_demanda_pagada` ≤ 2, confianza media y el candidato no se ofrece en N4 (eval 6).

## 6. Lo que NO es evidencia aquí
El número de anuncios, `estimated_total_count`, la antigüedad de un anuncio o el «anunciante grande» **no prueban ventas**. Úsalos como contexto de oferta persistente y declara lo no medible en el informe y en `hipotesis_para_d2`. D2 contrasta pago y demanda; la prueba pagada es de D7/D8.
