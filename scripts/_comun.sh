# Funciones comunes de los comandos de scripts/ (se carga con "source"; no se ejecuta solo).
# Define RAIZ y PY: el intérprete de .venv si existe, si no python3.

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -x "$RAIZ/.venv/bin/python" ]; then
  PY="$RAIZ/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi

# Lista (separada por NUL) los archivos que coinciden con un patrón, sin .venv ni node_modules.
buscar_archivos() {
  find "$RAIZ" \( -name .venv -o -name node_modules -o -name .git -o -name .wrangler -o -name dist \) -prune \
    -o -type f -name "$1" -print0
}
