# 7 · Claves de IA

Las tres van en `.env`. Para cada una: abrile la página, la persona crea la cuenta, carga saldo si hace falta y copia la clave; vos le abrís `.env` (`open -a TextEdit .env`), ella pega después del `=` de la línea correspondiente y guarda. Que no la pegue en el chat.

| Clave | Para qué | Dónde se saca |
|---|---|---|
| `KIE_API_KEY` | imágenes de la landing y de los anuncios, videos | https://kie.ai/api-key (necesita créditos) |
| `GEMINI_API_KEY` | todas las voces de los videos (regla: siempre Gemini TTS) e imágenes | https://aistudio.google.com/apikey (activar facturación en Google Cloud para no quedar en el límite gratis) |
| `ELEVENLABS_API_KEY` | efectos de sonido de los videos (opcional) | https://elevenlabs.io/app/settings/api-keys (plan con licencia comercial) |

Comprobá que estén cargadas con `estado_instalacion.py` (✓ en `env:KIE_API_KEY` y `env:GEMINI_API_KEY`) y que funcionen con una llamada mínima desde la terminal que lea la clave del `.env` sin imprimirla (por ejemplo, listar modelos de Gemini o pedir el saldo de Kie). Si una falla, decí cuál y qué respondió el servicio, sin mostrar la clave.
