// Logica pura del Worker `capi` (modulo interno, docs/06 4.3): construye y
// envia eventos server-side a la API de Conversiones de Meta (Graph
// `/{dataset}/events`). Sin dependencias; toda red pasa por un `transporte`
// inyectado (`{ solicitar(metodo, url, { cabeceras, cuerpo }) }`), igual que
// el resto del sistema (convenciones 4.1 "Red").
//
// Reglas de negocio (docs/06 4.3, M10, M11):
// - `enviarPurchase` SOLO si `consent_marketing === "1"` (sin eso, 0 llamadas a Graph).
// - `fbp`/`fbc` viajan SIN hash (si existen); `em`/`ph` normalizados y con SHA-256.
// - No se reenvia un evento de mas de 6 dias (limite de la plataforma Meta, no
//   un parametro de negocio: se deja como constante documentada, igual que
//   `factor_techo_teorico_diario` en limites.schema.json).
// - `event_id` determinista: `purchase_<session_id>` o `ic_<visitor_id>_<ts>`.
// - Ningun dato de salud viaja en `event_source_url` ni en `custom_data` (compliance).

import { sha256Hex } from "../../_lib/src/hash.mjs";

const DIAS_MAX_REENVIO_META = 6; // limite de la plataforma Meta, no un parametro de negocio

export function idPurchase(sessionId) {
  return `purchase_${sessionId}`;
}

export function idInitiateCheckout(visitorId, ts) {
  return `ic_${visitorId}_${ts}`;
}

export function normalizarEmail(email) {
  return email.trim().toLowerCase();
}

export function normalizarTelefono(telefono) {
  return telefono.replace(/[^0-9]/g, "");
}

/** SHA-256 hex de un campo ya normalizado (em/ph), para `user_data`. */
export async function hashCampo(valorNormalizado) {
  return sha256Hex(valorNormalizado);
}

/**
 * `true` si `tsEventoIso` sigue dentro de la ventana de reenvio de Meta
 * (<= DIAS_MAX_REENVIO_META dias antes de `ahora`).
 */
export function eventoEsReciente(tsEventoIso, ahora) {
  const tsEvento = new Date(tsEventoIso).getTime();
  const limite = ahora.getTime() - DIAS_MAX_REENVIO_META * 24 * 60 * 60 * 1000;
  return Number.isFinite(tsEvento) && tsEvento >= limite;
}

function epochSegundos(fechaIso) {
  return Math.floor(new Date(fechaIso).getTime() / 1000);
}

/**
 * Construye el objeto `user_data` del evento: `fbp`/`fbc` sin hash (solo si
 * existen) y `em`/`ph` con SHA-256 (solo si se proveyo el dato crudo).
 */
export async function construirUserData({ fbp, fbc, email, telefono }) {
  const userData = {};
  if (fbp) userData.fbp = fbp;
  if (fbc) userData.fbc = fbc;
  if (email) userData.em = [await hashCampo(normalizarEmail(email))];
  if (telefono) userData.ph = [await hashCampo(normalizarTelefono(telefono))];
  return userData;
}

/**
 * Construye el evento `Purchase` para el Graph API. `valorDecimal` ya viene
 * convertido por el llamador a cadena decimal en unidad estandar (este
 * modulo no decide el exponente ISO 4217: eso es `scripts/validar_esquemas.py`, de CT).
 */
export async function construirEventoPurchase({
  sessionId,
  eventTimeIso,
  eventSourceUrl,
  fbp,
  fbc,
  email,
  telefono,
  valorDecimal,
  moneda,
}) {
  const evento = {
    event_name: "Purchase",
    event_time: epochSegundos(eventTimeIso),
    event_id: idPurchase(sessionId),
    action_source: "website",
    event_source_url: eventSourceUrl,
    user_data: await construirUserData({ fbp, fbc, email, telefono }),
  };
  // `value`/`currency` solo si el llamador ya los convirtio a unidad
  // estandar (el exponente ISO 4217 vive en scripts/validar_esquemas.py, de
  // CT: este modulo no lo reimplementa). Sin ellos, el evento se envia
  // igual (el emparejamiento no depende de `custom_data`), pero sin
  // optimizar por valor: Pedido abierto a CT/B5 (ver README "Pedidos").
  if (valorDecimal !== undefined && moneda !== undefined) {
    evento.custom_data = { value: valorDecimal, currency: moneda };
  }
  return evento;
}

/** Construye el evento `InitiateCheckout` (sin datos de contacto: antes del pago). */
export async function construirEventoInitiateCheckout({
  visitorId,
  eventTimeIso,
  eventSourceUrl,
  fbp,
  fbc,
}) {
  return {
    event_name: "InitiateCheckout",
    event_time: epochSegundos(eventTimeIso),
    event_id: idInitiateCheckout(visitorId, epochSegundos(eventTimeIso)),
    action_source: "website",
    event_source_url: eventSourceUrl,
    user_data: await construirUserData({ fbp, fbc }),
  };
}

/**
 * Envia uno o mas eventos ya construidos a Graph `/{dataset}/events` por el
 * `transporte` inyectado. Nunca se llama si `consentMarketing !== "1"` (lo
 * decide el llamador antes de invocar esta funcion: ver `enviarPurchaseSiCorresponde`).
 */
export async function enviarEventos(transporte, { datasetId, token, apiVersion, eventos, testEventCode }) {
  const url = `https://graph.facebook.com/${apiVersion}/${datasetId}/events`;
  const cuerpo = {
    data: eventos,
    access_token: token,
  };
  if (testEventCode) cuerpo.test_event_code = testEventCode;
  return transporte.solicitar("POST", url, {
    cabeceras: { "content-type": "application/json" },
    cuerpo: JSON.stringify(cuerpo),
  });
}

/**
 * Orquesta el envio de `Purchase` respetando las reglas de consentimiento,
 * ventana de reenvio y ausencia de llamada a Graph cuando no corresponde.
 * Devuelve `{ enviado: boolean, motivo?, respuesta? }`.
 */
export async function enviarPurchaseSiCorresponde({
  consentMarketing,
  sessionId,
  eventTimeIso,
  eventSourceUrl,
  fbp,
  fbc,
  email,
  telefono,
  valorDecimal,
  moneda,
  datasetId,
  token,
  apiVersion,
  testEventCode,
  ahora,
  transporte,
}) {
  if (consentMarketing !== "1") {
    return { enviado: false, motivo: "sin_consentimiento" };
  }
  if (!eventoEsReciente(eventTimeIso, ahora)) {
    return { enviado: false, motivo: "fuera_de_ventana_6_dias" };
  }
  const evento = await construirEventoPurchase({
    sessionId,
    eventTimeIso,
    eventSourceUrl,
    fbp,
    fbc,
    email,
    telefono,
    valorDecimal,
    moneda,
  });
  const respuesta = await enviarEventos(transporte, {
    datasetId,
    token,
    apiVersion,
    eventos: [evento],
    testEventCode,
  });
  return { enviado: true, evento, respuesta };
}
