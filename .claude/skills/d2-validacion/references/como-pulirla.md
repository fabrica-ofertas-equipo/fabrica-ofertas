# Cómo pulir D2 (para el dueño) y checklist de 0.1 a 1.0

> **v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min).** Método: a mano → pulir → skill → el agente la usa (backbone §2.5; `docs/03` §2).

## 1. Cómo correr la primera vez (≈ 45 min de máquina + ≈ 30 de lectura y verificación tuyas; ≈ 40 si amplías a 5 snapshots)
1. Abre la pestaña Code en `<carpeta del proyecto>` y elige un candidato **real** (otro macro-nicho que el de `ofertas/_ejemplo/`) y un `locale` que M1 tenga como hipótesis. Pega el §10.1 de la spec o pide «ejecuta la skill d2-validacion»; responde las 6 preguntas bloqueantes de `preguntas-abiertas.md`.
2. Deja que el Maker siga la **rutina de `protocolo-biblioteca.md` §4** (R0-R9). Tú intervienes en **H1** (leer snapshots con la hoja) y **H2** (verificar la tabla del informe). **Cronometra** ambos.
3. Cuando termine, corre la **retro** (30-45 min, el mismo día): pide a Code el «MODO RETRO» de `docs/03` §2.3 (ediciones por categoría, reglas candidatas con ✔, preferencias, errores que un script habría detectado, criterio implícito, ≥ 10 sembrados).

## 2. Qué mirar en la corrida (las preguntas de criterio de la spec §10.2)
- ¿Qué «sostenido» no lo es al abrir el snapshot? (concepto repetido, anuncios clonados, producto distinto del que decía el título).
- ¿Qué «independientes» son el mismo embudo traducido o el mismo dominio? (`operador_id`, `motivo_clustering`).
- ¿Qué término **nativo** halló lo que otro no? ¿El término literal daba 0 y el de jerga regional no?
- ¿Suenan a persona del país las frases? ¿Cada cita se reproduce abriendo el enlace y está en el crudo?
- ¿Sobreviven el hueco y el MU a «¿por qué nadie lo hace ya?» (¿un fracaso previo, un sustituto gratis, un chatbot?) y el ángulo seguro **conserva el deseo** del cliente?
- ¿La hoja de lectura se podía rellenar en el tiempo previsto? ¿Qué campo faltaba siempre? ¿Qué enlaces ya no abrían?
- ¿Los competidores del informe se verifican en ≤ 15 min? ¿Algún enlace no está en el crudo (inventado)?
- Calibra `IS`, `umbral_ss` y `mecanismo_share_*` con ≥ 10 nichos conocidos (spec §10.2).

## 3. Qué anotar en la bitácora `Pulido` del panel
Una línea por observación, con la etiqueta de `docs/03` §2.2: `[error]` hecho o cálculo mal · `[regla]` criterio que quieres siempre · `[pref]` gusto tuyo · `[riesgo]` política/dinero · `[contexto]` solo para este caso. Más, siempre: minutos reales por paso (R2, R6, H1, H2), nº de enlaces que no abrían, nº de competidores verificables, qué pidió el Maker que no debía, y `origen_version` de cada artefacto que editaste (`humano`).

## 4. Checklist de paso de 0.1 a 1.0.0 (todo ☐ antes de promover; los ★ son innegociables)
- ☐ ★ **3 corridas manuales** del dueño (≥ 2 macro-nichos, ≥ 2 idiomas, ≥ 1 sin GO), cada una con retro de 30-45 min; el dueño acepta ≥ 2 sin edición sustantiva.
- ☐ ★ `validacion.json` válido contra `contratos/validacion.schema.json` (`scripts.validar_esquemas`) en el 100 % de las corridas; sin ROJO avanzando y sin afirmaciones de rentabilidad.
- ☐ ★ **W8**: en una oferta real, `anuncios_competencia.json` trae ≥ `competidores_verificables_min` competidores con promesa, mecanismo y enlaces que el dueño verifica en ≤ `tiempo_verificacion_dueno_max_min` (medido y anotado); `verificar_competidores.py --crudo` en verde.
- ☐ ★ `metricas.py` y `qa_recomputar.py` coinciden con **diferencia 0** en los dorados **reales**; pruebas de `scripts/tests` en verde; vectores 0,233 y 0,675.
- ☐ ★ **QA calibrado**: detecta ≥ 90 % de los bloqueantes sembrados (siempre **S12** y **S15**) en 3 corridas con sembrados rotados; da PASS a los dorados; 0 falsos bloqueos; muestra rotada de `casos-frontera.yaml`: 0 falsos verdes.
- ☐ ★ **Seguridad**: la prueba de inyección pasa (eval 12 y S12); sin secretos; acciones externas en `deny`; el Maker no usa Bash fuera de los scripts de D2.
- ☐ **Dorados**: el dueño aprueba ≥ 1 GO, ≥ 1 GO_CONDICIONAL y ≥ 1 NO_GO (≥ 2 idiomas y macro-nichos) y reemplazan a los sintéticos de `evals/dorados/`.
- ☐ **Evals**: ≥ 6 casos con skill > sin skill en cada uno (Sonnet y Haiku); el caso de otro idioma pasa sin editar la skill entre casos; 3 corridas del mismo caso dan la misma decisión clave en ≥ 2 de 3.
- ☐ **Parámetros**: el dueño aprueba `parametros_d2.propuesta.yaml` y se integra a `empresa/parametros.yaml` (+ `parametros.schema.json`); `max_consultas_biblioteca` y `costo_max_validacion` fijados en `limites.yaml`.
- ☐ **Dependencias críticas** de `dependencias.md` (#3-#5, #11, #12, #20; #1 y #10 ya resueltas) resueltas o con sustituto aceptado por escrito.
- ☐ **Ciclo y costo**: ≈ 45 min de máquina y ≤ 30-40 humanos en tope (`orquestador.timeout_etapa_min.D2`; `max_budget_por_corrida_agente`), registrados en `costos.jsonl`.
- ☐ **Forma**: `SKILL.md` < 500 líneas, `description` < 1.024 caracteres, referencias a un nivel, sin ejemplos fuera de salud, relaciones o dinero, sin el nicho del video.
- ☐ `CHANGELOG.md` 1.0.0 con lo que NO cubre, tag `skill/d2-validacion/v1.0.0` y etapa D2 en N1 en `empresa/autonomia.yaml` (solo tú lo asciendes).
Si se agota el tiempo y fallan solo ítems no ★: `v0.9` con la deuda escrita y volver con datos.

## 5. Reglas de oro mientras la pules
Cada cambio de la skill nace como un **caso nuevo** en `evals/` (eval primero). No toques los scripts: pide el cambio y se aplica por PR. Si una regla es solo preferencia tuya, va a tu perfil, no a la skill.
