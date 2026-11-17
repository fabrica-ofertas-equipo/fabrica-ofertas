// Logica pura del Worker `fulfill` (docs/06 4.6/4.7): encolado por `webhook-stripe` cuando la sesion
// esta `paid`. Si no hay entrega previa (dedupe por `session_id`), genera el enlace firmado
// (`enlace.mjs`), "envia" el correo transaccional (proveedor inyectado) y hace `POST /ingesta/entrega`
// al motor (transporte inyectado). Sin red directa, sin datos personales en el cuerpo que viaja a la
// API (el email solo llega al proveedor de correo, nunca a `/ingesta/entrega`).

import { firmarEnlace } from "./enlace.mjs";

const HORAS_POR_DIA = 24;
const MINUTOS_POR_HORA = 60;
const SEGUNDOS_POR_MINUTO = 60;
const MS_POR_SEGUNDO = 1000;
const MS_POR_DIA = HORAS_POR_DIA * MINUTOS_POR_HORA * SEGUNDOS_POR_MINUTO * MS_POR_SEGUNDO;

function isoZ(fecha) {
  return fecha.toISOString().replace(/\.\d+Z$/, "Z");
}

/**
 * Maneja una entrega pagada. Entradas:
 * - `sessionId`, `ofertaId`, `productoVersion`, `productoSha256`: de la sesion de Stripe / del
 *   paquete publicado (`postcompra.publicar_producto`).
 * - `email`: direccion real del comprador (nunca viaja a `postEntregaApi`).
 * - `venceDias`, `maxDescargas`: de `entrega.schema.json` del producto (o parametros).
 * - `secretoEnlace`: `DESCARGA_HMAC`.
 * - `yaEntregado(sessionId) -> Promise<boolean>` / `marcarEntregado(sessionId) -> Promise<void>`:
 *   dedupe inyectado (en produccion, KV; en pruebas, un Map).
 * - `enviarCorreo({ email, sessionId, token, venceEn }) -> Promise<object>`.
 * - `postEntregaApi(cuerpo) -> Promise<object>`: `POST /ingesta/entrega` (docs/06 4.7).
 * - `ahora`: `() => Date` inyectable.
 *
 * Devuelve `{ status, cuerpo }`.
 */
export async function manejarEntregaPagada({
  sessionId,
  ofertaId,
  productoVersion,
  productoSha256,
  email,
  venceDias,
  maxDescargas,
  secretoEnlace,
  yaEntregado,
  marcarEntregado,
  enviarCorreo,
  postEntregaApi,
  ahora,
}) {
  if (typeof sessionId !== "string" || !sessionId) {
    return { status: 400, cuerpo: { ok: false, codigo: "session_id_ausente" } };
  }
  if (await yaEntregado(sessionId)) {
    return { status: 200, cuerpo: { ok: true, codigo: "duplicado" } };
  }

  const ahoraDate = ahora();
  const venceEn = isoZ(new Date(ahoraDate.getTime() + venceDias * MS_POR_DIA));
  const token = await firmarEnlace(
    { sessionId, productoSha256, productoVersion, venceEn, maxDescargas },
    secretoEnlace,
  );

  // Se marca ANTES de enviar: dos entregas concurrentes para la misma sesion no deben mandar dos
  // correos ni dos POST a la API (el dedupe real, con cerrojo, lo aporta quien inyecta `yaEntregado`
  // y `marcarEntregado`, igual que `webhook-stripe` con su Durable Object; ver el Worker `index.mjs`).
  await marcarEntregado(sessionId);

  const correoResultado = await enviarCorreo({ email, sessionId, token, venceEn });
  const entregaResultado = await postEntregaApi({
    checkout_session_id: sessionId,
    oferta_id: ofertaId,
    estado: "entregado",
    intento: 1,
    producto_sha256: productoSha256,
    ts: isoZ(ahoraDate),
  });

  return {
    status: 200,
    cuerpo: {
      ok: true,
      codigo: "entregado",
      enlace: { vence_en: venceEn, max_descargas: maxDescargas },
      correo: correoResultado?.codigo ?? "enviado",
      api: entregaResultado?.codigo ?? "ok",
    },
  };
}
