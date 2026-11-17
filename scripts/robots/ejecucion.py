"""Ejecutor de robots en sombra: corre cada robot por separado, registra su latido y SIGUE con los demás aunque uno falle.

* Un robot que lanza una excepción queda como ``resultado: "error"`` (con la razón recortada) y no tumba a los otros.
* El latido se escribe (solo con ``--escribir``) justo después de cada robot, así que una caída posterior no pierde lo ya hecho.
* Por defecto NO se escribe nada. Con ``--escribir``: el latido de cada robot, el producto de cada robot bajo ``empresa/robots/salidas/``,
  ``empresa/datos/alertas.jsonl`` (robot de alertas) y, al final, ``empresa/robots/estado.json``.
* Nada envía mensajes ni toca Meta o Stripe: los robots no importan esos módulos (lo comprueba ``tests/robots/test_sin_red.py``).
"""
from __future__ import annotations

import datetime as _dt
import time
from typing import Any, Callable

from scripts.alertas.hechos import limpiar_texto
from scripts.robots import latidos as L
from scripts.robots import r_alarma, r_alertas, r_auditor, r_baja_j3, r_informe, r_perfil, r_vigia
from scripts.robots.catalogo import ORDEN_EJECUCION, por_id
from scripts.robots.estado import calcular_estado, escribir_estado
from scripts.robots.nucleo import Contexto, ErrorRobot, Resultado, iso_z

__all__ = ["EJECUTORES", "ejecutar", "ejecutar_robot", "texto_resumen"]

EJECUTORES: dict[str, Callable[[Contexto], Resultado]] = {
    r_perfil.ID: r_perfil.correr, r_alertas.ID: r_alertas.correr, r_vigia.ID: r_vigia.correr, r_alarma.ID: r_alarma.correr,
    r_baja_j3.ID: r_baja_j3.correr, r_auditor.ID: r_auditor.correr, r_informe.ID: r_informe.correr,
}
_ROTULO = {"ok": "OK", "parcial": "PARCIAL", "sin_datos": "SIN DATOS", "sin_decidir": "SIN DECIDIR", "alerta": "ALERTA", "error": "ERROR"}


def ejecutar_robot(robot_id: str, c: Contexto, *, origen: str = "manual") -> dict[str, Any]:
    """Corre UN robot y devuelve ``{robot, resultado, razon, inicio, fin, duracion_ms, resumen, datos, salidas, metricas, latido}``. Nunca lanza por el robot."""
    meta = por_id(robot_id)
    if meta is None or robot_id not in EJECUTORES:
        raise ErrorRobot(f"el robot «{robot_id}» no tiene versión en sombra")
    inicio = c.ahora()
    t0 = time.perf_counter()
    try:
        res = EJECUTORES[robot_id](c)
        if not isinstance(res, Resultado):
            raise ErrorRobot("el robot no devolvió un Resultado")
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - un robot roto no puede tumbar a los demás; se registra y se sigue
        res = Resultado("error", f"{type(exc).__name__}: {limpiar_texto(str(exc), 200)}",
                        [f"El robot falló: {type(exc).__name__}. Los demás siguieron."], datos={})
    duracion_ms = int((time.perf_counter() - t0) * 1000)
    salida: dict[str, Any] = {
        "robot": robot_id, "nombre": meta["nombre"], "resultado": res.estado, "razon": res.razon, "inicio": iso_z(inicio), "duracion_ms": duracion_ms,
        "resumen": res.resumen, "datos": res.datos, "salidas": res.salidas, "metricas": res.metricas, "latido": {"id": L.id_latido(robot_id, inicio), "escrito": False, "ya_existia": False, "error": None},
    }
    salida["fin"] = iso_z(inicio + _dt.timedelta(milliseconds=duracion_ms))
    if c.escribir:
        try:
            linea = L.construir_latido(robot_id, inicio, duracion_ms, res.estado, res.razon, origen=origen, salidas=res.salidas, metricas=res.metricas)
            nuevo = L.anexar(c.raiz, linea)
            salida["latido"].update(escrito=nuevo, ya_existia=not nuevo)     # repetir el mismo instante no es una falla: es idempotencia
        except ErrorRobot as exc:
            salida["latido"]["error"] = limpiar_texto(str(exc), 200)
    return salida


def ejecutar(robots: list[str], c: Contexto, *, origen: str = "manual") -> dict[str, Any]:
    """Corre los robots pedidos en el orden de ``ORDEN_EJECUCION`` y devuelve la corrida completa. ``errores`` > 0 no corta nada."""
    orden = [r for r in ORDEN_EJECUCION if r in robots]
    inicio = c.ahora()
    resultados = [ejecutar_robot(r, c, origen=origen) for r in orden]
    corrida: dict[str, Any] = {
        "tipo": "corrida_robots_sombra", "inicio": iso_z(inicio), "modo": "escrito" if c.escribir else "simulado", "origen": origen, "robots": resultados,
        "errores": sum(1 for r in resultados if r["resultado"] == "error"), "fallas_de_latido": sum(1 for r in resultados if r["latido"]["error"]),
        "estado_escrito": None, "error_estado": None,
    }
    if c.escribir:
        try:
            corrida["estado_escrito"] = escribir_estado(c.raiz, calcular_estado(c.raiz, c.ahora()))
        except (ErrorRobot, OSError, ValueError) as exc:
            corrida["error_estado"] = limpiar_texto(f"{type(exc).__name__}: {exc}", 200)
    return corrida


def texto_resumen(corrida: dict[str, Any]) -> str:
    modo = "GUARDADO (latidos y productos escritos)" if corrida["modo"] == "escrito" else "SIMULACRO: no se escribió nada"
    L_ = [f"ROBOTS EN SOMBRA — {corrida['inicio']} · {modo}", ""]
    for r in corrida["robots"]:
        L_.append(f"  {r['robot']:<10} {_ROTULO[r['resultado']]:<12} {r['razon']}")
    L_.append("")
    for r in corrida["robots"]:
        L_.append(f"[{r['robot']}] {r['nombre']} ({r['duracion_ms']} ms)")
        L_ += [f"    {x}" for x in r["resumen"]]
    corrieron = len(corrida["robots"])
    L_.append("")
    L_.append(f"Corrieron {corrieron} · con error {corrida['errores']} · no envió mensajes, no tocó Meta ni Stripe, no gastó, no pausó, no firmó.")
    if corrida["modo"] == "escrito":
        malos = [r["robot"] for r in corrida["robots"] if r["latido"]["error"]]
        L_.append("Latidos escritos en empresa/robots/latidos.jsonl" + (f" (FALLÓ para: {', '.join(malos)})" if malos else ""))
    return "\n".join(L_)
