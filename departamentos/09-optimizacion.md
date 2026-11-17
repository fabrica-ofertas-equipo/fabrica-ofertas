# D8 — Optimización diaria, lectura de datos y refresco de creativos
> Continuo · Cadencia: lectura cada `optimizacion.lectura_horas` (6 h) durante el test, decisión 1 vez al día, cierre semanal y veredicto · Gate por defecto: A con reglas deterministas (VALIDADA y toda reactivación son H) · Estado de la skill: por forjar · Adaptada al backbone v2.2 (2026-11-06)

> **Precedencia:** backbone > `contratos/` y `empresa/*.yaml` (nombres y valores; `docs/contratos.md` C19) > esta especificación. Todo número es un parámetro `[HIPÓTESIS]` de `parametros.yaml`; todo tope viene de `limites.yaml`; sin tope cargado el motor devuelve BLOQUEADO y no se gasta.

## 1. Misión y posición en el flujo

Convertir el dinero gastado en Meta en **decisiones correctas y aprendizaje reutilizable, por oferta** (= un concepto × un idioma/clúster de mercados, backbone 3.1): leer datos, conciliarlos con Stripe, decidir (matar, mantener, refrescar, proponer escala), emitir el veredicto y devolver aprendizajes. Regla de oro `[NUEVO]`: **el script decide el "cuánto" y el "cuándo"; el LLM explica el "por qué" y redacta pedidos y reportes** (5.6).

- **Recibe de:** D7 (campaña, IDs, `traspaso.json`), F1 (pedidos, tipo de cambio), D3 (`economia.json`, `oferta.json` con `riesgo`), D5, D6, D10 (`senal_pausa.json`), M1 (`mercado.json`), X1, X2. **Entrega a:** D6 (pedidos), D9 (veredicto, propuestas de escala), X2 y D1 (post-mortem, señales de fuente propia, 3.2), M1 (evidencia por `locale`), F2/dueño (KPI, reportes).
- **Fuente de verdad:** ingresos = Stripe (neto de reembolsos e impuestos); gasto = Meta; las compras de Meta son solo señal. Las uniones usan IDs (`oferta_id` + `adid`), nunca nombres de Meta (5.2–5.3). Un D8 por oferta; comparar mercados es de D9/M1 con los KPI de D8 (docs/08 §7). Dinero: enteros en unidad menor + ISO 4217.
- **Código a reutilizar:** `decision.estadistica`, `decision.reglas` (`evaluar_celda`, `ranking_hermanos`, `plan_grupo_control`, `proponer_aumento_presupuesto`, `evaluar_oferta_validada`), `decision.simulacion`. D8 añade `engine.d8` (docs/06 N13): lectura, conciliación, G, embudo, ejecutor.

## 2. Qué dice el video (y qué no dice)

- **[VIDEO] Hace:** semanas 3–4 = "testear con anuncios y generar las primeras ventas"; "si va bien, escalar". **Omite:** inversión diaria, umbrales, evidencia suficiente, fatiga, reconciliación con el cobro, diagnóstico de embudo, post-mortem. **No tomamos:** "si va bien, escalar" sin definición, "3.000 por mes", el día 30 como validación; la edición con IA no es nicho modelo.
- **[CREADORES] Hacen** (inv. 12 y 15): decidir **por gasto acumulado, no por horas** (MB; razonable); cribas **6/8/10-BK** (MB, confianza C, heurística propia: a 6 USD CTR, a 8 ≥ 2 carritos, a 10 ≥ 1 venta; ≈ 0,43–0,83 × `cpa_be`, para front de 12–15 USD); matar al llegar al BE sin vender (SB, C); ganador = CPA ≤ 50–60 % del BE ≈ ROAS > 2 ≈ margen ≥ 40 % (**una regla vista de tres maneras**, B); métricas por etapa (Anexo A.3); humano que sube y baja presupuesto (TT, A).
- **[CREADORES] No tomamos como hechos:** cifras de Argentina/LatAm y EE. UU. en USD sin ajustar por precio ni CPC (para Polonia no hay playbook); 6/8/10 mata ≈ 21,5 % de los ganadores de CPA 0,5 × BE y ≈ 54 % de los de CPA objetivo en una oferta de 27 USD (docs/08 §4.3); +30 % cada 3–4 h, +100 % y surfing (sin respaldo: 04 HC-3, DV-2, HC-26); 5–19 cuentas, WhatsApp, Utmify, "una venta valida", "50 conversiones" como puerta (es diagnóstico, HC-1). **Uso:** 6/8/10, CTR e IC son solo **alertas de priorización** en múltiplos de `cpa_be`, nunca corte; se contrastan con la regla bayesiana en el A/A (§6).

## 3. Variables

### 3.1 Entradas (contrato de entrada)

| variable | tipo | origen | oblig. | ejemplo/valores |
|---|---|---|---|---|
| `oferta_id`, `familia_id`, `fase` (TEST/ESCALA/REFRESCO) | str | `00-brief.yaml`, `campana.json` | sí | `OF-202611-01` |
| `mercado.json`: `locale`, `paises_segmentacion`, `moneda_cobro`, `metodos_pago`, `consumo.desistimiento_dias`, `cpm_esperado`, overlay de riesgo del país | json | M1 | sí | `it-IT`, `EUR` |
| `ids_meta{cid, asid[], adid[]}`, `ad_account_id`, `timezone_name`; `presupuesto_diario`, `evento_optimizacion`, `ventana_atribucion`, `estructura`; `fecha_activacion`, `ultima_edicion_significativa`, `rechazos_7d` | mixto | `ids_meta.json`, `campana.json`, `traspaso.json`, `ads_account_get_activity_logs` | sí | `America/Santiago` · 30 · `Purchase` · `CBO_1AS` |
| `economia.json`: `aov, mc, cpa_be, cpa_obj, roas_be, f` (= `cpa_obj`/`cpa_be`), `escenarios`, `criterios_corte`, `conv_central`, `cpc_esperado` | num | D3 | sí | 16 · 10 · 1,2 · 0,6 |
| `oferta.json`: `macro_nicho`, `riesgo{P,C,E,N,nivel,subnivel,reencuadre_aplicado}`, `angulos[]` (`angulo_seguro`, `claims_a_evitar`), `garantia.dias`, `problema_id`, `nicho_id`, fichas MU/EU (5.11) | json | D3 | sí | `dinero` · `verde` |
| `limites.yaml` (solo lectura): `moneda_limites`, `gasto_diario_global`, `gasto_diario_por_oferta`, `gasto_total_test_por_oferta`, `perdida_max_test_por_oferta`, `aumento_presupuesto_max_pct_por_paso`, `horas_min_entre_aumentos`, `factor_techo_teorico_diario`, `ratio_disputas_pausa`; propuestas nota 25: `cuota_gasto_amarillo_max_pct`, `dias_limpios_para_subir_cuota` | num | dueño | sí | `null` = BLOQUEADO |
| `parametros.yaml`: `testeo.*`, `veredicto.*`, `optimizacion.*`, `salud_operativa.*`, `estadistica.*` | num | X2 + dueño | sí | §3.4 |
| Insights por anuncio y día, estados, errores | num/enum | `ads_get_ad_entities` (`level=ad`, `time_increment="1"`), `ads_get_errors` | sí | Anexo A.1 |
| Pedidos Stripe: `session_id, oferta_id, adid, bruto, impuesto, comision_real, neto, moneda, tipo_cambio_id, metodo, pais, estado, pagado_en, reembolso, disputa, bump_tomado` | tabla | F1 → `empresa/datos/pedidos` (D8 no sondea Stripe) | sí | — |
| Sesiones de landing (`sesiones, lcp_ms, clics_checkout, sesiones_con_adid`, consentimiento); salud (HTTP, `empresa/infra/estado.json`, cuenta, EMQ, veto/sello de X1) | tabla/enum | D5, D0, X1, Meta | sí | cobertura `adid` ≥ 90 % |
| `10-postcompra/senal_pausa.json`, `reembolsos.jsonl` | json | D10 | sí | R08 |
| `matriz.json`, `paquete.json`; `fallas_conocidas`; `ads_insights_anomaly_signal` | json | D6; X2; Meta | opcional (apoyo, nunca disparan acciones) | — |
| `empresa/PAUSA`; calendario de eventos **por `locale`**; tipo de cambio | archivo/lista/num | dueño y M1 `[DUEÑO]`; F1 | PAUSA sí | `2026-11-27` Black Friday |

### 3.2 Variables de decisión

| variable | opciones | criterio de elección | cómo se testea |
|---|---|---|---|
| Unidad de decisión | anuncio · conjunto · campaña · oferta | anuncio para pausar; campaña/oferta para escalar y veredicto; nunca "país" ni "familia" | A/A (§6) |
| Métrica y ventana | CPA neto · ROAS neto; acumulado · 3 d · 7 d | **resuelto (docs/08 §1.2):** CPA neto frente a `cpa_be`/`cpa_obj` (CPA ≤ `f`·`cpa_be` ⇔ ROAS neto ≥ 1/`f`); acumulado para matar y veredicto, 3 d vs 7 d para fatiga y escala, nunca 1 día; compras sin `adid` no se prorratean (G4) | backtest |
| Método estadístico | umbral · bayesiano | se actúa con `P ≥ umbral`. **Manda el código existente:** conversión ~ Beta (prior débil de `conv_central`), clics por gasto ~ Gamma (`decision.reglas`). Compras **válidas** = pagadas, no reembolsadas ni disputadas, fuera de modo test, sin card-testing (F1), 1 por `email_hash`/día | falsos positivos en A/A |
| Refresco | anuncio al conjunto · prueba de creativos por API (2–7, HC-12) · campaña REFRESCO | **nunca** agregar a un conjunto que aprende (HC-3); API si es compatible `[VERIFICAR]` | preflight D7 |
| Moneda y mercado | moneda de decisión (`moneda_limites`) · moneda de cobro por oferta | F1 convierte con `tipo_cambio_id`; el gasto de Meta viene en la moneda de la cuenta; **sin tipo de cambio vigente → BLOQUEADO**. **MER por mercado** = ingreso neto Stripe del `locale` ÷ gasto Meta del `locale` (7 d), control del CPA atribuido | eval 16 |
| Escalón de riesgo | verde · amarillo-A · amarillo-B | `oferta.riesgo`; en amarillos los umbrales de salud bajan un escalón (G6) y no hay aumento automático | evals 15, 18 |
| Ejecutor | MCP (N0–N2) · API con token de sistema (N3+) | MCP solo para pausa pura; desatendido = `engine.d8` `[VERIFICAR]` | prueba de humo semanal |

### 3.3 Salidas (contrato de salida; `ofertas/<id>/08-operacion/`)

| artefacto | ruta · esquema | campos obligatorios | consumidor |
|---|---|---|---|
| Snapshot crudo | `diario/AAAA-MM-DD/metricas.json` (inmutable) | `pull_ts, ventana, fuente, filas[], incompleto` | QA, F2 |
| KPI | `diario/…/kpi_oferta_dia.json` (`kpi`); por anuncio/conjunto `kpis_nivel.json` (esquema pendiente) | gasto, impr, frecuencia, cpm, ctr_enlace, tasa_conexion, tasa_ic, tasa_compra_ic, compras_stripe, ingreso_neto, cpa, roas_neto, `mc_real`, `mer`, intervalos, `n`, madurez, `locale`, moneda | F2, Maker, QA, M1 |
| Conciliación, anomalías | `diario/…/conciliacion.json` (`conciliacion`), `anomalias.json` (pendiente) | `compras{meta,stripe,razon}, cobertura_adid_bp, pendientes_asincronos, estado`; `tipo, entidad, regla, severidad` | QA, D5, X1 |
| Decisiones | `decisiones.jsonl` (`decision`, append-only) | `decision_id` (hash de oferta+objeto+`lectura_ts`: repetir la lectura no duplica), `accion` (MATAR/SEGUIR/ESCALAR/INCONCLUSO/BLOQUEADO), `codigo`, `regla`, `version_reglas`, `hash_parametros`, `evidencia`, `gate`, `ejecutada` | QA, F2 |
| Órdenes de presupuesto | `ordenes_presupuesto.jsonl` (`orden_presupuesto`) | `emisor=D8`, `plan_ref=null`, `accion` ∈ {`mantener`, `aumentar`, `reducir`} (pausar/activar no son órdenes de presupuesto: van por `decision` y `meta.pausar`), `antes/despues`, `delta_pct`, `horas_desde_ultimo_aumento`, `ejecutor`, `idempotency_key` | scripts, F1 |
| Diagnóstico, reporte | `diario/…/diagnostico.md`, `reporte.md` (≤ 1 pantalla) | etapa del embudo, causa, responsable, acción; semáforo, gasto, compras, CPA, ROAS neto, MER, nivel de riesgo, decisiones, pendientes, 1 aprendizaje | dueño, D5/D6/D3 |
| Pedidos creativos | `pedidos_creativos.json` (pendiente) | `pedido_id, motivo, ad_origen, metricas, variable_a_variar` (una), `cantidad` (≤ 5), `plazo_h, mecanismo_lanzamiento, angulo_id` (de `oferta.angulos[]` permitidos al nivel), `aprendizaje{hook_id, hipotesis_id, resultado}`, `no_repetir[]` (incluye claims) | D6 |
| Veredicto | `veredicto_oferta.json` (`veredicto_oferta`) | `estado`, `regla`, `evidencia` (compras netas, `cohorte_madura_hasta`, `cpa_neto`, `mc_real`, `razon_ms`, `reembolso_pct`), `p`, `estabilidad`, `recomendacion`, `gate` | D9, O0, F1, dueño |
| Post-mortem (lo redacta el Maker de cierre de O0 con `orq cerrar`, sobre las salidas de D8, y lo confirma el dueño: `accion:cerrar_oferta`; vive en `08-operacion/` pero D8 solo aporta los insumos; W3-R10) | `postmortem.json` (`postmortem`) | `veredicto_sha256`, `causa_principal`, `causas[nivel_evidencia]`, `parametros_a_calibrar`, `retraso_clic_compra`; ranking de hooks, ángulos y mecanismos con n e intervalo; desvío de D3; `senales_para_d1[]` (objeciones y motivos de reembolso por ángulo, sin datos personales); evidencia por `locale` | X2, D3, D1, M1 |
| Semanal; QA | `semanal/AAAA-Sww.md`; `qa/d8-v<n>.json` | embudo, aprendizajes, decisiones vs resultado, costo IA, gasto amarillo vs `cuota_gasto_amarillo_max_pct`; 6.3 | dueño, F2, O0 |

### 3.4 Parámetros y umbrales (claves canónicas de `parametros.yaml`; todos `[HIPÓTESIS]`)

El prefijo `d8.` de la v1 se retira (equivalencias en Anexo A.2).

| parámetro | valor inicial | nota |
|---|---|---|
| `optimizacion.lectura_horas`, `.hora_decision` | 6, 09:00 zona de la cuenta | datos hasta el cierre de ayer |
| `testeo.ventana_no_decidir_h` | 72 | tras activar o editar; solo rigen G y K1 |
| `testeo.k_corte`, `.n_dec`, `.impr_min_diag`, `.clics_min_diag` | 3, 15, 3.000, 100 | P(0 compras) = e^−k = 5 % si CPA real = `cpa_be`; mínimos para juzgar CTR y etapas |
| `testeo.p_kill`, `.p_fallida`, `.p_escala`, `.p_ganador`, `.p_cierre_tope` | 0,90 · 0,95 · 0,80 · 0,80 · 0,20 | `p_cierre_tope`: P(CPA ≤ `cpa_be`) bajo la cual el tope cierra FALLIDA |
| `estadistica.alfa_descarte`, `.k_min_matar`, `.n_min_escala`, `.prior_conv_fuerza_clics` | 0,05 · 2,0 · 15 · 50 | los lee `decision.reglas`; grupo pendiente (C15) |
| `testeo.tasa_conexion_min`, `.tasa_ic_min_pct`, `.tasa_compra_ic_min_pct` | 0,70 · 3 · 20 | de D3; **sobrescribibles por `locale`**; en un `locale` nuevo, conclusiones "exploratorias" hasta `n_dec` |
| `testeo.cpm_alto_factor`, `.freq_alerta_7d`, `.fatiga_caida_ctr_pct`, `.fatiga_factor_cpa`, `.fatiga_senales_min` | 1,5 · 2,5 · 30 · 1,5 · 2 de 3 | CPM de referencia = D3 o mediana propia 7 d; Meta marca fatiga a ≥ 2 × (HC-30) |
| `testeo.razon_meta_stripe_min/max`, `.cobertura_adid_min_pct`, `.razon_ventana_dias`, `.razon_n_min`, `.k_ciego`, `.chequeos_rojos_g8` | 0,8/1,3 · 90 · 7 (`7d_click`, sin los últimos 2 días, HC-45) · 10 · 2 · 2 | con `n` < mínimo la razón **no dispara** el modo ciego; `k_ciego` topa la pérdida a ciegas |
| `veredicto.compras_min`, `.dias_min/max`, `.madurez_dias_extra`, `.estabilidad_tol_pct`, `.max_dia_pct`, `.reembolso_max_pct` | 15 · 7/14 · 7 · 15 · 50 · 8 | definición única 5.9; `reembolso_max_pct` < `reembolsos_pausa_pct` |
| `salud_operativa.reembolsos_alerta_pct/pausa_pct/n_min`; `.disputas_alerta_pct/muestra_min_pagos/casos_alerta/casos_pausa/ventana_dias` | 8/12/20; 0,3/50/2/3/30 | R06; pausa dura de disputas = `limites.ratio_disputas_pausa`; amarillos: un escalón menos (G6) |
| `optimizacion.max_pausas_dia_conjunto`, `.anuncios_sin_entrega_pct`, `.max_pedidos_abiertos`, `.dias_entre_pedidos`, `.cantidad_max_pedido` | 2 · 5 · 1 · 5 · 5 | nunca dejar la campaña a cero sola |
| Aumento de presupuesto | **no es parámetro:** `limites.aumento_presupuesto_max_pct_por_paso` y `.horas_min_entre_aumentos` (referencia 20 % / ≥ 72 h; hoy `null` = no se aumenta), 1,75 ×, ≤ 4 cambios/h, ≥ 30 s | plataforma (HC-26, DV-2) o dueño (R02) |

### 3.5 KPIs del paso

- **Propios:** recómputo QA ≤ 0,5 %; reproducibilidad 100 %; evidencia citada en 100 % de decisiones; A/A ≤ 5 % de corridas con falso kill; pausas revertidas por el dueño ≤ 5 %; gasto de un anuncio sin compra ≤ 1,2 × `k_corte`·`cpa_be`; anomalía→alerta ≤ 6 h; razón en rango ≥ 90 % de los días; `senal_pausa` consumida en el ciclo siguiente 100 %; costo IA por día.
- **Diferidos:** coincidencia veredicto–desenlace; pedido→anuncio ≤ 5 d; % de refrescos que baten al fatigado; desvío vs D3 **por `locale`**; % de problemas del banco (D1) que terminan en VALIDADA (X2).

## 4. Flujo paso a paso (SOP)

| # | Actor | Acción | Herramienta | Se guarda |
|---|---|---|---|---|
| 1 | Script | Si existe `empresa/PAUSA`: pausar y terminar (G1). Si no: pull de Meta (nivel ad, diario, 1d y 7d clic), estados, `senal_pausa.json` y pedidos de F1, con reintentos (incompleto → G7); normaliza moneda (`tipo_cambio_id`) y día de la cuenta (`engine.comun.dia_de_cuenta`; madurez en UTC); compras de Meta inmaduras 48 h (HC-45) | `ads_get_ad_entities`, `engine.d8 kpis` | `metricas.json`, `kpi_oferta_dia.json` |
| 2 | Script | Conciliación Meta↔Stripe, cobertura de `adid`, pendientes asíncronos (BLIK, Satispay, Klarna, Pay by Bank no cuentan hasta pagados), MER, anomalías; motor G → K → FT → E → M, árbol de embudo | `engine.d8 conciliar/reglas/embudo`, `decision.reglas` | `conciliacion.json`, `anomalias.json`, `decisiones.jsonl` (propuestas) |
| 3 | Maker | Lee solo salidas del motor y `matriz.json`; redacta diagnóstico, pedidos a D6 y reporte (cifras por plantilla) | skill | `diagnostico.md`, `pedidos_creativos.json`, `reporte.md` |
| 4 | QA | L1 completo; L2 sobre acciones, pedidos y veredictos; sello por hash | §6 | `qa/d8-v<n>.json` |
| 5 | Script / Humano | Ejecuta solo acciones permitidas al nivel (§7), 30 s entre ediciones; relee y verifica. N0–N2: la sesión principal (no el Maker) llama `ads_update_entity` con `{"status":"PAUSED"}` y un hook `PreToolUse` rechaza cualquier otro campo. N3+: `engine.d8 ejecutar` con token de sistema. Auditoría: `ads_account_get_activity_logs` vs `decisiones.jsonl` (huérfana → alerta) | MCP / API | `verificacion_post` |
| 6 | Maker / Humano | Con veredicto: `postmortem.json` a X2/D1/M1; el dueño resuelve H; viernes: semanal | skill | `veredicto_oferta.json`, `semanal/` |

**Motor de reglas** (manda la primera que dispara; `decisiones.jsonl` guarda `regla` y el `codigo` de `decision.reglas`):

- **G (guardarraíles; ignoran la ventana de no decidir):**
  - **G1** `PAUSA` → pausar. **G2** gasto del día > `factor_techo_teorico_diario` × máx. presupuesto vigente, semanal > 7 × presupuesto (HC-26), de la oferta > `gasto_diario_por_oferta`, `gasto_total_test_por_oferta` o `perdida_max_test_por_oferta`, o de la cuenta > `gasto_diario_global` → pausar. Mide **gasto efectivo** = leído + 1,75 × diario × horas sin lectura / 24 (docs/06 B05).
  - **G3** cuenta ≠ saludable, rechazo o "link failure" → congelar ediciones, alertar a X1, pausar el anuncio; **nunca reenviar el mismo hash ni editar en bucle**. Rechazo de producto o contenido → proponer congelar la hoja; de pieza revertido → solo el ángulo; `rechazos_7d` ≥ `compliance.rechazos_congelar` → congelar lanzamientos (O0). **G3b** X1 revoca el sello o sube el riesgo (p. ej. verde→rojo) → pausar la oferta; reactivar es H.
  - **G4 modo ciego:** razón Meta/Stripe (ventana móvil, `n ≥ razon_n_min`) fuera de rango 2 días seguidos, cobertura de `adid` < mínimo, o compras Stripe sin `Purchase` de servidor en 24 h → solo G; alerta a D5/D0. Con banner de consentimiento (UE/UK) la razón baja sin error: se calibra por `locale` y manda la **cobertura de `adid` medida del lado Stripe** `[VERIFICAR]`. **G4b** pausa si gasto ≥ `k_ciego`·`k_corte`·`cpa_be` sin una compra Stripe de la oferta.
  - **G5** tope de test o `dias_max` agotados → pausar, cerrar campaña y emitir veredicto; la lectura sigue sin gasto hasta la madurez.
  - **G6 salud operativa:** `senal_pausa.emitida` con `accion_solicitada=pausar` → pausar la oferta y anotar `consumida_por` = `decision_id`. D8 recalcula: con ≥ `disputas_muestra_min_pagos` pagos, (disputas+EFW)/pagos ≥ `ratio_disputas_pausa`; o ≥ `disputas_casos_pausa` casos; o reembolsos maduros (`n ≥ reembolsos_n_min`) > `reembolsos_pausa_pct`; con menos muestra, alerta a F1. **Escalón de riesgo:** AMARILLO-A usa los valores de la columna anterior (pausa a 0,20 % / 2 casos / 8 %; alerta a 0,15 % / 1 caso / 6 % `[HIPÓTESIS]`, nota 25 §9); AMARILLO-B además pausa el ángulo al primer caso. Pausar el gasto **no detiene** el contador: las disputas llegan a los 30–120 días.
  - **G7** pull incompleto, moneda sin tipo de cambio o `empresa/infra/estado.json` ≠ VERDE o > 6 h → no decidir rendimiento (BLOQUEADO). **G8** landing HTTP ≠ 200 o healthcheck de D5 en rojo `chequeos_rojos_g8` lecturas seguidas → pausar campaña (reactivar es H; pausar ≥ 7 días reinicia el aprendizaje).
- **K (matar anuncio; con tracking sano y fuera de ventana):** **K1** gasto (hasta ayer) ≥ `k_corte`·`cpa_be` con 0 compras Stripe del anuncio. **K2** ≥ 2 hermanos con impresiones ≥ `impr_min_diag`, el anuncio también, 0 compras y `P(CTR de enlace < 0,7·mediana de hermanos) ≥ p_kill` (0,95 si hay > 3 anuncios); con ≥ 1 compra no se mata por K2. **K3** ≥ 3 compras, `evaluar_celda` = MATAR (`alfa_descarte`) y existe un hermano mejor. Nunca se pausa el último anuncio activo ni más de `max_pausas_dia_conjunto`; si todos cumplen K se propone veredicto. Un anuncio con < `anuncios_sin_entrega_pct` del gasto tras 72 h queda **"sin veredicto"**: no se mata. Las **alertas 6/8/10** `[CREADORES, C]` (0,45 / 0,60 / 0,80 × `cpa_be` sin CTR, carritos o ventas) solo priorizan pedidos a D6. **Control de lo apagado** (docs/08 §4.5): reapertura en REFRESCO (propuesta H) para medir falsos descartes.
- **FT (fatiga → refrescar):** ≥ `fatiga_senales_min` de 3 en 2 lecturas seguidas: frecuencia 7 d ≥ umbral; CTR de enlace 3 d ≤ (1 − caída)·CTR inicial; CPA 3 d ≥ factor·CPA inicial (con ≥ 3 compras; si no, costo por IC) o estado "creative limited/fatigue" (HC-30). CTR y CPA se exigen con `P ≥ 0,8`; la señal de CPA no cuenta si el árbol marca falla en etapa 0, 2 o 4. Acción: pedido a D6; **no** se toca el anuncio vivo; el viejo se pausa solo cuando el reemplazo entrega y su CPA 7 d ≥ 2·`cpa_obj`.
- **E (escalar = propuesta; solo con VALIDADA confirmada por H):** compras ≥ `n_dec`; CPA 7 d ≤ `f`·`cpa_be_real`; CPA 3 d ≤ 1,15 × eso; `mc_real` − CPA > 0; frecuencia < 2; razón y cobertura sanas; sin FT; `P(CPA ≤ cpa_be) ≥ p_escala`; confirmada en 2 lecturas; **riesgo verde** (amarillo: propuesta a H solo con `dias_limpios_para_subir_cuota` y sin rechazos abiertos). `proponer_aumento_presupuesto` recorta a `aumento_presupuesto_max_pct_por_paso`, `horas_min_entre_aumentos` y 1,75 ×; saltos mayores = campaña `ESCALA` (D9). **Un solo escritor** (R04): con plan vigente en `09-escalado/plan.json` D8 no sube; sin plan, emite la `orden_presupuesto` (N3+).
- **M (mantener):** por defecto; `MANTENER_SIN_EVIDENCIA` si `n` < mínimos. Con < 20 compras totales no se comparan CPA entre anuncios: el ranking usa CTR, tasa de IC y gasto-a-primera-compra con intervalos, rotulado "exploratorio". La ventana de no decidir se reinicia con ediciones significativas (HC-3), no con pausar un anuncio.

**Árbol de diagnóstico del embudo** (primera etapa que falla con `P ≥ 0,9` contra los escenarios de D3 y los umbrales del `locale`; pocos datos: "no concluyente"; creadores en Anexo A.3):

| etapa | síntoma | causa probable | responsable |
|---|---|---|---|
| 0 Entrega | gasto < 50 % del presupuesto, aprendizaje limitado | puja, audiencia, límite diario (HC-29), rechazo | D7; no tocar creativos |
| 1 CTR de enlace bajo | pocos clics con impresiones suficientes | hook/ángulo (hook rate y retención **relativos** a hermanos, SB, C) | D6, variable = hook |
| 2 `tasa_conexion` baja con buen CTR | clics sin vistas de landing | velocidad (LCP), píxel, UTM, **banner de consentimiento que bloquea el píxel**; si `sesiones_con_adid`/clics es normal, es medición | D5 |
| 3 `tasa_ic` baja | no inician pago | promesa ≠ landing, precio, confianza | D5/D3 |
| 4 compra/IC baja | abandono en checkout | **método local no mostrado por la moneda de presentación** (BLIK exige PLN), 3DS, impuesto sorpresa; los pendientes asíncronos no son abandono | D5 (mix por `metodo`/`pais`) |
| 5 Embudo normal, CPA alto | CPM > `cpm_alto_factor` | subasta, país, Q4 | D7: ampliar; esperar o cerrar |
| 6 Decaimiento | compras/IC cae semana a semana (30→15 %) con creativos frescos | oferta comoditizada o clonada `[CREADORES, SB, C]` | D3/M1: otra oferta o mercado |

**Veredictos** (`evaluar_oferta_validada`; compras Stripe válidas; `mc_real` con comisiones, reembolsos y bump reales; `cpa_be_real` reemplaza al de D3 con ≥ 10 compras; `cpa_obj_real = f·cpa_be_real`). **Madurez** = `max(garantia.dias, consumo.desistimiento_dias)` + `veredicto.madurez_dias_extra`: la última compra madura entre el día 28 y el 35 (docs/08 §8); hasta entonces el veredicto es *provisional*.

- **VALIDADA** (definición única, 5.9): compras netas de cohorte madura ≥ `compras_min` en ≤ `dias_max` días activos; CPA neto ≤ `cpa_obj_real`; percentil 80 del CPA posterior ≤ `cpa_be_real`; CPA de la 2.ª mitad ≤ (1+`estabilidad_tol_pct`)·`cpa_obj_real`; ningún día > `max_dia_pct`; compras en ≥ 3 días; reembolsos ≤ `reembolso_max_pct`; razón sana; sin disputas abiertas (o ratio < `ratio_disputas_pausa`); **segundo corte confirmatorio**. Pasa a D9 con H (amarillo: con checklist de salud operativa y sin avisos de X1).
- **PROMETEDORA:** cumple todo salvo `cpa_obj` < CPA ≤ `cpa_be` con `P ≥ p_escala`; sigue optimizando creativos sin escalar. El *PROVISIONAL* de docs/08 = PROMETEDORA con `cohorte_madura_hasta` anterior al corte. Con `P` menor: INCONCLUSA ("justa y ruidosa").
- **FALLIDA:** `P(CPA ≤ cpa_be) ≤ 1 − p_fallida` con gasto ≥ 5·`cpa_be`, tracking sano, ≥ 72 h desde la última edición significativa y **sin falla técnica abierta** (etapa 0, 2 o 4 en rojo ⇒ INCONCLUSA con responsable D5/D7). Vía de tope: gasto = `gasto_total_test_por_oferta` y `P < p_cierre_tope`. Pausa automática; reabrir es H.
- **INCONCLUSA:** plazo o tope vencidos sin cumplir lo anterior. Decide el dueño: extender una vez, rediseñar o cerrar; se etiqueta la causa.

## 5. Agente Maker

- **Rol:** analista de performance: redacta diagnóstico, pedidos a D6, reportes y post-mortem sobre las salidas del motor. Alcance: `08-operacion/`.
- **No hace:** calcular KPIs a mano ni "corregir" una decisión del motor (puede **objetar** con motivo → gate H); activar o reactivar; crear anuncios o campañas; cambiar objetivo, evento, puja, audiencia, URL o creativos; subir presupuesto sobre el paso o el techo; tocar `limites.yaml`, `parametros.yaml` ni `contratos/` (solo propone); borrar o archivar; afirmar causas con evidencia baja; embellecer resultados; **pedir a D6 un ángulo, hook o claim fuera de `oferta.angulos[]` y del nivel de riesgo, ni copiar el texto de un ganador** (transmite estructura y variable, no claims de salud, ingresos o resultado).
- **Herramientas (mínimo privilegio):** lectura de `08-operacion/`, `10-postcompra/`, `economia.json`, `oferta.json`, `mercado.json`, `06-creativos/`, `empresa/datos/`, `parametros.yaml`; Meta solo lectura (`ads_get_ad_entities`, `ads_get_field_context`, `ads_get_errors`, `ads_account_get_activity_logs`, `ads_insights_*`, `ads_get_dataset_*`). **Sin escritura en Meta:** las acciones salen por `engine.d8 ejecutar` (N3+) o por la sesión principal tras aprobación (N0–N2), con lista blanca. Con el modo borrador del conector solo la pausa pura actúa sobre lo vivo; el presupuesto va por API con token de sistema `[VERIFICAR]`. Los hooks no se cargan con `claude -p --bare`: el ejecutor no lo usa o la lista blanca vive en el script (inv. 01 §4.1). Desde N3 no hay MCP en el runner (docs/09 §8).
- **Contexto:** salidas del motor, `economia.json`, `oferta.json`, `matriz.json`, fallas conocidas; sin tokens ni datos personales (solo `email_hash`).

## 6. Agente QA

**Independencia:** contexto limpio; recibe `metricas.json` crudo, `reglas.yaml` versionado, parámetros con hash, `economia.json`, `campana.json`, artefactos del día y fallas conocidas de X2; no el razonamiento del Maker; usa su **propio** recómputo. **Sello por hash:** cita `artefacto_sha256` de `decisiones.jsonl`/`veredicto_oferta.json`; actuar sobre un artefacto sin sello vigente es BLOQUEANTE. **QA-A** (previo al gasto, no cuenta como ronda): antes del primer ciclo `--live` verifica lista blanca, `hash_parametros`, IDs de Meta y tope. Cadencia: L1 en cada corrida; L2 sobre acciones, pedidos, veredictos y post-mortem; L3 al cambiar reglas y cada mes. Salida: hallazgos estructurados (`check_id`, `patron_clave`, `severidad`, `etapa`, `skill_version`) y `aprendizajes_para_skill[]` (6.3).

**L1 deterministas (BLOQUEANTE salvo nota):**
1. Esquemas válidos (`decision`, `orden_presupuesto`, `veredicto_oferta`, `postmortem`, `kpi`, `conciliacion`).
2. Recómputo independiente desde el crudo ≤ 0,5 % de diferencia (CTR, CPA, ROAS neto, MER); CPA y ROAS salen de Stripe, en una sola moneda con `tipo_cambio_id`.
3. Reproducibilidad: mismo dato y `hash_parametros` → mismas decisiones, cada una con `regla` y evidencia que cumple la condición; `hash_parametros` y `version_reglas` = los aprobados (un diff sin aprobación es BLOQUEANTE).
4. Conciliación: suma de pedidos del día = KPI; día de la cuenta y cortes UTC coherentes; razón y cobertura calculadas. Ninguna decisión de rendimiento dentro de la ventana de no decidir, con `n` bajo mínimos o datos inmaduros (salvo G y K1).
5. Acciones dentro de la lista blanca del nivel; presupuesto ≤ paso, ≥ horas mínimas, ≤ techo y 1,75 ×; 0 ediciones significativas durante el aprendizaje; `activity_log` ≡ `decisiones.jsonl`; estado posterior verificado.
6. Pedidos a D6: contrato de D6, `ad_origen` existente, una sola variable, ≤ cantidad máxima, `angulo_id` permitido al nivel, sin claims copiados.
7. Veredicto recomputado con `evaluar_oferta_validada` coincide; madurez respetada. Cifras del reporte = KPI (comparación de cadenas).
8. `registro.jsonl` y `costos.jsonl` completos; frescura del pull ≤ 6 h (MAYOR).
9. Disparos de modo ciego y G6 verificados contra su mínimo de `n` (falso bloqueo = MAYOR); `senal_pausa` emitida ⇒ pausa con `consumida_por`; umbrales de salud operativa con el escalón del nivel de riesgo.

**L2 rúbrica (0–5 con evidencia citada; sin evidencia no cuenta):**

| ítem | 1 | 3 | 5 |
|---|---|---|---|
| R1 Embudo | por intuición o etapa errónea | etapa correcta sin comparar con D3 | etapa correcta contra escenarios y umbrales del `locale`, responsable y acción única |
| R2 Incertidumbre | afirma con 2 compras | "poca muestra" sin cuantificar | intervalos y `P`; separa "no sé" de "malo" |
| R3 Pedido a D6 | "haz más como este" | variable sin hipótesis | variable única, hipótesis, evidencia, `no_repetir`, ángulo permitido |
| R4 Reporte | cifras sueltas | completo pero largo | 1 pantalla, semáforo, qué decidir hoy, costo de esperar |
| R5 Datos y costo de errar | ignora la razón; solo mira el ahorro | las menciona | explica causas (consentimiento, asíncronos, FX) y pondera pausar un ganador vs seguir gastando |
| R6 Post-mortem | cuenta lo ocurrido | causa plausible | separa correlación de causa, `nivel_evidencia`, recalibra D3, útil para X2/D1/M1 |
| R7 Salud de cuentas | ignora disputas y rechazos | los reporta | aplica el escalón de riesgo y anticipa el rezago de disputas |

**L3 simulaciones:** (a) **A/A secuencial**: 5 anuncios idénticos, 5.000 corridas de 14 días con lectura diaria (`decision.simulacion`), CPA verdadero = `cpa_obj`: ≤ 5 % de corridas con alguna pausa; segunda corrida con CPA = `cpa_be` (se reporta K1, ≈ 5 %); tercera con la **regla ingenua 6/8/10** como línea base (`falso_descarte_regla_ingenua`). (b) Ganador y perdedor sembrados: mata al perdedor en ≤ `k_corte`·`cpa_be` sin matar al ganador. (c) Dueño apurado: en 60 s dice estado, qué hacer y cuánto perdió. (d) Auditor: reconstruye el P&L desde Stripe en dos monedas. (e) Sin `adid` en el 40 % de pedidos → modo ciego. (f) Revisor de políticas: marca todo claim de salud, ingresos o resultado.

**Veredictos y loop:** PASS exige 0 BLOQUEANTES, 0 MAYORES y media L2 ≥ 3,8; máx. 2 rondas, luego ESCALAR; siempre ≥ 3 hallazgos o justificación con evidencia. QA previo obligatorio para pausar el anuncio de mayor gasto y para veredictos; posterior en el resto desde N3. Aplica por su cuenta solo mejoras que no cambian reglas ni dinero (misma semana, eventos del `locale`, sesgo por país o método, card-testing para F1).

**Defectos sembrados (≥ 90 % de bloqueantes detectados; 0 falsos bloqueos en dorados):** 1 pausa con 1 día de datos y gasto < `k_corte`·`cpa_be` (BLOQ.); 2 CPA con compras de Meta (BLOQ.); 3 ROAS con ingreso bruto: 3,2 en vez de 2,1 neto (MAYOR); 4 aumento +50 % sin esperar las horas mínimas (BLOQ.); 5 razón 0,55 con 25 compras ignorada (BLOQ.); 6 acción en Meta sin registro (BLOQ.); 7 "creativo malo" con CTR normal y `tasa_conexion` 45 % (MAYOR); 8 VALIDADA con 6 compras, 80 % en un día (BLOQ.); 9 pedido que repite el claim de ingresos, ahorro o salud del ganador (BLOQ., veto X1); 10 anuncios agregados a un conjunto que aprende (BLOQ.); 11 FALLIDA con `tasa_conexion` 45 % (BLOQ.); 12 modo ciego con razón 0,5 sobre 3 compras (MAYOR); 13 reactivación automática (BLOQ.); 14 CPA con compras de test, reembolsadas o duplicadas (MAYOR); 15 `senal_pausa` emitida sin pausa (BLOQ.); 16 umbral de verde en una oferta amarilla (MAYOR); 17 aumento automático a una oferta amarilla (BLOQ.); 18 CPA sumando EUR y PLN sin `tipo_cambio_id` (BLOQ.); 19 sello de X1 revocado y la oferta sigue gastando (BLOQ.); 20 pedido con ángulo fuera de `oferta.angulos[]` (BLOQ.); 21 "oferta mala" por conversión baja en un `locale` sin calibrar (MAYOR).

## 7. Gates y autonomía

| Nivel | Qué hace D8 | Gate | Métrica para ascender |
|---|---|---|---|
| N0 | El dueño, con el Maker en la pestaña Code, lee datos y ejecuta todo | H | skill v1 congelada; reglas en script |
| N1 | Maker + motor proponen; el dueño aplica cada acción en Meta | H | coincidencia motor–dueño ≥ 90 % en ≥ 30 decisiones; 0 errores de KPI |
| N2 | + QA. Ejecución automática solo de **pausas** (G, K; por la sesión Code o `meta.pausar`) con QA PASS previo (G1–G8 frenan primero y se auditan después); pedidos a D6 y escalas son propuestas | A en pausas · H en el resto | 14 días sin pausa revertida por error; auditoría 100 % reconciliada; QA ≥ 90 % de sembrados |
| N3 | + aumento ≤ paso dentro del techo **solo con VALIDADA confirmada (H), sin plan de D9 y riesgo verde**; pedidos a D6 automáticos; QA posterior; FALLIDA pausa sola | A con topes · S por excepción | 30 días y 2 ofertas; 0 incidentes de gasto; razón sana ≥ 90 % de días; ≥ 90 % de decisiones PASS |
| N4 | Ciclo desatendido con scripts y token de sistema; revisión semanal | A/S | 8 semanas; ≥ 90 % de veredictos confirmados; 0 acciones fuera de lista |

El nivel es **por etapa** (`autonomia.yaml`), con descenso automático ante violaciones; D8 pausa desde N2 y aumenta desde N3 (`gates.json`); **MCP hasta N2, scripts de mínimo privilegio desde N3** (5.5). En el primer test de un `locale` nuevo, G y K1 corren igual y el resto es "exploratorio" hasta `n_dec` compras. **Guardarraíles deterministas (no del LLM):** `PAUSA`; lista blanca; topes de `limites.yaml`; 1,75 ×; ≤ 4 cambios/h y ≥ 30 s; **nunca activar ni reactivar** (ni tras una pausa errónea: H); nunca borrar; modo ciego; `limite_gasto_cuenta_meta` como segundo candado; latido (36 h sin corrida → alerta). **Dinero:** toda subida sobre el tope pasa por D9/H. **Cumplimiento:** los creativos nuevos pasan por D6 + X1 + D7 (H para activar); el veto de X1 no se relaja.

## 8. Riesgos y modos de falla

| riesgo | señal temprana | mitigación | responsable |
|---|---|---|---|
| Decidir con ruido (matar un ganador); espionaje diario | pausas con `n` bajo o revertidas; pausas en A/A | significancia, A/A con lecturas diarias, ventana de no decidir, 6/8/10 solo como alerta | Script / QA |
| Tracking roto o consentimiento → decisiones ciegas | razón fuera de rango, cobertura < 90 % | modo ciego G4; cobertura del lado Stripe; rango por `locale` | Script / D5 |
| Reinicio del aprendizaje; edición humana en la UI; hook ausente en `--bare` | cambios en un conjunto que aprende; acción huérfana o fuera de lista | lista blanca en `engine.d8`; refresco por API o REFRESCO; auditoría diaria; prueba de humo | Script / D0 |
| Fatiga mal diagnosticada; FALLIDA con embudo roto | frecuencia baja con CPA alto; `tasa_conexion` baja al cerrar | árbol de embudo antes de pedir creativos; FALLIDA exige 0 fallas técnicas | Maker / QA |
| Reporte embellecido; economía de D3 errada | cifras ≠ KPI; `mc_real` < supuesto | plantilla con inserción; `cpa_be_real`, devolver a D3 | QA / D3 |
| Dos escritores de presupuesto; fraude o card-testing | ediciones cruzadas; ráfagas, EFW | `orden_presupuesto` único (R04); excluir del CPA y alertar a F1 | O0 / F1 |
| Se hereda un claim prohibido (salud, ingresos) | hook con promesa | pedidos transmiten estructura, no texto; lint X1 | QA / X1 |
| Una cuenta de Meta y una de Stripe sostienen todo; disputas a 30–120 días | `senal_pausa` amarilla, rechazos, avisos | escalón de riesgo, G6 y G3; reportar la cuota amarilla; D8 no oculta alertas | Script / X1 / F1 |
| Mezcla de monedas o FX ausente; umbrales de otro mercado en un `locale` nuevo | CPA o MER inconsistentes; "oferta mala" en el primer test | BLOQUEADO sin `tipo_cambio_id`; conclusiones exploratorias hasta `n_dec`; calibrar por `locale` | F1 / Maker / M1 |

## 9. Mejoras respecto del video

`[NUEVO]` por impacto: (1) motor determinista con significancia que decide con **Stripe** y margen real; (2) modo ciego tolerante al consentimiento; (3) árbol de diagnóstico por etapa y por `locale`; (4) veredictos formales con stop-loss y madurez; (5) refresco sin tocar lo que aprende y pedidos a D6 con ángulo permitido por nivel de riesgo; (6) post-mortem que recalibra D3 y alimenta D1/M1/X2; (7) QA con A/A y línea base 6/8/10; (8) respuesta a la pregunta sin contestar del video: el presupuesto sale de `economia.json` y D8 informa el gasto restante; (9) **escalón de salud operativa por nivel de riesgo** y consumo de `senal_pausa`; (10) MER por mercado.

## 10. Forja de la skill (pestaña Code)

### 10.1 Prompt de arranque (copiar y pegar en una sesión nueva de Claude Code abierta en `<carpeta del proyecto>`)

```
ROL: Eres el Maker de D8 (Optimización diaria y refresco de creativos) de un sistema que lanza ofertas de productos digitales de bajo ticket y las testea con anuncios en Meta hacia una landing propia con checkout de Stripe. Una oferta = un concepto × un idioma/clúster de mercados (locale BCP-47: it-IT, pl-PL, en-GB…), dentro de salud, relaciones o dinero. El dueño es hispanohablante, con criterio de negocio, no técnico. Eres analista cuantitativo: el código decide el cuánto y el cuándo, tú explicas el porqué.

LEE PRIMERO (no cambies nada, anota cambios propuestos): docs/_backbone.md (v2.2, completo) · departamentos/09-optimizacion.md · docs/contratos.md y los contratos/*.schema.json de decision, orden_presupuesto, veredicto_oferta, senal_pausa, postmortem, kpi, conciliacion, mercado, economia · docs/08-protocolo-estadistico-del-testeo.md y decision/*.py (reutilízalos) · docs/convenciones-de-codigo.md · empresa/*.yaml · ofertas/_ejemplo/ · docs/_investigacion/04, 12 (creadores = hipótesis A/B/C), 03 y 25.

ENTRADAS: las rutas de §3.1 (ofertas/<oferta_id>/ y empresa/); sin dato real usa ofertas/_ejemplo. Entorno: bash scripts/bootstrap.sh; pruebas: python3 -m unittest discover -s tests/decision -t .

PREGUNTA PRIMERO (bloqueantes, en una lista): oferta_id y locale; moneda de la cuenta de Meta y de cobro; zona horaria y hora de decisión; techos diario y de test (hoy null = BLOQUEADO); acciones automáticas desde N2; programador; nivel de riesgo; calendario del locale. No inventes valores.

TAREA: v1 en ofertas/<oferta_id>/08-operacion/ y engine/d8 (python -m engine.d8 kpis|conciliar|reglas|embudo|veredicto|ejecutar; dry-run por defecto): (1) reglas G, K, FT, E, M sobre decision.reglas, con parámetros de parametros.yaml y topes de limites.yaml, y ejecutor con lista blanca; (2) una jornada de ejemplo con los artefactos de §3.3 y sus esquemas; (3) los evals de §10.5 en ≥ 2 locales y 3 niveles de riesgo, el simulador A/A (14 días, 5.000 corridas) y la línea base 6/8/10; (4) autorrevisión contra la rúbrica de §6.

ACEPTACIÓN: esquemas válidos; el motor reproduce las decisiones de los casos; A/A ≤ 5 % de corridas con pausa de un anuncio rentable; cada decisión cita regla y evidencia; nunca compras de Meta ni monedas mezcladas sin tipo de cambio; modo ciego con tracking roto y no con 3 compras de razón 0,5; FALLIDA nunca con falla técnica abierta; senal_pausa emitida ⇒ pausa; ningún aumento automático en amarillo ni pedido con claim de salud o ingresos; ninguna acción fuera de la lista blanca; reporte ≤ 1 pantalla; español con tildes.

REGLAS: solo lecturas de Meta (ads_get_*, ads_insights_*); nunca ads_update_entity ni ads_activate_entity; no inventes datos ni URLs; marca [SUPUESTO], [HIPÓTESIS], [VERIFICAR]; NO ejecutes acciones con costo o efecto externo (crear, editar, pausar, activar, gastar) sin mi permiso: todo en simulación; nunca actives ni reactives; no modifiques contratos/**, limites.yaml ni parametros.yaml (propón cambios); si algo choca con un contrato o el código, manda el contrato y lo registras como conflicto. Cierra con supuestos, preguntas abiertas y cambios propuestos.
```

### 10.2 Cómo pulir

Tiempo: 3–4 sesiones de 90 min y 7 días en **modo sombra** con una campaña real (el motor propone, tú actúas). Mira: ¿coincide el motor con lo que harías tú (qué pausaste tú que el motor mantuvo, y al revés)?, ¿entiendes el reporte en 60 s?, ¿qué hago con una "prometedora"? Ajusta con datos, no con corazonadas.

### 10.3 Estructura de la skill a generar

```
.claude/skills/d8-optimizacion/
├── SKILL.md   rubric.md   references/ (reglas, embudo, veredictos, politica-ediciones, referencias-creadores, multimoneda, riesgo-y-salud-operativa, parametros-equivalencias)
└── templates/ (reporte, pedido.json, postmortem.json)   scripts/ (envoltorios de engine.d8, qa_recomputo.py)   evals/ (casos + generador A/A)
```
Subagentes: `.claude/agents/d8-maker.md`, `d8-qa.md`.

### 10.4 Definición de listo (DoD)

(a) Recómputo QA ≤ 0,5 % en 10 jornadas y reproducibilidad 100 %; (b) A/A: ≤ 5 % de corridas con pausa de un anuncio rentable en 5.000 simulaciones; (c) evals en ≥ 2 `locale` y 3 niveles; (d) QA detecta ≥ 90 % de sembrados con 0 falsos bloqueos en dorados; (e) 7 días en modo sombra con coincidencia ≥ 90 %; (f) reporte validado por el dueño y parámetros con fuente; (g) prueba de humo desatendida: pausa de un anuncio de prueba con token de sistema, verificada en `activity_log`; (h) una `senal_pausa` sintética de D10 produce pausa y `consumida_por`.

### 10.5 Evals mínimos (nichos y locales distintos para evitar sobreajuste)

1. Ganador claro (guía de CV y entrevista para volver al trabajo tras una pausa, `en-GB`): escala tras 2 lecturas y horas mínimas; propuesta H.
2. Perdedor por CTR (tarjetas de conversación para parejas, `it-IT`): K2 + pedido a D6 (variable = hook).
3. Buen CTR, `tasa_conexion` 40 % (plan semanal de comidas, `it-IT`, con banner de consentimiento): etapa 2 → D5; no culpa al creativo.
4. Vistas altas, IC 1 % (hoja de costeo y precio mínimo para quien vende manualidades, `pl-PL`): etapa 3 → D5/D3.
5. Compra/IC baja con precio en EUR y BLIK sin aparecer (`pl-PL`): etapa 4 → D5; los pendientes asíncronos no son abandono.
6. CPA alto, embudo normal, CPM × 2 en Black Friday: etapa 5; no matar creativos.
7. Ruido puro A/A: cero acciones. 8. Tracking roto (razón 0,5, cobertura 55 %): modo ciego. 9. Fatiga (frecuencia 3, CTR −35 %, CPA × 1,6): FT → pedido; no toca el anuncio vivo. 10. Gasto del día 2,1 × presupuesto: G2 pausa. 11. Orden "agrega 3 anuncios al conjunto": la rechaza y propone prueba de creativos o REFRESCO. 12. 9 compras al día 14: INCONCLUSA; 15 sin madurez: PROMETEDORA provisional. 13. Razón 0,5 con 3 compras: sin modo ciego.
14. 0 compras tras 5·`cpa_be` y `tasa_conexion` 40 % (calendario de cuotas y préstamos propios, `it-IT`): INCONCLUSA a D5, no FALLIDA.
15. `senal_pausa` roja (reembolsos 13 %) en oferta amarillo-A: pausa y `consumida_por`; con 8 pagos y 1 disputa: alerta a F1, no pausa.
16. Dos ofertas de una familia (`it-IT` EUR, `pl-PL` PLN): KPI y MER en moneda común con `tipo_cambio_id`; sin él → BLOQUEADO.
17. Refresco de un ganador que decía "ahorra X en N días": el pedido transmite estructura sin el claim.
18. X1 sube el riesgo de verde a rojo con la campaña activa: G3b pausa; reactivar exige H.

## 11. Preguntas abiertas / decisiones del dueño

**Resuelto:** validada (5.9); escritor único (R04); horas entre aumentos (R02); disputas y reembolsos (R06); `senal_pausa` (R08); métrica (docs/08 §1.2); duración y madurez (docs/06 N13); INCONCLUSA (docs/08 §6.3); programador (Railway cron o GitHub Actions, N3+).

1. `[DUEÑO]` **Pérdida máxima por oferta y por día:** diferida (2026-11-06); con `perdida_max_test_por_oferta` en `null` nada gasta. Política ante FALLIDA propuesta: pausa automática, post-mortem, reabrir solo con H.
2. `[DUEÑO]` Confirmar `f` = 0,6 y el margen mínimo para VALIDADA; fijar `aumento_presupuesto_max_pct_por_paso` y `horas_min_entre_aumentos` (referencia 20 % / 72 h) y si N3 aumenta automáticamente (propuesta: solo en verde).
3. `[DUEÑO]` Umbrales de salud operativa: `parametros.yaml` (alerta de disputas 0,3 %) frente a la nota 25 §9 (0,20 / 0,35 / 0,50 %); aprobar el escalón menos para amarillos.
4. `[DUEÑO]` Zona horaria y hora de decisión (propuesta: cuenta, 09:00), canal del reporte (archivo + dashboard de F2; sin correo) y calendario por `locale` (con M1).
5. `[VERIFICAR]` Que el token de sistema pause sin el conector (y cómo aparece en `activity_log`); prueba de creativos por API con Advantage+ ventas (HC-12); nombres de campos; desglose por país; rango de la razón con consentimiento; `7d_click` para la razón.
6. **Pedidos a S-A** (`docs/_historial/coordinacion-sesiones.md`): esquemas `anomalias`, `pedidos_creativos`, `kpis_nivel`; riesgo y madurez en `veredicto_oferta.evidencia`; grupo `estadistica` (C15) y claves `testeo.alerta_*_x_be`, `salud_operativa.amarillo_escalon_menos`; duplicados `testeo.p_kill`/`k_corte` vs `estadistica.alfa_descarte`/`k_min_matar`; `engine.d8` vs `scripts/d8_*.py`.
7. `docs/_historial/d1-v2-interfaces.md` no existía: solo se aplicó el backbone (3.2, 5.11); revisar al aparecer.

---

## Anexo (se traslada a `references/` de la skill)

### A.1 Campos de Meta e insights

Por anuncio y día: `amount_spent, impressions, reach, frequency, cpm, link_click, outbound_clicks, outbound_clicks_ctr, omni_landing_page_view, omni_initiated_checkout, omni_purchase, omni_purchase_values`; video: `video_play_actions`, `video_p25…p100_watched_actions`, `video_thruplay_watched_actions`. Ventanas `1d_click`/`7d_click` (esquema del conector 2026-11-05; confirmar con `ads_get_field_context` `[VERIFICAR]`). `reach` y `frequency` **no son aditivos**: se consultan con el rango y nivel pedidos.

### A.2 Equivalencias v1 → clave canónica y parámetros propuestos

Grupos: `lectura_horas`, `hora_decision`, `max_pausas_dia_conjunto`, `anuncios_sin_entrega_pct` y los de pedidos → `optimizacion.*`; `ventana_no_decidir_h`, `k_corte`, `n_dec`, `p_*`, `tasa_*`, fatiga, `razon_ms_rango`, `cobertura_adid_min`, `k_ciego`, `chequeos_rojos_g8` → `testeo.*`; `N_val`, `dias_val_max`, `estab_tol`, `reembolso_max` → `veredicto.*`; `g6_*` (20 pagos, 0,6 %, 10 %) → `salud_operativa.*` (R06) y `limites.ratio_disputas_pausa`; `flex_gasto_max`, `paso_presupuesto`, `horas_entre_aumentos` (48), `max_cambios_dia` → `limites.factor_techo_teorico_diario`, `.aumento_presupuesto_max_pct_por_paso`, `.horas_min_entre_aumentos`, `.max_cambios_presupuesto_por_hora_por_conjunto`.

Propuestos (X2 con aprobación del dueño): `testeo.alerta_ctr_x_be` 0,45 · `.alerta_ic_x_be` 0,60 · `.alerta_venta_x_be` 0,80 `[CREADORES, C]`; `optimizacion.mer_ventana_dias` 7; `salud_operativa.amarillo_escalon_menos` verdadero; `.disputas_pausa_oferta_pct` 0,35, `.disputas_casos_macro` 5, `.reembolsos_macro_pct` 15 (nota 25 §9; la pausa de macro-nicho es H de O0/F1/X1, no de D8).

### A.3 Referencias de creadores por etapa

`[CREADORES]` (hipótesis; Argentina/LatAm y EE. UU. en USD; no transferibles a Polonia o Italia sin datos propios): hook rate > 20 % o > 50 % y retención > 5 % o > 10 % (SB se contradice, C: solo relativos a hermanos); CTR de enlace > 1–1,5 % (MB), > 2 % (SB), < 0,5 % malo (TT) (B: alerta, umbral propio por `locale`); vistas/clics ≥ 70 % (MB y SB, B = `tasa_conexion_min`); IC/vistas ≥ 10 % y compra/IC > 10 % (venta directa) o > 30 % (con carrito) (C); CVR de landing > 2 % con ≥ 300 visitas (MB, B); escalar con CPA ≤ 50–60 % del BE ≈ ROAS > 2 (B, = `cpa_obj` con `f` = 0,6), mantener entre 60 y 90 % (C); esperar 48–72 h (B/C). Fórmulas: `cpa_obj` = `f`·`cpa_be`; MER = ingreso neto Stripe ÷ gasto Meta del `locale`; margen por clic = conversión × `mc` − CPC·(1 + tarifa Meta) (docs/08 §7); P(0 compras con gasto G) = e^(−G/CPA real).
