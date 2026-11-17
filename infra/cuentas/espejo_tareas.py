#!/usr/bin/env python3
"""Espejo de tareas programadas entre las dos cuentas de Claude.

La app guarda horario, carpeta y permisos de cada tarea en un registro por
cuenta (scheduled-tasks.json). Los prompts (~/.claude/scheduled-tasks/<id>/SKILL.md)
son compartidos. Solo corren las tareas de la cuenta con la que está abierta la app.

Este script detecta la cuenta ACTIVA (la que tiene la sesión más reciente) y copia
sus tareas a la otra, así al cambiar de cuenta en la app las tareas ya están.
Nunca escribe el registro de la cuenta activa: la app lo tiene en uso.

Uso:
  python3 infra/cuentas/espejo_tareas.py            # copia activa -> inactiva
  python3 infra/cuentas/espejo_tareas.py --estado   # solo muestra qué cuenta está activa
"""
import datetime
import json
import os
import sys
import tempfile

BASE = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "cuentas.json")
LOG = os.path.join(AQUI, "espejo.log")

# Campos que describen la tarea (se copian). El resto es estado de corrida y no se toca.
DEFINICION = ("displayName", "cronExpression", "fireAt", "enabled", "filePath", "cwd",
              "permissionMode", "permissionModeCarried", "useWorktree")
# Una tarea de una sola vez ya disparada no se copia.


def log(msg):
    linea = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(linea)
    with open(LOG, "a") as f:
        f.write(linea + "\n")
    # que el log no crezca sin fin
    with open(LOG) as f:
        lineas = f.readlines()
    if len(lineas) > 2000:
        with open(LOG, "w") as f:
            f.writelines(lineas[-1000:])


def leer(ruta):
    with open(ruta) as f:
        return json.load(f)


def ultima_corrida(reg):
    fechas = [t.get("lastRunAt") or "" for t in reg.get("scheduledTasks", [])]
    return max(fechas) if fechas else ""


def ultima_actividad(ruta_registro):
    """Momento de la sesión más reciente de la cuenta (cada sesión, propia o de una
    tarea, es un local_*.json que la app actualiza mientras corre)."""
    carpeta = os.path.dirname(ruta_registro)
    tiempos = [os.path.getmtime(os.path.join(carpeta, f))
               for f in os.listdir(carpeta) if f.startswith("local_") and f.endswith(".json")]
    return max(tiempos) if tiempos else 0.0


def escribir_atomico(ruta, datos):
    d = os.path.dirname(ruta)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".espejo-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def main():
    cfg = leer(CONFIG)
    cuentas = []
    for c in cfg["cuentas"]:
        ruta = os.path.join(BASE, c["registro"])
        if not os.path.exists(ruta):
            log(f"ERROR no existe el registro de {c['nombre']}: {ruta}")
            return 1
        reg = leer(ruta)
        cuentas.append({**c, "ruta": ruta, "reg": reg, "ultima": ultima_corrida(reg),
                        "actividad": ultima_actividad(ruta)})

    cuentas.sort(key=lambda c: c["actividad"], reverse=True)
    activa, inactiva = cuentas[0], cuentas[1]

    if "--estado" in sys.argv:
        for c in cuentas:
            marca = "ACTIVA " if c is activa else "inactiva"
            n = len(c["reg"].get("scheduledTasks", []))
            act = datetime.datetime.fromtimestamp(c["actividad"]).strftime("%d-%m %H:%M") if c["actividad"] else "—"
            print(f"{marca} {c['nombre']}: {n} tareas, última sesión {act}, última corrida {c['ultima'] or '—'}")
        return 0

    if not activa["reg"].get("scheduledTasks"):
        log(f"la cuenta activa ({activa['nombre']}) no tiene tareas; no copio nada para no vaciar la otra")
        return 0
    # si la otra cuenta tuvo actividad hace menos de 10 min, puede estar cambiándose: no tocar
    if inactiva["actividad"] and activa["actividad"] - inactiva["actividad"] < 600:
        log("las dos cuentas tuvieron actividad en los últimos 10 min; espero a la próxima vuelta")
        return 0

    # cambio de cuenta detectado (la activa no es la de la vez anterior)
    estado_ruta = os.path.join(AQUI, ".ultima_activa")
    anterior = open(estado_ruta).read().strip() if os.path.exists(estado_ruta) else ""
    if anterior and anterior != activa["nombre"]:
        log(f"CAMBIO DE CUENTA: ahora corre {activa['nombre']} (antes {anterior})")
    with open(estado_ruta, "w") as f:
        f.write(activa["nombre"])

    ahora = datetime.datetime.now(datetime.timezone.utc)
    piso = ahora.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    viejas = {t["id"]: t for t in inactiva["reg"].get("scheduledTasks", [])}
    nuevas = []
    for t in activa["reg"].get("scheduledTasks", []):
        if t.get("fireAt") and not t.get("enabled"):
            continue  # una sola vez, ya disparada
        n = dict(viejas.get(t["id"], {}))
        for k in list(n):
            if k in DEFINICION:
                del n[k]
        n["id"] = t["id"]
        for k in DEFINICION:
            if k in t:
                n[k] = t[k]
        n.setdefault("createdAt", int(ahora.timestamp() * 1000))
        # al pasar a esta cuenta no se recuperan las vueltas perdidas antes de este momento
        n["missedRunScanFloor"] = piso
        nuevas.append(n)

    antes = sorted((t["id"], json.dumps({k: t.get(k) for k in DEFINICION}, sort_keys=True))
                   for t in inactiva["reg"].get("scheduledTasks", []))
    despues = sorted((t["id"], json.dumps({k: t.get(k) for k in DEFINICION}, sort_keys=True))
                     for t in nuevas)
    inactiva["reg"]["scheduledTasks"] = nuevas
    escribir_atomico(inactiva["ruta"], inactiva["reg"])
    if antes != despues:
        log(f"copiadas {len(nuevas)} tareas de {activa['nombre']} a {inactiva['nombre']} (hubo cambios)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
