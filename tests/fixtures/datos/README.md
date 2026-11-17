# `tests/fixtures/datos/`

Fixtures de B3 (datos). **Nota de propiedad**: `tests/fixtures/{meta,datos}/reales/` es de **I1**
(ola 2: captura de fixtures reales con el MCP de Meta y el sandbox de Stripe, criterio B0-24). Esta
sesión no escribe ahí; en su lugar deja aquí, al nivel de `tests/fixtures/datos/`, fixtures de
**forma real pero sintética** (criterio B0-15, 24) para que los parsers de `datos` tengan algo
realista contra qué probarse hasta que exista una captura real.

- `meta_insights_OF-202611-01.json`: 3 días × 5 anuncios de `ofertas/_ejemplo` (es-ES, EUR), con la
  forma de la Graph API de Meta (Insights, `level=ad`, `time_increment=1`). Los valores del
  2026-11-11 coinciden a propósito con
  `ofertas/_ejemplo/08-operacion/diario/2026-11-11/kpi_oferta_dia.json` para poder comparar.
- `stripe_eventos_OF-202611-01.json`: 3 `checkout.session.completed` (uno duplicado con otro
  `event.id` para probar la deduplicación por `(tipo, objeto_id)`), 1 compra de prueba
  (`metadata.verificacion=1`, excluida), 1 `charge.refunded` y 1 `charge.dispute.created`, con la
  forma de la API de Stripe (`Event`, `Checkout Session`, `Charge` con `refunds` expandido,
  `Dispute`). Importes coherentes con `ofertas/_ejemplo/05-landing/checkout.json` (precio 1990, bump
  790 centavos de EUR).

Ambos marcados `"sintetico": true`: no hay una captura real (esta sesión nocturna no tiene conector
de Meta ni de Stripe ni acceso a red). Cuando I1 capture una respuesta real en
`tests/fixtures/{meta,datos}/reales/`, estos archivos pueden sustituirse por esa captura manteniendo
la misma forma. Sin datos personales: `visitor_id` e IDs son sintéticos; no hay correos, nombres ni
tarjetas.
