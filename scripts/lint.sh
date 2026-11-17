#!/usr/bin/env bash
# Comprobación de sintaxis: compileall de Python y node --check de los .mjs.
# Código de salida: 0 si todo compila; 1 si algo falla.
# Uso: bash scripts/lint.sh
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"
cd "$RAIZ"
[ -n "${PY:-}" ] || { echo "ERROR: falta python3" >&2; exit 1; }

fallos=0

echo "== Python: compileall"
# El bytecode va a un directorio temporal: lint no deja __pycache__ en el repositorio.
PYTHONPYCACHEPREFIX="$(mktemp -d)"
export PYTHONPYCACHEPREFIX
trap 'rm -rf "$PYTHONPYCACHEPREFIX"' EXIT
for d in engine decision datos meta compliance postcompra landing dashboard agentes infra contratos scripts tests tracking; do
  [ -d "$d" ] || continue
  "$PY" -m compileall -q "$d" || fallos=$((fallos + 1))
done

echo "== Node: node --check"
n=0
while IFS= read -r -d '' archivo; do
  n=$((n + 1))
  node --check "$archivo" || { echo "ERROR de sintaxis: $archivo" >&2; fallos=$((fallos + 1)); }
done < <(buscar_archivos '*.mjs')
echo "$n archivo(s) .mjs revisados"

if [ "$fallos" -eq 0 ]; then
  echo "LINT OK"
  exit 0
fi
echo "LINT FALLÓ ($fallos error(es))" >&2
exit 1
