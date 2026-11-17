# Producción: modelos, QA visual, costos y fallas conocidas

## 1. Modelos (Kie.ai; IDs leídos de docs.kie.ai el 2026-11-06)

| Paso | Modelo | Nota |
|---|---|---|
| Hojas de personaje, set, keyframes | `nano-banana-pro` (hasta 8 referencias, 2K, 9:16) | 18 créditos por imagen |
| Planos con diálogo | `kling/ai-avatar-pro` (imagen + audio → lip-sync 1080p) | ~22 créditos por segundo de audio; mínimo 1,2 s de audio (la skill rellena con silencio) |
| Planos de acción | `kling-3.0/video` (primer frame, sin sonido, `std`) | puede animar al revés: invertir el clip (`ffmpeg reverse`) es válido |
| Música | `ai-music-api/generate` (Suno V6, instrumental, `duration`) | 2 variantes por pedido; elegir por energía y sin voces (Whisper) |
| Voces | Gemini `gemini-3.8-flash-tts` (Interactions API) | `voices` con filtro por país; `[estilo]` al inicio de la línea = *style*, `<sigh>` en la frase = sonido |
| Efectos | ElevenLabs `sound-generation` | duración exacta; normalizar el pico a −3 dB |

`infinitalk/from-audio` falló dos veces seguidas en Kie (timeout del servidor al bajar el audio): no usar hasta verificar.

## 2. QA visual obligatorio (antes de montar)

1. **Hoja de contacto de keyframes** (todos en orden). Mirar: personajes iguales a sus hojas, nada de extras desconocidos, encuadre pedido, nada de texto.
2. **Hoja de frames de los clips** (2–3 cuadros por clip). Mirar: **texto inventado** (Kling Avatar mete subtítulos ilegibles en ~20 % de los clips), más de una boca moviéndose, acción al revés.
3. **Video final:** un cuadro por plano, transcripción del audio con Whisper (los «textos» que aparecen sobre la música son alucinaciones de Whisper: confirmar con `props-final.json`), y el volumen con `ebur128`.

## 3. Fallas conocidas y arreglo

| Falla | Arreglo |
|---|---|
| Keyframe que copia el encuadre del set | Plano cerrado sin set (automático); si sigue abierto, recortar desde el 2K (`crop` + `scale` lanczos) |
| Extras desconocidos en el plano | Plano general: elenco completo como referencia (automático); plano cerrado: «resto fuera de cuadro» |
| Texto inventado en un clip de Kling | El prompt ya lo prohíbe. Si aparece: guardar el original en `clips/_originales/` y **reencuadrar** dejando la franja afuera (cae en el tercio inferior). Si no se puede, rehacer el plano |
| Dos bocas se mueven | Contraplano con `elenco: solo` y el destinatario de espaldas |
| Gesto que no apunta a nadie | Contraplano por encima del hombro del destinatario |
| «No.» de 1 s | Línea con `[curt, flat, one quick syllable]` |
| Voces lentas y con pausas | `ritmo_voces` + compresión de pausas > 0,3 s (automático) |
| Corte de red con Kie | `sketch recuperar <carpeta>` (lee los `taskId` de los logs) |

## 4. Costos medidos (piloto de 34 planos y ~66 s)

| Ítem | Créditos Kie |
|---|---|
| 15 hojas de personaje (5 × 3 variantes) | 270 |
| 1 set | 18 |
| 34 keyframes (incluye rehechos) | ~1.000 |
| 34 clips con lip-sync (incluye rehechos) | ~1.600 |
| 3 clips de acción | ~140 |
| Música (5 pedidos Suno) | ~60 |
| **Total del piloto** | **≈ 3.500 créditos ≈ 17,5 USD** |

Una pieza nueva sin rehechos ronda **1.200–1.600 créditos (6–8 USD)**. La variante de hook (cambiar los primeros 2–3 planos) cuesta ≈ 100–200 créditos. Voces de Gemini: centavos. Efectos de ElevenLabs: dentro del plan. Tiempo: 40–60 min, casi todo cola de Kie.
