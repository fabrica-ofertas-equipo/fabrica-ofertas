# Relación con la skill `anthropic-skills:creativos-ads`

La skill instalada en el entorno del dueño (`~/.claude/skills/synced/…/creativos-ads/`: módulos de hooks, ad-creative, copywriting, investigación de clientes y contexto de tuotroproyecto/VibeSelling) es un **método general de creativos** adaptado de `coreyhaines31/marketingskills` y `PostPlusAI/hook-skills` (MIT). D6 **no la copia ni la reemplaza**: se apoya en ella cuando existe y se basta sola cuando no (el runner desatendido no la carga: solo la sesión Code del dueño). Se leyó el 2026-11-06; si cambia, se revisa este archivo al pulir.

## 1. Cuándo se consulta (solo método, nunca contexto de producto)

| Necesidad de D6 | Módulo de creativos-ads que ayuda |
|---|---|
| Elegir la ruta y el mecanismo de un hook (paso 4) | `modules/hooks/` (`pattern-router`, `hook-design`) |
| Primer fotograma y texto en pantalla de un video | `modules/hooks/references/visual-hook.md` | <!-- refcheck:ignore (ruta de la skill externa creativos-ads, fuera del repo) -->
| Revisar un prompt de generación antes de gastar créditos (paso 6) | `modules/hooks/references/prompt-preflight-qa.md` | <!-- refcheck:ignore (ruta de la skill externa creativos-ads, fuera del repo) -->
| Decodificar una referencia de la competencia en **ficha de formato** (paso 2) | `modules/hooks/references/reference-decode.md` | <!-- refcheck:ignore (ruta de la skill externa creativos-ads, fuera del repo) -->
| Estructura del guion y plantillas estáticas, matriz de hooks (segmento × motivación × formato) | `modules/ad-creative/GUIDE.md`, `modules/ad-creative/references/hook-system.md` y `static-ad-templates.md` de esa misma carpeta | <!-- refcheck:ignore (ruta de la skill externa creativos-ads, fuera del repo) -->
| Pipeline de video sin cara (estilo, voz en off, subtítulos) | `modules/ad-creative/references/motion-video-ads.md` | <!-- refcheck:ignore (ruta de la skill externa creativos-ads, fuera del repo) -->
| Minar la voz del cliente | `modules/customer-research/` |

**No se lee** `context/tuotroproyecto.md` (es contexto de otro producto: rioplatense, ángulos de tuotroproyecto, `ANG-…_HK-…` en nombres) salvo que la tarea sea de tuotroproyecto o VibeSelling, que no es esto. <!-- refcheck:ignore (ruta de la skill externa creativos-ads, fuera del repo) -->

## 2. Lo que se adopta (coincide con D6)

- Un hook son tres componentes (acción visual, línea hablada, texto en pantalla) que no se repiten; puente de 3–15 s que continúa la premisa; **una variable por iteración**; dos hooks por concepto que difieren en mecanismo.
- Matriz de diversidad (segmento × motivación × formato) en lugar de reescrituras de una misma celda.
- Fidelidad por escalones: baja fidelidad (estáticos, texto en pantalla, voz sobre b-roll) para hipótesis; alta solo para ángulos validados.
- Subtítulos siempre; verificación de límites de caracteres antes de entregar; cada concepto cita su fuente de fundamento (voz del cliente, comentarios) y no se inventan cifras ni testimonios.
- Escribir en el idioma y registro del mercado, nunca «castellano neutro ni traducido» (acá: el del `locale`).
- No generar imagen, video o voz «por cuenta propia»: se propone y decide el usuario (en D6: cotizar, mostrar y esperar aprobación).

## 3. Donde D6 es **más estricta** (D6 manda)

| creativos-ads sugiere | D6 |
|---|---|
| Ángulos «Outcome: Achieve Y in Z days», «Join 10,000+», «Limited time», «Identity: Built for [role]», números en titulares como «3x faster» | Ningún plazo de resultado, cifra de clientes/ventas, urgencia no verificable ni identidad con atributo (`lista-rojo-amarillo.md`) |
| Hooks de confesión en primera persona, bold claim, proof-first con captura de resultados, before/after | Prohibidos como testimonio, promesa o transformación; ver mapa en `tipos-de-hook.md` §6 |
| Founder content, partnership/creator ads, authority ads (médico), UGC, yapper | Sin cara; sin avales sanitarios o financieros aparentes; `avatar_ia` solo presentador rotulado en dinero verde |
| Reveals de iMessage/ChatGPT/Notes con conversaciones dramatizadas | No se usan (conversaciones y respuestas de IA fabricadas = testimonio sintético) |
| Texto en la imagen generado por el modelo («directo desde Claude») | Texto siempre por HTML→PNG + OCR; imagen generada solo como fondo sin texto |
| Nombres de anuncio de tuotroproyecto (`ANG-<ángulo>_HK-<tipo>_V<n>`) | `{concepto_id}_{img\|vid\|car}_{hook_id}_v{n}` (backbone §5.2) |
| «Más información» como CTA preferida | Variable de iteración; en otros idiomas no se asume |
| Medir hooks con umbrales (hook rate, retención, CTR) | Los define y recalibra D8 por `locale`; D6 no los fija |
| Carrusel «E-tier: rara vez vale» | Admitido solo como secuencia del entregable (pasos o páginas) |
| «Retiring creative too early: 1.000+ impresiones» y reglas de lectura | Es de D8 |

## 4. Zona segura 9:16

`creativos-ads` documenta una banda de texto de 720 × 1200 (y 220–1420); el Anexo A de la spec da otros márgenes. D6 usa el borde más restrictivo de cada lado (`specs-formatos.md` §2); ambas cifras son **[VERIFICAR]**.

## 5. Cómo se registra

Cuando el Maker usó un módulo de creativos-ads, lo anota en `brief-creativo.md` §6 («Método consultado») con el nombre del archivo; el QA no depende de ello. Si ese método choca con una regla de esta skill, **gana la regla de D6** y el choque se anota como observación de pulido (`como-pulirla.md`).
