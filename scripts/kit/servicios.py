"""Servicios de fondo de la fábrica en esta Mac (agentes de inicio de macOS, sin sudo). Paso 10 de instalar-fabrica.

  python3 scripts/kit/servicios.py panel        el panel en http://127.0.0.1:8790 siempre prendido (clave fija)
  python3 scripts/kit/servicios.py meta-vivo    lee Meta cada 10 minutos sin Claude (necesita META_ACCESS_TOKEN en .env)
  python3 scripts/kit/servicios.py estado       cuáles están cargados
  python3 scripts/kit/servicios.py quitar NOMBRE

Los agentes usan la ruta de ESTA carpeta y el Python de .venv; si se mueve la carpeta, se vuelven a crear.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parents[2]
PY = RAIZ / ".venv" / "bin" / "python"
AGENTES = Path.home() / "Library" / "LaunchAgents"
LOGS = Path.home() / "Library" / "Logs"

SERVICIOS = {
    "panel": {"args": [str(PY), "-m", "dashboard", "--puerto", "8790", "--no-abrir", "--clave-fija"], "keepalive": True},
    "meta-vivo": {"args": [str(PY), str(RAIZ / ".claude/skills/escalar-oferta/scripts/meta_vivo.py")], "intervalo": 600},
}


def etiqueta(nombre: str) -> str:
    return f"com.fabrica.{nombre}"


def plist(nombre: str, s: dict) -> str:
    args = "".join(f"<string>{escape(a)}</string>" for a in s["args"])
    extra = "<key>KeepAlive</key><true/>" if s.get("keepalive") else f"<key>StartInterval</key><integer>{s['intervalo']}</integer>"
    log = LOGS / f"fabrica-{nombre}.log"
    return ('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict>'
            f"<key>Label</key><string>{etiqueta(nombre)}</string><key>ProgramArguments</key><array>{args}</array>"
            f"<key>WorkingDirectory</key><string>{escape(str(RAIZ))}</string><key>RunAtLoad</key><true/>{extra}"
            f"<key>StandardOutPath</key><string>{log}</string><key>StandardErrorPath</key><string>{log}</string>"
            "</dict></plist>\n")


def cargar(nombre: str) -> int:
    if not PY.is_file():
        print("Falta .venv: corré primero el paso 2 de la instalación.")
        return 1
    AGENTES.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    p = AGENTES / f"{etiqueta(nombre)}.plist"
    p.write_text(plist(nombre, SERVICIOS[nombre]), encoding="utf-8")
    dominio = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{dominio}/{etiqueta(nombre)}"], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", dominio, str(p)], capture_output=True, text=True)
    if r.returncode:
        print(f"No se pudo cargar {nombre}: {r.stderr.strip()}")
        return 1
    print(f"{nombre}: cargado ({p}). Registro en {LOGS / f'fabrica-{nombre}.log'}")
    if nombre == "panel":
        print("La dirección con la clave aparece en el registro en unos segundos (línea que empieza con http://127.0.0.1:8790).")
    return 0


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd in SERVICIOS:
        return cargar(cmd)
    if cmd == "estado":
        lista = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
        for n in SERVICIOS:
            print(f"{n}: {'cargado' if etiqueta(n) in lista else 'no cargado'}")
        return 0
    if cmd == "quitar" and len(argv) > 1 and argv[1] in SERVICIOS:
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{etiqueta(argv[1])}"], capture_output=True)
        (AGENTES / f"{etiqueta(argv[1])}.plist").unlink(missing_ok=True)
        print(f"{argv[1]}: quitado")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
