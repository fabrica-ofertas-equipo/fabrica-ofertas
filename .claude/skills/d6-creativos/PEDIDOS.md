# Pedidos de D6 0.2.0 a S-A, S-B y al dueño (2026-11-07)

Todo lo que D6 0.2.0 necesita y **no es de S-C** (contratos, `empresa/*.yaml`, `engine/`, `agentes/hooks/`, `departamentos/`, el runner y las decisiones del dueño). Origen: `docs/_historial/mentor-sistema/brechas/01-cerebro-y-creativos.md` (B1-12, 14, 15, 16, 17, 21, 22). Resumen también en `docs/_historial/coordinacion-sesiones.md` («Avisos de S-C — D6 0.2.0»). Los pedidos de 0.1.x que siguen vigentes están en `references/dependencias.md` §4. Lo que está **hecho** y probado (`tests/creativos/`): `scripts/qc6.py`, `scripts/ganchos.py` + `datos/ganchos.jsonl`, `scripts/tanda.py`, plantillas y referencias.

| # | A quién | Qué | Brecha | Bloquea |
|---|---|---|---|---|
| 1 | S-A | Topes de diseño contra J3 y claves de la tanda en `parametros.yaml` | B1-14 | ejecutar J3 como está |
| 2 | **DUEÑO** | Elegir el régimen de aprobación de la tanda y el volumen por día | B1-15 | noche sin humano (mientras tanto: A) |
| 3 | S-A | `contratos/creativos.schema.json`: `variante_formato`, `variante_de`, `origen_locale`, `plantilla_id`, `subformato` | B1-20, B1-23 | medir qué formato vende |
| 4 | S-A | Resolver la contradicción «ganador traducido» (`localizacion.md` y J5 contra `docs/08` :316 y la spec 07) y escribir el modo tanda en la spec 07 | B1-16, B1-20 | traducir ganadores |
| 5 | S-A | J11: retirar `X32_REVISOR` y el revisor nativo de la spec 07 y 16 y de los parámetros | B1-12 | primer paquete en polaco |
| 6 | S-A + X1 + S-B | Gate de la tanda y alcance del sello de X1 «por plantilla» (solo régimen B) | B1-15 | régimen B |
| 7 | S-A | Ruta definitiva del dossier de inmersión y de los glosarios por idioma | B1-12 | capa 1 y 5 del QA de idioma |
| 8 | S-B | Allowlist de `agentes/hooks/herramientas.yaml` para `qc6.py`, `ganchos.py`, `tanda.py` | B1-17, 22, 16 | que el Maker los corra bajo el runner |
| 9 | S-B | Runner: `qc6.py lote` antes del QA y `qa/.l1/`; `ocr_check` con el motor de Vision | B1-17 | L1 de código del tramo B |
| 10 | S-B | Planificador nocturno de la tanda (ventanas, paralelismo, Chrome en el runner) | B1-16 | turno noche automático |
| 11 | S-B / X1 | Lint de compliance: 4.º nicho y falsos negativos pl-PL | B1-11 | sellar en `habilidades_hobbies` |
| 12 | S-B / X2 | Banco de hooks de X2: migrar `ganchos.jsonl` y fijar `D6_GANCHOS` | B1-22 | memoria de ganchos para agentes |
| 13 | S-B | `dim_anuncio`: `hook_tipo`, `formato`, `variante_formato`, `variante_de` | B1-23 | ranking de ángulo, gancho y formato |
| 14 | DUEÑO | Los 3 videos de Mentor (jurado, surfeo, «exclusivo de creativos»), si los tiene | B1-16 | calibrar la tanda con su criterio |

---

## 1 · S-A — Topes de diseño contra J3 y claves de la tanda (`empresa/parametros.yaml`, `contratos/parametros.schema.json`, spec 07 y 08)

J3: «una campaña CBO con ~10 creativos a 50-100 USD; 1 día sin venta → baja». Hoy `n_anuncios_max = min(creativos.n_anuncios_max 8, campana.n_anuncios_tope 6, floor(gasto_test_plan / (3 × cpa_obj)))`: con 50-100 US$ y un CPA de 15-18 US$ el último término da 1 y el paquete no se genera. Valores **`[SUPUESTO]`** (el dueño fija los reales):

| Clave | Hoy (rango) | Propuesta | Nota |
|---|---|---|---|
| `creativos.n_anuncios_max` | 8 ([2, 8]) | **10** ([2, 12]) | ~10 creativos por CBO |
| `campana.n_anuncios_tope` | 6 ([3, 8]) | **10** ([3, 12]) | hoy es el tope que manda |
| `creativos.n_conceptos_test` | 4 ([3, 6]) | **5** ([3, 8]) | 5 conceptos × 2 hooks |
| `creativos.hooks_por_concepto` | 2 ([1, 3]) | 2 | sin cambio |
| `creativos.reserva_conceptos` | 2 ([1, 4]) | 2 | sin cambio |
| factor «3» de `n_anuncios_max` | 3 | que **no limite** el paquete de lanzamiento | en J3 la unidad de decisión es la campaña (1 día sin venta con el presupuesto gastado → baja), no cada anuncio. Lo decide S-A junto con S-B (`engine.guard`, D7/D8); `validar_d6.py nmax --k` ya admite otro factor, pero no se cambia la regla sin su decisión |
| `creativos.candidatos_por_dia_min` / `_max` (por idioma) — **nuevas** | — | **5 / 10** | la tanda; separa los *candidatos* (baratos, Ruta A) de los *anuncios del test* |
| `creativos.tandas_por_semana` — **nueva** | — | **7** | turno noche diario |
| `creativos.muestreo_tanda_pct` — **nueva** | — | **20** | solo régimen B |
| `creativos.suplentes_listos_min` — **nueva** (B1-19) | — | 3 | suplentes ya probados |
| `creativos.margen_regeneracion_pct` | no existe | 20 | sigue pendiente de 0.1.x (`cost_preflight` sale 5 sin él) |
| `inmersion.calcos_max` | no existe | a fijar | umbral de calcos de la capa 5 del QA de idioma (QM-14) |

Mientras no cambie, D6 sigue la regla más estricta (SKILL §3 y `references/modo-tanda.md` §2).

## 2 · DUEÑO — Régimen de aprobación de la tanda y volumen por día

Dos opciones (B1-15), explicadas en `references/modo-tanda.md` §5. **No las decidió S-C**; `tanda.py bandeja` rechaza `muestreo` sin `--confirmado-por-dueno`.

- **A · Aprobación total.** Ves cada pieza de la carpeta «por aprobar» cada mañana. Sin riesgo de rechazo por algo no visto; el cuello de botella eres tú.
- **B · Muestreo con sello de X1 por plantilla.** Ves lo que el control automático marca (`revisar`), las piezas de plantillas sin sello vigente y una muestra (indica el %); lo demás queda «lista para sello» y solo el sello vigente de X1 sobre la plantilla, verificado por el motor, permite activarlo. Noche sin humano; un defecto que el control no detecta (una cara mal hecha, un logo dentro de una imagen, un matiz torpe del idioma) llegaría a Meta con la cuenta única. Exige además los puntos 6 de abajo.

**Pregunta para copiar:** *«¿Cómo quieres aprobar la tanda diaria: A) la veo toda cada mañana, o B) solo lo que el control automático marca y una muestra del ___ %, y lo demás sale con el sello de X1 por plantilla? ¿Y cuántos candidatos por idioma y por día, entre 5 y 10?»* Recomendación de S-C: **empezar por A** y pasar a B cuando haya varias tandas con `qc6` sin falsos. Mientras no responda: **A**.

## 3 · S-A — Contrato `creativos` (MINOR; junto al 1.1.0 ya pedido de `riesgo_pieza`)

`variante_formato` por anuncio con los valores `estatico-html`, `demo-pantalla`, `voz-en-off-broll`, `pov-proceso`, `presentador-ia`, `vsl-45-90s` y los **nuevos** `imagen-pregunta`, `relevo-otra-apertura`, `ganador-traducido`; `variante_de` (el `ad_name` que se reemplaza o traduce), `origen_locale` (idioma del ganador de origen), `plantilla_id` (identidad de la plantilla HTML, para el sello por plantilla) y `subformato` (hoy en `notas`). Mientras tanto viven en `matriz.json` y en `datos/ganchos.jsonl`.

## 4 · S-A — «Ganador traducido» y modo tanda en la spec

`references/localizacion.md` reglas 1 y 7 («no se traducen guiones», «no se reutilizan assets con texto») chocan con J5 y con `docs/08-protocolo-estadistico-del-testeo.md:316` («mismos creativos traducidos y revisados»). D6 0.2.0 las leyó así: **no se traduce lo ajeno** (J13) y **no se reutiliza el PNG** (se re-renderiza), pero **sí se traduce un ganador propio** con traducción fiel + 5 capas + X1 por `locale` (`references/formatos-que-miden-bien.md` §3). Pido confirmar esa lectura en la spec 07 y en `docs/08`, y añadir a la spec 07 el modo `tanda` (§4 y §7), los formatos de §5.12 y la regla «de noche se produce, a la tarde se carga».

## 5 · S-A — J11: retirar el revisor nativo de los validadores y la spec

- `scripts/validar_esquemas.py:2188-2189` (`X32_REVISOR`): `obligacion_legal_idioma = true` y `revisor_nativo = false` es hoy ERROR («X1 emite ROJO»). Debe ser **aviso**, como ya hizo D5 (`test_revisor_nativo_no_bloquea_pero_avisa`). La oferta de Polonia (`ofertas/OF-202611-91/mercado.json`) lo dispara.
- Spec 07 y 16 (`departamentos/`): `creativos.revisor_nativo_idiomas`, `producto.linguistica_muestreo_nativo_posterior`, `mercados.*` y la regla de X1 «sin revisor no se sella» pasan a **opcional**.
- Esquema de `mercado.json`: `revision_linguistica.revisor_nativo` deja de ser obligatorio con `obligacion_legal_idioma`.

## 6 · S-A + X1 + S-B — Gate de la tanda y sello «por plantilla» (solo si el dueño elige B)

(a) `contratos/gates.json`: el gate «aprobar tanda» (hoy D6 usa H en N0-N1, S en N2-N3, A en N4; J2 ya quitó el gate humano de activar). (b) Qué cubre exactamente el sello de X1 por plantilla: `plantilla_id` + hash de la plantilla HTML + el conjunto de `claim_id` permitidos + lint verde del texto; vigencia (el sello vence). (c) `engine/guard.py` debe **verificar** ese sello antes de activar una pieza `lista_para_sello_x1` (`tanda.py` solo cita el sello, no verifica ninguna firma). (d) La pantalla `#/fabrica` hoy no tiene botones de aprobar.

## 7 · S-A — Ruta definitiva del dossier de inmersión y de los glosarios

J12 pide una etapa de inmersión antes de D3. Hoy el único dossier es el del piloto (`docs/_historial/modelado-piloto/inmersion/pl-voz-del-cliente.md`). Fijar la ruta (propuesta: `ofertas/<id>/02-validacion/dossier_voz.md` + `.json`) y los glosarios `empresa/mercados/glosarios/<locale>.md` (M1). D6 los lee como entrada; sin ellos, `[SUPUESTO]`.

## 8 · S-B — `agentes/hooks/herramientas.yaml`

Faltan los tres scripts nuevos (el hook denegaría al `d6-maker` lo que su ficha dice que puede correr). Banderas generadas desde los `argparse` (una prueba de `tests/creativos/test_skill_d6_020.py` comprueba que esta lista siga al día):

```yaml
  ".claude/skills/d6-creativos/scripts/qc6.py":
    flags: ["lote", "motores", "pieza", "--ad-name", "--audio-esperado", "--copies", "--esperado", "--estricto", "--guion", "--hablado", "--html-fuente", "--json", "--locale", "--macro-nicho", "--matriz", "--max-fotogramas", "--oferta-dir", "--paquete", "--permitir", "--precio", "--precio-visible", "--presentador", "--prohibir", "--salida", "--salida-l1", "--simulado", "--simular"]
  ".claude/skills/d6-creativos/scripts/ganchos.py":
    flags: ["agregar", "buscar", "estadisticas", "listar", "marcar", "rechazar", "validar", "--ad-name", "--almacen", "--angulo", "--base", "--con-base", "--estado", "--estricto", "--estructura", "--formato", "--fuente-cita", "--fuente-ruta", "--fuente-seccion", "--hook-tipo", "--hoy", "--id", "--idioma", "--incluir-referentes", "--json", "--locale", "--minimo", "--nota", "--oferta-id", "--origen", "--por", "--riesgo-e01", "--rol", "--sin-base", "--sin-fuentes", "--texto", "--top", "--traduccion-es", "--umbral", "--uso", "--variante-formato", "--x1"]
  ".claude/skills/d6-creativos/scripts/tanda.py":
    flags: ["bandeja", "plan", "--angulos-nuevos", "--confirmado-por-dueno", "--fecha", "--json", "--locale", "--matriz", "--maximo", "--minimo", "--muestra-pct", "--objetivo", "--oferta-id", "--qc6", "--regimen", "--relevos", "--salida", "--sellos", "--tanda-dir", "--traducciones"]
```

Además (pendiente de 0.1.x): `render_estatico.py` necesita `--oferta-dir` en sus flags. `qc6.py` compila `swiftc` y llama a `ffmpeg`, `ffprobe`, `whisper-cli` y `pdftoppm` **por dentro**: el hook solo ve la línea de Bash, pero el sandbox del runner debe permitirlos (sin red). Si el sandbox no permite compilar, los puntos de OCR y personas salen `revisar`, nunca verde.

## 9 · S-B — Runner: `qa/.l1/` y motor de OCR

(a) Antes del QA tramo B, correr `qc6.py lote --oferta-dir ofertas/<id> --salida-l1 <tmp>` y **fusionar** sus `checks` (D6-L1-02, 06, 07, 08) en `ofertas/<id>/qa/.l1/d6-v<n>.json` (el Maker no puede escribir ahí). Forma: `{check_id, resultado ∈ pass|fail|no_aplica, detalle}`; `revisar` sale `no_aplica` y no cuenta como verde. Si el JSON dice `modo: simulado`, no es evidencia. (b) `scripts/creativos/ocr_check.py`: añadir `--motor-ocr vision` que use `qc6.OcrVision` (hoy la CLI sale 2 «sin motor»). (c) `agentes/contexto.py` `TABLA_ETAPAS["D6"]` (SB-5) y `references/dependencias.md` §1. (d) Que el servicio donde corra D6 tenga Chrome (SB-18), `ffmpeg`, `whisper-cli` + modelo; solo macOS tiene Vision: en Linux, OCR y personas salen `revisar` y hace falta otro motor (Tesseract) detrás del mismo `MotorOCR`.

## 10 · S-B — Planificador nocturno de la tanda

Hoy el único cron es el del Worker `watchdog`; no existe `empresa/robots.yaml`. Se pide: ventana de producción por idioma (00:00-07:00 hora local `[SUPUESTO]`), un trabajo por idioma que ejecute los pasos T0-T7 de `references/modo-tanda.md` (`tanda.py plan` → Maker en modo tanda → `qc6.py lote` → `tanda.py bandeja`), límite de paralelismo (la fuente: «una IA por idioma, 4 en paralelo»), la regla de horario (la tanda **no** carga a Meta; D7 carga por la tarde, en pausado), y el relevo disparado por D8 (`pedidos_creativos`, B1-19).

## 11 · S-B / X1 — Lint de compliance

`compliance.lint_claims` rechaza `--macro-nicho habilidades_hobbies` (B1-11) y `compliance/reglas_sensibles.yaml` no tiene reglas del 4.º nicho; no detecta `płynnie`, `w 30 dni`, `sekret poliglotów`, `tysiące zadowolonych klientów`, `Zostało tylko 3` (pl-PL) ni los patrones de it, fr, de y ro de `references/lista-rojo-amarillo.md` §2. `scripts/qc6_reglas.py` los cubre como red adicional `[HIPÓTESIS]`; cuando el lint oficial los cubra, esa lista se reduce.

## 12 · S-B / X2 — Banco de hooks

Cuando exista `empresa/memoria/banco_hooks.jsonl`, migrar los `ganchos.jsonl` por oferta y `datos/ganchos.jsonl` (campos ya compatibles: estructura y rechazos por claim, nunca claims) y apuntar `D6_GANCHOS` a una ruta fuera de `.claude/`. Mientras tanto no se crea `empresa/memoria/`.

## 13 · S-B — Medir qué vende

`datos/migraciones/0003_vistas_d8.sql:26`: `dim_anuncio(ad_id, oferta_id, concepto_id)` sin `hook_tipo`, `formato`, `variante_formato` ni `variante_de`. El `ad_name` de D6 ya los permite unir con `matriz.json` y con `ganchos.jsonl` (`ganchos.py marcar --ad-name`). Las cifras de la fuente (1,83 / 1,67 / 1,39 / 1,28) no son prior.

## 14 · DUEÑO — Videos de Mentor

Si tiene los tres videos que él menciona (cómo funciona el jurado, el robot de surfeo y «el exclusivo de creativos»), pasarlos: ahí están los criterios de formato y las proporciones de la tanda que este video no da (cuántas piezas, qué mezcla de relevos y ángulos, qué mide el «retorno»). `[NO VERIFICADO]` si son públicos.
