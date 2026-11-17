// Worker `webhook-stripe` (docs/06 4.3). Entrada HTTP real: delega toda la
// decision a `manejador.mjs` (logica pura, probada con `node --test` sin
// red). La Durable Object `DedupeSesion` envuelve `dedupe.mjs` con
// almacenamiento persistente real y un cerrojo por instancia, para que dos
// entregas concurrentes del mismo `session_id` se resuelvan una por una
// (ver `_lib/src/cerrojo.mjs`).

import { manejarWebhookStripe } from "./manejador.mjs";
import { registrarSiEsNuevo } from "./dedupe.mjs";
import { crearCerrojo } from "../../_lib/src/cerrojo.mjs";

export class DedupeSesion {
  constructor(state) {
    this.state = state;
    this.cerrojo = crearCerrojo();
  }

  async fetch(request) {
    const claves = await request.json();
    const resultado = await this.cerrojo.ejecutar(() =>
      registrarSiEsNuevo(this.state.storage, claves),
    );
    return new Response(JSON.stringify(resultado), {
      headers: { "content-type": "application/json" },
    });
  }
}

/** `registrarDedupe` real: un `fetch` interno a la Durable Object por `session_id`. */
function crearRegistradorDedupe(env, sessionId) {
  const id = env.DEDUPE_SESION.idFromName(sessionId);
  const stub = env.DEDUPE_SESION.get(id);
  return async (claves) => {
    const respuesta = await stub.fetch("https://dedupe-sesion.interno/registrar", {
      method: "POST",
      body: JSON.stringify(claves),
    });
    return respuesta.json();
  };
}

function extraerSessionIdAproximado(cuerpoCrudo) {
  try {
    const posible = JSON.parse(cuerpoCrudo);
    return posible?.data?.object?.id ?? "sin-sesion";
  } catch {
    return "sin-sesion"; // manejador.mjs rechaza igual el cuerpo invalido con 400
  }
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405 });
    }
    const cabeceraFirma = request.headers.get("Stripe-Signature");
    const cuerpoCrudo = await request.text();
    const toleranciaSeg = Number.parseInt(env.STRIPE_TOLERANCIA_SEG ?? "", 10);
    const modoProduccion = env.FABRICA_ENTORNO === "produccion";
    const secretoWhsec = modoProduccion ? env.STRIPE_WHSEC_LIVE : env.STRIPE_WHSEC_TEST;

    if (!secretoWhsec) {
      return new Response(JSON.stringify({ ok: false, codigo: "config_pendiente" }), {
        status: 500,
        headers: { "content-type": "application/json" },
      });
    }

    const sessionIdAproximado = extraerSessionIdAproximado(cuerpoCrudo);
    const registrarDedupe = crearRegistradorDedupe(env, sessionIdAproximado);

    const resultado = await manejarWebhookStripe({
      cabeceraFirma,
      cuerpoCrudo,
      secretoWhsec,
      toleranciaSeg,
      registrarDedupe,
      ahora: () => new Date(),
      configCapi: env.CAPI_DATASET_ID
        ? {
            datasetId: env.CAPI_DATASET_ID,
            token: env.META_CAPI_TOKEN,
            apiVersion: env.META_API_VERSION,
            testEventCode: env.META_TEST_EVENT_CODE,
          }
        : null,
      transporte: {
        async solicitar(metodo, url, opciones) {
          const respuesta = await fetch(url, {
            method: metodo,
            headers: opciones?.cabeceras,
            body: opciones?.cuerpo,
          });
          return { estado: respuesta.status, cuerpo: await respuesta.text() };
        },
      },
    });

    return new Response(JSON.stringify(resultado.cuerpo), {
      status: resultado.status,
      headers: { "content-type": "application/json" },
    });
  },
};
