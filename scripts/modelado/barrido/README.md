# scripts/modelado/barrido — Barrido por forma de la Biblioteca de Anuncios

Propietario: D1 (descubrimiento), Modo D. Spec: `departamentos/02-descubrimiento.md` **§17** (descubrimiento continuo; el barrido por forma es su pieza 1, el etiquetado la 2, la memoria la 6) y §12-§15. Contrato de datos: `CONTRATO.md` (en esta carpeta). Solo biblioteca estándar y PyYAML.

## 1. Qué es (y qué no)
El conector `ads_library_search` entrega **como máximo 50 anuncios por llamada**, los más recientes primero, sin paginación y solo a una sesión de Claude (no a un programa). Para ver más allá de los mismos 50, este paquete **rodea el límite**: parte la búsqueda en muchas consultas pequeñas (una frase estructural de oferta digital × un país), las hace ejecutar a agentes en paralelo que **escriben ellos mismos los resultados a disco**, y el código hace el resto: valida, agrupa por página, etiqueta con IA (con evidencia verificable), recuerda cada barrido, rankea temas, y arma fichas para `puntaje_modelar`.

**La IA propone, el código dispone.** Ningún umbral vive en el código: salen de `parametros_barrido.propuesta.yaml` y `scripts/modelado/parametros_modelado.propuesta.yaml`; si falta uno, falla cerrado (código 5).

> **El CLI solo orquesta archivos. Ningún subcomando llama a la red, a Meta, a Chrome ni a `claude`** (`cli.py` ni siquiera importa `socket`, `subprocess` ni `urllib`, y hay una prueba que lo exige). Los agentes que usan el conector de Meta los lanza **quien orquesta** (una persona o una sesión de Claude Code) con los **prompts que el CLI genera** (§4). Lo único que un agente ejecuta del repositorio es `validar-crudo` y `etiquetas-validar`, que solo leen.

## 2. Piezas
| Archivo | Qué hace |
|---|---|
| `cli.py` / `__main__.py` | Este CLI: integra todo lo de abajo. |
| `comun.py` | Errores y códigos de salida, lector JSON estricto, escritura atómica **sin sobrescribir**, parámetros, reloj, validación del crudo. |
| `plan.py` + `frases_forma.yaml` | Plan de consultas (país × forma, pasadas 1-3), reparto entre agentes, prompt de cada agente (`agente_barrido.md`). |
| `ingesta.py` | Crudos → páginas (dedupe por anuncio, edad de la oferta, medición por página, señal de exportadores), cobertura del plan. |
| `etiquetado.py` + `etiquetador.md` | Lotes para la IA, validación estricta de lo que devuelve (la evidencia debe ser un título **textual**), consolidación. |
| `memoria.py` | Instantánea inmutable de cada barrido, diff, `entrantes_30d` (`null` sin base, jamás 0). |
| `ranking.py` | Temas rankeados por anunciantes independientes y tracción, matriz tema × país, exportadores, puente a fichas `2.0.0`. |
| `ruta_b.py`, `ruta_c.py`, `ruta_d.py` | Rutas **alternativas** de captura (§8). **No** están integradas en este CLI. |

## 3. Flujo completo, en comandos
Todos desde la raíz del repositorio: `.venv/bin/python -m scripts.modelado.barrido <subcomando>` (abreviado `barrido` abajo). **Sin `--escribir` nada se escribe** (simulación); con `--escribir`, nada se sobrescribe. `CORRIDA` = `AAAA-MM-DD-<letra>` (p. ej. `2026-11-06-a`).

```
# 1. Plan de la pasada 1 (país × forma) y prompts de los agentes de barrido
barrido plan generar CORRIDA [--paises US,MX,ES] [--formas pago-unico,…]            # simula
barrido plan generar CORRIDA --escribir
barrido plan agentes CORRIDA --salida-prompts /tmp/prompts-CORRIDA-p1 --escribir   # DIR FUERA de empresa/; sin --n divide en olas
#    (con --n N los N agentes deben alcanzar: con 6 agentes × 10 consultas solo vale para planes de hasta 60 consultas;
#    con las 98 de una corrida completa `--n 6` sale con código 5 y pide más agentes)
#    ► quien orquesta lanza un agente por archivo (ver §4); cada uno escribe empresa/barrido/crudo/CORRIDA/<qid>.json
barrido plan agentes CORRIDA --pendientes --salida-prompts /tmp/prompts-CORRIDA-p1b --escribir   # reintento de lo que falte

# 2. Revisar lo que llegó
barrido estado CORRIDA                                  # ok / con error / sin ejecutar / truncadas / cupo
barrido validar-crudo empresa/barrido/crudo/CORRIDA/*.json

# 3. (opcional) Pasada 2: variantes de frase donde la muestra oculta mucho
barrido plan siguiente-pasada CORRIDA --escribir        # → planes/CORRIDA.pasada-2.json
barrido plan agentes CORRIDA --pasada 2 --salida-prompts /tmp/prompts-CORRIDA-p2 --escribir

# 4. Ingesta de la pasada 1 y etiquetado por IA
barrido ingestar CORRIDA --etapa solo-pasada1 --escribir        # → paginas/CORRIDA.solo-pasada1.json
barrido etiquetas empaquetar CORRIDA --etapa solo-pasada1 --escribir
barrido etiquetas prompts CORRIDA --salida-prompts /tmp/prompts-CORRIDA-etiq --escribir
#    ► un agente etiquetador por lote (§4); cada uno verifica con:  barrido etiquetas-validar CORRIDA lote-001
barrido etiquetas consolidar CORRIDA --escribir                 # → etiquetas/CORRIDA/consolidado.json

# 5. Pasada 3: medir de verdad a las páginas con más tracción (una consulta por página, en su país principal)
barrido plan pasada3 CORRIDA --max-paginas 50 --excluir-no-oferta --etapa solo-pasada1 \
        --n 5 --salida-prompts /tmp/prompts-CORRIDA-p3 --escribir     # → planes/CORRIDA.pasada-3.json + prompts
#    ► lanzar esos agentes (§4)

# 6. Ingesta final, memoria, ranking y fichas
barrido ingestar CORRIDA --escribir                     # → paginas/CORRIDA.json (con medición por página)
barrido memoria guardar CORRIDA --escribir              # instantánea inmutable + indice.jsonl
barrido memoria diff CORRIDA                            # cambios y entrantes_30d (null si no hay base)
barrido rankear CORRIDA --sello-esperado <SELLO> --sello-limites-esperado <SELLO_LIMITES> --escribir     # → candidatos/CORRIDA.json
barrido fichas CORRIDA --sello-esperado <SELLO> --sello-limites-esperado <SELLO_LIMITES> --escribir      # → candidatos/CORRIDA/fichas_borrador.json (validar_fichas real)

# 7. Puntaje y, después, la sesión D1 (captura y jueces)
.venv/bin/python -m scripts.modelado.puntaje_modelar puntuar empresa/barrido/candidatos/CORRIDA/fichas_borrador.json \
        --parametros scripts/modelado/parametros_modelado.propuesta.yaml --sello-esperado <SELLO> --json
#    ► captura.py / enlaces.py / juicio.py (sesión D1, §13-§14): puertas, transferibilidad y reencuadres siguen en null hasta que juzguen
```

Notas del flujo:
- **`--etapa NOMBRE`** existe porque la ingesta y el ranking se hacen **dos veces** en una corrida (tras la pasada 1 para elegir qué medir, y tras la pasada 3 para el resultado final) y nada se sobrescribe. `--etapa solo-pasada1` guarda la primera con el sufijo (`paginas/CORRIDA.solo-pasada1.json`, nombre que ya usa la corrida `2026-11-06-a`); sin `--etapa` es el artefacto final. Lo aceptan `ingestar`, `etiquetas empaquetar`, `plan pasada3` y `rankear`.
- **`plan reconstruir CORRIDA --escribir`** arma el plan de la pasada 1 a partir de los crudos que ya existen (qid del archivo; `forma_id` = qid sin el prefijo del país; idioma por el banco) cuando la corrida se hizo a mano o se perdió el plan. Es lo que se hizo a mano con `2026-11-06-a`; verificado contra sus crudos y su consolidado reales: reproduce idéntico (salvo `creado_en`) su plan de 48 consultas, y `plan pasada3 --max-paginas 50 --excluir-no-oferta` reproduce sus 50 consultas de pasada 3 (mismas páginas, mismo orden, mismo país, mismos qid). **El `search_terms` de un crudo es dato no confiable** (lo escribió un agente y pasaría al prompt del siguiente): solo se copia si coincide con la frase principal del banco para su forma e idioma. Las corridas hechas a mano traen frases propias (en `2026-11-06-a`, 42 de 48; 37 con una forma que ni siquiera está en `frases_forma.yaml`): sin `--aceptar-frases-fuera-del-banco` el comando sale con código 3 (nombra los qid, nunca imprime la frase); con la opción las acepta tal cual y **avisa cuáles quedaron fuera del banco** (no tienen variantes: `plan siguiente-pasada --pasada 2` no las parte). Esa opción está apagada por defecto, no existe con `FABRICA_ENTORNO=produccion`, y `plan agentes` la vuelve a exigir para relanzar una consulta de frase manual (`plan.instrucciones_agente` rechaza una frase que no es del banco).
- **`plan pasada3`** elige las páginas por `anuncios_activos_en_muestra` (desc), luego nº de consultas en que aparece (desc), luego `page_id` **como texto**; quita las que el etiquetado marcó `es_oferta_digital_pago_unico: false` o formato `comunidad_o_app`/`servicio`/`producto_fisico`; una consulta por página, en el país donde más anuncios tiene (empate: el primero por orden alfabético); qid `<pais>-pag-<sha1(page_id)[:8]>`; y no pasa del tope restante de `modelado_max_consultas_por_corrida`. Distinto de `plan siguiente-pasada --pasada 3` (lotes de hasta 5 `page_ids` × todos los países de presencia): no se usan los dos en la misma corrida.
- **`memoria guardar` y `rankear`** toman `n_consultas` y `paises_consultados` del plan, pero solo declaran consultado un país con **al menos una consulta con crudo válido** (si no, su «ausencia» no significaría nada). Los temas vienen del consolidado de etiquetas. `memoria guardar` guarda además `capturado_en` (el máximo de `capturado_en` de los crudos válidos; si fuera posterior al instante de guardado se limita a él y se avisa), de modo que la antigüedad de la base de `entrantes_30d` se mide desde la captura (`antiguedad_desde: "capturado_en"` en `memoria diff`), no desde cuándo se guardó. `memoria diff` expone también `entrantes_30d_piso_por_pais` (un valor sobre muestra truncada es un piso). `rankear` pasa `barrido_idioma_por_pais` = `plan.cargar_banco()["pais_idioma"]` y el diff de memoria (`entrantes_30d`).
- **`--sello-esperado`** (`rankear` y `fichas`): el sello de reglas (SHA-256 de la fórmula, los 35 parámetros `modelado_*` y los vocabularios, el mismo que calcula `puntaje_modelar`) debe ser el aprobado; si alguien cambió un umbral el comando sale con **código 4** sin calcular. Cada uno imprime el sello en uso.
- **`--sello-limites-esperado`** (cualquier subcomando): segundo sello, el de los **límites**, que el de reglas no cubre (con un tope de 120 o de 99999 consultas el sello de reglas es el mismo). Es el SHA-256 de `modelado_max_consultas_por_corrida` y de todas las claves `barrido_*` y `ruta_*` (cada una con su `valor` y su `rango`) de `parametros_barrido.propuesta.yaml` y de los `parametros_ruta_*.propuesta.yaml` que haya a su lado. Si no coincide con el aprobado, **código 4** antes de hacer nada. `estado`, `plan generar`, `rankear` y `fichas` imprimen el sello en uso.
- **`consolidado.json` no se usa a ciegas:** no lleva hash, así que `rankear`, `fichas`, `memoria guardar|diff`, `plan pasada3 --excluir-no-oferta` y `estado` lo **recalculan** con `etiquetas consolidar` en una carpeta temporal y exigen igualdad de `etiquetas`, `en_disputa` y `sin_etiquetar`. Si alguien lo editó, o una salida cambió después de consolidar, sale con código 3 y dice cómo rehacerlo (mover ese archivo y volver a consolidar; nada se sobrescribe).
- **Crudos que el plan no pidió:** `ingestar` sale con código 3 ante un crudo fuera del plan o con una consulta distinta de la planificada; el escape `--permitir-fuera-de-plan` no existe con `FABRICA_ENTORNO=produccion` y deja el aviso en la salida. `estado` también sale con código 3 si hay crudos fuera del plan, con otra consulta, o más crudos válidos que el tope de consultas.

## 4. Cómo se lanzan los agentes (los lanza quien orquesta; el CLI solo prepara)
**Agentes de barrido** (usan `ads_library_search`; Ruta A). `plan agentes … --salida-prompts DIR --escribir` escribe en `DIR` un archivo `CORRIDA.agente-NN.md` por agente (la plantilla `agente_barrido.md` con la corrida, la **raíz absoluta** del repositorio y sus consultas) y un `reparto.json`. Quien orquesta lanza un agente por archivo —con la herramienta de agentes de Claude Code, pegando el contenido del archivo como prompt— de a lo sumo `barrido_agentes_paralelos_max` a la vez (hoy 6; `plan agentes` sin `--n` ya divide en olas), y cada agente tiene como máximo `barrido_consultas_por_agente_max` consultas (hoy 10). Cada agente: carga la herramienta, ejecuta sus consultas **una por una**, **escribe** `empresa/barrido/crudo/CORRIDA/<qid>.json` (o `<qid>.error.json` si falla dos veces) y verifica con `barrido validar-crudo <ruta>`. Si dos consultas seguidas fallan, se detiene (probable bloqueo): no lo esquiva. Un archivo que ya existe lo salta (`YA_EXISTIA`), así que relanzar es seguro; `--pendientes` reparte solo lo que falta. Un crudo **inválido** (renombrado `.invalido` por el agente) requiere a una persona.

**Agentes etiquetadores** (no usan herramientas externas). `etiquetas prompts … --salida-prompts DIR --escribir` escribe `CORRIDA.lote-NNN.md` por lote: la definición completa de `etiquetador.md` más sus datos (corrida, lote, nombre `etiquetador-NNN`, rutas absolutas de entrada y salida, comando de verificación). El agente lee su lote en `etiquetas/CORRIDA/entrada/`, escribe su salida en `etiquetas/CORRIDA/salida/` y corre `barrido etiquetas-validar CORRIDA lote-NNN` (0 = todo aceptado, 3 = hay algo que corregir). Un lote que no se completa no detiene nada: `consolidar` lo cuenta como «sin etiquetar».

`DIR` **nunca puede estar dentro de `empresa/`** (zona protegida para agentes): el CLI lo rechaza (código 2). Usa una carpeta temporal fuera del repositorio.

**Permisos recomendados al lanzar los agentes (revisión de seguridad M3).** Los títulos y nombres que un agente copia son texto de terceros: pasados por Bash (`echo "…"`, `cat <<EOF … $(cmd) …`) pueden **ejecutarse** (se comprobó que `$(touch marca)` dentro de un heredoc sin comillas corre). Por eso: (1) **el contenido de cada archivo se escribe SOLO con Write** (parámetro `content`), nunca por Bash; el CLI antepone esa regla a cada prompt que genera; y (2) los agentes se lanzan con permisos mínimos, y todo lo demás denegado. Para los agentes de **barrido** (reemplaza `<RAIZ>` por la ruta absoluta del repositorio y `<corrida>` por la corrida):
```json
{ "permissions": {
    "allow": [
      "mcp__claude_ai_Meta_ADS__ads_library_search",
      "Edit(//<RAIZ>/empresa/barrido/crudo/<corrida>/**)",
      "Bash(date -u *)",
      "Bash(mkdir -p *)",
      "Bash(.venv/bin/python -m scripts.modelado.barrido validar-crudo *)"
    ],
    "deny": ["mcp__claude_ai_Meta_ADS__ads_create_*", "mcp__claude_ai_Meta_ADS__ads_update_*", "mcp__claude_ai_Meta_ADS__ads_activate_entity",
             "mcp__claude_ai_Meta_ADS__ads_boost_*", "mcp__claude_ai_Meta_ADS__ads_delete_*", "mcp__claude_ai_Meta_ADS__ads_creative_*",
             "mcp__claude_ai_Meta_ADS__ads_catalog_*", "mcp__claude_ai_Meta_ADS__ads_pixel_*", "WebFetch", "WebSearch"] } }
```
Para los agentes **etiquetadores** (sin conector): lo mismo sin la herramienta de Meta, con `"Edit(//<RAIZ>/empresa/barrido/etiquetas/<corrida>/salida/**)"` en lugar de la de `crudo` y `"Bash(.venv/bin/python -m scripts.modelado.barrido etiquetas-validar *)"` en lugar de `validar-crudo`. Notas: (a) en Claude Code una regla `Edit(...)` cubre también a Write; en la prueba de la ruta B una regla `Write(//…)` no coincidió y `Edit(//…)` sí (`docs/_historial/barrido-ruta-b.md` §2). (b) Los prompts ejecutan los comandos del repositorio como `cd "<RAIZ>" && .venv/bin/python …`: si tu versión evalúa cada parte de un comando compuesto, agrega `Bash(cd *)` (no tiene efecto) o lanza el agente con la raíz como directorio de trabajo. (c) Con estos permisos el paso 2.2 de `agente_barrido.md` (comprobación con `python -c`) y el `mv … .invalido` del 2.4 **no pueden ejecutarse**: `validar-crudo` cubre las mismas comprobaciones y, si un archivo no pasa, el agente escribe su `<qid>.error.json` con Write y una persona retira el defectuoso (el CLI antepone esa excepción al prompt). (d) Verifica las reglas con `/permissions` en la versión instalada antes de la primera corrida real.

## 5. Estructura de `empresa/barrido/`
```
planes/CORRIDA.json                      plan de la pasada 1            (+ CORRIDA.pasada-2.json, CORRIDA.pasada-3.json: planes acumulados)
crudo/CORRIDA/<qid>.json                 un archivo por consulta, escrito por el agente (CONTRATO §2)
crudo/CORRIDA/<qid>.error.json           {"qid","error","ts"} si la consulta falló
paginas/CORRIDA[.<etapa>].json           una entrada por página: anuncios, edad, medición, exportador, títulos
etiquetas/CORRIDA/entrada/lote-NNN.json  material del etiquetador (sin cifras)
etiquetas/CORRIDA/salida/lote-NNN.json   lo que devolvió el etiquetador (la valida el código)
etiquetas/CORRIDA/consolidado.json       etiquetas aceptadas, en disputa, sin etiquetar, cobertura
memoria/CORRIDA.json + memoria/indice.jsonl   instantánea inmutable (con hash) e índice
candidatos/CORRIDA[.<etapa>].json        temas rankeados, matriz tema × país, exportadores, descartadas
candidatos/CORRIDA/fichas_borrador.json  fichas 2.0.0 para puntaje_modelar (solo si hay)
```
Todo se escribe atómicamente y **sin sobrescribir**: si el archivo existe, el comando sale con código 2, lo dice y deja el disco intacto.

## 6. Referencia de subcomandos
Opciones comunes: `--json` (una línea JSON en stdout, también ante un error), `--sello-limites-esperado SELLO`, `--raiz DIR` y `--ahora AAAA-MM-DDTHH:MM:SSZ` (**solo pruebas**: se rechazan con `FABRICA_ENTORNO=produccion`, igual que `--permitir-fuera-de-plan` y `--aceptar-frases-fuera-del-banco`). Los que escriben aceptan `--escribir`.

| Subcomando | Qué hace |
|---|---|
| `validar-crudo RUTA…` | Valida crudos (`comun.leer_crudo`): `OK <qid> anuncios=N total=T`; 0 si todos pasan, 3 si alguno no (2 si no se puede leer). |
| `plan generar CORRIDA [--paises] [--formas]` | Plan de la pasada 1. |
| `plan ver CORRIDA [--consultas]` | Resumen del plan acumulado vigente. |
| `plan reconstruir CORRIDA [--aceptar-frases-fuera-del-banco]` | Plan de la pasada 1 desde los crudos existentes (§3). |
| `plan siguiente-pasada CORRIDA [--pasada 2\|3]` | Variantes de frase (2) o lotes de `page_ids` × países de presencia (3). |
| `plan pasada3 CORRIDA --max-paginas N [--excluir-no-oferta] [--etapa E] [--n N] [--salida-prompts DIR] [--aceptar-frases-fuera-del-banco]` | Pasada 3 una página por consulta (§3). |
| `plan agentes CORRIDA [--n N] [--pasada K] [--pendientes] [--salida-prompts DIR] [--aceptar-frases-fuera-del-banco]` | Reparto entre agentes y sus prompts; sin la opción, una consulta con frase que no es del banco sale con código 3 (nombra el qid, no la frase). |
| `ingestar CORRIDA [--etapa E] [--permitir-fuera-de-plan]` | Crudos → «Páginas»; rechaza (3) los crudos que el plan no autoriza. |
| `etiquetas empaquetar \| prompts \| validar \| consolidar` y el alias `etiquetas-validar CORRIDA LOTE` | Etiquetado por IA (§4). |
| `memoria guardar \| diff \| verificar` | Memoria de barridos. `guardar` incluye `capturado_en`; `diff` expone `entrantes_30d_piso_por_pais`; `verificar` sale con 3 si algún hash/índice no cuadra. |
| `rankear CORRIDA [--etapa E] [--sello-esperado S]` | Candidatos. |
| `fichas CORRIDA [--sello-esperado S]` | Borrador de fichas, validado con `puntaje_modelar.validar_fichas`; **sin fichas no escribe**. |
| `estado CORRIDA` | Panorama de solo lectura: plan, consultas ok/error/truncadas, páginas y medición, etiquetado, memoria, candidatos, fichas, cupo de consultas y freno. |

Códigos de salida: **0** correcto · **2** uso (argumentos, archivo ausente, destino ya existente, `--raiz`/`--ahora` en producción) · **3** validación (dato fuera de contrato; `estado` también si un artefacto está corrupto) · **4** bloqueado (`--sello-esperado` o `--sello-limites-esperado` distintos) · **5** falta un parámetro o se excede un límite (tope de consultas, agentes, cupo).

## 7. Parámetros y límites
Los números **no** están en el código. Hoy son propuestas `[HIPÓTESIS]` sin integrar a `empresa/parametros.yaml`:
- `parametros_barrido.propuesta.yaml`: `barrido_limite_por_consulta` 50 · `barrido_paises_origen` US, BR, MX, ES, IT, CO · `barrido_paises_presencia` (11 países) · `barrido_pasadas_max` 3 · `barrido_partir_si_total_supera` 100 · `barrido_variantes_por_particion_max` 3 · `barrido_pasada3_min_anuncios_muestra` 3 · `barrido_pasada3_paginas_max` 15 · `barrido_page_ids_por_consulta_max` 5 · `barrido_consultas_por_agente_max` 10 · `barrido_agentes_paralelos_max` 6 · `barrido_titulos_por_pagina_max` 10 · `barrido_paginas_por_lote_etiquetado` 20 · `memoria_ventana_min_dias` 25 y `memoria_ventana_max_dias` 60 · `barrido_exportador_monedas_pais`.
- `scripts/modelado/parametros_modelado.propuesta.yaml`: `modelado_max_consultas_por_corrida` **120** (cuenta las tres pasadas juntas), `modelado_anuncios_objetivo` 15, `modelado_dias_objetivo` 10 (decisión del dueño, 2026-11-06).

Límites que hay que tener presentes al leer los resultados:
- **50 anuncios por consulta**, los más recientes, sin paginación. Una página con 300 anuncios solo muestra 50 en una frase.
- **Tope por corrida** (120): el plan acumulado (pasadas 1+2+3) no puede pasarlo; excederlo es código 5, nunca se recorta en silencio (salvo `pasada3`, que se ajusta al cupo y lo avisa).
- **Un país por consulta**: el conteo `estimated_total_count` es por país.
- **Conteos piso vs. medidos.** Una página vista solo por frases tiene `medicion.estado: "muestra"` y su conteo es un **piso**, no el total (`muestra_truncada`, `anuncios_activos_medidos_es_piso`, `edad_es_piso`). Solo la pasada 3 (una consulta por `page_id` y país) mide: `completa` si se vieron todos los anuncios declarados, `parcial` si hay más de los que se ven. Un piso que ya supera el umbral es definitivo; uno insuficiente queda «indeterminada por muestra», **nunca se descarta por un conteo truncado**.
- **Ausencia en la muestra no es ausencia en el mercado**: cada hueco de la matriz tema × país es una hipótesis hasta medirlo con la pasada 3.
- **`entrantes_30d`** solo existe si hay una instantánea previa de entre `memoria_ventana_min_dias` y `memoria_ventana_max_dias` de antigüedad; con la primera corrida es `null` en todas partes (jamás 0).
- `es_oferta_digital_pago_unico: null` («no sé») **avanza** (fail-open en descubrimiento) y queda `por_verificar: modelo_de_cobro` (fail-closed al lanzar).

## 8. Rutas alternativas de captura (B, C, D): investigadas, **no integradas en este CLI**
La ruta A (agentes de Claude Code con el conector, arriba) es la única que orquesta este CLI. Las otras producen el **mismo crudo** (`ruta: "B"|"C"|"D"`), que `validar-crudo`, `ingestar` y todo lo demás ya aceptan. Cada una tiene su propia CLI y sus propios parámetros (`parametros_ruta_*.propuesta.yaml`).
| Ruta | Qué es | Veredicto actual (informe) |
|---|---|---|
| **B** — `ruta_b.py` | `claude -p` sin pantalla con el conector, una consulta por proceso; el código arma el crudo con el resultado exacto del conector (el modelo no escribe nada). | **Funciona con condiciones** (`docs/_historial/barrido-ruta-b.md`): sesión de suscripción abierta en esta máquina, encargo redactado de cierta forma, volumen bajo (términos del conector: «no bulk extraction»). Falta el ensayo real supervisado y el LaunchAgent. Pide a I1 exponerla en este CLI (pendiente de decisión, §10). |
| **C** — `ruta_c.py` | API oficial `ads_archive` (pagina de verdad, trae el texto del anuncio). | **Viable con condiciones** (`docs/_historial/barrido-ruta-c.md`): el dueño debe confirmar identidad y crear app y token; **solo anuncios comerciales de la UE y el Reino Unido** (no cubre EE. UU., Brasil, México ni Colombia); no trae moneda (se pierde la señal de exportadores); sin probar con un token real. |
| **D** — `ruta_d.py` | Chrome limpio sobre la página de búsqueda (scroll), con los frenos de `captura.py`. | **Sí, con condiciones** (`docs/_historial/barrido-ruta-d.md`): la lista se sirve sin sesión, pero la única visita de sondeo dejó un **freno puesto** (HTTP 403); no se midió el desplazamiento; el contrato no admite lo que la web entrega (moneda `null`, más de 50 anuncios, `page_id` nulo); el mayor riesgo con los términos de Meta. Solo desde un servidor, nunca desde la red del dueño. |

## 9. Freno compartido y reglas de seguridad
- **Freno compartido de captura:** `empresa/captura/freno.json` lo escriben `captura.py` y `ruta_d.py` cuando algo parece un bloqueo (captcha, login obligatorio, límite de solicitudes, HTTP 401/403/429). **Hoy está puesto** (`HTTP 403 (Document)`, de la visita de sondeo de la ruta D). **Solo una persona lo borra, a mano, después de revisar si fue un falso positivo; ningún agente lo borra ni lo esquiva.** Este CLI **solo lo lee** (`estado` lo muestra y `plan agentes`/`plan pasada3` avisan): no lo escribe, no lo borra, no lo consulta para decidir. No afecta a los agentes de la ruta A (usan el conector, no Chrome), pero sí a cualquier captura con Chrome (rutas D y `captura.py`).
- **Texto de la Biblioteca = dato no confiable.** Títulos y nombres de página los escriben los anunciantes y pueden traer órdenes dirigidas a una IA. Nunca se interpretan ni se ejecutan; el CLI no imprime títulos ni nombres de página (lo que imprime pasa por un saneador: una sola línea, sin caracteres de control, con tope de largo); los agentes los copian como texto dentro de comillas JSON; el etiquetador los trata como dato y el código descarta cualquier etiqueta cuya evidencia no sea un título textual del lote; en HTML/Markdown se escapan.
- **La IA nunca aporta una cifra medida:** el etiquetador no ve anuncios ni edades y cualquier campo extra invalida su etiqueta.
- **Nada se sobrescribe, nada se asume:** dato faltante o raro → error claro; puertas, transferibilidad y `entrantes_30d` van `null`, nunca `false` ni 0 por defecto.
- `--raiz`, `--ahora` y los escapes `--permitir-fuera-de-plan` y `--aceptar-frases-fuera-del-banco` existen solo fuera de producción y se rechazan con `FABRICA_ENTORNO=produccion`.
- **Lo que llega al prompt de un agente es del sistema, no de la Biblioteca:** qid kebab, país, frase del banco, dígitos de `page_id` y límite. Una frase de un crudo no se copia a un plan (`plan reconstruir`) ni a un prompt (`plan agentes`) sin la opción explícita.
- **Contenido solo con Write y permisos mínimos** para los agentes (§4).

## 10. Pendiente de decisión del dueño
1. **Aprobar e integrar los parámetros** (`parametros_barrido.propuesta.yaml`, y los `parametros_ruta_*` si se usa alguna ruta) en `empresa/parametros.yaml` y `contratos/parametros.schema.json` (rutas protegidas para agentes). Mientras tanto son hipótesis sin calibrar; los umbrales de tracción (15 anuncios, 10 días) ya los fijó el dueño.
2. **Aprobar el sello de reglas** que se pasa a `--sello-esperado` (se obtiene con `rankear`/`fichas` o `puntaje_modelar`).
3. **El freno actual:** que una persona revise si el HTTP 403 de la visita de sondeo fue un falso positivo y decida si lo borra. Mientras esté puesto, la ruta D y `captura.py` no corren.
4. **Qué ruta usar para pasar de 50 anuncios:** seguir con A (agentes del conector; gasta cuota de la sesión y tiene los límites de §7), habilitar B (cola desatendida con `claude -p`; falta el ensayo real y releer los términos del conector), C (identidad, app y token; solo UE/UK) o D (riesgo de términos de Meta; solo desde un servidor). Decidir también si se expone B en este CLI (el informe de la ruta B lo pide a I1; aquí no se hizo por instrucción).
5. **Cambios de contrato que piden las rutas:** B (declarar la carpeta `empresa/barrido/ruta_b/`), C (`currency` `XXX`/`null`, partir resultados mayores de 50) y D (`currency`/`page_id` nulos, más de 50 anuncios). `listar_crudos` ya excluye `*.extra.json` (eso no está pendiente). Ninguno está aprobado.
6. **Cadencia del barrido:** `entrantes_30d` y los «temas nuevos» exigen una segunda corrida con al menos `memoria_ventana_min_dias` (25) de antigüedad respecto de la primera. Decidir cada cuánto se corre y dónde (esta máquina o un servidor).
7. **Cómo se verifican los `por_verificar`:** las páginas con `es_oferta_digital_pago_unico: null` o tema indeterminado avanzan; la captura y los jueces (sesión D1) deben aclarar el modelo de cobro antes de lanzar.
8. **Lectura del hueco:** en las fichas borrador, un mercado «sin el original» sale de la ausencia en la **muestra**, no de una medición del mercado: `original_presente: false`, `anunciantes_sostenidos: 0` y `ventana: "evergreen"` son **hipótesis optimistas hasta medir** (el validador real no admite `null` en esos campos, y ponen H al máximo). La pasada 3 por país y la auditoría del rival las confirman. Está marcado en `pendiente` y en `_nota` de cada ficha.
9. **Memoria real de `2026-11-06-a`:** su instantánea (`memoria/2026-11-06-a.json`) se guardó con la ingesta de la **etapa 1** (solo pasada 1, 48 consultas), no con la ingesta final (98 consultas). Es **inmutable**: no se reescribe. Efecto: en la próxima corrida, `paginas_que_crecen` mostrará como crecimiento lo que es efecto de la pasada 3 (`entrantes_30d` no: usa presencia, no conteos). **La próxima corrida debe guardar su instantánea tras la ingesta final** (§3 paso 6, `memoria guardar` sin `--etapa`).

## 11. Pruebas
```
.venv/bin/python -m unittest tests.scripts.test_barrido_cli tests.scripts.test_barrido_e2e      # este CLI y la corrida sintética de punta a punta
.venv/bin/python -m unittest discover -s tests/scripts -t .                                       # toda la suite de scripts
```
`test_barrido_e2e.py` arma en una raíz temporal una corrida sintética (3 países, 13 páginas, con pasada 3 simulada y la salida del etiquetador **grabada** en `tests/fixtures/barrido/e2e/`) y corre todo el flujo con el CLI, sin red ni `claude` (se bloquean `socket` y `subprocess`), y comprueba que el `empresa/` real no cambió (hash antes/después).

*Para enlazar desde la spec: `departamentos/02-descubrimiento.md` §17 → `scripts/modelado/barrido/README.md`.*
