"""Paquete scripts.cerebro: las herramientas del Cerebro que no son una skill (el buscador por idea, el jardinero del domingo y el lector de preferencias).

* ``comun``         lectura confinada y solo lectura de la memoria (lista única, decisiones, lecciones, preferencias) y similitud de texto.
* ``buscar``        buscador por idea: difuso (BM25, plurales y erratas) y por etiquetas; devuelve fuente y fecha. Sin red, sin embeddings.
* ``jardinero``     el jardinero del domingo EN SECO: propone (fusiones, cierres, decisiones superadas, lecciones sin prueba, recordatorios); no aplica nada.
* ``preferencias``  lo que las skills (D6 y otras) leen: SOLO las preferencias que el dueño aprobó; una propuesta no rige.

Las escribe y lee la skill ``/cerebro-abrir`` y ``/cerebro-cerrar``; lo que guardan lo escribe únicamente ``guardar_pendiente.py``. Biblioteca estándar.
"""
