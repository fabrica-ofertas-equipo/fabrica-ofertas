# Encargo: retraducción ciega PL→EN (capa de QA de idioma)

Generar con `qa_idioma.preparar_retraduccion(mapas, porcentaje=..., semilla=...)`: el archivo `ciego` (solo polaco) va al agente; el `secreto` (originales) se guarda FUERA de la carpeta que ve el agente.

Prompt del encargo:

> Lee el archivo RUTA (solo ese archivo; no abras ningún otro archivo ni explores carpetas). Contiene textos en polaco y una «instruccion». Traduce al inglés TODOS los textos de «frases» y «palabras» siguiendo la instrucción; no omitas ninguno. No escribas ni modifiques ningún archivo, no ejecutes código y no uses la web. Tu mensaje final debe ser ÚNICAMENTE un JSON válido {"traducciones": {"<id>": "<inglés>"}} con una entrada por cada id (sin texto antes ni después, sin bloque de código).

Comparar con `qa_idioma.comparar_retraduccion(secreto, respuesta)`: `discrepancias_frases` son DISPARADORES de adjudicación (no errores probados): en el piloto el 86 % de las frases superó el umbral 0,6 y de las 18 marcadas la mayoría eran variantes benignas (mum/mom, holiday/vacation) y 3 eran cambios reales de sentido o de matiz.
