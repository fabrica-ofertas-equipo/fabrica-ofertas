# F2 — Dashboard y BI
> Tipo: empresa · Cadencia: ETL cada `dashboard.etl_meta_cada_h` + backfill diario (hora `dashboard.etl_stripe_backfill_hora`) + conciliación diaria + cuadre mensual con F1 + lectura semanal del radar · Gate por defecto: **A en todos los niveles** (`contratos/gates.json`); H solo en las acciones de §7 · Estado de la skill: por forjar
> **v2 (2026-11-06):** backbone v2.2; vistas por oferta, familia, mercado/idioma, macro-nicho y **Radar de problemas** (D1); multimoneda; Railway (Postgres) + Cloudflare; umbrales de `empresa/parametros.yaml`. Si algo contradice un contrato o el código de `datos/` y `dashboard/`, manda el contrato/código (Anexo B).
> **v2.1 (2026-11-06):** reconciliada con F1 y con los contratos en `docs/04-datos-kpis-dashboard.md` (documento único de datos; **su §1 es ahora la fuente del glosario** y su §8 registra los conflictos C-01…C-17). El Anexo A queda como resumen.

## 1. Misión y posición en el flujo

Convertir datos dispersos (Meta, Stripe, tracking, `estado.json`, costos, banco de D1) en **una sola verdad numérica auditable** y en vistas que respondan en 30 segundos: *¿gano o pierdo plata hoy?*, *¿qué espera mi decisión?* y *¿qué problema conviene lanzar?* Principio `[NUEVO]`: **el código calcula, el LLM interpreta**: ningún KPI sale de un LLM ni de JavaScript, sino de SQL versionado o funciones Python con tests (`datos.kpi`, `dashboard.build`). Lectura pura: sin credenciales de escritura sobre Meta ni Stripe.

**Reparto con F1 `[NUEVO]`:** F1 es dueño del libro mayor, el P&L y la ingestión de Stripe; F2 **no abre una segunda línea contable**: lee `ledger.jsonl`/`pnl.json` y los **verifica** (F1-07: dashboard = P&L). F2 es dueño de Meta por anuncio, la unión con pedidos, embudo, semáforos, alertas, radar y botón. D8 decide con su propio pull: F2 lo contrasta (C15).

**Ejes de lectura** (backbone 3.1): oferta → **familia** (`familia_id`) → **mercado** (`locale` + `pais`, moneda, método de pago) → **macro-nicho** (salud · relaciones · dinero) → blended. El ejemplo del video (edición con IA) no es un nicho modelo: ninguna vista asume idioma, país o moneda.

Recibe de F1, D8, D7, D5, M1, D1, X1, D10, O0, D0 y QA (§3.1). Entrega `empresa/datos/` y `empresa/dashboard/`; KPI y alertas a O0/D8/D9/M1/X2. **Origen del botón «Lanzar nueva oferta»** hacia O0 (no ejecuta nada).

## 2. Qué dice el video (y qué no dice)

- **[VIDEO] hace:** «la cuenta real de cuántas ventas necesitás para 3.000 por mes en ganancia» y «si va bien, escalar; si no, otra oferta». **Omite:** atribución, conciliación Meta vs Stripe, reembolsos, comisiones, costo de IA, frescura, economía unitaria, cuánto invertir antes de decidir, multimoneda y mercados.
- **No tomamos tal cual:** «160 anuncios = gana plata» (la Biblioteca no da gasto ni conversiones: inv. 02); el «85/100» de Venzio; que Meta «reporta» ventas como hecho (5.3); ninguna cifra de ingresos del autor.
- **[CREADORES]** (inv. 12-13; venden cursos): un tracker externo (Utmify) porque «Meta traquea mal» *C* `[MB/xYL-griq9oI]`; contrastado con doc. 04 §3.4, Meta **mide otra cosa** (ventanas, modelado, zona horaria): lo reemplazamos por atribución por IDs + Stripe + `ratio_recon`. Un dashboard por oferta *C* `[SB/ql-YUjCh8IQ]`: coincide con nuestro diseño. Muestran facturación de Stripe o «lucro» propio *B-* (existencia de ventas, no rentabilidad): nosotros, beneficio neto de reembolsos, comisión, IA y disputas. Sus columnas (hook rate, retención, toma del OTO) *C*: diagnóstico con intervalo y «no concluyente». Sus umbrales son de Argentina/EE. UU.; **para Polonia e Italia no hay playbook**: todo umbral por mercado es `[HIPÓTESIS]` hasta tener datos propios.

## 3. Variables

### 3.1 Entradas (contrato de entrada)

| variable | tipo | origen | oblig. | ejemplo / valores |
|---|---|---|---|---|
| `meta.insights_ad_dia` | filas (ad_id, fecha, gasto, impresiones, clics_enlace, lpv; compras y valor **por `ventana`**) | `datos.etl_meta` (API, `level=ad`, `time_increment=1`) con token **solo `ads_read`** de D0 `[VERIFICAR]`; el MCP (`ads_get_ad_entities`) es diagnóstico y **solo hasta N2** (5.5) | sí | `ventana ∈ {1d_click, 7d_click, 28d_click, 1d_view}` `[VERIFICAR]`. **Las ventanas se solapan: jamás se suman** |
| `meta.entidades`, `meta.salud` | entidades (estado, presupuesto, aprendizaje); cuenta (moneda, `timezone_name`, límite, estado); dataset (EMQ, dedupe) | `ads_get_ad_entities`, `ads_get_ad_accounts`, `ads_get_errors`, `ads_get_dataset_quality/stats` o API | sí | `learning_stage` `[VERIFICAR]` |
| `stripe.eventos`, `balance_tx`, `payouts` | JSON con firma verificada; filas (monto, fee, neto, **moneda de cobro y de liquidación**) | webhook y backfill de F1 (F2 no tiene clave de Stripe) | sí | `checkout.session.completed`, `async_payment_*`, `charge.refunded`, `charge.dispute.*` |
| `f1.ledger`, `f1.pnl`, `tipo_cambio` | `ledger.jsonl`, `pnl.json`, tasas | F1 (solo lectura) | sí | F2 no define tasas |
| `track.eventos` | PageView … Purchase con `event_id` y `consent_marketing` | D5 (`tracking.json`) | sí | `purchase_<session_id>` |
| `estado.json`, `portafolio.json`, `autonomia.yaml`, `veredicto_oferta.json`, `compliance/` | etapa, gate, nivel por etapa, pausa, veredicto; rechazos de Meta, avisos de Stripe, incidentes | O0, D8, X1 | sí | «VALIDADA posible el <fecha>» |
| `mercado.json`, `atlas.json` | `locale`, `paises_segmentacion[]`, moneda, `monedas_precio_adicionales`, métodos de pago, exposición país × nivel | M1 | sí | `it-IT`, `EUR` |
| `oferta.json`, `economia.json` | ticket, bump, `cpa_obj`, `riesgo{P,C,E,N,nivel,reencuadre_aplicado}`, `macro_nicho`, `familia_id`, `variante_de` | D3 | sí | `nivel: amarillo` |
| `empresa/descubrimiento/`, `01-descubrimiento/candidatos.json` | `banco.json`, `problemas/<problema_id>.json`, `senales/` (solo conteos y fechas), `barridos/`, `nichos.yaml`; snapshot v2 con `mecanismo`, `entregable`, `riesgo`, `que_la_mataria` | D1 | sí | `PRB-202611-0042` |
| `costos.jsonl`, `registro.jsonl`, `decisiones.jsonl`, `qa/*.json`, `empresa/infra/estado.json` | costos (barridos de D1 incluidos), acciones, decisiones, informes, healthcheck | O0, D8, QA, D0 | sí | `oferta_id` o `empresa` |
| `limites.yaml`, `parametros.yaml` | techos del dueño; umbrales (§3.4) | dueño / sistema | sí | ningún umbral vive en el código |
| `moneda_base`, `zona_horaria_reporte`, `costos_fijos` | ISO 4217; IANA; lista prorrateada (`[DUEÑO]` vía F1) | **USD** (la LLC liquida en USD) `[DUEÑO]`; zona = la de la cuenta de Meta, leída de `ads_get_ad_accounts` `[VERIFICAR]` | sí | `USD` |

### 3.2 Variables de decisión

| variable | opciones | criterio | cómo se testea |
|---|---|---|---|
| `almacen` | SQLite (desarrollo, B0) → **Postgres de Railway** (producción) | `datos.db.conectar(url)` admite ambos con las mismas migraciones; Postgres con app con login o >1 escritor | misma suite en ambos |
| `salida` | HTML estático → artefacto privado → app WSGI (`dashboard.api`) en Railway tras Cloudflare | menor fricción (§4); el botón real exige app | demo por fase |
| `base_ingreso_beneficio` | devengado por cohorte vs caja | **devengado**; vista de caja/payout aparte `[DUEÑO: confirmar]` | QA recomputa ambas |
| `modo_fx` | tasa del día de la transacción vs de hoy | **día de la transacción** (inv. 03 decisión 14); en Stripe manda el **neto liquidado en USD de `balance_tx`** | D2 |
| `vista_moneda` | base vs moneda de cobro | agregados en USD; vistas por mercado en moneda de cobro **más** equivalente USD; nunca sumar monedas; interfaz en español, formato por `locale` (5.10) | D8 |
| `corte_de_dia` | zona de la cuenta de Meta vs del dueño | zona de la cuenta de Meta; Stripe recortado a ella | pedidos 23:59/00:01 |
| `modo_ranking_creativos` | CPA crudo vs bayesiana | bayesiana con «no concluyente» `[NUEVO]` | simulación sintética |

### 3.3 Salidas (contrato de salida)

| artefacto | ruta | formato | campos obligatorios | consumidor |
|---|---|---|---|---|
| Base | Postgres de Railway o `empresa/datos/fabrica.db` (SQLite; ruta por defecto de `datos.etl_stripe`) | SQL | esquema = migraciones de `datos/` (estado real y brechas: docs/04 §2.1) | scripts, QA |
| Snapshots KPI | `empresa/datos/kpi_oferta_dia.json`, `kpi_blended_dia.json` (`contratos/kpi.schema.json`, `ambito ∈ oferta, blended`); familia/mercado/macro/radar tras un MINOR de `kpi` (hasta entonces, mismas fórmulas en el HTML con el mismo `run_id`) | JSON | `generado_en, run_id, version_esquema, version_glosario, fuentes{meta, stripe_eventos, stripe_balance}, filas[kpi_id, valor, unidad, n, estado ∈ ok/gris/provisional/stale, rango, ventana]` | D8, D9, O0, M1, X2 |
| Glosario | `empresa/datos/glosario_kpi.yaml` (Anexo A) | YAML | `id, definicion, formula, fuente, granularidad, tolerancia, semaforo{clave_verde, clave_rojo}, min_datos` | dashboard, QA |
| Conciliación | `empresa/datos/conciliacion/AAAA-MM-DD.json` | JSON | pruebas, diferencias, veredicto | F1, QA |
| Latido | `empresa/datos/latido_f2.json` | JSON | `ts, run_id, resultado` (O0 y el watchdog lo vigilan: F2 no avisa de su propia caída) | O0 |
| Alertas | `empresa/datos/alertas.jsonl` (`python -m dashboard.alertas`) | JSONL | formato unificado con F1 (docs/04 §5): `id, ts, severidad, regla_id, origen, oferta_id, macro_nicho, nivel, valor, umbral, accion_sugerida, estado` | O0, dueño |
| Dashboard | `empresa/dashboard/index.html`, `oferta/<id>.html`, `mercado/<locale>.html`, `radar.html` (`python -m dashboard.build`) | HTML autocontenido | cada cifra con fuente, ventana y `actualizado_en` | dueño |
| Lectura semanal | `empresa/dashboard/lectura-semanal.md` | Markdown | 5 líneas por oferta + 5 del radar citando `kpi_id` | dueño |
| Informe QA | `empresa/datos/qa/AAAA-MM-v<n>.json` | JSON (6.3) | veredicto, puntajes, hallazgos estructurados, `aprendizajes_para_skill[]` | O0, X2 |

**Esquema lógico** (manda `datos/migraciones/`): `dim_oferta(oferta_id, familia_id, variante_de, macro_nicho, nivel_riesgo, locale, moneda_cobro, paises[])` · `dim_campana/conjunto/anuncio` (ID de Meta como PK; el nombre se parsea de 5.2 solo para etiquetar) · `fact_meta_ad_dia(ad_id, fecha, moneda, gasto_minor, impresiones, clics_enlace, lpv, pull_ts)` + `fact_meta_conv(…, ventana, compras_meta, valor_meta_minor)` (separadas: con `ventana` en la PK, sumar el gasto lo triplica) · `fact_pedido(session_id, oferta_id, cid, asid, adid, utm_*, bruto_minor, impuesto_minor, fee_minor, moneda, liquidado_minor, moneda_liq, tipo_cambio_id, consent_marketing, metodo, pais, email_hmac, estado ∈ pendiente/pagado/fallido, interno, livemode, pagado_en)` · `fact_evento`, `fact_reembolso`, `fact_disputa`, `fact_balance_tx`, `fact_payout`, `dim_moneda`, `fact_costo`, `fact_estado_oferta`, `fact_decision`, `fact_conexion`, `fact_qa` · **radar:** `dim_problema(problema_id, macro_nicho, nicho_id, locale, estado, riesgo_nivel)`, `fact_senal_agg(problema_id, familia_senal, fuente_id, fecha, n_ingresadas, n_descartadas)`, `fact_barrido(barrido_id, nicho_id, locale, costo_minor)`, `fact_candidato(oferta_id, problema_id, rango)` · `raw_*` append-only con hash. Montos en **enteros de unidad menor** (JPY/CLP = 0). `email_hmac` = HMAC-SHA256 con clave secreta; `interno`, `verificacion=1` y `livemode=false` se excluyen. Un pedido es `pagado` solo con `payment_status=paid` o `async_payment_succeeded` (en BLIK, MB WAY, Pix…, `completed` puede no ser cobro). **Unión Meta↔Stripe: `oferta_id` + `adid` (ID, nunca nombre).**

### 3.4 Parámetros y umbrales

Todos viven en `empresa/parametros.yaml` (el Maker solo propone cambios). Mapa `grupo.clave` y valor inicial `[HIPÓTESIS]`:

| tema | clave | valor |
|---|---|---|
| ETL, reproceso, inmaduros | `dashboard.etl_meta_cada_h` · `meta_ventana_reproceso_dias` · `meta_dias_inmaduros` | 3 h · 7 d · 2 d |
| Frescura (amarillo/rojo) | `dashboard.frescura_{meta,stripe_eventos,stripe_balance}_{amarillo,rojo}_h` (eventos: por el **latido del receptor**) | 6/12 · 2/6 · 26/36 |
| Conciliación | `dashboard.recon_tol_stripe_balance` · `recon_tol_gasto_meta_pct` · `recon_min_pedidos`; razón: `testeo.razon_meta_stripe_{min,max}` · `razon_ventana_dias` · `razon_n_min` (hogar D8) | 0 · 1 % · 10 |
| Datos suficientes | `dashboard.pedidos_min_verde` · `gasto_min_decision_x_cpa` (visual; D8 decide con `testeo.*`) · `cobertura_atribucion_min_pct` | 5 · 2,0 · 70 |
| Gasto y economía | `dashboard.alerta_gasto_sobre_presupuesto_x`, `costo_ia_max_pct`, `mer_verde_factor`; `finanzas.gasto_vs_tope_*_pct` | 1,75 · 15 · 1,2 |
| Reembolsos y disputas | `salud_operativa.*` y `limites.ratio_disputas_pausa`: F2 **cita, no define** (R06). Madurez = `limites.politica_reembolso_dias` + `veredicto.madurez_dias_extra` | de F1/X1 |
| Por macro-nicho (nota 25 §9-10) | **pendientes del MINOR**: `salud_operativa.disputas_pausa_{oferta,macro}_pct`, `disputas_casos_macro`, `reembolsos_macro_pct`; `limites.cuota_gasto_amarillo_{,b_}max_pct`, `nivel_max_lanzable`, `reserva_dias_stripe` | sin valor propio; mientras falten: «sin umbral fijado» (gris) |
| Radar y botón | de D1: `descubrimiento.{caducidad_banco_dias, antiguedad_max_evidencia_meses, cuota_min_exploracion_por_macro_nicho_pct}`; `limites.{max_costo_por_barrido, locales_permitidos, macro_nichos_permitidos, paises_permitidos, ofertas_en_test_simultaneas_max, perdida_neta_acumulada_max}`; `mercados.clics_min_decidir_mercado`. Tope diario de encolados: **clave inexistente** (pedido `boton_max_lanzamientos_dia`) | F2 no define umbrales del radar |

### 3.5 KPIs del paso

Los KPIs de decisión están en el **Anexo A**. Reglas: USD con el `fx` del día (Stripe: neto liquidado de `balance_tx`); «gris» = datos insuficientes, nunca rojo (semáforo oficial `ok/gris/provisional/stale`); cada KPI declara `min_datos`; días inmaduros y cohortes inmaduras, rotulados.

**Vistas**
- **Oferta:** economía vs `cpa_obj`, embudo, creativos, estructura, reembolsos/disputas, conexiones, decisiones D8, QA, veredicto (5.9).
- **Familia:** ofertas hermanas lado a lado y contra la madre (`variante_de`): CPA, `tasa_compra`, `tasa_reembolso`, MER. Sirve a D9/M1 para expandir.
- **Mercado/idioma** (`locale`, `pais`): gasto, pedidos, CPA, mix de **métodos de pago** y su conversión de checkout, reembolso y disputa **por método**, IVA y comisión reales vs el supuesto de D3, exposición país × nivel de M1. Bajo `mercados.clics_min_decidir_mercado`: gris «direccional». Alimenta a M1.
- **Macro-nicho** (decisión 13): por macro y nivel (verde/amarillo-A/amarillo-B): gasto amarillo vs cuota, disputas y reembolsos con la **exposición abierta de 120 días** (pausar el gasto no detiene el contador, nota 25 §9), avisos de Stripe, rechazos de Meta, hojas pausadas. El dueño ve nivel y reencuadre, no la «ola» de la hoja.

**Radar de problemas — KPIs `[NUEVO]`** (provisionales hasta alinearlos con `docs/_historial/d1-v2-interfaces.md`, que aún no existe; F2 muestra y semaforiza con umbrales de D1). Por `macro_nicho · nicho_id · locale`:
- `banco_n` por estado; `vigentes_n` (evidencia dentro de `caducidad_banco_dias`); `ficha_completa_pct` (prueba de una frase + MU + EU, 5.11).
- `edad_evidencia_med_dias`, `evidencia_vencida_pct`, `cobertura_locale` (locales permitidos con barrido en ventana), `cuota_macro_pct` (vs `cuota_min_exploracion_por_macro_nicho_pct`).
- `senales_descartadas_pct` por fuente y `rechazos_por_motivo` (`sin_mecanismo`, `multi_mecanismo`, `fuera_de_macro_nicho`, `claim_de_salud_o_ingresos`…): fuentes ruidosas, filtros mal calibrados.
- `costo_barrido` y `costo_por_candidato` = costos de barrido del período / candidatos que llegan a vigentes, contra `max_costo_por_barrido`; `verdes_topn_pct`, `topn_estable_pct`.
- **Rendimiento por nicho y fuente** (cohortes lentas, n pequeño → gris): problemas → elegidos → pasan D2 → ofertas validadas (5.9); aporte de cada `fuente_id`; señales propias (D8/D10) que volvieron al banco. F2 muestra los **conteos observados**; la estimación suavizada la calcula X2 (`rendimiento_radar`) y F2 solo la presenta rotulada (docs/04 §4.3, C-17).

**KPIs de F2:** `pct_cifras_conciliadas`, `latencia_dato_p95`, `alertas_accionadas_pct`, `falsos_positivos_alerta`, test de 30 s (< 30 s).

## 4. Flujo paso a paso (SOP)

| # | Actor | Acción | Guarda |
|---|---|---|---|
| 1 | Humano | Confirma moneda base, zona (= cuenta de Meta) y dónde se ve el dashboard | `parametros.yaml` |
| 2 | Maker (construcción) | Versiona glosario y vistas; el esquema lo cambia su dueño | glosario, pedidos |
| 3 | Script | **Extract**: `datos.etl_meta` (reproceso 7 d, `pull_ts`), `datos.etl_stripe` (por cursor, desde lo que publica F1), archivos de O0/D1/M1/X1 | `raw_*` append-only con hash |
| 4 | Script | **Load idempotente** por PK + `run_id`; Stripe duplicado/desordenado: el orden de eventos no está garantizado (`infra/plantillas/stripe-eventos-webhook.yaml`), así que el estado vigente lo fija la relectura del objeto en el backfill diario | `fact_*` |
| 5 | Script | **Transform**: `datos.kpi` → `kpi_*.json`; marca inmaduros; radar desde `empresa/descubrimiento/` (solo conteos, fechas, IDs) | snapshots |
| 6 | Script | **Conciliar** (C3-C6, C15), `latido_f2.json`, alertas (las rojas las lee O0; F2 no pausa nada) | `conciliacion/`, `alertas.jsonl` |
| 7 | Script | Fuente roja o conciliación fallida: cifra **tachada con la causa**, jamás 0 ni valor viejo sin marca | dashboard |
| 8 | Script | `python -m dashboard.build --salida empresa/dashboard`: determinista, **todo texto escapado**, CSP | HTML |
| 9 | Maker (lector) | Lectura semanal con **solo números e IDs** | `lectura-semanal.md` |
| 10 | QA | Revisión por versión y auditoría semanal; **QA-A** antes de publicar artefacto o app (no cuenta ronda) | `empresa/datos/qa/` |
| 11 | Humano | Revisa alertas; elige candidato y pulsa el botón | `decisiones_dueno.jsonl` |

**Ruta tecnológica (menor fricción primero).** *Fase A (N0-N2):* HTML estático local; el botón **copia el comando** `python -m engine.orq crear --brief <ruta>` con un `00-brief.yaml` prellenado; se copia solo con el brief ya firmado (gate H del paso 3 de O0) y tras la validación en seco (paso 2), y `orq crear` corre después. *Fase B (opcional):* artefacto privado (`db` no se escribe desde cron `[VERIFICAR]`; publicar es H; solo agregados `[DUEÑO]`). *Fase C (N3-N4):* `dashboard.api` (WSGI estándar: `GET /salud`, `GET /estado` firmado) con Postgres en **Railway** y **Cloudflare** delante (DNS, HTTPS, Access con 2FA `[VERIFICAR]`); ETL por cron de Railway con tokens de solo lectura de D0; sin datos personales (email solo en HMAC); sesión corta.

**Botón «Lanzar nueva oferta»** (el `POST /ofertas` aún no se construye, `06-bases` §4.6). Clic → O0 pide a D1 los mejores problemas del **banco** con evidencia refrescada (no investiga desde cero) → M1 los empareja con `locale` y mercados → el **selector** los muestra → el dueño elige (`accion:elegir_candidato`, H hasta N3; firma Ed25519 con `orq firmar`, no del dashboard; clic como firma = C03 abierto) → se congela `candidatos.json` y arranca D2. **Selector top-N**, por candidato: `macro_nicho`, **nivel de riesgo y reencuadre** (ningún ROJO ni amarillo-B sin gate H), problema en voz del cliente, mecanismo único (`nombre`) y entregable único (`formato`), evidencia (n fuentes, tipos, edad, `locale`), `confianza`, mercado sugerido (moneda, métodos de pago habilitados), **«qué lo mataría»** y costo máximo en riesgo. El texto de D1 va escapado, truncado y rotulado «generado a partir de fuentes externas». El botón se **deshabilita con el motivo** si falla: esquema del brief, sesión/CSRF/`idempotency_key`, tope diario de encolados, `PAUSA`, infra VERDE y < 6 h, ofertas en test < `ofertas_en_test_simultaneas_max`, margen bajo `perdida_neta_acumulada_max`, `macro_nicho`/`locale`/país permitidos, ≥ 1 candidato vigente (si no: «pedir barrido dirigido»). El **costo máximo en riesgo** sale de `limites.yaml`, nunca del formulario; **encola** en O0, que re-valida todo.

**Wireframe 1 — Centro de control**
```
┌ CENTRO ── actualizado 14:02 (Meta 14:00 ● · Stripe 14:01 ● · tracking ●) ─ PAUSA: no ┐
│ HOY (USD) Ingresos 142 · Comisión 6 · Gasto 96 · IA 11 · BENEFICIO +29 (gris si datos<min) · MER 1.48 (BE 1.25) │
│ Payout pendiente 380 | Gasto vs tope 96/150 | Pérdida acum. −40/tope 300 │
├ POR MERCADO it-IT 2 · pl-PL 1 · en-CA 1 ─┬ POR MACRO salud ● · relaciones ▲ · dinero ● (amarillo 22 % de 30 %) ┤
├ REQUIERE TU DECISIÓN ▸ D3 OF-202611-02 gate H ▸ M1 primer lanzamiento pl-PL ▸ ROJA razón Meta/Stripe 0.55 │
├ RADAR 14 vigentes · evidencia mediana 21 d ┼ CONEXIONES ● Meta ● Stripe ● Píxel ▲ CAPI EMQ 5.8 ┤
├ [ Lanzar nueva oferta ] (habilitado: 1/3 en test; 14 candidatos vigentes) ───────────────────────────────┘
```
**Wireframe 2 — Oferta** (`OF-202611-01` · `it-IT` · EUR · dinero · verde)
```
┌ OF-202611-01 · TEST día 5 · QA D7 PASS_CON_NOTAS · FAM-202611-01 · Meta ● Stripe ● ───────────────┐
│ Economía: ticket 17 EUR + bump 9 · AOV 20.0 · CPA real 14.2 vs TOPE 12.4 ▲ rojo · gris si gasto<2×tope │
│ EMBUDO: Impr 48k → Clic enlace 620 (1.3%) → LPV 540 → Checkout 63 → Pagados 9 → Bump 3                 │
│ Meta reporta 10 (1d clic) · Stripe confirma 9 (8 con adid y consentimiento) · ratio 10/8 = 1.25 ✓         │
├ CREATIVOS (prob. de ser mejor) ────────────┬ OF-202611-01_TEST_VENTAS_ABO_20261106 · 3 conjuntos ▲ ────┤
│ C03_vid_H2_v1 CPA 9.8 P=0.84 ● líder       │ C01_img_H1_v1 CPA 16.0 P=0.07 no concluyente              │
├ MÉTODOS DE PAGO tarjeta 71 % … (conversión y reembolso por método) · reembolsos 1/9 · provisional ┤
```
**Wireframe 3 — Radar:** filas macro → nicho, columnas `locale`; celda = vigentes · edad de evidencia · costo por candidato; debajo, el selector y el rendimiento por nicho/fuente con n visible.

## 5. Agente Maker

- **Rol:** (a) scripts deterministas de ETL/KPI/alertas/build (`datos.*`, `dashboard.*`: los escribe una sesión de construcción con QA; el cron los ejecuta **sin LLM**); (b) agente **lector** en runtime (`agentes.runner`, lista blanca) que redacta la lectura semanal y propone vistas.
- **No hace:** no calcula cifras «a ojo»; no toca `estado.json`, `limites.yaml`, `parametros.yaml`, `contratos/**` ni hooks (propone en `empresa/propuestas/`); no activa, pausa ni edita campañas; no inventa datos faltantes; no ve PII ni secretos; **no lee texto libre externo** (UTM, nombres, metadata, comentarios, señales y fichas del banco: cualquiera puede poner instrucciones o `<script>`); no cambia scripts del scheduler en producción (versión fijada por hash tras QA + H).
- **Herramientas (mínimo privilegio):** lectura de `ofertas/**` y `empresa/**`; escritura solo en `empresa/datos/` (glosario, lectura) y `empresa/dashboard/`; Meta en solo lectura con `deny` para `ads_create_*`, `ads_update_*`, `ads_activate_*`, `ads_boost_*`, `ads_*_delete*` y escritura de `ads_pixel_*`; sin Stripe directo ni conectores de Shopify/Higgsfield; skills `data:sql-queries`, `data:validate-data`, `dataviz`, `data:build-dashboard` solo en sesiones de diseño.
- **Contexto:** esta especificación, glosario, última conciliación y fallas de X2.

## 6. Agente QA

**Independencia:** subagente `f2-qa`, contexto limpio, solo lectura; recibe base, esquema, glosario, fixtures, rúbrica y fallas conocidas de X2, no el razonamiento del Maker. **Recomputa** desde `raw_*` con SQL propio. Sella por **hash** la versión revisada de glosario/scripts (`skills_pin`); el veto de X1 aplica siempre.

**L1 — deterministas** (B = BLOQUEANTE)

| # | Check | Sev. |
|---|---|---|
| C1 | PK únicas, FK sin huérfanos, montos enteros con moneda | B |
| C2 | ETL dos veces ⇒ mismo hash de `fact_*` | B |
| C3 | Σ pedidos netos/fee del día (zona de reporte) = Σ `balance_transactions` **por tipo** (tol. 0); `livemode=false`, `interno`, `pendiente` fuera; contra-muestra de 3 pedidos y balance **directo a Stripe** con clave de lectura del QA | B |
| C4 | Gasto vs re-consulta a Meta de 3 anuncios (semilla registrada) en días maduros (`recon_tol_gasto_meta_pct`); sin multiplicar por ventana | B |
| C5 | Cordura: sin negativos; CTR ≤ 100 %; embudo monótono salvo tracking caído, que debe alertar | MAYOR |
| C6 | Fuente roja ⇒ cifra marcada; nunca 0 ni caché sin marca | B |
| C7 | Sin *fan-out*: Σ pedidos tras los joins = pedidos origen | B |
| C8 | FX del día; neto liquidado de `balance_tx`; **nunca suma de monedas distintas**; redondeo por `dim_moneda` | B |
| C9 | Recomputo de 10 KPIs ±0,01; B si falla uno que alimenta decisiones (`cpa_real`, `beneficio`, `mer`, `ratio_recon`) | B/MAYOR |
| C10 | Días de Meta y cohortes inmaduros rotulados; ninguna decisión sugerida los usa | B/MAYOR |
| C11 | Sin secretos ni emails en el HTML; `<script>`/`onerror=` en UTM, nombres, **extractos y fichas de D1** ⇒ texto inerte; CSP | B |
| C12 | Inyección de fixtures: cada regla de alerta se dispara y se cierra | MAYOR |
| C13 | Botón (N/A explícito antes de la fase C): sin `idempotency_key`/CSRF/sesión, con `PAUSA`, infra no VERDE, tope de ofertas, macro/locale no permitido, candidato ROJO o amarillo-B sin gate ⇒ rechazado; doble POST ⇒ una cola | B |
| C14 | Cada cifra del HTML = `kpi_*.json` = SQL del QA; sin cálculos en JS | B |
| C15 | Dashboard = `pnl.json` (F1-07); Σ gasto = F1; `cpa`/`roas` vs `kpis.json` de D8; diferencia ⇒ alerta, no se promedia | B |
| C16 | `ratio_recon` solo con pedidos `adid` **y** `consent_marketing=1`; los sin consentimiento cuentan en ingresos, no en la razón | B |
| C17 | Radar: conteos del HTML = `banco.json` = `problemas/`; evidencia vencida nunca vigente; n pequeño ⇒ gris; costo por candidato = `costos.jsonl` | B/MAYOR |
| C18 | Macro-nicho y selector: nivel mostrado = `riesgo.nivel` del contrato (recomputado); exposición de 120 d correcta; sin umbral fijado ⇒ gris, nunca verde | B |

**L2 — rúbrica** (0-5 con evidencia citada; ningún ítem < 3 y promedio ≥ `umbral_pass_F2` `[HIPÓTESIS]`)

| ítem | 1 | 3 | 5 |
|---|---|---|---|
| R1 Definiciones | KPI sin fórmula o distinta a la mostrada | fórmula sin tolerancia | cada cifra enlaza a glosario, fuente, ventana y tolerancia |
| R2 Accionabilidad | números sueltos | pregunta sin decisión | cada bloque dice qué decidir y qué umbral lo dispara |
| R3 Incertidumbre | rojo/verde con 3 pedidos | gris sin explicar | gris/«no concluyente» explicado, inmaduros y rangos |
| R4 Meta reporta / Stripe confirma | mezcladas | etiquetadas a veces | separadas y conciliadas con ratio |
| R5 Alertas | ruido o silencio | cubren lo principal, sin dueño | pocas, con causa, acción, responsable y falsos positivos medidos |
| R6 Legibilidad y neutralidad | ilegible en 30 s; supone un país o moneda | color como único código | test de 30 s; color + símbolo; locale y moneda por vista |
| R7 Seguridad y privacidad | datos expuestos | acceso protegido, PII sin revisar | Access + 2FA, sin PII, botón con defensas verificadas |

**L3 — simulaciones:** *dueño de 30 s* (¿gano o pierdo? ¿qué espera mi decisión? ¿qué candidato elijo y qué lo mataría?); *analista escéptico* (recalcula 3 cifras); *apagón* de Meta 8 h ⇒ stale; *botón* (doble clic, sesión expirada, `PAUSA`, candidato ROJO); *reembolso masivo* al 30 %; *mercado nuevo* sin tocar código.

**Defectos sembrados** (detectar ≥ 90 % de los bloqueantes; cada uno también corregido; los dorados dan PASS): D1 ROAS sin descontar reembolsos · D2 FX de hoy · D3 *fan-out* por metadata · D4 último día de Meta parcial · D5 Meta caído con valores viejos · D6 pedido `livemode=false` · D7 zona horaria · D8 suma EUR+PLN+USD · D9 botón sin idempotencia · D10 token en el HTML · D11 `ratio_recon` 7d_click contra Stripe 1d · D12 gasto sumado por ventanas · D13 `<script>` en `utm_content` · D14 semáforo con 3 pedidos · D15 webhook duplicado cuenta dos veces un reembolso · D16 pedido sin consentimiento en `ratio_recon` · D17 evidencia vencida como vigente · D18 candidato ROJO elegible · D19 `<script>` en un extracto de señal · D20 disputas «verdes» sin los 120 días abiertos. Mapa: D1/D11/D14→C9 · D2/D8→C8 · D3→C7 · D4→C10 · D5→C6 · D6/D7→C3 · D9/D18→C13/C18 · D10/D13/D19→C11 · D12→C4 · D15→C2 · D16→C16 · D17→C17 · D20→C18. Dorados: ≥ 2, de macro-nicho, idioma y moneda distintos.

**Mejoras de valor** (sin cambiar definiciones ni contratos): decisión sugerida por bloque; comparación con la semana anterior y con D3; vista de caja/payout; gráficos engañosos. **Veredicto** (5.4): PASS = 0 BLOQUEANTE, 0 MAYOR, promedio ≥ umbral; máx. 2 rondas, luego `ESCALAR`; siempre ≥ 3 hallazgos o evidencia de qué revisó; hallazgos con `check_id, patron_clave, severidad, etapa, skill_version`.

## 7. Gates y autonomía

Sin mover dinero. Gate de etapa F2 = **A** en N0-N4 (`gates.json`; lo que sube con el nivel es cuánto corre desatendido). Son **H**: publicar un artefacto o la app, cambiar el glosario, `accion:ascender_nivel`, `accion:elegir_candidato` (botón) y `accion:lanzamiento_pais_idioma_nuevo` (M1). El botón solo **encola**; O0 impone `limites.yaml`, `PAUSA`, preflight y X1.

| Nivel | Qué corre solo |
|---|---|
| N0 | nada: el dueño pide a mano en Code tablas y HTML con datos de prueba |
| N1 | ETL y build con scheduler; el dueño contrasta cifras con Stripe/Meta |
| N2 | Maker + QA en cada cambio de vistas/esquema; **Meta por MCP solo diagnóstico** |
| N3 | ETL, conciliación y alertas desatendidos con **credenciales propias** (Railway cron); H ante FAIL de conciliación > 24 h |
| N4 | botón en la app con las defensas de §4 (clic = H + validación del motor) |

**Ascenso:** N1→N2: 14 días de conciliación sin diferencias y ≥ 90 % del ETL sin intervención. N2→N3: 4 semanas con 0 cifras corregidas por el dueño, `ratio_recon` en rango o explicado, QA con ≥ 90 % de sembrados. N3→N4: 0 incidentes de datos que causaran una decisión equivocada y C13 en verde. **Descenso automático** a N1 ante discrepancia no explicada de Stripe, FAIL de C15 o frescura roja > 24 h.

## 8. Riesgos y modos de falla

| riesgo | señal temprana | mitigación | resp. |
|---|---|---|---|
| Decisión sobre dato viejo, parcial o inmaduro; doble conteo | frescura amarilla; C3/C7 | marcas; ningún KPI `stale`, `gris` o inmaduro decide; claves únicas, backfill idempotente | Script/QA |
| Atribución rota o sin consentimiento (UE/UK) | `cobertura_atrib` baja; razón fuera de rango | alerta; razón solo sobre consentidos (C16); Stripe es la verdad | D5/F2 |
| Multimoneda mal sumada o FX distinto al de F1 | C8; C15 ≠ 0 | neto liquidado de `balance_tx`; una sola tabla de FX (F1) | F1/F2 |
| Falsa certeza con pocos pedidos, clics o señales | rojo/verde con n < min | gris + «no concluyente»; n visible | Maker |
| Riesgo de cuenta enmascarado: disputas y reembolsos llegan a los 30-120 días | tasa «verde» con cohortes jóvenes | exposición abierta de 120 d, tasas provisionales, umbrales un escalón más bajo en amarillos | F1/X1 |
| Una cuenta de Meta y una de Stripe sostienen todo | rechazos, avisos, retención | tablero por macro-nivel con cuota amarilla, rechazos y avisos; alerta a X1/O0 | X1 |
| Inyección vía UTM, metadata o texto del banco (XSS o instrucciones al LLM) | C11 con fixtures hostiles | escape total, CSP, el LLM solo recibe números e IDs | Script/QA |
| Fuga de datos financieros o de compradores de ofertas sensibles (duelo, deuda, ruptura) | URL pública, token o email en HTML | Access + 2FA, sin PII, solo HMAC, retención acotada con X1 `[VERIFICAR]` (inv. 05, 21) | Humano/QA |
| Botón lanza gasto sin control | clic repetido, sesión robada, candidato rojo | idempotencia, CSRF, 2FA; la firma H no es del dashboard; el motor re-valida | O0/D0 |
| Scheduler caído o conector claude.ai no disponible desatendido; pérdida de la base | latido ausente; falla de disco | Railway cron con credenciales propias desde N3; `pg_dump` cifrado diario a R2 con restauración mensual (D0); eventos de Stripe recuperables ~30 d `[VERIFICAR]` | D0 |
| El Maker cambia un script con credenciales | hash distinto del fijado | scripts fijados por hash tras QA + H | Humano |
| Radar engañoso: el banco aparenta vigencia o diversidad que no tiene | `evidencia_vencida_pct` alto; un macro bajo la cuota | KPIs de §3.5; el botón se deshabilita sin vigentes | D1/F2 |

## 9. Mejoras respecto del video

1. **[NUEVO] Una verdad contable** (Stripe = ingresos, Meta = gasto), conciliación diaria y `ratio_recon` por consentimiento; el video solo «mira» Meta.
2. **Economía unitaria contra break-even**, semáforo gris y beneficio real (comisión, reembolsos, IA, disputas), multimoneda y por mercado/método de pago.
3. **Vistas por familia, mercado y macro-nivel** (exposición de 120 días, cuota amarilla) y **radar con selector del botón**: evidencia, nivel y «qué lo mataría».
4. **Ranking bayesiano de creativos**, salud de conexiones, botón con defensas, modo degradado explícito y aprendizajes a X2.

## 10. Forja de la skill (pestaña Code)

### 10.1 Prompt de arranque (copiar y pegar)

```
ROL: Ingeniero/a de datos y BI + diseñador/a de dashboards operativos para negocios de ads + ecommerce, trabajando como F2 (Dashboard y BI) para un dueño con criterio de negocio, no necesariamente técnico. Todo en español con tildes.

CONTEXTO: sistema multi-agente (Maker + QA independiente por tarea) que lanza ofertas de productos digitales de bajo ticket en cualquier idioma/mercado (oferta = concepto × idioma/clúster, backbone 3.1), dentro de salud, relaciones o dinero; tests con Meta hacia landing propia con Stripe (LLC de EE. UU., liquidación USD, cobro multimoneda); infra GitHub + Railway (Postgres) + Cloudflare. Estás en una sesión nueva de Claude Code abierta en <carpeta del proyecto>.

LEE PRIMERO (si algo choca, manda el contrato/código y lo registrás como conflicto): departamentos/13-dashboard-bi.md (con su Anexo), docs/_backbone.md (no lo cambies), docs/contratos.md, contratos/{kpi,parametros,limites,candidatos,mercado,conciliacion}.schema.json, docs/06-bases-del-testeo.md §4.4 y §4.6, docs/_historial/d1-v2-interfaces.md (si existe), docs/_investigacion/{02 (F2), 03 §3 y §7, 04 §2.5, §3, §10, 12 (F2), 25 §9-10}, departamentos/{00,02,09,12,16}-*.md. Usá los módulos existentes datos.{db,etl_meta,etl_stripe,ledger,kpi} y dashboard.{build,alertas,api}; si falta un módulo o contrato, NO lo escribas: registralo como pedido en docs/_historial/coordinacion-sesiones.md y trabajá con fixtures.

ENTRADAS: ofertas/*/{estado.json,mercado.json,03-oferta/*,01-descubrimiento/candidatos.json}, empresa/{portafolio.json,costos.jsonl,registro.jsonl,parametros.yaml,limites.yaml,autonomia.yaml,infra/estado.json,descubrimiento/,mercados/atlas.json}. Si faltan, FIXTURES [SINTÉTICO] en el directorio de fixtures de tests/dashboard/ (nunca en empresa/): 3 ofertas de macro-nichos, idiomas y monedas distintos (EUR y PLN, base USD), 14 días, reembolso tardío, pedido de prueba e interno, pago diferido pendiente, webhook duplicado, día de Meta parcial, corte de 8 h, pedidos sin adid y sin consentimiento, banco de D1 con evidencia vencida y un candidato ROJO. Base separada y banner [SINTÉTICO]; jamás escribas en empresa/datos/.

PREGUNTAS BLOQUEANTES (todas juntas; esperá respuesta): zona horaria y moneda de la cuenta de Meta (leídas de la cuenta); dónde corre el scheduler y dónde se ve el dashboard (local / artefacto / web con Cloudflare Access); canales de alertas críticas; beneficio devengado o de caja; costos fijos; si aceptás agregados en un artefacto.

TAREA (v1 para pulir): (1) empresa/datos/glosario_kpi.yaml con TODOS los KPIs del Anexo A y del Radar (§3.5), con claves de parametros.yaml en el semáforo; (2) plantillas de vista (centro, oferta, familia, mercado, macro-nicho, radar, selector del botón; skills dataviz y data:build-dashboard); (3) lectura semanal (solo números e IDs); (4) tests de C1-C18 de §6 y un caso por defecto D1-D20 sobre los módulos existentes con fixtures (C13 N/A sin app); (5) pedidos a otros dueños (MINOR de kpi por ámbito, boton_max_lanzamientos_dia, adiciones a migraciones); (6) lista de [SUPUESTO] y [VERIFICAR].

SALIDA: artefactos en sus rutas + resumen de 10 líneas (checks que pasan, no probados, decisiones del dueño que bloquean).

ACEPTACIÓN: ETL dos veces ⇒ mismo resultado; Σ pedidos = Σ balance; ningún KPI por LLM ni JS; gris ante inmaduros o datos insuficientes; nunca suma de monedas; HTML sin secretos ni PII; Meta reporta y Stripe confirma separados; texto del banco y de UTM inerte; el selector no habilita ROJO ni amarillo-B sin gate.

REGLAS: no inventes datos; marcá [SUPUESTO]; no ejecutes herramientas con costo o efecto externo (create_*, update_*, activate_*, publish_*, upload_*, share_*, generate_*, gasto de créditos) ni leas credenciales sin permiso; Meta y Stripe solo lectura (MCP de Meta: diagnóstico hasta N2); no toques estado.json, limites.yaml, parametros.yaml, contratos/ ni .claude/settings.json.
```

### 10.2 Cómo pulir

Máx. 3 sesiones de ~2 h. (1) Con datos reales, recalculá a mano 5 cifras (ingresos, gasto, CPA, beneficio, reembolsos). (2) Test de 30 s, con «¿qué candidato elijo?». (3) Rompé cosas: cortá una fuente, duplicá un webhook, cambiá de moneda, pasá `<script>` en un UTM y en un extracto. (4) ¿Esta cifra cambiaría una decisión? ¿Qué alerta ignorarías?

### 10.3 Estructura de la skill a generar

```
.claude/skills/f2-dashboard-bi/
├── SKILL.md
├── references/         # glosario_kpi.yaml, esquema.md, conciliacion.md, wireframes.md, reparto-f1-f2.md, radar.md
├── rubric.md
├── templates/          # oferta.html, centro.html, mercado.html, radar.html, lectura-semanal.md
├── scripts/            # envoltorios de python -m datos.kpi / dashboard.build / dashboard.alertas
└── evals/              # fixtures, defectos D1-D20, dorados
.claude/agents/f2-maker.md · f2-qa.md
```

### 10.4 Definición de listo (DoD)

C1-C12 y C14-C18 verdes sobre fixtures y datos reales (C13 al existir la app); ≥ 90 % de sembrados BLOQUEANTES detectados y ≥ 2 dorados en PASS; ETL desatendido 7 días con hash idéntico; el dueño recalcula 5 cifras y coinciden; 2 semanas de conciliación sin diferencias; test de 30 s; 0 secretos/PII; glosario aprobado `[DUEÑO]`; skill registrada con `orq nivel` (hash en `skills_pin`).

### 10.5 Evals mínimos

(1) Dinero en `it-IT` con pocos pedidos: gris. (2) Otro macro-nicho, idioma y moneda (p. ej. relaciones, `pl-PL`, PLN, base USD): FX correcto. (3) Corte de Meta de 8 h: stale. (4) Pedido de prueba y reembolso tardío. (5) 40 % de pedidos sin `adid` y 30 % sin consentimiento: alerta y razón solo sobre consentidos. (6) Botón con `PAUSA`. (7) Creativo en dos ofertas: sin doble conteo. (8) Pago diferido pendiente y luego fallido: no es venta. (9) UTM y extracto de señal hostiles: texto inerte. (10) Pedido a las 23:59 y 00:01 en la zona de la cuenta. (11) Banco con evidencia vencida y un macro bajo la cuota: alerta y botón con motivo. (12) Candidato ROJO en el top-N: visible, no elegible.

## 11. Preguntas abiertas / decisiones del dueño

**Resuelto en v2:** moneda base **USD** (decisión 7); zona = la de la cuenta de Meta (valor real `[VERIFICAR]`); Railway + Cloudflare (decisión 10); umbrales de reembolso/disputa = `parametros.salud_operativa` (R06).

1. `[DUEÑO]` ¿Beneficio devengado (recomendado) o de caja como vista principal?
2. `[DUEÑO]` Canales de alertas críticas (D0 exige ≥ 2, `canal_alertas`).
3. `[DUEÑO]` ¿Se aceptan ventas y gasto **agregados** en un artefacto de claude.ai (fase B)? ¿Tope diario de encolados del botón (`boton_max_lanzamientos_dia`, clave inexistente en `limites`)?
4. `[DUEÑO]` ¿El clic autenticado del botón vale como firma del gate H en N4 (C03)? Hasta decidir: `orq firmar`.
5. `[DUEÑO]` Costos fijos y prorrateo; con **Managed Payments** (MoR) cambian ingresos e impuestos `[VERIFICAR]` (inv. 03).
6. `[VERIFICAR]` Ventanas de atribución y campos (aprendizaje, video); Cloudflare Access con 2FA; retención de datos de compradores sensibles (con X1).
7. `[HIPÓTESIS]` Umbrales: calibrar con 4 semanas de datos; KPIs del radar: reconciliar con `d1-v2-interfaces.md`.

## Anexo (se traslada a `references/` de la skill)

### A. Glosario canónico de KPIs

**Resumen.** La fuente del glosario (fórmulas, granularidad, tolerancia, mínimos y semáforos) es `docs/04-datos-kpis-dashboard.md` §1; si difieren, manda ese documento. Id · fórmula · fuente · semáforo (claves en `parametros.yaml`). USD con el tipo de cambio del día (`tipo_cambio_id`); «gris» = datos insuficientes; tolerancia 0 contra `balance_tx` salvo indicación.

| id | fórmula | fuente | semáforo |
|---|---|---|---|
| `ingresos_brutos` | Σ cobrado **con impuesto** de pedidos pagados, `livemode=true`, `interno=false` (= `pnl.ingresos_brutos`); `impuestos` = pasivo por país; `ingresos_sin_impuesto` = brutos − impuestos | Stripe vía F1 | — |
| `ingresos_netos` | `ingresos_sin_impuesto` − reembolsos (sin su impuesto) imputados a la cohorte del pedido; **provisional** hasta madurez | Stripe vía F1 | — |
| `comision` | Σ `fee` de balance_transactions (incluye conversión de moneda) | Stripe | — |
| `gasto_meta` | Σ gasto de insights (moneda de la cuenta → USD); tol. `recon_tol_gasto_meta_pct` | Meta | — |
| `costo_ia` | Σ `fact_costo` imputado | `costos.jsonl` | rojo > `costo_ia_max_pct` del bruto |
| `resultado_operativo` (etiqueta «Beneficio») | `ingresos_brutos` − impuestos − reembolsos − comisiones − tarifas_disputa − disputas_perdidas − gasto_meta − costo_ia − otros_costos (incluye fijos prorrateados) (= `pnl.json`, ±0,01) | derivado | verde > 0 con ≥ `pedidos_min_verde`; provisional con cohortes inmaduras |
| `mer`, `mer_neto`, `mer_be` | `ingresos_sin_impuesto` / `gasto_meta_efectivo`; `ingresos_netos` / gasto (7 d, por `locale`, D8); `ingresos_sin_impuesto` / (`ingresos_sin_impuesto` − reembolsos − comisiones − tarifas_disputa − disputas_perdidas − costo_var) | derivado | verde ≥ `mer_verde_factor`×`mer_be`; amarillo ≥ `mer_be`; rojo < |
| `roas_stripe`, `roas_neto`, `roas_meta` | `ingresos_brutos` con `adid` / `gasto_meta_efectivo` (comparable con `roas_be = aov / cpa_be`); `contribución` / gasto; `valor_meta` / gasto por ventana | derivado; Meta | vs `roas_be`; `roas_meta` siempre «Meta reporta» |
| `cpa`, `cpa_visto`, `cpa_mezclado`, `cpa_neto` | `gasto_meta_efectivo` / pedidos con `adid` (IC 90 % Poisson); `gasto_meta` / pedidos con `adid` (lo que ve Ads Manager); `gasto_meta_efectivo` / todos los pedidos; gasto / compras netas de cohorte madura (D8) | derivado | `cpa_visto`: verde ≤ `cpa_obj`; amarillo ≤ `cpa_be_visto`; rojo > `cpa_be_visto`; gris si pedidos < `pedidos_min_verde`, gasto < `gasto_min_decision_x_cpa`×`cpa_obj` o el IC 90 % cruza `cpa_be_visto` («no concluyente») |
| `cpa_be`, `cpa_be_visto`, `cpa_obj`, `roas_be` | `cpa_be` = `mc`; `cpa_be_visto` = `cpa_be`/(1+`tarifa_meta`); `cpa_obj` = `economia.factor_cpa_objetivo`×`cpa_be_visto`; `roas_be` = `aov`/`cpa_be`; por país en multi-país | `economia.json` (supuesto) y `economia_real.json` (F1) | referencia |
| `aov`, `aov_neto`, `tasa_bump` | `ingresos_brutos`/pedidos (con impuesto, = `economia.aov`); `ingresos_sin_impuesto`/pedidos; pedidos con bump/pedidos | Stripe | bump < hipótesis de D3 = amarillo |
| `ctr_enlace`, `cpm`, `cpc_enlace`, `hook_rate`, `retencion` | clics_enlace/impr.; gasto/impr.×1000; gasto/clics_enlace; vistas 3 s/impr. y retención (campos `[VERIFICAR]`) | Meta | rangos de inv. 04 §8.2 `[HIPÓTESIS]`, por mercado |
| `tasa_conexion`, `tasa_ic`, `tasa_compra_ic` (antes `tasa_lpv/checkout/compra`; nombres de `testeo.*`) | lpv/clics; IC/lpv; pedidos/IC (embudo monótono) | Meta + tracking + Stripe | `testeo.tasa_conexion_min`, `tasa_ic_min_pct`, `tasa_compra_ic_min_pct` |
| `tasa_reembolso`, `tasa_disputa` | reembolsos/pedidos; (disputas+EFW)/pedidos; solo cohortes maduras | Stripe | `salud_operativa.*` (un escalón más bajo en amarillos) |
| `exposicion_disputas` | Σ neto de pagos de los últimos `reserva_dias_stripe` días | Stripe | informativo (macro-nivel) |
| `ratio_recon` | `compras_meta_1d_click` / pedidos `pagado` con `adid` y `consent_marketing=1`, ventana `razon_ventana_dias` | Meta÷Stripe | `testeo.razon_meta_stripe_{min,max}`; gris si pedidos < `recon_min_pedidos` |
| `cobertura_atrib` | pedidos con `adid` válido / pedidos | Stripe | < `cobertura_atribucion_min_pct` = amarillo |
| `emq`, `tasa_dedupe`, `frescura_fuente` | dataset; ahora − última carga OK | Meta; ETL | EMQ < 6 amarillo `[HIPÓTESIS]`; §3.4 |
| `prob_mejor` | P(θ_i = máx θ_j), Beta(1+pedidos, 1+clics−pedidos), 20.000 sorteos, semilla fija | derivado | máx < 0,8 o clics < mínimo = «no concluyente» |
| `mix_metodos`, `conv_checkout_metodo` | pedidos por `metodo`/pedidos; pedidos/IC por método | Stripe + tracking | informativo; gris si n < `recon_min_pedidos` |
| `cuota_amarilla_pct` | gasto en ofertas amarillas / gasto total | Meta + `oferta.json` | vs `limites.cuota_gasto_amarillo_max_pct`; gris si la clave no existe |

### B. Reconciliaciones v2

(1) Gate de F2: la v1 tenía H en N0-N1; manda `gates.json` (A en todos los niveles). (2) Disputas: el 0,5 % de F2 → `salud_operativa` (R06). (3) El Maker no escribe `contratos/**` (protegida): propone. (4) `datos.schema.sql` y los scripts `f2_etl/recon/alerts/dash_build.py` no existen: son las migraciones de `datos/` y los módulos `datos.*`/`dashboard.*`. (5) `cobertura_atribucion_min_pct` (`dashboard`) y `testeo.cobertura_adid_min_pct` coexisten: F2 muestra el primero, D8 decide con el segundo; reconciliar a un hogar. (6) `recon_ratio_meta_stripe` se retira: la razón vive en `testeo.razon_meta_stripe_*`; `gasto_alarma_pct`/`m_kill` de O0 → `finanzas.gasto_vs_tope_*` y `testeo.*`. (7) v2.1 (docs/04 §8): `ingresos_brutos` con impuesto (C-01), `aov` bruto y `cpa_obj` sobre `cpa_be_visto` (C-02/03), ids de CPA y de embudo (C-05/06), banda del `cpa` alineada con D8 (C-08), `fabrica.db`, `tipo_cambio_id` y estado del pedido (C-09/10), relectura del objeto en el backfill (C-11), alertas unificadas con F1 (C-12), wireframe 2 corregido (C-15).
