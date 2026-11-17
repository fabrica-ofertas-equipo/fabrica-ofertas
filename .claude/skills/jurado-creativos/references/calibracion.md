# Calibración contra lo cobrado

Cómo se sabe si el jurado acierta, cuándo se apaga y cuándo puede ganar peso. Código: `scripts/jurado/calibrar.py` + `scripts/jurado/estadistica.py`. Hoy corre con fixtures (`--fixture`): **no hay etiquetas reales**, y por eso el estado de cualquier jurado es `acumulando`.

## 1. Qué dice JPS y qué no

«A los 3 días, la verdad»: cada voto se cruza con lo cobrado `[P 36:13]`; el anuncio vuelve con **«inversión, vistas, gancho, clics, ventas»**, no solo ventas `[V 14:00]` (H-10); el miércoles «el jurado se recalibra con lo cobrado → jueces más finos» y «el que acierta pesa más» `[P 47:43]`. **No dice** cómo se calcula «acierta», qué se pondera, ni cuánto acierta hoy. Sus cifras son `[DECL]`. Todo lo de abajo es nuestro y `[SUPUESTO]` hasta que haya datos.

## 2. Unidad de análisis

Una **etiqueta** = una pieza (un anuncio) leída a una madurez dada. El jurado predice con `score` (`share_si` + desempate) **antes** del resultado; `jurado.json` queda sellado (`sello`, `sellado_en`). Un jurado cuyo sello no coincide, o cuya predicción es posterior a la lectura del resultado, **no entra**. 150 etiquetas son 150 anuncios (15 tandas de 10), no 150 votos: 10 avatares × 15 piezas no son 150 observaciones.

## 3. Madurez de la etiqueta

A 3 días y ~15 USD, las ventas son ruido (P(0 ventas) = e^(−G/c); `analisis/creativos-jurado.md` P3-06). Se calibra primero con lo abundante y solo el último nivel puede decir «predice ventas». Todas las etiquetas, salvo `ventas`, son **relativas a la tanda**: positivo = estrictamente por encima de la mediana de su tanda (quita el efecto del día y del presupuesto; una tanda sin contraste se descarta).

| Nivel | Positivo si… | Mínimo de exposición `[SUPUESTO]` | Qué mide |
|---|---|---|---|
| `inversion` | gasto de la pieza > mediana de la tanda | — | a quién le da presupuesto Meta (señal temprana, indirecta) |
| `gancho` | vistas de 3 s / impresiones > mediana | `min_impresiones` 1000 | si frena el dedo |
| `clics` | clics en el enlace / impresiones > mediana | `min_impresiones` 1000 | si provoca el clic (**la pregunta que hace el voto**) |
| `pago_iniciado` | pagos iniciados / clics > mediana | `min_clics` 50 | intención más profunda |
| `ventas` | compras netas ≥ `min_compras_positivo` (1) | `gasto_min_ventas`: **sale de `economia.json` (CPA máximo)**; sin él NO se etiqueta | si vende |

El nivel **principal** es el más maduro con ≥ `n_min_etiquetas`. Si ninguno llega, el estado es `acumulando`. Hasta que `ventas` tenga etiquetas, `calibracion.json` dice por escrito «**predice ventas NO está demostrado**».

Tamaño de muestra (Anexo B4 del análisis, potencia 80 %, α 5 %): para detectar AUC 0,65 hacen falta ≈ 143 anuncios si el 20 % es positivo, ≈ 254 si el 10 %, ≈ 787 si el 3 %. Las etiquetas relativas valen ~50 % de positivos (por construcción); `ventas` con ~3 % de acierto no se alcanza en meses. A 5-10 piezas por día, 150 etiquetas de `clics` son 15-30 días de tandas leídas.

## 4. Qué se mide

- **AUC** (probabilidad de que una pieza positiva puntúe más que una negativa; 0,5 = azar, 1 = perfecto, < 0,5 = invertido), con empates a medias, **IC95 de DeLong** y **p-valor contra el azar por permutación** (semilla reproducible).
- **Brier** del `share_si` leído como probabilidad (0 = perfecto) frente a la **línea base de prevalencia** (predecir siempre la tasa de positivos) y su `brier_skill = 1 − brier/brier_prevalencia`. El 0,25 de «50/50» solo es la vara con prevalencia 50 %. El `share_si` no es una probabilidad calibrada: un Brier malo con AUC bueno solo dice que hay que recalibrar la escala; el AUC ordena.
- **Comparaciones sobre las MISMAS piezas** (`baselines`): `azar` (0,5), `todos_aprueban` (puntaje constante, 0,5), **`rubrica_unica`** (el juez sin perfil `av-<locale>-rubrica`, gancho/claridad/CTA: la rúbrica R1-R3 del QA aplicada pieza a pieza) con **DeLong pareado**, y las que se pasen con `--baseline NOMBRE=archivo.jsonl` (p. ej. `virality`). Pregunta de fondo: ¿10 perfiles aportan algo sobre un único evaluador?

## 5. Estados y regla de apagado

| Estado | Condición (sobre el nivel principal) | Qué pasa |
|---|---|---|
| `acumulando` | < `n_min_etiquetas` (150) `[SUPUESTO]` | sigue en sombra; **no se juzga** (medir el acierto con menos es medir ruido) |
| **`apagar`** | ≥ 150 y (AUC ≤ 0,5 **o** el extremo superior del IC95 < `auc_min` 0,60) | **se apaga solo**: `paquetes.py armar` se niega (deja de gastar tokens) salvo `--reactivado-por` del dueño |
| `sombra` | supera al azar pero no cumple todo lo de abajo | sigue prediciendo sin decidir |
| `elegible_asesor` | AUC ≥ 0,60 **y** IC95 por encima del azar **y** p contra el azar < 0,05 **y** supera a la rúbrica (diferencia de AUC > 0, DeLong pareado p < 0,05, con ≥ 150 piezas puntuadas por ambos) **y** anclas OK **y** nivel principal ≥ `clics` | el dueño **puede** firmar la promoción |

«No supera al azar» se decide con el intervalo y no solo con el punto: un jurado con AUC 0,52 y 150 etiquetas (IC ≈ 0,43-0,61) sigue en sombra; con 1000 etiquetas (IC ≈ 0,48-0,56) se apaga. **Anclas OK** = en ≥ `anclas_min_pct` (60 %) de las tandas con ambas anclas la ganadora saca ≥ 0,2 más de «sí» que la perdedora, **y** al menos una tanda tuvo un ancla `medida`. Todos los números son `[SUPUESTO]`; el de azar (0,5) es definición.

## 6. Pesos: iguales

JPS: «el que acierta pesa más (por mercado)». Con ~35 piezas por semana por idioma y pocos positivos reales, ponderar 25 mercados × 10 jurados es ajustar ruido (Anexo B4). En v0.1 **todos pesan igual**; `calibrar.py` solo informa por avatar (`por_avatar`: AUC propio con IC, AUC del jurado con y sin él, mejora en cada mitad de las etiquetas). Una ponderación futura exige validación cruzada y una PC aprobada (BB:150); no existe en el código.

## 7. Recalibración del miércoles y reemplazo de avatares

1. Recoger las lecturas de métricas por anuncio (`metricas.jsonl`: gasto, impresiones, clics del enlace, vistas de 3 s, pagos iniciados, compras, `fecha_lectura`; productor pendiente de S-B: `PEDIDOS.md`).
2. `calibrar.py --jurados <todas las tandas del mismo mercado> --metricas … --salida empresa/jurado/calibracion/AAAA-Sww.json --fusionar-en <último jurado.json>` (la calibración se acumula entre ofertas del mismo `locale`; las estadísticas por avatar solo son comparables dentro de una oferta). Fusionar copia `precision` al `jurado.json` para la pantalla sin romper el sello.
3. `jurado-qa` revisa la calibración (L3-d).
4. **Reemplazo**: las `propuestas_reemplazo` las puede aplicar `avatares.py reemplazar --calibracion …` (queda en el registro). Criterios: ≥ 150 etiquetas del avatar; camino 1 = quitarlo sube el AUC del jurado ≥ δ (0,01) **en las dos mitades** de las etiquetas y él acierta menos que el jurado; camino 2 = su AUC propio tiene el IC95 entero bajo el azar y quitarlo no empeora al jurado en ninguna mitad. Nunca se reemplaza «porque el pasado no coincide» sin que pase esa prueba.
5. Si el estado es `apagar`: apagar y avisar al dueño. Si es `elegible_asesor`: avisar al dueño (puede firmar o no).

## 8. Qué NO demuestra esta calibración

- Que «el jurado compra como un cliente»: mide si **ordena** lo que el mercado después premia, a la madurez que haya.
- Que acierte en otro mercado, otro nicho u otro tipo de pieza (video está fuera).
- Causalidad: los anuncios que entran al test son los que el jurado ordenó primero si algún día ordena (sesgo de selección); mientras esté en sombra no hay ese sesgo, y por eso se empieza en sombra.
- Independencia: las piezas de una misma tanda comparten día y presupuesto (las etiquetas relativas lo mitigan, no lo eliminan).
- Corrección por comparaciones múltiples: se miran 5 niveles y varios avatares; la regla de apagado no depende de un p-valor suelto, pero la de promoción sí usa p < 0,05: es `[SUPUESTO]` y conviene endurecerla cuando haya más niveles con datos.
