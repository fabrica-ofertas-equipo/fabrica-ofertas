# Evals de la skill D3

| Carpeta | Contenido | Cómo se usa |
|---|---|---|
| `dorados/` | `casos.yaml` (los 9 casos de §10.5 con entrada y salida esperada), tres ofertas doradas completas (`01-es-es-reinsercion`, `02-it-it-planner-pasti`, `03-pl-pl-karty-rozmow`: dinero/salud/relaciones en es/it/pl), planes del motor para los casos 2 y 6 y `_esperado-numerico.yaml` | El Maker corre cada caso; el QA debe dar PASS a las doradas; los números se reproducen con los scripts |
| `sembrados/` | `sembrados.yaml` (S1-S25 con mutación y salida esperada del QA) y `datos/` (economías generadas por el motor para S4, S5 y S14) | `scripts/aplicar_sembrado.py` crea la copia defectuosa; el QA debe detectar ≥ 90 % de los bloqueantes (≥ 18 de 20) |
| `frontera/` | cómo medir falsos negativos peligrosos = 0, el encargo del modo `clasificar_riesgo` y el conjunto de retención [PENDIENTE: lo sella el dueño] | `scripts/medir_frontera.py` |

## Pruebas de los scripts (sin red, sin escritura fuera de temporales)
```
.venv/bin/python -m unittest discover -s .claude/skills/d3-arquitectura-oferta/scripts -p 'test_*.py'
```
Comprueban: la paridad de `scripts.nivel_riesgo` con los 230 casos de la suite (no hay tabla propia); que `economia_por_pais.py` reproduce `ofertas/_ejemplo/03-oferta/economia.json` y lee el evento de aprendizaje de `estadistica.*`; que las tres doradas pasan `validar_esquemas oferta` y `lint_d3`; que cada sembrado con `l1_esperado` lo detecta el script declarado (18 de 25; los otros 7 solo los puede detectar el juicio del QA); y que `medir_frontera.py` da 0 con un oráculo y > 0 con un clasificador ingenuo por tema.

## Qué NO prueban
Que una oferta venda (eso lo dice el mercado), que Meta apruebe un anuncio, ni que el texto en italiano o polaco sea nativo (revisión nativa pendiente, backbone 5.10). Un PASS del QA prueba que la oferta cumple la rúbrica; la validación de mercado es D8.

## Orden de corrida recomendado (DoD de la spec §10.4)
1. Tests de scripts (verde). 2. Dorados con el Maker (casos 1-9). 3. QA sobre las doradas (PASS) y sobre los sembrados (≥ 90 %). 4. Suite de frontera: `desarrollo`; al congelar, `rt`; la retención cuando el dueño la selle.
