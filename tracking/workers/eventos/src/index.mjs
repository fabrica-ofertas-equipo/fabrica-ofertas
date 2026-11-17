// Worker `eventos` (docs/06 4.3). Entrada HTTP real: delega la decision a
// `manejador.mjs` (logica pura, probada con `node --test`).

import { manejarEvento } from "./manejador.mjs";

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405 });
    }
    let cuerpo;
    try {
      cuerpo = await request.json();
    } catch {
      return new Response(JSON.stringify({ ok: false, codigo: "cuerpo_invalido" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      });
    }

    const resultado = await manejarEvento({
      cuerpo,
      env: {
        ingestSecret: env.INGEST_HMAC_SECRET,
        ingestaEventoUrl: env.INGESTA_EVENTO_URL,
      },
      ahora: () => new Date(),
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
