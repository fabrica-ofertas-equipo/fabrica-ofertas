# Salud de cuentas: regla de congelamiento, casos tabulares y contingencia

**La salud diaria es de CÓDIGO** (spec 14 §4 paso 8). Existe `compliance/salud.py` (`python -m compliance.salud evaluar` decide; `pausa` arma, en dry-run por defecto, la propuesta de `senal_pausa.json` que lee `engine.d8`; envoltorio `scripts/x1_salud.py`): es la traducción a parámetros reales de la regla de esta página, con `scripts/regla_salud.py` y las 21 series como oráculo (paridad probada en `tests/compliance/test_salud.py`; `dependencias.md` D-04). Sin `limites.ratio_disputas_pausa` (hoy `null`, del dueño) sale 5 y no decide. La señal de entrada sale de `meta.monitor` (`07-campana/traspaso.json`, `rechazos_7d`), `postcompra.metricas`, `dashboard.alertas`, y la pausa la ejecutan `meta.pausar` / `infra.kill`. La skill **redacta la regla, los casos y los informes**; **no pausa, no reanuda, no apela, no crea ni edita nada en Meta o Stripe**. **Reanudar es siempre humano.** Meta se lee **solo lectura y solo en la sesión interactiva del dueño** (`ads_get_ad_accounts`, `ads_get_ad_entities`, `ads_account_get_activity_logs`, `ads_get_dataset_quality`, `ads_library_search`, `ads_get_ad_preview(_screenshot)`); `ads_get_errors` **no** cubre rechazos ni restricciones; la **calidad de cuenta no tiene herramienta de lectura** (declaración del dueño, `compliance.declaracion_calidad_cuenta_max_dias`).

## 1. Entradas del estado de salud

| Campo | Origen | Nota |
|---|---|---|
| `account_status` | `ads_get_ad_accounts` | `ACTIVE` o cualquier otro (deshabilitada, restringida…) [VERIFICAR enumeración] |
| `calidad_cuenta_meta` + edad | declaración del dueño | `Saludable` / `Necesita atención` / `Restringida` (UI en español) [VERIFICAR] |
| `rechazos[]` (`hace_dias`, `tipo` ∈ producto·contenido·pieza, `revertido`) | `meta.monitor`, actividad de la cuenta | un rechazo **revertido en revisión no cuenta**; los anuncios `DISAPPROVED` **nunca se reenvían con el mismo hash** |
| `pagos_30d`, `disputas_30d` (disputas + EFW), `reembolsos_n`, `reembolsos_pct` (cohortes maduras) | F1 / `postcompra.metricas` | las disputas llegan hasta ~120 días tarde: informar **también la cohorte madura** |
| `stripe_aviso` | del dueño (UI de Stripe) | `informacion` · `retraso_pago` · `reserva` · `monitoreo_vamp` · `suspension` · `cierre` |
| `edad_salud_h` | del propio `salud_actual.json` | datos viejos = no se lanza (L1-12) |

## 2. Regla (pseudocódigo; oráculo ejecutable: `scripts/regla_salud.py`)

```
si falta cualquier parámetro       -> NO decidir; escalar (nada gasta sin dato)
accion = seguir
# 1. cuenta y procesador (lo más grave)
si account_status != ACTIVE                     -> PAUSA (cuenta)
si calidad == Restringida                       -> PAUSA (cuenta)
si calidad != estado_meta_requerido_para_lanzar -> congelar lanzamientos y auditar (alcance cuenta)   [SUPUESTO]
si stripe_aviso en {suspension, cierre, monitoreo_vamp}  -> PAUSA (cuenta)
si stripe_aviso en {retraso_pago, reserva}               -> pausar_oferta
# 2. rechazos vivos = no revertidos y dentro de rechazos_ventana_dias
si algún vivo es de producto o contenido        -> congelar_hoja
si algún vivo es de pieza                       -> congelar_angulo
si cuenta(vivos) >= rechazos_congelar           -> congelar_hoja (alcance cuenta) + bajar D5-D9 a N1
# 3. disputas + EFW
si pagos >= disputas_muestra_min_pagos y disputas/pagos >= limites.ratio_disputas_pausa
                                                 -> pausar_oferta + proponer pausa del macro (gate H)
si disputas >= disputas_casos_pausa              -> pausar_oferta
si no, si disputas >= disputas_casos_alerta o (pagos >= muestra_min y % >= disputas_alerta_pct) -> alerta
# 4. reembolsos (solo con reembolsos_n >= reembolsos_n_min)
si % >= reembolsos_pausa_pct -> pausar_oferta ; si % >= reembolsos_alerta_pct -> alerta
# 5. frescura
si edad_salud_h > salud_max_antiguedad_h o declaración de calidad vencida -> lanzamientos bloqueados + alerta
accion final = la MÁS GRAVE de todas (seguir < congelar_angulo < congelar_hoja < pausar_oferta < PAUSA)
```

**Escalón para amarillos** (nota 25 §9, aún sin parámetro): las ofertas amarillo-a usan la columna anterior de alerta/pausa; amarillo-b además pausa el ángulo al primer caso (`salud_operativa.amarillo_escalon_menos`: **[PENDIENTE: MINOR]**). **Reservas** (F1): fondo de reembolsos y colchón rodante son de F1, X1 solo los menciona en el dossier.

## 3. Casos tabulares (series simuladas: `evals/salud/series.json`, 21 series, todas coinciden con `regla_salud.py`)

Los números de la serie son **de prueba** (copia de los valores iniciales `[HIPÓTESIS]` de 2026-11-06; `ratio_disputas_pausa` en 0.005 solo para probar, el dueño no lo fijó). Si el dueño cambia un parámetro, se **recalcula el esperado**, no se edita la regla.

| Serie | Situación | Acción esperada |
|---|---|---|
| SAL-01 | todo verde | `seguir` |
| SAL-02 / 03 | un rechazo de pieza sin revertir / revertido | `congelar_angulo` / `seguir` |
| SAL-04 | un rechazo de producto | `congelar_hoja` |
| **SAL-05** | **tres rechazos de pieza en cinco días (sembrado X1-S12, eval E08)** | `congelar_hoja` (cuenta) + bajar D5-D9 a N1; un dictamen «continuar» es el defecto |
| SAL-06 | dos rechazos, uno fuera de la ventana | `congelar_angulo` |
| SAL-07 / 08 | 2 casos de disputa / 3 casos sobre 1.000 pagos | alerta / `pausar_oferta` |
| SAL-09 / 10 | 1 caso sobre 40 pagos (poca muestra) / 2 casos sobre 300 pagos (≥ `ratio_disputas_pausa`) | `seguir` / `pausar_oferta` + pausa del macro (H) |
| SAL-11…13 | reembolsos en alerta / pausa / sin muestra | alerta / `pausar_oferta` / `seguir` |
| SAL-14…16 | «Necesita atención» / «Restringida» / cuenta no ACTIVE | congelar lanzamientos y auditar / `PAUSA` / `PAUSA` |
| SAL-17 / 18 | Stripe suspende o cierra / retraso de pago | `PAUSA` / `pausar_oferta` |
| SAL-19 / 20 | salud vieja / declaración de calidad vencida | lanzamientos bloqueados |
| SAL-21 | rechazo de pieza + 3 disputas | `pausar_oferta` (gana la más grave) |

## 4. Contingencia (`contingencia.md`; lo ejecuta una persona)

- **Anuncio rechazado:** **no reintentar sin cambio real**; apelar solo ante error evidente (una apelación por activo salvo decisión del dueño); registrar en `incidentes.jsonl` y como **caso nuevo de la suite** (por claim).
- **«Necesita atención»:** congelar lanzamientos y **auditar 14 días**.
- **Restringida:** `PAUSA` y apelación del administrador (~48 h, cupo limitado) [VERIFICAR].
- **Stripe retiene o cierra:** congelar campañas, reunir evidencia de entrega y reembolsos y apelar por la UI de Stripe (pausa de pagos hasta 120 días según la nota 25 [VERIFICAR]).
- **Cuenta de Meta deshabilitada previa:** decide el dueño (apelar o abandonar). **Prohibido** rotar cuentas o clonar embudos (LM-08).
- **Respaldo legítimo:** activos no compartidos con otros negocios del dueño; saldo prepago mínimo (si choca con el preflight M-03, manda M-03); carril B de cobro solo para verdes; simulacro trimestral. La decisión 15 del dueño descartó, **por ahora**, el segundo administrador y la seguridad personal: es **riesgo residual aceptado** (si se restringe su perfil personal y es el único administrador, puede caer la cuenta de anuncios); X1 lo menciona en el dossier, **no lo exige como tarea ni gate**.

## 5. Salidas de salud (formato `[SUPUESTO]`: no hay esquema todavía)

`empresa/compliance/salud_actual.json` (estado vigente: `account_status`, ratios, `nivel_por_hoja`, `deriva[]`, `accion`, `generado_en`), `salud.jsonl` (una línea por corrida), `incidentes.jsonl`, `apelaciones.jsonl`, `bitacora.jsonl` (encadenada por hash; ancla semanal al dueño). El informe semanal al dueño (N4) y los pedidos a F2/O0 van como resumen en español de negocio: qué cambió, qué acción propone el código, qué decide el humano.
