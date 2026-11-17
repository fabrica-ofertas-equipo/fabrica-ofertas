# Checklist del dueño · 10 minutos — {oferta_id} · {locale} · {version}

> Lo corre el dueño (o quien él designe) antes de aprobar. Si no entra en 10 minutos, **se reduce la muestra, no el primer paso**. En un idioma que el dueño no lee,
> la ortografía y el registro pasan al revisor nativo. Puntos = peso en minutos aproximados.

| Ítem | Peso | Qué hacer | ✔ / ✘ y nota |
|---|---|---|---|
| Promesa y portada | 0,5 | ¿La portada dice lo mismo que la landing y que `oferta.json`? ¿Está el tiempo previsto? | |
| Abrir en el celular | 0,5 | Abrir el PDF/hoja en un móvil real: legible sin zoom, sin desbordes | |
| **Primer paso real, cronometrado** | **3** | Cronometrar el primer paso del método con un caso propio. Anotar minutos reales frente a `verificacion.json#eu.tiempo_primer_resultado` (desvío grande = promete de más) | real: ___ min · estimado: ___ min |
| 5 hechos contra su fuente | 2 | Elegir 5 filas de `afirmaciones.jsonl`; abrir cada fuente y comprobar cifra, unidad y fecha | |
| 2 prompts/unidades con un caso propio | 2 | Probar 2 prompts, fichas o fórmulas con datos propios: utilizable sin ajustes mayores | |
| ¿Qué página borrarías? | 0,5 | Toda página que no mapee a una promesa sobra | |
| Demo / muestra | 0,5 | La muestra gratuita es veraz (capturas reales, nada simulado) | |
| Avisos, ayuda e IA | 0,25 | Aviso de alcance, «cuándo parar», ayuda literal del país (si aplica) y divulgación de IA | |
| Marca y portada | 0,25 | Marca visual de la oferta (paleta y tipografías OFL), sin logos de terceros | |
| **Pregunta final** | — | «¿Me daría vergüenza recibir un reclamo de este producto?» | |

**Pasos con interfaz gráfica que SOLO hace una persona** (el agente los marca `no_verificado_por_agente`): duplicar/abrir la hoja en Google Sheets o Excel y poner la configuración regional del locale; comprobar los casos dorados en la hoja; abrir en el móvil; descargar desde el enlace de preproducción; cualquier cuenta o pago.

Resultado: ☐ APRUEBO ☐ APRUEBO CON EDICIONES MENORES (listarlas) ☐ DEVUELVO (motivo). Firma/fecha: ______
Ediciones que hice a mano (para `origen_version` y para pulir la skill): ______
