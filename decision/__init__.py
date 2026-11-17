"""Paquete `decision`: estadistica del testeo, presupuestos, reglas secuenciales y simulacion.

Solo biblioteca estandar. Principio rector del proyecto: los LLM proponen, el codigo dispone.
Ningun umbral, tope ni presupuesto esta fijado en el codigo: todo se recibe como parametro
(`empresa/parametros.yaml`, `empresa/limites.yaml`, `economia.json`). Si falta un limite, las
funciones devuelven BLOQUEADO y nada se gasta ni se activa.

Modulos:
  estadistica  distribuciones (Beta, Gamma), intervalos, tamanos de muestra, probabilidades de error.
  presupuesto  economia por pedido, CPA de equilibrio, clics y presupuesto minimos por celda.
  reglas       decision secuencial (matar/seguir/escalar/inconcluso), control, compatibilidad con Meta,
               validacion de oferta con cohortes maduras.
  simulacion   Monte Carlo con semilla que mide las garantias de las reglas.
"""

__all__ = ["estadistica", "presupuesto", "reglas", "simulacion"]
