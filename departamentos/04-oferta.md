# D3 — Arquitectura de la oferta
> Pipeline · una vez por oferta (concepto × idioma/clúster) y por revisión de versión · Gate por defecto: **H** (S desde N3, `contratos/gates.json`) · Estado de la skill: v0.1 sin pulir (forjada por S-C el 2026-11-06; ver `.claude/skills/d3-arquitectura-oferta/`; v1.0 solo con corrida manual real, retro y DoD firmados, `docs/03` §2.6) · Especificación v2.2 (2026-11-06)

## 1. Misión y posición en el flujo

Convertir un candidato elegido (D1) y validado (D2) en una **oferta vendible con anuncios y rentable en su mercado**: nombre, promesa, bonus, garantía, precio local, bump, ángulos, avatar, **riesgo re-verificado** y **economía por mercado**, heredando el mecanismo y el entregable únicos. Es el último punto barato para frenar una oferta inviable.

- **Unidad** (backbone 3.1): una `oferta_id` = un concepto en un `locale` y un clúster `paises_segmentacion` con una `moneda` de cobro. Otro idioma o mercado = nueva `oferta_id` con `variante_de`: hereda la estructura, pero economía, riesgo y localización se rehacen (no se traduce el texto).
- **Recibe de:** D1 (`candidatos.json` v2: ficha MU/EU, `macro_nicho`, `riesgo`), D2, M1 (`mercado.json`; opcional `mercado.seleccion.json`), `00-brief.yaml`, F1 (`tarifas.json`), X1 (claims, matriz país × nivel, ayuda por país), X2 (fallas).
- **Entrega a:** D4 (`promesa.tiempo_prometido_min` = única fuente del tiempo), D5, D6, D7/D8 (CPA objetivo, presupuesto, cortes), F1, X1 (sello por hash de `oferta.json` + `economia.json`).
- **Regla rectora:** lo prometido en anuncio y landing es contrato [NUEVO, `05-legal.md` §3.3]. Promesa y nombre **no pueden contradecir ni exagerar** la ficha MU/EU (backbone 5.11) ni el nivel de riesgo (decisión 13).

## 2. Qué dice el video (y qué no dice)

| | Contenido |
|---|---|
| **[VIDEO] Hace / omite** | Hace: entrevista de 10 preguntas, título/subtítulo, vehículo (PDF cuyo tiempo de lectura = tiempo prometido), puntaje 85/100, garantía, urgencia, prueba social, order bump, ángulos por conciencia. Su nicho (edición con IA) **no es un nicho modelo**. Omite: economía unitaria, presupuesto del test, método del puntaje, precios, tasa de bump, riesgos legales y adaptación por país e idioma. |
| **[CREADORES]** | Ficha sin preguntas bloqueantes, nombre descriptivo local y estructura promesa → "para quién" → qué lograrás → producto y bonus → FAQ (Fer; **B**); garantía de 7 a 30 días (C); Europa "desde ~14 €" al mismo precio en todos los países (Tomi; C); el motor es el backend más que el frontal (Santi, Tomi; B). |
| **No tomamos tal cual** | "85/100" sin método; cupos y contadores falsos; precio tachado "al doble" (Fer; C); bump con 40-50 % de toma (C; planificar 10-15 %); upsell de un clic (exige tarjeta guardada: excluye BLIK y otros locales, `03-stripe.md` §1.3); "con una venta ya está validado"; testimonios modelo; las condiciones fijas de Fer (precio, garantía de 7 días) y su permiso de "mencionar que se puede generar ingresos" (es promesa P2n aunque no lleve cifra, nota 25 §2.2). |

## 3. Variables

Etiquetas: [VIDEO] · [CREADORES] (A/B/C) · [NUEVO] · [DUEÑO] · [HIPÓTESIS] · [VERIFICAR] · [SUPUESTO]. Toda variable inferida lleva `origen: SUPUESTO` y `confianza`.

### 3.1 Entradas (contrato de entrada)

| Variable | Origen | Nota |
|---|---|---|
| `candidato_ref`, `macro_nicho`, `prueba_una_frase`, fichas `mecanismo{causa_raiz, nombre, como_funciona, diferencia, prueba_logica, riesgo_de_claim}` y `entregable{formato, alcance, estado_a_b, tiempo_al_primer_resultado, producibilidad, licencias}`, `riesgo{P, C, E, N, nivel, reencuadre_aplicado, claims_a_evitar, angulo_seguro}` | `candidatos.json` v2 (D1) | **Se heredan; D3 no re-elige el problema** y re-verifica el riesgo (por candidato, no por tema). `precio_plausible` y `demanda_pagada` son prior, no evidencia |
| Huecos, saturación de mecanismo, sustituto gratis, `voz_cliente`, `anuncios_competencia` | D2 | citas literales en el **idioma de la oferta** |
| `locale`, `paises_segmentacion[]`, `moneda_cobro`, `metodos_pago`, `fiscal`, `consumo{desistimiento_dias, boton_arrepentimiento}`, `cpm_esperado` | M1 (`mercado.json`; opcional `mercado.seleccion.json`) | el mercado es **hipótesis**, nunca prior. Lectura opcional de `mercado.seleccion.json#precio_referencia` (por moneda) como orientación de precio: es el artefacto de apoyo de M1, sin esquema aún (ola CT-4) y no sellado; lo que D3 necesita para sellar vive en `mercado.json`, y el precio lo fija D3. Opcional [SUPUESTO]: `mercado.seleccion.json#mix_metodos_referencia[]` como insumo del `mix_metodos` de `engine.factibilidad` (la spec de M1 aún no lo lista) |
| `tarifas.json`: comisión por método y país, recargos, IVA por país, tarifa de disputa, recargo de ubicación de Meta | F1, ≤ 30 días | sin él: `[SUPUESTO]` de `03-stripe.md` §4.1 y L1 lo marca |
| `reglas_claims`, `matriz_pais_nivel`, `ayuda_por_pais`, `terminos_sensibles/<locale>` | X1 | por jurisdicción |
| `limites.yaml` (solo lectura): `precio_neto_minimo`, `perdida_max_test_por_oferta`, `gasto_*`, `politica_reembolso_dias`, `locales_permitidos`, `paises_permitidos`, `lineas_rojas`, `nivel_max_lanzable[macro_nicho]` (objeto salud/relaciones/dinero con `verde`, `amarillo-a` o `amarillo-b`; `null` = solo verde, fail-closed: no es un dato faltante, `limites.schema` 1.3.0) | dueño | un `null` en los topes de dinero (p. ej. `perdida_max_test_por_oferta`) no impide redactar, pero la oferta queda "sin gasto autorizado" |
| `entrevista.yaml` opcional: `credencial_honesta` (default "ninguna"), `casos_previos_n` (0), `capacidad_demo`, `vetos_dueno[]`, `insight_propio` | [DUEÑO] | sin preguntas bloqueantes |

### 3.2 Variables de decisión

**Ficha sin preguntas bloqueantes** [CREADORES B, Fer]: el Maker decide con criterios explícitos (facilidad de creación, claridad, valor percibido, potencial comercial, facilidad de comunicar, producibilidad con IA, **economía del mercado**, **riesgo**) y deja las decisiones de alto impacto en `supuestos[]` para el gate H. Solo se detiene por dato de contrato ausente.

| Variable | Criterio de elección | Se testea |
|---|---|---|
| `cliente_ideal` | El del candidato, en **tercera persona de rol o situación** (E0/E1); nunca "tú + atributo" ni pregunta | D6 |
| `promesa` | Sujeto = el entregable (P0/P1); verbos de la herramienta; medida **de uso** ("90 minutos para completarlo"), nunca tiempo hasta un resultado ni dinero, salud o estado del lector; verificable por un novato cronometrado. Cifra solo como P2s (suma del propio producto, rótulo "ilustrativo" en el mismo medio; nota 25 §2.5) | 2-3 ganchos en D6 |
| `nombre`, `subtitulo` | **Nombre descriptivo en el idioma local**, sin sufijos *Studio, Academy, Master, Pro, Lab, Creative*, sin verbo de cambio, nombre de estado ("Glucosa Estable") ni "ganar" con el lector como beneficiario. **Subtítulo = promesa + diferencial** (el MU), dentro de P0/P1. Marca y dominio neutros | L1-13 |
| `marca_propuesta[]` | **Hasta 3** candidatos de marca **neutra** (sin claim de salud ni de dinero, sin imitar marcas conocidas, sin los sufijos ni el verbo de resultado vedados al nombre), cada uno con su dominio propuesto; X1 los revisa. El dueño aprueba **una** con gate H **antes** de comprar el dominio. **No se compra dominio ni se crea dataset** (irreversibles; máx. 100 por portfolio) para un candidato sin veredicto de D3 `FACTIBLE` o `AJUSTADA`. La compra es del alta de oferta (N01b de `docs/06`, entre D4 y D5): es gasto, gate H siempre, nunca de un agente | L1-13, L1-09; gate H |
| `mecanismo`, `vehiculo`, `entregables` | Los de D1: un mecanismo que nombra el procedimiento, un entregable autocontenido sin servicio, comunidad, clases en vivo ni suscripción. Si cambia la causa raíz o aparece un segundo mecanismo, **devuelve a D1** con `rechazo.motivo` canónico | intercambio; novato en D4 |
| `bonus` | **3-5**, fáciles de producir con IA, ligados al resultado, **sin** comunidad, soporte, mentoría, clases en vivo ni certificado; ninguno requisito de la promesa; **cada bonus hereda el riesgo** (uno rojo vuelve roja la oferta) | objeción n.º 1 |
| `garantia` | `reembolso_incondicional`, `dias ≥ max(politica_reembolso_dias, mínimo legal del mercado, 14)` [NUEVO, `05-legal.md` §2.1]; nunca de resultado; los 7 días de los ejemplos no son defecto. UE/UK: el desistimiento legal de 14 días es otro derecho; en contenido digital se pierde solo con consentimiento expreso y reconocimiento en casillas separadas (X1-J07, D5), la garantía comercial no lo sustituye ni oculta, y desde 2026-06-19 debe haber función de desistimiento en línea (Directiva (UE) 2023/2673 [VERIFICAR]) | `r` real |
| `urgencia`, `prueba` | `urgencia = null` salvo fecha o cupo real verificable por código (la landing de referencia del dueño ya eliminó cuenta regresiva, cupos y notificaciones). Prueba: `logica_del_producto`, `muestra`, `dato_con_fuente` o `testimonio_con_permiso`; cifras de clientes, ventas o estrellas las genera un script desde Stripe; reseñas con `compra_id` | CTR y conversión |
| `precio.lista` | **Precio local con IVA incluido** (`tax_behavior: inclusive`) en la `moneda` del mercado, con escalón local (14,90 €, 49 zł: punto de partida [HIPÓTESIS, 08 §3]); el menor con `razon ≥ 1,3` en **todos** los países del clúster y `≥ precio_neto_minimo`; ancla solo con historial real de 30 días (Ómnibus UE [VERIFICAR]) | un precio en v1; `precio_b` preaprobado: propuesta en `oferta.md` §E; no es campo de `oferta.json`. Si D8/D9 lo usan, se pide a CT en ese momento |
| `bump`, `upsell` | Bump 0-1 (precio entre `landing.bump_pct_precio_min` y `landing.bump_pct_precio_max` del precio del frontal, hoy 30-60 %, D5; recomendación [HIPÓTESIS]: ≤ 40 % mientras no haya toma real, porque el bump caro baja la aceptación; sin servicio ni requisito) para llevar el aov hacia ≥ 1,3 × el frontal (16 §2.3; creadores ≥ 1,5 [B]). Una sola fuente del tope: el parámetro (LT-35 pide a CT su hogar único). En v1 el bump se ofrece como `oferta_previa` (casilla del bump en `/comprar`, no premarcada; segundo `line_item`): el modo lo fija D5 en `checkout.json` (`oferta.json` no tiene ese campo) y `casilla_en_checkout` queda [PENDIENTE: lo construye B2] hasta probarlo en sandbox. Upsell de un clic: **desactivado** | aceptación en Stripe |
| `angulos[]` | ≥ 5 (el contrato exige ≥ 3), ≥ 3 niveles de conciencia (N1-N5 del contrato, distintos de los niveles de autonomía), **patrones seguros** del macro-nicho (nota 25 §5.1), claims ⊂ `claims_permitidos`; `angulo_id` en kebab sin `_` (alimenta los nombres de Meta, 5.2); la medición se une por `oferta_id` + `adid` (5.3), nunca por nombre. El `hook` de cada ángulo se entrega en tercera persona, sin atributo ni estado emocional del espectador y sin «tú + situación» (E ≤ E1, X1-E01); D5 y D6 lo reformulan si no, pero D3 lo entrega neutro y L1-03 lo comprueba. Los ejemplos concretos de `_ejemplo/03-oferta/oferta.json` se corrigen por LT-50 | D6/D7 |
| `riesgo` | Máximo de P, C, E y N sobre producto, nombre, marca, bonus, bump y ángulo recomendado (tabla única 25 §2.3; `python -m scripts.nivel_riesgo`, construido: única implementación de ejes a nivel, emite `version_tabla`) | L1-11 |

### 3.3 Salidas (contrato de salida)

| Artefacto | Ruta (`ofertas/<id>/03-oferta/`) | Formato y campos | Consumidor |
|---|---|---|---|
| Oferta | `oferta.json` | `contratos/oferta.schema.json` (todos los campos son obligatorios): ids y versión, `marca` (la elegida; su `dominio` es el **propuesto**, no comprado), `candidato_ref`, `macro_nicho`, `locale`, `paises_segmentacion`, `moneda`, `riesgo`, `requiere_gate_humano_legal`, `prueba_una_frase`, `mecanismo`, `promesa{…, claims_permitidos[], claims_prohibidos[]}`, `vehiculo`, `entregables`, `bonus`, `garantia`, `urgencia`, `prueba`, `precio{lista, tax_behavior, anclaje}`, `bump`, `upsell`, `angulos`, `avatar`, `puntaje`, `supuestos`, `hipotesis_test`, `aprobada_por_dueno` | D4-D7, F1, X1 |
| Economía | `economia.json` | `contratos/economia.schema.json`, generado por `engine/factibilidad`, no por el LLM; dinero `{monto en unidad menor, moneda}`, tasas en puntos básicos | D7, D8, F1 |
| Ficha | `oferta.md` (sin esquema) | Arriba: economía **por mercado**, riesgo, supuestos y `marca_propuesta[]` (hasta 3, con dominio propuesto; el esquema `oferta` aún no tiene ese campo: pedido a CT, §11). Debajo, los 12 puntos de Fer: nombre y subtítulo, concepto, público, problema y dolores, resultado y promesa, contenido completo, categorías o módulos, bonus, beneficios, objeciones, precio y garantía, llamado a la acción. Las secciones A-F de arriba (economía, riesgo, supuestos y decisiones de alto impacto en la §E, `marca_propuesta[]`; plantilla de la skill) van en español para el dueño; la ficha de 12 puntos va en el idioma de la oferta (con citas literales en su idioma original), porque es la base de D5 y la que lee el cliente frío de L3 (1). Las propuestas de tope y presupuesto van en la §E (D3 no escribe `limites.propuesta.yaml`; ver §5) | Dueño, D5 |
| Entrevista | `entrevista.yaml` (sin esquema) | Solo los opcionales del dueño, con `origen` | Maker, QA |

`angulos` y `avatar` van **dentro** de `oferta.json`. **Mapeo v1 → contrato (manda el contrato):** `mercados_objetivo[]` → `locale` + `paises_segmentacion[]` + `moneda`; `variante_es` → `locale`; `nivel_riesgo_nicho` → `macro_nicho` + `riesgo{P, C, E, N, nivel, reencuadre_aplicado}`; `politica_reembolso` → `garantia`; `FACTIBLE_CON_RIESGO` → `AJUSTADA`. `locale`, `moneda` y `precio.lista` son **únicos por oferta** (multimoneda vacía en el testeo inicial); la economía se calcula **por país del clúster**: `economia.json` guarda el peor país y la tabla por país va en `oferta.md` hasta que exista `economia.por_pais[]` (pedido a CT).

### 3.4 Parámetros y umbrales

En `empresa/parametros.yaml` (grupos `economia` y `testeo`; todos [HIPÓTESIS]; el Maker no los escribe).

`economia.razon_min_factible` "1.3" (1,1-1,6; < 1,0 NO_FACTIBLE, 1,0-1,3 AJUSTADA) · `factor_cpa_objetivo` "0.6" (0,4-0,8) · `penal_evento_senal` "1.25" (1,1-1,6; si se optimiza `InitiateCheckout`) · `tasa_bump_bp` 1000 (500-2500; los creadores dicen 30-50 % [C]) · `tasa_upsell_bp` 0 (0-800) · `tasa_reembolso_bp` 700 (300-1200) · `tasa_disputa_bp` 50 (20-100) (alarmas operativas en F1/D8, `salud_operativa.*`) · `escenarios_embudo` pes 80/70, central 120/150, opt 200/250 (CTR de enlace / clic→compra, bp; el CPM sale de `mercado.cpm_esperado`) · `precio_lista_rango` 12-29 USD eq. (fuera ⇒ H) · `puntaje_min_oferta` 75 (70-85) · `puntaje_dim_min_oferta` 3 (3-4) · `lectura_wpm_diseno` 200 (150-250) · `tiempo_diseno_max_factor` "1.10" (D4 re-mide hasta 1,25×; `tiempo_consumo_min = palabras_max/200 + minutos de ejecución`) · `umbral_qa` "4.0" (3,5-4,5; promedio R1-R11 en escala 0-5 [HIPÓTESIS], análogo a O0, D4, D5 y X2; clave nueva [PENDIENTE: la agrega CT, LT-45]) · `testeo.k_corte` 3 (2-4) · `testeo.n_dec` 15 (10-25).

**Claves nuevas propuestas** (aprobación del dueño): `economia.escenarios_costo` {pes: r 1200, d 100 · central: 800, 60 · opt: 400, 30} bp (red team 16 §2.3 [HIPÓTESIS]; hoy r y d son únicos); por país en `tarifas.json`: `iva_bp` y `recargo_meta_bp` (FR/IT/ES 300, AT 500, UK 200, PL 0; fuente secundaria de un reporte de Reuters [VERIFICAR]). D3 **consume** (no define) `limites.{nivel_max_lanzable, lineas_rojas, cuota_gasto_amarillo_max_pct}` y `salud_operativa.*` (nota 25 §10). D3 no usa `finanzas.fondo_reembolsos_*_pct` para calcular: lo consume F1 [PENDIENTE: CT, S-11 del backlog de CT-3]; D3 sigue con `tasa_reembolso_bp` y, en amarillo, la fila `pes` cuando exista. **En amarillo el costo central usa la fila `pes`** hasta tener datos propios [NUEVO][HIPÓTESIS] (el único benchmark de educación en línea da 1,02-4,79 % de contracargos, nivel C).

**Fórmulas** (las ejecuta `engine/factibilidad`; el `scripts/factibilidad.py` de la v1 se retira). Comandos, desde la raíz: `.venv/bin/python -m engine.factibilidad calcular --entradas ENTRADAS.json [--parametros empresa/parametros.yaml] [--limites empresa/limites.yaml] [--salida 03-oferta/economia.json]` y `.venv/bin/python -m engine.factibilidad verificar --economia ofertas/<id>/03-oferta/economia.json [--parametros ...]`; salida 0, 2 (uso), 3 (entrada inválida o diferencias) o 5 (falta un parámetro; con `limites.yaml` en `null` no sale 5: `limites_pendientes[]` lo lista). Por **país p** del clúster:

```
aov = P + b·Pb + u·Pu     neto = aov/(1+t_p)   (precio con IVA incluido; t_p de tarifas.json: IT 22 %, PL 23 %; tasa reducida de e-book solo con respuesta del contador [VERIFICAR])
comisiones = Σ_m mix_m·(pct_m·aov + fijo_m·(1+u) [+1,5 % internacional +1 % conversión])      (m = métodos activos de mercado.json)
stripe_tax = pct_tax·aov + fijo_tax·(1+u)      (se resta aparte de las comisiones)
mc = neto − comisiones − stripe_tax − r·neto − d·(neto + tarifa_disputa) − costo_var      (la comisión no se devuelve al reembolsar)
cpa_be = mc   cpa_be_visto = cpa_be·10000/(10000 + tarifa_meta_bp)   (el CPA de Ads Manager)   cpa_obj = f·cpa_be_visto   roas_be = aov/cpa_be
cpa_real(esc) = CPM/(1000·CTR·conv)   razon = cpa_be_visto/cpa_real(central)   razon_obj = cpa_obj/cpa_real(central)
(`tarifa_meta_bp` sale de `economia.entradas_usadas`; por país es `recargo_meta_bp` de `tarifas.json`)
presupuesto_test_min = max(5·k·cpa_be, n_dec·cpa_real(central));  diario < 0,5·(50/7)·cpa_real(central) ⇒ InitiateCheckout y cpa_real × penal_evento_senal
dias_test = max(7, ⌈presupuesto_test_min/diario⌉)   gasto_test_plan = diario·dias_test   perdida_max_test = gasto_test_plan + costos_fijos_oferta
criterios_corte: gasto ≥ k·cpa_be sin compra ⇒ pausa; "validada" = backbone 5.9 (D8)
```

**Comisión por método** [Stripe, cuenta de EE. UU.; `03-stripe.md` §4, 07e-07g]: tarjeta 2,9 % + 0,30 USD (+1,5 % internacional, +1 % conversión = 5,4 % + 0,30); BLIK 1,9 % + 0,30 con los mismos recargos (sin tarifa de disputa); Pix 1,8 % + 0,30; Managed Payments +3,5 % (**no** admite BLIK, Przelewy24 ni Satispay); Stripe Tax 0,5 % o 0,50 USD por API; disputa 15 USD. **Un método local exige su moneda local** (BLIK → PLN; Satispay, Bancontact → EUR; Pix → BRL). Hoy `mercado.metodos_pago.fase = estandar_tarjeta_billeteras` y `fiscal.regimen = diferido` (dueño, 2026-11-06): **v1 calcula con tarjeta y billeteras**; la cobertura en Polonia sin BLIK es mucho menor que el ≈ 67 % con BLIK/P24 (07g) [VERIFICAR] y los escenarios de 16 mezclan 45 % BLIK.

**Escenarios por mercado** (conservador = `pes`, base = `central`, optimista = `opt`). Red team 16 §2.3 [HIPÓTESIS; CTR y CPM de terceros, nivel C], frontal PL 49 zł / IT 14,90 € con bump (aov × 1,15 / 1,30 / 1,50); CPA de equilibrio base 11,5 (PL) y 14,8 USD (IT) frente a un CPA modelado de 25,6 y 28,0. `razon` optimista / base / conservador: PL 1,4 / 0,45 / 0,14; IT 1,6 / 0,53 / 0,17. Con 14,90 € / 49 zł y bump ×1,3 **solo el optimista pasa**: el equilibrio base exige conversión clic→compra de 3,8-4,5 % (plausible: 1,6-2,3 %). Palancas: precio, bump con toma real, IVA reducido de e-book (+19 % del neto; [VERIFICAR] con contador), mercado y mecanismo; **un frontal de ~14 € sin bump no cierra**. `razon ≥ 1,3` solo dice que el test vale la pena; escalar exige `razon_obj ≥ 1`. Veredictos (enum del contrato): `FACTIBLE` · `AJUSTADA` (H explícito) · `NO_FACTIBLE` (no pasa a D4: ≤ 2 ciclos de palancas, luego `ESCALAR`). `perdida_max_test` se compara con `limites.perdida_max_test_por_oferta` **tras convertir a `moneda_limites`** con el tipo de cambio de F1; con ese tope en `null` la economía se calcula, pero la oferta no autoriza gasto. El CPM de los tres escenarios es `mercado.cpm_esperado` (un CPM por mercado; los escenarios solo varían CTR, clic a compra y, cuando exista, r y d). Si M1 etiquetó el CPM [SUPUESTO] (vencido o ventana Q4), D3 lo hereda en `supuestos[]`; el multiplicador de estrés 1,5 es una sensibilidad de M1 (bandera), no un escenario de D3. Al sellar o cambiar `limites.yaml`, toda `economia.json` vigente se regenera (modo revisar de la skill): `limites_pendientes` debe coincidir con las claves aún en `null`.

### 3.5 KPIs del paso

| Propios | Diferidos (campaña y banco) |
|---|---|
| % aprobadas sin edición · rondas Maker↔QA · brecha de puntaje · claims ROJO = 0 · `razon` por mercado · **devoluciones a D1** por motivo canónico | Error de CPA por mercado · aov, bump, reembolso y disputa reales vs supuestos **por nivel de riesgo** · CTR y conversión por ángulo · % validada por macro-nicho, nivel y locale (realimenta el radar de D1) |

## 4. Flujo paso a paso (SOP)

| # | Actor | Acción | Se guarda |
|---|---|---|---|
| 0 | Script | Preflight: candidato congelado, D2 favorable, `PAUSA` ausente, `mercado.json` aprobado (H si es el primer lanzamiento del idioma), locale/país/macro permitidos, tarifas ≤ 30 días | `registro.jsonl` |
| 1-3 | Maker | Ficha sin preguntas (3.2); avatar con **citas textuales**; verifica la prueba de una frase y hereda MU/EU (si no se sostiene, devuelve a D1) | borrador |
| 4-6 | Maker | Nombre, subtítulo, promesa, vehículo; entregables, 3-5 bonus, garantía, urgencia, prueba; tres precios locales con IVA incluido y bump | borrador |
| 7 | Script | `engine/factibilidad` por país; `NO_FACTIBLE` ⇒ volver a 4-6 (≤ 2 ciclos) o ESCALAR | `economia.json` |
| 8 | Script + Maker | Riesgo: `nivel_riesgo` sobre todos los activos; ROJO ⇒ reencuadre RE-01…15 (máx. 2; conserva el deseo; anuncio = landing = producto) o devolución; X1 aprueba toda bajada desde ROJO o AMARILLO-B | `riesgo` |
| 9 | Maker | ≥ 5 ángulos seguros; `hipotesis_test[]` con métrica **distinguible con el volumen** (con ~15 compras un ángulo se compara por CTR y costo por checkout); hasta 3 `marca_propuesta[]` neutras; auto-puntaje; `oferta.md` | `oferta.json/md` |
| 10-12 | Script, QA | Script: los L1 deterministas (`validar_esquemas oferta`, `lint_d3 --json`, `engine.factibilidad verificar`, `nivel_riesgo`) los corre el código ANTES del QA y los deja en `ofertas/<id>/qa/.l1/d3-v<n>.json` (subcarpeta oculta; X18 solo recorre `qa/*.json`, no recursivo) [PENDIENTE: lo construye S-B: etapa de checks previa al QA del runner]. QA: L2 + L3 en contexto limpio, con esos L1 como entrada de solo lectura; ≤ 2 rondas, BLOQUEANTE persistente ⇒ `ESCALAR` | `qa/d3-v<n>.json` |
| 13 | X1 | Claims, país y nivel, incluidos los candidatos de `marca_propuesta[]`; **veto** y sello por hash | `empresa/compliance/` |
| 14 | Humano | **Gate H**: lee `oferta.md`, supuestos, nivel y veredicto; **elige la marca** de `marca_propuesta[]` (o las rechaza); aprueba, edita o rechaza. Sin marca aprobada O0 no dispara el alta de oferta (N01b) y no se compra dominio | `oferta.json` v<n> inmutable |

## 5. Agente Maker

- **Rol:** estratega de ofertas de respuesta directa (ecuación de valor, Schwartz, reversión de riesgo) con criterio de cumplimiento.
- **Alcance:** `oferta.json`, `oferta.md`, `entrevista.yaml`; `economia.json` solo vía el script. Propone; no decide dinero: las propuestas de tope y presupuesto van en `oferta.md` §E (no es una salida); el archivo `empresa/propuestas/limites.propuesta.yaml` lo escribe `.venv/bin/python -m engine.propuestas proponer --oferta <id>` a partir de `economia.json` (existe; el dueño lo sella con `sellar`). D4 sí escribe su propio `04-producto/limites.propuesta.yaml`.
- **NO hace:** inventar datos, testimonios, cifras o credenciales; prometer dinero o salud; garantizar resultados; escasez o precio de referencia falsos; calcular economía "a ojo"; cambiar el problema de D1; modificar `limites.yaml`, `parametros.yaml` o `contratos/**`; publicar, crear productos o tocar Meta/Stripe; depender de Venzio.
- **Herramientas (mínimo privilegio; `docs/09` §8.1: D3 no usa web ni MCP en ningún nivel):** lectura de `ofertas/<id>/`, `empresa/` y `docs/`; escritura solo en el staging de `03-oferta/` (hook `PreToolUse` sobre `file_path`); Bash limitado a `python -m engine.factibilidad`, `python -m scripts.validar_esquemas`, `python -m scripts.nivel_riesgo` y `python -m compliance.lint_claims` (el envoltorio `scripts/lint_claims.py` falla sin `PYTHONPATH`) [PENDIENTE: lo construye S-B (B9): inscribir estas formas en `agentes/hooks/herramientas.yaml`, que hoy solo lista `scripts/<x>.py`]; sin WebSearch, WebFetch ni `mcp__*`; ningún `create_/update_/activate_`. La competencia y la voz del cliente entran por `anuncios_competencia.json` y `voz_cliente.json` de D2 y el mercado por `mercado.json` de M1: D3 debe poder completar la oferta solo con archivos de D1, D2 y M1.
- **Contexto:** 3.1, skill D3, fallas conocidas (X2), glosario del locale (`empresa/mercados/glosarios/<locale>.md`).

## 6. Agente QA

**Independencia:** contexto limpio; recibe oferta v<n>, contrato 3.3, `candidatos.json`, `mercado.json`, `00-brief.yaml`, D2, `parametros.yaml`, `limites.yaml`, `tarifas.json`, reglas de X1, rúbrica y fallas conocidas; **no** el razonamiento ni el auto-puntaje del Maker. Solo lectura (`docs/09` §9.2): sin Write, Bash ni MCP; devuelve el informe por `structured_output` y el runner lo persiste en `qa/d3-v<n>.json`: hallazgos estructurados (`check_id`, `patron_clave`, `severidad`, `etapa`, `skill_version`) y `aprendizajes_para_skill[]`. Los L1 deterministas los produce el código antes del QA (SOP 10-12) en `ofertas/<id>/qa/.l1/d3-v<n>.json` y el QA los copia a `checks_l1` del informe; nunca como `qa/d3-v<n>-l1.json` (X18 valida todo `qa/*.json` contra `qa.schema`) ni en el staging (el QA tiene deny de `.staging/**` ajenos y de `runs/**`, `docs/09` §10); ruta única para todas las etapas (conflicto C-01 del consolidado de la ingesta). No corrige: devuelve la corrección por hallazgo (campo `correccion`) y el Maker aplica el parche en la ronda siguiente (máx. 2 rondas; no hay rama `qa/`). Sin checkpoint QA-A (D3 no gasta créditos).

### Checks deterministas (L1)

| ID | Check | Falla |
|---|---|---|
| L1-01 | `scripts.validar_esquemas oferta ofertas/<id>` pasa; ids y versión coherentes | BLOQUEANTE |
| L1-02 | Precio, bump, upsell, moneda y garantía idénticos en `oferta.json`, `oferta.md`, `economia.json`; `vehiculo.tiempo_consumo_min` (estimado de **diseño**: lectura) ≤ `parametros.economia.tiempo_diseno_max_factor` (1,10) × `promesa.tiempo_prometido_min` (única fuente; D4 mide lectura + ejecución con tope 1,0× estimado y `producto.cold_run_tolerancia` 1,25× en frío y nunca cambia la promesa: la devuelve a D3; R10) | MAYOR |
| L1-03 | Linter de claims **por idioma** (`terminos_sensibles/<locale>`): ROJO = 0 en nombre, subtítulo, ángulos, bump, bonus y garantía; AMARILLO con evidencia | BLOQUEANTE |
| L1-04 | Recómputo con `tarifas.json` y `parametros.yaml`: diferencia ≤ 1 % y mismo veredicto; escenarios y tasas iguales a `parametros.yaml` o con override fuente D2/M1; si la razón solo pasa con override, MAYOR | BLOQUEANTE |
| L1-05 | Tarifas ≤ 30 días; locale/país permitidos; `tax_behavior` definido; método local ⇒ moneda local; `garantia.dias` ≥ mínimo legal y ≥ `politica_reembolso_dias`; `boton_arrepentimiento` declarado para D5 | BLOQUEANTE |
| L1-06 | `urgencia ≠ null` ⇒ `verificable_por` (fecha o contador real sin reinicio); `prueba[]` solo tipos del contrato; testimonio ⇒ `consentimiento_ref`; sin cifras de personas si `casos_previos_n = 0` | BLOQUEANTE |
| L1-07 | Toda cita existe literal en `voz_cliente.json`; cada objeción tiene `respuesta_en`; cada ángulo, nivel, objeción y `claims_ref ⊂ claims_permitidos` | MAYOR |
| L1-08 | Precio ≥ `precio_neto_minimo` y en `precio_lista_rango`; `perdida_max_test` ≤ tope (misma moneda); 1,75 × diario ≤ gasto diario máximo | BLOQUEANTE |
| L1-09 | Sin marcas de terceros en nombre/promesa (`05-legal.md` P-03) ni Venzio; sin ≥ `compliance.ngrama_copia_palabras` (8) palabras consecutivas idénticas a `anuncios_competencia.json` (entre `ngrama_alerta_temprana_palabras` (6) y 8: alerta, no bloqueo) | MAYOR |
| L1-10 | Ningún "precio normal/valor real" sin historial; comparación con fuente y fecha | BLOQUEANTE |
| L1-11 | `riesgo.nivel` = máximo de P, C, E, N; macro permitido; `nivel ≤ limites.nivel_max_lanzable[macro_nicho]` (`null` = solo verde); cada país admite el nivel (matriz de X1); AMARILLO ⇒ `requiere_gate_humano_legal = true` (nombre heredado del contrato: es el gate H del dueño, no una revisión de abogado; decisión 14); ROJO ⇒ FAIL | BLOQUEANTE |
| L1-12 | Promesa, nombre y subtítulo no contradicen ni exageran la ficha MU/EU; entregable único; `bonus`, `bump` y `entregables` sin comunidad, soporte, mentoría, clases en vivo ni servicio humano; ningún bonus eleva el nivel | BLOQUEANTE |
| L1-13 | Nombre sin sufijos *Studio, Academy, Master, Pro, Lab, Creative*, verbo de cambio, nombre de estado, "ganar" o "cura" como resultado (X1-P07), ni idioma del nombre distinto del `locale`; `marca_propuesta[]` ≤ 3, neutras (sin claim de salud ni de dinero ni marca conocida: L1-09) | BLOQUEANTE (detiene; decide una persona) |
| L1-14 | UE/UK: garantía comercial separada del derecho legal; renuncia y función de desistimiento delegadas a D5/X1-J07, sin promesa que las contradiga | BLOQUEANTE |
| L1-15 | Descargos y ayuda del macro-nicho declarados para D4/D5 (conflicto de pareja o familia: aviso de seguridad y línea de ayuda del país) | MAYOR |

### Rúbrica, simulaciones y calibración

**L2** (0-5 con evidencia citada; sin evidencia = 0): R1 Promesa · R2 Cliente · R3 Mecanismo · R4 Vehículo · R5 Reversión de riesgo · R6 Prueba sin testimonios · R7 Precio y ancla · R8 Bump/upsell · R9 Ángulos · R10 Voz y objeciones · **R11 Riesgo y cumplimiento** (anclas en A.2). **Puntaje 0-100** [NUEVO; pesos HIPÓTESIS]: promesa 20 · confianza en el resultado 20 · tiempo hasta el avance 15 · facilidad de aplicar 15 · tranquilidad al comprar 15 · motivos para decidirse 15. **Anti-autocomplacencia:** el QA puntúa a ciegas y vale el **menor**; brecha > 10 = MAYOR; topes: sin prueba verificable, confianza ≤ 3; garantía condicionada, tranquilidad ≤ 3; tiempo descalzado, tiempo ≤ 2; `NO_FACTIBLE` ⇒ total ≤ 59; claim ROJO ⇒ 0; X2 lo correlaciona con CTR y conversión.

**L3:** (1) **cliente frío**, en el idioma de la oferta, lee solo `oferta.md` y responde qué es, para quién, cuánto, qué recibe, cuándo y qué pasa si no sirve (≥ 5/6); (2) **comprador escéptico**, 3 corridas; (3) **revisor Meta/Stripe por país**: atributos personales, ingresos, urgencia, categoría especial; (4) **analista adversarial**: costos duplicados y CPA doble del central; (5) **intercambio**: si un competidor puede usar el texto cambiando el nombre, R3 ≤ 2; (6) **segunda lectura nativa** de título, subtítulo y ángulos (5.10).

**Mejoras de valor:** mecanismo con nombre propio; bonus barato contra la objeción n.º 1; precio mínimo con `razon ≥ 1,3`; muestra de 1 página; `precio_b` preaprobado (propuesta en `oferta.md` §E; no es campo de `oferta.json`; si D8/D9 lo usan, se pide a CT en ese momento); vocabulario por locale. `PASS` = 0 BLOQUEANTES y 0 MAYORES abiertos, `qa.puntaje_global` (media de R1-R11, 0-5) ≥ `qa.umbral` (= `economia.umbral_qa`; convención `<grupo>.umbral_qa`, conflicto C-12 del consolidado; `orquestador.umbral_pass_o0` es de O0 y no corresponde), y el puntaje ciego 0-100 ≥ `economia.puntaje_min_oferta` con ninguna dimensión < `economia.puntaje_dim_min_oferta`. El puntaje ciego se registra en `simulaciones_l3` con nombre `puntaje_ciego` hasta que `qa.schema` tenga campo propio (CT-4); vale el menor entre el del QA y el del Maker; brecha > 10 = MAYOR. Otros veredictos: `PASS_CON_NOTAS` · `FAIL` · `ESCALAR`; ≤ 2 rondas; siempre ≥ 3 hallazgos o evidencia de lo revisado. **Calibración:** defectos sembrados S1-S25 (A.1; ≥ 3 nichos y ≥ 2 idiomas; ≥ 18 de los 20 bloqueantes, 90 %) y dorados que dan PASS; los casos de `docs/_historial/hwr-semillas/casos-frontera.yaml` sobre P, E y N son la suite de D3: **falsos negativos peligrosos = 0**.

## 7. Gates y autonomía

| Nivel | D3 | Gate (`gates.json`) |
|---|---|---|
| N0-N1 | Dueño o Maker con skill; el dueño revisa todo | H total |
| N2 | Maker + QA + scripts L1 | **H siempre** sobre la oferta |
| N3 | Gate **S** si VERDE, país y nivel admitidos por la matriz de X1, 0 AMARILLOS abiertos, `razon ≥ 1,5`, locale ya lanzado, QA PASS sin notas | S; **H** si cambia macro-nicho, locale/país, garantía o precio fuera de rango, hay `override`, el nivel es AMARILLO-B o ROJO reencuadrado, o salta una bandera L1/L2 |
| N4 | El botón dispara D3; muestreo semanal | S + revisión semanal; H en `AJUSTADA` |

**Siempre determinista:** economía y veredicto, linters de claims y nombre, nivel de riesgo (el LLM no baja un nivel que el lint subió), tope de pérdida, precio mínimo, vigencia de tarifas, permitidos, `PAUSA`. **El veto y el sello por hash de X1 no se relajan con el nivel.** **Para ascender** [HIPÓTESIS]: N1→N2: 5 ofertas con ≤ 3 ediciones y 0 sembrados sin detectar. N2→N3: ≥ 10 ofertas en ≥ 2 macro-nichos y ≥ 2 idiomas, ≥ 70 % sin edición, recall de sembrados ≥ 90 %, error mediano de CPA ≤ 35 % en ≥ 5 tests, 0 incidentes de cumplimiento. N3→N4: ≥ 20 ofertas, 0 ROJO escapados, reembolso y disputa dentro de lo supuesto por nivel. Un ROJO escapado baja la etapa.

## 8. Riesgos y modos de falla

| Riesgo | Señal temprana | Mitigación | Responsable |
|---|---|---|---|
| Oferta inviable en su mercado | `razon < 1,3` en algún país; CPA del test > central | Economía por país; corte `k·cpa_be`; quitar el país | Script / F1 |
| Claim de ingresos, salud o relaciones; nombre que enuncia resultado | Linter ROJO; X1-P07; anuncios rechazados | Vender el entregable; RE-01…15; H en amarillo-B | X1 / QA |
| Una cuenta de Meta y una de Stripe sostienen todo | Rechazos; reembolsos > 8 %; disputas > 0,2 % | Nivel por candidato; cuota amarilla; pausa al primer rechazo de producto | X1 / F1 / D8 |
| Economía con método o impuesto equivocado | Mix BLIK con locales diferidos; IVA omitido | Tarifas por método y país; solo tarjeta y billeteras en v1 | Script / QA |
| Garantía o desistimiento mal diseñados; escasez o prueba falsas | `r > 10 %`; `d > 0,3 %`; urgencia sin `verificable_por` | Reembolso fácil antes de la disputa; L1-05, L1-06, L1-10, L1-14 | D5 / D10 / X1 |
| Puntaje inflado; economía "afinada" para pasar | Brecha > 10; override de escenarios | Doble puntaje ciego; L1-04 | Script / QA |
| Promesa que exagera la ficha MU/EU; mala localización; copia | Dos "cómo"; cita no literal; similitud | L1-09, L1-12; devolución a D1; retraducción | QA / D6 |

## 9. Mejoras respecto del video

Priorizadas [NUEVO]: (1) **compuerta de factibilidad por mercado** antes de D4 (IVA, comisión por método, recargo de Meta, reembolsos, disputas, escenarios); (2) **riesgo por candidato**, ángulos seguros, marca neutra y veto de X1; (3) **ficha sin preguntas bloqueantes** (Fer) con MU/EU heredados; (4) puntaje auditable; (5) bump para diluir comisión fija y disputa; (6) reembolso incondicional ≥ 14 días separado del desistimiento legal; urgencia y prueba solo reales; (7) localización por locale y familias; sin Venzio.

## 10. Forja de la skill (pestaña Code)

### 10.1 Prompt de arranque (copiar y pegar)

```
ROL: Estratega de ofertas de respuesta directa para productos digitales de bajo ticket (guías, plantillas, hojas de cálculo, packs) vendidos con anuncios en Meta hacia una landing propia con Stripe, en cualquier mercado e idioma. Cumplidor por construcción pero criterioso: el riesgo se evalúa por candidato, no por tema.

DIRECTORIO: abrí la sesión en <carpeta del proyecto>. LEE PRIMERO: docs/_backbone.md (v2.2: 3.1, 5.1-5.11, 6); departamentos/04-oferta.md (3, 6, Anexo); docs/contratos.md; contratos/oferta.schema.json y economia.schema.json; ofertas/_ejemplo/03-oferta/; docs/_investigacion/25-marco-salud-relaciones-dinero.md (§2, §4, §5), 03-stripe.md §4, 16-red-team-mercados-y-modelo.md §2, 05-legal.md §2; docs/fuente/landing-fer/prompt-1-crear-oferta.md (solo la estructura de ficha).

ENTRADAS (mercado e idioma son ENTRADA): ofertas/<oferta_id>/{00-brief.yaml, mercado.json, 01-descubrimiento/candidatos.json (candidato elegido con mecanismo único, entregable único y riesgo), 02-validacion/{validacion,voz_cliente,anuncios_competencia}.json} y, en solo lectura, empresa/{parametros.yaml, limites.yaml, finanzas/tarifas.json, compliance/*}. Modo práctica (sin carpeta de oferta): copiá ofertas/_ejemplo/ a ofertas/OF-AAAAMM-9N/ (id válido; convención de práctica NN ≥ 90, que `orq crear` no asigna, pero numera desde el máximo del mes: borrá la carpeta de práctica al terminar) [SUPUESTO: confirmar con B1] y pedime locale, país, moneda y candidato. Sin tarifas.json: 03-stripe.md §4.1 con [VERIFICAR]. CPM, CTR y conversión son [HIPÓTESIS]; todo otro dato faltante, [SUPUESTO].

TAREA: v1 completo en ofertas/<oferta_id>/03-oferta/: oferta.json (angulos y avatar dentro), economia.json (SOLO del motor engine/factibilidad; si no existe, un borrador [HIPÓTESIS] y avisame), oferta.md (economía por país, riesgo y supuestos arriba; debajo la ficha de 12 puntos de Fer) y entrevista.yaml solo con lo opcional.
1) No me hagas preguntas: decidí por criterios explícitos y listá las decisiones en supuestos[]; parate solo si falta un dato de contrato.
2) Heredá la ficha de mecanismo y entregable únicos; promesa, nombre y subtítulo no pueden contradecirla ni exagerarla; si no se sostiene, devolvé a D1 con el motivo canónico.
3) Nombre descriptivo en el idioma local, sin Studio/Academy/Master/Pro/Lab/Creative ni verbos de cambio o nombres de estado; subtítulo = promesa + diferencial; 3-5 bonus fáciles de producir, SIN comunidad, soporte, mentorías ni clases en vivo.
4) Promesa sobre el contenido (verbos de la herramienta, medida de uso; sin dinero, salud, atributos del lector ni plazos de resultado). Recalculá riesgo {P, C, E, N, nivel, reencuadre_aplicado}; ROJO ⇒ reencuadre RE-xx (máx. 2) o devolución.
5) Precio local con IVA incluido, garantía (reembolso incondicional ≥ 14 días y ≥ mínimo legal) y bump salen de la economía del mercado, no son fijos. UE/UK: la garantía no sustituye el desistimiento ni su función en línea (desde 2026-06-19). Urgencia y prueba social solo reales.
6) Economía por país con IVA, método de pago (v1: tarjeta y billeteras), recargo de Meta y escenarios pes/central/opt; informá razon y razon_obj. NO_FACTIBLE ⇒ palancas (máx. 2 ciclos) o escalá. Con limites.yaml en null, la oferta queda sin gasto autorizado.
7) ≥ 5 ángulos seguros en ≥ 3 niveles de conciencia, con objeción, prueba y cita literal; hipótesis de test con métrica distinguible; auto-puntaje con evidencia.
Validá: .venv/bin/python -m scripts.validar_esquemas oferta ofertas/<oferta_id>

ACEPTACIÓN: validar_esquemas pasa; 0 claims ROJO; riesgo = máximo de los 4 ejes; cada número con fórmula o etiqueta; citas literales de voz_cliente.json; precio, bump y garantía idénticos en todos los archivos.

REGLAS: no inventes datos, testimonios, cifras ni credenciales; nada con costo o efecto externo (Meta, Stripe, Shopify, publicar, gastar); escribí solo en ofertas/<oferta_id>/03-oferta/; no modifiques contratos/**, empresa/limites.yaml, empresa/parametros.yaml ni departamentos/*; no sobreescribas versiones aprobadas (creá v2). Terminá con: supuestos, preguntas abiertas y 5 cosas que yo debería pulir.
```

### 10.2 Cómo pulir

Máximo 2 sesiones de 90 minutos por oferta de práctica, 3 ofertas (macro-nichos e idiomas distintos). Preguntas: ¿entiendo la oferta en 10 segundos?; ¿pagaría y qué me frenaría?; ¿y si el CPA real es el doble?; ¿el nombre dice un resultado?; ¿qué frase borraría un revisor de Meta?; ¿el cliente reconocería la promesa en su idioma?

### 10.3 Estructura de la skill a generar

```
.claude/skills/d3-arquitectura-oferta/
├── SKILL.md   rubric.md   evals/ (dorados, sembrados, casos de frontera)
├── references/    # desistimiento y garantías por mercado, tarifas e IVA, reencuadres, claims por macro-nicho, ejemplos por idioma, Anexo
├── templates/     # oferta.md de 12 puntos, entrevista.yaml
└── scripts/       # envoltorios de engine/factibilidad, lint_claims.py
.claude/agents/d3-maker.md   .claude/agents/d3-qa.md
```

### 10.4 Definición de listo (DoD)

(a) 3 ofertas de práctica, una por macro-nicho y en ≥ 2 idiomas, con ≤ 3 ediciones; (b) `engine.factibilidad` reproduce `ofertas/_ejemplo/03-oferta/economia.json`, los vectores de `tests/contratos/test_factibilidad.py` (24,42; 16,25; 11,54) y los 3 veredictos; los casos PL/IT de 16 §2.3 (±1 %) quedan [PENDIENTE: `parametros.economia.escenarios_costo` y `mix_metodos` con tarifas de F1]; (c) el QA detecta ≥ 90 % de los bloqueantes sembrados y da PASS a los dorados; (d) 0 claims ROJO y 0 falsos negativos peligrosos en los casos de frontera; (e) Maker y QA difieren ≤ 10 puntos en 80 % de los casos; (f) `validar_esquemas oferta` pasa; (g) los evals 2-6 pasan sin editar la skill entre uno y otro.

### 10.5 Evals mínimos

1. **Dinero (es-ES):** reinserción laboral tras una pausa (`ofertas/_ejemplo`), verde. 2. **Dinero, dos idiomas:** "presupuesto por fecha de cobro" en pl-PL (49 zł) e it-IT (14,90 €), dos `oferta_id` de una familia; con BLIK diferido el caso base es `NO_FACTIBLE`. 3. **Salud (it-IT):** planificador semanal de comidas; "perdi 8 kg in 30 giorni" ⇒ ROJO ⇒ RE-02. 4. **Relaciones (pl-PL):** tarjetas de conversación para parejas, sin "randki"; duelo o ruptura ⇒ amarillo con bloque de ayuda. 5. **Manualidades:** "ganá USD 500 con velas" ⇒ ROJO ⇒ costeo y precio mínimo (verde); como pasatiempo ⇒ `fuera_de_macro_nicho`. 6. `NO_FACTIBLE` forzado (ticket 7 USD) y 30 USD/día con `InitiateCheckout`. 7. Sin casos previos: ni cifras de alumnos ni citas inventadas. 8. Locale sin `mercado.json` aprobado: se detiene. 9. `limites.yaml` en `null`: sin gasto autorizado. 10. Defectos S1-S25.

## 11. Preguntas abiertas / decisiones del dueño

1. **Pérdida máxima por oferta**, presupuesto diario y precio neto mínimo: diferidos; hasta fijarlos ninguna oferta autoriza gasto.
2. **Régimen fiscal y métodos locales** (IVA/OSS, Stripe Tax o Managed Payments, BLIK/P24): diferidos; v1 calcula con tarjeta y billeteras.
3. **Reembolso:** ¿14 días incondicional como piso [recomendado] y 30 como variante?
4. **Primer mercado y primera oferta:** los decide el dueño [DUEÑO] con la propuesta de M1 (ranking sin criterio de pagos en `scripts/mercados/rank_sin_pagos.py` y cobertura de pago real); **un mercado a la vez** (`empresa/parametros.yaml`: `mercados_test_paralelos_max` = 1), sin par de arranque. Polonia e Italia son **hipótesis** a contrastar con datos propios; con los pagos diferidos (solo tarjeta y billeteras) Polonia no pasa la regla R6 de M1 (cobertura de pago ≈ 17 % frente a un mínimo duro de 40 %) y se evalúa solo si el dueño habilita métodos locales. Tipo de IVA del PDF según el contador.
5. **Ticket mínimo** y apetito por `AJUSTADA`; ¿bump en v1 [recomendado]?
6. **Marca:** "marca y dominio por oferta" es un **[SUPUESTO]** hasta que el dueño lo confirme: a la pregunta respondió «no aplica creo» (primera sesión, respuesta 3; `docs/_historial/auditoria-pedidos-primera-sesion.md` C-11; backbone §2.9). "Clay Art Studio™" (ejemplo de la decisión 9) choca con la regla de Fer y la marca neutra: ¿sufijos solo en la marca, nunca en el nombre del producto? La elección entre los candidatos de `marca_propuesta[]` es gate H (paso 14).
7. **Amarillo:** aprobar el costo central con la fila `pes`, `nivel_max_lanzable`, cuota amarilla y líneas rojas (nota 25 §12.4).
8. Credencial afirmable; identificación pública del vendedor; soporte y actualizaciones.
9. [VERIFICAR] Políticas de Meta sobre garantías, urgencia y resultados irreales (Transparency Center: 404); art. 16(m) de la Directiva 2011/83/UE y Directiva (UE) 2023/2673 en EUR-Lex; recargo de ubicación de Meta; mínimos legales de reembolso por país.
10. **Pedido a CT** (esquema `oferta`, MINOR): campo opcional `marca_propuesta[]` (hasta 3 `{nombre, dominio}`; hoy `oferta.schema.json` no lo admite y `marca{nombre, dominio}` exige un dominio ya en D3, cuando todavía no se compró). Mientras tanto viaja en `oferta.md`. El alta (`ofertas/<id>/infra/alta.json`, `infra.alta_oferta` y `infra/plantillas/alta-oferta.yaml`) está construido por S-B (B8b, verificado el 2026-11-06); el esquema de `alta.json`, pedido a CT-3.

## Anexo (se traslada a `references/` de la skill)

### A.1 Defectos sembrados (≥ 3 nichos y ≥ 2 idiomas)

BLOQUEANTES: S1 "ganá USD 500 en 7 días" · S3 "solo 50 copias" sin contador · S4 `cpa_be < cpa_real` y el texto dice "rentable" · S6 testimonio sin fuente · S7 "resultados garantizados" con otra política de reembolso · S10 "¿Estás endeudado?" (E2) · S13 "valor real 197, hoy 17" sin historial · S14 CTR/conversión editados para que la razón dé 1,4 · S15 upsell `off_session` sin botón · S16 nombre "Glucosa Estable" o "Cero Deudas" · S18 promesa con dos mecanismos o contraria a la ficha MU/EU · S19 bonus "grupo privado" o "sesión 1:1" · S20 BLIK con precio en EUR o con `fase = estandar_tarjeta_billeteras` · S22 garantía que oculta el desistimiento (UE/UK) · S23 reseña con cifra o antes/después · S24 reencuadre que solo cambia sinónimos · S25 AMARILLO-B sin gate H o país fuera de la matriz · **S5** economía sin comisión fija ni IVA (L1-04) · **S17** nombre con sufijo *Studio/Pro* o en inglés en it-IT (L1-13) · **S21** precio sin IVA para consumidor UE (L1-05/L1-04). Un defecto cuyo check es BLOQUEANTE es BLOQUEANTE: son **20** (los 17 anteriores más S5, S17 y S21).
MAYORES (5): S2 PDF de 60 páginas "en 20 minutos" · S8 cita inventada · S9 bump necesario para la promesa (si se quiere BLOQUEANTE, agregar «bump requisito de la promesa» a L1-12) · S11 auto-puntaje 90 sin prueba · S12 depende de Venzio (L1-09 es MAYOR). MENOR: ninguno.

### A.2 Anclas de la rúbrica (1 / 5; el 3 es el punto medio)

R1 vaga / verbo de la herramienta + medida de uso verificable · R2 "todos" / dolor reciente + anunciantes que ya le venden (D2), en 3.ª persona · R3 genérico / nombra el procedimiento y ocupa un hueco de D2 · R4 no resuelve el bloqueo / consumo < promesa · R5 ninguna u oculta / incondicional, visible, ≥ mínimo legal · R6 sin respaldo / muestra + lógica del producto · R7 sin lógica / fundado en `razon` por país, ancla con fuente y fecha · R8 irrelevante o requisito / siguiente paso dentro del rango del parámetro, con margen · R9 mismo mensaje / ≥ 5, ≥ 3 niveles, seguros, con objeción, prueba y cita · R10 jerga / citas con fuente, priorizadas · R11 nivel mal calculado / ángulo seguro, reencuadre, descargos y mercado verificados.
