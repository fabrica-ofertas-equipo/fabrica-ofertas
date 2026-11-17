import test from "node:test";
import assert from "node:assert/strict";

import worker from "../src/index.mjs";
import { firmarHmacSha256Hex } from "../../_lib/src/hmac.mjs";
import { CuotaVisitante } from "../src/index.mjs";
import { crearAlmacenEnMemoria } from "../../_lib/src/almacen_memoria.mjs";

const CATALOGO_HMAC_SECRETO = "catalogo-secreto";
const CATALOGO_OBJETO = {
  ofertas: {
    "OF-202611-01": {
      price_id: "price_front_v1",
      price_id_bump: null,
      moneda: "EUR",
      success_url: "https://oferta.example/gracias",
      return_url: "https://oferta.example/comprar",
      ids_meta: { campaign_id: "1", adset_ids: [], ad_ids: [] },
    },
  },
};

function crearNamespaceCuotaFalso() {
  const instancia = new CuotaVisitante({ storage: crearAlmacenEnMemoria() });
  return {
    idFromName(nombre) {
      return nombre;
    },
    get() {
      return { fetch: (url, init) => instancia.fetch(new Request(url, init)) };
    },
  };
}

async function construirEnv() {
  const catalogoJson = JSON.stringify(CATALOGO_OBJETO);
  const catalogoFirma = await firmarHmacSha256Hex(CATALOGO_HMAC_SECRETO, catalogoJson);
  return {
    CATALOGO_JSON: catalogoJson,
    CATALOGO_FIRMA: catalogoFirma,
    CATALOGO_HMAC: CATALOGO_HMAC_SECRETO,
    MAX_SESIONES_POR_VISITANTE: "5",
    STRIPE_RK_CHECKOUT: "rk_test_123",
    STRIPE_API_VERSION: "2026-10-28.endive",
    ORIGENES_PERMITIDOS: "https://oferta.example",
    LOCALES_RENUNCIA_REQUERIDA: "es-ES",
    CUOTA_VISITANTE: crearNamespaceCuotaFalso(),
  };
}

/** Reemplaza `globalThis.fetch` (lo usa `transporte.solicitar` real de index.mjs) por un doble sin red. */
function instalarFetchFalso() {
  const original = globalThis.fetch;
  const llamadas = [];
  globalThis.fetch = async (url, init) => {
    llamadas.push({ url: String(url), init });
    if (String(url).includes("checkout/sessions")) {
      return new Response(JSON.stringify({ id: "cs_test_123", url: "https://checkout.stripe.com/c/pay/cs_test_123" }), {
        status: 200,
      });
    }
    return new Response("{}", { status: 200 });
  };
  return {
    llamadas,
    restaurar() {
      globalThis.fetch = original;
    },
  };
}

test("GET /api/sesion: 405 sin tocar el catalogo ni la red", async () => {
  const falso = instalarFetchFalso();
  try {
    const env = await construirEnv();
    const respuesta = await worker.fetch(new Request("https://oferta.example/api/sesion", { method: "GET" }), env);
    assert.equal(respuesta.status, 405);
    assert.equal(falso.llamadas.length, 0);
  } finally {
    falso.restaurar();
  }
});

test("POST /api/sesion de extremo a extremo (formulario, mismo origen): 303 con Location de Stripe", async () => {
  const falso = instalarFetchFalso();
  try {
    const env = await construirEnv();
    const cuerpo = new URLSearchParams({
      oferta_id: "OF-202611-01",
      locale: "es-ES",
      renuncia_desistimiento: "on",
    }).toString();
    const respuesta = await worker.fetch(
      new Request("https://oferta.example/api/sesion", {
        method: "POST",
        headers: {
          "content-type": "application/x-www-form-urlencoded",
          "sec-fetch-site": "same-origin",
        },
        body: cuerpo,
      }),
      env,
    );
    assert.equal(respuesta.status, 303);
    assert.equal(respuesta.headers.get("location"), "https://checkout.stripe.com/c/pay/cs_test_123");
    const bodyTexto = await respuesta.text();
    assert.equal(bodyTexto, "");
  } finally {
    falso.restaurar();
  }
});

test("POST /api/sesion de extremo a extremo (formulario, origen cruzado): 403 y pagina sin reflejar entrada", async () => {
  const falso = instalarFetchFalso();
  try {
    const env = await construirEnv();
    const cuerpo = new URLSearchParams({
      oferta_id: "OF-202611-01",
      locale: "es-ES",
      renuncia_desistimiento: "on",
    }).toString();
    const respuesta = await worker.fetch(
      new Request("https://oferta.example/api/sesion", {
        method: "POST",
        headers: {
          "content-type": "application/x-www-form-urlencoded",
          "sec-fetch-site": "cross-site",
        },
        body: cuerpo,
      }),
      env,
    );
    assert.equal(respuesta.status, 403);
    const bodyTexto = await respuesta.text();
    assert.ok(!bodyTexto.includes("OF-202611-01"), "la pagina de error no debe reflejar la entrada del usuario");
    assert.equal(falso.llamadas.length, 0);
  } finally {
    falso.restaurar();
  }
});
