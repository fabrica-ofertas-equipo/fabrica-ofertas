# Informe de poscompra — {{oferta_id}} · {{locale}} · semana {{AAAASww}}

> v0.1 sin pulir. Lo cifrado lo calcula el **código** (`postcompra.metricas`, `datos/`); el Maker no recalcula, no redondea a su favor y no interpreta una muestra insuficiente. Toda cifra lleva **n, ventana y cohorte**. Sin dato: «sin dato» y qué lo produciría. Una cohorte es madura cuando pasó la garantía + 7 días. Los datos de ejemplo se marcan `sintetico` y no se mezclan con los reales.

**Periodo:** AAAA-MM-DD a AAAA-MM-DD (UTC) · **Quién lo redactó:** `d10-maker` v0.1.0 · **Fuentes:** `entregas.jsonl`, `reembolsos.jsonl`, `senal_pausa.json`, `soporte.jsonl`, `resenas_informe.json` (hashes) · **Estado del cableado:** [qué parte corre de verdad y qué es simulado; `[NO PROBADO]` donde corresponda]

## 1. Resumen para el dueño (5 líneas como máximo)
- Lo que salió bien / lo que hay que decidir hoy / lo que esperaba su clic / lo escalado / el riesgo mayor.
- Decisiones pendientes con el nombre del parámetro (`null` = fail-closed): …

## 2. Pagos y entrega (por línea, método y país)
| Medida | Valor | n | Ventana | Meta / umbral | Estado |
|---|---|---|---|---|---|
| Pagos | | | | | |
| `entrega_ok` (entregados ≤ `entrega_max_min` / pagados) | | | | ≥ 99 % | |
| `t_entrega_p95` | | | | `entrega_alerta_min` | |
| Pagos sin entrega, reintentos, `fallido` | | | | 0 | |
| `descarga_24h` | | | | 85 % | |
| `activacion_72h` (sin clics de escáner) | | | | 40 % | |

## 3. Oferta tras el pago (cuando exista contrato)
| Línea | Tomada / ofrecida | Por método | Reembolsada | Disputada | Observación |
|---|---|---|---|---|---|
| bump | | | | | |
| upsell | planificado | | | | |
| postpago | planificado | | | | |
Ticket medio real: … frente al modelado por D3 (`tasa_bump_bp`, `tasa_upsell_bp`): …

## 4. Reembolsos y disputas (cohorte madura)
| Medida | Valor | n | Ventana | Umbral (`salud_operativa.*`, `limites.ratio_disputas_pausa`) | Estado |
|---|---|---|---|---|---|
| `r` (reembolsos / pagos) | | | | alerta / pausa | |
| `d` (disputas + EFW / pagos, provisional hasta ≈ 120 d) | | | | alerta / pausa | |
| Por `adid` / ángulo (se pasa a D8 y D6) | | | | | |
Motivos de reembolso (conteo por categoría, sin datos personales): …
Peticiones dentro de garantía **sin respuesta o sin ejecutar**: … (debe ser 0; si no, incidente).
`senal_pausa.json`: emitida sí/no, nivel, motivo, `consumida_por`.

## 5. Soporte y bandeja
| Medida | Valor | n | Meta |
|---|---|---|---|
| Mensajes por categoría (C1-C10) | | | |
| `tickets_por_100` | | | ≤ 8 |
| Primera respuesta p90 (`tpr_p90`) | | | ≤ `soporte_primera_respuesta_h` |
| Auto-enviados (macros selladas) / por humano / escalados | | | |
| Escalados a C7 (crisis, seguridad, legal) y plazo cumplido (≤ 24 h) | | | |
| Mensajes con orden incrustada detectados (dato, no obedecidos) | | | |

## 6. Reseñas reales
| Medida | Valor |
|---|---|
| Pedidas / respondidas (tasa) | |
| Con permiso de valoración / de texto / de nombre | |
| Media de las que cuentan (n) y **media de todas las verificadas** | |
| `brecha_de_autorizacion_decimas` (≥ 3 → avisar) | |
| Distribución de estrellas: todas / que cuentan / publicables | |
| Retiradas · descartadas por motivo · a revisión humana | |
| `prueba_social_real.json` vigente: n, fecha, validación | |
Nota de honestidad: la media pública no es la satisfacción global (los reembolsados y disputados no reciben la petición): `r` de la misma cohorte = …

## 7. Vigía (cobros y entrega)
| Id | Estado | Detalle |
|---|---|---|
| V1 pago sin entrega · V2 avisos de Stripe · V3 Stripe cobra y paga · V4 disputas · V5 reembolsos · V6 correo (rebotes, quejas) · V7 pagos asíncronos · V8 descriptor y política · V9 cuenta de Meta (solo lectura) | | |

## 8. Señales de vuelta
- **D3 (oferta):** … · **D4 (producto):** … · **D5 (landing):** … · **D6/D8 (por `adid`):** … · **D1/X2 (`senales_propias.jsonl`):** … · **M1 (métodos, países):** …

## 9. Pedidos abiertos a otras sesiones (de `PEDIDOS.md`) y decisiones del dueño
| Id | Qué | A quién | Bloquea |
|---|---|---|---|

## 10. Límites de este informe
Qué no se pudo medir y por qué (muestra insuficiente, cableado ausente, datos simulados): …
