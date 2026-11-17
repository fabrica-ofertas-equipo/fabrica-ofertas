#!/usr/bin/env python3
"""Guarda el horario de las tareas programadas para la agenda del panel (``ofertas/_funnels/tareas.json``).

El panel calcula solo la próxima corrida de cada tarea con su cron, pero el cron vive en la app de Claude y solo una sesión lo
puede leer (``list_scheduled_tasks``). La vigilancia lo refresca en cada vuelta completa (punto 2c): guarda la respuesta en el
scratchpad y corre este script. Pedido del dueño (14-nov): ver en cada oferta qué está programado, qué se está haciendo y qué se hizo.

Uso: python3 tareas_snapshot.py --entrada <respuesta de list_scheduled_tasks.json>   (o la respuesta por la entrada estándar)
Escribe solo los campos que usa el panel: taskId, title, schedule, cronExpression, fireAt, enabled, nextRunAt, lastRunAt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
DESTINO = RAIZ / "ofertas" / "_funnels" / "tareas.json"
CAMPOS = ("taskId", "title", "schedule", "cronExpression", "fireAt", "enabled", "nextRunAt", "lastRunAt")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", help="JSON con la lista de tareas (si falta, se lee la entrada estándar)")
    ap.add_argument("--destino", default=str(DESTINO))
    a = ap.parse_args()
    crudo = Path(a.entrada).read_text(encoding="utf-8") if a.entrada else sys.stdin.read()
    datos = json.loads(crudo)
    lista = datos.get("tareas") if isinstance(datos, dict) else datos
    if not isinstance(lista, list) or not lista:
        sys.exit("No es una lista de tareas: no se escribe nada.")
    tareas = [{k: t.get(k) for k in CAMPOS if k in t} for t in lista if isinstance(t, dict) and t.get("taskId")]
    salida = {"leido": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "tareas": tareas}
    destino = Path(a.destino)
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, destino)
    print(f"tareas.json: {len(tareas)} tareas")


if __name__ == "__main__":
    main()
