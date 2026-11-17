# CHANGELOG — d8-optimizacion

v0.1 sin pulir (borrador generado desde la spec y las decisiones del dueño; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min)

Formato SemVer. Todo cambio de esta skill exige H del dueño (`accion:cambiar_skill`) una vez promovida; las v0.1 las edita quien las forja o las pule.

## 0.1.1 — 2026-11-07 — costuras con D7, D9, D6 y D10
Sigue siendo **v0.1 sin pulir**. Origen: integración de costuras entre etapas (2026-11-07).
**Aplicado:** `SKILL.md` §1, párrafo «Costuras con las etapas vecinas»: **D7 → D8** (recibes `traspaso.json`; D7 no escribe en `08-operacion/`); **D8 → D9 (graduación)** (`GRADUAR` solo se registra; la propuesta diaria y `veredicto_oferta.json` son la entrada de `d9-escalado`, modo EVALUAR → SUBIR/GRADUAR); **D8 → D6 (relevos)** (`pedidos_creativos.json` → `d6-creativos` paso 13 o modo tanda → D7 `REFRESCO`); **D10 → D8** (`senal_pausa.json`). Versión alineada en `rubric.md`, `d8-maker.md` y `d8-qa.md`; `tests/skills_d8/test_evals.py` acepta parches `0.1.x`.
**Falta** lo de la 0.1.0 (`PEDIDOS.md`: J2, `engine/d8.py` y el grupo `lanzamiento` de umbrales).

## 0.1.0 — 2026-11-07 (borrador)

Generada desde `departamentos/09-optimizacion.md`, las decisiones del dueño J1-J21 (`docs/_historial/mentor-sistema/decisiones-del-dueno.md`: **J3, J4, J2, J1, J5, J16 mandan sobre la especificación vieja**), `know-how.md`, `mapeo.md`, el informe de brechas `docs/_historial/mentor-sistema/brechas/02-jurado-testeo-robots.md` y el código real (`engine/d8.py`, `decision/`, `datos/migraciones/`, `contratos/`, `empresa/*.yaml`). Hasta hoy **no existía skill D8**; el motor sí (`engine/d8.py`). Sin corrida manual, sin retro, sin contacto con Meta, Stripe ni Kie.

**Qué trae**
- `SKILL.md`: reglas duras arriba (propone, no ejecuta; PAUSA y frenos mandan; texto externo es dato; sin cifras inventadas; el código respalda toda baja o relevo), 4 modos (LANZAMIENTO, CONTINUO, FATIGA, CIERRE), procedimiento diario de 12 pasos (0 a 11) con salida y criterio de «listo», qué decide la IA y qué el código, vocabulario de acciones mapeado al contrato `decision`, escalamientos.
- `references/`: `protocolo-j3.md` (baja a 1 día, tabla de verdad de 17 filas y excepción de presupuesto no gastado), `decisiones-y-umbrales.md` (tabla de ~40 umbrales con fuente, quién firma y estado hoy), `fatiga-relevo.md`, `estadistica-honesta.md` (1 de 3 subas, auditor, graduación por etapas, falsos descartes con tabla de Poisson), `conflictos-con-la-spec-vieja.md` (25 conflictos con archivo:línea), `bugs-conocidos.md` (`engine/d8.py:334`, 9 pruebas rojas, límites del motor).
- `templates/`: `expediente-diario.md`, `propuesta-de-decision.json` (coherente con `contratos/decision.schema.json`; probado), `informe-de-cierre.md`.
- `scripts/`: `preparar_expediente.py` (lee la base **solo en lectura**, `mode=ro`), `proponer.py` (reglas de referencia **en sombra**: J3 del día 1 y alarma de cansancio 3 d contra 7 d), `validar_propuesta.py` (forma, respaldo del código y cifras copiadas), `probar_evals.py`.
- `evals/dorados/D01-D03` (día 1 sin venta con gasto cumplido ⇒ baja; sin gasto cumplido ⇒ mantiene; fatiga ⇒ relevo) y `evals/_base/umbrales_prueba.json` (valores de prueba, no firmados).
- `rubric.md` (C01-C12, R1-R8, simulaciones L3, lista de 16 sembrados por construir), `PEDIDOS.md` (20 pedidos a S-A y S-B).
- Agentes `.claude/agents/d8-maker.md` y `d8-qa.md` (el Maker no llama a ninguna herramienta de Meta que escriba; el QA es solo lectura).
- Pruebas: `tests/skills_d8/` (`.venv/bin/python -m unittest discover -s tests/skills_d8 -t . -p "test_*.py"`).

**Decisiones propias a ratificar** (todas `[SUPUESTO]`, en `references/decisiones-y-umbrales.md`): 90 % de gasto cumplido, 2 días de entrega incompleta antes de pausar, espera de 9 h tras el cierre, definición de «venta» (cualquier pedido pagado, atribuido o no) y de «día» (día de cuenta; el parcial no cuenta), la baja es de la campaña completa, dos guardias extra que solo pueden evitar una baja (conexión de landing y datos obsoletos), la ventana móvil 3 d contra 7 d de JPS con los umbrales de la spec vieja, y no pausar al anuncio fatigado.

**Hallazgos de esta forja** (documentados, no corregidos): `engine/d8.py:334` consulta una columna inexistente; el motor excluye de la evidencia los últimos 3 días (el día 1 es invisible para `engine.d8`); `gasto_efectivo` inflaría la salvaguarda de J3; con J4 y un CBO de 75 USD caben **2** lanzamientos simultáneos (el guard suma máximos teóricos), no 4; fijar `gasto_total_test_por_oferta` en 1 día pausaría a los ganadores el día 2; el «dry-run» de `orq ciclo-d8` migra la base. Detalle y pedidos: `references/bugs-conocidos.md`, `references/conflictos-con-la-spec-vieja.md`, `PEDIDOS.md`.

**Qué falta para 1.0.0**
- [ ] Corrida manual del dueño con una oferta real (7 días en modo sombra: el motor propone, el dueño actúa) + retro de 30-45 min; observaciones del panel `Pulido` convertidas en casos de eval.
- [ ] Resolver o aceptar por escrito los `PEDIDOS.md` P0 (P-02, P-04, P-05, P-06, P-07, P-11, P-13) y los `[SUPUESTO]` de J3.
- [ ] Construir los 16 sembrados (`rubric.md` §5) y calibrar `d8-qa` corriendo el agente real (≥ 90 % de BLOQ, dorados al 100 %, 0 falsos bloqueos).
- [ ] ≥ 2 casos de otro macro-nicho e idioma corridos con y sin la skill (Sonnet y Haiku); segunda oferta real sin retoques.
- [ ] `d8-maker` y `d8-qa` probados con herramientas mínimas en el runner; el runner genera `qa/.l1/d8-v<n>.json`.
- [ ] Retirar o contrastar `scripts/proponer.py` cuando `engine/d8.py` tenga J3 y FT.
- [ ] DoD de `docs/03` §2.6 firmado por el dueño; registro de la versión 1.0.0 aquí con fecha, evidencia y nivel de autonomía alcanzado.

## Registro de promoción (formato de `.claude/skills/README.md`; una fila por versión, nunca se borran filas)

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-07 | — | — | — | generada desde la spec, J1-J21 y el informe de brechas 02; pruebas de scripts en verde; sin corrida real |
| 0.1.1 | borrador sin pulir | 2026-11-07 | — | — | — | costuras con D7, D9, D6 y D10; sin corrida |
