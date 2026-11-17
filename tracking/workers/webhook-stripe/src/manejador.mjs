// Logica pura del Worker `webhook-stripe` (docs/06 4.3, N14, 4.8). Firma,
// tolerancia, dedupe por `event.id` y por `(tipo, objeto_id)`, encolado a
// `fulfill` (aqui solo se REGISTRA la intencion: el Worker `fulfill` es de
// B7 y no es parte de este alcance) y disparo de `capi.enviarPurchaseSiCorresponde`
// cuando corresponde. Sin red directa: toda llamada pasa por `transporte`.

import { verificarFirmaStripe } from "./firma.mjs";
import { enviarPurchaseSiCorresponde } from "../../capi/src/capi.mjs";

/**
 * Extrae `{ tipo, objetoId, sessionId, pagado }` de un evento de Stripe ya
 * parseado (formato snapshot, docs/07 2.3: `data.object` completo).
 */
function describirEvento(evento) {
  const tipo = evento?.type;
  const objeto = evento?.data?.object ?? {};
  if (tipo === "checkout.session.completed" || tipo === "checkout.session.async_payment_succeeded") {
    return {
      tipo,
      objetoId: objeto.id,
      sessionId: objeto.id,
      pagado: objeto.payment_status === "paid",
      metadata: objeto.metadata ?? {},
      amountTotal: objeto.amount_total,
      currency: objeto.currency,
    };
  }
  if (tipo === "charge.refunded") {
    return { tipo, objetoId: objeto.id, sessionId: null, pagado: false, metadata: {} };
  }
  return { tipo, objetoId: objeto.id ?? null, sessionId: null, pagado: false, metadata: {} };
}

/**
 * Maneja una entrega de webhook completa. Entradas:
 * - `cabeceraFirma`, `cuerpoCrudo`: tal como llegaron (sin tocar).
 * - `secretoWhsec`, `toleranciaSeg`: configuracion inyectada (nunca fija en el codigo).
 * - `registrarDedupe({eventId, tipo, objetoId}) -> Promise<{duplicado}>`: quien
 *   resuelve el dedupe real (en produccion, un `fetch` a la Durable Object
 *   `DedupeSesion`, que serializa con su propio cerrojo; en pruebas, una
 *   funcion directa sobre `dedupe.registrarSiEsNuevo` con un almacen en
 *   memoria). Este modulo no conoce el mecanismo de almacenamiento.
 * - `ahora`: `() => Date` inyectable.
 * - `configCapi`: datos para `enviarPurchaseSiCorresponde` (datasetId, token, apiVersion, testEventCode).
 * - `transporte`: inyectado, nunca `fetch` global.
 *
 * Devuelve `{ status, cuerpo }`.
 */
export async function manejarWebhookStripe({
  cabeceraFirma,
  cuerpoCrudo,
  secretoWhsec,
  toleranciaSeg,
  registrarDedupe,
  ahora,
  configCapi,
  transporte,
}) {
  const ahoraDate = ahora();
  const verificacion = await verificarFirmaStripe({
    cabeceraFirma,
    cuerpoCrudo,
    secretoWhsec,
    ahoraEpochSeg: Math.floor(ahoraDate.getTime() / 1000),
    toleranciaSeg,
  });
  if (!verificacion.valida) {
    return { status: 400, cuerpo: { ok: false, codigo: verificacion.motivo } };
  }

  let evento;
  try {
    evento = JSON.parse(cuerpoCrudo);
  } catch {
    return { status: 400, cuerpo: { ok: false, codigo: "cuerpo_invalido" } };
  }
  if (typeof evento?.id !== "string" || !evento.id) {
    return { status: 400, cuerpo: { ok: false, codigo: "event_id_ausente" } };
  }

  const descrito = describirEvento(evento);
  if (!descrito.objetoId) {
    return { status: 400, cuerpo: { ok: false, codigo: "objeto_id_ausente" } };
  }

  const { duplicado } = await registrarDedupe({
    eventId: evento.id,
    tipo: descrito.tipo,
    objetoId: descrito.objetoId,
  });
  if (duplicado) {
    return { status: 200, cuerpo: { ok: true, codigo: "duplicado" } };
  }

  const esCompletado =
    descrito.tipo === "checkout.session.completed" ||
    descrito.tipo === "checkout.session.async_payment_succeeded";
  if (!esCompletado || !descrito.pagado) {
    // Otros tipos (p. ej. charge.refunded) o sesiones no pagadas: se registra
    // la recepcion pero no hay entrega ni CAPI que disparar desde este Worker.
    return { status: 200, cuerpo: { ok: true, codigo: "recibido" } };
  }

  // "encolado" = la intencion de entrega para `fulfill` (B7); este Worker no
  // escribe en su almacen (fuera de alcance), solo deja constancia en la respuesta.
  let capiResultado = { enviado: false, motivo: "sin_configuracion_capi" };
  if (configCapi) {
    const metadata = descrito.metadata;
    capiResultado = await enviarPurchaseSiCorresponde({
      consentMarketing: metadata.consent_marketing,
      sessionId: descrito.sessionId,
      eventTimeIso: ahoraDate.toISOString().replace(/\.\d+Z$/, "Z"),
      eventSourceUrl: metadata.event_source_url,
      fbp: metadata.fbp,
      fbc: metadata.fbc,
      // `valorDecimal`/`moneda` quedan sin convertir en este alcance (el
      // exponente ISO 4217 vive en Python, CT): ver "Pedidos" en el README.
      valorDecimal: configCapi.valorDecimal,
      moneda: configCapi.moneda,
      datasetId: configCapi.datasetId,
      token: configCapi.token,
      apiVersion: configCapi.apiVersion,
      testEventCode: configCapi.testEventCode,
      ahora: ahoraDate,
      transporte,
    });
  }

  return {
    status: 200,
    cuerpo: { ok: true, codigo: "encolado", capi: capiResultado.motivo ?? "enviado" },
  };
}
