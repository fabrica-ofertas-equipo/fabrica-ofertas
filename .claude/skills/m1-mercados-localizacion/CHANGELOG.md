# CHANGELOG — m1-mercados-localizacion

Versionado SemVer (backbone §5.1). Cada cambio de skill requiere aprobación del dueño (H) hasta N2.

## 0.1.1 — 2026-11-06 — ajustes por la ingesta de S-A (SC-1…SC-9, SC-17)

**v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD: corrida manual real del dueño, retro de 30-45 min y DoD firmado por el dueño; ninguna v0.1 se promueve sola).** Solo se aplicó lo cuya spec está CERRADA en `docs/_historial/ingesta-skills-cierre.md`; lo derivado quedó como `[PENDIENTE]` en `references/dependencias.md`.
- **SC-1 / M1-48:** el QA (`m1-qa`, `Read, Grep, Glob`) no corrige ni aplica parches: devuelve `correccion` por hallazgo (`devuelto_al_maker`) y `cambios_aplicados = []`; el Maker aplica el parche en la ronda siguiente (máx. `orquestador.max_rondas_qa`). `rubric.md` regla 4 y `templates/qa-m1.json` (sin `corregido_por_qa` ni cambios aplicados; validada contra `contratos/qa.schema.json`) y ambos agentes.
- **SC-2:** el L1 lo corre código y llega en `ofertas/<id>/qa/.l1/m1-v<n>.json`; sin él, «evidencia ausente» con la severidad del check; el QA no toma el L1 de lo que escriba el Maker. `chequeos_l1.py` (cabecera), `rubric.md`, `m1-qa.md`, `SKILL.md` S8-S9.
- **SC-3:** nivel y subnivel los emite `python -m scripts.nivel_riesgo` (M1 los lee, no clasifica); sin `subnivel` se deriva de los colores (un eje amarillo = a, ≥ 2 = b) `[SUPUESTO]`. **Niveles en minúscula** (`verde`, `amarillo-a`, `amarillo-b`, contrato `comunes#nivel_lanzable`) en `_comun.py`, `puntaje.py`, `semilla_exposicion.json`, propuesta de esquema, evals y referencias; `nivel_max_lanzable` `null` o ausente = SOLO VERDE (fail-closed); un valor fuera del enum sale con código 5.
- **SC-4:** sin web ni `mcp__*` para el Maker de M1 fuera del modo atlas y la sesión interactiva del dueño (`m1-maker.md`, `SKILL.md`); el QA ya no los tiene.
- **SC-5 y SC-6** no aplican a M1 (no produce `assets` ni libro de costos). **SC-7:** comandos reales solo donde M1 los cita (`engine.factibilidad calcular|verificar` en `dependencias.md` #8). **SC-8:** `mercados.umbral_qa` y `mercados.umbral_item_min_qa` reemplazan a `umbral_pass_qa` / `item_min_qa` (rúbrica, QA, fallback). **SC-9:** precisión de v0.1 y de v1.0 (corrida manual, retro y DoD firmados) en SKILL, rúbrica, pulido, agentes y este archivo.
- **SC-17:** eliminado `mult_cpm_si_cpm_vencido_min` (`chequeos_l1.py`, `vigencia.py`, `puntaje.py`, fallback): MQ-03M pasa con `[SUPUESTO]` en `cpm_fuente` y bandera `cpm_vencido`; `mult_cpm` central 1,2 y estrés 1,5 solo como sensibilidad, sin excluir mercados; plantillas coherentes (`mult_cpm_efectivo` 1.2, `r` 2.48 reproducido). `dependencias.md` reescrita (I1, I2, I7, I14 resueltas por R-C01; #6 y #12 inexactos; #8 `engine/factibilidad.py` existe pero no calcula `r`; derivados con su LT), `interfaz-d1.md`, `algoritmo.md`, `localizacion.md` (lee `producto.linguistica_muestreo_nativo_posterior`; `_comun.py` la lee del grupo `producto`). `preguntas-abiertas.md` P1: las 5 opciones se conservan; el par IT+PL en paralelo deja de ser la ruta (opción C = comparación excepcional si el dueño sube el parámetro) y la evidencia de datos propios del barrido queda como hipótesis.
- `autoprueba.py`: las 22 pruebas previas siguen en verde y se suman 3 (MQ-03M, `mult_cpm`, niveles en minúscula): 25 pruebas, 17/17 sembrados medibles.

## 0.1.0 — 2026-11-06 — borrador

**v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min).**

Generada desde `departamentos/16-mercados-localizacion.md` (§4-§6, §10, Anexos A-D) contra los contratos reales (`contratos/mercado.schema.json` 1.1.0, `candidatos`, `qa`, `limites`, `gates.json`) y `scripts/mercados/rank.py`.

Incluye: SKILL.md (modos S/A/L/T/G), 13 references, rúbrica R1-R8, 11 plantillas, 5 scripts probados (`puntaje.py` extiende `rank.py` con cobertura por fase, rama Managed Payments, EXPO y R1-R10; `vigencia.py`; `lint_locale.py`; `chequeos_l1.py` MQ-01…MQ-22; `autoprueba.py`: 22 pruebas y 17 sembrados medibles por script, todos en verde), 10 dorados y 18 sembrados, y los agentes `m1-maker` / `m1-qa`.

### Qué falta para 1.0.0 (checklist completo en `references/pulido.md` §4)
- [ ] Atlas v1 real: 15 países de 08 §2.2 + RO y FR con fuente+fecha+confianza (hoy `empresa/mercados/` no existe; las fichas de `evals/dorados/fixtures/` son de **ejemplo**); desglose de RO/FR en `rank.py`.
- [ ] Cobertura por fase correcta en PL e IT con fichas reales; reproducción de 08 y del escenario `corregido` (ya en verde con los datos actuales).
- [ ] QA calibrado: ≥ 90 % de los bloqueantes sembrados con 0 falsos PASS en una corrida real del `m1-qa` (L1 ya medido por script; D09 y etiquetas omitidas solo L2).
- [ ] Dos selecciones de práctica aprobadas por el dueño sin reescribir el razonamiento; 3 iteraciones, cada una con un país distinto.
- [ ] Evals con vs. sin skill (Sonnet y Haiku), 3 corridas por caso, corrida en sombra ≥ 80 %, prueba de inyección.
- [ ] Respuesta (o aplazamiento firmado) de las preguntas P1-P8 de `references/preguntas-abiertas.md` — en particular **P1: qué mercado se prueba primero**.
- [ ] Pedidos a S-A/X1/D1/D3 de `references/dependencias.md` (esquemas, parámetros `grupos.mercados`, `matriz_pais_nivel`, `limites.nivel_max_lanzable`, `engine.factibilidad`) y promoción de los scripts a `scripts/mercados/` con tests del repo.
- [ ] Resolución por sus dueños de las incoherencias I1-I14 de `references/dependencias.md` (esta skill las documenta y **no** las resuelve): Italia y Polonia en paralelo (docs/03) frente a `mercados_test_paralelos_max = 1`; R6 excluye Polonia con pagos diferidos; `empresa/mercados/atlas.json` inexistente; `scripts/mercados/` solo cubre 15 mercados (RO y FR fuera de `rank.py`); `precios_por_moneda[]` frente a `monedas_precio_adicionales`; firma de exposición fiscal frente al borrador; `mult_cpm` con CPM vencido frente a R9.
- [ ] Tag `skill/m1-mercados-localizacion/v1.0.0` por PR aprobado por el dueño (o `v0.9` con la deuda escrita).

### Decisiones de forja (a revisar al pulir)
- Fallback de parámetros `[SUPUESTO]` en `scripts/parametros_m1.fallback.json` (único lugar con números); `parametros.yaml` manda cuando existan las claves.
- Matriz de exposición = semilla del Anexo D (`scripts/semilla_exposicion.json`) hasta que X1 publique la suya.
- `mercado.seleccion.json` con esquema **propuesto** por M1; borrador de `mercado.json` tolera solo la firma de exposición fiscal pendiente del gate H.
- Esta v0.1 **no** genera el atlas ni escribe fuera de su carpeta de skill y de sus dos agentes.

## Registro de promoción (formato de `.claude/skills/README.md`; una fila por versión, nunca se borran)

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-06 | — | — | — | generada desde la spec |
| 0.1.1 | borrador sin pulir | 2026-11-06 | — | — | — | ajustes por la ingesta de S-A (SC-1…SC-9, SC-17) |
