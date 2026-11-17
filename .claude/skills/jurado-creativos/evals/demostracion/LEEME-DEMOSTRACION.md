# DEMOSTRACIÓN — no es una opinión de nadie

Esta carpeta muestra el flujo del Jurado de creativos con **votos sintéticos** generados por una función determinista (`scripts/jurado/demo.py`), sin ningún LLM. Las piezas son los 11 ganchos candidatos de la oferta piloto OF-202611-91 y dos controles escritos a mano. **Nada de aquí sirve para decidir un anuncio**: todos los archivos llevan `demostracion: true` y los votos `origen: sintetico_demo`; `agregar.py` y `calibrar.py` los rechazan fuera de una demostración.

Qué mirar: `avatares.json` (10 avatares con sus citas y su límite de N), `tanda-*/ciego/` (lo que vería un votante: una pieza por paquete, ids opacos), `tanda-*/privado/` (manifiesto con la semilla y el orden, llave, informes de ceguera y L1), `tanda-*/votos/` y `tanda-*/jurado.json` (ranking, bandas, acuerdo, anclas). `calibracion-vacia.json` muestra que hoy hay 0 de 150 etiquetas: no se mide ningún acierto.

Reproducir: `.venv/bin/python -m scripts.jurado.demo corrida --salida .claude/skills/jurado-creativos/evals/demostracion`.
