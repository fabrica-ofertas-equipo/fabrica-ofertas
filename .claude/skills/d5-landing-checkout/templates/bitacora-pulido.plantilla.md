# Bitácora de pulido de la landing — <oferta_id> · sesión <n> · <fecha>

> Plantilla para la pestaña `Pulido` del panel (`#/pulido`; `POST /pulido {oferta_id, etapa:"D5", titulo, detalle, severidad: baja|media|alta, tipo: observacion|nota|decision}`). Una entrada por observación. Proceso: `references/proceso-landing.md` §10.

**Datos de la sesión:** dispositivo y navegador (p. ej. «iPhone, navegador integrado de Instagram») · URL de preview · versión de la landing (`landing_version`) · duración.

## Formato de cada entrada
`titulo`: `[S##][R#|C##][categoría] frase corta` · `detalle`: qué viste · qué esperabas · qué regla lo evitaría · captura o ruta · `severidad`: alta (bloquea comprar, recibir o cumplir) | media (comprensión o confianza) | baja (estética o gusto) · `tipo`.
Categorías: `[error]` hecho, cálculo o copy mal · `[regla]` criterio que quieres siempre · `[pref]` gusto tuyo · `[riesgo]` política, legal o dinero · `[contexto]` solo esta oferta.

## Ejemplos
| titulo | detalle | severidad | tipo |
|---|---|---|---|
| `[S01][R2][error] El hero no dice el precio` | A 5 s dos de tres personas no supieron cuánto cuesta; esperaba precio en el hero. Regla: la microlínea del hero incluye `{precio}`. | alta | observacion |
| `[S03][C15][riesgo] «tu vergüenza» atribuye un estado` | Frase del dolor 2; pasar a obstáculo impersonal. | alta | observacion |
| `[S09][R7][error] El bump no se ve como opcional` | La casilla aparece igual que los términos. | media | observacion |
| `[S11][pref] Prefiero el botón más grande` | Gusto personal; no va a la skill. | baja | nota |
| `[S08][regla] La prueba honesta debe abrir con la muestra` | Orden de bloques en S08. Candidata a regla (esperar 2.ª evidencia). | media | decision |

## Cierre de sesión (retro de 30 min)
| Categoría | N.º de entradas | Acción |
|---|---|---|
| `[error]` | | corregir en `v<n+1>` y añadir un caso a `evals/` |
| `[regla]` | | candidata al proceso; entra con ≥ 2 evidencias (salvo `[riesgo]`) |
| `[pref]` | | a tu perfil, no a la skill |
| `[riesgo]` | | a X1 y a `references/claims-rojos.md` |
| `[contexto]` | | se queda en la oferta |
Entradas `alta` abiertas: … · ¿lista para gate H? (criterios de §10.6): …
