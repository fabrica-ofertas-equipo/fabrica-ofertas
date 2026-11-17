"""Marco de robots EN SOMBRA (S-C): robots de solo lectura y propuesta, con latido por robot.

Nada aquí envía mensajes, llama a Meta o Stripe, gasta, pausa, activa ni firma. Cada robot lee archivos del proyecto y la base en
modo ``ro`` y devuelve una PROPUESTA o una medición. El runtime real (host, cola, reintentos, ejecución con guard) es de S-B.

Uso (desde la raíz del repositorio)::

    .venv/bin/python -m scripts.robots.sombra listar
    .venv/bin/python -m scripts.robots.sombra ejecutar --todos --simular
    .venv/bin/python -m scripts.robots.sombra estado
    .venv/bin/python -m scripts.robots.sombra programar

Diseño y pedidos: ``docs/_historial/mentor-sistema/robots-sombra.md`` y ``robots.propuesta.yaml``.
"""
