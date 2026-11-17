# Informe semanal de escala — semana AAAA-Www (lunes <fecha>)

> v0.1 sin pulir. Lo redacta `d9-maker` el lunes (cierre semanal). **Toda cifra viene de código o de una fuente citada**; el Maker no calcula. Si no hay dato: `[SIN DATO]` y qué pedido lo falta. ≤ 1 página para el dueño.

## 1. Lo que importa (≤ 5 líneas)
<qué ganó, qué se propuso, qué se ejecutó, qué falló, qué decide el dueño esta semana>

## 2. Ángulo ganador por idioma (ranking de ángulos)
| Idioma/oferta | Ángulo | Compras netas | CPA neto | P(CPA ≤ equilibrio) | Nivel (`RENTABLE/CAMPEON/VALIDADA`) |
|---|---|---|---|---|---|
| <locale · oferta_id> | <angulo_id> | | | | |
(Hoy `dim_anuncio` solo guarda `concepto_id`, no `angulo_id`: `[SIN DATO]` hasta que exista, B2-30.)

## 3. Campañas de escala
| Oferta | ESCALA | Presupuesto actual | Pasos propuestos | Pasos ejecutados | Veredicto a 96 h (bueno/neutro/malo) | Reversiones |
|---|---|---|---|---|---|---|
| | | | | | | |

## 4. Frenos de empresa (J4)
Máximo teórico diario usado / `gasto_diario_global`: <…> / <…> · pérdida acumulada + spend_cap restante / `perdida_neta_acumulada_max`: <…> / <…>. Propuestas **frenadas por el techo** esta semana: <n> (evidencia para que el dueño decida si lo sube con su firma; **no** se propone un número). PAUSA: <no / sí, desde …>.

## 5. Acierto de las decisiones (habilita o frena la escalera)
| Tipo | Decisiones juzgadas | Aciertos | Tasa | Mínimo (`auditor.acierto_min_*`) | Etapa vigente | Cambio propuesto |
|---|---|---|---|---|---|---|
| Subas | | | | | | |
| Bajas | | | | | | |
Fuente: auditor de código (`[PENDIENTE]` P-14). Mientras no exista: «acierto: sin dato; etapa 0 (solo proponer)». Referencia **del sistema de referencia, declarada y sin verificar**: 3 de 4 bajas y 1 de 3 subas aciertan.

## 6. Ganadores vivos en test y relevos
Campeones en test (siguen vivos, regla 2): <n> · en la ESCALA: <n>/<`top_en_escala`> · fatiga abierta: <n> · pedidos a D6 abiertos: <n> (máx. `optimizacion.max_pedidos_abiertos`) · relevos listos en el banco (regla 6): <n>.

## 7. Familias e idiomas
| Familia | Madre (estado) | Hijas | Tablero (n/25) | Fase del idioma | Rehabilitación en curso |
|---|---|---|---|---|---|
| | | | | | |
Concentración: el ganador/idioma más pesado aporta <…> % del ingreso neto de la semana (riesgo de concentración).

## 8. Falsos descartes del día 1 (si hay dato)
Ofertas dadas de baja por la regla de J3: <n>; de ellas con grupo de control que luego vendieron: <n> (`decision.reglas.estimar_falsos_descartes`). Sin dato: `[SIN DATO]`.

## 9. Pedidos abiertos que más frenan
1. <P-xx · qué frena · a quién> 2. <…> 3. <…>

## 10. Para decidir esta semana
<máx. 3 decisiones del dueño con su costo de equivocarse: criterio de ganador (E-05), techos, idioma nuevo, etapa de la escalera…>
