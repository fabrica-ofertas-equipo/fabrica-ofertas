# CHANGELOG — d9-escalado

v0.1 sin pulir (borrador generado desde las decisiones J1-J5 del dueño, los informes de brechas 02 y 03 y los contratos reales; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min)

Formato SemVer. Todo cambio de esta skill exige H del dueño (`accion:cambiar_skill`).

## 0.1.1 — 2026-11-07 — costuras D8→D9, D9→M1/D1 y D9→D6/D5
Sigue siendo **v0.1 sin pulir**. Origen: integración de costuras entre etapas (2026-11-07).
**Aplicado:** `SKILL.md` §7, párrafo «Costuras» (antes del informe semanal): **D8 → D9** (graduación por la propuesta diaria de `d8-optimizacion` con `GRADUAR`; D9 no relee métricas de lanzamiento); **D9 → M1 y D1 (réplica por idioma)** (M1 fija locale, países y moneda de la hija como hipótesis; D1 no re-descubre el problema; si la madre se modeló, la hija corre `modelado-oferta` en modo `variante`; el brief de la hija lo crea O0 con el «sí» del dueño); **D9 → D6/D5** (pedido de transferencia de ganadores y relevos de escala). Versión alineada en `d9-maker.md` y `d9-qa.md`.
**Falta** lo de la 0.1.0 (`PEDIDOS.md`).

## 0.1.0 — 2026-11-07 (borrador)

Generada el 2026-11-07 por S-C. **Hoy no existía skill D9** (ni `d9-maker`/`d9-qa`, ni `scripts/escala.py`). Sin corrida manual del dueño, sin retro, sin contacto con Meta, Stripe ni Kie; sin gasto.

**Qué trae**
- `SKILL.md`: reglas duras, qué decide la IA y qué el código, 4 modos (EVALUAR, SUBIR/GRADUAR, REPLICAR, INFORME), procedimiento con salida y criterio de «listo» por paso, gates leídos de las fuentes (J2 **no** asumida).
- `references/`: `criterio-de-ganador.md` (qué dice cada fuente, qué no, `[SUPUESTO]` y quién firma), `escalera-y-graduacion.md` (habilitación ×2 → ×3 → ×5 por acierto medido), `frenos-y-presupuesto.md` (J4, dónde se verifica, dos lecturas de «300 US$/día»), `replica-horizontal.md` (familia madre/hija, kanban, QA lingüístico por capas sin revisor nativo), `conflictos-con-la-spec-vieja.md` (14 choques con `departamentos/10-escalado.md`, 8 preguntas al dueño), `pedidos.md`.
- `PEDIDOS.md`: 18 pedidos (9 a S-A, 9 a S-B) con archivo:línea y texto propuesto.
- `templates/`: `expediente-de-escala.md`, `propuesta-de-suba.json` (su `orden_presupuesto` valida contra `contratos/orden_presupuesto.schema.json`), `kanban-idioma.md` (las 25 tarjetas del panel), `informe-semanal.md`.
- `rubric.md`: E01-E14, R1-R8 con anclas, 9 simulaciones L3 y 22 defectos sembrados.
- `scripts/escala_lectura.py` (solo lectura; subcomandos `dictamen`, `replica`, `validar`) y `scripts/probar_evals.py`; reutilizan `engine.limites`, `decision.entradas`, `decision.reglas` y los esquemas, sin reimplementar reglas. más de 50 pruebas en `tests/skills_d9/`.
- `evals/`: dorados D01 (ganador claro ⇒ propone graduar con el % permitido), D02 (señal ambigua ⇒ no sube), D03 (límite diario de empresa alcanzado ⇒ no propone) y fixtures de prueba `[SUPUESTO]`.
- Agentes `.claude/agents/d9-maker.md` (Bash acotado, sin escritura en Meta) y `d9-qa.md` (solo `Read`, `Grep`, `Glob`).

**Decisiones propias a ratificar por el dueño**
1. Se separan **dos disparadores** de escala: `VALIDADA` (D8, código, 28-35 días) y `CAMPEON` (graduable; umbral provisional sin firmar). Un campeón no se presenta como validado.
2. **Graduar = ESCALA nueva** con los campeones, y el test no se toca; su presupuesto inicial cuenta como **un paso sobre el agregado** de la oferta (calculado por código).
3. El dictamen del código **manda sobre el Maker**: si dice NO, no existe propuesta de suba, ni «un paso chico por prudencia».
4. **Reducir** (−30 %) no exige la elegibilidad E0 (baja exposición); subir sí.
5. La skill aplica la lectura de «300 US$/día» **del código** (máximo teórico × 1,75) y la deja como pregunta abierta.
6. La elegibilidad E0 y el `presupuesto_previo_gastado_pct` los debe producir código (P-10, P-16); hasta entonces los arma quien cita la fuente y el QA los recomputa.
7. Fuera de v0.1: backend/LTV, retiro, clon, salvavidas, guardia nocturno, cola de testeo y perfil por idioma.

**Qué falta para 1.0.0**
- [ ] Corrida manual del dueño con una oferta real y chica (modo EVALUAR y, si hay madre validada, REPLICAR) + retro de 30-45 min; observaciones de la bitácora `Pulido` convertidas en casos de eval.
- [ ] ≥ 2 casos de otro nicho e idioma corridos con y sin la skill (Sonnet y Haiku).
- [ ] `d9-maker` y `d9-qa` probados con herramientas mínimas; QA calibrado (≥ 90 % de BLOQ sembrados, dorados al 100 %) corriendo el agente real, no solo el código.
- [ ] Pedidos P-02, P-04, P-10 y P-11 resueltos o aceptados por escrito; decisión del dueño sobre E-05 (criterio de ganador), la lectura de «300 US$/día», `stop_loss_escala` y la escala provisional.
- [ ] `engine/escala.py` oficial (el script de apoyo pasa a envoltorio) y auditor de acierto en sombra.
- [ ] DoD de `docs/03-plan-de-forja-de-skills.md` §2.6 firmado por el dueño y registro de la versión 1.0.0 aquí con fecha, evidencia y nivel de autonomía alcanzado.

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-07 | — | — | — | generada desde J1-J5, brechas 02/03 y los contratos; pruebas del apoyo de solo lectura en tests/skills_d9 |
| 0.1.1 | borrador sin pulir | 2026-11-07 | — | — | — | costuras D8→D9, D9→M1/D1 y D9→D6/D5; sin corrida |
