#!/bin/zsh
# Monta la capa en la nube del panel (dueño, 2026-11-14, opción 2). Se puede correr de nuevo sin romper nada (idempotente).
#
# Requisitos (los hace el dueño una vez):
#   1. npx wrangler login            → autoriza Cloudflare en el navegador
#   2. cloudflared tunnel login      → elige el dominio tu-dominio.com
#   3. después de montar: los dos secretos que solo él tiene (ver al final)
#
# Qué hace:
#   - base D1 «fabrica-vivo» + tablas (schema.sql)
#   - clave de lectura del panel: la genera si no existe (~/.config/fabrica-panel/vivo_lectura, permisos 600) y la carga como secreto
#   - publica el worker en vivo.tu-dominio.com (cron cada 5 min)
#   - túnel «fabrica-panel» hacia el panel (127.0.0.1:8790) en panel.tu-dominio.com, como agente de inicio com.fabrica.tunel
#   - agente de inicio com.fabrica.nube-sync (cada 5 min trae la nube al libro)
# El túnel se conecta al DNS SOLO con --publicar-panel, después de crear la regla de Cloudflare Access (login con Google).
set -euo pipefail
cd "$(dirname "$0")"
RAIZ="$(cd ../../.. && pwd)"
CONF="$HOME/.config/fabrica-panel"; mkdir -p "$CONF"; chmod 700 "$CONF"
W=(npx --yes wrangler@4)

echo "· cuenta de Cloudflare"; "${W[@]}" whoami | grep -i -E "logged in|account" | head -3

echo "· base D1"
if ! grep -q 'database_id = "[0-9a-f-]\{36\}"' wrangler.toml; then
  ID=$("${W[@]}" d1 list --json | python3 -c 'import json,sys; print(next((d["uuid"] for d in json.load(sys.stdin) if d["name"]=="fabrica-vivo"), ""))')
  [[ -z "$ID" ]] && ID=$("${W[@]}" d1 create fabrica-vivo | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
  sed -i '' "s/database_id = \".*\"/database_id = \"$ID\"/" wrangler.toml
fi
"${W[@]}" d1 execute fabrica-vivo --remote --file schema.sql --yes >/dev/null

echo "· clave de lectura del panel"
if [[ ! -s "$CONF/vivo_lectura" ]]; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$CONF/vivo_lectura"; chmod 600 "$CONF/vivo_lectura"
  tr -d '\n' < "$CONF/vivo_lectura" | "${W[@]}" secret put LECTURA_TOKEN >/dev/null
fi

echo "· publicar el worker"
# Sin subdominio workers.dev la cuenta no acepta el cron (código 10063): se avisa y se sigue; se arregla abriendo Workers una vez.
"${W[@]}" deploy 2>&1 | grep -E "Deployed|vivo.tu-dominio.com|10063" | head -5 || true

echo "· túnel"
if ! cloudflared tunnel list -o json | python3 -c 'import json,sys; sys.exit(0 if any(t["name"]=="fabrica-panel" for t in (json.load(sys.stdin) or [])) else 1)'; then
  cloudflared tunnel create fabrica-panel >/dev/null
fi
TID=$(cloudflared tunnel list -o json | python3 -c 'import json,sys; print(next(t["id"] for t in (json.load(sys.stdin) or []) if t["name"]=="fabrica-panel"))')
cat > "$HOME/.cloudflared/fabrica-panel.yml" <<EOF
tunnel: $TID
credentials-file: $HOME/.cloudflared/$TID.json
ingress:
  - hostname: panel.tu-dominio.com
    service: http://127.0.0.1:8790
  - service: http_status:404
EOF

plist() {  # $1 etiqueta, $2… argumentos; agentes de inicio del usuario (sin sudo), se levantan solos si se caen
  local P="$HOME/Library/LaunchAgents/$1.plist"; shift
  { echo '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict>'
    echo "<key>Label</key><string>$(basename "$P" .plist)</string><key>ProgramArguments</key><array>"
    for a in "$@"; do echo "<string>$a</string>"; done
    echo "</array><key>WorkingDirectory</key><string>$RAIZ</string><key>RunAtLoad</key><true/>"
    echo "$EXTRA<key>StandardOutPath</key><string>$HOME/Library/Logs/$(basename "$P" .plist).log</string><key>StandardErrorPath</key><string>$HOME/Library/Logs/$(basename "$P" .plist).log</string></dict></plist>"
  } > "$P"
  launchctl bootout "gui/$(id -u)/$(basename "$P" .plist)" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$P"
}
EXTRA='<key>KeepAlive</key><true/>' plist com.fabrica.tunel "$(command -v cloudflared)" tunnel --config "$HOME/.cloudflared/fabrica-panel.yml" run fabrica-panel
EXTRA='<key>StartInterval</key><integer>300</integer>' plist com.fabrica.nube-sync "$RAIZ/.venv/bin/python" "$RAIZ/.claude/skills/escalar-oferta/scripts/nube_sync.py"

if [[ "${1:-}" == "--publicar-panel" ]]; then
  echo "· DNS panel.tu-dominio.com → túnel (la regla de Access tiene que existir antes)"
  cloudflared tunnel route dns fabrica-panel panel.tu-dominio.com
fi

echo "· salud"; curl -s https://vivo.tu-dominio.com/salud; echo
cat <<'EOF'

Faltan los dos secretos que solo tenés vos (se pegan en la terminal; nadie más los ve):
  cd "infra/workers/vivo" && npx wrangler secret put META_ACCESS_TOKEN
  cd "infra/workers/vivo" && npx wrangler secret put IMPULTIENDA_WEBHOOK_SECRET
EOF
