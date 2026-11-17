# Glosario del proyecto (términos que usa esta skill)

- **Oferta** = un concepto × un idioma/clúster de mercados (backbone §3.1). Familia = ofertas del mismo concepto.
- **Locale** = BCP-47 con región (`it-IT`). **Bloque** = 1 locale + países de misma moneda y régimen.
- **Hipótesis** (`estado_decision`): todo mercado, hasta tener datos propios suficientes. **Prior**: una preferencia por un mercado sin evidencia propia; **no existe** (`prior_de_mercado = ninguno`).
- **Fase de pagos**: `estandar_tarjeta_billeteras` (vigente) o `con_locales`. **Cobertura**: suma de cuotas de los métodos que la fase permite cobrar. **Valor de desbloqueo**: cobertura(con_locales) − cobertura(estándar), en pp.
- **Hueco PayPal**: cuota del pago online que cubre PayPal y una LLC de EE. UU. no puede cobrar vía Stripe.
- **`r`**: CPA esperado / neto (sin bump). **`r_b`**: `r` / factor de bump (R9).
- **Exposición** V·A·A+·R: riesgo regulatorio del país por macro-nicho. **Etiqueta**: marca de la promesa/contenido final del candidato que dispara una restricción (R3).
- **R1-R10**: exclusiones duras. **MQ-nn**: checks deterministas del QA (L1).
- **Gate H**: aprobación humana obligatoria (primer lanzamiento en un país o idioma). **Señal de proceso**: resultado de un test por debajo de `clics_min_decidir_mercado`: detecta fallas de proceso, no decide mercados.
- **Barrido**: corrida del radar de D1 (Modo D) sobre la Biblioteca de Anuncios; **muestra truncada**: ≤ 50 anuncios por consulta (conteos = piso).
- **Atlas**: índice derivado de las fichas por (país, locale).
- **T3**: decisión de una celda oferta × mercado contra su CPA de equilibrio (docs/08).
