# D7 — Campañas Meta: armado, conexión y lanzamiento del test
> Pipeline (una vez por oferta; se reinvoca para REFRESCO/ESCALA a pedido de D8/D9) · Bajo demanda · Gate por defecto: H (activar) · Estado de la skill: v0.1 sin pulir (forjada por S-C el 2026-11-06; ver `.claude/skills/d7-campanas-meta/CHANGELOG.md`) · Especificación v2 (2026-11-06), conforme a backbone v2.2

## 1. Misión y posición en el flujo

Convertir una oferta (concepto × idioma/clúster, backbone 3.1) con landing real (D5) y paquete aprobado (D6) en una **campaña de test de Meta armada, medible, dentro de los topes, pre-verificada y activada solo con firma humana**, y vigilar sus primeras 72 h hasta traspasarla a D8. D7 **arma y lanza; no elige mercado, no clasifica riesgo ni emite veredicto**: hereda `locale`, países y moneda de `mercado.json` (M1), el nivel de riesgo de `oferta.json` (D1/D3/X1) y las reglas de `decision/` (docs/08).

- **Recibe** (en `ofertas/<id>/`): `00-brief.yaml`, `mercado.json`, `03-oferta/{oferta,economia}.json`, `05-landing/{tracking,checkout,assets}.json` + `despliegue.json` `[PENDIENTE: lo define CT-3 (LT-12); hoy no lo produce landing/desplegar.py ni lo trae ofertas/_ejemplo/05-landing/]`, `06-creativos/paquete.json`; `ofertas/<id>/infra/alta.json` (D0 N01b; forma real `schema_version "0.1.0"`, `completo`, `pasos[]` con `{id, estado, mensaje, evidencia}` `[PENDIENTE: esquema, LT-30 y LT-36]`); sellos de X1; `empresa/{limites,parametros}.yaml`; `empresa/infra/{estado.json,meta.yaml}`.
- **Entrega:** `07-campana/` (`campana.json`, `ids_meta.json`, `preflight.json`, `aprobacion.json`, `traspaso.json`, `lanzamiento.log`) a D8 y D9.
- **Fuera de alcance:** creativos (D6), landing/tracking (D5), riesgo (D1/D3/X1), mercado (M1), optimizar/escalar (D8/D9), fijar topes y apelar (dueño).
- **Código existente:** `meta.{nombres,payloads,crear,preflight,activar,monitor,monedas}`, `decision.{estadistica,presupuesto,reglas}`, `engine.orq`, hooks `agentes/hooks/pretooluse_{gasto,activacion}.py`; hoy tienen CLI (`python -m meta.<módulo>`) `nombres`, `payloads`, `crear`, `preflight`, `activar`, `monitor`, `pausar`, `subir_presupuesto` y `lectura_viva` (los de nombres, payloads, preflight, monitor y lectura_viva son de la ola 2 B5b, 2026-11-06) y solo corren en `dry-run` o `fixture` (su modo `live` está bloqueado: aún no se conecta a un transporte real `[PENDIENTE: lo construye B5/B8]`). Si esta especificación contradice un contrato o el código, manda este (Anexo A5).

## 2. Qué dice el video (y qué no dice)

- **[VIDEO] Hace:** "conectar tu administrador de anuncios de Meta con Claude para que te monte las campañas"; semanas 3–4 "testear con anuncios; si va bien escalar, si no armar otra oferta". Su nicho (edición con IA) no es modelo: D7 sirve a cualquier oferta de salud, relaciones o dinero, en cualquier idioma.
- **[VIDEO] Omite (lo central):** estructura, evento, atribución, presupuesto, criterio de parada y de "validado", píxel/CAPI, políticas, cuenta, rechazos, riesgo de bloqueo.
- **No tomamos tal cual:** "te monta las campañas" (el MCP arma borradores, no es desatendible); "160 anuncios = gana mucho" (la Biblioteca no muestra gasto, 04 §1.2); escasez "tras X ventas" (solo si es real; veto X1).
- **[CREADORES] contrastado con Meta** (una sola tradición de vendedores de cursos, umbrales de Argentina; 12 §7, 04 §6):
  - *ABO, 3–10 conjuntos × 1 anuncio × 5–7 USD, un video por conjunto* (MB, SB, TT, FG; conf. B). Meta pide ~50 eventos/semana por conjunto (HC-1); a 5 USD/día, CPC 0,31 y conversión 2 % hay ~0,3 compras/día contra 7 (16 H3). **No es el default**; solo como cribado que ordena (§3.2).
  - *"Con una venta ya está validado"; corte 6/8/10 USD* (MB, TT; conf. C). Cortar a 10 USD mata al 54 % de los ganadores de CPA 16,2 (docs/08 §4.3). **Rechazado.**
  - *Pretest de ~30 anuncios a 1,5–2 USD/día* (SB; C): ordena por CPC, no mata.
  - *Surfing, +30 %/3 h, 5–19 cuentas, WhatsApp, tráfico para "calentar"*: sin respaldo (HC-3, DV-2); una sola cuenta (decisión 8); la escala es de D9.

## 3. Variables

### 3.1 Entradas (contrato de entrada)

| variable | origen | ejemplo / nota |
|---|---|---|
| `oferta_id`, `familia_id`, `variante_de`, `slug` | `00-brief.yaml` | `OF-202611-01` |
| `locale`, `paises_segmentacion[]`, `moneda_cobro` | `mercado.json` (M1); nunca un país único supuesto | `it-IT`, `[IT]`, `EUR` |
| `macro_nicho`, `riesgo{P,C,E,N,nivel,subnivel,reencuadre_aplicado,claims_a_evitar,angulo_seguro}`, `candidato_ref`, `mecanismo`, `claims_permitidos[]` | `oferta.json`; el riesgo se calcula por candidato (D1/D3/X1), D7 solo lo lee `[PENDIENTE: subnivel en candidatos#riesgo, LT-04/LT-20; hoy el subnivel lo emite scripts/nivel_riesgo.py]` | `dinero`, `verde` |
| `cpa_be, cpa_obj, cpa_real{pes,central,opt}, razon, veredicto, gasto_test_plan, perdida_max_test, presupuesto_test_min, dias_test, evento_optimizacion_inicial, criterios_corte{k,n_dec}` | `economia.json` (D3); `entradas_usadas.tarifa_meta_bp` (economía 1.1.0) | `cpa_be` ya incluye bump, reembolsos y disputas |
| `anuncios[]`, `destino.landing_hash`, `politicas{meta_enhancements, divulgacion_ia}`, `x1_ref` | `paquete.json` (D6) | — |
| `pixel_id`, `dataset_id`, `dominio_verificado`, `emq_objetivo`, `consent_gating` | `tracking.json` (D5) | un dataset `DS_<oferta_id>` por oferta |
| Límites canónicos (R01): `moneda_limites`, `gasto_diario_por_oferta`, `gasto_total_test_por_oferta`, `perdida_max_test_por_oferta`, `ofertas_en_test_simultaneas_max`, `limite_gasto_cuenta_meta`, `cuentas_permitidas[]`, `paises_permitidos`, `locales_permitidos`, `factor_techo_teorico_diario`, `autoaprobar_hasta`, `politica_divulgacion_ia` | `limites.yaml` (solo el dueño; `null` = no gasta). La pérdida máxima por oferta **no está fijada**: todo tope es paramétrico y fail-closed | alias v1 retirados |
| Claves de riesgo de 25 §10.1 `[ya en limites.schema 1.3.0 (CT-3 lote A; valores [DUEÑO])]`: `nivel_max_lanzable`, `hojas_pausadas`, `cuota_gasto_amarillo[_b]_max_pct`, `envios_amarillo_a_semana`, `envios_amarillo_b_mes`, `dias_limpios_para_subir_cuota`, `edad_minima_audiencia` | `limites.yaml` | sin ellas, D7 lanza solo verde |
| `cuenta_meta{ad_account_id, page_id, portfolio_id, estado, moneda, huso, offset_moneda, min_daily_budget, tipo_pago, default_dsa_beneficiary, default_dsa_payor, administradores_humanos}` (sin Instagram) | D0: ficha `meta` de `departamentos/01` §3.3 (`empresa/infra/meta.yaml`); `estado.json` VERDE y < 6 h `[PENDIENTE: lo construye D0; hoy no existe la carpeta empresa/infra/]`; mientras no exista, la lectura de cuenta se anota en `lanzamiento.log` | LLC como beneficiario/pagador. `administradores_humanos` es **solo informativo** (decisión 15): ningún check, puerta ni gate lo exige; P07 mira solo la página vinculada |
| `x1_estado_cuenta`, `rechazos_7d`, sellos de X1 | X1 | "saludable", 0 |

### 3.2 Variables de decisión

| variable | opciones | criterio / cómo se testea |
|---|---|---|
| `unidad_de_test` | **una campaña por oferta (= idioma)**; los `paises_segmentacion` van juntos en un conjunto | Dentro de una oferta no se compara país con país. Comparar mercados/idiomas = comparar **ofertas de una familia** con presupuesto diario, fechas y evento iguales (docs/08 §7: `prob_margen_por_clic_mayor`; ~2.400 clics por brazo para +50 % relativo) |
| `estructura` | **`CBO_1AS`** (JSON `estructura: CBO`: 1 campaña, 1 conjunto Advantage+, `n_anuncios`) · `ABO_n` (cribado) · `AB_nativo` | Default: junta eventos (HC-1). `ABO_n` solo si `presupuesto ≥ n×gasto_recomendado` (`plan_celda`). `AB_nativo` fuera del test inicial. El algoritmo concentra gasto: anuncios con gasto < `k×cpa_max` = "sin veredicto" |
| `evento_optimizacion` | `PURCHASE` · `INITIATE_CHECKOUT` (señal) | `evento_optimizacion_recomendado`: `PURCHASE` si `diario ≥ 0,5×(50/7)×cpa_esperado`; si no, IC y se informa cuánto falta. Es el **mismo evento** que `economia.evento_optimizacion_inicial`, con otra escritura según el contrato: mapa 1 a 1 `Purchase` ↔ `PURCHASE` e `InitiateCheckout` ↔ `INITIATE_CHECKOUT` (la regla cruzada entre ambos esquemas es el pedido LT-08 a CT-3 `[PENDIENTE: la define CT-3]`); no se cambia en caliente. Se juzga por compras de Stripe |
| `audiencia` | amplia Advantage+ (default) · intereses (sugerencia) · lookalike (sin semilla) | Controles duros: países, `edad_min = edad_minima_audiencia` (18), `genero: todos`, `excluye_categorias_sensibles`. Sin intereses sensibles ni lookalike de compradores amarillos en UE/UK. Género o 25+ solo como prueba A/B con gate H |
| `special_ad_categories` | `[]` · `EMPLOYMENT` · `FINANCIAL_PRODUCTS_SERVICES` | La fija el dictamen de X1 según lo que el anuncio **ofrece** (listados de empleo o producto financiero; la guía de carrera sin listados y la educación financiera sin producto no la requieren, 25 §5.3). Si ≠ `[]`: sin intereses, 18–65, gate H del dueño + dictamen de X1 (decisión 14: sin abogado; el campo `requiere_gate_humano_legal` de `oferta.json` conserva su nombre histórico y significa eso, no una revisión legal) |
| `ubicaciones`, `atribucion`, `inicio` | Advantage+ · `7d_click` informando también 1 d · programado ≥ `anticipacion_preaprobacion_h` | **Programar el inicio ya es activar**: mismo gate H; el script recalcula la hora. Revisión previa de políticas `[VERIFICAR]` (HC-25) |
| `canal_ejecucion` | N0–N1: MCP en la sesión Code · N2+: `meta.*` con Marketing API y token operador | El runner no carga conectores y ningún agente recibe credenciales (docs/06 D-19); conflicto A5-1 |

**Diseño estadístico** (docs/08, método bayesiano de O0).
- **Se decide por P(CPA neto ≤ `cpa_be`)** con compras válidas de Stripe (5.3, 5.9), nunca por las de Meta ni por "una venta". Beta (conversión) × Gamma (clics por gasto), prior débil del escenario central de D3 (50 clics). `evaluar_celda`: MATAR si P(CPA > BE) ≥ 95 % y gasto ≥ 2×BE; ESCALAR (propuesta a D9) con ≥ `n_dec` compras, P ≥ 80 % y CPA típico ≤ objetivo; INCONCLUSO al tope. D7 **no ejecuta la regla**: la congela en `reglas_parada` (`k_corte`, `hash_parametros`).
- **Poder:** ~50 eventos/semana por conjunto es un diagnóstico, no una penalización (HC-1); `eventos = 7×diario/CPA`: con CPA 15 y 30 USD/día salen ~14, así que el aprendizaje limitado se asume y se decide por compras acumuladas. Descartar cuesta ≈ 3×BE y confirmar un ganador ≈ 16×BE `[HIPÓTESIS]`: un test chico puede **refutar**, no validar, y se declara.
- **Variante `[NUEVO]` cribado → confirmación (opcional):** (1) ABO de 3–6 conjuntos de 1 anuncio, ≤ 48 h, que **ordena** conceptos por clics de enlace e inicios de pago con intervalos, sin matar por compras; (2) los 1–3 mejores pasan a una campaña `CBO_1AS` **nueva** (agregar anuncios a un conjunto que aprende reinicia, HC-3). Su gasto cuenta dentro de `gasto_total_test_por_oferta`.

### 3.3 Salidas (contrato de salida)

| artefacto | ruta | campos obligatorios | consumidor |
|---|---|---|---|
| Plan de campaña | `07-campana/campana.json` (`campana.schema.json` 1.2.0) | Los del esquema (`estado` borrador→preflight_ok→aprobada→activa↔pausada→cerrada, `estructura`, `evento_optimizacion`, `atribucion`, `paises`, `idioma`, `presupuesto` en unidad menor con `spend_cap` (entero o `null`), `spend_cap_minimo_meta` y `candado_alternativo{tipo, stop_time, lifetime_budget}` (obligatorio si `spend_cap` es `null`), `economia{cpa_equilibrio = economia.cpa_be, cpa_objetivo = economia.cpa_obj, cpa_max, k_corte, n_anuncios}`, `special_ad_categories`, `audiencia`, `nombres`, `url`, `anuncios[]`, `reglas_parada`, `criterio_validada`, `ids_meta`) y `hash_config` = SHA-256 del JSON canónico de `campana.json` sin `hash_config` (así lo define el contrato); el estado vivo de cada `object_id` en Meta (presupuesto, `spend_cap`, evento, targeting, creativo, enlace, textos, **DSA**) NO entra en el hash: se compara campo por campo en `meta.activar`; `estado` e `ids_meta` cambian después del sellado [PENDIENTE: lo define CT-3 (LT-10); [SUPUESTO] v0.1: campana.json se sella una sola vez con estado borrador e ids_meta null, los IDs viven en ids_meta.json y las transiciones en estado.json] | D8, D9, QA, hooks |
| IDs | `ids_meta.json` | esquema `ids_meta`: `ad_account_id, campaign_id, adset_ids[], ad_ids[], creative_ids[], creado_en, hash_config`; el mapa `ad_name→ad_id` queda en `lanzamiento.log` (el esquema no admite `canal` ni mapas) | D8, D9, F2 |
| Preflight | `preflight.json` | por `P01…P24` y `P25` (esquema `preflight` 1.0.0; `P25` obligatorio si `special_ad_categories` no está vacío): `estado, evidencia`; las extensiones `PX1…PX4` de A1 no caben en el esquema (rechaza `P26+`): bloquean igual, se evalúan aparte con `meta.preflight.items_px` (informe fuera del objeto sellado; ola 2 B5b; hoy `generar()` solo emite P01–P25) y se anotan en `lanzamiento.log` hasta el MINOR de `preflight` (pedido §11.7); más `semaforo`, `hash_config`, `generado_en` y `valido_hasta` (≤ `campana.preflight_vigencia_h` = 24 h; no confundir con las 6 h de `empresa/infra/estado.json`). `modo` fixture\|vivo no está en el esquema: va en `lanzamiento.log` (un preflight en fixture nunca habilita activar) | gate H, hooks |
| Aprobación | `aprobacion.json` | `aprobacion.schema` 1.0.0: `oferta_id`, `accion` (`activar_campana`; excluyente con `etapa`), `gate`, `nivel`, `hash_objetivo`, `object_ids`, `aprobado_por`, `creado_en`, `vigencia_hasta`; lo escribe el motor tras verificar la orden firmada, nunca el Maker. La orden firmada (`orden_firmada.schema` 1.1.0: `accion: activar_campana`, `oferta_id`, `hash_objetivo`, `object_ids` opcional, `ts`, `nonce`, `firma`) la genera el dueño con `orq firmar` en su terminal (**Ed25519**); en N3, `aprobado_por.tipo = regla` | hooks, `meta.activar` |
| Bitácora | `lanzamiento.log` `[PENDIENTE: sin esquema en contratos/; formato a definir con CT-3 (LT-13, diferido)]` | cada llamada, `active_errors`, monitoreo T+1/6/24/48/72 h | QA, X1, D8 |
| Traspaso | `traspaso.json` | esquema `traspaso`: `ventana_h` (1/6/24/48/72), `medido_en`, `campana`, `anuncios[]`, `gasto{real, esperado}` (con tarifa; `esperado` = techo permitido hasta la ventana: `min(max_teorico_diario × ceil(ventana_h/24), 7 × diario) × (1 + tarifa)`, no el ritmo medio, [SUPUESTO] de D7; el ritmo medio `diario × ventana_h/24` se informa aparte; `real > esperado` es la anomalía `gasto-sobre-esperado` y pausa (§4 paso 11); `[PENDIENTE: lo calcula el llamador (engine.orq/B5); meta.monitor lo recibe por parámetro]`), `estado_aprendizaje`, `rechazos_7d`, `adid_capturado_bp`, `clics_enlace`, `vistas_landing`, `anomalias[]`, `lanzamiento_estable` (solo con `ventana_h = 72`, 0 anomalías y 0 rechazos). `macro_nicho`, `nivel`, `candidato_ref`, `problema_id` y `nicho_id` no viajan aquí: D8, X2 y D1 los leen de `oferta.json` y `estado.json` (R-W3-13) | D8, X2, D1 (radar) |

Pedidos a contratos: §11.7.

### 3.4 Parámetros y umbrales (todos `[HIPÓTESIS]` salvo nota; ya en `parametros.yaml` o `limites.yaml`, sin duplicar)

- **CPA:** `campana.economia.cpa_max` = `economia.cpa_be` (en la moneda de la campaña; `cpa_equilibrio` y `cpa_objetivo` son `cpa_be` y `cpa_obj`, R-W3-12); Ads Manager muestra `cpa_be/(1+tarifa_meta)`, así que el techo se compara con el gasto **facturado** `[NUEVO]`.
- **`k_corte` 3 (2–4), `n_dec` 15 (10–25)** (`testeo.*`): P(0 compras si CPA = `cpa_max`) = e^-k; con 15 compras el CPA tiene ≈ ±26 %.
- **`n_anuncios`** = `min(paquete, campana.n_anuncios_tope 6, floor(techo_total/(k×cpa_max)))`, mín. `n_anuncios_min` 3: menos anuncios, no menos gasto por anuncio. `techo_total` = `min(gasto_total_test_por_oferta, perdida_max_test_por_oferta)`; si falta alguno, exit 5.
- **`presupuesto_total`** (en unidades visibles, sin tarifa) = `max(n_anuncios×k×cpa_max, n_dec×cpa_esperado)` y `≤ total_visible_max = floor(techo_total / (spend_cap_factor × (1 + tarifa_meta)))`, de modo que `spend_cap × (1 + tarifa) ≤ techo_total`. `n_anuncios` baja mientras `n_anuncios×k×cpa_max > total_visible_max` (sin pasar de `n_anuncios_min`); si `n_dec×cpa_esperado > total_visible_max`, el test solo refuta (`total = n_anuncios×k×cpa_max`) y la tarjeta informa `techo_necesario_para_validar = ceil(n_dec×cpa_esperado×spend_cap_factor×(1 + tarifa))` y pide H. `dias` = `economia.dias_test` o `campana.dias_test_defecto` 10 (rango sugerido 7–14), acotado por `campana.dias_test_min` 7 y `dias_test_max` 30 (el choque de 30 con `veredicto.dias_max` 14 es la decisión del dueño de `docs/00` §0 punto 8); `diario = total/dias` ≥ mínimo de la cuenta.
- **`max_teorico_diario`** = `factor_techo_teorico_diario` ("1.75") × diario ≤ `gasto_diario_por_oferta`; semanal ≤ 7× (HC-26). **`spend_cap`** = `spend_cap_factor` "1.10" × total; si queda bajo el mínimo de Meta (≈ 100 USD `[VERIFICAR]`), candado alternativo `stop_time` + `lifetime_budget`.
- **`monto_api`** = `round(monto × offset de Meta)`: 1 para CLP, COP, CRC, HUF, ISK, IDR, JPY, KRW, PYG, TWD, VND; 100 el resto (`meta/monedas.py`); nunca el decimal ISO.
- **Medición y ritmo:** EMQ ≥ `emq_objetivo` (6,0; = `landing.emq_min_purchase`); captura de `adid` en la landing ≥ `landing.captura_adid_min_pct` (95) y compras de Stripe con `adid` ≥ `testeo.cobertura_adid_min_pct` (90; son dos medidas distintas, W3-R03); razón Meta/Stripe 0,8–1,3; vistas/clics ≥ 0,6; `ventana_no_decidir_h` 72; `preflight_vigencia_h` 24; ≥ 30 s entre ediciones, ≤ 4 cambios de presupuesto/h.
- **Cuota y ritmo por nivel de riesgo** (25 §2.4):

| nivel | gasto diario | envíos nuevos | revisión previa |
|---|---|---|---|
| verde | sin tope | libre | lint L1 de X1, muestreo |
| amarillo-A | ≤ 30 % (50 % tras 60 días limpios) | ≤ 3/semana hasta 60 días limpios | RHS (revisión humana de seguridad) en el primer lanzamiento de la hoja × idioma; pre-aprobación 24 h |
| amarillo-B | ≤ 10 % | ≤ 1/mes | no se arma mientras `limites.nivel_max_lanzable` sea amarillo-A (recomendación del dueño, `docs/00` §0 punto 5); si el dueño lo habilita: gate H en cada envío, ayuda verificada del país y las cuotas de la fila |
| rojo | no se arma | — | — |

Amarillo-A sin las claves de riesgo en `limites` no se lanza. El amarillo-A con exposición A+ lleva gate H del dueño por país × macro-nicho × nivel (nota 25 §8.1, decisión 14).

- **Congelación** (`compliance.rechazos_congelar` 2 en `rechazos_ventana_dias` 7): rechazo de **producto o contenido** (ejes C, N) congela la hoja; de **pieza** (P, E) revertido congela el ángulo (un rechazo revertido no cuenta, HC 1210227555661027); dos en 7 días congelan la cuenta. En amarillos, pausa del ángulo al primer rechazo. Reembolsos y disputas (`salud_operativa`): D7 no los calcula, pero no lanza si la oferta, la hoja o el macro-nicho están en pausa naranja/roja; la tarjeta muestra el escalón (amarillos, un escalón más bajo).

Ejemplo numérico: Anexo A3.

### 3.5 KPIs del paso

- **Propios:** % preflight aprobado a la primera; 0 activaciones sin `aprobacion.json`; 0 gasto sobre `max_teorico_diario`; % anuncios aprobados en 1.ª revisión por nivel; **falsos verdes** (rechazo de un anuncio verde); tarifa de ubicación acumulada; 0 activaciones UE sin DSA; tracking vivo a las 24 h (`adid` ≥ 95 %, Purchase deduplicado).
- **Diferidos (D8/F2):** CPA por anuncio, compras Stripe atribuidas, razón Meta/Stripe, estado de cuenta a 30 d y resultado por `problema_id`/`nicho_id` hacia el radar de D1 y X2.

## 4. Flujo paso a paso (SOP)

| # | quién | acción | herramienta |
|---|---|---|---|
| 1 | Script | Puertas: sin `PAUSA`; infra VERDE < 6 h; límites completos (`evaluar_limites`); `locale` ∈ `locales_permitidos`, países ⊆ `paises_permitidos` ∩ matriz país × nivel (J01); `riesgo.nivel` ≤ `nivel_max_lanzable`, hoja no pausada, cuota y envíos; sellos de X1 vigentes; ofertas en test < máximo; cuenta permitida; alta de la oferta hecha: `alta.json` con `completo = true` y los pasos `meta-dataset`, `meta-capi-token`, `meta-dominio-verificado` y `spend-cap` en `ok`; los IDs de `tracking.json` deben coincidir con los de la `evidencia` del alta | `engine.orq` |
| 2 | Script | Economía y presupuesto (§3.4); aborta si diario × 1,75 > tope o `n_anuncios` < mínimo → borrador `campana.json`; el presupuesto, `n_anuncios` y la tarifa los calcula `meta.payloads.calcular_presupuesto` (con `python -m meta.payloads presupuesto`) y el evento `decision.presupuesto.evento_optimizacion_recomendado` | `meta.payloads`, `decision.presupuesto` |
| 3 | Maker (N0–N1) / Script (N2+) | Lectura de cuenta: estado, pago, mínimo diario, página, DSA por defecto, dataset, calidad, volumen; estado de calidad de la cuenta: declaración del dueño (≥ semanal) leída de `empresa/compliance/salud_actual.json` (`calidad_cuenta_meta`, `departamentos/14` §3.1), `[VERIFICAR]` si el conector llega a exponer «Calidad de la cuenta»; sin declaración vigente, P04 es ROJO por dato ausente | `ads_get_*` / `meta.preflight` |
| 4 | Maker + Script | Estructura, evento, audiencia (§3.2); URL con macros y nombres 5.2. **QA-A** sobre el plan antes de crear (sin ronda): P14–P19, P25 y PX1–PX4 sobre `paquete.json`, porque los creativos son inmutables | `meta.nombres` |
| 5 | Script (N2+) / Maker autorizado (N0–N1) | Borrador `PAUSED`: campaña → conjunto (con DSA) → creativos → anuncios; reutiliza por prefijo `{oferta_id}_TEST_`; lee `active_errors` | `meta.crear`; `ads_create_*` |
| 6 | Script | Preflight P01–P25 (`meta.preflight`) y PX1–PX4 (`meta.preflight.items_px`, informe aparte), sella `hash_config`; genera `preflight.json` y la lectura viva `07-campana/lectura_viva.json` (`python -m meta.lectura_viva`; [PENDIENTE: que `engine.orq` la genere antes del QA (B1/O0) y su esquema, pedido a CT]) que se entregan al QA | `meta.preflight` |
| 7 | Maker | Vistas previas por anuncio y ubicación | `ads_get_ad_preview` |
| 8 | QA | Revisión independiente (§6), máx. 2 rondas; solo lee `preflight.json` y `lectura_viva.json` (sin MCP ni Bash) | lectura de archivos |
| 9 | X1 + Humano | X1 sella `hash_config` + `object_ids`; **gate H**: tarjeta de 1 página (gasto máximo con tarifa, CPA, nivel y reencuadre, `problema_id`, riesgos, DSA, hash) y `orq firmar --accion activar_campana` | `compliance`, `engine.orq` |
| 10 | Script | `meta.activar` (docs/06 N12): relee Meta; exige hash vivo = aprobado = preflight < 24 h y `object_ids` = sello: `meta.activar` relee el estado vivo y lo compara campo por campo con `campana.json` sellado (`diferencias_config_viva`) `[PENDIENTE: lo construye B5: DSA propio cuando exista campana.economia.dsa (LT-10); enlace y textos solo con --creativos]`; activa anuncios → conjunto → campaña; relee `effective_status` y pausa lo imprevisto | Marketing API; `ads_activate_entity` está en `deny` del piso (docs/09 §6): no se activa por MCP. Si un borrador por MCP (N0–N1) llegara a publicarse, rige `allow_partial_publish=false`, `ignore_validation_errors=false`, solo bajo hook |
| 11 | Script | `meta.monitor` T+1/6/24/48/72 h (`python -m meta.monitor`): entrega, errores, revisión, gasto vs esperado (con tarifa), Purchase/IC, `adid`; pausa (única escritura viva) si gasto 24 h > `max_teorico_diario`, errores bloqueantes o `PAUSA` `[PENDIENTE: B5: pausa por gasto, active_errors y congelación por eje; hoy meta.monitor solo pausa anuncios DISAPPROVED y congela por cuenta]`. Disparador: `engine.orq` a T+1, 6, 24, 48 y 72 h `[PENDIENTE: lo construye B1; hoy orq no tiene subcomando de monitoreo]`; hasta entonces, el dueño corre `python -m meta.monitor` según `docs/10` §1.4 y §2.4. Si una ventana no se midió hasta su hora más la tolerancia, se registra `VENTANA_OMITIDA` en `lanzamiento.log` y se escala al dueño; tolerancia: `[PENDIENTE: parámetro campana.tolerancia_ventana_min, LT-52, valor [HIPÓTESIS] a calibrar]` | Marketing API (lecturas equivalentes a `ads_get_errors` y `ads_account_get_activity_logs`; sin MCP en lo desatendido) |
| 12 | Maker + X1 | Rechazo: clasificar (técnico/política, eje P·C·E·N); técnico = anuncio nuevo corregido; política = X1 decide; **nunca reenviar igual ni editar en bucle** | `ads_get_errors` |
| 13 | Script | Traspaso a D8 si 72 h sin incidentes; si no, `ESCALAR` | `meta.monitor` |

Responsable de la ventana T0 → T+72 h: D7 (el Maker en modo VIGILAR interpreta cada `traspaso.json`, clasifica rechazos por eje y pide a D6/X1; no escribe en Meta ni pausa por su cuenta). D8 asume la campaña con el traspaso estable de 72 h (`lanzamiento_estable = true`).

`ads_create_*` deja DRAFT, pero publicar puede dejar ACTIVO ⇒ **todo publish es activación**. Pruebas de aceptación previas a N2 `[VERIFICAR]` (cuenta de prueba, inicio a +7 días): estado tras publicar con y sin `publish_as_active`; macros en `link_url` o `url_tags`; revisión con anuncio programado.

## 5. Agente Maker

- **Rol:** media buyer técnico que propone estructura, evento y audiencia y deja el expediente listo. **No** activa, no sube presupuesto, no edita campañas vivas, no crea audiencias ni experimentos, no toca píxel/eventos, no borra, no fija `self_ai_disclosure` ni la categoría especial, no escribe copy, no clasifica ni rebaja el riesgo.
- **Herramientas:** `Read`/`Write` en `ofertas/<id>/07-campana/` salvo `aprobacion.json`; `Bash` solo `python -m meta.{nombres,payloads,preflight}`. **MCP** (solo en sesiones interactivas del dueño, hasta N2; los procesos desatendidos `claude -p` no tienen conectores): de lectura, `ads_get_*`, `ads_insights_*` y `ads_get_ad_preview*`. Las de escritura (`ads_create_*`, `ads_update_entity`) no las usa desatendido y, en la sesión interactiva, solo las que el piso deja en `ask`, con mi autorización explícita en cada una y nunca `ads_activate_entity`. Lo que el piso deniega (`ads_creative_*`, p. ej. la subida de creativos) lo hace el código del motor con el token de Meta restringido `[PENDIENTE: lo construye B5/B8; hoy meta.crear no sube medios y su modo live está bloqueado]` o a mano el dueño. El piso está en `docs/09-runtime-de-agentes.md` §6 y, en su versión para hoy, en `docs/_historial/settings-piso-hoy.propuesta.json`; aún no está instalado (no existe `.claude/settings.json`): lo decide el dueño. Sin credenciales de Meta: las escrituras N2+ son de `meta.crear`/`meta.activar`.
- **Contexto:** §3.1, `04-meta-ads.md`, `fallas_conocidas` (X2), `claims_a_evitar` y `angulo_seguro` del riesgo.
- **Guardarraíles por hooks** (`.claude/settings.json`; matcher `mcp__claude_ai_Meta_ADS__.*`; falla cerrado; sin `--bare`): publicar = el hook `pretooluse_activacion` deniega salvo `aprobacion.json` presente, sello de X1 firmado y vigente con `object_ids` exactos y cuenta permitida (la firma Ed25519, el hash vivo y el preflight vigente los verifica el script: `engine.guard` y `meta.activar`); `ads_update_entity` solo `{"status":"PAUSED"}`; presupuesto o `spend_cap` fuera de límites, cuenta fuera de la lista, `PAUSA` o infra no VERDE = `deny`. `permissions.deny` y `ask` son los del piso (docs/09 §6; no se repiten acá): `ads_activate_entity` y la familia de escritura que D7 no usa (`ads_boost_ig_post`, `ads_experiment_*`, `ads_delete_*`, `ads_creative_*`, `ads_pixel_*`, `ads_catalog_*`, `ads_update_custom_audience*`) van en `deny`; `ads_create_*` y `ads_update_entity` en `ask` (en el runner, `ask` equivale a denegar); `Edit` sobre `limites.yaml`, `parametros.yaml`, `agentes/hooks/**`, `.claude/**` y los sellos de X1 también va en `deny`; `aprobacion.json` no la escribe el Maker. Segundo candado: límite de gasto de la cuenta en Meta (HC-28).
- **Desatendido (N3–N4):** Marketing API con usuario del sistema "operador" (no admin), versión fijada, `url_tags`, creación `PAUSED`, activación solo por `meta.activar` con orden por regla (§7).

## 6. Agente QA

**Independencia:** contexto limpio; recibe `07-campana/*`, capturas, contrato §3.3, `paquete.json`, `tracking.json`, `limites.yaml`, rúbrica y `fallas_conocidas`; solo lectura, **sin MCP ni Bash** (se lanza con `--tools "Read,Grep,Glob"` y `--disallowedTools "mcp__*"`, docs/09 §9.2): el QA **no re-ejecuta el preflight ni lee Meta**. Las comprobaciones deterministas y la lectura viva de las entidades las produce **código del motor antes del QA** y se las entrega en `07-campana/preflight.json` y `07-campana/lectura_viva.json` `[PENDIENTE: el motor aún no la genera antes del QA (B1/O0); el módulo `meta.lectura_viva` existe y no tiene esquema en `contratos/`]`; el QA juzga sobre esos archivos (no los escribe ni los sustituye por lo que diga el Maker). Salida `qa/d7-v<n>.json` (backbone 6): veredicto, puntajes con evidencia, hallazgos estructurados (`check_id, patron_clave, severidad, etapa, skill_version`) con su `correccion`, `cambios_aplicados` = [], mejoras de valor, `aprendizajes_para_skill[]`.

### 6.1 Checks deterministas (L1; todos BLOQ salvo nota)

Los checks que comparan contra Meta, la red o los hooks (recálculo de `hash_config`, C02, C03, C06, C07, C08, C12) los calcula código del motor antes del QA; el QA verifica su evidencia en `preflight.json` y `lectura_viva.json` y juzga el resto leyendo los archivos.

- **C01** esquemas válidos y `hash_config` recalculado coincide. **C02** entidades en Meta = `campana.json` (objetivo, evento, países, presupuesto, `spend_cap`, stop, nombres, categorías, DSA, estructura Advantage+ con sus tres indicadores `ENABLED` `[VERIFICAR]`). **C03** todo en DRAFT/`PAUSED` antes del gate; 0 objetos ACTIVE o ajenos a `ids_meta`; `active_errors` vacío.
- **C04** dinero: diario × 1,75 ≤ `gasto_diario_por_oferta`; total con tarifa y `spend_cap` con tarifa ≤ `techo_total`; monto con offset de Meta. **C05** nombres 5.2 (ASCII, `_`, sin `|`), macros, `ejemplo_resuelto` sin vacíos. **C06** enlace 200; `landing_hash`, precio y moneda iguales en paquete y checkout. **C07** dataset = `tracking.json`; EMQ; evento de prueba con el mismo `event_id` en navegador y servidor.
- **C08** dominio, página, pago, cuenta "saludable" (declaración del dueño vigente en `salud_actual.json`; sin ella, falla por dato ausente), límite diario de Meta ≥ 1,75× diario, saldo prepago ≤ 3 días de gasto. **C09** (MAYOR) mejoras de Meta apagadas; `self_ai_disclosure` = `politica_divulgacion_ia`. **C10** textos idénticos a `paquete.json`, `lint_claims` OK, `claim_ids` ⊆ `claims_permitidos`; ningún anuncio presenta el mecanismo como claim de salud o ingresos.
- **C11** (MAYOR) `locale` y países = `mercado.json`, sin mezcla de variantes. **C12** hook probado en seco (sin aprobación, firma inválida, hash viejo, `object_ids` de más) → `deny`.
- **C13** riesgo: `nivel` ≤ `nivel_max_lanzable`, hoja no pausada, cuota, matriz país × nivel, `special_ad_categories` = dictamen de X1, sin intereses sensibles ni lookalike amarillo en UE/UK. **C14** DSA con beneficiario y pagador = LLC en cada conjunto si hay UE o "mundial". **C15** sin términos sensibles (`terminos_sensibles/<locale>.yaml` `[PENDIENTE: lo construye X1; hoy no existe, compliance/reglas_sensibles.yaml es léxico de claims y solo cubre es-ES y en-US: sin léxico C15 falla cerrado]`) en nombres, `slug`, URL ni UTM: `{{campaign.name}}` viaja a la URL (X1-D01).

### 6.2 Rúbrica de criterio (L2; 0–5 con evidencia; PASS ≥ 4,0 de media y ningún ítem < 3; sin parámetro propio: se usa `compliance.umbral_rubrica_pass` hasta que exista `campana.umbral_qa` `[PENDIENTE: lo define CT-3 (LT-13, diferido)]`). Ancla 1 / 3 / 5

- **R1 Economía y poder:** sin derivación / fórmulas ok / derivado de `cpa_max` con tarifa, dice si el test valida o solo refuta y cuánto falta para `PURCHASE`.
- **R2 Estructura y señal:** sin justificar / justificada / limitaciones declaradas, fase 2 = campaña nueva, cribado solo si cabe.
- **R3 Medición:** UTMs sin IDs / IDs sin conciliación / unión por IDs, ventanas, conciliación con Stripe y tolerancia a tráfico sin consentimiento.
- **R4 Cumplimiento por candidato:** claims dudosos pasan / lint ok sin previews / previews revisadas, nivel, cuota y matriz comprobados, plan de rechazos por eje y ángulo seguro respetado.
- **R5 Reglas de parada:** ausentes / genéricas / numéricas con `hash_parametros` y ejecutor. **R6 Riesgo de cuenta única:** compartida / dedicada / portafolio aislado, límites duros.
- **R7 Operabilidad:** log incompleto / completo / otro agente retoma desde el log. **R8 Tarjeta de gate:** ilegible / completa / el dueño decide en 2 min.

### 6.3 Simulaciones (L3), mejoras y veredictos

1. **Revisor de políticas de Meta por nivel:** ¿rechazaría cada anuncio o landing y qué eje lo hundiría? 2. **Auditor del peor caso:** gasto máximo en 24 h, 7 d y total (175 %, `spend_cap`, límite de cuenta, tarifa) ≤ lo aprobado. 3. **Comprador escéptico en móvil**, en el idioma de la oferta. 4. **Fallo de piezas:** si cae el webhook o el píxel, ¿en cuántas horas lo sabríamos? 5. **Concentración:** ¿qué pasa si esta cuenta cae hoy?

Mejoras de valor (si no alteran promesa, precio, claims, presupuesto ni contrato): menos `n_anuncios`, ratio 9:16, `placement` en la URL. Veredictos y 2 rondas según backbone 6; un BLOQ en C03/C04/C12/C13/C14 o un FAIL de X1 ⇒ `FAIL` sin ronda de cortesía. Anti-sello: ≥ 3 hallazgos o evidencia de revisión. **Calibración:** sembrados S1–S22 (≥ 90 % de BLOQ) y 2 campañas doradas de macro-nichos distintos, una en otro idioma, deben dar PASS (A2); y la matriz nivel × país del preflight (PX3) se contrasta con una muestra rotada de `casos-frontera.yaml` (nota 25 §11; hoy `docs/_historial/hwr-semillas/`): 0 falsos verdes; fixtures offline, jamás objetos reales.

## 7. Gates y autonomía

Nivel por etapa en `empresa/autonomia.yaml` (`etapa:D7`); activar es `accion:activar_campana`, siempre en `acciones_gate_humano`: por defecto H en todo nivel; la «S» de `gates.json` en N3/N4 solo rige con una regla preaprobada y firmada por el dueño (`aprobado_por.tipo = regla`) o si el dueño quita la acción de esa lista con firma (C-W3-02).

| nivel | qué hace D7 | gate |
|---|---|---|
| N0 | Dueño arma con Claude Code y MCP; se forja la skill | H en todo (`orq ingresar`) |
| N1 | Maker con skill crea el borrador; dueño revisa y activa | H |
| N2 | Maker + QA + preflight; `meta.*` por API; hooks | **H en activar**: `orq firmar` fuera de la sesión del agente |
| N3 | Activación por script con topes; orden por regla solo con preflight y QA = PASS, riesgo verde o amarillo-A con RHS hecha y sin bandera abierta, gasto ≤ `autoaprobar_hasta`, cuenta saludable | H si gasto > umbral, amarillo-B, primer lanzamiento de un idioma o macro-nicho (M1), hoja nueva, primer rechazo de una hoja o PASS_CON_NOTAS |
| N4 | Botón "Lanzar nueva oferta" con tope diario global y kill switches | Excepciones; revisión semanal |

**Dinero, cumplimiento, reputación:** guardarraíles deterministas (hook, `limites.yaml`, `spend_cap`, límite de cuenta, `PAUSA`, infra VERDE), nunca solo instrucciones; el veto de X1 no se relaja. Todo cambio de la skill exige H.
**Ascenso:** N2→N3 con ≥ 10 lanzamientos, 0 incidentes de gasto, ≥ 85 % de preflights a la primera, ≥ 90 % de campañas sin edición, ≥ 95 % de anuncios aprobados en 1.ª revisión, QA ≥ 90 % de sembrados, 0 restricciones y 0 falsos verdes. N3→N4: 30 días sin incidentes y reconciliación Meta/Stripe en rango.

## 8. Riesgos y modos de falla

| riesgo | señal temprana | mitigación | resp. |
|---|---|---|---|
| Publicar deja ACTIVO sin gate | entidad ACTIVE | hook, `object_ids`, sello, C03 | Script/QA |
| Aprobación forjada u objeto editado tras aprobar | hash vivo ≠ aprobado | Ed25519, `Write` denegado, relectura antes de publicar | Script/QA |
| Unidad de moneda (×100 en CLP) | monto leído ≠ calculado | offset de Meta, C04, S11 | Script/QA |
| Gasto > presupuesto (175 %, tarifa no visible en Ads Manager) | factura > gasto leído | techo sobre máximo teórico y facturado, `spend_cap`, pausa | Script |
| Cuenta restringida por rechazos de **producto** (Meta cuenta advertencias, no gasto) | "Needs attention" | cuota por nivel, congelación escalonada, activos no compartidos, prepago ≤ 3 días; sin cuentas nuevas para esquivar; apela solo el dueño. Riesgo residual aceptado por el dueño (decisión 15): sin gestor de contraseñas, llaves físicas ni segundo administrador; los frenos de software no cambian | X1/dueño |
| Falso verde | rechazo de un anuncio "aprobable" | pre-vuelo 24 h, pausa del ángulo, caso nuevo en X2 | X1 |
| DSA ausente o LLC pública en la Biblioteca (1 año) | anuncio UE sin publicar | C14/PX1; decidir nombre antes del primer gasto | Dueño/Script |
| Tracking roto o sin consentimiento (UE/UK) | `adid` < 95 % | P09/P10; Stripe es la verdad; pausa y vuelta a D5 | Script/D5 |
| Reinicios por editar; deriva del sitio o edición en Ads Manager; términos sensibles en la URL | hash vivo ≠ sellado | estructura congelada 72 h, nombres limpios, K03 de X1 | Hook/X1 |
| Test sin poder / "una venta valida" | INCONCLUSO | advertencia R1, `evaluar_celda`, compras de Stripe | Maker/QA/D8 |
| Verificación financiera de Meta (AU, IE, ES) o categoría omitida | Meta la pide | parada dura; X1 decide | X1 |

## 9. Mejoras respecto del video

1. **[NUEVO]** Presupuesto desde la economía unitaria con tarifa de ubicación (@neurohain).
2. **[NUEVO]** Decisión bayesiana congelada en `reglas_parada`, poder declarado, cribado que ordena sin matar.
3. **[NUEVO]** Gate firmado (Ed25519) atado a `hash_config` con estado vivo y sello de X1.
4. **[NUEVO]** Topes nativos de Meta independientes del código; preflight de tracking, DSA y riesgo por candidato.
5. **[NUEVO]** Test por idioma; mercados se comparan como ofertas de una familia.
6. **[NUEVO]** Cuota y ritmo por nivel, congelación por eje, cuenta única protegida.
7. **[NUEVO]** Monitoreo T+1…72 h con traspaso a D8 y retorno al radar de D1; offset de moneda de Meta.

## 10. Forja de la skill (pestaña Code)

### 10.1 Prompt de arranque (copiar y pegar)

```
ROL: Sos el Maker del departamento D7 (Campañas Meta) de un sistema que lanza ofertas de productos digitales de bajo ticket en cualquier idioma y mercado, dentro de los 3 grandes nichos (salud, relaciones, dinero). Armás el borrador técnico de una campaña de TEST de Meta Ads, con preflight y expediente de aprobación. NUNCA activás, publicás, gastás ni cambiás nada en Meta sin mi permiso explícito en este chat. Esta sesión está abierta en <carpeta del proyecto>.

LEÉ PRIMERO (rutas desde esa carpeta): docs/_backbone.md v2.2.x (§3.1, §5, §6, decisiones 13, 14 y 15); departamentos/08-campanas-meta.md; docs/06-bases-del-testeo.md (N11-N12); docs/08-protocolo-estadistico-del-testeo.md; docs/contratos.md; contratos/campana.schema.json; docs/_investigacion/04-meta-ads.md, 02-conectores.md (D7), 07a (DSA, tarifa), 25-marco-salud-relaciones-dinero.md (§2.4, §5.3, §10).
ENTRADA: oferta_id y su idioma/locale y países (de ofertas/<oferta_id>/mercado.json; si falta, te los pido: no asumas un país). Archivos en ofertas/<oferta_id>/: 00-brief.yaml, 03-oferta/{oferta,economia}.json, 05-landing/{tracking,checkout,despliegue}.json, 06-creativos/paquete.json; y empresa/limites.yaml, empresa/parametros.yaml, empresa/infra/. Si falta algo o un límite está en null, no lo inventes: pregunta bloqueante; si forjás antes de que existan D3/D5/D6, pedime valores o usá un caso ficticio [SUPUESTO] sin tocar Meta.

TAREA: producí un v1 COMPLETO en ofertas/<oferta_id>/07-campana/: (1) economía y presupuesto con las fórmulas del §3.4 (decision.presupuesto, tarifa de ubicación del país, monto con el offset de moneda de Meta, aviso si el test solo puede refutar); (2) campana.json válido contra contratos/campana.schema.json, con estructura y evento justificados (§3.2), special_ad_categories según el dictamen de X1 y nombres 5.2 sin términos sensibles; (3) preflight.json con P01-P25 y las extensiones PX1-PX4 (Anexo A1; P14-P19, P25 y PX1-PX4 antes de crear, §4 paso 4), incluida la comprobación de nivel de riesgo, cuota, matriz país x nivel y DSA si hay UE; (4) la tarjeta de gate de 1 página; (5) el plan de monitoreo T+1/6/24/48/72 h y el protocolo de rechazos por eje. Podés LEER Meta con ads_get_* e ads_insights_*; crear en BORRADOR solo con las herramientas que el piso deja en ask y con mi autorización explícita en cada llamada; si no, entregá los payloads exactos sin ejecutarlos. Nunca llames a ads_activate_entity. No escribas copy ni cambies el nivel de riesgo. self_ai_disclosure, mejoras automáticas, género/edad y nombre del beneficiario DSA: preguntámelos.

FORMATO: archivos del contrato §3.3 y un resumen con [SUPUESTO], preguntas bloqueantes, riesgos, [VERIFICAR] y pruebas de aceptación pendientes.
ACEPTACIÓN: máximo teórico de gasto <= límites; presupuesto que cubre corte y validación o declara que solo refuta; ninguna cifra sin derivación ni claim fuera de paquete.json; hash_config sella campana.json y el estado leído de Meta; todo sin activar; autorrevisate contra R1-R8 y C01-C15.
REGLAS: no inventes datos, URLs ni IDs; marcá [SUPUESTO]; preguntas bloqueantes primero (máx. 8) y esperá mis respuestas; sin acciones con costo o efecto externo sin permiso; español con tildes.
```

### 10.2 Cómo pulir

Armá a mano una campaña **real y chica** (N0), tope mínimo, oferta verde. Mirá: ¿el cálculo evitó un error de presupuesto o moneda?; ¿entendés la tarjeta en 2 minutos?; ¿qué campo de Meta tocaste que el Maker no previó?; ¿llegaron los eventos el día 1? Máximo 3 iteraciones de ~2 h; congelá cuando dos campañas seguidas (distinto macro-nicho o idioma) salgan sin retoques.

### 10.3 Estructura de la skill a generar

```
.claude/skills/d7-campanas-meta/
├── SKILL.md      # SOP §4, reglas §3.2
├── rubric.md     # R1–R8, C01–C15
├── references/   # Anexo, mapa MCP↔API, políticas X1, tarifa y DSA por país
├── templates/    # campana, preflight, aprobacion, tarjeta-gate, traspaso
├── scripts/      # envoltorios a meta.* y decision.presupuesto
└── evals/        # casos, sembrados S1–S22, dorados
```

### 10.4 Definición de listo (DoD)

`meta.payloads.calcular_presupuesto` reproduce A3 `[VERIFICAR: test de B5 con 192 / 19,2 / 33,6 y CLP con offset 1]`, advierte el contraejemplo y convierte CLP con offset 1; `meta.preflight` P01–P25 y `items_px` (PX1–PX4) en solo lectura; el hook bloquea el 100 % de las activaciones sin aprobación; 2 campañas de macro-nichos distintos (una en otro idioma) dan PASS; el QA detecta ≥ 90 % de BLOQ sembrados; pruebas `[VERIFICAR]` resueltas en cuenta de prueba; la firma rechaza un archivo escrito por el agente; el dueño aprueba la tarjeta sin cambios dos veces seguidas.

### 10.5 Evals mínimos

1. Salud verde `it-IT` (plan de comidas semanal, sin claims de peso), presupuesto holgado (`PURCHASE`, tarifa 3 %, DSA). 2. Misma oferta con presupuesto bajo (`INITIATE_CHECKOUT`, "solo refuta"). 3. **Otro nicho e idioma:** dinero verde `pl-PL` (hoja de costeo y precio mínimo para quien vende manualidades; sin "ganar" ni cifras de ingreso) y relaciones verde (tarjetas de conversación para parejas). 4. Amarillo-A (RHS pendiente → H); amarillo-B o rojo no se arma. 5. Paquete con 2 anuncios rechazables; tracking caído; UE sin DSA. 6. Sembrados S1–S22; cuenta CLP prepaga.

## 11. Preguntas abiertas / decisiones del dueño

1. `[DUEÑO]` Primer idioma/mercado y huso de la cuenta (irreversibles). Polonia e Italia son hipótesis, no priores: un mercado a la vez (`mercados_test_paralelos_max` = 1) y el primer mercado lo decide el dueño con la propuesta de M1 (docs/08 §7; 16 M6).
2. `[DUEÑO]` Cuenta deshabilitada previa (apelar o abandonar; nunca abrir otra para esquivarla).
3. `[DUEÑO]` Topes de `limites.yaml`: `gasto_diario_por_oferta`, `gasto_total_test_por_oferta`, `perdida_max_test_por_oferta` (diferida: se definirá con los presupuestos de testeo), `autoaprobar_hasta`, `limite_gasto_cuenta_meta`, tipo de pago (tarjeta virtual o prepago ≤ 3 días de gasto) y custodia de la clave Ed25519.
4. `[DUEÑO]` Nombre visible en la Biblioteca como beneficiario/pagador DSA (LLC o marca); política de `self_ai_disclosure` y de mejoras de Meta.
5. `[DUEÑO]` ¿`INITIATE_CHECKOUT` como fase de señal y que un test chico "solo refute"? Cuotas por nivel (30 %/10 %, 3 envíos/semana); género o 25+ (recomendado: amplia 18+); excluir o no FR/IT/ES/AT por la tarifa (Meta no garantiza reducirla).
6. `[VERIFICAR]` PAUSA vs ACTIVO al publicar; macros en `link_url`/`url_tags`; revisión de anuncios programados (hooks en `-p`: ver docs/09 H4; se repite la sonda de hooks tras cada actualización de Claude Code); tarifa vigente (FR/IT/ES 3 %, AT 5 %, UK 2 %, TR 5 %; relectura mensual) y si aparece en "Importe gastado"; mínimo de `spend_cap`; versión de API y estructura Advantage+; `age_max` con Advantage+ Audience (la skill usa 18–65; `campana.schema` 1.2.0 no agrega `edad_sugerida` ni `edad_dura` por esto); si "madres" en tercera persona cuenta como atributo (25 §12.2).
7. Pedidos a contratos y código (para «Pedidos de S-A» de `coordinacion-sesiones.md`): los esquemas `aprobacion`, `traspaso` y `preflight` ya existen y `tarifa_meta_bp` ya está en `economia`; versiones vigentes (`x-version`): `traspaso` 1.1.0, `aprobacion` 1.0.0, `preflight` 1.0.0, `orden_firmada` 1.1.0, `economia` 1.2.0, `limites` 1.3.0; siguen pendientes `dsa`, `macro_nicho`, `riesgo_nivel`, `tarifa_meta_bp` en `campana.economia` (copia de `economia.entradas_usadas.tarifa_meta_bp`, que D3 toma de `tarifas.json#recargo_meta_bp` del país de mayor recargo del clúster; nombre único, W3-R05); `preflight` MINOR con las extensiones PX1–PX4 (hoy `P26+` no valida). Ya registrados en CT-3 (`docs/_historial/ct3-pedidos-tardios.md`): LT-08 (regla cruzada del evento y ejemplo dorado), LT-09 (parámetros del evento de optimización), LT-10 (`campana.economia` y alcance del hash), LT-11 (categoría especial en el dictamen de X1), LT-12 (PX1–PX4 y `despliegue.json`), LT-13 (claves de riesgo y matriz país × nivel; diferidos: `lanzamiento.log` y `campana.umbral_qa`).

## Anexo (se traslada a `references/` de la skill)

### A1. Preflight P01–P25 y extensiones PX1–PX4 (determinista; cualquier fallo bloquea; `modo: fixture` nunca vale como vivo)

P01 sin `PAUSA` · P02 cuenta ACTIVE y consultable · P03 método de pago · P04 cuenta "saludable" (declaración del dueño ≥ semanal en `empresa/compliance/salud_actual.json`; sin declaración vigente, ROJO por dato ausente) · P05 límite diario de Meta ≥ 1,75× diario · P06 límite de gasto de cuenta fijado por el dueño (prepago: saldo ≤ `gasto_max_aprobado` y ≤ 3 días) · P07 página vinculada · P08 dataset activo con eventos recientes · P09 EMQ ≥ objetivo (Purchase se mide a T+24/72 h; antes, payload de prueba completo) · P10 evento de prueba por navegador y servidor con el mismo `event_id` · P11 dominio verificado · P12 enlace 200 sin redirecciones · P13 URL sin vacíos, con macros · P14 `landing_hash`, precio y moneda = paquete y checkout · P15 copys = paquete y `lint_claims` OK · P16 mejoras de Meta en OPT_OUT (`text_optimizations`, `image_touchups`, `image_animation`, `inline_comment`, `enhance_cta`) · P17 `self_ai_disclosure` = política · P18 `locale` y países = `mercado.json` ⊆ `paises_permitidos` · P19 nombres 5.2 · P20 presupuesto y `spend_cap` ≤ límites con offset de Meta · P21 `active_errors` vacío, 0 objetos ajenos · P22 vistas previas · P23 ofertas en test < máximo · P24 `hash_config` sellado · P25 `special_ad_categories` = dictamen de X1 y sello vigente sobre `hash_config` y `object_ids` [PENDIENTE: lo construye S-B con el campo de categoría requerida del dictamen de X1 (LT-11); hoy meta.preflight._p25 da NO_APLICA si special_ad_categories = [], así que no detecta la categoría omitida (S19): lo cubre C13 del QA]. **Extensiones `[NUEVO]` (PX; el esquema 1.0.0 solo admite P01–P25; las emite `meta.preflight.items_px` como informe aparte, sin entrar en el objeto sellado):** PX1 DSA en cada conjunto UE/"mundial" (sin él Meta no publica, tampoco por API) · PX2 tarifa de ubicación en techo y tarjeta · PX3 riesgo: nivel, hoja, cuota, envíos, matriz país × nivel · PX4 sin términos sensibles en nombres, `slug`, URL, UTM ni eventos.

### A2. Defectos sembrados (BLOQ salvo nota)

S1 `&asid=` vacío (C05) · S2 diario 100 vs tope 40 (C04) · S3 campaña ACTIVA antes del gate (C03) · S4 precio 19 en anuncio y 17 en landing (C06) · S5 copy "Ganá USD 3.000 al mes" (C10) · S6 aprobación de versión anterior (C01/C12) · S7 `PURCHASE` con 12 USD/día y `cpa_esperado` 30 (MAYOR) · S8 `es-MX` con "vosotros" (MAYOR C11) · S9 mejoras de texto activas (MAYOR C09) · S10 dataset inactivo (C07) · S11 CLP con monto ×100 (C04) · S12 sin `spend_cap`/`stop_time` (C04) · S13 firma inválida (C12). **Nuevos:** S14 candidato rojo o amarillo-B sin gate (C13) · S15 envío amarillo sobre cuota o con hoja pausada (C13) · S16 país fuera de la matriz (C13) · S17 conjunto UE sin DSA (C14) · S18 término sensible en `hook_id`/`slug` que viaja en la URL (C15) · S19 anuncio de producto financiero con `special_ad_categories: []` (C13) · S20 lookalike de compradores amarillos en UE/UK (C13) · S21 anuncio rechazado recreado idéntico (C10) · S22 presupuesto sin tarifa que rebasa el techo en Italia (C04).

### A3. Ejemplo numérico `[NUEVO]`

Precio 19 USD, `cpa_be` 16, `cpa_esperado` 12, n=4, k=3, sin tarifa: corte 4×3×16 = 192; validar 15×12 = 180; total 192 USD; 10 días → 19,2/día; máximo teórico 33,6/día. Umbral `PURCHASE` 0,5×(50/7)×12 ≈ 43/día > 19,2 ⇒ `INITIATE_CHECKOUT`, y lo dice. Con tarifa 3 % (Italia): facturado 192×1,03 = 197,8; CPA visto 16/1,03 = 15,5. Contraejemplo: CPM 4, CTR 1,2 % y conversión 1,5 % dan CPA ≈ 22 (> 16): inviable; si llega así (`NO_FACTIBLE`), el Maker advierte y escala sin gastar (04 §8.3). Entradas `[HIPÓTESIS]`.

### A4. Hechos de plataforma

- Límites de gasto y edición (HC-26, DV-2: §3.4). Ediciones significativas (segmentación, creativo, evento, agregar anuncio, pausa ≥ 7 d) reinician aprendizaje y disparan revisión (HC-3, HC-25); cambiar un parámetro de URL publicado también (HC-16); resultados maduran en ~48 h (HC-45); intereses = sugerencias al optimizar conversiones (HC-41).
- **DSA:** beneficiario y pagador en todo anuncio nuevo o editado que apunte a la UE o "mundial"; visibles en la Biblioteca hasta 1 año; sin efecto en entrega ni costo (https://www.facebook.com/business/help/605021638170961; 07a A.4).
- **Tarifa de ubicación** desde 2026-07-01 `[VERIFICAR]`: FR/IT/ES 3 %, AT 5 %, UK 2 %, TR 5 %; va en la factura, no en Ads Manager; no aplica a categorías especiales (https://www.facebook.com/business/help/1238737454289085; 07a, 16).
- **Offset de moneda de Meta:** https://developers.facebook.com/docs/marketing-api/currencies. Máx. 50 anuncios por conjunto y formato flexible de 10 medios `[VERIFICAR]` (04 §2.7).
- Glosario: **CBO_1AS** = presupuesto de campaña con un conjunto Advantage+; **cribado** = ABO corto que ordena; **RHS** = revisión humana de seguridad (25 §2.4); **hoja** = sub-nicho del árbol de D1.

### A5. Conflictos resueltos (manda el contrato/código)

1. **MCP hasta N2 (backbone 5.5) frente a scripts por API desde N2:** el runner no carga conectores y ningún agente recibe credenciales (docs/06 D-19; docs/09 H2); el MCP queda para N0–N1. A reconciliar con el backbone.
2. Claves de `limites.yaml` v1 (`gasto_diario_oferta`, `gasto_test_oferta`, `ofertas_test_simultaneas`) → canónicas (R01).
3. Firma de `aprobacion.json`: HMAC → Ed25519 (docs/06 §4.7).
4. Separador `|` (pregunta 7 de la v1): resuelta por backbone 5.2.
5. Unidad de monto: decimales ISO → offset de Meta (docs/07 M-K).
6. `guardia_meta.py`, `calc_test.py`, `preflight_meta.py`, `activar_campana.py` → `agentes/hooks/pretooluse_*`, `decision.presupuesto`, `meta.preflight`, `meta.activar`.
7. "Validada ≥ 15 compras ≤ 14 d" propia de la v1 → backbone 5.9 (la declara D8). Sin `ig_user_id` (decisión 8).
