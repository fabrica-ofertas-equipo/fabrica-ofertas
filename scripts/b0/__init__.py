"""``scripts.b0`` — módulos de evaluación de los criterios de B0 que no dependen del motor de
estados (``engine.estado``/``orq``/``d8``, en construcción esta noche por B1a/B1b). Cada módulo
expone una o más funciones ``evaluar_b0_NN(...) -> scripts.b0_e2e.Criterio`` que ``scripts.b0_e2e``
importa y registra. Ninguno usa red ni credenciales reales (``FABRICA_ENTORNO=prueba``, raíz
temporal inyectada).
"""
from __future__ import annotations
