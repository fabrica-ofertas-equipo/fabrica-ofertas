> **v0.1 sin pulir (borrador generado desde la spec; v1.0.0 exige corrida manual del dueño, retro de 30-45 min y DoD firmados por el dueño).**

# CHANGELOG — o0-lanzar-oferta

SemVer. Cada versión: qué cambia, qué falta para la siguiente.

## 0.1.2 — 2026-11-07 — recorrido completo con modelado y D8/D9/D10 (PENDIENTES A10)
Sigue siendo **v0.1 sin pulir**. Origen: `.claude/skills/modelado-oferta/PENDIENTES.md` sección A e integración de costuras. **No cambia gates ni autonomía** (J2 sigue pendiente en contratos: C-04 abierta).
**Aplicado:** `description` y §2 paso 2 (el candidato del Modo D llega con su plan v0); §**3b** (nuevo) con el recorrido «lanzar una oferta» paso a paso: D1 (desarme y plan v0) → M1 → D2 (7b inmersión) → modelado (plan v1, aprobación del dueño en `plan_mejora.json`, R-4) → D3 (modo `modelado`) → D4 → D5 con imágenes (J21: encargo → producción con Kie.ai → revisión ciega → integrar) → D6 → D7 → D8 / D9 / D10, cada uno con su gate existente de `gates.json`; «modelado» no es etapa de la máquina de estados y `proximo_paso.py` no la conoce (se añade en «Avisos»); plantilla del informe con la línea de modelado.
**Falta (bloqueado: S-A)** etapa o gate propio de modelado en `contratos/gates.json` y `estado.schema.json`; J2 (`activar_campana`).

## 0.1.1 — 2026-11-06 — ajustes por la ingesta de S-A (SC-1…SC-9, SC-18)

Sigue **v0.1 sin pulir**. Fuente: `docs/_historial/ingesta-skills-cierre.md` §1 «O0» y §3.2.

- **SC-7** `proximo_paso.py` emite comandos de la CLI real: `firmar` con `--hash-objetivo <hash_salida>` y `--clave-privada <RUTA_DE_TU_CLAVE_PRIVADA>` (nunca una ruta real); `ejecutar` solo `--modo fixture --fixture DIR` (dry-run/live `[PENDIENTE: SB-9]`); el brief sin firma no inventa un `orq firmar --etapa O0` (no valida: LT-54); `activar` avisa que `--live` no está en la CLI `[PENDIENTE: B5]` y que sin `--live` solo simula; `pausa` avisa que `reanudar` no está en la CLI; `ingresar` avisa que `--origen` no se propaga y los costos no se asientan (SB-10). 24 pruebas (las 20 previas, una con la aserción de `dry-run` cambiada a `fixture`, más 4 nuevas).
- **SC-18** C-04 reescrita: «gate efectivo = H hasta que el dueño decida D-02»; las seis acciones mínimas no se pueden quitar ni con firma (se retira «quita la acción con `engine.limites sellar`»); C-06 resuelta (spec de D1 v1.1: N0-N3 = H); la validación del brief no crea nada y `oferta_id` nace en `orq crear` tras el gate H (`orq validar` `[PENDIENTE: SB-8]`); `engine.limites proponer|sellar` → `engine.propuestas proponer|sellar` (`bloqueos_dueno.py` y su referencia; 9 pruebas verdes); tope diario del botón = `limites.boton_max_lanzamientos_dia` (en `limites`, valor del dueño; sin crear: LT-13); pedidos al panel (`POST /ofertas`, `GET /bloqueos`, forma única de `proximo_paso` `{motor_disponible, tipo, etapa, texto, comando}`) en `o0-orquestador-portafolio/references/dependencias.md` §F, sin tocar `dashboard/**`; `formato-de-salida.md` §4: la salida `--json` de `proximo_paso.py` no es idéntica a la del panel.
- **SC-3, SC-4, SC-9** `nivel_riesgo` existe; sin web ni MCP; el aviso «v0.1 sin pulir» dice que v1.0.0 exige corrida manual, retro y DoD firmados. SC-1, SC-2, SC-5, SC-6 y SC-8 no tocan a esta skill (es solo lectura y no tiene QA propio ni usa claves `umbral_*`).

## 0.1.0 — 2026-11-06 — borrador (sin pulir)

**Qué hay:** `SKILL.md` (`disable-model-invocation: true`; solo lectura; modos `nueva` y `OF-…`; informe fijo); `scripts/proximo_paso.py` (próximo paso, gate efectivo y comando exacto; sustituto de `orq siguiente`; 20 pruebas), `scripts/bloqueos_dueno.py` (bloqueos de decisiones del dueño derivados de los archivos; 9 pruebas); `references/` (formato de salida y tabla de decisión, bloqueos del dueño, contradicciones abiertas y sesión interactiva); `templates/informe-proximo-paso.md`; `rubric.md` (L1-L10); `evals/dorados` y `evals/sembrados`.

**Añadido tras la auditoría de pedidos (W3/W6, hueco 7):** registro de decisiones del dueño que bloquean (primer mercado, cuenta de Meta, límites, métodos de pago, líneas rojas) para que el panel los muestre como bloqueos visibles; documentación de C-04 y C-06 sin resolverlas; marca de etapas que exigen sesión interactiva (D1/D2 Biblioteca, D6 Higgsfield).

**Qué NO hay / es `[PENDIENTE]`:** `engine.orq` (todos sus subcomandos), `GET /bloqueos` y el botón `POST /ofertas` del panel, interfaz de D1 v2, tope diario de encolados del botón (sin clave en `parametros.yaml`). Evals no corridos; sin corrida manual del dueño.

## Checklist de paso de 0.1 a 1.0.0 (cada ítem con evidencia reproducible; nada es «cumple» sin ella)

DoD de `docs/03-plan-de-forja-de-skills.md` §2.6 y de la spec `departamentos/00-orquestador-portafolio.md` §10.4, más W3/W6 de `docs/_historial/auditoria-pedidos-primera-sesion.md`.

- [ ] **Corrida manual del dueño** con una oferta real en la pestaña Code, y **retro de 30-45 min** (`docs/03` §2.3: ediciones por categoría, reglas candidatas con ✔ del dueño, preferencias al perfil, checks L1 propuestos, ítems de rúbrica, 2 dorados y ≥ 10 defectos sembrados, ≤ 5 ambigüedades). Sin esto no se promueve; el DoD lo firma el dueño.
- [ ] **Contrato 100 %:** salida válida contra su esquema en todas las corridas (`python -m scripts.validar_esquemas`); sin `float`, sin secretos.
- [ ] **Determinismo:** los scripts de la skill con pruebas verdes (`scripts/test_*.py`) y paridad con el motor cuando exista (`orq siguiente` = `proximo_paso.py`; `orq crear` repite `validar_brief.py`).
- [ ] **Evals:** ≥ 6 casos (`evals/dorados/`: §10.5 de la spec + otro nicho + otro idioma), **con skill > sin skill** en cada uno, en Sonnet y en Haiku (si Haiku queda por debajo, se documenta).
- [ ] **Estabilidad:** 3 corridas del mismo caso, decisión clave igual en ≥ 2 de 3.
- [ ] **QA calibrado:** 100 % de dorados en PASS y detecta **todos** los BLOQ de `evals/sembrados/` (juego rotado para que no se memorice); 0 falsos bloqueos.
- [ ] **Aceptación en sombra:** el dueño acepta ≥ 2 de 3 casos sin edición sustantiva `[HIPÓTESIS]`.
- [ ] **Forma:** `SKILL.md` < 500 líneas, `description` < 1.024 caracteres, referencias a un nivel, costo de contexto anotado (`/skill-doctor`).
- [ ] **Seguridad:** prueba de inyección (texto hostil en una cita del banco) pasa; sin secretos; sonda de guardarraíles 100 % `deny`; acciones con efecto detrás de gate.
- [ ] **Costo:** corrida dentro de `limites.max_budget_por_corrida_agente`, registrada en `costos.jsonl`.
- [ ] **Sin sobreajuste:** cero menciones del nicho del video; el caso de otro idioma (`pl-PL`) y otro macro-nicho pasan sin editar la skill entre casos.
- [ ] **Cumplimiento** (ningún candidato ROJO llega a un brief aprobable; X1 puede vetar).
- [ ] **Motor presente:** `engine.orq`, `engine.estado` y `scripts/nivel_riesgo.py` ya existen; falta `portafolio.py`, `orq validar`, `ejecutar` real y `activar --live`, y que sus criterios B0 pasen; transiciones ilegales rechazadas y replay exacto; oferta ficticia D1→M1→D7 en N1; kill switch ≤ `parametros.orquestador.pausa_global_max_min` también con un barrido en curso.
- [ ] **Decisión del dueño D-02** (C-04: gate efectivo H hasta que decida; C-06 ya está resuelta), y la lista de PEDIDOS de `o0-orquestador-portafolio/references/dependencias.md` §B (esquemas `variante_de`, `radar`, `propuesta`).
- [ ] **Alternativa por API** documentada para los pasos de sesión interactiva (D1/D2 Biblioteca, D6 Higgsfield) que el motor usará desde N3.
- [ ] **El dueño aprobó** un brief y una propuesta semanal de ejemplo (dorados reales).
- [ ] **Congelar:** aprobación del dueño, registro de versión `1.0.0` aquí y en `skills_pin` (`orq nivel --etapa O0 --a N1`); desde entonces los cambios solo entran por el script de aplicación de X2 con su aprobación. Si faltan solo ítems no innegociables: `0.9` con la deuda anotada.
