import assert from "node:assert/strict";
import { test } from "node:test";
import { verificarEnlace } from "../src/enlace.mjs";
import { firmarEnlace } from "../../fulfill/src/enlace.mjs";

// `descarga` solo VERIFICA; el token lo firma `fulfill` (docs/06 4.6, "formato EXACTO"). Por eso
// estas pruebas firman con el modulo de `fulfill` y verifican con el de `descarga`: si algun dia
// alguno de los dos cambia el formato sin que el otro lo siga, estas pruebas lo detectan.
const SECRETO = "secreto-de-prueba-no-real";
const PAYLOAD = {
  sessionId: "cs_test_0001",
  productoSha256: "sha256:" + "a".repeat(64),
  productoVersion: "v1",
  venceEn: "2026-11-20T00:00:00Z",
  maxDescargas: 2,
};

test("verificarEnlace de descarga acepta un token firmado por fulfill", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, SECRETO, { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload.sessionId, "cs_test_0001");
  assert.equal(payload.productoSha256, PAYLOAD.productoSha256);
});

test("verificarEnlace rechaza una firma alterada", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const [cuerpo] = token.split(".");
  const alterado = `${cuerpo}.${"0".repeat(64)}`;
  const payload = await verificarEnlace(alterado, SECRETO, { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload, null);
});

test("verificarEnlace rechaza un token vencido", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, SECRETO, { ahora: new Date("2026-12-01T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload, null);
});

test("verificarEnlace rechaza en el borde exacto de la cuota (maxDescargas=2, descargasHechas=2)", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, SECRETO, { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 2 });
  assert.equal(payload, null);
});

test("verificarEnlace acepta justo antes del tope (descargasHechas=1 de 2)", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, SECRETO, { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 1 });
  assert.equal(payload.sessionId, "cs_test_0001");
});

test("verificarEnlace rechaza con otra clave", async () => {
  const token = await firmarEnlace(PAYLOAD, SECRETO);
  const payload = await verificarEnlace(token, "otra-clave", { ahora: new Date("2026-11-10T00:00:00Z"), descargasHechas: 0 });
  assert.equal(payload, null);
});
