import test from "node:test";
import assert from "node:assert/strict";

import { registrarSiEsNuevo } from "../src/dedupe.mjs";
import { crearAlmacenEnMemoria } from "../../_lib/src/almacen_memoria.mjs";
import { crearCerrojo } from "../../_lib/src/cerrojo.mjs";

test("primer evento: no es duplicado", async () => {
  const almacen = crearAlmacenEnMemoria();
  const resultado = await registrarSiEsNuevo(almacen, {
    eventId: "evt_1",
    tipo: "checkout.session.completed",
    objetoId: "cs_test_1",
  });
  assert.equal(resultado.duplicado, false);
});

test("mismo event.id dos veces: la segunda es duplicado", async () => {
  const almacen = crearAlmacenEnMemoria();
  const claves = { eventId: "evt_1", tipo: "checkout.session.completed", objetoId: "cs_test_1" };
  const primero = await registrarSiEsNuevo(almacen, claves);
  const segundo = await registrarSiEsNuevo(almacen, claves);
  assert.equal(primero.duplicado, false);
  assert.equal(segundo.duplicado, true);
});

test("mismo session_id con DOS event.id distintos: el segundo es duplicado por (tipo, objeto_id)", async () => {
  const almacen = crearAlmacenEnMemoria();
  const primero = await registrarSiEsNuevo(almacen, {
    eventId: "evt_1",
    tipo: "checkout.session.completed",
    objetoId: "cs_test_1",
  });
  const segundo = await registrarSiEsNuevo(almacen, {
    eventId: "evt_2", // Stripe puede emitir dos Event distintos para el mismo hecho
    tipo: "checkout.session.completed",
    objetoId: "cs_test_1",
  });
  assert.equal(primero.duplicado, false);
  assert.equal(segundo.duplicado, true);
});

test("mismo event.id pero tipo/objeto distinto (teorico): tambien se marca duplicado por event.id", async () => {
  const almacen = crearAlmacenEnMemoria();
  await registrarSiEsNuevo(almacen, { eventId: "evt_x", tipo: "a", objetoId: "o1" });
  const segundo = await registrarSiEsNuevo(almacen, { eventId: "evt_x", tipo: "b", objetoId: "o2" });
  assert.equal(segundo.duplicado, true);
});

test("dos entregas concurrentes del mismo evento: solo una se registra como nueva", async () => {
  const almacen = crearAlmacenEnMemoria();
  const cerrojo = crearCerrojo();
  const claves = { eventId: "evt_concurrente", tipo: "checkout.session.completed", objetoId: "cs_concurrente" };

  const registrarConCerrojo = () => cerrojo.ejecutar(() => registrarSiEsNuevo(almacen, claves));

  const [a, b] = await Promise.all([registrarConCerrojo(), registrarConCerrojo()]);
  const nuevos = [a, b].filter((r) => r.duplicado === false);
  const duplicados = [a, b].filter((r) => r.duplicado === true);
  assert.equal(nuevos.length, 1);
  assert.equal(duplicados.length, 1);
});

test("eventos distintos no colisionan entre si", async () => {
  const almacen = crearAlmacenEnMemoria();
  const a = await registrarSiEsNuevo(almacen, { eventId: "evt_a", tipo: "t", objetoId: "o_a" });
  const b = await registrarSiEsNuevo(almacen, { eventId: "evt_b", tipo: "t", objetoId: "o_b" });
  assert.equal(a.duplicado, false);
  assert.equal(b.duplicado, false);
});
