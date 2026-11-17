# evals/dorados

10 casos de departamentos/16 §10.5 (D01-D10). Deben dar PASS con 0 bloqueantes. D01 y D02 traen `contexto.json` ejecutable con `scripts/puntaje.py seleccionar`;
`fixtures/pais-*.json` son fichas de EJEMPLO armadas desde las notas 07a-07h/08 (no son el atlas). Salida esperada de cada caso en su `caso.json` o `.json`.
Automatizado: `.venv/bin/python -I .claude/skills/m1-mercados-localizacion/scripts/autoprueba.py`. Lo que solo juzga un QA (L2) va en `verificacion.L2`.
Anti-sobreajuste: los casos cubren dinero, salud y relaciones, y los idiomas it, pl, en y de; ningun caso es 'el' caso de la skill.
