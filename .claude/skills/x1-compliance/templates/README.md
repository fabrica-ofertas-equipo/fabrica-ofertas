# templates/

| Archivo | Para qué | Lo llena |
|---|---|---|
| `dictamen-fail-d6.json` | dictamen de X1 (un `qa`, `etapa: X1`) **FAIL** de D6: «Perdé 8 kg en 30 días», con reencuadre RE-02 (válido contra `contratos/qa.schema.json` y `scripts/validar_dictamen.py`) | Maker (borrador) → QA (definitivo) |
| `dictamen-pass-con-notas-d5.json` | dictamen **PASS_CON_NOTAS** de D5; hash en ceros y textos «[PLANTILLA]»: **no sirve para sellar** | ídem |
| `checklist-etapa.md` | hoja de trabajo por etapa (ejes, controles, hallazgos, gates H) | Maker |
| `simulacion-revisor.md` | simulaciones L3 (a)-(d) | Maker y QA |
| `paises.yaml`, `matriz_pais_nivel.yaml` | semilla de Anexo B y nota 25 §8.1, todo `[VERIFICAR]`, `estado: pendiente` | Maker; **aprueba solo el dueño con firma** |
| `reglas_claims.yaml`, `terminos_sensibles.locale.yaml` | borrador de reglas por locale (propuesta). El linter real lee `compliance/reglas_sensibles.yaml` y, como léxico aditivo, `empresa/compliance/terminos_sensibles/<locale>.yaml` **en la forma categoría → nivel → regex** (`empresa/compliance/ejemplos/terminos_sensibles.es-ES.ejemplo.yaml`), no la de este borrador (`dependencias.md` D-02b) | Maker + revisor nativo |
| `limites.propuesta.yaml` | las 30 líneas rojas y claves para `limites.yaml` (nunca lo escribe el Maker) | Maker → dueño |
| `politica_recoleccion.yaml`, `sello-recoleccion.md` | política de recolección de D1 y checklist VC-01…16 | Maker → dueño |
| `dossier.md` | resumen para el dueño y puntos fiscales para el contador | Maker |

Comprobar los JSON: `.venv/bin/python .claude/skills/x1-compliance/scripts/validar_dictamen.py templates/dictamen-fail-d6.json --sin-nombre`.
