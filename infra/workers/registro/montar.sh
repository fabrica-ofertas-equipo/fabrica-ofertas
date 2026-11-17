#!/bin/zsh
# Monta el registro compartido de ofertas tomadas (worker «fabrica-registro»). Idempotente.
#
#   DOMINIO=tu-dominio.com ./montar.sh            crea la base, aplica el esquema y publica en registro.<DOMINIO>
#   ./montar.sh alta <id-instalacion>             da de alta una instalación e imprime su token UNA vez
#   ./montar.sh baja <id-instalacion>             la desactiva (sus reservas siguen hasta vencer)
#
# Lo monta SOLO la instalación principal (la que es dueña del dominio). Las demás reciben su token y la URL.
# Requisito: npx wrangler login (una vez).
set -euo pipefail
cd "$(dirname "$0")"
W=(npx --yes wrangler@4)
CONF="$HOME/.config/fabrica"; mkdir -p "$CONF"; chmod 700 "$CONF"

if [[ "${1:-}" == "alta" ]]; then
  ID="${2:?falta el id de la instalación (p. ej. socia-1)}"
  [[ "$ID" =~ ^[a-z0-9-]{3,40}$ ]] || { echo "id inválido: minúsculas, números y guiones"; exit 1; }
  TOK=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
  HASH=$(printf '%s' "$TOK" | shasum -a 256 | cut -d' ' -f1)
  "${W[@]}" d1 execute fabrica-registro --remote --yes --command \
    "INSERT INTO instalaciones (token_hash, id, alta) VALUES ('$HASH', '$ID', datetime('now')) ON CONFLICT(id) DO UPDATE SET token_hash=excluded.token_hash, activa=1" >/dev/null
  echo "Instalación «$ID» dada de alta. Token (se muestra una sola vez; pasáselo por un canal privado):"
  echo "$TOK"
  exit 0
fi
if [[ "${1:-}" == "baja" ]]; then
  ID="${2:?falta el id}"; [[ "$ID" =~ ^[a-z0-9-]{3,40}$ ]] || exit 1
  "${W[@]}" d1 execute fabrica-registro --remote --yes --command "UPDATE instalaciones SET activa=0 WHERE id='$ID'" >/dev/null
  echo "Instalación «$ID» desactivada."; exit 0
fi

: "${DOMINIO:?poné DOMINIO=tu-dominio.com antes del comando}"
echo "· cuenta de Cloudflare"; "${W[@]}" whoami | grep -i -E "logged in|account" | head -3
echo "· base D1"
if ! grep -q 'database_id = "[0-9a-f-]\{36\}"' wrangler.toml; then
  ID=$("${W[@]}" d1 list --json | python3 -c 'import json,sys; print(next((d["uuid"] for d in json.load(sys.stdin) if d["name"]=="fabrica-registro"), ""))')
  [[ -z "$ID" ]] && ID=$("${W[@]}" d1 create fabrica-registro | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
  sed -i '' "s/database_id = \".*\"/database_id = \"$ID\"/" wrangler.toml
fi
sed -i '' "s/^pattern = \"registro\..*\"/pattern = \"registro.$DOMINIO\"/" wrangler.toml
"${W[@]}" d1 execute fabrica-registro --remote --file schema.sql --yes >/dev/null
echo "· publicar"; "${W[@]}" deploy 2>&1 | grep -E "Deployed|registro\." | head -3 || true
echo "· salud"; sleep 3; curl -s "https://registro.$DOMINIO/salud"; echo
if [[ ! -s "$CONF/registro_token" ]]; then
  echo "· token de esta instalación (principal)"
  "$0" alta principal | tail -1 > "$CONF/registro_token"; chmod 600 "$CONF/registro_token"
fi
echo "Listo. Esta instalación usa ~/.config/fabrica/registro_token; registro_url = https://registro.$DOMINIO"
