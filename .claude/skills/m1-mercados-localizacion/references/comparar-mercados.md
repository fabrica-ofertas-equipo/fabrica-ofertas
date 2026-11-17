# Cómo comparar mercados con la misma oferta y presupuestos iguales — y qué decide qué con datos propios

> Fuente: `docs/08-protocolo-estadistico-del-testeo.md` §3.2-§3.5 y §7; `departamentos/16` §3.4 y §4.1; `docs/_investigacion/16` H3 y M1. Principio del dueño (2026-11-06): **ningún mercado es un prior**; el prior de todos es el mismo (`conv_central` y fuerza idénticas): no hay mercado «favorito» en el código. El ajuste de creadores no pesa en la decisión final.

## 1. Qué M1 decide y qué NO
| Decisión | Quién | Con qué |
|---|---|---|
| **Qué mercado probar primero** (hipótesis de arranque) | M1 propone con puntaje determinista + sensibilidad; **el dueño firma** (gate H en el primer lanzamiento de un país o idioma) | modelo de `rank.py`/`puntaje.py` con confianza C, **más** las decisiones del dueño que cambian el resultado (Managed Payments, métodos locales, `mercados_test_paralelos_max`) |
| **Si ESA oferta funciona en ESE mercado** (T3 contra su equilibrio) | D8 (reglas deterministas) | clics, compras y CPA netos de Stripe de la celda oferta × mercado |
| **Si un mercado es mejor que otro** | protocolo de `docs/08` §7 sobre datos propios | margen por clic `conv × MC_mercado − CPC·(1+f_meta)` con presupuestos iguales y ≥ clics por brazo |
| **Cambiar `estado_decision` a `decidido_con_datos_propios`** | solo con datos propios suficientes (abajo) y gate H | `evidencia_propia{clics_enlace, compras_stripe, ofertas_probadas}` |
| Recalibrar pesos del puntaje | M1 con ≥ 8 pares mercado-oferta con resultado | puntaje vs. RPC/CPC observado; hasta entonces pesos fijos |

## 2. Diseño de la comparación (docs/08 §7)
- **Una celda por mercado**: misma oferta, mismos creativos traducidos y revisados, mismo evento de optimización, **presupuestos diarios iguales**, misma ventana de calendario, ABO con un conjunto por mercado (excepción justificada a 6.2); `idioma` y `país` fijos.
- Se mantiene constante todo lo demás: la **traducción es una variable de confusión** que no se separa de la geografía. Una diferencia entre mercados **no se transfiere a otro idioma** sin barrido local (backbone 3.2).
- Con `mercados_test_paralelos_max = 1` **no se puede comparar**: solo se prueba un mercado y se decide T3. Comparar exige subir ese parámetro (decisión del dueño, rango 1-3). **No lo supongas**; si el dueño quiere comparar, la salida lleva `pendientes_dueno: ["mercados_test_paralelos_max ≥ 2"]` y el presupuesto de K mercados.

## 3. Cuánto cuesta decidir (el número que más engaña)
- Estimar una conversión central con ±25 % relativo (IC 95 %) cuesta ~`clics_min_decidir_mercado` clics **por mercado** (`parametros.yaml#mercados.clics_min_decidir_mercado`, `[HIPÓTESIS]`).
- Distinguir dos conversiones cuesta clics **por brazo** (`n_dos_proporciones`, α bilateral `estadistica.mercados_alfa`, potencia 80 %): para +50 % relativo sobre una base de 2,5 % son del orden de `clics_min_decidir_mercado` clics por brazo (tabla de docs/08 §7); con ~1.000 clics por mercado solo se detecta una diferencia muy grande (docs/08 §7: +82 %).
- **Un piloto de ~60-75 USD por país en 72 h NO compara mercados** (16 H3): con ~240 clics y 5 compras el IC 95 % de la conversión es 0,7-4,8 %; con 5 conjuntos de 15 USD aparece al menos una venta en ~91 % de los casos aunque la conversión real sea un tercio del equilibrio. Sirve para detectar **fallas de proceso** (checkout, BLIK, entrega, CMP, rechazos). Por debajo de `clics_min_decidir_mercado` la salida se etiqueta **señal de proceso** y `estado_decision` NO cambia (MQ-19; sembrado D15).
- El **efecto observado que cabe dentro del mínimo detectable no se atribuye al mercado**: puede ser traducción, Q4 (Black Friday 2026-11-27) o azar. Leer la ventana como «Q4», no compararla con enero.

## 4. Cómo se interpreta una diferencia (docs/08 §7)
1. `P(margen A > B) ≥ estadistica.mercados_p_diferencia` y A pasa T3 ⇒ A es mejor y rentable; sigue A y B queda como control de la hipótesis.
2. Ese umbral pero ninguno pasa T3 ⇒ A «pierde menos»: no es negocio; se revisa la oferta (el equilibrio), no se escala.
3. P intermedia ⇒ empate estadístico: se decide por costo operativo (revisor nativo, IVA, mezcla de pago) o se amplía **una vez**.
4. Con más de dos mercados se corrige por selección (el mejor de varios sobreestima su tasa): `prob_mejor`.
**Poda**: tras 100-300 conversiones se conservan los países con ingreso por clic ≥ CPC (RPC/CPC, 08 §6).

## 5. Qué dato propio reemplaza a qué supuesto (recalibración, `08` §6)
| Supuesto del atlas | Dato propio que lo reemplaza | Cuándo |
|---|---|---|
| CPM de referencia (C, julio) | CPM propio por país (mezcla ponderada con el benchmark) | ≥ 1.000 clics o ≥ 100 USD de gasto |
| Cobertura de pago estimada | mezcla real de métodos del panel de Stripe | ~50 compras por país |
| Cuota de BLIK u otro método local | % de compras por método y abandono por método | tras la habilitación |
| Comisión modelada | `balance_transaction.fee` real | primeras transacciones (desvío > 0,5 pp = corregir) |
| Ajuste de creadores | resultado propio con ≥ 100 clics por celda | deja de contar (ya pesa 0) |
| Puntaje mínimo y CAC relativo | ≥ 8 pares mercado-oferta con resultado | recalibrar pesos |
| Hipótesis de brecha del barrido (presencia/hueco por país) | pasada 3 del barrido (page_ids × país) y evidencia local E1-E4 | antes de pasar a D2 |

## 6. Preguntas de criterio al leer una selección
«¿Qué dato barato movería más el resultado?» (casi siempre: la mezcla real de pagos del país, o el CPM propio). «¿Qué decisión del dueño mueve más el puntaje?» (Managed Payments × métodos locales). «¿El elegido sigue en el top 3 en todos los escenarios de sensibilidad?» «¿La diferencia entre el 1.º y el 2.º es mayor que `empate_puntos`?» Si no, es un empate y **el piloto es la única forma de decidir**.
