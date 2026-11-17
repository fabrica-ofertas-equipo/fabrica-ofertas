# Informe de cierre de D8 · `<oferta_id>` · `<AAAA-MM-DD>`
> v0.1 sin pulir (skill d8-optimizacion 0.1.0). Se redacta **cuando termina el ciclo de una oferta** (baja de lanzamiento, veredicto, retiro o graduación a escala). Ruta: `ofertas/<oferta_id>/08-operacion/cierre/informe-de-cierre.md`. Es insumo del `postmortem.json` (lo redacta el cierre de O0 con `orq cerrar` y lo confirma el dueño; contrato `postmortem`: `causa_principal`, `causas[nivel_evidencia]`, `parametros_a_calibrar`, `retraso_clic_compra`) y del cerebro. **Toda cifra se copia** de `entrada.json`, `kpi_oferta_dia.json`, `veredicto_oferta.json`, `decisiones.jsonl` o del libro de F1, con su fuente; aquí no se calcula nada.

## 1. Identificación y causa de cierre
**Oferta:** `<oferta_id>` · `<concepto × idioma/locale>` · **variante de:** `<variante_de|—>` · **ciclo:** `<fecha de primer gasto>` → `<fecha de cierre>` (`<n>` días de cuenta cerrados).
**Causa de cierre:** `<BAJA_J3 | FALLIDA | INCONCLUSA | VALIDADA | GRADUADA | RETIRADA | PAUSA_GLOBAL>` · **quién la ejecutó:** `<código (decision_id) | dueño>` · **gate:** `<H|A>`.
**Una frase para el dueño:** `<p. ej. «Se apagó al cierre del día 1: gastó 74 de 75 USD, 160 clics, 4 inicios de pago y 0 ventas»>`.

## 2. Cronología (cada hito con su `decision_id`)
| Fecha | Qué pasó | Fuente |
|---|---|---|
| `<…>` | lanzamiento: CBO de `<n>` creativos a `<presupuesto>` (J3) | `07-campana/campana.json` |
| `<…>` | `<decisión del motor o propuesta de D8>` — `<accion · codigo>` | `decisiones.jsonl:<decision_id>` |
| `<…>` | `<aplicada por … / rechazada por el dueño>` | `<…>` |

## 3. Dinero contra los frenos de empresa (J4)
| Concepto | Valor | Fuente |
|---|---|---|
| Gasto total de la oferta | `<…>` | `<acumulado.gasto_minor o ledger de F1>` |
| Ingreso neto (Stripe) · reembolsos | `<…>` · `<…>` | `<kpi_oferta_dia.json / veredicto_oferta.json>` |
| Pérdida de la oferta | `<…>` | `<F1>` |
| Pérdida neta acumulada de la cartera / tope `perdida_neta_acumulada_max` | `<…>` / `<null | 3000 USD>` | `<F1>`, `limites.yaml` |
| Gasto del día más alto de la empresa / tope `gasto_diario_global` | `<…>` / `<null | 300 USD>` | `<F1>`, `limites.yaml` |

## 4. Qué se aprendió (separar hecho, hipótesis y causa)
- **Hecho (con cifra y fuente):** `<embudo del último día: clics → vistas → inicios de pago → ventas>`.
- **Hipótesis (`[HIPÓTESIS]`):** `<precio | promesa | checkout | creativos | landing>` — **nivel de evidencia:** `<bajo|medio|alto>`. Un día de datos no prueba una causa.
- **Causa principal propuesta** (kebab, para el `postmortem`): `<p. ej. sin-venta-dia-1-embudo-completo>` · **causas:** `<codigo · descripción ≤ 300 caracteres · nivel_evidencia>`.
- **Ángulos, hooks y mecanismos probados** (con `n` e intervalo si el motor los dio; si no, «sin intervalo»): `<…>`.
- **Retraso clic→compra observado:** `<n_compras · mediana_h · p90_h | «sin compras»>` (calibra `lanzamiento.espera_post_dia_h`).
- **Falsos descartes:** `<¿hubo control? tasa si la hay | «sin medir»>`; referencia del modelo: `estadistica-honesta.md` §5.
- **Parámetros a calibrar** (`grupo.clave` de `parametros.yaml` y motivo): `<…>`.

## 5. Qué se repite y qué no
`<qué mantener del paquete (si la oferta vendió) | qué cambiar en la próxima variante: UNA variable>` · `no_repetir[]`: `<ganchos y claims que cayeron>`. Sin testimonios, cifras de alumnos ni urgencias inventadas (J8).

## 6. Señales para otras etapas (sin datos personales)
| Para | Señal |
|---|---|
| D1/M1 | `<objeciones o motivos de reembolso por ángulo (sin datos personales); evidencia por locale>` |
| D3 | `<desvío frente a economia.json: CPA, conversión, reembolso>` |
| D5 | `<fallas de conexión, checkout o atribución vistas>` |
| D6 | `<hooks y formatos que sirvieron o no>` |
| X1 | `<rechazos, claims que fallaron>` |

## 7. Pendientes
**Humano:** `<…>` · **Código / otros equipos:** `<PEDIDOS.md P-xx>` · **`[SUPUESTO]`:** `<…>` · **`[VERIFICAR]`:** `<…>`.

## 8. Autoverificación
`[ ]` cifras con fuente · `[ ]` la baja de lanzamiento no se presenta como veredicto FALLIDA de la oferta · `[ ]` hipótesis marcadas · `[ ]` sin datos personales · `[ ]` el informe no afirma lo que el día no prueba.
