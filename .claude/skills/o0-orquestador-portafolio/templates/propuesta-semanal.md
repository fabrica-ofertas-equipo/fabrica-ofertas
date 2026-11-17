<!-- PLANTILLA de propuesta semanal (modo B). Ruta real: empresa/propuestas/AAAA-Www.md (+ .json). TODA cifra sale de portafolio.py / decision/ [PENDIENTE: S-B, SB-18];
     sin eso este documento es solo estructura y lleva el rótulo SIN CIFRAS RECOMPUTADAS. Ejemplo ficticio: ningún número de aquí es real. -->
# Propuesta semanal AAAA-Www · <SIN CIFRAS RECOMPUTADAS | cifras recomputadas con portafolio.py v…>
Generada: <AAAA-MM-DDThh:mm:ssZ> · vence a las `parametros.orquestador.propuesta_vence_h` · datos al <AAAA-MM-DDThh:mm:ssZ> (frescura ≤ `frescura_datos_max_h`)

## 1. Resumen en 5 líneas
<Dónde está tu plata (gasto acumulado y de hoy por oferta; cita archivo) · qué se propone hacer · qué necesita tu firma · el mayor riesgo · qué cambió desde la semana pasada.>

## 2. Decisiones por oferta
| Oferta (macro-nicho · locale) | Fase | Recomendación (de `decision/`) | Evidencia (archivo y campo) | Incertidumbre | Costo de equivocarse | Alternativa descartada |
|---|---|---|---|---|---|---|
| <OF-… (dinero · it-IT)> | <en_test> | <seguir / matar / escalar / esperar> | <ofertas/OF-…/08-operacion/…> | <intervalo o «datos insuficientes»> | <monto moneda_limites> | <qué y por qué no> |

## 3. Asignación semanal
Ofertas en paralelo = mín(`limites.ofertas_en_test_simultaneas_max`, presupuesto semanal ÷ gasto de test por oferta, capacidad de revisión, `paralelas_max_por_nivel[N]`) = <n>. Mercados en paralelo ≤ `mercados.mercados_test_paralelos_max`.

## 4. Ascensos recomendados (solo los que recomienda el motor con su evidencia)
<Ninguno | etapa → nivel, con las métricas de confianza y el número de ofertas>

## 5. Riesgos y banderas
<Rechazos de Meta, disputas y reembolsos frente a `salud_operativa.*`, hojas pausadas, cuota amarilla usada, bandera L1/L2 abierta>

## 6. KPIs (propios y diferidos)
<Aprobación sin edición y de primera ronda · tiempo botón → candidato → campaña lista · costo por oferta lanzada · incidentes de guardarraíl · tasa de escape · ofertas validadas por macro-nicho × locale (diferido)>

## 7. Radar de D1
<Barridos de la semana y costo frente a `limites.max_costo_por_barrido` · tamaño del banco · candidatos vigentes · % de verdes en el top-N · antigüedad de la evidencia · barridos cancelados por PAUSA>

## 8. Exposición
| Eje | Valor | Frente a |
|---|---|---|
| Por macro-nicho (salud / relaciones / dinero) | <% del gasto> | cuota de exploración |
| Por mercado (locale) | <% del gasto> | un mercado no es prior |
| Por nivel de riesgo (verde / amarillo) | <% del gasto> | cuota amarilla (`limites`, claves de nichos de `limites` 1.3.0; `null` = SOLO VERDE) |

## 9. Propuestas de D9 (con tu «sí» el motor crea el brief hijo o cierra la oferta; D9 nunca activa)
<`expansion.json` → `accion:lanzamiento_pais_idioma_nuevo` · `retiro.json` → `accion:retirar_oferta` · `plantilla_clon.json`>

## 10. Lo que necesito que firmes
| Qué | Gate | Comando (lo corres tú) |
|---|---|---|
| <accion> | H | `.venv/bin/python -m engine.orq firmar --oferta OF-… --accion <accion> --como dueno --hash-objetivo <hash de lo que firmas> --clave-privada <RUTA que pones tú>` |

## 11. `[SUPUESTO]` y `[VERIFICAR]`
<Lista; cada uno con su fuente>
