# Disputas, reembolsos extremos, vigía de cobros y señales de vuelta

> v0.1 sin pulir. Origen: `departamentos/11` §4 (pasos 11-15), §7, Anexo B y C; `know-how.md` (vigía de pagos; «disputas en Stripe las maneja el cerebro»); `mapeo.md` §7 paso 6 («disputas en 1 clic: el sistema prepara, el dueño envía»); `postcompra/{evidencia,metricas,reembolsar}.py`. Reglas de proceso, no dictámenes legales (decisión 14).

## 1. Disputas: el sistema prepara, el dueño envía

1. **Qué hace el código:** `charge.dispute.created` abre el caso; `postcompra.reembolsar` **rechaza** cualquier reembolso con `disputa_abierta` (no se devuelve dinero sobre un cargo en disputa: Stripe lo cobraría dos veces); `postcompra.evidencia` arma `resumen.json` + `manifiesto.json` (hashes) **sin datos personales**; la IP y el agente de usuario que Stripe pide viven en una tabla restringida y viajan solo hacia Stripe (contradicción registrada en `coordinacion-sesiones.md`, «Pedidos de S-A (D10)»). La alerta sale por **dos canales en ≤ 1 h**.
2. **Qué hace el Maker:** redacta la **narrativa** de la respuesta a partir de esos hechos (§1.2) y recomienda contestar o no. **No envía**: la clave de escritura de Stripe está en `deny` y `accion:disputa` es H en todos los niveles. Lo envía el dueño antes de `due_by` (tarjeta `[VERIFICAR]` plazo vigente; BLIK 12 días; MB WAY 7; Satispay 15).
3. **Contestar o no:** por defecto solo si el importe ≥ `postcompra.disputa_contestar_min` (20 USD `[HIPÓTESIS]`) o hay patrón de fraude o descarga confirmada. **El ratio pesa más que el monto**: un contracargo cuenta aunque se gane, y pausar el gasto no baja el contador (se madura ≈ 120 días).
4. **EFW (alerta temprana de fraude):** reembolso automático si cabe en `reembolso_auto_max` y el tope diario; si no, cola humana. Visa puede contarla igual `[VERIFICAR]`.
5. **Retención de evidencia:** `postcompra.evidencia_retencion_dias` (180; BLIK 400 por su ventana de 13 meses) `[RIESGO RESIDUAL: privacidad]`.

### 1.1 Si el comprador sí pidió el reembolso y no se le dio
Si en `soporte.jsonl` hay una petición dentro de garantía **sin respuesta o sin ejecutar**, **no se contesta la disputa**: se reconoce el error, se escala al dueño y se reembolsa por la vía manual (`postcompra.reembolso_manual`, honrado en `reembolso_ejecucion_h`); el incidente va al informe. Contestar con la garantía publicada cuando no se cumplió es el peor resultado (pérdida + ratio + riesgo de cuenta).

### 1.2 Esqueleto de la narrativa (en inglés, es lo que lee el banco; solo hechos del paquete)
1. **Compra:** fecha, importe, método, descriptor, líneas (principal, bump), `landing_version`. 2. **Lo que se prometió:** el texto visible de la garantía y el procedimiento, con la URL de `/legal/reembolsos` y la versión vigente el día de la compra. 3. **Cómo se entregó:** `entrega_id`, estado, fecha de envío, descargas con marcas de tiempo, hash del producto (`producto_sha256`). 4. **Cómo se podía pedir el reembolso:** E0, `/gracias`, soporte; si el comprador **nunca** lo pidió, es la prueba más fuerte. 5. **Historial con soporte:** solo si existe, resumido. 6. **Conclusión:** una frase. Todo dato que falte se escribe `[HECHO NO DISPONIBLE]`; el Maker no completa, no estima y no cita al comprador más allá de lo que figura.

## 2. Reembolsos extremos y abuso

- **Abuso:** `postcompra.reembolso_abuso_flag` (≥ 2 reembolsos previos del mismo correo o tarjeta) lleva el caso a revisión **humana**; nunca se bloquea ni se rechaza automáticamente.
- **Incidente de seguridad** (mensaje que atribuye daño, crisis, abuso o pérdida de dinero al producto): el Maker deriva a una persona (C7, ≤ 24 h); reembolso inmediato sin condiciones por la vía manual; el código emite `senal_pausa` con `motivo = incidente_seguridad` y `accion_solicitada = alertar` para congelar la escala (el esquema 1.2.0 ya lo admite; `postcompra.metricas` aún emite 1.1.0: P-05). El Maker no discute causalidad ni da consejo. Retiro de la oferta con 3 reportes en 30 días o una lesión grave (parámetros pedidos `postcompra.respuesta_incidente_horas` y `retiro_reportes_30d`).
- **Reembolso fuera de plazo:** siempre humano; D10 nunca lo rechaza por su cuenta.

## 3. Vigía de cobros y entrega

**Qué es:** el dueño pide un vigía de pagos «que ninguna cuenta se frene por un pago» (`know-how.md`: «si una cuenta publicitaria deja de gastar por un pago, avisa al celular»; centro de mando: «0 pagos frenados sin aviso»). Tiene **dos mitades**: la cuenta publicitaria de Meta (M-02 y M-03 del preflight: cuenta activa, tope y forma de pago; dueños D0, infra y D7) y el **cobro con Stripe y la entrega**, que es la parte de D10. D10 vigila la segunda y **lee** la primera; no la arregla.

| Id | Qué vigila | Fuente | Umbral | Quién actúa |
|---|---|---|---|---|
| V1 | pago sin entrega | `fact_pedido.pagado_en` frente a `entregas.jsonl` | `entrega_alerta_min` (10 min); reintentos a 1, 5 y 30 min (`entrega_reintentos`) | código reintenta; alerta; dueño `[PENDIENTE P-06]` |
| V2 | los avisos de Stripe llegan | preflight S-03 y S-04 (eventos recibidos frente a los de Stripe en 24 h) | huecos > 0 | S-B / dueño |
| V3 | Stripe puede cobrar y pagar | preflight S-02 | requisitos pendientes o vencidos | dueño |
| V4 | disputas bajo control | `postcompra.metricas` (S-07) → `senal_pausa.json` | `salud_operativa.disputas_*`, `limites.ratio_disputas_pausa` (hoy `null`) | D8 consume la señal; el dueño decide |
| V5 | reembolsos fuera de umbral | idem | `reembolsos_alerta_pct`, `reembolsos_pausa_pct`, `reembolsos_n_min` | D8 / dueño |
| V6 | correo: rebotes y quejas | proveedor de correo `[PENDIENTE: B3-15]` | `email_rebote_max_pct` 2, `email_queja_max_pct` 0,1 | dueño |
| V7 | pagos asíncronos | `async_payment_failed`, `unpaid` | cualquiera sin entrega | código |
| V8 | Stripe muestra bien el negocio | preflight S-08 (descriptor, política y contacto) | verde | dueño |
| V9 | cuenta de Meta sin frenos por pago | preflight M-02, M-03 | rojo | D0 / infra / D7 (D10 solo lo repite en el informe) |

- **Regla de D10:** el vigía **no pausa**. Emite `senal_pausa.json` por código y D8 la lee en cada ciclo (R08, `consumida_por`); la pausa dura es `limites.ratio_disputas_pausa` y la ejecuta el motor o el `watchdog`.
- **Canales:** severidad → canal, plantilla fija sin texto libre, siempre dos canales; resumen diario 08:30 por script (`mapeo.md` §9). `dashboard.alertas` (B10) aún no existe `[PENDIENTE]`; el panel de pagos (`dashboard/web/lib/pagos.js`) ya muestra S-02…S-08 y M-02/M-03 con estados vacíos honestos.
- **Con `null` en límites** (`ratio_disputas_pausa`, `reembolso_auto_max`, `reembolsos_auto_max_por_dia`), D10 no inventa un valor: lo lista como pregunta bloqueante y la señal usa el conteo absoluto de `salud_operativa` mientras la muestra sea insuficiente.

## 4. Plazos legales frente a la garantía (resumen; fuente `departamentos/11` Anexo B; `[VERIFICAR]` país por país)

| Jurisdicción | Regla | Qué hace D10 |
|---|---|---|
| UE | 14 días; en digital se pierde con consentimiento expreso, reconocimiento de la pérdida y confirmación del vendedor en soporte duradero; función de desistimiento de dos pasos (Dir. 2023/2673, desde 2026-06-19) | casilla separada (D5) + `{{bloque_renuncia}}` en E0; si la renuncia no se acredita, reembolso íntegro; garantía ≥ 14 |
| Reino Unido | CCR 2013, 14 días | igual que la UE |
| Suiza | sin derecho general de desistimiento en línea | los 14 días son **contractuales**: no llamarlos «derecho legal» |
| Australia | garantías legales que no se excluyen | prohibido «sin reembolsos tras la descarga» |
| EE. UU. | sin derecho federal; FTC Act §5 | honrar la garantía publicada |
| Polonia (oferta A) | UE; documentación al consumidor en polaco | textos en polaco; garantía 30 días ≥ 14 |

La política usa **el máximo entre la garantía y el plazo legal** de cada país del clúster (`mercado.consumo.desistimiento_dias`). La garantía no se ata nunca a un resultado.

## 5. Métricas y señales de vuelta (qué recibe cada etapa)

| A quién | Qué | Cómo |
|---|---|---|
| **D8** | `senal_pausa.json`; reembolsos y disputas por `adid` | código (`postcompra.metricas`); unión por `oferta_id` + `adid`, no por nombres |
| **D3** | toma real del bump y de la oferta tras el pago, `r` y `d` por línea, motivos de reembolso, preguntas que la oferta no responde | informe semanal |
| **D4** | quejas del producto: archivo que falta, calidad, formato, nivel | `senales_propias.jsonl` + informe |
| **D5** | confusiones («pensé que incluía…», «no sé cómo me llega») | informe + señal propia |
| **D6** | `r` y `d` por ángulo y gancho que atrajo al comprador | por `adid` (código) |
| **D1 / X2** | problemas reales de compradores (extracto ≤ 200 car., sin datos personales) | `senales_propias.jsonl` |
| **M1** | métodos de pago que fallan o se reembolsan, países | informe |
| **Dueño** | lo que espera su clic, lo escalado, los incidentes | resumen diario y semanal |

Toda cifra con **n, ventana y cohorte madura** (garantía + 7 días); con muestra insuficiente se dice y no se interpreta.

## 6. Método de pago frente a disputa y reembolso (Anexo C, `[VERIFICAR]`)

| Método | Contracargo | Reembolso |
|---|---|---|
| Tarjetas, Apple/Google Pay, Link | sí; ≈ 15 USD, +15 al contestar (se devuelve si se gana); ≈ 120 días | inmediato; comisión no devuelta |
| BLIK (solo PLN; hoy bloqueado por contrato) | sí, sin tarifa; responder en 12 días; notificación hasta 13 meses | hasta 730 días, ≤ 120 min |
| MB WAY / Satispay | sí; 7 / 15 días | Satispay 180 días |
| Przelewy24, Bancontact, EPS, iDEAL, Multibanco | sin contracargo | transferencia de la LLC (1-5 días); cola humana |
