import test from "node:test";
import assert from "node:assert/strict";

import { manejarEvento } from "../src/manejador.mjs";
import { verificarHmacSha256 } from "../../_lib/src/hmac.mjs";

const SECRETO = "ingest-secreto";

function cuerpoBase(overrides = {}) {
  return {
    oferta_id: "OF-202611-01",
    tipo: "PageView",
    ts: "2026-11-06T12:00:00Z",
    visitor_id: "v".repeat(20),
    cid: "1000000001",
    asid: "2000000001",
    adid: "3000000001",
    fuente: "landing",
    consentimiento: true,
    ...overrides,
  };
}

function crearTransporteFalso(estado = 200) {
  const llamadas = [];
  return {
    llamadas,
    async solicitar(metodo, url, opciones) {
      llamadas.push({ metodo, url, opciones });
      return { estado, cuerpo: JSON.stringify({ ok: true }) };
    },
  };
}

test("evento valido: 202 aceptado y firma correcta en las cabeceras", async () => {
  const transporte = crearTransporteFalso();
  const resultado = await manejarEvento({
    cuerpo: cuerpoBase(),
    env: { ingestSecret: SECRETO, ingestaEventoUrl: "https://api.example/ingesta/evento" },
    ahora: () => new Date("2026-11-06T12:00:05Z"),
    transporte,
  });
  assert.equal(resultado.status, 202);
  assert.equal(transporte.llamadas.length, 1);
  const llamada = transporte.llamadas[0];
  assert.equal(llamada.url, "https://api.example/ingesta/evento");
  const ts = llamada.opciones.cabeceras["X-Fabrica-Ts"];
  const firmaCabecera = llamada.opciones.cabeceras["X-Fabrica-Firma"];
  assert.equal(ts, "2026-11-06T12:00:05Z");
  const firmaHex = firmaCabecera.replace("hmac-sha256=", "");
  const valida = await verificarHmacSha256(SECRETO, `${ts}.${llamada.opciones.cuerpo}`, firmaHex);
  assert.equal(valida, true);
});

test("tipo no permitido (Purchase no es responsabilidad de este Worker): rechaza por validacion", async () => {
  const resultado = await manejarEvento({
    cuerpo: cuerpoBase({ tipo: "Purchase" }),
    env: { ingestSecret: SECRETO, ingestaEventoUrl: "https://api.example/ingesta/evento" },
    ahora: () => new Date(),
    transporte: crearTransporteFalso(),
  });
  assert.equal(resultado.status, 400);
  assert.ok(resultado.cuerpo.errores.includes("tipo_invalido"));
});

test("timestamp sin Z: rechaza por validacion", async () => {
  const resultado = await manejarEvento({
    cuerpo: cuerpoBase({ ts: "2026-11-06T12:00:00" }),
    env: { ingestSecret: SECRETO, ingestaEventoUrl: "https://api.example/ingesta/evento" },
    ahora: () => new Date(),
    transporte: crearTransporteFalso(),
  });
  assert.equal(resultado.status, 400);
  assert.ok(resultado.cuerpo.errores.includes("ts_invalido"));
});

test("duplicado (409 del servicio de ingesta): responde 200 'duplicado'", async () => {
  const resultado = await manejarEvento({
    cuerpo: cuerpoBase(),
    env: { ingestSecret: SECRETO, ingestaEventoUrl: "https://api.example/ingesta/evento" },
    ahora: () => new Date(),
    transporte: crearTransporteFalso(409),
  });
  assert.equal(resultado.status, 200);
  assert.equal(resultado.cuerpo.codigo, "duplicado");
});

test("sin configuracion (secreto o url ausentes): 500 config_pendiente, nunca asume", async () => {
  const resultado = await manejarEvento({
    cuerpo: cuerpoBase(),
    env: { ingestSecret: null, ingestaEventoUrl: null },
    ahora: () => new Date(),
    transporte: crearTransporteFalso(),
  });
  assert.equal(resultado.status, 500);
  assert.equal(resultado.cuerpo.codigo, "config_pendiente");
});

test("adid fuera de formato: rechaza por validacion", async () => {
  const resultado = await manejarEvento({
    cuerpo: cuerpoBase({ adid: "123" }),
    env: { ingestSecret: SECRETO, ingestaEventoUrl: "https://api.example/ingesta/evento" },
    ahora: () => new Date(),
    transporte: crearTransporteFalso(),
  });
  assert.equal(resultado.status, 400);
  assert.ok(resultado.cuerpo.errores.includes("adid_invalido"));
});

async function eventIdEnviado(cuerpo) {
  const transporte = crearTransporteFalso();
  await manejarEvento({
    cuerpo,
    env: { ingestSecret: SECRETO, ingestaEventoUrl: "https://api.example/ingesta/evento" },
    ahora: () => new Date("2026-11-06T12:00:05Z"),
    transporte,
  });
  return JSON.parse(transporte.llamadas[0].opciones.cuerpo).event_id;
}

test("event_id por defecto CON consentimiento: determinista tipo_visitor_ts (un reintento cae en el mismo id)", async () => {
  const a = await eventIdEnviado(cuerpoBase());
  const b = await eventIdEnviado(cuerpoBase());
  assert.equal(a, `PageView_${"v".repeat(20)}_2026-11-06T12:00:00Z`);
  assert.equal(a, b);
});

test("event_id por defecto SIN consentimiento: no lleva el visitor_id y no es determinista", async () => {
  const visitor = "visitante-privado-1234";
  const a = await eventIdEnviado(cuerpoBase({ consentimiento: false, visitor_id: visitor }));
  const b = await eventIdEnviado(cuerpoBase({ consentimiento: false, visitor_id: visitor }));
  assert.ok(!a.includes(visitor), a);
  assert.match(a, /^PageView_sa_[0-9a-f]{32}_2026-11-06T12:00:00Z$/);
  assert.notEqual(a, b);
  assert.match(a, /^[A-Za-z0-9_.:-]{8,128}$/); // cumple el formato que valida el servicio de ingesta
});

test("si el cliente manda su propio event_id se respeta tal cual, con o sin consentimiento", async () => {
  assert.equal(await eventIdEnviado(cuerpoBase({ event_id: "evento-del-cliente-1", consentimiento: false })), "evento-del-cliente-1");
  assert.equal(await eventIdEnviado(cuerpoBase({ event_id: "evento-del-cliente-2" })), "evento-del-cliente-2");
});
