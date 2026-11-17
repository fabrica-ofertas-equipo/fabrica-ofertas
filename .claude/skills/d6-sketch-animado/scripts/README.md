# scripts · d6-sketch-animado

Motor del sub-formato **sketch animado** de D6. Propietario: D6 (creativos). Lo invoca el Maker de D6 o el dueño, por nombre.

## Módulos
- `sketch.py` + `sketch` (lanzador con el `.venv` de la raíz): CLI por pasos.
- `sketchlib/kie.py`: cliente Kie.ai (subida, `createTask`, `recordInfo`, descarga, Suno, **registro previo de créditos** en `06-creativos/costos.jsonl`, `recuperar`).
- `sketchlib/voces.py`: Gemini TTS (voces preset de la biblioteca, por locale), `say` para el animatic y efectos de ElevenLabs.
- `sketchlib/pipeline.py`: personajes, escenarios, keyframes, voces, efectos, animar, montar (Remotion), recuperar, costo.
- `brief_desde_oferta.py`: arma `brief-sketch.json` desde la oferta (sale 3 si el gate de cumplimiento falla).
- `motor/`: proyecto Remotion (`Sketch`): cortes, cámara por plano, subtítulos con Whisper, música por secciones con ducking y cortes, viñeta, etiqueta IA y cierre con la marca de D5.

## CLI (desde la raíz del proyecto)
```bash
S=.claude/skills/d6-sketch-animado/scripts
.venv/bin/python $S/brief_desde_oferta.py --oferta OF-202611-01 --ad-name c01-hueco_vid_h1_v1
$S/sketch nuevo     ofertas/OF-202611-01/06-creativos/sketch/c01-hueco_vid_h1_v1
$S/sketch animatic  ofertas/OF-202611-01/06-creativos/sketch/c01-hueco_vid_h1_v1   # gratis
$S/sketch costo     <carpeta>
$S/sketch voces-google --filtro "spain female"
$S/sketch personajes <carpeta> --variantes 3 ; $S/sketch escenarios <carpeta> ; $S/sketch keyframes <carpeta>
$S/sketch voces <carpeta> ; $S/sketch efectos <carpeta> ; $S/sketch animar <carpeta> ; $S/sketch montar <carpeta>
$S/sketch recuperar <carpeta>          # tareas pagas que un corte de red dejó sin descargar
```
Códigos de salida: 0 ok · 2 falta entrada (brief) · 3 gate de cumplimiento (brief) · ≠0 error de la herramienta.

## Entradas y salidas
Lee la oferta aprobada (`03-oferta/oferta.json`, `mercado.json`, `05-landing/paleta.json` y `fonts/`) y `empresa/limites.yaml` (solo lectura). Escribe solo en `ofertas/<id>/06-creativos/` (`sketch/<ad_name>/`, `assets/<ad_name>.mp4`, `costos.jsonl`).

## Variables de entorno (`.env` de la raíz)
`KIE_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`.

## Cómo probar
`./instalar.sh` (verifica todo) y el animatic de `references/ejemplo-guion.yaml` sobre una copia de `ofertas/_ejemplo`. No gasta créditos.
