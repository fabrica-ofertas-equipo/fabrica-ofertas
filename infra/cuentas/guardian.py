#!/usr/bin/env python3
"""Guardián de la vigilancia, FUERA de Claude (agente com.fabrica.guardian, cada 10 min).

Problema (16-nov): los avisos al celular los manda Claude. Si la cuenta de Claude se queda sin uso, la app
se cierra o la Mac se traba, la vigilancia deja de correr y nadie avisa: las campañas siguen gastando sin corte.

Este script no usa Claude. Mira el latido de vigilancia-ofertas (ofertas/_funnels/latidos.json, lo deja cada
vuelta cada 15 min) y, si hace más de UMBRAL_MIN que no late, avisa con una notificación de macOS con sonido, un iMessage al dueño (guardian.json) y
lo registra en avisos.jsonl (el panel lo muestra). No repite el aviso dentro de 3 h (ventana de urgentes de avisos.py).

Uso: python3 infra/cuentas/guardian.py [--probar]   (--probar manda la notificación sin mirar el latido)
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LATIDOS = RAIZ / "ofertas" / "_funnels" / "latidos.json"
AVISOS = RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts" / "avisos.py"
LOG = Path(__file__).resolve().parent / "guardian.log"
CONFIG = Path(__file__).resolve().parent / "guardian.json"  # {"imessage": "+54911… o correo de Apple ID"}
TAREA = "vigilancia-ofertas"
UMBRAL_MIN = 75  # corre cada 15 min; una vuelta completa larga puede tardar ~50 min en dejar el latido


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def app_abierta():
    # ps y no pgrep: pgrep no ve a sus procesos padre (desde una sesión de Claude daría «cerrada»)
    salida = subprocess.run(["ps", "-axo", "args"], capture_output=True, text=True).stdout
    return any(l.strip() == "/Applications/Claude.app/Contents/MacOS/Claude" for l in salida.splitlines())


def notificar(titulo, mensaje):
    m = mensaje.replace('"', "'")
    t = titulo.replace('"', "'")
    subprocess.run(["osascript", "-e", f'display notification "{m}" with title "{t}" sound name "Sosumi"'],
                   capture_output=True)


def imessage(mensaje):
    """Manda el aviso por iMessage al dueño (a su propio número o Apple ID). Devuelve True si salió."""
    try:
        destino = json.loads(CONFIG.read_text()).get("imessage", "").strip()
    except (OSError, ValueError):
        destino = ""
    if not destino:
        return False
    m = mensaje.replace("\\", "").replace('"', "'")
    script = ('tell application "Messages"\n'
              '  set s to 1st account whose service type = iMessage\n'
              f'  send "{m}" to participant "{destino}" of s\n'
              'end tell')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"iMessage no salió: {r.stderr.strip()}")
    return r.returncode == 0


def red_wifi():
    """Nombre de la red Wi-Fi actual ('' si no se sabe)."""
    r = subprocess.run(["ipconfig", "getsummary", "en0"], capture_output=True, text=True)
    for linea in r.stdout.splitlines():
        if linea.strip().startswith("SSID :"):
            return linea.split(":", 1)[1].strip()
    return ""


def hay_internet():
    """True si se llega a internet de verdad. Una red pública con portal (TeleCentro Wifi, 17-nov) «conecta» pero
    devuelve su página de login en vez de «Success»: eso cuenta como sin internet."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://captive.apple.com/hotspot-detect.html", timeout=8) as r:
            return b"Success" in r.read(2000)
    except Exception:
        return False


def texto_aviso(minutos, abierta, internet=True, red=""):
    """El aviso con los pasos mínimos para arreglarlo: primero la red (la caída del 17-nov fue un Wi-Fi público
    sin internet y el aviso culpaba a la cuenta de Claude), después si la app de Claude está abierta o no."""
    cab = (f"⚠️ Fábrica: la vigilancia no corre hace {minutos} min. "
           "Las campañas siguen gastando sin el corte.\n\n")
    if not internet:
        return cab + (f"Causa: la Mac está SIN INTERNET (red: {red or 'desconocida'}). No es la cuenta de Claude.\n\n"
                      "Qué hacer: conectá la Mac a la red tuotroproyecto (o cable). El vigilante de Wi-Fi lo reintenta solo cada "
                      "minuto; si sigue así, la red de casa está caída. Al volver internet, las tareas arrancan solas.")
    if abierta:
        return cab + ("Lo más probable: la cuenta de Claude se quedó sin uso.\n\n"
                      "Qué hacer en la Mac:\n"
                      "1. Abrí Claude y fijate si dice que llegaste al límite.\n"
                      "2. Si dice límite: tocá tu nombre abajo a la izquierda → Cerrar sesión → entrá con la otra cuenta.\n"
                      "3. Cerrá Claude con Cmd+Q y volvé a abrirlo.\n"
                      "Si no dice límite, hacé solo el paso 3.\n\n"
                      "Las tareas ya están copiadas en las dos cuentas: en 15 min vuelve a correr sola.")
    return cab + ("La app de Claude está cerrada.\n\n"
                  "Qué hacer: abrí Claude en la Mac. En 15 min la vigilancia vuelve a correr sola.")


def main():
    if "--probar" in sys.argv:
        notificar("Fábrica: prueba del guardián", "Si ves esto, el guardián puede avisarte.")
        print("prueba enviada; iMessage:", "salió" if imessage("Fábrica: prueba del guardián. Si te llega, el aviso de vigilancia parada te va a llegar al celular.") else "no salió (ver guardian.log o guardian.json)")
        return 0
    try:
        lat = json.loads(LATIDOS.read_text())[TAREA]
        ultimo = dt.datetime.fromisoformat(lat.get("ultimo_ok") or lat["ultimo"])
    except (OSError, ValueError, KeyError) as e:
        log(f"no pude leer el latido: {e}")
        return 0
    ahora = dt.datetime.now(dt.timezone.utc)
    minutos = int((ahora - ultimo).total_seconds() // 60)
    if minutos <= UMBRAL_MIN:
        return 0
    internet = hay_internet()
    red = red_wifi()
    if not internet:
        log(f"sin internet (red: {red or '?'}) hace {minutos} min sin vigilancia")
    texto = texto_aviso(minutos, app_abierta(), internet, red)
    mensaje = texto.replace("\n", " ")
    r = subprocess.run([sys.executable, str(AVISOS), "avisar", "guardian-vigilancia-parada", "--mensaje", mensaje,
                        "--urgente"], capture_output=True, text=True, cwd=RAIZ)
    if "ENVIAR" in r.stdout:
        notificar("Fábrica: vigilancia parada", mensaje)
        cel = imessage(texto)
        log(f"AVISO enviado (iMessage {'ok' if cel else 'no'}): {mensaje}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
