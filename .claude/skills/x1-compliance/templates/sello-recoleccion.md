# Sello de recolección de D1 · <periodo> · <fuente_id>

> PLANTILLA (`references/recoleccion.md`). Cada fila con evidencia citada. El sello lo emite el código `[PENDIENTE: B6]`; esto es el dictamen-borrador.

- Fuente: `<fuente_id>` · color **V / A / R** · nivel de autonomía: N… · captcha/403/`Disallow`: sí/no (si sí → **roja**)

| VC | Check | ✔/✘ | Evidencia (cita ≤ 25 palabras, URL, fecha) | Tipo (veto/pausa/MAYOR) |
|---|---|---|---|---|
| 01 | términos leídos ≤ 90 días | | | veto |
| 02 | robots.txt / ai.txt / TDMRep | | | veto |
| 03 | sin login ni evasión | | | veto |
| 04 | tope por dominio | | | pausa |
| 05 | filtro de PII probado con muestras sembradas | | | veto |
| 06 | solo campos permitidos | | | veto |
| 07 | extractos ≤ 25 palabras | | | MAYOR |
| 08 | nicho sensible o menores: agregado o veto | | | veto |
| 09 | TTL y evidencia fuera de Git | | | veto |
| 10 | borrado ≤ 7 días | | | pausa |
| 11 | aviso público por idioma (UE) | | | veto |
| 12 | interés legítimo y DPIA documentados | | | veto |
| 13 | LLM con acuerdo de procesamiento y sin entrenamiento | | | veto |
| 14 | sin citas de terceros | | | MAYOR |
| 15 | texto web tratado como dato | | | MAYOR |
| 16 | registro de la consulta | | | registro |

**Resultado:** sello **concedido / denegado**. Gate H del dueño (fuente nueva de nivel A, política): ☐ firmado.
