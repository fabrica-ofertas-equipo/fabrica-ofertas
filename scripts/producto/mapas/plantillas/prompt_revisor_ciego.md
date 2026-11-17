# Encargo: revisión ciega de exactitud lingüística

Lanzar UN agente de contexto limpio, solo lectura (Read, Grep, Glob), SIN acceso a: el prompt del escritor, el informe del escritor, los informes de QA automático ni otras revisiones.

Prompt del encargo (sustituir RUTA y N):

> Lee el archivo RUTA (solo ese archivo; no abras ningún otro archivo ni explores carpetas) y sigue al pie de la letra las «instrucciones» y la «rubrica» que contiene. Revisa los N mapas que trae. No escribas ni modifiques ningún archivo, no ejecutes código y no uses la web. Tu mensaje final debe ser ÚNICAMENTE el JSON del informe (sin texto antes ni después, sin bloque de código).

El archivo RUTA lo genera `revision_ciega.paquete(mapas, ruta)` (instrucciones, rúbrica E1-E8 y los mapas; nada del proceso de escritura). Lotes de ≤ 6 mapas por agente (el rendimiento de lectura baja con más). Guardar el JSON íntegro del revisor en `04-producto/qa/revision_ciega-ronda<N>.json` y validarlo con `revision_ciega.validar_informe`. La aceptación la calcula `revision_ciega.decidir`, no el revisor.
