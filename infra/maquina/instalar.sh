#!/bin/zsh
# Instala (o reinstala) el vigilante de Wi-Fi como LaunchAgent. No pide contraseña.
# Uso: zsh infra/maquina/instalar.sh
set -e
AQUI="${0:A:h}"
PLIST="$HOME/Library/LaunchAgents/com.fabrica.vigilante-wifi.plist"
DOMINIO="gui/$(id -u)"

# La versión vieja (antes de vivir en el repo) se llamaba com.usuario.vigilante-wifi.
for viejo in com.usuario.vigilante-wifi com.fabrica.vigilante-wifi; do
  launchctl bootout "$DOMINIO/$viejo" 2>/dev/null || true
done
rm -f "$HOME/Library/LaunchAgents/com.usuario.vigilante-wifi.plist"

cp "$AQUI/com.fabrica.vigilante-wifi.plist" "$PLIST"
launchctl bootstrap "$DOMINIO" "$PLIST"
echo "vigilante instalado; estado:"
launchctl print "$DOMINIO/com.fabrica.vigilante-wifi" | grep -E "state =|run interval" | head -2
