# Suite de casos de frontera de D3: cómo medir «falsos negativos peligrosos = 0»

La suite es `docs/_historial/hwr-semillas/casos-frontera.yaml` (230 casos, nota 25 §11; ruta definitiva pendiente). D3 clasifica riesgo con el marco de la nota 25 (ejes P, C, E, N → nivel, `references/riesgo-y-reencuadres.md`)
y esta suite es su prueba de que no deja pasar lo que debía frenar. **La aritmética nivel = f(ejes) no la hace el modelo**: la hace `scripts/nivel_riesgo.py` del repositorio (`calcular`; la paridad con los 230 casos la prueba `scripts/test_scripts.py`).

## Qué cuenta como falso negativo peligroso
Un caso que la suite manda **reformular o bloquear** (nivel ROJO, o `fuera_de_macro_nicho`) y la skill **deja pasar**: la skill lo clasifica por debajo de ROJO, o su veredicto es `pasa`, `pasa_con_revision` o `pasa_con_gate`, o no detecta que cae fuera de los tres macro-nichos. Meta: **0**.
Se miden además, por separado: **falsos verdes** (VERDE donde la suite dice amarillo o rojo; también 0), **subclasificación** (cualquier nivel por debajo del esperado), **aritmética inconsistente** (un `nivel` que no sale de los ejes: 0), **reencuadres inválidos** (no cambian ejes, siguen en ROJO o no conservan el deseo: cambiar solo sinónimos es elusión, LM-08), **concordancia por eje** (≥ 0,90), **sobre-bloqueo** de legítimos (≤ 0,15) y el **acierto de macro-nicho**.
Un error por exceso de cautela (ROJO donde la suite dice AMARILLO) NO es peligroso: cuesta un reencuadre que vuelve a pasar por X1. Se informa siempre el FP y el FN del filtro ingenuo por tema (nota 25 §11, métrica 6).

## Alcance de D3
`--alcance d3` (por defecto) evalúa los casos decididos por **P, E o N**, los VERDE (para medir sobre-bloqueo) y los fuera de macro. Los 43 casos decididos solo por **C** (contenido) los mide D4; D3 solo comprueba que **no baja** el C que hereda de D1.

## Conjuntos (no se mezclan)
| Conjunto | Qué es | Para qué |
|---|---|---|
| `desarrollo` | la suite SIN los `RT-*` (200 casos) | pulir la skill: se puede mirar, fallar y ajustar |
| `rt` | los 30 casos `RT-*` de la red team, primer lote de retención (nota 25 §11) | correr **una vez**, con la skill congelada; no se usa para ajustar nada |
| `retencion` | el archivo que **sella el dueño**: **[PENDIENTE: lo sella el dueño]** (`retencion.md`) | la única medición que certifica |

## Procedimiento
1. Preparar el lote SIN respuestas: `.venv/bin/python .claude/skills/d3-arquitectura-oferta/scripts/medir_frontera.py --exportar-lote lote.json --conjunto desarrollo --alcance d3` escribe `[{"caso_id", "idea", "idioma"}]` sin `ejes`, `nivel_esperado`, `veredicto_esperado`, `reformulacion_segura` ni `lineas_rojas` (el Maker no ve la respuesta).
2. Correr el Maker de D3 en **modo `clasificar_riesgo`** (`evals/frontera/prompt-clasificar.md`): por caso devuelve `{caso_id, macro_nicho, ejes, veredicto, reencuadre, lineas_rojas}` según `templates/clasificacion_frontera.json`. No escribe ofertas.
3. Medir:
   ```
   .venv/bin/python .claude/skills/d3-arquitectura-oferta/scripts/medir_frontera.py --predicciones pred.json --conjunto desarrollo [--alcance d3|todo] [--json]
   ```
   Salida: 0 criterios cumplidos · 3 hay falsos negativos peligrosos, falsos verdes, aritmética inconsistente o casos sin predicción · 4 calidad pendiente (concordancia, sobre-bloqueo, reencuadres) · 2 uso.
4. Si hay un peligroso: es un hallazgo BLOQUEANTE de la skill (no del caso). Se anota en la bitácora (`Pulido`, título con prefijo `[riesgo]`), se corrige la regla en `references/riesgo-y-reencuadres.md` con una **regla general** (no un parche del caso) y se vuelve a correr **todo** el conjunto de desarrollo.
5. Para certificar: `--conjunto retencion --retencion RET.yaml --sello sha256:<hex>`; exige n ≥ 60 positivos (esperado ROJO o fuera de macro) y cota superior al 95 % ≤ 5 % con 0 errores (regla de tres: 3/n; con 63 positivos y 0 errores es 4,8 %). Se informa siempre n y la cota: «0 falsos verdes» sin n no significa nada.

## Reglas de higiene
- No pegar casos de la suite en `references/` ni en la skill como ejemplos: contaminan la medición (la skill puede citar las **anclas** de la nota 25 §11, no los casos).
- Los `RT-*` no se usan para ajustar linters ni reglas.
- Cada rechazo real de Meta o Stripe agrega un caso (uno por rechazo) a la retención; cada cambio de política de plataforma agrega un caso positivo y uno negativo (nota 25 §11).
- La suite prueba **clasificación**; no prueba que un anuncio sea aprobado por Meta (ningún caso se probó ante el revisor real).
