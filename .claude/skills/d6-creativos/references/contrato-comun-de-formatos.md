# Contrato común mínimo de un productor de formato (propuesta)

Estado: **propuesta de S-C (2026-11-07)**; no existía un contrato común (cada productor define el suyo: `d6-sketch-animado` usa `brief-sketch.json`, la Ruta A usa `copies.json`). Lo mínimo para que D6 pueda enchufar cualquier formato sin reescribirse. Inventario de productores en `productores-de-formato.md`.

## 1. Idea

> **entrada = brief + copy → salida = pieza + fragmento de `paquete.json`.**

D6 (el Maker) decide la matriz, el ángulo, el hook, el copy, los claims y el riesgo; congela los textos (QA-A) y **entrega al productor lo que ya está aprobado**. El productor no inventa texto, no cambia claims, no sube nada, no aprueba. Devuelve la pieza y los datos que D6 necesita para armar `paquete.json` y para que el QA y X1 revisen.

## 2. Entrada mínima (`formato-brief.json`, ejemplo en `templates/formato-brief.json`)

| Campo | Qué es | De dónde sale |
|---|---|---|
| `oferta_id`, `locale`, `macro_nicho` | identidad y lugar | `mercado.json`, `oferta.json` |
| `ad_name`, `concepto_id`, `hook_id`, `hook_tipo`, `formato`, `variante_formato`, `presentador`, `duracion_s`, `v` | la fila de la matriz | `06-creativos/matriz.json` |
| `copy` | `texto_principal`, `titular`, `descripcion`, `cta`, `texto_en_pieza{…}` | `06-creativos/copies.json` (congelado) |
| `guion_ref`, `hash_textos` | guion congelado y el hash de textos aprobado en QA-A | `guiones/<ad_name>.md`, `validar_d6.py textos` |
| `claim_ids`, `claims_prohibidos` | lo que se puede afirmar y lo que no | `oferta.promesa` |
| `riesgo_pieza` | nivel y `ejes_codigo` ya calculados | `scripts.nivel_riesgo` |
| `marca` | colores, fuentes (WOFF2 con licencia) | `05-landing/paleta.json` |
| `limites` | `creditos_max_pieza`, `creditos_max_oferta`, `politica_divulgacion_ia` | `empresa/limites.yaml` (solo lectura) |
| `ruta` | `A` (0 créditos) o `B`/`C` (créditos, cotización aprobada) | SKILL §5.4 |
| `cotizacion` (rutas con créditos) | créditos aprobados por el dueño y `idempotency_key` estable | chat del dueño + `costos.jsonl` |

## 3. Salida mínima (`formato-salida.json`, ejemplo en `templates/formato-salida.json`)

1. **La pieza:** `assets/<ad_name>.<png|mp4>` (y las fuentes reproducibles: `assets/src/<ad_name>.html`, guion de montaje).
2. **El fragmento de `paquete.json`:** el objeto `anuncios[].assets[]` de la pieza con `archivo`, `ratio`, `sha256`, `herramienta`, `modelo`, `job_id`, `ia_generado`, `c2pa_origen`, `c2pa_final`, `etiqueta_ia_visible`, `copy_hash`, `licencia_ref`, `costo_creditos` (forma de `contratos/creativos.schema.json` y de `templates/paquete.json`). D6 lo inserta en `anuncios[]`; el productor **no escribe** `paquete.json`.
3. **Registros:** la línea previa en el borrador `06-creativos/costos.jsonl` (rutas con créditos), las entradas de `licencias.json` y la fila de `assets.json` (`creditos_reservados`, `creditos_reales`).
4. **Resultado de `qc6.py pieza`** sobre la pieza (`qc6.json`): el productor no se autoaprueba, pero corre el mismo control que correrá el QA.

## 4. Reglas comunes (todas las de la SKILL §1 valen íntegras)

- **Texto = el congelado.** Lo que la pieza muestra o dice es exactamente `copy.texto_en_pieza` / la línea hablada del guion; sin añadidos, sin traducciones automáticas, sin copy inyectado por la herramienta (el de `ads_studio_get_run` se descarta).
- **Sin efectos externos sin permiso:** nada de subir a Meta; nada de publicar; sin claves en el agente (B1-18); cotización registrada **antes** de gastar y tope respetado; tras un timeout se consulta el estado antes de reintentar.
- **Solo escribe en `ofertas/<id>/06-creativos/`** (y en el staging de su corrida).
- **Determinista donde se pueda:** misma entrada, misma pieza (versión de herramienta y modelo registrados en `herramienta`/`modelo`).
- **Modo `--simular`/dry-run:** valida la entrada y devuelve la salida esperada sin generar nada ni gastar.
- **Etiqueta de IA y C2PA** según `politica_divulgacion_ia`; C2PA nunca se elimina a propósito.

## 5. Interfaz de línea de comandos (si es un script)

`<productor> producir --brief formato-brief.json --salida 06-creativos/ [--simular] [--json]`

Códigos de salida (convenciones del repo): `0` ok · `2` uso · `3` entrada o pieza inválida (esquema, hash de textos, QC en `falla`) · `4` preflight en rojo · `5` falta o se excede un tope de créditos · `6` falla de una herramienta externa. Una skill (sin CLI) cumple el contrato entregando los mismos archivos.

## 6. Cumplimiento hoy

| Productor | Entrada | Salida | Falta |
|---|---|---|---|
| Ruta A (`render_estatico.py`) | `copies.json` + `matriz.json` | PNG + HTML fuente | que el Maker arme el fragmento (lo hace a mano con `templates/paquete.json`); no hay `--simular` (el render ya es 0 créditos) |
| `d6-sketch-animado` | `brief_desde_oferta.py` → `brief-sketch.json` (equivalente al brief) | `mp4` + `assets.json` + `licencias.json` + `costos.jsonl` previo | fragmento de `paquete.json`, salida `--json`, `--simular` unificado, `qc6.py` sobre el mp4 |
| Ruta B | matriz + guion + cotización | `mp4` | nunca corrió; sin API fuera de la sesión del dueño |

Cuando S-A fije `variante_formato` y `subformato` en `contratos/creativos.schema.json` (`PEDIDOS.md` #3), el `formato-brief.json` pasa de propuesta a contrato.
