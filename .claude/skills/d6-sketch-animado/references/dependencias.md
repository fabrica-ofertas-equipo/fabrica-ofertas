# Dependencias (lo que la skill necesita y aún no existe en código del sistema)

| Qué | Estado |
|---|---|
| `subformato` en `matriz.json` y `creativos.schema.json` | [PENDIENTE: CT] |
| Hook de gasto (`agentes/hooks/pretooluse_gasto.py`) para llamadas HTTP a Kie (hoy controla herramientas de conectores) | [PENDIENTE: S-B] — la skill escribe la línea previa en `costos.jsonl` por su cuenta |
| OCR de fotogramas (`scripts.creativos.ocr_check`) para el texto inventado de Kling | sin motor OCR instalado: revisión visual del QA con la hoja de frames |
| Herramientas locales: `ffmpeg`/`ffprobe`, `whisper-cli` + `~/.cache/whisper/ggml-large-v3-turbo.bin`, Node ≥ 20, `say` (macOS, solo para el animatic) | verificadas por `scripts/instalar.sh` |
| Python: `requests` | `scripts/requirements-extra.txt` (instalado en `.venv`) |
| Remotion 4.0.532 | `scripts/motor/` (`npm install` en `instalar.sh`; `node_modules` ignorado) |
