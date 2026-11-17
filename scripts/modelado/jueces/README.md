# jueces
Instrucciones de los dos jueces de IA del Modo D (spec `departamentos/02-descubrimiento.md` §13).
- `rubrica.md`: reglas, preguntas y formato de respuesta (común a ambos).
- `juez_a.md`: auditor escéptico. `juez_b.md`: analista de modelado.
Las citas de cada juez se verifican contra el material antes de consolidar. Respuestas reales de la primera corrida: `../ejemplos/juez_a_crochet_2026-11-06.json` y `juez_b_…`.
Los ejemplos de `../ejemplos/` se hicieron con las reglas anteriores; se les quitaron las respuestas a las tres reglas que el dueño retiró (comunidad/app, commodity, producibilidad).
Cada juez corre por separado (idealmente modelos distintos), sin herramientas y sin ver al otro. Su JSON se consolida con `python -m scripts.modelado.juicio consolidar`.
En las pruebas de este repo los jueces se lanzaron como subagentes con permiso de lectura solo sobre estos archivos y el material; la versión desatendida los llamará por API sin herramientas.
