# scripts/mercados — ranking reproducible de mercados

Reproduce y corrige el ranking de `docs/_investigacion/08-mercados-ranking.md` (informe: `docs/_investigacion/08b-ranking-reproducible-y-corregido.md`). Solo biblioteca estándar de Python; sin red.

## Archivos
| Ruta | Qué es |
|---|---|
| `rank.py` | Motor: puntajes de 08 §2.1, regla de costo de adquisición (`r = CPA / neto`), neto completo (16 H1), 25 escenarios, estabilidad, rejilla factorial, verificaciones |
| `rank_sin_pagos.py` | Ranking sin el criterio de pagos (ya existía); `rank.py` lo importa y comprueba que coincide |
| `datos/mercados.json` | 15 mercados puntuados: puntajes publicados de 08 §2.2 con su confianza, CPM, tarifa de Meta, ticket, IVA, comisión por método, cobertura de pago, población, ajuste de creadores (08 y "en regla"), cada uno con fuente |
| `datos/parametros.json` | Pesos, bandas de CAC y de pago, embudo (CTR, conversión), costos directos, criterio de escala, valores de los escenarios |
| `resultados/escenarios.json` | Salida generada y versionada de todos los escenarios y de la rejilla (una prueba exige que coincida con el código) |

## Uso (desde la raíz del repositorio)
```
python3 -I scripts/mercados/rank.py                        # reproduce los 15 totales de 08 y verifica
python3 -I scripts/mercados/rank.py --lista                # escenarios
python3 -I scripts/mercados/rank.py --escenario corregido  # tabla con r, orden económico (#r), CPA y neto
python3 -I scripts/mercados/rank.py --todos                # resumen de estabilidad de todos los escenarios
python3 -I scripts/mercados/rank.py --grid [--cac-modo relativo]   # 216 combinaciones: frecuencia en el top
python3 -I scripts/mercados/rank.py --exportar scripts/mercados/resultados/escenarios.json
.venv/bin/python -m unittest tests.mercados                # pruebas (27)
```

## Cómo cambiar un dato o recalibrar con datos propios
1. Editar `datos/mercados.json` (un CPM, un ticket, un IVA, una cobertura) o `datos/parametros.json` (CTR, conversión, reembolsos). Mantener `fuente` y la etiqueta `[HIPÓTESIS]`/`[VERIFICAR]`.
2. `python3 -I scripts/mercados/rank.py` debe seguir en "OK" si no se tocaron los puntajes publicados; si cambió un dato de entrada, las pruebas que fijan los números de 08/16 lo avisarán (es intencional).
3. Regenerar `resultados/escenarios.json` con `--exportar` y correr las pruebas.

Limitaciones: casi todos los insumos son confianza C; los 9 mercados fuera del top 15 de 08 no tienen desglose y no se recalculan; el criterio de escala y el CAC "relativo" son propuestas `[NUEVO]`, no parte de 08.
