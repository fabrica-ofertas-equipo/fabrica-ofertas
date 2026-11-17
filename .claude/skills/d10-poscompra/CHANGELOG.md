# CHANGELOG — d10-poscompra

v0.1 sin pulir (borrador generado desde la spec y las decisiones del dueño; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min)

Formato SemVer. Todo cambio de esta skill exige H del dueño (`accion:cambiar_skill`) una vez promovida; las v0.1 las edita quien las forja o las pule.

## 0.1.1 — 2026-11-07 — costuras D10→D5, D6 y D8
Sigue siendo **v0.1 sin pulir**. Origen: integración de costuras entre etapas (2026-11-07).
**Aplicado:** `SKILL.md` §7 tras INFORME, párrafo «Costuras (quién consume qué)»: **D10 → D5** (`prueba_social_real.json` lo escribe el código desde tu propuesta; D5 solo lo lee y omite el componente sin él); **D10 → D6** (reseñas reales con permiso y sin cifras de resultado; reembolsos y disputas por `adid`); **D10 → D8** (`senal_pausa.json` y reembolsos por `adid`; D10 nunca pausa); señales propias a D3/D4/M1/D1/X2. Versión alineada en `d10-maker.md` y `d10-qa.md`.
**Falta** lo de la 0.1.0 (`PEDIDOS.md`).

## 0.1.0 — 2026-11-07 (borrador)

Generada desde `departamentos/11-postcompra.md` **corregida con J1-J21** (J7/J16 oferta tras el pago, J8 y la nota tras J19 reseñas reales sin beta, J11 sin revisor nativo, J13, J20 Impulstienda pendiente), `docs/_historial/mentor-sistema/{know-how,mapeo,brechas/03-paises-tienda-cobro}.md` y el código real de `postcompra/`, `infra/workers/{fulfill,descarga,watchdog}`, `tracking/workers/webhook-stripe`, `landing/` y `contratos/`. Sin corrida manual, sin contacto con Stripe, Meta ni Kie, sin red, sin claves.

**Qué trae**
- `SKILL.md` (cuatro modos PAQUETE, BANDEJA, RESENAS, INFORME; 12 reglas duras; quién ejecuta qué y con qué gate), `rubric.md` (L1-01…L1-14, R1-R8, 14 simulaciones L3), 8 `references/` (`entrega-y-correo`, `oferta-tras-el-pago`, `soporte-y-bandeja`, `resenas-reales`, `disputas-y-vigia`, `impulstienda-pendiente`, `conflictos-con-la-spec-vieja`, `pedidos`), `PEDIDOS.md` (cambios que pide a S-A, S-B y otras skills, con archivo:línea).
- `templates/`: 12 correos (entrega, petición de reseña, recordatorio, reembolso) en pl, es y en; 12 respuestas tipo M01-M12 en pl, es y en; informe de poscompra; ejemplos de datos, reseñas sintéticas, `prueba_social_real.json`, orden y manifiesto.
- `scripts/d10.py` (stdlib: valida `prueba_social_real.json` contra lo que espera la landing, agrega reseñas con permiso, genera correos desde plantillas con escape, lint de plantillas, plan de entrega por línea, valida órdenes al código) y `scripts/probar_evals.py`; `tests/skills_d10/` (69 pruebas).
- `evals/`: dorados D01-D03 y sembrados S01-S15 (11 automatizables, 4 para el QA).
- Agentes `.claude/agents/d10-maker.md` y `d10-qa.md` (QA solo lectura).

**Hallazgos de la lectura del código (a `PEDIDOS.md`)**: `webhook-stripe` no llama a `fulfill` ni lee el correo; `fulfill` marca «entregado» antes de enviar y aunque el correo falle; asunto fijo en español sin identidad del vendedor; un solo `producto_sha256` (sin entrega por línea); `descarga` consume cuota con un GET; ningún código consume `postcompra.entrega_*` ni `soporte_*`; `postcompra.metricas` emite `senal_pausa` 1.1.0 (el esquema ya es 1.2.0); `prueba_social_real.json` no puede llevar el texto de las reseñas (esquema cerrado).

**Decisiones propias a ratificar**: la entrega del principal no espera a la oferta tras el pago; E1 (día 3) y E2 (día 7, único recordatorio) como petición de reseña automática a todos los compradores elegibles, con tres permisos granulares y sin incentivo; suprimir reembolsados/disputados/ticket abierto por estado objetivo y declarar la limitación; la respuesta que afirma una acción solo sale si el código aceptó la orden (`respuesta_alternativa`); campo `linea` propuesto en `producto.items[]` y `entrega`; `pedido_ref` derivado del `session_id`; diferir la secuencia E1-E3 de onboarding y todo marketing por correo.

**Qué falta para 1.0.0**
- [ ] Corrida manual del dueño: compra real propia + reembolso real (`accion:compra_real_minima`) con retro de 30-45 min; observaciones de la bitácora Pulido convertidas en casos de eval.
- [ ] Dos corridas más de macro-nichos e idiomas distintos (`es-ES` dinero, `it-IT` relaciones) con y sin la skill.
- [ ] `d10-maker` y `d10-qa` probados con herramientas mínimas; QA calibrado (≥ 90 % de los BLOQUEANTES sembrados, dorados al 100 %) corriendo el agente real.
- [ ] Resolver o aceptar por escrito los pedidos de `PEDIDOS.md`: P-01…P-10 (S-B), A-01…A-08 (S-A), C-01…C-02 (otras skills y `landing/`).
- [ ] Decisiones del dueño: proveedor de correo, razón social y dirección, `soporte@`, `politica_divulgacion_ia`, `correos_max_*`, `reembolso_auto_max`, gate de respuestas y de la petición de reseña, revocar el enlace al reembolsar, respuestas de Impulstienda (16 preguntas), capturas del tramo posterior a la compra del referente.
- [ ] Revisión de X1 de las plantillas (hash) y del texto de las casillas de permiso.
- [ ] Registro de 1.0.0 en la tabla de abajo, con fecha, evidencia y nivel de autonomía.

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-07 | — | — | — | generada desde la spec corregida con J1-J21 |
| 0.1.1 | borrador sin pulir | 2026-11-07 | — | — | — | costuras D10→D5, D6 y D8; sin corrida |
