# Informe de inviabilidad — OF-AAAAMM-NN (D3, <fecha>)

> Se escribe en la sección C de `oferta.md` cuando el veredicto sigue NO_FACTIBLE tras 2 ciclos de palancas. Es la evidencia con la que el dueño decide; no es una excusa: cada línea sale del motor.

**Conclusión:** NO_FACTIBLE. Peor país: <XX>, razón <x,xx> (< 1,0). La oferta no pasa a D4. Se entrega `oferta.json` (puntaje total ≤ 59) y `economia.json` solo para que la decisión tenga base.

| Corrida | Ciclo | Palanca | Precio | Bump | País(es) | razón (peor) | Veredicto |
|---|---|---|---|---|---|---|---|
| 1 | 0 | propuesta inicial | | | | | |
| 2 | 1 | bump / embudo (el precio frontal es el de la escalera J16 y no se barre) | | | | | |
| 3 | 2 | mercado (se quita el país inviable) / bump | | | | | |

**Por qué las palancas no alcanzan:** <dos o tres frases con cifras del motor: p. ej. «el CPA de equilibrio máximo alcanzable con el tope de `precio_lista_rango` es X y el CPA real central es Y»>.

**Lo que NO se hizo (y no se debe hacer):** subir CTR o conversión sin fuente D2/M1, quitar el IVA o la comisión fija, cambiar el veredicto a mano, o proponer un precio fuera de `precio_lista_rango` sin gate H.

**Opciones para el dueño (H):**
1. Descartar la oferta (el costo de equivocarse aquí es cero; en la campaña son los días de `perdida_max_test`).
2. Volver a D1 con el motivo canónico que corresponda (`mercado_demasiado_estrecho`, `sustituto_gratis_dominante`…) o cambiar de mercado con M1.
3. Aprobar un precio fuera de rango o un override de escenarios con fuente D2/M1 (queda en `supuestos[]` y L1-04 lo marca MAYOR).
