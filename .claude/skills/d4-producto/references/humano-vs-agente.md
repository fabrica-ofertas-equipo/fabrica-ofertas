# Qué hace un agente, qué hace un humano

> Backbone 6.2 («los pasos con interfaz gráfica los hace un humano»), spec §4 paso 4 y 9, §6.3, §7. Lo que un agente **no puede** verificar se marca `no_verificado_por_agente` y pasa al checklist; **nunca** se simula ni se da por hecho.

| Tarea | Agente (Maker/QA/scripts) | Humano |
|---|---|---|
| Redactar, estructurar, calcular, generar JSONL/HTML/CSS/XLSX por código | Sí (Maker) | Revisa |
| Ejecutar el método sobre archivos locales (scripts de la skill y de `scripts/producto/`, caso ficticio, gasto 0; sin red, sin cuentas de prueba, sin CAPTCHA) | Sí | — |
| **Interfaz gráfica de escritorio** (abrir/duplicar en Google Sheets o Excel, configuración regional, imprimir a PDF, selector de archivos, probar en el móvil) | **No** → `no_ejecutable_por_agente` | **Sí** |
| Web, cuenta, pago o CAPTCHA de un tercero | **No** (el Maker no tiene web ni MCP) | Sí (cuentas de prueba del dueño) |
| Cronometrar el primer paso real | No (el reloj del agente no es humano) | **Sí** (checklist; alternativa A de `tiempo-y-novato.md`) |
| Cold run de novatos en frío (B) | Sí (2+ agentes, otra sesión, idioma del producto) | Complementa (A) |
| Verificar 5 hechos contra su fuente abriendo el enlace | Script/QA (cita en snapshot) | Sí, 5 hechos a mano en el checklist |
| RHS (revisión humana de seguridad, 30-60 min) | No sustituible (un LLM «interpreta») | **Sí**, en el primer amarillo-a de cada hoja × idioma |
| Revisión **nativa** del idioma (glosario, avisos, ayuda) | No (retraducción y segunda lectura son controles de agente) | **Sí**, primer lanzamiento de cada idioma; luego 1 de cada 5 |
| Muestra física de un patrón con conteos | No | **Sí**, primer lanzamiento del tipo |
| Casos dorados de una hoja (recalcular) | Hoy no [PENDIENTE: `calc_hoja`] | Sí (carga cada caso en la hoja) |
| Elegir/aprobar la guía de estilo de imágenes (si el dueño habilita imágenes generadas); comprobar plan y términos de licencia en la web | Propone | **Sí** |
| Dar permiso para gastar créditos (hoy D4 no gasta: sin Higgsfield) | **Nunca** (solo pide) | **Sí**, explícito en el chat |
| Aprobar el producto | No | Sí (gate S: checklist de 10 min; H si GUI, tipo nuevo o sin cold run humano) |

## Qué se anota cuando un paso no es verificable por agente
`autoprueba.json#no_ejecutable_por_agente`, `verificacion.json#mu.operable.no_verificado_por_agente` y, en el QA, `simulaciones_l3[].resultado` con el texto «no_verificado_por_agente». Si **todos** los pasos operables de un producto son GUI, el producto va siempre a revisión humana.

## Checklist del dueño (10 min) y RHS
`templates/checklist_dueno.md` y `templates/rhs_lista.md`. Si no entra en 10 minutos, se reduce la muestra, no el primer paso. En un idioma que el dueño no lee, la ortografía pasa al revisor nativo. Quién los hace (dueño, colaborador, revisor pagado por hora) es **decisión del dueño** [DUEÑO] (`preguntas-abiertas.md`).
