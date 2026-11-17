# Estadística honesta: por qué solo 1 de 3 subas acierta, por qué existe el auditor y por qué se gradúa por etapas

> v0.1 sin pulir (skill 0.1.0). Fuentes: JPS (`know-how.md` §4.2, §5 y §9; brechas A.3, A.4, H-01, H-12), `docs/08-protocolo-estadistico-del-testeo.md` (§4.3 a §4.5), `mapeo.md` §3 y §11. Etiquetas: `[P]` pantalla · `[V]` voz · `[DECL]` cifra declarada sin verificar · `[cálculo nuestro]` aritmética reproducible (modelo de Poisson, sin sobredispersión) · `[HIPÓTESIS]` valor inicial. Ninguna cifra de JPS se usa como prior ni como umbral (`mapeo.md` §6).

## 1. Principio

La IA no sabe si una oferta «es buena»: sabe qué dijo un día de datos. «No sé» no es «malo». Esta skill nunca afirma con 2 compras (rúbrica R2), nunca presenta una baja de lanzamiento como un veredicto sobre la oferta y marca toda causa sin prueba como `[HIPÓTESIS]`.

## 2. Lo que JPS dice haber medido (y lo poco que eso prueba)

- Su auditor `[P][DECL]`: **3 de cada 4 cortes de gasto aciertan; 1 de cada 3 subas de gasto acierta**, «por eso las subas ahora piden más pruebas».
- **No dice cuántas decisiones** hay detrás. Si fueran literalmente 3 de 4 y 1 de 3, los intervalos exactos de Clopper-Pearson al 95 % serían: cortes 19 %-99 %, subas 1 %-91 % `[cálculo nuestro]`: no distinguen nada. Se toman como **señal de cautela** (subir es más arriesgado que cortar), no como medición. Nuestra propia tasa saldrá de **nuestro** auditor (`decisiones.jsonl` + resultado posterior, B2-24).

## 3. Por qué una suba falla más que un corte

1. **Regresión a la media y maldición del ganador.** Se sube lo que mejor se ve; con pocas ventas, el «mejor de varios» sobreestima su tasa real. Es el mismo sesgo que `docs/08` §4.3 atenúa con prior y mínimos de compras, pero no elimina.
2. **El presupuesto no escala el resultado.** Duplicar el presupuesto cambia la subasta, la audiencia alcanzada y el aprendizaje de Meta; el CPA de ayer no es el de mañana. Un corte no cambia nada de lo que se midió.
3. **Medición atrasada.** El píxel puede tardar hasta 4 h en registrar una venta `[V 17:30]`; el clic→compra tiene su propio retraso. Subir sobre datos incompletos premia o castiga a ciegas. Su regla vieja de duplicar cada hora «cumplía los parámetros pero no aprendía»: no distinguía si Meta ya había gastado ese presupuesto o solo se le había dado más (brechas H-01).
4. **Asimetría del costo.** Un corte pierde lo ya gastado; una suba compromete más dinero encima de una estimación frágil.
5. **Base rate bajo.** 3 de cada 100 creativos lanzados son ganadores de verdad `[V][DECL]`: la mayoría de lo que parece prometedor no lo es.

Consecuencias de diseño: (a) las subas son **de código, con pasos y topes** (D9) y no se proponen desde un día de datos; (b) cada suba la **califica un auditor** con lo que pasó 72-96 h después y se degrada el nivel de quien falla (B2-24, B2-25); (c) la **graduación es por etapas**.

## 4. Graduación por etapas

Ninguna etapa se salta, y cada una pide la **tendencia de 3 días** (regla de oro 3 `[P 43:58]`: «un día sin ventas no dice nada»), salvo la de lanzamiento, donde el dueño eligió 1 día (J3).

| Etapa | Qué se afirma | Criterio (propuesto) | Quién lo calcula | Estado del criterio |
|---|---|---|---|---|
| 0 · Vive | el paquete vendió al menos una vez en el día 1 | ≥ 1 venta pagada, o entrega incompleta (no se juzga) | `proponer.py lanzamiento` | J3 (+ `[SUPUESTO]`) |
| 1 · Rentable en testeo | probablemente gana dinero y **se queda en testeo** | P(CPA ≤ BE) ≥ 0,80 con ≥ 15 compras (`testeo.p_escala`, `n_dec`); JPS: «CPA 15-18 con un producto de 27 es rentable y se queda» | `engine/d8.py` | spec vieja `HIP`; el dueño decide cuál rige (B2-06) |
| 2 · Campeón | candidato a escala (**GRADUAR**): sigue vivo en el testeo (regla de oro 2) | ≥ 10 compras netas y CPA ≤ 0,40 × BE `[HIPÓTESIS]`; JPS: «≥ 10 ventas a CPA 6-7» `[V][DECL]` | `engine/d8.py` + criterio firmado | **sin firma**: `CRITERIO_CAMPEON_SIN_FIRMA` |
| 3 · Escala ×2 | se agranda el presupuesto | paso ×2 dentro de J4; ×3 y ×5 solo si el auditor mide acierto | D9 / robot de escalera | fuera de D8 |
| 4 · VALIDADA | la oferta se considera validada (portafolio) | cohorte madura (garantía + 7 días), P ≥ 0,80, sin disputas, segundo corte | `evaluar_oferta_validada` | choca con el ritmo de J1 (`conflictos-con-la-spec-vieja.md` C-07) |

## 5. Falsos descartes del día 1 (lo que la regla J3 acepta perder)

Si el CPA real de una oferta es `c` y la campaña gasta `G` sin ventas, la probabilidad de **cero ventas por azar** es `e^(−G/c)` (Poisson `[cálculo nuestro]`, la misma fórmula de `docs/08` §4.3). Tabla, en % de ofertas **buenas** que la regla apagaría por azar:

| Gasto del día | CPA real 10 | 14 | 17 | 27 | 40 |
|---|---|---|---|---|---|
| 50 USD | 0,7 % | 2,8 % | 5,3 % | 15,7 % | 28,7 % |
| 75 USD | 0,1 % | 0,5 % | 1,2 % | 6,2 % | 15,3 % |
| 100 USD | 0,0 % | 0,1 % | 0,3 % | 2,5 % | 8,2 % |

Lectura honesta:

- Con 75 USD, una oferta con CPA de 14 casi nunca se pierde (0,5 %); una con CPA de 27 se pierde 1 de cada 16; una de 40, 1 de cada 7. **J3 deja pasar a las ofertas con margen amplio y es injusta con las ajustadas.** Eso es lo que el dueño aceptó («la pérdida queda acotada por la regla»); la tabla le dice a cuánto cuesta.
- Es un **piso**: el modelo supone entrega estable y ventas independientes. El riesgo real es **entrega y varianza** (aprendizaje limitado de Meta: ~50 eventos por semana, `docs/08` §4.6; ~10 creativos que se reparten el gasto), que aumentan los ceros respecto de Poisson. Por eso existe la salvaguarda de presupuesto gastado.
- Se separa **cero ventas** de **cero por falla técnica** (conexión de landing, tracking, pago): estas últimas no son azar y la regla no las baja (`protocolo-j3.md` filas 14-15).
- Un CPA igual al precio del frontal (17 USD) ya pierde dinero: la tabla no dice «cuándo apagar» sino cuántas ofertas rentables se apagan; la rentabilidad la fija el punto de equilibrio de `economia.json` (J16: la factibilidad debe entregar el **CPA máximo** como umbral).

### Medir los falsos descartes (control de lo apagado)

`decision.reglas.plan_grupo_control` y `estimar_falsos_descartes` existen y están probadas, pero no están cableadas a la baja J3 (B2-14). Reabrir una fracción de lo apagado (`control_fraccion` 0,15; 25 % del presupuesto previo; gasto máximo `control_gasto_max_k` = 2 × CPA_BE) permite estimar la tasa. **Cuesta:** detectar una tasa de 10 % frente a 5 % pide ~150 controles; 15 % frente a 5 %, ~44 (`docs/08` §4.5). Con un CPA_BE ilustrativo de 17 USD (`[SUPUESTO]`: cota alta, el precio del frontal J16), el gasto máximo por control es ~34 USD: **150 controles ≈ 5.100 USD y 44 ≈ 1.500 USD** `[cálculo nuestro]`, comparados con la pausa de J4 a -3.000 USD. Por eso el control es una **decisión del dueño** (U-60), y mientras no se active la tasa solo se conoce por el modelo de arriba y por los pocos casos en que una oferta apagada vuelve a lanzarse.

## 6. Qué nunca se concluye

- Que una oferta «no funciona» por un día de datos, ni que un ángulo «no sirve» por una baja de lanzamiento (el paquete completo falló; no se sabe cuál de sus partes).
- Diferencias entre mercados o idiomas sin barrido local (`docs/08` §7; un piloto de ~150 USD no compara mercados).
- Causa a partir de correlación: el expediente separa `correlacion` de `causa` y pone `nivel_evidencia` (bajo/medio/alto) en cada explicación.
- Ninguna cifra de JPS (3 de 100, 1,83 de retorno por dólar, 10 ventas a CPA 6-7) como umbral: son `[DECL]`, sobre productos y mercados que no son los nuestros.
