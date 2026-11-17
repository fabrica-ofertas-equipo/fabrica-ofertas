#!/bin/zsh
# Abre la landing de una oferta en Chrome, sirviéndola en local (solo tu Mac, 127.0.0.1).
#
# Uso (desde la raíz del proyecto):
#   scripts/ver_landing.sh                      # OF-202611-91, versión de producción (sin demo)
#   scripts/ver_landing.sh OF-202611-91 vista-previa   # con reseñas de demostración rotuladas «DEMO»
#   scripts/ver_landing.sh OF-202611-91 produccion 8792 # otro puerto
#
# Para verla en español: en Chrome, ícono de traducir en la barra de direcciones (o clic derecho → Traducir a español).
# Para apagar el servidor: Ctrl-C en esta terminal (o `kill $(lsof -ti tcp:PUERTO)`).
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
OFERTA="${1:-OF-202611-91}"
VERSION="${2:-produccion}"
PUERTO="${3:-8791}"
case "$VERSION" in
  produccion|prod) CARPETA="sitio" ;;
  vista-previa|vp) CARPETA="sitio-vista-previa" ;;
  *) echo "Versión desconocida: $VERSION (usa produccion o vista-previa)"; exit 2 ;;
esac
DIR="$RAIZ/ofertas/$OFERTA/05-landing/$CARPETA"
if [ ! -d "$DIR" ]; then
  echo "No existe $DIR. Genera la landing primero (landing.generar, y --vista-previa para la otra versión)."
  exit 3
fi
if lsof -ti "tcp:$PUERTO" >/dev/null 2>&1; then
  echo "El puerto $PUERTO ya está en uso: apago ese servidor y sirvo $CARPETA."
  kill $(lsof -ti "tcp:$PUERTO") 2>/dev/null || true
  sleep 1
fi
echo "Sirviendo $DIR en http://127.0.0.1:$PUERTO/  (Ctrl-C para apagar)"
( sleep 1; open -a "Google Chrome" "http://127.0.0.1:$PUERTO/" 2>/dev/null || open "http://127.0.0.1:$PUERTO/" ) &
cd "$DIR" && exec python3 -m http.server "$PUERTO" --bind 127.0.0.1
