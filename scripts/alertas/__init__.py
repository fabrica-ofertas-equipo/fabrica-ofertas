"""Paquete scripts.alertas: alertas, semáforo «¿me puedo ausentar?» y su productor (B10 de docs/04 §5).

* ``hechos``   lee SOLO archivos locales del proyecto (sin red, sin claves, sin ``.env``) y junta lo que hace falta en un diccionario.
* ``reglas``   convierte esos hechos en alertas conformes a ``contratos/alertas.schema.json`` (reglas que no necesitan datos de ventas).
* ``semaforo`` convierte los mismos hechos en el semáforo verde/amarillo/rojo y la lista «qué falta, en orden, y a quién le toca».
* ``producir`` es el productor: ``python -m scripts.alertas.producir`` (``--simular`` por defecto, ``--escribir`` para guardar).

Lo comparten el panel (``GET /api/alertas``, ``GET /api/informe``), el informe de las 08:30 (``scripts.informe``) y la línea de comandos.
"""
