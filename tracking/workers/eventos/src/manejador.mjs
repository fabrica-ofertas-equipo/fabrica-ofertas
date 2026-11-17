// Logica pura del Worker `eventos` (docs/06 4.3): valida PageView/ViewContent
// y reenvia firmado (HMAC interno, docs/06 4.7) a `POST api/ingesta/evento`.

import { validarEvento } from "./validacion.mjs";
import { construirCabecerasInternas } from "../../_lib/src/hmac.mjs";
import { jsonCanonico } from "../../_lib/src/json_canonico.mjs";

/**
 * `event_id` cuando el cliente no manda uno. Con consentimiento es determinista (`tipo_visitor_ts`: un reintento
 * del mismo evento cae en el mismo id y el servicio lo trata como duplicado). SIN consentimiento el evento no es
 * atribuible: el `visitor_id` NO puede quedar dentro de la clave (revision de seguridad del panel), asi que el id
 * es aleatorio (un reintento se contaria dos veces en los agregados, a cambio de no vincular a la persona).
 */
function eventIdPorDefecto(cuerpo) {
  if (cuerpo.consentimiento === true) return `${cuerpo.tipo}_${cuerpo.visitor_id}_${cuerpo.ts}`;
  return `${cuerpo.tipo}_sa_${globalThis.crypto.randomUUID().replace(/-/g, "")}_${cuerpo.ts}`;
}

/**
 * Maneja `POST /api/ev`. Entradas:
 * - `cuerpo`: JSON ya parseado.
 * - `env`: `{ ingestSecret, ingestaEventoUrl }`.
 * - `ahora`: `() => Date`.
 * - `transporte`: inyectado.
 *
 * Devuelve `{ status, cuerpo }`.
 */
export async function manejarEvento({ cuerpo, env, ahora, transporte }) {
  const validacion = validarEvento(cuerpo);
  if (!validacion.ok) {
    return { status: 400, cuerpo: { ok: false, codigo: "validacion", errores: validacion.errores } };
  }
  if (!env?.ingestSecret || !env?.ingestaEventoUrl) {
    return { status: 500, cuerpo: { ok: false, codigo: "config_pendiente" } };
  }

  const evento = {
    event_id: cuerpo.event_id ?? eventIdPorDefecto(cuerpo),
    oferta_id: cuerpo.oferta_id,
    tipo: cuerpo.tipo,
    ts: cuerpo.ts,
    visitor_id: cuerpo.visitor_id,
    cid: cuerpo.cid ?? "desconocido",
    asid: cuerpo.asid ?? "desconocido",
    adid: cuerpo.adid ?? "desconocido",
    fuente: cuerpo.fuente,
    consentimiento: cuerpo.consentimiento,
  };
  const cuerpoExacto = jsonCanonico(evento);
  const ahoraIso = ahora().toISOString().replace(/\.\d+Z$/, "Z");
  const cabecerasFirma = await construirCabecerasInternas(env.ingestSecret, cuerpoExacto, ahoraIso);

  const respuesta = await transporte.solicitar("POST", env.ingestaEventoUrl, {
    cabeceras: { "content-type": "application/json", ...cabecerasFirma },
    cuerpo: cuerpoExacto,
  });

  if (respuesta.estado >= 200 && respuesta.estado < 300) {
    return { status: 202, cuerpo: { ok: true, codigo: "aceptado" } };
  }
  if (respuesta.estado === 409) {
    return { status: 200, cuerpo: { ok: true, codigo: "duplicado" } };
  }
  return { status: 502, cuerpo: { ok: false, codigo: "ingesta_error" } };
}
