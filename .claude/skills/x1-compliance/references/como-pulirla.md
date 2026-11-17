# Cómo pulir x1-compliance: de v0.1 sin pulir a 1.0.0

> **v0.1 sin pulir** (borrador generado desde la spec; v1.0 exige corrida manual del dueño, retro de 30-45 min y DoD firmados; no promover antes).

Método del dueño: **a mano → pulir → skill → el agente la usa** (`docs/03-plan-de-forja-de-skills.md` §2). Máximo **3 sesiones de 90 min** (spec 14 §10.2). X1 es de las skills que **clasifican riesgo** (D1, D3, D6, X1): además de la rúbrica se mide contra la suite y la retención (`docs/03` §2.5.3).

## 1. Qué hacer en cada sesión (corrida a mano en la pestaña Code)

**Sesión 1 — criterio y dorados (90 min).** Invoca `/x1-compliance` (Modo A) sobre un artefacto real o `ofertas/_ejemplo/` en lectura. Corre los 14 evals de `evals/dorados/minimos-10-5.json` (E01…E14) y los 17 de `legitimos-deben-pasar.json`. Mira **hallazgo por hallazgo**: ¿la cita es literal? ¿la corrección conserva el deseo? ¿bloqueó algo vendible?
**Sesión 2 — la suite y los sembrados (90 min).** `correr_evals.py suite-entrada` → clasificador ciego **con** y **sin** la skill → `correr_evals.py suite`. Corre el QA a ciegas sobre `evals/sembrados/sembrados.json` (rotando macro-nicho e idioma). Anota los falsos verdes y el sobre-bloqueo.
**Sesión 3 — idiomas, salud y cierre (90 min).** Corpus adversarial en voseo, tuteo, it y pl; series de salud; un dictamen de punta a punta con `compliance.sellar` **en dry-run** (sin `--live`) para ver qué rechaza (sin firma, con hash alterado, con lint ROJO). Retro de 30-45 min (§4).

## 2. Preguntas de criterio (las del dueño, §10.2)

1. ¿Esta regla **bloquea algo vendible** que un reencuadre salvaría? (¿qué legítimo bloqueó por el tema: embarazo, deuda, duelo, «madres», «prestiti»?)
2. ¿Qué **rechazo real** de Meta o Stripe **no habría cazado** esta skill? (cada rechazo real pasa a regla y a caso)
3. ¿La frase **sobrevive en italiano y polaco**? ¿el voseo y la jerga?
4. ¿Algún «verde» que **tú no habrías lanzado**? Es el defecto más caro: falso verde.
5. ¿El dictamen se lee en lenguaje de negocio y dice **qué cambiar**, no solo «no»?
6. ¿Cada hallazgo separa **norma / política oficial / prudencia propia**?

## 3. Qué anotar en la bitácora del panel (`Pulido`)

Una línea por observación, con categoría (docs/03 §2.2): `[error]` hecho mal · `[regla]` criterio que quieres siempre · `[pref]` gusto tuyo · `[riesgo]` política/legal/dinero · `[contexto]` solo este caso. Siempre: caso (id de eval o suite), hallazgo/regla afectada, **antes → después**, motivo con tus palabras. Ejemplos: «`[riesgo]` E02: el linter dio verde a “Perdé 8 kg”; el QA lo cazó; pedir regla de voseo» · «`[regla]` L08: “comida sana” no es promesa de cura» · «`[pref]` prefiero que el reencuadre siempre ofrezca dos opciones».

## 4. Retro (30-45 min, el mismo día; `docs/03` §2.3)

Ediciones por categoría; **reglas candidatas** con enunciado verificable, evidencia y contraejemplo (descarta las de una sola evidencia, salvo `[riesgo]`); preferencias → `perfil_dueno.md`, no a la skill; errores que **un script habría detectado** (candidatos a L1); tu criterio implícito reescrito como ítems de rúbrica con anclas; ejemplos nuevos (2 dorados y ≥ 10 sembrados); lo que sigue ambiguo (máx. 5 preguntas).

## 5. Checklist de paso de 0.1 a 1.0.0 (DoD de la spec §10.4 + docs/03 §2.6 + W3/W4 de la auditoría)

Marca cada ítem con **evidencia reproducible** (comando o archivo). Nada es «cumple» sin ella.

| # | Criterio | Cómo se mide | Hoy (0.1) |
|---|---|---|---|
| 1 | **Líneas rojas aprobadas por el dueño y cargadas** (`limites.lineas_rojas`) y `nivel_max_lanzable` | `grep lineas_rojas empresa/limites.yaml` no es `[]`; el dueño aprobó §2 y las líneas rojas | ☐ `[]` |
| 2 | **Clasificador de riesgo en código**: `scripts/nivel_riesgo.py` (promovido desde `nivel_ejes.py`; **una de tres implementaciones independientes por diseño**, junto a `validar_esquemas.py` y `verificar_hwr.py`: NO se unifican ni se importan entre sí, nota 25 §2.3), `contratos/taxonomia.yaml` `[PENDIENTE: no existe]`, matriz país × nivel | `python -m scripts.nivel_riesgo --suite docs/_historial/hwr-semillas/casos-frontera.yaml` = 0 discrepancias; los otros dos archivos existen | ☑ `nivel_riesgo.py` (S-B, 2026-11-06) · ☐ `contratos/taxonomia.yaml` (CT-3, LT-20; backlog A-02/S-21) · ☐ matriz país × nivel (LT-13; backlog S-13; CT-4) y su firma por el dueño |
| 3 | **Suite de casos de frontera** (230): legítimos pasan y peligrosos se bloquean o reformulan | `correr_evals.py suite`: **0 falsos verdes sobre rojos**, sobre-bloqueo ≤ 15 % y por debajo del filtro por tema (71 FP / 79 FN), concordancia por eje ≥ 90 % | ☐ no corrida con el LLM |
| 4 | **Retención**: 0 falsos verdes sobre ≥ 60 positivos, cota ≤ 5 %, anotada por dos personas, sellada por hash | `correr_evals.py retencion`; informar n y cota | ☐ `[PENDIENTE: lo sella el dueño]` |
| 5 | **Linter cubre las 30 líneas rojas sin falsos positivos en dorados** | `correr_evals.py codigo`: 0 FP en `legitimos-deben-pasar`; cobertura de las 8 categorías del corpus | ☐ 0 FP y 79/86 rojos vistos (7 falsos verdes del código: la cobertura no es total; revisor nativo pendiente) |
| 6 | **QA detecta 100 % de los sembrados L1 y ≥ 90 % de los ★** (juego rotado) | QA a ciegas sobre `sembrados.json`; contar | ☐ |
| 7 | **QA calibrado**: 100 % de dorados en PASS; 0 falsos bloqueos | `minimos-10-5` y `legitimos` | ☐ |
| 8 | **`compliance.sellar` rechaza** dictámenes sin firma o con hash alterado; `compliance.verificar` sale 4 | prueba manual en dry-run + `tests/compliance` | ☐ verificar |
| 9 | **Sello de recolección** bloquea una fuente roja sembrada (`E13`) | prueba | ☐ [PENDIENTE: S-B SB-15 (emisor `compliance.sellar_recoleccion`) y CT-4 (esquema)] |
| 10 | **Regla de salud** pasa las series simuladas | `regla_salud.py --series evals/salud/series.json` y `tests/compliance/test_salud.py` (paridad con `compliance/salud.py`) | ☑ oráculo y ejecutor (S-B B6c); ☐ falta `ratio_disputas_pausa` del dueño y la corrida diaria programada |
| 11 | `paises.yaml` de v1 con fuente y fecha o `[VERIFICAR]`, **aprobado con firma del dueño** (sin revisión legal humana) | archivo + firma | ☐ no existe |
| 12 | **Estabilidad**: 3 corridas del mismo caso dan la misma decisión clave en ≥ 2 de 3 | corridas | ☐ |
| 13 | **Con vs sin skill**: la skill supera la línea base en cada caso (Sonnet; Haiku si cabe) | evals | ☐ |
| 14 | **Otro nicho e idioma**: E14, L11-L14 pasan sin editar la skill entre casos; cero menciones del nicho del video | evals | ☐ |
| 15 | **Seguridad**: prueba de inyección (texto hostil en un competidor o página) no cambia el dictamen; sin secretos; acciones externas en `deny` | corpus de 10 textos hostiles | ☐ |
| 16 | **Forma**: `SKILL.md` < 500 líneas, `description` < 1.024, referencias a un nivel, JSON de templates válido | `.venv/bin/python -m unittest discover -s .claude/skills/x1-compliance/scripts -p "test_*.py"` (20 pruebas) + `correr_evals.py estructura` | ☑ |
| 17 | **Aceptación del dueño en sombra**: ≥ 2 de 3 casos sin edición sustantiva; 2 sombras seguidas ≥ 80 % de coincidencia y 0 `[skill-falla]` bloqueante | `docs/03` §2.7 | ☐ |
| 18 | **Concordancia con el dueño ≥ 90 %** (para N1→N2: 20 dictámenes) | dictámenes revisados | ☐ |

Si se agota el tiempo y solo fallan ítems **no innegociables**: `v0.9` con la deuda escrita en `CHANGELOG.md` y volver con datos. **Innegociables** (docs/03 §2.6): contrato válido, determinismo, QA calibrado, seguridad y, para X1, el ítem de cumplimiento (**0 falsos verdes en retención, con n y cota**, y que X1 pueda vetar). Congelar = PR aprobado por el dueño, tag `skill/x1-compliance/v1.0.0`, etapa en N1 en `autonomia.yaml`.

## 6. Cuándo se considera lista

Cuando los 18 ítems están ☑ o con deuda aceptada por el dueño por escrito, **y** el dueño corrió a mano al menos un dictamen de cada etapa (D2 consultivo, D3, D5, D6, D7) y el sello de punta a punta en dry-run. **v1.0 exige corrida manual, retro y DoD firmados.** Hasta entonces el runner **no** la promueve y el frontmatter dice «v0.1 sin pulir».
