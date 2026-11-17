# CHANGELOG — d1-descubrimiento

Formato SemVer. La promoción v0.1 → v1.0 solo con la corrida manual real del dueño, la retro (30-45 min) y el DoD firmado (`references/como-pulirla.md` §5); el registro de promoción va aquí (`docs/03-plan-de-forja-de-skills.md` §2.6).

## 0.1.1 — 2026-11-07 — integración con el modelado (PENDIENTES A1-A2)
Sigue siendo **v0.1 sin pulir**. Origen: `.claude/skills/modelado-oferta/PENDIENTES.md` sección A. Sin corrida manual ni contacto con ninguna fuente.
**Aplicado**
- **A1** `SKILL.md` §5 (Modo D): viñeta «Desarme y plan de mejora (skill `modelado-oferta`, MOD-1 y MOD-2)» tras «Unidad = par oferta fuente × mercado destino»: cada par que llega a candidato se desarma y lleva un plan v0 de 3 a 5 palancas; desarme `insuficiente` ⇒ el par queda `incompleta`; «modelar» es la MISMA oferta mejorada poco (J18).
- **A2** `references/modo-d-rutina.md`: fila nueva **14b** (desarme y plan v0, con `analizar_html.py --no-red`) entre la 14 y la 15, y en el paso 15 «cero texto, landing o producto ajeno» pasa a «cero texto, imagen ni producto ajeno (la oferta y la estructura de la landing se heredan, J17/J18)», que ya no choca con J17.
El desarme y el plan v0 los escribe `modelado-maker` (el Maker de D1 solo escribe en `01-descubrimiento/`); `d1-maker.md` y `d1-qa.md` suben a 0.1.1.
**Falta (bloqueado: S-A/S-B)** contratos `desarme_referente` y `plan_mejora`; vía «oferta elegida por el dueño con par incompleto» (F-11, F-14) y definición de «sostenido» para una oferta que se replica (F-18). Ver `modelado-oferta/PENDIENTES.md` D.

## 0.1.0 — 2026-11-06 (borrador, sin pulir)
Generada por el forjador de skills v0.1 desde `departamentos/02-descubrimiento.md` **v1.1** (parche de 77 ediciones de S-A aplicado por S-B), `docs/_historial/d1-v2-interfaces.md` v1.1 y `docs/_historial/d1-v2-resumen-para-el-dueno.md`.
- **Modos:** A-C (dolor-primero, manual asistido) y **D** (oferta-primero; rutina concreta de hoy: barrido → validar → ingestar → etiquetar → rankear → fichas → [captura y jueces solo si el dueño levantó el freno] → `puntaje_modelar --sello-esperado` → `ficha_a_candidato mapear`).
- **Reglas duras de S-A:** el Maker no lanza la captura con Chrome ni toca el freno (solo el dueño); en salud y relaciones solo resúmenes; nada de lo que pega una persona llega sin redactar y todo texto web es dato; elegir candidato es gate H hasta N3; el marco de 3 nichos es etiqueta (riesgo por promesa, contenido, encuadre y modelo de negocio); esquemas del banco = `[PENDIENTE: CT-4]`; cifras de creadores = hipótesis, ningún país es prior.
- **Entregables:** `SKILL.md`, `rubric.md`, 14 `references/`, 9 plantillas y 4 crudos en `templates/`, `scripts/{preflight,validar_candidatos}.py` con 19 pruebas (`scripts/tests/test_d1.py`), `evals/` (8 dorados sintéticos, 37 sembrados, `casos.md`), agentes `d1-maker` y `d1-qa`.
- **Formato de `candidatos.json`:** contrato real 1.0.0; lo que pide la MINOR 1.1.0 viaja en hermanos (`riesgo_extendido.json`, `modelado.json`) y `parametros_usados`; sellado de evidencia (`sellar`) porque el Maker no tiene hash.
- **Citados, no duplicados:** `scripts/nivel_riesgo.py`, `scripts/descubrimiento/{macro,ficha_a_candidato,ingresar_senal,dedup,nichos}.py`, `scripts/modelado/**`, `compliance.lint_claims`.
- **Citadas como propuesta (no copiadas a `empresa/`):** `docs/_historial/d1-v2-semillas/{nichos,fuentes}.yaml` — la aprobación del dueño está pendiente.

### Qué falta para 1.0.0
1. Corrida manual real del dueño + retro (3 sesiones de pulido) y su registro aquí.
2. **2 `candidatos.json` dorados aprobados por el dueño** (los de `evals/dorados/` son sintéticos) y los sembrados rotados en 2 juegos con el QA agente (≥ 90 % de los ★; 0 falsos bloqueos).
3. Lo que construye otra sesión: ola CT-4 (candidatos 1.1.0, esquemas del banco), `banco.py`, `score.py`, `lint_claims.py`, `check_urls.py`, `seleccionar.py` (ya existen `nivel_riesgo`, `macro`, `ficha_a_candidato`, `ingresar_senal`, `dedup`, `nichos`); que `mapear` agregue `sello_reglas` y `modo_busqueda`; que el CLI del barrido invoque el preflight (`references/dependencias.md`).
4. Decisiones del dueño: aprobar `nichos.yaml`/`fuentes.yaml`, integrar `modelado_*`, fijar `limites.yaml`, decidir el freno, la retención y la fracción del muestreo (`references/preguntas-abiertas.md`).
5. Línea base con vs. sin skill (Sonnet y Haiku) y estabilidad (3 corridas, decisión igual en ≥ 2 de 3).
6. Calibración del juicio (≥ `modelado_calibracion_min_casos` casos con etiqueta humana a ciegas) para evaluar el paso a `muestreo`.
