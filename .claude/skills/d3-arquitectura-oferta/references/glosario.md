# Glosario de D3

| Término | Significado |
|---|---|
| `oferta_id` / unidad | un concepto en un `locale` y un clúster de `paises_segmentacion` con una `moneda` de cobro (backbone 3.1); otro idioma o mercado = nueva `oferta_id` con `variante_de` |
| MU / EU | mecanismo único (un «cómo» nombrable de 2-6 palabras) y entregable único (un producto digital autocontenido sin servicio); la **prueba de una frase** los une (backbone 5.11) |
| `aov` | valor medio del pedido = P + b·Pb + u·Pu (frontal + bump + upsell ponderados por su toma) |
| `mc`, `cpa_be`, `cpa_be_visto`, `cpa_obj` | margen de contribución por pedido (= CPA de equilibrio) · el mismo visto en Ads Manager (÷ (1 + recargo de Meta)) · objetivo = `factor_cpa_objetivo` × `cpa_be_visto` |
| `cpa_real` (pes / central / opt) | CPM ÷ (1000 × CTR de enlace × conversión clic→compra) por escenario; con `InitiateCheckout`, × `penal_evento_senal` |
| `razon` / `razon_obj` | `cpa_be_visto / cpa_real(central)` y `cpa_obj / cpa_real(central)` |
| `razon_min_factible` | umbral de `FACTIBLE` (`parametros.economia`); `< 1,0` = `NO_FACTIBLE`; entre ambos, `AJUSTADA` |
| `roas_be` | `aov / cpa_be` |
| `presupuesto_test_min`, `dias_test`, `gasto_test_plan`, `perdida_max_test` | plan del test que calcula el motor; la pérdida máxima suma los costos fijos de la oferta |
| `limites_pendientes[]` | claves críticas de `limites.yaml` aún en `null`: la oferta se calcula pero no autoriza gasto |
| P, C, E, N | ejes de riesgo: promesa, contenido, encuadre, negocio (nota 25 §2); el nivel es el máximo |
| P2s / P2n | cifra del propio entregable (amarillo) / resultado atribuido al lector (rojo, con o sin cifra) |
| RE-01…15 | catálogo de reencuadres seguros (nota 25 §4) |
| N1-N5 (ángulos) | niveles de conciencia de Schwartz; **no** son los niveles de autonomía N0-N4 ni el eje N de riesgo |
| `requiere_gate_humano_legal` | nombre heredado del contrato: gate **H del dueño** para amarillo (decisión 14: no es abogado) |
| gate H / S / A | humano obligatorio / semi (por excepción) / automático (`contratos/gates.json`) |
| `parada.json` | señal de «no entrego oferta» (devuelta a D1, NO_FACTIBLE agotado, riesgo rojo, dato ausente, mercado no permitido) |
| `[SUPUESTO]` · `[HIPÓTESIS]` · `[VERIFICAR]` · `[PENDIENTE]` | dato asumido · número o regla a calibrar · hecho externo sin confirmar · lo que construye otro componente (solo en `dependencias.md`) |
| escalón local | precio psicológico del mercado (14,90 €, 49 zł) |
| ciclo de palancas | una revisión del diseño (precio, bump, mercado) seguida de una corrida del motor; máximo 2 |
| dorado / sembrado / retención | oferta que debe dar PASS · oferta con un defecto inyectado que el QA debe detectar · conjunto de casos de frontera sellado por el dueño que la skill no ve |
