# `scripts/descubrimiento/` — D1c/D1d: camino crítico del Modo D

> Construido en la ola de la noche del 2026-11-06 (sesión D1c) y continuado la misma noche (ola 2,
> sesión D1d: freno por `via`, negación en la regla 5, orígenes reales de parámetros, sidecar 1.1.0 y
> `banco.py`). Fuente de verdad: `docs/_historial/d1-v2-interfaces.md` (v1.1, §2/§2.3/§2.4/§3.8/§3.8.1/
> §6.4/§8.6) y `departamentos/02-descubrimiento.md` (Modo D, §12-§17). Marco de riesgo:
> `docs/_investigacion/25-marco-salud-relaciones-dinero.md` §1-§2. No se tocó `scripts/modelado/**`
> (excepto `preflight_descubrir.py`, que SÍ es de este componente) ni `contratos/**` (de otras
> sesiones): se importan, nunca se editan.

## Propósito en una frase
La puerta de entrada de D1 a `candidatos.json`: clasifica el macro-nicho por deseo central (Q0-Q6),
calcula el riesgo por candidato, mapea una ficha ya puntuada del Modo D a un candidato válido contra
`contratos/candidatos.schema.json` 1.0.0, ingresa señales de voz del cliente con PII redactada, y el
preflight de solo lectura que el CLI del barrido puede llamar antes de gastar una consulta.

## Módulos

| Módulo | Qué hace | Estado |
|---|---|---|
| `macro.py` | Árbol Q0-Q6 (nota 25 §1.2) sobre la `prueba_una_frase` del producto propio. Heurística determinista por palabras clave (es/en/it/pl); suite de retención en `tests/fixtures/descubrimiento/macro_retencion.yaml` (69 positivos, 0 falsos verdes, 0 % falsos rojos). | Construido y probado (21 pruebas) |
| `ficha_a_candidato.py` | Puerta de §3.8.1 (12 reglas, 9 implementadas en código — 10-12 son del CLI/QA): mapea ficha `2.0.0` + juicio del Maker a un candidato 1.0.0. Usa `scripts.nivel_riesgo` (falla cerrado si no está) y `scripts.modelado.puntaje_modelar` (puntuación, sensibilidad; no se reimplementa). D1d: regla 5 con detección de negación por ventana (ya no veta "sin comunidad"), orígenes reales de `modelado_*`/`sim_dup_bloqueo` sin `--parametros`, y sidecar 1.1.0 con `sello_reglas`/`modo_busqueda`/`riesgo` ampliado por candidato. | Construido y probado (53 pruebas) |
| `ingresar_senal.py` | Redacción de PII (correos/teléfonos, incluidos ofuscados), `senal_id` determinista, categoría especial (salud/relaciones agregadas), escritura append-only en `empresa/descubrimiento/senales/AAAA-MM/<fuente>.jsonl`. | Construido y probado (26 pruebas) |
| `scripts/modelado/preflight_descubrir.py` | `comprobar_descubrir(raiz, env, via=...)`: PAUSA, freno de captura (solo con `via="captura_web"`, interfaces §6.4), infra VERDE, límites de "descubrir". Para que el CLI del barrido (otra sesión) lo llame. | Construido y probado (16 pruebas) |
| `nichos.py` | Validador de `nichos.yaml` (árbol macro→nicho→hoja, ids únicos, `macro_secundario`, `semillas_fuera_de_marco` nunca sembradas). | Construido y probado (13 pruebas, incluida la semilla real de 92 hojas) |
| `dedup.py` | `similitud_memoria` determinista (Jaccard de tokens sobre audiencia/resultado/obstáculo/formato); sustituto documentado del "modelo de embeddings local" que la spec pide y no existe. | Construido y probado (15 pruebas) |
| `banco.py` | Alta de problemas (`PRB-AAAAMM-NNNN` correlativo), grafo de estados/transiciones (§2.3), `pares_modelado[]`, índice derivado `banco.json` y caducidad (`descubrimiento.caducidad_banco_dias`, ausente ⇒ 5). Único escritor de `empresa/descubrimiento/problemas/` y `banco.json`. | Construido y probado (32 pruebas) |

Total: 176 pruebas en `tests/scripts/test_descubrimiento_*.py` (`unittest discover -p
"test_descubrimiento*.py"`) + 30 de `test_nivel_riesgo.py` (no editado, solo consumido) = 206 pruebas
verdes. No se tocó ninguna prueba de `scripts/modelado/` (167 pruebas combinadas de
`test_puntaje_modelar.py` + `test_juicio.py` + `test_nivel_riesgo.py` siguen en 0).

## CLI con ejemplos

```bash
# Clasificador de macro-nicho
.venv/bin/python -m scripts.descubrimiento.macro clasificar \
  --frase "de gastar sin control cada mes a ahorrar de forma constante" --senal-id-e3 abc123abc123 --json
.venv/bin/python -m scripts.descubrimiento.macro verificar tests/fixtures/descubrimiento/macro_retencion.yaml

# Puerta ficha -> candidatos.json (dry-run por defecto; --aplicar escribe)
# Sin --parametros: resuelve modelado_*/sim_dup_bloqueo por su hogar real bajo --raiz (D1d n.2c)
.venv/bin/python -m scripts.descubrimiento.ficha_a_candidato mapear pares.json --raiz . \
  --oferta-id OF-202611-01 --corrida-id RUN-20261106-01 --locale es-MX --paises MX \
  --modo-busqueda D --salida candidatos.json --rechazos empresa/descubrimiento/rechazos.jsonl \
  --aplicar --json
# Con --parametros: un solo YAML fixture que junta modelado_* y sim_dup_bloqueo (pruebas/diagnóstico)
.venv/bin/python -m scripts.descubrimiento.ficha_a_candidato mapear pares.json \
  --parametros tests/fixtures/descubrimiento/parametros_modo_d.yaml \
  --oferta-id OF-202611-01 --corrida-id RUN-20261106-01 --locale es-MX --paises MX \
  --salida candidatos.json --rechazos empresa/descubrimiento/rechazos.jsonl --aplicar --json

# Ingreso de una señal (dry-run por defecto; --aplicar escribe el .jsonl)
.venv/bin/python -m scripts.descubrimiento.ingresar_senal ingresar \
  --fuente-id youtube-comentarios --familia dolor --tipo-evidencia E3 --locale es-MX --pais MX \
  --url https://example.com/post --extracto "no se en que se me va el dinero cada mes" \
  --fecha-consulta 2026-11-06 --modo-captura asistida --capturado-por humano \
  --fuentes tests/fixtures/descubrimiento/fuentes.yaml --aplicar --json

# Preflight de solo lectura para el CLI del barrido (via obligatoria, sin valor por defecto)
.venv/bin/python -m scripts.modelado.preflight_descubrir --via conector --json
.venv/bin/python -m scripts.modelado.preflight_descubrir --via captura_web --json

# Validador de nichos.yaml y similitud de memoria
.venv/bin/python -m scripts.descubrimiento.nichos validar tests/fixtures/descubrimiento/nichos_semilla.yaml
.venv/bin/python -m scripts.descubrimiento.dedup calcular --candidato c.json --memoria m.json --json

# Banco de problemas (dry-run por defecto; --aplicar escribe)
.venv/bin/python -m scripts.descubrimiento.banco --raiz . crear --via oferta_primero \
  --locale-origen es-MX --problema "quiere ahorrar pero gasta sin control" --aplicar --json
.venv/bin/python -m scripts.descubrimiento.banco --raiz . transicionar PRB-202611-0001 \
  --a normalizado --aplicar --json
.venv/bin/python -m scripts.descubrimiento.banco --raiz . indice --aplicar --json
.venv/bin/python -m scripts.descubrimiento.banco --raiz . caducar --aplicar --json
```

Códigos de salida: convenciones §8 (0 ok · 2 uso · 3 validación · 4 bloqueado · 5 límite). Ningún
módulo usa red, LLM ni `--live`; `ingresar_senal`, `ficha_a_candidato mapear` y todo `banco` son
dry-run por defecto y solo escriben con `--aplicar`.

## Cómo probar
```bash
.venv/bin/python -m unittest discover -s tests/scripts -p "test_descubrimiento*.py" -t .
.venv/bin/python -m unittest tests/scripts/test_nivel_riesgo.py -t .          # no se editó, se consume
.venv/bin/python -m unittest tests/scripts/test_puntaje_modelar.py tests/scripts/test_juicio.py -t .  # comprobar que no se rompió scripts/modelado
```

## Entradas y salidas
- Entradas: `tests/fixtures/descubrimiento/{macro_retencion.yaml, fuentes.yaml, nichos_semilla.yaml,
  fuentes_semilla.yaml, parametros_modo_d.yaml}` (las dos semillas son copias de
  `docs/_historial/d1-v2-semillas/` — **nunca** se escribieron en `empresa/descubrimiento/`, son
  propuestas pendientes de aprobación del dueño). `contratos/candidatos.schema.json` 1.0.0 (vigente;
  importado, no editado).
- Salidas: `empresa/descubrimiento/senales/AAAA-MM/<fuente>.jsonl` (append-only, PII redactada antes
  de escribir); `candidatos.json` (esquema 1.0.0), su sidecar `<salida>.sidecar-1.1.0.json` y
  `rechazos.jsonl` (solo motivos canónicos), todos solo con `--aplicar`; `empresa/descubrimiento/
  problemas/PRB-AAAAMM-NNNN.json` y `empresa/descubrimiento/banco.json` (índice derivado), ambos solo
  con `--aplicar` de `banco.py` (único escritor).
- Variables de entorno: ninguna propia (no hay credenciales ni secretos en este componente).

## Decisiones (fail-closed ante dato o contrato faltante)
1. **`candidatos.json` 1.1.0 no existe todavía** (pendiente de CT, interfaces §8.1 n.1): se construyó
   contra el **1.0.0 vigente**. Los campos aditivos de §3.7 (`subnivel`, `ejes_codigo`,
   `version_tabla`, `banderas`, `macro_secundario`, `origen`, `transferencia`, `padre_id`, y en
   `evidencia[]` `senal_id`/`familia`/`locale`) se calculan y se usan internamente para las 9 reglas,
   pero se **recortan** antes de validar/escribir el documento final (viajaban en la clave interna
   `_riesgo_1_1_0`/`_origen` de cada candidato, descartada sin guardar en D1c). **D1d:** esos campos
   (consolidados en `_aditivos_1_1_0`, más `sello_reglas`/`modo_busqueda`) ya no se descartan: el CLI
   los extrae a un **sidecar** (`<salida>.sidecar-1.1.0.json`) antes de borrarlos del candidato final
   (ver decisión 4b). Pedido a CT sigue abierto: integrar la MINOR de verdad en el esquema.
2. **`linea_roja_de_contenido_o_negocio`, `duplicado_de_la_memoria`, `evidencia_insuficiente` e
   `inviable_sin_backend` no existen en `comunes#motivo_rechazo`** (pendiente de CT, interfaces §7,
   §8.1 n.2): un par que caería en esos motivos queda `vetada`/`no_pasa` con `motivo = None` (no se
   escribe en `rechazos.jsonl`, conserva su `estado_par`, interfaces §3.8.1 regla 11 último inciso).
3. **`nivel_max_lanzable` no existe en `limites.yaml`** (pendiente de CT, interfaces §5.1): ausente,
   solo pasa `verde` (fail-closed); con la clave presente (`{"macro_nicho": "nivel[-subnivel]"}`) se
   respeta el tope real.
4. **`descubrimiento.sim_dup_bloqueo` y los 36 `modelado_*` conviven en `grupos.descubrimiento` pero
   `parametros.schema.json` aún no tiene la `patternProperties` de la MINOR 1.2.0** (interfaces §5.2):
   `ficha_a_candidato` lee ambos grupos de claves con lectura directa de YAML (mismo estilo que
   `puntaje_modelar.cargar_parametros`), sin pasar por `engine.parametros` (que exigiría el esquema
   completo y rechazaría el archivo mientras conviven). Ver `_leer_sim_dup_bloqueo`.
   **D1d:** sin `--parametros`, el CLI ya no exige UN archivo con ambos: `sim_dup_bloqueo` se lee
   siempre de `empresa/parametros.yaml` (único hogar real) y `modelado_*` de ahí si el dueño ya los
   integró, si no del respaldo `scripts/modelado/parametros_modelado.propuesta.yaml`
   (`parametros_descubrimiento_reales`). Hoy (sin integrar) el camino real siempre cae al respaldo:
   verificado contra el `empresa/parametros.yaml` del repositorio.
4b. **`sello_reglas`/`modo_busqueda` por candidato (MINOR 1.1.0, §3.7) no caben en el esquema 1.0.0**
   (`additionalProperties:false`): a nivel documento viajan en `parametros_usados` (abierto en 1.0.0);
   por candidato viajan en un **sidecar** aparte (`<salida>.sidecar-1.1.0.json`, clave `candidato_id`,
   junto con `riesgo.{subnivel,ejes_codigo,version_tabla}` y `origen`), que el CLI escribe con
   `--aplicar` junto a `candidatos.json`. No se valida contra ningún esquema (no existe uno para el
   sidecar): es información de trazabilidad, no el contrato final.
4c. **La regla 5 (sin servicio/comunidad/en vivo) ya no veta por substring literal**: detecta negación
   por ventana comparando formas compactadas (sin tildes/espacios/guiones, resistente a ofuscación
   simple) y dejó de vetar "sin comunidad"; sigue vetando ante texto "mixto" (una mención negada y
   otra afirmada) -- fail-closed. Un campo estructurado opcional del juicio
   (`entregable_estructura.{servicio,comunidad_o_en_vivo}`) puede decidir directo si el Maker ya lo
   sabe con certeza; su ausencia o `false` NO relaja el chequeo de texto (sigue siendo la red de
   seguridad). No es análisis de lenguaje natural real: sigue siendo una heurística, ahora más difícil
   de evadir por accidente o por una frase negativa común.
5. **El `locale` BCP-47 completo lo resuelve M1** (`locales_activos.yaml#paises`, interfaces §3.8): acá
   `mercado.mercado` es el país ISO-2 de la ficha del Modo D; las reglas 5/6 comparan contra ese
   ISO-2, no contra un `es-MX` completo. Documentado como simplificación hasta que D1c reciba el mapeo
   de M1.
6. **El preflight de D1 no verifica la firma HMAC de `estado.json`** (a diferencia de
   `engine.guard.comprobar_live`, que sí la exige antes de `--live`): este preflight es de solo
   lectura para una operación que no gasta ni activa nada por sí misma; se documenta como alcance
   reducido, no como omisión accidental.
6b. **D1d: `via` es obligatoria en `comprobar_descubrir` (sin valor por defecto, interfaces §6.4)**:
   antes el freno de captura bloqueaba TODO (incluido el barrido por el conector, que no usa Chrome).
   Ahora `via="captura_web"` sigue bloqueado por el freno; `via="conector"` lo ignora, pero PAUSA,
   infra y límites siguen aplicando igual. Esto rompe cualquier llamador que invocara
   `comprobar_descubrir(raiz)` sin `via` (ver «Pedidos» -- `.claude/skills/d1-descubrimiento/`).
7. **`similitud_memoria` usa Jaccard de tokens, no un modelo de embeddings** (la spec pide uno
   "[VERIFICAR]" que no existe sin red ni dependencias nuevas): es un sustituto explícito, documentado
   en `dedup.py`.
8. **El clasificador de macro (`macro.py`) es una heurística de palabras clave, no un modelo de
   lenguaje** (scope: "código determinista, sin LLM"): su calibración es la suite de retención: 69
   casos positivos (es/en/it/pl), 0 falsos verdes, 0 % de falsos rojos (tope 5 %).
9. **D1d: `banco.py` construido** (alta/estados/índice/caducidad de `empresa/descubrimiento/`).
   Sin `contratos/problema.schema.json` (no existe, pedido a CT §8.1 n.3): solo valida sus propias
   invariantes mínimas (forma del `problema_id`, `estado` del enumerado, transición permitida), nunca
   inventa un valor para un campo que depende de otra etapa (macro, riesgo, mecanismo...). El grafo de
   transiciones (`TRANSICIONES_PERMITIDAS`) resolvió dos ambigüedades de la especificación de forma
   genérica, a falta de una regla explícita: `rechazado -> normalizado` como la única reapertura
   posible (interfaces §2.4 no dice a qué estado vuelve) y `vencido -> {vigente, archivado}` (el
   refresco de evidencia vuelve a `vigente`; sin refresco, a `archivado`). `ficha_a_candidato` sigue
   SIN integrarse con `banco.py` en un único comando de punta a punta (sería el pedido natural de la
   próxima ola): hoy son dos CLIs independientes que un orquestador (O0 o un script futuro) tendría
   que encadenar, pasando los `ResultadoPar` no-`pasa` de `ficha_a_candidato` a
   `banco.agregar_pares_modelado`.
10. **`mecanismo.causa_raiz.senales` y la comprobación de E3 por locale destino en `evidencia[]`
    necesitan que el `juicio` del Maker traiga `senal_id`, `tipo` y `locale` por cada ítem de
    evidencia** (campos que en el esquema 1.0.0 vigente ni existen en `evidencia[]`): es la forma
    aditiva de 1.1.0 que se usa internamente (ver decisión 1) y se exige en el **contrato de entrada**
    de `ficha_a_candidato` (ver su docstring), no en el `candidatos.json` final.

## Pedidos

### A CT (`contratos/**`, ola 0b/posterior)
- `candidatos` MINOR 1.1.0 completa (§3.7): sin ella, D1c/D1d recorta todo lo aditivo antes de validar
  (ahora en un sidecar, ver decisión 4b, en vez de descartarlo silenciosamente).
- `comunes#motivo_rechazo` + `linea_roja_de_contenido_o_negocio` (+ opcionalmente
  `duplicado_de_la_memoria`, `evidencia_insuficiente`, `inviable_sin_backend`).
- `limites` MINOR: `nivel_max_lanzable`, `hojas_pausadas`, `max_capturas_web_por_dia`.
- `parametros` MINOR 1.2.0 (`patternProperties` para `modelado_*`/`barrido_*`/...) para que
  `grupos.descubrimiento` pueda tener a la vez `sim_dup_bloqueo` y los `modelado_*` sin violar
  `additionalProperties: false`.
- Esquema `senal` (y `problema`, `barrido`, `nichos`, `fuentes`): hoy `ingresar_senal.py`, `nichos.py`
  y `banco.py` validan con sus propias reglas mínimas, no con `jsonschema` (`banco.py` no tiene
  ningún esquema todavía: §8.1 n.3).

### A la sesión de `scripts/modelado/` (barrido)
- Que el CLI del barrido llame a
  `scripts.modelado.preflight_descubrir.comprobar_descubrir(raiz, env, via="conector")` antes de
  gastar una consulta del conector (hoy no lo hace, interfaces §0 n.10); `via="captura_web"` para
  `captura.py`/`enlaces.py`/ruta D.
- `engine/guard.py` (B1): añadir `max_consultas_biblioteca` a
  `scripts.validar_esquemas.CLAVES_CRITICAS["descubrir"]` cuando el dueño apruebe la clave.

### A quien mantiene `.claude/skills/d1-descubrimiento/` (ruta protegida, no se edita desde aquí)
- `scripts/preflight.py:129` llama `comprobar_descubrir(raiz)` sin `via`; ahora `via` es obligatoria
  y sin valor por defecto (decisión D1d, interfaces §6.4): la llamada lanza `TypeError`. Hoy ese
  `TypeError` queda atrapado por el `except Exception` de ese mismo script (P-08 se reporta como
  AVISO con el mensaje del error, no rompe el resto del preflight de la skill), pero el mensaje que
  imprime ("scripts.modelado.preflight_descubrir bloquearía el barrido...") es confuso para un
  `TypeError` de uso. Pasar `via="conector"` (la skill corre en sesión interactiva con el conector).

### Al dueño
- Aprobar `nichos.yaml` y `fuentes.yaml` (hoy son semillas en `docs/_historial/d1-v2-semillas/`,
  usadas acá solo como fixtures de prueba).
- `nivel_max_lanzable` por macro-nicho (hoy D1c solo puede lanzar verde).

## Qué falta para el primer candidato real (interfaces §8.6)
Con `nichos.yaml` aprobado y una ficha real del Modo D con su juicio (macro, riesgo, mecanismo,
entregable, evidencia con E3 del locale destino), `ficha_a_candidato mapear --aplicar` ya puede
producir un `candidatos.json` válido contra el esquema vigente. El banco de problemas (`banco.py`) ya
existe y puede recibir de punta a punta un problema `semilla` → sus transiciones → `pares_modelado[]`
de los pares que no pasan la puerta, pero **nadie los conecta todavía**: hace falta un script (u O0)
que, tras cada corrida de `ficha_a_candidato mapear`, llame a `banco.agregar_pares_modelado` con los
`ResultadoPar` que no llegaron a `pasa`. Sigue faltando la captura asistida real de E3 (hoy la aporta
el Maker a mano, fuera de este código) y el sello de recolección de X1 (su emisor no existe,
interfaces §4.4).
