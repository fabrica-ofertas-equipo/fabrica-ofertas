# Herramientas: lo que lee un agente, lo que escribe el código, y la lista `deny`

## 1. Regla

**Las herramientas de Meta que escriben están en `deny` para agentes (Maker y QA) y estos agentes no las usan nunca.** Crear el borrador, calcular el `hash_config`, el preflight y activar son **código** (`meta/`, `scripts/meta_*.py`) con orden firmada y sello de X1. Un agente propone y prepara el expediente; no tiene credenciales de Meta (docs/06 D-19, docs/09 H2: el runner con clave de API no carga ningún conector MCP).

## 2. Qué puede llamar el agente (solo lectura `ads_get_*`, solo en sesión interactiva)

| Herramienta MCP (`mcp__claude_ai_Meta_ADS__…`) | Para qué en D7 | Quién |
|---|---|---|
| `ads_get_ad_accounts` | estado, moneda, método de pago, `is_queryable`, mínimo diario | Maker |
| `ads_get_ad_account_pages` | página vinculada | Maker |
| `ads_get_datasets`, `ads_get_dataset_details`, `ads_get_dataset_quality`, `ads_get_dataset_stats` | dataset de la oferta, EMQ, eventos recientes (rango ≤ 28 días) | Maker |
| `ads_get_ad_entities` (`draft` y vivo), `ads_get_field_context` | leer el borrador y el árbol creado; verificar campos antes de pedirlos | Maker |
| `ads_get_errors` | `active_errors` por entidad | Maker |
| `ads_get_ad_preview` | vistas previas por anuncio y ubicación (`…_screenshot` no está pensada para uso del modelo) | Maker |
| `ads_account_get_activity_logs` | cambios hechos fuera del plan (deriva); lectura pura, está en la lista del Maker junto a `ads_get_*` (SC-4 no la retira: es de D7, no de D3-D6) | Maker D7 / dueño / X1 |

El Maker no tiene `WebFetch` ni `WebSearch`; los conectores existen solo en la sesión interactiva del dueño (el runner desatendido no los carga). El QA **no** tiene MCP (`Read`, `Grep`, `Glob`): juzga sobre `07-campana/preflight.json`, `07-campana/lectura_viva.json` y el informe L1 `qa/.l1/d7-v<n>.json`, generados por código (`dependencias.md` A13). Las lecturas del Maker se **anotan en el log** con sus valores literales (tipo `LECTURA_*`, `templates/lanzamiento.log.jsonl`) como bitácora para retomar el trabajo: **sin valor probatorio**, el QA no las toma como evidencia.

## 3. `deny` (nunca)

Piso de `docs/09` §6 y `docs/_historial/settings-piso-hoy.propuesta.json`:
`ads_activate_entity` · `ads_boost_ig_post` · `ads_delete_*` · `ads_creative_*` (incluye `upload_*`, `update*`, `create_image_variations`) · `ads_experiment_*` · `ads_*custom_audience*` · `ads_pixel_*` y `ads_catalog_*` (escrituras) · `ads_finalize_local_ad_image_upload`. En clase `ask` (el dueño confirma cada llamada; en el runner equivale a denegar): `ads_create_campaign`, `ads_create_ad_set`, `ads_create_ad`, `ads_create_creative`, `ads_update_entity` (el hook solo admite `{"status":"PAUSED"}`; `fields` llega como cadena JSON).

Los subagentes `d7-maker` y `d7-qa` **no listan ninguna de estas herramientas** en `tools`. En N0–N1, si el dueño quiere crear el borrador con el conector en su sesión interactiva, lo hace la **sesión principal** con los payloads exactos que dejó el Maker (clase `ask`, una confirmación por llamada), nunca el Maker; el resultado se registra en el log y se valida con `ads_get_*`. Conflicto resuelto: la spec sigue el piso de `docs/09` §6 (`ads_creative_*` en `deny`; la subida de creativos la hace el código o el dueño a mano), no esta skill (`dependencias.md` C3).

`ads_create_*` deja DRAFT, pero **publicar puede dejar ACTIVO**: todo publish es activación y exige hook, sello de X1, `object_ids` exactos y orden firmada. Pruebas previas a N2 `[VERIFICAR]` (cuenta de prueba): estado tras publicar con y sin `publish_as_active`; macros en `link_url`/`url_tags`; revisión con anuncio programado.

## 4. Código real (verificado en el repositorio, 2026-11-06)

Todos corren en `dry-run` o `fixture`; **`--modo live` está bloqueado** (código 4: no hay Transporte real). Salida común: `{ok, modo, codigo, datos, avisos}` con `--json`.

| Qué | Módulo / comando | Estado |
|---|---|---|
| Nombres y URL | `python -m meta.nombres {campana,conjunto,anuncio,url,resolver} …` (puro, sin red) → `scripts/d7.py nombres` | usable; CLI propio |
| Presupuesto | `python -m meta.payloads presupuesto --economia economia.json --n-anuncios-paquete N [--escenario pes\|central\|opt] [--dias D] [--spend-cap-minimo-meta M]`; función `meta.payloads.calcular_presupuesto` (aplica `tarifa_meta_bp`, calcula `n_anuncios`/`total`, `spend_cap` o candado alternativo) → `scripts/d7.py presupuesto` (delega en ella) | usable; la tarifa y `n_anuncios` ya están (A6 resuelto) |
| Offset de moneda | `meta.monedas.a_unidad_meta`, `offset_meta` | usable |
| Borrador `PAUSED` idempotente por prefijo `{oferta_id}_TEST_` | `python -m scripts.meta_crear --oferta OF-… --campana campana.json --creativos creativos.json --ad-account act_… --pixel-id … [--modo dry-run\|fixture] [--fixture reglas.json] [--salida ids_meta.json] --json` | solo dry-run y fixture; no sube medios |
| Preflight P01–P25 | `python -m meta.preflight --oferta OF-… --entradas entradas.json --campana campana.json [--salida preflight.json]` → `scripts/d7.py preflight` | sin red; el modo `fixture` nunca habilita activar |
| PX1–PX4 | `meta.preflight.items_px(EntradasPX)`: informe **aparte**, nunca dentro del `preflight.json` sellado (el esquema rechaza `P26+`); PX3 da ROJO informativo sin matriz país × nivel | existe; MINOR del esquema pendiente (LT-12) |
| Estado vivo para el QA | `python -m meta.lectura_viva --oferta OF-… --ids-meta ids_meta.json --hash-config sha256:… [--salida lectura_viva.json] [--incluir-creativo]` (reutiliza `meta.activar.leer_estado_vivo`) | existe; `[PENDIENTE: SB-12]` `engine.orq` no lo genera aún antes del QA; trae `campana`, `conjunto`, `anuncios` sin `effective_status`, DSA ni `active_errors`; sin esquema |
| Activación (N12) | `python -m scripts.meta_activar --oferta … --campana campana.json --ids-meta ids_meta.json --hash-config sha256:… --cuenta cuenta.json --monto <max_teorico_diario> --moneda … [--sello sello.json] [--creativos creativos.json] [--modo dry-run\|fixture]` | sello de X1 (TOCTOU) + 7 pasos de `engine.guard` + **relee el estado vivo y lo compara campo por campo con `campana.json`** (`diferencias_config_viva`: presupuesto, `spend_cap` o candado, evento, targeting, creativo, categorías; enlace y textos solo con `--creativos`; el DSA propio espera `campana.economia.dsa`, LT-10); activa anuncios → conjunto → campaña con rollback |
| Diagnóstico de los 7 pasos | `python -m engine.guard comprobar --operacion activar --oferta … --monto … --moneda … --sello … --cuenta cuenta.json --json` | sin efectos |
| Monitoreo | `python -m meta.monitor --oferta … --ids-meta ids_meta.json --ventana-h {1,6,24,48,72} --gasto-real N --gasto-esperado N --moneda … --estado-aprendizaje … --clics-enlace N --vistas-landing N [--adid-capturado-bp N] [--historial h.json]` | CLI existe; pausa solo anuncios `DISAPPROVED`; `[PENDIENTE: SB-12]` pausa por gasto, `active_errors`, congelación por eje y el disparador T+1…72 h en `engine.orq` |
| Pausa (kill switch capa 2) | `python -m scripts.pausar --campana-id ID` o `--ad-account act_…` | dry-run/fixture |
| Validar artefactos | `python -m scripts.validar_esquemas oferta ofertas/<id>`; `scripts/d7.py validar --esquema campana --archivo …` | usable |
| Orquestador | `python -m engine.orq {crear,estado,siguiente,ejecutar,firmar,ingresar,nivel,activar,ciclo-d8,veredicto,cerrar,pausar}` | existe. `ejecutar` solo corre `--modo fixture --fixture DIR`; `activar --live` bloqueado; `reanudar` no está en la CLI (solo la API de Python) |
| Firmar el gate | `python -m engine.orq firmar --oferta … --accion activar_campana --hash-objetivo sha256:… --clave-privada <ruta> [--como dueno] [--nonce …]` | existe. La clave privada Ed25519 la pone el dueño en su terminal: nunca en un chat ni en el repositorio. No admite `--object-ids` `[PENDIENTE: SB-2]`; nadie escribe aún `07-campana/aprobacion.json` |

Códigos de salida de los CLI: 0 correcto · 2 uso · 3 validación · 4 bloqueado (PAUSA, infra, sello, orden sin firmar, `--modo live`) · 5 límite o parámetro faltante · 6 externo.

## 5. Mapa MCP ↔ API (para N2+)

| Acción | MCP (sesión Code, solo N0–N1) | Marketing API (código N2+, usuario de sistema «operador», no admin, versión fijada) |
|---|---|---|
| leer cuenta / dataset / errores | `ads_get_*` | `GET act_<id>`, `/<dataset>/stats`, `/<obj>?fields=…` |
| crear campaña / conjunto / creativo / anuncio | `ads_create_*` (`ask`) | `POST act_<id>/campaigns|adsets|adcreatives|ads` con `status=PAUSED` (`meta.crear`) |
| activar | **nunca por MCP** (`deny`) | `POST /<id> status=ACTIVE` objeto por objeto: anuncios → conjunto → campaña (`meta.activar`) |
| pausar | `ads_update_entity {"status":"PAUSED"}` (hook; solo la sesión principal del dueño, no el Maker) | `POST /<id> status=PAUSED` (`meta.pausar`, `forzar=True`) |

`allow_partial_publish`, `ignore_validation_errors`, `publish_as_active` y `object_ids` son parámetros del conector MCP en modo borrador; la Marketing API no los tiene. Tope de plataforma: ≥ 30 s entre ediciones del mismo objeto, ≤ 4 cambios de presupuesto por hora por conjunto (`limites.segundos_min_entre_ediciones`, `max_cambios_presupuesto_por_hora_por_conjunto`).
