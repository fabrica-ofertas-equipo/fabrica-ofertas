# Tarjeta de gate: activar campaña (1 página)
> v0.1 sin pulir (skill 0.1.1). La lee el dueño en 2 minutos y firma o no. El agente NO activa. Todo número sale de `campana.json`, `economia.json` y `limites.yaml`: ninguno se escribe a mano.

**Oferta:** `<oferta_id>` · `<marca>` · idioma `<locale>` · países `<paises>` · moneda `<moneda>` · `problema_id`/`candidato_ref`: `<…>` · macro-nicho `<salud|relaciones|dinero>`
**hash_config (lo que firmas):** `sha256:<…>` · **object_ids:** campaña `<id>`, conjunto `<id>`, anuncios `<n>` ids · **Preflight:** `<VERDE, modo vivo, válido hasta …>` · **QA D7:** `<PASS, qa/d7-vN.json>` · **Sello X1:** `<vigente hasta …>`

## 1. Dinero (peor caso, con tarifa de ubicación `<tarifa> %`)
| | Importe |
|---|---|
| Presupuesto diario (Meta) | `<diario>` |
| Máximo teórico diario (× `<factor>`) | `<max_teorico_diario>` (tope diario por oferta: `<gasto_diario_por_oferta>`) |
| Total del test (visible / facturado con tarifa) | `<total_test>` / `<facturado_plan>` |
| `spend_cap` o candado (`stop_time` + `lifetime_budget`) | `<…>` (peor caso facturado `<…>` ≤ techo `<techo_total>`) |
| Límite de gasto de la cuenta en Meta | `<…>` |
| Gasto en 24 h / 7 días / total (máximos) | `<…>` / `<…>` / `<…>` |

## 2. Qué responde el test
CPA de equilibrio `<cpa_be>` (visto en Ads Manager `<cpa_be_visto>`), objetivo `<cpa_obj>`, corte `<k> × <cpa_max>` por anuncio · `<n_anuncios>` anuncios · `<dias>` días.
**¿Valida o solo refuta?** `<VALIDA | SOLO REFUTA: faltan <…> de tope para validar>` · **Evento:** `<PURCHASE | INITIATE_CHECKOUT>`; `<si IC: faltan <…>/día para PURCHASE>`. Se juzga por compras de Stripe.

## 3. Riesgo y cumplimiento
Nivel `<verde|amarillo-a>` · reencuadre aplicado `<sí/no, cuál>` · `claims_a_evitar` respetados `<sí>` · RHS `<hecha/pendiente/no aplica>` · cuota usada `<…>` · `special_ad_categories` `<[] | …>` (X1) · DSA beneficiario `<…>` y pagador `<…>` · mejoras de Meta `OPT_OUT` · `self_ai_disclosure` `<…>`

## 4. Vigilancia y traspaso
T0 = activación. Ventanas: T+1 `<hora>`, T+6, T+24, T+48, T+72. Dueño de la ventana: D7; disparador: `<motor/dueño>`. Pausa automática por gasto > `<…>` o anuncio rechazado. Traspaso a D8 a las 72 h si 0 anomalías y 0 rechazos.

## 5. Riesgos, `[SUPUESTO]` y preguntas abiertas
`<lista corta>`

## 6. Si dices «no»
Nada se activa; el borrador sigue `PAUSED`; el Maker corrige lo que indiques (nueva versión; el `hash_config` cambia y se re-sella).

**Firma (en tu terminal, fuera de la sesión del agente):** `python -m engine.orq firmar --oferta <oferta_id> --accion activar_campana --hash-objetivo <hash_config> --clave-privada <ruta de tu clave Ed25519> --como dueno`. La clave privada nunca va en un chat ni en el repositorio. Gate efectivo de activar: H en todo nivel (C-04 abierta hasta tu decisión K-02/D-02).
