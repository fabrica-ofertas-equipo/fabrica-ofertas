# Biblioteca de ganchos y antirrepetición (`scripts/ganchos.py`)

Brecha B1-22. D6 tenía 8 `hook_tipo` cerrados (`tipos-de-hook.md`) pero ningún historial que evitara repetir un gancho, ni un banco propio dentro del repo: el banco de X2 (`empresa/memoria/banco_hooks.jsonl`) no existe y el `ideador-guiones` que usa el dueño vive en `~/.claude/skills/` (26 estructuras, historial y banco para otras marcas): los agentes desatendidos no lo leen y varias de sus estructuras chocan con las reglas duras de D6 (`antes-despues`, `ancla-millonaria`, `historia-real`). Por eso hay una versión mínima **dentro del repo**, ya filtrada por esas reglas y con historial por `oferta_id`. No depende de `ideador-guiones`.

## 1. Qué guarda

Dos clases de JSONL, una línea por gancho:

- **Biblioteca base** `datos/ganchos.jsonl` (dentro de la skill): la semilla (§4) y los ganchos de referentes. **Solo lectura para los agentes**: el Maker no puede escribir en `.claude/` (SKILL regla 11) y cambiar un archivo de una skill pinneada cambia su hash.
- **Almacén de escritura** por oferta: `ofertas/<id>/06-creativos/ganchos.jsonl` (`--almacen`, o la variable `D6_GANCHOS`). Ahí escribe el Maker: es el historial por `oferta_id` de B1-22. Sus ids siguen a los de la base (`G-0034`, …); un id se identifica con `(oferta_id, id)` si algún día se funden los archivos.

Todo comando compara contra la **unión** de la base y el almacén; `agregar` y `marcar` escriben solo en el almacén (`--sin-base` desactiva la base; `--base` suma otras bibliotecas de solo lectura, p. ej. la de otra oferta del mismo idioma). Sin `--almacen`, el almacén es la propia base (uso de una persona en su sesión). Campos de cada línea:

| Campo | Qué es |
|---|---|
| `id` | `G-NNNN`, correlativo |
| `oferta_id` | oferta a la que pertenece (`null` en referentes) |
| `locale`, `texto`, `traduccion_es` | el gancho tal como sale en la pieza; su traducción al español sirve para detectar la copia de un referente traducido |
| `formato`, `variante_formato` | `imagen`/`video`/`carrusel`; p. ej. `imagen-pregunta`, `relevo-otra-apertura`, `ganador-traducido` |
| `hook_tipo` | uno de los 8 del vocabulario cerrado |
| `angulo`, `estructura` | el ángulo y **la forma que se hereda** (obligatoria en los referentes) |
| `origen` | `propio` · `dossier` · `referente` · `ganador` · `ideador` |
| `rol` | `candidato` (se puede usar) o `referencia_anticopia` (solo para detectar parecidos) |
| `estado` | `borrador` · `aprobado` · `usado` · `rechazado` · `retirado` (candidatos); `referencia` (referentes) |
| `x1`, `riesgo_e01` | `sin_dictamen` / `pass` / `fail`; riesgo preliminar de atributo del espectador (`bajo`/`medio`/`alto`): lo decide el lint y X1, no este campo |
| `uso` (referentes) | `heredar_estructura` o `descartar` (prueba social, urgencia, precio o promesa implícita fuerte) |
| `fuente` | **de dónde sale**: `ruta` (archivo del repo), `seccion`, `cita_ids` |
| `anuncios` | los `ad_name` donde se usó |

## 2. Comandos

```bash
G=".claude/skills/d6-creativos/scripts/ganchos.py --almacen ofertas/<id>/06-creativos/ganchos.jsonl"   # el Maker siempre con --almacen
.venv/bin/python $G rechazar  --texto "…" --locale pl-PL --oferta-id OF-… [--traduccion-es "…"] [--umbral 0.8] [--estricto]
.venv/bin/python $G agregar   --texto "…" --locale pl-PL --hook-tipo pregunta-tarea --formato imagen --angulo vocabulario-por-tema \
                              --fuente-ruta docs/…md --fuente-seccion "§11.2" --fuente-cita W88083229 [--oferta-id …] [--variante-formato imagen-pregunta]
.venv/bin/python $G buscar    --texto "…" [--locale pl-PL] [--top 5] [--incluir-referentes]
.venv/bin/python $G listar    [--locale … --formato … --angulo … --hook-tipo … --estado … --oferta-id … --incluir-referentes] [--json]
.venv/bin/python $G estadisticas [--por formato|angulo|idioma|hook_tipo|estado|origen] [--incluir-referentes] [--json]
.venv/bin/python $G marcar    --id G-0003 --estado usado --x1 pass --ad-name c01-mapa_img_h1_v1
.venv/bin/python $G validar   # ids únicos, vocabulario, fuentes que existen
```

Códigos: 0 ok · 3 rechazado o inválido · 2 uso.

## 3. Antirrepetición y anticopia

- **Similitud difusa** (0-1): el mayor entre la razón de secuencia de `difflib` y la media de Dice de trigramas y Jaccard de palabras, sobre texto plegado (sin mayúsculas, tildes ni puntuación; `ł→l`, `ß→ss`). Detecta ediciones pequeñas y el mismo gancho con las palabras reordenadas.
- **Umbral:** `memoria.sim_dup` de `empresa/parametros.yaml` (0,80); si no se puede leer, 0,80 `[SUPUESTO]`. Un candidato con similitud ≥ umbral con **cualquier** gancho guardado del mismo idioma (incluidos los `rechazado`, `retirado` y los de otras ofertas) se rechaza: una frase rechazada por Meta, Stripe o X1 **nunca** se reenvía, ni retocada (SKILL regla 13).
- **Anticopia (J13):** contra los `referencia_anticopia` de **cualquier** idioma, por similitud del texto y, si se pasa `--traduccion-es`, por la traducción al español. Además, una secuencia de palabras iguales ≥ `compliance.ngrama_copia_palabras` (8) rechaza; entre `ngrama_alerta_temprana_palabras` (6) y 7 da una alerta. Detecta un calco palabra por palabra; **no detecta** un calco en otro idioma sin `traduccion_es`.
- **Estructura repetida** (mismo `angulo` + `hook_tipo` + `formato` en la misma oferta) es un **aviso**, no un rechazo: con 5-10 piezas por día el espacio de combinaciones se agota y lo que evita el clon es el texto. `rechazar --estricto` la vuelve exit 3.

## 4. Semilla (2026-11-07)

33 ganchos, cada uno con su `fuente` (un test comprueba que el texto aparece literal en el archivo citado):

| Origen | Cantidad | Fuente | Estado |
|---|---|---|---|
| `dossier` · candidatos pl-PL | 11 (los 10 de §11.2 + el extra de muestra gratis) | `docs/_historial/modelado-piloto/inmersion/pl-voz-del-cliente.md` §11.2 | `borrador`, `x1 = sin_dictamen`; los redactó el agente de la inmersión (no son citas) y llevan `riesgo_e01` (alto en 4: los que afirman una condición del lector o aluden a su situación económica) |
| `referente` · anticopia | 22 | `docs/_historial/modelado-piloto/referentes/{mapas-mentales-idiomas,aprender-coreano,colorear-arte-y-yoga}.md` | `referencia`; 17 con `uso = heredar_estructura` y 5 con `descartar` |

Los ganchos del dossier **no se usan tal cual**: pasan por la regla de atributo del espectador (se reencuadran a tercera persona o a pregunta sobre la tarea), por las 5 capas de idioma y por X1. Los referentes se guardan solo para no parecerse: su texto es expresión ajena.

## 5. Cómo lo usan el Maker y el QA

- **Maker, paso 4 y tanda T2:** (siempre con `--almacen ofertas/<id>/06-creativos/ganchos.jsonl`) antes de escribir el cuerpo, `rechazar` con el gancho; si entra, `agregar` con su fuente; al aprobarse, `marcar --estado aprobado`; al lanzarse, `--estado usado --ad-name`. Un hook nuevo sin `fuente.cita_ids` es `[SUPUESTO]`.
- **QA (solo lectura):** `datos/ganchos.jsonl` y `06-creativos/ganchos.jsonl` son archivos que puede leer con `Read`; verifica por muestreo que el gancho del paquete esté en la biblioteca con su fuente y que no repita ni copie (D6-L1-08, R3, R8). No ejecuta el script (no tiene Bash): el runner deja `rechazar` en `qa/.l1/` (`PEDIDOS.md` #8-#9).
- **Estadísticas:** `estadisticas` responde «qué formato, ángulo e idioma se probó» y «qué `hook_tipo` falta probar»; el ranking por **resultado** (qué ángulo vendió) es de D8/F2 (B1-23) y llegará cuando haya ventas.

## 6. Migración a X2

Cuando exista `empresa/memoria/banco_hooks.jsonl` (X2, B1-04), los almacenes por oferta y la base se vuelcan ahí con una migración de S-B (`PEDIDOS.md` #12): los campos ya son los de un banco (estructura de hooks y rechazos por claim, **nunca claims**). Mientras tanto no se crea `empresa/memoria/`. La base cambia solo cuando una persona la edita desde su sesión (nuevas semillas o referentes), con `ganchos.py agregar` sin `--almacen` y registro en el `CHANGELOG.md`.
