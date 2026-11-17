import assert from "node:assert/strict";
import { test } from "node:test";
import { manejarPeticion } from "../src/index.mjs";
import { firmarEnlace } from "../../fulfill/src/enlace.mjs";

const SECRETO = "secreto-de-prueba-no-real";
const AHORA = () => new Date("2026-11-10T00:00:00Z");

class KVFalso {
  constructor() { this.datos = new Map(); }
  async get(clave) { return this.datos.has(clave) ? this.datos.get(clave) : null; }
  async put(clave, valor) { this.datos.set(clave, valor); }
}

class BucketFalso {
  constructor(objetos = {}) { this.objetos = objetos; }
  async get(clave) { return this.objetos[clave] ?? null; }
}

test("POST a /d/<sessionId> no esta permitido (405)", async () => {
  const env = { CONTADORES: new KVFalso(), BUCKET_PRODUCTOS: new BucketFalso(), DESCARGA_HMAC: SECRETO };
  const resp = await manejarPeticion(new Request("https://descargas.ejemplo/d/cs_test_0001?token=x.y", { method: "POST" }), env);
  assert.equal(resp.status, 405);
});

test("GET sin token: 400", async () => {
  const env = { CONTADORES: new KVFalso(), BUCKET_PRODUCTOS: new BucketFalso(), DESCARGA_HMAC: SECRETO };
  const resp = await manejarPeticion(new Request("https://descargas.ejemplo/d/cs_test_0001"), env);
  assert.equal(resp.status, 400);
});

test("GET con token invalido: 403", async () => {
  const env = { CONTADORES: new KVFalso(), BUCKET_PRODUCTOS: new BucketFalso(), DESCARGA_HMAC: SECRETO };
  const resp = await manejarPeticion(new Request("https://descargas.ejemplo/d/cs_test_0001?token=invalido.invalido"), env);
  assert.equal(resp.status, 403);
});

test("GET con token valido y producto en el bucket: 200 con el cuerpo y content-type", async () => {
  const sha = "sha256:" + "a".repeat(64);
  const token = await firmarEnlace(
    { sessionId: "cs_test_0001", productoSha256: sha, productoVersion: "v1", venceEn: "2026-11-20T00:00:00Z", maxDescargas: 3 },
    SECRETO,
  );
  const env = {
    CONTADORES: new KVFalso(),
    BUCKET_PRODUCTOS: new BucketFalso({ [sha]: { body: "contenido-fake", httpMetadata: { contentType: "application/pdf" } } }),
    DESCARGA_HMAC: SECRETO,
  };
  const resp = await manejarPeticion(
    new Request(`https://descargas.ejemplo/d/cs_test_0001?token=${encodeURIComponent(token)}`),
    env,
    { ahora: AHORA },
  );
  assert.equal(resp.status, 200);
  assert.equal(resp.headers.get("content-type"), "application/pdf");
  assert.equal(await resp.text(), "contenido-fake");
});

test("sin binding DESCARGA_HMAC: 500, no se confunde con 'invalido'", async () => {
  const env = { CONTADORES: new KVFalso(), BUCKET_PRODUCTOS: new BucketFalso() };
  const resp = await manejarPeticion(new Request("https://descargas.ejemplo/d/cs_test_0001?token=x.y"), env);
  assert.equal(resp.status, 500);
});
