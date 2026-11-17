import test from "node:test";
import assert from "node:assert/strict";

import { manejarSolicitudSesion } from "../src/manejador.mjs";
import { contarSesionYRegistrar } from "../src/limitador.mjs";
import { firmarHmacSha256Hex } from "../../_lib/src/hmac.mjs";
import { crearAlmacenEnMemoria } from "../../_lib/src/almacen_memoria.mjs";

const CATALOGO_HMAC_SECRETO = "catalogo-secreto";

const CATALOGO_OBJETO = {
  ofertas: {
    "OF-202611-01": {
      price_id: "price_front_v1",
      price_id_bump: "price_bump_v1",
      moneda: "EUR",
      success_url: "https://oferta.example/gracias",
      return_url: "https://oferta.example/landing",
      ids_meta: {
        campaign_id: "1000000001",
        adset_ids: ["2000000001"],
        ad_ids: ["3000000001"],
      },
    },
  },
};

async function construirEnv(overrides = {}) {
  const catalogoJson = JSON.stringify(CATALOGO_OBJETO);
  const catalogoFirma = await firmarHmacSha256Hex(CATALOGO_HMAC_SECRETO, catalogoJson);
  return {
    catalogoJson,
    catalogoFirma,
    catalogoHmacSecreto: CATALOGO_HMAC_SECRETO,
    turnstileSecreto: null, // desactivado por defecto en estas pruebas
    maxSesionesPorVisitante: 5,
    stripeRkCheckout: "rk_test_123",
    stripeApiVersion: "2026-10-28.endive",
    ...overrides,
  };
}

function crearTransporteFalso({ stripeUrl = "https://checkout.stripe.com/c/pay/cs_test_123" } = {}) {
  const llamadas = [];
  return {
    llamadas,
    async solicitar(metodo, url, opciones) {
      llamadas.push({ metodo, url, opciones });
      if (url.includes("checkout/sessions")) {
        return { estado: 200, cuerpo: JSON.stringify({ id: "cs_test_123", url: stripeUrl }) };
      }
      if (url.includes("turnstile")) {
        return { estado: 200, cuerpo: JSON.stringify({ success: true }) };
      }
      return { estado: 200, cuerpo: "{}" };
    },
  };
}

function cuerpoBase(overrides = {}) {
  return {
    oferta_id: "OF-202611-01",
    visitor_id: "v".repeat(20),
    bump: false,
    locale: "es-ES",
    consent_marketing: "1",
    landing_version: "v1",
    params: {
      utm_source: "meta",
      utm_medium: "paid",
      utm_campaign: "camp",
      utm_content: "cont",
      utm_term: "term",
      cid: "1000000001",
      asid: "2000000001",
      adid: "3000000001",
    },
    ...overrides,
  };
}

function verificadorCuotaSiempreOk() {
  return async () => ({ permitido: true, conteo: 1 });
}

test("sesion valida: 200 con url, metadata completa y precio del catalogo (no del cliente)", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesion({
    cuerpo: cuerpoBase({ price_id: "price_INVENTADO", monto: 1 }), // "precio manipulado"
    cabeceraReferer: "https://oferta.example/landing",
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 200);
  assert.equal(resultado.cuerpo.url, "https://checkout.stripe.com/c/pay/cs_test_123");

  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  assert.ok(llamadaStripe);
  const cuerpoEnviado = llamadaStripe.opciones.cuerpo;
  assert.ok(cuerpoEnviado.includes("line_items%5B0%5D%5Bprice%5D=price_front_v1"));
  assert.ok(!cuerpoEnviado.includes("price_INVENTADO"));
  assert.ok(cuerpoEnviado.includes("metadata%5Badid%5D=3000000001"));
});

test("metadata sin adid en la solicitud: la metadata final SIEMPRE incluye adid (desconocido)", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const cuerpo = cuerpoBase();
  delete cuerpo.params.adid;
  const resultado = await manejarSolicitudSesion({
    cuerpo,
    cabeceraReferer: "https://oferta.example/landing",
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 200);
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  assert.ok(llamadaStripe.opciones.cuerpo.includes("metadata%5Badid%5D=desconocido"));
});

test("adid fuera del catalogo: se reemplaza por 'desconocido' pero la sesion se crea", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const cuerpo = cuerpoBase({ params: { ...cuerpoBase().params, adid: "9999999999" } });
  const resultado = await manejarSolicitudSesion({
    cuerpo,
    cabeceraReferer: "https://oferta.example/landing",
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 200);
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  assert.ok(llamadaStripe.opciones.cuerpo.includes("metadata%5Badid%5D=desconocido"));
});

test("catalogo con firma HMAC invalida: rechaza sin llamar a Stripe", async () => {
  const env = await construirEnv({ catalogoFirma: "0".repeat(64) });
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesion({
    cuerpo: cuerpoBase(),
    cabeceraReferer: null,
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 500);
  assert.equal(resultado.cuerpo.codigo, "catalogo_invalido");
  assert.equal(transporte.llamadas.filter((l) => l.url.includes("checkout/sessions")).length, 0);
});

test("oferta_id valido pero ausente del catalogo: 404", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesion({
    cuerpo: cuerpoBase({ oferta_id: "OF-202611-99" }),
    cabeceraReferer: null,
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 404);
});

test("cuota excedida: 429 y no llama a Stripe", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesion({
    cuerpo: cuerpoBase(),
    cabeceraReferer: null,
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: async () => ({ permitido: false, conteo: 5, motivo: "cuota_excedida" }),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 429);
  assert.equal(transporte.llamadas.filter((l) => l.url.includes("checkout/sessions")).length, 0);
});

test("Turnstile invalido: 400 y no llama a Stripe", async () => {
  const env = await construirEnv({ turnstileSecreto: "secreto-turnstile" });
  const llamadas = [];
  const transporte = {
    llamadas,
    async solicitar(metodo, url, opciones) {
      llamadas.push({ metodo, url, opciones });
      if (url.includes("turnstile")) return { estado: 200, cuerpo: JSON.stringify({ success: false }) };
      return { estado: 200, cuerpo: JSON.stringify({ id: "cs", url: "https://x" }) };
    },
  };
  const resultado = await manejarSolicitudSesion({
    cuerpo: { ...cuerpoBase(), turnstile_token: "token-malo" },
    cabeceraReferer: null,
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 400);
  assert.equal(resultado.cuerpo.codigo, "turnstile_invalido");
  assert.equal(llamadas.filter((l) => l.url.includes("checkout/sessions")).length, 0);
});

test("Turnstile valido: la sesion se crea", async () => {
  const env = await construirEnv({ turnstileSecreto: "secreto-turnstile" });
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesion({
    cuerpo: { ...cuerpoBase(), turnstile_token: "token-bueno" },
    cabeceraReferer: null,
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte,
  });
  assert.equal(resultado.status, 200);
});

test("consent_marketing con valor fuera de '0'/'1': rechaza por validacion", async () => {
  const env = await construirEnv();
  const resultado = await manejarSolicitudSesion({
    cuerpo: cuerpoBase({ consent_marketing: "si" }),
    cabeceraReferer: null,
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte: crearTransporteFalso(),
  });
  assert.equal(resultado.status, 400);
  assert.ok(resultado.cuerpo.errores.includes("consent_marketing_invalido"));
});

test("fbp con formato invalido: rechaza por validacion", async () => {
  const env = await construirEnv();
  const resultado = await manejarSolicitudSesion({
    cuerpo: cuerpoBase({ params: { ...cuerpoBase().params, fbp: "no-es-fbp" } }),
    cabeceraReferer: null,
    ipRemota: "1.2.3.4",
    env,
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte: crearTransporteFalso(),
  });
  assert.equal(resultado.status, 400);
  assert.ok(resultado.cuerpo.errores.includes("fbp_invalido"));
});

test("integracion con limitador real (no mock): la sexta sesion del dia se rechaza", async () => {
  const env = await construirEnv({ maxSesionesPorVisitante: 5 });
  const almacen = crearAlmacenEnMemoria();
  const verificarCuota = (datos) => contarSesionYRegistrar(almacen, datos);
  const transporte = crearTransporteFalso();
  let ultimo;
  for (let i = 0; i < 6; i += 1) {
    ultimo = await manejarSolicitudSesion({
      cuerpo: cuerpoBase(),
      cabeceraReferer: null,
      ipRemota: "1.2.3.4",
      env,
      verificarCuota,
      ahora: () => new Date("2026-11-06T12:00:00Z"),
      transporte,
    });
  }
  assert.equal(ultimo.status, 429);
});
