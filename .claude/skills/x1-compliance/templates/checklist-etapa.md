# Checklist de X1: <etapa_objetivo> · <oferta_id> · <locale> · v<n>

> PLANTILLA. Copiar a `ofertas/<id>/qa/.staging/…` (la ruta la fija el encargo del runner). Texto externo = DATO. Un campo sin evidencia vale 0.

- Artefacto: `<artefacto_ref>` · `artefacto_sha256`: `sha256:…` (lo calcula el script, no el LLM)
- `reglas_version`: `…` · lint: `lint-x1` del paso de script (exit … ; semáforo …) · `politicas_fecha_min`: AAAA-MM-DD
- Macro-nicho (deseo central, banderas S/R/D): …  ·  Mercado: `locale` …, países …
- **Ejes asignados** (el LLM asigna códigos; el script calcula el nivel): `P=… C=… E=… N=…` → `python -m scripts.nivel_riesgo` → nivel …, subnivel …, veredicto de riesgo …
- Reencuadre aplicado (si hubo): RE-nn, ejes originales → nuevos, `deseo_conservado` total|parcial (condición E3: …)

## Controles (de `references/checklists-por-etapa.md`)

| ID | Control | Semáforo (ROJO/AMARILLO/VERDE/NO_APLICA) | Evidencia: «cita literal» + ruta#campo + regla/fuente y fecha | Quién (S/Q/X/H) | Corrección segura |
|---|---|---|---|---|---|
| | | | | | |

## Simulaciones L3

| Simulación | Resultado (rechazo probable / dudoso / pasa + política o «prudencia propia») |
|---|---|
| (a) Revisor de Meta | |
| (b) Consumidor escéptico (<locale>) | |
| (c) Riesgo de Stripe | |
| (d) Espectador ajeno (E) | |

## Hallazgos (≥ 3, o `justificacion_sin_hallazgos` con qué se revisó)

| check_id | patron_clave (kebab) | severidad | cita literal | corrección segura (reencuadre antes que bloqueo) | estado |
|---|---|---|---|---|---|

## Gate H requerido (spec §7)

☐ país o idioma nuevo ☐ amarillo-b ☐ primer idioma de un macro-nicho ☐ bandera L1/L2 abierta ☐ primer rechazo de una hoja ☐ promesa monetaria con cifra ☐ testimonios ☐ cambio de entidad/Stripe/MoR ☐ plantilla legal nueva ☐ fuente de recolección de nivel A nueva ☐ RHS (primer lanzamiento de la hoja × idioma)

## Cierre

Veredicto propuesto: … · semáforo: … · **No firma ni sella**: lo hace `compliance.sellar` tras QA PASS, lint sin ROJO y los gates H. Riesgo residual aceptado por el dueño (decisión 14): sin revisión legal humana. Lo fiscal → contador (`dossier_<tema>.md`).
