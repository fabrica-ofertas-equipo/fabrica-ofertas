#!/bin/zsh
# Instala y verifica las dependencias de la skill d6-sketch-animado (sin sudo ni nada global).
# Uso: .claude/skills/d6-sketch-animado/scripts/instalar.sh   (desde la raíz del proyecto)
set -u
DIR="${0:A:h}"; REPO="${DIR:h:h:h:h}"; ok=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "  VERDE  $1"; else echo "  ROJO   $1 — $3"; ok=1; fi; }
echo "d6-sketch-animado · verificación"
chk "ffmpeg/ffprobe" "command -v ffmpeg && command -v ffprobe" "brew install ffmpeg"
chk "whisper-cli" "command -v whisper-cli" "brew install whisper-cpp"
chk "modelo Whisper large-v3-turbo" "test -f $HOME/.cache/whisper/ggml-large-v3-turbo.bin" "descargar ggml-large-v3-turbo.bin a ~/.cache/whisper/"
chk "Node ≥ 20" "node -e 'process.exit(parseInt(process.versions.node)>=20?0:1)'" "instalar Node 20+"
chk ".venv de la raíz (Python 3.15)" "test -x '$REPO/.venv/bin/python'" "scripts/bootstrap.sh"
"$REPO/.venv/bin/pip" install -q -r "$DIR/requirements-extra.txt" && echo "  VERDE  requirements-extra.txt instalado en .venv"
( cd "$DIR/motor" && npm install --no-audit --no-fund >/dev/null 2>&1 ) && echo "  VERDE  motor Remotion (npm install)" || { echo "  ROJO   npm install del motor"; ok=1; }
for k in KIE_API_KEY GEMINI_API_KEY ELEVENLABS_API_KEY; do
  chk "$k en .env" "grep -q '^$k=.' '$REPO/.env'" "agregarla al .env de la raíz (ver .env.example)"
done
exit $ok
