#!/bin/zsh
# Vigilante de Wi-Fi de la máquina principal (16-nov-2026). Ver infra/maquina/README.md.
# Corre cada minuto (LaunchAgent com.fabrica.vigilante-wifi). Si no hay internet
# de verdad (también detecta los portales con login, como «TeleCentro Wifi»),
# vuelve a conectar la iMac a la red buena.

RED_BUENA="${VIGILANTE_RED:-tuotroproyecto}"
INTERFAZ="${VIGILANTE_INTERFAZ:-$(networksetup -listallhardwareports | awk '/Wi-Fi/{getline; print $2}')}"
LOG="${VIGILANTE_LOG:-$HOME/Library/Logs/fabrica-vigilante-wifi.log}"
ESTADO="${VIGILANTE_ESTADO:-$HOME/Library/Logs/fabrica-vigilante-wifi.fallas}"

hay_internet() {
  # captive.apple.com devuelve «Success» sólo con internet real; un portal devuelve su página de login.
  curl -s --max-time 6 "${VIGILANTE_URL:-http://captive.apple.com/hotspot-detect.html}" | grep -q "Success"
}

anotar() { print -r -- "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"; }

if hay_internet; then
  [[ -f "$ESTADO" ]] && { anotar "internet de vuelta"; rm -f "$ESTADO"; }
  exit 0
fi

# Un bache de un minuto no alcanza: esperamos 2 fallas seguidas.
fallas=$(( $(cat "$ESTADO" 2>/dev/null || echo 0) + 1 ))
print $fallas > "$ESTADO"
anotar "sin internet (falla $fallas)"
(( fallas < 2 )) && exit 0

# Wi-Fi apagado: prenderlo.
if networksetup -getairportpower "$INTERFAZ" | grep -q "Off"; then
  anotar "Wi-Fi apagado, lo prendo"
  networksetup -setairportpower "$INTERFAZ" on
  sleep 8
fi

# Apagar y prender el Wi-Fi: macOS vuelve a la red conocida de mayor prioridad,
# que es tuotroproyecto (networksetup -setairportnetwork sin la clave falla con -3900).
anotar "reinicio el Wi-Fi para volver a $RED_BUENA"
networksetup -setairportpower "$INTERFAZ" off; sleep 3
networksetup -setairportpower "$INTERFAZ" on
for i in {1..10}; do
  sleep 3
  if hay_internet; then anotar "ok: internet de vuelta a los $((i*3))s"; rm -f "$ESTADO"; break; fi
done
hay_internet || anotar "sigue sin internet (¿se cayó tuotroproyecto?); reintento en el próximo minuto"

# Que el log no crezca para siempre.
[[ $(wc -l < "$LOG") -gt 2000 ]] && tail -n 1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exit 0
