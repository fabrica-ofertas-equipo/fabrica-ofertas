#!/usr/bin/env bash
# Crea .venv, instala dependencias y verifica el entorno. Idempotente.
# Uso: bash scripts/bootstrap.sh
# No usa sudo ni instala nada global: todo queda dentro de .venv.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"
cd "$RAIZ"

command -v python3 >/dev/null || { echo "ERROR: falta python3" >&2; exit 1; }
command -v node >/dev/null || { echo "ERROR: falta node" >&2; exit 1; }

if [ ! -x .venv/bin/python ]; then
  echo "== Creando .venv"
  python3 -m venv .venv
fi
PY="$RAIZ/.venv/bin/python"

echo "== Instalando dependencias (requirements-dev.txt incluye requirements.txt)"
"$PY" -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt

# Dependencias extra declaradas por cada componente (nunca se editan las de la raíz).
for extra in */requirements-extra.txt tracking/workers/*/requirements-extra.txt; do
  [ -f "$extra" ] || continue
  echo "== Instalando extras de $extra"
  "$PY" -m pip install --quiet --disable-pip-version-check -r "$extra"
done

echo "== Verificando"
"$PY" - <<'PYEOF'
import importlib.metadata as md
import sys
import jsonschema, pytest, yaml  # noqa: F401  (falla si no se instalaron)
print("python", sys.version.split()[0])
for paquete in ("PyYAML", "jsonschema", "pytest"):
    print(paquete, md.version(paquete))
PYEOF
echo "node $(node --version)"
echo "OK: entorno listo. Siguiente: bash scripts/test_all.sh"
