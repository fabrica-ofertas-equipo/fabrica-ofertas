// Las consultas de almacenD1 contra SQLite real (D1 es SQLite): node --test infra/workers/vivo/test/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";
import { almacenD1 } from "../src/index.mjs";
import { ventaDePayload } from "../src/logica.mjs";

function d1Falso() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(fileURLToPath(new URL("../schema.sql", import.meta.url)), "utf8"));
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    first: async () => db.prepare(sql).get(...args) ?? null,
    all: async () => ({ results: db.prepare(sql).all(...args) }),
    run: async () => db.prepare(sql).run(...args),
  });
  return { prepare: (sql) => stmt(sql), batch: async (ops) => { for (const o of ops) await o.run(); } };
}

test("almacenD1: ventas con upsert e idempotencia, Meta por día y lectura", async () => {
  const al = almacenD1(d1Falso());
  const p = { id: "e1", event: "order.approved", created_at: "2026-11-14T14:00:00Z", data: { order_id: "o1", order_number: 1, status: "approved", total: 19, currency: "USD", order_created_at: "2026-11-14T13:00:00Z", store: { subdomain: "t" } } };
  await al.guardarVenta(ventaDePayload(p));
  assert.equal(await al.yaVisto("e1"), true);
  await al.guardarVenta(ventaDePayload({ ...p, id: "e2", data: { ...p.data, total: 20 } }));   // misma orden y evento: actualiza
  await al.guardarVenta(ventaDePayload({ ...p, id: "e3", test: true, data: { ...p.data, order_id: "TEST-9" } }));
  const filas = [{ fecha: "2026-11-14", campana: "c1", nombre: "n", gasto: 10, impresiones: 1, clics: 1, visitas: 1, pagos_iniciados: 0, compras: 0, valor_compras: 0, leido: "L1" }];
  await al.guardarMeta(filas, [{ id: "c1" }], "L1", null);
  await al.guardarMeta([{ ...filas[0], gasto: 12, leido: "L2" }], [{ id: "c1" }], "L2", null);
  const d = await al.leer("2026-11-14");
  assert.equal(d.ventas.length, 1, "la prueba de Impultienda no se lista");
  assert.equal(d.ventas[0].total, 20);
  assert.equal(d.meta_dia.length, 1);
  assert.equal(d.meta_dia[0].gasto, 12);
  assert.equal(d.meta_estado.leido, "L2");
  assert.ok(d.ultimo_aviso);
});

test("almacenD1: carritos y órdenes aprobadas", async () => {
  const { carritoDePayload } = await import("../src/logica.mjs");
  const al = almacenD1(d1Falso());
  const base = { created_at: "2026-11-15T10:00:00Z", data: { order_id: "o9", status: "pending", total: 32, currency: "USD", order_created_at: "2026-11-15T09:20:00Z", customer: { email: "x@y.z" }, store: { subdomain: "tienda-a" } } };
  await al.guardarCarrito(carritoDePayload({ ...base, id: "c1", event: "order.abandoned" }, false));
  await al.guardarVenta(ventaDePayload({ ...base, id: "v1", event: "order.approved", data: { ...base.data, status: "approved" } }));
  const r = await al.leerCarritos("2026-11-15T00:00:00Z");
  assert.equal(r.carritos.length, 1);
  assert.equal(r.carritos[0].tienda, "tienda-a");
  assert.deepEqual(r.aprobadas, ["o9"]);
  assert.equal(await al.yaVisto("c1"), true);
});
