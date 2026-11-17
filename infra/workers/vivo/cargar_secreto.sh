#!/bin/zsh
# Carga un secreto en la nube (worker «fabrica-vivo») SIN pegarlo a ciegas y sin confundirlo con el comando copiado.
# Uso: infra/workers/vivo/cargar_secreto.sh IMPULTIENDA_WEBHOOK_SECRET | META_ACCESS_TOKEN
# El valor lo copia el dueño DESPUÉS de correr esto; el script lo toma del portapapeles, comprueba que no sea un comando,
# lo sube con wrangler y vacía el portapapeles. Nunca lo imprime (solo el largo y los primeros 4 caracteres).
set -euo pipefail
cd "$(dirname "$0")"
NOMBRE="${1:?falta el nombre del secreto}"
echo ""
echo "  1) Copiá ahora el valor de $NOMBRE (el botón «Copiar» de la página)."
echo "  2) Volvé acá y apretá Enter."
read -r _
V="$(pbpaste)"
V="${V//$'\n'/}"
if [[ -z "$V" || "$V" == cd* || "$V" == *wrangler* || "$V" == *" "* ]]; then
  echo "✘ Lo que hay en el portapapeles no parece la clave (está vacío o es un comando). Copiá la clave y corré esto de nuevo."
  exit 1
fi
echo "· voy a cargar un valor de ${#V} caracteres que empieza con ${V[1,4]}…"
printf '%s' "$V" | npx --yes wrangler@4 secret put "$NOMBRE"
printf '' | pbcopy
echo "· listo; vacié el portapapeles."
