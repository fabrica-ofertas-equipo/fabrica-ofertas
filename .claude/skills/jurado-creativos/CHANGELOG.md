# Changelog — skill `jurado-creativos`

SemVer. Cada versión dice qué corrida real la respalda. **v0.1 sin pulir (borrador generado desde `docs/_historial/mentor-sistema/brechas/02-jurado-testeo-robots.md`; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min).**

## 0.1.0 — 2026-11-07 — primera versión (sin corrida real)

Sigue siendo **v0.1 sin pulir**. Origen: brechas B2-26 (jurado de creativos) y B2-27 (calibración contra lo cobrado) del informe de brechas 02; decisiones J1-J21; análisis `analisis/creativos-jurado.md` P3-01…P3-11 y decisión D-3 (modo sombra).
**Qué trae**
- `SKILL.md` (reglas duras, qué hace la IA y qué el código, procedimiento diario de 8 pasos y semanal, reglas de decisión, DoD), `rubric.md` (JQ-01…JQ-14, R1-R6, L3), `references/` (avatares desde la voz del cliente, votación ciega, calibración, sombra y promoción, conflictos y pedidos), `templates/` (avatar, voto, jurado + esquema JSON propuesto, piezas, anclas, promoción, métricas, parámetros propuestos, informe del QA), `evals/` (dorados, sembrados y una demostración sin LLM) y `PEDIDOS.md` (17 pedidos).
- Agentes `jurado-votante` (un voto, solo `Read`, sin precargar la skill) y `jurado-qa` (solo lectura).
- Código en `scripts/jurado/` (stdlib, sin red, sin LLM): `avatares.py`, `paquetes.py`, `agregar.py`, `calibrar.py`, `estadistica.py`, `demo.py`; 168 pruebas en `tests/jurado/`.
**Honestidad.** Modo sombra por defecto; el jurado nunca decide gasto; sin etiquetas reales no hay AUC ni Brier; la promoción exige 150 etiquetas, ganarle al azar y a la rúbrica, anclas medidas y la firma del dueño. Los parámetros son `[SUPUESTO]`. La fuente no da el prompt de los avatares ni la ponderación (H-11).
**Falta** (ver `PEDIDOS.md`): contrato y parámetros (S-A), pantalla (`modo`, `aplica_orden`, `precision.estado`), runner de votación, scheduler y `metricas.jsonl` (S-B), voz del cliente ampliada, anclas medidas, los 3 videos de JPS y una corrida real.

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-07 | — | — | — | generada desde las brechas 02; solo demostración con votos sintéticos |
