# 1 · Herramientas de la Mac

Comprobá primero qué hay: `python3 .claude/skills/instalar-fabrica/scripts/estado_instalacion.py` (si el proyecto todavía no está bajado, usá `which brew git gh node ffmpeg python3` y `ls "/Applications/Google Chrome.app"`).

1. **Homebrew** (si falta). Es el instalador de programas de la Mac. Pide la contraseña de la Mac, así que lo corre la persona en su terminal; dale el comando en un bloque para copiar:
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
   Al terminar, Homebrew muestra dos líneas «Next steps» para agregarlo al PATH: que las copie y las corra también. Comprobá con `brew --version`.
2. **El resto, de una:** `brew install git gh node python@3.13 ffmpeg` (lo podés correr vos; tarda unos minutos).
3. **Google Chrome** (lo usan los PDF y el panel): si falta, `brew install --cask google-chrome`.
4. **Opcional:** `brew install whisper-cpp` (transcribe los videos del referente; sin esto se transcribe con otra vía más lenta).

Hecho cuando el script de estado marca ✓ en homebrew, git, gh, node, ffmpeg y google-chrome.
