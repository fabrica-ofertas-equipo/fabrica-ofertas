# Conjunto de retención: [PENDIENTE: lo sella el dueño]

**Estado v0.1: no existe.** Esta carpeta solo fija el protocolo; el conjunto lo construye y sella el dueño. Hasta entonces el clasificador de riesgo **no está certificado** y X1 no puede ascender de N2 a N3 (spec 14 §7: 0 falsos verdes sobre ≥ 60 positivos).

## Requisitos (spec 14 §6 y nota 25 §11)

- ≥ 30 % del tamaño de la suite (≥ 70 casos si la suite tiene 230), de los cuales **≥ 60 positivos** (esperado rojo).
- **Sellado por hash** (`sellado_sha256` = sha256 del JSON canónico de `casos`) y **anotado por dos personas** independientes; la discrepancia entre anotadores se resuelve y se documenta.
- **Invisible** para los Makers, el QA de desarrollo y los linters: se guarda fuera de `.claude/skills/` y fuera de lo que lee cualquier agente (el QA de certificación lo recibe solo en la corrida de certificación, con la entrada ciega).
- **+15 casos por trimestre** y **+1 por cada rechazo real** de Meta o Stripe (por claim).
- Los 30 casos RT-\* de la suite son el primer lote de retención: no se usan para ajustar lints ni criterios.
- Se informa siempre **n y la cota** (regla de tres: con n = 63 y 0 falsos verdes, cota 4,8 %; con n < 60 no certifica).

## Cómo se corre

```
.venv/bin/python .claude/skills/x1-compliance/scripts/correr_evals.py retencion --manifiesto <ruta del manifiesto> --respuestas R.json
.venv/bin/python .claude/skills/x1-compliance/scripts/correr_evals.py cota --n 63 --falsos 0
```

El corredor rechaza (salida 4) un manifiesto cuyo hash no coincida o con menos de dos anotadores, y no certifica con menos de 60 positivos. Plantilla: `manifiesto.plantilla.json` (vacía, rechazada a propósito).
