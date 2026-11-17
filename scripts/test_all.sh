#!/usr/bin/env bash
# Corre todas las pruebas: unittest, pytest (si está) y node --test por carpeta con pruebas de Node.
# Código de salida: 0 si todo pasa; 1 si algo falla.
# Uso: bash scripts/test_all.sh
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"
cd "$RAIZ"
[ -n "${PY:-}" ] || { echo "ERROR: falta python3 (ejecutar scripts/bootstrap.sh)" >&2; exit 1; }

fallos=0
paso() { echo; echo "== $1"; }

paso "Python: unittest discover"
"$PY" -m unittest discover -s tests -t . || fallos=$((fallos + 1))

paso "Python: pytest"
if "$PY" -c "import pytest" 2>/dev/null; then
  "$PY" -m pytest || fallos=$((fallos + 1))
else
  echo "pytest no está instalado: se omite (ejecutar scripts/bootstrap.sh)"
fi

paso "Node: node --test por carpeta"
if command -v node >/dev/null; then
  # Cada carpeta <x>/test con *.test.mjs se prueba por separado, desde <x>.
  carpetas=()
  while IFS= read -r -d '' archivo; do
    carpetas+=("$(dirname "$(dirname "$archivo")")")
  done < <(buscar_archivos '*.test.mjs')
  if [ "${#carpetas[@]}" -eq 0 ]; then
    echo "no hay pruebas de Node"
  else
    while IFS= read -r carpeta; do
      echo "-- $carpeta"
      ( cd "$carpeta" && node --test test/*.test.mjs ) || fallos=$((fallos + 1))
    done < <(printf '%s\n' "${carpetas[@]}" | sort -u)
  fi
else
  echo "node no está instalado: se omite"
  fallos=$((fallos + 1))
fi

echo
if [ "$fallos" -eq 0 ]; then
  echo "TODO OK"
  exit 0
fi
echo "FALLARON $fallos grupo(s) de pruebas" >&2
exit 1
