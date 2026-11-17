# Rúbrica de QA · d6-sketch-animado (la usa el QA de D6 en los tramos A y B)

Severidades como en `d6-creativos/rubric.md`: BLOQUEANTE · MAYOR · MENOR.

## Tramo A · guion (antes de gastar)
| # | Chequeo | Severidad si falla |
|---|---|---|
| A1 | Toda línea con un hecho del producto tiene `claims: [id]` y el id existe en `claims_permitidos` | BLOQUEANTE |
| A2 | Ninguna frase (ni parafraseada) de `claims_prohibidos` / `claims_a_evitar`; ningún resultado (trabajo, dinero, kilos, salud, pareja), ni insinuado por el detonante | BLOQUEANTE |
| A3 | Ningún personaje habla como cliente con resultado propio («me funcionó», «conseguí…») | BLOQUEANTE |
| A4 | Las objeciones se dicen entre personajes; ninguna atribuye un atributo al espectador | BLOQUEANTE |
| A5 | Macro-nicho ≠ salud/relaciones; nivel verde; gate del dueño y de X1 anotado | BLOQUEANTE |
| A6 | Escrito en el idioma del `locale`, con escenario, nombres y modismos del país (no traducido) | MAYOR |
| A7 | Estructura de `formato.md` §1: gancho ≤ 5 s, ≥ 3 objeciones, revelación con ≤ 3 frases, remate, historia ≤ 57 s en el animatic | MAYOR |
| A8 | Personajes genéricos por papel, sin parecido buscado con personas reales, marcas ni otros estudios | MAYOR |
| A9 | `etiqueta_ia` presente según `politica_divulgacion_ia` | BLOQUEANTE |

## Tramo B · pieza
| # | Chequeo | Severidad si falla |
|---|---|---|
| B1 | Ningún texto inventado en cuadro (hoja de frames de todos los clips y del video final) | BLOQUEANTE |
| B2 | El audio dice el guion congelado palabra por palabra (Whisper) | BLOQUEANTE |
| B3 | Un solo personaje mueve la boca por plano; los gestos apuntan a quien corresponde | MAYOR |
| B4 | Personajes iguales a sus hojas en todos los planos; sin extras desconocidos | MAYOR |
| B5 | Subtítulos dentro de la zona segura, sincronizados (inicio ≤ 6 cuadros tras la voz), 1–3 palabras | MAYOR |
| B6 | Mezcla −17 ± 1 LUFS, pico ≤ −1 dBFS; sin huecos de silencio absoluto salvo los cortes buscados | MENOR |
| B7 | `costos.jsonl` tiene una línea previa por tarea; `creditos_reales` (de `trabajo/gasto.jsonl`) ≤ reservado | MAYOR |
| B8 | `assets.json`: `ia_generado: true`, `job_id` por tarea, licencias de música, efectos y voces registradas | MAYOR |
