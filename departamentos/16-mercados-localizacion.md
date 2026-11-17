# M1 — Mercados, idiomas y monedas (selección y localización)
> Empresa + por oferta · Cadencia: atlas mensual y por evento; selección una vez por oferta (antes de D2); localización bajo demanda de D3-D6 y D10 · Gate por defecto: H en el primer lanzamiento en un país o idioma nuevo (S desde N3) · Estado de la skill: forjada v0.1 sin pulir (`.claude/skills/m1-mercados-localizacion/`)

> **Estado de insumos (2026-11-06, revisión QA independiente).** Existen backbone v2.2.4, `contratos/mercado.schema.json` 1.1.0, `empresa/{limites,parametros}.yaml` (grupo `mercados` con solo 4 claves, §3.4), las notas de investigación y la **implementación de referencia: `scripts/mercados/rank.py`** (datos en `scripts/mercados/datos/`; `python3 -I scripts/mercados/rank.py [--todos | --escenario corregido | --grid]`) más `rank_sin_pagos.py`. `rank.py` **no cubre** (`[SUPUESTO]` hasta que exista): EXPO, cobertura de pago **por fase** (su `cobertura_central_pct` es la de 08, *con* locales: Polonia 67 %), rama Managed Payments y R1-R10. También existen `engine/factibilidad.py` (CPA de equilibrio y margen por pedido; no calcula `r` ni `conv_esp` y no sustituye a `rank.py`), `tests/mercados/test_rank.py`, `docs/_historial/d1-v2-interfaces.md` §4.2 (confirma los nombres de M1 en la interfaz con el radar: §3.3, §4 pasos 13-15, Anexo B) y `departamentos/02-descubrimiento.md` (el radar de D1). **No existen** `scripts/mercados/{puntaje,lint_locale,vigencia}.py` (hoy v0.1 en la carpeta de la skill, `.claude/skills/m1-mercados-localizacion/scripts/`; destino `scripts/mercados/`), `empresa/mercados/`, `empresa/compliance/{paises,matriz_pais_nivel,ayuda_por_pais}.yaml` ni `empresa/infra/stripe.yaml`. Cuando D1 y M1 difieran en un nombre de la interfaz, manda D1.
> **Regla de precedencia.** Manda el contrato. Conflictos resueltos aquí: (1) `mercado.json` 1.1.0 solo admite `card/apple_pay/google_pay/link` y régimen `diferido` (decisión del dueño de diferir los métodos locales): lo que M1 recomienda más allá va a un archivo hermano `mercado.seleccion.json`, no al sellado; (2) la nota 08 §5.6 dice que un país nuevo dentro de un idioma validado es automático, pero backbone 5.5 y `gates.json` (`etapa:M1`, `accion:lanzamiento_pais_idioma_nuevo`) lo hacen H hasta N2: manda el backbone; (3) `parametros.mercados.mercados_test_paralelos_max = 1` frente al "K ≤ 3" de 08: manda el parámetro; (4) el dueño decidió que el ajuste de creadores **no pesa en la decisión final**: M1 lo calcula y lo muestra, con peso 0 en el puntaje que decide; (5) la v1 de esta especificación exigía a la vez cobertura ≥ 55 % (R6) e «Italia elegida en fase vigente» (cobertura 46-50 %): se separa en umbral duro 40 % y blando 55 % (§3.4); (6) `r` de las bandas de CAC es **sin bump** (como 08 y `rank.py`; si no, no se reproducen los totales de 08) y el bump solo entra en R9 como `r_b = r/1,5`; (7) la fórmula de disputas se alinea a `rank.py` (16 §2.1) y se registra la divergencia con D3 (`d × (neto + tarifa)`), a unificar en `engine.factibilidad` (pedido de D3).

## 1. Misión y posición en el flujo

Decidir **en qué idioma, país, moneda y con qué métodos de cobro se testea cada oferta**, y hacer que todo texto de cara al cliente sea nativo del `locale`. Es la unión entre el candidato de D1 (qué problema) y el resto del pipeline (D2-D7), y la memoria de qué mercados conocemos y con qué grado de certeza. Ningún mercado es un prior: `estado_decision = hipotesis` hasta tener datos propios `[DUEÑO]`; Polonia, Italia o cualquier otro entran por puntaje, no por impresión.

- **Recibe de:** D1 (`candidatos.json`; banco y señales por `locale`; hipótesis de transferencia entre idiomas), O0 (brief), D2 (solo de ofertas **anteriores** del mismo `locale`, vía X2; la sonda de la oferta en curso la hace M1 en la ficha y D2 la profundiza después: M1 no depende del `validacion.json` de la misma oferta, `DEPENDENCIAS` del validador: M1 ← D1 y D2 ← D1, M1; W3-R09), D3/F1 (tarifas, economía realizada), D8/D9 (RPC/CPC, `expansion.json`), X1 (`paises.yaml`, `matriz_pais_nivel.yaml`, `ayuda_por_pais.yaml`, veto), D0 (`empresa/infra/stripe.yaml.metodos_pago[]` = lo habilitado) [PENDIENTE: lo construye S-B/D0]; hasta entonces la fuente es la captura `docs/fuente/stripe-metodos-de-pago-habilitados.md` [VERIFICAR], `limites.yaml` (`paises_permitidos`, `locales_permitidos`), memoria X2.
- **Entrega a:** D3, D5, D6, D7, D9 (`mercado.json`), D2/D3 (`mercado.seleccion.json`, artefacto de apoyo que no se sella: informativo para el dueño, D2 y D3; lo que D3/D5 necesitan para sellar vive en `mercado.json`), D1 (`locales_activos.yaml`, `terminos_busqueda/`, veredicto de viabilidad por locale), D4/D5/D6/D10 (glosarios y reglas de locale).
- **Dos funciones:** (A) *selección*: empareja candidato × mercado y emite el mercado de la oferta; (B) *localización*: capacidad transversal (glosarios, adaptación cultural, QA lingüístico). M1 **no** fija precio (D3), no clasifica riesgo (D1/X1), no escribe landings ni anuncios, no activa ni gasta.

## 2. Qué dice el video (y qué no dice)

**[VIDEO] Hace:** nada de mercados: vende un producto único en un idioma. **Omite:** país, moneda, impuestos, métodos de pago, idioma legal, CPM por país, qué lanzar dónde.

**[CREADORES]:** filtran por idioma y eligen países dentro de él [tomi-trimb/TMUoC_w5mog @ 14:04] (A); podan países por ingreso por clic ≥ CPC [santiago-bilbao/ElvFpYsjNRA @ 05:35] (B); Italia tiene 27 videos con cifras, Polonia 0 lanzamientos (C-B, nota 06).

**No tomamos tal cual:** (1) ROAS europeos de creadores: techo sin CMP, IVA, desistimiento ni reembolsos (16 H4); (2) "competencia baja = oportunidad" (16 H7); (3) "una cuenta por idioma" (no replicable); (4) "no se preocupen por el IVA si todavía no vendieron" (en la UE corre desde la primera venta, 05 §6.1); (5) que el orden de 08 sea rentabilidad: es **orden de prueba y facilidad operativa** (confianza global C).

## 3. Variables

### 3.1 Entradas (contrato de entrada)

| Variable | Tipo | Origen | Oblig. | Ejemplo / valores |
|---|---|---|---|---|
| `candidatos.json` (`candidato_id`, `problema_id`, `macro_nicho`, `riesgo{P,C,E,N,nivel,categoria,claims_a_evitar,angulo_seguro,reencuadre_aplicado}`, `precio_plausible{min,max,razon}`, `ventana_estacional`, `palabras_clave_voz_cliente`) | JSON | D1 | sí | contrato `candidatos` 1.0.0. `riesgo.banderas` y `macro_secundario` **no existen aún en el esquema** (nota 25 §2.7, pedido en `oferta`): hasta entonces EXPO/R3 usan `categoria` + `macro_nicho` y marcan `[SUPUESTO]` |
| `hipotesis_transferencia` {`problema_id`, `locale_origen`, `locale_destino`, `mecanismo_traducible`} | JSON | D1 `[NUEVO, propuesta]` | no | es-ES → it-IT |
| `limites`: `paises_permitidos`, `locales_permitidos`, `gasto_total_test_por_oferta`, `perdida_max_test_por_oferta` | listas / enteros | dueño | sí; **vacío o `null` ⇒ salida 5 (fail-closed)** | `["IT","PL"]` |
| `apetito_riesgo` | enum del brief (`conservador·moderado·agresivo`) | brief | sí | uno de los tres valores del brief. `acepta_diferido_fiscal` no es entrada: es la existencia de `fiscal.exposicion_aceptada` firmada (R8); `acepta_hueco_paypal` es decisión [DUEÑO] y se informa en `pendientes_dueno[]` |
| `nivel_max_lanzable` | objeto por macro-nicho | `limites` (LT-13) | sí | `dinero = amarillo-a` |
| `metodos_habilitados` | lista | `empresa/infra/stripe.yaml.metodos_pago[]` (D0) [PENDIENTE: lo construye S-B/D0]; hasta entonces, captura `docs/fuente/stripe-metodos-de-pago-habilitados.md` [VERIFICAR] | sí | 14 habilitados; 24 deshabilitados y 1 "requiere acción" **sin leer** `[VERIFICAR]`. Mapeo: D0 usa `metodo, estado, monedas, paises_cliente, managed_payments_compatible, accesible_ee_uu, ultima_verificacion`; la ficha de M1 (Anexo A) usa `id, habilitado_dueno, moneda_exigida, managed_payments_ok, elegible_cuenta_us`; manda D0 para el inventario y M1 solo proyecta |
| `decision_managed_payments`, `fase_pagos` | enum | dueño | sí | `no_decidido` ⇒ se asume Stripe estándar; `fase_pagos = estandar_tarjeta_billeteras` |
| `x1`: `matriz_pais_nivel`, `paises`, `ayuda_por_pais`, `terminos_sensibles/<locale>` | YAML | X1 | sí (si faltan: pregunta bloqueante) | exposición V/A/A+/R por país × macro |
| `tarifas.json` (F1), `economia_real.json` | JSON | F1 | sí (≤ 30 días) | comisión por (país, método, moneda) |
| `resultados_propios` por celda oferta × país | JSON | D8/D9/F1 | no | clics, compras, RPC, reembolsos, disputas por método |
| `atlas.json` y `paises/<ISO>.json` | JSON | M1 | sí | ver 3.3 |

### 3.2 Variables de decisión

| Variable | Opciones | Criterio | Cómo se testea |
|---|---|---|---|
| Unidad de oferta | 1 `locale` + clúster de países de **misma moneda y régimen** | Idioma = unidad de oferta; país = unidad de segmentación y de poda [CREADORES A] | Una celda por país (T3/T4 de docs/08 §7) |
| `fase_pagos` | `estandar_tarjeta_billeteras` (vigente) · `con_locales` (requiere decisión del dueño y MINOR del contrato) | Decisión del dueño de diferir; M1 calcula **ambas** y reporta el valor de desbloqueo | Compra real de prueba por método |
| `moneda_cobro` | EUR · moneda local · USD + `monedas_precio_adicionales` | Local si un método clave la exige (BLIK = PLN); EUR en eurozona (evita +1 % de conversión); Adaptive Pricing apagado (D5) | Comisión real vs modelo |
| Régimen fiscal | `diferido` (vigente) · `stripe_tax` · `merchant_of_record` | Dueño + contador; `diferido` exige exposición firmada por país | Campo `exposicion_aceptada` |
| Mercados en paralelo | 1 hasta `mercados_test_paralelos_max` (hoy 1; rango 1-3) | Presupuestos iguales para comparar; el parámetro manda | Protocolo estadístico §7 |

### 3.3 Salidas (contrato de salida)

| Artefacto | Ruta | Formato | Campos obligatorios | Consumidor |
|---|---|---|---|---|
| Ficha de país | `empresa/mercados/paises/<ISO>.json` | JSON (sin `float`: bp enteros, dinero `{monto, moneda}`) | Anexo A | M1, D2, D3 |
| Atlas (índice derivado) | `empresa/mercados/atlas.json` | JSON | por (país, locale): puntajes por criterio, `ficha_ref`, `ultima_verificacion`, `confianza`, `estado` (`candidato·activo·pausado·vetado`) | O0, F2, D9 |
| **Mercado de la oferta** | `ofertas/<id>/mercado.json` | contrato `mercado` 1.1.0 | todos los de `mercado.schema.json`; `estado_decision = hipotesis`; `metodos_pago.fase = estandar_tarjeta_billeteras`; `cpm_esperado` en unidad menor | D2-D7, D9, F1, X1 |
| Selección ampliada | `ofertas/<id>/mercado.seleccion.json` (**sin esquema aún; pedido a S-A**; **artefacto de APOYO de M1: no se sella** — `ARCHIVOS_SELLADOS['M1'] = ['mercado.json']`; es informativo para el dueño, D2 y D3; lo que D3/D5 necesitan para sellar vive en `mercado.json`) | JSON | `ranking[]` (top 5 con 9 criterios y sensibilidad), `excluidos[]` (regla y motivo), `precio_referencia` por moneda (rango, **lo fija D3**), `metodos_locales_recomendados[]` con `moneda_requerida` y `valor_desbloqueo_pp`, `carga_fiscal`, `riesgos[]`, `presupuesto_test_sugerido`, `pendientes_dueno[]`, `fuentes[]`; opcional `pais_referencia` (ISO; mercado maduro del mismo idioma, solo para observar; lo propone M1 desde `paises/<ISO>.json` y lo confirma el dueño); opcional `[SUPUESTO]` `mix_metodos_referencia[]` (`metodo`, `peso_bp` que suma 10000, `comision_pct_bp`, `comision_fija`, `tarifa_disputa`) para el `mix_metodos` de `engine.factibilidad`. Sin contrato: archivo hermano de M1 (CT-4); si CT-4 quiere sellarlo, pedido aparte | D2, D3, dueño (gate H) |
| Locales activos | `empresa/mercados/locales_activos.yaml` | YAML | por locale: `estado`, `prioridad` 1-5, `paises`, `presupuesto_exploracion{max_busquedas, max_costo}`, `macros_prioridad`, `requisitos_ok` | D1 |
| Términos de búsqueda y fuentes locales | `empresa/mercados/terminos_busqueda/<locale>.yaml` | YAML | `dolor[]`, `sustitutos[]`, `sitios_site[]`, `fuente_id_candidatos[]`, `revisado_por` | D1, D2 |
| Emparejamientos | `empresa/mercados/emparejamientos/<fecha>.json` | JSON | matriz candidato × mercado, `S`, bloqueos, `evidencia_local` | O0, dueño |
| Glosario y reglas de locale | `empresa/mercados/glosarios/<locale>.md` (+ `reglas/<locale>.yaml`) | MD + YAML | tono y registro, términos obligatorios/prohibidos, formatos, género/plurales, ejemplos | D3-D6, D10 |
| Calibración | `empresa/mercados/calibracion/AAAA-MM.json` | JSON | RPC/CPC, mezcla de métodos, comisión real, reembolsos y disputas por país | M1, D9 |
| QA | `empresa/mercados/qa/<periodo>-v<n>.json` · `ofertas/<id>/qa/m1-v<n>.json` | `qa` | veredicto, hallazgos | O0 |

### 3.4 Parámetros y umbrales

Todos [HIPÓTESIS] salvo indicación. Hoy `parametros.yaml#mercados` solo trae `clics_min_decidir_mercado`, `mercados_test_paralelos_max`, `primer_lanzamiento_requiere_h` y `prior_de_mercado`; **el resto es pedido LT-17 (con su addendum LT-53)**: el hogar único de los parámetros de M1 es `empresa/parametros.yaml` (grupo `mercados`), no `scripts/mercados/datos/parametros.json` (que solo guarda las constantes del modelo de ranking de `rank.py`); hasta que existan, M1 lee el fallback de la skill (`.claude/skills/m1-mercados-localizacion/scripts/parametros_m1.fallback.json`) y lo marca `[SUPUESTO]`

| Parámetro | Valor inicial | Rango | Nota |
|---|---|---|---|
| Pesos (PA·CAC·COMP·PAGO·FISC·LOC·FRAUD·EXPO·ESC) | 12·18·5·18·12·8·8·12·7 | ±5 c/u | 08 usaba 15·20·10·20·15·10·10; se agregan EXPO (decisión 13) y ESC (16 §5.2) y baja COMP (16 H7) |
| Peso del ajuste de creadores en la decisión | **0** (se muestra aparte, ±5 máx.) | 0 | Dueño 2026-11-06 |
| CTR de enlace central | 1,3 % (bp enteros: 130) | 0,8-1,8 % | 1,8 % es umbral de descarte de Tomi, no promedio (16 M2). D3 usa 120 en `economia.escenarios_embudo.central`: divergencia registrada (130 reproduce el escenario `corregido` de `rank.py`, LT-53) |
| Multiplicador de CPM estacional `mult_cpm` | 1,2 central · 1,5 estrés, cuando la ventana del test toca noviembre-diciembre (Black Friday 2026-11-27) | 1,0-1,5 | 16 M1: los CPM del atlas son de julio y no hay cifra autoritativa de Q4 para PL/IT (blogs: +25-50 % o más, C). `rank.py` escenario `corregido` usa 1,2 y `corregido_estres` 1,5. El 1,5 no es filtro: con 1,5, R9 sacaría además de los ya excluidos con 1,2 a CA, NZ, AU, IE, BE, CH y ES (`r_b` 2,54 / 2,21 / 2,72 / 2,37 / 2,55 / 2,43 / 2,24 > 2,2; cálculo de revisión: `r` del escenario `corregido` de `rank.py` × 1,25 / 1,5) |
| Conversión base | 2,0 % a 17,3 USD, elasticidad −0,5, límites 1-3 % | | 08 §5 |
| Escenario de costos | reembolso y disputa: M1 lee `economia.tasa_reembolso_bp` y `economia.tasa_disputa_bp` (hoy 700/50); los 800/60 de 16 H1 son los del escenario `corregido` de `rank.py` y se informan como sensibilidad; Stripe Tax Basic 0,5 % o 0,50 USD por API | 400/30-1200/100 | pedido D3/F1; sin él, 08 usa neto sin reembolsos ni Tax y sobrestima ~10 % (16 H1); disputa con tarjeta 15 USD [stripe.com/pricing, A] |
| `r` máximo para R9 (con bump AOV = 1,5·P) | 2,2 sobre `r_b = r/1,5` (≡ `r` sin bump > 3,3) | 1,8-2,5 | 08 §5; `r` se define en §4.1 |
| Cobertura de pago de la fase vigente | **duro 40 %** (R6) · **blando 55 %** (bandera `cobertura_media` + gate H + `valor_desbloqueo_pp`) | duro 30-50; blando 50-60 | 07g propone 60 % y hueco PayPal ≤ 20 pp. Con 55 duro Italia (46-50 %) quedaría excluida e Italia no podría ser el primer mercado en fase vigente; con 40 pasa con bandera y Polonia (≈ 17 %) cae |
| Vigencia de ficha | tarifas Stripe/Meta ≤ `finanzas.tarifas_antiguedad_max_dias` (30); legal ≤ 90 (bloquean); CPM ≤ 60 (**no bloquea**: vencido ⇒ MAYOR, etiqueta `[SUPUESTO]` y bandera `cpm_vencido`; se usa `mult_cpm.central` (1,2); el 1,5 (estrés) se informa como sensibilidad (bandera) y NO excluye mercados; es benchmark C que el CPM propio reemplaza tras 1.000 clics) | | alineado a D3 (tarifas ≤ 30) y X1. Hoy **todo CPM del atlas es del 2026-07-27 (102 días)**: con la regla estricta no se podría seleccionar nada |
| `clics_min_decidir_mercado` | 2400 (existente) | | docs/08 §7 |
| Presupuesto de test sugerido | por mercado: `clics_min × CPC` (el CPC ya incluye `f_meta` y `mult_cpm`; ≈ 740-1.220 USD a CPC 0,31-0,51); total = K × eso, recortado a los topes de `limites` | | un piloto de ~150 USD **no compara mercados** (16 H3). Con 2.400 clics el efecto mínimo detectable es ~+33 % relativo sobre una base de 2,5 % (docs/08 §3.3): por debajo de `clics_min` el resultado se etiqueta **señal de proceso** y `estado_decision` no cambia |
| Puntaje mínimo / empate | 55 / diferencias < 8 puntos | 45-65 | 08 §0. **El 55 se calibró sin neto completo**: en `rank.py --escenario corregido` solo 7 de 15 lo superan (CA 71, AU 67, NZ/US/HUS 64, GB 62, IE 58; IT 53, PL 51, la diferencia IT-PL queda en 2 puntos, dentro del empate). Hasta recalibrar es **bandera `bajo_minimo`** (gate H), no exclusión |
| Muestreo nativo posterior | 20 % = `producto.linguistica_muestreo_nativo_posterior` ("0.20"; hogar único en el grupo `producto`, decisión R-08 del backlog de CT-3; = «1 de cada 5» de D4 §6.3; M1 la lee; [PENDIENTE: la agrega CT-3, backlog S-04]) | 10-30 % | alineado a D4. NO existe `mercados.muestreo_nativo_posterior_pct` (conflicto C-05) |

### 3.5 KPIs del paso

- **Propios:** fichas vigentes de países activos (100 %); datos con fuente+fecha (100 %); tiempo del dueño por selección ≤ 30 min; desvío puntaje vs. CPA realizado (con ≥ 8 pares mercado-oferta).
- **Diferidos (medidos en campaña):** RPC/CPC por país; CPM propio vs. atlas (desvío); comisión real vs. modelo (> 0,5 pp = corregir); % de compras por método (BLIK ≥ 30 % de compras polacas si se habilita; si no, relevancia refutada); abandono por método; reembolso y disputas por país; rechazos de Meta por país/idioma.

## 4. Flujo paso a paso (SOP)

| # | Actor | Paso | Se guarda |
|---|---|---|---|
| 1 | Script | Preflight: `PAUSA` ausente; `paises_permitidos`/`locales_permitidos` no vacíos (si no, salida 5); candidato verde/amarillo con `macro_nicho` válido; fichas vigentes | `registro.jsonl` |
| 2 | Maker | Lista de países candidatos = permitidos ∩ locales con ficha; si falta ficha, pregunta bloqueante o encarga su construcción (paso 12) | borrador |
| 3 | Script | **Exclusiones duras** R1-R10 (§4.1) por país | `excluidos[]` |
| 4 | Script | Puntaje de 9 criterios para (candidato, país) con `puntaje.py` (v0.1 en la carpeta de la skill; destino `scripts/mercados/`), que **extiende `rank.py`** (misma economía y bandas; añade EXPO, cobertura por fase y rama Managed Payments). La economía pasa a `engine.factibilidad` cuando exista; hasta entonces `rank.py` es la referencia y toda divergencia se registra | `ranking[]` |
| 5 | Script | Sensibilidad (los escenarios de `rank.py`): CTR 1,0/1,3/1,8, `mult_cpm` 1,0/1,2/1,5, pesos iguales, ticket −35 %, sin/con creadores, ambas fases de pago, con/sin Managed Payments; se informa si el mercado elegido sigue en el top 3 | `sensibilidad` |
| 6 | Maker | Agrupa por `locale`, elige 1 bloque (hasta `mercados_test_paralelos_max`) y, si hay presupuesto, un brazo de **exploración** de menor puntaje para contrastar el modelo | borrador |
| 7 | Maker | Redacta `mercado.json` (contrato) y `mercado.seleccion.json`; si el primer lanzamiento es del locale, `requiere_gate_h = true` y `aprobado_por = null`; la v1 (`origen_version = maker`) lleva `exposicion_aceptada = null` y se valida en modo borrador (tolera solo esa firma pendiente) hasta que CT cierre LT-16(b) | v1 |
| 8 | QA (M1) | Checks MQ-01…MQ-22 y rúbrica (§6); máx. 2 rondas | `qa/m1-v1.json` |
| 9 | X1 | Dictamen por jurisdicción sobre `mercado.json` (veto) | `ofertas/<id>/qa/x1-m1-v<n>.json` (R15); por país, `empresa/compliance/qa/<periodo>-v<n>.json` |
| 10 | Humano | **Gate H**: lee 1 página (mercado elegido, 2 alternativas, qué se asume, qué falta); firma, y firma la exposición fiscal por país si el régimen es `diferido`; la firma humana crea la v2 (`origen_version = humano`) | `aprobado_por` |
| 11 | Script | Sella `mercado.json` (`estado.etapas.M1.hash_salida`) | `estado.json` |
| 12 | Maker | **Mantenimiento de atlas** (mensual y por evento): reverifica fichas por fuente oficial; registra contradicciones entre notas | `paises/`, `atlas.json` |
| 13 | Maker | Publica `locales_activos.yaml` y `terminos_busqueda/<locale>` para D1 | YAML |
| 14 | Maker | Recibe `hipotesis_transferencia` de D1 y responde viabilidad destino (¿ficha, glosario, revisor, ley?) y pide barrido local; **nunca declara válido** un problema en otro idioma | `emparejamientos/` |
| 15 | Script | Botón "Lanzar nueva oferta": matriz candidato × mercado para O0 (top 3 pares por candidato) | `emparejamientos/` |
| 16 | Maker | Servicio de localización (§4.2) a petición de D3-D6, D10 | glosarios, reglas |

### 4.1 Algoritmo de selección

**Exclusiones duras (R, fail-closed):**
- **R1** país fuera de `paises_permitidos` o locale fuera de `locales_permitidos`.
- **R2** candidato rojo, `fuera_de_macro_nicho` o `nivel` > `nivel_max_lanzable[macro]`.
- **R3 (tipo de promesa o contenido × país):** X1 expresa en `matriz_pais_nivel.yaml` restricciones `{pais, macro, tipo: promesa|contenido|modelo, condicion, id_check}` (J03-J05: DE sin formato "curso" ni ayuda fiscal; ES/DE salud sin términos del RD 1907/1996 art. 4 ni HWG; UK/IT/FR/US dinero sin instrumento, ingresos ni inversión; PL dinero sin cripto; AU dinero solo de hogar). M1 las cruza con `riesgo.banderas` y las líneas rojas (`lp-xx`…`lm-xx`) del candidato: **se excluye el par (promesa/contenido, país), nunca el tema entero**. Un reencuadre seguro (nota 25 §4) que baje el nivel reabre el par.
- **R4** sin línea de ayuda verificada del país para la categoría central (hoy Rumanía en emocional) ⇒ bloqueo; amarillo-B sin gate H ⇒ bloqueo.
- **R5** `obligacion_legal_idioma` (PL, FR, Quebec) sin revisor nativo ⇒ ROJO de X1 (contrato `X32_REVISOR`); Quebec en francés queda fuera del clúster `en-CA`.
- **R6** cobertura de pago de la **fase vigente** < umbral duro (40 %). Entre 40 % y el blando (55 %): pasa con bandera `cobertura_media` y gate H.
- **R7** moneda requerida por el único método clave no cobrable o no declarada.
- **R8** `fiscal.regimen = diferido` en país con IVA desde la primera venta sin `exposicion_aceptada` firmada: si la firma aún no se pidió (v1 del Maker) ⇒ bandera `requiere_firma_exposicion_fiscal` y el sellado la exige (MQ-07); si el dueño ya decidió y la firma no cubre el país ⇒ excluido; UK: registro desde la primera venta; no aplica con Managed Payments = sí.
- **R9** `r_b = r/1,5` > 2,2 (neto completo, `mult_cpm` vigente). Con la economía corregida (`rank.py corregido`) esto saca a EE. UU., Reino Unido e hispanos de EE. UU. (r_b 2,6 / 2,5 / 2,9) (y deja a Suecia al borde, 2,21) salvo ticket mayor o bump probado: no es un error, es el efecto de 16 H1.
- **R10** ficha con datos críticos vencidos (tarifas de Stripe/Meta > 30 días, legal > 90; el CPM no bloquea, §3.4).

**Puntaje** (cada criterio 0-5 con `puntaje·confianza`; total = Σ peso·puntaje/5):

| Criterio | Regla de puntaje |
|---|---|
| PA poder adquisitivo | consumo/habitante vs. media UE y ticket observado (08 §2.1) |
| CAC | `r = CPC/(neto·conv_esp)` **sin bump** (como 08 y `rank.py`); 5 si r ≤ 1,0 · 4 ≤ 1,25 · 3 ≤ 1,5 · 2 ≤ 1,8 · 1 ≤ 2,2 · 0 mayor. `CPC = CPM·mult_cpm·(1+f_meta)/(1000·CTR)`; `conv_esp = clamp(2 %·(17,3/P)^0,5; 1 %; 3 %)`; `neto = (1−ρ)·P/(1+t) − comisión − fee_tax − d·15·part_tarjeta` (16 §2.1: el reembolso devuelve bruto e IVA y la comisión se pierde; la disputa con tarjeta cuesta 15 USD; BLIK no cobra tarifa: `part_tarjeta` < 1); comisión = `pct·P + fijo (+1,5 % internacional, +1 % conversión)`; `f_meta` = tarifa de ubicación de Meta (ver hechos vigentes). **Saturación:** con la economía corregida 14 de 15 mercados quedan en CAC 0 y el criterio (18 %) deja de discriminar; el puntaje central usa las bandas reancladas por mediana (`rank.py` `cac_modo=relativo`, escenario `corregido_cac_relativo`) y el nivel absoluto lo garantiza R9 |
| COMP | saturación **con** señal de demanda (no solo cantidad de anuncios); peso bajo |
| **PAGO** | `cobertura = Σ cuota_m` de los métodos **habilitados en la fase vigente**, elegibles para la cuenta de EE. UU., cobrables en la moneda y no excluidos por la decisión de Managed Payments. ≥ 70 % = 5 · 60-69 = 4 · 50-59 = 3 · 40-49 = 2 · 30-39 = 1 · < 30 = 0. Se informa siempre `cobertura_con_locales` y `valor_desbloqueo_pp`, y el hueco PayPal en pp |
| FISC | 4 umbral alto y Stripe presenta · 3 umbral global · 2 OSS desde la primera venta · 1 formalismo extra (Impressum, Toubon, representante) |
| LOC | 5 inglés/español · 3-4 idiomas con buen soporte de IA · 1-2 difíciles o con revisor escaso u obligación legal |
| FRAUD | disputas del método dominante, COD, normas de desistimiento |
| **EXPO** (nuevo) | exposición del país contra el nivel del candidato, evaluada **por bandera de `riesgo` y por `macro_nicho` + secundario, tomando la peor** (nota 25 §8.1: J01 lee por bandera, no por macro primario; semilla en Anexo D): **verde** V=5·A=4·A+=3·R=2; **amarillo-A** V=4·A=3·A+=1·R=0 (A+ y R ⇒ bandera `gate_h_exposicion`; se rigen por la matriz de X1 y los lints J03-J05, sin consulta legal humana: decisión 14); **amarillo-B** V=2·A=1; A+/R excluidos |
| ESC | alcance publicitario/población del locale (16 §5.2) |

**Salida:** orden por total; desempate por menor carga fiscal, luego base sin ajuste (como `rank.py`); K ≤ `mercados_test_paralelos_max`; el puntaje de un bloque (1 `locale` + países de misma moneda y régimen) es la media simple de sus países [SUPUESTO] y K cuenta bloques; ajuste de creadores solo informativo. Determinista: mismos datos versionados ⇒ mismo orden, sin LLM en el cálculo; el Maker solo carga datos con fuente.

**Implementación de referencia (`scripts/mercados/rank.py`, solo biblioteca estándar).** Hoy reproduce los 15 totales de 08 §2.2 (`OK: 15 totales y sin_pagos reproducidos`), recalcula CAC con la regla de `r` y marca la inconsistencia de Suiza (r 1,58 contra 1,50 publicado; 17 H1), y corre los escenarios `neto_completo_*`, `cpm_q4_x1_2/1_5`, `ctr_*`, `ticket_ingles_17*`, `sin_pagos*`, `corregido*`, `escala_10` y `--grid`. Lectura (confianza C, datos de julio): en `corregido` Italia queda 8.ª con 53 y Polonia 10.ª con 51, **pero 5 de esos 53 puntos son el ajuste de creadores que M1 pesa 0**: sin él (`sin_ajuste_creadores`, `pesos_iguales_sin_creadores`) Polonia queda ~3 puntos *por encima* de Italia. Es un empate (< 8) en ambos sentidos, ninguno supera el mínimo 55 y el PAGO de Polonia en `rank.py` (4) cuenta BLIK: en la fase vigente (≈ 17 %) sería 0 y perdería ~14 puntos. Con `mercados_test_paralelos_max = 1` el piloto decide si ESA oferta funciona en ESE mercado (T3) y no compara mercados; comparar exige subir el parámetro a ≥ 2 [DUEÑO]. Un cambio de modelo en M1 se prueba primero contra este script; si divergen, el QA (MQ-09) lo registra como conflicto y manda el contrato.

**Rama Managed Payments (si `decision_managed_payments = si`; con `no_decidido` se calcula Stripe estándar y se informa la otra rama).** (a) PAGO: solo cuentan tarjeta, Apple/Google Pay, Link y, para BE, Bancontact; BLIK, Satispay, MB WAY, EPS, Pay by Bank y Przelewy24 salen (Polonia ≈ 17-23 %) [07e §1.5, A]; (b) neto: `+3,5 %` sobre las comisiones de Payments (`[VERIFICAR]` si sobre el total con impuestos) y sin `fee_tax` propio [03 §4.2, A]; (c) FISC sube a 4-5 y **R8 no aplica** (el MoR calcula, cobra, presenta y remite) [03 §0.3; 07b]; (d) `[VERIFICAR]` antes de elegirlo: solo Checkout/Payment Links, sin Elements ni dominio propio de checkout (roza la decisión 9 y el backbone 5.3), descriptor «LINK.COM*». M1 no activa nada: reporta el delta de puntaje y de neto de cada rama.

**Hechos externos vigentes que M1 aplica (cada uno `[VERIFICAR]` en la ficha antes de sellar; fechas de lectura de las notas):**

| Hecho | Estado | Fuente |
|---|---|---|
| Tarifa de ubicación de Meta: FR 3 %, IT 3 %, ES 3 %, AT 5 %, UK 2 % (TR 5 %) desde 2026-07-01; línea aparte en la factura, no figura en las métricas de Ads Manager, el IVA se calcula sobre ella; se puede excluir el país a nivel de cuenta pero Meta no garantiza que baje la tarifa; no aplica a categorías especiales de anuncios | A | facebook.com/business/help/1238737454289085 (07a, resumen 4) |
| IVA de no establecidos: OSS no-Unión sin umbral desde la primera venta (UE); UK registro HMRC desde la primera venta; CH representante fiscal y umbral mundial 100.000 CHF; NO VOEC | B | 07b, 07h §7; 05 §6.1 |
| Función/botón de desistimiento en 2 pasos: obligatoria en la UE desde 2026-06-19 (Dir. (UE) 2023/2673), alcanza a comerciantes no UE que apuntan a consumidores UE; Italia art. 54-bis; **transposición polaca suspendida al 2026-06-12** (CMS, B) | B/C | 05 §2; 07h §7 |
| DSA: beneficiario y pagador obligatorios en todo anuncio nuevo o editado hacia la UE | A | facebook.com/business/help/721913190475838 (07a) |
| BLIK: titular de EE. UU. elegible, solo clientes de Polonia, PLN, sin Managed Payments, sin Express Checkout Element, sin apelación de disputas | A | docs.stripe.com/payments/blik (leída 2026-11-06) |

**`mercado.seleccion.json` ≠ contrato.** Qué va dónde: `locale`, `paises_segmentacion`, `moneda_cobro`, `cpm_esperado` (`{monto, moneda}` en unidad menor), `cpm_fuente`, `fiscal`, `consumo`, `glosario_ref`, `revision_linguistica` van a `mercado.json`; precio de referencia, métodos locales recomendados, puntajes y presupuesto van al archivo hermano. D3 decide el precio y `engine.factibilidad` el veredicto.

**Efecto central de la fase de pagos (cálculo propio sobre 07g/07h, confianza C):**

| País | Cobertura `estandar_tarjeta_billeteras` | Con locales habilitados | Lectura |
|---|---|---|---|
| Polonia | ≈ 17 % (tarjetas 11 % + billeteras ≈ 6 %) | ≈ 60-70 % (BLIK 45-55 % + tarjetas 11 % + billeteras ≈ 6 %; Przelewy24 y pay-by-link, ≈ 15-25 pp [HIPÓTESIS] C, se informan aparte y NO se suman a la cobertura; 07h §3.3) | falla R6 hoy; pasa con BLIK y moneda PLN |
| Italia | ≈ 46-50 % | ≈ 48-60 % (Satispay marginal) | independiente de lo local; PayPal (24-36 %) inalcanzable |
| Canadá / Irlanda | ≈ 72-74 % / ≈ 70 % | igual | las tarjetas dominan |

BLIK, verificado hoy en la ficha oficial: negocio en EE. UU. elegible, solo clientes de Polonia, PLN, **sin Managed Payments**, sin tarifa de disputa pero sin apelación (aviso del cliente hasta 13 meses), y en móvil el comprador vuelve manualmente a la página (riesgo de medición del Purchase) [docs.stripe.com/payments/blik, A, leída 2026-11-06]. Esto resuelve la contradicción 07b/07h y deja la decisión en manos del dueño: **mientras los métodos locales sigan diferidos, Polonia queda fuera por R6**; eso no dice nada sobre su mercado, dice que el cobro estándar no lo alcanza.

### 4.2 Localización como capacidad transversal

| Etapa | Actor | Detalle |
|---|---|---|
| 1. Glosario y reglas | M1 Maker + revisor nativo | `glosarios/<locale>.md`: registro (tú/Ty/Lei), términos del oficio **y** de cada macro-nicho, términos prohibidos (de X1), formato de moneda (`49 zł`, `9,90 €`), decimales, fechas, unidades/papel, género y plurales (PL 2-4 vs 5+; PL "robiłeś/robiłaś"), ejemplos buenos/malos |
| 2. Traducir + adaptar | Maker de cada departamento con el glosario | Transcreación (voz, humor, ritmo, ejemplos locales), no traducción literal; M1 no escribe en carpetas ajenas |
| 3. Lint determinista | `lint_locale.py` (v0.1 en la carpeta de la skill; destino `scripts/mercados/`) | Glosario obligatorio/prohibido, formatos, diacríticos, caracteres de otro idioma, longitud, moneda coherente con `moneda_cobro`, plurales PL heurísticos |
| 4. Retraducción | segundo modelo | Traduce de vuelta al idioma fuente; un juez compara significado y promesa; discrepancia en promesa/precio/legal = MAYOR |
| 5. Segunda lectura | otro modelo | Naturalidad, calcos del inglés/español, concordancias |
| 6. Muestreo humano | nativo | Primer lanzamiento de un idioma: 100 % de legales, checkout y landing, 30 % de piezas de anuncio y del producto `[HIPÓTESIS]`; después `producto.linguistica_muestreo_nativo_posterior` (20 %). Con `obligacion_legal_idioma`: 100 % y sin revisor no se lanza |

**Handoffs:** D3 recibe moneda, rango de precio de referencia y glosario del nombre del producto (marca neutra, sin connotación local rara); D4, idioma, unidades, formato de papel y fuentes con diacríticos; D5, plantillas legales, casillas de renuncia, CMP, métodos por moneda y formatos; D6, voz del locale y lista de términos sensibles; D10, plantillas fijas de soporte en el idioma y horarios.

## 5. Agente Maker

**Rol:** analista de mercados y arquitecto de localización. **Hace:** seleccionar mercado, mantener el atlas, publicar locales activos y términos de búsqueda, responder transferencias de D1, construir glosarios. **No hace:** fijar precio, clasificar riesgo ni redactar claims, asignar presupuesto o topes (solo sugiere), tocar `limites.yaml`, aceptar un país por impresión del dueño o de un creador, activar métodos de pago, hablar con Stripe/Meta en modo escritura.
**Permisos (mínimo privilegio):** `Read` de `docs/`, `empresa/`, `ofertas/<id>/`; `Edit/Write` solo en el staging del encargo (runner) o, en sesión del dueño, en `empresa/mercados/**` y `ofertas/<id>/mercado*.json`; `Bash` solo los scripts de M1 y `scripts/validar_esquemas`; `WebSearch`/`WebFetch` de solo lectura únicamente en el modo atlas (fuentes oficiales; `WebFetch` ubica, no cita; no en el modo selección); sin MCP (docs/09 §8.1: M1 = archivos), por tanto sin `ads_library_search`: los datos del barrido los lee de `empresa/barrido/`. El runner agrega la web solo en modo atlas.

## 6. Agente QA

**Independencia:** contexto limpio; recibe `mercado.json`, `mercado.seleccion.json`, atlas/fichas citadas, contrato, `limites`, `parametros`, X1 y rúbrica; no el razonamiento del Maker. **Facultades:** devolver cada hallazgo con su `correccion` (`estado = devuelto_al_maker`); el parche lo aplica el Maker en la ronda siguiente (máx. 2 rondas); el QA, de solo lectura, no edita ni aplica nada (`cambios_aplicados = []`); no hay rama `qa/`.

**Checks deterministas (L1):** los ejecuta CÓDIGO (el runner) antes del QA y entrega el informe con su hash en la ruta única `ofertas/<id>/qa/.l1/m1-v<n>.json`; el QA (solo `Read, Grep, Glob`) los cita y no recalcula nada. Un check `no_aplica` por falta de insumo se devuelve pidiendo el insumo.

| ID | Check | Sev. |
|---|---|---|
| MQ-01 | `validar_esquemas` sobre `mercado.json` (1.1.0, `schema_version` ≥ 1.1.0) | BLOQ |
| MQ-01S | `mercado.seleccion.json` valida contra su esquema (cuando exista; hoy contra la propuesta) | MAYOR |
| MQ-02 | Todo dato del atlas con `fuente_url` o `[VERIFICAR]`, `fecha_lectura` y `confianza` A/B/C | BLOQ |
| MQ-03 | Vigencia: tarifas ≤ 30 días y legal ≤ 90 | BLOQ |
| MQ-03M | CPM > 60 días sin etiqueta `[SUPUESTO]` y bandera `cpm_vencido` | MAYOR |
| MQ-04 | Coherencia moneda ↔ método: BLIK⇒PLN y cliente PL; Satispay, Bancontact, EPS, MB WAY⇒EUR; Pix⇒BRL; Amazon Pay⇒USD; Klarna solo clientes de EE. UU. | BLOQ |
| MQ-05 | `paises_segmentacion` ⊂ `paises_permitidos`; `locale` ∈ `locales_permitidos` | BLOQ |
| MQ-06 | `moneda_cobro` válida para todos los países del clúster | MAYOR |
| MQ-07 | Impuestos: tasa de la ficha = fuente; `diferido` ⇒ `exposicion_aceptada` firmada cubre el clúster; nada de "IVA incluido" con diferido | BLOQ |
| MQ-08 | `consumo.desistimiento_dias`, botón de arrepentimiento y consentimiento coinciden con la ficha del país | MAYOR |
| MQ-09 | Pesos suman 100; el runner recalcula el puntaje (`puntaje.py`/`rank.py`, ±0,5) y `rank.py` sigue imprimiendo `OK: 15 totales…`; el QA cita `qa/.l1/m1-v<n>.json` | BLOQ |
| MQ-10 | `estado_decision = hipotesis`, `evidencia_propia` en 0 si no hay datos; peso de creadores = 0; sin texto "prior" | BLOQ |
| MQ-11 | `revision_linguistica`: `obligacion_legal_idioma` ∧ ¬`revisor_nativo` ⇒ no sellar | BLOQ |
| MQ-12 | EXPO y R3 coinciden con la matriz de X1 (hash citado) | BLOQ |
| MQ-13 | Cobertura de pago calculada con los métodos de la **fase** (Klarna, Amazon Pay y PayPal no suman) | BLOQ |
| MQ-14 | Tarifa de ubicación de Meta incluida en `r` donde aplica | MAYOR |
| MQ-15 | `primer_lanzamiento_en_locale` ⇒ `requiere_gate_h` y `aprobado_por = null` hasta la firma | BLOQ |
| MQ-16 | Nº de mercados ≤ `mercados_test_paralelos_max`; presupuesto sugerido ≤ topes (o `limites_pendientes`) | MAYOR |
| MQ-17 | `cpm_esperado` en unidad menor entera y `cpm_fuente` no vacío; contradicciones entre notas registradas | MAYOR |
| MQ-18 | Neto completo: reembolso, disputas, Stripe Tax, comisión por método+moneda, tarifa de ubicación y `mult_cpm` (si el test toca nov-dic); `r` recomputado por el runner con `rank.py` (±0,05) | BLOQ |
| MQ-19 | Presupuesto = K × `clics_min` × CPC sin doble `f_meta`; si el tope de `limites` es menor, la salida dice «señal de proceso», no «decide mercado» | MAYOR |
| MQ-20 | Managed Payments: ambas ramas informadas (PAGO, neto +3,5 %, FISC, R8); con `no_decidido` la rama estándar no resta métodos ni suma 3,5 % | MAYOR |
| MQ-21 | `mercado.json` coincide con `brief.mercado_objetivo` (locale, moneda, países); el validador lo emite como `X30_MERCADO` | MAYOR |
| MQ-22 | Una `hipotesis_transferencia` nunca figura como válida sin `evidencia_local` (cubre ★D16) | BLOQ |

**Rúbrica (manda el contrato: `items[].item_id` = R1-R8, 0-5, con evidencia citada; PASS = 0 BLOQ y 0 MAYORES abiertos + `puntaje_global` ≥ `mercados.umbral_qa` (4,0) y ningún ítem < `mercados.umbral_item_min_qa` (3); convención `<grupo>.umbral_qa`, conflicto C-12; el `umbral` del informe se llena con esa clave, decimal como cadena; las claves las agrega CT, LT-17/LT-53):**

| Ítem | 1 | 3 | 5 |
|---|---|---|---|
| R1 Trazabilidad | datos sin fuente | fuente sin fecha | fuente, fecha y confianza en todo |
| R2 Pagos por fase | cuenta métodos no cobrables | fase correcta, sin valor de desbloqueo | ambas fases, hueco PayPal y moneda explícitos |
| R3 Economía | neto sin impuestos/reembolsos | neto completo, un escenario | neto completo, sensibilidad CTR/ticket, `r` reproducible |
| R4 Exposición por macro | ignora X1 | cita la matriz | cruza promesa/contenido × país y reencuadre disponible |
| R5 Localización | traducción literal | glosario básico | glosario por macro, retraducción y muestreo planificados |
| R6 Honestidad | presenta un país como favorito | marca [HIPÓTESIS] | separa evidencia propia, de creadores y supuestos; dice qué no sabe |
| R7 Gates y firma | `aprobado_por` con firma de agente; gate H omitido | gate H marcado | `requiere_gate_h` y `aprobado_por = null` hasta la firma humana; exposición fiscal por país pendiente de la firma; veto de X1 intacto; `pendientes_dueno[]` completos |
| R8 Utilidad para el siguiente agente | D3 no sabe qué moneda ni rango usar | campos presentes | `precio_referencia` por moneda con `fija: D3`, `glosario_ref` o pendiente, presupuesto sugerido dentro de topes o `limites_pendientes`, resumen de 1 página para el gate H |

**Simulaciones (L3):** contador (IVA y OSS), revisor de cumplimiento de X1 por país × macro (matriz y J01-J08), nativo ciego sobre una landing de muestra, escéptico ("¿por qué no Polonia?" se responde con números y la palanca BLIK).

**Defectos sembrados (≥ 90 % de los bloqueantes ★ deben detectarse):** ★D1 BLIK con precio en EUR; ★D2 cobertura de Polonia que suma Klarna/Amazon Pay; ★D3 dato de ficha sin fecha ni fuente; ★D4 ajuste de creadores decide el desempate Polonia > Italia; ★D5 `diferido` sin exposición firmada en IT; ★D6 clúster `en-CA` que incluye Quebec o `fr-CA` sin revisor; ★D7 `pl-PL` con `revisor_nativo=false`; ★D8 PayPal contado como habilitable; ★D14 neto sin reembolsos ni Stripe Tax (r subestimado ~10 %); ★D15 test de < 2.400 clics presentado como decisión de mercado; ★D16 `hipotesis_transferencia` de D1 declarada «válida» sin barrido local; ★D17 CPM de julio sin `mult_cpm` en una ventana de diciembre; ★D9 salud en DE con promesa de eficacia puesta como verde; D10 tarifa de Meta de Italia omitida; D11 pesos que suman 103; D12 CPM sin fecha; D13 Managed Payments elegido sin descontar BLIK; D18 `f_meta` aplicado dos veces al presupuesto. **Frontera (nota 25 §11):** los casos de `casos-frontera.yaml` con `mercado_gate` (hoy `docs/_historial/hwr-semillas/`) deben dar el mismo veredicto de país × nivel que la proyección de `matriz_pais_nivel.yaml` (0 divergencias).
**Dorados (deben dar PASS, 0 BLOQ):** evals 1 y 2 de §10.5 resueltos con la fase vigente. **Anti-sello-de-goma:** el QA lista ≥ 3 hallazgos o justifica con evidencia qué revisó (backbone 6.7).
**Mejoras de valor:** separar PT-PT de PT-BR; clúster monomoneda; brazo de exploración barato; el dato barato que más mueve el resultado. **Loop:** protocolo común (6.5), máx. 2 rondas.

## 7. Gates y autonomía

| Nivel | M1 | Dinero / cumplimiento | Métrica para ascender |
|---|---|---|---|
| N0-N1 | Dueño en Code con el Maker; todo se revisa | M1 no gasta; solo hipótesis | v1 del atlas; 5 selecciones con ≤ 1 corrección |
| N2 | Maker + QA + X1; **H** en primer lanzamiento de **país o idioma** (`etapa:M1`, `accion:lanzamiento_pais_idioma_nuevo`) y en toda exposición fiscal; el gate por país × macro-nicho × nivel (amarillo-A con exposición A+) es adicional al de primer lanzamiento | país fuera de `paises_permitidos` = denegado | ≥ 10 selecciones, 0 fichas vencidas aceptadas, QA ≥ 90 % de sembrados |
| N3 | S: el dueño audita por excepción (`gates.json`; efectivo **H** mientras `limites.acciones_gate_humano` contenga `lanzamiento_pais_idioma_nuevo`, como en D9: C-W3-02); **H** si cambia el régimen fiscal, entra un país con idioma legal obligatorio, o se supera el tope de mercados | scripts con `fuentes_permitidas` | 3 meses sin hallazgo BLOQ ni rechazo atribuible a mercado |
| N4 | Atlas y selección sin dueño; el botón empareja candidato × mercado; H solo en lo anterior | topes duros | revisión trimestral |

**Veto de X1 por jurisdicción** no se relaja con el nivel (backbone 6.8). **Dinero:** M1 no asigna presupuesto, sugiere dentro de topes; con `limites` en `null` emite `limites_pendientes`. Una expansión (D9) es oferta hija: gate H de M1/D9, paridad de evidencia local y economía propia.

## 8. Riesgos y modos de falla

| Riesgo | Señal temprana | Mitigación | Resp. |
|---|---|---|---|
| Elegir por impresión (Polonia) y no por datos | el desempate depende del ajuste de creadores | peso 0, MQ-10, brazo de exploración y, solo si el dueño sube el parámetro, test paralelo con presupuesto igual | QA |
| Cobertura de pago inflada por métodos no cobrables | Klarna/PayPal en la suma | MQ-13; elegibilidad para cuenta de EE. UU. por método | QA |
| Falsa certeza (CPM de blogs, confianza C) | todo el atlas en C | `confianza` por campo; CPM propio tras ≥ 1.000 clics | M1 |
| Cumplimiento (IVA, desistimiento, idioma legal, consentimiento) | R5/R8, país sin dictamen | fail-closed, exposición firmada, X1 | X1 |
| Políticas y tarifas cambian (Meta, Stripe, DFA, art. 54-bis, UC82 en Polonia `[VERIFICAR]`) | ficha vencida, avisos | vigencia 30/90 días; disparadores por evento | M1 |
| Traducción plausible pero mala (concordancias, calcos) | retraducción diverge, quejas de soporte | QA lingüístico en capas y nativo en el primer lanzamiento | M1/QA |
| Concentración: una cuenta de Meta y una de Stripe | rechazo en un país | un rechazo congela la hoja × idioma; no abrir cuentas nuevas | O0/X1 |
| Q4 (Black Friday 2026-11-27) sube el CPM; el atlas es de julio | CPM real > `mult_cpm` × atlas | `mult_cpm` 1,2 central y 1,5 sensibilidad, sensibilidad obligatoria, leer el test como «Q4» y no comparar con enero | M1/D8 |
| Mínimo 55 y CAC calibrados sin neto completo | casi todo el atlas bajo mínimo, CAC en 0 | bandera `bajo_minimo`, CAC relativo, recalibrar con datos propios (≥ 8 pares) | M1 |

## 9. Mejoras respecto del video

1. **[NUEVO]** Mercado como hipótesis con puntaje reproducible, sensibilidad y brazo de exploración.
2. **[NUEVO]** Pagos por **fase** (vigente vs. con locales) con valor de desbloqueo: convierte la pregunta del dueño en un número.
3. **[NUEVO]** Exposición regulatoria por macro-nicho y exclusión por (promesa o contenido × país), alimentada por X1, sin excluir temas.
4. **[NUEVO]** Economía con neto completo (Stripe Tax, reembolsos, disputas, tarifa de ubicación de Meta).
5. **[NUEVO]** Localización como servicio con QA en capas y glosarios por macro-nicho; interfaz con el radar de D1.

## 10. Forja de la skill (pestaña Code)

### 10.1 Prompt de arranque (copiar y pegar)

```
ROL: eres el Maker de M1 (Mercados, idiomas y monedas) de un sistema que lanza ofertas digitales de bajo ticket en Meta con checkout de Stripe (LLC de EE. UU.). NINGÚN país es favorito: Polonia, Italia y los demás son hipótesis (dueño, 2026-11-06). Toda oferta encuadra en salud, relaciones o dinero.
LEE (rutas desde la raíz del repositorio; si falta un archivo, dilo y sigue con lo disponible): docs/_backbone.md (completo), departamentos/16-mercados-localizacion.md, docs/contratos.md, contratos/mercado.schema.json, contratos/candidatos.schema.json, empresa/limites.yaml, empresa/parametros.yaml, docs/fuente/stripe-metodos-de-pago-habilitados.md, docs/08-protocolo-estadistico-del-testeo.md (§3.3 y §7), scripts/mercados/rank.py, scripts/mercados/rank_sin_pagos.py, scripts/mercados/datos/*.json, y de docs/_investigacion/: 03-stripe.md, 04-meta-ads.md, 05-legal.md, 06-mercados-atlas-creadores.md, 07a-mercados-eurozona.md, 07b-mercados-europa-no-euro-uk-ch.md, 07c-mercados-angloparlantes-y-otros.md, 07d-mercados-latam-y-hispanos-eeuu.md, 07e-pagos-habilitados-europa.md, 07f-pagos-dominantes-no-habilitados.md, 07g-pagos-pix-us-uk-otros.md, 07h-polonia-italia.md, 08-mercados-ranking.md, 16-red-team-mercados-y-modelo.md, 22e-regulacion-por-jurisdiccion-salud-dinero-relaciones.md, 25-marco-salud-relaciones-dinero.md (§8). PRIMER PASO: ejecuta `python3 -I scripts/mercados/rank.py` y `... --escenario corregido` (solo lectura) y confirma que reproduce los 15 totales de 08 §2.2; si no, para y avisa.
TAREA: Arma el atlas v1: empresa/mercados/paises/<ISO>.json para los 15 del top de 08 §2.2 más RO y FR (campos del Anexo A; ficha y R1-R10; puntaje solo cuando exista desglose, hoy RO y FR no tienen), atlas.json, locales_activos.yaml, glosarios it-IT, pl-PL y en-CA, y mercado.json + mercado.seleccion.json de práctica para un candidato de dinero verde y uno de salud verde. Cobertura de pago en las DOS fases, valor de desbloqueo y rama Managed Payments. Economía con neto completo y mult_cpm 1,2/1,5. Trabaja en dos tandas (primero PL, IT, CA; luego el resto) y pide visto bueno entre ambas.
REGLAS: no inventes; cada dato con URL y fecha o [VERIFICAR]; confianza A/B/C por campo; [SUPUESTO] donde corresponda (incluido todo lo que rank.py no cubre: EXPO, cobertura por fase, R1-R10); sin float; ajuste de creadores con peso 0; escribe solo en empresa/mercados/ y ofertas/<id>/mercado*.json; lista pedidos en vez de tocar contratos/, limites o parametros; no ejecutes herramientas con costo o efecto externo; no ejecutes scripts/test_all.sh.
PREGUNTAS BLOQUEANTES (haz estas preguntas primero y espera respuesta): paises_permitidos y locales_permitidos; Managed Payments sí/no; métodos locales diferidos o no; pestañas "Deshabilitado" y "requiere acción" de Stripe; mercados_test_paralelos_max; revisor nativo del idioma del primer mercado (pl o it solo si salen elegidos); fecha prevista del test (¿antes o después del 1-ene? define mult_cpm).
SALIDA: archivos + resumen (supuestos, contradicciones y cuál prevalece, ranking con sensibilidad, qué decisión del dueño mueve más el resultado, [VERIFICAR]). ACEPTACIÓN: MQ-01…MQ-22 y totales de 08 §2.2 reproducidos (±1) con rank.py.
```

### 10.2 Cómo pulir
Mirar: ¿la cobertura de Polonia cambia según la fase?, ¿cada celda tiene fecha y fuente?, ¿el puntaje se reproduce con el script?, ¿la ficha dice qué NO sabe? Preguntar: "¿qué dato barato movería más el resultado?". Máximo 2 h por iteración y 3 iteraciones, cada una con un país nuevo (evita sobreajuste a PL/IT).

### 10.3 Estructura de la skill a generar
```
.claude/skills/m1-mercados-localizacion/
├── SKILL.md   references/{algoritmo.md, anexo-ficha.md, pagos-por-fase.md, managed-payments.md, localizacion.md, interfaz-d1.md, matriz-exposicion.md}
├── rubric.md   templates/{ficha-pais.json, mercado.seleccion.json, glosario.md}
├── scripts/ (puntaje.py extiende scripts/mercados/rank.py; vigencia.py, lint_locale.py, chequeos_l1.py, autoprueba.py)
└── evals/{dorados,sembrados}/ (carpetas con casos JSON)    CHANGELOG.md
```
Los scripts de la skill (`puntaje.py`, `vigencia.py`, `lint_locale.py`, `chequeos_l1.py`, `autoprueba.py`) viven hoy en `.claude/skills/m1-mercados-localizacion/scripts/` (v0.1). [PENDIENTE: lo construye S-B: promoverlos a `scripts/mercados/` con pruebas en `tests/mercados/`]

### 10.4 Definición de listo (DoD)
(1) Atlas v1 con 15+2 países (15 + RO + FR: ficha y R1-R10; puntaje solo cuando exista desglose, hoy RO y FR no tienen), 100 % de datos con fuente+fecha+confianza. (2) Reproduce los totales de 08 en ±1 punto (`rank.py` imprime `OK`), la sensibilidad de 08 §2.5 y el escenario `corregido` (CA 71 … IT 53, PL 51) con los mismos datos. (3) Eval de cobertura por fase correcto en PL e IT. (4) QA detecta ≥ 90 % de los bloqueantes sembrados con 0 falsos PASS. (5) Cero cadenas con país favorito. (6) `mercado.json` válido con `validar_esquemas`. (7) El dueño aprueba 2 selecciones de práctica sin reescribir el razonamiento. (8) Pedidos a S-A listados y sin ediciones fuera de propiedad.

### 10.5 Evals mínimos
1. **Dinero verde, es-ES→it-IT/pl-PL** (caso de práctica 1, un mercado a la vez): (dinero verde «presupuesto por cobro», 25 §8.2 paso 1) con fase vigente, PL excluido por R6 (≈ 17 % < 40 %) e IT pasa con bandera `cobertura_media` (46-50 % < 55 %); con `con_locales` y PLN, PL pasa R6, y compararlo con IT en paralelo exige `mercados_test_paralelos_max ≥ 2` [DUEÑO] (presupuesto igual y sin precio tachado; 60-75 USD por país es **solo señal de proceso**, no compara mercados: eso exige `clics_min`); si el parámetro sigue en 1, el primer mercado se decide en serie.
2. **Inglés Commonwealth** (CA sin Quebec, NZ, AU; IE solo con OSS): clúster `en-CA/AU/NZ` con monedas distintas ⇒ se separa por moneda; en dinero, CA y NZ antes que AU/IE/UK/US por la verificación financiera de Meta (25 §8.2 paso 3).
3. **Otro idioma/mercado sin ficha** (de-DE o ro-RO): falla cerrado, pregunta bloqueante; no inventa.
4. **Otro nicho (salud, it-IT)** con "perdi 8 kg in 30 giorni": R2/R3 excluyen ese **ángulo**, no la salud; el reencuadre (planificador semanal) reabre.
5. **Dinero amarillo-A en UK/AU**: bloqueado o con gate H por EXPO y verificación financiera de Meta.
6. **Hipótesis de transferencia** es-ES→it-IT del radar: M1 pide barrido local y no valida.
7. **Ficha con tarifas de 45 días**: R10 bloquea.
8. **Managed Payments = sí** (relaciones, pl-PL): PAGO de PL cae a ≈ 17-23 %, R6 la excluye, FISC sube y R8 no aplica; M1 informa el delta y no decide el régimen.
9. **Ventana de diciembre con CPM de julio**: sin `mult_cpm` el QA devuelve BLOQ (MQ-18; y MAYOR por MQ-03M si el CPM además está vencido sin etiqueta); con 1,2/1,5 el orden se informa con sensibilidad.
10. **Idioma sin ficha en inglés** (en-GB para un candidato de dinero verde): UK exige registro HMRC desde la primera venta (R8 si `diferido`) y J05; EXPO por bandera, no por macro.

## 11. Preguntas abiertas / decisiones del dueño

1. **¿Managed Payments sí o no?** Con él, BLIK, Satispay, MB WAY, EPS, Pay by Bank y Przelewy24 quedan fuera y Polonia cae a ≈ 17-23 %. `[DUEÑO + contador]`
2. **¿Se activan los métodos locales** (habilitar Przelewy24, precios en PLN/EUR)? Requiere MINOR del contrato `mercado` (S-A) y fin del diferido.
3. Captura de las pestañas "Deshabilitado" (24) y "requiere acción" (1) de Stripe. `[VERIFICAR]`
4. `paises_permitidos` y `locales_permitidos` (hoy vacíos ⇒ nada se lanza) y `mercados_test_paralelos_max` (1 hoy; comparar dos mercados a la vez exige ≥ 2).
5. Revisor nativo del idioma del primer mercado (polaco o italiano solo si salen elegidos; costo fijo del test). Sin abogado local (decisión 14): lo legal lo cubren la plantilla generada y los checks de X1.
6. Contador: tipo de IVA de un PDF (¿5 %/4 % de e-book o tasa general?), OSS no-Unión y quién presenta, registro UK, representante GDPR.
7. ¿Aceptar el hueco de PayPal en Italia/UK/CA (16-30 pp) o evaluar PayPal propio?
8. Fuente de la impresión "sobre todo Polonia" (video, canal o cifra) para registrarla como evidencia C.
9. Quebec y Brasil: ¿proyectos aparte con idioma y régimen propios?
10. Umbrales de cobertura de pago (duro 40 % / blando 55 %) y puntaje mínimo (55): ¿se aceptan como arrancan o se prefiere otra regla? Cambian qué países entran en fase vigente.
11. ¿Se testea en noviembre-diciembre (CPM de Q4, `mult_cpm` 1,2-1,5) o se espera a enero? Lo decide el dueño con O0; M1 solo informa el costo.
12. Refrescar los CPM del atlas (hoy del 2026-07-27, 102 días) con una fuente nueva: pedido a la sesión que opere `WebSearch`; mientras tanto todo CPM es `[SUPUESTO]`.

## Anexo A — Ficha de país (`paises/<ISO>.json`)

Cada campo lleva `{valor, fuente_url, fecha_lectura, confianza}`; sin `float`.

| Bloque | Campos |
|---|---|
| Identidad | `iso`, `locales[{locale, idioma, obligacion_legal_idioma}]`, `moneda_local`, `monedas_cobro_posibles`, `alcance_meta{fb}` (sin Instagram: no se opera), `estado` |
| Pagos | `metodos[{id, cuota_bp, habilitado_dueno, elegible_cuenta_us, moneda_exigida, managed_payments_ok, comision_bp, fijo, disputas{tarifa, apelable, plazo_dias}}]`, `cobertura{fase_estandar, con_locales}` (central y rango), `hueco_principal{metodo, pp, cerrable}` |
| Fiscal | `impuesto`, `tasa_bp`, `tasa_reducida_ebook_bp` `[VERIFICAR]`, `mecanismo`, `umbral`, `registro_estado`, `ventas_acum_12m` |
| Consumo y datos | `desistimiento{dias, renuncia_digital, funcion_online{fecha, estado}}`, `boton_arrepentimiento`, `privacidad{ley, cmp_modelo}`, `dsa{beneficiario_pagador}`, `identidad_vendedor` |
| Meta | `cpm_bench{monto, moneda, fecha}`, `cpm_propio`, `recargo_meta_bp` (= `tarifas.json#recargo_meta_bp` de F1; en `mercado.json` no se guarda: D3 lo copia a `economia.tarifa_meta_bp`), `verificacion_financiera`, `sonda{consulta, total, paginas_distintas, fecha}` |
| **Por macro-nicho** (proyección de solo lectura de X1, con hash de origen) | `salud/relaciones/dinero{exposicion V·A·A+·R, nivel_max_sin_gate, restricciones[{tipo, condicion, id_check}], descargos_obligatorios[], ayuda_pais{linea, verificada_por, fecha}}` |
| Localización y calidad | `registro`, `notas_culturales`, `fuentes_locales[fuente_id]`, `ultima_verificacion`, `contradicciones[]`, `revisor_nativo{estado}` |

## Anexo B — Interfaz con el radar de D1 (confirmado por D1 en `docs/_historial/d1-v2-interfaces.md` §4.2)

- **Locales activos:** un locale entra en `locales_activos.yaml` si está en `locales_permitidos`, tiene ficha vigente, glosario y `terminos_busqueda`. `prioridad` 1-5 sale del puntaje medio del locale (candidato-independiente), la evidencia propia y si hay oferta activa. **Presupuesto de exploración** por locale: `w_l = score_medio_l · (1 + 0,5·oferta_activa)`, `cuota_l = tope_barrido_global · w_l/Σw`, mínimo 1 barrido mensual por locale activo y ≤ 20 % para locales sin ficha completa; M1 reparte los topes de D1 (`max_busquedas_por_barrido`, `max_costo_por_barrido`), nunca los amplía; D1 añade `presupuesto_exploracion.max_consultas_biblioteca` (entero).
- **Transferencia:** D1 envía `{problema_id, locale_origen, locale_destino, mecanismo_traducible ∈ si·parcial·no}` y la guarda en `empresa/descubrimiento/transferencias/AAAA-MM-DD.jsonl`; M1 responde `{viable, bloqueos[], barrido_local_solicitado, requisitos}`. El problema no se asume válido: la evidencia es por locale (backbone 3.2).
- **Emparejamiento:** `S(c, m) = Σ w_k·score_k(m | c)` (CAC con `precio_plausible` de c; EXPO con `riesgo` de c; LOC con el tipo de contenido); sin evidencia local E1-E4 en m el par se marca `hipotesis_de_transferencia` y no pasa a D2 sin barrido local.
- **Fichas → radar:** `terminos_busqueda` y `fuentes_locales` quedan `[VERIFICAR]` hasta revisión nativa; los `fuente_id` los fija D1.

## Anexo C — Casos de prueba adicionales

| Caso | Entrada | Resultado esperado de M1 |
|---|---|---|
| P3 Portugal PT-PT | requiere MB WAY/Multibanco | Fase vigente: cobertura baja; con locales: sube; `pt-PT` ≠ `pt-BR` |
| 25 §8.2 pasos 2-5 | salud IT, relaciones PL, amarillo-A, amarillo-B | Cada paso reproduce el par (macro, nivel, país) permitido o con gate; Rumanía emocional bloqueada (R4); DE salud con eficacia, R3 |
| Reproducción de 08 | pesos 15·20·10·20·15·10·10 | Totales de 08 §2.2 ±1 |

## Anexo D — Matriz macro-nicho × mercado (semilla de EXPO y R3; nota 25 §8.1, `[HIPÓTESIS]`, X1 la fija)

Exposición V bajo · A medio · A+ medio-alto · R alto. Nivel máximo sin gate: V → hasta amarillo-B con ayuda verificada; A → amarillo-A (B con gate H del dueño, ayuda verificada y evidencia por una de dos vías: texto fiel a la fuente T1 verificado por script, o revisión profesional si el dueño la consigue; ninguna es obligatoria; ver conflicto C-08 en `docs/_historial/ingesta-skills-consolidado.md`); A+ → amarillo-A solo con gate H del dueño por país × macro-nicho × nivel (una vez; se registra en `empresa/decisiones_dueno.jsonl`), sin consulta legal humana: lo verifican X1 y los lints J03-J05; riesgo residual aceptado (decisión 14); R → verde y solo producto de hogar sin cifra de ahorro, instrumento ni ingreso. La matriz es por (país, macro) y por **bandera del candidato**; el overlay solo sube niveles y no reemplaza los lints J03-J05. Mientras `empresa/compliance/matriz_pais_nivel.yaml` no exista, M1 usa esta semilla y marca `[SUPUESTO]`; cuando exista manda X1 (MQ-12). **Riesgo residual aceptado por el dueño (decisión 14): sin revisión legal humana; lo verificable lo automatiza X1 y lo fiscal lo cubre el contador.**

| País | Salud | Relaciones | Dinero | Condiciones que M1 pasa a R3/R4 |
|---|---|---|---|---|
| PL | A+ | V | A+ | dinero sin cripto; sin bata ni estética clínica (UOKiK); ayuda 800 70 2222; revisor nativo por idioma × macro |
| IT | A+ | A | A+ (J05: sin instrumento, ingresos ni inversión) | «senza dieta» y plazos = patrón AGCM; ruptura y duelo con Telefono Amico |
| RO | A | V | A | sin ayuda de crisis verificada ⇒ R4 en emocional |
| FR | A+ | A | A+ | Toubon y menciones legales sin confirmar `[VERIFICAR]` (lo cierra X1 con fuente oficial; riesgo residual aceptado) |
| ES | R (condicional a «finalidad sanitaria», RD 1907/1996 art. 4) | V | A+ | verificación financiera de Meta = parada |
| DE | R para eficacia (HWG) | A (FernUSG si es «curso») | A+ (StBerG §5) | sin formato curso ni soporte; cobertura de pago ~32 % |
| GB / IE | A+ | V | A+ (J05; ingresos e inversión R) | IVA/registro desde la primera venta (UK); verificación financiera de Meta en IE |
| US | A | A | A+; inversión roja | FTC; categoría especial financiera si promociona un producto financiero |
| AU | verde y amarillo-A | verde y amarillo-A | solo verde de hogar | verificación financiera y aviso «pagado por» |
| CA / NZ / PT | CA verde y amarillo-A; NZ y PT no evaluados (heredan por analogía `[SUPUESTO]`) | ídem | CA sin hipotecas (LM-11); NZ y PT sin evaluar | PT-PT `[VERIFICAR]` |

**Orden de lanzamiento:** el de 25 §8.2 (pasos 1-5; casos en §10.5 y Anexo C) es de **riesgo y aprendizaje**, no de rentabilidad; el puntaje no lo sustituye. La ventana estacional (salud y relaciones de mediados de diciembre a abril; dinero en enero) puede adelantar una hoja verde.
