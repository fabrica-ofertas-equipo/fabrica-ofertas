#!/bin/zsh
# Respaldo automático en git + GitHub privado (dueño, 15-nov: «Sí, armalo»). Lo corre el agente de inicio com.fabrica.respaldo
# cada hora; no usa Claude. Qué hace:
#   1. copia las tareas programadas y la memoria de Claude dentro del proyecto (infra/respaldo/), para que también queden respaldadas;
#   2. git add -A (el .gitignore deja afuera claves, entornos y medios pesados de las ofertas);
#   3. saca del commit todo archivo de más de 20 MB (GitHub no acepta > 100 MB) y lo anota en .git/info/exclude;
#   4. FRENA si algún valor del .env aparece en lo que se va a subir (no commitea nada y lo anota en el registro);
#   5. commit «Respaldo automático <fecha>» y push a origin.
# Registro: ~/Library/Logs/fabrica-respaldo.log. Sale 0 si respaldó o no había cambios; 3 si frenó por un secreto; 4 si falló el push.
set -u
RAIZ="<carpeta del proyecto>"
cd "$RAIZ" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
ahora() { date "+%Y-%m-%d %H:%M"; }

# 1. copias de lo que vive fuera del proyecto
mkdir -p infra/respaldo/tareas-programadas infra/respaldo/memoria
rsync -a --delete --include='*/' --include='SKILL.md' --exclude='*' "$HOME/.claude/scheduled-tasks/" infra/respaldo/tareas-programadas/ 2>/dev/null
rsync -a --delete "$HOME/.claude/projects/-Users-usuario-Digital-Products/memory/" infra/respaldo/memoria/ 2>/dev/null
for f in "$HOME"/Library/LaunchAgents/com.fabrica.*.plist; do [ -f "$f" ] && cp "$f" infra/respaldo/ 2>/dev/null; done

# 2. preparar
git add -A >/dev/null 2>&1
if git diff --cached --quiet; then echo "$(ahora) sin cambios"; exit 0; fi

# 3. archivos grandes fuera
git diff --cached --name-only --diff-filter=AM -z | while IFS= read -r -d '' p; do
  [ -f "$p" ] || continue
  t=$(wc -c < "$p" 2>/dev/null | tr -d " "); t=${t:-0}
  if [ "$t" -gt 20000000 ]; then
    git rm --cached -q -- "$p"
    printf '%s\n' "/$p" >> .git/info/exclude
    echo "$(ahora) fuera por tamaño ($((t / 1000000)) MB): $p"
  fi
done
if git diff --cached --quiet; then echo "$(ahora) sin cambios (solo archivos grandes)"; exit 0; fi

# 4. ningún valor del .env puede subirse
if [ -f .env ]; then
  while IFS= read -r linea; do
    v="${linea#*=}"; v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
    [ ${#v} -ge 16 ] || continue
    if git grep --cached -q -F -e "$v" 2>/dev/null; then
      archivo=$(git grep --cached -l -F -e "$v" 2>/dev/null | head -1)
      git reset -q
      echo "$(ahora) FRENADO: un valor del .env aparece en $archivo; no se subió nada"
      exit 3
    fi
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env)
fi

# 5. commit y push
n=$(git diff --cached --name-only | wc -l | tr -d ' ')
git -c user.name="Fábrica (respaldo automático)" -c user.email="respaldo@fabrica.local" commit -q -m "Respaldo automático $(ahora) · $n archivos" || { echo "$(ahora) falló el commit"; exit 1; }
if git push -q origin HEAD 2>&1; then echo "$(ahora) respaldado: $n archivos"; else echo "$(ahora) commit local hecho, falló el push"; exit 4; fi
