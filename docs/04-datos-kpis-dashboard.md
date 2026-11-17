# 04 — Datos, KPIs y dashboard (documento único de datos)

> Versión 1.0 (2026-11-06). Rol: ingeniería de datos y BI para medición de ads y ecommerce multimoneda. **Normativo para el glosario de KPIs, el modelo de datos, el ETL, la conciliación y las vistas.** Subordinado a `docs/_backbone.md` (v2.2), `docs/contratos.md` y `contratos/*.schema.json`; si choca con un contrato o con el código, manda el contrato/código y se registra en §8. Reemplaza al Anexo A de F2 (`departamentos/13-dashboard-bi.md`) como **fuente única del glosario**; F2 y F1 (`12-finanzas.md`) conservan su misión y sus controles. Etiquetas: `[HIPÓTESIS]`, `[VERIFICAR]`, `[SUPUESTO]`, `[NUEVO]`, `[DUEÑO]`, `[CREADORES]` (confianza A/B/C).

## 0. Alcance, precedencia y estado real del código

**Principios** (backbone 5.3, F1/F2): (1) **el código calcula, el LLM interpreta**: ningún KPI sale de un LLM ni de JavaScript; (2) **Stripe = verdad de ingresos, Meta = verdad de gasto**; las compras de Meta son señal («Meta reporta»); (3) uniones por **IDs** (`oferta_id` + `adid`), nunca por nombres; (4) dinero en **enteros de unidad menor** + ISO 4217, ningún `float`; (5) **nunca se suman monedas**; (6) «datos insuficientes» es **gris**, jamás rojo; (7) fuente caída ⇒ cifra marcada, nunca 0 ni valor viejo sin marca.

**Qué existe hoy (2026-11-06) y qué no**

| Pieza | Estado | Consecuencia |
|---|---|---|
| `datos.db` (`conectar`, `migrar`, upsert), `datos.etl_stripe` (3 tipos de evento, solo `--fixture`), `datos/migraciones/0001_inicial.sql` | **Existen** | El modelo de §2.1 distingue lo migrado de lo objetivo |
| `datos.etl_meta`, `datos.ledger`, `datos.kpi`, `dashboard.build/alertas/api`, `contratos/kpi` por familia/mercado/macro/radar | **No existen** (B3/B10; `kpi` solo tiene `ambito` oferta/blended) | Todo lo de §1 y §4 es especificación; se prueba con fixtures `[SINTÉTICO]` |
| Contratos `kpi`, `pnl`, `ledger`, `conciliacion`, `costos`, `tipo_cambio`, `tracking_plan`, `traspaso`, `senal_pausa`, `reembolso`, `entrega` | Existen | Mandan sobre cualquier nombre de este documento |
| `docs/_historial/d1-v2-interfaces.md`, `empresa/descubrimiento/`, `02-descubrimiento.md` v2 | **No existen** (el archivo del árbol sigue en v1) | Los KPIs del Radar (§4.3) son `[SUPUESTO]` derivados del backbone 3.2 y de `parametros.descubrimiento`; se reconcilian cuando D1 publique sus interfaces |
| Postgres | `datos.db` reconoce `postgresql://` y **falla cerrado** (sin controlador) | Producción N0-N2: SQLite en volumen de Railway (docs/06 §4.8) |

## 1. Glosario canónico de KPIs

### 1.1 Convenciones

- **Agregación:** todo KPI se calcula como **razón de sumas** (Σ numerador / Σ denominador) en el grano pedido, nunca como promedio de razones. Se almacena en el grano más fino disponible (anuncio-día) y se agrega hacia arriba. `alcance` y `frecuencia` **no son aditivos**: se consultan a Meta con el rango y nivel pedidos.
- **Unidades en `kpi.filas[].unidad`:** `minor:<ISO>` (dinero, entero), `bp` (tasas, entero), `ratio` (ROAS, MER, razones; decimal con 2 cifras), `count`, `horas`, `dias`. Moneda de agregados: **USD** (§3).
- **Día de reporte** = día calendario en la **zona IANA de la cuenta de Meta** (`engine.comun.dia_de_cuenta`); Stripe y el ledger (que guarda el día UTC) se recortan a esa zona al leer. Días con menos de `dashboard.meta_dias_inmaduros` (2) de antigüedad y ventanas de 28 d en campañas de < 28 d son **provisionales** (Meta tarda hasta 48 h en procesar, 04-meta-ads §2.5).
- **Estados del dato** (`kpi.estado`, contrato): `ok` · `provisional` (días o cohortes inmaduros) · `gris` (n bajo el mínimo o clave sin valor) · `stale` (fuente roja/vieja o conciliación ≠ `CONCILIADO`: la cifra se muestra **tachada con la causa**). El **color** (verde/amarillo/rojo) no se persiste: lo deriva `dashboard.build` del valor y las claves de §1.8; se acompaña siempre de símbolo (● ▲ ■ ○) para no depender del color.
- **Mínimos de datos** (`min`): **M-imp** = `impresiones ≥ testeo.impr_min_diag` (3.000) y `clics_enlace ≥ testeo.clics_min_diag` (100) para juzgar tasas de tráfico; **M-ped** = `compras ≥ dashboard.pedidos_min_verde` (5) para verde, `≥ dashboard.recon_min_pedidos` (10) para razones; **M-gasto** = `gasto_meta ≥ dashboard.gasto_min_decision_x_cpa` (2,0) × `cpa_obj` para rojo (visual: D8 decide con `testeo.*`); **M-mad** = cohorte madura (§1.6). Si falta, el KPI es `gris`.
- **Qué compra cuenta** (`compras`): sesiones de Checkout **raíz** con `payment_status = paid` o `async_payment_succeeded`, `livemode = true`, sin `verificacion = 1` ni `interno`. `checkout.session.completed` con `unpaid` (OXXO, Pix, transferencias) **no es venta** hasta el evento asíncrono; si falla, nunca lo fue. Un upsell post-compra es una sesión hija (`parent_session_id`): suma a ingresos y `aov`, no a `compras` (no duplica el CPA).

### 1.2 Tráfico y entrega (fuente Meta; grano anuncio-día)

| `kpi_id` | Definición y fórmula | Tolerancia | Semáforo (claves) y mínimo |
|---|---|---|---|
| `gasto_meta` | Σ `spend` (moneda de cuenta → USD, §3). «Gasto visto» en Ads Manager | ≤ `dashboard.recon_tol_gasto_meta_pct` (1 %) contra reconsulta, solo días maduros; contra el ledger de F1 = 0 | Sin color propio. Contra tope: ▲ ≥ `finanzas.gasto_vs_tope_amarilla_pct` (80 %), ■ ≥ `gasto_vs_tope_roja_pct` (100 %) de `limites.gasto_diario_*`; ■ si > `dashboard.alerta_gasto_sobre_presupuesto_x` (1,75) × presupuesto diario |
| `gasto_meta_efectivo` | `gasto_meta × (1 + finanzas.impuesto_meta_pct) + Σ_país gasto_país × recargo_meta_bp` (tarifa de ubicación; llega por factura, no en `spend`) | Conciliado con la factura de Meta (mensual) | Base del `cpa` de F1 |
| `impresiones` | Σ `impressions` | 1 % | M-imp para cualquier tasa |
| `alcance`, `frecuencia` | `reach` del rango; `impresiones / alcance` del mismo rango | n/a | `frecuencia`: ▲ ≥ `testeo.freq_alerta_7d` (2,5) en 7 d |
| `cpm` | `gasto_meta / impresiones × 1000` | derivado ±0,01 | ▲ > `testeo.cpm_alto_factor` (1,5) × CPM de D3 o mediana propia 7 d; por `locale` |
| `clics_enlace` | Clics en el enlace (campo único fijado por el ETL con `ads_get_field_context`; **nunca** `clicks` total) `[VERIFICAR]` | 1 % | M-imp |
| `ctr_enlace` | `clics_enlace / impresiones` | derivado | Bandas de `economia.escenarios_embudo` del `locale`: ■ < pes (80 bp), ▲ < central (120 bp), ● ≥ central; umbral propio por `locale` tras datos propios `[HIPÓTESIS]` |
| `cpc_enlace` | `gasto_meta / clics_enlace` | derivado | Informativo vs `economia.cpc_esperado` |
| `hook_rate` | Reproducciones de ≥ 3 s / impresiones (anuncios de video; `video_play_actions`) `[VERIFICAR campo]` | 1 % | **Relativo a sus hermanos** del conjunto (D8), no absoluto `[CREADORES, C]`; gris bajo M-imp |
| `hold_rate` | ThruPlay (`video_thruplay_watched_actions`) / reproducciones de 3 s `[VERIFICAR]`; curva p25-p100 en el detalle | 1 % | Relativo a hermanos; gris bajo M-imp |

### 1.3 Embudo (Meta + tracking propio + Stripe)

| `kpi_id` | Definición | Semáforo (claves) y mínimo |
|---|---|---|
| `vistas_landing` | `omni_landing_page_view` de Meta (misma fuente que los clics); control: sesiones del Worker propio | Diferencia > 25 % entre ambas ⇒ alerta de tracking |
| `tasa_conexion` (antes `tasa_lpv` en F2) | `vistas_landing / clics_enlace` | ■ < `testeo.tasa_conexion_min` (0,70); M-imp |
| `inicios_pago` | `InitiateCheckout` deduplicados por `event_id` (`ic_<visitor_id>_<ts>`) del Worker propio | Embudo no monótono con tracking caído ⇒ alerta, no cifra |
| `tasa_ic` (antes `tasa_checkout`) | `inicios_pago / vistas_landing` | ▲ < `testeo.tasa_ic_min_pct` (3 %) |
| `compras` | Ver §1.1 (Stripe) | Tolerancia 0 contra `balance_transactions` |
| `tasa_compra_ic` (antes `tasa_compra`) | `compras / inicios_pago` | ▲ < `testeo.tasa_compra_ic_min_pct` (20 %) |
| `conv_clic_compra` | `compras / clics_enlace` | Referencia: `economia.conv_central` |
| `compras_meta` | `omni_purchase` **por ventana** (`1d_click`, `7d_click`, `28d_click`, `1d_view`); **ventanas solapadas: jamás se suman** | Siempre rotulado «Meta reporta» con su ventana |
| `mix_metodos`, `conv_checkout_metodo` | Compras por `metodo` / compras; compras / `inicios_pago` por método | Informativo; gris bajo M-ped; M1 lo usa para refutar o confirmar la relevancia de un método (p. ej. BLIK) |

### 1.4 Ventas, impuestos y comisiones (Stripe → USD; grano pedido-día)

| `kpi_id` | Definición y fórmula | Tolerancia / fuente |
|---|---|---|
| `ingresos_brutos` | Σ cobrado **con impuesto** de compras (= `pnl.ingresos_brutos`; el esquema lo implica: `resultado_operativo = ingresos_brutos − impuestos − …`) | 0 vs `balance_transactions` |
| `impuestos` | Σ `amount_tax` − impuesto reembolsado; **pasivo por país**, no ingreso (§3.3) | 0; Stripe `total_details.amount_tax` |
| `ingresos_sin_impuesto` | `ingresos_brutos − impuestos` | derivado |
| `reembolsos` | Σ reembolso − su parte de impuesto, **devengado en la cohorte del pedido**; provisional hasta madurez | 0 vs `balance_transactions` tipo refund |
| `ingresos_netos` | `ingresos_sin_impuesto − reembolsos` (provisional) | derivado |
| `comisiones` | Σ `fee` de `balance_transactions` (cargo, conversión, Stripe Tax); **no se revierte al reembolsar**; `tarifas_disputa` (15 USD en tarjeta) y `disputas_perdidas` aparte | 0 |
| `aov` | `ingresos_brutos / compras` (con impuesto; **igual a `economia.aov` y `engine.factibilidad`**). `aov_neto = ingresos_sin_impuesto / compras` | derivado |
| `tasa_bump`, `tasa_upsell` | Compras con bump / compras; sesiones hijas pagadas / sesiones raíz | ▲ si < `economia.tasa_bump_bp` (1000 = 10 %); gris bajo M-ped |
| `tasa_reembolso` | Pedidos con reembolso / compras, **solo cohortes maduras** (§1.6) | ▲ ≥ `salud_operativa.reembolsos_alerta_pct` (8), ■ ≥ `reembolsos_pausa_pct` (12); gris con `n <` `reembolsos_n_min` (20); en amarillo-A, un escalón menos |
| `tasa_disputa` | (disputas + alertas tempranas de fraude) / compras, ventana `disputas_ventana_dias` (30) | ▲ ≥ `disputas_alerta_pct` (0,3 %) o `casos ≥ disputas_casos_alerta` (2); ■ ≥ `limites.ratio_disputas_pausa` (fracción) o casos ≥ `disputas_casos_pausa` (3); el % exige `n ≥ disputas_muestra_min_pagos` (50), los **casos** disparan sin muestra |
| `exposicion_disputas` | Σ neto de pagos de los últimos `limites.reserva_dias_stripe` días (120; clave **inexistente**, §9) | Informativo, por macro-nicho: pausar el gasto **no detiene el contador** |

### 1.5 Rentabilidad y eficiencia

| `kpi_id` | Definición y fórmula | Semáforo (claves) y mínimo |
|---|---|---|
| `contribucion`, `mc` | `ingresos_brutos − impuestos − reembolsos − comisiones − tarifas_disputa − disputas_perdidas − costo_var`; `mc = contribucion / compras` | Base de `cpa_be` real (F1 `economia_real`) |
| `resultado_operativo` (etiqueta «Beneficio») | Fórmula de `pnl`: `ingresos_brutos − impuestos − reembolsos − comisiones − tarifas_disputa − disputas_perdidas − gasto_meta − costo_ia − otros_costos` (`costo_var` y fijos prorrateados van en `otros_costos`) = `pnl.json` ±0,01 | ● > 0 con M-ped; **provisional** con cohortes inmaduras |
| `cpa` | `gasto_meta_efectivo / compras con adid`, con IC 90 % de Poisson; < 10 compras: «evidencia insuficiente» (F1) | Ver banda abajo |
| `cpa_visto` | `gasto_meta / compras con adid`: lo que muestra Ads Manager; se compara con `cpa_obj` y `cpa_be_visto` | Color de la oferta |
| `cpa_mezclado` | `gasto_meta_efectivo / todas las compras` (con y sin `adid`) | ▲ si difiere > 25 % de `cpa` (tracking) |
| `cpa_neto` | `gasto / compras netas de cohorte madura` (D8: insumo de VALIDADA, 5.9) | Lo emite D8 en `veredicto_oferta`; F2 lo muestra |
| `cpa_be`, `cpa_be_visto`, `cpa_obj`, `roas_be` | De `economia.json` (D3, **supuesto**) y de `economia_real.json` (F1, **realizado**): `cpa_be = mc`; `cpa_be_visto = cpa_be × 10000 / (10000 + tarifa_meta_bp)`; `cpa_obj = economia.factor_cpa_objetivo (0,6) × cpa_be_visto`; `roas_be = aov / cpa_be` | Referencias; F1 usa además `cpa_obj_efectivo = 0,6 × cpa_be` para la calculadora |
| `roas_stripe` | `ingresos_brutos con adid / gasto_meta_efectivo` (comparable con `roas_be`) | vs `roas_be` |
| `roas_neto` | `contribucion / gasto_meta_efectivo` (= `pnl.kpis.roas_neto`); CPA ≤ f·`cpa_be` ⇔ `roas_neto ≥ 1/f` | ● ≥ 1/f, ▲ ≥ 1, ■ < 1 |
| `roas_meta` | `omni_purchase_values / gasto_meta` por ventana | «Meta reporta»; nunca decide |
| `mer`, `mer_neto`, `mer_be` | `ingresos_sin_impuesto / gasto_meta_efectivo` (todos los pedidos); `ingresos_netos / gasto` en 7 d por `locale` (D8); `mer_be = ingresos_sin_impuesto / (ingresos_sin_impuesto − reembolsos − comisiones − tarifas_disputa − disputas_perdidas − costo_var)` (= `neto/mc` por pedido) | ● ≥ `dashboard.mer_verde_factor` (1,2) × `mer_be`; ▲ ≥ `mer_be`; ■ < `mer_be` |
| `cac` | `gasto_meta_efectivo / compradores nuevos` (primer pedido por `email_hmac` y oferta) | Difiere de `cpa` solo con recompra o correos repetidos |
| `payback_caja_dias` | Días desde el primer gasto hasta que Σ neto liquidado disponible ≥ Σ gasto Meta pagado; incluye `finanzas.payout_lag_dias` (14, luego medido) | Insumo de `capital.json`; ▲ si > `limites.dias_cobertura_caja` |
| `cac_payback_ratio` | `cpa / mc`: ≤ 1 = el primer pedido paga su adquisición | Mismas bandas que `cpa` |
| `rpc_enlace`, `margen_por_clic` | `ingresos_netos / clics_enlace`; `conv_clic_compra × mc − cpc_enlace × (1 + tarifa_meta)` (docs/08 §7) | Por país: gris bajo `mercados.clics_min_decidir_mercado` (2.400) |
| `ltv_30d` | `ingresos_netos de la cohorte a 30 d / compradores`; hasta que exista recompra ≈ `aov_neto` | Diferido (D9) |
| `costo_ia`, `costo_ia_pct` | Σ `costos.jsonl` imputado; `costo_ia / ingresos_sin_impuesto` | ▲ > `dashboard.costo_ia_max_pct` (15 %) |

**Banda del `cpa`** (alineada con D8: matar solo con evidencia, escalar con `cpa ≤ cpa_obj`): se evalúa `cpa_visto` contra `cpa_obj` y `cpa_be_visto`. Orden: (1) M-ped o M-gasto no cumplidos ⇒ **gris**; (2) el IC 90 % **cruza `cpa_be_visto`** ⇒ gris «no concluyente»; (3) `cpa_visto ≤ cpa_obj` ● ; (4) `≤ cpa_be_visto` ▲ (rentable por debajo del objetivo: D8 mantiene); (5) `> cpa_be_visto` ■.

### 1.6 Calidad de la medición y del dato

| `kpi_id` | Definición | Semáforo y tolerancia |
|---|---|---|
| `ratio_recon` | `compras_meta (1d_click) / compras con adid y consent_marketing = 1`, ventana `testeo.razon_ventana_dias` (7 d, sin los últimos 2 días) | Rango `testeo.razon_meta_stripe_min/max` (0,8-1,3); gris si compras < `testeo.razon_n_min` (10); ■ tras `testeo.chequeos_rojos_g8` (2) lecturas seguidas fuera de rango |
| `cobertura_atrib` | Compras con `adid` válido / compras | ▲ < `dashboard.cobertura_atribucion_min_pct` (70); D8 exige `testeo.cobertura_adid_min_pct` (90) para decidir (dos hogares: §8, C-07) |
| `emq`, `tasa_dedupe` | Calidad de coincidencia del evento Purchase; % deduplicado (dataset) | ▲ EMQ < 6 `[HIPÓTESIS]` (clave inexistente, §9) |
| `frescura_fuente` | Ahora − última carga correcta, por fuente | Tabla de §6.2 |
| `prob_mejor` | P(θᵢ = máx θⱼ), Beta(1+compras, 1+clics−compras), 20.000 sorteos, semilla fija | «No concluyente» si máx < 0,8 o clics < mínimo |
| `cuota_amarilla_pct` | Gasto en ofertas amarillas / gasto total | vs `limites.cuota_gasto_amarillo_max_pct` (clave inexistente ⇒ gris) |
| `pct_cifras_conciliadas`, `latencia_dato_p95` | Cifras con conciliación `CONCILIADO` / total; p95 de (ahora − dato) | Metas de F2 (§6.3) |

**Madurez** (R12): una cohorte es madura cuando su edad supera `limites.politica_reembolso_dias + veredicto.madurez_dias_extra` (7); las disputas maduran aparte (`salud_operativa.disputas_madurez_dias`, 60; exposición real de 120 d). Todo KPI de reembolsos, disputas y `cpa_neto` sobre cohortes jóvenes es `provisional`.

### 1.7 Tolerancias de discrepancia (resumen)

| Par comparado | Tolerancia | Si falla |
|---|---|---|
| Σ pedidos/comisiones del día vs `balance_transactions` por tipo | `dashboard.recon_tol_stripe_balance` = 0 unidades menores | `DESCUADRE`: cifras tachadas |
| Dashboard vs `pnl.json` vs ledger | ±0,01 USD (F1 «al centavo» sin redondeos intermedios) | Alerta; no se promedia |
| `gasto_meta` vs reconsulta de 3 anuncios (semilla registrada) | `recon_tol_gasto_meta_pct` (1 %), días maduros | Alerta amarilla |
| `cpa`/`roas` vs `kpis` de D8 | 0 en igual ventana; si difieren, **alerta** (C15) | Gana la fuente con su definición, nunca un promedio |
| Radar: conteos del HTML vs `banco.json` vs `problemas/` | 0 | Bloqueante de QA |

## 2. Modelo de datos

### 2.1 Tablas: migradas (0001) frente a objetivo

Claves y nombres: **manda `datos/migraciones/`**; lo demás es objetivo (docs/06 §4.8, F2 §3.3) y se pide como migración 0002+ al dueño de `datos` (§9).

| Tabla | PK | Estado | Brecha o decisión |
|---|---|---|---|
| `stripe_evento` | `event_id`; `UNIQUE(tipo, objeto_id)` | migrada | Solo 3 tipos: faltan `async_payment_succeeded/failed`, `expired`, `charge.dispute.closed`, `payout.*` y alertas tempranas (los destinos reales los suscriben: `infra/plantillas/stripe-eventos-webhook.yaml`, fuente única). Un `UNIQUE(tipo, objeto_id)` descarta una segunda actualización del mismo objeto: el estado vigente lo fija el backfill |
| `fact_pedido` | `checkout_session_id` (**es el `order_id`**; no existe otro) | migrada, **incompleta** | Tiene `monto_minor` (= `amount_total`), `moneda`, `adid`, `visitor_id`, `consent_marketing`, `es_prueba`, `es_interna`, `estado` (= `payment_status` crudo). **Faltan** `cid`, `asid`, `impuesto_minor`, `fee_minor`, `liquidado_minor`, `moneda_liq`, `tipo_cambio_id`, `metodo`, `pais`, `bump_tomado`, `parent_session_id`, `email_hmac`, `pagado_en`, `dia_cuenta`. `dia_utc` es de creación, no de pago |
| `fact_reembolso`, `fact_disputa` | `stripe_refund_id`, `dispute_id` | migradas | Faltan estado de la disputa final, `due_by`, alertas tempranas y el impuesto del reembolso (necesario para `reembolsos` sin IVA) |
| `fact_meta_ad_dia` | `(ad_id, fecha)` | migrada, **con una brecha de regla** | Tiene `compras_meta` **sin `ventana`** y sin `lpv`: contradice «jamás se suman ventanas». Objetivo: `fact_meta_conv(ad_id, fecha, ventana)` aparte, y `lpv`, `pull_ts` |
| `raw_meta_insight` | `(ad_id, fecha)` | migrada | Objetivo `raw_meta_insights(pull_id)` **append-only** con hash (reproceso auditable); la PK actual sobrescribe |
| `fact_evento_tracking` | `event_id` | migrada | docs/06 la llama `fact_evento` y agrega `cid`, `asid`, `tipo`, `fuente`, `consentimiento`, `valor_minor`: unificar nombre (§9) |
| `dim_oferta`, `dim_campana`, `dim_conjunto`, `dim_anuncio` | `oferta_id`; `campaign_id`; `adset_id`; `ad_id` | **objetivo** | `dim_oferta`: `familia_id`, `variante_de`, `locale`, `moneda_cobro`, `paises[]`, `macro_nicho`, `nivel_riesgo`, `problema_id`, `nicho_id`; `dim_anuncio`: `ad_name`, `concepto_id`, `hook_id`, `formato`, `version` (el nombre se parsea de 5.2 solo para etiquetar) |
| `fact_balance_tx`, `fact_payout`, `tipo_cambio` | `balance_transaction_id`; `payout_id`; `(par, fecha)` | objetivo | `tipo_cambio` espeja `tipos_cambio.jsonl` de F1 (id `TC-…`, hash) |
| `fact_costo`, `fact_decision`, `fact_estado_oferta`, `fact_conexion`, `fact_qa`, `fact_entrega` | `costo_id`, `decision_id`, `(oferta_id, etapa, ts)`… | objetivo | De `costos.jsonl`, `decisiones.jsonl`, `estado.json`, `infra/estado.json`, `qa/*.json`, `entregas.jsonl` |
| Radar: `dim_problema`, `fact_senal_agg`, `fact_barrido`, `fact_candidato` | `problema_id`; `(problema_id, familia_senal, fuente_id, fecha)`; `barrido_id`; `(oferta_id, problema_id)` | objetivo | **Solo conteos, fechas e IDs**, jamás el texto de las señales |

### 2.2 Claves y uniones

```
dim_oferta ─1:N─ dim_campana ─1:N─ dim_conjunto ─1:N─ dim_anuncio(ad_id)
     │ oferta_id                                      │ ad_id
     │                                  fact_meta_ad_dia(ad_id, fecha)  ── fact_meta_conv(.., ventana)
     └─ oferta_id + adid ───────────── fact_pedido(checkout_session_id) ─┬─ fact_reembolso / fact_disputa (session_id)
              familia_id · locale · macro_nicho (vía dim_oferta)         ├─ fact_entrega · fact_balance_tx
              problema_id → dim_problema (radar)                         └─ fact_evento_tracking (visitor_id = client_reference_id)
```

| Unión | Clave | Regla |
|---|---|---|
| Meta ↔ Stripe | `oferta_id` + `adid` (= `ad_id`) | Nunca por nombre; las macros de nombre se congelan al publicar. `adid = 'desconocido'` cuenta en `cobertura_atrib`, no se prorratea (D8 G4) |
| Pedido ↔ sesión de landing | `client_reference_id = visitor_id` | Une el Worker propio con Stripe; `email_hmac` (HMAC-SHA256) es el único identificador de persona |
| Upsell | `parent_session_id` | Una venta con hijas se mide en la raíz |
| Familia / mercado / macro-nicho | `dim_oferta` | Σ familias = Σ mercados = Σ macro-nichos = consolidado (F1-05) |
| Día | `dia_cuenta` = `dia_de_cuenta(ts, tz)` | Meta guarda `tz` por fila; el pedido debe guardar `dia_cuenta` calculado con la misma zona |

**Regla anti *fan-out***: antes de unir hechos de granos distintos, **agregar cada lado a `(oferta_id, ad_id, dia_cuenta)`**; unir pedidos con `fact_meta_ad_dia` por fila multiplica ingresos (defecto sembrado D3). Σ pedidos tras cualquier unión = pedidos de origen (C7).

### 2.3 Almacenamiento y retención

| Etapa | Almacén | Notas |
|---|---|---|
| Desarrollo, B0, primer testeo | **SQLite** (`empresa/datos/fabrica.db` por defecto en `datos.etl_stripe`; en producción, volumen de Railway del servicio `motor`, una réplica) | Migraciones idénticas; `?` como marcador. El nombre `dashboard.sqlite` de F2 se retira (§8, C-09) |
| Desde N3 o con >1 escritor / app con login | **Postgres de Railway**, red privada, controlador `pg8000` `[VERIFICAR en Python 3.15]` | `datos.db.traducir_marcadores`; respaldo `pg_dump` cifrado diario a R2, restauración mensual (D0, R-02) |
| Archivos | `kpi_oferta_dia.json`, `kpi_blended_dia.json`, `pnl.json`, `conciliacion/`, `alertas.jsonl`, `latido_f2.json` | Exportación derivada; la base es la fuente |

Retención: `raw_*` y `stripe_evento` append-only con hash; datos de compradores de ofertas sensibles acotados con X1 `[VERIFICAR inv. 05, 21]`; sin IP ni user-agent en la base.

### 2.4 ETL

| Job | Fuente | Frecuencia (clave) | Idempotencia | Reproceso / backfill | Módulo |
|---|---|---|---|---|---|
| Insights de Meta | API (`level=ad`, `time_increment=1`), token solo `ads_read` `[VERIFICAR]`; **MCP solo hasta N2** (5.5) | `dashboard.etl_meta_cada_h` (3 h) | upsert `(ad_id, fecha)` y `(ad_id, fecha, ventana)`; `pull_ts` | **Siempre** relee `meta_ventana_reproceso_dias` (7 d); `--desde/--hasta` para huecos | `datos.etl_meta` (no existe) |
| Entidades y salud de Meta | `ads_get_ad_entities`, `ads_get_ad_accounts`, `ads_get_errors`, dataset | cada pull | upsert por ID | — | ídem |
| Stripe en tiempo real | Webhook destino `finanzas` (firma verificada) | continuo | `event.id` y `(tipo, objeto_id)` únicos | Reenvío del panel 15 d / CLI 30 d `[VERIFICAR]` | `datos.etl_stripe` (existe; fixture) |
| Stripe backfill | `balance_transactions`, `payouts`, relectura de objetos | diario a `dashboard.etl_stripe_backfill_hora` (03:00 UTC), por cursor `created` | upsert por ID; **la relectura del objeto es el estado final** (el orden de eventos no está garantizado) | Reporting API en el cierre mensual (CSV en unidades mayores) | `datos.etl_stripe` |
| Tracking propio | `POST /ingesta/evento` (HMAC + ventana de tiempo) | continuo | `ON CONFLICT(event_id) DO NOTHING`; mismo id con otro contenido ⇒ 409 | — | `datos.manejar_ingesta_evento` |
| Costos, decisiones, tipo de cambio | `costos.jsonl`, `decisiones.jsonl`, `tipos_cambio.jsonl` (F1) | cada corrida / diario | `costo_id`, `decision_id`, `(par, fecha)` (mismo id con otra tasa ⇒ error) | Se reconstruyen desde el JSONL | `datos.ledger`/`datos.kpi` |
| Radar (D1) | `empresa/descubrimiento/` | tras cada barrido + semanal | `problema_id`, `barrido_id` | Solo conteos | `datos.kpi` |

Hasta N2 el pull de Meta es de una **sesión del dueño** (no hay credenciales desatendidas): la frescura de Meta será amarilla/roja entre pulls y **el tablero debe mostrarlo sin disimular**.

### 2.5 Reconciliación Meta frente a Stripe

**Por qué difieren** (04-meta-ads §3.4; confianza A en lo oficial, el resto `[NUEVO]`) y qué hacemos:

| Causa | Efecto | Tratamiento en los KPIs |
|---|---|---|
| Atribución por personas y entre dispositivos; **1d de visualización** sin clic | Meta > Stripe | `ratio_recon` usa `1d_click`; `1d_view` solo informativo |
| Ventanas, modelado de conversiones y «fecha de conversión» vs «de exposición» | Diferencias de día | Ventana de 7 d que **excluye los últimos 2 días** |
| UE/UK sin consentimiento: píxel y CAPI no envían | Meta < Stripe | Denominador solo con `consent_marketing = 1`; los demás cuentan en ingresos |
| Bloqueadores, `adid` perdido, doble disparo, falta de deduplicación | ± | `cobertura_atrib`, `tasa_dedupe`, `event_id = purchase_<session_id>` |
| Reembolsos, contracargos, pagos asíncronos pendientes o fallidos | Meta no revierte | Stripe es la verdad; `pendientes_asincronos` aparte |
| Zona horaria; pedidos de prueba/internos; valor mal enviado | Días o importes desplazados | `dia_cuenta`; `livemode=false` e `interno` fuera; el valor de Meta no entra al P&L |

**Cuatro conciliaciones diarias** (contrato `conciliacion`; todo estado ≠ `CONCILIADO` **tacha las cifras**): (1) pedidos Stripe = `balance_transactions` (tol. 0) y `saldo + Σ net − payouts = saldo final`; (2) gasto Meta = insights (1 %) y tarifa de ubicación = factura; (3) atribución: `ratio_recon` y `cobertura_adid_bp`; (4) dashboard = `pnl.json` (F1-07/C15) y `cpa`/`roas` = `kpis` de D8. Estados: `INCOMPLETO` si falta Meta o Stripe (las diferencias no concluyen).

## 3. Multimoneda e impuestos

### 3.1 Cuatro monedas distintas

| Moneda | Qué es | Valor / fuente |
|---|---|---|
| **De cobro** | La que ve el cliente, por oferta (`mercado.moneda_cobro`; el precio por moneda vive en `checkout.precios_por_moneda[]` (D5); `mercado.monedas_precio_adicionales[]` solo lista las monedas extra) | EUR, PLN, USD… La carga de Stripe queda en esta moneda |
| **De liquidación** | La del saldo de Stripe de la LLC | **USD** `[DUEÑO]`; `balance_transaction.amount/net/exchange_rate` |
| **De la cuenta de Meta** | La del gasto y de `limites.moneda_limites` | `[VERIFICAR]`: el conector no la devuelve (C02 de contratos); si ≠ USD hace falta `tipo_cambio_id` |
| **Base / de presentación** | Agregados, blended y P&L | **USD**; vistas por mercado: moneda de cobro **más** equivalente USD; formato numérico por `locale`; interfaz en español |

### 3.2 Reglas

- **Cobros:** el USD sale del **neto liquidado de `balance_tx`** (`liquidado_minor`, tasa de Stripe); no se reconvierte con una tabla propia. Gasto de Meta y costos en otra moneda: `tipo_cambio_id` (`TC-BASECOT-AAAAMMDD`) **de la fecha del hecho**, nunca la de hoy; una línea sin `tipo_cambio_id` es `gris` («sin tipo de cambio») y D8 queda BLOQUEADO. La diferencia de cambio (tasa del cargo vs de la liquidación) va **aparte**.
- **Redondeo:** half-even, por exponente ISO 4217 (JPY/CLP = 0). Ojo: Meta usa **su propio offset** para presupuestos (offset 1 en CLP, COP, HUF, JPY…; `meta.monedas.a_unidad_meta`); el `spend` de insights viene en unidades estándar `[VERIFICAR con una lectura real]`.
- **Salto de FX:** variación > 5 %/día entre tasas consecutivas del mismo par ⇒ alerta de cordura `[HIPÓTESIS]` (clave `dashboard.fx_salto_max_pct`, inexistente).
- **Precios multimoneda:** con *Adaptive Pricing* el importe no es el de lista (el cliente paga 2-4 % más); el `aov` se compara solo dentro de una moneda de cobro o en USD con el FX del día.

### 3.3 IVA como pasivo (no es ingreso ni caja libre)

`ingresos_brutos` incluye el impuesto; `impuestos` = Σ `amount_tax` − reembolsado, **por país**, y se resta antes de cualquier margen. En modo `sin_tax` el IVA implícito es `cobrado × t / (1 + t)` (pasivo contingente, solo con `exposicion_aceptada` firmada); con *Managed Payments* Stripe remite el IVA y cobra +3,5 % `[VERIFICAR]`. El dashboard muestra «pasivo de IVA por país» junto a «reservas» y **fuera de `caja_libre`**; el export trimestral para el contador es de F1.

**Ejemplo numérico `[HIPÓTESIS: tasa 3,72 PLN/USD de F1]`:** una compra de 49 zł con IVA 23 % ⇒ cobrado 13,17 USD; IVA = 49 × 0,23 / 1,23 = 9,16 zł = 2,46 USD (pasivo); `ingresos_sin_impuesto` = 10,71 USD. En producción el USD lo fija `balance_tx`, no esta tasa.

## 4. Vistas del dashboard

### 4.1 Inventario

Todas muestran, en cada cifra, **fuente, ventana, estado del dato y `actualizado_en`**; las cifras de Meta llevan «Meta reporta» y las de Stripe «Stripe confirma».

| Vista | Pregunta que responde | Contenido clave | Ejes |
|---|---|---|---|
| **Centro de control** (blended) | ¿Gano o pierdo hoy? ¿Qué espera mi decisión? | Hoy en USD (ingresos, comisión, gasto, IA, `resultado_operativo`, `mer` vs `mer_be`), payout pendiente, gasto vs tope, pérdida acumulada vs `perdida_neta_acumulada_max`, cola de decisiones, mini-radar, conexiones, botón | Empresa; por mercado y macro-nicho resumido |
| **Oferta** | ¿Esta oferta cumple su economía? | Economía vs `cpa_be`/`cpa_obj` (D3 y realizado), embudo, creativos (`prob_mejor`), estructura, métodos de pago, reembolsos/disputas, conexiones, decisiones de D8, QA, veredicto (5.9) | `oferta_id` |
| **Familia** | ¿Qué hermana rinde y expandir? | Ofertas hermanas vs la madre (`variante_de`): `cpa`, `tasa_compra_ic`, `tasa_reembolso`, `mer` | `familia_id` |
| **Mercado/idioma** | ¿Sirve este mercado y este método de pago? | Gasto, compras, `cpa`, mix de métodos y su conversión, reembolso y disputa por método, IVA y comisión reales vs D3, exposición país × nivel; gris «direccional» bajo `clics_min_decidir_mercado` | `locale`, `pais`, `metodo` |
| **Macro-nicho** | ¿Cuánto riesgo de cuenta llevo? | Gasto amarillo vs cuota, disputas/reembolsos con **exposición abierta de 120 d**, avisos de Stripe, rechazos de Meta, hojas pausadas | salud · relaciones · dinero × verde/amarillo-A/B |
| **Pipeline** | ¿Dónde está cada oferta y qué espera? | Etapas D1→D10 por oferta (`estado.json`): estado, gate pendiente, nivel, ronda de QA, edad en la etapa, `obsoleta`; costo IA acumulado; ediciones humanas | `oferta_id × etapa` |
| **Radar de problemas** | ¿Qué conviene lanzar y cuánta evidencia fresca hay? | §4.3 | `macro_nicho × nicho_id × locale` |
| **Salud de conexiones** | ¿Puedo gastar? | Semáforo de `empresa/infra/estado.json` por bloque (ítems M-, S-, C-, R-, G-, E-, L-, K-, P-): tokens, cuenta de Meta, EMQ/dedupe, webhooks, ETL, respaldo; **sin VERDE con < 6 h nadie gasta** | componente |
| **Alertas** | ¿Qué pide acción ahora? | §5, con causa, acción sugerida, responsable y estado | regla × objeto |
| **Costos de agentes** | ¿Cuánto cuesta operar? | `costo_ia` por oferta, etapa/agente y barrido de D1; corrida vs `limites.max_budget_por_corrida_agente`; créditos vs `creditos_max_oferta`; `costo_ia_pct`; costo por oferta validada; imputación directa/familia/`empresa` | `oferta_id`, etapa, agente |

### 4.2 Wireframes (los de Centro y Oferta viven en F2 §4 con las correcciones de §8)

**Mercado / método de pago**
```
┌ MERCADO pl-PL · PLN (equiv. USD) · 1 oferta · clics 1.900 (< 2.400: DIRECCIONAL ○) ───────────┐
│ Gasto 112 USD · Compras 7 · cpa 16.0 ▲ · comisión efectiva 3.1 % (D3 supuso 2.4 %) ▲           │
│ MÉTODO     compras  mix    conv. checkout  reembolso  disputa     IVA 23 % pasivo: 31.2 USD     │
│ BLIK         3     43 %      31 %           0/3       sin tarifa   exposición 120 d: 84 USD      │
│ Tarjeta      4     57 %      22 %           1/4       0            Meta: sin tarifa de ubicación │
└ BLIK ≥ 30 % de compras polacas ⇒ relevante (08); < 30 % ⇒ hipótesis refutada. n pequeño: gris ─┘
```
**Pipeline**
```
OFERTA        locale macro   D1  M1  D2  D3  D4  D5  D6  D7  D8   gate pendiente · edad · costo IA
OF-202611-01  it-IT  dinero  ✔   ✔   ✔   ✔   ✔   ✔   ✔   ✔   ▶    — · día 5 · 41 USD
OF-202611-02  pl-PL  relac.  ✔   ✔   ✔   ⏸H  ·   ·   ·   ·   ·    D3 firma · 2 d · 12 USD
OF-202611-03  it-IT  salud   ✔   ✔   ▶   ·   ·   ·   ·   ·   ·    — · 1 d · 6 USD
✔ aprobada · ▶ en curso/QA · ⏸H esperando al dueño · ✖ bloqueada/obsoleta (hover: causa y hash)
```
**Conexiones y alertas**
```
CONEXIONES (estado.json 14:00, vigente 4 h)   ● Meta M-01..10  ● Stripe S-01..08  ● Cloudflare  ● Railway
 ▲ CAPI EMQ 5.8 (< 6)   ▲ ETL Meta hace 7 h (amarillo ≥ 6 h)   ○ Railway respaldo sin datos
ALERTAS ABIERTAS (3)  ■ F2-A06 razón Meta/Stripe 0.55 (2 lecturas) → D8 modo ciego · dueño: revisar CAPI
                      ▲ F2-A07 cobertura de adid 62 % < 70 %      ▲ F2-A15 relaciones 0 % bajo cuota 20 %
```

### 4.3 Radar de problemas (D1) `[SUPUESTO: pendiente de d1-v2-interfaces.md]`

Fuente: `empresa/descubrimiento/{banco.json, problemas/, barridos/}` y `costos.jsonl`; solo conteos, fechas e IDs (el texto de señales no entra a la base ni al LLM de F2). Claves de D1 existentes: `descubrimiento.caducidad_banco_dias` (90), `antiguedad_max_evidencia_meses` (18), `cuota_min_exploracion_por_macro_nicho_pct` (20), `limites.max_costo_por_barrido`, `locales_permitidos`, `macro_nichos_permitidos`.

| `kpi_id` (por `macro_nicho · nicho_id · locale`) | Definición | Semáforo |
|---|---|---|
| `radar_banco_n` | Problemas por estado del banco | Informativo |
| `radar_vigentes_n` | Problemas con evidencia refrescada dentro de `caducidad_banco_dias` y señales dentro de `antiguedad_max_evidencia_meses` | ■ si 0 en el total: **botón deshabilitado** |
| `radar_ficha_completa_pct` | Con prueba de una frase + MU + EU completos (5.11) | ▲ < 100 % entre candidatos |
| `radar_edad_evidencia_med_dias`, `radar_evidencia_vencida_pct` | Mediana de edad de la señal más reciente; vencidas / total | Una vencida **nunca** cuenta como vigente |
| `radar_cobertura_locale` | `locales_permitidos` con barrido en ventana / permitidos | ▲ < 100 % |
| `radar_cuota_macro_pct` | Esfuerzo (barridos o gasto de barrido) por macro-nicho / total | ▲ < `cuota_min_exploracion…` (20) |
| `radar_senales_descartadas_pct`, `radar_rechazos_motivo` | Por `fuente_id`; conteo por los 10 motivos canónicos de 5.11 (`sin_mecanismo`, `multi_mecanismo`, `fuera_de_macro_nicho`, `claim_de_salud_o_ingresos`…) | Fuentes ruidosas o filtros mal calibrados |
| `radar_costo_barrido`, `radar_costo_por_candidato` | Costo de un barrido; Σ costos de barrido del período / candidatos que llegan a vigentes | ■ si un barrido > `limites.max_costo_por_barrido` |
| `radar_verdes_topn_pct`, `radar_topn_estable_pct` | % de nivel verde en el top-N; estabilidad del top-1 bajo sensibilidad | Informativo |
| `radar_rendimiento_nicho_fuente` | Problemas → elegidos → pasan D2 → ofertas VALIDADAS (5.9), por nicho y `fuente_id`; señales propias (D8/D10) devueltas al banco | **Muestra conteos observados**; la estimación suavizada la calcula X2 (`rendimiento_radar`); gris con n < `memoria.n_min_rendimiento` (pedido) |

**Wireframe del Radar**
```
RADAR · último barrido 05-nov (costo 7 / tope 10 USD) · 14 vigentes · evidencia mediana 21 d · cobertura locale 3/4
          │ it-IT              │ pl-PL              │ en-GB            │ es-MX
 DINERO   │ 5 · 18 d · 3 USD   │ 3 · 40 d ▲         │ sin barrido ○    │ 2 · 55 d ▲
 RELAC.   │ 0 ▲ bajo cuota     │ 2 · 25 d · 4 USD   │ 1 · 30 d         │ gris (n<3) ○
 SALUD    │ 4 · 12 d · 5 USD   │ gris (n<3) ○       │ 0                │ 0
 celda = vigentes · edad mediana de evidencia · costo por candidato  |  cuota: dinero 50 % · relac. 14 % ▲ · salud 36 %
 RENDIMIENTO (n visible): nicho X: 6 problemas → 2 elegidos → 1 pasa D2 → 0 validadas (n pequeño ○)   fuente reddit: 31 % descartadas
```

### 4.4 El botón «Lanzar nueva oferta»

Contrato de flujo (F2 §4, backbone 3.2): clic → O0 pide a D1 los mejores problemas **del banco** con evidencia refrescada (no investiga desde cero) → M1 los empareja con `locale` y mercados → el **selector top-N** los muestra → el dueño elige (`accion:elegir_candidato`, H hasta N3, firma Ed25519 con `orq firmar`, no del dashboard; C03 abierto) → se congela `candidatos.json` y arranca D2. Fase A: el botón **copia el comando** `python -m engine.orq crear --brief <ruta>` con un `00-brief.yaml` prellenado, y lo copia solo con el brief ya firmado (gate H, paso 3 de O0) y tras la validación en seco (paso 2); `orq crear` corre después (paso 4; `departamentos/00`). `engine/orq.py` existe con el subcomando `crear`; `POST /ofertas` no existe en `dashboard/` [PENDIENTE: lo construye S-B (B10)]. **Solo encola**; O0 re-valida límites, `PAUSA`, preflight y X1.

```
┌ LANZAR NUEVA OFERTA ── banco 14:00 · 14 vigentes · evidencia mediana 21 d · generado a partir de fuentes externas ─┐
│ Filtros: macro [dinero ▣ relaciones ▣ salud ▣]  locale [it-IT ▣ pl-PL ▣]  nivel ≤ [verde ▣ amarillo-A ▣]          │
├─ # ─ Problema (voz del cliente, inerte) ─────── Macro · Riesgo ─ Mecanismo → Entregable ─ Evidencia ── Mercado ───┤
│ 1  «no sé cómo cobrar mi primer trabajo»        dinero · verde   «plan 3 pasos» → plantilla  4 fuentes E1+E3 · 21 d  it-IT │
│    Qué lo mataría: sustituto gratuito dominante · Costo máx. en riesgo: 300 USD (de limites.yaml) · ficha 100 % · conf. media │
│ 2  «guía de reinserción tras la baja»           relaciones · verde …                                                    │
│ 3  «…»                                          salud · ROJO — visible, NO elegible (no se puede lanzar)                │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Elegir #1 y encolar ]  ◄ deshabilitado con motivo si: esquema del brief · sesión/CSRF/idempotency_key · tope de       │
│   encolados del día · PAUSA · infra no VERDE o > 6 h · ofertas en test = máx. · margen bajo perdida_neta_acumulada_max  │
│   · macro/locale/país no permitidos · 0 candidatos vigentes                                                             │
│ [ Pedir barrido dirigido ] (si 0 vigentes o un macro bajo cuota) · costo estimado ≤ max_costo_por_barrido               │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Reglas del selector: por candidato `macro_nicho`, **nivel de riesgo y reencuadre** (ningún ROJO ni amarillo-B sin gate H), problema en voz del cliente, `mecanismo.nombre` y `entregable.formato`, evidencia (n de fuentes, tipos, edad, `locale`), `confianza`, mercado sugerido (moneda, métodos habilitados), «qué lo mataría», costo máximo en riesgo y `costo_por_candidato`. El texto de D1 se muestra **escapado, truncado y rotulado**. El costo en riesgo sale de `limites.yaml`, nunca del formulario. Tope diario de encolados: clave inexistente (`boton_max_lanzamientos_dia`, §9).

## 5. Alertas y umbrales

Todo umbral se lee de `empresa/parametros.yaml` o `limites.yaml`; el código no tiene números. Clave con † = inexistente: el KPI/alerta queda **gris «sin umbral fijado»**, nunca verde. F2 **no pausa nada**: las rojas las lee O0 (que ejecuta vía D8 o X1/F1). Alertas de F1 (`F1-A01…A08`, Anexo A de F1) se muestran sin redefinir.

| ID | Condición | Umbral (clave) | Sev. | Destino y acción sugerida |
|---|---|---|---|---|
| F2-A01 | Frescura de Meta | `dashboard.frescura_meta_{amarillo,rojo}_h` (6/12) | ▲/■ | O0: relanzar pull; rojo > 24 h ⇒ F2 baja a N1 |
| F2-A02 | Frescura de eventos de Stripe (por **latido del receptor**) | `frescura_stripe_eventos_{amarillo,rojo}_h` (2/6) | ▲/■ | D0: revisar webhook |
| F2-A03 | Frescura de `balance_transactions` | `frescura_stripe_balance_{amarillo,rojo}_h` (26/36) | ▲/■ | F1: backfill |
| F2-A04 | Pedidos ≠ `balance_tx` | `recon_tol_stripe_balance` (0) | ■ | Cifra tachada; F1 investiga |
| F2-A05 | Gasto vs reconsulta de Meta | `recon_tol_gasto_meta_pct` (1) | ▲ | F1/D8 |
| F2-A06 | `ratio_recon` fuera de rango con n suficiente; ■ tras 2 lecturas | `testeo.razon_meta_stripe_{min,max}`, `razon_n_min`, `chequeos_rojos_g8` | ▲/■ | D8 (modo ciego), D5 (revisar CAPI) |
| F2-A07 | Cobertura de `adid` | `cobertura_atribucion_min_pct` (70) y `testeo.cobertura_adid_min_pct` (90) | ▲ | D5 |
| F2-A08 | Gasto del día > presupuesto × factor | `alerta_gasto_sobre_presupuesto_x` (1,75) | ■ | O0: PAUSA; D7 |
| F2-A09 | Gasto vs tope (día/test) y pérdida acumulada | `finanzas.gasto_vs_tope_{amarilla,roja}_pct`; `limites.perdida_neta_acumulada_max` | ▲/■ | O0/F1 (el guardarraíl crea `PAUSA`, no F2) |
| F2-A10 | `costo_ia_pct` o corrida sobre presupuesto | `costo_ia_max_pct` (15); `limites.max_budget_por_corrida_agente` | ▲ | O0 |
| F2-A11 | Reembolsos y disputas | `salud_operativa.*` y `limites.ratio_disputas_pausa` (F2 **cita**; define F1-A01/A02, D10) | ▲/■ | F1, D8, X1 |
| F2-A12 | Cordura de embudo/tracking (§6.1) | invariantes, sin umbral | ▲ | D5 |
| F2-A13 | EMQ bajo / dedupe | `dashboard.emq_min` † (6) | ▲ | D5 |
| F2-A14 | Cuota amarilla | `limites.cuota_gasto_amarillo_max_pct` † | ▲/■ | X1/O0 |
| F2-A15 | Radar: macro bajo cuota, evidencia vencida alta, 0 vigentes | `descubrimiento.cuota_min_exploracion_por_macro_nicho_pct` (20), `caducidad_banco_dias` (90) | ▲ | D1 (barrido dirigido) |
| F2-A16 | Conexión crítica roja o `estado.json` > 6 h | `infra`/D0 | ■ | Nadie gasta ni activa |
| F2-A17 | Latido de F2 ausente; ETL sin correr | `watchdog.latido_max_min` | ■ | O0/watchdog (F2 no avisa de su propia caída) |

**Higiene:** una alerta = `regla × objeto × ventana`, deduplicada; estados `abierta → reconocida → cerrada` (cierre automático al volver al rango); `alertas.jsonl` unificado (F1 y F2) con `id, ts, severidad, regla_id, origen, oferta_id, macro_nicho, nivel, valor, umbral, accion_sugerida, estado`; se mide `alertas_accionadas_pct` y `falsos_positivos_alerta`. No existe aún esquema `alertas` (pedido).

## 6. QA de datos

### 6.1 Cordura (L1, determinista)

Sin negativos en gasto, impresiones, clics ni compras · `ctr_enlace ≤ 100 %` · `clics_enlace ≤ impresiones` · `alcance ≤ impresiones`, `frecuencia ≥ 1` · embudo monótono (`inicios_pago ≤ vistas_landing × 1,05`; `compras ≤ inicios_pago`, salvo tracking caído, que debe **alertar**) · `reembolsos ≤ cobrado` por pedido · `compras_netas ≤ compras` · ninguna suma de monedas distintas · PK únicas, FK sin huérfanos, enteros con moneda · ETL dos veces ⇒ mismo hash de `fact_*` · sin secretos ni emails en el HTML.

### 6.2 Frescura

| Fuente | ● hasta | ▲ | ■ | Medida |
|---|---|---|---|---|
| Meta (insights) | < 6 h | 6-12 h | > 12 h | Ahora − última carga correcta |
| Eventos de Stripe | < 2 h | 2-6 h | > 6 h | Latido del receptor (no el último evento: sin ventas no hay eventos) |
| `balance_transactions` | < 26 h | 26-36 h | > 36 h | Último backfill |
| ETL/KPI de F2 | `watchdog.latido_max_min` | — | superado | `latido_f2.json` |
| `infra/estado.json` | < 6 h y VERDE | — | más viejo o no VERDE | Firma y `valido_hasta` |

Fuente en ■ ⇒ cifras `stale` con la causa; **ningún KPI `stale`, `gris` o inmaduro dispara una decisión**.

### 6.3 Casos de calibración (valores esperados; fixtures `[SINTÉTICO]` en `tests/fixtures/dashboard/`, nunca en `empresa/`)

| Caso | Entrada | Resultado esperado |
|---|---|---|
| CAL-01 vector de F1 (USD) | 10 pedidos (3 con bump), 17 + 7, bruto 191, Meta 150, `mc` 16,25, tarifa Meta 0 | `aov` 19,10 · `tasa_bump` 30 % · `cpa` 15,00 · `mer` 1,27 · `cpa_obj` 9,75 · IC 90 % ≈ 9,5-27,6 cruza `cpa_be` ⇒ **gris «no concluyente»**, no rojo |
| CAL-02 multimoneda | 3 compras de 14,90 EUR (17,28 USD liquidados), 2 de 49 PLN, 1 de 17 USD | `ingresos_brutos` = Σ `liquidado_minor`; la suma de montos de origen (44,70 + 98 + 17) es un resultado **prohibido** |
| CAL-03 `ratio_recon` | Meta 1d_click = 10; Stripe 9 pagadas, 8 con `adid`, 8 con consentimiento | 10/8 = **1,25 ●**. Con 7 consentidos: 1,43 ▲ (fuera de 0,8-1,3) |
| CAL-04 *fan-out* | Un pedido y dos anuncios del mismo día unidos sin agregar | Σ pedidos y `ingresos_brutos` sin cambio (C7) |
| CAL-05 zona | Cuenta `America/Santiago` (UTC−3 en noviembre `[VERIFICAR]`): pedidos a 2026-11-06T02:30Z y T03:30Z | Primero es **día de cuenta 11-05**, segundo **11-06**; en UTC ambos son 11-06 |
| CAL-06 reembolso parcial | 14,90 EUR, IVA 22 %, reembolso de 5,00 EUR el día 20 | `reembolsos` = 5,00 − 5 × 22/122 = **4,10 EUR**, imputado a la cohorte del pedido; la comisión no se devuelve |
| CAL-07 pago asíncrono | `completed` con `unpaid`, luego `async_payment_failed` | Nunca es compra; `pendientes_asincronos` baja |
| CAL-08 radar | 14 vigentes: dinero 8, salud 6, relaciones 0; una evidencia de 100 d con `caducidad_banco_dias` = 90 | Alerta F2-A15; ese problema **no** es vigente; el botón sigue habilitado con el macro marcado |

Dorados: ≥ 2, de distinto macro-nicho, idioma y moneda (dinero `it-IT`/EUR; relaciones `pl-PL`/PLN con BLIK). Defectos sembrados D1-D20 (incluido el webhook duplicado) y chequeos C1-C18: F2 §6. Meta: ≥ 90 % de bloqueantes sembrados detectados y 0 falsos bloqueantes en el dorado; KPIs de F2: `pct_cifras_conciliadas`, `latencia_dato_p95`, `alertas_accionadas_pct`, `falsos_positivos_alerta`, prueba de 30 s.

## 7. Seguridad y acceso

| Tema | Regla |
|---|---|
| **Credenciales** | F2 y el ETL usan tokens **de solo lectura**: Meta `ads_read` `[VERIFICAR]`, Stripe clave restringida de lectura (F2 no tiene clave de Stripe: lee la base). `deny` para `ads_create_*`, `ads_update_*`, `ads_activate_*`, `ads_boost_*`, `ads_*_delete*`, escritura de `ads_pixel_*`. Ningún secreto en HTML, logs o prompts |
| **Acceso** | Fase A: archivo local. Fase C: `dashboard.api` en Railway detrás de **Cloudflare Access con 2FA** `[VERIFICAR]`; sesión corta, CSRF, `idempotency_key`; rol de base de datos de solo lectura. Un artefacto de claude.ai solo con **agregados** `[DUEÑO]` |
| **Datos personales** | Sin email en claro: solo `email_hmac` (clave aparte); sin IP ni user-agent; retención acotada con X1; ofertas sensibles (duelo, deuda, ruptura, salud) se nombran por `oferta_id` y `slug` neutros, nunca por producto |
| **Texto no confiable** | UTM, nombres de campaña/anuncio, `metadata`, extractos de señales y fichas de D1 pueden traer `<script>` o instrucciones: **escape total, CSP, truncado y rótulo**; el agente lector recibe **solo números e IDs** (prueba con fixtures hostiles en `utm_content` y en un extracto) |
| **Integridad y disponibilidad** | Scripts de ETL/KPI fijados por hash tras QA + H; `raw_*` append-only con hash; `pg_dump` diario a R2 con restauración mensual probada; si Meta o Stripe caen, las cifras se marcan, no se inventan |
| **Botón** | Defensas de §4.4; la firma H **no** es del dashboard; el motor re-valida todo; doble POST ⇒ una cola |

## 8. Registro de conflictos resueltos y ediciones aplicadas

Regla aplicada: **contrato/código > F1/F2 > este documento donde ya hay norma**; el resto se alinea aquí. «Ed.» = edición quirúrgica realizada en F1 o F2.

| ID | Conflicto | Resolución | Ed. |
|---|---|---|---|
| C-01 | F2 definía `ingresos_brutos` **sin** impuesto; F1 y el esquema `pnl` (`resultado = ingresos_brutos − impuestos − …`) lo definen **con** impuesto | Manda `pnl`: `ingresos_brutos` con impuesto; nuevo `ingresos_sin_impuesto` | F2 |
| C-02 | `aov`: F1 lo definía neto de impuesto; `engine.factibilidad` y `economia.aov` = **bruto** (`P + b·Pb + u·Pu`) | Manda el código: `aov` bruto; `aov_neto` aparte | F1, F2 |
| C-03 | `cpa_obj`: F2 lo etiquetaba «break-even»; F1 = `0,6 × cpa_be`; el código = `0,6 × cpa_be_visto` | Manda el código; F1 conserva `cpa_obj_efectivo = 0,6 × cpa_be` para su calculadora (Italia: 6,96 efectivo = 6,76 visto) | F1, F2 |
| C-04 | `roas_be`: F1 `aov/mc`; código `aov/cpa_be` | Mismo valor; unificado a `aov / cpa_be` | F1 |
| C-05 | CPA: F2 `cpa_real` (todas las compras), F1 (con `adid` y gasto efectivo), D8 `cpa_neto` | Tres ids distintos con denominadores explícitos: `cpa`, `cpa_mezclado`, `cpa_neto` (§1.5) | F2 |
| C-06 | Nombres de embudo: F2 `tasa_lpv/tasa_checkout/tasa_compra` frente a D8/`parametros.testeo` `tasa_conexion/tasa_ic/tasa_compra_ic` | Manda `testeo.*` | F2 |
| C-07 | Cobertura de `adid`: `dashboard.…_min_pct` (70) frente a `testeo.cobertura_adid_min_pct` (90) | Coexisten (visual 70 / decisión de D8 90); a un hogar (pedido abierto) | — |
| C-08 | Color de `cpa`: F2 verde ≤ 0,8 × `cpa_obj` y rojo > `cpa_obj`, que marca rojo lo que D8 deja en SEGUIR | Banda de §1.5 alineada con D8, más «no concluyente» por IC | F2 |
| C-09 | F2 `dashboard.sqlite` y `fx_id` frente al código `fabrica.db` y al contrato `tipo_cambio_id` | Manda el código/contrato | F2 |
| C-10 | Estado de pedido en F2 (`pendiente/pagado/fallido`) frente al código (`payment_status` crudo) | `compras` filtra `paid`/`async_payment_succeeded` (§1.1); la normalización es de `datos` | F2 |
| C-11 | SOP 4 de F2: «el estado sale del `created`» frente a `stripe-eventos-webhook.yaml` («orden no garantizado; no usar `created` para ordenar») | La relectura del objeto en el backfill fija el estado final | F2 |
| C-12 | Alertas: F2 (`id, regla, estado`) frente a F1 (`regla_id, macro_nicho, nivel, accion_sugerida`), dos archivos | Esquema unificado y `origen` (§5) | F1, F2 |
| C-13 | Frescura de Stripe: `finanzas.datos_frescura_roja_h` (26) frente a `dashboard.frescura_stripe_balance_{amarillo,rojo}_h` (26/36) | La vista usa `dashboard.*`; `pnl.frescura.estado = stale` se declara con el rojo (36); retirar la clave de `finanzas` (pedido) | F1 |
| C-14 | Quién entrega `pedidos` a F2/D8: F1 «en `empresa/datos/`» frente a F2 (ETL de `datos`) | Un solo almacén: `fact_pedido` y `stripe_evento` en la base, escritos por `datos.etl_stripe`; F1 los lee | F1 |
| C-15 | Wireframe 2 de F2: «Stripe 9 (8 con adid, 7 con consentimiento) · ratio 1.25» no cuadra (10/7 = 1,43) | Corregido: 8 con `adid` y consentimiento ⇒ 1,25 | F2 |
| C-16 | Día de corte: el ledger guarda día UTC; F2 usa la zona de Meta; F1-08 pide ambos | P&L y dashboard agregan por `dia_cuenta`; `ledger.fecha` UTC es solo partición (a confirmar por F1) | — |
| C-17 | Hogar del radar de rendimiento: F2 lo calcula; X2 prepara `rendimiento_radar` suavizado | F2 muestra conteos y la estimación de X2 | F2 |

## 9. Pedidos, `[VERIFICAR]` y decisiones del dueño

**Pedidos a otros dueños** (en `docs/_historial/coordinacion-sesiones.md`, sin editar lo ajeno): (1) `datos/migraciones` 0002 (§2.1) y unificar `fact_evento`/`fact_evento_tracking`; (2) `kpi` MINOR: `ambito` familia/locale/macro_nicho/radar + `clave`, semáforo opcional; (3) esquema `alertas` unificado; (4) claves nuevas: `dashboard.emq_min`, `dashboard.fx_salto_max_pct`, `limites.reserva_dias_stripe`, `limites.cuota_gasto_amarillo_max_pct`, `boton_max_lanzamientos_dia`, `memoria.n_min_rendimiento`, y retirar `finanzas.datos_frescura_roja_h`; (5) D1: publicar `d1-v2-interfaces.md` (estados del banco y KPIs); (6) D8: leer pedidos de la base, no de `empresa/datos/pedidos`.

**`[VERIFICAR]`:** campos de Meta (clic en enlace, 3 s, ThruPlay, aprendizaje) con `ads_get_field_context`; unidad del `spend`; ventanas; zona y moneda de la cuenta (C02); Cloudflare Access con 2FA; reenvío de eventos de Stripe; `exchange_rate` en sandbox; retención con X1; si `amount_spent` incluye la tarifa de ubicación.

**Decisiones del dueño:** beneficio devengado (recomendado) o de caja; canales de alertas críticas (≥ 2); si acepta agregados en un artefacto; costos fijos y su prorrateo; modo fiscal por mercado; si el clic del botón vale como firma en N4 (C03); cuota del Radar por macro-nicho.
