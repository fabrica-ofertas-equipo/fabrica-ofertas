# Informe D2 — {oferta_id} · {locale} · {candidato_id}  (≤ 3 páginas, en español)

> Plantilla. Todo lo que mueva el veredicto lleva su `EV-nn` (URL https + fecha). El veredicto sale del script; aquí solo se explica. Estado: {provisional | definitivo}.

## 1. Veredicto
**Calculado (script): {GO | GO_CONDICIONAL | NO_GO} · Propuesto: {…} · Final: {…}** · Confianza: {puntos}/100 ({alta|media|baja}) — criterios cumplidos: {c1 … c5}.
Razones (códigos del script traducidos): {…}. Si es GO_CONDICIONAL: **refinamiento** {sub-nicho | ángulo | MU | país | formato} y **evidencia faltante** {lista accionable}.

## 2. Tres evidencias que sostienen el veredicto
1. {hecho con cifra} — `EV-nn` · {URL} · {fecha}
2. …
3. …

## 3. Lo que NO se sabe (y qué lo refutaría)
- Gasto, impresiones, conversiones y ventas de los competidores: la Biblioteca no los da. «{N} anuncios» y `estimated_total_count` son contexto, no prueba.
- {Conteos que son un PISO por muestra truncada: cuáles.}
- {Lo que cambiaría el veredicto: p. ej. «si el hueco aparece en ≥ 30 % de los sostenidos…»}.

## 4. Competidores verificables por el dueño (≥ {competidores_verificables_min}) — verificación ≈ {minutos} min
| Competidor (`operador_id`) | Tipo | Promesa (paráfrasis) | Mecanismo (clase M) | SS_a | Enlaces a abrir (máx. {max_enlaces}) | ¿Coincide? (sí / no / no abre) |
|---|---|---|---|---|---|---|
| {op-01} | {producto_digital} | {…} | {M1: …} | {0,875} | https://www.facebook.com/ads/library/?id={…} · …| |
Cómo verificar: abre cada enlace (≈ {minutos_por_enlace} min), compara **promesa** y **mecanismo** con esta fila y marca la última columna. Lo que marques «no» pasa a `inferido` o `no_disponible` y se recalcula.

## 5. Huecos y diferenciador
{Hueco sustentado: ausente en X de Y sostenidos con ≥ 3 anuncios leídos; ≥ 5 frases de ≥ 3 fuentes.} Saturación de mecanismo: {baja|media|alta} (MU clase {Mx}; share {…}; |O| = {…}). Sustituto gratis (web, YouTube, chatbot): {no dominante | diferenciado | dominante}.

## 6. Riesgo y nivel
Nivel final: {verde | amarillo-a | amarillo-b | rojo} (heredado de D1: {…}; D2 solo lo sube). Ángulo seguro: {…}. Claims de la competencia que **no** se copian (`prohibido_copiar`): {lista}. Dictamen de X1: {PASS | PASS_CON_NOTAS | FAIL | pendiente}.

## 7. Qué necesito de ti
{Gate S: revisar GO / GO_CONDICIONAL. Decisiones `[DUEÑO]`: …} · Tiempo que te llevó la lectura: {min} (anótalo en `Pulido`).
