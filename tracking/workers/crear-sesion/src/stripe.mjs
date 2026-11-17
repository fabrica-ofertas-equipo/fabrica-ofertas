// Construccion de la Checkout Session de Stripe (docs/07 2.4; docs/06 4.3).
// El precio SOLO sale del catalogo firmado (nunca del cliente); la
// `Idempotency-Key` es determinista: `sha256(operacion, oferta_id,
// visitor_id, price_id, bump, bucket)`.

import { sha256Prefijado } from "../../_lib/src/hash.mjs";
import { jsonCanonico } from "../../_lib/src/json_canonico.mjs";

/** Claves que `checkout.metadata_esquema` exige (contratos/checkout.schema.json). */
const CLAVES_METADATA_OBLIGATORIAS = [
  "oferta_id",
  "adid",
  "asid",
  "cid",
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
  "visitor_id",
  "consent_marketing",
  "landing_version",
  "event_source_url",
];

/**
 * Construye la metadata completa: SIEMPRE incluye las claves obligatorias
 * (con "desconocido" o "" cuando falten, nunca las omite: eso es lo que
 * exige el caso "metadata sin adid"). `fbp`/`fbc` solo si existen.
 */
export function construirMetadata({ ofertaId, visitorId, params, consentMarketing, landingVersion, eventSourceUrl, eventId }) {
  const p = params ?? {};
  const metadata = {
    oferta_id: ofertaId,
    adid: p.adid ?? "desconocido",
    asid: p.asid ?? "desconocido",
    cid: p.cid ?? "desconocido",
    utm_source: p.utm_source ?? "",
    utm_medium: p.utm_medium ?? "",
    utm_campaign: p.utm_campaign ?? "",
    utm_content: p.utm_content ?? "",
    utm_term: p.utm_term ?? "",
    visitor_id: visitorId,
    consent_marketing: consentMarketing,
    landing_version: landingVersion,
    event_source_url: (eventSourceUrl ?? "").slice(0, 500),
  };
  if (p.fbp) metadata.fbp = p.fbp;
  if (p.fbc) metadata.fbc = p.fbc;
  if (eventId) metadata.event_id = eventId;
  for (const clave of CLAVES_METADATA_OBLIGATORIAS) {
    if (!(clave in metadata)) {
      throw new Error(`construirMetadata: falta la clave obligatoria ${clave}`);
    }
  }
  return metadata;
}

/** `Idempotency-Key = sha256(operacion, oferta_id, visitor_id, price_id, bump, bucket)` (docs/06 4.3). */
export async function construirIdempotencyKey({ ofertaId, visitorId, priceId, bump, bucket }) {
  const payload = jsonCanonico({
    operacion: "crear_sesion",
    oferta_id: ofertaId,
    visitor_id: visitorId,
    price_id: priceId,
    bump,
    bucket,
  });
  return sha256Prefijado(payload);
}

/**
 * Payload de la Checkout Session (forma logica; la codificacion a
 * `application/x-www-form-urlencoded` la hace `aFormularioStripe`).
 * `priceId` SIEMPRE viene del catalogo del servidor, nunca del cuerpo del
 * cliente (asi se neutraliza un "precio manipulado").
 */
export function construirPayloadSesion({ priceId, bumpPriceId, bumpTomado, visitorId, metadata, successUrl, returnUrl, locale }) {
  const lineItems = [{ price: priceId, quantity: 1 }];
  if (bumpTomado && bumpPriceId) {
    lineItems.push({ price: bumpPriceId, quantity: 1 });
  }
  return {
    mode: "payment",
    ui_mode: "hosted", // [VERIFICAR en sandbox] (docs/07 2.4): valor exacto del parametro real
    line_items: lineItems,
    client_reference_id: visitorId,
    metadata,
    success_url: successUrl,
    return_url: returnUrl,
    locale,
  };
}

/** Codifica un objeto anidado a `application/x-www-form-urlencoded` (sin dependencias). */
export function aFormularioStripe(obj) {
  const params = new URLSearchParams();
  function recorrer(valor, clave) {
    if (valor === null || valor === undefined) return;
    if (Array.isArray(valor)) {
      valor.forEach((v, i) => recorrer(v, `${clave}[${i}]`));
    } else if (typeof valor === "object") {
      for (const [k, v] of Object.entries(valor)) recorrer(v, clave ? `${clave}[${k}]` : k);
    } else {
      params.append(clave, String(valor));
    }
  }
  for (const [k, v] of Object.entries(obj)) recorrer(v, k);
  return params;
}
