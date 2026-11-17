// Logica pura del Worker `crear-sesion` (docs/06 4.3; docs/07 2.4).
// Orquesta: tamano del cuerpo -> Turnstile -> formato -> catalogo firmado
// (precio de servidor) -> ids de atribucion (adid/asid/cid solo del
// catalogo) -> cuota diaria -> metadata completa -> Checkout Session.

import { validarCuerpoSesion, formatoIdAtribucionValido } from "./validacion.mjs";
import { verificarTurnstile } from "./turnstile.mjs";
import { cargarCatalogoVerificado, entradaOferta, idEnCatalogo } from "./catalogo.mjs";
import { diaUtc } from "./limitador.mjs";
import { construirMetadata, construirIdempotencyKey, construirPayloadSesion, aFormularioStripe } from "./stripe.mjs";
import { idInitiateCheckout } from "../../capi/src/capi.mjs";

/**
 * Decide `adid`/`asid`/`cid` finales: solo se aceptan si pasan el formato Y
 * figuran en el catalogo firmado de la oferta; si CUALQUIERA falla,
 * `adid` pasa a "desconocido" (docs/06 4.3) y esa sesion cuenta en
 * `cobertura_adid` (lo mide `datos`, no este Worker).
 */
function resolverIdsAtribucion(entradaCatalogo, params) {
  const p = params ?? {};
  const formatoOk =
    formatoIdAtribucionValido(p.cid) && formatoIdAtribucionValido(p.asid) && formatoIdAtribucionValido(p.adid);
  const enCatalogo =
    formatoOk &&
    p.cid !== undefined &&
    p.asid !== undefined &&
    p.adid !== undefined &&
    idEnCatalogo(entradaCatalogo, "cid", p.cid) &&
    idEnCatalogo(entradaCatalogo, "asid", p.asid) &&
    idEnCatalogo(entradaCatalogo, "adid", p.adid);
  if (!formatoOk || !enCatalogo) {
    return { adid: "desconocido", asid: "desconocido", cid: "desconocido", confiable: false };
  }
  return { adid: p.adid, asid: p.asid, cid: p.cid, confiable: true };
}

/**
 * Nucleo comun a los modos JSON y formulario, desde que ya se conocen
 * `ofertaId`/`visitorId`/`bump`/`locale`/`consentMarketing`/`landingVersion`
 * (los modos difieren solo en DE DONDE sacan esos valores: cuerpo JSON o
 * campos de formulario + cookies). Hace: catalogo firmado (precio de
 * servidor) -> ids de atribucion -> cuota diaria -> metadata completa
 * (+ `metadataExtra` opcional, p. ej. evidencia de la renuncia de
 * desistimiento) -> Checkout Session. Devuelve `{ status, cuerpo }`.
 */
export async function crearSesionCheckout({
  ofertaId,
  visitorId,
  bump,
  locale,
  consentMarketing,
  landingVersion,
  params,
  cabeceraReferer,
  metadataExtra,
  env,
  verificarCuota,
  ahora,
  transporte,
}) {
  const catalogo = await cargarCatalogoVerificado(env.catalogoJson, env.catalogoFirma, env.catalogoHmacSecreto);
  if (!catalogo) {
    return { status: 500, cuerpo: { ok: false, codigo: "catalogo_invalido" } };
  }
  const entrada = entradaOferta(catalogo, ofertaId);
  if (!entrada || !entrada.price_id) {
    return { status: 404, cuerpo: { ok: false, codigo: "oferta_no_en_catalogo" } };
  }

  const ahoraDate = ahora();
  const diaActual = diaUtc(ahoraDate);
  const cuota = await verificarCuota({
    visitorId,
    diaUtc: diaActual,
    limite: env.maxSesionesPorVisitante,
  });
  if (!cuota.permitido) {
    return { status: 429, cuerpo: { ok: false, codigo: cuota.motivo ?? "cuota_excedida" } };
  }

  const ids = resolverIdsAtribucion(entrada, params);
  const eventId = idInitiateCheckout(visitorId, Math.floor(ahoraDate.getTime() / 1000));
  const metadata = construirMetadata({
    ofertaId,
    visitorId,
    params: { ...(params ?? {}), ...ids },
    consentMarketing,
    landingVersion,
    eventSourceUrl: cabeceraReferer ?? entrada.success_url,
    eventId,
  });
  if (metadataExtra) {
    Object.assign(metadata, metadataExtra);
  }

  // El precio SIEMPRE sale de `entrada` (catalogo firmado): cualquier
  // `price_id`/`monto` que el cliente intente mandar se ignora por
  // completo (no se lee en ningun punto de este modulo).
  const idempotencyKey = await construirIdempotencyKey({
    ofertaId,
    visitorId,
    priceId: entrada.price_id,
    bump,
    bucket: diaActual,
  });

  const payload = construirPayloadSesion({
    priceId: entrada.price_id,
    bumpPriceId: entrada.price_id_bump,
    bumpTomado: bump === true,
    visitorId,
    metadata,
    successUrl: entrada.success_url,
    returnUrl: entrada.return_url,
    locale,
  });

  const respuestaStripe = await transporte.solicitar("POST", "https://api.stripe.com/v1/checkout/sessions", {
    cabeceras: {
      Authorization: `Bearer ${env.stripeRkCheckout}`,
      "content-type": "application/x-www-form-urlencoded",
      "Idempotency-Key": idempotencyKey,
      "Stripe-Version": env.stripeApiVersion,
    },
    cuerpo: aFormularioStripe(payload).toString(),
  });

  let datosRespuesta;
  try {
    datosRespuesta = JSON.parse(respuestaStripe.cuerpo);
  } catch {
    return { status: 502, cuerpo: { ok: false, codigo: "respuesta_stripe_invalida" } };
  }
  if (respuestaStripe.estado >= 400 || !datosRespuesta.url) {
    return { status: 502, cuerpo: { ok: false, codigo: "stripe_error" } };
  }

  return { status: 200, cuerpo: { url: datosRespuesta.url } };
}

/**
 * Maneja `POST /api/sesion` en modo JSON (sin cambios de comportamiento:
 * `visitor_id`/`params`/`consent_marketing`/`landing_version` vienen en el
 * cuerpo). Entradas principales:
 * - `cuerpo`: JSON ya parseado del cuerpo (el llamador controla el tamano maximo).
 * - `cabeceraReferer`, `ipRemota`.
 * - `env`: catalogo firmado (`catalogoJson`, `catalogoFirma`, `catalogoHmacSecreto`),
 *   `turnstileSecreto`, `maxSesionesPorVisitante`.
 * - `verificarCuota({visitorId, diaUtc, limite}) -> Promise<{permitido, conteo, motivo?}>`:
 *   quien resuelve la cuota real (en produccion, un `fetch` a la Durable
 *   Object `CuotaVisitante`; en pruebas, `limitador.contarSesionYRegistrar`
 *   directo sobre un almacen en memoria). Este modulo no conoce el
 *   mecanismo de almacenamiento.
 * - `ahora`: `() => Date`.
 * - `transporte`: inyectado (Turnstile y Stripe).
 *
 * Devuelve `{ status, cuerpo }`.
 */
export async function manejarSolicitudSesion({
  cuerpo,
  cabeceraReferer,
  ipRemota,
  env,
  verificarCuota,
  ahora,
  transporte,
}) {
  const validacion = validarCuerpoSesion(cuerpo);
  if (!validacion.ok) {
    return { status: 400, cuerpo: { ok: false, codigo: "validacion", errores: validacion.errores } };
  }

  if (env.turnstileSecreto) {
    const turnstileOk = await verificarTurnstile(transporte, {
      token: cuerpo.turnstile_token,
      secreto: env.turnstileSecreto,
      ipRemota,
    });
    if (!turnstileOk) {
      return { status: 400, cuerpo: { ok: false, codigo: "turnstile_invalido" } };
    }
  }

  return crearSesionCheckout({
    ofertaId: cuerpo.oferta_id,
    visitorId: cuerpo.visitor_id,
    bump: cuerpo.bump,
    locale: cuerpo.locale,
    consentMarketing: cuerpo.consent_marketing,
    landingVersion: cuerpo.landing_version,
    params: cuerpo.params,
    cabeceraReferer,
    env,
    verificarCuota,
    ahora,
    transporte,
  });
}
