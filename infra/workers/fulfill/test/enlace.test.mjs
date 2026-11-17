import assert from "node:assert/strict";
import { test } from "node:test";
import { firmarEnlace, verificarEnlace } from "../src/enlace.mjs";

const SECRETO = "secreto-de-prueba-no-real";
const PAYLOAD = {
  sessionId: "cs_test_0001",
  productoSha256: "sha256:" + "a".repeat(64),
  productoVersion: "v1",
  venceEn: "2026-11-20T00:00:00Z",
  maxDescargas: 5,
};

test("firmarEnlace produce un token con dos partes separadas por punto", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  assert.equal(token.split(".").length, 2);
});

test("verificarEnlace acepta un token válido, sin vencer y con cuota", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, SECRETO, { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload.sessionId, "cs_test_0001");
});

test("verificarEnlace rechaza una firma alterada", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const [cuerpo] = token.split(".");
  const alterado = `${cuerpo}.0000000000000000000000000000000000000000000000000000000000000000`;
  const payload = await verificarEnlace(alterado, SECRETO, { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload, null);
});

test("verificarEnlace rechaza un token vencido", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, SECRETO, { ahora: new Date("2026-12-01T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload, null);
});

test("verificarEnlace rechaza cuando se agotó la cuota de descargas", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, SECRETO, { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 5 });
  assert.equal(payload, null);
});

test("verificarEnlace rechaza con otra clave", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, "otra-clave", { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload, null);
});
