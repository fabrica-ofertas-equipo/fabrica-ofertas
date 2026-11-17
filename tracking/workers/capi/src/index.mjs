// `capi` es un modulo interno (docs/06 4.3: "capi | modulo interno"): no
// expone una ruta publica. Este archivo es el punto de entrada que exige
// wrangler para desplegarlo con sus propios secretos aislados
// (`META_CAPI_TOKEN__<oferta_id>`, `META_API_VERSION`), pero la logica real
// vive en `capi.mjs` y se consume por importacion directa desde otros
// Workers del mismo repositorio (p. ej. `webhook-stripe`).
export * from "./capi.mjs";

export default {
  async fetch() {
    return new Response("capi: modulo interno, sin ruta publica", { status: 404 });
  },
};
