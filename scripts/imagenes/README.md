# scripts/imagenes — imágenes de la landing con Kie.ai (generar → revisión ciega → reintentos → finales)

Propósito: producir las imágenes de las ranuras de una oferta (héroe, portadas de dodatki y bump, tarjeta de compra, og, miniaturas ilustrativas) con
**texto exacto**, con trazabilidad de cada candidato, tope de créditos y una **revisión independiente ciega**. Primera oferta que lo recorrió:
OF-202611-91 (Słowomapa), rondas 1-3.

| Pieza | Qué hace |
|---|---|
| `portadas_planas.py` | portadas y mapas PLANOS (HTML/CSS → PNG con Chrome): la fuente del texto exacto y la referencia de Kie |
| `ranuras_kie.py` | CLI: `generar`, `reintentar`, `elegir`, `derivar`, `recomprobar`, `saldo`, `manifiesto` y los comandos del ciclo de revisión |
| `guia_escena.py` · `componer_portadas.py` | escenas con marcadores y composición por código (portadas planas pegadas sobre la escena de Kie) |
| `ciclo_revision.py` | paquete ciego, instrucciones del revisor, validar y aplicar su veredicto, plan de reintentos y finales |
| `finales_ranuras.py` | 2048 px → medida y peso de cada ranura (webp/jpg) + `manifiesto-final.json` |
| `ocr_vision.swift` | OCR con Vision de macOS (pl-PL) que usan las comprobaciones de código |

Todo lo del ciclo de revisión es **código sin red ni créditos**; solo `generar`, `reintentar` y `saldo` llaman a Kie. La clave `KIE_API_KEY` se lee de `.env`
dentro del proceso y nunca se imprime ni se guarda.

## Variables de los ejemplos
```bash
OF=ofertas/OF-202611-91                       # carpeta de la oferta
A=$OF/05-landing/assets                       # carpeta de trabajo de las imágenes
PLAN=$A/plan-slots.json                       # plan de ranuras (prompts, referencias, textos esperados, rúbrica por slot)
```
El plan declara por slot: `slot_id`, `ratio`, `prompt`, `referencias`, `intentos` (modelo y cuántos), `funcion`, `textos_esperados`, `textos_estrictos`,
`objetos_esperados`, `no_debe_aparecer`, `estricto` (true = títulos y cifras exactos), `criterios`, `dimensiones_requeridas`, `alt_propuesto` y, si procede,
`ilustrativa` / `reemplazar_con_real_cuando_exista_producto` (si faltan, se calculan: ver más abajo).

## El ciclo completo

### 1. Generar (orquestador + código)
```bash
python3 scripts/imagenes/portadas_planas.py $A/portadas-planas.json --salida $A/referencias         # portadas planas con el texto exacto
python3 scripts/imagenes/ranuras_kie.py saldo   --assets $A --fase inicio [--ledger gasto-ronda2.json --ronda 2 --tope 600]
python3 scripts/imagenes/ranuras_kie.py generar $PLAN --assets $A --seco --tope 900                  # cotiza sin gastar
python3 scripts/imagenes/ranuras_kie.py generar $PLAN --assets $A [--solo hero,compra] --tope 900    # anota el gasto ANTES de cada envío; para al llegar al tope
# mockups con varias portadas (texto exacto por código): boceto -> escena con marcadores -> composición -> candidato
python3 scripts/imagenes/guia_escena.py  $A/referencias/comp/guia-X.json --salida $A/referencias/comp/guia-X.png
python3 scripts/imagenes/componer_portadas.py componer $A/referencias/comp/X-comp.json               # supersampling 2x, recorte final
python3 scripts/imagenes/ranuras_kie.py derivar $PLAN --assets $A --slot X --desde <png compuesto> --base <escena> --nombre r2-comp-01
python3 scripts/imagenes/ranuras_kie.py elegir  $PLAN --assets $A --slot X --candidato r2-comp-01 --motivo "..."
python3 scripts/imagenes/ranuras_kie.py recomprobar $PLAN --assets $A                                # dimensiones, ratio, peso WebP, OCR
python3 scripts/imagenes/ranuras_kie.py saldo   --assets $A --fase fin [--ledger gasto-ronda2.json --ronda 2]
```
Cada candidato queda en `$A/candidatos/<slot>/<intento>.png` con su `<intento>.json` (prompt exacto, modelo, parámetros, créditos, `task_id`, sha256,
textos esperados, comprobaciones, `ronda`, `tipo`). `generar` es idempotente: lo ya generado no se vuelve a pagar.

### 2. Paquete de revisión CIEGO
```bash
python3 scripts/imagenes/ranuras_kie.py manifiesto $PLAN --assets $A --ciego                          # todo lo pendiente de revisar
python3 scripts/imagenes/ranuras_kie.py manifiesto $PLAN --assets $A --ciego --solo-slots hero,compra # solo esos slots
python3 scripts/imagenes/ranuras_kie.py manifiesto $PLAN --assets $A --ciego --solo-re-revisar        # solo rehechos o sin revisar
```
Escribe `$A/revision-ciega/ronda<N>/paquete-ciego.json` y deja cada candidato pendiente con un **alias** (`c1`, `c2`…, orden barajado) en
`$A/revision-ciega/ronda<N>/<slot>/<alias>.png` (enlace duro o copia), más el mapa secreto alias → candidato en
`$A/revision-ciega/mapa-secreto-ronda<N>.json`. El paquete trae: rúbrica general, `hechos_del_producto` leídos de `03-oferta/oferta.json` (marca,
entregables, bonus, bump y **`NO_incluye`**), y por slot función, textos esperados, objetos esperados, lo que NO debe aparecer, medidas, rúbrica
(`estricto`, `textos_estrictos`, criterios), portada plana de referencia, `ilustrativa` y `reemplazar_con_real_cuando_exista_producto`, y las **rutas
absolutas** de los candidatos pendientes. **No** lleva prompts, modelos, créditos, OCR, `seleccion_maker`, correcciones ni nombres de candidato; el
código comprueba que no filtra nada (aborta si encuentra un rastro). Se excluyen las escenas con marcadores y los candidatos ya revisados.

El paquete del Maker (con todo el detalle y el estado calculado por slot) es el mismo comando sin `--ciego`: `manifiesto $PLAN --assets $A`
(escribe `$A/paquete-revision.json`).

### 3. Instrucciones del revisor
```bash
python3 scripts/imagenes/ranuras_kie.py revisar-prompt $PLAN --assets $A [--ronda N]
```
Escribe `instrucciones-revisor.md` junto al paquete ciego: rol (solo lectura: Read, Grep, Glob), qué verificar por candidato (texto exacto con ortografía
polaca y guion largo, objetos, hechos del producto, distancia del referente, deformaciones, aliasing, objetos flotantes, márgenes, bandas vacías), reglas
del veredicto y el formato JSON de salida:
```json
{"ronda": 1, "revisor": "texto libre", "slots": [
  {"slot_id": "hero",
   "candidatos": [{"nombre": "c1", "veredicto": "PASA|REHACER|RECHAZADO", "hallazgos": [], "diferencias_texto": [], "texto_dudoso": []}],
   "mejor": "c1" , "veredicto_slot": "PASA|PASA_CONDICIONAL|REHACER", "condiciones": [], "correccion_para_regenerar": ""}]}
```

### 4. El agente revisor (lo invoca el ORQUESTADOR, no el código)
El orquestador lanza un agente independiente de **solo lectura** (por ejemplo `d5-qa`, o un agente general con Read/Grep/Glob), le pasa el contenido de
`instrucciones-revisor.md` y guarda como `revision-nueva.json` el JSON de su respuesta final. El código no invoca agentes ni juzga la imagen.

### 5. Aplicar la revisión
```bash
python3 scripts/imagenes/ranuras_kie.py aplicar-revision $PLAN revision-nueva.json --assets $A [--tope 300] [--n 1] [--max-intentos 3] [--ronda N]
```
Valida la forma y la coherencia; si todo es correcto: traduce los alias, guarda `$A/revision-ronda<N>.json` (con el JSON bruto), pone como
`seleccion_maker` el candidato aprobado, actualiza `$A/paquete-revision.json` (`estado` y `aprobado_por_revision` por slot) y escribe
`$A/plan-reintentos-ronda<N>.json` con, por slot en REHACER: la corrección, el modelo propuesto, los intentos usados de 3, los créditos estimados
(`estimar_creditos` con el mínimo medido por modelo), el `comando_sugerido` y si **supera el tope**; más la lista `pendientes_que_superan_el_tope`.

**Se rechaza TODO el archivo, sin escribir nada (salida 3)** si: no es JSON o no tiene la forma pedida; trae un slot o un candidato desconocido; un
`REHACER` no trae `correccion_para_regenerar`; un `PASA` apunta a un candidato que no pasa; un `PASA_CONDICIONAL` no trae `condiciones`; o **un slot
estricto recibe `PASA` con `diferencias_texto` no vacías**. El orquestador devuelve la lista de errores al revisor y repite.

Estados por slot (se calculan, no se escriben): `PASA_ronda<N>`, `REHACER_ronda<N>`, `rehecho_ronda<M>_pendiente_de_revision` (hay un candidato elegido
nuevo), `pendiente_de_revision`. También se entienden las revisiones manuales de las rondas 1 y 2 (`estrictas`/`ilustrativas` → `PASA`/`REHACER`).

### 6. Reintentos (orquestador + código)
Con `plan-reintentos-ronda<N>.json` el orquestador decide qué pagar (respetando el tope de la ronda) y ejecuta los `comando_sugerido`:
```bash
python3 scripts/imagenes/ranuras_kie.py reintentar $PLAN --assets $A --slot hero --modelo nano-banana-pro --correccion "texto del revisor"
```
(o rehace la escena y vuelve a componer si el slot se compone por código). Luego vuelve al paso 2 con `--solo-re-revisar`: la ronda siguiente solo
muestra los candidatos nuevos.

### 7. Finalizar
```bash
python3 scripts/imagenes/ranuras_kie.py finalizar $PLAN --assets $A [--assets-json $OF/05-landing/assets.json] [--incluir-pendientes]
```
Genera `$A/final/<slot>.webp|jpg` a la medida y peso de cada ranura (las medidas salen de `assets.json`, solo lectura; el og conserva 1200×630) y
`$A/final/manifiesto-final.json` **solo con los slots aprobados** (sha256, modelo, créditos, intentos por ronda, `ilustrativa`,
`reemplazar_con_real_cuando_exista_producto`, `etiqueta_ia_visible`, `alt_propuesto`) y la propuesta de parches para `assets.json` (nunca lo edita).
Avisa de los no aprobados y de las condiciones abiertas (salida 4 si no hay ninguno aprobado); con `--incluir-pendientes` los añade en estado «asignado».

## Qué es del orquestador y qué es del código
| Paso | Orquestador (agente que dirige el trabajo) | Código (`scripts/imagenes/`) |
|---|---|---|
| Decidir el plan, los prompts y el tope de créditos | sí | lo valida y lo cumple (`TopeExcedido`, idempotencia) |
| Generar, componer, comprobar | lanza los comandos | hace todo (Kie, Chrome, ffmpeg, OCR) |
| Construir el paquete ciego | lanza `manifiesto --ciego` | arma el paquete, los alias, el mapa secreto y vigila las fugas |
| **Invocar al agente revisor** | **sí**: lo lanza (solo lectura) y recoge su JSON | no |
| Aplicar el veredicto | lanza `aplicar-revision` y devuelve los errores al revisor | valida, rechaza lo inválido, marca estados, plan de reintentos |
| Decidir qué reintentar y cuánto gastar | sí (mira el plan de reintentos y el tope) | estima créditos y marca lo que supera el tope |
| Finalizar | lanza `finalizar` y atiende los avisos | convierte, calcula sha256 y escribe los manifiestos |
| Cambiar `assets.json`, `copy.json`, la landing | sí (con los parches propuestos) | nunca lo hace |

## `ilustrativa` y `reemplazar_con_real_cuando_exista_producto`
Si el plan no los fija, se calculan: una ranura es **ilustrativa** si `assets.json` la declara `captura_producto` o su id empieza por `muestra`;
toda ilustrativa **se sustituye con la pieza real cuando exista el producto** (`reemplazar_con_real_cuando_exista_producto = true`), y
`reemplazar_ahora` se activa si ya existe `04-producto/producto.json`. Un valor explícito en el plan manda.

## Códigos de salida de `ranuras_kie.py`
0 ok · 2 uso o plan inválido · 3 revisión rechazada (`aplicar-revision` no escribió nada) · 4 `finalizar` sin slots aprobados · 5 tope de créditos · 6 falló
Kie o una herramienta externa.

## Pruebas
```bash
.venv/bin/python -m unittest discover -s tests/imagenes -t .       # sin red: Kie se simula con un doble; ffmpeg/cwebp/sips solo en las pruebas que los usan
```
