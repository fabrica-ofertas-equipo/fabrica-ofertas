"""``programar``: IMPRIME (nunca instala) las entradas de launchd y de cron para correr cada robot en sombra a su hora en la Mac del dueño.

No escribe archivos, no llama a ``launchctl`` ni a ``crontab``, no crea carpetas. Instalar es una decisión del DUEÑO (E1 de brechas/04: topología del motor).
Las horas del método son del reloj del MERCADO (HIPÓTESIS, E-14); launchd y cron usan la hora de esta Mac, así que se convierten para HOY: cuando cambie el
horario de verano en alguno de los dos lugares hay que volver a correr ``programar``.
"""
from __future__ import annotations

import datetime as _dt
import plistlib
import shlex
from pathlib import Path
from typing import Any

from scripts.robots.catalogo import CATALOGO, horas_programadas, ids_en_sombra
from scripts.robots.zonas import ZONA_MERCADO_DEFECTO, zona, zona_local

__all__ = ["ADVERTENCIA", "entradas", "generar", "hora_local"]

PREFIJO = "com.fabrica-ofertas.robot."

ADVERTENCIA = """\
══ NO SE INSTALÓ NADA ══ Esto solo IMPRIME. Ningún archivo se escribió, no se llamó a launchctl ni a crontab.
Instalar estas entradas es decisión del DUEÑO (E1 de brechas/04, topología: servidor siempre encendido o esta Mac). Antes de decidir:
  1. Si la Mac duerme (man launchd.plist): los robots de HORA FIJA corren UNA vez al despertar lo que se perdió (agrupado); los PERIÓDICOS («cada N min»,
     StartInterval) y cron pierden las vueltas del sueño sin avisar, y `estado` los mostrará como vencidos. Con la Mac apagada o dormida no hay vigía de
     nada: esto NO es una red de seguridad (la red es el watchdog, B4-12).
  2. Son robots EN SOMBRA: leen y proponen. No envían mensajes, no tocan Meta ni Stripe, no gastan, no pausan, no firman. Con --escribir escriben
     empresa/robots/ (latidos y productos) y empresa/datos/alertas.jsonl.
  3. Cada entrada corre con --programado: desde su primera corrida el robot pasa a ESPERARSE (si falta su latido, `estado` lo marca vencido).
  4. Las horas del mercado se convirtieron a la hora de esta Mac para HOY. Con el cambio de horario de verano, volver a correr `programar`.
  5. Para quitar un robot: launchctl bootout gui/$(id -u)/<etiqueta> y borrar su .plist, o declararlo `estado: apagado` en empresa/robots.yaml."""


def hora_local(hora: str, reloj: str, tz_mercado: Any, tz_local: Any, hoy: _dt.date) -> tuple[int, int]:
    """«HH:MM» del reloj del mercado (o del dueño) → (hora, minuto) en la zona de esta Mac, con la fecha de ``hoy`` para resolver el horario de verano."""
    h, m = int(hora[:2]), int(hora[3:])
    if reloj == "dueno":
        return h, m
    t = _dt.datetime(hoy.year, hoy.month, hoy.day, h, m, tzinfo=tz_mercado).astimezone(tz_local)
    return t.hour, t.minute


def entradas(robot: dict[str, Any], *, python: str, raiz: Path, tz_mercado: Any, tz_local: Any, hoy: _dt.date, log_dir: Path) -> dict[str, Any]:
    """Todo lo necesario para instalar UN robot: etiqueta, argumentos, disparadores (launchd) y minuto/hora de cron."""
    argumentos = [python, "-m", "scripts.robots.sombra", "ejecutar", "--robot", robot["id"], "--escribir", "--programado", "--raiz", str(raiz)]
    prog = robot["programacion"]
    ent: dict[str, Any] = {"id": robot["id"], "etiqueta": PREFIJO + robot["id"], "argumentos": argumentos, "log": str(log_dir / f"{robot['id']}.log"),
                           "raiz": str(raiz), "reloj": robot["reloj"], "horario": robot["horario"]}
    if prog["tipo"] == "cada":
        ent.update(intervalo_s=int(prog["cada_min"]) * 60, cada_min=int(prog["cada_min"]), horas_locales=[])
    else:
        horas = sorted({hora_local(h, robot["reloj"], tz_mercado, tz_local, hoy) for h in horas_programadas(robot)})
        ent.update(intervalo_s=None, cada_min=None, horas_locales=[f"{h:02d}:{m:02d}" for h, m in horas])
    return ent


def _plist(ent: dict[str, Any]) -> str:
    doc: dict[str, Any] = {"Label": ent["etiqueta"], "ProgramArguments": ent["argumentos"], "WorkingDirectory": ent["raiz"], "RunAtLoad": False,
                           "StandardOutPath": ent["log"], "StandardErrorPath": ent["log"], "ProcessType": "Background", "LowPriorityIO": True}
    if ent["intervalo_s"]:
        doc["StartInterval"] = ent["intervalo_s"]
    else:
        doc["StartCalendarInterval"] = [{"Hour": int(h[:2]), "Minute": int(h[3:])} for h in ent["horas_locales"]]
    return plistlib.dumps(doc, sort_keys=False).decode("utf-8")


def _cron(ent: dict[str, Any]) -> list[str]:
    cmd = f"cd {shlex.quote(ent['raiz'])} && {' '.join(shlex.quote(a) for a in ent['argumentos'])} >> {shlex.quote(ent['log'])} 2>&1"
    if ent["intervalo_s"]:
        n = ent["cada_min"]
        return [f"{'0' if n == 60 else f'*/{n}'} * * * * {cmd}"]
    return [f"{int(h[3:])} {int(h[:2])} * * * {cmd}" for h in ent["horas_locales"]]


def generar(*, raiz: Path, python: str | None = None, formato: str = "ambos", robots: list[str] | None = None, zona_mercado: str = ZONA_MERCADO_DEFECTO,
            zona_dueno: str | None = None, ahora: _dt.datetime | None = None, home: Path | None = None) -> str:
    """El texto completo que imprime ``programar``. Función pura: no toca el disco."""
    ahora = ahora or _dt.datetime.now(_dt.timezone.utc)
    tz_m = zona(zona_mercado)
    tz_l = zona(zona_dueno) if zona_dueno else zona_local()
    hoy = ahora.astimezone(tz_m).date()
    py = python or str(raiz / ".venv" / "bin" / "python")
    log_dir = (home or Path.home()) / "Library" / "Logs" / "fabrica-robots"
    pedidos = robots or ids_en_sombra()
    ents = [entradas(r, python=py, raiz=raiz, tz_mercado=tz_m, tz_local=tz_l, hoy=hoy, log_dir=log_dir) for r in CATALOGO if r["id"] in pedidos and r["ejecutor_hoy"] == "sombra"]
    L = [ADVERTENCIA, "", f"Reloj del mercado: {zona_mercado} (HIPÓTESIS) · hora de esta Mac / del dueño: {tz_l} · calculado para {hoy.isoformat()}",
         f"Raíz del proyecto: {raiz}", f"Python: {py}", f"Registros: {log_dir} (hay que crear la carpeta: mkdir -p {shlex.quote(str(log_dir))})", "",
         "ROBOT       RELOJ     HORARIO DEL MÉTODO              EN ESTA MAC"]
    for e in ents:
        local = f"cada {e['cada_min']} min" if e["intervalo_s"] else ", ".join(e["horas_locales"])
        L.append(f"{e['id']:<11} {'dueño' if e['reloj'] == 'dueno' else 'mercado':<9} {e['horario']:<31} {local}")
    if formato in ("launchd", "ambos"):
        L += ["", "══ launchd ══ (un archivo por robot en ~/Library/LaunchAgents/<etiqueta>.plist; cargarlo es decisión del dueño)"]
        for e in ents:
            L += ["", f"--- {e['etiqueta']}.plist ---", _plist(e).rstrip(),
                  f"# Cargar:  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/{e['etiqueta']}.plist",
                  f"# Quitar:  launchctl bootout gui/$(id -u)/{e['etiqueta']}"]
    if formato in ("cron", "ambos"):
        L += ["", "══ cron ══ (crontab -e; cron usa la hora de esta Mac y NO recupera lo perdido si la Mac duerme)"]
        for e in ents:
            L += _cron(e)
    return "\n".join(L)
