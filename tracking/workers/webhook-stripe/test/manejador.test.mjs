import test from "node:test";
import assert from "node:assert/strict";

import { manejarWebhookStripe } from "../src/manejador.mjs";
import { registrarSiEsNuevo } from "../src/dedupe.mjs";
import { crearAlmacenEnMemoria } from "../../_lib/src/almacen_memoria.mjs";
import { crearCerrojo } from "../../_lib/src/cerrojo.mjs";
import { firmarHmacSha256Hex } from "../../_lib/src/hmac.mjs";

const SECRETO = "whsec_prueba";

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

function crearRegistradorDedupe(almacen = crearAlmacenEnMemoria(), cerrojo = crearCerrojo()) {
  return (claves) => cerrojo.ejecutar(() => registrarSiEsNuevo(almacen, claves));
}

async function construirEntrega({ eventId = "evt_1", sessionId = "cs_test_1", consentMarketing = "1", tEpoch = 1000 } = {}) {
  const cuerpoCrudo = JSON.stringify({
    id: eventId,
    type: "checkout.session.completed",
    data: {
      object: {
        id: sessionId,
        payment_status: "paid",
        amount_total: 1990,
        currency: "eur",
        metadata: {
          consent_marketing: consentMarketing,
          event_source_url: "https://oferta.example/gracias",
        },
      },
    },
  });
  const firma = await firmarHmacSha256Hex(SECRETO, `${tEpoch}.${cuerpoCrudo}`);
  return { cuerpoCrudo, cabeceraFirma: `t=${tEpoch},v1=${firma}`, tEpoch };
}

function configBase({ registrarDedupe, transporte, tEpoch, configCapi = { datasetId: "ds1", token: "tok", apiVersion: "v21.0" } }) {
  return {
    secretoWhsec: SECRETO,
    toleranciaSeg: 300,
    registrarDedupe,
    ahora: () => new Date(tEpoch * 1000),
    configCapi,
    transporte,
  };
}

test("firma valida + consentimiento: responde 200 encolado y llama a Graph", async () => {
  const { cuerpoCrudo, cabeceraFirma, tEpoch } = await construirEntrega();
  const transporte = crearTransporteFalso();
  const resultado = await manejarWebhookStripe({
    cabeceraFirma,
    cuerpoCrudo,
    ...configBase({ registrarDedupe: crearRegistradorDedupe(), transporte, tEpoch }),
  });
  assert.equal(resultado.status, 200);
  assert.equal(resultado.cuerpo.codigo, "encolado");
  assert.equal(transporte.llamadas.length, 1);
});

test("firma falsa: responde 400 y no dedupe ni Graph", async () => {
  const { cuerpoCrudo, tEpoch } = await construirEntrega();
  const transporte = crearTransporteFalso();
  const resultado = await manejarWebhookStripe({
    cabeceraFirma: "t=1000,v1=firmafalsa",
    cuerpoCrudo,
    ...configBase({ registrarDedupe: crearRegistradorDedupe(), transporte, tEpoch }),
  });
  assert.equal(resultado.status, 400);
  assert.equal(resultado.cuerpo.ok, false);
  assert.equal(transporte.llamadas.length, 0);
});

test("firma vencida (fuera de tolerancia): responde 400", async () => {
  const { cuerpoCrudo, cabeceraFirma, tEpoch } = await construirEntrega();
  const transporte = crearTransporteFalso();
  const resultado = await manejarWebhookStripe({
    cabeceraFirma,
    cuerpoCrudo,
    ...configBase({ registrarDedupe: crearRegistradorDedupe(), transporte, tEpoch: tEpoch + 10000 }),
  });
  assert.equal(resultado.status, 400);
  assert.equal(resultado.cuerpo.codigo, "fuera_de_tolerancia");
});

test("duplicado: la segunda entrega del mismo evento responde 200 'duplicado' y no vuelve a llamar a Graph", async () => {
  const { cuerpoCrudo, cabeceraFirma, tEpoch } = await construirEntrega();
  const transporte = crearTransporteFalso();
  const registrarDedupe = crearRegistradorDedupe();
  const config = configBase({ registrarDedupe, transporte, tEpoch });

  const primero = await manejarWebhookStripe({ cabeceraFirma, cuerpoCrudo, ...config });
  const segundo = await manejarWebhookStripe({ cabeceraFirma, cuerpoCrudo, ...config });

  assert.equal(primero.cuerpo.codigo, "encolado");
  assert.equal(segundo.status, 200);
  assert.equal(segundo.cuerpo.codigo, "duplicado");
  assert.equal(transporte.llamadas.length, 1, "Graph solo se llama una vez: una entrega");
});

test("mismo session_id con dos event.id distintos: el segundo es duplicado y una sola entrega", async () => {
  const transporte = crearTransporteFalso();
  const registrarDedupe = crearRegistradorDedupe();
  const primera = await construirEntrega({ eventId: "evt_a", sessionId: "cs_doble" });
  const segunda = await construirEntrega({ eventId: "evt_b", sessionId: "cs_doble" });

  const r1 = await manejarWebhookStripe({
    cabeceraFirma: primera.cabeceraFirma,
    cuerpoCrudo: primera.cuerpoCrudo,
    ...configBase({ registrarDedupe, transporte, tEpoch: primera.tEpoch }),
  });
  const r2 = await manejarWebhookStripe({
    cabeceraFirma: segunda.cabeceraFirma,
    cuerpoCrudo: segunda.cuerpoCrudo,
    ...configBase({ registrarDedupe, transporte, tEpoch: segunda.tEpoch }),
  });

  assert.equal(r1.cuerpo.codigo, "encolado");
  assert.equal(r2.cuerpo.codigo, "duplicado");
  assert.equal(transporte.llamadas.length, 1);
});

test("dos entregas concurrentes del mismo evento: una sola llamada a Graph", async () => {
  const { cuerpoCrudo, cabeceraFirma, tEpoch } = await construirEntrega({ sessionId: "cs_concurrente" });
  const transporte = crearTransporteFalso();
  const registrarDedupe = crearRegistradorDedupe();
  const config = configBase({ registrarDedupe, transporte, tEpoch });

  const [a, b] = await Promise.all([
    manejarWebhookStripe({ cabeceraFirma, cuerpoCrudo, ...config }),
    manejarWebhookStripe({ cabeceraFirma, cuerpoCrudo, ...config }),
  ]);

  const codigos = [a.cuerpo.codigo, b.cuerpo.codigo].sort();
  assert.deepEqual(codigos, ["duplicado", "encolado"]);
  assert.equal(transporte.llamadas.length, 1);
});

test("consent_marketing='0' (cmp=r, sin consentimiento): NO se llama a Graph", async () => {
  const { cuerpoCrudo, cabeceraFirma, tEpoch } = await construirEntrega({ consentMarketing: "0" });
  const transporte = crearTransporteFalso();
  const resultado = await manejarWebhookStripe({
    cabeceraFirma,
    cuerpoCrudo,
    ...configBase({ registrarDedupe: crearRegistradorDedupe(), transporte, tEpoch }),
  });
  assert.equal(resultado.status, 200);
  assert.equal(resultado.cuerpo.codigo, "encolado");
  assert.equal(resultado.cuerpo.capi, "sin_consentimiento");
  assert.equal(transporte.llamadas.length, 0);
});

test("evento no pagado (checkout.session.completed con payment_status != paid): no llama a Graph", async () => {
  const cuerpoCrudo = JSON.stringify({
    id: "evt_no_pagado",
    type: "checkout.session.completed",
    data: { object: { id: "cs_no_pagado", payment_status: "unpaid", metadata: {} } },
  });
  const tEpoch = 1000;
  const firma = await firmarHmacSha256Hex(SECRETO, `${tEpoch}.${cuerpoCrudo}`);
  const transporte = crearTransporteFalso();
  const resultado = await manejarWebhookStripe({
    cabeceraFirma: `t=${tEpoch},v1=${firma}`,
    cuerpoCrudo,
    ...configBase({ registrarDedupe: crearRegistradorDedupe(), transporte, tEpoch }),
  });
  assert.equal(resultado.cuerpo.codigo, "recibido");
  assert.equal(transporte.llamadas.length, 0);
});

test("cuerpo que no es JSON: responde 400 cuerpo_invalido", async () => {
  const tEpoch = 1000;
  const cuerpoCrudo = "no-es-json";
  const firma = await firmarHmacSha256Hex(SECRETO, `${tEpoch}.${cuerpoCrudo}`);
  const resultado = await manejarWebhookStripe({
    cabeceraFirma: `t=${tEpoch},v1=${firma}`,
    cuerpoCrudo,
    ...configBase({ registrarDedupe: crearRegistradorDedupe(), transporte: crearTransporteFalso(), tEpoch }),
  });
  assert.equal(resultado.status, 400);
  assert.equal(resultado.cuerpo.codigo, "cuerpo_invalido");
});
