# Mapa de claves (la skill cita claves, nunca números)

Todos los valores de `parametros.yaml` son `[HIPÓTESIS]` (`valor, unidad, hipotesis, fuente, ultima_calibracion`). `limites.yaml` lo fija solo el dueño (`engine.propuestas sellar --live`, con `FABRICA_ENTORNO=produccion`); con una clave necesaria en `null` o una lista exigida vacía, **nada gasta ni activa** (código 5). Los importes de `limites` son enteros en la unidad menor de `limites.moneda_limites`; los `*_pct` son unidades de porcentaje (20 = 20 %); `ratio_disputas_pausa` es fracción. Verificado contra `empresa/*.yaml` el 2026-11-06.

## `empresa/limites.yaml` — claves que usa O0

| Clave | Para qué la usa el brief / la cartera |
|---|---|
| `moneda_limites` | moneda de **todo** el presupuesto del brief; otra moneda no crea nada |
| `gasto_total_test_por_oferta` · `gasto_diario_por_oferta` · `factor_techo_teorico_diario` | techos de `presupuesto.test_total_max` y `test_diario_max` (× factor ≤ diario) |
| `perdida_max_test_por_oferta` · `perdida_neta_acumulada_max` · `stop_loss_escala` | la primera es **diferida por el dueño** (se fija con `engine.propuestas proponer`, que exige la `economia.json` de D3, y `sellar`); las otras frenan cartera y escala |
| `ofertas_en_test_simultaneas_max` · `capital_en_riesgo_total` · `limite_gasto_cuenta_meta` | cartera y último candado |
| `paises_permitidos` · `locales_permitidos` · `cuentas_permitidas` | mercado y cuenta del brief (listas vacías = no permitido) |
| `macro_nichos_permitidos` (fijo: salud, relaciones, dinero) · `subnichos_prohibidos` (vacío por diseño) · `lineas_rojas[]` (`promesa`, `contenido`, `modelo_negocio`) | encuadre |
| `acciones_gate_humano` | gate efectivo (mínimas: `activar_campana`, `reactivar_tras_pausa`, `subir_presupuesto_sobre_tope`, `cambiar_limites`, `cambiar_entidad_stripe`, `lanzamiento_pais_idioma_nuevo`) |
| `politica_divulgacion_ia` · `politica_reembolso_dias` · `ventana_veto_min` | defaults del brief |
| `costo_max_producto` · `costo_max_validacion` · `max_budget_por_corrida_agente` | default de `ia_max`; tope por corrida de agente |
| `max_barridos_por_semana` · `max_busquedas_por_barrido` · `max_costo_por_barrido` · `fuentes_permitidas` | radar de D1 |
| `horas_min_entre_aumentos` · `aumento_presupuesto_max_pct_por_paso` | subir presupuesto (D8/D9, no O0) |
| `sello` (hash + firma Ed25519) · `LIMITES_HASH_ANCLA` (variable de entorno) | sin sello válido no se opera |

**Claves de nichos** (`[HIPÓTESIS]` de la nota 25 §10.1; ya en `limites` 1.3.0, `null` = SOLO VERDE): `hojas_pausadas`, `nivel_max_lanzable`, `cuota_gasto_amarillo_max_pct`, `cuota_gasto_amarillo_b_max_pct`, `envios_amarillo_a_semana`, `envios_amarillo_b_mes`, `edad_minima_audiencia`. **`boton_max_lanzamientos_dia`** (tope diario de encolados del botón) va en `limites`, no en `parametros`, y su valor es del dueño; aún no está en el esquema (CT-3, LT-13). La fracción mínima de verdes del top-N del botón es `parametros.descubrimiento.cuota_verde_topn_min_pct` (aún sin crear: LT-05). `ratio_disputas_pausa`: el spec dice `"0.006"`, la nota 25 §9 sugiere `"0.005"`: **decide el dueño**.

## `empresa/parametros.yaml` — grupos que usa O0

| Clave | Qué gobierna |
|---|---|
| `orquestador.max_rondas_qa` (fijo) · `reintentos_tecnicos` · `espera_reintento_min` · `timeout_etapa_min.<D1…D7,QA>` | rondas Maker↔QA, reintentos (jamás reintentar un gasto sin verificarlo) y timeouts |
| `orquestador.umbral_pass_o0` · `umbral_item_min_o0` | PASS del QA de O0 |
| `orquestador.p_viable_descartar` · `p_viable_escalar` · `exploracion_pct` · `paralelas_max_por_nivel` | cartera (los usa `portafolio.py`, no tú) |
| `orquestador.gasto_alarma_pct` · `freno_pct` · `frescura_datos_max_h` · `pausa_global_max_min` · `propuesta_vence_h` | alarmas, frescura, kill switch, vencimiento de la propuesta |
| `mercados.mercados_test_paralelos_max` · `primer_lanzamiento_requiere_h` · `prior_de_mercado` (= ninguno) | mercados en paralelo; ningún prior |
| `economia.*` (p. ej. `presupuesto_test_min` sale de `economia.json` de **ese** mercado, comisiones e IVA incluidos) | piso para decidir; con `test_total_max` menor la oferta solo puede morir |
| `veredicto.dias_max` · `madurez_dias_extra` | ventana y madurez del test |
| `salud_operativa.*` · `compliance.*` · `watchdog.latido_max_min` · `testeo.k_corte` | frenos y descensos (`barreras-y-frenos.md`) |
| `finanzas.*` (reservas por nivel: fondo de reembolsos y retención de Stripe como horizonte de caja) | F1; O0 solo las cita |

Si una clave citada no existe en el archivo, **no inventes su valor**: «clave ausente: PEDIDO» y `ParametroFaltante` (código 5) para quien la necesite.
