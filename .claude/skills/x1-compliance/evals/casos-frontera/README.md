# Suite de casos de frontera: el eval central de X1

Fuente: `docs/_historial/hwr-semillas/casos-frontera.yaml` (v2, 230 casos; ejes P·C·E·N, nivel, veredicto, reencuadre, línea roja). Es **solo lectura y de otra sesión**: aquí no se copia, se corre. La aritmética `nivel = f(ejes)` ya está probada (0 discrepancias con `scripts/nivel_ejes.py`, que es la tabla de la nota 25 §2.3); lo que se mide aquí es la **clasificación** del clasificador (el LLM del Maker/QA), que es lo que podría dar un falso verde.

## Protocolo (clasificador ciego)

1. `.venv/bin/python .claude/skills/x1-compliance/scripts/correr_evals.py suite-entrada --salida $ESCRATCH/entrada.json` → 200 casos (`id`, `idea`, `idioma`) **sin etiquetas esperadas** y **sin los 30 RT-\*** (primer lote de retención: no se usan para ajustar).
2. Un Maker (o QA) en **contexto limpio**, con la skill, asigna ejes por caso aplicando `references/criterio-riesgo.md` y devuelve `{"<id>": {"ejes": {"P":"P0","C":"C1","E":"E0","N":"N1"}, "macro": "dinero", "reformulado": {"ejes": {...}}}}`. No declara el nivel: lo calcula el script. Repetir **sin la skill** (línea base) para ver que la skill mejora.
3. `.venv/bin/python .claude/skills/x1-compliance/scripts/correr_evals.py suite --respuestas R.json` imprime: **falsos verdes peligrosos** (rojo → verde; requisito 0), subclasificados (rojo → amarillo), **sobre-bloqueo** (legítimo clasificado un nivel por encima; requisito ≤ 15 %), concordancia por eje (≥ 90 %) y la referencia del filtro ingenuo por tema (71 falsos positivos y 79 falsos negativos en la suite completa).
4. Cualquier falso verde es un defecto de la skill, no ruido: se corrige el criterio (`references/criterio-riesgo.md`), se agrega el caso a `evals/adversarial/` y se repite. **Nunca se ajusta mirando los RT-\***.

La suite sirve para **desarrollar**; no certifica. La certificación (≥ 60 positivos, 0 falsos verdes, cota ≤ 5 %) es contra la retención sellada por el dueño: `../retencion/README.md`.

## Qué mirar al pulir (dueño)

- ¿Qué legítimo bloqueó el clasificador por el tema (embarazo, deuda, duelo, ruptura, «madres», «prestiti»)? Es sobre-bloqueo: afinar el criterio, no relajar una línea roja.
- ¿Qué peligroso pasó? Mirar qué eje falló: casi siempre P (verbo de cambio con el producto como sujeto), E (atributo en pregunta) o N (servicio humano oculto).
- ¿Un reencuadre «total» quedó rojo? Entonces R4 de la rúbrica es 1 o 2.
