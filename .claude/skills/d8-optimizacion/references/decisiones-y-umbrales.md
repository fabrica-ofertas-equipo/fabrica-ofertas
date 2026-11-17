# Decisiones y umbrales: cada valor que hace falta, de dónde sale y quién lo firma

> v0.1 sin pulir (skill 0.1.0). Verificado contra `empresa/parametros.yaml`, `empresa/limites.yaml` y `empresa/autonomia.yaml` del 2026-11-07. **Regla de la skill: un umbral en `null` o ausente = la regla que lo necesita devuelve `NO_DECIDIR` (fail-closed). Nada se estima.** `scripts/proponer.py umbrales` imprime esta misma tabla con el estado real del día (`umbrales_faltantes`).

**Etiquetas de fuente.** `[P]` leído en pantalla del video de Juan Pablo Mentor (JPS) · `[V]` solo dicho de voz · `[P/V]` ambos · `[DECL]` cifra declarada por él, sin verificar · `[SUPUESTO]` valor o definición nuestra, sin fuente externa ni firma · `J#` decisión del dueño (`decisiones-del-dueno.md`) · `HIP` hipótesis de la especificación vieja ya cargada en `parametros.yaml` (`hipotesis: true`) · `[cálculo nuestro]` aritmética reproducible. **Quién firma:** *Dueño* = decide el valor (los de `limites.yaml` los firma él con `engine.propuestas sellar`); *S-A* = lo carga en `parametros.yaml` o el contrato; *S-B* = lo implementa el código. «Hoy» = estado de los archivos.

## A. Frenos de empresa (J4) y topes por oferta

| ID | Clave | Valor propuesto | Fuente | Firma | Hoy |
|---|---|---|---|---|---|
| U-01 | `limites.gasto_diario_global` | 300 USD/día (en unidad menor de la moneda de la cuenta). Es el techo del **máximo teórico** (× 1,75): Σ presupuestos diarios ≈ 171 USD | J4 | Dueño | `null` |
| U-02 | `limites.perdida_neta_acumulada_max` | 3.000 USD → PAUSA global automática; la levanta solo una persona | J4 | Dueño | `null`; hoy solo se comprueba al activar o subir (`engine/limites.py:343`); sin vigilante continuo (B2-04) |
| U-03 | `limites.moneda_limites` | la moneda de la única cuenta de Meta | M1/dueño | Dueño | `null` |
| U-04 | `limites.gasto_diario_por_oferta` | ≥ máximo teórico de un lanzamiento: 75 × 1,75 = 131,25 USD (13.125) `[cálculo nuestro]`; con 100 USD, 175 | derivado de J3 | Dueño | `null` |
| U-05 | `limites.gasto_total_test_por_oferta` | **a decidir.** Si se pone ≈ 1 día, un ganador se pausaría el día 2 (`engine/d8.py:254-257` lo usa como tope de celda ⇒ INCONCLUSO). Propuesta `[SUPUESTO]`: 7 × U-04, para que un ganador llegue a graduar | brecha E-04 | Dueño | `null` |
| U-06 | `limites.perdida_max_test_por_oferta` | ≈ 1 día de máximo teórico (13.125 con CBO 75) `[SUPUESTO]`. J3 dice «sin tope de pérdida por oferta»; el motor y el validador lo exigen no nulo para gastar, así que se fija en lo que la regla ya acota | brecha E-04 | Dueño | `null` (diferido 2026-11-06) |
| U-07 | `limites.ofertas_en_test_simultaneas_max` | 2 con CBO de 75 (`floor(300 / 131,25)`); 3 con 50; 1 con 100 `[cálculo nuestro]`: el guard suma **máximos teóricos** (`engine/limites.py:268-290`) | derivado de J3+J4 | Dueño | `null` |
| U-08 | `orquestador.paralelas_max_por_nivel` | hoy {N0:1, N1:1, N2:1, N3:2, N4:3}; con lanzamientos diarios que viven ≥ 1 día no alcanza | HIP (`parametros.yaml:82`) | S-A + dueño | existe; choca con J3 |
| U-09 | `limites.capital_en_riesgo_total`, `limite_gasto_cuenta_meta` | ≥ U-02 por coherencia exigida por `evaluar_limites` | — | Dueño | `null` |

## B. Regla de lanzamiento J3 (`scripts/proponer.py lanzamiento`)

| ID | Clave | Valor propuesto | Fuente | Firma | Hoy |
|---|---|---|---|---|---|
| U-10 | `lanzamiento.baja_dias` | 1 | J3 | Dueño (ya lo dijo) → S-A carga | **ausente** (no existe el grupo `lanzamiento`) |
| U-11 | `lanzamiento.baja_requiere_presupuesto_gastado` | `true` (obligatorio: el script se niega a decidir si es `false`) | J3 | Dueño (ya lo dijo) → S-A | ausente |
| U-12 | `lanzamiento.gasto_cumplido_min_pct` | 90 | `[SUPUESTO]` (brecha E-01, «punto de partida 90 % `[HIPÓTESIS]`») | Dueño el valor, S-A carga | ausente |
| U-13 | `lanzamiento.espera_post_dia_h` | 9 (= `optimizacion.hora_decision` 09:00); se recalibra con el `retraso_clic_compra` del `postmortem` | `[SUPUESTO]` | S-A | ausente |
| U-14 | `lanzamiento.dias_max_sin_entrega` | 2 | `[SUPUESTO]` | Dueño/S-A | ausente |
| U-15 | `lanzamiento.presupuesto_cbo_usd` | 50-100 (arranque 75) | J3 / `[HIPÓTESIS]` mapeo §12 | Dueño | ausente |
| U-16 | `lanzamiento.creativos_por_cbo` | ~10 | J3 | Dueño | ausente; choca con `campana.n_anuncios_tope` = 6 (`parametros.yaml:917`) |
| U-17 | Definición de «venta» | pedido pagado no de prueba ni interno, con o sin `adid`; el reembolso del mismo día no se descuenta | `[SUPUESTO]` (E-03) | S-A + S-B | texto, no clave |
| U-18 | Definición de «día» | día de cuenta (zona de la cuenta); el parcial no cuenta por la salvaguarda | `[SUPUESTO]` (E-02) | S-A | texto |
| U-19 | `testeo.tasa_conexion_min` | 0,70 (vistas de landing / clics de enlace; solo con ≥ U-20 clics) | HIP (spec vieja 09 §3.4) | S-A | `'0.70'` (`parametros.yaml:1059`) |
| U-20 | `testeo.clics_min_diag` | 100 | HIP | S-A | 100 (`:1012`) |
| U-21 | `optimizacion.lectura_horas` | 6 (frescura máxima de la lectura de Meta) | HIP | S-A | 6 (`:1231`) |
| U-22 | `testeo.ventana_no_decidir_h` | 72 en la spec vieja; **J3 la suspende** para la baja del día 1 | HIP; choca con J3 | S-A + S-B | 72 (`:996`) |
| U-23 | `estadistica.dias_madurez_compra` | 3 en el motor: `decision/entradas.py:301-303` excluye del gasto y los clics los últimos 3 días ⇒ el día 1 es invisible para `engine.d8`. Para J3 hay que separar la madurez de las compras **de Meta** de la del gasto y las ventas **de Stripe** | HIP | S-B | 3 (`:2423`) |

## C. Seguimiento continuo y graduación (E-05; J3 no lo define)

| ID | Clave | Valor propuesto | Fuente | Firma | Hoy |
|---|---|---|---|---|---|
| U-30 | criterio «rentable» (queda en testeo) | P(CPA ≤ BE) ≥ `testeo.p_escala` (0,80) con ≥ `testeo.n_dec` (15) compras; JPS: con un producto de 27 USD, un creativo a CPA 15-18 «es rentable y se queda en testeo». La skill `d9-escalado` (`d9-escalado/references/criterio-de-ganador.md` §3) usa otro: CPA neto ≤ `cpa_obj` de `economia.json`; el dueño debe unificarlos | HIP / `[V][DECL]` | Dueño (B2-06) | `p_escala` y `n_dec` existen (HIP) |
| U-31 | criterio «campeón» (se gradúa a escala) | ≥ 10 compras netas y CPA ≤ 0,40 × BE. JPS: «≥ 10 ventas a CPA 6-7» con producto de 27 USD (≈ 0,25-0,30 × BE), 3 de cada 100 creativos | `[HIPÓTESIS]` mapeo §3.2 / `[V][DECL]` | **Dueño** (B2-06) | `escalado.campeon_compras_min` y `campeon_cpa_max_x_be` **ausentes** |
| U-32 | ventana de la tendencia | 3 días («¿vende en 3 días?» `[P 36:59]`; regla de oro 3 `[P 43:58]`) | `[P]` | Dueño | ausente (`graduacion.ventana_dias`) |
| U-33 | `escalado.promocion_min_compras` | 5 (D9) | HIP | S-A | 5 (`:1399`); otro criterio más (B2-06) |
| U-34 | `auditor.acierto_min` (misma clave que pide `d9-escalado`) | cortes 0,5 y subas 0,6; ventana 72-96 h; JPS 3 h `[P]`; midió 3 de 4 cortes y 1 de 3 subas `[DECL]` | `[HIPÓTESIS]` mapeo §12 | S-A + S-B | ausente |
| U-35 | «7 días: lo máximo que dura un freno automático» `[P 38:49]` | todo freno de un robot caduca a los 7 días y se reevalúa `[inferencia]` | `[P]` | S-A + S-B | ausente |

## D. Fatiga y relevo (`scripts/proponer.py fatiga`)

| ID | Clave | Valor propuesto | Fuente | Firma | Hoy |
|---|---|---|---|---|---|
| U-40 | `testeo.fatiga_ventana_reciente_dias` / `_previa_dias` | 3 / 7 («últimos 3 días contra los 7 anteriores» `[P 08:05]`) | `[P]` | S-A | **ausentes** |
| U-41 | `testeo.fatiga_caida_ctr_pct` | 30 (JPS: umbral de «cansado» `[?]`, no lo dice) | HIP | S-A | 30 (`:1099`); sin consumidor en el motor |
| U-42 | `testeo.fatiga_factor_cpa` | 1,5 | HIP | S-A | `'1.5'` |
| U-43 | `testeo.fatiga_senales_min` | 2 señales | HIP | S-A | 2 |
| U-44 | `testeo.freq_alerta_7d` | 2,5 (la frecuencia no está en la base: `fact_meta_ad_dia` no la guarda; es opcional en la entrada) | HIP | S-A + S-B (ETL) | `'2.5'` (`:1091`) |
| U-45 | `testeo.fatiga_lecturas_seguidas` | 2 («2 lecturas seguidas», `departamentos/09-optimizacion.md:112`) | spec vieja | S-A | **ausente** |
| U-46 | `testeo.fatiga_compras_min` | 3 («con ≥ 3 compras; si no, costo por IC», `:112`) | spec vieja | S-A | **ausente** |
| U-47 | `testeo.impr_min_diag` | 3.000 impresiones por ventana | HIP | S-A | 3000 |
| U-48 | `testeo.k_corte` | 3 (gasto reciente suficiente para esperar ventas: ≥ 3 × CPA previo) | HIP | S-A | 3 |
| U-49 | `optimizacion.max_pedidos_abiertos` / `dias_entre_pedidos` / `cantidad_max_pedido` | 1 / 5 / 5 | HIP | S-A + dueño | existen (`:1262-1278`); chocan con el ritmo diario de J |
| U-50 | `creativos.reserva_conceptos` (banco de suplentes) | 2 conceptos (solo guion y copy, sin assets) | HIP (D6) | S-A | 2 (`:861`); JPS no da la cifra |
| U-51 | alcance de la alarma | JPS la aplica a los creativos de la **escala** `[V 40:00]`; D8 evalúa los de TEST con historial de ventas; la escala es de D9 | `[V]` | S-A | n/a |

## E. Control de lo apagado (falsos descartes)

| ID | Clave | Valor propuesto | Fuente | Firma | Hoy |
|---|---|---|---|---|---|
| U-60 | `estadistica.control_fraccion` / `control_fraccion_presupuesto` / `control_gasto_max_k` | 0,15 / 0,25 / 2,0 | HIP (`docs/08` §4.5) | Dueño decide si aplica a los lanzamientos J3 (cuesta dinero: `estadistica-honesta.md` §5) | existen (`:2380-2395`) |

## F. Preguntas abiertas para el dueño (ordenadas por lo que bloquea)

1. **Firmar `limites.yaml`** con J4 y los topes por oferta (U-01 a U-07, U-09), la moneda y los topes por oferta coherentes entre sí. Sin esto el guard no gasta y D8 devuelve `BLOQUEADO`. Atención a U-05: no fijarlo en 1 día.
2. **Confirmar los valores `[SUPUESTO]` de J3:** 90 % de gasto cumplido (U-12), 2 días sin entrega antes de pausar (U-14), definición de «venta» y de «día» (U-17, U-18), espera de 9 h (U-13).
3. **Criterio de campeón y ventana de tendencia** (U-31, U-32; B2-06): ¿cuál rige para graduar, cuál para escalar y cuál para VALIDADA?
4. **¿El gate de pausar baja a A desde N0?** J2 («su modelo desde el día 1») lo implica; `contratos/gates.json` `accion:pausar` N0-N1 = H y `autonomia.yaml` D8 = N0 (`PEDIDOS.md` P-01).
5. **¿Qué pasa con una oferta apagada?** ¿Se puede relanzar una variante sin `reabrir_fallida` por cada una? (`PEDIDOS.md` P-08)
6. **¿Se activa el control de falsos descartes?** Cuesta (`estadistica-honesta.md` §5); sin él la tasa de falsos descartes se estima solo con el modelo de Poisson.
7. **Las dos extensiones nuestras a J3** (conexión de landing y datos obsoletos) ¿se quedan o se quitan? Solo pueden evitar una baja, nunca provocarla.
