// Worker `crear-sesion` (docs/06 4.3). Entrada HTTP real: delega la
// decision a `manejador.mjs` (logica pura, probada con `node --test`). La
// cuota diaria por visitante vive en la Durable Object `CuotaVisitante`.
//
// La limitacion de tasa por IP/zona y el WAF se configuran en el panel de
// Cloudflare (infra, B8): no son codigo de este Worker (ver README "Pedidos").

import { manejarSolicitudSesion } from "./manejador.mjs";
import { manejarSolicitudSesionFormulario } from "./formulario.mjs";
import { contarSesionYRegistrar } from "./limitador.mjs";

/** `"a,b , c"` -> `["a","b","c"]` (config no secreta, comentada en wrangler.toml). */
function listaDesdeComa(valor) {
  return (valor ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/** Pagina de error minima para el modo formulario: NUNCA refleja la entrada del usuario (`codigo` sale de un enum interno fijo). */
function paginaErrorFormulario(codigo) {
  return `<!doctype html><html lang="es"><meta charset="utf-8"><title>No se pudo iniciar el pago</title><body><p>No se pudo iniciar el pago (${codigo}).</p></body></html>`;
}

export class CuotaVisitante {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    const { visitorId, diaUtc, limite } = await request.json();
    const resultado = await contarSesionYRegistrar(this.state.storage, { visitorId, diaUtc, limite });
    return new Response(JSON.stringify(resultado), {
      headers: { "content-type": "application/json" },
    });
  }
}

/** `verificarCuota` real: un `fetch` interno a la Durable Object por visitante. */
function crearVerificadorCuota(env, visitorId) {
  const id = env.CUOTA_VISITANTE.idFromName(visitorId);
  const stub = env.CUOTA_VISITANTE.get(id);
  return async (datos) => {
    const respuesta = await stub.fetch("https://cuota-visitante.interno/contar", {
      method: "POST",
      body: JSON.stringify(datos),
    });
    return respuesta.json();
  };
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405 });
    }
    const cuerpoMaxBytes = Number.parseInt(env.CUERPO_MAX_BYTES ?? "", 10);
    if (Number.isInteger(cuerpoMaxBytes) && cuerpoMaxBytes > 0) {
      const contentLength = Number.parseInt(request.headers.get("content-length") ?? "", 10);
      if (Number.isInteger(contentLength) && contentLength > cuerpoMaxBytes) {
        return new Response(JSON.stringify({ ok: false, codigo: "cuerpo_demasiado_grande" }), {
          status: 413,
          headers: { "content-type": "application/json" },
        });
      }
    }

    const contentType = request.headers.get("content-type") ?? "";
    let cuerpo = null;
    if (!contentType.includes("application/x-www-form-urlencoded")) {
      try {
        cuerpo = await request.json();
      } catch {
        return new Response(JSON.stringify({ ok: false, codigo: "cuerpo_invalido" }), {
          status: 400,
          headers: { "content-type": "application/json" },
        });
      }
    }

    const transporte = {
      async solicitar(metodo, url, opciones) {
        const respuesta = await fetch(url, {
          method: metodo,
          headers: opciones?.cabeceras,
          body: opciones?.cuerpo,
        });
        return { estado: respuesta.status, cuerpo: await respuesta.text() };
      },
    };
    const envComun = {
      catalogoJson: env.CATALOGO_JSON,
      catalogoFirma: env.CATALOGO_FIRMA,
      catalogoHmacSecreto: env.CATALOGO_HMAC,
      turnstileSecreto: env.TURNSTILE_SECRET,
      maxSesionesPorVisitante: Number.parseInt(env.MAX_SESIONES_POR_VISITANTE ?? "", 10),
      stripeRkCheckout: env.STRIPE_RK_CHECKOUT,
      stripeApiVersion: env.STRIPE_API_VERSION,
      origenesPermitidos: listaDesdeComa(env.ORIGENES_PERMITIDOS),
      localesRenunciaRequerida: listaDesdeComa(env.LOCALES_RENUNCIA_REQUERIDA),
    };

    if (contentType.includes("application/x-www-form-urlencoded")) {
      const texto = await request.text();
      const campos = Object.fromEntries(new URLSearchParams(texto).entries());
      const resultado = await manejarSolicitudSesionFormulario({
        campos,
        cabeceraCookie: request.headers.get("cookie"),
        cabeceraSecFetchSite: request.headers.get("sec-fetch-site"),
        cabeceraOrigin: request.headers.get("origin"),
        cabeceraReferer: request.headers.get("referer"),
        env: envComun,
        verificarCuota: crearVerificadorCuota(env, campos?.oferta_id ?? "desconocido"),
        ahora: () => new Date(),
        transporte,
      });
      if (resultado.location) {
        return new Response(null, { status: 303, headers: { Location: resultado.location } });
      }
      return new Response(paginaErrorFormulario(resultado.codigo), {
        status: resultado.status,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }

    const resultado = await manejarSolicitudSesion({
      cuerpo,
      cabeceraReferer: request.headers.get("referer"),
      ipRemota: request.headers.get("cf-connecting-ip"),
      env: envComun,
      verificarCuota: crearVerificadorCuota(env, cuerpo?.visitor_id ?? "desconocido"),
      ahora: () => new Date(),
      transporte,
    });

    return new Response(JSON.stringify(resultado.cuerpo), {
      status: resultado.status,
      headers: { "content-type": "application/json" },
    });
  },
};
