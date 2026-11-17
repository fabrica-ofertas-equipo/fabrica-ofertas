import test from "node:test";
import assert from "node:assert/strict";

import { manejarSolicitudSesionFormulario } from "../src/formulario.mjs";
import { paramsDeCookie } from "../src/cookies.mjs";
import { firmarHmacSha256Hex } from "../../_lib/src/hmac.mjs";

const CATALOGO_HMAC_SECRETO = "catalogo-secreto";
const PATRON_VISITOR_ID = /^[A-Za-z0-9_-]{16,64}$/;

const CATALOGO_OBJETO = {
  ofertas: {
    "OF-202611-01": {
      price_id: "price_front_v1",
      price_id_bump: "price_bump_v1",
      moneda: "EUR",
      success_url: "https://oferta.example/gracias",
      return_url: "https://oferta.example/comprar",
      landing_version: "v3",
      ids_meta: { campaign_id: "1000000001", adset_ids: ["2000000001"], ad_ids: ["3000000001"] },
    },
    "OF-202611-02": {
      price_id: "price_front_v2",
      price_id_bump: null,
      moneda: "EUR",
      success_url: "https://oferta.example/gracias",
      return_url: "https://oferta.example/comprar",
      renuncia: { requerido: false, texto_version: "v9" },
      ids_meta: { campaign_id: "1", adset_ids: [], ad_ids: [] },
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
    turnstileSecreto: null,
    maxSesionesPorVisitante: 5,
    stripeRkCheckout: "rk_test_123",
    stripeApiVersion: "2026-10-28.endive",
    origenesPermitidos: ["https://oferta.example"],
    localesRenunciaRequerida: ["es-ES", "de-DE"],
    ...overrides,
  };
}

function crearTransporteFalso(opts) {
  const o = opts || {};
  const stripeUrl = o.stripeUrl || "https://checkout.stripe.com/c/pay/cs_test_123";
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

function camposBase(overrides = {}) {
  return { oferta_id: "OF-202611-01", locale: "es-ES", renuncia_desistimiento: "on", ...overrides };
}

function verificadorCuotaSiempreOk() {
  return async () => ({ permitido: true, conteo: 1 });
}

function cabeceraCookie(opts) {
  const o = opts || {};
  const partes = [];
  if (o.visitorId !== undefined) partes.push("fab_vid=" + encodeURIComponent(o.visitorId));
  if (o.attr !== undefined) {
    // Formato canonico: k=v&k=v con cada valor percent-encoded (un string se manda tal cual, para casos malformados).
    partes.push("fab_attr=" + (typeof o.attr === "string" ? o.attr
      : Object.entries(o.attr).map(([k, v]) => k + "=" + encodeURIComponent(v)).join("&")));
  }
  if (o.fbp !== undefined) partes.push("_fbp=" + encodeURIComponent(o.fbp));
  if (o.fbc !== undefined) partes.push("_fbc=" + encodeURIComponent(o.fbc));
  return partes.join("; ");
}

function argsBase(overrides = {}) {
  return {
    campos: camposBase(),
    cabeceraCookie: undefined,
    cabeceraSecFetchSite: "same-origin",
    cabeceraOrigin: undefined,
    cabeceraReferer: "https://oferta.example/comprar",
    verificarCuota: verificadorCuotaSiempreOk(),
    ahora: () => new Date("2026-11-06T12:00:00Z"),
    transporte: crearTransporteFalso(),
    ...overrides,
  };
}

test("formulario valido sin cookies: 303 a Stripe, visitor_id aleatorio y metadata completa", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(argsBase({ env, transporte }));
  assert.equal(resultado.status, 303);
  assert.equal(resultado.location, "https://checkout.stripe.com/c/pay/cs_test_123");
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  assert.ok(llamadaStripe);
  const cuerpoEnviado = llamadaStripe.opciones.cuerpo;
  const m = cuerpoEnviado.match(/client_reference_id=([^&]+)/);
  assert.ok(m, "client_reference_id presente");
  assert.match(decodeURIComponent(m[1]), PATRON_VISITOR_ID);
  assert.ok(cuerpoEnviado.includes("metadata%5Bconsent_marketing%5D=0"));
  assert.ok(cuerpoEnviado.includes("metadata%5Blanding_version%5D=v3"));
  assert.ok(cuerpoEnviado.includes("metadata%5Brenuncia_texto_version%5D=desconocida"));
});

test("formulario valido con cookies fab_vid/fab_attr/_fbp/_fbc: usa el visitor_id y los params de las cookies", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const visitorId = "v".repeat(20);
  const cookie = cabeceraCookie({
    visitorId: visitorId,
    attr: { utm_source: "meta", utm_medium: "paid", cid: "1000000001", asid: "2000000001", adid: "3000000001" },
    fbp: "fb.1.1234567890123.998877",
    fbc: "fb.1.1234567890123.algo",
  });
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, cabeceraCookie: cookie, campos: camposBase({ renuncia_desistimiento: "on" }) }),
  );
  assert.equal(resultado.status, 303);
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  const cuerpoEnviado = llamadaStripe.opciones.cuerpo;
  assert.ok(cuerpoEnviado.includes("client_reference_id=" + visitorId));
  assert.ok(cuerpoEnviado.includes("metadata%5Bconsent_marketing%5D=1"));
  assert.ok(cuerpoEnviado.includes("metadata%5Badid%5D=3000000001"));
  assert.ok(cuerpoEnviado.includes("metadata%5Bfbp%5D=fb.1.1234567890123.998877"));
});

test("locale UE sin casilla de renuncia marcada: 400 renuncia_requerida y no llama a Stripe", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, campos: camposBase({ renuncia_desistimiento: undefined }) }),
  );
  assert.equal(resultado.status, 400);
  assert.equal(resultado.codigo, "renuncia_requerida");
  assert.equal(transporte.llamadas.filter((l) => l.url.includes("checkout/sessions")).length, 0);
});

test("locale no-UE sin renuncia: no la exige, la sesion se crea", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, campos: camposBase({ locale: "en-US", renuncia_desistimiento: undefined }) }),
  );
  assert.equal(resultado.status, 303);
});

test("casilla de renuncia marcada: deja renuncia_ts y renuncia_texto_version en la metadata", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(argsBase({ env, transporte }));
  assert.equal(resultado.status, 303);
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  const cuerpoEnviado = llamadaStripe.opciones.cuerpo;
  assert.ok(cuerpoEnviado.includes("metadata%5Brenuncia_ts%5D=2026-11-06T12%3A00%3A00Z"));
  assert.ok(cuerpoEnviado.includes("metadata%5Brenuncia_texto_version%5D=desconocida"));
});

test("el catalogo (renuncia.requerido=false) anula la lista de locales de configuracion", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, campos: { oferta_id: "OF-202611-02", locale: "es-ES" } }),
  );
  assert.equal(resultado.status, 303);
});

test("Sec-Fetch-Site: cross-site: 403 y no llama a Stripe", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, cabeceraSecFetchSite: "cross-site" }),
  );
  assert.equal(resultado.status, 403);
  assert.equal(resultado.codigo, "origen_invalido");
  assert.equal(transporte.llamadas.length, 0);
});

test("sin Sec-Fetch-Site, Origin distinto al configurado: 403", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, cabeceraSecFetchSite: undefined, cabeceraOrigin: "https://atacante.example" }),
  );
  assert.equal(resultado.status, 403);
});

test("sin Sec-Fetch-Site y sin Origin (ambos ausentes): 403", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, cabeceraSecFetchSite: undefined, cabeceraOrigin: undefined }),
  );
  assert.equal(resultado.status, 403);
});

test("sin Sec-Fetch-Site pero con Origin configurado: pasa el chequeo de origen", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, cabeceraSecFetchSite: undefined, cabeceraOrigin: "https://oferta.example" }),
  );
  assert.equal(resultado.status, 303);
});

test("campo extra en el formulario: 400 y no llama a Stripe", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, campos: camposBase({ email: "intruso@example.com" }) }),
  );
  assert.equal(resultado.status, 400);
  assert.equal(resultado.codigo, "validacion");
  assert.equal(transporte.llamadas.length, 0);
});

test("Turnstile deshabilitado: cf-turnstile-response presente es un campo extra: 400", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, campos: camposBase({ "cf-turnstile-response": "token" }) }),
  );
  assert.equal(resultado.status, 400);
  assert.equal(resultado.codigo, "validacion");
});

test("cookie fab_vid malformada: se ignora (visitor_id aleatorio, no rechaza la solicitud)", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, cabeceraCookie: "fab_vid=corto" }),
  );
  assert.equal(resultado.status, 303);
});

test("cookie fab_attr malformada (sin k=v): se ignora, params por defecto desconocido", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, cabeceraCookie: "fab_attr=no-es-un-par" }),
  );
  assert.equal(resultado.status, 303);
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  assert.ok(llamadaStripe.opciones.cuerpo.includes("metadata%5Badid%5D=desconocido"));
});

test("fab_attr canonico (k=v&k=v): utm y ids validos pasan; claves ajenas, ids invalidos y fbclid se descartan", () => {
  const params = paramsDeCookie({ fab_attr: "utm_source=meta&utm_medium=paid%20social&cid=1000000001&asid=12&adid=3000000001&fbclid=IwAR0&evil=1&utm_term=" });
  assert.deepEqual(params, { utm_source: "meta", utm_medium: "paid social", cid: "1000000001", adid: "3000000001" });
});

test("fab_attr: sobre 400 bytes se ignora entera; justo en 400 se acepta; JSON viejo no se interpreta", () => {
  const relleno = "a".repeat(400 - "utm_source=".length);
  assert.deepEqual(paramsDeCookie({ fab_attr: "utm_source=" + relleno }), { utm_source: relleno });
  assert.deepEqual(paramsDeCookie({ fab_attr: "utm_source=" + relleno + "b" }), {});
  assert.deepEqual(paramsDeCookie({ fab_attr: encodeURIComponent(JSON.stringify({ utm_source: "meta", cid: "1000000001" })) }), {});
  assert.deepEqual(paramsDeCookie({}), {});
  assert.deepEqual(paramsDeCookie({ fab_attr: "" }), {});
});

test("fab_attr: clave repetida manda la primera; secuencias % rotas no lanzan", () => {
  assert.deepEqual(paramsDeCookie({ fab_attr: "utm_source=uno&utm_source=dos" }), { utm_source: "uno" });
  assert.doesNotThrow(() => paramsDeCookie({ fab_attr: "utm_source=%E0%A4%A&adid=3000000001" }));
});

test("bump=on: agrega el price_id de bump a los line_items", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, campos: camposBase({ bump: "on" }) }),
  );
  assert.equal(resultado.status, 303);
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  assert.ok(llamadaStripe.opciones.cuerpo.includes("line_items%5B1%5D%5Bprice%5D=price_bump_v1"));
});

test("bump ausente: NO agrega price_id de bump", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(argsBase({ env, transporte, campos: camposBase() }));
  assert.equal(resultado.status, 303);
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  assert.ok(!llamadaStripe.opciones.cuerpo.includes("price_bump_v1"));
});

test("Stripe devuelve una url con host distinto a checkout.stripe.com: nunca redirige, 502", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso({ stripeUrl: "https://atacante.example/pay/cs_test_123" });
  const resultado = await manejarSolicitudSesionFormulario(argsBase({ env, transporte }));
  assert.equal(resultado.status, 502);
  assert.equal(resultado.location, undefined);
});

test("oferta_id ausente del catalogo: 404 y no llama a Stripe", async () => {
  const env = await construirEnv();
  const transporte = crearTransporteFalso();
  const resultado = await manejarSolicitudSesionFormulario(
    argsBase({ env, transporte, campos: camposBase({ oferta_id: "OF-202611-99" }) }),
  );
  assert.equal(resultado.status, 404);
  assert.equal(transporte.llamadas.length, 0);
});
