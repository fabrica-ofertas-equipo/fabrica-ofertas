import test from "node:test";
import assert from "node:assert/strict";

import {
  idPurchase,
  idInitiateCheckout,
  normalizarEmail,
  normalizarTelefono,
  hashCampo,
  eventoEsReciente,
  construirUserData,
  construirEventoPurchase,
  construirEventoInitiateCheckout,
  enviarEventos,
  enviarPurchaseSiCorresponde,
} from "../src/capi.mjs";
import { sha256Hex } from "../../_lib/src/hash.mjs";

function crearTransporteFalso() {
  const llamadas = [];
  return {
    llamadas,
    async solicitar(metodo, url, opciones) {
      llamadas.push({ metodo, url, opciones });
      return { estado: 200, cuerpo: JSON.stringify({ events_received: 1 }) };
    },
  };
}

test("idPurchase es determinista: purchase_<session_id>", () => {
  assert.equal(idPurchase("cs_test_123"), "purchase_cs_test_123");
});

test("idInitiateCheckout es determinista: ic_<visitor_id>_<ts>", () => {
  assert.equal(idInitiateCheckout("visitante-1", 1000), "ic_visitante-1_1000");
});

test("normalizarEmail recorta y pasa a minusculas", () => {
  assert.equal(normalizarEmail("  Persona@Ejemplo.COM  "), "persona@ejemplo.com");
});

test("normalizarTelefono deja solo digitos", () => {
  assert.equal(normalizarTelefono("+54 (9) 11-2345-6789"), "5491123456789");
});

test("hashCampo coincide con sha256Hex del valor normalizado", async () => {
  const esperado = await sha256Hex("persona@ejemplo.com");
  assert.equal(await hashCampo("persona@ejemplo.com"), esperado);
});

test("eventoEsReciente: dentro de 6 dias es verdadero", () => {
  const ahora = new Date("2026-11-06T00:00:00Z");
  const hace5dias = "2026-11-01T00:00:01Z";
  assert.equal(eventoEsReciente(hace5dias, ahora), true);
});

test("eventoEsReciente: mas de 6 dias es falso", () => {
  const ahora = new Date("2026-11-06T00:00:00Z");
  const hace7dias = "2026-10-30T00:00:00Z";
  assert.equal(eventoEsReciente(hace7dias, ahora), false);
});

test("construirUserData: fbp/fbc sin hash, em/ph con SHA-256", async () => {
  const userData = await construirUserData({
    fbp: "fb.1.1111111111.2222222222",
    fbc: "fb.1.1111111111.clickid",
    email: "Persona@Ejemplo.com",
    telefono: "+54 9 11 2345 6789",
  });
  assert.equal(userData.fbp, "fb.1.1111111111.2222222222");
  assert.equal(userData.fbc, "fb.1.1111111111.clickid");
  assert.deepEqual(userData.em, [await hashCampo("persona@ejemplo.com")]);
  assert.deepEqual(userData.ph, [await hashCampo("5491123456789")]);
});

test("construirUserData: sin fbp/fbc/email/telefono no incluye esas claves", async () => {
  const userData = await construirUserData({});
  assert.deepEqual(userData, {});
});

test("construirEventoPurchase: event_id y datos minimos", async () => {
  const evento = await construirEventoPurchase({
    sessionId: "cs_test_abc",
    eventTimeIso: "2026-11-06T12:00:00Z",
    eventSourceUrl: "https://oferta.example/gracias",
    fbp: null,
    fbc: null,
    email: null,
    telefono: null,
    valorDecimal: "19.90",
    moneda: "EUR",
  });
  assert.equal(evento.event_name, "Purchase");
  assert.equal(evento.event_id, "purchase_cs_test_abc");
  assert.equal(evento.action_source, "website");
  assert.equal(evento.custom_data.value, "19.90");
  assert.equal(evento.custom_data.currency, "EUR");
  assert.deepEqual(evento.user_data, {});
});

test("construirEventoInitiateCheckout: sin datos de contacto", async () => {
  const evento = await construirEventoInitiateCheckout({
    visitorId: "visitante-1",
    eventTimeIso: "2026-11-06T12:00:00Z",
    eventSourceUrl: "https://oferta.example/landing",
    fbp: "fb.1.1.1",
    fbc: null,
  });
  assert.equal(evento.event_name, "InitiateCheckout");
  assert.equal(evento.user_data.fbp, "fb.1.1.1");
  assert.equal("ph" in evento.user_data, false);
  assert.equal("em" in evento.user_data, false);
});

test("enviarEventos construye la URL de Graph con dataset y version, e incluye test_event_code", async () => {
  const transporte = crearTransporteFalso();
  await enviarEventos(transporte, {
    datasetId: "123456789",
    token: "token-secreto",
    apiVersion: "v21.0",
    eventos: [{ event_name: "Purchase" }],
    testEventCode: "TEST12345",
  });
  assert.equal(transporte.llamadas.length, 1);
  const llamada = transporte.llamadas[0];
  assert.equal(llamada.metodo, "POST");
  assert.equal(llamada.url, "https://graph.facebook.com/v21.0/123456789/events");
  const cuerpo = JSON.parse(llamada.opciones.cuerpo);
  assert.equal(cuerpo.access_token, "token-secreto");
  assert.equal(cuerpo.test_event_code, "TEST12345");
  assert.equal(cuerpo.data.length, 1);
});

test("enviarPurchaseSiCorresponde: sin consentimiento NO llama a Graph (caso 'cmp=r')", async () => {
  const transporte = crearTransporteFalso();
  const resultado = await enviarPurchaseSiCorresponde({
    consentMarketing: "0",
    sessionId: "cs_test_1",
    eventTimeIso: "2026-11-06T00:00:00Z",
    eventSourceUrl: "https://oferta.example/gracias",
    valorDecimal: "19.90",
    moneda: "EUR",
    datasetId: "ds1",
    token: "tok",
    apiVersion: "v21.0",
    ahora: new Date("2026-11-06T00:05:00Z"),
    transporte,
  });
  assert.equal(resultado.enviado, false);
  assert.equal(resultado.motivo, "sin_consentimiento");
  assert.equal(transporte.llamadas.length, 0);
});

test("enviarPurchaseSiCorresponde: con consentimiento SI llama a Graph", async () => {
  const transporte = crearTransporteFalso();
  const resultado = await enviarPurchaseSiCorresponde({
    consentMarketing: "1",
    sessionId: "cs_test_2",
    eventTimeIso: "2026-11-06T00:00:00Z",
    eventSourceUrl: "https://oferta.example/gracias",
    valorDecimal: "19.90",
    moneda: "EUR",
    datasetId: "ds1",
    token: "tok",
    apiVersion: "v21.0",
    ahora: new Date("2026-11-06T00:05:00Z"),
    transporte,
  });
  assert.equal(resultado.enviado, true);
  assert.equal(transporte.llamadas.length, 1);
  assert.equal(resultado.evento.event_id, "purchase_cs_test_2");
});

test("enviarPurchaseSiCorresponde: evento fuera de ventana de 6 dias no llama a Graph", async () => {
  const transporte = crearTransporteFalso();
  const resultado = await enviarPurchaseSiCorresponde({
    consentMarketing: "1",
    sessionId: "cs_test_3",
    eventTimeIso: "2026-10-01T00:00:00Z",
    eventSourceUrl: "https://oferta.example/gracias",
    valorDecimal: "19.90",
    moneda: "EUR",
    datasetId: "ds1",
    token: "tok",
    apiVersion: "v21.0",
    ahora: new Date("2026-11-06T00:05:00Z"),
    transporte,
  });
  assert.equal(resultado.enviado, false);
  assert.equal(resultado.motivo, "fuera_de_ventana_6_dias");
  assert.equal(transporte.llamadas.length, 0);
});
