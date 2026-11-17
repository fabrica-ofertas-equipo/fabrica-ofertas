# CHANGELOG — d7-campanas-meta

v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min)

Formato SemVer. Todo cambio de esta skill exige H del dueño (`accion:cambiar_skill`).

## 0.1.2 — 2026-11-07 — traspaso a D8 con la skill `d8-optimizacion`
Sigue siendo **v0.1 sin pulir**. Origen: integración de costuras entre etapas (2026-11-07).
**Aplicado:** `SKILL.md` paso 13 «Traspaso a D8»: D8 asume con la skill `d8-optimizacion` (modo LANZAMIENTO, regla J3), trabaja solo en `ofertas/<id>/08-operacion/` y lee `07-campana/{campana,traspaso}.json`; D7 no decide qué apagar ni escalar y no escribe en `08-operacion/`; los relevos y rechazos que pida D8 vuelven a D7 solo como fase `REFRESCO`.
**Falta** lo de la 0.1.1 (`dependencias.md` C.11: el motor no escala un lanzamiento inestable).

## 0.1.1 — 2026-11-06 (ajustes por la ingesta de S-A: SC-1…SC-9 y SC-16)

Sigue siendo v0.1 sin pulir. Fuente: `docs/_historial/ingesta-skills-cierre.md` §1 (D7) y §3.2. Sin corrida manual ni contacto con Meta.

- **SC-16 / SC-2 (evidencia viva).** El QA lee `07-campana/preflight.json`, `07-campana/lectura_viva.json` (existe `meta.lectura_viva`) y el informe L1 `qa/.l1/d7-v<n>.json`, todos de código; las `LECTURA_*` del Maker pasan a ser bitácora sin valor probatorio; sin `lectura_viva.json` la «evidencia viva ausente» es MAYOR (`d7.py lint`: C02 `evidencia_viva_ausente`, C03/C14 `evidencia_viva_incompleta`, C01 si su `hash_config` no es el de `campana.json`; sembrados nuevos S23 y S24). `[PENDIENTE: SB-12/SB-6]` `engine.orq` aún no los entrega, y `lectura_viva.json` no trae `effective_status`, DSA ni `active_errors`.
- **SC-16 (refresco).** `dependencias.md` reescrito contra el código real (A1, A3, A4, A5, A6, A8, A11, A13, A14 y C1–C3, C7, C8; B1, B2 resueltos); `alta-por-oferta.md` alineado con los 11 pasos de `infra/plantillas/alta-oferta.yaml` y `alta.json` como puerta; `mcp-api-y-herramientas.md` §4 con los CLI reales de `meta.*` y `engine.orq`; `riesgo-cuota-por-nivel.md` con `scripts.nivel_riesgo` y las claves de `limites` 1.3.0 (`null` = solo verde); `SKILL.md` §9 y `como-pulirla.md` §4: C-04 abierta, **gate efectivo H** hasta que el dueño decida K-02/D-02.
- **Código.** `scripts/d7.py presupuesto` fallaba por una firma obsoleta; ahora delega en `meta.payloads.calcular_presupuesto` (única implementación, con tarifa y `n_anuncios`) y conserva sus comprobaciones. C13 usa `nivel` en minúscula y `subnivel` del snapshot si existe o, si no, ≥ 2 amarillos = B `[SUPUESTO]`.
- **SC-1.** El QA no corrige: `correccion` por hallazgo (`devuelto_al_maker`), `cambios_aplicados = []`; el Maker aplica el parche en la ronda siguiente. D7 no tenía `aplicar_parche` ni `scripts/qa/*`.
- **SC-3.** `scripts.nivel_riesgo` como fuente; sin regla «todo amarillo = B». **SC-4.** `d7-maker` conserva solo lecturas de Meta (`ads_get_*` y `ads_account_get_activity_logs`, de solo lectura, para detectar deriva fuera del plan), sin `WebFetch`/`WebSearch`, con la familia de escritura de Meta en `disallowedTools`; `d7-qa` con `mcp__*` denegado. **SC-7.** Comandos reales de `engine.orq` (`firmar --hash-objetivo --clave-privada`, `ejecutar` solo fixture, `activar --live` y `reanudar` no están) y `compliance.lint_claims`. **SC-8.** `campana.umbral_qa` `[PENDIENTE: CT-4]`; no `qa_pass_promedio_min` ni `umbral_pass_qa`. **SC-9.** Nace v0.1; v1.0 exige corrida manual, retro y DoD firmados.
- **SC-5, SC-6: no aplican** (D7 no declara ranuras de `assets`, no usa Higgsfield y no escribe el libro de costos).
- **Conservado de S-A/S-B:** P07 informativo (decisión 15), contrato D7↔D8 (`ENTREGA_D7_INESTABLE`), C-04 abierta.

## 0.1.0 — 2026-11-06 (borrador)

Generada desde `departamentos/08-campanas-meta.md` (§3–§6, §10, Anexo) y el código real de `meta/`, `decision/`, `engine/guard.py`, `agentes/hooks/` y `contratos/`. Sin corrida manual del dueño, sin retro, sin contacto con Meta.

**Qué trae**
- `SKILL.md` (SOP de 14 pasos con criterio de «listo», reglas de decisión, qué nunca hace), `rubric.md` (C01–C15, R1–R8 con anclas, L3), 13 `references/`, `templates/` (campana, preflight, ids_meta, traspaso, aprobación de ejemplo, tarjeta de gate, formato de `lanzamiento.log`, hechos del preflight; los JSON validan contra `contratos/`).
- `scripts/d7.py` (presupuesto con tarifa y offset, nombres/URL, sellado de hash, validación, lint L1 C01–C15 parcial, envoltorio del preflight) y `scripts/probar_evals.py`; reproducen el ejemplo A3 (192 / 19,2 / 33,6) y convierten CLP con offset 1.
- `evals/`: dorados D01–D12 (salud it-IT con tarifa y DSA, mismo caso con presupuesto bajo, dinero pl-PL con candado alternativo, relaciones de-DE, amarillo-A con RHS pendiente, rojo, tracking caído, paquete con anuncios rechazables, CLP prepaga, A3, `NO_FACTIBLE`, prepago > 3 días) y sembrados S01–S22; 19 de 22 sembrados y 11 de 12 dorados son automatizables (`probar_evals.py`); S05, S13, S19 y D08 son para correr `d7-qa` y la sonda de hooks a mano.
- Agentes `.claude/agents/d7-maker.md` y `d7-qa.md` (QA solo lectura).
- Decisiones propias a ratificar: **D7 es dueño de la ventana T0 → T+72 h** (cierra el hueco «sin dueño» del monitoreo), `campana.json` se sella una sola vez, `gasto_esperado` = techo permitido por ventana, subnivel amarillo derivado de los ejes P, C, N, formato de `lanzamiento.log`.

**Qué falta para 1.0.0** (checklist completa en `references/como-pulirla.md`)
- [ ] Corrida manual del dueño con una campaña real y chica + retro de 30–45 min; observaciones de la bitácora `Pulido` convertidas en casos de eval.
- [ ] ≥ 2 casos reales de otro nicho e idioma corridos con y sin la skill (Sonnet y Haiku); segunda campaña real sin retoques.
- [ ] `d7-maker` y `d7-qa` probados con herramientas mínimas; sonda de hooks (`.claude/settings.json` instalado) con `deny` al 100 %.
- [ ] QA calibrado (≥ 90 % de BLOQ sembrados, dorados al 100 %, 0 falsos bloqueos) corriendo el agente real, no solo el lint.
- [ ] DoD de `docs/03` §2.6 firmado por el dueño y DoD de la spec §10.4 (dueño aprueba la tarjeta dos veces seguidas).
- [ ] Resolver o aceptar por escrito los `[PENDIENTE]` de `references/dependencias.md` (al 0.1.1 quedan: Transporte real de `meta.*` y `--modo live`, `firmar --object-ids` y `aprobacion.json`, disparador T+1…72 h y pausa por gasto en `engine.orq`/`meta.monitor`, `lectura_viva.json` y `qa/.l1/` entregados por `engine.orq`, matriz país × nivel y cuota en `engine.guard`, léxico `terminos_sensibles/<locale>`, `empresa/infra/meta.yaml`, esquemas de `alta.json`/`lectura_viva`/`lanzamiento.log`).
- [ ] Decisiones abiertas del dueño: `references/preguntas-abiertas.md`; contradicción **C-04** (`acciones_gate_humano` vs `contratos/gates.json`): gate efectivo H hasta que el dueño decida K-02/D-02; el segundo administrador (decisión 15) ya no bloquea.
- [ ] Pruebas `[VERIFICAR]` de plataforma en cuenta de prueba (PAUSA vs ACTIVO al publicar, macros en `link_url`/`url_tags`, anuncios programados, `age_max` con Advantage+).
- [ ] Registro en este archivo de la versión 1.0.0 con fecha, evidencia y nivel de autonomía alcanzado.
