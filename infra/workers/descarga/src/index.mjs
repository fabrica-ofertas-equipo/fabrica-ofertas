// Worker `descarga` (docs/06 4.3/4.6: "descargas.<dominio_infra>/d/*"). Unica ruta: GET /d/<sessionId>
// ?token=<token> (token firmado por `fulfill`, ver `enlace.mjs`). Cualquier otro metodo es 405.

import { crearBucketR2, crearContadorKv, manejarDescarga, sessionIdDeRuta } from "./logica.mjs";

function jsonRespuesta(cuerpo, estado) {
  return new Response(JSON.stringify(cuerpo), { status: estado, headers: { "content-type": "application/json" } });
}

/** Despacha una peticion HTTP contra la logica pura de arriba (testeable sin red real). */
export async function manejarPeticion(request, env, { ahora = () => new Date() } = {}) {
  if (request.method !== "GET") {
    return jsonRespuesta({ ok: false, codigo: "metodo_no_permitido" }, 405);
  }
  const url = new URL(request.url);
  const resultado = await manejarDescarga({
    sessionIdRuta: sessionIdDeRuta(url.pathname),
    token: url.searchParams.get("token") ?? "",
    secreto: env.DESCARGA_HMAC,
    ahora,
    contador: crearContadorKv(env.CONTADORES),
    bucket: crearBucketR2(env.BUCKET_PRODUCTOS),
  });
  if (resultado.status !== 200) {
    return jsonRespuesta(resultado.cuerpo, resultado.status);
  }
  const objeto = resultado.binario;
  return new Response(objeto.body ?? objeto, {
    status: 200,
    headers: {
      "content-type": objeto.httpMetadata?.contentType ?? "application/octet-stream",
      "content-disposition": "attachment",
    },
  });
}

export default {
  fetch(request, env) {
    return manejarPeticion(request, env);
  },
};
