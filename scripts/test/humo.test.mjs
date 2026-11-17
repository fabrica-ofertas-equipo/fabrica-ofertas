// Prueba de humo de Node: módulos ES y node:test funcionan sin dependencias.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

test("módulos ES y SHA-256 disponibles", () => {
  const hash = createHash("sha256").update("{}", "utf8").digest("hex");
  assert.equal(hash, "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a");
});

test("fetch y crypto.subtle existen (Workers usan la misma API web)", () => {
  assert.equal(typeof fetch, "function");
  assert.equal(typeof globalThis.crypto.subtle.digest, "function");
});
