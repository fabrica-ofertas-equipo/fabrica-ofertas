# Tarifa de ubicación y DSA por país (hechos de plataforma `[VERIFICAR]`)

## Tarifa de ubicación de Meta

Desde 2026-07-01 `[VERIFICAR]` (https://www.facebook.com/business/help/1238737454289085; 07a, 16): FR/IT/ES 3 %, AT 5 %, UK 2 %, TR 5 %; va en la **factura**, no aparece en Ads Manager; no aplica a categorías especiales. Relectura mensual (`parametros.compliance.reverif_plataformas_dias`).

**Regla de la skill:** D7 no usa esa tabla: lee `economia.entradas_usadas.tarifa_meta_bp` (D3 la toma de `tarifas.json#recargo_meta_bp` del país de mayor recargo del clúster) y la aplica en el techo, el `spend_cap` y la tarjeta. Sin `tarifa_meta_bp` el lint da BLOQ `tarifa_meta_bp_ausente`. Excluir o no FR/IT/ES/AT por la tarifa es decisión del dueño (Meta no garantiza reducirla): `preguntas-abiertas.md`. Un `campana.economia.tarifa_meta_bp` propio es pedido a contratos `[PENDIENTE]`.

## DSA (Reglamento de Servicios Digitales)

Beneficiario y pagador son obligatorios en todo anuncio **nuevo o editado** que apunte a la UE o «mundial»; son visibles en la Biblioteca de anuncios hasta 1 año; sin efecto en entrega ni costo (https://www.facebook.com/business/help/605021638170961; 07a A.4). Sin DSA, Meta no publica, tampoco por API.

- Destino UE = algún país de `campana.paises` en la UE (27). EEE no UE: `[VERIFICAR]`.
- El conjunto se crea con `dsa_beneficiary` y `dsa_payor` = `cuenta_meta.default_dsa_beneficiary/payor` (la LLC o la marca que decida el dueño **antes del primer gasto**: queda pública un año). El conector rellena ese valor con el nombre de la empresa; el Maker no lo inventa.
- Comprobación: el Maker lee el conjunto del borrador (`ads_get_ad_entities`) y anota `dsa_beneficiary`/`dsa_payor` en el log (`LECTURA_CONJUNTO`, bitácora); la prueba es `07-campana/lectura_viva.json` (código): el lint C14 exige ambos no vacíos por cada `adset_id` de `ids_meta.json` (sembrados S17 y S24) y, hoy, `lectura_viva.json` aún no los trae `[PENDIENTE: SB-12]`.
- Activar en UE sin DSA es un incidente (KPI: 0 activaciones UE sin DSA).

## Otros hechos usados

- Máximo teórico diario 1,75× el presupuesto (HC-26 `[VERIFICAR]` texto oficial); semanal ≤ 7×.
- Ediciones significativas (segmentación, creativo, evento, agregar anuncio, pausa ≥ 7 d, parámetro de URL publicado) reinician aprendizaje y disparan revisión (HC-3, HC-16, HC-25); resultados maduran en ~48 h (HC-45).
- Mínimo de `spend_cap` de Meta ≈ 100 USD o equivalente local (https://developers.facebook.com/docs/marketing-api/reference/ad-campaign-group, leída 2026-11-06; monto local exacto `[VERIFICAR]`).
- Offset de moneda: https://developers.facebook.com/docs/marketing-api/currencies.
- Máx. 50 anuncios por conjunto y formato flexible de 10 medios `[VERIFICAR]` (04 §2.7); el test usa 3–6.
