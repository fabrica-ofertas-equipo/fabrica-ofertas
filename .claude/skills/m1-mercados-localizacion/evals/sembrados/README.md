# evals/sembrados

18 defectos sembrados de departamentos/16 §6 (D1-D18). Cada archivo: `defecto`, `mutaciones` (sobre las plantillas y fixtures de la skill), `deteccion` (que check lo caza: `l1` = script, `excluir` = puntaje.py, `L2` = juicio del QA) y `salida_esperada_qa`.
Objetivo: el QA detecta >= 90 % de los bloqueantes marcados `bloqueante_star` con 0 falsos PASS. Los medibles por script se corren con
`.venv/bin/python -I .claude/skills/m1-mercados-localizacion/scripts/autoprueba.py`; los `L2` (D09) los mide una corrida del QA con la rubrica.
Regla de calibracion: rotar la mitad de los sembrados cada vez que cambie la skill del QA para que no se memoricen (backbone 6.6).
