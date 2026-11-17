# Dossier <tema> · para el dueño y el contador

> PLANTILLA. **No es asesoría legal ni fiscal.** Sin revisión legal humana (decisión 14); lo verificable lo automatiza X1; **lo fiscal lo decide el contador**. Fecha: AAAA-MM-DD · `locale`/países: …

## 1. Resumen para el dueño (lenguaje de negocio, ≤ 10 líneas)
Qué se revisó, qué se bloquea, qué se aprobó, qué decisión tuya falta y con qué consecuencia.

## 2. Para el contador (lo fiscal; X1 solo lo señala)
| Tema | Dato que X1 vio (con fuente y fecha o `[VERIFICAR]`) | Decisión que corresponde al contador |
|---|---|---|
| Entidad y país de cobro | | |
| Modelo de impuestos: Stripe directo + Stripe Tax / Managed Payments / MoR | `mp_elegible`: sí/no (producto 100 % automatizado, sin servicio humano) | |
| IVA UE (OSS no-Unión) y registro UK (IVA desde la primera venta) | | |
| Umbrales de ventas por país/estado (alerta de F1) | | |

## 3. Riesgos residuales sin dueño legal (X1 los clasifica; decide el dueño y lo registra en `empresa/decisiones_dueno.jsonl`)
| Riesgo | Nivel (verde/amarillo/rojo) | Por qué | Mitigación automática vigente | Decisión del dueño |
|---|---|---|---|---|
| Promesa monetaria o nicho de riesgo alto | | | | |
| Requerimiento de autoridad, reclamo masivo o cierre de cuenta | | | contingencia.md | |
| Voces o rostros parecidos a personas reales | | | etiqueta IA + C2PA | |

## 4. Estado de cuentas (solo lectura)
`account_status` · calidad declarada (fecha) · rechazos en la ventana · disputas/reembolsos · acción propuesta por el código.

## 5. Pendientes y `[VERIFICAR]`
…
