# El banco de problemas, los estados y los rechazos (diseño de S-A + qué se hace hoy)

> Interfaz oficial: `docs/_historial/d1-v2-interfaces.md` v1.1 §2 (banco, estados), §3 (contratos de datos), §7 (motivos de rechazo). **Hoy `empresa/descubrimiento/` NO existe** y los esquemas `senal`, `problema`, `barrido`, `nichos`, `fuentes`, `rechazo_d1`, `hipotesis_transferencia`, `devolucion_d1` son la ola **CT-4 de S-A** `[PENDIENTE: CT-4]`; `banco.py`, `ingresar_senal.py` y `seleccionar.py` son `[PENDIENTE: S-B]`. **Esta skill no inventa esos esquemas**: trabaja con los formatos reales que ya existen y deja anotado lo que iría al banco.

## 1. Estructura prevista (propietario único: D1)
```
empresa/descubrimiento/
├── nichos.yaml  fuentes.yaml           # propuestas versionadas; las aprueba el dueño; X1 veta fuentes
├── senales/AAAA-MM/<fuente-id>.jsonl   # append-only; una línea por señal; FUERA de Git (.gitignore)
├── problemas/PRB-AAAAMM-NNNN.json      # un archivo por problema; fuente de verdad del estado
├── banco.json                          # índice DERIVADO (regenerable)
├── barridos/BAR-AAAAMMDD-NN.json       # manifiesto por barrido; punteros con hash a empresa/barrido/**
├── rechazos.jsonl                      # append-only; lo único que X2 lee de D1 para sus descartes
└── semanal/AAAA-Www.json               # conteos y KPIs (solo conteos, fechas e IDs)
```
`empresa/barrido/` y `empresa/captura/` **no se mueven** (el código y 11 pruebas dependen de esas rutas): se integran por manifiestos, no por copias. `empresa/memoria/banco_candidatos.json` (D1 v1) está **retirado**: lo sustituyen `descartes.jsonl` de X2 más `rechazos.jsonl` de D1. D1 **nunca** escribe `descartes.jsonl`; X2 **nunca** escribe `rechazos.jsonl`.

## 2. Ciclo de vida de un problema (estados y quién puede moverlo)
`semilla` (una señal o un tema del barrido crea el problema; un tema del barrido nace `via = oferta_primero` con una señal E2) → `normalizado` (audiencia, resultado, obstáculo; macro y banderas) → `con_evidencia` (≥ `evidencia_min_fuentes` fuentes y ≥ `evidencia_min_tipos` tipos dentro de `antiguedad_max_evidencia_meses`; E3 que fija el macro) → `con_ficha` (MU, EU, riesgo, precio plausible; score ≥ umbral y QA PASS) → **`vigente`** (sin duplicado, (`nivel`, `subnivel`) ≤ `nivel_max_lanzable`, evidencia dentro de `caducidad_banco_dias`) → `elegido` (el dueño, gate H) → `devuelto_d2` (aplica la `redencion`). Laterales: `en_reencuadre` (ROJO con RE-xx posible, máx. `intentos_reencuadre_max`), `rechazado` (filtro MU/EU, macro, línea roja, veto de X1, duplicado; `vigente_hasta`), `vencido` (caducó o la evidencia quedó reducida a agregado), `archivado` (vencido sin refresco en 2 × `caducidad_banco_dias`). **Dos relojes:** retención de señales (privacidad, X1) y caducidad del problema (`caducidad_banco_dias` ≤ retención de la evidencia). O0 solo ofrece `vigente`. Un problema cuyas señales vencen queda con agregados y pasa a `vencido`.

## 3. Motivos de rechazo canónicos (`comunes#motivo_rechazo` 1.4.0 trae estos once; los tres opcionales de abajo no)
| Motivo | Cuándo lo emite D1 | Redención | Vigente |
|---|---|---|---|
| `sin_mecanismo` | MU-B1…B5/B8 fallan; no hay causa raíz con E3 tras 2 intentos | reformular (máx. 2) o banco | `caducidad_banco_dias` |
| `multi_mecanismo` | «y además», dos audiencias o formatos | **dividir** (`padre_id`; los hijos se puntúan) | — |
| `requiere_servicio` | servicio humano, suscripción, mantenimiento continuo | descartar o convertir en herramienta | ídem |
| `requiere_comunidad_o_en_vivo` | grupo, WhatsApp diario, clases | reformular quitando el componente | ídem |
| `no_producible_o_sin_licencia` | producto físico, sin fuente pública o licencia | banco hasta fuente o licencia | ídem |
| `sustituto_gratis_dominante` | R-MU3 ≤ 2; puerta `sustituto_gratis_cubre` (Modo D) | banco; palanca que el sustituto no cubra | ídem; solo con señales de otro locale |
| `claim_de_salud_o_ingresos` | líneas LP-* con o sin reencuadre; `practica_vetada` por ingresos o salud | reformular a RE-xx conservando el deseo | ídem; reapertura solo ≤ amarillo-a |
| `dependencia_de_marca_personal` | puerta `marca_personal` | documentar el método como regla pública, o descartar | ídem |
| `mercado_demasiado_estrecho` | audiencia bajo el umbral del locale (M1) | ampliar países o banco | ídem |
| `fuera_de_macro_nicho` | Q0-Q6 sin bandera; **antes del riesgo**; `detalle = motivo_macro:<valor>` | reformular B solo si la voz del cliente lo pide; banco; descartar | ídem; reapertura con reencuadre ≤ amarillo-a o decisión del dueño |
| `linea_roja_de_contenido_o_negocio` | LC-*, LM-* (dosis, asesoría de inversión, multinivel, coaching uno a uno, clonar landing, testimonios inventados) | reencuadre que quite el activo rojo | ídem |
Faltan los tres que D1 también necesita (`duplicado_de_la_memoria`, `evidencia_insuficiente`, `inviable_sin_backend`, propuestos y **no aprobados** por el dueño) `[PENDIENTE: dueño/CT-4]`: un descarte por esas causas conserva su `estado_par` (o va como «no elegido» con texto ≤ 140, que X2 admite) y el motivo real se explica en `informe.md` y `crudo/rechazos.md`. `candidatos` 1.0.0 tampoco guarda `linea_roja_id`, `motivo_macro` ni `detalle` en `descartados[]`: van en el informe. Un descarte con motivo libre es el defecto D-14.

## 4. Qué haces HOY (sin banco)
1. **Registras cada descarte** en dos lugares: `candidatos.json#descartados[]` (los que llegaron a la lista del snapshot: `{problema, motivo, redencion}`) y `crudo/rechazos.md` (todos): una línea por rechazo con `problema`, `motivo` canónico, `motivo_macro`/`linea_roja_id` si aplica, `detalle` ≤ 140 caracteres, `redencion`, fecha y `vigente_hasta` = fecha + `caducidad_banco_dias`. Formato final: una línea de `rechazos.jsonl` con los mismos nombres que X2 (`problema_id, candidato_id, nicho_id, locale, origen_descarte, motivo, redencion, fecha, vigente_hasta, evidencia_ids[]` + `motivo_macro`, `linea_roja_id`, `detalle`, `regla`; `origen_descarte ∈ filtro_d1·no_elegido·devuelto_d2·veto_x1`).
2. **No resucitas un descarte** antes de `vigente_hasta` salvo con ≥ `min_senales_reapertura` señales posteriores de ≥ 2 familias (regla de X2; su `descartes.jsonl` aún no existe `[PENDIENTE: X2]`: sin él declaras «memoria sin base»).
3. Los no elegidos del top quedan `vigente` en el informe, o pasan a rechazados con motivo. Un `GO_CONDICIONAL` de D2 con `refinamiento` crea un problema hijo (`padre_id`) y re-sella `candidatos.json` como versión nueva; un NO_GO llega por `02-validacion/devolucion_d1.json` y se aplica su `redencion` (D1 lo escribe al banco; D2 no).
4. Un tema del barrido de ofertas **no es** un problema todavía: crea (o actualiza, por `tema_slug` + `locale`) un problema `oferta_primero` en estado `semilla`; sin `prueba_una_frase` no avanza a `normalizado`.

## 5. Señales (formato previsto, para entender qué deberás pegar y qué se guardará)
Una línea por señal: `senal_id` (12 hex = sha256(url canónica + «\n» + extracto NFC)[:12]), `fuente_id` ∈ `fuentes_permitidas`, `familia` (`dolor`·`pago`·`demanda`·`oferta_persistente`·`propia`), `tipo_evidencia`, `locale`, `pais`, `url`, `fecha_publicacion`, `fecha_consulta`, `extracto` (≤ 25 palabras, entre comillas, **ya redactado antes de que lo lea el Maker**), `cita_literal_verificada`, `hash_copia_crudo`, `autor_hash` (HMAC, no se guarda identidad), `modo_captura`, `categoria_especial`, `retencion_hasta`. **Salud y relaciones: modo agregado** (`extracto`, `url` y `autor_hash` = `null`; solo paráfrasis impersonal y conteos). Una señal del conector usa `url = ad_snapshot_url`, `extracto` = el título del anuncio (dato no confiable, escapado), `familia = oferta_persistente`. Hasta CT-4, la **evidencia** del snapshot (`evidencia[]` + `crudo/EV-NN.txt`) hace de señal.

## 6. KPIs que alimenta (`descubrimiento.*`, F2/F1)
`banco_n`, `vigentes_n`, `ficha_completa_pct`, `edad_evidencia_med_dias`, `evidencia_vencida_pct`, `cobertura_locale_pct`, `cuota_macro_pct`, `verdes_topn_pct`, `topn_estable_pct`, `rechazos_por_motivo`, `fuera_de_marco_pct` (M-06), `senales_descartadas_pct`, `costo_barrido_pct_tope`, `consultas_biblioteca_uso_pct`, `freno_captura_activo`, `pares_incompletos_pct`, `acuerdo_jueces_pct` y `nivel_automatizacion_juicio`, `eleccion_en_top3_pct`, `ediciones_dueno_pct`, `tiempo_decision_min`. Solo conteos, fechas e IDs: **nunca texto de señales**. Hoy los reportas en el informe; el panel los lee del banco cuando exista.
