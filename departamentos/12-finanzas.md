# F1 — Finanzas
> Tipo: empresa · Cadencia: continua (webhooks) + conciliación diaria + propuesta de capital semanal + cierre mensual · Gate por defecto: A (alertas) · H (capital: `accion:asignar_capital`, en todos los niveles) · Estado de la skill: por forjar · Especificación v2.2 (2026-11-06)

## 1. Misión y posición en el flujo

F1 es el CFO del sistema: convierte Stripe (ingresos), Meta (gasto) y costos de herramientas/IA en **una sola verdad contable por oferta y consolidada**, y responde: ¿gané plata?, ¿cuánto puedo gastar mañana?, ¿qué oferta, mercado o nicho merece capital? Principio `[NUEVO]`: **los scripts calculan, el LLM interpreta y propone; el dueño decide el capital**. F1 no mueve dinero, no pausa, no reembolsa: emite alertas y propuestas que consume el motor de O0.

- **Unidad (backbone 3.1):** una `oferta_id` = concepto × idioma/clúster de mercados, con dataset, dominio y P&L propios. F1 agrega por **familia**, **mercado** (`locale`, país del cliente, método de pago) y **macro-nicho y nivel de riesgo**. Se cobra en moneda local, se liquida en USD (LLC de EE. UU., decisión 7) y **nada se suma sin tipo de cambio registrado**.
- **Recibe de:** Stripe (clave de solo lectura; destino de webhooks `finanzas`, docs/07), Meta (gasto), `empresa/costos.jsonl`, `empresa/infra/*.yaml`, `oferta.json` y `economia.json` (D3), `mercado.json` (M1), `veredicto_oferta.json` (D8), `reembolsos.jsonl` (D10), `empresa/{limites,parametros}.yaml` (solo lectura).
- **Entrega a:** O0 (caja, pérdida acumulada), D3 (`tarifas.json`, realizado vs supuesto), M1 (economía por mercado), D8/D9 (cpa_be y roas_be reales, `capital.json`), F2 (la base de `datos/`: `fact_pedido` y `stripe_evento` los escribe `datos.etl_stripe` y F1 los **lee**; no son archivos de F1), X1/X2 (disputas y reembolsos por nivel), dueño. Salida: `empresa/finanzas/`.
- **Estado del código (2026-11-06):** `datos.ledger` y `datos.kpi` (B3) **aún no existen**; las fórmulas de 3.5 están en `decision.presupuesto.economia_por_pedido` y el IC del CPA en `decision.estadistica.intervalo_cpa_poisson_minor`. Tienen esquema `ledger`, `pnl`, `conciliacion`, `tipo_cambio`, `costos`; el resto no (Anexo D). Manda el contrato.

## 2. Qué dice el video (y qué no dice)

- **[VIDEO] hace:** menciona order bump/upsell; meta de "3.000 por mes en ganancia" con una "cuenta de cuántas ventas necesitás" que **no muestra**. **Omite:** presupuesto de anuncios, comisiones, reembolsos, disputas, impuestos, IA, caja, break-even, qué es "ganancia", multimoneda, reservas. Su nicho no es modelo.
- **[CREADORES] (confianza C salvo nota):** "ganancia" = facturación menos gasto publicitario (tomi-trimb/CYTDrzVwx9I @ 21:33); "no se preocupen por el IVA si todavía no vendieron" (tomi-trimb/-nQaXIO7Ap0 @ 1:23:11); ROAS de Italia 7-9, techo sin ajustar (16 §2.5); "con una venta ya está validado" frente a "nunca con una venta" (**B**); reembolsos de 0-5 por 100 sin datos (15 §4).
- **No tomamos:** "3.000 USD/mes" como promesa (parámetro del dueño, se calcula); cifras de creadores como evidencia; ROAS sin IVA ni reembolsos (un vendedor no establecido en la UE debe IVA desde la primera venta, 07a, A).
- **Contraste oficial:** Stripe no devuelve la comisión al reembolsar (03 §4.3); la disputa de tarjeta cuesta 15 USD; desde 2026-07-01 Meta cobra una **tarifa de ubicación** (FR/IT/ES 3 %, AT 5 %, UK 2 %), en línea aparte de la factura (07a, A; `[VERIFICAR]` en la primera factura).

## 3. Variables

### 3.1 Entradas (contrato de entrada)

| variable | tipo | origen | oblig. | ejemplo / valores |
|---|---|---|---|---|
| `stripe.{balance_transactions, charges, refunds, disputes, payouts, early_fraud_warnings, checkout_sessions, reportes}` | listas y CSV de la Reporting API (unidades mayores; fuente del QA) | Stripe, clave `rk_live_` solo lectura `[NUEVO]`; webhooks | sí | `metadata.oferta_id/cid/asid/adid` (5.3). `charge.*` = moneda de cobro; `balance_transaction.amount/currency/exchange_rate` = liquidación. Impuesto: `checkout_session.total_details.amount_tax` (Charge no lo trae) |
| `meta.gasto` | por campaña/anuncio/día (`spend`) | `ads_get_ad_entities`, `ads_insights_*` (MCP hasta N2; scripts desde N3) | sí | moneda y `tz` de la cuenta; la tarifa de ubicación llega por factura, no en `spend` |
| `costos.jsonl` | contrato `costos`: `oferta_id\|"empresa", etapa, origen ∈ {ia, creditos, herramienta}, concepto, monto{monto, moneda}` | todos los agentes (5.7) | sí | el detalle (claude, higgsfield, hosting) va en `concepto`. D6 (Higgsfield) alimenta `origen: creditos` con `creditos` entero y `monto` 0 hasta que F1 valore el crédito; el motor es el único escritor y consolida desde el borrador `06-creativos/costos.jsonl` de cada etapa (también D4 si habilita imágenes generadas). Ruta del libro: `empresa/costos.jsonl` |
| `empresa/finanzas/tipos_cambio.jsonl` | contrato `tipo_cambio`: `tipo_cambio_id` (`TC-USDPLN-20261106`), `par`, `tasa`, `fuente`, `hash_contenido` | `[DUEÑO]` elige la fuente; cobros: `exchange_rate` de Stripe | sí si hay >1 moneda | 1 USD = 3,72 PLN `[HIPÓTESIS]` |
| `oferta`, `mercado`, `portafolio`, `economia`, `veredicto_oferta` | `locale, moneda, macro_nicho, riesgo{nivel, subnivel}, familia_id, metodos_pago, fiscal, aov, mc, cpa_be, estado` | D3, M1, O0, D8 | sí | it-IT · EUR · dinero · amarillo-A; F1 **no redefine** "oferta validada" |
| `moneda_base`, `pais_titular`, `modo_impuestos` | ISO; enum | `[DUEÑO]`; `empresa/infra/stripe.yaml` | sí | USD · EE. UU. · `estandar+tax`, `managed_payments`, `sin_tax` (por mercado) |
| `meta_ganancia_mensual`, `tasa_renta_reserva` | número + definición; % | `[VIDEO]` (3.000) / `[DUEÑO]` y contador | sí | 3000 "operativa antes de renta"; 25 `[HIPÓTESIS]` |
| `limites.yaml`, `parametros.yaml` | techos; umbrales | `[DUEÑO]` / el sistema propone | sí | claves en 3.4; un `null` obligatorio ⇒ F1 propone, nada gasta |

### 3.2 Variables de decisión

| variable | opciones | criterio | cómo se testea |
|---|---|---|---|
| Madurez y vista | `pnl.vista` ∈ `devengado`, `caja`; `madurez` por bloque ∈ `provisional`, `maduro`, `mixto` | maduro = edad > `politica_reembolso_dias` + `veredicto.madurez_dias_extra` (R12); el capital usa lo maduro, o lo provisional con reserva | el QA reconstruye ambas |
| Costos compartidos | directa / prorrata por gasto Meta | directa si hay `oferta_id`; crear un concepto va a la familia y se reparte por gasto de las variantes; resto, 30 días | sensibilidad ±20 % |
| Moneda de reporte | base USD con la tasa de la fecha del hecho | cobros: `exchange_rate` del `balance_transaction`; gasto Meta y costos en otra moneda: tabla propia; diferencia de cambio aparte | sandbox multimoneda; moneda sin decimales |
| Modo fiscal por mercado | `estandar+tax` · `managed_payments` (+3,5 %) · `sin_tax` | F1 **calcula y compara** neto y cobertura de pago de cada modo; decide el dueño con el contador. En `sin_tax` el IVA implícito es pasivo contingente | `tarifas.json` con los tres modos |
| Forecast | 4 semanas + 3 meses; pes/central/opt | `r` y `d` por nivel (amarillo parte de `pes`); < 30 pedidos usa D3 marcado | MAPE |

### 3.3 Salidas (contrato de salida)

| artefacto | ruta | formato | campos obligatorios | consumidor |
|---|---|---|---|---|
| Libro mayor | `empresa/finanzas/ledger.jsonl` | `ledger` 1.0.0 | `clave_natural` (`<fuente>:<id>`, upsert), `tipo` ∈ {pedido, gasto, reembolso, disputa, comision, impuesto, costo, ajuste}, `oferta_id\|"empresa"`, `fecha`, `ts`, `sentido`, `importe{monto, moneda}` (origen), `es_prueba`, `adid`, `tipo_cambio_id` + `importe_base`; correcciones solo como `ajuste`. País, método y madurez, en `empresa/datos/` hasta el MINOR | F2, QA |
| Tarifas | `empresa/finanzas/tarifas.json` | sin esquema (pedido) | por (país, método, moneda): `comision_pct_bp, comision_fija, recargos_bp, conversion_bp, tarifa_disputa{monto, apelable}`; por país: `iva_bp`, `recargo_meta_bp`; por modo: `stripe_tax`, `managed_payments_bp`; `fuente_url`, `fecha_lectura` (≤ 30 días) | D3, M1, D5 |
| P&L | `empresa/finanzas/pnl.json` | `pnl` 1.0.0 | `por_oferta[]`, `consolidado` (9 líneas, `resultado_operativo`, `kpis`, `madurez`), `vista`, `fx_ref`, `frescura`. Cortes por familia, mercado y macro-nicho/nivel: `pnl_cortes.json` `[SUPUESTO]` | O0, F2, M1 |
| Conciliación | `empresa/finanzas/conciliacion.json` (`"empresa"`) y `conciliacion/<oferta_id>.json` | `conciliacion` 1.0.0 | `stripe_vs_ledger`, `gasto_meta_vs_ledger`, `compras`, `cobertura_adid_bp`, `estado`, `cifras_tachadas` | F2, QA |
| Economía real | `empresa/finanzas/economia_real.json` | JSON | realizado vs supuesto D3 (aov, b, r, d, mc, CPA, cpa_be y roas_be reales, brecha %), **por país y método**: comisión efectiva, mezcla, IVA, recargo Meta | D3, D8, D9, M1, X2 |
| Alertas | `empresa/finanzas/alertas.jsonl` | JSONL | `id, ts, severidad, regla_id, origen, oferta_id, macro_nicho, nivel, valor, umbral, accion_sugerida, estado` (unificado con F2: docs/04 §5) | O0, X1, dueño |
| Capital | `empresa/finanzas/capital.json` | JSON | caja (disponible, pendiente, reservas, comprometido), pasivos fiscales por país, `asignacion`, `payout_lag_dias`, `ventana_madurez_dias`, `reinversion_pct`, `r_esperado` por nivel, propuesta semanal (motivo, alternativa), `forecast`, `resiliencia` | **dueño (H)**, O0, D9 |
| Calculadora | `empresa/finanzas/calculadora.json` | JSON | `ventas_mes`, `gasto_meta_mes`, `capital_trabajo`, sensibilidad por mercado | dueño, D3 |
| Cierre mensual | `empresa/finanzas/cierre/AAAA-MM/{cierre.json, cierre.md, export_contador.csv}` | mixto | resultado, pasivos (IVA por país, renta), restatements, `sha256` | dueño, contador |
| Informe QA | `empresa/finanzas/qa/<periodo>-v<n>.json` | `qa` (6.3) | veredicto, puntajes, hallazgos, `aprendizajes_para_skill[]` | O0, X2 |

### 3.4 Parámetros y umbrales

Todos `[HIPÓTESIS]`. † = clave aún inexistente (Anexo D). Alertas: Anexo A.

| clave | inicial | nota |
|---|---|---|
| `ventana_madurez_dias` = `limites.politica_reembolso_dias` + `veredicto.madurez_dias_extra` | + 7 | R12 (la v1 usaba +14) |
| `salud_operativa.disputas_madurez_dias` · `limites.reserva_dias_stripe` † | 60 · 120 | pausar el gasto **no detiene el contador** de disputas (22d) |
| `finanzas.fondo_reembolsos_{amarillo,verde}_pct` † | 15 · 8 | del neto cobrado, liberado a 120 días; reemplaza `reserva_disputas_pct` (1 %) |
| `finanzas.reserva_reembolsos_modo` · `reserva_impuesto_indirecto_pct` | `r` esperado por nivel × neto no maduro · 100 % de `amount_tax` y del IVA implícito (`sin_tax`) | el impuesto es pasivo, no caja libre |
| `finanzas.reserva_renta_pct` · `reserva_stripe_pct`, `colchon_reserva_pct_90d` † | 25 % del resultado acumulado positivo · 0 hasta observar `risk_reserved`, tope 25 | renta 15-35 `[CONSULTAR contador]`; Stripe no publica % `[VERIFICAR]` |
| `finanzas.caja_congelamiento_*` † | 3 semanas de gasto Meta + 1 mes de fijos | caja mínima ante una retención |
| `finanzas.presupuesto_test_x_cpa_obj` · `escalado.reinversion_pct` · `orquestador.exploracion_pct` · `finanzas.concentracion_max_pct` · `limites.cuota_gasto_amarillo_max_pct` † | min(`limites`, 15 × cpa_obj) · 50 · 20 · 50 · 30 | 8-25 (04-meta-ads §9.2); resto: caja del dueño |
| `finanzas.payout_lag_dias` · `limites.dias_cobertura_caja` · `impuesto_meta_pct` · `tarifas_antiguedad_max_dias` · `comision_desvio_pp` | 14, luego medido · `payout_lag_dias` + 7 · 0 hasta conciliar (más `recargo_meta_bp`) · 30 · 1,5 | primer payout 7-14 d |
| `salud_operativa.reembolsos_{alerta,pausa}_pct`, `_n_min` | 8 · 12 · 20 | cohortes maduras |
| `salud_operativa.disputas_{alerta_pct, casos_alerta, casos_pausa, muestra_min_pagos}` | 0,3 % · 2 · 3 · 50 | **un solo conjunto** (R06) que leen F1, F2, D8, D10 y X1; pausa dura = `limites.ratio_disputas_pausa` |
| `disputas_pausa_oferta_pct` †, `_pausa_macro_pct` †, `reembolsos_macro_pct` †, `amarillo_escalon_menos` † | 0,35 % · 0,50 % y ≥ 5 casos · 15 % · `true` | nota 25 §9; **amarillo-A, un escalón más bajo** (alerta 0,15 %, 1 caso, 6 %; pausa 0,20 %, 2, 8 %) |

### 3.5 KPIs del paso

**Definiciones (las ejecuta el script; mismas que D3 con valores realizados; USD tras convertir cada línea con su `tipo_cambio_id`):**

```
cobrado       = Σ cargos exitosos (= pnl.ingresos_brutos, con impuesto) [VERIFICAR con CT]
impuesto      = Σ amount_tax − impuesto reembolsado (pasivo por país; = pnl.impuestos)
reembolsos    = Σ refund − su parte de impuesto          disputas_perdidas = netas de impuesto (abiertas → reserva)
comisiones    = Σ fee de balance_transactions (cargo, stripe_fx_fee, tax_fee, +3,5 % de Managed Payments); tarifa_disputa aparte
                -- NO se revierten al reembolsar [S39]; con Managed Payments Stripe remite el IVA
contribución  = cobrado − impuesto − reembolsos − comisiones − tarifas_disputa − disputas_perdidas − costo_var     mc = contribución / pedidos
gasto_meta_efectivo = Σ spend × (1 + impuesto_meta_pct) + Σ_país spend_país × recargo_meta_bp
aov = cobrado / pedidos (bruto, con impuesto: igual a `economia.aov` y `engine.factibilidad`)   aov_neto = (cobrado − impuesto) / pedidos     CPA = gasto_meta_efectivo / pedidos_stripe_atribuidos (adid), IC90 Poisson; < 10 compras: «evidencia insuficiente»
     CPA visto en Ads Manager = CPA / (1 + recargo_meta); CPA_mezclado (todos los pedidos) difiere > 25 % ⇒ alerta de tracking
ROAS_stripe = ingreso_atribuido / gasto_meta     ROAS_neto = contribución / gasto_meta     MER = ingreso_sin_impuesto / gasto_marketing
cpa_be = mc     cpa_be_visto = cpa_be × 10000 / (10000 + tarifa_meta_bp)     roas_be = aov / cpa_be
cpa_obj = `economia.factor_cpa_objetivo` (0,6) × cpa_be_visto (contrato `economia`; se compara con el CPA visto)     cpa_obj_efectivo = 0,6 × cpa_be (lo que usa la calculadora; se compara con el CPA efectivo)
resultado_operativo = ingresos_brutos − impuestos − reembolsos − comisiones − tarifas_disputa − disputas_perdidas − gasto_meta − costo_ia − otros_costos
```

**Por mercado y nivel:** `comision_efectiva_pct` por (país, método) · `mezcla_metodos` (cuota de BLIK en compras polacas; 08 pide ≥ 30 % como prueba de relevancia) · `reembolso_pct` y `disputa_pct` maduros por nivel, macro-nicho y mercado · `cuota_gasto_amarillo_pct` · `disputas_proyectadas_120d` · pasivo de IVA por país · `payback_caja_dias`.

**Vector de prueba `[HIPÓTESIS]`** (tarjeta internacional 4,4 % + 0,30; ticket 17, bump 7 al 30 %; r 7 %, d 0,5 %, costo_var 0,20): aov 19,10 · **mc 16,25** · cpa_be 16,25 · roas_be 1,18 · cpa_obj 9,75. **Caso con moneda y mercado (16 §2.2):** Italia, 14,90 € = 17,28 USD, IVA 22 % −3,12, comisión −1,23, Stripe Tax −0,09, reembolso 8 % −1,13, disputa −0,09 ⇒ mc ≈ 11,6; con Meta +3 %, cpa_be visto ≈ 11,3 (CPA modelado de 16 §2.3: 1,89 × el equilibrio). **Test real:** 10 pedidos (3 con bump), bruto 191, Meta 150 ⇒ CPA 15,0, IC90 ≈ 9,5-27,6: **no concluyente**; con IA/dominio imputados (52) el resultado operativo es −41,40.

**Oferta validada** (5.9, R11): no se define aquí; F1 entrega a D8 las compras de Stripe netas de reembolsos en cohorte madura y el CPA con gasto efectivo, y D8 emite `veredicto_oferta.estado`.

**Diferidos:** error de pronóstico de D3 por mercado · % de ofertas con resultado ≥ 0 a 60 días · costo de IA por oferta validada · error del forecast · rendimiento por macro-nicho y mercado (a D1 vía X2).

## 4. Flujo paso a paso (SOP)

| # | Actor | Acción | Guarda |
|---|---|---|---|
| 1 | Script | Webhook (destino `finanzas`) → `stripe_evento` único por `(tipo, objeto_id)` y `event.id` | `empresa/datos/` |
| 2 | Script (diario) | Backfill: balance_transactions, payouts, gasto Meta, `costos.jsonl`, tipos de cambio con hash | crudo versionado |
| 3 | Maker + Humano (≤ 30 días o desvío de comisión) | Propone `tarifas.json` desde páginas oficiales y Dashboard (texto crudo); el script valida y publica | `tarifas.json` |
| 4 | Script | Ledger; atribuye por `metadata.oferta_id` → `client_reference_id` → `lookup_key` → `adid`; resto a `empresa` (alerta si > 2 %); `es_prueba` excluida | `ledger.jsonl` |
| 5 | Script | Conciliación triple: Stripe = ledger; saldo inicial + Σ net − payouts = final; gasto Meta = insights | `conciliacion.json` |
| 6 | Script | P&L, cortes, KPIs, `economia_real`, reservas, caja, pasivos, alertas | `pnl.json`, `alertas.jsonl` |
| 7 | Maker | Interpreta desvíos (mezcla de países y métodos), recalcula break-even, propone capital con alternativa y riesgo, borrador de cierre | `capital.json`, `cierre.md` |
| 8 | QA | Re-ejecuta con recomputador propio, rúbrica y simulaciones | `qa/<periodo>-v<n>.json` |
| 9 | Humano | Aprueba o edita el capital (H); firma el cierre | `registro.jsonl` |
| 10 | Script | Publica a F2; las ROJAS de pausa las ejecuta O0 vía D8; si `pérdida_neta_acumulada` ≥ `perdida_neta_acumulada_max`, el guardarraíl de O0 (no F1) crea `empresa/PAUSA` | — |

**Cierre mensual:** el humano sube extracto bancario y cargos de Meta; F1 concilia payouts↔banco y gasto↔tarjeta. Provisional el día 2; **maduro** al cumplirse la ventana; luego, *restatement*. **Cada trimestre,** `export_contador.csv` trae base, tasa e IVA por país para la declaración OSS no-Unión (30-abr, 31-jul, 31-oct, 31-ene; en EUR, 07a A), el Reino Unido y países con umbral `[CONSULTAR contador]`.

## 5. Agente Maker

- **Rol:** CFO/FP&A. Interpreta números ya calculados, redacta cierre y propuesta de capital.
- **No hace:** calcular totales "de cabeza"; mover, reembolsar, pagar, pausar o activar; editar `limites.yaml`; cambiar `parametros.yaml` (propone `propuestas_parametros.json`); asesoría fiscal definitiva; inventar datos o tarifas.
- **Herramientas (mínimo privilegio):** lee `empresa/` y `03-oferta/`; escribe solo en `empresa/finanzas/`; ejecuta los módulos de datos. **Hasta N2** consulta por MCP Stripe (OAuth, lectura) y Meta (`ads_get_ad_entities`, `ads_insights_*`); **desde N3** solo lee archivos de scripts con credenciales propias (el MCP de Stripe exigirá OAuth o claves de agente desde 2026-11-30 `[VERIFICAR]`). **Denegado:** `stripe_api_write`, `ads_update_entity`, `ads_activate_entity`, `ads_create_*`, secret keys.
- **Seguridad de datos:** la RAK vive solo en el entorno de los scripts. El ledger guarda IDs y montos, no texto libre de clientes (datos no confiables); ningún nombre de producto ni dato de salud, deuda o relación entra en reportes: el cierre usa `oferta_id` y `slug` neutros. **Contexto:** `ledger`, `pnl.json`, `alertas`, parámetros, fallas de X2.

## 6. Agente QA

**Independencia:** contexto limpio; recibe cierre y propuestas, contrato 3.3, rúbrica, `limites.yaml`, supuestos de D3, fallas de X2; **no** el razonamiento del Maker. Usa un **recomputador propio** (`qa_recompute.py`, sesión aparte) y una **fuente distinta**: CSV de la Reporting API; en el cierre, extracto bancario, tarjeta de Meta y 3 pedidos al azar contra el Dashboard. Solo lectura. Sella por hash `cierre.json` y `capital.json`; sin QA-A.

**L1: checks deterministas** (falla = BLOQUEANTE salvo MAYOR indicado)

- **F1-01** `.venv/bin/python -m scripts.validar_esquemas oferta <dir>` valida ledger, tipos_cambio y conciliacion (`pnl` aún sin subcomando: `jsonschema`) · MAYOR.
- **F1-02** Σ balance_transactions por tipo = Σ ledger al centavo; saldo inicial + Σ net − payouts = final; payouts = *payout reconciliation*.
- **F1-03** sin duplicados (`clave_natural`) tras replay de webhooks; `es_prueba` fuera del P&L; ledger sin reescritura (solo upsert o `ajuste`).
- **F1-04** gasto Meta por oferta = insights (≤ `dashboard.recon_tol_gasto_meta_pct`), sin huérfanos, tarifa de ubicación conciliada con la factura.
- **F1-05** identidades: cobrado − impuesto − reembolsos − comisiones − costos = contribución; Σ ofertas + `empresa` = consolidado = dashboard; **Σ familias = Σ mercados = Σ macro-nichos**.
- **F1-06** impuesto fuera de ingreso; pasivo por país = Σ `amount_tax` (+ IVA implícito en `sin_tax`); sin doble conteo con Managed Payments.
- **F1-07** FX: cada línea convertida cita un `tipo_cambio_id` de la fecha del hecho; diferencia de cambio aparte; monedas sin decimales con half-even.
- **F1-08** corte de mes y zona horaria (`tz` de Meta vs UTC); fórmulas de 3.5 con los vectores de `docs/06` (16,25 · 24,42 · 11,54) y el caso Italia (±1 %) · MAYOR.
- **F1-09** la clave de F1 recibe 403 al escribir; ROAS/CPA usan compras de Stripe, nunca las de Meta.
- **F1-10** frescura ≤ `dashboard.frescura_stripe_balance_rojo_h` (36; hogar único con F2: la clave `finanzas.datos_frescura_roja_h`, 26, se retira por pedido, docs/04 C-13); `empresa` ≤ 2 %; `adid` ≥ `cobertura_atribucion_min_pct`; `tarifas.json` ≤ 30 días y con cada (país, método) vendido · MAYOR.
- **F1-11** umbrales leídos de `parametros`/`limites`, ninguno fijo; oferta amarilla con el escalón de su nivel · MAYOR.
- **F1-12** propuesta de capital ≤ `limites.yaml`, con vista madura (o provisional con reserva), cuota amarilla respetada, `caja_libre` ≥ 7 días de gasto y caja de congelamiento.

**L2: rúbrica** (0-5 con evidencia citada; mínimo 3 por dimensión; total ≥ 80 % `[HIPÓTESIS]`)

| dimensión | 1 | 3 | 5 |
|---|---|---|---|
| Definiciones y madurez | mezcla bruto/neto; ganancia dentro de garantía | un KPI ambiguo; provisional con recomendación | coinciden con 3.5 y D3; condiciona por madurez |
| Multimoneda e impuestos | suma monedas o ignora el IVA | convierte bien, IVA sin país | tasa por fecha, pasivo por país, modos comparados |
| Imputación de costos | sin asignar | sin criterio | justificada, con sensibilidad |
| Capital | "subir/bajar" sin números | monto y motivo | monto, motivo, alternativa, riesgo, tope, nivel |
| Alertas | ruido o sin acción | acción vaga | valor, umbral, causa, acción, responsable |
| Forecast y claridad | un número; jerga | escenarios sin intervalo | 3 escenarios; las 3 preguntas en 5 min |

**L3: simulaciones.** (a) *Contador escéptico:* rehace el mes desde `export_contador.csv` y el Dashboard, con el IVA por país. (b) *Dueño en 5 minutos:* "¿gané?", "¿cuánto gasto mañana?", "¿qué me preocupa?". (c) *Estrés:* r×3, CPA +50 %, FX −10 %, disputa en ticket de 7. (d) *Replay* de eventos. (e) *Retención* de 120 días en Stripe o cuenta de Meta restringida: `resiliencia` da los días cubiertos.

**Calibración:** dorado = mes sintético en sandbox de Stripe (disputa: `4000 0000 0000 0259`) o fixtures `[VERIFICAR]`; defectos sembrados en el Anexo B, rotados; meta ≥ 90 % de bloqueantes y PASS al dorado sin falsos BLOQUEANTES. **Mejoras que busca:** costos huérfanos de IA, ROAS_neto < roas_be, mezcla de países o métodos que cambia la comisión; corrige solo lo mecánico.

**Veredictos y loop:** backbone 5.4 y 6 (máx. 2 rondas; `PASS` exige 0 BLOQUEANTES/MAYORES y puntaje ≥ umbral; si no, `ESCALAR`); mínimo 3 hallazgos o justificación; hallazgos con `check_id`, `patron_clave`, `severidad`, `etapa`, `skill_version`.

## 7. Gates y autonomía

"Capital" = asignación de presupuesto de anuncios y reservas; F1 nunca mueve dinero bancario. `contratos/gates.json`: `etapa:F1` = A y `accion:asignar_capital` = **H en N0-N4**; el nivel de F1: `empresa/autonomia.yaml`. **Automatiza,** con guardarraíl determinista (alertas y pausas en código, reservas mínimas, propuesta ≤ `limites.yaml`, kill por `perdida_neta_acumulada_max` ejecutado por O0, clave de solo lectura): ingestión, ledger, conciliación, P&L, KPIs, alertas, forecast, calculadora, export contable.

| Nivel | Qué hace F1 | Gate |
|---|---|---|
| N0 | El dueño arma P&L y cierre a mano en Claude Code; se forjan fórmulas y alertas | H todo |
| N1 | Maker con skill produce todo; el dueño revisa todo | H |
| N2 | Maker + QA; capital y cierre firmados | A alertas · H capital y cierre |
| N3 | Cierre por muestreo; propuesta por bandas, **sigue H** | A · H capital |
| N4 | Revisión semanal; reasignación automática solo si el dueño cambia `gates.json` | A con kill switches · H límites, caja, impuestos |

**Ascender `[HIPÓTESIS]`:** N0→N1: cierre dorado exacto. N1→N2: 2 cierres con 0 diferencias vs Stripe/contador. N2→N3: ≥ 90 días, ≥ 80 % de alertas accionadas, 0 falsos negativos rojos, ≥ 70 % de propuestas sin edición, MAPE ≤ 25 % a 4 semanas. N3→N4: 2 meses sin bloqueantes y estrés superado. Descenso automático si hay una diferencia > 1 USD o una roja no detectada.

## 8. Riesgos y modos de falla

| riesgo | señal temprana | mitigación | responsable |
|---|---|---|---|
| Ganancia inflada por datos inmaduros | reembolsos y disputas tardíos | madurez por bloque; fondos 15/8 %; restatement | F1 |
| **Concentración:** una cuenta de Stripe y una de Meta sostienen todo | `risk_reserved`, payout atrasado, aviso de Stripe, cuenta de Meta restringida | caja de congelamiento; `resiliencia` trimestral; pausa por tramos (oferta, macro, `PAUSA`); carril B solo para verdes | F1/X1/dueño |
| Amarillas: reembolsos y disputas sobre lo supuesto | `r`/`d` > escenario `pes` | escalón más bajo; cuota amarilla; aviso a X1 y D9 | F1 |
| Comisión subestimada (métodos, FX, Stripe Tax por API = 0,50 USD fijo) | comisión efectiva > esperada | `tarifas.json` ≤ 30 días | F1 |
| IVA sin reservar o mal clasificado; OSS o UK sin registrar | pasivo ≠ `amount_tax` | pasivo por país; `sin_tax` solo con `exposicion_aceptada` | F1/dueño |
| Meta: tarifa de ubicación o impuestos fuera de `spend`; prepago alto | gasto ≠ cargos en tarjeta | conciliar con factura; prepago ≤ 3 días de gasto (si el preflight M-03 exige tarjeta sin prepago, manda M-03) | Humano/F1 |
| Caja: Meta cobra antes de que Stripe pague; n chico | `caja_libre` < 7 días; IC90 cruza cpa_be | recortar tope (H); «evidencia insuficiente» | F1/D8 |

## 9. Mejoras respecto del video

1. **[NUEVO] Break-even antes de gastar,** por mercado, con IVA, método y recargo de Meta, recalculado con datos reales.
2. **[NUEVO] Ledger único, idempotente y multimoneda,** conciliado a diario y contra banco y tarjeta.
3. **[NUEVO] Ganancia provisional vs madura,** fondos por nivel (15/8 %), caja de congelamiento y simulacro de retención.
4. **[NUEVO] P&L por oferta, familia, mercado y macro-nicho,** con comisión efectiva por método: el dato propio con que M1 y D9 deciden mercados (Polonia e Italia son hipótesis).
5. **[NUEVO] Impuestos como pasivo por país,** modos fiscales comparados y paquete para el contador (OSS, Reino Unido, renta de la LLC).
6. **[NUEVO] Reglas de capital** y calculadora de la meta.

**Calculadora `[HIPÓTESIS]`:** `ventas_mes = (G_pre + F_mes) / (mc − CPA)`, `G_pre = G_neta / (1 − tasa_renta_reserva)`; `gasto_meta_mes = ventas_mes × CPA`; `capital_trabajo ≈ gasto_diario × (payout_lag + 7)`. Con G = 3.000 antes de renta y F_mes = 150: **vector de prueba** (mc 16,25; cpa_obj 9,75) ⇒ **485 pedidos/mes** (≈ 16/día), Meta ≈ 4.730 USD, capital ≈ 3.300 USD (CPA ≥ mc ⇒ imposible). **Italia, frontal solo** (mc 11,6; cpa_obj efectivo 6,96) ⇒ **679 pedidos/mes** (≈ 22/día), Meta ≈ 4.725 USD; si 3.000 es neto tras renta al 25 %, ≈ 894. El CPA de escala suele superar el del test (`cpa_escala`) y esos volúmenes pueden exigir varias ofertas y mercados: la meta depende del CPA y del aov; D3 debe diseñar el valor del primer pedido.

## 10. Forja de la skill (pestaña Code)

### 10.1 Prompt de arranque (copiar y pegar)

```
ROL: Eres el CFO/FP&A de un sistema autónomo que lanza ofertas de productos digitales de bajo ticket en cualquier mercado e idioma, con anuncios en Meta y cobro con Stripe (LLC de EE. UU.: cobro en moneda local, liquidación en USD), y analista de riesgo de pagos. Cumplidor por construcción pero criterioso: el riesgo se evalúa por candidato (salud, relaciones, dinero), no por tema. Español con tildes.

DIRECTORIO: abre la sesión en <carpeta del proyecto>. LEE PRIMERO: docs/_backbone.md (v2.2: 3.1, 5, 6), departamentos/12-finanzas.md (3, 6, Anexo), docs/contratos.md, contratos/{ledger,pnl,conciliacion,tipo_cambio,costos,economia}.schema.json, empresa/{limites,parametros}.yaml (solo lectura), docs/convenciones-de-codigo.md (3, 4, 7), docs/_investigacion/03-stripe.md (4-7), 07a, 07e, 16 (2) y 25 (9, 10). Las cifras de creadores no son hechos.

ENTRADAS (mercado e idioma son ENTRADA): pregúntame primero locale, países de cliente, moneda de cobro, métodos de pago, macro-nicho, nivel de riesgo y precio, y úsalos en TODO; sin carpeta de oferta, modo práctica: copia ofertas/_ejemplo/ a ofertas/practica-01/. Datos de Stripe y Meta: solo los CSV que yo te dé; sin ellos, un mes sintético [SUPUESTO] en empresa/finanzas/_sintetico/.

TAREA: v1 de F1 con el contrato de 3.3: ledger, tipos_cambio, tarifas (URL y fecha o [VERIFICAR]), pnl (oferta, consolidado, cortes por familia, mercado y macro-nicho), conciliacion, economia_real, alertas (Anexo A), capital, calculadora (3.000/mes) y cierre mensual. El cálculo lo hace código: datos.ledger y datos.kpi aún no existen; escribe prototipos en empresa/finanzas/_propuestas_codigo/ (nunca en datos/, engine/, decision/, contratos/ ni .claude/) y reutiliza decision.presupuesto.economia_por_pedido. Tests: vector de 3.5 (mc 16,25; roas_be 1,18; 485 pedidos), docs/06 (24,42 · 11,54) y el caso Italia (±1 %). Valida con .venv/bin/python -m scripts.validar_esquemas oferta ofertas/practica-01 (ledger, tipos_cambio, conciliacion; pnl, con jsonschema).

ACEPTACIÓN: Stripe = ledger = P&L = dashboard al centavo; impuestos fuera de ingreso, pasivo por país; comisiones no devueltas; ROAS/CPA con compras de Stripe (CPA con IC90); vistas provisional y madura; reservas fuera de la caja libre; ninguna suma de monedas sin tipo_cambio_id; ningún umbral fijo en código; ejemplos en 3 macro-nichos y 2 idiomas/monedas (it-IT en EUR, pl-PL en PLN con BLIK); cada número con fuente o etiqueta.

REGLAS: no inventes datos ni tarifas; PREGUNTAS BLOQUEANTES PRIMERO (moneda base y fuente de FX, modo de impuestos, definición de "ganancia", tasa de renta, límites) y espera; solo claves de lectura; NO ejecutes acciones con costo o efecto externo sin mi permiso; no edites limites.yaml, parametros.yaml ni contratos (lista de pedidos); termina con supuestos, riesgos y preguntas abiertas.
```

### 10.2 Cómo pulir
Máximo ~3 sesiones de 60-90 min. Mirar: ¿coinciden 3 pedidos (uno en moneda local) y 1 payout con el Dashboard y el banco?; ¿entendés el resumen en 5 minutos?; ¿cada alerta dice qué hacer?; ¿qué número te daría miedo?; ¿firmarías el capital propuesto? Probá un mes malo, una amarilla y otra moneda.

### 10.3 Estructura de la skill a generar
```
.claude/skills/f1-finanzas/
├── SKILL.md   rubric.md   evals/ (mes dorado, sembrados, nichos, idiomas, monedas)
├── references/   # definiciones (3.5), tarifas e IVA por país, reglas de capital, Anexo
├── templates/    # cierre, resumen semanal, propuesta de capital
└── scripts/      # envoltorios de datos.ledger/datos.kpi, calculadora, qa_recompute
```
Subagentes: `.claude/agents/f1-maker.md`, `f1-qa.md`.

### 10.4 Definición de listo (DoD)
Cierre dorado al centavo · tests reproducen 3.5, `docs/06`, el caso Italia y la calculadora · `validar_esquemas` pasa · ≥ 90 % de bloqueantes sembrados y 0 falsos BLOQUEANTES en el dorado · el dueño responde las 3 preguntas en ≤ 5 min · clave sin escritura · evals 2-9 en PASS sin editar la skill entre uno y otro.

### 10.5 Evals mínimos
1) Mes dorado, **dinero (it-IT):** presupuesto por fecha de cobro, 14,90 €, IVA 22 %, Meta +3 %. 2) Misma oferta **en pl-PL** (49 zł, BLIK 45 % + tarjeta, IVA 23 %): dos `oferta_id` de una familia, comparadas. 3) **Salud (it-IT):** planificador de comidas, amarillo-A (fondo 15 %, escalón más bajo). 4) **Relaciones (pl-PL):** tarjetas de conversación para parejas, 7 € sin bump. 5) Cobro en USD y moneda sin decimales (CLP/JPY) con impuesto y reembolso parcial. 6) Managed Payments frente a estándar en Polonia. 7) 3 disputas y 12 % de reembolsos; payout retenido y `risk_reserved`. 8) Eventos duplicados, gasto sin `oferta_id`, compras de prueba. 9) Meta de 3.000/mes con CPA ≥ mc. Aprobado = checks en verde y diferencia 0,00 por eval.

## 11. Preguntas abiertas / decisiones del dueño

1. `[DUEÑO]` **Moneda base:** USD (liquidación de la LLC, decisión 7). Falta la **fuente de tipo de cambio** para gasto Meta y costos (recomendado: `exchange_rate` de Stripe para cobros y un banco central para el resto) y la moneda de la cuenta de Meta (`moneda_limites`; el conector no la devuelve).
2. `[DUEÑO]` **Modo de impuestos por mercado** con el contador: estándar + Stripe Tax, Managed Payments (+3,5 %; Polonia queda en ~23 % de cobertura) o `sin_tax` con exposición aceptada. Diferido: v1 calcula con tarjeta.
3. `[DUEÑO]` **Qué es "3.000 USD de ganancia":** ¿operativa antes de renta o en tu bolsillo?; régimen fiscal de la LLC y tasa `[CONSULTAR contador]`.
4. `[DUEÑO]` Capital, `perdida_neta_acumulada_max`, presupuesto de test y tope diario: **diferidos**; en `null` nada gasta. Aprobar las claves nuevas (fondos 15/8 %, caja de congelamiento, escalón amarillo) y fijar `ratio_disputas_pausa` (0,5 % de la nota 25 o 0,6 % de la plantilla).
5. `[DUEÑO]` ¿Cuánto del beneficio maduro se reinvierte? ¿Reasignación automática (cambiar `gates.json`)? Política de reembolso (días) y topes automáticos.
6. `[VERIFICAR]` Facturación de Meta (umbral/mensual, impuestos, línea de la tarifa de ubicación) y si `amount_spent` la incluye; reservas de Stripe en cuentas nuevas; base del 3,5 % de Managed Payments; `tax_fee` de Stripe Tax por API; Reporting API y `exchange_rate` en sandbox.
7. `[VERIFICAR]` IVA de PDF de plantillas frente a e-book (IT 4 %, PL 5 %, fuentes C) y qué tasa y fecha usa el OSS para monedas distintas del euro.

## Anexo (se traslada a references/ de la skill)

### A. Reglas de alerta (los umbrales salen de `parametros`/`limites`, nunca del código)

- **F1-A01** reembolsos/pagos (cohorte madura, n ≥ `reembolsos_n_min`): > alerta AMARILLA, > pausa ROJA.
- **F1-A02** (disputas + EFW)/pagos a 30 días: ≥ alerta o `casos_alerta` (AMARILLA); ≥ `disputas_pausa_oferta_pct` o `casos_pausa` (NARANJA, pausa de oferta); ≥ pausa de macro y ≥ 5 casos (ROJA, **H**). Una amarilla-A usa el escalón más bajo.
- **F1-A03** comisión efectiva fuera de `comision_desvio_pp` con ≥ 20 cargos · AMARILLA. **F1-A04** gasto vs tope (día, test) o cuota amarilla ≥ 80 % AMARILLA, ≥ 100 % ROJA.
- **F1-A05** `ROAS_stripe` < `roas_be` real tras gasto ≥ `testeo.k_corte` × cpa_be · ROJA; compras Meta/Stripe fuera de 0,8-1,3 · AMARILLA.
- **F1-A06** datos > `dashboard.frescura_stripe_balance_rojo_h` o conciliación ≠ 0 (cifra tachada) · ROJA. **F1-A07** saldo Stripe < 0, payout `failed` o `risk_reserved` · ROJA; `caja_libre` < 7 días · AMARILLA. **F1-A08** disputa abierta con `due_by` (D10 responde; F1 reserva), `tarifas.json` > 30 días, trimestre OSS sin base · AMARILLA.

### B. Defectos sembrados (rotar y combinar)

**BLOQUEANTES:** (1) cargo contado dos veces; (2) impuesto como ingreso; (3) monedas sumadas sin convertir o tasa de hoy; (4) ROAS con compras de Meta; (5) sube presupuesto con ganancia solo provisional; (6) clave de lectura con escritura; (7) `sin_tax` sin reserva del IVA implícito.
**MAYORES:** (8) reembolso que devuelve la comisión; (9) disputa perdida sin tarifa; (10) gasto imputado a otra oferta; (11) dashboard ≠ P&L; (12) calculadora sin fijos ni reembolsos; (13) impuesto restado dos veces; (14) disputa abierta sin reservar o payout en tránsito como caja libre; (15) pedidos sin `oferta_id` descartados; (16) tarifa de ubicación no imputada; (17) Managed Payments sin su 3,5 % o con IVA doble; (18) umbral fijo en código u oferta amarilla con umbrales de verde; (19) prueba en el P&L o cortes que no suman; (20) producto sensible nombrado en el cierre o en un evento.

### C. Tarifas y fuentes (`tarifas.json` v1; titular EE. UU., leídas 2026-11-05/06; `[VERIFICAR]` antes de usar)

- **Tarjeta** 2,9 % + 0,30 USD, internacional +1,5 %, conversión +1 % (03 §4.1, A). **BLIK · Satispay · MB WAY · Bancontact · EPS · Pay by Bank** 1,9 · 1,8 · 1,5 · 1,4 · 1,6 · 1,5 % + 0,30 con los mismos recargos (07e §1.2, A). **P24** (no habilitado) 2,2 % + 0,30; **Pix** 1,8 % + 0,30, IOF 3,5 % del cliente (07g).
- **Disputa** 15 USD; BLIK sin tarifa ni apelación; Pix solo por fraude (03 §4.1, 16 H1). **Stripe Tax** 0,5 % o 0,50 USD por API. **Managed Payments** +3,5 %, sin BLIK, Satispay, MB WAY, EPS, Pay by Bank ni P24 (03 §4.2, 07e).
- **Meta, ubicación:** FR/IT/ES 3 %, AT 5 %, UK 2 %; PL, DE, NL, PT, GR, BE, IE sin tarifa (07a, A). **IVA estándar:** IT 22 · PL 23 · FR 20 · DE 19 · ES 21 · PT 23 · UK 20 %; e-book reducido (IT 4, PL 5) no vale para plantillas sin el contador (07a B.1, 07b; B/C).

### D. Pedidos y conflictos resueltos (el contrato manda)

- **Resueltos:** (1) ledger: la v1 usaba `asiento_id`, `hash_prev` y tipos `cobro/payout/reserva_*`; manda `ledger.schema.json`; payouts, reservas y caja van en `capital.json`. (9) Reconciliación F1/F2 (docs/04 §8, C-01…C-17): `aov` bruto, `cpa_obj` sobre `cpa_be_visto`, `roas_be = aov / cpa_be`, alertas unificadas, F1 lee `fact_pedido`, frescura de Stripe con un solo hogar. (2) `pnl.vista` = `devengado|caja`; la madurez es del bloque. (3) `costos.origen` = `ia|creditos|herramienta`. (4) Madurez = garantía + 7 (R12), no +14. (5) Un solo conjunto de umbrales en `salud_operativa` (R06). (6) "Oferta validada" = `veredicto_oferta.estado` (R11). (7) Código en `datos.ledger`/`datos.kpi`, no `scripts/finanzas/`. (8) `asignar_capital` es H siempre.
- **Pedidos a CT** (también en `docs/_historial/coordinacion-sesiones.md`): `ledger` 1.1.0 (`pais_cliente`, `metodo_pago`, tipos `payout`/`reserva`); `pnl` 1.1.0 (`por_familia[]`, `por_mercado[]`, `por_macro_nicho[]`); `pnl.fx_ref` (`FX-…`) frente a `tipo_cambio_id` (`TC-…`); esquemas `tarifas`, `economia_real`, `capital`, `alertas`, `calculadora`, `cierre`; claves † de 3.4; `ratio_disputas_pausa` 0,006 (plantilla) frente a 0,005 (nota 25); confirmar que `pnl.ingresos_brutos` incluye impuesto.
