# 08 — Protocolo estadístico del testeo

> Versión 1 · 2026-11-06 · Rol: estadístico/a aplicado/a a experimentación publicitaria. Contrato maestro: `docs/_backbone.md` v2.2 (prevalece). Código: `decision/estadistica.py`, `presupuesto.py`, `reglas.py`, `simulacion.py`; pruebas en `tests/decision/`.
> **Alcance:** cómo se decide, con números, si un anuncio, un ángulo, una oferta en un mercado, un mercado frente a otro o una oferta entera sobreviven a un testeo pagado en Meta; cuánto cuesta decidir; y cómo se automatiza con código determinista. **No fija** ningún tope de gasto ni la pérdida máxima por oferta (decisión del dueño del 2026-11-06: se definirán después a partir de los presupuestos de testeo). Todo umbral es paramétrico (`empresa/parametros.yaml`), todo tope viene de `empresa/limites.yaml`; si falta el tope, el código devuelve BLOQUEADO y no se gasta.
> **Etiquetas:** `[HIPÓTESIS]` = a calibrar con datos propios; `[VERIFICAR]` = hecho externo sin confirmar; `[NUEVO]` = aporte de esta nota. Los hechos de Meta y Stripe se heredan de las notas 03, 04, 12 y 16 (cada una cita su fuente oficial); no se consultó ninguna fuente nueva. Los números de las secciones 3 y 5 salen de ejecutar el código del repositorio.
> **Dinero:** montos acumulados (precio, CPA de equilibrio, gasto, tope) en enteros de unidad menor con moneda ISO 4217. CPC y CPM son tasas de costo unitario: `float` en unidad menor por clic (0,31 USD = 31,0), porque redondearlos a entero pierde hasta 10 % de precisión. Los valores esperados se calculan en coma flotante y se redondean half-even al salir.

---

## 0. Resumen ejecutivo

1. **Se decide por P(CPA neto real ≤ equilibrio de `economia.json`)**, con compras válidas de Stripe; nunca por "una venta" ni por las compras que reporta Meta.
2. **Diseño: bayesiano secuencial con prior débil, calibrado por simulación.** Conversión clic→compra ~ Beta (prior de ~50 clics, menos de una compra de información); clics por unidad de gasto ~ Gamma. Mirar los datos a diario rompe los valores p clásicos, así que se reportan las tasas de error de la regla completa (ganadores descartados, perdedores escalados, gasto hasta decidir).
3. **Cortar a 10 USD sin venta es inválido:** mata al 54 % de los ganadores cuyo CPA es 16,2 USD (0,6 × un equilibrio de 27 USD). La regla propuesta descarta al 2 % (3.000 corridas).
4. **El costo de decidir es una función:** descartar un perdedor cuesta ~ln(1/α) × CPA de equilibrio (≈ 3 × con α = 5 %), sin importar el CPC; confirmar un ganador, ~16 ×; estimar la conversión con ±25 %, ~2.400 clics (743-1.223 USD a los CPC de la nota 16, reproducido).
5. **Un tope de ~15 × el equilibrio por celda mata perdedores y escala ganadores holgados, pero no resuelve ofertas "casi buenas":** con CPA entre 0,7 y 1,0 × equilibrio, 59-72 % de las corridas terminan INCONCLUSAS. Es el insumo para que el dueño fije el tope más adelante.
6. **Meta condiciona el diseño:** ~50 eventos por semana por conjunto es un diagnóstico, no una puerta, pero a estos CPA un conjunto de test casi siempre queda en aprendizaje limitado; por eso se decide con compras acumuladas de Stripe, con un solo conjunto (CBO_1AS) y aumentos ≤ +20 % cada ≥ 72 h con ≤ 4 cambios por hora.
7. **Comparar mercados es caro:** ver +50 % relativo en la conversión (2,5 % frente a 3,75 %) exige ~2.400 clics por mercado (~2.600 USD para dos). Polonia e Italia no tienen ventaja previa.
8. **"Oferta validada" (backbone 5.9)** se calcula sobre cohortes maduras (garantía + 7 días), netas de reembolsos e IVA, con el equilibrio recalculado con comisiones y reembolsos reales.

---

## 1. Qué se decide en un testeo

### 1.1 Cinco decisiones, cinco métricas

| # | Decisión | Unidad | Métrica | Resultado posible | Error que se vigila | Código |
|---|---|---|---|---|---|---|
| T1 | ¿Seguir gastando en este anuncio? | anuncio | P(CPA ≤ equilibrio) con las compras de Stripe del anuncio | MATAR / SEGUIR / (ESCALAR no aplica) | descartar un ganador | `evaluar_celda` (nivel `anuncio`) |
| T2 | ¿Qué ángulo funciona mejor? | ángulo (anuncios agrupados) | P(conversión más alta) y conversión con intervalo | ranking, etiqueta `exploratorio` si hay < 20 compras | declarar ganador a un ruido | `ranking_hermanos` |
| T3 | ¿La oferta merece más gasto en este mercado? | oferta-mercado | P(CPA ≤ equilibrio), P(CPA ≤ objetivo), CPA típico | MATAR / SEGUIR / ESCALAR / INCONCLUSO | descartar un ganador; escalar un perdedor | `evaluar_celda` (nivel `oferta_mercado`) |
| T4 | ¿Qué mercado o idioma conviene más para la MISMA oferta? | mercado | P(margen por clic de A > B) | ordenar, empatar o seguir probando | atribuir a la geografía lo que es ruido | `prob_margen_por_clic_mayor` |
| T5 | ¿La oferta está validada? | oferta | CPA neto de cohorte madura frente a CPA objetivo real; ROAS neto | VALIDADA / PROVISIONAL / PROMETEDORA / FALLIDA / INCONCLUSA | validar con reembolsos aún sin madurar | `evaluar_oferta_validada` |

T1-T3 comparten la misma función porque el problema estadístico es idéntico (una celda acumula clics, gasto y compras); cambian el tope de gasto y los parámetros. T3 es el corazón: sus tasas de error son las que valida la sección 5.

### 1.2 Métrica: CPA neto frente al equilibrio

- **CPA** = gasto de Meta (con la tarifa de Meta del país, si existe) ÷ compras de Stripe válidas atribuidas al anuncio (pagadas, no reembolsadas ni disputadas, sin modo test, sin duplicados por `email_hash`). El gasto sale de Meta; los ingresos y las compras, de Stripe (backbone 5.3).
- **CPA de equilibrio** (`CPA_BE`) = contribución por pedido `MC` de `economia.json`: precio con bump esperado, menos IVA, comisión de Stripe (porcentaje, fija y recargos), Stripe Tax, reembolsos esperados, disputas esperadas y costo variable (`economia_por_pedido`). **CPA objetivo** = f × `CPA_BE` (f = 0,6 en D3). Lo que ve Ads Manager es `MC / (1 + tarifa_meta)`; el código distingue ambos.
- **Conversión de equilibrio** `c* = CPC / CPA_BE`: la conversión clic→compra mínima para no perder dinero. Es el "objetivo" de toda la estadística.
- **ROAS neto** = contribución neta de cohorte ÷ gasto; su equilibrio es 1. Se cumple CPA ≤ f × `CPA_BE` si y solo si ROAS neto ≥ 1/f (1,67 con f = 0,6). Por eso el dashboard puede mostrar cualquiera de los dos y las reglas decidir con el CPA.
- **Nunca** "una venta": una compra no distingue un anuncio de CPA 5 de uno de CPA 50 (sección 4.3).

### 1.3 Error tolerable: bayesiano con prior débil, elegido y justificado

Un contraste frecuentista (valor p por celda) responde "¿rechazo conv ≤ c*?"; el bayesiano responde directamente "¿cuál es hoy P(CPA ≤ equilibrio)?", que es la cantidad que decide. **Elección:** modelo bayesiano para decidir y calibración frecuentista por simulación para medir los errores. Razones: (1) los datos llegan a diario y se actúa a diario (D8 lee cada 6 h y decide una vez al día), y espiar invalida el valor p; (2) con 2-10 compras por celda un intervalo frecuentista solo dice "no significativo", mientras que la posterior con prior débil encoge hacia lo esperado sin imponer una creencia fuerte; (3) los costos asimétricos se codifican con umbrales distintos (matar 95 %; escalar 80 % más compras mínimas y CPA típico ≤ objetivo); (4) los errores de espiar a diario se miden en el mismo código que correrá en producción.

**Tolerancias de partida** `[HIPÓTESIS]`, medidas en la sección 5:

- Ganador (CPA ≤ objetivo = 0,6 × equilibrio) descartado: ≤ ~4 % de las corridas. Un ganador justo (CPA ≈ 0,85 × equilibrio) puede perderse hasta ~14 %: aporta poco y es caro de confirmar.
- Perdedor (CPA ≥ 1,3 × equilibrio) escalado: ≤ 0,5 %.
- Perdedor severo (CPA ≥ 4 × equilibrio) muerto con un gasto medio de ~3,5 × equilibrio.

Matar exige más (95 %) que escalar (80 %) porque matar un ganador pierde toda su rentabilidad futura, mientras que escalar es gradual (≤ +20 % por paso, reversión automática en D9) y ya exige tres condiciones: ≥ 15 compras, P ≥ 80 % y CPA típico ≤ objetivo.

---

## 2. Modelo y fórmulas

**Datos de una celda:** gasto `G` (unidad menor), clics de enlace `n`, compras de Stripe `k`. Se usan clics de enlace y no vistas de landing: no dependen del banner de consentimiento ni del navegador interno de Meta, así que el denominador no se degrada en la UE (nota 16, H4).

**Conversión.** `conv ~ Beta(a0 + k, b0 + n − k)`. El prior se construye con la conversión central esperada de D3 (`conv_central`) y una fuerza `prior_conv_fuerza_clics` (a0 + b0), 50 `[HIPÓTESIS]`: con conv_central = 2 % equivale a 1 compra en 50 clics. **Clics por unidad de gasto.** `lam ~ Gamma(α0 + n, β0 + G)` con `CPC = 1/lam`; el prior es el CPC esperado de D3 con peso `prior_cpc_fuerza_clics` (20 clics).

**CPA y su probabilidad.** `CPA = 1 / (lam × conv)`. `CPA ≤ L` equivale a `conv ≥ 1/(L × lam)`, así que `P(CPA ≤ L) = E_lam[ 1 − BetaCDF(1/(L·lam); a, b) ]`. La esperanza sobre `lam` se calcula de forma determinista con `nodos_cpc` cuantiles de la Gamma (5 por defecto): sin Monte Carlo en producción. Funciones: `prob_cpa_menor`, `cpa_mediano_minor`, `intervalo_cpa_minor` (intervalo creíble aproximado con el CPC en su media posterior). Para F1, que reporta IC90 Poisson del CPA con pocas compras, `intervalo_cpa_poisson_minor` da el intervalo exacto de Garwood.

**Dos precauciones sobre el prior** `[NUEVO]`:

1. Si la conversión esperada de D3 está muy por debajo de `c*`, la posterior ya cree que la celda pierde y podría matar con muy poco gasto. Por eso `evaluar_celda` impone un piso de gasto `k_min_matar × CPA_BE` (2 ×) y `plan_celda` lo incluye en el costo de descartar: el prior encoge, el piso protege.
2. La media del prior sale de un escenario `[HIPÓTESIS]` de D3: si subestima la conversión real la regla es más severa de lo debido. La fuerza de 50 clics hace que 150-200 clics reales ya pesen 3-4 veces más que el prior.

**Compras tardías.** Meta atribuye con ventana de 7 días de clic y Stripe registra la compra cuando ocurre: una parte de las compras de los clics de hoy llegará en los próximos días. Esto sesga la conversión observada **a la baja** y favorece matar ganadores. El modelo no lo corrige (limitación L1); lo mitigan la ventana de no decidir (72 h), la marca `datos_maduros` (últimos 2 días inmaduros, nota 04 HC-45) y el piso de gasto. Medir la distribución real del retraso clic→compra en las primeras ofertas es la primera calibración prioritaria.

---

## 3. Calculadoras de presupuesto (`presupuesto.py`)

### 3.1 Economía por pedido

`economia_por_pedido(ParametrosPrecio)` implementa las fórmulas de D3/F1 (precio con IVA incluido):

```
AOV = P + b·Pb + u·Pu            neto = AOV − IVA        IVA = AOV · t/(1+t)
comisión = pct·AOV + fija·(1+u)  stripe_tax = pct_tax·AOV + fijo_tax·(1+u)
MC = neto − comisión − stripe_tax − r·neto − d·(neto + tarifa_disputa) − costo_var
CPA_BE = MC    CPA visto = MC/(1 + tarifa_meta)    CPA_obj = f · CPA visto
```

El reembolso devuelve bruto e IVA pero la comisión se pierde (03 §4.3): por eso `r` multiplica el neto y la comisión se resta entera. Las pruebas reproducen tres vectores publicados:

| Vector | Fuente | Resultado del código |
|---|---|---|
| P = 27, bump 10 % × 9, 2,9 % + 0,30, r = 7 %, d = 0,5 %, costo var. 0,20 | D3 §3.4 | AOV 27,90; CPA_BE 24,42 (D3: ≈ 24,4) |
| P = 17, bump 30 % × 7, 4,4 % + 0,30, r = 7 %, d = 0,5 % | F1 §3.5 | AOV 19,10; MC 16,25; CPA_obj 9,75 |
| Italia base, frontal 17,28 USD con IVA 22 %, 5,4 % + 0,30, Tax 0,5 %, r = 8 %, d = 0,6 %, Meta +3 % | nota 16 §2.2 | CPA_BE 11,54 (nota: ≈ 11,6); visto en Ads Manager 11,20 (≈ 11,3) |

La diferencia con la nota 16 viene de cómo cuenta las disputas (D3 resta neto más tarifa; la nota 16, solo la tarifa de 15 USD). El código sigue D3, que es el contrato de `economia.json`.

### 3.2 Clics y presupuesto mínimos por celda

`plan_celda(EntradaPlan)` devuelve tres cantidades de clics y su gasto (`clics × CPC`). Con `c* = CPC/CPA_BE`, `c_gan = CPC/CPA_obj`:

- **Descartar** (`clics_para_descartar_sin_compras`): menor `n` con P(conv > c* | 0 compras) ≤ α. Con prior casi plano es `ln(1/α)/c*` clics, es decir un gasto de **ln(1/α) × CPA_BE** (≈ 3,0 × para α = 5 %), **independiente del CPC**: un CPC alto exige menos clics pero cada uno cuesta más. Con un prior informativo es menor; el piso `k_min_matar × CPA_BE` lo corrige.
- **Confirmar un ganador** (`n_contraste_unilateral(c*, c_gan, α, potencia)`): clics para distinguir un ganador de CPA = objetivo del equilibrio con error α y potencia 80 %. Es la cantidad cara.
- **Precisión** (`n_precision_relativa`): clics para estimar la conversión central con semiancho relativo de 25 % y 95 %.

`gasto_recomendado = max(descartar, confirmar)`; `gasto_total = × n_celdas × (1 + tarifa_meta)`. `autorizado` es verdadero solo si hay tope cargado y el recomendado cabe; sin tope, `autorizado = False` y un aviso cita `limites.yaml`.

### 3.3 Reproducción de la nota 16 (~2.400 clics, 740-1.220 USD)

```
python3 -c "from decision.presupuesto import presupuesto_precision as p; print(p(0.025,0.25,0.95,31.0), p(0.025,0.25,0.95,51.0))"
```

Para estimar una conversión de 2,5 % con ±25 % relativo (IC 95 %): `n = z²(1−p)/(p·rel²) = 2.398` clics (60 compras). A CPC 0,31 USD son **743 USD**; a CPC 0,51 USD, **1.223 USD**: coincide con la nota 16. Con 5 compras en 241 clics el intervalo exacto de Clopper-Pearson al 95 % es 0,68 %-4,77 % (nota 16: 0,67-4,76 %); con 147 clics, 1,11-7,76 %. La tabla "Nivel 2" de la nota 16 (abandonar si compras ≤ k, con prior uniforme y P < 5 %) se reproduce exactamente en las pruebas:

| Clics | Abandonar si compras ≤ (c* = 2 %) | (c* = 3 %) | Seguir si compras ≥ (c* = 2 %) | (c* = 3 %) |
|---|---|---|---|---|
| 500 | 4 | 8 | 13 | 18 |
| 1.000 | 12 | 20 | 24 | 35 |
| 2.000 | 29 | 47 | 45 | 66 |

La nota 16 tiene razón en que la precisión absoluta es cara; este protocolo la **generaliza**: lo que se compra no es precisión sino la capacidad de tomar una decisión concreta (matar, escalar), que cuesta menos o más según el caso.

### 3.4 Tabla de sensibilidad

Producida por `tabla_sensibilidad` (α = 5 %, potencia 80 %, prior 2 % de fuerza 50, f = 0,6), con `CPA_BE` visto = 14,78 USD (Italia, caso base de la nota 16). Reproducir: `python3 -c "from decision import presupuesto as p; [print(f) for f in p.tabla_sensibilidad(1478,0.6,[31.0,51.0,85.0],[0.01,0.02,0.03,0.04],0.05,0.8,0.02,50.0)]"`.

| CPC (USD) | c* | Clics para descartar* | Gasto para descartar | Clics para confirmar un ganador (CPA = 0,6 × BE) | Gasto para confirmar |
|---|---|---|---|---|---|
| 0,31 | 2,10 % | 93 | 28,8 | 780 | 241,8 |
| 0,51 | 3,45 % | 37 | 18,9 | 466 | 237,7 |
| 0,85 | 5,75 % | 2 | 1,7 | 271 | 230,4 |

\* Sin el piso de `k_min_matar`: el prior de 2 % ya sospecha de conversiones altas, por eso descartar casi no cuesta clics; el piso (2 × 14,78 = 29,6 USD) es el gasto efectivo mínimo. **Descartar cuesta ~3 × CPA_BE y confirmar un ganador ~16 × CPA_BE, casi independientes del CPC; con CPA_BE de 11,30 (Polonia base) o 24,42 (ejemplo D3) escalan a ~180 y ~400 USD.** La razón CPA/equilibrio de cada par es `CPC / (conv × CPA_BE)`: con CPC 0,51 USD y conversión 2 %, 1,73; con 4 %, 0,86. El equilibrio manda el presupuesto.

### 3.5 Efecto mínimo detectable

`mde_relativo(clics, conv_base, α, potencia)` da el aumento relativo de la conversión que una prueba unilateral detecta. Contra una base de 2,5 % y con 2.400 clics el efecto mínimo es +33 %; con 500 clics, mucho mayor. Para comparar dos brazos (mercados, ángulos) hacen falta clics **por brazo** (`n_dos_proporciones`): +50 % relativo con 2,5 % de base cuesta 2.393 clics por brazo (α = 10 % bilateral, potencia 80 %). Los diferenciales de 20-30 % de los anuncios de un mismo mercado son indetectables con presupuestos de test.

### 3.6 Aprendizaje limitado de Meta

`eventos_semanales_esperados = 7 × presupuesto_diario / CPA`; para 50 eventos por semana (nota 04 HC-1) el presupuesto es `50/7 × CPA`: con CPA esperado de 14,78 USD son **105,6 USD por día por conjunto**; con 30 USD diarios se obtienen ~14 eventos por semana. `evento_optimizacion_recomendado` replica la regla de D7: `PURCHASE` si el presupuesto cubre al menos la mitad del necesario (`meta_fraccion_min_purchase`), si no `INITIATE_CHECKOUT` (evento más frecuente, que Meta recomienda). Se decide siempre por compras de Stripe, no por el evento optimizado, y con el aprendizaje limitado asumido (HC-1: "no es una penalización").

---

## 4. Reglas de decisión secuenciales (`reglas.py`)

### 4.1 Estados y orden

`evaluar_celda(EvidenciaCelda, ParametrosDecision, LimitesCelda) -> Decision` es una función pura. Manda la primera condición que se cumple:

| Orden | Condición | Acción | Código |
|---|---|---|---|
| 0 | Falta el tope de gasto de `limites.yaml`, moneda distinta o datos inconsistentes | BLOQUEADO | `sin_limites`, `moneda_distinta`, `datos_invalidos` |
| 1 | 0 clics | SEGUIR (o INCONCLUSO si ya se alcanzó el tope) | `sin_evidencia`, `tope_sin_clics` |
| 2 | Gasto ≥ `k_min_matar` × CPA_BE, tracking sano y P(CPA > BE) ≥ 1 − α (1 − α_tope al llegar al tope). Con ventana de no decidir o datos inmaduros solo se mata con 0 compras | MATAR | `sin_compras`, `cpa_peor_que_equilibrio` |
| 3 | Compras ≥ `n_min_escala`, P(CPA ≤ BE) ≥ `p_escala`, CPA típico ≤ objetivo, fuera de ventana, tracking sano | ESCALAR (propuesta a D9) | `ganador_probable` |
| 4 | Gasto ≥ tope sin lo anterior | INCONCLUSO | `tope_sin_veredicto`, `tope_con_datos_dudosos` |
| 5 | Resto | SEGUIR | `sin_evidencia`, `tracking_dudoso`, `ventana_no_decidir`, `prometedora`, `zona_gris` |

La salida es un `Decision` con `accion`, `codigo`, `explicacion` en lenguaje natural con las cifras (compras, clics, gasto, CPA típico con IC90, P(CPA ≤ equilibrio), P(CPA ≤ objetivo), tope), todos los umbrales usados y `a_dict()` serializable para `empresa/registro.jsonl` y `decisiones.jsonl`. Ejemplo de explicación real: *"ESCALAR (propuesta a D9, dentro del paso permitido): 20 compras en 300 clics y 120,00 USD; CPA típico 6,68 USD (IC90 4,82 USD a 9,69 USD); equilibrio 15,00 USD, objetivo 9,00 USD; P(CPA<=equilibrio)=99,9 %, P(CPA<=objetivo)=90,3 %. Cumple 20 >= 15 compras, …"*.

Correspondencia con D8: MATAR cubre K1 y K3; ESCALAR, E (necesita además VALIDADA confirmada por H); SEGUIR, M; INCONCLUSO, el cierre por tope (G5); los guardarraíles G (PAUSA, límites de cuenta, modo ciego) siguen fuera de esta función y tienen prioridad. Esta función no reactiva ni activa nada.

### 4.2 Umbrales (todos paramétricos)

| Parámetro | Valor inicial | Rol |
|---|---|---|
| `alfa_descarte` | 0,05 | matar si P(CPA > BE) ≥ 95 % |
| `alfa_descarte_tope` | 0,20 | al agotar el tope: matar si P(CPA > BE) ≥ 80 % (D8 `p_cierre_tope`) |
| `k_min_matar` | 2,0 | gasto mínimo para matar = 2 × CPA_BE |
| `p_escala`, `n_min_escala` | 0,80 y 15 | escalar con P(CPA ≤ BE) ≥ 80 % y ≥ 15 compras (D3/D8 `N_dec`) |
| `ventana_no_decidir_h` | 72 | tras activar o editar de forma significativa |
| `prior_conv_fuerza_clics`, `prior_cpc_fuerza_clics` | 50 y 20 | prior débil |

### 4.3 Falsos descartes: cuánto mata "cortar a 10 USD sin venta" y cómo evitarlo

Con un proceso de Poisson de compras, la probabilidad de gastar `G` sin ninguna venta siendo el CPA real `c` es `e^(−G/c)`. Tabla (% de ganadores muertos por el corte clásico), reproducible con `prob_sin_compras_poisson`:

| CPA real del ganador (USD) \ corte | 6 USD | 8 USD | **10 USD** | 15 USD | 30 USD | 45 USD |
|---|---|---|---|---|---|---|
| 6,5 (0,5 × equilibrio de 13) | 39,7 % | 29,2 % | 21,5 % | 9,9 % | 1,0 % | 0,1 % |
| 9,0 | 51,3 % | 41,1 % | 32,9 % | 18,9 % | 3,6 % | 0,7 % |
| 13,0 | 63,0 % | 54,0 % | 46,3 % | 31,5 % | 9,9 % | 3,1 % |
| **16,2** (0,6 × equilibrio de 27) | 69,0 % | 61,0 % | **53,9 %** | 39,6 % | 15,7 % | 6,2 % |
| 27,0 (en el equilibrio) | 80,1 % | 74,4 % | 69,0 % | 57,4 % | 32,9 % | 18,9 % |

El ~54 % corresponde a un ganador en el CPA objetivo de una oferta de 27 USD (equilibrio 27, f = 0,6) cortado a 10 USD; la simulación lo confirma (33,5 % simulado frente a 32,9 % analítico para CPA 9; las nueve combinaciones corridas coinciden). Cómo lo evita el protocolo:

1. **Gasto mínimo proporcional al equilibrio.** Descartar con error ε a un ganador de CPA `c` exige gastar `c × ln(1/ε)` (`gasto_minimo_para_error`): 5 % pide 3,0 × `c`, 48,5 USD para el ganador de 16,2 USD, no 10. El piso `k_min_matar × CPA_BE` y la probabilidad posterior hacen que ese sea el mínimo efectivo.
2. **Una sola regla de muerte, probabilística.** La cascada CTR → carrito → venta acumula descartes (nota 12 §7.2: > 25 %; `prob_descarte_en_cascada([0,2; 0,2; 0,2])` = 48,8 %). Aquí CTR y señales intermedias **ordenan** (T2) pero no matan.
3. **Cualquier compra cambia la regla:** con ≥ 1 compra decide la posterior entera, no el "cero ventas".
4. **Control sobre lo apagado** (4.5) y **INCONCLUSO en lugar de MATAR** cuando, al llegar al tope, la evidencia no separa el CPA del equilibrio: los casos ambiguos pasan a decisión humana.

Resultado medido (sección 5): un ganador en el CPA objetivo se descarta en el **2,1 %** de las corridas (4,0 % con sobredispersión de la conversión), frente a 32,9-53,9 % del corte a 10 USD.

### 4.4 Mirar a diario: qué cuesta

Una regla que mira cada día con umbral de 95 % descarta más ganadores que el 5 % nominal de una prueba única; por eso se **simula tal como corre** (lectura diaria, ventana de 72 h, tope, ruido de gasto y CPC). Medido: ganador en el objetivo, 2,1 % descartado; ganador justo (0,85 × equilibrio), 9,1 % antes del tope y 13,7 % en total (el resto, al llegar al tope con el umbral relajado de 80 %); en el equilibrio exacto, 31 %, que no es un error económico (margen cero).

### 4.5 Grupo de control de lo apagado (10-20 %)

`plan_grupo_control` elige, por un hash determinista de la semilla y el id, un 10-20 % de las celdas apagadas (`control_fraccion`, 0,15) para que sigan vivas como **control**, con una fracción de su presupuesto previo (0,25) y un gasto máximo propio (`control_gasto_max_k` × CPA_BE). Se evalúan con la misma función; las que luego cumplen ESCALAR o P(CPA ≤ BE) ≥ `p_escala` son **falsos descartes** (`estimar_falsos_descartes` da la tasa con IC exacto).

El control **no rescata** una celda: es un instrumento de calibración que agrega muchas ofertas. Detectar una tasa de falsos descartes de 10 % frente a 5 % exige ~150 controles acumulados (unilateral, α = 5 %, potencia 80 %; `n_controles_para_detectar`), unas 15 ofertas con 10 celdas apagadas cada una; 15 % frente a 5 % exige ~44. Su costo máximo es `len(control) × gasto_max`. En CBO_1AS no se puede forzar gasto a un anuncio (el algoritmo reparte): ahí el control es una **reapertura programada** en una campaña REFRESCO acotada, o una celda propia si la estructura es ABO.

### 4.6 Compatibilidad con las restricciones de Meta

| Restricción | Fuente | Cómo se aplica |
|---|---|---|
| ~50 eventos de optimización por semana por conjunto para salir de aprendizaje limitado; es un diagnóstico, no una penalización | 04 HC-1 (oficial) | `eventos_semanales_esperados`; se decide con compras de Stripe acumuladas; un solo conjunto (CBO_1AS) para concentrar eventos; `INITIATE_CHECKOUT` si el presupuesto no alcanza |
| Una edición significativa (creativo nuevo, agregar un anuncio, audiencia, evento, pausar ≥ 7 días) reinicia el aprendizaje | 04 HC-3 | `horas_desde_edicion` entra a la regla; ventana de no decidir de 72 h; no se agregan anuncios a un conjunto que aprende |
| Aumento ≤ 20 % por paso y ≥ 72 h entre aumentos | heurística profesional (04 S-9; HC-3 no publica un porcentaje oficial) y `limites.yaml` | `proponer_aumento_presupuesto` recorta al paso, exige las horas y devuelve el instante del próximo intento |
| ≤ 4 cambios de presupuesto por hora por conjunto; ≥ 30 s entre ediciones del mismo objeto | 04 DV-2 (oficial) | mismo función: bloquea y calcula la espera |
| Gasto diario hasta 1,75 × el presupuesto | 04 HC-26 (oficial) | el techo diario se compara contra `nuevo × 1,75` y recorta el aumento para que no lo supere |
| Resultados maduros después de ~48 h | 04 HC-45 | `datos_maduros`; las compras de los últimos 2 días no deciden salvo 0 compras |

`pasos_para_alcanzar(3.000, 30.000, 0,20, 72)` da 13 aumentos y 36 días: **multiplicar por diez un presupuesto con el paso máximo tarda cinco semanas.** Los saltos mayores son campañas ESCALA nuevas (D9), que cuentan como un paso. Si no hay techo diario cargado, `proponer_aumento_presupuesto` no permite nada.

### 4.7 Lo que esta regla no hace

No compara CPA entre anuncios con < 20 compras totales (ranking "exploratorio"), no reabre lo pausado, no modifica Meta, no define el tope ni corrige compras tardías; la "maldición del ganador" se atenúa (prior, 15 compras) pero no se elimina.

---

## 5. Simulaciones Monte Carlo (`simulacion.py`)

**Diseño.** Una celda se simula día a día hasta MATAR, ESCALAR o INCONCLUSO. Cada día: gasto = presupuesto × lognormal (σ = 0,15, tope 1,75 ×), CPC del día × lognormal (σ = 0,20), clics ~ Poisson, compras ~ Binomial(clics, conversión), tracking sano, la regla completa de 4.1 con ventana de 72 h desde la activación. Semilla fija (`random.Random(semilla × 1.000.003 + i)`). Economía de referencia: equilibrio 15,00 USD, objetivo 9,00 USD, 15 USD de presupuesto diario y un tope de 225 USD (15 × equilibrio) **solo como dato de prueba**: el tope real lo fija el dueño. Reproducir: `python3 -m decision.simulacion --corridas 3000 --semilla 20261106` (≈ 40 s). Las pruebas del repositorio corren 160 corridas por escenario con tolerancias explícitas.

### 5.1 Seis escenarios de CPC y conversión (3.000 corridas)

| Escenario | CPC | Conv. | CPA/BE | MATAR (antes del tope) | ESCALAR | INCONCLUSO | Gasto medio / mediana / p90 (USD) | Días | Compras |
|---|---|---|---|---|---|---|---|---|---|
| A ganador fuerte, CPC bajo | 0,25 | 3,70 % | 0,45 | 0,1 % (0,1 %) | 96,5 % | 3,4 % | 110 / 103 / 154 | 7,4 | 16,9 |
| B ganador en objetivo, CPC alto | 0,45 | 5,00 % | 0,60 | 2,1 % (2,0 %) | 60,9 % | 37,0 % | 162 / 153 / 225 | 11,0 | 18,7 |
| C ganador justo | 0,35 | 2,75 % | 0,85 | 13,7 % (9,1 %) | 13,2 % | 73,1 % | 199 / 225 / 225 | 13,7 | 16,2 |
| D equilibrio | 0,40 | 2,67 % | 1,00 | 31,1 % (18,8 %) | 3,9 % | 65,0 % | 195 / 225 / 225 | 13,4 | 13,4 |
| E perdedor moderado | 0,45 | 2,00 % | 1,50 | 79,3 % (59,1 %) | 0,2 % | 20,6 % | 148 / 165 / 225 | 10,1 | 6,8 |
| F perdedor severo | 0,70 | 1,00 % | 4,67 | 100,0 % (99,8 %) | 0,0 % | 0,0 % | 53 / 43 / 85 | 3,5 | 0,7 |

### 5.2 Curva operativa (CPC 0,40 USD, 3.000 corridas por punto)

| CPA/BE | 0,40 | 0,50 | 0,60 | 0,70 | 0,85 | 1,00 | 1,15 | 1,30 | 1,50 | 2,00 |
|---|---|---|---|---|---|---|---|---|---|---|
| MATAR | 0,1 % | 0,7 % | 1,9 % | 5,3 % | 15,4 % | 31,1 % | 48,4 % | 63,5 % | 79,5 % | 95,3 % |
| ESCALAR | 98,5 % | 86,9 % | 61,6 % | 35,6 % | 12,4 % | 3,9 % | 1,0 % | 0,4 % | 0,1 % | 0,0 % |
| INCONCLUSO | 1,4 % | 12,5 % | 36,5 % | 59,1 % | 72,2 % | 65,0 % | 50,6 % | 36,1 % | 20,4 % | 4,7 % |
| Gasto medio (USD) | 97 | 129 | 162 | 185 | 198 | 195 | 184 | 171 | 152 | 114 |

### 5.3 Qué garantiza la regla (y qué no)

| Garantía | Resultado medido | Tolerancia en las pruebas (160 corridas) |
|---|---|---|
| Ganador en el objetivo o mejor descartado ≤ 4 % | 0,1 % (0,45 × BE) y 2,1 % (0,6 × BE); 4,0 % con sobredispersión σ = 0,3 | A ≤ 4 %; B ≤ 8 % |
| Perdedor ≥ 1,3 × BE escalado ≤ 0,5 % | 0,4 % (1,3), 0,1 % (1,5), 0,0 % (2) | E ≤ 3 % |
| Ganador fuerte (0,45 × BE) escalado en ≥ 90 % | 96,5 % | ≥ 88 % |
| Perdedor severo muerto barato | 100 %, gasto medio 53 USD = 3,5 × BE | ≥ 97 %; gasto medio ≤ 90 USD |
| Gasto nunca supera el tope | **no es una propiedad por construcción**: la simulación recorta al tope, pero en la realidad solo el `spend_cap` nativo corta (aproximado) y Meta puede gastar hasta 1,75 × el diario un día. Se mide `p99 (gasto − tope)` con `ConfigSim.sobregiro_dia` (B1/I1) y se usa `gasto_efectivo = gasto_leído + 1,75 × diario × (horas_sin_lectura / 24)` para decidir | prueba |
| Sin tope cargado, gasto 0 | BLOQUEADO | prueba |
| Regla ingenua a 10 USD | 33 % de ganadores de CPA 9 y 54 % de CPA 16,2 | simulada ≈ analítica ± 8 pp |

**Estas garantías valen con atribución perfecta y compras el mismo día del clic** (la simulación oficial fija `tracking_sano=True` y `datos_maduros=True`). Simulación propia de la crítica técnica (1.500 corridas por celda, ganador B a 0,6 × BE; resultado externo a este repositorio, a reproducir en I1): con `captura_adid_min_pct = 95` el descartado pasa de 2,7 % a 3,0 %; con 95 % de cobertura **y** 25 % de compras un día tarde, 10 % a los 2 días y 5 % a los 5, sube a **8,0 %** (9,3 % con cobertura 90 %), y el ganador «justo» (0,85 × BE) de 12,8 % a 26,9 %. Correcciones: `compras_corregidas = round(compras_atribuidas × 10000 / cobertura_adid_bp)` del mismo periodo en `decision/entradas.py::evidencia_celda`; `tracking_sano` exige cobertura ≥ mínimo **y** razón Meta/Stripe en rango; `datos_maduros` excluye de la evidencia el gasto y los clics de los últimos `estadistica.dias_madurez_compra` días (propuesta: medir en la primera oferta; mientras tanto 3); `MATAR` con 0 compras exige además media ventana de no decidir (**aplicado** en `decision/reglas.py`). Propuesta al dueño (no aplicada a `parametros.yaml`): `landing.captura_adid_min_pct` rango [97, 100], valor 98. Los escenarios «95 % + retraso» entran a la simulación (`ConfigSim.cobertura`, `retraso`) y la tolerancia de B pasa a «≤ 6 % con 95 % + retraso» o se corrige la regla hasta cumplirla (B1/I1).

**Lo que no garantiza:** resolver lo intermedio. Con el tope de prueba (15 × BE), un ganador en el objetivo se escala solo el 61 % de las veces y el 37 % termina INCONCLUSO; entre 0,7 y 1,0 × BE más de la mitad de los resultados son inconclusos. Eso no es un fallo de la regla sino el costo de la evidencia: no hay forma de separar un CPA 0,85 × BE del equilibrio con 16 compras.

### 5.4 Robustez y sensibilidad

| Variante | Resultado relevante (3.000 corridas) |
|---|---|
| Sobredispersión de la conversión σ = 0,3 por día | A: 0,4 % matar, 94,8 % escalar. B: 4,0 % matar. E: 79,3 % matar, 0,1 % escalar. La regla es robusta |
| Tope de 25 × BE (375 USD) | B: escalar 71,8 % (de 60,9 %), inconcluso 26,1 %. E: matar 86,9 %, inconcluso 13,0 %. Gasto medio B 209 USD |
| `alfa_descarte_tope` = 0,10 | C: matar 9,9 % (de 13,7 %); D: 20,8 %; E: matar 66,1 % e inconcluso 33,7 % (de 20,6 %) |
| Presupuesto de 30 USD diarios | Mismo orden de errores; F gasta 70 USD (de 53) y decide en 2,4 días |

La palanca de más valor es **el tope por celda**: pasar de 15 × a 25 × BE sube la tasa de escalado de ganadores en objetivo en 11 puntos y baja los inconclusos en otros 11, a cambio de ~30 % más de gasto medio en los casos ambiguos. Esa es la información que el dueño necesita para fijar el tope más adelante: el **gasto medio de un perdedor severo** es ~3,5 × BE, el de un perdedor moderado ~10 × BE y el de una oferta en el equilibrio ~13 × BE. Esta nota no recomienda un tope.

---

## 6. Estructura del test

### 6.1 Qué se compara, en este orden

| Variable | Cómo entra | Cuándo se decide |
|---|---|---|
| Oferta × mercado (T3) | celda: 1 campaña, 1 conjunto | primero; decide si hay negocio |
| Ángulo (mensaje) | 2-3 anuncios de ángulos distintos, agrupados | con ≥ 20 compras totales; antes, "exploratorio" |
| Creativo dentro del ángulo ganador | 2-3 variantes (hook, formato) | segunda ronda: REFRESCO o prueba de creativos por API |
| Audiencia | amplia (Advantage+), país y edad como controles | no se testea en el piloto: los intereses son sugerencias con conversiones (04 HC-40/41); se compara después, en D9 |

**Ángulo antes que creativo:** agrupar duplica la muestra por comparación y evita diluir los ~16 clics por anuncio-día. Un anuncio no se compara con otro por CPA hasta tener ≥ 20 compras en la celda; antes se ordena por conversión por clic con intervalos (T2).

### 6.2 ABO frente a CBO, y cuántos conjuntos

- **Por defecto CBO_1AS** (D7): 1 campaña con presupuesto de campaña, 1 conjunto Advantage+, 3-6 anuncios, que junta todos los eventos (04 HC-1: combinar si hay aprendizaje limitado). Costo: el algoritmo concentra gasto en 1-2 anuncios y no es un experimento aleatorizado. Para la **posterior no es problema** (la asignación adaptativa depende solo de datos observados); para comparar anuncios sí: los menos entregados quedan "sin veredicto".
- **ABO solo si** `presupuesto_test ≥ n_celdas × gasto_minimo_por_celda` (`max_celdas`, con el `gasto_recomendado` de 3.2): cada celda extra diluye la muestra (nota 16, H3: 5 conjuntos × 15 USD). Máximo del piloto: 1 conjunto por oferta-mercado; 2 solo en un A/B nativo (7-30 días, una variable, presupuestos iguales; HC-10/11) o en la comparación de mercados (sección 7).
- **Creativos nuevos:** no se agregan al conjunto que aprende (HC-3); prueba de creativos por API (2-7 anuncios, HC-12) o campaña REFRESCO.
- **Duración:** mínimo 7 días (HC-11) salvo muerte por regla; en Q4 (Black Friday 2026-11-27) el CPM sube y el test se lee como "Q4" (nota 16, M1).

### 6.3 Cuándo un test es INCONCLUSO

1. Tope alcanzado sin que la posterior permita matar ni escalar (`tope_sin_veredicto`): causa **justa** (P(CPA ≤ BE) ≥ `p_escala` pero sin margen o sin 15 compras) o **ruidosa**.
2. Tope alcanzado con tracking o datos inmaduros fuera de rango (`tope_con_datos_dudosos`): responsable D5/D7, no la oferta. Tope sin un solo clic (`tope_sin_clics`): falla de entrega.
3. Falla técnica abierta en las etapas 0, 2 o 4 del árbol de embudo de D8: una FALLIDA pasa a INCONCLUSA con responsable de embudo.

El dueño resuelve un INCONCLUSO: extender el tope una vez, rediseñar (mejorar el valor del primer pedido para subir el equilibrio) o cerrar.

---

## 7. Comparación de mercados e idiomas con la misma oferta

**Principio.** Polonia e Italia son hipótesis del dueño y de creadores, no priores: el prior de todos los mercados es el mismo (`conv_central` y fuerza idénticas), no hay mercado "favorito" en el código. La evidencia disponible (nota 16) ni siquiera respalda a Polonia sobre Italia.

**Qué se compara.** No la conversión cruda sino el **margen por clic** `conv × MC_mercado − CPC × (1 + tarifa_meta)`, porque el ticket, el IVA, la comisión y el CPC difieren por mercado. `prob_margen_por_clic_mayor` calcula P(margen_A > margen_B) con semilla. Cada mercado se evalúa además contra su propio equilibrio con T3: un mercado puede ganarle a otro y aun así perder dinero.

**Diseño.** Una celda por mercado: misma oferta, mismos creativos traducidos y revisados, mismo evento de optimización, **presupuestos diarios iguales** y misma ventana de calendario, ABO con un conjunto por mercado (excepción justificada a 6.2), `idioma` y `país` fijos. Se mantiene constante todo lo demás: la traducción es una variable de confusión que no se puede separar de la geografía.

**Costo mínimo.** Clics **por mercado** para distinguir dos conversiones (α = 10 % bilateral, potencia 80 %, `n_dos_proporciones`; costo con CPC 0,51 y 0,56 USD de la nota 16 y +3 % de tarifa de Meta en el segundo):

| Conversión A → B | Relativo | Clics por mercado | Costo de 2 mercados (USD) |
|---|---|---|---|
| 2,0 % → 4,0 % | +100 % | 897 | 975 |
| 3,0 % → 4,5 % | +50 % | 1.981 | 2.153 |
| 2,5 % → 3,75 % | +50 % | 2.393 | 2.601 |
| 2,0 % → 2,5 % | +25 % | 10.876 | 11.820 |

Con 1.000 clics por mercado solo se detecta +82 %; con 2.000, +55 %. **Un piloto de ~150 USD no compara mercados** (nota 16, H3): detecta fallas de proceso.

**Cómo se interpreta una diferencia.** (1) P(margen A > B) ≥ 0,90 y A pasa T3 (P(CPA ≤ BE) ≥ 0,80): A es mejor y rentable; sigue A y B queda como control de la hipótesis. (2) P ≥ 0,90 pero ninguno pasa T3: A "pierde menos", no es negocio; se revisa la oferta (el equilibrio), no se escala. (3) P entre 0,10 y 0,90: empate estadístico; se decide por costo operativo (revisor nativo, IVA, mix de pago) o se amplía una vez. (4) Si el efecto observado cabe dentro del mínimo detectable, no se atribuye al mercado: puede ser traducción, Q4 o azar.

Con más de dos mercados se usa `prob_mejor` (P de ser el mejor) y se corrige por selección: el mejor de varios sobreestima su tasa (nota 16, H3). Una diferencia entre mercados **no se transfiere a otro idioma** sin barrido local (backbone 3.2).

---

## 8. Oferta validada (backbone 5.9)

`evaluar_oferta_validada(pedidos, dias, ahora_utc, ParametrosValidacion, ParametrosDecision)`:

1. **Cohorte madura**: pedidos con `pagado_en ≤ ahora − (garantía + margen)` (14 + 7 = 21 días) y el gasto y los clics de los días hasta esa fecha de corte. Solo pedidos atribuidos a un anuncio (`adid`); los demás no cuentan.
2. **Neta**: compra neta = pagada y no reembolsada por completo. Contribución = bruto − IVA − comisión real (no se devuelve) − reembolso neto de IVA − disputa perdida − costo variable. **CPA neto** = gasto ÷ compras netas. **CPA de equilibrio real** = contribución ÷ compras netas (reemplaza el de D3); **CPA objetivo real** = f × ese valor. Equivale a ROAS neto ≥ 1/f.
3. **VALIDADA** si la cohorte madura cumple: compras netas ≥ `n_val` (15), compras en ≥ 3 días, ningún día con más de 50 %, reembolsos ≤ 8 %, P(CPA ≤ equilibrio real) ≥ 0,80 y CPA neto ≤ objetivo real.
4. **PROVISIONAL**: la vista con cohortes inmaduras (a las que se les aplica el reembolso esperado, `max(observado, r × neto)`) cumple, pero la madura aún no tiene `n_val` compras. Se permite escalar solo un paso pequeño; no es VALIDADA.
5. **PROMETEDORA**: cumple todo salvo CPA entre el objetivo y el equilibrio reales. **FALLIDA**: gasto ≥ `k_min_fallida` × equilibrio y P(CPA ≤ equilibrio real) ≤ 0,05. **INCONCLUSA**: el resto.

El orden temporal importa: una compra del día *t* madura en *t* + garantía + `madurez_dias_extra`; con compras repartidas en una ventana de 7 a 14 días, la última madura **entre el día 28 y el 35** desde la activación (el día 21 es solo la madurez de la compra del día 0), mientras que D8 pide validar en ≤ 14 días. El veredicto `VALIDADA` no puede emitirse antes de `fecha_ultimo_pedido_considerado + politica_reembolso_dias + veredicto.madurez_dias_extra` (estado `espera_madurez`, docs/06 D-22). `VALIDADA` exige además un **segundo corte confirmatorio**: P ≥ 0,80 recalculada en la cohorte madura sobre los días *posteriores* a la decisión de escalar (replicación) o, con ≥ 3 ofertas probadas, `p_validada = 1 − 0,2 / n_ofertas_probadas` (L8). Las disputas abiertas y los EFW se restan como si estuvieran perdidas (`PedidoStripe.disputa_abierta_minor`, aplicado) y `VALIDADA` exige `disputas_abiertas == 0` o ratio < `ratio_disputas_pausa` (B1, `decision/entradas.py`). Un `FALLIDA` decidido con la vista provisional no es final: `fallida → en_construccion` admite reapertura firmada (gate H, `accion:reabrir_fallida`); pendiente de decisión: exigir madurez del gasto para `falla_dura(v_pro)`. Por eso existe PROVISIONAL (sección 9, pedido 3). Los pedidos de otra moneda no se mezclan: F1 convierte antes.

---

## 9. Limitaciones y pedidos a otros componentes

### 9.1 Limitaciones (sin maquillar)

- **L1. Compras tardías.** El modelo trata cada clic como si convirtiera o no al instante; un retraso de días entre clic y compra hace que el test mate de más. Solo lo mitigan el piso de gasto y la ventana de 72 h.
- **L2. Conversión constante.** Se prueba sobredispersión diaria (σ = 0,3), no deriva, estacionalidad (Q4) ni fatiga del creativo; el CPM de noviembre-diciembre es una incógnita (nota 16, M1).
- **L3. Equilibrio fijo.** `CPA_BE` supone el bump, el mix de pago y los reembolsos de D3; la varianza del ingreso por pedido no entra a la posterior (D8 reemplaza el equilibrio con ≥ 10 compras).
- **L4. Prior de D3** `[HIPÓTESIS]`: la fuerza de 50 clics limita el daño, no lo elimina.
- **L5. Un conjunto no es un experimento.** En CBO_1AS el reparto del algoritmo no es aleatorio; comparar anuncios es observacional.
- **L6. Simulación de una celda** con economía y tope de prueba; no modela el reparto entre celdas.
- **L7. Atribución.** Supone que la compra de Stripe lleva el `adid` correcto (cobertura ≥ 90 %); si no, el modo ciego de D8 bloquea. Con cobertura < 100 % y compras tardías la regla mata más ganadores (ver 5.3): corregir las compras por cobertura.
- **L8. Comparaciones múltiples.** Entre muchas ofertas o mercados probados, algún "ganador" aparece por azar; el nivel 4 de la nota 16 sigue vigente.
- **L9.** El control de falsos descartes tarda cientos de casos en informar: al principio es una promesa de medición.

### 9.2 Pedidos a otros componentes (no se editaron sus archivos)

1. **D8:** adoptar los nombres `estadistica.*` y retirar duplicados (`p_kill`, `p_fallida`, `k_corte`). D8 usa Gamma-Poisson sobre compras y gasto; este protocolo usa Beta-Binomial sobre clics, que aprovecha los clics y separa el CPC. `p_kill` 0,90 (K3) frente a `alfa_descarte` 0,05.
2. **D3 (`economia.json`):** añadir `conv_central`, `cpc_esperado_minor`, `cpa_equilibrio_visto_minor` (sin la tarifa de Meta que ve Ads Manager) y `tarifa_meta_pct`; el equilibrio debe incluir Stripe Tax y la tarifa de disputa con la fórmula de 3.1.
3. **D8, veredicto:** añadir `PROVISIONAL` (o mapearlo a PROMETEDORA con marca `cohorte_inmadura`): "validar en ≤ 14 días" choca con garantía + 7. **Resuelto (docs/06 D-11):** `PROVISIONAL` = `PROMETEDORA` con `evidencia.cohorte_madura_hasta` anterior al corte; la oferta sigue `en_test`; `VALIDADA` solo con cohorte madura.
4. **F1:** `ventana_madurez_dias = reembolso_dias + 14` contradice el backbone 5.9 (garantía + 7); decidir cuál rige.
5. **Backbone 5.6 / `limites.yaml`:** no existe un tope por celda (anuncio, ángulo, mercado); hace falta `tope_gasto_celda` o una regla que lo derive de `perdida_max_test_por_oferta`. Sin él, `evaluar_celda` devuelve BLOQUEADO. **Resuelto (docs/06 D-12):** sin clave nueva; tope de la celda `oferta_mercado` = mínimo entre `economia.gasto_test_plan`, `limites.gasto_total_test_por_oferta` y `limites.perdida_max_test_por_oferta`; los anuncios no llevan tope propio.
6. **D7:** documentar que CBO_1AS impide forzar gasto a un anuncio y que la comparación de mercados usa ABO con presupuestos iguales.
7. **`parametros.yaml`** está protegido: el bloque de la sección 10 es una **propuesta** para el script de X2 con aprobación del dueño. Los límites de Meta (1,75 ×, ≤ 4 cambios por hora, 30 s) y de paso y espera (+20 %, 72 h) viven en `limites.yaml`.
8. **Datos:** medir desde la primera oferta el retraso clic→compra (L1): es la calibración que más mueve el costo de decidir. **Resuelto (docs/06 D-24):** campo obligatorio `retraso_clic_compra` del post-mortem.

---

## 10. Parámetros iniciales para `empresa/parametros.yaml`

Todos `[HIPÓTESIS]` salvo `hipotesis: false`. Una prueba (`tests/decision/test_reglas.py`) verifica que las nueve primeras coinciden con el espejo de `decision/simulacion.py` y que cada entrada trae `unidad`, `hipotesis`, `fuente` y `ultima_calibracion`. El prior de conversión y el CPC esperado vienen de `economia.json` de cada oferta.

```yaml
parametros:
  estadistica.prior_conv_fuerza_clics: {valor: 50, unidad: clics, hipotesis: true, fuente: "08 §2", ultima_calibracion: null}
  estadistica.prior_cpc_fuerza_clics: {valor: 20, unidad: clics, hipotesis: true, fuente: "08 §2", ultima_calibracion: null}
  estadistica.alfa_descarte: {valor: 0.05, unidad: probabilidad, hipotesis: true, fuente: "08 §4.2, §5", ultima_calibracion: null}
  estadistica.alfa_descarte_tope: {valor: 0.20, unidad: probabilidad, hipotesis: true, fuente: "D8 p_cierre_tope", ultima_calibracion: null}
  estadistica.p_escala: {valor: 0.80, unidad: probabilidad, hipotesis: true, fuente: "D8 p_escala", ultima_calibracion: null}
  estadistica.k_min_matar: {valor: 2.0, unidad: x_cpa_equilibrio, hipotesis: true, fuente: "08 §2; D3 k=3", ultima_calibracion: null}
  estadistica.n_min_escala: {valor: 15, unidad: compras, hipotesis: true, fuente: "D3 N_dec", ultima_calibracion: null}
  estadistica.ventana_no_decidir_h: {valor: 72, unidad: horas, hipotesis: true, fuente: "04 §9.2, HC-3", ultima_calibracion: null}
  estadistica.nodos_cpc: {valor: 5, unidad: puntos, hipotesis: true, fuente: "08 §2", ultima_calibracion: null}
  estadistica.potencia: {valor: 0.80, unidad: probabilidad, hipotesis: true, fuente: "08 §3.2", ultima_calibracion: null}
  estadistica.precision_relativa: {valor: 0.25, unidad: fraccion, hipotesis: true, fuente: "16 §3", ultima_calibracion: null}
  estadistica.confianza_precision: {valor: 0.95, unidad: probabilidad, hipotesis: true, fuente: "16 §3", ultima_calibracion: null}
  estadistica.dias_test_min: {valor: 7, unidad: dias, hipotesis: false, fuente: "04 HC-11", ultima_calibracion: null}
  estadistica.meta_eventos_aprendizaje_semana: {valor: 50, unidad: eventos, hipotesis: false, fuente: "04 HC-1", ultima_calibracion: null}
  estadistica.meta_fraccion_min_purchase: {valor: 0.5, unidad: fraccion, hipotesis: true, fuente: "D7 §3.2", ultima_calibracion: null}
  estadistica.control_fraccion: {valor: 0.15, unidad: fraccion, hipotesis: true, fuente: "08 §4.5 (0,10-0,20)", ultima_calibracion: null}
  estadistica.control_fraccion_presupuesto: {valor: 0.25, unidad: fraccion, hipotesis: true, fuente: "08 §4.5", ultima_calibracion: null}
  estadistica.control_gasto_max_k: {valor: 2.0, unidad: x_cpa_equilibrio, hipotesis: true, fuente: "08 §4.5", ultima_calibracion: null}
  estadistica.mercados_alfa: {valor: 0.10, unidad: probabilidad, hipotesis: true, fuente: "08 §7", ultima_calibracion: null}
  estadistica.mercados_p_diferencia: {valor: 0.90, unidad: probabilidad, hipotesis: true, fuente: "08 §7", ultima_calibracion: null}
  estadistica.validacion_garantia_dias: {valor: 14, unidad: dias, hipotesis: true, fuente: "05 §2", ultima_calibracion: null}
  estadistica.validacion_margen_madurez_dias: {valor: 7, unidad: dias, hipotesis: false, fuente: "backbone 5.9; F1 usa +14", ultima_calibracion: null}
  estadistica.validacion_n_val: {valor: 15, unidad: compras_netas, hipotesis: true, fuente: "D8 N_val", ultima_calibracion: null}
  estadistica.validacion_dias_con_compras_min: {valor: 3, unidad: dias, hipotesis: true, fuente: "D8 veredicto", ultima_calibracion: null}
  estadistica.validacion_max_dia_pct: {valor: 0.50, unidad: fraccion, hipotesis: true, fuente: "D8 max_dia_pct", ultima_calibracion: null}
  estadistica.validacion_reembolso_max: {valor: 0.08, unidad: fraccion, hipotesis: true, fuente: "D8 reembolso_max", ultima_calibracion: null}
  estadistica.validacion_p_validada: {valor: 0.80, unidad: probabilidad, hipotesis: true, fuente: "D8 p_escala", ultima_calibracion: null}
  estadistica.validacion_p_fallida: {valor: 0.95, unidad: probabilidad, hipotesis: true, fuente: "D8 p_fallida", ultima_calibracion: null}
  estadistica.validacion_k_min_fallida: {valor: 5.0, unidad: x_cpa_equilibrio, hipotesis: true, fuente: "D8 FALLIDA", ultima_calibracion: null}
  estadistica.validacion_tasa_reembolso_esperada: {valor: 0.07, unidad: fraccion, hipotesis: true, fuente: "D3 r=7 %", ultima_calibracion: null}
```
