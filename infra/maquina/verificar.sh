#!/bin/zsh
# Chequeo de la máquina principal: ¿se puede dejar sola y manejar desde afuera?
# Sólo lee, no cambia nada. Uso: zsh infra/maquina/verificar.sh
RED_BUENA="${VIGILANTE_RED:-tuotroproyecto}"
WIFI=$(networksetup -listallhardwareports | awk '/Wi-Fi/{getline; print $2}')
TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
mal=0
si()  { print "  OK    $1"; }
no()  { print "  FALTA $1"; mal=$((mal+1)); }

print "Máquina principal — $(scutil --get ComputerName)"

curl -s --max-time 6 http://captive.apple.com/hotspot-detect.html | grep -q Success \
  && si "internet de verdad (no un portal con login)" || no "sin internet"

if [[ -x $TS ]]; then
  linea=$($TS status 2>&1 | head -1)
  [[ $linea == 100.* ]] && si "Tailscale conectado: $(print $linea | awk '{print $2, $1}')" \
                        || no "Tailscale sin sesión ($linea)"
else
  no "Tailscale no instalado (App Store)"
fi

nc -z -G 2 127.0.0.1 5900 >/dev/null 2>&1 && si "Compartir pantalla activo" || no "Compartir pantalla apagado"
nc -z -G 2 127.0.0.1 22   >/dev/null 2>&1 && si "Sesión remota (SSH) activa" || no "Sesión remota (SSH) apagada"

[[ $(pmset -g | awk '$1=="sleep"{print $2}') == 0 ]] && si "nunca entra en reposo" || no "entra en reposo"
fdesetup status | grep -q "Off" && si "FileVault apagado (vuelve sin estar ahí)" \
                                || no "FileVault activo: tras un reinicio hay que poner la clave en la máquina"

[[ $(defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser 2>/dev/null) == "$USER" ]] \
  && si "inicia sesión sola después de un reinicio" || no "no inicia sesión sola (Usuarios y grupos → Iniciar sesión automáticamente)"
sysadminctl -screenLock status 2>&1 | grep -q "screenLock is off" \
  && si "pantalla sin bloqueo con contraseña" || no "la pantalla se bloquea con contraseña"
[[ $(defaults read /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates 2>/dev/null) == 0 ]] \
  && si "macOS no se actualiza (ni reinicia) solo" || no "macOS puede actualizarse y reiniciarse solo"
osascript -e 'tell application "System Events" to get the name of every login item' 2>/dev/null | grep -q Tailscale \
  && si "Tailscale arranca solo al iniciar sesión" || no "Tailscale no arranca solo (agregalo a Ítems de inicio)"

redes=$(networksetup -listpreferredwirelessnetworks "$WIFI" 2>/dev/null | sed 1d | sed 's/^[[:space:]]*//')
[[ $(print -r -- "$redes" | head -1) == "$RED_BUENA" ]] && si "«$RED_BUENA» es la primera red Wi-Fi" \
                                                       || no "«$RED_BUENA» no es la primera red Wi-Fi"
publicas=$(print -r -- "$redes" | grep -iE "^(TeleCentro Wifi|Personal Wifi Zone|Fibertel Zone|Claro Wifi|Movistar Wifi)$")
[[ -z $publicas ]] && si "sin redes públicas con login guardadas" \
                   || no "redes públicas guardadas: $(print -r -- $publicas | tr '\n' ',')"

if launchctl print "gui/$(id -u)/com.fabrica.vigilante-wifi" >/dev/null 2>&1; then
  si "vigilante de Wi-Fi activo"
else
  no "vigilante de Wi-Fi no instalado (zsh infra/maquina/instalar.sh)"
fi
print "  últimas acciones del vigilante:"
tail -3 "$HOME/Library/Logs/fabrica-vigilante-wifi.log" 2>/dev/null | sed 's/^/    /' || print "    (ninguna)"

print
(( mal == 0 )) && print "Todo en orden." || print "$mal cosa(s) para revisar."
exit $mal
