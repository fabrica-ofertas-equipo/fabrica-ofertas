// node --test infra/workers/registro/test/*.test.mjs   (SQLite real: D1 es SQLite)
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";
import { manejarPeticion, almacenD1 } from "../src/index.mjs";
import { sha256Hex, estadoResultante, tomadaPorOtra } from "../src/logica.mjs";

function d1Falso() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(fileURLToPath(new URL("../schema.sql", import.meta.url)), "utf8"));
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    first: async () => db.prepare(sql).get(...args) ?? null,
    all: async () => ({ results: db.prepare(sql).all(...args) }),
    run: async () => db.prepare(sql).run(...args),
  });
  return { raw: db, prepare: (sql) => stmt(sql), batch: async (ops) => { for (const o of ops) await o.run(); } };
}

async function montar() {
  const db = d1Falso();
  for (const [tok, id] of [["tok-a", "principal"], ["tok-b", "socia-1"]]) {
    db.raw.prepare("INSERT INTO instalaciones (token_hash, id, alta) VALUES (?,?,?)").run(await sha256Hex(tok), id, "2026-11-14");
  }
  return almacenD1(db);
}

const H1 = "a".repeat(64), H2 = "b".repeat(64), H3 = "c".repeat(64);
const pedir = (al, ruta, cuerpo, tok, ahora = new Date("2026-11-14T12:00:00Z")) =>
  manejarPeticion(new Request(`https://registro.x${ruta}`, { method: "POST", body: JSON.stringify(cuerpo),
    headers: { "content-type": "application/json", ...(tok ? { authorization: `Bearer ${tok}` } : {}) } }), {}, al, { ahora }).then(async (r) => ({ status: r.status, body: await r.json() }));

test("sin token o con token desconocido: 401", async () => {
  const al = await montar();
  assert.equal((await pedir(al, "/consultar", { huellas: [H1] })).status, 401);
  assert.equal((await pedir(al, "/consultar", { huellas: [H1] }, "otro")).status, 401);
});

test("el primero que reserva se la queda; la otra la ve tomada y no puede reservarla", async () => {
  const al = await montar();
  const r1 = await pedir(al, "/reservar", { items: [{ huella: H1, estado: "banco" }, { huella: H2, estado: "lanzada" }] }, "tok-a");
  assert.deepEqual(r1.body.resultado, { [H1]: "ok", [H2]: "ok" });
  const c = await pedir(al, "/consultar", { huellas: [H1, H2, H3] }, "tok-b");
  assert.deepEqual(c.body.tomadas.sort(), [H1, H2]);
  const propia = await pedir(al, "/consultar", { huellas: [H1] }, "tok-a");
  assert.deepEqual(propia.body.tomadas, [], "lo propio no figura como tomado");
  const r2 = await pedir(al, "/reservar", { items: [{ huella: H1, estado: "modelando" }, { huella: H3, estado: "banco" }] }, "tok-b");
  assert.deepEqual(r2.body.resultado, { [H1]: "tomada", [H3]: "ok" });
});

test("una reserva vencida se libera sola; lanzada dura un año", async () => {
  const al = await montar();
  await pedir(al, "/reservar", { items: [{ huella: H1, estado: "banco" }, { huella: H2, estado: "lanzada" }] }, "tok-a");
  const despues = new Date("2026-12-10T12:00:00Z");   // 26 días: banco (21) venció, lanzada no
  const c = await pedir(al, "/consultar", { huellas: [H1, H2] }, "tok-b", despues);
  assert.deepEqual(c.body.tomadas, [H2]);
  const r = await pedir(al, "/reservar", { items: [{ huella: H1, estado: "banco" }] }, "tok-b", despues);
  assert.equal(r.body.resultado[H1], "ok");
});

test("el estado propio nunca baja y liberar solo toca lo propio", async () => {
  assert.equal(estadoResultante("lanzada", "banco"), "lanzada");
  assert.equal(estadoResultante("banco", "modelando"), "modelando");
  assert.equal(tomadaPorOtra(null, "x", new Date()), false);
  const al = await montar();
  await pedir(al, "/reservar", { items: [{ huella: H1, estado: "lanzada" }] }, "tok-a");
  await pedir(al, "/reservar", { items: [{ huella: H1, estado: "banco" }] }, "tok-a");
  const n = await pedir(al, "/liberar", { huellas: [H1] }, "tok-b");
  assert.equal(n.body.liberadas, 0);
  assert.deepEqual((await pedir(al, "/consultar", { huellas: [H1] }, "tok-b")).body.tomadas, [H1]);
  assert.equal((await pedir(al, "/liberar", { huellas: [H1] }, "tok-a")).body.liberadas, 1);
  assert.deepEqual((await pedir(al, "/consultar", { huellas: [H1] }, "tok-b")).body.tomadas, []);
});

test("cuerpos inválidos: 400; rutas desconocidas: 404; salud pública", async () => {
  const al = await montar();
  assert.equal((await pedir(al, "/reservar", { items: [{ huella: "dominio.com", estado: "banco" }] }, "tok-a")).status, 400);
  assert.equal((await pedir(al, "/reservar", { items: [{ huella: H1, estado: "otro" }] }, "tok-a")).status, 400);
  assert.equal((await pedir(al, "/consultar", { huellas: [] }, "tok-a")).status, 400);
  assert.equal((await pedir(al, "/borrar", {}, "tok-a")).status, 404);
  const s = await manejarPeticion(new Request("https://registro.x/salud"), {}, al);
  assert.deepEqual(await s.json(), { ok: true });
});
