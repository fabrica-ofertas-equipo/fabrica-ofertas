# Registro de decisiones del dueño que bloquean (hueco 7 de la auditoría)

**Problema** (`docs/_historial/auditoria-pedidos-primera-sesion.md` §6.7): primer mercado y oferta, cuenta de Meta, límites, métodos de pago y líneas rojas están listadas en `docs/00-decisiones-y-tareas-del-dueno.md` §0, pero ningún paso del flujo las convertía en un **bloqueo visible**. **Solución de esta skill:** el estado de cada decisión **se deriva de los archivos reales** (no de una casilla de un `.md`), con `scripts/bloqueos_dueno.py`; el panel puede mostrarlo sin interpretar texto libre.

## 1. Catálogo (ids estables)

| `id` | Decisión | Resuelta cuando… (archivo y clave) | Qué bloquea | Quién y cómo se cierra |
|---|---|---|---|---|
| `limites` | Límites completos y **sellados** (incluye la pérdida máxima por oferta, diferida) | `engine`-evaluación `scripts.validar_esquemas.evaluar_limites` de `gastar` y `activar` sin faltantes, con `sello` | gastar, activar, D7, brief aprobable (`orq crear` sale 5) | dueño: `engine.propuestas proponer` (exige la `economia.json` de D3) → `sellar` (`--live` con `FABRICA_ENTORNO=produccion` y `--clave-privada` con la ruta que pone él); no existe `engine.limites proponer\|sellar` |
| `primer_mercado` | Primer locale y países | `limites.locales_permitidos` y `limites.paises_permitidos` no vacíos | brief (`B13_*`), M1 primer lanzamiento, D2 en adelante | dueño con datos de M1 (hipótesis, ningún prior) + `engine.propuestas sellar` |
| `cuenta_meta` | Una sola cuenta limpia y su moneda | `limites.cuentas_permitidas` no vacía y `limites.moneda_limites` no nula | brief (`B13_CUENTA`, `B10_MONEDA`), D7, toda activación | dueño (nunca abrir otra cuenta para esquivar la deshabilitada) + `engine.propuestas sellar` |
| `lineas_rojas` | Líneas rojas aprobadas (promesas, contenidos, modelos de negocio) | `limites.lineas_rojas` no vacía | QA del brief (check 3), nivel máximo lanzable, candidato amarillo | dueño aprueba o recorta la propuesta + `engine.propuestas sellar` |
| `metodos_pago` | Métodos de pago y régimen fiscal **por mercado** | `ofertas/<id>/mercado.json`: `fiscal.exposicion_aceptada` firmada y `metodos_pago` decididos | D5 (checkout), D7, X1 (`X32_FISCAL`) | dueño + contador (lo fiscal; **sin abogado**) |

Estados: `abierta` (bloquea ahora) · `diferida` (decidida para después; bloquea al llegar a la etapa) · `resuelta` · `no_verificable` (necesita `--oferta`). Ampliable: topología del motor (Railway o local), canal de alertas, revisor nativo por idioma, fan page, `ratio_disputas_pausa` (spec `"0.006"` frente a nota 25 `"0.005"`); cada una con su archivo y clave cuando exista dónde leerla.

## 2. Contrato para el panel (`--json`)
`{generado_en, abiertas, total, items:[{id, titulo, estado, evidencia, bloquea[], como_se_cierra, quien, comando, referencia}]}`. Todo texto es dato derivado de archivos del propio proyecto; el panel lo escapa igual. **PEDIDO al panel (no se edita `dashboard/`; `o0-orquestador-portafolio/references/dependencias.md` §F.3):** exponerlo como `GET /bloqueos` y/o como acción de lista blanca de **lectura** `bloqueos` en `dashboard/acciones.yaml`, y mostrarlo en el Resumen como banda de bloqueos visibles (cada uno con «bloquea: …» y el comando). Cuando exista `empresa/decisiones_pendientes.yaml` (CT-3, LT-29) el panel lo lee de ahí; hasta entonces esta ayuda deriva el estado de `limites.yaml` y `mercado.json`. El panel **no resuelve** ninguno: la resolución es siempre una acción del dueño en su terminal (`engine.propuestas sellar`, `orq firmar`).

## 3. Cómo queda registrada la resolución
- `limites`, `primer_mercado`, `cuenta_meta`, `lineas_rojas`: el **sello firmado** de `limites.yaml` (hash + Ed25519) es el registro; `LIMITES_HASH_ANCLA` fuera del volumen.
- `metodos_pago`: `mercado.fiscal.exposicion_aceptada.firmada_por` (firma del dueño sobre `{oferta_id, paises, aprobador, fecha}`).
- Toda decisión además puede asentarse en `empresa/decisiones_dueno.jsonl` (donde se firman propuestas); su esquema no existe `[PENDIENTE: CT-4]`.

## 4. Cómo se usa en el recorrido
`/o0-lanzar-oferta` corre el script **antes de cualquier otra cosa** y repite los bloqueos abiertos en cada informe. Un brief nunca se declara «aprobable» mientras `limites`, `primer_mercado` o `cuenta_meta` estén abiertos; la skill lo dice con la clave exacta y no «completa» el límite.
