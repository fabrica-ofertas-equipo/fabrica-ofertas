# Comandos: qué existe hoy y qué sigue `[PENDIENTE]`

Convención: se escriben con `.venv/bin/python -m …` desde la raíz del repositorio. **El agente dice el comando exacto; no lo ejecuta** (salvo las lecturas marcadas ◐). Códigos de salida: 0 correcto · 1 interno · 2 uso · 3 validación · 4 bloqueado (entorno, PAUSA, infra, aprobación) · 5 límite excedido o dato de límites/parámetros faltante · 6 externo. Con `--json` los comandos de `engine.orq` imprimen `{ok, modo, codigo, datos, avisos}`. `--raiz` y `--ahora` no existen con `FABRICA_ENTORNO=produccion`.

Leído del código el 2026-11-06 (`engine/orq.py`, `engine/propuestas.py`, `engine/limites.py`, `engine/guard.py`, `engine/registro.py`, `engine/factibilidad.py`, `scripts/nivel_riesgo.py`). Si el motor y esta tabla difieren, **manda el motor** y se registra el conflicto.

## 1. Lecturas (◐) y ayudas que existen hoy

| Comando | Qué hace | ◐ |
|---|---|---|
| `python -m engine.orq estado --oferta OF [--json]` | `{fase, pausa, etapas{etapa: estado}, gates_pendientes[]}` | ◐ |
| `python -m engine.orq siguiente --oferta OF [--json]` | próxima etapa ejecutable (`null` si no hay) | ◐ |
| `python -m engine.limites estado [--operacion OP] [--raiz R] [--json]` | ¿alcanzan los límites para `OP` (`gastar`, `activar`, `descubrir`, `escalar`…)? 0 · 5 | ◐ |
| `python -m engine.guard comprobar --operacion OP [--oferta] [--monto] [--moneda] [--sello] [--cuenta JSON] [--modo live\|fixture] [--json]` | evalúa los 7 pasos del guard y dice cuál falla (sin `FABRICA_ENTORNO=produccion` queda BLOQUEADO en «entorno») | ◐ |
| `python -m engine.registro verificar [--json]` | cadena de hashes y anclas de `empresa/registro.jsonl` | ◐ |
| `python -m scripts.nivel_riesgo --P P2s --C C1 --E E0 --N N1 [--zona-gris] [--reencuadre] [--fuera-de-macro] [--json]` · `--suite ARCHIVO` | nivel de riesgo por candidato (`nivel` en minúscula, `subnivel` A\|B, `colores`, `veredicto_riesgo`); `nivel` es `None` fuera de macro-nicho. No importes este módulo desde `validar_esquemas.py` ni `verificar_hwr.py` (tres implementaciones independientes por diseño) | ◐ |
| `python -m engine.factibilidad calcular --entradas ARCHIVO [--parametros] [--limites] [--salida]` · `verificar --economia ARCHIVO` | economía única de D3 (no es de O0; la cita) | ◐ |
| `python -m scripts.validar_esquemas [esquemas\|ejemplos\|oferta DIR\|limites ARCHIVO --operacion OP\|parametros ARCHIVO --operacion OP]` | valida contratos y ofertas completas | ◐ |
| `python -m compliance.lint_claims` · `compliance.html_checks` | chequeos de claims y HTML (de X1/D5/D6, no de O0) | ◐ |
| `python -m scripts.preflight` · `python -m scripts.pausar` | preflight de infraestructura · capa 2 del kill switch | el dueño, nunca el agente |

`engine.estado` es librería (sin CLI): solo `engine.orq` escribe `estado.json`.

## 2. `engine.orq`: los 13 subcomandos tal como están hoy

Todos aceptan `--raiz`, `--ahora`, `--live` y `--json`. «Quién» = quién lo corre; «efecto» = lo que escribe o mueve.

| Subcomando | Flags reales | Quién · efecto | Límites reales de hoy |
|---|---|---|---|
| `crear` | `--brief RUTA` | dueño · escribe `ofertas/<id>/00-brief.yaml` y `estado.json` | El brief debe venir **ya firmado y sin `oferta_id`/`familia_id`/`creado_en`**: asigna `OF-AAAAMM-NN` y `FAM-AAAAMM-NN` (aquí **nace el ID**, tras el gate H del brief), idempotente por `hash_contenido_brief`. Solo valida esquema, moneda = `moneda_limites` y países ∈ `paises_permitidos` (5 si fallan). **No** verifica hash ni firma del brief (LT-54), ni PAUSA, riesgo, techos, locale, cuenta, ni copia el snapshot de D1 `[PENDIENTE: SB-8]` |
| `estado` · `siguiente` | `--oferta` | lectura | ver §1 |
| `ejecutar` | `--oferta --etapa Dn --modo {dry-run,fixture,live} [--fixture DIR]` | dueño/motor · promueve la etapa y aplica el gate | **Solo corre `--modo fixture --fixture DIR`** (rondas grabadas: `ronda-N/salida/` + `qa.json`). `--modo dry-run` y `live` se rechazan (salida 4) hasta que `agentes.runner` se integre `[PENDIENTE: SB-9]` |
| `firmar` | `--oferta` `--etapa Dn` (con `--accion aprobar_etapa`, el defecto) o `--accion A` (sin `--etapa`) **`--hash-objetivo SHA256`** **`--clave-privada RUTA`** `[--como dueno] [--nonce N]` | **dueño**, en su terminal · firma Ed25519 y escribe `empresa/ordenes/<nonce>.json` | `--hash-objetivo` y `--clave-privada` son **obligatorios**. La ruta de la clave la pone el dueño: **nunca en un chat ni en el repositorio**. El hash de una etapa es su `hash_salida`. Un nonce es de un solo uso. La orden no admite `etapa: O0` (`comunes.etapa_oferta`): la firma del brief es `[PENDIENTE: LT-54]`. Tras firmar, **se repite** el mismo `ejecutar`/`ingresar` para que el motor aplique la orden |
| `ingresar` | `--oferta --etapa Dn --desde DIR [--origen {humano,sesion_code}]` | dueño · valida con el mismo esquema, promueve a `vN` y aplica el gate | Rechaza symlinks y rutas fuera de lo sellado. Con gate A/S aprueba; con gate H queda `pendiente_firma` hasta que exista la orden. `--origen` se acepta pero **no se propaga** (el ingreso queda `humano`) y los costos manuales **no** se asientan en `empresa/costos.jsonl` `[PENDIENTE: SB-10]` |
| `nivel` | `--oferta --etapa Dn --a N1\|N2 --evidencia RUTA [--como dueno]` | dueño · asciende un nivel por llamada | Solo asciende (el descenso es automático, fuera de la CLI). Hoy no exige la orden firmada `ascender_nivel` |
| `activar` | `--oferta --object-ids … --hash-config … [--live]` | dueño/motor · `guard` y paso de fase | **`--live` no está integrado**: la CLI lo rechaza (salida 4, `meta.activar` es B5). Sin `--live` **simula** el guard y mueve la fase a `en_test` sin tocar Meta: no es una forma de activar |
| `ciclo-d8` · `veredicto` · `cerrar` | `--oferta` | motor · lectura diaria; veredicto; fase final y post-mortem | existen (`engine.d8`, `engine.cerrar`) |
| `pausar` | `[--oferta]` | dueño · crea `empresa/PAUSA` y pausa la oferta | efecto inmediato |
| `reanudar` | — | — | **No está en la CLI**: la CLI responde «use la API de Python». Solo existe `engine.orq.reanudar(firma_verificada=…, infra_verde=…)` como función |

## 3. Límites de dinero: `engine.propuestas` (no existe `engine.limites proponer|sellar`)

| Comando | Qué hace | Quién · efecto |
|---|---|---|
| `python -m engine.propuestas proponer --oferta OF [--multiplos 10 15 25] [--corridas N] [--semilla N] [--json]` | simula 5 escenarios por múltiplo del CPA de equilibrio y escribe `empresa/propuestas/limites.propuesta.yaml`; **no** toca `limites.yaml` | dueño · escribe local. Exige `ofertas/<id>/03-oferta/economia.json` (D3); sin él sale 4 |
| `python -m engine.propuestas sellar [--propuesta RUTA] --como dueno [--live] [--clave-privada RUTA] [--json]` | verifica la propuesta, calcula el sello y, **solo con `--live`**, escribe `empresa/limites.yaml` | **dueño**, en su terminal. Es el **único escritor** de `limites.yaml`. `--live` exige `FABRICA_ENTORNO=produccion`; sin `--live` es dry-run. La ruta de la clave la pone el dueño |

## 4. Ayudas de esta skill (solo lectura, sin red, con pruebas)

| Comando | Qué hace |
|---|---|
| `.venv/bin/python .claude/skills/o0-orquestador-portafolio/scripts/validar_brief.py BRIEF [--limites …] [--autonomia …] [--candidatos … --candidato CAND-NN] [--presupuesto-test-min N] [--calcular-hash] [--json]` | valida el borrador **en seco** (esquema, hash, moneda, límites, nichos, mercado, candidato); 0 · 2 · 3 · 5; **no crea nada ni asigna ID**. Es la validación previa al gate H; `orq validar` (el mismo chequeo dentro del motor) es `[PENDIENTE: SB-8]` |
| `.venv/bin/python .claude/skills/o0-lanzar-oferta/scripts/proximo_paso.py --oferta ID [--autonomia RUTA] [--json]` | próximo paso, gate efectivo y comando con los flags reales; ayuda más detallada que `orq siguiente` (que manda si difieren) |
| `.venv/bin/python .claude/skills/o0-lanzar-oferta/scripts/bloqueos_dueno.py [--oferta ID] [--estricto] [--json]` | decisiones del dueño que bloquean, derivadas de los archivos reales |
| `…/scripts/test_validar_brief.py` · `…/o0-lanzar-oferta/scripts/test_proximo_paso.py` · `…/test_bloqueos_dueno.py` | pruebas de las tres ayudas |

## 5. Orden del lanzamiento de una oferta (qué comando, cuándo)

1. Entrevista y borrador (`validar_brief.py --calcular-hash`) → 2. **validación en seco** (`validar_brief.py …`; no crea nada) → 3. QA del brief y **gate H del dueño** → 4. `orq crear --brief <RUTA del brief firmado>` (el ID nace aquí) → 5. cadena D1…D7 con `orq siguiente`/`ingresar`/`ejecutar` y `orq firmar` en cada gate H → 6. `orq activar` (acción aparte, H; `--live` `[PENDIENTE: B5]`).

## 6. Cómo habla el agente de un comando

Siempre: el comando completo y copiable, **quién lo corre** (dueño en su terminal / motor), **qué efecto tiene** (lectura, escribe local, mueve dinero, firma) y si usa algo que la CLI aún no tiene (`[PENDIENTE]`: `ejecutar` dry-run/live, `activar --live`, `reanudar`, `orq validar`). Un `firmar` lleva `--hash-objetivo` y `--clave-privada <RUTA_QUE_PONES_TÚ>`; **nunca** una clave, un token ni una ruta de clave privada real. Con `PAUSA`, ningún comando con efecto.
